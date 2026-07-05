"""ClassifyBurstController tests — event-driven densification of maybe_classify_in_window.

Locks the load-bearing guarantees: arming opens a bounded high-frequency polling window, calls stop
once the window expires, sustained fire (repeated arm()) EXTENDS the window rather than restarting
it from a shorter point, and any single RGC call failure never breaks the loop (fail-open).
"""
import asyncio

from bridge.vapi_bridge.classify_burst import ClassifyBurstController


class MockRGC:
    """Records maybe_classify_in_window call timestamps; can be made to raise on demand."""

    def __init__(self, *, raises=False):
        self.calls = []
        self._raises = raises

    def maybe_classify_in_window(self, now_ms):
        if self._raises:
            raise RuntimeError("boom")
        self.calls.append(now_ms)


def _run(coro):
    return asyncio.run(coro)


def test_not_armed_by_default_is_inactive():
    c = ClassifyBurstController(MockRGC(), duration_ms=5000.0, poll_s=0.05)
    assert c.is_active is False


def test_arm_activates_and_expires_after_duration():
    import time
    c = ClassifyBurstController(MockRGC(), duration_ms=100.0, poll_s=0.05)
    c.arm(time.time() * 1000.0)
    assert c.is_active is True
    import time as _t
    _t.sleep(0.15)                     # past the 100ms duration
    assert c.is_active is False


def test_run_calls_rgc_while_armed_then_stops_calling_after_expiry():
    rgc = MockRGC()
    c = ClassifyBurstController(rgc, duration_ms=150.0, poll_s=0.03)

    async def drive():
        task = asyncio.ensure_future(c.run())
        import time
        c.arm(time.time() * 1000.0)
        await asyncio.sleep(0.25)      # well past the 150ms window
        n_during_and_after = len(rgc.calls)
        await asyncio.sleep(0.2)       # give it more time post-expiry
        c.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return n_during_and_after

    n = _run(drive())
    assert n >= 2                      # multiple calls happened during the armed window
    assert len(rgc.calls) == n         # NO further calls accumulated after expiry


def test_sustained_fire_extends_the_window_not_restarts_it():
    # arm() is called on EVERY rising edge (mark_onset's own semantics) -- each call sets an
    # absolute deadline, so repeated arming during sustained fire extends forward rather than
    # resetting to a fixed short window.
    import time
    c = ClassifyBurstController(MockRGC(), duration_ms=200.0, poll_s=0.05)
    t0 = time.time() * 1000.0
    c.arm(t0)
    first_deadline = c._armed_until_ms
    c.arm(t0 + 150.0)                  # a second rising edge before the first window closes
    assert c._armed_until_ms > first_deadline   # extended forward, not reset to a shorter point
    assert c._armed_until_ms == t0 + 150.0 + 200.0


def test_fail_open_rgc_exception_never_breaks_the_loop():
    rgc = MockRGC(raises=True)
    c = ClassifyBurstController(rgc, duration_ms=150.0, poll_s=0.03)

    async def drive():
        task = asyncio.ensure_future(c.run())
        import time
        c.arm(time.time() * 1000.0)
        await asyncio.sleep(0.1)       # several poll ticks, each one raising
        c.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    _run(drive())                      # no exception propagates out of the loop -> pass


def test_stop_ends_the_loop():
    rgc = MockRGC()
    c = ClassifyBurstController(rgc, duration_ms=5000.0, poll_s=0.02)

    async def drive():
        task = asyncio.ensure_future(c.run())
        import time
        c.arm(time.time() * 1000.0)
        await asyncio.sleep(0.05)
        c.stop()
        await asyncio.sleep(0.05)
        n_after_stop = len(rgc.calls)
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return n_after_stop

    n = _run(drive())
    assert n == len(rgc.calls)          # zero further calls once stop() fired
