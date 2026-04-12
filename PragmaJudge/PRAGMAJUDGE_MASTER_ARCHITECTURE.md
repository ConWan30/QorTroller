# PRAGMAJUDGE — Master Architectural Framework
## Claude Code Context Document · Phase 201+ · Sub-Protocol of VAPI

**Document Purpose:** This file is the authoritative context document for Claude Code
when building PragmaJudge. Every decision, every new file, every new contract, every
new agent must be validated against this document before implementation. This document
is not aspirational — it describes what exists in VAPI (Phase 200) and exactly how
PragmaJudge extends it. Nothing in VAPI's existing codebase is modified. PragmaJudge
is an additive layer only.

**Repository Location:** `C:\Users\Contr\vapi-pebble-prototype\pragmajudge\`

**Research Foundation:** Frameworks sourced from
`PragmaJudge__A_Cross-Disciplinary_Architecture_for_Physical_Intelligence_Accountability.md`
correlated throughout this document against VAPI Phase 200 infrastructure.

---

## SECTION 0 — INVIOLABLE BUILD RULES FOR CLAUDE CODE

These rules have no exceptions. Any build instruction that would violate them must be
refused and flagged to the human orchestrator immediately.

**RULE 0.1 — VAPI CODEBASE IS READ-ONLY.**
Claude Code must never modify any file in `bridge/vapi_bridge/`, any existing agent
file, `store.py`, `config.py`, `chain.py`, `federation_bus.py`, or any existing
Solidity contract. All PragmaJudge code lives exclusively under `pragmajudge/`.

**RULE 0.2 — PITL LAYERS ARE UNTOUCHABLE.**
PragmaJudge must never read, reference, modify, or depend on the PITL detection
stack internals: L0–L6 layer logic, the 228-byte PoAC wire format fields, the
Mahalanobis L4 feature computation, IMU tremor detection, or the HID bridge loop.
PragmaJudge's only permitted interface with VAPI's detection output is consuming
the VHP credential via `isFullyEligible(deviceId)` — one composable view call.

**RULE 0.3 — FROZEN INVARIANTS ARE IMMUTABLE.**
The following constants appear in VAPI and must never be changed by any PragmaJudge
code under any circumstance:

```
epistemic_consensus_threshold = 0.65       # Phase 147 hardened
BLOCK_QUORUM                  = 0.67       # Phase 109A floor
MINT_QUORUM                   = 0.80       # Phase 110 floor
PoAC wire format              = 228 bytes  # Phase 1, frozen
chain_link_hash               = SHA-256(raw[0:164])  # body only
device_id                     = keccak256(pubkey)
hard_cheat_codes              = {0x28, 0x29, 0x2A}
L4_anomaly_threshold          = 7.009
L4_continuity_threshold       = 5.367
```

**RULE 0.4 — DRY_RUN DEFAULT.**
All new PragmaJudge agents must initialize with `dry_run=True` by default, mirroring
VAPI's SessionAdjudicator pattern. No real vault disbursements, no real PRAGMA mints,
no real on-chain writes until `dry_run=False` is explicitly set by the operator.

**RULE 0.5 — FEDERATION BUS IS APPEND-ONLY.**
PragmaJudge agents subscribe to the existing `federation_bus` event channel and
publish new event types. They must never modify or intercept existing VAPI event
handlers. New event types are prefixed `PRAGMA_` to avoid collision.

**RULE 0.6 — SOURCE TYPE ISOLATION.**
When PragmaJudge writes to any shared VAPI registry (e.g., AdjudicationRegistry.sol),
it must always pass `source_type="PRAGMA_JUDGE"`. This isolates PragmaJudge records
from VAPI records in all queries and analytics.

**RULE 0.7 — SEQUENCING GATE.**
PragmaJudge build phases are gated behind VAPI milestones. Claude Code must check
gate status before implementing vault disbursements or PRAGMA minting:
- Gate 1: `separation_ratio > 1.0` AND `ALL_PAIRS_GATE_ENABLED=true`
- Gate 2: `N >= 100` live non-dry-run VAPI adjudications with zero false positives
- Gate 3: VHP end-to-end demonstrated on IoTeX testnet
PragmaJudge infrastructure can be built and tested before these gates. Real economic
operations (vault disbursements, token minting) activate only after gates clear.

---

## SECTION 1 — WHAT VAPI HAS ALREADY BUILT (CONSUMED BY PRAGMAJUDGE)

This section documents every VAPI component that PragmaJudge treats as a dependency.
Claude Code must understand these thoroughly before writing a single line of new code.

### 1.1 The Human Identity Primitive

**Contract:** `PHGCredential` (ERC-4671 soulbound token)
**Contract:** `VAPIProtocolLens` — exposes `isFullyEligible(deviceId)`
**Contract:** `VAPIDualPrimitiveGate` at `0xd7b146...` — `isDualEligible()`
**Contract:** `VAPIioIDRegistry` — device DID: `did:io:0x<addr>`

PragmaJudge's single point of contact with VAPI's identity layer is one view call:

```solidity
// PragmaJudge gates every session on this. Zero gas. Zero new infrastructure.
bool humanVerified = VAPIProtocolLens.isFullyEligible(deviceId);
require(humanVerified, "VHP credential required for PragmaJudge session");
```

The PHGCredential's `expiresAt` field is automatically respected — an expired credential
returns `false` from `isFullyEligible()`. PragmaJudge does not need to implement TTL
checking; VAPI's existing BiometricCredentialTTLAgent (Phase 178) handles it.

What this means programmatically: every `PromptCommitmentRegistry.sol` function that
initiates a PragmaJudge session must call `isFullyEligible()` first. If it returns
`false`, the transaction reverts. This is the only PragmaJudge dependency on VAPI's
biometric infrastructure.

### 1.2 The Verdict Anchoring Registry

**Contract:** `AdjudicationRegistry` at `0x44CF98...` on IoTeX Testnet (chain ID 4690)

VAPI uses this contract to anchor PoAd (Proof of Adjudication) hashes with
`block.number` timestamps. PragmaJudge reuses this registry for verdict anchoring
by passing `source_type="PRAGMA_JUDGE"` as a distinguishing parameter.

```solidity
// PragmaJudge writes verdicts here. VAPI writes PoAd hashes here.
// The registry holds both. Source type separates them in queries.
AdjudicationRegistry.anchorVerdict(
    verdict_hash,       // SHA-256(verdict_json)
    session_id,         // PragmaJudge session ID
    "PRAGMA_JUDGE"      // source type — mandatory
);
```

Claude Code must never modify AdjudicationRegistry.sol. It is consumed as-is.

### 1.3 The ZK Proof Infrastructure

**Contract:** `PITLSessionRegistryV2` at `0x8da0A4...`
**Contract:** `PitlSessionProofVerifier` at `0x07D3ca...`
**Circuit:** `PitlSessionProof.circom` — Groth16/BN254, ~1,820 constraints
**Proving system:** Groth16 on BN254 curve
**Powers of tau:** 2^11
**Ceremony:** Phase 67, 3 contributors, verified via `CeremonyRegistry.sol` at `0x739B5f...`

PragmaJudge introduces a new circuit `PragmaIntentProof.circom` that uses the same
Groth16/BN254 proving system and the same ptau powers-of-tau from Phase 67. It does
not require a new MPC ceremony if constraint count stays below 2^11 = 2,048.

The research paper's ZK-PoP construction (192-byte proofs, 8.2ms verification) maps
directly onto this infrastructure. PragmaJudge's new circuit proves:
- C1: `intentCommitment = Poseidon(8)(embeddingFeatures[0..6], speechActCode)`
- C2: `fidelityScore >= fidelityThreshold` (output served committed intent)
- C3: `verdictCode === verdictFromConsensus` (prevents verdict forgery, mirrors VAPI Phase 62)

New verifier contract `PragmaIntentProofVerifier.sol` is deployed separately. It does
not modify or extend `PitlSessionProofVerifier`.

### 1.4 The Ruling Commit-Reveal Pattern

**Contract:** `RulingRegistry` at `0xa3A235...`
**Pattern:** `commitment_hash = SHA-256(verdict + sorted(evidence_hashes) + attestation_hash_hex + struct.pack(">Q", ts_ns))`

PragmaJudge adopts this exact commitment formula for its own verdict commitments,
substituting PragmaJudge-specific evidence fields:

```python
# PragmaJudge verdict commitment — mirrors VAPI Phase 66 pattern exactly
pragma_commitment_hash = SHA256(
    verdict_code +                    # SATISFIED | FAILED | PARTIAL | ESCALATED
    sorted(agent_evidence_hashes) +   # from OutputFidelityJudge agents
    intent_commitment_hash +          # from PromptCommitmentRegistry
    struct.pack(">Q", ts_ns)          # nanosecond timestamp
)
```

This is not a modification of RulingRegistry.sol. PragmaJudge deploys its own
`PragmaVerdictRegistry.sol` using the same anti-replay and commitment pattern.

### 1.5 The Epistemic Consensus Fleet

**Existing fleet:** 36 agents, all running as background asyncio tasks in `bridge_agent.py`
**Bus:** `federation_bus` — internal async event channel
**Threshold:** `epistemic_consensus_threshold = 0.65` (frozen, Phase 147)
**Consensus formula (swarm on):** `{0.35 ClassJ, 0.35 Supervisor, 0.15 Triage, 0.15 ioSwarm}`
**Triage prerequisite:** `triage_prereq_required=True` — Triage signal must be present

PragmaJudge adds four new semantic agents to this fleet. They do not replace or modify
any of the 36 existing agents. They run as additional asyncio tasks in the same runtime,
subscribe to federation_bus, and publish PRAGMA_-prefixed events. The consensus fleet
grows from 36 to 40 agents when PragmaJudge is active.

The research paper's AgentAuditor framework (arXiv:2602.09341) — which builds Reasoning
Trees from agent evaluations and identifies Critical Divergence Points — is implemented
as the `PragmaConsensusArbiter` agent's internal logic, not as a modification to the
existing `EpistemicConsensusGate` agent (Agent #24).

The research paper's hinTS threshold BLS signatures (896 bytes, 390K gas constant
verification) are the target implementation for PragmaJudge's multi-agent verdict
signing. This is a new cryptographic primitive that supplements VAPI's existing ECDSA-P256
signing without replacing it.

### 1.6 The ioSwarm Decentralized Consensus Layer

**IoSwarmAdjudicationCoordinator** (Phase 109C): dual-quorum, BLOCK_QUORUM=0.67
**IoSwarmVHPMintCoordinator** (Phase 110): MINT_QUORUM=0.80, fail-closed
**IoSwarmRenewalCoordinator** (Phase 109B): CERTIFY_RENEW_QUORUM=0.60
**Current state:** `IOSWARM_ENABLED=true` (emulator mode, Phase 200)

PragmaJudge introduces a fourth ioSwarm coordinator: `IoSwarmPragmaVerdictCoordinator`.
This coordinator routes PragmaJudge SATISFIED/FAILED verdicts through ioSwarm consensus
before any PragmaVault disbursement executes. The quorum for vault disbursements mirrors
MINT_QUORUM=0.80 (irreversible economic action). The quorum for FAILED verdicts
(reversible — no disbursement) mirrors BLOCK_QUORUM=0.67.

The existing three coordinators are not modified.

### 1.7 The FleetSignalCoherenceAgent

**Agent #33** (Phase 193): always-on, `fleet_coherence_enabled=True`
**Coherence ID format:** `"coh_" + SHA-256[:16]`
**Auto-promotes to VAPI_WHAT_IF.md:** persistent contradictions after N_PROMOTE_THRESHOLD=3
**BP-007:** `_scrub_evidence()` removes raw biometric fields from evidence_json

PragmaJudge verdict contradictions (e.g., OutputFidelityJudge agents disagree with
PragmaConsensusArbiter) are automatically detected by FleetSignalCoherenceAgent because
it monitors all federation_bus events. PragmaJudge does not need to implement its own
coherence monitoring — it inherits this capability by publishing to the shared bus.

PragmaJudge adds three new coherence rules to FleetSignalCoherenceAgent's ruleset
(appended, not replacing existing 15 rules):
- **PRAGMA-C1 (CONTRADICTION):** `SATISFIED` verdict with `implicit_satisfaction_score < 0.3`
- **PRAGMA-C2 (ORPHAN):** Intent commitment with no linked agent verdict after 30 minutes
- **PRAGMA-C3 (INVERSION):** Vault disbursement timestamp precedes verdict commitment timestamp

These rules are injected via a new configuration file `pragmajudge/coherence_rules.py`
that FleetSignalCoherenceAgent imports on startup. No modification to the agent itself.

### 1.8 The SQLite Persistence Layer

**File:** `store.py` — 100+ tables, full audit trail
**Pattern:** All new PragmaJudge tables follow VAPI's existing table naming and schema conventions

PragmaJudge adds the following new tables to the SQLite store. These are created via
migration scripts in `pragmajudge/migrations/`. They do not alter existing VAPI tables.

```sql
-- Core PragmaJudge tables (new, additive only)
CREATE TABLE pragma_sessions (
    id INTEGER PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,      -- PragmaJudge session UUID
    device_id TEXT NOT NULL,              -- keccak256(pubkey) from VAPI
    vhp_verified INTEGER NOT NULL,        -- 1 if isFullyEligible() passed
    intent_commitment_hash TEXT,          -- Poseidon hash of intent embedding
    platform_stake_amount REAL,           -- credits staked by platform
    verdict_code TEXT,                    -- SATISFIED|FAILED|PARTIAL|ESCALATED
    verdict_commitment_hash TEXT,         -- anti-replay commitment
    fidelity_score REAL,                  -- cosine distance: intent vs output
    implicit_satisfaction_score REAL,     -- behavioral inference score
    vault_disbursed INTEGER DEFAULT 0,    -- 1 if reimbursement executed
    dry_run INTEGER DEFAULT 1,            -- mirrors VAPI dry_run pattern
    created_at INTEGER,                   -- nanosecond timestamp
    updated_at INTEGER
);

