# LUMEN-3 / N5 Increment 1 — Lag-Structure Coherence Study (HONEST NEGATIVE)

**2026-07-08. Pre-registered bar (stated before any class statistic was computed):**
genuine lag-consistency ≥ 0.60 AND decoupled ≤ genuine − 0.25, N≥8 informative windows
per class, on ≥1 channel. **Result: bar MISSED on all three channels. Published as-is —
the bar is not iterated post-hoc.**

## Classes and data

- GENUINE: M13 (HDMI) + M14 (RP) match windows — 426 windows, 3 channels
- DECOUPLED: a1spectate session — 213 windows, same instrument

## Results

| channel | genuine consistency (median lag) | decoupled consistency (median lag) | separates |
|---|---|---|---|
| geometric | 0.244 (108.3ms) — INCOHERENT | 0.889 (0.0ms) — "COHERENT" | NO |
| b1_flash | 0.778 (33.3ms) | 0.762 (33.3ms) | NO |
| b2_killmark | 0.237 (275.0ms) | 0.614 (50.0ms) | NO |

Direction partially INVERTED: decoupled windows show *higher* apparent lag-consistency
on two channels.

## Findings

**F-N5-1 — window-aggregate lag consistency does not separate.** The hypothesis as
operationalized is refuted on this data. Banked like every negative before it
(accel_phase_coherence, GCAP): the metric is retired, not tuned.

**F-N5-2 — the zero-default degeneracy (the real lesson).** The decoupled class's
"coherence" is an estimator artifact: absent true causation, the cross-correlation
argmax defaults toward lag=0 with high apparent stability (geometric decoupled: 0.889
consistency pinned at 0.0ms on n=9). *Consistency of lag rewards the degenerate
estimator.* Meanwhile genuine in-match lags scatter (b2 median 275ms, consistency 0.237)
because 5s windows aggregate MULTIPLE overlapping fire events — the window is the wrong
unit of analysis for latency structure.

**The redirect (what increment 2 actually needs):** per-EVENT latency — single-stimulus
pairing of one trigger pull to one screen response, with the physical pipeline band
([~20, ~300]ms) as a hard prior and strictly-positive lag as a requirement, not a
statistic. That is precisely **RP-4 (cross-lobe latency calibration, USB-direct first)**
— the rig-gated item is the true prerequisite for the N5 oracle, now demonstrated
rather than assumed. The recoil-precognition trap (macro Δ≤0 vs human Δ∈[+80,+280]ms)
survives as the target claim; it needs the per-event instrument, not window aggregates.

## Status

- LUMEN-3 increment 1: **CLOSED — honest negative, instrument lesson banked.**
- LUMEN-3 increment 2: **GATED on RP-4** (per-event latency calibration; rig).
- `l9_presence/predictive_coupling.py` stays: the consistency machinery + fail-open
  verdicts are reusable once fed per-event lags; the pre-registration text remains in
  its docstring as the record.

## Files
- Result JSON: `audits/n5_lag_structure_result.json`
- Module + tests: `l9_presence/predictive_coupling.py`, `tests/test_predictive_coupling.py` (8/8)
- Runner: `scripts/n5_lag_structure_study.py`
