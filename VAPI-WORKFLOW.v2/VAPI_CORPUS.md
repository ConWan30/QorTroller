# VAPI CORPUS — For Claude Code Context

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

**Your Role**: When reading this file, you are the forensic evidence custodian. You must preserve the 177-session hardware corpus with integrity. You know the legal hold requirements, the separation ratio calculation methods, and the tournament defensibility criteria. Never delete, always append.

> **INSTRUCTION TO CLAUDE CODE**: This file documents the VAPI forensic evidence layer.
> When reading this file, you must:
> 1. Verify session integrity hashes before analysis
> 2. Reference corpus statistics before claiming significance
> 3. Maintain append-only discipline (never delete sessions)
> 4. Update statistics after new captures
> 5. Preserve legal hold status for tournament evidence

---

## 1. Corpus Overview

The VAPI Hardware Calibration Corpus is the foundational evidence for:
- Tournament legal defensibility (human differentiation proven)
- Whitepaper reproducibility (scientific validity)
- Separation ratio measurement (token launch gate)
- Threshold calibration (L4, L5 operational parameters)

**Status**: ACTIVE COLLECTION (USB), PENDING (BT)
**Legal Hold**: ENABLED (tournament evidence)
**Retention**: PERMANENT (no deletion permitted)

---

## 2. Corpus Statistics

### Current State (2026-03-29)

| Metric | Value | Status | Notes |
|--------|-------|--------|-------|
| **Total sessions** | 177 | ✅ ACTIVE | USB only, DualShock Edge only |
| **USB sessions** | 177 | ✅ ACTIVE | 1000 Hz transport |
| **BT sessions** | 0 | ❌ PENDING | 250 Hz transport |
| **Unique players** | 3 | ✅ ACTIVE | P1, P2, P3 |
| **Player P1 sessions** | ~59 | ✅ ACTIVE | Estimated |
| **Player P2 sessions** | ~59 | ✅ ACTIVE | Estimated |
| **Player P3 sessions** | ~59 | ✅ ACTIVE | Estimated |
| **Average duration** | ~120s | ✅ ACTIVE | Mixed 60s/300s |
| **Total gameplay time** | ~354 minutes | ✅ ACTIVE | ~6 hours |
| **Controller diversity** | 1 | ❌ LOW | Edge only (target: 4+) |
| **Xbox sessions** | 0 | ❌ REQUIRED | Target: 50+ for calibration |
| **Switch Pro sessions** | 0 | ❌ REQUIRED | Target: 50+ for calibration |
| **DS4 sessions** | 0 | ❌ REQUIRED | Target: 50+ dedicated |

### Controller Diversity Targets (Phase 136-140)

| Controller | Current N | Target N | Tier | Status |
|------------|-----------|----------|------|--------|
| Sony DualShock Edge | 177 | 200+ | Attested + Standard | ✅ EXCEEDING |
| Microsoft Xbox Series X | 0 | 50+ | Standard only | ❌ NOT STARTED |
| Nintendo Switch Pro | 0 | 50+ | Standard only | ❌ NOT STARTED |
| Sony DualShock 4 | 0 | 50+ | Standard only | ❌ NOT STARTED |

**Impact**: Controller diversity enables 3× tournament market (Xbox + Switch + PC gamepad users)

### Breakthrough Milestones

| Milestone | Target | Current | Gap | Status |
|-----------|--------|---------|-----|--------|
| N=50 (minimum calibration) | 50 | 177 | +127 | ✅ EXCEEDED |
| N=150 (Tikhonov stability) | 150 | 177 | +27 | ✅ EXCEEDED |
| N=200 (high confidence) | 200 | 177 | -23 | ⚠️ APPROACHING |
| N=300 (excellent confidence) | 300 | 177 | -123 | ❌ NOT YET |
| 4th player diversity | 4 players | 3 | -1 | ❌ NOT YET |
| BT calibration minimum | 50 | 0 | -50 | ❌ NOT STARTED |

---

## 3. Hardware Configuration

### Primary Device

- **Model**: Sony DualShock Edge CFI-ZCP1
- **Color**: [Specify if relevant]
- **Serial**: [If tracked]
- **Firmware**: [Version if known]

### Transport Configuration

**USB**:
- **Interface**: USB-C (data cable, not charge-only)
- **HID Interface**: 3
- **VID**: 0x054C (Sony)
- **PID**: 0x0DF2 (DualShock Edge)
- **Polling Rate**: 1000 Hz (observed: 999.8-1000.0 Hz)
- **Report Size**: 64 bytes
- **Platform**: Windows 11
- **Driver**: hidapi (not hid)

