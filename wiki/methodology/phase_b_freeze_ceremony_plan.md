# Phase B Freeze Ceremony (#6 ① v1.1 + #10 ③) — Revised Ceremony Plan

**Status:** Ceremony PLAN (no `--generate` fired; no code changed). Held for operator review +
confirmation before Step A. HEAD `48879281` / main `d483d1a3`. Pre-investigation:
`wiki/methodology/phase_b_freeze_ceremony_pre_investigation.md`. **Decision FC → FC-(a)** (VAPI
Layer-C namespace separate from QorTroller project namespace). **Scanner → Option A**, implemented
as a **separate parallel function** so the existing VAPI scanner is byte-identical.

---

## Decisions locked
- **FC-(a)** — `frozen_v1_commitment_family_count` (VAPI Layer-C) **stays 12**; a NEW
  `qortroller_commitment_family_count = 1` tracks frozen QorTroller-branded families. VAPI `-` prefix
  is permanent Layer-C technical reference (QRESCE discipline); conflating namespaces is rejected.
- **POEP-v0 framing precision:** ③ is the **first FROZEN** QorTroller-branded family.
  `QORTROLLER-POEP-v0` already exists in the same namespace (PoEP, hardware-validated across 5
  players) but is **NOT frozen here** — it remains v0/default-OFF pending the L6B N≥50 gate. When it
  freezes (separate later ceremony, post-activation), `qortroller_commitment_family_count` → 2.
- **Scanner-A (parallel function)** — add `mythos_qortroller_crypto_drift` + QorTroller frozensets;
  the existing `mythos_crypto_drift` function + `_PATTERN_017_FROZEN_TAGS` + `_KNOWN_CAPABILITY_TAGS`
  are **untouched byte-for-byte**. This is additive, not a modification of the load-bearing VAPI
  audit primitive.

## Implementation nuances (load-bearing)
1. **Genesis dual-tag.** ③ uses TWO domain tags in `ipact_renewal.py`: `QORTROLLER-IPACT-RENEWAL-v1`
   (per-link) + `QORTROLLER-IPACT-RENEWAL-GENESIS-v1` (genesis). Both go in
   `_QORTROLLER_PATTERN_017_FROZEN_TAGS` (else the scanner flags GENESIS unknown-HIGH). They are **2
   tag-entries representing 1 family** → the count fact = **1 family**, not 2.
2. **CHALLENGE capability tag.** `QORTROLLER-IPACT-CHALLENGE-v1` lives in `ipact_challenge.py` (a
   scanned file) → must be in `_QORTROLLER_KNOWN_CAPABILITY_TAGS` (known-but-not-frozen, like VAPI's
   `VAPI-BT-WITNESS-BLE-v1`) so the scanner doesn't flag it unknown-HIGH. Its **freeze stays
   deferred** (a separate later ceremony, second-consumer-gated).
3. **Scanner scope = `bridge/vapi_bridge/` only.** `QORTROLLER-POEP-v0` is in `l9_presence/` (not
   scanned) → correctly invisible; consistent with POEP being unfrozen.
4. **Parallel-function constraint.** Do NOT modify `mythos_crypto_drift`'s body, regex, or
   frozensets. Add a NEW `mythos_qortroller_crypto_drift` (same fail-open contract, regex
   `rb'b"(QORTROLLER-[A-Za-z0-9_\-]+-v\d+)"'`, scanning the same bridge_dir) checking against the two
   new QorTroller frozensets.

