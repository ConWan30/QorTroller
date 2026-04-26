# Phase 237.5 — Pre-design Verification (V1–V5)

**Status**: HOLD FOR REVIEW. No design proposal in this document. No code.
Verification standard from Phase 238 + Phase 237-ZK-SEPPROOF applied: every
claim cites file:line or on-chain RPC result.

**Date**: 2026-04-26

---

## V1 — Current corpus_snapshot_log schema

**Source**: `bridge/vapi_bridge/store.py:3279-3306`. Schema verbatim:

```sql
CREATE TABLE IF NOT EXISTS corpus_snapshot_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_commitment TEXT NOT NULL,
    wiki_hash           TEXT NOT NULL,
    agent_root          TEXT NOT NULL DEFAULT '',
    separation_ratio    REAL NOT NULL DEFAULT 0.0,
    corpus_n            INTEGER NOT NULL DEFAULT 0,
    ts_ns               INTEGER NOT NULL,
    on_chain_confirmed  INTEGER NOT NULL DEFAULT 0,
    ipfs_cid            TEXT NOT NULL DEFAULT '',
    tx_hash             TEXT NOT NULL DEFAULT '',
    trigger_reason      TEXT NOT NULL DEFAULT '',
    created_at          REAL NOT NULL
)
```

**Field nullability for `tx_hash` and `on_chain_confirmed`**:

- `on_chain_confirmed INTEGER NOT NULL DEFAULT 0` — `NOT NULL`, defaults to 0.
  Stored as INTEGER (boolean encoded as 0/1; `store.py:14207` writes
  `1 if on_chain_confirmed else 0`).
- `tx_hash TEXT NOT NULL DEFAULT ''` — `NOT NULL`, defaults to empty string.

**Insert function** at `bridge/vapi_bridge/store.py:14176-14220`. Full signature:

```python
def insert_corpus_snapshot(
    self,
    snapshot_commitment: str,
    wiki_hash: str,
    agent_root: str,
    separation_ratio: float,
    corpus_n: int,
    ts_ns: int,
    trigger_reason: str = "",
    on_chain_confirmed: bool = False,
    tx_hash: str = "",
    ipfs_cid: str = "",
) -> int:
```

The function accepts `on_chain_confirmed` and `tx_hash` parameters with safe
defaults (False / empty string), so:
- The fields are populated at insert time (NOT a post-insert UPDATE pattern).
- A failed-then-retried anchor would require an explicit UPDATE statement —
  which currently does NOT exist in the codebase. Phase 237.5's anchor
  retry path (if shipped) needs either a new `update_corpus_snapshot_anchor`
  store method OR the anchor must succeed within the same insert call.

**Idempotency**: `UNIQUE INDEX idx_corpus_snapshot_log_commit ON
corpus_snapshot_log(snapshot_commitment)` (`store.py:3299-3300`). Duplicate
commitment inserts return the existing row id silently
(`store.py:14213-14220`). This means **two operators triggering snapshots
within the same nanosecond produce the same commitment, are deduped, and
the second caller gets the first caller's row_id**. The anchor wiring needs
to handle the "row already exists" case without re-anchoring.

---

## V2 — force-corpus-snapshot endpoint behavior (current)

**Source**: `bridge/vapi_bridge/operator_api.py:7437-7514`.

Step-by-step from request receipt to response:

1. **Auth + rate-limit gate** (`operator_api.py:7452-7453`):
   `_check_key(api_key)` — full operator key required; `_check_rate(api_key)`.

2. **Reason validation** (`operator_api.py:7454-7458`):
   ```python
   _reason = (reason or "").strip()
   if len(_reason) < 10:
       raise HTTPException(422, "reason must be at least 10 characters
                                 (operator audit field)")
   ```

3. **Wiki dir resolution** (`operator_api.py:7468`):
   `_wiki_dir = getattr(cfg, "wiki_dir", "wiki")` — Config field if set, else
   relative `wiki/` from bridge cwd.

