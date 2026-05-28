# QorTroller Gamer-Sovereign Data Economy
## Technical Framework Document — Claude Code Instructional Instrument
**Version:** 1.0 · **Date:** 2026-05-27 · **Status:** Design-Complete / Pre-Implementation
**Authority:** Architectural Collaborator synthesis · Operator review required before any arc fires

---

## 0. The Core Architectural Insight (Read This First)

> **The proof of humanity IS the data provenance.**

QorTroller is not an anti-cheat protocol with a data marketplace bolted on.
It is a single system where the infrastructure that proves humanity
simultaneously generates the most credible human behavioral dataset in
competitive gaming.

The PITL stack, the PoAC chain, the 228-byte tamper-evident records, the
composite-sig renewal, the AIT separation ratio — every layer built to prove
a live human is on a certified controller — also produces cryptographically-
attested, continuously-proven behavioral data with hardware-rooted provenance.

The Curator's job is to extract value from what the protocol already generates.
Not to build a separate data pipeline. The marketplace exists because the
anti-cheat infrastructure already runs.

This insight is the reason the data economy arc is architecturally coherent
rather than speculative. The scaffolding is complete. What follows is the
spec for what gets built on top of it.

---

## 1. Current State — What Is Real and Deployed

**Status: LIVE on IoTeX testnet (chain ID 4690)**
**Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692**
**Balance: ~9.12 IOTX · 51 contracts live · 13 frozen primitives · 35 PV-CI invariants**

### 1.1 Marketplace Infrastructure (LIVE)

| Contract | Address | Purpose |
|---|---|---|
| VAPIDataMarketplace | Phase 238 | On-chain marketplace surface |
| VAPIDataMarketplaceListings | Phase 238 | Listing management |
| VAPIConsentRegistry | Phase 237 | Gamer consent bitmask (current: coarse bitmask) |
| PitlSessionProofVerifier | Phase 62 | On-chain ZK verifier (Poseidon-8 Groth16) |
| VAPIBiometricGovernance | Phase 222 | Dispute resolution + governance |
| AgentSlashing | Phase O0 | Economic penalty execution |
| AuditLog | Phase O0 | Attestation transparency log |

### 1.2 Curator Agent (LIVE — Scope-Limited)

```
Agent:    vapi-curator
On-chain ID: 0xed6a2df5...
Status:   O3_ACTING (live authority)
Current scope: marketplace monitoring + tier-drift + consent monitoring
Autonomous: NO — executor-disabled (two-key gate)
```

**Critical constraint:** The Curator currently holds O3_ACTING authority but
is executor-disabled. Expanding its scope to autonomous marketplace-lister
requires a formal governance proposal through `VAPIBiometricGovernance`.
This is not a code change. It is a governance ceremony. **It is the
prerequisite for every arc in this document.**

### 1.3 What the Current Stack Produces (LIVE)

Every gaming session with the DualShock Edge CFI-ZCP1 connected produces:

- **PoAC records**: 228-byte tamper-evident records at ~200ms windows,
  signed with ECDSA-P256, chained by SHA-256. 637K+ on live device.
- **PITL classifications**: humanity_probability from L4 Mahalanobis +
  L5 temporal rhythm + L2B causal latency + E4 spectral entropy.
- **Adjudication verdicts**: HUMAN / BOT / UNCLEAR per session, from
  dual-verdict (LLM + deterministic fallback) with no divergence.
- **GIC chain stamps**: cryptographic session ledger (GIC_100 reached).
- **VHP renewal proofs**: composite-sig challenge-response (ML-DSA-44 +
  ECDSA-P256) against on-chain registered pubkey in VAPIPoEPRegistry.

This data already exists. The data economy arc packages it for sovereign
monetization. Nothing new needs to be captured.

### 1.4 What Is NOT Yet Built (HYPOTHETICAL — Architecturally Specified)

| Component | Status | Gate |
|---|---|---|
| VAPIBuyerRegistry | HYPOTHETICAL | Governance ceremony first |
| VAPIBuyerCategoryVerifier (ZK circuit) | HYPOTHETICAL | Governance ceremony first |
| Category-specific encryption key management | HYPOTHETICAL | After Arc 2 |
| Post-session Curator autonomous packaging loop | HYPOTHETICAL | After Arc 3 |
| Structured consent manifest (7-dimension) | HYPOTHETICAL | After Arc 4 |
| Curator scope expansion to marketplace-lister | GOVERNANCE-GATED | Prerequisite |

---

## 2. Governance Prerequisite — Curator Scope Expansion

**This must complete before any implementation arc fires.**
**It is not a Claude Code session. It is an operator-executed ceremony.**

### 2.1 What the Ceremony Requires

A formal governance proposal through `VAPIBiometricGovernance` authorizing
the Curator agent to expand from:
- **Current scope**: marketplace monitoring + tier-drift + consent monitoring
- **Proposed scope**: + autonomous post-session data packaging + ZK proof
  generation + marketplace listing on gamer's behalf within consent policy

### 2.2 Why This Gate Exists

The Curator cannot self-expand its authority. This is the architectural
check that makes the entire data economy trustworthy. An agent that can
expand its own scope without operator authorization is not a protocol
steward — it is a liability. The governance gate is the correct sequencing,
not bureaucratic overhead.

### 2.3 On-Chain Execution

```
Contract: VAPIBiometricGovernance (deployed, Phase 222)
Action: submitProposal(
    agentId=0xed6a2df5...,
    newScopeHash=keccak256(scope_manifest_bytes),
    justificationHash=sha256(justification_doc_bytes),
    duration=GOVERNANCE_WINDOW
)
```

The scope manifest must explicitly list every new capability being authorized.
The AuditLog records the governance event. The Curator's expanded authority
becomes effective only after the proposal passes.

---

## 3. Data Economy Architecture — The Gamer Supplier Model

### 3.1 The Structural Reversal

**Before QorTroller data economy:**
- Gamer plays → Sony, EA, platform operator harvest biometric data silently
- Zero compensation, zero transparency, zero opt-out

**After QorTroller data economy:**
- Gamer plays → Bridge captures → Curator packages per consent policy
- Gamer is the data supplier → Curator is the sovereign broker
- No data leaves without consent → Every sale auditable on-chain
- Revenue hits gamer's wallet → Gamer controls policy

### 3.2 Edge-Compute Architecture (W3bstream Pattern)

The 1000 Hz raw capture creates massive data weight. Pushing it to a
centralized cloud for processing introduces latency, gas costs, and
unacceptable privacy risk.

