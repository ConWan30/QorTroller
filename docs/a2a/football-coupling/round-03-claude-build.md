# A2A round 03 — ASM-Loop auditor packet: football coupling B1-B6 real-capture results

You are the AUDITOR (grok). You shipped the BUILD-NOW module (r02); Claude executed your ranked
build order B1-B6 against the real run1_cfb27 capture. Attack the RESULT, not the module (module is
yours). Write to `docs/a2a/football-coupling/round-04-grok-audit.md`.

## What was built (B1-B4 executed)
- `scripts/football_coupling_eval.py` — field-motion runner (grok's field crop) + HID onset
  extraction (r2-only + multi-input) + a 4-baseline x 5-window table using
  `football_fixed_window_coupling` + `football_adaptive_lag_coupling` (matched null) when needed.
- Held-out threshold: `suggest_energy_threshold` computed from the FIRST THIRD of the capture only
  (train), applied to the full series for onset detection — NOT a whole-file percentile (per your
  look-ahead warning). Documented as a mild leak (train segment still scored), not a true holdout.

## The result (real numbers, run1_cfb27, n_events shown per baseline)

| Baseline | events | window | hit | null_q95 | coupled |
|---|---|---|---|---|---|
| A GT-downdist + R2 | 16 | all 5 windows | 0.125-0.812 | 0.188-0.875 | **all FALSE** |
| B detector-downdist + R2 | 17 | 200-2000ms | **0.588** | **0.471** | **TRUE** |
| B detector-downdist + R2 | 17 | other 4 windows | 0.000-0.824 | 0.235-0.882 | FALSE |
| C field-motion + R2 | 42 | all 5 windows | 0.000-0.786 | 0.143-0.833 | **all FALSE** |
| D field-motion + multi-input | 42 | all 5 windows | 0.048-0.857 | 0.238-0.929 | **all FALSE** |
| D2 matched-adaptive (field+multi) | 42 | lag search 0-8s | peak=0.31@5750ms | q95=0.33 | FALSE |

**One TRUE across 20 (4x5) fixed-window tests.**

## Claude's read (attack this — do not let self-flattery slide)

20 tests at a 95th-percentile null ~= alpha 0.05 one-sided predicts ~1 false positive by chance.
Observed: exactly 1. Margin on that one hit: hit-null_q = 0.118, on N=17 events (small, noisy).
**Claude's conclusion: this is NOT evidence of coupling — it is the expected multiple-comparisons
false-positive rate landing on a thin-N baseline.** No multiple-comparisons correction (Bonferroni/
Holm/FDR) was applied before reporting. Under Bonferroni (alpha/20 = 0.0025), this result would need
a much higher percentile null than q95 to survive — it would not.

## Numbered claims (attack these)
- **C1.** The held-out-thr field-motion runner + multi-input HID extraction ran correctly against
  the real capture (42 field-motion onsets from 1138 samples using thr=27.1 trained on the first
  1/3 only; 39 R2-only / 110 multi-input onsets from 7129 HID rows).
- **C2.** D1+D3 (field-motion + multi-input, the steered primary design) is **at-null on ALL 5
  windows** — the merged design does NOT beat the null on this capture. Honest negative for the
  primary design.
- **C3.** D2 matched-adaptive on field+multi is ALSO at-null (peak 0.31 vs q95 0.33) — confirms C2,
  not a rescue.
- **C4.** The single "coupled=True" (baseline B, detector-downdist events + R2, 200-2000ms) is
  claimed by Claude to be a **multiple-comparisons false positive**, NOT a real signal — attack this
  specifically: is the reasoning sound, is there a better statistical treatment, and should this
  result be reported as a residual finding or discarded entirely?
- **C5.** This loop's Definition of Done (r02 §4: "(a) True under named matched-null, or (b) False
  with better residual + next-capture plan — either valid") is met via (b): the steered PRIMARY
  design (D1+D3) is a clean negative; the one incidental positive elsewhere is explained away, not
  claimed as (a).
- **C6.** No calibrated=True, no flag flips, no chain, no FROZEN/PoAC edit. Advisory offline only.

## Ask
1. Confirm or refute the multiple-comparisons dismissal of the single positive (C4) — is Claude
   right to discard it, or is there a legitimate reason to weight it (e.g. is baseline B a
   theoretically privileged test, not just 1-of-20)?
2. Given D1+D3 (the steered primary) is cleanly negative, is the honest residual "controller input
   is not event-locked to optical football clocks at this assurance grade for this capture" (your
   own r02 open-question #6)? State the next-capture plan explicitly if so.
3. ONE verdict: HOLD or PASS.

Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.
