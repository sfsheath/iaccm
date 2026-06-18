"""Regression cases. Each YAML in eval/cases/ encodes a real identification the system must
reproduce. Structural checks run now; the live end-to-end assertion is xfail until the pipeline
is implemented.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CASES_DIR = Path(__file__).parent / "cases"
CASE_FILES = sorted(CASES_DIR.glob("*.yaml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.stem)
def test_case_is_well_formed(case_file: Path) -> None:
    case = _load(case_file)
    for key in ("id", "images", "intake", "expected", "must_include_candidates"):
        assert key in case, f"{case_file.name} missing '{key}'"
    assert case["expected"].get("form_id"), "expected.form_id required"
    # The expected answer must itself be one of the candidates that retrieval must surface.
    assert case["expected"]["form_id"] in case["must_include_candidates"]


@pytest.mark.xfail(reason="end-to-end ID needs a live model + fixture images", strict=False)
@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.stem)
def test_case_resolves_end_to_end(case_file: Path) -> None:
    case = _load(case_file)
    from iaccm.agent.identify import Identifier  # noqa: F401

    pytest.skip(
        "wire Identifier().step(case['intake'], images=…) and assert the in-family conclusion is "
        f"{case['expected']['form_id']!r}"
    )