CREATE TABLE pragma_intent_records (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    speech_act_code TEXT,                 -- DIRECTIVE|ASSERTIVE|COMMISSIVE|EXPRESSIVE|DECLARATIVE
    surface_intent_hash TEXT,             -- Poseidon(literal prompt embedding)
    instrumental_intent_hash TEXT,        -- Poseidon(inferred use-case embedding)
    terminal_intent_hash TEXT,            -- Poseidon(underlying goal embedding)
    gricean_implicature_json TEXT,        -- structured implicature extraction
    embedding_dim INTEGER DEFAULT 384,    -- all-MiniLM-L6-v2 output dimension
    created_at INTEGER
);

CREATE TABLE pragma_agent_verdicts (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,               -- e.g., "output_fidelity_judge_1"
    agent_ioID TEXT,                      -- did:io:0x<addr> of agent identity
    verdict_code TEXT,                    -- SATISFIED|FAILED|PARTIAL
    confidence REAL,                      -- 0.0–1.0
    fidelity_score REAL,
    reasoning_tree_json TEXT,             -- AgentAuditor reasoning tree
    dissent_recorded INTEGER DEFAULT 0,   -- 1 if minority report filed
    created_at INTEGER
);

CREATE TABLE pragma_vault_ledger (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_type TEXT,                      -- STAKE|DISBURSEMENT|REFUND|SLASH
    amount REAL,
    currency TEXT DEFAULT 'PRAGMA',
    from_address TEXT,
    to_address TEXT,
    on_chain_tx TEXT,                     -- IoTeX tx hash
    dry_run INTEGER DEFAULT 1,
    created_at INTEGER
);

CREATE TABLE pragma_pil_records (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    -- Physical Input Layer (PIL) biometric fields
    keystroke_timing_jitter_variance REAL,
    mouse_tremor_peak_hz REAL,
    mouse_tremor_band_power REAL,
    idle_micro_movement_variance REAL,
    reading_pause_duration_ms REAL,
    compositional_error_rate REAL,
    temporal_rhythm_cv REAL,              -- coefficient of variation
    cross_layer_coherence_score REAL,     -- PIL multi-signal coherence
    human_presence_probability REAL,
    pil_inference_code TEXT,              -- NOMINAL|AI_DETECTED|ANOMALY
    created_at INTEGER
);

