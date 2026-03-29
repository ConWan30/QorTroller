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

**Active Phase**: Phase 136 — DualSense Audio Passthrough Router
**Phase Start**: 2026-03-29
**Phase Status**: COMPLETE
**Next Phase**: Phase 137 (Tikhonov verification / SeparationRatioRegistry.sol / Tikhonov auto-detect)

### Phase 136 Deliverables

| Component | Status | Evidence |
|-----------|--------|----------|
| audio_router.py | ✅ LIVE | NEW: Windows Core Audio COM vtable dispatch |
| AudioDevice / AudioRouteResult / AudioRouter | ✅ LIVE | 3 new classes |
| config audio_passthrough_enabled(True) / audio_device_preference("system") | ✅ LIVE | +2 config fields |
| dualshock_integration.py | ✅ LIVE | _audio_router=None init + ensure_game_audio() + restore() |
| Bridge tests | ✅ PASS | 1,734 pytest (+18 Phase 136) |
| SDK tests | ✅ PASS | 233 tests (unchanged) |
| Hardhat tests | ✅ PASS | 462 tests (unchanged) |

### Phase 135 Deliverables (COMPLETE 2026-03-27)

| Component | Status | Evidence |
|-----------|--------|----------|
| TournamentActivationChainAgent | ✅ LIVE | agent #16, auto_activate_on_breakthrough=False |
| tournament_activation_chain_log | ✅ LIVE | 7-key GET endpoint |
| Tool #104 | ✅ LIVE | get_tournament_activation_chain |

### Claude Code Guidance

When working on VAPI:
- Check this section first to understand current system state
- Phase 136 COMPLETE — Phase 137 work requires user approval first
- Reference specific agent numbers and tool numbers from this table
- If test counts differ from this table (expected: 1734/462/233), investigate regression

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
| Bridge pytest | 1,734 | ✅ PASS | 2026-03-29 |
| SDK tests | 233 | ✅ PASS | 2026-03-29 |
| Hardhat tests | 462 | ✅ PASS | 2026-03-29 |
| Hardware tests | 37 | ⚠️ HARDWARE-ONLY | Manual |
| E2E tests | 14 | ⚠️ REQUIRES NODE | Manual |

### BridgeAgent Tools

**Available**: 104 deterministic tools (expanded from 28 original)
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
| SessionAdjudicator | 5 min | ACTIVE | 2026-03-29 |
| RulingEnforcementAgent | 5 min | ACTIVE | 2026-03-29 |
| PoAdAnchorAgent | 60 sec | ACTIVE | 2026-03-29 |
| SeparationRatioMonitorAgent (#15) | 300 sec | MONITORING | 2026-03-29 |
| TournamentActivationChainAgent (#16) | N/A (manual) | STANDBY | — |
| CalibrationIntelligenceAgent | 30 min | EVENT-DRIVEN | — |
| Agent #17 ControllerHardwareIntelligenceAgent | — | DESIGN ONLY Phase 137+ | — |

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
| separation_score | 0.474 / 1.0 required | ⚠️ LOW | **YES** |
| l4_score | [From l4_calibration_log] | TBD | — |
| dual_gate_score | [From vhp_dual_gate_log] | TBD | — |
| epoch_score | [From epoch_window_analytics] | TBD | — |
| ioswarm_score | [From ioswarm_node_registry] | TBD | — |
| dry_run_score | True (N<100?) | ⚠️ | — |

**Overall**: NOT READY (separation_ratio < 1.0 is non-negotiable)

### State Flags (Current Configuration)

These flags indicate current system capabilities. They change as phases complete, but each value has specific meaning.

### Current Values (Phase 136)

| Flag | Value | Meaning | Phase |
|------|-------|---------|-------|
| GSR_ENABLED | false | Galvanic skin response uncalibrated, advisory only | 99B |
| L6B_ENABLED | false | L6b neuromuscular reflex uncalibrated | 63 |
| dry_run | true | Enforcement simulation mode (no real penalties) | 97 |
| bt_transport_enabled | false | Bluetooth 250Hz transport disabled | 120 |
| ioswarm_enabled | false | Live ioSwarm nodes not registered | 109A |
| l4_battery_threshold_enabled | false | Per-battery routing not active | 126 |
| confidence_multiplier_enabled | false | bt_strat_ratio multiplier disabled | 122 |
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

### Breakthrough Hypothesis (Phase 129)

**Claim**: Diagonal approximation (0.474) under-reports true separation due to feature correlation. Full covariance Tikhonov correction may reveal ratio > 0.60 or even > 1.0.

**Status**: UNVERIFIED — requires `--full-covariance` run on N=177 corpus.

**Action Required**: Run Phase 129 analysis when approved.

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
| Separation ratio | 0.474 | >1.0 | 121/129 | **OPEN** |
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

**Document Version**: 1.0 (Phase 135)
**Last Updated**: 2026-03-29
**Update Trigger**: Phase 136 completion
**Update Method**: Manual edit, not AutoResearch (ground truth file)
