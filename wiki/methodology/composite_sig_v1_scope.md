# Composite Signature Wire-Format — v1 Scope (DRAFT)

**Status:** DRAFT scope · Phase B item ① · **no code, no FROZEN-v1 tag pinned**
(reserved only, ceremony `ffa887d6`). Pre-implementation V-check **APPROVED**
(`vapi_validate_proposal`, 0 violations / 0 warnings, 2026-05-23). HEAD `11761759`.

**Purpose.** Define the wire format for QorTroller's composite (classical + post-quantum)
**credential** signatures — the dependency root for **P4b** (PoEP commitment registration)
and **PoEP P4c** (hybrid signing). This is an **application-layer device-bound attestation
credential**, distinct from account-level transaction signing (the carve-out raised on
IIP-64 PR #72).

---

## 0. Honesty rails (read first)
- **DRAFT scope.** Not frozen; subject to revision before any freeze ceremony.
- **No FROZEN-v1 tag pinned this step.** The composite-sig tag is **RESERVED** (governance
  log) per ceremony `ffa887d6`; it freezes only when this scope doc + `composite_sig.py` +
  test vectors all land — a **separate** ceremony. Reservation ≠ freeze.
- **IIP-64 references are to PR #72 head** (`iotexproject/iips#72`, branch `xinxin-crypto:iip-64`,
  head `2c9b098`) — a **DRAFT proposal, NOT a merged/ratified IIP**. We design *for* it, we do
  not hard-couple to it. Section numbers may shift if the PR revs; re-validate on merge.
- **Novelty claim is conditional** (see §8). Absence of evidence in the internal corpus is
  **not** evidence of absence in the broader prior-art space.
- **Touches no FROZEN-v1 primitive** / 228-byte PoAC wire format / `SHA-256(raw[:164])` chain
  hash / ZK params / state flags. PoEP remains a **v0 candidate, default-OFF**
  (`poep_enabled=false`); the L6B N≥50 activation gate is unaffected.

## 1. Adoption
QorTroller adopts **IETF `draft-ietf-lamps-pq-composite-sigs-16`** (2026-04-08;
Ounsworth / Gray / Pala / Klaussner / Fluhrer) as the wire-format reference for composite
credential signing. The **ML-DSA + ECDSA-P256** composites are **IETF-registered** (draft-16);
the **SLH-DSA-128s + ECDSA-P256** device-identity composite is a **QorTroller-custom**
construction that reuses draft-16's semantics + message-binding verbatim (Decision C3, §3.1).
- **AND-composition ONLY.** Verification requires **both** the classical and the PQ
  component to validate.
- **Reject** any presented composite where either half is missing or invalid. **No
  OR-composition. No ECDSA-fallback-on-PQ-failure.** (Downgrade resistance: a CRQC must not
  be able to strip the PQ half and present an ECDSA-only signature that still verifies.)

Both component signatures are computed over the identical
`M' = Prefix ‖ Label ‖ len(ctx) ‖ ctx ‖ PH(M)` per IETF draft-16 §2.2 / §3.2; ML-DSA
additionally consumes `mldsa_ctx = Label`. Verification of the composite requires both
component verifications to succeed independently against `M'`. This binding pattern — both
components over one domain-separated message — is what makes the AND-composition
cryptographically meaningful rather than merely a concatenation.

## 2. Message-binding construction & domain separation
Message binding follows **IETF `draft-ietf-lamps-pq-composite-sigs-16` §2.2 / §3.2**:

```
M' = Prefix ‖ Label ‖ len(ctx) ‖ ctx ‖ PH(M)
```

where:
- **Prefix** = `"CompositeAlgorithmSignatures2025"` — **32 ASCII bytes**, hex
  `436F6D706F73697465416C676F726974686D5369676E61747572657332303235`.
- **Label** = the registered (or QorTroller-allocated) per-algorithm identifier (see §3).
- **len(ctx)** = single unsigned byte, default `0`; **ctx** ≤ 255 bytes.
- **PH(M)** = the composite's specified hash of the message.

