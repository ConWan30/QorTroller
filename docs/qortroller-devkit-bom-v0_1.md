# QorTroller Dev-Kit BOM (v0.1 scaffold)

**Status:** v0.1 scaffold — first Rung 2 BOM artifact. Most rows
intentionally carry `UNVERIFIED-EXTERNAL` supplier slots until Sensor B
intelligence populates them. **This document does NOT yet certify any
specific supplier or commit any procurement.** Promotion of an individual
row to `LIVE-SUPPLIED` requires both: (a) Stage A measurement complete
for the part class per Sensor Stack v2.1, AND (b) two verified suppliers
with delivery commitments. Both are multi-cycle future work.

**Origin:** HWFL-1 Cycle 4 (2026-06-10). First DORMANT-to-LIVE conversion
attempt — moves Sensor C's G2.1 from DORMANT to verifier-backed LIVE
on document existence + structural integrity, NOT on supplier
verification. Honest weighting at every level: presence ≠ procurement.

**Audience:** internal hardware-staircase planning. NOT a partner-facing
artifact yet. Partner-handoff package assembler (future Rung 3 work) will
re-render a curated subset once supplier slots are real.

---

## §1 Honesty stamp

The hardest mistake a BOM can make is implying confidence it doesn't
have. v0.1 admits the following:

- **No supplier is committed.** All Supplier-1 and Supplier-2 slots in
  this document are placeholders until Sensor B narrative sources S2–S6
  populate with verified data AND the operator confirms.
- **No part has been Stage A measured against the QorTroller protocol.**
  Sensor Stack v2.1 Empirical Unknown #1 (intra-vs-inter Mahalanobis on
  N=10 players × 100 trigger pulls × 3 contexts) and Empirical Unknown
  #4 (Hall-effect stick same-model same-batch separability on N=20
  stock + N=20 batched-aftermarket) are both OPEN. Until they close,
  any stick or trigger row carrying `LIVE-SUPPLIED` would be lying.
- **The DualSense Edge ships from Sony with potentiometer sticks, not
  Hall-effect.** Aftermarket Hall/TMR retrofit kits exist but are a
  different supply chain. Do not let any future BOM amendment imply
  Sony-OEM Hall sticks; that's the canonical fact-correction in
  Sensor Stack v2.1.
- **Microphone surface is DEFERRED, not absent.** TRACK1-LESSON-002 +
  TRACK1-LESSON-003 establish privacy + multi-mic-literature-doesn't-
  transfer reasons. Lightbar optical witness on Surface 4 is strictly
  preferable on every privacy axis. The microphone row stays as
  DEFERRED placeholder so future cycles cannot silently re-introduce it.

---

## §2 Two-supplier discipline rail

For every Critical part (C1–C8), two supplier slots are MANDATORY.
"Single-source critical part" is a documented failure mode (e.g.
F-DECON-3.2 single-copy MFG CA on the protocol side proves the same
discipline applies to non-physical resources). The slots may be empty
in v0.1 — what they cannot be is collapsed to one column.

Advisory parts (A1–A3) and accessory parts (E1–E3) carry one supplier
slot by default; two is recommended but not required.

| Status code | Meaning |
|---|---|
| `LIVE-SUPPLIED` | Stage A measured + 2 verified suppliers + delivery commit |
| `LIVE-SHORTLIST` | Stage A measured + ≥1 candidate identified; not yet committed |
| `UNVERIFIED-EXTERNAL` | Spec known; supplier intel pending Sensor B narrative |
| `MEASUREMENT-PENDING` | Spec known; gated on Sensor Stack v2.1 Stage A measurement |
| `DEFERRED` | Explicitly out of scope per a documented lesson or decision |

---

## §3 Critical parts (C1–C8)

