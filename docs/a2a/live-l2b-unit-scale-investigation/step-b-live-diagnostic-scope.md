# Step B — live diagnostic scope (grok round-02 Ask 5 Step B)

**Status: SCOPED, NOT BUILT. NOT RUN.** This document is the plan; nothing has been
executed. Building/running requires operator go-ahead (this is a real-hardware
capture, per the session's standing "ask before starting rig sessions" discipline).

## Goal

Close the one gap Step A (offline replay) could not: prove that the **currently
running production code path**, driven by a **real, physically-connected
controller**, actually observes `coupled_fraction ≈ 0` and fires `0x31` after
real button presses — not just that it structurally must, and not just that a
stored session replays that way offline.

## Definition of done

A short real capture (target: >= 20 real Cross/R2 presses) produces a printed
report of: live `gyro_mag` percentiles (p50/p95/max), the implied adaptive
threshold (`median(baseline) + 30.0`), `n_press_events`, `coupled_fraction`,
`anomaly`, `classify()` result, `humanity_score()` — all computed via the
**unmodified** `ImuPressCorrelationOracle` at its **default** `_IMU_SPIKE_THRESH`
(no patching this time — Step A already proved the patched-recovery behavior;
Step B's job is only to observe today's real default behavior).

## Design

**New script:** `scripts/diag_l2b_live_probe.py`

- Reuses `scripts/u3_raw_capture.py`'s `parse_imu()` byte offsets (gyro
  `/1000.0`-scaled, accel, offsets 16-27) — already regression-tested
  (`bridge/tests/test_u3_raw_capture_imu.py`) and independently confirmed by
  grok round-02 as byte-equivalent to `DualSenseReader`'s real hardware scaling.
- Reads Cross via the same raw-byte convention the L2B/L2C test loaders already
  use for the same physical HID report: `(buttons_0 >> 5) & 1`, remapped to
  `CROSS_BIT = 1 << 0` before constructing the snap object (`l2b_imu_press_
  correlation.py:84`). R2 trigger is read directly as the raw 0-255 byte — no
  remap needed, `_R2_PRESS_THRESH=64` / `_R2_RELEASE_THRESH=30` are already
  raw-scale.
- Feeds each polled frame into one **unmodified, imported, not reimplemented**
  `ImuPressCorrelationOracle()` from `controller/l2b_imu_press_correlation.py`
  via its real `push_snapshot()` method — this is the actual production class,
  just fed from a standalone reader instead of the bridge.
- Plain `hid` library (`hid.device()`, nonblocking), same as `u3_raw_capture.py`
  — **not** `pydualsense`/`DualSenseReader`. Two reasons: avoids a new
  dependency, and avoids exclusive-HID-handle contention if the bridge happens
  to be running at the same time (a different library opening the same VID/PID
  could conflict; the safer default is bridge OFF during this probe anyway,
  stated explicitly below).
- Prints a running status line every few seconds (frame count, current
  `gyro_mag` p95, current `n_press_events`) so progress is visible without
  waiting for the end, then a final report dict — same style as Step A's
  pattern-check printout.

## Explicit non-goals / guardrails

- No `_IMU_SPIKE_THRESH` patch — observe default live behavior only.
- No bridge involvement: does not start, stop, or talk to the bridge process,
  does not touch `bridge/.env`, does not write to `~/.vapi/bridge.db`.
- No chain, no FROZEN/PoAC surface, no production file edits.
- No game required — this only needs the Edge connected via USB data cable to
  the laptop and real Cross/R2 presses under a human hand. No PS5, no BT
  pairing, no CFB27 session needed. Should take 2-3 minutes once running.

## Precondition to confirm before running

**Bridge should be stopped** (or confirmed not holding the HID device) before
this probe opens its own handle, to avoid a silent HID-open failure or, worse,
two processes reading the same device inconsistently. If the bridge is running
and you'd rather not stop it, say so and this gets re-scoped to a WS-subscribe
variant (Ask 5 Step B's other sketch: log `pitl_l2b_*` fields off the live
bridge stream instead of opening a second HID handle) — noted as the fallback,
not the default, because it's more moving parts for the same answer.

## Success / failure criteria (printed, not asserted — this is observation, not
a test)

| Observation | Interpretation |
|---|---|
| `coupled_fraction` near 0, `anomaly=True`, `0x31` fires after warmup | Matches Step A / round-02 prediction — live bug confirmed at runtime |
| `coupled_fraction` high (>= ~0.55), no fire | Prediction refuted — something differs between this probe and the real live path; investigate before trusting Step A's conclusion for production |
| Never reaches 15 presses in the capture window | Inconclusive — extend duration or press more deliberately, not a verdict either way |

## What happens after

This is still read-only characterization, matching the L2B/L2C investigation's
standing mandate. If Step B confirms (expected), the next decision is which of
D1/D3/D4 (already laid out in round-02) to pursue — that's a separate,
explicitly-scoped follow-on, not automatic from this step.
