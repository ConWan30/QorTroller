"""Phase 110 — IoSwarmVHPMintEmulator: deterministic N-node VHP mint authorization emulator.

W1: All nodes share same seed/logic — testnet-only (MockGSRGrip/IoSwarmNodeEmulator precedent).
Real ioSwarm nodes use independent hardware stacks (production security property).
Verdict mapping: AUTHORIZE / DENY (binary — no FLAG ambiguity at highest stakes).
Inputs: consecutive_clean (session streak length) + recent_block_count (recent BLOCK rulings).
"""
from __future__ import annotations

import hashlib
import random


class IoSwarmVHPMintEmulator:
    """Emulates N independent ioSwarm nodes each applying VHP mint authorization logic.

    Thresholds (Phase 110 invariants, FROZEN):
      AUTHORIZE:  consecutive_clean >= 5 AND recent_block_count == 0 → all AUTHORIZE
      AUTHORIZE:  consecutive_clean >= 3 AND recent_block_count == 0 → AUTHORIZE/DENY mixed
      DENY:       recent_block_count >= 2 → all DENY
      DENY:       consecutive_clean < 3 AND recent_block_count < 2 → DENY/AUTHORIZE mixed

    W1: All nodes share seed=110 — testnet-only; production nodes use independent hardware.
    """

    def __init__(self, n_nodes: int = 5, seed: int = 110) -> None:
        self._n_nodes = n_nodes
        self._seed = seed

    def evaluate_vhp_mint(
        self,
        device_id: str,
        consecutive_clean: int,
        recent_block_count: int,
    ) -> list[dict]:
        """Return [{node_id, verdict, confidence}, ...] for n_nodes nodes.

        Determinism: SHA-256(f"{seed}:{device_id}:{consecutive_clean}:{recent_block_count}")
        Per-node RNG: random.Random(base + i * 997)   # 997 = prime offset (Phase 109B/C precedent)

        Test anchors (seed=110):
          evaluate_vhp_mint("dev", consecutive_clean=5, recent_block_count=0) -> 5/5 AUTHORIZE
          evaluate_vhp_mint("dev", consecutive_clean=0, recent_block_count=3) -> 5/5 DENY
        """
        fingerprint = f"{self._seed}:{device_id}:{consecutive_clean}:{recent_block_count}"
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()
        base_int = int(digest[:16], 16)

        results = []
        for i in range(self._n_nodes):
            rng = random.Random(base_int + i * 997)
            node_id = f"vhp_mint_node_{i}"

            if recent_block_count >= 2:
                # Hard DENY — recent blocks signal enforcement concern
                verdict = "DENY"
                confidence = round(0.85 + rng.random() * 0.10, 4)

            elif consecutive_clean >= 5 and recent_block_count == 0:
                # Strong AUTHORIZE — long clean streak with no blocks
                verdict = "AUTHORIZE"
                confidence = round(0.87 + rng.random() * 0.10, 4)

            elif consecutive_clean >= 3 and recent_block_count == 0:
                # Moderate AUTHORIZE — decent streak with no blocks
                verdict = "AUTHORIZE" if rng.random() > 0.20 else "DENY"
                confidence = round(0.70 + rng.random() * 0.18, 4)

            else:
                # Low streak with few blocks — lean DENY
                verdict = "DENY" if rng.random() > 0.30 else "AUTHORIZE"
                confidence = round(0.60 + rng.random() * 0.18, 4)

            results.append({
                "node_id":    node_id,
                "verdict":    verdict,
                "confidence": confidence,
            })

        return results
