# ASM-Loop: real G4 causal binding (L2B) on real data — 2026-07-22

## r01 scope + build (combined — straight reuse, no design fork, self-caught real bug mid-build)

**Task:** Implement the last stubbed Composite-B gate (G4, causal binding — was hardcoded None)
using the TESTED methodology in `controller/l2b_imu_press_correlation.py`. Grounded first: unlike
tremor, L2B is a timestamp-windowed lookback check (not frequency-domain), so it's naturally
tolerant of change-dedup's irregular sampling — empirically confirmed on run3 (median 14.5 gyro
samples in the 75ms lookback window per real press, 0/58 presses with zero samples). No forward-
collaborate round needed; straight build+audit.

**Real bug self-caught mid-build:** first real-data result was a suspicious coupled_fraction=0.0
across every window (and the whole 300s session) — implausibly bot-like. Investigated rather than
trusting it: `L2B_IMU_SPIKE_THRESH=30.0` is calibrated in `controller/l2b_imu_press_correlation.py`
for RAW (unscaled) gyro LSB units read directly from the live pydualsense wrapper. This adapter's
`scripts/u3_raw_capture.py::parse_imu()` applies a `/1000.0` scale to gyro (the grok-audited fix
from the earlier tremor-fft-real-data round, matching `controller/dualshock_emulator.py`'s
convention) — so the threshold has to be scaled the same way, or it can NEVER fire. Empirical proof:
real gyro_mag on run3 tops out ~18.5 in scaled units; threshold=30 is structurally unreachable.
Fixed to `L2B_IMU_SPIKE_THRESH = 30.0/1000.0`; whole-session coupled_fraction on run3 jumped from
0.0 to **0.966** (consistent with the reference module's documented human baseline ~0.70-0.90).

**Separate, honest, non-bug finding:** individual 30s Composite-B windows have ~9 R2 presses each
(this game's cadence), below `min_press_events=15` (reused directly from the tested module's own
floor) — so G4 stays honestly None on every individual window checked, even though the underlying
computation is now correct. This does not change the 7/19 PARTIAL_PRESENT result (G4=None is N/A,
not a fail, per the evaluator's existing design) but is disclosed, not hidden.

**Tests:** 5 new (l2b-no-gyro->None, too-few-presses->None, coupled-session->high-fraction,
decoupled-session->low-fraction, and an explicit unit-scale regression pin asserting
L2B_IMU_SPIKE_THRESH < 1.0 so this exact bug can never silently reappear). 28/28 in the adapter
suite, 55/55 across the whole realplay-liveness test surface. PV-CI 184.

**Ceiling:** advisory/offline only. No calibrated=True, no poep/L6B flags, no chain, no FROZEN/PoAC
edit. Does not claim G4 is validated across other games/sessions — N=1 capture, same discipline as
every other real-data finding this session.

## r03 grok audit — PASS

**ONE VERDICT: PASS.** C1–C5 hold under independent re-run (run3: thr=0.03 → 0.9655; thr=30 → 0.0;
gyro max 18.515; 58 R2 presses; all 30s windows &lt;15 presses → G4=None N/A). C6 pre-audit pin was
weak (`&lt;1.0`); BUILD-NOW: `L2B_RAW_IMU_SPIKE_THRESH` + `GYRO_SCALE_DIVISOR` SoT + pin that raw thr
fails on scaled synthetic. Residual R1: live DualSense emulator also /1000s gyro while live L2B thr
is raw-LSB — out of this adapter arc. Artifact:
`docs/a2a/l2b-causal-binding-real-data/round-03-grok-audit.md`. Stage only.

## r02/r03 audit (grok, manual copy/paste due to A2A relay classifier block) — VERDICT: PASS

grok independently reproduced the unit-scale bug (thr=30.0 -> 0.0; thr=0.03 -> 0.9655, 56/58
presses) and confirmed C1/C2/C4/C5 clean, C3/C7 PASS with minor INFO corrections (58 presses not
59; test-count bookkeeping). C6 (the regression pin) was found genuinely too weak
(`assert L2B_IMU_SPIKE_THRESH < 1.0` would pass on almost any wrong-but-small threshold) and grok
applied its own BUILD-NOW fix directly: introduced `L2B_RAW_IMU_SPIKE_THRESH=30.0` +
`GYRO_SCALE_DIVISOR=1000.0` as a single source of truth (derived `L2B_IMU_SPIKE_THRESH = RAW/
DIVISOR`), and strengthened the regression test to pin the exact derivation AND assert the raw
threshold explicitly FAILS on scaled synthetic data (not just "is small").

**R1 — the significant residual, confirmed real via read-only investigation (Claude, post-audit):**
grok flagged that `controller/dualshock_emulator.py` — the REAL hardware-reading module (not a
simulator; own docstring: "Reads REAL inputs from a DualSense Edge controller") — ALSO applies
`/1000.0` to gyro on every path that populates InputSnapshot (both the primary `ds.states` path and
the first-frame fallback). `bridge/vapi_bridge/dualshock_integration.py` imports directly from this
module (`from dualshock_emulator import (...)`, L1196) and feeds those exact snapshots into the
LIVE `ImuPressCorrelationOracle` via `push_snapshot` (L2287) -- the real production anti-cheat
Layer 2B, not a copy. `controller/l2b_imu_press_correlation.py::_IMU_SPIKE_THRESH` defaults to
`30.0`, calibrated for RAW LSB units (design + hw_* test corpus use raw magnitudes in the
thousands). This is the SAME bug class, in the LIVE anti-cheat path, not just this offline adapter.

**NOT fixed here** -- explicitly out of scope per grok's own ruling and this arc's adapter-only
discipline; live anti-cheat code needs its own dedicated, carefully-verified investigation before
any change, given tournament-eligibility implications. Flagged prominently to the operator.

**LOOP CONVERGED at PASS** for the adapter (49 tests, PV-CI 184, real 0.966 result on run3). The
R1 live-path finding is the most significant thing this whole session surfaced and is reported
separately, not folded into this arc's "done" status.
