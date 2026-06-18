"""Hybrid candidate retrieval: structured filter + (TODO) vector similarity + archetype funnel.

HARD RULE (CLAUDE.md rule 2): never prune a ware on a lossy signal. ``candidates_for_part``
returns the FULL set for a part-type across all wares; ranking may reorder, never drop, before
the model has compared them.

Breadth is bounded ONLY by a directly-observable part-type (``by_part``) — never by an inferred
family/ware. Ware, cross-reference, and archetype are **ordering boosts**, never membership
filters: a model triage of "this is terra sigillata" must never remove a candidate before the
model has compared it (that is the founding bug in a scaling costume). ``verify_breadth`` guards it.
"""

from __future__ import annotations

import re

from ..catalog.models import Candidate, FormRecord, PartType
from ..catalog.store import CatalogStore

# Boost weights (relative ordering only — never a threshold that drops anything).
_W_ARCHETYPE = 1.0  # per shared gross-shape archetype
_W_CROSS_REF = 2.0  # per shared cross-reference the conversation named (e.g. "Drag. 29")
_W_WARE = 3.0  # the conversation named this exact ware/family


def _norm(s: str) -> str:
    """Lowercase, punctuation→space, collapse — so 'Drag-29' and 'Drag. 29' compare equal."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _matchable(term: str) -> bool:
    """A boost term safe to substring-match: ≥3 chars with a letter. Excludes bare numbers like
    a cross-ref of just '9' (which would spuriously match inside 'Drag 29')."""
    return len(term) >= 3 and any(c.isalpha() for c in term)


class Retriever:
    def __init__(self, catalog: CatalogStore | None = None) -> None:
        self.catalog = catalog or CatalogStore()

    def candidates_for_part(
        self,
        part: PartType,
        archetype_ids: list[str] | None = None,
        prefer_wares: list[str] | None = None,
        cross_ref_terms: list[str] | None = None,
    ) -> list[Candidate]:
        """Full candidate set for a part-type across all wares, ordered by the boost signals."""
        return self._rank(self.catalog.by_part(part), archetype_ids, prefer_wares, cross_ref_terms)

    def candidates_for_parts(
        self,
        parts: list[PartType],
        archetype_ids: list[str] | None = None,
        prefer_wares: list[str] | None = None,
        cross_ref_terms: list[str] | None = None,
    ) -> list[Candidate]:
        """Full candidate set for a UNION of observed part-types, deduped by id, ordered by boosts.

        A sherd may show more than one diagnostic part (e.g. rim + wall); breadth is bounded only by
        those observed parts (rule 2), never by an inferred ware. The forms are unioned FIRST, then
        ranked in a single pass — ranking the union (not merging per-part rankings) keeps a shared
        form's score correct and the ordering total."""
        seen: dict[str, FormRecord] = {}
        for p in parts:
            for f in self.catalog.by_part(p):
                seen.setdefault(f.id, f)
        return self._rank(list(seen.values()), archetype_ids, prefer_wares, cross_ref_terms)

    def all_candidates(
        self,
        archetype_ids: list[str] | None = None,
        prefer_wares: list[str] | None = None,
        cross_ref_terms: list[str] | None = None,
    ) -> list[Candidate]:
        """The full catalog as a breadth set, ordered by the boost signals. Used when the part-type
        is not yet known — the model still compares within the whole set, never recalling a form."""
        return self._rank(list(self.catalog), archetype_ids, prefer_wares, cross_ref_terms)

    def boost_terms(self, text: str) -> tuple[list[str], list[str]]:
        """Find which catalogue wares and cross-references the conversation actually mentions, so
        we can lift them in the ordering. Grounded in the catalogue's own vocabulary (not brittle
        regex), so it extends automatically as typologies are added. Returns ``(wares, xrefs)``.
        """
        t = _norm(text)
        if not t:
            return [], []
        wares: set[str] = set()
        xrefs: set[str] = set()
        for f in self.catalog:
            nw = _norm(f.ware)
            if _matchable(nw) and nw in t:
                wares.add(f.ware)
            for x in f.cross_refs:
                nx = _norm(x)
                if _matchable(nx) and nx in t:
                    xrefs.add(x)
        return sorted(wares), sorted(xrefs)

    def _rank(
        self,
        forms: list[FormRecord],
        archetype_ids: list[str] | None,
        prefer_wares: list[str] | None = None,
        cross_ref_terms: list[str] | None = None,
    ) -> list[Candidate]:
        """Order by gross-shape + ware/cross-ref overlap; ordering only — never drops a form."""
        wanted = set(archetype_ids or [])
        pref = {_norm(w) for w in (prefer_wares or [])}
        xref = {_norm(x) for x in (cross_ref_terms or [])}
        out: list[Candidate] = []
        for f in forms:
            arch_hits = wanted & set(f.archetype_ids)
            ware_hit = _norm(f.ware) in pref if pref else False
            xref_hits = [x for x in f.cross_refs if _norm(x) in xref] if xref else []
            score = (
                _W_ARCHETYPE * len(arch_hits)
                + _W_WARE * (1 if ware_hit else 0)
                + _W_CROSS_REF * len(xref_hits)
            )
            reasons = []
            if ware_hit:
                reasons.append(f"ware «{f.ware}»")
            if xref_hits:
                reasons.append("xref " + ", ".join(xref_hits))
            if arch_hits:
                reasons.append("shape " + ", ".join(sorted(arch_hits)))
            out.append(
                Candidate(form=f, score=score, why="; ".join(reasons) or "in candidate set")
            )
        out.sort(key=lambda c: c.score, reverse=True)
        return out

    def verify_breadth(self, candidates: list[Candidate], part: PartType) -> bool:
        """Guard: the candidate set must equal the full catalog set for this part-type."""
        full = {f.id for f in self.catalog.by_part(part)}
        seen = {c.form.id for c in candidates}
        return full.issubset(seen)
