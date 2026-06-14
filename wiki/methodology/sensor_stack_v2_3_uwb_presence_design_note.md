# Sensor Stack v2.3 — UWB Radar Presence (DESIGN NOTE / PROPOSAL)

**Status: DESIGN NOTE — a PROPOSAL, not an accepted architectural revision.**
Proposes one candidate surface (**Surface 9**) for the QorTroller-native sensor
stack. Does NOT supersede `sensor_stack_v2_1_architectural_revision.md` (6 accepted
surfaces) or the v2.2 piezo design note (proposed Surfaces 7–8). No LIVE claim.
Acceptance into a future v2.3 *revision* requires (a) operator acceptance, (b) a
privacy review pass, AND (c) the Stage A measurement passing. Until all three,
this is a measurement-pending candidate only.

**Origin:** operator intelligence pass 2026-06-14 (Decision C2), triaged against
the protocol's honesty + verification discipline. Specs below verified against
Qorvo public sources (product page + product brief), not the relayed narrative
alone.

---

## §0 Honesty stamp (inherited)

Graded, not marketed. Subject to the same same-controller-population separability
constraint (`CROSS-LESSON-001`), the three-independent-verification-classes rule
(`BT-CALIB-LESSON-001`), and — critically — the privacy lens that **dropped the
microphone** (`TRACK1-LESSON-003`). New signals feed EXISTING feature slots /
off-chain analysis; they do NOT expand the 228-byte PoAC FROZEN wire format.

**Verification correction:** the relayed claim of "on-chip AI/ML processing" is
narrowed to what Qorvo publishes — an on-chip **Cortex-M33 + Secure Enclave** with
on-chip compute for ranging / AoA / radar. "AI/ML" specifically is not a verified
Qorvo claim; do not repeat it.

---

## §1 Surface 9 — UWB Radar Embodied-Presence (Qorvo QM35825)

### Concept
A UWB SoC (Qorvo **QM35825**) using radar-based sensing to detect the physical
presence of a body holding/near the controller — micro-motion, gross mass,
and (per Qorvo) vital-sign-class signals. On-chip compute reduces it to a binary
"present/absent" decision exported to the ESP32 over **SPI or UART** (the QM35825
exposes high-speed SPI + UART + GPIO — **NOT I2C**; the relayed "I2C to the ESP32"
was wrong), so the MCU's 1 kHz polling loop is never bogged down by raw radar
processing.

**Verified specs (Qorvo product page, 2026-06-14):** IEEE 802.15.4-2024 + 802.15.4z
(HRP/BPRF/HPRF), **FiRa 3.0 certified**; ranging ±5 cm; 3D AoA ±2°; supply
1.14–3.6 V; interfaces **2× hi-speed SPI slave (40 MHz) + SPI master + UART +
25 GPIO** (no I2C); **Cortex-M33 + Secure Enclave**, Secure Boot/Debug, and
**hardware RSA / SHA / AES / TRNG**; radar modes for motion / presence /
people-counting / vital-sign. Dev kit **QM35825DK-05** (Linux). First fully-
integrated low-power UWB SoC (vendor claim, Mar 2025). (Correction: relayed
"on-chip AI/ML" is narrowed to the Cortex-M33 + on-chip radar/ranging compute —
"AI/ML" is not a verified Qorvo claim.)

### Proposed tier: **ADVISORY — PRESENCE GATE (explicitly NOT an identity surface)**
- **CLAIMS (defensible):** zero-contact "a body is present at the controller now"
  — a fast L9/PoEP presence pre-gate, orthogonal to the adaptive-trigger PoEP
  challenge (C7) and the Surface 7 piezo-acoustic grip-liveness.
- **Does NOT claim:** who the person is. Presence ≠ identity. Cross-session
  controller-identity from radar is out of scope (CROSS-LESSON-001).

### Threat-model honesty
A presence gate **raises spoof cost; it does not close the gap.** A rig with a
moving mass / a warm body nearby can present a "human-present" radar return.
Surface 9 forces an adversary to physically stage presence rather than replay
data — valuable, one signal in a fusion, not a silver bullet.

