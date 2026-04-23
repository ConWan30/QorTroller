# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 331 included, 5 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (11 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.620 |
| Mean inter-player distance | 0.049 |
| **Separation ratio (inter/intra)** | **0.079** |
| Leave-one-out classification accuracy | 30.5% (101/331) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.08). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 136      | 0.569      | 0.567     | 0.018     | 3.861     | 0.477        |
| Player 2 | 100      | 0.653      | 1.130     | 0.022     | 9.193     | 0.523        |
| Player 3 | 95       | 0.638      | 0.594     | 0.022     | 5.067     | 0.581        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.018    | 0.055    |
| Player 2 | 0.018    | —        | 0.073    |
| Player 3 | 0.055    | 0.073    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=136 sessions, mean=0.569):
  0.824, 0.034, 0.137, 3.034, 0.243, 0.142, 0.716, 0.292, 0.348, 0.223, 0.326, 0.249, 0.068, 0.218, 0.018, 0.349, 0.765, 1.072, 0.137, 0.262, 1.121, 0.306, 0.043, 0.166, 0.292, 0.294, 0.353, 0.302, 1.388, 0.195, 0.063, 0.506, 0.191, 1.081, 0.028, 0.123, 0.167, 0.218, 0.479, 0.624, 0.639, 0.611, 0.602, 0.571, 0.528, 0.561, 0.729, 0.761, 0.732, 0.701, 0.746, 3.073, 0.510, 0.252, 0.363, 0.538, 0.414, 0.576, 0.706, 0.168, 0.504, 0.071, 1.210, 0.583, 1.509, 3.861, 0.191, 1.405, 2.754, 0.161, 0.812, 0.727, 0.434, 0.769, 0.043, 0.642, 0.278, 0.454, 0.095, 0.319, 0.328, 0.942, 0.365, 0.033, 0.126, 0.616, 0.747, 0.232, 0.082, 0.083, 0.156, 0.070, 0.351, 1.182, 1.736, 1.202, 0.469, 0.421, 0.304, 0.195, 0.075, 0.341, 0.409, 0.118, 0.232, 0.136, 0.351, 0.478, 0.477, 0.079, 0.702, 0.728, 0.716, 0.752, 0.520, 0.826, 0.639, 0.681, 0.680, 0.813, 0.823, 0.824, 0.825, 0.457, 0.759, 0.621, 0.698, 0.730, 0.602, 0.654, 0.599, 0.509, 0.474, 0.476, 0.362, 0.583

**Player 2** (N=100 sessions, mean=0.653):
  0.706, 0.393, 0.212, 0.664, 0.126, 0.491, 0.057, 1.458, 0.156, 0.125, 0.022, 0.248, 0.155, 0.242, 0.454, 0.671, 0.611, 0.673, 0.633, 0.748, 0.726, 0.727, 0.759, 0.748, 0.575, 0.575, 0.061, 0.362, 0.451, 0.261, 9.193, 7.006, 0.268, 1.245, 0.690, 0.615, 0.786, 0.836, 0.779, 0.721, 0.217, 0.168, 0.029, 0.319, 0.243, 0.483, 0.611, 0.063, 0.378, 0.184, 0.569, 0.545, 0.190, 0.349, 0.539, 0.185, 0.769, 0.095, 0.962, 0.088, 0.079, 0.065, 0.671, 0.487, 1.108, 0.128, 0.822, 0.593, 0.045, 0.120, 0.180, 0.115, 0.061, 0.049, 0.084, 0.089, 0.561, 2.233, 0.456, 0.457, 0.642, 0.844, 0.843, 0.760, 0.780, 0.790, 0.782, 0.799, 0.840, 0.823, 0.835, 0.756, 0.694, 0.691, 0.505, 0.445, 0.655, 0.506, 0.465, 0.236

