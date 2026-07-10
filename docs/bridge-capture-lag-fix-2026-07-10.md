# Bridge Event-Loop Starvation / Capture-Lag Fix

**Status:** FIX DESIGN ONLY (2026-07-10). High-risk arc — mutual audit before build.  
**Unlocks:** live dense-candidate path can promote (authored>0) when capture is not fps-floored.  
**Does not:** retune K=3 authorship gates, prune FROZEN/biometric/records, touch PoAC/chain.  
**Rails:** never break fleet/data · flag default-OFF · off-loop work only · measured bar · PV-CI 182.

---

## 1. Claim / scope

**Attribute and relieve asyncio event-loop starvation during live presence capture so Remote Play capture `ema_fps` stays near a playable floor (~30+) and loop-starvation excess stays under the existing 1.0s threshold — by (1) identifying the top sync offenders, then (2) offloading and/or capture-priority deferral of non-essential work — without dropping fleet data integrity or changing authorship/crypto surfaces.**

| In scope | Out of scope |
|----------|----------------|
| Diagnostic attribution + offload / capture-priority | DB prune of records/biometrics/FROZEN |
| Config flags, timed instrumentation, tests | Lowering dense K / promote_floor |
| Measurable fps + starvation bar | Mainnet / IOTX / PoAC |

---

## 2. Symptom + root grounding (do not re-derive)

### 2.1 Measured this session (`densecand_validate`)

| Signal | Value |
|--------|--------|
| `loop_health_monitor` | 41× **LOOP STARVATION**; worst sleep expected 2.0s → actual **5.16s** (excess **3.16s**) |
| RGC governor | `ema_fps≈13`, flags `fps_floor_reached`, `unsteady_fps`, downscale→8 |
| Dense-candidate | Mechanism OK (progress + stall-recut) but late bootstrap (~9.5 min) → authored=0 |
| Contrast | M14 same RP class **~38 fps** when ambient load lower |

### 2.2 Prior findings (authoritative)

| Source | Conclusion |
|--------|------------|
| `project_retina_phase0_live_starvation_finding` | Ambient floor = agent-fleet inline DB + large DB; retina is **victim**; “S5 offload+prune = path to bar” |
| `project_remote_play_presence_lean_ondemand` | **bridge-down = perfect**; `PRESENCE_LEAN_MODE` helps, not always enough |
| Phase 235-EVENTLOOP (CLAUDE.md) | Sync >5ms → `to_thread`/`executor`; high-cardinality tables indexed |
| Dense-candidate live log | Authorship **promotion logic** no longer the freeze wall; **lag is** |

### 2.3 Existing machinery (build on it)

| Piece | Role |
|-------|------|
| `loop_health_monitor.py` | Detects starvation (sleep delay); does **not** name the blocker |
| `loop_timing.timed_block` | Per-site SLOW DB / SLOW TASK warnings (curator, ACIM, PIA, stewards, …) |
| `PRESENCE_LEAN_MODE` | Skips ~30-agent fleet + grind + PCC + heavy provenance at main startup (`main.py` ~L1247–1259) |
| `MINIMAL_TASK_MODE` / boot cohorts | Further boot isolation (config) |
| RGC `AdaptiveCaptureGovernor` | Reacts to lag (downscale/region) — **symptom mitigation**, not root fix |
| `records` indexes | `idx_records_status/device/created_at/inference_ts/device_created` already in `store/_core.py` |

---

## 3. Diagnostic mechanism (pin offenders before surgery)

### 3.1 Goal

On each starvation window, attribute **top 2–3 sync sources** with enough confidence to offload or defer them — not guess.

### 3.2 Increment D1 — capture-session attribution (flag-gated)

| Component | Spec |
|-----------|------|
| Flag | `LOOP_STARVATION_ATTRIBUTION_ENABLED` default **OFF** |
| Ring | Process-global or module ring of last N `timed_block` exits: `{label, dur_s, tid, wall_ns, thread}` |
| On starvation | In `run_loop_health_monitor` WARNING path: dump top-K ring entries by `dur_s` in last `check_interval + excess` window + optional stack sample |
| Stack sample (optional sub-flag) | `LOOP_STARVATION_STACK_SAMPLE=1`: `sys._current_frames()` for main thread only, log top frames (no PII); default OFF (noise + cost) |
| Capture linkage | When RGC active / `CAPTURE_PRIORITY` armed, also log RGC `ema_fps` + governor flags on the same WARNING line |

**Do not** sample stacks on every loop iteration — only on starvation events.

### 3.3 Increment D2 — lean-mode honesty in diag

If starvation occurs while `presence_lean_mode=True`, log that fact explicitly (lean is not a full free pass: DualShock + retina + batcher + remaining HTTP/sync can still block). If lean is **False** during a “capture” session, that is finding #0: **wrong operational posture**.

