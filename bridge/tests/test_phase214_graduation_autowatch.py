"""
Phase 214 — GraduationAutowatchBridge tests (WIF-041 mitigation)

T214-1  graduation_autowatch_enabled defaults True in config
T214-2  graduation_autowatch_log table created by schema migration
T214-3  insert_graduation_autowatch_log() / get_graduation_autowatch_status() store round-trip
T214-4  SeparationRatioMonitorAgent._all_pairs_prev initialises False
T214-5  _check_all_pairs_transition() fires when all_pairs_above_1 changes False→True
T214-6  _check_all_pairs_transition() does NOT re-fire on consecutive True (one-shot per crossing)
T214-7  StagedDryRunGraduationAgent._check_autowatch_triggers() evaluates unprocessed entries
T214-8  GET /agent/graduation-autowatch-status endpoint returns 6 required keys
"""

from __future__ import annotations

import json
import tempfile
import time
import os

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path: str):
    """Return an initialised Store backed by a temp SQLite database."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
    from bridge.vapi_bridge.store import Store
    db_path = os.path.join(tmp_path, "test_p214.db")
    return Store(db_path)


def _make_cfg(**overrides):
    """Return a minimal config-like namespace with Phase 214 fields."""
    defaults = {
        "graduation_autowatch_enabled": True,
        "staged_graduation_enabled": False,
        "graduation_rollback_window_sessions": 10,
        "graduation_fp_threshold": 2,
        "graduation_poll_interval_s": 600,
        "live_feature_dim": 13,
    }
    defaults.update(overrides)

    class _Cfg:
        pass

    cfg = _Cfg()
    for k, v in defaults.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# T214-1  graduation_autowatch_enabled defaults True in config
# ---------------------------------------------------------------------------
def test_graduation_autowatch_enabled_default():
    """graduation_autowatch_enabled should default True (always-on monitoring)."""
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.graduation_autowatch_enabled is True, (
        "graduation_autowatch_enabled must default True (Phase 214 -- always-on)"
    )


# ---------------------------------------------------------------------------
# T214-2  graduation_autowatch_log table created by schema migration
# ---------------------------------------------------------------------------
def test_graduation_autowatch_log_table_created():
    """Schema migration must create graduation_autowatch_log table."""
    tmp = tempfile.mkdtemp()
    store = _make_store(tmp)
    with store._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='graduation_autowatch_log'"
        ).fetchone()
    assert row is not None, "graduation_autowatch_log table must exist after migration"

    # Schema version 214 must be recorded
    with store._conn() as conn:
        sv = conn.execute(
            "SELECT phase FROM schema_versions WHERE phase=214"
        ).fetchone()
    assert sv is not None, "schema_versions must record phase=214"


# ---------------------------------------------------------------------------
# T214-3  store round-trip insert/get
# ---------------------------------------------------------------------------
def test_graduation_autowatch_store_round_trip():
    """insert_graduation_autowatch_log and get_graduation_autowatch_status round-trip."""
    tmp = tempfile.mkdtemp()
    store = _make_store(tmp)

    # Insert a trigger event
    row_id = store.insert_graduation_autowatch_log(
        probe_type="tremor_resting",
        ratio=1.177,
        all_pairs_above_1=True,
        trigger_fired=True,
    )
    assert isinstance(row_id, int) and row_id > 0

    status = store.get_graduation_autowatch_status()
    assert status["trigger_count"] == 1
    assert status["evaluated_count"] == 0
    assert status["last_trigger_probe_type"] == "tremor_resting"
    assert abs(status["last_trigger_ratio"] - 1.177) < 0.001

    # Insert an evaluation entry
    store.insert_graduation_autowatch_log(
        probe_type="tremor_resting",
        ratio=1.177,
        all_pairs_above_1=True,
        trigger_fired=False,
        preconditions_evaluated=True,
        preconditions_met=False,
        blockers_json=json.dumps(["staged_graduation_enabled=False"]),
    )
    status2 = store.get_graduation_autowatch_status()
    assert status2["evaluated_count"] == 1
    assert status2["last_preconditions_met"] is False
    assert "staged_graduation_enabled=False" in status2["last_blockers"]


# ---------------------------------------------------------------------------
# T214-4  SeparationRatioMonitorAgent._all_pairs_prev initialises False
# ---------------------------------------------------------------------------
def test_separation_ratio_monitor_all_pairs_prev_init():
    """SeparationRatioMonitorAgent must initialise _all_pairs_prev=False (Phase 214)."""
    from bridge.vapi_bridge.separation_ratio_monitor_agent import SeparationRatioMonitorAgent

    cfg = _make_cfg()
    tmp = tempfile.mkdtemp()
    store = _make_store(tmp)
    agent = SeparationRatioMonitorAgent(cfg=cfg, store=store, bus=None)
    assert hasattr(agent, "_all_pairs_prev"), "_all_pairs_prev attribute must exist"
    assert agent._all_pairs_prev is False, "_all_pairs_prev must initialise False"


# ---------------------------------------------------------------------------
# T214-5  _check_all_pairs_transition fires on False->True crossing
# ---------------------------------------------------------------------------
def test_all_pairs_transition_fires_on_crossing():
    """_check_all_pairs_transition() must insert log entry when all_pairs changes False->True."""
    import asyncio
    from bridge.vapi_bridge.separation_ratio_monitor_agent import SeparationRatioMonitorAgent

    tmp = tempfile.mkdtemp()
    store = _make_store(tmp)
    cfg = _make_cfg(graduation_autowatch_enabled=True)
    agent = SeparationRatioMonitorAgent(cfg=cfg, store=store, bus=None)

    # Seed defensibility log with all_pairs_above_1=True
    store.insert_separation_defensibility_log(
        session_type="tremor_resting",
        n_sessions_total=28,
        ratio=1.177,
        n_per_player={"P1": 10, "P2": 9, "P3": 9},
        min_n_per_player=10,
        all_pairs_above_1=True,
        defensible=True,
    )

    # Run the transition check -- should detect False->True
    asyncio.get_event_loop().run_until_complete(agent._check_all_pairs_transition())

    status = store.get_graduation_autowatch_status()
    assert status["trigger_count"] >= 1, (
        "_check_all_pairs_transition must insert trigger entry when all_pairs changes False->True"
    )
    assert agent._all_pairs_prev is True


# ---------------------------------------------------------------------------
# T214-6  _check_all_pairs_transition does NOT re-fire on consecutive True
# ---------------------------------------------------------------------------
def test_all_pairs_transition_no_refire():
    """Consecutive True states must NOT re-fire graduation_readiness_check."""
    import asyncio
    from bridge.vapi_bridge.separation_ratio_monitor_agent import SeparationRatioMonitorAgent

    tmp = tempfile.mkdtemp()
    store = _make_store(tmp)
    cfg = _make_cfg(graduation_autowatch_enabled=True)
    agent = SeparationRatioMonitorAgent(cfg=cfg, store=store, bus=None)
    # Simulate already-transitioned state
    agent._all_pairs_prev = True

    store.insert_separation_defensibility_log(
        session_type="tremor_resting",
        n_sessions_total=31,
        ratio=1.2,
        n_per_player={"P1": 11, "P2": 10, "P3": 10},
        min_n_per_player=10,
        all_pairs_above_1=True,
        defensible=True,
    )

    asyncio.get_event_loop().run_until_complete(agent._check_all_pairs_transition())

    status = store.get_graduation_autowatch_status()
    assert status["trigger_count"] == 0, (
        "No new trigger should fire when all_pairs was already True (no transition)"
    )


# ---------------------------------------------------------------------------
# T214-7  StagedDryRunGraduationAgent._check_autowatch_triggers evaluates entries
# ---------------------------------------------------------------------------
def test_staged_graduation_auto_evaluates_triggers():
    """_check_autowatch_triggers() must evaluate unprocessed trigger entries."""
    from bridge.vapi_bridge.staged_dry_run_graduation_agent import StagedDryRunGraduationAgent

    tmp = tempfile.mkdtemp()
    store = _make_store(tmp)
    cfg = _make_cfg(
        graduation_autowatch_enabled=True,
        staged_graduation_enabled=False,
    )
    agent = StagedDryRunGraduationAgent(cfg=cfg, store=store, bus=None)

    # Insert an unevaluated trigger
    store.insert_graduation_autowatch_log(
        probe_type="tremor_resting",
        ratio=1.177,
        all_pairs_above_1=True,
        trigger_fired=True,
        preconditions_evaluated=False,
    )

    agent._check_autowatch_triggers()

    status = store.get_graduation_autowatch_status()
    assert status["evaluated_count"] >= 1, (
        "_check_autowatch_triggers must produce evaluated entry"
    )
    # staged_graduation_enabled=False so preconditions_met must be False
    assert status["last_preconditions_met"] is False


# ---------------------------------------------------------------------------
# T214-8  GET /agent/graduation-autowatch-status returns 6 required keys
# ---------------------------------------------------------------------------
def test_graduation_autowatch_endpoint_keys():
    """GET /agent/graduation-autowatch-status must return 6 required keys."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
    from fastapi.testclient import TestClient
    from bridge.vapi_bridge.store import Store
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.operator_api import create_operator_app

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "t214_8.db")
    store = Store(db_path)
    cfg = Config()

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.get("/agent/graduation-autowatch-status")
    assert resp.status_code == 200
    body = resp.json()
    required = {
        "graduation_autowatch_enabled",
        "trigger_count",
        "evaluated_count",
        "last_trigger_probe_type",
        "last_preconditions_met",
        "timestamp",
    }
    missing = required - set(body.keys())
    assert not missing, f"Endpoint missing keys: {missing}"
    assert body["graduation_autowatch_enabled"] is True
    assert body["trigger_count"] == 0
    assert body["evaluated_count"] == 0