4. **Concurrent input computation** (`operator_api.py:7472-7474`):
   ```python
   wiki_hash = await asyncio.to_thread(compute_wiki_snapshot_hash, _wiki_dir)
   pcs = await asyncio.to_thread(store.get_protocol_coherence_status)
   ait = await asyncio.to_thread(store.get_ait_separation_status)
   ```
   Three SQLite + filesystem reads, dispatched to thread pool to keep the
   asyncio event loop responsive.

5. **Compute commitment** (`operator_api.py:7476-7483`):
   ```python
   agent_root = agent_root_from_hex(pcs.get("latest_merkle_root"))
   ratio = float(ait.get("separation_ratio", 0.0))
   corpus_n = int(ait.get("n_sessions", 0))
   ts_ns = _t236snap.time_ns()
   commitment = compute_corpus_commitment(
       wiki_hash, agent_root, ratio, corpus_n, ts_ns
   )
   ```
   FROZEN-v1 SHA-256 commitment per `corpus_snapshot.py:25-37`.

6. **Persist to corpus_snapshot_log** (`operator_api.py:7485-7497`):
   ```python
   row_id = await asyncio.to_thread(
       store.insert_corpus_snapshot,
       commitment.hex(),
       wiki_hash.hex(),
       agent_root.hex(),
       ratio,
       corpus_n,
       ts_ns,
       _reason,
       False,    # on_chain_confirmed   <-- HARDCODED FALSE
       "",       # tx_hash               <-- HARDCODED EMPTY
       "",       # ipfs_cid (deferred)
   )
   ```
   **Lines 7494-7496 are the architectural gap Phase 237.5 closes.**
   `on_chain_confirmed` is hardcoded `False` and `tx_hash` is hardcoded `""`
   regardless of any configuration.

7. **Return JSON** (`operator_api.py:7499-7510`): 10-key dict with
   `on_chain_confirmed: False` always.

8. **Error path** (`operator_api.py:7511-7514`): exceptions other than
   HTTPException become a 500 Internal Server Error.

**Trigger frequency**: This endpoint is **operator-triggered only**. There is
no autonomous agent that calls it. Per the comment at `corpus_snapshot.py:18-23`:

> Snapshot triggers (caller-driven; this module is pure functions):
>   - New AIT session inserted (separation ratio likely changed)
>   - Separation ratio changed > 0.01 from the prior snapshot
>   - Agent fleet Merkle root changed (any agent added/updated)
>   - Manual via POST /operator/force-corpus-snapshot
>   - Periodic baseline (e.g. once per grind day)

**These are documented intended triggers, not implemented automatic triggers.**
A grep across the codebase (`grep -rE "insert_corpus_snapshot|force-corpus-snapshot"`)
finds the call in only one place: the operator endpoint itself. No agent
fires it on AIT session insert. No periodic timer runs it. Today the
endpoint runs **only when an operator explicitly invokes it**.

This materially changes the per-snapshot economic argument in V5/D2. The
"continuous snapshot every minute during grind" scenario in the design
hypothesis does not match current behavior — snapshots happen rarely and
manually.

---

## V3 — Quote the on-chain deferral comment verbatim

**Source**: `bridge/vapi_bridge/operator_api.py:7430-7436`. Verbatim:

```python
    # Phase 236-CORPUS-SNAPSHOT — POST /operator/force-corpus-snapshot
    # ------------------------------------------------------------------
    # Operator-triggered fresh snapshot. Computes wiki_hash + reads agent root
    # and AIT separation status NOW, builds the FROZEN v1 commitment, persists
    # to corpus_snapshot_log. Optional on_chain_confirm (Phase 221 anchor reuse)
    # is config-gated and not auto-fired here — the snapshot exists locally
    # always; on-chain anchoring is a separate operator action.
```

**Classification of the deferral reason**:

