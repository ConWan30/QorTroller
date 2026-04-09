# Phase 177 — ProtocolMaturityScoringAgent (Agent #26)

**Status**: COMPLETE  
**Date**: 2026-04-08  
**Cycle**: Autoresearch Cycle 8 (final phase)

## Summary

Phase 177 adds the ProtocolMaturityScoringAgent, the 26th and final agent of Autoresearch Cycle 8. It synthesizes 6 upstream agent signals into a single unified `maturity_score` (0.0–1.0) that serves as a protocol production-readiness oracle. The maturity tier (ALPHA / BETA / PRODUCTION_CANDIDATE) is the first composable cross-agent signal in VAPI — all prior agents produced single-domain scores; this agent produces a protocol-wide synthesis.

## Deliverables

| Component | Notes |
|-----------|-------|
| `protocol_maturity_log` table | insert_protocol_maturity_log(6 components) / get_protocol_maturity_status() |
| schema(177,"protocol_maturity") | registered in store._SCHEMA_VERSIONS |
| GET /agent/protocol-maturity-score | 10 keys: protocol_maturity_enabled/maturity_score/maturity_tier/6 components/timestamp |
| Tool #126 get_protocol_maturity_score | BridgeAgent tool |
| ProtocolMaturityScoringResult(9 slots) | fail-safe: error path returns ALPHA tier, 0.0 score |
| VAPIProtocolMaturityScoring SDK | get_score() method, error handling |
| config +protocol_maturity_enabled=True | default on |
| agent fleet 25→26 | |

## Maturity Formula

```
maturity_score = 0.25×separation + 0.20×chain_integrity + 0.15×consent
               + 0.15×biometric_freshness + 0.15×agent_calibration + 0.10×enrollment
```

Weights sum to 1.0. All components are [0.0–1.0].

## Tier Thresholds

| Tier | Range | Meaning |
|------|-------|---------|
| ALPHA | < 0.50 | Protocol in active development |
| BETA | 0.50–0.85 | Protocol approaching stability |
| PRODUCTION_CANDIDATE | ≥ 0.85 | Requires separation_ratio > 1.0 + all gates met |

**Current tier**: ALPHA (separation_ratio=0.569 < 0.70 gate → separation_component is low)

## SDK Naming Collision Fix (2026-04-08)

Phase 177 originally shipped `ProtocolMaturityResult`/`VAPIProtocolMaturity` but these names were already used by Phase 104's PMI-based classes at `sdk/vapi_sdk.py` lines 1692/1708. Python's last-definition-wins caused 5 Phase 104 test failures. Fixed by renaming Phase 177 classes to `ProtocolMaturityScoringResult`/`VAPIProtocolMaturityScoring`.

## Test Delta

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Bridge | 1990 | 1998 | +8 |
| SDK | 321 | 325 | +4 |
| Hardhat | 468 | 468 | 0 |

## WHAT_IF

**WIF-027 W1 — Maturity score gaming by silencing agents**  
An operator could disable specific agents (e.g., consent ledger) to prevent low scores from flowing into the maturity formula. A silence_penalty component should reduce maturity_score when any contributing agent is disabled.  
→ Phase 178 candidate

**WIF-027 W2 — DePIN marketplace trustworthiness oracle**  
maturity_score ≥ 0.85 (PRODUCTION_CANDIDATE) is designed as the gateway condition for DePIN data marketplace listing. Operators of data marketplace nodes can call GET /agent/protocol-maturity-score to gate listing eligibility. This creates the first cross-protocol composable primitive linking tournament anti-cheat to data economy.

## Dependencies

| Agent | Contributes |
|-------|-------------|
| SeparationRatioMonitorAgent (#15) | separation_component via separation_defensibility_log |
| PoACChainIntegrityMonitor (#25) | chain_integrity_component |
| ConsentLedgerAgent (Phase 160) | consent_component |
| BiometricPrivacyComplianceAgent (#22) | biometric_freshness_component |
| AgentCalibrationIntegrityMonitor (#18) | agent_calibration_component |
| EnrollmentAutoGuidanceAgent (#20) | enrollment_component |

## Bus Channel

Phase 177 adds the `maturity` bus channel to the P2P Knowledge Bus (vapi_managed_agents.py). Managed agents subscribe to this channel to receive tier transitions.
