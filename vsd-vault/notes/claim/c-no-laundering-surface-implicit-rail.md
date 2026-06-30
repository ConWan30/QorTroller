---
type: claim
id: c-no-laundering-surface-implicit-rail
title: no laundering surface today; independence rail is implicit
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 10
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-devcert-preinvestigation-report"]
---

No consumer today weights `developer_self` as independent third-party trust: no marketplace / Curator /
readiness / aggregate reads `cert_scope` as a trust input. The honesty rail is `population_certified=False`
and `certified=False`, hardcoded on every proof (`novel_presence_fusion.py:307`, `operator_api/_app.py:1324-1326`).
There is **no explicit `verifier_independence` field** (grep: absent). That makes the rail *implicit* — a
latent (not currently exploited) risk: a future consumer reading only `cert_scope` /
`is_developer_self_certified()` without checking `population_certified` could launder a single-subject cert
as independent trust. Source: [[i-devcert-preinvestigation-report]] Confirm 3 (GRADE VERIFIED).
