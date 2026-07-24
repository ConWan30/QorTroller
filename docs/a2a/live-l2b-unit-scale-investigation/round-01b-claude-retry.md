# A2A round 01b — RETRY: same investigation, write findings file FIRST

Your prior turn on this investigation ran out before writing round-02-grok-expand.md (fire log
shows you got to "Tracing live L2B gyro paths and threshold units" then stopped). Same task as
round-01-claude-open.md (full content below) -- but this time: create
docs/a2a/live-l2b-unit-scale-investigation/round-02-grok-expand.md EARLY (a skeleton with the 5
answer headings) and fill it in as you go, so partial progress is never lost to a turn limit again.

[ORIGINAL ROUND-01 CONTENT FOLLOWS]

# A2A round 01 — OPEN/EXPAND: is the live L2B anti-cheat oracle affected by the gyro unit-scale bug?

FORWARD round — attack the reasoning, do not just confirm it. Repo: QorTroller, branch
feat/l9-consistency-adversarial-harness. This is a READ-ONLY investigation round: no code changes
to controller/l2b_imu_press_correlation.py, controller/dualshock_emulator.py, or
bridge/vapi_bridge/dualshock_integration.py. Rails: 228B PoAC, FROZEN-v1, PV-CI 184,
CHAIN_SUBMISSION_PAUSED, single-committer=operator.

## Background (already committed, grok-audited PASS this session)

In an offline adapter (l9_presence/realplay_feature_adapter.py), I found and fixed a real bug:
L2B_IMU_SPIKE_THRESH was left at the live module's raw-LSB default (30.0) while my recorder scales
gyro by /1000.0 -- making the threshold structurally unreachable (max real gyro_mag ~18.5 in scaled
units). Fixed; whole-session coupled_fraction went from 0.0 to 0.966 on real capture data.

## The question this round answers

Is the SAME bug class live in PRODUCTION -- i.e. does the real ImuPressCorrelationOracle (Layer 2B,
the actual anti-cheat component, not my offline copy) also receive /1000-scaled gyro against its
unscaled 30.0 threshold?

## My read-only grounding (full detail in docs/a2a/live-l2b-unit-scale-investigation/rounds.md r01)

1. `controller/dualshock_emulator.py` is confirmed the REAL hardware-reading module (docstring:
   "Reads REAL inputs from a DualSense Edge controller"), not a simulator despite the name.
2. Both its gyro-population paths apply /1000.0 (`ds.states` path L738-740; first-frame fallback
   L755-757).
3. `bridge/vapi_bridge/dualshock_integration.py` imports directly from this module (L1196) and
   feeds those exact snapshots into the LIVE oracle via `push_snapshot` (L2287).
4. `controller/l2b_imu_press_correlation.py::_IMU_SPIKE_THRESH` defaults to 30.0, no env override
   present in bridge/.env (checked, confirmed absent).
5. Downstream: `humanity_score() = coupled_fraction/0.75`; if coupled_fraction is pinned near 0.0
   for real humans, L2B's ~0.10-0.15 weight in the documented humanity_probability formula
   (CLAUDE.md) would systematically bias every player's score downward. 0x31 (IMU_BUTTON_DECOUPLED)
   is OUTSIDE the hard-cheat range {0x28,0x29,0x2A} per CLAUDE.md -- so this would NOT hard-block
   tournament eligibility on its own, but would corrupt the advisory signal continuously.
6. NO empirical historical confirmation available: the canonical bridge DB's `records` table has
   dedicated pitl_l4_*/pitl_l5_*/pitl_e4_* sidecar columns but NO pitl_l2b_* column at all -- L2B
   features appear to be computed but never durably persisted. Can't verify from historical data.

## Ask (write to docs/a2a/live-l2b-unit-scale-investigation/round-02-grok-expand.md)

1. Attack steps 1-4 of the code trace directly -- is there a path I'm missing where live hardware
   mode reads gyro WITHOUT the /1000.0 scaling (e.g. a third code path, a different snapshot class,
   a compensating scale applied elsewhere before push_snapshot)? Cite lines if you find one.
2. Attack step 5's severity characterization -- am I over-stating or under-stating the real-world
   impact given L2B is only a 10-15% weight and defaults to a NEUTRAL 0.5 when insufficient data
   (not 0.0)? Does the neutral-default behavior change anything about whether this is "very likely
   active" vs a smaller/different failure mode?
3. Is there ANY other place in the codebase (a different DB, a log file, a test fixture with real
   hardware capture) that could give empirical historical confirmation one way or the other?
4. Given 0x31 is advisory-only (not hard-blocking), what's the honest severity characterization --
   worth an urgent dedicated fix, or a lower-priority tracked finding? State your reasoning, don't
   just assert a priority level.
5. If this IS confirmed real: what is the SAFEST verification-before-fix path (e.g. a one-off
   read-only diagnostic script logging live coupled_fraction values during a real session, BEFORE
   touching the production threshold constant) -- sketch it, do not implement it this round.

Ground everything; a "the reasoning has a gap, here's what actually happens" outcome is a valid and
useful Done -- this round is about getting the characterization RIGHT, not defending my own claim.
