"""Phase 101B — Edge AI Bridge Profile.

Reports the VAPI bridge's footprint in IoTeX's Edge AI framework.
The 13-agent autonomous fleet IS an edge AI system — verifiable inferences
produced at the bridge edge, anchored on IoTeX L1, not in a data center.

get_edge_ai_profile() never raises.
"""

import logging
import time

log = logging.getLogger(__name__)

# Agent fleet inventory (from Phase 79–100 agent registrations)
_AGENT_FLEET = [
    "SessionAdjudicator",
    "SessionAdjudicatorValidationAgent",
    "CeremonyWatchdogAgent",
    "RulingEnforcementAgent",
    "RulingProvenanceAnchorAgent",
    "ClassJDetector",
    "DivergenceTriageAgent",
    "AgentSupervisor",
    "ProtocolIntelligenceAgent",
    "LiveModeActivationPipeline",
    "FederationBroadcastAgent",
    "LiveModeActivationAgent",
    "GSRRegistryAgent",
    "VHPRenewalAgent",
]


def get_edge_ai_profile(cfg=None, store=None) -> dict:
    """Return the VAPI bridge's Edge AI profile for IoTeX ecosystem positioning (Phase 101B).

    Maps VAPI's architecture onto IoTeX's three-layer Real-World AI stack:
      - ioID (Verify): VAPIioIDRegistry LIVE (Phase 55)
      - Quicksilver/W3bstream (Process): PoAC + GSR applets LIVE (Phase 99B)
      - Realms (Perceive): deferred until >= 100k daily PoAC

    Never raises.
    """
    try:
        dry_run_active = bool(getattr(cfg, "agent_dry_run_mode", True)) if cfg else True
        agent_autonomy = "advisory" if dry_run_active else "full"

        # Attempt to get PoAC rate from store
        poac_rate_per_hour = 0.0
        if store is not None:
            try:
                with store._conn() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM records "
                        "WHERE created_at >= ?",
                        (time.time() - 3600,),
                    ).fetchone()
                    poac_rate_per_hour = float(row["cnt"]) if row else 0.0
            except Exception:
                pass

        # LLM availability
        llm_available = False
        try:
            import anthropic  # noqa: F401
            llm_available = True
        except ImportError:
            pass

        inference_mode = "llm_augmented" if llm_available else "local_rule_fallback"

        # QuickSilver integration status
        qs_active = bool(
            getattr(cfg, "quicksilver_collateral_address", "") if cfg else ""
        )

        return {
            # Fleet identity
            "protocol": "VAPI — Verified Autonomous Physical Intelligence",
            "category": "AGaaS (Agentic-as-a-Service)",
            "depin_category": "Verified Autonomous Physical Intelligence / DePIN",
            "iotex_ecosystem": "IoTeX L1 (chain 4690 testnet / 4689 mainnet)",

            # Edge AI footprint
            "agent_fleet_size": len(_AGENT_FLEET),
            "agent_fleet": _AGENT_FLEET,
            "inference_mode": inference_mode,
            "edge_compute_model": "cpu_bound_no_gpu",
            "edge_inference_note": (
                "Rule fallback (local SLM-equivalent) + optional LLM augmentation. "
                "No GPU required. Runs on commodity hardware at the bridge edge."
            ),
            "agent_autonomy_level": agent_autonomy,
            "poac_rate_per_hour": poac_rate_per_hour,

            # IoTeX layer integration
            "iotex_layer_integration": {
                "ioID": True,           # Phase 55 — VAPIioIDRegistry LIVE
                "w3bstream": True,      # Phase 99B — PoAC + GSR applets LIVE
                "quicksilver": qs_active,  # Phase 101A — stIOTX collateral
                "realms": False,        # Deferred until >= 100k daily PoAC
            },

            # Composability
            "composable_gate": "VAPIProtocolLens.isFullyEligible(deviceId)",
            "soulbound_credential": "VAPIVerifiedHumanProof (ERC-4671, 90d expiry)",
            "cross_chain_bridge": "VAPIVerifiedHumanProofBridge (LayerZero V2 OApp)",

            # Positioning statement (IoTeX Edge AI alignment)
            "positioning": (
                "VAPI is the first live AGaaS deployment of IoTeX's Real-World AI vision "
                "applied to human cognition: verifiable (ioID-anchored PoAC), local "
                "(edge bridge, not cloud), decentralized (operator registry + VHP "
                "composability), and physically-grounded (certified DualShock Edge "
                "hardware + GSR biometrics pipeline)."
            ),

            # Phase 109A: ioSwarm integration layer (infrastructure-only)
            "ioswarm_integration": {
                "layer": "ioswarm_consensus",
                "status": "infrastructure_only",
                "phase": "109A",
                "task_spec": "vapi_pitl_adjudication_v1",
                "applets": ["validate_poac_record", "process_gsr_packet"],
                "enabled": False,
                "next_step": "Phase 109B: VHPRenewalAgent task spec migration",
            },

            "timestamp": time.time(),
        }
    except Exception as exc:
        log.warning("get_edge_ai_profile: %s", exc)
        return {
            "protocol": "VAPI",
            "agent_fleet_size": 14,
            "error": str(exc),
            "timestamp": time.time(),
        }
