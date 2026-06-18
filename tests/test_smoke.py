"""Smoke tests: the package imports cheaply (no heavy deps) and the core data is sane."""

from __future__ import annotations

from pathlib import Path


def test_package_imports() -> None:
    import iaccm

    assert iaccm.__version__


def test_archetype_vocabulary() -> None:
    from iaccm.catalog import ARCHETYPES, ARCHETYPES_BY_ID

    assert len(ARCHETYPES) == 27  # 20 base + 7 whole-amphora bodies (Sciallano entries)
    ids = [a.id for a in ARCHETYPES]
    assert len(ids) == len(set(ids)), "archetype ids must be unique"
    assert "L-CONE-KNOB" in ARCHETYPES_BY_ID  # the lid archetype for the seed case
    assert "A-OVOID" in ARCHETYPES_BY_ID  # whole-amphora body archetype
    assert all(a.svg for a in ARCHETYPES), "every archetype needs a silhouette"


def test_models_instantiate() -> None:
    from iaccm.catalog import FormRecord, PartType, SourcePointer

    rec = FormRecord(
        id="CLAIR-C Dn9.11",
        ware="CLAIR-C",
        vessel_class="lid",
        part_types=[PartType.LID],
        attributes={"rim": "everted/raised"},
        date_start=450,
        date_end=520,
        source=SourcePointer(short_title="DICOCER (Lattara 6)", page_printed=188),
    )
    assert rec.part_types == [PartType.LID]


def test_paths_are_relative_to_root_not_hardcoded() -> None:
    from iaccm.config import Settings

    s = Settings(root=Path("/tmp/somewhere_else"))
    assert s.corpus_path == Path("/tmp/somewhere_else/corpus")
    assert s.index_path == Path("/tmp/somewhere_else/index")
