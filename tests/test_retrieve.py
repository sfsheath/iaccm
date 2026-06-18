"""Retrieval ordering must never violate the breadth invariant (CLAUDE.md rule 2):
ware/cross-ref boosts reorder candidates but never drop one."""

from __future__ import annotations

from iaccm.catalog.models import FormRecord, PartType, SourcePointer
from iaccm.catalog.store import CatalogStore
from iaccm.retrieve.search import Retriever


def _catalog(tmp_path) -> CatalogStore:
    store = CatalogStore(tmp_path / "catalog.jsonl")
    store.save(
        [
            FormRecord(
                id="ARS 8",
                ware="African Red Slip Ware",
                vessel_class="carinated bowl",
                part_types=[PartType.RIM, PartType.WALL],
                cross_refs=["Drag. 29", "Lamboglia 1"],
                source=SourcePointer(short_title="t", page_printed=1),
            ),
            FormRecord(
                id="ARS 9A",
                ware="African Red Slip Ware",
                vessel_class="bowl",
                part_types=[PartType.RIM],
            ),
            FormRecord(
                id="AMPH X",
                ware="Amphore italique",
                vessel_class="amphora",
                part_types=[PartType.RIM, PartType.TOE],
                cross_refs=["Dressel 1A"],
            ),
        ]
    )
    return store


def test_boost_orders_without_dropping(tmp_path) -> None:
    r = Retriever(_catalog(tmp_path))

    wares, xrefs = r.boost_terms("I think Drag-29, African Red Slip Ware")
    assert "African Red Slip Ware" in wares
    assert "Drag. 29" in xrefs
    assert "9" not in xrefs  # bare numeric cross-refs are not substring-matched

    ranked = r.all_candidates(prefer_wares=wares, cross_ref_terms=xrefs)
    # boost lifts the ware+cross_ref match to the top …
    assert ranked[0].form.id == "ARS 8"
    # … but nothing is dropped: every catalog form is still present (rule 2).
    assert {c.form.id for c in ranked} == {"ARS 8", "ARS 9A", "AMPH X"}


def test_part_breadth_holds_after_boost(tmp_path) -> None:
    r = Retriever(_catalog(tmp_path))
    wares, xrefs = r.boost_terms("African Red Slip Ware, Drag 29")
    rims = r.candidates_for_part(
        PartType.RIM, prefer_wares=wares, cross_ref_terms=xrefs
    )
    # Every RIM form across ALL wares (incl. the amphora) survives the boosted ordering.
    assert r.verify_breadth(rims, PartType.RIM)
    assert {c.form.id for c in rims} == {"ARS 8", "ARS 9A", "AMPH X"}
