# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 114 included, 5 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (11 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.678 |
| Mean inter-player distance | 0.278 |
| **Separation ratio (inter/intra)** | **0.410** |
| Leave-one-out classification accuracy | 31.6% (36/114) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.41). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 53       | 0.722      | 0.890     | 0.015     | 4.415     | 0.296        |
| Player 2 | 31       | 0.696      | 0.536     | 0.097     | 2.347     | 0.506        |
| Player 3 | 27       | 0.662      | 0.446     | 0.124     | 1.850     | 0.614        |
| Player 4 | 3        | 0.632      | 0.225     | 0.441     | 0.948     | 0.507        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 | Player 4 |
| -------- | -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.358    | 0.465    | 0.490    |
| Player 2 | 0.358    | —        | 0.109    | 0.160    |
| Player 3 | 0.465    | 0.109    | —        | 0.085    |
| Player 4 | 0.490    | 0.160    | 0.085    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=53 sessions, mean=0.722):
  1.490, 0.296, 0.038, 4.356, 0.125, 0.031, 1.324, 0.199, 0.284, 0.096, 0.251, 0.142, 0.148, 0.103, 0.237, 0.286, 1.402, 1.381, 0.448, 0.154, 1.456, 0.221, 0.189, 0.015, 0.684, 0.203, 0.777, 0.215, 1.862, 0.053, 0.151, 1.009, 0.046, 1.395, 0.234, 0.422, 0.492, 0.087, 4.415, 0.483, 1.472, 1.342, 0.901, 1.409, 0.292, 1.214, 1.176, 0.890, 0.594, 0.880, 0.219, 0.058, 0.641

**Player 2** (N=31 sessions, mean=0.696):
  1.209, 0.734, 0.181, 0.874, 0.334, 0.613, 0.227, 2.347, 0.123, 0.331, 0.146, 0.249, 0.374, 0.506, 0.752, 0.908, 0.799, 1.058, 1.134, 1.692, 0.957, 0.471, 0.398, 0.137, 0.426, 0.395, 0.956, 1.818, 0.097, 1.113, 0.219

**Player 3** (N=27 sessions, mean=0.662):
  1.657, 0.614, 0.641, 0.418, 0.971, 0.348, 0.305, 0.270, 0.131, 0.124, 0.951, 0.247, 1.026, 0.346, 0.281, 1.035, 1.036, 0.264, 0.686, 0.293, 0.958, 1.204, 0.703, 0.557, 0.174, 0.771, 1.850

**Player 4** (N=3 sessions, mean=0.632):
  0.441, 0.948, 0.507

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                 | Player 3                 | Player 4                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------ | ------------------------ | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 8189.2669 (+/-6197.4775) | 6275.0155 (+/-4551.8948) | 5685.5481 (+/-4068.3685) | 5545.4994 (+/-3625.6608) | 2643.7675   |
| tremor_peak_hz                   | 0.7349 (+/-1.3165)       | 4.3118 (+/-14.2120)      | 4.2067 (+/-14.9321)      | 0.0000 (+/-0.0000)       | 4.3118      |
| touchpad_spatial_entropy         | 0.3633 (+/-0.8696)       | 0.5712 (+/-1.0968)       | 0.3517 (+/-0.7790)       | 1.5971 (+/-1.3247)       | 1.2454      |
| accel_magnitude_spectral_entropy | 4.7936 (+/-0.6995)       | 4.9237 (+/-1.0446)       | 4.7074 (+/-1.2349)       | 4.4134 (+/-0.3049)       | 0.5103      |
| stick_autocorr_lag1              | 0.1122 (+/-0.0834)       | 0.0649 (+/-0.0801)       | 0.0548 (+/-0.0709)       | 0.0040 (+/-0.0057)       | 0.1081      |
| stick_autocorr_lag5              | 0.1005 (+/-0.0767)       | 0.0573 (+/-0.0709)       | 0.0471 (+/-0.0615)       | 0.0029 (+/-0.0040)       | 0.0977      |
| grip_asymmetry                   | 1.0481 (+/-0.1411)       | 1.0368 (+/-0.1119)       | 1.0830 (+/-0.2589)       | 1.0000 (+/-0.0000)       | 0.0830      |
| touch_position_variance          | 0.0066 (+/-0.0160)       | 0.0084 (+/-0.0172)       | 0.0040 (+/-0.0088)       | 0.0193 (+/-0.0152)       | 0.0153      |
| trigger_onset_velocity_r2        | 0.0032 (+/-0.0047)       | 0.0055 (+/-0.0224)       | 0.0020 (+/-0.0028)       | 0.0000 (+/-0.0000)       | 0.0055      |
| tremor_band_power                | 0.0029 (+/-0.0032)       | 0.0024 (+/-0.0031)       | 0.0020 (+/-0.0026)       | 0.0000 (+/-0.0000)       | 0.0029      |
| trigger_onset_velocity_l2        | 0.0011 (+/-0.0021)       | 0.0007 (+/-0.0016)       | 0.0010 (+/-0.0022)       | 0.0000 (+/-0.0000)       | 0.0011      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 31.6% (36/114 sessions correctly assigned)**

