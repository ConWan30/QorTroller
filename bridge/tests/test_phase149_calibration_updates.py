"""
Phase 149 — Calibration Staleness Fixes (8 tests)

test_1_current_phase_constant_is_148
test_2_count_players_from_dirs_finds_3_players
test_3_load_separation_from_db_reads_snapshot
test_4_load_separation_from_db_returns_none_on_empty
test_5_compute_progress_uses_db_ratio
test_6_compute_progress_uses_dir_based_player_count
test_7_calibration_intelligence_agent_separation_returns_phase143_values
test_8_get_zero_variance_features_touch_variance_active
"""

import importlib.util
import json
import sqlite3
import sys
import tempfile
import pathlib
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_BRIDGE = _REPO_ROOT / "bridge" / "vapi_bridge"

# bridge/vapi_bridge/calibration_agent.py (Phase 17) would shadow the scripts
# version under the same name.  Load the scripts version explicitly so tests
# always target the Phase 149 calibration_agent in scripts/.
_CA_PATH = _SCRIPTS / "calibration_agent.py"
_ca_spec = importlib.util.spec_from_file_location("calibration_agent_scripts", _CA_PATH)
_ca_mod = importlib.util.module_from_spec(_ca_spec)
_ca_spec.loader.exec_module(_ca_mod)

if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))


# ---------------------------------------------------------------------------
# 1. _CURRENT_PHASE constant
# ---------------------------------------------------------------------------

class TestCurrentPhaseConstant:

    def test_1_current_phase_constant_is_148(self):
        """_CURRENT_PHASE in scripts/calibration_agent.py must be 148 after Phase 149 update."""
        assert _ca_mod._CURRENT_PHASE == 148


# ---------------------------------------------------------------------------
# 2. _count_players_from_dirs
# ---------------------------------------------------------------------------

class TestCountPlayersFromDirs:

    def test_2_count_players_from_dirs_finds_3_players(self):
        """_count_players_from_dirs must return 3 when terminal_cal_P1/P2/P3 all exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            human = root / "sessions" / "human"
            (human / "terminal_cal_P1").mkdir(parents=True)
            (human / "terminal_cal_P2").mkdir(parents=True)
            (human / "terminal_cal_P3").mkdir(parents=True)
            original = _ca_mod._REPO_ROOT
            _ca_mod._REPO_ROOT = root
            try:
                count = _ca_mod._count_players_from_dirs()
            finally:
                _ca_mod._REPO_ROOT = original
        assert count == 3

    def test_2b_count_players_includes_hw_json_as_p1(self):
        """hw_*.json files count as P1 even without explicit terminal_cal_P1 dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            human = root / "sessions" / "human"
            human.mkdir(parents=True)
            (human / "hw_001.json").touch()
            # No terminal_cal_P* dirs
            original = _ca_mod._REPO_ROOT
            _ca_mod._REPO_ROOT = root
            try:
                count = _ca_mod._count_players_from_dirs()
            finally:
                _ca_mod._REPO_ROOT = original
        assert count == 1  # P1 from hw_*.json


# ---------------------------------------------------------------------------
# 3–4. _load_separation_from_db
# ---------------------------------------------------------------------------

class TestLoadSeparationFromDb:

    def _make_db_with_snapshot(self, path: pathlib.Path, ratio: float) -> None:
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE separation_ratio_snapshots "
            "(id INTEGER PRIMARY KEY, pooled_ratio REAL, created_at REAL)"
        )
        conn.execute(
            "INSERT INTO separation_ratio_snapshots (pooled_ratio, created_at) VALUES (?, ?)",
            (ratio, 1711000000.0),
        )
        conn.commit()
        conn.close()

    def test_3_load_separation_from_db_reads_snapshot(self):
        """_load_separation_from_db returns the latest pooled_ratio from the DB."""
        import calibration_agent as ca
        with tempfile.TemporaryDirectory() as tmpdir:
            db = pathlib.Path(tmpdir) / "bridge.db"
            self._make_db_with_snapshot(db, 1.261)
            result = _ca_mod._load_separation_from_db(db)
        assert result == pytest.approx(1.261)

    def test_4_load_separation_from_db_returns_none_on_empty(self):
        """_load_separation_from_db returns None when table is empty or missing."""
        import calibration_agent as ca
        with tempfile.TemporaryDirectory() as tmpdir:
            db = pathlib.Path(tmpdir) / "bridge.db"
            # Table exists but no rows
            conn = sqlite3.connect(str(db))
            conn.execute(
                "CREATE TABLE separation_ratio_snapshots "
                "(id INTEGER PRIMARY KEY, pooled_ratio REAL, created_at REAL)"
            )
            conn.commit()
            conn.close()
            result = _ca_mod._load_separation_from_db(db)
        assert result is None

    def test_4b_load_separation_returns_none_on_missing_db(self):
        """_load_separation_from_db returns None when DB file does not exist."""
        result = _ca_mod._load_separation_from_db(pathlib.Path("/nonexistent/bridge.db"))
        assert result is None


