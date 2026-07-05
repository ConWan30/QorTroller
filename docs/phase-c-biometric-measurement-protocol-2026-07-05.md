# Phase C — C-2.1: Biometric Signal Power Measurement Protocol

**Status: DRAFT — awaiting review/approval per C-2.1's own exit criteria before C-2.2 (data
collection) begins. No sessions run, no code changed by this document.**

## 1. Purpose and scope

Quantify the current discriminative power of the L4/L5/L6B biometric feature set — inter-subject
vs intra-subject separation, under a protocol tighter than the free-form gameplay corpus that has
driven every separation-ratio number in CLAUDE.md to date. This is a measurement plan, not a
re-run of existing probes: the deliverable is an **enrollment/verification split** with FAR/FRR
framing, which the corpus has never had (every prior number — AIT 1.199, touchpad_corners 0.728,
tremor_resting 1.177 — is LOO cross-validation over one undifferentiated pool, not a train/test
split simulating a real enrollment-then-verify flow).

## 2. Signals in scope (exact current feature set — verified against source, not recalled)

### 2.1 L4 — `controller/tinyml_biometric_fusion.py::BiometricFeatureVector.to_vector()`

13-element vector (indices 0–12), current as of this document's writing:

| idx | Feature | Status for this protocol |
|---|---|---|
| 0 | `trigger_resistance_change_rate` | **EXCLUDED** — structurally zero in static-trigger games (NCAA CFB 26); confirmed in CLAUDE.md's L4 calibration state |
| 1 | `trigger_onset_velocity_l2` | in scope |
| 2 | `trigger_onset_velocity_r2` | in scope |
| 3 | `micro_tremor_accel_variance` | in scope |
| 4 | `grip_asymmetry` | in scope |
| 5 | `stick_autocorr_lag1` | in scope |
| 6 | `stick_autocorr_lag5` | in scope |
| 7 | `tremor_peak_hz` | in scope (requires ≥32 frames; 0.0 below) |
| 8 | `tremor_band_power` | in scope (same floor as tremor_peak_hz) |
| 9 | `accel_magnitude_spectral_entropy` | in scope; **requires 1000 Hz polling** — unreliable at standard HID (125–250 Hz); this is the same floor the retina/killfeed capture work hit with 120 Hz throttling (see `project_dualconnection_capture_blind_finding` memory) — the capture rig for this protocol MUST be verified at 1000 Hz before C-2.2, not assumed |
| 10 | `touch_position_variance` | **EXCLUDED pending recapture** per CLAUDE.md's standing note ("touch_position_variance(excl pending recapture)") |
| 11 | `press_timing_jitter_variance` | in scope |
| 12 | `touchpad_spatial_entropy` | in scope, but **not yet in the calibrated threshold set** (CLAUDE.md: "live_dim=13 vs calib_dim=12" staleness note) — this protocol's data collection is the first chance to fold it into a real separation-ratio computation, not just a live-dimension mismatch footnote |

**In-scope active set for this protocol: 10 features** (indices 1–9, 11–12 minus the two
structural exclusions). This matches the corpus's own precedent (CLAUDE.md: "Feature space: 12
features, 10 active") with the one addition that `touchpad_spatial_entropy` (index 12, Phase 121)
is included here for the first time in a formal separation measurement — prior corpus work only
measured 10 of the 12 pre-Phase-121 features.

### 2.2 L5 — `controller/temporal_rhythm_oracle.py::TemporalRhythmFeatures`

3 statistical signals over inter-press interval distributions:

| Feature | Definition | Human range (source docstring) |
|---|---|---|
| `cv` | coefficient of variation (std/mean) of inter-press intervals | > 0.15 human; < 0.08 bot-like |
| `entropy_bits` | Shannon entropy of interval distribution (50 ms buckets) | ~1.38 bits (N=50 hardware); < 1.0 bot-like |
| `quant_score` | fraction of intervals snapping to the 60 Hz timer grid (16.667 ms multiples, ±5 ms) | > 0.55 bot-like |

All 3 are in scope. `sample_count` and `anomaly_signals` (0–3 fired-signal count) are diagnostic,
not separate discriminative features — recorded per session but not fed into the Mahalanobis
vector.

