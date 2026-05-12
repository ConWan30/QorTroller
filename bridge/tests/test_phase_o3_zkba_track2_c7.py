"""Phase O3-ZKBA-TRACK1 Track 2 C7 — anchor script + chain method tests.

Plan §6 A3 deliverables. C7 ships under operator gate-by-gate
authorization for Track 2 — wallet 0 IOTX at this commit (script
exists; chain method exists; both operator-gated at runtime).

  T-ZKBA-T2-C7-1   parallel_zkba_anchor.py imports cleanly
  T-ZKBA-T2-C7-2   _check_gates() returns False without env vars set
  T-ZKBA-T2-C7-3   _check_gates() returns False when only CHAIN_SUBMISSION_PAUSED is set
                   (Gate 2 OPERATOR_ZKBA_ANCHOR_AUTHORIZED missing)
  T-ZKBA-T2-C7-4   _check_gates() returns True when BOTH env vars set
  T-ZKBA-T2-C7-5   AGENT_ANCHOR_ORDER + AGENT_BUNDLE_FILES + EXPECTED_MERKLES
                   constants match C6 ship state
  T-ZKBA-T2-C7-6   _verify_bundle_merkles() succeeds on current bundle files
  T-ZKBA-T2-C7-7   anchor_zkba_artifact method exists on ChainClient + matches
                   anchor_corpus_snapshot signature shape
  T-ZKBA-T2-C7-8   _ZKBA_DEVICE_ID constant exists + has correct SHA-256 hash
                   of b"VAPI_ZKBA_v1"
  T-ZKBA-T2-C7-9   anchor_zkba_artifact returns (None, False) when
                   kill-switch active (fail-open contract)
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_HERE = os.path.dirname(__file__)
_BRIDGE = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)


def _import_script_module():
    """Load scripts/parallel_zkba_anchor.py as a Python module."""
    spec = importlib.util.spec_from_file_location(
        "parallel_zkba_anchor",
        os.path.join(_SCRIPTS, "parallel_zkba_anchor.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-1: script imports cleanly
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_1_script_imports():
    mod = _import_script_module()
    assert hasattr(mod, "_check_gates")
    assert hasattr(mod, "_verify_bundle_merkles")
    assert hasattr(mod, "_run")
    assert hasattr(mod, "_main_cli")
    assert hasattr(mod, "AGENT_ANCHOR_ORDER")
    assert hasattr(mod, "AGENT_BUNDLE_FILES")
    assert hasattr(mod, "EXPECTED_MERKLES")
    assert hasattr(mod, "COST_BUDGET_IOTX")
    assert hasattr(mod, "SAFETY_FLOOR_IOTX")


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-2: gates fail without env vars
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_2_gates_fail_no_env(monkeypatch):
    monkeypatch.delenv("CHAIN_SUBMISSION_PAUSED", raising=False)
    monkeypatch.delenv("OPERATOR_ZKBA_ANCHOR_AUTHORIZED", raising=False)
    mod = _import_script_module()
    ok, reason = mod._check_gates()
    assert ok is False
    assert "Gate 1" in reason


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-3: gate 2 fails when only gate 1 is set
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_3_gate2_fails_alone(monkeypatch):
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.delenv("OPERATOR_ZKBA_ANCHOR_AUTHORIZED", raising=False)
    mod = _import_script_module()
    ok, reason = mod._check_gates()
    assert ok is False
    assert "Gate 2" in reason


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-4: both gates pass when both env vars set
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_4_both_gates_pass(monkeypatch):
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.setenv("OPERATOR_ZKBA_ANCHOR_AUTHORIZED", "true")
    mod = _import_script_module()
    ok, reason = mod._check_gates()
    assert ok is True
    assert "aligned" in reason.lower()


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-5: constants match C6 ship state
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_5_constants():
    mod = _import_script_module()
    # AGENT_ANCHOR_ORDER matches parallel_o2_anchor precedent
    assert mod.AGENT_ANCHOR_ORDER == ("anchor_sentry", "guardian", "curator")
    # All v2 bundles referenced
    assert mod.AGENT_BUNDLE_FILES == {
        "anchor_sentry": "anchor_sentry_o2_suggest_v2.json",
        "guardian":      "guardian_o2_suggest_v2.json",
        "curator":       "curator_o2_suggest_v2.json",
    }
    # Expected Merkle roots from C6 ship (commit 755fac33)
    assert mod.EXPECTED_MERKLES["anchor_sentry"] == (
        "0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23"
    )
    assert mod.EXPECTED_MERKLES["guardian"] == (
        "0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0"
    )
    assert mod.EXPECTED_MERKLES["curator"] == (
        "0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d"
    )


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-6: _verify_bundle_merkles succeeds on current files
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_6_verify_merkles_passes_on_current_bundles():
    mod = _import_script_module()
    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, reason, computed = mod._verify_bundle_merkles(bundle_dir)
    assert ok is True, f"merkle verification failed: {reason}"
    assert "match EXPECTED_MERKLES" in reason
    assert len(computed) == 3
    # Each computed Merkle should equal the expected
    for agent_id, expected in mod.EXPECTED_MERKLES.items():
        assert computed[agent_id].lower() == expected.lower()


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-7: anchor_zkba_artifact exists on ChainClient
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_7_anchor_zkba_artifact_method_exists():
    from vapi_bridge.chain import ChainClient
    assert hasattr(ChainClient, "anchor_zkba_artifact")
    method = getattr(ChainClient, "anchor_zkba_artifact")
    # Async method per signature mirror of anchor_corpus_snapshot
    assert asyncio.iscoroutinefunction(method)


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-8: _ZKBA_DEVICE_ID constant
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_8_zkba_device_id_constant():
    from vapi_bridge.chain import ChainClient
    assert hasattr(ChainClient, "_ZKBA_DEVICE_ID")
    # SHA-256 of b"VAPI_ZKBA_v1" (underscores per attribution convention)
    expected = hashlib.sha256(b"VAPI_ZKBA_v1").digest()
    assert ChainClient._ZKBA_DEVICE_ID == expected
    assert len(ChainClient._ZKBA_DEVICE_ID) == 32


# --------------------------------------------------------------------------
# T-ZKBA-T2-C7-9: anchor_zkba_artifact fail-open on kill-switch
# --------------------------------------------------------------------------
def test_t_zkba_t2_c7_9_anchor_zkba_artifact_killswitch_fail_open():
    """When cfg.chain_submission_paused=True (kill-switch active), the
    method MUST return (None, False) without making any RPC call."""
    from vapi_bridge.chain import ChainClient

    # Construct a minimal ChainClient-like instance with kill-switch active
    cfg = MagicMock()
    cfg.chain_submission_paused = True
    cfg.adjudication_registry_address = "0xa3A2356C90E642a7c510d0C726EC515EA720c621"

    client = ChainClient.__new__(ChainClient)
    client._cfg = cfg
    client._account = MagicMock()
    client._w3 = MagicMock()

    result = asyncio.run(client.anchor_zkba_artifact("a" * 64))
    assert result == (None, False)
