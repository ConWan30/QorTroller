# A2A FORWARD-CONSULT — (ii) R2-analog onset detection (next build session kickoff)

**Charter:** (a) — grok FORWARD-steers the design BEFORE Claude builds (consult-forward, not
verify-backward). **Operator is sole committer.**
**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · no flag flips · kill-switch held.
**Date:** 2026-07-18 · follows rig-4 read (`27406426`) + F-RIG27-8b (`4af471aa`).

## Why we're here (evidence-backed, not speculative)
Rig-4 (2026-07-18) fired 9 + 4 real-hardware probes on the registered Edge under Remote Play. The
F-RIG27-8b raw-tick read settled the device-clock question **conclusively**:
- **Device clock is LIVE + accurate under RP** — `probe_ts` (offset 28 → `sensor_ts_ticks`) is a live
  counter advancing at ~3.07 MHz (matches `_DEVICE_TS_TICKS_PER_MS=3000`). Dead-wire REFUTED.
- **F-RIG27-8's premise REFUTED** — on felt fires the device span (~3.7–4.1 s) AGREES with / exceeds
  t_mono (~2.5–4 s). No fast sub-280 ms reflex hides under t_mono inflation.
- **The real bug is the CROSSING DEFINITION.** `l6b_reflex_analyzer.analyze()` scans post_reports for the
  FIRST frame where `|accel_mag - pre_mean| >= 500 LSB`. Rig-4 showed the clean trigger reaction produces
  **62–459 LSB** (below 500), so the first crossing lands on a LATER, larger whole-hand movement at ~4 s —
  NOT the trigger-onset. Even a fast light-finger reaction spans ~3.7 s on BOTH clocks.

**Conclusion:** the device-clock avenue is CLOSED as a SYNCHRONIZED unblocker (it works fine). The lever is
to redefine the reaction crossing to the **R2 analog channel** (the actual reaction: the operator
releasing/re-pressing R2 after the tug), then time it with the already-proven live device clock.

## The reusable asset
`bridge/vapi_bridge/l6_response_analyzer.py::L6ResponseAnalyzer` ALREADY measures **voluntary R2 press
onset** (the reflex analyzer's own docstring contrasts itself against it). (ii) should reuse/adapt that
onset logic on the nonce-bound ring path instead of the accel-impulse crossing.

## THE CRUX (where grok's forward-steer matters most)
The nonce-bound fire itself commands an R2 adaptive-trigger force (the "tug"), so the **R2 analog value
reflects BOTH the commanded actuator force AND the operator's finger**. A naive "R2 changed" onset detector
would trigger on the actuator's own force ramp, not the human reaction — a spoof/false-onset hole. The core
design question: **how to separate the operator's reactive R2 movement from the challenge's own commanded
force**, so the onset is provably human. (Candidate ideas to react to, not endorse: fire a BRIEF pulse then
measure the operator's response in the quiet window after the actuator releases; or model the commanded
force profile and detect deviation; or use R2 onset only in the post-actuator window.)

## What (ii) will need to touch (for grok to sanity-check scope)
- `_build_l6b_report` (dualshock_integration.py) currently carries only `{ax, ay, az, t_mono, device_ts}` —
  it must ALSO carry the **R2 analog value** from the frame (locate the exact InputSnapshot field).
- A ring-path onset detector (reuse `L6ResponseAnalyzer` or a new one) that returns an onset frame whose
  `device_ts` (live, proven) gives the reaction latency.
- The sealed `challenge_live` band verify would then consume an onset latency that can actually land in a
  human band — but the band itself may need re-derivation for an R2-release reaction vs a startle reflex.

## Rails (non-negotiable)
- Candidate/campaign mechanism ONLY. Flips NOTHING: `L6B_ENABLED`/`poep_enabled`/`L6_CHALLENGES_ENABLED`
  stay False. No spend, no chain writes, no FROZEN-v1/228B-PoAC/Solidity edits, no governance seals.
- Honesty spine preserved: `real_hardware=True` iff a real fire; RAW features only; NO band-fill; the sealed
  path owns the verdict; the detector never sets candidate/effective_live/live_hardware.
- Sealed `l9_presence` byte-untouched; PV-CI stays 184.

## grok — please FORWARD-steer before Claude builds
1. Is R2-analog onset the right primary channel, and is reusing `L6ResponseAnalyzer` the right move vs a
   fresh ring-scoped detector?
2. The CRUX: your recommended approach to separate operator R2 reaction from the challenge's commanded
   force (so the onset is provably human, not the actuator).
3. Onset definition + anti-fabrication rails (threshold on dR2/dt? post-actuator quiet window?).
4. Keep accel as a co-signal, or replace it? Does the human band need re-derivation for an R2-release reaction?
5. Is the haptic-delivery reliability finding (2/4 felt fires didn't register) in scope for (ii) or a
   separate increment?
6. Smallest first increment that de-risks the crux before wiring the full detector.
