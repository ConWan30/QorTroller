# Step C — live controlled recovery probe results

**Executed:** operator-fired, this session, following round-04's approved-with-
modifications procedure. Two runs; the first was discarded as confounded, the
second is the real result.

## Setup issues found and resolved before any real data was collected

1. **Pre-existing bridge process (PID 1612, ~1.3GB resident)** was already
   bound to port 8080 from an earlier, unrelated session — not started by this
   procedure, running the default (unscoped) `L2B_IMU_SPIKE_THRESH`. Operator
   confirmed safe to stop; stopped before any observation began. Pointing the
   observer at port 8080 without catching this would have silently measured
   the wrong process.
2. **My own first scoped-launch attempt failed to bind** (port still held by
   PID 1612 at that moment) and left a zombie process (PID 15976) holding the
   Edge's HID device exclusively even though its HTTP server never came up.
   Operator confirmed safe to kill; killed before relaunching.
3. **Observer stdout buffering**: piping to a file without `python -u`
   silently buffers `print()` output, so the first observer launch produced no
   visible progress. Relaunched with `-u` for live monitoring; the buffered
   duplicate was left running and later checked for cross-confirmation (it
   agrees with the finding below).

## Run 1 (discarded) — confounded by an unrelated automated haptic pulse

Bridge launched with `L2B_IMU_SPIKE_THRESH=0.03`, `CHAIN_SUBMISSION_PAUSED=true`,
`GRIND_MODE=false`. 180s observation, 136 non-null samples (unbuffered) / 135
(buffered duplicate), **100% flat at `coupled_fraction=0.0`**, `inference_name`
consistently `0x32` (L2C, not L2B), at a suspiciously regular ~1.2-1.3s cadence.

Investigation found `bridge/.env` has `DUAL_GRIND_TETHER_ENABLED=true`. Reading
`dualshock_integration.py` (~L805-820): "VSD Cycle 25 tether" fires an
automated adaptive-trigger haptic pulse every `dual_grind_tether_duty_s=1.2s`
to keep the DualSense Edge's wireless module anchored to the PS5 during
dual-connection play. This is a real hardware-actuated pulse, not a synthetic
input event — but since it's motor-driven (not a genuine hand/grip motion), any
resulting oracle classification of it as "decoupled" would be **structurally
correct behavior for that stimulus**, not evidence about the unit-scale bug.
The cadence match (~1.2-1.3s observed vs. 1.2s configured duty cycle) is strong
circumstantial confirmation this is what dominated the sample. **This run's
verdict is discarded, not reported as a Step C result** — neither round-03 nor
round-04 anticipated this confound.

## Run 2 (real result) — tether disabled, real presses operator-confirmed

Bridge relaunched with `L2B_IMU_SPIKE_THRESH=0.03`, `CHAIN_SUBMISSION_PAUSED=true`,
`GRIND_MODE=false`, `DUAL_GRIND_TETHER_ENABLED=false`. Startup log confirmed the
"Cycle25 tether ENABLED" line was **absent** this run (present in Run 1's log) —
direct evidence the override took effect, and by the same import-time-env
mechanism round-04 C1 already verified is leak-proof, giving confidence
`L2B_IMU_SPIKE_THRESH=0.03` also loaded correctly (not independently re-verified
via a runtime value dump this run — see open questions).

Operator explicitly confirmed pressing Cross/R2 continuously throughout this
120s window (asked directly mid-run rather than assumed, given the ambiguous
early cadence).

**Result: 102/102 non-null samples flat at `coupled_fraction=0.0`,
`l2b_p_human=0.0`, `inference_name=0x31` (L2B itself winning the record) on
every single sample.**

```json
{
  "duration_s": 120.0,
  "n_non_null_samples": 102,
  "fires_0x31_total": 102,
  "fires_0x31_in_last5": 5,
  "median_coupled_fraction_last5": 0.0,
  "median_p_human_last5": 0.0
}
```

**Verdict: RECOVERY FAILED** per round-04 Ask 4's dual gate
(`median_cf < 0.15` and `0x31` firing in the trailing window both independently
satisfy the fail condition here).

## What this means (and does not mean)

Per round-04 Ask 5's explicit instruction: **do not jump to a production fix**
on this result — a Step C failure could mean the fix is genuinely insufficient,
or it could mean an integration-specific confound Steps A/B couldn't have
caught because they bypassed the full bridge wiring. The contrast is stark:
Step A (offline replay, same oracle class, real captured session) went
`1.0 -> 0.0 -> 1.0` across raw/live-sim/recovery passes. Step B (standalone
live script, real Edge, real presses, same oracle class, same threshold
mechanism) also went to `0.0` at the default and would be expected to recover
at `0.03` (not yet re-tested at 0.03 standalone — see next step). Step C, run
through the **full bridge integration path** with the identical fix applied,
shows **zero recovery** despite confirmed real presses and the tether confound
removed.

This gap between "isolated oracle recovers" and "same fix, same hardware, full
bridge path does not" is itself the load-bearing new finding. It points at
something specific to `dualshock_integration.py`'s wiring — not necessarily the
unit-scale hypothesis being wrong, but something *additional* in the
integration layer breaking recovery that a standalone script never exercises.

## Immediate next diagnostic (cheapest per round-04's own C-fail ladder)

**C-fail-2** is the fastest, already-built next step: re-run
`scripts/diag_l2b_live_probe.py` (Step B's standalone script) with
`L2B_IMU_SPIKE_THRESH=0.03` set, using real live presses right now, in this
same session. If the standalone script recovers at 0.03 but the full bridge
still doesn't, that isolates the problem to the integration layer specifically
(button-bit remap, event-loop batching of gyro samples into the precursor
window, or something else `dualshock_integration.py` does differently from
both the standalone reader and the offline replay). If the standalone script
*also* fails to recover now, the unit-scale hypothesis itself needs
re-examination — a materially different, more serious finding.

**Not yet run. Awaiting operator direction on whether to proceed immediately
or scope the next step with grok first**, consistent with this investigation's
established discipline.
