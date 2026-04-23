"""Phase 235-B — PCC Attestation Slot on ruling_validation_log.

T235B-1: pcc_state=NOMINAL + pcc_host_state=EXCLUSIVE_USB + divergence=0 → counts toward streak
T235B-2: pcc_state=DEGRADED + divergence=0 → does NOT count (streak breaks)
T235B-3: pcc_state=NOMINAL + pcc_host_state=CONTESTED + divergence=0 → does NOT count
T235B-4: pcc_state=NULL + divergence=0 → fail-closed, does NOT count (pre-235-B row)
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def tmp_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "test_235b.db"))


def _insert(store, ruling_id, divergence, pcc_state, pcc_host_state):
    """Helper: insert a minimal validation row with PCC fields."""
    store.insert_validation_record(
        ruling_id=ruling_id,
        device_id="dev-test",
        llm_verdict="FLAG",
        fallback_verdict="FLAG",
        llm_confidence=0.5,
        fallback_confidence=0.5,
        divergence=divergence,
        divergence_reason=None,
        pcc_state=pcc_state,
        pcc_host_state=pcc_host_state,
    )


# ---------------------------------------------------------------------------
# T235B-1: NOMINAL + EXCLUSIVE_USB + divergence=0 → counts
# ---------------------------------------------------------------------------

def test_t235b_1_nominal_exclusive_usb_counts(tmp_store):
    _insert(tmp_store, 1, 0, "NOMINAL", "EXCLUSIVE_USB")
    _insert(tmp_store, 2, 0, "NOMINAL", "EXCLUSIVE_USB")
    _insert(tmp_store, 3, 0, "NOMINAL", "EXCLUSIVE_USB")

    summary = tmp_store.get_validation_summary(gate_n=100)
    assert summary["consecutive_clean"] == 3, (
        f"Expected 3 clean sessions with NOMINAL+EXCLUSIVE_USB, got {summary['consecutive_clean']}"
    )
    assert summary["latest_pcc_state"] == "NOMINAL"
    assert summary["latest_pcc_host_state"] == "EXCLUSIVE_USB"


# ---------------------------------------------------------------------------
# T235B-2: pcc_state=DEGRADED breaks streak even with divergence=0
# ---------------------------------------------------------------------------

def test_t235b_2_degraded_does_not_count(tmp_store):
    # 2 clean NOMINAL rows, then 1 DEGRADED row
    _insert(tmp_store, 1, 0, "NOMINAL", "EXCLUSIVE_USB")
    _insert(tmp_store, 2, 0, "NOMINAL", "EXCLUSIVE_USB")
    _insert(tmp_store, 3, 0, "DEGRADED", "EXCLUSIVE_USB")

    summary = tmp_store.get_validation_summary(gate_n=100)
    # Most recent row is DEGRADED — streak is 0 (DEGRADED head breaks immediately)
    assert summary["consecutive_clean"] == 0, (
        f"DEGRADED head must break streak; got consecutive_clean={summary['consecutive_clean']}"
    )


# ---------------------------------------------------------------------------
# T235B-3: NOMINAL + CONTESTED breaks streak
# ---------------------------------------------------------------------------

def test_t235b_3_contested_does_not_count(tmp_store):
    # 2 clean NOMINAL+EXCLUSIVE_USB, then 1 NOMINAL+CONTESTED
    _insert(tmp_store, 1, 0, "NOMINAL", "EXCLUSIVE_USB")
    _insert(tmp_store, 2, 0, "NOMINAL", "EXCLUSIVE_USB")
    _insert(tmp_store, 3, 0, "NOMINAL", "CONTESTED")

    summary = tmp_store.get_validation_summary(gate_n=100)
    assert summary["consecutive_clean"] == 0, (
        f"CONTESTED host_state must break streak; got {summary['consecutive_clean']}"
    )


# ---------------------------------------------------------------------------
# T235B-4: NULL pcc_state → fail-closed, does not count
# ---------------------------------------------------------------------------

def test_t235b_4_null_pcc_does_not_count(tmp_store):
    # Pre-235-B row: pcc_state=None (NULL in DB)
    _insert(tmp_store, 1, 0, None, None)
    _insert(tmp_store, 2, 0, None, None)

    summary = tmp_store.get_validation_summary(gate_n=100)
    assert summary["consecutive_clean"] == 0, (
        f"NULL pcc_state must be fail-closed (streak=0); got {summary['consecutive_clean']}"
    )
    assert summary["latest_pcc_state"] is None
