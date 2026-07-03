---
type: ingredient
id: i-dcert-board-implementation-audit
title: D-CERT board-clearance implementation audit — the four commits that resolved D-CERT-1/6/7/9, with grounding
source: claude-code-goal-execution-2026-07-02
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["d-cert8-emit-evidence-base", "i-fcert007-followup-report", "s-devcert-investigation-synthesis"]
---

READ-ONLY provenance audit grounding the four D-CERT board-clearance decisions (VSD-INV-6). No code
was changed by this note. Each block resolved under the /goal board-clearance arc,
verify -> build -> HOLD -> atomic-commit, additive + null-safe, PV-CI 182 throughout. Board artifact:
`audits/dcert-board-clearance-2026-07-02.md` (commit `3383fe2f`).

## The implementation commits (pushed on feat/l9-consistency-adversarial-harness)

- **D-CERT-7 `fc58a7b9`** — `verifier_independence` on FusedGamerPresenceProof
  (novel_presence_fusion.py) + SDK VAPIPresenceProof (vapi_sdk.py) + API (_app.py). Derived in
  fuse() from cert_scope (None = advisory / False = developer_self / True unreachable by
  construction). SDK helper `verifier_is_independent()`. 55 bridge + 53 SDK tests.
- **D-CERT-6 `654fff3d`** — single-source the developer N-gate on
  `config.developer_self_cert_min_reflex_n` (was three uncoordinated `30` literals; the config field
  was the dead one). poep_session_enroll.py `resolve_min_n()` reads it; explicit CLI override wins
  but is logged on divergence. 23 tests.
- **D-CERT-9 `71779014`** — collision guard (option b). poep_session_enroll.py
  `label_corpus_status()` (FAIL-CLOSED) + `collision_verdict()` + `--extend-existing` + enrollment
  nonce + audit meta on verdict/disclosure + `_COLLISION_GUARD_NOTE`. 32 tests + end-to-end
  behavioral (refuse = exit-2 / no-write; extend records the meta).
- **D-CERT-1 `6f9fc2a8`** — active-oracles manifest (option a). novel_presence_fusion.py
  `_oracle_manifest()` (per-oracle outcome, derived in fuse() from the same checks it scores) + SDK
  + API. cert_scope STAYS binary; three-orthogonal-questions invariant stated in-code. 67 bridge +
  62 SDK tests.
- **SDK self-description `deed6dee`** — evidence base + verifier_independence + active_oracles into
  VAPIPresenceProof (closes F-CERT-008/005 one layer up, for the external-auditor audience).

## Boundary
No FROZEN-v1 / 228B PoAC / chain / IOTX / verdict-semantics changed; cert_scope stays binary. The
resolutions are recorded (operator-pending) in [[d-cert7-verifier-independence]] /
[[d-cert6-single-source-n-gate]] / [[d-cert9-collision-guard]] / [[d-cert1-active-oracles-manifest]],
with the reasoning in [[s-dcert-board-clearance]]. The only cert-path block still open is D-CERT-5
(authorship -> cert bind), gated on the RP-session l2_ads calibration + splice-FAR pairing +
range->match transfer.