Both component signatures (classical ECDSA-P256 and PQ ML-DSA / SLH-DSA) are computed over the
**identical `M'`**. ML-DSA additionally consumes `mldsa_ctx = Label`. Verification of the
composite requires **both** component verifications to succeed independently against `M'`.

**PATTERN-017 binding via `ctx` (not a label suffix).** QorTroller's domain separation across
PATTERN-017 commitment families is carried in **`ctx`** — not by mangling the Label. Specifically:
`ctx` = the PATTERN-017 family domain tag (e.g. `b"QORTROLLER-POEP-v0"`); **`M`** = the 32-byte
commitment value; **`PH(M)`** = the hash of the commitment per the composite's hash spec. This
uses the IETF draft's purpose-built domain-separation mechanism and is **stronger binding** than
a label-suffix would have been.

## 3. Algorithm tiering (per IIP-64 §4.1 / §4.6 — PR #72 head)
| Tier | Composite | Label | Hash (PH) | OID | IETF status |
|---|---|---|---|---|---|
| **Credential-signing** (PoEP P4c, primary) | ML-DSA-65 + ECDSA-P256 | `COMPSIG-MLDSA65-ECDSA-P256-SHA512` | SHA-512 | 1.3.6.1.5.5.7.6.45 | IETF-registered (draft-16) |
| **Device-identity — user tier** | ML-DSA-44 + ECDSA-P256 | `COMPSIG-MLDSA44-ECDSA-P256-SHA256` | SHA-256 | 1.3.6.1.5.5.7.6.40 | IETF-registered (draft-16) |
| **Device-identity — long-lived (10–20 yr DePIN)** | SLH-DSA-128s + ECDSA-P256 | `COMPSIG-SLHDSA128S-ECDSA-P256-SHA256-QORTROLLER` | SHA-256 | QorTroller arc — TBD (deferred; Decision OID-2b) | **QorTroller-custom; deliberate divergence; tracked for IETF LAMPS WG submission** |

ML-DSA-65 is the high-assurance credential tier per IIP-64 §4.1. ML-DSA-44 is the
user/lighter-weight tier per IIP-64 §4.1. SLH-DSA-128s + ECDSA-P256 is the **hash-based
crypto-diversity hedge** for long-lived device identities per IIP-64 §4.6 and the external PQ
assessment, executed as a QorTroller-custom composite that reuses draft-16's AND-composition
and message-binding construction with a QorTroller-defined Label.

**OID provenance.** The two ML-DSA OIDs are draft-16's registered literals from the
`1.3.6.1.5.5.7.6` arc (SMI Security for PKIX Algorithms; algorithm names in draft-16 §6,
registration in §8.1.2): `id-MLDSA65-ECDSA-P256-SHA512 = 1.3.6.1.5.5.7.6.45` and
`id-MLDSA44-ECDSA-P256-SHA256 = 1.3.6.1.5.5.7.6.40`. The SLH-DSA-128s composite has **no IETF
OID** (draft-16 registers no SLH-DSA composite); its OID is a **QorTroller-arc allocation, TBD
— deferred until an external-need trigger fires (Decision OID-2b)** (no QorTroller IANA Private
Enterprise Number arc `1.3.6.1.4.1.X` exists yet — verified absent from repo, governance docs,
and the public IANA PEN registry, 2026-05-23). **The OID is not load-bearing for ① itself:** `M'` binding and alg-id validation
key off the **Label**, not the OID — the OID becomes load-bearing only when the credential is
DER-encoded into a PKIX `AlgorithmIdentifier` or submitted to the IETF LAMPS WG. KATs are
therefore unaffected by the pending SLH-DSA OID; they regenerate only if the eventual PKIX
encoding test is added.

### 3.1 Decision C3 — device-identity tier = QorTroller-custom SLH-DSA-128s + ECDSA-P256 (option b)
The decision is not "IETF-standard vs not" — it is **where in the credential stack the
IETF-standard property needs to hold.** IETF composite signatures matter most for
**interoperability across unrelated systems.** The device-identity-tier composite is generated
by QorTroller controllers and validated by the QorTroller bridge/registry — **no third-party
validator is in the trust path** — so the interoperability argument for IETF-standard is weaker
at the device-identity tier than at the credential-signing tier.

