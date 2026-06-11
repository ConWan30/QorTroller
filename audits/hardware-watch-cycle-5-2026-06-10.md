# Sensor B — Hardware Watch Report (Cycle 5, 2026-06-10)

HWFL-1 Sensor B v0.1 — supply-and-standards watch. Pure-function assembler at `bridge/vapi_bridge/sensor_b_supply_watch.py`; network boundary lives at `scripts/run_sensor_b.py`. Generated `2026-06-11T23:06:35+00:00`.


## Honesty rail

Every web-sourced claim in this report carries an **UNVERIFIED-EXTERNAL** posture by default. `FRESH` lines come from structured queries (e.g. `gh pr view` JSON) and the summary cell reproduces only directly-observable fields. `PENDING-OPERATOR-NOTE` lines are placeholders the operator fills in by reading the primary URL and pasting intelligence into the runner's `--narratives` JSON. The loop NEVER converts an external claim into a repo-code change without independent verification by the operator.

## Standing OPERATOR-ACTION box (loop never auto-touches)

- [ ] **OA-1** Back up `~/.vapi/qortroller_foundation_mfg_ca.json` (517 B) — F-DECON-3.2 interim. Highest-leverage 5-min action.
- [ ] **OA-2** Create `docs/disaster-recovery-runbook.private.md` with full AWS KMS ARNs.
- [ ] **OA-3** IAM scope-down on bridge/.env AWS keys → `KMS:Sign` + `KMS:GetPublicKey` on the two specific key ARNs.
- [ ] **OA-4** Long-term: HSM-backed ManufacturerRootCA + device re-issuance.

## State summary

| State | Count |
|---|---|
| FRESH | 1 |
| PENDING-OPERATOR-NOTE | 4 |
| UNVERIFIED-EXTERNAL | 2 |
| **Total** | **7** |

## Watch lines

