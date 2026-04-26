# Phase 237.5 — CORPUS-SNAPSHOT On-Chain Anchoring

**Date**: 2026-04-26
**Status**: COMPLETE
**Encoding**: phase 237.5 (decimal); wiki engine integer encoding `2375`
**Provenance**: [VAPI:Phase2375:MEMORY.md:MEASURED]

## Summary

Closes the architectural gap surfaced by the Phase 237-ZK-SEPPROOF
verification: `force-corpus-snapshot` was hardcoding `on_chain_confirmed=False`
and `tx_hash=""` at `bridge/vapi_bridge/operator_api.py:7494-7496`. The
corpus_snapshot_log schema fields existed (`store.py:3279-3306`) but no
chain wrapper wrote them, leaving any future ZK-SEPPROOF binding to
corpus state with a database-only foundation.

Phase 237.5 wires the existing `AdjudicationRegistry.anchorAdjudication(
bytes32 podHash, string sourceType)` primitive to the corpus snapshot
path with `sourceType="CORPUS_SNAPSHOT"`. Zero contract change. Zero
deploy cost. Bridge wallet is already the contract owner (verified via
on-chain `eth_call` to selector `0x8da5cb5b` returning the active wallet
address `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`).

## Architectural decision

**Reuse `AdjudicationRegistry`** at `0x44CF981f46a52ADE56476Ce894255954a7776fb4`
(Phase 111 LIVE per `contracts/deployed-addresses.json:76-78`):
- `anchorAdjudication(bytes32 podHash, string sourceType)` at
  `contracts/contracts/AdjudicationRegistry.sol:79-99`.
- Open-enum `sourceType` (line 96 stores any string).
- Anti-replay built in (`AdjudicationRegistry.sol:93`: `require(!poadRecorded[
  podHash], "PoAd: already recorded")`).
- ZK-SEPPROOF view primitives ready: `isRecorded(bytes32)` (`:106-108`),
  `getSourceType(bytes32)` (`:111-113`).
- Event: `AdjudicationAnchoredV2(bytes32 indexed podHash, string sourceType,
  uint256 blockNumber)` (`:37-41`).

Verification + design references:
- `wiki/proposals/PHASE_237_5_VERIFICATION.md` — V1–V5 with file:line citations
- `wiki/proposals/PHASE_237_5_DESIGN.md` — D1–D5 reasoning + 4-section design

## Files modified

| File | Change |
|---|---|
| `bridge/vapi_bridge/chain.py` | NEW `async def anchor_corpus_snapshot(snapshot_commitment_hex) -> tuple[str \| None, bool]` inserted after `record_adjudication` (`:2529`). Mirrors record_adjudication scaffolding. **Legacy `record_adjudication` path UNAFFECTED.** |
| `bridge/vapi_bridge/operator_api.py` | Refined order in `force_corpus_snapshot` endpoint: compute → anchor → insert with populated result. Comment block at `:7430-7440` rewritten. `tx_hash` field added to response. |
| `bridge/tests/test_phase237_5_corpus_anchor.py` | NEW. 5 tests T237.5-1..5. |
| `scripts/vapi_invariant_gate.py` | INV-CORPUS-001 (anchor_corpus_snapshot signature), INV-CORPUS-002 (`"CORPUS_SNAPSHOT"` literal). 26 → 28 invariants. |
| `.github/INVARIANTS_ALLOWLIST.json` | Regenerated via `--generate --reason "invariant_change: corpus snapshot on-chain anchor contract is itself a protocol invariant" --confirm-governance`. 28 entries. |
| `monitoring/skill14_phase237_5.json` | Skill 14 sweep output. Verdict: PASS. |

## Order of operations (Commit 2 refinement)

```python
# Phase 237.5: anchor FIRST so the insert can record the live result in one call.
tx_hash_hex, anchored = await chain.anchor_corpus_snapshot(commitment.hex())

row_id = await asyncio.to_thread(
    store.insert_corpus_snapshot,
    commitment.hex(), wiki_hash.hex(), agent_root.hex(),
    ratio, corpus_n, ts_ns, _reason,
    bool(anchored),         # on_chain_confirmed (was hardcoded False)
    tx_hash_hex or "",      # tx_hash (was hardcoded "")
    "",                     # ipfs_cid (still deferred)
)
```

This refinement removes the post-insert UPDATE pattern; no
`update_corpus_snapshot_anchor` store method needed. Anchor failure →
graceful insert with `(tx_hash="", on_chain_confirmed=False)`.

## Tests

```
T237.5-1: anchor_corpus_snapshot returns (None, False) when adjudication_registry_address is empty
T237.5-2: anchor_corpus_snapshot returns (None, False) on bad commitment hex (no raise)
T237.5-3: anchor_corpus_snapshot success path returns (tx_hex, True)
T237.5-4: 'PoAd: already recorded' revert treated as idempotent (None, False)
T237.5-5: ZK-SEPPROOF binding feasibility — round-trip via mocked isRecorded + getSourceType
```

