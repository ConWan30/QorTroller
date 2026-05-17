# VBDIP-0006 — VAPI Firmware Reference Implementation

**Status:** Draft. Architect Ed25519 signature pending operator-runtime ceremony.
**Date:** 2026-05-15
**Author:** VAPI Principal Architect
**Track:** VAD bridge sub-discipline (VBDIP). Mirrors VBDIP-0001 (VAD framework) + VBDIP-0002 (ZKBA visual projections) authoring pattern.
**Canonical anchors:**
- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` (parent framework)
- `wiki/methodology/bt_calibration_v1_1_architectural_revision.md` (transport verification rule)
- `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` (DualSense Edge sensor characterization)
- `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`
- `wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf`
- `lessons.md` entries `BT-CALIB-LESSON-001`, `CROSS-LESSON-001`, `MLGA-LESSON-001`, **`FIRMWARE-REFERENCE-LESSON-001`** (this proposal authors)

## Section 0 — Executive Summary

The VAPI bridge today constructs 228-byte PoAC records from HID frames it reads via hidapi from a DualSense Edge connected over USB-C. The implicit trust assumption is that "the HID stream the laptop sees was emitted by an unmodified, tamper-evident DualSense Edge." That assumption is falsifiable by the cloud-gaming-bot stealth attack class documented in the v1.1 BT calibration anchor §3 — a sophisticated attacker can replay HID frames to spoof a session, inject synthesized inputs that mimic biometric features, or bypass the controller entirely while the controller's BT emissions remain plausible.

VBDIP-0006 specifies the architectural path that closes this gap: **VAPI-Native Controllers** where the 228-byte PoAC wire format is constructed and ECDSA-P256 signed inside the controller's secure element before it leaves the device. The controller's private key is generated inside the secure element + never readable by external interfaces + tamper-resistant per FIPS 140-2 Level 3 (or equivalent) under physical attack. Even full firmware extraction does not yield the key without coordinated tamper-attack on the secure element chip itself.

The trust-boundary shift VBDIP-0006 documents:

| Layer | Before (today) | After (VBDIP-0006 firmware operational) |
|---|---|---|
| Layer 0 (Physical Input) | Implicit trust in HID stream | Cryptographic signature at-source |
| Bridge construction | Bridge derives PoAC from HID frames | Bridge **validates** signed PoAC from controller |
| Attack surface | HID frame replay possible | Replay impossible without secure-element key access |
| Trust property | "We trust this controller is unmodified" | "We trust this signature came from a registered, certified device" |

VBDIP-0006 is **a markdown specification only**. It does NOT ship hardware, does NOT modify the bridge, and does NOT close the implementation gap. It is the document a firmware engineer (operator runtime, or external manufacturer engineer) reads when implementing a VAPI-Native Controller. It is also the document an operator references when pitching manufacturer partnerships.

VBDIP-0006 v1.0 claims session-bound device-attested PoAC emission. VBDIP-0006 v1.0 does NOT claim cross-session controller identity (CROSS-LESSON-001 same-model separability gap is unresolved). VBDIP-0006 v1.0 does NOT claim defense against attackers with full physical custody of the controller + coordinated tamper-attack capability on the secure element + replacement firmware programming. Those are explicitly out of scope and reserved for v2 if and when SE-tampering-defense hardware is justified.

## Section 1 — Scope and Intent

### What VBDIP-0006 specifies

The minimum-viable contract that any firmware claiming to be "VAPI-Native" must satisfy. The contract has four mandatory components:

1. **Wire format compliance.** Firmware emits the 228-byte FROZEN PoAC wire format per `bridge/vapi_bridge/codec.py` byte-for-byte. The 164-byte signed body + 64-byte ECDSA-P256 signature.
2. **At-source cryptographic signing.** The signature is generated inside a secure element + binds the body to a device private key that never leaves the chip.
3. **Device identity attestation.** The device registers its public key with `VAPIHardwareCertRegistry` (Phase 99A LIVE on IoTeX testnet at `0x1031b7840184D6c8f0EA03F051970578C3c874C2`) at manufacturer-side device-family certification time. The on-chain registration produces a HARDWARE Participation Card ZKBA artifact (7th ZKBA class, Phase O3-ZKBA-TRACK1 closure).
4. **Conformance test pass.** The firmware passes the conformance test suite documented in §8 — 100 deterministic test vectors that map fixed inputs to specific PoAC signatures verifiable against the device public key.

### What VBDIP-0006 does NOT specify

VBDIP-0006 is deliberately **transport-and-hardware-agnostic** within the constraint envelope established by BT-CALIB-LESSON-001 + Sensor Stack v2.1. It does not specify:
- Which microcontroller IC the firmware runs on (Teensy 4.1, STM32H743, NXP MCXN947, RP2040 — all permitted as long as the contract is met)
- Which secure element chip is used (ATECC608B reference; other ECDSA-P256 + tamper-resistant + non-exportable-key SEs equivalent)
- Which sensor ICs are integrated (Sensor Stack v2.1 constrains the L4 feature surfaces but not specific part numbers)
- The controller's physical shell, button layout, ergonomic decisions

VBDIP-0006 is a protocol specification, not a product specification.

### Why session-bound, not cross-session

Per `lessons.md` `CROSS-LESSON-001`, cross-session controller identity claims require a same-model separability study for N≥3 identical controllers in tournament-realistic conditions. That study does not exist for any DePIN gaming protocol, including VAPI's planned partners. Until it exists, VBDIP-0006 v1.0 firmware claims session-bound device attestation only — every PoAC record is signed; every session is bindable to a registered device family; but the protocol does NOT claim that "this PoAC came from THE specific physical unit serial #ABCD1234" with cryptographic certainty across sessions.

This restraint is the v1.0 constraint envelope. CROSS-LESSON-001 closure unlocks a v2 expansion.

## Section 2 — Transport Verification Block

Per `BT-CALIB-LESSON-001` application rule, this section documents the verified transport primitives any VBDIP-0006 firmware must implement. Three independent verification source classes cited for each transport.

### Channel A — USB-HID composite device

VBDIP-0006 firmware MUST present as a USB composite device exposing TWO HID interfaces over USB Full-Speed (12 Mbps minimum) or USB High-Speed (480 Mbps):

**Interface 0 — Standard Gamepad HID.** A DualShock-compatible HID descriptor that the host operating system (Windows / macOS / Linux / PS5 / PS5 Pro) recognizes as a controller. Required so the controller works as a normal game input device.

**Interface 3 — VAPI Custom HID.** A custom HID interface that emits the 228-byte PoAC stream at 1000 Hz. Bound to USB Usage Page 0xFF00 (vendor-defined). Required so the VAPI bridge can subscribe to the signed PoAC records.

Verification sources for USB-HID composite descriptors on the target MCU class (Teensy 4.1 / STM32H743):
1. **USB-IF Class Definition for Human Interface Devices** v1.11 (Section 6, Composite Devices) — the upstream standard
2. **TeensyUSB library source** (`teensy/usb_hid_dual` reference) — the reference firmware implementation
3. **Field confirmation** — Windows USB Device Tree Viewer + Linux `lsusb -v` both successfully enumerate Teensy 4.1 composite descriptors with multiple HID interfaces

USB composite is verified-supported on all target MCU classes.

### Channel B — BT-Classic BR/EDR with HIDP

VBDIP-0006 firmware MUST pair to PS5 (and other BR/EDR HIDP hosts) using Bluetooth Classic BR/EDR with HID-over-L2CAP (HIDP profile). This is the transport DualSense Edge uses today. Per `BT-CALIB-LESSON-001` verification block (the Linux mainline `hid-playstation.c` driver + Bluepad32 FAQ + BlueRetro project + PCGamingWiki Controller:DualSense Edge entry + FreeBSD field test):

- **NOT BLE-HOGP.** BLE with HID-over-GATT is a different transport stack. PS5 does not negotiate BLE-HOGP with DualShock-class controllers.
- BT-Classic primitives the firmware exposes: Tpoll (the polling interval the master uses), AFH channel map across 79 1-MHz channels, L2CAP/baseband ARQN/SEQN retransmission counters, HCI Read_RSSI per ACL link.

The firmware MUST implement BR/EDR via a BT-Classic-capable radio module. Reference implementations:
- **Espressif ESP32-S3-WROOM-1U** — has BT 5.0 with BR/EDR + LE dual mode + HIDP support
- **Nordic nRF52840** — primarily LE-focused but has BR/EDR via external radio firmware (more complex)
- **Cypress / Infineon CYW43439** — Pi Pico W radio; BR/EDR + LE dual mode

VBDIP-0006 v1.0 firmware implements BR/EDR HIDP only. BLE-HOGP variants are reserved for a future VBDIP-0006-BLE addendum if and when manufacturer demand justifies it (per the v1.1 BT calibration revision §2 pivoting decision).

### Channel C — VAPI Mode toggle

VBDIP-0006 firmware MUST support two operating modes:

**Mode A — Standard Controller Mode.** The controller behaves identically to a stock DualSense Edge. The VAPI Custom HID interface (Interface 3) is present in the descriptor but inactive — does not emit PoAC records. Host applications that don't know about VAPI simply ignore the unused interface.

**Mode B — VAPI Attested Mode.** The VAPI Custom HID interface actively emits the 228-byte PoAC stream at 1000 Hz to subscribed hosts. Mode B is opt-in by the user; entering Mode B requires a deliberate button combo at boot (e.g., hold L2 + R2 + PS button during power-on) OR a host-side enable signal via Interface 0's feature reports.

Mode separation prevents PoAC stream leakage when the controller is paired to non-VAPI hosts (e.g., a casual PS5 game with no VAPI integration). It also gives the user explicit consent control per VAPI's biometric privacy discipline (BP-001 Temporal Biometric Decay) — Mode B activation = consent to PoAC emission for that session.

## Section 3 — FROZEN Cryptographic Primitives Implemented

VBDIP-0006 firmware MUST implement the following FROZEN primitives byte-for-byte. Drift on any of these breaks bridge compatibility + cryptographic verifiability + invokes Mythos-Crypto variant failure on the next PR after detection.

### 3.1 PoAC wire format (FROZEN per CLAUDE.md hard rules)

- **228 bytes total** per record (164B body + 64B ECDSA-P256 signature).
- **Body fields and layout** must match `bridge/vapi_bridge/codec.py` byte-for-byte. Field-by-field specification:

| Bytes | Field | Type | Notes |
|---|---|---|---|
| 0-7 | device_id | uint64 | `keccak256(pubkey)[0:8]` — first 8 bytes of the keccak256 hash of the ECDSA-P256 public key |
| 8-15 | counter | uint64 BE | monotonic non-decreasing counter; increments per record |
| 16-31 | record_hash | 16B | `SHA-256(raw[:164])[0:16]` — first 16 bytes of SHA-256 over the body region (PER CLAUDE.md hard rule: "chain link hash = SHA-256(164B body) — body ONLY, NOT 228B") |
| 32-39 | timestamp_ms | uint64 BE | monotonic milliseconds since device boot |
| 40-71 | prev_record_hash | 32B | full SHA-256 of the previous record's 164-byte body (zero-bytes for first record) |
| 72-103 | sensor_commitment | 32B | SHA-256 over the canonical-JSON-sorted 13-feature L4 vector |
| 104-104 | inference_code | uint8 | 0x00 = NOMINAL; 0x28/0x29/0x2A = hard cheat codes (DRIVER_INJECT, WALLHACK, AIMBOT); 0x2B/0x30-0x33 = advisory codes |
| 105-117 | l4_features | 13 × float16 | 13-feature Mahalanobis fingerprint (Sensor Stack v2.1) |
| 118-127 | l5_rhythm | 10B | CV (4B float32 BE) + entropy (4B float32 BE) + quantization flag (1B) + reserved (1B) |
| 128-163 | extension_field | 36B | reserved for future fields; firmware MUST zero this region |
| 164-227 | signature | 64B | ECDSA-P256 (r,s) over SHA-256(raw[:164]) using the device private key |

The cryptographic chain link hash for the GIC chain is `SHA-256(raw[:164])`. This is the FROZEN invariant from `CLAUDE.md` Hard Rule: "chain link hash = SHA-256(164B body) — body ONLY, NOT 228B".

### 3.2 Device identity (FROZEN)

`deviceId = keccak256(pubkey)` — the FROZEN keccak256 hash over the 64-byte uncompressed ECDSA-P256 public key. The full 32-byte deviceId is the unique on-chain identifier registered with `VAPIHardwareCertRegistry`. The first 8 bytes are embedded in every PoAC record at bytes 0-7.

### 3.3 GIC chain genesis tag (FROZEN per Phase 235-A)

`b"VAPI-GIC-GENESIS-v1"` (19-byte domain tag, FROZEN). The on-device GIC chain MUST be initialized using this tag as the prefix of the genesis hash preimage. See `bridge/vapi_bridge/grind_chain.py` for the bridge-side authoritative implementation that firmware must mirror.

### 3.4 Hard cheat codes (FROZEN)

The firmware MUST emit these inference_code values when the documented conditions trigger:
- `0x28` DRIVER_INJECT — when the on-device L2 IMU/HID/XInput discrepancy detector fires (Phase 47 + Phase 49 logic)
- `0x29` WALLHACK — currently never emitted by firmware; reserved for tournament adjudicator-side use only
- `0x2A` AIMBOT — currently never emitted by firmware; reserved for adjudicator-side use only

VBDIP-0006 v1.0 firmware emits `0x28` only. Hard cheat code emission is a controller-internal decision — the bridge does NOT instruct the firmware.

### 3.5 Advisory codes (firmware-side optional)

`0x2B` TEMPORAL_BOT, `0x30` BIOMETRIC_ANOMALY, `0x31` IMU_PRESS_DECOUPLED, `0x32` STICK_IMU_DECOUPLED, `0x33` GSR_CORRELATION_ABSENT.

VBDIP-0006 v1.0 firmware MAY emit `0x30` (L4 anomaly above threshold) but the L4 thresholds (anomaly=7.009, continuity=5.367) are calibrated by the bridge against multi-player corpus — the firmware does NOT make tournament-eligibility decisions, only emits the observed value. Bridge-side L4 logic remains authoritative.

### 3.6 PATTERN-017 commitment families relevant to firmware

The firmware MAY implement, but is NOT required to implement, these PATTERN-017 commitment-family primitives:

| Tag | When firmware would implement | Default v1.0 |
|---|---|---|
| `b"VAPI-CONSENT-v1"` | If firmware provides on-device per-category consent management | DEFER to bridge |
| `b"VAPI-VAME-v1"` | If firmware emits VAPI Application-Layer Message Envelopes | DEFER to bridge |
| `b"VAPI-CORPUS-SNAPSHOT-v1"` | Bridge-only primitive | NEVER firmware |
| `b"VAPI-FRR-v1"` | Bridge-only primitive (Operator Initiative Fleet) | NEVER firmware |
| `b"VAPI-MLGA-SESSION-v1"` | Bridge-only capability tag | NEVER firmware |

VBDIP-0006 v1.0 firmware implements ONLY: the 228-byte PoAC wire format + GIC chain advancement + the device identity / signing pipeline. Other primitives stay bridge-side. This keeps v1.0 firmware scope tractable for first-implementation manufacturers.

## Section 4 — Secure Element Contract

### 4.1 Required capabilities

The secure element (SE) integrated into VBDIP-0006 firmware MUST provide:

1. **ECDSA-P256 hardware signing.** The SE generates and stores an ECDSA-P256 keypair. The private key NEVER leaves the SE — no exposed API can read it. Signing operations take a 32-byte message digest as input + return the 64-byte (r,s) signature. The bridge validates signatures using only the public key.

2. **Hardware key generation.** The keypair is generated inside the SE during manufacturer-side factory programming OR at the controller's first boot. Externally-injected keys (where the manufacturer types the private key into the SE) are explicitly NOT acceptable. The manufacturer programs ONLY a manufacturer-side signing certificate that proves the SE was provisioned by the certified manufacturer.

3. **Tamper-resistant storage.** The SE must protect against:
   - **Side-channel attacks** (timing, power analysis, electromagnetic emissions) at common-attacker tier
   - **Optical attacks** (laser fault injection) at common-attacker tier
   - **Physical chip decap + readout** — must produce a destroyed-on-tamper response under EM, X-ray, or chemical decapping
   - **Reset-glitching** attacks on the SE↔MCU bus

Minimum certification level: **FIPS 140-2 Level 3** (or Common Criteria EAL5+ equivalent). Reference implementation: **Microchip ATECC608B-MAHDA-S** which is FIPS 140-2 Level 3 + EAL5+.

4. **Attestation of provenance.** The SE must support a mechanism whereby the device proves it was provisioned by the certified manufacturer — typically via an X.509 certificate chain rooted at the manufacturer's CA. This certificate accompanies the device's pubkey registration on `VAPIHardwareCertRegistry`.

### 4.2 Reference implementation (firmware↔SE handshake)

For a Teensy 4.1 + ATECC608B reference implementation, the firmware handshake is:

```
Initialization (one-time, at first boot):
  1. firmware: SE.WAKE()
  2. firmware: SE.GEN_KEY(slot=0)
     → SE internally generates ECDSA-P256 keypair
     → returns public key (64 bytes uncompressed)
  3. firmware: Store public key in firmware-readable memory
  4. firmware: SE.SIGN(slot=0, message=manufacturer_provisioning_challenge)
     → produces signature proving the keypair was generated on this SE
  5. firmware: Send {pubkey, provisioning_proof} to manufacturer-side certification harness
  6. manufacturer: Validates provisioning_proof + calls VAPIHardwareCertRegistry.certifyDevice(profile_hash, manufacturer_addr)

