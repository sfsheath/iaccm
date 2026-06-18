"""Provider seam: structured output is shared across backends (prompted JSON over generate), and the
provider is selectable per call (the CLI --provider/--model flags). No network."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from iaccm.config import ModelSettings, Settings
from iaccm.model import get_model_client
from iaccm.model.base import ModelClient


class _Out(BaseModel):
    a: int
    b: str = ""


def test_parse_is_shared_prompted_json() -> None:
    """Any backend inherits ModelClient.parse: it appends a JSON-schema instruction to the prompt,
    calls generate(), and validates the reply — independent of the concrete SDK."""
    seen: dict = {}

    class FakeClient(ModelClient):
        model_name = "fake"

        def generate(self, prompt, *, system=None, images=None, pdf=None, max_tokens=16000):
            seen["prompt"] = prompt
            return 'noise before {"a": 7, "b": "x"} noise after'  # fenced/dirty JSON tolerated

    out = FakeClient().parse("describe", _Out)
    assert out == _Out(a=7, b="x")
    assert "JSON Schema" in seen["prompt"]  # the schema instruction was appended


def test_parse_retries_once_then_raises() -> None:
    class BadClient(ModelClient):
        model_name = "bad"
        calls = 0

        def generate(self, prompt, *, system=None, images=None, pdf=None, max_tokens=16000):
            type(self).calls += 1
            return "not json at all"

    bad = BadClient()
    with pytest.raises(RuntimeError, match="did not return a valid _Out"):
        bad.parse("x", _Out)
    assert BadClient.calls == 2  # one retry


def _settings(provider: str, **model_kw) -> Settings:
    return Settings(model=ModelSettings(provider=provider, api_key="k", **model_kw))


def test_featherless_routes_to_openai_compatible_with_default_endpoint() -> None:
    client = get_model_client(_settings("featherless", name="some-vlm"))
    assert type(client).__name__ == "OpenAICompatibleClient"
    assert client.settings.model.endpoint == "https://api.featherless.ai/v1"
    assert client.model_name == "some-vlm"


def test_provider_and_model_override() -> None:
    # default config is anthropic; --provider/--model switch the run without touching .env
    client = get_model_client(_settings("anthropic"), provider="featherless", model="vlm-x")
    assert type(client).__name__ == "OpenAICompatibleClient"
    assert client.model_name == "vlm-x"


def test_endpoint_explicit_base_url_wins() -> None:
    s = _settings("featherless", base_url="http://localhost:9999/v1")
    assert s.model.endpoint == "http://localhost:9999/v1"


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown model provider"):
        get_model_client(_settings("nope-llm"))


def test_dotenv_loads_bare_keys(tmp_path, monkeypatch) -> None:
    # bare (unprefixed) keys in .env must reach the process env so the SDKs / _resolve_key see them
    import os

    from iaccm.config import _load_dotenv

    (tmp_path / ".env").write_text('IACCM_TEST_KEY=fk-test\n# a comment\nIACCM_TEST_Q="quoted"\n')
    monkeypatch.delenv("IACCM_TEST_KEY", raising=False)
    monkeypatch.delenv("IACCM_TEST_Q", raising=False)
    try:
        _load_dotenv(tmp_path)
        assert os.environ.get("IACCM_TEST_KEY") == "fk-test"
        assert os.environ.get("IACCM_TEST_Q") == "quoted"  # surrounding quotes stripped
        monkeypatch.setenv("IACCM_TEST_KEY", "shell-wins")  # a shell value must NOT be overridden
        _load_dotenv(tmp_path)
        assert os.environ["IACCM_TEST_KEY"] == "shell-wins"
    finally:
        os.environ.pop("IACCM_TEST_KEY", None)
        os.environ.pop("IACCM_TEST_Q", None)


def test_featherless_key_resolves_from_env(monkeypatch) -> None:
    # the provider-specific key wins over the generic IACCM_MODEL_API_KEY (no collision)
    from iaccm.model.openai_client import _resolve_key

    monkeypatch.setenv("FEATHERLESS_API_KEY", "fk-123")
    assert _resolve_key("featherless", "generic-key") == "fk-123"
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    assert _resolve_key("featherless", "generic-key") == "generic-key"
