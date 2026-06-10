"""Tests for LLM provider resolution and the LiteLLM routing path.

These tests never hit the network — ``litellm.completion`` is monkeypatched.
"""

import os
import tempfile
import types

os.environ.setdefault("TESTGEN_DB_DIR", tempfile.mkdtemp(prefix="testgen-test-"))

from app import config  # noqa: E402
from app.llm import LLMClient, _extract_json  # noqa: E402


def _fake_response(content: str):
    msg = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=msg, finish_reason="stop")
    return types.SimpleNamespace(choices=[choice])


def _litellm_client(monkeypatch, model="gpt-4o", base_url="http://gw.local/v1", key="sk-test"):
    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "litellm")
    monkeypatch.setattr(config.settings, "LITELLM_BASE_URL", base_url)
    monkeypatch.setattr(config.settings, "LITELLM_API_KEY", key)
    monkeypatch.setattr(config.settings, "LITELLM_MODEL", model)
    return LLMClient()


def test_litellm_available_and_model(monkeypatch):
    client = _litellm_client(monkeypatch)
    assert client.provider == "litellm"
    assert client.available
    assert client.model == "gpt-4o"


def test_litellm_adds_openai_prefix_for_proxy(monkeypatch):
    client = _litellm_client(monkeypatch)
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("hello")

    monkeypatch.setattr(client._client, "completion", fake_completion)
    assert client.complete("hi") == "hello"
    assert captured["model"] == "openai/gpt-4o"
    assert captured["api_base"] == "http://gw.local/v1"
    assert captured["api_key"] == "sk-test"
    assert [m["role"] for m in captured["messages"]] == ["system", "user"]


def test_litellm_keeps_existing_prefix(monkeypatch):
    client = _litellm_client(monkeypatch, model="anthropic/claude-3-haiku")
    captured = {}
    monkeypatch.setattr(
        client._client, "completion", lambda **kw: (captured.update(kw), _fake_response("ok"))[1]
    )
    client.complete("hi")
    assert captured["model"] == "anthropic/claude-3-haiku"


def test_auto_prefers_litellm_when_gateway_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(config.settings, "LITELLM_BASE_URL", "http://gw.local/v1")
    monkeypatch.setattr(config.settings, "LITELLM_API_KEY", None)
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-openai")
    assert LLMClient()._resolve_provider() == "litellm"


def test_complete_json_parses_fenced_block():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
