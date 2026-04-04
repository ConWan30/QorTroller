# VAPI CONTEXT — For Claude Code Context

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

**Your Role**: When reading this file, you are the system state oracle. You must know the current phase, wallet balance, contract addresses, and tournament readiness status before proposing any action. Ground all proposals in this reality.

> **INSTRUCTION TO CLAUDE CODE**: This file is the ground truth of current VAPI system state.
> When reading this file, you must:
> 1. Reference this state before proposing changes
> 2. Update this file when phases complete (only then)
> 3. Verify contract addresses and balances before on-chain operations
> 4. Check tournament readiness conditions before declaring "ready"

---

## 1. Current Phase Status

**Active Phase**: Phase 156 — EnrollmentAutoGuidanceAgent (agent #20)
**Phase Start**: 2026-04-04
**Phase Status**: COMPLETE
**Next Phase**: Phase 157 (TBD — user approval required)

### Phase 150 Deliverables (COMPLETE 2026-04-03)

| Component | Status | Evidence |
|-----------|--------|----------|
| separation_defensibility_log table | ✅ LIVE | insert/get store methods + schema(150) |
| config.min_touchpad_sessions_per_player | ✅ LIVE | default=10 (WIF-010 target) |
| analyze_interperson_separation.py | ✅ LIVE | --session-consistency + --min-n-per-player flags |
| GET /agent/separation-defensibility-status | ✅ LIVE | 6 keys (defensible/ratio/n_per_player/min_n_per_player/all_pairs_above_1/found) |
| Tool #106 get_separation_defensibility_status | ✅ LIVE | BridgeAgent tool, 6 required keys |
| SeparationDefensibilityResult + VAPISeparationDefensibility SDK | ✅ LIVE | 6 slots, never raises |
| openapi.yaml SeparationDefensibilityStatus schema | ✅ LIVE | GET /agent/separation-defensibility-status path |
| SDK_VERSION | ✅ UPDATED | 3.0.0-phase148→3.0.0-phase150 |
| WIF-010 formal closure | ✅ DOCUMENTED | defensible=False (P1=3/P2=4/P3=4 < min_n=10) |
| WIF-011 added | ✅ DOCUMENTED | Session type mixing integrity gap (OPEN) |
| Bridge tests | ✅ PASS | 1,868 pytest (+40 Phases 152-156) |
| SDK tests | ✅ PASS | 265 tests (+20 Phases 152-156) |
| Hardhat tests | ✅ PASS | 468 tests (+6 Phase 153 SeparationRatioRegistry) |

### Phase 149 Deliverables (COMPLETE 2026-04-03)

| Component | Status | Evidence |
|-----------|--------|----------|
| calibration_agent.py _CURRENT_PHASE=148 | ✅ LIVE | DB-first ratio + dir-based player count |
| hardware_calibration_watcher.py | ✅ LIVE | default ratio 0.362→1.261 + Phase 148 docstring |
| calibration_intelligence_agent.py | ✅ LIVE | Phase 148 prompt + Phase 143 values ratio=1.261/LOO=63.6% |
| CALIBRATE_SETUP.ps1 | ✅ LIVE | Phase 109→148 reference |
| Bridge tests | ✅ PASS | 1,808 pytest (+10 Phase 149) |
| SDK tests | ✅ PASS | 237 tests (unchanged) |
| Hardhat tests | ✅ PASS | 462 tests (unchanged) |

### Phase 148 Deliverables (COMPLETE 2026-04-02)

| Component | Status | Evidence |
|-----------|--------|----------|
| AgentCalibrationIntegrityMonitor (ACIM) | ✅ LIVE | agent #18, 16 self-tests every 15 min |
| mcp_server.py | ✅ CODE COMPLETE | mcp_server_enabled=False default; 6 MCP resources |
| agent_calibration_health table | ✅ LIVE | insert/get |
| Tool #105 get_agent_calibration_health | ✅ LIVE | 6 keys |
| GET /agent/calibration-health | ✅ LIVE | endpoint |

### Claude Code Guidance

When working on VAPI:
- Check this section first to understand current system state
- Phase 149 COMPLETE — Phase 150 requires user approval first
- Reference specific agent numbers and tool numbers from this table
- If test counts differ from this table (expected: 1808/462/237), investigate regression

---

## 2. On-Chain State (IoTeX Testnet)

### Wallet Status

| Wallet | Address | Balance | Status |
|--------|---------|---------|--------|
| Active Bridge | 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 | ~0.35 IOTX | OPERATIONAL |
| Deploy Requirement | — | ~0.40 IOTX | **BLOCKED** |

**Critical**: ~0.35 IOTX insufficient for VAPISwarmOperatorGate.sol deployment (~0.13 IOTX). Funding required to unblock Phase 130B.

### Live Contracts (39 Total)

#### Core Protocol (23 contracts)

| Contract | Address | Phase | Status |
|----------|---------|-------|--------|
| PoACVerifier | 0x... | Phase 1 | LIVE |
| TieredDeviceRegistry | 0x... | Phase 10 | LIVE |
| PHGRegistry | 0x... | Phase 9 | LIVE |
| PHGCredential | 0x... | Phase 99C | LIVE |
| TournamentGate | 0x... | Phase 104 | LIVE |
| PITLSessionRegistry | 0x8da0A497234C57914a46279A8F938C07D3Eb5f12 | Phase 62 | LIVE |
| PitlSessionProofVerifier | 0x07D3ca1548678410edC505406f022399920d4072 | Phase 62 | LIVE |
| VAPIProtocolLens | 0x1972... | Phase 108 | LIVE |
| VAPIDualPrimitiveGate | 0xd7b1... | Phase 113 | LIVE |
| AdjudicationRegistry | 0x44CF... | Phase 111 | LIVE |
| RulingRegistry | 0xa3A2356C90E642a7c510d0C726EC515EA720c621 | Phase 68 | LIVE |
| CeremonyRegistry | 0x739B5fae312834bA2a7e44525bA5f54853C5672f | Phase 67 | LIVE |
| [Additional 11 core contracts] | — | Various | LIVE |

#### Supporting Contracts (16 contracts)

| Contract | Purpose | Status |
|----------|---------|--------|
| VAPIioIDRegistry | Device identity | LIVE |
| PITLTournamentPassport | ZK passport | LIVE |
| [Additional 14 supporting] | — | LIVE |

### ZK Ceremony Status (Phase 67)

| Circuit | Contributors | Status | Block Beacon |
|---------|--------------|--------|--------------|
| PitlSessionProof | 3 | ✅ COMPLETE | #41723255 |
| TournamentPassport | 3 | ✅ COMPLETE | #41723255 |
| [Additional circuits] | 3 | ✅ COMPLETE | #41723255 |

**Verification**: `verifyCeremony()` returns true on all circuits.

### Claude Code Guidance

When proposing on-chain operations:
- Check wallet balance before suggesting deployments
- Verify contract address matches deployed-addresses.json
- Reference specific phase numbers when discussing contract capabilities
- **Red flag**: Proposing mainnet operations (testnet only currently)

---

## 3. Bridge Service State

### Test Suite Status

| Component | Test Count | Status | Last Run |
|-----------|------------|--------|----------|
| Bridge pytest | 1,868 | ✅ PASS | 2026-04-04 |
| SDK tests | 265 | ✅ PASS | 2026-04-04 |
| Hardhat tests | 468 | ✅ PASS | 2026-04-04 |
| Hardware tests | 37 | ⚠️ HARDWARE-ONLY | Manual |
| E2E tests | 14 | ⚠️ REQUIRES NODE | Manual |

### BridgeAgent Tools

**Available**: 105 deterministic tools (expanded from 28 original)
**Key Tools** (sample):
- #1-20: Core bridge operations
- #21: get_game_profile (Phase 51)
- #22: get_ioid_status (Phase 55)
- #23: generate_tournament_passport (Phase 56)
- #28: get_controller_twin_data (Phase 59)
- #29: get_session_replay (Phase 61)
- #30: get_enrollment_status (Phase 62)
- #31: get_reflex_baseline (Phase 63)
- #32-33: get_autonomous_rulings, request_adjudication (Phase 65)
- #34-35: get_ruling_streak, override_ruling (Phase 66)
- #75-81: ioSwarm tools (Phase 109A-114)
- #90-99: Separation ratio, calibration, BT tools (Phase 120-131)
- #104: get_tournament_activation_chain (Phase 135)

### Background Agents

| Agent | Cycle Time | Status | Last Action |
|-------|------------|--------|-------------|
| SessionAdjudicator | 5 min | ACTIVE | 2026-04-03 |
| RulingEnforcementAgent | 5 min | ACTIVE | 2026-04-03 |
| PoAdAnchorAgent | 60 sec | ACTIVE | 2026-04-03 |
| SeparationRatioMonitorAgent (#15) | 300 sec | MONITORING | 2026-04-03 |
| TournamentActivationChainAgent (#16) | N/A (manual) | STANDBY | — |
| CalibrationIntelligenceAgent | 30 min | EVENT-DRIVEN | — |
| Agent #17 ControllerHardwareIntelligenceAgent | — | DESIGN ONLY Phase 137+ | — |
| Agent #18 AgentCalibrationIntegrityMonitor (ACIM) | 15 min | ACTIVE | Phase 148 LIVE |

### SQLite Schema

**Database**: bridge/vapi.db
**Tables**: 131 total

Key tables:
- records (PoAC chain)
- devices (registration)
- pitl_session_proofs (ZK sessions)
- pitl_records (L2-L5 classifications)
- l4_threshold_tracks (per-battery calibration)
- l4_calibration_log (staleness tracking)
- separation_ratio_snapshots (ratio versioning)
- ioswarm_node_registry (live nodes)
- agent_rulings (AIL decisions)
- ruling_streaks (enforcement)

### Claude Code Guidance

When working with bridge code:
- Check test counts match this table
- Reference specific table schemas when proposing SQL changes
- Background agents have specific cycle times — respect them
- **Red flag**: Proposing schema changes without migration in schema_versions

---

## 4. PITL Threshold Tracks

### Current Calibration Status

| Battery Type | N Sessions | Anomaly Threshold | Continuity Threshold | Source | Status |
|--------------|------------|-------------------|----------------------|--------|--------|
| USB full | 177 | Tikhonov (pending) | Tikhonov (pending) | Full covariance | PHASE 129 PENDING |
| USB diagonal | 177 | 7.009 | 5.367 | Phase 46 | ACTIVE |
| BT 250Hz | 0 | 7.009* | 5.367* | Mirrors USB | **WRONG — UNCALIBRATED** |
| Touchpad | [subset] | — | — | USB corpus | Included in 177 |
| Trigger | [subset] | — | — | USB corpus | Included in 177 |
| Resting grip | [subset] | — | — | USB corpus | Included in 177 |

*BT thresholds mirror USB but are structurally incorrect due to 250Hz sampling.

### Feature Dimensions

- **Current live**: 13 dimensions (Phase 121 touchpad_spatial_entropy added)
- **Last calibrated**: 12 dimensions (Phase 46)
- **Staleness status**: ⚠️ STALE — live_feature_dim (13) ≠ calibration_feature_dim (12)

### Claude Code Guidance

When working with thresholds:
- Acknowledge USB/BT structural difference
- Full covariance (Tikhonov) applicable only to USB N=177 corpus
- BT requires N≥50 separate calibration
- **Red flag**: Applying USB thresholds to BT sessions, ignoring staleness

---

## 5. Tournament Readiness Score

### 6-Signal Formula (Phase 128)

```
score = 0.30 × separation_score +
        0.20 × l4_score +
        0.15 × dual_gate_score +
        0.15 × epoch_score +
        0.10 × ioswarm_score +
        0.10 × dry_run_score
```

**Ready threshold**: score ≥ 0.90

### Current Status (Estimated)

| Signal | Value | Status | Blocker? |
|--------|-------|--------|----------|
| separation_score | **1.261** touchpad_corners N=11 (Phase 143 diagonal+LOO) | ✅ ABOVE GATE | N=11 thin — needs ≥10/player |
| l4_score | [From l4_calibration_log] | stale (dim 12 vs 13) | — |
| dual_gate_score | [From vhp_dual_gate_log] | TBD | — |
| epoch_score | [From epoch_window_analytics] | TBD | — |
| ioswarm_score | [From ioswarm_node_registry] | TBD | — |
| dry_run_score | True (N<100 live adjudications) | ⚠️ | — |

**Overall**: CONDITIONALLY UNBLOCKED on touchpad_corners (ratio=1.261 > 1.0). Full corpus pooled=0.417 still BLOCKER. Touchpad_corners N=11 legally thin — target ≥10 sessions/player for defensible evidence.

### State Flags (Current Configuration)

These flags indicate current system capabilities. They change as phases complete, but each value has specific meaning.

### Current Values (Phase 149)

| Flag | Value | Meaning | Phase |
|------|-------|---------|-------|
| GSR_ENABLED | false | Galvanic skin response uncalibrated, advisory only | 99B |
| L6B_ENABLED | false | L6b neuromuscular reflex uncalibrated | 63 |
| dry_run | true | Enforcement simulation mode (no real penalties) | 97 |
| bt_transport_enabled | false | Bluetooth 250Hz transport disabled | 120 |
| ioswarm_enabled | false | Live ioSwarm nodes not registered | 109A |
| l4_battery_threshold_enabled | false | Per-battery routing not active | 126 |
| confidence_multiplier_enabled | false | bt_strat_ratio multiplier disabled | 122 |
| mcp_server_enabled | false | FastAPI MCP sub-app disabled (Phase 148 infrastructure) | 148 |
| multi_controller_enabled | false | Agent #17 (ControllerHardwareIntelligenceAgent) DESIGN ONLY Phase 137+ | 137+ |

### Controller Registry Status

| Controller | PHCI Certified | N Sessions | Tier Eligible | Status |
|------------|---------------|------------|---------------|--------|
| Sony DualShock Edge | ✅ Yes | 177 USB | Attested + Standard | ✅ ACTIVE |
| Microsoft Xbox Series X | ⏳ Pending | 0 | Standard only | ❌ PENDING |
| Nintendo Switch Pro | ⏳ Pending | 0 | Standard only | ❌ PENDING |
| Sony DualShock 4 | ✅ Yes | Subset | Standard only | ⏳ PARTIAL |

**Target**: 4+ controller profiles by Phase 140

### Claude Code Guidance

When assessing tournament readiness:
- Check all 6 signals before declaring ready
- Check all state flags before proposing on-chain operations
- separation_ratio > 1.0 is the hard gate
- Reference specific tables for signal values
- **Red flag**: Declaring ready with separation < 1.0, ignoring ioswarm/dry_run flags

---

## 6. Hardware Calibration Corpus

### Session Statistics

| Metric | Value | Status |
|--------|-------|--------|
| Total sessions | 177 | ✅ CALIBRATED |
| USB sessions | 177 | ✅ |
| BT sessions | 0 | ❌ REQUIRED |
| Unique players | 3 | ✅ (P1, P2, P3) |
| Player P1 sessions | [count] | ✅ |
| Player P2 sessions | [count] | ✅ |
| Player P3 sessions | [count] | ✅ |

### Device Configuration

- **Primary Device**: Sony DualShock Edge CFI-ZCP1
- **Transport**: USB-C (1000 Hz)
- **Platform**: Windows 11
- **HID Interface**: 3 (hidapi: VID=0x054C, PID=0x0DF2)

### Breakthrough Results (Phases 137–143)

**Phase 143 result (CURRENT BEST — 2026-04-02)**:
- Separation ratio: **1.261** (diagonal + proper LOO, N=11 touchpad_corners, 3-player)
- Classification: 63.6% (7/11, proper LOO) — honest estimate
- Inter-player pairs: P1 vs P2=2.868, P1 vs P3=3.276, P2 vs P3=2.243
- Covariance: diagonal auto-fallback (N/p=1.375 < 3.0 threshold)
- Status: ABOVE 1.0 gate — but N=11 legally thin; target ≥10 sessions/player

**Phase 138 result (P4→P3 merge, superseded by Phase 143)**:
- Ratio 1.552 (full Tikhonov) — P1/P3 distance 0.127 was covariance noise artifact; diagonal gives 3.276

**Full corpus pooled (N=127, 2026-03-29)**: 0.417 — plateau regime confirmed; free-form gameplay cannot reach >1.0.

### Claude Code Guidance

When working with calibration:
- Corpus is USB-only — BT is separate workstream
- Tikhonov applicable only when N>150 (satisfied)
- 3-player diversity enables inter-person separation
- **Red flag**: Assuming BT calibrated, ignoring N=0 status

---

## 7. Whitepaper & Documentation

### Publication Status

- **DOI**: 10.5281/zenodo.18966169
- **Version**: v3 (Phase 136)
- **Sections**: 1-12 complete
- **§9.5**: Professional adversarial data (Phase 48) — ADDED

### Key Deliverables

| Document | Status | Location |
|----------|--------|----------|
| Whitepaper | Published | paper/vapi-whitepaper.md |
| Architecture | Current | docs/architecture.md |
| Bridge Guide | Current | bridge/dualshock-bridge-guide.md |
| PITL Guide | Current | bridge/physical-input-trust-guide.md |
| Hardware Guide | Current | docs/hardware-testing-guide.md |

### Claude Code Guidance

When proposing documentation changes:
- Whitepaper sections must match code reality
- DOI references must be accurate
- Test counts in whitepaper must match actual counts
- **Red flag**: Test count inflation, undocumented features

---

## 8. Open Gaps & Blockers

### TOURNAMENT BLOCKERS (Non-Negotiable)

| Gap | Current | Required | Phase | Status |
|-----|---------|----------|-------|--------|
| Separation ratio (touchpad_corners) | **1.261** N=11 | >1.0 defensible (N≥10/player) | 143 | **CONDITIONALLY MET** |
| Separation ratio (full corpus pooled) | 0.417 N=127 | >1.0 | 129 | **OPEN** |
| Wallet funding | ~0.35 IOTX | ~0.40 IOTX | 130B | **OPEN** |

### Calibration Gaps (Progressive)

| Gap | Current | Required | Phase | Status |
|-----|---------|----------|-------|--------|
| BT calibration | 0 sessions | 50 sessions | 120 | OPEN |
| GSR calibration | false | N≥20 sessions | 99B | OPEN |
| L6b calibration | false | N≥20 sessions | 63 | OPEN |

### Claude Code Guidance

When prioritizing work:
- Tournament blockers take precedence over progressive gaps
- Separation ratio breakthrough unblocks everything
- BT calibration is valuable but not tournament-blocking
- **Red flag**: Working on BT when separation is the critical path

---

**Document Version**: 1.2 (Phase 156)
**Last Updated**: 2026-04-04
**Update Trigger**: Phase 156 session — VAPI_AGENTS.md synced (agents #19-20 added); VAPI_SKILLS.md Skill 14 added; vapi.md 20-phase drift corrected; AutoResearch cycle 4 score=1.000
**Update Method**: Manual edit, not AutoResearch (ground truth file)
**AutoResearch Last Run**: 2026-04-04 (cycle 4, score=1.000; W1 enrollment_count_gate + W2 PoFC filed)
