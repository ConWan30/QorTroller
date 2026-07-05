# Phase C — Classify Sampling-Rate Bottleneck: Event-Driven Burst Mitigation (Scoping)

**Status: SCOPING ONLY — no code changed, no session run. Awaiting review before implementation.**

## 1. The finding this scopes

Live-verified during C-1.2 (2026-07-05, phase_c_c1_2_match1 session): the bootstrap-catch path
(`_session_anchor_fold`, and everything downstream of it — OCR bootstrap, session-anchor
promotion, dense-classify) only runs inside `maybe_classify_in_window`, which is called **once
per `_session_loop` iteration**. That loop's period is `dualshock_record_interval_s`, defaulting
to **1.0 second**. Dense-classify (Phase W.2, `d2eb8d9e`) lowers `min_gap_ms` from 200ms to 50ms
— but both values are already far below the 1-second loop period, so the min-gap was never the
real constraint. The actual ceiling is the loop's own once-per-second call rate, which
dense-classify does not touch.

Confirmed against real data: a crop from today's match scored 0.756 on `feed_v1` (comfortably
above both the 0.55 bootstrap floor and 0.66 promote floor) when re-checked offline, and OCR read
the handle cleanly at the same crop — yet zero bootstrap catches happened live, and R2-window
math confirms a window was open at that exact timestamp. This matches the original Fusion Arc
finding ("~2.8 classifications/window for 23 kills, 0 authored") almost exactly, and likely
explains the "many kills, zero authored" pattern across the whole arc, not just today.

## 2. Precedent this design reuses (not a new pattern)

`bridge/vapi_bridge/presence_burst.py::should_combat_fire()` already solves an adjacent problem
with exactly this shape: "fire a presence burst iff R2 just crossed the fire threshold (rising
edge), no burst is currently capturing, and the cooldown since the last combat burst has
elapsed." It's driven from the same per-tick `_r2i` (max r2_trigger across the tick's pydualsense
frame batch) that already feeds `mark_r2_onset`, computed inline within `_session_loop` — no
cross-thread signaling needed, since it stays on the asyncio event-loop thread throughout. This is
a live, working, already-proven mechanism in this exact codebase. The classify-density fix below
is the same shape applied to a different downstream action (densify classify calls, not
toggle WGC capture).

## 3. Proposed design

### 3.1 Core idea (matches the operator's proposal)