# ---------------------------------------------------------------------------
# 5–6. _compute_progress
# ---------------------------------------------------------------------------

class TestComputeProgress:

    def _make_db_with_snapshot(self, path: pathlib.Path, ratio: float) -> None:
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE separation_ratio_snapshots "
            "(id INTEGER PRIMARY KEY, pooled_ratio REAL, created_at REAL)"
        )
        conn.execute(
            "INSERT INTO separation_ratio_snapshots (pooled_ratio, created_at) VALUES (?, ?)",
            (ratio, 1711000000.0),
        )
        conn.commit()
        conn.close()

    def test_5_compute_progress_uses_db_ratio(self):
        """_compute_progress reads separation ratio from DB snapshot, not just env var."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = pathlib.Path(tmpdir) / "bridge.db"
            self._make_db_with_snapshot(db, 1.261)
            result = _ca_mod._compute_progress([], [], db=db)
        assert result["separation_ratio_current"] == pytest.approx(1.261)

    def test_6_compute_progress_uses_dir_based_player_count(self):
        """_compute_progress uses directory scan for player count, not DB device_id grouping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            human = root / "sessions" / "human"
            (human / "terminal_cal_P1").mkdir(parents=True)
            (human / "terminal_cal_P2").mkdir(parents=True)
            (human / "terminal_cal_P3").mkdir(parents=True)
            original_root = _ca_mod._REPO_ROOT
            _ca_mod._REPO_ROOT = root
            try:
                # Pass single device_id session — DB grouping yields 1 player
                sessions = [{
                    "device_id": "single_device_abc123",
                    "touch_position_variance": 0.0,
                    "micro_tremor_accel_variance": 0.0,
                    "press_timing_jitter_variance": 0.0,
                    "created_at": 1711000000.0,
                }]
                result = _ca_mod._compute_progress(sessions, [], db=None)
            finally:
                _ca_mod._REPO_ROOT = original_root
        # Should report 3 (from dirs), not 1 (from single device_id)
        assert result["n_players"] == 3


# ---------------------------------------------------------------------------
# 7–8. CalibrationIntelligenceAgent tools
# ---------------------------------------------------------------------------

class TestCalibrationIntelligenceAgentTools:

    def _make_agent(self):
        """Construct CalibrationIntelligenceAgent with mocked config and store."""
        # Stub heavy deps if not present
        for mod_name in ["anthropic"]:
            if mod_name not in sys.modules:
                sys.modules[mod_name] = MagicMock()

        from calibration_intelligence_agent import CalibrationIntelligenceAgent

        cfg = MagicMock()
        cfg.llm_provider = "anthropic"
        cfg.llm_model = "claude-sonnet-4-6"
        cfg.llm_api_key = "test-key"
        cfg.calibration_agent_enabled = True

        store = MagicMock()
        # get_separation_ratio_status returns empty (triggers fallback)
        store.get_separation_ratio_status.return_value = []

        agent = CalibrationIntelligenceAgent.__new__(CalibrationIntelligenceAgent)
        agent._cfg = cfg
        agent._store = store
        agent._client = None
        return agent

    def test_7_get_separation_analysis_returns_phase143_values(self):
        """get_separation_analysis tool returns Phase 143 honest diagonal values."""
        agent = self._make_agent()
        result = agent._execute_tool("get_separation_analysis", {})
        # Phase 143: ratio=1.261, classification=63.6%, tournament_blocker=True
        assert result["interperson_separation_ratio"] == pytest.approx(1.261)
        assert result["loo_classification_accuracy"] == pytest.approx(0.636, abs=0.01)
        assert result["tournament_blocker"] is True
        assert result["phase"] == 143

    def test_8_get_zero_variance_features_touch_variance_active(self):
        """get_zero_variance_features reports touch_position_variance as active in touchpad sessions."""
        agent = self._make_agent()
        result = agent._execute_tool("get_zero_variance_features", {})
        features = result.get("features", [])
        assert isinstance(features, list), f"Expected list, got {type(features)}"
        tpv_entries = [f for f in features if f.get("name") == "touch_position_variance"]
        assert tpv_entries, "touch_position_variance not found in features list"
        tpv = tpv_entries[0]
        assert tpv.get("status") == "active_in_touchpad_sessions", (
            f"Expected 'active_in_touchpad_sessions', got {tpv.get('status')!r}"
        )
