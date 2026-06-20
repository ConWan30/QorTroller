"""Webhook ingest gated on RETINA_EXTERNAL_INGEST_ENABLED."""
from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient


def _app(tmp_path, monkeypatch, *, external_ingest: bool):
    monkeypatch.setenv("OPERATOR_API_KEY", "test-key")
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.store import Store
    from bridge.vapi_bridge.operator_api._app import create_operator_app

    cfg = replace(
        Config(),
        operator_api_key="test-key",
        retina_external_ingest_enabled=external_ingest,
    )
    store = Store(str(tmp_path / "wh.db"))
    app = create_operator_app(cfg, store, chain=None)
    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    return _app(tmp_path, monkeypatch, external_ingest=False)


def test_webhook_rejected_when_external_ingest_off(client):
    resp = client.post(
        "/operator/retina-event?api_key=test-key",
        json={"device_id": "cd" * 32, "events": []},
    )
    assert resp.status_code == 403
    assert "RETINA_EXTERNAL_INGEST_ENABLED" in resp.json()["detail"]


def test_webhook_accepted_when_external_ingest_on(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch, external_ingest=True)

    resp = client.post(
        "/operator/retina-event?api_key=test-key",
        json={"device_id": "cd" * 32, "events": [{"type": "test"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
