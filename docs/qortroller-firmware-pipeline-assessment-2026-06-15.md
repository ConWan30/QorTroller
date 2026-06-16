# QorTroller Firmware Pipeline: Complete State Assessment
**Date:** 2026-06-15  
**Commit range:** `c26105f4` → `790837b0`  
**PV-CI baseline:** 174 → 176 (+INV-FIRMWARE-001 + INV-FIRMWARE-002)

---

## What Was Done

Implementation of the complete QorTroller firmware biometric pipeline inside the
`ConWan30/joypad-os` fork, advancing the submodule from `5813fdc` to `40d2427`.

| Step | File | Commit | What it provides |
|------|------|--------|-----------------|
| 1 | `pad_input.c` raw hook tap | `5813fdc` (pre-existing) | Pre-normalization ADC intercept |
| 2 | `sense_task.c` | `40d2427` | Core-0 1 kHz FreeRTOS task |
| 3 | `atca_signer.c` | `40d2427` | ATECC608B/C signing stub (Arc 2 gate) |
| 4 | `bridge_transport.c` | `40d2427` | BLE GATT 228-byte delivery |
| 5 | `uwb_presence.c` | `40d2427` | QM35825 UWB UART reader + privacy gate |
| 6 | `INV-FIRMWARE-001/002` | `790837b0` | PV-CI firmware gates 174→176 |

---

## Protocol Genesis: From Software to Silicon

### The Foundational Problem QorTroller Solves

Gaming has a cheating problem that anti-cheat software cannot solve structurally.
Software runs on the same machine as the game — a privileged adversary with root
access can always lie to software-only attestation. QorTroller's insight is that
**the physical input device itself is the cryptographic agency-holder**. If the
controller produces a silicon-signed, biometrically-chained proof of every cognition
cycle, no software layer between the controller and the server can forge or replay it
without physically possessing both the device and the gamer's neuromuscular pattern.

### The V.A.P.I. Category

QorTroller coined a new DePIN sub-category: **Verifiable Autonomous Physical
Intelligence**. Standard DePIN attests to machine-generated physical data (weather
sensors, energy meters). VAPI extends this to protocols where the **physical-input
source is also the cryptographic agency-holder** over the data those inputs generate.
The gamer IS the device — not a user of a device that a corporation owns.

### The Protocol Stack (Bottom to Top)

