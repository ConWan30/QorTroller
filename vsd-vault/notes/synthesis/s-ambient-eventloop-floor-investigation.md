---
type: synthesis
id: s-ambient-eventloop-floor-investigation
title: Ambient event-loop floor investigation — the residual bridge starvation is NOT retina (R1 fixed that); attribute and reduce the machine/fleet/WAL floor, measurement-first
created: 2026-06-26T12:10:00Z
modified: 2026-06-26T12:10:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Closes the Phase 0.1 retina arc and opens a dedicated workflow for the residual. Builds on
[[s-retina-phase0_1-loop-safety]] and [[project_retina_phase0_live_starvation_finding]].

WHAT THE PHASE 0.1 ARC ESTABLISHED (so this note doesn't re-litigate it):
  - R1 (bound _check_dynamics window, committed) is the decisive, reliable win: the catastrophic
    embed-driven stall dropped from ~94.28s to a typical max of 2-5s. KEEP.
  - R4 (batch DA off the per-record path) was DROPPED: da_router is an in-memory MOCK, so there was
    never heavy DA network I/O to relieve; the drain only added a thread + bursty SQLite logging.
    Two loaded runs put R4's effect inside the noise band (max excess 11.53s vs 3.12s across runs).
    R4 is correct for a REAL DA node and stays documented in specs/retina-phase0_1-loop-safety.md;
    it is not warranted on the mock testbed.

THE LOAD-BEARING FINDING (why this is a NEW workflow, not more retina work): the residual event-loop
starvation is AMBIENT, not retina. Evidence: (a) an IDLE bridge (retina producing nothing) still had
~16 starvation events / 240s, max 4.88s; (b) starvation does not scale with retina load — a loaded run
with FEWER retina rows (37) had MORE starvation than one with more; (c) high run-to-run variance
(max excess 2.05 / 11.53 / 3.12s across comparable loaded runs) is the signature of machine/OS/GC/IO
noise, not a single hot code path. R1 already made the retina embed cheap; what remains is the bridge's
own baseline load. The strict bar (<1.0s max excess, <=2 events/240s) is bounded by this floor and is
NOT achievable by any further retina-side lever.

INVESTIGATION WORKFLOW (measurement-first; each step ends in a HOLD):
  S1 ATTRIBUTE. Instrument the starvation events to learn WHICH operation holds the loop. Options:
     enable asyncio debug mode (slow-callback logging) for a bounded window; add per-callback timing
     around the loop_health check; or sample the loop thread's stack at starvation onset. Goal: a
     ranked list of the sync operations (by total loop-held time) that cause the floor.
  S2 BISECT THE FLEET. Reuse the STABILITY-arc bisection discipline (MINIMAL_TASK_MODE): run idle
     baselines with subsets of the ~29-agent background fleet disabled, to attribute the idle 16/240s
     floor to specific pollers/tasks. The agent poll loops + heartbeats are the prime suspects.
  S3 WAL / SQLite. Measure checkpoint timing + write-lock contention on the ~1.5 GB ~/.vapi/bridge.db;
     audit index coverage on high-cardinality hot tables (records 192k+ per the EVENTLOOP invariant
     note). A WAL checkpoint or an unindexed scan on the loop thread is a classic ambient stall.
  S4 OS / GC. Rule in/out Windows scheduling + CPython GC pauses (gc stats around starvation; the
     94.28s/11.53s outliers especially smell like a checkpoint or a paging/GC stall, not steady load).
  S5 CANDIDATE LEVERS (only after S1-S4 attribute the floor; no guessing): move any remaining
     loop-thread sync work to to_thread/executor; throttle agent poll cadences; WAL checkpoint tuning
     (wal_autocheckpoint / periodic PRAGMA wal_checkpoint(TRUNCATE) off-loop); add missing indexes;
     right-size the persist ThreadPoolExecutor. Each lever is measured against the idle + loaded
     starvation distribution before/after.

ACCEPTANCE: the floor is ATTRIBUTED to named causes with measured contributions (not asserted), and
each proposed lever has a measured before/after on the starvation distribution. Whether the strict bar
is reachable is itself an output of S1-S4 — it may turn out the bar must be relaxed to the machine's
achievable floor, which is an honest result.

HONESTY RAILS: measurement-first — no code change before S1-S4 attribute a cause. No FROZEN-v1 / 228B
PoAC. No chain/IOTX. This is the residual after the STABILITY arc + R1; it is the bridge's baseline
load, and reducing it is a general-bridge effort, not a retina one. Variance is large, so every claim
needs multiple runs (idle + loaded), not a single sample — the Phase 0.1 single-run mis-reads
(the non-reproducing 11.53s) are the cautionary precedent.