Misclassified sessions:

| Session                                            | True Player | Predicted | Best Dist |
| -------------------------------------------------- | ----------- | --------- | --------- |
| hw_005                                             | Player 1    | Player 4  | 1.001     |
| hw_006                                             | Player 1    | Player 2  | 0.082     |
| hw_011                                             | Player 1    | Player 4  | 0.835     |
| hw_019                                             | Player 1    | Player 2  | 0.134     |
| hw_021                                             | Player 1    | Player 4  | 0.914     |
| hw_023                                             | Player 1    | Player 4  | 0.052     |
| hw_027                                             | Player 1    | Player 2  | 0.179     |
| hw_029                                             | Player 1    | Player 4  | 0.197     |
| hw_031                                             | Player 1    | Player 4  | 0.295     |
| hw_036                                             | Player 1    | Player 4  | 0.520     |
| hw_039                                             | Player 1    | Player 2  | 0.141     |
| hw_040                                             | Player 1    | Player 4  | 0.074     |
| hw_041                                             | Player 1    | Player 4  | 0.035     |
| hw_045                                             | Player 2    | Player 1  | 0.856     |
| hw_046                                             | Player 2    | Player 1  | 0.383     |
| hw_047                                             | Player 2    | Player 3  | 0.072     |
| hw_048                                             | Player 2    | Player 4  | 0.733     |
| hw_049                                             | Player 2    | Player 1  | 0.032     |
| hw_050                                             | Player 2    | Player 4  | 0.472     |
| hw_051                                             | Player 2    | Player 1  | 0.132     |
| hw_052                                             | Player 2    | Player 1  | 1.995     |
| hw_053                                             | Player 2    | Player 4  | 0.050     |
| hw_054                                             | Player 2    | Player 1  | 0.029     |
| hw_056                                             | Player 2    | Player 4  | 0.105     |
| hw_057                                             | Player 2    | Player 1  | 0.034     |
| hw_058                                             | Player 2    | Player 1  | 0.154     |
| hw_060                                             | Player 3    | Player 1  | 0.152     |
| hw_061                                             | Player 3    | Player 1  | 0.177     |
| hw_062                                             | Player 3    | Player 1  | 0.052     |
| hw_063                                             | Player 3    | Player 1  | 0.508     |
| hw_064                                             | Player 3    | Player 1  | 0.123     |
| hw_065                                             | Player 3    | Player 1  | 0.189     |
| hw_066                                             | Player 3    | Player 2  | 0.163     |
| hw_068                                             | Player 3    | Player 4  | 0.104     |
| hw_070                                             | Player 3    | Player 2  | 0.072     |
| hw_071                                             | Player 3    | Player 1  | 0.488     |
| hw_072                                             | Player 3    | Player 4  | 0.210     |
| terminal_cal_P1/natural_grip_20260326T234127Z      | Player 1    | Player 4  | 0.033     |
| terminal_cal_P1/resting_baseline_20260326T233432Z  | Player 1    | Player 4  | 0.984     |
| terminal_cal_P1/spectral_accel_20260327T011014Z    | Player 1    | Player 4  | 0.854     |
| terminal_cal_P1/stick_sweeps_20260327T000958Z      | Player 1    | Player 4  | 0.413     |
| terminal_cal_P1/touchpad_corners_20260327T031241Z  | Player 1    | Player 4  | 0.920     |
| terminal_cal_P1/touchpad_corners_20260327T230404Z  | Player 1    | Player 2  | 0.104     |
| terminal_cal_P1/touchpad_corners_20260328T142201Z  | Player 1    | Player 4  | 0.725     |
| terminal_cal_P1/touchpad_freeform_20260327T030955Z | Player 1    | Player 4  | 0.688     |
| terminal_cal_P1/touchpad_freeform_20260328T141850Z | Player 1    | Player 4  | 0.131     |
| terminal_cal_P1/touchpad_swipes_20260327T030742Z   | Player 1    | Player 4  | 0.391     |
| terminal_cal_P2/button_sequence_20260327T021315Z   | Player 2    | Player 3  | 0.648     |
| terminal_cal_P2/natural_grip_20260327T015604Z      | Player 2    | Player 4  | 0.772     |
| terminal_cal_P2/natural_grip_20260329T032252Z      | Player 2    | Player 4  | 0.658     |
| terminal_cal_P2/resting_baseline_20260327T015045Z  | Player 2    | Player 4  | 0.918     |
| terminal_cal_P2/resting_baseline_20260329T031701Z  | Player 2    | Player 4  | 0.995     |
| terminal_cal_P2/spectral_accel_20260327T022944Z    | Player 2    | Player 3  | 1.632     |
| terminal_cal_P2/stick_sweeps_20260327T022131Z      | Player 2    | Player 4  | 0.836     |
| terminal_cal_P2/touchpad_corners_20260328T003556Z  | Player 2    | Player 1  | 0.115     |
| terminal_cal_P2/touchpad_corners_20260328T153820Z  | Player 2    | Player 1  | 0.050     |
| terminal_cal_P2/touchpad_freeform_20260328T003347Z | Player 2    | Player 1  | 0.101     |
| terminal_cal_P2/touchpad_freeform_20260328T153604Z | Player 2    | Player 4  | 0.253     |
| terminal_cal_P2/touchpad_freeform_20260329T005231Z | Player 2    | Player 1  | 0.603     |
| terminal_cal_P2/touchpad_swipes_20260328T003136Z   | Player 2    | Player 1  | 1.464     |
| terminal_cal_P2/touchpad_swipes_20260328T153354Z   | Player 2    | Player 4  | 0.086     |
| terminal_cal_P2/touchpad_swipes_20260329T005021Z   | Player 2    | Player 4  | 0.973     |
| terminal_cal_P2/trigger_rhythm_20260327T020442Z    | Player 2    | Player 3  | 0.112     |
| terminal_cal_P3/button_sequence_20260328T014042Z   | Player 3    | Player 4  | 0.996     |
| terminal_cal_P3/natural_grip_20260328T005708Z      | Player 3    | Player 4  | 0.318     |
| terminal_cal_P3/resting_baseline_20260328T003917Z  | Player 3    | Player 4  | 1.004     |
| terminal_cal_P3/resting_baseline_20260328T011813Z  | Player 3    | Player 4  | 1.005     |
| terminal_cal_P3/spectral_accel_20260328T015847Z    | Player 3    | Player 4  | 0.225     |
| terminal_cal_P3/stick_sweeps_20260328T014814Z      | Player 3    | Player 4  | 0.671     |
| terminal_cal_P3/touchpad_corners_20260327T232204Z  | Player 3    | Player 4  | 0.254     |
| terminal_cal_P3/touchpad_corners_20260328T161059Z  | Player 3    | Player 4  | 0.926     |
| terminal_cal_P3/touchpad_freeform_20260327T231922Z | Player 3    | Player 1  | 0.742     |
| terminal_cal_P3/touchpad_freeform_20260328T160809Z | Player 3    | Player 1  | 0.244     |
| terminal_cal_P3/touchpad_swipes_20260327T231705Z   | Player 3    | Player 4  | 0.524     |
| terminal_cal_P3/touchpad_swipes_20260328T160459Z   | Player 3    | Player 2  | 0.093     |
| terminal_cal_P3/trigger_rhythm_20260328T011017Z    | Player 3    | Player 4  | 0.739     |
| terminal_cal_P3/trigger_rhythm_20260328T013207Z    | Player 3    | Player 1  | 1.389     |
| terminal_cal_P4/touchpad_freeform_20260329T032705Z | Player 4    | Player 1  | 0.462     |

## Excluded Sessions

| Session | Reason                                       | Polling Rate Hz |
| ------- | -------------------------------------------- | --------------- |
| hw_043  | polling_rate_hz=203.6 outside [800.0,1100.0] | 203.55          |
| hw_044  | polling_rate_hz=492.7 outside [800.0,1100.0] | 492.67          |
| hw_067  | polling_rate_hz=72.2 outside [800.0,1100.0]  | 72.16           |
| hw_069  | polling_rate_hz=307.1 outside [800.0,1100.0] | 307.14          |
| hw_073  | polling_rate_hz=49.7 outside [800.0,1100.0]  | 49.7            |

## Recommendations for L4 Multi-Person Calibration

### Implications for VAPI Protocol

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.41 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=28 sessions/player average is marginal for Player 2/3.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*