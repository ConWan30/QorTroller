# WHAT_IF Entry — Stability Proof Empirically Refutes Phase 235.x Proactor Root-Cause Hypothesis (2026-05-07)

**Source**: 30-minute sustained polling-load empirical test (T=19:46 → T=20:17,
2026-05-07) of bridge-under-watchdog with Phase 235.x-STABILITY fix
(commit `dfbbb048`) deployed
**Phase**: 235.x-STABILITY validation; result inverts initial diagnosis
**Validation**: NEGATIVE RESULT — proves the fix doesn't address root cause;
points future investigation at loop-blocking sync work

---

## WIF-064 — Bridge Zombies Without Exceptions; Loop-Blocking Sync Work Is The Real Cause

**Operator-observed symptom**: Bridge under watchdog with Phase 235.x-STABILITY
defensive tuning shipped. 30-min sustained polling-load (curl every 3s
mimicking frontend hooks). Expected: zero zombies. Observed: 16 BRIDGE_UNRESPONSIVE
events + 3 RESTART_TRIGGERED. Polling pass rate: 17.5% (7/40 health checks
succeeded; 33 timed out).

**W1 — Failure mode (refuted hypothesis)**:

Phase 235.x-STABILITY (commit `dfbbb048`) shipped 3 layers of defensive tuning:
1. asyncio exception handler suppressing `_ProactorBasePipeTransport._call_connection_lost` callbacks
2. uvicorn `timeout_keep_alive=120` (was 5s)
3. DualShock USB poll timeout 4× → 10× multiplier

The hypothesis: chronic bridge "zombie" pattern (uvicorn HTTP serving dies while
asyncio loop continues) is caused by Windows asyncio Proactor connection-lost bugs
under uvicorn HTTP keep-alive thrash.

**EMPIRICAL FINDING — the hypothesis was wrong**:

Over the 30-min window:
- `_stability_exception_handler` triggered **0 times** — Proactor `_call_connection_lost`
  errors did NOT fire
- Python tracebacks logged: **0** — bridge isn't crashing with exceptions
- Bridge process stayed alive with `_session_loop` advancing — pure asyncio loop
  did NOT die
- HTTP serving became unresponsive for 12-30s windows, then recovered without
  any visible error

This means the bridge zombie pattern is **NOT** a Proactor connection-cleanup bug.
It's something **blocking the asyncio event loop synchronously** — not crashing it.

**Real root cause hypothesis (untested, candidates):**

| Candidate | Why suspected |
|-----------|---------------|
| SQLite WAL contention | Long DB queries on event loop thread block all HTTP serving |
| `cedar_drift_sweeper` chain RPC reads | C4 sweeper does sync chain reads every 600s (scope drift sweep) |
| FSCA synchronous queries during 15-min poll | FleetSignalCoherenceAgent reads many tables per cycle |
| Operator endpoints with heavy DB joins | activation_log lookup empirically slow at first hit |
| pydualsense HID poll executor saturation | Concurrent USB executor threads blocking event loop scheduling |

The common pattern: **synchronous work executing on (or starving) the event loop
thread for >12s windows, during which uvicorn cannot accept new HTTP connections
or serve queued ones.**

**W2 — Closure (operational only; root-cause fix deferred)**:

The watchdog correctly detected and recovered:
- 16 BRIDGE_UNRESPONSIVE events all caught within 12-30s
- 3 RESTART_TRIGGERED events all completed successfully
- WATCHDOG_HALT did NOT trigger (stayed under 3-restart-per-hour ceiling)
- Bridge service remained operationally usable (just degraded)

**Phase 235.x-STABILITY fix is not removed** — it remains as defensive
infrastructure for the case where Proactor errors DO occur. But its description
in CLAUDE.md / project_phase_235_stability memory should be amended:
"defensive tuning that addresses one of several potential zombie causes;
real root cause is loop-blocking sync work (WIF-064)."

**Generalized lesson**: A diagnosed root cause + a fix that PASSES unit tests
does NOT prove the fix addresses the operational problem. Only sustained
empirical observation under realistic load proves (or refutes) the diagnosis.
**Negative results are valuable** — they redirect future investigation toward
the actual root cause instead of chasing the wrong abstraction.

**Future Phase 235.x-STABILITY-2 candidate** (next investigation):
1. Add asyncio scheduler-instrumentation: log when event loop is starved
   (e.g., asyncio's `slow callback` warning at threshold lowered to 1s)
2. Profile FSCA + drift sweeper + DB queries for synchronous blocking
3. Wrap suspected sync work in `asyncio.to_thread()` migration
4. Re-run 30-min stability proof; expect zero BRIDGE_UNRESPONSIVE if
   loop-blocking is the real cause

**Operational impact**: Watchdog continues to be the safety net. Frontend
testing works in flickering windows (~50s healthy → ~20s zombie → recover).
Phase O1 D 3-week shadow data accumulation continues uninterrupted thanks
to watchdog auto-restart. Real root-cause investigation is wallet-free,
controller-free, no-bridge-restart work for a future session.

**Cross-references**:
- Commit `dfbbb048` — original (incomplete) Phase 235.x-STABILITY fix
- WIF-062 — original (now superseded) Proactor zombie hypothesis
- Memory `project_phase_235_stability.md` — needs amendment per this WIF
- Watchdog: `scripts/bridge_watchdog.py` (still THE essential safety net)
- Empirical test artifact: `C:/Users/Contr/AppData/Local/Temp/stability_watchdog.log`
  + `bdi90ygij.output` (30-min window, 19:43-20:18 UTC 2026-05-07)
