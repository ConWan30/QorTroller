"""Mythos Operator-Initiative audit variant tests (operator-authorized
extension 2026-05-15).

These tests exercise the audit under deliberate perturbations to prove it
is NOT vacuous — i.e., each of the 5 check families correctly fires a
finding when its invariant is violated.

T-MYTHOS-OPINIT-1  Healthy repo → 0 findings (positive case)
T-MYTHOS-OPINIT-2  Missing bundle file → CRITICAL Family-1 finding
T-MYTHOS-OPINIT-3  Bundle with wrong agent_id → CRITICAL Family-2 finding (Q9 drift)
T-MYTHOS-OPINIT-4  Bundle with mutated policies → CRITICAL Family-3 finding (Merkle drift)
T-MYTHOS-OPINIT-5  Anchor script with wrong AGENT_ANCHOR_ORDER → HIGH Family-4 finding
T-MYTHOS-OPINIT-6  Missing architect attestation → MEDIUM Family-5 finding
T-MYTHOS-OPINIT-7  All findings carry frozen_region=True (Mythos NEVER auto-fixes)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _copy_minimal_initiative_tree(dst_root: Path) -> Path:
    """Copy the bundle dir + parallel anchor scripts + architect attestation
    + VBDIP-0001 manifest dir from the real repo into a temp tree. The
    audit-under-test then runs against the temp tree, so each test can
    perturb in isolation without touching the real repo files."""
    real = ROOT
    # Cedar bundles
    src_bundles = real / "bridge" / "vapi_bridge" / "cedar_bundles"
    dst_bundles = dst_root / "bridge" / "vapi_bridge" / "cedar_bundles"
    dst_bundles.mkdir(parents=True, exist_ok=True)
    for f in src_bundles.glob("*.json"):
        shutil.copy(f, dst_bundles / f.name)

    # cedar_parser.py (audit imports vapi_bridge.cedar_parser)
    src_parser = real / "bridge" / "vapi_bridge" / "cedar_parser.py"
    if src_parser.is_file():
        shutil.copy(src_parser, dst_bundles.parent / "cedar_parser.py")

    # Parallel anchor scripts
    src_scripts = real / "scripts"
    dst_scripts = dst_root / "scripts"
    dst_scripts.mkdir(parents=True, exist_ok=True)
    for fname in ("parallel_o2_anchor.py", "parallel_o3_act_anchor.py"):
        s = src_scripts / fname
        if s.is_file():
            shutil.copy(s, dst_scripts / fname)

    # Methodology overlap
    src_eval = real / "vsd-vault" / "eval" / "architect_key_attestation.json"
    dst_eval = dst_root / "vsd-vault" / "eval"
    dst_eval.mkdir(parents=True, exist_ok=True)
    if src_eval.is_file():
        shutil.copy(src_eval, dst_eval / src_eval.name)
    src_manifests = real / "vsd-vault" / "manifests" / "proposals-VBDIP-0001"
    if src_manifests.is_dir():
        dst_manifests = dst_root / "vsd-vault" / "manifests" / "proposals-VBDIP-0001"
        dst_manifests.mkdir(parents=True, exist_ok=True)
        for f in src_manifests.glob("*"):
            if f.is_file():
                shutil.copy(f, dst_manifests / f.name)

    return dst_root


# ----- T-MYTHOS-OPINIT-1 (healthy positive case) -----

def test_t_mythos_opinit_1_healthy_repo_zero_findings():
    """Against the live repo, the audit MUST return 0 findings — proving
    today's Operator Initiative is fully synchronized."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    findings = asyncio.run(mythos_operator_initiative_audit())
    assert findings == [], (
        f"Expected 0 findings against the healthy live repo; got "
        f"{len(findings)}: {[f.coherence_id for f in findings]}"
    )


# ----- T-MYTHOS-OPINIT-2 (Family 1: missing bundle) -----

