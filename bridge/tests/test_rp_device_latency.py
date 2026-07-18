"""F-RIG27-8 device-clock reflex latency tests (grok rplatency r02→r04).

The reflex analyzer computes latency from bridge t_mono (inflated 3-15x under RP's bursty frame reads).
This adds an ADDITIVE device-sensor-clock companion: the DualSense on-device sensor timestamp is a raw
uint32 counter @ ~3MHz (states[28:32], surfaced on InputSnapshot.sensor_ts_ticks and threaded through
`device_ts` on each l6b report). The analyzer captures crossing_device_ts (canonical latency /
classification BYTE-STABLE); the resolve prefers the device latency = wrap_u32(crossing - probe) / 3000
when the fail-closed rails pass, else falls back to t_mono. Device ts is RAW TICKS end-to-end; the
helper is the only place ticks become ms.
"""
from bridge.controller.l6b_reflex_analyzer import L6bReflexAnalyzer
from bridge.vapi_bridge.dualshock_integration import (
    _rp_device_latency_ms,
    _DEVICE_TS_TICKS_PER_MS,
    _U32,
)

_TPMS = _DEVICE_TS_TICKS_PER_MS   # 3000 ticks / ms


def _rep(mag, t_mono, device_ts):
    # a report the analyzer reads: accel magnitude via ax + baseline 0 (ay=az=0); device_ts = raw ticks
    return {"ax": mag, "ay": 0.0, "az": 0.0, "t_mono": t_mono, "device_ts": device_ts}


# ── the helper rails (ticks -> ms, wrap-safe) ─────────────────────────────────
def test_helper_valid_span_ticks():
    # 180ms = 540_000 ticks
    assert _rp_device_latency_ms(1_540_000, 1_000_000) == 180.0
    assert _rp_device_latency_ms(1_000_000 + int(200 * _TPMS), 1_000_000) == 200.0


def test_helper_both_ends_required():
    assert _rp_device_latency_ms(-1.0, 1_000_000) == -1.0     # no crossing (sentinel)
    assert _rp_device_latency_ms(1_540_000, 0) == -1.0        # no probe device_ts (0 = absent)
    assert _rp_device_latency_ms(0, 0) == -1.0


def test_helper_frozen_or_duplicate_stream_rejected():
    # a FROZEN / duplicate device ts (probe == crossing) -> span 0 ticks -> reject (fall back to t_mono)
    assert _rp_device_latency_ms(1_000_000, 1_000_000) == -1.0


def test_helper_rejects_implausible_and_bad_types():
    assert _rp_device_latency_ms(1_000_000 + int(600 * _TPMS), 1_000_000) == -1.0  # 600ms > 500 max
    assert _rp_device_latency_ms("x", 1.0) == -1.0                                  # non-numeric
    assert _rp_device_latency_ms(_U32, 1_000_000) == -1.0                           # crossing not u32
    assert _rp_device_latency_ms(1_540_000, _U32 + 5) == -1.0                       # probe not u32


def test_helper_wrap_u32_recovers_rollover_span():
    # the ~24-min uint32 rollover: probe near the top, crossing just after the wrap, true span 180ms.
    probe = _U32 - 300_000
    crossing = (probe + int(180 * _TPMS)) % _U32     # = 240_000 after wrap
    assert crossing < probe                          # crossing numerically SMALLER (wrapped)
    assert _rp_device_latency_ms(crossing, probe) == 180.0   # wrap_u32 recovers the true span


def test_helper_regressed_ts_not_a_wrap_is_rejected():
    # a small backward step (stale/replayed ts, NOT a real rollover) wraps to a huge span -> reject
    assert _rp_device_latency_ms(1_000_000 - 30, 1_000_000) == -1.0


# ── the analyzer captures crossing_device_ts ADDITIVELY (canonical byte-stable) ──
def test_analyzer_captures_device_ts_additively():
    an = L6bReflexAnalyzer(human_min_ms=80.0, human_max_ms=280.0, accel_delta_threshold_lsb=500.0)
    probe_ts = 100.0
    # pre baseline ~0; a crossing at post index 2 (delta 3000 > 500), device_ts (ticks) at crossing
    pre = [_rep(0.0, 99.0, 1_000_000)]
    post = [_rep(10.0, 100.1, 1_030_000), _rep(50.0, 100.2, 1_060_000),
            _rep(3000.0, 100.25, 1_100_000), _rep(3000.0, 100.3, 1_150_000)]
    r = an.analyze(pre, post, probe_ts)
    assert r.accel_delta_peak >= 3000.0                     # real reflex captured
    assert r.crossing_device_ts == 1_100_000               # device ticks at the crossing frame
    # canonical (t_mono) path unchanged: true_latency computed from crossing_t_mono - probe_ts
    assert r.true_latency_ms == (100.25 - 100.0) * 1000.0  # 250ms via t_mono (unchanged)


