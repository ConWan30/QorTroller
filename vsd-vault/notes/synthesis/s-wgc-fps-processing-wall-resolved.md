---
type: synthesis
id: s-wgc-fps-processing-wall-resolved
title: WGC fps bottleneck RESOLVED — per-frame processing, not the capture surface; slice-at-source + phaseCorrelate reach the ~39fps delivery ceiling (supersedes the s-wgc-fps-deepdive-workflow backend funnel)
created: 2026-06-27T07:30:00Z
modified: 2026-06-27T07:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Supersedes Part B of [[s-wgc-fps-deepdive-workflow]] (the E0-E5 capture-PATH backend funnel). Part A of that
note — and [[s-retina-wgc-process-isolation-scope]] — STAND: process isolation is still ruled out. What is
REFUTED is the leading hypothesis that fullscreen Remote Play bypasses DWM so WGC cannot SAMPLE the frames,
which is what scoped the windowed / Win-graphics / OCR / DXGI / OBS funnel.

THE MEASUREMENT TRAP (why cycle-40/41 mis-diagnosed it). `scripts/validate_wgc_standalone_fps.py` reports
`rgc.frames_seen`, which increments only AFTER `frames_to_motion` succeeds (qortroller_retina_capture.py:152)
— it measures POST-PROCESSING throughput, not raw WGC arrival. So cycle-40's "standalone == in-bridge ==
~1.6fps -> capture surface is the ceiling" was reading the processing rate in BOTH cases; the test could not
distinguish "surface slow" from "callback slow". The decisive probe this session was a NO-OP callback that
just counts arrivals: raw WGC = ~39fps. With MPO/overlay off (operator), static == motion == ~7fps — a FIXED
per-frame cost, content-independent. The bottleneck was the per-frame callback, not the surface; the funnel is
moot (no windowed/DXGI/OBS needed to GET frames — WGC already delivers ~39fps).

THE REAL WALL (a second correction). Slicing the frame before the convert — the obvious fix — was necessary
but NOT sufficient: a per-stage microbench showed dense `cv2.calcOpticalFlowFarneback` (~37-200ms, content-
dependent) was ~54% of the post-slice frame time and UNCHANGED by the slice (it already ran on the downscaled
gray). The pipeline only ever consumed the MEAN of that dense field — a single global yaw/pitch pan — so
`cv2.phaseCorrelate` computes it DIRECTLY ~18x faster. Coupling scores via Pearson r (scale-invariant), so the
proxy's absolute scale is irrelevant.

SHIPPED (2 commits on feat/l9-consistency-adversarial-harness, NOT pushed):
- `cab15fdc` slice-at-source: stride-slice `frame.frame_buffer` by the live downscale BEFORE `_to_u8_bgr`, so
  the 6MB ascontiguousarray + HDR float-normalize + grayscale run on ~1/d**2 the pixels. `_to_u8_bgr` /
  `to_gray_small` untouched (slice at the call site; `to_gray_small` gets downscale=1 — no double-down). The
  governor shape-guard re-baseline is preserved.
- `eb9eec27` phaseCorrelate: `cv_motion.frames_to_motion` swaps dense Farneback for `cv2.phaseCorrelate`
  global-pan — same `FrameMotion` return + same negation sign (empirically: +x scene pan -> yaw_rate<0,
  identical to the old mean-flow convention; Hanning window cached by shape). +6 unit tests
  (`frames_to_motion` was the live-validated I/O boundary, previously untested).

OFFLINE PROOF: slice + phaseCorrelate = ~3.3ms/frame (~300fps ceiling) vs the old Farneback wall. Processed
rate is now bounded by the ~39fps WGC DELIVERY, not the callback. PV-CI 182, 0 invariants touched, no test
regressions (51 passed across the retina/cv_motion/governor/coupling surface).

OPEN GATE (why this note is `likely`, not `certain`): live operator validation on the rig —
`validate_wgc_standalone_fps --monitor 1 --seconds 30` while playing should show `frames_seen` ~7 -> ~30-40,
and `rgc.status()` should still show COUPLED_CLEAN on coupled play (confirming the absolute phaseCorrelate sign
AND that coupling survives the estimator swap). Until that runs, the offline ceiling is proven but the
end-to-end verdict is not.

NET: Remote Play CAN feed the coupled-retina screen-lobe at usable rate; the cycle-41 "native-PC strictly
required for the lag pillar" re-scope is RELAXED to "preferred, not required". The 4 non-screen pillars are
unaffected. No FROZEN-v1 / 228B PoAC / chain / IOTX touch; advisory presence lobe only.
