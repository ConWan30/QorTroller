# VHP Renewal Cadence (iPACT-DePIN) — v1 Scope (DRAFT)

**Status:** DRAFT scope (post-update: byte formats + challenge source locked; device_id FLIP →
`device_id_to_bytes32` CONSENT convention) · Phase B item ③ ·
**no code, no FROZEN-v1 tag pinned**. Pre-implementation V-check **APPROVED**
(`vapi_validate_proposal`, 0 violations; the lone warning is the keyword-triggered TGE
boilerplate, not about this design, 2026-05-23). HEAD `94d36357` (feature) / `b24fcbdb` (main).

**Purpose.** Formalize QorTroller's **VHP renewal cadence** as a gamer-sovereign,
replay-resistant, **re-attestation-bound** commitment primitive — the iPACT-DePIN instance
(IIP-64 §4.8.5) — and **close the dormant-blind gap**: today `VHPRenewalAgent` auto-renews any
VHP within a 7-day TTL window with **no requirement that the device still be present**, so a
dormant device's credential would be auto-renewed forever (the opposite of a defensible
dormant-wallet answer). This is the **load-bearing motivation**; §4.8.5 alignment is a bonus,
not the driver.

Pre-③ investigation: `wiki/methodology/vhp_renewal_cadence_ipact_pre3_investigation.md`.

---

## 0. Honesty rails (read first)
- **DRAFT scope.** Not frozen; subject to revision before any freeze ceremony.
- **No FROZEN-v1 tag pinned this step.** `QORTROLLER-IPACT-RENEWAL-v1` is **RESERVED** (scope-doc
  only); it freezes only when this scope doc + code + vectors land — a **separate** ceremony.
- **③ landing does NOT by itself close the dormant-blind vulnerability.** The re-attestation
  binding ships **DEFAULT-OFF** (additive, no behavior change). Until the operator flips
  enforcement on, `VHPRenewalAgent` still renews on TTL-proximity alone. **The dormant-blind
  vulnerability remains OPEN until that flip** (D-③-3) — which becomes a tracked subsequent
  decision after an observation period. This doc must never be read as "③ closed the gap." The
  flip-on decision is a **tracked subsequent governance event** (backlog item) and requires its
  own observation period + V-check + commit lineage — analogous to other QorTroller enforcement
  flips. ③ landing **creates the option** to close the vulnerability; the **act of closing it is a
  separate operator decision**.
- **IIP-64 §4.8.5 is a single under-specified paragraph in a DRAFT PR** (`iotexproject/iips#72`,
  head `2c9b098`). Its refresh semantics (refreshable vs one-time) are the **open question
  QorTroller raised on PR #72, still awaiting @cryptoxfan's reply.** ③ is designed
  **regime-agnostic** (§7) — the on-wire artifact is identical under either resolution.
- **Novelty claim is conditional** (§8). Absence of evidence in the internal corpus is not
  evidence of absence in the broader prior-art space.
- **Touches no FROZEN-v1 primitive** / 228-byte PoAC wire format / `SHA-256(raw[:164])` chain
  hash / ZK params / deployed contract / TGE gate. `renew_vhp` stays kill-switch-gated.
  **Gamer-sovereignty preserved** — the gamer's device produces the re-attest proof; the bridge
  observes, never manufactures it (cf. the CONSENT primitive invariant).

## 1. Adoption & binding language
QorTroller adopts a **chained SHA-256 commitment** as the renewal-cadence primitive, in the
PATTERN-017 family shape (born-PQ-safe per IIP-64 §2.4). Each VHP renewal emits one commitment
that **links to the prior renewal's commitment** (`prev_commitment`) and **binds a fresh device
re-attestation proof** (`reattest_proof`). The chain gives **monotonic, replay-resistant
timestamp semantics** — a direct answer to §4.8.5 open-question (a).
- **Renewal validity (when enforcement ON)** requires: (i) a well-formed commitment chained to
  the device's prior renewal commitment, AND (ii) a valid fresh `reattest_proof` within the
  epoch. A renewal without a valid re-attestation is **rejected** — this is what closes the
  dormant-blind gap.
