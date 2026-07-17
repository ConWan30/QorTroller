# MFG Root CA → HSM: readiness PROVEN + Path A re-anchor tooling — 2026-07-16

## Part 1 — HSM CA readiness PROVEN (live, no spend)

The operator provisioned a real AWS KMS P-256 key and the no-spend preflight passed against it:

- Key: alias `qortroller-mfg-ca`, ARN `…key/3c7098fa-204d-4cca-8221-30ad335e2bb1`, `us-east-1`, Enabled,
  `KeyUsage=SIGN_VERIFY`, `KeySpec=ECC_NIST_P256`.
- `scripts/mfg_ca_hsm_preflight.py` → **READY: True**. All hard checks green: `is_p256_65b`,
  `canary_verifies`, `full_cert_verifies` (a full DeviceBirthCertificate signed by the KMS CA passed
  production `verify_cert`, incl. the DEVICE_ID_CANON keccak binding), `key_enabled`, `key_usage_ok`,
  `key_spec_ok`, `is_new_root`.
- **New HSM issuer pubkey (public, not secret):** `04d2636cbce595ab9d0acff76f0dfb7058…` (65-byte P-256),
  genuinely a NEW root — differs from the software CA.
- No IOTX spent, no chain write, no key material left the HSM (non-exportable). The `vapi-bridge` IAM user
  can Sign/GetPublicKey on the key; `kms:CreateKey` was correctly DENIED to it (least-privilege) — the key
  was created via the Console under an admin identity.

This closes the **root half** of F-DECON-3.2: a non-exportable HSM key provably issues valid device certs.

## Part 2 — Path A re-anchor tooling (built; operator fires the deploy + spend)

The one live device `581a836c` is anchored on the immutable one-shot VMDR (`0x2e5B5FB1…`) under its old
software-signed `birthCertHash`. VMDR cannot be updated in place (grok round-22/24). Path A closes the
**device half** via a companion OVERRIDE (grok round-24 — no VMDR redeploy, no Lens migration):

- **`contracts/contracts/VAPIDeviceBirthCertUpdateRegistry.sol`** (Ownable): owner-vouched
  `setUpdatedBirthCertHash(deviceId, newHash)` (requires the device active on VMDR, non-zero, no-op
  rejected) / `clearOverride` (honest rollback) / `currentBirthCertHash` = OVERRIDE-then-VMDR (the single
  effective-hash view verifiers read) + `BirthCertHashUpdated`/`Cleared` events. Same `onlyOwner`
  Foundation trust as `VMDR.registerDevice` — a second hash write path, NOT a new trust principal.
- **10/10 Hardhat tests** (`test/VAPIDeviceBirthCertUpdateRegistry.test.js`): active-gate + precedence +
  guards + events + revoke-after-override-is-inert (isActive stays the eligibility gate).
- **Deploy** `scripts/deploy-device-birthcert-update-registry.js` (estimate-first, triple-gated:
  deployer==bridge wallet + hard-cap 0.5 IOTX + 2× balance guard; broadcast iff `VAPI_DBC_DEPLOY_CONFIRM=1`).
- **Re-anchor** `scripts/set-updated-birth-cert-hash.js` (estimate-first + pre-send revert guard; broadcast
  iff `VAPI_DBC_SET_CONFIRM=1`).
- **Verify** `scripts/verify_device_cert.py` now reads `currentBirthCertHash` (override-then-VMDR) when
  `BIRTH_CERT_UPDATE_REGISTRY_ADDRESS` is set; env unset → legacy VMDR-only (fail-open). **env SET +
  override read fail → ERROR exit 3 (fail-CLOSED)** — never fall back to the raw VMDR hash once the
  registry is wired (would silently re-accept a software cert after HSM re-anchor).

### Operator ceremony (fires the AWS-already-done + the chain steps)
> **Amended 2026-07-16 (F-PATHA-1 resolution):** step 2 MUST use `--reissue` — a plain `--dry-run`
> canon-derives `20b37e1c` (the composite key's keccak), NOT the registered `581a836c`. The mint/verify
> split (`DEVICE_ID_CANON_v1.md` §8) made the chain binding authoritative, so this override re-anchor is
> now SUFFICIENT for 581a836c. (Pre-split it was necessary-but-not-sufficient — F-PATHA-1.)
1. ✅ Provision KMS key + preflight READY (done — Part 1).
2. Re-issue the cert for the EXISTING id under KMS (fail-closed chain-gated on the on-chain pubkeyHash):
   `MFG_CA_BACKEND=kms VAPI_KMS_MFG_CA_ALIAS=alias/qortroller-mfg-ca AWS_PROFILE=vapi-bridge python scripts/provision_device_mfg.py --reissue 581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8 --controller-model CFI-ZCP1 --signing-path B --proof-tier FULL` → note the printed `birthCertHash` (cert lands at `~/.vapi/device_birth_cert_reissue.json` — the registered software cert is never clobbered).
3. Deploy the override (estimate first, then `VAPI_DBC_DEPLOY_CONFIRM=1`). Record the address; set
   `BIRTH_CERT_UPDATE_REGISTRY_ADDRESS` in `bridge/.env` + add the `deployed-addresses.json` entry.
4. Re-anchor (estimate first, then `VAPI_DBC_SET_CONFIRM=1` with `DEVICE_ID`=581a836c, `NEW_HASH`=the step-2 hash).
5. `python scripts/verify_device_cert.py --cert-path ~/.vapi/device_birth_cert_reissue.json` → expect **VALID**.
6. Flip `MFG_CA_BACKEND=kms` in `bridge/.env`; archive the old software cert as forensic-only.

### Pending governance seal (OPERATOR-FIRED — not done autonomously)
- **INV-MFG-003** (pin the override contract's `onlyOwner` + `isActive` guard + `BirthCertHashUpdated` +
  `currentBirthCertHash` override-wins) bumps PV-CI 183→184. Adding an invariant + regenerating the
  allowlist is a `--confirm-governance` seal, which stays operator-fired per the governance-seal boundary.
  Fire it when you seal the contract as LIVE trust.
- **Sensor-C G1.6 LIVE-FRAGILE → LIVE** is earned only AFTER step 5 (581a836c VALID under the HSM root) —
  a separate operator-confirmed Sensor-C edit. Not touched here.

**This pass:** contract + tests + deploy + re-anchor + verify integration + this audit note. PV-CI 183
unchanged; 0 IOTX; no chain write; no key provisioned by the repo. grok round-24 (design) + round-25
(verify). Operator fires the deploy + the ~0.2 IOTX re-anchor.