### The novelty is the BINDING, not the chip
A radar "present" flag is just a flag until it is **cryptographically bound** into
PoEP/attestation. The QM35825's on-chip **Secure Enclave** is the interesting hook
(it could sign/attest the presence assertion at silicon), but the binding
architecture — how a presence flag enters the humanity signal without becoming a
forgeable input — is PROTOCOL work, same lesson as C7 (the binding is the IP, not
the hardware).

### PRIVACY REVIEW RIDER (gating, not optional)
Qorvo markets **vital-sign / respiration** sensing on this SoC. Respiration and
heart-rate are **biometric data**. The same lens that dropped the microphone
(`TRACK1-LESSON-003`: BIPA / GDPR Art. 9 / CIPA attach to capture-and-storage
regardless of downstream use, and ToS consent doesn't reach incidentally-sensed
household third parties) applies here. **Surface 9 v1 must be scoped to a
non-biometric presence/motion decision only** (binary present/absent), with
vital-sign modes DISABLED, OR it cannot exit design-note state. A privacy review
documenting this scope is a hard precondition.

### Stage A gate — Empirical Unknown #7 (NEW, proposed)
> Measure presence-discrimination: human-held-and-present vs desk / clamp / empty
> vs a moving-mass rig, across N≥10 people and a confound matrix (range, angle,
> nearby bystanders, enclosure material). Decision threshold: robust present/absent
> separation across the matrix at a fixed false-positive budget, AND a quantified
> rig-spoof cost. Until #7 closes, Surface 9 is a logged advisory signal, not a gate.

### Verification blocks required (three independent classes, BT-CALIB-LESSON-001)
1. **Vendor spec** — QM35825 datasheet / product brief (radar modes, I2C/SPI
   interface, presence-flag API, power).
2. **Independent prior-art anchor** — UWB radar presence/vital-sign literature
   bounding what it can/can't resolve.
3. **Independent measurement** — the Empirical Unknown #7 dataset on real units.

### PoAC constraint
Surface 9 output is a presence flag (+ optional confidence) feeding the L9/PoEP
pre-gate. No bytes added to the 228-byte PoAC record.

### Layer mapping
| Surface | Sensing | Feeds | Gate before LIVE |
|---|---|---|---|
| **9 UWB radar presence** | Sensing (radar) | L9/PoEP presence pre-gate | Empirical Unknown #7 + privacy review + binding architecture |

---

## §2 Sourcing

**This IS the correct Qorvo lane.** Qorvo's UWB/RF-sensing portfolio is a genuine
fit here (distinct from the ACT88760 power role, BOM A3). Verify the specific
QM35825 variant + presence-flag API against the datasheet before any named
commitment in a partner-facing artifact (BT-CALIB-LESSON-001 / F-HWFL-5-1 rider).

---

## §3 Proposed BOM advisory row (pending acceptance + privacy review + Stage A)

| ID | Description | Status | Notes |
|---|---|---|---|
| `A6` | UWB radar presence SoC (Qorvo QM35825) | `MEASUREMENT-PENDING` | Surface 9; gate Empirical Unknown #7 + privacy review (vital-sign modes OFF) + binding architecture; Qorvo UWB lane; presence-only, NOT identity |

---

## §4 Decisions open for the operator

- **D-UWB-1:** accept this note → fold Surface 9 into a real
  `sensor_stack_v2_3_architectural_revision.md` (which WOULD supersede v2.1 with a
  `[SUPERSEDED-v2.1]` annotation), or hold as a proposal?
- **D-UWB-2:** add the A6 BOM advisory row now (MEASUREMENT-PENDING), or wait?
- **D-UWB-3:** register Empirical Unknown #7 as a canonical Stage A gate?
- **D-UWB-4:** privacy posture — confirm v1 scope is non-biometric presence only
  (vital-sign modes disabled) before any prototype capture.

---

## §5 Provenance

Born operator intelligence pass 2026-06-14 (Decision C2). Specs verified vs Qorvo
public sources. Anchors: `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`
(6 accepted surfaces), `wiki/methodology/sensor_stack_v2_2_piezo_surfaces_design_note.md`
(Surfaces 7–8), `TRACK1-LESSON-003` (privacy), `CROSS-LESSON-001` (separability).
DESIGN NOTE — no LIVE claim, no BOM mutation, no surface acceptance until §4
decisions + the privacy review + Stage A resolve.
