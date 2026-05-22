# L9 Fusion Phase — Scope (co-capture + combined classifier)

**Status:** SCOPE / design-only. No code, no capture, no governance change yet. The
goal is to take 3-way LOO classification from L9-alone's honest **72%** toward **>80%**
by fusing L9's render-loop features with controller biometrics — exploiting error
independence (orthogonal physics), not a classifier trick (those were ruled out, see
`81e252d9` lever sweep).

## 1. Hypothesis
L9 (render-derived) and the controller biometrics (HID-derived) measure orthogonal
physics, so their LOO errors should fall on *different* sessions. When two classifiers
make independent errors, score-level fusion exceeds either alone. **Decisive risk:**
if the errors are *correlated* (both fail on the same hard player), fusion gains little.
So the phase is gated on an **error-independence pre-test**, not on building the combiner.

## 2. The non-obvious decision: WHICH controller signal can you co-capture?
This is the crux and it's easy to get wrong:

- L9 requires **active aiming gameplay** (Remote Play, the player driving the camera).
- The project's *strong* controller biometrics come from **controlled batteries** that
  are NOT gameplay: **AIT** (isometric trigger hold, 66.7% LOO, 4 features) and
  **touchpad_corners**. You physically cannot do an isometric-hold battery *and* play
  the game in the same session.
- During L9 gameplay, the co-capturable controller features are the **free-gameplay L4
  features**, which historically separate *weakly* (pooled ratio 0.417, ~30%).

So there are two distinct fusion architectures, and the phase must pick:

| Option | What's fused | Co-capture? | Strength | Honesty |
|---|---|---|---|---|
| **A. Session-level (gameplay)** | L9 + free-gameplay L4, same session | YES (simultaneous) | one input weak (~30%) → modest lift | clean per-session LOO |
| **B. Multi-battery enrollment** | L9 + AIT + touchpad, per player, GIC-bound | NO (separate batteries, one enrollment) | uses strong signals (66.7%) | player-level; evaluate leave-one-**player**-out; leakage-careful |

**Recommendation:** run **A first as the cheap error-independence test** (simultaneous
co-capture is the clean experiment), then pursue **B as the real deployment model** —
it matches the per-gamer VHP multi-probe identity vision and uses the strong batteries.
B is where >80% most plausibly lives; A tells us fast whether render+HID errors are
independent at all.

## 3. Fusion method: score-level (late), NOT feature-level
Feature-level concatenation pushes p to ~16-19; at N≈18-24 that violates the project's
`N/p > 3.0` rule and reproduces the Phase-138 inflation. **Score-level fusion** keeps
each sub-classifier low-dimensional (L9: 3 feats diagonal; AIT: 4 feats), emits a
per-session posterior/score from each, and combines the scalars (equal-weight or
accuracy-weighted log-likelihood sum). Combiner has ≤2 params → N/p-safe. Avoids the
inflation trap entirely.

## 4. Phases & deliverables
- **F0 — Independence harness (no capture).** Build the error-independence analysis +
  score-level combiner + permutation guardrail, with synthetic tests. Reuses
  `_loo_accuracy`, `_load_reliable`, `permutation_test`.
- **F1 — Co-capture recorder.** Un-gate HID to a dedicated **1 kHz reader thread**
  (the de-risk already saw 1001 reports/s on report 0x01 with sticks@3/4 + IMU@16-21)
  running parallel to the mss frame loop. Feed the 1 kHz buffer through the existing
  **`BiometricFeatureExtractor`** (REUSE — keeps L4 features identical to the live
  pipeline) → one session emits L9 features **and** L4 features + camera, time-tagged.
- **F2 — Re-capture P1/P2/P3** (~8 active-aim sessions each) with co-capture. Needs the
  players again (scarce resource). Existing L9 sessions lack L4; existing L4 corpus
  lacks L9 → a fresh co-captured corpus is required for Option A.
- **F3 — Combined classifier + the two verdicts:** (a) **error independence** (do L9 & L4
  miss the same sessions? Q-statistic / McNemar / overlap), and (b) **fused LOO** >
  max(L9, L4) and ≥80%, permutation p<0.05.
- **F4 — Decision (governance-gated).** If fused ≥80% AND independent AND significant →
  register L9 as a probe in `analyze_interperson_separation.py` / `separation_defensibility_log`
  and wire to the tournament gate (two-key + chain-pause discipline). Else → bank L9 as
  the Stream-A presence primitive and stop.

## 5. Risks / unknowns (named up front)
- **Weak co-capture partner (Option A):** gameplay-L4 ~30% caps the lift; A may show
  independence but not reach 80% — that's why B (strong batteries) is the real target.
- **AIT/L9 activity incompatibility:** cannot co-capture isometric-hold AIT with gameplay
  → B is multi-battery enrollment, not simultaneous; needs the cross-probe **identity
  linkage** (operator confirms L9-P1 == AIT-P1) and **leave-one-player-out** evaluation
  (with 3 players that's barely testable → still ultimately wants more players).
- **HID contention:** L9's 1 kHz reader vs the bridge's interface-3 reader — run
  co-capture **standalone** (bridge not capturing) to avoid contention.
- **Leakage discipline (Option B):** never let a session borrow its own player's
  cross-probe aggregate at LOO time; hold out whole players.
- **3-player ceiling persists:** fusion can raise the 3-way %, but a generalizable
  tournament-grade claim still eventually needs more gamers. Treat any >80% as provisional.
- **Inflation guard:** every fused number must pass the permutation null (same as L9).

## 6. What stays frozen / gated
Standalone `l9_presence/` (+ reuse of the existing extractor). No FROZEN-v1 primitive,
no PoAC, no chain submission, no contract. PoCP/Witness anchoring + tournament-gate
wiring remain behind explicit operator opt-in and the F4 decision. Nothing goes live on
a fused number until it clears F3 with independence + significance.

## 7. Effort estimate
F0 ~ small (analysis + tests). F1 ~ medium (1 kHz threading + extractor reuse + alignment).
F2 ~ operator capture session (all 3 players). F3 ~ small (run + interpret). F4 ~ governance.
The gating insight: **F0 + a small F2 co-capture answers the independence question cheaply
before committing to F1's full build** — verification-first.
