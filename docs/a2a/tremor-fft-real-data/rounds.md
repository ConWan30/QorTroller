# ASM-Loop: real tremor FFT against run3_cfb27 capture — 2026-07-22

## r01 scope

**Task:** Implement the real FFT-based tremor computation in
`l9_presence/realplay_feature_adapter.py::tremor_from_accel` (currently a deliberate stub returning
(None,None)), using the accel data now available in run3_cfb27_20260722 (44079 rows, 100% accel
coverage confirmed). This is the last gate (G3) blocking Composite-B from reaching PARTIAL_PRESENT
on real data -- G1/G2/layer1/G5 already pass on real windows (90-120s, 120-150s, 150-180s).

**Grounding (do first):** reuse the EXISTING tested tremor FFT methodology in
`controller/tinyml_biometric_fusion.py` (tremor_peak_hz / tremor_band_power / micro_tremor_accel_variance,
8-12Hz physiological band, documented >=1024-sample floor) rather than reinventing FFT parameters.

**Definition of done:** real tremor_peak_hz/tremor_band_power computed from run3's actual accel
samples; re-run the Composite-B evaluator; report what verdict (if any) real windows now reach.
Honest either way -- if real tremor doesn't clear the 8-12Hz band gate, that's a valid, reportable
result, not a failure to paper over. grok PASS required before commit.

**Ceiling:** advisory/offline only. No calibrated=True, no poep/L6B flags, no chain, no FROZEN/PoAC
edit. Does not claim this validates Composite-B as a security mechanism -- only that the tremor gate
is now genuinely computed rather than stubbed.

## r02 (grok expand) — COMPLETE

**File:** `docs/a2a/tremor-fft-real-data/round-02-grok-expand.md`  
**Envelope in:** `30529504a23ebc01` · prior body sha MATCH.

**Steer summary:**
- Irregular-sampling diagnosis **partially accepted** — serious for whole-window naive FFT; not a ban.
- Claude gap numbers on 90–120s **reproduced** independently.
- **E1+segment+GAP_VOID_MS=50** primary; E3-for-G3 **refute**; E2 defer; E4 follow-on; refute-all **reject**.
- Concrete void: **50.0 ms** hard gap; soft void if clean segment < **2.0 s** or < **256** samples.
- "Defer, need recapture" is **valid Done if empirical yield is zero**, not a priori.
- BUILD-NOW this expand: **none** (design-only). Claude owns ranked build order in expand §5.

**Next:** Claude r02/r03 implement per ranked build order.

## r02 grok EXPAND — steered design, ran an existence probe, then r03 build

grok refuted the "irregular sampling bans any FFT" over-claim: the real problem is heavy-tailed
gaps (p90=17ms fine, max=1824ms catastrophic), not uniform irregularity. Steered MERGE
E1(resample)+segment-first+gap-void rail; REFUTE E3 (stick-velocity is a category error — G3 is
INVOLUNTARY continuity, stick motion during active play is voluntary); DEFER E2 (Lomb-Scargle);
ADOPT E4 (fixed-interval recorder) as a non-blocking follow-on, not required this round. Pinned
concrete constants with derivation: GAP_VOID_MS=50 (~half the 10Hz tremor period), MIN_CLEAN_SEG_MS
=2000, MIN_CLEAN_SEG_SAMPLES=256, RESAMPLE_HZ=200, band-limited peak search [8,12]Hz (not global
argmax, which finds postural/gravity energy). Ran an existence probe on real run3 data: a genuine
2.72s clean segment produced a real 10.16Hz in-band peak, band power 0.0199 (>>1e-6 floor) — proof
the design was buildable before Claude wrote any code.

## r02 build (Claude) — real tremor implemented, 7/19 windows reach PARTIAL_PRESENT

Implemented `tremor_from_accel` + pure helpers (`inter_sample_gaps_ms`, `longest_clean_segment`)
exactly per grok's steered constants/procedure. 10 new tests (23 total in the adapter suite; 29
across the whole arc). Re-ran the Composite-B evaluator against run3_cfb27_20260722 (real capture,
44079 rows, 100% IMU/ticks coverage):

**7 of 19 windows now reach PARTIAL_PRESENT — first time ever on real data.** Verified legitimate,
not gamed: gate_bitmap on every passing window shows G1/layer1-ticks/layer1-rate-locked/G2/G3/G5
all genuinely True, G4 honestly None (l2b_coupled_fraction not computed — real, disclosed gap),
optical_consistent correctly False (not wired into this offline path), capping every window at
PARTIAL_PRESENT rather than CONTINUOUS — exactly the designed tiering, nothing forced.

**Bug found + fixed along the way:** the runner's `honest_note` was hardcoded static text
describing run1's old missing-IMU limitation — would have silently misreported run3's real result
if left as-is (a stale-claim bug of exactly the class this arc's discipline exists to catch).
Made dynamic, verified it now correctly reports "7 windows reached PARTIAL_PRESENT" for this run.

29/29 tests green, PV-CI 184. Firing r03 to grok for adversarial audit before commit.

## r03 audit (grok) — VERDICT: PASS

grok r04 (returncode 0, sha256 matched, independently re-ran PV-CI, tests, and reproduced the exact
7/19 PARTIAL_PRESENT result with per-window hz/band_power/gaf numbers matching). Confirmed C1-C7
all hold: constants/procedure match r02 exactly, no whole-window naive FFT anywhere, band-limited
search proven not cosmetic, the 7/19 result is legitimate (spot-checked every passing window's
bitmap — no forced True bits), no tinyml/production-path edits, E4 correctly deferred, rails clean.

Two LOW-severity, non-blocking residuals flagged (not required for PASS, applied anyway since
already in the code): (1) "longest segment" was by sample-count, not duration — grok recommended
duration-based to match the ">=2.0s clean data" floor's own semantics; fixed, verified stable (still
7/19 on real data, no verdict flipped). (2) accel_y/accel_z KeyError risk if a row somehow had
accel_x without the other two axes (run3 is 100% full-triple, but real data shouldn't be assumed
perfect) — added an explicit guard.

One residual explicitly OUT of scope for this round (grok's own ruling): G3's soft SNR floor
(TREMOR_MIN_BAND_POWER=1e-6, pre-existing in realplay_liveness.py, not introduced this round) lets
broadband noise satisfy the band-power check. Fixing that is an EVALUATOR change needing its own
A2A loop, not an adapter fix — correctly not touched here.

**LOOP CONVERGED at PASS.** First real, non-fabricated PARTIAL_PRESENT verdicts from Composite-B on
live captured data (7/19 windows), reached by correctly implementing a segment-first FFT design
that routes around a real sampling-irregularity problem this session's grounding surfaced before
any code was written. 50/50 tests green, PV-CI 184.