- **Composition, not supersession** (D-③-4): ③ is the **gamer-sovereign cadence/commitment**
  primitive for **VHP TTL renewal**. The Phase 185/186 HMAC layer
  (`ReEnrollmentAttestationAgent` / `AttestationBoundRenewalAgent`) remains the **optional
  operator-secret enforcement gate** for **biometric re-enrollment** specifically. Different
  purpose (gamer-sovereign vs operator-secret; VHP-TTL vs biometric-reenroll), different keys,
  both retained.

## 2. Commitment construction (byte formats LOCKED — ③-CONSTRUCTION / ③-BOOTSTRAP / ③-RE-ATTEST-PROOF)
```
commitment = SHA-256(
    b"QORTROLLER-IPACT-RENEWAL-v1"          # 27-byte domain tag (width asserted at import)
    || device_id_32B                        # 32 bytes = device_id_to_bytes32(device_id) (CONSENT convention)
    || uint64_be(token_id)                  # 8 bytes, big-endian
    || prev_commitment                      # raw 32 bytes (SHA-256 output; see genesis note)
    || uint64_be(epoch_index)               # 8 bytes, big-endian
    || reattest_proof                       # raw 32 bytes (SHA-256-class digest; see below)
    || uint64_be(ts_ns)                     # 8 bytes, big-endian, nanoseconds since Unix epoch
)
```
**Field byte formats (all six LOCKED):**
1. **`device_id`** → `device_id_32B = device_id_to_bytes32(device_id)` — **raw 32 bytes, no
   length prefix**, using the **exact CONSENT-family convention** (`consent_categories.device_id_to_bytes32`,
   verified 2026-05-23). That function normalizes per these branches: **(i)** 32 raw bytes →
   passthrough; **(ii)** 64-char hex string (with or without `0x`) → `bytes.fromhex` (the
   canonical on-chain `bytes32` form, e.g. keccak256(pubkey)); **(iii)** any other string →
   `SHA-256(device_id.encode("utf-8"))` fallback (e.g. `Sony_DualShock_Edge_CFI-ZCP1`). ③
   replicates this construction **byte-for-byte** — a test asserts byte-identity against the live
   `consent_categories.device_id_to_bytes32` across all three branches, so ③ uses the **same**
   construction, not a parallel one. **No new charset/length constraint is introduced** (the
   hashed/normalized 32-byte form is charset- and normalization-agnostic), eliminating the
   new-property and Unicode-normalization concerns entirely. This makes ③'s device_id handling
   **structurally identical to the CONSENT family** (see §7 family-consistency row).
2. **`token_id`** — `uint64` big-endian.
3. **`prev_commitment`** — raw **32 bytes** (SHA-256 output; never hex in the preimage).
4. **`epoch_index`** — `uint64` big-endian (0 at issuance/genesis, +1 per renewal).
5. **`reattest_proof`** — fixed **32 bytes** (SHA-256-class digest; computed per ③-RE-ATTEST-PROOF below).
6. **`ts_ns`** — `uint64` big-endian, nanoseconds since Unix epoch. **Strictly monotonically
   increasing per device** (mirrors INV-GIC-002: `time.time_ns()` + explicit `prev_ts` guard
   `if ts_ns <= prev_ts: ts_ns = prev_ts + 1`; never float-seconds, never `monotonic_ns`).

**Genesis (③-BOOTSTRAP) — first renewal's `prev_commitment`:**
```
prev_commitment_on_first_renewal = SHA-256(
    b"QORTROLLER-IPACT-RENEWAL-GENESIS-v1" || device_id_32B || uint64_be(token_id)
)
```
*(`device_id_32B = device_id_to_bytes32(device_id)` — the same 32-byte encoding as the main
preimage; token_id as uint64-BE.)*
**Determinism note:** the genesis commitment is **deterministic** given `(device_id, token_id)`;
it is a **chain anchor, not a secret**. Any party with `(device_id, token_id)` can compute
`device_id_32B = device_id_to_bytes32(device_id)` and then the genesis. **This is a feature, not a
vulnerability** — it lets any verifier re-derive the chain root without trusting the bridge.

**`reattest_proof` (32 bytes) — ③-RE-ATTEST-PROOF computation:**
```
reattest_proof_32B = SHA-256( challenge_bytes || composite_sig_bytes )
```
- **`challenge_bytes`** = the **bridge-issued random nonce** for this renewal, encoded as
  `uint8(len(nonce)) || nonce` (1-byte length prefix + raw nonce bytes; nonce is **32 bytes** of
  CSPRNG output in v1, so the prefix byte = `0x20`).
