# VHR-Live Attempt — Stability Findings (2026-06-05)

## Objective

Fire the first live VHR (Verified Human Replay) proof while the operator plays
NCAA College Football 26 on the bridge-connected DualSense Edge.

## Outcome

**No VHR proof produced.** The bridge could not stay alive long enough (between
~30 seconds and ~3 minutes per restart) for the `SessionAdjudicator` 5-minute
poll cycle to complete a ruling validation and fire `on_session_complete_vhr`.
Multiple stability mitigations narrowed the failure surface but the underlying
recurrent Windows ProactorEventLoop / IoTeX RPC / SQLite scan load remained.

Gameplay records WERE captured to `bridge.db` — they persist regardless of
whether the boundary→adjudication→hook chain fires. The blocked step is
specifically the VHR pipeline trigger, not data capture.

## Configuration changes that DID happen (and remain in place)

### Feature config — keep

- `VHR_HOOK_ENABLED=true` — activates `on_session_complete_vhr` to fire after
  every adjudicated ruling. Was dormant by default.
- `SESSION_GAMER_ADDRESS=0x0Cf36dB57…` — operator/bridge wallet, single-tenant
  dev mapping for Arc 4 consent-manifest lookup.
- `GRIND_TARGET 100 → 200` — re-armed the `SessionBoundaryDetectorAgent` which
  had auto-stopped when GIC chain reached the previous target (chain_length=100
  ≥ grind_target). Without this bump no boundary would ever close; the adjudic-
  ator would never get a session to rule on; the VHR hook would never fire.
- `GAME_PROFILE_ID=ncaa_cfb_26` — explicit profile selection (was implicit).

### New code — keep

- `bridge/vapi_bridge/operator_api.py` — `GET /operator/bridge/grind-chain-status`
  now includes `grind_target` in the response (was missing). Frontend ribbon
  was falling back to a hardcoded `100`; now shows the live target.
