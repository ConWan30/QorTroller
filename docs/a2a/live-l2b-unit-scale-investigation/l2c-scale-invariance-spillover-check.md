# L2C spillover check — does the L2B gyro unit-scale bug also hit L2C?

**Trigger:** grok's round-02 (`round-02-grok-expand.md`) open-question #3 explicitly
flagged this as a separate, un-conflated follow-up: *"L2C unit coupling?
`StickImuCorrelationOracle` also consumes `snap.gyro_z` live. Dead-zone games
neutralize L2C differently, but non-dead-zone profiles may carry a related scale
issue (separate investigation — do not conflate)."*

**Answer: no — L2C is architecturally immune to this specific bug class.**

## Why L2B broke

`controller/l2b_imu_press_correlation.py` fires an anomaly when a computed
`gyro_mag` (absolute magnitude, raw LSB units by design — see its own docstring)
fails to exceed a fixed **absolute** threshold, `_IMU_SPIKE_THRESH = 30.0`. Live
production (`controller/dualshock_emulator.py`) feeds gyro pre-scaled by `/1000.0`.
A raw peak of ~4000 LSB becomes ~4.0 live — never within reach of `baseline + 30`.
The threshold is an absolute-magnitude constant compared against a variable whose
unit changed out from under it.

## Why L2C does not

`controller/l2c_stick_imu_correlation.py` never compares `gyro_z` to any fixed
absolute constant. Its only statistic is `np.corrcoef(stick_velocity, gyro_z)` —
the Pearson correlation coefficient — evaluated at causal lags 10–60 frames, and
`_CORR_THRESHOLD = 0.15` is a threshold on that dimensionless coefficient, not on
`gyro_z`'s raw magnitude.

Pearson correlation is invariant to positive linear rescaling of either input:

```
corr(a, k*b) = cov(a, k*b) / (std(a) * std(k*b))
             = k*cov(a,b) / (std(a) * k*std(b))     [k > 0]
             = cov(a,b) / (std(a) * std(b))
             = corr(a, b)
```

For `k < 0` the sign of `corr` flips but `|corr|` does not — and `anomaly` is
computed on `abs(max_causal_corr)`, so a sign flip can't move the verdict either.
Whether `gyro_z` arrives as raw int16 or `/1000.0`-scaled (or any other positive
constant scale), `max_causal_corr`, `anomaly`, `classify()`, and `humanity_score()`
are all mathematically unchanged.

## Verification

This is a closed algebraic argument, not an empirical claim, so it doesn't need a
live-hardware replay to settle — but per this session's "ground first, then pin it
with a test" discipline it's now backed by 3 regression tests in
`bridge/tests/test_l2c_stick_imu_correlation.py` (`TestGyroScaleInvariance`):

1. Synthetic causally-coupled signal, raw vs `/1000.0` scale → identical
   `max_causal_corr`, `lag_at_max`, `anomaly`, `classify()`, `humanity_score()`.
2. Real `hw_005.json` session replayed at raw scale vs `/1000.0` scale (the exact
   replay methodology grok used to *confirm* the L2B bug in round-02 Ask 1, applied
   here to *refute* an analogous L2C bug) — verdict identical at both scales.
3. Sign-flipping rescale (`k < 0`) — magnitude of correlation and the
   `anomaly`/`classify()` verdict unchanged; only the stored signed
   `max_causal_corr` flips sign, as expected.

All 20 tests in the file pass (17 pre-existing + 3 new).

## Scope note

This closes the *unit-scale* question specifically. It says nothing about whether
L2C's `_CORR_THRESHOLD = 0.15` or lag window `[10, 60]` frames are well-calibrated
in general, and does not touch the already-documented dead-zone-neutral behavior
(`right_stick_x` static in NCAA CFB 26 → `_MIN_STICK_STD` guard → `None` → 0.5
neutral prior per CLAUDE.md). No production code changed. No FROZEN/PoAC/chain
surface touched.
