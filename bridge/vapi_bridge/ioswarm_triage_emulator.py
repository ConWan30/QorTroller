"""Phase 109C — IoSwarmTriageEmulator: deterministic N-node DivergenceTriageAgent emulator.

W1 (architectural security boundary): All nodes share same seed/logic — testnet-only
(code-before-operators, MockGSRGrip precedent). Real ioSwarm nodes use independent
hardware stacks. Documented in module docstring and §9.28.

Triage pattern precedence: ml_bot_cluster > cheat_cluster > enrollment_anomaly > none.
Verdict mapping: BLOCK / FLAG / CLEAR  (native IoSwarmConsensusAggregator format).

Verdict logic per escalation state:
  not escalated         → all CLEAR,         conf 0.88–0.98
  escalated + ml_bot    → all BLOCK,         conf 0.82–0.94
  escalated + cheat     → BLOCK/FLAG split,  conf 0.70–0.88
  escalated + anomaly   → FLAG/CLEAR split,  conf 0.52–0.74

Test anchors (deterministic):
  evaluate_triage("dev", "", True, "ml_bot_cluster:2x_HIGH")  → 5/5 BLOCK
  evaluate_triage("dev", "", False, None)                      → 5/5 CLEAR
"""
from __future__ import annotations

import hashlib
import random


class IoSwarmTriageEmulator:
    """Emulates N independent ioSwarm nodes each applying DivergenceTriageAgent logic.

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

    def evaluate_triage(
        self,
        device_id: str,
        session_id: str,
        escalated: bool,
        triage_patterns: "str | None" = None,
    ) -> list[dict]:
        """Return per-node verdicts for N simulated ioSwarm DivergenceTriageAgent nodes.

        Parameters
        ----------
        device_id:
            Controller/device identifier (used for determinism).
        session_id:
            Session identifier (used for determinism; empty string is valid).
        escalated:
            Whether DivergenceTriageAgent escalated this device (True = escalated).
        triage_patterns:
            Colon-separated triage pattern string from DivergenceTriageAgent report
            (e.g. "ml_bot_cluster:2x_HIGH", "cheat_cluster:1x_MEDIUM"). None or ""
            means no specific pattern detected (enrollment_anomaly path).

        Returns
        -------
        list[dict]
            Each element: {"node_id": str, "verdict": str, "confidence": float}.
            Verdict ∈ {"BLOCK", "FLAG", "CLEAR"}.
        """
        # Deterministic base from all inputs — same inputs always yield same verdicts
        patterns_key = triage_patterns or ""
        digest = hashlib.sha256(
            f"{self._seed}:{device_id}:{session_id}:{int(escalated)}:{patterns_key}".encode()
        ).hexdigest()
        base = int(digest, 16) % (2**31)

        results: list[dict] = []
        for i in range(self._n_nodes):
            rng = random.Random(base + i * 997)  # 997 = prime offset (Phase 109B precedent)
            patterns = triage_patterns or ""

            if not escalated:
                # Device not escalated — no triage signal
                verdict = "CLEAR"
                confidence = round(0.88 + rng.random() * 0.10, 4)

            elif "ml_bot_cluster" in patterns:
                # ML-bot cluster detected (Phase 91: ≥2 ClassJ HIGH sessions)
                # Highest confidence BLOCK — machine pattern confirmed across sessions
                verdict = "BLOCK"
                confidence = round(0.82 + rng.random() * 0.12, 4)

            elif "cheat_cluster" in patterns:
                # Cheat cluster detected (Phase 91: ≥1 hard cheat code)
                # Predominantly BLOCK, small FLAG minority (forensics edge cases)
                verdict = "BLOCK" if rng.random() > 0.20 else "FLAG"
                confidence = round(0.70 + rng.random() * 0.18, 4)

            else:
                # Enrollment anomaly only (Phase 91: ≥3 non-eligible enrollment events)
                # Lower confidence — enrollment gap can have legitimate causes
                verdict = "FLAG" if rng.random() > 0.40 else "CLEAR"
                confidence = round(0.52 + rng.random() * 0.22, 4)

            results.append({
                "node_id": f"ioswarm_emulator_node_{i}",
                "verdict": verdict,
                "confidence": confidence,
            })

        return results
