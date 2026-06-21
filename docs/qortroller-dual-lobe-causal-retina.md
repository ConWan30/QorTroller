# Dual-Lobe Causal-Coherence Retina (OCR × Trio-Retina) — QorTroller-exclusive fusion

**Status:** prototype core, `UNCALIBRATED`, default-off. No FROZEN/PoAC/chain touch.
Pairs with [[project_l9_retina_fusion_capture_rig]] and the presence↔retina binding work.

## The idea in one line

QorTroller already uses Trio-Retina as a model-agnostic encoder over the **controller input
stream** (the INPUT world). Add a second lobe that encodes the **game screen** via OCR (the
OUTCOME world), and fuse them by **causality**: every on-screen outcome must be explained by
a preceding controller input from *this certified device*.

## Why this is exclusive to QorTroller

Screen-OCR anti-cheat is ordinary — anyone can watch a game feed. The moat is that
QorTroller has a **cryptographically-anchored input world-model**: the controller lobe
(`retina_controller_embedder.py`) encodes the 1 kHz HID window into retina `WorldState`/
`Event`s and anchors them through events-root → `state_commitment` → DA-witness → w3bstream
→ PDA attestation. Binding an OCR outcome stream to *that* certified input stream is the
exclusive capability. Nobody without the certified controller lobe can reproduce the bind.

## The two lobes

| Lobe | Source | retina detector | Events |
|------|--------|-----------------|--------|
| Controller (exists) | 1 kHz HID window | `qortroller-controller-v1` encoder | `controller.trigger.onset`, `controller.stick.radial_jump`, `controller.trajectory.anomalous`, `controller.tremor.anomalous` |
| Screen (new) | game video / OCR of HUD | OCR now; YOLO/VLM/Grounding DINO later | `scene.down_advanced`, `scene.first_down`, `scene.score_changed` (input-caused); `scene.playclock_reset`, `scene.quarter_changed` (markers) |

OCR is the right *first* screen detector for NCAA CFB: the HUD is dense, discrete, and
legible. YOLO/Grounding DINO/VLM (snap detection, tackle detection, ball tracking) are
higher-fidelity upgrades that emit into the *same* event schema — the fusion is detector-
agnostic by construction.

## The fusion: input → outcome causal coherence

`retina_causal_coherence.assess_coherence` matches each **input-caused** outcome to a
controller input event within a play-length window `[t − window_s, t]` (default 10 s).

- **COHERENT** — outcomes explained by preceding input (a live human playing).
- **ORPHAN_OUTCOME** — the screen advanced (down/score changed) with no explaining input on
  the certified device → relay (human drives screen B, bot on certified A), replay against a
  live screen, or a spectator feed. **The flag case.**
- **ORPHAN_INPUT** — heavy input, ~no outcomes → informational (failed plays, defense,
  menu); NOT a cheat by itself.
- **INSUFFICIENT** — too little evidence.

This generalizes L9/PoCP stick→camera coupling into **input-trajectory → game-outcome
semantics**. It does NOT try to solve aim-assist-vs-pro-skill (that stays a trajectory-ROC
problem on the controller lobe); it adds *contextual disambiguation* across presence/relay/
replay — exactly the worth-thesis of the consistency engine.

## How it composes with existing work

- Both lobes share the same `record_hash` / `state_commitment` chain, so the causal link is
  itself DA-witnessed and PDA-attestable — provable, not merely computed.
- The screen lobe reuses `probe_screen.read_screen_region` (cocapture `ScreenCapturer` +
  pytesseract) for the OCR edge; the fusion is pure over a normalized `TimedEvent` stream.
- It slots beside `presence_retina_consistency` as a new **Outcome** axis: Presence ×
  Trajectory × L4 × **Input-Outcome-Coherence**.

## Honest scope (what this prototype is NOT)

- `UNCALIBRATED`: the causal map (which input types cause which outcomes) and the 10 s window
  are a **hypothesis**. They need a real co-capture experiment (controller lobe + OCR lobe in
  one bound session, with known HUMAN / RELAY / REPLAY labels) before any calibrated score —
  the same posture the consistency engine takes (`UNCALIBRATED_SYNTHETIC`).
- Score OCR is provisional (scoreboard glyphs are noisy); down/distance/play-clock are the
  load-bearing fields.
- Not wired into the live bridge perception loop; default-off pure core + tests only.

## Files

- `bridge/vapi_bridge/retina_screen_lobe.py` — `parse_hud` (OCR text → `HudState`),
  `diff_hud` (transitions → `ScreenEvent`s), conservative (an OCR dropout never fabricates).
- `bridge/vapi_bridge/retina_causal_coherence.py` — `TimedEvent` normaliser + adapters +
  `assess_coherence` → `CoherenceReport` (`UNCALIBRATED`).
- `bridge/tests/test_retina_causal_coherence.py` — 22 pure tests (parse, diff, fusion).

## Next (gated, not built)

1. Real co-capture experiment to calibrate the causal map + window and measure
   ORPHAN_OUTCOME separation on labelled HUMAN / RELAY / REPLAY sessions.
2. Upgrade the screen lobe with retina-native YOLO/Grounding DINO snap/tackle detectors
   (same event schema) for setups where the video feed is available.
3. Emit the screen lobe through the existing events-root → state_commitment → DA-witness
   chain so outcome events are anchored identically to controller events.
