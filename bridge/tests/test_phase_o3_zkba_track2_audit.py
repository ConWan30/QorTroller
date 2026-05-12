"""Phase O3-ZKBA-TRACK1 Track 2 post-ceremony audit tests (D-TRACK2-G6).

Wallet-free observability harness verification. The audit script at
scripts/zkba_post_ceremony_audit.py produces a READ-ONLY report
cross-checking local v2 bundle Merkle vs EXPECTED_MERKLES lock +
Cedar v2 lane authority matrix.

  T-ZKBA-T2-AUDIT-1  Section 1 (local Merkle) passes against current
                     v2 bundle files (Merkle matches C6 ship lock)
  T-ZKBA-T2-AUDIT-2  Section 1 fails (status="DRIFT") when v2 bundle is
                     mutated locally (tampered_bundle test fixture)
  T-ZKBA-T2-AUDIT-3  Section 3 (lane matrix) passes — full CFSS
                     invariant holds across all 12 expected (agent,
                     action, resource, effect) tuples
  T-ZKBA-T2-AUDIT-4  Section 3 detects CFSS violation when a bundle
                     is mutated to permit a forbidden lane action
  T-ZKBA-T2-AUDIT-5  Human-readable report contains expected sections
                     + G7 operator commands block
  T-ZKBA-T2-AUDIT-6  JSON report shape matches expected schema
                     (audit_id, wallet_free, sections, overall_pass)
  T-ZKBA-T2-AUDIT-7  G7 operator commands include the 5 required steps
                     (advancement / drafts / store query / FSCA / readiness)

WALLET-FREE INVARIANT: every test in this file runs WITHOUT any chain
RPC call. Section 2 (chain reads) tests are NOT in this file because
they require live RPC; they'd be covered by an integration-level test
that operator-runs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _SCRIPTS)


def _import_audit_module():
    """Load scripts/zkba_post_ceremony_audit.py as a Python module."""
    spec = importlib.util.spec_from_file_location(
        "zkba_post_ceremony_audit",
        os.path.join(_SCRIPTS, "zkba_post_ceremony_audit.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-1: Section 1 passes against current v2 bundles
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_1_section1_passes_current_bundles():
    mod = _import_audit_module()
    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings, computed = mod.section_1_local_merkles(bundle_dir)
    assert ok is True, f"Section 1 failed: {findings}"
    # Each of 3 agents has a MATCH finding
    for agent_id in mod.AGENT_ANCHOR_ORDER:
        match = [f for f in findings if f.get("agent") == agent_id]
        assert match, f"missing finding for {agent_id}"
        assert match[0]["status"] == "MATCH"
        assert computed[agent_id].lower() == mod.EXPECTED_MERKLES[agent_id].lower()


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-2: Section 1 detects bundle drift
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_2_section1_detects_drift(tmp_path):
    """Copy v2 bundles into tmp_path + mutate one to break Merkle. Verify
    Section 1 reports DRIFT for the mutated bundle."""
    mod = _import_audit_module()
    src_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    for fname in mod.AGENT_BUNDLE_FILES.values():
        src = src_dir / fname
        dst = tmp_path / fname
        dst.write_bytes(src.read_bytes())

    # Mutate the Sentry bundle: add an extra policy
    sentry_path = tmp_path / mod.AGENT_BUNDLE_FILES["anchor_sentry"]
    with open(sentry_path) as f:
        data = json.load(f)
    data["policies"].append({
        "id": "P-DRIFT",
        "effect": "permit",
        "principal": {"agentId": "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"},
        "action": "skill:tampered",
        "resource": "lane://drift/**",
    })
    with open(sentry_path, "w") as f:
        json.dump(data, f)

    ok, findings, _ = mod.section_1_local_merkles(tmp_path)
    assert ok is False
    sentry_finding = [f for f in findings if f.get("agent") == "anchor_sentry"][0]
    assert sentry_finding["status"] == "DRIFT"
    # Guardian + Curator still MATCH
    for agent_id in ("guardian", "curator"):
        f = [f for f in findings if f.get("agent") == agent_id][0]
        assert f["status"] == "MATCH", f"{agent_id} unexpectedly drifted"


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-3: Section 3 passes (CFSS matrix holds)
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_3_section3_passes_current_bundles():
    mod = _import_audit_module()
    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = mod.section_3_lane_matrix(bundle_dir)
    assert ok is True, f"CFSS violation: {[f for f in findings if f['status'] != 'OK']}"
    # All 12 rows of EXPECTED_LANE_MATRIX evaluated
    assert len(findings) == len(mod.EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-4: Section 3 detects CFSS violation
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_4_section3_detects_cfss_violation(tmp_path):
    """Mutate Sentry bundle to PERMIT zk-marketplace-listing (Curator's
    exclusive action). Verify Section 3 reports CFSS_VIOLATION."""
    mod = _import_audit_module()
    src_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    for fname in mod.AGENT_BUNDLE_FILES.values():
        src = src_dir / fname
        dst = tmp_path / fname
        dst.write_bytes(src.read_bytes())

    # Tamper: remove Sentry's forbid + add a permit for Curator's action
    sentry_path = tmp_path / mod.AGENT_BUNDLE_FILES["anchor_sentry"]
    with open(sentry_path) as f:
        data = json.load(f)
    # Remove existing forbid on tool:zk-marketplace-listing
    data["policies"] = [
        p for p in data["policies"]
        if not (p.get("action") == "tool:zk-marketplace-listing" and p.get("effect") == "forbid")
    ]
    # Add an inappropriate permit
    data["policies"].append({
        "id": "P-VIOLATION",
        "effect": "permit",
        "principal": {"agentId": "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"},
        "action": "tool:zk-marketplace-listing",
        "resource": "draft://zk_listings/*",
    })
    with open(sentry_path, "w") as f:
        json.dump(data, f)

    ok, findings = mod.section_3_lane_matrix(tmp_path)
    assert ok is False
    # Specifically: the Sentry / zk-marketplace-listing row should now show
    # actual=permit when expected=forbid
    violations = [
        f for f in findings
        if f["agent"] == "anchor_sentry"
        and f["action"] == "tool:zk-marketplace-listing"
    ]
    assert violations
    assert violations[0]["expected"] == "forbid"
    assert violations[0]["actual"] == "permit"
    assert violations[0]["status"] == "CFSS_VIOLATION"


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-5: Human report contains expected sections
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_5_human_report_shape():
    mod = _import_audit_module()
    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    s1 = mod.section_1_local_merkles(bundle_dir)
    s3 = mod.section_3_lane_matrix(bundle_dir)
    report = mod._render_human_report(
        s1=s1, s2=None, s3=s3, chain_reads_requested=False,
    )
    # Expected section headers
    assert "ZKBA Track 2 Post-Ceremony Audit (D-TRACK2-G6)" in report
    assert "Section 1 — Local v2 Bundle Merkle Verification" in report
    assert "Section 2 — On-chain reads SKIPPED" in report
    assert "Section 3 — Cedar v2 Lane Authority Matrix (CFSS)" in report
    assert "Section 4 — Overall Audit Result" in report
    assert "Section 5 — D-TRACK2-G7 Operator-Driven Commands" in report
    assert "D-TRACK2-G6 audit: PASS" in report


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-6: JSON report shape
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_6_json_report_shape():
    mod = _import_audit_module()
    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    s1 = mod.section_1_local_merkles(bundle_dir)
    s3 = mod.section_3_lane_matrix(bundle_dir)
    raw = mod._render_json_report(
        s1=s1, s2=None, s3=s3, chain_reads_requested=False,
    )
    parsed = json.loads(raw)
    assert parsed["audit_id"] == "D-TRACK2-G6"
    assert parsed["wallet_free"] is True
    assert parsed["overall_pass"] is True
    assert parsed["g7_operator_commands_required"] is True
    assert "section_1_local_merkles" in parsed["sections"]
    assert "section_3_lane_matrix" in parsed["sections"]
    # Section 2 absent when chain reads not requested
    assert "section_2_chain_reads" not in parsed["sections"]
    # Section 1 + 3 each ok
    assert parsed["sections"]["section_1_local_merkles"]["ok"] is True
    assert parsed["sections"]["section_3_lane_matrix"]["ok"] is True


# ---------------------------------------------------------------------------
# T-ZKBA-T2-AUDIT-7: G7 operator commands content
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_7_g7_commands_content():
    mod = _import_audit_module()
    commands = mod.G7_OPERATOR_COMMANDS
    # 5 required verification steps surfaced
    assert "operator-initiative-advancement" in commands
    assert "operator-agent-drafts" in commands
    assert "get_operator_agent_drafts" in commands
    assert "fsca/contradictions" in commands
    assert "Curator readiness criterion" in commands
    # References VBDIP-0002 §16 G7 explicitly
    assert "VBDIP-0002 §16 G7" in commands


# ---------------------------------------------------------------------------
# Static check: wallet-free + read-only invariant pinned
# ---------------------------------------------------------------------------
def test_t_zkba_t2_audit_static_wallet_free():
    """Audit script must NOT contain any chain-write operation. Pin the
    wallet-free invariant by greppping the source for forbidden patterns."""
    src_path = Path(_SCRIPTS) / "zkba_post_ceremony_audit.py"
    text = src_path.read_text(encoding="utf-8")
    # No chain writes
    forbidden = [
        "_send_tx",
        "set_agent_scope_root",
        "update_agent_scope_governance",
        "anchor_zkba_artifact",
        "anchor_corpus_snapshot",
        "anchor_bundle",
        "send_raw_transaction",
        "build_transaction",
        "sign_transaction",
    ]
    for pattern in forbidden:
        # `get_agent_scope_root` is OK (read-only eth_call); skip it
        if pattern == "set_agent_scope_root":
            # Different from get_agent_scope_root — need to ensure ONLY the
            # write variant is forbidden; allow get_
            assert "set_agent_scope_root" not in text, \
                "audit script contains chain-write set_agent_scope_root"
        else:
            assert pattern not in text, \
                f"audit script contains forbidden chain-write pattern: {pattern}"