Per-record signing (at 1000 Hz):
  1. firmware: Construct 164-byte PoAC body
  2. firmware: digest = SHA-256(body)
  3. firmware: SE.SIGN(slot=0, message=digest)
     → SE returns 64-byte (r, s) signature
  4. firmware: Compose 228-byte record (body || signature)
  5. firmware: Emit via USB-HID Interface 3
```

The signing operation latency is the primary firmware performance constraint. ATECC608B SIGN operations complete in ~50-80ms typical, which means the firmware MUST pipeline:
- Read sensors @ 1000 Hz on a 1ms scheduler
- Construct body for record N immediately
- Sign record N-1 in parallel
- Emit record N-2 when record N-1's signature returns

Three-deep pipeline → records emit at 1000 Hz with ~3ms cumulative latency, which is well within VAPI's bridge tolerance (the existing bridge-constructed pipeline has comparable latency from hidapi → record construction → store insert).

### 4.3 Acceptable secure-element substitutes

Any SE meeting the four capabilities in §4.1 satisfies the contract. Beyond ATECC608B, candidate SEs include:

- **NXP EdgeLock SE051** (FIPS 140-2 Level 3 + EAL6+; used in the IoTeX Pebble Tracker; ~$3 in volume)
- **STMicroelectronics STSAFE-A110** (FIPS 140-2 Level 3; ~$2 in volume)
- **Espressif HSM module** integrated in ESP32-S3 SoC (FIPS 140-2 Level 2 — NOT sufficient for v1.0 firmware; v2.0 may relax this)
- **Infineon OPTIGA Trust M** (Common Criteria EAL6+; ~$3.50 in volume)

Manufacturers may choose any of the above. The conformance test suite (§8) verifies SE behavior regardless of vendor.

## Section 5 — Sensor Pipeline Abstraction Layer

### 5.1 The firmware contract for sensors

VBDIP-0006 firmware MUST implement a sensor abstraction layer that exposes the following 13 L4 feature surfaces per Sensor Stack v2.1 architectural revision §2:

| Feature index | Feature name | Derived from | Sampling rate |
|---|---|---|---|
| 0 | `trigger_onset_velocity_L2` | Adaptive trigger force readout (Hall ADC) | 1000 Hz |
| 1 | `trigger_onset_velocity_R2` | Adaptive trigger force readout (Hall ADC) | 1000 Hz |
| 2 | `micro_tremor_accel_variance` | IMU accelerometer (still-hold ring buffer) | 1000 Hz |
| 3 | `grip_asymmetry` | IMU + button matrix | 1000 Hz |
| 4 | `stick_autocorr_lag1` | Right stick X ring buffer | 1000 Hz |
| 5 | `stick_autocorr_lag5` | Right stick X ring buffer | 1000 Hz |
| 6 | `tremor_peak_hz` | Accel magnitude FFT (4-15 Hz search, parabolic interp, 4096-pt zero-padded per Phase 213) | 1000 Hz windowed |
| 7 | `tremor_band_power` | Accel magnitude FFT band 4-15 Hz | 1000 Hz windowed |
| 8 | `accel_magnitude_spectral_entropy` | Shannon entropy of accel 0-500 Hz power spectrum (1024 frames; Phase 46) | 1000 Hz windowed |
| 9 | `touch_position_variance` | Touchpad capacitive 12-bit X/Y ring buffer | 250 Hz (touchpad native rate) |
| 10 | `press_timing_jitter_variance` | IBI deques per Phase 57 (Cross/L2/R2/Triangle button presses) | event-driven |
| 11 | `trigger_resistance_change_rate` | EXCLUDED in current corpus (Phase 17 zero-feature; reserved) | n/a |
| 12 | `touchpad_spatial_entropy` | 8×8 Shannon entropy heatmap of touchpad XY ring buffer (Phase 121; max log2(64)≈6.0 bits) | event-driven |

This is the same 13-feature surface the bridge-side `BiometricFeatureExtractor` in `dualshock_integration.py` produces today. The firmware MUST produce byte-compatible values to within the IEEE 754 float16 precision boundary.

### 5.2 Sensor IC substitution discipline

Firmware MAY substitute equivalent sensor ICs as long as the L4 feature output matches within 3σ deviation against the same physical input. Example substitutions:

| Reference sensor (DualSense Edge donor) | Acceptable substitute |
|---|---|
| Sony custom IMU | ICM-42688-P (TDK InvenSense) — `accel_variance` + `tremor_band_power` outputs match within 0.5 LSB² |
| Sony Hall-effect trigger sensor | Allegro A1308 — `trigger_onset_velocity` outputs match within 2 ADC counts |
| Sony capacitive touchpad | Azoteq IQS7222C — `touch_position_variance` outputs match within 50 squared-units |

Manufacturer responsibility: provide a substitution validation report with the device family certification documenting the cross-IC match data.

### 5.3 What the firmware does NOT do at the sensor pipeline layer

- Does NOT make L4 anomaly/continuity decisions (those use bridge-side calibrated thresholds 7.009/5.367 per CLAUDE.md hard rules)
- Does NOT make tournament-eligibility decisions (bridge-side `VAPIProtocolLens.isFullyEligible()` is the single composable gate)
- Does NOT modify or suppress L4 features based on observed values (firmware emits raw observations; bridge interprets)

## Section 6 — VAPI Mode HID Descriptor

### 6.1 USB descriptor structure

The composite device descriptor exposes:

```
Device Descriptor
├── Configuration 1: Composite
│   ├── Interface 0: HID — Standard Gamepad
│   │   ├── HID Descriptor (DualShock-compatible report layout)
│   │   ├── Endpoint 0x81 IN: Interrupt 64 bytes @ 1ms
│   │   └── Endpoint 0x01 OUT: Interrupt 64 bytes @ 1ms (haptic + LED feedback)
│   └── Interface 3: HID — VAPI Custom (Usage Page 0xFF00)
│       ├── HID Descriptor (vendor-defined report layout)
│       └── Endpoint 0x83 IN: Interrupt 256 bytes @ 1ms (PoAC stream)
```

Interface 3 (VAPI Custom) Report ID structure:

| Report ID | Direction | Length | Purpose |
|---|---|---|---|
| 0x01 | IN | 228 bytes | One PoAC record (FROZEN wire format) |
| 0x02 | IN | 64 bytes | Heartbeat (device public key broadcast every 1s) |
| 0x03 | OUT | 32 bytes | Bridge → firmware: Mode B activation signal + nonce challenge |
| 0x04 | IN | 96 bytes | Firmware → bridge: Nonce-challenge response (provisioning proof) |

The 256-byte endpoint MaxPacketSize accommodates the 228-byte PoAC record with 28 bytes of HID overhead. USB Full-Speed delivers 12 Mbps; per-frame budget is 12000 bits / 1ms = ~1500 bytes — well above the 256-byte requirement.

### 6.2 Report ID 0x01 (PoAC record) emission cadence

The firmware MUST emit one Report ID 0x01 record every 1ms (1000 Hz) when in Mode B. Skipped records are permitted only under documented degradation conditions (e.g., USB host backpressure, sensor IC initialization, secure element busy). Each skipped frame MUST be visible to the bridge via counter discontinuities — the firmware MUST NOT silently substitute zero records.

### 6.3 Report ID 0x02 (heartbeat) cadence

The firmware MUST emit one Report ID 0x02 heartbeat every 1 second regardless of Mode. The heartbeat carries:

- 8 bytes: device_id (first 8 of `keccak256(pubkey)`)
- 32 bytes: full device public key
- 24 bytes: firmware version (UTF-8, null-padded)

This lets the bridge enumerate connected devices + verify pubkey before subscribing to Report ID 0x01.

### 6.4 Backward compatibility with bridge

The existing VAPI bridge (commit `9cc15c3e` and later) reads HID data via hidapi from interface 3 byte-stream. Adapting to read the VAPI Custom HID Report ID 0x01 instead of the current biometric report layout requires a new bridge module `bridge/vapi_bridge/native_controller_ingest.py` (see Stage A engineering deliverables in §9). The existing hidapi interface 3 reading code coexists — both code paths run in parallel during the transition period.

## Section 7 — VAPIHardwareCertRegistry Registration Flow

### 7.1 The on-chain primitive

`VAPIHardwareCertRegistry` is LIVE on IoTeX testnet at `0x1031b7840184D6c8f0EA03F051970578C3c874C2` (Phase 99A, deployed in `contracts/scripts/deploy-phase99a.js`). The contract exposes:

```solidity
function certifyDevice(
    bytes32 profile_hash,
    uint8 cert_level,
    bytes32 device_pubkey_hash,
    address manufacturer_addr
) external returns (uint256 certId)

