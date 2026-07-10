# Live Authorship Dense-Candidate Fix (Option 3)

**Status:** FIX DESIGN — audit PASS (Claude); 3 CODE-TRUTH corrections folded below.  
**Not:** a strategy thesis, gate retune, OCR densification, or PoAC change.  
**Rails:** flag-gated default-OFF · no OCR on dense path · no event-loop starvation · K=3/0.66 unchanged · no FROZEN/chain/IOTX · PV-CI 182.

**Bug class:** Live killfeed authorship → `INSUFFICIENT_KILLS` / 0 authored on RP (M18, rp4_rp) while offline archive re-scan finds readable kills. Session anchor freezes in **CANDIDATE**.

---

## 1. Claim / scope

**This fix increases the rate at which the session-anchor state machine receives CANDIDATE observations by scoring the dense panel-crop stream with the candidate template (and independent feed_v1 raw-auth for stalls), without running OCR on that stream, without changing the promotion integrity gate (K=3, promote_floor=0.66, FP demote, stall-recut), and without touching the 228B PoAC wire.**

**In scope:** live path only (`qortroller_retina_capture` + pure `SessionAnchorGenerator` call sites).  
**Out of scope:** deferred/archive KAS (already finds kills), lowering K or floor, OCR densification, EVENT-BIND, chain.

---

## 2. Root cause (pinned)

| Layer | Fact |
|-------|------|
| State machine | `SessionAnchorGenerator`: BOOTSTRAP → CANDIDATE → PROMOTED (`l9_presence/killfeed_session_anchor.py`) |
| Promotion rule | `observe_candidate`: K=`DEFAULT_K_CONSISTENCY=3` hits with `score ≥ DEFAULT_PROMOTE_FLOOR=0.66` on non-background killer-slot geometry |
| Stall-recut | Same function: `raw_killer_authored and not clears` increments stalls; at `stall_limit=3` → demote to BOOTSTRAP for recut |
| Live call site | `_session_anchor_fold` only from classification path (`_inline_classify_worker` → fold), itself driven by **R2-window** `classify_in_window_sync` / maybe_classify |
| Failure mode | CANDIDATE reached (often on codec-noisy cut); few R2 windows (e.g. 19) + loop starvation → almost no `observe_candidate` → zero progress/stall/promote; kills sit in gaps; offline crops still readable |

**Integrity is fine; observation density is not.** Option 3 multiplies **which crops feed the gate**, not the gate.

---

## 3. Design decision — dense path feeds **both** K-progress and stall-recut

### 3.1 The weak-cut subtlety

If the candidate template was cut from a noisy crop, it may **never** reach 0.66. Then K-progress alone cannot promote. The machine already solves this via **stall-recut**: independent evidence of a real kill the candidate missed → demote → BOOTSTRAP → new cut.

Dense scoring’s highest leverage under RP is often **accelerating stall-recut** (replace a bad cut) while still allowing clean K-progress when the cut is good.

### 3.2 Locked choice (D-LAF-1)

| Feed | Dense path does | How (no OCR) |
|------|-----------------|--------------|
| **K-progress** | Yes | `killer_slot_best(bgr, candidate_template)` → `observe_candidate(score=…, raw_killer_authored=False)` when clears |
| **Stall** | Yes | Independent **feed_v1 / bootstrap static template** score ≥ `promote_floor` on same crop while candidate sub-floor → `raw_killer_authored=True` (same semantics as AUTHORED_PRESENT without OCR) |

**OCR remains demote-only and R2/bootstrap-gated** — never called from the dense path (preserves D-CG-1 posture; cost stays off dense stream).

---

## 4. Exact hook + call graph

### 4.1 Pure core (no I/O)

New helper (location preference: method on `RetinaGameCapture` or small pure function in same module):