```
[DualShock Edge] → [1002 Hz HID frames] → [Bridge (local)]
                                              │
                              [~/.vapi/bridge.db — SQLite WAL]
                                              │
                              [Post-session: Curator reads local DB]
                                              │
                         [Applies consent policy → generates ZK proofs]
                                              │
                    [Lists ONLY ZK proofs + metadata on VAPIDataMarketplace]
                                              │
                         [Raw biometric data NEVER leaves local machine]
```

The bridge already runs locally. The DB already exists. The Curator reads
what's already there. No new data pipeline required.

### 3.3 What Gets Packaged (Not What Gets Sold)

The Curator NEVER packages:
- Raw 12-feature Mahalanobis vectors
- Raw trigger force curves (1 kHz continuous)
- Raw IMU samples (250 Hz gyro + accelerometer)
- Raw HID frame data

These are **protocol invariants** — immutable regardless of any consent
configuration. If a gamer explicitly requests raw data sale, the Curator
refuses. This protects not just the gamer's privacy but the cryptographic
integrity of the entire network: a buyer with raw biometric fingerprints
could train an ML model to synthesize curves that bypass the humanity proof.

The Curator ONLY packages: ZK proofs derived from session data. Four tiers.

---

## 4. The 7-Dimension Consent Manifest

**Status: HYPOTHETICAL — specified, not yet built**
**Replaces: VAPIConsentRegistry coarse bitmask**
**Implementation: Arc 4 (see section 8)**

The current `VAPIConsentRegistry` stores a coarse bitmask. The data economy
requires a structured consent manifest — a policy document the Curator reads
and enforces on every listing decision, with each decision anchored to the
policy hash on-chain.

### Dimension 1 — Data Category Floor (Protocol Invariants, Not User-Settable)

```python
# PROTOCOL INVARIANTS — immutable, Curator enforces regardless of consent config
DATA_FLOOR_NEVER_PACKAGE = [
    "raw_mahalanobis_vector",     # 12-feature biometric fingerprint
    "raw_trigger_force_curves",   # 1 kHz adaptive trigger data
    "raw_imu_samples",            # 250 Hz gyro + accelerometer
    "raw_hid_frames",             # 64-byte per-frame sensor data
]

# GAMER-CONFIGURABLE above the floor:
DATA_CATEGORIES = {
    "aggregate_session_stats":      {"sensitivity": "LOW",     "default": True},
    "skill_level_zk_proofs":        {"sensitivity": "MEDIUM",  "default": True},
    "improvement_trajectory":       {"sensitivity": "MEDIUM_HIGH", "default": False},
    "context_performance":          {"sensitivity": "HIGH",    "default": False},
    "controller_characterization":  {"sensitivity": "MEDIUM",  "default": None},  # gamer decides
}
```

### Dimension 2 — Buyer Category Consent

```python
BUYER_CATEGORIES = {
    "academic_research":      {"default": True},
    "game_developer":         {"default": True},
    "esports_team_scout":     {"default": True},
    "brand_advertiser":       {"default": False},  # explicit opt-in required
    "anonymous_buyer":        {"default": False},  # explicit opt-in required
    "competing_player_team":  {"default": False, "overrideable": False},  # protocol invariant
}
```

### Dimension 3 — Aggregation Floor

```python
# Gamer-settable minimum. Cannot be lowered below N=10 (protocol floor).
AGGREGATION_FLOOR = {
    "min_sessions_per_package": 10,   # protocol minimum — not overrideable
    "gamer_min": 10,                  # gamer can raise, cannot lower
}
# Rationale: prevents buyer from reconstructing individual biometric fingerprint
# by purchasing many single-session packages. Ties to AIT separation ratio work.
```

### Dimension 4 — Temporal Cooling Period

```python
# Prevents real-time surveillance applications
COOLING_PERIOD_HOURS = 72  # protocol minimum
# Gamer can extend (168h, 720h), cannot shorten below 72h
```

### Dimension 5 — Pricing Floor

```python
PRICING = {
    "min_price_vapi_tokens": None,    # gamer-set
    "revenue_split": {
        "gamer": 0.80,                # 80% to gamer wallet
        "protocol_treasury": 0.15,    # 15% to protocol
        "curator_fee": 0.05,          # 5% to Curator operational budget
    },
    "listing_type": "fixed_price",    # "fixed_price" | "auction" — gamer's choice
}
```

### Dimension 6 — ZK Proof Depth Tiers

```python
ZK_PROOF_TIERS = {
    1: {
        "name": "Ranking",
        "claim": "This player is in percentile X",
        "sensitivity": "LOWEST",
        "default": True,
        "reveals": "skill percentile only",
    },
    2: {
        "name": "Trajectory",
        "claim": "This player improved from percentile X to Y over N sessions",
        "sensitivity": "MEDIUM",
        "default": True,
        "reveals": "consistency + effort over time",
    },
    3: {
        "name": "Context Performance",
        "claim": "This player performs at percentile X under specific in-game conditions",
        "sensitivity": "HIGH",
        "default": False,   # explicit opt-in required
        "reveals": "stress response + fatigue signatures",
    },
    4: {
        "name": "Full Session Proof",
        "claim": "This specific session had these specific measurable characteristics",
        "sensitivity": "HIGHEST",
        "default": False,   # explicit opt-in required
        "reveals": "session-level granularity",
    },
}
# Circuit: PitlSessionProofVerifier (LIVE on-chain, Poseidon-8 Groth16)
# Curator calls verifier to generate proofs — does not build new circuits
```

### Dimension 7 — Curator Autonomy Level

```python
AUTONOMY_LEVELS = {
    "approval_required": {
        "description": "Curator proposes each listing. 24h window. No listing without explicit approval.",
        "default": True,  # DEFAULT — must be upgraded explicitly
        "risk": "LOW",
    },
    "notify_only": {
        "description": "Curator acts, then notifies. Reversible within N hours.",
        "default": False,
        "risk": "MEDIUM",
    },
    "full_autonomy": {
        "description": "Curator lists and settles without asking. Revenue arrives. Gamer reviews history.",
        "default": False,
        "risk": "HIGH — requires explicit upgrade from gamer",
    },
    "manual_only": {
        "description": "Curator never acts autonomously. Presents opportunities; gamer executes.",
        "default": False,
        "risk": "NONE",
    },
}
# CRITICAL: Default is approval_required. No gamer should be enrolled in
# full_autonomy without explicitly understanding and choosing it.
```