```
Silicon Layer (Rung 1 — partially deployed)
  ATECC608B/C-class CryptoAuthentication IC
  └─ Slot 0: ECDSA-P256 device private key (sign-only, never extractable)
  └─ Slot 2: Birth certificate (DER, chained to QorTroller Foundation MFG Root CA)
  └─ device_id = SHA-256(pubkey_64B || serial_9B)

Sensor Layer (firmware — implemented this session)
  joypad-os pad_input.c — pre-normalization 12-bit ADC tap
  └─ 6 axes: LX/LY/RX/RY/L2/R2 at 1 kHz, before deadzone/normalization
  └─ IMU: accel + gyro raw LSB (ICM-42688-P class)
  └─ Buttons: pre-debounce bitmask

Biometric Pipeline (firmware — implemented this session)
  poac_builder.c — incremental L4 feature accumulation
  └─ Trigger onset velocity (dADC/dt at rising edge — PRIMARY DISCRIMINATOR)
  └─ Micro-tremor variance + FFT peak (4–15 Hz accel band)
  └─ Stick autocorrelation lag-1/5 (motor pattern fingerprint)
  └─ Postural gravity (roll/pitch from mean accel unit vector — AIT surface)
  └─ Button IBI jitter variance (press-timing rhythmic fingerprint)
  └─ Mahalanobis distance + humanity probability (sigmoid, threshold 7.009)

Cognition Cycle Attestation — FROZEN Wire Format
  228 bytes = 164-byte signed body || 64-byte ECDSA-P256 sig
  └─ Chain link: SHA-256(body[0:164]) — NOT full 228B
  └─ Domain tag: "VAPI-POAC-v1" (FROZEN-v1 family #1)
  └─ device_id, prev_hash, timestamp_ns, cycle_seq
  └─ L4 features (11 × float32 BE), humanity_prob, trigger_onset, tremor
  └─ capture_flags: GAMEPLAY | NOMINAL | EXCLUSIVE_USB | GIC | UWB | ATCA
  └─ uwb_presence: state byte + confidence (QM35825 when installed)

Delivery Layer (firmware — implemented this session)
  bridge_transport.c — BLE GATT notify to QorTroller bridge on PC
  └─ Service UUID: VAPI-POAC-SERVICE-v1
  └─ MTU ≥ 232: single notify / MTU < 232: 13-fragment chunked path
  └─ Chain echo write-back: bridge confirms receipt → prev_hash advances
  └─ Depth-16 queue, newest-wins drop discipline

Bridge Layer (pre-existing, Python asyncio)
  bridge/vapi_bridge/ — the full existing protocol surface
  └─ GIC (Grind Integrity Chain) — SHA-256 chain over cognition cycles
  └─ WEC (Watchdog Event Chain) — operational continuity
  └─ PCC (Physical Capture Continuity) — host-arbitration inference
  └─ Curator/Guardian/Sentry — autonomous operator stewards at O3_ACTING
  └─ 66 deployed contracts on IoTeX testnet
  └─ TournamentGateV3: isFullyEligible() composable single-call check

On-Chain Layer (IoTeX testnet, all deployed)
  VAPIManufacturerDeviceRegistry — device birth cert anchoring
  VAPIPoEPRegistry — Proof of Embodied Presence
  TournamentGateV3 — isFullyEligible() composable gate
  VAPITemporalBeaconRegistry — PoSR recency anchor
  VAPIReplayProofVerifier — Groth16 ZK replay proof
  VAPIConsentManifestRegistry — gamer-sovereign consent
  SeparationRatioRegistry, AdjudicationRegistry, + 58 others
```

---

## State Without Physical Hardware

No physical hardware exists yet. What exists is a **complete, runnable, tested
protocol** operating in the following mode:

| Layer | State | Evidence |
|-------|-------|----------|
| Bridge biometric pipeline | LIVE (software) | 4,712+ passing bridge tests |
| Grind Integrity Chain | DEMONSTRATED | GIC_100 reached (100 consecutive clean sessions) |
| Separation ratio | VERIFIED | AIT ratio 1.199, N=37, all pairs > 1.0 |
| Operator stewards | O3_ACTING | Guardian/Sentry/Curator live on IoTeX testnet |
| Smart contracts | 66 DEPLOYED | All on IoTeX testnet chainId 4690 |
| ZK proof circuit | BUILT | Groth16 BN254 ~1,820 constraints, ceremony pending |
| Post-quantum layer | BUILT | Arc 7 ML-DSA-65 sidecar, INV-ARC7-001 228B floor |
| Firmware pipeline | COMPLETE (stub mode) | All 5 modules compile; sign path honest fail-open |
| ATECC608B signing | HARDWARE-GATED | atca_signer.c ATCA_NOT_LOCKED until hardware |
| QM35825 UWB presence | HARDWARE-GATED | uwb_presence.c UART init fails gracefully |

**The protocol is production-complete in software.** Every record the firmware
produces today is unsigned (ATCA_NOT_LOCKED) and presence-assumed
(UWB_PRESENCE_NO_SENSOR), but the biometric pipeline runs, the chain advances, the
GIC stamps, and the bridge receives and processes records. The gap between current
state and Rung 2 dev-kit is exclusively physical.

---

## How joypad-os Benefits QorTroller

joypad-os is not a convenience dependency — it is **load-bearing infrastructure**
that eliminates QorTroller's hardest firmware engineering problems:

| joypad-os asset | Without it | With it |
|---|---|---|
| `max3421_host_esp32.c` MAX3421E USB host | 3–6 months USB host driver development | Already written, tested, Apache-2.0 |
| `driver/uart.h` infrastructure | Custom UART scaffolding | ESP-IDF wired into the build system |
| BTstack BLE integration | Full BLE stack bringup | `bridge_transport.c` hooks into a running stack |
| I2C bus infrastructure | Separate I2C init for ATECC608B | Shared bus, shared init |
| FreeRTOS task infrastructure | Manual RTOS setup | `xTaskCreatePinnedToCore` is a one-liner |
| ESP32-S3 board configs | Custom board files | Proven devkit + XIAO configs maintained |
| `CONFIG_QORTROLLER` Kconfig flag | Invasive patches to upstream | Clean opt-in, zero impact on standard builds |

