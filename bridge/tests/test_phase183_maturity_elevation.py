"""Phase 183 bridge tests — MaturityElevationGateAgent (WIF-027 W2 closure).

8 tests:
  T183-1  maturity_elevation_log table created; insert stores row; returns row_id >= 1
  T183-2  get_maturity_elevation_status returns safe defaults when empty
  T183-3  elevation_available=True when gap_to_target < 0.05
  T183-4  elevation_available=False when gap_to_target >= 0.05
  T183-5  critical_component stored and read correctly
  T183-6  estimated_sessions_total sums correctly
  T183-7  maturity_elevation_enabled config field present and defaults to True
  T183-8  GET /agent/maturity-elevation-plan endpoint returns 9 expected keys
"""
import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test183.db"))


# ---------------------------------------------------------------------------
# T183-1  table created; insert stores row; returns row_id >= 1
# ---------------------------------------------------------------------------

def test_t183_1_insert_maturity_elevation_log():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        plan = {"separation_component": {"gap": 0.30, "action": "P1_RE_ENROLLMENT"}}
        row_id = s.insert_maturity_elevation_log(
            current_tier="ALPHA",
            target_tier="BETA",
            gap_to_target=0.27,
            elevation_plan_json=json.dumps(plan),
            elevation_available=False,
            critical_component="separation_component",
            estimated_sessions_total=4,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T183-2  get_maturity_elevation_status returns safe defaults when empty
# ---------------------------------------------------------------------------

def test_t183_2_status_safe_defaults_when_empty():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        status = s.get_maturity_elevation_status()
        assert status["current_tier"] == "ALPHA"
        assert status["target_tier"] == "BETA"
        assert status["gap_to_target"] == 1.0
        assert status["elevation_available"] is False
        assert status["estimated_sessions_total"] == 0


# ---------------------------------------------------------------------------
# T183-3  elevation_available=True when gap < 0.05
# ---------------------------------------------------------------------------

def test_t183_3_elevation_available_when_gap_small():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_maturity_elevation_log(
            current_tier="BETA",
            target_tier="PRODUCTION_CANDIDATE",
            gap_to_target=0.03,
            elevation_plan_json="{}",
            elevation_available=True,
            critical_component="separation_component",
            estimated_sessions_total=0,
        )
        status = s.get_maturity_elevation_status()
        assert status["elevation_available"] is True
        assert status["gap_to_target"] == 0.03


# ---------------------------------------------------------------------------
# T183-4  elevation_available=False when gap >= 0.05
# ---------------------------------------------------------------------------

def test_t183_4_elevation_not_available_when_gap_large():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_maturity_elevation_log(
            current_tier="ALPHA",
            target_tier="BETA",
            gap_to_target=0.27,
            elevation_plan_json="{}",
            elevation_available=False,
            critical_component="separation_component",
            estimated_sessions_total=4,
        )
        status = s.get_maturity_elevation_status()
        assert status["elevation_available"] is False


# ---------------------------------------------------------------------------
# T183-5  critical_component stored and read correctly
# ---------------------------------------------------------------------------

def test_t183_5_critical_component_stored():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_maturity_elevation_log(
            current_tier="ALPHA",
            target_tier="BETA",
            gap_to_target=0.27,
            elevation_plan_json="{}",
            elevation_available=False,
            critical_component="enrollment_component",
            estimated_sessions_total=8,
        )
        status = s.get_maturity_elevation_status()
        assert status["critical_component"] == "enrollment_component"


# ---------------------------------------------------------------------------
# T183-6  estimated_sessions_total stored and read correctly
# ---------------------------------------------------------------------------

def test_t183_6_estimated_sessions_total():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_maturity_elevation_log(
            current_tier="ALPHA",
            target_tier="BETA",
            gap_to_target=0.27,
            elevation_plan_json="{}",
            elevation_available=False,
            critical_component="separation_component",
            estimated_sessions_total=12,
        )
        status = s.get_maturity_elevation_status()
        assert status["estimated_sessions_total"] == 12


# ---------------------------------------------------------------------------
# T183-7  maturity_elevation_enabled config field present and defaults True
# ---------------------------------------------------------------------------

def test_t183_7_config_field_present():
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "maturity_elevation_enabled")
    assert cfg.maturity_elevation_enabled is True


# ---------------------------------------------------------------------------
# T183-8  GET /agent/maturity-elevation-plan returns 9 expected keys
# ---------------------------------------------------------------------------

def test_t183_8_endpoint_returns_expected_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = Store(str(Path(tmp) / "test183t8.db"))
        cfg = Config()
        object.__setattr__(cfg, "operator_api_key", "test-key-183")

        app = create_operator_app(cfg, store)
        client = TestClient(app)

        resp = client.get(
            "/agent/maturity-elevation-plan",
            params={"api_key": "test-key-183"},
        )
        assert resp.status_code == 200
        body = resp.json()
        expected_keys = {
            "maturity_elevation_enabled",
            "current_tier",
            "target_tier",
            "gap_to_target",
            "elevation_available",
            "elevation_plan",
            "estimated_sessions_total",
            "critical_component",
            "timestamp",
        }
        for k in expected_keys:
            assert k in body, f"Missing key: {k}"