Going lattice-only (option a, ML-DSA-44) would forfeit the crypto-diversity hedge that IIP-64
§4.6 and the external PQ assessment explicitly want for 10–20-year device identities: a single
Dilithium cryptanalytic surprise would compromise **both** the credential and device-identity
tiers simultaneously. Hash-based **SLH-DSA-128s** at the device-identity tier provides that
systemic-risk hedge.

Option (b) is therefore correct, executed with **maximum proximity to IETF draft-16**: reuse
draft-16 AND-composition semantics + the verbatim message-binding construction (§2) + the
verbatim 32-byte Prefix; diverge **only** in a QorTroller-defined Label
(`COMPSIG-SLHDSA128S-ECDSA-P256-SHA256-QORTROLLER`; any QorTroller OID is allocated from a
**QorTroller-owned arc, not the IETF range**), with `PH(M) = SHA-256` (natural pairing for the
128-bit level) and PATTERN-017 binding via `ctx` (same mechanism as the credential tier, §2).
**Tracked follow-on (not blocking ①):** a draft addition to the IETF LAMPS WG proposing
SLH-DSA-128s + ECDSA-P256 as a registered composite — converts "non-IETF" to "IETF-pending"
over time and strengthens the device-identity tier's audit posture.

### 3.2 Decision OID-2b — SLH-DSA-128s OID = defer IANA PEN application until external need triggers it (modified option i)
Step 2a (2026-05-23) found **no existing QorTroller IANA Private Enterprise Number arc**
(`1.3.6.1.4.1.X`) — absent from the repo, governance docs, and the public IANA PEN registry.
Decision: **defer the PEN application until an external need triggers it — not on a calendar.**

**Why defer (rather than file-now-parallel).** The IANA PEN is needed when QorTroller's composite
signatures begin interacting with **external systems** — an IETF LAMPS submission, a third-party
audit, a first integration partner, or PKIX-encoded credential exchange with a non-QorTroller
validator. **None of these external interactions are active or scheduled.** Filing the PEN now
creates a public commitment surface area (organizational name, structure) **ahead of when it is
needed**, with no compensating benefit while QorTroller remains sole-developer,
pre-external-engagement.

**Trigger conditions (tracked).** File the PEN when any of these fires: **(a)** the IETF LAMPS
submission (§3.1 tracked follow-on) becomes concrete with a fixed timeline; **(b)** a third-party
security audit is scheduled; **(c)** a first external integration partner needs PKIX-encoded
credentials; or **(d)** the operator identifies another trigger.

**Why the deferral is safe for ①.** The OID is **not load-bearing for ①** (load-bearing finding,
§3): `M'` binding and alg-id validation key off the **Label**, not the OID; the OID matters only
at PKIX-encoding or LAMPS-submission time — which are precisely the deferred external
interactions. So the deferral blocks neither `composite_sig.py` nor the core KATs.

**Option (iii) (provisional placeholder OID) remains rejected:** a placeholder embedded in
vectors or code creates technical-debt items that "clearly marked" provisions in practice fail to
protect against. The honest state is an explicit `TBD`, not a fake literal.

**Freeze-with-pending-literal canon (unchanged).** The architectural canon is that the OID lives
under a QorTroller-allocated PEN sub-arc; the literal value is a **registration detail** pinned
when a trigger condition fires — **without re-freeze**. The OID assignment is a **documented
registration event, not a canonical architectural change**: the freeze covers the construction
(AND-composition, message-binding, Label, hash pairing, `ctx` domain separation), and the OID
literal is registration metadata layered on top.

**Operator-side action (not Claude Code):** when a trigger condition fires, the operator files the
IANA PEN application per RFC 9371. This is outward-facing and operator-only; Claude Code cannot
file on the operator's behalf. On assignment, the SLH-DSA row's OID cell is a one-line edit
(`TBD` → literal) per the canon above.

## 4. Implementation reference
- **liboqs** (Open Quantum Safe) for ML-DSA / SLH-DSA — **software, OFF-CHAIN**; ECDSA-P256
  via existing crypto.
