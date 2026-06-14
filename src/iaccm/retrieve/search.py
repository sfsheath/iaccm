"""Hybrid candidate retrieval: structured filter + (TODO) vector similarity + archetype funnel.

HARD RULE (CLAUDE.md rule 2): never prune a ware on a lossy signal. ``candidates_for_part``
returns the FULL set for a part-type across all wares; ranking may reorder, never drop, before
the model has compared them.
"""

from __future__ import annotations

from ..catalog.models import Candidate, PartType
from ..catalog.store import CatalogStore


class Retriever:
    def __init__(self, catalog: CatalogStore | None = None) -> None:
        self.catalog = catalog or CatalogStore()

    def candidates_for_part(
        self, part: PartType, archetype_ids: list[str] | None = None
    ) -> list[Candidate]:
        """Full candidate set for a part-type. Archetype ids (if given) reorder by gross-shape
        match; they must not remove forms from the set."""
        forms = self.catalog.by_part(part)
        candidates = [
            Candidate(form=f, score=0.0, why="structural part match") for f in forms
        ]
        # TODO: boost score where archetype_ids intersect f.archetype_ids; add vector
        # similarity over descriptions. Do NOT filter wares out here.
        return candidates

    def verify_breadth(self, candidates: list[Candidate], part: PartType) -> bool:
        """Guard: the candidate set must equal the full catalog set for this part-type."""
        full = {f.id for f in self.catalog.by_part(part)}
        seen = {c.form.id for c in candidates}
        return full.issubset(seen)
