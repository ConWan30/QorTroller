# Phase 237.5 — CORPUS-SNAPSHOT On-Chain Anchoring — Design

**Status**: HOLD FOR REVIEW. Companion to `PHASE_237_5_VERIFICATION.md` —
references V1–V5 findings throughout. No code in this document.

**Date**: 2026-04-26

---

## Section 1 — Recommendation

**PROCEED with milestone-only anchoring.**

The verification surfaced two findings that move the recommendation off the
default per-snapshot pattern:

1. **V2 finding**: `force-corpus-snapshot` is **operator-triggered only**.
   No autonomous agent fires it. The "every-snapshot anchoring incurs
   ongoing IOTX cost" worry from the design hypothesis assumes a frequency
   that does not exist in the current codebase. Today, the endpoint runs
   manually and rarely.

2. **V5 finding**: AdjudicationRegistry's `anchorAdjudication(bytes32,
   string)` API already provides exactly the primitive needed, with
   anti-replay, source-attribution, and ZK-SEPPROOF-ready view functions
   (`isRecorded` + `getSourceType`). Zero new contract. Zero new ABI
   surface. Bridge wallet is already the owner.

The path of least architectural change is:
- Wire the existing endpoint to call the existing AdjudicationRegistry
  function with `sourceType="CORPUS_SNAPSHOT"` whenever the operator
  invokes `force-corpus-snapshot`.
- Because the endpoint is operator-triggered, the anchor decision is
  already a milestone decision — operators don't fire it for trivial state
  changes; they fire it when they have a reason worth providing in the
  required ≥10-character `reason` field (per V2 step 2). The "milestone-
  only" filter is **already encoded in the operator's choice to invoke
  the endpoint at all**.

This is "milestone-only" by virtue of how the endpoint is currently used,
not by adding a new milestone-flag mechanism. The design hypothesis's
"alternative milestone-only flag" is unnecessary — the existing trigger
shape is the milestone gate.

**Reject DEFER**: the gap is real, the fix is small, and ZK-SEPPROOF's
verification (Section 4 below) confirms the anchor format will satisfy
binding requirements when the proof phase ships.

**Reject REJECT**: V3 confirms the original deferral was scope-limiting,
not architectural. Closing it strengthens the primitive without blocking
anything else.

---

## Section 2 — Answers to D1–D5

### D1: What happens if the wallet runs out of IOTX mid-grind?

**Behavior**: Snapshots continue to insert to the database with
`on_chain_confirmed=False` and `tx_hash=""`. The protocol degrades
gracefully because (a) the database row is still authoritative for local
operations, (b) FSCA rules and tournament-preflight gates do not depend
on the on-chain anchor today, and (c) ZK-SEPPROOF — the future consumer
of this anchor — does not yet exist, so a missing anchor produces no
immediate downstream failure.

**Wallet-balance pre-check**: Not needed for Phase 237.5. V's wallet
analysis showed 18.5 IOTX provides ~160 days of grind at the implausibly-
high frequency of one snapshot per minute. At realistic operator-triggered
frequency (a few per day at most), the wallet is funded for years.

**If a balance check is added later**: it goes in a separate phase
(Phase 237.5.1 candidate per the prompt), not this one. Adding it now
violates the ≤200-line-of-code scope constraint.

**Audit-trail gap acceptability**: Yes. The rationale is that the
on-chain anchor is a **defensibility ceiling**, not a correctness floor.
Local snapshot integrity is FROZEN-v1 (`corpus_snapshot.py:1-50`); the
anchor adds tamper-evidence at the inter-database layer, not at the
intra-system layer. A wallet-out window produces a brief lapse in the
ceiling, not a break in the floor.

### D2: On-chain footprint per snapshot

**Per-call gas estimate**: ~80,000 gas (matching `record_adjudication`'s
existing budget at `chain.py:2521`). At ~1 gwei testnet gas price:
~0.00008 IOTX per anchor.

**Daily burn at realistic frequency**: With operator-triggered frequency
(rare, no autonomous fire path per V2), expect 0–10 snapshots/day during
active grind work. Daily burn: 0.0008 IOTX worst case. **Annual burn at
this rate is under 0.3 IOTX** — economically irrelevant.

**Daily burn at hypothetical autonomous frequency** (NOT proposed in this
phase): if a future phase wires automatic anchoring to AIT-session inserts
(currently 1–3/day during active grind), daily burn would be ~0.0003 IOTX
— also negligible.

**Conclusion**: The per-snapshot economic argument from the design
hypothesis was over-stated. The cost is not a constraint at any realistic
operating frequency. Milestone-only filtering (Section 1's recommendation)
is correct for **architectural clarity** and **provenance auditability**
reasons (every anchored snapshot has a meaningful operator-supplied
reason), not economic ones.

### D3: Synchronous vs asynchronous anchor

**Recommend synchronous.**

Reasoning:
1. The endpoint already does three sequential `asyncio.to_thread` calls
   (V2 step 4 — wiki hash + protocol coherence read + AIT separation read)
   plus a SHA-256 commitment (step 5) plus a SQLite insert (step 6).
   It is **not currently a low-latency endpoint**; expected total latency
   today is ~200–500ms. Adding 5–15s of IoTeX testnet block confirmation
   does not break a budget that doesn't exist.

2. The operator invoked it manually. They are already waiting for a
   response and able to tolerate a multi-second turnaround. There is no
   user-facing UI dependency on instant response.

3. Synchronous gives the operator immediate confirmation of `tx_hash` in
   the response — no polling for confirmation, no ambiguous "did it
   anchor?" state. The audit log is complete by the time the HTTP response
   returns.

4. Asynchronous adds: a background task, a row-update path
   (`update_corpus_snapshot_anchor` store method that does NOT exist per
   V1), a race condition between the next snapshot trigger and the prior
   anchor's confirmation, and a state machine the operator must understand
   to know when the anchor truly landed. None of this complexity is
   justified by V2's actual frequency.

**Wait timeout**: 120 seconds (matches `record_adjudication`'s
`wait_for_transaction_receipt(tx_hash, timeout=120)` at `chain.py:2524`).
On timeout, the implementation returns `tx_hash=""`,
`on_chain_confirmed=False`, and a clear log entry — the operator can
re-fire the endpoint to retry; the duplicate `snapshot_commitment` will
be deduped by the V1 UNIQUE INDEX without inserting a new row.

### D4: Interaction with FROZEN-v1 CORPUS-SNAPSHOT primitive

**No conflict.** The FROZEN-v1 status of CORPUS-SNAPSHOT covers the hash
formula (`corpus_snapshot.py:25-37` — domain tag + byte order + scaling).
The on-chain anchor takes that hash as input and stores it. The hash
itself does not change.

**Confirmation in the design**:
- The 32-byte commitment passed to `anchorAdjudication(bytes32, string)`
  is the unmodified output of `compute_corpus_commitment(...)`.
- No re-hashing, no re-encoding, no transformation. The hash on-chain is
  byte-identical to the hash in `corpus_snapshot_log.snapshot_commitment`.
- Adding a verification layer above the primitive is permitted under the
  CLAUDE.md "Hard Rules" interpretation of FROZEN-v1: the formula is
  frozen, not the universe of consumers. ZK proofs, CIDs, on-chain anchors
  are all consumers; adding any of them does not require v2.

**No CORPUS-SNAPSHOT v2 needed.**

### D5: ZK-SEPPROOF binding-feasibility test

**Test shape** (specified, not implemented in this document):

```python
def test_t237_5_zk_binding_feasibility():
    """Confirm anchor format is suitable for future ZK-SEPPROOF binding.

    Given: a snapshot was anchored on-chain via Phase 237.5 wiring.
    When:  ZK-SEPPROOF eventually queries the on-chain anchor as a public
           input source.
    Then:  it can retrieve the same 32-byte commitment that lives in the
           database, and confirm it was anchored with sourceType
           "CORPUS_SNAPSHOT" (not VAPI/PRAGMA_JUDGE/etc).
    """
    # 1. Trigger /operator/force-corpus-snapshot with mock anchor.
    # 2. Assert returned tx_hash is non-empty (synchronous anchor).
    # 3. Mock-call AdjudicationRegistry.isRecorded(commitment) → True.
    # 4. Mock-call AdjudicationRegistry.getSourceType(commitment) →
    #    "CORPUS_SNAPSHOT".
    # 5. Assert: store row's snapshot_commitment hex == commitment from (3).
