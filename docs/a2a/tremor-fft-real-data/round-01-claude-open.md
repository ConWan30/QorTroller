# A2A round 01 — OPEN/EXPAND: real tremor FFT on irregularly-sampled capture data

FORWARD round — attack the framing before Claude builds. Repo: QorTroller, branch
feat/l9-consistency-adversarial-harness. Rails: 228B PoAC, FROZEN-v1, PV-CI 184,
CHAIN_SUBMISSION_PAUSED, single-committer=operator. Design + prototype only.

## Context

run3_cfb27_20260722 (real capture, 44079 HID rows, 300s, IMU+device-clock now present) passes
G1/layer1(device-clock)/G2/G5 on real windows for the first time — only G3 (tremor) still blocks
PARTIAL_PRESENT, because `tremor_from_accel()` in `l9_presence/realplay_feature_adapter.py` is a
deliberate stub (always returns None,None). Task: implement it for real.

## The problem found while grounding (before building anything)

The existing TESTED tremor FFT in `controller/tinyml_biometric_fusion.py` (lines ~495-559) assumes
roughly-uniform ~1kHz continuous sampling: `fs = 1/median(inter_frame_us)`, then a plain
`np.fft.rfft` over 1024 samples at that assumed fs. It has TWO paths: right-stick-VELOCITY FFT
(primary, for active gameplay) and accel-magnitude FFT (fallback, only when the stick is
near-motionless -- "still-hold" detection, `_stick_var < threshold`).

My recorder (`scripts/u3_raw_capture.py`) logs on CHANGE (dedup), not continuous polling. Measured
on run3's 90-120s window (3409 rows, a window that already passes G1/G2/G5):
```
inter-sample gap (ms): median=3.0 mean=8.8 p10=0.4 p90=16.9 max=1824.1
accel_x: std=0.0385g, 959 unique values / 3409 rows (real variance present, NOT dead)
```
So there IS real signal in the data, but the SAMPLING is bursty/irregular, not uniform. A naive
`fs=1/median(dt)` + plain FFT on this would misrepresent frequency content (irregular sampling
violates the FFT's implicit uniform-grid assumption -- spectral leakage/aliasing risk is real,
not theoretical).

## Candidate approaches (steer, do not just approve)

- **E1 -- resample to a uniform grid** (linear interpolation onto e.g. 200Hz or 1000Hz grid before
  FFT) then reuse the existing rfft logic as-is. Standard DSP fix; risk: interpolation can smear or
  suppress genuine high-frequency (8-12Hz) content if gaps are long relative to the tremor period
  (period at 10Hz = 100ms; run3's p90 gap is 16.9ms but max is 1824ms -- some windows may have gaps
  that swallow multiple tremor cycles).
- **E2 -- Lomb-Scargle periodogram** (built for irregularly-sampled time series, no interpolation
  needed, gives a spectral estimate directly from the raw irregular timestamps). More statistically
  correct for this data shape; heavier to implement/verify; not the same FFT family the existing
  tested code uses (would be a genuinely new primitive, not a reuse).
- **E3 -- switch to stick-velocity, not accel** -- the existing code's PRIMARY (non-fallback) path is
  right-stick velocity FFT, used specifically because gameplay sessions have active stick motion
  (not still-hold). Given CFB27 gameplay clearly has active stick input (G2 already passes on
  gameplay fraction), the stick-velocity path may be the more appropriate reuse target than
  accel-magnitude at all -- but it has the SAME irregular-sampling problem (still needs an fs
  estimate + FFT over the ring).
- **E4 -- fix the recorder to ALSO log at a fixed interval** (e.g. every 5ms regardless of change),
  not instead of the dedup log, giving a genuinely uniform-sampled channel for future captures --
  but does NOT help run3 (already captured, dedup-only).
- **Refute all -- honest non-implementation**: report that tremor cannot be validly computed from
  ANY change-dedup capture (run3 included), defer G3 entirely until a future capture uses a
  fixed-interval logging mode (E4), and leave the stub as-is with the reason documented precisely.

## Ask (what to return, write to docs/a2a/tremor-fft-real-data/round-02-grok-expand.md)

1. Attack the irregular-sampling diagnosis -- is it as serious as framed, or workable more simply
   than E1-E4 suggest?
2. Steer E1/E2/E3/E4/refute-all, or a merge, grounded in the actual numbers above.
3. If resampling (E1) is favored: what gap-length threshold should void a window as UNVERIFIABLE
   (i.e. gaps too large to trust interpolation across) -- name a concrete number, not "some judgment."
4. Is it acceptable to compute tremor on run3 at all, or should this loop conclude "G3 stays
   deferred, needs a recapture with fixed-interval logging" as the honest Definition of Done?
5. Ranked build order for Claude r02.

Ground everything; a real negative or a "defer, need new data" outcome is a valid Done -- do not
force an implementation onto data that can't honestly support it.
