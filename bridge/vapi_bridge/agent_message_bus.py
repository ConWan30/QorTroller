"""Phase 79 — AgentMessageBus: in-process asyncio pub/sub for zero-latency agent coordination.

Publishers call:  await bus.publish(event_type, payload, source)
Subscribers call: queue = await bus.subscribe(event_type)
                  event = await asyncio.wait_for(queue.get(), timeout=60.0)

QueueFull is caught and logged (never raises to caller).
Multiple subscribers to the same event_type each receive a copy (fan-out).
SQLite agent_events remains the durable audit log — bus is fast path only.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

log = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 100


class AgentMessageBus:
    """In-process asyncio pub/sub for zero-latency agent-to-agent messaging.

    Backed by asyncio.Queue per topic (maxsize=100). SQLite agent_events is the
    durable persistence layer. The bus provides immediate delivery; the store
    provides persistence and replay.

    Publishers call: await bus.publish(event_type, payload, source)
    Subscribers call: queue = await bus.subscribe(event_type)
                      event = await asyncio.wait_for(queue.get(), timeout=60.0)

    QueueFull is caught and logged (never raises to caller).
    Multiple subscribers to the same event_type each receive a copy (fan-out).
    """

    def __init__(self):
        self._subs: dict = defaultdict(list)
        self._lock: Optional[asyncio.Lock] = None

    async def _init_lock(self) -> None:
        """Initialize asyncio.Lock — must be called after event loop is running."""
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str) -> asyncio.Queue:
        """Register a subscriber for event_type; returns a per-subscriber Queue."""
        await self._init_lock()
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        async with self._lock:
            self._subs[event_type].append(q)
        log.debug(
            "AgentMessageBus: new subscriber for '%s' (total=%d)",
            event_type, len(self._subs[event_type]),
        )
        return q

    async def publish(self, event_type: str, payload: dict, source: str) -> None:
        """Publish event_type to all subscribers (fan-out).

        Wraps payload into an envelope: {event_type, payload, source, ts}.
        QueueFull is caught per-subscriber — one slow consumer cannot block others.
        """
        await self._init_lock()
        envelope = {
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "ts": time.time(),
        }
        async with self._lock:
            queues = list(self._subs.get(event_type, []))
        delivered = 0
        for q in queues:
            try:
                q.put_nowait(envelope)
                delivered += 1
            except asyncio.QueueFull:
                log.warning(
                    "AgentMessageBus: QueueFull for event_type='%s' source='%s' — "
                    "subscriber is falling behind (event dropped)",
                    event_type, source,
                )
        if queues:
            log.debug(
                "AgentMessageBus: published '%s' from '%s' to %d/%d subscribers",
                event_type, source, delivered, len(queues),
            )

    def publish_sync(self, event_type: str, payload: dict, source: str) -> None:
        """Non-async variant for use from sync contexts.

        Uses call_soon_threadsafe if a running event loop is available,
        otherwise silently discards (safe fallback for test contexts).
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        self.publish(event_type, payload, source)
                    )
                )
        except Exception as exc:
            log.debug("AgentMessageBus.publish_sync: %s", exc)