### 4.1 Consent Manifest On-Chain Anchoring

```python
# Each consent manifest version gets a hash anchored on-chain
# Curator decision log: every listing action references the policy hash
# Gamer audit: "Curator listed [dataset] on [date] under policy [hash]"

consent_manifest_hash = sha256(canonical_json(manifest))
# Stored in: VAPIConsentRegistry (upgraded from bitmask to hash — Arc 4)
# Curator reads: manifest from local config, verifies against on-chain hash
# If manifest tampered: Curator refuses to list (fail-closed)
```

---

## 5. ZK Skill Proofs — Technical Architecture

**Status: HYPOTHETICAL (circuit) — LIVE (verifier contract)**
**Existing verifier: PitlSessionProofVerifier (Poseidon-8, Groth16, LIVE)**

### 5.1 What ZK Skill Proofs Enable

A gamer can prove to an esports team, tournament organizer, or researcher:
- "I am in the 94th percentile for trigger response in NCAA CFB 26"
- "My humanity_probability has been ≥0.85 across 37 consecutive sessions"
- "My L4 Mahalanobis distance from known-bot cluster exceeds threshold T"

...without revealing:
- Their raw biometric fingerprint
- Their session-level data
- Their real identity

The proof is portable, unfakeable (rooted in the PoAC chain), and verifiable
by anyone with an RPC connection to IoTeX testnet (or mainnet post-TGE).

### 5.2 Circuit Architecture

```
Inputs (private):
  - session_ids[]: array of session IDs being proven over
  - humanity_prob[]: per-session humanity probability values
  - pitl_layer_scores[]: L4, L5, L2B, E4 per session
  - poac_chain_root: Merkle root of included PoAC records
  - gamer_private_key: proves gamer controls the credential

Inputs (public):
  - min_sessions: aggregation floor (≥10)
  - percentile_claim: the claim being proven
  - game_profile: "ncaa_cfb_26" | ...
  - verifier_address: on-chain verifier

Output:
  - ZK proof: "these private inputs satisfy the claim at the stated tier"
  - Proof hash: anchored on VAPIDataMarketplace listing

Circuit: Poseidon-8 friendly (matches existing PitlSessionProofVerifier)
Proving system: Groth16 (matches existing ceremony artifacts)
```

### 5.3 What Buyers Receive

The buyer receives the ZK proof + the proof hash + the verifier contract
address. They call `PitlSessionProofVerifier.verify(proof)` on-chain.
The contract returns `true` (claim holds) or `false` (claim invalid).

The buyer learns: the claim is true or false.
The buyer does NOT learn: which sessions, which player, which device.

---

## 6. The 4-Layer Buyer Verification System

**Status: HYPOTHETICAL — complete architectural spec**
**Problem: On a permissionless chain, cryptography verifies signatures, not intentions.**

### Layer 1 — Attested Buyer Credentials (Curator-Issued)

**Status: HYPOTHETICAL — requires VAPIBuyerRegistry (Arc 1)**

```solidity
// VAPIBuyerRegistry.sol (to be built in Arc 1)
struct BuyerCredential {
    bytes32  buyerDID;           // ioID DID of the buyer entity
    uint8    categoryId;         // 1=Academic, 2=GameDev, 3=EsportsTeam, 4=Brand
    bytes32  evidenceHash;       // sha256(supporting documentation — off-chain)
    address  attestedBy;         // Curator wallet (after governance ceremony)
    uint64   issuedAt;
    uint64   expiresAt;          // credentials expire annually; re-attest required
    bool     active;
}

mapping(bytes32 => BuyerCredential) public credentials; // buyerDID → credential
```

The Curator reviews real-world documentation off-chain and issues the
credential on-chain. Every credential issuance is logged in AuditLog.
The governance override via VAPIBiometricGovernance is the backstop against
Curator mis-categorization or compromise.

**Protocol symmetry:** Manufacturers attest to hardware (VAPIManufacturerDeviceRegistry).
Curator attests to buyers (VAPIBuyerRegistry). Same trust pattern; different subjects.

### Layer 2 — ZK Buyer Category Proofs (Privacy-Preserving)

**Status: HYPOTHETICAL — requires VAPIBuyerCategoryVerifier circuit (Arc 2)**

Buyers in competitive industries (esports, AAA game development) cannot
afford to leak purchasing patterns on a public ledger. An esports team
buying ZK proofs for specific players reveals their scouting strategy.

ZK buyer credentials allow a buyer to prove:
- "I possess a valid, unexpired credential for category `esports_team`"
- Signed by the Curator's attested key
- WITHOUT revealing which institution or which wallet

```
Circuit: VAPIBuyerCategoryVerifier (to be built)
Pattern: Semaphore (nullifier + membership proof)
Verifier: VAPIBuyerCategoryVerifier.sol (to be deployed, Arc 2)
```

The smart contract checks the ZK proof against the gamer's consent policy.
Category verified → listing accessible. Buyer identity: private.

### Layer 3 — Economic Slashing (Deterrence Backstop)

**Status: LIVE (AgentSlashing contract deployed)**

```
Stake requirement: VAPI tokens, scaled to data sensitivity level accessed
Slashing trigger 1: Curator detects behavioral anomaly on-chain
  → "academic" buyer sweeping entire marketplace (not a study)
  → Curator proposes slashing event → VAPIBiometricGovernance decides
Slashing trigger 2: Off-chain fraud report with on-chain evidence
  → Evidence hash submitted to VAPIBiometricGovernance
  → Governance verifies → AgentSlashing.slash(buyerDID, amount)
  → Credential revoked in VAPIBuyerRegistry
  → Wallet blacklisted

Calibration principle: stake must exceed realistic value of misrepresentation.
Governance sets the stake floor. A 1,000 VAPI stake against 10,000 VAPI
data value is not deterrence — it's a cost of doing business.
```

**Honest limit:** Economically sophisticated actors calculate expected value.
Slashing deters casual misrepresentation, not sophisticated attacks with
calculated ROI. Layers 1 + 4 are the backstops for sophisticated attacks.

### Layer 4 — Encrypted Data Packaging (Damage Bounding)

**Status: HYPOTHETICAL — requires key management infrastructure (Arc 3)**

```
K_academic = encryption key for academic-tier packages
K_gamedev  = encryption key for game-developer-tier packages
K_esports  = encryption key for esports-tier packages
K_brand    = encryption key for brand-tier packages (only if gamer consented)
```

