"""Phase 99B — GSR Registry Agent.

Polls MockGSRGrip (or real hardware) on a configurable interval, extracts L7 features,
persists to SQLite, and (when cfg.gsr_enabled=True) publishes to VAPIGSRRegistry.sol
via chain.record_gsr_sample_on_chain().

Default: gsr_enabled=false — all on-chain writes are skipped.
Bus event: gsr_sample_recorded published after each SQLite insert (always, regardless
of on-chain status) so other agents can subscribe to physiological signals.

Precedent: same poll-and-bus pattern as ClassJDetector (Phase 81), DivergenceTriageAgent
(Phase 91), ProtocolIntelligenceAgent (Phase 89).
"""
import asyncio
import hashlib
import logging
import time

log = logging.getLogger(__name__)


class GSRRegistryAgent:
    """5-minute poll loop: collect GSR sample → store → publish bus event → (optional) on-chain."""

    def __init__(self, cfg, store, chain=None, bus=None):
        self._cfg = cfg
        self._store = store
        self._chain = chain
        self._bus = bus
        self._grip = None

    def _get_grip(self):
        """Lazy-init MockGSRGrip (or real hardware driver, same interface)."""
        if self._grip is None:
            from vapi_bridge.gsr_feature_extractor import MockGSRGrip
            self._grip = MockGSRGrip(seed=42)
        return self._grip

    async def _collect_and_store(self) -> dict | None:
        """Collect one GSR sample, extract features, persist, publish bus event.

        Never raises. Returns the stored row dict on success, None on error.
        """
        try:
            from vapi_bridge.gsr_feature_extractor import extract_l7_features
            grip = self._get_grip()
            sample = grip.get_sample()

            # Use a synthetic device_id for MockGSRGrip (real hardware provides real device_id)
            device_id = "gsr_grip_mock"

            # L7 features from a minimal single-sample window
            # In production: accumulate a 128-sample window before feature extraction
            window = [sample]
            features = extract_l7_features(window)

            row_id = self._store.insert_gsr_sample(
                device_id=device_id,
                arousal_index=sample.arousal_index,
                correlation=sample.correlation,
                conductance_raw=sample.conductance_raw,
                l7_features_json=str(features),
            )

            # Publish bus event regardless of on-chain status
            if self._bus is not None:
                payload = {
                    "device_id": device_id,
                    "arousal_index": sample.arousal_index,
                    "correlation": sample.correlation,
                    "row_id": row_id,
                    "timestamp": sample.timestamp,
                }
                self._bus.publish_sync("gsr_sample_recorded", payload)

            # On-chain write only when gsr_enabled=True and chain is available
            if getattr(self._cfg, "gsr_enabled", False) and self._chain is not None:
                arousal_millis = int(sample.arousal_index * 1000)
                # Encode correlation: (-1.0 to +1.0) → (0 to 1000) via (r + 1.0) * 500
                corr_millis = int((sample.correlation + 1.0) * 500)
                device_id_bytes = hashlib.sha256(device_id.encode()).digest()[:32]
                device_id_b32 = bytes(device_id_bytes).ljust(32, b"\x00")
                ts_uint = int(sample.timestamp)
                try:
                    tx_hash = await self._chain.record_gsr_sample_on_chain(
                        device_id_b32, arousal_millis, corr_millis, ts_uint
                    )
                    log.info(
                        "GSRRegistryAgent: on-chain tx=%s arousal=%d corr=%d",
                        tx_hash[:16], arousal_millis, corr_millis,
                    )
                except Exception as exc:
                    log.warning("GSRRegistryAgent: on-chain write failed: %s", exc)

            return {"row_id": row_id, "device_id": device_id,
                    "arousal_index": sample.arousal_index,
                    "correlation": sample.correlation}

        except Exception as exc:
            log.warning("GSRRegistryAgent._collect_and_store: %s", exc)
            return None

    async def run_poll_loop(self) -> None:
        """Run indefinitely; collect a GSR sample every gsr_sample_interval_s seconds."""
        interval = getattr(self._cfg, "gsr_sample_interval_s", 30)
        log.info("GSRRegistryAgent: starting poll loop (interval=%ds, gsr_enabled=%s)",
                 interval, getattr(self._cfg, "gsr_enabled", False))
        while True:
            await self._collect_and_store()
            await asyncio.sleep(interval)
