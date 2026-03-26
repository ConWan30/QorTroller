"""Phase 109A — IoSwarmConsensusAggregator: multi-node quorum logic.

W1 mitigation: BLOCK requires BLOCK_QUORUM=0.67 (not 0.60 general threshold).
Tie or insufficient agreement -> HOLD (never auto-BLOCK on ambiguity).
HOLD escalation: 3 consecutive HOLDs same device_id -> hold_escalation_flag=True (advisory).
"""
from __future__ import annotations

import logging
from collections import Counter

log = logging.getLogger(__name__)

GENERAL_QUORUM = 0.60
BLOCK_QUORUM = 0.67   # W1: higher bar for enforcement verdicts
HOLD_ESCALATION_THRESHOLD = 3

# Verdict -> numeric score used as epistemic signal in session_adjudicator
_VERDICT_SCORE: dict[str, float] = {
    "BLOCK": 1.0,
    "FLAG": 0.5,
    "HOLD": 0.5,
    "CLEAR": 0.0,
    "CERTIFY": 0.0,
}


class IoSwarmConsensusAggregator:
    """Aggregate verdicts from multiple ioSwarm nodes into a single quorum result.

    Usage::

        agg = IoSwarmConsensusAggregator()
        result = agg.aggregate(node_verdicts)
        # result["quorum_verdict"] in {"BLOCK","HOLD","FLAG","CLEAR","CERTIFY"}
    """

    def __init__(self, store=None) -> None:
        # store is optional; used only for hold-escalation history lookup
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def aggregate(self, node_verdicts: list[dict]) -> dict:
        """Aggregate node verdicts into a quorum decision.

        Parameters
        ----------
        node_verdicts:
            List of dicts, each with keys:
              - ``node_id``    (str)
              - ``verdict``    (str)
              - ``confidence`` (float)

        Returns
        -------
        dict with keys:
          quorum_verdict, quorum_reached, agreement_ratio, node_count,
          block_quorum_met, swarm_verdict_score, hold_escalation_flag,
          verdict_distribution
        """
        if not node_verdicts:
            return self._empty_result()

        node_count = len(node_verdicts)
        verdicts = [v.get("verdict", "HOLD") for v in node_verdicts]
        dist = Counter(verdicts)
        majority_verdict, majority_count = dist.most_common(1)[0]

        agreement_ratio = majority_count / node_count

        # Check if the winning verdict is actually a tie (two verdicts share majority)
        is_tie = sum(1 for _, cnt in dist.most_common(2) if cnt == majority_count) >= 2
        if is_tie:
            majority_verdict = "HOLD"
            agreement_ratio = majority_count / node_count

        # Apply quorum rules
        if majority_verdict == "BLOCK":
            block_quorum_met = agreement_ratio >= BLOCK_QUORUM
            quorum_reached = block_quorum_met
            quorum_verdict = "BLOCK" if block_quorum_met else "HOLD"
        else:
            block_quorum_met = False
            quorum_reached = agreement_ratio >= GENERAL_QUORUM
            quorum_verdict = majority_verdict if quorum_reached else "HOLD"

        swarm_verdict_score = _VERDICT_SCORE.get(quorum_verdict, 0.5)
        hold_escalation_flag = False

        # HOLD escalation check via store (advisory, never raises)
        if quorum_verdict == "HOLD" and self._store is not None:
            hold_escalation_flag = self._check_hold_escalation(node_verdicts)

        return {
            "quorum_verdict": quorum_verdict,
            "quorum_reached": quorum_reached,
            "agreement_ratio": round(agreement_ratio, 4),
            "node_count": node_count,
            "block_quorum_met": block_quorum_met,
            "swarm_verdict_score": swarm_verdict_score,
            "hold_escalation_flag": hold_escalation_flag,
            "verdict_distribution": dict(dist),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_hold_escalation(self, node_verdicts: list[dict]) -> bool:
        """Return True if store shows >=3 consecutive HOLD results for this device."""
        try:
            device_id = node_verdicts[0].get("node_id", "") if node_verdicts else ""
            # If a proper device_id is not embedded in node_id we skip
            if not device_id:
                return False
            rows = self._store.get_ioswarm_consensus_log(device_id=device_id, limit=HOLD_ESCALATION_THRESHOLD)
            if len(rows) < HOLD_ESCALATION_THRESHOLD:
                return False
            return all(r.get("quorum_verdict") == "HOLD" for r in rows[:HOLD_ESCALATION_THRESHOLD])
        except Exception as exc:  # noqa: BLE001
            log.debug("_check_hold_escalation: %s", exc)
            return False

    @staticmethod
    def _empty_result() -> dict:
        return {
            "quorum_verdict": "HOLD",
            "quorum_reached": False,
            "agreement_ratio": 0.0,
            "node_count": 0,
            "block_quorum_met": False,
            "swarm_verdict_score": 0.5,
            "hold_escalation_flag": False,
            "verdict_distribution": {},
        }
