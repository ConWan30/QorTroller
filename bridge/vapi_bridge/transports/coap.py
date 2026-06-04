"""
CoAP Transport — Listens for PoAC records via CoAP POST.

Resource:
  POST /vapi/poac  — 228-byte binary PoAC record in request payload

CoAP is the preferred protocol for NB-IoT devices due to its minimal
overhead (4-byte header vs MQTT's variable-length header).
"""

import asyncio
import collections
import logging
import time

import aiocoap
import aiocoap.resource as resource

from ..codec import POAC_RECORD_SIZE
from ..config import Config

log = logging.getLogger(__name__)

# Per-remote-host rate limit. Sliding 60-second window, monotonic clock so
# wall-clock rollback cannot bypass the gate. Caps unauthenticated UDP DoS.
_COAP_RATE_RPM = 120
_COAP_WINDOW_S = 60.0
_COAP_MAX_HOSTS = 1024  # prevent unbounded memory growth from spoofed sources


class PoACResource(resource.Resource):
    """CoAP resource that accepts PoAC record submissions."""

    def __init__(self, on_record):
        super().__init__()
        self._on_record = on_record
        self._rate_windows: dict = {}

    def _rate_allow(self, host_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - _COAP_WINDOW_S
        dq = self._rate_windows.get(host_key)
        if dq is None:
            if len(self._rate_windows) >= _COAP_MAX_HOSTS:
                # Evict oldest tracked host (FIFO) before accepting a new one
                try:
                    oldest = next(iter(self._rate_windows))
                    self._rate_windows.pop(oldest, None)
                except StopIteration:
                    pass
            dq = collections.deque()
            self._rate_windows[host_key] = dq
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= _COAP_RATE_RPM:
            return False
        dq.append(now)
        return True

    async def render_post(self, request):
        host_key = getattr(request.remote, "hostinfo", "unknown")
        if not self._rate_allow(host_key):
            return aiocoap.Message(
                code=aiocoap.TOO_MANY_REQUESTS,
                payload=b"rate_limited",
            )
        payload = request.payload
        if len(payload) != POAC_RECORD_SIZE:
            return aiocoap.Message(
                code=aiocoap.BAD_REQUEST,
                payload=f"Expected {POAC_RECORD_SIZE} bytes, got {len(payload)}".encode(),
            )

        source = f"coap:{request.remote.hostinfo}"
        try:
            await self._on_record(bytes(payload), source)
            return aiocoap.Message(code=aiocoap.CHANGED, payload=b"OK")
        except Exception as e:
            log.error("CoAP record processing error: %s", e)
            return aiocoap.Message(
                code=aiocoap.INTERNAL_SERVER_ERROR,
                payload=str(e)[:100].encode(),
            )


class CoapTransport:
    """Async CoAP server for PoAC records."""

    def __init__(self, cfg: Config, on_record):
        self._cfg = cfg
        self._on_record = on_record

    async def run(self):
        """Start CoAP server and listen for records."""
        root = resource.Site()
        root.add_resource(
            ["vapi", "poac"], PoACResource(self._on_record)
        )

        bind = (self._cfg.coap_bind, self._cfg.coap_port)
        log.info("CoAP server starting on %s:%d", *bind)

        context = await aiocoap.Context.create_server_context(root, bind=bind)
        try:
            # Keep running until cancelled
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            log.info("CoAP transport shutting down")
            await context.shutdown()
            raise