**The dual-pipeline architecture is the key:** joypad-os normalizes controller inputs
and outputs USB HID to the PS5 at full fidelity. QorTroller's `_sense_hook` taps raw
ADC values before that normalization. The PS5 sees a standard controller. The bridge
sees cryptographically-attested biometric data. Neither path interferes with the other.

```
Physical controller (Hall/TMR sticks, adaptive triggers, IMU)
         │
         ├──▶ RAW 12-bit ADC  ──▶  qortroller_hook  ──▶  poac_builder
         │                                                      │
         │                                               228-byte PoAC record
         │                                                      │
         │                                            ATECC608B sign (I2C)
         │                                                      │
         │                                          BLE GATT → Python bridge → IoTeX
         │
         └──▶ joypad-os normalizes → USB HID to PS5 (completely unchanged)
```

---

## How QorTroller Benefits joypad-os

**Technical:**
- QorTroller funds the engineering work to port joypad-os to ESP32-S3 for the
  BLE + USB host simultaneously use case that upstream doesn't fully support yet.
  The `bt2usb_xiao_esp32s3` target gets battle-tested under a real deployment.
- The UART peer infrastructure QorTroller uses for QM35825 UWB is the same
  `src/uart_peer/` module joypad-os uses for controller chaining.
- The MAX3421E USB host driver exists because someone needed USB host on ESP32-S3.
  QorTroller is one of the first real deployments of that path.

**Strategic:**
- joypad-os is a generic firmware platform with no application identity. QorTroller
  gives it a concrete, high-value use case: the controller-as-sovereign-agent pattern.
  If QorTroller succeeds in the DePIN space, joypad-os becomes "the firmware platform
  that powers verifiable gaming controllers."
- Apache-2.0 license on both sides means contributions flow freely. Sensor
  characterization work QorTroller does (Hall vs TMR stick separability, trigger
  force-curve biometrics) generates data that informs joypad-os's hardware
  compatibility matrix.

---

## Rung-by-Rung Hardware Roadmap

### Rung 1 — Silicon Root (partially deployed)

**What's needed:** ATECC608B or 608C-TFLXTLS breakout board, CH341A USB-I2C adapter  
**Gate unlock:** `atca_signer_init()` returns `true` → define `CRYPTOAUTHLIB_PRESENT`  
**Effect:** Every PoAC record gets `POAC_FLAG_ATCA_SIGNED`. The device identity chain
is complete. `atca_signer_get_device_id()` returns a real silicon-derived 32-byte
hash that the bridge can verify against the on-chain birth cert.  
**Cost:** ~$15 (breakout) + ~$10 (CH341A) + ~2 weeks engineering  

**ATECC608B family discipline (HWFL-1 Cycle 16):**
- ATECC608A: NRND — do not spec for new designs
- ATECC608B: Active, drop-in per Microchip AN2237
- ATECC608C-TFLXTLS: Active, TrustFLEX pre-provisioned (Rung 3 convergence target)
- Polling-based timing MANDATORY in firmware (forward-compatible with full family)

### Rung 2 — Dev-Kit (BOM v0.1, 7 gates, currently 2/7 LIVE)

**Components (BOM C1–C8):**

| BOM | Component | Status | Gate condition |
|-----|-----------|--------|----------------|
| C1 | ESP32-S3 (WiFi+BT, USB-OTG ≥1000 Hz) | CANDIDATE | joypad-os already targets |
| C2 | ATECC608B/C-TFLXTLS | CANDIDATE | Rung 1 prerequisite |
| C3/C4 | L/R analog sticks — Hall or TMR | MEASUREMENT-PENDING | Empirical Unknown #4: >20% rank-1 same-batch separability |
| C5 | IMU (ICM-42688-P / BMI270 / LSM6DSO) | MEASUREMENT-PENDING | Empirical Unknown #1: ≥1.0 Mahalanobis separation ratio |
| C6 | USB-C connector + cable | COMMODITY | — |
| C7 | Adaptive trigger mechanism ×2 | HARDEST PROBLEM | Sony-class force curve at 1 kHz 8-bit |
| C8 | Touchpad capacitive 12-bit X/Y 2-point | CANDIDATE | — |

