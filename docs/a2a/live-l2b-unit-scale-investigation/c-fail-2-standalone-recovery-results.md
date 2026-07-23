# C-fail-2 — standalone script re-tested at thr=0.03: isolates the problem to bridge integration

**Executed:** round-04 Ask 5's cheapest next diagnostic, after Step C's live
bridge run showed `RECOVERY FAILED` despite confirmed real presses and the
tether confound removed (`step-c-live-run-results.md`).

## Method

`scripts/diag_l2b_live_probe.py` (Step B's already-built standalone script,
unmodified) re-run with `L2B_IMU_SPIKE_THRESH=0.03` process-scoped, no bridge
involved at all. First attempt completed its 90s window with 0 presses
(operator confirmed they hadn't started pressing yet — re-run cleanly rather
than treated as a result). Second attempt: real presses started immediately.

## Result

25 real Cross/R2 presses in 5.1s:

```json
{
  "n_press_events": 25,
  "imu_spike_thresh_default": 0.03,
  "gyro_mag_p50": 8.2573,
  "gyro_mag_p95": 8.6544,
  "gyro_mag_max": 9.8485,
  "coupled_fraction": 0.92,
  "anomaly": false,
  "fires_0x31": false,
  "humanity_score": 1.0
}
```

**Clean recovery.** `coupled_fraction=0.92` clears round-04's `>=0.55` recovery
gate comfortably, `humanity_score=1.0`, no `0x31` fire. This matches Step A's
Pass 3 (offline replay, patched threshold) and confirms the unit-scale fix
works correctly on the real, physically-connected Edge, on the identical
oracle class, at the corrected threshold — outside the bridge.

Note: the script's own printed "pattern check" line read *"REFUTES round-02
hypothesis... investigate before trusting Step A's conclusion"* — this is
**not a real contradiction**. That heuristic in `diag_l2b_live_probe.py` was
written for Step B's original purpose (checking whether the *default*
threshold=30 reproduces the bug) and has no awareness that this run used the
`0.03` override; its canned wording is simply stale/misleading when read
against an overridden threshold. The raw numbers (`coupled_fraction=0.92`,
`humanity_score=1.0`, no fire) are the actual, correct, positive result.

## What this settles

Comparing the three live/replay results side by side, all using the identical
`ImuPressCorrelationOracle` class and identical `0.03` threshold:

| Path | Real hardware | Real presses | Result |
|---|---|---|---|
| Step A Pass 3 (offline replay) | N/A (stored session) | 19 (from corpus) | Recovered: 1.0 |
| C-fail-2 (standalone script) | Yes | 25 | Recovered: 0.92 |
| Step C (full bridge) | Yes | confirmed continuous | **Failed: 0.0, every sample** |

Two independent paths that bypass `dualshock_integration.py`'s wiring both
recover cleanly. Only the path that goes through the full bridge integration
fails. This **isolates the residual problem to something specific to
`dualshock_integration.py`'s wiring of the L2B oracle** — not the unit-scale
hypothesis, which is now confirmed correct and sufficient at the oracle level
on real hardware.

## Next diagnostics (round-04's remaining ladder)

- **C-fail-3** — button/Cross bit remap: compare `n_press_events` the bridge's
  oracle instance actually accumulates against raw HID rising edges, to check
  whether `dualshock_integration.py`'s own live snapshot construction feeds
  Cross/R2 correctly into `push_snapshot`.
- **C-fail-4** — timing/batching: confirm gyro samples the bridge's oracle
  receives actually land inside the 5-80ms pre-edge precursor window under the
  bridge's event-loop/session-loop batching cadence, rather than being
  averaged, dropped, or delayed by the async pipeline in a way a standalone
  tight polling loop never would be.

Not yet investigated. This is a genuinely new, narrower finding than the
original unit-scale question and may warrant its own scoped investigation
(read `dualshock_integration.py`'s actual snapshot-construction and L2B
wiring code before hypothesizing further) rather than guessing from here.
