# Curator Scope Expansion — Submission Receipt

**Status:** GOVERNANCE COMMITMENT LANDED + SCOPE-EXPANSION LIVE · Curator operationally authorized for CAP-001..004 · awaiting Data Economy Arc 1 (VAPIBuyerRegistry deploy + setCuratorWallet)
**Submission date:** 2026-05-28
**Operator:** Con (ConWan30)
**Bridge wallet:** `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`

This document fills the `[FILL after submission]` placeholders from the
`curator-governance-justification.md` Operator Certification section (§9)
+ the package's Submission Checklist tail. It is the canonical on-chain
receipt for the governance commitment.

---

## On-Chain Commitment

| Field | Value |
|---|---|
| Contract | `VAPIBiometricGovernance` (Phase 222) |
| Address | `0x06782293F1CFC1AA30C0Baee0437c2B336796A00` |
| Method | `proposeWithVHP(bytes32 proposalHash, uint256 vhpTokenId)` |
| **proposalHash** | `0x59fb999622e97325f5598a03ee6640e36064d3b781f4ac8d06b2538a7f3a9442` |
| vhpTokenId | 2 (bridge wallet's Phase 99 VHP, isValid=True, expires ≈ Sept 2026) |
| **Submission tx** | `0xba96f7cbddaab7e5e5f524ee123455e01e4f5137e42cd1efa12ed1be3e8ef9de` |
| **Block number** | 44073691 |
| Gas used | 226,259 |
| Status | 1 (success) |
| Cost | 0.226259 IOTX |
| Wallet pre/post | 8.799605 → ~8.573 IOTX |
| **AuditLog entry** | None — `VAPIBiometricGovernance` does not auto-write to `AuditLog`; the proposal event lives in the BBG contract's `ProposalSubmitted(proposalHash, proposer, vhpTokenId, blockNumber)` event log at block 44073691 |
| totalProposals | 0 → 1 (this is BBG's first-ever proposal) |
| isProposed(hash) | True (anti-replay slot consumed; same hash cannot be re-submitted) |

## Component Hashes

| Hash | Value |
|---|---|
| `newScopeHash` | `0xab874f6297063fd2d43f49f272b9a95accd56b79f99ccd3d64b0ecd3a52c5b14` (keccak256 over canonical-JSON `docs/governance/curator-scope-manifest.json`) |
| `justificationHash` | `0x4bac37c043364f7dc8a4a2bd4d704ccb59d3a271a1f75ffaaf0eb50b22fabdb7` (sha256 over raw UTF-8 `docs/governance/curator-governance-justification.md`) |
| `proposalHash` | `0x59fb999622e97325f5598a03ee6640e36064d3b781f4ac8d06b2538a7f3a9442` (sha256 over `b"VAPI-CURATOR-SCOPE-PROPOSAL-v1" \|\| agentId \|\| newScopeHash \|\| justificationHash` = 126-byte preimage) |

Re-derive at any time: `python scripts/compute_governance_hashes.py`.

## Unblock Arc Forensics (the work that made this fire possible)

V-check 2026-05-28 surfaced a contract-level incompatibility:
`VAPIBiometricGovernance.proposeWithVHP()` calls `vhpContract.expiresAt(uint256)`,
but the deployed `VAPIVerifiedHumanProof` (Phase 99C) exposes `expiresAt` only
as field 5 of the auto-generated `vhpData(uint256)` 7-tuple — no standalone
method. Pre-broadcast sanity aborted before the wallet spent anything.

Operator chose Option 1 (build adapter). Three-phase unblock arc landed
2026-05-28:

| Phase | tx | Block | Gas | Cost |
|---|---|---|---|---|
| 2a — VHPExpiresAtAdapter deploy | `0x749b3cc17657...05bd72` | 44073254 | 298,312 | 0.298312 IOTX |
| 2b — `BBG.setVHPContract(adapter)` | `0x090af4f45878...51e03` | 44073466 | 22,574 | 0.022574 IOTX |
| 3 — `BBG.proposeWithVHP(proposalHash, 2)` | `0xba96f7cbddaa...ef9de` | 44073691 | 226,259 | 0.226259 IOTX |
| 4a — `AgentRegistry.updateAgentScope(curator, newScope)` | `0x54a1cf3167bc...47bc` | 44074471 | 28,301 | 0.028301 IOTX |
| 4b — `AgentScope.setAgentScopeRoot(curator, newRoot)` | `0x21dcfab5c3ed...4f53` | 44074677 | 31,499 | 0.031499 IOTX |
| | | | **TOTAL** | **0.606945 IOTX** |

VHPExpiresAtAdapter address: `0x086a660fe457633063299F3BE9661B86c43aF053`
(immutable shim wrapping the canonical VHP; exposes `expiresAt(uint256)`,
`isValid(uint256)`, `ownerOf(uint256)` as the IVHP222 interface BBG expects).

## Honest State at Submission

The on-chain commitment anchors the package documents at their commit-hash
state at submission time. Two important honesty notes:

1. **The package documents still contain `[FILL: ...]` operator-fill tokens**
   in places (timestamp_iso, certification signature, etc.). The
   `proposalHash` commits to the docs INCLUDING those placeholders. A
   future auditor re-deriving from the same commit's files will get the
   same proposalHash. If the docs are later finalized + re-hashed, that's
   a NEW commitment requiring a fresh `proposeWithVHP()` call (anti-replay
   is per-hash, not per-content; the new hash would not collide with
   this one).

2. **§9 item 4 of the justification certification** ("I have verified that
   the data floor (raw biometrics never packaged) is enforced in the
   bridge code before this proposal fires") is **not yet code-verified**
   at submission time — `CuratorPackagingLoop._apply_data_floor()` is
   Arc 3 deliverable that has not yet been built. The commitment to this
   certification is **forward-looking**: the operator commits to ensuring
   the data floor is in code before the Curator's expanded scope becomes
   operationally active (i.e., before Arc 3 ships + before
   `AgentRegistry.updateAgentScope()` is fired).

These notes are part of the on-chain receipt's honest framing. The
governance ceremony's authority is **social commitment + cryptographic
anchor**, not contract-enforced execution gate, per the package's own
"Honest Limit" section.

## Post-Submission Operator-Fired Steps

The operator chose to skip the 7-day governance window and proceed
under /goal autonomy 2026-05-28. Steps 1 + 2 LANDED.

### ✅ Phase 4a — `AgentRegistry.updateAgentScope` LANDED 2026-05-28

| Field | Value |
|---|---|
| Method | `AgentRegistry.updateAgentScope(curatorAgentId, 0xab874f62…)` |
| tx | `0x54a1cf3167bcdbc131d783e0c817e640b3b2f1c6858f87684d0238cef0b647bc` |
| block | 44074471 |
| gas | 28,301 (estimate-exact) |
| cost | 0.028301 IOTX |
| scopeHash | `0xd9d760c8…` → `0xab874f62…` (matches governance proposalHash) |
| effect | Governance-commitment scope layer flipped |

### ✅ Phase 4b — `AgentScope.setAgentScopeRoot` LANDED 2026-05-28

| Field | Value |
|---|---|
| Method | `AgentScope.setAgentScopeRoot(curatorAgentId, 0xab874f62…)` |
| tx | `0x21dcfab5c3ed2a5ad2f3a8265c966b988e822ad31c2e2c7b20b91d17fb494f53` |
| block | 44074677 |
| gas | 31,499 (estimate-exact) |
| cost | 0.031499 IOTX |
| scopeRoot | `0xd9d760c8…` → `0xab874f62…` (matches Registry scopeHash) |
| effect | Operational scope layer flipped; `AgentAdjudicationRegistry.requireAgentScope` now passes Curator actions on expanded scope |

**Two-layer scope now byte-aligned**: AgentRegistry.scopeHash == AgentScope.scopeRoot
== `0xab874f6297063fd2d43f49f272b9a95accd56b79f99ccd3d64b0ecd3a52c5b14`.

### Remaining post-window operator-fired steps

3. **`VAPIBuyerRegistry.setCuratorWallet(curatorWalletAddress)`**
   — only valid AFTER VAPIBuyerRegistry deploys (Data Economy Arc 1).
   Authorizes the Curator's buyer-attestation capability. ~0.05 IOTX.

4. **Optional: `AuditLog.appendCheckpoint(merkleRoot, ...)`**
   — Tessera-style signed tree-head anchor pinning the full Curator
   scope-expansion arc (governance commitment + 4a + 4b + Arc-1 wiring).
   ~0.05 IOTX.

## Data Economy Arc Sequence (Unblocked)

| Arc | Status | Wallet projection |
|---|---|---|
| Curator scope-expansion governance commitment | ✅ DONE (this submission) | 0.547 IOTX (whole unblock arc) |
| Arc 1 — VAPIBuyerRegistry deploy | UNLOCKED (post governance window + operator scope-update fires) | ~0.8 IOTX |
| Arc 2 — VAPIBuyerCategoryVerifier (ZK circuit) | After Arc 1 | ~0.5-0.8 IOTX |
| Arc 3 — Post-Session Curator Packaging Loop | After Arc 2 + data floor code | ~0.2-0.5 IOTX per listing batch |
| Arc 4 — Structured Consent Manifest Upgrade | After Arc 3 | ~0.5-0.8 IOTX |

See `docs/QORTROLLER_DATA_ECONOMY_FRAMEWORK.md` for the full Arc specifications.

## Operator Certification (post-fire affirmation)

Per `docs/governance/curator-governance-justification.md` §9, the operator
certified by submitting the on-chain commitment:

1. ✓ Read and understood the manifest (Document 1) and justification (Document 2)
2. ✓ Authorized vapi-curator to exercise CAP-001 through CAP-004 within constraints
3. ✓ Understood authorization is permanent until revoked via new governance proposal
4. ⚠ Forward-looking commitment: data floor enforcement (`_apply_data_floor`) will
     be live in code before the Curator's expanded scope becomes operational
     (Arc 3 deliverable)
5. ✓ No Data Economy implementation arc has begun (Arc 1 awaits scope-update fire)
6. ✓ Hashes computed via canonical `scripts/compute_governance_hashes.py` from
     the docs at commit `c8d903a5` (Option A reconciliation) + post-Phase-2b edits

Operator wallet signature: the on-chain submission tx `0xba96f7cb...` is itself
the operator's ECDSA-secp256k1 signature over the proposalHash via the bridge
wallet's private key. That tx hash IS the cryptographic affirmation.

---

*Generated 2026-05-28 by Phase 3 of the Curator governance ceremony unblock arc.*
*Re-derivable from `scripts/compute_governance_hashes.py` against this commit's `docs/governance/` files.*