Buyers holding a valid credential for category X receive access to K_X only.
The smart contract (or Curator acting as decryption oracle) issues K_X only
to wallets presenting valid credentials.

**The critical property:** Even if a brand advertiser successfully frauds
their way through Layers 1-3 and obtains K_academic, they decrypt only what
academic packages contain: Tier 1-2 ZK proofs. Raw biometrics are never in
any package at any tier level. The data floor (Dimension 1) is immutable.
The blast radius of a successful fraud attack is strictly bounded.

### Synthesis: Why Defense-in-Depth Works

| Layer | Catches | Misses |
|---|---|---|
| Attested credentials | Casual misrepresentation | Sophisticated fraud with real docs |
| ZK category proofs | On-chain identity linkage | Still requires an attestor |
| Economic slashing | When gain ≤ stake | When gain >> stake |
| Encrypted packages | Escalation beyond category ceiling | Intra-category fraud |

All four together: misrepresentation is practically difficult, economically
risky, and damage-bounded even when it succeeds.

---

## 7. The Adoption Flywheel

```
prove humanity
      ↓
generate sovereign behavioral data
      ↓
Curator packages → lists on VAPIDataMarketplace
      ↓
gamer earns from existing play (no extra effort)
      ↓
more gamers want V.A.P.I.-native tournaments
      ↓
more tournament operators integrate isFullyEligible()
      ↓
more manufacturers want certified hardware
      ↓
more controllers enrolled → richer dataset → higher data value
      ↓
[repeat]
```

The flywheel does not require new infrastructure at each stage. It requires
existing infrastructure to be used. The PoAC chain already runs. The PITL
stack already classifies. The adjudicator already verdicts. The Curator
already monitors. Each stage of the flywheel is unlocked by a governance
decision or an arc completion — not by building something new.

---

## 8. Implementation Arcs — Claude Code Specifications

**Prerequisites for all arcs:**
1. Governance ceremony for Curator scope expansion (operator-executed, not code)
2. Arc sequencing is strict: Governance → Arc 1 → Arc 2 → Arc 3 → Arc 4
3. Each arc is hold-gated (pre-investigation → hold → implementation → P-check → hold → commit)
4. No arc fires without operator authorization on wallet-spending commits

**Estimated total wallet spend:** ~3-4 IOTX across all four arcs
**Estimated development time:** 6-8 weeks focused

---

### Arc 1 — VAPIBuyerRegistry + Credential Issuance

**Scope:** Layer 1 of the buyer verification system.
**Gate:** Governance ceremony complete (Curator scope expanded).
**Wallet spend:** ~0.8-1.0 IOTX (one contract deploy)

#### Arc 1 Pre-Investigation Checklist

Before any implementation, Claude Code must verify:

1. **Governance ceremony receipt.** Confirm `VAPIBiometricGovernance` has a
   passed proposal expanding Curator scope. Read the AuditLog entry. If not
   present, stop and surface — no arc fires without this.

2. **VAPIBuyerRegistry naming convention.** Confirm Layer C: all contracts
   carry VAPI prefix. Naming: `VAPIBuyerRegistry`. All `deviceId`-parallel
   fields use `bytes32 buyerDID`. Check `deployed-addresses.json` key convention.

3. **ioID DID integration.** Read how existing contracts use ioID DIDs (if at
   all). Determine whether `VAPIBuyerRegistry` should integrate ioID directly
   or store a `bytes32 buyerDID` derived separately. Surface findings.

4. **Curator attestation key.** The Curator attests buyer credentials. What
   key does the Curator use for on-chain writes post-governance? Confirm the
   KMS-HSM key that Guardian anchored is available for Curator's attestation
   transactions. If unclear, surface before implementation.

5. **AuditLog interface.** Read `AuditLog.sol` (deployed, Phase O0). Confirm
   the method signature for logging credential issuance events. Every Curator
   attestation action must be logged here.

#### Arc 1 Commit Plan

**Commit 1 — VAPIBuyerRegistry.sol + Hardhat tests**

```solidity
// SPDX-License-Identifier: MIT
// VAPIBuyerRegistry — Buyer category credential registry.
// Trust model: CURATOR-ATTESTED (attestedBy = Curator wallet post-governance).
// Structural parallel to VAPIManufacturerDeviceRegistry (manufacturer attests hardware).
// The Curator attests buyers. Same pattern; different subjects.
// Governance ceremony required before Curator can attest (scope expansion via
// VAPIBiometricGovernance). Credential issuance before governance = REVERTS.

pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract VAPIBuyerRegistry is Ownable, ReentrancyGuard {

    // FROZEN enum values — pinned by vapi_invariant_gate.py INV-BUY-001
    uint8 public constant CATEGORY_ACADEMIC    = 1;
    uint8 public constant CATEGORY_GAME_DEV    = 2;
    uint8 public constant CATEGORY_ESPORTS     = 3;
    uint8 public constant CATEGORY_BRAND       = 4;
    // Category 5+ reserved for future governance-approved categories

    struct BuyerCredential {
        bytes32  buyerDID;           // ioID DID of buyer entity
        uint8    categoryId;         // CATEGORY_* constant above
        bytes32  evidenceHash;       // sha256(off-chain documentation)
        address  attestedBy;         // Curator wallet address
        uint64   issuedAt;           // block.timestamp
        uint64   expiresAt;          // issuedAt + 365 days
        bool     active;
    }

    mapping(bytes32 => BuyerCredential) public credentials;
    mapping(bytes32 => bool)            public registered;
    address public curatorWallet;       // set by owner post-governance

    event CredentialIssued(bytes32 indexed buyerDID, uint8 categoryId, address attestedBy);
    event CredentialRevoked(bytes32 indexed buyerDID);
    event CuratorWalletSet(address indexed wallet);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function setCuratorWallet(address wallet) external onlyOwner {
        curatorWallet = wallet;
        emit CuratorWalletSet(wallet);
    }

    function issueCredential(
        bytes32 buyerDID,
        uint8   categoryId,
        bytes32 evidenceHash
    ) external nonReentrant {
        require(msg.sender == curatorWallet, "only Curator");
        require(curatorWallet != address(0), "Curator wallet not set");
        require(!registered[buyerDID], "already registered");
        require(categoryId >= CATEGORY_ACADEMIC && categoryId <= CATEGORY_BRAND, "invalid category");
        credentials[buyerDID] = BuyerCredential({
            buyerDID:    buyerDID,
            categoryId:  categoryId,
            evidenceHash: evidenceHash,
            attestedBy:  msg.sender,
            issuedAt:    uint64(block.timestamp),
            expiresAt:   uint64(block.timestamp) + 365 days,
            active:      true
        });
        registered[buyerDID] = true;
        emit CredentialIssued(buyerDID, categoryId, msg.sender);
    }

    function revokeCredential(bytes32 buyerDID) external {
        require(msg.sender == curatorWallet || msg.sender == owner(), "unauthorized");
        require(registered[buyerDID], "not registered");
        credentials[buyerDID].active = false;
        emit CredentialRevoked(buyerDID);
    }

    function isValidCredential(bytes32 buyerDID, uint8 categoryId)
        external view returns (bool)
    {
        BuyerCredential memory c = credentials[buyerDID];
        return registered[buyerDID]
            && c.active
            && c.categoryId == categoryId
            && block.timestamp < c.expiresAt;
    }

    function getCategory(bytes32 buyerDID) external view returns (uint8) {
        return credentials[buyerDID].categoryId;
    }
}
```

