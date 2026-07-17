# DEVICE_ID_CANON v1

**Document ID:** DEVICE-ID-CANON-v1  
**Status:** Canonical identity anchor (F-FW-2 adjudication)  
**Supersedes:** `SHA-256(pubkey ‖ serial)` firmware formula, `"atecc-" + serial` Arc 2 draft, opaque CLI `--device-id` without pubkey derivation  
**Companion:** [`VBDIP-0006-vapi-firmware-reference-implementation.md`](VBDIP-0006-vapi-firmware-reference-implementation.md) §A.5 (signing-layer binding; no `device_id` in PoAC body)

---

## TL;DR

`device_id` is a **32-byte `bytes32`**:

```
device_id = keccak256(P)     where P = 65-byte uncompressed SEC1 ECDSA-P256 public key
P         = 0x04 ‖ X ‖ Y       X and Y are 32-byte big-endian field elements
```

**Four-way consensus** already agrees on this encoding in bridge, on-chain registry, controller identity, and the live demo device. The canon **documents** settled truth; it does not invent a new formula.

**Scope (mint/verify split — F-PATHA-1 / A2A round-26, 2026-07-16):** the canon is the
**MINT-only** gate — it governs how NEW device_ids are derived at registration ceremonies
(`assert_mint_device_id_canon` / `resolve_device_id_hex`). It is **not** the verify gate for a
device already registered on VMDR: there the authoritative binding is the **on-chain
`pubkeyHash`** (`sha256(compressed cert pubkey)` == `devices[deviceId].pubkeyHash`) via
`verify_registered_device_binding`. Slogan: **canon for minting, chain-binding for verifying.**
See §8.

**Computation site (F-KEY-1):** ESP32 software or manufacturing provisioning computes `device_id` from the **exported** P-256 public key. The ATECC608 secure element **signs** PoAC records; it does **not** derive `device_id` in silicon. Recommended: precompute at ceremony → store 32 bytes in an ATECC data slot → firmware reads slot for display/registration only.

---

## 1. Preimage specification (F-KEY-2)

| Field | Value |
|-------|--------|
| Curve | NIST P-256 (SECP256R1) |
| Encoding | SEC1 uncompressed point |
| Total length | **65 bytes** |
| Byte 0 | **`0x04`** prefix (**included** in hash — not stripped) |
| Bytes 1–32 | **X** coordinate, big-endian |
| Bytes 33–64 | **Y** coordinate, big-endian |
| Hash | `keccak256(P)` → 32-byte `device_id` |

**Explicit non-canonical encodings (do not use for `device_id`):**

- 64-byte preimage with `0x04` stripped (Ethereum address-style) — produces a **different** `device_id`
- `SHA-256(pubkey ‖ serial)` — firmware drift; superseded
- `"atecc-" + serial` string — Arc 2 draft; superseded
- Opaque `bytes32` from CLI without pubkey derivation — ceremony anti-pattern

### Golden vector (public artifact)

Demo device (Path B reference DualShock Edge, MFG registry + live sessions):

```
keccak256(0x04 ‖ X ‖ Y)  →  581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8
```

The **65-byte public key** preimage for this derivation is **not** embedded in this document. Reproduce via the committed test fixture introduced in Phase 0 commit 2 (`bridge/tests/fixtures/device_id_canon_demo.json` — pubkey hex + expected `device_id` only, no private material). This doc cites the **result**; the fixture holds the **preimage** for CI and auditors.

**Drift correction (F-PATHA-1, 2026-07-16):** the fixture pubkey (`042adcdb…`) is the keccak
**preimage** of `581a836c` (the controller-identity key) — but it is **NOT** the
`ecdsa_p256_pubkey_hex` inside the registered DeviceBirthCertificate. The cert binds the
composite host key (`02997c…`), and the live VMDR bind is
`(device_id=581a836c, pubkeyHash=sha256(compressed 02997c…)=235a2c04…)`. The 2026-05-27
registration predates this canon (`f778e1fd`, 2026-06-18), so cert-pubkey ≡ id-preimage was
never enforced — and for this device is not true. Consequence: `581a836c` **cannot** be
validated by re-deriving the cert pubkey locally; it is validated by the **on-chain
pubkeyHash binding** (§8). Do not read "live demo = 581a836c under this preimage" as "the
registered cert's pubkey derives 581a836c" — that was the doc drift.

---

## 2. Four-way consensus record (pre-canon verification)

Arbitration date: 2026-06-18. Method: read implementations + re-derive golden vector from operator machine key material (not committed).

| Layer | File | Behavior |
|-------|------|----------|
| Bridge codec | `bridge/vapi_bridge/codec.py::compute_device_id` | `keccak(pubkey_bytes)`; docstring requires 65-byte uncompressed SEC1 |
| On-chain | `contracts/contracts/DeviceRegistry.sol::computeDeviceId` | `keccak256(_pubkey)`; header documents `0x04 ‖ x ‖ y` (65 bytes) |
| Controller | `controller/persistent_identity.py` | `_keccak256(self._public_bytes)` on 65-byte uncompressed key |
| Tests | `bridge/tests/test_codec.py::_generate_keypair` | `Encoding.X962` + `PublicFormat.UncompressedPoint` → 65 bytes |
| Live demo | MFG-registered device `581a836c…` | Fixture (identity-key) preimage matches 65-byte-with-prefix encoding only; the **registered cert** binds a different key — see §1 drift correction + §8 (chain-binding verifies it) |

