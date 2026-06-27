---
type: synthesis
id: s-retina-wgc-process-isolation-scope
title: Process-isolation scope for the WGC screen-lobe — validate the in-bridge contention diagnosis FIRST, then isolate WGC+cv_motion into a subprocess feeding FrameMotion over a queue so the coupled-retina/lag pillar runs at full frame rate
created: 2026-06-26T23:10:00Z
modified: 2026-06-26T23:10:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 150
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the durable fix for the ~2fps WGC delivery that limits the coupled-retina/lag pillar. The shape-guard
fix (cycle-39, `55ee8c55`) UNBLOCKED the screen-lobe (COUPLED_CLEAN now appears, frame_errs=0), but WGC
delivers only ~2fps INSIDE the busy bridge process while it ran full-rate STANDALONE earlier (frames_seen 218
vs frozen ~20). The remaining limiter is frame DELIVERY rate, not crashes.

OBSERVED (live, this session): window-capture AND monitor-capture both ~2fps; frame_errs=0 post-shape-guard;
cv2 ops (cvtColor/resize/Farneback) release the GIL so pure-CPU contention is NOT the obvious cause; the
windows_capture callback runs on its own thread but must re-enter Python (GIL) to invoke our handler, and the
bridge runs a heavy asyncio loop + ChainReconciler (STAGE-8 SLOW CHAIN 5-10s blocks) + agent fleet on the
same interpreter. HYPOTHESIS: the WGC callback is starved of interpreter time / event-loop scheduling in the
bridge process. NOT PROVEN.

PHASE 0 — VALIDATE THE DIAGNOSIS BEFORE BUILDING (recursive-verification-first; the load-bearing gate):
run the EXISTING standalone capture (a tiny script constructing RetinaGameCapture(monitor_index=1).start(),
print frames_seen/fps over 30s) WHILE the bridge is running and the operator plays. Two outcomes:
  (a) standalone gets ~60fps alongside the bridge -> CONFIRMS in-bridge contention -> process isolation is
      the correct fix (Phase 1).
  (b) standalone ALSO ~2fps -> the limit is the capture itself (Remote Play protected/overlay surface, or the
      monitor present-rate to WGC), and process isolation will NOT help -> stop, re-scope toward a different
      capture path (DXGI Desktop Duplication, or accept the rate / use it as a low-rate witness only).
Phase 0 is ~20 LOC + a play session; it prevents building the wrong fix. Do NOT skip it.

PHASE 1 — PROCESS-ISOLATE (only if Phase 0 = (a)): isolate the GIL-heavy half, keep coupling where the HID is.
  Architecture (Option B, preferred over running the whole core in the subprocess):
    * SUBPROCESS (multiprocessing.Process): owns WgcFrameSource — WGC capture + _to_u8_bgr (HDR-aware) +
      cv_motion (to_gray_small + frames_to_motion + the cycle-39 shape-guard). Emits FrameMotion samples
      {ts_ms, yaw_rate, pitch_rate} over a multiprocessing.Queue (tiny payload at ~60fps; not raw frames).
    * BRIDGE SIDE: a MotionReceiver drains the queue -> core.feed_frame_motion(...); the hot loop keeps
      feeding core.feed_hid(...) (HID already lives in the bridge). Coupling extract_features + the verdict
      stay in-bridge (lightweight numpy) -> meta["retina_coupled_verdict"] unchanged downstream.
  Why Option B over "whole core in subprocess": the coupling oracle is cheap and needs the HID stream that is
  already in the bridge; shipping HID INTO the subprocess + verdict back doubles IPC. Isolate only the heavy
  WGC+cv_motion producer.
  GOVERNOR straddle: the AdaptiveCaptureGovernor adjusts downscale (subprocess) AND lag_window_ms (bridge
  oracle). Keep the governor in the bridge; send `downscale` to the subprocess over a small control Queue;
  the subprocess reports fps telemetry back in the FrameMotion envelope. The shape-guard already makes a live
  downscale change safe.
  LIFECYCLE + fail-open: subprocess starts/stops with the bridge under retina_game_capture_enabled; if it
  dies or the queue stalls, the receiver feeds nothing -> coupling abstains (exactly today's None behavior) ->
  the proof degrades gracefully, never fabricates. A stall watchdog respawns it (parallels restart_if_stalled).

REUSE (no new physics): RetinaGameCaptureCore / WgcFrameSource / cv_motion / map_l9_to_nqpv_retina / the
coupled_negative gate / the shape-guard ALL carry over verbatim; only the PROCESS BOUNDARY + the FrameMotion
queue are new. Default-off; reversible.

HONESTY RAILS: (i) the in-bridge-contention cause is HYPOTHESIZED — Phase 0 must confirm it or the build is
wrong; (ii) no FROZEN-v1 / 228B PoAC / chain / IOTX — this is a capture-transport refactor, not a protocol
change; (iii) the 4 non-screen pillars (presence/PoEP, hardware, input⊗gameplay, physicality L4·L5·L6) are
already at 100% and do NOT depend on this — process isolation only raises the coupled-retina sample RATE from
intermittent (~25%) toward continuous; (iv) if Phase 0 = (b), the honest outcome is "screen-lobe is a
low-rate witness on Remote Play" and the lag pillar belongs to a native-PC aim-game (directly capturable
swapchain), NOT more capture engineering. Related: [[s-bt-contention-angle-scope]],
[[s-presence-oracle-liveness-scope]], [[project_dualconnection_capture_blind_finding]],
[[recursive_verification_first_pattern]].
