# Phase C — C-2.3: AIT Holdout Separation Report

**Date:** 2026-07-05  
**Branch:** feat/l9-consistency-adversarial-harness  
**Status:** MARGINAL — ratio=1.037 but 95% CI spans 1.0 (0.986, 1.119); see §3 and §5  
**Probe:** AIT (Adaptive-trigger Isometric Tremor, L2 hold 115–135 analog, 30s)  
**Methodology:** Enrollment/verification split (C-2.1 protocol) — first holdout metric in this corpus  

---

## 1. Corpus

### 1.1 Session Counts (valid only — after force-range filter)

| Player | Enrolled | Verified | Invalid (force OOB) |
|--------|----------|----------|---------------------|
| P1 | 9 / 10 | 9 / 10 | 2 (1 enroll + 1 verify) |
| P2 | 10 / 11 | 10 / 10 | 1 (1 enroll) |
| P3 | 8 / 10 | 11 / 11 | 2 (2 enroll) |
| **Total** | **27** | **30** | **5** |

### 1.2 Invalid Sessions — Extraction Failures (honest accounting)

The AIT extractor filters frames to `l2_trigger ∈ [90, 180]` (force range corresponding to the
115–135 analog target zone) and requires ≥512 qualifying frames. Five sessions failed this filter:

| File | Reason | Frame count in-range |
|------|--------|----------------------|
| enroll_P1_006.json | Trigger fully pressed (median=255); only 208 frames in [90,180] < 512 minimum | 208/30002 |
| enroll_P2_005.json | Trigger fully pressed (median=255); similar transition-only frames | ~200/30002 |
| enroll_P3_003.json | Trigger partially held (max=255, but sparse) | 9290 total held, filter narrow |
| enroll_P3_005.json | Trigger under-pressed (max=79 < 90 threshold) | 0/30002 |
| verify_P1_004.json | Trigger not sustained in target range | <512 qualifying frames |

**Root cause:** Protocol compliance rate ≈88% (52/57 sessions valid across all players). The force
target (115–135) is narrow — below the natural full-press reflex at 255. Future sessions should
display a live force readout and confirm the target range before starting.

### 1.3 Covariance Mode

**Diagonal covariance** (pooled from enrollment set).  
Per-player N ranges from 8 (P3) to 10 (P2). Minimum per-player N/p = 8/4 = **2.0 < COV_MIN_RATIO=3.0** →
diagonal covariance required (Phase 142 rule applies at the smallest group).  
Pooled N/p = 27/4 = 6.75, which would permit full covariance on the pooled set, but the per-player
centroid estimate (8 sessions for P3) is the binding constraint. Diagonal used for consistency and
smallest-group honesty.

---

## 2. Enrollment Centroids

| Player | `accel_tremor_peak_hz` | `roll_cos` | `roll_sin` | `pitch_cos` |
|--------|------------------------|------------|------------|-------------|
| P1 | 7.171 | 0.059 | -0.362 | -0.053 |
| P2 | 7.129 | -0.181 | 0.399 | -0.106 |
| P3 | 8.615 | -0.329 | 0.441 | -0.694 |

Pooled diagonal variance (enrollment):  
`accel_tremor_peak_hz`=3.706 | `roll_cos`=0.331 | `roll_sin`=0.660 | `pitch_cos`=0.179

**Critical observation:** P1 and P2 tremor centroids are nearly identical (7.171 vs 7.129 Hz,
Δ=0.042 Hz). Given `accel_tremor_peak_hz` pooled variance=3.706 (std≈1.925 Hz), this Δ is
well within 1 standard deviation — P1 and P2 are indistinguishable on the primary AIT discriminator
in this enrollment dataset.

---

## 3. Headline Results

