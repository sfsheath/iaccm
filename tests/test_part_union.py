"""Part-bounded retrieval for the dialogue loop: narrowing by the observed part(s) must preserve
the breadth invariant (CLAUDE.md rule 2) — full set within the part(s), deduped, never a ware
dropped — and scaling may omit only by visible rank, never hide a ware."""

from __future__ import annotations

from iaccm.agent.identify import _CANDIDATE_CAP, _cap, _to_part_types
from iaccm.catalog.models import FormRecord, PartType
from iaccm.catalog.store import CatalogStore
from iaccm.retrieve.search import Retriever


def _catalog(tmp_path) -> CatalogStore:
    store = CatalogStore(tmp_path / "catalog.jsonl")
    store.save(
        [
            FormRecord(id="ARS 8", ware="African Red Slip Ware", vessel_class="bowl",
                       part_types=[PartType.RIM, PartType.WALL]),
            FormRecord(id="AMPH AFR", ware="Amphore africaine", vessel_class="amphora",
                       part_types=[PartType.RIM, PartType.TOE, PartType.WALL],
                       cross_refs=["Africano piccolo"]),
            FormRecord(id="AMPH GRC", ware="Amphore grecque", vessel_class="amphora",
                       part_types=[PartType.RIM, PartType.TOE]),
            FormRecord(id="LID 1", ware="CLAIR-C", vessel_class="lid", part_types=[PartType.LID]),
        ]
    )
    return store


def test_single_part_is_full_set_and_subset_of_all(tmp_path) -> None:
    r = Retriever(_catalog(tmp_path))
    toes = r.candidates_for_parts([PartType.TOE])
    ids = {c.form.id for c in toes}
    assert ids == {"AMPH AFR", "AMPH GRC"}  # every toe form, both wares
    assert r.verify_breadth(toes, PartType.TOE)
    # bounded by the part, so a strict subset of the whole catalogue
    assert ids < {c.form.id for c in r.all_candidates()}


def test_multi_part_union_dedupes_and_keeps_breadth(tmp_path) -> None:
    r = Retriever(_catalog(tmp_path))
    union = r.candidates_for_parts([PartType.RIM, PartType.WALL])
    ids = [c.form.id for c in union]
    assert sorted(ids) == ["AMPH AFR", "AMPH GRC", "ARS 8"]  # LID 1 excluded (no rim/wall)
    assert len(ids) == len(set(ids))  # ARS 8 + AMPH AFR carry both parts — appear once, not twice
    assert r.verify_breadth(union, PartType.RIM)
    assert r.verify_breadth(union, PartType.WALL)


def test_boost_lifts_african_toe_above_greek(tmp_path) -> None:
    r = Retriever(_catalog(tmp_path))
    wares, xrefs = r.boost_terms("African amphora, Africano piccolo")
    toes = r.candidates_for_parts([PartType.TOE], prefer_wares=wares, cross_ref_terms=xrefs)
    assert [c.form.id for c in toes][0] == "AMPH AFR"  # African ranks above Greek
    assert r.verify_breadth(toes, PartType.TOE)  # …without dropping the Greek one


def test_unknown_resolution() -> None:
    # The model saying nothing, or "unknown", both collapse to [UNKNOWN] → loop falls back to
    # the (scaled) whole catalogue rather than a wrong part-bound.
    assert _to_part_types([]) == [PartType.UNKNOWN]
    assert _to_part_types(["unknown"]) == [PartType.UNKNOWN]
    assert _to_part_types(["Toe", "wall"]) == [PartType.TOE, PartType.WALL]  # case-insensitive


def test_cap_by_visible_rank() -> None:
    assert _cap(50, show_all=False) == 50  # under the cap → show all
    assert _cap(1000, show_all=False) == _CANDIDATE_CAP  # over → trimmed to the cap
    assert _cap(1000, show_all=True) == 1000  # widened → show everything
    assert _CANDIDATE_CAP >= 109  # must show a full amphora-toe set (109) without trimming
