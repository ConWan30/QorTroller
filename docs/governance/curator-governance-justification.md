# QorTroller Curator Scope Expansion — Governance Justification
## Proposal for VAPIBiometricGovernance

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

## 1. Executive Summary

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

## 2. The Architectural Basis — Why This Is Not a New System

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

## 3. Current Curator State — What Is Being Expanded From

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

## 4. What Is Being Authorized — Capability by Capability

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

## 5. Constraint Inventory — What the Curator Cannot Do

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

## 6. Risk Assessment

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

## 7. Rollback Plan

If the Curator's expanded capabilities produce unexpected behavior or
if any constraint is found to be violated in production:

```
Immediate rollback (operator-executable, no governance required):
  bridge/.env: CURATOR_PACKAGING_ENABLED=false -> restart bridge
  Effect: packaging loop disabled at next restart. No new listings.
  Existing listings: unaffected (on-chain, already committed).

Full revocation (operator-fired, anchored on-chain):
  AgentRegistry.updateAgentScope(
    agentId   = bytes32(0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8),
    newScope  = bytes32(PRE-EXPANSION_SCOPE_HASH)  // the scopeHash before this proposal
  )
  AgentScope.setAgentScopeRoot(
    agentId    = bytes32(0xed6a2df5...),
    scopeRoot  = bytes32(PRE-EXPANSION_SCOPE_ROOT)
  )
  Effect: agent's scopeHash + scopeRoot revert to pre-expansion values
  Effect: VAPIBuyerRegistry.curatorWallet operator-fired set to address(0)
          (separate tx — operator action, not governance-enforced)
  Effect: bridge config flag CURATOR_PACKAGING_ENABLED=false -> restart
          (closes the local loop)

Cryptographic anchor for the rollback (recommended, not required):
  1. Author rollback-scope-manifest.json (mirror of current state pre-expansion)
  2. Compute rollback proposalHash via scripts/compute_governance_hashes.py
  3. VAPIBiometricGovernance.proposeWithVHP(rollback_proposalHash, vhpTokenId=2)
  4. Then fire the AgentRegistry.updateAgentScope() above
  The proposeWithVHP commitment is the public, VHP-gated commitment that the
  rollback was deliberate and operator-authorized. Optional but matches the
  social-commitment pattern of the original expansion.

Partial revocation (operator-fired, anchored on-chain):
  Individual capabilities can be revoked by deploying a narrower scope:
    CAP-001 revocation: VAPIBuyerRegistry.setCuratorWallet(address(0))
                        Curator cannot issue new credentials (existing valid)
    CAP-002 revocation: bridge CURATOR_PACKAGING_ENABLED=false
                        Curator does not run the packaging loop
    CAP-003 revocation: scope manifest without "marketplace_listing" capability
                        + AgentRegistry.updateAgentScope(new_narrower_hash)
                        Existing listings remain; new listing capability revoked
```

The rollback mechanisms exist before any code arc fires. The governance
infrastructure (VAPIBiometricGovernance, AgentRegistry, AgentScope,
AgentSlashing, AuditLog) is already deployed. Rolling back this expansion
does not require building new tooling. The deployed `VAPIBiometricGovernance`
v1 (Phase 222) does not expose a single `revokeScope(agentId, capabilityIds[])`
method; rollback is composed from the existing onlyOwner methods on
AgentRegistry + AgentScope, optionally anchored by a fresh `proposeWithVHP()`
VHP-gated commitment to the rollback scope hash.

### Honesty Note on Governance Enforcement (V-check finding 2026-05-28)

The Phase 222 `VAPIBiometricGovernance` contract anchors VHP-gated
commitments to opaque `bytes32 proposalHash` values via `proposeWithVHP()`.
It does NOT contract-enforce the subsequent execution of the proposal.
Specifically: `AgentRegistry.updateAgentScope()` and `AgentScope.setAgentScopeRoot()`
are both `onlyOwner` (bridge wallet) — the operator can call them without
any governance proposal at all.

The authority of this governance ceremony is therefore **social commitment +
cryptographic anchor**: the operator publicly commits to the proposal (via
the VHP-gated `proposeWithVHP` call) BEFORE executing the scope change. The
proposalHash on-chain is the receipt that the operator committed to exactly
these documents. Future auditors re-derive the hash from these files and
verify the commitment matches.

Trust this governance ceremony to the same extent you trust the operator
to honor a publicly-committed proposal. The contract layer ensures the
commitment is anchored + tamper-evident; the operator's discipline ensures
the subsequent execution matches the commitment.

A future Phase 222.v2 could close this loop by gating `updateAgentScope`
on a passed governance proposal. That is a separate architectural arc,
not part of this expansion.

---

## 8. IPFS Preservation

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

## 9. Operator Certification

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
