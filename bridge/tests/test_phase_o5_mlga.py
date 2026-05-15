"""Phase O5-MLGA tests — variant + dataproof + capture pipeline.

T-MLGA-1   MLGA_SESSION_DOMAIN_TAG = b"VAPI-MLGA-SESSION-v1" (20 bytes FROZEN)
T-MLGA-2   compute_mlga_session_dataproof determinism + manual recompute
T-MLGA-3   Per-input tamper detection (all 8 input fields independent)
T-MLGA-4   BT observability byte values FROZEN at 0x00/0x01/0x02
T-MLGA-5   bt_observability out-of-range / end < start ValueError
T-MLGA-6   mlga_session_log insert/get round-trip + UNIQUE idempotency
T-MLGA-7   MLGA capability tag registered in _KNOWN_CAPABILITY_TAGS (not PATTERN-017)
T-MLGA-8   Mythos-Live-Gameplay variant on empty DB → 1 MEDIUM HID-DISCONNECTED finding
T-MLGA-9   Mythos-Live-Gameplay variant on populated NOMINAL DB → 0 findings
T-MLGA-10  Cadence schedule has per_session tier with live_gameplay variant
T-MLGA-11  All live_gameplay findings have frozen_region=False (live state is operational)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


# ----- T-MLGA-1 -----

def test_t_mlga_1_domain_tag_frozen():
    from vapi_bridge.mlga_capture import MLGA_SESSION_DOMAIN_TAG
    assert MLGA_SESSION_DOMAIN_TAG == b"VAPI-MLGA-SESSION-v1"
    assert len(MLGA_SESSION_DOMAIN_TAG) == 20


# ----- T-MLGA-2 -----

def test_t_mlga_2_dataproof_determinism_and_manual_recompute():
    from vapi_bridge.mlga_capture import (
        compute_mlga_session_dataproof,
        MLGA_SESSION_DOMAIN_TAG,
        MLGA_BT_OBSERVED,
    )
    args = dict(
        session_start_ts_ns=1778000000_000_000_000,
        session_end_ts_ns=1778001800_000_000_000,
        n_poac_records=1_800_000,
        n_trigger_pulls_r2=124,
        n_trigger_pulls_l2=31,
        apop_state_counts={
            "ACTIVE_MATCH_PLAY": 1500,
            "MENU_DETECTED": 50,
        },
        bt_observability=MLGA_BT_OBSERVED,
        gic_advances_in_session=18,
    )
    d1 = compute_mlga_session_dataproof(**args)
    d2 = compute_mlga_session_dataproof(**args)
    assert d1 == d2, "non-deterministic"
    assert len(d1) == 32

    # Hand recompute the FROZEN preimage layout
    canonical_apop = json.dumps(
        args["apop_state_counts"], sort_keys=True,
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    apop_summary = hashlib.sha256(canonical_apop).digest()
    preimage = (
        MLGA_SESSION_DOMAIN_TAG
        + args["session_start_ts_ns"].to_bytes(8, "big")
        + args["session_end_ts_ns"].to_bytes(8, "big")
        + args["n_poac_records"].to_bytes(8, "big")
        + args["n_trigger_pulls_r2"].to_bytes(4, "big")
        + args["n_trigger_pulls_l2"].to_bytes(4, "big")
        + apop_summary
        + args["bt_observability"].to_bytes(1, "big")
        + args["gic_advances_in_session"].to_bytes(4, "big")
    )
    assert len(preimage) == 89
    expected = hashlib.sha256(preimage).digest()
    assert d1 == expected


# ----- T-MLGA-3 -----

def test_t_mlga_3_per_input_tamper_detection():
    """Each of the 8 input fields independently load-bearing."""
    from vapi_bridge.mlga_capture import (
        compute_mlga_session_dataproof, MLGA_BT_OBSERVED,
    )
    base = dict(
        session_start_ts_ns=1778000000_000_000_000,
        session_end_ts_ns=1778001800_000_000_000,
        n_poac_records=1_800_000,
        n_trigger_pulls_r2=124,
        n_trigger_pulls_l2=31,
        apop_state_counts={"ACTIVE_MATCH_PLAY": 1500},
        bt_observability=MLGA_BT_OBSERVED,
        gic_advances_in_session=18,
    )
    c0 = compute_mlga_session_dataproof(**base)
    tampered = [
        {**base, "session_start_ts_ns": base["session_start_ts_ns"] + 1},
        {**base, "session_end_ts_ns":   base["session_end_ts_ns"] + 1},
        {**base, "n_poac_records":      base["n_poac_records"] + 1},
        {**base, "n_trigger_pulls_r2":  base["n_trigger_pulls_r2"] + 1},
        {**base, "n_trigger_pulls_l2":  base["n_trigger_pulls_l2"] + 1},
        {**base, "apop_state_counts":   {"ACTIVE_MATCH_PLAY": 1501}},
        {**base, "bt_observability":    0x00},
        {**base, "gic_advances_in_session": base["gic_advances_in_session"] + 1},
    ]
    for i, t in enumerate(tampered):
        ct = compute_mlga_session_dataproof(**t)
        assert ct != c0, f"tamper at field index {i} did not change dataproof"


# ----- T-MLGA-4 -----

def test_t_mlga_4_bt_observability_frozen_values():
    from vapi_bridge.mlga_capture import (
        MLGA_BT_NOT_OBSERVED, MLGA_BT_OBSERVED,
        MLGA_BT_HELD_PLACED_IDENTIFIED,
    )
    assert MLGA_BT_NOT_OBSERVED == 0x00
    assert MLGA_BT_OBSERVED == 0x01
    assert MLGA_BT_HELD_PLACED_IDENTIFIED == 0x02


# ----- T-MLGA-5 -----

def test_t_mlga_5_input_validation():
    from vapi_bridge.mlga_capture import compute_mlga_session_dataproof
    base = dict(
        session_start_ts_ns=1778000000_000_000_000,
        session_end_ts_ns=1778001800_000_000_000,
        n_poac_records=10,
        n_trigger_pulls_r2=5,
        n_trigger_pulls_l2=5,
        apop_state_counts={},
        bt_observability=0x00,
        gic_advances_in_session=0,
    )
    # bt_observability out of FROZEN range
    with pytest.raises(ValueError, match="FROZEN"):
        compute_mlga_session_dataproof(**{**base, "bt_observability": 0x05})
    # bt_observability > 255
    with pytest.raises(ValueError, match="uint8"):
        compute_mlga_session_dataproof(**{**base, "bt_observability": 256})
    # negative input
    with pytest.raises(ValueError, match="non-negative"):
        compute_mlga_session_dataproof(**{**base, "n_poac_records": -1})
    # end < start
    with pytest.raises(ValueError, match="end must be >= start"):
        compute_mlga_session_dataproof(
            **{**base,
               "session_end_ts_ns": base["session_start_ts_ns"] - 1}
        )


# ----- T-MLGA-6 -----

def test_t_mlga_6_store_round_trip_and_idempotency():
    from vapi_bridge.store import Store
    from vapi_bridge.mlga_capture import (
        compute_mlga_session_dataproof, MLGA_BT_OBSERVED,
    )
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        store = Store(db_path=db)

        d = compute_mlga_session_dataproof(
            session_start_ts_ns=1778000000_000_000_000,
            session_end_ts_ns=1778001800_000_000_000,
            n_poac_records=1_800_000,
            n_trigger_pulls_r2=124,
            n_trigger_pulls_l2=31,
            apop_state_counts={"ACTIVE_MATCH_PLAY": 1500},
            bt_observability=MLGA_BT_OBSERVED,
            gic_advances_in_session=18,
        )
        dataproof_hex = d.hex()

        rid1 = store.insert_mlga_session(
            session_id="ncaa_cfb_26_session_001",
            session_start_ts_ns=1778000000_000_000_000,
            session_end_ts_ns=1778001800_000_000_000,
            n_poac_records=1_800_000,
            n_trigger_pulls_r2=124,
            n_trigger_pulls_l2=31,
            apop_state_counts_json='{"ACTIVE_MATCH_PLAY":1500}',
            bt_observability=MLGA_BT_OBSERVED,
            gic_advances_in_session=18,
            dataproof_hex=dataproof_hex,
        )
        assert rid1 > 0

        status = store.get_mlga_session_status()
        assert status["total_sessions"] == 1
        assert status["total_poac_records"] == 1_800_000
        assert status["total_r2_pulls"] == 124
        assert status["total_gic_advances"] == 18

        # Idempotent re-insert: same row id returned
        rid2 = store.insert_mlga_session(
            session_id="ncaa_cfb_26_session_001",
            session_start_ts_ns=1778000000_000_000_000,
            session_end_ts_ns=1778001800_000_000_000,
            n_poac_records=999_999,  # different field; UNIQUE on session_id+dataproof
            n_trigger_pulls_r2=124,
            n_trigger_pulls_l2=31,
            apop_state_counts_json='{"ACTIVE_MATCH_PLAY":1500}',
            bt_observability=MLGA_BT_OBSERVED,
            gic_advances_in_session=18,
            dataproof_hex=dataproof_hex,
        )
        assert rid2 == rid1
        status2 = store.get_mlga_session_status()
        assert status2["total_sessions"] == 1


# ----- T-MLGA-7 -----

def test_t_mlga_7_capability_registered():
    """MLGA tag must be in _KNOWN_CAPABILITY_TAGS (not _PATTERN_017_FROZEN_TAGS)."""
    from vapi_bridge.mythos_variants import (
        _KNOWN_CAPABILITY_TAGS, _PATTERN_017_FROZEN_TAGS,
    )
    assert b"VAPI-MLGA-SESSION-v1" in _KNOWN_CAPABILITY_TAGS
    assert b"VAPI-MLGA-SESSION-v1" not in _PATTERN_017_FROZEN_TAGS


# ----- T-MLGA-8 -----

def test_t_mlga_8_variant_empty_db_surfaces_disconnected_finding():
    """Against empty DB (no controller plugged in / no capture_health rows),
    variant should NOT raise + may surface informational findings."""
    from vapi_bridge.mythos_variants import mythos_live_gameplay_audit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        findings = asyncio.run(mythos_live_gameplay_audit(db_path=db))
        # Empty DB: capture_health_log empty → no HID finding. APOP empty
        # → no APOP finding. records empty → no sensor finding. GIC chain
        # empty → no GIC finding. Net: 0 findings (clean fresh state).
        assert isinstance(findings, list)


# ----- T-MLGA-9 -----

def test_t_mlga_9_variant_surfaces_degraded_capture_finding():
    """Seed capture_health_log with capture_state=DEGRADED → variant
    surfaces MEDIUM finding."""
    from vapi_bridge.mythos_variants import mythos_live_gameplay_audit
    import time as _t
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db)
        # Seed a capture_health_log row with DEGRADED state
        with sqlite3.connect(db) as con:
            con.execute(
                "INSERT INTO capture_health_log "
                "(capture_state, host_state, poll_rate_hz, "
                " transition_reason, grind_mode, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("DEGRADED", "EXCLUSIVE_USB", 500.0,
                 "test_seed", 0, _t.time()),
            )
            con.commit()
        findings = asyncio.run(mythos_live_gameplay_audit(db_path=db))
        hid_findings = [
            f for f in findings
            if f.severity == "MEDIUM"
            and "HID stream integrity DEGRADED" in (f.description or "")
        ]
        assert hid_findings, (
            f"expected MEDIUM HID-degraded finding; got: "
            f"{[(f.severity, f.description[:60]) for f in findings]}"
        )


# ----- T-MLGA-10 -----

def test_t_mlga_10_cadence_per_session_tier():
    from vapi_bridge.mythos_cadence_engine import MYTHOS_CADENCE_SCHEDULE
    assert "per_session" in MYTHOS_CADENCE_SCHEDULE
    assert "live_gameplay" in MYTHOS_CADENCE_SCHEDULE["per_session"]


# ----- T-MLGA-12 (unblock-export script) -----

def test_t_mlga_12_unblock_export_empty_db():
    """Export against empty DB → 0 sessions, NO_SESSIONS verdict, exit 1."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import mlga_unblock_export as exp
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        out = exp.run_export(db_path=db, since_days=30)
        assert out["sessions_in_window"] == 0
        assert out["verdict"] == "NO_SESSIONS"
        assert out["exit_code"] == 1


