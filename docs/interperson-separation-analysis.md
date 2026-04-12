# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 242 included, 5 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (11 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.616 |
| Mean inter-player distance | 0.028 |
| **Separation ratio (inter/intra)** | **0.045** |
| Leave-one-out classification accuracy | 31.8% (77/242) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.04). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 105      | 0.569      | 0.593     | 0.048     | 3.467     | 0.391        |
| Player 2 | 73       | 0.645      | 1.185     | 0.037     | 8.405     | 0.386        |
| Player 3 | 64       | 0.635      | 0.626     | 0.036     | 4.495     | 0.521        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.036    | 0.027    |
| Player 2 | 0.036    | —        | 0.020    |
| Player 3 | 0.027    | 0.020    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=105 sessions, mean=0.569):
  0.945, 0.201, 0.087, 2.664, 0.090, 0.084, 0.844, 0.124, 0.170, 0.084, 0.149, 0.073, 0.138, 0.048, 0.184, 0.170, 0.892, 0.832, 0.309, 0.104, 0.877, 0.136, 0.159, 0.077, 0.452, 0.115, 0.506, 0.131, 1.127, 0.075, 0.139, 0.650, 0.074, 0.840, 0.184, 0.294, 0.335, 0.082, 2.700, 0.338, 0.760, 0.716, 0.492, 0.105, 0.297, 0.249, 0.957, 0.374, 1.240, 3.467, 0.360, 1.137, 2.400, 0.330, 0.935, 0.854, 0.584, 0.896, 0.217, 0.776, 0.439, 1.097, 0.115, 0.474, 0.486, 0.705, 0.179, 0.195, 0.300, 0.751, 0.531, 0.391, 0.253, 0.430, 0.084, 1.273, 0.152, 0.935, 1.451, 0.950, 0.276, 0.572, 0.135, 0.078, 0.253, 0.498, 0.561, 0.067, 0.397, 2.400, 0.173, 0.284, 0.272, 0.127, 0.887, 0.758, 0.829, 0.859, 0.740, 0.788, 0.737, 0.654, 0.621, 0.623, 0.380

**Player 2** (N=73 sessions, mean=0.645):
  0.474, 0.181, 0.390, 0.814, 0.100, 0.653, 0.147, 1.174, 0.341, 0.097, 0.207, 0.426, 0.068, 0.060, 0.741, 0.836, 0.633, 8.405, 6.355, 0.081, 0.976, 0.837, 0.768, 0.927, 0.975, 1.251, 0.870, 0.067, 0.076, 0.218, 0.493, 0.076, 0.645, 0.386, 0.255, 0.548, 0.070, 0.340, 0.321, 0.037, 0.518, 0.321, 0.073, 0.910, 0.124, 0.712, 0.484, 0.140, 0.254, 0.440, 0.263, 0.848, 0.314, 0.961, 0.369, 0.182, 0.305, 0.365, 0.087, 0.248, 0.241, 0.133, 0.111, 0.336, 0.900, 0.842, 0.839, 0.288, 0.610, 0.806, 0.667, 0.628, 0.413

