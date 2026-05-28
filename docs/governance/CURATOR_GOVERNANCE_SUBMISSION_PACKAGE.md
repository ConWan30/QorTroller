# Curator Scope Expansion — Governance Submission Package
## VAPIBiometricGovernance Proposal
**Agent:** vapi-curator · **On-chain ID:** 0xed6a2df5...
**Proposal type:** Scope expansion — O3_ACTING capability authorization
**Prepared by:** Con (ConWan30) · Architectural Collaborator synthesis
**Status:** TEMPLATE — operator fills marked fields before submission

---

## How to Use This Package

This package produces two canonical documents:

1. `curator-scope-manifest.json` — machine-readable capability enumeration.
   Hashed with keccak256. Submitted as `newScopeHash`.

2. `curator-governance-justification.md` (this document below section break).
   Hashed with SHA-256. Submitted as `justificationHash`.

The hashes commit the protocol to exactly what is being authorized. A future
auditor re-derives both hashes from these files and verifies they match the
on-chain proposal. Any deviation means the authorization was tampered with.

### Canonical Hash Computation

The actual `scripts/compute_governance_hashes.py` shipped in the repo
implements the canonical hash computation + the on-chain submission template.
Run it after finalizing both governance documents:

```bash
python scripts/compute_governance_hashes.py
```

The script produces three hashes (all bytes32):

| Hash | Formula | Use |
|---|---|---|
| `newScopeHash` | `keccak256(canonical_json(manifest))` | off-chain commitment to the scope manifest content |
| `justificationHash` | `sha256(raw_utf8(justification.md))` | off-chain commitment to the justification document |
| `proposalHash` | `sha256(b"VAPI-CURATOR-SCOPE-PROPOSAL-v1" \|\| agentId \|\| newScopeHash \|\| justificationHash)` — 126-byte preimage → 32 bytes | the single on-chain commitment submitted via `proposeWithVHP` |

### On-Chain ABI Reality Check (V-check finding 2026-05-28)

The deployed `VAPIBiometricGovernance` (Phase 222, address
`0x06782293F1CFC1AA30C0Baee0437c2B336796A00`) does **NOT** expose
`submitProposal(agentId, newScopeHash, justificationHash, duration)`. The
real on-chain method is:

```solidity
function proposeWithVHP(bytes32 proposalHash, uint256 vhpTokenId) external nonReentrant;
```

The contract takes a single opaque commitment + a VHP-gated proposer
identity (msg.sender must own the soulbound VHP). The structured shape
of the proposal (agentId, scopeHash, justificationHash) is enforced
**off-chain** — anyone re-deriving the proposalHash from the three component
hashes can verify the on-chain commitment matches the documents in this
package.

The bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` holds the
required VHP at `tokenId = 2` (Phase 99 demo mint, `isValid = True`).
That is the `vhpTokenId` argument.

### Submission Template (verified against deployed ABI)

After running `compute_governance_hashes.py`, submit via:

```
VAPIBiometricGovernance.proposeWithVHP(
    proposalHash = bytes32(0x<proposalHash from script output>),
    vhpTokenId   = 2  // bridge wallet's Phase 99 VHP
)
```

**Critical:** Run the hash script AFTER finalizing both documents. Any edit
to either document changes its hash and invalidates the proposalHash. Any
edit AFTER on-chain submission means future auditors will detect the
mismatch when they re-derive the hash from the post-edit file. Finalize -->
hash --> submit. **Never** submit --> edit.

### Honest Limit: On-Chain Enforcement vs Social Commitment

The Phase 222 governance contract's role is to anchor a VHP-gated
commitment to the proposalHash. It does **NOT** contract-enforce the
subsequent scope-expansion action. Specifically:

- `AgentRegistry.updateAgentScope(agentId, newScopeHash)` is `onlyOwner`
  (bridge wallet) — the operator can call it without any governance
  proposal at all.
- `AgentScope.setAgentScopeRoot(agentId, scopeRoot)` is also `onlyOwner`.

The governance ceremony's authority is therefore **social + cryptographic**:
the operator publicly commits to the proposal (via on-chain VHP-gated
proposalHash) before executing the scope change. Honoring the commitment
is the operator's discipline; the smart contract trusts the operator
to follow through. A future Phase 222.v2 could close this loop by gating
`updateAgentScope` on a passed governance proposal — that is a separate
arc, not part of this expansion.

---

# Document 1: Scope Manifest
## File: `docs/governance/curator-scope-manifest.json`
## Hash: keccak256(canonical_bytes) → `newScopeHash`

```json
{
  "version": "1.0",
  "manifestType": "AGENT_SCOPE_EXPANSION",
  "timestamp_iso": "[FILL: ISO 8601 timestamp at finalization]",
  "agent": {
    "name": "vapi-curator",
    "onChainId": "0xed6a2df5...",
    "registryContract": "AgentRegistry",
    "currentPhase": "O3_ACTING",
    "executorStatus": "DISABLED_TWO_KEY_GATE"
  },
  "currentScope": [
    "marketplace_monitoring",
    "tier_drift_monitoring",
    "consent_monitoring",
    "listing_observation",
    "dispute_flagging_advisory"
  ],
  "addedCapabilities": [
    {
      "id": "CAP-001",
      "name": "buyer_attestation",
      "description": "Issue and revoke buyer credentials in VAPIBuyerRegistry on behalf of the protocol",
      "contract": "VAPIBuyerRegistry",
      "methods": ["issueCredential", "revokeCredential"],
      "constraints": [
        "Requires off-chain documentation review before issuance",
        "Every issuance logged to AuditLog on-chain",
        "Credentials expire in 365 days and require re-attestation",
        "CATEGORY_BRAND issuance requires explicit secondary operator confirmation"
      ]
    },
    {
      "id": "CAP-002",
      "name": "post_session_packaging",
      "description": "Read local bridge.db post-session and prepare ZK proof packages per gamer consent manifest",
      "contract": "none (local bridge operation)",
      "methods": ["CuratorPackagingLoop.on_session_complete"],
      "constraints": [
        "Raw biometric data (Mahalanobis vectors, force curves, IMU, HID frames) NEVER packaged — protocol invariant",
        "Consent manifest hash verified against VAPIConsentRegistry on-chain before every session",
        "Aggregation floor enforced: min 10 sessions per package (non-bypassable)",
        "Cooling period enforced: min 72 hours post-session (non-bypassable)",
        "Autonomy level default: approval_required — never initialize as full_autonomy",
        "Fail-closed on consent manifest mismatch: abort packaging, log error"
      ]
    },
    {
      "id": "CAP-003",
      "name": "marketplace_listing",
      "description": "Submit ZK proof package listings to VAPIDataMarketplace on gamer's behalf",
      "contract": "VAPIDataMarketplace",
      "methods": ["createListing", "cancelListing"],
      "constraints": [
        "Only lists packages that passed full consent manifest enforcement",
        "Every listing includes consent_policy_hash field (auditable)",
        "Listing requires gamer approval if autonomy_level = approval_required (default)",
        "Revenue routing: 80% gamer wallet, 15% protocol treasury, 5% Curator operational budget",
        "CHAIN_SUBMISSION_PAUSED respected — no listings submitted when kill-switch active"
      ]
    },
    {
      "id": "CAP-004",
      "name": "behavioral_anomaly_monitoring",
      "description": "Monitor buyer purchasing patterns on-chain and flag anomalies for slashing review",
      "contract": "AgentSlashing (propose only, not execute)",
      "methods": ["proposeSlashing (advisory — governance executes)"],
      "constraints": [
        "Curator PROPOSES slashing events — VAPIBiometricGovernance executes",
        "Curator cannot execute slashing autonomously (governance gate preserved)",
        "Every anomaly flag logged to AuditLog with evidence hash",
        "False-positive slashing proposals do not punish buyer until governance confirms"
      ]
    }
  ],
  "invariantsPreserved": [
    "228-byte PoAC wire format: UNCHANGED",
    "13 FROZEN PATTERN-017 families: UNCHANGED",
    "35 PV-CI invariants: unchanged (data economy arcs add new ones, not modify existing)",
    "VAPIPoEPRegistry gamer-sovereign model: UNCHANGED",
    "Curator cannot self-expand authority beyond this manifest without new governance proposal",
    "Operator two-key gate for Curator executor: PRESERVED (Curator submits txs via bridge wallet, not independent key)",
    "Data floor (raw biometrics never packaged): PROTOCOL INVARIANT enforced in code",
    "CHAIN_SUBMISSION_PAUSED kill-switch: respected by all new capabilities"
  ],
  "rollbackMechanism": {
    "method": "VAPIBiometricGovernance.revokeScope(agentId, capabilityIds[])",
    "effect": "VAPIBuyerRegistry.curatorWallet set to address(0) — Curator cannot attest buyers",
    "packageLoopEffect": "curator_packaging_enabled flag set False in config — loop disabled at next restart",
    "marketplaceEffect": "Existing listings remain; new listing capability revoked",
    "timeToEffect": "One bridge restart after config flag propagates",
    "auditTrail": "Revocation tx hash anchored on AuditLog"
  },
  "governanceWindowDays": 7,
  "requiredSignatures": 1,
  "signatoryAddress": "[FILL: operator wallet address]"
}
```

**Important:** Before computing `keccak256` of this file, ensure it is
serialized as canonical JSON: `json.dumps(manifest, sort_keys=True, separators=(',',':'))`.
Whitespace differences produce different hashes.

---

# Document 2: Governance Justification
## File: `docs/governance/curator-governance-justification.md`
## Hash: SHA-256(UTF-8 bytes) → `justificationHash`

---

## QorTroller Curator Scope Expansion — Governance Justification
### Proposal for VAPIBiometricGovernance

**Date:** [FILL: ISO 8601 date at finalization]
**Operator:** Con (ConWan30) · Bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
**Protocol state at submission:**
- Contracts live: 51 (IoTeX testnet, chain 4690)
- Frozen primitives: 13 PATTERN-017 families
- PV-CI invariants: [FILL: current count at submission]
- GIC chain: GIC_100 reached · PoAC records: 637K+
- AIT separation ratio: 1.199 (N=37, all pairs above 1.0)
- Operator fleet: O3_ACTING (Sentry / Guardian / Curator)

---

### 1. Executive Summary

This proposal requests authorization for the vapi-curator agent to expand
its operational scope from passive marketplace monitoring to active
marketplace participation — specifically: buyer credential attestation,
post-session ZK proof packaging on behalf of gamers, and marketplace
listing submission within gamer-defined consent boundaries.

The expansion does not change the Curator's identity, on-chain registration,
or cryptographic keys. It expands what the Curator is authorized to do with
its existing O3_ACTING authority.

This expansion is the governance gate that makes the QorTroller Gamer-
Sovereign Data Economy operational. It is the correct sequencing: a human
governance ceremony authorizes Curator's expanded authority before any
code arc implements it. The Curator cannot self-authorize this expansion.
That constraint is the architectural feature being honored here.

---

### 2. The Architectural Basis — Why This Is Not a New System

The data economy built by this expansion does not bolt a marketplace onto
an anti-cheat protocol. It extracts value from what the anti-cheat protocol
already produces.

The PITL stack, the PoAC chain, the 228-byte tamper-evident records, the
AIT separation ratio, the VHP renewal proofs — every layer built to prove
a live human is on a certified controller — simultaneously produces the
most credible human behavioral dataset in competitive gaming. The proof
of humanity IS the data provenance.

The Curator's expanded role is to package this existing production output
into sovereign, consent-gated, buyer-verified ZK proofs and list them on
the already-deployed VAPIDataMarketplace. The protocol's existing proof
infrastructure (PitlSessionProofVerifier, VAPIConsentRegistry) handles
the work. The Curator orchestrates it within strict consent boundaries.

Reference: `docs/QORTROLLER_DATA_ECONOMY_FRAMEWORK.md` — the complete
technical specification for all four implementation arcs that follow this
governance ceremony. That document is the engineering basis for this proposal.

---

### 3. Current Curator State — What Is Being Expanded From

**Current authorized scope:**
- Marketplace monitoring: observing listings, flagging anomalies (advisory)
- Tier-drift monitoring: watching player tier changes for protocol health
- Consent monitoring: verifying gamer consent records are current

**Current limitations:**
- Cannot issue buyer credentials
- Cannot package post-session data
- Cannot submit marketplace listings
- Cannot execute slashing (advisory only — already correct)
- Executor-disabled (two-key gate — preserved by this proposal)

The Curator is an active, O3_ACTING on-chain agent. It holds real authority.
This governance ceremony expands what that authority covers, within the
constraint inventory named in Section 5 below.

---

### 4. What Is Being Authorized — Capability by Capability

**CAP-001: Buyer Attestation**

Authorization: the Curator may issue and revoke buyer credentials in the
forthcoming VAPIBuyerRegistry contract, binding a buyer's ioID DID to a
verified category (Academic, GameDev, Esports, Brand).

Why this is safe: Every credential issuance requires off-chain documentation
review before the on-chain transaction fires. Every issuance is logged to
AuditLog (immutable on-chain record). Credentials expire annually and require
re-attestation. The operator retains override authority via `VAPIBiometricGovernance`
governance at any time. The Curator cannot issue credentials for categories
not in the FROZEN enum (INV-BUY-001).

Why the Curator is the right attestor: It already monitors the marketplace
and already has the context to identify behavioral patterns inconsistent with
claimed buyer categories. It is the most information-rich agent for this role.
The structural parallel: VAPIManufacturerDeviceRegistry has the operator attest
hardware. VAPIBuyerRegistry has the Curator attest buyers. Same trust model;
different subjects.

**CAP-002: Post-Session ZK Proof Packaging**

Authorization: the Curator may read the local bridge database post-session,
apply the gamer's consent manifest, and generate ZK skill proofs using the
already-deployed PitlSessionProofVerifier.

Why this is safe: The data floor (raw biometrics never packaged) is a protocol
invariant enforced in code — not a policy preference the Curator can override.
The consent manifest hash is verified against VAPIConsentRegistry on-chain
before every session; tampering aborts packaging. Aggregation and cooling
floors are on-chain enforced in the forthcoming consent manifest upgrade.
The Curator reads existing data; it does not collect new data. The HID capture
loop is unaffected.

**CAP-003: Marketplace Listing Submission**

Authorization: the Curator may submit ZK proof package listings to the already-
deployed VAPIDataMarketplace on behalf of gamers who have set an appropriate
autonomy level in their consent manifest.

Why this is safe: Every listing includes the consent_policy_hash — auditable
by the gamer, the operator, and any third party. The default autonomy level
(approval_required) means no listing fires without explicit gamer approval.
The gamer upgrades to full_autonomy only by explicit action; it is never
the default. Revenue routing (80/15/5 split) is enforced by the listing
contract — the Curator cannot alter revenue routing.

**CAP-004: Behavioral Anomaly Monitoring → Slashing Proposals**

Authorization: the Curator may propose slashing events to VAPIBiometricGovernance
when buyer purchasing patterns suggest credential misrepresentation.

Why this is safe: The Curator PROPOSES; VAPIBiometricGovernance EXECUTES.
The two-step is preserved. The Curator cannot execute slashing autonomously.
This is the correct separation of concerns: the Curator has the on-chain
behavioral visibility to flag anomalies; the governance layer has the authority
to act on them.

---

### 5. Constraint Inventory — What the Curator Cannot Do

These constraints are non-negotiable. They are enforced in contract code,
bridge code, and protocol invariants. The Curator does not have the authority
to override them regardless of any configuration:

```
IMMUTABLE CONSTRAINTS (protocol invariants, code-enforced):