**Re-derivation check:** 64-byte stripped preimage yields `c8fa05a3…` — does **not** match the deployed demo registration.

---

## 3. Lone outlier (supersession target)

| File | Drift | Resolution phase |
|------|-------|------------------|
| `bridge/firmware/joypad-os/src/qortroller/atca_signer.c` | `SHA-256(pubkey_64B ‖ serial_9B)` | Phase 1B — replace with F-KEY-1 slot-read + provisioning-time keccak |
| `docs/path-a-arc2-prompt.md` (draft) | `"atecc-" + serial` string id | Phase 1B — cite this canon |

No other layer presents an alternate **canonical** formula. F-FW-2 post-adjudication: CRITICAL fires on **canonical-layer** drift (bridge/chain/controller), not on firmware files listed here while this document is present.

---

## 4. F-KEY-1 — Computation residency

| Role | Responsibility |
|------|----------------|
| **ATECC608B/C** | Generate/ hold P-256 key; **sign** 164-byte PoAC body; export public key bytes for provisioning |
| **ESP32 / host provisioning** | Export pubkey → compute `keccak256(65B P)` → write 32B to ATECC data slot (recommended) |
| **Bridge / manufacturing** | Verify slot or exported pubkey matches `codec.compute_device_id()` at ceremony and first connect |
| **Forbidden** | Claiming ATECC608 computes `device_id` via on-chip SHA over pubkey‖serial |

---

## 5. PoAC wire boundary (orthogonal)

- **228-byte PoAC** = 164-byte signed body + 64-byte ECDSA-P256 signature (FROZEN)
- **Chain link hash** = `SHA-256(raw[0:164])` — body only
- **`device_id` is not embedded in the PoAC body** — identity binds at the **signing layer** (pubkey → `device_id` at verify/register time). See VBDIP §A.5.

---

## 6. Standing external dependencies

| ID | Dependency | Notes |
|----|------------|-------|
| **D-IOID-P256** | ioID EIP-712 permit expects **secp256k1** device signer; controller silicon is **P-256** | Option C (silicon-native permit) blocked pending IoTeX coordination — parallel track to **IIP-64** (on-chain P256 verify for PoAC, not ioID permit) |
| **D-CONTROLLER-IOID-1** | **Option A (LOCKED):** gamer wallet signs ioID permit; bridge read-only orchestrator | Silicon P256 linked via MFG registry + birth cert until D-IOID-P256 resolves |

---

## 7. Enforcement

- **F-FW-2 probe** (`bridge/vapi_bridge/daemon_health_monitor.py` + `scripts/daemon_health_runner.py`): canon-aware; see probe module docstring
- **Phase 0 commit 2:** `bridge/tests/test_device_id_canon.py` + `bridge/tests/fixtures/device_id_canon_demo.json` pin golden vector
- **PV-CI:** future `INV-DEVICE-ID-001` ceremony (out of scope for commit 1)

---

## 8. Mint vs verify split (F-PATHA-1 / A2A round-26, 2026-07-16)

The canon is the **mint** rule, not the **verify** rule for registered devices. The
manufacturer's attestation is the on-chain `registerDevice` bind — local re-derivation of
`device_id` from the cert pubkey after registration is what produced F-PATHA-1-class drift.

| Mode | Binding rule |
|------|--------------|
| Chain reachable + `registered[device_id]` | **Authoritative:** `sha256(compressed cert pubkey) == devices[device_id].pubkeyHash` (chain wins BOTH directions — a match grandfathers a pre-canon id; a mismatch fails even a canon-consistent pair) |
| Offline / unregistered | **Best-effort mint-shape:** `device_id == keccak256(65B uncompressed pubkey)` per this canon |
| Offline + known pre-canon registered device | Honest **INVALID-OFFLINE** — never `canon OR skip` |

API surfaces (`bridge/vapi_bridge/device_birth_cert.py`):

- `assert_mint_device_id_canon` / `resolve_device_id_hex` — **mint/registration only**, fail-closed canon.
- `verify_registered_device_binding` — chain-first precedence verify (rules above). **Trust boundary
  (round-27 F1):** `on_chain_pubkey_hash_hex` MUST be the RPC-fetched `devices[deviceId].pubkeyHash`
  for that id — never `sha256` of the cert/local key (circular; grandfathers any id). Pass `None` when
  you have no chain evidence.
- `verify_cert(cert, on_chain_pubkey_hash_hex=…)` — default `None` = offline canon best-effort; with the VMDR `pubkeyHash` supplied the binding is the authoritative chain check.
- Re-issue of an existing registration: `scripts/provision_device_mfg.py --reissue <id>` — same `device_id` + same key + new issuer/sig/hash, fail-closed gated on the on-chain `pubkeyHash` match (never mints, never broadcasts `registerDevice`).

Enforced by `bridge/tests/test_device_binding_split.py` (T-BIND-1..12, incl. the live-device
grandfather pin). Finding record: `audits/F-PATHA-1-device-id-canon-drift-2026-07-16.md`;
consult transcript: `docs/a2a/hsm/round-26-grok-consult-canon.txt`.

---

## Reproduction commands

```bash
# After commit 2 fixture lands:
python -m pytest bridge/tests/test_device_id_canon.py -q

# F-FW-2 health probe (expect 0 CRITICAL post-canon adjudication):
python scripts/daemon_health_runner.py
```
