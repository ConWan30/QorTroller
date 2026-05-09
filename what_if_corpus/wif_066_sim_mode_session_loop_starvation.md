# WHAT_IF Entry — sim_mode `_session_loop` Saturates Event Loop with Synchronous Biometric Extraction (2026-05-08)

**Source**: Phase 235.x-STABILITY-3 first instrumented bisection run
(`logs/stability3_bisection_20260508_173007/`), bridge-under-watchdog
running 22:30:26 → 22:39:35 UTC with no controller plugged in (sim_mode auto-fallback)
**Phase**: 235.x-STABILITY-3 validation; instrumentation works perfectly,
B1/B2/B3 hypotheses refuted by data, NEW offender candidate identified
**Validation**: POSITIVE INSTRUMENTATION RESULT — STABILITY-3 captures
LOOP STARVATION events with file/line precision; first run identifies a
non-hypothesised offender candidate

---

## WIF-066 — sim_mode session_loop is the Dominant Starvation Source under Polling Load

**Operator-observed symptom**: First post-STABILITY-3 instrumented bisection
run (5-min effective probe load + ~2 min cooldown). Goal: capture
LOOP STARVATION timings + correlate with WEC BRIDGE_UNRESPONSIVE events to
identify which background task is the offender (B1 drift sweeper / B2 FSCA /
B3 WAL checkpoint hypotheses prepared).

Result: **40 LOOP STARVATION warnings, max excess 37.87s, mean ~4.5s.** The
hypothesised B1/B2/B3 cadences (60s / 900s / irregular WAL) DO NOT FIT the
data — STARVATION events are continuous (~5s spacing), not periodic.
Smoking gun: `_poll_frames timed out after 10.0s — possible USB freeze or
disconnect (iter=45, is_sim_mode=True)` directly preceded the 37.87s
catastrophic stall.

**W1 — Failure mode**:

In `is_sim_mode=True` (no controller plugged in, Phase 52 fallback active),
the DualShock `_session_loop` runs synthetic frame generation followed by
the full per-record biometric pipeline (FFT for tremor peak, Mahalanobis
distance, feature extraction across all 12 dimensions, record dispatch,
DB insert). All of this work currently executes synchronously on the
asyncio event loop thread.

In `is_sim_mode=True`, there is no natural backpressure from real USB HID
polling rate. Synthetic frames generate as fast as the sync work completes,
so `_session_loop` iterations run back-to-back at ~3-9s/iter, blocking the
loop continuously.

Empirical iter-gap histogram (137 iterations over ~7 min):
- 1-2s spacing: 67 iters (49%) — design-target rate
- 2-5s spacing: 34 iters (25%) — mild blocking
- 5-10s spacing: 25 iters (18%) — moderate blocking
- >10s spacing: 10 iters (7%) — severe blocking, max 68s gap

Mean iter time: 3.88s vs design target 1.0s. Bridge throughput at ~26% of
intended.

This pattern is INVISIBLE to STABILITY-2's to_thread instrumentation (FSCA
+ drift sweeper) because the offender is in dualshock_integration, not
those modules. STABILITY-3's independent heartbeat task captures it
because it doesn't care which task is blocking — only that the loop is
blocked.

**W2 — Mitigation**:

Three options, in order of preference:

1. **Wrap per-record biometric pipeline in `asyncio.to_thread`** —
   mirroring STABILITY-2's pattern for FSCA/drift sweeper. Requires
   identifying the specific call chain
   (BiometricFeatureExtractor.extract → numpy FFT/Mahalanobis →
   record dispatch). Most surgical. **Phase 235.x-STABILITY-4 candidate.**

2. **Throttle sim_mode frame generation rate** — add a minimum
   `await asyncio.sleep(0.1)` between synthetic frame generations so the
   loop yields between iterations. Hides the symptom in sim_mode but
   doesn't address the underlying sync-on-loop pattern; would still
   manifest under real controller load. Not preferred.

