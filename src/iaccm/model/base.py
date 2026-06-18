"""Provider-agnostic model interface.

The rest of the app talks to a ``ModelClient`` and never to a concrete SDK. The default backend
is Claude (``anthropic_client``); an OpenAI-compatible backend (``openai_client``) is kept for a
future local path (Ollama / vLLM). ``config.model.provider`` selects which one ``get_model_client``
returns.

The model is only ever asked to do *constrained comparison / extraction* grounded in supplied
images, PDFs and notes (CLAUDE.md rule 3) — never open-ended recall of a typology.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

# --- structured output via prompted JSON ---------------------------------------------------
# We deliberately do NOT use the server-side strict-grammar paths (``messages.parse`` /
# ``output_config.format`` / ``strict`` tool use): the per-page extraction schema (a list of
# ~13-field objects) is large enough that constrained-grammar compilation times out
# ("Grammar compilation timed out" / "Schema is too complex"). Instead we ask for plain JSON,
# keep adaptive thinking on, and validate client-side with a one-shot retry. This is the only
# structured-output mechanism the app uses, so every backend inherits it.


def json_schema_instruction(schema: type[BaseModel]) -> str:
    """Instruction appended to a prompt asking the model to emit one JSON object for ``schema``."""
    return (
        "\n\nReturn your answer as a SINGLE JSON object conforming to this JSON Schema. "
        "Output ONLY the JSON object — no markdown fences, no prose before or after it.\n"
        + json.dumps(schema.model_json_schema())
    )


def parse_json_response[T: BaseModel](text: str, schema: type[T]) -> T:
    """Validate a model's text reply into ``schema``, tolerating fences/prose around the JSON."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object found in model output: {text[:200]!r}")
    return schema.model_validate_json(text[start : end + 1])


@dataclass
class PdfRef:
    """A PDF to attach to a request — either an inline local path (sent as base64) or an
    already-uploaded provider file id (Anthropic Files API)."""

    path: Path | None = None
    file_id: str | None = None


def guess_media_type(path: Path) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")


class ModelClient(ABC):
    """A thin, single-shot interface. Multi-turn dialog is composed by the agent on top of this."""

    model_name: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[Path] | None = None,
        pdf: PdfRef | None = None,
        max_tokens: int = 16000,
    ) -> str:
        """Return the model's text reply to a prompt plus optional images / a PDF."""

    def parse[T: BaseModel](
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        images: list[Path] | None = None,
        pdf: PdfRef | None = None,
        max_tokens: int = 16000,
    ) -> T:
        """Return a validated instance of ``schema`` via prompted JSON over ``generate`` — the only
        structured-output mechanism (see the module note), so every backend inherits it. Asks for
        one JSON object, validates client-side, and retries once on malformed output."""
        instruction = json_schema_instruction(schema)
        last_err: Exception | None = None
        for attempt in range(2):
            retry = "" if attempt == 0 else (
                "\n\nYour previous reply was not valid JSON. Output ONLY the JSON object."
            )
            text = self.generate(
                prompt + instruction + retry,
                system=system,
                images=images,
                pdf=pdf,
                max_tokens=max_tokens,
            )
            try:
                return parse_json_response(text, schema)
            except (ValidationError, ValueError) as e:
                last_err = e
        raise RuntimeError(f"model did not return a valid {schema.__name__}: {last_err}")

    def upload_pdf(self, path: Path) -> PdfRef:
        """Make a reusable reference to a PDF. Default is inline (no upload); backends with a
        Files API override this to upload once and reference by id across many requests."""
        return PdfRef(path=Path(path))
