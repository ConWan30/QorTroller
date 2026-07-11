# F-ARCB-1 — Force MATCH_ENDED on Session Close

**Status:** FIX DESIGN ONLY (2026-07-10).  
**Finding:** Live LUMEN-2b emitted `MATCH_STARTED` (n_started=1, `match_state=IN_MATCH`) but at stop `match_state_n_ended=0` and no `MATCH_ENDED` line in `retina_match_state.jsonl`, despite `close_session` wired at `RGC.stop` ~L1712.  
**Rails:** advisory never-gates · flag-off byte-identical · dedup preserved · no FROZEN/PoAC/chain · PV-CI 182.

---

## 1. Claim / scope

**Make `LiveMatchStateTracker.close_session` always emit a deterministic `MATCH_ENDED` for any still-open IN_MATCH group at session close (using last activity as `ts_ms` and stop time as `detected_at_ms`), so the seamless match view completes without waiting for 240s exit-gap confidence and without relying solely on `detect_match_state` returning a live IN_MATCH span at stop.**

| In scope | Out of scope |
|----------|----------------|
| `close_session` force-emit path | Changing `tick` hysteresis / exit_gap |
| Tests for open-match close | B2 per-match KAS segmentation |
| Wiring already at RGC.stop | Crypto session boundary changes |

---

## 2. Root cause (pinned)

### 2.1 Current `close_session` (~L121–137)

```text
tl = detect_match_state(session_span=(start, now), onsets, windows, kills, ...)
for span in tl.spans where state == IN_MATCH:
    emit MATCH_ENDED if end_key not in _emitted
clear _open_match_start_ms
```