| ID | Description | Spec ref | Supplier 1 | Supplier 2 | Status | Notes |
|---|---|---|---|---|---|---|
| `C1` | MCU module (ESP32-class, Wi-Fi/BT, USB-OTG ≥ 1000 Hz) | HWFL-1 master prompt RUNG 2; Sensor C G2.2 | _(slot)_ | _(slot)_ | `UNVERIFIED-EXTERNAL` | Espressif ESP32-S3 is the v0.1 reference candidate. Sensor B S6 (Cycle 5): wireless certs via boilerplate, NO Common Criteria/FIPS on landing page — ESP32 alone NOT a substitute for ATECC608A, secure-element pairing required (BOM C2). Cert status: PARTIAL |
| `C2` | Secure element (ECDSA-P256, locked private-key extraction) | `docs/path-a-manufacturing-spec.md` §2 Hardware Requirement | _(slot)_ | _(slot)_ | `UNVERIFIED-EXTERNAL` | ATECC608A/B reference; alternatives YubiKey 5 PIV, STSAFE-A110. Sensor B S2 tracks lifecycle. |
| `C3` | Left analog stick — Hall-effect or TMR | `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` Surface 6 | _(slot)_ | _(slot)_ | `MEASUREMENT-PENDING` | 3 v0.1 candidates: K-Silver JH16 HE, MIDAS 5-pin HE, Magneto TMR. Gated on Empirical Unknown #4 (same-batch separability ≥20%). Sensor B S3/S4/S5 tracks availability. |
| `C4` | Right analog stick — same family as C3 | (same as C3) | _(slot)_ | _(slot)_ | `MEASUREMENT-PENDING` | Same-family-as-C3 discipline: BOM cannot mix Hall + TMR across L/R, breaks calibration corpus assumption. |
| `C5` | IMU (6-axis gyro + accel ≥ 1000 Hz polling) | `docs/path-a-manufacturing-spec.md` §5 PROOF_TIER_FULL requirement | _(slot)_ | _(slot)_ | `MEASUREMENT-PENDING` | Reference candidates ICM-42688-P / BMI270 / LSM6DSO. Stage A measurement Empirical Unknown #1 anchors selection. |
| `C6` | USB-C connector + cable assembly | `docs/path-a-manufacturing-spec.md` §1 reference DualShock Edge USB-C | _(slot)_ | _(slot)_ | `UNVERIFIED-EXTERNAL` | Spec straightforward; supplier selection low-risk; recommend USB-IF certified. |
| `C7` | Adaptive trigger mechanism × 2 (L2 / R2) | `docs/path-a-manufacturing-spec.md` §5 PROOF_TIER_FULL + Sensor Stack v2.1 Surface 1 PRIMARY DISCRIMINATOR | _(slot)_ | _(slot)_ | `MEASUREMENT-PENDING` | The protocol's strongest L4 discriminator runs on this surface — empirically must reproduce Sony-class force-curve fidelity (1 kHz, 8-bit per axis). Custom design likely; off-shelf candidates rare. |
| `C8` | Touchpad capacitive sensor (12-bit X/Y 2-point) | Sensor Stack v2.1 Surface 2 CO-SIGNAL | _(slot)_ | _(slot)_ | `UNVERIFIED-EXTERNAL` | Cypress / Microchip touch IC families. Binding constraint is data volume per session not per-event separability. |

---

## §4 Advisory parts (A1–A3)

| ID | Description | Spec ref | Supplier 1 | Supplier 2 | Status | Notes |
|---|---|---|---|---|---|---|
| `A1` | Lightbar LED array (3-color symbol stream channel) | Sensor Stack v2.1 Surface 4 CO-SIGNAL | _(slot)_ | _(optional)_ | `UNVERIFIED-EXTERNAL` | Used as challenge-response witness channel; passive camera on tournament station observes. Privacy-preferred path vs microphone. |
| `A2` | Microphone array | _(none — DEFERRED)_ | — | — | `DEFERRED` | TRACK1-LESSON-002 (DualSense exposes single mono UAC1 post-DSP, not multi-mic; literature does not transfer) + TRACK1-LESSON-003 (privacy law: BIPA/GDPR/CIPA attach to capture regardless of downstream use). Row preserved so future cycles cannot silently revive it. |
| `A3` | Battery cell + management IC | HWFL-1 master prompt RUNG 2 | _(slot)_ | _(optional)_ | `UNVERIFIED-EXTERNAL` | Drain rate is L4 ADVISORY signal only (4-bit 11-bucket level, multi-min cadence). Spec straightforward. |

