---
type: synthesis
id: s-nqpv-corpus-adapter-scope
title: NQPV hw_*→NqpvCorpusRecord adapter scope — replay the offline humanity pipeline over the real N=10 1000 Hz corpus, with the p_L4 re-anchor living OFFLINE (study-only), never touching the hard-rule-gated live bridge formula
created: 2026-06-26T18:45:00Z
modified: 2026-06-26T18:45:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 110
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the adapter that turns the validated real N=10 1000 Hz human biometric corpus
([[project_dualconnection_capture_blind_finding]], sessions/human/hw_nqpv_001..010.json) into
human-positive NqpvCorpusRecords the RETINA-EXCL-2 harness consumes — closing the last gap between the
captured corpus and a study run with REAL human data (vs the synthetic humans in the cycle-31 demo).
Builds on [[s-nqpv-capture-regime-resolution-scope]] (which identified the 1000 Hz requirement) and
[[s-nqpv-study-corpus-harness-built]] (loader/harness).

GOAL: a pure-ish offline module `nqpv_offline_humanity.py` (+ runner) that, per session, replays the
PITL humanity pipeline over the 1000 Hz reports and emits NqpvCorpusRecord(label=human) with a REAL
humanity-derived l4_l5_l6_ok — feeding `nqpv_study_harness.run_study` against the synthetic adversaries
(nqpv_adversary_synth) for the first measured human-TAR / adversary-FAR + the anti-GCAP gate.

DESIGN (reuse proven parts; no live hot-path touch):
  - Extract: `controller.tinyml_biometric_fusion.BiometricFeatureExtractor` at CALIBRATION_WINDOW_FRAMES
    (validated: accel_entropy 4.23 mean / 78% in 3-8.6 over the corpus). One NqpvCorpusRecord PER WINDOW
    (~58/session → ~580 human records) for harness statistics; synthetic per-window device_id/record_hash
    (mirrors the adversary synth binding).
  - L4 distance: reuse `mahalanobis(vector, mean, diag_cov)` (line 762) against the population centroid
    built from the N=10 corpus fingerprints (profile session_stats l4_mahal_dist_mean=2.454/std=1.041;
    anomaly threshold 5.579 = mean+3σ). Leave-one-out per session for an honest distance (a session is
    not scored against a centroid that includes itself).
  - humanity: the FROZEN baseline 5-signal formula 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·0.5 +
    0.10·0.5, with p_L5 = l5_rhythm proxy from the extractor, p_E4 from e4 drift, p_L2B/p_L2C neutral
    (no L2B/L2C oracle offline). l4_l5_l6_ok = humanity >= 0.5.

p_L4 RE-ANCHOR — OFFLINE, STUDY-ONLY (the load-bearing discipline): the live formula
`_p_l4 = exp(-(d-2))` (dualshock_integration.py:1792) gives p_L4≈0.0067 at the 5.58 threshold — it
under-scores real human distances (corpus mean d≈2.45). The adapter uses a RE-ANCHORED p_L4 (e.g.
`0.5 ** (d / anomaly_threshold)` so d==threshold→0.5, d≈2.45→~0.74) computed AGAINST the measured N=10
profile. This re-anchor lives ONLY in the offline adapter — it does NOT edit the live bridge formula
(that change alters live humanity for every record, is gated by the hard rules "thresholds only tighten"
+ "do not change without re-deriving", and is a SEPARATE deferred decision). The adapter exposes the
anchor as an injectable so the live-formula decision can later adopt the validated value.

HONESTY RAILS: N=10 is "low confidence" (target N≥50); the corpus is ONE human (the operator) → the
study measures human-TAR for one human + adversary-FAR vs MODELED adversaries = feasibility, NOT a
population/tournament claim (breadth is the standing open lever — BCC). Presence oracles (PoEP +
coupled-retina) still ABSTAIN — so even with real L4 the study lands in the cco+l4l5l6 regime the harness
proved FAILs to fully separate; the value is a real human-positive substrate + the p_L4 anchor validated
on real data + the pipeline proven end-to-end. NQPV stays advisory/default-off. No FROZEN-v1 / 228B PoAC
/ chain / IOTX; offline module only; sessions gitignored. Related: [[s-nqpv-study-corpus-harness-built]],
[[s-nqpv-capture-regime-resolution-scope]], [[l9-presence-arc]].
