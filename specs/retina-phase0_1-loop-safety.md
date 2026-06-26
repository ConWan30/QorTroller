# Phase 0.1 — Retina event-loop loop-safety remediation

**Status:** R1 in progress; R2–R5 scoped, operator-gated.
**Scope:** advisory-only (no verdict-gate wiring). No FROZEN-v1 / 228-byte PoAC change. Default-OFF preserved. No chain/IOTX.
**Predecessor:** VSD cycle-22 `s-trio-retina-controller-lobe-first-scope`; Phase-0 commit `c124b9f8` (hook → `asyncio.to_thread`).

## Goal
With retina **fully enabled** (perception + full provenance stack: DA upload + w3bstream + PDA), keep the
bridge event loop clean — no catastrophic stalls, sustained starvation under a small budget — so the
Phase-0 advisory controller-lobe spine runs on the live grind without degrading ingestion.

## Evidence (A/B, 2026-06-26, same machine + controller)
Two 240 s live runs. Baseline = all retina flags on. A/B = `RETINA_DA_UPLOAD` + `W3BSTREAM_VALIDATION` +
`W3BSTREAM_ENFORCE_ON_INGEST` + `PDA_ATTESTATION` + `DA_WITNESS` all OFF; `RETINA_PERCEPTION_ENABLED` ON.

| Config | starvation @90 checks | max excess | 96 s-class stall | retina filling |
|---|---|---|---|---|
| Baseline (full I/O) | 10 events | 2.53 s → **94.28 s** | **YES** | +82 rows/5 min |
| A/B (heavy I/O OFF, embed ON) | 12 events | **2.52 s** | **NO** (≤2.52 s) | +107 rows/5 min |

Two separable causes:
1. **Sustained starvation = the CPU embed.** Near-identical with all heavy I/O off → the embed is the
   floor. It is **GIL-bound pure-Python** (`embed_controller_window` per-frame loop + the
   **O(window²)** `_check_dynamics(snaps[:i+1])` growing slice), so `asyncio.to_thread` structurally
   cannot relieve it (a worker thread holding the GIL still blocks the loop thread).
2. **The catastrophic ~96 s stall = per-record I/O.** Vanished with DA/w3bstream/PDA off — driven by
   per-record DA upload (~2×17 KB/s) + w3bstream-enforce + PDA + SQLite write-lock contention on a
   ~61 k-row `retina_event_log`.

## Remediation (prioritized by the A/B)

### Primary — CPU embed (fixes the sustained floor)
- **R1 — kill the O(window²).** `_check_dynamics` only uses the last `horizon+1` samples; pass
  `snaps[i-dynamics_horizon : i+1]` at the call site instead of `snaps[:i+1]`. Behavior-preserving
  (identical last `horizon+1` window → identical pred/actual/residual). O(window²) → O(window).
  Pure refactor, lowest risk, likely the single biggest win. **(this change)**
- **R2 — throttle cadence.** Decouple the embed from the 1 s session loop; run every Nth tick / fixed
  cadence. Advisory perception does not need per-second granularity. Cheap insurance.
- **R3 — process pool (only if R1+R2 insufficient).** Run the embed in a `ProcessPoolExecutor` to truly
  escape the GIL. Heavier (snap serialization, trio-retina import in worker). Gate on measurement.

### Secondary — I/O tail (kills the catastrophic spikes)
- **R4 — batch DA upload off the per-record path.** Periodic background drain uploads accumulated rows
  in bulk, not 2×/record. (The `.env` comment says "upload … BULK" — per-record is the regression.)
- **R5 — SQLite contention.** Index `retina_event_log` for its query patterns; batch inserts; route
  retina writes through the dedicated `vapi-persist` pool so they don't starve the loop's own
  `to_thread(store…)` calls.

## Files touched (anticipated)
- `bridge/vapi_bridge/retina_controller_embedder.py` (R1 call-site bounded slice)
- `bridge/vapi_bridge/retina_perception.py` / `dualshock_integration.py` (R2 cadence gate)
- `bridge/vapi_bridge/retina_da_upload.py` + a drain task (R4)
- store schema/migration for an index (R5)
- `bridge/tests/test_retina_*` perf/equivalence tests

## Acceptance (measurable)
Re-run the 240 s live observation with **all** retina flags ON →
- **0 stalls > 10 s; max excess < 1.0 s; ≤ 2 starvation events / 240 s** (loop effectively clean),
- `retina_event_log` still filling with populated `state_commitment_hex`,
- 19 retina tests + `test_retina_eventloop_safety` green, PV-CI 182, 228 B PoAC + default-OFF intact.

R1 unit acceptance: `_check_dynamics(full_slice)` == `_check_dynamics(bounded_slice)` for the same frame
(behavior-preserving), and existing embedder tests unchanged.

## Boundaries
No FROZEN-v1 / 228-byte PoAC. Advisory-only (no verdict wiring). Default-OFF preserved. No chain/IOTX.
R3 only if measured-necessary.

## Recommended sequence
**R1 first** (pure refactor + equivalence test, no hardware) → re-measure → **R4** (batch DA) → re-run
the live acceptance. R1 + R4 may suffice; R2 is cheap insurance; R3 is the fallback.
