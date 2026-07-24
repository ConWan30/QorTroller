# A2A optical — RE-VERIFY #2: F8/F9/F10 structural + fail-closed calibration gate

You are the AUDITOR (grok). RE-VERIFY after your r04 HOLD (F8 BLOCK circular-null collapse +
F9/F10 WARN + F1 residual). Builder adopted all. Confirm close / hunt new breaks. ONE verdict
HOLD or PASS. Write `docs/a2a/optical-copresence/round-06-grok-reverify.md`.

Disposition (l9_presence/optical_copresence.py + bridge/tests/test_optical_copresence.py on disk):
- F8 BLOCK (modulus collapse on regular grid) -> FIXED: wrap period = r_span + mean_gap = n*mean_gap
  for a regular grid, so all n response points stay distinct through every phase (no first/last
  collision). Test `test_circular_null_no_point_collapse_on_regular_grid` asserts null_q<1.0 +
  coupled on a 16-point grid.
- F10 WARN (3s fixture != football) -> FIXED: all tests now use SNAP_MS=30_000 (real NCAA snap
  spacing) where a pure-phase null discriminates (true lock p~0.015). Off-phase periodic macro +
  dense mash + preceding-replay all assert event_coupled=False at this regime.
- F9 WARN (discrete lattice / strict >) + F6 (no calibrated alpha-level test) -> ADDRESSED by
  FAIL-CLOSED CALIBRATION GATE: `optical_consistent_flag(..., calibrated=False default)` returns
  False unless calibrated=True. So the uncalibrated n~8-12 lattice CANNOT flip replay_resistant/
  CONTINUOUS in production — CONTINUOUS is fail-closed-unreachable until U3 measurement validates
  thresholds. `test_flag_fail_closed_until_calibrated` + `test_end_to_end_uncalibrated_optical_caps
  _at_partial` pin this (uncalibrated -> PARTIAL; calibrated -> CONTINUOUS).
- F2/F3/F5 already CLOSED r04.

Accepted residual (measurement, like the main loop's R-HYP): thresholds (MIN_ABS_HIT_RATE,
NULL_QUANTILE, NULL_MIN_EXCESS, MIN_EVENTS) stay CANDIDATE until U3 measures NCAA snap-interval +
reaction-lag distributions; the fail-closed gate means nothing over-claims meanwhile.

Attack: is the period=r_span+mean_gap fix correct for IRREGULAR response spacing too (not just
grids)? Does the fail-closed gate actually make CONTINUOUS unreachable in production? Any NEW break.
With F8 structurally fixed + fail-closed gate + U3 residual explicitly accepted, is this a
residual-accepted PASS? Code-review only. Rails: 228B PoAC/FROZEN-v1/PV-CI 184/CHAIN_SUBMISSION_PAUSED/
single-committer=operator.
