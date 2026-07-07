---
type: synthesis
id: s-dcert-board-clearance
title: D-CERT board clearance — five of six blocks resolved-and-implemented; the resolutions and why each option won on cost-at-call-sites
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 90
relationship_to_predecessor: inputTo
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-dcert-board-implementation-audit", "s-devcert-investigation-synthesis", "s-cert8-self-describing-proof"]
---

## Recommendation

Record D-CERT-1/6/7/9 as RESOLVED (operator-pending decision notes), symmetric with how cycle 57
opened the D-CERT set signed. D-CERT-8 (cycle 58) was the keystone — self-description made the rest
field-level jobs — and the four blocks then fell in dependency order, each with Phase-0 facts before
options and cost-at-call-sites rather than cost-by-name. Grounding: [[i-dcert-board-implementation-audit]].

## Why each option won (the load-bearing claim: cost at the call sites, not the promise)

- **D-CERT-7** — make the verifier-independence rail explicit. Derived structurally inside fuse() from
  cert_scope (a param could be set by a caller; a derivation cannot lie). `True` is unreachable by
  construction today — the slot a future independent-verification path fills, not dead code.
- **D-CERT-6** — wire the config field as THE N-gate source. The fix was not "wire the field" but
  "make the canonical-looking thing actually canonical": F-CERT-007's finding was that the
  operator-facing field was the dead one. CLI-override divergence is logged so a one-off can never
  become a fourth uncoordinated literal — the drift mechanism closed at its source.
- **D-CERT-9** — collision guard (b), NOT label->device binding (a). Fact A killed (a) at honest cost:
  no per-unit identity is reachable at the enroll call site (DEVICE_ID_CANON_v1 is secure-element-
  rooted + Arc-2-gated; only the model string is present). Binding to an unverified HID serial would
  be a precision-looking-but-unproven bind. Fact B killed (c) defer: the label-as-sole-scope mechanism
  is already live across six labels. (b) closes the SILENT path; (a) is the Arc-2-gated COMPLETION.
- **D-CERT-1** — active-oracles manifest (a), one scope, NOT scope-per-oracle-set (b). The manifest IS
  the mechanism that made one-scope safe: F-CERT-005's gap was verdicts not declaring their evidence
  set; the fix is declaration, not scope multiplication. (b) would reintroduce D-CERT-6's uncoordinated-
  literal drift at the scope layer, touching every `== "developer_self"` branch. cert_scope stays binary.

## The invariant this establishes

Every proof declares who vouches (cert_scope), whether the voucher is independent
(verifier_independence), what evidence backed it (active_oracles), and on what calibration basis (the
D-CERT-8 evidence base) — end-to-end through the SDK, with silent label-pooling closed at enrollment.
Three orthogonal questions, three fields, none doing another's job.

## Honest scope

Self-describing != more-certified: population_certified stays False throughout; these close
AUDITABILITY gaps, not certification gaps. Two completions are deferred on NAMED events, not parked as
intentions: Arc-2 identity binding (D-CERT-9), and the poep/l4l5l6 abstained-vs-absent input-type
conflation (D-CERT-1, "abstained_or_absent" named honestly; resolves when the fusion input schema is
next opened). The only open cert-path block is D-CERT-5 (authorship -> cert), gated on the RP session.

## Confidence

highly-likely. The resolutions are implemented + verified (bridge/SDK suites green, PV-CI 182) and
operator-affirmed at each HOLD; not `certain` only because the two deferred completions remain open on
their gates and D-CERT-5 is unresolved by design.