### 2.3 L6B — `bridge/controller/l6b_reflex_analyzer.py::L6bReflexAnalyzer`

**Honest gap, stated up front:** L6B is currently **N=0 hardware-calibrated** (CLAUDE.md hard
rule: "L6B_ENABLED=false — never change without N≥50 neuromuscular reflex calibration"). This
protocol's L6B component is the FIRST structured attempt at that N≥50 campaign, not a re-measure
of an existing corpus. Feature: `latency_ms` (canonical: `true_latency_ms` when device-clock
`t_mono` is present, else legacy `index × 8ms`), classified into BOT (< 15 ms) / INCONCLUSIVE
(15–80 ms, or sub-`human_min_ms` with a small `reflex_gap_ms`) / HUMAN (80–280 ms, widened to
350 ms per desk-calibration note in the source docstring) / NO_RESPONSE. The discriminative
question this protocol asks is **inter-subject latency distribution**, not just the existing
bot/human bucket edges — i.e., does each of P1/P2/P3's HUMAN-bucket latencies cluster distinctly
enough to serve as a 4th oracle signal, or does human-to-human variance swamp the 80–280 ms band.

## 3. Session design

### 3.1 Enrollment / verification split (the actual new contribution of this protocol)

Every prior separation-ratio number in this repo (AIT, touchpad_corners, tremor_resting, full
free-form corpus) is LOO cross-validation: every session is both training data (via the
LOO-excluded centroid) and test data, in the same pool. That's the right tool for measuring
whether player-clusters exist at all, but it does not simulate what an actual tournament
enrollment flow would look like: enroll once, verify many times later, on sessions the enrollment
centroid never saw.

This protocol's session design:
- **Enrollment set**: N=10 sessions/player minimum (matching the AIT defensibility gate's own
  `n>=10` floor — CLAUDE.md Phase 231), one probe type held fixed for the enrollment centroid.
- **Verification set**: N=10 additional sessions/player, collected in a SEPARATE capture pass
  (not interleaved with enrollment — session-order matters here, unlike LOO which is
  order-agnostic), same probe type.
