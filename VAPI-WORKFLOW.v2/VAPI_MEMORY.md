# VAPI MEMORY — For Claude Code Context

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

**Your Role**: When reading this file, you are the institutional memory of VAPI. You must remember what worked, what failed, and why. Never repeat failed experiments. Always build on validated patterns. Add your own learnings after each session.

> **INSTRUCTION TO CLAUDE CODE**: This file is the compounding learning log of VAPI development.
> When reading this file, you must:
> 1. Read recent entries (last 5-10) before proposing changes
> 2. Avoid repeating failed experiments (marked FAILED below)
> 3. Build on successful patterns (marked PATTERN)
> 4. Add new entries after significant discoveries or failures
> 5. Append-only — never delete historical entries

---

## 1. Session Outcomes (Chronological, Newest First)

### 2026-03-29: Phase 136 COMPLETE — DualSense Audio Passthrough Router [DONE]

**What was done**:
- Created `bridge/vapi_bridge/audio_router.py` — Windows Core Audio COM vtable dispatch
- `IPolicyConfigVista` CLSID `{870AF99C-...}` vtable[13]=`SetDefaultEndpoint` for ERole 0/1/2
- `IMMDeviceEnumerator` vtable[4]=`GetDefaultAudioEndpoint` to detect current default
- `AudioDevice` dataclass with `is_dualsense` + `is_system_audio` classification from registry
- `AudioRouter(preferred)`: `ensure_game_audio()` + `restore()` — pure ctypes, no external deps
- Config: `audio_passthrough_enabled=True` + `audio_device_preference="system"`
- Wired into `dualshock_integration.py`: after boot record + `_shutdown_cleanup()` restore
- 18 tests: Bridge 1716→1734

**Results**:
- Game audio now auto-restores to Realtek when DualSense Edge connects USB
- Windows registry enumeration reads HKLM MMDevices/Audio/Render endpoints
- Graceful no-op on non-Windows (CI-safe); all errors non-fatal (debug logged)

**What we learned**:
- Windows COM vtable dispatch via ctypes is the correct approach (no external deps)
- IPolicyConfigVista CLSID {870AF99C-...} is stable Vista → Windows 11
- DualSense audio endpoint identified by `is_dualsense` keyword matching on driver_name/usb_id
- restore() on shutdown prevents permanent audio routing change after bridge exits

