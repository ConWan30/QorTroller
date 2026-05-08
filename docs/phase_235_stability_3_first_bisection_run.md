# Phase 235.x-STABILITY-3 — First Instrumented Bisection Run (2026-05-08)

**Run dir:** `logs/stability3_bisection_20260508_173007/`
**Bridge boot:** 22:30:26 UTC
**`/health` ready:** 22:31:24 UTC (58s startup)
**Polling probe:** 22:32:09 UTC start, killed early at 22:34:38 UTC (~150s of probe load before first interrupt)
**Bridge auto-restart by watchdog:** 22:36:43 UTC (after first kill missed the bridge subprocess)
**All processes terminated:** 22:39:35 UTC (bridge subprocess killed during second restart)

## Headline empirical result

**Instrumentation works.** STABILITY-3 loop_health_monitor produced 40 distinct
`LOOP STARVATION` warnings during ~7 min of bridge runtime, max excess 37.87s.
Compared to WIF-065 baseline (16 BRIDGE_UNRESPONSIVE / 0 STARVATION over 30 min),
this run shows clear capture of the offender signal.

**The hypothesised B1/B2/B3 bisection plan (drift sweeper / FSCA / WAL checkpoint)
is NOT supported by the data from this run.** The dominant offender visible here
is the DualShock `_session_loop` running in `sim_mode=True` (no controller
plugged in).

## Quantitative summary

| Metric | Value |
|---|---|
| LOOP STARVATION events | 40 |
| Max excess over 1.0s threshold | 37.87s (single catastrophic stall at 22:32:26) |
| Mean excess (all events) | ~4.5s |
| BRIDGE_UNRESPONSIVE WEC events | 7 (1 boot-grace + 6 during run) |
| BRIDGE_HEALTHY WEC events | 19 |
| `_poll_frames` 10s timeouts | 1 (at 22:32:25, immediately preceding 37.87s stall) |
| `_session_loop` iterations | 137 |
| `_session_loop` iter-spacing mean | 3.88s (design target: 1.0s) |
| `_session_loop` iter-spacing max | 68.0s |
| Iter gaps in 1-2s range | 67 / 136 (49%) |
| Iter gaps in 2-5s range | 34 / 136 (25%) |
| Iter gaps in 5-10s range | 25 / 136 (18%) |
| Iter gaps > 10s | 10 / 136 (7%) |
| `/health` polls > 1s | 50 / 109 success polls (46%) |
| `/health` p99 latency | 10s (capped by probe timeout) |

## Smoking gun

```
17:32:25 [WARNING] dualshock_integration: _poll_frames timed out after 10.0s
                  — possible USB freeze or disconnect (iter=45, is_sim_mode=True)
17:32:26 [INFO] session_boundary_detector_agent: stopped — GIC_target reached (fires=0)
17:32:26 [WARNING] loop_health_monitor: LOOP STARVATION expected sleep=2.0s,
                  actual=39.87s (excess=37.87s)
17:32:26 [WATCHDOG] INFO Bridge recovered.
```

The 10s `_poll_frames` timeout fires inside the asyncio event loop. The
`asyncio.wait_for(..., timeout=10.0)` boundary cannot cancel a synchronous
inner call that's currently executing — so the timeout fires only after the
sync work yields, and then additional sync work continues to block the loop
for the remaining 27.87s.

After this catastrophic event, every subsequent `_session_loop` iteration
triggers another STARVATION warning (4-9s excess each), confirming the loop
itself is the recurring offender — not a single periodic background task.

## Why drift sweeper / FSCA / WAL hypotheses don't fit

| Hypothesis | Expected cadence | Observed cadence | Match? |
|---|---|---|---|
| B1 drift sweeper | every 60s (bundle) | continuous, ~5s spacing | **NO** |
| B2 FSCA | every 900s (15 min) | continuous, ~5s spacing | **NO** |
| B3 WAL checkpoint | irregular (~1000-frame trigger) | continuous | **NO** |
| **NEW: sim_mode session_loop** | every iteration | every iteration matches | **YES** |

