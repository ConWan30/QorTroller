---
type: synthesis
id: s-multi-channel-presence-gate
title: Multi-channel input→screen presence gate — one unifying principle (a vaulted-controller input CAUSES a deterministic on-screen change at bounded latency) spanning geometric coupling (stick→pan, refined by the decoupled-energy gate), trigger→HUD event coupling (fire→bloom / hit→red-hitmarker / ADS→scope), and the novel recoil-compensation closed-loop. All channels read the SAME burst frames + the 1000Hz vaulted controller (zero extra capture/lag); fused by latency-consistency anti-spoof; per-game HUD discipline; phased build, plan-before-code.
created: 2026-06-27T19:30:00Z
modified: 2026-06-27T19:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

CYCLE 49. Operator `/goal` 2026-06-27: after the coupling-threshold campaign (10–15+ min active-aim,
Remote-Play/Warzone, dev-cert), analyze the corpus as a STAPLE and deep-design the FULL multi-channel gate
(geometric + trigger→HUD) plus any aligned novel QorTroller-exclusive proofs, before writing channel code.
This note is the architecture; the recoil-compensation channel gets its own note
([[s-recoil-compensation-coupling]]) per the operator's "could become its own layer."

## 0. The staple (what the campaign proved — `audits/coupling-calibration-2026-06-27.md`)

Channel A (geometric) is REAL and calibratable in the Remote-Play/Warzone regime: 52 computed windows,
null max 0.055, genuine coupling med 0.114. The operator's decoupled-energy gate is empirically decisive —
gating walking/world-scroll windows took the FAR-safe calibration from TPR 0.85 → **1.00** at the same null
(`calibrate()` ADOPTABLE-PROVISIONAL, dev-cert). The old 0.20 default is far too strict (TPR 0.08). This corpus
+ `coupling_threshold_calibration.gate_coupled_by_decoupled_energy` is the reusable foundation every later
channel calibrates against — same FAR-controlled honesty rails, same structured-negative anti-GCAP gate.

## 1. The unifying principle (why these are ONE gate, not three features)

Every channel has the SAME shape: **a controller input that QorTroller already holds as ground truth (1000 Hz,
off the cryptographically-vaulted certified device) CAUSES a deterministic change on the screen we are already
capturing, with a bounded, session-consistent latency.** The proof is the temporal+causal coupling between the
precisely-known input and the observed screen response — NOT the screen alone, NOT the input alone.

This is QorTroller-EXCLUSIVE for one structural reason: QorTroller is the only system that simultaneously holds
(a) the certified controller's precise input telemetry AND (b) the retina capture of the same session. A cloud
anti-cheat sees only the input stream; an OCR/vision cheat-detector sees only the screen. QorTroller sees BOTH
and can demand they cohere. The whole gate is "prove the human's hands and the human's screen are the same
causal system, live."

A second structural gift: the channels share ONE session render+stream latency (Remote Play ≈ 50–150 ms,
estimated per session). That shared latency is itself an anti-spoof: a forged channel that injects fake screen
events will not match the real pipeline latency the other channels measure. Latency-consistency across channels
is the load-bearing forgery test (§4).

## 2. The channels

### Channel A — Geometric coupling (EXISTING, refined this cycle)
- input: right stick (camera/aim); screen: global optical-flow pan; math: |causal Pearson r| + time-shuffled null.
- refinement (this cycle): decoupled-energy gate keeps right-stick-DRIVEN windows, drops walking world-scroll.
- strength: continuous, scale-invariant (catches micro-aim-while-still — Pearson r is magnitude-independent).
- weakness: a single correlation; a bot faking stick + a synced pan can mimic it. Needs the other channels.

### Channel B — Trigger→HUD event coupling (NEW — operator's crosshair idea)
- **B1 fire→bloom**: R2 onset (1000 Hz) → center-ROI luminance/motion spike (muzzle flash + reticle bloom +
  recoil kick) at bounded latency. Coupling = consistent lag + co-occurrence of fire-telemetry and center spike.
- **B2 hit→red-hitmarker**: a landed fire → brief center-ROI RED spike (hitmarker / reticle turns red).
  STRONGEST anti-spoof in B: the red marker is GAME-STATE-driven (only on a real hit), so forging it requires
  forging game state, not just input.
- **B3 ADS→scope**: L2 held → large full-frame state change (scope vignette / FOV shift) gated to L2 hold.
- strength: discrete EVENT coupling; harder to fake than continuous flow.
- weakness: GAME-SPECIFIC (Warzone reticle/hitmarker colors + ROI geometry); needs per-game templates + its
  own FAR/FRR. Game-agnostic core (A, C1) carries non-HUD games; B is the per-game layer.

