"""Phase 109C — VAPIAdjudicationSwarmTaskSpec: frozen task spec for ClassJ+Triage quorum.

This spec describes the ioSwarm task that decentralizes ClassJDetector+DivergenceTriageAgent
verdicts to a multi-node quorum with dual-quorum veto capability.

Key invariants:
  - classj_block_quorum = 0.67  (enforcement standard; NOT 0.60 renewal standard)
  - triage_block_quorum = 0.67  (enforcement standard)
  - dual_veto_score = 0.80       (W2: score override when both quorums BLOCK independently)
  - status = "phase109c_infrastructure_only" (testnet; nodes are emulators)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VAPIAdjudicationSwarmTaskSpec:
    """Frozen ioSwarm task specification for VAPI ClassJ+Triage adjudication quorum.

    The dual-quorum veto (W2 novel) fires ONLY when both classj_quorum_verdict==BLOCK
    AND triage_quorum_verdict==BLOCK.  FLAG+BLOCK or BLOCK+FLAG is insufficient —
    both signals must be at maximum severity independently.  This prevents single-signal
    evasion from triggering false veto while giving operators mathematical confidence
    to activate live mode (false positive probability drops multiplicatively).
    """

    task_id: str = "vapi_classj_triage_adjudication_v1"
    task_version: str = "1.0.0-phase109c"
    executor: str = "vapi_bridge"

    # Quorum thresholds — enforcement standard (stricter than CERTIFY_RENEW_QUORUM=0.60)
    classj_block_quorum: float = 0.67
    triage_block_quorum: float = 0.67

    # W2 dual-quorum veto: consensus_score = max(consensus_score, dual_veto_score)
    # when BOTH classj AND triage quorums independently reach BLOCK
    dual_veto_score: float = 0.80

    # Contract addresses (IoTeX testnet — ALL LIVE)
    protocol_lens_address: str = "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf"
    ruling_registry_address: str = "0xa3A2356C90E642a7c510d0C726EC515EA720c621"

    def to_json(self) -> dict:
        """Return ioSwarm-compatible task spec as a dictionary."""
        return {
            "task_id": self.task_id,
            "task_version": self.task_version,
            "executor": self.executor,
            "status": "phase109c_infrastructure_only",
            "description": (
                "Decentralized ClassJ+Triage adjudication with dual-quorum veto. "
                "Phase 109C: N=5 emulator nodes (testnet, code-before-operators). "
                "Real ioSwarm nodes use independent hardware stacks in production."
            ),
            "input_schema": {
                "device_id": "str — controller/device identifier",
                "session_id": "str — session identifier (empty string valid)",
                "entropy_variance": "float — Phase 81 ClassJDetector signal (higher=human-like)",
                "escalated": "bool — DivergenceTriageAgent escalation flag",
                "triage_patterns": "str|null — colon-sep triage pattern string from Phase 91",
            },
            "output_schema": {
                "classj_quorum_verdict": "str — BLOCK|FLAG|CLEAR",
                "classj_agreement_ratio": "float — fraction of nodes agreeing on verdict",
                "triage_quorum_verdict": "str — BLOCK|FLAG|CLEAR",
                "triage_agreement_ratio": "float — fraction of nodes agreeing on verdict",
                "dual_veto": "bool — True when BOTH classj==BLOCK AND triage==BLOCK",
                "dual_veto_score": "float — score override applied when dual_veto==True",
                "node_count": "int — number of emulator nodes evaluated",
            },
            "quorum_config": {
                "classj_block_quorum": self.classj_block_quorum,
                "triage_block_quorum": self.triage_block_quorum,
                "tie_resolution": "HOLD",
                "note": (
                    "0.67 = enforcement standard (NOT 0.60 renewal standard). "
                    "Tie resolution HOLD prevents false positives on split verdicts."
                ),
            },
            "dual_veto_config": {
                "dual_veto_score": self.dual_veto_score,
                "dual_veto_condition": "classj_quorum_verdict == BLOCK AND triage_quorum_verdict == BLOCK",
                "score_override_formula": "consensus_score = max(consensus_score, 0.80)",
                "rationale": (
                    "W2 novel — exclusive to VAPI. When ClassJ AND Triage both independently "
                    "reach BLOCK (67% node agreement each), the joint false-positive probability "
                    "drops multiplicatively. Score clamped to 0.80 > epistemic threshold 0.60 "
                    "→ always drives BLOCK verdict. Gives operators mathematical confidence "
                    "to flip dry_run=False."
                ),
            },
            "vhp_authorization_gate": {
                "contract": "VAPIProtocolLens",
                "address": self.protocol_lens_address,
                "method": "isFullyEligible(operatorDeviceId)",
                "description": "Operator device must hold valid VHP to submit adjudication tasks",
            },
            "fail_open_direction": {
                "adjudication_errors": "CLEAR (avoid false positives)",
                "note": (
                    "OPPOSITE of VHPRenewal fail-open (which returns approved=True). "
                    "Adjudication errors lean toward CLEAR to prevent false bans."
                ),
            },
            "w1_security_boundary": {
                "testnet_note": (
                    "All 5 emulator nodes share same seed/logic — testnet only "
                    "(code-before-operators, MockGSRGrip precedent). Evasion of one "
                    "node evades all nodes simultaneously. This is acceptable for testnet; "
                    "production ioSwarm nodes use independent hardware stacks "
                    "(architectural security property, not code-level)."
                ),
            },
            "w3bstream_applets": [
                "validate_poac_record",
                "process_adjudication_result",
            ],
            "protocol_lens_address": self.protocol_lens_address,
            "ruling_registry_address": self.ruling_registry_address,
        }

    def write_spec_file(self, output_path: str | None = None) -> str:
        """Write task spec JSON to file and return the path."""
        if output_path is None:
            # Default: scripts/ at repo root
            _here = os.path.dirname(os.path.abspath(__file__))
            _repo = os.path.normpath(os.path.join(_here, "..", ".."))
            output_path = os.path.join(_repo, "scripts", "vapi-adjudication-swarm-agent.json")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(self.to_json(), fh, indent=2)
        return output_path
