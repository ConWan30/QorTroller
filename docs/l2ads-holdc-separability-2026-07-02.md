# l2_ads HOLD-C separability — 2026-07-02 range session

Evidence doc for the first live l2_ads calibration corpus (abstain-only capture, Remote Play,
`RETINA_ADS_COUPLING_ENABLED=true`, `enabled=False` — detector never fired a verdict). Records the
scalar-separability verdict and the pre-registered shape-feature pass. Same standing as the iron-sight
coverage boundary and the splice-FAR finding: a **structural boundary on record**, not a threshold shipped.

Corpus is local capture data (gitignored `retina_ads_coupling.jsonl`), N as captured below. Rich = held
sequence ≥ 20 samples.

## Corpus captured

| class | segment | n (rich) | role |
|---|---|---|---|
| 8× no-fire | `kc_8x_nofire_1` | 14 | positive (optic ADS) |
| 3× no-fire | `kc_3x_nofire_1` | 10 | positive |
| 1× optic (red-dot) | `kc_1x_nofire_1` | 12 | positive |
| 8× fire | `kc_8x_fire_1` | 9 | positive (flash contamination) |
| iron sight | `kc_1x_ironsight_1`+`_2` | 13 | boundary (ADS, no optic) |
| L2-non-ADS (menu/inspect) | `kc_neg_l2_nonads_1` | 8 | negative — L2 held, no scope |
| screen-transition, no L2 | `kc_neg_screentrans_1` | 17 (bg) | negative — scene shift, no L2 |
| passive idle | (unlabeled bg) | 27 | quiet baseline |

## Finding 1 — center-ROI magnitude is scene-confounded; no pooled scalar threshold at this N

Held-step = median(held_seq roi) − baseline.

| | signed held-step | \|transition_magnitude\| |
|---|---|---|
| optic-positives pooled (n=45) | median **+17.9**, p10 −0.3 | median ~7, p10 1.7 |
| L2-non-ADS neg (n=8) | median −1.0, p90 +0.5 | median 3.8, p90 8.7 |
| pooled gap (pos_p10 − neg_p90) | **−0.8 → OVERLAP** | **−7.0 → OVERLAP** |
| iron-sight (n=13) | −1.5 (negative-level) | 5.0 (above neg) |

Medians separate cleanly (+17.9 vs −1.0), but tails overlap: dark-scene optic-ADS (8×-no-fire p10 = −11)
dips into the negative range because the scoped view can be *darker* than the pre-ADS baseline. The signed
magnitude and its absolute onset jump are both scene-confounded. **No single pooled scalar threshold achieves
clean separation.**

Per-optic, some optics are individually clean: **3×-no-fire** (p10 +17.0, zero overlap with neg p90 +0.5)
and **8×-fire** (all positive) separate; **8×-no-fire** and **1×-optic** carry scene-dependent low tails.

## Finding 2 — shape featurization (pre-registered) does not rescue a clean threshold at this N

Pre-registered before computing, physics prior = the scope overlay is a rendered UI element (step-like
onset, stable held, exit on release) while a scene-brightness change is continuous and a menu press has no
transition. All five computed in one pass; every result reported including failures. No iterating.

| # | feature | definition | prediction | result |
|---|---|---|---|---|
| F1 | onset_abrupt | \|transition_mag\| / onset_window_members | separate (motivated) | **FAIL** — gap −0.81; optic 0.54 / neg 0.27 barely ordered |
| F2 | exit_abrupt | max \|Δroi\| across exit_seq | separate (motivated) | **median-separates, tails overlap** — optic 8.85 ≫ neg 1.06 (iron 2.19), but optic p10=0.0 and one n=8 neg outlier → neg p90=14.3 |
| F3 | held_cv | std/mean of held_seq roi | fail vs menu (both stable) | **FAIL as predicted** — optic 0.03 / neg 0.01 |
| F4 | held_range | max−min of held_seq roi | optic *lower* (stable overlay) | **PREDICTION WRONG** — optic *higher* (10.26 vs 0.79); scoped world varies, menu flat. Strong but opposite-direction → post-hoc, double-suspicion, not claimed |
| F5 | exit_len | # samples in exit_seq | exploratory | **FAIL** — identical medians (18/18) |

**Verdict: featurization does not produce a confirmed separating feature at this N.** The only
pre-registered *motivated* feature with median separation in its predicted direction is **F2
exit-abruptness** — and it is **provisional**: tails overlap both ways, and a single n=8 negative outlier
controls the negative p90 (now identified — see confirmation gate). F4's strong raw separation is opposite
its pre-registered direction, so it is a post-hoc hypothesis, not evidence — but its mechanism is real (the
scoped world moves, a static menu does not), so it earns a *corrected* physics story and is re-registered as
a fresh, equal-footing prediction for the next out-of-sample pass (below); it carries none of tonight's data
as evidence.

## Coverage boundaries (structural — on record)