**Player 3** (N=95 sessions, mean=0.638):
  0.745, 0.315, 0.332, 0.184, 0.551, 0.136, 0.109, 0.089, 0.173, 0.029, 0.537, 0.245, 0.463, 0.466, 0.496, 0.581, 0.541, 0.609, 0.355, 0.593, 0.520, 0.597, 0.614, 0.620, 0.613, 0.625, 0.765, 0.395, 1.028, 0.368, 0.629, 0.517, 5.067, 2.063, 0.316, 0.273, 0.770, 0.770, 0.257, 0.542, 0.276, 0.721, 0.399, 0.133, 0.040, 0.499, 1.257, 0.665, 1.207, 1.575, 0.927, 0.704, 0.375, 0.518, 0.896, 0.556, 0.788, 0.722, 2.347, 1.009, 1.478, 0.282, 0.454, 0.022, 0.442, 0.395, 0.137, 0.299, 0.354, 1.164, 0.262, 0.119, 0.661, 0.612, 0.594, 0.609, 0.679, 0.771, 0.383, 0.769, 0.767, 0.767, 0.590, 0.614, 0.625, 0.705, 0.769, 0.547, 0.655, 0.158, 0.650, 0.552, 0.509, 0.595, 1.130

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                  | Player 3                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------- | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 6877.8095 (+/-6571.7384) | 7028.0506 (+/-10694.0003) | 6428.5536 (+/-7139.0140) | 599.4971    |
| touchpad_spatial_entropy         | 0.5389 (+/-0.8638)       | 0.6799 (+/-1.0250)        | 0.6792 (+/-1.0736)       | 0.1410      |
| tremor_peak_hz                   | 7.0598 (+/-3.5180)       | 6.9778 (+/-1.5490)        | 6.9626 (+/-2.4109)       | 0.0972      |
| accel_magnitude_spectral_entropy | 4.6071 (+/-0.8872)       | 4.6596 (+/-1.1026)        | 4.6240 (+/-1.1493)       | 0.0525      |
| stick_autocorr_lag1              | 0.0515 (+/-0.0746)       | 0.0255 (+/-0.0552)        | 0.0197 (+/-0.0472)       | 0.0318      |
| stick_autocorr_lag5              | 0.0465 (+/-0.0679)       | 0.0228 (+/-0.0492)        | 0.0173 (+/-0.0416)       | 0.0292      |
| grip_asymmetry                   | 1.0193 (+/-0.0913)       | 1.0124 (+/-0.0648)        | 1.0246 (+/-0.1430)       | 0.0122      |
| tremor_band_power                | 0.6285 (+/-0.1714)       | 0.6172 (+/-0.2121)        | 0.6190 (+/-0.2172)       | 0.0114      |
| trigger_onset_velocity_l2        | 0.0093 (+/-0.0301)       | 0.0120 (+/-0.0386)        | 0.0132 (+/-0.0350)       | 0.0040      |
| trigger_onset_velocity_r2        | 0.0015 (+/-0.0034)       | 0.0020 (+/-0.0127)        | 0.0008 (+/-0.0019)       | 0.0012      |
| touch_position_variance          | 0.0102 (+/-0.0154)       | 0.0099 (+/-0.0155)        | 0.0101 (+/-0.0154)       | 0.0003      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)        | 0.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)        | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 30.5% (101/331 sessions correctly assigned)**

Misclassified sessions:

| Session                                                | True Player | Predicted | Best Dist |
| ------------------------------------------------------ | ----------- | --------- | --------- |
| hw_005                                                 | Player 1    | Player 3  | 0.769     |
| hw_007                                                 | Player 1    | Player 2  | 0.119     |
| hw_008                                                 | Player 1    | Player 2  | 3.016     |
| hw_009                                                 | Player 1    | Player 2  | 0.225     |
| hw_010                                                 | Player 1    | Player 2  | 0.124     |
| hw_011                                                 | Player 1    | Player 3  | 0.662     |
| hw_012                                                 | Player 1    | Player 2  | 0.273     |
| hw_013                                                 | Player 1    | Player 2  | 0.330     |
| hw_014                                                 | Player 1    | Player 2  | 0.205     |
| hw_015                                                 | Player 1    | Player 2  | 0.308     |
| hw_016                                                 | Player 1    | Player 2  | 0.230     |
| hw_017                                                 | Player 1    | Player 2  | 0.051     |
| hw_018                                                 | Player 1    | Player 2  | 0.200     |
| hw_020                                                 | Player 1    | Player 2  | 0.331     |
| hw_021                                                 | Player 1    | Player 3  | 0.710     |
| hw_022                                                 | Player 1    | Player 2  | 1.053     |
| hw_023                                                 | Player 1    | Player 3  | 0.084     |
| hw_024                                                 | Player 1    | Player 2  | 0.244     |
| hw_025                                                 | Player 1    | Player 2  | 1.102     |
| hw_026                                                 | Player 1    | Player 2  | 0.288     |
| hw_027                                                 | Player 1    | Player 2  | 0.030     |
| hw_028                                                 | Player 1    | Player 2  | 0.148     |
| hw_029                                                 | Player 1    | Player 3  | 0.237     |
| hw_030                                                 | Player 1    | Player 2  | 0.276     |
| hw_031                                                 | Player 1    | Player 3  | 0.298     |
| hw_032                                                 | Player 1    | Player 2  | 0.284     |
| hw_033                                                 | Player 1    | Player 2  | 1.370     |
| hw_034                                                 | Player 1    | Player 2  | 0.177     |
| hw_035                                                 | Player 1    | Player 2  | 0.046     |
| hw_036                                                 | Player 1    | Player 3  | 0.451     |
| hw_037                                                 | Player 1    | Player 2  | 0.173     |
| hw_038                                                 | Player 1    | Player 2  | 1.062     |
| hw_040                                                 | Player 1    | Player 3  | 0.071     |
| hw_041                                                 | Player 1    | Player 3  | 0.113     |
| hw_042                                                 | Player 1    | Player 2  | 0.200     |
| hw_047                                                 | Player 2    | Player 3  | 0.139     |
| hw_048                                                 | Player 2    | Player 3  | 0.591     |
| hw_050                                                 | Player 2    | Player 3  | 0.418     |
| hw_053                                                 | Player 2    | Player 3  | 0.083     |
| hw_056                                                 | Player 2    | Player 3  | 0.175     |
| hw_060                                                 | Player 3    | Player 2  | 0.242     |
| hw_061                                                 | Player 3    | Player 2  | 0.259     |
| hw_062                                                 | Player 3    | Player 2  | 0.111     |
| hw_063                                                 | Player 3    | Player 2  | 0.478     |
| hw_064                                                 | Player 3    | Player 2  | 0.065     |
| hw_065                                                 | Player 3    | Player 2  | 0.040     |
| hw_066                                                 | Player 3    | Player 2  | 0.024     |
| hw_071                                                 | Player 3    | Player 2  | 0.464     |
| terminal_cal_P1/ait_P1_001                             | Player 1    | Player 3  | 0.424     |
| terminal_cal_P1/ait_P1_002                             | Player 1    | Player 3  | 0.569     |
| terminal_cal_P1/ait_P1_003                             | Player 1    | Player 3  | 0.584     |
| terminal_cal_P1/ait_P1_004                             | Player 1    | Player 3  | 0.556     |
| terminal_cal_P1/ait_P1_005                             | Player 1    | Player 3  | 0.547     |
| terminal_cal_P1/ait_P1_006                             | Player 1    | Player 3  | 0.516     |
| terminal_cal_P1/ait_P1_007                             | Player 1    | Player 3  | 0.473     |
| terminal_cal_P1/ait_P1_008                             | Player 1    | Player 3  | 0.506     |
| terminal_cal_P1/ait_P1_009                             | Player 1    | Player 3  | 0.675     |
| terminal_cal_P1/ait_P1_010                             | Player 1    | Player 3  | 0.707     |
| terminal_cal_P1/ait_P1_011                             | Player 1    | Player 3  | 0.678     |
| terminal_cal_P1/ait_P1_012                             | Player 1    | Player 3  | 0.647     |
| terminal_cal_P1/ait_P1_013                             | Player 1    | Player 3  | 0.692     |
| terminal_cal_P1/button_sequence_20260326T235727Z       | Player 1    | Player 2  | 3.054     |
| terminal_cal_P1/hpsp_P1_001                            | Player 1    | Player 3  | 0.455     |
| terminal_cal_P1/hpsp_P1_002                            | Player 1    | Player 3  | 0.197     |
| terminal_cal_P1/hpsp_P1_003                            | Player 1    | Player 3  | 0.309     |
| terminal_cal_P1/mixed_biometric_probe_20260406T020720Z | Player 1    | Player 2  | 0.520     |
| terminal_cal_P1/mixed_biometric_probe_20260406T021445Z | Player 1    | Player 3  | 0.389     |
| terminal_cal_P1/mixed_biometric_probe_20260407T225745Z | Player 1    | Player 3  | 0.521     |
| terminal_cal_P1/mixed_biometric_probe_20260408T235921Z | Player 1    | Player 2  | 0.687     |
| terminal_cal_P1/mixed_biometric_probe_20260411T002724Z | Player 1    | Player 2  | 0.150     |
| terminal_cal_P1/mixed_biometric_probe_20260411T003202Z | Player 1    | Player 2  | 0.486     |
| terminal_cal_P1/mixed_biometric_probe_20260411T003442Z | Player 1    | Player 3  | 0.025     |
| terminal_cal_P1/mixed_biometric_probe_20260411T003739Z | Player 1    | Player 2  | 1.192     |
| terminal_cal_P1/mixed_biometric_probe_20260411T023325Z | Player 1    | Player 2  | 0.564     |
| terminal_cal_P1/mixed_biometric_probe_20260411T023630Z | Player 1    | Player 2  | 1.491     |
| terminal_cal_P1/mixed_biometric_probe_20260411T024710Z | Player 1    | Player 2  | 3.843     |
| terminal_cal_P1/mixed_biometric_probe_20260411T024938Z | Player 1    | Player 3  | 0.137     |
| terminal_cal_P1/mixed_biometric_probe_20260411T034635Z | Player 1    | Player 2  | 1.386     |
| terminal_cal_P1/mixed_biometric_probe_20260411T034955Z | Player 1    | Player 2  | 2.736     |
| terminal_cal_P1/natural_grip_20260326T234127Z          | Player 1    | Player 3  | 0.107     |
| terminal_cal_P1/resting_baseline_20260326T233432Z      | Player 1    | Player 3  | 0.757     |
| terminal_cal_P1/spectral_accel_20260327T011014Z        | Player 1    | Player 3  | 0.672     |
| terminal_cal_P1/stick_sweeps_20260327T000958Z          | Player 1    | Player 3  | 0.379     |
| terminal_cal_P1/touchpad_corners_20260327T031241Z      | Player 1    | Player 3  | 0.715     |
| terminal_cal_P1/touchpad_corners_20260327T230404Z      | Player 1    | Player 3  | 0.038     |
| terminal_cal_P1/touchpad_corners_20260328T142201Z      | Player 1    | Player 3  | 0.587     |
| terminal_cal_P1/touchpad_corners_20260404T183706Z      | Player 1    | Player 3  | 0.223     |
| terminal_cal_P1/touchpad_corners_20260405T031958Z      | Player 1    | Player 3  | 0.410     |
| terminal_cal_P1/touchpad_corners_20260405T210157Z      | Player 1    | Player 2  | 0.077     |
| terminal_cal_P1/touchpad_corners_20260411T053255Z      | Player 1    | Player 3  | 0.264     |
| terminal_cal_P1/touchpad_corners_20260411T054009Z      | Player 1    | Player 3  | 0.273     |
| terminal_cal_P1/touchpad_corners_20260411T201020Z      | Player 1    | Player 2  | 0.924     |
| terminal_cal_P1/touchpad_corners_20260411T201619Z      | Player 1    | Player 2  | 0.346     |
| terminal_cal_P1/touchpad_corners_20260411T220326Z      | Player 1    | Player 3  | 0.071     |
| terminal_cal_P1/touchpad_freeform_20260327T030955Z     | Player 1    | Player 3  | 0.561     |
| terminal_cal_P1/touchpad_freeform_20260327T230136Z     | Player 1    | Player 2  | 0.729     |
| terminal_cal_P1/touchpad_freeform_20260328T141850Z     | Player 1    | Player 3  | 0.178     |
| terminal_cal_P1/touchpad_freeform_20260404T183437Z     | Player 1    | Player 3  | 0.042     |
| terminal_cal_P1/touchpad_freeform_20260405T031703Z     | Player 1    | Player 3  | 0.033     |
| terminal_cal_P1/touchpad_freeform_20260405T205237Z     | Player 1    | Player 2  | 0.137     |
| terminal_cal_P1/touchpad_freeform_20260411T053010Z     | Player 1    | Player 3  | 0.023     |
| terminal_cal_P1/touchpad_freeform_20260411T053800Z     | Player 1    | Player 2  | 0.333     |
| terminal_cal_P1/touchpad_freeform_20260411T200813Z     | Player 1    | Player 2  | 1.163     |
| terminal_cal_P1/touchpad_freeform_20260411T201414Z     | Player 1    | Player 2  | 1.717     |
| terminal_cal_P1/touchpad_freeform_20260411T215344Z     | Player 1    | Player 2  | 1.184     |
| terminal_cal_P1/touchpad_freeform_20260411T220036Z     | Player 1    | Player 2  | 0.450     |
| terminal_cal_P1/touchpad_swipes_20260327T030742Z       | Player 1    | Player 3  | 0.366     |
| terminal_cal_P1/touchpad_swipes_20260327T225535Z       | Player 1    | Player 2  | 0.286     |
| terminal_cal_P1/touchpad_swipes_20260328T141624Z       | Player 1    | Player 2  | 0.177     |
| terminal_cal_P1/touchpad_swipes_20260404T183208Z       | Player 1    | Player 3  | 0.025     |
| terminal_cal_P1/touchpad_swipes_20260405T031009Z       | Player 1    | Player 3  | 0.286     |
| terminal_cal_P1/touchpad_swipes_20260405T031430Z       | Player 1    | Player 3  | 0.354     |
| terminal_cal_P1/touchpad_swipes_20260405T204508Z       | Player 1    | Player 2  | 0.100     |
| terminal_cal_P1/touchpad_swipes_20260411T052538Z       | Player 1    | Player 3  | 0.177     |
| terminal_cal_P1/touchpad_swipes_20260411T053540Z       | Player 1    | Player 3  | 0.118     |
| terminal_cal_P1/touchpad_swipes_20260411T200605Z       | Player 1    | Player 2  | 0.333     |
| terminal_cal_P1/touchpad_swipes_20260411T201207Z       | Player 1    | Player 2  | 0.459     |
| terminal_cal_P1/touchpad_swipes_20260411T214920Z       | Player 1    | Player 2  | 0.459     |
| terminal_cal_P1/touchpad_swipes_20260411T215749Z       | Player 1    | Player 2  | 0.060     |
| terminal_cal_P1/tremor_resting_P1_001                  | Player 1    | Player 3  | 0.647     |
| terminal_cal_P1/tremor_resting_P1_002                  | Player 1    | Player 3  | 0.673     |
| terminal_cal_P1/tremor_resting_P1_003                  | Player 1    | Player 3  | 0.661     |
| terminal_cal_P1/tremor_resting_P1_004                  | Player 1    | Player 3  | 0.698     |
| terminal_cal_P1/tremor_resting_P1_005                  | Player 1    | Player 3  | 0.465     |
| terminal_cal_P1/tremor_resting_P1_006                  | Player 1    | Player 3  | 0.771     |
| terminal_cal_P1/tremor_resting_P1_007                  | Player 1    | Player 3  | 0.584     |
| terminal_cal_P1/tremor_resting_P1_008                  | Player 1    | Player 3  | 0.626     |
| terminal_cal_P1/tremor_resting_P1_009                  | Player 1    | Player 3  | 0.625     |
| terminal_cal_P1/tremor_resting_P1_010                  | Player 1    | Player 3  | 0.759     |
| terminal_cal_P1/tremor_resting_P1_011                  | Player 1    | Player 3  | 0.768     |
| terminal_cal_P1/tremor_resting_P1_012                  | Player 1    | Player 3  | 0.769     |
| terminal_cal_P1/tremor_resting_P1_013                  | Player 1    | Player 3  | 0.771     |
| terminal_cal_P1/tremor_resting_P1_014                  | Player 1    | Player 3  | 0.403     |
| terminal_cal_P1/tremor_seed_20260405T002729Z           | Player 1    | Player 3  | 0.705     |
| terminal_cal_P1/tremor_seed_20260405T031320Z           | Player 1    | Player 3  | 0.566     |
| terminal_cal_P1/tremor_seed_20260405T204429Z           | Player 1    | Player 3  | 0.643     |
| terminal_cal_P1/tremor_seed_20260411T052353Z           | Player 1    | Player 3  | 0.675     |
| terminal_cal_P1/tremor_seed_20260411T053508Z           | Player 1    | Player 3  | 0.547     |
| terminal_cal_P1/tremor_seed_20260411T193750Z           | Player 1    | Player 3  | 0.599     |
| terminal_cal_P1/tremor_seed_20260411T200530Z           | Player 1    | Player 3  | 0.544     |
| terminal_cal_P1/tremor_seed_20260411T201135Z           | Player 1    | Player 3  | 0.455     |
| terminal_cal_P1/tremor_seed_20260411T214848Z           | Player 1    | Player 3  | 0.419     |
| terminal_cal_P1/tremor_seed_20260411T215716Z           | Player 1    | Player 3  | 0.421     |
| terminal_cal_P1/tremor_seed_20260418T170749Z           | Player 1    | Player 3  | 0.307     |
| terminal_cal_P1/trigger_rhythm_20260326T234937Z        | Player 1    | Player 2  | 0.565     |
| terminal_cal_P2/ait_P2_001                             | Player 2    | Player 3  | 0.381     |
| terminal_cal_P2/ait_P2_002                             | Player 2    | Player 3  | 0.598     |
| terminal_cal_P2/ait_P2_003                             | Player 2    | Player 3  | 0.537     |
| terminal_cal_P2/ait_P2_004                             | Player 2    | Player 3  | 0.600     |
| terminal_cal_P2/ait_P2_005                             | Player 2    | Player 3  | 0.559     |
| terminal_cal_P2/ait_P2_006                             | Player 2    | Player 3  | 0.675     |
| terminal_cal_P2/ait_P2_007                             | Player 2    | Player 3  | 0.653     |
| terminal_cal_P2/ait_P2_008                             | Player 2    | Player 3  | 0.654     |
| terminal_cal_P2/ait_P2_009                             | Player 2    | Player 3  | 0.685     |
| terminal_cal_P2/ait_P2_010                             | Player 2    | Player 3  | 0.675     |
| terminal_cal_P2/button_sequence_20260327T021315Z       | Player 2    | Player 3  | 0.502     |
| terminal_cal_P2/hpsp_P2_001                            | Player 2    | Player 3  | 0.502     |
| terminal_cal_P2/hpsp_P2_003                            | Player 2    | Player 3  | 0.289     |
| terminal_cal_P2/mixed_biometric_probe_20260407T224620Z | Player 2    | Player 3  | 0.188     |
| terminal_cal_P2/mixed_biometric_probe_20260409T223441Z | Player 2    | Player 1  | 9.211     |
| terminal_cal_P2/mixed_biometric_probe_20260409T223730Z | Player 2    | Player 1  | 7.024     |
| terminal_cal_P2/natural_grip_20260327T015604Z          | Player 2    | Player 3  | 0.617     |
| terminal_cal_P2/natural_grip_20260329T032252Z          | Player 2    | Player 3  | 0.542     |
| terminal_cal_P2/resting_baseline_20260327T015045Z      | Player 2    | Player 3  | 0.713     |
| terminal_cal_P2/resting_baseline_20260329T031701Z      | Player 2    | Player 3  | 0.763     |
| terminal_cal_P2/spectral_accel_20260327T022944Z        | Player 2    | Player 3  | 0.706     |
| terminal_cal_P2/stick_sweeps_20260327T022131Z          | Player 2    | Player 3  | 0.648     |
| terminal_cal_P2/touchpad_corners_20260329T010156Z      | Player 2    | Player 1  | 0.025     |
| terminal_cal_P2/touchpad_corners_20260329T203046Z      | Player 2    | Player 3  | 0.246     |
| terminal_cal_P2/touchpad_corners_20260405T033521Z      | Player 2    | Player 3  | 0.410     |
| terminal_cal_P2/touchpad_corners_20260411T141707Z      | Player 2    | Player 3  | 0.025     |
| terminal_cal_P2/touchpad_corners_20260411T142422Z      | Player 2    | Player 3  | 0.305     |
| terminal_cal_P2/touchpad_freeform_20260328T153604Z     | Player 2    | Player 3  | 0.277     |
| terminal_cal_P2/touchpad_freeform_20260404T191308Z     | Player 2    | Player 3  | 0.697     |
| terminal_cal_P2/touchpad_freeform_20260411T143855Z     | Player 2    | Player 3  | 0.036     |
| terminal_cal_P2/touchpad_swipes_20260328T153354Z       | Player 2    | Player 3  | 0.059     |
| terminal_cal_P2/touchpad_swipes_20260329T005021Z       | Player 2    | Player 3  | 0.749     |
| terminal_cal_P2/touchpad_swipes_20260405T032414Z       | Player 2    | Player 3  | 0.055     |
| terminal_cal_P2/touchpad_swipes_20260405T033016Z       | Player 2    | Player 3  | 0.108     |
| terminal_cal_P2/touchpad_swipes_20260411T141222Z       | Player 2    | Player 3  | 0.026     |
| terminal_cal_P2/touchpad_swipes_20260411T141927Z       | Player 2    | Player 1  | 0.033     |
| terminal_cal_P2/tremor_resting_P2_001                  | Player 2    | Player 1  | 2.251     |
| terminal_cal_P2/tremor_resting_P2_002                  | Player 2    | Player 3  | 0.383     |
| terminal_cal_P2/tremor_resting_P2_003                  | Player 2    | Player 3  | 0.384     |
| terminal_cal_P2/tremor_resting_P2_004                  | Player 2    | Player 3  | 0.568     |
| terminal_cal_P2/tremor_resting_P2_005                  | Player 2    | Player 3  | 0.771     |
| terminal_cal_P2/tremor_resting_P2_006                  | Player 2    | Player 3  | 0.770     |
| terminal_cal_P2/tremor_resting_P2_007                  | Player 2    | Player 3  | 0.687     |
| terminal_cal_P2/tremor_resting_P2_008                  | Player 2    | Player 3  | 0.707     |
| terminal_cal_P2/tremor_resting_P2_009                  | Player 2    | Player 3  | 0.717     |
| terminal_cal_P2/tremor_resting_P2_010                  | Player 2    | Player 3  | 0.709     |
| terminal_cal_P2/tremor_resting_P2_011                  | Player 2    | Player 3  | 0.726     |
| terminal_cal_P2/tremor_resting_P2_012                  | Player 2    | Player 3  | 0.767     |
| terminal_cal_P2/tremor_resting_P2_013                  | Player 2    | Player 3  | 0.750     |
| terminal_cal_P2/tremor_resting_P2_014                  | Player 2    | Player 3  | 0.762     |
| terminal_cal_P2/tremor_seed_20260405T032335Z           | Player 2    | Player 3  | 0.683     |
| terminal_cal_P2/tremor_seed_20260405T032940Z           | Player 2    | Player 3  | 0.621     |
| terminal_cal_P2/tremor_seed_20260405T204530Z           | Player 2    | Player 3  | 0.618     |
| terminal_cal_P2/tremor_seed_20260411T141846Z           | Player 2    | Player 3  | 0.372     |
| terminal_cal_P2/tremor_seed_20260411T143454Z           | Player 2    | Player 3  | 0.582     |
| terminal_cal_P2/tremor_seed_20260411T164059Z           | Player 2    | Player 3  | 0.433     |
| terminal_cal_P2/tremor_seed_20260411T210448Z           | Player 2    | Player 3  | 0.392     |
| terminal_cal_P2/trigger_rhythm_20260327T020442Z        | Player 2    | Player 3  | 0.164     |
| terminal_cal_P3/hpsp_P3_002                            | Player 3    | Player 2  | 0.955     |
| terminal_cal_P3/mixed_biometric_probe_20260406T022141Z | Player 3    | Player 2  | 0.561     |
| terminal_cal_P3/mixed_biometric_probe_20260409T224016Z | Player 3    | Player 2  | 4.994     |
| terminal_cal_P3/mixed_biometric_probe_20260409T224305Z | Player 3    | Player 2  | 1.990     |
| terminal_cal_P3/touchpad_corners_20260405T203336Z      | Player 3    | Player 2  | 0.426     |
| terminal_cal_P3/touchpad_corners_20260405T210733Z      | Player 3    | Player 2  | 1.184     |
| terminal_cal_P3/touchpad_corners_20260411T143221Z      | Player 3    | Player 2  | 0.592     |
| terminal_cal_P3/touchpad_corners_20260411T144915Z      | Player 3    | Player 2  | 1.134     |
| terminal_cal_P3/touchpad_corners_20260411T165518Z      | Player 3    | Player 2  | 1.502     |
| terminal_cal_P3/touchpad_corners_20260411T210250Z      | Player 3    | Player 2  | 0.853     |
| terminal_cal_P3/touchpad_freeform_20260327T231922Z     | Player 3    | Player 2  | 0.631     |
| terminal_cal_P3/touchpad_freeform_20260328T160809Z     | Player 3    | Player 2  | 0.303     |
| terminal_cal_P3/touchpad_freeform_20260329T032705Z     | Player 3    | Player 2  | 0.445     |
| terminal_cal_P3/touchpad_freeform_20260329T215205Z     | Player 3    | Player 2  | 0.823     |
| terminal_cal_P3/touchpad_freeform_20260405T203100Z     | Player 3    | Player 2  | 0.715     |
| terminal_cal_P3/touchpad_freeform_20260405T205753Z     | Player 3    | Player 2  | 0.649     |
| terminal_cal_P3/touchpad_freeform_20260411T142956Z     | Player 3    | Player 2  | 2.274     |
| terminal_cal_P3/touchpad_freeform_20260411T144705Z     | Player 3    | Player 2  | 0.936     |
| terminal_cal_P3/touchpad_freeform_20260411T165253Z     | Player 3    | Player 2  | 1.405     |
| terminal_cal_P3/touchpad_freeform_20260411T210041Z     | Player 3    | Player 2  | 0.211     |
| terminal_cal_P3/touchpad_swipes_20260405T202817Z       | Player 3    | Player 2  | 0.226     |
| terminal_cal_P3/touchpad_swipes_20260405T204800Z       | Player 3    | Player 2  | 0.281     |
| terminal_cal_P3/touchpad_swipes_20260411T142705Z       | Player 3    | Player 2  | 1.090     |
| terminal_cal_P3/touchpad_swipes_20260411T144345Z       | Player 3    | Player 2  | 0.189     |
| terminal_cal_P3/touchpad_swipes_20260411T164808Z       | Player 3    | Player 2  | 0.048     |
| terminal_cal_P3/touchpad_swipes_20260411T205834Z       | Player 3    | Player 2  | 0.588     |
| terminal_cal_P3/trigger_rhythm_20260328T013207Z        | Player 3    | Player 2  | 1.057     |

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

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.08 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=110 sessions/player average is adequate.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*