def test_analyzer_device_ts_absent_stays_minus_one():
    an = L6bReflexAnalyzer(human_min_ms=80.0, human_max_ms=280.0, accel_delta_threshold_lsb=500.0)
    pre = [{"ax": 0.0, "ay": 0.0, "az": 0.0, "t_mono": 99.0}]           # no device_ts key
    post = [{"ax": 3000.0, "ay": 0.0, "az": 0.0, "t_mono": 100.2}]
    r = an.analyze(pre, post, 100.0)
    assert r.crossing_device_ts == -1.0                    # absent -> stays -1 (t_mono path identical)
    assert r.true_latency_ms > 0.0                         # t_mono canonical still works


# ── THE FIX (integration): RP t_mono inflated, device clock in-band ───────────
def test_rp_lag_t_mono_inflated_device_in_band():
    an = L6bReflexAnalyzer(human_min_ms=80.0, human_max_ms=280.0, accel_delta_threshold_lsb=500.0)
    probe_ts = 100.0
    probe_device_ticks = 1_000_000
    # RP: the bridge PROCESSES the crossing frame ~3s late (t_mono 103.0), but the DEVICE stamped it
    # 180ms after the fire (device ticks 1_000_000 + 540_000). The reflex is real (peak 6000).
    crossing_ticks = probe_device_ticks + int(180 * _TPMS)
    pre = [_rep(0.0, 99.5, probe_device_ticks)]
    post = [_rep(20.0, 101.0, 1_030_000), _rep(6000.0, 103.0, crossing_ticks)]
    r = an.analyze(pre, post, probe_ts)
    t_mono_lat = r.true_latency_ms
    dev_lat = _rp_device_latency_ms(r.crossing_device_ts, probe_device_ticks)
    assert t_mono_lat == (103.0 - 100.0) * 1000.0          # 3000ms via t_mono (rig-3 pathology)
    assert dev_lat == 180.0                                 # 180ms via device clock — IN BAND
    assert 80.0 <= dev_lat <= 280.0 and not (80.0 <= t_mono_lat <= 280.0)


# ── the resolved-latency preference (device when valid, else t_mono) ──────────
def test_resolve_prefers_device_when_valid():
    # mirrors the completion-block choice: latency_ms = dev_lat if dev_lat>0 else analyzer latency
    dev_lat = _rp_device_latency_ms(1_000_000 + int(180 * _TPMS), 1_000_000)   # 180ms
    assert dev_lat > 0.0
    resolved = dev_lat if dev_lat > 0.0 else 3000.0
    assert resolved == 180.0
    # rails fail (absent probe) -> fall back to the analyzer's t_mono latency (honest, no fabrication)
    dev_bad = _rp_device_latency_ms(1_540_000, 0)
    resolved2 = dev_bad if dev_bad > 0.0 else 3000.0
    assert resolved2 == 3000.0


# ── THE LIVE WIRE (grok r03 BLOCK): poll() must actually populate sensor_ts_ticks ──
import struct
import sys
import types
from pathlib import Path

# match the codebase convention (dualshock_integration inserts controller/ on sys.path and imports
# the emulator as a top-level module — NOT as controller.dualshock_emulator).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "controller"))
from dualshock_emulator import DualSenseReader, InputSnapshot  # noqa: E402


def _fake_ds_state():
    """Minimal ds.state covering every attribute poll() reads (all neutral)."""
    _tp = types.SimpleNamespace(X=0, Y=0, isActive=False)
    return types.SimpleNamespace(
        cross=False, circle=False, square=False, triangle=False,
        L1=False, R1=False, L3=False, R3=False,
        DpadUp=False, DpadDown=False, DpadLeft=False, DpadRight=False,
        share=False, options=False, ps=False, touchBtn=False,
        LX=128, LY=128, RX=128, RY=128, L2_value=0, R2_value=0,
        trackPadTouch0=_tp, trackPadTouch1=_tp,
    )


def _fake_ds_with_states(tick_value: int, buf_len: int = 40):
    """A fake pydualsense handle whose normalized states buffer carries `tick_value` at offset 28."""
    buf = bytearray(buf_len)
    if buf_len >= 32:
        struct.pack_into('<I', buf, 28, tick_value & 0xFFFFFFFF)
    return types.SimpleNamespace(state=_fake_ds_state(), states=list(buf))


