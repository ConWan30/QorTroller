# LUMEN-2b Live Match-State Wiring (Arc B)

**Status:** WIRING DESIGN ONLY (2026-07-10). Loop: design → Claude audit/build → operator commit.  
**Not:** new match-state algorithm, per-match KAS segmentation (B2), or certificate changes.  
**Rails:** advisory never-gates · flag-gated default-OFF · tick ~1/consumption cycle · live==offline detector · no PoAC/FROZEN/chain · PV-CI 182.

---

## 1. Claim / scope

**Wire the finished pure `LiveMatchStateTracker` into the live capture consumption path so the operator can see MATCH_STARTED / MATCH_ENDED (and current LOBBY/IN_MATCH) during play — by feeding signals the loop already produces, ticking once per consumption cycle, emitting advisory JSONL + diag fields — without gating any verdict, certificate, or cryptographic session boundary.**

| In scope (this increment) | Out of scope (B2 / later) |
|---------------------------|---------------------------|
| Construct / feed / tick / close tracker | Auto-segment deferred KAS via `slice_scan_by_spans` |
| `retina_match_state.jsonl` + RGC diag surface | Dashboard UI productization |
| Flag-off byte-identical | Chain / FROZEN / PoAC |

---

## 2. Ready core (no reimplementation)

| API | Role |
|-----|------|
| `LiveMatchStateTracker(session_start_ms, session_id=...)` | Construct once at capture start |
| `push_onset(t_ms)` | R2 fire times |
| `push_window(gate_ms, end_ms)` | Resolved R2 classify windows |
| `push_kill_span(start_ms, end_ms)` | **Confirmed** K≥anchor kill activity only |
| `tick(now_ms) → list[LiveTransition]` | Diff new MATCH_STARTED / MATCH_ENDED |
| `close_session(now_ms) → list[LiveTransition]` | Flush final ENDED at stop (no 240s wait) |
| `state_now(now_ms) → "IN_MATCH" \| "LOBBY"` | Advisory current state |
| `LiveTransition.to_dict()` | Emit payload |

`tick` re-runs **`detect_match_state`** (same as offline). Offline M14/M13 timelines remain the regression anchor.

---

## 3. Wiring map (CODE-TRUTH)

### 3.1 Construct (capture start)

| Item | Spec |
|------|------|
| **Where** | `RetinaGameCapture.__init__` (or first start path next to other default-OFF monitors: session-anchor / death / ads ~L667–730) |
| **When flag ON** | `self._match_state = LiveMatchStateTracker(session_start_ms=time.time()*1000 or first_tick, session_id=...)` |
| **session_id** | Prefer `os.environ.get(ENV_SESSION_ID)` from `l9_presence.session_identity` (daemon mints via `derive_session_id`); else `None` / local stamp — **must not invent a second join key** if ENV is set |
| **When flag OFF** | `self._match_state = None` — zero feeds, zero tick, zero file |

### 3.2 Feeders

| Signal | Hook | Exact behavior |
|--------|------|----------------|
| **Onset** | `RetinaGameCapture.mark_r2_onset` ~**L935–948** | After `mark_onset` succeeds path: `if self._match_state: self._match_state.push_onset(float(now_ms))` |
| **Window** | `_log_composite` ~**L950+** when composite is non-None | If composite has `window_gate_ms` and `window_end_ms` (from `killfeed_inline` resolve ~L357–360): `push_window(gate, end)` **once per resolved composite** (each composite is one closed window) |
| **Kill span** | Same `_log_composite` | **Only** `composite.get("verdict") == "AUTHORED_PRESENT"`: `push_kill_span(window_gate_ms, window_end_ms)` or `(killer_first_ms, ts_ms)` if gate missing — prefer **window bounds** as the confirmed activity span. Do **not** feed OBSERVED/SPECTATED/OWN_DEATH as kill anchors (feeder owns F-LUMEN-2 discipline) |

### 3.3 Tick (bounded cadence)

| Item | Spec |
|------|------|
| **Where** | Immediately after `flush_stale_inline_window` in the consumption cycle — **`dualshock_integration.py` ~L1803** (documented call site of flush). Prefer a thin `RetinaGameCapture.tick_match_state(now_ms)` that: flush already done by caller → `transitions = tracker.tick(now_ms)` → emit. |
| **Cadence** | **Once per consumption cycle**, not per WGC frame, not per HID sample. Same order of cost as flush_stale (already “once per tick”). |
| **Cost** | `detect_match_state` is O(n) over accumulated onsets/windows/kills (stdlib). Over a long match n is thousands, not millions; once-per-consumption keeps it off the hot path. Do **not** call from `on_frame_arrived`. |
| **Thread** | Consumption loop context (same as mark_r2_onset / flush today) — pure stdlib, no OCR/cv2. Fail-open: exceptions never break capture. |

### 3.4 close_session

| Item | Spec |
|------|------|
| **Primary** | `RetinaGameCapture.stop()` ~**L1619–1622** — before tearing down source: `if self._match_state: emit(self._match_state.close_session(now_ms))` |
| **Daemon** | `cmd_stop` kills the process after harvest; **RGC.stop must flush** so stop is reliable without a separate daemon-only path. Optional: daemon also reads final jsonl for summary print — not required for wiring. |

### 3.5 Emit format

**File:** `retina_match_state.jsonl` (path next to composites; configurable default like other logs).

**Line schema** (one transition per line):