function isCertified(bytes32 profile_hash) external view returns (bool)
```

Where:
- `profile_hash` = SHA-256 over the device family canonical descriptor JSON (manufacturer name + model + firmware version + sensor IC list + secure element vendor)
- `cert_level` = `0` (prototype) / `1` (TIER 1 controller only) / `2` (TIER 2 controller + GSR per VAPIHardwareCertRegistry §35)
- `device_pubkey_hash` = `keccak256(pubkey)` — the same value embedded in PoAC records
- `manufacturer_addr` = manufacturer's wallet address; the cert artifact attributes manufacturing to this address publicly

### 7.2 Manufacturer-side certification flow

Per VBDIP-0006 v1.0, the manufacturer-side flow is:

1. **Device-family canonical descriptor.** The manufacturer authors a JSON file documenting:
   ```json
   {
     "manufacturer": "ExampleCorp",
     "model": "VAPI-Edge-Prototype-v1",
     "firmware_version": "0.1.0",
     "vbdip_0006_version": "1.0",
     "sensor_ics": ["ICM-42688-P", "A1308-x2", "IQS7222C", ...],
     "secure_element_vendor": "Microchip",
     "secure_element_part": "ATECC608B-MAHDA-S",
     "secure_element_cert": "FIPS-140-2-L3 + EAL6+",
     "test_suite_pass_report": "ipfs://bafy.../report.json"
   }
   ```
2. **profile_hash computation.** `profile_hash = SHA-256(canonical_json(descriptor_dict))`. Canonical-JSON discipline: sort_keys=True, separators=(",", ":"), ensure_ascii=False.
3. **Device pubkey collection.** During factory programming, each device's SE-generated pubkey is recorded.
4. **On-chain registration.** Manufacturer calls `certifyDevice(profile_hash, cert_level, device_pubkey_hash, manufacturer_addr)` from the manufacturer's wallet for each device.
5. **HARDWARE Participation Card emission.** Each certification produces a HARDWARE Participation Card ZKBA artifact (Phase O3-ZKBA-TRACK1 7th class, commit `35`) automatically — the script `scripts/zkba_compile_hardware_card.py` runs as a post-certification hook.

### 7.3 Per-device vs per-family certification

VBDIP-0006 v1.0 supports both:

- **Per-device certification:** Each individual physical unit gets one `certifyDevice` call. Higher gas cost (~0.05 IOTX per device) but full per-unit auditability.
- **Per-family certification:** One `certifyDevice` call certifies the entire device family by `profile_hash`. Individual devices are linked to the family certificate via their pubkey's match against the certified `profile_hash`. Lower gas cost; manufacturer batches.

The choice is manufacturer-strategic — high-end controllers may want per-device certification; mass-market may want per-family. Both modes satisfy the contract.

### 7.4 Why this matters for tournament eligibility

`VAPIProtocolLens.isFullyEligible()` (Phase 70 LIVE) composes `isCertified(profile_hash)` as one of its sub-checks. A controller registered via the flow above becomes recognized as VAPI-Certified, which means its PoAC stream can be admitted to tournaments that require VAPI-certified hardware. Without this registration, the controller's PoAC stream is unsigned (or signed by an unrecognized key) and tournaments reject it.

## Section 8 — Conformance Test Suite Specification

### 8.1 The 100 test vectors

VBDIP-0006 v1.0 firmware compliance is verified against 100 deterministic test vectors. Each vector specifies:

```json
{
  "vector_id": "TV-001",
  "fixed_input": {
    "device_pubkey_hash": "0x..." (32B),
    "counter": 12345,
    "timestamp_ms": 1747252800000,
    "prev_record_hash": "0x..." (32B),
    "sensor_commitment": "0x..." (32B),
    "inference_code": 0,
    "l4_features": [/* 13 float16 values */],
    "l5_rhythm_cv": 0.42,
    "l5_rhythm_entropy": 2.71,
    "l5_rhythm_quant_flag": 0
  },
  "expected_body_bytes": "0x..." (164B; FROZEN serialization),
  "expected_record_hash": "0x..." (16B; SHA-256(body)[0:16])
}
```

For each test vector:

1. Firmware receives the fixed_input via a test-harness HID command
2. Firmware constructs the 164-byte body using its internal serialization
3. Firmware emits the body via a test-harness output endpoint
4. Test suite verifies the body matches `expected_body_bytes` byte-for-byte
5. Test suite verifies the record_hash matches `expected_record_hash` byte-for-byte
6. Test suite asks firmware to sign the body
7. Firmware uses its SE to produce a 64-byte signature
8. Test suite verifies the signature is valid ECDSA-P256 over `SHA-256(body)` using the device's pubkey

Vector pass criteria: ALL 8 steps must succeed. The full set of 100 vectors covers:
- 20 vectors: random inputs (Mersenne Twister seed=0)
- 20 vectors: edge case inputs (zero-valued fields, max-valued fields, negative L4 features)
- 20 vectors: hard-cheat scenarios (inference_code=0x28, varying l4_features)
- 20 vectors: GIC chain continuity (sequence of 20 records with chained prev_record_hash)
- 20 vectors: counter rollover behavior (counter near uint64 max)

### 8.2 Test harness shape

The conformance test suite is implemented as a Python script `scripts/test_vbdip_0006_conformance.py` (Phase 2 deliverable; not yet shipped as of VBDIP-0006 v1.0 freeze). It:

1. Connects to a VAPI-Native Controller via USB-HID
2. Reads device pubkey via Report ID 0x02 heartbeat
3. Issues 100 test vectors via a test-harness OUT report
4. Collects firmware responses via a test-harness IN report
5. Validates each vector per §8.1 step 1-8
6. Emits a pass/fail report

Manufacturer ships the pass report alongside the device family certification on `VAPIHardwareCertRegistry`. The pass report is anchored to IPFS via `manifest.test_suite_pass_report` in the device family canonical descriptor.

### 8.3 Why deterministic test vectors

Non-deterministic test vectors would allow firmware to silently lie (deliberately or accidentally) about wire format compliance. Deterministic vectors make compliance verifiable by any party with the firmware + the published vector set + a USB-HID interface.

## Section 9 — Constraint Envelope (v1.0 Claims Discipline)

Mirrors the v1.1 BT calibration revision §7 constraint envelope pattern. VBDIP-0006 v1.0 claims discipline:

### 9.1 What VBDIP-0006 v1.0 firmware DOES claim

- Tamper-evident PoAC emission. The 228-byte signed records are cryptographically anchored to a device private key that physical-attack-defends per FIPS 140-2 Level 3 or equivalent.
- Wire format compliance. The 100-vector conformance test suite passes — firmware emits byte-for-byte FROZEN PoAC records.
- Device identity attestation. The pubkey is registered with `VAPIHardwareCertRegistry` + the manufacturer is publicly attributable on-chain.
- Mode A / Mode B separation. The user has explicit consent control over PoAC emission.
- Session-bound attestation. Each gameplay session produces signed records that the bridge can validate against the device pubkey.

### 9.2 What VBDIP-0006 v1.0 firmware does NOT claim

- **Cross-session controller identity.** CROSS-LESSON-001 still binds. A signed PoAC record proves "this signature came from a registered + certified device" but does NOT prove "this signature came from THE specific physical unit serial #ABCD1234." Same-model separability study (N≥3 identical units in tournament-realistic conditions) is unresolved. v2.0 firmware may revisit if the study lands.
- **Defense against full physical custody + coordinated tamper-attack.** An attacker with sustained physical access to the controller + state-of-the-art tamper analysis equipment + bench programming setup can theoretically extract the SE private key. VBDIP-0006 v1.0 firmware claims resistance only against common-attacker tier (FIPS 140-2 Level 3 SE characterization).
- **Defense against post-extraction firmware replacement.** If an attacker extracts the SE keypair, they can program a replacement device that emits valid signatures with the original key. VBDIP-0006 v1.0 firmware does NOT include anti-cloning protection. v2 may explore physical unclonable functions (PUF) for this gap.
- **Detection of every cheat class.** VAPI's L1-L8 layers continue to cover advisory cheat detection. Firmware-side hard cheat detection is limited to `0x28` DRIVER_INJECT only. Other cheat classes remain bridge-side or adjudicator-side.
- **BLE-HOGP transport support.** Per the v1.1 BT calibration revision §2 decision, VBDIP-0006 v1.0 firmware is BR/EDR-HIDP only. BLE-HOGP variants require a separate VBDIP addendum.
- **Defense against the cloud-gaming-bot stealth attack in cloud-streamed-only mode.** If the controller is physically present + emitting valid PoAC but the inputs the game receives upstream are remote-replayed (Parsec / cloud-gaming user-script), the PoAC stream remains valid but the game-side input doesn't match. The cross-correlation lag check (v1.1 §5 Empirical Unknown #5) is the load-bearing detection signal. VBDIP-0006 v1.0 firmware-side does not address this — it remains a bridge + witness layer concern.

### 9.3 Implications for manufacturers + tournaments

Manufacturer marketing of VBDIP-0006-v1.0-conformant controllers should align with the constraint envelope. Acceptable marketing claims include:
- "Cryptographically signed gameplay attestation"
- "Hardware-anchored device identity for tournament eligibility"
- "Tamper-evident PoAC emission"
- "VAPI-Certified for tournament-grade trust"

Marketing claims that overstate the constraint envelope MUST be avoided:
- ❌ "Unforgeable controller identity across sessions" (cross-session identity not guaranteed in v1.0)
- ❌ "Cheat-proof gameplay" (only `0x28` DRIVER_INJECT firmware-side; other cheats remain advisory)
- ❌ "State-actor-resistant" (FIPS 140-2 L3 is not nation-state attacker resistant)

Tournament organizers admitting VBDIP-0006-v1.0 controllers should pair the on-chain certification check with bridge-side L1-L8 evidence aggregation per the existing VAPI protocol — the firmware-side signature is necessary but not sufficient.

## Section 10 — References and Companion Lessons

### Active VAPI lessons applied

- `BT-CALIB-LESSON-001` — Transport verification rule. §2 of this document applies it.
- `CROSS-LESSON-001` — Same-model separability constraint. §1 + §9 of this document explicitly cite it as v1.0 constraint envelope binding.
- `MLGA-LESSON-001` — Dual-connection topology insight. §2 of this document references the dual-USB + dual-BT operating model.
- `FIRMWARE-REFERENCE-LESSON-001` — Cryptographic signing at-source as the only Layer 0 trust closure path. **This proposal authors this lesson.** See `lessons.md` companion entry.

### Architectural anchors

- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` (parent framework)
- `wiki/methodology/bt_calibration_v1_1_architectural_revision.md` (transport canonical anchor)
- `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` (sensor canonical anchor)
- `wiki/methodology/mlga_architectural_proposal_v1.md` (companion proposal)