The comment says "config-gated and not auto-fired here." This is **"ship
later"** language, not an architectural prohibition. There is no claim that
on-chain anchoring is dangerous, breaks an invariant, or interacts badly
with another primitive. The comment frames it as a deliberate scope
boundary — the snapshot is locally complete and the on-chain layer is a
separate operator action.

**Implication for Phase 237.5**: The deferral was scope-limiting at Phase
236 ship time, not a load-bearing architectural decision. Phase 237.5 can
close it without addressing a precursor concern. The phase shape is
straightforward.

---

## V4 — Closest existing on-chain anchor pattern

**All chain.anchor_* / chain.record_*_on_chain functions** (from `grep -nE
"async def anchor_|async def record_.*on_chain" bridge/vapi_bridge/chain.py`):

| Function | Line | Signature shape |
|---|---|---|
| `record_ruling_on_chain` | 2024 | device-scoped ruling (Phase 67) |
| `record_ceremony_on_chain` | 2086 | per-circuit MPC ceremony (Phase 67) |
| `record_gate_attestation_on_chain` | 2357 | gate attestation (Phase 222) |
| `record_gsr_sample_on_chain` | 2427 | per-device GSR sample (Phase 99B) |
| `record_adjudication` | 2487 | PoAd legacy 3-arg (Phase 112) |
| `commit_separation_ratio` | 2748 | SeparationRatioRegistry commit (Phase 153) |
| `renew_separation_ratio_commitment` | 2803 | SeparationRatioRegistry renewal (Phase 178) |
| `anchor_coherence` | 2925 | ProtocolCoherenceRegistry (Phase 221) |
| `anchor_coherence_with_provenance` | 3019 | ProtocolCoherenceRegistry (Phase 227) |

**Closest analog by structural shape**: `record_adjudication`
(`chain.py:2487-2529`) is the closest. Its signature:

```python
async def record_adjudication(
    self,
    device_id: str,
    poad_hash_hex: str,
    dual_veto: bool,
) -> str:
    """Anchor a PoAd hash in AdjudicationRegistry.sol (Phase 112).
    ...
    Returns tx_hash hex.
    """
```

Why it's the closest match:
- Anchors a single 32-byte hash representing an off-chain commitment.
- Uses `bytes.fromhex(poad_hash_hex)[:32]` for the anchor argument
  (`chain.py:2504`) — exact pattern needed for snapshot_commitment.
- Inline ABI per-call (`chain.py:2505-2514`), same idiom the new function
  would follow.
- Returns `tx_hash.hex()` (`chain.py:2529`) — matches the design hypothesis
  return contract.
- Raises `RuntimeError` on missing address or revert — Phase 237.5 should
  catch this RuntimeError at the caller (operator endpoint) per the design
  hypothesis's fail-graceful requirement.

**Caveat**: `record_adjudication` is bound to the *legacy* 3-arg
`recordAdjudication(deviceIdHash, poadHash, dualVeto)` API. The new function
should target the *VAPI-EXT* 2-arg `anchorAdjudication(podHash, sourceType)`
API per V5 — different ABI, but the surrounding scaffolding (build_transaction,
sign, send_raw, wait_for_receipt) follows the same pattern.

**`anchor_coherence` is structurally similar but contractually wrong**: it
anchors a `merkleRoot + agentCount + tsNs` triple to ProtocolCoherenceRegistry,
which is fleet-scope, not corpus-scope. The schema is wrong shape for a
corpus snapshot.

---

## V5 — Where the new anchor function lives (A / B / C)

### Candidate A: extend AdjudicationRegistry (existing, deployed)

**Contract**: `0x44CF981f46a52ADE56476Ce894255954a7776fb4` (deployed
2026-03-27 per `contracts/deployed-addresses.json:78` `_phase111_status: LIVE`).

**Existing primitive** at `contracts/contracts/AdjudicationRegistry.sol:79-99`:

```solidity
function anchorAdjudication(
    bytes32 podHash,
    string memory sourceType
) external onlyOwner {
    _anchorAdjudication(podHash, sourceType);
}

function anchorAdjudication(bytes32 podHash) external onlyOwner {
    _anchorAdjudication(podHash, "VAPI");
}

function _anchorAdjudication(bytes32 podHash, string memory sourceType) internal {
    require(!poadRecorded[podHash], "PoAd: already recorded");
    poadRecorded[podHash] = true;
    poadSourceType[podHash] = sourceType;
    totalAdjudications++;
    emit AdjudicationAnchoredV2(podHash, sourceType, block.number);
}
```

**Critical evidence the contract was designed exactly for this case**:
- `sourceType` is a free-form string (`AdjudicationRegistry.sol:23-25` doc:
  `// poadHash → source sub-protocol ("VAPI", "VAPI_MOBILE", "PRAGMA_JUDGE", ...)`).
- The contract code does NOT enforce a closed enum — line 96:
  `poadSourceType[podHash] = sourceType;` accepts any string. Adding
  `"CORPUS_SNAPSHOT"` requires zero contract code change.
- Anti-replay built in: `poadRecorded[podHash]` UNIQUE check
  (`AdjudicationRegistry.sol:93`). Duplicate snapshot_commitment anchors
  fail loudly with `"PoAd: already recorded"` revert — exactly the right
  behavior since `corpus_snapshot_log` already enforces local UNIQUE on
  the same hash (V1).
- View functions for ZK-SEPPROOF binding already exist:
  - `isRecorded(bytes32 poadHash) external view returns (bool)`
    (`AdjudicationRegistry.sol:106-108`) → ZK-SEPPROOF can confirm "this
    snapshot was anchored."
  - `getSourceType(bytes32 podHash) external view returns (string memory)`
    (`AdjudicationRegistry.sol:111-113`) → ZK-SEPPROOF can confirm the
    anchored hash was a corpus-snapshot specifically (not a different VAPI
    primitive).
- Emits `AdjudicationAnchoredV2(bytes32 indexed podHash, string sourceType,
  uint256 blockNumber)` (`AdjudicationRegistry.sol:37-41`) — indexed podHash
  enables efficient log queries; sourceType filter possible client-side.

**Owner verification (on-chain RPC)**: I called `eth_call` to selector
`0x8da5cb5b` (`owner()`) on `0x44CF981f46a52ADE56476Ce894255954a7776fb4`
this session. Result:

```
0x0000000000000000000000000cf36db57fc4680bcdfc65d1aff96993c57a4692
```

Decoded: `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` — **the active bridge
wallet** per CLAUDE.md "Active wallet (bridge + deployer)". The bridge has
`onlyOwner` access already; no transfer-of-ownership transaction needed.

### Candidate B: extend CeremonyAuditRegistry (existing, deployed)

**Contract code** at `contracts/contracts/CeremonyAuditRegistry.sol`. Struct
`CeremonyParticipant` (lines 22-27):

```solidity
struct CeremonyParticipant {
    bytes32 ceremonyId;
    bytes32 circuitName;
    address participantAddress;
    bytes32 contributionHash;
    uint256 registeredAt;
}
```

The struct is **ceremony-participant-shaped**: ceremonyId, circuitName,
participantAddress, contributionHash. None of these map cleanly to a corpus
snapshot. To use this contract, you would have to either add a new function
(contract upgrade required, no upgrade pattern available — non-upgradeable
contract per OpenZeppelin Ownable) or shoe-horn corpus state into the
participant fields with semantics that don't match the field names. Both
options are wrong.

**Reject Candidate B**: shape mismatch. CeremonyAuditRegistry is for ZK
ceremony participant tracking, not arbitrary hash anchoring.

### Candidate C: deploy new CorpusSnapshotRegistry.sol

**Cost** (estimated from prior phase deploy economics in CLAUDE.md and
deploy script comments): contract deploy ~0.10–0.15 IOTX. Plus the
ongoing per-anchor cost (~0.0001 IOTX per call at ~80k gas).

