"""Tests for VSD-emits-VPM Integrity Label (pure stdlib) + frozen-vocab subset + MCP tool reg."""
from __future__ import annotations

import sys
from pathlib import Path

_VAULT = Path(__file__).resolve().parent.parent.parent / "vsd-vault"
sys.path.insert(0, str(_VAULT / ".vsd"))

import vsd_vpm_label as L  # noqa: E402

_HEAD = "ab" * 32


def test_live_only_when_both_pass_and_committed():
    assert L.derive_vsd_visual_state(True, True, False) == "live"
    assert L.derive_vsd_visual_state(True, True, True) == "dry-run"
    assert L.derive_vsd_visual_state(False, True, False) == "unverified"
    assert L.derive_vsd_visual_state(True, False, False) == "unverified"
    assert L.derive_vsd_visual_state(False, False, True) == "unverified"  # fail dominates dry-run


def test_label_builds_and_verifies():
    lab = L.build_vsd_vpm_label(sic_head_hex=_HEAD, harness_pass=True, pv_ci_pass=True,
                                dry_run=False, ts_ns=100)
    ok, reason = L.verify_vsd_vpm_label(lab)
    assert ok and lab["visual_state"] == "live" and "verified" in reason
    assert lab["integrity_label"]["proof_weight"] == L.PROOF_WEIGHT_CHAIN_ONLY


def test_deterministic():
    a = L.build_vsd_vpm_label(sic_head_hex=_HEAD, harness_pass=True, pv_ci_pass=True,
                              dry_run=False, ts_ns=100)
    b = L.build_vsd_vpm_label(sic_head_hex=_HEAD, harness_pass=True, pv_ci_pass=True,
                              dry_run=False, ts_ns=100)
    assert a["label_hash"] == b["label_hash"]


def test_overclaim_rejected():
    """The load-bearing anti-overclaim check: hand-editing visual_state to `live` over a failed
    cycle must fail verify (visual_state must equal the honesty-derived value)."""
    lab = L.build_vsd_vpm_label(sic_head_hex=_HEAD, harness_pass=False, pv_ci_pass=True,
                                dry_run=False, ts_ns=100)
    assert lab["visual_state"] == "unverified"
    lab["visual_state"] = "live"                    # attacker paints it live
    # recompute hash so the body-tamper check doesn't fire first — isolate the overclaim check
    import hashlib, json
    body = {k: v for k, v in lab.items() if k != "label_hash"}
    lab["label_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = L.verify_vsd_vpm_label(lab)
    assert ok is False and "overclaim" in reason


def test_body_tamper_rejected():
    lab = L.build_vsd_vpm_label(sic_head_hex=_HEAD, harness_pass=True, pv_ci_pass=True,
                                dry_run=False, ts_ns=100)
    lab["sic_head_hex"] = "cd" * 32                  # tamper, keep old hash
    ok, reason = L.verify_vsd_vpm_label(lab)
    assert ok is False and "tamper" in reason


def test_label_never_claims_zk_or_anchor():
    lab = L.build_vsd_vpm_label(sic_head_hex=_HEAD, harness_pass=True, pv_ci_pass=True,
                                dry_run=False, ts_ns=100)
    assert lab["integrity_label"]["zk_verified"] is False
    assert lab["integrity_label"]["on_chain_anchor"] is False
    assert lab["anchor_status"] == "none"


def test_forecast_clean_and_rising():
    clean = L.forecast_drift([{"mythos_drift": 0, "harness_pass": True, "pv_ci_pass": True}])
    assert clean["forecast"] == "clean-projected"
    rising = L.forecast_drift([{"mythos_drift": 0}, {"mythos_drift": 1}, {"mythos_drift": 2}])
    assert rising["trend"] == "rising" and rising["forecast"] == "drift-likely-next-cycle"
    empty = L.forecast_drift([])
    assert empty["forecast"] == "unknown"


def test_module_is_dependency_free():
    """The label module must stay pure stdlib so the ambient MCP verifier works without bridge.
    Check the actual import statements (not comment text, which legitimately mentions the deps)."""
    import ast, inspect
    tree = ast.parse(inspect.getsource(L))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "cryptography" not in imported and "vapi_bridge" not in imported
    assert imported <= {"hashlib", "json", "__future__"}


def test_vocab_is_subset_of_frozen_vpm():
    """Drift guard: our mirrored vocabulary must remain a subset of the FROZEN VPMVisualState
    enum (normalized for the underscore/hyphen skew between wrapper and artifact layers)."""
    sys.path.insert(0, str(_VAULT.parent / "scripts"))
    try:
        from vsd_vpm_wrapper import VPMVisualState
    except Exception as exc:
        import pytest
        pytest.skip(f"vsd_vpm_wrapper not importable (no bridge env): {exc}")
    frozen = {v.value.replace("_", "-") for v in VPMVisualState}
    assert set(L.VPM_VISUAL_STATES).issubset(frozen)


def test_mcp_vpm_tool_registered():
    import importlib
    sys.path.insert(0, str(_VAULT.parent / "vapi-mcp"))
    try:
        u = importlib.import_module("unified_server")
    except Exception as exc:
        import pytest
        pytest.skip(f"unified_server import unavailable: {exc}")
    assert "vsd_vpm_label" in u.TOOLS
