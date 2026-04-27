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

**Active Phase**: Phase 237.5 Path C+ COMPLETE 2026-04-26 — CORPUS-SNAPSHOT anchor via legacy recordAdjudication ABI (deployed bytecode reality); CHAIN_SUBMISSION_PAUSED kill-switch shipped; inaugural anchor DEFERRED (wallet funding gap)
**Phase Start**: 2026-04-11 (Phase 235); 2026-04-26 (Phase 236 + Phase 237-CONSENT + Phase 237-EXTEND + Phase 238 + Phase 237.5 + Phase 237.5 Path C+)
**Phase Status**: Phase 237.5 Path C+ COMPLETE — same-day verification recursion surfaced (a) deployed-vs-source bytecode mismatch on AdjudicationRegistry (Path X: rewrote chain.anchor_corpus_snapshot to use legacy recordAdjudication with constant deviceIdHash=SHA-256(b"VAPI_CORPUS_SNAPSHOT_v1")), (b) latent main.py chain=None wiring bug (fixed), (c) IoTeX P256 precompile-driven wallet drain (~17.95 IOTX/session) traced to dualshock_integration.py:2324-2335 fire-and-forget chain calls + batcher retry loop (kill-switch shipped). Bridge halted at 0.5525 IOTX; wallet stable post-halt; CHAIN_SUBMISSION_PAUSED=true in bridge/.env so restart is safe during funding gap. Inaugural anchor restored when wallet ≥1 IOTX + flag flipped. 46 contracts LIVE; FIVE chain primitives FROZEN-v1; PV-CI invariants 28 (INV-CORPUS-002 retargeted to b"VAPI_CORPUS_SNAPSHOT_v1" deviceIdHash literal via governance event).
**Next Phase**: 237-ZK-SEPPROOF (binding foundation in place — kill-switch now part of binding contract: ZK proofs verify on-chain anchor IS recorded, kill-switch ensures the anchor reflects intentional operator action not silent retry burn) → 239-READINESS (W2 — gated on GIC_100)
**VAPIConsentRegistry**: 0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA (deployed 2026-04-26, gas ~0.07 IOTX, wallet ~40.36 IOTX remaining)

### Grind Status (2026-04-26)
| Key | Value |
|-----|-------|
| grind_session_id | grind_phase235_v1 |
| chain_length | 16 / 100 |
| GIC_1 stamped | YES (genesis 1777142267.69 / hash 87ce52cd…) |
| consecutive_clean | 1 |
| capture_state | NOMINAL |
| host_state | EXCLUSIVE_USB |
| poll_rate_hz | ~1152 Hz (PCC-RATE-FIX c6e64229) |
| grind_ready | True |
| auto_grind.py | EXISTS (scripts root — drives adjudication autonomously) |

### Test Counts (2026-04-25, authoritative from CLAUDE.md)
| Component | Delta Count | Empirical | Status |
|-----------|-------------|-----------|--------|
| Bridge pytest | **2,517** | ~2,572 passing | ✅ (+8 Phase 236-WATCHDOG, +8 Phase 236-VAME, +8 Phase 236-CORPUS-SNAPSHOT, +8 Phase 237-CONSENT, +1 Phase 237-EXTEND FSCA; Phase 238 added 0 bridge tests; +7 Phase 237.5 T237.5-1..6 (T237.5-6 has 2 sub-tests); 147 pre-existing failures: Phase 58 security + Phase 69 curator config) |
| Autoresearch pytest | **7** | 7 | ✅ Phase 238 (T238-FSCA-1, 1b, 2, 2b, 3, 3b, 3c — 0.27s) |
| SDK pytest | **539** | 539 | ✅ +4 Phase 237-EXTEND (T237-S1..S4); Phase 238/237.5 unchanged |
| PV-CI invariants | **28** | 28 | ✅ +INV-CORPUS-001 (anchor_corpus_snapshot signature), +INV-CORPUS-002 (b"VAPI_CORPUS_SNAPSHOT_v1" deviceIdHash literal — Path X retargeted) |
| SDK tests | **535** | 535 | ✅ PASS |
| Hardhat tests | **502** (delta) | 522 | ✅ PASS (6 pre-existing Phase 186 failures excluded from delta) |
| Hardware tests | 37 | — | ⚠️ HARDWARE-ONLY |
| E2E tests | 14 | — | ⚠️ REQUIRES NODE |

