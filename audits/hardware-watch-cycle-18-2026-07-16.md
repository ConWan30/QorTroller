# Sensor B — Hardware Watch Report (Cycle 18, 2026-07-16)

HWFL-1 Sensor B v0.1 — supply-and-standards watch. Pure-function assembler at `bridge/vapi_bridge/sensor_b_supply_watch.py`; network boundary lives at `scripts/run_sensor_b.py`. Generated `2026-07-17T03:10:36+00:00`.


## Honesty rail

Every web-sourced claim in this report carries an **UNVERIFIED-EXTERNAL** posture by default. `FRESH` lines come from structured queries (e.g. `gh pr view` JSON) and the summary cell reproduces only directly-observable fields. `PENDING-OPERATOR-NOTE` lines are placeholders the operator fills in by reading the primary URL and pasting intelligence into the runner's `--narratives` JSON. The loop NEVER converts an external claim into a repo-code change without independent verification by the operator.

## Standing OPERATOR-ACTION box (loop renders; operator attests)

_Statuses are OPERATOR attestations. The HWFL-1 sensors (Sensor C ledger + Sensor B watch) render this box via bridge/vapi_bridge/operator_actions.py; they never write or infer a status. To change an attestation, edit this file. Sanitization (F-CYCLE8-1/9-1): keep CA filenames, raw AWS ARNs, and home-directory key paths OUT of this file._

- [x] **OA-1** (moot) Back up / protect the MFG Root CA canonical file (path per docs/disaster-recovery-runbook.private.md). — _attested 2026-07-17: Retired on both axes: the interim-backup secrecy rationale was already lost to public git history (F-CYCLE9-1), AND the F-DECON-3.2 root fix landed, so the software CA is now cold-retained forensic-only, not a live signer._ (hint: see `Sensor-C G1.6 (LIVE post root-fix)`)
- [x] **OA-2** (done) Maintain docs/disaster-recovery-runbook.private.md with the full AWS KMS ARNs (gitignored companion). — _attested 2026-07-17: Private companion exists locally; the loop existence-checks only and never reads its contents._ (hint: path `docs/disaster-recovery-runbook.private.md`)
- [ ] **OA-3** (open) Scope the bridge/.env AWS IAM keys down to KMS:Sign + KMS:GetPublicKey on the specific key ARNs. — _attested 2026-07-17: There are now THREE keys (Sentry secp256k1 + Guardian secp256k1 + MFG Root CA P-256 alias). The 2026-07-16 ceremony proved the bridge IAM user can Sign with the CA key and that CreateKey is denied; full least-privilege policy is verifiable only in the operator's AWS console. CA isolation is enforced at the kms_client alias map (agents hold no MFG alias), not at the IAM principal — so the scope-down remains a real, open hardening step._
- [x] **OA-4** (done) Long-term: HSM-backed ManufacturerRootCA + live-device re-issuance (the F-DECON-3.2 root fix). — _attested 2026-07-17: Fired 2026-07-16/17: AWS KMS P-256 HSM CA live, override registry deployed (0x31030C8F...), device 581a836c re-anchored and VALID under the HSM root, INV-MFG-003 governance-sealed (PV-CI 184), Sensor-C G1.6 demoted to LIVE._ (hint: see `audits/mfg-ca-hsm-readiness-and-path-a-2026-07-16.md`)


## State summary

| State | Count |
|---|---|
| PENDING-OPERATOR-NOTE | 7 |
| **Total** | **7** |

## Watch lines

| Topic | Title | State | Summary | Fetched at |
|---|---|---|---|---|
| `S1.iip64-pr72` | IIP-64 PR #72 movement | `PENDING-OPERATOR-NOTE` |  |  |
| `S2.atecc608a-lifecycle` | ATECC608A lifecycle / successor parts | `PENDING-OPERATOR-NOTE` |  |  |
| `S3.k-silver-jh16-he-stick` | K-Silver JH16 Hall-effect stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S4.midas-5pin-he-stick` | MIDAS 5-pin Hall-effect stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S5.magneto-tmr-stick` | Magneto TMR stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S6.esp32-cert-status` | ESP32-class module certification status | `PENDING-OPERATOR-NOTE` |  |  |
| `S7.competitive-landscape` | Competitive attested-input controller landscape | `PENDING-OPERATOR-NOTE` |  |  |

## Detail

### S1.iip64-pr72 — IIP-64 PR #72 movement
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `STRUCTURED`
- **primary URL:** https://github.com/iotexproject/iips/pull/72
- **spec ref:** Sensor C G4.1 BLOCKED-ON-EXTERNAL
- **freshness window:** 7 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_

### S2.atecc608a-lifecycle — ATECC608A lifecycle / successor parts
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.microchip.com/en-us/product/atecc608a
- **spec ref:** docs/path-a-manufacturing-spec.md §2 Hardware Requirement
- **freshness window:** 30 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_

### S3.k-silver-jh16-he-stick — K-Silver JH16 Hall-effect stick module availability
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.k-silver.com/
- **spec ref:** Sensor C G2.5 Hall/TMR stick selection
- **freshness window:** 30 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_

### S4.midas-5pin-he-stick — MIDAS 5-pin Hall-effect stick module availability
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://moddedzone.com/
- **spec ref:** Sensor C G2.5 Hall/TMR stick selection
- **freshness window:** 30 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_

### S5.magneto-tmr-stick — Magneto TMR stick module availability
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.battlebeavercustoms.com/
- **spec ref:** Sensor C G2.5 Hall/TMR stick selection
- **freshness window:** 30 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_

### S6.esp32-cert-status — ESP32-class module certification status
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.espressif.com/en/products/socs/esp32
- **spec ref:** Sensor C G2.7 BLOCKED-ON-SENSOR-B (unblock candidate)
- **freshness window:** 60 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_

### S7.competitive-landscape — Competitive attested-input controller landscape
- **state:** `PENDING-OPERATOR-NOTE`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** _(narrative survey; no single canonical URL)_
- **spec ref:** HWFL-1 master prompt; recurring intel surface
- **freshness window:** 90 days
- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_


## Provenance

- Canonical source registry: `bridge/vapi_bridge/sensor_b_supply_watch.py::_CANONICAL_SOURCES` (7 sources, FROZEN per cycle)
- Network calls: `scripts/run_sensor_b.py` only (gh CLI for STRUCTURED, operator JSON for MANUAL_NARRATIVE)
- Discipline: every external claim escaped + UNVERIFIED-EXTERNAL by default
