# Sensor B — Hardware Watch Report (Cycle 17, 2026-06-13)

HWFL-1 Sensor B v0.1 — supply-and-standards watch. Pure-function assembler at `bridge/vapi_bridge/sensor_b_supply_watch.py`; network boundary lives at `scripts/run_sensor_b.py`. Generated `2026-06-13T04:53:52+00:00`.


## Honesty rail

Every web-sourced claim in this report carries an **UNVERIFIED-EXTERNAL** posture by default. `FRESH` lines come from structured queries (e.g. `gh pr view` JSON) and the summary cell reproduces only directly-observable fields. `PENDING-OPERATOR-NOTE` lines are placeholders the operator fills in by reading the primary URL and pasting intelligence into the runner's `--narratives` JSON. The loop NEVER converts an external claim into a repo-code change without independent verification by the operator.

## Standing OPERATOR-ACTION box (loop never auto-touches)

- [ ] **OA-1** Back up MFG Root CA canonical file (path per `docs/disaster-recovery-runbook.private.md`). F-DECON-3.2 interim mitigation. Highest-leverage 5-min action.
- [ ] **OA-2** Create `docs/disaster-recovery-runbook.private.md` with full AWS KMS ARNs.
- [ ] **OA-3** IAM scope-down on bridge/.env AWS keys → `KMS:Sign` + `KMS:GetPublicKey` on the two specific key ARNs.
- [ ] **OA-4** Long-term: HSM-backed ManufacturerRootCA + device re-issuance.

## State summary

| State | Count |
|---|---|
| FRESH | 1 |
| UNVERIFIED-EXTERNAL | 5 |
| VERIFIED-EXTERNAL | 1 |
| **Total** | **7** |

## Watch lines

