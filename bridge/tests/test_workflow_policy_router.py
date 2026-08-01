"""Tests for the Workflow Policy Router (WPR-1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw
import workflow_policy_router as wpr


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({
        "version": 1,
        "policies": [
            {
                "id": "test-repo-health",
                "enabled": True,
                "trigger": {"type": "manual"},
                "action": {"content": "@EA repo health", "require_operator_pubkey": True},
                "limits": {"max_per_hour": 2, "cooldown_s": 0},
                "publish": {"mode": "return_only"},
            },
            {
                "id": "disabled-policy",
                "enabled": False,
                "trigger": {"type": "manual"},
                "action": {"content": "@EA seat", "require_operator_pubkey": True},
                "limits": {"max_per_hour": 1, "cooldown_s": 0},
                "publish": {"mode": "return_only"},
            },
            {
                "id": "cooldown-policy",
                "enabled": True,
                "trigger": {"type": "manual"},
                "action": {"content": "@EA repo health", "require_operator_pubkey": True},
                "limits": {"max_per_hour": 99, "cooldown_s": 10},
                "publish": {"mode": "return_only"},
            },
            {
                "id": "on-queue-depth",
                "enabled": True,
                "trigger": {"type": "queue_nonempty"},
                "action": {"content": "@EA diagnose status", "require_operator_pubkey": True},
                "limits": {"max_per_hour": 99, "cooldown_s": 0},
                "publish": {"mode": "return_only"},
            },
        ],
    }), encoding="utf-8")
    return path


@pytest.fixture
def gateway_config(tmp_path: Path) -> gw.GatewayConfig:
    return gw.GatewayConfig(
        operator_pubkeys=("op1pubkey",),
        rig_ops_channel="rig-ops",
        audit_log_path=tmp_path / "acp_gateway.jsonl",
        devin_queue_path=tmp_path / "acp_devin_queue.jsonl",
        plans_path=tmp_path / "acp_plans.jsonl",
        devin_results_path=tmp_path / "acp_devin_results.jsonl",
        seals_path=tmp_path / "acp_sap_seals.jsonl",
        challenges_path=tmp_path / "acp_sap_challenges.jsonl",
    )


def test_load_policies(catalog: Path):
    policies = wpr._load_policies(catalog)
    assert set(policies) == {"test-repo-health", "disabled-policy", "cooldown-policy", "on-queue-depth"}


def test_load_policies_rejects_bad_content(catalog: Path):
    bad = catalog.parent / "bad.json"
    bad.write_text(json.dumps({
        "version": 1,
        "policies": [
            {
                "id": "bad",
                "enabled": True,
                "action": {"content": "@EA shell foo"},
                "limits": {},
            }
        ]
    }), encoding="utf-8")
    with pytest.raises(wpr.RouterError):
        wpr._load_policies(bad)


def test_dry_run(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    state = tmp_path / "state.jsonl"
    run = wpr.run_policy_by_id(
        "test-repo-health",
        policies_path=catalog,
        state_path=state,
        cfg=gateway_config,
        dry_run=True,
        pubkey="op1pubkey",
    )
    assert run.ok
    assert run.skipped is False
    assert run.content == "@EA repo health"
    assert run.harness == "dry_run"


def test_run_unknown_policy(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    state = tmp_path / "state.jsonl"
    run = wpr.run_policy_by_id(
        "unknown",
        policies_path=catalog,
        state_path=state,
        cfg=gateway_config,
    )
    assert run.ok is False
    assert "unknown policy" in run.error


def test_run_disabled_policy(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    state = tmp_path / "state.jsonl"
    run = wpr.run_policy_by_id(
        "disabled-policy",
        policies_path=catalog,
        state_path=state,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    assert run.ok is True
    assert run.skipped is True
    assert "disabled" in run.error


def test_cooldown_policy(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    state = tmp_path / "state.jsonl"
    # First run goes through (but ACP may reject pubkey; still counts as non-skipped attempt).
    wpr.run_policy_by_id(
        "cooldown-policy",
        policies_path=catalog,
        state_path=state,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    # Second run immediately should hit cooldown.
    run = wpr.run_policy_by_id(
        "cooldown-policy",
        policies_path=catalog,
        state_path=state,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    assert run.skipped is True
    assert "cooldown" in run.error


def test_max_per_hour(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    state = tmp_path / "state.jsonl"
    for _ in range(3):
        wpr.run_policy_by_id(
            "test-repo-health",
            policies_path=catalog,
            state_path=state,
            cfg=gateway_config,
            pubkey="op1pubkey",
        )
    run = wpr.run_policy_by_id(
        "test-repo-health",
        policies_path=catalog,
        state_path=state,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    assert run.skipped is True
    assert "max_per_hour" in run.error


def test_cli_list(catalog: Path, capsys):
    assert wpr._main(["--list", "--config", str(catalog)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list)
    assert {p["id"] for p in out} == {"test-repo-health", "disabled-policy", "cooldown-policy", "on-queue-depth"}


def test_queue_nonempty_empty(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    queue = tmp_path / "queue.jsonl"
    queue.write_text("", encoding="utf-8")
    state = tmp_path / "state.jsonl"
    runs = wpr.run_policy_by_trigger(
        "queue_nonempty",
        policies_path=catalog,
        state_path=state,
        queue_path=queue,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    assert len(runs) == 1
    assert runs[0].skipped is True
    assert runs[0].error == "queue_empty"


def test_queue_nonempty_non_empty(catalog: Path, gateway_config: gw.GatewayConfig, tmp_path: Path):
    queue = tmp_path / "queue.jsonl"
    queue.write_text(
        json.dumps({"status": "queued", "job_id": "j1"}) + "\n",
        encoding="utf-8",
    )
    state = tmp_path / "state.jsonl"
    runs = wpr.run_policy_by_trigger(
        "queue_nonempty",
        policies_path=catalog,
        state_path=state,
        queue_path=queue,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    assert len(runs) == 1
    assert runs[0].policy_id == "on-queue-depth"
    assert runs[0].skipped is False


def test_queue_nonempty_runs_on_queue_depth_policy(gateway_config: gw.GatewayConfig, tmp_path: Path):
    catalog = tmp_path / "policies.json"
    catalog.write_text(json.dumps({
        "version": 1,
        "policies": [
            {
                "id": "on-queue-depth",
                "enabled": True,
                "trigger": {"type": "queue_nonempty"},
                "action": {"content": "@EA diagnose status", "require_operator_pubkey": True},
                "limits": {},
                "publish": {"mode": "return_only"},
            }
        ]
    }), encoding="utf-8")
    queue = tmp_path / "queue.jsonl"
    queue.write_text(
        json.dumps({"status": "queued", "job_id": "j1"}) + "\n",
        encoding="utf-8",
    )
    state = tmp_path / "state.jsonl"
    runs = wpr.run_policy_by_trigger(
        "queue_nonempty",
        policies_path=catalog,
        state_path=state,
        queue_path=queue,
        cfg=gateway_config,
        pubkey="op1pubkey",
    )
    assert len(runs) == 1
    assert runs[0].policy_id == "on-queue-depth"
    assert runs[0].skipped is False


def test_webhook_transport(tmp_path: Path):
    """WPR-3 — policy runner POSTs to a webhook and interprets the response."""
    import http.server
    import threading

    received: list[dict] = []
    response = {"ok": True, "content": "repo: healthy", "tags": [["acp_tool", "repo_health"]], "tool": "repo_health", "harness": "grok-build"}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            received.append(json.loads(body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        policy = wpr.Policy(
            id="webhook-test",
            enabled=True,
            trigger={},
            match={},
            action={"content": "@EA repo health"},
            limits={},
            publish={},
        )
        run = wpr._run_webhook(policy, f"http://127.0.0.1:{port}/buzz", "op1")
        assert run.ok is True
        assert run.content == "repo: healthy"
        assert run.tool == "repo_health"
        assert run.harness == "grok-build"
        assert received[0]["content"] == "@EA repo health"
        assert received[0]["pubkey"] == "op1"
    finally:
        server.shutdown()


def test_cli_trigger_queue_nonempty(catalog: Path, capsys, tmp_path: Path):
    queue = tmp_path / "queue.jsonl"
    queue.write_text("", encoding="utf-8")
    assert wpr._main(["--trigger", "queue_nonempty", "--config", str(catalog), "--queue-path", str(queue)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list)
    assert out[0]["skipped"] is True
    assert out[0]["error"] == "queue_empty"
