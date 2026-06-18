"""Tests for vessel_class canonicalization (deterministic, no model calls)."""

from __future__ import annotations

import pytest

from iaccm.catalog.vessel_class import normalize_vessel_class as nz


@pytest.mark.parametrize(
    "raw,expected",
    [
        # French → English
        ("amphore", "amphora"),
        ("coupe", "cup"),
        ("assiette", "plate"),
        ("plat", "dish"),
        ("cruche", "jug"),
        ("couvercle", "lid"),
        ("amphore (petit modèle)", "amphora (small)"),
        # bord = rim sub-entry → interim 'amphora rim'
        ("bord", "amphora rim"),
        # casing
        ("Dish", "dish"),
        ("Bowl", "bowl"),
        ("Casserole", "casserole"),
        # bilingual dedup
        ("lid / couvercle", "lid"),
        # already clean → unchanged
        ("dish", "dish"),
        ("unknown", "unknown"),
        ("cup", "cup"),
        # modifier phrases: translated/lowercased, not reordered
        ("Flat-based dish", "flat-based dish"),
        ("Large dish with flat cut-out handles", "large dish with flat cut-out handles"),
        ("dish (with leaf decoration)", "dish (with leaf decoration)"),
        # blank
        ("", ""),
        ("  ", ""),
    ],
)
def test_known_mappings(raw: str, expected: str) -> None:
    assert nz(raw) == expected


@pytest.mark.parametrize(
    "variants,expected",
    [
        (["dish / bowl", "bowl / dish", "bowl/dish", "dish/bowl", "Dish/bowl"], "bowl/dish"),
        (["plate/dish", "dish / plate"], "dish/plate"),
        (["casserole / bowl"], "bowl/casserole"),
    ],
)
def test_compound_order_converges(variants: list[str], expected: str) -> None:
    for v in variants:
        assert nz(v) == expected, f"{v!r} did not canonicalize to {expected!r}"


@pytest.mark.parametrize(
    "raw",
    [
        "amphore",
        "bord",
        "dish / bowl",
        "lid / couvercle",
        "Large dish with flat cut-out handles",
        "amphore (petit modèle)",
        "unknown",
    ],
)
def test_idempotent(raw: str) -> None:
    once = nz(raw)
    assert nz(once) == once, f"not idempotent: {raw!r} → {once!r} → {nz(once)!r}"
