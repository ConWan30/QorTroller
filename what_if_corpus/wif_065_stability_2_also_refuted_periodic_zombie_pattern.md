# WHAT_IF Entry — STABILITY-2 Empirical Validation Also Negative; Periodic Zombie Pattern Suggests OS-Level Cause (2026-05-08)

**Source**: 30-min sustained polling-load empirical test (T=12:16 → 12:46
2026-05-08) of bridge-under-watchdog with Phase 235.x-STABILITY-2 fix
(commit `bcd66b35`) deployed
**Phase**: 235.x-STABILITY-2 validation; SECOND consecutive negative result;
points to OS-level / non-callback root cause
**Validation**: NEGATIVE RESULT — proves the to_thread fixes don't address
the chronic zombie pattern; identifies asyncio instrumentation gap

---

## WIF-065 — Identical 16/16 BRIDGE_UNRESPONSIVE Across Two Different Fixes Reveals Periodic Cause + Instrumentation Gap

**Operator-observed symptom**: Phase 235.x-STABILITY-2 (commit `bcd66b35`)
shipped to_thread wraps for FSCA detection methods + cedar_drift_sweeper
bundle sweep + asyncio slow_callback_duration instrumentation. 30-min
empirical re-run of the WIF-064 polling-load test methodology was supposed
to show 0 BRIDGE_UNRESPONSIVE events if the to_thread fixes addressed the
real root cause.

Result: **16 BRIDGE_UNRESPONSIVE events — IDENTICAL to WIF-064 baseline.**

| Metric | WIF-064 baseline | STABILITY-2 result |
|--------|------------------|-------------------|
| BRIDGE_UNRESPONSIVE | 16 | **16 (identical)** |
| RESTART_TRIGGERED | 3 | **3 (identical)** |
| WATCHDOG_HALT | 0 | **1** (worse) |
| Slow callback warnings | n/a | **0** (instrumentation silent) |
| Polling failure rate | 82.5% | ~40% (better) |

The IDENTICAL count strongly implies a **periodic zombie cause** at ~112s
mean spacing (30 min / 16 events) that the to_thread fixes did not affect.

**W1 — Failure mode (TWO findings)**:

### Finding 1 — STABILITY-2 to_thread fixes did not eliminate zombies

The hypothesis (per WIF-064): bridge zombies are caused by FSCA's 25+ sync
SQL queries on the event loop thread + drift sweeper's sync file SHA-256.
Wrapping these in `asyncio.to_thread` should yield the event loop and
prevent zombies.

Empirical refutation: zombie count IDENTICAL post-fix. Either:
- The fixes work but additional sync work elsewhere also blocks
- The cause isn't asyncio callbacks at all — something at OS / network level

### Finding 2 — asyncio slow_callback_duration instrumentation produced 0 warnings

Phase 235.x-STABILITY-2 set `loop.slow_callback_duration = 1.0` so any
callback exceeding 1 second would log via asyncio's built-in warning. Zero
warnings appeared during 16 zombie events.

**Root cause of the instrumentation gap**: asyncio's slow-callback warning
fires only when `loop.set_debug(True)` is enabled. STABILITY-2's wiring
sets the threshold but does NOT enable debug mode (it's opt-in via
ASYNCIO_DEBUG_ENABLED env, default False). So the threshold has no effect.

**Periodic cause hypotheses (untested)**:

| Candidate | Why suspected |
|-----------|---------------|
| Windows ProactorEventLoop TCP cycle saturation | uvicorn `keep_alive=120` (Phase 235.x-STABILITY) means each connection lives 120s; periodic close events may bunch up |
| OS-level scheduler starvation | Windows priority inversion under sustained load |
| pydualsense executor pool exhaustion | Concurrent USB poll executor threads block scheduler |
| GIL contention from background imports | InsightSynthesizer Mode 6 + other periodic agents |
| SQLite WAL checkpoint blocking | Periodic auto-checkpoint may pause all queries (~112s suggests checkpoint_truncate interval) |

Notable: 112s is suspiciously close to default SQLite WAL `wal_autocheckpoint`
PRAGMA at 1000 pages (~1 MB) when bridge is generating ~10 KB/s of writes.

**Generalized lesson**: When two different fixes produce IDENTICAL negative
empirical results, the cause is upstream of both fixes. Look at the LAYER
ABOVE (OS, network, stdlib internals), not at finer-grained code-level
fixes. Also: instrumentation must be VERIFIED to actually fire under
expected conditions before being trusted to detect (or rule out) a class
of issue.

**W2 — Closure (operational only; root-cause investigation deferred)**:

The watchdog continues to be the operational safety net:
- 16 BRIDGE_UNRESPONSIVE events all detected within 12-30s
- 3 RESTART_TRIGGERED all completed
- WATCHDOG_HALT fired once (at end of window) — 3-restart-per-hour ceiling
  worked as designed; required brief operator attention then resumed

Phase 235.x-STABILITY (commit `dfbbb048`) and STABILITY-2 (commit `bcd66b35`)
defensive code remains in place — both target real risks (Proactor crashes,
sync work) even though neither addresses THIS zombie pattern. They harden
against edge cases that haven't yet manifested.

**Future Phase 235.x-STABILITY-3 candidate** (next investigation):

1. **Fix the instrumentation gap first**: enable `loop.set_debug(True)`
   in main.py when `slow_callback_duration` is below 5s, OR add a
   custom slow-callback handler that doesn't depend on debug mode.

2. **Capture process-level metrics during a zombie event**:
   - Active TCP connections count (Get-NetTCPConnection)
   - Thread count
   - Memory + CPU per zombie window
   - SQLite WAL file size at zombie onset

3. **Test the periodic hypothesis directly**:
   - Disable cedar_drift_sweeper (set CEDAR_DRIFT_SWEEP_ENABLED=false)
   - Re-run 30-min test. If zombie count drops dramatically, drift sweeper
     IS the periodic trigger.
   - Same test with FSCA disabled (set FLEET_COHERENCE_ENABLED=false)
   - Test with auto SQLite WAL checkpoint disabled
     (PRAGMA wal_autocheckpoint=0)

4. **Check Windows TCP TIME_WAIT accumulation**:
   - Default Windows TIME_WAIT is 120s
   - 30 closed connections per minute × 120s = 3600 TIME_WAIT slots
   - If this saturates Windows ephemeral port range, new connections fail
     until cleanup → "zombie" appearance

**Operational impact**: Bridge runs operationally usable thanks to watchdog.
Frontend testing flickers. Phase O1 D 3-week shadow data accumulation
continues uninterrupted (watchdog catches every miss). Real root-cause
fix is STABILITY-3 work for a future session — wallet-free + investigative.

**Cross-references**:
- Commit `bcd66b35` — Phase 235.x-STABILITY-2 (now empirically refuted)
- Commit `dfbbb048` — Phase 235.x-STABILITY (also empirically refuted via WIF-064)
- WIF-064 — first refutation (Proactor hypothesis)
- WIF-062 — original (now twice-refuted) Proactor zombie hypothesis
- Memory `project_stability_proof_negative_finding.md` — needs amendment
- `scripts/bridge_watchdog.py` — THE essential safety net regardless of any
  STABILITY-N fix outcome
- Empirical artifact: `b9tmm97gi.output` watchdog log + `b7rpl7m54.output`
  polling-load log (12:16-12:46 UTC 2026-05-08)