CREATE TABLE pragma_coherence_log (
    id INTEGER PRIMARY KEY,
    coherence_id TEXT UNIQUE,             -- "coh_" + SHA-256[:16] (VAPI pattern)
    rule_id TEXT,                         -- PRAGMA-C1|PRAGMA-C2|PRAGMA-C3
    session_id TEXT,
    severity TEXT,                        -- INFO|WARNING|CRITICAL
    description TEXT,
    evidence_json TEXT,                   -- BP-007 scrubbed
    resolved INTEGER DEFAULT 0,
    promoted_to_whatif INTEGER DEFAULT 0,
    created_at INTEGER
);

CREATE TABLE pragma_minority_reports (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    dissenting_agent_id TEXT,
    majority_verdict TEXT,
    dissent_verdict TEXT,
    dissent_reasoning TEXT,               -- full reasoning tree of dissent
    critical_divergence_point TEXT,       -- AgentAuditor CDP
    fed_to_automl INTEGER DEFAULT 0,      -- 1 when routed to rubric improvement
    created_at INTEGER
);
```

### 1.9 The AutoResearch Wiki Loop

**Files:** `VAPI_WHAT_IF.md`, `VAPI_MEMORY.md`, `skill.md` delta pattern
**Trigger:** FleetSignalCoherenceAgent auto-promotes after N_PROMOTE_THRESHOLD=3
**Pattern:** Every PragmaJudge cycle produces: skill.md delta + WHAT_IF addition + experiment log

PragmaJudge creates a parallel documentation loop in `pragmajudge/docs/`:
- `PRAGMA_WHAT_IF.md` — PragmaJudge-specific contradiction promotions
- `PRAGMA_MEMORY.md` — PragmaJudge calibration state
- `PRAGMA_RUBRIC_DELTA.md` — rubric evolution from minority report corpus

The AutoResearch loop for PragmaJudge feeds the Marshall DAO governance pipeline
for rubric evolution proposals. This is new infrastructure but follows VAPI's exact
documentation-as-code pattern.

### 1.10 The Token Infrastructure

**Contract:** `VAPIToken` — ERC-20, 1B fixed supply, IoTeX L1
**Contract:** `VAPIOperatorRegistry` — minimum 10,000 VAPI locked stake
**Bridge:** LayerZero V2 OApp for cross-chain token movement

PragmaJudge introduces a companion token `PRAGMA` (separate ERC-20, separate supply).
PRAGMA is not a fork of VAPIToken — it is a new contract `PRAGMAToken.sol` with its
own tokenomics. Agents earn PRAGMA only on SATISFIED verdicts. PragmaVault holds
both PRAGMA and USDC/IOTX as staking assets.

The LayerZero V2 integration pattern from VAPI's VAPIToken is replicated for PRAGMA's
cross-chain vault mechanics. Claude Code implements `PRAGMAToken.sol` following the
exact same operator-mint, lock/unlock, and LayerZero OApp patterns as VAPIToken.

---

## SECTION 2 — WHAT PRAGMAJUDGE BUILDS NEW

This section documents every new component PragmaJudge introduces. Everything here
is net-new code in the `pragmajudge/` folder.

### 2.1 New Smart Contracts (IoTeX Testnet, chain ID 4690)

All contracts follow VAPI's existing Solidity patterns: CEI pattern, OpenZeppelin
imports, anti-replay commitments, fail-closed defaults, and VAPI's event naming
conventions. All are deployed on IoTeX Testnet before any mainnet consideration.

**`PromptCommitmentRegistry.sol`**
The entry point for every PragmaJudge session. Accepts a prompt commitment hash, a
platform stake, and a deviceId. Calls `VAPIProtocolLens.isFullyEligible(deviceId)`
before accepting. Stores the Pedersen vector commitment to the intent embedding.
Implements commit-then-reveal pattern mirroring `SeparationRatioRegistry.sol`.

Key functions:
```solidity
function commitPrompt(
    bytes32 intentCommitment,  // Poseidon hash of embedding vector
    bytes32 speechActCode,     // keccak256("DIRECTIVE"|"ASSERTIVE"|etc.)
    bytes32 deviceId,          // from VAPI ioID registry
    uint256 platformStake      // credits locked in PragmaVault
) external returns (bytes32 sessionId);

function revealVerdict(
    bytes32 sessionId,
    bytes32 verdictCommitment, // anti-replay commitment hash
    uint8 verdictCode          // 0x00=SATISFIED, 0x01=FAILED, 0x02=PARTIAL
) external;
```

**`PragmaVault.sol`**
Holds platform stakes and manages disbursements. On FAILED verdict confirmed by
ioSwarm quorum (0.80), automatically transfers stake-equivalent credits to user.
On SATISFIED verdict, releases stake back to platform with zero penalty.
Fail-closed: no disbursement without ioSwarm MINT_QUORUM=0.80 confirmation.
Mirrors VAPI's `VAPIGovernanceTimelock.sol` CEI + co-signer cancel pattern for
large disbursements above a configurable threshold.

Key functions:
```solidity
function stake(bytes32 sessionId, uint256 amount) external;
function disburse(bytes32 sessionId) external;  // called by IoSwarmPragmaVerdictCoordinator
function refund(bytes32 sessionId) external;    // on SATISFIED verdict
function getVaultBalance() external view returns (uint256);
```

**`PragmaVerdictRegistry.sol`**
Anchors verdict commitment hashes with block.number timestamps. Anti-replay via
UNIQUE `commitmentHash` constraint (mirrors `RulingRegistry.sol`). Stores
`source_type="PRAGMA_JUDGE"` on every record. Provides the on-chain audit trail
required by EU AI Act Article 12.

**`PragmaIntentProofVerifier.sol`**
Groth16 verifier for `PragmaIntentProof.circom`. Deployed separately from
`PitlSessionProofVerifier`. Uses same BN254 curve and ptau from Phase 67 ceremony
(no new MPC ceremony required if constraint count ≤ 2,048). Verifies:
- C1: intent commitment binding
- C2: fidelity score above threshold
- C3: verdict code matches consensus output

**`PRAGMAToken.sol`**
ERC-20, separate from VAPIToken. Fixed supply TBD (configured pre-TGE). Operator-
mint pattern identical to VAPIToken. LayerZero V2 OApp for cross-chain vault mechanics.
`tgeComplete` flag blocks all minting post-TGE. Staking/lock/unlock mirrors
`VAPIOperatorRegistry` pattern.

**`PragmaEloRegistry.sol`**
Rolling AI platform quality ELO computed from PragmaJudge verdict chains. Mirrors
VAPI's `SkillOracle.sol` pattern exactly — ELO computed from verdict sequences, not
from raw scores. Platform ELO is queryable by any downstream contract.

**`PragmaDataSovereigntyRegistry.sol`**
Consent registry for PIL behavioral biometric data. Three licensing tiers:
PLATFORM (AI quality improvement) / RESEARCHER (academic study) / USER (personal
analytics). Mirrors VAPI's `DataSovereigntyRegistry.sol` pattern with PRAGMA token
rewards replacing VAPI token rewards for consented data licensing.

**`IoSwarmPragmaVerdictCoordinator.sol`**
Fourth ioSwarm coordinator (alongside VAPI's three). VAULT_QUORUM=0.80 for
disbursements (irreversible). VERDICT_QUORUM=0.67 for FAILED verdicts (reversible).
Fail-closed for disbursements. Swarm fingerprint = SHA-256(sorted_verdicts +
fidelity_score + ts_ns). Emulator mode matches VAPI's existing pattern.

### 2.2 New ZK Circuit

**`PragmaIntentProof.circom`**
Proving system: Groth16 on BN254. Target constraint count: ~1,500–2,000 (within
Phase 67 ptau 2^11). Three constraints:

```
C1: intentCommitment = Poseidon(8)(scaledEmbedding[0..6], speechActCode)
    -- Binds the semantic embedding of the prompt to its speech act classification.
    -- Mirrors VAPI's C1: featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)

C2: fidelityScore >= fidelityThreshold
    -- Proves AI output embedding cosine similarity exceeds the committed threshold.
    -- Mirrors VAPI's C2: anomalyScore <= anomalyThreshold

C3: verdictCode === verdictFromConsensus
    -- Prevents verdict forgery. Mirrors VAPI's Phase 62 C3 exactly.
