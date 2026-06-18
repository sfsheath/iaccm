"""Model access — provider-agnostic. Default backend is Claude; OpenAI-compatible kept for later."""

from __future__ import annotations

from ..config import Settings, get_settings
from .base import ModelClient, PdfRef

__all__ = ["ModelClient", "PdfRef", "get_model_client"]

_OPENAI_COMPATIBLE = {"featherless", "ollama", "openai", "openai-compatible", "vllm", "remote"}


def get_model_client(
    settings: Settings | None = None, *, provider: str | None = None, model: str | None = None
) -> ModelClient:
    """Return the configured backend. ``IACCM_MODEL_PROVIDER`` selects it (default anthropic);
    ``provider`` / ``model`` override it per call (the CLI ``--provider`` / ``--model`` flags), so a
    run can switch to an open-weight provider while keys stay in ``.env``."""
    settings = settings or get_settings()
    if provider or model:
        updates = {k: v for k, v in (("provider", provider), ("name", model)) if v}
        settings = settings.model_copy(update={"model": settings.model.model_copy(update=updates)})
    name = settings.model.provider.lower()
    if name == "anthropic":
        from .anthropic_client import AnthropicClient

        return AnthropicClient(settings)
    if name in _OPENAI_COMPATIBLE:
        from .openai_client import OpenAICompatibleClient

        return OpenAICompatibleClient(settings)
    raise ValueError(
        f"Unknown model provider {name!r}; expected 'anthropic' or {sorted(_OPENAI_COMPATIBLE)}."
    )
