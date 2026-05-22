# /goal — Reframe the L9 separation gate to per-player VERIFICATION (EER)

**Origin (2026-05-21):** asked Mythos + the WHAT-IF/knowledge tooling to find "the actual
solution." Result: **no hidden solution exists** — Mythos is an audit layer (no proposals),
and `vapi_query_knowledge` returns **0 hits** for verification / EER / false-accept. The
protocol only knows **N-way identification** (separation ratio + N-way LOO classification),
which is the **wrong objective** and degrades as players are added (LOO 90.9→72.2→62.5% at
2/3/4 players). That gap is the goal.

## The goal
Adopt **per-player verification (EER / FAR-FRR)** as the L9 (and, by extension, the VHP)
gate metric — *"is this session the human who enrolled?"*, a 1-vs-rest decision that is
**independent per player and does NOT degrade as players are added.** This matches the
actual deployment (VHP = Verified *Human* Proof, per gamer), unlike N-way identification
(which player among N — irrelevant to the use case).

## Honest baseline (NOT a fix — measured, falls short)
On 4 players × 6 reliable co-captured sessions, L9-alone (3 features, Euclidean nearest-
centroid, LOO genuine / 1-vs-rest impostor):

| Player | verification EER |
|---|---|
| P1 | 16.7% |
| P2 | 44.4% |
| P3 | 22.2% |
| P4 | 33.3% |
| **mean** | **29.2%** |

This is the **right metric** but **not tournament-grade** (target ~<10% EER). EER varies
widely by player (P1/P3 usable-ish; P2/P4 poor) — the signal is real and significant but
not yet strong enough. The reframe corrects the *objective*; it does not by itself clear
the bar. No shortcut found; no goalpost moved.

## Path to drive EER down (the real work, in priority order)
1. **More sessions per player** — tighter enrollment centroids; the dominant lever at this N.
2. **More players** — robust per-player threshold calibration (and honest EER estimates).
3. **Multi-probe verification fusion** — combine each player's L9 profile with their
   controller-battery profile *at the verification level* (per-player evidence), which is a
   more appropriate place for fusion than N-way (where fusion did not generalize — `345eb3b0`).
4. **Per-player adaptive thresholds** — calibrate FAR/FRR per enrolled gamer.

## Definition of done
Mean per-player EER ≤ ~10% on ≥5 players with ≥10 sessions each, permutation-significant,
**and** the gate logic (preflight / VHP issuance) reads EER, not N-way accuracy. Until then
L9 stays banked as Stream A (causal presence, validated) + a real-but-sub-grade biometric.

## What this is NOT
Not a claim that L9 is tournament-grade today (mean EER 29%). Not a metric chosen to make a
number pass — it's the metric the use case actually requires, which the protocol was missing.
Strengthening the signal (data) is still required.