[C-01] Raw biometric data (Mahalanobis vectors, force curves, IMU samples,
       HID frames) is NEVER packaged, NEVER listed, NEVER included in any
       ZK proof input that reaches a buyer. ProtocolViolationError on attempt.

[C-02] Aggregation floor: minimum 10 sessions per package. On-chain enforced
       in VAPIConsentRegistry manifest upgrade. Not a soft warning — a revert.

[C-03] Cooling period: minimum 72 hours post-session. On-chain enforced.
       Not configurable below this floor.

[C-04] Buyer category "competing_player_team" is NEVER an authorized
       recipient category under any gamer consent configuration.

[C-05] CHAIN_SUBMISSION_PAUSED kill-switch is respected. No listings
       submitted while kill-switch is active. No exceptions.

[C-06] Consent manifest hash must match VAPIConsentRegistry on-chain record.
       Mismatch → packaging aborts → fail-closed.

[C-07] Autonomy level "full_autonomy" is never the default for a new gamer.
       Default is always "approval_required".

[C-08] The Curator cannot expand its own scope. Any capability not in this
       manifest requires a new VAPIBiometricGovernance proposal.

[C-09] The Curator cannot execute slashing. It proposes; governance executes.

[C-10] The operator two-key gate is preserved. Curator submits transactions
       via bridge wallet; it does not hold an independent signing key.
