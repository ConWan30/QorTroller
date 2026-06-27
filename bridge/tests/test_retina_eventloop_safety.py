"""Phase 0 — Trio-Retina controller-lobe hook event-loop safety.

The advisory perception hook runs inside the async ``_session_loop``. Its heavy work
(numpy embed + state-commitment in ``run_controller_perception``; SQLite/provenance in
``persist_retina_result``) MUST be offloaded via ``asyncio.to_thread`` so it never stalls
the ingestion event loop (Phase 235-EVENTLOOP discipline; same rule as the STABILITY-arc
on_record/_resolve_pubkey offloads). These tests pin that property + the fail-open rail.

Pure unit tests over ``DualShockTransport._run_retina_perception_hook`` with a fake self —
no controller, no real store, no full transport construction.
"""
from __future__ import annotations

import asyncio
import threading
import types

from vapi_bridge import retina_depin_policy, retina_perception
from vapi_bridge.dualshock_integration import DualShockTransport
from vapi_bridge.retina_perception import RetinaPerceptionResult


class _FakeCfg:
    retina_perception_enabled = True
    retina_perception_window = 4
    retina_dynamics_horizon = 2
    retina_events_root_poseidon_enabled = False


class _FakeStore:
    def __init__(self):
        self.persisted = []

    def insert_retina_event_batch(self, **kw):
        self.persisted.append(kw)
        return 1


def _fake_transport():
    t = types.SimpleNamespace()
    t._cfg = _FakeCfg()
    t._device_id_hex = "de" * 16
    t._device_id = None
    t._retina_snap_ring = []  # content irrelevant; perception is patched
    t._pending_pitl_meta = {}
    t._store = _FakeStore()
    return t


def test_retina_hook_offloads_heavy_work_to_thread(monkeypatch):
    """run_controller_perception + persist_retina_result execute on a worker thread,
    NOT the coroutine's (event-loop) thread."""
    seen: dict[str, int] = {}

    def _probe_run(snap_buffer, **kw):
        seen["run_thread"] = threading.get_ident()
        return RetinaPerceptionResult(
            enabled=True,
            source_id=kw["source_id"],
            event_count=2,
            trajectory_anomalies=1,
            record_hash_hex=kw["record_hash_hex"],
            state_commitment_hex="abcd",
            events=[{"type": "controller.trigger.onset"}],
        )

    def _probe_persist(store, device_id, result, *, source="hid", cfg=None):
        seen["persist_thread"] = threading.get_ident()
        store.insert_retina_event_batch(device_id=device_id)

    monkeypatch.setattr(retina_perception, "run_controller_perception", _probe_run)
    monkeypatch.setattr(retina_perception, "persist_retina_result", _probe_persist)
    monkeypatch.setattr(retina_depin_policy, "get_runtime_policy_state", lambda: None)

    t = _fake_transport()

    async def _drive():
        seen["coro_thread"] = threading.get_ident()
        await DualShockTransport._run_retina_perception_hook(t, "cd" * 16)

    asyncio.run(_drive())

    # the offload guarantee: heavy work ran off the event-loop thread
    assert seen["run_thread"] != seen["coro_thread"]
    assert seen["persist_thread"] != seen["coro_thread"]
    # PITL meta attached on the loop after the await
    assert t._pending_pitl_meta["retina_enabled"] is True
    assert t._pending_pitl_meta["retina_trajectory_anomalies"] == 1
    assert t._pending_pitl_meta["retina_alert"] is True
    assert t._pending_pitl_meta["retina_source"] == "hid"
    # persisted through the threaded path
    assert t._store.persisted


def test_retina_hook_is_fail_open(monkeypatch):
    """A perception error never propagates out of the hook (advisory layer must not
    break ingestion), and leaves PITL meta untouched."""
    def _boom(snap_buffer, **kw):
        raise RuntimeError("synthetic perception failure")

    monkeypatch.setattr(retina_perception, "run_controller_perception", _boom)
    monkeypatch.setattr(retina_depin_policy, "get_runtime_policy_state", lambda: None)

    t = _fake_transport()

    async def _drive():
        await DualShockTransport._run_retina_perception_hook(t, "cd" * 16)

    asyncio.run(_drive())  # must not raise

    assert t._pending_pitl_meta == {}  # error before attach -> nothing written
    assert t._store.persisted == []