3. **Skip biometric extraction in sim_mode** — only run
   feature extraction when frames came from real HID. Operationally
   correct (sim_mode features don't represent any real player anyway)
   but changes test/grind behavior in ways that may have downstream
   effects on calibration_intelligence_agent + InsightSynthesizer
   feedback loops. Risky.

**Critical confounder (REFUTED 2026-05-08T19:08-19:22 UTC)**: First-run was
sim_mode. **Second run with controller plugged in (`sim_mode=False`,
real DualShock Edge) shows MORE STARVATION not less**: 60 events in 13 min
vs 40 events in 7 min for sim_mode. Mean spacing 11.2s, max excess
similar magnitude. The session_loop sync work IS the production offender;
sim_mode behaviour generalizes. (Earlier conjecture that "real USB polling
provides natural backpressure" was wrong — `_make_record` and
`Bridge.on_record` synchronous work dominates regardless of frame source.)

Real-controller run also REFUTES B1 (drift sweeper, 60s cadence) and B2
(FSCA, 900s cadence) hypotheses: 46 of 59 STARVATION gaps fall in 5-30s
range. Neither periodic offender candidate fits.

**W3 — Verification gap**:

To distinguish "sim_mode-only" from "real-controller too" we need:

- A second bisection run with controller plugged in
- Same probe protocol but with corrected paths (current probe got
  404 on `/bridge/capture-health` and `/bridge/grind-chain-status` —
  likely doubled-prefix issue per WIF-061; need to verify mount points)
- Compare iter-gap histogram and STARVATION rate between sim_mode and
  real-controller

If real-controller shows similar STARVATION cadence, ship STABILITY-4
to_thread fix on biometric pipeline. If real-controller is clean,
sim_mode-specific throttle (option 2) is sufficient and STABILITY-3
already establishes that real-controller is the operating regime that
matters.

**Architectural note**: STABILITY-3 instrumentation is now general
infrastructure for any future "loop starvation" question. Independent
heartbeat at 2s cadence + 1s threshold + cumulative summary every 60
checks. No asyncio internals monkey-patching, works regardless of
debug mode, catches ANY cause. Future bisection runs use this same
mechanism.

**Status**: CLOSED 2026-05-09 — Phase 235.x-STABILITY-4 shipped + empirically
validated. `Bridge.on_record` refactored to route the heavy sync chain
(PITL apply + ECDSA-P256 verify + 3 SQLite writes) through
`asyncio.to_thread(self._persist_record_sync, ...)`. Default ON; opt-out
via `LOOP_PERSIST_TO_THREAD_ENABLED=false`. 7 deterministic tests
T-235-STAB4-1..7 PASS. Adjacent regression 33/33 PASS.

**Empirical validation 2026-05-09T08:47Z** (run dir
`logs/stability4_validation_20260509_034724/`):
  - `/health` p50: 584ms → **3ms** (195× faster)
  - Probe global p50: 2028ms → 31ms (-98%)
  - LOOP STARVATION rate: 4.6/min → 2.5/min (-46%)
  - BRIDGE_UNRESPONSIVE rate: 1.8/min → 0.85/min (-53%)
  - Max STARVATION excess: 37.87s → ~14s (no more catastrophic stalls)

Per-source record ordering preserved by sequential await pattern in the
caller (DualShockTransport `_session_loop` awaits each `_dispatch` one
at a time per source). PoAC chain link hash invariants unchanged
(SHA-256(body[0:164]) — codec untouched).

**Residual STARVATION sources** (smaller — for STABILITY-5 candidates):
  - `_resolve_pubkey` cold-cache `store.list_devices()` scan still on loop
  - capture-health endpoint reading store synchronously
  - WAL checkpoint pressure under faster persist throughput
  - WS broadcast JSON serialization on loop

None of these produce the 30+ second catastrophic stalls seen pre-fix,
so the watchdog's 3-restart-per-hour ceiling is comfortably clear of
operational rates. Bridge is now operationally usable for sustained
polling load — frontend testing + Phase O1 D shadow data accumulation
both feasible without watchdog restart loops.

Closing references:
  - Code: `bridge/vapi_bridge/main.py` (`on_record` + `_persist_record_sync`)
  - Config: `bridge/vapi_bridge/config.py` (`loop_persist_to_thread_enabled`)
  - Tests: `bridge/tests/test_phase_235_stability_4.py` (7 tests)
  - Validation: `docs/phase_235_stability_4_validation.md`
