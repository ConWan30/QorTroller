"""Phase 109C — IoSwarmClassJEmulator: deterministic N-node ClassJDetector emulator.

W1 (architectural security boundary): All nodes share same seed/logic — testnet-only
(code-before-operators, MockGSRGrip precedent). Real ioSwarm nodes use independent
hardware stacks (production security property is architectural, not code-level). An
adversary who evades one emulator node evades all nodes simultaneously; this is
documented and acceptable for testnet. Mitigation is physical node independence at
production deployment, not code-level diversity.

Verdict mapping: BLOCK / FLAG / CLEAR  (native IoSwarmConsensusAggregator format).
Entropy-variance thresholds (Phase 81 invariants — FROZEN):
  HIGH:    entropy_variance <= 0.03  → all BLOCK,         conf 0.88–0.98
  HIGH-:   entropy_variance <= 0.05  → BLOCK/FLAG split,  conf 0.78–0.90
  MID-H:   entropy_variance <= 0.10  → BLOCK/FLAG split,  conf 0.60–0.78
  MEDIUM:  entropy_variance <= 0.15  → FLAG/BLOCK split,  conf 0.50–0.70
  LOW:     entropy_variance >  0.15  → all CLEAR,         conf 0.87–0.97

Test anchors (deterministic):
  evaluate_classj("dev", "", 0.03) → 5/5 BLOCK
  evaluate_classj("dev", "", 0.20) → 5/5 CLEAR
"""
from __future__ import annotations

import hashlib
import random


class IoSwarmClassJEmulator:
    """Emulates N independent ioSwarm nodes each applying ClassJDetector logic.

    Parameters
    ----------
    n_nodes:
        Number of simulated ioSwarm nodes (default 5).
    seed:
        Base determinism seed (default 109, Phase 109C seed family).
    """

    def __init__(self, n_nodes: int = 5, seed: int = 109) -> None:
        self._n_nodes = n_nodes
        self._seed = seed

    def evaluate_classj(
        self,
        device_id: str,
        session_id: str,
        entropy_variance: float,
    ) -> list[dict]:
        """Return per-node verdicts for N simulated ioSwarm ClassJDetector nodes.

        Parameters
        ----------
        device_id:
            Controller/device identifier (used for determinism).
        session_id:
            Session identifier (used for determinism; empty string is valid).
        entropy_variance:
            Phase 81 ClassJDetector signal (higher = more human-like entropy).

        Returns
        -------
        list[dict]
            Each element: {"node_id": str, "verdict": str, "confidence": float}.
            Verdict ∈ {"BLOCK", "FLAG", "CLEAR"}.
        """
        # Deterministic base from all inputs — same inputs always yield same verdicts
        digest = hashlib.sha256(
            f"{self._seed}:{device_id}:{session_id}:{entropy_variance:.6f}".encode()
        ).hexdigest()
        base = int(digest, 16) % (2**31)

        results: list[dict] = []
        for i in range(self._n_nodes):
            rng = random.Random(base + i * 997)  # 997 = prime offset (Phase 109B precedent)

            if entropy_variance <= 0.03:
                # Extreme low-variance — all BLOCK (high confidence bot signal)
                verdict = "BLOCK"
                confidence = round(0.88 + rng.random() * 0.10, 4)

            elif entropy_variance <= 0.05:
                # Strong low-variance — predominantly BLOCK
                verdict = "BLOCK" if rng.random() > 0.05 else "FLAG"
                confidence = round(0.78 + rng.random() * 0.12, 4)

            elif entropy_variance <= 0.10:
                # Moderate low-variance — majority BLOCK, some FLAG
                verdict = "BLOCK" if rng.random() > 0.30 else "FLAG"
                confidence = round(0.60 + rng.random() * 0.18, 4)

            elif entropy_variance <= 0.15:
                # Ambiguous range — majority FLAG, minority BLOCK
                verdict = "FLAG" if rng.random() > 0.45 else "BLOCK"
                confidence = round(0.50 + rng.random() * 0.20, 4)

            else:
                # High variance (human-like) — all CLEAR (no bot signal)
                verdict = "CLEAR"
                confidence = round(0.87 + rng.random() * 0.10, 4)

            results.append({
                "node_id": f"ioswarm_emulator_node_{i}",
                "verdict": verdict,
                "confidence": confidence,
            })

        return results
