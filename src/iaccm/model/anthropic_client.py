"""Claude backend (default). Uses the official ``anthropic`` SDK — never an OpenAI-compatible shim.

Model default is ``claude-opus-4-8`` (from config). Adaptive thinking is on for the kind of
constrained extraction/comparison this tool does. PDFs are attached as ``document`` blocks (inline
base64 for a small slice, or by ``file_id`` after an upload-once via the Files API).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from .base import ModelClient, PdfRef, guess_media_type

_FILES_BETA = "files-api-2025-04-14"


def _b64(path: Path) -> str:
    return base64.standard_b64encode(Path(path).read_bytes()).decode()


class AnthropicClient(ModelClient):
    def __init__(self, settings: Settings | None = None) -> None:
        import anthropic  # lazy: keep package import cheap

        self.settings = settings or get_settings()
        m = self.settings.model
        # api_key="" → let the SDK resolve ANTHROPIC_API_KEY from the environment.
        self._client = anthropic.Anthropic(api_key=m.api_key or None)
        self.model_name = m.name

    # --- content assembly ---------------------------------------------------

    def _content(
        self, prompt: str, images: list[Path] | None, pdf: PdfRef | None
    ) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        if pdf is not None:
            if pdf.file_id:
                blocks.append(
                    {"type": "document", "source": {"type": "file", "file_id": pdf.file_id}}
                )
            elif pdf.path:
                blocks.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": _b64(pdf.path),
                        },
                    }
                )
        for img in images or []:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": guess_media_type(img),
                        "data": _b64(img),
                    },
                }
            )
        blocks.append({"type": "text", "text": prompt})
        return blocks

    def _betas(self, pdf: PdfRef | None) -> list[str]:
        return [_FILES_BETA] if (pdf and pdf.file_id) else []

    # --- public API ---------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[Path] | None = None,
        pdf: PdfRef | None = None,
        max_tokens: int = 16000,
    ) -> str:
        kwargs: dict[str, Any] = dict(
            model=self.model_name,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": self._content(prompt, images, pdf)}],
        )
        if system:
            kwargs["system"] = system
        betas = self._betas(pdf)
        resp = (
            self._client.beta.messages.create(betas=betas, **kwargs)
            if betas
            else self._client.messages.create(**kwargs)
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    # parse() is inherited from ModelClient (shared prompted-JSON structured output).

    def upload_pdf(self, path: Path) -> PdfRef:
        uploaded = self._client.beta.files.upload(
            file=Path(path), betas=[_FILES_BETA]
        )
        return PdfRef(file_id=uploaded.id)
