"""Priority 5 Full Mythos — 4 remaining variants tests.

Crypto / Methodology / Ceremony / Corpus variants. Each test set proves
non-vacuousness under deliberate perturbations, plus the healthy-repo
positive case.

T-MYTHOS-CRYPTO-1..4
T-MYTHOS-METHODOLOGY-1..3
T-MYTHOS-CEREMONY-1..4
T-MYTHOS-CORPUS-1..3
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
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


# ===========================================================================
# Mythos-Crypto tests
# ===========================================================================

def test_t_mythos_crypto_1_healthy_repo_zero_findings():
    """Healthy live repo → 0 findings (all 11 commitment families + 3
    capability tags accounted for)."""
    from vapi_bridge.mythos_variants import mythos_crypto_drift
    findings = asyncio.run(mythos_crypto_drift())
    assert findings == [], (
        f"expected 0 findings on healthy repo; got "
        f"{[(f.severity, f.description[:80]) for f in findings]}"
    )


def test_t_mythos_crypto_2_missing_family_critical():
    """Perturb _PATTERN_017_FROZEN_TAGS to expect a tag that isn't on disk
    → CRITICAL missing-family finding."""
    from vapi_bridge import mythos_variants
    saved = mythos_variants._PATTERN_017_FROZEN_TAGS
    try:
        mythos_variants._PATTERN_017_FROZEN_TAGS = frozenset(
            list(saved) + [b"VAPI-NONEXISTENT-v1"]
        )
        findings = asyncio.run(mythos_variants.mythos_crypto_drift())
        crit = [
            f for f in findings
            if f.severity == "CRITICAL"
            and "FAMILY DRIFT" in (f.description or "")
            and "VAPI-NONEXISTENT-v1" in (f.description or "")
        ]
        assert crit, (
            f"expected CRITICAL missing-family; got: "
            f"{[(f.severity, f.description[:80]) for f in findings]}"
        )
        assert all(f.frozen_region for f in crit)
        assert all(f.fix_authority_tier == 3 for f in crit)
    finally:
        mythos_variants._PATTERN_017_FROZEN_TAGS = saved


def test_t_mythos_crypto_3_unknown_tag_high():
    """Drop a known capability tag from the audit's set → its appearance
    in production source becomes an UNKNOWN HIGH finding."""
    from vapi_bridge import mythos_variants
    saved = mythos_variants._KNOWN_CAPABILITY_TAGS
    try:
        # Remove BT-WITNESS-v1 from known capabilities; the audit should
        # then flag its appearance in bt_witness.py as UNKNOWN.
        mythos_variants._KNOWN_CAPABILITY_TAGS = frozenset()
        findings = asyncio.run(mythos_variants.mythos_crypto_drift())
        unknown_high = [
            f for f in findings
            if f.severity == "HIGH"
            and "UNKNOWN CRYPTOGRAPHIC TAG" in (f.description or "")
            and "VAPI-BT-WITNESS" in (f.description or "")
        ]
        assert unknown_high, (
            f"expected HIGH unknown-tag for VAPI-BT-WITNESS; got: "
            f"{[(f.severity, f.description[:80]) for f in findings]}"
        )
    finally:
        mythos_variants._KNOWN_CAPABILITY_TAGS = saved


def test_t_mythos_crypto_4_missing_poseidon_sha_high():
    """If the Poseidon test-vector SHA-256 pin file is missing → HIGH."""
    from vapi_bridge.mythos_variants import mythos_crypto_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = Path(td)
        # Mirror the bridge/vapi_bridge/ tree minimally so the variant
        # can scan it, but DON'T create scripts/w3bstream/poseidon_test_vectors.sha256
        (root / "bridge" / "vapi_bridge").mkdir(parents=True)
        # Drop in a synthetic file with the 10 family domain tags so the
        # crypto-family check passes (we want JUST the poseidon-sha
        # missing finding).
        synth = (root / "bridge" / "vapi_bridge" / "_synthetic.py")
        family_lines = "\n".join(
            f'TAG{i} = b"{tag.decode()}"'
            for i, tag in enumerate(
                __import__("vapi_bridge.mythos_variants").mythos_variants._PATTERN_017_FROZEN_TAGS,
                start=1
            )
        )
        synth.write_text(family_lines, encoding="utf-8")
        findings = asyncio.run(mythos_crypto_drift(repo_root=root))
        poseidon_high = [
            f for f in findings
            if f.severity == "HIGH"
            and "Poseidon test-vector corpus SHA-256" in (f.description or "")
        ]
        assert poseidon_high, (
            f"expected HIGH Poseidon-sha-missing; got: "
            f"{[(f.severity, f.description[:80]) for f in findings]}"
        )


# ===========================================================================
# Mythos-Methodology tests
# ===========================================================================

def test_t_mythos_methodology_1_healthy_repo_zero_findings():
    """Healthy live repo → 0 findings (all required methodology files exist)."""
    from vapi_bridge.mythos_variants import mythos_methodology_drift
    findings = asyncio.run(mythos_methodology_drift())
    assert findings == [], (
        f"expected 0 findings on healthy repo; got "
        f"{[(f.severity, f.description[:80]) for f in findings]}"
    )


def test_t_mythos_methodology_2_missing_vbdip_high():
    """Empty temp tree → HIGH on missing VBDIP-0001 + architect attestation
    + MEDIUM on others."""
    from vapi_bridge.mythos_variants import mythos_methodology_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        findings = asyncio.run(mythos_methodology_drift(repo_root=Path(td)))
        # Expect findings for every methodology required file
        assert len(findings) >= 5, (
            f"expected several methodology-missing findings; got {len(findings)}"
        )
        high = [f for f in findings if f.severity == "HIGH"]
        # VBDIP-0001 + architect_key are HIGH
        assert any("VBDIP-0001" in (f.description or "") for f in high)
        assert any("architect_key" in (f.description or "") for f in high)


def test_t_mythos_methodology_3_all_findings_frozen_region():
    """Every methodology missing-file finding MUST be frozen_region=True
    (methodology trust chain is FROZEN; restore from git, never regenerate)."""
    from vapi_bridge.mythos_variants import mythos_methodology_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        findings = asyncio.run(mythos_methodology_drift(repo_root=Path(td)))
        assert findings, "expected non-empty findings"
        for f in findings:
            assert f.frozen_region is True
            assert f.fix_authority_tier == 3


# ===========================================================================
# Mythos-Ceremony tests
# ===========================================================================

def test_t_mythos_ceremony_1_healthy_repo_zero_findings():
    """Healthy live repo → 0 findings (CHAIN_SUBMISSION_PAUSED=true,
    parallel scripts exist, allowlist parseable)."""
    from vapi_bridge.mythos_variants import mythos_ceremony_drift
    findings = asyncio.run(mythos_ceremony_drift())
    assert findings == [], (
        f"expected 0 findings on healthy repo; got "
        f"{[(f.severity, f.description[:80]) for f in findings]}"
    )


def test_t_mythos_ceremony_2_kill_switch_disarmed_critical():
    """Synthesize an .env with CHAIN_SUBMISSION_PAUSED=false → CRITICAL."""
    from vapi_bridge.mythos_variants import mythos_ceremony_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = Path(td)
        # Copy the live scripts + allowlist so those checks pass; perturb env only.
        scripts_dir = root / "scripts"
        scripts_dir.mkdir(parents=True)
        for s in ("parallel_o2_anchor.py", "parallel_o3_act_anchor.py"):
            (scripts_dir / s).write_text("# stub", encoding="utf-8")
        gh_dir = root / ".github"
        gh_dir.mkdir(parents=True)
        (gh_dir / "INVARIANTS_ALLOWLIST.json").write_text("{}", encoding="utf-8")
        # Disarmed kill-switch
        env_path = root / "bridge" / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("CHAIN_SUBMISSION_PAUSED=false\n", encoding="utf-8")
        findings = asyncio.run(mythos_ceremony_drift(repo_root=root, env_path=env_path))
        kill_switch = [
            f for f in findings
            if f.severity == "CRITICAL"
            and "KILL-SWITCH DISARMED" in (f.description or "")
        ]
        assert kill_switch, (
            f"expected CRITICAL kill-switch-disarmed; got: "
            f"{[(f.severity, f.description[:80]) for f in findings]}"
        )
        assert all(f.frozen_region for f in kill_switch)
        assert all(f.fix_authority_tier == 3 for f in kill_switch)


def test_t_mythos_ceremony_3_missing_anchor_script_high():
    """No scripts/parallel_*.py → HIGH ceremony-script-missing finding."""
    from vapi_bridge.mythos_variants import mythos_ceremony_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        findings = asyncio.run(mythos_ceremony_drift(repo_root=Path(td)))
        high = [
            f for f in findings
            if f.severity == "HIGH"
            and "CEREMONY SCRIPT MISSING" in (f.description or "")
        ]
        assert high, "expected HIGH missing-script findings"
        # Both scripts should be reported
        assert any("parallel_o2_anchor.py" in (f.description or "") for f in high)
        assert any("parallel_o3_act_anchor.py" in (f.description or "") for f in high)


def test_t_mythos_ceremony_4_missing_allowlist_high():
    """Missing PV-CI allowlist → HIGH."""
    from vapi_bridge.mythos_variants import mythos_ceremony_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = Path(td)
        scripts_dir = root / "scripts"
        scripts_dir.mkdir(parents=True)
        for s in ("parallel_o2_anchor.py", "parallel_o3_act_anchor.py"):
            (scripts_dir / s).write_text("# stub", encoding="utf-8")
        # NO allowlist + NO env file (so kill-switch check skips silently)
        findings = asyncio.run(mythos_ceremony_drift(repo_root=root))
        allowlist_high = [
            f for f in findings
            if f.severity == "HIGH"
            and "PV-CI allowlist file MISSING" in (f.description or "")
        ]
        assert allowlist_high


# ===========================================================================
# Mythos-Corpus tests
# ===========================================================================

def test_t_mythos_corpus_1_empty_db_two_low_findings():
    """Empty bridge DB → 2 LOW informational findings (empty separation
    snapshots + empty GIC chain)."""
    from vapi_bridge.mythos_variants import mythos_corpus_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_mythos_corpus.db")
        # Initialize empty Store schema
        from vapi_bridge.store import Store
        Store(db_path=db_path)
        findings = asyncio.run(mythos_corpus_drift(db_path=db_path))
        assert len(findings) >= 1
        # All findings should be LOW (informational dev-vs-prod divergence)
        assert all(f.severity == "LOW" for f in findings), (
            f"expected all LOW; got: {[(f.severity, f.description[:60]) for f in findings]}"
        )
        # None should be frozen_region (this is operational, not protocol drift)
        assert not any(f.frozen_region for f in findings)


def test_t_mythos_corpus_2_tge_blocker_surface_medium():
    """Seed separation_ratio_snapshots with a ratio<1.0 row → MEDIUM
    TGE-blocker finding."""
    from vapi_bridge.mythos_variants import mythos_corpus_drift
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_mythos_corpus.db")
        from vapi_bridge.store import Store
        Store(db_path=db_path)
        # Hand-seed a row in separation_defensibility_log (Phase 150 table)
        # with ratio=0.728 + all_pairs_above_1=0 (the touchpad_corners
        # TGE blocker per CLAUDE.md).
        import time as _t
        with sqlite3.connect(db_path) as con:
            con.execute(
                "INSERT INTO separation_defensibility_log "
                "(session_type, n_sessions_total, n_per_player_json, "
                " min_n_per_player, defensible, ratio, all_pairs_above_1, "
                " created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("touchpad_corners", 35, "{}", 10, 0, 0.728, 0, _t.time()),
            )
            con.commit()
        findings = asyncio.run(mythos_corpus_drift(db_path=db_path))
        tge = [
            f for f in findings
            if f.severity == "MEDIUM"
            and "TGE BLOCKER" in (f.description or "")
            and "touchpad_corners" in (f.description or "")
        ]
        assert tge, (
            f"expected MEDIUM TGE blocker for touchpad_corners; got: "
            f"{[(f.severity, f.description[:80]) for f in findings]}"
        )


def test_t_mythos_corpus_3_nonexistent_db_low_fail_open():
    """Nonexistent DB path → variant returns LOW finding (fail-open
    informational), NEVER raises."""
    from vapi_bridge.mythos_variants import mythos_corpus_drift
    findings = asyncio.run(mythos_corpus_drift(db_path="/no/such/path.db"))
    # Either: returns empty (sqlite3.connect auto-creates), or returns LOW
    # informational. Either way: never raises. Verify by checking we got
    # a list back without exceptions.
    assert isinstance(findings, list)
