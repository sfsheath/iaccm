"""PDF ingest. Render plate pages and read them with the model to produce one structured
``FormRecord`` per published form.

IMPORTANT (CLAUDE.md rule 2): extraction is **visual-first**. We render every plate page in the
requested range and read it; we never decide a ware "has no form of type X" from the text layer
alone — a wrapped or mis-OCR'd line would silently drop the right candidate. The founding bug
lived exactly here.

Rendering uses PyMuPDF (``fitz``) — no ``poppler`` needed. Rendered pages/crops are transient and
git-ignored (``*.plate.png`` under ``.cache/``); they are derived from copyrighted source and are
never committed or exported (docs/copyright.md). Sending a page to the model for identification is
acceptable (owner's call: fair use); the *exported* artifact is facts + pointers only.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..catalog.archetypes import ARCHETYPES
from ..catalog.models import FormRecord, PartType, SourcePointer
from ..catalog.vessel_class import normalize_vessel_class
from ..config import get_settings
from ..model import ModelClient, get_model_client
from ..model.base import json_schema_instruction, parse_json_response
from .profiles import SourceProfile, build_prompt
from .windows import ClassWindow, class_windows

# --- locator + extraction schema (what the model returns per page) -------------------------

class FormBBox(BaseModel):
    """Normalized box (0–1) around one form's profile drawing on the rendered page."""

    x0: float
    y0: float
    x1: float
    y1: float


class ExtractedForm(BaseModel):
    ware: str  # running header / ware, e.g. "CLAIR-C"
    form_id: str  # printed catalogue number for this form, e.g. "Dn 9.11"
    vessel_class: str  # printed shape word(s); normalized to canonical English in _to_record
    part_types: list[str] = Field(default_factory=list)  # mapped to PartType downstream
    description: str = ""  # our paraphrase of the diagnostic attributes
    origin: str | None = None  # production origin/region
    contents: str | None = None  # transported product
    date_start: int | None = None  # negative = BCE
    date_end: int | None = None
    archetype_ids: list[str] = Field(default_factory=list)  # 1–2 ids from the vocabulary
    cross_refs: list[str] = Field(default_factory=list)  # printed equivalences, e.g. "Hayes 50B"
    figure_label: str | None = None  # plate/figure label as printed
    item_label: str | None = None  # item number within the plate
    bbox: FormBBox | None = None  # box of this form's drawing; None if not drawn on this page
    bbox_image_index: int | None = None  # multi-image (class-window) only: which attached image
    #                                      (0-based) the bbox is on; ignored for single-image pages


class PageForms(BaseModel):
    forms: list[ExtractedForm] = Field(default_factory=list)


# --- checksum ------------------------------------------------------------------------------

