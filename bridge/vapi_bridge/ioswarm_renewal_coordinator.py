"""Phase 109B — IoSwarmRenewalCoordinator: multi-node quorum for VHP renewal.

Fail-open design: coordinator errors -> renewal proceeds (renewal != enforcement).
Uses IoSwarmNodeEmulator for testnet; real ioSwarm nodes when registered.
"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)

CERTIFY_RENEW_QUORUM = 0.60  # Same as GENERAL_QUORUM (renewal is lower stakes than enforcement)


class IoSwarmRenewalCoordinator:
    """Coordinates multi-node ioSwarm quorum for VHP renewal authorization.

    Fail-open: any exception -> approved=True so VHP renewals are not blocked
    by coordinator infrastructure issues.
    Uses IoSwarmNodeEmulator by default (code-before-operators; Phase 109B).
    """

    def __init__(self, cfg, store, emulator=None, live_client=None) -> None:
        self._cfg = cfg
        self._store = store
        self._live_client = live_client
        if emulator is None:
            from .ioswarm_node_emulator import IoSwarmNodeEmulator
            n = int(getattr(cfg, "ioswarm_node_count", 5))
            self._emulator = IoSwarmNodeEmulator(n_nodes=n, seed=109)
        else:
            self._emulator = emulator

    def evaluate_renewal(
        self,
        device_id: str,
        token_id: int,
        consecutive_clean: int,
    ) -> dict:
        """Submit renewal to nodes, aggregate quorum, store audit result.

        Steps:
        1. Query get_ioswarm_consensus_log(device_id, limit=5) -> recent_block_count
        2. Run emulator.evaluate_renewal(...)
        3. Pass node_verdicts to IoSwarmConsensusAggregator().aggregate()
        4. Map quorum_verdict CERTIFY_RENEW->approved=True; SKIP_RENEW/HOLD->approved=False
        5. Call store.insert_ioswarm_renewal(...) for audit
        6. Return {approved, quorum_verdict, agreement_ratio, node_count, node_verdicts}

        On any exception: log warning, return {approved=True, quorum_verdict="ERROR", ...}
        """
        try:
            # Step 1: Get recent BLOCK count from consensus log (W2 integration)
            recent_logs = self._store.get_ioswarm_consensus_log(device_id=device_id, limit=5)
            recent_block_count = sum(
                1 for r in recent_logs if r.get("quorum_verdict") == "BLOCK"
            )

            # Step 2: Query emulator nodes
            node_verdicts = self._emulator.evaluate_renewal(
                device_id=device_id,
                token_id=token_id,
                consecutive_clean=consecutive_clean,
                recent_block_count=recent_block_count,
            )

            # Step 3: Aggregate via IoSwarmConsensusAggregator (reused from Phase 109A)
            from .ioswarm_consensus_aggregator import IoSwarmConsensusAggregator
            agg_result = IoSwarmConsensusAggregator().aggregate(node_verdicts)

            quorum_verdict  = agg_result["quorum_verdict"]
            agreement_ratio = agg_result["agreement_ratio"]
            node_count      = agg_result["node_count"]

            # Step 4: Map verdict -> approved
            approved = quorum_verdict == "CERTIFY_RENEW"

            # Step 5: Store audit log
            self._store.insert_ioswarm_renewal(
                device_id=device_id,
                token_id=token_id,
                quorum_verdict=quorum_verdict,
                agreement_ratio=agreement_ratio,
                node_count=node_count,
                renewal_approved=int(approved),
                node_verdicts_json=json.dumps(node_verdicts),
            )

            return {
                "approved":       approved,
                "quorum_verdict": quorum_verdict,
                "agreement_ratio": agreement_ratio,
                "node_count":     node_count,
                "node_verdicts":  node_verdicts,
            }

        except Exception as exc:
            log.warning(
                "IoSwarmRenewalCoordinator: error for device=%s (fail-open): %s",
                device_id,
                exc,
            )
            return {
                "approved":       True,
                "quorum_verdict": "ERROR",
                "agreement_ratio": 0.0,
                "node_count":     0,
                "node_verdicts":  [],
                "error":          str(exc),
            }
