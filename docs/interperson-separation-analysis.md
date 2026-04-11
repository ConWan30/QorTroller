# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 33 included, 0 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (8 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `trigger_onset_velocity_l2`, `trigger_onset_velocity_r2`, `grip_asymmetry`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.817 |
| Mean inter-player distance | 0.584 |
| **Separation ratio (inter/intra)** | **0.715** |
| Leave-one-out classification accuracy | 48.5% (16/33) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.72). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 10       | 0.813      | 0.542     | 0.273     | 1.838     | 0.656        |
| Player 2 | 12       | 0.514      | 0.328     | 0.109     | 1.005     | 0.505        |
| Player 3 | 11       | 1.124      | 0.550     | 0.160     | 1.971     | 1.190        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.474    | 0.866    |
| Player 2 | 0.474    | —        | 0.413    |
| Player 3 | 0.866    | 0.413    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=10 sessions, mean=0.813):
  1.105, 0.273, 0.890, 0.322, 1.663, 0.441, 0.339, 0.391, 1.838, 0.870

**Player 2** (N=12 sessions, mean=0.514):
  0.191, 0.109, 0.215, 0.726, 0.232, 1.005, 0.862, 0.285, 0.827, 0.133, 0.803, 0.775

**Player 3** (N=11 sessions, mean=1.124):
  1.190, 1.945, 1.400, 0.945, 0.683, 0.160, 1.431, 0.421, 1.344, 1.971, 0.876

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                 | Player 3                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------ | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 5778.5106 (+/-3915.5459) | 7897.4825 (+/-2901.5414) | 9876.5282 (+/-5996.2192) | 4098.0176   |
| tremor_peak_hz                   | 10.5654 (+/-27.3232)     | 1.7146 (+/-3.8554)       | 2.8501 (+/-3.8929)       | 8.8508      |
| accel_magnitude_spectral_entropy | 4.1330 (+/-0.2560)       | 3.9976 (+/-0.2576)       | 3.9228 (+/-0.4984)       | 0.2102      |
| touchpad_spatial_entropy         | 1.5168 (+/-0.2720)       | 1.3853 (+/-0.4469)       | 1.3791 (+/-0.4363)       | 0.1377      |
| stick_autocorr_lag1              | 0.0068 (+/-0.0135)       | 0.0067 (+/-0.0198)       | 0.0018 (+/-0.0058)       | 0.0049      |
| stick_autocorr_lag5              | 0.0038 (+/-0.0075)       | 0.0055 (+/-0.0170)       | 0.0009 (+/-0.0028)       | 0.0046      |
| touch_position_variance          | 0.0315 (+/-0.0143)       | 0.0279 (+/-0.0185)       | 0.0302 (+/-0.0146)       | 0.0036      |
| tremor_band_power                | 0.0004 (+/-0.0007)       | 0.0001 (+/-0.0003)       | 0.0000 (+/-0.0001)       | 0.0003      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| trigger_onset_velocity_l2        | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| trigger_onset_velocity_r2        | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| grip_asymmetry                   | 1.0000 (+/-0.0000)       | 1.0000 (+/-0.0000)       | 1.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 48.5% (16/33 sessions correctly assigned)**

Misclassified sessions:

| Session                                           | True Player | Predicted | Best Dist |
| ------------------------------------------------- | ----------- | --------- | --------- |
| terminal_cal_P1/touchpad_corners_20260327T230404Z | Player 1    | Player 2  | 0.267     |
| terminal_cal_P1/touchpad_corners_20260405T210157Z | Player 1    | Player 2  | 0.062     |
| terminal_cal_P1/touchpad_corners_20260411T201020Z | Player 1    | Player 3  | 0.990     |
| terminal_cal_P1/touchpad_corners_20260411T201619Z | Player 1    | Player 3  | 0.033     |
| terminal_cal_P2/touchpad_corners_20260329T203046Z | Player 2    | Player 1  | 0.353     |
| terminal_cal_P2/touchpad_corners_20260404T191532Z | Player 2    | Player 3  | 0.192     |
| terminal_cal_P2/touchpad_corners_20260405T033521Z | Player 2    | Player 1  | 0.602     |
| terminal_cal_P2/touchpad_corners_20260405T210457Z | Player 2    | Player 3  | 0.452     |
| terminal_cal_P2/touchpad_corners_20260411T141707Z | Player 2    | Player 1  | 0.262     |
| terminal_cal_P2/touchpad_corners_20260411T142422Z | Player 2    | Player 1  | 0.439     |
| terminal_cal_P2/touchpad_corners_20260411T164609Z | Player 2    | Player 3  | 0.396     |
| terminal_cal_P2/touchpad_corners_20260411T210937Z | Player 2    | Player 3  | 0.380     |
| terminal_cal_P3/touchpad_corners_20260327T232204Z | Player 3    | Player 1  | 0.396     |
| terminal_cal_P3/touchpad_corners_20260328T161059Z | Player 3    | Player 1  | 1.112     |
| terminal_cal_P3/touchpad_corners_20260329T032924Z | Player 3    | Player 1  | 0.585     |
| terminal_cal_P3/touchpad_corners_20260329T215413Z | Player 3    | Player 1  | 0.228     |
| terminal_cal_P3/touchpad_corners_20260404T203748Z | Player 3    | Player 1  | 0.270     |

## Excluded Sessions

No sessions excluded.

## Recommendations for L4 Multi-Person Calibration

### Implications for VAPI Protocol

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.72 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=11 sessions/player average is adequate.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*