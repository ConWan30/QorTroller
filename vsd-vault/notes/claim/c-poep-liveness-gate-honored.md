---
type: claim
id: c-poep-liveness-gate-honored
title: PoEP-liveness gate is honored, not bypassed
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 10
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-devcert-preinvestigation-report"]
---

The PoEP `poep_present` field abstains (returns `None`) unless **both** keys pass: the operator flag
(`poep_liveness_enabled`) AND the data gate (enrollment verdict not `calibration_incomplete`) —
`poep_activation.py:31-51`. Both are currently true (`bridge/.env`: `POEP_LIVENESS_ENABLED=true`;
recorded proof shows `poep_present=true`), so the field is *activated*, which is gate-honored, not a
bypass or mislabel. It is a real PoEP liveness verdict, session-enrollment-scoped (read from
`~/.vapi/poep_session_verdict.json` and carried per-record), not a weaker substitute. Source:
[[i-devcert-preinvestigation-report]] Confirm 2 (GRADE VERIFIED).
