# L9 Fusion — Option B Round Scope (L9 + strong controller battery)

**Status:** SCOPE / design-only. Motivated by the F3 Option-A result: fusion is
empirically validated — L9 and controller errors are **complementary** (Yule's
Q = −0.47, double-fault 0.11, permutation p = 0.0007) — and lifted 66.7% → **77.8%**,
but with the WEAK free-gameplay L4 partner (50%). Option B fuses L9 with a **strong**
controller battery (AIT 66.7%, touchpad) to chase the last points past 80%.

## The structural fact that shapes everything
- L9 needs **active-aiming gameplay**.
- AIT needs an **isometric trigger hold**; touchpad needs **touchpad sweeps**. Neither
  is gameplay — you cannot do them in the same session as L9.
- => Option B is NOT session-level co-capture. It is **player-level multi-battery
  fusion**: each player contributes separate L9 sessions and AIT sessions, fused per
  person.

## The evaluation method (leakage-safe): player-paired rounds
Within one player, all L9 sessions are exchangeable (same person, same activity), and so
are all AIT sessions. So pairing one L9 session with one AIT session of the SAME player
forms a valid multimodal "verification round" = "this player did both batteries."

1. Per player, pair L9 sessions with AIT sessions 1:1 → `round_i = {l9: l9_vec_i, ait: ait_vec_i}`
   (≈ min(n_L9, n_AIT) rounds/player; ~6/player → ~18 rounds for 3 players).
2. Feed the rounds straight into the EXISTING F0 harness (`fusion.fusion_report`,
   views = ["l9", "ait"]) — it already does score-level fusion + per-view LOO that holds
   the round's index out of BOTH views' centroids, + permutation null + error independence.
3. Leakage discipline: the held-out round's L9 and AIT sessions are excluded from their
   own centroids (the harness does this by index). Pairing shares only the player label —
   which is the thing being predicted, not leaked.

So the ONLY new code (FB0) is a small **round assembler** that pairs per-player L9 + AIT
vectors into `MultiViewSession`s. Everything downstream is already built and tested.

## Two data sub-paths for the AIT view
| | Source of AIT view | New capture? | Risk |
|---|---|---|---|
| **B1 (reuse)** | existing AIT corpus (N=37, P1=13/P2=10/P3=14) | none | requires CONFIRMED identity linkage: L9-P1 == AIT-P1 etc. (operator must verify the same humans). Wrong mapping = invalid fusion. |
| **B2 (fresh)** | capture AIT for the SAME 3 players who did L9, now | ~6 AIT sessions/player | none — same-person guaranteed by construction. Needs the players + the isometric battery. |

**Recommend B2 when the players are available** (no identity risk; uses the project's
existing AIT capture path — `terminal_calibration_runner.py`/AIT battery). Use **B1** only
if the L9↔AIT identity mapping is certain, as the fast no-capture option.

## Phases
- **FB0 — round assembler (code, no players).** `assemble_rounds(l9_by_player, ait_by_player)`
  → list[MultiViewSession]; pairs 1:1 per player; tests on synthetic. Wires to fusion_report.
- **FB1 — AIT feature adapter.** Get the AIT 4-feature vectors (accel_tremor_peak_hz,
  roll_cos, roll_sin, pitch_cos) per player — reuse the project's AIT extraction (B1: load
  from corpus; B2: extract from fresh AIT captures).
- **FB2 — AIT data.** B2: capture ~6 AIT isometric sessions for P1/P2/P3 (same controller).
  B1: load existing AIT corpus with confirmed identity mapping.
- **FB3 — verdict.** `fusion_report(rounds, ["l9","ait"])` → fused LOO, gain over best view,
  error independence (does L9 miss different players than AIT?), permutation p. ≥80%?
- **FB4 — decision (governance-gated).** If fused ≥80% AND independent AND significant →
  candidate for the separation pipeline / VHP multi-probe enrollment. Else → bank.

## Risks / honesty (carried forward)
- **3-player ceiling persists.** Even a >80% Option-B number is PROVISIONAL until a 4th/5th
  player; more people de-risks generalization more than a stronger partner does.
- **Pairing-exchangeability** assumes within-player sessions are interchangeable (true for a
  fixed person/activity); report it openly.
- **B1 identity linkage** is a correctness risk — only use with operator-confirmed mapping.
- **No p-hacking:** do not tune fusion weights on the same rounds to reach 80%; do not lower
  the 80% bar. A real cross-80% must come from a genuinely stronger, independent partner.
- **Activity burden:** AIT is a controlled isometric battery, not gameplay — operator-side.

## Reused (not rebuilt)
F0 fusion harness (`fusion.py`), the existing L9 co-capture corpus (L9 view ready), the
project's AIT capture + 4-feature extraction, the permutation guardrail. Net new surface
is small: FB0 round assembler + FB1 AIT adapter.

## Effort
FB0 small (code+tests). FB1 small–medium (reuse/adapt AIT extraction). FB2 = one operator
capture round (B2) or zero (B1). FB3 small. Cheapest decisive path: **FB0 + B1 (if identity
confirmed) → FB3 in minutes**; otherwise FB0 → B2 capture → FB3.
