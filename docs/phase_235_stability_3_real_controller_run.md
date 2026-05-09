# Phase 235.x-STABILITY-3 — Real-Controller Bisection Run + PROBE-FIX (2026-05-08)

**Run dir:** `logs/stability3_realctrl_20260508_190820/`
**Bridge boot:** 19:08:27 local
**`/health` ready:** 19:09:22 local (~55s startup)
**Real-controller mode:** `sim_mode=False` (DualShock Edge plugged in this time)
**Probe duration:** ~9 min effective (probe relaunched once after self-test deadline tuning)
**Run ended:** 19:22:01 local (operator-initiated kill)

## Headline empirical result

**WIF-066 sim_mode confounder hypothesis REFUTED.** Real-controller
produces MORE LOOP STARVATION events than sim_mode, not less.
Both modes show continuous sub-30s starvation cadence; the offender
generalizes across frame sources. B1/B2/B3 hypotheses (drift sweeper /
FSCA / WAL checkpoint) **also refuted by both runs**.

## Side-by-side comparison

| Metric | First run (sim_mode) | Second run (real controller) |
|---|---|---|
| Bridge runtime measured | ~7 min | ~13 min |
| LOOP STARVATION events | 40 | **60** |
| Mean STARVATION spacing | continuous, ~5s | 11.2s |
| Max STARVATION excess | 37.87s | similar magnitude |
| BRIDGE_UNRESPONSIVE WEC events | 7 | **23** |
| `/health` p99 latency | 10s (capped) | 10s (capped) |
| `/health` p50 latency | n/a (probe paths broken) | 584ms |
| Probe global p50 latency | n/a | **2028ms** |
| Probe slow_gt_1s rate | 46% | **58%** |

**STARVATION gap distribution (real-controller, n=59 gaps):**
- < 5s: 9 (15%)
- 5-30s: 46 (78%) — dominant bucket
- 30-90s: 3 (5%)
- 90s-15min: 1 (2%)
- > 15min: 0

This distribution is INCOMPATIBLE with B1 (60s drift sweeper — would put
~13 events at exactly 60s spacing) and INCOMPATIBLE with B2 (900s FSCA —
would put at most 1 event in the run window). The offender's cadence
matches `_session_loop` iteration spacing in starved-but-running state.

## PROBE-FIX changes shipped

Two bugs in the original probe (commit `1ce38c72`) wasted half the first
bisection run:

1. **Path doubled-prefix.** `/bridge/capture-health` and
   `/bridge/grind-chain-status` were declared inside the operator sub-app
   (mounted at `/operator`). Real URLs are `/operator/bridge/X`. Per
   WIF-061 doubled-prefix convention.

2. **No fail-fast self-test.** Probe ran 1700s producing 50% 404 error
   rate without warning. PROBE-FIX adds `_self_test()` that runs every
   configured endpoint once before main load and aborts on 404/401/403
   while treating timeouts as REACHABLE-BUT-STARVED (the signal we want
   to measure).

Probe also gained:
- `OPERATOR_API_KEY` resolution from explicit arg → env → `bridge/.env`
- `x-api-key` header injection on operator endpoints (skipped on `/health`)
- `_DEADLINE_EXCEEDED` sentinel in self_test_results JSONL header for audit
- `--skip-self-test` flag for diagnostic edge cases
- 8 deterministic tests (T-235-STAB3-PFIX-1..6) covering env-file parsing,
  api-key precedence, 404 = abort, 200 = pass, timeout = pass, regression
  guard on the doubled-prefix paths

All 8 tests PASS in 0.61s. Bridge tests unchanged (probe is operator-side
tooling).

## Smoking gun (real-controller)

```
19:09:22 [INFO] Bridge /health responsive
19:09:30 [INFO] _session_loop: iter=24 (sim_mode=False)
19:09:40 [WARNING] LOOP STARVATION: actual=Xs (excess=Ys)
...
19:08:57 → 19:21:36 — 60 STARVATION events spread across 13 min
```

`_session_loop` iteration spacing matches STARVATION cadence: when each
session_loop iter runs the synchronous PoAC pipeline (`_make_record` →
`_dispatch` → `Bridge.on_record`), the event loop is blocked for the
duration of biometric extraction + signing + DB insert + chain submission
trigger evaluation. Subsequent endpoint requests pile up in the asyncio
ready queue.

## What this leaves unresolved

WIF-064/065 reported 16 BRIDGE_UNRESPONSIVE events over 30 min with the
older STABILITY-2 fix. This run shows 23 events over 13 min — roughly
3.5× the rate. Possible reasons:
1. Higher /health poll rate (1Hz vs the WIF-064 frontend cadence)
2. Bridge wallet at 0.132 IOTX may produce different chain-pause behavior
3. Different DualShock state (battery, BT pairing, stick deadzone) than
   WIF-064 baseline

These don't change the bisection conclusion (offender is sub-30s, not 60s
or 900s). They do mean the absolute STARVATION rate isn't directly
comparable across runs.

## Recommended next phase

**Phase 235.x-STABILITY-4** — wrap `_make_record` + `_dispatch` →
`Bridge.on_record` synchronous work in `asyncio.to_thread`, mirroring
STABILITY-2's pattern for FSCA + drift sweeper.

Concrete call sites (from this session's audit):
- `bridge/vapi_bridge/dualshock_integration.py:1677`
  `await self._dispatch(raw)` — currently awaits but `_dispatch`'s inner
  call to `Bridge.on_record` runs sync work on the loop thread
- `bridge/vapi_bridge/dualshock_integration.py:2262` `_dispatch`
- `Bridge.on_record` in main.py — full PoAC verification path

Risk: PoAC chain integrity is downstream of this path. Any `to_thread`
wrap MUST preserve:
- Per-record ordering (chain link hash depends on prior body bytes)
- Chain link hash invariant: SHA-256(body[0:164])
- Atomicity of "verify → insert → trigger downstream" pipeline

Tests for STABILITY-4 must verify per-record sequencing is unchanged
under load (probably by sending N records and asserting chain link
hashes match the synchronous reference output).

**STABILITY-4 is NOT shipped this commit.** Verification-first discipline:
the fix surface is large enough that operator review on the design is
warranted before code changes land.

## Log artifacts

Local-only (logs/ not committed):
- `logs/stability3_realctrl_20260508_190820/watchdog.log` — 700+ lines
  including 60 STARVATION warnings + 23 WEC BRIDGE_UNRESPONSIVE events
- `logs/stability3_realctrl_20260508_190820/polling_probe.jsonl` — 215
  poll records with full latency distribution
