# ENTITY: Agent Fleet Registry (All 22 Agents)

[VAPI:Phase166:MEMORY.md:MEASURED]

## Registry Table

All 22 agents in `VAPI_AGENTS.md` fleet as of Phase 166.

| # | Agent | Phase | Status | Primary Function |
|---|-------|-------|--------|-----------------|
| 1 | SessionIngestor | 1 | LIVE | PoAC chain ingestion + validation |
| 2 | PITLStackExecutor | 1 | LIVE | L0-L6 PITL stack execution per record |
| 3 | SessionAdjudicator | 65 | LIVE | 5-min poll; BLOCK/CERTIFY/HOLD verdicts (dry_run=True) |
| 4 | RulingEnforcementAgent | 66 | LIVE | Streak escalation FLAG×5→HOLD/HOLD×2→BLOCK |
| 5 | CredentialLifecycleAgent | 67 | LIVE | PHGCredential suspend/reinstate lifecycle |
| 6 | ProactiveMonitor | 52 | LIVE | Runtime health checks; decoupled from agent instance |
| 7 | EnrollmentManager | 62 | LIVE | Auto PHGCredential mint after enrollment_min=10 NOMINAL |
| 8 | ZKProofAgent | 56 | LIVE | Groth16 proof generation; C3 constraint binding |
| 9 | PoAdAnchorAgent | 112 | LIVE | 60-sec cycle; SHA-256(sorted_verdicts+quorum+ts_ns) |
| 10 | VHPRenewalAgent | 109B | LIVE | ioSwarm VHP renewal quorum (CERTIFY_RENEW_QUORUM=0.60) |
| 11 | IoSwarmAdjudicationCoordinator | 109C | LIVE | DUAL_VETO=0.80; fail-open CLEAR; CLASSJ_BLOCK=0.67 |
| 12 | IoSwarmVHPMintCoordinator | 110 | LIVE | MINT_QUORUM=0.80; fail-CLOSED; swarm fingerprint |
| 13 | CalibrationIntelligenceAgent | 50 | LIVE | claude-sonnet-4-6; 6 tools; 30-min event consumer |
| 14 | BridgeAgent | 50 | LIVE | claude-sonnet-4-6; 28+ tool bindings |
| 15 | SeparationRatioMonitorAgent | 129 | LIVE | 300s poll; fires separation_ratio_breakthrough bus |
| 16 | TournamentActivationChainAgent | 135 | LIVE | `auto_activate_on_breakthrough=False` PERMANENT |
| 17 | CaptureStagnationMonitor | 154 | LIVE | Rolling sessions/day; stagnant when <0.5/day |
| 18 | AgentCalibrationIntegrityMonitor (ACIM) | 148 | LIVE | 16 self-tests every 15 min |
| 19 | ControllerHardwareIntelligenceAgent | 155 | LIVE | Multi-controller tier registry |
| 20 | EnrollmentAutoGuidanceAgent | 156 | LIVE | 1-hour poll; synthesizes agents 15/17/18/19 |
| 21 | FleetConsensusSnapshotAgent | 157 | LIVE | PoFC = SHA-256(sorted_verdicts+ratio+ts_ns) |
| 22 | BiometricPrivacyComplianceAgent | 159 | LIVE | TBD(t)=e^(-λt), τ_half=90d; GDPR monitoring |

## Critical Invariants [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

- Agent #16: `auto_activate_on_breakthrough=False` PERMANENT — compile-time constant, not config
- Agent #18: Anti-single-validator; cross-validates all other agents independently
- Agent #3: `dry_run=True` default — never set False without N≥100 live adjudications
- Epistemic threshold: 0.65 (Phase 147) — ClassJ+Supervisor alone (0.60) cannot reach gate

## Fleet Growth

| Phase | New Agents | Fleet Count |
|-------|-----------|-------------|
| Phase 1–80 | 1–14 (core PITL) | 14 |
| Phase 129 | +#15 SeparationRatioMonitor | 15 |
| Phase 135 | +#16 TournamentActivationChain | 16 |
| Phase 148 | +#18 ACIM | 17 |
| Phase 154 | +#17 CaptureStagnation | 18 |
| Phase 155 | +#19 ControllerHardwareIntelligence | 19 |
| Phase 156 | +#20 EnrollmentAutoGuidance | 20 |
| Phase 157 | +#21 FleetConsensusSnapshot | 21 |
| Phase 159 | +#22 BiometricPrivacyCompliance | **22** |

## Related Pages

- [[agent_fleet]]
- [[agent_21_fleet_consensus]]
- [[agent_22_biometric_privacy]]
- [[epistemic_consensus]]
