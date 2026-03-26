"""Phase 109A — VAPISwarmTaskSpec: ioSwarm-compatible task specification.

The frozen dataclass serialises to an ioSwarm JSON task spec.
Output written to scripts/vapi-swarm-agent.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# VHP auth gate: require VAPIProtocolLens.isFullyEligible(operatorDeviceId)
_VHP_AUTH_GATE_ADDRESS = "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf"
_VHP_CONTRACT_ADDRESS = "0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF"


@dataclass(frozen=True)
class VAPISwarmTaskSpec:
    """ioSwarm task specification for VAPI PITL adjudication.

    All fields are frozen — never mutate after construction.
    ``to_json()`` serialises to the ioSwarm agent JSON format.
    """

    task_id: str = "vapi_pitl_adjudication_v1"
    task_version: str = "1.0.0-phase109a"
    executor: str = "vapi_bridge"
    quorum_threshold: float = 0.60
    block_quorum_threshold: float = 0.67
    w3bstream_applets: tuple = ("validate_poac_record", "process_gsr_packet")
    protocol_lens_address: str = _VHP_AUTH_GATE_ADDRESS
    vhp_contract_address: str = _VHP_CONTRACT_ADDRESS

    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        """Serialise to ioSwarm-compatible dict.

        Output schema matches ioSwarm task-spec v1 format.
        Written to scripts/vapi-swarm-agent.json by write_spec_file().
        """
        return {
            "task_id": self.task_id,
            "task_version": self.task_version,
            "executor": self.executor,
            "status": "phase109a_infrastructure_only",
            "input_schema": {
                "device_id": "bytes32",
                "record_hash": "bytes32",
                "inference_code": "uint8",
                "evidence_json": "string",
            },
            "output_schema": {
                "verdict": "string",
                "confidence": "float",
                "evidence_hash": "bytes32",
                "commitment_hash": "bytes32",
            },
            "quorum_config": {
                "general_threshold": self.quorum_threshold,
                "block_threshold": self.block_quorum_threshold,
                "tie_resolution": "HOLD",
                "w1_note": "BLOCK requires block_threshold; ties and insufficient quorum -> HOLD",
            },
            "reward_condition": (
                "verdict_matches_quorum AND trailing_false_positive_rate < 0.01"
                " AND consecutive_clean >= 5"
            ),
            "vhp_authorization_gate": {
                "contract": "VAPIProtocolLens",
                "method": "isFullyEligible(bytes32)",
                "address": self.protocol_lens_address,
                "error": "VAPI: human presence required",
                "vhp_contract": self.vhp_contract_address,
            },
            "w3bstream_applets": list(self.w3bstream_applets),
            "chain": {
                "network": "iotex_testnet",
                "chain_id": 4690,
            },
            "phase_notes": {
                "current": "109A: infrastructure only, not yet registered with live ioSwarm nodes",
                "next": "109B: VHPRenewalAgent migrated as first task spec",
                "roadmap": "110: VHP as universal IoTeX DePIN human authorization primitive",
            },
        }

    def write_spec_file(self, path: str) -> None:
        """Serialise spec to *path* (JSON)."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_json(), fh, indent=2)
            fh.write("\n")
