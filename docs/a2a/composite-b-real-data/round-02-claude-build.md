# A2A round 02 — ASM-Loop auditor packet: Composite-B real-data adapter (off-rig)

You are the AUDITOR (grok). Break claims C1-C7. Cite files/lines. Write findings to
`docs/a2a/composite-b-real-data/round-03-grok-audit.md`.

## What was built (off-rig, no new capture)
- `scripts/u3_raw_capture.py` — promoted/fixed recorder: now captures accel/gyro (offsets verified
  against `controller/dualshock_emulator.py:730-767`, the tested pydualsense parse) + `sensor_ts_ticks`
  (offset 28, F-RIG27-8 device clock, needed for the anti-replay rail §2.5). The run1_cfb27 recorder
  captured NEITHER — this is a real gap fix for future captures, not cosmetic.
- `bridge/tests/test_u3_raw_capture_imu.py` — 6 tests on `parse_imu` (pure byte-parsing, synthetic
  buffers, no hardware).
- `l9_presence/realplay_feature_adapter.py` — pure `extract_window_features(rows, t_lo, t_hi, ...)`:
  HID rows -> `realplay_liveness.WindowFeatures`. Computes G2 (trigger_active_fraction, real), press
  counts, a CANDIDATE G5 rhythm proxy (inter-press-gap CV), device-clock span (real if present),
  tremor (honestly None — accel-FFT deliberately unimplemented stub, not fabricated).
- `l9_presence/tests/test_realplay_feature_adapter.py` — 12 tests, synthetic HID rows.
- `scripts/realplay_liveness_eval.py` — runner: slides 30s/50%-overlap windows across a real capture,
  runs the ALREADY-COMMITTED `evaluate_realplay_liveness` (from the original ASM-Loop-verified
  Composite-B module, untouched this round), reports verdict distribution.

## The real result (run1_cfb27_20260721, first time this evaluator ran on non-synthetic data)
- 14 windows, ALL verdict=UNVERIFIABLE.
- Gate bitmap on every window: `G1_capture=True`, `layer1_device_ticks_present=False` — fails
  closed at the device-clock-ticks check (F4 rule), BEFORE ever reaching G3/tremor.
- `has_accel_data=false`, `has_sensor_ts_ticks=false` — confirmed absent from run1's HID rows
  (recorded before today's recorder fix).

## Numbered claims (attack these)
- **C1.** The IMU/device-clock byte offsets in `u3_raw_capture.py` are NOT guessed — they match the
  existing tested parse in `controller/dualshock_emulator.py:738-751` (gyro at [22,24,26], accel at
  [16,18,20], sensor_ts_ticks uint32 LE at [28], all little-endian, USB-transport unstripped report).
- **C2.** `realplay_liveness.py` (the committed Composite-B evaluator) was NOT modified this round —
  this is a pure consumer/adapter round, testing the existing module against real data for the first
  time, not changing its logic.
- **C3.** The all-UNVERIFIABLE result on run1 is the CORRECT and EXPECTED outcome given run1's real
  data gap (no device ticks) — it is evidence the fail-closed contract works, NOT evidence the
  evaluator is broken, and NOT evidence it's "validated" (that needs a capture with real IMU data).
- **C4.** G2 (gameplay_active_fraction) and press-event counting ARE real, computed from actual HID
  data in run1 — these parts of the adapter are genuinely exercised end-to-end, unlike G3/G4/anti-replay.
- **C5.** The G5 rhythm proxy (inter-press-gap coefficient-of-variation) is explicitly labeled
  CANDIDATE, not the real L5 temporal-rhythm-oracle primitive — a coarser stand-in usable without IMU.
- **C6.** The tremor-from-accel function honestly returns `(None, None)` rather than fabricating FFT
  output from absent/thin data — even for a future capture WITH accel present, the FFT itself is a
  deliberately-unimplemented stub (documented, not silently stubbed).
- **C7.** Advisory/offline only: no `calibrated=True`, no flag flips, no chain, no FROZEN/PoAC edit,
  PV-CI 184 unchanged (verify independently). 18 new tests green (6 recorder + 12 adapter).

## Ask
1. Verify C1's byte-offset claim against the cited emulator lines yourself.
2. Is there a risk in the G2/press-count "real" claim — any silent look-ahead, any place synthetic
   defaults leak into a real computation?
3. Is the all-UNVERIFIABLE result reported honestly, or does anything in the runner/report oversell
   what was proven?
4. ONE verdict: HOLD or PASS.

Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.
