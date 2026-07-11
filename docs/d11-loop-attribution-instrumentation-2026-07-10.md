# D1.1 — Instrument Un-Instrumentated Loop-Thread Sync (Gates F2)

**Status:** DESIGN ONLY (2026-07-10). Instrumentation-only; no offload yet.  
**Predecessor:** D1 attribution ring (`loop_timing.timed_block` + dump on LOOP STARVATION).  
**Finding:** `lag_attr_validate` under `LOOP_STARVATION_ATTRIBUTION_ENABLED=1` + `PRESENCE_LEAN_MODE=true` → 18 starvation events, **every dump empty** (`NO timed_block entries`, lean_mode=True). Fleet instrumented sites are ruled out. Offender is **un-instrumented** sync on the asyncio loop in the lean residual path.  
**Rails:** flag-gated / byte-identical when attribution off · no behavior change · no FROZEN/PoAC/chain · PV-CI 182 · 0 IOTX.

**Reframe:** live authored>0 can land via off-loop dense path despite lag; D1.1/F2 are about **fps/density/bridge health**, not the sole authorship blocker.

---

## 1. Claim / scope

**Wrap the residual lean-mode loop-thread sync call sites (DualShock session loop, store reads/writes still on the loop, batcher/chain views if still scheduled) in the existing `timed_block` attribution ring so the next capture names the exact offender — without offloading, throttling, or changing data semantics.**

| In scope | Out of scope |
|----------|----------------|
| `timed_block` wraps + optional loop-tid filter on dump | F2 `asyncio.to_thread` (follow-on design after names) |
| Lean residual path only prioritization | Re-instrumenting already-wrapped fleet agents |
| Tests for ring + filter | Capture-priority mode (F1) |

---

## 2. Why D1 was empty (and why that is progress)

| Fact | Implication |
|------|-------------|
| lean_mode=True | Agent fleet (curator / ACIM / PIA / stewards / chain_reconciler timed sites) **not running** |
| Empty ring every starvation | Blocker is **not** those labels — it is unwrapped sync or non-Python delay |
| Residual under lean | DualShock + retina + whatever main still starts (loop_health, batcher?, HTTP) + SQLite WAL |

D1.1 instruments the residual; F2 offloads what D1.1 names.

---

## 3. Candidate sites (rank → wrap)

Rank by (a) known to run under lean, (b) likely on **event-loop thread**, (c) SQLite/RPC/sync.

| Priority | Site | Path / notes | Label suggestion |
|----------|------|--------------|------------------|
| **P0** | DualShock session-loop **store reads** still sync | e.g. `get_detection_policy` ~L1957, `get_ioid_device`, calibration profile reads | `ds.store.get_detection_policy` etc. |
| **P0** | DualShock **store writes** still sync on loop | `upsert_device`, `insert_usb_reconnect_log`, `insert_l6b_*`, `store_cognitive_embedding`, `store_frame_checkpoint`, `store_pitl_proof` — wrap each or a shared `_store_sync(label, fn, *a)` helper | `ds.store.<method>` |
| **P0** | Consumption tick retina cluster | `flush_stale_inline_window` + `tick_match_state` ~L1803–1804 | `retina.flush_stale+tick_match` |
| **P1** | `mark_r2_onset` / `maybe_classify` scheduling | if any sync body remains on loop | `retina.mark_r2_onset` |
| **P1** | Batcher poll if still scheduled under lean | `batcher.py` — some paths already `to_thread`; wrap any residual loop-thread store | `batcher.get_pending` |
| **P1** | Chain view calls on loop | `chain.py` / dualshock chain reads if any not already executor | `chain.<view>` |
| **P2** | Session-loop body slices | Coarse wrap of large sync segments between awaits in `_session_loop` as umbrella labels | `ds.session_loop.segment_N` (temporary if needed) |

**Prune:** Do not re-wrap fleet agents already under STAGE-7 timed_block. Do not wrap pure async `await asyncio.sleep` / `await to_thread` bodies (that would mis-attribute worker time as loop time — see §4).

**Implementation pattern (no behavior change):**

```python
from .loop_timing import timed_block
with timed_block("ds.store.get_detection_policy", warn_s=0.005, logger=log,
                 prefix="[LEAN-RESIDUAL]", hint="loop-thread SQLite"):
    _policy = self._store.get_detection_policy(...)
```

Use **warn_s=0.005** (5 ms EVENTLOOP bar) so sub-threshold calls still enter the attribution ring (ring records **every** timed_block exit when attribution is ON — already true in `timed_block` finally). WARNINGS stay quiet under threshold.

---

## 4. Loop-thread tid filter (recommended)

Worker threads (qt-dense-cand, classify-burst, HID) can also call instrumented code later; their blocks **do not starve the asyncio loop**.

| Change | Spec |
|--------|------|
| Capture loop tid | At bridge start / first monitor iter: `loop_tid = threading.get_ident()` on the loop thread (store on cfg or module set by `run_loop_health_monitor` first line) |
| `top_blocks` filter | Optional `loop_tid_only: int | None` — when set, drop ring entries with `tid != loop_tid` |
| Dump line | Log `loop_tid=N` + `n_dropped_worker_tid=M` for honesty |

**Default when attribution ON:** filter to loop tid if known; if unknown, dump all (today’s behavior) + note.

---

## 5. Rails

| # | Rail |
|---|------|
| 1 | **Instrumentation only** — no to_thread, no throttle, no drop |
| 2 | Attribution still gated by `LOOP_STARVATION_ATTRIBUTION_ENABLED` (default OFF) → byte-identical when off |
| 3 | timed_block fail-passthrough — never swallow store errors |
| 4 | No FROZEN / PoAC / chain writes; PV-CI 182 |
| 5 | Prefer lean residual path; do not re-open fleet instrumentation as P0 |

---

## 6. CODE-TRUTH

| Item | Path |
|------|------|
| Ring + `timed_block` | `bridge/vapi_bridge/loop_timing.py` |
| Dump on starvation | `bridge/vapi_bridge/loop_health_monitor.py` ~L90–111 |
| Lean skip fleet | `bridge/vapi_bridge/main.py` ~L1247–1259 |
| Consumption tick | `dualshock_integration.py` ~L1803–1804 |
| Store call sites | `dualshock_integration.py` (grep `self._store.`) |
| Batcher to_thread pattern | `batcher.py` |
| D1 design | `docs/bridge-capture-lag-fix-2026-07-10.md` |

---

## 7. Test plan

| ID | Assert |
|----|--------|
| T1 | Attribution OFF: no new labels required; existing D1 tests still pass |
| T2 | Wrap a synthetic sync fn on “loop” tid → starvation dump names that label |
| T3 | Worker-tid entry excluded when loop_tid filter ON |
| T4 | Store wrapper: exception from store still propagates |
| T5 | warn_s low: short calls still appear in ring when attribution ON |

---

## 8. Operator decisions

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-D11-1** | Instrument P0 dualshock store + retina flush/tick first | Yes | ☐ accept ☐ amend |
| **D-D11-2** | Loop-tid filter on dump when loop tid known | Yes | ☐ accept ☐ amend |
| **D-D11-3** | No F2 in this PR | Yes | ☐ accept ☐ amend |
| **D-D11-4** | Proceed Claude audit → build → stage | Hold for GO | ☐ GO ☐ hold |

---

## 9. Success criterion

Next rig capture with attribution ON + lean ON:

```text
LOOP STARVATION attribution (top N ...): ds.store.X=...; retina.flush...
```

Not `NO timed_block entries`. Then Grok designs **F2** offload for those labels only.

---

*End D1.1 design v0 — 2026-07-10.*
