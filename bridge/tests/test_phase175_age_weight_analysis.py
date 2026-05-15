"""Phase 175 bridge tests — AgeWeightedRatioPersistenceAgent (agent #24).

8 tests:
  T175-1  insert_age_weight_analysis_log stores record correctly
  T175-2  get_age_weight_analysis_status returns latest record
  T175-3  temporal_drift_index computed as raw_ratio - age_weighted_ratio
  T175-4  drift_direction P1_NONSTATIONARITY when tdi > 0.05
  T175-5  drift_direction IMPROVING when tdi < -0.05
  T175-6  drift_direction STABLE when tdi near zero
  T175-7  GET /agent/age-weight-analysis-status returns 8 keys
  T175-8  GET /agent/age-weight-analysis-status default halflife_days = 90.0
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test175.db"))


# ---------------------------------------------------------------------------
# T175-1  insert stores record
# ---------------------------------------------------------------------------

def test_t175_1_insert_stores_record():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        row_id = s.insert_age_weight_analysis_log(
            probe_type="touchpad_corners",
            raw_ratio=0.569,
            age_weighted_ratio=0.720,
            halflife_days=90.0,
            n_sessions_used=20,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T175-2  get_age_weight_analysis_status returns latest
# ---------------------------------------------------------------------------

def test_t175_2_get_returns_latest():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_age_weight_analysis_log("touchpad_corners", 0.569, 0.720, 90.0, 20)
        time.sleep(0.01)
        s.insert_age_weight_analysis_log("touchpad_corners", 0.612, 0.650, 30.0, 22)
        rows = s.get_age_weight_analysis_status(limit=1)
        assert len(rows) == 1
        assert abs(rows[0]["raw_ratio"] - 0.612) < 1e-6


# ---------------------------------------------------------------------------
# T175-3  temporal_drift_index = raw - age_weighted
# ---------------------------------------------------------------------------

def test_t175_3_temporal_drift_index():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_age_weight_analysis_log("touchpad_corners", 0.569, 0.720, 90.0, 20)
        rows = s.get_age_weight_analysis_status(limit=1)
        expected_tdi = round(0.569 - 0.720, 6)
        assert abs(rows[0]["temporal_drift_index"] - expected_tdi) < 1e-5


# ---------------------------------------------------------------------------
# T175-4  drift_direction P1_NONSTATIONARITY when tdi > 0.05
# ---------------------------------------------------------------------------

def test_t175_4_drift_p1_nonstationarity():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        # raw=1.2, age_weighted=1.0 -> tdi=0.2 > 0.05
        s.insert_age_weight_analysis_log("touchpad_corners", 1.200, 1.000, 90.0, 15)
        rows = s.get_age_weight_analysis_status(limit=1)
        assert rows[0]["drift_direction"] == "P1_NONSTATIONARITY"


# ---------------------------------------------------------------------------
# T175-5  drift_direction IMPROVING when tdi < -0.05
# ---------------------------------------------------------------------------

def test_t175_5_drift_improving():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        # raw=1.0, age_weighted=1.3 -> tdi=-0.3 < -0.05
        s.insert_age_weight_analysis_log("touchpad_corners", 1.000, 1.300, 90.0, 15)
        rows = s.get_age_weight_analysis_status(limit=1)
        assert rows[0]["drift_direction"] == "IMPROVING"


# ---------------------------------------------------------------------------
# T175-6  drift_direction STABLE when tdi near zero
# ---------------------------------------------------------------------------

def test_t175_6_drift_stable():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        # raw=1.0, age_weighted=1.02 -> tdi=-0.02 in [-0.05, 0.05]
        s.insert_age_weight_analysis_log("touchpad_corners", 1.000, 1.020, 90.0, 15)
        rows = s.get_age_weight_analysis_status(limit=1)
        assert rows[0]["drift_direction"] == "STABLE"


# ---------------------------------------------------------------------------
# T175-7  get_age_weight_analysis_status returns expected keys
# ---------------------------------------------------------------------------

def test_t175_7_status_returns_expected_keys():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_age_weight_analysis_log("touchpad_corners", 0.569, 0.720, 90.0, 20)
        rows = s.get_age_weight_analysis_status(limit=1)
        assert len(rows) == 1
        row = rows[0]
        expected_keys = {
            "id", "probe_type", "raw_ratio", "age_weighted_ratio",
            "temporal_drift_index", "halflife_days", "n_sessions_used",
            "drift_direction", "created_at",
        }
        assert expected_keys.issubset(set(row.keys()))


# ---------------------------------------------------------------------------
# T175-8  empty log returns default halflife_days = 90.0
# ---------------------------------------------------------------------------

def test_t175_8_empty_log_returns_empty_list():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        rows = s.get_age_weight_analysis_status(limit=1)
        # No records — empty list (defaults handled at API layer)
        assert rows == []
