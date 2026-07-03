---
type: decision
id: d-cert9-collision-guard
title: D-CERT-9 — close silent cross-subject label pooling with a collision guard (option b); label->device binding is the Arc-2-gated completion; operator-pending signature
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-dcert-board-clearance", "i-dcert-board-implementation-audit", "i-fcert007-followup-report"]
---

DECISION — OPERATOR CO-SIGNED via git-attestation (loop-drafted; implemented + pushed `71779014`).

CO-SIGN NOTE: decision notes are never loop-signed; the manifest stays `signed:false /
pending:operator`. Git-attestation (the operator-authorized commit under the single-committer's wallet,
this ceremony fired via /goal) is the co-sign. No forged architect signature.

WHAT IS DECIDED — **(b) collision guard**, NOT (a) label->device binding, on the Phase-0 facts:
1. **Fact A** — no per-unit identity is reachable at the enroll call site today. The only `device_id`
   there is the model string "Sony_DualShock_Edge_CFI-ZCP1" (identical for every Edge); the real
   per-unit `DEVICE_ID_CANON_v1 = keccak256(SEC1 pubkey)` is secure-element-rooted and Arc-2-gated.
   Binding to a weaker unverified HID serial would be a precision-looking-but-unproven bind — the shape
   this protocol keeps refusing. **So (a) is the Arc-2-gated COMPLETION of this arc, not a rejected
   alternative; the collision guard is increment one of it.**
2. **Fact B** — the label-as-sole-scope mechanism is already live across six labels (DEV + P1..P5, all
   sharing the model device_id), so (c) defer is not the honest form of deferral.
3. **The guard closes the SILENT part of silent pooling — the actual hazard.** `label_corpus_status()`
   is FAIL-CLOSED (returns 'fresh' only when it can PROVE the label unused; unreadable corpus ->
   'ambiguous' -> treated as existing). Enrolling under a not-fresh label REQUIRES `--extend-existing`
   (exit-2 / nothing written otherwise); a deliberate extension proceeds and is recorded. Deliberate
   pooling under the flag is an operator decision — allowed to be wrong as long as it is visible.
4. **detection != prevention** (stated verbatim in `_COLLISION_GUARD_NOTE`): the enrollment-instance
   nonce makes accidental pooling POST-HOC DETECTABLE, not prevented. Prevention is the Arc-2-gated
   label->device binding.

GATE (named event, not a someday): (a) label->device binding lands when Arc 2 delivers
DEVICE_ID_CANON_v1 at the enroll site. HONESTY RAILS: enroll-only; l9_presence capture path +
poep_calibration.py untouched; no verdict-semantics change.