### Existing VAPI code references

- `bridge/vapi_bridge/codec.py` — FROZEN PoAC wire format authoritative implementation
- `bridge/vapi_bridge/grind_chain.py` — FROZEN GIC chain primitive (genesis tag + advancement)
- `bridge/vapi_bridge/dualshock_integration.py` — `BiometricFeatureExtractor` (the 13 L4 features firmware must mirror)
- `bridge/vapi_bridge/zkba_artifact.py` — PATTERN-017 commitment family registry
- `scripts/zkba_compile_hardware_card.py` — HARDWARE Participation Card emission (Phase O3-ZKBA-TRACK1 7th class)

### Existing VAPI on-chain primitives

- `VAPIHardwareCertRegistry` — `0x1031b7840184D6c8f0EA03F051970578C3c874C2` (Phase 99A LIVE)
- `VAPIioIDRegistry` — `0xF7885B588718b891B2234477D031607da4a7ACfe` (Phase 55 LIVE)
- `VAPIProtocolLens` — `0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf` (Phase 70 LIVE; composes `isCertified`)
- `AdjudicationRegistry` — `0x44CF981f46a52ADE56476Ce894255954a7776fb4` (Phase 111 LIVE; PoAd anchoring)

### External references

- USB-IF Class Definition for Human Interface Devices v1.11
- FIPS 140-2 Security Requirements for Cryptographic Modules
- Common Criteria CC v3.1 EAL5+ / EAL6+ certifications
- Microchip ATECC608B Data Sheet (DS40002193)
- NXP EdgeLock SE051 Product Brief
- IEEE 754 — Standard for Floating-Point Arithmetic (float16 encoding for L4 features)
- ECDSA P-256 / secp256r1 — NIST SP 800-186 Recommendations for Discrete Logarithm-Based Cryptography
- SHA-256 — FIPS 180-4 Secure Hash Standard
- Keccak-256 — Ethereum Foundation Yellow Paper Appendix B (deviceId derivation)