```

---

### 6. Risk Assessment

**Risk: Curator mis-categorizes a buyer (issues Academic credential to a Brand)**

Mitigation: Evidence hash required at issuance (off-chain documentation).
AuditLog records every issuance. Annual credential expiry limits lifetime
of mis-categorization. Slashing backstop penalizes discovered fraud. The
Layer 4 encrypted packaging bounds the blast radius — even a mis-categorized
buyer only decrypts their tier's ZK proofs, never raw biometrics.

**Risk: Curator packaging loop accesses data it shouldn't**

Mitigation: Data floor enforced as a `ProtocolViolationError` in code — not
a policy flag. Consent manifest verified on-chain before every session. The
bridge DB contains processed session data, not raw HID frames (those are
never persisted beyond the in-memory processing window).

**Risk: Curator submits listings without gamer awareness**

Mitigation: Default autonomy level is `approval_required`. Gamer must
explicitly upgrade to higher autonomy levels. Every listing anchors the
consent_policy_hash. The gamer can always audit: "what did the Curator
list and under what policy?"

**Risk: This governance ceremony authorizes capabilities that then expand further**

Mitigation: The scope manifest (Document 1) is the exact enumeration of
what is authorized. CAP-001 through CAP-004. Any capability not in that
list requires a new governance proposal. The Curator cannot self-expand.
This document is the ceiling, not the floor.

---

### 7. Rollback Plan

If the Curator's expanded capabilities produce unexpected behavior or
if any constraint is found to be violated in production:

```
Immediate rollback (operator-executable, no governance required):
  bridge/.env: CURATOR_PACKAGING_ENABLED=false → restart bridge
  Effect: packaging loop disabled at next restart. No new listings.
  Existing listings: unaffected (on-chain, already committed).