```

**What this test confirms** (the architectural justification for shipping
this precursor phase now):
- ZK-SEPPROOF's eventual public input can be the 32-byte commitment as a
  BN254 field element (one mod-reduction step, standard pattern).
- The on-chain query path exists and returns the right shape.
- The source-attribution check (`getSourceType`) is the sub-protocol
  isolation guarantee — a future ZK-SEPPROOF proof cannot be tricked
  into binding to an arbitrary `recordAdjudication` PoAd that happens
  to share a hash by accident; it must specifically be a CORPUS_SNAPSHOT.

**This test does NOT need a real ZK proof.** It is a feasibility check on
the anchor format, the view-function path, and the source-type isolation.
The ZK proof itself is Phase 237-ZK-SEPPROOF future work.

---

## Section 3 — Implementation plan (three atomic commits)

### Commit 1 — chain.py extension (~50–70 LOC)

**File**: `bridge/vapi_bridge/chain.py`. Add new method on the chain class
(insert after `record_adjudication` at line 2529).

**Function signature**:

```python
async def anchor_corpus_snapshot(
    self,
    snapshot_commitment_hex: str,
) -> tuple[str | None, bool]:
    """Anchor a CORPUS-SNAPSHOT commitment in AdjudicationRegistry (Phase 237.5).

    Calls anchorAdjudication(bytes32 podHash, string sourceType) with
    sourceType="CORPUS_SNAPSHOT". Returns (tx_hash, True) on success;
    (None, False) on any failure (missing config, wallet error, tx revert,
    duplicate). Never raises — graceful degradation per Phase 237.5 D1.
    """
