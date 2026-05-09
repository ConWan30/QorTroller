"""Phase 238 Step I-AUTOLOOP-3 — ProtocolStateCache.

In-memory aggregation hub for real-time protocol events that drive the
frontend Twin controller animations + dashboard pulses.  Sits between
the bridge's existing event producers (PoAC chain links, GIC verdicts,
PCC state changes, Curator verdicts, on-chain anchor confirmations)
and the SSE consumers (frontend EventSource clients).

Why this cache exists:
  - Frontend animations need ~real-time triggers (60 fps Twin scene)
  - HTTP polling cadences are 5-30s — too laggy for high-frequency events
  - Direct SQLite reads per SSE frame would revert Phase 235.x-STABILITY
    worker pool gains (~14s p95 stalls under polling load)
  - SSE fan-out from one in-memory ring buffer → many EventSource clients
    is the canonical solution

Performance invariants:
  - update_*() methods MUST be O(1) and never raise
  - All updates store in bounded deque (maxlen=100 per category) so
    memory is bounded
  - Subscribers receive events via asyncio.Queue.put_nowait — non-
    blocking; if a subscriber's queue is full (overwhelmed slow client),
    we drop the event for that subscriber (graceful degradation)
  - Heartbeat task fires every 15s to keep idle SSE connections alive
    (prevents proxy timeouts)
"""
from __future__ import annotations

import asyncio
import logging
import time as _t
from collections import deque
from typing import Optional

log = logging.getLogger(__name__)


# FROZEN event types — wire contract LOCKED for frontend consumption.
# Adding a new event type requires a v2 of this module + frontend update.
EVENT_POAC_CHAIN_LINK    = "poac_chain_link"
EVENT_GIC_VERDICT        = "gic_verdict"
EVENT_PCC_STATE_CHANGE   = "pcc_state_change"
EVENT_CURATOR_VERDICT    = "curator_verdict"
EVENT_ANCHOR_CONFIRMED   = "anchor_confirmed"
EVENT_HEARTBEAT          = "heartbeat"

FROZEN_EVENT_TYPES = frozenset({
    EVENT_POAC_CHAIN_LINK,
    EVENT_GIC_VERDICT,
    EVENT_PCC_STATE_CHANGE,
    EVENT_CURATOR_VERDICT,
    EVENT_ANCHOR_CONFIRMED,
    EVENT_HEARTBEAT,
})

# Per-category ring buffer cap (recent history for new SSE subscribers).
RING_BUFFER_CAP = 100

# Per-subscriber queue cap (drop events when slow client falls behind).
SUBSCRIBER_QUEUE_CAP = 200

# Heartbeat interval — keepalive for idle SSE connections.
HEARTBEAT_INTERVAL_S = 15.0


