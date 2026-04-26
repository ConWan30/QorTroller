"""Phase 235-DASH-UPGRADE-3: live data integration tests.

T235-DASH-1: insert_ait_session stores per_player_features_json correctly
T235-DASH-2: get_ait_separation_status returns per_player_tremor_hz from stored features
T235-DASH-3: get_ait_separation_status returns per_player_roll_angle_deg from roll_cos/roll_sin
T235-DASH-4: get_ait_separation_status returns per_player_pitch_angle_deg from pitch_cos
T235-DASH-5: get_ait_separation_status returns empty dicts for legacy rows (no per_player_features_json)
T235-DASH-6: get_grind_analytics returns last_validation_ts as newest created_at
T235-DASH-7: get_grind_analytics returns last_stamp_ts as newest stamped row created_at
T235-DASH-8: get_grind_analytics returns 0.0 for both timestamps when no rows exist
"""
import json
import math
import sys
import tempfile
import time
import types
from pathlib import Path

import pytest

# Stub optional bridge deps so import succeeds without a running bridge
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_BRIDGE_DIR = Path(__file__).parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from vapi_bridge.store import Store


@pytest.fixture()
def store():
    # Windows WAL: use mkdtemp, not TemporaryDirectory (WAL keeps file open during teardown)
    d = tempfile.mkdtemp()
    s = Store(f"{d}/test.db")
    yield s


def _insert_ait(store, per_player_features=None):
    return store.insert_ait_session(
        n_sessions=37,
        n_per_player={"Player 1": 13, "Player 2": 10, "Player 3": 14},
        separation_ratio=1.199,
        all_pairs_above_1=True,
        inter_player_mean=1.682,
        intra_player_mean=0.520,
        loo_accuracy=0.667,
        cov_mode="full",
        pair_distances={"P1vP2": 1.850, "P1vP3": 1.846, "P2vP3": 1.349},
        analysis_date="2026-04-18",
        per_player_features=per_player_features,
    )


# T235-DASH-1
def test_per_player_features_stored(store):
    ppf = {
        "Player 1": {"accel_tremor_peak_hz": 9.37, "roll_cos": 0.8, "roll_sin": 0.6, "pitch_cos": 0.95},
        "Player 2": {"accel_tremor_peak_hz": 1.71, "roll_cos": 0.5, "roll_sin": 0.87, "pitch_cos": 0.70},
        "Player 3": {"accel_tremor_peak_hz": 2.85, "roll_cos": 0.9, "roll_sin": 0.44, "pitch_cos": 0.80},
    }
    _insert_ait(store, per_player_features=ppf)
    with store._conn() as conn:
        row = conn.execute("SELECT per_player_features_json FROM ait_session_log LIMIT 1").fetchone()
    stored = json.loads(row[0])
    assert stored["Player 1"]["accel_tremor_peak_hz"] == pytest.approx(9.37)
    assert stored["Player 3"]["accel_tremor_peak_hz"] == pytest.approx(2.85)


# T235-DASH-2
def test_per_player_tremor_hz_returned(store):
    ppf = {
        "Player 1": {"accel_tremor_peak_hz": 9.37, "roll_cos": 0.8, "roll_sin": 0.6, "pitch_cos": 0.95},
        "Player 2": {"accel_tremor_peak_hz": 1.71, "roll_cos": 0.5, "roll_sin": 0.87, "pitch_cos": 0.70},
        "Player 3": {"accel_tremor_peak_hz": 2.85, "roll_cos": 0.9, "roll_sin": 0.44, "pitch_cos": 0.80},
    }
    _insert_ait(store, per_player_features=ppf)
    status = store.get_ait_separation_status()
    th = status["per_player_tremor_hz"]
    assert th["Player 1"] == pytest.approx(9.37)
    assert th["Player 2"] == pytest.approx(1.71)
    assert th["Player 3"] == pytest.approx(2.85)


# T235-DASH-3
def test_per_player_roll_angle_deg_returned(store):
    # roll_cos=0.8, roll_sin=0.6 → atan2(0.6,0.8) ≈ 36.87°
    ppf = {"Player 1": {"accel_tremor_peak_hz": 9.37, "roll_cos": 0.8, "roll_sin": 0.6, "pitch_cos": 0.95}}
    _insert_ait(store, per_player_features=ppf)
    status = store.get_ait_separation_status()
    expected = math.degrees(math.atan2(0.6, 0.8))
    assert status["per_player_roll_angle_deg"]["Player 1"] == pytest.approx(expected, abs=0.01)


# T235-DASH-4
def test_per_player_pitch_angle_deg_returned(store):
    # pitch_cos=0.95 → acos(0.95) ≈ 18.19°
    ppf = {"Player 1": {"accel_tremor_peak_hz": 9.37, "roll_cos": 0.8, "roll_sin": 0.6, "pitch_cos": 0.95}}
    _insert_ait(store, per_player_features=ppf)
    status = store.get_ait_separation_status()
    expected = math.degrees(math.acos(0.95))
    assert status["per_player_pitch_angle_deg"]["Player 1"] == pytest.approx(expected, abs=0.01)


# T235-DASH-5
def test_legacy_row_empty_dicts(store):
    _insert_ait(store, per_player_features=None)
    status = store.get_ait_separation_status()
    assert status["per_player_tremor_hz"] == {}
    assert status["per_player_roll_angle_deg"] == {}
    assert status["per_player_pitch_angle_deg"] == {}


def _seed_validation_log(store, n_stamped, n_unstamped):
    import time as _t
    with store._conn() as conn:
        ts = _t.time()
        for i in range(n_unstamped):
            ts += 1.0
            conn.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                " llm_confidence, fallback_confidence, divergence, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (i, f"dev_{i}", "FLAG", "FLAG", 0.05, 0.05, 0, ts),
            )
        for i in range(n_stamped):
            ts += 1.0
            conn.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                " llm_confidence, fallback_confidence, divergence, grind_chain_hash, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (1000 + i, f"dev_s{i}", "FLAG", "FLAG", 0.05, 0.05, 0, f"deadbeef{i:04x}", ts),
            )
    return ts  # last ts = last stamped row


# T235-DASH-6
def test_last_validation_ts(store):
    last_ts = _seed_validation_log(store, n_stamped=3, n_unstamped=2)
    result = store.get_grind_analytics()
    # rows sorted by created_at ASC; last entry is the last stamped row
    assert result["last_validation_ts"] == pytest.approx(last_ts, abs=0.1)


# T235-DASH-7
def test_last_stamp_ts(store):
    last_ts = _seed_validation_log(store, n_stamped=3, n_unstamped=0)
    result = store.get_grind_analytics()
    assert result["last_stamp_ts"] == pytest.approx(last_ts, abs=0.1)
    assert result["last_stamp_ts"] <= result["last_validation_ts"] + 0.001


# T235-DASH-8
def test_timestamps_zero_when_empty(store):
    result = store.get_grind_analytics()
    assert result["last_validation_ts"] == 0.0
    assert result["last_stamp_ts"] == 0.0
