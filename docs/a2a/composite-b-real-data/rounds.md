# ASM-Loop: Composite-B real-data adapter (off-rig) — 2026-07-22

## r01 scope

**Task:** Build the feature-extraction adapter that runs the ALREADY-COMMITTED
`l9_presence/realplay_liveness.py` evaluator against REAL data from the run1_cfb27 capture
(~/.vapi/u3_captures/run1_cfb27_20260721) — the first time it's tested on anything but synthetic
WindowFeatures. Off-rig (no new capture). grok collaborates + audits over the terminal bus,
autonomous per operator directive.

**Definition of done:**
1. A real feature-extraction adapter: raw HID + frames -> `WindowFeatures` sliding windows across
   the 240s capture, run through `evaluate_realplay_liveness`.
2. Whatever gaps this surfaces get diagnosed honestly (e.g. if the recorder didn't capture a field a
   gate needs, that's a finding, not a blocker to paper over).
3. If a real gap is found (grounding check below already suggests one), fix it going forward
   (recorder improvement) so the NEXT capture is fully evaluable — this is off-rig code work.
4. Converges under grok PASS (or residual-accepted).

**Ceiling:** advisory/offline only. Does not flip `calibrated=True`, `poep_enabled`, `L6B`. No chain,
no FROZEN/PoAC edit. Does not claim the module is "validated" — only that it runs end-to-end on real
data and reports what it honestly finds.

**Grounding check before building (do first):** the run1 recorder
(`~/.vapi/u3_captures/run1_cfb27_20260721/recorder.py`) only parsed HID bytes 1-9 (sticks, triggers,
buttons) — G3 (tremor, needs accel) may be UNAVAILABLE from this capture. Confirm against the real
recorder code before assuming.

**A2A bus:** sealed envelopes via scripts/a2a_pkg_relay.py + deliver --fire grok
(PYTHONIOENCODING=utf-8), autonomous.

## r02 build + r03 audit (grok) — HOLD, real bug found + fixed by grok, then a second fix by Claude

grok r03 (returncode 0, sha256 matched, independently re-ran PV-CI + checked git log to confirm
realplay_liveness.py untouched). **Verdict HOLD** — C1/C2/C3/C5/C6/C7 PASS (or PASS-residual), but
**C4 FAIL**: my claim "G2/press-count genuinely exercised end-to-end on real data" was FALSE on the
actual runner path — a real bug (F-COMPB-TNS-1): the adapter preferred absolute epoch `t_ns` over
relative `t_ms` when both keys were present (the real runner's row shape), silently emptying every
window (G2=None, presses=0). My unit tests never caught it because they only used t_ms-only
synthetic rows, never the real dual-key shape. grok fixed it directly (BUILD-NOW, `_row_t_ms()`
prefers relative t_ms) + added a regression test.

**Claude verified the fix against the REAL run1 data** (grok could not locate the capture path):
`gameplay_active_fraction=0.507`, `press_events=31` on window [30s,60s] — genuinely non-None now.
Re-ran the full 14-window report: still all-UNVERIFIABLE (correct — the device-clock-ticks gate
fires before G2 ever matters for the verdict), closing grok's open-question #1.

**Claude also fixed a second grok-flagged residual**: `parse_imu`'s docstring claimed gyro matched
the emulator's `/1000.0` scaling convention, but the code returned raw unscaled int16 — a real
correctness gap for any future G4/coupling work using gyro. Fixed to apply `/1000.0` genuinely,
tests updated (int16-overflow bug in my own test fix caught immediately by re-running, corrected).

**Disposition:** both HOLD-causing/flagged issues fixed and independently verified. 19/19 tests
green, PV-CI 184. Firing r04 re-verify to grok before commit.

## r04 fix + r05 re-verify (grok) — VERDICT: PASS

grok r05 (returncode 0, sha256 matched) independently re-derived the real-data G2/press numbers
across FOUR windows (not just the one Claude checked) — all matched exactly (30-60s: gaf=0.507050,
presses=31; 0-30s: gaf=0.529, presses=20; 15-45s: gaf=0.447, presses=31; 60-90s: gaf=0.725,
presses=9). Confirmed the gyro /1000.0 fix line-by-line against the cited emulator code. Re-ran the
full 19-test suite independently (19/19 green) + PV-CI (184).

**Both r03 findings formally CLOSED:** C4 (G2 claim-integrity) closed via the real-data re-derive
matching peer + manual computation; C1 gyro-units residual closed via the fix. Remaining minor
residuals (G1 injection policy, zero-fill-vs-omit on short HID buffers) explicitly ACCEPTED as
documented residuals, not escalated to BLOCK.

**LOOP CONVERGED at PASS.** Two real bugs found and fixed across this loop (F-COMPB-TNS-1 by grok,
gyro-units by Claude), both independently re-verified against real capture data, not just re-run in
isolation. Honest result stands: run1 evaluates all-UNVERIFIABLE (correct fail-closed behavior on a
capture missing IMU/device-clock data); the NEXT capture using the fixed recorder is what's needed
to exercise G3/G4/anti-replay end-to-end.