### 3.4 Exit criterion for D1

Before F1/F2 code changes that alter runtime:

- ≥1 real or reproduced starvation log with **named top offenders** (from timed_block ring and/or stack).  
- Documented shortlist (expected candidates, not pre-convictions): remaining non-lean agents if lean off; SQLite in dualshock/retina path; batcher/store; FSCA/curator if still scheduled; chain RPC if not lean-skipped.

---

## 4. Chosen levers (justify + order)

### 4.1 Decision summary (D-LAG-*)

| Priority | Lever | Why |
|----------|-------|-----|
| **P0 operational** | Document + enforce **PRESENCE_LEAN_MODE=true** for live RP capture sessions | Already the designed “bridge light” path; free if not used |
| **F1 (code)** | **Capture-priority mode** (new flag) | Reversible; defers non-essential background while capture active; does not delete data |
| **F2 (code)** | **Offload remaining loop-thread sync DB/CPU** via `asyncio.to_thread` | EVENTLOOP-compliant; no semantic data change |
| **F3 (follow-on)** | DB size / prune / archive | High risk; **not this arc** — design note only |

**Recommendation: F1 + F2 together**, after D1 names offenders. F1 yields the loop under capture; F2 fixes EVENTLOOP violations that still run (including on lean path).

### 4.2 F1 — `CAPTURE_PRIORITY_MODE` (name TBD; default OFF)

**Intent:** While a live retina/presence capture is active, **defer or stretch** non-essential agent/fleet poll work so DualShock + RGC own the loop; when capture stops, **resume full cadence** with no dropped durable writes (defer ≠ drop).

| Property | Spec |
|----------|------|
| Flag | `CAPTURE_PRIORITY_MODE` / `RETINA_CAPTURE_PRIORITY` env, default **false** |
| Arm | RGC start / dualshock retina attach sets `app.capture_priority_active=True` (or module atomic) |
| Disarm | `RGC.stop` / capture end → False; fleet resumes |
| Behavior when armed | Background agent `run_poll_loop` iterations: `await asyncio.sleep(extra)` or skip this cycle if `last_run` recent; **no** cancel mid-transaction; **no** delete queues |
| Lean interaction | If `PRESENCE_LEAN_MODE` already skipped fleet at boot, F1 is mostly no-op for those agents — still useful if lean is false or residual tasks remain |
| Reversibility | Disarm restores previous poll intervals; no schema change |

**Never:** drop pending batcher submissions, discard agent rulings, or skip FSCA if operator requires it — FSCA may be “essential”; default defer list = heavy poll agents already known SLOW in timed_block (curator packaging tick, calibration monitor self-tests, protocol intelligence compute) — **final list from D1**.

### 4.3 F2 — Offload sync work (EVENTLOOP compliance)

For each D1 top offender that is **sync on the loop thread**:

```text
# WRONG (blocks loop)
result = store.expensive_query(...)

# RIGHT
result = await asyncio.to_thread(store.expensive_query, ...)
```

| Rule | Spec |
|------|------|
| Threshold | Blocks ≥5ms (CLAUDE.md event_loop_invariants) |
| Pattern | Match batcher / honesty_board already using `to_thread` |
| Tests | Unit: mock store sleep; assert call not on loop thread when awaited from async test |
| Safety | No nested loop; no holding locks across await incorrectly |

### 4.4 F3 — Prune follow-on (explicit non-bundle)

| Allowed later | Forbidden in this arc |
|---------------|------------------------|
| Operator-run backup + archive of old `records` / logs | Auto-prune FROZEN-v1 tables, biometric raw, consent ledgers |
| Verify indexes present (already largely true for records) | “Delete half the DB mid-match” |

Note in decisions table; separate design + backup runbook if pursued.

---

## 5. Success bar (measurable)

| Metric | Pass |
|--------|------|
| RGC `ema_fps` during live RP capture | **≥ 30** steady (not only spikes); not stuck on `fps_floor_reached` |
| `loop_health` excess | **≤ 1.0 s** (existing starvation threshold); starvation event rate near zero over a 10+ min match |
| Authorship path | Dense + session-anchor can bootstrap **early** enough that live authored>0 is **possible** (not guaranteed every match — still needs kills/OCR) |
| Flag off | Byte-identical prior behavior |

Validation = **rig session** with before/after log pair; diagnostic units offline.

---

## 6. Five hard rails

