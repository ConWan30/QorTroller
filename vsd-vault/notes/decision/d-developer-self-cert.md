---
type: decision
id: d-developer-self-cert
title: Adopt developer self-certification as the v0 basis for NQPV presence-oracle liveness — single-subject (the developer) calibration basis + developer-scoped data gate, scoped-and-labeled cert_scope=developer_self, full software-stack activation for the developer; operator-pending signature
created: 2026-06-26T20:30:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

OPERATOR DECISION (2026-06-26, confirmed via two design selections): adopt DEVELOPER SELF-CERTIFICATION
as the v0 basis for NQPV presence-oracle liveness, so the full presence stack can go LIVE for the
developer while playing — without waiting on the population N>=50-across-humans prerequisite. The loop
drafts this record; the operator co-signs (decision notes are never loop-signed).

WHAT IS DECIDED:
1. CALIBRATION BASIS = the developer alone. The developer's own captures define the L4 fingerprint band
   AND the PoEP reflex band (single-subject). This is the starting spec; population breadth is a later
   widening, not a prerequisite for developer-scoped activation.
2. DATA GATE (developer-self scope) = the developer's own N>=30 in-band reflex reactions (single-subject),
   REPLACING the N>=50-across-humans rule FOR developer-self cert only. The population gate (N>=50 across
   humans) remains the prerequisite for a future population/tournament cert.
3. CERT SCOPE + LABELING (the honesty rail, operator-selected "scoped"): the proof reports
   cert_scope="developer_self" with certified=true (developer-self) and population_certified=false. It is
   a REAL certified verdict for the developer's own scope, explicitly NOT a population/tournament claim.
   It upgrades cleanly to population cert later by widening the corpus — same code, wider scope. advisory
   flips to False ONLY within developer_self scope; outside that scope the proof remains advisory.
4. ACTIVATION = a master flag (developer_self_cert) that, for the developer's device/profile, flips the
   SOFTWARE-gated presence stack on TOGETHER: nqpv_cocapture_enabled + poep_liveness_enabled (the
   developer's own two-key) + the validated l4_humanity_reanchor + session-start PoEP enrollment ->
   a live presence proof during play (PoEP is session-level: enroll still at session start, the verdict
   stays live through the match).
5. WHAT STAYS HONEST-GATED EVEN IN DEV MODE: the coupled-retina lobe still needs a camera (hardware) ->
   it abstains until a camera is present. Dev mode lights up everything SOFTWARE-activatable; the camera
   lobe stays honest about needing the rig. Real adversary captures + population breadth remain required
   for population/tournament cert (out of developer-self scope).

HARD-RULE AMENDMENTS (operator-authorized by this decision):
- "L6B_ENABLED=false; never change without N>=50 (population)" -> for DEVELOPER-SELF cert, the gate is the
  developer's own N>=30 in-band reflexes; population N>=50 still governs population cert. L6B_ENABLED and
  poep_enabled remain default-OFF globally; the developer's two-key flips them within dev mode only.
- The NQPV advisory/default-off posture is preserved globally; developer_self_cert is an opt-in,
  reversible (flag off -> back to advisory/default-off) developer-accessibility mode.

WHY THIS IS DEFENSIBLE (not an overclaim): the verdict is honestly SCOPED. A single-subject cert that
silently read as full certified=true would discredit the stack on first outside audit; cert_scope=
developer_self is certified-for-the-developer + population_certified=false, which an auditor can verify
and which upgrades to population cert by widening the corpus. This preserves verification-over-assertion
while giving full developer activation today.

OUT OF SCOPE: no FROZEN-v1 / 228B PoAC / chain / IOTX; no on-chain certification; the 228-byte wire +
L4 anomaly/continuity thresholds are untouched. This decision authorizes a developer-accessibility
activation mode + its labeling, nothing on-chain.

IMPLEMENTATION (follows this decision, separate commits): (a) developer_self_cert config master flag +
cert_scope threaded through novel_presence_fusion -> oracle_panel -> endpoint -> SDK; (b) single-subject
calibration basis + the N>=30 developer data gate (reuse poep_calibration with min_n=30, single-subject)
+ the l4 single-subject band; (c) session-start PoEP enrollment that sets _session_poep_verdict; (d) the
developer-scoped N>=30 reflex campaign. Related: [[s-presence-oracle-liveness-scope]],
[[s-nqpv-corpus-adapter-scope]], [[project_dualconnection_capture_blind_finding]].
