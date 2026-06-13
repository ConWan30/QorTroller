# QorTroller Component Sourcing Sheet (v0.1)

**Purpose:** the friction-free prep sheet for Fusion Stage 3. For each BOM row: a
**specific candidate part number**, **where to download its STEP/3D model**, the **one
spec to verify**, and a confidence flag. When you return to Fusion, you download-and-drop
instead of hunting.

**Honesty rails (inherited):** every part below is a **candidate to verify**, not a
committed supplier. Confidence flags: `SOLID` (well-known part, model readily available),
`CANDIDATE` (plausible, verify availability), `CUSTOM` (must be designed, no off-shelf
model). Nothing here is `LIVE-SUPPLIED` — that needs Stage A measurement + two verified
suppliers per the BOM promotion rules.

**Before you trust any URL:** HEAD-probe it first to skip dead/anti-bot pages —
`python scripts/probe_vendor_urls.py <url> --label sourcing` (the F-HWFL-5-1 lesson).
Vendor sites that are HTTP-only may refuse the AI WebFetch but still work in a browser
(the F-CYCLE17-1 lesson — e.g. K-Silver).

**Model sources glossary:** SnapEDA (free, footprint+STEP), Ultra Librarian (vendor),
GrabCAD (community STEP incl. controller bodies), TraceParts (connectors/hardware),
manufacturer site (authoritative).

---

## Critical parts (C1–C8)

### C1 — MCU module
- **Candidate part:** Espressif **ESP32-S3-WROOM-1** (or -1U) — `SOLID`
- **STEP model:** Espressif site → "ESP32-S3-WROOM-1 3D model / STEP"; or SnapEDA search "ESP32-S3-WROOM-1"
- **Verify:** USB-OTG present + ≥1000 Hz HID capability; module dims ≈ 25.5 × 18 × 3.1 mm
- **Note:** pairs with C2 — ESP32 alone is NOT a secure element (Cycle 5 S6 finding)

### C2 — Secure element
- **Candidate part:** Microchip **ATECC608B** (UDFN-8 production / SOIC-8 for dev) — `SOLID`. Forward option: **ATECC608C-TFLXTLS** (TrustFLEX pre-provisioned).
- **STEP model:** Microchip site → "ATECC608B package 3D"; or SnapEDA "ATECC608B"
- **Verify:** ECDSA-P256, on-chip keygen, key-extraction lock; **polling-based timing** (per the Cycle 16 spec amendment — do NOT spec the NRND 608A for new designs)
- **Alternatives:** YubiKey 5 PIV, ST STSAFE-A110

### C3 / C4 — Analog sticks (same family, L/R)
- **Candidate parts:** **K-Silver JH16** (Hall) or **K-Silver JS16** (TMR) — one vendor, both physics, same form factor (Cycle 17 finding); or **GuliKit** TMR module — `CANDIDATE`
- **STEP model:** GrabCAD search "Hall effect joystick module" / "PS5 stick module"; K-Silver site is HTTP-only (browser, not WebFetch)
- **Verify:** Empirical Unknown #4 (same-batch separability ≥20%) is the real gate — measurement-pending; pin map + dims ≈ 20×20×22 mm
- **Discipline:** C3 and C4 MUST be the same sensing physics — never mix Hall + TMR (breaks the calibration corpus). Note: avoid the "MIDAS 5-pin" candidate until its vendor is re-identified (Cycle 17 provenance-gap finding).

### C5 — IMU (6-axis)
- **Candidate part:** TDK InvenSense **ICM-42688-P** (LGA-14) — `SOLID`. Alternates: Bosch **BMI270**, ST **LSM6DSO**.
- **STEP model:** TDK InvenSense site → "ICM-42688-P 3D"; or SnapEDA
- **Verify:** ≥1000 Hz output data rate; 6-axis gyro+accel; dims ≈ 3 × 3 × 0.9 mm
- **Note:** Empirical Unknown #1 (trigger Mahalanobis) anchors final selection

### C6 — USB-C connector
- **Candidate part:** GCT **USB4085** or Amphenol **12401548E4#2A** (USB-C receptacle) — `SOLID`
- **STEP model:** SnapEDA or TraceParts "USB-C receptacle 16-pin"
- **Verify:** USB-IF certified, data-capable (not power-only), through-hole+SMT hybrid mount

### C7 — Adaptive trigger × 2 (strongest signal surface) — TWO distinct parts

The novelty is **NOT the actuator hardware** (adaptive triggers are patented prior
art). The novelty is the **force-curve liveness extraction** — the protocol reading a
biomechanical 1 kHz force curve that translator hardware can't synthesize and turning
it into a humanity signal. The two parts below serve **different target surfaces** and
must not be conflated:

**C7-actuator — the electromechanical trigger mechanism**
- **Candidate:** **CUSTOM, clean-sheet** — no off-shelf model. Model the lever +
  actuator + linkage yourself (Fusion Stage 6). A DualSense Edge body is a
  **dimensional sanity-check ONLY** — never reshaped/traced (IP hazard).
- **Target surface:** L4 (the force-curve signal source) — the *sensing* of applied
  force. The actuator provides programmable resistance; the **analysis** is the IP.
- **Gate:** freedom-to-operate (FTO) read BEFORE any geometry externalizes, AND Stage A
  separability measurement. `CUSTOM` · `aspirational-primary`.
- **STEP model:** your design (no external source).

**L6-haptic-driver — the piezo feedback driver (a SEPARATE component)**
- **Candidate:** **Boréas BOS1901 / BOS1921** (CapDrive piezo driver) — `CANDIDATE`
  (see Sensor Stack v2.2 design note).
- **Target surface:** L6 active challenge-response (the *stimulus* the protocol issues
  to provoke a reflex) — NOT the trigger actuator. Different surface, different part.
- **STEP model:** Boréas site for the driver IC.
- **Verify:** sub-ms localized pulse for the 80–280 ms reflex window; gated on the L6B
  N≥50 corpus.

**Do not merge these into one "trigger" line** — the actuator (force *sensing* source,
L4) and the haptic driver (reflex *stimulus*, L6) are distinct surfaces.

### C8 — Touchpad
- **Candidate part:** Microchip **MTCH6303** or Azoteq **IQS7211** capacitive touch controller + custom overlay — `CANDIDATE`
- **STEP model:** SnapEDA for the IC; overlay is custom
- **Verify:** 12-bit X/Y, 2-point multitouch; sensor area ≈ 50 × 30 mm

---

## Advisory parts (A1, A3)

### A1 — Lightbar LED
- **Candidate part:** addressable RGB (**WS2812B**) or simple RGB LED array — `SOLID`
- **STEP model:** SnapEDA "WS2812B"
- **Verify:** brightness for camera-witness read at tournament-station distance

### A3 — Battery + charger
- **Candidate parts:** 3.7 V LiPo pouch ~500 mAh (generic) + charger IC — `CANDIDATE`
- **Charger IC note:** TP4056 works for basic linear charge; if you ever want USB-C PD or smarter management, **TI BQ24075** is a better candidate. (Do NOT spec a piezo-harvesting PMIC — that idea was rejected as a power solution; see Sensor Stack v2.2 §5.)
- **STEP model:** GrabCAD "LiPo pouch 503450"; SnapEDA for the charger IC
- **Verify:** dims ≈ 50 × 35 × 6 mm; capacity vs ESP32-S3 active-radio draw

---

## Accessory (E1)

### E1 — PCB mainboard
- **Approach:** design in **KiCad** (free), export STEP into Fusion — `CUSTOM`
- **Verify:** 4-layer minimum, controlled impedance for USB-HS; outline ≈ 95 × 55 × 1.6 mm

---

## Stage 3 download order (when you return to Fusion)

Biggest fit-risk first, so surprises surface early:

1. **Envelope sanity-check (optional)** — a DualSense Edge body from GrabCAD for **dimensional comparison ONLY** (does my design fit a similar hand-envelope?). Never reshape or trace it — model from primitives. FTO read before any geometry externalizes.
2. **C3/C4 stick module** — GrabCAD Hall/TMR module
3. **C1 ESP32-S3-WROOM-1** — Espressif/SnapEDA
4. **C5 ICM-42688-P** — TDK/SnapEDA
5. **C2 ATECC608B** — Microchip/SnapEDA
6. **C6 / C8 / A1 / A3** — SnapEDA/TraceParts/GrabCAD as you go

For each: `Insert → Upload` the STEP, move it onto its colored placeholder block, then
suppress/delete the block. The block dimensions already match these candidates' nominal
sizes, so the real part should drop in close.

---

## Honest reminders

- Every `CANDIDATE` part needs availability + datasheet verification before it enters a
  pitch as fact.
- The stick (C3/C4) and trigger (C7) rows stay `MEASUREMENT-PENDING` regardless of how
  good the model looks — Stage A measurement is the gate, not the render.
- Two-supplier discipline applies to all critical parts before `LIVE-SUPPLIED`.

---

## Provenance

Born 2026-06-13. Part candidates reflect BOM v0.1 + Cycle 16 spec amendment (608B/608C
family) + Cycle 17 stick intel (K-Silver dual Hall/TMR, GuliKit TMR, MIDAS provenance
gap) + Sensor Stack v2.2 piezo note (Boréas driver). All part numbers are candidates to
independently verify, never committed suppliers.
