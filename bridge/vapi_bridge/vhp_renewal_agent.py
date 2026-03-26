"""
VHPRenewalAgent — 14th autonomous agent — VHP soulbound token TTL lifecycle manager.
Phase 102: Developer Integration Layer.

Polls every 6 hours. Finds VHPs expiring within cfg.vhp_renewal_warning_days (default 7).
In dry_run mode: logs renewal advisory without chain call.
In live mode: calls chain.renew_vhp(token_id), logs to vhp_renewal_log.
W2 liveness beacon: publishes 'vhp_lifecycle_warning' if no VHPs ever issued.
Never raises from run_poll_loop.
"""
from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)


class VHPRenewalAgent:
    """14th autonomous agent — VHP soulbound token TTL lifecycle manager (Phase 102).

    Polls every 6 hours. Finds VHPs expiring within cfg.vhp_renewal_warning_days.
    In dry_run mode: logs renewal advisory without chain call.
    In live mode: calls chain.renew_vhp(token_id), logs to vhp_renewal_log.
    W2 liveness beacon: publishes 'vhp_lifecycle_warning' if no VHPs ever issued.
    Never raises from run_poll_loop.
    """

    POLL_INTERVAL_S = 21_600  # 6 hours

    def __init__(self, cfg, store, chain=None, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._chain = chain
        self._bus   = bus

    async def run_poll_loop(self) -> None:
        """Main agent loop — runs forever, never raises."""
        log.info("VHPRenewalAgent: started (poll=%ds)", self.POLL_INTERVAL_S)
        while True:
            try:
                await self._check_and_renew()
            except Exception as exc:  # pragma: no cover
                log.warning("VHPRenewalAgent poll error: %s", exc)
            await asyncio.sleep(self.POLL_INTERVAL_S)

    async def _check_and_renew(self) -> None:
        """Core renewal logic. Called once per poll cycle."""
        warning_days = getattr(self._cfg, "vhp_renewal_warning_days", 7)
        cutoff       = time.time() + warning_days * 86_400
        expiring     = self._store.get_expiring_vhps(cutoff)
        total        = self._store.get_total_vhp_count()

        # W2 liveness beacon — publish warning when protocol has never issued a VHP
        if total == 0:
            if self._bus is not None:
                self._bus.publish_sync(
                    "vhp_lifecycle_warning",
                    {"reason": "no_vhps_ever_issued"},
                    source="VHPRenewalAgent",
                )
            log.info("VHPRenewalAgent: no VHPs ever issued — lifecycle warning published")
            return

        if not expiring:
            log.debug("VHPRenewalAgent: no VHPs expiring within %d days", warning_days)
            return

        dry_run = getattr(self._cfg, "agent_dry_run_mode", True)
        log.info(
            "VHPRenewalAgent: %d VHPs expiring within %d days (dry_run=%s)",
            len(expiring), warning_days, dry_run,
        )

        for vhp in expiring:
            # Phase 109B: ioSwarm quorum guard — additive, backward-compatible
            _ioswarm_renewal_on = getattr(self._cfg, "ioswarm_renewal_enabled", False)
            if _ioswarm_renewal_on:
                try:
                    from .ioswarm_renewal_coordinator import IoSwarmRenewalCoordinator
                    _coord = IoSwarmRenewalCoordinator(cfg=self._cfg, store=self._store)
                    _result = _coord.evaluate_renewal(
                        device_id=vhp["device_id"],
                        token_id=vhp["token_id"],
                        consecutive_clean=vhp.get("consecutive_clean", 0),
                    )
                    if not _result["approved"]:
                        log.info(
                            "VHPRenewalAgent: ioSwarm quorum %s (ratio=%.2f) — skip renewal %s",
                            _result["quorum_verdict"],
                            _result["agreement_ratio"],
                            vhp["device_id"],
                        )
                        continue  # skip this VHP this poll cycle
                except Exception as _exc:
                    log.debug(
                        "VHPRenewalAgent: ioSwarm coordinator error (fail-open): %s", _exc
                    )
            tx = ""
            try:
                if not dry_run and self._chain is not None:
                    tx = await self._chain.renew_vhp(vhp["token_id"])
                self._store.insert_vhp_renewal(
                    device_id=vhp["device_id"],
                    token_id=vhp["token_id"],
                    old_expires_at=vhp["expires_at"],
                    new_expires_at=vhp["expires_at"] + 90 * 86_400,
                    tx_hash=tx,
                    dry_run=dry_run,
                )
                if self._bus is not None:
                    self._bus.publish_sync(
                        "vhp_renewed",
                        {
                            "device_id": vhp["device_id"],
                            "token_id":  vhp["token_id"],
                            "dry_run":   dry_run,
                        },
                        source="VHPRenewalAgent",
                    )
                log.info(
                    "VHPRenewalAgent: renewed token_id=%s dry_run=%s tx=%s",
                    vhp["token_id"], dry_run, tx,
                )
            except Exception as exc:
                log.warning(
                    "VHPRenewalAgent: failed to renew token_id=%s: %s",
                    vhp["token_id"], exc,
                )
