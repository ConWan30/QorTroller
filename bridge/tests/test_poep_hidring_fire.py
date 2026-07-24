"""POEP-HID-RING bridge-half tests - request_poep_nonce_probe + _resolve_poep_fire (no HID, no rig).

Unbound-method pattern: the methods run against a SimpleNamespace fake self, so the 2700-line transport
never constructs. Covers: fail-closed gates (env / l6b_enabled / driver / controller), single-slot busy
(pending + inflight), amplitude clamp (never desk 255), arm shape (nonce/future/pre-snapshot/post-reset),
pre-write abort, resolver packing + no-op rails, and the CONTRACT integration - the bridge's resolved
dict drives the ACTUAL l9 BridgeFireCaptureAdapter end-to-end.
"""
import asyncio
from collections import deque
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.dualshock_integration import DualShockTransport, PoepFireRefused
from l9_presence.poep_bridge_fire_adapter import BridgeFireCaptureAdapter

_ENV = "POEP_LIVE_FIRE_ENABLED"


class _FakeDriver:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    async def send_l6b_probe(self, ds, r2_force, mode):
        if self.fail:
            raise RuntimeError("driver boom")
        self.calls.append((int(r2_force), str(mode)))
        return 123.456

    async def clear_triggers(self, ds):
        return None


def _fake(*, driver=None, l6b=True, analyzer=True, reader=True, pending=None, inflight=False):
    return SimpleNamespace(
        _l6b_enabled=l6b,
        _l6b_analyzer=object() if analyzer else None,
        _l6_driver=driver if driver is not None else _FakeDriver(),
        _reader=SimpleNamespace(ds=object()) if reader else None,
        _l6b_pending=pending,
        _l6b_post_buffer=["stale-post-frame"],
        _l6b_pre_buffer=deque([{"ax": 1.0}], maxlen=50),
        _poep_fire_inflight=inflight,
        _cfg=SimpleNamespace(l6b_probe_mode="pulse", l6b_probe_hold_ms=15),
        _POEP_FIRE_AMP_MAX=80,
    )


def _request(ns, nonce="nonce123", amp=60):
    return DualShockTransport.request_poep_nonce_probe(ns, nonce, amp)


def _resolve(ns, **kw):
    return DualShockTransport._resolve_poep_fire(ns, **kw)