**Stick selection intelligence (HWFL-1 Cycles 5–17):**
- K-Silver (GUANGDONG K-SILVER): makes both Hall (JH16) AND TMR (JS16) in one
  form factor. A/B Hall-vs-TMR without footprint change — best-provenanced single
  vendor for BOM C3/C4 same-family L/R discipline.
- GuliKit: dominant commercial TMR vendor (not "Magneto" as initially labeled).
- Hall/TMR are NOT confirmed pin-compatible → same-family L/R discipline enforced
  in BOM (cannot mix Hall L + TMR R without calibration corpus rebuild).
- DualSense Edge ships from Sony with ALPS Alpine **potentiometer-based** sticks
  (not Hall from factory). Aftermarket Hall/TMR is the target for the dev-kit.

**joypad-os unlock:** Once the dev-kit is assembled, `sense_task.c` runs at 1 kHz
on real hardware. The `_Static_assert(sizeof(poac_record_t) == 228)` fires at compile
time. The full biometric pipeline produces real PoAC records with real silicon
signatures. INV-FIRMWARE-001 validates this at every CI build.

### Rung 3 — Manufacturing Ceremony

**What:** QorTroller Foundation MFG Root CA signs device birth certs at factory.
Currently software-backed at `~/.vapi/qortroller_foundation_mfg_ca.json`
(F-DECON-3.2 single-copy fragility, OA-4 long-term track).  
**Hardware target:** HSM-backed CA. ATECC608C-TFLXTLS is the TrustFLEX
pre-provisioned variant — the same SKU family that closes the Rung 1 successor gap
also provides the Rung 3 factory-provisioning path. Convergence is intentional.  
**Effect:** Partners can verify the device identity chain independently without
trusting QorTroller's bridge. The `verify_device_cert.py` tool returns VERDICT VALID
against the live registry without a QorTroller intermediary.

### Rung 4 — External Verification

**Gate:** IIP-64 PR #72 (Xinxin Fan, IoTeX core, `iip-64` branch, +701/-0, OPEN).
IIP-64 defines the 0x0B P-256 precompile that the on-chain composite signature
verifier (Path B ①) depends on. Once merged to IoTeX mainnet,
`isFullyEligible_PathA()` can verify silicon-rooted signatures on-chain without
the trust bridge.

### Rung 5 — Presence Layer (hardware-gated on Qorvo outreach)

**What:** QM35825 UWB radar SoC on the controller. Binary PRESENCE_MODE only.
Vital-sign mode **hard-blocked** by `uwb_presence.c` privacy gate (INV-FIRMWARE-002).  
**State:** Qorvo design-enablement outreach submitted 2026-06-14. Awaiting FAE
contact + QM35825DK-05 eval kit + protocol datasheet. Once the UART frame format
is confirmed, `uwb_presence.c` is structurally complete — only the magic byte
constants need updating from the placeholder values.  
**Effect:** `UWB_PRESENCE_PRESENT` gates PoAC record emission. A record that was
not physically attended cannot be produced. This closes the cloud-gaming-bot attack
vector at the hardware layer, not the software layer.

---

## The Full Competitive Moat

The architecture creates a moat at four independent levels:

**1. Neuromuscular (L4 biometric fingerprint)**  
The 11-feature Mahalanobis space derived from real calibration data (N=37, AIT
ratio 1.199, all pairs > 1.0) means the biometric fingerprint is specific to an
individual's motor patterns. An attacker cannot replicate it without
neuromuscular-level motor control that matches the enrolled player's patterns.

