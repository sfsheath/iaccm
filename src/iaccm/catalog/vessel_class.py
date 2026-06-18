"""Canonicalize ``FormRecord.vessel_class`` to a consistent English vocabulary.

``vessel_class`` is a DISPLAY field (it appears in the agent's candidate list); it is not part of an
``id``, retrieval filter, or dedup key, so normalizing it is functionally inert — it only makes the
catalog read cleanly. This module is the single source of truth, used both at ingest (so new records
are born canonical) and by the ``iaccm normalize-catalog`` migration (to clean existing records).

Deterministic and idempotent — no model calls. Faithful transcription stays the model's job; this is
the separate, auditable translation/normalization layer that sits after it.
"""

from __future__ import annotations

import re

# French shape words → English, applied token-wise (keys lowercased).
_FR_TERMS: dict[str, str] = {
    "amphore": "amphora",
    "coupe": "cup",
    "assiette": "plate",
    "plat": "dish",
    "cruche": "jug",
    "couvercle": "lid",
    "petit": "small",
    "modèle": "model",
    "modele": "model",
}

# Single-word English head nouns whose pure combinations may be reordered to a canonical order
# (so "dish/bowl" and "bowl/dish" converge). Modifier phrases are never reordered.
_HEADS = {"amphora", "bowl", "casserole", "cup", "dish", "jug", "lid", "plate"}

# Whole-string overrides (lowercased key) for values that are not a simple token-translation:
# 'bord' is a rim sub-entry, not a shape (interim 'amphora rim' — see plan's future-work note);
# the French parenthetical is tidied here rather than left as "amphora (small model)".
CANONICAL: dict[str, str] = {
    "bord": "amphora rim",
    "amphore (petit modèle)": "amphora (small)",
}


def _translate(part: str) -> str:
    return " ".join(_FR_TERMS.get(w, w) for w in part.split())


def normalize_vessel_class(raw: str) -> str:
    """Return the canonical English ``vessel_class`` for a raw printed/extracted value.

    Idempotent: ``normalize(normalize(x)) == normalize(x)``. Collapses whitespace, lowercases,
    translates French shape words, and unifies separator+order for bare two-shape compounds.
    Modifier phrases ("flat-based dish", "dish (variant)") are translated/lowercased, not reordered.
    """
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return ""
    key = s.lower()
    if key in CANONICAL:
        return CANONICAL[key]
    parts: list[str] = []
    for chunk in key.split("/"):
        t = _translate(chunk.strip()).strip()
        if t and t not in parts:  # translate each side, drop duplicates ("lid / couvercle" → "lid")
            parts.append(t)
    if not parts:
        return ""
    if all(p in _HEADS for p in parts):  # only pure head-noun combos get a stable canonical order
        parts = sorted(parts)
    return "/".join(parts)


__all__ = ["normalize_vessel_class", "CANONICAL"]
