---
type: decision
id: d-cert7-verifier-independence
title: D-CERT-7 — make the verifier-independence rail an explicit field on FusedGamerPresenceProof; operator-pending signature
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-dcert-board-clearance", "i-dcert-board-implementation-audit"]
---

DECISION — OPERATOR CO-SIGNED via git-attestation (loop-drafted; implemented + pushed `fc58a7b9`).

CO-SIGN NOTE (honest crypto status): decision notes are never loop-signed, and this vault has no
separate operator-key ceremony — like every prior decision, the manifest stays `signed:false /
pending:operator`. The operator's co-signature is expressed by git-attestation: the operator-authorized
commits under the single-committer's wallet (this ceremony fired via /goal) are the attestation. The
manifest's `pending:operator` is therefore the honest state (no forged architect signature).

WHAT IS DECIDED:
1. **D-CERT-7 = YES.** `verifier_independence` is an explicit, declarative field on the proof (was
   implicit in `population_certified=False`), so a consumer reading only `cert_scope` cannot launder
   `developer_self` into third-party/independent trust.
2. **Semantics:** `None` = no cert scope applies (advisory, N/A); `False` = self-certified
   (developer_self: verifier == subject; MUST NOT be laundered); `True` = an independent verifier
   (population/tournament). Derived structurally inside `fuse()` from `cert_scope` — a parameter could
   be set by a caller, a derivation cannot lie about the scope.
3. **`True` is unreachable by construction today** — no code path sets it. It becomes reachable only
   when a genuinely independent verification path exists; it is the slot that path fills, NOT dead code.
   A consumer gating on independent verification passes ONLY on `True` (None and False fail closed).
4. **SDK:** `VAPIPresenceProof` carries the field + a first-class `verifier_is_independent()` helper, so
   external consumers check independence directly instead of inferring it from `population_certified`.

HONESTY RAILS: additive + null-safe (absent -> None, never coerced); no verdict-semantics change;
`population_certified` / `cert_scope` / `certified` untouched. Basis: cycle-57 Confirm-3.