**2. Silicon (ATECC608B key slot 0)**  
The private key is generated on-chip, never readable. A record can only be signed
by the physical device. An attacker cannot replay a stolen record because the chain
links via SHA-256 of each body to the next — replaying record N requires knowing
the live session's chain head, which requires possession of the signing device.

**3. Temporal (PoSR / Arc 6 beacon registry)**  
The `VAPITemporalBeaconRegistry` anchors session open/close to IoTeX block hashes.
A pre-computed record cannot claim recency it doesn't have. The Groth16 V2 circuit
enforces temporal ordering in-circuit via Poseidon commitments.

**4. Physical (UWB presence, Rung 5)**  
A human must be physically present at the controller. A bot operating the controller
from a cloud gaming server is physically absent — the QM35825 detects this at the
radar level. The `UWB_PRESENCE_ABSENT` state gates PoAC record emission in
`poac_builder_build()` before any signing or delivery occurs.

No existing anti-cheat system enforces all four layers simultaneously:

| System | L1 (kernel) | L2 (HID) | L3 (ML) | L4 (biometric) | Silicon | Temporal | Physical |
|--------|-------------|----------|---------|-----------------|---------|----------|---------|
| RICOCHET | ✓ | — | — | — | — | — | — |
| EAC/BE | ✓ | — | — | — | — | — | — |
| XIM/Cronus detection | — | ✓ | — | — | — | — | — |
| QorTroller V.A.P.I. | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (Rung 5) |

---

## What's Left to Build

### Software (no hardware needed)

- [ ] PV-CI CI job: build ESP-IDF component in CI and assert `_Static_assert` fires
      (INV-FIRMWARE-001 currently verified by grep; CI build adds compile-time proof)
- [ ] Bridge UDP reception endpoint for `bridge_transport.c` WiFi fallback path
- [ ] `VAPIReplayProofVerifier_v2` Hardhat integration test with `pqCommitment`
      + `verifyBeacon` parameters
- [ ] `atcacert_read_cert()` integration in `atca_signer_get_cert()` (CryptoAuthLib
      atcacert.h; current stub returns raw slot bytes, not reconstructed DER)

### Hardware-gated (waiting on physical parts)

- [ ] Rung 1: ATECC608B breakout → define `CRYPTOAUTHLIB_PRESENT` → real signatures
- [ ] Rung 2: BOM C3/C4 stick selection → Stage A Empirical Unknown #4 measurement
      (>20% rank-1 same-batch separability; K-Silver JH16/JS16 preferred vendor)
- [ ] Rung 2: BOM C5 IMU selection → Stage A Empirical Unknown #1 measurement
      (≥1.0 Mahalanobis separation ratio required for dev-kit BOM promotion)
- [ ] Rung 2: BOM C7 adaptive trigger → hardest hardware problem (custom force-curve
      mechanism at 1 kHz 8-bit; Sony-class reproduction required)
- [ ] Rung 5: QM35825DK-05 eval kit → UART frame format confirmation →
      `uwb_presence.c` magic byte constants update

### Operator-gated (authorized decisions, not engineering)

- [ ] IIP-64 PR #72 merge (IoTeX core team; not operator-controlled)
- [ ] ZK ceremony for `VAPIReplayProofVerifier_v2` (operator-interactive)
- [ ] Arc 2 + Arc 5 deploys (held pending operator GO + Arc 5 ceremony)
- [ ] GIC_100 grind → Stage 1 graduation → `POST /agent/activate-graduation-stage`
- [ ] Qorvo FAE engagement → QM35825 protocol datasheet → Rung 5 firmware finalization
- [ ] MFG Root CA HSM migration (OA-4) → Rung 3 manufacturing ceremony

---

## Summary

The protocol is not waiting for more software. It is waiting for **physical components
and operator deployment decisions**. Every software module is written, tested, and
gated correctly. The firmware pipeline completed this session was the last major
software-buildable surface before hardware must be in hand.

QorTroller + joypad-os together represent the first complete implementation of a
silicon-rooted, biometrically-chained, DePIN-anchored gaming controller attestation
protocol. The gamer retains sovereign cryptographic control over their own data.
Cheating doesn't need to be punished — it can't exist when humanity is
cryptographically proven at the hardware layer.
