---
type: synthesis
id: s-fusion-near-term-leverage
title: F2 (recency-bound living presence) has the highest near-term fusion leverage
created: 2026-06-23T00:00:00Z
modified: 2026-06-23T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 30
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Ranks the five fusions in [[s-feature-fusion-enhancements]] by NEAR-TERM leverage, scored as
(primitives-already-shipped) x (core-thesis value) / (external gate + build surface). The
ranking is `likely`; the act of BUILDING any of them remains an operator decision, not this
note's authority.

CONCLUSION: F2 (recency-bound living presence) wins near-term. F5 (provenance quadrille) is the
lowest-risk runner-up. F1/F3 are gated on things the protocol does not yet control
(Qorvo partner + hardware for F1; Stage-A Empirical-Unknown-#1 measurement for F3). F4 is
high-value but a multi-contract end-to-end surface under the deploy-hold.

WHY F2:
- All three primitives are already LIVE, not roadmap: PoSR temporal beacon is deployed
  (Arc 6, FROZEN-v1 #14, VAPITemporalBeaconRegistry 0x96244031...); GIC is live and reached
  GIC_100; L9/PoCP causal coupling is validated. The fusion is a SOFTWARE composition over
  shipped pieces — zero hardware, zero external partner, zero open measurement gate.
- It advances the CORE thesis, not a side surface: PoCP proves a session is causally-live
  (input->output coupling); PoSR proves it cannot backdate/replay; binding them closes the
  relay+replay seam that either primitive alone leaves open. That seam is exactly the
  cloud-gaming-bot stealth pattern the BT-calibration anchor names as the real adversary.
- It is composable as a read path first (no chain write): a verifier that reads the PoCP
  verdict + the beacon-bound recency + the GIC link and emits a single recency-bound presence
  attestation. A VPM honesty label (the VSD-emits-VPM grammar shipped this session) keeps it
  from overclaiming standalone-tournament-grade.

HONEST CAVEAT (load-bearing): L9/PoCP is validated but NOT standalone-tournament-grade per the
L9 arc; the fusion STRENGTHENS an existing presence capability, it does not manufacture a new
standalone one. F2 should ship wearing a VPM label whose visual_state reflects that ceiling
(not `live`-as-tournament-grade) until breadth/measurement justifies promotion. This is the
same anti-overclaim discipline the loop just applied to itself.

WHY F5 IS THE RUNNER-UP: the non-chain half (a read-only unified provenance assembler over GIC
+ WEC + CORPUS-SNAPSHOT + SIC) is pure software and ALREADY begun (VSD-emits-VPM bound the SIC
arm to the protocol's honesty grammar this session). Lowest build risk of all five; its
headline value (on-chain SIC anchor) is operator-fired, so the high-value step is gated even
though the assembler is not.

NEXT MOVE IF F2 IS CHOSEN (operator decision): a read-only `recency_bound_presence` verifier
(reads PoCP + beacon + GIC, emits one attestation + a VPM label), fixtures-first, no chain
write, no FROZEN edit — mirrors the WMP-lane and Sensor-A v0.2 shapes already proven in-repo.
