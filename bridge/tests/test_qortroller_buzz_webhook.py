#!/usr/bin/env python3
"""Tests for scripts/qortroller_buzz_webhook.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw
import qortroller_buzz_webhook as webhook

OPERATOR = "abc123operatorpubkey"


@pytest.fixture
def acp_cfg(tmp_path: Path) -> gw.GatewayConfig:
    return gw.GatewayConfig(
        operator_pubkeys=(OPERATOR,),
        audit_log_path=tmp_path / "acp_gateway.jsonl",
        devin_queue_path=tmp_path / "acp_devin_queue.jsonl",
        plans_path=tmp_path / "acp_plans.jsonl",
        devin_results_path=tmp_path / "acp_devin_results.jsonl",
    )


@pytest.fixture
def client(acp_cfg: gw.GatewayConfig):
    from fastapi.testclient import TestClient

    app = webhook.make_app(
        webhook_cfg=webhook.WebhookConfig(
            operator_pubkeys=(OPERATOR,),
            webhook_secret="s3cr3t",
        ),
        acp_cfg=acp_cfg,
    )
    return TestClient(app)


def test_webhook_rejects_missing_auth(client):
    response = client.post("/buzz", json={"pubkey": OPERATOR, "content": "@EA status"})
    assert response.status_code == 401


def test_webhook_accepts_allowed_command(client):
    response = client.post(
        "/buzz",
        json={"pubkey": OPERATOR, "content": "@EA wp acp"},
        headers={"Authorization": "Bearer s3cr3t"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["tool"] == gw.TOOL_SHOW_WP_STATUS
    assert data["content"].startswith("[grok-build]")
    assert any(tag[0] == "acp_tool" and tag[1] == gw.TOOL_SHOW_WP_STATUS for tag in data["tags"])


def test_webhook_rejects_unknown_pubkey(client):
    response = client.post(
        "/buzz",
        json={"pubkey": "badpubkey", "content": "@EA status"},
        headers={"Authorization": "Bearer s3cr3t"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "rejected" in data["content"].lower()


def test_webhook_requires_pubke_and_content(client):
    response = client.post("/buzz", json={}, headers={"Authorization": "Bearer s3cr3t"})
    assert response.status_code == 400
