---
type: ingredient
id: i-cert8-proof-schema-audit
title: D-CERT-8 schema audit — what FusedGamerPresenceProof emits vs the calibration evidence base it omits
source: claude-code-investigation-2026-07-02
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["c-proof-not-self-auditable", "c-oracle-set-comparability-gap"]
---

READ-ONLY code audit grounding D-CERT-8 (provenance only — VSD-INV-6). No code was changed.

## What the proof artifact emits today

`FusedGamerPresenceProof` (bridge/vapi_bridge/novel_presence_fusion.py:45–75) carries, verbatim:
`verdict`, `device_id`, `record_hash`, `cco_tier`, `retina_verdict`, `poep_present`,
`l4_l5_l6_consistent`, `presence_score`, `disagreement_index`, `binding_ok`, `timestamp_ns`,
`commitments`, `notes`, `cert_scope` (default `"advisory"`; `:63`), `population_certified`
(`False`; `:64`), and the PoVCA fields (`posca_*`, `:71–75`). The build site sets
`cert_scope = "developer_self" if developer_self_cert else "advisory"` and `population_certified=False`
(`:281`, `:306–307`).

## What it does NOT emit (the evidence base) — confirms F-CERT-008

The proof records the *result* (`poep_present=true`, `cert_scope=developer_self`) but not **what
authorized it**: the governing model, the reflex band, the calibration N, or the player-scope. Per
[[c-proof-not-self-auditable]], `~/.vapi/poep_session_verdict.json` carries this-session
`n_reacted`/`n_in_band` but not the band's calibration N; recovering the evidence base (N=52,
single-subject, player DEV) required filesystem access to `poep_l9/`. So an auditor of the proof
*stream alone* cannot reconstruct the basis — the artifact is not self-describing.

## The four evidence-base fields D-CERT-8 would add (and their live sources)

Grounded in the schema above, the recomputability gap closes by emitting, inline on the proof:
1. `governing_model` — the certifying regime + model id (today: the developer-self fusion regime,
   PoEP-driven per [[c-live-devcert-poep-driven-pocp-abstains]]; the value the `cert_scope` label
   already implies but does not carry as data).
2. `calibration_band` — the reflex-band spec that defined "in-band" for this verdict (the band whose
   N the session's `n_in_band` is measured against).
3. `calibration_n` — the band's calibration N (the 52), distinct from the session `n_in_band` the
   proof already implies via `poep_present`.
4. `calibration_player_scope` — the single-subject player label the band was fit on (DEV), making the
   "single-subject" honesty of `cert_scope=developer_self` a verifiable field, not just prose.

## Boundary

No FROZEN-v1 / 228B PoAC / chain / cert-code change proposed by THIS note — it is an audit of the
emit surface. The decision to add the fields is [[d-cert8-emit-evidence-base]] (operator-pending).