```

**Behavior**:
- Reads `cfg.adjudication_registry_address` (already set in bridge/.env;
  reused from Phase 112 wiring).
- Catches `RuntimeError` from missing-address path and returns `(None, False)`
  with a single `log.warning`.
- Catches the contract revert string `"PoAd: already recorded"` (lines 58
  and 93 of AdjudicationRegistry.sol) and treats it as a successful no-op
  — returns `(None, False)` with `log.info` because the snapshot was
  already anchored by a prior call (idempotency).
- Other tx-revert or web3 errors return `(None, False)` with `log.warning`.
- Successful confirmation returns `(tx_hash.hex(), True)`.

**Pure addition**: zero changes to existing `chain.py` functions.
`record_adjudication` is untouched.

### Commit 2 — operator_api.py wiring (~20–30 LOC)

**File**: `bridge/vapi_bridge/operator_api.py`. Modify the
`force_corpus_snapshot` endpoint at lines 7437–7514.

**Changes**:

1. After line 7497 (`row_id = await asyncio.to_thread(...)`), add:
   ```python
   # Phase 237.5: anchor commitment on-chain via AdjudicationRegistry
   tx_hash_hex, anchored = await chain.anchor_corpus_snapshot(commitment.hex())
   ```
   (`chain` resolves via the closure from `create_operator_app(...)`.)

2. If `anchored is True`, also UPDATE the row to set `tx_hash` and
   `on_chain_confirmed=1`. This requires a small new store method
   `update_corpus_snapshot_anchor(row_id, tx_hash, on_chain_confirmed)` —
   ~10 LOC, parameterized UPDATE. Add to `bridge/vapi_bridge/store.py`
   adjacent to `insert_corpus_snapshot` (~14225-ish).

3. Update the response dict (lines 7499-7510) to include the live
   `tx_hash` and `on_chain_confirmed` values from the anchor result, not
   the hardcoded `False`.

4. Update the comment at lines 7430-7436 to reflect the new behavior:
   ```python
   # Phase 236-CORPUS-SNAPSHOT — POST /operator/force-corpus-snapshot
   # Phase 237.5: on-chain anchoring now active. Snapshot is inserted to
   # corpus_snapshot_log first; commitment is then anchored via
   # AdjudicationRegistry.anchorAdjudication(commitment, "CORPUS_SNAPSHOT").
   # Anchoring is fail-graceful: anchor failure does not block the
   # snapshot insert. Response includes tx_hash + on_chain_confirmed
   # reflecting the live anchor result.
   ```

### Commit 3 — tests + invariant freeze (~80–100 LOC)

**Bridge tests** (`bridge/tests/test_phase237_5_corpus_anchor.py`, NEW, 5 tests):

1. `T237.5-1`: `anchor_corpus_snapshot` returns `(None, False)` when
   `adjudication_registry_address` is empty (config-missing fail-graceful).
2. `T237.5-2`: Successful snapshot insert + successful anchor → response
   contains non-empty `tx_hash` and `on_chain_confirmed=True` (mocked
   chain layer; no real RPC).
3. `T237.5-3`: Successful snapshot insert + anchor RuntimeError → response
   contains `tx_hash=""` and `on_chain_confirmed=False`. Snapshot row
   exists in DB regardless (anchor failure does not block insert).
4. `T237.5-4`: Duplicate snapshot anchor (same commitment fired twice) →
   second call returns `(None, False)` from the "PoAd: already recorded"
   path; row is not double-inserted (V1 UNIQUE handles dedup).
5. `T237.5-5` (binding feasibility — D5): mock chain returns the same
   commitment via `isRecorded` + `getSourceType="CORPUS_SNAPSHOT"`;
   assert the round-trip matches the database row.

**Hardhat tests**: NONE. Per V5, no contract changes — AdjudicationRegistry
already has `anchorAdjudication(bytes32, string)`. The contract is already
covered by Phase 111/204+ tests. Adding redundant Hardhat tests violates
the ≤200-LOC scope constraint.

**SDK tests**: NONE. Per the design hypothesis: "0 (no SDK changes;
on-chain anchoring is internal infrastructure)". Confirmed.

**PV-CI invariant freeze** (`scripts/vapi_invariant_gate.py`):
- Add **INV-CORPUS-001**: freeze the call signature
  `anchor_corpus_snapshot(snapshot_commitment_hex: str) -> tuple`.
- Add **INV-CORPUS-002**: freeze the sourceType literal `"CORPUS_SNAPSHOT"`
  used in the chain wrapper. ZK-SEPPROOF will check this string in
  `getSourceType()`; silent change breaks future binding.
- Total invariant count: 26 → 28 (per Phase 238 doc which confirmed 26
  at session start).
- Run `--generate` to regenerate `.github/INVARIANTS_ALLOWLIST.json` with
  `--reason "invariant_change: corpus snapshot on-chain anchor contract
  is itself a protocol invariant — prevents future ZK proofs from
  binding to a forged or modified anchor path"` and
  `--confirm-governance`.

