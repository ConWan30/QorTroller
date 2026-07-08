# EDGE-SENSE — The DualSense Edge as Lumen/Retina Hardware

**Design note + first empirical probe, 2026-07-07. Advisory scoping — no flag flips,
no FROZEN-v1 change. Prototype hardware: the operator's existing Sony DualSense Edge
(CFI-ZCP1) — the certified device already in hand. Zero new hardware required.**

## 1. The distinctive claim

Every plane of the trio model (perception / assertion / meaning) currently assumes the
controller is only the *input* device and the *signer*. EDGE-SENSE elevates the same
silicon to a first-class perception device:

1. **Cause-lobe sensor (Lumen).** The Lumen world model's defining move is
   input-conditioned prediction — expected-screen-given-input. The input half of every
   causal prediction IS the Edge's 1000Hz stream (sticks, triggers, IMU). The
   controller isn't *feeding* the world model; it is the world model's cause-side
   sensor array, and it is the only cryptographically certified one in existence.

2. **Haptic-echo witness (Retina-class, screen-independent).** In Remote Play the game
   drives the controller's haptic motors and adaptive triggers (fire feedback, damage
   rumble, explosions). The Edge's own IMU physically *feels* those actuations. That
   makes the controller a game-event perception surface that needs NO screen capture:
   game -> haptic actuation -> IMU signature -> event stream, entirely inside the
   device that signs the PoAC records. **The witness and the signer are one device.**

Why this matters strategically: F-RP2-1 measured that Remote Play's binding constraint
is screen-capture density. The haptic-echo channel is **capture-contention-immune** —
it works at full fidelity when WGC collapses, when there's no capture card, when the
governor downscales. It is the one perception surface Remote Play cannot thin.

The three-lobe session, all joined on the U1 session_id:

```
  input lobe   (HID 1000Hz)        what the human DID          — shipped (KAS HID lobe)
  screen lobe  (retina crops)      what the game SHOWED        — shipped (killfeed/PoSP)
  echo lobe    (game->haptics->IMU) what the game TOLD the      — EDGE-SENSE (this note)
                                   device it did
```

A splice/replay attack now has to forge three mutually-corroborating channels with
consistent latency structure — including one that lives inside certified hardware it
does not control.

## 2. What already exists (nothing here starts from zero)

| Piece | Status |
|---|---|
| 1000Hz IMU capture path | BUILT — `scripts/capture_session.py` (dual-connection fix; N=10 corpus at accel_entropy 4.23) |
| IMU features in the live record stream | LIVE — 334 M14 records carry `micro_tremor_accel_variance` / `tremor_peak_hz` / `tremor_band_power` |
| Haptic-actuation-as-signature precedent | LIVE — PCC 3-signal haptic-tolerance binding (`accel_var >= 3e-4` = "haptics firing", Phase 235-PCC-SPC) |
| Self-issued haptic stimulus machinery | LIVE — Cycle25 tether (amp 12, 1.2s duty, 35ms pulses) + PoEP adaptive-trigger challenge stack |
| Reflex-window discipline | DESIGNED — L6-Response roadmap (80–280ms post-stimulus window; GIC_100 gate long cleared) |
| Session join key | SHIPPED — U1 session_id threads all surfaces |

## 3. First empirical probe — Match 14's own data (P1, run 2026-07-07)

Question: is game-driven haptic actuation visible in the IMU features already captured
during Match 14? (334 feature-bearing records, ~1/s through the match.)

| Population | median accel_var | p90 | over PCC haptic threshold (3e-4) |
|---|---|---|---|
| trigger_active=1 (firing) | 1.22e-4 | 2.02e-4 | 0/4 |
| trigger_active=0 | 2.12e-5 | 1.92e-3 | **77/330 (23%)** |

**Honest findings:**

- **F-ES-1 (substrate confirmed):** the IMU feature stream exists in ordinary match
  data at usable density. The prototype needs no new capture plumbing to begin.
- **F-ES-2 (flag too sparse):** `trigger_active` marked only 4/334 records — record
  granularity (~1/s) under-samples bursty firing. The fire-vs-idle comparison cannot
  be answered from M14 data alone; median 6x elevation on N=4 is a hint, not a result.