| Topic | Title | State | Summary | Fetched at |
|---|---|---|---|---|
| `S1.iip64-pr72` | IIP-64 PR #72 movement | `FRESH` | PR #72 'IIP-64: Post-Quantum Cryptographic Migration for IoTeX' — OPEN; last updated 2026-05-23T15:35:47Z; author=xinxin-crypto; head=iip-64; +701/-0 lines | 2026-06-13T04:53:52+00:00 |
| `S2.atecc608a-lifecycle` | ATECC608A lifecycle / successor parts | `VERIFIED-EXTERNAL` | ATECC608A is NRND (Not Recommended for New Designs) since &gt;=2021-03 per Microchip product page ('Recommend using the ATECC608B'); corroborated by nerves-hub/nerves_key issue #60. Successor chain 608A -&gt; 608B -&gt; 608C; at least one 608B variant (ATECC608B-MAH4I-S) is itself NRND with ATECC608C-TFLXTLS (TrustFLEX pre-provisioned) as replacement. Migration cost LOW: AN2237 (DS40002237A) documents 608B as functional drop-in for 608A — same commands/structure, CryptoAuthLib absorbs differences; caveat is hardwired-timing firmware needs review (polling-based timing unaffected). Datasheets: DS40002239A (608B summary), DS40002513 (608C summary). | 2026-06-10T23:59:00+00:00 |
| `S3.k-silver-jh16-he-stick` | K-Silver JH16 Hall-effect stick module availability | `UNVERIFIED-EXTERNAL` | K-Silver (GUANGDONG K-SILVER INDUSTRIAL CO., LTD) makes the JH16 Hall-effect joystick module AND a JS16 TMR joystick in what appears to be the same product family (joint instruction manual 'JH16 Hall Effect and JS16 TMR'). JH16 = integrated Hall-effect sensors, marketed as drift-eliminating drop-in replacement for PS4/Switch/handheld modules; soldering install (desolder original, solder JH16). Significant for BOM C3/C4 same-family discipline: a single vendor offering both a Hall (JH16) and a TMR (JS16) in one form factor would let the dev-kit hold L/R same-family while A/B testing Hall-vs-TMR without changing footprint. GAP: no authoritative electrical spec (supply voltage, analog output range, pin map) was obtainable this cycle — the official vendor site k-silver.com is HTTP-only and refused HTTPS WebFetch (ECONNREFUSED); the manuals.plus instruction manual is anti-bot 403. Operator must pull the spec via browser or direct datasheet request. | 2026-06-13T05:00:00+00:00 |
| `S4.midas-5pin-he-stick` | MIDAS 5-pin Hall-effect stick module availability | `UNVERIFIED-EXTERNAL` | PROVENANCE GAP (finding, not intel). A targeted WebSearch for the BOM C3/C4 candidate 'MIDAS 5-pin Hall-effect' joystick module returned NO brand-specific authoritative source — only generic third-party Hall-effect replacement listings (Amazon/Walmart/eBay no-name modules). Unlike K-Silver (named vendor + official site) and GuliKit (named TMR vendor + retail presence), 'MIDAS' as a stick-module brand has weak public provenance as of 2026-06-13. Implication for the dev-kit BOM: the MIDAS C3/C4 candidate should be treated as LOWER-CONFIDENCE than K-Silver JH16 / GuliKit TMR until the operator can point to the actual MIDAS vendor/datasheet, OR it should be re-identified (the name may be a reseller label, a Hall IC vendor, or an internal codename rather than a sourceable module). | 2026-06-13T05:00:00+00:00 |
| `S5.magneto-tmr-stick` | Magneto TMR stick module availability | `UNVERIFIED-EXTERNAL` | TMR (Tunnel Magnetoresistance) is the current premium drift-free stick technology: quantum tunneling between two ferromagnetic layers across an insulating barrier; as the free layer's magnetization rotates with the stick's magnet, element resistance changes (analog, proportional to field orientation). Contrasted with Hall-effect (which measures voltage perpendicular to current). Claimed advantages: non-contact zero-drift, low power, higher sensitivity than GMR/AMR/Hall. Commercially the dominant TMR module vendor is GuliKit (TMR kit for PS5 DualSense / DualSense Edge, soldering required); 'Magneto' appears in the BOM as a TMR brand but GuliKit is the better-provenanced commercial TMR source as of 2026-06-13. GAP: no voltage/output-range spec, no confirmed pin-compatibility with Hall modules, no quantified latency or temperature range obtained — vendor material is marketing-focused. For BOM C3/C4: TMR and Hall are NOT guaranteed pin/footprint compatible; the same-family L/R discipline (do not mix Hall+TMR) is reinforced by this lack of confirmed cross-compat. | 2026-06-13T05:00:00+00:00 |
| `S6.esp32-cert-status` | ESP32-class module certification status | `UNVERIFIED-EXTERNAL` | ESP32 SoC family actively listed by Espressif alongside successor family members (ESP32-S2/S3/C2/C3/C5/C6/H2/H21/H4/P4/E22/S31/C61) as of 2026-06-11. Espressif landing page mentions wireless certs FCC/CE/SRRC/KCC/IC/TELEC/WFA/BQB in support section (not explicitly tied to ESP32 specifically — landing-page boilerplate caveat). ISO 9001 referenced. NO Common Criteria or FIPS cert stated on this page (significant for Path A: ESP32 alone is NOT a substitute for the ATECC608A — secure-element pairing remains required). Production status not stated directly on this page. | 2026-06-11T00:30:00+00:00 |
| `S7.competitive-landscape` | Competitive attested-input controller landscape | `UNVERIFIED-EXTERNAL` | Competitive stick-technology landscape for the dev-kit BOM (drift-free input tier): the aftermarket has converged on two contactless drift-free technologies — Hall-effect (commodity tier; many vendors incl. K-Silver JH16, GuliKit JH13, generic modules ~$15/pair) and TMR (premium tier; GuliKit, AimControllers, Get A Grip Gaming) — against legacy potentiometer (drift-prone, what the DualSense Edge ships with from ALPS Alpine per Sensor Stack v2.1 fact-correction). For QorTroller's L4-fingerprinting purpose this matters because: (1) the protocol's stick-fingerprint discriminator depends on per-unit analog noise-floor characteristics, which differ between Hall and TMR sensing physics — the same-batch separability question (Empirical Unknown #4, &gt;20% rank-1 threshold) must be measured PER sensor technology, not assumed transferable; (2) the market's drift-free convergence means a purpose-built QorTroller controller using Hall or TMR sticks is in line with competitive premium controllers, not exotic. This is landscape context, NOT a selection — C3/C4 stays MEASUREMENT-PENDING on Stage A. | 2026-06-13T05:00:00+00:00 |

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
- **fetched at:** `2026-06-13T04:53:52+00:00`

### S2.atecc608a-lifecycle — ATECC608A lifecycle / successor parts
- **state:** `VERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.microchip.com/en-us/product/atecc608a
- **spec ref:** docs/path-a-manufacturing-spec.md §2 Hardware Requirement
- **freshness window:** 30 days
- **summary:** ATECC608A is NRND (Not Recommended for New Designs) since &gt;=2021-03 per Microchip product page ('Recommend using the ATECC608B'); corroborated by nerves-hub/nerves_key issue #60. Successor chain 608A -&gt; 608B -&gt; 608C; at least one 608B variant (ATECC608B-MAH4I-S) is itself NRND with ATECC608C-TFLXTLS (TrustFLEX pre-provisioned) as replacement. Migration cost LOW: AN2237 (DS40002237A) documents 608B as functional drop-in for 608A — same commands/structure, CryptoAuthLib absorbs differences; caveat is hardwired-timing firmware needs review (polling-based timing unaffected). Datasheets: DS40002239A (608B summary), DS40002513 (608C summary).
- **raw excerpt:**
```
Implications operator-derived: F-HWFL-5-2 spec drift (Path A spec hard-names NRND ATECC608A in §1.1; should move to family language 'ATECC608B/608C-class CryptoAuthentication secure element, CryptoAuthLib-compatible, polling-based timing REQUIRED'); Rung 1 unaffected (on-hand 608A breakout remains valid for reference rig — NRND != unavailable, Rung 1 proves ceremony not BOM); Rung 2/3 BOM should specify 608B minimum + evaluate 608C-TFLXTLS (TrustFLEX successor part converges with §3.2 Rung 3 factory provisioning strategy).
```
- **fetched at:** `2026-06-10T23:59:00+00:00`
- **verified by:** operator (Con / ConWan30) via Claude.ai session
- **verified date:** `2026-06-10`
- **sources:**
  - https://www.microchip.com/en-us/product/atecc608a
  - https://github.com/nerves-hub/nerves_key/issues/60
  - Microchip DS40002239A (ATECC608B summary datasheet)
  - Microchip DS40002513 (ATECC608C summary datasheet)
  - Microchip AN2237 / DS40002237A (608A-&gt;608B migration guide)
  - Microchip AN3539 (additional migration guide)

### S3.k-silver-jh16-he-stick — K-Silver JH16 Hall-effect stick module availability
- **state:** `UNVERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.k-silver.com/
- **spec ref:** Sensor C G2.5 Hall/TMR stick selection
- **freshness window:** 30 days
- **summary:** K-Silver (GUANGDONG K-SILVER INDUSTRIAL CO., LTD) makes the JH16 Hall-effect joystick module AND a JS16 TMR joystick in what appears to be the same product family (joint instruction manual 'JH16 Hall Effect and JS16 TMR'). JH16 = integrated Hall-effect sensors, marketed as drift-eliminating drop-in replacement for PS4/Switch/handheld modules; soldering install (desolder original, solder JH16). Significant for BOM C3/C4 same-family discipline: a single vendor offering both a Hall (JH16) and a TMR (JS16) in one form factor would let the dev-kit hold L/R same-family while A/B testing Hall-vs-TMR without changing footprint. GAP: no authoritative electrical spec (supply voltage, analog output range, pin map) was obtainable this cycle — the official vendor site k-silver.com is HTTP-only and refused HTTPS WebFetch (ECONNREFUSED); the manuals.plus instruction manual is anti-bot 403. Operator must pull the spec via browser or direct datasheet request.
- **raw excerpt:**
```
Sources (reachability-checked, see url-reachability-cycle-17): http://k-silver.com/en/index.php/product/index/7.html (REACHABLE 200 to HEAD; ECONNREFUSED to HTTPS WebFetch), https://manuals.plus/ae/1005009222750559 (FORBIDDEN 403 to HEAD; title 'K-Sliver JH16 Hall Effect and JS16 TMR Joystick Instruction Manual'). WebSearch-derived: 5-pin module, available in 5-packs, batch appearance variation noted as non-functional. NOT obtained: voltage, output range, latency, dimensions, Hall IC part number.
```
- **fetched at:** `2026-06-13T05:00:00+00:00`

### S4.midas-5pin-he-stick — MIDAS 5-pin Hall-effect stick module availability
- **state:** `UNVERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://moddedzone.com/
- **spec ref:** Sensor C G2.5 Hall/TMR stick selection
- **freshness window:** 30 days
- **summary:** PROVENANCE GAP (finding, not intel). A targeted WebSearch for the BOM C3/C4 candidate 'MIDAS 5-pin Hall-effect' joystick module returned NO brand-specific authoritative source — only generic third-party Hall-effect replacement listings (Amazon/Walmart/eBay no-name modules). Unlike K-Silver (named vendor + official site) and GuliKit (named TMR vendor + retail presence), 'MIDAS' as a stick-module brand has weak public provenance as of 2026-06-13. Implication for the dev-kit BOM: the MIDAS C3/C4 candidate should be treated as LOWER-CONFIDENCE than K-Silver JH16 / GuliKit TMR until the operator can point to the actual MIDAS vendor/datasheet, OR it should be re-identified (the name may be a reseller label, a Hall IC vendor, or an internal codename rather than a sourceable module).
- **raw excerpt:**
```
WebSearch 'MIDAS Hall effect 5-pin joystick module gamepad replacement' (2026-06-13) returned only generic no-name PS5/Xbox Hall replacement listings; the search engine itself flagged no MIDAS-brand match and offered to re-search. This is a sourcing-confidence finding routed to the operator, not a vendor narrative.
```
- **fetched at:** `2026-06-13T05:00:00+00:00`

### S5.magneto-tmr-stick — Magneto TMR stick module availability
- **state:** `UNVERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** https://www.battlebeavercustoms.com/
- **spec ref:** Sensor C G2.5 Hall/TMR stick selection
- **freshness window:** 30 days
- **summary:** TMR (Tunnel Magnetoresistance) is the current premium drift-free stick technology: quantum tunneling between two ferromagnetic layers across an insulating barrier; as the free layer's magnetization rotates with the stick's magnet, element resistance changes (analog, proportional to field orientation). Contrasted with Hall-effect (which measures voltage perpendicular to current). Claimed advantages: non-contact zero-drift, low power, higher sensitivity than GMR/AMR/Hall. Commercially the dominant TMR module vendor is GuliKit (TMR kit for PS5 DualSense / DualSense Edge, soldering required); 'Magneto' appears in the BOM as a TMR brand but GuliKit is the better-provenanced commercial TMR source as of 2026-06-13. GAP: no voltage/output-range spec, no confirmed pin-compatibility with Hall modules, no quantified latency or temperature range obtained — vendor material is marketing-focused. For BOM C3/C4: TMR and Hall are NOT guaranteed pin/footprint compatible; the same-family L/R discipline (do not mix Hall+TMR) is reinforced by this lack of confirmed cross-compat.
- **raw excerpt:**
```
WebFetch https://eu.aimcontrollers.com/blog/tmr-technology-tunnel-magnetoresistance-sensors-in-gaming/ (REACHABLE 200; fetched 2026-06-13): 'As the magnetization direction of the free layer changes, the electrical resistance of the TMR element changes too'; resistance shift via electron transfer across insulating barrier; zero-drift via non-contact sensing; low power; higher sensitivity than GMR/AMR. NOT stated: voltage range, pin compat, latency, temp range. Corroborating reachable sources (not fetched this cycle): windowscentral.com/gaming/what-are-tmr-sticks (200), ifixit.com/News/115707/tm
```
- **fetched at:** `2026-06-13T05:00:00+00:00`

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
- **state:** `UNVERIFIED-EXTERNAL`
- **fetch kind:** `MANUAL_NARRATIVE`
- **primary URL:** _(narrative survey; no single canonical URL)_
- **spec ref:** HWFL-1 master prompt; recurring intel surface
- **freshness window:** 90 days
- **summary:** Competitive stick-technology landscape for the dev-kit BOM (drift-free input tier): the aftermarket has converged on two contactless drift-free technologies — Hall-effect (commodity tier; many vendors incl. K-Silver JH16, GuliKit JH13, generic modules ~$15/pair) and TMR (premium tier; GuliKit, AimControllers, Get A Grip Gaming) — against legacy potentiometer (drift-prone, what the DualSense Edge ships with from ALPS Alpine per Sensor Stack v2.1 fact-correction). For QorTroller's L4-fingerprinting purpose this matters because: (1) the protocol's stick-fingerprint discriminator depends on per-unit analog noise-floor characteristics, which differ between Hall and TMR sensing physics — the same-batch separability question (Empirical Unknown #4, &gt;20% rank-1 threshold) must be measured PER sensor technology, not assumed transferable; (2) the market's drift-free convergence means a purpose-built QorTroller controller using Hall or TMR sticks is in line with competitive premium controllers, not exotic. This is landscape context, NOT a selection — C3/C4 stays MEASUREMENT-PENDING on Stage A.
- **raw excerpt:**
```
WebSearch-derived landscape (2026-06-13): Hall vendors K-Silver, GuliKit (JH13), generic; TMR vendors GuliKit, AimControllers, Get A Grip Gaming. DualSense Edge ships ALPS potentiometer sticks from factory (per CLAUDE.md Sensor Stack v2.1 fact-correction); aftermarket Hall/TMR are the drift-free upgrades. Separability per-technology is an open Stage A measurement.
```
- **fetched at:** `2026-06-13T05:00:00+00:00`


## Provenance

- Canonical source registry: `bridge/vapi_bridge/sensor_b_supply_watch.py::_CANONICAL_SOURCES` (7 sources, FROZEN per cycle)
- Network calls: `scripts/run_sensor_b.py` only (gh CLI for STRUCTURED, operator JSON for MANUAL_NARRATIVE)
- Discipline: every external claim escaped + UNVERIFIED-EXTERNAL by default
