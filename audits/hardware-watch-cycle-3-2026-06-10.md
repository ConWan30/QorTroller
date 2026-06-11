# Sensor B — Hardware Watch Report (Cycle 3, 2026-06-10)

HWFL-1 Sensor B v0.1 — supply-and-standards watch. Pure-function assembler at `bridge/vapi_bridge/sensor_b_supply_watch.py`; network boundary lives at `scripts/run_sensor_b.py`. Generated `2026-06-11T00:36:16+00:00`.


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
| PENDING-OPERATOR-NOTE | 6 |
| **Total** | **7** |

## Watch lines

| Topic | Title | State | Summary | Fetched at |
|---|---|---|---|---|
| `S1.iip64-pr72` | IIP-64 PR #72 movement | `FRESH` | PR #72 'IIP-64: Post-Quantum Cryptographic Migration for IoTeX' — OPEN; last updated 2026-05-23T15:35:47Z; author=xinxin-crypto; head=iip-64; +701/-0 lines | 2026-06-11T00:36:16+00:00 |
| `S2.atecc608a-lifecycle` | ATECC608A lifecycle / successor parts | `PENDING-OPERATOR-NOTE` |  |  |
| `S3.k-silver-jh16-he-stick` | K-Silver JH16 Hall-effect stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S4.midas-5pin-he-stick` | MIDAS 5-pin Hall-effect stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S5.magneto-tmr-stick` | Magneto TMR stick module availability | `PENDING-OPERATOR-NOTE` |  |  |
| `S6.esp32-cert-status` | ESP32-class module certification status | `PENDING-OPERATOR-NOTE` |  |  |
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
- **fetched at:** `2026-06-11T00:36:16+00:00`

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
