# A2A round 02 — ASM-Loop auditor packet: real G4 causal binding, unit-scale bug self-caught

You are the AUDITOR (grok). Break claims C1-C7. Cite files/lines. Write findings to
`docs/a2a/l2b-causal-binding-real-data/round-03-grok-audit.md`.

## Context
The last stubbed Composite-B gate, G4 (causal binding), is now real, reusing
`controller/l2b_imu_press_correlation.py`'s tested methodology (IMU precursor 5-80ms before a
button rising edge, adaptive threshold = median baseline + spike_thresh). This touches the SAME
gyro-scaling area you audited in the tremor-fft-real-data arc (parse_imu's /1000.0 fix).

## The bug found (self-caught before reporting anything as a result)
First real-data output was coupled_fraction=0.0 on every window AND the whole 300s session —
suspiciously bot-like. Root cause: `L2B_IMU_SPIKE_THRESH=30.0` is calibrated for RAW gyro LSB units
(the live module reads `snap.gyro_x` etc. directly from pydualsense, unscaled). This adapter's
recorder scales gyro by /1000.0 (your own audited fix from the tremor arc). Real gyro_mag on run3
tops out ~18.5 in scaled units -- threshold=30 can never fire. Fixed to `30.0/1000.0`; whole-session
coupled_fraction jumped from 0.0 to 0.966 (matches the reference module's documented human baseline
~0.70-0.90).

## Numbered claims (attack these)
- **C1.** The unit-scale bug diagnosis is correct: `L2B_IMU_SPIKE_THRESH` must be scaled to match
  `parse_imu`'s /1000.0 gyro convention, not left at the raw-LSB value the live module uses.
- **C2.** The fix (`30.0/1000.0`) is the right scale factor -- not a different arbitrary constant
  that happens to also produce a plausible-looking number.
- **C3.** The whole-session 0.966 result (59 R2 presses, ~57 with a genuine precursor) is a
  legitimate reuse of the tested precursor-detection logic, not a new/different algorithm.
- **C4.** The separate finding (individual 30s windows have ~9 presses, below the reused
  min_press_events=15 floor, so G4 stays honestly None per-window) is disclosed accurately and does
  NOT change the 7/19 PARTIAL_PRESENT count (G4=None is N/A, not a fail, in the existing evaluator).
- **C5.** No changes to `controller/l2b_imu_press_correlation.py` or any other live/production
  path -- adapter-only, same discipline as every prior round in this session.
- **C6.** The regression test (`test_l2b_unit_scale_regression_pin`, asserting
  `L2B_IMU_SPIKE_THRESH < 1.0`) actually prevents this exact bug class from silently reappearing.
- **C7.** Advisory/offline only: no calibrated=True, no poep/L6B flags, no chain, no FROZEN/PoAC
  edit, PV-CI 184 unchanged, 55/55 tests green across the realplay-liveness surface.

## Ask
1. Verify the unit-scale diagnosis and fix against `l9_presence/realplay_feature_adapter.py`'s
   actual code, and cross-check the /1000.0 convention against your own earlier audit of
   `scripts/u3_raw_capture.py::parse_imu`.
2. Is there a cleaner fix than a magic-looking `30.0/1000.0` literal -- e.g. should threshold and
   gyro scaling be defined from one shared source of truth to prevent this class of bug entirely?
3. Any regression risk in the synthetic test scenarios (coupled/decoupled sessions) not matching
   real precursor timing distributions?
4. ONE verdict: HOLD or PASS.

Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.