Result: **5/5 passing** (`bridge/tests/test_phase237_5_corpus_anchor.py`,
0.27s).

## ZK-SEPPROOF binding feasibility

Per `PHASE_237_5_DESIGN.md` Section 4, the anchor format satisfies four
binding requirements for the eventual ZK-SEPPROOF design phase:

1. **On-chain availability**: `AdjudicationRegistry.isRecorded(commitment)`
   returns `true` after Phase 237.5 anchor.
2. **Sub-protocol isolation**: `getSourceType(commitment)` returns
   `"CORPUS_SNAPSHOT"`, distinguishing this anchor from
   `recordAdjudication`-shaped PoAd hashes.
3. **Block-anchored timestamp**: `AdjudicationAnchoredV2` event emits
   `block.number` as indexed parameter, providing temporal anchor
   semantics matching the Phase 67 ceremony beacon precedent.
4. **Field-element compatibility** (deferred to ZK-SEPPROOF design): the
   32-byte commitment requires one mod-reduction step into BN254's
   254-bit scalar field. Phase 237.5 does not constrain the chosen
   reduction strategy; the on-chain hash byte-for-byte equals the
   database hash.

When the touchpad_corners breakthrough lands and an operator fires
`force-corpus-snapshot` at that moment, the snapshot commitment is
anchored on IoTeX testnet in real-time. The ZK-SEPPROOF design phase
finds the binding foundation already in place.

## Test counts

| Component | Before | After | Delta |
|---|---|---|---|
| Bridge | 2510 | 2515 | +5 |
| Autoresearch | 7 | 7 | 0 |
| SDK | 539 | 539 | 0 |
| Hardhat | 528 | 528 | 0 |
| PV-CI invariants | 26 | 28 | +2 (INV-CORPUS-001, INV-CORPUS-002) |
| Contracts LIVE | 46 | 46 | 0 (no new deploy) |

## Wallet impact

- Live balance pre-Phase 237.5: 18.4995 IOTX (verified via `eth_getBalance`)
- Per-anchor cost: ~0.00008 IOTX (100,000 gas at ~1 gwei)
- Daily burn at operator-triggered frequency: <0.001 IOTX
- Effective balance pre-Phase 237.5 = effective balance post-Phase 237.5
  (deploy cost zero; per-anchor cost negligible)

## What this phase does NOT do

- Does NOT modify the FROZEN-v1 CORPUS-SNAPSHOT hash formula
  (`corpus_snapshot.py:25-37` untouched)
- Does NOT add an autonomous snapshot trigger (operator-triggered
  remains the implicit milestone-only filter)
- Does NOT add wallet-balance pre-check (Phase 237.5.1 candidate;
  out of scope per ≤200 LOC)
- Does NOT add anchor-retry background task (synchronous chosen)
- Does NOT add a new contract (existing AdjudicationRegistry sufficient)
- Does NOT modify `record_adjudication` (legacy Phase 112 path explicit-untouched)

## Inaugural anchor (operator action, post-deploy)

After bridge restart:

```bash
curl.exe -sS -X POST "http://127.0.0.1:8080/operator/operator/force-corpus-snapshot?api_key=vapi-dev-local&reason=Phase%20237.5%20inaugural%20CORPUS_SNAPSHOT%20anchor%20activation"
```

Expected response: `tx_hash` non-empty (real hex), `on_chain_confirmed: true`,
`row_id > 0`.

Inaugural `tx_hash`: TBD — fills in via follow-up doc commit after the
first post-deploy snapshot fires.

## Verification artifacts

- Skill 14 sweep: `monitoring/skill14_phase237_5.json` (verdict CLEAN)
- Wiki sweep page: `wiki/sweeps/sweep_20260426_clean.md`
- Wiki briefs: `wiki/briefs/brief_MEMORY.md_2375.md`,
  `wiki/briefs/brief_VAPI_WHAT_IF.md_2375.md`
- Phase_close snapshot SHA-256: `2e174075db7b...`
- PV-CI gate: 28/28 PASS (post `--generate`)
- Bridge regression: 22/22 PASS across Phase 237.5 + 236 corpus_snapshot + 112 poad

## References

- Phase 236-CORPUS-SNAPSHOT: `wiki/phases/phase_236.md`
- Phase 237-ZK-SEPPROOF verification: `wiki/proposals/PHASE_237_ZK_SEPPROOF_VERIFICATION.md`
- Phase 237.5 verification: `wiki/proposals/PHASE_237_5_VERIFICATION.md`
- Phase 237.5 design: `wiki/proposals/PHASE_237_5_DESIGN.md`
- AdjudicationRegistry contract: `contracts/contracts/AdjudicationRegistry.sol`
- AdjudicationRegistry deployed: `0x44CF981f46a52ADE56476Ce894255954a7776fb4`
