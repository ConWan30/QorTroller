"""Phase 235-PCC-PERSIST — keep capture_health_log fresh without API polling.

T235-PERSIST-1: stable live PCC state writes periodic snapshots to SQLite
T235-PERSIST-2: transition rows flush immediately without double-writing a snapshot
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _FakeStore:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def insert_capture_health_event(self, **kwargs):
        self.rows.append(dict(kwargs))
        return len(self.rows)


class _FakeMonitor:
    def __init__(self, status: dict, transitions: list[dict] | None = None) -> None:
        self._status = dict(status)
        self._transitions = list(transitions or [])

    def get_status(self) -> dict:
        return dict(self._status)

    def pop_transitions(self) -> list[dict]:
        out = list(self._transitions)
        self._transitions.clear()
        return out


class _FakeCfg:
    grind_mode = True
    grind_session_id = "grind_phase235_v1"
    prev_grind_session_id = "grind_phase235_v0"


pytestmark = pytest.mark.smoke


def test_t235_persist_1_periodic_snapshot_when_live_status_is_stable(monkeypatch):
    from vapi_bridge.pcc_persistence import persist_pcc_monitor_once

    store = _FakeStore()
    monitor = _FakeMonitor(
        {
            "capture_state": "NOMINAL",
            "host_state": "EXCLUSIVE_USB",
            "poll_rate_hz": 1002.4,
            "sample_count": 8,
        }
    )
    monkeypatch.setattr("vapi_bridge.pcc_persistence.time.monotonic", lambda: 10.0)

    last_ts = persist_pcc_monitor_once(
        store,
        monitor,
        _FakeCfg(),
        last_snapshot_monotonic=0.0,
        snapshot_interval_s=5.0,
    )

    assert last_ts == pytest.approx(10.0)
    assert len(store.rows) == 1
    assert store.rows[0]["transition_reason"] == "periodic_snapshot"
    assert store.rows[0]["capture_state"] == "NOMINAL"
    assert store.rows[0]["host_state"] == "EXCLUSIVE_USB"
    assert store.rows[0]["session_id"] == "grind_phase235_v1"


def test_t235_persist_2_transitions_flush_without_extra_snapshot(monkeypatch):
    from vapi_bridge.pcc_persistence import persist_pcc_monitor_once

    store = _FakeStore()
    monitor = _FakeMonitor(
        {
            "capture_state": "DISCONNECTED",
            "host_state": "UNKNOWN",
            "poll_rate_hz": 0.0,
            "sample_count": 8,
        },
        transitions=[
            {
                "new_state": "DISCONNECTED",
                "host_state": "UNKNOWN",
                "poll_rate_hz": 0.0,
                "reason": "hid_timeout",
            }
        ],
    )
    monkeypatch.setattr("vapi_bridge.pcc_persistence.time.monotonic", lambda: 25.0)

    last_ts = persist_pcc_monitor_once(
        store,
        monitor,
        _FakeCfg(),
        last_snapshot_monotonic=0.0,
        snapshot_interval_s=5.0,
    )

    assert last_ts == pytest.approx(25.0)
    assert len(store.rows) == 1
    assert store.rows[0]["transition_reason"] == "hid_timeout"
    assert store.rows[0]["capture_state"] == "DISCONNECTED"
