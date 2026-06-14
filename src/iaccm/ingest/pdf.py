"""PDF ingest. Render pages, (optionally) OCR, and extract one structured FormRecord per
published form.

IMPORTANT (CLAUDE.md rule 2): extraction must be **visual-first**. Render every plate page and
read it; never decide a ware "has no form of type X" from the text layer alone — a wrapped or
mis-OCR'd line will silently drop the right candidate. The founding bug lived exactly here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from ..catalog.models import FormRecord


def checksum(pdf_path: Path) -> str:
    """Content hash that binds a shared index bundle to the user's own local PDF."""
    h = hashlib.sha256()
    with Path(pdf_path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_page(pdf_path: Path, page_pdf: int, dpi: int = 200) -> Path:
    """Render a single PDF page to a transient PNG (git-ignored cache). Returns its path.

    Rendered plate images are derived from copyrighted source and must never be committed
    or exported (docs/copyright.md)."""
    import fitz  # PyMuPDF, lazy import

    raise NotImplementedError(
        "TODO: render page with fitz to a *.plate.png under the ignored cache dir"
    )


def extract_forms(pdf_path: Path, short_title: str, page_offset: int = 0) -> Iterator[FormRecord]:
    """Yield one FormRecord per published form.

    Suggested pipeline: render each plate page -> detect form entries (layout/VLM) ->
    structured fields (id, ware, vessel_class, attributes, date range, source page) ->
    classify into PartType + archetype_ids. Verify completeness by counting forms per ware
    against the book's own numbering before trusting the catalog."""
    raise NotImplementedError("TODO: implement visual-first structured extraction")