- **`composite_sig_bytes`** = `uint32_be(len(sig)) || sig`, where `sig` is the composite-signature
  blob the device produces over `challenge_bytes` via `l9_presence/composite_sig.sign(keypair, ctx,
  challenge)` — i.e. the output of `l9_presence/composite_sig.encode_composite(label, ec_sig,
  pq_sig)` from ① (verified function name 2026-05-23), byte-pinned by ①'s test vectors (see
  `l9_presence/tests/test_composite_sig.py`). 4-byte BE length prefix because composite sigs reach
  ~8 KB (SLH-DSA-128s tier). This makes the cross-doc dependency on ① explicit.
- **Wire-level the slot is proof-type-agnostic** (any 32-byte digest); the **default validator**
  (when enforcement ON) is **(B) composite-sig over a fresh challenge**, making ③ the first real
  consumer of ① (feeds the ① freeze ceremony, backlog #6). The validator is **pluggable**.
- **Challenge source = bridge-issued random nonce per renewal** (strongest freshness). Bridge
  generates a fresh CSPRNG nonce → device signs it via composite-sig → bridge verifies.
  **Gamer-sovereign:** the bridge issues the challenge but the **device's signature** is the
  sovereign act; the bridge never manufactures the proof.
  - *Rejected — challenge option B (chain-derived nonce):* a chain reorg would invalidate
    in-flight challenges, and the nonce is **predictable within the block-gossip window**
    (weaker freshness). Rejected.
  - *Rejected — challenge option C (commitment-chain-derived nonce):* derivable by **anyone
    holding the prior commitment** (which is public per the genesis-determinism property), so it
    provides **no freshness** against a replay actor who has observed the chain. Rejected.

## 3. Cadence parameter (named + frozen) — Decision D-③-2
Promote the existing **hardcoded** `90 * 86_400` TTL extension in
`bridge/vapi_bridge/vhp_renewal_agent.py` to a **named, frozen** module constant:
```
IPACT_RENEWAL_EPOCH_DAYS = 90    # v1; single-tier; no value change from the prior hardcode
```
- **No behavior change to the number** — the renewal still extends TTL by 90 days; only the
  silent literal becomes an auditable named parameter.
- **Single tier** in v1. Per-device-tier epochs (e.g. shorter for high-stakes device-identity)
  **deferred to v2** if the observation period warrants.
- The epoch parameter gets its own PV-CI invariant **in the freeze ceremony** (§6), not now.
- `epoch_index` (§2) = the integer renewal sequence number for the device (0 at issuance, +1 per
  renewal), giving each commitment an unambiguous position independent of wall-clock.

## 4. Implementation reference
- **Extend:** `bridge/vapi_bridge/vhp_renewal_agent.py` — replace the `90 * 86_400` literal with
  `IPACT_RENEWAL_EPOCH_DAYS * 86_400`; on each renewal, compute + persist the commitment; when
  enforcement ON, gate renewal on a valid `reattest_proof`.
- **Add:** a standalone pure-Python commitment module (no bridge imports, independently
  verifiable — mirrors `grind_chain.py` / `composite_sig.py`) computing + chaining the
  commitment and verifying a chain.
- **Add:** a `store` table for renewal commitments (chain head per device; `UNIQUE(device_id,
  epoch_index)` anti-replay; monotonic `ts_ns` guard) + getters mirroring the GIC chain helpers.
- **Config:** `ipact_renewal_enforcement_enabled: bool = False` (D-③-3 default-OFF) +
  `IPACT_RENEWAL_EPOCH_DAYS` exposure.
- **No new contract.** On-chain anchoring (if ever) reuses an existing registry, operator-fired,
  not auto — same posture as CORPUS-SNAPSHOT.

## 5. Test-vector plan (code — NEXT step, not this doc)
- (a) **Byte-pinned commitment KATs** — deterministic `commitment` hex for fixed inputs (the
  novel, byte-pinnable artifact); domain-tag width asserted.
- (b) **Chain validity** — genesis (bootstrap) + N-link chain recomputes byte-identically;
  tamper in any field breaks the chain.
- (c) **Replay rejection** — duplicate `epoch_index` rejected; regressing/duplicate `ts_ns`
  bumped per the monotonicity guard; stale `reattest_proof` reuse rejected.
- (d) **Dormant-blind close (enforcement ON)** — renewal with a valid fresh `reattest_proof`
  succeeds; renewal **without** one is **rejected** (the security property).
- (e) **Default-OFF behavior** — with `ipact_renewal_enforcement_enabled=False`, renewal path is
  **byte-identical to today's** (no re-attest required; pure additive commitment logging).
- (f) **Regime-agnostic artifact identity** — the commitment bytes are identical whether ③ is
  framed as the §4.8.5 refresh cadence or as the re-attestation layer above a one-time iPACT
  (proves proposal item 4: no rework on @cryptoxfan's reply).
- (g) **Challenge-issuance correctness** — the bridge issues a **fresh** random nonce per renewal
  (two consecutive renewals draw distinct nonces); a **stale/replayed** challenge is **rejected**
  (a `reattest_proof` computed against a previously-issued nonce does not validate for a new
  renewal); the `reattest_proof_32B = SHA-256(challenge_bytes || composite_sig_bytes)` computation
  is byte-pinned for a fixed (nonce, composite-sig) pair.

## 6. Tag reservation status
`QORTROLLER-IPACT-RENEWAL-v1` is **RESERVED (scope-doc only)** — **not** in
`_PATTERN_017_FROZEN_TAGS` and **not** in the PV-CI allowlist (the byte literal does not exist in
production yet). The **freeze ceremony** (add tag to `_PATTERN_017_FROZEN_TAGS`; add a PV-CI
invariant for the commitment byte layout AND for `IPACT_RENEWAL_EPOCH_DAYS=90`; bump
`frozen_v1_commitment_family_count` 12→13 + `INV-MYTHOS-FAMILIES-001` description; regen
allowlist via `vapi_invariant_gate.py --generate --confirm-governance`) is a **separate later
step**, fired when the operator chooses to lock ③ as canonical.

## 7. Alignment checklist
| Check | Reference | Status |
|---|---|---|
| Chained SHA-256 commitment, born-PQ-safe | IIP-64 §2.4 + PATTERN-017 canon | ALIGNED |
| **iPACT-DePIN — §4.8.5 REFRESHABLE branch** | IIP-64 §4.8.5 (PR #72, DRAFT) | REGIME-AGNOSTIC: ③ chain *is* the refresh cadence; offer as §4.8.5 contribution |
| **iPACT-DePIN — §4.8.5 ONE-TIME branch** | IIP-64 §4.8.5 (PR #72, DRAFT) | REGIME-AGNOSTIC: ③ chain sits as the re-attestation layer *above* the one-time iPACT |
| Replay / timestamp semantics | §4.8.5 open-Q(a) | ANSWERED (prev_commitment link + monotonic ts_ns) |
| Gamer-sovereignty (device produces proof, bridge observes) | INV-CONSENT-003 family / sovereignty invariant | ALIGNED |
| Composition with Phase 185/186 HMAC | D-③-4 | ALIGNED (compose, not supersede) |
| Construction consistent with other PATTERN-017 families | PATTERN-017 family canon | ALIGNED (domain-tagged SHA-256, chained like GIC/WEC; device_id_to_bytes32 per CONSENT convention for cross-family consistency) |
| Monotonic ts_ns guard | INV-GIC-002 precedent | ALIGNED |
| Kill-switch coverage on any live renewal | feedback_kill_switch_coverage | ALIGNED (renew_vhp already gated) |

**Caveat:** IIP-64 is a DRAFT PR (head `2c9b098`); §4.8.5 may change on merge / on @cryptoxfan's
reply — re-validate then. ③'s regime-agnostic property is the structural insulation.

### 7.1 Decision D-③-1 — `QORTROLLER-IPACT-RENEWAL-v1` is a 13th commitment FAMILY (Reading A)
**Chosen: Reading A — a 13th PATTERN-017 commitment family** (global chain semantics:
`prev_commitment` links renewals as a per-device chain; the commitment commits to a *state event*
— a renewal with provenance — which is the R3 **family** criterion, structurally identical to
AGENT-COMMIT / FRR / GIC). Chain construction (`prev_commitment`) is **part of what is committed
to**, not a method applied externally.

**Rejected alternative — Reading B (capability tag applied to existing families; chain is
per-family-instance).** Defensible, but rejected because: (1) the commitment commits to a state
event (the family criterion, not a hash capability); (2) chain semantics are intrinsic to the
commitment, not external; (3) Reading B would re-blur the family-vs-capability distinction the R3
criterion exists to clarify — capability tags should not carry chain-construction-and-verification
logic. Recorded here for the audit trail.

**Family count 12 → 13.** Ripples (same cascade shape as the 11→12 VAPI-O3-SUPERSEDE move):
`frozen_v1_commitment_family_count` canonical fact + `INV-MYTHOS-FAMILIES-001` description, applied
**in the freeze ceremony**, not now. The state-of-protocol §4.1 + WP v6 §4.2 enumerations are
already amber from the 11→12 cascade; 12→13 does not materially worsen amber. The tracked **v6.1
reconciliation** ([[frozen-governance-gaps-2026-05-22]]) should now cover **both** the 11→12
(VAPI-O3-SUPERSEDE-v1) and 12→13 (QORTROLLER-IPACT-RENEWAL-v1) additions — restating the R3
family-vs-capability distinction with both properly described and the chain semantics noted.

## 8. Novelty claim (conditional)
**Claim:** no *known* public production deployment of a **chained SHA-256 commitment for a
DePIN credential renewal cadence with gamer-sovereign re-attestation binding** (each ingredient
— soulbound-token TTL, commitment chains, re-attestation — has prior art; the *binding pattern*
for renewal cadence does not, to our knowledge). **Conditional:** rests on the internal corpus +
the IIP-64/PoEP assessment; absence of evidence is not evidence of absence; a USPTO+EPO search
should precede any external/IP assertion. To be checked against the vapi-knowledge what-if
corpus before any external claim.

---

## Scope-doc-time decisions — RESOLVED (2026-05-23)
All three (+ a fourth surfaced) are resolved and locked in §2 above. Recorded here for the index:
- **③-CONSTRUCTION** → six byte formats locked (§2): device_id `device_id_to_bytes32 → raw 32 B`
  (CONSENT convention; **FLIP** from the earlier length-prefixed-UTF-8 draft — see commit message);
  token_id `uint64-BE`; prev_commitment `raw 32 B`; epoch_index `uint64-BE`; reattest_proof
  `fixed 32 B`; ts_ns `uint64-BE`.
- **③-BOOTSTRAP** → credential-bound deterministic genesis (§2), with the
  determinism-is-a-feature note.
- **③-RE-ATTEST-PROOF** → wire-level opaque 32-byte digest; default validator (B) composite-sig
  over a fresh challenge; `reattest_proof_32B = SHA-256(challenge_bytes || composite_sig_bytes)`
  (§2).
- **③-CHALLENGE-SOURCE** (new fourth) → **bridge-issued random nonce per renewal**; chain-derived
  (B) and commitment-chain-derived (C) alternatives **rejected** with reasoning (§2).

---

## Dependencies & relationships
- **Consumes (when enforcement ON):** a re-attestation proof — recommended binding to **① composite-sig** (③-RE-ATTEST-PROOF option B), making ③ the first integration consumer of ① → feeds the **① freeze ceremony** (backlog #6).
- **Sibling:** ② P4b (commitment registration) follows ③; P4b registers commitments whose lifetime ③ manages.
- **Cross-refs:** `bridge/vapi_bridge/vhp_renewal_agent.py`, `…/reenrollment_attestation_agent.py`, `…/attestation_bound_renewal_agent.py`, `bridge/vapi_bridge/grind_chain.py` (chain pattern), `l9_presence/composite_sig.py` (① sibling). Memory: [[composite-sig-v1-shipped]], [[iip64-pr72-engagement]], [[frozen-governance-gaps-2026-05-22]].

## Provenance
Pre-implementation V-check `vapi_validate_proposal` → APPROVED (0 violations; lone warning =
keyword-triggered TGE boilerplate, not about this design), 2026-05-23, HEAD `94d36357`. This is a
**DRAFT scope held for operator review** before code + vectors. Protocol: V-check (done) → hold
→ scope doc (this file) → **hold** → code + vectors → P-check → hold → atomic commit. The freeze
ceremony for `QORTROLLER-IPACT-RENEWAL-v1` + the `IPACT_RENEWAL_EPOCH_DAYS` PV-CI invariant is a
separate later step.
