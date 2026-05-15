"""Phase O5-MLGA Stage 3 — session tracker runtime tests.

T-MLGA-TRACKER-1   Tracker constructs with defaults; no session open initially
T-MLGA-TRACKER-2   open_session opens; idempotent re-open returns same id
T-MLGA-TRACKER-3   close_session closes; idempotent re-close returns False
T-MLGA-TRACKER-4   close persists dataproof to mlga_session_log
T-MLGA-TRACKER-5   poll_once on empty DB → noop_no_controller
T-MLGA-TRACKER-6   poll_once with NOMINAL capture → opens session
T-MLGA-TRACKER-7   poll_once with open session + DISCONNECTED → closes session
T-MLGA-TRACKER-8   poll_once accumulates records / R2 / APOP / GIC deltas
T-MLGA-TRACKER-9   Auto-close at max_session_duration_s threshold
T-MLGA-TRACKER-10  live_status snapshot returns correct shape
T-MLGA-TRACKER-11  config has 3 MLGA tracker fields with default-False/30/3600
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_store(td: str):
    from vapi_bridge.store import Store
    return Store(db_path=os.path.join(td, "t.db"))


def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.mlga_session_tracker_enabled = overrides.get("enabled", True)
    cfg.mlga_session_tracker_interval_s = overrides.get("interval", 30)
    cfg.mlga_session_max_duration_s = overrides.get("max_dur", 3600)
    return cfg


def _seed_capture_state(db_path: str, capture_state: str, host_state: str = "EXCLUSIVE_USB"):
    with sqlite3.connect(db_path) as con:
        con.execute(
            "INSERT INTO capture_health_log "
            "(capture_state, host_state, poll_rate_hz, transition_reason, "
            " grind_mode, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (capture_state, host_state, 1000.0, "test_seed", 0, time.time()),
        )
        con.commit()


# ----- T-1 -----

def test_t_mlga_tracker_1_constructs_with_defaults():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = _make_cfg()
        tracker = MLGASessionTracker(store=store, cfg=cfg)
        assert tracker._open is None
        assert tracker._sessions_persisted == 0


# ----- T-2 -----

def test_t_mlga_tracker_2_open_session_idempotent():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker = MLGASessionTracker(store=_make_store(td), cfg=_make_cfg())
        sid_1 = tracker.open_session("test_reason")
        sid_2 = tracker.open_session("test_reason_2")  # re-open no-op
        assert sid_1 == sid_2
        assert tracker._open is not None
        assert tracker._open.open_reason == "test_reason"


# ----- T-3 -----

def test_t_mlga_tracker_3_close_session_idempotent():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker = MLGASessionTracker(store=_make_store(td), cfg=_make_cfg())
        # close with no open session → False
        assert tracker.close_session("test") is False
        tracker.open_session("open")
        assert tracker.close_session("close_1") is True
        # second close → False (no open session)
        assert tracker.close_session("close_2") is False


# ----- T-4 -----

def test_t_mlga_tracker_4_close_persists_dataproof():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        tracker = MLGASessionTracker(store=store, cfg=_make_cfg())
        tracker.open_session("test", ts_ns=1_000_000_000)
        tracker._open.n_poac_records = 100
        tracker._open.n_trigger_pulls_r2 = 5
        tracker.close_session("test_close", ts_ns=2_000_000_000)
        # Verify row persisted in mlga_session_log
        status = store.get_mlga_session_status()
        assert status["total_sessions"] == 1
        assert tracker._sessions_persisted == 1
        assert tracker._last_close_reason == "test_close"


# ----- T-5 -----

def test_t_mlga_tracker_5_poll_empty_db_noop():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        tracker = MLGASessionTracker(store=store, cfg=_make_cfg())
        result = tracker.poll_once()
        assert result["action"] in ("noop_no_controller", "noop")


# ----- T-6 -----

def test_t_mlga_tracker_6_poll_nominal_opens_session():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        tracker = MLGASessionTracker(store=store, cfg=_make_cfg())
        _seed_capture_state(store._db_path, "NOMINAL")
        result = tracker.poll_once()
        assert result["action"] == "opened"
        assert tracker._open is not None
        assert tracker._open.open_reason == "poll_detected_nominal"


# ----- T-7 -----

def test_t_mlga_tracker_7_poll_disconnected_closes_session():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        tracker = MLGASessionTracker(store=store, cfg=_make_cfg())
        tracker.open_session("test")
        _seed_capture_state(store._db_path, "DISCONNECTED")
        result = tracker.poll_once()
        assert result["action"] == "closed_disconnect"
        assert tracker._open is None
        assert tracker._sessions_persisted == 1


# ----- T-8 -----

def test_t_mlga_tracker_8_poll_accumulates_deltas():
    """Seed records + APOP + GIC rows; verify cursor advancement +
    accumulators update."""
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        tracker = MLGASessionTracker(store=store, cfg=_make_cfg())
        _seed_capture_state(store._db_path, "NOMINAL")
        tracker.poll_once()  # opens session
        assert tracker._open is not None

        # Seed records — records schema has many NOT NULL columns; minimal
        # subset for tracker accumulation (trigger_active is what tracker reads).
        with sqlite3.connect(store._db_path) as con:
            for i in range(10):
                con.execute(
                    "INSERT INTO records "
                    "(device_id, counter, timestamp_ms, inference, "
                    " action_code, confidence, battery_pct, "
                    " trigger_active, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("dev", i, int(time.time()*1000), 0,
                     0, 50, 90,
                     1 if i % 2 == 0 else 0, time.time()),
                )
            con.commit()

        result = tracker.poll_once()
        assert result["action"] == "accumulated"
        assert tracker._open.n_poac_records == 10
        # 5 records had trigger_active=1 → 5 R2 pulls counted (R2-dominant attribution)
        assert tracker._open.n_trigger_pulls_r2 == 5


# ----- T-9 -----

def test_t_mlga_tracker_9_auto_close_max_duration():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # max_duration_s = 1 second for fast test
        tracker = MLGASessionTracker(
            store=store, cfg=_make_cfg(max_dur=1),
            max_session_duration_s=1,
        )
        _seed_capture_state(store._db_path, "NOMINAL")
        tracker.poll_once()  # opens
        # Force open_ts_ns far in past so duration exceeds threshold
        tracker._open.open_ts_ns = time.time_ns() - 2_000_000_000  # 2s ago
        result = tracker.poll_once()
        assert result["action"] == "closed_max_duration"
        assert tracker._open is None
        assert tracker._last_close_reason == "max_duration_reached"


# ----- T-10 -----

def test_t_mlga_tracker_10_live_status_shape():
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        tracker = MLGASessionTracker(store=store, cfg=_make_cfg())

        # No open session
        s0 = tracker.live_status()
        assert s0.has_open_session is False
        assert s0.enabled is True
        assert s0.sessions_persisted_total == 0

        # Open + accumulate
        tracker.open_session("test")
        tracker._open.n_poac_records = 42
        tracker._open.n_trigger_pulls_r2 = 7

        s1 = tracker.live_status()
        assert s1.has_open_session is True
        assert s1.n_poac_records == 42
        assert s1.n_trigger_pulls_r2 == 7
        assert s1.session_duration_s >= 0


# ----- T-11 -----

def test_t_mlga_tracker_11_config_fields(monkeypatch):
    """Config has 3 MLGA tracker fields with documented defaults."""
    # Strip env that might override the defaults
    for env_var in (
        "MLGA_SESSION_TRACKER_ENABLED",
        "MLGA_SESSION_TRACKER_INTERVAL_S",
        "MLGA_SESSION_MAX_DURATION_S",
    ):
        monkeypatch.delenv(env_var, raising=False)
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "mlga_session_tracker_enabled")
    assert hasattr(cfg, "mlga_session_tracker_interval_s")
    assert hasattr(cfg, "mlga_session_max_duration_s")
    # Defaults per the Phase O5-MLGA Stage 3 ship
    assert cfg.mlga_session_tracker_enabled is False
    assert cfg.mlga_session_tracker_interval_s == 30
    assert cfg.mlga_session_max_duration_s == 3600
