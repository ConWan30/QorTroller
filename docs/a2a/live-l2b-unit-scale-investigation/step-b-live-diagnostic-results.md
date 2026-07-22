# Step B — live diagnostic results (grok round-02 Ask 5 Step B)

**Script:** `scripts/diag_l2b_live_probe.py`. Bridge stopped for the duration of
this probe (no HID contention). Edge connected via USB data cable only — no
game, no PS5, no BT pairing. Operator pressed Cross / pulled R2 repeatedly on
request.

## Result

25 real button presses observed in 5.5s (2 status ticks at t=2.0s/6 presses,
t=4.0s/15 presses, then target reached at 25):

```json
{
  "duration_s": 5.5,
  "n_frames": 5519,
  "n_press_events": 25,
  "min_press_events_required": 15,
  "imu_spike_thresh_default": 30.0,
  "coupled_fraction_anomaly_floor": 0.55,
  "gyro_mag_p50": 8.2267,
  "gyro_mag_p95": 8.8568,
  "gyro_mag_max": 9.631,
  "coupled_fraction": 0.0,
  "anomaly": true,
  "fires_0x31": true,
  "humanity_score": 0.0
}
```

**MATCHES round-02 hypothesis: `coupled_fraction=0.0` (near 0), `0x31` fired live.**

Live `gyro_mag` never rose above ~9.6 across the entire capture (p50=8.23,
p95=8.86, max=9.63), while the adaptive threshold implied by the default
`_IMU_SPIKE_THRESH=30.0` sat around ~38.2 (baseline median + 30.0). The real
signal is roughly 4x too small to ever cross the floor — matching the Step A
offline-replay pattern (`hw_nqpv_009.json`: raw max ~thousands of LSB collapsing
to single digits at `/1000.0` scale) almost exactly, now reproduced with today's
actual hardware, today's actual code path, in real time.

## What this closes

This was the one gap Step A (offline replay) could not close on its own: proof
that the *currently running* production code, driven by a *real, physically
connected* controller, actually observes this failure mode right now — not
just "structurally must" (round-01/round-02 code trace) or "does when replayed
offline" (Step A). All three lines of evidence now agree:

1. **Code trace** (round-01, confirmed round-02): live hardware path scales
   gyro `/1000.0`; oracle threshold is raw-LSB `30.0`; no compensating rescale
   anywhere in between.
2. **Offline replay** (Step A): one real captured session with enough presses
   goes 1.0 → 0.0 → 1.0 across raw / live-sim / recovery passes.
3. **Live probe** (Step B, this document): a real controller, real hand, real
   time — `coupled_fraction=0.0`, `0x31` fires, on the unmodified default
   threshold.

## Investigation status: characterization complete

The L2B/L2C investigation's original mandate (read-only characterization, no
production fix) is now fully discharged:

- L2B: **confirmed defect, P1 integrity / advisory-only**, reproduced by code
  trace + offline replay + live runtime observation. No production code
  changed anywhere in this investigation.
- L2C: **confirmed immune** to the same bug class (Pearson-correlation
  scale-invariance, pinned with regression tests on real session data).

Remaining work is squarely in Step C/D territory (grok round-02) and is a
**separate, explicitly-scoped decision**, not automatic from this result:
Step C (controlled recovery probe, process-scoped env override, still no
`bridge/.env` persistence) and then choosing D1 (rescale default threshold),
D3 (canonicalize units end-to-end), or D4 (interim honesty rail: force
`p_L2B` neutral + flag) as the production fix.
