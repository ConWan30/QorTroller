# Path A Manufacturing Specification (v1)

**Audience:** controller manufacturers, partner-HSM operators, hardware
integrators who want to ship a DualSense-class controller (or compatible
ECDSA-P256 secure-element-bearing device) that is silicon-rooted in
QorTroller's V.A.P.I. protocol on IoTeX.

**Status:** Path A Arc 1 reference implementation. Arc 2 (`SecureElementBackend`
+ ATECC608A hardware integration) is the implementation-side companion to this
spec and ships when the partner-hardware breakout is connected to the rig.

---

## 1. What Path A v1 Proves

Path A v1 = **silicon-rooted iPACT renewal authenticity.** When a device
asserts Path A, every Verifiable Humanity Proof (VHP) renewal it produces is
cryptographically attestable to a specific ECDSA-P256 private key that lives
in a hardware secure element (ATECC608A or equivalent) and cannot be
extracted from silicon under any conditions documented in the chip's
threat model.

**Path A v1 does NOT yet prove** silicon-rooting of every individual PoAC
record. That is Path A v2 (Arc 3+) — a separate design pass that requires a
secure-element sign-latency study (~3 ms per sign on ATECC608A vs the 1000 Hz
PoAC pipeline; needs buffering architecture) OR a faster signing surface
(e.g. STM32 with onboard ECDSA acceleration).

**Path A v1 reference implementation demonstrated:** QorTroller Foundation
on IoTeX testnet — VAPIManufacturerDeviceRegistry at
`0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0`. Manufacturers deploying their
own registry instance follow the same contract bytecode.

---

## 2. Hardware Requirement

Minimum supported secure element:

| Vendor | Part | ECDSA curve | Locked slots | Notes |
|---|---|---|---|---|
| Microchip | **ATECC608A** | P-256 | 16 | Reference Path A v1 target |
| Microchip | ATECC608B | P-256 | 16 | Drop-in compatible |
| YubiKey | YubiKey 5 (PIV) | P-256 | up to 4 PIV slots | Workable; partner-decision per slot allocation |
| ST | STSAFE-A110 | P-256 | 8 zones | Workable; ECDSA over I2C |

**Mandatory chip properties:**
1. Hardware-bound ECDSA-P256 private key, generated on-chip via
   `atcab_genkey()` (ATECC) or `piv_generate_key()` (YubiKey), with the
   private-key extraction policy locked at provisioning time to "never
   exportable."
2. SHA-256 over the 32-byte digest input to the chip's `sign` operation
   (the chip itself does NOT hash; the host pre-hashes).
3. I2C or USB-HID host interface usable by Linux/Windows host driver.
4. Attestation-certificate readback (optional v1, REQUIRED v2): the chip's
   on-chip attestation cert binding the key slot to the chip serial number.

**Recommended host adapter:** CH341A USB-I2C for development; production
controllers integrate the secure element directly on the controller PCB
with I2C lines wired to the host MCU.

---

## 3. Manufacturing Ceremony

For each device shipped:

### 3.1 Per-chip key generation (one-time, at the factory)

1. Power up the chip. If a key slot is already locked, abort — chip has
   been provisioned previously.
2. Call `atcab_genkey(slot=0, pubkey_out=64B)`. The chip generates a fresh
   P-256 keypair; the private key never leaves silicon.
3. Lock slot 0 (`atcab_lock_data_zone()` after configuring slot 0 to be
   `EXT_SIGN | INT_SIGN` only, no `READ`).
4. Capture the 64-byte uncompressed pubkey (X || Y, no 0x04 prefix). Append
   0x04 for SEC1-uncompressed; compress to 33 bytes using standard
   point-compression (0x02 prefix if Y is even, 0x03 if odd).
5. Read the chip serial number via `atcab_read_serial_number()`. Persist as
   `atecc_chip_id` in the cert.

### 3.2 Cert issuance (one-time, per device, at the factory)

6. Build a `DeviceBirthCertificate` (Section 4) with:
   - `device_id_hex`        — your canonical device serialization (32 bytes hex)
   - `ecdsa_p256_pubkey_hex` — the 33-byte compressed pubkey from step 4
   - `controller_model`      — e.g. `"CFI-ZCP1"`
   - `manufacturer_id`       — your manufacturer identifier
   - `signing_path: "A"`
   - `proof_tier`            — one of `FULL` / `STANDARD` / `BASIC` (Section 5)
   - `atecc_chip_id`         — chip serial from step 5
   - `issuer_pubkey_hex`     — your ManufacturerRootCA P-256 SEC1-uncompressed
                              pubkey (65 bytes / 130 hex chars)
   - `issuer_backend`        — e.g. `"yubikey"` or `"hardware-hsm"` in production
