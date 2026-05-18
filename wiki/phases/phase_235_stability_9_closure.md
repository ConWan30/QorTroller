# Phase 235.x-STABILITY-9 EMPIRICAL CLOSURE — 2026-05-18

**Status**: SHIPPED — PARTIAL CLOSURE accepted as engineering trade-off.
**Final residual**: 14.22s STARVATION peak (down from 49.73s baseline; −71%).
**Operational posture**: bridge partner-deployable; /health steady at 0.22s p50; watchdog containment of residual; CHAIN_SUBMISSION_PAUSED=true held throughout.
**Wallet impact**: 0 IOTX across entire arc.
**PV-CI**: 128/128 PASS throughout (zero invariant churn).

---

## Arc Summary

The longest engineering arc in VAPI/Qorsense protocol history: **14 stages of incremental hardening + 9 bisection cycles + 41 agents individually verified clean + structural finding documented**. Began 2026-05-17 with `d7c15a2b` Stage 0 instrument; closed 2026-05-18 with `756eb36a` Stage 14 sync get_logs offload.

The load-bearing question: **why does the bridge's event loop block for 45-50 seconds at boot+1:57 wave-window despite Stages 1-12 progressive hardening?** After 9 bisection cycles isolating ProactiveMonitor surveillance as the primary offender, Stage 13 + Stage 14 reduced the peak by 71% but revealed a structural Windows ProactorEventLoop + AsyncHTTPProvider cancellation gap that requires per-method sync companion engineering to fully close. Marginal returns crossed at Stage 14 (10% improvement); accepted-debt closure shipped.

---

## Cumulative Empirical Trajectory

| Stage | Date | Peak | Count | Wave | Key change |
|---|---|---|---|---|---|
| Pre-S5 baseline | 2026-05-17 13:25 | **49.73s** | 66 | 7.5 min | Original starvation wave |
| Stage 5 (jitter) | 2026-05-17 | ~49s | ~60 | ~7 min | Random first-fire spread |
| Stages 6-7 (instrument) | 2026-05-17 | ~52s | ~65 | ~7 min | loop_timing + curator instrument |
| Stage 8 (chain SQLite to_thread) | 2026-05-17 | 54.18s | 67 | 7 min | SLOW SQLITE cleared |
| Stage 9 (ChainReadGovernor) | 2026-05-17 | 54.16s | 66 | 6 min | TTL cache + semaphore + timeout |
| Stage 10 (BootCohortScheduler) | 2026-05-17 | 49.75s | 62 | 6 min | Deterministic slot spread |
| Stage 11 (trigger-source to_thread) | 2026-05-17 | 53.21s | 65 | 8.5 min | Stewards' trigger sources offloaded |
| Stage 12 (sync_w3 block_number) | 2026-05-17 | 45.62s | 59 | 5.5 min | Windows ProactorEventLoop gap closed for block_number |
| **BISECT B1-B5_PMONITOR** | 2026-05-17→18 | — | — | — | **41 agents individually verified clean; ProactiveMonitor isolated as sole 50s offender** |
| Stage 13 (ProactiveMonitor surveillance to_thread) | 2026-05-18 | **15.86s** | 66 | 7.5 min | NCD pairwise distance compute offloaded; primary fix |
| Stage 14 (sync get_logs offload) | 2026-05-18 | **14.22s** | 70 | 10 min | get_phg_checkpoint_events sync_fn path; STAGE-9 TIMEOUT 5→1 |
| **CLOSURE** | 2026-05-18 | **14.22s** | 70 | 10 min | **Accepted-debt with structural finding documented** |

**Cumulative peak reduction: 49.73s → 14.22s = −71% across 14 stages.**

---

## The 9-Cycle Bisection — Empirical Isolation Methodology

After Stages 5-12 failed to close the residual peak, BISECT mode was activated (commit `d7c15a2b` Stage 9-v0 instrument): MINIMAL_TASK_MODE=true parks all ~50 background agents leaving only uvicorn + loop_health_monitor. Sequential per-batch re-enablement isolated the offender.

| Cycle | Batch | Agents | Result |
|---|---|---|---|
| BISECT-1 | MINIMAL only | uvicorn + loop_health | 0 STARVATION (control baseline) |
| B1 | InsightSynth + FSCA + CorpusCurator | 3 | CLEAN |
| B2 | 3 stewards + 9 absorbed (incl ChainReconciler) | 12 | CLEAN |
| B3 | 4 MLGA trackers | 4 | CLEAN |
| B4 | chain.watch_revocations + PoAdAnchor + LiveWriteExecutor | 3 | CLEAN |
| B5_ALL | Full production fall-through | All | **FIRES 65/48.96s** (RETAIN set offender confirmed) |
| B5A | AlertRouter + CalibrationIntelligenceAgent | 2 | CLEAN |
| B5B | DataCurator + SessionAdjudicator + 4 more | 6 | CLEAN |
| B5C | SeparationRatioMonitor + 7 more | 8 | CLEAN |
| B5D | batcher + cedar_drift_sweeper + cfss + LiveModeActivationAgent | 2 (effective) | CLEAN |
| **B5_PMONITOR** | **ProactiveMonitor + full dep tree (sole spawn)** | 1 | **FIRES 11/49.67s** ⚡ ROOT CAUSE FOUND |

