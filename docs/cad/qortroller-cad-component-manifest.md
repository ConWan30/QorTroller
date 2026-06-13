# QorTroller CAD Component Manifest (v0.1)

**Purpose:** the assembly shopping-list that turns the HWFL-1 dev-kit BOM
(`docs/qortroller-devkit-bom-v0_1.md`) into a CAD-ready component set. For each
part: nominal dimensions (for blockout/clearance), where to get a *real* STEP/3D
model, the function, and the exploded-view annotation text for the pitch render.

**Status discipline (inherited from the BOM):** dimensions marked `≈` are
**nominal placeholders for concept blockout only** — they are NOT verified against
a datasheet yet. Replace each with the real manufacturer STEP file before any
dimension is presented as fact to Qorvo / Battle Beaver / a manufacturer. The BOM
status code travels with each row so the CAD model never implies more confidence
than the hardware loop has earned.

**How to use:** in your CAD hub (Fusion 360), create one component per row, set its
bounding box to the nominal dims to block out fit, then swap in the real STEP as you
download it. The `Annotation` column is the callout text for the exploded view.

---

## Where real component models come from (sources)

| Source | What it gives | Notes |
|---|---|---|
| **Manufacturer site** | Authoritative STEP/IGES | Espressif, Microchip, TDK/InvenSense, Bosch, ST all publish 3D CAD |
| **SnapEDA** | PCB footprint + 3D STEP | Free; great for ICs/connectors |
| **Ultra Librarian** | Footprint + 3D | Vendor-backed |
| **GrabCAD** | Community STEP (incl. DualSense / Edge reference bodies) | Verify dims; community-made |
| **TraceParts / 3DContentCentral** | Connectors, hardware, fasteners | Industrial standard parts |

**Reachability tip:** before manual hunting, HEAD-probe candidate URLs with the
HWFL-1 prober — `python scripts/probe_vendor_urls.py <url> --label cad-src` — to
route around dead/anti-bot pages (the same F-HWFL-5-1 lesson that bit the Cycle 5
vendor research; see `audits/url-reachability-cycle-17-2026-06-13.md`).

---

## Critical parts (C1–C8)