| Topic | Title | State | Summary | Fetched at |
|---|---|---|---|---|
| `S1.iip64-pr72` | IIP-64 PR #72 movement | `FRESH` | PR #72 'IIP-64: Post-Quantum Cryptographic Migration for IoTeX' — OPEN; last updated 2026-05-23T15:35:47Z; author=xinxin-crypto; head=iip-64; +701/-0 lines | 2026-06-11T23:06:35+00:00 |
| `S2.atecc608a-lifecycle` | ATECC608A lifecycle / successor parts | `UNVERIFIED-EXTERNAL` | STATUS: VERIFIED-EXTERNAL (operator-proxy fetch). ATECC608A is NRND (Not Recommended for New Designs) since &gt;=2021-03 per Microchip product page ('Recommend using the ATECC608B'); corroborated by nerves-hub/nerves_key issue #60. Successor chain 608A -&gt; 608B -&gt; 608C; at least one 608B variant (ATECC608B-MAH4I-S) is itself NRND with ATECC608C-TFLXTLS (TrustFLEX pre-provisioned) as replacement. Migration cost LOW: AN2237 (DS40002237A) documents 608B as functional drop-in for 608A — same commands/structure, CryptoAuthLib absorbs differences; caveat is hardwired-timing firmware needs review (polling-based timing unaffected). Datasheets: DS40002239A (608B summary), DS40002513 (608C summary). | 2026-06-10T23:59:00+00:00 |
| `S3.k-silver-jh16-he-stick` | K-Silver JH16 Hall-effect stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S4.midas-5pin-he-stick` | MIDAS 5-pin Hall-effect stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S5.magneto-tmr-stick` | Magneto TMR stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S6.esp32-cert-status` | ESP32-class module certification status | `UNVERIFIED-EXTERNAL` | ESP32 SoC family actively listed by Espressif alongside successor family members (ESP32-S2/S3/C2/C3/C5/C6/H2/H21/H4/P4/E22/S31/C61) as of 2026-06-11. Espressif landing page mentions wireless certs FCC/CE/SRRC/KCC/IC/TELEC/WFA/BQB in support section (not explicitly tied to ESP32 specifically — landing-page boilerplate caveat). ISO 9001 referenced. NO Common Criteria or FIPS cert stated on this page (significant for Path A: ESP32 alone is NOT a substitute for the ATECC608A — secure-element pairing remains required). Production status not stated directly on this page. | 2026-06-11T00:30:00+00:00 |
| `S7.competitive-landscape` | Competitive attested-input controller landscape | `PENDING-OPERATOR-NOTE` |  |  |

## Detail

### S1.iip64-pr72 — IIP-64 PR #72 movement
- **state:** `FRESH`
- **fetch kind:** `STRUCTURED`
- **primary URL:** https://github.com/iotexproject/iips/pull/72
- **spec ref:** Sensor C G4.1 BLOCKED-ON-EXTERNAL
- **freshness window:** 7 days
- **summary:** PR #72 'IIP-64: Post-Quantum Cryptographic Migration for IoTeX' — OPEN; last updated 2026-05-23T15:35:47Z; author=xinxin-crypto; head=iip-64; +701/-0 lines
- **raw excerpt:**
```
{
  "additions": 701,
  "author": {
    "id": "MDQ6VXNlcjM2OTY2ODc4",
    "is_bot": false,
    "login": "xinxin-crypto",
    "name": "Xinxin Fan"
  },
  "closedAt": null,
  "deletions": 0,
  "headRefName": "iip-64",
  "isDraft": false,
  "mergedAt": null,
  "number": 72,
  "state": "OPEN",
  "title": "IIP-64: Post-Quantum Cryptographic Migration for IoTeX",
  "updatedAt": "2026-05-23T15:35:47Z"
}
```
- **fetched at:** `2026-06-11T23:06:35+00:00`

### S2.atecc608a-lifecycle — ATECC608A lifecycle / successor parts
- **state:** `UNVERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.microchip.com/en-us/product/atecc608a
- **spec ref:** docs/path-a-manufacturing-spec.md §2 Hardware Requirement
- **freshness window:** 30 days
- **summary:** STATUS: VERIFIED-EXTERNAL (operator-proxy fetch). ATECC608A is NRND (Not Recommended for New Designs) since &gt;=2021-03 per Microchip product page ('Recommend using the ATECC608B'); corroborated by nerves-hub/nerves_key issue #60. Successor chain 608A -&gt; 608B -&gt; 608C; at least one 608B variant (ATECC608B-MAH4I-S) is itself NRND with ATECC608C-TFLXTLS (TrustFLEX pre-provisioned) as replacement. Migration cost LOW: AN2237 (DS40002237A) documents 608B as functional drop-in for 608A — same commands/structure, CryptoAuthLib absorbs differences; caveat is hardwired-timing firmware needs review (polling-based timing unaffected). Datasheets: DS40002239A (608B summary), DS40002513 (608C summary).
- **raw excerpt:**
```
Sources enumerated: (1) microchip.com/en-us/product/atecc608a — 'Recommend using the ATECC608B'. (2) github.com/nerves-hub/nerves_key/issues/60 — community corroboration. (3) Microchip datasheets DS40002239A (608B), DS40002513 (608C). (4) Microchip app notes AN2237 (= DS40002237A) and AN3539 — migration guides. Implications operator-derived: F-HWFL-5-2 spec drift (Path A spec hard-names NRND ATECC608A in §1.1; should move to family language 'ATECC608B/608C-class CryptoAuthentication secure element, CryptoAuthLib-compatible, polling-based timing REQUIRED'); Rung 1 unaffected (on-hand 608A break
```
- **fetched at:** `2026-06-10T23:59:00+00:00`

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
- **state:** `UNVERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.espressif.com/en/products/socs/esp32
- **spec ref:** Sensor C G2.7 BLOCKED-ON-SENSOR-B (unblock candidate)
- **freshness window:** 60 days
- **summary:** ESP32 SoC family actively listed by Espressif alongside successor family members (ESP32-S2/S3/C2/C3/C5/C6/H2/H21/H4/P4/E22/S31/C61) as of 2026-06-11. Espressif landing page mentions wireless certs FCC/CE/SRRC/KCC/IC/TELEC/WFA/BQB in support section (not explicitly tied to ESP32 specifically — landing-page boilerplate caveat). ISO 9001 referenced. NO Common Criteria or FIPS cert stated on this page (significant for Path A: ESP32 alone is NOT a substitute for the ATECC608A — secure-element pairing remains required). Production status not stated directly on this page.
- **raw excerpt:**
```
Source: https://www.espressif.com/en/products/socs/esp32 (fetched via Claude Code WebFetch 2026-06-11 UTC). Datasheet: https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf. Wireless certs listed in support section (not ESP32-specific): FCC, CE, SRRC, KCC, IC, TELEC, WFA, BQB. Safety certs mentioned: ISO 9001. Family successors listed verbatim: ESP32-S2, ESP32-S3, ESP32-C2, ESP32-C3, ESP32-C5, ESP32-C6, ESP32-H2, ESP32-H21, ESP32-H4, ESP32-P4, ESP32-E22, ESP32-S31, ESP32-C61. Production-status statement: not present on this page.
```
- **fetched at:** `2026-06-11T00:30:00+00:00`

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
