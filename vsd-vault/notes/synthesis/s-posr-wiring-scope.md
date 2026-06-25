---
type: synthesis
id: s-posr-wiring-scope
title: PoSR session-recency wiring SCOPE (Phase 1 default-OFF + Phase 2 ZK-checkpointed)
created: 2026-06-25T00:00:00Z
modified: 2026-06-25T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

The 2026-06-25 activation session lit up the on-chain PoSR rails (TemporalBeaconRegistry keeper
set + live beacon; Arc 7 v2 verifier `VAPIReplayProofVerifier_v2 0xf4106736…` deployed). This note
scopes the bridge-side wiring that makes that infrastructure consumed in the LIVE capture path —
recording the scope before execution so the build has signed provenance, the loop documenting what
it is about to act on. Companion to [[s-f2-recency-bound-presence-built]], which built the read-only
recency-bound presence verifier; this scope makes the same PoSR×PoAC×GIC fusion live at the
session boundary rather than only in a packaging-time read path.

THE GAP: `on_session_complete_vhr` → `VAPIReplayProofPipeline.package_session` still produces an
Arc 5 v1 proof with NO recency binding. The `PoSRBeaconBinder` (with its None-fallback honesty rail)
exists but is never called in the live path; `REPLAY_PROOF_VERIFIER_V2_ADDRESS` is read by nothing.
So the deployed recency rails are inert at the bridge layer. Two structural facts make the wiring
non-trivial: (1) the v2 circuit needs BOTH open and close beacon commitments, but the pipeline only
runs at session close — so an open-beacon capture at session start must be added + persisted;
(2) the v2 proof needs Poseidon beacon commitments via a circomlibjs helper that does not yet exist
(the binder's commitments are SHA-256, a separate on-chain sidecar value) — and circomlibjs/in-circuit
Poseidon byte-equality is the exact hard gate Arc 5 flagged.

THE NOVEL ASSURANCE (QorTroller-exclusive): a generic recency proof asserts "a session happened
between two blocks." QorTroller can assert what no other protocol holds the chains for — "THIS
PoAC-attested session, GIC-chained, on a certified Edge, happened strictly between two on-chain
anchored beacons" — because the open/close commitments chain to the session's `poac_genesis_link` /
`poac_final_link` (the binder already computes this). The recency claim fuses PoAC + PoSR + GIC at
the session boundary, not as an add-on but as the binding itself.

THE PHASE SPLIT (operator decision 2026-06-25):
  - PHASE 1 (autonomous /goal loop): the SAFE, default-OFF wiring + validated beacon DATA PATH —
    config flags (`posr_recency_enabled` default False), open-beacon capture+persist at session
    start, binder integration in `package_session` with v1 fallback, 3 novel-assurance PV-CI
    invariants (INV-POSR-WIRING-001/002/003), tests. With the flag OFF, behavior is byte-identical
    to today. Phase 1 attaches recency metadata to a still-v1 proof — it proves the full
    open→persist→close→strictly-after→commitment-chain path end-to-end WITHOUT touching the ZK prover.
  - PHASE 2 (operator-checkpointed, NOT autonomous): the real v2 Groth16 proof — a new circomlibjs
    Poseidon helper byte-equal to the circuit + `Groth16Prover` v2 mode. Held off the autonomous
    loop precisely because Poseidon byte-equality is the known hard gate that needs operator
    verification, not unsupervised autonomy.

HONESTY RAILS (why this is VSD-worthy, not just code):
  - Default-OFF + fail-closed: a missing/stale beacon, or open==close, degrades to today's exact v1
    behavior. Never fabricate a recency claim. INV-POSR-WIRING-001 pins the fallback.
  - Temporal ordering enforced at the WIRING layer (close.block strictly > open.block,
    INV-POSR-WIRING-002), not only in-circuit — defense in depth, surfaced before any prover runs.
  - No FROZEN-v1 / 228-byte PoAC edit, no Solidity, no deploy, no chain write, no IOTX spend;
    `CHAIN_SUBMISSION_PAUSED` untouched; fully reversible; per-commit /goal audit trail (V/P/Mythos).
  - The keeper-during-play (anchor_beacon.py --loop, ideally bound to an active GIC grind session)
    is the operational reason genuine open<close is satisfiable live — and the real purpose of the
    keeper cadence, not a cost to justify.

WHY IT MATTERS: this is the smallest honest step that makes the deployed recency rails real in the
gameplay path — a default-OFF data path over shipped evidence, fixtures-first, reversible, with the
ZK byte-equality gate explicitly held for operator verification. Promotion (flag-on, real v2 proofs,
on-chain submission) stays a separate operator decision the wiring does not pre-empt.
