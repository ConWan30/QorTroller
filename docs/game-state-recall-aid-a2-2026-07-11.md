# Game-State Buffer OCR-Recall Aid (TRL-1 A2) - 2026-07-11

The last TRL-1 cycle, and the only one that touches the certificate path - so it is built with
the discipline that rail demands. Additive to the existing LUMEN-1 game-state buffer
(`l9_presence/game_state_buffer.py`): the `SceneEventStream` already structures the observation
plane (SCENE_CHANGE / SCENE_STABLE_SEGMENT / KILL_ROW_CLUSTER / INPUT_WINDOW); A2 adds the
**OCR-recall aid** on top.

## What it does

`recall_priority(stream)` raises **WHERE TO LOOK** for the throttled kill-row OCR: bursts of
SCENE_CHANGE (a row appeared / left) mark the temporal windows worth the OCR budget, a
KILL_ROW_CLUSTER overlap boosts them, and non-max suppression collapses each burst to one distinct
window. Under sparse RP sampling this spends the OCR budget where a row most likely appeared -
raising recall without OCR seeing more frames.

## The rails (why this is safe to ship at the desk)

- **Advisory only.** It ranks where to look. It never opens a classification window, never lowers
  the K=3 authored-kill floor, never changes `canon()`, never feeds `presence_score` (the anti-GCAP
  weight rail). OCR still owns the read; this only allocates the read budget. (Alignment doc N1: the
  observation plane may suggest, never assert.)
- **Consumption-gated.** `authorship_recall_priority(stream, consumption_regated=False)` returns `[]`.
  The recall priorities reach the live authorship / certificate path **only** after the
  **zero-false-read gate + the C1 adversarial pairing RE-PASS on the card feed** (the B8 lesson: a
  better reader can dissolve an accidental defense). **That re-gate is RIG/CARD-gated, not a desk
  step.** So A2 ships the aid + the rail, while the certificate-path wiring stays structurally
  deferred - `consumption_regated` is False and there is no code path that flips it here.

## The honest ceiling (the card-transition step)

This cycle does **not** wire the aid into authorship, and makes **no** certificate-path change - by
construction. The remaining work is the RIG step when the card lands: capture real card-feed OCR
crops, **re-run the zero-false-read gate and the C1 adversarial pairing** with the recall aid active,
and only if both re-pass, flip `consumption_regated` on. Until then the aid is a logging/scheduling
advisory that cannot influence a certificate. This is the same "build the structure, defer the gated
part, never cross the rail" discipline the ZKP/FLY scaffolds used - here the gated part is the
certificate-path consumption, and the gate is the rig re-validation.

---

*TRL-1 A2 - game-state recall aid. Loop: `docs/trio-readiness-loop-trl1-2026-07-11.md`.
The loop SATURATES here (9/9); card-arrival hands off to the rig-gated live loop.*
