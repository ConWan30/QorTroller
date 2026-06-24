---
type: synthesis
id: s-f5-provenance-quadrille
title: F5 provenance quadrille — a read-only assembler over four shipped chains
created: 2026-06-24T00:00:00Z
modified: 2026-06-24T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 35
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Assesses F5 from [[s-feature-fusion-enhancements]] (ranked lowest-risk runner-up in
[[s-fusion-near-term-leverage]]): fuse the four provenance chains QorTroller already ships into one
read-only attestation that a grind run is consistent across BOTH the product and the process that
built it. The ranking + design are `likely`; building the assembler is an operator decision.

THE FOUR CHAINS (all shipped, each a SHA-256 hash chain with its own FROZEN genesis tag):
  - GIC  `VAPI-GIC-GENESIS-v1`  (grind_chain.py)        — COGNITIVE: per-session adjudication continuity
  - WEC  `VAPI-WEC-GENESIS-v1`  (watchdog_chain.py)     — OPERATIONAL: per-restart bridge continuity
  - CORPUS-SNAPSHOT `VAPI-CORPUS-SNAPSHOT-v1` (corpus_snapshot.py) — CORPUS: wiki+agent-root integrity
  - SIC  `VAPI-SIC-GENESIS-v1`  (synthesis_integrity_chain.py) — METHODOLOGY: per-cycle synthesis integrity

Today these chains stand alone. F5 is the read-only ASSEMBLER that reads each chain's head + intact
flag and emits one unified provenance attestation: "at this grind session, all four chains are intact
and head-consistent." The novelty is coverage — no other protocol chains BOTH its product (GIC/WEC/
CORPUS) AND the methodology that builds it (SIC) under one verification. VSD-emits-VPM (cycle 4) was
the first concrete step: it bound the SIC arm to the protocol's own visual-honesty grammar.

WHY LOWEST-RISK (runner-up, not winner): the assembler is pure software — it READS four existing
chain-status surfaces and packages a verdict. No new crypto, no new FROZEN family, no chain write.
Mirrors the WMP-lane / recency_bound_presence packaging discipline already proven in-repo. Its build
risk is below F2's because it computes nothing new — it only cross-checks heads that already exist.

WHY STILL THE RUNNER-UP, NOT THE WINNER (honest gating): F5's HEADLINE value is anchoring the unified
root on IoTeX (as GIC_100 was anchored), and that is an operator-fired chain write — gated, not
autonomous. The read-only assembler is buildable now and useful now (a single "is this run provenance-
clean across all four dimensions" check for audits / partner due-diligence), but the high-value
on-chain step waits for operator GO + wallet budget. So the BUILDABLE half is low-risk; the
VALUABLE-headline half is gated. That split is why F2 (whose full value is reachable with no chain
write) outranked F5 near-term in [[s-fusion-near-term-leverage]].

SHAPE IF BUILT (operator decision): a read-only `provenance_quadrille` assembler that takes the four
chain-status dicts (each {head_hex, intact, n_links}) + a grind_session_id, verifies all four intact,
and emits one attestation + a VPM honesty label. visual_state=`live` only when all four are intact;
any broken/absent chain -> `unverified`; the label declares on_chain_anchor=false until the operator-
fired anchor lands. Fixtures-first, no chain read inside the assembler (callers pass status), no
FROZEN edit. The same anti-overclaim discipline F2 and VSD-emits-VPM already hold.