Hardhat tests (8): issue credential (Academic), verify active + unexpired,
category retrieval, expired credential fails `isValidCredential`, double-
registration reverts, non-Curator issuer reverts, revoke → inactive, Curator
wallet not set → reverts.

**vapi_invariant_gate.py:** Add `INV-BUY-001` pinning `CATEGORY_ACADEMIC = 1`
and `CATEGORY_BRAND = 4`. PV-CI count: 35 → 37.

**bridge/vapi_bridge/chain.py:** Add view methods:
```python
def is_valid_buyer_credential(self, buyer_did: str, category_id: int) -> bool
def get_buyer_category(self, buyer_did: str) -> int
```
60s TTL cache. Fail-open when `buyer_registry_address` unset (bridge
readiness must not depend on deploy).

Deploy: `contracts/scripts/deploy-vapi-buyer-registry.js`. ABORT guard.
`estimate_gas × 1.25`. Adds entry to `deployed-addresses.json`.
**Operator authorization required before deploy fires.**

P-check: Hardhat green, bridge tests pass, invariant gate clean.
**Hold for operator review before Arc 1 Commit 2.**

**Commit 2 — Curator bridge attestation module**

`bridge/vapi_bridge/curator_attestation.py`:

```python
class CuratorAttestationModule:
    """
    Curator's buyer credential attestation capability.
    Active only after governance ceremony completes (curatorWallet set on-chain).
    All issuance actions logged to AuditLog (on-chain).

    Workflow:
    1. Buyer submits documentation request (off-chain — email/form)
    2. Operator reviews documentation
    3. Operator calls attest_buyer() with evidence hash
    4. Module calls VAPIBuyerRegistry.issueCredential() on-chain
    5. AuditLog entry created
    6. Buyer receives on-chain credential
    """

    def attest_buyer(
        self,
        buyer_did: str,
        category_id: int,
        evidence_hash: bytes,
        dry_run: bool = True  # default True — operator must explicitly set False
    ) -> str: ...  # returns tx_hash or dry_run summary

    def revoke_credential(self, buyer_did: str, reason_hash: bytes) -> str: ...

    def flag_behavioral_anomaly(
        self,
        buyer_did: str,
        anomaly_type: str,
        evidence: dict
    ) -> None: ...  # triggers slashing proposal pipeline
```

Tests (5): dry_run mode returns summary without tx, `attest_buyer` produces
valid on-chain credential, `revoke_credential` sets active=false, anomaly
flag logged to AuditLog, non-governance-expanded Curator reverts.

P-check: full suite, invariant gate clean.
**Hold for operator review before Arc 2.**

---

### Arc 2 — VAPIBuyerCategoryVerifier (ZK Circuit)

**Scope:** Layer 2 of the buyer verification system. Privacy-preserving
category proof. Buyer proves category membership without revealing identity.
**Gate:** Arc 1 complete + Curator attestation operational.
**Wallet spend:** ~0.5-0.8 IOTX (verifier contract deploy)

#### Arc 2 Pre-Investigation Checklist

1. **Existing ZK ceremony artifacts.** Read `Groth16VerifierZKSepProof` (Phase
   237-ZK-SEPPROOF, IoTeX-anchored ceremony). Confirm: is the MPC ceremony
   infrastructure reusable for a new circuit? What did the prior ceremony
   produce (PTAU file, verification key)? Can the same PTAU be reused?

2. **Poseidon-8 compatibility.** Confirm `PitlSessionProofVerifier` uses
   Poseidon-8. `VAPIBuyerCategoryVerifier` should use the same hash function
   for consistency. Verify circom/snarkjs toolchain is available.

3. **Semaphore pattern audit.** The buyer ZK proof uses Semaphore-style
   nullifiers. Read whether any existing QorTroller circuit uses nullifiers.
   If not, this is net-new circuit design — scope accordingly.

4. **Existing verifier deploy pattern.** Read how `PitlSessionProofVerifier`
   was deployed (deploy script, ABI registration in bridge). Match pattern.

#### Arc 2 Circuit Specification

```circom
// VAPIBuyerCategoryVerifier.circom
// Proves: buyer holds a valid, unexpired credential for claimed category
// Without revealing: which buyer, which institution, which wallet

pragma circom 2.0.0;
include "poseidon.circom";

template BuyerCategoryProof() {
    // Private inputs
    signal private input buyerDID;          // buyer's DID (stays private)
    signal private input credentialNonce;   // unique per proof (prevents reuse)
    signal private input categoryId;        // the claimed category
    signal private input issuedAt;          // credential issuance timestamp
    signal private input expiresAt;         // credential expiry timestamp
    signal private input curatorSigR;       // Curator ECDSA sig components
    signal private input curatorSigS;

    // Public inputs
    signal input claimedCategory;           // what the buyer claims to be
    signal input currentTimestamp;          // block.timestamp at proof time
    signal input curatorPubkey;             // Curator's registered pubkey hash
    signal input nullifierHash;             // prevents proof reuse

    // Constraints
    // 1. categoryId matches claimedCategory
    // 2. currentTimestamp < expiresAt (credential not expired)
    // 3. Curator signature valid over (buyerDID, categoryId, issuedAt, expiresAt)
    // 4. nullifierHash = Poseidon(buyerDID, credentialNonce)

    // Output
    signal output valid;    // 1 if all constraints satisfied
}
```

