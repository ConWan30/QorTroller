"""Protocol-Enforced Multi-Modal Attestation Ticker.

Runs on a configurable interval during active gameplay sessions,
collects outputs from all attestation channels, builds a cryptographic
attestation envelope, and records it to the database.

This is a read-only integration layer — it never modifies existing
components or protocol paths.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time as _time
from typing import Optional, Dict, Any, List, Callable, Awaitable

from .types import ChannelSnapshot, AttestationEnvelope
from .store import AttestationStore

log = logging.getLogger(__name__)


def _hash(data: Any) -> str:
    """SHA-256 hash of a JSON-serializable object."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()


class AttestationTicker:
    """Orchestrates the attestation loop during active gameplay sessions.

    Usage:
        ticker = AttestationTicker(db_path=SESSION_DB_PATH)
        ticker.watch_hardware(hardware_watcher)
        ticker.watch_protocol(protocol_state)
        ticker.watch_biometrics(reflex_concierge)
        ticker.watch_retina(retina_fusion)
        ticker.watch_vlm(retina_oracle)
        ticker.watch_fsca(contradiction_oracle)
        ticker.watch_pv_ci(invariant_sentinel)

        async def on_state_change(old, new):
            if new == "ALL_READY":
                await ticker.start(session_id)
            elif old == "ALL_READY":
                await ticker.stop()

        hardware_watcher.on_state_change = on_state_change
    """

    def __init__(
        self,
        store: AttestationStore,
        tick_interval: float = 1.0,
        on_envelope: Optional[Callable[[AttestationEnvelope], Awaitable[None]]] = None,
    ):
        self._store = store
        self._tick_interval = tick_interval
        self._on_envelope = on_envelope  # optional callback (e.g., for TUI display)

        # ── Channel readers (all optional) ────────────────
        self._readers: Dict[str, Callable[[], Any]] = {}

        # ── State ─────────────────────────────────────────
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._session_id: str = ""
        self._tick_count: int = 0
        self._last_envelope_hash: str = ""

    # ── Channel registration (all optional) ───────────────

    def watch_hardware(self, hardware_watcher) -> None:
        """Watch HardwareWatcher for DualShock/capture/bridge state."""
        self._readers["hardware"] = lambda: getattr(hardware_watcher, "last_state", None)

    def watch_protocol(self, protocol_state) -> None:
        """Watch ProtocolState for bridge health and PoAC state."""
        def _read_protocol():
            try:
                if hasattr(protocol_state, "bridge_health"):
                    return protocol_state.bridge_health()
                elif hasattr(protocol_state, "data"):
                    return protocol_state.data
                return None
            except Exception:
                return None
        self._readers["controller"] = _read_protocol

    def watch_biometrics(self, reflex_concierge) -> None:
        """Watch ReflexConcierge for PoEP separation ratio."""
        def _read_biometrics():
            try:
                if hasattr(reflex_concierge, "assess_operator_state"):
                    return reflex_concierge.assess_operator_state()
                return {
                    "separation_ratio": getattr(reflex_concierge, "_baseline_separation", None),
                    "adjustments": getattr(reflex_concierge, "_adjustments_made", 0),
                }
            except Exception:
                return None
        self._readers["biometrics"] = _read_biometrics

    def watch_retina(self, retina_fusion) -> None:
        """Watch ScreenRetinaFusion for dual-lobe output."""
        def _read_retina():
            try:
                if hasattr(retina_fusion, "last_analysis"):
                    return retina_fusion.last_analysis()
                return None
            except Exception:
                return None
        self._readers["retina"] = _read_retina

    def watch_vlm(self, retina_oracle) -> None:
        """Watch RetinaVisualOracle for VLM third-lobe observations."""
        def _read_vlm():
            try:
                if hasattr(retina_oracle, "last_observation"):
                    return retina_oracle.last_observation()
                elif hasattr(retina_oracle, "_last_observation"):
                    return retina_oracle._last_observation
                return None
            except Exception:
                return None
        self._readers["vlm"] = _read_vlm

    def watch_fsca(self, contradiction_oracle) -> None:
        """Watch ContradictionOracle for FSCA rule violations."""
        def _read_fsca():
            try:
                if hasattr(contradiction_oracle, "active_contradictions"):
                    return contradiction_oracle.active_contradictions()
                elif hasattr(contradiction_oracle, "_cached_contradictions"):
                    return contradiction_oracle._cached_contradictions
                return []
            except Exception:
                return []
        self._readers["fsca"] = _read_fsca

    def watch_pv_ci(self, invariant_sentinel) -> None:
        """Watch InvariantSentinel for PV-CI invariant check results."""
        def _read_pv_ci():
            try:
                if hasattr(invariant_sentinel, "summary"):
                    return invariant_sentinel.summary()
                elif hasattr(invariant_sentinel, "_last_results"):
                    return invariant_sentinel._last_results
                return None
            except Exception:
                return None
        self._readers["pv_ci"] = _read_pv_ci

    def watch_session_id(self, getter: Callable[[], str]) -> None:
        """Watch a callable that returns the current session_id."""
        self._session_id_getter = getter

    # ── Lifecycle ─────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def last_envelope_hash(self) -> str:
        return self._last_envelope_hash

    async def start(self, session_id: str) -> None:
        """Start the attestation loop for a session.

        Args:
            session_id: Current session ID from SessionHistory.
        """
        if self._running:
            log.warning("AttestationTicker already running for session %s", self._session_id)
            return

        self._session_id = session_id
        self._tick_count = 0
        self._last_envelope_hash = ""
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        log.info("AttestationTicker started for session %s", session_id)

    async def stop(self) -> Optional[AttestationEnvelope]:
        """Stop the attestation loop. Returns the final envelope, if any."""
        if not self._running:
            return None

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Build a final summary envelope
        final = self._build_envelope()
        if final and not final.envelope_hash:
            log.warning("Final attestation envelope empty")
        else:
            self._store.append(final)

        log.info(
            "AttestationTicker stopped for session %s — %d ticks",
            self._session_id, self._tick_count,
        )
        self._session_id = ""
        return final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    # ── Tick loop ────────────────────────────────────────

    async def _tick_loop(self):
        """Main attestation loop — runs on tick_interval."""
        try:
            while self._running:
                tick_start = _time.time()
                envelope = self._build_envelope()
                if envelope.envelope_hash:
                    self._store.append(envelope)
                    self._last_envelope_hash = envelope.envelope_hash
                    self._tick_count += 1

                    if self._on_envelope:
                        try:
                            await self._on_envelope(envelope)
                        except Exception as exc:
                            log.warning("on_envelope callback failed: %s", exc)

                # Sleep for the remainder of the tick interval
                elapsed = _time.time() - tick_start
                sleep_time = max(0, self._tick_interval - elapsed)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("Attestation tick loop crashed: %s", exc)
            self._running = False

    def _build_envelope(self) -> AttestationEnvelope:
        """Snapshot all channels and build an attestation envelope.

        Each channel reader is called independently. If a reader raises
        or returns None, that channel is omitted from the envelope.
        The envelope is still valid — missing channels are simply absent.
        """
        snapshot = self._take_snapshot()
        if not snapshot.session_id:
            snapshot.session_id = self._session_id

        # Hash each available channel
        # Map: snapshot field name → channel hash key
        channel_map = {
            "hardware": "hardware",
            "controller": "controller",
            "biometrics": "biometrics",
            "retina": "retina",
            "vlm": "vlm",
            "contradictions": "fsca",
            "invariants": "pv_ci",
        }
        channel_hashes = {}
        for field_name, hash_key in channel_map.items():
            value = getattr(snapshot, field_name, None)
            if value is not None:
                channel_hashes[hash_key] = _hash(value)

        # Cross-modal hash: sorted keys, concatenated values
        if channel_hashes:
            sorted_parts = [channel_hashes[k] for k in sorted(channel_hashes)]
            cross_modal_hash = _hash("".join(sorted_parts))
        else:
            cross_modal_hash = ""

        # PV-CI fingerprint
        pv_ci_fingerprint = ""
        if snapshot.invariants:
            pv_ci_fingerprint = snapshot.invariants.get(
                "fingerprint",
                _hash(snapshot.invariants),
            )

        # Final envelope hash — chains to previous tick
        raw = snapshot.__dict__.copy()
        envelope_hash_parts = [
            str(snapshot.tick),
            str(snapshot.timestamp),
            snapshot.session_id,
            cross_modal_hash,
            pv_ci_fingerprint,
            self._last_envelope_hash,
        ]
        envelope_hash = _hash("|".join(envelope_hash_parts))

        return AttestationEnvelope(
            tick=snapshot.tick,
            timestamp=snapshot.timestamp,
            session_id=snapshot.session_id,
            channel_hashes=channel_hashes,
            cross_modal_hash=cross_modal_hash,
            pv_ci_fingerprint=pv_ci_fingerprint,
            envelope_hash=envelope_hash,
            previous_envelope_hash=self._last_envelope_hash,
            raw=raw,
        )

    def _take_snapshot(self) -> ChannelSnapshot:
        """Read all registered channels and produce a snapshot.

        All reads are in-memory property accesses or cached data.
        No I/O on the hot path.
        """
        snapshot = ChannelSnapshot(
            tick=self._tick_count,
            timestamp=_time.time(),
            session_id=self._session_id,
            hardware=self._read("hardware"),
            controller=self._read("controller"),
            biometrics=self._read("biometrics"),
            retina=self._read("retina"),
            vlm=self._read("vlm"),
            contradictions=self._read("fsca"),
            invariants=self._read("pv_ci"),
        )
        return snapshot

    def _read(self, channel: str) -> Any:
        """Read a channel if registered. Returns None if not available."""
        reader = self._readers.get(channel)
        if reader is None:
            return None
        try:
            return reader()
        except Exception as exc:
            log.debug("Channel '%s' read failed: %s", channel, exc)
            return None