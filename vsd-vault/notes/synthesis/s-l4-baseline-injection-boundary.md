---
type: synthesis
id: s-l4-baseline-injection-boundary
title: Do NOT script-inject an L4 baseline to unblock enrollment — it fails the protocol's own integrity guards (a loop self-catch)
created: 2026-06-26T00:00:00Z
modified: 2026-06-26T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 45
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Operator asked me (correctly, in good faith) to compute + write a per-device L4 baseline from the
existing record corpus to break the enrollment deadlock and reach M1. Running that request through
the VSD discipline instead of just executing it surfaced that I should NOT do it — and WHY. This
note records the reversal honestly: the loop catching its own operator's would-be integrity
violation is exactly what the self-verifying loop is for.

THE DEADLOCK (confirmed, real): CERTIFY → M1 requires device_enrollments.status == "eligible", which
EnrollmentManager flips only when nominal_count >= 10 AND avg_humanity >= 0.60. avg_humanity is stuck
at ~0.36 because player_calibration_profiles holds an ALL-ZERO baseline (baseline_mean=0,
baseline_std=0) — it was never computed. Zero baseline → huge L4 Mahalanobis distance → humanity
collapses → enrollment never triggers. The diagnosis is right; the operator's "calibrate on my data"
instinct is the correct shape of the fix.

WHY A SCRIPT-INJECTED BASELINE IS THE WRONG FIX (three independent guards it violates):

  G1 — THRESHOLDS ONLY TIGHTEN. Per-player L4 thresholds may only tighten from the global 7.009
  anomaly threshold (enforced by min()). The live distances are 31–59 (above 7.009); the only way a
  hand-written baseline makes them pass is to LOOSEN the threshold to ~mean+3σ of those distances
  (~75) — which is precisely what the tighten-only guard exists to forbid. A baseline that certifies
  the player by loosening is the textbook prohibited move.

  G2 — SEPARATION DEFENSIBILITY. The alternative — re-adding the player to the corpus centroid so
  their distance drops — CHANGES the inter-player separation ratio, which is the tournament
  defensibility gate (AIT ratio 1.199, separation_defensibility_log). That recompute must pass the
  defensibility ceremony, not a side-channel DB write. Injecting a centroid bypasses the exact
  cryptographic-honesty property the protocol sells.

  G3 — CEREMONY BYPASS. device_enrollments is a Phase-62 ENROLLMENT CEREMONY state machine driven by
  EnrollmentManager over genuine NOMINAL sessions, with a downstream (chain-gated) PHGCredential mint.
  A raw upsert of "eligible" + a fabricated baseline forges the ceremony's output. A "certified"
  session sourced from an injected baseline is a FAKE proof — strictly worse than no proof for a
  protocol whose entire value is verifiable, defensible certification.

THE DEEPER MISWIRING THIS EXPOSES (the genuinely useful finding): M1 is a PRESENCE claim
(recency-bound human replay), but its CERTIFY gate runs through the IDENTITY-enrollment machinery
(device_enrollments / L4 corpus / separation). There is no "presence-grade enrollment" path into the
current CERTIFY gate. So either (a) the player completes genuine IDENTITY enrollment (full ceremony +
defensibility — heavyweight, and only honest if their fingerprint truly enters the corpus), or (b)
the VHR verdict gate is deliberately reconfigured to accept a presence-grade verdict (the
replay_require_verdict manifest setting / a scoped code path) — a design decision, operator-fired,
recorded, NOT a calibration hack. That fork is the real decision; the baseline injection was a
shortcut around it.

THE GENUINE PATH (now unblocked): the enrollment deadlock is broken by REAL NOMINAL sessions, which
are finally possible — USB capture is NOMINAL/EXCLUSIVE_USB at ~1.6 kHz this session (the BT-114 Hz
era is over). So: play/capture genuine NOMINAL sessions on USB → the live EnrollmentManager computes
the baseline + accrues nominal_count THROUGH the protocol's own pipeline (guards intact) → humanity
rises legitimately → eligible → CERTIFY → M1. The fix was never a script; it was the stable USB
capture we already achieved, plus letting the ceremony run.

HONESTY RAILS:
  - The VSD loop documents this decision; it does NOT and must NOT write biometric calibration or
    flip enrollment. That is outside its mandate and crosses G1–G3.
  - I am reversing a prior in-session offer to compute+write the baseline. The reversal is the
    correct outcome: "I'll do the right one or none" resolves to NONE for a direct injection.
  - If the operator wants the presence-grade M1 specifically, the honest lever is the VHR verdict
    gate (option b above) as an explicit, recorded design change — not a forged identity enrollment.
