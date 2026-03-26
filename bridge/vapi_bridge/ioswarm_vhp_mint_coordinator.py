"""Phase 110 — IoSwarmVHPMintCoordinator: fail-CLOSED quorum gate for VHP mint.

W1 (fail-CLOSED): Exceptions -> authorized=False (OPPOSITE of VHPRenewal fail-OPEN).
  VHP mint is irreversible (soulbound on-chain) — false positives (unauthorized mints) are
  worse than false negatives (delayed mints). Never fail-open on an irreversible action.
  This is OPPOSITE of:
    Phase 109B renewal fail-OPEN: errors -> approved=True (avoid blocking honest renewals)
    Phase 109C adjudication fail-OPEN: errors -> CLEAR (avoid false bans)

W2 (swarm fingerprint): SHA-256(node_verdicts_json) stored as swarm_fingerprint in audit log.
  Creates two-era VHP provenance: pre-110 (no fingerprint) vs. post-110 (quorum-authorized).
  Downstream tournament contracts can use fingerprint to distinguish authorization pathway.

MINT_QUORUM = 0.80 — stricter than BLOCK_QUORUM=0.67 (enforcement standard).
Convergent design: same 0.80 threshold as DUAL_VETO_SCORE (Phase 109C).

Emulator: IoSwarmVHPMintEmulator(n=5, seed=110).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

log = logging.getLogger(__name__)

# W1: Stricter than BLOCK_QUORUM=0.67 — VHP mint is irreversible
# Convergent design: matches DUAL_VETO_SCORE from Phase 109C (both high-confidence gates use 0.80)
MINT_QUORUM = 0.80


class IoSwarmVHPMintCoordinator:
    """Runs N-node VHP mint authorization quorum, stores swarm_fingerprint, audit log.

    Parameters
    ----------
    cfg:
        Bridge config object. Uses:
          cfg.ioswarm_vhp_mint_enabled (bool)
          cfg.ioswarm_vhp_mint_quorum (float, default 0.80)
    store:
        VAPIStore instance for ioswarm_vhp_mint_log.
    mint_emulator:
        Optional injected IoSwarmVHPMintEmulator (default: IoSwarmVHPMintEmulator(n=5, seed=110)).
    """

    def __init__(self, cfg, store, mint_emulator=None) -> None:
        self._cfg = cfg
        self._store = store

        if mint_emulator is None:
            from .ioswarm_vhp_mint_emulator import IoSwarmVHPMintEmulator
            mint_emulator = IoSwarmVHPMintEmulator(n_nodes=5, seed=110)
        self._emulator = mint_emulator

    def authorize(
        self,
        device_id: str,
        consecutive_clean: int,
        recent_block_count: int,
    ) -> dict:
        """Run N-node VHP mint quorum, compute swarm_fingerprint, store audit log.

        Steps:
          1. emulator.evaluate_vhp_mint(device_id, consecutive_clean, recent_block_count)
          2. Compute authorize_ratio = count(AUTHORIZE) / n_nodes
          3. authorized = (authorize_ratio >= MINT_QUORUM)
          4. swarm_fingerprint = SHA-256(json.dumps(node_verdicts, sort_keys=True))
          5. Store to ioswarm_vhp_mint_log
          6. Return result dict

        Fail-CLOSED (W1): any exception -> {"authorized": False, "quorum_verdict": "DENY",
                                             "agreement_ratio": 0.0, "error": str(exc)}
        This is OPPOSITE of VHPRenewal fail-OPEN (errors there -> approved=True).

        Returns
        -------
        dict with keys:
          authorized, quorum_verdict, agreement_ratio, node_count,
          node_verdicts, swarm_fingerprint
          [error: str (only on fail-closed path)]
        """
        try:
            mint_q = float(getattr(self._cfg, "ioswarm_vhp_mint_quorum", MINT_QUORUM))

            # Step 1: Query emulator nodes
            node_verdicts = self._emulator.evaluate_vhp_mint(
                device_id=device_id,
                consecutive_clean=consecutive_clean,
                recent_block_count=recent_block_count,
            )

            # Step 2: Compute authorize ratio directly (binary decision, no aggregator ambiguity)
            node_count = len(node_verdicts)
            if node_count == 0:
                # No nodes → fail-closed
                raise RuntimeError("No nodes returned from emulator")

            authorize_count = sum(1 for v in node_verdicts if v.get("verdict") == "AUTHORIZE")
            authorize_ratio = round(authorize_count / node_count, 4)

            # Step 3: authorized = (authorize_ratio >= MINT_QUORUM)
            authorized = authorize_ratio >= mint_q

            # Derive quorum_verdict for logging
            deny_count = node_count - authorize_count
            if authorize_count > deny_count:
                quorum_verdict = "AUTHORIZE"
            elif deny_count > authorize_count:
                quorum_verdict = "DENY"
            else:
                # Tie -> DENY (fail-closed on ambiguity at highest-stakes gate)
                quorum_verdict = "DENY"

            # Step 4: swarm_fingerprint = SHA-256(node_verdicts_json, sort_keys=True)
            verdicts_json = json.dumps(node_verdicts, sort_keys=True)
            swarm_fingerprint = hashlib.sha256(verdicts_json.encode()).hexdigest()

            # Step 5: Store audit log
            try:
                self._store.insert_ioswarm_vhp_mint(
                    device_id=device_id,
                    authorized=authorized,
                    quorum_verdict=quorum_verdict,
                    agreement_ratio=authorize_ratio,
                    node_count=node_count,
                    consecutive_clean=consecutive_clean,
                    recent_block_count=recent_block_count,
                    node_verdicts_json=verdicts_json,
                    swarm_fingerprint=swarm_fingerprint,
                )
            except Exception as store_exc:
                log.debug("IoSwarmVHPMintCoordinator: audit store error (non-fatal): %s", store_exc)

            if authorized:
                log.info(
                    "IoSwarmVHPMintCoordinator: VHP mint AUTHORIZED — device=%s "
                    "authorize_ratio=%.2f (>= %.2f) fingerprint=%s...",
                    device_id, authorize_ratio, mint_q, swarm_fingerprint[:16],
                )
            else:
                log.info(
                    "IoSwarmVHPMintCoordinator: VHP mint DENIED — device=%s "
                    "authorize_ratio=%.2f (< %.2f) quorum=%s",
                    device_id, authorize_ratio, mint_q, quorum_verdict,
                )

            return {
                "authorized":       authorized,
                "quorum_verdict":   quorum_verdict,
                "agreement_ratio":  authorize_ratio,
                "node_count":       node_count,
                "node_verdicts":    node_verdicts,
                "swarm_fingerprint": swarm_fingerprint,
            }

        except Exception as exc:
            # Fail-CLOSED (W1): any exception -> authorized=False
            # OPPOSITE of VHPRenewal fail-OPEN (errors there -> approved=True)
            log.debug("IoSwarmVHPMintCoordinator: fail-CLOSED on error: %s", exc)
            return {
                "authorized":       False,
                "quorum_verdict":   "DENY",
                "agreement_ratio":  0.0,
                "node_count":       0,
                "node_verdicts":    [],
                "swarm_fingerprint": None,
                "error":            str(exc),
            }
