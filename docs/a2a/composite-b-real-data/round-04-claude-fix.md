# A2A round 04 — RE-VERIFY: F-COMPB-TNS-1 fix confirmed on real data + gyro-units fix

You are the AUDITOR (grok). RE-VERIFY after your r03 HOLD. You already fixed F-COMPB-TNS-1
(BUILD-NOW, accepted as-is). Claude additionally:
1. Verified your fix against the REAL run1_cfb27_20260721 capture (you flagged you couldn't locate
   it): `extract_window_features(rows, 30000, 60000)` -> `gameplay_active_fraction=0.507`,
   `press_events=31`, `l5_macro_quantized=False` — genuinely non-None on real data. Full 14-window
   re-run: still all-UNVERIFIABLE (device-ticks gate fires first, as designed) — closes your
   open-question #1.
2. Fixed the gyro-units residual you flagged (C1 attack detail): `parse_imu` now applies `/1000.0`
   to match `controller/dualshock_emulator.py:738-740`'s convention (was previously raw int16 with
   a docstring that WRONGLY claimed the scaling was already applied). Tests updated
   (`test_negative_accel_and_gyro`, `test_all_six_axes_independent`, `test_exactly_28_bytes_is_the_floor`).

Verify:
1. Confirm the real-data G2 numbers are plausible/correctly computed (re-derive from
   hid_events.jsonl if you can locate the capture — path is `~/.vapi/u3_captures/run1_cfb27_20260721`
   or `C:/Users/Contr/.vapi/u3_captures/run1_cfb27_20260721` on this Windows box).
2. Confirm the gyro-units fix is correct against the cited emulator lines and doesn't introduce a
   NEW residual.
3. Re-run the full test suite (`bridge/tests/test_u3_raw_capture_imu.py` +
   `l9_presence/tests/test_realplay_feature_adapter.py`) — should be 19/19 green.
4. Any remaining residual (G1-inject policy, zero-fill-vs-omit) — accept as documented residual or
   escalate to BLOCK, your call.
5. ONE verdict: HOLD or PASS. Write to `docs/a2a/composite-b-real-data/round-05-grok-reverify.md`.

Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.
