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

from . import ipact_renewal
from .ipact_renewal import IPACT_RENEWAL_EPOCH_DAYS

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

    def _obtain_reattest_proof(self, vhp: dict) -> bytes | None:
        """Phase B ③ — pluggable re-attestation-proof hook (default validator: ① composite-sig
        over a bridge-issued fresh challenge).

        Returns a 32-byte ``reattest_proof`` (see ipact_renewal.compute_reattest_proof) when a
        fresh, valid device re-attestation is available for this renewal; otherwise None.

        v1 default: returns None — the live challenge-issuance ↔ device-signing ↔ verify
        handshake is NOT wired in this commit (enforcement ships DEFAULT-OFF). When enforcement
        is later flipped ON, this hook is the single integration point to wire (or inject in
        tests); until wired it returns None, so an ON gate is FAIL-CLOSED (renewals skip rather
        than auto-renew a dormant device). Subclass / monkeypatch to supply a real proof.
        """
        return None

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
                    from .ioswarm_live_node_client import IoSwarmLiveNodeClient as _ILNC131r
                    _live_client_r = _ILNC131r(cfg=self._cfg, store=self._store)
                    _coord = IoSwarmRenewalCoordinator(cfg=self._cfg, store=self._store, live_client=_live_client_r)
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
            # Phase B item ③ — iPACT-DePIN renewal-cadence commitment + enforcement gate.
            # DEFAULT-OFF: when enforcement is off, the commitment chain still accumulates
            # (NO_REATTEST_PROOF sentinel) but renewals are NOT gated → behavior below is
            # byte-identical to pre-③. When ON, a renewal without a valid fresh re-attestation
            # is SKIPPED (closes the dormant-blind gap).
            _enforce = getattr(self._cfg, "ipact_renewal_enforcement_enabled", False)
            if _enforce:
                _proof = self._obtain_reattest_proof(vhp)
                if _proof is None:
                    log.info(
                        "VHPRenewalAgent: ③ enforcement ON but no valid re-attestation for "
                        "%s — skipping renewal (dormant-blind gate)", vhp["device_id"],
                    )
                    continue  # fail-closed: no fresh proof → no renewal
                _reattest_proof = _proof
            else:
                _reattest_proof = ipact_renewal.NO_REATTEST_PROOF
            try:
                _head = self._store.get_ipact_renewal_head(vhp["device_id"])
                if _head is None:
                    _prev = ipact_renewal.genesis_commitment(
                        vhp["device_id"], vhp["token_id"])
                    _epoch_index = 0
                else:
                    _prev = _head["commitment"]
                    _epoch_index = _head["epoch_index"] + 1
                _ts_ns = time.time_ns()
                _prev_ts = self._store.get_prev_ipact_ts_ns(vhp["device_id"])
                if _ts_ns <= _prev_ts:  # INV-GIC-002 monotonicity guard
                    _ts_ns = _prev_ts + 1
                _commitment = ipact_renewal.compute_commitment(
                    vhp["device_id"], vhp["token_id"], _prev,
                    _epoch_index, _reattest_proof, _ts_ns,
                )
                self._store.insert_ipact_renewal_commitment(
                    device_id=vhp["device_id"], token_id=vhp["token_id"],
                    epoch_index=_epoch_index, prev_commitment=_prev,
                    reattest_proof=_reattest_proof, commitment=_commitment,
                    ts_ns=_ts_ns, enforced=_enforce,
                )
            except Exception as _exc:  # fail-open on the commitment side when OFF
                log.debug("VHPRenewalAgent: ③ commitment error: %s", _exc)

            tx = ""
            try:
                if not dry_run and self._chain is not None:
                    tx = await self._chain.renew_vhp(vhp["token_id"])
                self._store.insert_vhp_renewal(
                    device_id=vhp["device_id"],
                    token_id=vhp["token_id"],
                    old_expires_at=vhp["expires_at"],
                    new_expires_at=vhp["expires_at"] + IPACT_RENEWAL_EPOCH_DAYS * 86_400,
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
