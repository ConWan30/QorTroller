---
type: synthesis
id: s-cert8-self-describing-proof
title: D-CERT-8 — emit the calibration evidence base inline; it is the cheapest first move because it turns the rest of the set from reverse-engineering into field-checks
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 40
relationship_to_predecessor: inputTo
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-cert8-proof-schema-audit", "c-proof-not-self-auditable", "c-oracle-set-comparability-gap", "c-single-subject-n30-governs", "c-triple-sourced-constant-shared-label", "s-devcert-investigation-synthesis"]
---

## Recommendation

Resolve **D-CERT-8 = YES**: `FusedGamerPresenceProof` should emit its calibration evidence base
inline — `governing_model`, `calibration_band`, `calibration_n`, `calibration_player_scope`
([[i-cert8-proof-schema-audit]]) — so the proof *stream alone* is self-describing and the F-CERT-008
recomputability gap ([[c-proof-not-self-auditable]]) closes. This matches the architect lean recorded
in [[s-devcert-investigation-synthesis]] and honors the sequencing note there ("resolve D-CERT-8
first regardless of D-CERT-1's (a)/(b)/(c)").

## Why it is the *cheapest first move* (the load-bearing claim)

D-CERT-8 is the keystone not because it is the biggest change but because it changes the SHAPE of the
other open blocks — each one currently requires reverse-engineering the basis from the filesystem;
after D-CERT-8 each becomes a check against a declared field:

- **D-CERT-1** (which primitive the cert attests / `active_oracles` manifest): the comparability gap
  ([[c-oracle-set-comparability-gap]]) is "two verdicts aren't evidence-set comparable." A proof that
  declares its own `governing_model` + (with D-CERT-1's `active_oracles`) its contributing lobes makes
  comparability a *field comparison*, not an inference. D-CERT-8 is the substrate D-CERT-1 writes onto.
- **D-CERT-6** (consolidate the triple-sourced N>=30 constant, [[c-triple-sourced-constant-shared-label]]):
  once `calibration_n` is a first-class emitted field, "which of the three sources is authoritative"
  has an obvious answer — the one the proof emits — and the dead config field becomes either the single
  source feeding it or provably unused.
- **D-CERT-7** (promote the implicit independence rail to an explicit field): a proof already carrying
  its evidence base is the natural place the `verifier_independence` field lands; D-CERT-8 opens the
  emit surface D-CERT-7 extends.
- **D-CERT-9** (shared-default-label multi-developer hazard): `calibration_player_scope` as an emitted
  field is exactly the identity-vs-label distinction D-CERT-9 needs named — surfacing it now makes
  D-CERT-9 a validation on a field rather than a latent ambiguity.

So the set is a dependency fan-out from one substrate: **make the proof self-describing, then every
other block is "declare/verify a field" instead of "reconstruct the basis from `poep_l9/`."**

## Honest scope of this recommendation

This synthesis recommends the DIRECTION; it does not itself change code. The four field names are the
audit's proposal ([[i-cert8-proof-schema-audit]]), not a frozen schema — the operator's decision
([[d-cert8-emit-evidence-base]], pending) fixes names + placement. Two honest limits: (1) the
`governing_model` value today is singular (developer-self, PoEP-driven) so the field is low-entropy at
N=1 — its value is forward (it stops being trivial the moment a second regime/oracle-set exists, which
is when comparability actually bites); (2) emitting the evidence base does NOT make the cert
population-valid — `population_certified` stays `False`; self-describing ≠ more-certified, it is
more-auditable. The l2_ads second channel that D-CERT-5 would bind remains parked on the
RP-reliable-L2 finding, so D-CERT-5 is untouched here — D-CERT-8 is deliberately the block that does
NOT depend on the parked channel.

## Confidence

likely. The gap and the schema are VERIFIED with file:line citations ([[i-cert8-proof-schema-audit]],
novel_presence_fusion.py:45–75, :281, :306–307); the *recommendation* is a design judgment (that
self-describing-first is the cheapest sequencing), which is argued but not measured — hence `likely`,
not `highly-likely`.
