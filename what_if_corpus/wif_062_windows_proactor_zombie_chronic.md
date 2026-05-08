# WHAT_IF Entry — Windows asyncio Proactor Zombie + DualShock USB Poll Pressure (2026-05-07)

**Source**: Multi-session chronic issue finally root-caused at Phase 235.x-STABILITY;
empirically triggered when watchdog HALTED 2026-05-07 18:40 after 3 zombie restart
cycles in 1 hour during operator's frontend test session
**Phase**: 235.x-STABILITY (closure shipped commit `dfbbb048`)
**Validation**: CLOSED via 3-layer defensive tuning fix + 6 unit tests +
empirical burst-test verification

---

## WIF-062 — Windows ProactorEventLoop _call_connection_lost Crashes Under HTTP Keep-Alive Thrash

**Operator-observed symptom**: Bridge process appeared healthy (port LISTEN,
`_session_loop` iterations advancing every 2s, asyncio loop spinning) but
HTTP requests stopped being served. `curl /health` timed out. `curl` against
shadow-log endpoint returned empty. Frontend hooks `noMock: true` correctly
hid C5/C8 surfaces. Watchdog detected unresponsiveness at 30s, killed bridge,
restarted. Cycle repeated 3 times in 1 hour → watchdog HALT per safety
ceiling design.

**W1 — Failure mode (root-caused via V-checks + log analysis)**:

Two compounding issues:

1. **Windows asyncio `_ProactorBasePipeTransport._call_connection_lost`
   chronic bug** (logged Python issue, exists in 3.10+ ProactorEventLoop on
   Windows). Under `uvicorn` HTTP keep-alive thrash, repeated connection
   closes accumulate exceptions until the event loop stops accepting new
   connections while other tasks (`_session_loop`, drift sweeper, FSCA
   poll) keep running. The default uvicorn `timeout_keep_alive=5` exacerbates
   this dramatically when frontend polls at 3s/5s/30s cadences.

2. **DualShock `_poll_frames` timeout 4×interval too aggressive**. Default
   was 4× the 1s interval = 4s. Real Windows USB stacks experience 1-3s
   transient hiccups during normal operation. Each hiccup triggered a
   timeout → scheduled `signal_disconnect` callback + retry → compounded
   event-loop pressure.

**Why SelectorEventLoop wasn't a viable fix** (V-check finding):

3 codebase call sites use `asyncio.create_subprocess_exec` which Selector
doesn't support on Windows:
- `operator_api.py:3918`
- `session_adjudicator.py:1039` (LLM subprocess)
- `zk_verifier.py:85` (ZK proof verification)

Switching to Selector would break all three. **Defensive tuning chosen as
lower-risk alternative.**

**Generalized lesson**: A "bridge zombie" can present as a process that
appears alive (LISTEN socket, CPU activity, heartbeat tasks running) but
whose HTTP serving is dead. Listen state is not aliveness. Always probe
end-to-end with a real HTTP request before claiming the service is healthy.

**W2 — Closure (commit `dfbbb048`)**:

3-layer defensive tuning:

| Layer | Change | Effect |
|-------|--------|--------|
| asyncio | `_stability_exception_handler` matches `_call_connection_lost` messages → log WARNING + continue | Crashes no longer cascade |
| uvicorn | `timeout_keep_alive=120` (was 5s default) | Connections live 24× longer = 24× fewer close events |
| DualShock | `_poll_frames` timeout 4× → 10× interval | Tolerates real USB hiccups (1-3s) without retry pressure cascade |

Both timeout values are env-overridable: `UVICORN_TIMEOUT_KEEP_ALIVE_S=120`
and `DUALSHOCK_POLL_TIMEOUT_MULTIPLIER=10`.

**Empirical verification**: Burst-test of 11 sustained `/health` calls all
returned `{"status":"ok"}` in <1s each. Bridge survived without zombie.
Activation log returned 2 rows correctly under load.

**Operational impact**: Without WIF-062 closure, watchdog hits 3-restart-per-hour
ceiling regularly during frontend testing or sustained shadow-data accumulation
operations → operator must manually intervene every ~hour. With closure,
expectation is 30+ min sustained operation without zombie. Phase O1 D's
≥3-week shadow data accumulation requirement is now feasible without
constant babysitting.

**Cross-references**:
- Commit `dfbbb048` — atomic 3-layer fix + 6 tests
- Memory `project_phase_235_stability.md` — closure detail
- `scripts/bridge_watchdog.py` — still recommended as safety net even with this fix
- Watchdog HALT correctness: 3-restart/hour ceiling design correctly halted on
  recurrence; operator-intervention pattern works as intended (no separate WIF)