**41 agents verified clean.** ProactiveMonitor isolated as primary offender with peak match within ±3% of full-production baseline (49.67s vs 48.96s). First STARVATION at boot+1:54 = exactly 54s into ProactiveMonitor's first 60s poll cycle.

---

## Root Cause Synthesis

### Primary blocker (Stage 13 fix)

`ProactiveMonitor._check_anomaly_clusters` called `network_correlation_detector.detect_clusters()` synchronously on the event-loop thread. The method invokes `build_distance_matrix(device_ids)` which is a doubly-nested O(N²) loop computing `prover.compute_distance(...)` for every device pair — Normalized Compression Distance over zlib-compressed behavioral fingerprints. For N=100 devices: 4,950 compression-based compute calls. Then DBSCAN on top. ~50-second block on event loop.

**Stage 13 patch**: wrap `detect_clusters()` + `get_high_risk_devices()` + `analyze_device()` + `get_leaderboard()` in `asyncio.to_thread`. Peak 49.67s → 15.86s (−68%).

### Secondary blocker (Stage 14 fix)

After Stage 13, residual 15.86s peak clustered at exactly **10s governor wait_for timeout + ~5.86s socket-cancellation residual** — exact Windows ProactorEventLoop signature on AsyncWeb3 event-filter `get_logs()` reads. The async path through `AsyncHTTPProvider` does not propagate `asyncio.CancelledError` cleanly when the socket is mid-`WSARecv` — `asyncio.wait_for` returns at the configured timeout but the underlying socket continues blocking for ~5s additional until OS-level read completion. Same structural issue Stage 12 addressed for `block_number`; Stage 14 addresses for `get_logs`.

**Stage 14 patch**: add `get_phg_checkpoint_events_sync()` via `self._sync_w3`; extend `ChainReadGovernor.run_read()` with optional `sync_fn` parameter; route through `asyncio.to_thread(sync_fn)` when provided. STAGE-9 governor TIMEOUT dropped 5 → 1 (−80%). Peak 15.86s → 14.22s (−10% marginal).

### Tertiary blocker (accepted-debt)

After Stage 14, remaining 14.22s peak cluster at 10-15s indicates **additional async chain read sites** still using AsyncHTTPProvider:

- `chain.watch_manufacturer_revocations()` — `event_filter().get_logs(...)` (chain.py:1581); different call site than chain_reconciler
- `chain.is_adjudication_recorded()` — async view call from Curator's AnchorFreshnessTriggerSource
- `chain.is_consent_valid()`, `chain.is_certified()`, etc. — other async view calls

