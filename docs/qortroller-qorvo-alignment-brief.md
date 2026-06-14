# QorTroller × Qorvo — Alignment & Synergy Brief

**Date:** 2026-06-14
**Purpose:** open a design-enablement conversation with Qorvo for the silicon layer
of the QorTroller controller. **This is not a grant request** — Qorvo's engagement
model is design enablement (samples, eval kits, FAE/Design-Hub support, UWB Partner
Program, RF Accelerator), and that's exactly what's asked here.
**Status discipline:** every part is an `UNVERIFIED-EXTERNAL` candidate or
`MEASUREMENT-PENDING` surface — specs below are verified against Qorvo's public
product pages (2026-06-14); nothing is a committed BOM line.

---

## 1. One line + why silicon

**QorTroller is the reference controller for V.A.P.I. — a DePIN category where the
physical input device is also the cryptographic owner of the data it produces.**
The protocol already runs (testnet); the missing layer is purpose-built silicon.
Qorvo is the natural fit for three of its hardware surfaces: **power, UWB presence
sensing, and RF front-end.**

## 2. Why this isn't vaporware (the credibility anchor)

The backend + bridge are built and running on IoTeX testnet — the hardware slots
into a *working* system, not a concept deck:

| Proof point | Value |
|---|---|
| Cryptographic record | 228-byte Proof-of-Autonomous-Cognition per cognition cycle (FROZEN wire format) |
| Automated tests | ~5,766 |
| Deployed contracts (IoTeX testnet 4690) | 66 deployed / 58 active |
| Fail-closed CI invariants | 174 / 174 |
| Grind-integrity chain | GIC_100 reached |
| Biometric separation (A.I.T.) | ratio 1.199, N=37 |
| Reference device today | DualSense Edge (CFI-ZCP1), real-controller capture live |

The honest gaps are stated up front (§6): testnet-only, no token, no external audit,
N=3 player corpus, no hardware yet. The point of engaging Qorvo is to build that
hardware layer.

## 3. Qorvo product-line mapping (verified specs)

| QorTroller need | Qorvo line | Specific part | Role in the architecture | Status |
|---|---|---|---|---|
| **Power-rail integrity** | PMIC | **ACT88760** (eval: ACT88760EVK-102.E2) | 13 rails (7 bucks + 6 LDOs), 2.6–5.8 V in / 0.5–3.8 V out, WLCSP-81; clean multi-rail regulation against RF/compute current spikes for the 1 kHz sense path; preserves ESP32-S3 deep-sleep | `UNVERIFIED-EXTERNAL` candidate (BOM A3) |
| **UWB presence / sensing** | UWB SoC | **QM35825** (dev kit: QM35825DK-05, Linux) | L9 Embodied-Presence (Sensor Stack v2.3, Surface 9): radar presence detection; ±5 cm ranging, 3D AoA ±2°, 1.14–3.6 V, SPI/UART; **Cortex-M33 + Secure Enclave + HW RSA/SHA/AES/TRNG** → on-silicon hook for binding presence into attestation; FiRa 3.0 / 802.15.4z | `MEASUREMENT-PENDING` (design-note proposal) |
| **RF front-end** (BT telemetry + Wi-Fi OTA on the ESP32-S3 path) | RF FEMs / BAW-SAW filters / coexistence | _(to identify with FAE)_ | clean RF for the wireless DePIN node (BT broadcast + Wi-Fi OTA) | `CANDIDATE` (part TBD) |

**Honest exclusions (not Qorvo — stated so the ask is precise):**
- Secure element → Microchip **ATECC608B/608C-class** (BOM C2)
- Adaptive-trigger actuation → **Boréas** (piezo haptic) / custom mechanism (BOM C7)
- Analog sticks → **K-Silver JH16 (Hall) / GuliKit (TMR)** (BOM C3/C4)
- IMU → TDK / Bosch / ST (BOM C5)

## 4. What QorTroller needs *accessible* from Qorvo (the asks)

