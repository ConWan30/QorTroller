"""Phase 109B — VHPRenewalSwarmTaskSpec: ioSwarm task spec for VHP renewal.

Parallel to VAPISwarmTaskSpec (Phase 109A adjudication spec).
Lower quorum threshold (0.60 vs BLOCK_QUORUM 0.67) — renewal is lower stakes than enforcement.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VHPRenewalSwarmTaskSpec:
    """ioSwarm-compatible task spec for VHP renewal authorization (Phase 109B).

    Nodes evaluate device's consecutive_clean history and recent BLOCK count to
    produce CERTIFY_RENEW / SKIP_RENEW / HOLD verdicts.
    """

    task_id:               str   = "vapi_vhp_renewal_v1"
    task_version:          str   = "1.0.0-phase109b"
    executor:              str   = "vapi_bridge"
    quorum_threshold:      float = 0.60  # CERTIFY_RENEW; renewal < enforcement stakes
    protocol_lens_address: str   = "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf"
    vhp_contract_address:  str   = "0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF"

    def to_json(self) -> dict:
        """Serialize to ioSwarm-compatible JSON.

        input_schema:  device_id(bytes32), token_id(uint256), consecutive_clean(uint8),
                       renewal_warning_days(uint8)
        output_schema: verdict(CERTIFY_RENEW/SKIP_RENEW/HOLD), confidence(float)
        quorum_config: threshold=0.60, tie_resolution=HOLD, min_nodes=3
        vhp_authorization_gate: isFullyEligible(bytes32) on VAPIProtocolLens
        """
        return {
            "task_id": self.task_id,
            "task_version": self.task_version,
            "executor": self.executor,
            "status": "phase109b_infrastructure_only",
            "description": (
                "VAPI VHP renewal authorization via ioSwarm multi-node quorum. "
                "Nodes evaluate consecutive_clean history and recent BLOCK count "
                "to produce CERTIFY_RENEW/SKIP_RENEW/HOLD verdicts. "
                "Phase 109B: emulator mode (IoSwarmNodeEmulator) until live nodes registered."
            ),
            "input_schema": {
                "device_id": "bytes32",
                "token_id": "uint256",
                "consecutive_clean": "uint8",
                "renewal_warning_days": "uint8",
            },
            "output_schema": {
                "verdict": "CERTIFY_RENEW | SKIP_RENEW | HOLD",
                "confidence": "float",
            },
            "quorum_config": {
                "threshold": self.quorum_threshold,
                "tie_resolution": "HOLD",
                "min_nodes": 3,
            },
            "vhp_authorization_gate": {
                "contract": self.protocol_lens_address,
                "function": "isFullyEligible(bytes32)",
                "description": (
                    "VAPIProtocolLens eligibility check — operator device must be "
                    "fully eligible before submitting renewal tasks"
                ),
            },
            "chain": {
                "name": "iotex_testnet",
                "chain_id": 4690,
                "vhp_contract": self.vhp_contract_address,
            },
            "w3bstream_applets": [
                "validate_poac_record",
                "process_gsr_packet",
            ],
        }

    def write_spec_file(self, path: str) -> None:
        """Write JSON spec to path (creates parent dirs as needed)."""
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_json(), fh, indent=2)
