"""Post-O3 ceremony verification audit tests.

T-POST-O3-1   run_audit completes against empty DB; Section 1 FAIL on all 3 agents
T-POST-O3-2   _norm_hex helper handles 0x prefix + case correctly
T-POST-O3-3   _EXPECTED_O3_ACTING_MERKLES has 3 entries with valid 64-hex chars
T-POST-O3-4   Mythos variant mythos_post_o3_ceremony_audit emits CRITICAL findings on empty DB
T-POST-O3-5   Mythos variant findings carry frozen_region=True + tier=3 for CRITICAL
T-POST-O3-6   Cadence schedule has post_ceremony tier with post_o3 + operator_initiative
T-POST-O3-7   Completion manifest file exists + contains all 12 Merkle pins
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


# ---------------------------------------------------------------------------
# T-POST-O3-1
# ---------------------------------------------------------------------------

def test_t_post_o3_1_empty_db_section_1_fail():
    """Empty DB → Section 1 reports 3 missing activations + verdict
    SECTION_1_FAIL + exit code 1."""
    import operator_initiative_post_o3_audit as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        audit = asyncio.run(mod.run_audit(
            db_path=db, include_chain_reads=False, repo_root=ROOT,
        ))
        s1 = audit["sections"]["section_1"]
        assert s1["all_pass"] is False
        for agent in ("anchor_sentry", "guardian", "curator"):
            entry = s1["per_agent"][agent]
            assert entry["pass"] is False
            assert entry["checks"]["activation_row_exists"] is False
        assert audit["verdict"] in ("SECTION_1_FAIL",)
        assert audit["exit_code"] == 1


# ---------------------------------------------------------------------------
# T-POST-O3-2
# ---------------------------------------------------------------------------

def test_t_post_o3_2_norm_hex():
    """_norm_hex strips 0x + lowercases."""
    import operator_initiative_post_o3_audit as mod
    assert mod._norm_hex("0xABCD") == "abcd"
    assert mod._norm_hex("0xabcd") == "abcd"
    assert mod._norm_hex("abcd") == "abcd"
    assert mod._norm_hex("") == ""
    assert mod._norm_hex(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T-POST-O3-3
# ---------------------------------------------------------------------------

def test_t_post_o3_3_expected_merkles_shape():
    """_EXPECTED_O3_ACTING_MERKLES has 3 agents + each merkle is 64 hex chars."""
    import operator_initiative_post_o3_audit as mod
    assert set(mod._EXPECTED_O3_ACTING_MERKLES.keys()) == {
        "anchor_sentry", "guardian", "curator"
    }
    for agent, merkle in mod._EXPECTED_O3_ACTING_MERKLES.items():
        assert merkle.startswith("0x"), f"{agent}: missing 0x prefix"
        assert len(merkle) == 66, f"{agent}: expected 66 chars (0x + 64), got {len(merkle)}"
        # All chars after 0x must be valid hex
        int(merkle, 16)


# ---------------------------------------------------------------------------
# T-POST-O3-4
# ---------------------------------------------------------------------------

def test_t_post_o3_4_mythos_variant_emits_critical_findings():
    """Mythos-Post-O3 variant against empty DB → 3 CRITICAL findings
    (one per missing agent activation)."""
    from vapi_bridge.mythos_variants import mythos_post_o3_ceremony_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        findings = asyncio.run(mythos_post_o3_ceremony_audit(
            repo_root=ROOT, db_path=db, include_chain_reads=False,
        ))
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 3, (
            f"expected 3 CRITICAL findings (one per agent); got {len(criticals)}. "
            f"All findings: {[(f.severity, f.description[:60]) for f in findings]}"
        )
        agent_names_found = set()
        for f in criticals:
            for name in ("anchor_sentry", "guardian", "curator"):
                if name in (f.description or ""):
                    agent_names_found.add(name)
        assert agent_names_found == {"anchor_sentry", "guardian", "curator"}


# ---------------------------------------------------------------------------
# T-POST-O3-5
# ---------------------------------------------------------------------------

def test_t_post_o3_5_critical_findings_are_frozen_region_tier_3():
    """Every CRITICAL Mythos-Post-O3 finding MUST carry frozen_region=True
    + fix_authority_tier=3 (Mythos never auto-fixes post-ceremony drift)."""
    from vapi_bridge.mythos_variants import mythos_post_o3_ceremony_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        findings = asyncio.run(mythos_post_o3_ceremony_audit(
            repo_root=ROOT, db_path=db, include_chain_reads=False,
        ))
        critical = [f for f in findings if f.severity == "CRITICAL"]
        for f in critical:
            assert f.frozen_region is True, (
                f"CRITICAL finding {f.coherence_id} has frozen_region=False"
            )
            assert f.fix_authority_tier == 3, (
                f"CRITICAL finding {f.coherence_id} has tier {f.fix_authority_tier}"
            )


# ---------------------------------------------------------------------------
# T-POST-O3-6
# ---------------------------------------------------------------------------

def test_t_post_o3_6_cadence_schedule_post_ceremony():
    """MYTHOS_CADENCE_SCHEDULE must have a 'post_ceremony' tier listing
    post_o3 + operator_initiative."""
    from vapi_bridge.mythos_cadence_engine import MYTHOS_CADENCE_SCHEDULE
    assert "post_ceremony" in MYTHOS_CADENCE_SCHEDULE, (
        f"schedule keys: {list(MYTHOS_CADENCE_SCHEDULE.keys())}"
    )
    assert "post_o3" in MYTHOS_CADENCE_SCHEDULE["post_ceremony"]
    assert "operator_initiative" in MYTHOS_CADENCE_SCHEDULE["post_ceremony"]


# ---------------------------------------------------------------------------
# T-POST-O3-7
# ---------------------------------------------------------------------------

def test_t_post_o3_7_completion_manifest_exists_with_merkle_pins():
    """The completion manifest file must exist + contain all 12 Cedar
    bundle Merkle pins (4 lifecycle stages × 3 agents = 12)."""
    manifest = ROOT / "wiki" / "methodology" / "operator_initiative_completion_manifest.md"
    assert manifest.is_file(), f"manifest missing at {manifest}"
    text = manifest.read_text(encoding="utf-8")
    # 12 Merkle roots from CLAUDE.md NOTE history
    merkle_pins = [
        # O1 SHADOW
        "0xebe899279b230ff5d71db22dc4b80282c810ff5bd1a9d249db6e6d309af52e41",
        "0x46807e13dd1c81cefa784ab8b30f8cdcaefd60697de921aae46ac24dac000a50",
        "0x44f89d0a05e7594741f7a06a1c4ca817d58396ad41b22b0eb5d0b5ce4be88ae6",
        # O2 SUGGEST v1
        "0x1af7854a08de4ce26ba7aeb5a6c215b3ae15057b3d3e665eb48db5044bfc2609",
        "0x70ccf51f36d6a3812181004b20668a68e936e8d975ebd9ac217d13743a82bdab",
        "0xeb400a5c9b410c6f3035a595e2c36dee915f6b2447f822c72c46b164ccd5daa9",
        # O2 SUGGEST v2
        "0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23",
        "0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0",
        "0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d",
        # O3 ACTING
        "0xc0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878",
        "0x6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225",
        "0xd9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24",
    ]
    for pin in merkle_pins:
        assert pin in text, f"manifest missing Merkle pin {pin[:20]}..."
    # And the 3 agent Q9 hexes
    for q9 in (
        "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c",
        "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1",
        "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8",
    ):
        assert q9 in text, f"manifest missing Q9 hex {q9[:20]}..."
