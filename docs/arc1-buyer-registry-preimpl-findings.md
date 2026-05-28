# Arc 1 — VAPIBuyerRegistry: Pre-Implementation Findings (V-check)

**Date:** 2026-05-28 · **Against HEAD:** `9f8863a9` · **Mode:** read-only, no code authored

The brief assumed Arc 1 contract authoring had not yet begun. It has. The HEAD
commit `9f8863a9` already ships `VAPIBuyerRegistry.sol` + 17 Hardhat tests +
estimate-only deploy script. This V-check therefore reconciles **what is already
committed** against **the authoritative state-doc §5.2 spec**, rather than
greenfielding.

---

## Headline finding: the committed contract is built to the WRONG (superseded) spec

The committed contract follows the **framework-doc draft**, not the **state-doc
§5.2 authoritative spec**. The operator's own briefing is explicit: *"The state
doc is authoritative … Claude Code must build to the state doc spec, not the
framework doc draft."* The committed contract does the opposite.

| Surface | Committed `VAPIBuyerRegistry.sol` (`9f8863a9`) | State doc §5.2 (AUTHORITATIVE) |
|---|---|---|
| Buyer identifier | `bytes32 buyerDID` (ioID) | `address buyerAddr` (wallet) |
| Issue sig | `issueCredential(buyerDID, categoryId, evidenceHash)` | `issueCredential(buyerAddr, category, expiresAt)` |
| Categories | 4: ACADEMIC / GAME_DEV / ESPORTS / BRAND | 3: RESEARCH_ACADEMIC / BRAND_ADVERTISING / INTEGRATOR_TECHNICAL |
| Validity view | `isValidCredential(buyerDID, categoryId)` | `isAuthorizedBuyer(buyerAddr, category)` |
| Expiry | hard-coded `issuedAt + 365 days` | caller-supplied `expiresAt` |
| Re-attestation | slot permanently consumed (no re-issue) | "re-attested via re-issuance" |

**Timeline that produced the drift:** the state doc was generated against HEAD
`e75b3016` and states "`VAPIBuyerRegistry.sol` not yet authored" (§ line 223).
The contract was then authored in `9f8863a9` — but to the framework draft, not
§5.2. So §5.2 is not stale; it predates and supersedes the contract.

**Not yet deployed.** The contract is source-only / estimate-only
(`VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM=1` required to broadcast). No on-chain
broadcast has occurred. Reworking now costs nothing on-chain.

---

## Secondary finding: AuditLog wiring as briefed is architecturally mismatched

Brief step 5 says *"every issueCredential call must log to AuditLog immediately
after the credential mapping is written."* But the deployed `AuditLog.sol` is a
**batched Merkle tree-head checkpoint** anchor (`appendCheckpoint(merkleRoot,…)`),
not a per-event logger. The submission receipt itself notes BBG "does not
auto-write to AuditLog" — the proposal event lives in BBG's own event log.

Correct pattern: `VAPIBuyerRegistry` emits its own `CredentialIssued` /
`CredentialRevoked` events (it already does); AuditLog optionally anchors a
Tessera-style checkpoint over a batch of those events (state doc §6.4 item 7),
operator-fired, not per-issuance. Per-call AuditLog writes are not how the
contract works and would burn gas per credential.

---

## On-chain prerequisite status (brief steps 1 + 3)

Documentary evidence (committed `docs/governance/SUBMISSION_RECEIPT.md`):

- **Phase 4a** `AgentRegistry.updateAgentScope` — LANDED. tx `0x54a1cf31…`,
  block 44074471, scopeHash `0xd9d760c8…` → `0xab874f62…`.
- **Phase 4b** `AgentScope.setAgentScopeRoot` — LANDED. tx `0x21dcfab5…`,
  block 44074677, scopeRoot `0xd9d760c8…` → `0xab874f62…`.
- Two-layer scope byte-aligned at `0xab874f6297063fd2d43f49f272b9a95accd56b79f99ccd3d64b0ecd3a52c5b14`.
- **Governance proposalHash** `0x59fb9996…` — anchored. tx `0xba96f7cb…`,
  block 44073691, BBG totalProposals 0→1, isProposed=True.

I have NOT independently RPC-verified `scopeHash()` / `scopeRoot()` against a
live node this session (the receipt is the in-repo evidence). I can fire a
read-only RPC confirmation on request before any deploy.

---

## Naming + address-book convention (brief step 4)

- `VAPIBuyerRegistry` matches the Layer C `VAPI`-prefix convention. ✓
- `deployed-addresses.json` keys new contracts by bare PascalCase name (e.g.
  `"VAPIManufacturerDeviceRegistry": "0x2e5B…"`) with a sibling
  `"_<lowercasename>_note"` deploy-provenance string. No `VAPIBuyerRegistry`
  key exists yet (consistent with not-yet-deployed). ✓

---

## Gap list — files Arc 1 touches (post-decision)

If reworked to §5.2:
- `contracts/contracts/VAPIBuyerRegistry.sol` — rewrite (addr identifier, 3-cat, caller expiresAt, isAuthorizedBuyer, re-issuance path).
- `contracts/test/VAPIBuyerRegistry.test.js` — rewrite 17 tests to new ABI.
- `contracts/scripts/deploy-vapi-buyer-registry.js` — adjust (cost estimate will shift slightly).
- `deployed-addresses.json` — new key + note (post-deploy).
- Bridge: `is_authorized_buyer` / `get_buyer_category` / `list_credentials` (commit 2).
- Config + PV-CI `INV-BUY-001` (category/ABI freeze) — **not yet pinned anywhere**; NatSpec references it as if it exists. (commit 2)
- `curator_attestation.py` + `POST /curator/attest-buyer` (commit 3).

---

## DECISION REQUIRED (V-check hold)

The committed contract diverges from the authoritative spec. Two paths:

- **A — Rework to §5.2** (what the briefing instructs): rewrite contract +
  tests + script to `buyerAddr` / 3 categories / `isAuthorizedBuyer` /
  caller `expiresAt` / re-issuance. Supersede `9f8863a9` with a new commit.
- **B — Ratify the framework-draft spec** as committed: the prior session's
  `bytes32 buyerDID` / 4-category design stands; update state doc §5.2 to match
  instead. (Only if the operator deliberately chose the DID design.)

Holding for operator decision before any code is authored.