```

Public signals (nPublic=5, mirrors VAPI's nPublic=5):
1. `intentCommitment` — Poseidon hash binding prompt embedding to speech act
2. `fidelityScore` — cosine distance between intent and output embeddings (public)
3. `fidelityThreshold` — current calibrated threshold (configurable, not frozen)
4. `sessionId` — links to on-chain PragmaJudge session
5. `verdictCode` — must match consensus output from agent fleet

### 2.3 New Agents (Agents #37–#41)

All new agents are implemented as Python asyncio classes in `pragmajudge/agents/`.
They follow VAPI's exact agent architecture: polling cycle, federation_bus subscription,
store interaction, tool bindings, LLM backing where appropriate. All initialize with
`dry_run=True`. All use `claude-sonnet-4-6` where LLM is required.

---

**Agent #37 — PromptIntentExtractor**

*Role:* Receives raw prompt text (off-chain, never stored), extracts three-layer intent
graph, classifies speech act, extracts Gricean implicatures, and produces the structured
intent JSON that feeds the commitment circuit.

*Implementation pattern:* Mirrors VAPI's `CalibrationIntelligenceAgent` (Phase 50) —
event consumer, not a polling agent. Fires on `PRAGMA_SESSION_INITIATED` bus event.

*Research framework:* Implements speech act theory taxonomy from Williams & Bayne (2024)
— DIRECTIVE, ASSERTIVE, COMMISSIVE, EXPRESSIVE, DECLARATIVE classifications. Extracts
Gricean implicatures using the research finding that LLMs score 20-60% on implicature
tasks, making external verification essential.

*Key outputs:*
```python
@dataclass
class IntentGraph:
    surface_intent_embedding: np.ndarray    # 384-dim, all-MiniLM-L6-v2
    instrumental_intent_embedding: np.ndarray
    terminal_intent_embedding: np.ndarray
    speech_act_code: str                    # DIRECTIVE|ASSERTIVE|etc.
    gricean_implicatures: dict              # structured extraction
    commitment_hash: str                    # Poseidon(embedding[0..6], speech_act)
    confidence: float                       # 0.0–1.0
```

*Tools:* 6 tools (#150–#155 in catalog)
*Bus events published:* `PRAGMA_INTENT_EXTRACTED`
*Bus events consumed:* `PRAGMA_SESSION_INITIATED`

---

**Agent #38 — OutputFidelityJudge (×3 instances: OFJ-1, OFJ-2, OFJ-3)**

*Role:* Each instance independently evaluates whether the AI output's semantic
embedding satisfies the committed intent embedding within the fidelity threshold.
Three independent instances implement the CollabEval three-phase protocol from the
research paper: independent evaluation → structured panel debate → cross-panel synthesis.

*Implementation pattern:* Mirrors VAPI's `ClassJAgent` (Phase 81) — epistemic specialist
with weighted contribution to consensus. Each OFJ instance has weight 0.233 in the
PragmaJudge consensus formula (3 × 0.233 = 0.699, leaving 0.301 for PragmaConsensusArbiter
integration with ioSwarm).

*Research framework:* Implements AgentAuditor Reasoning Tree construction (arXiv:2602.09341).
Each OFJ builds a hypothesis tree from the output evaluation, identifies Critical Divergence
Points (CDPs) where its analysis diverges from prior OFJ instances, and files a formal
dissent record when it disagrees with the emerging consensus. RBTS scoring (Robust Bayesian
Truth Serum) incentivizes truthful evaluation: each OFJ submits a quality score plus a
prediction of other OFJ scores. Agents are rewarded when their evaluation is "surprisingly
common" and their prediction is accurate.

*Key computation:*
```python
# Fidelity score: cosine distance between committed intent and AI output embeddings
# Matches research paper's Groth16 circuit for semantic intent commitment
fidelity_score = cosine_similarity(intent_embedding, output_embedding)

# Mahalanobis-style threshold check (mirrors VAPI's L4 pattern)
# fidelity_threshold is calibrated per platform, not globally frozen
satisfied = fidelity_score >= platform_fidelity_threshold

# RBTS scoring
rbts_score = bts_information_score(my_verdict, predicted_peer_verdicts)
             + quadratic_prediction_score(my_prediction, actual_peer_verdicts)
```

*Minority Report Protocol:* When an OFJ instance votes against the majority, it
automatically files a `pragma_minority_reports` record containing its full Reasoning
Tree and the CDP that caused divergence. After 3 occurrences of the same CDP pattern,
FleetSignalCoherenceAgent auto-promotes to `PRAGMA_WHAT_IF.md`.

*Tools:* 9 tools per instance (#156–#164 for OFJ-1, #165–#173 for OFJ-2, #174–#182 for OFJ-3)
*Bus events published:* `PRAGMA_OFJ_VERDICT_{1|2|3}`
*Bus events consumed:* `PRAGMA_INTENT_EXTRACTED`, `PRAGMA_OUTPUT_RECEIVED`

---

**Agent #39 — PragmaConsensusArbiter**

*Role:* Aggregates OFJ verdicts, integrates PIL human-presence signal, applies the
weighted consensus formula, produces the final PragmaJudge verdict, triggers
IoSwarmPragmaVerdictCoordinator, and routes vault disbursement or refund.

*Implementation pattern:* Mirrors VAPI's `EpistemicConsensusGate` (Agent #24, Phase 98)
— aggregates signals, applies frozen threshold, emits authoritative verdict.

*Consensus formula:*
```python
# PragmaJudge consensus formula
# Note: epistemic_consensus_threshold = 0.65 is inherited from VAPI — FROZEN
pragma_consensus = (
    0.233 * p_OFJ1 +         # OutputFidelityJudge instance 1
    0.233 * p_OFJ2 +         # OutputFidelityJudge instance 2
    0.233 * p_OFJ3 +         # OutputFidelityJudge instance 3
    0.15  * p_PIL  +          # Physical Input Layer human-presence score
    0.10  * p_ioSwarm +       # IoSwarmPragmaVerdictCoordinator
    0.05  * p_implicit        # Implicit satisfaction signal (behavioral)
)
# Verdict: SATISFIED if pragma_consensus >= 0.65, else FAILED
verdict = "SATISFIED" if pragma_consensus >= 0.65 else "FAILED"
```

*Research framework:* Implements the five-layer consensus stack from the research paper:
- Layer 0 (Byzantine foundation): Tolerates f≤1 Byzantine OFJ agent (n=3 > 3×1+1)
- Layer 1 (Liquid democracy): OFJ agents delegate to domain specialists for complex rubrics
- Layer 2 (Deliberation): CollabEval three-phase protocol across OFJ instances
- Layer 3 (Weighted consensus): RBTS-calibrated weights (better-calibrated OFJs get bonus)
- Layer 4 (Meta-governance): Futarchy rubric selection (post-Gate 2)

*hinTS Implementation:* When ≥2 of 3 OFJ agents agree (threshold ≥0.65), PragmaConsensusArbiter
collects partial BLS signatures from each agreeing agent and aggregates into a single
896-byte SNARK-verified signature for on-chain settlement. This is the research paper's
hinTS construction applied to PragmaJudge's 3-agent sub-consensus. The full 36-agent
fleet threshold remains at 0.65 × 36 = 24 agents for ioSwarm confirmation.

*Tools:* 12 tools (#183–#194 in catalog)
*Bus events published:* `PRAGMA_VERDICT_FINAL`, `PRAGMA_VAULT_TRIGGER`
*Bus events consumed:* `PRAGMA_OFJ_VERDICT_1`, `PRAGMA_OFJ_VERDICT_2`, `PRAGMA_OFJ_VERDICT_3`, `PRAGMA_PIL_SIGNAL`

---

**Agent #40 — PILMonitorAgent (Physical Input Layer Monitor)**

*Role:* Monitors keyboard, mouse, and touchpad signals from the user's PC during
AI interaction sessions. Computes the PIL biometric features that distinguish human
from AI-operated sessions. Produces `human_presence_probability` as a continuous
signal fed to PragmaConsensusArbiter.

*Implementation pattern:* Mirrors VAPI's `BridgeAgent` (Phase 50) for peripheral
monitoring — asyncio HID/input event reader — but reads from PC input devices rather
than a DualShock Edge controller. Uses the same asyncio event loop, same store write
patterns, same polling frequency.

*Research framework:* Implements the Physical Input Layer (PIL) detection stack from
PragmaJudge's architecture. Five detection signals:

```python
# PIL Detection Stack (analogous to VAPI's PITL Nine Layers)
PIL_K = keystroke_dynamics_features()     # timing jitter, dwell, flight time
PIL_M = mouse_movement_biometrics()       # tremor 8-12Hz, overshoot, micro-drift
PIL_S = scroll_reading_behavior()         # pause duration vs content length
PIL_I = idle_micro_movement()             # involuntary cursor drift at rest
PIL_X = cross_layer_coherence()           # temporal binding across all signals

