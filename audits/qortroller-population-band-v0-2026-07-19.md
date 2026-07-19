# QorTroller population reaction-time band — v0 · CANDIDATE, ADVISORY (ASM-Loop r02 → r07 PASS, 2026-07-19)

**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · **candidate/advisory only** — emits a
band + FRR, **gates nothing**; `poep_enabled`/`L6B`/`L6_CHALLENGES` stay False; no on-chain, no flag flip.
This loop closes the anti-cheat detector's residual **F5**: the shipped detector used the single-operator GO
band floor (320 ms) as the anti-bot **sub-floor**, so a population human who reacts *faster* than 320 ms would
false-positive as `SUSPECTED_BOT`. This module separates the two floors and gives a data-driven, honestly
PROVISIONAL population-band estimator.

## What it is
`l9_presence/population_band.py` + the parameterized detector (`qortroller_anticheat.detect_session` /
`poep_r2onset_adversarial.detect_voluntary_go` now take `go_lo_ms`, `go_hi_ms`, `sub_floor_ms`).
- **Two floors, not one (F5 fix):** the **GO band** `(go_lo, go_hi]` is the "clean fast-cluster" window; the
  **sub-floor** is the *human-impossibility* boundary. A reaction between the sub-floor and `go_lo` is a fast
  human → new verdict **`SOFT_TOO_FAST`** (retry), NOT `SUSPECTED_BOT`. Only a reaction **≤ sub-floor** is the
  bot rail `REJECT_TOO_FAST`.
- **Population-safe sub-floor = the anticipation boundary** `ANTICIPATION_FLOOR_MS = 120 ms`
  (`population_safe_sub_floor_ms()`), NOT the 320 ms band edge.
- **`estimate_population_band(operator_samples)`** pools per-operator reaction samples → a band
  (`floor = max(anticipation, p1 − margin)`, `ceiling = p99 + margin`) + per-operator FRR, tagged
  **PROVISIONAL** until `≥ MIN_OPERATORS_FOR_POPULATION (5)` operators each with `≥ MIN_SAMPLES_PER_OPERATOR (20)`.
- **FAR is recomputed for the (wider) band** with the SAME grok-audited math (`worst_case_true_far`): it reports
  the joint worst-case FAR for the population band **and** the single-operator band side by side.

## Verdict ladder (per fire, population config)
`REJECT` (no gold t0) → `REJECT_NO_REACTION` (flat/no in-window reaction) → **`REJECT_TOO_FAST`** (lat ≤ sub-floor,
non-human) → **`SOFT_TOO_FAST`** (sub-floor < lat ≤ go_lo, fast human, retry) → **`SOFT_TOO_SLOW`** (lat > go_hi,
retry) → **`GO`** (lat in (go_lo, go_hi]). `detect_session.n_soft` aggregates both soft verdicts; `n_sub_floor`
is the bot rail count (any > 0 → `SUSPECTED_BOT`).

## F5 demonstrated (fixture, `single_operator_floor_false_positive_rate`)
A fast operator (~200 ms reactions): the single-operator **320 ms** floor rejects **100 %** of them as sub-floor
(false `SUSPECTED_BOT`); the population-safe **120 ms** anticipation floor rejects **0 %**. A genuinely sub-human
~80 ms feed is still rejected **100 %** by the 120 ms floor (it is not a fast human). Per-fire: `onset=200 ms` →
`REJECT_TOO_FAST` on the default (single-op) path, `SOFT_TOO_FAST` on the population path — the fix, opt-in.

## The FAR honesty (r04 — models the three-zone ladder + guards the degenerate band)
Two effects **both RAISE** the population FAR and both are surfaced (grok r03 F4): a **wider band** raises
`p_go = band/ISI`, and a **lower sub-floor** (anticipation 120 ms vs 320 ms) **shrinks the fatal zone**, so the
`(sub_floor, go_lo]` soft zone becomes `p_other` (non-fatal escape). `blind_bot_probs/blind_bot_far/
worst_case_true_far` now take `sub_floor_ms` (default `go_lo` → single-op behavior byte-identical); the
estimator computes `worst_case_far_population_band` with `sub_floor=anticipation`, so the reported number is
the FAR of the **actual three-zone population config**, not an understated single-op proxy.

**Band coherence guard (grok r03 F1/F2 — the two BLOCKs):** `floor = max(anticipation, p1−margin)` can
**exceed** `ceiling = p99+margin` when the whole pool reacts faster than the anticipation floor. Such a band is
**DEGENERATE** (`floor ≥ ceiling`): it is flagged `degenerate_band=True`, forced `provisional=True` regardless
of operator/sample counts, and its FAR is reported as **`None` (UNDEFINED)** — NOT a misleading `0.0` that
would falsely read as a tight, safe band and reverse the `pop_far ≥ single_op_far` inequality. The
`≥`-invariant is therefore scoped to **coherent** bands; a degenerate pool is a red flag, not a low-FAR result.

## Claim ceiling (what this is NOT)
- **N = 1 operator → PROVISIONAL.** With one operator this is a **FRAMEWORK + a CONSERVATIVE PRIOR**, not a
  measured population band. `provisional=True`, `operators_needed=4` are surfaced in the return.
