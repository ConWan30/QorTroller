---
type: synthesis
id: s-nqpv-study-corpus-harness-built
title: NQPV defensibility study BUILT (loader + adversary synthesizer + PILOT harness) — empirically proves the fusion separates humans from adversaries ONLY when the presence oracles are live; pilot/co-capture regimes FAIL, full regime PASSES, near-miss all-spoof quantifies the residual
created: 2026-06-26T17:30:00Z
modified: 2026-06-26T17:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 150
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Executes critical-path steps 4-6 of [[s-nqpv-defensibility-study-scope]] (spec: specs/nqpv-defensibility-study.md):
the study-corpus loader, the adversary-corpus synthesizer, and the PILOT study harness. The study now
RUNS end-to-end and returns the honest feasibility readout the RETINA-EXCL-2 scope demanded. Still
ADVISORY/default-off — this is the feasibility gate (PILOT tier), not certification.

BUILT (3 pure modules + injected I/O, Sensor B/C precedent; 22 new tests; PV-CI 182 unchanged):
  - bridge/vapi_bridge/nqpv_corpus_loader.py — NqpvCorpusRecord (tri-state oracle fields; None=ABSTAIN,
    never fabricated) + load_from_rows (normalizes BOTH the records-table shape and the future
    co-capture-sidecar shape) + to_fuse_inputs (maps to fuse() kwargs) + fuse_record + the single
    store-touching I/O fn fetch_human_rows (reuses the tested Store.get_recent_records).
  - bridge/vapi_bridge/nqpv_adversary_synth.py — deterministic (seeded) MODELED adversary corpus across
    4 orthogonal classes: REPLAY (real HW + replayed physics, no live presence), MACRO_INJECTION (fails
    L4/L5/L6), RELAY_AIM_ASSIST (live human, non-causal output), NEAR_MISS_HUMAN (the residual attack,
    behind an explicit spoof_all_rate knob).
  - bridge/vapi_bridge/nqpv_study_harness.py — run_study: fuse every record -> TAR/FAR -> ROC sweep ->
    the MANDATORY anti-GCAP rail (fused TAR >= best single-oracle TAR) -> feasibility verdict
    {PASS | FAIL | INSUFFICIENT_DATA}; supports a PILOT PROJECTION that abstains the not-yet-live oracles.

EMPIRICAL FINDING (30 synthetic full-oracle humans + 80 adversaries, spoof_all_rate=0):
  - FULL regime (all 4 oracles live): PASS — operating point thr=0.2, TAR=1.000, FAR=0.000, anti-GCAP
    holds (best-single cco=1.00). The presence oracles separate replay/relay cleanly.
  - COCAPTURE regime (cco + l4l5l6 live, presence oracles abstained): FAIL — maxFAR=1.0. REPLAY carries
    real hardware AND replayed human physics, so cco+l4l5l6 cannot tell it from a human.
  - PILOT regime (l4l5l6 only — today's strictly-queryable source): FAIL — maxFAR=1.0.
  - FULL + near-miss all-spoof (spoof_all_rate=1.0): FAIL — maxFAR=0.5. Quantifies the residual
    orthogonality attack: a false accept requires spoofing EVERY oracle incl. the screen witness.

THE LOAD-BEARING CONCLUSION: the calibrated NQPV fusion is defensible ONLY when the PRESENCE oracles
(PoEP + the coupled-retina screen witness) are LIVE. In every regime available today (USB-only capture)
it CANNOT separate — reported honestly as FAIL (measurable, no qualifying point), distinct from
INSUFFICIENT_DATA. This converts "we should wire the camera/PoEP" from an aspiration into a measured
prerequisite for certification. It also vindicates the cycle-29 calibrated model's anti-GCAP design: the
rail held (fused TAR never dropped below best-single) in the regime that DID separate — no GCAP collapse.

PERSISTENCE GAP (recorded, not hidden): the live-loop co-capture hook attaches nqpv_* fields to the PITL
meta sidecar, but main.IngestService.on_record maps only a fixed set of pitl_* columns onto the persisted
record — the nqpv_* keys are dropped before insert_record. So today's only queryable oracle is
l4_l5_l6_ok (derived from persisted pitl_humanity_prob). The loader already consumes the richer sidecar
shape; closing the gap is persistence wiring (map nqpv_* -> a column/table), not a loader change. The
PILOT regime above is exactly this single-live-oracle reality, so the FAIL is the truth, not a stub.

HONESTY RAILS: all synthetic — a FAR here measures the fusion LOGIC under a MODELED adversary
distribution (feasibility), NOT an empirical real-world FAR (FULL tier needs real adversary captures +
breadth corpus, hardware-gated). No FROZEN-v1 / 228B PoAC / chain touch; harness read-only over the
corpus; NQPV stays default-off advisory until an operator-gated promotion after a FULL-tier pass. The
sharpening (COUPLED_CLEAN-as-presence, screen-lobe dissolved) already shipped and is not contingent on
this outcome. Related: [[s-nqpv-defensibility-aligning-solution]], [[s-novel-fusion-m1-presence-assessment]],
[[l9-presence-arc]].
