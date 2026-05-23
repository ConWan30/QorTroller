# QorTroller ↔ IIP-64 (PR #72) — Engagement Record

**Status:** IIP-64 is **public** — `iotexproject/iips#72`, *"Post-Quantum Cryptographic
Migration for IoTeX,"* author Xinxin Fan (@cryptoxfan), **Status: Draft**, created
2026-05-14, +701 lines. This resolves the *"IIP-64 not independently verifiable"* caveat in
the PQ/novelty assessment (`IIP-64 and QorTroller PoEP_ Post-Quantum Verification and Novelty
Assessment.pdf`); its **Stage 0 → Stage 1 trigger** ("if a public PR surfaces, proceed to
engage") is now met.

**Engagement comment:** prepared 2026-05-23. **Posted by the operator** under their own GitHub
identity — NOT auto-posted (a public comment on a third-party governance PR is an
operator-identity action). The verbatim text below is the single source of truth for what was
submitted.

---

## Why QorTroller engages (the head-start thesis)

QorTroller is a deployed downstream consumer of exactly the precompile + registry IIP-64
proposes. Its commitment fabric is SHA-256 (born-PQ-safe per **§2.4**); its credential primitive
(PoEP) is a reference instance of **§4.6** (DePIN device identity) + **§4.8.5** (iPACT-DePIN);
its ZK path aligns to **§4.7** (SP1, STARK-native, avoiding the Groth16 recursion step). Engaging
now positions QorTroller as a **design partner on IIP-64's Phase 0 deliverable:** *"Publish DePIN
PQ Device Identity Standard for new device provisioning."* It is also direct evidence for the
Halo DePIN-Incubator grant (reciprocity + design-partner framing).

The migration surface is narrow and known: ~most of the protocol is already PQ-safe (hash
commitments); the three deltas are PoAC signature → ML-DSA/SLH-DSA checkpoints, ZK Groth16 → SP1
STARK, and account key → PQ Key Registry.

---

## The submitted comment (verbatim)

> Reviewing this as a DePIN protocol building on IoTeX that expects to be a direct downstream consumer of the precompile and PQ Key Registry proposed here. QorTroller — a presence- and device-auth credential layer for competitive gaming, controller-bound — is architected on a SHA-256 commitment family for its credential primitive, the same hash-based construction §2.4 identifies as providing ≥128-bit post-quantum preimage security. Credential signing is designed as hybrid ECDSA + ML-DSA, tiered following §4.1 and §4.6 (ML-DSA-44 for user-equivalent paths, SLH-DSA-128s for device-identity), with a Groth16 → SP1/STARK ZK migration on our roadmap. Our broader protocol — 49 contracts plus a SHA-256 grind-integrity chain — is already live on IoTeX testnet. The structural fit with §4.6 (DePIN device-identity migration) and §4.8.5 (iPACT-DePIN), grounded in the §3.11 IoTeX-specific insights, is striking, and the architecture looks like a natural deployment target for Phase 0–1 of this roadmap.
>
> Two questions where clarification would meaningfully help downstream protocols plan against the spec:
>
> **Application-layer credential carve-out.** §4.6 addresses DePIN device-identity migration but frames device keys at the account-equivalent layer. For protocols that issue device-bound *attestation credentials* — verified hardware proofs, embodied-presence credentials, interactive challenge-response attestations — at the application layer, separately from account-level transaction signing: would the spec consider explicitly acknowledging that the PQ precompile (0x0B) and PQ Key Registry can be consumed for application-layer credential issuance independently of account-level enforcement timing? Concretely, a DePIN credential layer could be PQ-deployable on Phase 1's timeline (2027 Q3) without waiting for Phase 2's hybrid enforcement on user accounts.
>
> **iPACT-DePIN refinement.** §4.8.5 is the cleanest fit for our use case but is sketched in a single paragraph relative to §4.8.1–4.8.4. It notes manufacturers should generate iPACTs "during firmware updates or during provisioning" — two clarifications would help downstream protocols build against it: (a) does that imply a refreshable cadence rather than one-time, and what are the replay/timestamp semantics across refreshes; and (b) how is iPACT-DePIN intended to interact with verified-hardware-proof renewal cadences for devices that periodically re-attest? We've been working through exactly this renewal model and would value coordinating on it.
>
> Two small editorial notes on §4.1/§4.2: (1) the signature selection in §4.1 is nuanced and well-justified by the verify-cost analysis — ML-DSA-44 for user transactions, ML-DSA-65 reserved for consensus/admin keys; to the extent the surrounding discussion gets compressed to "ML-DSA-65 as primary," it may be worth keeping the per-tier framing front-and-centre so reviewers pressure-test the actual decision. (2) Minor inconsistency: §4.2's precompile input comment maps SLH-DSA-128s/128f to algorithm_id `0x04`/`0x05`, while the §4.1 identifier table assigns them `0x10`/`0x11` — worth reconciling so implementers key off one canonical table.
>
> Happy to engage further on any of these, and to share our device-credential and renewal design when it's useful.

---

## The two open questions + what each resolution unlocks

1. **Application-layer credential carve-out** — can the 0x0B precompile + PQ Key Registry be
   consumed for app-layer *attestation credentials* independently of account-enforcement timing?
   - **If acknowledged:** PoEP P4b/P4c can ship on **Phase 1's timeline (2027 Q3)** — on-chain
     commitment registration + 0x0B-targeted hybrid signing — without waiting for Phase 2
     account enforcement.
   - **If not / deferred:** keep the PoEP commitment off-chain (already SHA-256 PQ-safe) until
     Phase 2; re-raise the carve-out in a spec revision.

2. **iPACT-DePIN refresh semantics** — refreshable cadence vs one-time; interaction with
   verified-hardware-proof renewal.
   - **If refreshable:** bind VHP renewal cadence = iPACT-DePIN cadence; offer a §4.8.5 spec
     contribution.
   - **If one-time:** design VHP renewal as a layer above iPACT; surface the periodic
     re-attestation gap.

---

## Response-handling phase note (when @cryptoxfan replies)

- **Editorial catches** (§4.2 `0x04`/`0x05` vs §4.1 `0x10`/`0x11`; ML-DSA tiering framing) —
  low-controversy, likely accepted; thank, confirm, move on. Rapport with low cost.
- **If he invites collaboration / "share your design":** this is the prize — respond with
  `l9_presence/POEP_SCOPE.md` + the renewal model and pursue **reference-implementation status
  for the Phase 0 DePIN PQ Device Identity Standard.**
- **Honesty guardrails for any follow-up:** PoEP is a **v0 candidate, not activated**
  (`poep_enabled=False`, L6B N≥50 unmet); cite IIP-64 as **Draft**; *"no known production prior
  art"* (absence-of-evidence) on adaptive-trigger device-auth; the credential layer is **not**
  account custody.
- **Grant tie-in:** a constructive thread is direct evidence for the Halo DePIN-Incubator
  application; cross-reference the grant deck (slides 09–12) + reference §11, which already cite
  IIP-64 #72.

---

## Cross-references
- Assessment: `IIP-64 and QorTroller PoEP_ Post-Quantum Verification and Novelty Assessment.pdf`
- PoEP scope: `l9_presence/POEP_SCOPE.md` · L9 arc: `l9_presence/README.md`
- Frontend (now IIP-64-aligned): `frontend/public/grant-brief.html` (slides 09–12),
  `frontend/public/qortroller-reference.html` (§11)
- IIP-64 sections cited: §2.4, §3.11, §4.1, §4.2, §4.6, §4.7, §4.8.5
