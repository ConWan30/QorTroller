---
type: synthesis
id: s-wgc-capture-enhancements-built
title: WGC capture enhancements BUILT — presentation-timestamp coupling + CPU ROI-crop convert (bridge retina path)
created: 2026-06-28T15:30:00Z
modified: 2026-06-28T16:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 110
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

BUILT (`3f1854e6`, bridge retina path `qortroller_retina_capture.py::WgcFrameSource`; advisory/default-off;
no FROZEN-v1 / 228B PoAC / chain / IOTX / firmware). Two of the WGC enhancements scoped in the cycle-51
arc — the two cheapest wins that most directly serve the latency invariant ([[s-cross-channel-latency-invariant]])
and the combat-burst observer-effect cost ([[s-retina-presence-product-thesis]]).

**#1 Presentation-timestamp coupling.** `on_frame_arrived` fed `time.time()` (callback-arrival, jittery) to
all three screen channels; the WGC frame already carries its presentation time (`frame.timespan`, previously
ignored). New pure `align_timespan_ms()` maps `timespan` onto the HID wall-clock EPOCH (one-time offset
anchor) with QPC precision — removing callback-scheduling jitter from the screen-side coupling timestamps.
Fail-open to wall-clock on missing/zero/non-monotonic `timespan`; the governor fps/stall clock stays on
wall-clock arrival (it must measure real cadence). Payoff: tighter `lag_ms` → cleaner cross-channel lag
agreement (the invariant's MAD separation). This payoff is **measurable only on live WGC frames** — the
offline tests prove correctness (epoch anchor, presentation-delta tracking vs wall jitter, fail-open), not
the jitter reduction itself.

**#2 CPU ROI-crop convert.** New pure `convert_for_channels()` produces a direct numpy-luma full-frame GRAY
(geometric channel + B1 luminance, which crops it for free) and converts ONLY the small B2 center-ROI to BGR
— eliminating the full-frame BGR materialization. One shared HDR `lum_scale` across both outputs (recomputing
from the ROI would inject false flow/redness drift). Note: literal GPU-side crop-before-readback is NOT
possible (`windows_capture` reads back the full window/monitor before the callback) — this is the achievable
CPU-side form.

**Microbench (per-frame convert, strided 1080p / downscale 4 = 270×480×4):** SDR uint8 **+15%**, HDR uint16
**+19%**, HDR float **+55%** (2.02 → 0.90 ms). The HDR-float win is the load-bearing one — HDR games
(Warzone-class) made the old path materialize a full-frame float→BGR image every frame. Better than the
plan's honest "modest" projection on exactly the regime that matters.

**Verification:** +8 unit tests (pure helpers, no WGC needed); 31 retina tests pass; full `l9_presence` 307
pass; PV-CI 182 unchanged.

**LIVE VALIDATION — Part A, 2026-06-28 (`scripts/validate_wgc_standalone_fps.py --monitor 1`, real WGC frames):**
- **Timespan units CONFIRMED.** First-frame raw `timespan=375253384500` → `/10000` = `37,525,338 ms`. Decoded
  as QPC 100 ns ticks that is 375,253,384,500 × 100 ns = ~37,525 s = **~10.4 h = system uptime**, exactly what
  WGC `SystemRelativeTime` (relative to boot) should read. So `_TIMESPAN_TICKS_PER_MS = 10000` is RIGHT —
  open gate #1 below is RESOLVED, not assumed.
- `ts_source="timespan"` on every sample (never `wall_fallback`); `ts_offset_ms` STABLE across all samples
  (one-time epoch anchor holds); `screen_ts = timespan + offset` lands on the wall-clock epoch (~1.78e12 ms),
  so HID↔screen lag stays meaningful.
- #2 convert: 582 frames processed, `frame_format=uint8(1080,1920,4)` (SDR BGRA 1080p), **zero frame-
  processing errors** — the direct-luma gray + ROI-only BGR path is clean on real frames.
- fps read ~19 (PARTIAL) only because this was DESKTOP capture (no game motion / low present rate), NOT a
  regression — content-/environment-bound. The delivery-bound reading + HDR `fmt` come from the in-game pass.

**Open gate (why still `likely`, not `certain`):**
1. ~~`frame.timespan` units unverified~~ — **RESOLVED 2026-06-28 (Part A above): `/1e4` confirmed on a live frame.**
2. #1's jitter-reduction PAYOFF + the latency-invariant FAR still need the operator-gated COUPLED pass
   (bridge + Remote Play + controller): steadier `lag_ms`, `COUPLED_CLEAN` holds, and the genuine-vs-spectate
   `calibrate_tau_lag` separation (Part B, `scripts/capture_latency_calibration.py` + the Warzone runbook).

**Deferred (same cycle-51 WGC menu, NOT built here):** HDR-correct B2 color space, capture-source attestation
+ retina CaptureHealthMonitor (fail-closed), adaptive duty-cycle, and the off-device sidecar (the lag-free
production answer). Those remain the higher-effort items.