- **F-ES-3 (the heavy idle tail):** 23% of non-firing records exceed the PCC haptic
  signature. Something actuates the controller outside trigger moments. Three named
  candidates: (a) game haptics from non-fire events (damage taken, explosions —
  Warzone drives haptics constantly), (b) grip/handling motion, (c) **our own Cycle25
  tether** — the bridge pulses the haptic motor every 1.2s at amp 12. The tether is
  simultaneously a confound AND the calibration asset: a known-schedule, known-amplitude
  self-stimulus. If IMU windows correlate with the tether schedule, the haptic-echo
  channel is demonstrated end-to-end with zero game dependence.
- **F-ES-4 (the instrument gap):** `accel_magnitude_spectral_entropy` read 0.0
  throughout — the live bridge polls ~120Hz, below spectral-feature requirements. The
  discriminator between haptic actuation (motor frequencies, structured) and human
  tremor (4–15Hz) is spectral, so the decisive measurement needs the 1000Hz path —
  which is already built (`capture_session.py`).

## 4. Prerequisite workflow — the ES ladder (verification-first)

- **ES-P0 — RP haptic-forwarding premise (operator, ~2 min).** Confirm PS Remote Play
  on this rig forwards game haptics/adaptive-trigger effects to the USB-connected Edge
  (fire a weapon; feel it). If RP forwards nothing, the echo lobe is HDMI/local-only —
  scope changes, note it. NEVER assumed.
- **ES-P1 — mine captured data. DONE (this note, §3).** Substrate confirmed; sparse
  flag + 120Hz ceiling named.
- **ES-P2 — instrumented 1000Hz capture (rig, ~15 min).** `capture_session.py`-class
  capture during a haptic-rich RP segment, in FOUR sub-segments: tether-on idle
  (known-schedule self-stimulus = channel calibration), tether-off idle (floor),
  tether-off firing-range (game fire haptics), tether-off damage-taking (game damage
  haptics). Deliverable: per-segment spectral profiles.
- **ES-P3 — separation study (offline).** Haptic-band signature vs 4–15Hz tremor vs
  grip motion, from ES-P2 data. Pre-registered bar: haptic events separable from
  human tremor at >=10x band-power ratio with zero false events on tether-off idle.
- **ES-P4 — three-lobe alignment (offline, existing archives + next match).** Echo
  events vs screen kill/hit moments vs HID trigger onsets, joined on session_id;
  latency-consistency structure (echo should LAG input by game+RP latency, co-move
  with screen events). This is the Lumen N5 study gaining its third channel.
- **ES-W — wiring (only after P0–P4 green).** `EchoEvent` stream as an advisory oracle
  into NQPV (declared in `active_oracles` per D-CERT-1 — abstain when absent), fields
  referenced by commitment. Default-OFF, developer_self, never moves presence_score
  uncalibrated. KAS/PoSP schema untouched until the oracle earns a calibrated weight.

## 5. Rails (unchanged, binding)

228B PoAC untouched — the echo lobe emits a separate advisory stream, never touches
the wire. R2∧B2 stands — echo events never open classification windows. Microphone
stays DROPPED (TRACK1-LESSON-002/003) — the IMU-as-vibration-sensor deliberately reads
actuation, not audio; no acoustic reconstruction is in scope, and any future finding
that IMU data reconstructs speech-adjacent content is a stop-and-surface event.
Sub-perceptual stimulus amplitudes only (<=60/255) for any self-issued pulses.
Advisory, default-OFF, `cert_scope=developer_self`, `population_certified=False`.

## 6. Where it lands

- **Ledger:** ES track opens in `audits/rp-close-1-ledger-2026-07-07.md` beside the
  LUMEN track. ES-P2 is the next rig-gated item and can share rig time with any
  future match session.
- **Convergence:** ES-P4 IS LUMEN-3's third channel — the tracks merge at the
  three-lobe causal study. The Edge prototype costs nothing (hardware in hand),
  threatens nothing (advisory), and gives the ecosystem its most distinctive claim:
  **perception inside the certified device.**
