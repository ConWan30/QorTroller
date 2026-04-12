-- vapi_ext_002_agent_manifest.sql
-- VAPI-EXT Phase 204+ — Agent Manifest table
--
-- Canonical catalogue of all 36 VAPI_CORE agents.
-- Sub-protocols add their own agents to this table via their migration files.
-- Enables monitoring agents and sub-protocols to enumerate the full fleet
-- without reading Python source files.
--
-- agent_number matches the VAPI agent fleet numbering (Agent #1 = SessionAdjudicator, etc.)
-- class_name is the Python class that implements the agent.
-- module_path is the relative path within bridge/vapi_bridge/.
-- phase_introduced is the VAPI phase that added this agent.
-- sub_protocol identifies the owning sub-protocol (VAPI_CORE for all baseline agents).

CREATE TABLE IF NOT EXISTS vapi_ext_agent_manifest (
    agent_number      INTEGER PRIMARY KEY,
    class_name        TEXT NOT NULL,
    module_path       TEXT NOT NULL,
    phase_introduced  INTEGER NOT NULL,
    sub_protocol      TEXT NOT NULL DEFAULT 'VAPI_CORE',
    active            INTEGER NOT NULL DEFAULT 1,   -- boolean: 1=True
    created_at        REAL NOT NULL
);

-- Insert all 36 VAPI_CORE agents (idempotent via INSERT OR IGNORE)

INSERT OR IGNORE INTO vapi_ext_agent_manifest
    (agent_number, class_name, module_path, phase_introduced, sub_protocol, active, created_at)
VALUES
    (1,  'SessionAdjudicator',                   'session_adjudicator.py',                65,  'VAPI_CORE', 1, strftime('%s','now')),
    (2,  'CalibrationIntelligenceAgent',          'calibration_intelligence_agent.py',     50,  'VAPI_CORE', 1, strftime('%s','now')),
    (3,  'SeparationRatioMonitorAgent',           'separation_ratio_monitor_agent.py',     129, 'VAPI_CORE', 1, strftime('%s','now')),
    (4,  'PoAdAnchorAgent',                       'poad_anchor_agent.py',                  112, 'VAPI_CORE', 1, strftime('%s','now')),
    (5,  'ClassJDetector',                        'class_j_detector.py',                   81,  'VAPI_CORE', 1, strftime('%s','now')),
    (6,  'RulingEnforcementAgent',                'ruling_enforcement_agent.py',           66,  'VAPI_CORE', 1, strftime('%s','now')),
    (7,  'VHPRenewalAgent',                       'vhp_renewal_agent.py',                  109, 'VAPI_CORE', 1, strftime('%s','now')),
    (8,  'CalibrationWatcher',                    'calibration_agent.py',                  50,  'VAPI_CORE', 1, strftime('%s','now')),
    (9,  'ProactiveMonitor',                      'proactive_monitor.py',                  50,  'VAPI_CORE', 1, strftime('%s','now')),
    (10, 'InsightSynthesizer',                    'insight_synthesizer.py',                50,  'VAPI_CORE', 1, strftime('%s','now')),
    (11, 'FederationBus',                         'federation_bus.py',                     34,  'VAPI_CORE', 1, strftime('%s','now')),
    (12, 'TournamentActivationChainAgent',        'tournament_activation_chain_agent.py',  70,  'VAPI_CORE', 1, strftime('%s','now')),
    (13, 'EnrollmentManager',                     'enrollment_manager.py',                 62,  'VAPI_CORE', 1, strftime('%s','now')),
    (14, 'IoSwarmRenewalCoordinator',             'ioswarm_renewal_coordinator.py',        109, 'VAPI_CORE', 1, strftime('%s','now')),
    (15, 'IoSwarmAdjudicationCoordinator',        'ioswarm_adjudication_coordinator.py',   109, 'VAPI_CORE', 1, strftime('%s','now')),
    (16, 'IoSwarmVHPMintCoordinator',             'ioswarm_vhp_mint_coordinator.py',       110, 'VAPI_CORE', 1, strftime('%s','now')),
    (17, 'ControllerHardwareIntelligenceAgent',   'controller_hardware_intelligence_agent.py', 155, 'VAPI_CORE', 1, strftime('%s','now')),
    (18, 'AgentCalibrationIntegrityMonitor',      'agent_calibration_monitor.py',          100, 'VAPI_CORE', 1, strftime('%s','now')),
    (19, 'ControllerHardwareIntelligenceAgent',   'controller_hardware_intelligence_agent.py', 155, 'VAPI_CORE', 1, strftime('%s','now')),
    (20, 'EnrollmentAutoGuidanceAgent',           'enrollment_auto_guidance_agent.py',     156, 'VAPI_CORE', 1, strftime('%s','now')),
    (21, 'FleetConsensusSnapshotAgent',           'fleet_consensus_snapshot_agent.py',     157, 'VAPI_CORE', 1, strftime('%s','now')),
    (22, 'BiometricPrivacyComplianceAgent',       'biometric_privacy_compliance_agent.py', 159, 'VAPI_CORE', 1, strftime('%s','now')),
    (23, 'SeparationRatioRecoveryAgent',          'separation_ratio_recovery_agent.py',    152, 'VAPI_CORE', 1, strftime('%s','now')),
    (24, 'AgeWeightAnalysisAgent',                'age_weight_analysis_agent.py',          124, 'VAPI_CORE', 1, strftime('%s','now')),
    (25, 'PersonaBreakDetectorAgent',             'persona_break_detector_agent.py',       182, 'VAPI_CORE', 1, strftime('%s','now')),
    (26, 'MaturityElevationGateAgent',            'maturity_elevation_gate_agent.py',      183, 'VAPI_CORE', 1, strftime('%s','now')),
    (27, 'ProtocolMaturityScoringAgent',          'protocol_maturity_scoring_agent.py',    177, 'VAPI_CORE', 1, strftime('%s','now')),
    (28, 'ReEnrollmentAttestationAgent',          'reenrollment_attestation_agent.py',     185, 'VAPI_CORE', 1, strftime('%s','now')),
    (29, 'AttestationBoundRenewalAgent',          'attestation_bound_renewal_agent.py',    186, 'VAPI_CORE', 1, strftime('%s','now')),
    (30, 'AttestationOpSecAdvisorAgent',          'attestation_opsec_advisor_agent.py',    187, 'VAPI_CORE', 1, strftime('%s','now')),
    (31, 'BiometricStationarityOracleAgent',      'biometric_stationarity_oracle_agent.py',188, 'VAPI_CORE', 1, strftime('%s','now')),
    (32, 'ProtocolIntelligenceRecordAgent',       'protocol_intelligence_record_agent.py', 189, 'VAPI_CORE', 1, strftime('%s','now')),
    (33, 'LivePresenceSignalingAgent',            'live_presence_signaling_agent.py',      190, 'VAPI_CORE', 1, strftime('%s','now')),
    (34, 'CorpusDataCuratorAgent',                'data_curator_agent.py',                 192, 'VAPI_CORE', 1, strftime('%s','now')),
    (35, 'FleetSignalCoherenceAgent',             'fleet_signal_coherence_agent.py',       193, 'VAPI_CORE', 1, strftime('%s','now')),
    (36, 'CoherenceFingerprintRegistry',          'fleet_signal_coherence_agent.py',       194, 'VAPI_CORE', 1, strftime('%s','now'));