7. Compute the cert canonical bytes: all fields except `signature_hex`,
   JSON-serialized with `sort_keys=True, separators=(",", ":"),
   ensure_ascii=True` (Section 4.2).
8. Sign the canonical bytes with your ManufacturerRootCA HSM. Produce 64-byte
   raw r||s ECDSA-P256 sig. Persist as `signature_hex`.
9. Persist the signed cert to manufacturer records.

### 3.3 On-chain registration (one-time, per device, at the factory)

10. Compute `birthCertHash = SHA-256(canonical_bytes_full(signed_cert))`.
    The `canonical_bytes_full` is the cert WITH the signature field included.
11. Call `VAPIManufacturerDeviceRegistry.registerDevice(deviceId, pubkeyHash,
    controllerModel, signingPath, proofTier, birthCertHash)` from your
    manufacturer-HSM wallet (which MUST be the registry contract's `owner()`).
    Gas: ~870k. Cost on IoTeX testnet: ~0.87 IOTX.
12. Ship the device. Include the signed cert JSON file as a factory artifact
    delivered to the host's local storage (`~/.vapi/device_birth_cert.json`)
    OR retrievable via a manufacturer key-recovery URL.

---

## 4. DeviceBirthCertificate Format

### 4.1 Fields (cert version 1.0)

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | string | yes | `"1.0"` |
| `device_id_hex` | string | yes | 32 bytes as 64 hex chars |
| `ecdsa_p256_pubkey_hex` | string | yes | 33 bytes compressed SEC1, 66 hex chars |
| `controller_model` | string | yes | `"CFI-ZCP1"` / `"CFI-ZCT1"` / etc. |
| `manufacturer_id` | string | yes | e.g. `"QorTrollerFoundation"`, `"YourBrandHardwareCA"` |
| `manufacturing_date` | string | yes | ISO 8601 |
| `signing_path` | `"A"` \| `"B"` | yes | `"A"` for silicon-rooted Path A devices |
| `proof_tier` | `"FULL"` \| `"STANDARD"` \| `"BASIC"` | yes | Section 5 |
| `issuer_pubkey_hex` | string | yes | ManufacturerRootCA SEC1-uncompressed pubkey, 130 hex chars |
| `atecc_chip_id` | string \| null | optional | Chip serial. Required for `signing_path: "A"`. null for `"B"`. |
| `issuer_backend` | string \| null | optional | Provenance: `"software"` (reference), `"atecc608"`, `"yubikey"`, `"hsm"`. |
| `signature_hex` | string | yes | 64-byte raw r\|\|s ECDSA-P256 sig, 128 hex chars |

### 4.2 Canonical-bytes derivation (FROZEN)

```
canonical_bytes_for_signing(cert) =
    UTF-8 encoding of:
        json.dumps(
            {field: value for field, value in cert.items() if value is not None and field != "signature_hex"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True
        )
```

`canonical_bytes_full(cert)` is identical except it INCLUDES `signature_hex`.

**Stability guarantees:**
- `sort_keys=True` — field order canonical regardless of source language's dict ordering
- `separators=(",", ":")` — no whitespace within the JSON
- `ensure_ascii=True` — non-ASCII manufacturer IDs are escaped (`\u####`)
- Null-valued optional fields are dropped (so a future cert format adding an
  optional field doesn't change the hash relative to omitting it)

### 4.3 birthCertHash binding

```
birthCertHash = SHA-256(canonical_bytes_full(signed_cert))
```

Anchored on-chain in `VAPIManufacturerDeviceRegistry.registerDevice`. A
tournament operator running `verify_device_cert.py` re-derives this hash
from the cert JSON and compares it to the on-chain value. Any cert
tampering breaks the match.

---

## 5. Proof Tier Assignment

| Tier | Constant | Hardware requirements |
|---|---|---|
| **FULL** | `PROOF_TIER_FULL = 1` | Adaptive triggers + ≥ 1000 Hz USB polling + 3-axis IMU (gyro + accel). DualSense Edge CFI-ZCP1 is the reference. |
| **STANDARD** | `PROOF_TIER_STANDARD = 2` | Adaptive triggers (any degree) + ≥ 800 Hz polling. DualSense CFI-ZCT1 qualifies. |
| **BASIC** | `PROOF_TIER_BASIC = 3` | Below STANDARD. Eligible for partial protocol features only. Third-party / generic gamepads default here. |

These constants are FROZEN at v1; pinned by `INV-MFG-001` and `INV-MFG-002`
in `scripts/vapi_invariant_gate.py`. Adding a new tier requires a v2 of this
spec + a registry contract redeploy.

---

## 6. On-Chain Registration Procedure

### 6.1 Contract ABI (write surface — `registerDevice`)

```solidity
function registerDevice(
    bytes32 deviceId,
    bytes32 pubkeyHash,       // sha256(compressed_ecdsa_p256_pubkey)
    bytes32 controllerModel,  // keccak256(utf8(model_string))
    uint8   signingPath,      // 1 = Path A, 2 = Path B
    uint8   proofTier,        // 1 / 2 / 3
    bytes32 birthCertHash     // sha256(canonical_bytes_full(cert))
) external onlyOwner nonReentrant;
```

**Caller:** must be the registry contract's `owner()`. For QorTroller's
reference deploy, owner is the bridge wallet
`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`. Partner deploys redeploy with
their manufacturer-HSM wallet as `initialOwner`.

### 6.2 Anti-replay

`deviceId` may be registered at most ONCE. To replace a device's
registration (e.g. after a security-relevant chip incident), call
`revokeDevice(deviceId)` then register under a NEW `deviceId`. The
historical record is preserved on-chain for forensic audit.

### 6.3 Reference deploy

| Property | Value |
|---|---|
| Network | IoTeX testnet (chainId 4690) |
| Address | `0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0` |
| Owner | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` (QorTroller Foundation) |
| Deploy tx | `0x07efc58a0b5b34fa3805d30aa45538c137d8059cc0c4b800c052703cacbb66a9` |
| Block | 44019764 |

Partner manufacturers redeploy with their own `initialOwner`; the bytecode
is open in `contracts/contracts/VAPIManufacturerDeviceRegistry.sol`.

---

## 7. Verification

### 7.1 `verify_device_cert.py` — audit tool

```bash
python scripts/verify_device_cert.py
# or with explicit cert path:
python scripts/verify_device_cert.py --cert-path /path/to/cert.json
```

Performs three checks:
1. ECDSA-P256 sig verifies against the cert's `issuer_pubkey_hex`
2. `SHA-256(canonical_bytes_full)` matches on-chain `birthCertHash`
3. `VAPIManufacturerDeviceRegistry.isActive(deviceId)` is `true`

Exit codes: `0 = VALID`, `1 = INVALID`, `2 = NOT_REGISTERED`, `3 = ERROR`.
Use `--offline` to skip steps 2-3 (cert-format + sig only).

### 7.2 `VAPIProtocolLens_v2.isFullyEligible_PathA(deviceId)` — composable gate

(Ships with Path A Arc 1 Commit 4. Returns `true` iff a device is fully
eligible per VAPI protocol gates AND registered as Path A AND active in
the manufacturer registry. Single eth_call for tournament integrations.)

---

## 8. Contact + Partnership Track

QorTroller Foundation invites partner manufacturer integrations. The
partnership track aligns with IoTeX's IIP-64 PQ migration design-partner
program (Xinxin Fan, IoTeX core team). Contact:

- IIP-64 design-partner channel: github.com/iotexproject/iips/pull/72
- QorTroller protocol issues: github.com/ConWan30/QorTroller/issues

A production-grade ceremony involves:
1. Hardware HSM for the ManufacturerRootCA (replacing the reference impl's
   `SoftwareIdentityBackend` plaintext-key file).
2. Per-batch slot-configuration audit (chip slot 0 locked `INT_SIGN | EXT_SIGN`
   only, no `READ`).
3. Per-device cert + on-chain registration in a single attestable batch
   transaction.
4. Cert delivery channel from manufacturer to gamer's host (factory-provisioned
   file OR signed cert-recovery URL).

> **Reference-implementation honesty stamp:** the Arc 1 deploy uses
> `SoftwareIdentityBackend` (plaintext-key file at
> `~/.vapi/qortroller_foundation_mfg_ca.json`) as the ManufacturerRootCA. This
> is DEV-grade key custody. Production partner ceremonies MUST replace this
> with a hardware-HSM-rooted P-256 key. The cert format and on-chain schema are
> production-grade; only the signing-authority custody is reference-grade until
> a partner-HSM ceremony is conducted.