## Section 11 — Authoring Discipline + Versioning

VBDIP-0006 is a methodology layer document. Its lifecycle parallels VBDIP-0001:

- v1.0 ships as Draft → operator review + revision → FROZEN state at vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json with architect Ed25519 signature
- v1.x amendments ship via Appendix structure (mirrors VBDIP-0002 Appendix B v1.1 amendment pattern) — backward-compatible refinements + clarifications. v1.x amendments do not require re-signature of the v1.0 manifest; they add a v1.1 manifest with cross-reference.
- v2.0 ships only after at least one VBDIP-0006-v1.0-conformant controller has been shipped by a manufacturer partner + has collected at least 1000 in-field gameplay sessions of telemetry data demonstrating v1.0 firmware operates as specified. v2.0 may relax / extend / replace v1.0 sections.

### Architect Ed25519 signing procedure (operator-runtime)

Per VBDIP-0001 §6.2 precedent + the architect_key_attestation.json chain (`vsd-vault/eval/architect_key_attestation.json`):

```
1. Operator confirms VBDIP-0006 markdown is final (after review pass).
2. Operator computes canonical hash:
     python -c "import hashlib; print(hashlib.sha256(open('wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md','rb').read()).hexdigest())"
3. Operator signs the 32-byte hash with the architect Ed25519 private key:
     python -c "from cryptography.hazmat.primitives.asymmetric import ed25519; ..."
4. Operator writes the signed manifest to:
     vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json
5. Operator commits the manifest file in a separate commit (NOT this one) using the
   architect_key_attestation.json chain for provenance.
```

