"""Guidance loads incrementally: method/principles always; a category's diagnostic key only once
the sherd has triaged to it (never all keys at once — that would bias unrelated sherds)."""

from __future__ import annotations

from iaccm.agent.guidance import (
    available_categories,
    load_category,
    load_method,
    normalize_category,
)


def test_method_always_has_triage_key() -> None:
    assert "Triage key" in load_method()


def test_category_keys_resolve() -> None:
    assert set(available_categories()) >= {"fineware", "coarseware", "amphora", "lamp"}
    assert load_category("amphora")  # non-empty
    assert load_category("nonsense") == ""


def test_normalize_category_variants() -> None:
    assert normalize_category("Fine ware") == "fineware"
    assert normalize_category("amphorae") == "amphora"
    assert normalize_category("cooking ware") == "coarseware"
    assert normalize_category("lamps") == "lamp"
    assert normalize_category("not a category") is None


def test_category_key_loads_only_after_triage() -> None:
    from iaccm.agent.identify import Identifier, RankResult, TriageResult

    triage_prompts: list[str] = []
    rank_prompts: list[str] = []

    class Stub:
        model_name = "stub"

        def parse(self, prompt: str, schema, **kw):  # type: ignore[no-untyped-def]
            if schema is TriageResult:
                triage_prompts.append(prompt)
                return TriageResult(category="fine ware", observed_parts=["rim"])
            rank_prompts.append(prompt)
            return RankResult()

        def generate(self, *a, **k):  # type: ignore[no-untyped-def]
            return ""

    idf = Identifier(client=Stub())
    idf.step("a glossy red bowl sherd")  # turn 1
    assert idf.category == "fineware"
    # The TRIAGE call carried NO category key — nothing had triaged yet (the principle under test).
    assert "DIAGNOSTIC KEY — category 'fineware'" not in triage_prompts[0]
    assert "Triage key" in triage_prompts[0]  # method/triage key is always present
    # The RANK call of the SAME turn already uses the freshly-triaged fineware key.
    assert "DIAGNOSTIC KEY — category 'fineware'" in rank_prompts[0]
    assert "METHOD & PRINCIPLES" in rank_prompts[0]

    idf.step("more detail")  # turn 2: category persisted, so even triage now carries the key
    assert "DIAGNOSTIC KEY — category 'fineware'" in triage_prompts[1]