**VAPIBuyerCategoryVerifier.sol** — Groth16 on-chain verifier (generated from
circuit). Deploy pattern matches `PitlSessionProofVerifier`.

**Bridge integration:**
```python
# bridge/vapi_bridge/zk_buyer_verifier.py
def verify_buyer_category_proof(
    proof: bytes,
    claimed_category: int,
    current_timestamp: int
) -> bool:
    """Calls VAPIBuyerCategoryVerifier on-chain. Returns True if proof valid."""
```

P-check: circuit constraints verified (all inputs, all edge cases), verifier
contract Hardhat tests (6), bridge integration tests (3).
**Hold for operator review before Arc 3.**

---

### Arc 3 — Post-Session Curator Packaging Loop

**Scope:** The operational core. Post-session, the Curator reads local DB,
applies consent manifest, generates ZK skill proofs, lists on marketplace.
**Gate:** Arc 2 complete (buyer verification operational).
**Wallet spend:** ~0.2-0.5 IOTX per listing batch (marketplace transactions)

#### Arc 3 Architecture

```python
# bridge/vapi_bridge/curator_packaging_loop.py

class CuratorPackagingLoop:
    """
    Post-session data packaging orchestrator.
    Triggered: on session_complete event from gameplay_session_log.
    Reads: local bridge.db session data.
    Enforces: gamer's consent manifest (policy hash verified against on-chain).
    Generates: ZK skill proofs via PitlSessionProofVerifier.
    Lists: proof packages on VAPIDataMarketplace.
    Never: touches raw biometric data. Never: bypasses consent policy.
    """

    async def on_session_complete(self, session_id: str) -> None:
        """
        Main entry point. Called by dualshock_integration.py session boundary.

        Steps:
        1. Load consent manifest → verify hash against VAPIConsentRegistry on-chain
        2. If manifest tampered or missing: abort (fail-closed)
        3. Load session data from bridge.db
        4. Apply aggregation floor (N≥10 check — may defer if insufficient sessions)
        5. Apply temporal cooling (72h check — may defer if too recent)
        6. Apply data category floor (protocol invariant — no raw data ever)
        7. For each permitted ZK proof tier in manifest:
           a. Compute proof inputs from session aggregate
           b. Generate ZK proof via PitlSessionProofVerifier
           c. Encrypt package under category key (K_academic etc.)
           d. Prepare listing metadata
        8. Based on autonomy_level in manifest:
           - approval_required: write to pending_listings table, notify gamer
           - notify_only: list immediately, write to notifications table
           - full_autonomy: list immediately, write to history table
        9. Log all actions to AuditLog (on-chain, per listing)
        10. Update gameplay_session_log with packaging_status
        """

    def _apply_data_floor(self, session_data: dict) -> dict:
        """
        Protocol invariant enforcement. Strips any raw biometric fields.
        Raises ProtocolViolationError if called with raw field names.
        This check is immutable — no consent configuration bypasses it.
        """
        FORBIDDEN_FIELDS = {
            "raw_mahalanobis_vector",
            "raw_trigger_force_curves",
            "raw_imu_samples",
            "raw_hid_frames",
        }
        for field in FORBIDDEN_FIELDS:
            if field in session_data:
                raise ProtocolViolationError(
                    f"Data floor violation: {field} cannot be packaged under any configuration"
                )
        return session_data

    def _check_aggregation_floor(
        self, device_id: str, min_sessions: int = 10
    ) -> bool:
        """
        Returns True if sufficient sessions exist for aggregation.
        Returns False (defer, do not fail) if insufficient.
        Never packages individual sessions below the floor.
        """

    def _check_cooling_period(
        self, session_ended_at: int, cooling_hours: int = 72
    ) -> bool:
        """
        Returns True if session is old enough to package.
        Returns False (defer) if still within cooling period.
        """
```

#### Arc 3 Commit Plan (3 commits)

**Commit 1:** `CuratorPackagingLoop` core + consent manifest loader +
data floor enforcement + aggregation + cooling checks. Tests (8): data floor
raises on forbidden fields, aggregation defers below N=10, cooling defers
within 72h, consent manifest hash mismatch aborts, approval_required writes
to pending table, full_autonomy lists immediately, audit log entry on every
action, session log updated.

**Commit 2:** ZK proof generation integration + category encryption + listing
submission. Tests (6): proof generation succeeds for Tier 1-2 (default ON),
proof generation for Tier 3-4 requires explicit consent, encrypted package
correct key used per category, marketplace listing tx submitted, listing
rejected if buyer_category not in gamer consent policy, listing metadata
includes consent_policy_hash.

**Commit 3:** Autonomy ladder UI hooks + pending_listings bridge endpoint +
gamer notification system. New endpoint: `GET /curator/pending-listings` +
`POST /curator/approve-listing/{listing_id}` + `POST /curator/reject-listing/
{listing_id}`. Tests (5): pending listings surfaced correctly, approve
triggers marketplace submission, reject clears from pending, notification
written on full_autonomy listing, AuditLog entry on every decision.

P-check: full suite, invariant gate, marketplace listings verified on-chain.
**Hold for operator review before Arc 4.**

---

### Arc 4 — Structured Consent Manifest Upgrade

**Scope:** Upgrade VAPIConsentRegistry from coarse bitmask to structured
policy manifest. Backward-compatible — existing bitmask consent records
migrate to equivalent manifest defaults.
**Gate:** Arc 3 complete (packaging loop uses manifest).
**Wallet spend:** ~0.5-0.8 IOTX (registry redeploy or proxy upgrade)

#### Arc 4 Pre-Investigation Checklist

1. **VAPIConsentRegistry upgradeability.** Read the current contract. Is it
   upgradeable (UUPS/TransparentProxy)? Or fixed deploy (requiring redeploy
   per SeparationRatioRegistry precedent)? Surface finding — determines
   whether Arc 4 redeploys or upgrades.

2. **Existing consent bitmask consumers.** Search for all callers of
   `VAPIConsentRegistry` across bridge code and contracts. Map every call
   site — consent manifest upgrade must not break any existing consumer.

3. **Migration path for existing consent records.** The bitmask
   `consent_bits` currently stored per device must map to manifest defaults.
   Document the exact migration logic before any contract change.

#### Arc 4 Consent Manifest Schema

