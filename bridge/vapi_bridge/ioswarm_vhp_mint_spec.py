"""Phase 110 — VAPIVHPMintSwarmTaskSpec: ioSwarm task spec for VHP mint authorization.

W1 (fail-CLOSED): VHP mint is irreversible (soulbound on-chain) — fail direction is CLOSED.
W2 (swarm fingerprint): SHA-256(node_verdicts_json) creates two-era VHP provenance audit trail.
MINT_QUORUM = 0.80 — stricter than BLOCK_QUORUM=0.67; matches DUAL_VETO_SCORE from Phase 109C.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VAPIVHPMintSwarmTaskSpec:
    """Frozen task spec for ioSwarm VHP mint authorization coordination."""

    task_id:                 str   = "vapi_vhp_mint_authorization_v1"
    task_version:            str   = "1.0.0-phase110"
    executor:                str   = "vapi_bridge"
    mint_quorum:             float = 0.80   # W1: stricter than BLOCK_QUORUM=0.67; irreversible action
    fail_direction:          str   = "CLOSED"  # W1: fail-CLOSED (OPPOSITE of renewal fail-OPEN)
    swarm_fingerprint_field: str   = "SHA-256(node_verdicts_json)"  # W2: provenance audit
    protocol_lens_address:   str   = "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf"
    vhp_contract_address:    str   = "0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF"

    def to_json(self) -> dict:
        return {
            "task_id":       self.task_id,
            "task_version":  self.task_version,
            "executor":      self.executor,
            "status":        "phase110_infrastructure_only",
            "quorum_config": {
                "threshold":       self.mint_quorum,
                "fail_direction":  self.fail_direction,
                "note":            "AUTHORIZE requires >=80% node agreement; exceptions block mint",
            },
            "w2_provenance": {
                "swarm_fingerprint": self.swarm_fingerprint_field,
                "audit_trail":       "two-era VHP: pre-110 (no fingerprint) vs post-110 (quorum-authorized)",
            },
            "input_schema": {
                "device_id":           "str — device identifier",
                "consecutive_clean":   "int — session streak length",
                "recent_block_count":  "int — number of recent BLOCK enforcement rulings",
            },
            "output_schema": {
                "authorized":       "bool — True if >= 80% nodes AUTHORIZE",
                "quorum_verdict":   "str — AUTHORIZE | DENY (majority)",
                "agreement_ratio":  "float — fraction of AUTHORIZE nodes",
                "swarm_fingerprint": "str — SHA-256 of node_verdicts_json (W2)",
            },
            "vhp_authorization_gate": {
                "contract":   "VAPIProtocolLens",
                "address":    self.protocol_lens_address,
                "method":     "isFullyEligible(operatorDeviceId)",
                "vhp_contract": self.vhp_contract_address,
            },
        }

    def write_spec_file(self, path: "str | None" = None) -> str:
        """Write task spec JSON to scripts/vapi-vhp-mint-swarm-agent.json (or path)."""
        if path is None:
            root = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
            )
            path = os.path.join(root, "vapi-vhp-mint-swarm-agent.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_json(), fh, indent=2)
        return path
