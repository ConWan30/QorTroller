# B2 instrumented capture — the R2^B2 premise, measured (2026-07-03)

Closes G0's needs-capture verdict with a live measurement. Daemon `b2trace` ran the full producer PLUS a new
per-frame B2 trace (RETINA_B2_TRACE_ENABLED: every frame's `center_roi_redness` -> retina_b2_trace.jsonl,
512-sample batches flushed on a daemon thread — zero frame-callback I/O; 0 frame stalls). One BR match:
13,312 samples over 894s at ~14.9 Hz effective, 10 composite AUTHORED kills as ground truth (the producer
worked again: 10 AUTHORED; the dedup fix live — counters now exact).

## Result — B2 does NOT reliably mark kill moments (as measured)

| discriminator | per-kill hit | random-window control | lift |
|---|---|---|---|
| peak amplitude >= ambient p95 | 4/10 | 25% | ~1.6x chance |
| onset derivative (d-red) >= p99 | 6/10 | 34% | ~1.8x chance |

Neither the absolute redness peak nor the flash-onset derivative separates kill windows from random
same-length windows with anything approaching trigger-grade reliability. A B2-triggered classify would miss
40-60% of kills AND fire ambiently (combat scenes are red-noisy).

**PREMISE VERDICT: REFUTED as a trigger, at this sampling and ROI.** Two recorded caveats for any revisit:
(1) ~15 Hz effective trace under-samples a ~100-200ms hitmarker flash (the WGC duty/downscale governs the B2
feed rate); (2) the ROI (frac=1.0 centre) dilutes the small crosshair-local hitmarker glyph in scene redness.
A higher-rate trace or a tight hitmarker-shaped ROI could change the answer — but this is what the live
`_th2_oracle` channel actually sees, so B2-as-trigger over the CURRENT channel is not viable.

## Consequence for the architecture (settled)

- **Dense-tail stays the density mechanism** (already shipped, live-validated: 5 matches of composite
  AUTHORED). The HOLD-2 fork choice (dense-tail-now over instrumented-capture-first) is retroactively
  fully vindicated — waiting on B2 would have gated the working producer on a premise that measured false.
- **B2 remains a coupling-EVIDENCE channel** (the windowed th2_coupling aggregate: 5/26/55 coupled_true
  across death-only vs kill-heavy matches — real at match granularity), NOT a per-kill trigger.
- The R2^B2 standing rail (B2 never classifies outside an R2 window) stays pinned — it is about what B2
  is ALLOWED to do, and remains correct whether or not B2 is ever wired as an in-window trigger.
- The conjunction verdict (L4) should weight B2 as corroborating coupling evidence, not as a required leg.

This closes Fusion Increment 1 in full: G1' + G0 + W.1 + W.2 + G2' + G3 (5 live matches) + refinements
(stall-recut, gated cut, dedup) + the B2 premise measurement.