```solidity
// VAPIConsentManifest struct (stored in upgraded VAPIConsentRegistry)
struct ConsentManifest {
    // Dimension 1 — Data categories (above the immutable floor)
    bool allowAggregateStats;
    bool allowSkillRankingProof;        // Tier 1
    bool allowTrajectoryProof;          // Tier 2
    bool allowContextPerformanceProof;  // Tier 3
    bool allowFullSessionProof;         // Tier 4

    // Dimension 2 — Buyer categories
    bool allowAcademic;
    bool allowGameDev;
    bool allowEsports;
    bool allowBrand;                    // explicit opt-in only
    bool allowAnonymous;                // explicit opt-in only

    // Dimension 3 — Aggregation floor
    uint16 minSessionsPerPackage;       // ≥10 (protocol minimum enforced on-chain)

    // Dimension 4 — Temporal cooling
    uint32 coolingPeriodHours;          // ≥72 (protocol minimum enforced on-chain)

    // Dimension 5 — Pricing
    uint256 minPriceVapi;               // in VAPI token units
    uint8   listingType;                // 0=fixed, 1=auction

    // Dimension 6 — ZK proof depth (covered by Tier bools above)

    // Dimension 7 — Autonomy level
    uint8   autonomyLevel;              // 0=manual, 1=approval, 2=notify, 3=full

    // Manifest versioning
    uint64  updatedAt;
    bytes32 manifestHash;               // sha256(canonical bytes of this struct)
}

// Protocol floor enforcement (on-chain, not bypassable)
modifier manifestFloors(ConsentManifest memory m) {
    require(m.minSessionsPerPackage >= 10, "aggregation floor: min 10 sessions");
    require(m.coolingPeriodHours >= 72, "cooling floor: min 72 hours");
    _;
}
```

Migration: existing consent_bits → manifest with equivalent category defaults.
Old `VAPIConsentRegistry.isConsented(deviceId)` still callable (compatibility).
New `VAPIConsentRegistry.getManifest(deviceId)` returns structured manifest.

P-check: full migration verified, all existing consent consumers still
function, manifest floors enforced on-chain, bridge reads manifest correctly.
**Hold for operator review before commit.**

---

## 9. Protocol Invariants — What Claude Code Must Never Modify

The following are FROZEN-v1 primitives. They cannot be changed without
an explicit governance ceremony (`vapi_invariant_gate.py --generate --confirm-governance`).
Attempting to modify them in any arc is a STOP condition.

### 9.1 The 13 Frozen PATTERN-017 Families

| # | Family | Purpose |
|---|---|---|
| 1 | VAPI-GIC-GENESIS-v1 | Grind integrity chain |
| 2 | VAPI-WEC-GENESIS-v1 | Watchdog event chain |
| 3 | VAPI-VAME-v1 | Verified API mediation |
| 4 | VAPI-CORPUS-SNAPSHOT-v1 | Calibration corpus integrity |
| 5 | VAPI-CONSENT-v1 | Gamer-sovereign consent bitmask |
| 6 | VAPI-PCC-v1 | Physical capture continuity |
| 7 | VAPI-FRR-v1 | Fleet readiness root |
| 8 | VAPI-AGENT-ROOT-v1 | Agent action commitment |
| 9 | VAPI-CEREMONY-v1 | MPC ceremony attestation |
| 10 | VAPI-OPERATOR-INITIATIVE-v1 | Operator phase ladder |
| 11 | VAPI-O3-SUPERSEDE-v1 | Cryptographic supersession |
| 12 | VAPI-IOSWARM-v1 | ioSwarm-coordinated quorum |
| 13 | QORTROLLER-IPACT-RENEWAL-v1 | VHP renewal cadence |

### 9.2 The 228-Byte PoAC Wire Format

**NEVER modified.** The entire data economy arc derives value FROM these
records. Their wire format is the foundation. Any arc that touches the
PoAC record format without explicit ceremony is invalid.

### 9.3 The Data Floor (Protocol Invariant, Not User Preference)

The following data categories are NEVER packaged, NEVER sold, NEVER
included in any ZK proof circuit input that reaches a buyer, under any
consent configuration:
- Raw 12-feature Mahalanobis vectors
- Raw trigger force curves (1 kHz)
- Raw IMU samples (250 Hz)
- Raw HID frame data (64-byte)

This is enforced in `CuratorPackagingLoop._apply_data_floor()` as a
`ProtocolViolationError` — not a warning, not a log — a hard exception.

### 9.4 The Consent Manifest Protocol Floors (On-Chain Enforced)

- Aggregation floor: `minSessionsPerPackage ≥ 10` (non-bypassable)
- Cooling period: `coolingPeriodHours ≥ 72` (non-bypassable)
- Buyer category: `competing_player_team` never allowed (non-bypassable)

---

## 10. Claude Code Process Patterns — Instructional Reference

Every implementation session follows this ritual without exception.

### 10.1 Verification-First Discipline

```
pre-implementation V-check (read-only, no code)
    ↓ hold for operator review
    ↓ findings surface drift, confirmed
implementation (commits in sequence, hold-gated)
    ↓ each commit: write → test → P-check
P-check (pytest + invariant gate + drift scanner)
    ↓ hold for operator review
atomic commit (reasoning preserved in commit body)
```

**Never bypass the hold steps to save tokens or session turns.**
The verification standard exists to catch drift in both directions.

### 10.2 Contract Deployment Pattern

```javascript
// Every deploy script follows this pattern
async function main() {
    const balance = await ethers.provider.getBalance(deployer);
    const estimate = await factory.getDeployTransaction(...args).then(
        tx => ethers.provider.estimateGas(tx)
    );
    const gasLimit = estimate.mul(125).div(100);  // estimate × 1.25 — NOT static
    if (balance.lt(gasLimit.mul(gasPrice).mul(2))) {
        throw new Error("ABORT: insufficient balance for deploy + 2× safety margin");
    }
    // ... deploy
}
// Always: ABORT guard → estimate_gas × 1.25 → deploy → log forensics
// forensics: tx hash, block number, gasUsed, IOTX cost → deployed-addresses.json
```

### 10.3 Deployed-Addresses.json Convention

```json
"VAPIBuyerRegistry": "0x<ADDR>",
"_vapiobuyerregistry_status": "LIVE (testnet)",
"_vapibuyerregistry_note": "Phase Data-Economy-Arc1 — buyer credential registry; attestedBy=Curator wallet; CATEGORY_ACADEMIC=1 FROZEN; deploy tx <HASH>; block <N>; gasUsed <G>; cost <X> IOTX; eth_getCode-verified"
```

