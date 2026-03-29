"""Phase 112 — PoAd On-Chain Anchor Agent.
Polls poad_registry_log for unanchored entries; calls chain.record_adjudication();
updates on_chain_tx. Non-blocking poll loop. poad_on_chain_enabled=False -> self-disables.
"""
import asyncio
import logging

log = logging.getLogger(__name__)
POLL_INTERVAL_S = 60


class PoAdAnchorAgent:
    def __init__(self, cfg, store, chain) -> None:
        self._cfg, self._store, self._chain = cfg, store, chain

    async def run_poll_loop(self) -> None:
        while True:
            await asyncio.sleep(POLL_INTERVAL_S)
            if not getattr(self._cfg, "poad_on_chain_enabled", False):
                continue
            await self._anchor_pending()

    async def _anchor_pending(self) -> None:
        entries = self._store.get_unanchored_poad_entries(limit=5)
        for entry in entries:
            try:
                tx_hash = await self._chain.record_adjudication(
                    device_id=entry["device_id"],
                    poad_hash_hex=entry["poad_hash"],
                    dual_veto=entry["dual_veto"],
                )
                self._store.update_poad_on_chain_tx(entry["poad_hash"], tx_hash)
                log.info("PoAdAnchorAgent: anchored poad=%s tx=%s",
                         entry["poad_hash"][:16], tx_hash[:16])
            except Exception as exc:
                log.debug("PoAdAnchorAgent: anchor failed poad=%s: %s",
                          entry["poad_hash"][:16], exc)