# -- fail-closed gates ---------------------------------------------------------------------------
def test_env_gate_refuses(monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(_request(_fake()))
    assert ei.value.status_code == 503 and "gated" in str(ei.value)


def test_l6b_flag_gate_refuses(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(_request(_fake(l6b=False)))
    assert ei.value.status_code == 503 and "l6b_enabled" in str(ei.value)


def test_missing_driver_and_controller_refused(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    ns = _fake(analyzer=False)
    with pytest.raises(PoepFireRefused):
        asyncio.run(_request(ns))
    ns2 = _fake(reader=False)
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(_request(ns2))
    assert "not connected" in str(ei.value)


def test_busy_pending_and_inflight_409(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(_request(_fake(pending={"probe_ts": 1.0})))
    assert ei.value.status_code == 409
    with pytest.raises(PoepFireRefused) as ei2:
        asyncio.run(_request(_fake(inflight=True)))
    assert ei2.value.status_code == 409


def test_bad_nonce_400(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(_request(_fake(), nonce=""))
    assert ei.value.status_code == 400


# -- successful arm ------------------------------------------------------------------------------
def test_successful_fire_arms_nonce_bound_pending(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    ns = _fake()

    async def _run():
        fut = await _request(ns, nonce="n_abc", amp=255)   # desk 255 must clamp to 80
        p = ns._l6b_pending
        assert p is not None
        assert p["poep_nonce"] == "n_abc"
        assert isinstance(p["poep_t_fire_ns"], int) and p["poep_t_fire_ns"] > 0
        assert p["poep_future"] is fut and not fut.done()
        assert p["probe_r2_force"] == 80                    # gameplay LOW band ceiling
        assert p["frames_remaining"] == 350                 # same window as the auto-tick
        assert p["pre_reports"] == [{"ax": 1.0}]            # pre snapshot BEFORE the fire
        assert ns._l6b_post_buffer == []                    # post window reset at arm
        assert ns._poep_fire_inflight is False              # slot released after arm
        assert ns._l6_driver.calls == [(80, "pulse")]       # the real driver path, clamped

    asyncio.run(_run())


def test_pre_write_abort_releases_slot(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    ns = _fake(driver=_FakeDriver(fail=True))
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(_request(ns))
    assert "pre/at write" in str(ei.value)
    assert ns._l6b_pending is None                          # nothing armed
    assert ns._poep_fire_inflight is False                  # slot released


# -- resolver ------------------------------------------------------------------------------------
def test_resolver_packs_measured_features(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    ns = _fake()

    async def _run():
        fut = await _request(ns, nonce="n_pack")
        _resolve(ns, latency_ms=250.0, peak_lsb=3000.0, precursor_gap_ms=None)
        res = await asyncio.wait_for(fut, timeout=1.0)
        assert res["fired"] is True and res["real_hardware"] is True
        assert res["nonce"] == "n_pack"
        assert res["t_fire_ns"] == ns._l6b_pending["poep_t_fire_ns"]
        assert res["latency_ms"] == 250.0 and res["peak_lsb"] == 3000.0
        # second resolve is a no-op (future done) - never InvalidStateError
        _resolve(ns, latency_ms=1.0, peak_lsb=1.0, precursor_gap_ms=None)

    asyncio.run(_run())


def test_resolver_noop_for_auto_tick_probe():
    ns = _fake(pending={"probe_ts": 1.0, "frames_remaining": 10})   # no poep_future key
    _resolve(ns, latency_ms=100.0, peak_lsb=500.0, precursor_gap_ms=None)   # must not raise
    ns2 = _fake(pending=None)
    _resolve(ns2, latency_ms=100.0, peak_lsb=500.0, precursor_gap_ms=None)  # must not raise


# -- CONTRACT integration: the bridge dict drives the ACTUAL client adapter ----------------------
def test_bridge_contract_drives_client_adapter(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    ns = _fake()
    box = {}

    async def _run():
        fut = await _request(ns, nonce="n_e2e")
        _resolve(ns, latency_ms=250.0, peak_lsb=3000.0, precursor_gap_ms=5.0)
        box["result"] = await asyncio.wait_for(fut, timeout=1.0)

    asyncio.run(_run())

    # feed the bridge's resolved dict through the real l9 client (its post_fire IS this response)
    client = BridgeFireCaptureAdapter(post_fire=lambda amp, nonce: box["result"])
    fr = client.fire_fn(60, "n_e2e")
    assert fr.fired is True and fr.real_hardware is True
    win = client.imu_capture_fn(fr.t_fire_ns)
    assert win is not None and win.latency_ms == 250.0 and win.peak_lsb == 3000.0

    # honest-failure variant: analysis-failed packing (latency None) -> window with lat 0 -> verify fails
    async def _run_fail():
        ns2 = _fake()
        fut = await _request(ns2, nonce="n_fail")
        _resolve(ns2, latency_ms=None, peak_lsb=0.0, precursor_gap_ms=None,
                 error="l6b analysis failed (no score)")
        return await asyncio.wait_for(fut, timeout=1.0)

    res2 = asyncio.run(_run_fail())
    client2 = BridgeFireCaptureAdapter(post_fire=lambda amp, nonce: res2)
    fr2 = client2.fire_fn(60, "n_fail")
    assert fr2.fired is True and fr2.real_hardware is True      # the force DID fire
    win2 = client2.imu_capture_fn(fr2.t_fire_ns)
    assert win2.latency_ms == 0.0 and win2.peak_lsb == 0.0      # honest no-score -> verify will fail


# -- F-HIDRING-1 (grok r03): two-way exclusion race ----------------------------------------------
class _SlowDriver(_FakeDriver):
    """send_l6b_probe blocks on an event so a concurrent request can interleave mid-await."""

    def __init__(self):
        super().__init__()
        self.gate = asyncio.Event()

    async def send_l6b_probe(self, ds, r2_force, mode):
        await self.gate.wait()
        return await super().send_l6b_probe(ds, r2_force, mode)


def test_f_hidring_1_concurrent_request_mid_await_sees_409(monkeypatch):
    """The auto-tick sequence (as the session loop performs it post-fix: claim flag -> await fire ->
    arm -> release) is simulated; a poep request landing MID-AWAIT must 409 and clobber nothing."""
    monkeypatch.setenv(_ENV, "1")
    driver = _SlowDriver()
    ns = _fake(driver=driver)

    async def _auto_tick_sequence():
        # mirrors the fixed session-loop dispatch: claim -> fire -> arm -> release
        ns._poep_fire_inflight = True
        try:
            ts = await driver.send_l6b_probe(ns._reader.ds, r2_force=60, mode="pulse")
            if ns._l6b_pending is None:                       # the belt guard
                ns._l6b_pending = {"probe_ts": ts, "frames_remaining": 350}
        finally:
            ns._poep_fire_inflight = False

    async def _run():
        auto = asyncio.ensure_future(_auto_tick_sequence())
        await asyncio.sleep(0.01)                             # auto-tick is now mid-await (flag held)
        with pytest.raises(PoepFireRefused) as ei:
            await _request(ns, nonce="racer")
        assert ei.value.status_code == 409                    # two-way exclusion: mid-await sees busy
        driver.gate.set()
        await auto
        assert ns._l6b_pending["probe_ts"] == 123.456         # auto-tick's arm intact, nothing clobbered
        assert "poep_future" not in ns._l6b_pending           # no orphaned poep future
        assert ns._poep_fire_inflight is False                # slot released

    asyncio.run(_run())


def test_f_hidring_1_auto_tick_claims_flag_in_source():
    """Mechanical pin: the session-loop auto-tick dispatch claims + releases the inflight flag."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2]
           / "bridge" / "vapi_bridge" / "dualshock_integration.py").read_text(encoding="utf-8")
    dispatch = src.split("L6b probe dispatch failed")[0].split("Phase 63: L6b probe dispatch")[-1]
    assert "self._poep_fire_inflight = True" in dispatch      # claimed before the fire await
    assert "pending already armed during auto-tick dispatch" in src   # the belt guard exists
    # released in the dispatch finally (the completion path never touches the flag)
    tail = src.split("L6b probe dispatch failed")[1][:400]
    assert "self._poep_fire_inflight = False" in tail
