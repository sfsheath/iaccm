"""Configuration. All paths resolve relative to a configurable root — nothing hardcoded,
so the repo runs unchanged after being moved to a different directory.

Settings come from environment variables (prefix ``IACCM_``) and an optional ``.env`` file.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv(root: Path) -> None:
    """Load ``KEY=VALUE`` lines from ``<root>/.env`` into the process environment (a shell-exported
    value wins). Lets per-provider keys (``ANTHROPIC_API_KEY``, ``FEATHERLESS_API_KEY``, …) live in
    ``.env`` without the ``IACCM_MODEL_`` prefix — pydantic-settings only auto-reads its own
    prefixed fields. No python-dotenv dependency."""
    env = root / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key:
            os.environ.setdefault(key, val.strip().strip('"').strip("'"))


def find_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` (or CWD) to the folder containing pyproject.toml.

    Falls back to the starting directory if none is found, so the app still runs when
    installed as a wheel rather than from a checkout.
    """
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return start


class ModelSettings(BaseSettings):
    """Model backend. Default is Claude via the official SDK (``provider="anthropic"``); set
    ``provider="ollama"`` (or another OpenAI-compatible value) for a local path. Provider/model
    are never hardcoded elsewhere — read from here.

    For Claude, leave ``api_key`` empty to let the SDK read ``ANTHROPIC_API_KEY`` from the
    environment, or set ``IACCM_MODEL_API_KEY`` in ``.env`` to pass a key explicitly.
    """

    model_config = SettingsConfigDict(
        env_prefix="IACCM_MODEL_", env_file=".env", extra="ignore", protected_namespaces=()
    )

    provider: str = "anthropic"
    base_url: str = ""  # OpenAI-compatible endpoint; blank → per-provider default (see `endpoint`)
    name: str = "claude-opus-4-8"
    api_key: str = ""

    @property
    def endpoint(self) -> str:
        """OpenAI-compatible base URL: an explicit ``base_url`` wins, else a per-provider default
        (so ``--provider featherless`` needs only a key + model, not a URL)."""
        defaults = {
            "featherless": "https://api.featherless.ai/v1",
            "ollama": "http://localhost:11434/v1",
        }
        return self.base_url or defaults.get(self.provider.lower(), "http://localhost:11434/v1")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IACCM_", env_file=".env", extra="ignore", protected_namespaces=()
    )

    root: Path = Field(default_factory=find_root)
    corpus_dir: Path = Path("corpus")  # user's own PDFs — git-ignored (copyright firewall)
    bundle_dir: Path = Path("bundle")  # shareable derived facts (the catalog) — committed
    index_dir: Path = Path("index")  # local-only derived artifacts (vectors, caches) — git-ignored
    model: ModelSettings = Field(default_factory=ModelSettings)

    def _resolve(self, p: Path) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (self.root / p)

    @property
    def corpus_path(self) -> Path:
        return self._resolve(self.corpus_dir)

    @property
    def bundle_path(self) -> Path:
        return self._resolve(self.bundle_dir)

    @property
    def index_path(self) -> Path:
        return self._resolve(self.index_dir)


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(find_root())  # make bare per-provider keys in .env available to the SDKs
    return Settings()