| Metric | Value |
|--------|-------|
| **Holdout separation ratio** | **1.037** |
| **95% bootstrap CI** | **(0.986, 1.119)** — CI spans 1.0 |
| LOO ratio (combined pool) | 1.121 |
| LOO - holdout delta | +0.084 |
| mean_inter (verification) | 1.728 |
| mean_intra (verification) | 1.666 |

**Primary finding:** Holdout ratio = 1.037 — technically above 1.0 but the 95% CI (0.986, 1.119)
spans 1.0. The hypothesis that the true separation ratio exceeds 1.0 is NOT confirmed at 95%
confidence.  

**LOO overstates by +0.084:** The LOO ratio (1.121) uses the same sessions for building centroids
and measuring distances — it is an optimistic estimate. The holdout ratio (1.037) with a fixed
enrollment centroid is the more honest number for a tournament-enrollment scenario.

---

## 4. Pairwise Distance Table (verification sessions → enrollment centroids)

Rows = ground-truth player; columns = enrollment centroid.  
Bold diagonal = intra-player (should be smallest for classification to succeed).

| | P1 centroid | P2 centroid | P3 centroid |
|---|---|---|---|
| P1 | **1.847** | 1.231 | 1.921 |
| P2 | 1.969 | **1.198** | 1.818 |
| P3 | 1.991 | 1.414 | **1.944** |

**Classifier collapse finding:** P2 centroid is the nearest centroid for ALL three players'
verification sessions:
- P1 sessions: d(P1 centroid)=1.847, d(P2 centroid)=**1.231** — nearest is P2, not P1
- P2 sessions: d(P2 centroid)=**1.198** — nearest is P2 (correct)
- P3 sessions: d(P2 centroid)=**1.414**, d(P3 centroid)=1.944 — nearest is P2, not P3

**Root cause:** P1 and P2 tremor centroids are 0.042 Hz apart (within measurement noise given
std≈1.925 Hz). If verification sessions for P1 show a tremor peak slightly below P1's enrollment
centroid (7.171 Hz), P2's centroid (7.129 Hz) becomes the nearest. The roll/pitch features provide
insufficient compensating discriminative power at this N to overcome the tremor-hz ambiguity.

---

## 5. FAR / FRR (nearest-centroid classification)

| Player | FRR | FAR | Genuine N | Impostor N | GA | GR | IA | IR |
|--------|-----|-----|-----------|------------|----|----|----|----|
| P1 | 0.889 | 0.000 | 9 | 21 | 1 | 8 | 0 | 21 |
| P2 | 0.000 | 0.950 | 10 | 20 | 10 | 0 | 19 | 1 |
| P3 | 1.000 | 0.000 | 11 | 19 | 0 | 11 | 0 | 19 |
| **All** | **0.633** | **0.317** | 30 | 60 | 11 | 19 | 19 | 41 |