def test_t_mythos_opinit_2_missing_bundle_critical():
    """Delete one bundle file → audit MUST surface CRITICAL Family-1 finding."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = _copy_minimal_initiative_tree(Path(td))
        target = root / "bridge" / "vapi_bridge" / "cedar_bundles" / "curator_o3_acting_v1.json"
        target.unlink()
        findings = asyncio.run(mythos_operator_initiative_audit(repo_root=root))
        crit = [
            f for f in findings
            if f.severity == "CRITICAL"
            and "curator_o3_acting_v1" in (f.description or "")
            and "missing" in (f.description or "").lower()
        ]
        assert crit, f"expected missing-bundle CRITICAL; got {[(f.severity, f.description[:60]) for f in findings]}"
        assert all(f.frozen_region for f in crit)
        assert all(f.fix_authority_tier == 3 for f in crit)


# ----- T-MYTHOS-OPINIT-3 (Family 2: Q9 hex drift) -----

def test_t_mythos_opinit_3_q9_hex_drift_critical():
    """Mutate the agent_id field in one bundle → CRITICAL Q9 drift finding."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = _copy_minimal_initiative_tree(Path(td))
        target = root / "bridge" / "vapi_bridge" / "cedar_bundles" / "anchor_sentry_o1_shadow_v1.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["agent_id"] = "0x" + "ff" * 32   # drift
        target.write_text(json.dumps(payload), encoding="utf-8")
        findings = asyncio.run(mythos_operator_initiative_audit(repo_root=root))
        q9_findings = [
            f for f in findings
            if f.severity == "CRITICAL" and "Q9 HEX DRIFT" in (f.description or "")
        ]
        assert q9_findings, (
            f"expected Q9 drift CRITICAL; got: {[(f.severity, f.description[:60]) for f in findings]}"
        )
        # Merkle drift ALSO fires (mutating agent_id changes canonical bytes)
        merkle_findings = [
            f for f in findings if "MERKLE DRIFT" in (f.description or "")
        ]
        assert merkle_findings, "expected Merkle drift to also fire (mutated agent_id → canonical bytes changed)"


# ----- T-MYTHOS-OPINIT-4 (Family 3: Merkle drift only) -----

def test_t_mythos_opinit_4_merkle_drift_critical():
    """Add a policy to a bundle (but keep agent_id intact) → CRITICAL
    Merkle drift, no Q9 drift."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = _copy_minimal_initiative_tree(Path(td))
        target = root / "bridge" / "vapi_bridge" / "cedar_bundles" / "guardian_o1_shadow_v1.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        # Add a benign extra policy (canonical bytes change → Merkle changes)
        payload["policies"].append({
            "id": "P-INJECTED",
            "effect": "permit",
            "principal": {"agentId": payload["agent_id"]},
            "action": "skill:read",
            "resource": "lane://wiki/**",
        })
        target.write_text(json.dumps(payload), encoding="utf-8")
        findings = asyncio.run(mythos_operator_initiative_audit(repo_root=root))
        merkle_only = [
            f for f in findings
            if f.severity == "CRITICAL" and "MERKLE DRIFT" in (f.description or "")
        ]
        assert merkle_only, (
            f"expected Merkle drift CRITICAL; got: {[(f.severity, f.description[:60]) for f in findings]}"
        )
        # Q9 drift should NOT fire (we kept the agent_id unchanged)
        q9_findings = [f for f in findings if "Q9 HEX DRIFT" in (f.description or "")]
        assert q9_findings == [], (
            f"Q9 drift should not fire when agent_id is unchanged; got: {[f.description[:60] for f in q9_findings]}"
        )


# ----- T-MYTHOS-OPINIT-5 (Family 4: anchor script order drift) -----

def test_t_mythos_opinit_5_anchor_order_drift_high():
    """Mutate AGENT_ANCHOR_ORDER in parallel_o2_anchor.py → HIGH finding."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = _copy_minimal_initiative_tree(Path(td))
        target = root / "scripts" / "parallel_o2_anchor.py"
        src = target.read_text(encoding="utf-8")
        # Swap two agents in the tuple → drift
        perturbed = src.replace(
            'AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")',
            'AGENT_ANCHOR_ORDER = ("guardian", "anchor_sentry", "curator")',
            1,
        )
        target.write_text(perturbed, encoding="utf-8")
        findings = asyncio.run(mythos_operator_initiative_audit(repo_root=root))
        order_findings = [
            f for f in findings
            if f.severity == "HIGH"
            and "AGENT_ANCHOR_ORDER" in (f.description or "")
        ]
        assert order_findings, (
            f"expected HIGH order-drift; got: {[(f.severity, f.description[:60]) for f in findings]}"
        )


