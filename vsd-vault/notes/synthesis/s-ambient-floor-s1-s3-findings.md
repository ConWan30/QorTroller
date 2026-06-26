---
type: synthesis
id: s-ambient-floor-s1-s3-findings
title: Ambient floor S1-S3 results — the residual event-loop starvation is the agent fleet's inline DB work + a 5.4GB bloated DB; reachable only by S5 (offload + prune), not retina
created: 2026-06-26T13:55:00Z
modified: 2026-06-26T13:55:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Durable close of the cycle-24 ambient-floor investigation workflow ([[s-ambient-eventloop-floor-investigation]]).
S1-S3 executed measurement-first; S4 deferred (low priority); S5 is the build, operator-gated.
Extends [[project_retina_phase0_live_starvation_finding]].

S1 ATTRIBUTE (asyncio debug, 180s idle full bridge). Ranked by total loop-held time, the residual
floor is INLINE synchronous DB work in the operator-agent polling loops -- NOT retina, NOT the
session loop:
  - GuardianPollingLoop._run (operator_agent_guardian_polling.py) ~6.12s
  - FleetSignalCoherenceAgent.run (_run_once, 24 coherence rules) ~5.77s
  - SentryPollingLoop._run_loop ~1.37s
  - session loop (_run_ds_with_restart) only ~2.44s; retina absent entirely.
To the line: STABILITY-9 already offloaded the trigger-FETCH (_safe_get_triggers -> to_thread); the
paths it did NOT reach are the residual -- the SHARED _absorbed_ticker.tick_all() (guardian:186 +
sentry:168, ticks the 9 absorbed agents synchronously), _dispatch_one/_dispatch_one_cycle (draft
sign+DB write), and FSCA._run_once() (rule eval scanning fleet tables).

S2 BISECT (MINIMAL_TASK_MODE=true BISECT_BATCH=B2, 120s isolated). The 3 polling stewards spawned
ALONE (no session loop, no retina, no FSCA) still produced GuardianPollingLoop._run ~1.02s steady
-state -> confirms the stewards are a SUFFICIENT cause. The 6s spikes are CADENCE-DRIVEN: they hit
only when a DB-heavy absorbed agent fires on its own schedule (this 120s window mostly missed them)
-- that variance IS the high run-to-run noise seen across the loaded retina runs.

S3 DB AUDIT (read-only). bridge.db is 5.4 GB (~3.6x the cycle-24 note's 1.5GB assumption); records
= 923,316 rows (~5x the note's 192k); capture_health_log 198k, retina_event_log/da_upload_log 61k
each -- all unbounded-accumulating. The hot tables ARE indexed (records has 6 indexes,
fleet_coherence_log 5, the time-series tables are created_at-DESC indexed). So the DB-side cause is
BLOAT + un-covered absorbed-agent/FSCA query patterns, NOT missing indexes.

COMBINED VERDICT: the residual ambient floor = (a) agent-fleet inline sync DB work +
(b) a 5.4 GB bloated DB. This is a general-bridge concern, exactly as cycle-24 predicted. R1 was the
correct + sufficient retina-side fix; R4 was rightly dropped; R2 would not have helped. The strict
bar (<1.0s max excess, <=2 events/240s) is reachable ONLY by S5.

S5 LEVERS (prioritized; a future BUILD, not started here):
  1. Offload the inline steward paths to to_thread -- _absorbed_ticker.tick_all(), the dispatch
     path, and FSCA._run_once() -- the same pattern STABILITY-9 applied to the fetch path. Highest
     leverage; directly removes the GIL/loop hold.
  2. Prune/archive the unbounded tables (records 923k, capture_health_log 198k, retina_event_log +
     retina_da_upload_log 61k each) -- shrink the 5.4 GB DB, cut page-cache pressure for every query.
  3. (lower) right-size the persist executor; throttle absorbed-agent cadences.

SEQUENCE (operator-set): grok's cycle-25 experimental hardware tests (s-usb-bt-* dual-tether) close
first based on their results; THEN an operator-authorized autonomous VSD loop cycle builds out S5.
Each S5 lever is measured before/after on the idle+loaded starvation distribution -- promotion on
measurement, not assertion (the Phase 0.1 single-run mis-read is the cautionary precedent).

HONESTY RAILS: S1-S3 are measurement-only -- no bridge code changed. No FROZEN-v1 / 228B PoAC. No
chain/IOTX. asyncio debug attribution can be imperfect (Handle repr is the suspend point, not the
exact sync line), but S1 + S2 agree and the named callbacks are unambiguous. S4 (OS/GC) unrun -- the
clear S1-S3 attribution makes it low-priority; the only unattributed items are one-time startup spikes.
