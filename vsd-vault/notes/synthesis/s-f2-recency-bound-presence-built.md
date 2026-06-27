---
type: synthesis
id: s-f2-recency-bound-presence-built
title: F2 recency-bound presence verifier BUILT (read-only fusion, packaging-only)
created: 2026-06-24T00:00:00Z
modified: 2026-06-24T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 45
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

The F2 fusion ranked highest-near-term-leverage in [[s-fusion-near-term-leverage]] is now built:
`bridge/vapi_bridge/recency_bound_presence.py` + 20 tests. This note records WHAT shipped and the
honesty rails it holds — the loop documenting that its own recommendation was acted on.

WHAT: a read-only verifier fusing three ALREADY-SHIPPED primitives into one session attestation —
PoCP causal coupling (l9_presence.coupling.CouplingFeatures) x PoSR temporal beacon
(replay_proof_pipeline.posr.PoSRSessionBeacon) x GIC link (grind_chain). The fusion VALUE is the
three-leg verification: (1) PoCP leg requires coupling above threshold AND the negative control
(time-shuffled input) to COLLAPSE — that collapse is the anti-relay core, since a relayed stream
may show apparent coupling but shuffled input must lose it; (2) PoSR leg requires close block
strictly after open AND cadence-aligned open (% 64) — forward ordering is the anti-backdate/replay
guard; (3) GIC leg requires a well-formed link = cognitive continuity. Only all-three-pass yields
verdict RECENCY_BOUND_PRESENT; partial states are PRESENT_NOT_RECENCY_BOUND / DECOUPLED_REVIEW /
INSUFFICIENT. This closes the relay+replay seam either primitive alone leaves open.

HONESTY RAILS (the reason this is a VSD-worthy build, not just code):
  - Packaging/verification ONLY — reads already-computed leg verdicts; no numpy, no chain read,
    no signing, no anchoring. Mirrors the WMP-lane bundle_assembler discipline.
  - No new FROZEN-v1 family, no new PV-CI invariant (179 unchanged). SCHEMA is a packaging string.
  - Anti-overclaim BY CONSTRUCTION: every pass carries a mandatory claim_scope =
    "session-bound; NOT standalone-tournament-grade" (PoCP is validated but not tournament-grade
    per the L9 arc), and the emitted VPM honesty label declares zk_verified=false /
    on_chain_anchor=false. visual_state is `live` ONLY on a full real-capture recency-bound pass;
    synthetic input renders `emulated`; any failed leg renders `unverified`. verify_attestation
    re-checks visual_state == derived, so a hand-edited `live` over a decoupled session is rejected.
    This is the SAME anti-overclaim discipline the VSD loop applies to itself (VSD-emits-VPM).

WHY IT MATTERS: F2 strengthens an existing presence capability without asserting what it cannot
prove — the core QorTroller thesis ([[s-purpose-of-vapi]]) applied to a concrete fusion. The
verifier is the smallest honest step: a read path over shipped evidence, fixtures-first, reversible.
Promotion to a chain-anchored or tournament-grade claim remains a separate operator decision gated
on breadth + the same-model separability study (CROSS-LESSON-001), and the VPM label structurally
prevents claiming it early.