```text
_dense_candidate_observe(self, bgr, now_ms) -> Optional[dict]
  # Precondition: gen.regime == CANDIDATE (else return None immediately)
  # 1. active = gen.active_anchor(); if None: return
  # 2. kscore, kxf, kyf = killer_slot_best(bgr, active)
  # 3. fresh = self._dense_killer_fresh_row(bgr, now_ms)   # OWN state — see C3
  # 4. is_bg = (now_ms - self._dense_last_killer_fresh_ms) > _SESSION_ANCHOR_ROW_PERSIST_MS
  # 5. raw_auth = False
  #    feed_score, _, _ = killer_slot_best(bgr, self._anchor)  # bootstrap feed_v1 template
  #    if feed_score >= gen.promote_floor and not is_bg: raw_auth = True
  #    # NOT: _ocr_bootstrap_read  — FORBIDDEN on this path
  # 6. with self._inline_admission_lock:   # C1 — correct lock name
  #      return gen.observe_candidate(score=kscore, x_frac=kxf, y_frac=kyf,
  #          is_background=is_bg, now_ms=now_ms, raw_killer_authored=raw_auth)
  # 7. log same transition events as fold (promoted / stall / demote / progress)
```

**Do not** call `_session_anchor_fold` wholesale — it embeds BOOTSTRAP OCR. Dense path is CANDIDATE-only subset.

### 4.2 Call sites (when flag ON + CANDIDATE) — audit C2 concrete hook

| Site | Why |
|------|-----|
| **Enqueue only from `save_capture_crops`** | Fires on dense stash (~tune 1Hz + Fix B burst flush). **Must not run observe inline** — `save_capture_crops` is reached from **event-loop `tune()`** (~L1400). |
| **Execute on dedicated off-loop worker** | Mirror `qt-burst-flush`: non-window-gated worker thread drains a queue of `(bgr_copy or path, now_ms)` and runs `_dense_candidate_observe` under `_inline_admission_lock`. |
| **Not only R2 windows** | Window-only feed recreates the bug. |

**C2 (locked):** hook = **schedule** from `save_capture_crops` (copy panel + ts into queue when CANDIDATE + flag ON + throttle); **observe** only on the dense-candidate worker thread (or shared burst worker with non-window drain), never under the asyncio loop.

**Dedupe:** skip if panel stash ts == `_last_dense_candidate_ts`.

### 4.3 What stays R2-window-only

| Path | Still window-gated? |
|------|---------------------|
| Full classify / composite authorship / OCR bootstrap | **Yes** |
| BOOTSTRAP `observe_bootstrap` + OCR cut | **Yes** (existing) |
| PROMOTED AUTHORED fold into monitor | **Yes** (existing; out of this fix’s promotion problem) |
| Dense CANDIDATE observe | **No** — CANDIDATE + flag + throttle only |

---

## 5. Thread-safety + event-loop rails

### 5.1 Serialization (C1 — correct lock name)

Reuse **`self._inline_admission_lock`** (not `_inline_classify_lock` — that name does not exist). Documents burst vs loop admission atomicity (~L634 / L944).

All of:

- `classify_in_window_sync` → `_inline_classify_worker` → `_session_anchor_fold` → `observe_candidate`
- `_dense_candidate_observe` → `observe_candidate`

must take **`_inline_admission_lock`** for generator mutation. Dense observe runs on a **dedicated off-loop worker** (or extended non-window drain on the burst worker); never concurrent with fold without the lock.

### 5.2 Never on the event loop (C2)

History: Phase 235 starvation; OCR 550ms–1.3s; match-10b classify collapse.  
**Concrete:** `save_capture_crops` is on the **event-loop `tune()` path** — so dense work is **enqueue-only** there.

| Allowed | Forbidden |
|---------|-----------|
| Dedicated dense-candidate worker thread (preferred; non-window-gated) | Running `killer_slot_best` / `observe_candidate` inside `tune()` / `save_capture_crops` |
| Burst-flush thread for window densify I/O (existing) | Calling `_ocr_bootstrap_read` from dense path |
| Lock-held pure CV + `observe_candidate` (cheap) | Holding lock across OCR |

### 5.3 Fresh-row state isolation (C3)

