"""Tests for BCRA — bridge connectivity readiness aggregator (read-only composition + VPM honesty)."""
from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vapi_bridge.bridge_connectivity_aggregator import (  # noqa: E402
    LaneState, ReadinessVerdict, SCHEMA_VERSION, VPM_VISUAL_STATES, LANE_ORDER,
    classify_controller, classify_agents, classify_chain, classify_operational,
    assemble_connectivity, verify_attestation,
)


def _ctrl_ok(): return {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000}
def _agents_ok(): return {"fleet_coherent": True, "agents_total": 38, "agents_live": 38}
def _chain_ok(): return {"rpc_reachable": True, "submission_paused": False}
def _oper_ok(): return {"watchdog_chain_intact": True, "gic_chain_intact": True, "restarts_last_hour": 0}


# ── lane classifiers ─────────────────────────────────────────────────────────

def test_controller_states():
    assert classify_controller(_ctrl_ok()).state == LaneState.CONNECTED.value
    assert classify_controller({"capture_state": "DISCONNECTED"}).state == LaneState.DISCONNECTED.value
    assert classify_controller({"capture_state": "NOMINAL", "host_state": "CONTESTED"}).state == LaneState.DEGRADED.value
    assert classify_controller(None).state == LaneState.UNKNOWN.value


def test_agents_states():
    assert classify_agents(_agents_ok()).state == LaneState.CONNECTED.value
    assert classify_agents({"fleet_coherent": True, "agents_total": 38, "agents_live": 30}).state == LaneState.DEGRADED.value
    assert classify_agents({"fleet_coherent": False, "agents_total": 38, "agents_live": 38}).state == LaneState.DEGRADED.value
    assert classify_agents(None).state == LaneState.UNKNOWN.value


def test_chain_killswitch_renders_degraded_not_green():
    """Load-bearing honesty test: kill-switch ON is a TRUE state and must render DEGRADED."""
    r = classify_chain({"rpc_reachable": True, "submission_paused": True})
    assert r.state == LaneState.DEGRADED.value and "kill-switch" in r.evidence
    assert classify_chain(_chain_ok()).state == LaneState.CONNECTED.value
    assert classify_chain({"rpc_reachable": False}).state == LaneState.DISCONNECTED.value


def test_operational_states():
    assert classify_operational(_oper_ok()).state == LaneState.CONNECTED.value
    assert classify_operational({"watchdog_chain_intact": False, "gic_chain_intact": True, "restarts_last_hour": 0}).state == LaneState.DISCONNECTED.value
    assert classify_operational({"watchdog_chain_intact": True, "gic_chain_intact": True, "restarts_last_hour": 5}).state == LaneState.DEGRADED.value
    assert classify_operational(None).state == LaneState.UNKNOWN.value


# ── overall verdict ──────────────────────────────────────────────────────────

def test_all_connected_is_fully_connected_and_live():
    att = assemble_connectivity(_ctrl_ok(), _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100)
    assert att.verdict == ReadinessVerdict.FULLY_CONNECTED.value
    assert att.visual_state == "live"
    ok, reason = verify_attestation(asdict(att))
    assert ok and "verified" in reason


def test_killswitch_on_makes_overall_degraded_not_live():
    att = assemble_connectivity(_ctrl_ok(), _agents_ok(),
                                {"rpc_reachable": True, "submission_paused": True}, _oper_ok(), ts_ns=100)
    assert att.verdict == ReadinessVerdict.DEGRADED.value
    assert att.visual_state == "unverified"   # the whole bridge is not "live" while paused


def test_disconnected_lane_is_partially_connected():
    att = assemble_connectivity({"capture_state": "DISCONNECTED"}, _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100)
    assert att.verdict == ReadinessVerdict.PARTIALLY_CONNECTED.value
    assert att.visual_state == "unverified"


def test_unknown_lane_degrades_overall():
    att = assemble_connectivity(_ctrl_ok(), None, _chain_ok(), _oper_ok(), ts_ns=100)
    assert att.verdict == ReadinessVerdict.DEGRADED.value


# ── honesty rails ────────────────────────────────────────────────────────────

def test_label_never_claims_zk_or_anchor():
    att = assemble_connectivity(_ctrl_ok(), _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100)
    il = att.vpm_label["integrity_label"]
    assert il["zk_verified"] is False and il["on_chain_anchor"] is False


def test_overclaim_rejected_on_verify():
    import hashlib, json
    att = asdict(assemble_connectivity({"capture_state": "DISCONNECTED"}, _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100))
    att["visual_state"] = "live"
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    att["attestation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = verify_attestation(att)
    assert ok is False and "overclaim" in reason


def test_lane_state_tamper_rejected():
    """Flip a lane to connected but keep verdict → verdict-vs-lanes consistency check catches it."""
    import hashlib, json
    att = asdict(assemble_connectivity({"capture_state": "DISCONNECTED"}, _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100))
    att["lanes"]["controller"]["state"] = "connected"     # lie about the controller
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    att["attestation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = verify_attestation(att)
    assert ok is False and "inconsistent" in reason


def test_body_tamper_rejected():
    att = asdict(assemble_connectivity(_ctrl_ok(), _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100))
    att["verdict"] = "fully_connected_lol"
    ok, reason = verify_attestation(att)
    assert ok is False


def test_deterministic():
    a = assemble_connectivity(_ctrl_ok(), _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100)
    b = assemble_connectivity(_ctrl_ok(), _agents_ok(), _chain_ok(), _oper_ok(), ts_ns=100)
    assert a.attestation_hash == b.attestation_hash


def test_four_lanes_always_present():
    att = assemble_connectivity(None, None, None, None, ts_ns=100)
    assert set(att.lanes) == set(LANE_ORDER)
    assert all(att.lanes[n]["state"] == "unknown" for n in LANE_ORDER)


def test_no_frozen_byte_tag_introduced():
    import ast, inspect
    from vapi_bridge import bridge_connectivity_aggregator as M
    tree = ast.parse(inspect.getsource(M))
    bytes_consts = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, bytes)]
    assert not any(b.startswith(b"VAPI-") for b in bytes_consts)


def test_module_is_chain_and_numpy_free():
    import ast, inspect
    from vapi_bridge import bridge_connectivity_aggregator as M
    tree = ast.parse(inspect.getsource(M))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "numpy" not in imported and "web3" not in imported
    assert imported <= {"hashlib", "json", "dataclasses", "enum", "typing", "__future__"}


def test_visual_state_vocab_subset_of_frozen_vpm():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    try:
        from vsd_vpm_wrapper import VPMVisualState
    except Exception as exc:
        import pytest
        pytest.skip(f"vsd_vpm_wrapper not importable: {exc}")
    frozen = {v.value.replace("_", "-") for v in VPMVisualState}
    assert set(VPM_VISUAL_STATES).issubset(frozen)
