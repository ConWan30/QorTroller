"""RP-2c Fix B tests — window-gated burst densification.

Pins: the PURE cadence choice (_stash_every); flag-off = base cadence always
(byte-identical behavior); THE ANTI-SPLICE RAIL — density opens ONLY inside an
R2-propagated window, never from screen content; monitor.in_window predicate;
maybe_flush_burst_crop gates (flag / window / new-stash de-dup / capture-enabled).
"""
from __future__ import annotations

from types import SimpleNamespace

from bridge.vapi_bridge.qortroller_retina_capture import (
    RetinaGameCapture,
    _stash_every,
)
from l9_presence.killfeed_inline import InlineAuthorshipMonitor


def test_stash_every_flag_off_is_base_always():
    """burst_every=0 (default) -> base cadence regardless of any window state."""
    assert _stash_every(20, 0, 1000.0, 5000.0) == 20
    assert _stash_every(20, 0, 1000.0, 0.0) == 20


def test_stash_every_burst_inside_window_only():
    assert _stash_every(20, 5, 1000.0, 5000.0) == 5     # inside dense window
    assert _stash_every(20, 5, 6000.0, 5000.0) == 20    # past it -> base


def test_stash_every_never_zero():
    assert _stash_every(0, 0, 0.0, 0.0) == 1
    assert _stash_every(20, -3, 1000.0, 5000.0) == 20   # negative burst = off


def test_anti_splice_rail_screen_content_never_opens_density():
    """THE pinned rail: with NO R2-propagated dense window (dense_until=0), the burst
    cadence is unreachable no matter what 'appears on screen' — the only writer of
    dense_until_ms is mark_r2_onset (input side)."""
    for now in (0.0, 1.0, 1e12):
        assert _stash_every(20, 5, now, 0.0) == 20


def test_monitor_in_window_predicate():
    mon = InlineAuthorshipMonitor()
    assert not mon.in_window(1000.0)                     # no window yet
    mon.mark_onset(1000.0)
    gate, end = mon._window_gate_ms, mon._window_end_ms
    assert mon.in_window((gate + end) / 2)
    assert not mon.in_window(end + 1.0)


def _rgc(burst_every=5, capture_enabled=True, panel_ts=111.0, monitor=None):
    """Minimal RetinaGameCapture stand-in via __new__ — maybe_flush_burst_crop touches
    only these attributes."""
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)
    rgc._source = SimpleNamespace(_kf_burst_every=burst_every, _panel_ts=panel_ts)
    rgc._capture_enabled = capture_enabled
    rgc._inline_monitor = monitor
    rgc._last_burst_flush_ts = None
    rgc._flushes = []
    rgc.save_capture_crops = lambda: rgc._flushes.append(1)
    return rgc


def _open_monitor(now=1000.0):
    mon = InlineAuthorshipMonitor()
    mon.mark_onset(now)
    return mon, (mon._window_gate_ms + mon._window_end_ms) / 2


def test_flush_happens_inside_window_once_per_stash():
    mon, mid = _open_monitor()
    rgc = _rgc(monitor=mon)
    rgc.maybe_flush_burst_crop(mid)
    assert rgc._flushes == [1]
    rgc.maybe_flush_burst_crop(mid + 10)                 # same stash ts -> de-dup, no flush
    assert rgc._flushes == [1]
    rgc._source._panel_ts = 222.0                        # NEW stash -> flush again
    rgc.maybe_flush_burst_crop(mid + 20)
    assert rgc._flushes == [1, 1]


def test_flush_never_outside_window():
    mon, _ = _open_monitor()
    rgc = _rgc(monitor=mon)
    rgc.maybe_flush_burst_crop(mon._window_end_ms + 1.0)
    assert rgc._flushes == []


def test_flush_never_when_flag_off_or_capture_off():
    mon, mid = _open_monitor()
    rgc = _rgc(burst_every=0, monitor=mon)
    rgc.maybe_flush_burst_crop(mid)
    assert rgc._flushes == []
    rgc2 = _rgc(capture_enabled=False, monitor=mon)
    rgc2.maybe_flush_burst_crop(mid)
    assert rgc2._flushes == []


def test_flush_no_monitor_is_noop():
    rgc = _rgc(monitor=None)
    rgc.maybe_flush_burst_crop(1000.0)
    assert rgc._flushes == []
