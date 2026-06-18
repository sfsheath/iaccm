"""JSONL-backed catalog of FormRecords — the shareable derived product.

Lives under ``bundle/`` and is committed/distributable: it holds only facts (our own paraphrased
descriptions, dates, part types, archetype tags, printed-page pointers, normalized bboxes, cross-
references) — never copyrighted plate images or verbatim book text. A recipient drops in their own
copy of the source PDFs and the pointers resolve against it (docs/copyright.md)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from ..config import get_settings
from .models import FormRecord, PartType


class CatalogStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else (get_settings().bundle_path / "catalog.jsonl")

    def __iter__(self) -> Iterator[FormRecord]:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield FormRecord.model_validate_json(line)

    def save(self, records: list[FormRecord]) -> None:
        """Write the catalog atomically: a full write to a temp file, then an atomic rename.

        Atomicity matters for the field deployment (low bandwidth, connections that drop mid-write):
        a killed process can never leave a half-written or truncated ``catalog.jsonl`` — the old
        file stays intact until the new one is complete."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(r.model_dump_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(self.path)  # atomic on the same filesystem

    def upsert(self, records: list[FormRecord]) -> int:
        """Merge ``records`` into the catalog by form id (so ingesting another ware/typology does
        not clobber earlier ones). Returns the total record count after the merge."""
        merged = {r.id: r for r in self}
        for r in records:
            merged[r.id] = r
        self.save(list(merged.values()))
        return len(merged)

    def merge(self, records: list[FormRecord]) -> int:
        """Incremental upsert used to checkpoint one page at a time during ingest.

        On an id collision the two records are FIELD-UNIONed (``FormRecord.union``): a form
        catalogued across pages — its text entry (description, dates, cross-refs) on one page and
        its figure drawing (bbox, shape) on another — combines into one complete record instead of
        either clobbering the other. The union keeps the bbox-bearing source, so a drawing is never
        lost (CLAUDE.md rule 2: breadth/quality). Idempotent, and because it persists per page it
        survives an interrupted run. Returns the total record count."""
        merged = {r.id: r for r in self}
        for r in records:
            prior = merged.get(r.id)
            merged[r.id] = prior.union(r) if prior is not None else r
        self.save(list(merged.values()))
        return len(merged)

    def by_part(self, part: PartType) -> list[FormRecord]:
        """Breadth guarantee: every form of this part-type, across ALL wares.

        Do not add ware filtering here. Narrowing is the job of comparison downstream,
        never of dropping a ware before it has been seen (CLAUDE.md rule 2)."""
        return [r for r in self if part in r.part_types]
