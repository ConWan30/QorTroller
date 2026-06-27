---
type: synthesis
id: s-f5-provenance-quadrille-built
title: F5 provenance-quadrille assembler BUILT (read-only, packaging-only)
created: 2026-06-24T00:00:00Z
modified: 2026-06-24T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 40
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

The F5 assembler assessed in [[s-f5-provenance-quadrille]] is now built:
`bridge/vapi_bridge/provenance_quadrille.py` + 19 tests. This note records WHAT shipped and the
honesty rails it holds — the loop documenting that its own assessment was acted on, the F5 sibling
to [[s-f2-recency-bound-presence-built]].

WHAT: a read-only assembler that fuses the four shipped provenance chains — GIC (cognitive) + WEC
(operational) + CORPUS-SNAPSHOT (corpus) + SIC (methodology) — into ONE attestation that a grind
run is intact across both the product and the process that built it. It READS four already-computed
chain-status dicts (each {head_hex, intact, n_links}), verifies each leg (well-formed 32B head +
intact + >=1 link), and emits a verdict: QUADRILLE_INTACT (all four) / QUADRILLE_BROKEN (a chain
present but broken) / INSUFFICIENT (a chain missing or genesis-only). On all-intact it computes a
unified_root = SHA-256 over the four heads in fixed CHAIN_ORDER — the digest that WOULD be anchored.

HONESTY RAILS (why this is a VSD-worthy build, not just code):
  - Read-only / packaging ONLY — callers pass chain status; the assembler never reads the chain,
    recomputes a chain, signs, or anchors. Mirrors the WMP-lane + recency_bound_presence discipline.
  - NO new FROZEN-v1 family. The unified_root is a PLAIN SHA-256 packaging digest with NO
    `b"VAPI-...-v1"` byte-literal domain tag — so it does not register as a commitment family or
    trip the crypto-drift detectors. A dedicated test (AST over bytes constants) guards this.
    SCHEMA is a lowercase packaging string. NO new PV-CI invariant (179 unchanged).
  - Anti-overclaim by construction: visual_state=`live` ONLY when all four chains are intact; any
    broken/absent chain -> `unverified`; a non-intact attestation MUST NOT carry a unified_root;
    the VPM label declares on_chain_anchor=false until the operator-fired IoTeX anchor lands (as
    GIC_100 was). verify_attestation recomputes the unified_root and rejects a hand-edited `live`,
    a forged root, or a root smuggled onto a broken quadrille. Same discipline as F2 + VSD-emits-VPM.

WHY IT MATTERS: the assembler is the buildable-now half of F5 — a single "is this run provenance-
clean across all four dimensions" check usable today for audits / partner due-diligence. Its
novelty is COVERAGE: no other protocol cross-checks both its product chains and the methodology
chain that builds it. The VALUABLE-headline half (anchoring unified_root on IoTeX) stays an
operator-fired chain write, and the VPM label structurally prevents claiming the anchor early.
Both near-term fusions the loop ranked (F2 winner, F5 runner-up) are now built as read-only
verifiers — each the smallest honest step over shipped evidence, fixtures-first, reversible.
