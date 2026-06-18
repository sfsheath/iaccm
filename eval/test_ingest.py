"""Ingest-quality eval: does a profile actually pull complete records off real pages?

Distinct from eval/test_cases.py (which checks identification). These run the live extraction over a
real source PDF and assert the resulting records are STRUCTURALLY complete — the right id, the
fields a fiche promises populated, the published concordances present, a drawing located. Structural
(not exact-string) because the model is nondeterministic.

Opt-in and self-skipping: marked ``ingest`` (deselected by default — run ``pytest -m ingest``), and
skipped entirely if the source PDF is absent (it is git-ignored under the copyright firewall) or the
model backend is unconfigured. So a normal ``pytest`` / CI run never spends a model call here.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

GOLDENS = sorted((Path(__file__).parent / "ingest").glob("*.yaml"))


def _flatten_cases() -> list[tuple[str, dict, dict]]:
    out: list[tuple[str, dict, dict]] = []
    for gf in GOLDENS:
        spec = yaml.safe_load(gf.read_text(encoding="utf-8"))
        for case in spec.get("cases", []):
            out.append((f"{spec['source']}-{case['class']}", spec, case))
    return out


CASES = _flatten_cases()


@pytest.mark.ingest
@pytest.mark.parametrize("label,spec,case", CASES, ids=[c[0] for c in CASES])
def test_class_window_record_is_complete(label: str, spec: dict, case: dict) -> None:
    from iaccm.config import get_settings
    from iaccm.ingest.pdf import extract_forms
    from iaccm.ingest.profiles import get_profile

    pdf = get_settings().corpus_path / spec["pdf"]
    if not pdf.exists():
        pytest.skip(f"{spec['pdf']} not in corpus (git-ignored source)")
    if os.environ.get("IACCM_MODEL_PROVIDER", "anthropic") == "anthropic" and not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("IACCM_MODEL_API_KEY")
    ):
        pytest.skip("no model API key configured")

    profile = get_profile(spec["source"])
    pages = _parse_pages(case["scan_pages"])
    records = [r for _, _, recs in extract_forms(pdf, profile, printed_pages=pages) for r in recs]

    target = case["form_id"]
    rec = next((r for r in records if r.id.endswith(target)), None)
    assert rec is not None, f"no record for {target!r}; got {[r.id for r in records]}"

    for field in case.get("require_nonempty", []):
        assert getattr(rec, field), f"{target}: expected non-empty {field}"
    if case.get("require_dates"):
        assert rec.date_start is not None and rec.date_end is not None, f"{target}: dates missing"
    wanted = case.get("cross_refs_any", [])
    if wanted:
        blob = " | ".join(rec.cross_refs)
        assert any(w in blob for w in wanted), (
            f"{target}: none of {wanted} in cross_refs {rec.cross_refs}"
        )
    if case.get("require_bbox"):
        assert rec.source and rec.source.bbox, f"{target}: expected a located drawing (bbox)"


def _parse_pages(spec: str) -> list[int]:
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
