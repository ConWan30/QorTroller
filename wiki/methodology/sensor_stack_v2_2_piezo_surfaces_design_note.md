# Sensor Stack v2.2 — Piezoelectric Surfaces (DESIGN NOTE / PROPOSAL)

**Status: DESIGN NOTE — a PROPOSAL, not an accepted architectural revision.**
This document proposes two *candidate* surfaces (Surface 7, Surface 8) for the
DualSense-class / QorTroller-native sensor stack. It does NOT supersede
`sensor_stack_v2_1_architectural_revision.md`; the six v2.1 surfaces and their
tier assignments are unchanged. Neither surface here carries any LIVE claim.
Acceptance into a future v2.2 *revision* requires (a) operator acceptance of this
note, AND (b) the per-surface Stage A measurement passing. Until both, these are
measurement-pending candidates only.

**Origin:** operator brainstorm 2026-06-13 (piezo integration / Qorvo outreach),
triaged against the protocol's honesty discipline. Captures ideas #1 (piezo-acoustic
grip liveness) and #2 (piezo L6 actuation). Ideas #3 (energy harvesting) and #4
(piezo-TMR pressure ring) were assessed and deliberately NOT promoted to surfaces
this pass (see §5).

---

## §0 Honesty stamp (inherited discipline)

Every claim below is graded, not marketed. The recurring failure mode this note
guards against is the "impossible / could never / instantly detects" overclaim. The
protocol's credibility rests on saying **"raises spoof cost, pending Stage A
measurement"** rather than **"unbeatable."** Both proposed surfaces are subject to
the same same-controller-population separability constraint (`CROSS-LESSON-001`) and
the same three-independent-verification-classes rule (`BT-CALIB-LESSON-001`) as every
existing surface. New signals feed EXISTING feature slots / off-chain analysis — they
do NOT expand the 228-byte PoAC FROZEN wire format (hard rule).

---

## §1 Surface 7 — Piezo-Acoustic Through-Shell Grip Liveness

### Concept
A piezo actuator injects an ultrasonic acoustic wave into the controller shell
(PETG/ABS). A second piezo element reads the transmitted/reflected wave. A hand
gripping the shell absorbs and damps the wave in a tissue-characteristic way
(flesh + bone acoustic impedance ≠ air ≠ rigid mount). The damping signature gates
a fast **held-vs-not-held liveness** decision.

### Proposed tier: **ADVISORY — LIVENESS GATE ONLY (explicitly NOT an identity surface)**
- **What it CLAIMS (defensible):** binary-ish presence — "a compliant body is gripping
  the controller now," usable as a cheap pre-gate before the 1 kHz micro-tremor
  analysis spins up. Maps to L0/L9 Proof of Embodied Presence (PoEP).
- **What it does NOT claim (until measured):** per-person biometric identity. Treating
  shell-acoustic damping as a *who* signal (vs a *is-something-gripping* signal) is a
  much larger claim requiring its own same-batch separability study. Surface 7 v0 is a
  **liveness gate, not a fingerprint.**

### Threat-model honesty
A liveness gate **raises spoof cost; it does not close the gap.** A rig packed with
ballistic gel / silicone tuned to tissue-like acoustic impedance can approximate human
damping. Surface 7 forces a spoofer to physically model tissue impedance instead of
replaying data — valuable, but it is one signal in a fusion, not a silver bullet.
Frame it that way in any pitch.

### Confounds that MUST be characterized before any claim
Acoustic transmission through a polymer shell is sensitive to:
- **Temperature** (PETG/ABS modulus shifts with temp → damping baseline drifts)
- **Humidity / sweat** on the grip surface
- **Grip pressure** (light vs death-grip changes coupling)
- **Gloves** (esports players sometimes wear them)
- **Unit-to-unit manufacturing variance** (shell wall thickness, infill, print-layer
  adhesion for 3D-printed prototypes vs injection-molded production)
- **Mount geometry** (resting against a leg vs a desk vs a clamp)

A surface whose baseline moves with ambient temperature is not deployable as a hard
gate until the confound envelope is mapped. This is the core of its Stage A study.

### Stage A gate — **Empirical Unknown #5 (NEW, proposed)**
> Measure held-vs-not-held acoustic-damping separability across N≥10 hands × the full
> confound matrix (≥3 temperatures, ±humidity, gloved/ungloved, light/firm grip) on
> N≥10 controller units. **Decision threshold:** the held/not-held decision boundary
> must hold (e.g., ≥95% true-positive at a fixed false-positive budget) ACROSS the
> confound matrix, not just at one bench condition. A secondary probe quantifies
> rig-spoof cost (gel/silicone mimics) to set the honest "raises-cost-by-X" claim.

