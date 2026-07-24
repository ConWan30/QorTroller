# Sensor C — Rung-Gate Readiness Ledger (Cycle 18, 2026-07-16)

HWFL-1 Sensor C v0.1 — machine-checkable snapshot of every gate across Rungs 1-4 of the QorTroller manufacturing staircase. Honest weighting: nothing LIVE that isn't verifiable now. Generated `2026-07-17T03:10:36+00:00` by `scripts/run_sensor_c.py`. Machine-readable companion: `audits/rung-gate-ledger-latest.json`.


## Standing OPERATOR-ACTION box (loop renders; operator attests)

_Statuses are OPERATOR attestations. The HWFL-1 sensors (Sensor C ledger + Sensor B watch) render this box via bridge/vapi_bridge/operator_actions.py; they never write or infer a status. To change an attestation, edit this file. Sanitization (F-CYCLE8-1/9-1): keep CA filenames, raw AWS ARNs, and home-directory key paths OUT of this file._

- [x] **OA-1** (moot) Back up / protect the MFG Root CA canonical file (path per docs/disaster-recovery-runbook.private.md). — _attested 2026-07-17: Retired on both axes: the interim-backup secrecy rationale was already lost to public git history (F-CYCLE9-1), AND the F-DECON-3.2 root fix landed, so the software CA is now cold-retained forensic-only, not a live signer._ (hint: see `Sensor-C G1.6 (LIVE post root-fix)`)
- [x] **OA-2** (done) Maintain docs/disaster-recovery-runbook.private.md with the full AWS KMS ARNs (gitignored companion). — _attested 2026-07-17: Private companion exists locally; the loop existence-checks only and never reads its contents._ (hint: path `docs/disaster-recovery-runbook.private.md`)
- [ ] **OA-3** (open) Scope the bridge/.env AWS IAM keys down to KMS:Sign + KMS:GetPublicKey on the specific key ARNs. — _attested 2026-07-17: There are now THREE keys (Sentry secp256k1 + Guardian secp256k1 + MFG Root CA P-256 alias). The 2026-07-16 ceremony proved the bridge IAM user can Sign with the CA key and that CreateKey is denied; full least-privilege policy is verifiable only in the operator's AWS console. CA isolation is enforced at the kms_client alias map (agents hold no MFG alias), not at the IAM principal — so the scope-down remains a real, open hardening step._
- [x] **OA-4** (done) Long-term: HSM-backed ManufacturerRootCA + live-device re-issuance (the F-DECON-3.2 root fix). — _attested 2026-07-17: Fired 2026-07-16/17: AWS KMS P-256 HSM CA live, override registry deployed (0x31030C8F...), device 581a836c re-anchored and VALID under the HSM root, INV-MFG-003 governance-sealed (PV-CI 184), Sensor-C G1.6 demoted to LIVE._ (hint: see `audits/mfg-ca-hsm-readiness-and-path-a-2026-07-16.md`)


## State summary

| State | Count |
|---|---|
| LIVE | 5 |
| LIVE-PARTIAL | 1 |
| DORMANT | 12 |
| HARDWARE-GATED | 3 |
| BLOCKED-ON-EXTERNAL | 1 |
| **Total** | **22** |


## Rung 1

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G1.1` | DualSense Edge physically connected | `HARDWARE-GATED` | intrinsic state (HARDWARE-GATED); see spec_ref |
| `G1.2` | ATECC608A breakout physically connected | `HARDWARE-GATED` | intrinsic state (HARDWARE-GATED); see spec_ref |
| `G1.3` | CH341A USB-I2C bridge present | `HARDWARE-GATED` | intrinsic state (HARDWARE-GATED); see spec_ref |
| `G1.4` | VAPIManufacturerDeviceRegistry deployed on IoTeX testnet | `LIVE` | VMDR @ 0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0 (IoTeX testnet chainId 4690) |
| `G1.5` | First reference device registered on-chain | `LIVE` | registration tx 0x68f6cf49…ac9c0 cited in CLAUDE.md (block 44028531) |
| `G1.6` | ManufacturerRootCA root of trust present (HSM-backed post root-fix; file pre-fix) | `LIVE` | MFG Root CA root of trust is HSM-backed — F-DECON-3.2 root fix landed 2026-07-16/17: birth-cert override registry deployed (deployed-addresses.json) + INV-MFG-003 governance-sealed in the PV-CI allowlist (both machine-checked here). The ceremony record (audits/mfg-ca-hsm-readiness-and-path-a-2026-07-16.md) attests the live device VALID under the HSM root — attested by that artifact, not re-verified by this sensor. Software CA file cold-retained forensic-only per the migration runbook — existence no longer load-bearing. |
| `G1.7` | SecureElementBackend honesty rail intact | `LIVE` | SecureElementBackend raises NotImplementedError (blocks silent host-key fallback; Arc 2 hardware-gated) |


## Rung 2

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G2.1` | Dev-kit BOM document exists (two suppliers per critical part) | `LIVE` | docs/qortroller-devkit-bom-v0_1.md present with C1-C8 + two-supplier rail (SCAFFOLD only — no supplier committed; LIVE-SUPPLIED gated on Stage A measurement + 2 verified suppliers per BOM §7) |
| `G2.2` | Zephyr firmware target for QorTroller controller | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.3` | Thread-C-equivalent isolation statement in firmware spec | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.4` | φ sanitization device-residency design | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.5` | Hall/TMR stick module selection finalized | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.6` | IMU module selection finalized | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.7` | ESP32-class module cert status known | `LIVE-PARTIAL` | S6 narrative (ops_notes_cycle5.json) + BOM C1 row both reference the 'NO Common Criteria/FIPS on landing page; ESP32 alone NOT a substitute for ATECC608A; secure-element pairing required' finding. PARTIAL because S6 is UNVERIFIED-EXTERNAL (Sensor B v0.1.1 schema; Claude WebFetch draft, not operator-verified with verified_by+sources+verified_date). Promotion to full LIVE requires S6 lifted to VERIFIED-EXTERNAL. |


## Rung 3

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G3.1` | Partner-handoff package assembler | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.2` | TrustFLEX provisioning path amendment to spec | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.3` | Manufacturer CA chained to reference root — design | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.4` | Per-batch slot-config audit checklist | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.5` | Two-supplier cost model for critical parts | `DORMANT` | intrinsic state (DORMANT); see spec_ref |


## Rung 4

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G4.1` | IIP-64 PR #72 movement / merge | `BLOCKED-ON-EXTERNAL` | intrinsic state (BLOCKED-ON-EXTERNAL); see spec_ref |
| `G4.2` | Spec-as-compliance-standard formalized | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G4.3` | Device-identity registry interop spec | `DORMANT` | intrinsic state (DORMANT); see spec_ref |


## Provenance

- Canonical gate registry: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_CANONICAL_GATES` (22 gates, FROZEN per cycle)
- Verifier functions: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_VERIFIERS` (6 active)
- Schema: `vapi-rung-gate-ledger-v1` (JSON companion artifact)
- Rung definitions: HWFL-1 master prompt + `docs/path-a-manufacturing-spec.md`
