---
type: claim
id: c-single-subject-n30-governs
title: single-subject N>=30 governs developer_self; population N>=50 never called
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 10
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-fcert007-followup-report"]
---

The actual gate for `developer_self` enrollment is `single_subject_reflex_model(min_n=30)`:
`scripts/poep_session_enroll.py:53` -> `poep_calibration.py:92,98,43-48` (`calibration_complete = len(rx)
>= 30`). The population N>=50 L6B path (`poep_readiness` / `liveness_score` / `poep_verify`) is **never
called** on this code path. The bridge reads the resulting single-subject verdict via
`read_session_poep_verdict` (`poep_activation.py:54-73`). Source: [[i-fcert007-followup-report]]
(GRADE VERIFIED).
