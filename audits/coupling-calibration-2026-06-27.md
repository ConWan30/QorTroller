# Coupling-Threshold Calibration — Campaign 2026-06-27 (Remote Play / Warzone, dev-cert)

**Staple analysis** for the L9 coupled-retina presence oracle. Single-subject (developer-self-cert,
`DEVELOPER_SELF_CERT_ENABLED=true`), Remote-Play regime, Warzone corpus. Produced under `/goal` from the
10–15+ min active-aim campaign the operator played 2026-06-27. READ-ONLY analysis (no capture, no chain, 0 IOTX).

- Corpus (raw): `audits/coupling-campaign-corpus-2026-06-27.json` (127 diag windows + 96 burst proofs)
- Pipeline (reusable): `scripts/calibrate_coupling_threshold.py` → `vapi_bridge.coupling_threshold_calibration`
- Tests: `bridge/tests/test_coupling_threshold_calibration.py` (10/10 PASS)

## 1. What the campaign produced

| signal | count | meaning |
|---|---|---|
| diag windows total | 127 | one per RGC diag tick during bursts |
| — abstained | 75 | right-stick idle (walking/no-aim) → oracle's existing `MIN_STICK_STD` gate filtered them |
| — computed (genuine right-stick input) | 52 | real `coupling_score` + `negative_control` + `decoupled_energy` |
| burst proofs | 96 | 2 COUPLED_CLEAN (≥0.20), 44 IMPLAUSIBLE, 50 None(abstain) |

The oracle's **existing abstain gate already does the first cut** (75/127 idle windows removed). The 52 computed
windows are the calibration corpus.

## 2. Distributions (52 computed windows)

| | n | min | p25 | med | p75 | p90 | max | mean |
|---|---|---|---|---|---|---|---|---|
| coupling (genuine input) | 52 | 0.000 | 0.071 | 0.114 | 0.144 | 0.169 | 0.831 | 0.125 |
| null (time-shuffled chance) | 52 | 0.000 | 0.030 | 0.036 | 0.042 | 0.049 | **0.055** | 0.036 |
| decoupled_energy | 52 | 0.309 | 0.977 | 0.987 | 0.994 | 0.999 | 1.000 | 0.971 |

The null (chance/spoof baseline) maxes at **0.055**. Genuine coupling p25 (0.071) already sits above it.

## 3. The decoupled-energy gate (operator's input-activity insight) — VALIDATED

`decoupled_energy` = fraction of on-screen motion the input did NOT cause. **Walking** scrolls the whole world
(high decoupled_energy) without the right stick driving the pan → it **dilutes** the coupling correlation.
Splitting the 52 computed windows by decoupled_energy median:

| half | coupling mean | null mean | n |
|---|---|---|---|
| LOW-decoupled (right-stick-driven, aiming) | **0.183** | 0.037 | 26 |
| HIGH-decoupled (world-scroll / walking) | 0.066 | 0.034 | 26 |

Walking windows carry ~3× lower coupling. Gating them out concentrates the genuine signal.

## 4. FAR-controlled calibration (`calibrate()`)

| config | verdict | threshold | FAR | TPR | separation |
|---|---|---|---|---|---|
| ungated (52) | ADOPTABLE | 0.051 | 0.077 | 0.846 | 0.0635 |
| **gated, DE≤p50 (29)** | **ADOPTABLE** | 0.051 | 0.077 | **1.00** | **0.093** |

FAR=0 boundary on this corpus is at the null max **0.055** (no null sample reaches it). The gate lifts TPR
0.846 → **1.00** and separation 0.0635 → 0.093 at the same null — the empirical proof the gate works. The old
**0.20 default is far too strict** (TPR 0.08; only 2/96 bursts cleared it).

### Recommendation (PROVISIONAL — see caveats)
- **`L9_COUPLING_THRESHOLD ≈ 0.06`** (FAR=0 on this corpus, TPR 0.81 ungated; TPR ~1.0 on gated genuine-aim).
- Apply the **decoupled-energy gate** so the COUPLED class is genuine right-stick-driven windows.
- This makes burst proofs read COUPLED_CLEAN on real aim instead of IMPLAUSIBLE.

## 5. Honest caveats (do NOT skip before any production adoption)

1. **Single-subject, dev-cert scope.** N=52 computed / 1 player / Remote-Play / Warzone. This is a developer
   self-cert threshold, NOT a population threshold. A Remote-Play threshold ≠ a native-PC threshold (regime).
2. **Shuffle null is the weakest honest null.** The FAR is measured against the time-shuffled control only.
   **Structured negatives** (auto-camera / replay / another player's POV — the anti-GCAP rail) can beat shuffle
   and MUST be added before production; re-run with `--structured-null`. Until then this is PROVISIONAL.
3. **The gate cut is RELATIVE, not absolute.** decoupled_energy runs ~0.97–0.99 in busy game scenes, so an
   absolute DE threshold is scene/stream/game-fragile. The calibration gate is a quantile rank-filter within the
   corpus; a LIVE oracle should rank windows **within a burst** and keep the lowest-DE fraction — see the
   multi-channel gate design note.
4. **N just under production floor when gated** (29 < 30). Re-confirm at N≥30 gated.

## 6. Path forward

- Adopt `L9_COUPLING_THRESHOLD=0.06` as the dev-cert Remote-Play/Warzone provisional via env (no code default
  change) once the operator approves.
- Collect a **structured-negative** burst set (auto-camera / spectator POV) → re-run `--structured-null` to
  promote PROVISIONAL → production-eligible.
- Build the **live decoupled-energy gate** + the **trigger→HUD event channel** per the multi-channel gate design
  note (planned this cycle, code deferred).
