"""Phase 80 — FederationBroadcastAgent: event-driven BLOCK ruling broadcaster.

KEY DISTINCTION: First purely event-driven agent in VAPI (no polling loop).
Subscribes to ruling_block_committed on AgentMessageBus. Broadcasts on receipt
— <100ms peer delivery vs 5-min polling lag.

W1 mitigation: INSERT into federation_threat_signals (broadcast_at=NULL) BEFORE
broadcasting to peers. On startup: recover unbroadcast=NULL rows.
Network partition cannot cause silent loss.

Anti-fingerprinting: broadcasts {device_id, commitment_hash, circuit_id} only.
Dedup: UNIQUE INDEX on commitment_hash — replay attacks rejected by DB constraint.
"""

import asyncio
import json
import logging
import time
from hashlib import sha256
import hmac as _hmac

log = logging.getLogger(__name__)


class FederationBroadcastAgent:
    """Phase 80 — Event-driven BLOCK ruling broadcaster to peer bridge instances."""

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus

    def _get_peers(self) -> list:
        """Return list of configured peer URLs."""
        peers_str = getattr(self._cfg, "federation_broadcast_peers", "")
        if not peers_str:
            return []
        return [p.strip() for p in peers_str.split(",") if p.strip()]

    def _sign_payload(self, payload_bytes: bytes) -> str:
        """Compute HMAC-SHA256 signature for federation authentication."""
        key = getattr(self._cfg, "federation_broadcast_api_key", "vapi-federation-default")
        return _hmac.new(key.encode(), payload_bytes, sha256).hexdigest()

    async def run_event_consumer(self) -> None:
        """Event-driven consumer — subscribes to ruling_block_committed.

        No polling loop — purely interrupt-driven (first such agent in VAPI fleet).
        """
        log.info("FederationBroadcastAgent started (Phase 80) — event-driven only")
        if self._bus is None:
            log.warning("FederationBroadcastAgent: no bus — agent disabled (bus required)")
            return

        queue = await self._bus.subscribe("ruling_block_committed")
        await self._recover_unbroadcast()
        _consecutive_failures = 0
        while True:
            try:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                    await self._broadcast_to_peers(event["payload"])
                except asyncio.TimeoutError:
                    pass  # Normal — no events in this 60s window
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "FederationBroadcastAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("FederationBroadcastAgent: broadcast error: %s", exc)

    async def _recover_unbroadcast(self) -> None:
        """On startup: recover and retry unbroadcast signals from prior crash."""
        try:
            pending = self._store.get_unbroadcast_signals(limit=100)
            if pending:
                log.info(
                    "FederationBroadcastAgent: recovering %d unbroadcast signal(s)",
                    len(pending),
                )
                for row in pending:
                    payload = {
                        "device_id": row["device_id"],
                        "commitment_hash": row["commitment_hash"],
                        "circuit_id": row.get("circuit_id") or "",
                    }
                    await self._broadcast_to_peers(payload, signal_id=row["id"])
        except Exception as exc:
            log.warning("FederationBroadcastAgent: recovery failed: %s", exc)

    async def _broadcast_to_peers(self, payload: dict, signal_id: int = None) -> None:
        """Broadcast threat signal to all configured peers."""
        peers = self._get_peers()
        if not peers:
            log.debug("FederationBroadcastAgent: no peers configured — skipping broadcast")
            return

        # W1: Insert into DB before broadcast (prevent silent loss on network partition)
        if signal_id is None:
            try:
                signal_id = self._store.insert_threat_signal(
                    device_id=payload.get("device_id", ""),
                    commitment_hash=payload.get("commitment_hash", ""),
                    circuit_id=payload.get("circuit_id", ""),
                    source_peer=None,
                )
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    log.debug("FederationBroadcastAgent: duplicate commitment_hash — skipping")
                    return
                log.warning("FederationBroadcastAgent: DB insert failed: %s", exc)

        broadcast_payload = {
            "device_id": payload.get("device_id", ""),
            "commitment_hash": payload.get("commitment_hash", ""),
            "circuit_id": payload.get("circuit_id", ""),
            "source_peer": "self",
            "broadcast_at": time.time(),
        }
        payload_bytes = json.dumps(broadcast_payload, sort_keys=True).encode()
        sig = self._sign_payload(payload_bytes)
        api_key = getattr(self._cfg, "federation_broadcast_api_key", "")

        broadcast_ok = False
        for peer_url in peers:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{peer_url}/federation/threat-signal",
                        content=payload_bytes,
                        headers={
                            "Content-Type": "application/json",
                            "X-Federation-HMAC": sig,
                        },
                        params={"api_key": api_key},
                    )
                    if resp.status_code in (200, 201):
                        broadcast_ok = True
                        log.info(
                            "FederationBroadcastAgent: broadcast to %s OK (device=%s)",
                            peer_url, broadcast_payload["device_id"][:12],
                        )
                    else:
                        log.warning(
                            "FederationBroadcastAgent: peer %s returned %d",
                            peer_url, resp.status_code,
                        )
            except ImportError:
                log.warning("FederationBroadcastAgent: httpx not installed — cannot broadcast")
                break
            except Exception as exc:
                log.warning("FederationBroadcastAgent: peer %s failed: %s", peer_url, exc)

        # Mark as broadcast if at least one peer succeeded
        if broadcast_ok and signal_id is not None:
            try:
                self._store.mark_threat_signal_broadcast(signal_id)
            except Exception as exc:
                log.debug("FederationBroadcastAgent: mark_broadcast failed: %s", exc)