### Channel C — Novel QorTroller-exclusive proofs (operator's "if anymore aligning novel proofs")
- **C1 recoil-compensation closed-loop** (HEADLINE — own note [[s-recoil-compensation-coupling]]): R2 fire →
  on-screen recoil kick UP → the human pulls the right stick DOWN to compensate at human reflex latency
  (80–280 ms). The stick correction is CAUSED by the on-screen recoil — a closed sensorimotor loop. Directly
  defeats anti-recoil macros (the #1 Warzone cheat): a static macro yields an inhuman, screen-independent
  signature; a human yields reactive, variable-latency compensation bound to the actual on-screen kick.
- **C2 kill→target-switch**: elimination event → a burst of re-aim within a human reaction window (overlaps A+B2).
- **C3 damage→reaction**: flinch/red-edge vignette → reposition/juke input (weaker, variable; advisory only).
- **C4 UI input→screen-state**: map/inventory/options button → deterministic full-screen UI appears — a cheap,
  low-frequency SESSION-INTEGRITY check (human-shaped menu navigation), not a per-fight proof.
- **C5 aim-assist-friction coupling** (research-tier): constant stick input + a screen-pan DECELERATION = the
  crosshair crossed a target (rotational aim-assist friction). Subtle, console-specific, hard to fake; defer.
C1 is the one to build (anti-cheat-valuable + presence proof + QorTroller-exclusive). C2–C5 are catalogued so
future cycles cannot silently re-discover them; only C1 + C4 graduate to the build plan (§5).

## 3. Why this folds into the EXISTING burst (the honest cost statement)

ALL channels analyze the SAME captured burst frames + the SAME 1000 Hz telemetry already on hand. B/C add ROI
luminance/color/template stats to the optical-flow the retina already computes — **extra analysis, NOT extra
capture**. So the multi-channel gate does NOT add capture cost or gameplay lag beyond the single burst (the
lean+on-demand model is preserved: zero capture during play, one burst on request, then GPU released). This is
the load-bearing feasibility point: richer proof at the same observer-effect cost.

## 4. Fusion + anti-spoof

- per channel: coupling_score + null + a per-channel FAR-safe threshold, calibrated exactly like A
  (`calibrate()` + structured negatives). Each channel keeps its own ADOPTABLE/INSEPARABLE/INSUFFICIENT verdict.
- presence verdict (two modes): (i) CONJUNCTION — require ≥K channels COUPLED for the strong claim; (ii) GRADED
  presence probability — weighted evidence sum (the humanity-formula pattern) for a soft score.
- **latency-consistency is the primary forgery test**: estimate the session render+stream lag once
  (cross-correlation; the oracle already surfaces `lag_ms`/`lag_window_ms`), then require every channel's
  input→screen lag to fall in the same session band. A spoof that fabricates one channel breaks the shared-lag
  invariant. This is novel and QorTroller-exclusive (needs both halves to even measure).
- anti-GCAP per channel: structured negatives (auto-camera / replay / spectator POV) beat the shuffle null;
  every channel stays PROVISIONAL until its structured-negative set is added (mirrors the NQPV study + the
  coupling-calibration rail already in code).

## 5. Phased build plan (plan-before-code; each phase = corpus → calibrate → structured-neg → tests → adopt)

- **P0 DONE** (this cycle): channel A + decoupled-energy calibration FILTER (analysis-time) + staple corpus.
- **P1 live decoupled-energy gate** in the oracle: per-burst RELATIVE rank (keep lowest-DE fraction) — NOT an
  absolute DE threshold (DE runs 0.97–0.99 in busy scenes; absolute cuts are scene/game-fragile). Makes channel
  A work on natural play (no forced panning). Smallest, highest-leverage next step.
- **P2 channel B1** (fire→bloom): R2 telemetry + center-ROI luminance spike + latency-align. Simplest event
  channel; proves the trigger→HUD pipe.
- **P3 channel B2** (hit→red-hitmarker): center-ROI red detector + game-state coupling. The strong anti-spoof.
- **P4 channel C1** (recoil-compensation): the novel anti-cheat proof — own corpus, own calibration
  ([[s-recoil-compensation-coupling]]).
- **P5 channel B3 (ADS) + FUSION + latency-consistency verdict** — assemble the multi-channel gate + the
  shared-lag forgery test.
Each phase ships behind a default-off flag, dev-cert/advisory, with its own FAR-safe calibration before any
verdict weight. No phase changes FROZEN-v1, the 228B PoAC, the chain, or spends IOTX.

## 6. Honest boundaries

- advisory presence oracles, NOT identity, NOT a FROZEN primitive, NOT on the 228B wire — same scope as all L9
  presence work.
- per-game HUD channels (B) are game-specific; the game-agnostic core is A (+ C1 where the game has recoil).
- everything is dev-cert / single-subject until population validation (the breadth lever, BCC-harvested).
- the capture observer-effect (burst lag) is unchanged; multi-channel is analysis, not more capture.
- per-regime: Remote-Play thresholds ≠ native-PC thresholds; label corpora by regime.

Refs (in-vault): [[s-recoil-compensation-coupling]], [[s-coupling-threshold-calibration]],
[[s-presence-lean-mode-build-plan]], [[s-posca-input-grounded-screen-authorship]],
[[s-sidecar-capture-process-vs-device]].
