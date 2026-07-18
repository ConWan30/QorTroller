You are the AUDITOR in an A2A verification loop. Another agent (the builder)
produced the work below with a numbered claims list. Your job is to break the
claims, not to be agreeable and not to rewrite the work.

Rules:
- Attack each claim C1..Cn individually. State what you checked and how.
- Return numbered findings F1..Fn, each tagged BLOCK, WARN, or INFO, each
  citing the specific claim or artifact line it concerns.
- Look hardest for: over-claims, silent scope creep, untested paths presented
  as tested, ambiguity that lets a false reading survive, and anything the
  builder would prefer you not notice.
- End with exactly one verdict: HOLD (any BLOCK/WARN stands) or PASS.
- Do not propose full fixes; describing WHY a finding blocks is enough.
- If you cannot verify a claim from the material given, that is a finding
  (WARN: unverifiable as presented), not a pass.

[BUILDER'S WORK + CLAIMS LIST FOLLOWS]

# ASM-Loop F-RIG27-8 — r04 re-verify (device-clock reflex latency)

This is r04, addressing your r03 **HOLD**. r03's BLOCK was that `_f.timestamp_ms` is a DEAD WIRE
(`InputSnapshot` has no `timestamp_ms`), so `device_ts` was always 0 and the device path never armed
on hardware (bar 7 FAIL). You also flagged a units bug (offset 28 is uint32 @~3MHz ticks, not ms) and
missing wrap-handling (bar 6 PARTIAL). All addressed below.

## r03 finding disposition

| r03 finding | disposition |
|---|---|
| BLOCK: `_f.timestamp_ms` dead wire; `InputSnapshot` has no such field | FIXED — device ts now sourced from `_states[28:32]` in the REAL `DualSenseReader.poll()`, surfaced on a new `InputSnapshot.sensor_ts_ticks` field, threaded through `device_ts`. New test drives the live poll() and asserts population. |
| BLOCK/units: offset 28 is uint32 @~3MHz ticks, not ms | FIXED — raw ticks carried end-to-end; the helper is the ONLY tick→ms conversion (`/ _DEVICE_TS_TICKS_PER_MS = 3000`). |
| bar 6 PARTIAL: no wrap_u32, no frozen/duplicate rail | FIXED — helper does `(c - p) % _U32` (wrap-safe: real ~24-min rollover recovers a small span; frozen/duplicate → span 0 → reject; regressed/stale → huge span → reject) + a uint32-range guard (`c/p >= 2^32 → reject`). |
| bar 1-4 PASS (additive, corpus byte-stable, sealed clean, PV-CI 184) | Preserved — re-verified below. |

## The fix (4 files, all uncommitted; the whole F-RIG27-8 increment is one commit)

### 1. `controller/dualshock_emulator.py` — the real device-clock source
- `InputSnapshot` gains `sensor_ts_ticks: int = 0` (dataclass field, **NOT** added to `serialize()`'s
  explicit pack list → the 50-byte snapshot is byte-identical; test asserts this).
- `poll()` — inside the existing `if _states is not None and len(_states) >= 28:` IMU block (which
  already parses accel @16/18/20 + gyro @22/24/26 from `_s = bytes(_states)`), after the bt_seq line:
  ```python
  if len(_states) >= 32:
      snap.sensor_ts_ticks = struct.unpack_from('<I', _s, 28)[0]
  ```
  Offset 28 is the DualSense sensor timestamp, immediately after the IMU block states[16:28],
  transport-normalized identically (the codebase's raw drain thread reads the SAME offset 28 for
  `push_l2_raw`, dualshock_integration.py:899). Absent (len<32 / first-frame) → stays 0 → helper falls back.

### 2. `bridge/vapi_bridge/dualshock_integration.py` — helper (ticks→ms, wrap-safe) + wiring
- New module constants: `_DEVICE_TS_TICKS_PER_MS = 3000.0`, `_U32 = 1 << 32`.
- `_rp_device_latency_ms(crossing_device_ticks, probe_device_ticks, max_ms=500.0)`:
  ```python
  c = float(...); p = float(...)          # non-numeric → -1
  if c <= 0 or p <= 0: return -1.0        # both ends required (0 = absent)
  if c >= _U32 or p >= _U32: return -1.0  # not a valid uint32 tick
  span_ticks = (c - p) % _U32             # wrap-safe modular diff
  span_ms = span_ticks / 3000.0
  if not (0.0 < span_ms <= max_ms): return -1.0
  return span_ms
  ```
- `_l6b_entry["device_ts"] = int(getattr(_f, "sensor_ts_ticks", 0) or 0)` (raw ticks; was the dead
  `getattr(_f, "timestamp_ms", 0)`).
- `_probe_device_ts = int(_pre_reports[-1].get("device_ts", 0) or 0)` (raw ticks).
- Completion block unchanged in shape: `_dev_lat = _rp_device_latency_ms(crossing_device_ts, probe_ticks)`;
  resolve uses `_dev_lat if _dev_lat > 0.0 else _l6b_result.latency_ms`.

### 3. `bridge/controller/l6b_reflex_analyzer.py` — additive capture only (canonical untouched)
- `crossing_device_ts` field + capture doc updated to say RAW TICKS; the analyzer only CAPTURES the
  crossing frame's `device_ts` value; `latency_ms` / `true_latency_ms` / classification / corpus UNCHANGED.

### 4. `bridge/tests/test_rp_device_latency.py` — 13 tests (rewritten for ticks + live path)

## Claims (attack these)

- **C1** The device path now ARMS on real hardware: `test_live_poll_populates_sensor_ts_ticks` constructs
  a real `DualSenseReader`, sets a fake `ds` whose `states[28:32]` = a known uint32, calls the REAL
  `poll()`, and asserts `snap.sensor_ts_ticks == that value`. (This is the specific thing that was dead in r03.)
- **C2** Units correct: raw uint32 ticks @3000/ms; `test_helper_valid_span_ticks` (540_000 ticks → 180.0ms),
  `test_rp_lag_t_mono_inflated_device_in_band` (t_mono 3000ms OOB vs device 180ms in-band).
- **C3** Wrap-safe: `test_helper_wrap_u32_recovers_rollover_span` (probe near 2^32, crossing wrapped
  smaller, true span 180ms recovered); `test_helper_frozen_or_duplicate_stream_rejected` (probe==crossing → -1);
  `test_helper_regressed_ts_not_a_wrap_is_rejected` (small backward step → huge span → -1).
- **C4** Fail-closed both-ends + uint32 range + (0,500ms]: `test_helper_both_ends_required`,
  `test_helper_rejects_implausible_and_bad_types`.
- **C5** Canonical byte-stable: `test_analyzer_captures_device_ts_additively` asserts `true_latency_ms`
  is still t_mono-based and unchanged while `crossing_device_ts` is captured additively;
  `test_analyzer_device_ts_absent_stays_minus_one` (absent device_ts → t_mono path identical).
- **C6** 50-byte snapshot byte-identical: `test_input_snapshot_serialize_byte_stable_with_new_field`
  (`InputSnapshot().serialize() == InputSnapshot(sensor_ts_ticks=X).serialize()`).
- **C7** Scope/rails: sealed `l9_presence/` byte-untouched (git status empty); PV-CI 184; zero spend;
  no flag flips (poep_enabled/L6B_ENABLED stay False — device_ts is a non-gating t_mono-fallback
  companion on the nonce-bound RP verify path only); DEFAULT_BAND / corpus / 228B-PoAC untouched.
- **C8** (KNOWN LIMIT, labeled) The full-stream monotonic-progression rail (r02 E.4) is NOT built. The
  two-point span>0 rail covers frozen/duplicate/regressed at the (probe, crossing) pair; a host feeding a
  slowly-incrementing FORGED counter is out of scope here — the verdict does not depend on device_ts
  (it's a t_mono-fallback companion; the nonce + real_hardware + sealed verify own the verdict). Flagged
  for your ruling, not presented as built.

## Test / gate evidence
- `test_rp_device_latency.py`: 13 passed.
- regression: analyzer 25 (with device-latency) · InputSnapshot/emulator/dualshock surfaces 173
  (test_biometric_fusion + test_l2b_imu_press_correlation + test_phase205 + test_phase57 + test_game_profile
  + test_hid_xinput_oracle + test_dualshock_integration) · poep/ring/l6b 112 (hidring_fire + campaign_mode
  + cco_l6b_wiring + l6b_bridge_integration + humanity_formula_l6b + live_capture + live_verify + reflex_gate).
- `scripts/vapi_invariant_gate.py`: PASS 184.
- `git status l9_presence/`: empty (sealed untouched).

Break C1 hardest (it's the exact dead-wire you caught in r03 — confirm the live poll() genuinely reads
offset 28 and that my fake `ds` doesn't sidestep the real code path). Then C3 wrap math and C6 byte-stability.
