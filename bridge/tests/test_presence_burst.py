"""PresenceBurstController tests — duty-cycle capture that coexists with the Remote Play stream.

Locks the load-bearing guarantees: a burst is start -> accumulate -> read -> STOP (the GPU is never left
held), bursts never overlap (single-flight), fail-open on start/status errors, and on-demand mode (period<=0)
does not auto-loop.
"""
import asyncio

from vapi_bridge.presence_burst import PresenceBurstController


class MockRGC:
    """RetinaGameCapture-like stub recording start/stop + max concurrent captures (must stay <= 1)."""

    def __init__(self, *, start_ret=True, start_raises=False, status_raises=False, status=None):
        self.started = 0
        self.stopped = 0
        self._conc = 0
        self.max_conc = 0
        self._start_ret = start_ret
        self._start_raises = start_raises
        self._status_raises = status_raises
        self._status = status or {"nqpv_verdict": "COUPLED_CLEAN", "coupling_score": 0.35,
                                  "negative_control": 0.03, "grid_samples": 500}

    def start(self):
        if self._start_raises:
            raise RuntimeError("boom")
        self.started += 1
        if self._start_ret:
            self._conc += 1
            self.max_conc = max(self.max_conc, self._conc)
        return self._start_ret

    def stop(self):
        self.stopped += 1
        if self._conc > 0:
            self._conc -= 1

    def status(self):
        if self._status_raises:
            raise RuntimeError("status boom")
        return dict(self._status)


def _run(coro):
    return asyncio.run(coro)


def test_fire_once_happy_starts_reads_stops():
    rgc = MockRGC()
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0)
    p = _run(c.fire_once())
    assert p["ok"] is True
    assert p["verdict"] == "COUPLED_CLEAN"
    assert p["coupling_score"] == 0.35 and p["negative_control"] == 0.03
    assert rgc.started == 1 and rgc.stopped == 1   # started then STOPPED -> GPU released
    assert rgc.max_conc == 1
    assert c.last_proof == p


def test_fire_once_always_stops_even_on_status_error():
    rgc = MockRGC(status_raises=True)
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0)
    p = _run(c.fire_once())
    assert p["ok"] is True          # burst ran; status unreadable -> verdict None
    assert p["verdict"] is None
    assert rgc.stopped == 1         # GPU is NEVER left held


def test_fire_once_start_fail_is_fail_open():
    rgc = MockRGC(start_ret=False)
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0)
    p = _run(c.fire_once())
    assert p["ok"] is False and p["reason"] == "capture_start_failed"
    assert rgc.stopped == 0         # never started -> nothing to stop


def test_fire_once_start_raises_is_fail_open():
    rgc = MockRGC(start_raises=True)
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0)
    p = _run(c.fire_once())
    assert p["ok"] is False and p["reason"].startswith("start_error")


def test_bursts_never_overlap_single_flight():
    rgc = MockRGC()
    c = PresenceBurstController(rgc, burst_s=0.05, period_s=0)

    async def two():
        return await asyncio.gather(c.fire_once(), c.fire_once())

    res = _run(two())
    assert all(p["ok"] for p in res)
    assert rgc.started == 2 and rgc.stopped == 2
    assert rgc.max_conc == 1         # the lock prevented overlapping captures


def test_run_periodic_on_demand_does_not_autoloop():
    rgc = MockRGC()
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0)   # period<=0 -> on-demand only
    _run(c.run_periodic())
    assert rgc.started == 0          # no automatic burst fired


def test_run_on_demand_fires_on_trigger_then_consumes_it(tmp_path):
    import os
    trig = str(tmp_path / "presence_trigger")
    open(trig, "w").close()                      # request a proof
    rgc = MockRGC()
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0, trigger_path=trig)

    async def drive():
        task = asyncio.ensure_future(c.run_on_demand(poll_s=0.05))
        await asyncio.sleep(0.5)                  # let it poll, fire, consume
        c.stop(); task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(drive())
    assert rgc.started >= 1 and rgc.stopped >= 1  # a proof burst fired
    assert not os.path.exists(trig)               # trigger consumed (one proof per request)


def test_run_on_demand_no_trigger_no_capture(tmp_path):
    trig = str(tmp_path / "never")               # file does NOT exist
    rgc = MockRGC()
    c = PresenceBurstController(rgc, burst_s=0.01, period_s=0, trigger_path=trig)

    async def drive():
        task = asyncio.ensure_future(c.run_on_demand(poll_s=0.05))
        await asyncio.sleep(0.3)
        c.stop(); task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(drive())
    assert rgc.started == 0                        # zero capture during normal play (no trigger)


# --- P1 decoupled-energy gate (default-off) -------------------------------------------------------------

class GatedMockRGC(MockRGC):
    """MockRGC + the P1 burst-gate surface (reset_burst_history / burst_gated_summary)."""

    def __init__(self, *, summary=None, **kw):
        super().__init__(**kw)
        self.reset_called = 0
        self.status_calls = 0
        self._summary = summary

    def status(self):
        self.status_calls += 1
        return super().status()

    def reset_burst_history(self):
        self.reset_called += 1

    def burst_gated_summary(self, keep_quantile=0.5):
        return self._summary


def test_de_gate_reads_summary_maps_verdict_and_stops():
    from types import SimpleNamespace
    summ = SimpleNamespace(coupled=True, representative_coupling=0.19, n_kept=2, n_total=4)
    rgc = GatedMockRGC(summary=summ)
    c = PresenceBurstController(rgc, burst_s=0.05, period_s=0, de_gate=True, sample_interval_s=0.01)
    p = _run(c.fire_once())
    assert p["ok"] is True and p.get("de_gated") is True
    assert p["verdict"] == "COUPLED_CLEAN"                 # gated median >= threshold
    assert p["coupling_score"] == 0.19 and p["n_kept"] == 2 and p["n_total"] == 4
    assert rgc.reset_called == 1                           # history reset at burst start
    assert rgc.status_calls >= 1                           # sampled during the burst (accumulates windows)
    assert rgc.stopped == 1                                # GPU released


def test_de_gate_below_threshold_is_implausible():
    from types import SimpleNamespace
    summ = SimpleNamespace(coupled=False, representative_coupling=0.03, n_kept=2, n_total=4)
    rgc = GatedMockRGC(summary=summ)
    c = PresenceBurstController(rgc, burst_s=0.03, period_s=0, de_gate=True, sample_interval_s=0.01)
    p = _run(c.fire_once())
    assert p["verdict"] == "IMPLAUSIBLE" and p["de_gated"] is True
    assert rgc.stopped == 1


def test_de_gate_no_windows_is_abstain_none():
    from types import SimpleNamespace
    summ = SimpleNamespace(coupled=False, representative_coupling=None, n_kept=0, n_total=0)
    rgc = GatedMockRGC(summary=summ)
    c = PresenceBurstController(rgc, burst_s=0.03, period_s=0, de_gate=True, sample_interval_s=0.01)
    p = _run(c.fire_once())
    assert p["verdict"] is None and p["de_gated"] is True  # no windows -> honest abstain
    assert rgc.stopped == 1
