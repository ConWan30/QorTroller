---
type: synthesis
id: s-retina-remote-play-process-isolation
title: Remote-Play coupled-retina via PROCESS ISOLATION — the callback-fixed retina is GIL/agent/DB-starved to ~7-12fps IN-BRIDGE; a sole-capturer subprocess emitting FrameMotion over IPC lets the coupling oracle run at ~32fps in production. Operator commits Remote-Play as QorTroller's novel surface (NOT native-PC). Phase-0 validate-first before the IPC build.
created: 2026-06-27T11:05:00Z
modified: 2026-06-27T11:05:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 480
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

OPERATOR DECISION (load-bearing): QorTroller targets REMOTE PLAY streaming as a first-class novel surface, NOT
native-PC. The coupled-retina / lag pillar must work over the stream. Any necessary engineering is in scope.
This note scopes the execution plan; native-PC fallback ([[s-coupling-threshold-calibration]] INSEPARABLE
outcome) is REMOVED from the table for the lag pillar.

DIAGNOSIS (measured live 2026-06-27, BR active-aim over Remote Play). The per-frame callback is ALREADY fast —
slice-at-source + phaseCorrelate = ~3.3ms/frame, standalone ~32-39fps ([[s-wgc-fps-processing-wall-resolved]]).
But IN-BRIDGE the retina runs at only ~7-12fps and DECAYS over minutes (ema_fps 17.66 -> 7.35), and BR-aim
coupling is thin (~0.075 vs shuffle null ~0.022 — positive ~3.4x separation, but far below the 0.20 threshold
and below the 0.14-0.21 the pre-surfacing recap saw). Two corrections this session: (1) the standalone
validator returns 0 ALONGSIDE the bridge because BOTH capture monitor 1 -> double-capture starves the second
WGC pool; (2) a process-env shed (RETINA_DA_UPLOAD/W3BSTREAM_ENFORCE/PDA=false) did NOT take — the bridge
reads `.env` over shell env (40 DA/w3bstream lines still fired), so both runs were full-stack. NET: the binding
constraint is NOT the surface, NOT the callback, NOT delivery — it is **GIL / event-loop / SQLite contention**:
the retina callback fights the agent fleet + 5.4GB DB + per-record provenance for the same Python GIL, so it
never reaches its ~32fps potential. The ambient floor is machine-bound in-process (S5 conclusion) — so the
answer is to take the retina OUT of the bridge process.

THE FIX — PROCESS ISOLATION (resurrects the cycle-40/41 Phase-1 design, shelved for the fps problem; it is the
CORRECT fix for the contention problem). A dedicated worker SUBPROCESS becomes the SOLE capturer of monitor 1:
owns WGC capture + stride-slice + `_to_u8_bgr` + phaseCorrelate, runs in its own interpreter = its own GIL =
~32-39fps immune to the bridge's agent/DB/provenance contention. It emits tiny `FrameMotion {ts_ms, yaw_rate,
pitch_rate}` (~24 bytes) over a `multiprocessing.Queue` (or a stdout-jsonl pipe) at ~32fps — NO raw frames
cross the boundary. The BRIDGE stops capturing entirely (no double-capture) and instead CONSUMES the
FrameMotion stream, feeding it into the existing coupling oracle alongside the live HID right-stick stream ->
coupling at full rate. Reuse: `WgcFrameSource`/`RetinaGameCaptureCore` (move into the worker verbatim),
`cv_motion` (slice+phaseCorrelate already done), the L9 coupling oracle (`coupling.py`, unchanged — it already
consumes FrameMotion + HID), the dualshock HID feed. The only NEW surface is the worker entrypoint + the IPC
boundary + the bridge-side consumer that replaces the in-process `feed_frame_motion` call site.

PHASE 0 — VALIDATE FIRST (the cycle-40 lesson: prove before building the IPC). Edit `bridge/.env`
`RETINA_GAME_CAPTURE_ENABLED=false` (bridge stops capturing) + run a STANDALONE subprocess capturing monitor 1
WHILE the full bridge runs (agents + DB + provenance all live). Measure the subprocess `frames_seen` over 30s.
GATE: subprocess >= ~30fps with the bridge full-stack but NOT capturing -> contention-isolation CONFIRMED ->
build Phase 1. If subprocess ALSO < ~15fps with the bridge not capturing -> the contention is cross-process
(CPU/GPU/memory-bandwidth saturation, not just GIL) -> escalate (CPU affinity / priority / shed agents via a
`.env` MINIMAL_TASK_MODE). This Phase-0 is the missing measurement: today's standalone-0 was double-capture, NOT
a real isolation test (the bridge was still capturing). Revert the `.env` flag after.

PHASE 1 — BUILD (only if Phase-0 passes). `scripts/retina_capture_worker.py` (worker: WGC sole-capturer ->
FrameMotion over the IPC channel; clean-exit + heartbeat). Bridge: spawn the worker (default-off flag
`retina_process_isolation_enabled`), consume FrameMotion into the coupling oracle, FAIL-OPEN (worker death /
stale heartbeat -> lobe abstains, never fabricates, never blocks ingestion). Tests: worker emits well-formed
FrameMotion; bridge consumer feeds the oracle; fail-open on worker death; no double-capture; PV-CI 182
unchanged.

PHASE 2 — SIGNAL DESIGN (only if coupling still thin at ~32fps). Re-measure BR-aim coupling on the de-starved
lobe. If still ~0.075: investigate (a) lag-window alignment for Remote-Play decode/stream latency
(governor lag_window_ms=500 / resample_hz=120 may be mistuned for the stream), and (b) whether phaseCorrelate's
GLOBAL pan captures small BR aim corrections (the right stick may move the reticle more than it globally pans
the world) -> a local/ROI motion estimator may track aim better than global pan. Then resume the
[[s-coupling-threshold-calibration]] campaign on the faster lobe.

HONESTY RAILS: advisory / default-off until the coupling-threshold campaign calibrates on the faster lobe
(the FAR-controlled threshold still gates COUPLED_CLEAN). No FROZEN-v1 / 228B PoAC / chain / IOTX. The 4
non-screen pillars (L4/L5/L6 + L9 controller-lobe) are unaffected and do not depend on any of this. Related:
[[s-retina-wgc-process-isolation-scope]], [[s-wgc-fps-processing-wall-resolved]],
[[project_retina_phase0_live_starvation_finding]], [[recursive_verification_first_pattern]].
