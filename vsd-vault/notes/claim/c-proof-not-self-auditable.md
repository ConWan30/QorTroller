---
type: claim
id: c-proof-not-self-auditable
title: F-CERT-008 — proof artifact is not self-describing for its evidence base
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 12
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-fcert007-followup-report"]
---

F-CERT-008: the proof artifact records `poep_present=true` but **not** the governing model, band, or
calibration N that authorized it. The verdict file `~/.vapi/poep_session_verdict.json` carries
`n_reacted`/`n_in_band` (this session) but not the band's calibration N. Recovering the evidence base
(N=52, single-subject, player DEV) required filesystem access to `poep_l9/`. The artifact is therefore not
self-describing — an auditor of the proof stream alone cannot reconstruct what authorized it. Source:
[[i-fcert007-followup-report]] anomaly 3 + architect synthesis. Relates to
[[c-oracle-set-comparability-gap]].