Keep `_session_loop`'s own interval untouched (no global rate change — invasive, affects every
other system riding that loop: HID feed, l2_ads, death-window, ADS coupling, etc.). Instead, run a
**separate, independent async task** that polls at a much tighter interval (e.g., every 100–200ms)
but only *does anything* while a **burst window** is armed. The burst arms on an R2 rising edge
(reusing `should_combat_fire`'s exact detection logic) and stays armed for a bounded duration
(3–5s, matching the R2_WINDOW_MS `hi` bound so the burst and the classify-window close together).

### 3.2 Concrete mechanism

- **New small controller, `ClassifyBurstController`** (new file, `bridge/vapi_bridge/classify_burst.py`,
  modeled directly on `PresenceBurstController`'s shape — `is_active`, single bounded task, fail-open):
  - `arm(now_ms)`: sets `self._armed_until_ms = now_ms + burst_duration_ms`.
  - `async def run(self, poll_interval_s=0.15)`: `while self._running: if time.time()*1000 <
    self._armed_until_ms: self._rgc.maybe_classify_in_window(time.time()*1000); await
    asyncio.sleep(poll_interval_s)`.
  - Reuses `maybe_classify_in_window` UNCHANGED — no new classify logic, no new scoring path. The
    burst controller's only job is to call that existing, already-safe entry point more often.
- **Trigger site**: alongside `dualshock_integration.py`'s existing combat-trigger block
  (`bridge/vapi_bridge/dualshock_integration.py` ~line 1811), which already computes
  `_r2 = int(frames[-1].r2_trigger)` and tracks `self._prev_r2_combat` for rising-edge detection
  via `should_combat_fire`. Note this is a SEPARATE per-tick computation from `mark_r2_onset`'s
  own `_r2i = max(f.r2_trigger for f in frames)` (last-frame vs max-across-batch, different state
  variables) — two independent R2-detection sites already coexist in this exact function today.
  The classify-burst arm should reuse the combat-trigger's rising-edge result directly (same `if
  should_combat_fire(...)` block, one more line) rather than adding a third independent
  computation.
- **Why this is safe by construction**: `InlineAuthorshipMonitor.should_classify()` already gates
  on `_inflight` (single-flight — a call while a classify is in-flight is a safe no-op) and
  `min_gap_ms` (a call before the gap elapses is a safe no-op) and the R2-window bounds themselves
  (a call outside an open window is a safe no-op). Calling `maybe_classify_in_window` from TWO
  independent sources (the main loop's once-per-second call, and this new burst task's ~every-150ms
  call) is exactly as safe as calling it from one source more often — every extra call outside a
  valid firing moment is a cheap no-op, and the classify itself remains off-thread
  (`asyncio.to_thread`) so it never blocks either caller.

### 3.3 What this does NOT change

- `_session_loop`'s own interval, HID feed cadence, l2_ads, death-window, ADS coupling — untouched.
- `_killer_fresh_row`'s frame-diff logic — untouched. (Open question, not a design decision: denser
  sampling means the "previous frame" fed into the fresh-row diff will usually be much more recent
  once the burst is active, which should make that diff MORE meaningful, not less — but this is an
  expected side-effect to verify empirically, not something this design deliberately targets.)
- The R2_WINDOW_MS bounds, match_floor, killer_max_frac, any promotion/stall-limit constant.
- `push_r2_raw` / `HidOnsetDetector` (today's fix) — this design deliberately reuses the per-tick
  `_r2i` trigger (same one `should_combat_fire` uses), not the device-clock HID lobe, so it stays
  on the asyncio thread with zero cross-thread signaling. The device-clock HID lobe remains the
  cross-lobe-latency measurement source; it is not repurposed as a live control signal here.

## 4. Config surface (default-OFF)

| Flag | Default | Purpose |
|---|---|---|
| `RETINA_CLASSIFY_BURST_ENABLED` | False | master switch for this mitigation |
| `RETINA_CLASSIFY_BURST_DURATION_MS` | 5000 (matches R2_WINDOW_MS hi bound) | how long a burst stays armed after the triggering rising edge |
| `RETINA_CLASSIFY_BURST_POLL_S` | 0.15 | the burst task's own poll interval |

Requires `--session-anchor` (or at least `--killfeed-inline`) to have any effect — a no-op flag
otherwise, same discipline as `--dense-classify`/`--ocr-bootstrap`.

## 5. Test plan

- Pure unit tests on the controller (mirroring `presence_burst.py`'s own test shape, if one
  exists — check before writing): arm() sets the deadline correctly; run() calls
  `maybe_classify_in_window` repeatedly while armed, not at all once expired; `is_active`
  reflects armed state; fail-open on any exception from the RGC call.
- A wiring test at the `RetinaGameCapture`/`dualshock_integration` boundary confirming the burst
  arms on the same rising-edge condition `should_combat_fire` already uses (same `_r2i` inputs,
  same threshold) — NOT a new detection mechanism, so this test should be nearly a copy of
  `should_combat_fire`'s own existing tests with the classify-burst arm as the assertion instead.
- Explicitly test the "extra calls are safe no-ops" property: call `maybe_classify_in_window`
  back-to-back with no window open, assert no exception and no classify scheduled.

## 6. Open questions for review (do not resolve unilaterally)

- **Burst duration**: 5000ms (proposed, matches R2_WINDOW_MS hi) — or should it re-arm/extend on
  each subsequent rising edge within the burst (sustained fire keeps it open), mirroring
  `mark_onset`'s own "sustained fire keeps the window open" semantics? Recommend yes (extend, not
  restart), for consistency with how the classify window itself already behaves.
- **Poll interval**: 150ms proposed (comfortably above `classify_panel`'s own ~100ms cost, so the
  burst task never queues up faster than classify can actually complete) — is this the right
  balance, or should it be tied to `RETINA_DENSE_CLASSIFY_MIN_GAP_MS` instead of a new independent
  constant?
- **Scope of the fix**: this mitigates the *classify* sampling rate specifically. It does NOT
  increase the *crop-saving* rate for corpus-growth purposes generally (crop-saving is currently
  coupled 1:1 to classify calls via `_inline_classify_worker`) — should burst-mode crops also be
  saved to the dense corpus, or would that meaningfully change corpus composition/growth-rate
  assumptions elsewhere? Flagging rather than deciding.
- **Validation session**: once implemented, C-1.2's next live session doubles as this fix's live
  validation (does the 0.756-scoring-crop-class of miss actually stop happening) — same "the next
  corpus session is the live validation" pattern D-CG-1 used.

## 7. Relationship to C-1.2

Recommend NOT resuming C-1.2 data collection (including the firing-range hitmarker test) until at
least a first pass of this mitigation lands — every session run under the current 1 Hz ceiling
risks the same low-yield outcome as today's match, which wastes rig time without producing usable
latency data. This mitigation is non-rig work and can proceed immediately.
