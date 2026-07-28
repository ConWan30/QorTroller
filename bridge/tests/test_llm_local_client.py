"""R1 tests for LocalOpenAIClient. No real network — all HTTP mocked."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from bridge.vapi_bridge.llm_routing.local_client import LocalHealth, LocalOpenAIClient


# ---------------------------------------------------------------------------
# Default-OFF
# ---------------------------------------------------------------------------


def test_default_disabled_without_env(monkeypatch):
    monkeypatch.delenv("LOCAL_LLM_ENABLED", raising=False)
    client = LocalOpenAIClient()
    assert client.enabled is False
    assert client.configured is False
    h = client.health()
    assert h.ok is False
    assert h.enabled is False
    assert h.detail == "local_llm_disabled"
    assert h.live is False
    assert client.chat([{"role": "user", "content": "hi"}]) is None


def test_explicit_enabled_true_overrides_env(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "0")
    client = LocalOpenAIClient(enabled=True, session=MagicMock())
    assert client.enabled is True


def test_env_truthy_enables(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
    client = LocalOpenAIClient(session=MagicMock())
    assert client.enabled is True


# ---------------------------------------------------------------------------
# Health — fail-open
# ---------------------------------------------------------------------------


def test_health_ok_when_models_lists_configured_model():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"id": "deepseek-r1:14b"}, {"id": "other"}]}
    session.get.return_value = resp

    client = LocalOpenAIClient(
        enabled=True,
        model="deepseek-r1:14b",
        base_url="http://127.0.0.1:11434/v1",
        session=session,
    )
    h = client.health()
    assert h.ok is True
    assert h.enabled is True
    assert h.live is True
    assert h.detail == "ok"
    assert h.latency_ms is not None
    session.get.assert_called_once()
    assert session.get.call_args[0][0] == "http://127.0.0.1:11434/v1/models"


def test_health_model_not_listed_still_ok_with_detail():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"id": "llama3"}]}
    session.get.return_value = resp

    client = LocalOpenAIClient(enabled=True, model="deepseek-r1:14b", session=session)
    h = client.health()
    assert h.ok is True
    assert h.detail == "model_not_listed:deepseek-r1:14b"


def test_health_http_error_not_ok():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 503
    session.get.return_value = resp

    client = LocalOpenAIClient(enabled=True, session=session)
    h = client.health()
    assert h.ok is False
    assert h.enabled is True
    assert h.live is True
    assert h.detail == "http_503"


def test_health_connection_error_fail_open():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("refused")

    client = LocalOpenAIClient(enabled=True, session=session)
    h = client.health()
    assert h.ok is False
    assert h.enabled is True
    assert h.live is False
    assert h.detail.startswith("unreachable:")


def test_health_to_dict_shape():
    h = LocalHealth(
        ok=True,
        enabled=True,
        base_url="http://127.0.0.1:11434/v1",
        model="deepseek-r1:14b",
        detail="ok",
        latency_ms=12.5,
        live=True,
    )
    d = h.to_dict()
    assert d["backend"] == "local"
    assert d["ok"] is True
    assert d["live"] is True


# ---------------------------------------------------------------------------
# Chat — fail-open
# ---------------------------------------------------------------------------


def test_chat_disabled_returns_none_without_http():
    session = MagicMock()
    client = LocalOpenAIClient(enabled=False, session=session)
    assert client.chat([{"role": "user", "content": "hi"}]) is None
    session.post.assert_not_called()


def test_chat_ok_returns_content():
    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": "local-ok"}}]
    }
    session.post.return_value = resp

    client = LocalOpenAIClient(enabled=True, model="deepseek-r1:14b", session=session)
    out = client.chat([{"role": "user", "content": "ping"}])
    assert out == "local-ok"
    args, kwargs = session.post.call_args
    assert args[0].endswith("/chat/completions")
    assert kwargs["json"]["model"] == "deepseek-r1:14b"


def test_chat_http_error_returns_none():
    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError("500")
    session.post.return_value = resp

    client = LocalOpenAIClient(enabled=True, session=session)
    assert client.chat([{"role": "user", "content": "x"}]) is None


def test_chat_connection_error_returns_none():
    session = MagicMock()
    session.post.side_effect = requests.ConnectionError("down")

    client = LocalOpenAIClient(enabled=True, session=session)
    assert client.chat([{"role": "user", "content": "x"}]) is None


def test_chat_passes_optional_temperature():
    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": "t"}}]}
    session.post.return_value = resp

    client = LocalOpenAIClient(enabled=True, session=session)
    client.chat([{"role": "user", "content": "x"}], temperature=0.0)
    assert session.post.call_args.kwargs["json"]["temperature"] == 0.0


# ---------------------------------------------------------------------------
# Config surface
# ---------------------------------------------------------------------------


def test_env_base_url_and_model(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "1")
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://10.0.0.2:1234/v1/")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5:7b")
    client = LocalOpenAIClient(session=MagicMock())
    assert client.base_url == "http://10.0.0.2:1234/v1"
    assert client.model == "qwen2.5:7b"


def test_api_key_header_when_set():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": []}
    session.get.return_value = resp

    client = LocalOpenAIClient(enabled=True, api_key="local-secret", session=session)
    client.health()
    headers = session.get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer local-secret"


def test_no_authorization_header_without_key():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": []}
    session.get.return_value = resp

    client = LocalOpenAIClient(enabled=True, api_key="", session=session)
    client.health()
    headers = session.get.call_args.kwargs["headers"]
    assert "Authorization" not in headers