Until #5 closes, Surface 7 cannot be a gate — at most a logged advisory signal.

### Verification blocks required (three independent classes per BT-CALIB-LESSON-001)
1. **Vendor spec** — a real piezo transceiver + driver IC datasheet (drive frequency,
   sense bandwidth, power).
2. **Open-source / prior-art anchor** — bio-acoustic / swept-frequency through-body
   sensing literature (e.g., acoustic grip-detection, Touché-class swept-frequency
   work) establishing the physics is real and bounding what it can/can't resolve.
3. **Independent measurement** — the Empirical Unknown #5 dataset on real units.

### PoAC constraint
Surface 7 output is a small liveness flag + damping-feature vector that feeds the
L9/PoEP pre-gate and/or an existing L4 advisory slot. It does NOT add bytes to the
228-byte PoAC record. If a commitment to the liveness result is ever needed on-chain,
it rides as a feature inside an existing frozen structure, never as a format change.

---

## §2 Surface 8 — Piezo Haptic L6 Actuation Channel

### Concept
Replace (or augment) ERM/voice-coil haptics with high-definition piezo actuators under
the trigger caps / grip. Piezo actuators deliver microsecond-accurate, hyper-localized,
silent mechanical pulses — a far cleaner stimulus for the L6 active
challenge-response loop than sluggish rotary/voice-coil haptics.

### Proposed classification: **ACTUATOR (challenge side) coupled to L6 / L6B sensing**
This is not a sensing surface; it is the *stimulus* half of the L4-coupled-to-L6
challenge-response channel the manufacturing spec already names as **Stage B**. When
the protocol issues a nonce-bound PoEP challenge, the piezo delivers a sub-perceptual
tap (amplitude ≤60/255 design target) to the **fingertip pad** (precise physiology:
the pad, not the tendon directly), and the 1 kHz polling loop captures the involuntary
neuromuscular correction inside the 80–280 ms human reaction band.

### Why this is the strongest of the four piezo ideas
- It **upgrades a feature that is already on the roadmap** (roadmap_post_stage_1
  L6-Response; manufacturing-spec Stage B = adaptive-trigger challenge-response).
- The hardware advantage is a **verifiable fact**, not a claim: piezo haptics have
  sub-millisecond response and tight localization vs ERM/voice-coil. A cleaner stimulus
  yields a cleaner reflex measurement.

### What it CLAIMS vs does NOT claim
- **CLAIMS (defensible):** a precise, silent, localized stimulus that makes the reflex
  response captured at 1 kHz cleaner and harder to fake → a stronger *statistical*
  discriminator in the reflex-timing band.
- **Does NOT claim:** that it makes spoofing "mathematically impossible." The
  reflex-timing band is a statistical discriminator that raises spoof cost; a
  closed-loop rig with its own actuator+sensor could attempt a plausible response.
  Cut "impossible" from any pitch.

### Stage A / corpus gates
- **Empirical Unknown #6 (NEW, proposed):** quantify reflex-response *cleanliness*
  (SNR / separability of human reflex vs no-reflex vs synthetic) under piezo stimulus
  vs a voice-coil baseline, N≥10 players. Decision: piezo must measurably out-separate
  the voice-coil baseline to justify the BOM cost.
- **Existing hard gate, unchanged:** `L6B_ENABLED=false` until **N≥50 neuromuscular
  reflex calibration sessions per player** (currently N=0). Better hardware does NOT
  bypass the corpus requirement — the actuator can ship before the *claim* can.

### Verification blocks required
1. **Vendor spec** — piezo haptic driver IC + actuator datasheet (rise time, drive
   voltage, displacement, audible-noise floor).
2. **Prior-art anchor** — piezo-haptic literature + the human voluntary-reaction-time
   band (80–280 ms) literature already anchored in the protocol.
3. **Independent measurement** — Empirical Unknown #6 + the L6B N≥50 corpus.

### PoAC constraint
Surface 8 produces a reflex-timing feature that feeds the existing L6/L6B humanity
sub-score. No change to the 228-byte record.

---

## §3 Layer-stack mapping

| Surface | Stimulus/Sensing | Feeds | Gate before LIVE |
|---|---|---|---|
| **7 Piezo-acoustic** | Sensing | L0/L9 PoEP liveness pre-gate (+ optional L4 advisory) | Empirical Unknown #5 (confound-robust held/not-held) |
| **8 Piezo haptic** | Actuation (challenge side) | L6/L6B reflex-timing sub-score | Empirical Unknown #6 + L6B N≥50 corpus |

---