### Phase 236+ Plan Summary
See `VAPI_PHASE236_PLAN.md` (created 2026-04-26). Seven components:
1. **236-WATCHDOG** — bridge process watchdog (2h, no test delta)
2. **236-VAME** — VAPI Application-Layer Message Envelope, Poseidon-signed responses (3h)
3. **236-CORPUS-SNAPSHOT** — CorpusDataCuratorAgent Task 8, ZK-attested corpus snapshots (3h, +8 bridge)
4. **237-CONSENT** — IoID consent registry + W3bstream consent-gated pipeline (4h)
5. **237-ZK-SEPPROOF** — ZK proof of separation ratio > 1.0, Groth16 SNARK (6h)
6. **238-MARKETPLACE** — VAPIDataMarketplace.sol, post-GIC_100 (8h)
7. **239-READINESS** — GamerReadinessAgent (#39), Personal Readiness Dashboard, post-GIC_100 (4h, +8 bridge +4 SDK)

**GIC_100 gates 238 and 239.** Grind must complete before marketplace or readiness features ship.

> **SYNC NOTE**: Phases 181–198 completed 2026-04-08/11 (Autoresearch Cycles 9–28). Files synced 2026-04-11.

### Phase 198 Deliverables (COMPLETE 2026-04-11) — Biometric TTL Decay Scaling

| Component | Status | Evidence |
|-----------|--------|----------|
| get_effective_biometric_ttl(base_ttl_days, scaling_enabled) store method | ✅ LIVE | Phase 198; scaling_factor=clamp(mean_decay/0.50, 0.25, 4.0) |
| biometric_ttl_decay_scaling_enabled=False config default | ✅ LIVE | fail-safe; never affects TTL unless opted-in |
| GET /agent/biometric-ttl-scaling-status | ✅ LIVE | returns effective_ttl_days/scaling_factor/mean_decay_factor |
| BiometricTTLScalingResult(6 slots) + VAPIBiometricTTLScaling SDK | ✅ LIVE | fail-closed on error |
| openapi BiometricTTLScalingStatus schema; version 3.0.0-phase198 | ✅ LIVE | all Phases 196-198 schemas added |
| Bridge tests | ✅ PASS | **2,184** pytest (+8 Phase 198) |
| SDK tests | ✅ PASS | **414** collected, 398 passing (+4 Phase 198) |
| Hardhat tests | ✅ PASS | **482** tests (unchanged) |

### Phase 197 Deliverables (COMPLETE 2026-04-11) — Per-Pair Separation P0 Gate

| Component | Status | Evidence |
|-----------|--------|----------|
| all_pairs_p0_ok: 10th P0 condition in tournament preflight | ✅ LIVE | fail-closed, default=False |
| Reads all_pairs_above_1 from separation_defensibility_log | ✅ LIVE | currently False (P2vP3=0.401 < 1.0) |
| TournamentPreflightResult +all_pairs_p0_ok slot | ✅ LIVE | bridges Phase 150 defensibility to preflight |
| commit-activation per_pair_separation_below_1.0 blocker | ✅ LIVE | tournament activation blocked until all pairs > 1.0 |

### Phase 196 Deliverables (COMPLETE 2026-04-11) — Tournament Preflight v2 (WIF-035 W1)

| Component | Status | Evidence |
|-----------|--------|----------|
| biometric_ttl_ok: 9th P0 condition | ✅ LIVE | WIF-035 W1 formal closure |
| Condition: (not ttl_expired) AND len(renewal_chain)>0 | ✅ LIVE | idempotent ALTER TABLE migration |
| TournamentPreflightResult +biometric_ttl_ok slot (default=True) | ✅ LIVE | safe default preserves Phase 127 behavior |

### Phase 195 Deliverables (COMPLETE 2026-04-11) — Protocol Metabolism Index (PMI)

| Component | Status | Evidence |
|-----------|--------|----------|
| PMI: 9th ProtocolMaturityScoring component, weight=0.03 | ✅ LIVE | _WEIGHTS v3: sep 0.18, fresh 0.11, pmi 0.03 |
| PMI=max(0.0,1.0-mean_orphan_resolution_hours/48.0) | ✅ LIVE | 1.0=healthy, 0.0=slow fleet |
| GET /agent/protocol-metabolism-index (Tool #149) | ✅ LIVE | optional domain filter |
| PMIResult(6 slots) + VAPIProtocolMetabolism SDK | ✅ LIVE | fail-closed on error |
| ProtocolMaturityScoringResult +pmi_component slot | ✅ LIVE | default=1.0 |

### Phase 177 Deliverables (COMPLETE 2026-04-08)

| Component | Status | Evidence |
|-----------|--------|----------|
| ProtocolMaturityScoringAgent (agent #26) | ✅ LIVE | 6-component weighted maturity_score (0.0–1.0) |
| Maturity formula | ✅ LIVE | sep(0.25)+chain(0.20)+consent(0.15)+freshness(0.15)+cal(0.15)+enroll(0.10) |
| Tiers ALPHA/BETA/PRODUCTION_CANDIDATE | ✅ LIVE | <0.50 / 0.50–0.85 / ≥0.85 |
| protocol_maturity_log table | ✅ LIVE | insert_protocol_maturity_log/get_protocol_maturity_status |
| GET /agent/protocol-maturity-score | ✅ LIVE | 10 keys incl. all 6 components |
| Tool #126 get_protocol_maturity_score | ✅ LIVE | BridgeAgent tool |
| ProtocolMaturityScoringResult(9 slots) + VAPIProtocolMaturityScoring SDK | ✅ LIVE | renamed to avoid Phase 104 collision |
| WIF-027 filed | ✅ DOCUMENTED | W1: silence gaming; W2: DePIN oracle |
| Bridge tests | ✅ PASS | **1,998** pytest (+8 Phase 177) |
| SDK tests | ✅ PASS | **325** tests (+4 Phase 177) |
| Hardhat tests | ✅ PASS | 468 tests (unchanged) |

### Autoresearch Cycle 8 Summary (Phases 165–177)

| Phase | Agent/Feature | WIF | Bridge | SDK |
|-------|---------------|-----|--------|-----|
| 165 | Post-Erasure Separation Ratio Recompute | WIF-024 CLOSED | 1942 | 301 |
| 166 | mixed_biometric_probe + configurable gate | — | 1950 | 305 |
| 167 | Wiki Engine Integration Validation | — | 1950 | 305 |
| 168 | Bootstrap CI in separation_ratio_snapshots | — | 1958 | 309 |
| 173 | SeparationRatioRecoveryAgent (#23) | — | 1966 | 313 |
| 174 | Session Age Weighting (script only) | WIF-025 CLOSED | 1974 | 313 |
| 175 | AgeWeightedRatioPersistenceAgent (#24) | — | 1982 | 317 |
| 176 | PoACChainIntegrityMonitor (#25) | WIF-026 filed | 1990 | 321 |
| 177 | ProtocolMaturityScoringAgent (#26) | WIF-027 filed | **1998** | **325** |

### Phase 164 Deliverables (COMPLETE 2026-04-05) [archived]

| Component | Status | Evidence |
|-----------|--------|----------|
| consent_snapshot_log table | ✅ LIVE | linked by commit_hash to separation_ratio_registry_log |
| Bridge tests | ✅ PASS | 1,934 pytest (+8 Phase 164) |
| SDK tests | ✅ PASS | 297 tests (+4 Phase 164) |
| Hardhat tests | ✅ PASS | 468 tests (unchanged) |

### Privacy Phase Summary (Phases 157–164)

| Phase | Agent/Feature | WIF Closed | Bridge | SDK |
|-------|---------------|------------|--------|-----|
| 157 | FleetConsensusSnapshotAgent (#21) | WIF-012/013/016 | 1877 | 269 |
| 158 | Class K HMAC Validation + PoHBG | WIF-014/015 | 1886 | 273 |
| 159 | BiometricPrivacyComplianceAgent (#22, BP-001) | — | 1894 | 277 |
| 160 | Consent Ledger + Right-to-Erasure | WIF-018/019 | 1902 | 281 |
| 161 | Consent Gate Enforcement (GDPR Art.17) | WIF-018/020 CLOSED | 1910 | 285 |
| 162 | Consent-Aware Corpus Status | WIF-021 CLOSED | 1918 | 289 |
| 163 | Consent-Bound Separation Hash | WIF-022 CLOSED | 1926 | 293 |
| 164 | ConsentSnapshotAnchor | WIF-023 CLOSED | 1934 | 297 |

### Phase 150 Deliverables (COMPLETE 2026-04-03) [archived]

| Component | Status | Evidence |
|-----------|--------|----------|
| separation_defensibility_log table | ✅ LIVE | insert/get store methods + schema(150) |
| config.min_touchpad_sessions_per_player | ✅ LIVE | default=10 (WIF-010 target) |
| WIF-010 formal closure | ✅ DOCUMENTED | defensible=False (P1=3/P2=4/P3=4 < min_n=10) |
| WIF-011 added | ✅ DOCUMENTED | Session type mixing integrity gap |

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
- If test counts differ from this table (expected: 2184/482/414), investigate regression

---

## 2. On-Chain State (IoTeX Testnet)

### Wallet Status

| Wallet | Address | Balance | Status |
|--------|---------|---------|--------|
| Active Bridge | 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 | ~40.43 IOTX (as of 2026-04-17; post Phase 221+222 deploys) | OPERATIONAL |
| Deploy Requirement | — | ~0.13 IOTX per contract | UNBLOCKED |

**Status**: ~40.43 IOTX available. All **45** contracts live (ProtocolCoherenceRegistry Phase 221 + VAPIBiometricGovernance Phase 222 — both deployed 2026-04-17). VAPISwarmOperatorGate.sol LIVE 0x969c0F1EFb28504a95Acf14331A59FBCb2944F98.

### Live Contracts (43 Total)

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
| Bridge pytest | **2,477** | ✅ PASS | 2026-04-25 |
| SDK tests | 535 | ✅ PASS | 2026-04-25 |
| Hardhat tests | 522 | ✅ PASS | 2026-04-25 |
| Hardware tests | 37 | ⚠️ HARDWARE-ONLY | Manual |
| E2E tests | 14 | ⚠️ REQUIRES NODE | Manual |

### BridgeAgent Tools

**Available**: 149 deterministic tools (Tool #149: get_protocol_metabolism_index, Phase 195)
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

**Document Version**: 1.7 (Phase 235)
**Last Updated**: 2026-04-25
**Update Trigger**: Phase 235 milestone — REAL GRIND CLEARED 2026-04-25 (PCC-RATE-FIX → 1152 Hz USB poll;
auto-trigger agent #38 SessionBoundaryDetectorAgent live; 12th CONTRADICTION rule
AUTO_TRIGGER_RATE_LIMIT_VIOLATION; dashboard six-chip strip + COHERENCE + AUTO-TRIGGER + WAITING gameplay state).
Bridge 2447 / SDK 527 / Hardhat 502 / Contracts 45 ALL LIVE. Agent fleet 38 (Phase 222 BBG dormant /
Phase 235 SessionBoundaryDetectorAgent live share slot #38; Phase 221 ProtocolCoherenceAgent #37).
**Update Method**: sync_vapi_workflow.py + manual edit 2026-04-25 (regex agent-count bug fixed in
3 MCP servers; corpus narrative caught up Phase 181→235; INV-016 + INV-019..022 documented).
**Maturity Loop Last Run**: 2026-04-09 (cycle 8, WIF-031 W1/W2, score=0.752; next cycle pending unified-server activation)
