"""
VAPI_CORE tool manifest — VAPI-EXT Phase 204+

All 149 VAPI_CORE tools declared as ToolDefinition objects for range-ownership
registration in ToolRegistry at BridgeAgent startup.

Tool numbers 1-143: BridgeAgent._TOOLS (in declaration order)
Tool numbers 144-149: CalibrationIntelligenceAgent tools

Handlers are placeholder lambdas — real dispatch happens inside BridgeAgent
and CalibrationIntelligenceAgent. This manifest exists purely for range
validation so sub-protocols cannot accidentally claim tools 1-149.
"""
from __future__ import annotations

from .._noop_handler import _noop
from ..tool_registry import ToolDefinition

# ---------------------------------------------------------------------------
# VAPI_CORE tool manifest (149 tools, numbers 1–149)
# ---------------------------------------------------------------------------

VAPI_CORE_TOOLS: list[ToolDefinition] = [
    # -----------------------------------------------------------------------
    # Phase 30 — Initial BridgeAgent tools (#1–#19)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=1, name="get_player_profile",
        description="Get a player's full profile: PHG score, record count, humanity probability.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=2, name="get_leaderboard",
        description="Get the top players ranked by confirmed PHG humanity score.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=3, name="get_leaderboard_rank",
        description="Get the 1-based leaderboard rank of a specific device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=4, name="run_pitl_calibration",
        description="Run PITL calibration and return the updated threshold distribution.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=5, name="get_continuity_chain",
        description="Get the PoAC chain of custody for a device: links, gaps, hashes.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=6, name="get_recent_records",
        description="Get the most recent PoAC records anchored on IoTeX.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=7, name="get_startup_diagnostics",
        description="Get bridge startup diagnostics: ZK artifacts, chain, config.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=8, name="get_phg_checkpoints",
        description="Get PHG score checkpoints for a device over time.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=9, name="check_eligibility",
        description="Check full tournament eligibility for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=10, name="get_pitl_proof",
        description="Get the ZK PITL session proof for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=11, name="get_behavioral_report",
        description="Get behavioral archaeology report for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=12, name="get_network_clusters",
        description="Get network correlation clusters detected by NCD.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=13, name="get_federation_status",
        description="Get federation bus status and connected agent count.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=14, name="get_detection_policy",
        description="Get the active PITL detection policy configuration.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=15, name="query_digest",
        description="Query the PITL digest for a device or session range.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=16, name="get_credential_status",
        description="Get the PHG credential status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=17, name="get_calibration_status",
        description="Get the L4 calibration status and threshold freshness.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=18, name="get_session_narrative",
        description="Get a human-readable narrative summary of a PITL session.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    ToolDefinition(
        number=19, name="compare_device_fingerprints",
        description="Compare two device biometric fingerprints for similarity.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=30,
    ),
    # -----------------------------------------------------------------------
    # Phase 50 — CalibrationIntelligenceAgent integration (#20)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=20, name="get_calibration_agent_status",
        description="Get the CalibrationIntelligenceAgent status and last event.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
    # -----------------------------------------------------------------------
    # Phase 51 — Game-Aware Profiling (#21)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=21, name="get_game_profile",
        description="Get the active game profile: L5 priority, L6-Passive stats.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=51,
    ),
    # -----------------------------------------------------------------------
    # Phase 55 — ioID Device Identity (#22)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=22, name="get_ioid_status",
        description="Get the ioID registration status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=55,
    ),
    # -----------------------------------------------------------------------
    # Phase 58 — Security Hardening tools (#23–#26)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=23, name="analyze_threshold_impact",
        description="Analyze the impact of a threshold change on historical sessions.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=58,
    ),
    ToolDefinition(
        number=24, name="predict_evasion_cost",
        description="Predict the adversarial cost to evade current thresholds.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=58,
    ),
    ToolDefinition(
        number=25, name="get_anomaly_trend",
        description="Get L4 anomaly trend for a device over recent sessions.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=58,
    ),
    ToolDefinition(
        number=26, name="generate_incident_report",
        description="Generate an operator incident report for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=58,
    ),
    # -----------------------------------------------------------------------
    # Phase 56 — ZK Tournament Passport (#27)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=27, name="generate_tournament_passport",
        description="Generate a ZK tournament passport for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=56,
    ),
    # -----------------------------------------------------------------------
    # Phase 59 — Controller 3D Digital Twin (#28)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=28, name="get_controller_twin_data",
        description="Get controller digital twin data for 3D visualization.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=59,
    ),
    # -----------------------------------------------------------------------
    # Phase 61 — Session Replay (#29)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=29, name="get_session_replay",
        description="Get session replay frames and feature history for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=61,
    ),
    # -----------------------------------------------------------------------
    # Phase 62 — Player Enrollment (#30)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=30, name="get_enrollment_status",
        description="Get the enrollment status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=62,
    ),
    # -----------------------------------------------------------------------
    # Phase 63 — L6b Neuromuscular Reflex (#31)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=31, name="get_reflex_baseline",
        description="Get the L6b neuromuscular reflex baseline for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=63,
    ),
    # -----------------------------------------------------------------------
    # Phase 65 — Autonomous Intelligence Layer (#32–#33)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=32, name="get_autonomous_rulings",
        description="Get autonomous agent rulings for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=65,
    ),
    ToolDefinition(
        number=33, name="request_adjudication",
        description="Request an autonomous adjudication for a session.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=65,
    ),
    # -----------------------------------------------------------------------
    # Phase 66 — Ruling Enforcement Pipeline (#34–#35)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=34, name="get_ruling_streak",
        description="Get the ruling streak and escalation state for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=66,
    ),
    ToolDefinition(
        number=35, name="override_ruling",
        description="Operator override of an autonomous ruling for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=66,
    ),
    # -----------------------------------------------------------------------
    # Phase 67 — MPC Ceremony Hardening (#36–#37)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=36, name="verify_ceremony_integrity",
        description="Verify the MPC ceremony integrity via ZK proof.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=67,
    ),
    ToolDefinition(
        number=37, name="get_suspension_status",
        description="Get the PHG credential suspension status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=67,
    ),
    # -----------------------------------------------------------------------
    # Phase 68 — Production Enforcement (#38–#40)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=38, name="get_zk_verifier_stats",
        description="Get ZK verifier statistics: proof count, pass/fail rate.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=68,
    ),
    ToolDefinition(
        number=39, name="get_enrollment_pipeline",
        description="Get the enrollment pipeline status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=68,
    ),
    ToolDefinition(
        number=40, name="request_live_adjudication",
        description="Request a live (non-dry-run) adjudication for a session.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=68,
    ),
    # -----------------------------------------------------------------------
    # Phase 70 — Protocol Intelligence (#41–#48)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=41, name="get_data_lineage",
        description="Get the data lineage chain for a calibration corpus entry.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=42, name="get_token_eligibility",
        description="Get VAPI token eligibility status for an operator device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=43, name="get_oracle_state",
        description="Get the SkillOracle on-chain state for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=44, name="compute_reward_score",
        description="Compute the VAPI reward score for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=45, name="get_ruling_provenance",
        description="Get the ruling provenance chain for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=46, name="get_validation_gate_status",
        description="Get the validation gate status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=47, name="publish_sovereignty_pledge",
        description="Publish a data sovereignty pledge for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    ToolDefinition(
        number=48, name="get_live_mode_status",
        description="Get the live mode status and activation state.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    # -----------------------------------------------------------------------
    # Phase 70 — federation alias (#49 — same name as #13, distinct slot)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=49, name="get_federation_status_v2",
        description="Get extended federation status (Phase 70 alias).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=70,
    ),
    # -----------------------------------------------------------------------
    # Phase 81 — ClassJ / Reactive Adjudication (#50–#51)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=50, name="get_class_j_assessment",
        description="Get the ClassJ threat assessment for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=81,
    ),
    ToolDefinition(
        number=51, name="get_reactive_adjudication_status",
        description="Get the reactive adjudication status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=81,
    ),
    # -----------------------------------------------------------------------
    # Phase 98 — Agent Supervisor / Gate Readiness (#52–#53)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=52, name="get_agent_supervisor_status",
        description="Get the agent supervisor status and triage prerequisite state.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=98,
    ),
    ToolDefinition(
        number=53, name="get_gate_readiness",
        description="Get the tournament gate readiness summary.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=98,
    ),
    # -----------------------------------------------------------------------
    # Phase 192 — CorpusDataCuratorAgent tools (#54–#62)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=54, name="get_session_contribution_weights",
        description="Get per-session contribution weights from the corpus curator.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=55, name="anchor_data_readiness_certificate",
        description="Anchor a data readiness certificate for the current corpus state.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=56, name="get_data_readiness_certificate",
        description="Get the latest data readiness certificate from the corpus curator.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=57, name="get_feature_correlation_status",
        description="Get the cross-feature temporal correlation status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=58, name="get_federated_corpus_quality",
        description="Get the federated corpus quality report (BP-007 compliant).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=59, name="anchor_erasure_certificate",
        description="Anchor a proof-of-erasure certificate for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=60, name="get_erasure_certificate",
        description="Get the erasure certificate for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=61, name="get_corpus_entropy_status",
        description="Get the corpus entropy monitor status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    ToolDefinition(
        number=62, name="get_data_provenance_chain",
        description="Get the provenance DAG chain for a corpus entry.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=192,
    ),
    # -----------------------------------------------------------------------
    # Phase 193 — FleetSignalCoherenceAgent tools (#63–#65, #67)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=63, name="get_fleet_coherence_summary",
        description="Get the fleet signal coherence summary.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=193,
    ),
    ToolDefinition(
        number=64, name="get_fleet_coherence_entries",
        description="Get fleet coherence log entries filtered by category.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=193,
    ),
    # -----------------------------------------------------------------------
    # Phase 194 — CoherenceFingerprintRegistry (#65)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=65, name="get_coherence_fingerprint_summary",
        description="Get the coherence fingerprint summary and persistent contradictions.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=194,
    ),
    # -----------------------------------------------------------------------
    # Phase 195 — Protocol Metabolism Index (#66)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=66, name="get_protocol_metabolism_index",
        description="Get the Protocol Metabolism Index (orphan resolution rate).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=195,
    ),
    ToolDefinition(
        number=67, name="resolve_coherence_entry",
        description="Resolve a fleet coherence entry with an operator note.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=193,
    ),
    # -----------------------------------------------------------------------
    # Phase 180 — Biometric Renewal Engine (#68)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=68, name="trigger_renewal_commitment",
        description="Trigger a separation ratio renewal commitment on-chain.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=180,
    ),
    # -----------------------------------------------------------------------
    # Phase 179 — ZK Ceremony Audit Gate (#69)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=69, name="get_ceremony_audit_status",
        description="Get the ZK ceremony audit gate status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=179,
    ),
    # -----------------------------------------------------------------------
    # Phase 178 — Biometric Credential TTL (#70)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=70, name="get_biometric_credential_age",
        description="Get the biometric credential age and TTL status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=178,
    ),
    # -----------------------------------------------------------------------
    # Phase 177 — Protocol Maturity Scoring (#71)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=71, name="get_protocol_maturity_score",
        description="Get the protocol maturity score (0.0–1.0) and tier.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=177,
    ),
    # -----------------------------------------------------------------------
    # Phase 170 — PoAC chain integrity (#72)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=72, name="get_poac_chain_integrity",
        description="Get the PoAC chain integrity status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=170,
    ),
    # -----------------------------------------------------------------------
    # Phase 168 — Age weight analysis (#73)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=73, name="get_age_weight_analysis_status",
        description="Get the age weight analysis status for the corpus.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=168,
    ),
    # -----------------------------------------------------------------------
    # Phase 165 — Post-erasure recompute (#74–#75)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=74, name="get_separation_ratio_recovery_status",
        description="Get the separation ratio recovery status post-erasure.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=165,
    ),
    ToolDefinition(
        number=75, name="trigger_post_erasure_recompute",
        description="Trigger a post-erasure separation ratio recompute.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=165,
    ),
    # -----------------------------------------------------------------------
    # Phase 163 — Consent snapshot delta (#76)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=76, name="get_consent_snapshot_delta",
        description="Get the consent snapshot delta for the corpus.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=163,
    ),
    # -----------------------------------------------------------------------
    # Phase 161 — Separation ratio commitment (#77)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=77, name="commit_separation_ratio",
        description="Commit the current separation ratio on-chain.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=161,
    ),
    # -----------------------------------------------------------------------
    # Phase 162 — Consent-aware corpus (#78–#79)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=78, name="get_consent_aware_corpus_status",
        description="Get the consent-aware corpus status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=162,
    ),
    ToolDefinition(
        number=79, name="get_consent_gate_status",
        description="Get the consent gate status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=162,
    ),
    # -----------------------------------------------------------------------
    # Phase 161 — Consent status (#80)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=80, name="get_consent_status",
        description="Get the data sovereignty consent status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=161,
    ),
    # -----------------------------------------------------------------------
    # Phase 159 — Biometric Privacy Compliance (#81)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=81, name="get_biometric_privacy_status",
        description="Get the biometric privacy compliance status (BP-001).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=159,
    ),
    # -----------------------------------------------------------------------
    # Phase 158 — Class K HMAC / PoHBG (#82–#83)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=82, name="get_pohbg_status",
        description="Get the Proof of Human Biometric Grip (PoHBG) status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=158,
    ),
    ToolDefinition(
        number=83, name="get_gsr_hmac_validation_status",
        description="Get the GSR HMAC validation status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=158,
    ),
    # -----------------------------------------------------------------------
    # Phase 157 — Fleet Consensus Snapshot (#84)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=84, name="get_fleet_consensus_snapshot",
        description="Get the fleet consensus snapshot for the current corpus.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=157,
    ),
    # -----------------------------------------------------------------------
    # Phase 156 — Enrollment Auto Guidance (#85)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=85, name="get_enrollment_auto_guidance_status",
        description="Get the enrollment auto-guidance status and urgency level.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=156,
    ),
    # -----------------------------------------------------------------------
    # Phase 155 — Controller Hardware Intelligence (#86)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=86, name="get_controller_hardware_status",
        description="Get the controller hardware intelligence status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=155,
    ),
    # -----------------------------------------------------------------------
    # Phase 154 — Capture Stagnation Monitor (#87)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=87, name="get_capture_stagnation_status",
        description="Get the capture stagnation monitor status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=154,
    ),
    # -----------------------------------------------------------------------
    # Phase 153 — SeparationRatioRegistry (#88)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=88, name="get_separation_ratio_registry_status",
        description="Get the on-chain separation ratio registry status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=153,
    ),
    # -----------------------------------------------------------------------
    # Phase 152 — Centroid Velocity Monitor (#89)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=89, name="get_centroid_velocity_status",
        description="Get the centroid velocity monitor status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=152,
    ),
    # -----------------------------------------------------------------------
    # Phase 151 — Enrollment Capture Guidance (#90)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=90, name="get_enrollment_capture_guidance",
        description="Get enrollment capture guidance (per-probe, per-player).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=151,
    ),
    # -----------------------------------------------------------------------
    # Phase 150 — Separation Defensibility Gate (#91)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=91, name="get_separation_defensibility_status",
        description="Get the separation ratio defensibility gate status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=150,
    ),
    # -----------------------------------------------------------------------
    # Phase 148 — Agent Calibration Health (#92)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=92, name="get_agent_calibration_health",
        description="Get the agent calibration health summary.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=148,
    ),
    # -----------------------------------------------------------------------
    # Phase 147 — Tournament Activation Chain (#93)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=93, name="get_tournament_activation_chain",
        description="Get the tournament activation chain and P0 conditions.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=147,
    ),
    # -----------------------------------------------------------------------
    # Phase 146 — L4 Recalibration (#94)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=94, name="run_l4_recalibration",
        description="Run an L4 threshold recalibration against the corpus.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=146,
    ),
    # -----------------------------------------------------------------------
    # Phase 112 — PoAd On-Chain Anchoring (#95)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=95, name="get_ioswarm_poad_anchor_status",
        description="Get the ioSwarm PoAd on-chain anchor status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=112,
    ),
    # -----------------------------------------------------------------------
    # Phase 131 — IoSwarm Live Node (#96)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=96, name="ping_ioswarm_nodes",
        description="Ping live ioSwarm nodes and return latency stats.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=131,
    ),
    # -----------------------------------------------------------------------
    # Phase 120 — BT Transport Foundation (#97)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=97, name="get_usb_stability_status",
        description="Get the USB transport stability status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=120,
    ),
    # -----------------------------------------------------------------------
    # Phase 131 — IoSwarm Node Registry (#98)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=98, name="get_ioswarm_node_registry_status",
        description="Get the ioSwarm live node registry status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=131,
    ),
    # -----------------------------------------------------------------------
    # Phase 130 — Swarm Operator Gate (#99)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=99, name="get_swarm_operator_gate_status",
        description="Get the VAPISwarmOperatorGate on-chain status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=130,
    ),
    # -----------------------------------------------------------------------
    # Phase 129 — Separation Ratio Breakthrough Monitor (#100)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=100, name="get_separation_ratio_breakthrough",
        description="Get the separation ratio breakthrough monitor status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=129,
    ),
    # -----------------------------------------------------------------------
    # Phase 128 — Tournament Readiness Score (#101)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=101, name="get_tournament_readiness_score",
        description="Get the tournament readiness score (6-signal formula).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=128,
    ),
    # -----------------------------------------------------------------------
    # Phase 127 — Tournament Pre-Launch Validation (#102)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=102, name="run_tournament_preflight",
        description="Run the tournament pre-launch validation suite.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=127,
    ),
    # -----------------------------------------------------------------------
    # Phase 126 — L4 Router Status (#103)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=103, name="get_l4_router_status",
        description="Get the L4 per-battery threshold router status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=126,
    ),
    # -----------------------------------------------------------------------
    # Phase 125 — Per-Battery Threshold Calibrator (#104)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=104, name="apply_l4_battery_calibration",
        description="Apply a per-battery L4 calibration run.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=125,
    ),
    # -----------------------------------------------------------------------
    # Phase 124 — L4 Threshold Track Registry (#105)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=105, name="get_l4_threshold_tracks",
        description="Get the L4 per-battery threshold track registry.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=124,
    ),
    # -----------------------------------------------------------------------
    # Phase 123 — L4 Calibration Staleness Monitor (#106)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=106, name="get_l4_calibration_status",
        description="Get the L4 calibration staleness status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=123,
    ),
    # -----------------------------------------------------------------------
    # Phase 122 — VHP Confidence Score Multiplier (#107)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=107, name="get_confidence_score_multiplier_status",
        description="Get the VHP confidence score separation ratio multiplier status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=122,
    ),
    # -----------------------------------------------------------------------
    # Phase 121 — Touchpad Spatial Entropy / Separation Ratio (#108)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=108, name="get_separation_ratio_status",
        description="Get the inter-person separation ratio monitoring status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=121,
    ),
    # -----------------------------------------------------------------------
    # Phase 120 — BT Transport (#109)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=109, name="get_bt_transport_status",
        description="Get the BLE transport foundation status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=120,
    ),
    # -----------------------------------------------------------------------
    # Phase 119 — Override Lifecycle Management (#110–#111)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=110, name="revoke_device_epoch_override",
        description="Revoke an epoch window override for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=119,
    ),
    ToolDefinition(
        number=111, name="get_epoch_window_override_status",
        description="Get the epoch window override status for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=119,
    ),
    # -----------------------------------------------------------------------
    # Phase 118 — Epoch Window Auto-Tune / Cold-Start Override (#112–#113)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=112, name="set_device_epoch_override",
        description="Set an epoch window override for a cold-start device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=118,
    ),
    ToolDefinition(
        number=113, name="get_epoch_window_auto_tune",
        description="Get the epoch window auto-tune recommendation.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=118,
    ),
    # -----------------------------------------------------------------------
    # Phase 117 — Per-Device Epoch Freshness Heatmap (#114)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=114, name="get_epoch_window_device_heatmap",
        description="Get the per-device epoch freshness heatmap.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=117,
    ),
    # -----------------------------------------------------------------------
    # Phase 116 — Epoch-Window Analytics (#115)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=115, name="get_epoch_window_analytics",
        description="Get epoch window analytics: p50/p95/recommended window.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=116,
    ),
    # -----------------------------------------------------------------------
    # Phase 114 — VHP Mint Dual-Primitive Gate (#116)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=116, name="get_vhp_dual_gate_log",
        description="Get the VHP dual-primitive gate log.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=114,
    ),
    # -----------------------------------------------------------------------
    # Phase 113 — VAPIDualPrimitiveGate (#117)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=117, name="check_dual_eligibility",
        description="Check dual-primitive eligibility (PoAC + PoAd).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=113,
    ),
    # -----------------------------------------------------------------------
    # Phase 111 — PoAd Registry (#118)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=118, name="get_adjudication_registry_status",
        description="Get the AdjudicationRegistry on-chain status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=111,
    ),
    # -----------------------------------------------------------------------
    # Phase 110 — IoSwarm VHP Mint (#119)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=119, name="get_ioswarm_vhp_mint_status",
        description="Get the ioSwarm VHP mint authorization status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=110,
    ),
    # -----------------------------------------------------------------------
    # Phase 109C — IoSwarm Dual-Quorum Adjudication (#120)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=120, name="get_ioswarm_adjudication_status",
        description="Get the ioSwarm dual-quorum adjudication status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=109,
    ),
    # -----------------------------------------------------------------------
    # Phase 109B — IoSwarm VHP Renewal (#121)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=121, name="get_ioswarm_renewal_status",
        description="Get the ioSwarm VHP renewal coordinator status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=109,
    ),
    # -----------------------------------------------------------------------
    # Phase 109A — IoSwarm Bridge Adapter (#122)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=122, name="get_ioswarm_status",
        description="Get the ioSwarm consensus aggregator status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=109,
    ),
    # -----------------------------------------------------------------------
    # Phase 108 — Tournament Readiness (#123)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=123, name="get_tournament_readiness",
        description="Get the tournament readiness summary (pre-Phase 128).",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=108,
    ),
    # -----------------------------------------------------------------------
    # Phase 105 — Live Mode Readiness (#124)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=124, name="get_live_mode_readiness",
        description="Get the live mode readiness check results.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=105,
    ),
    # -----------------------------------------------------------------------
    # Phase 104 — Epistemic Config (#125–#126)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=125, name="get_epistemic_config",
        description="Get the epistemic consensus configuration and weights.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=104,
    ),
    ToolDefinition(
        number=126, name="get_protocol_maturity",
        description="Get the protocol maturity tier assessment.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=104,
    ),
    # -----------------------------------------------------------------------
    # Phase 102 — Activation Sequence (#127)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=127, name="run_activation_sequence",
        description="Run the tournament commit-activation sequence.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=102,
    ),
    # -----------------------------------------------------------------------
    # Phase 109B — VHP Renewal Log (#128)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=128, name="get_vhp_renewal_log",
        description="Get the VHP renewal log for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=109,
    ),
    # -----------------------------------------------------------------------
    # Phase 100 — Edge AI Profile (#129)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=129, name="get_edge_ai_profile",
        description="Get the edge AI inference profile for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=100,
    ),
    # -----------------------------------------------------------------------
    # Phase 103 — QuickSilver Collateral (#130)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=130, name="get_quicksilver_collateral_status",
        description="Get the QuickSilver stIOTX collateral status for an operator.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=103,
    ),
    # -----------------------------------------------------------------------
    # Phase 102 — Activation Status (#131)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=131, name="get_activation_status",
        description="Get the tournament activation status and commit conditions.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=102,
    ),
    # -----------------------------------------------------------------------
    # Phase 98 — Operator Status (#132)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=132, name="get_operator_status",
        description="Get the operator staking and registration status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=98,
    ),
    # -----------------------------------------------------------------------
    # Phase 100 — Epistemic Consensus Log (#133)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=133, name="get_epistemic_consensus_log",
        description="Get the epistemic consensus log entries.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=100,
    ),
    # -----------------------------------------------------------------------
    # Phase 102 — Live Mode Guard Log (#134)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=134, name="get_live_mode_guard_log",
        description="Get the live mode guard log entries.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=102,
    ),
    # -----------------------------------------------------------------------
    # Phase 98 — Enforcement Certificate (#135)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=135, name="get_enforcement_certificate",
        description="Get the enforcement certificate for a ruling.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=98,
    ),
    # -----------------------------------------------------------------------
    # Phase 102 — Activation Audit (#136)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=136, name="get_activation_audit",
        description="Get the activation audit trail.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=102,
    ),
    # -----------------------------------------------------------------------
    # Phase 101 — Escalation Ruling Log (#137)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=137, name="get_escalation_ruling_log",
        description="Get the ruling escalation log for a device.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=101,
    ),
    # -----------------------------------------------------------------------
    # Phase 100 — Activation Log (#138)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=138, name="get_activation_log",
        description="Get the activation sequence log entries.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=100,
    ),
    # -----------------------------------------------------------------------
    # Phase 98 — Triage Report (#139)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=139, name="get_triage_report",
        description="Get the epistemic triage report for a session.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=98,
    ),
    # -----------------------------------------------------------------------
    # Phase 98 — Shadow Enforcement Log (#140)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=140, name="get_shadow_enforcement_log",
        description="Get the shadow enforcement log entries.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=98,
    ),
    # -----------------------------------------------------------------------
    # Phase 90 — Protocol Intelligence (#141–#143)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=141, name="get_protocol_intelligence",
        description="Get the protocol intelligence report.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=90,
    ),
    ToolDefinition(
        number=142, name="get_campaign_status",
        description="Get the active campaign and enrollment status.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=90,
    ),
    ToolDefinition(
        number=143, name="get_corpus_status",
        description="Get the calibration corpus status and session counts.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=90,
    ),
    # -----------------------------------------------------------------------
    # Phase 50 — CalibrationIntelligenceAgent tools (#144–#149)
    # -----------------------------------------------------------------------
    ToolDefinition(
        number=144, name="get_threshold_history",
        description="Get the L4 threshold calibration history.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
    ToolDefinition(
        number=145, name="get_feature_variance_report",
        description="Get the per-feature variance report for the corpus.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
    ToolDefinition(
        number=146, name="get_zero_variance_features",
        description="Get structurally zero-variance features in the calibration corpus.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
    ToolDefinition(
        number=147, name="get_separation_analysis",
        description="Get the inter-person separation analysis report.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
    ToolDefinition(
        number=148, name="get_pending_recalibration_flags",
        description="Get pending recalibration flags from the calibration agent.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
    ToolDefinition(
        number=149, name="trigger_recalibration",
        description="Trigger a threshold recalibration via the calibration agent.",
        handler=_noop, sub_protocol="VAPI_CORE", phase_introduced=50,
    ),
]

assert len(VAPI_CORE_TOOLS) == 149, f"Expected 149 tools, got {len(VAPI_CORE_TOOLS)}"
