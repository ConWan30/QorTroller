# Step A — offline unit-path replay (grok round-02, Ask 5 Step A)

**Script:** `scripts/diag_l2b_unit_scale_replay.py` (new, additive, no production-code
edits — `controller/l2b_imu_press_correlation.py` is imported and its module-level
`_IMU_SPIKE_THRESH` attribute is patched in-process only, for the recovery pass; the
file on disk is never touched).

**Method:** for every `sessions/human/hw_*.json` file (real human calibration
captures, not synthetic), replay through `ImuPressCorrelationOracle` three ways:

1. **raw** — gyro as stored in the session JSON (raw int16 LSB, matching Phase 17's
   original offline validation).
2. **live-sim** — same snaps, `gyro_x/y/z /= 1000.0` (matches the live
   `DualSenseReader.poll()` hardware-path scaling confirmed in round-02 Ask 1).
3. **recovery** — live-sim snaps, with `_IMU_SPIKE_THRESH` patched from `30.0` to
   `0.03` (= `30.0 / 1000.0`) for this process only.

Only sessions reaching `_MIN_PRESS_EVENTS = 15` Cross/R2 rising edges produce a
verdict at all (`extract_features()` returns `None` below that floor — most
`hw_*.json` files are stick/tremor/touchpad calibration captures with few or zero
button presses, so this floor is the real bottleneck, not file size).

## Result

Full corpus scan found exactly **one** qualifying session,
`sessions/human/hw_nqpv_009.json` (19 press events) — full output in
`step-a-offline-replay-results.json`:

| Pass | `coupled_fraction` | `anomaly` | fires `0x31` | `humanity_score` |
|---|---|---|---|---|
| raw (as stored) | **1.0** | False | No | **1.0** |
| live-sim (`/1000.0`) | **0.0** | True | **Yes** | **0.0** |
| recovery (`thresh=0.03`) | **1.0** | False | No | **1.0** |

This is a clean, textbook confirmation of the round-02 hypothesis on real captured
human data, not synthetic: the same 19 real button presses with the same real
gyro sensor readings go from **perfectly coupled** (raw units) to **completely
decoupled — firing the advisory as if it were a software injector** (live-scaled
units) to **fully recovered** (threshold corrected to match the live scale). Nothing
else moved between passes — same snaps, same press timestamps, same code path;
only the gyro unit convention and the threshold changed. This isolates the defect to
exactly the unit mismatch identified in round-01/round-02, with no other confound.

## Honest limits of this result

- **N=1 qualifying session.** Only `hw_nqpv_009.json` cleared the 15-press floor in
  the full `sessions/human/` corpus at the time of this run. This is a single clean
  reproduction, not a statistical sample — but the mechanism it demonstrates
  (a fixed absolute LSB threshold vs. a `/1000.0`-scaled live signal) is a closed
  code-path argument already independently confirmed by grok in round-02 Ask 1, so
  one clean empirical case that behaves exactly as predicted is strong corroboration,
  not the sole evidence.
- **Still not a live-runtime observation.** This replays a stored session through the
  oracle offline; it does not prove *today's running bridge process* is observing
  `coupled_fraction≈0` mid-play right now. That gap (grok round-02 Ask 3, "what
  remains unproven without a live session") is unchanged by this step — Step B
  (live WS/diagnostic observation) is still open if that confirmation is wanted.
- **No production code was changed.** `_IMU_SPIKE_THRESH` was patched in a Python
  attribute, in-process, for pass 3 only, then restored before the process exits.
  `controller/l2b_imu_press_correlation.py` is untouched on disk.

## Status

Step A (offline replay) is **complete and confirms the finding** with real captured
human data. Steps B/C/D from grok's ladder (live diagnostic, controlled env-var
recovery probe on a running bridge, production fix candidate) remain open,
unstarted, and out of scope for this pass per the original investigation's
read-only mandate.
