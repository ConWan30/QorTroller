# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 31 included, 0 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (7 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `trigger_onset_velocity_l2`, `grip_asymmetry`, `touch_position_variance`, `press_timing_jitter_variance`, `touchpad_spatial_entropy`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 1.862 |
| Mean inter-player distance | 1.227 |
| **Separation ratio (inter/intra)** | **0.659** |
| Leave-one-out classification accuracy | 41.9% (13/31) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.66). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 9        | 0.928      | 0.910     | 0.125     | 3.359     | 0.644        |
| Player 2 | 10       | 2.029      | 1.488     | 0.711     | 5.641     | 1.471        |
| Player 3 | 12       | 2.627      | 1.785     | 1.444     | 7.600     | 1.928        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.748    | 1.479    |
| Player 2 | 0.748    | —        | 1.454    |
| Player 3 | 1.479    | 1.454    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=9 sessions, mean=0.928):
  0.355, 0.125, 0.479, 0.644, 0.460, 3.359, 0.781, 1.124, 1.027

**Player 2** (N=10 sessions, mean=2.029):
  5.641, 1.263, 1.419, 1.906, 3.597, 2.707, 1.523, 0.711, 0.789, 0.734

**Player 3** (N=12 sessions, mean=2.627):
  1.444, 1.651, 1.742, 5.306, 2.097, 1.857, 1.867, 1.990, 1.769, 2.199, 7.600, 2.005

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                | Player 2                 | Player 3                | Inter-Range |
| -------------------------------- | ----------------------- | ------------------------ | ----------------------- | ----------- |
| micro_tremor_accel_variance      | 1193.5877 (+/-645.9129) | 3652.8551 (+/-7311.4229) | 1118.4613 (+/-886.1634) | 2534.3938   |
| accel_magnitude_spectral_entropy | 4.6311 (+/-1.2101)      | 5.1243 (+/-1.5956)       | 5.8125 (+/-1.5812)      | 1.1814      |
| tremor_peak_hz                   | 7.0456 (+/-0.6517)      | 6.7824 (+/-1.1426)       | 7.4270 (+/-0.7186)      | 0.6446      |
| tremor_band_power                | 0.6519 (+/-0.2182)      | 0.5813 (+/-0.2773)       | 0.3937 (+/-0.3014)      | 0.2582      |
| stick_autocorr_lag1              | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0023 (+/-0.0076)      | 0.0023      |
| stick_autocorr_lag5              | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0012 (+/-0.0039)      | 0.0012      |
| trigger_onset_velocity_r2        | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0001 (+/-0.0004)      | 0.0001      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)      | 0.0000      |
| trigger_onset_velocity_l2        | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)      | 0.0000      |
| grip_asymmetry                   | 1.0000 (+/-0.0000)      | 1.0000 (+/-0.0000)       | 1.0000 (+/-0.0000)      | 0.0000      |
| touch_position_variance          | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)      | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)      | 0.0000      |
| touchpad_spatial_entropy         | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)      | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 41.9% (13/31 sessions correctly assigned)**

Misclassified sessions:

| Session                               | True Player | Predicted | Best Dist |
| ------------------------------------- | ----------- | --------- | --------- |
| terminal_cal_P1/tremor_resting_P1_006 | Player 1    | Player 3  | 2.312     |
| terminal_cal_P2/tremor_resting_P2_001 | Player 2    | Player 1  | 6.185     |
| terminal_cal_P2/tremor_resting_P2_002 | Player 2    | Player 1  | 1.166     |
| terminal_cal_P2/tremor_resting_P2_003 | Player 2    | Player 1  | 1.248     |
| terminal_cal_P2/tremor_resting_P2_004 | Player 2    | Player 1  | 1.935     |
| terminal_cal_P2/tremor_resting_P2_005 | Player 2    | Player 3  | 2.608     |
| terminal_cal_P2/tremor_resting_P2_006 | Player 2    | Player 3  | 1.944     |
| terminal_cal_P2/tremor_resting_P2_007 | Player 2    | Player 1  | 1.040     |
| terminal_cal_P2/tremor_resting_P2_008 | Player 2    | Player 1  | 0.528     |
| terminal_cal_P2/tremor_resting_P2_009 | Player 2    | Player 1  | 0.654     |
| terminal_cal_P2/tremor_resting_P2_010 | Player 2    | Player 1  | 0.683     |
| terminal_cal_P3/tremor_resting_P3_001 | Player 3    | Player 1  | 0.193     |
| terminal_cal_P3/tremor_resting_P3_002 | Player 3    | Player 1  | 1.418     |
| terminal_cal_P3/tremor_resting_P3_003 | Player 3    | Player 1  | 1.538     |
| terminal_cal_P3/tremor_resting_P3_004 | Player 3    | Player 2  | 5.774     |
| terminal_cal_P3/tremor_resting_P3_010 | Player 3    | Player 1  | 0.858     |
| terminal_cal_P3/tremor_resting_P3_011 | Player 3    | Player 1  | 8.039     |
| terminal_cal_P3/tremor_resting_P3_012 | Player 3    | Player 1  | 0.641     |

## Excluded Sessions

No sessions excluded.

## Recommendations for L4 Multi-Person Calibration

### Implications for VAPI Protocol

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.66 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=10 sessions/player average is marginal for Player 2/3.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*