def _reader_with(ds):
    r = DualSenseReader()
    r.connected = True
    r.ds = ds
    r._is_edge = False
    r._accel_scale = 8192.0
    return r


def test_live_poll_populates_sensor_ts_ticks():
    # THE fix for grok r03 BLOCK: a real poll() reads states[28:32] as the device ts (not the
    # nonexistent InputSnapshot.timestamp_ms). This drives the actual poll() code path.
    ticks = 178_916_557                                     # arbitrary uint32
    r = _reader_with(_fake_ds_with_states(ticks))
    snap = r.poll()
    assert snap.sensor_ts_ticks == ticks                   # LIVE wire arms (was always 0 before r04)


def test_live_poll_short_states_leaves_ticks_zero():
    # states shorter than 32 (first-frame / truncated) -> sensor_ts_ticks stays 0 -> helper falls back.
    r = _reader_with(_fake_ds_with_states(999, buf_len=30))
    snap = r.poll()
    assert snap.sensor_ts_ticks == 0


def test_input_snapshot_serialize_byte_stable_with_new_field():
    # the additive sensor_ts_ticks field is NOT in serialize() -> the packed snapshot is byte-identical
    base = InputSnapshot()
    with_ticks = InputSnapshot(sensor_ts_ticks=178_916_557)
    assert base.serialize() == with_ticks.serialize()      # additive field never touches the wire


# ── END-TO-END through PRODUCTION code (grok r04 F3): real snap -> _build_l6b_report -> analyze -> helper ──
def test_integration_production_l6b_build_wires_device_ts_end_to_end():
    # closes F3: a real InputSnapshot carries sensor_ts_ticks; the PRODUCTION _build_l6b_report reads it
    # via getattr (NOT a re-implemented ternary) -> the real analyzer captures crossing_device_ts -> the
    # real helper yields the in-band device latency. A silent getattr-name typo in production fails HERE.
    from bridge.vapi_bridge.dualshock_integration import _build_l6b_report

    probe_ticks = 1_000_000
    crossing_ticks = probe_ticks + int(180 * _TPMS)        # 180ms device latency
    scale = 8192.0
    # real InputSnapshots: accel_z pinned to 0 so ||accel|| math is clean (default is 1.0 gravity)
    pre_snap = InputSnapshot(accel_x=0.0, accel_z=0.0, sensor_ts_ticks=probe_ticks)
    post_small = InputSnapshot(accel_x=0.0, accel_z=0.0, sensor_ts_ticks=probe_ticks + 30_000)
    post_cross = InputSnapshot(accel_x=1.0, accel_z=0.0, sensor_ts_ticks=crossing_ticks)  # 8192 LSB delta
    pre = [_build_l6b_report(pre_snap, scale, t_mono=99.5)]
    post = [_build_l6b_report(post_small, scale, t_mono=101.0),
            _build_l6b_report(post_cross, scale, t_mono=103.0)]
    # the probe device ts = last pre-frame's device_ts (production _probe_device_ts semantics)
    probe_device_ts = int(pre[-1]["device_ts"])
    assert probe_device_ts == probe_ticks                  # production getattr wired sensor_ts_ticks->device_ts
    an = L6bReflexAnalyzer(human_min_ms=80.0, human_max_ms=280.0, accel_delta_threshold_lsb=500.0)
    r = an.analyze(pre, post, 100.0)
    assert r.accel_delta_peak >= 8000.0                    # real crossing captured
    assert r.crossing_device_ts == crossing_ticks          # analyzer captured the crossing device ticks
    dev_lat = _rp_device_latency_ms(r.crossing_device_ts, probe_device_ts)
    assert dev_lat == 180.0                                 # in-band device latency, end-to-end
    # t_mono canonical stays inflated (rig pathology) -> proves the device path is the fix, not luck
    assert r.true_latency_ms == (103.0 - 100.0) * 1000.0 and not (80.0 <= r.true_latency_ms <= 280.0)


def test_integration_production_build_absent_ticks_falls_back():
    # a frame with NO sensor_ts_ticks (default 0) -> device_ts 0 -> helper -1 -> t_mono fallback (honest)
    from bridge.vapi_bridge.dualshock_integration import _build_l6b_report

    snap = InputSnapshot(accel_x=1.0, accel_z=0.0)          # sensor_ts_ticks defaults to 0
    entry = _build_l6b_report(snap, 8192.0, t_mono=100.2)
    assert entry["device_ts"] == 0                          # absent ticks -> 0
    assert _rp_device_latency_ms(entry["device_ts"], 1_000_000) == -1.0   # both-ends rail -> fallback
