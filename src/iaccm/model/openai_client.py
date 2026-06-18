"""OpenAI-compatible backend — any endpoint that speaks the OpenAI chat API: a hosted open-weight
provider (e.g. Featherless), a local server (Ollama / vLLM), or OpenAI itself. Select it with
``--provider featherless`` (or `ollama`/`openai`/…), or ``IACCM_MODEL_PROVIDER=featherless``.

Vision is sent as ``image_url`` content blocks; structured output is the shared prompted-JSON
``parse`` inherited from ``ModelClient`` (so this backend needs no override). The chosen model MUST
be vision-capable for ingest and identification — pick an open VLM (e.g. a Qwen-VL / Llama-Vision).
PDF attachment is not supported here (the agent renders pages to images, which is what ingest uses).
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from .base import ModelClient, PdfRef, guess_media_type


def _data_url(path: Path) -> str:
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{guess_media_type(path)};base64,{b64}"


def _resolve_key(provider: str, configured: str) -> str:
    """API key for an OpenAI-compatible provider: the PROVIDER-specific env var wins (e.g.
    ``FEATHERLESS_API_KEY``) so several providers' keys can sit in ``.env`` without colliding; then
    the generic ``IACCM_MODEL_API_KEY``, then ``OPENAI_API_KEY``. A placeholder is the last resort
    for keyless local endpoints (Ollama ignores the key)."""
    return (
        os.environ.get(f"{provider.upper()}_API_KEY", "")
        or configured
        or os.environ.get("OPENAI_API_KEY", "")
        or "-"
    )


class OpenAICompatibleClient(ModelClient):
    def __init__(self, settings: Settings | None = None) -> None:
        from openai import OpenAI  # lazy

        self.settings = settings or get_settings()
        m = self.settings.model
        self._client = OpenAI(base_url=m.endpoint, api_key=_resolve_key(m.provider, m.api_key))
        self.model_name = m.name

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[Path] | None = None,
        pdf: PdfRef | None = None,
        max_tokens: int = 16000,
    ) -> str:
        if pdf is not None:
            raise NotImplementedError(
                "PDF attachment is not supported on the OpenAI-compatible backend; "
                "ingest renders pages to images."
            )
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images or []:
            content.append({"type": "image_url", "image_url": {"url": _data_url(img)}})
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    # parse() is inherited from ModelClient (shared prompted-JSON structured output over generate).
