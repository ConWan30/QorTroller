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


def _probe(store, verdict, cls, dev="desk-P1", lat=200.0):
    store.insert_l6b_probe(device_id=dev, probe_ts_ms=1.0, latency_ms=lat,
                           classification=cls, accel_delta_peak=600.0, reflex_verdict=verdict)


def test_gate_counts_valid_reflexes_not_raw_probes(store):
    # 3 real reflexes + 47 garbage = 50 raw rows, but only 3 valid -> gate NOT reached.
    for _ in range(3):
        _probe(store, "REFLEX_OBSERVED", "HUMAN")
    for _ in range(30):
        _probe(store, None, "NO_RESPONSE", lat=-1.0)
    for _ in range(17):
        _probe(store, None, "INCONCLUSIVE", lat=17.0)   # too-fast artifact
    p = store.get_l6b_calibration_progress()
    assert p["probe_count"] == 50            # raw total (transparency)
    assert p["valid_reflex_count"] == 3      # only REFLEX_OBSERVED
    assert p["gate_reached"] is False        # 50 garbage probes do NOT reach the gate


def test_gate_reached_only_on_50_valid(store):
    for _ in range(50):
        _probe(store, "REFLEX_OBSERVED", "HUMAN")
    p = store.get_l6b_calibration_progress()
    assert p["valid_reflex_count"] == 50 and p["gate_reached"] is True


def test_empty_corpus_honest_zero(store):
    p = store.get_l6b_calibration_progress()
    assert p["probe_count"] == 0 and p["valid_reflex_count"] == 0 and p["gate_reached"] is False