- **On-chain verify via the PQ precompile at `0x0B` is DEFERRED to IIP-64 Phase 1 / 2027 Q3.**
  The wire format is designed to be **precompile-compatible** (the composite encoding maps to
  the precompile's `[alg_id][pubkey][msg][sig]` input when it lands).
- If the IIP-64 precompile design diverges from this encoding (e.g., separate precompiles per
  algorithm rather than a generic dispatcher), the wire format will require an adapter layer.
  The wire format itself is precompile-agnostic; only the on-chain verification path depends on
  the eventual precompile interface.

## 5. Test-vector plan (`composite_sig.py` — NEXT step, not this doc)
- (a) **AND-composite sign + verify** (happy path) per pairing.
- (b) **Downgrade-rejection:** reject composite with a missing PQ half; reject missing ECDSA
  half; reject OR-fallback / ECDSA-only-on-PQ-fail attempts.
- (c) **Domain-separation:** reject a composite signed under a wrong/mismatched label
  (wrong PATTERN-017 tag or wrong commitment).
- (d) **Known-answer test vectors (KATs)** for: **ML-DSA-65 + ECDSA-P256 + SHA-512**
  (`COMPSIG-MLDSA65-ECDSA-P256-SHA512`), **ML-DSA-44 + ECDSA-P256 + SHA-256**
  (`COMPSIG-MLDSA44-ECDSA-P256-SHA256`), and **SLH-DSA-128s + ECDSA-P256 + SHA-256**
  (`COMPSIG-SLHDSA128S-ECDSA-P256-SHA256-QORTROLLER`, QorTroller-custom).
- (e) **Algorithm-identifier validation:** reject composites where the presented `alg_id`
  (Label) does not match the actual signature components (e.g., a signature claiming
  `COMPSIG-MLDSA65-ECDSA-P256-SHA512` but containing different bytes). Guards against
  confusion attacks at the algorithm-negotiation layer.

## 6. Tag reservation status
The composite-sig wire-format tag is **RESERVED (governance-log only)** in ceremony
`ffa887d6` — **not** pinned in the PV-CI allowlist (the byte literal does not exist yet). Its
**freeze ceremony** (add to `_PATTERN_017_FROZEN_TAGS` or `_KNOWN_CAPABILITY_TAGS` + PV-CI
invariant + allowlist regen) happens **only** when this scope doc + `composite_sig.py` + test
vectors all land.

## 7. V-check vs IETF draft + IIP-64 (alignment checklist)
| Check | Reference | Status |
|---|---|---|
| AND-composition, no downgrade | IETF draft (composite semantics) | ALIGNED |
| Message-binding `Prefix‖Label‖len(ctx)‖ctx‖PH(M)` | IETF draft §2.2/§3.2 | ALIGNED (locked verbatim from draft-16, see §2) |
| Tiering: ML-DSA-65 credential / ML-DSA-44 device-user | IIP-64 §4.1, §4.6 | ALIGNED |
| SLH-DSA-128s device long-lived tier | IETF draft-16 (registers no SLH-DSA composite) | **DIVERGENCE** (QorTroller-custom, deliberate — see Divergence + §3.1) |
| Precompile-compatible (`0x0B`) | IIP-64 §4.2 | DESIGN-FOR (deferred to Phase 1) |
| SHA-256 commitment binding unchanged | PATTERN-017 (FROZEN-v1) | ALIGNED (commitment untouched) |
| Construction consistent with other PATTERN-017 families (AGENT-COMMIT, FRR, …) | PATTERN-017 family canon | ALIGNED (commitment is domain-tagged SHA-256, matching the family pattern; composite-sig wraps the commitment, does not replace it) |

**Divergence (deliberate, documented).** The **SLH-DSA-128s + ECDSA-P256** composite is a
deliberate divergence from IETF draft-16, which registers **no** SLH-DSA composite. The
divergence is **bounded** — it reuses draft-16's AND-composition semantics, message-binding
construction, and 32-byte Prefix **verbatim**, diverging only in a QorTroller-defined Label
(`COMPSIG-SLHDSA128S-ECDSA-P256-SHA256-QORTROLLER`). **Justification:** IIP-64 §4.6 and the
external PQ assessment both recommend hash-based crypto for long-lived (10–20 yr) device
identities; lattice-only across both tiers forfeits the systemic-risk hedge (Decision C3, §3.1).
**Tracked:** prepare a draft addition to the IETF LAMPS WG proposing SLH-DSA-128s + ECDSA-P256
as a registered composite. **Caveat:** IIP-64 is a DRAFT PR (head `2c9b098`); section numbers
may shift on merge — re-validate then.

### 7.1 Implementation divergences (item ①, 2026-05-23) — all bounded + documented
Surfaced while implementing `l9_presence/composite_sig.py` against the chosen backends
(`quantcrypt` 1.0.1 ML-DSA; `slh-dsa` 0.2.2 SLH-DSA-SHA2-128s, FIPS-205 KAT-validated 42/42
NIST ACVP; `cryptography` ECDSA-P256):

1. **ML-DSA component — empty native ctx (forced backend-level divergence).** The ML-DSA component
   signs `M'` with empty native ctx because PQClean (via quantcrypt) does not expose the ctx
   parameter — this is a **forced backend-level divergence** from draft-16's `mldsa_ctx = Label`
   binding. The Label binding is preserved via `M'` (the load-bearing security property holds), but
   the belt-and-suspenders ctx layer is **unavailable for ML-DSA on this backend** (only OpenSSL
   exposes ML-DSA ctx).
2. **SLH-DSA component — `slhdsa_ctx = Label` (native binding restored; Decision SLHDSA-CTX → (ii)).**
   The SLH-DSA component signs `M'` with `slhdsa_ctx = Label`, **matching draft-16's design intent**
   for native PQ-component ctx binding. This **restores the belt-and-suspenders binding layer for the
   device-identity tier** (the longest-lived, highest-stakes credential in the stack) where the
   library exposes the capability. The architectural **asymmetry** between #1 and #2 is therefore
   **deliberate** — native binding restored wherever the backend allows — not uniform-by-default.
3. **Outer container = QorTroller v1 framing (bounded; adapter deferred).** The composite signature
   is serialized with a simple length-prefixed container (`version ‖ label_len ‖ label ‖ ec_len ‖
   ec_sig ‖ pq_len ‖ pq_sig`), **not** draft-16's ASN.1 `CompositeSignatureValue` SEQUENCE. The
   **component** signatures (ML-DSA/SLH-DSA over `M'`, ECDSA over `M'`) are draft-16-conformant; a
   draft-16 ASN.1 adapter is deferred alongside the `0x0B` precompile adapter (§4).

## 8. Novelty claim (conditional)
**Claim:** no *known* public production deployment of an **app-layer device-bound composite
ECDSA + ML-DSA / SLH-DSA over a domain-tagged SHA-256 commitment**.
- **Primary support:** the external PQ/novelty assessment (`IIP-64 and QorTroller PoEP_…
  Novelty Assessment.pdf`) — states no public production prior art for an ECDSA+ML-DSA
  composite over a SHA-256 commitment (each individual primitive has prior art; the *binding
  pattern* does not).
- **Secondary support:** query of the freshly-loaded vapi-knowledge what-if corpus (internal)
  — no matching prior art.
- **Conditional:** the claim rests on these two bases. **Absence of evidence in the corpus is
  not evidence of absence** in the broader prior-art space. A USPTO + EPO patent search
  (tracked, grant item 05) should precede any external/IP assertion.

---

## Dependencies unblocked
**P4b** (PoEP commitment registration) and **PoEP P4c** (hybrid signing) both consume this
wire format.

## Provenance
Pre-implementation V-check `vapi_validate_proposal` → APPROVED (0 violations / 0 warnings),
2026-05-23, HEAD `11761759`. This is a **DRAFT scope held for operator review** before
`composite_sig.py` + test vectors are produced. Protocol: V-check (done) → hold (done) →
scope doc (this file) → **hold** → `composite_sig.py` + vectors → P-check → hold → atomic commit.
