"""Command-line entry points: ``iaccm ingest``, ``iaccm show``, ``iaccm ui``, ``iaccm id``."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Identification of Archaeological Ceramics in the Central Mediterranean")

# Shared model-provider overrides (keys live in .env per provider, e.g. ANTHROPIC_API_KEY /
# FEATHERLESS_API_KEY). Reused across commands so provider choice is a per-run CLI flag.
_PROVIDER_OPT = typer.Option(
    None, "--provider",
    help="Model provider for this run: anthropic | featherless | ollama | openai (default .env).",
)
_MODEL_OPT = typer.Option(None, "--model", help="Model name override for this run.")


def _parse_pages(spec: str) -> list[int]:
    """Parse a printed-page spec like '185-189' or '185,187,190' or '185' into a list of ints."""
    pages: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            pages.extend(range(int(lo), int(hi) + 1))
        else:
            pages.append(int(part))
    return pages


@app.command()
def ingest(
    pdf: Path,
    pages: str = typer.Option(
        ...,
        "--pages",
        help="Printed page range, e.g. '185-189'. For class-window sources (e.g. peacock-1991) "
        "this is the range SCANNED for class headers; each class found is ingested as one window.",
    ),
    source: str = typer.Option(
        "dicocer", "--source", help="Profile slug: 'dicocer' | 'sciallano-1994' | 'peacock-1991'."
    ),
    ware: str | None = typer.Option(
        None,
        "--ware",
        help="Force this ware onto every form in the range — for section-organized books whose "
        'ware is not printed on the page (e.g. hayes-1972: --ware "African Red Slip Ware").',
    ),
    page_offset: int | None = typer.Option(None, help="Override the profile's printed→PDF offset."),
    dpi: int | None = typer.Option(None, help="Override the profile's render DPI."),
    batch: bool = typer.Option(False, "--batch", help="Use the Batch API (~50% cheaper; async)."),
    resume: bool = typer.Option(
        True, help="Skip pages already done in a prior run; --no-resume redoes the whole range."
    ),
    provider: str | None = _PROVIDER_OPT,
    model: str | None = _MODEL_OPT,
) -> None:
    """Read a page range of a typology PDF into the catalog (one record per form).

    The ``--source`` profile supplies the short title, page offset, DPI and the layout-specific
    extraction prompt. Adding a new typology is a profile entry, not a code change.

    Ingest is incremental and resumable: each page is saved to the catalog the moment it is read,
    and finished pages are recorded so an interrupted run (e.g. a dropped connection) picks up where
    it left off without re-spending — designed for low-bandwidth field use.
    """
    from .catalog.store import CatalogStore
    from .ingest.pdf import (
        checksum,
        extract_forms,
        extract_forms_batch,
        load_done_pages,
        mark_page_done,
        progress_path,
    )
    from .ingest.profiles import get_profile

    try:
        profile = get_profile(source)
    except KeyError as e:
        typer.echo(str(e))
        raise typer.Exit(1) from None
    if page_offset is not None:
        profile = profile.model_copy(update={"page_offset": page_offset})

    printed = _parse_pages(pages)
    cs = checksum(pdf)
    typer.echo(f"checksum: {cs}")
    prog = progress_path(profile.slug, cs)
    done = load_done_pages(prog) if resume else set()
    if done:
        typer.echo(f"resuming: {len(done)} page(s) already done — skipping them")
    typer.echo(f"reading {profile.short_title} pp.{printed[0]}–{printed[-1]} (source={source}) …")

    from .model import get_model_client
    from .model.anthropic_client import AnthropicClient

    client = get_model_client(provider=provider, model=model)
    typer.echo(f"model: {client.model_name} ({type(client).__name__})")
    if batch and not isinstance(client, AnthropicClient):
        typer.echo("note: the Batch API is Anthropic-only — using the live path for this provider.")
        batch = False

    store = CatalogStore()
    total = sum(1 for _ in store)
    new = 0
    gen = (
        extract_forms_batch(
            pdf, profile, printed_pages=printed, dpi=dpi, skip_page_pdfs=done,
            ware_override=ware, client=client,
        )
        if batch
        else extract_forms(
            pdf, profile, printed_pages=printed, dpi=dpi, skip_page_pdfs=done,
            ware_override=ware, client=client,
        )
    )
    for printed_page, page_pdf, recs in gen:
        if recs:
            total = store.merge(recs)  # checkpoint to disk (atomic) before marking the page done
            new += len(recs)
        mark_page_done(prog, page_pdf)
        typer.echo(f"  page {printed_page}: {len(recs)} form(s) [saved; catalog={total}]")
    typer.echo(f"done; {new} form(s) this run; catalog holds {total} → {store.path}")


@app.command()
def show(
    form_id: str,
    pdf: Path = typer.Option(None, help="Override source PDF (else resolved by checksum)."),
    dpi: int = 200,
) -> None:
    """Render a form's profile crop (or whole page) from its locator — proves the pointer."""
    from .catalog.store import CatalogStore
    from .ingest.pdf import find_source_pdf, render_region

    rec = next((r for r in CatalogStore() if r.id == form_id), None)
    if rec is None:
        typer.echo(f"no catalog record for {form_id!r}")
        raise typer.Exit(1)
    src = rec.source
    if src is None or src.page_pdf is None:
        typer.echo(f"{form_id!r} has no page pointer")
        raise typer.Exit(1)
    pdf_path = pdf or find_source_pdf(src.checksum, src.source_file)
    if pdf_path is None:
        typer.echo("could not resolve the source PDF (checksum not matched in corpus); pass --pdf")
        raise typer.Exit(1)
    out = render_region(pdf_path, src.page_pdf, src.bbox, dpi=dpi)
    kind = "crop" if src.bbox else "whole page"
    where = f"{src.figure_label or ''} {src.item_label or ''}".strip()
    typer.echo(f"{form_id}: rendered {kind} ({where or 'page ' + str(src.page_pdf)}) → {out}")