Each could be wrapped via the Stage 14 pattern (sync companion + `asyncio.to_thread`). However, marginal returns analysis at Stage 14 (only −10% improvement vs Stage 13's −68%) suggests per-method sync companion engineering will continue yielding diminishing returns. **Accepted-debt closure shipped** with the pattern documented for future Stage 15+ work if operationally required.

---

## Structural Finding for Long-Term Reference

**Windows ProactorEventLoop + AsyncHTTPProvider Cancellation Gap (WIF-067 candidate)**

When AsyncWeb3 reads (block_number, get_logs, contract view calls) execute against IoTeX RPC over a stalled TCP connection on Windows ProactorEventLoop, `asyncio.wait_for(coro, timeout=N)` returns at the N-second timeout BUT the underlying socket `WSARecv` IOCP completion continues blocking the event loop thread for an additional ~5-15 seconds until the OS reports the read completion (success, error, or TCP-keepalive death).

**Mitigation pattern**: Construct a sync `Web3(HTTPProvider(...))` companion alongside the async client. Route the read through `asyncio.to_thread(lambda: sync_w3.eth.<method>(...))`. The blocking socket lives on a ThreadPoolExecutor worker where Windows ProactorEventLoop cancellation behavior is irrelevant; the event loop heartbeat stays healthy. Apply per-method as needed.

**Forward-looking resolution**: Linux deployment OR AsyncWeb3 upgrade with proper async cancellation handling would address the structural root cause more cleanly than per-method sync companions. Bridge target deployment for partner integration should consider Linux-host preference for production.

---

## Durable Improvements Shipped

### 4 New Bridge Modules

| File | Purpose | Stage |
|---|---|---|
| `bridge/vapi_bridge/startup_grace.py` | Random startup jitter + Stage 10 BootCohortScheduler integration | 5/10 |
| `bridge/vapi_bridge/loop_timing.py` | Generic `timed_block()` contextmanager for STAGE-N instrumentation | 7 |
| `bridge/vapi_bridge/chain_read_governor.py` | TTL block_number cache + asyncio.Semaphore + timeout + sync_fn offload (Stage 14) | 9/12/14 |
| `bridge/vapi_bridge/boot_cohort_scheduler.py` | Deterministic boot-cohort slot scheduler | 10 |

### Per-Stage Patches Across Existing Bridge Modules

- `fleet_signal_coherence_agent.py` (Stage 1 subprocess.run + Stage 4 promote_to_wif to_thread)
- `corpus_curator_agent.py` (Stage 2 task body to_thread restructure)
- `chain_reconciler.py` (Stage 8 SQLite to_thread + Stage 9 governor + Stage 12 sync_w3 + Stage 14 sync_fn)
- `chain.py` (Stage 12 sync_w3 companion + Stage 14 get_phg_checkpoint_events_sync)
- `chain_read_governor.py` (Stage 9 base + Stage 12 sync_w3 + Stage 14 sync_fn)
- `operator_agent_{sentry,guardian,curator}_polling.py` (Stage 11 trigger-source to_thread)
- `proactive_monitor.py` (Stage 13 surveillance to_thread × 4 hotpaths)
- `operator_steward_absorbed_agents.py` (Stage 10 scheduler integration)
- Multiple agent files (Stage 5 startup_grace integration)

### 14 Stage Commits

```
d7c15a2b  Stage 0 instrument (MINIMAL_TASK_MODE bisection)
6d052618  Stage 1 FSCA subprocess.run loop-blocker fix
35176b3f  Stage 2 curator task body restructure
a2767d56  Stage 3 sync work hunt + 3 fixes
e5dd1eb3  Stage 4a rationalization v1
e2b14ce9  Stage 4b event-drive divergence
58f2725b  Stage 4c+4d+4e absorbed agents
0f17543f  Stage 5 startup-jitter
5bb9a7c4  Stage 6 curator readiness starvation instrument
0d121ec1  Stage 7 first-fire cohort timing instrument
25664a3d  Stage 8 ChainReconciler reconcile off event loop
3924df5a  Stage 9 chain RPC read governor
fdada30d  Stage 10 deterministic boot-cohort slot scheduler
185d5a84  Stage 11 trigger-source asyncio.to_thread
05e2a149  Stage 12 sync-Web3 chain-read offload
cf1e64de  Stage 13 ProactiveMonitor surveillance to_thread
756eb36a  Stage 14 sync get_logs offload (LAST STAGE)
```

### Test Coverage Growth

Bridge tests **4191 → 4330 (+139)** across STABILITY-9 arc + BISECT instrument. PV-CI 128/128 PASS preserved throughout. 5,548-test full CI suite unchanged (no SDK/Hardhat/Vitest churn).

---

## Operational Posture at Closure

- `CHAIN_SUBMISSION_PAUSED=true` held in `bridge/.env` throughout (kill-switch as 4th-defense layer)
- Wallet 0 IOTX impact across entire arc (no on-chain operations)
- PV-CI 128/128 PASS unchanged (zero invariant churn)
- Zero FROZEN-v1 primitive edits (PoAC wire format, GIC chain, WEC, VAME, CORPUS-SNAPSHOT, CONSENT, BIOMETRIC-SNAPSHOT, LISTING, FRR, ZKBA, POSEIDON-AS, VAPI-O3-SUPERSEDE all byte-identical)
- Zero contract/SDK/Hardhat/Vitest changes
- All stages Q1-reactivatable via single env-flag revert (MINIMAL_TASK_MODE=true + restart returns to bisection baseline)
- /health steady-state p50=0.22s / p95=0.27s — bridge serves traffic cleanly outside the boot wave throughout the arc
- Watchdog containment unchanged (Phase 236-WATCHDOG); 3 restarts/hr ceiling provides additional safety layer

---

## Downstream Unblock

**QRESCE-0001 R1 plan-doc commit unlocked.** STABILITY-9 has reached terminal state (partial closure documented). Per `qresce-0001-v0.4-brand-amendment.md §6` dependency banner: R1 commit gates on R0 certificate AND STABILITY-9 terminal state. This phase note closes the second gate. R0 prerequisites (trademark + domain + pronunciation + GitHub slot) remain operator-side work — R0 certificate signature is the final unblock.

---

## Stage 15+ Reservation

If operational stress surfaces the 14s residual as load-bearing (partner deployment, tournament-day stress), Stage 15+ work is well-scoped:

- Audit `bridge/vapi_bridge/chain.py` async methods touching `event_filter().get_logs()` or async view calls
- Add sync companions via `self._sync_w3` (mirror Stage 14 pattern)
- Route through `ChainReadGovernor.run_read(sync_fn=...)` or direct `asyncio.to_thread`
- Hotpath candidates: `watch_manufacturer_revocations`, `is_adjudication_recorded`, `is_consent_valid`, `is_certified`, `get_agent_scope_root`

Estimated 5-8 sync companions × ~30 LOC each + symmetric tests = 1-2 cycles to close peak below 5s. Alternatively, Linux deployment OR AsyncWeb3 upgrade with proper cancellation handling addresses the structural root cause without per-method sync companions.

---

*End STABILITY-9 EMPIRICAL CLOSURE. 14 stages + 9 bisection cycles + 41 agents verified + structural Windows ProactorEventLoop finding documented + 4 durable bridge modules shipped + 139 new bridge tests + 0 IOTX wallet impact + 0 FROZEN-v1 primitive edits + PV-CI 128/128 PASS preserved. Bridge partner-deployable at 14s residual; /health steady at 0.22s p50.*
