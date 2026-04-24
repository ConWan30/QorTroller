"""Phase 235-ULTRAREVIEW Commit 1 — GIC enforcement tests.

T-UR-1: INV-GIC-003 — _gic_chain_broken=True halts consecutive_clean and gate
T-UR-2: INV-GIC-002 — gic_ts_ns is sole ordering key (backward NTP step safe)
T-UR-3: INV-GIC-001 — grind_session_id isolates chains (day-boundary rotation safe)
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store
from vapi_bridge.grind_chain import genesis_gic, compute_gic

_SID_A = "grind_test_ur_a"
_SID_B = "grind_test_ur_b"
_COMMITMENT = "ab" * 32  # 64 hex chars


def _seed_device_and_ruling(store: Store, device: str = "dev") -> int:
    store.upsert_device(device, "00" * 32)
    return store.insert_agent_ruling(
        device_id=device,
        verdict="FLAG",
        confidence=0.05,
        reasoning="",
        evidence_json="{}",
        commitment_hash=_COMMITMENT,
    )


def _insert_clean_row(store: Store, ruling_id: int, device: str = "dev") -> int:
    """Insert a NOMINAL EXCLUSIVE_USB non-divergent row (count-eligible)."""
    return store.insert_validation_record(
        ruling_id=ruling_id,
        device_id=device,
        llm_verdict="FLAG",
        fallback_verdict="FLAG",
        llm_confidence=0.05,
        fallback_confidence=0.05,
        divergence=0,
        pcc_state="NOMINAL",
        pcc_host_state="EXCLUSIVE_USB",
    )


# ---------------------------------------------------------------------------
# T-UR-1: INV-GIC-003 — chain_broken flag halts consecutive_clean
# ---------------------------------------------------------------------------

def test_inv_gic_003_broken_chain_halts_streak(tmp_path):
    store = Store(str(tmp_path / "test_ur_1.db"))
    ar_id = _seed_device_and_ruling(store)

    # Insert 5 clean rows — normally these would advance consecutive_clean
    for _ in range(5):
        _insert_clean_row(store, ar_id)

    # Without the broken flag, streak should advance
    summary_normal = store.get_validation_summary(gate_n=100, max_divergence_rate=1.0)
    assert summary_normal["consecutive_clean"] == 5, (
        "Baseline: 5 clean rows should give consecutive_clean=5"
    )

    # Simulate startup chain-break detection writing to the store flag
    store.set_gic_chain_broken(True)

    # Now get_validation_summary must fail-closed
    summary_broken = store.get_validation_summary(gate_n=100, max_divergence_rate=1.0)
    assert summary_broken["consecutive_clean"] == 0, (
        "INV-GIC-003: chain_broken=True must reset consecutive_clean to 0"
    )
    assert summary_broken["gate_passed"] is False, (
        "INV-GIC-003: chain_broken=True must prevent gate from passing"
    )
    assert summary_broken.get("chain_broken") is True, (
        "INV-GIC-003: response must include chain_broken=True sentinel"
    )

    # Clearing the flag restores normal counting
    store.set_gic_chain_broken(False)
    summary_restored = store.get_validation_summary(gate_n=100, max_divergence_rate=1.0)
    assert summary_restored["consecutive_clean"] == 5, (
        "INV-GIC-003: after clearing flag, consecutive_clean must restore to 5"
    )


# ---------------------------------------------------------------------------
# T-UR-2: INV-GIC-002 — gic_ts_ns is sole ordering key
# ---------------------------------------------------------------------------

def test_inv_gic_002_gic_ts_ns_is_sole_ordering(tmp_path):
    store = Store(str(tmp_path / "test_ur_2.db"))
    ar_id = _seed_device_and_ruling(store)

    ts_base = int(time.time() * 1e9)
    ts_high = ts_base + 2_000_000_000  # t+2s
    ts_low  = ts_base + 1_000_000_000  # t+1s (simulates backward NTP step)

    gen_high = genesis_gic(_SID_A, ts_high)
    gic_high = compute_gic(gen_high, _COMMITMENT, "EXCLUSIVE_USB", "FLAG", ts_high)

    gen_low  = genesis_gic(_SID_A, ts_low)
    gic_low  = compute_gic(gen_low,  _COMMITMENT, "EXCLUSIVE_USB", "FLAG", ts_low)

    # Insert row1 first (gic_ts_ns = ts_high)
    row1 = _insert_clean_row(store, ar_id)
    store.update_grind_chain_hash(row1, gic_high.hex(), ts_high, _SID_A)

    # Insert row2 second — later created_at, but lower gic_ts_ns (backward NTP)
    row2 = _insert_clean_row(store, ar_id)
    store.update_grind_chain_hash(row2, gic_low.hex(), ts_low, _SID_A)

    # get_prev_grind_chain_hash must return the hash with the highest gic_ts_ns
    # (row1, gic_high), NOT the hash with the highest created_at (row2, gic_low).
    prev = store.get_prev_grind_chain_hash(_SID_A)
    assert prev == gic_high, (
        "INV-GIC-002: get_prev_grind_chain_hash must order by gic_ts_ns DESC, "
        "not created_at — a backward NTP step must not displace the true chain tip"
    )


# ---------------------------------------------------------------------------
# T-UR-3: INV-GIC-001 — session_id isolates chains across day boundaries
# ---------------------------------------------------------------------------

def test_inv_gic_001_session_id_isolation(tmp_path):
    store = Store(str(tmp_path / "test_ur_3.db"))
    ar_id = _seed_device_and_ruling(store)

    ts_base = int(time.time() * 1e9)

    # Session A — 2 GIC entries
    gen_a = genesis_gic(_SID_A, ts_base)
    gic_a1 = compute_gic(gen_a,   _COMMITMENT, "EXCLUSIVE_USB", "FLAG", ts_base + 1)
    gic_a2 = compute_gic(gic_a1,  _COMMITMENT, "EXCLUSIVE_USB", "FLAG", ts_base + 2)

    row_a1 = _insert_clean_row(store, ar_id)
    store.update_grind_chain_hash(row_a1, gic_a1.hex(), ts_base + 1, _SID_A)

    row_a2 = _insert_clean_row(store, ar_id)
    store.update_grind_chain_hash(row_a2, gic_a2.hex(), ts_base + 2, _SID_A)

    # Session B — 1 GIC entry (simulates day-boundary rotation to new session ID)
    gen_b  = genesis_gic(_SID_B, ts_base + 3)
    gic_b1 = compute_gic(gen_b,  _COMMITMENT, "EXCLUSIVE_USB", "FLAG", ts_base + 3)

    row_b1 = _insert_clean_row(store, ar_id)
    store.update_grind_chain_hash(row_b1, gic_b1.hex(), ts_base + 3, _SID_B)

    # Session A tip must be gic_a2, not gic_b1
    prev_a = store.get_prev_grind_chain_hash(_SID_A)
    assert prev_a == gic_a2, (
        "INV-GIC-001: session A tip must be gic_a2, not contaminated by session B"
    )

    # Session B tip must be gic_b1
    prev_b = store.get_prev_grind_chain_hash(_SID_B)
    assert prev_b == gic_b1, (
        "INV-GIC-001: session B tip must be gic_b1 (its own chain)"
    )

    # Chain status for A must see chain_length=2, intact
    status_a = store.get_grind_chain_status(_SID_A)
    assert status_a["chain_length"] == 2, (
        f"INV-GIC-001: session A chain_length must be 2, got {status_a['chain_length']}"
    )

    # Chain status for B must see chain_length=1, intact
    status_b = store.get_grind_chain_status(_SID_B)
    assert status_b["chain_length"] == 1, (
        f"INV-GIC-001: session B chain_length must be 1, got {status_b['chain_length']}"
    )