# Human presence probability (mirrors VAPI's humanity_probability formula)
human_presence_probability = (
    0.28 * p_PIL_K +    # keystroke dynamics (research: 91% cognitive fatigue accuracy)
    0.27 * p_PIL_M +    # mouse tremor (same 8-12Hz band as VAPI controller IMU)
    0.20 * p_PIL_S +    # scroll/reading behavior
    0.15 * p_PIL_I +    # idle micro-movement
    0.10 * p_PIL_X      # cross-layer coherence
)

# Hard detection (mirrors VAPI's hard cheat codes 0x28-0x2A)
# PIL_HARD_AI_DETECTED blocks session eligibility unconditionally
if keystroke_cv < AI_SPEED_THRESHOLD:
    pil_inference_code = "PIL_AI_DETECTED"   # inference code 0x40 (new, PragmaJudge only)
```

*Mobile extension:* On mobile devices, PIL_K maps to tap timing dynamics, PIL_M maps
to swipe gesture IMU (BioMoTouch framework: EER 0.27%), PIL_S maps to scroll velocity
patterns, and PIL_I maps to device hold tremor. The same feature computation pipeline
runs on both desktop and mobile — only the input source changes.

*TinyML implementation:* PIL feature models (LSTM/1D-CNN, INT8 quantized, <500KB) run
on-device via TinyML inference, matching the research paper's <500ms, <1mW constraint.
Model updates flow via W3bstream secure aggregation with differential privacy (ε=4).

*Consent gate:* `PIL_MONITORING_CONSENT_REQUIRED=True` — PIL monitoring activates only
after explicit user consent recorded in `PragmaDataSovereigntyRegistry.sol`.

*Tools:* 8 tools (#195–#202 in catalog)
*Bus events published:* `PRAGMA_PIL_SIGNAL`
*Bus events consumed:* `PRAGMA_SESSION_INITIATED`

---

**Agent #41 — PragmaFleetMonitor**

*Role:* Health monitoring for the PragmaJudge sub-system. Tracks PragmaVault balance,
PRAGMA token flows, verdict distribution statistics, PIL calibration staleness, and
OFJ agent calibration drift. Reports to the human orchestrator and publishes to the
AutoResearch Wiki Loop.

*Implementation pattern:* Mirrors VAPI's `ProtocolMaturityScoringAgent` (Phase 177) —
9-component maturity score, tier classification, recursive improvement loop.

*PragmaJudge maturity score components:*
```python
PRAGMA_MATURITY_WEIGHTS = {
    "fidelity_calibration":   0.20,   # threshold accuracy vs ground truth
    "vault_health":           0.15,   # vault solvency ratio
    "consensus_stability":    0.15,   # OFJ agreement rate
    "pil_separation":         0.15,   # human vs AI PIL discrimination
    "rbts_calibration":       0.12,   # agent RBTS score distribution
    "ioswarm_quorum":         0.08,   # IoSwarmPragmaVerdictCoordinator health
    "minority_report_rate":   0.07,   # dissent frequency (too high = rubric problem)
    "vault_disbursement_rate":0.05,   # FAILED verdict frequency per platform
    "coherence_index":        0.03,   # PRAGMA coherence violations per 100 sessions
}
```

*Tools:* 6 tools (#203–#208 in catalog)
*Bus events published:* `PRAGMA_MATURITY_SCORE`, `PRAGMA_FLEET_HEALTH`
*Bus events consumed:* All PRAGMA_* events (observer pattern)

### 2.4 The Proof of Human Input (PoHI) Record

The PoHI record is PragmaJudge's analog to VAPI's 228-byte PoAC record. It is produced
by PILMonitorAgent for each monitored interaction session. It is NOT the PoAC record —
it is a separate data structure with a separate chain, stored separately, and never
mixed with PoAC records.

```
 Offset  Len  Field
 ──────  ───  ─────────────────────────────────────────
     0    8   timestamp_ns          (uint64, big-endian)
     8    1   pil_inference_code    (uint8: 0x00=NOMINAL, 0x40=AI_DETECTED, 0x41=ANOMALY)
     9    1   confidence_byte       (uint8: 0–255 maps to 0.0–1.0)
    10    4   pragma_session_id     (uint32, big-endian) — PragmaJudge session, NOT VAPI session_id
    14    4   sequence_number       (uint32, big-endian)
    18    2   feature_dim           (uint16: currently 10)
    20    2   reserved              (0x0000)
    22    8   human_presence_fp64   (IEEE 754 double, big-endian)
    30    8   cross_coherence_fp64  (IEEE 754 double, big-endian)
    38   80   pil_features_fp64[10] (10 × IEEE 754 double, big-endian)
   118   16   device_id             (keccak256(pubkey) — same derivation as VAPI)
   134   14   reserved_padding      (0x00 × 14)
   148   64   ECDSA-P256 signature  (r ∥ s, 32B each)
```

**Total: 212 bytes.** Body = bytes[0:148]. Signature = bytes[148:212].
**Chain link:** `pohi_hash = SHA-256(raw[0:148])` — body ONLY (mirrors VAPI's pattern)
**Hard AI detection:** `pil_inference_code = 0x40` blocks session unconditionally

This format is frozen once established, following VAPI's Phase 1 invariant philosophy.
Do not modify once deployed.

### 2.5 New Tool Catalog Extensions (#150–#208)

PragmaJudge extends VAPI's 149-tool catalog with 59 new tools (#150–#208).
All tools follow VAPI's naming convention, OpenAPI schema pattern, and SDK class
structure. Selected key tools:

```
#150  commit_prompt_intent        — initiate PragmaJudge session, commit intent hash
#151  get_intent_extraction       — retrieve PromptIntentExtractor analysis for session
#152  submit_output_for_judgment  — feed AI output embedding to OFJ agents
#153  get_pragma_verdict          — retrieve final verdict for session
#154  get_vault_balance           — PragmaVault current balance
#155  get_pragma_fidelity_score   — cosine distance: intent vs output for session
#156  get_ofj1_verdict            — OFJ-1 verdict and reasoning tree
#157  get_ofj2_verdict            — OFJ-2 verdict and reasoning tree
#158  get_ofj3_verdict            — OFJ-3 verdict and reasoning tree
#165  get_minority_report         — retrieve dissent record for session
#166  get_pragma_coherence_log    — FleetSignalCoherenceAgent PRAGMA entries
#170  get_pil_signal              — PIL human-presence score for session
#171  get_pohi_chain_health       — PoHI record chain integrity status
#180  run_pragma_preflight        — P0 conditions for PragmaJudge activation
#183  get_pragma_consensus        — PragmaConsensusArbiter aggregated result
#190  get_pragma_maturity_score   — 9-component maturity score from PragmaFleetMonitor
#195  get_pil_calibration_status  — PIL biometric profile enrollment status
#200  trigger_vault_disbursement  — manual vault trigger (operator override)
#203  get_pragma_elo              — AI platform ELO from PragmaEloRegistry
#208  get_pragma_metabolism_index — cognitive orphan resolution speed (mirrors PMI)
```

---

## SECTION 3 — THE MOBILE GAMING EXTENSION

This section describes how PragmaJudge's architecture extends naturally to mobile gaming
when Claude Code begins that build phase. The framework is the same — only the physical
input surface changes.

### 3.1 Mobile as a VAPI-Class Physical Device

In VAPI, the DualShock Edge controller is the physical device. Its IMU, trigger mechanics,
and touchpad produce biometric signals. In the mobile extension, a smartphone is the
physical device. Its accelerometer, gyroscope, touchscreen pressure sensors, and capacitive
contact patterns produce an equivalent class of biometric signals.

The physiological tremor band is identical: 8–12 Hz appears in smartphone accelerometer
data exactly as it does in controller IMU data. The Bosch BMI260/323-class hardware used
in modern smartphones is comparable to controller IMU hardware in resolution and noise
floor. This means VAPI's existing tremor detection mathematics applies directly to mobile
without algorithmic changes — only the data source changes.

### 3.2 Mobile Hardware Attestation → ioID Chain

The research paper establishes the mobile trust chain:

```
Apple Secure Enclave / Android StrongBox
    → generates non-exportable keypair
    → Apple/Google attestation servers certify key origin
    → attested key signs ioID DID registration on IoTeX
    → VAPIioIDRegistry creates ioID NFT: did:io:0x<mobile_device_addr>
    → PHGCredential issued for mobile device after biometric enrollment
    → isFullyEligible(mobileDeviceId) composable gate activates
