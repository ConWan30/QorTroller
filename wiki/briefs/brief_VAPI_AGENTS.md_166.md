# VAPI Wiki Ingest Brief
## Source: VAPI_AGENTS.md | Phase 166 | 2026-04-08T01:14:12.014474+00:00
## Provenance tag: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]

---

## INSTRUCTION TO CLAUDE CODE

You are reading this brief to generate VAPI wiki pages.
No external API is called. You are the LLM.

Do the following in order:
1. Read the source content below
2. For each domain listed, create or update the corresponding wiki page
3. Every factual claim must include: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]
4. Run check_invariants() on your proposed content before writing
   (call: python vapi_wiki.py check "<proposed_content_snippet>")
5. Write each page using:
   python vapi_wiki.py write_page <page_type> "<entity_name>" 166 "<content>"
   OR write the markdown file directly to wiki/<type>/<name>.md
6. After all pages are written: python vapi_wiki.py snapshot

---

## Pre-Scan Results

### Invariant Check on Source
Status: WARNINGS DETECTED
  [WARN] EPISTEMIC: Threshold 0.65 (Phase 147 hardening). Cannot regress. triage_prereq_required=True also required.

### Extracted Metrics
{
  "separation_ratio": "0",
  "phase": "57",
  "l4_anomaly": "0",
  "l4_continuity": "0",
  "epistemic": "5"
}

### Domains Detected in Source
{
  "phase_state": false,
  "separation_ratio": true,
  "agents": true,
  "contracts": true,
  "l4_calibration": true,
  "what_if": true,
  "privacy": false,
  "zk_circuit": true,
  "ioswarm": true,
  "count": 7
}

---

## Pages to Create/Update

Based on domain detection, Claude Code should create these wiki pages:

- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  Content: current value, gate, root cause, mixed probe status
  Provenance: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]
- wiki/entities/agent_fleet.md [TYPE: ENTITY]
  Content: all 166 agents, new agents added this phase, epistemic threshold
  Provenance: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]
- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  Content: 7.009/5.367 frozen values, staleness (12-feat vs 13-feat), recalibration candidate
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
- wiki/what_if/w1_w2_entries.md [TYPE: WHAT_IF]
  Content: new W1/W2 entries from this phase
  Provenance: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]
- wiki/concepts/zk_circuit.md [TYPE: CONCEPT]
  Content: Groth16, BN254, Poseidon(8), nPublic=5, ceremony block #41723255
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

---

## Provenance Rules (enforce these — do not skip)

- Every factual claim: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]
- Measured values: [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]
- Designed (not yet measured): [VAPI:Phase166:VAPI_AGENTS.md:DESIGNED]
- Frozen protocol constants: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
- Claims without source: tag as [NEEDS_PROVENANCE]
- Contradictions: preserve BOTH claims, mark [CONTRADICTION: unresolved]

---

## FROZEN VALUES (never modify these in wiki pages)

{
  "poac_bytes": "228",
  "record_hash": "SHA-256(raw[:164])",
  "nPublic": "5",
  "zk_hash": "Poseidon(8)",
  "ceremony_beacon": "#41723255",
  "l4_anomaly": "7.009",
  "l4_continuity": "5.367",
  "epistemic_threshold": "0.65",
  "triage_prereq": "True",
  "auto_activate": "False",
  "block_quorum": "0.67",
  "mint_quorum": "0.80",
  "vhp_expiry_days": "90",
  "separation_gate": "0.70"
}

If the source text contradicts any frozen value, flag it as:
[CONTRADICTION: source claims X | frozen value is Y | [VAPI:Phase166:VAPI_AGENTS.md:MEASURED]]
Write to: wiki/contradictions.md

---

## Wiki Page Format

Each page must follow this structure:

```markdown
# [Page Type]: [Entity Name]

[VAPI:Phase166:VAPI_AGENTS.md:MEASURED]

## Current State
[factual description with provenance on each claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|
| ... | ... | [VAPI:Phase166:VAPI_AGENTS.md:MEASURED] | LIVE/DESIGNED/STALE |

## Related Pages
- [[entity_1]]
- [[entity_2]]
```

---

## Source Content

# VAPI AGENTS — For Claude Code Context

## Agent Identity: VAPI Master Expert

**You are Claude Code, the Architectural Infrastructure Creator of VAPI and an Expert across all domains comprising the VAPI ecosystem.**

**Your Expertise Profile**:
- **DePIN/Blockchain Architect**: IoTeX L1 integration, Solidity smart contract design, ZK proof systems (Groth16), on-chain verification, token economics, distributed consensus (ioSwarm), wallet management, MPC ceremonies
- **AI/ML/FL/AGI Engineer**: PITL stack (L0-L6) classification, behavioral ML for anti-cheat, federated learning threat correlation, Mahalanobis biometric analysis, temporal rhythm detection, humanoid bot classification, epistemic consensus protocols
- **IoT-Sensors-Electronics Engineer**: HID protocol implementation, sensor fusion (accelerometer/gyroscope), embedded firmware (C/Zephyr RTOS), real-time data acquisition, hardware calibration, BLE transport, power management, ATECC608A secure elements
- **Cryptographic Systems Engineer**: SHA-256/Poseidon hashing, ECDSA-P256 signatures, zero-knowledge circuits, Merkle proofs, device identity (ioID), credential lifecycle (VHP soulbound tokens)
- **Distributed Systems Architect**: Asyncio agent orchestration, SQLite WAL concurrency, MQTT/Mosquitto messaging, FastAPI bridge services, cross-bridge threat correlation, event-driven architectures
- **Anti-Cheat Systems Specialist**: Gaming anti-cheat protocols, wallhack/aimbot detection, injection detection (HID-XInput Oracle), tournament integrity, competitive gaming ecosystems
- **Firmware Engineer**: nRF9160 embedded development, Zephyr RTOS, sensor polling optimization, 228-byte PoAC record generation, power-efficient cryptography
- **Full-Stack Integration Engineer**: Python SDK design, OpenAPI client generation, dataclass/slot optimization, pytest automation, Hardhat contract testing

