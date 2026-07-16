# Path A — Manufacturer Root CA → AWS KMS HSM migration

**Status: CAPABILITY BUILT, DEFAULT OFF. The live flip is an operator ceremony — nothing in code flips it.**

## Why

The QorTroller Foundation Manufacturer Root CA signs Path A `DeviceBirthCertificate`s. Today its private
key is a **single-copy, plaintext P-256 key file** (`SoftwareIdentityBackend`, which warns
`INSECURE/DEV ONLY` on every use). That single copy on one machine is the protocol's longest-standing
CRITICAL finding — **F-DECON-3.2** (single-point-of-failure CA), **OA-1**/**OA-4** (backup / HSM-root
actions), and **Sensor-C G1.6 = LIVE-FRAGILE**.

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

## Operator ceremony (to actually flip)

1. **Provision** an AWS KMS key `KeySpec=ECC_NIST_P256`, `KeyUsage=SIGN_VERIFY`; create alias
   `VAPI_KMS_MFG_CA_ALIAS`; scope IAM to `kms:Sign`/`kms:Verify`/`kms:GetPublicKey` on **that alias only**.
   Do **not** grant the Guardian/Sentry principals Sign on it (trust domains stay separate).
2. Keep `MFG_CA_BACKEND=software` while provisioning + testing.
3. **Re-issue** the `DeviceBirthCertificate` for each active device under the new KMS issuer
   (`provision_device_mfg.py`), i.e. re-sign the birth cert with the KMS CA.
4. **Re-anchor** on-chain if the VMDR binds `birthCertHash` (re-`registerDevice` for the affected devices).
5. **Only then** set `MFG_CA_BACKEND=kms` + `VAPI_KMS_MFG_CA_ALIAS` in `bridge/.env`.
6. **Retire** the software key: archive offline or destroy per policy — do **not** leave two live signers
   without a written policy (that is a new fragility, not a fix).

## Only after the real flip

- Demote **Sensor-C G1.6** `LIVE-FRAGILE → LIVE` and close **F-DECON-3.2** at root (this pass builds the
  capability; it does **not** demote G1.6 — capability ≠ root fix).

## Verification (built)

`bridge/tests/test_kms_identity_backend.py` pins: single-SHA-256-then-DIGEST contract (with a double-hash
negative that fails verify), 64-byte sig / 65-byte `0x04‖X‖Y` pubkey wire shapes, end-to-end
`verify_cert_signature` through both `create_backend("kms")` and `ManufacturerRootCA(backend=…)`, wrong-curve
fail-closed, and default-stays-`software`. `PV-CI 183`. No live AWS call, no chain write, no key provisioned.

Design consult: `docs/a2a/hsm/round-13-grok-design-hsm.txt`.