`_killer_fresh_row` mutates **`_prev_killer_gray`** / **`_last_killer_fresh_ms`** shared with the fold path. Cross-thread reuse **corrupts the frame-diff**.

| Dense path owns | Fold path keeps |
|-----------------|-----------------|
| `_dense_prev_killer_gray` | `_prev_killer_gray` |
| `_dense_last_killer_fresh_ms` | `_last_killer_fresh_ms` |
| `_dense_killer_fresh_row(bgr, now_ms)` — same algorithm, own prior | `_killer_fresh_row` unchanged |

is_background for dense uses `_dense_last_killer_fresh_ms` + the same `_SESSION_ANCHOR_ROW_PERSIST_MS` constant.

### 5.4 Double-count prevention

| Risk | Mitigation |
|------|------------|
| Same crop scored twice (flush + classify) | Throttle by panel stash ts: skip if `ts == _last_dense_candidate_ts` |
| Concurrent observe | `_inline_admission_lock` around generator |
| K inflated by background spam | Existing `is_background` / geometry gates unchanged |

---

## 6. Flag + cadence

| Symbol | Default | Meaning |
|--------|---------|---------|
| `RETINA_CANDIDATE_DENSE_SCORE` | **off** (`0`/unset) | Feature master switch — **byte-identical** live path when off |
| `RETINA_CANDIDATE_DENSE_MIN_MS` | **100** (suggested) | Min interval between dense observes (throttle) |
| Optional `RETINA_CANDIDATE_DENSE_EVERY_N` | **1** | Score every Nth save (secondary throttle) |

**Cadence recommendation (D-LAF-2):** **throttled every-crop of the dense stash**, not unrestricted 600-crop OCR-class work. Template match is cheap; throttle still protects CPU under 60fps panel churn. Default **100ms** ≈ ≤10 observes/s when CANDIDATE.

When flag OFF: zero new branches on hot path beyond a single env read at method entry (or config cached at start).

---

## 7. Integrity gate — unchanged (checklist)

| Gate | Value | Dense path |
|------|-------|------------|
| `k_consistency` | 3 | Unchanged |
| `promote_floor` | 0.66 | Unchanged |
| FP demote on background clear | R3 | Unchanged |
| Stall limit / recut | 3 | Unchanged; dense **feeds** stalls via feed_v1 raw_auth |
| OCR can never author / never increment K | D-CG-1 | Dense path: **no OCR at all** |
| PoAC / FROZEN / chain | — | No contact |

---

## 8. Test plan

| ID | Test |
|----|------|
| **T1** | Flag OFF: no calls to dense observe; classify/fold behavior byte-identical (spy/mock call counts) |
| **T2** | Synthetic CANDIDATE + 3 dense crops with score ≥0.66 → `promoted` event (K=3) without any classify window |
| **T3** | Dense path never invokes `_ocr_bootstrap_read` / `ocr_frame` (monkeypatch assert) |
| **T4** | Concurrent dense + fold: `_inline_admission_lock` ordering; no double-increment beyond one observe per unique stash ts |
| **T4b** | Dense fresh-row state does not mutate `_prev_killer_gray` (fold prior unchanged after dense observes) |
| **T4c** | `save_capture_crops` / tune path only enqueues; observe runs off-loop (thread assert / mock) |
| **T5** | Weak cut: candidate score low, feed_v1 ≥0.66 on 3 crops → `candidate_demoted_stall` / recut path |
| **T6** | Background crop with high candidate score → FP demote still works on dense path |
| **T7** | Throttle: N rapid saves → ≤1 observe per `DENSE_MIN_MS` |
| **T8** | Regime BOOTSTRAP/PROMOTED: dense observe no-ops |

Unit-test pure `SessionAnchorGenerator` where possible; integration tests mock `killer_slot_best` return values.

---

## 9. CODE-TRUTH (verify before build)

