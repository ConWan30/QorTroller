# C-fail-4 fix — live verification RESULT: RECOVERY CONFIRMED

**This closes the L2B investigation's core question.** With the C-fail-4 fix
applied (`_stamp_frame_collection_times` wired into `_session_loop`, both
committed alongside this doc), the full bridge integration path — real
DualSense Edge, real presses, the exact production code path — now correctly
detects IMU precursors instead of reporting every player as decoupled.

## Setup

Bridge launched with `L2B_IMU_SPIKE_THRESH=0.03` (the separately-confirmed
unit-scale fix, still only process-scoped — not yet a permanent code change),
`CHAIN_SUBMISSION_PAUSED=true`, `GRIND_MODE=false`,
`DUAL_GRIND_TETHER_ENABLED=false` (avoiding the automated-haptic-pulse
confound found during Step C). This is the identical env-override recipe as
the clean Step C run, so the only variable versus that prior *failed* run is
the code fix itself.

## A real mistake caught before it corrupted the result

The first launch attempt in this verification pass silently fell back to
**simulation mode** (`DualSense Edge not found — running in simulation mode`)
because the bridge process started before the operator had reconnected the
controller's USB cable. Simulation mode is decided once at startup and
doesn't re-check while the process runs, so this bridge instance would never
have picked up real hardware no matter how long it ran. Caught by reading the
startup log explicitly for `sim_mode`/`SIMULATION MODE` markers (not assumed
from a clean HTTP bind alone), rather than trusting a run that happened to
produce plausible-looking numbers. The stale bridge was stopped (with
operator confirmation — an initial force-kill attempt was correctly rejected
mid-flight since the operator hadn't yet said the controller was reconnected)
and relaunched only after the startup log showed `DualSense Edge connected`.

## Result

90-second run, real presses throughout:

```json
{
  "duration_s": 90.0,
  "n_non_null_samples": 74,
  "fires_0x31_total": 0,
  "fires_0x31_in_last5": 0,
  "median_coupled_fraction_last5": 0.7514,
  "median_p_human_last5": 1.0,
  "verdict": "RECOVERY CONFIRMED"
}
```

`coupled_fraction` started around `0.65` and climbed to `~0.75` over the
window as more press history accumulated; `p_human` reached `1.0`.
**`0x31` never fired once across all 74 non-null samples.** Compare against
every prior full-bridge measurement in this investigation, all of which were
flat at `0.0` regardless of real presses or the threshold override:

| Run | Path | `coupled_fraction` |
|---|---|---|
| Step C (pre-fix) | full bridge | 0.0 (102/102 samples) |
| C-fail-2 | standalone script | 0.92 |
| C-fail-4 repro | standalone logic test | 0.92-1.0 (Mode B) / 0.0 (Mode A) |
| **This run** | **full bridge, fix applied** | **0.75 (74/74 samples)** |

The full bridge now matches the standalone/offline results instead of
diverging from them — the gap this investigation exists to close.

## Status

L2B is now confirmed working correctly end-to-end: unit-scale fix (process-
scoped, not yet permanent) + timing fix (permanent, committed) together
restore genuine precursor detection through the real production path, on
real hardware, with a real player. Remaining open items, unchanged from
before this verification: (1) `L2B_IMU_SPIKE_THRESH=0.03` is still only a
process-scoped override, not a shipped default — that's a separate decision;
(2) no adversarial (grok) review has happened on any of this since round-04;
(3) L5/L2C's possible shared exposure remains its own, unstarted, future
investigation.
