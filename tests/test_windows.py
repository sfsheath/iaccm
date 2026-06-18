"""Class-window scanner tests.

Two layers: a fast pure test of the rule-2 contiguity guard (no PDF), and a corpus-gated integration
test that runs the real scanner over Peacock & Williams 1991 IF the user has the PDF. The PDF is
git-ignored (copyright firewall), so the integration test self-skips in CI / on a fresh clone.
"""

from __future__ import annotations

import pytest

from iaccm.config import get_settings
from iaccm.ingest.profiles import get_profile
from iaccm.ingest.windows import _assert_contiguous, class_windows

PEACOCK_PDF = "PeacockDWilliamsD1991-AmphoraeRomanEconomy.pdf"


def test_contiguity_guard_accepts_unbroken_runs() -> None:
    _assert_contiguous([1, 2, 3, 4, 5], "x")  # from 1
    _assert_contiguous([3, 4, 5, 6], "x")  # a sub-range (pilot scan) is fine
    _assert_contiguous([42], "x")  # a single class


def test_contiguity_guard_rejects_gaps_and_empties() -> None:
    with pytest.raises(ValueError, match="missing"):
        _assert_contiguous([3, 4, 6], "book.pdf")  # a fused/undetected Class 5
    with pytest.raises(ValueError):
        _assert_contiguous([], "book.pdf")


def _peacock_pdf_or_skip():
    path = get_settings().corpus_path / PEACOCK_PDF
    if not path.exists():
        pytest.skip(f"{PEACOCK_PDF} not in corpus (git-ignored source) — integration test skipped")
    return path


def test_peacock_yields_55_contiguous_class_windows() -> None:
    pdf = _peacock_pdf_or_skip()
    profile = get_profile("peacock-1991")
    windows = class_windows(pdf, profile, range(82, 212))  # the full catalogue, Classes 1–55
    keys = [w.key for w in windows]
    assert keys == list(range(1, 56)), f"expected Classes 1–55 contiguous, got {keys}"
    for w in windows:
        assert w.pages_pdf, f"Class {w.key} has an empty page span"
        assert w.pages_pdf == sorted(w.pages_pdf), f"Class {w.key} pages not in order"
        assert w.pages_pdf[0] == w.header_printed + profile.page_offset  # header page is first