The current commit ships a placeholder manifest file (`vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json.PENDING-ARCHITECT-SIGNATURE`) documenting the procedure. The actual signed manifest ships in a follow-up operator-runtime commit when ready.

### PV-CI ceremony

This commit fires the PV-CI ceremony pinning the 4 new VBDIP-0006 invariants:
- `INV-VBDIP-0006-001` — §1 scope statement + trust-boundary-shift claim
- `INV-VBDIP-0006-002` — §3 FROZEN cryptographic primitives list (228-byte PoAC + GIC genesis tag + hard cheat codes)
- `INV-VBDIP-0006-003` — §6 VAPI Mode HID descriptor (Interface 3 Report ID 0x01 = 228 bytes + Usage Page 0xFF00)
- `INV-VBDIP-0006-004` — §8 conformance test suite specification (100 vectors)

PV-CI count delta: 113 → 117 (this commit) + 1 future (FIRMWARE-REFERENCE-LESSON-001) if pinned in a follow-up ceremony.

---

*VBDIP-0006 v1.0 Draft — VAPI Principal Architect, 2026-05-15*


---

## Appendix A — v1.1 Wire-Layout Reconciliation

**Status:** v1.1 amendment. Mirror of VBDIP-0002 Appendix B v1.1 amendment pattern + VBDIP-0006 §11.2 convention ("v1.x amendments ship via Appendix structure ... do not require re-signature of the v1.0 manifest; they add a v1.1 manifest with cross-reference").

**Date:** 2026-05-16
**Author:** VAPI Principal Architect
**Triggering finding:** VBDIP-0006 conformance harness M1 pre-flight inspection on commit `d47d49eb` discovered §3.1's byte-layout table does not match `bridge/vapi_bridge/codec.py` — the file §3.1 simultaneously declared as authoritative ("Body fields and layout must match `bridge/vapi_bridge/codec.py` byte-for-byte"). Per the operator's discipline (Codex co-architect brief 2026-05-16), the conformance corpus is a CONTRACT artifact for VBDIP-0006, not merely a regression corpus for the current bridge. The contradiction must be reconciled at the spec layer before vectors ship.

**v1.0 preservation invariant:** Lines 1-553 of this document — the entirety of v1.0 Sections 0 through 11 — remain BYTE-IDENTICAL to the v1.0 architect-signed snapshot. Verification of v1.0 against `vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json` (canonical hash `0667cd34ec2635e58da3fb7860d537018ed3b4f30290df2ccac4a84ecbf1d3db`) succeeds via git history: `git show 1f30057d:wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md` yields the v1.0 file exactly as signed. The v1.0 manifest stays valid against that git-snapshotted content.

This appendix is APPENDED to the file. The v1.1 manifest at `vsd-vault/manifests/proposals-VBDIP-0006/002.manifest.json` signs the current-commit file (v1.0 + Appendix A v1.1 amendment). Both manifests coexist.

---

### A.1 The contradiction (named explicitly)

VBDIP-0006 v1.0 §3.1 declared two contradictory authorities simultaneously:

1. **Declared "Body fields and layout must match `bridge/vapi_bridge/codec.py` byte-for-byte"** — making codec.py the authoritative oracle.
2. **Then provided a byte-offset table** that does NOT match what codec.py serializes.

Both layouts sum to 164B body + 64B signature = 228B record. The total is correct. The field positions are NOT.

The §3.1 table claimed `device_id` at bytes 0-7, `counter` at 8-15 (uint64), `record_hash` at 16-31 (16-byte truncation), `timestamp_ms` at 32-39, `prev_record_hash` at 40-71, `sensor_commitment` at 72-103, `inference_code` at byte 104, 13 × float16 L4 features at 105-117, L5 rhythm at 118-127, and 36B "extension_field reserved" at 128-163.

