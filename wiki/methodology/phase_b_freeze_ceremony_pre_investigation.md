# Phase B Freeze Ceremony (#6 ① v1.1 + #10 ③) — Pre-Ceremony Investigation

**Status:** Pre-ceremony investigation (read-only). **No `--generate` fired; no code changed.**
HEAD `48879281` (PR#7) / `d483d1a3` (main). Held for operator review before any ceremony plan.
**Headline: the ceremony as originally shaped collides with the existing freeze infrastructure —
recommend a revised shape + one operator decision (Decision FC) before proceeding.**

---

## The collision (read first)
The scope docs assumed the freeze = "add the tag to `_PATTERN_017_FROZEN_TAGS`, bump
`frozen_v1_commitment_family_count` 12→13, ripple `INV-MYTHOS-FAMILIES-001`" — the ffa887d6 shape.
**That shape does not work for the Phase B tags**, because the existing freeze infrastructure is
**`VAPI-`-prefix-coupled** and the Phase B primitives are **QorTroller-branded / IETF-derived**:

- **`mythos_crypto_drift` scanner regex** (`bridge/vapi_bridge/mythos_variants.py:891`) is
  `rb'b"(VAPI-[A-Za-z0-9_\-]+-v\d+)"'` — it discovers **only `VAPI-`-prefixed** literals. It never
  sees `QORTROLLER-IPACT-RENEWAL-v1`, `QORTROLLER-IPACT-CHALLENGE-v1`, `COMPSIG-*`, or
  `CompositeAlgorithmSignatures2025`. (This is why crypto_drift returned 0 for ③ and #8 — not
  because they're frozen, because they're invisible to it.)
- **Therefore adding `QORTROLLER-IPACT-RENEWAL-v1` to `_PATTERN_017_FROZEN_TAGS` BREAKS the audit:**
  `missing = _PATTERN_017_FROZEN_TAGS - discovered_bytes` (line 911) would flag it as a **permanent
  CRITICAL "missing"** every run (the scanner can't discover a non-`VAPI-` tag). The frozenset and
  the scanner are coupled; a QorTroller tag in the VAPI frozenset is a standing false-positive.

## (a) Tag classifications — verified

**① composite-sig → NOT a commitment family. It is a wire-format / protocol primitive.**
Composite-sig produces *signatures over M′*, not domain-tagged SHA-256 *commitments to a state
event* (the R3 family criterion). Its literals are the IETF Prefix `CompositeAlgorithmSignatures2025`
(an **IETF draft constant, not even QorTroller-owned**), the three `COMPSIG-*` labels, and the OIDs —
none are PATTERN-017 commitment-family tags. → **#6 does NOT touch `_PATTERN_017_FROZEN_TAGS` or any
family count.** #6 = **PV-CI byte-literal invariants** pinning the signature wire format (32-B Prefix
+ 3 labels + M′ construction) AND the v1.1 pubkey wire format (envelope + field widths 65/1952/1312/32
+ version=0x01) in `l9_presence/composite_sig.py`. (Precedent: it's a primitive pinned by PV-CI, like
the 228-byte PoAC wire format is pinned — not a frozenset member.)

**③ `QORTROLLER-IPACT-RENEWAL-v1` → IS a commitment family (D-③-1 Reading A), but QorTroller-branded.**
Genuine domain-tagged SHA-256 commitment. BUT it cannot enter the `VAPI-`-only frozenset/scanner
(see collision). → #10 freeze = **PV-CI byte-literal invariants** pinning the commitment byte layout
+ `IPACT_RENEWAL_EPOCH_DAYS=90` + the two domain tags (`QORTROLLER-IPACT-RENEWAL-v1` /
`-GENESIS-v1`) in `bridge/vapi_bridge/ipact_renewal.py` (brand-agnostic; the gate already pins
arbitrary byte literals).

**#8 `QORTROLLER-IPACT-CHALLENGE-v1` → capability tag, DEFER (agree with operator).** RESERVED;
only one consumer (#8's internal test). Not frozen in this ceremony. Tracked for a later freeze when
a second consumer exists.

## (b) Family-count math — needs Decision FC
`frozen_v1_commitment_family_count = 12` (`doc_consistency_registry.py:118`) and
`INV-MYTHOS-FAMILIES-001` ("12 commitment families") are **semantically the `VAPI-` Layer-C
PATTERN-017 family count** (the frozenset they describe is `VAPI-`-only: GIC/WEC/VAME/CORPUS-SNAPSHOT/
CONSENT/BIOMETRIC-SNAPSHOT/LISTING/FRR/ZKBA-ARTIFACT/AGENT-COMMIT/O3-SUPERSEDE/PHYSICAL-DATA-ATTESTATION
= 12). ③ is QorTroller-branded. **Decision FC required:**
- **FC-(a) [recommended]** — the VAPI count is the **Layer-C VAPI category** count; it **stays 12**.
  ③ is the **first QorTroller-branded commitment family**, tracked by its own PV-CI invariant + a
  NEW canonical fact `qortroller_commitment_family_count = 1`. **Why:** matches QRESCE brand
  discipline (VAPI = Layer-C FROZEN category, frozen as-is; QorTroller = the project/era layer). Keeps
  the two brand namespaces clean; does not retrofit a QorTroller tag into a VAPI-Layer-C invariant.
- **FC-(b)** — treat all commitment families as one namespace; bump to **13**; extend the crypto_drift
  scanner regex to also discover `QORTROLLER-…-v\d+` + add ③ to a (brand-agnostic) frozenset; ripple
  INV-MYTHOS-FAMILIES-001 to 13. **Cost:** modifies the audit primitive's scanner itself (sensitive),
  and conflates the brand layers the QRESCE work deliberately separated.

The D-③-1 scope-doc text ("13th PATTERN-017 family … 12→13 … INV-MYTHOS-FAMILIES-001 ripple") assumed
FC-(b) implicitly; this investigation surfaces that FC-(a) is cleaner and brand-correct. **Operator's call.**

## (c) PV-CI invariants to add (the real freeze, both shapes)
Brand-agnostic byte-literal pins via `vapi_invariant_gate.py --generate` + allowlist regen:
- **#6 ① (composite-sig):** INV pinning `PREFIX = b"CompositeAlgorithmSignatures2025"` (32B) + the
  three `COMPSIG-*` labels + `_WIRE_VERSION`/envelope widths + the v1.1 `_PQ_PUBKEY_LEN`
  {1952,1312,32} + `ec_len==65` + version=0x01 acceptance, in `l9_presence/composite_sig.py`.
- **#10 ③ (ipact-renewal):** INV pinning `_DOMAIN_TAG`/`_GENESIS_TAG` (27/35B) + the 147-B commitment
  preimage byte order + `IPACT_RENEWAL_EPOCH_DAYS=90`, in `bridge/vapi_bridge/ipact_renewal.py`.
- (If FC-(b): also scanner regex + frozenset edits + INV-MYTHOS-FAMILIES-001 description. If FC-(a):
  none of the VAPI mythos surfaces are touched; optionally a new `INV-QORTROLLER-FAMILIES-001`.)

## (d) v6.1 reconciliation status
Unchanged by this ceremony (still a separate tracked item). Under **FC-(a)** the VAPI count stays 12
so the existing amber (11→12) is unaffected and v6.1 additionally documents "QorTroller-branded
families tracked separately." Under **FC-(b)** v6.1 must cover 11→12→13. Recommend FC-(a) keeps v6.1
scope smaller.

## (e) Ceremony justification text (draft — for whichever shape is chosen)
FC-(a) shape: `invariant_change: freeze Phase B wire-formats via PV-CI — composite-sig v1.1
(signature + pubkey) + QORTROLLER-IPACT-RENEWAL-v1 commitment layout + IPACT_RENEWAL_EPOCH_DAYS=90;
post-#8 integration evidence; VAPI Layer-C family count unchanged (12); ③ = 1st QorTroller-branded
family.`

## (f) CHALLENGE-tag deferral — CONFIRMED
`QORTROLLER-IPACT-CHALLENGE-v1` is NOT frozen in this ceremony. Deferred (new backlog item) until a
second consumer of the challenge surface exists. Agree with operator.

---

## Recommendation
**Do NOT fire the ffa887d6-shape ceremony.** Instead:
1. **Operator resolves Decision FC** (recommend FC-(a): VAPI count stays 12; ③ = 1st QorTroller-branded
   family with its own count/invariant).
2. The freeze is **PV-CI byte-literal invariants only** for ① (wire formats) + ③ (commitment layout +
   epoch); the `VAPI-` mythos frozenset / `frozen_v1_commitment_family_count` / INV-MYTHOS-FAMILIES-001
   are **untouched** under FC-(a).
3. Then a ceremony plan (Step A operator `--generate` → B ripples → C re-verify → D commit → E push +
   cherry-pick), V-checked first.

This is the pre-ceremony investigation catching a mechanism collision before a high-stakes,
hard-to-reverse governance ceremony — exactly its purpose. **Held for operator review of Decision FC +
the revised shape.**

## Cross-refs
`bridge/vapi_bridge/mythos_variants.py` (frozensets + VAPI-only scanner), `scripts/vapi_invariant_gate.py`
(INV-MYTHOS-FAMILIES-001 + the gate), `bridge/vapi_bridge/doc_consistency_registry.py`
(frozen_v1_commitment_family_count=12), `l9_presence/composite_sig.py` (#6 target),
`bridge/vapi_bridge/ipact_renewal.py` (#10 target). Memory: [[composite-sig-v1-shipped]],
[[ipact-renewal-cadence-v1-shipped]], [[ipact-handshake-wiring-v1-shipped]],
[[frozen-governance-gaps-2026-05-22]] (ffa887d6 precedent + v6.1).