- `bridge/vapi_bridge/game_profile.py` — new `COD_WARZONE` GameProfile
  registered. Switchable via `GAME_PROFILE_ID=cod_warzone` + bridge restart.
  Tuned with L2-ADS L6-Passive (vs NCAA's R2-sprint) and Warzone button
  semantics.
- `frontend/src/api/mockBridge.js` — `grind_target` fallback bumped 100 → 200
  to match the live config.

### Stability mitigations — keep (cheap to retain, useful for next session)

These three were disabled and stay disabled. They are absorbed by the operator-
initiative stewards in the steady-state architecture (Phase 235.x-STABILITY-9
stages 4c/4d/4e), so disabling the standalone agents costs nothing — the
stewards still tick them via their polling loops.

- `PROTOCOL_INTELLIGENCE_ENABLED=false`
- `GAMER_READINESS_ENABLED=false`
- `CONTROLLER_INTELLIGENCE_ENABLED=false`

### Stability mitigations — REVERTED to operator-fired ON state

These were briefly disabled tonight because each absorbs ~11 specs and ticks
them every 30s, which was the dominant contributor to executor saturation.
Reverting because the Phase O1-D-PATH-B v2 executor autoloop depends on them
in steady state.

- `OPERATOR_AGENT_SENTRY_POLLING_ENABLED=true` (restored)
- `OPERATOR_AGENT_GUARDIAN_POLLING_ENABLED=true` (restored)
- `OPERATOR_AGENT_CURATOR_POLLING_ENABLED=true` (restored)

## Root-cause analysis

The repeating crash pattern across ~7 bridge restarts:

```
T+0s     bridge starts; ~50+ background tasks spawn
T+10-90s LOOP STARVATION warnings begin (loop_health_monitor catches
         3-6s of synchronous work blocking the event loop)
T+30-90s starvations cascade; /health stops responding to watchdog polls
T+120s   watchdog records 3 consecutive UNRESPONSIVE → kills + respawns
```

### Documented contributors (from log evidence)

1. **Operator-steward absorbed-spec ticking** — three polling loops (Sentry,
   Guardian, Curator) each tick ~11 absorbed specs every 30 seconds, including
   `spec_ProtocolIntelligenceAgent` (~1.8s blocking) and `spec_ChainReconciler`
   (~5.9s blocking, dominated by slow IoTeX RPC). Cumulative absorbed-spec
   load is the largest single contributor.

2. **IoTeX RPC blocking** — `ChainReconciler` and `watch_manufacturer_revocations`
   poll `eth_getLogs` / `block_number` against IoTeX testnet RPC every 30s.
   Empirical RPC latency seen: 2.7s `block_number`, 3.0s `get_logs` range,
   intermittent `range exceeds the limit` errors forcing retry. These calls
   run on the shared event-loop executor pool; under load they queue behind
   other to_thread work and effectively block the loop while waiting.

3. **InsightSynthesizer Mode 6 startup compute** — recomputes L4 anomaly +
   continuity thresholds at boot (one-time, but blocking, ~hundreds of ms
   on real corpus). Compounds with the steady-state load during the
   stabilization window after each restart.

4. **MLGA / GIC-BETA / HONESTY-BOARD / CDRR-DAG / drift-sweeper trackers**
   — six trackers polling at 30-60s intervals. Each individually is small but
   six on the same executor compound.

5. **Windows ProactorEventLoop** — `OSError WinError 64` ("The specified
   network name is no longer available") observed in `asyncio.windows_events`
   when HTTP accept loops drop a connection mid-flight. Documented in
   CLAUDE.md memory `project_stability_proof_negative_finding` as REFUTED
   for being a sole cause, but it is empirically a co-contributor under
   sustained load on this machine.

### Why my mitigations weren't enough

Disabling individual standalone agents (`PROTOCOL_INTELLIGENCE_ENABLED=false`
etc.) **did not stop the absorbed-spec versions** — the steward polling loops
invoke the same specs through a separate code path. Per CLAUDE.md memory
`project_phase_235_stability_5_shipped` and the absorbed-agents design intent,
absorption is the optimization; the env flags only gate the standalone task
spawn, not the spec function itself.

Disabling the three polling loops (the deeper mitigation) did help — bridge
survived ~3.5 minutes instead of ~1 minute — but `SessionAdjudicator` polls
every 300 seconds (5 minutes). The bridge structurally needs MORE survival
time than the mitigations buy, and the disable also broke the operator-
initiative work the user relies on in steady state.

## Recommended next-session plan

In priority order. Steps 1-3 are pre-attempt work; step 4 is the live retry.

### 1. Code fix — chain RPC offload

Audit `bridge/vapi_bridge/chain.py` for IoTeX RPC calls that aren't yet
wrapped in `asyncio.to_thread` or a dedicated chain-read thread pool. Suspects:

- `watch_manufacturer_revocations` (30s poll)
- `ChainReconciler._reconcile_cycle` (the `chain_block_number` + `chain_get_logs`
  calls already STAGE-9 governed but evidence shows they're still blocking under
  load — the semaphore may not be sufficient when the executor is already
  saturated)
- `chain.get_phg_checkpoint_events_sync` (the `range exceeds the limit` source)

Consider a dedicated `chain_read_pool = ThreadPoolExecutor(max_workers=4)` so
chain RPCs don't queue behind unrelated to_thread work.

### 2. Code fix — SQLite scan audit

`store.get_validation_summary`, `store.get_grind_chain_status`, and similar
helpers are wrapped in `asyncio.to_thread` at the endpoint layer, but
`session_adjudicator_validator` and the absorbed specs likely call them
inline. Grep for `store.*(_sync|get_)` invocations from `async def` bodies
without `to_thread` wrappers.

### 3. Empirical bisection

Use the existing Phase 235.x-STABILITY-9-BISECT instrument
(`bridge/vapi_bridge/config.py:319-354`) to localize which task batch starves
the loop most. Pattern: set `MINIMAL_TASK_MODE=true` + `BISECT_BATCH=Bn` in
`bridge/.env`, restart bridge, observe for 10-12 minutes, record per-minute
STARVATION counts. Batches:

- `B1` SQLite-heavy compute (InsightSynthesizer + FleetSignalCoherence + DataCurator)
- `B2` Polling stewards (Sentry + Guardian + Curator + absorbed-agent tickers)
- `B3` MLGA trackers (mlga_session + gic_ledger_beta + honesty_board + cdrr_dag + ...)
- `B4` Chain-side agents (ChainReconciler + watch_manufacturer_revocations + VHPRenewal)

Expected: `B4` will dominate. If `B2` is comparable, the polling-loop steward
absorb pattern itself needs revisiting.

### 4. Live VHR retry

After steps 1-3 land, set the bridge running in normal config (all of tonight's
env mitigations stay in place per "keep" lists above), play continuously for
10+ minutes, and watch for `PROOF_BUILT` in the bridge log. If the bridge
survives the SessionAdjudicator 5-minute poll cycle, VHR should fire on the
next session boundary closure — assuming the Arc 4 consent manifest gate is
also configured (`VAPIConsentManifestRegistry.setConsentManifest(allow
ReplayProofs=true)` from `SESSION_GAMER_ADDRESS`'s wallet, which is operator-
fired and was NOT done tonight). If consent manifest is unset, outcome will be
`vhr_deferred_no_consent` — honest no-op, no fabricated proof, but the
pipeline will visibly run.

## Environmental notes

- Bridge venv: `bridge/.venv` (Python 3.13, web3/fastapi/hidapi/pydualsense/
  cryptography/quantcrypt/pyjwt installed). The user's previous Python
  environment had been hijacked by `hermes-agent` PATH entries; those have
  been stripped from the persistent User PATH.
- Three deps were missing from `bridge/requirements.txt`: `pyjwt`, `hidapi`,
  `pydualsense`. These should be added to the requirements file in a separate
  hygiene commit so fresh clones don't repeat tonight's install sequence.
- The `hermes-agent` install at `C:\Users\Contr\AppData\Local\hermes\` is
  still on disk (~3GB, contains memories/sessions/skills). PATH hijack is
  resolved; full directory removal pending operator decision.

## Files modified or created tonight

```
bridge/.env                                  edited
bridge/vapi_bridge/operator_api.py           edited (grind_target in response)
bridge/vapi_bridge/game_profile.py           edited (COD_WARZONE profile)
frontend/src/api/mockBridge.js               edited (grind_target 100→200)
docs/2026-06-05-vhr-attempt-stability-findings.md   NEW (this file)
```

Honesty rails preserved throughout: no FROZEN-v1 family edits, no PV-CI invariant
change, no contract deployment, no wallet activity, `CHAIN_SUBMISSION_PAUSED=true`
held the entire session.
