"""
Phase 188 tests — BiometricStationarityOracleAgent (agent #32).

Tests:
  T188-1: biometric_stationarity_log table created by Store.__init__
  T188-2: insert_biometric_stationarity_log stores record correctly
  T188-3: get_biometric_stationarity_status returns STABLE when no records
  T188-4: get_biometric_stationarity_status returns latest record
  T188-5: _compute_p_genuine_drift returns HIGH when chain intact + strong velocity
  T188-6: _compute_p_adversarial_window returns HIGH when chain anomaly + drift
  T188-7: config fields present and default False
  T188-8: SKIP (operator_api env dependency)
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

import types as _types
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

# dotenv stub — provide load_dotenv as a no-op
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402
from vapi_bridge.biometric_stationarity_oracle_agent import (  # noqa: E402
    BiometricStationarityOracleAgent,
)


@pytest.fixture()
def tmp_db():
    _d = tempfile.mkdtemp()
    _p = os.path.join(_d, "test_phase188.db")
    yield _p


@pytest.fixture()
def store(tmp_db):
    return Store(db_path=tmp_db)


@pytest.fixture()
def cfg():
    return Config()


# ---------------------------------------------------------------------------
# T188-1: table created
# ---------------------------------------------------------------------------

def test_t188_1_table_created(store):
    """T188-1: biometric_stationarity_log table created by Store.__init__."""
    import sqlite3
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "biometric_stationarity_log" in tables


# ---------------------------------------------------------------------------
# T188-2: insert stores record
# ---------------------------------------------------------------------------

def test_t188_2_insert_stores_record(store):
    """T188-2: insert_biometric_stationarity_log stores record correctly."""
    row_id = store.insert_biometric_stationarity_log(
        player_id="P1",
        p_genuine_drift=0.75,
        p_adversarial_window=0.10,
        stationarity_verdict="GENUINE_DRIFT",
        chain_integrity_score=1.0,
        trend_velocity=-0.12,
        temporal_drift_index=0.08,
        session_count_used=20,
    )
    assert row_id > 0
    import sqlite3
    with sqlite3.connect(store._db_path) as conn:
        row = conn.execute(
            "SELECT player_id, stationarity_verdict, p_genuine_drift, p_adversarial_window "
            "FROM biometric_stationarity_log WHERE id = ?",
            (row_id,),
        ).fetchone()
    assert row[0] == "P1"
    assert row[1] == "GENUINE_DRIFT"
    assert abs(row[2] - 0.75) < 1e-6
    assert abs(row[3] - 0.10) < 1e-6


# ---------------------------------------------------------------------------
# T188-3: get_status returns STABLE when no records
# ---------------------------------------------------------------------------

def test_t188_3_get_status_stable_when_empty(store):
    """T188-3: get_biometric_stationarity_status returns STABLE when no records."""
    status = store.get_biometric_stationarity_status()
    assert status["stationarity_verdict"] == "STABLE"
    assert status["p_genuine_drift"] == 0.0
    assert status["p_adversarial_window"] == 0.0
    assert status["total_adversarial_alerts"] == 0


# ---------------------------------------------------------------------------
# T188-4: get_status returns latest record
# ---------------------------------------------------------------------------

def test_t188_4_get_status_returns_latest(store):
    """T188-4: get_biometric_stationarity_status returns the latest record."""
    store.insert_biometric_stationarity_log(
        player_id="P1", p_genuine_drift=0.2, p_adversarial_window=0.8,
        stationarity_verdict="ADVERSARIAL_WINDOW", chain_integrity_score=0.80,
        trend_velocity=-0.20, temporal_drift_index=0.12, session_count_used=20,
    )
    store.insert_biometric_stationarity_log(
        player_id="P2", p_genuine_drift=0.7, p_adversarial_window=0.1,
        stationarity_verdict="GENUINE_DRIFT", chain_integrity_score=0.99,
        trend_velocity=-0.08, temporal_drift_index=0.06, session_count_used=14,
    )
    status = store.get_biometric_stationarity_status()
    # Latest is P2 (inserted last)
    assert status["player_id"] == "P2"
    assert status["stationarity_verdict"] == "GENUINE_DRIFT"
    # total_adversarial_alerts should count P1's ADVERSARIAL_WINDOW
    assert status["total_adversarial_alerts"] == 1


# ---------------------------------------------------------------------------
# T188-5: _compute_p_genuine_drift HIGH when chain intact + strong velocity
# ---------------------------------------------------------------------------

def test_t188_5_p_genuine_drift_high(cfg):
    """T188-5: _compute_p_genuine_drift returns high score when chain intact + strong velocity."""
    agent = BiometricStationarityOracleAgent(None, cfg, bus=None)
    p = agent._compute_p_genuine_drift(
        trend_velocity=-0.15,          # strong negative
        temporal_drift_index=0.12,     # elevated TDI
        chain_integrity_score=0.99,    # intact chain
        drift_direction="P1_NONSTATIONARITY",
    )
    # Should score ≥ 0.75 (0.35 velocity + 0.25 TDI + 0.25 chain + 0.15 direction)
    assert p >= 0.70, f"Expected p >= 0.70, got {p}"


# ---------------------------------------------------------------------------
# T188-6: _compute_p_adversarial_window HIGH when chain anomaly + drift
# ---------------------------------------------------------------------------

def test_t188_6_p_adversarial_window_high(cfg):
    """T188-6: _compute_p_adversarial_window returns high score when chain anomaly + drift."""
    agent = BiometricStationarityOracleAgent(None, cfg, bus=None)
    p = agent._compute_p_adversarial_window(
        trend_velocity=-0.20,       # sudden drop
        temporal_drift_index=0.15,  # elevated TDI
        chain_integrity_score=0.80, # well below floor (0.95)
        recovery_action="P1_RE_ENROLLMENT",
    )
    # chain gap = 0.95 - 0.80 = 0.15 → min(0.45, 0.45 * (0.15/0.10)) = 0.45
    # velocity < -0.15 → +0.30; P1_RE_ENROLLMENT + chain anomaly → +0.25
    # total = 0.45 + 0.30 + 0.25 = 1.0 (capped)
    assert p >= 0.60, f"Expected p >= 0.60, got {p}"


# ---------------------------------------------------------------------------
# T188-7: config fields present and default False
# ---------------------------------------------------------------------------

def test_t188_7_config_fields_default(cfg):
    """T188-7: Phase 188 config fields present with correct defaults."""
    assert hasattr(cfg, "biometric_stationarity_enabled")
    assert cfg.biometric_stationarity_enabled is False
    assert hasattr(cfg, "stationarity_adversarial_threshold")
    assert abs(cfg.stationarity_adversarial_threshold - 0.60) < 1e-6
    assert hasattr(cfg, "stationarity_chain_integrity_floor")
    assert abs(cfg.stationarity_chain_integrity_floor - 0.95) < 1e-6


# ---------------------------------------------------------------------------
# T188-8: endpoint smoke (skipped — requires operator_api env)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="operator_api smoke test requires full bridge env")
def test_t188_8_endpoint_smoke():
    """T188-8: GET /agent/biometric-stationarity-status returns expected keys."""
    pass