- The **120 ms anticipation floor is a conservative general-psychophysics PRIOR**, stated **WITHOUT a fabricated
  citation** and **NOT our measurement**. A *measured* population floor across operators is **rig-gated**.
- The population band **widens the FAR** (honest tradeoff), it does not tighten it. It fixes a **false-reject**
  (F5), not a false-accept.
- The `SOFT_TOO_FAST` fix is **opt-in**: the default `detect_session(recs)` path (`sub_floor = go_lo = 320`) is
  **behaviorally/verdict-identical** to the shipped detector — a fast session still reads `SUSPECTED_BOT`
  (`n_sub_floor` unchanged). It is **NOT byte-identical source** (grok r03 F3): one response key was renamed
  `n_soft_slow → n_soft` (now aggregating both soft verdicts), reason strings changed, and the dead
  `SOFT_TOO_FAST` branch was added (inert when `sub == go_lo`). The one committed consumer of the old key —
  the runner `scripts/qortroller_anticheat_report.py` — was updated in the same change (grok r05 F7 caught it
  crashing on the rename; no test keyed the old name). The population band must be explicitly supplied.
- Advisory: emits a band + verdict, **gates nothing**; `poep_enabled`/`L6B` stay False.

## Rig/data remainder (not resolved here)
Real multi-operator reaction corpus (≥5 operators × ≥20 samples) to promote PROVISIONAL → measured; a measured
anticipation floor; age/fatigue/session covariates; the fire-time-observing-bot residual (unchanged, defended by
the named HMAC frame-commitment follow-on, not this module).

**Tests:** 24 fixture tests (`l9_presence/tests/test_population_band.py`, CI-safe, no gitignored dumps) +
regression: 17 anti-cheat (`l9_presence/tests/test_qortroller_anticheat.py`) + 9 adversarial
(`bridge/tests/test_poep_r2onset_adversarial.py`) — **50 green total**. PV-CI **184**. Zero spend; sealed
FROZEN/PoAC untouched.

## Loop outcome — grok r07 PASS (2026-07-19)
6 rounds (r02 build → r03 HOLD 2 BLOCK/4 WARN → r04 fix → r05 HOLD 3 new WARN → r06 fix → **r07 PASS**).
grok independently re-ran the 47-test suite + PV-CI 184 + live numeric attacks (degenerate pool, sub_floor
FAR threading, config-conditional note) and returned **PASS**. Post-PASS hardening (INFO-level, no new round):
**F12** — `far_note` now branches on effective `sub >= go_lo` (not `is None`), so an explicit `sub == go_lo`
gets the correct single-op note; **F13** — the module docstring's `3.2e-4` now carries the population caveat.
**F14 CLOSED (follow-up increment):** the runner `qortroller_anticheat_report.py` now has `--go-lo`,
`--go-hi`, `--sub-floor`, and a `--population` convenience flag (uses the ~120ms anticipation floor with an
explicit "uncited prior" label). It prints the active config (single-operator vs POPULATION) and threads the
band + sub-floor into `detect_session`, so live dumps can now be scored under a population config from the CLI
— e.g. the same fast (~200ms) session reads `SUSPECTED_BOT` under the default (single-op) config but
`SOFT`/not-a-bot under `--sub-floor 120`. 3 CI-safe runner tests (default / `--sub-floor` / `--population`)
drive the real arg parser over synthetic tmp dumps.

## r06 disposition (grok r05 re-verify — both BLOCKs cleared, 3 new WARNs)
- **F7 WARN** (broken committed consumer `qortroller_anticheat_report.py` reading `n_soft_slow`; false
  "no consumer" claim) → FIXED: runner reads `n_soft`; audit claim corrected (the runner WAS the consumer).
- **F8 WARN** (`detect_session` didn't thread `sub_floor_ms` into its FAR) → FIXED: FAR calls now pass
  `sub_floor_ms`; the population session's reported `blind_bot_far` is now the (higher) three-zone number.
- **F9 WARN** (`far_note` hardcoded the single-op `3.2e-4` envelope for all configs) → FIXED: `far_note` is
  config-conditional; a population config explicitly disclaims `3.2e-4` and points at `worst_case_true_far`.
- **F10 INFO** (test name still says "byte_identical") → cosmetic; the pin is a verdict pin. Left as-is.

## r04 disposition (grok r03 audit)
- **F1 BLOCK** (inverted band FAR understatement) → FIXED: band coherence guard; degenerate band → `pop_far=None`.
- **F2 BLOCK** (non-provisional inverted band) → FIXED: degenerate band forces `provisional=True`.
- **F4 WARN** (FAR model ignored soft zone) → FIXED: `sub_floor_ms` threaded through the FAR functions; the
  population FAR now models the real fatal zone (anticipation floor) and the soft escape.
- **F5 WARN** (stale `SUSPECTED_BOT` copy hardcoding 320) → FIXED: message reports the configured sub-floor.
- **F3 WARN** ("byte-identical" overclaim) → FIXED: reworded to behaviorally/verdict-identical + schema note.
- **F6 WARN** ("9 adversarial" unlocatable) → the suite is `bridge/tests/test_poep_r2onset_adversarial.py`
  (9 tests, verified `9 passed`); grok r03 swept only `l9_presence/tests/`. Cited by path above.
- **F7–F10 INFO** → acknowledged; within the claim ceiling.
