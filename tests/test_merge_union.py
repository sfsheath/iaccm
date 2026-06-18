"""Field-union merge: a form catalogued across pages (text entry + figure drawing) must combine into
one complete record — neither half clobbering the other — and stay idempotent (CLAUDE.md rule 2)."""

from __future__ import annotations

from iaccm.catalog.models import FormRecord, PartType, SourcePointer
from iaccm.catalog.store import CatalogStore


def _text() -> FormRecord:
    return FormRecord(
        id="African Red Slip Ware Form 50",
        ware="African Red Slip Ware",
        vessel_class="dish",
        part_types=[PartType.RIM, PartType.WALL],
        description="Large flat-floored dish with a plain rounded rim and low ring foot.",
        date_start=230,
        date_end=400,
        cross_refs=["Lamboglia 40", "Salomonson A"],
        archetype_ids=["O-DISH-FLARED"],
        source=SourcePointer(short_title="Hayes 1972", page_printed=70, page_pdf=96, bbox=None),
    )


def _figure() -> FormRecord:
    # same form, its drawing on a figure plate: carries the bbox + a shape-read part, no prose
    return FormRecord(
        id="African Red Slip Ware Form 50",
        ware="African Red Slip Ware",
        vessel_class="",
        part_types=[PartType.BASE, PartType.FOOT],
        description="",
        cross_refs=["Atlante XXX"],
        archetype_ids=["O-DISH-FLARED"],
        source=SourcePointer(short_title="Hayes 1972", page_printed=199, page_pdf=200,
                             bbox=[0.1, 0.2, 0.4, 0.5]),
    )


def test_union_combines_text_and_figure() -> None:
    u = _text().union(_figure())
    assert u.description.startswith("Large flat-floored")        # rich text kept
    assert u.date_start == 230 and u.date_end == 400             # dates from text
    assert u.source and u.source.bbox == [0.1, 0.2, 0.4, 0.5]    # drawing geometry kept
    assert set(u.part_types) == {PartType.RIM, PartType.WALL, PartType.BASE, PartType.FOOT}
    assert u.cross_refs == ["Lamboglia 40", "Salomonson A", "Atlante XXX"]  # union, order-stable
    assert u.archetype_ids == ["O-DISH-FLARED"]                  # deduped


def test_union_is_order_independent_and_idempotent() -> None:
    a, b = _text(), _figure()
    ab, ba = a.union(b), b.union(a)
    # the fields that matter converge regardless of order
    for f in ("date_start", "date_end"):
        assert getattr(ab, f) == getattr(ba, f)
    assert (ab.source.bbox is not None) and (ba.source.bbox is not None)
    assert set(ab.part_types) == set(ba.part_types)
    assert a.union(a).model_dump() == a.model_dump()            # idempotent


def test_store_merge_unions_not_replaces(tmp_path) -> None:
    store = CatalogStore(tmp_path / "catalog.jsonl")
    store.merge([_text()])           # text page ingested first (no bbox)
    store.merge([_figure()])         # figure page later — must NOT clobber the description
    recs = list(store)
    assert len(recs) == 1
    r = recs[0]
    assert r.description.startswith("Large flat-floored")   # description survived
    assert r.source and r.source.bbox is not None           # and the drawing attached
    store.merge([_figure()])         # idempotent re-ingest
    assert len(list(store)) == 1
