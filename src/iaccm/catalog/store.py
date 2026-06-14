"""JSONL-backed catalog of FormRecords. Lives under ``index/`` (git-ignored vectors; the
catalog itself is facts and may be shared as part of an index bundle)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..config import get_settings
from .models import FormRecord, PartType


class CatalogStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else (get_settings().index_path / "catalog.jsonl")

    def __iter__(self) -> Iterator[FormRecord]:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield FormRecord.model_validate_json(line)

    def save(self, records: list[FormRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(r.model_dump_json() + "\n")

    def by_part(self, part: PartType) -> list[FormRecord]:
        """Breadth guarantee: every form of this part-type, across ALL wares.

        Do not add ware filtering here. Narrowing is the job of comparison downstream,
        never of dropping a ware before it has been seen (CLAUDE.md rule 2)."""
        return [r for r in self if part in r.part_types]
