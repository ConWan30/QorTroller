"""Phase 109B — IoSwarmNodeEmulator: deterministic N-node ioSwarm simulator.

Follows MockGSRGrip precedent (Phase 63/81): code-before-operators development.
IoSwarmNodeEmulator(n_nodes=5, seed=109) is fully deterministic.
"""
from __future__ import annotations

import hashlib
import random


class IoSwarmNodeEmulator:
    """Emulates N independent ioSwarm nodes for testnet/test development.

    Per-node verdict logic for evaluate_renewal():
    - consecutive_clean >= 5 AND recent_block_count == 0: CERTIFY_RENEW, conf ~0.85–0.95
    - consecutive_clean >= 3 AND recent_block_count <= 1: CERTIFY_RENEW, conf ~0.65–0.75
    - consecutive_clean >= 1 AND recent_block_count <= 2: node-specific (seed-based split)
    - else: SKIP_RENEW

    Produces per-node confidence variance via deterministic offset from seed.
    Never raises.
    """

    def __init__(self, n_nodes: int = 5, seed: int = 109) -> None:
        self._n_nodes = n_nodes
        self._seed = seed

    def evaluate_renewal(
        self,
        device_id: str,
        token_id: int,
        consecutive_clean: int,
        recent_block_count: int = 0,
    ) -> list[dict]:
        """Return [{node_id, verdict, confidence}, ...] for n_nodes nodes.

        Deterministic: same inputs always produce the same verdicts.
        Never raises.
        """
        results: list[dict] = []
        # Deterministic per-call base seed from inputs
        base = int(
            hashlib.sha256(
                f"{self._seed}:{device_id}:{token_id}:{consecutive_clean}:{recent_block_count}".encode()
            ).hexdigest(),
            16,
        ) % (2**31)

        for i in range(self._n_nodes):
            rng = random.Random(base + i * 997)

            if consecutive_clean >= 5 and recent_block_count == 0:
                verdict = "CERTIFY_RENEW"
                confidence = round(0.85 + rng.random() * 0.10, 4)
            elif consecutive_clean >= 3 and recent_block_count <= 1:
                verdict = "CERTIFY_RENEW"
                confidence = round(0.65 + rng.random() * 0.10, 4)
            elif consecutive_clean >= 1 and recent_block_count <= 2:
                # Node-specific split: ~60% CERTIFY_RENEW based on per-node seed
                if rng.random() > 0.40:
                    verdict = "CERTIFY_RENEW"
                else:
                    verdict = "SKIP_RENEW"
                confidence = round(0.50 + rng.random() * 0.20, 4)
            else:
                verdict = "SKIP_RENEW"
                confidence = round(0.80 + rng.random() * 0.15, 4)

            results.append(
                {
                    "node_id": f"ioswarm_emulator_node_{i}",
                    "verdict": verdict,
                    "confidence": confidence,
                }
            )
        return results
