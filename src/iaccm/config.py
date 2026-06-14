"""Configuration. All paths resolve relative to a configurable root — nothing hardcoded,
so the repo runs unchanged after being moved to a different directory.

Settings come from environment variables (prefix ``IACCM_``) and an optional ``.env`` file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    """Any OpenAI-compatible endpoint. Default is local Ollama; override for a remote
    open-weights provider. Provider/model are never hardcoded elsewhere — read from here."""

    model_config = SettingsConfigDict(
        env_prefix="IACCM_MODEL_", env_file=".env", extra="ignore", protected_namespaces=()
    )

    provider: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    name: str = "qwen2.5-vl:7b"
    api_key: str = "ollama"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IACCM_", env_file=".env", extra="ignore", protected_namespaces=()
    )

    root: Path = Field(default_factory=find_root)
    corpus_dir: Path = Path("corpus")
    index_dir: Path = Path("index")
    model: ModelSettings = Field(default_factory=ModelSettings)

    def _resolve(self, p: Path) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (self.root / p)

    @property
    def corpus_path(self) -> Path:
        return self._resolve(self.corpus_dir)

    @property
    def index_path(self) -> Path:
        return self._resolve(self.index_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
