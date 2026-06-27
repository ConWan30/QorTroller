---
type: synthesis
id: s-wgc-fps-deepdive-workflow
title: WGC fps deep-dive research workflow — process isolation CONFIRMED dead; the frames exist at 60fps on screen so this is a capture-PATH problem; cheapest-first experiment matrix (Game-Bar diagnostic -> windowed mode -> Win graphics settings -> OCR/process audit -> DXGI Desktop Duplication) with stop-at-first->=30fps gates
created: 2026-06-26T23:40:00Z
modified: 2026-06-26T23:40:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 130
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

CONFIRMS process isolation is dead AND scopes the deep-dive to make WGC capture match the 60fps the display
already renders. Two parts.

PART A — PROCESS ISOLATION CONFIRMED RULED OUT. Phase 0 (cycle-40, `6521644f`): standalone WGC monitor-capture
of FULLSCREEN Remote Play = ~1.6fps, IDENTICAL to in-bridge. A separate process with its own interpreter +
no asyncio loop + no agent fleet got the SAME rate -> the ~2fps is NOT GIL/event-loop contention -> moving
WGC to a subprocess cannot raise it. Phase 1 stays OFF. (The cycle-39 shape-guard remains correct + necessary
— it's what lets coupling compute at all.)

PART B — THE REFRAME (load-bearing): the operator SEES smooth 60fps gameplay in the Remote Play window, and
Windows is set to 60fps video capture. So the frames PHYSICALLY EXIST at 60fps on the display — WGC just isn't
SAMPLING them. That makes this a capture-PATH problem (likely solvable), not a "the frames aren't there"
problem. Phase 0 only tested ONE path (WGC monitor-capture of fullscreen); it did NOT test windowed mode,
overlay/flip settings, process load, or alternate capture APIs. The leading hypothesis: fullscreen Remote
Play presents via independent-flip / hardware overlay that bypasses DWM composition, so WGC (which samples the
composed surface) sees ~1.6fps; a COMPOSITED (windowed) surface, or a capture API that reads the flip chain
directly (DXGI Desktop Duplication), would get full rate.

DEEP-DIVE EXPERIMENT MATRIX (cheapest-first; STOP at the first that yields >=30fps; each measured with an
extended validate_wgc_standalone_fps reporting a comparison row):
  E0 — BOUNDS THE QUESTION (do this first, ~2 min, operator action): does ANY tool capture Remote Play at
       60fps? Record 10s with Xbox Game Bar (Win+Alt+R) — check the clip's fps; or OBS Display/Window Capture
       fps meter. If 60 -> the surface IS capturable -> our WGC path/config is the problem -> E1+ will work.
       If ~2 -> the surface is protected against ALL capture -> skip to the native-PC fallback, do not invest
       in E1-E4. THIS GATE decides whether the deep dive is worth running.
  E1 — WINDOWED Remote Play + WGC window-capture (cheapest fix, highest prior): switch Remote Play OUT of
       fullscreen to a window; capture by window_name. A composited window is reliably WGC-capturable at the
       present rate. Measure.
  E2 — WINDOWS GRAPHICS SETTINGS: toggle Settings > System > Display > Graphics > "Optimizations for windowed
       games" (Win11 flip-model control) for Remote Play, and global "Hardware-accelerated GPU scheduling"
       (Settings > Display > Graphics > Default settings). Re-measure E1/fullscreen after each. These directly
       change whether presentation goes through DWM (capturable) or an overlay (not).
  E3 — PROCESS / OCR AUDIT: enumerate running capture/OCR/GPU-heavy processes (the operator mentioned an
       installed OCR). Since the screen IS smooth 60fps, a GPU hog is UNLIKELY the cause (the display isn't
       starved) — but rule out a competing capturer that grabbed the frame pool, and confirm no OCR is pinning
       the capture path. Cheap to check, low prior.
  E4 — DXGI DESKTOP DUPLICATION (strongest alternate API): use `dxcam` (pip; DXGI-based, commonly 60-240fps,
       reads the flip chain directly and handles overlay/fullscreen better than WGC for many titles). Add a
       dxcam frame source behind the SAME RetinaGameCaptureCore (feed_frame_motion) so cv_motion + coupling +
       the shape-guard are reused verbatim; only the frame PRODUCER changes. Measure vs WGC.
  E5 — OBS VIRTUAL-CAM BRIDGE (heavyweight fallback): OBS captures Remote Play, exposes a virtual camera; the
       bridge reads the v-cam (cv2.VideoCapture). Robust but adds an external dependency + a manual OBS step.

TOOLING: extend scripts/validate_wgc_standalone_fps.py to (a) accept a `--backend {wgc-monitor,wgc-window,
dxcam}` switch and (b) print a comparison table across runs, so E1/E4 are one command each. dxcam install is
gated behind E0=capturable (don't add the dep until E0 says it's worth it).

DECISION: the workflow is a FUNNEL — E0 decides solvable-at-all; E1/E2 are the cheap likely fixes (windowed +
flip settings); E4 is the real alternate if the surface needs flip-chain reading; native-PC aim-game is the
guaranteed fallback that needs zero capture engineering (game on the local swapchain -> WGC full-rate, which
is exactly why standalone got 218 frames in an earlier non-streamed moment). HONESTY: Part A is proven; Part B
is hypotheses ranked by prior, each falsifiable by one fps measurement; no FROZEN-v1 / PoAC / chain / IOTX;
the 4 non-screen pillars are at 100% and independent of all of this — the deep dive only raises the
coupled-retina/lag sample RATE. Related: [[s-retina-wgc-process-isolation-scope]],
[[project_dualconnection_capture_blind_finding]], [[recursive_verification_first_pattern]].
