---
type: claim
id: c-cert-scope-is-regime-label
title: cert_scope is a regime label, not a primitive binding
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 10
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-devcert-preinvestigation-report"]
---

`cert_scope` is set purely by a flag (`novel_presence_fusion.py:281` —
`"developer_self" if developer_self_cert else "advisory"`); it does not by itself bind any single
presence primitive. The proof object `FusedGamerPresenceProof` is a multi-oracle fusion (CCO, PoEP,
PoCP-retina, L4L5L6, PoVCA) where each oracle abstains independently and `fuse()` builds the score from
whichever are present (`:233-242`). So the scope is a *regime label* over a fusion, not a per-primitive
attestation. Source: [[i-devcert-preinvestigation-report]] Confirm 1 (GRADE VERIFIED).