```json
{
  "schema": "qortroller-match-state-live-v0",
  "session_id": "<ENV or null>",
  "event": "MATCH_STARTED" | "MATCH_ENDED",
  "ts_ms": 0.0,
  "detected_at_ms": 0.0,
  "advisory": true
}
```

Plus optional `match_state_now` heartbeats: **not required** — prefer event-only to keep volume low; surface current state in **diag only**.

**Diag** (`status_dict` / RGC diag block used by daemon parse):

```text
match_state_enabled: bool
match_state: "LOBBY" | "IN_MATCH" | "OFF"
match_state_last_event: "MATCH_STARTED" | "MATCH_ENDED" | null
match_state_last_ts_ms: float | null
match_state_n_started: int
match_state_n_ended: int
```

Log.info on STARTED/ENDED (once per transition) so the operator sees it in the daemon log while playing.

---

## 4. Five hard rails

| # | Rail | Enforcement |
|---|------|-------------|
| **1** | **Advisory — never gates** | No branch of authorship, PoSP, KAS, dense-candidate, or certificates reads match-state. Crypto session boundary = daemon start/stop only (module invariant). |
| **2** | **Flag default-OFF** | `RETINA_MATCH_STATE_ENABLED` unset/0 → no construct, no push, no tick, no file, no diag keys beyond `match_state_enabled: false` (or omit). |
| **3** | **Bounded tick** | Once per consumption cycle only; off WGC/hot path; fail-open. |
| **4** | **live == offline** | Same `detect_match_state`; tests: feed identical onsets/windows/kills → live tracker transitions match offline detector timeline (or pure-core parity already in `test_match_state_live.py` + one integration feed test). |
| **5** | **No chain / FROZEN / PoAC / 228B** | PV-CI 182; no new domain tag (schema string only on jsonl). |

---

## 5. B2 note (do not build)

Per-match authorship auto-segmentation: feed confirmed match spans into existing `kas_deferred.slice_scan_by_spans` at session-close / deferred build. **Natural B2** after this emit path is proven live. Out of scope here.

---

## 6. Test plan

| ID | Assert |
|----|--------|
| **T1** | Flag OFF: no tracker attribute / no `push_*` / no jsonl created (spy construct) |
| **T2** | Pure parity: same signals → `tick` transitions match offline `detect_match_state` span events (reuse M14-style synthetic feeds from `test_match_state_live`) |
| **T3** | `push_kill_span` alone → MATCH_STARTED (kill-anchor confirm) |
| **T4** | `close_session` emits final MATCH_ENDED without waiting exit_gap |
| **T5** | Multiple `tick` calls dedupe (no double STARTED) |
| **T6** | Wiring unit: mock composite AUTHORED_PRESENT → push_kill_span called once; non-AUTHORED → not called |
| **T7** | `mark_r2_onset` → push_onset once when enabled |
| **T8** | Fail-open: tracker raises → capture path continues |

---

## 7. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-LMW-1** | Flag name `RETINA_MATCH_STATE_ENABLED` default OFF | Yes | ☐ accept ☐ amend |
| **D-LMW-2** | Emit path `retina_match_state.jsonl` + log.info + diag fields | Yes | ☐ accept ☐ amend |
| **D-LMW-3** | Tick once per consumption cycle after `flush_stale_inline_window` | Yes | ☐ accept ☐ amend |
| **D-LMW-4** | Kill feeder = AUTHORED_PRESENT composites only | Yes | ☐ accept ☐ amend |
| **D-LMW-5** | session_id from `ENV_SESSION_ID` when set | Yes | ☐ accept ☐ amend |
| **D-LMW-6** | B2 slice_scan auto-segment deferred | Yes | ☐ accept ☐ amend |
| **D-LMW-7** | Proceed Claude audit → build → stage | Hold for GO | ☐ GO ☐ hold |

---

## 8. CODE-TRUTH index

| Item | Path |
|------|------|
| Tracker core | `l9_presence/match_state_live.py` |
| Offline detector | `l9_presence/match_state.py` `detect_match_state` |
| Existing pure tests | `l9_presence/tests/test_match_state_live.py` |
| R2 onset | `bridge/vapi_bridge/qortroller_retina_capture.py` `mark_r2_onset` ~L935 |
| Composite log / AUTHORED | `_log_composite` ~L950–981; verdict keys from `killfeed_inline` resolve ~L357–360 |
| Window fields | `window_gate_ms`, `window_end_ms` on composite |
| Flush + consumption | `flush_stale_inline_window` ~L983; caller `dualshock_integration.py` ~L1803 |
| Stop | `RetinaGameCapture.stop` ~L1619 |
| Daemon stop | `scripts/retina_capture_daemon.py` `cmd_stop` ~L368 (process kill; rely on RGC.stop) |
| Session id env | `l9_presence/session_identity.py` `ENV_SESSION_ID`; daemon mint ~L87–89 |

---

## 9. Success criterion (operator)

With `RETINA_MATCH_STATE_ENABLED=1` on a live session:

1. Daemon log shows `MATCH_STARTED` after real play begins (kill anchor or consecutive activity).  
2. Diag `match_state` flips LOBBY ↔ IN_MATCH.  
3. At stop, jsonl has matching STARTED/ENDED lines; `close_session` ensures final ENDED if a match was open.  
4. Flag OFF: no behavioral change vs current capture.

---

*End of LUMEN-2b live match-state wiring design v0 — 2026-07-10.*
