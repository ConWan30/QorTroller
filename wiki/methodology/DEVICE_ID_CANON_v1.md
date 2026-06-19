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

---

## 2. Four-way consensus record (pre-canon verification)

Arbitration date: 2026-06-18. Method: read implementations + re-derive golden vector from operator machine key material (not committed).

| Layer | File | Behavior |
|-------|------|----------|
| Bridge codec | `bridge/vapi_bridge/codec.py::compute_device_id` | `keccak(pubkey_bytes)`; docstring requires 65-byte uncompressed SEC1 |
| On-chain | `contracts/contracts/DeviceRegistry.sol::computeDeviceId` | `keccak256(_pubkey)`; header documents `0x04 ‖ x ‖ y` (65 bytes) |
| Controller | `controller/persistent_identity.py` | `_keccak256(self._public_bytes)` on 65-byte uncompressed key |
| Tests | `bridge/tests/test_codec.py::_generate_keypair` | `Encoding.X962` + `PublicFormat.UncompressedPoint` → 65 bytes |
| Live demo | MFG-registered device `581a836c…` | Matches **65-byte-with-prefix** preimage only |

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

## Reproduction commands

```bash
# After commit 2 fixture lands:
python -m pytest bridge/tests/test_device_id_canon.py -q

# F-FW-2 health probe (expect 0 CRITICAL post-canon adjudication):
python scripts/daemon_health_runner.py
```
