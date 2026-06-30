---
type: synthesis
id: s-devcert-investigation-synthesis
title: Dev-Cert investigation synthesis — developer_self is PoEP-driven, gate-honored, single-subject N>=30
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 45
relationship_to_predecessor: inputTo
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-devcert-preinvestigation-report", "i-fcert007-followup-report", "c-cert-scope-is-regime-label", "c-live-devcert-poep-driven-pocp-abstains", "c-poep-liveness-gate-honored", "c-no-laundering-surface-implicit-rail", "c-oracle-set-comparability-gap", "c-single-subject-n30-governs", "c-n52-numeric-coincidence", "c-proof-not-self-auditable", "c-triple-sourced-constant-shared-label"]
---

## Summary

The design-review scope mismatch — six PoCP/authorship-strengthening levers targeting a primitive the live
cert does not bind — is **resolved as real**. `developer_self` is a multi-oracle **fusion schema**
([[c-cert-scope-is-regime-label]]) that is **PoEP-driven in current practice**, with screen-coupling PoCP
contributing exactly zero (`window_retina_coupled=0`) and killfeed authorship absent from the proof schema
entirely ([[c-live-devcert-poep-driven-pocp-abstains]]). The PoEP liveness gate is **honored, not bypassed**
([[c-poep-liveness-gate-honored]]); there is **no active laundering surface**, though the independence rail
is implicit, not an explicit field ([[c-no-laundering-surface-implicit-rail]]). The governing data gate is
**single-subject N>=30**, never the population N>=50 ([[c-single-subject-n30-governs]]); the measured band is
N=52 but 100% one subject ([[c-n52-numeric-coincidence]]). Two structural gaps surfaced: verdicts are not
evidence-set comparable and the proof is not self-describing ([[c-oracle-set-comparability-gap]],
[[c-proof-not-self-auditable]]); and the N>=30 constant is triple-sourced with the operator-facing config
field dead, while band scoping is by player-label, not identity ([[c-triple-sourced-constant-shared-label]]).

## Corrected understanding vs original framing

The state-doc's "`developer_self` = PoEP liveness + the developer's profile" was **accurate in live practice
but incomplete on schema**. In practice the recorded cert *is* PoEP(+CCO+L4L5L6)-driven, so the snapshot's
PoEP emphasis is not wrong. But the proof *object* is a multi-oracle fusion (PoEP + PoCP-retina + CCO +
L4L5L6 + PoVCA) with a dormant PoCP slot and no authorship field at all. Per VSD honesty discipline, **source
wins over snapshot**: the cert is a fusion regime label, currently exercising only the PoEP/CCO/L4L5L6 lobes.

## Open decision blocks (OPEN — not resolved by this note)

- **D-CERT-1** — which primitive(s) the engineered developer-cert attests going forward:
  (a) populate the dormant `retina_verdict` slot for `developer_self` + add an `active_oracles` manifest
  field; (b) a new separate PoCP cert scope, existing one untouched; (c) full fold (not blocked by gate
  status, but inherits the comparability gap hardest). Architect sequencing recommendation: resolve D-CERT-8
  first regardless of (a)/(b)/(c).
- **D-CERT-5** — does killfeed authorship become a field on `FusedGamerPresenceProof` (cert-bound) or stay
  `status()`-only (cert-orthogonal, current state)?
- **D-CERT-6** — consolidate the triple-sourced N>=30 constant: wire
  `config.developer_self_cert_min_reflex_n` as the single source of truth (architect lean), or delete it as
  dead config?
- **D-CERT-7** — promote the implicit independence rail to an explicit `verifier_independence` field now (no
  consumer to migrate yet), or defer until a consumer appears?
- **D-CERT-8** (new) — should the proof artifact emit its calibration evidence-base (governing model, band,
  N, player-scope) inline, closing the recomputability gap? Architect lean: yes.
- **D-CERT-9** (new) — the shared-default-label multi-developer hazard: not urgent at N=1; name it now,
  resolve before any second-developer onboarding.

These are recorded for the operator to resolve in a future explicit-go design session. This note resolves
none of them. The prior decision note [[d-developer-self-cert]] (operator-pending) remains the canonical
decision anchor for the developer-self scope.

## Confidence

highly-likely. Both ingredient reports graded VERIFIED with file:line citations and no UNRESOLVED gradings;
the two architect-derived claims (F-CERT-005, F-CERT-008) are graded `likely` individually and do not lift
the floor.

## Scope statement

No code, config, or `.env` changes were made in this cycle. This note and its referenced claim/ingredient
notes are a record of investigation findings only. No D-CERT block was resolved. No cert/bridge/config code
was touched.
