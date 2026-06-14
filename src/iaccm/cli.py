"""Command-line entry points: ``iaccm ingest``, ``iaccm ui``, ``iaccm id``."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Identification of Archaeological Ceramics in the Central Mediterranean")


@app.command()
def ingest(pdf: Path, short_title: str = "DICOCER (Lattara 6)", page_offset: int = 2) -> None:
    """Build/refresh the local index from a typology PDF in corpus/."""
    from .catalog.store import CatalogStore
    from .ingest.pdf import checksum, extract_forms

    typer.echo(f"checksum: {checksum(pdf)}")
    records = list(extract_forms(pdf, short_title=short_title, page_offset=page_offset))
    CatalogStore().save(records)
    typer.echo(f"saved {len(records)} form records")


@app.command()
def ui(host: str = "127.0.0.1", port: int = 7860) -> None:
    """Launch the Gradio workbench."""
    from .ui.app import launch

    launch(server_name=host, server_port=port)


@app.command(name="id")
def identify(image: list[Path] = typer.Argument(...)) -> None:
    """Identify a sherd from one or more photos (headless dialog)."""
    from .agent.graph import build_graph

    graph = build_graph()
    state = graph.invoke({"images": list(image)})
    typer.echo(state.get("result"))


if __name__ == "__main__":
    app()