| BOM | Component | Nominal dims (blockout) | Real-model source | Function | Exploded-view annotation |
|---|---|---|---|---|---|
| **C1** | MCU module — ESP32-S3 (Wi-Fi/BT, USB-OTG ≥1000 Hz) | ≈ 25.5 × 18 × 3.1 mm (ESP32-S3-WROOM-1 module) | Espressif → "ESP32-S3-WROOM-1" STEP; SnapEDA | The brain: runs firmware, polls sensors at 1 kHz, builds the 228-byte PoAC record, talks USB-HID + BT | "C1 — ESP32-S3 MCU · 1 kHz sensor poll · builds Proof-of-Autonomous-Cognition record" |
| **C2** | Secure element — ATECC608B/608C-class (ECDSA-P256, non-extractable key) | ≈ 4 × 3 × 0.6 mm (UDFN-8) / SOIC-8 dev variant | Microchip → "ATECC608B" STEP; SnapEDA | Hardware root of trust: holds the device private key that signs every renewal; key never leaves silicon | "C2 — Secure Element (ATECC608B) · on-chip P-256 key · silicon root of trust" |
| **C3** | Left analog stick — Hall-effect *or* TMR (same family as C4) | ≈ 20 × 20 × 22 mm (module incl. shaft/gimbal) | GrabCAD "Hall effect joystick module"; K-Silver / GuliKit if STEP available | Drift-free analog position; per-unit noise-floor is an L4 biometric fingerprint surface | "C3 — Left stick (Hall/TMR) · contactless · drift-free · L4 fingerprint surface" |
| **C4** | Right analog stick — same family as C3 | (same as C3) | (same as C3) | Same as C3; same-family L/R is mandatory (mixing Hall+TMR breaks the calibration corpus) | "C4 — Right stick (same family as C3) · L/R must match sensing physics" |
| **C5** | IMU — 6-axis gyro+accel ≥1000 Hz | ≈ 3 × 3 × 0.9 mm (ICM-42688-P LGA-14) | TDK InvenSense → "ICM-42688-P" STEP; or Bosch "BMI270"; or ST "LSM6DSO" | Motion + gravity vector; gravity-postural fingerprint (AIT) + anti-spoof IMU/HID discrepancy check | "C5 — 6-axis IMU · gravity-postural biometric (AIT) · injection-detect" |
| **C6** | USB-C connector + cable | ≈ 9 × 7.5 × 3.2 mm (receptacle) | TraceParts / SnapEDA "USB-C receptacle"; USB-IF | Wired data path (the protocol's exclusive-capture link) + power/charge | "C6 — USB-C · exclusive-capture data link · 1 kHz HID over USB" |
| **C7** | Adaptive trigger × 2 (L2/R2) | ≈ 30 × 18 × 25 mm per trigger assy (motor + geartrain + lever) | **Custom — model from scratch**; DualSense Edge trigger as ref geometry (GrabCAD) | **The novel IP.** Programmable force-curve; the strongest anti-cheat discriminator (translator HW can't synthesize a biomechanical 1 kHz force curve); doubles as a challenge-response channel | "C7 — Adaptive trigger ×2 · programmable 1 kHz force-curve · PRIMARY anti-cheat discriminator + challenge channel" |
| **C8** | Touchpad — capacitive 12-bit X/Y 2-point | ≈ 50 × 30 × 1.5 mm (sensor area) | Microchip/Cypress touch-IC STEP + custom overlay | 2-point capacitive input; co-signal data-volume surface | "C8 — Capacitive touchpad · 12-bit 2-point · co-signal surface" |

---

## Advisory parts (A1, A3) — A2 microphone is DEFERRED (do not model)

| BOM | Component | Nominal dims | Real-model source | Function | Annotation |
|---|---|---|---|---|---|
| **A1** | Lightbar LED array (3-color symbol stream) | ≈ 20 × 4 × 1.2 mm (LED strip) | SnapEDA RGB LED; or generic strip | Optical challenge-response witness channel (passive tournament camera reads host-issued symbol stream) — the privacy-preferred presence channel | "A1 — Lightbar · optical challenge-response witness · privacy-preferred vs mic" |
| **A3** | Battery cell + management IC | ≈ 50 × 35 × 6 mm (LiPo pouch) + PMIC | GrabCAD LiPo pouch; SnapEDA PMIC | Power; drain-rate is an L4 *advisory* signal only (coarse, 4-bit) | "A3 — Battery + PMIC · drain-rate advisory signal (coarse)" |
| ~~A2~~ | ~~Microphone~~ | — | — | **DEFERRED** — do NOT place in the model. TRACK1-LESSON-002/003 (multi-mic literature doesn't transfer + BIPA/GDPR/CIPA privacy). Modeling it would re-introduce a retired surface. | (omit) |

---

## Accessory parts (E1) — structural

| BOM | Component | Nominal dims | Real-model source | Function | Annotation |
|---|---|---|---|---|---|
| **E1** | PCB substrate (4-layer min, controlled-Z for USB-HS) | ≈ 95 × 55 × 1.6 mm (main board outline) | **Design in KiCad → export STEP** | The board everything mounts to; defines internal real-estate | "E1 — 4-layer mainboard · controlled-impedance USB-HS" |
| **E2** | Enclosure shell | (the thing you're designing) | **Start from DualSense Edge ref (GrabCAD), reshape in Fusion** | Ergonomic housing; the printable part | (the shell itself) |
| **E3** | Internal cable harness | route-dependent | model as swept pipes in Fusion | Interconnect; gated on PCB layout | "E3 — harness" |

---

## Assembly notes (fit + clearance reality)

1. **Block out E1 (the mainboard) first.** Everything else is positioned relative to it. C1/C2/C5/C8-IC mount on it; C3/C4/C7 mount through/around it.
2. **C7 triggers are the space hogs and the IP** — reserve the front-shoulder volume early; they drive the overall envelope.
3. **Same-family stick rule (C3=C4)** — model them as one component, instanced twice mirrored, so you cannot accidentally show mixed sensing physics.
4. **Keep C2 (secure element) visually distinct** in the exploded view — it's the cryptographic story that makes QorTroller *QorTroller*, not just another pad. Give it its own callout color.
5. **Leave the A2 microphone cavity absent** — its absence is a deliberate, presentable privacy decision; note it on the slide.
6. **Target print envelope:** the assembled controller is ≈ 160 × 105 × 65 mm — confirms you need a printer bed of at least ~180 × 180 mm to print the shell halves flat. (Verify once the shell is modeled.)

---

## Sync to the hardware loop

Every row here traces to a BOM row, which traces to a Sensor C gate, which traces to
a Sensor B intel source. The provenance chain the manufacturer pitch can show:

```
Sensor B (supply intel)  →  BOM C-row (part spec + status)  →  CAD component (this manifest)  →  exploded-view callout (the slide)
```

When a BOM row is still `MEASUREMENT-PENDING` (C3/C4/C5/C7), the CAD callout should
say so — e.g. "candidate geometry, Stage A measurement pending" — so the model is as
honest as the loop. Never let the polished render imply a part is locked when the BOM
says it isn't.