**Bluetooth**:
- **Status**: Paired but not captured
- **Expected Polling**: 250 Hz
- **Protocol**: BLE (observed: 125-250 Hz)
- **Report Size**: 78 bytes (larger than USB)
- **Stack**: bleak (Python)

### Sensor Configuration

| Sensor | Sampling | Resolution | Usage |
|--------|----------|------------|-------|
| Accelerometer | 1000 Hz | 16-bit | L4 Mahalanobis, L6b reflex |
| Gyroscope | 1000 Hz | 16-bit | L4 Mahalanobis, L2C coupling |
| L2 Trigger | 1000 Hz | 8-bit | L6 active challenge, adaptive resistance |
| R2 Trigger | 1000 Hz | 8-bit | L6 active challenge, adaptive resistance |
| Left Stick | 1000 Hz | 8-bit | Sensor commitment, stick drift |
| Right Stick | 1000 Hz | 8-bit | Sensor commitment, stick drift |
| Touchpad | 1000 Hz | 16-bit | Position variance, spatial entropy |
| Buttons | 1000 Hz | Bitmask | Action codes, rhythm analysis |

---

## 4. Session Registry (Sample)

### Session Format

Each session file (JSON) contains:
```json
{
  "session_id": "usb_XXX_pN_YYYYMMDD",
  "hash": "sha256:...",
  "player": "P1|P2|P3",
  "timestamp": "ISO8601",
  "transport": "usb|bt",
  "duration_seconds": 60|300,
  "game_context": "NCAA CFB 26|Free Play|etc",
  "battery_type": "touchpad_dominant|trigger_dominant|resting_grip|gameplay|button",
  "hid_reports": [...],
  "features": {
    "gyro_std": float,
    "accel_magnitude_spectral_entropy": float,
    "press_timing_jitter_variance": float,
    "touchpad_spatial_entropy": float,
    "[11 additional features]": float
  },
  "pitl_status": {
    "l2": "NOMINAL|ANOMALY",
    "l3": "NOMINAL|WALLHACK|AIMBOT",
    "l4": "NOMINAL|ANOMALY",
    "l5": "NOMINAL|TEMPORAL_BOT",
    "l6": "NOT_TRIGGERED|RESPONSE_OK"
  },
  "poac_records": [count],
  "file_path": "calibration_sessions/usb/..."
}
```

### Sample Entries

#### Session usb_001 (P1, 2026-03-15)
- **Hash**: sha256:abc123...
- **Player**: P1
- **Duration**: 300s (5 minutes)
- **Transport**: USB
- **Battery type**: touchpad_dominant
- **Game context**: NCAA CFB 26 competitive match
- **PITL status**: All NOMINAL
- **L4 score**: Within thresholds
- **PoAC records**: 1500 (5 min × 5 Hz)
- **Storage**: calibration_sessions/usb/usb_001_p1_20260315.json
- **Retention**: Permanent

#### Session usb_177 (P3, 2026-03-27)
- **Hash**: sha256:def456...
- **Player**: P3
- **Duration**: 60s (1 minute)
- **Transport**: USB
- **Battery type**: resting_grip
- **Game context**: Free play gold tier
- **PITL status**: All NOMINAL
- **L4 score**: Within thresholds
- **PoAC records**: 300 (1 min × 5 Hz)
- **Storage**: calibration_sessions/usb/usb_177_p3_20260327.json
- **Retention**: Permanent
- **Notes**: Final session in Phase 135 corpus

---

## 5. Separation Ratio Snapshots (Versioned)

### Snapshot v1 — Diagonal Approximation (Phase 121)

- **Timestamp**: 2026-03-20
- **Method**: Diagonal covariance (feature independence assumed)
- **Corpus**: N=177, 3 players
- **Pooled ratio**: 0.474
- **Per-battery ratios**:
  - Touchpad dominant: [value]
  - Trigger dominant: [value]
  - Resting grip: [value]
- **Confidence**: LOW (methodological approximation)
- **Status**: SUPERSEDED by v2 (pending)

### Snapshot v2 — Tikhonov Full Covariance (Phase 129)

- **Timestamp**: PENDING
- **Method**: Full covariance with Tikhonov regularization
- **Corpus**: N=177, 3 players (same as v1)
- **Pooled ratio**: TBD
- **Per-battery ratios**: TBD
- **Confidence**: HIGH (N>150, mathematically stable)
- **Status**: PENDING execution
- **Hypothesis**: > 0.60 or potentially > 1.0

### Future Snapshots

- **v3**: Post-touchpad-recapture (if Tikhonov < 1.0)
- **v4**: With 4th player (diversity improvement)
- **v5**: BT transport calibrated (N≥50)