## §4 Sourcing flags (partnership reality check)

**Correction to the brainstorm's premise:** Qorvo's acoustic-wave strength is
**BAW/SAW RF filters** (radio front-end), not grip-sensing or haptic piezo. Do not
build a pitch on "Qorvo piezo." Per-surface sourcing:

| Surface | Best-fit piezo vendor(s) | Qorvo's actual role |
|---|---|---|
| **8 piezo haptics** | **Boréas Technologies** (CapDrive piezo haptic driver ICs — purpose-built for sub-ms localized haptics); TDK/Aito | Not the haptic-piezo source |
| **7 piezo-acoustic sensing** | TDK, TE Connectivity, Murata (piezo transceivers) | BAW tech is RF-band; repurposing to grip-sensing is non-trivial, not off-shelf |
| **(elsewhere in BOM)** | — | Qorvo remains a credible match for **RF/connectivity + power-management** ICs and possibly MEMS — keep the relationship, just name it accurately |

**Verification rider (BT-CALIB-LESSON-001 / F-HWFL-5-1):** independently confirm each
vendor's *current* commercial portfolio + part availability before naming any of them
in a deck. HEAD-probe candidate datasheet URLs with
`python scripts/probe_vendor_urls.py <url>` first to route around dead/anti-bot pages.

---

## §5 Ideas assessed but NOT promoted this pass

- **#3 Piezo energy harvesting** — KEPT AS NARRATIVE, REJECTED AS POWER ENGINEERING.
  Button-press harvest yields micro-to-milliwatts; the ESP32 radio draws 80–240 mA in
  active play — orders of magnitude short of break-even. The TP4056 is a linear charger,
  not a harvesting PMIC (would need TI BQ25570 / LTC3588). Do NOT enter it in the BOM as
  a power solution. *Interesting reframe for a future note:* piezo button-harvest as a
  **proof-of-physical-work cryptographic signal** (a verifiable energy-signature that a
  solenoid-press rig produces differently than a human) — a novelty primitive, NOT a
  power feature. Parked.
- **#4 Piezo-TMR pressure ring** — INCREMENTAL; competes with C7 for the novelty budget
  and turns the near-off-shelf C3/C4 stick into a custom mechanical integration. Parked
  as a v2 L4-fusion candidate; do not dilute the adaptive-trigger (C7) story to add it.

---

## §6 Proposed BOM advisory rows (pending operator acceptance + Stage A)

If this note is accepted, add to `docs/qortroller-devkit-bom-v0_1.md` §4 Advisory:

| ID | Description | Status | Notes |
|---|---|---|---|
| `A4` | Piezo-acoustic transceiver pair (grip liveness) | `MEASUREMENT-PENDING` | Surface 7; gate Empirical Unknown #5; vendor TDK/TE/Murata; liveness-gate only, NOT identity |
| `A5` | Piezo haptic actuator + driver IC (L6 challenge) | `MEASUREMENT-PENDING` | Surface 8; gate Empirical Unknown #6 + L6B N≥50; vendor Boréas/TDK; Stage B feature |

Both carry the two-supplier note. Neither may reach `LIVE-SUPPLIED` without its Stage A
gate closing — same rule as C3/C4/C5/C7.

---

## §7 Decisions open for the operator

- **D-PIEZO-1:** accept this design note → fold Surfaces 7/8 into a real
  `sensor_stack_v2_2_architectural_revision.md` (which WOULD then supersede v2.1 with a
  `[SUPERSEDED-v2.1]` annotation), or hold as a proposal?
- **D-PIEZO-2:** add the A4/A5 advisory rows to the BOM now (as MEASUREMENT-PENDING), or
  wait until a vendor is identified?
- **D-PIEZO-3:** register Empirical Unknowns #5 and #6 as canonical Stage A gates?
- **D-PIEZO-4:** pursue Boréas as a named haptic-piezo partner alongside Qorvo (RF/power),
  or keep partner naming out of the deck until portfolios are independently verified?

---

## §8 Provenance

- Born operator brainstorm 2026-06-13; triaged in-session against protocol honesty rails.
- Anchors: `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` (the 6
  accepted surfaces), `docs/path-a-manufacturing-spec.md` (Stage A/B framing),
  `docs/qortroller-devkit-bom-v0_1.md` (advisory-row target), CLAUDE.md
  roadmap_post_stage_1 (L6-Response), `CROSS-LESSON-001` + `BT-CALIB-LESSON-001`
  (separability + three-verification-class discipline).
- This is a DESIGN NOTE. No LIVE claim, no BOM mutation, no surface acceptance until the
  §7 decisions and the Stage A gates resolve.
