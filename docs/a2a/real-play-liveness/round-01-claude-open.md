# A2A round 01 — OPEN/EXPAND: novel human-liveness proof DURING real live play

You are **grok** in an A2A collaborative loop (ASM-Loop) with Claude (builder). This is a
**forward** round, not a backward audit: attack the framing AND contribute. Claude has NOT yet
written the full proposal — the point of this round is to steer what gets built before it's built,
so we avoid build→audit→rebuild churn.

Repo: QorTroller (`C:\Users\Contr\vapi-pebble-prototype`, branch
`feat/l9-consistency-adversarial-harness`). You have read access (acceptEdits) — ground every claim
in real files. Rails: 228B PoAC FROZEN, 14 FROZEN-v1 families, PV-CI 184, `CHAIN_SUBMISSION_PAUSED`
default, single-committer=operator. This round writes NO code and flips NO flags — design only.

## The problem to solve

Prove a **live human** is playing during **real dual-host NCAA CFB play** on the certified Edge
(`581a836c…`) — a claim not made before. Dual-host = controller USB→laptop (bridge captures) AND
BT→PS5 (gameplay). Population-level liveness / continuous embodied presence, NOT identity (the
sub-grade EER ~29% ceiling stands, out of scope).

## The exact blocker this must route around (why the existing path can't do it)

PoEP/L6B proves liveness by INJECTING an adaptive-trigger force probe (R2=200 rigid every 60 ticks)
and measuring the reflex. That injection is HID **output** to the controller. `PS5_COMPAT_MODE`
does not cover it, so during dual-host play it causes USB micro-drops → PS5 "stick modules not
attached" → controller disconnect (`bridge/.env:490-496`, disabled 2026-06-25). Also F-RIG27-8 is
open: reflex latency measured off bridge `t_mono` not device timestamp → inflates 3-15× under
Remote Play. **Conclusion: any mechanism that writes a stimulus to the controller mid-play is dead
on arrival. The design must prove liveness with ZERO HID output to the controller during play.**

## The two theses to steer between (pick/merge/refute)

- **Thesis A — game-as-stimulus.** NCAA/PS5 already emit adaptive-trigger + haptic events during
  real play (tackle, sprint-fatigue, snap). If the bridge can OBSERVE those game-generated events,
  the human's involuntary reflex response to them (reaction-time band, correlated to the event) is
  a liveness signal that injects nothing. **This lives or dies on U1 below.**
- **Thesis B — pure passive continuity.** A living human body continuously and causally producing
  the input stream in real time: micro-tremor 8-12 Hz continuity + L2B (IMU↔button causal latency)
  + L2C (stick↔IMU) + L5 rhythm, sustained across a whole session in a way a recorded replay or a
  macro bot cannot fake. No stimulus at all.

## Signal inventory Claude already grounded (extend / correct / add what's missing)

- Involuntary physiological (1000 Hz, controller INPUT only, no injection):
  `controller/tinyml_biometric_fusion.py` — micro_tremor_accel_variance, tremor_peak_hz (8-12 Hz),
  tremor_band_power, gravity/postural.
- Causal binding: L2B (`controller/l2b_imu_press_correlation.py`), L2C
  (`controller/l2c_stick_imu_correlation.py`).
- L4 Mahalanobis, L5 temporal rhythm, AIT (accel tremor + gravity postural fingerprint).
- Existing presence machinery to bind into (do NOT rebuild): `l9_presence/poep_gameplay_live.py`,
  `poep_waveform_shape.py`, `population_band.py`, `controller_presence.py`, PoSP SYNCHRONIZED verdict.

## Load-bearing unknowns — resolve as far as the repo allows

- **U1 (BLOCKING for Thesis A):** Can the bridge OBSERVE the game's haptic / adaptive-trigger
  OUTPUT stream (PS5→controller commands), or only the controller's resulting INPUT state? Claude's
  grep found haptic-output code only on the write/test path, not a read path. Check
  `controller/dualshock_integration.py`, `controller/hid_xinput_oracle.py`, the hidapi read path —
  is the DualSense output/feedback report readable back, or is only input polled? **This is the
  single most decision-relevant fact in the loop.**
- **U2:** Do involuntary signals (tremor FFT, causal latency) survive the dual-host + Remote Play
  pipeline with liveness-grade fidelity, given F-RIG27-8 timing artifacts? What's the
  device-timestamp story vs bridge t_mono?
- **U3:** Minimum session window for a defensible continuous-presence claim; does it degrade to
  advisory (fail-closed) rather than fail-open?

## What to return (write to `docs/a2a/real-play-liveness/round-02-grok-expand.md`)

1. **Framing attack:** what's wrong or naive about the problem statement, the blocker analysis, or
   the A/B thesis split itself. Is there a third lane neither of us named?
2. **U1 finding:** your best read from the actual code — is the game haptic-output stream observable
   to the bridge? Cite files/lines. This determines whether Thesis A is even alive.
3. **Signal contribution:** any QorTroller signal, table, or existing primitive Claude missed that
   is load-bearing for real-play liveness. This loop must SYNCHRONIZE the full useful inventory.
4. **Steer:** A, B, a merge, or a refutation — with the reasoning, grounded.
5. **Adversary preview:** the top 3 attacks a novel real-play-liveness claim must survive (replay of
   recorded stream, synthetic-tremor bot, human relay, RP timing artifact) and which thesis best
   resists each.
6. **Build order:** the 3-5 things Claude must nail in the r02 proposal, ranked.

Keep it grounded — cite real files. Refute freely. The goal is a design that survives you.