@app.command(name="forget-source")
def forget_source(
    source_file: str = typer.Argument(..., help="Exact source.source_file to drop (the PDF name)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the count without writing."),
) -> None:
    """Delete every record from one source PDF — use before re-ingesting a book whose prior ingest
    was wrong. Keys STRICTLY on ``source.source_file`` (so records of OTHER books that merely cite
    this one in their cross-refs are kept). Atomic write."""
    from .catalog.store import CatalogStore

    store = CatalogStore()
    records = list(store)
    drop = [r for r in records if r.source and r.source.source_file == source_file]
    keep = [r for r in records if not (r.source and r.source.source_file == source_file)]
    typer.echo(f"{len(records)} record(s); {len(drop)} from {source_file!r} would be dropped.")
    if dry_run:
        typer.echo("dry run — nothing written.")
        return
    if not drop:
        typer.echo("no matching records — nothing to write.")
        return
    store.save(keep)
    typer.echo(f"wrote {len(keep)} record(s) → {store.path}")


@app.command(name="normalize-catalog")
def normalize_catalog(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show the before→after changes without writing the catalog."
    ),
) -> None:
    """Canonicalize every record's ``vessel_class`` to English in place (idempotent).

    Cosmetic only — ``vessel_class`` is a display field, so ids, retrieval and source pointers stay
    untouched. Run ``--dry-run`` first to review the mapping. Do NOT run while an ingest is writing
    the catalog (both do a whole-file rewrite; concurrent runs can lose updates).
    """
    import collections

    from .catalog.store import CatalogStore
    from .catalog.vessel_class import normalize_vessel_class

    store = CatalogStore()
    records = list(store)
    changes: collections.Counter[tuple[str, str]] = collections.Counter()
    for r in records:
        new = normalize_vessel_class(r.vessel_class)
        if new != r.vessel_class:
            changes[(r.vessel_class, new)] += 1
        r.vessel_class = new

    n_changed = sum(changes.values())
    typer.echo(
        f"{len(records)} record(s); {n_changed} would change across {len(changes)} mapping(s):"
    )
    for (old, new), c in sorted(changes.items(), key=lambda x: -x[1]):
        typer.echo(f"  {c:4}  {old!r} → {new!r}")
    if dry_run:
        typer.echo("dry run — nothing written.")
        return
    if n_changed == 0:
        typer.echo("already canonical — nothing to write.")
        return
    store.save(records)
    typer.echo(f"wrote {len(records)} record(s) → {store.path}")


@app.command()
def ui(
    host: str = "127.0.0.1",
    port: int = 7860,
    public: bool = typer.Option(
        False, "--public", help="Expose a public gradio.live share link (anyone with the URL)."
    ),
    provider: str | None = _PROVIDER_OPT,
    model: str | None = _MODEL_OPT,
) -> None:
    """Launch the Gradio workbench. Local-only by default; --public creates a shareable link."""
    from .ui.app import launch

    if public:
        typer.echo(
            "⚠  --public: creating a temporary public gradio.live link. Anyone with the URL can "
            "use this workbench — and it sends your local plate images to the model API. "
            "Ctrl-C to stop."
        )
    launch(provider=provider, model=model, server_name=host, server_port=port, share=public)


@app.command(name="id")
def identify(
    notes: str = typer.Argument(..., help="What you know, in free text."),
    image: list[Path] = typer.Option(None, "--image", help="Sherd photo / drawing (repeatable)."),
    show_all: bool = typer.Option(
        False, "--all", help="Show every candidate for the observed part (no top-N cap)."
    ),
    provider: str | None = _PROVIDER_OPT,
    model: str | None = _MODEL_OPT,
) -> None:
    """Run one identification turn headlessly and print the ranked candidates + question.

    The turn triages the photo to its diagnostic part, retrieves the full candidate set for that
    part (never narrowed by an inferred ware), then ranks within it — so even this single-shot call
    narrows instead of ranking the whole catalogue.
    """
    from .agent.identify import Identifier
    from .model import get_model_client

    client = get_model_client(provider=provider, model=model) if (provider or model) else None
    result = Identifier(client=client).step(
        notes, images=list(image) if image else None, show_all=show_all
    )
    typer.echo(result.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
