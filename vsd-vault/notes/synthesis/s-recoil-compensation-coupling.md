---
type: synthesis
id: s-recoil-compensation-coupling
title: Recoil-compensation closed-loop — the novel QorTroller-exclusive proof that simultaneously attests PRESENCE and defeats the #1 Warzone cheat (anti-recoil macros). A human watches the on-screen recoil kick and pulls the stick DOWN to compensate at human reflex latency (80–280 ms AFTER the visible kick); an open-loop macro syncs its down-pull to the R2 TRIGGER, which — because of the render+stream delay — fires BEFORE the on-screen kick a human would react to. That "precognition" (compensation leading the visible kick) is physically impossible for a screen-reactive human and is only measurable by a system holding BOTH the 1000Hz trigger telemetry AND the retina + the session latency model. Channel C1 of [[s-multi-channel-presence-gate]].
created: 2026-06-27T19:35:00Z
modified: 2026-06-27T19:35:00Z
phase: VSD-LOOP
status: draft
confidence: plausible
effort: 70
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

CYCLE 49 companion to [[s-multi-channel-presence-gate]]. The headline novel proof in the operator's `/goal`
("if anymore aligning novel QorTroller-exclusive proofs… proceed"). It is BOTH a presence attestation and a
direct counter to anti-recoil scripting — the most common Warzone cheat — using the same burst frames + the
1000 Hz vaulted-controller telemetry, at zero extra capture cost.

## 1. The closed sensorimotor loop (the physics)

1. Player fires: **R2 onset** — exact timestamp, 1000 Hz, off the certified device.
2. The gun recoils: the on-screen view **kicks UP** (recoil pattern) — a deterministic upward optical-flow
   spike, appearing at the render+stream latency after R2 (Remote Play ≈ 50–150 ms).
3. The human SEES the kick and pulls the right stick **DOWN** (+counter-pattern) to hold the crosshair — a
   compensating stick-Y input at **human reflex latency** (80–280 ms after the VISIBLE kick).
4. The view settles. Loop repeats per shot in full-auto.

The proof is the coupling between the **on-screen vertical recoil motion** and the **compensating stick-Y
input**, conditioned on the compensation LAGGING the visible kick by a human reflex band. It is closed-loop:
the human's hands react to the human's screen.

## 2. The discriminator — human reflex-lag vs macro precognition (load-bearing)

An anti-recoil macro is **open-loop / feedforward**: it applies a pre-programmed down-pull synced to the FIRE
input (R2), because the macro is **screen-blind** — it never observes the recoil it cancels. Naively, both
human and macro show "stick-down correlates with firing," so a trigger→compensation correlation does NOT
separate them.

The separation comes from the **stream latency**, and it is clean:

- **Human**: compensation reacts to the VISIBLE kick → stick-down lags the on-screen kick by **+80–280 ms**
  (positive reflex latency), with natural variance and over/under-correction.
- **Macro**: compensation is synced to the R2 TRIGGER (fixed ~0–30 ms offset, near-zero variance). But the
  on-screen kick is DELAYED from R2 by the render+stream latency (~50–150 ms). So the macro's down-pull
  arrives **before or simultaneous with** the on-screen kick → compensation appears to **LEAD the visible
  kick** — a "precognition" signature physically impossible for a human reacting to the screen.

So C1 measures the latency of the compensation relative to the **on-screen kick** (not the trigger):
`Δ = t(stick-down onset) − t(on-screen kick onset)`.
- human: Δ ∈ [+80, +280] ms, dispersed.
- macro: Δ ≤ 0 (leads/coincides), tight variance → flagged.

This is QorTroller-exclusive: measuring Δ requires BOTH the precise trigger/stick telemetry AND the on-screen
kick AND the session latency model — no cloud anti-cheat (input-only) or vision detector (screen-only) can
compute it. The Remote-Play stream delay, usually a liability for capture, becomes the **amplifier** that
exposes the macro's precognition.

## 3. The math (per fire event)

Per detected R2 onset:
- **on-screen kick onset** `t_k`: first upward vertical-flow spike in the center/upper ROI after R2 (the
  retina already computes optical flow; add a signed vertical component + ROI).
- **compensation onset** `t_c`: first negative (downward) stick-Y deflection after R2 (1000 Hz telemetry).
- **Δ = t_c − t_k**; classify by the reflex-band test above.
- **coupling_score**: |Pearson r| between the on-screen vertical recoil trajectory and the compensating
  stick-Y trajectory over the post-shot window, on the Δ-aligned signals (closed-loop coupling magnitude).
- **null**: time-shuffled stick-Y (chance), same as channel A.
- **structured negative (anti-GCAP, REQUIRED before adoption)**: an emulated anti-recoil macro (deterministic
  R2-synced down-pull) — the explicit adversary this channel is built to reject. The channel is INSEPARABLE-
  honest if it cannot separate human Δ from macro Δ in a regime.

## 4. Anti-cheat value + presence value (both, from one signal)

- **Anti-cheat**: anti-recoil macros (Cronus/reWASD/scripts) are the single most common Warzone cheat. C1
  flags them by their screen-blindness — the precognition Δ — which the macro cannot remove without modeling
  the exact, varying session stream latency in real time. Raising the cost of that modeling is the moat.
- **Presence**: a positive human Δ (reflex-lagged, dispersed, closed-loop) is strong evidence of a live human
  in the loop — exactly the L9 presence claim, on the hardest-to-fake modality.

## 5. Corpus + calibration (same rails as channel A)

- collect fire-event windows during real gunfights (active full-auto) → human Δ distribution + coupling.
- structured negative: run an emulated macro (or capture a known-macro session) → macro Δ distribution.
- calibrate a FAR-safe Δ-band + coupling threshold via the `calibrate()` rails; ADOPTABLE only if human and
  macro Δ separate at bounded FAR. Per-regime (Remote-Play Δ ≠ native-PC Δ — the stream latency is the whole
  mechanism, so regime-labeling is doubly essential here).
- dev-cert / advisory until population + multi-cheat-tool validation; default-off flag.

## 6. Honest caveats / boundaries

- requires the game to have **on-screen recoil** + the player to be **firing** — active only in gunfights
  (acceptable: gunfights are exactly when cheating matters). Not a passive/idle proof.
- somewhat game-specific recoil patterns, but the closed-loop PRINCIPLE is game-agnostic.
- a sophisticated **closed-loop** cheat that actually reads the screen and reacts with humanlike reflex
  latency+variance would defeat C1 — but that cheat is far costlier than a macro and starts to resemble a
  human-in-the-loop; C1 raises the floor, it is not a total solution (state this, never overclaim).
- advisory presence oracle; NOT identity, NOT FROZEN-v1, NOT on the 228B wire, 0 IOTX.
- folds into the existing burst (analysis of frames already captured) — no extra capture/lag.

Refs (in-vault): [[s-multi-channel-presence-gate]], [[s-coupling-threshold-calibration]],
[[s-posca-input-grounded-screen-authorship]].