1. **UWB Partner Program** entry — register at `qorvo.com/innovation/ultra-wideband/partners/registration` (program connects to Design House / Turn-Key / Certification partners across NA/EMEA/APAC). The sharpest near-term door, directly aligned with the QM35825 / Surface 9 work.
2. **Eval kits / samples** (via Design Hub / distributor / sales): **QM35825DK-05**, **ACT88760EVK-102.E2**.
3. **FAE / Design-Hub support** — RF front-end part selection + reference designs.
4. **RF Accelerator** (mentoring + open-hardware + crowdfunding for IoT/wireless RF) — a parallel ecosystem track.
5. **Datasheets + reference designs** for the three parts above.

## 5. How it integrates with the established backend/bridge

```
human input → sensors → ESP32-S3 MCU builds 228-byte PoAC → ATECC608B signs → IoTeX
              ▲ Qorvo QM35825 (UWB presence, L9, via SPI/UART)
              ▲ Qorvo ACT88760 (power rails for the 1 kHz loop)
              ▲ Qorvo RF FEM (BT telemetry + Wi-Fi OTA path)
```
The bridge service (Python asyncio) already defines the firmware↔backend contract
(the 228-byte record, consent, GIC chain). Qorvo silicon slots into a running
pipeline — power integrity, an SPI/UART presence flag, and the RF path — **not a
clean-sheet product Qorvo has to architect.** That's the de-risk for a supplier.

## 6. Honest status — conceptual framework vs. tested

QorTroller is a **conceptual framework proven in software, with hardware as the
testable next phase.** Each hardware claim is gated on a named Stage A measurement
and stays `MEASUREMENT-PENDING` until it passes:

| Surface | Stage A gate (must pass before any LIVE claim) |
|---|---|
| Adaptive trigger (C7) | Empirical Unknown #1 — intra-vs-inter-player trigger Mahalanobis > 1.0 |
| Sticks (C3/C4) | Empirical Unknown #4 — same-batch separability ≥ 20% (per sensor physics) |
| Piezo surfaces (7/8) | Empirical Unknowns #5/#6 (acoustic liveness / reflex SNR) |
| UWB presence (Surface 9) | Empirical Unknown #7 — human-present vs desk/rig discrimination + rig-spoof cost; **+ privacy review (vital-sign modes off)** |

We never claim "unbeatable" — each surface *raises spoof cost, pending measurement.*
That discipline is the whole protocol's credibility, and it's how we'd run the
Qorvo-enabled hardware bring-up too.

## 7. The ask

A 30-minute design conversation + UWB Partner Program entry + eval-kit sampling
(QM35825DK-05, ACT88760EVK-102.E2). We bring a running protocol, a defined BOM, a
digital prototype, and a measurement plan; Qorvo brings the silicon, eval hardware,
and design support. Goal: a reference dev-kit bring-up path.

## 8. Attachments (the rest of the packet)

- Architecture diagram — `cad/out/qortroller_architecture.png`
- Dev-kit BOM (v0.2) — `docs/qortroller-devkit-bom-v0_1.md`
- Path A silicon/cert spec — `docs/path-a-manufacturing-spec.md`
- Sensor Stack v2.2 (piezo) / v2.3 (UWB) design notes — `wiki/methodology/`
- CAD model (STEP) — `cad/out/qortroller_layout.step`
- Project assessment — `docs/qortroller-project-assessment-2026-06-13.md`

## 9. Provenance

Born 2026-06-14. Qorvo specs verified vs `qorvo.com` product pages
(ACT88760, QM35825) + UWB Partner Program page. Engagement-model framing verified
(Qorvo = design enablement / UWB Partner Program / RF Accelerator, not a cash grant).
All vendor data independently re-verify before any externalized commitment
(BT-CALIB-LESSON-001). IoTeX remains the protocol's L1 home; this brief advances the
hardware track in parallel while the Halo grant program is paused.