**Reject Candidate C unless A is infeasible**: deploying a new contract
adds a new address to track, a new wallet ownership invariant, a new
Hardhat test file, and additional CLAUDE.md / deploy-addresses update
overhead. AdjudicationRegistry already provides every primitive
(`isRecorded`, `getSourceType`, anti-replay, source-attributed event)
that ZK-SEPPROOF will need. A new contract reproduces those primitives
with no functional gain.

### Recommendation

**Option A** is correct with code-level evidence. The bridge calls
`anchorAdjudication(bytes32, string)` on the existing AdjudicationRegistry
contract with `sourceType="CORPUS_SNAPSHOT"`. Zero contract change. Zero
deploy cost. Existing access control + anti-replay + ZK-SEPPROOF view
primitives all reusable without modification.

The implementation phase needs ONE new function in `chain.py`
(`anchor_corpus_snapshot`), parallel to `record_adjudication` but
targeting the 2-arg `anchorAdjudication` ABI with sourceType
`"CORPUS_SNAPSHOT"`.

---

## V-Wallet — Live wallet balance (for D1/D2 economic analysis)

**Live RPC query** this session to `eth_getBalance` for
`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` against
`https://babel-api.testnet.iotex.io`:

```
result: 0x100bb888531aea000
decoded: 18.4995 IOTX
```

The prompt cites "approximately 20.432 IOTX as of 2026-04-14"; live value
is **18.4995 IOTX as of 2026-04-26**. ~1.94 IOTX has been spent in 12 days.
This is documented as a follow-up reconciliation in the Phase 238 commit
notes; not blocking for Phase 237.5.

At ~80k gas for `anchorAdjudication` (matching `record_adjudication`'s
80k budget per `chain.py:2521`), and IoTeX testnet gas price of ~1 gwei,
the per-anchor cost is approximately:
- 80,000 gas × 1 gwei × 10⁻⁹ = 0.00008 IOTX per call.

At V2's actual snapshot frequency (operator-triggered only, low frequency),
the daily IOTX burn is negligible. Even at one snapshot per minute (which
exceeds documented use), 1,440 calls/day × 0.00008 = ~0.115 IOTX/day —
~160 days of grind funded from current balance.

**Wallet balance does not constrain Phase 237.5's design choices.**

---

## Summary: V1–V5 ground truth

| Question | Finding | Implication for design |
|---|---|---|
| V1 | `tx_hash` and `on_chain_confirmed` are NOT NULL with safe defaults; insert function accepts both as parameters; UNIQUE on `snapshot_commitment` | Anchor wiring can pass `tx_hash` and `True` directly to `insert_corpus_snapshot` on success. No UPDATE pattern needed for synchronous anchor. |
| V2 | Endpoint hardcodes `on_chain_confirmed=False, tx_hash=""` at `operator_api.py:7494-7496`. Triggered manually, not autonomously. | Two-line change: replace hardcoded values with anchor result. No new agent or scheduler needed. |
| V3 | Comment says "config-gated and not auto-fired here ... separate operator action." Pure scope-deferral, no architectural prohibition. | Phase 237.5 has no precursor concern to resolve. |
| V4 | `record_adjudication` (chain.py:2487) is the structural template; `anchor_coherence` is contractually wrong shape. | New `anchor_corpus_snapshot` mirrors `record_adjudication`'s scaffolding but targets `anchorAdjudication(bytes32, string)` ABI. |
| V5 | AdjudicationRegistry already has perfect primitive (`anchorAdjudication(bytes32, string)`) with `isRecorded` + `getSourceType` views. Bridge wallet IS the contract owner (verified on-chain). | Option A: extend AdjudicationRegistry with `sourceType="CORPUS_SNAPSHOT"`. Zero contract change. |
| Wallet | Live balance 18.4995 IOTX. Per-anchor cost ~0.00008 IOTX. | Economics don't constrain frequency; cost-vs-completeness debate (per-snapshot vs milestone-only) is not a wallet question. |

Document holds for review. No design proposal follows in this file.