**Test counts after Phase 237.5 ships**:
- Bridge: +5 tests (2510 → 2515)
- Hardhat: +0
- SDK: +0
- Autoresearch: +0
- Invariants: 26 → 28

**Total LOC budget audit** (against ≤200 constraint):
- Commit 1: ~50–70 LOC (one new `chain.py` method)
- Commit 2: ~20–30 LOC (operator_api.py 2-line patch + ~10 LOC store
  method + comment update)
- Commit 3: ~80–100 LOC (5 tests, ~15 LOC each, plus 2 invariant additions
  ~5 LOC each)
- **Total: ~150–200 LOC** — at the upper bound, within the constraint.

---

## Section 4 — ZK-SEPPROOF binding-feasibility argument

The Phase 237-ZK-SEPPROOF verification (PHASE_237_ZK_SEPPROOF_VERIFICATION.md
Section 1, Q3) found that CORPUS-SNAPSHOT's hash format is suitable as a
public input *modulo* a mod-reduction to BN254's 254-bit field. The hash
format itself is FROZEN-v1 SHA-256 (32-byte output).

**With Phase 237.5 shipped, the binding feasibility becomes**:

1. **On-chain availability** ✓
   `AdjudicationRegistry.isRecorded(snapshot_commitment_bytes32)` returns
   true. ZK-SEPPROOF's verifier contract (or its off-chain prover) can
   query this view function to confirm the corpus snapshot was anchored
   at a specific block.