---

## §5 Accessory parts (E1–E3)

| ID | Description | Spec ref | Supplier 1 | Status | Notes |
|---|---|---|---|---|---|
| `E1` | PCB substrate (4-layer minimum, controlled impedance for USB-HS) | manufacturing-spec §3 manufacturing ceremony | _(slot)_ | `UNVERIFIED-EXTERNAL` | Stage A bring-up requires reference design before substrate spec finalizes. |
| `E2` | Enclosure (industrial design + ingress rating) | _(none — operator IDH selection)_ | _(slot)_ | `UNVERIFIED-EXTERNAL` | Out of v0.1 protocol scope; tracked for completeness. |
| `E3` | Internal cable harness | _(none)_ | _(slot)_ | `UNVERIFIED-EXTERNAL` | Standard; gated on PCB design. |

---

## §6 Sensor B linkage table

Which Sensor B canonical source unblocks which BOM row when populated:

| Sensor B source | Topic | BOM rows it informs |
|---|---|---|
| `S2.atecc608a-lifecycle` | ATECC608A lifecycle / successors | `C2` |
| `S3.k-silver-jh16-he-stick` | K-Silver JH16 HE | `C3`, `C4` |
| `S4.midas-5pin-he-stick` | MIDAS 5-pin HE | `C3`, `C4` |
| `S5.magneto-tmr-stick` | Magneto TMR | `C3`, `C4` |
| `S6.esp32-cert-status` | ESP32 cert status | `C1` |
| _(no source yet)_ | IMU vendor landscape | `C5` |
| _(no source yet)_ | Adaptive trigger mechanism IP | `C7` |
| _(no source yet)_ | Touchpad IC selection | `C8` |

Future cycles may extend Sensor B's canonical source list to cover the
three "no source yet" rows; that's a Sensor B v0.2 cycle decision.

---

## §7 Promotion criteria

A row may transition `UNVERIFIED-EXTERNAL` → `LIVE-SHORTLIST` when:
- The relevant Sensor B narrative source has populated with concrete
  candidate supplier data AND
- The operator has independently verified one candidate (web review,
  datasheet, contact)

A row may transition `LIVE-SHORTLIST` → `LIVE-SUPPLIED` when:
- Stage A measurement complete for the part class (per Sensor Stack
  v2.1 Empirical Unknown #1 or #4 as relevant) AND
- Two verified suppliers identified AND
- Delivery commitment in writing from each AND
- Operator ceremony explicitly commits

A row may transition `MEASUREMENT-PENDING` → `UNVERIFIED-EXTERNAL`
ONLY after the gating Empirical Unknown closes — Sensor C will not
auto-promote; that's an operator ceremony per the master prompt's
"loop never declares a rung open" rule.

The microphone row (`A2`) cannot transition out of `DEFERRED` without
a documented supersession of TRACK1-LESSON-002 + TRACK1-LESSON-003.

---

## §8 Provenance

- BOM scaffold born HWFL-1 Cycle 4 (`docs/qortroller-devkit-bom-v0_1.md`)
- Verifier: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_verify_g2_1_devkit_bom_exists`
- Sensor C amendment: G2.1 intrinsic-DORMANT → verifier-backed LIVE in
  Cycle 4 commit (point-release v0.1.1 of Sensor C; D-HWFL-13 confirmed)
- Spec anchors: `docs/path-a-manufacturing-spec.md` (Path A v1) +
  `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`
  (Sensor Stack v2.1) + HWFL-1 master prompt RUNG 2 description
