"""Thin wrapper over any OpenAI-compatible endpoint (Ollama / vLLM / remote provider).

The model is only ever asked to do *constrained comparison* grounded in supplied images and
notes (docs/method.md, CLAUDE.md rule 3) — never open-ended recall of a typology.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings


def _encode_image(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


class ModelClient:
    def __init__(self, settings: Settings | None = None) -> None:
        from openai import OpenAI  # lazy: keeps package import cheap

        self.settings = settings or get_settings()
        m = self.settings.model
        self._client = OpenAI(base_url=m.base_url, api_key=m.api_key)
        self.model_name = m.name

    def vision_chat(
        self, prompt: str, images: list[Path] | None = None, **kwargs: Any
    ) -> str:
        """Send a prompt plus optional images; return the text reply."""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images or []:
            b64 = _encode_image(img)
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            )
        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": content}],
            **kwargs,
        )
        return resp.choices[0].message.content or ""
