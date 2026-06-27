---
type: synthesis
id: s-live-p-l4-reanchor-scope
title: Live-bridge p_L4 re-anchor scope — adopt the corpus-validated 0.5**(d/threshold) in the live humanity formula, DEFAULT-OFF + config-gated (byte-identical when off), because it RAISES humanity and humanity hard-gates the 0.60 passport — operator validates on N>=50 before flipping
created: 2026-06-26T19:45:00Z
modified: 2026-06-26T19:45:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 70
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes adopting the offline-validated p_L4 re-anchor (s-nqpv-corpus-adapter-scope; validated on the real
N=10 1000 Hz corpus) into the LIVE bridge humanity formula. This is the deferred hard-rule-gated decision
flagged across cycles 34-35. Conclusion: build it DEFAULT-OFF + config-gated; the operator flips it only
after a real validation pass. No live behavior change on commit.

THE DEFECT (real): live `_p_l4 = exp(-max(0, d-2))` (dualshock_integration.py:1873) anchors at d=2.0, far
tighter than the measured L4 NOMINAL scale (cfg.l4_anomaly_threshold default 7.009; the N=10 study saw
human-mean d~2.45). So genuine NOMINAL humans are UNDER-credited: at d=5 (well under threshold) p_L4=0.05;
at the threshold p_L4~0.007. Humanity is capped low for real humans — exactly what the offline study
exposed (the re-anchor 0.5**(d/threshold) gives d==threshold->0.5, d~2.45->~0.74, and was coherent on the
real corpus: 9/10 sessions L4-NOMINAL).

THE SAFETY TENSION (why NOT a blind flip): the re-anchor RAISES p_L4 at every d>2 -> RAISES humanity_prob.
humanity_prob is NOT purely advisory — it HARD-GATES passport issuance (bridge_agent.py:649,
"humanity_prob >= 0.60 / minHumanityInt >= 600"). Raising humanity makes the 0.60 gate EASIER to clear,
which is a security LOOSENING — precisely what the hard rule "thresholds can only tighten" guards against.
Mitigant: records with d > anomaly_threshold are ALREADY blocked by the L4 anomaly hard-gate (the
re-anchor only changes the SUB-threshold NOMINAL scoring), so the loosening is bounded to NOMINAL records;
but a near-threshold NOMINAL record (d~6) jumps from p_L4~0.018 to ~0.55, which materially shifts its
humanity — so the net effect on the 0.60 passport pass-rate MUST be measured, not assumed.

THE BUILD (default-off, reversible, hot-loop-safe):
  - New pure helper `l4_humanity.p_l4_from_distance(distance, warmed, *, reanchor_enabled, anomaly_threshold)`
    — OFF (default): byte-identical exp(-max(0,d-2)); ON: 0.5**(d/threshold) clamped [0,1]; not-warmed /
    None -> 0.5. Unit-tested both branches + the byte-identical-when-off rail.
  - dualshock_integration p_L4 site calls the helper with reanchor_enabled = cfg.l4_humanity_reanchor_enabled
    (NEW, default False) and anomaly_threshold = cfg.l4_anomaly_threshold (tracks the runtime threshold).
  - When the flag is False the live humanity formula is BYTE-IDENTICAL to today (regression-asserted).

VALIDATION GATE before the operator flips the flag (documented in the config + note, NOT performed by
this build): (1) a real N>=50 corpus (current is N=10 one-human low-confidence); (2) measure the 0.60
passport pass-rate for humans (should RISE toward correct — the intended fix) AND for the assembled
adversaries (must NOT rise — the anti-loosening check); (3) confirm no per-player threshold is loosened
(the anomaly gate itself is untouched). Only then flip l4_humanity_reanchor_enabled=true.

HONESTY RAILS: default-off = zero live change on commit; the anomaly hard-gate is untouched (this only
re-scores sub-threshold humanity); reversible via the flag; the re-anchor anchors to the configured
threshold so it tracks per-deployment calibration. No FROZEN-v1 / 228B PoAC / chain / IOTX. The 228-byte
PoAC wire + the L4 anomaly/continuity thresholds are NOT touched. Related: [[s-nqpv-corpus-adapter-scope]],
[[project_dualconnection_capture_blind_finding]], [[s-nqpv-capture-regime-resolution-scope]].