class ProtocolStateCache:
    """Singleton-style in-memory event hub.

    Attached to ``app._protocol_state_cache`` at bridge startup.  Producers
    call ``update_*()`` methods from any sync/async context; consumers
    register via ``subscribe()`` and read via ``async for event in queue``.
    """

    def __init__(self) -> None:
        # Bounded ring buffers per category (most-recent N events)
        self._buffers: dict[str, deque] = {
            EVENT_POAC_CHAIN_LINK:  deque(maxlen=RING_BUFFER_CAP),
            EVENT_GIC_VERDICT:      deque(maxlen=RING_BUFFER_CAP),
            EVENT_PCC_STATE_CHANGE: deque(maxlen=RING_BUFFER_CAP),
            EVENT_CURATOR_VERDICT:  deque(maxlen=RING_BUFFER_CAP),
            EVENT_ANCHOR_CONFIRMED: deque(maxlen=RING_BUFFER_CAP),
        }
        # Active SSE subscribers — each gets its own asyncio.Queue
        self._subscribers: list[asyncio.Queue] = []
        # Counters for telemetry / tests
        self.events_emitted: int = 0
        self.events_dropped: int = 0
        self.subscribers_registered: int = 0

    # ── Producer API (called from event sources) ────────────────────────

    def update_poac_link(self, hash16: str, ts_ns: Optional[int] = None) -> None:
        """Producer: PoAC chain link confirmed.  hash16 = first 16 chars of record_hash."""
        evt = {"hash16": str(hash16)[:16], "ts_ns": int(ts_ns or _t.time_ns())}
        self._emit(EVENT_POAC_CHAIN_LINK, evt)

    def update_gic_verdict(
        self, verdict: str, severity: str = "INFO",
        ts_ns: Optional[int] = None,
    ) -> None:
        """Producer: GIC verdict stamped on grind chain."""
        evt = {
            "verdict":  str(verdict),
            "severity": str(severity),
            "ts_ns":    int(ts_ns or _t.time_ns()),
        }
        self._emit(EVENT_GIC_VERDICT, evt)

    def update_pcc_state(
        self, capture_state: str, host_state: str,
        ts_ns: Optional[int] = None,
    ) -> None:
        """Producer: Physical Capture Continuity state change."""
        evt = {
            "capture_state": str(capture_state),
            "host_state":    str(host_state),
            "ts_ns":         int(ts_ns or _t.time_ns()),
        }
        self._emit(EVENT_PCC_STATE_CHANGE, evt)

    def update_curator_verdict(
        self, commitment16: str, verdict: str, severity: str = "INFO",
        ts_ns: Optional[int] = None,
    ) -> None:
        """Producer: Curator agent produced a review verdict."""
        evt = {
            "commitment16": str(commitment16)[:16],
            "verdict":      str(verdict),
            "severity":     str(severity),
            "ts_ns":        int(ts_ns or _t.time_ns()),
        }
        self._emit(EVENT_CURATOR_VERDICT, evt)

    def update_anchor(
        self, tx_hash: str, primitive_type: str,
        ts_ns: Optional[int] = None,
    ) -> None:
        """Producer: on-chain anchor transaction confirmed.

        primitive_type is one of: GIC, WEC, VAME, CORPUS-SNAPSHOT, CONSENT,
        BIOMETRIC-SNAPSHOT, SEPPROOF, LISTING-v1.
        """
        evt = {
            "tx_hash":        str(tx_hash),
            "primitive_type": str(primitive_type),
            "ts_ns":          int(ts_ns or _t.time_ns()),
        }
        self._emit(EVENT_ANCHOR_CONFIRMED, evt)

    # ── Consumer API (called from SSE endpoint) ─────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE subscriber.  Returns an asyncio.Queue that
        will receive (event_type, payload_dict) tuples as events fire.
        Caller MUST call ``unsubscribe(queue)`` on disconnect.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_CAP)
        self._subscribers.append(q)
        self.subscribers_registered += 1
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber.  Idempotent — silent on missing."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def recent(self, event_type: str, n: int = 10) -> list[dict]:
        """Read up to N most-recent events from the buffer for a category.
        Used by SSE endpoint to backfill a new client with recent history.
        """
        buf = self._buffers.get(event_type)
        if buf is None:
            return []
        # Most recent last in deque; reverse for DESC newest-first
        items = list(buf)
        return list(reversed(items[-int(n):]))

    def stats(self) -> dict:
        """Telemetry summary for tests + status endpoint."""
        return {
            "events_emitted":          int(self.events_emitted),
            "events_dropped":          int(self.events_dropped),
            "subscribers_active":      len(self._subscribers),
            "subscribers_registered":  int(self.subscribers_registered),
            "buffer_sizes":            {k: len(v) for k, v in self._buffers.items()},
        }

    # ── Internal fan-out ────────────────────────────────────────────────

    def _emit(self, event_type: str, payload: dict) -> None:
        """O(1) emit — append to ring buffer + fan out to subscribers.
        Never raises; slow subscribers drop the event silently.
        """
        try:
            buf = self._buffers.get(event_type)
            if buf is not None:
                buf.append(payload)
            self.events_emitted += 1
            # Fan out to subscribers (non-blocking)
            envelope = (event_type, payload)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(envelope)
                except asyncio.QueueFull:
                    self.events_dropped += 1
                except Exception:
                    # Queue may have been closed; remove silently on next gc
                    self.events_dropped += 1
        except Exception as exc:
            log.debug("ProtocolStateCache emit failed: %s", exc)


# ── Heartbeat task ──────────────────────────────────────────────────────────

async def run_heartbeat_loop(cache: ProtocolStateCache) -> None:
    """Heartbeat loop — emits a heartbeat event every 15s so idle SSE
    connections stay alive (prevents proxy timeouts).  Cancellation-safe.
    """
    log.info("ProtocolStateCache heartbeat loop starting (%.0fs interval)", HEARTBEAT_INTERVAL_S)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            try:
                # Heartbeat does NOT go through ring buffers; it only fans
                # out to current subscribers as a (heartbeat, {ts_ns}) envelope.
                envelope = (EVENT_HEARTBEAT, {"ts_ns": int(_t.time_ns())})
                for q in list(cache._subscribers):
                    try:
                        q.put_nowait(envelope)
                    except (asyncio.QueueFull, Exception):
                        pass
            except Exception as exc:
                log.debug("Heartbeat emit failed: %s", exc)
    except asyncio.CancelledError:
        log.info("ProtocolStateCache heartbeat loop cancelled; exiting cleanly")
        raise