- **Iron-sight out of coverage.** l2_ads sees "ADS-with-optic," not "ADS." Real human iron-sight ADS
  produces no center-ROI step (median −1.5, sits in the negative range on every scalar and shape feature
  tried). The channel's coverage claim must scope to optic-ADS; iron-sight ADS is invisible to it. Same
  shape as the killfeed firefight-deaths-only boundary.
- **Screen-transition immunity is structural, not thresholded.** Class-2 negatives (scene shifts with no
  L2) produced large ROI swings (spread 30.7) yet `ads_event = 0` throughout — the window requires an L2
  rising edge, so a replay supplying screen frames without a coupled live press cannot open a window at all.
  This is the real anti-splice strength and it is independent of any magnitude/shape threshold.

## Caveats (stated up front)

- **Onset-timing scope.** Onset edges ride the device clock (device-ts-corrected wall clock, 3 MHz sensor
  ts — NOT the ~1.2 s drain tick; `ts_source: device` on 120/120 records). But under Remote Play with
  ads-coupling ON, offset-5 is *undersampled* (56/57 crosscheck disagreements blind-low — the
  "consumption-load / GIL contention with ads-coupling ON" recurrence predicted in
  `docs/hid-timing-resolution-2026-07-01.md`): a real press whose first report read 0 fires its edge on a
  later valid report. Onset-latency features are device-precise-but-RP-undersampled, not ground truth.
- **F2's caveat is lighter than the shared framing — stated precisely.** F2 is `max |Δroi|` across
  `exit_seq`; the ROI *samples* ride the precise WGC clock, so the *measurement* is not RP-timing-limited.
  Only the exit *window boundary* (when `exit_seq` starts) rides the pyds L2 release edge — so the RP caveat
  is about *which samples land in the window*, not about the feature's clock. The hybrid device-ts wiring is
  therefore likely **not** needed for F2. This is a narrower, more accurate scope than "F2 rides the release
  edge."
- **Thin negative leg.** n=8 L2-non-ADS negatives. A p90 on eight samples moves a lot with one sample —
  F2's overlap is driven by a single outlier. This is the binding limit on tonight's result.

## D-ADS-1 (pre-sharpened)

- **min-across-optics is dead** — pooling the worst scene-dependent tail (8×-no-fire) yields overlap.
- Realistic options: **per-optic thresholds** (viable for tight optics 3×/8×-fire, weak for 8×-no-fire),
  or accept that **a scalar humanity threshold is not supported** and the channel's value is the structural
  no-L2-no-window immunity plus per-optic partial separability. Iron-sight explicitly out of coverage either
  way.
- **F2 exit-abruptness is the one provisional lever** worth carrying forward, not resolving now.

## Confirmation gate (frozen)

Nothing here resolves D-ADS-1. The candidates carried forward are provisional pending **out-of-sample
confirmation against frozen feature definitions**.

**The n=8 negative outlier is identified, not excluded.** The menu record with exit_abrupt 14.3: its
`exit_seq` sits flat (~27.5, matching its held baseline) for ~280 ms after release, then spikes to 43.0 at
t+344 ms — a real delayed UI/scene transition landing inside the 500 ms exit window, not noise. So F2's
negative tail is heavy **by mechanism, not fluke**: UI-transitions-during-the-exit-window are real-world
events F2 must survive. This rewrites the negatives protocol below — the confirmation session must
*deliberately include* release-during-UI-transition cases (menu-close-on-release, weapon-swap-on-release),
not hope to avoid them.

**Two frozen shape candidates on equal footing** (neither carries tonight's data as evidence):
- **F2 `exit_abrupt`** = max \|Δroi\| across `exit_seq`. Prediction: optic-ADS > L2-non-ADS.
- **F4 `held_range`** = max−min of `held_seq` roi, **re-registered with corrected physics**: the scoped
  world moves (varying held ROI) while a static menu does not, so optic-ADS > L2-non-ADS (the *opposite* of
  tonight's failed prediction that the overlay's stability would make optic *lower*). Testing two frozen
  candidates costs the same session as one.

**Next range session, confirmation capture** (short, rangebound): **~15 fresh L2-non-ADS negatives,
deliberately including release-during-UI-transition cases**, plus more positives to firm the optic tails,
scored against frozen F2 + re-registered F4. Same posture as every threshold this project has shipped:
separates-on-this-corpus-pre-registered is a hypothesis; separates-out-of-sample is evidence.

## Net

On this corpus, l2_ads does **not** have a confirmed humanity-threshold feature — center-ROI magnitude is
scene-confounded (no pooled scalar), and the pre-registered shape pass yields only one provisional candidate
(F2, thin-neg-leg-limited). The channel's demonstrated value is **structural** (no-L2-no-window anti-splice)
plus **per-optic partial** separability, with iron-sight ADS out of coverage. This is the finding, whether
or not F2 survives its confirmation gate.
