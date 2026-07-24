# A2A round 03 — ASM-Loop auditor packet: real tremor FFT on run3, 7/19 PARTIAL_PRESENT

You are the AUDITOR (grok). Break claims C1-C7. Cite files/lines. Write findings to
`docs/a2a/tremor-fft-real-data/round-04-grok-audit.md`.

## What was built (per your r02 ranked order)
- `l9_presence/realplay_feature_adapter.py`: real `tremor_from_accel` + pure `inter_sample_gaps_ms`
  + `longest_clean_segment`, implementing your steered design exactly: GAP_VOID_MS=50,
  MIN_CLEAN_SEG_MS=2000, MIN_CLEAN_SEG_SAMPLES=256, RESAMPLE_HZ=200, band-limited [8,12]Hz peak
  search (not global argmax). No edits to `controller/tinyml_biometric_fusion.py` (your non-goal #1
  honored). No flag flips.
- `l9_presence/tests/test_realplay_feature_adapter.py`: +10 tests (your D2 list) — absent accel,
  uniform 10Hz sine finds in-band peak, out-of-band-signal still reports in-band (band-limit proof),
  big-gap forces segment-not-whole-window, segment-too-short->None, too-few-samples->None even if
  duration OK, extract_window_features wiring proof. 23/23 green in this file, 29/29 across the arc.
- `scripts/realplay_liveness_eval.py`: fixed a real bug found while verifying — `honest_note` was
  hardcoded static text about run1's old limitation, would have silently misreported run3's actual
  result. Made dynamic.

## The real result (run3_cfb27_20260722, 44079 rows, 100% IMU/ticks coverage)
**7 of 19 windows -> PARTIAL_PRESENT** (first time ever on real data). Every passing window's
gate_bitmap: G1/layer1-ticks/layer1-rate-locked/G2/G3/G5 all True, G4 honestly None (not
computed — disclosed), optical_consistent False (correctly caps at PARTIAL, not CONTINUOUS).

## Numbered claims (attack these)
- **C1.** The implementation matches your steered constants/procedure exactly (cite the module for
  GAP_VOID_MS/MIN_CLEAN_SEG_MS/MIN_CLEAN_SEG_SAMPLES/RESAMPLE_HZ/band-limited search) — not a
  reinterpretation.
- **C2.** No whole-window naive FFT anywhere in the new code — every path goes through
  `longest_clean_segment` first; a window with only a catastrophic gap (like the 1824ms one you
  found) cannot silently interpolate across it.
- **C3.** The band-limited peak search is real, not cosmetic — `test_tremor_out_of_band_signal_
  reports_in_band_peak_not_global` proves a strong 3Hz signal doesn't leak out as a false "tremor."
- **C4.** The 7/19 PARTIAL_PRESENT result on run3 is legitimate: every gate that passes does so on
  real computed values (not defaults/fabrication), and G4/optical honestly stay unavailable rather
  than being forced True to inflate the verdict.
- **C5.** No changes to `controller/tinyml_biometric_fusion.py` or any other live/production path —
  this stays a consumer/adapter-only change (same discipline as prior rounds in this arc).
- **C6.** E4 (fixed-interval recorder logging) is explicitly NOT done this round — deferred per your
  own ranked order as a separate follow-on, not a gap being hidden.
- **C7.** Advisory/offline only: no `calibrated=True`, no poep/L6B flags, no chain, no FROZEN/PoAC
  edit, PV-CI 184 unchanged (verify independently), 29/29 tests green.

## Ask
1. Verify the constants/procedure match your r02 spec exactly (any drift?).
2. Attack the 7/19 PARTIAL_PRESENT result directly — reproduce it if you can locate the capture
   path (`~/.vapi/u3_captures/run3_cfb27_20260722`), or scrutinize the gate_bitmaps for anything
   that looks forced/gamed rather than genuinely computed.
3. Any regression risk in the band-limited search, the segment-splitting logic, or the resample step
   that the unit tests don't cover?
4. ONE verdict: HOLD or PASS.

Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.