codec.py actually serializes `prev_poac_hash` at 0x00 (32B), `sensor_commitment` at 0x20 (32B), `model_manifest_hash` at 0x40 (32B), `world_model_hash` at 0x60 (32B), then a struct-packed block at 0x80-0xA3 containing `inference_result` (1B), `action_code` (1B), `confidence` (1B), `battery_pct` (1B), `monotonic_ctr` (4B uint32 BE), `timestamp_ms` (8B int64 BE), `latitude` (8B double BE), `longitude` (8B double BE), `bounty_id` (4B uint32 BE).

### A.2 Reconciliation rule (binding)

**`bridge/vapi_bridge/codec.py` is authoritative for the FROZEN PoAC v1 wire layout.** The v1.0 §3.1 table is SUPERSEDED by this v1.1 amendment. The codec.py implementation is FROZEN per the CLAUDE.md hard rule ("Never modify the 228-byte PoAC wire format") + has been the source of truth for every PoAC record the bridge has parsed since Phase 17. The PoAC wire format has shipped through 49 LIVE contracts and ~3500 bridge tests against this exact byte layout. Re-aligning the codec to match v1.0 §3.1's table would be a FROZEN-region break — not permissible.

**`codec.py` is not modified by this amendment.** The reconciliation moves at the SPEC layer only.

### A.3 Authoritative wire layout (replaces v1.0 §3.1 table verbatim)

The 228-byte PoAC record body layout per codec.py header docstring + `_FIELDS_FMT` struct format:

| Offset | Field | Size | Format | Notes |
|---|---|---|---|---|
| 0x00 | `prev_poac_hash` | 32B | raw bytes | Full SHA-256 of the previous record's 164-byte body. Zero-bytes for first record in a chain. This is the GIC-chain backbone primitive. |
| 0x20 | `sensor_commitment` | 32B | raw bytes | SHA-256 commitment over the sensor-feature canonical projection. L4/L5 biometric features are COMMITTED through this hash — NOT serialized as raw float16 fields in the body. |
| 0x40 | `model_manifest_hash` | 32B | raw bytes | SHA-256 of the on-device TinyML model manifest. Bridge cross-references against published model registry. |
| 0x60 | `world_model_hash` | 32B | raw bytes | SHA-256 of the EWCWorldModel state snapshot at record time. Used for cross-session continuity checks (E4 cognitive drift). |
| 0x80 | `inference_result` | 1B | uint8 | 0x00 NOMINAL, 0x01 ANOMALY_LOW, 0x02 ANOMALY_HIGH, 0x10 STATIONARY, 0x11 WALKING, 0x12 VEHICLE, 0x13 FALL. Hard-cheat codes 0x28/0x29/0x2A per v1.0 §3.4 + advisory codes 0x2B/0x30-0x33 per §3.5 are also valid `inference_result` values when firmware-emitted. |
| 0x81 | `action_code` | 1B | uint8 | ACTION_NAMES enum (NONE/REPORT/ALERT/BOUNTY_*/PSM_*/MODEL_UPDATE/BOOT/SWARM_SYNC). |
| 0x82 | `confidence` | 1B | uint8 | 0-255 confidence in the inference (255 = highest). |
| 0x83 | `battery_pct` | 1B | uint8 | 0-100 battery percentage. |
| 0x84 | `monotonic_ctr` | 4B | uint32 BE | Non-decreasing counter; wraps at 2^32-1. Firmware MUST handle wrap-around. NOTE: v1.0 §3.1 erroneously specified uint64 at bytes 8-15; actual is uint32 at offset 0x84. |
| 0x88 | `timestamp_ms` | 8B | int64 BE | Milliseconds since device boot (signed for clock-correction events). |
| 0x90 | `latitude` | 8B | IEEE 754 double BE | GPS latitude; 0.0 when not reported. |
| 0x98 | `longitude` | 8B | IEEE 754 double BE | GPS longitude; 0.0 when not reported. |
| 0xA0 | `bounty_id` | 4B | uint32 BE | Bounty Market reference; 0 when not bounty-bound. |
| ---  | body total | **164B** | | Everything above; signed by the device key. |
| 0xA4 | `signature` | 64B | raw (r ‖ s) | ECDSA-P256 signature: 32-byte r ‖ 32-byte s. Computed as ECDSA-P256(SHA-256(body[0:164])) using the device's secp256r1 private key. |
| ---  | record total | **228B** | | Wire-format complete. |

### A.4 Clarification: chain link hash + record_hash semantics

The CLAUDE.md hard rule states: **"chain link hash = SHA-256(164B body) — body ONLY, NOT 228B."** This is the FULL 32-byte SHA-256, not a truncation.

v1.0 §3.1 erroneously specified `record_hash` as a 16-byte truncation occupying bytes 16-31 of the body. **This was wrong.** The actual semantics:

- **`record_hash`** in codec.py is a DERIVED field, not a body field. After `parse_record()`, `PoACRecord.record_hash` holds the full 32-byte `hashlib.sha256(body).digest()`. It is NOT stored in the wire format.
- **No 16-byte truncation exists** in the live wire format. The "first 16 bytes" claim in v1.0 §3.1 was unsourced.
- **The hash chain** binds record N to record N-1 via `record[N].prev_poac_hash = SHA-256(record[N-1].body[0:164])` — a full 32-byte hash at body offset 0x00.

This v1.1 amendment treats the v1.0 conformance-harness plan (`docs/vbdip-0006-conformance-harness.md` §3.1 vector schema) `record_hash_hex` field as SUPERSEDED by `body_sha256_hex` (full 32 bytes). The conformance harness plan is updated separately in the same commit.

### A.5 Clarification: device identity layer separation

v1.0 §3.1 placed `device_id = keccak256(pubkey)[0:8]` at body bytes 0-7. **This was wrong.**

The reconciliation:

- **`device_id`** is `keccak256(pubkey)` (full 32-byte hash per `codec.py:compute_device_id`). It is NOT embedded in the PoAC body at any offset.
- **Device identity binds at the signing layer**: the bridge derives `device_id` from the verifying public key at signature-check time. The PoAC body itself carries no identity field; the signature + the public key together attest identity.
- **The certificate layer** (`VAPIHardwareCertRegistry` at `0x1031b7840184D6c8f0EA03F051970578C3c874C2`) is where device identity attestation lives: the manufacturer registers the device's pubkey + the cert binds the family to a `profile_hash`. PoAC records flow under that established identity; they do not re-attest it per record.

This division of concerns matches the canonical anchor in `docs/mobile-companion-app.md` §6 ("the phone never holds a key; identity binds at controller SE + cert registry").

### A.6 Clarification: L4 / L5 biometric commitment via hashes

v1.0 §3.1 placed `l4_features` as 13 × IEEE 754 float16 (26B) at bytes 105-117 + `l5_rhythm` as 10B at bytes 118-127. **This was wrong.**

The reconciliation:

- **L4 / L5 features are NOT serialized as raw floats in the PoAC body.** Doing so would expose biometric data on every record (contradicting BP-007 minimization), inflate body size beyond the FROZEN 164B, and require firmware float16 encoding the bridge does not consume.
- **L4 / L5 features are COMMITTED via hash** into the three 32-byte hash fields at body offsets 0x20 (sensor_commitment), 0x40 (model_manifest_hash), 0x60 (world_model_hash). The commitment scheme: SHA-256 over the canonical-JSON projection of the feature vector.
- **L4 / L5 EVIDENCE flows side-band** through the existing `pitl_*` fields on `PoACRecord` (the `pitl_l4_distance`, `pitl_l4_warmed_up`, `pitl_l5_cv`, `pitl_l5_entropy_bits`, etc. fields at `codec.py:101-113`). These are extension fields populated AFTER `parse_record()`; they are NOT part of the 228B wire format.