**CORRECTION**: ControllerHardwareIntelligenceAgent (Agent #17) is DESIGN ONLY — no code written.
Phase 136 = Audio Router (code complete). Agent #17 is a candidate for Phase 137+.

**Pattern identified** [PATTERN-011]:
Controller capability mapping must:
1. Preserve 228-byte PoAC format (controller-agnostic)
2. Adjust PITL weights based on available layers
3. Enforce tier eligibility (Attested requires L6 full)
4. Use per-controller threshold tracks (no cross-contamination)
5. Maintain USB/BT separation (250Hz ≠ 1000Hz)

**Next Steps**:
- N≥50 calibration sessions for Xbox Series X
- N≥50 calibration sessions for Switch Pro
- N≥50 calibration sessions for DualShock 4 (dedicated)
- PHCI certification API for hardware partners

---

### 2026-03-27: Phase 135 Complete — TournamentActivationChainAgent [SUCCESS]

**What was done**:
- Added TournamentActivationChainAgent (agent #16)
- Implemented auto_activate_on_breakthrough=False (hardcoded safety)
- Created tournament_activation_chain_log table with 7-key schema
- Added Tool #104: get_tournament_activation_chain

**Results**:
- Bridge: 1,716 pytest passing
- SDK: 233 tests passing
- Hardhat: 462 tests passing
- All gates verified before activation (separation_ok, l4_ok, gate_ok, cert_ok, audit_ok, dual_gate_warned, epoch_window_warned, ioswarm_warned)

**What we learned**:
- Activation features need explicit operator override path
- auto_activate_on_breakthrough=False prevents accidental live mode
- Tournament gates require 8-condition AND check
- Persistent activation_state in SQLite prevents double-activation

**Pattern identified** [PATTERN-001]:
Every "activation" or "enforcement" feature must have:
1. dry_run gate (default True)
2. Manual operator override path
3. Persistent state tracking
4. Idempotent operations (safe to retry)

---

### 2026-03-25: Phase 134 Complete — L4 Recalibration Pipeline [SUCCESS]

**What was done**:
- Created scripts/l4_recalibration_pipeline.py (terminal UX)
- Implemented 6-step pipeline: backup → export → analyze → calibrate → validate → activate
- Added l4_recalibration_log table for audit trail
- Integrated with ThresholdCalibratorAgent

**Results**:
- +9 bridge tests (1,716 total)
- USB threshold track updated with N=177
- Terminal workflow validated (web dashboard insufficient)

**What we learned**:
- Calibration workflows need BOTH headless (CI) and terminal (operator) modes
- 6-step pipeline prevents operator error
- Backup step is non-negotiable (rollback capability)
- Validation step catches bounds violations before activation

**Pattern identified** [PATTERN-002]:
Calibration workflows must have:
1. Backup before change (sqlite .backup)
2. Export for external analysis
3. min() enforcement (thresholds only tighten)
4. Validation before activation
5. Idempotent activation (safe retry)

---

### 2026-03-22: Phase 131 Complete — IoSwarm Live Node Foundation [SUCCESS]

**What was done**:
- Created ioswarm_node_registry table (node_url, staker_address, active, last_seen_ts)
- Implemented IoSwarmLiveNodeClient with emulator fallback
- Added GET /agent/ioswarm-node-registry-status endpoint
- Integrated with IoSwarmRenewalCoordinator, IoSwarmAdjudicationCoordinator, IoSwarmVHPMintCoordinator

**Results**:
- Bridge: 1,669 tests (+8 from Phase 130B)
- SDK: 217 tests (+4)
- Hardhat: 460 tests (+6)
- Emulator mode provides zero-behavior-change fallback

**What we learned**:
- Live node infrastructure must have emulator fallback
- Staker address per node enables VAPISwarmOperatorGate validation
- Node timeout (default 30s) prevents indefinite blocking
- Registry status endpoint enables operator visibility

**Pattern identified** [PATTERN-003]:
ioSwarm infrastructure must:
1. Support live nodes AND emulator fallback
2. Validate staker addresses for decentralization
3. Provide registry visibility to operators
4. Fail-open (emulator) when live nodes unavailable

---

### 2026-03-20: Phase 129 Hypothesis — Tikhonov Breakthrough [PENDING VERIFICATION]

**What was proposed**:
- Run analyze_interperson_separation.py --full-covariance on N=177 corpus
- Apply Phase 129 Tikhonov regularization to full covariance matrix
- Hypothesis: Corrected ratio > 0.60 or potentially > 1.0

**Current status**:
- N=177 corpus available (USB, 3 players)
- Tikhonov correction applicable (N>150 threshold met)
- Diagonal approximation: 0.474
- Full covariance estimate: UNKNOWN (pending execution)

**What we expect to learn**:
- Whether measurement imprecision (not signal weakness) suppressed ratio
- If full covariance reveals breakthrough already achieved
- Whether additional hardware sessions needed or just better analysis

**Pattern identified** [PATTERN-004]:
Large-N corpus analysis (N>150) should:
1. Prefer full covariance over diagonal approximation
2. Apply Tikhonov regularization for numerical stability
3. Compare estimates: diagonal vs full vs regularized
4. Update confidence intervals based on method precision

**Action required**: Run --full-covariance analysis when approved.

---

### 2026-03-18: Phase 128 Complete — Protocol Intelligence Dashboard [SUCCESS]

**What was done**:
- Created TournamentReadinessScore with 6-signal formula
- Implemented GET /agent/tournament-readiness-score endpoint
- Added separation_score = min(1.0, pooled_ratio) cap
- Integrated all 6 signals: separation, l4, dual_gate, epoch, ioswarm, dry_run

**Results**:
- Bridge: 1,644 tests (+8)
- SDK: 205 tests (+4)
- Score computation: 0.30/0.20/0.15/0.15/0.10/0.10 weights

**What we learned**:
- Readiness score prevents overconfidence before separation > 1.0
- 6-signal formula balances technical and operational readiness
- Score as oracle input enables automated monitoring
- capping separation_score at 1.0 prevents premature "ready" declaration

**Pattern identified** [PATTERN-005]:
Readiness assessment must:
1. Weight separation ratio highest (30%)
2. Cap score at current reality (no optimistic projection)
3. Include operational signals (ioswarm, dry_run)
4. Provide per-signal breakdown for blocker identification

---

### 2026-03-15: Phase 127 Complete — Tournament Pre-Launch Validation [SUCCESS]

**What was done**:
- Created tournament_preflight_log table (8 conditions)
- Implemented POST /agent/run-tournament-preflight endpoint
- Added preflight gate to POST /agent/commit-activation
- Overall_pass=False now blocks commit

**Results**:
- Bridge: 1,636 tests (+9)
- Preflight runs all 8 conditions before activation
- Audit trail for tournament launch authorization

**What we learned**:
- Pre-flight gate prevents activation with known blockers
- Audit trail provides legal defensibility for launch decisions
- 8 conditions must pass before operator can commit
- separation_ok and l4_ok are P0 (blocking) conditions

**Pattern identified** [PATTERN-006]:
Launch authorization must:
1. Run preflight checks (all conditions)
2. Block on P0 conditions (separation, l4)
3. Log audit trail (operator, timestamp, conditions)
4. Require explicit operator override to bypass (discouraged)

---

## 2. Calibration Patterns Discovered

### [PATTERN-007] Resting Grip Normalization (Phase 121)

**Discovery**: Touchpad-dominant sessions show inflated bt_strat_ratio due to baseline drift.

**Mechanism**: Resting grip position (no touch) establishes per-player baseline. Subtract before Mahalanobis computation.

**Applies to**: All touchpad sessions in corpus (P1, P2, P3)

**Implementation**: analyze_interperson_separation.py --resting-grip-normalization

**Status**: ACTIVE in Phase 121+ analysis

---

### [PATTERN-008] Battery Heterogeneity Risk (W1-003, Phase 124)

**Discovery**: USB thresholds (1000 Hz) applied to BT sessions (250 Hz) cause false positives.

**Mechanism**: 4× sampling difference creates different variance profiles. Same human behavior produces different Mahalanobis scores.

**Applies to**: Any multi-transport tournament (USB + BT)

**Solution**: Per-battery threshold tracks (l4_threshold_tracks table)

**Status**: MIGRATING from global thresholds to per-battery (Phase 125-126)

---

### [PATTERN-009] L4 Staleness Detection (Phase 123)

**Discovery**: Feature dimension drift (12→13) invalidates thresholds silently.

**Mechanism**: New feature (touchpad_spatial_entropy) added in Phase 121. Old thresholds applied to 13-dim space = 12-dim threshold on partial data.

**Detection**: live_feature_dim != calibration_feature_dim in l4_calibration_log

**Applies to**: Any feature addition after threshold calibration

**Solution**: Staleness flag + automatic recalibration suggestion

**Status**: DETECTED in N=177 corpus (stale=True currently)

---

### [PATTERN-010] Confidence Multiplier Safety (Phase 122)

**Discovery**: bt_strat_ratio as VHP confidence multiplier penalizes non-touchpad sessions.

**Mechanism**: No-touchpad sessions have bt_strat_ratio=0.0, reducing confidence_score to 0.0.

**Solution**: confidence_multiplier_enabled=False (default), confidence_multiplier_floor=0.0

**Applies to**: VHP minting with battery diversity

**Status**: DISABLED by default, per-battery lookup candidate for Phase 124+

---

## 3. Failed Experiments (What Not To Do Again)

### [FAILED-001] Spectral Entropy for Separation Ratio (Phase 46)

**Attempt**: Use accel_magnitude_spectral_entropy to improve inter-person separation.

**Hypothesis**: Spectral features would differentiate players better than kinematic features.

**Result**: 0 improvement — feature is bot-vs-human, not person-vs-person.

**Why it failed**: 
- Spectral entropy detects injection (software vs hardware signal patterns)
- Inter-person separation requires biometric differentiation (tremor, rhythm)
- Different problem domains entirely

**Lesson**: "More features" ≠ "better separation"; features must match the discrimination target.

**Current status**: accel_magnitude_spectral_entropy active for bot detection (index 9), not separation.

---

### [FAILED-002] Early BT Transport Enable (Phase 120)

**Attempt**: Enable bt_transport_enabled=True with USB-calibrated thresholds.

**Hypothesis**: BT and USB similar enough to share thresholds.

**Result**: L4 false positives at 250 Hz — 4× fewer samples = different variance profile.

**Why it failed**:
- Mahalanobis distance sensitive to sample count per window
- Human micro-tremor (8-12 Hz) completes more cycles per window at BT rates
- Gyro_std variance artificially elevated at 250 Hz

**Lesson**: BT requires separate N≥50 calibration; cannot inherit USB thresholds.

**Current status**: bt_transport_enabled=False default, Phase 120 infrastructure complete but disabled pending calibration.

---

### [FAILED-003] Diagonal Covariance Assumption (Phase 121-128)

**Attempt**: Use diagonal covariance (feature independence) for separation ratio with N=177.

**Hypothesis**: Features sufficiently independent for diagonal approximation.

**Result**: Ratio 0.474 — potentially under-reported due to feature correlation.

**Why it may have failed**:
- Touchpad spatial entropy correlates with stick axes during gameplay
- L2/R2 trigger resistance correlates with grip pressure
- Full covariance captures these relationships

**Lesson**: Large-N corpora (N>150) enable full covariance estimation; diagonal approximation wastes data.

**Current status**: Phase 129 Tikhonov correction pending — may reveal true ratio.

---

## 4. Preferences Established

### Threshold Management

- **Only min() tightening**: Thresholds never loosen (enforced in calibrator)
- **Per-battery routing**: USB and BT have separate tracks (Phase 126)
- **Staleness detection**: Live vs calibrated feature dimension checked (Phase 123)

### Calibration Session Selection

- **NOMINAL only for EMA**: Anomaly sessions excluded from stable track updates (prevents baseline poisoning)
- **Minimum N=50**: Statistical significance threshold for calibration
- **Recommended N=177+**: Full covariance stability (Tikhonov applicable)

### Tournament Gates

- **Manual override path**: Every gate has operator bypass (discouraged but available)
- **Idempotent operations**: Safe to retry activation, minting, etc.
- **Audit trail**: All gate decisions logged with operator, timestamp, conditions

### Feature Addition Protocol

1. Add feature to FeatureExtractor
2. Update _BIO_FEATURE_DIM
3. Set calibration_feature_dim (marks stale)
4. Run recalibration (Phase 134 pipeline)
5. Update live_feature_dim (marks fresh)

### Separation Ratio Measurement

- **Honest disclosure**: Report actual measured ratio, not target ratio
- **Method documentation**: Specify diagonal vs full covariance, N sessions, player count
- **Tikhonov applicability**: N>150 only (mathematical stability)

---

## 5. Active Hypotheses (Pending Verification)

### [HYPOTHESIS-001] Tikhonov Reveals Breakthrough

**Claim**: Full covariance Tikhonov correction on N=177 corpus reveals separation ratio > 0.60 or > 1.0.

**Evidence**:
- Diagonal approximation: 0.474
- Feature correlation suspected (resting grip, touchpad, triggers)
- N=177 satisfies large-N threshold for full covariance

**Test**: Run analyze_interperson_separation.py --full-covariance

**Expected outcomes**:
- If >1.0: Tournament readiness unblocked, whitepaper update, TGE possible
- If 0.60-1.0: Progress documented, continue calibration toward 1.0
- If <0.50: Reassess — signal may need hardware recapture (Phase 17 touchpad)

**Status**: PENDING execution approval.

---

### [HYPOTHESIS-002] Per-Battery Multiplier Viable

**Claim**: Battery-stratified confidence multiplier enables touchpad-dominant sessions without penalizing others.

**Evidence**:
- Current bt_strat_ratio penalizes no-touchpad (ratio=0.0)
- Per-battery lookup possible with l4_threshold_tracks (Phase 124)

**Test**: Enable confidence_multiplier_enabled=True with per-battery floor

**Expected outcomes**:
- If VHP minting fairness improves: Keep enabled
- If complexity exceeds benefit: Keep disabled (advisory only)

**Status**: THEORETICAL — candidate for Phase 136+.

---

## 6. Session Cadence Guidelines

Based on accumulated learning:

| Session Type | Cycles | Focus |
|--------------|--------|-------|
| Deep work day | 3-5 | Improvement cycles at start, then manual dev |
| Normal session | 1 | Single cycle, then implementation |
| Hardware/calibration | 0 | No orchestration improvement needed |
| Phase planning | 2 | Next phase coherence before coding |
| Tikhonov verification | 1 | Single focused cycle, then execution |

---

**Document Version**: 1.0 (Phase 135)
**Last Updated**: 2026-03-29
**Update Method**: Append-only, manual edit after significant sessions
**Retention**: All entries preserved indefinitely
