# Path A — Manufacturer Root CA → AWS KMS HSM migration

**Status: FIRED 2026-07-16/17 (operator ceremony). The HSM CA is live (`MFG_CA_BACKEND=kms`); the live
device re-anchored and verifies VALID under it; F-DECON-3.2 is closed at root. The code DEFAULT remains
`software` for rollback — nothing in code auto-flips; the flip was, and any future one is, an operator
ceremony.** This doc is retained as the migration runbook + the historical record of the flip.

## Why (this was the pre-flip posture — now resolved)

The QorTroller Foundation Manufacturer Root CA signs Path A `DeviceBirthCertificate`s. Before the flip its
private key **was** a **single-copy, plaintext P-256 key file** (`SoftwareIdentityBackend`, which warns
`INSECURE/DEV ONLY` on every use). That single copy on one machine **was** the protocol's longest-standing
CRITICAL finding — **F-DECON-3.2** (single-point-of-failure CA), **OA-1**/**OA-4** (backup / HSM-root
actions), and **Sensor-C G1.6 = LIVE-FRAGILE**. **All of that is now discharged** (see §After the real flip
+ the retention graduation below): the CA is a non-exportable HSM key, G1.6 is **LIVE**, OA-4 is **done**,
and OA-1 is **moot**. The remaining standing item is OA-3 (AWS IAM least-privilege scope-down).

Moving the CA key into an **AWS KMS HSM** makes it **non-exportable**: the bridge can request a signature,
it can never read the key. This reuses the exact HSM mechanism the Sentry/Guardian operator agents already
use — on a **separate** key.

## What was built (this pass)

- `hardware_identity.KMSIdentityBackend` — a `SigningBackend` (P-256) that signs via an injectable sync KMS
  port and returns the ABC's 64-byte raw `r‖s` wire shape. **Load-bearing contract:** the body is
  SHA-256'd **exactly once** and signed in KMS `DIGEST` mode (the software backend hashes internally; KMS
  wants a 32-byte prehash — never double-hash, never pass the raw body as a digest).
- Pure converters `_der_sig_to_raw_rs` (DER → raw `r‖s`) and `_spki_to_uncompressed_p256`
  (DER SPKI → 65-byte uncompressed; **fails closed** on a non-P-256 key).
- `create_backend("kms", …)` + `make_kms_ca_port(alias, region)` (real boto3 sync port).
- `ManufacturerRootCA` selects its backend: **`MFG_CA_BACKEND` env, default `software` (byte-identical to
  before)**; `kms` requires `VAPI_KMS_MFG_CA_ALIAS`.

## The migration reality (READ THIS)

**Flipping to KMS is NOT a transparent swap — it is a CA migration.** A KMS key mints a **new issuer
public key**, i.e. a **new root**. Consequences:

- The one device registered to date (`581a836c…`, signed by the current software CA, on-chain in the VMDR)
  will **not** verify against the new KMS root.
- Path A treats the issuer as a **certificate field** (`issuer_pubkey_hex`), not a global frozen root — so
  **old certs stay valid against the old issuer pubkey stored on them**. The migration is additive at the
  cert level, but any consumer that pins a single expected root must be updated.
- No **dual-root** support is built this pass (multi-root PKI — trust store, which-root-mints-what,
  deprecation windows, VMDR dual-issuer semantics — is a separate product decision, not justified by a
  one-device inventory).

**`MFG_CA_BACKEND=kms` must not be set until the ceremony below is complete.**

## THE RE-ANCHOR BLOCKER (read before ceremony day — grok round-22)

The round-13 draft of this doc said "re-`registerDevice` for the affected devices." **That is false against
the deployed contract.** `VAPIManufacturerDeviceRegistry.registerDevice` is **ONE-SHOT**:

```solidity
require(!registered[deviceId], "VMDR: already registered");   // line 105
// revokeDevice only sets active=false; registered[deviceId] stays true forever
// there is NO updateBirthCertHash function
```

So the one live device `581a836c…` (software-anchored) **cannot be re-anchored to a new root**. A
`provision_device_mfg.py --execute` against it would **revert and waste gas**. Two consequences:

1. A KMS-issued cert produces a **different** `birthCertHash`; with the old hash still on chain,
   `verify_device_cert` returns **INVALID (birthCertHash mismatch)** for `581a836c` even though the KMS
   signature is perfect. **The anchor cannot move** — this is a contract limit, not a KMS bug.
2. Therefore the flip is only *fully* real for the existing device under **Path A** below.

**Pick a path (operator decision):**

| Path | What it means | Cost |
|---|---|---|
| **A — add an update path** | Add `updateBirthCertHash(deviceId, newHash)` `onlyOwner` (+ event) to VMDR, deploy it, then operator-fire the re-anchor. Fully closes F-DECON-3.2 at root for `581a836c`; earns the G1.6 demotion. | Solidity change + a deploy (a separate chain ceremony) |
| **B — net-new only (honest v0)** | Use the KMS CA for **net-new** devices only; `581a836c` **stays software-anchored** on chain forever (its old cert stays VALID against the old issuer). Flip is partial. **F-DECON-3.2 is NOT closed** for the existing device; **G1.6 is NOT demoted**. | 0 chain change |
| **C — new VMDR + Lens rewire** | Out of scope. | Too big |

## Operator ceremony (to actually flip)

1. **Provision** an AWS KMS key `KeySpec=ECC_NIST_P256`, `KeyUsage=SIGN_VERIFY`; create alias
   `VAPI_KMS_MFG_CA_ALIAS`; scope IAM to `kms:Sign`/`kms:Verify`/`kms:GetPublicKey` on **that alias only**.
   Do **not** grant the Guardian/Sentry principals Sign on it (trust domains stay separate).

   ```bash
   aws kms create-key --key-spec ECC_NIST_P256 --key-usage SIGN_VERIFY \
     --description "QorTroller Foundation Manufacturer Root CA"
   aws kms create-alias --alias-name alias/qortroller-mfg-ca --target-key-id <keyId>
   # IAM policy (attach to the operator/CA principal ONLY — never Guardian/Sentry):
   # { "Effect":"Allow", "Action":["kms:Sign","kms:Verify","kms:GetPublicKey"],
   #   "Resource":"arn:aws:kms:us-east-1:<acct>:key/<keyId>" }
   ```

2. Keep `MFG_CA_BACKEND=software` while provisioning.
3. **PREFLIGHT (no spend, no chain)** — prove the KMS CA is usable before anything irreversible:
   ```bash
   MFG_CA_BACKEND=kms VAPI_KMS_MFG_CA_ALIAS=alias/qortroller-mfg-ca AWS_REGION=us-east-1 \
     python scripts/mfg_ca_hsm_preflight.py     # exit 0 = READY (P-256 / canary / full-cert / describe_key / new-root)
   ```
4. **Re-issue (read-only chain gate, no spend)** the cert for the EXISTING registered id under the KMS
   issuer — `--reissue`, NOT `--dry-run` (a plain dry-run canon-derives `20b37e1c` from the composite key,
   not the registered `581a836c` — F-PATHA-1; the mint/verify split makes the on-chain pubkeyHash the
   authoritative binding, see `wiki/methodology/DEVICE_ID_CANON_v1.md` §8):
   ```bash
   MFG_CA_BACKEND=kms VAPI_KMS_MFG_CA_ALIAS=alias/qortroller-mfg-ca \
     python scripts/provision_device_mfg.py \
       --reissue 581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8 \
       --controller-model CFI-ZCP1 --signing-path B --proof-tier FULL
   # fail-closed gate: registered + active + on-chain pubkeyHash == local key; NEVER broadcasts.
   # cert lands at ~/.vapi/device_birth_cert_reissue.json (registered software cert untouched).
   ```
5. **Re-anchor** — **only under Path A** (after deploying `updateBirthCertHash`); operator-fired, estimate-first.
   Under **Path B this step does not exist** — `581a836c` stays software-anchored; only net-new devices use
   `--execute` (their first registration is allowed by the one-shot rule).
6. **Only then** set `MFG_CA_BACKEND=kms` + `VAPI_KMS_MFG_CA_ALIAS` in `bridge/.env`.

## Rollback + key retention (load-bearing)

- **Rollback:** set `MFG_CA_BACKEND=software` (or unset) — the flip-back. This is why the software key is
  retained (cold), not destroyed: emergency rollback + emergency re-sign still need it.
- **Retention — GRADUATED 2026-07-17 (condition met).** The original destroy-gate was: do NOT destroy the
  software CA key until, for every device you care about, EITHER the on-chain hash matches a KMS-issued cert
  AND `verify_device_cert` → **VALID**, OR there is a written write-off policy. That condition is now **MET
  for the only live device** — `581a836c` re-anchored under the HSM root and reads **VALID** (2026-07-16/17,
  Path A fired). So the software key graduates from *"MUST retain, condition unmet"* to **"cold-retain as a
  forensic archive; never a second live signer; destroy only under an explicit written write-off policy."**
  `MFG_CA_BACKEND=kms` is live; the software-signed cert is INVALID-superseded on-chain (the override wins).
  Do not delete the key just because the condition is met — rollback still depends on it.

## After the real flip (Path A on-chain proof) — ✅ DONE 2026-07-16/17

- **Sensor-C G1.6 demoted `LIVE-FRAGILE → LIVE` and F-DECON-3.2 closed at root** (commit `bb11a0bb`). The
  authoritative root for the live device is now the HSM and `verify_device_cert` → **VALID** under it; the
  demote is evidence-driven (two-part: INV-MFG-003 sealed + override registry deployed), so reverting either
  artifact re-demotes honestly. This was the Path-A-only outcome — Path B never earned it (capability ≠ root
  fix). See `audits/mfg-ca-hsm-readiness-and-path-a-2026-07-16.md` Part 3.

## Verification (built)

- `bridge/tests/test_kms_identity_backend.py` — the KMS backend wire contract (single-SHA-256-then-DIGEST,
  64B/65B shapes, verify through `create_backend("kms")` + `ManufacturerRootCA(backend=…)`, wrong-curve
  fail-closed, default-stays-`software`).
- `bridge/tests/test_mfg_ca_readiness.py` — the preflight go/no-go (software + KMS-fake CA ready; wrong
  KeySpec / disabled / not-a-new-root fail-closed; note flags the VMDR one-shot blocker).

**Status 2026-07-17: the migration is FIRED.** HSM CA live (issuer `04d2636c…`), override registry deployed
(`0x31030C8F…`), `581a836c` re-anchored (tx `0x9f282157…`) + VALID, `INV-MFG-003` governance-sealed
(**PV-CI 184**), G1.6 demoted. 0.687 IOTX measured. Design consults `docs/a2a/hsm/round-13-grok-design-hsm.txt`
(capability) + `round-22-grok-design-mfgflip.txt` (flip tooling); F-PATHA-1 mint/verify split `round-26/27`;
ceremony record `audits/mfg-ca-hsm-readiness-and-path-a-2026-07-16.md`.