VBDIP-0006-conformant firmware MUST emit the body without raw L4 / L5 floats. Firmware that wants to communicate L4 / L5 details to the bridge does so via the side-band channel (Phase 50 `agent_events` table or future VBDIP-0006-extension report types), NOT by inlining floats into the FROZEN body.

### A.7 What this means for VBDIP-0006 firmware contract

VBDIP-0006-conformant firmware MUST:

1. Emit body bytes per the A.3 authoritative layout — byte-for-byte identical to what `codec.py:parse_record()` accepts and re-serializes.
2. Sign the 164-byte body with ECDSA-P256 using the device's SE-resident private key (unchanged from v1.0).
3. Register its public key with `VAPIHardwareCertRegistry` for identity attestation (unchanged from v1.0).
4. NOT serialize raw L4 / L5 features into the body; commit them via the appropriate hash field.
5. NOT embed a `device_id` field in the body; identity binds at the signing layer.
6. NOT truncate any hash to 16 bytes in the wire format.

VBDIP-0006-conformant firmware MAY:

- Implement extended side-band reporting (Phase 50 agent_events compatibility) for L4 / L5 / advisory codes.
- Emit hard cheat codes (0x28 DRIVER_INJECT firmware-emitted) as the `inference_result` byte at offset 0x80 when the firmware-side detector fires.

### A.8 What v1.0 §3.1 claims are SUPERSEDED

For audit traceability, the explicit list of v1.0 §3.1 claims this amendment supersedes:

- ❌ `device_id` at body bytes 0-7 → **superseded.** device_id binds at signing/cert layer (A.5)
- ❌ `counter` at body bytes 8-15 (uint64) → **superseded.** Actual field is `monotonic_ctr` (uint32 BE) at offset 0x84
- ❌ `record_hash` at body bytes 16-31 (16B truncation) → **superseded.** No truncation exists; chain hash is full SHA-256 stored at the NEXT record's `prev_poac_hash` (A.4)
- ❌ `timestamp_ms` at body bytes 32-39 → **superseded.** Actual offset is 0x88
- ❌ `prev_record_hash` at body bytes 40-71 → **superseded.** Field exists but at offset 0x00 (named `prev_poac_hash` in codec.py)
- ❌ `sensor_commitment` at body bytes 72-103 → **superseded.** Actual offset is 0x20
- ❌ `inference_code` at body byte 104 → **superseded.** Actual offset is 0x80 (field named `inference_result`)
- ❌ `l4_features` 13 × float16 at bytes 105-117 → **superseded.** L4 features committed via hash, not serialized (A.6)
- ❌ `l5_rhythm` 10B at bytes 118-127 → **superseded.** L5 features committed via hash, not serialized (A.6)
- ❌ `extension_field` 36B reserved at bytes 128-163 → **superseded.** Bytes 0x80-0xA3 contain the live struct-packed fields (`_FIELDS_FMT` `>BBBBIqddI`)

The signature region at bytes 164-227 (64B ECDSA-P256) — the ONLY v1.0 §3.1 claim that matched codec.py — is preserved by this v1.1 amendment.

### A.9 Conformance harness implications

`docs/vbdip-0006-conformance-harness.md` is updated in the same commit to:

- Target the v1.1 authoritative layout per A.3 (not the v1.0 §3.1 table)
- Drop the 13 × float16 L4 features from the vector input schema; replace with `sensor_commitment_hex` (32-byte hash input)
- Drop the L5 rhythm fields from the vector input schema; covered by `sensor_commitment_hex`
- Use `body_sha256_hex` as the single canonical body hash field (no 16-byte truncation field)
- Use `monotonic_ctr` (uint32) not `counter` (uint64)
- Add `action_code`, `confidence`, `battery_pct`, `latitude`, `longitude`, `bounty_id` fields per A.3 layout
- Categories C1-C5 remain (random / edge-case / hard-cheat / GIC chain / counter rollover); allocation 20×5=100 unchanged; counter rollover is now uint32 boundary near `2^32-1` per A.3 reconciliation

The conformance harness plan amendment lands in the SAME COMMIT as this v1.1 spec amendment to maintain atomic consistency between the contract layer and the implementation layer.

### A.10 Versioning + manifest cross-reference

- **v1.0 manifest** at `vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json` — UNCHANGED. Signs the v1.0 file snapshot at commit `1f30057d`. Verification of v1.0 reads `git show 1f30057d:wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md`.
- **v1.1 manifest** at `vsd-vault/manifests/proposals-VBDIP-0006/002.manifest.json` — NEW. Signs the current-commit file (v1.0 §0-11 + Appendix A v1.1 amendment). Verification reads the file at the v1.1 ceremony commit.
- Both manifests coexist. Both verify against the same architect Ed25519 pubkey (`056e695f…8ca8`). Both anchored back to bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` via the shared attestation envelope.
- v1.0 to v1.1 lineage: v1.1 manifest's `supersedes` field references the v1.0 manifest path + canonical hash, making the lineage cryptographically traversable.

### A.11 PV-CI invariant impact

`scripts/vapi_invariant_gate.py` carries `INV-VBDIP-0006-001..004` invariants pinning regions of v1.0 Sections 1, 3, 6, 8. **None of these regions are modified by this v1.1 amendment.** Appendix A is APPENDED to the file; v1.0 content is byte-identical. PV-CI invariants stay green.

INV-VBDIP-0006-002 (which pins v1.0 §3 FROZEN cryptographic primitives) requires special note: it was authored against the v1.0 §3.1 table that A.1 now identifies as erroneous. The invariant TEXT in `vapi_invariant_gate.py` references the regions correctly (the 228-byte total + GIC genesis tag + hard cheat code 0x28); the regex matches succeed against the v1.0 file content (which is unchanged). **The PV-CI invariant remains technically correct** because it pins the FROZEN-region text in v1.0, not the §3.1 byte-offset claims that are corrected by A.3. A future maintenance amendment MAY tighten INV-VBDIP-0006-002 to explicitly include the A.3 layout — deferred to a separate operator-authorized work item.

### A.12 Authoring discipline reaffirmed

This v1.1 amendment follows the §11.2 lifecycle convention verbatim:

- v1.0 spec content byte-identical (lines 1-553)
- Appendix A appended (not interleaved)
- v1.0 manifest unchanged; v1.1 manifest added with cross-reference
- No reformat of v1.0 text; no renumbering of v1.0 sections
- No PV-CI scope additions in this amendment (existing invariants cover the unchanged v1.0 regions; new invariants for A.3 layout deferred to maintenance amendment)
- No new wire-format primitives; the amendment corrects spec drift, it does not introduce new contracts

The v1.0 manifest's `verification_procedure` step 1 ("Read VBDIP-0006 from proposal_path at this commit") is satisfied by git history: any future verifier of v1.0 reads from commit `1f30057d` and gets the byte-identical v1.0 file. The v1.1 manifest's equivalent step reads the file at the v1.1 ceremony commit.

---

*VBDIP-0006 v1.1 Wire-Layout Reconciliation Appendix — VAPI Principal Architect, 2026-05-16*