## What freezes (the real freeze = PV-CI byte-literal invariants)
- **#6 ① v1.1** (`l9_presence/composite_sig.py`) — new PV-CI invariants pinning: `PREFIX =
  b"CompositeAlgorithmSignatures2025"` (32B), the 3 `COMPSIG-*` labels, the signature envelope
  (`_WIRE_VERSION`/`_EC_LEN_BYTES`/`_PQ_LEN_BYTES`), and the v1.1 pubkey format (`_PQ_PUBKEY_LEN`
  {1952,1312,32} + `ec_len==65` + version=0x01 acceptance). **Does NOT touch any commitment frozenset
  or family count** (composite-sig is a signature primitive, not a commitment family).
- **#10 ③** (`bridge/vapi_bridge/ipact_renewal.py`) — new PV-CI invariants pinning: `_DOMAIN_TAG`
  (27B) + `_GENESIS_TAG` (35B) + the 147-B commitment preimage byte order + `IPACT_RENEWAL_EPOCH_DAYS
  = 90`.
- **Namespace tracking** — new canonical fact `qortroller_commitment_family_count = 1` +
  (Scanner-A) the two QorTroller frozensets + `mythos_qortroller_crypto_drift` + a new
  `INV-QORTROLLER-FAMILIES-001` pinning the QorTroller frozenset declaration.
- **UNTOUCHED:** `frozen_v1_commitment_family_count` (stays 12), `_PATTERN_017_FROZEN_TAGS`,
  `_KNOWN_CAPABILITY_TAGS`, `mythos_crypto_drift`, `INV-MYTHOS-FAMILIES-001`.

## Steps
**Step B-pre (Claude — code, BEFORE --generate so the gate can pin it):**
  1. Add the #6 + #10 PV-CI invariant definitions to `scripts/vapi_invariant_gate.py`.
  2. Add `_QORTROLLER_PATTERN_017_FROZEN_TAGS` {RENEWAL-v1, RENEWAL-GENESIS-v1} +
     `_QORTROLLER_KNOWN_CAPABILITY_TAGS` {CHALLENGE-v1} + `mythos_qortroller_crypto_drift` to
     `mythos_variants.py` (existing VAPI surfaces untouched).
  3. Add `qortroller_commitment_family_count = 1` to `doc_consistency_registry.py` +
     `INV-QORTROLLER-FAMILIES-001` to the gate.
  4. Add tests: T-FREEZE-* (PV-CI invariants present + the new scanner discovers ③'s 2 tags + 0
     drift + CHALLENGE not flagged + count fact = 1).
  **V-check (`vapi_validate_proposal`) here, then HOLD for operator review of the code before --generate.**

**Step A (operator — governance):** fire
  `python scripts/vapi_invariant_gate.py --generate --reason "<drafted below>" --confirm-governance`
  (interactive phrase "I understand this changes a frozen protocol invariant"). Regenerates the
  allowlist Merkle root pinning the new invariants. **Operator-only.**

**Step C (Claude — re-verify):** `vapi_invariant_gate.py --report` all pass; `mythos_crypto_drift` 0
  (VAPI, untouched); `mythos_qortroller_crypto_drift` 0 (discovers ③'s 2 tags, CHALLENGE known); the
  freeze test suite + 108 Phase-B tests pass; confirm `frozen_v1_commitment_family_count`==12 and
  `qortroller_commitment_family_count`==1.

**Step D (Claude — commit):** atomic commit, full ceremony reasoning (Decision FC→FC-(a) + 3 reasons,
  POEP-v0 framing precision, Scanner-A parallel-function rationale, the mechanism-collision finding
  that triggered the revision, the four honesty rails, what froze vs what stayed untouched).

**Step E (Claude — push):** push PR #7 + cherry-pick to main (standing instruction).

## Draft --reason (Step A)
`invariant_change: Phase B freeze (FC-a) — PV-CI-pin composite-sig v1.1 (sig+pubkey wire formats) +
QORTROLLER-IPACT-RENEWAL-v1 commitment layout + IPACT_RENEWAL_EPOCH_DAYS=90; add
qortroller_commitment_family_count=1 + parallel QorTroller drift scanner; VAPI Layer-C family count
unchanged (12); post-#8 integration evidence; CHALLENGE tag deferred.`

## Honesty rails
- Does NOT change production state of ① v1.1 or ③ (both shipped + exercised via #8); makes the
  canonical wire formats immutable-without-governance.
- Does NOT close the dormant-blind gap (four-stage path: ③ → #8 → ② P4b → VBDIP-0006 → flip-on).
- Does NOT freeze `QORTROLLER-IPACT-CHALLENGE-v1` (deferred; known-capability so the scanner is quiet).
- Does NOT modify `mythos_crypto_drift`'s VAPI scanner/frozensets (Scanner-A is a parallel function).
- Establishes the namespace-separation pattern for future QorTroller-branded primitives (POEP-v0 next).

## Tracked follow-ons after this ceremony
#3 LAMPS submission · #4 IANA PEN · #5 PEN OID pin · **#6 ① v1.1 freeze → CLOSED** · #9 phase-180
hygiene · **#10 ③ freeze → CLOSED** · #11 VBDIP-0006 signer · #12 ② P4b key registration ·
**NEW: QORTROLLER-IPACT-CHALLENGE-v1 freeze** (second-consumer-gated) · **NEW: v6.1 reconciliation**
(now also documents the qortroller_commitment_family_count namespace) · **NEW: QORTROLLER-POEP-v0
freeze** (post-L6B-N≥50 activation; → count 2).