**Your Role**: When reading this file, you are the agent fleet commander. You can spawn parallel expert contexts for any of these 20 agents. You know their fail modes, epistemic weights, and tool inventories. Orchestrate them for complex cross-domain tasks.

> **INSTRUCTION TO CLAUDE CODE**: This file defines the VAPI agent fleet as callable expert subsystems.
> When reading this file, you must:
> 1. Reference specific agents when proposing changes to their domains
> 2. Spawn parallel expert contexts for complex cross-domain work
> 3. Respect each agent's fail mode (fail-open vs fail-closed)
> 4. Use agent-specific tools from the 104 available

---

## Agent Overview

VAPI operates **22 specialized agents** in the bridge service. Each agent is a background asyncio task with specific expertise, tools, and decision logic. This document maps them for Claude Code expert spawning.

> **SYNC NOTE**: Agents 21–22 added in Phases 157/159. Synced 2026-04-05.

### Agent Table

| # | Agent | LLM | Cycle | Expertise | Fail Mode | Tools |
|---|-------|-----|-------|-----------|-----------|-------|
| 1 | SessionAdjudicator | claude-opus-4-6 | 5 min | PITL L0-L6 pipeline, PoAd anchoring | Fail-open | 15 |
| 2 | CalibrationIntelligenceAgent | claude-sonnet-4-6 | 30 min | L4 thresholds, per-battery tracks | Fail-closed | 6 |
| 3 | SeparationRatioMonitorAgent | — | 300 sec | Tikhonov correction, breakthrough | Fail-open | 3 |
| 4 | PoAdAnchorAgent | — | 60 sec | ioSwarm consensus, dual-quorum | Non-blocking | 2 |
| 5 | ClassJDetector | claude-opus-4-6 | 60 sec | Humanoid bot classification | Fail-open | 8 |
| 6 | RulingEnforcementAgent | — | 5 min | Streak escalation, on-chain commit | Fail-closed | 4 |
| 7 | VHPRenewalAgent | claude-opus-4-6 | 5 min | VHP credential renewal | Fail-closed | 6 |
| 8 | CalibrationWatcher | — | Real-time | Threshold drift detection | Advisory | 3 |
| 9 | ProactiveMonitor | — | 60 sec | Real-time cluster detection | Advisory | 5 |
| 10 | InsightSynthesizer | claude-opus-4-6 | 6 hrs | Retrospective digests, policy | Advisory | 6 |
| 11 | FederationBus | — | 120 sec | Cross-bridge threat correlation | Privacy-preserving | 4 |
| 12 | TournamentActivationChainAgent | claude-opus-4-6 | Manual | Tournament readiness orchestration | Manual | 10 |
| 13 | EnrollmentManager | — | Event | PHGCredential mint after enrollment | Fail-closed | 4 |
| 14 | IoSwarmRenewalCoordinator | — | Event | ioSwarm consensus for VHP renewal | Fail-open | 5 |
| 15 | IoSwarmAdjudicationCoordinator | — | Event | Dual-quorum veto for adjudication | Fail-open | 5 |
| 16 | IoSwarmVHPMintCoordinator | — | Event | ioSwarm quorum for VHP minting | Fail-closed | 6 |
| 17 | ControllerHardwareIntelligenceAgent (v1) | claude-opus-4-6 | Event-driven | Multi-controller capability mapping, PITL layer availability, tier eligibility, transport negotiation | Fail-open | 8 |
| 18 | AgentCalibrationIntegrityMonitor (ACIM) | — | 15 min | Cross-validates 16 agents' calibration invariants independently; anti-single-validator | Fail-open | 1 |
| 19 | ControllerHardwareIntelligenceAgent | claude-opus-4-6 | 1 hour | Attested vs Standard tier mapping; composite key profile_hash:battery_type:transport_type; default thresholds 7.009/5.367; controller_hardware_profiles table | Fail-open | 8 |
| 20 | EnrollmentAutoGuidanceAgent | — | 1 hour | Synthesizes Phase 151 guidance + Phase 154 stagnation + Phase 152 velocity + Phase 155 controller status; urgency HIGH/MEDIUM/LOW; fires enrollment_complete → TournamentActivationChainAgent | Fail-open | 1 |
| 21 | FleetConsensusSnapshotAgent | — | 1800 sec | WIF-012 dual-condition overall_ready gate; WIF-016 cov_stability_check() 3 regime labels; WIF-013 PoFC hash=SHA-256(sorted_verdicts+ratio+ts_ns); fleet_consensus_snapshot_log | Fail-open | 1 |
| 22 | BiometricPrivacyComplianceAgent | — | 5 min | BP-001 Temporal Biometric Decay TBD(t)=e^(-λt) τ_half=90d; warning when mean_decay_factor<0.25 (≈2 half-lives); privacy_compliance_log; biometric_decay_warning bus event | Advisory | 1 |

---

## Agent 1: SessionAdjudicator

**Trigger**: `/vapi expert adjudicate 
... [truncated — full content in VAPI-WORKFLOW.v2/VAPI_AGENTS.md]

---

## After Writing Pages

Run these commands in order:
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot
  python vapi_wiki.py autoresearch_feed

The autoresearch_feed command syncs any wiki gaps into the AutoResearch
experiment log so the next /vapi autoresearch cycle can address them.