| # | Rail |
|---|------|
| **1** | **Never break fleet or drop data** — throttle/defer/offload only; capture-priority fully reversible at stop |
| **2** | **Flags default-OFF** — attribution, capture-priority, stack sample |
| **3** | **Nothing new on the hot path that blocks** — no sync DB added inline; instrumentation ring is O(1) append |
| **4** | **Measured** — fps + starvation before/after; D1 attribution logs |
| **5** | **No PoAC / FROZEN / chain / prune of integrity tables** — PV-CI 182 |

---

## 7. CODE-TRUTH

| Item | Path |
|------|------|
| Loop health | `bridge/vapi_bridge/loop_health_monitor.py` `run_loop_health_monitor` |
| Config thresholds | `config.py` `loop_health_*` (~L164–189) |
| Timed blocks | `bridge/vapi_bridge/loop_timing.py` `timed_block` |
| Known SLOW sites | `corpus_curator_agent.py`, `agent_calibration_monitor.py`, `protocol_intelligence_agent.py`, `operator_steward_absorbed_agents.py` |
| Lean mode | `main.py` ~L1247–1259; `config.presence_lean_mode` / `PRESENCE_LEAN_MODE` |
| RGC governor / fps | `qortroller_retina_capture.py` AdaptiveCaptureGovernor, `ema_fps`, downscale; diag ~L1572+ |
| Dualshock consumption | `dualshock_integration.py` (retina flush / capture path) |
| Classify burst (already off-loop) | `classify_burst.py`, dualshock spawn ~L907 |
| Records indexes | `store/_core.py` idx_records_* including `idx_records_device_created` |
| Batcher to_thread pattern | `batcher.py` |
| Prior starvation docs | memories / phase notes cited in §2.2 |

---

## 8. Test plan

| ID | Assert |
|----|--------|
| **T1** | Attribution OFF: no ring dump; health monitor log format unchanged except version note |
| **T2** | Attribution ON + synthetic slow `timed_block` during fake sleep delay → WARNING includes that label in top-K |
| **T3** | Capture-priority OFF: agent poll cadence unchanged (mock clock) |
| **T4** | Capture-priority ON: deferred agent skips/sleeps; on disarm, cadence resumes; **no** lost insert when using “defer cycle” not “drop write” |
| **T5** | Offload: async path calls store via `to_thread` (mock) |
| **T6** | Flag matrix byte-identical when all new flags false |
| **T7** | Never-gates: capture-priority does not alter PoAC wire / consent / grind chain APIs |

---

## 9. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-LAG-1** | Attribution method = timed_block ring + optional stack sample on starvation | Yes | ☐ accept ☐ amend |
| **D-LAG-2** | Levers = **both** F1 capture-priority + F2 offload after D1 names offenders | Yes | ☐ accept ☐ amend |
| **D-LAG-3** | Flag `CAPTURE_PRIORITY_MODE` (or `RETINA_CAPTURE_PRIORITY`) default OFF | Yes | ☐ accept ☐ amend |
| **D-LAG-4** | Flag `LOOP_STARVATION_ATTRIBUTION_ENABLED` default OFF | Yes | ☐ accept ☐ amend |
| **D-LAG-5** | Operational: live RP capture uses `PRESENCE_LEAN_MODE=true` | Strongly recommend | ☐ accept ☐ amend |
| **D-LAG-6** | DB prune = **follow-on only**, backup-required, not this PR | Yes | ☐ accept ☐ amend |
| **D-LAG-7** | Success bar: ema_fps ≥ 30 + starvation excess ≤ 1.0s | Yes | ☐ accept ☐ amend |
| **D-LAG-8** | Proceed Claude audit → build D1 first → then F1/F2 → stage | Hold for GO | ☐ GO ☐ hold |

---

## 10. Build sequence (risk control)

```text
1. D1 attribution only (safest) → ship → one capture with attribution ON
2. Read top offenders from logs
3. F2 offload those sites (surgical)
4. F1 capture-priority if residual starvation remains under lean+offload
5. Rig validation against §5 bar
6. Prune arc separately if DB size still dominates I/O after offload
```

Do **not** land F1+F2+prune in one commit.

---

## 11. Relationship to authorship arcs

| Arc | Role |
|-----|------|
| Dense-candidate | Mechanism fixed; needs fps |
| Deferred window-pad | Offline authored without live fps |
| **This arc** | Live fps so dense path can finish promote in-match |
| LUMEN-2b match-state | Independent advisory |

Operator can keep using deferred for verifiable authored while this lands.

---

## 12. Honest limits

1. OS scheduling / GPU / other processes can still starve — we only fix **our** loop blockers.  
2. ema_fps ≥ 30 is a **capture health** bar, not a guarantee of authored>0 every match.  
3. Lean mode trades fleet features for capture quality — by design.  
4. Stack samples can be noisy; timed_block labels are primary attribution.

---

*End of bridge capture-lag fix design v0 — 2026-07-10.*