# ----- T-MYTHOS-OPINIT-6 (Family 5: methodology overlap gap) -----

def test_t_mythos_opinit_6_missing_architect_attestation_medium():
    """Remove the architect attestation file → MEDIUM methodology finding."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = _copy_minimal_initiative_tree(Path(td))
        attest = root / "vsd-vault" / "eval" / "architect_key_attestation.json"
        if attest.is_file():
            attest.unlink()
        findings = asyncio.run(mythos_operator_initiative_audit(repo_root=root))
        meth = [
            f for f in findings
            if "Architect Ed25519 attestation" in (f.description or "")
        ]
        assert meth, (
            f"expected architect-attestation MEDIUM; got: {[(f.severity, f.description[:60]) for f in findings]}"
        )
        assert all(f.severity == "MEDIUM" for f in meth)
        assert all(f.frozen_region for f in meth)


# ----- T-MYTHOS-OPINIT-7 (universal frozen_region=True invariant) -----

def test_t_mythos_opinit_7_all_findings_frozen_region_true():
    """Mythos NEVER auto-fixes Operator Initiative state — every finding
    that touches protocol-layer surfaces (bundles / scripts / methodology)
    MUST carry frozen_region=True so the store layer's INV-MYTHOS-FROZEN-
    PROTECTION-001 forces tier=3 read-only."""
    from vapi_bridge.mythos_variants import mythos_operator_initiative_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = _copy_minimal_initiative_tree(Path(td))
        # Apply 3 perturbations simultaneously to exercise multiple families.
        (root / "bridge" / "vapi_bridge" / "cedar_bundles" / "curator_o3_acting_v1.json").unlink()
        target = root / "bridge" / "vapi_bridge" / "cedar_bundles" / "anchor_sentry_o1_shadow_v1.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["agent_id"] = "0x" + "ff" * 32
        target.write_text(json.dumps(payload), encoding="utf-8")
        script = root / "scripts" / "parallel_o3_act_anchor.py"
        script.write_text(
            script.read_text(encoding="utf-8").replace(
                'AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")',
                'AGENT_ANCHOR_ORDER = ("curator", "guardian", "anchor_sentry")',
                1,
            ),
            encoding="utf-8",
        )

        findings = asyncio.run(mythos_operator_initiative_audit(repo_root=root))
        assert len(findings) >= 3, (
            f"expected at least 3 findings from 3 perturbations; got "
            f"{len(findings)}"
        )
        # All protocol-layer findings (severity CRITICAL or HIGH) MUST be frozen_region
        protocol_findings = [
            f for f in findings if f.severity in ("CRITICAL", "HIGH")
        ]
        for f in protocol_findings:
            assert f.frozen_region is True, (
                f"finding {f.coherence_id} severity={f.severity} has "
                f"frozen_region=False — violates INV-MYTHOS-FROZEN-PROTECTION-001"
            )
            assert f.fix_authority_tier == 3, (
                f"finding {f.coherence_id} has fix_authority_tier="
                f"{f.fix_authority_tier} but MUST be 3 (Mythos never "
                f"auto-fixes Operator Initiative state)"
            )