Full revocation (governance required):
  VAPIBiometricGovernance.revokeScope(
    agentId=0xed6a2df5...,
    capabilityIds=["CAP-001","CAP-002","CAP-003","CAP-004"]
  )
  Effect: VAPIBuyerRegistry.curatorWallet → address(0)
  Effect: Curator cannot attest buyers or submit listings
  AuditLog: revocation anchored on-chain
  Time to effect: one bridge restart

Partial revocation (governance required):
  Individual capabilities can be revoked without revoking all four.
  CAP-001 revocation: Curator cannot issue new credentials (existing valid)
  CAP-003 revocation: Curator cannot submit new listings (existing remain)
```

The rollback mechanisms exist before any code arc fires. The governance
infrastructure (VAPIBiometricGovernance, AgentSlashing, AuditLog) is already
deployed. Rolling back this expansion does not require building new tooling.

---

### 8. IPFS Preservation

Before submitting this proposal on-chain, both documents must be pinned to IPFS:

```bash
# Pin scope manifest
ipfs add docs/governance/curator-scope-manifest.json
# → CID: [FILL after pinning]

# Pin justification document
ipfs add docs/governance/curator-governance-justification.md
# → CID: [FILL after pinning]

# Include CIDs in on-chain proposal metadata if VAPIBiometricGovernance
# supports a metadataURI field. Enables permanent off-chain retrieval.
```

If IPFS is unavailable, the documents must be committed to the repository
at `docs/governance/` before the proposal fires. The on-chain hashes are
the commitments; the files are the re-derivation source.

---

### 9. Operator Certification

By submitting this governance proposal on-chain, I, Con (ConWan30), certify:

1. I have read and understood the full capability enumeration in the scope
   manifest (Document 1) and this justification document (Document 2).

2. I authorize the vapi-curator agent to exercise capabilities CAP-001
   through CAP-004 as defined in the scope manifest, subject to all
   constraints in Section 5 of this document.

3. I understand that this authorization is permanent until revoked via
   a new VAPIBiometricGovernance proposal.

4. I have verified that the data floor (raw biometrics never packaged)
   is enforced in the bridge code before this proposal fires.

5. I have verified that no Data Economy implementation arc has begun
   before this governance ceremony completes.

6. The hashes submitted on-chain were computed from the finalized, unmodified
   versions of both documents in this package.

**Operator signature:** [FILL: ECDSA-P256 signature over sha256(justificationHash)]
**Bridge wallet:** 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
**Submission tx:** [FILL after submission]
**Block number:** [FILL after submission]
**AuditLog entry:** [FILL after submission]

---

## Submission Checklist

Before firing the `submitProposal()` transaction:

- [ ] Both documents finalized — no further edits after this point
- [ ] `compute_governance_hashes.py` run — hashes confirmed
- [ ] IPFS CIDs filled in (or docs committed to repo at `docs/governance/`)
- [ ] Bridge at current HEAD, all tests green
- [ ] Data floor enforcement verified in `curator_packaging_loop.py`
  (ProtocolViolationError fires on forbidden fields — confirmed in test suite)
- [ ] `CURATOR_PACKAGING_ENABLED=false` in bridge/.env (remains false until
  governance passes AND Arc 3 implementation complete)
- [ ] Operator certification section signed
- [ ] Gas estimate run: `estimate_gas × 1.25` for `submitProposal()` call
- [ ] Wallet balance confirmed sufficient (estimated: ~0.05 IOTX)
- [ ] `submitProposal()` fired — tx hash recorded
- [ ] AuditLog entry confirmed
- [ ] `docs/governance/SUBMISSION_RECEIPT.md` written with all fill fields completed

**After governance window passes and proposal confirmed:**
- [ ] `VAPIBuyerRegistry.setCuratorWallet(curatorWalletAddress)` executed
- [ ] Confirmation logged to AuditLog
- [ ] MEMORY.md updated: governance ceremony complete, Curator scope expanded
- [ ] CLAUDE.md updated: Data Economy arcs now unblocked
- [ ] Data Economy Arc 1 prompt fired to Claude Code