---

## 6. Evidence Integrity

### Verification Procedures

**Periodic Integrity Check** (recommended: monthly):
```bash
# Compute corpus Merkle root
cd calibration_sessions
find . -name "*.json" -type f -exec sha256sum {} \; | sort | sha256sum
# Result: 0x... (corpus hash)
```

**Last Verification**: [Date to be filled]
**Result**: [PASS/FAIL]
**Discrepancies**: [None or list]

### Backup Locations

| Location | Status | Sync Frequency | Encryption |
|----------|--------|----------------|------------|
| Local (calibration_sessions/) | PRIMARY | Real-time | No |
| Git LFS | BACKUP | On commit | No |
| Cloud (specify provider) | BACKUP | Weekly | Yes (AES-256) |
| Offline (external drive) | ARCHIVE | Monthly | Yes (hardware encryption) |

### Legal Hold

**Purpose**: Tournament legal defense, regulatory compliance
**Jurisdiction**: [Specify if known]
**Retention Period**: 7 years minimum
**Destruction**: PROHIBITED (no deletion permitted)
**Access Log**: [If tracked]

---

## 7. Player Profiles

### Player P1

- **Sessions**: ~59
- **Dominant battery**: [touchpad|trigger|mixed]
- **Gameplay style**: [competitive|casual|mixed]
- **L4 baseline**: [Mahalanobis mean]
- **L5 baseline**: [CV mean]
- **Notes**: [Any patterns]

### Player P2

- **Sessions**: ~59
- **Dominant battery**: [touchpad|trigger|mixed]
- **Gameplay style**: [competitive|casual|mixed]
- **L4 baseline**: [Mahalanobis mean]
- **L5 baseline**: [CV mean]
- **Notes**: [Any patterns]

### Player P3

- **Sessions**: ~59
- **Dominant battery**: [touchpad|trigger|mixed]
- **Gameplay style**: [competitive|casual|mixed]
- **L4 baseline**: [Mahalanobis mean]
- **L5 baseline**: [CV mean]
- **Notes**: [Any patterns]

### Player P4 (Candidate)

- **Status**: RECRUITING
- **Requirements**: NCAA CFB 26 experience, DualShock Edge available
- **Target sessions**: 50+
- **Diversity benefit**: Gender, age, playstyle variation improves separation

---

## 8. Calibration Certificates

### USB Full Battery (Phase 46/134)

- **Calibration date**: 2026-03-25
- **N sessions**: 177
- **Method**: Diagonal covariance
- **Anomaly threshold**: 7.009
- **Continuity threshold**: 5.367
- **Certificate hash**: sha256:...
- **Status**: ACTIVE (but STALE — live_feature_dim=13 vs calibration_dim=12)

### Per-Battery Tracks (Phase 124-126)

Pending per-battery calibration:
- Touchpad dominant: [pending]
- Trigger dominant: [pending]
- Resting grip: [pending]

---

## 9. Usage Guidelines

### For Analysis

1. Always verify session hash before inclusion
2. Check player diversity (minimum 3, target 5+)
3. Confirm N≥50 for statistical significance
4. Document method: diagonal vs full covariance
5. Report honest ratio, not target ratio

### For Legal Defense

1. Preserve all session files (no deletion)
2. Maintain chain of custody (backup logs)
3. Document capture methodology (this file)
4. Provide expert testimony preparation (whitepaper §7)
5. Prepare for ratio measurement audit (SeparationRatioRegistry.sol)

### For Scientific Reproducibility

1. Share de-identified session data (hashes only, no raw HID)
2. Provide feature extraction code
3. Document Mahalanobis computation (covariance method)
4. Include confidence intervals
5. Archive analysis scripts with session data

---

## 10. Append-Only Log

| Date | Action | Sessions Added | Corpus Hash | Operator |
|------|--------|----------------|-------------|----------|
| 2026-03-15 | Initial capture | 50 | 0x... | [Operator] |
| 2026-03-20 | Continued capture | 100 | 0x... | [Operator] |
| 2026-03-27 | Phase 135 complete | 177 | 0x... | [Operator] |
| 2026-03-?? | BT capture start | 0→? | TBD | [Future] |
| 2026-0?-?? | 4th player added | 177→? | TBD | [Future] |

---

**Document Version**: 1.0 (Phase 135)
**Last Updated**: 2026-03-29
**Corpus Status**: N=177 USB, 0 BT, 3 players
**Next Milestone**: N=200 or Tikhonov verification
**Legal Hold**: ACTIVE
**Retention**: PERMANENT
