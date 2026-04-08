# ENTITY: VAPI Agent Fleet

[VAPI:Phase166:MEMORY.md:MEASURED]

## Overview

VAPI operates a 22-agent autonomous fleet running continuously behind `isFullyEligible()`.
No human intervention is required for routine operation. Agents communicate via the
federation bus, publish events, and cross-validate each other's calibration via ACIM (#18).

**Current count:** 22 agents [VAPI:Phase166:MEMORY.md:MEASURED]

## Full Registry [VAPI:Phase166:MEMORY.md:MEASURED]

| # | Agent | Phase | Status | Key Function |
|---|-------|-------|--------|-------------|
| 1–14 | Core PITL agents | 1–80 | LIVE | L2/L3/L4/L5/L6 detection + enforcement |
| 15 | SeparationRatioMonitorAgent | 129 | LIVE | Polls separation ratio; fires breakthrough bus event |
| 16 | TournamentActivationChainAgent | 135 | LIVE | Tournament deployment sequencing; `auto_activate_on_breakthrough=False` PERMANENT |
| 17 | CaptureStagnationMonitor | 154 | LIVE | Rolling sessions/day rate; stagnant when <0.5/day |
| 18 | AgentCalibrationIntegrityMonitor (ACIM) | 148 | LIVE | 16 self-tests every 15 min; cross-validates all agents |
| 19 | ControllerHardwareIntelligenceAgent | 155 | LIVE | Multi-controller tier registry; `multi_controller_enabled=False` |
| 20 | EnrollmentAutoGuidanceAgent | 156 | LIVE | 1-hour poll; synthesizes guidance from agents 15/17/18/19 |
| 21 | FleetConsensusSnapshotAgent | 157 | LIVE | PoFC hash = SHA-256(sorted_verdicts + ratio + ts_ns) |
| 22 | BiometricPrivacyComplianceAgent | 159 | LIVE | TBD(t) = e^(-lambda*t), tau_half=90d; GDPR monitoring |

## Critical Invariants [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

- **Agent #16:** `auto_activate_on_breakthrough=False` is PERMANENT. Non-negotiable.
  This is a compile-time constant, not a config flag. Any proposal to set it True is HARD STOP.
- **ACIM (#18):** Anti-single-validator architecture. Each agent's calibration invariant
  is cross-validated independently. `agent_calibration_monitor_enabled=True` default.
- **Stable EMA track:** Updates NOMINAL sessions only. Security invariant, never override.
  Agent that enforces this: SessionAdjudicator (core fleet).
- **Epistemic consensus threshold:** 0.65 (Phase 147 hardening). ClassJ + Supervisor alone
  (0.60) no longer reaches the gate. `triage_prereq_required=True`.

## Agent #20 — EnrollmentAutoGuidanceAgent [VAPI:Phase166:MEMORY.md:MEASURED]

Synthesizes four upstream signals:
- Phase 151 capture guidance (per-probe per-player gap breakdown)
- Phase 154 stagnation monitor (sessions/day velocity)
- Phase 152 centroid velocity (ratio velocity between consecutive snapshots)
- Phase 155 controller hardware status

**Outputs:**
- `urgency_level`: HIGH / MEDIUM / LOW
- `sessions_needed_total`: sum of per-player gaps across all 4 probe types
- `estimated_days`: sessions_needed / sessions_per_day rate
- `overall_ready`: True only when sessions_needed==0 AND defensible==True (WIF-012)
- `cov_regime_status`: diagonal_stable / transition_warning / full_covariance_active (WIF-016)

**Action on `overall_ready=True`:** fires `enrollment_complete` event →
`TournamentActivationChainAgent` receives it but does NOT auto-activate
(`auto_activate_on_breakthrough=False` PERMANENT).

## Agent #21 — FleetConsensusSnapshotAgent [VAPI:Phase166:MEMORY.md:MEASURED]

Proof of Fleet Consensus (PoFC):
```
pofc_hash = SHA-256(sorted_verdicts + separation_ratio_str + ts_ns)
```

Every 1,800 seconds. Anchors fleet consensus state cryptographically.
`fleet_consensus_snapshot_log` table. `GET /agent/fleet-consensus-snapshot`.

WIF-012 dual-condition `overall_ready` gate enforced here:
`overall_ready = (sessions_needed == 0) AND (defensible == True)`

## Agent #22 — BiometricPrivacyComplianceAgent [VAPI:Phase166:MEMORY.md:MEASURED]

Temporal Biometric Decay monitoring (BP-001):
```
TBD(t) = e^(-lambda * t)
lambda = ln(2) / tau_half
tau_half = 90 days
```

Warning triggered when `mean_decay_factor < 0.25` (~2 half-lives, ~180 days old).
Fires `biometric_decay_warning` bus event. `privacy_compliance_log` table.
`biometric_privacy_enabled=True` default.

## ACIM Self-Tests (16 per cycle) [VAPI:Phase166:MEMORY.md:MEASURED]

Agent #18 runs every 15 minutes:
- L4 threshold bounds check (7.009/5.367 within valid range)
- Stable EMA track integrity
- Epistemic consensus threshold ≥ 0.65
- ioSwarm quorum values (BLOCK_QUORUM=0.67, MINT_QUORUM=0.80)
- ZK circuit invariants (nPublic=5, Poseidon(8))
- auto_activate_on_breakthrough=False
- Wire format 228B
- Chain hash SHA-256(raw[:164])

## Related Pages

- [[phase_166]]
- [[separation_ratio]]
- [[l4_thresholds]]
- [[epistemic_consensus]]
- [[poac_wire_format]]