- **Metric**: verification-session Mahalanobis distance against the FIXED enrollment centroid
  (not recomputed per test session — this is what makes it a true holdout, unlike LOO's
  exclude-and-recompute). Report both the separation ratio (inter/intra on this held-out split)
  AND the false-accept/false-reject rate at the current `min_separation_ratio` operating point
  (0.70, per CLAUDE.md's Phase 166 default) — the corpus has separation ratios but has never
  reported FAR/FRR at a stated threshold, which is the number a tournament-eligibility decision
  actually needs.

### 3.2 Probe type

Recommend **AIT** (Adaptive-trigger Isometric Tremor probe) as the primary probe for this
protocol: it is the only probe type that has already cleared the `>1.0` separation bar
(1.199, N=37, all_pairs_above_1=True per Phase 229/231) and has an established defensibility gate
(`ait_defensibility_ok`) already wired into `store.py`/`operator_api.py`. Reusing a
proven-separating probe means this protocol tests the ENROLLMENT/VERIFICATION SPLIT methodology
against a known-good signal, isolating "does the split reduce the ratio vs LOO" as the finding,
rather than conflating it with "is this probe type any good" (touchpad_corners already answered
that question negatively for its own probe — 0.728, structurally capped by P2/P3 biometric
proximity).

### 3.3 Corpus target

3-player active corpus (P1/P2/P3, matching every existing corpus). Per player: 10 enrollment +
10 verification = 20 new AIT sessions/player, 60 total. This roughly matches the existing AIT
corpus size (N=37 today) — the point is not a bigger corpus, it's a DIFFERENTLY STRUCTURED one
that supports a holdout metric the current corpus cannot produce after the fact (LOO and
train/test are not interchangeable after collection; the split has to be by session-collection
order, decided before capture).

### 3.4 L6B campaign (parallel, per §2.3)

N≥50 L6B probe sessions per player is the standing gate for `L6B_ENABLED`. This protocol does
not commit to hitting N=50 in one pass — it specifies the SAME enrollment/verification discipline
(hold out a verification set) so that whatever N is reached, the resulting number is a real
holdout separation estimate, not another LOO figure layered on top of the ones that already
exist for L4.

## 4. Statistical approach

### 4.1 Distance metric and covariance mode

Mahalanobis distance, covariance mode selected by the existing `analyze_interperson_separation.py`
rule (`COV_MIN_RATIO = 3.0`): diagonal covariance when `N/p < 3.0` (p = active feature count),
full Tikhonov-regularized covariance otherwise, with the `transition_warning` band (±margin
around 3.0, WIF-016) surfaced explicitly rather than silently flipping regimes near the boundary.
With p=10 (L4 active set) and N=20/player enrollment, N/p=2.0 — **diagonal covariance applies**;
this should be stated in the resulting report, not left implicit, since Phase 138→143 history in
this repo shows full-covariance noise suppression on small N produced a materially different
(and wrong) ratio once (1.552 full vs 1.261 diagonal corrected, same N=11 corpus).

### 4.2 Separation ratio

`ratio = mean(inter-player holdout distance) / mean(intra-player holdout distance)`, computed on
the verification set against the FIXED enrollment centroid (§3.1) — not the existing LOO
recomputation. Report both the holdout ratio and, for direct comparability, the LOO ratio on the
same combined 20-session/player pool, so the delta between the two methodologies is itself a
finding (if holdout ratio is meaningfully lower than LOO ratio on the same data, that's evidence
LOO has been overstating real-world separability all along — worth knowing either way).

### 4.3 Confidence intervals — an honest gap this protocol should close

No prior separation-ratio report in this repo carries a confidence interval; every number is a
point estimate. At N=10/player enrollment, bootstrap resampling (resample sessions with
replacement within each player, recompute the ratio, repeat ≥1000×) is cheap and gives an honest
spread. This protocol adds a 95% bootstrap CI to the headline ratio — the first time this corpus
has reported one.

### 4.4 FAR/FRR at the stated operating point

At `min_separation_ratio = 0.70` (current default): for each verification session, classify
ACCEPT (distance-ratio-implied same-player) or REJECT, against ground truth (the session's real
player label). Report FAR (a different player's session wrongly accepted) and FRR (the enrolled
player's own verification session wrongly rejected) as plain fractions with the N they're computed
over — this is the number the "Advisory Presence Confidence Model" (C-4.2) will actually need as
an input, not a bare ratio.

## 5. What this protocol deliberately does not attempt

- **Not** a new feature search — the 10 (L4) + 3 (L5) + 1 (L6B latency) signals are exactly the
  currently-shipped set. Finding new discriminative features is out of scope.
- **Not** a claim of population-level certification — 3 players stays a single-scope developer
  corpus, same caveat every existing separation number carries (`cert_scope=developer_self`,
  `population_certified=False` per the D-CERT-1/7 discipline already wired into the presence
  fusion — see `bridge/vapi_bridge/novel_presence_fusion.py`).
- **Not** a promotion decision — this protocol produces numbers for C-4.2/C-4.3 to weigh; it does
  not itself flip any `_ENABLED` flag or move a weight in `_PROVISIONAL_WEIGHTS`.

## 6. Deliverables (this protocol's own exit criteria)

1. This document, reviewed and approved before C-2.2 begins.
2. On approval, C-2.2 runs the enrollment+verification AIT sessions (hardware-gated, needs
   operator "ready?" per standing rig discipline) and the L6B campaign in parallel.
3. C-2.3 consumes the resulting corpus and produces the holdout ratio, LOO-vs-holdout delta,
   bootstrap CI, and FAR/FRR table described above.

## 7. Open questions for review (do not resolve unilaterally)

- Is N=10/10 enrollment/verification per player the right split size, or should it track the
  existing N=37 AIT corpus more closely (e.g., 15/15, reusing more of what may already exist as
  enrollment data if those sessions can be legitimately treated as pre-existing enrollment)?
- Should the L6B campaign's target be a hard N=50 before this protocol's C-2.3 report, or an
  honest interim report at whatever N is reached in the time available, with N=50 as a follow-on?
- Is AIT the right sole probe for this pass, or should touchpad_corners also get the
  enrollment/verification treatment despite its known ceiling (to check whether the holdout
  methodology itself changes its 0.728, even if it's expected to stay sub-1.0)?