| Symbol | Location |
|--------|----------|
| `SessionAnchorGenerator`, BOOTSTRAP/CANDIDATE/PROMOTED | `l9_presence/killfeed_session_anchor.py` |
| `DEFAULT_K_CONSISTENCY=3`, `DEFAULT_PROMOTE_FLOOR=0.66`, `DEFAULT_STALL_LIMIT=3` | same ~L41–44 |
| `observe_candidate(..., raw_killer_authored=)` | same ~L157–207 |
| `killer_slot_best` | `l9_presence/killfeed_cv.py` |
| `_session_anchor_fold` | `bridge/vapi_bridge/qortroller_retina_capture.py` ~L1026–1106 |
| CANDIDATE branch + OCR stall witness | same ~L1069–1088 |
| `classify_in_window_sync` | same ~L954–977 |
| `save_capture_crops` | same ~L832–852 |
| `maybe_flush_burst_crop` (window-gated densify) | same ~L854+ |
| **`_inline_admission_lock`** (C1) | same ~L634 / L944 — **not** `_inline_classify_lock` |
| Burst-flush thread | same ~L780–797 |
| `tune()` → `save_capture_crops` on event loop (C2) | `tune` ~L1400 region |
| Fold fresh-row state | `_killer_fresh_row` / `_prev_killer_gray` |
| Dense fresh-row state (C3, new) | `_dense_killer_fresh_row` / `_dense_prev_killer_gray` / `_dense_last_killer_fresh_ms` |
| `RETINA_KF_EVERY_BURST` | densify flag (related, not this fix) |

**Do not** route dense path through `_ocr_bootstrap_read` (~L1108+).

### Audit corrections log (Claude → design fold → build)

| ID | Correction | Intent change? |
|----|------------|----------------|
| **C1** | Lock name `_inline_admission_lock` (design); **build used dedicated `_session_anchor_lock`** shared by fold + dense worker — fold `observe_candidate` also under lock (single-flight begin/end does not cover dense thread); `nullcontext` fallback for `__new__` test fixtures so fail-open fold except does not swallow missing lock | No — same serialization intent; dedicated lock is cleaner |
| **C2** | Off-loop `qt-dense-cand` worker (not inline in `tune()`/`save_capture_crops`) | No |
| **C3** | Own `_dense_prev_killer_gray` | No |
| **Build** | 9 new tests green (no-OCR + feed_v1 stall-recut); 75-test regression; PV-CI 182 | — |

---

## 10. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-LAF-1** | Dense path feeds **both** K-progress and stall-recut (feed_v1 raw_auth, no OCR) | **Both** | ☐ accept ☐ amend |
| **D-LAF-2** | Cadence: throttled dense stash (default min 100ms), not window-only | Yes | ☐ accept ☐ amend |
| **D-LAF-3** | Flag `RETINA_CANDIDATE_DENSE_SCORE` default **OFF** | Yes | ☐ accept ☐ amend |
| **D-LAF-4** | Enqueue from `save_capture_crops`; observe on off-loop worker + `_inline_admission_lock` + own dense fresh-row state | Yes | ☐ accept ☐ amend |
| **D-LAF-5** | No change to K / 0.66 / stall_limit / FP demote | Yes | ☐ accept ☐ amend |
| **D-LAF-6** | Proceed Claude audit → implement + tests → stage | Hold for GO | ☐ GO ☐ hold |

---

## 11. Success criterion (live validation — later, operator)

After flag ON on an RP session with real kills:

1. KAS trail shows `candidate_progress` and/or `candidate_stall` / `candidate_demoted_stall` / `promoted` during CANDIDATE without requiring dense OCR.  
2. Live authored_kills > 0 when archive has readable own-kills (same session).  
3. Flag OFF: prior behavior restored.

Not required to close the design lane; required before claiming “RP live authorship fixed.”

---

## 12. Explicit non-goals

- Lowering K or promote_floor for RP  
- OCR on dense stream  
- Replacing deferred attestation  
- EVENT-BIND / PoAC / chain  
- Auto-enabling the flag in production defaults  

---

*End of live-authorship dense-candidate fix design v0 — 2026-07-10.*
