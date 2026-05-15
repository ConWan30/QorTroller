"""Phase 182 bridge tests — PersonaBreakDetectorAgent (WIF-028 deeper mitigation).

8 tests:
  T182-1  persona_break_log table created, insert stores row, returns row_id >= 1
  T182-2  get_persona_break_status returns safe defaults when no rows exist
  T182-3  player_id filter returns latest for that player only
  T182-4  persona_break_detected=True stored and read correctly
  T182-5  re_enrollment_urgency=CRITICAL when persona break detected
  T182-6  persona_break_detection_enabled and persona_break_loo_threshold config fields present
  T182-7  GET /agent/persona-break-status endpoint returns 8 expected keys
  T182-8  second player stored separately — no cross-player contamination
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test182.db"))


# ---------------------------------------------------------------------------
# T182-1  table created; insert stores row; returns row_id >= 1
# ---------------------------------------------------------------------------

def test_t182_1_insert_persona_break_log():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        row_id = s.insert_persona_break_log(
            player_id="P1",
            loo_accuracy_trend=0.15,
            tdi_current=0.12,
            persona_break_detected=True,
            urgency="CRITICAL",
            n_snapshots=5,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T182-2  get_persona_break_status returns safe defaults when no rows
# ---------------------------------------------------------------------------

def test_t182_2_status_safe_defaults_when_empty():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        status = s.get_persona_break_status()
        assert status is not None
        assert status["persona_break_detected"] is False
        assert status["loo_accuracy_trend"] == 1.0
        assert status["re_enrollment_urgency"] == "MEDIUM"
        assert status["n_snapshots_used"] == 0


# ---------------------------------------------------------------------------
# T182-3  player_id filter returns latest for that player only
# ---------------------------------------------------------------------------

def test_t182_3_player_id_filter():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_persona_break_log("P1", 0.10, 0.05, True,  "CRITICAL", 5)
        s.insert_persona_break_log("P2", 0.80, 0.01, False, "MEDIUM",   3)
        p1 = s.get_persona_break_status("P1")
        p2 = s.get_persona_break_status("P2")
        assert p1["player_id"] == "P1"
        assert p1["persona_break_detected"] is True
        assert p2["player_id"] == "P2"
        assert p2["persona_break_detected"] is False


# ---------------------------------------------------------------------------
# T182-4  persona_break_detected=True stored and read correctly
# ---------------------------------------------------------------------------

def test_t182_4_persona_break_detected_true():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_persona_break_log("P1", 0.12, 0.18, True, "CRITICAL", 5)
        status = s.get_persona_break_status("P1")
        assert status["persona_break_detected"] is True
        assert status["loo_accuracy_trend"] == pytest_approx(0.12)


def pytest_approx(v):
    return v  # simple passthrough for value check


# ---------------------------------------------------------------------------
# T182-5  re_enrollment_urgency=CRITICAL when persona break
# ---------------------------------------------------------------------------

def test_t182_5_urgency_critical_when_break():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_persona_break_log("P1", 0.05, 0.20, True, "CRITICAL", 5)
        status = s.get_persona_break_status("P1")
        assert status["re_enrollment_urgency"] == "CRITICAL"


# ---------------------------------------------------------------------------
# T182-6  config fields present and defaults correct
# ---------------------------------------------------------------------------

def test_t182_6_config_fields_present():
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "persona_break_detection_enabled")
    assert cfg.persona_break_detection_enabled is True
    assert hasattr(cfg, "persona_break_loo_threshold")
    assert cfg.persona_break_loo_threshold == 0.20


# ---------------------------------------------------------------------------
# T182-7  GET /agent/persona-break-status endpoint returns 8 expected keys
# ---------------------------------------------------------------------------

def test_t182_7_endpoint_returns_expected_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = Store(str(Path(tmp) / "test182t7.db"))
        cfg = Config()
        object.__setattr__(cfg, "operator_api_key", "test-key-182")

        app = create_operator_app(cfg, store)
        client = TestClient(app)

        resp = client.get(
            "/agent/persona-break-status",
            params={"api_key": "test-key-182"},
        )
        assert resp.status_code == 200
        body = resp.json()
        expected_keys = {
            "persona_break_detection_enabled",
            "player_id",
            "loo_accuracy_trend",
            "tdi_current",
            "persona_break_detected",
            "re_enrollment_urgency",
            "n_snapshots_used",
            "timestamp",
        }
        for k in expected_keys:
            assert k in body, f"Missing key: {k}"


# ---------------------------------------------------------------------------
# T182-8  second player stored separately — no cross-player contamination
# ---------------------------------------------------------------------------

def test_t182_8_two_players_separate_snapshots():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_persona_break_log("P1", 0.10, 0.15, True,  "CRITICAL", 5)
        s.insert_persona_break_log("P3", 0.75, 0.02, False, "MEDIUM",   4)
        p1_status = s.get_persona_break_status("P1")
        p3_status = s.get_persona_break_status("P3")
        assert p1_status["persona_break_detected"] is True
        assert p3_status["persona_break_detected"] is False
        assert p1_status["n_snapshots_used"] == 5
        assert p3_status["n_snapshots_used"] == 4
