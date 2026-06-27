---
type: synthesis
id: s-retina-phase0_1-loop-safety
title: Phase 0.1 — A/B isolates the retina event-loop starvation into two causes (GIL-bound CPU embed = sustained floor; per-record I/O = catastrophic spikes); to_thread fixes neither alone
created: 2026-06-26T11:40:00Z
modified: 2026-06-26T11:40:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Records the empirical close of the cycle-22 Phase-0 live finding. The Phase-0 commit `c124b9f8`
(retina hook -> asyncio.to_thread) was necessary but the live run still starved the loop (one ~96s
stall). A controlled A/B then isolated WHY. Builds on [[s-trio-retina-controller-lobe-first-scope]].
Full plan: specs/retina-phase0_1-loop-safety.md.

THE A/B (2026-06-26, same machine + controller, two 240s live runs):
  - Baseline (all retina provenance flags ON): 10 starvation events @90 checks, escalating to a single
    ~96s loop stall (expected sleep 2.0s, actual 96.28s).
  - A/B (DA_UPLOAD + W3BSTREAM_VALIDATION + ENFORCE + PDA + DA_WITNESS all OFF; PERCEPTION ON):
    12 starvation events @90 checks, max excess 2.52s, NO 96s-class stall. Embed still produced
    (retina_event_log +107 rows/5min vs +82 baseline -- faster without the heavy I/O).

TWO SEPARABLE CAUSES (the load-bearing result):
  1. SUSTAINED starvation = the CPU EMBED. Near-identical with all heavy I/O off, so the embed is the
     floor. It is GIL-bound pure-Python: embed_controller_window's per-frame loop + the O(window^2)
     _check_dynamics(snaps[:i+1]) growing-slice. asyncio.to_thread CANNOT relieve it -- a worker thread
     holding the GIL still blocks the event-loop thread. This is why Phase-0's to_thread fix, though
     correct (it removed the inline-blocking class), did not eliminate starvation.
  2. CATASTROPHIC ~96s spike = per-record I/O. Vanished with DA/w3bstream/PDA off. Driven by per-record
     DA upload (~2x17KB/s) + w3bstream-enforce + PDA + SQLite write-lock contention on a ~61k-row
     retina_event_log.

WHY THE A/B MATTERED: the remediation differs sharply by cause -- threading is useless for the GIL-bound
embed, so the fix there is algorithmic (O(window^2)->O(window)), cadence throttling, or a process pool;
the I/O tail is fixed by batching DA off the per-record path + SQLite indexing. Without the A/B we'd have
guessed. This is verification-first: the live P-check proved the implementation (to_thread) did not meet
the system goal (loop safety), and the A/B V-check told us precisely what would.

REMEDIATION (prioritized, specs/retina-phase0_1-loop-safety.md):
  R1 (this change) -- _check_dynamics only uses the last horizon+1 samples; pass the bounded slice at the
     call site. Behavior-preserving, O(window^2)->O(window). Likely the single biggest win.
  R2 throttle embed cadence (not every 1s tick). R3 process-pool the embed iff R1+R2 insufficient.
  R4 batch DA upload off the per-record path. R5 index/serialize retina_event_log writes.

HONESTY RAILS: advisory-only (no verdict wiring); no FROZEN-v1 / 228B PoAC change; default-OFF preserved;
no chain/IOTX. The A/B left bridge/.env restored to all-true. Acceptance is a measured re-run (all flags
ON) with the loop clean (no >10s stalls; max excess <1.0s; <=2 events/240s) -- promotion on measurement,
not assertion. Related: [[project_retina_phase0_live_starvation_finding]].
