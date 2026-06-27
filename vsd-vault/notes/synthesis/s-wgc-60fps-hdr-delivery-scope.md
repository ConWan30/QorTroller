---
type: synthesis
id: s-wgc-60fps-hdr-delivery-scope
title: Path to 60fps HDR coupled-retina — the callback is already 60fps-ready (HDR <=7.7ms/frame post-fix); the binding constraint is WGC DELIVERY (~39->60), dominated by the Remote Play HDR stream decode rate
created: 2026-06-27T08:30:00Z
modified: 2026-06-27T08:30:00Z
phase: VSD-LOOP
status: draft
confidence: possible
effort: 70
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the meticulous path to 60fps HDR coupled-retina. Builds on [[s-wgc-fps-processing-wall-resolved]] (the
slice + phaseCorrelate fix) and supersedes the backend-funnel framing of [[s-wgc-fps-deepdive-workflow]];
Part A of [[s-retina-wgc-process-isolation-scope]] still stands.

THE REFRAME (load-bearing, microbenched). The HDR callback is ALREADY under the 60fps budget at every
downscale -- the slice-at-source fix turned the old full-1080p scRGB-float `_to_u8_bgr` (~164ms) into a sliced
op:
  d=4: scRGB-float 7.66ms | fused-luma 5.24ms | HDR10-uint16 4.34ms   (60fps budget = 16.7ms)
  d=6: scRGB-float 3.55ms | fused-luma 2.49ms | HDR10-uint16 2.03ms
  d=8: scRGB-float 1.40ms | fused-luma 1.36ms | HDR10-uint16 1.47ms
Even the WORST HDR case (scRGB-float, d=4) is 7.66ms = <half the 16.7ms frame budget; >2x margin at d=4, more
at d=6/8. So Front B (callback) is essentially DONE for 60fps. The fused HDR->gray-luma lever (compute weighted
luma in one float pass, skip the 8-bit BGR materialization + cvtColor) saves ~30% at d=4 but is marginal at
d=6/8 -- headroom insurance, not required.

THE BINDING CONSTRAINT IS DELIVERY, NOT THE CALLBACK. The live SDR run was 32fps PROCESSED = ~31ms/frame
effective, but the SDR callback is ~4ms -- the other ~27ms is the callback IDLING between WGC frame arrivals.
Raw WGC delivery is ~39fps (no-op probe), and that ~39 ceiling is present IN SDR ALREADY (32fps processed, 39
raw). So 60fps is not currently delivered even in SDR -- it is a Remote Play stream / present-rate reality, not
an HDR-specific or a callback problem. HDR only RAISES the bar (HDR10 needs ~25% more bitrate for the same
fps/resolution -> more likely to be bandwidth-throttled below 60).

EXPERIMENT MATRIX -- FRONT A (raise WGC delivery ~39 -> 60; the whole game). Cheapest-first; STOP at the first
config that yields >=55fps RAW delivery (no-op probe) in HDR:
  A0 -- MAKE-OR-BREAK, operator, ~2 min: measure the TRUE Remote Play stream fps in HDR. PS Remote Play ->
       Settings -> Video Quality: Resolution=1080p, Frame Rate=HIGH(60). Check the in-stream connection stats.
       If the stream itself decodes <60 distinct HDR frames, 60fps coupled-retina is STREAM-BOUND -> no capture
       engineering fixes it; accept ~39-45, or drop HDR for the lag pillar (SDR is cheaper bitrate -> closer to
       60), or move the lag pillar to a native-PC aim-game. THIS GATE decides whether 60 is reachable at all.
  A1 -- raw-arrival no-op probe WITH HDR active: is raw delivery still ~39, or does HDR's present path change
       it? Compare to the SDR ~39. (Extend validate_wgc_standalone_fps / add a no-op `--raw-arrival` mode.)
  A2 -- HDR present path: HDR fullscreen may RE-ENGAGE the MPO/independent-flip overlay the operator disabled
       for SDR. Re-check Win11 graphics (Optimizations for windowed games / Hardware-accelerated GPU scheduling)
       WITH HDR on; A/B monitor-capture vs window-capture in HDR.
  A3 -- network/encode headroom for HDR60: wired or 5GHz, bitrate headroom; HDR10 doubles the per-frame data.

EXPERIMENT MATRIX -- FRONT B (keep the callback <=16.7ms; ALREADY WON, do only if a future regime needs it):
  B0 -- per-stage timing diag in the callback (every Nth frame, like the existing RGC diag) to confirm the live
       HDR `_to_u8_bgr` matches the bench AND to report whether WGC delivers HDR as scRGB-float16 (expensive
       path) or HDR10-uint16 (the cheap `>>8` path).
  B1 -- fused HDR->gray-luma (skip the BGR uint8 + cvtColor): ~30% at d=4. Implement only if A succeeds AND a
       contended regime erodes the margin.
  B2 -- governor already raises downscale 4->8 under low fps (target_fps=60); confirm it drives toward d=6/8 in
       HDR (1.4-3.6ms) before B1. The dormant `region_scale` crop control (governor produces it, tune() never
       applies it) is a further unwired lever.

DECISION: 60fps HDR is reachable ONLY IF the Remote Play stream delivers ~60 distinct HDR frames -- a
network/encode/stream-settings question (A0), not a capture-code one. The callback is ready (7.66ms worst-case
HDR). HONEST RISK (why `possible`, not `likely`): the ~39 ceiling holds in SDR already, so the stream/present
rate is the limit today, and HDR makes 60 harder; A0 may show the stream caps below 60 in HDR, in which case
the honest outcome is "best stream the link allows" + SDR-or-native-PC for the 60fps lag pillar. No FROZEN-v1 /
228B PoAC / chain / IOTX touch; advisory presence lobe only; the 4 non-screen pillars are unaffected.
