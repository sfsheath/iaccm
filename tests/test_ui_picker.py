"""The UI model picker reflects what's actually usable: a cloud provider only with its key present,
Ollama only when its server answers. No network (the Ollama probe is monkeypatched)."""

from __future__ import annotations

import io
import json

from iaccm.ui import app


def _labels(monkeypatch, **env) -> list[str]:
    monkeypatch.setattr(app, "_ollama_models", lambda: [])
    for k in ("ANTHROPIC_API_KEY", "IACCM_MODEL_API_KEY", "FEATHERLESS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return [lbl for lbl, _, _ in app._available_presets()]


def test_featherless_only_with_key(monkeypatch) -> None:
    assert any("Featherless" in lbl for lbl in _labels(monkeypatch, FEATHERLESS_API_KEY="fk"))
    assert not any("Featherless" in lbl for lbl in _labels(monkeypatch))  # no key → hidden


def test_anthropic_only_with_key(monkeypatch) -> None:
    assert any("Anthropic" in lbl for lbl in _labels(monkeypatch, ANTHROPIC_API_KEY="sk"))
    assert not any("Anthropic" in lbl for lbl in _labels(monkeypatch, FEATHERLESS_API_KEY="fk"))


def test_no_providers_is_empty(monkeypatch) -> None:
    assert _labels(monkeypatch) == []  # nothing configured, Ollama down → empty (UI has a fallback)


def test_ollama_models_parsed_when_running(monkeypatch) -> None:
    payload = json.dumps({"models": [{"name": "qwen2.5-vl:7b"}, {"name": "llava:13b"}]}).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=0: io.BytesIO(payload))
    assert app._ollama_models() == [
        ("Ollama / qwen2.5-vl:7b", "ollama", "qwen2.5-vl:7b"),
        ("Ollama / llava:13b", "ollama", "llava:13b"),
    ]


def test_ollama_unreachable_returns_empty(monkeypatch) -> None:
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert app._ollama_models() == []


def test_colour_note_injects_only_set_colours() -> None:
    # Eyedropper samples are appended to the user's message so the model treats them as observables.
    assert app._colour_note(None, None) == ""  # nothing sampled → no noise in the prompt
    assert app._colour_note("#b5563a", None) == " [sampled colours — surface/slip #b5563a]"
    assert app._colour_note(None, "#c97f5a") == " [sampled colours — fresh-break fabric #c97f5a]"
    both = app._colour_note("#b5563a", "#c97f5a")
    assert both == " [sampled colours — surface/slip #b5563a; fresh-break fabric #c97f5a]"


def test_eyedropper_handler_detects_selectdata() -> None:
    # Regression: the click handler's ``evt: gr.SelectData`` must be detected as event-data, or
    # Gradio misbinds the click coords. build_app() binds ``gr`` into module globals so the
    # lazily-imported annotation resolves; building without a mismatch warning proves it.
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        app.build_app()  # raises if Gradio can't match the handler's args (the misbinding symptom)
