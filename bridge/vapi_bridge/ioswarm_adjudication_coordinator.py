"""Phase 109C — IoSwarmAdjudicationCoordinator: dual-quorum veto for ClassJ+Triage.

W2 (Dual-Quorum Veto — exclusive to VAPI):
  When BOTH IoSwarmClassJEmulator quorum AND IoSwarmTriageEmulator quorum independently
  return BLOCK (each requiring ≥67% node agreement), score_override = max(consensus_score,
  DUAL_VETO_SCORE=0.80) fires.  The joint false-positive probability drops multiplicatively.

Fail-open direction for adjudication: errors → CLEAR verdicts (avoid false positives).
  This is OPPOSITE of VHPRenewal fail-open (which approves renewals on error to avoid
  blocking honest renewals).  Adjudication errors lean toward CLEAR to prevent false bans.

Reuses IoSwarmConsensusAggregator (Phase 109A) for quorum logic.
Emulators: IoSwarmClassJEmulator + IoSwarmTriageEmulator (Phase 109C).
"""
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# W1: Enforcement standard quorum (NOT 0.60 renewal standard)
CLASSJ_BLOCK_QUORUM = 0.67
TRIAGE_BLOCK_QUORUM = 0.67

# W2: Score override when both quorums independently BLOCK
# 0.80 > epistemic threshold 0.60 → always drives BLOCK verdict
DUAL_VETO_SCORE = 0.80


class IoSwarmAdjudicationCoordinator:
    """Runs ClassJ quorum + Triage quorum, computes dual-quorum veto, stores audit log.

    Parameters
    ----------
    cfg:
        Bridge config object.  Uses:
          cfg.ioswarm_adjudication_enabled (bool)
          cfg.ioswarm_classj_block_quorum (float, default 0.67)
          cfg.ioswarm_triage_block_quorum (float, default 0.67)
    store:
        VAPIStore instance for ioswarm_adjudication_log.
    classj_emulator:
        Optional injected IoSwarmClassJEmulator (default: IoSwarmClassJEmulator(n=5, seed=109)).
    triage_emulator:
        Optional injected IoSwarmTriageEmulator (default: IoSwarmTriageEmulator(n=5, seed=109)).
    """

    def __init__(
        self,
        cfg,
        store,
        classj_emulator=None,
        triage_emulator=None,
    ) -> None:
        self._cfg = cfg
        self._store = store

        if classj_emulator is None:
            from .ioswarm_classj_emulator import IoSwarmClassJEmulator
            classj_emulator = IoSwarmClassJEmulator(n_nodes=5, seed=109)
        if triage_emulator is None:
            from .ioswarm_triage_emulator import IoSwarmTriageEmulator
            triage_emulator = IoSwarmTriageEmulator(n_nodes=5, seed=109)

        self._classj_emulator = classj_emulator
        self._triage_emulator = triage_emulator

    def evaluate(
        self,
        device_id: str,
        session_id: str,
        entropy_variance: float,
        escalated: bool,
        triage_patterns: "str | None" = None,
    ) -> dict:
        """Run ClassJ quorum + Triage quorum, compute dual-veto, store audit log.

        Steps:
          1. Run classj_emulator.evaluate_classj(...)
          2. Aggregate via IoSwarmConsensusAggregator
          3. Run triage_emulator.evaluate_triage(...)
          4. Aggregate via IoSwarmConsensusAggregator
          5. dual_veto = (classj_quorum == "BLOCK" AND triage_quorum == "BLOCK")
          6. Store to ioswarm_adjudication_log
          7. Return result dict

        Fail-open (adjudication): any exception → CLEAR verdicts, dual_veto=False, error=str(exc)
        This is OPPOSITE of VHPRenewal fail-open (errors there → approved=True).

        Returns
        -------
        dict with keys:
          classj_quorum_verdict, classj_agreement_ratio, classj_node_verdicts,
          triage_quorum_verdict, triage_agreement_ratio, triage_node_verdicts,
          dual_veto, dual_veto_score, node_count
          [error: str (only on fail-open path)]
        """
        try:
            from .ioswarm_consensus_aggregator import IoSwarmConsensusAggregator

            cj_block_q = getattr(self._cfg, "ioswarm_classj_block_quorum", CLASSJ_BLOCK_QUORUM)
            tr_block_q = getattr(self._cfg, "ioswarm_triage_block_quorum", TRIAGE_BLOCK_QUORUM)

            # Step 1+2: ClassJ quorum
            classj_nodes = self._classj_emulator.evaluate_classj(
                device_id, session_id, entropy_variance
            )
            cj_agg = IoSwarmConsensusAggregator().aggregate(classj_nodes)

            # Step 3+4: Triage quorum
            triage_nodes = self._triage_emulator.evaluate_triage(
                device_id, session_id, escalated, triage_patterns
            )
            tr_agg = IoSwarmConsensusAggregator().aggregate(triage_nodes)

            cj_verdict = cj_agg.get("quorum_verdict", "CLEAR")
            tr_verdict = tr_agg.get("quorum_verdict", "CLEAR")

            # Step 5: Dual-veto fires ONLY on BLOCK+BLOCK
            # FLAG+BLOCK or BLOCK+FLAG is insufficient — prevents single-signal false veto
            dual_veto = (cj_verdict == "BLOCK" and tr_verdict == "BLOCK")

            cj_agreement = cj_agg.get("agreement_ratio", 0.0)
            tr_agreement = tr_agg.get("agreement_ratio", 0.0)
            node_count = len(classj_nodes)

            # Step 6: Store audit log
            try:
                self._store.insert_ioswarm_adjudication(
                    device_id=device_id,
                    session_id=session_id or "",
                    classj_quorum_verdict=cj_verdict,
                    classj_agreement_ratio=cj_agreement,
                    triage_quorum_verdict=tr_verdict,
                    triage_agreement_ratio=tr_agreement,
                    dual_veto=dual_veto,
                    node_count=node_count,
                    classj_verdicts_json=json.dumps(classj_nodes),
                    triage_verdicts_json=json.dumps(triage_nodes),
                )
            except Exception as store_exc:
                log.debug("IoSwarmAdjudicationCoordinator: audit store error (non-fatal): %s", store_exc)

            result = {
                "classj_quorum_verdict": cj_verdict,
                "classj_agreement_ratio": cj_agreement,
                "classj_node_verdicts": classj_nodes,
                "triage_quorum_verdict": tr_verdict,
                "triage_agreement_ratio": tr_agreement,
                "triage_node_verdicts": triage_nodes,
                "dual_veto": dual_veto,
                "dual_veto_score": DUAL_VETO_SCORE if dual_veto else 0.0,
                "node_count": node_count,
            }

            if dual_veto:
                log.info(
                    "IoSwarmAdjudicationCoordinator: dual-quorum veto — device=%s "
                    "classj=%s(%.2f) triage=%s(%.2f) → score_override≥%.2f",
                    device_id, cj_verdict, cj_agreement, tr_verdict, tr_agreement, DUAL_VETO_SCORE,
                )

            return result

        except Exception as exc:
            # Fail-open: adjudication error → CLEAR verdicts (avoid false bans)
            log.debug("IoSwarmAdjudicationCoordinator: fail-open on error: %s", exc)
            return {
                "classj_quorum_verdict": "CLEAR",
                "classj_agreement_ratio": 0.0,
                "classj_node_verdicts": [],
                "triage_quorum_verdict": "CLEAR",
                "triage_agreement_ratio": 0.0,
                "triage_node_verdicts": [],
                "dual_veto": False,
                "dual_veto_score": 0.0,
                "node_count": 0,
                "error": str(exc),
            }
