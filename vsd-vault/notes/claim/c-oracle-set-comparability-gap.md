---
type: claim
id: c-oracle-set-comparability-gap
title: F-CERT-005 — verdicts are not evidence-set comparable (no oracle manifest)
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 15
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-devcert-preinvestigation-report"]
---

ARCHITECT-DERIVED (F-CERT-005), not stated in either report — derived from the Confirm-1 evidence that
`fuse()` builds the verdict from whichever oracles are present, abstaining the rest. Because the active
oracle set varies per proof and the proof carries **no active-oracle manifest**, two
`CONSISTENT_HUMAN_VERIFIED_HARDWARE` verdicts are not necessarily attesting the same evidence set (e.g. one
with PoCP coupled, one with `window_retina_coupled=0`). Comparability across proofs therefore requires
external context the artifact does not carry. Provenance: architect-derived from
[[i-devcert-preinvestigation-report]] Confirm 1. Relates to [[c-proof-not-self-auditable]].