**Player 3** (N=64 sessions, mean=0.635):
  1.268, 0.069, 0.087, 0.091, 0.278, 0.129, 0.144, 0.165, 0.404, 0.267, 0.266, 0.473, 0.958, 0.824, 0.728, 4.495, 1.850, 0.539, 0.500, 0.963, 0.963, 0.483, 0.753, 0.502, 0.915, 0.617, 0.369, 0.229, 0.223, 0.931, 0.384, 0.889, 1.228, 0.623, 0.420, 0.123, 0.250, 0.598, 0.761, 0.499, 0.435, 1.953, 0.704, 1.142, 0.036, 0.667, 0.236, 0.657, 0.613, 0.372, 0.068, 0.105, 0.848, 0.051, 0.144, 0.377, 0.754, 0.856, 0.392, 0.851, 0.760, 0.720, 0.800, 0.815

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                  | Player 3                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------- | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 8419.0796 (+/-6714.8774) | 8716.6887 (+/-11736.2440) | 8563.3221 (+/-7654.2505) | 297.6092    |
| tremor_peak_hz                   | 6.9568 (+/-27.1399)      | 5.9772 (+/-16.2995)       | 5.0886 (+/-16.3905)      | 1.8682      |
| touchpad_spatial_entropy         | 0.6981 (+/-0.9248)       | 0.9314 (+/-1.0977)        | 1.0082 (+/-1.1744)       | 0.3102      |
| accel_magnitude_spectral_entropy | 4.4971 (+/-0.6323)       | 4.4616 (+/-0.8536)        | 4.3683 (+/-0.9111)       | 0.1288      |
| stick_autocorr_lag1              | 0.0667 (+/-0.0787)       | 0.0349 (+/-0.0621)        | 0.0288 (+/-0.0552)       | 0.0379      |
| stick_autocorr_lag5              | 0.0602 (+/-0.0717)       | 0.0313 (+/-0.0552)        | 0.0254 (+/-0.0486)       | 0.0347      |
| grip_asymmetry                   | 1.0250 (+/-0.1032)       | 1.0169 (+/-0.0753)        | 1.0364 (+/-0.1730)       | 0.0195      |
| touch_position_variance          | 0.0132 (+/-0.0163)       | 0.0135 (+/-0.0167)        | 0.0149 (+/-0.0167)       | 0.0017      |
| trigger_onset_velocity_r2        | 0.0018 (+/-0.0036)       | 0.0025 (+/-0.0148)        | 0.0009 (+/-0.0021)       | 0.0015      |
| tremor_band_power                | 0.0015 (+/-0.0027)       | 0.0011 (+/-0.0023)        | 0.0009 (+/-0.0019)       | 0.0007      |
| trigger_onset_velocity_l2        | 0.0008 (+/-0.0017)       | 0.0004 (+/-0.0011)        | 0.0005 (+/-0.0015)       | 0.0004      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)        | 0.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)        | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 31.8% (77/242 sessions correctly assigned)**

Misclassified sessions:

| Session                                                | True Player | Predicted | Best Dist |
| ------------------------------------------------------ | ----------- | --------- | --------- |
| hw_007                                                 | Player 1    | Player 3  | 0.083     |
| hw_008                                                 | Player 1    | Player 2  | 2.629     |
| hw_009                                                 | Player 1    | Player 3  | 0.064     |
| hw_010                                                 | Player 1    | Player 3  | 0.080     |
| hw_012                                                 | Player 1    | Player 2  | 0.091     |
| hw_013                                                 | Player 1    | Player 2  | 0.135     |
| hw_014                                                 | Player 1    | Player 3  | 0.059     |
| hw_015                                                 | Player 1    | Player 2  | 0.114     |
| hw_016                                                 | Player 1    | Player 2  | 0.042     |
| hw_018                                                 | Player 1    | Player 3  | 0.024     |
| hw_020                                                 | Player 1    | Player 2  | 0.135     |
| hw_022                                                 | Player 1    | Player 2  | 0.797     |
| hw_024                                                 | Player 1    | Player 2  | 0.075     |
| hw_025                                                 | Player 1    | Player 2  | 0.842     |
| hw_026                                                 | Player 1    | Player 2  | 0.102     |
| hw_028                                                 | Player 1    | Player 3  | 0.067     |
| hw_030                                                 | Player 1    | Player 2  | 0.081     |
| hw_032                                                 | Player 1    | Player 2  | 0.097     |
| hw_033                                                 | Player 1    | Player 2  | 1.092     |
| hw_034                                                 | Player 1    | Player 3  | 0.056     |
| hw_037                                                 | Player 1    | Player 3  | 0.056     |
| hw_038                                                 | Player 1    | Player 2  | 0.805     |
| hw_042                                                 | Player 1    | Player 3  | 0.058     |
| hw_047                                                 | Player 2    | Player 1  | 0.356     |
| hw_048                                                 | Player 2    | Player 1  | 0.781     |
| hw_049                                                 | Player 2    | Player 3  | 0.081     |
| hw_050                                                 | Player 2    | Player 1  | 0.620     |
| hw_051                                                 | Player 2    | Player 1  | 0.119     |
| hw_053                                                 | Player 2    | Player 1  | 0.310     |
| hw_054                                                 | Player 2    | Player 3  | 0.078     |
| hw_055                                                 | Player 2    | Player 1  | 0.179     |
| hw_056                                                 | Player 2    | Player 1  | 0.394     |
| hw_057                                                 | Player 2    | Player 3  | 0.051     |
| hw_059                                                 | Player 3    | Player 1  | 1.242     |
| hw_060                                                 | Player 3    | Player 2  | 0.065     |
| hw_061                                                 | Player 3    | Player 2  | 0.082     |
| hw_063                                                 | Player 3    | Player 2  | 0.263     |
| hw_064                                                 | Player 3    | Player 1  | 0.125     |
| hw_065                                                 | Player 3    | Player 1  | 0.126     |
| hw_066                                                 | Player 3    | Player 1  | 0.153     |
| hw_068                                                 | Player 3    | Player 1  | 0.389     |
| hw_070                                                 | Player 3    | Player 1  | 0.255     |
| hw_071                                                 | Player 3    | Player 2  | 0.251     |
| hw_072                                                 | Player 3    | Player 1  | 0.459     |
| terminal_cal_P1/button_sequence_20260326T235727Z       | Player 1    | Player 2  | 2.666     |
| terminal_cal_P1/mixed_biometric_probe_20260406T020720Z | Player 1    | Player 2  | 0.302     |
| terminal_cal_P1/mixed_biometric_probe_20260408T235921Z | Player 1    | Player 2  | 0.457     |
| terminal_cal_P1/mixed_biometric_probe_20260411T003202Z | Player 1    | Player 2  | 0.262     |
| terminal_cal_P1/mixed_biometric_probe_20260411T003739Z | Player 1    | Player 2  | 0.924     |
| terminal_cal_P1/mixed_biometric_probe_20260411T023325Z | Player 1    | Player 2  | 0.338     |
| terminal_cal_P1/mixed_biometric_probe_20260411T023630Z | Player 1    | Player 2  | 1.205     |
| terminal_cal_P1/mixed_biometric_probe_20260411T024710Z | Player 1    | Player 2  | 3.435     |
| terminal_cal_P1/mixed_biometric_probe_20260411T034635Z | Player 1    | Player 2  | 1.103     |
| terminal_cal_P1/mixed_biometric_probe_20260411T034955Z | Player 1    | Player 2  | 2.366     |
| terminal_cal_P1/touchpad_corners_20260411T201020Z      | Player 1    | Player 2  | 0.671     |
| terminal_cal_P1/touchpad_corners_20260411T201619Z      | Player 1    | Player 2  | 0.143     |
| terminal_cal_P1/touchpad_freeform_20260327T230136Z     | Player 1    | Player 2  | 0.495     |
| terminal_cal_P1/touchpad_freeform_20260405T205237Z     | Player 1    | Player 3  | 0.074     |
| terminal_cal_P1/touchpad_freeform_20260411T053800Z     | Player 1    | Player 2  | 0.120     |
| terminal_cal_P1/touchpad_freeform_20260411T200813Z     | Player 1    | Player 2  | 0.900     |
| terminal_cal_P1/touchpad_freeform_20260411T201414Z     | Player 1    | Player 2  | 1.416     |
| terminal_cal_P1/touchpad_freeform_20260411T215344Z     | Player 1    | Player 2  | 0.915     |
| terminal_cal_P1/touchpad_freeform_20260411T220036Z     | Player 1    | Player 2  | 0.240     |
| terminal_cal_P1/touchpad_swipes_20260327T225535Z       | Player 1    | Player 2  | 0.101     |
| terminal_cal_P1/touchpad_swipes_20260328T141624Z       | Player 1    | Player 3  | 0.057     |
| terminal_cal_P1/touchpad_swipes_20260411T053540Z       | Player 1    | Player 2  | 2.415     |
| terminal_cal_P1/touchpad_swipes_20260411T200605Z       | Player 1    | Player 2  | 0.138     |
| terminal_cal_P1/touchpad_swipes_20260411T201207Z       | Player 1    | Player 2  | 0.248     |
| terminal_cal_P1/touchpad_swipes_20260411T214920Z       | Player 1    | Player 2  | 0.236     |
| terminal_cal_P1/trigger_rhythm_20260326T234937Z        | Player 1    | Player 2  | 0.344     |
| terminal_cal_P2/button_sequence_20260327T021315Z       | Player 2    | Player 1  | 0.705     |
| terminal_cal_P2/mixed_biometric_probe_20260406T021844Z | Player 2    | Player 1  | 0.835     |
| terminal_cal_P2/mixed_biometric_probe_20260407T224620Z | Player 2    | Player 1  | 0.602     |
| terminal_cal_P2/mixed_biometric_probe_20260409T223441Z | Player 2    | Player 3  | 8.423     |
| terminal_cal_P2/mixed_biometric_probe_20260409T223730Z | Player 2    | Player 3  | 6.373     |
| terminal_cal_P2/natural_grip_20260327T015604Z          | Player 2    | Player 1  | 0.804     |
| terminal_cal_P2/natural_grip_20260329T032252Z          | Player 2    | Player 1  | 0.735     |
| terminal_cal_P2/resting_baseline_20260327T015045Z      | Player 2    | Player 1  | 0.894     |
| terminal_cal_P2/resting_baseline_20260329T031701Z      | Player 2    | Player 1  | 0.941     |
| terminal_cal_P2/spectral_accel_20260327T022944Z        | Player 2    | Player 1  | 1.218     |
| terminal_cal_P2/stick_sweeps_20260327T022131Z          | Player 2    | Player 1  | 0.836     |
| terminal_cal_P2/touchpad_corners_20260328T003556Z      | Player 2    | Player 3  | 0.063     |
| terminal_cal_P2/touchpad_corners_20260328T153820Z      | Player 2    | Player 3  | 0.060     |
| terminal_cal_P2/touchpad_corners_20260329T010156Z      | Player 2    | Player 1  | 0.190     |
| terminal_cal_P2/touchpad_corners_20260329T203046Z      | Player 2    | Player 1  | 0.461     |
| terminal_cal_P2/touchpad_corners_20260405T033521Z      | Player 2    | Player 1  | 0.612     |
| terminal_cal_P2/touchpad_corners_20260411T141707Z      | Player 2    | Player 1  | 0.226     |
| terminal_cal_P2/touchpad_corners_20260411T142422Z      | Player 2    | Player 1  | 0.515     |
| terminal_cal_P2/touchpad_corners_20260411T144124Z      | Player 2    | Player 3  | 0.057     |
| terminal_cal_P2/touchpad_freeform_20260328T003347Z     | Player 2    | Player 3  | 0.027     |
| terminal_cal_P2/touchpad_freeform_20260328T153604Z     | Player 2    | Player 1  | 0.485     |
| terminal_cal_P2/touchpad_freeform_20260329T202820Z     | Player 2    | Player 3  | 0.060     |
| terminal_cal_P2/touchpad_freeform_20260404T191308Z     | Player 2    | Player 1  | 0.877     |
| terminal_cal_P2/touchpad_freeform_20260405T033248Z     | Player 2    | Player 3  | 0.105     |
| terminal_cal_P2/touchpad_freeform_20260411T141440Z     | Player 2    | Player 1  | 0.465     |
| terminal_cal_P2/touchpad_freeform_20260411T142155Z     | Player 2    | Player 1  | 0.119     |
| terminal_cal_P2/touchpad_freeform_20260411T143855Z     | Player 2    | Player 1  | 0.225     |
| terminal_cal_P2/touchpad_swipes_20260328T153354Z       | Player 2    | Player 1  | 0.284     |
| terminal_cal_P2/touchpad_swipes_20260329T005021Z       | Player 2    | Player 1  | 0.928     |
| terminal_cal_P2/touchpad_swipes_20260404T190950Z       | Player 2    | Player 1  | 0.156     |
| terminal_cal_P2/touchpad_swipes_20260405T032414Z       | Player 2    | Player 1  | 0.274     |
| terminal_cal_P2/touchpad_swipes_20260405T033016Z       | Player 2    | Player 1  | 0.334     |
| terminal_cal_P2/touchpad_swipes_20260405T204608Z       | Player 2    | Player 1  | 0.059     |
| terminal_cal_P2/touchpad_swipes_20260411T141222Z       | Player 2    | Player 1  | 0.216     |
| terminal_cal_P2/touchpad_swipes_20260411T141927Z       | Player 2    | Player 1  | 0.212     |
| terminal_cal_P2/touchpad_swipes_20260411T143628Z       | Player 2    | Player 1  | 0.112     |
| terminal_cal_P2/touchpad_swipes_20260411T164137Z       | Player 2    | Player 1  | 0.077     |
| terminal_cal_P2/tremor_seed_20260405T032335Z           | Player 2    | Player 1  | 0.866     |
| terminal_cal_P2/tremor_seed_20260405T032940Z           | Player 2    | Player 1  | 0.809     |
| terminal_cal_P2/tremor_seed_20260405T204530Z           | Player 2    | Player 1  | 0.806     |
| terminal_cal_P2/tremor_seed_20260411T141846Z           | Player 2    | Player 1  | 0.578     |
| terminal_cal_P2/tremor_seed_20260411T143454Z           | Player 2    | Player 1  | 0.773     |
| terminal_cal_P2/tremor_seed_20260411T164059Z           | Player 2    | Player 1  | 0.634     |
| terminal_cal_P2/tremor_seed_20260411T210448Z           | Player 2    | Player 1  | 0.596     |
| terminal_cal_P2/trigger_rhythm_20260327T020442Z        | Player 2    | Player 1  | 0.379     |
| terminal_cal_P3/button_sequence_20260328T014042Z       | Player 3    | Player 1  | 0.942     |
| terminal_cal_P3/mixed_biometric_probe_20260406T022141Z | Player 3    | Player 2  | 0.809     |
| terminal_cal_P3/mixed_biometric_probe_20260407T225423Z | Player 3    | Player 1  | 0.713     |
| terminal_cal_P3/mixed_biometric_probe_20260409T224016Z | Player 3    | Player 2  | 4.478     |
| terminal_cal_P3/mixed_biometric_probe_20260409T224305Z | Player 3    | Player 2  | 1.830     |
| terminal_cal_P3/natural_grip_20260328T005708Z          | Player 3    | Player 1  | 0.524     |
| terminal_cal_P3/natural_grip_20260328T012401Z          | Player 3    | Player 1  | 0.482     |
| terminal_cal_P3/resting_baseline_20260328T003917Z      | Player 3    | Player 1  | 0.947     |
| terminal_cal_P3/resting_baseline_20260328T011813Z      | Player 3    | Player 1  | 0.948     |
| terminal_cal_P3/spectral_accel_20260328T015847Z        | Player 3    | Player 1  | 0.469     |
| terminal_cal_P3/stick_sweeps_20260328T014814Z          | Player 3    | Player 1  | 0.735     |
| terminal_cal_P3/touchpad_corners_20260327T232204Z      | Player 3    | Player 1  | 0.488     |
| terminal_cal_P3/touchpad_corners_20260328T161059Z      | Player 3    | Player 1  | 0.899     |
| terminal_cal_P3/touchpad_corners_20260329T032924Z      | Player 3    | Player 1  | 0.602     |
| terminal_cal_P3/touchpad_corners_20260329T215413Z      | Player 3    | Player 1  | 0.356     |
| terminal_cal_P3/touchpad_corners_20260404T203748Z      | Player 3    | Player 1  | 0.219     |
| terminal_cal_P3/touchpad_corners_20260405T203336Z      | Player 3    | Player 2  | 0.205     |
| terminal_cal_P3/touchpad_corners_20260405T210733Z      | Player 3    | Player 2  | 0.913     |
| terminal_cal_P3/touchpad_corners_20260411T143221Z      | Player 3    | Player 2  | 0.369     |
| terminal_cal_P3/touchpad_corners_20260411T144915Z      | Player 3    | Player 2  | 0.872     |
| terminal_cal_P3/touchpad_corners_20260411T165518Z      | Player 3    | Player 2  | 1.211     |
| terminal_cal_P3/touchpad_corners_20260411T210250Z      | Player 3    | Player 2  | 0.605     |
| terminal_cal_P3/touchpad_freeform_20260327T231922Z     | Player 3    | Player 2  | 0.404     |
| terminal_cal_P3/touchpad_freeform_20260328T160809Z     | Player 3    | Player 2  | 0.114     |
| terminal_cal_P3/touchpad_freeform_20260329T032705Z     | Player 3    | Player 2  | 0.236     |
| terminal_cal_P3/touchpad_freeform_20260329T215205Z     | Player 3    | Player 2  | 0.582     |
| terminal_cal_P3/touchpad_freeform_20260404T203515Z     | Player 3    | Player 1  | 0.746     |
| terminal_cal_P3/touchpad_freeform_20260405T203100Z     | Player 3    | Player 2  | 0.483     |
| terminal_cal_P3/touchpad_freeform_20260405T205753Z     | Player 3    | Player 2  | 0.416     |
| terminal_cal_P3/touchpad_freeform_20260411T142956Z     | Player 3    | Player 2  | 1.936     |
| terminal_cal_P3/touchpad_freeform_20260411T144705Z     | Player 3    | Player 2  | 0.688     |
| terminal_cal_P3/touchpad_freeform_20260411T165253Z     | Player 3    | Player 2  | 1.125     |
| terminal_cal_P3/touchpad_freeform_20260411T210041Z     | Player 3    | Player 2  | 0.036     |
| terminal_cal_P3/touchpad_swipes_20260327T231705Z       | Player 3    | Player 1  | 0.653     |
| terminal_cal_P3/touchpad_swipes_20260328T160459Z       | Player 3    | Player 1  | 0.225     |
| terminal_cal_P3/touchpad_swipes_20260329T032458Z       | Player 3    | Player 1  | 0.642     |
| terminal_cal_P3/touchpad_swipes_20260329T214956Z       | Player 3    | Player 1  | 0.598     |
| terminal_cal_P3/touchpad_swipes_20260404T203239Z       | Player 3    | Player 1  | 0.359     |
| terminal_cal_P3/touchpad_swipes_20260405T204800Z       | Player 3    | Player 2  | 0.097     |
| terminal_cal_P3/touchpad_swipes_20260411T142705Z       | Player 3    | Player 2  | 0.831     |
| terminal_cal_P3/touchpad_swipes_20260411T164808Z       | Player 3    | Player 1  | 0.139     |
| terminal_cal_P3/touchpad_swipes_20260411T205834Z       | Player 3    | Player 2  | 0.358     |
| terminal_cal_P3/tremor_seed_20260405T202721Z           | Player 3    | Player 1  | 0.739     |
| terminal_cal_P3/tremor_seed_20260405T204725Z           | Player 3    | Player 1  | 0.840     |
| terminal_cal_P3/tremor_seed_20260411T142608Z           | Player 3    | Player 1  | 0.379     |
| terminal_cal_P3/tremor_seed_20260411T144306Z           | Player 3    | Player 1  | 0.836     |
| terminal_cal_P3/tremor_seed_20260411T164734Z           | Player 3    | Player 1  | 0.744     |
| terminal_cal_P3/tremor_seed_20260411T205801Z           | Player 3    | Player 1  | 0.705     |
| terminal_cal_P3/trigger_rhythm_20260328T011017Z        | Player 3    | Player 1  | 0.785     |
| terminal_cal_P3/trigger_rhythm_20260328T013207Z        | Player 3    | Player 2  | 0.798     |

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

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.04 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=81 sessions/player average is adequate.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*