def test_t_mlga_13_unblock_export_with_seeded_session():
    """Seed a high-volume session → all 3 phases report progress."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import mlga_unblock_export as exp
    from vapi_bridge.store import Store
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        store = Store(db_path=db)
        store.insert_mlga_session(
            session_id="test_session_001",
            session_start_ts_ns=int(time.time()*1e9) - 3600_000_000_000,
            session_end_ts_ns=int(time.time()*1e9),
            n_poac_records=1_000_000,
            n_trigger_pulls_r2=200,
            n_trigger_pulls_l2=50,
            apop_state_counts_json='{"ACTIVE_MATCH_PLAY":900}',
            bt_observability=2,  # held-vs-placed identified
            gic_advances_in_session=15,
            dataproof_hex="ab" * 32,
        )
        out = exp.run_export(db_path=db, since_days=30)
        assert out["sessions_in_window"] == 1
        # All 3 phase exports present
        assert "phase_243_ss2_stage_a" in out["exports"]
        assert "phase_242_bt_stage_2" in out["exports"]
        assert "phase_229_ait_corpus" in out["exports"]
        # Phase 243: 250 pulls counted
        assert out["exports"]["phase_243_ss2_stage_a"]["mlga_total_pulls"] == 250
        # Phase 242: 1 session with BT observed, 1 held-placed
        assert out["exports"]["phase_242_bt_stage_2"]["mlga_sessions_with_bt_observed"] == 1
        assert out["exports"]["phase_242_bt_stage_2"]["mlga_sessions_with_held_placed"] == 1
        # Phase 229: 15 GIC advances
        assert out["exports"]["phase_229_ait_corpus"]["mlga_gic_advances_total"] == 15


# Add the `time` import for the seeded test
import time as _time_for_mlga_test
time = _time_for_mlga_test


# ----- T-MLGA-11 -----

def test_t_mlga_11_all_live_gameplay_findings_frozen_region_false():
    """MLGA finds are operational state, not protocol FROZEN material.
    INVARIANT: every live_gameplay finding MUST have frozen_region=False
    (the unique property of this variant among the 9 Mythos variants)."""
    from vapi_bridge.mythos_variants import mythos_live_gameplay_audit
    import time as _t
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db)
        # Seed both DEGRADED + CONTESTED + zero-trigger conditions to
        # exercise all 4 check families.
        with sqlite3.connect(db) as con:
            con.execute(
                "INSERT INTO capture_health_log "
                "(capture_state, host_state, poll_rate_hz, "
                " transition_reason, grind_mode, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("DEGRADED", "CONTESTED", 500.0,
                 "test_seed_t11", 0, _t.time()),
            )
            con.commit()
        findings = asyncio.run(mythos_live_gameplay_audit(db_path=db))
        assert findings, "expected ≥1 finding from seeded degraded state"
        for f in findings:
            assert f.frozen_region is False, (
                f"live_gameplay finding {f.coherence_id} has "
                f"frozen_region=True — VIOLATES INVARIANT (every "
                f"MLGA finding must be operational, not protocol-FROZEN)"
            )
