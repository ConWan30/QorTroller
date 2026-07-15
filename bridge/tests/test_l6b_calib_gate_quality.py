"""F-POEP-P0-2 — the L6B N>=50 calibration gate counts VALID reflexes, not raw probes.

Pre-fix, get_l6b_calibration_progress used COUNT(*) so 50 NO_RESPONSE / INCONCLUSIVE artifact rows
would satisfy the calibration gate. These tests pin the fix: gate_reached keys on REFLEX_OBSERVED
rows only; raw probe_count stays reported for transparency.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from bridge.vapi_bridge.store import Store


@pytest.fixture()
def store():
    d = tempfile.mkdtemp()
    s = Store(db_path=str(Path(d) / "t.db"))
    yield s


_TS = [0.0]  # monotonic probe-timestamp source, spaced 10s apart (independent by default)


def _probe(store, verdict, cls, dev="desk-P1", lat=200.0, peak=600.0, policy="desk_operator_still",
           ts=None):
    # B1+B2: a USABLE reflex needs an allowlisted policy AND IMU peak AND in-band -- not just verdict.
    if ts is None:
        _TS[0] += 10_000.0   # 10s apart -> independent under the 5s burst window
        ts = _TS[0]
    store.insert_l6b_probe(device_id=dev, probe_ts_ms=ts, latency_ms=lat,
                           classification=cls, accel_delta_peak=peak, reflex_verdict=verdict,
                           policy_ref=policy)


def test_gate_counts_usable_reflexes_not_raw_or_observed(store):
    # 3 usable reflexes + 47 garbage of THREE kinds -> only 3 usable, gate NOT reached.
    for _ in range(3):
        _probe(store, "REFLEX_OBSERVED", "HUMAN")                                   # usable
    for _ in range(20):
        _probe(store, None, "NO_RESPONSE", lat=-1.0)                               # no reflex
    for _ in range(15):
        _probe(store, "REFLEX_OBSERVED", "HUMAN", peak=0.0, policy=None)           # null-route peak=0 junk
    for _ in range(12):
        _probe(store, "REFLEX_OBSERVED", "HUMAN", policy="CCO_T0_POLICY_v1_OPTION_C")  # device-physics
    p = store.get_l6b_calibration_progress()
    assert p["probe_count"] == 50            # raw total (transparency)
    assert p["valid_reflex_count"] == 3      # B1+B2: only allowlisted + IMU + in-band
    assert p["gate_reached"] is False        # 47 garbage (incl. REFLEX_OBSERVED junk) do NOT count


def test_gate_reached_only_on_50_independent_usable(store):
    for _ in range(50):
        _probe(store, "REFLEX_OBSERVED", "HUMAN")                # spaced 10s -> 50 independent
    p = store.get_l6b_calibration_progress()
    assert p["valid_reflex_count"] == 50 and p["independent_reflex_count"] == 50
    assert p["gate_reached"] is True


def test_burst_correlated_usable_do_not_clear_gate(store):
    # grok DQ-6 ENFORCED: 50 usable reflexes all fired in one <5s burst = 1 effective independent.
    for _ in range(50):
        _probe(store, "REFLEX_OBSERVED", "HUMAN", ts=1000.0)     # same timestamp -> one burst
    p = store.get_l6b_calibration_progress()
    assert p["valid_reflex_count"] == 50                         # raw usable still shown
    assert p["independent_reflex_count"] == 1                    # but only 1 independent
    assert p["gate_reached"] is False                            # burst-inflated N does NOT clear the gate


def test_empty_corpus_honest_zero(store):
    p = store.get_l6b_calibration_progress()
    assert p["probe_count"] == 0 and p["valid_reflex_count"] == 0 and p["gate_reached"] is False
