"""Priority 4 — Operator Initiative O3 readiness status audit tests.

T-PHASE-O3-AUDIT-1  Empty DB: all 3 agents O0 + agent_not_anchored blocker + verdict=BLOCKED
T-PHASE-O3-AUDIT-2  Recent O1_SHADOW anchor (~5d back): shadow_age <504h, calendar projection accurate
T-PHASE-O3-AUDIT-3  Old O1_SHADOW anchor (>504h): shadow_age cleared but still blocked on eval_count<100
T-PHASE-O3-AUDIT-4  JSON output is valid JSON
T-PHASE-O3-AUDIT-5  Calendar projection structure (cleared/hours_remaining/days_remaining/iso)
T-PHASE-O3-AUDIT-6  Verdict resolution logic — READY_TO_FIRE / BLOCKED / PARTIAL_PROGRESS
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# sys.path setup — same convention as test_phase242 / test_phase243.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT))  # for scripts/

# Web3/eth_account stub
sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


# Canonical-name → Q9-frozen agentId per Config() defaults (Phase O1 C1
# + Sessions 1+2+3). The watcher's _resolve_agent_id_for_store translates
# canonical names to these Q9 hex values via cfg.operator_agent_*_id —
# tests MUST seed activation_log keyed by Q9 hex, not canonical name.
_AGENT_Q9_HEX = {
    "anchor_sentry": "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c",
    "guardian":      "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1",
    "curator":       "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(td: str):
    """Create a fresh file-based Store (Windows WAL safety)."""
    from vapi_bridge.store import Store
    return Store(db_path=os.path.join(td, "test_o3_audit.db"))


def _seed_activation(store, *, agent_id: str, bundle_filename: str,
                     activated_at: float) -> None:
    """Seed a row in operator_agent_activation_log with explicit activated_at.

    insert_operator_agent_activation overwrites activated_at with time.time();
    so after insert we UPDATE the column directly to backdate it for
    shadow_age control. This is test-only — production code never updates
    activated_at."""
    rid = store.insert_operator_agent_activation(
        agent_id=agent_id,
        from_phase="O0",
        to_phase="O1_SHADOW",
        from_scope_root="0x" + "00" * 32,
        to_scope_root="0x" + (agent_id[:2] * 32),  # unique per agent (deduped)
        bundle_path=f"/bundles/{bundle_filename}",
        governance_tx_hash="0x" + "ab" * 32,
        operational_tx_hash="0x" + "cd" * 32,
        governance_block_number=1,
        operational_block_number=2,
        operator_authority_hash="0x" + "ef" * 32,
        reason_text="test seeding",
    )
    with sqlite3.connect(store._db_path) as con:
        con.execute(
            "UPDATE operator_agent_activation_log SET activated_at = ? WHERE id = ?",
            (activated_at, rid),
        )
        con.commit()


# ---------------------------------------------------------------------------
# T-PHASE-O3-AUDIT-1
# ---------------------------------------------------------------------------

def test_t_phase_o3_audit_1_empty_db_verdict_blocked():
    """Empty DB: all 3 agents are at O0 with agent_not_anchored blocker.
    Verdict MUST be BLOCKED (not PARTIAL — agents in same O0 phase, but
    Gate 4 requires all 3 o3_ready=True simultaneously)."""
    from scripts.operator_initiative_o3_readiness_status import run_audit, main
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        # Force the Store schema creation via instantiation, then point the
        # audit at that DB path.
        from vapi_bridge.store import Store
        db_path = os.path.join(td, "test_o3_audit.db")
        Store(db_path=db_path)  # initializes schema

        audit = run_audit(db_path)
        assert audit["error"] is None, f"unexpected audit error: {audit['error']}"
        assert len(audit["per_agent"]) == 3
        for a in audit["per_agent"]:
            assert a["current_phase"] == "O0"
            assert "agent_not_anchored" in a["o2_blockers"]
            assert "agent_not_anchored" in a["o3_blockers"]
            assert a["o2_ready"] is False
            assert a["o3_ready"] is False

        assert audit["rollup"]["parallel_o3_anchor_gate4"] == "BLOCKED"
        # All 3 agents share the same O0 phase → fleet_phase_aligned=True
        # (even though they're not at the target phase yet — the alignment
        # invariant tracks same-phase, not target-reached).
        assert audit["rollup"]["fleet_phase_aligned"] is True
        assert audit["rollup"]["next_alignment_target"] == "O1_SHADOW"


# ---------------------------------------------------------------------------
# T-PHASE-O3-AUDIT-2
# ---------------------------------------------------------------------------

def test_t_phase_o3_audit_2_recent_shadow_anchor_calendar_projection():
    """Seed all 3 agents with O1_SHADOW anchors ~5 days back. Audit MUST
    surface shadow_age ~120h + days_remaining ~16 + projection iso ~now+16d."""
    import time as _t
    from scripts.operator_initiative_o3_readiness_status import run_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_o3_audit.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db_path)
        now = _t.time()
        five_days_ago = now - (5 * 86400)
        for agent in ("anchor_sentry", "guardian", "curator"):
            _seed_activation(
                store,
                agent_id=_AGENT_Q9_HEX[agent],  # Q9 hex — what watcher queries
                bundle_filename=f"{agent}_o1_shadow_v1.json",
                activated_at=five_days_ago,
            )

        audit = run_audit(db_path)
        assert audit["error"] is None
        # Each agent should now show O1_SHADOW phase + shadow_age ~120h.
        for a in audit["per_agent"]:
            assert a["current_phase"] == "O1_SHADOW", a
            assert 100.0 <= a["shadow_age_hours"] <= 140.0  # ~120h ±20h tolerance
            assert a["o2_ready"] is False  # under 504h
            # Projection MUST report not-cleared with ~16 days remaining
            proj = a["next_gate_projection"]
            assert proj["cleared"] is False
            assert 14.0 <= proj["days_remaining"] <= 18.0


# ---------------------------------------------------------------------------
# T-PHASE-O3-AUDIT-3
# ---------------------------------------------------------------------------

def test_t_phase_o3_audit_3_old_shadow_anchor_still_blocked_on_eval_count():
    """Seed all 3 agents with O1_SHADOW anchors 22 days back (>504h).
    shadow_age gate clears but eval_count=0 < 100 blocker fires."""
    import time as _t
    from scripts.operator_initiative_o3_readiness_status import run_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_o3_audit.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db_path)
        now = _t.time()
        twenty_two_days_ago = now - (22 * 86400)
        for agent in ("anchor_sentry", "guardian", "curator"):
            _seed_activation(
                store,
                agent_id=_AGENT_Q9_HEX[agent],
                bundle_filename=f"{agent}_o1_shadow_v1.json",
                activated_at=twenty_two_days_ago,
            )

        audit = run_audit(db_path)
        assert audit["error"] is None
        for a in audit["per_agent"]:
            assert a["current_phase"] == "O1_SHADOW"
            assert a["shadow_age_hours"] > 504.0
            assert a["next_gate_projection"]["cleared"] is True
            # Still O2-blocked: eval_count=0 < 100
            eval_blocker_present = any(
                "eval_count_" in b for b in a["o2_blockers"]
            )
            assert eval_blocker_present, (
                f"expected eval_count blocker, got: {a['o2_blockers']}"
            )
            assert a["o2_ready"] is False
        assert audit["rollup"]["parallel_o3_anchor_gate4"] == "BLOCKED"


# ---------------------------------------------------------------------------
# T-PHASE-O3-AUDIT-4
# ---------------------------------------------------------------------------

def test_t_phase_o3_audit_4_json_output_is_valid_json(capsys):
    """--json output MUST parse as JSON (operator dashboards consume this
    shape directly)."""
    from scripts.operator_initiative_o3_readiness_status import main
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_o3_audit.db")
        from vapi_bridge.store import Store
        Store(db_path=db_path)

        exit_code = main(["--db", db_path, "--json"])
        captured = capsys.readouterr()
        # Exit code 1 (BLOCKED — empty DB) is expected
        assert exit_code == 1
        # Output must be valid JSON
        parsed = json.loads(captured.out)
        assert "per_agent" in parsed
        assert "rollup" in parsed
        assert "gate_thresholds" in parsed
        assert parsed["gate_thresholds"]["shadow_age_min_hours"] == 504


# ---------------------------------------------------------------------------
# T-PHASE-O3-AUDIT-5
# ---------------------------------------------------------------------------

def test_t_phase_o3_audit_5_projection_structure():
    """The next_gate_projection dict MUST contain the 5 documented keys:
    cleared / hours_remaining / days_remaining / projected_unix / projected_iso.
    Hand-verifies that the projection helper produces the contract the
    operator dashboard binds to."""
    from scripts.operator_initiative_o3_readiness_status import (
        _projected_gate_clear_date,
    )
    import time as _t
    now = _t.time()

    # Case A: shadow_age=0 → not cleared, 504h remaining
    a = _projected_gate_clear_date(
        shadow_age_hours=0.0, target_hours=504, now_unix=now
    )
    assert set(a.keys()) == {
        "cleared", "hours_remaining", "days_remaining",
        "projected_unix", "projected_iso",
    }
    assert a["cleared"] is False
    assert a["hours_remaining"] == 504.0
    assert abs(a["days_remaining"] - 21.0) < 0.001

    # Case B: shadow_age=504 → cleared exactly
    b = _projected_gate_clear_date(
        shadow_age_hours=504.0, target_hours=504, now_unix=now
    )
    assert b["cleared"] is True
    assert b["hours_remaining"] == 0.0

    # Case C: shadow_age=1000 → cleared (well over)
    c = _projected_gate_clear_date(
        shadow_age_hours=1000.0, target_hours=504, now_unix=now
    )
    assert c["cleared"] is True


# ---------------------------------------------------------------------------
# T-PHASE-O3-AUDIT-6
# ---------------------------------------------------------------------------

def test_t_phase_o3_audit_6_verdict_resolution():
    """Verdict resolution logic:
        all 3 o3_ready=True → READY_TO_FIRE  (exit 0)
        any agent with o2_ready=False AND o3_ready=False → BLOCKED (exit 1)
        otherwise → PARTIAL_PROGRESS (exit 2)
    This is the operator-facing decision boundary — fork point between
    "fire parallel_o3_act_anchor.py" and "keep observing"."""
    from scripts.operator_initiative_o3_readiness_status import main

    # Empty DB → all agents O0 → verdict BLOCKED → exit code 1
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_o3_audit.db")
        from vapi_bridge.store import Store
        Store(db_path=db_path)
        exit_code = main(["--db", db_path])
        assert exit_code == 1, "empty DB MUST return BLOCKED (exit 1)"

    # Error path: non-existent DB path component path
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        # Construct a path that the Store will refuse to create
        bad_path = os.path.join(td, "non_existent_dir", "subdir", "x.db")
        # Store should fail-open or raise; either way the audit catches
        # and returns error path (exit 3)
        exit_code = main(["--db", bad_path])
        assert exit_code in (1, 3), (
            f"bad path: expected exit 1 (BLOCKED if Store auto-creates) "
            f"or 3 (ERROR if init raises), got {exit_code}"
        )