### 10.4 Invariant Entry Pattern

```python
# vapi_invariant_gate.py — new INV entry structure
Invariant(
    id="INV-BUY-001",
    description="VAPIBuyerRegistry CATEGORY_ACADEMIC constant = 1 (FROZEN)",
    file="contracts/contracts/VAPIBuyerRegistry.sol",
    pattern=r"CATEGORY_ACADEMIC\s*=\s*1",
    min_matches=1,
)
```

### 10.5 Honesty Rails — Required in Every Arc

- `CuratorPackagingLoop` log on init: `"[CURATOR] Packaging loop active. Raw biometric data
  never packaged. Consent policy enforced per manifest hash [HASH]."`
- Session-status endpoint: `"curator_packaging": "pending_governance"` until governance
  ceremony complete; `"curator_packaging": "operational"` after.
- Every listing on VAPIDataMarketplace: `consent_policy_hash` field — the
  gamer's manifest hash at the time of listing. Auditable on-chain.
- If aggregation floor not met: defer, log `"DEFER: insufficient sessions
  for aggregation (have N, need 10)"` — not an error, not a failure.
- If cooling period active: defer, log `"DEFER: cooling period active until
  [timestamp]"` — not an error, not a failure.
- Autonomy level `approval_required` is the default. Never initialize
  a new gamer manifest with full_autonomy.

### 10.6 Key File Paths Reference

```
bridge/vapi_bridge/
├── curator_packaging_loop.py      [Arc 3 — to be created]
├── curator_attestation.py         [Arc 1 Commit 2 — to be created]
├── zk_buyer_verifier.py           [Arc 2 — to be created]
├── signing_backends/              [LIVE — SigningBackend abstraction]
│   ├── base.py                    [LIVE — SigningBackend Protocol]
│   ├── host_key.py                [LIVE — HostKeyBackend (Path B)]
│   └── secure_element.py          [HARDWARE-GATED — SecureElementBackend stub]
├── composite_device_identity.py   [LIVE — shim wrapping HostKeyBackend]
├── vhp_renewal_agent.py           [LIVE — VHP renewal with enforcement ON]
├── dualshock_integration.py       [LIVE — session lifecycle + casual trigger]
├── chain.py                       [LIVE — all on-chain view calls]
├── config.py                      [LIVE — all env-driven config]
└── operator_api.py                [LIVE — all bridge endpoints]

contracts/contracts/
├── VAPIManufacturerDeviceRegistry.sol  [LIVE — Path A Arc 1]
├── VAPIBuyerRegistry.sol               [Arc 1 — to be created]
├── VAPIBuyerCategoryVerifier.sol       [Arc 2 — to be created]
└── VAPIProtocolLensV2.sol              [LIVE — isFullyEligible_PathA()]

scripts/
├── provision_device_mfg.py         [LIVE — manufacturing ceremony tooling]
├── verify_device_cert.py           [LIVE — audit tool]
└── vapi_invariant_gate.py          [LIVE — 35 invariants, PV-CI gate]

docs/
├── path-a-manufacturing-spec.md    [LIVE — partner-facing hardware spec]
├── path-a-arc2-prompt.md           [HARDWARE-GATED — SecureElementBackend prompt]
└── casual-play-runbook.md          [LIVE — operator play guide]
```

---

## 11. Forward Path — Gates and Sequencing

### Immediate (Operator-Fired, No External Gates)

| Item | Action |
|---|---|
| Arc 2 (Path A hardware) | Order ATECC608A breakout + CH341A. Run `docs/path-a-arc2-prompt.md` on arrival. |
| Curator O2 SUGGEST graduation | Cedar bundle pre-authored. Fire when N≥50 review threshold met. |
| Additional device registrations | Any operator-owned controller → `provision_device_mfg.py --execute`. ~0.2 IOTX/device. |

### Data Economy Prerequisite (Operator-Executed Ceremony)

| Item | Action |
|---|---|
| Curator scope governance proposal | Submit to VAPIBiometricGovernance. Scope manifest specifies: autonomous marketplace-listing, ZK proof generation, buyer attestation. Gate for all Data Economy arcs. |

### Data Economy Arcs (Post-Governance, Sequenced)

```
Governance ceremony
      ↓
Data Economy Arc 1 — VAPIBuyerRegistry (~2 weeks)
      ↓
Data Economy Arc 2 — ZK Buyer Category Verifier (~2 weeks)
      ↓
Data Economy Arc 3 — Post-Session Packaging Loop (~2 weeks)
      ↓
Data Economy Arc 4 — Consent Manifest Upgrade (~1-2 weeks)
      ↓
Flywheel operational
```

### Calibration-Gated (~Weeks of Capture)

| Item | Gate |
|---|---|
| PoEP activation | N≥50 calibration sessions per player |
| L4 v2 sensor stack | Empirical Unknown #1 + #4 (physical capture sessions) |
| L8 BT calibration | BlueZ + USB BT dongle + capture sessions |

### External / Partner-Gated

| Item | Gate |
|---|---|
| IIP-64 design partnership | @cryptoxfan engagement on PR #72 |
| First manufacturer partner | Traction from gameplay + TGE receipts |
| Tournament operator integration | VAPIProtocolLensV2.isFullyEligible_PathA() → one eth_call |
| Mainnet TGE | Wallet refill + Phase 99 deploy (separation_ratio > 1.0 cleared: 1.199, N=37) |
| Repo flip private → open | Merge PR #8 + secrets audit + README update |

---

## 12. The Load-Bearing Question

The protocol's load-bearing question for the next 30-90 days is no longer
"can we build this?" — that question is answered. It is:

> **Does the gaming industry want to be V.A.P.I.-native?**

The technical scaffolding is sufficiently demonstrated that the answer becomes
a market question, not an engineering one. The data economy layer — if built
through these four arcs — makes staying V.A.P.I.-native economically rational
for gamers, not just technically interesting. That is the flywheel that
carries adoption from early demonstrators to ecosystem.

The arc from "anti-cheat protocol" to "gamer-sovereign data economy" is not
a pivot. It is the protocol's architecture revealing its full shape. Anti-cheat
is the wedge. Sovereign data is the long-term value capture. They are the same
system. The proof of humanity IS the data provenance.

---

*Document generated: 2026-05-27*
*Based on: QorTroller Extraordinary Comprehensive Assessment + Data Economy*
*Framework design session*
*Claude Code instructional instrument — load this document at session start*
*for any Data Economy arc implementation*