It **ignores** `_open_match_start_ms` (the live tracker's open-match flag set on STARTED).

### 2.2 Why detect can yield zero ENDED while live was IN_MATCH

| Mechanism | Effect |
|-----------|--------|
| **Open-match not reified as ENDED** | `detect_match_state` snaps IN_MATCH end to **last active bucket**; that span is still `IN_MATCH` in the timeline and *should* appear in the for-loop — unless confirmation fails at re-detect |
| **Clock / signal mismatch at stop** | `close_session(time.time()*1000)` vs dualshock `_now_ms` / session_start clock drift → empty or UNKNOWN timeline → **no IN_MATCH spans** while `_open_match_start_ms` was set during play |
| **Dedup alone** | Cannot explain n_ended=0 if no prior ENDED was emitted |

Live evidence: STARTED fired → `_open_match_start_ms` was set → `state_now` was IN_MATCH. Stop path must **force-close that open group** even if re-detect returns nothing.

### 2.3 Design intent already stated

Module docstring / wiring design: *close_session flushes newest match end without waiting for hysteresis; manifest seal is a harder boundary than the gap.* Implementation only did “re-detect and emit if span present” — incomplete vs that intent.

---

## 3. Fix (exact semantics)

### 3.1 Algorithm

```text
close_session(now_ms) -> list[LiveTransition]:
  out = []

  # (A) Existing path: emit ENDED for any IN_MATCH spans re-detect finds
  #     (covers multi-match / already-snapped ends; keep for parity)
  tl = detect_match_state(...)
  for span in IN_MATCH spans:
      end_key = (MATCH_ENDED, round(span.end_ms / (bucket_s * 1000)))
      if end_key not in _emitted:
          _emitted.add(end_key)
          out.append(LiveTransition(MATCH_ENDED, span.end_ms, now_ms))
          # clear open if matches
          if _open_match_start_ms == span.start_ms:
              _open_match_start_ms = None

  # (B) F-ARCB-1 FORCE PATH — still-open live match
  if _open_match_start_ms is not None:
      end_ts = _last_activity_ms() if _last_activity_ms() is not None else float(now_ms)
      # Prefer last activity for ts_ms (truth: match ended at last activity);
      # detected_at_ms = now_ms (honest: we became confident at stop).
      end_key = (MATCH_ENDED, round(end_ts / (bucket_s * 1000)))
      if end_key not in _emitted:
          # Collision with (A) same bucket: skip (already emitted).
          # If collision wrongly skipped a needed emit, use force key below.
          _emitted.add(end_key)
          out.append(LiveTransition(MATCH_ENDED, end_ts, float(now_ms)))
      else:
          # Same bucket key already used but open flag still set (edge case):
          force_key = (MATCH_ENDED, "session_close", round(end_ts / (bucket_s * 1000)))
          if force_key not in _emitted:
              _emitted.add(force_key)
              out.append(LiveTransition(MATCH_ENDED, end_ts, float(now_ms)))
      _open_match_start_ms = None

  return out
```

**Simpler preferred form (D-ARCB-1):** after path (A), if `_open_match_start_ms is not None`, always append one `MATCH_ENDED` with:

- `ts_ms = last_activity or now_ms`  
- `detected_at_ms = now_ms`  
- dedup key = `(MATCH_ENDED, "session_close", round(ts_ms / bucket_ms))` **or** always unique `(MATCH_ENDED, "session_close", int(now_ms))` so force never collides with detect-based keys  

Recommend **`end_key = (MATCH_ENDED, "session_close")`** single-shot: at most one force-close per tracker lifetime. Clear, matches “session seal once.”

### 3.2 Dedup policy (locked recommendation)

| Key | Use |
|-----|-----|
| Detect path | `(MATCH_ENDED, bucket_index)` as today |
| Force path | `(MATCH_ENDED, "session_close")` — **exactly one** force ENDED per tracker if open |

If detect already emitted ENDED for that match (open flag cleared in (A)), force skipped.  
If detect emitted nothing but open flag set, force emits once.

### 3.3 Advisory rails unchanged

- Emit only via existing `_emit_match_state` / jsonl / diag counters.  
- No authorship/PoSP/certificate gates.  
- Flag still `RETINA_MATCH_STATE_ENABLED`; when off, stop path no-ops.

### 3.4 Clock note (optional hardening, same PR if cheap)

If construct used wall `time.time()*1000` and dualshock uses a different `_now_ms`, document that **session_start_ms and all push_* must share one clock**. Prefer setting `session_start_ms` from the first dualshock `_now_ms` when available. Not required to fix force-emit if open flag is trusted.

---

## 4. CODE-TRUTH

| Item | Path |
|------|------|
| `close_session` / `_open_match_start_ms` / `_last_activity_ms` | `l9_presence/match_state_live.py` ~L77–81, L103–108, L121–137 |
| `detect_match_state` | `l9_presence/match_state.py` ~L130–200 |
| Stop wiring | `qortroller_retina_capture.py` `stop` ~L1707–1715 |
| Tick / emit | RGC `tick_match_state` / `_emit_match_state` |
| Pure tests today | `l9_presence/tests/test_match_state_live.py` (`close_session flushes without hysteresis`) |
| Wiring tests | `bridge/tests/test_match_state_wiring.py` |

---

## 5. Test plan

| ID | Assert |
|----|--------|
| **T1** | STARTED via kill/onset → `close_session` before exit_gap → **one** MATCH_ENDED; `_open_match_start_ms is None` |
| **T2** | `ts_ms` of force ENDED ≤ last onset/window/kill; `detected_at_ms == now_ms` |
| **T3** | Double `close_session` → second returns [] (dedup) |
| **T4** | If detect path already emitted ENDED and open cleared → force does not double-emit |
| **T5** | Empty signals + never STARTED → close returns [] |
| **T6** | Flag-off wiring: stop does not require tracker |
| **T7** | Never-gates: no production of certificate/verdict side effects (pure module) |

Update pure test that claimed close_session flushes without hysteresis to cover **open flag force** when re-detect would return empty (simulate by using mismatched session_span if needed, or spy).

---

## 6. Operator decisions

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-ARCB-1** | Force ENDED via `_open_match_start_ms` + last_activity; dedup key `(MATCH_ENDED, "session_close")` | Yes | ☐ accept ☐ amend |
| **D-ARCB-2** | Keep detect-based (A) path first for multi-match | Yes | ☐ accept ☐ amend |
| **D-ARCB-3** | No change to tick hysteresis | Yes | ☐ accept ☐ amend |
| **D-ARCB-4** | Proceed Claude audit → build → stage | Hold for GO | ☐ GO ☐ hold |

---

## 7. Success criterion

Live session with `RETINA_MATCH_STATE_ENABLED=1`:

- jsonl has MATCH_STARTED during play  
- After stop: **MATCH_ENDED** line present, `match_state_n_ended ≥ 1`  
- Advisory only  

---

*End F-ARCB-1 design v0 — 2026-07-10.*