```

This chain is programmatically identical to VAPI's controller ioID flow. Claude Code
implements `MobileAttestationBridge.py` in `pragmajudge/mobile/` that handles the
Apple/Android attestation step before calling the existing ioID registration contract.

### 3.3 Mobile PIL Detection Stack

On mobile, the PIL detection stack maps as follows:

```python
# Mobile PIL mapping (same computation, different input source)
PIL_K (mobile) = tap_timing_dynamics()         # inter-tap interval jitter
PIL_M (mobile) = swipe_gesture_biometrics()    # BioMoTouch: EER 0.27%, 5 swipes
PIL_S (mobile) = scroll_reading_behavior()     # same computation as desktop
PIL_I (mobile) = device_hold_tremor()          # 8-12Hz from device IMU (same as controller)
PIL_X (mobile) = cross_modal_coherence()       # tap + IMU temporal binding

# BioMoTouch framework (arXiv 2604.07071): fuses capacitive + IMU
# HMOG framework: head movement + orientation + gyroscope for continuous auth
# AUToSen: F1-score 98% on accelerometer+gyroscope+magnetometer
```

The `PILMonitorAgent` (Agent #40) has a `device_mode` configuration:
- `device_mode = "desktop"` — reads keyboard/mouse HID events
- `device_mode = "mobile"` — reads touchscreen/IMU events via mobile SDK

Both modes produce identical `pragma_pil_records` table entries and identical PoHI
records. The downstream agents (OFJ, PragmaConsensusArbiter) are unaware of which
mode is active.

### 3.4 Mobile Anti-Cheat Gap — Layer 3

The research paper identifies that mobile gaming (86% of games compromised) has a
critical missing layer: no existing solution provides continuous human physical presence
verification. VAPI's controller-based approach proves the concept; the mobile extension
fills the Layer 3 gap.

Mobile-specific PIL inference codes (extending the PoHI code space):
```
0x42 = PIL_TOUCH_INJECTION     # programmatic touch events at impossible velocity
0x43 = PIL_EMULATOR_DETECTED   # device IMU signature inconsistent with mobile hardware
0x44 = PIL_REPLAY_ATTACK       # touch event sequence matches stored replay
0x45 = PIL_AI_AGENT_MOBILE     # behavioral signatures consistent with Claude/GPT computer use
```

Hard codes `{0x40, 0x42, 0x43}` block PragmaJudge session eligibility unconditionally
on mobile, mirroring VAPI's hard cheat code philosophy for the controller domain.

### 3.5 Mobile DePIN Reward Structure

Mobile devices registered as PragmaJudge DePIN nodes earn PRAGMA rewards following
the same multiplier logic as desktop devices, with mobile-specific additions:

```
Base PIL verification (mobile)              1.0×
VHP credential active                       1.5×
PIL enrollment complete (N≥10 sessions)     2.0×
Cross-device coherence (mobile + desktop)   2.5×  ← new for mobile
Implicit satisfaction signal contributed    1.75×
AI agent detection event                    3.0×
Silent agent uptime streak (7+ days)        1.25×
Mobile-specific: App Attest anchored        1.5×  ← new for mobile
```

The cross-device coherence multiplier is architecturally significant: a user who holds
a VAPI VHP credential from controller biometrics AND passes PIL verification on their
mobile device AND their desktop creates the strongest possible composite human presence
proof — three independent physical surfaces confirming one enrolled biometric identity.

---

## SECTION 4 — INTEGRATION ARCHITECTURE DIAGRAM

```
VAPI LAYER (Phase 200, READ-ONLY — NEVER MODIFIED)
┌─────────────────────────────────────────────────────────────────┐
│  DualShock Edge → PITL (L0-L6) → PoAC (228B) → IoTeX L1        │
│  PHGCredential (ERC-4671) → isFullyEligible(deviceId)           │
│  AdjudicationRegistry.sol → RulingRegistry.sol → 43 contracts   │
│  36 agents → federation_bus → FleetSignalCoherenceAgent         │
│  PitlSessionProof.circom (Groth16/BN254) → CeremonyRegistry     │
│  VAPIToken (1B) → VAPIOperatorRegistry → ioSwarm (3 coordinators│
└────────────────────────────┬────────────────────────────────────┘
                             │ isFullyEligible(deviceId)
                             │ (single composable view call)
                             │ AdjudicationRegistry (source_type=PRAGMA_JUDGE)
                             │ federation_bus (PRAGMA_* events appended)
                             ▼
PRAGMAJUDGE LAYER (Phase 201+, NEW CODE IN pragmajudge/)
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Input Surfaces:                                                  │
│  [PC Keyboard/Mouse] → PILMonitorAgent (#40) → PoHI (212B)      │
│  [Mobile Touch/IMU]  → PILMonitorAgent (#40) → PoHI (212B)      │
│                                     │                             │
│  Session Layer:                     │                             │
│  PromptCommitmentRegistry.sol ←─────┘                            │
│  PromptIntentExtractor (#37)                                      │
│  IntentGraph (384-dim embedding, speech act, implicature)        │
│  PragmaIntentProof.circom (Groth16, C1+C2+C3)                   │
│                                     │                             │
│  Judgment Layer:                    │                             │
│  OutputFidelityJudge ×3 (#38)       │                             │
│  [RBTS scoring + AgentAuditor Reasoning Trees]                   │
│  [Minority Report on dissent]       │                             │
│                                     │                             │
│  Consensus Layer:                   │                             │
│  PragmaConsensusArbiter (#39)       │                             │
│  [0.65 threshold, inherited frozen] │                             │
│  IoSwarmPragmaVerdictCoordinator    │                             │
│  [VAULT_QUORUM=0.80, VERDICT_QUORUM=0.67]                        │
│                                     │                             │
│  Economic Layer:                    │                             │
│  PragmaVault.sol                    │                             │
│  PRAGMAToken.sol                    │                             │
│  [SATISFIED → refund stake]         │                             │
│  [FAILED → disburse to user]        │                             │
│                                     │                             │
│  Monitoring Layer:                  │                             │
│  PragmaFleetMonitor (#41)           │                             │
│  [Maturity score, ELO, coherence]   │                             │
│  AutoResearch → PRAGMA_WHAT_IF.md   │                             │
│                                     │                             │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
IoTeX L1 (Testnet 4690)
┌─────────────────────────────────────────────────────────────────┐
│  PromptCommitmentRegistry.sol (NEW)                              │
│  PragmaVault.sol (NEW)                                           │
│  PragmaVerdictRegistry.sol (NEW)                                 │
│  PragmaIntentProofVerifier.sol (NEW)                             │
│  PRAGMAToken.sol (NEW)                                           │
│  PragmaEloRegistry.sol (NEW)                                     │
│  PragmaDataSovereigntyRegistry.sol (NEW)                         │
│  IoSwarmPragmaVerdictCoordinator.sol (NEW)                       │
│                                                                   │
│  + All 43 existing VAPI contracts (UNCHANGED)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## SECTION 5 — PHASE BUILD SEQUENCE FOR CLAUDE CODE

PragmaJudge is built in phases, each gated on the prior phase passing all tests.
No phase proceeds until the prior phase's test suite is green. VAPI's existing
3,089 tests must remain green after every PragmaJudge build step.

### Phase 201 — Foundation (Build First)
1. Create `pragmajudge/` folder structure
2. Implement SQLite migrations (new tables only, additive)
3. Implement `PILMonitorAgent` (Agent #40) — desktop mode only, dry_run=True
4. Implement `PromptIntentExtractor` (Agent #37) — LLM-backed, dry_run=True
5. Implement `PromptCommitmentRegistry.sol` — deploy IoTeX Testnet
6. Write Phase 201 test suite (target: 200+ tests)
7. Verify VAPI 3,089 tests still green

### Phase 202 — Judgment Layer
1. Implement `OutputFidelityJudge` ×3 (Agent #38) with RBTS scoring
2. Implement AgentAuditor Reasoning Tree construction
3. Implement Minority Report protocol and `pragma_minority_reports` table
4. Implement `PragmaIntentProof.circom` circuit
5. Deploy `PragmaIntentProofVerifier.sol`
6. Write Phase 202 test suite (target: 300+ tests)

### Phase 203 — Consensus and Vault
1. Implement `PragmaConsensusArbiter` (Agent #39) with 5-layer consensus stack
2. Implement `IoSwarmPragmaVerdictCoordinator` (emulator mode)
3. Implement `PragmaVault.sol` with dry_run protection
4. Implement `PRAGMAToken.sol`
5. Implement `PragmaVerdictRegistry.sol`
6. Write Phase 203 test suite (target: 300+ tests)

### Phase 204 — Monitoring and AutoResearch
1. Implement `PragmaFleetMonitor` (Agent #41)
2. Implement `PragmaEloRegistry.sol`
3. Implement PRAGMA_WHAT_IF.md AutoResearch loop
4. Implement FleetSignalCoherenceAgent rule injection (PRAGMA-C1, C2, C3)
5. Implement hinTS BLS signature aggregation for OFJ consensus
6. Write Phase 204 test suite (target: 200+ tests)

### Phase 205 — Mobile Extension (Gated on Phase 204 complete)
1. Implement `MobileAttestationBridge.py` (Apple App Attest + Android StrongBox)
2. Extend `PILMonitorAgent` with `device_mode="mobile"`
3. Implement BioMoTouch swipe gesture biometrics
4. Extend PoHI code space with mobile-specific inference codes (0x42–0x45)
5. Implement `PragmaDataSovereigntyRegistry.sol`
6. Write Phase 205 test suite (target: 250+ tests)

### Phase 206 — Federated Learning Pipeline (W3bstream Integration)
1. Implement vertical federated learning architecture for PIL biometric models
2. Implement differential privacy (ε=4) gradient update protocol
3. Implement W3bstream Sprout module for adjudication compute
4. Implement on-device TinyML model inference (<500KB, INT8 quantized)
5. Write Phase 206 test suite (target: 200+ tests)

---

## SECTION 6 — RESEARCH PAPER TO CODE MAPPING

This section tells Claude Code exactly which research framework maps to which code
component, so that implementation decisions are grounded in validated academic work.

| Research Finding | Code Component | Implementation Detail |
|---|---|---|
| MIT Media Lab: 55% less neural connectivity on passive LLM acceptance | `PILMonitorAgent` keystroke jitter | High keystroke jitter CV = genuine evaluation; low CV = passive acceptance |
| PLOS ONE: GSR triggered by AI content | `PILMonitorAgent` PIL_M | Mouse idle micro-movement as GSR proxy without wearable |
| TSVD GSR classification: 98.3% accuracy | `PILMonitorAgent` cross_layer_coherence | TSVD applied to multi-modal PIL signal cross-correlation |
| Keystroke cognitive fatigue: 91% accuracy | `PILMonitorAgent` PIL_K | Keystroke inter-event entropy as cognitive load proxy |
| Mouse trajectory: 68.8% decision variance | `PILMonitorAgent` PIL_M | Cursor path complexity as decision conflict signal |
| ZK-PoP: 192-byte proofs, 8.2ms verify | `PragmaIntentProof.circom` | Groth16 circuit on same BN254 as VAPI — matches exactly |
| hinTS: 896-byte threshold BLS, 390K gas | `PragmaConsensusArbiter` | OFJ verdict aggregation via BLS threshold signatures |
| Pedersen vector commitment (384-dim) | `PromptIntentExtractor` | all-MiniLM-L6-v2 → quantized 16-bit → Pedersen commit on BN254 |
| IPFE selective disclosure | `PragmaIntentProof.circom` | Prove PIL features in human range without revealing raw values |
| BVFLMSP Bayesian vertical FL | Phase 206 W3bstream module | Per-modality Bayesian NN, uncertainty estimates, split model |
| FedFV: EER 0.07% biometric auth | Phase 206 W3bstream module | Shared encoder + personal classifier, never share personal layer |
| Differential privacy ε=4, 2-5% accuracy loss | Phase 206 W3bstream module | DP noise on embeddings before W3bstream aggregation |
| QV fails for information aggregation | `PragmaConsensusArbiter` | RBTS for verdict quality, QV only for rubric governance |
| RBTS: Bayes-Nash incentive compatible n≥3 | `OutputFidelityJudge` | 3 OFJ instances exceed minimum; multi-task variant for batch |
| STAKESURE: redistribute slash to harmed | `PragmaVault.sol` | Failed verdict stake → user reimbursement, not burn |
| No collusion resistance in general | All agents | Random assignment per session, commit-reveal, temporal isolation |
| BioMoTouch: EER 0.27%, 5 swipes | Phase 205 mobile PIL_M | Fuse capacitive + IMU for swipe gesture biometric |
| AUToSen: F1 98% continuous mobile auth | Phase 205 PILMonitorAgent | Accelerometer + gyroscope + magnetometer continuous monitoring |
| Apple Secure Enclave / Android StrongBox | Phase 205 MobileAttestationBridge | Non-exportable key → Apple/Google attestation → ioID DID |
| AgentAuditor: 65% accuracy where majority wrong | `OutputFidelityJudge` | Reasoning Tree construction, Critical Divergence Point identification |
| CollabEval three-phase deliberation | All OFJ instances | Independent eval → panel debate → synthesis (6 panels × 6 agents at scale) |
| Byzantine approximate agreement f≤11 | `PragmaConsensusArbiter` | n=36 fleet tolerates 11 Byzantine (3×11+1=34 < 36) |
| Williams & Bayne speech act theory | `PromptIntentExtractor` | DIRECTIVE / ASSERTIVE / COMMISSIVE / EXPRESSIVE / DECLARATIVE taxonomy |
| Gricean implicature: LLMs score 20-60% | `PromptIntentExtractor` | External implicature extraction as primary failure detection |
| EU AI Act Article 12 logging mandate | `PragmaVerdictRegistry.sol` | Every verdict anchored on-chain with block.number = tamper-evident log |
| Moffatt v. Air Canada liability | `PragmaVault.sol` | Cryptographic non-repudiation: what was requested vs delivered |
| IoTeX Roll-DPoS: 36 delegates, PBFT+VRF | Entire PragmaJudge fleet | 36-agent fleet is epistemic analogue of IoTeX consensus layer |
| IoTeX ioID: did:io:0x<addr> | All PIL device registrations | Desktop + mobile devices registered as DePIN nodes via ioID |
| IoTeX Scaleout: contributor-owned ML | Phase 206 W3bstream | PIL biometric models as Initial Model Offerings, community co-ownership |

---

## SECTION 7 — CONFIGURATION CONSTANTS

All PragmaJudge configuration lives in `pragmajudge/config.py`. Constants that are
candidates for future freezing are marked with `# CANDIDATE_INVARIANT`.

```python
# pragmajudge/config.py

# ─── Inherited from VAPI (DO NOT REDEFINE — import from vapi_bridge.config) ───
# epistemic_consensus_threshold = 0.65
# BLOCK_QUORUM = 0.67
# MINT_QUORUM = 0.80

# ─── PragmaJudge-Specific Constants ───

# Vault mechanics
VAULT_QUORUM = 0.80                    # ioSwarm quorum for vault disbursement # CANDIDATE_INVARIANT
VERDICT_QUORUM = 0.67                  # ioSwarm quorum for FAILED verdict
PLATFORM_STAKE_MIN = 100              # minimum credits platform must stake per session

# Fidelity threshold (not globally frozen — calibrated per platform)
DEFAULT_FIDELITY_THRESHOLD = 0.72     # cosine similarity floor for SATISFIED
FIDELITY_THRESHOLD_MIN = 0.60         # floor: no platform can set below this

# PIL detection
PIL_AI_SPEED_THRESHOLD = 0.00005      # keystroke CV below this = AI_DETECTED (mirrors VAPI L5)
PIL_TREMOR_BAND_LOW_HZ = 8.0          # physiological tremor band (same as VAPI)
PIL_TREMOR_BAND_HIGH_HZ = 12.0        # physiological tremor band (same as VAPI)
PIL_HUMAN_PRESENCE_THRESHOLD = 0.65   # below this = ANOMALY advisory

# PRAGMA token rewards
PRAGMA_BASE_RATE = 1.0                # base PRAGMA per verified session
PRAGMA_VHP_MULTIPLIER = 1.5           # VHP credential active
PRAGMA_ENROLLED_MULTIPLIER = 2.0      # PIL enrollment complete N≥10
PRAGMA_CROSS_DEVICE_MULTIPLIER = 2.5  # controller + PC coherence verified
PRAGMA_IMPLICIT_MULTIPLIER = 1.75     # implicit satisfaction signal contributed
PRAGMA_AI_DETECTION_MULTIPLIER = 3.0  # AI agent detection bounty
PRAGMA_UPTIME_MULTIPLIER = 1.25       # 7+ day silent agent uptime streak
PRAGMA_MOBILE_ATTEST_MULTIPLIER = 1.5 # App Attest / StrongBox anchored (mobile)

# Intent extraction
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dimensional sentence embeddings
EMBEDDING_DIM = 384
EMBEDDING_QUANTIZE_BITS = 16          # fixed-point quantization before commitment
SPEECH_ACT_CODES = [                  # Searle's taxonomy
    "DIRECTIVE", "ASSERTIVE", "COMMISSIVE", "EXPRESSIVE", "DECLARATIVE"
]

# Agent fleet
PRAGMA_CONSENSUS_WEIGHTS = {
    "ofj1": 0.233, "ofj2": 0.233, "ofj3": 0.233,
    "pil": 0.15, "ioswarm": 0.10, "implicit": 0.05
}                                      # sum = 1.004 (rounding — normalize in code)

# Federated learning (Phase 206)
FL_DIFFERENTIAL_PRIVACY_EPSILON = 4.0  # 2-5% accuracy degradation acceptable
FL_MODEL_MAX_SIZE_KB = 500             # TinyML constraint
FL_AGGREGATION_OVERHEAD_TARGET = 0.0125 # 1.25% of baseline (W3bstream target)

# Dry run (NEVER change default — must be explicit operator action)
PRAGMA_DRY_RUN_DEFAULT = True

# ioSwarm emulator (matches VAPI pattern)
PRAGMA_IOSWARM_ENABLED = True          # True = emulator mode until live nodes registered
PRAGMA_IOSWARM_EMULATOR_SEED = 201     # distinct from VAPI seeds 109/110

# Coherence
PRAGMA_PROMOTE_THRESHOLD = 3           # contradictions before PRAGMA_WHAT_IF promotion
                                       # mirrors VAPI's N_PROMOTE_THRESHOLD=3

# Chain
IOTEX_TESTNET_CHAIN_ID = 4690          # inherited from VAPI
PRAGMA_SOURCE_TYPE = "PRAGMA_JUDGE"    # mandatory on all registry writes
```

---

## SECTION 8 — FILE STRUCTURE

```
vapi-pebble-prototype/
├── bridge/                          # VAPI codebase — READ ONLY
│   └── vapi_bridge/                 # DO NOT MODIFY ANY FILE HERE
├── pragmajudge/                     # ALL PRAGMAJUDGE CODE LIVES HERE
│   ├── __init__.py
│   ├── config.py                    # Section 7 constants
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── prompt_intent_extractor.py   # Agent #37
│   │   ├── output_fidelity_judge.py     # Agent #38 (instanced ×3)
│   │   ├── pragma_consensus_arbiter.py  # Agent #39
│   │   ├── pil_monitor_agent.py         # Agent #40
│   │   └── pragma_fleet_monitor.py      # Agent #41
│   ├── circuits/
│   │   ├── PragmaIntentProof.circom     # ZK circuit
│   │   └── PragmaIntentProof_js/        # compiled artifacts
│   ├── contracts/
│   │   ├── PromptCommitmentRegistry.sol
│   │   ├── PragmaVault.sol
│   │   ├── PragmaVerdictRegistry.sol
│   │   ├── PragmaIntentProofVerifier.sol
│   │   ├── PRAGMAToken.sol
│   │   ├── PragmaEloRegistry.sol
│   │   ├── PragmaDataSovereigntyRegistry.sol
│   │   └── IoSwarmPragmaVerdictCoordinator.sol
│   ├── migrations/
│   │   ├── 001_create_pragma_sessions.sql
│   │   ├── 002_create_pragma_intent_records.sql
│   │   ├── 003_create_pragma_agent_verdicts.sql
│   │   ├── 004_create_pragma_vault_ledger.sql
│   │   ├── 005_create_pragma_pil_records.sql
│   │   ├── 006_create_pragma_coherence_log.sql
│   │   └── 007_create_pragma_minority_reports.sql
│   ├── mobile/
│   │   ├── __init__.py
│   │   └── mobile_attestation_bridge.py # Phase 205
│   ├── fl/                          # Federated learning (Phase 206)
│   │   ├── __init__.py
│   │   ├── vertical_fl_coordinator.py
│   │   └── tinyml_inference.py
│   ├── coherence_rules.py           # PRAGMA-C1, C2, C3 injected into FleetSignalCoherenceAgent
│   ├── tools/
│   │   └── catalog.py               # Tools #150–#208
│   ├── docs/
│   │   ├── PRAGMA_WHAT_IF.md        # AutoResearch output
│   │   ├── PRAGMA_MEMORY.md         # Calibration state
│   │   └── PRAGMA_RUBRIC_DELTA.md   # Rubric evolution log
│   └── tests/
│       ├── test_phase_201.py        # 200+ tests
│       ├── test_phase_202.py        # 300+ tests
│       ├── test_phase_203.py        # 300+ tests
│       ├── test_phase_204.py        # 200+ tests
│       ├── test_phase_205.py        # 250+ tests
│       └── test_phase_206.py        # 200+ tests
```

---

## SECTION 9 — WHAT PRAGMAJUDGE PROVES THAT NOTHING ELSE CAN

This section exists so Claude Code understands the *purpose* behind each component
it builds. Understanding purpose prevents misimplementation.

PragmaJudge is the first system that simultaneously achieves all four of the following:

**1. Physiological proof of human presence during AI interaction.**
Not just account credentials or device attestation — actual biometric verification that
a human body produced the physical input signals during the session. VAPI proved this
for gaming controllers. PragmaJudge extends it to every computing surface. No existing
AI accountability system has this property.

**2. Cryptographic proof that the AI served the committed intent.**
The fidelity gap between what was intended (committed before output is seen) and what
was delivered (measured after) is computed by consensus agents and verified by a ZK
circuit. The proof is posted on-chain and is verifiable by any third party. No existing
system measures or proves intent fidelity — they only measure output quality divorced
from intent.

**3. Economic consequence for AI platform output failure.**
The PragmaVault creates real financial stakes. When an AI output fails the fidelity
gate, the platform's staked credits flow to the user automatically. This is skin-in-the-
game accountability that no existing AI evaluation framework provides.

**4. Recursive self-improvement through cryptographically anchored disagreement.**
Every OFJ minority dissent, every FleetSignalCoherenceAgent contradiction detection,
every AutoResearch Wiki Loop entry feeds back into rubric improvement. The system's
judgment gets better over time in a verifiable, auditable, on-chain-anchored way.

These four properties together, and only together, constitute the PragmaJudge protocol.
Any build that achieves fewer than all four is incomplete. Claude Code should treat this
as its success criteria for every phase.

---

*Document Version: Phase 201 Initialization*
*Correlation Source: VAPI_PROTOCOL_ASSESSMENT.md (Phase 200)*
*Research Source: PragmaJudge__A_Cross-Disciplinary_Architecture_for_Physical_Intelligence_Accountability.md*
*Chain: IoTeX Testnet 4690*
*Repository: C:\Users\Contr\vapi-pebble-prototype\pragmajudge\*
*Active Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692*
*Dual-Architect: Claude Master Architect + Grok Architect Master*
*Human Orchestrator: Direct*
