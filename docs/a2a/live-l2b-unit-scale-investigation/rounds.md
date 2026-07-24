# ASM-Loop: live L2B unit-scale investigation (R1 from l2b-causal-binding-real-data) — 2026-07-22

## r01 scope

**Task:** Determine whether the SAME unit-scale bug found and fixed in the offline
realplay_feature_adapter (gyro scaled /1000.0 in the recorder, but the L2B spike threshold
calibrated for raw LSB) is ALSO active in the LIVE production anti-cheat path
(controller/l2b_imu_press_correlation.py::ImuPressCorrelationOracle, the real Layer 2B oracle).
Read-only investigation + forward-collaborate with grok to pressure-test the reasoning before
reporting any conclusion as settled. NOT a fix round — explicitly scoped to characterize the bug's
real-world presence/impact, not remediate it.

**Grounding done so far (Claude, read-only, this session):**
1. `controller/dualshock_emulator.py` is the REAL hardware-reading module (own docstring: "Reads
   REAL inputs from a DualSense Edge controller connected via USB or Bluetooth") — not a simulator
   despite the filename. Confirmed both its gyro-population code paths apply `/1000.0`:
   - primary: `snap.gyro_x = struct.unpack_from('<h', _s, 22)[0] / 1000.0` (ds.states path)
   - fallback: `snap.gyro_x = ds.state.gyro.Pitch / 1000.0` (first-frame fallback)
2. `bridge/vapi_bridge/dualshock_integration.py` imports directly from this module
   (`from dualshock_emulator import (...)`, L1196) and feeds the resulting InputSnapshot objects
   into `self._imu_press_oracle.push_snapshot(snap)` (L2287) — the LIVE oracle instance, not a copy.
3. `controller/l2b_imu_press_correlation.py::_IMU_SPIKE_THRESH` defaults to `30.0`
   (env `L2B_IMU_SPIKE_THRESH`, no override present in `bridge/.env` — confirmed, using code
   default). Module docstring + design context (hw_* test corpus uses raw magnitudes in the
   thousands) indicates this constant was calibrated for RAW (unscaled) gyro LSB units.
4. No env override compensates for this in the live config.
5. Downstream impact if real: `humanity_score() = min(1.0, coupled_fraction/0.75)`. If
   coupled_fraction is structurally pinned near 0.0 (threshold unreachable given max real scaled
   gyro_mag ~18.5 vs threshold 30), `humanity_score()` would report ~0.0 for genuine human sessions
   instead of the ~0.9+ real coupling should produce (measured 0.966 on the offline capture after
   the fix). `classify()` would also fire `IMU_BUTTON_DECOUPLED` (0x31) almost continuously on real
   human play (coupled_fraction 0.0 < _COUPLED_FRACTION=0.55 anomaly threshold). 0x31 is OUTSIDE
   the hard-cheat range {0x28,0x29,0x2A} (CLAUDE.md), so this would NOT directly block tournament
   eligibility, but L2B contributes 0.10-0.15 weight in the documented humanity_probability formula
   (`p_human = ... + 0.15*p_L2B` with L6 active, or similar without) — a systematic downward bias
   on every player's computed humanity score, not a hard block.
6. NO empirical historical confirmation available: checked the canonical bridge DB
   (`~/.vapi/bridge.db`, 5.7GB) for stored `l2b_coupled_fraction`/`l2b_p_human` values — the
   `records` table has `pitl_l4_*`, `pitl_l5_*`, `pitl_e4_*` sidecar columns but **NO `pitl_l2b_*`
   column at all** — meaning L2B features are computed in-memory (`self._pending_pitl_meta` dict)
   but apparently never persisted to a durable, queryable column. This is itself a secondary
   finding (persistence gap), separate from the unit-scale question, and blocks easy empirical
   verification from historical session data.

**Definition of done:** grok independently verifies or refutes the code-trace reasoning above
(steps 1-5), and states plainly whether this is characterized correctly as "very likely active in
production" or something weaker/stronger. Does NOT fix anything. Produces a clear-eyed severity +
recommended-next-step writeup for the operator to decide on.

**Ceiling:** read-only investigation only. No code changes to
`controller/l2b_imu_press_correlation.py`, `controller/dualshock_emulator.py`, or
`bridge/vapi_bridge/dualshock_integration.py` in this round. No flag flips, no chain, no
FROZEN/PoAC edit. Does not claim this affects tournament HARD eligibility (0x31 is advisory-only,
confirmed against CLAUDE.md's own documented hard-cheat-code range).

## r04 grok audit — Step C scope APPROVE WITH MODIFICATIONS

Envelope `ca53b55559a872f0` / `round-03-claude-open.md` (sha MATCH). C1-C4 held
under attack with named mods: HTTP_PORT=**8080** (not 8000); WS 60s keep-alive;
no watchdog; process-scoped thr=0.03 + belt CHAIN pause / GRIND false. Live
`.env` preflight this audit: GRIND=false, CHAIN_SUBMISSION_PAUSED=true, L6B off;
IOSWARM=true (emulator OK under pause). Success bar: coupled_fraction >=0.55 +
p_human >0.5 after warmup. Does **not** authorize execution — operator-fired only.
Artifact: `round-04-grok-audit.md`. Bus: handoff/claim (Claude-safe).
Envelope out: `b46ffa0b7e5ec29e` grok->claude.

## Step C live run + C-fail-2 (operator-fired, real hardware)

Live run per round-04's checklist hit two setup problems (stale pre-existing
bridge on port 8080; own zombie from a failed bind) resolved with operator
confirmation before any data was trusted, then an unrelated confound
(`DUAL_GRIND_TETHER_ENABLED=true` automated haptic pulse polluting the press
stream) discovered and disabled. Clean run: **RECOVERY FAILED**
(coupled_fraction=0.0, 102/102 samples, real presses operator-confirmed).
C-fail-2 (re-run Step B's standalone script at thr=0.03): **clean recovery**
(coupled_fraction=0.92, humanity_score=1.0). Isolates the residual bug to
`dualshock_integration.py`'s integration wiring, not the unit-scale fix
(confirmed correct twice over, offline + standalone). Artifacts:
`step-c-live-run-results.md`, `c-fail-2-standalone-recovery-results.md`.

## r05 claude open — C-fail-3/4 hypothesis (GROK CREDITS EXHAUSTED, no audit obtained)

`round-05-claude-open.md` posted + handed off (envelope `d1ee0c1dff2787e1`) to
grok for adversarial audit of a code-read hypothesis: C-fail-3 (button remap)
reasoned very-likely-not-the-bug; C-fail-4 (timing/batching) — `InputSnapshot`
has no `timestamp_ms`, `push_snapshot()` falls back to `monotonic()`,
`dualshock_integration.py` processes an already-collected 1-second batch in a
tight post-hoc loop, collapsing real per-frame timing into a ~ms cluster and
breaking the 5-80ms precursor window regardless of threshold. **Operator
reported grok ran out of usage credits before responding — this round never
got an audit.** Proceeding solo per operator instruction: built
`scripts/diag_l2b_batch_timing_repro.py`, a standalone repro (no hardware, no
bridge) feeding the real oracle class an identical injected precursor+press
pattern two ways (bridge-style tight-loop batch replay vs. realtime-style
call-as-collected). **Result: mechanism CONFIRMED empirically** — batch mode
collapses a 1000ms history span to 1.08ms and misses every precursor
(coupled_fraction=0.0000); realtime mode preserves 1079.05ms and detects all
16 (coupled_fraction=1.0000). Explicitly flagged: no adversarial review of
this reasoning or script has happened. No production fix scoped or built.
Artifact: `c-fail-4-timing-repro-results.md`.

## C-fail-4 fix built, live-verified, and shipped as default — investigation CLOSED

Scoped (`c-fail-4-fix-scope.md`), built (`_stamp_frame_collection_times` wired
into `_session_loop`, dynamic-attribute approach, operator-selected), and
live-verified against the real bridge + real controller
(`c-fail-4-fix-live-verification-results.md`): 90s run, 74/74 non-null
samples, `coupled_fraction` climbing 0.65→0.75, zero `0x31` fires. Caught and
corrected a real near-miss mid-verification — a first bridge launch silently
fell into simulation mode (started before the controller's USB was
reconnected) and was caught by reading the startup log before trusting the
data, not assumed clean from a working HTTP bind alone.

`L2B_IMU_SPIKE_THRESH` then shipped as `0.03` **by default** in
`controller/l2b_imu_press_correlation.py` (was `30.0`, raw-LSB-calibrated;
live production needs live-scaled units) — closing the loop from a
process-scoped override to a permanent fix. This surfaced a real,
foreseeable-but-unaddressed regression: the module constant serves TWO unit
systems (raw-LSB historical corpus vs. live-scaled production), and one
existing test (`test_adaptive_threshold_tracks_baseline`) implicitly assumed
the old raw-LSB default — fixed by making it explicitly patch to `30.0` for
its raw-LSB scenario, matching the new default's own documented convention
for raw-LSB callers. `scripts/diag_l2b_unit_scale_replay.py` (Step A) had the
same latent issue in the opposite direction (its 3-pass narrative implicitly
depended on the OLD default for passes 1-2) — fixed to pin an explicit
threshold per pass, independent of whatever the module default currently is;
re-ran on the original qualifying session and reproduced byte-identical
results to the original historical artifact, confirming the fix didn't
change behavior, only removed an implicit dependency. C-fail-4's own
regression pin and the offline adapter's independent pin were checked and
confirmed unaffected (different failure mechanism / independently-defined
constants, respectively) rather than assumed safe.

125 tests green across every L2B/L2C/dualshock_integration/offline-adapter
file touched by this investigation; PV-CI 184 unchanged throughout.

**Investigation status: CLOSED.** L2B works correctly end-to-end in
production. Remaining honest residuals, explicitly not closed by this: no
grok adversarial audit ever happened on C-fail-3/4 or either fix (credits
exhausted mid-investigation); L5's possible shared timing exposure (it never
checks `timestamp_ms` at all, a different and *more* exposed pattern than
L2B/L2C's try-then-fallback) remains untouched and unstarted, its own future
investigation.
