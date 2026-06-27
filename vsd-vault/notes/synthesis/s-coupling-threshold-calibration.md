---
type: synthesis
id: s-coupling-threshold-calibration
title: Calibrate the UNCALIBRATED L9 coupling threshold (0.20) against real Remote-Play data — FAR-controlled separation of real coupling vs the shuffle null; harness + status-surfacing + runner BUILT, data campaign pending
created: 2026-06-27T09:30:00Z
modified: 2026-06-27T09:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 80
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

HYPOTHESIS UNDER TEST. The L9 `COUPLING_THRESHOLD = 0.20` (coupling.py) is explicitly UNCALIBRATED —
`screen_retina_fusion.py` marks it "thresholds are hypotheses until a study." Live confirmation 2026-06-27
(Warzone via Remote Play, bridge running, the slice+phaseCorrelate fix from [[s-wgc-fps-processing-wall-resolved]]
live at ~45fps): with ACTIVE right-stick aiming, `coupling_score` ran ~0.14-0.15 typically with a PEAK of
**0.213** (crossed 0.20 at least once), vs idle ~0.0 and the shuffle null ~0.02. So COUPLED_CLEAN fires
intermittently over Remote Play (the "~25% COUPLED_CLEAN" thin-signal prior holds), and the question is whether
0.20 is simply mis-set for the Remote-Play regime OR Remote-Play coupling is genuinely marginal.

THE HONEST METHOD (rails — never lower a threshold just to make COUPLED_CLEAN fire). Per active-aim window the
oracle gives TWO numbers: `coupling_score` (real |causal Pearson r|, stick->screen) and `negative_control`
(the SAME window with the input TIME-SHUFFLED = the chance/null baseline; "MUST be << coupling_score"). Calibrate
by SEPARATING real coupling from the null with a MEASURED false-accept rate:
  * adopted threshold = the (1 - FAR_cap) quantile of the null -> FAR is bounded by construction, not assumed;
    it MUST sit strictly above the null's upper tail.
  * verdict ADOPTABLE only if real coupling clears that point with TPR >= floor; if coupled overlaps the null,
    NO threshold is FAR-safe -> INSEPARABLE = the honest "Remote-Play coupling is sub-grade; native-PC for the
    lag pillar" outcome ([[s-wgc-60fps-hdr-delivery-scope]] / cycle-44), NOT a lowered bar.
  * ANTI-GCAP rail (mirrors [[s-nqpv-defensibility-study-scope]]): the shuffle is the WEAKEST honest null;
    structured decoupled motion (auto-camera / replay / another player's POV) can beat shuffle, so a
    shuffle-only ADOPTABLE is PROVISIONAL until structured negatives are added.
  * per-REGIME: a Remote-Play threshold is NOT a native-PC threshold (latency/jitter differ) — label + calibrate
    per regime.

BUILT THIS CYCLE (start calibration):
- `bridge/vapi_bridge/coupling_threshold_calibration.py` — pure `calibrate(coupled, null) -> CalibrationResult`
  {ADOPTABLE | INSEPARABLE | INSUFFICIENT_DATA}; FAR-controlled threshold = null (1-FAR_cap) quantile; TPR +
  separation (median(coupled) - p95(null)); N floors (>=10 any verdict, >=30 production); shuffle-only +
  anti-GCAP caveats baked in. 7 tests (clean-separation ADOPTABLE / overlap INSEPARABLE / small-N INSUFFICIENT
  / FAR-controlled-near-null-p95 / shuffle-only-caveat / session-seed-honest / to_dict).
- `qortroller_retina_capture.py` `RGC.status()` SURFACING — now emits `coupling_score` + `negative_control` +
  `decoupled_energy` + `grid_samples`, so the per-session RGC diag LOGS the calibration data (needs a bridge
  restart to take effect).
- `scripts/calibrate_coupling_threshold.py` — read-only runner: harvests (coupling_score, negative_control)
  pairs from the diag log, runs calibrate(), prints verdict + caveats.
- FIRST PASS on the 2026-06-27 session log: coupled N=26 (range 0.000-0.213) / shuffle-placeholder null N=5 ->
  **INSUFFICIENT_DATA** (separation +0.0665 positive but N too small; null is placeholder pre-surfacing). Honest:
  the harness works, the data isn't there yet.

CAMPAIGN (data/operator-gated; why `likely` not `certain`): (1) restart the bridge so `negative_control` logs;
(2) collect N>=30 LABELLED active-aim Remote-Play windows + structured decoupled negatives (not just shuffle);
(3) calibrate per regime; (4) adopt a calibrated `L9_COUPLING_THRESHOLD` (env-overridable, no code edit) ONLY on
FAR-safe separation with the structured null — else the honest outcome is native-PC for the lag pillar. The
threshold is presence/anti-cheat-relevant, so adoption is an operator decision after the measured envelope, not
an autonomous flip. Default-off posture holds (`retina_coupled_negative_enabled=False`); no FROZEN-v1 / 228B
PoAC / chain / IOTX touch.
