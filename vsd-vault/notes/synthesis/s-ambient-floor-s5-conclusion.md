---
type: synthesis
id: s-ambient-floor-s5-conclusion
title: S5 conclusion — the offload lever is already done and the bloat is core-PoAC-dominated; the residual event-loop floor is machine-bound (GIL + 5.4GB DB), so the strict bar is relaxed to the achievable floor (cycle-24's anticipated honest outcome)
created: 2026-06-26T14:30:00Z
modified: 2026-06-26T14:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Closes the ambient-floor investigation (cycle-24 scope -> cycle-26 S1-S3 findings -> this S5
conclusion). Builds on [[s-ambient-floor-s1-s3-findings]] and [[s-ambient-eventloop-floor-investigation]].
Operator decision (2026-06-26): accept the floor as machine-bound.

S5 DEEP V-CHECK (the build's first step revised its own premise):
  - **The offload lever (cycle-26 S5 lever #1) is ALREADY DONE.** grep-confirmed to_thread coverage in
    the hot agents: FleetSignalCoherenceAgent **8** (all contradiction/orphan/inversion checks +
    writes via `_check_*_sync` + `_write_*`/`_promote_to_wif`), the steward absorbed-ticker **4**
    (`await asyncio.to_thread(method)` per absorbed agent), Guardian/Sentry **2 each** (the
    trigger-fetch `_safe_get_triggers`). The STABILITY-9 arc threaded these. There is essentially NO
    offload headroom left -> the residual starvation is the **GIL** (to_thread'd pure-Python + SQLite
    still contend it; the exact R1/R4 lesson) plus the 5.4GB DB making each query heavy.
  - **The bloat is dominated by `records` (~925k rows) = core PoAC provenance, NOT safe to
    auto-delete.** The safe-to-prune telemetry tables (capture_health_log ~199k, retina_event_log /
    retina_da_upload_log ~62k each, agent_events ~65k ~= 388k rows) are a MINORITY of the ~1.5M-row
    total; pruning them won't meaningfully shrink 5.4GB. dbstat unavailable (SQLite built without the
    vtab), so per-byte attribution is inferred from row counts, but records is the largest table by a
    wide margin and PoAC rows carry the heaviest payload.

CONCLUSION: cycle-26's S5 plan (offload + prune) is largely VOID — offload is done, and the prune's
only high-impact target is off-limits (core data). The residual ambient floor (~2-5s max excess,
~15-30 starvation events/240s, high variance) is **machine-bound**: GIL contention from the
already-threaded CPU-bound agent work + the 5.4GB core-data DB + ambient Windows OS/GC. It is not
fixable retina-side (R1 was the win) nor agent-offload-side (done).

DECISION (operator): **accept the floor as machine-bound and relax the strict bar** (<1.0s max excess,
<=2 events/240s) **to the achievable floor**. This is exactly the honest outcome cycle-24's S5 step
explicitly allowed for ("the bar may need to be relaxed to the machine's achievable floor"). The
meaningful, shipped win remains **R1** (`fd4acdaa`): the catastrophic embed stall 94.28s -> 2-5s
typical. The remainder is the bridge's machine baseline.

REMAINING THEORETICAL LEVERS (NOT pursued — heavy and/or operator-design-gated, recorded for honesty):
  - records ARCHIVAL (not deletion) to shrink the DB — high impact, but records are core PoAC
    provenance (GIC-chain / grind refs); needs an operator-designed retention + archive strategy.
  - PROCESS-POOL the CPU-bound agents to escape the GIL — heavy refactor, cross-process serialization,
    higher risk; only if the floor ever becomes operationally blocking.
  - THROTTLE agent poll cadences — reduces starvation FREQUENCY (config, reversible) but not per-event
    severity, and trades agent responsiveness; low marginal value vs the machine floor.

HONESTY RAILS: S5 made NO bridge code change — the conclusion is that no safe high-leverage autonomous
lever remains; barreling into core-data deletion or a low-value change would have been the wrong move.
Measurement-first throughout (S1 asyncio-debug attribution, S2 bisect, S3 DB audit, S5 to_thread-grep
+ dbstat). No FROZEN-v1 / 228B PoAC; no chain/IOTX. The investigation is closed honestly: the floor is
characterized, attributed, and accepted as machine-bound; R1 is the durable improvement.