def checksum(pdf_path: Path) -> str:
    """Content hash that binds a shared index bundle to the user's own local PDF."""
    h = hashlib.sha256()
    with Path(pdf_path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_source_pdf(
    target_checksum: str | None, source_file: str | None = None
) -> Path | None:
    """Resolve a catalog pointer to a local PDF in the corpus dir, so a distributed bundle works
    against a recipient's own drop-in copy. Tries, in order: exact content checksum (same file),
    then the original filename, then — if the corpus holds exactly one PDF — that file."""
    corpus = get_settings().corpus_path
    pdfs = sorted(corpus.glob("*.pdf"))
    if target_checksum:
        for pdf in pdfs:
            if checksum(pdf) == target_checksum:
                return pdf
    if source_file:
        for pdf in pdfs:
            if pdf.name == source_file:
                return pdf
    return pdfs[0] if len(pdfs) == 1 else None


# --- rendering (fitz) ----------------------------------------------------------------------

def _cache_dir() -> Path:
    d = get_settings().root / ".cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def render_page(pdf_path: Path, page_pdf: int, dpi: int = 200) -> Path:
    """Render a 1-based PDF page to a transient PNG under the ignored cache dir."""
    import fitz  # PyMuPDF, lazy import

    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as doc:
        page = doc[page_pdf - 1]
        pix = page.get_pixmap(dpi=dpi)
        out = _cache_dir() / f"{pdf_path.stem}_p{page_pdf}.plate.png"
        pix.save(out)
    return out


def render_region(
    pdf_path: Path, page_pdf: int, bbox: list[float] | None, dpi: int = 200
) -> Path:
    """Render a normalized-bbox crop of a page, or the whole page when ``bbox`` is None."""
    import fitz

    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as doc:
        page = doc[page_pdf - 1]
        if bbox is None:
            return render_page(pdf_path, page_pdf, dpi=dpi)
        r = page.rect
        x0, y0, x1, y1 = bbox
        clip = fitz.Rect(
            r.x0 + x0 * r.width, r.y0 + y0 * r.height,
            r.x0 + x1 * r.width, r.y0 + y1 * r.height,
        )
        pix = page.get_pixmap(dpi=dpi, clip=clip)
        tag = "-".join(str(int(round(v * 1000))) for v in bbox)  # unique per crop region
        out = _cache_dir() / f"{pdf_path.stem}_p{page_pdf}_{tag}.crop.plate.png"
        pix.save(out)
    return out


def render_candidate_crops(
    forms: list[FormRecord], n: int, *, dpi: int = 200
) -> list[tuple[Path, str]]:
    """Render the profile-drawing crops of up to ``n`` candidate forms, for visual comparison.

    Per form: resolve its source PDF (``find_source_pdf``) and render its ``bbox`` crop
    (``render_region``); a form with no bbox falls back to its whole page; a form whose PDF cannot
    be resolved is skipped (stays a text-only candidate). Deduped by (source_file, page_pdf, bbox);
    input order preserved, capped at ``n``. Crops land in the git-ignored cache. Returns
    ``(png_path, form_id)`` pairs so the caller can key images→forms in the prompt."""
    out: list[tuple[Path, str]] = []
    seen: set[tuple[str | None, int, tuple[float, ...] | None]] = set()
    for f in forms:
        src = f.source
        if src is None or src.page_pdf is None:
            continue
        key = (src.source_file, src.page_pdf, tuple(src.bbox) if src.bbox else None)
        if key in seen:
            continue
        pdf = find_source_pdf(src.checksum, src.source_file)
        if pdf is None:
            continue
        seen.add(key)
        out.append((render_region(pdf, src.page_pdf, src.bbox, dpi=dpi), f.id))
        if len(out) >= n:
            break
    return out


def page_has_vector_art(pdf_path: Path, page_pdf: int, threshold: int = 20) -> bool:
    """Heuristic probe: are the plates vector line art (many drawing paths) or raster scans?
    Picks the eventual high-precision bbox method; for v1 we localize via the model regardless."""
    import fitz

    with fitz.open(Path(pdf_path)) as doc:
        return len(doc[page_pdf - 1].get_drawings()) >= threshold


# --- extraction ----------------------------------------------------------------------------

_PART_VALUES = {p.value: p for p in PartType}


def _to_part_types(values: Iterable[str]) -> list[PartType]:
    out: list[PartType] = []
    for v in values:
        p = _PART_VALUES.get(str(v).strip().lower())
        if p and p not in out:
            out.append(p)
    return out or [PartType.UNKNOWN]


_ARCH_IDS = {a.id for a in ARCHETYPES}


def _to_record(
    ef: ExtractedForm,
    short_title: str,
    source_file: str,
    printed: int,
    page_pdf: int,
    cs: str,
    ware_override: str | None = None,
) -> FormRecord:
    """Map one model-extracted form to a stored ``FormRecord`` (shared by live + batch paths).

    ``ware_override`` forces the ware (and hence the id prefix) for books whose ware is a section
    that never appears on the page and repeats across sections (e.g. Hayes: ARS Form 8 vs Late
    Roman C Form 8) — the caller supplies it per page-range segment via ``--ware``."""
    ware = (ware_override or "").strip() or ef.ware.strip() or short_title
    ident = ef.form_id.strip()
    full_id = ident if ident.startswith(ware) else f"{ware} {ident}".strip()
    bbox = [ef.bbox.x0, ef.bbox.y0, ef.bbox.x1, ef.bbox.y1] if ef.bbox else None
    return FormRecord(
        id=full_id,
        ware=ware,
        vessel_class=normalize_vessel_class(ef.vessel_class),  # printed term → canonical English
        part_types=_to_part_types(ef.part_types),
        description=ef.description.strip(),
        origin=(ef.origin.strip() or None) if ef.origin else None,
        contents=(ef.contents.strip() or None) if ef.contents else None,
        date_start=ef.date_start,
        date_end=ef.date_end,
        archetype_ids=[a for a in ef.archetype_ids if a in _ARCH_IDS],
        cross_refs=[c.strip() for c in ef.cross_refs if c.strip()],
        source=SourcePointer(
            short_title=short_title,
            source_file=source_file,
            page_printed=printed,
            page_pdf=page_pdf,
            checksum=cs,
            figure_label=ef.figure_label,
            item_label=ef.item_label,
            bbox=bbox,
        ),
    )


def _window_record(
    ef: ExtractedForm, profile: SourceProfile, source_file: str, w: ClassWindow, cs: str
) -> FormRecord:
    """Map one class-window form to a ``FormRecord``, pointing the citation at the page that
    actually carries the drawing (resolved from ``bbox_image_index`` over the window's page list),
    so ``show``/``render_region`` crop the right page. Falls back to the header page."""
    idx = ef.bbox_image_index
    if ef.bbox is not None and idx is not None and 0 <= idx < len(w.pages_pdf):
        page_pdf = w.pages_pdf[idx]
    else:
        page_pdf = w.pages_pdf[0]
    printed = page_pdf - profile.page_offset
    return _to_record(ef, profile.short_title, source_file, printed, page_pdf, cs)


# A unit of extraction (a page, or a class window), tagged with a printed page and a resume key
# (the resolved PDF page for page layouts; the class number for class-window). The resume key is
# what the caller records in the .done sidecar and matches against ``skip_page_pdfs``.
PageResult = tuple[int, int, list[FormRecord]]


# --- resume progress (drop-resilience) -----------------------------------------------------
# Field deployments are low-bandwidth with connections that drop. We checkpoint after every page
# (see CatalogStore.merge) and record which PDF pages are done in a sidecar under the git-ignored
# index dir, so a re-run skips finished pages — including the empty/divider pages that yield no
# records — and only re-spends model calls on pages that never completed.

def progress_path(profile_slug: str, cs: str) -> Path:
    d = get_settings().index_path
    d.mkdir(parents=True, exist_ok=True)
    return d / f"ingest.{profile_slug}.{cs[:12]}.done"


def load_done_pages(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {int(ln) for ln in path.read_text().split() if ln.strip().isdigit()}


def mark_page_done(path: Path, page_pdf: int) -> None:
    """Append one finished PDF page, fsync'd, so progress survives an abrupt kill."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{page_pdf}\n")
        fh.flush()
        os.fsync(fh.fileno())


def extract_forms(
    pdf_path: Path,
    profile: SourceProfile,
    printed_pages: Iterable[int] | None = None,
    *,
    client: ModelClient | None = None,
    dpi: int | None = None,
    skip_page_pdfs: set[int] | None = None,
    ware_override: str | None = None,
) -> Iterator[PageResult]:
    """Read each requested printed page and yield ``(printed_page, page_pdf, records)`` as soon as
    that page is done — so the caller can checkpoint immediately (resilient to dropped connections).

    ``profile.page_offset`` converts a printed page to its 1-based PDF page (DICOCER: +2). Pages
    whose resolved PDF page is in ``skip_page_pdfs`` are not rendered or sent — that is how a re-run
    resumes an interrupted ingest without re-spending. A page that errors is skipped (not yielded),
    so the run continues and the page is retried on the next run (breadth).
    """
    if printed_pages is None:
        raise ValueError("printed_pages is required — pass a page range (no whole-book scan).")

    pdf_path = Path(pdf_path)
    client = client or get_model_client()
    dpi = dpi if dpi is not None else profile.dpi
    skip = skip_page_pdfs or set()
    cs = checksum(pdf_path)

    if profile.layout == "class-window":
        # One multi-image call per class; ``skip`` and the yielded key are class numbers, not pages.
        for w in class_windows(pdf_path, profile, list(printed_pages)):
            if w.key in skip:
                print(f"  class {w.key}: already done — skipping")
                continue
            imgs = [render_page(pdf_path, p, dpi=dpi) for p in w.pages_pdf]
            try:
                page_forms = client.parse(
                    build_prompt(profile, w.header_printed), PageForms, images=imgs
                )
            except Exception as e:  # one bad class must not abort the run (breadth)
                print(f"  ! class {w.key} (pp.pdf {w.pages_pdf}) failed: {type(e).__name__}: {e}")
                continue
            recs = [_window_record(ef, profile, pdf_path.name, w, cs) for ef in page_forms.forms]
            yield w.header_printed, w.key, recs
        return

    for printed in printed_pages:
        page_pdf = printed + profile.page_offset
        if page_pdf in skip:
            print(f"  page {printed} (pdf {page_pdf}): already done — skipping")
            continue
        img = render_page(pdf_path, page_pdf, dpi=dpi)
        try:
            page_forms = client.parse(
                build_prompt(profile, printed, ware=ware_override), PageForms, images=[img]
            )
        except Exception as e:  # one bad page must not abort the run (breadth)
            print(f"  ! page {printed} (pdf {page_pdf}) extraction failed: {type(e).__name__}: {e}")
            continue
        recs = [
            _to_record(
                ef, profile.short_title, pdf_path.name, printed, page_pdf, cs, ware_override
            )
            for ef in page_forms.forms
        ]
        yield printed, page_pdf, recs


def extract_forms_batch(
    pdf_path: Path,
    profile: SourceProfile,
    printed_pages: Iterable[int] | None = None,
    *,
    client: ModelClient | None = None,
    dpi: int | None = None,
    poll_seconds: int = 20,
    batch_size: int = 40,
    skip_page_pdfs: set[int] | None = None,
    ware_override: str | None = None,
) -> Iterator[PageResult]:
    """Same extraction as ``extract_forms`` but via the Batch API — ~50% cheaper, asynchronous.

    Pages are submitted in chunks of ``batch_size`` (each its own batch) to stay under the Batch
    API's 256 MB payload limit — essential for large/scanned books. Each chunk is polled to
    completion; results are yielded per page so the caller checkpoints after each chunk. Pages in
    ``skip_page_pdfs`` are not submitted (resume). Requires the Anthropic backend.
    """
    if printed_pages is None:
        raise ValueError("printed_pages is required — pass a page range (no whole-book scan).")

    from ..model.anthropic_client import AnthropicClient

    client = client or get_model_client()
    if not isinstance(client, AnthropicClient):
        raise RuntimeError(
            "Batch ingest requires the Anthropic backend (set IACCM_MODEL_PROVIDER=anthropic)."
        )
    dpi = dpi if dpi is not None else profile.dpi
    short_title = profile.short_title
    skip = skip_page_pdfs or set()
    sdk = client._client
    pdf_path = Path(pdf_path)
    cs = checksum(pdf_path)
    json_instr = json_schema_instruction(PageForms)

    if profile.layout == "class-window":
        windows = [
            w for w in class_windows(pdf_path, profile, list(printed_pages)) if w.key not in skip
        ]
        yield from _extract_windows_batch(
            sdk, client, pdf_path, profile, windows, cs, json_instr, poll_seconds, batch_size
        )
        return

    pages = [p for p in printed_pages if (p + profile.page_offset) not in skip]
    if not pages:
        return

    errored = 0
    nchunks = (len(pages) + batch_size - 1) // batch_size
    for ci in range(nchunks):
        chunk = pages[ci * batch_size : (ci + 1) * batch_size]
        requests: list[dict[str, Any]] = []
        page_by_id: dict[str, tuple[int, int]] = {}
        for printed in chunk:
            page_pdf = printed + profile.page_offset
            img = render_page(pdf_path, page_pdf, dpi=dpi)
            img_b64 = base64.standard_b64encode(img.read_bytes()).decode()
            cid = f"p{printed}"
            page_by_id[cid] = (printed, page_pdf)
            content = [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
                },
                {
                    "type": "text",
                    "text": build_prompt(profile, printed, ware=ware_override) + json_instr,
                },
            ]
            requests.append(
                {
                    "custom_id": cid,
                    "params": {
                        "model": client.model_name,
                        "max_tokens": 16000,
                        "thinking": {"type": "adaptive"},
                        "messages": [{"role": "user", "content": content}],
                    },
                }
            )
        print(
            f"chunk {ci + 1}/{nchunks}: submitting {len(requests)} page(s) "
            f"(pp. {chunk[0]}–{chunk[-1]}; ≈50% pricing)…"
        )
        batch = sdk.messages.batches.create(requests=requests)  # type: ignore[arg-type]
        print(f"  batch {batch.id} submitted; polling every {poll_seconds}s…")
        while sdk.messages.batches.retrieve(batch.id).processing_status != "ended":
            time.sleep(poll_seconds)
        for result in sdk.messages.batches.results(batch.id):
            printed, page_pdf = page_by_id.get(result.custom_id, (0, 0))
            if result.result.type != "succeeded":
                errored += 1
                continue
            text = "".join(b.text for b in result.result.message.content if b.type == "text")
            try:
                page_forms = parse_json_response(text, PageForms)
            except Exception:
                errored += 1
                continue
            recs = [
                _to_record(ef, short_title, pdf_path.name, printed, page_pdf, cs, ware_override)
                for ef in page_forms.forms
            ]
            yield printed, page_pdf, recs
        print(f"  chunk {ci + 1} done")

    if errored:
        print(f"  ! {errored} page request(s) errored or unparsable (will retry on next run)")


# The Batch API rejects any request over 256 MB. A class-window request carries a whole multi-page
# entry (1–9 page images), so we pack windows into chunks by estimated base64 payload, not by count.
# 180 MB leaves headroom under the hard cap for the JSON envelope + prompt text atop the images.
MAX_BATCH_B64_BYTES = 180 * 1024 * 1024


def _pack_windows_by_bytes(
    windows: list[ClassWindow], page_path: dict[int, Path], batch_size: int
) -> list[list[ClassWindow]]:
    """Greedily group windows so each chunk's estimated base64 image payload stays under the API
    cap. Estimate = rendered PNG size × 4/3 (base64 expansion). A new chunk starts when the next
    window would breach the byte budget or the count cap; a single oversized window still ships
    alone (one class's span is far under the cap)."""
    chunks: list[list[ClassWindow]] = []
    cur: list[ClassWindow] = []
    cur_bytes = 0
    for w in windows:
        wbytes = sum(page_path[p].stat().st_size * 4 // 3 for p in w.pages_pdf)
        if cur and (cur_bytes + wbytes > MAX_BATCH_B64_BYTES or len(cur) >= batch_size):
            chunks.append(cur)
            cur, cur_bytes = [], 0
        cur.append(w)
        cur_bytes += wbytes
    if cur:
        chunks.append(cur)
    return chunks


def _extract_windows_batch(
    sdk: Any,
    client: Any,
    pdf_path: Path,
    profile: SourceProfile,
    windows: list[ClassWindow],
    cs: str,
    json_instr: str,
    poll_seconds: int,
    batch_size: int,
) -> Iterator[PageResult]:
    """Batch-API path for class-window layouts: one request per class, each carrying the window's
    full multi-image span. ``custom_id`` is the class key so results map back to their window; the
    yielded resume key is the class number (parallel to the page path's PDF page)."""
    if not windows:
        return
    dpi = profile.dpi
    errored = 0
    # Render each needed page once (cached on disk, shared pages deduped), then pack windows into
    # byte-bounded chunks so no single batch request exceeds the API's 256 MB limit.
    page_path: dict[int, Path] = {}
    for w in windows:
        for p in w.pages_pdf:
            if p not in page_path:
                page_path[p] = render_page(pdf_path, p, dpi=dpi)
    chunks = _pack_windows_by_bytes(windows, page_path, batch_size)
    nchunks = len(chunks)

    for ci, chunk in enumerate(chunks):
        requests: list[dict[str, Any]] = []
        win_by_id: dict[str, ClassWindow] = {}
        chunk_bytes = 0
        for w in chunk:
            content: list[dict[str, Any]] = []
            for p in w.pages_pdf:
                img_b64 = base64.standard_b64encode(page_path[p].read_bytes()).decode()
                chunk_bytes += len(img_b64)
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
                    }
                )
            content.append(
                {"type": "text", "text": build_prompt(profile, w.header_printed) + json_instr}
            )
            cid = f"c{w.key}"
            win_by_id[cid] = w
            requests.append(
                {
                    "custom_id": cid,
                    "params": {
                        "model": client.model_name,
                        "max_tokens": 16000,
                        "thinking": {"type": "adaptive"},
                        "messages": [{"role": "user", "content": content}],
                    },
                }
            )
        mb = chunk_bytes // (1024 * 1024)
        print(
            f"chunk {ci + 1}/{nchunks}: submitting {len(requests)} class(es) "
            f"(Class {chunk[0].key}–{chunk[-1].key}; ~{mb} MB; ≈50% pricing)…"
        )
        batch = sdk.messages.batches.create(requests=requests)  # type: ignore[arg-type]
        print(f"  batch {batch.id} submitted; polling every {poll_seconds}s…")
        while sdk.messages.batches.retrieve(batch.id).processing_status != "ended":
            time.sleep(poll_seconds)
        for result in sdk.messages.batches.results(batch.id):
            win = win_by_id.get(result.custom_id)
            if win is None:
                continue
            if result.result.type != "succeeded":
                errored += 1
                continue
            text = "".join(b.text for b in result.result.message.content if b.type == "text")
            try:
                page_forms = parse_json_response(text, PageForms)
            except Exception:
                errored += 1
                continue
            recs = [_window_record(ef, profile, pdf_path.name, win, cs) for ef in page_forms.forms]
            yield win.header_printed, win.key, recs
        print(f"  chunk {ci + 1} done")

    if errored:
        print(f"  ! {errored} class request(s) errored or unparsable (will retry on next run)")