**Interpretation (classifier collapse):** The FAR/FRR pattern is characteristic of a degenerate
classifier — nearly all 30 verification sessions (28/30) are assigned to the P2 centroid:
- P1: FRR=0.889 (8 out of 9 P1 sessions misclassified as P2)
- P2: FRR=0.000, FAR=0.950 (correctly classifies its own 10 sessions, but also "accepts" 19
  impostors — all P1 and P3 sessions that fall nearest to P2's centroid)
- P3: FRR=1.000 (all 11 P3 sessions misclassified as P2)

This is not a random error — it is a structural collapse explained by §4: P2 centroid is the global
nearest for all three players in the verification set. The separation ratio of 1.037 reflects
that mean_inter (1.728) is slightly larger than mean_intra (1.666), but the variance is too large
and the centroids too close for classification to be reliable.

**These FAR/FRR values cannot be used as operating-point numbers for C-4.2.** They reflect
classifier collapse, not a meaningful biometric operating point. A separable system (ratio >> 1.0)
would show FRR and FAR both well below 0.5.

---

## 6. Comparison to Prior Corpus Numbers

| Metric | Value | Source |
|--------|-------|--------|
| AIT LOO ratio (prior corpus, N=37, LOO) | 1.199 | Phase 229/231 |
| **AIT holdout ratio (C-2.3)** | **1.037** | C-2.3, fixed enrollment centroids |
| AIT LOO ratio (C-2.3 combined pool) | 1.121 | C-2.3 LOO comparator |
| Holdout LOO delta | +0.084 | Methodological gap |
| Prior corpus CI | not computed | C-2.3 first bootstrap CI in this corpus |

**The LOO→holdout drop from 1.199→1.037 is consistent with what holdout methodology is designed
to reveal:** LOO is optimistic because it uses the session being evaluated to help build the
centroid estimate. The holdout protocol reveals that the AIT signal is not robust enough to
enroll players and generalize reliably to new sessions at this N and force-compliance rate.

---

## 7. Honest Limitations

- **3-player developer corpus only** — `cert_scope=developer_self`, `population_certified=False`.
- **5 invalid sessions (force OOB)** — 88% protocol compliance. Future captures need a live
  force display to maintain the 115–135 target zone.
- **P1/P2 tremor near-identical** — 7.171 vs 7.129 Hz — within measurement noise. This is a
  genuine feature ambiguity, not a data quality issue. More sessions would tighten the centroid
  but the centroids themselves may converge (two players with similar tremor frequencies).
- **N/player too small to characterize P3** — 8 enrollment sessions with p=4 features yields
  N/p=2.0, the minimum for reliable centroid estimation under diagonal covariance.
- **Roll/pitch features insufficient as compensating discriminators** — at this N, the gravity
  posture features do not overcome the tremor-hz ambiguity between P1 and P2.
- **No promotion decision** — this report characterizes the AIT signal honestly. It does not
  flip any `_ENABLED` flag or modify `_PROVISIONAL_WEIGHTS`.

---

## 8. Summary

| Finding | Value | Actionable consequence |
|---------|-------|------------------------|
| Holdout ratio | 1.037 | Marginal — CI spans 1.0 |
| 95% CI | (0.986, 1.119) | Cannot claim robust separability |
| Classifier behavior | Collapsed to P2 | FAR/FRR not usable for C-4.2 |
| LOO-holdout gap | +0.084 | LOO overstates; holdout is honest number |
| Force compliance | 88% (52/57) | Protocol refinement needed |
| P1/P2 tremor delta | 0.042 Hz (0.022 std units) | Primary discriminator insufficient |

**C-2.3 verdict:** The AIT holdout analysis reveals a **marginal and unreliable separation** at
this corpus size and force-compliance rate. The ratio nominally exceeds 1.0 but the CI cannot
reject the null (ratio ≤ 1.0). The nearest-centroid classifier degenerates to always-predict-P2.

**What this does NOT mean:** The AIT signal has no value. The prior LOO result (1.199, N=37) was
honest and the methodology was correct. The holdout analysis reveals that 9–10 enrollment sessions
are insufficient to build reliable centroids when two players have similar tremor frequencies. More
sessions per player (target N≥20 enrollment) would reduce centroid estimation noise.

**C-4.2 / C-3.2 next steps:** C-4.2 (Advisory Presence Confidence Model) should weight AIT as
low-confidence until the enrollment N reaches a regime where the classifier does not collapse.
C-3.2 (KAS quality sessions) continues on its independent track.

---

## 9. Next Steps

- **C-2.3: CLOSED** by this report (with honest marginal finding).
- **C-3.2** (KAS quality measurement sessions) — independent track, unaffected.
- **C-4.2** — AIT weight should be advisory/low-confidence; do not use §5 FAR/FRR as inputs.
- **C-2.3 follow-up (optional):** Re-run with N≥20 enrollment per player and stricter force
  compliance (live display during capture). This is not a gate on any other Phase C deliverable.
- **L6B campaign** (parallel, N=0) — `L6B_ENABLED` gate stays at N≥50 regardless of C-2.3 result.