FSCA's 900s poll interval means at most ONE FSCA cycle could have fired
during this 7-min run; its first poll happens at the schedule mark. Drift
sweeper has 60s bundle / 600s scope intervals — ~7 bundle cycles maximum,
not 40+ events. The data refutes both.

## Self-stabilization observation

The loop_health_monitor's cumulative summary at 22:37:49 reports
`30 checks, 3 starvation events (max excess 1.38s)` — the rate dropped
dramatically after the first ~5 min of bridge life. This matches the
empirical pattern of "heavy startup work concentrates in the first few
minutes." Once CorpusDataCuratorAgent's startup poll completes (Task 2
"entropy" + Task 6 "readiness" fired at 22:31:18-19), things settle.

## Confounders

1. **sim_mode is not the production load profile.** The bridge auto-falls
   to sim_mode when no controller is plugged in (Phase 52 hardening). The
   WIF-064/065 baseline was measured with real controller polling at ~1000Hz.
   sim_mode generates synthetic frames at a different cadence with different
   sync work patterns. **The offender identified here may not be the same
   offender that produced WIF-064/065's BRIDGE_UNRESPONSIVE events.**

2. **Probe path errors.** 112 of 203 polls hit `/bridge/capture-health` and
   `/bridge/grind-chain-status` and returned 404 (probe used wrong paths;
   actual mount is likely under operator app's doubled-prefix). This reduced
   load on the bridge during the run, biasing results toward "less
   starvation than baseline" — but starvation was still severe, so the
   conclusion holds.

3. **GRIND_TARGET reached.** Bridge log line 22:32:26
   "SessionBoundaryDetectorAgent stopped — GIC_target reached this run
   (fires=0)" — chain_length=100 was already at target when bridge booted.
   Some grind-mode-specific code paths may behave differently than during
   the WIF-064/065 baseline (which was during active grind).

## Revised bisection priority

Given the data, the corrected priority order is:

1. **NEW B0: sim_mode session_loop sync biometric extraction.** Most likely
   to surface starvation in tests run without controller. Real fix: wrap
   the per-record biometric pipeline (FFT, Mahalanobis distance computation,
   feature extraction) in `asyncio.to_thread`, mirroring STABILITY-2's
   approach for FSCA and drift sweeper.

2. **B1-B3 unresolved.** The B1/B2/B3 hypotheses cannot be confirmed or
   refuted from this run because the load profile (sim_mode) doesn't match
   the baseline (real controller). To test those hypotheses we need a
   real-controller run with the polling probe paths fixed.

## Recommended next actions

1. **Fix probe paths.** Find the correct mount points for capture-health and
   grind-chain-status (likely `/operator/operator/bridge/capture-health` per
   doubled-prefix convention) so the probe generates representative load.

2. **File this as WIF-066 (sim_mode session_loop loop-blocking).**
   Independent finding from the WIF-064/065 sequence; operationally adjacent
   but not a duplicate.

3. **Defer code change until real-controller baseline.** Don't ship a fix
   targeting sim_mode session_loop until we confirm whether the same code
   path is the offender during real-controller grinds. The fix shape
   (asyncio.to_thread wrap on biometric pipeline) is the same in either
   case, but priority depends on which run it's actually fixing.

4. **Re-run with real controller.** Operator plugs in DualShock Edge and
   repeats this protocol. Compare iter-gap histogram and STARVATION cadence
   between sim_mode and real-controller runs. Whichever offender persists
   is the production target.

## Log artifacts

- `logs/stability3_bisection_20260508_173007/watchdog.log` — full bridge stdout
  (400+ lines, includes both boot sequences and 40 STARVATION warnings)
- `logs/stability3_bisection_20260508_173007/polling_probe.jsonl` — 203 poll
  records including header + footer summary
- `logs/stability3_bisection_20260508_173007/probe.stderr.log` — probe banner

These are not committed (logs/ is large + run-specific) but kept locally
for the next operator session's verification.
