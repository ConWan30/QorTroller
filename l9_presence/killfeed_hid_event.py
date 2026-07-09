"""QorTroller L9 — shared HID-lobe event schema + R2-onset detector (Increment B follow-on, HID lobe).

The screen lobe (killfeed_screen_event) turns a killfeed AUTHORED composite into an OUTCOME event on the
WGC frame-capture clock. This is its INPUT-lobe twin: it turns an R2 trigger rising-edge into an r2_onset
event on the DEVICE clock (the DualSense sensor timestamp, raw offset 28, uint32 @ 3 MHz — the same
timing-authoritative source the l2_ads path uses, which survives the ~1.2 s burst-drain that collapses the
consumption-loop clock). Both lobes' events feed ONE unified events_root (retina_session_root) and the
input->outcome causal-coherence assessment (retina_causal_coherence), so the KAS certificate binds a genuine
dual-lobe (screen+HID) root and the cross-lobe latency becomes measurable.

CLOCK DISCIPLINE: the onset t is the DEVICE-clock wall-corrected ms (DeviceClockL2Source's device->wall
anchor), NOT the ~1.2 s consumption tick. The device clock and the WGC frame-capture clock are BOTH wall-
anchored (to time.time()*1000), so the cross-lobe latency (screen frame-capture ts vs HID onset device ts) is
comparable — but only as well as the two independent wall-anchors agree, so each onset ALSO stores its raw
device_ts + the reader wall_ms, keeping the anchor offset auditable offline. The coherence assessment stays
UNCALIBRATED (a hypothesis until co-capture validates the anchor agreement).

anti-splice framing: an r2_onset is an INPUT event (input_caused=False — causality is required OF outcomes,
not of the input that supplies it). It is the LIVE controller cause a replay-splice cannot produce on demand.
PURE: dict transforms + a rising-edge state machine; stdlib + DeviceClockL2Source only (no bridge/cv2/I/O).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .ads_coupling import DEFAULT_L2_THRESHOLD, DeviceClockL2Source

HID_EVENT_R2_ONSET = "r2_onset"
# the coherence engine's INPUT type for a trigger snap (retina_causal_coherence.INPUT_EVENT_TYPES)
COHERENCE_INPUT_TYPE = "controller.trigger.onset"


def hid_onset_event(*, t_ms: float, device_ts: Optional[int] = None, wall_ms: Optional[float] = None,
                    l2: Optional[int] = None, record_hash: Optional[str] = None) -> dict:
    """One R2 rising-edge -> canonical HID-lobe event mapping (feeds the unified events_root). t_ms is the
    DEVICE-clock wall-corrected ms (the alignment clock); device_ts (raw uint32) + wall_ms (reader wall clock)
    ride alongside so the device->wall anchor offset stays auditable against the screen lobe's WGC anchor.

    EVENT-BIND increment 2 (docs/event-bind-design-2026-07-09.md): `record_hash` is the live PoAC anchor
    stamped at capture time so this INPUT and its co-detected screen OUTCOME share a cryptographic bind
    (splice-proof), not clock proximity. KEY-ONLY-WHEN-STAMPED: absent record_hash -> the dict is
    byte-identical to pre-EVENT-BIND, so an unstamped session's events_root is UNCHANGED; a stamped
    session folds the anchor INTO the events_root/KAS commitment. Default None = stamping off."""
    ev = {
        "type": HID_EVENT_R2_ONSET,
        "t_ms": round(float(t_ms), 3),
        "device_ts": (int(device_ts) if device_ts is not None else None),   # raw uint32 (anchor audit)
        "wall_ms": (round(float(wall_ms), 3) if wall_ms is not None else None),
        "l2": (int(l2) if l2 is not None else None),
        # an r2_onset is the INPUT CAUSE, not an outcome that must itself be explained (see docstring)
        "input_caused": False,
    }
    if record_hash is not None:
        ev["record_hash"] = str(record_hash)   # the shared PoAC anchor (key-only-when-stamped)
    return ev


class HidOnsetDetector:
    """R2 rising-edge detector on the DEVICE clock. Wraps DeviceClockL2Source (reusing its unwrap + device->
    wall anchor) and emits an r2_onset event each time L2 crosses the threshold upward. Single-producer
    (the ~1 kHz raw hidapi reader calls push); the caller drains events off that hot thread. Fail-open: a
    malformed report never raises and never fabricates an onset."""

    def __init__(self, threshold: int = DEFAULT_L2_THRESHOLD, maxlen: int = 4096) -> None:
        self._src = DeviceClockL2Source()
        self._threshold = int(threshold)
        self._prev_l2: Optional[int] = None
        self._events: list[dict] = []
        self._maxlen = int(maxlen)
        self._onsets = 0
        self._record_hash: Optional[str] = None   # EVENT-BIND increment 2: current live PoAC anchor (or None)

    def set_record_hash(self, record_hash: Optional[str]) -> None:
        """EVENT-BIND increment 2: the daemon calls this when a new PoAC record is produced, so the NEXT
        r2_onset stamps that live record_hash (the shared anchor with the screen lobe). Default None =
        stamping off -> onsets are byte-identical to pre-EVENT-BIND. GIL-safe single scalar assignment."""
        self._record_hash = str(record_hash) if record_hash else None

    def push(self, wall_ms: float, ts_u32: int, l2: int) -> None:
        """Ingest one raw report (wall_ms, sensor_ts uint32, L2). Feeds the device-clock source, then folds
        the newly device-timestamped sample(s) through the rising-edge state machine. Never raises."""
        try:
            self._src.push_raw(wall_ms, ts_u32, l2)
            for wall_corrected, cur in self._src.drain():
                if self._prev_l2 is not None and self._prev_l2 < self._threshold <= cur:
                    # rising edge across the threshold -> R2 onset at the device-precise wall-corrected ms
                    self._events.append(hid_onset_event(t_ms=wall_corrected, device_ts=int(ts_u32) & 0xFFFFFFFF,
                                                         wall_ms=wall_ms, l2=cur,
                                                         record_hash=self._record_hash))
                    self._onsets += 1
                    if len(self._events) > self._maxlen:      # bound memory (drained periodically anyway)
                        self._events = self._events[-self._maxlen:]
                self._prev_l2 = cur
        except Exception:  # noqa: BLE001 — advisory; never break the raw reader on a bad report
            pass

    def drain_events(self) -> list[dict]:
        """Pop all buffered r2_onset events (oldest-first) for the caller to JSONL-append. GIL-safe for the
        single-producer/single-consumer handoff (the underlying source holds its own lock for the raw deque)."""
        out, self._events = self._events, []
        return out

    def onset_count(self) -> int:
        """Monotonic total of R2 onsets detected (never reset by drain_events). D-HIDW-1: the consumption
        loop polls this to detect device-clock R2 edges for inline-window opening + classify-burst arming —
        independent of the event buffer, so JSONL draining and edge detection cannot race each other."""
        return int(self._onsets)

    def stats(self) -> dict:
        d = {"hid_onsets": self._onsets, "hid_events_buffered": len(self._events)}
        d.update({"hid_devclock_" + k: v for k, v in self._src.stats().items()})
        return d


def session_hid_events(raw_onsets, *, span_ms: Optional[tuple] = None) -> list[dict]:
    """Stored r2_onset records (from retina_hid_events.jsonl) -> HID-lobe events feeding the unified root.
    Skips malformed rows (no numeric t_ms) and, if span_ms=(lo,hi) is given, rows outside the session span.
    Re-canonicalizes through hid_onset_event so a hand-edited sink can't smuggle extra fields into the root."""
    out: list[dict] = []
    lo, hi = (span_ms if span_ms else (None, None))
    for r in raw_onsets or []:
        t = r.get("t_ms") if isinstance(r, Mapping) else None
        if not isinstance(t, (int, float)):
            continue
        if lo is not None and not (lo <= t <= hi):
            continue
        out.append(hid_onset_event(t_ms=t, device_ts=r.get("device_ts"), wall_ms=r.get("wall_ms"),
                                   l2=r.get("l2"), record_hash=r.get("record_hash")))
    return out


def to_timed_event(event: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """HID-lobe event mapping -> causal-coherence TimedEvent kwargs (kind=input; t in SECONDS from the DEVICE
    t_ms). None if the event has no timestamp. Consumed by retina_causal_coherence.TimedEvent(**kwargs); its
    type is COHERENCE_INPUT_TYPE so assess_coherence counts it as a plausible play action."""
    if not event or event.get("t_ms") is None:
        return None
    return {"kind": "input", "type": COHERENCE_INPUT_TYPE, "t": float(event["t_ms"]) / 1000.0,
            "input_caused": False}
