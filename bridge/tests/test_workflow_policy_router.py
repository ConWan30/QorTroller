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
    assert set(policies) == {"test-repo-health", "disabled-policy", "cooldown-policy"}


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
    assert {p["id"] for p in out} == {"test-repo-health", "disabled-policy", "cooldown-policy"}