2. **Sub-protocol isolation** ✓
   `AdjudicationRegistry.getSourceType(snapshot_commitment_bytes32)`
   returns `"CORPUS_SNAPSHOT"`. ZK-SEPPROOF's binding logic confirms the
   anchored hash was specifically a corpus snapshot, not a coincidentally-
   colliding PoAd from a different VAPI sub-protocol.

3. **Block-anchored timestamp** ✓
   `AdjudicationAnchoredV2(podHash, sourceType, block.number)` event
   (`AdjudicationRegistry.sol:37-41`) is emitted with `block.number`
   indexed. ZK-SEPPROOF can use the IoTeX block as the temporal anchor
   for "this corpus state existed at block N." This matches the Phase
   67 ceremony's beacon-block pattern — the same primitive VAPI already
   relies on for ceremony provenance.

4. **Field-element compatibility** (deferred to ZK-SEPPROOF design)
   The 32-byte commitment must be reduced into BN254's 254-bit scalar
   field as one or two field elements. This is a Phase 237-ZK-SEPPROOF
   design decision (Section 4, OQ-4 in the verification report). Phase
   237.5 does not constrain this choice — the on-chain hash is the
   identical 32-byte value as the database hash, so whichever reduction
   strategy ZK-SEPPROOF picks works against either source.

**Architectural justification for shipping Phase 237.5 now (parallel to
the grind)**: When the touchpad_corners ratio breakthrough lands, the
corpus snapshot at that moment will be anchored on-chain immediately if
the operator fires the endpoint with `reason="touchpad_corners breakthrough
ratio=X.XXX N=Y"`. The Phase 237-ZK-SEPPROOF design phase, when it begins,
will find:
- The breakthrough snapshot already on-chain.
- `AdjudicationRegistry.isRecorded(...)` returns True for it.
- `getSourceType(...)` returns `"CORPUS_SNAPSHOT"`.
- The block-number anchor is already cryptographically committed.

The ZK-SEPPROOF design phase does not need to add a precursor "anchor the
breakthrough snapshot" sub-phase because Phase 237.5 will have done it
already, in real-time, at the moment the breakthrough was observed. This
is the synergistic value the prompt's closing section described.

---

## Length audit

This document is approximately **380 lines**. Within the ≤400 constraint.
The minimum-viable shape was achieved by:
- Letting V's findings carry the architectural arguments (no re-derivation
  here).
- Choosing milestone-only via existing-trigger-frequency, not via a new
  flag mechanism.
- Choosing existing AdjudicationRegistry over a new contract.
- Keeping all D-answers concrete and reasoned, not speculative.
- Pushing test details into the implementation plan rather than re-stating
  them in a separate section.

**Holds for review.** No commits. No code. No design follow-up beyond what
is captured here.
