"""Guidance loaded into the identification prompt — **incrementally**, as the sherd narrows.

`docs/method.md` (the cascade, the two-layer doctrine, the breadth invariant, the compact triage
key) is always loaded — it is general and ware-neutral. The per-category diagnostic keys
(`docs/typologies/*.md`) are loaded **only when the sherd triages to that category**: the model
returns a `category`, and the matching key loads to refine the next turn.

Why not load them all every time: a key is necessarily opinionated about its own ware family (the
ARS key will say ARS things, the amphora key amphora things). Injecting every key into every
identification biases unrelated sherds — an ARS discriminator has no business steering a lamp ID.
Load only what the sherd has narrowed to. This also keeps the prompt focused as the typology set
grows to tens of categories.
"""

from __future__ import annotations

import re
from functools import cache, lru_cache
from pathlib import Path

from ..config import get_settings

# Category → the typology key that loads when a sherd triages to it. Add a row when you add a
# docs/typologies/<file>.md for a new category. The keys here are the canonical category tokens the
# model is asked to use; `normalize_category` maps common variants onto them.
CATEGORY_DOCS: dict[str, str] = {
    "fineware": "finewares.md",
    "coarseware": "coarsewares.md",
    "amphora": "amphorae.md",
    "lamp": "lamps.md",
}

_SYNONYMS: dict[str, str] = {
    "fineware": "fineware",
    "fine ware": "fineware",
    "fine wares": "fineware",
    "tableware": "fineware",
    "fine": "fineware",
    "coarseware": "coarseware",
    "coarse ware": "coarseware",
    "coarse wares": "coarseware",
    "coarse": "coarseware",
    "cooking ware": "coarseware",
    "cookingware": "coarseware",
    "cooking": "coarseware",
    "coarse cooking ware": "coarseware",
    "amphora": "amphora",
    "amphorae": "amphora",
    "transport amphora": "amphora",
    "lamp": "lamp",
    "lamps": "lamp",
}


def _docs_dir() -> Path:
    return get_settings().root / "docs"


@lru_cache(maxsize=1)
def load_method() -> str:
    """The ware-neutral method/principles + triage key. Always loaded."""
    p = _docs_dir() / "method.md"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


@cache
def load_category(category: str) -> str:
    """The diagnostic key for one triaged category (``""`` if unknown or absent)."""
    fn = CATEGORY_DOCS.get(category)
    if not fn:
        return ""
    p = _docs_dir() / "typologies" / fn
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def available_categories() -> list[str]:
    """Category tokens whose key file actually exists on disk."""
    return [c for c, fn in CATEGORY_DOCS.items() if (_docs_dir() / "typologies" / fn).is_file()]


def normalize_category(text: str) -> str | None:
    """Map the model's free-text category onto a canonical token, or None if it isn't one."""
    return _SYNONYMS.get(re.sub(r"\s+", " ", text.strip().lower()))
