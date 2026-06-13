# Phase O0 — Design Pass 2C: Implementation Plan

**Status**: APPROVED 2026-04-27. All four load-bearing question
decisions plus seven supporting question decisions confirmed by
operator. Resolutions preserved in Section 9's "Operator decisions
(2026-04-27)" subsection as the permanent implementation record. Phase
O0 implementation work begins in the next session per this plan; this
document is the implementation contract. No code or contract changes
ship as part of this commit — this is a standalone documentation
commit closing the design phase.

**Scope discipline**: produces the Phase O0 (Foundations) implementation
plan synthesizing all resolved decisions from prior passes. Phase O1
(Shadow/Read-Only) through Phase O6 (Full Operator) are out of scope
except where dependencies need to be acknowledged. The Phase O0
estimate from Pass 2A's revised range is 3.5-6 weeks; Pass 2C confirms
this estimate based on the synthesis work below.

**Resolved inputs from prior design passes** (not open for revision —
nine total):

From **Design Pass 1** (commit `30181951`):
1. Parallel `AgentAdjudicationRegistry` contract; existing
   `AdjudicationRegistry` at `0x44CF981f46a52ADE56476Ce894255954a7776fb4`
   untouched.
2. Scope-class agent action authorization (AgentScope + AuditLog +
   AgentAdjudicationRegistry); CONSENT v1 stays FROZEN.
3. `wiki/audits/` and `wiki/sweeps/` move to top-level `audits/` and
   `sweeps/`.

From **Pass 2A** (commit `6751bf9a`):
4. Wallet funding to 5 IOTX target.
5. OAuth 2.1 client credentials + HMAC request signing in Phase O0;
   mTLS via SPIFFE/SPIRE deferred to P3+.
6. Separate `scripts/vapi_path_scope_gate.py` + new GitHub Actions
   workflow for per-author path scope checking.
7. AGENT_COMMIT v1 as sixth FROZEN-v1 primitive on
   AgentAdjudicationRegistry.
8. Audience: businesses and institutions evaluating data sovereignty
   under regulatory, legal, and reputational standards.

From **Pass 2B** (commit `fe4232e3`):
9. PHYSICAL_DATA_ATTESTATION v1 as seventh FROZEN-v1 primitive on
   AgentAdjudicationRegistry.

**Verification standard**: every architectural claim cites `file:line`
or external-source verification. Every dependency claim references
specific contracts or modules. Every effort estimate cites prior phases
as calibration data.

**Date**: 2026-04-27

---

## Section 1 — Executive Summary

### What Phase O0 ships

Phase O0 (Foundations) provisions the cryptographic identity layer,
attestation infrastructure, and CI governance scaffolding required for
Anchor Sentry and Guardian to begin operating in Phase O1 (Shadow Mode).
Phase O0 does NOT yet activate the agents — they are defined, registered,
provisioned, but inactive at Phase O0 exit. P1 begins their first
operational cadence.

The shipping deliverables fall into seven categories:

1. **Five new contracts deployed to IoTeX testnet**: AgentRegistry,
   AgentScope, AgentSlashing, AuditLog, AgentAdjudicationRegistry. Total
   estimated deploy cost ~0.45 IOTX (per Pass 2A V8 revised estimates;
   excludes the EAS deploy that was eliminated by V10 Option C).
2. **Two new FROZEN-v1 primitives**: AGENT_COMMIT v1 (sixth) and
   PHYSICAL_DATA_ATTESTATION v1 (seventh). Each ships as a bridge
   module + store table + chain wrapper + PV-CI invariants + tests.
3. **Two GitHub Apps registered**: `vapi-anchor-sentry[bot]` and
   `vapi-guardian[bot]` with KMS-backed signing keys.
4. **Two ioID DIDs minted**: one per agent, with ERC-6551 TBAs bound
   on the existing IoTeX testnet ioID infrastructure.
5. **Bridge authentication layer additions**: OAuth 2.1 client
   credentials + HMAC request signing middleware coexisting with the
   existing `_check_key`/`_check_read_key` patterns.
6. **CI gate additions**: `scripts/vapi_path_scope_gate.py` + new
   `.github/workflows/vapi-path-scope-gate.yml` workflow + new
   `.github/CODEOWNERS` file establishing path-based lane discipline.
7. **Lane reorganization**: `wiki/audits/` → `audits/` and
   `wiki/sweeps/` → `sweeps/`, with the wiki engine constant
   updates required to preserve referential integrity.

### Order of operations

Phase O0 work proceeds in five overlapping streams. Streams 2-5 can
proceed in parallel once Stream 1 completes:

- **Stream 1 (Week 1)**: Wallet funding + lane reorg + CODEOWNERS +
  path-scope gate. Unblocks all subsequent streams. Deploys do not
  begin until wallet ≥3 IOTX confirmed live.
- **Stream 2 (Weeks 1-3)**: Contract development + Hardhat tests + deploy.
  All five contracts written, internally audited, deployed in dependency
  order. Estimated 2-3 weeks.
- **Stream 3 (Weeks 1-2)**: Two FROZEN-v1 primitives implemented as
  bridge modules + store + chain wrappers. Estimated 1.5-2 weeks (~5-8
  days per primitive matching Pass 2A V10 estimate; runnable in
  parallel by separate sub-tasks within the stream).
- **Stream 4 (Weeks 2-4)**: Authentication layer (OAuth 2.1 + HMAC
  middleware). Estimated 1.5-2 weeks. Can begin once basic streams 1-3
  shape is locked.
- **Stream 5 (Weeks 3-5)**: Agent identity provisioning — GitHub Apps
  registration, KMS keys, ioID DIDs, ERC-6551 TBAs, AgentRegistry
  registration. Estimated 1-2 weeks. Depends on Stream 2 contract
  deploys.

### Timeline confirmation

**Pass 2C confirms the Pass 2A estimate of 3.5-6 weeks for Phase O0.**
Best case 3.5 weeks if all streams complete cleanly with no IoTeX gas
surprises. Worst case 6 weeks if KMS provisioning hits AWS-account
issues, GitHub Apps registration runs into GitHub-side delays,
IoTeX testnet exhibits the gas-estimation surprise pattern from Phase
237.5 Path C+, or Hardhat tests surface contract design issues that
require redesign-and-redeploy cycles.

### Phase O0 exit criteria (revised — full version in Section 8)

- 5 contracts deployed on IoTeX testnet, total contract count rising
  from 46 to 51
- AGENT_COMMIT v1 and PHYSICAL_DATA_ATTESTATION v1 primitive
  infrastructure live in bridge
- 2 GitHub Apps with KMS-backed signing keys
- 2 ioID DIDs + ERC-6551 TBAs bound
- Both agents registered in AgentRegistry (status=DEFINED, no operational
  authority yet)
- OAuth 2.1 + HMAC auth middleware live alongside existing single-shared-
  secret pattern
- `vapi_path_scope_gate.py` enforcing CODEOWNERS rules in CI
- `audits/` + `sweeps/` at top-level; wiki engine references updated
- `INVARIANTS_ALLOWLIST.json` regenerated with 4 new invariants
  (28 → 32 entries)
- All bridge tests passing; all contract tests passing

### What Phase O0 explicitly does NOT include

Per architecture document section 9, Phase O0 is foundations only with
no agent operational authority:

- No agent process startup (agents stay defined but inactive)
- No bridge endpoint allowlisting for agent tokens (allowed in P1)
- No commit authority granted to agents (granted in P2)
- No on-chain transactions from agent identities (allowed in P4)
- No EAS deployment (per Pass 2A V10 Option C; AGENT_COMMIT v1 is
  VAPI-native)
- No SPIRE/SPIFFE infrastructure (per Pass 2A V2 Option B; deferred to
  P3+)
- No Cedar policy bundles (deferred to P1+; Phase O0 ships AgentScope
  contract but bundle Merkle root may be the zero hash at Phase O0
  exit)
- No Tessera log infrastructure (deferred to P1+; AuditLog contract
  ships with append-only Merkle root storage but the upstream Tessera
  signed-tree-head feed is not yet live)

The agents' first operational cadence begins in Phase O1.

---

## Section 2 — Resolved Inputs Map

The nine resolved inputs from prior passes map to concrete Phase O0
deliverables as follows. Each input becomes one or more implementation
tasks.

| # | Resolved input | Source | Phase O0 deliverable | Section reference |
|---|---|---|---|---|
| 1 | Parallel AgentAdjudicationRegistry contract | Pass 1 Conflict 1 | New contract `contracts/contracts/AgentAdjudicationRegistry.sol` deployed; existing AdjudicationRegistry untouched | §3.5 |
| 2 | Scope-class authorization (AgentScope + AuditLog + AgentAdjudicationRegistry) | Pass 1 Conflict 2 | Three contracts deployed; CONSENT v1 unchanged | §3.2, §3.4, §3.5 |
| 3 | Lane reorg (`wiki/audits/` → `audits/`, `wiki/sweeps/` → `sweeps/`) | Pass 1 Conflict 3 | 3 file moves + 6 `vapi_wiki_engine.py` reference updates + CODEOWNERS rules | §5.3 |
| 4 | Wallet ≥5 IOTX target | Pass 2A V8 | Operator funding action; pre-deploy balance checks ≥3 IOTX in deploy scripts | §3 (gas budgets), §6 |
| 5 | OAuth 2.1 + HMAC; mTLS deferred | Pass 2A V2 | New `bridge/vapi_bridge/agent_auth.py` module; new endpoint annotations | §5.1 |
| 6 | Separate path-scope gate | Pass 2A V5 | New `scripts/vapi_path_scope_gate.py` + new workflow + CODEOWNERS file | §5.2 |
| 7 | AGENT_COMMIT v1 as sixth FROZEN-v1 primitive | Pass 2A V10 | New `bridge/vapi_bridge/agent_commit.py` + store table + chain wrapper + 2 invariants + tests | §4.1 |
| 8 | Audience: businesses/institutions for data sovereignty | Pass 2A | Audit-stable endpoint contracts; primitive design choices favor compliance-grade verifiability | §4.1, §4.2, §8 |
| 9 | PHYSICAL_DATA_ATTESTATION v1 as seventh FROZEN-v1 primitive | Pass 2B Path 3 | New `bridge/vapi_bridge/physical_data_attestation.py` + store table + chain wrapper + 2 invariants + tests | §4.2 |

**Map proves no implementation question contradicts a resolved decision.**
The 5 contracts in Section 3 align with Inputs 1+2. The 2 primitives in
Section 4 align with Inputs 7+9 and use AgentAdjudicationRegistry from
Input 1 as their on-chain anchor. The bridge infrastructure in Section
5 implements Inputs 5+6+3. The agent identity infrastructure in Section
6 uses Input 4's funded wallet. Input 8 is the framing that constrains
design choices throughout — every endpoint contract, primitive
versioning decision, and audit surface choice is made to favor
compliance-grade verifiability.

---

## Section 3 — Contract Deployment Sequence

### Deployment order constraint

The five contracts have the following dependency graph:

```
AgentRegistry (no deps)
    ↓ (referenced by AgentScope's policy bundle bindings)
AgentScope
    ↓ (referenced by AuditLog's audit-bind validation)
AuditLog
    ↓ (referenced by AgentSlashing for action history)
AgentSlashing
    ↓ (referenced by AgentAdjudicationRegistry's requireAgentScope modifier)
AgentAdjudicationRegistry
```

Deploy order: AgentRegistry → AgentScope → AuditLog → AgentSlashing →
AgentAdjudicationRegistry. Each later contract may reference the
earlier ones in its constructor or post-deploy initialization.

### Section 3.1 — AgentRegistry.sol

- **File path**: `contracts/contracts/AgentRegistry.sol`
- **Purpose**: registers each Operator Agent with `(agentId →
  publicKey, scopeHash, status)`. Sibling contract to
  VAPIBiometricGovernance (Phase 222 LIVE at
  `0x06782293F1CFC1AA30C0Baee0437c2B336796A00`); follows same
  Ownable + ReentrancyGuard + indexed-events pattern.
- **Constructor arguments**: `(address initialOwner)` — bridge wallet
  `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`.
- **Dependencies**: none.
- **Hardhat test file**: `contracts/test/PhaseO0_AgentRegistry.test.js`
- **Estimated gas cost**: ~0.07 IOTX (matches VAPIBiometricGovernance
  Phase 222 deploy estimate at `contracts/scripts/deploy-phase222.js:9`
  — same Ownable+Registry shape).
- **Owner/access control**:
  `onlyOwner` for `registerAgent(...)` and `updateAgentStatus(...)`.
  View functions (`getAgent(agentId)`, `getAttestationCapabilities` if
  Path 2 from Pass 2B is later adopted as a future extension — but
  Path 2 is not part of Phase O0 scope) public.
- **Events emitted**:
  - `AgentRegistered(bytes32 indexed agentId, address indexed publicKey, bytes32 scopeHash, uint8 status)`
  - `AgentStatusUpdated(bytes32 indexed agentId, uint8 oldStatus, uint8 newStatus)`
  - `AgentScopeUpdated(bytes32 indexed agentId, bytes32 oldScope, bytes32 newScope)`

The agent_id field is `bytes32` representing the hash of the agent's
ioID DID + ERC-6551 TBA address binding. Specific encoding deferred
to Section 6 (Agent Identity Infrastructure).

Status enum values: `DEFINED=0` (Phase O0 exit state), `SHADOW=1` (P1),
`SUGGESTING=2` (P2), `WRITE_TOURNAMENT=3` (P3), `INVARIANT_AUTH=4`
(P4), `PROVENANCE_WRITE=5` (P5), `FULL_OPERATOR=6` (P6),
`SUSPENDED=255`.

### Section 3.2 — AgentScope.sol

- **File path**: `contracts/contracts/AgentScope.sol`
- **Purpose**: stores Merkle root of the policy bundle (Cedar/Rego)
  the bridge verifies against at request time. Per architecture
  document section 4 + Pass 1 Conflict 2 Option C resolution.
- **Constructor arguments**: `(address initialOwner, address agentRegistry)`
  — bridge wallet + AgentRegistry address from Section 3.1 deploy.
- **Dependencies**: AgentRegistry (Section 3.1) for cross-validation.
- **Hardhat test file**: `contracts/test/PhaseO0_AgentScope.test.js`
- **Estimated gas cost**: ~0.05 IOTX (smaller contract; Merkle root
  storage + per-agent mapping; matches V8's estimate).
- **Owner/access control**: `onlyOwner` for `setAgentScopeRoot(agentId,
  root)`. Default Phase O0 scopeRoot is `bytes32(0)` (empty bundle —
  agent has no operational scope yet, consistent with Phase O0 not
  granting operational authority).
- **Events emitted**:
  - `AgentScopeRootSet(bytes32 indexed agentId, bytes32 oldRoot, bytes32 newRoot, uint256 timestamp)`

View function `getScopeRoot(agentId) → bytes32` exposes the current
root. The bridge reads this at request time and verifies the request
falls within the bundle (off-chain verification; the contract stores
the root, the bridge interprets the bundle).

### Section 3.3 — AgentSlashing.sol

- **File path**: `contracts/contracts/AgentSlashing.sol`
- **Purpose**: VetoSlasher-pattern economic accountability for agent
  misbehavior. Bond → slash → 24h veto window → burn. Per
  architecture document section 4.
- **Constructor arguments**: `(address initialOwner, address agentRegistry,
  uint256 vetoWindowSeconds)` — bridge wallet + AgentRegistry +
  86400 (24 hours).
- **Dependencies**: AgentRegistry.
- **Hardhat test file**: `contracts/test/PhaseO0_AgentSlashing.test.js`
- **Estimated gas cost**: ~0.10 IOTX (largest of the five contracts;
  bond accounting + veto state machine + slash execution logic).
- **Owner/access control**:
  `onlyOwner` for `slashAgent(agentId, reason, evidenceHash)`,
  `vetoSlash(slashId)`, `executeSlash(slashId)`. Bond deposits are
  permissionless during P0 but no agent is yet active so no actual
  bonds will be deposited at Phase O0 exit.
- **Events emitted**:
  - `BondDeposited(bytes32 indexed agentId, uint256 amount)`
  - `SlashProposed(uint256 indexed slashId, bytes32 indexed agentId, uint256 amount, bytes32 evidenceHash)`
  - `SlashVetoed(uint256 indexed slashId, address indexed cosigner)`
  - `SlashExecuted(uint256 indexed slashId, uint256 burnedAmount, uint256 distributedAmount)`

The veto window pattern matches `VAPIGovernanceTimelock.sol` (Phase 69+
existing contract). Co-signer cancel pattern reused.

### Section 3.4 — AuditLog.sol

- **File path**: `contracts/contracts/AuditLog.sol`
- **Purpose**: append-only Merkle root anchor for nightly Tessera
  signed-tree-head checkpoints. Phase O0 ships the contract; Tessera
  upstream feed is deferred to P1+.
- **Constructor arguments**: `(address initialOwner)` — bridge wallet.
- **Dependencies**: none for deploy; AgentRegistry reference is
  optional (queried by clients off-chain).
- **Hardhat test file**: `contracts/test/PhaseO0_AuditLog.test.js`
- **Estimated gas cost**: ~0.05 IOTX (simplest contract; Merkle root
  storage with append-only constraint).
- **Owner/access control**: `onlyOwner` for `appendCheckpoint(merkleRoot,
  treeSize, timestamp)`. View `getLatestCheckpoint() → (root, size, ts,
  blockNumber)`.
- **Events emitted**:
  - `CheckpointAppended(uint256 indexed checkpointId, bytes32 merkleRoot, uint256 treeSize, uint256 timestamp)`

Anti-replay constraint: each `merkleRoot` MUST be unique (mapping
`bytes32 → bool` for dedup); attempting to append the same root reverts.
Each append MUST have `treeSize > previousTreeSize` (monotonic growth
constraint). Each append MUST have `timestamp >= block.timestamp - 3600`
(within last hour — prevents stale checkpoint attacks).

### Section 3.5 — AgentAdjudicationRegistry.sol

- **File path**: `contracts/contracts/AgentAdjudicationRegistry.sol`
- **Purpose**: agent-scoped action anchor. Per Design Pass 1 Conflict
  1 Option A. Hosts AGENT_COMMIT v1 and PHYSICAL_DATA_ATTESTATION v1
  primitives via `actionType` discriminator.
- **Constructor arguments**: `(address initialOwner, address agentRegistry,
  address agentScope)` — bridge wallet + AgentRegistry + AgentScope.
- **Dependencies**: AgentRegistry, AgentScope.
- **Hardhat test file**: `contracts/test/PhaseO0_AgentAdjudicationRegistry.test.js`
- **Estimated gas cost**: ~0.08 IOTX (larger than AgentRegistry due to
  `requireAgentScope` modifier logic + actionType vocabulary
  enforcement).
- **Owner/access control**:
  `requireAgentScope(agentId, actionType)` modifier on
  `anchorAgentAction(...)`. The modifier looks up agentId's scopeRoot
  via AgentScope and validates actionType is in the agent's allowed
  vocabulary. Phase O0 scopeRoot is zero hash for both agents, so the
  modifier rejects all anchor calls at Phase O0 exit (consistent with
  P0's no-operational-authority constraint).
- **Events emitted**:
  - `AgentActionAnchored(bytes32 indexed agentId, bytes32 indexed actionHash, string actionType, uint256 blockNumber)`

Per Design Pass 1 Conflict 1 Option A architectural details
(PHASE_O0_DESIGN_PASS_1.md:191-225):

```solidity
// Function signatures (design only — not implementation)
function anchorAgentAction(
    bytes32 actionHash,
    bytes32 agentId,
    string calldata actionType
) external requireAgentScope(agentId, actionType);

function isRecorded(bytes32 actionHash) external view returns (bool);
function getAgentActionType(bytes32 actionHash) external view returns (string memory);
```

Anti-replay: each `actionHash` MUST be unique. Mapping `bytes32 → string`
stores `actionType`. Mapping `bytes32 → bytes32` stores agentId.

### Section 3.6 — Deployment script

- **File path**: `contracts/scripts/deploy-phaseo0.js`
- **Pattern**: follows `contracts/scripts/deploy-phase237.js` shape
  (read in this session — Ownable deploy + post-deploy smoke tests +
  `deployed-addresses.json` update + `bridge/.env.testnet` hint
  printing).
- **Pre-deploy wallet balance check**: queries
  `eth_getBalance` for `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`;
  aborts if balance < 3 IOTX. The 3 IOTX threshold gives ~6× the total
  estimated deploy cost (~0.45 IOTX) plus drain-margin headroom per
  Pass 2A V8.
- **Deploy sequence within script**:
  1. Deploy AgentRegistry; record address.
  2. Deploy AgentScope(agentRegistry); record.
  3. Deploy AuditLog; record.
  4. Deploy AgentSlashing(agentRegistry, vetoWindow=86400); record.
  5. Deploy AgentAdjudicationRegistry(agentRegistry, agentScope); record.
  6. Smoke tests on each: owner check, view function returns expected
     defaults.
  7. Update `contracts/deployed-addresses.json` with all 5 addresses.
  8. Print `bridge/.env.testnet` hints for the 5 new env vars.

Each deploy has a balance check after to ensure margin remains for
remaining deploys. If balance falls below 0.5 IOTX during the
sequence, abort and log; resume after wallet refunding.

**Total estimated deploy cost**: ~0.07 + 0.05 + 0.05 + 0.10 + 0.08 +
~0.10 (initialization txs and ioID minting from Section 6) = **~0.45
IOTX**, well within the 5 IOTX target wallet.

### Section 3.7 — Hardhat test pattern

Each `contracts/test/PhaseO0_<ContractName>.test.js` follows the
existing pattern from `contracts/test/Phase222.test.js` (Phase 222
BBG tests) and `contracts/test/Phase221.test.js`:

- Deploy fixture using ethers.getContractFactory
- Owner-only modifier tests (positive + negative)
- Event emission tests
- Anti-replay tests (where applicable — AuditLog merkleRoot uniqueness,
  AgentAdjudicationRegistry actionHash uniqueness)
- View function correctness tests
- Edge case tests: zero-address guards, empty bytes32 inputs, etc.

Estimated 6-10 tests per contract × 5 contracts = 30-50 new Hardhat
tests. Phase 222 added 8 Hardhat tests; Phase 221 added 6. Phase O0's
contract count is larger (5 vs 1) so total is in the 30-50 range.

---

## Section 4 — Primitive Implementation Tasks

### Section 4.1 — AGENT_COMMIT v1 (sixth FROZEN-v1 primitive)

- **Bridge module file path**: `bridge/vapi_bridge/agent_commit.py`
- **Pattern**: mirrors `bridge/vapi_bridge/corpus_snapshot.py` (read in
  this session — 23-byte domain tag, struct.pack(">Q", ...) for ts_ns
  + uint64 fields, `.digest()` returns 32 bytes).
- **Hash formula** (per Pass 2A V10 Option C, Section 3 architectural
  details — frozen at Phase O0 deploy):

```python
_AGENT_COMMIT_TAG = b"VAPI-AGENT-COMMIT-v1"  # 20 bytes

def compute_agent_commit_hash(
    agent_id: bytes,           # 32 bytes — bytes32 of ioID DID + TBA binding
    commit_sha: bytes,         # 20 bytes — git SHA-1
    prev_commit_hash: bytes,   # 32 bytes — chained ref; zeros for genesis
    repo_uri_sha: bytes,       # 32 bytes — SHA-256 of canonical repo URI
    ts_ns: int,                # uint64 — agent's claimed commit timestamp
) -> bytes:
    return hashlib.sha256(
        _AGENT_COMMIT_TAG +
        agent_id +
        commit_sha +
        prev_commit_hash +
        repo_uri_sha +
        struct.pack(">Q", ts_ns)
    ).digest()  # 136 bytes input → 32 bytes output

def genesis_agent_commit(agent_id: bytes, ts_ns: int) -> bytes:
    """Genesis agent commit — prev_commit_hash is zeros."""
    return compute_agent_commit_hash(
        agent_id=agent_id,
        commit_sha=b"\x00" * 20,
        prev_commit_hash=b"\x00" * 32,
        repo_uri_sha=hashlib.sha256(
            b"https://github.com/ConWan30/vapi-pebble-prototype"
        ).digest(),
        ts_ns=ts_ns,
    )
```

Validation (raises ValueError on bad input): all bytes-length checks,
ts_ns range check `0 <= ts_ns <= 0xFFFFFFFFFFFFFFFF`.

- **Store table schema** (`bridge/vapi_bridge/store.py` migration):

```sql
CREATE TABLE agent_commit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_hash TEXT NOT NULL UNIQUE,        -- hex of agent_commit hash
    agent_id TEXT NOT NULL,                  -- hex of bytes32 agent_id
    commit_sha TEXT NOT NULL,                -- hex of git SHA-1 (40 chars)
    prev_commit_hash TEXT NOT NULL,          -- hex; "0"*64 for genesis
    repo_uri_sha TEXT NOT NULL,              -- hex
    ts_ns INTEGER NOT NULL,
    tx_hash TEXT NOT NULL DEFAULT '',        -- on-chain anchor tx
    on_chain_confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_agent_commit_log_agent_id ON agent_commit_log(agent_id);
CREATE INDEX idx_agent_commit_log_ts_ns ON agent_commit_log(ts_ns);
CREATE UNIQUE INDEX idx_agent_commit_log_commit_hash ON agent_commit_log(commit_hash);
```

Schema version: `schema_versions(238, "agent_commit_log")` (next
available version after current Phase 237.5 latest).

- **Chain wrapper** (in `bridge/vapi_bridge/chain.py`):

```python
async def anchor_agent_commit(
    self,
    commit_hash_hex: str,
    agent_id_hex: str,
) -> tuple[Optional[str], bool]:
    """Anchor AGENT_COMMIT v1 on AgentAdjudicationRegistry.

    Returns (tx_hash, on_chain_confirmed). On error returns (None, False).
    Respects chain_submission_paused kill-switch from Phase 237.5 Path C+.
    """
    if self._cfg.chain_submission_paused:
        log.warning("chain.anchor_agent_commit: kill-switch active; skipping")
        return (None, False)
    # ... call AgentAdjudicationRegistry.anchorAgentAction(
    #     commit_hash, agent_id, "AGENT_COMMIT"
    # ) with dynamic gas estimate × 1.25 buffer per Phase 237.5 Path X
```

- **PV-CI invariants to freeze**:
  - **INV-AGENT-COMMIT-001**: function `compute_agent_commit_hash`
    exists in `bridge/vapi_bridge/agent_commit.py` with the canonical
    signature (matches V10's Section 3 architectural details).
  - **INV-AGENT-COMMIT-002**: domain tag literal
    `b"VAPI-AGENT-COMMIT-v1"` pinned in `agent_commit.py`.

Pattern: matches `INV-CORPUS-001` and `INV-CORPUS-002` from Phase 237.5
(see `scripts/vapi_invariant_gate.py:264-277`).

- **Test file paths**:
  - `bridge/tests/test_phase_o0_agent_commit.py` — module-level tests:
    hash determinism (same inputs → same hash), tamper detection (one
    bit change → different hash), genesis anchoring, ValueError on bad
    inputs, store insert idempotency.
  - `bridge/tests/test_phase_o0_agent_commit_chain.py` — chain wrapper
    tests with `chain_submission_paused=True/False` paths; mocked
    `AgentAdjudicationRegistry.anchorAgentAction` call.

Estimated 6-8 bridge tests for AGENT_COMMIT v1.

### Section 4.2 — PHYSICAL_DATA_ATTESTATION v1 (seventh FROZEN-v1 primitive)

- **Bridge module file path**: `bridge/vapi_bridge/physical_data_attestation.py`
- **Pattern**: same as AGENT_COMMIT v1; follows `corpus_snapshot.py`
  shape with adapted hash formula.
- **Hash formula** (per Pass 2B Path 3, Section 4 architectural details
  — frozen at Phase O0 deploy):

```python
_PDA_TAG = b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"  # 32 bytes

def compute_pda_hash(
    hardware_data_hash: bytes,    # 32 bytes — SHA-256 of physical data
    agent_id: bytes,              # 32 bytes — bytes32 agent_id
    attestation_type: bytes,      # 32 bytes — keccak256 of type string
    ts_ns: int,                   # uint64 — attestation timestamp
) -> bytes:
    return hashlib.sha256(
        _PDA_TAG +
        hardware_data_hash +
        agent_id +
        attestation_type +
        struct.pack(">Q", ts_ns)
    ).digest()  # 136 bytes input → 32 bytes output

def attestation_type_from_string(s: str) -> bytes:
    """Compute attestation_type bytes32 from canonical type string.

    Uses keccak256 (not SHA-256) to match on-chain conventions for
    string-to-bytes32 hashing in Solidity/EVM contexts.
    """
    from eth_utils import keccak
    return keccak(s.encode("utf-8"))
```

Recognized attestation_type strings (canonical vocabulary; see Section
4.3):
- `"BIOMETRIC_CORPUS_SNAPSHOT"` — agent attests to a CORPUS-SNAPSHOT v1
  derived from biometric data
- `"POAC_CHAIN_INTEGRITY"` — agent attests to a PoAC chain root
- `"TREMOR_FFT_FEATURE_VECTOR"` — agent attests to a tremor FFT feature
  vector hash
- `"FLEET_COHERENCE_OBSERVATION"` — agent attests to a fleet coherence
  finding
- `"HARDWARE_CERTIFICATION"` — agent attests to a hardware certification
  proof

Validation: all bytes-length checks; ts_ns range; attestation_type MUST
be 32 bytes (raises if not).

- **Store table schema**:

```sql
CREATE TABLE physical_data_attestation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pda_commitment TEXT NOT NULL UNIQUE,     -- hex of PDA hash
    hardware_data_hash TEXT NOT NULL,        -- hex
    agent_id TEXT NOT NULL,
    attestation_type TEXT NOT NULL,          -- canonical string (not hash)
    attestation_type_hash TEXT NOT NULL,     -- hex of keccak256(string)
    ts_ns INTEGER NOT NULL,
    tx_hash TEXT NOT NULL DEFAULT '',
    on_chain_confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_pda_log_agent_id ON physical_data_attestation_log(agent_id);
CREATE INDEX idx_pda_log_ts_ns ON physical_data_attestation_log(ts_ns);
CREATE INDEX idx_pda_log_attestation_type ON physical_data_attestation_log(attestation_type);
CREATE UNIQUE INDEX idx_pda_log_commitment ON physical_data_attestation_log(pda_commitment);
```

Schema version: `schema_versions(239, "physical_data_attestation_log")`.

The `attestation_type` column stores the canonical string (e.g.,
`"BIOMETRIC_CORPUS_SNAPSHOT"`); the `attestation_type_hash` stores
the keccak256 hash that was used in the PDA hash formula. Both stored
for query convenience and audit trail clarity.

- **Chain wrapper**:

```python
async def anchor_pda_attestation(
    self,
    pda_commitment_hex: str,
    agent_id_hex: str,
    attestation_type: str,
) -> tuple[Optional[str], bool]:
    """Anchor PHYSICAL_DATA_ATTESTATION v1 on AgentAdjudicationRegistry.

    Calls anchorAgentAction(pda_commitment, agent_id, "PHYSICAL_DATA_ATTESTATION").
    Note: actionType is the literal string, distinct from attestation_type
    (the latter differentiates kinds of physical data within PDA records).
    """
    if self._cfg.chain_submission_paused:
        log.warning("chain.anchor_pda_attestation: kill-switch active; skipping")
        return (None, False)
    # ... call with dynamic gas estimate × 1.25 buffer
```

- **PV-CI invariants to freeze**:
  - **INV-PDA-001**: function `compute_pda_hash` exists in
    `bridge/vapi_bridge/physical_data_attestation.py` with canonical
    signature.
  - **INV-PDA-002**: domain tag literal
    `b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"` pinned.

- **Test file paths**:
  - `bridge/tests/test_phase_o0_pda.py` — module tests
  - `bridge/tests/test_phase_o0_pda_chain.py` — chain wrapper tests

Estimated 6-8 bridge tests for PHYSICAL_DATA_ATTESTATION v1.

### Section 4.3 — actionType Vocabulary for AgentAdjudicationRegistry

`AgentAdjudicationRegistry.anchorAgentAction(actionHash, agentId, actionType)`
takes `actionType` as a string discriminator. The canonical Phase O0
actionType vocabulary:

| actionType | Maps to primitive | Purpose |
|---|---|---|
| `"AGENT_COMMIT"` | AGENT_COMMIT v1 | Anchors a git commit attestation |
| `"PHYSICAL_DATA_ATTESTATION"` | PHYSICAL_DATA_ATTESTATION v1 | Anchors a physical-data binding |
| `"AUDIT_LOG_CHECKPOINT"` | (future P1+) | Anchors a Tessera signed-tree-head; not yet active |
| `"BOUNDARY_UPDATE"` | (future P3+) | Anchors a scope/policy bundle update; not yet active |

Phase O0 ships only the first two as live vocabulary; the latter two
are reserved (recognized by the contract but not yet exercised by
agents). The `requireAgentScope` modifier rejects calls with
unrecognized actionType strings — at Phase O0 exit, both agents have
empty scope so all calls are rejected anyway, consistent with no-
operational-authority.

The vocabulary expansion path is governance-event-style: adding a new
actionType requires a `--reason "ceremony_update: ..." ` invocation of
the invariant gate plus a (future) AgentRegistry capability update.
Phase O0 freezes the vocabulary at four entries.

### Section 4.4 — Bridge endpoint surface (audit-stable)

Per Input 8 (audience: businesses/institutions), audit endpoints must
be stable across versions for compliance teams to trust historical
queries. Phase O0 ships the following GET endpoints (all read-only,
require x-api-key header per `_check_read_key`):

- `GET /agent/agent-commit-history?agent_id=<hex>&limit=<n>` — returns
  AGENT_COMMIT v1 records DESC by ts_ns; max limit=100.
- `GET /agent/agent-commit-status?commit_hash=<hex>` — returns single
  record by commit_hash; 404 if not found.
- `GET /agent/physical-data-attestation-history?agent_id=<hex>&attestation_type=<str>&limit=<n>` —
  returns PDA records, optional filter by attestation_type.
- `GET /agent/physical-data-attestation-status?pda_commitment=<hex>` —
  returns single record by commitment; 404 if not found.
- `GET /agent/agent-registry-status?agent_id=<hex>` — returns
  AgentRegistry view of agent (publicKey, scopeHash, status).

These endpoints become audit surfaces from Phase O0 onward and must
maintain backward compatibility per the API stability guarantees Pass
2C Section 9 surfaces.

---

## Section 5 — Bridge Infrastructure Additions

### Section 5.1 — Authentication Layer (Pass 2A V2 Option B)

#### OAuth 2.1 client credentials implementation path

**File path**: `bridge/vapi_bridge/agent_auth.py` (NEW module).

**Module exports**:
- `_check_agent_token(authorization_header, x_agent_keyid, x_timestamp,
   x_nonce, x_signature, request)` — FastAPI dependency.
- `mint_token(client_id, client_secret, scopes, ttl_seconds)` —
  internal token issuer.
- `verify_token(token)` — verifies JWT signature and TTL.

**Token format**: HS256 JWT (per Pass 2A V2 Option B architectural
details — HS256 in P0 for simplicity; RS256 deferred to P3+).

JWT claims:
- `sub` — agent_id (matches AgentRegistry agentId hex)
- `iss` — `"vapi-bridge-oauth"`
- `aud` — `"vapi-bridge-agent-endpoints"`
- `exp` — TTL: 60-300 seconds per architecture document specification
- `iat` — issued at
- `scope` — space-separated scope list (e.g., `"bridge:agent:phases:read
  bridge:agent:agent-commit:read"`)

**Token issuer hosting**: Phase O0 hosts the issuer as a module within
the existing bridge process (`bridge/vapi_bridge/oauth_issuer.py`),
NOT as a separate service. Operator decision per Pass 2B Section 8
Open Question 3 — open during Pass 2C; decision logged in Section 9
of this pass.

**Credential storage** (Phase O0):
- `OAUTH_CLIENT_ID_SENTRY` and `OAUTH_CLIENT_SECRET_SENTRY` in
  `bridge/.env.testnet` (env-var-backed; matches existing operator key
  pattern).
- `OAUTH_CLIENT_ID_GUARDIAN` and `OAUTH_CLIENT_SECRET_GUARDIAN` similarly.
- KMS migration deferred to P3+ when KMS infrastructure exists for git
  signing keys (per V2 architectural details).

#### HMAC request signing implementation path

**Canonical request format** (per architecture document section 7):
```
METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(body)
```

**Headers**:
- `X-Agent-KeyId` — agent's HMAC key identifier (matches AgentRegistry)
- `X-Timestamp` — Unix seconds; ±300s clock skew window enforced
- `X-Nonce` — UUIDv4 or similar; nonce dedup applies
- `X-Signature` — base64 HMAC-SHA-256 of the canonical string

**Verification function**: `_verify_hmac_signature(headers, body)` in
`agent_auth.py`.

**Nonce store** (Phase O0): in-memory LRU with TTL eviction. TTL = 600
seconds (twice the ±300s clock skew window per Pass 2B Section 8 Open
Question 4). Redis-backed nonce store deferred to P3+.

**Implementation reuse**: existing HMAC infrastructure at
`bridge/vapi_bridge/operator_api.py:223,243,255,1442` provides the
HMAC primitive; new code adds the canonical-request-string + nonce
dedup + timestamp window logic.

#### Integration with existing `_check_key`/`_check_read_key`

The two auth paths coexist:
- **Operator endpoints** (existing 154+ endpoints) continue using
  `_check_key(api_key)` and `_check_read_key(x_api_key)` from
  `operator_api.py`. No changes to these patterns.
- **Agent endpoints** (Phase O0 new endpoints from Section 4.4 +
  any future P1+ endpoints) use new
  `_check_agent_token(...)` dependency from `agent_auth.py`.

Per-endpoint annotation pattern:
```python
# Operator endpoint (existing)
@app.get("/operator/something")
def operator_endpoint(api_key: str = Query(...)):
    _check_key(api_key)
    ...

# Agent endpoint (new in Phase O0)
@app.get("/agent/agent-commit-history")
def agent_commit_history(
    auth: dict = Depends(_check_agent_token),
):
    ...
```

The `Depends(_check_agent_token)` dependency does both OAuth token
verification AND HMAC request signature verification. Failure of
either layer → HTTP 401.

#### Endpoint allowlist for agent-scoped tokens

Phase O0 ships the new audit endpoints (Section 4.4) protected by
`_check_agent_token`. **The agents themselves do not yet hold tokens**
— Phase O0 provisions the tokens but does not distribute them to the
agents. Token distribution to active agents begins in P1.

Phase O0 endpoint allowlist for agent tokens (5 read-only endpoints):
- `GET /agent/agent-commit-history`
- `GET /agent/agent-commit-status`
- `GET /agent/physical-data-attestation-history`
- `GET /agent/physical-data-attestation-status`
- `GET /agent/agent-registry-status`

All require `bridge:agent:phases:read` OAuth scope. Write endpoints
are not in Phase O0 scope.

### Section 5.2 — Path Scope Gate (Pass 2A V5 Option B)

#### `scripts/vapi_path_scope_gate.py` specification

**Script structure**:
```python
def parse_codeowners(path: Path) -> list[tuple[str, list[str]]]:
    """Parse .github/CODEOWNERS into (path_glob, [owners]) entries.

    Skips comments (#) and blank lines. Respects glob ordering: later
    entries override earlier ones for matching paths (GitHub convention).
    """

def enumerate_changed_paths(base_ref: str, head_ref: str) -> list[str]:
    """Run `git diff --name-only base_ref..head_ref`; return paths."""

def identify_author() -> str:
    """In CI: read GITHUB_ACTOR env var.
       Locally: git log -1 --format='%ae'.
       For agent commits: GitHub App bot login (e.g., 'vapi-anchor-sentry[bot]').
    """

def check_path_scopes(
    changed_paths: list[str],
    author: str,
    codeowners: list[tuple[str, list[str]]],
) -> list[dict]:
    """Returns list of violations (or [] if all paths within scope)."""

def run_gate(base_ref: str, head_ref: str) -> int:
    """Orchestrator. Exit 0=pass, 1=fail. Reports each violation
    with path, expected owner, actual author, remediation."""
```

**CODEOWNERS file** (`/.github/CODEOWNERS`):

```
# VAPI repo CODEOWNERS — Phase O0+ lane discipline
# Anchor Sentry's lane (provenance + wiki + events)
wiki/**             @vapi-anchor-sentry[bot]
provenance/**       @vapi-anchor-sentry[bot]
events/**           @vapi-anchor-sentry[bot]

# Guardian's lane (operational health + audits + invariants)
ops/**              @vapi-guardian[bot]
audits/**           @vapi-guardian[bot]
sweeps/**           @vapi-guardian[bot]
invariants/**       @vapi-guardian[bot]

# Human-only paths (require human author for any modification)
contracts/**        @ConWan30
bridge/**           @ConWan30
scripts/**          @ConWan30
sdk/**              @ConWan30
frontend/**         @ConWan30
CLAUDE.md           @ConWan30
VAPI-WORKFLOW.v2/** @ConWan30
.github/**          @ConWan30
```

**Note on Phase O0 mode**: Phase O0 sets the bot-owner paths but
neither bot has commit authority yet. Path-scope gate enforces "if a
commit is by `vapi-anchor-sentry[bot]`, only `wiki/**`, `provenance/**`,
or `events/**` paths can be modified — otherwise reject." This
enforcement runs from Phase O0 onward; bot commits begin in P2
(Suggestion mode → drafting PRs).

#### `.github/workflows/vapi-path-scope-gate.yml`

**Workflow file structure**:
```yaml
name: VAPI Path Scope Gate
on: [pull_request]
permissions:
  pull-requests: write
  contents: read
jobs:
  path-scope-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - name: Run path scope gate
        run: |
          python scripts/vapi_path_scope_gate.py \
            --base ${{ github.base_ref }} \
            --head ${{ github.sha }}
      - name: Comment on PR if failed
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            # Post violations as PR comment with remediation guidance
```

Pattern matches existing `.github/workflows/vapi-invariant-gate.yml`
from Phase 224.

#### Configuration format

CODEOWNERS is the source of truth. No additional configuration file
needed for Phase O0. Future agent-CI checks (commit-message format,
KMS key fingerprint, etc.) may add their own configurations; each
follows the focused-script-per-concern pattern.

#### Error messaging

When a commit is rejected, the gate output includes:
```
[path-scope-gate] VIOLATIONS:
  bridge/vapi_bridge/store.py
    expected owner: @ConWan30
    actual author:  @vapi-guardian[bot]
    remediation: revert this change OR update CODEOWNERS to grant
                 @vapi-guardian[bot] access to bridge/** (governance
                 review required — this is a human-only path).
[path-scope-gate] EXIT 1
```

### Section 5.3 — Lane Reorganization (Design Pass 1 Conflict 3 Option A)

#### File moves

```bash
# Use git mv to preserve history
git mv wiki/audits/contradictions.md audits/contradictions.md
git mv wiki/audits/phase_224_legacy_endpoint_audit.md audits/phase_224_legacy_endpoint_audit.md
git mv wiki/sweeps/sweep_20260426_clean.md sweeps/sweep_20260426_clean.md

# Remove now-empty directories
rmdir wiki/audits/
rmdir wiki/sweeps/
```

Three files moved. Two directories removed.

#### `vapi_wiki_engine.py` reference updates

Six reference points identified by grep:

| Line | Current content | Updated content |
|---|---|---|
| 52 | `v writes wiki/sweeps/sweep_{ts}.md` (docstring) | `writes sweeps/sweep_{ts}.md` |
| 108 | `WIKI_SWEEPS = WIKI / "sweeps"` | `SWEEPS_DIR = REPO_ROOT / "sweeps"` (new top-level constant) |
| 329 | `WIKI_SYNTH, WIKI_WHATIF, WIKI_SWEEPS, WIKI_BRIEFS]` (init list) | Remove `WIKI_SWEEPS` from this list; add `SWEEPS_DIR.mkdir(parents=True, exist_ok=True)` to a parallel init step |
| 636 | `Writes sweep record to wiki/sweeps/` (docstring) | `Writes sweep record to sweeps/` |
| 701 | `sweep_path = WIKI_SWEEPS / f"sweep_..."` | `sweep_path = SWEEPS_DIR / f"sweep_..."` |
| 724 | `print(f"\n[SWEEP] wiki/sweeps/{sweep_path.name}")` | `print(f"\n[SWEEP] sweeps/{sweep_path.name}")` |

#### Documentation references that need updating

References to `wiki/audits/` and `wiki/sweeps/` in working documents
(historical references in commit messages stay valid; only update
working-document references that resolve paths):

- `CLAUDE.md` — search for `wiki/sweeps/` and `wiki/audits/`; update
  any references that resolve paths.
- `VAPI-WORKFLOW.v2/VAPI_CONTEXT.md` — same.
- `VAPI-WORKFLOW.v2/VAPI_MEMORY.md` — Section 10 has reference to
  `monitoring/skill14_phase237_5.json; ingested as wiki/sweeps/...` —
  update.
- `wiki/phases/phase_237_5.md` — has explicit
  `wiki/sweeps/sweep_20260426_clean.md` reference — update.
- `monitoring/skill14_phase237_5.json` — has wiki/sweeps reference —
  update.

#### Order of operations (preserves referential integrity)

Atomic single-commit:
1. `git mv` the three files.
2. `rmdir wiki/audits/` and `rmdir wiki/sweeps/`.
3. Update `vapi_wiki_engine.py` 6 references.
4. Update working-document references in CLAUDE.md, VAPI_CONTEXT.md,
   VAPI_MEMORY.md, wiki/phases/phase_237_5.md,
   monitoring/skill14_phase237_5.json.
5. Run `python -c "import ast; ast.parse(open('vapi_wiki_engine.py').read())"`
   — confirm no syntax errors.
6. Run `python vapi_wiki_engine.py phase_close <next>` smoke test —
   confirm engine produces output to new sweeps/ path.
7. Single commit titled
   `"phase_o0(lane): wiki/audits/ → audits/, wiki/sweeps/ → sweeps/"`

This commit must land BEFORE the path-scope gate workflow goes live —
the gate reads CODEOWNERS which uses post-migration paths. Sequencing
is enforced in Stream 1 of the operational order in Section 1.

---

## Section 6 — Agent Identity Infrastructure

### Section 6.1 — ioID DID Minting

**Target contracts** (verified live this session via V3 finding):

| Contract | Address | Purpose |
|---|---|---|
| ProjectRegistry | `0x060581AA1A4e0cC92FBd74d251913238De2F13cd` | Register agent project |
| ioIDRegistry | `0x0A7e595C7889dF3652A19aF52C18377bF17e027D` | Mint ioID DID |
| ioID NFT | `0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` | DID NFT collection |
| ERC-6551 Registry | `0x000000006551c19487814612e58FE06813775758` | Token-bound account registry |

**Mint sequence** (AMENDED 2026-05-02 — see Section 13 — corrected per
read-only investigation findings against deployed ioIDRegistry,
ProjectRegistry, and ERC-6551 Registry contracts on IoTeX testnet
cross-referenced against ioID-contracts canonical source at commit
`b94ad092b84f83fba068ed83bc28b72dd6f2cc4f`; the original mint
sequence below is preserved as historical record):

1. Register the **VAPI Operator Agents project** on ProjectRegistry
   **once per VAPI deployment** (not per agent — both agents share
   the project NFT distinguished by per-agent ERC-6551 salts per
   K1a + I2b 2026-05-02 operator decisions). Call:

   ```solidity
   ProjectRegistry.register("VAPI Operator Agents", <projectType>)
       // selector 0x767b79ed
   ```

   Exact `projectType` uint8 value empirically verified during
   amendment implementation session against ioID-contracts canonical
   source at commit `b94ad092` (`contracts/ProjectRegistry.sol`) and
   on-chain enum query (delegated per Section 13.6 OQ2). Output:
   project_id (uint256). The bridge wallet receives one IProject NFT
   at contract `0xf07336e1c77319b4e740b666eb0c2b19d11fc14f` (the
   canonical NFT contract for ERC-6551 binding per Section 13.4 K3
   clarification — distinct from the per-DID NFT infrastructure
   referenced in the original mint sequence).

   [NOTE 2026-05-02 third amendment: original Section 6.1 step 1
   specified two project registrations (one per agent). Per K1a
   architectural reconciliation, ioIDRegistry binds devices to
   project NFTs distinguished by unique device addresses (multiple
   devices register against the same project NFT); capability-level
   distinction lives at the agent layer (capability specs at commit
   52978771), not at the project NFT layer. One project + per-agent
   salts is operationally and cost-simpler than two projects +
   shared salt and preserves the same security properties.]

2. **Pin the agent's DID document JSON-LD to IPFS** via Pinata
   (Q7 / Section 6.4 implementation at commit `dcaf5015`). Compute
   the content hash (`keccak256` over canonical content per
   ioID-contracts hash convention). Output: IPFS CID (the URI),
   bytes32 content hash.

   [NOTE 2026-05-02 third amendment: this step is new — the
   original mint sequence implied register-then-pin ordering,
   but the corrected ioIDRegistry.register signature (step 3)
   requires both the URI and content hash as inputs. Pin must
   precede register. Corrected orchestration documented in
   Section 13.5.]

3. Mint ioID DID via ioIDRegistry. Call:

   ```solidity
   ioIDRegistry.register(
       address deviceContract,    // IProject = 0xf07336e1c77319b4e740b666eb0c2b19d11fc14f
       uint256 tokenId,           // project_id from step 1
       address device,            // agent's ECDSA-secp256k1 ETH address (KMS-derived)
       bytes32 hash,              // content hash from step 2
       string calldata uri,       // IPFS URI from step 2
       uint8 v, bytes32 r, bytes32 s   // EIP-712 signature by `device`
   )
       // selector 0x39a4a241
   ```

   The 8-param signature with EIP-712 `(v, r, s)` components is the
   canonical ioIDRegistry.register signature, verified empirically
   in deployed bytecode (selector `0x39a4a241` present in the
   dispatch table; the original 2-param `register(uint256, address)`
   selector `0xdbbdf083` is NOT in deployed bytecode). EIP-712
   signature flow detailed in Section 13.3. Output: `did:io:<device>`
   identifier (the device address itself).

   [NOTE 2026-05-02 third amendment: original 2-parameter signature
   `ioIDRegistry.register(uint256, address)` was assumed without
   empirical verification against deployed bytecode; corrected per
   Section 13.2 against ioID-contracts canonical source at commit
   `b94ad092` (`contracts/ioIDRegistry.sol`). The EIP-712 signature
   flow (uint8 v, bytes32 r, bytes32 s) is new functionality not
   present in the original specification — see Section 13.3 for
   implementation requirements.]

4. Bind ERC-6551 TBA via the ERC-6551 Registry singleton
   (`0x000000006551c19487814612e58FE06813775758`). Call:

   ```solidity
   ERC6551Registry.createAccount(
       implementation,       // standard ERC-6551 Account implementation
       <salt>,               // per-agent salt:
                             //   keccak256("vapi-anchor-sentry") for Sentry
                             //   keccak256("vapi-guardian") for Guardian
                             //   per I2b
       chainId,              // 4690 (IoTeX testnet)
       0xf07336e1c77319b4e740b666eb0c2b19d11fc14f,  // IProject NFT per K3
       project_id            // from step 1 (same project NFT for both agents)
   )
       // selector 0x8a54c52f
   ```

   Per K1a + I2b: the same project NFT (one tokenId for the entire
   VAPI Operator Agents project) is bound to two distinct TBAs via
   per-agent salts. Sentry's TBA ≠ Guardian's TBA despite the
   shared (deviceContract, tokenId) pair — the salt distinguishes
   them, preserving identity distinction at the on-chain level
   matching the capability spec distinction at commit `52978771`
   (Sentry's wiki/provenance/attestation lane vs Guardian's
   audits/sweeps/operational-stewardship lane). Output: distinct
   TBA address per agent.

   [NOTE 2026-05-02 third amendment: per-agent salts replace the
   original `salt=bytes32(0)` per I2b. NFT contract address
   corrected to IProject `0xf07336e1c77319b4e740b666eb0c2b19d11fc14f`
   per K3 — the original address `0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7`
   is per-DID infrastructure (per-DID NFTs minted internally by
   ioIDRegistry, not ERC-6551-bindable). The original Section 6.1
   step 3 conflated these two NFT contracts. See Section 13.4 for
   canonical NFT address clarification.]

*Original mint sequence per agent (executed twice, once for each
agent), preserved for historical record of design phase reasoning
that produced the original Pass 2C 2026-04-27 specification:*

> 1. Register agent project on ProjectRegistry. Project name:
>    `"vapi-anchor-sentry"` for Sentry; `"vapi-guardian"` for
>    Guardian. Output: project_id (uint256).
>    [SUPERSEDED 2026-05-02 — per K1a, one project NFT shared
>    across both agents replaces two-project architecture]
>
> 2. Mint ioID DID via ioIDRegistry. Input: project_id,
>    deviceAddress (the agent's ECDSA public key, derived from
>    KMS-backed signing key — see Section 6.3). Output:
>    did:io:<address> identifier + ioID NFT tokenId.
>    [SUPERSEDED 2026-05-02 — 2-param signature does not match
>    deployed bytecode per Section 13.2; EIP-712 signature flow
>    missing per Section 13.3]
>
> 3. Bind ERC-6551 TBA via the ERC-6551 Registry. Input: ioID NFT
>    contract address (`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7`),
>    tokenId (from step 2), salt=bytes32(0), implementation address
>    (standard ERC-6551 Account implementation). Output: TBA
>    address (the agent's on-chain account).
>    [SUPERSEDED 2026-05-02 — NFT contract address corrected to
>    IProject `0xf07336e1c77319b4e740b666eb0c2b19d11fc14f` per K3
>    + Section 13.4; salt=bytes32(0) replaced by per-agent salts
>    per I2b]

**DID document JSON-LD structure** (stored on IPFS):

```json
{
  "@context": ["https://www.w3.org/ns/did/v1"],
  "id": "did:io:0x<address>",
  "verificationMethod": [{
    "id": "did:io:0x<address>#kms-key-1",
    "type": "EcdsaSecp256k1VerificationKey2019",
    "controller": "did:io:0x<address>",
    "publicKeyHex": "0x<pubkey>"
  }],
  "authentication": ["did:io:0x<address>#kms-key-1"],
  "service": [{
    "id": "did:io:0x<address>#vapi-agent",
    "type": "VAPIOperatorAgent",
    "serviceEndpoint": "https://github.com/apps/vapi-anchor-sentry"
  }],
  "metadata": {
    "agentRole": "ANCHOR_SENTRY",
    "vapiPhase": "P0",
    "modelClass": "claude-sonnet-4-6",
    "createdAt": "<iso8601>"
  }
}
```

The `metadata.modelClass` field implements V6 finding's open question 6
about whether the SBT identity should include a model_class field.
Phase O0 includes it; this is the cryptographic-claim formulation
operator decision.

**Estimated gas costs per agent**:
- ProjectRegistry registration: ~0.02 IOTX
- ioIDRegistry mint: ~0.02 IOTX
- ERC-6551 TBA bind: ~0.02 IOTX
- IPFS pin: ~$0.001 USD via Pinata or self-hosted

**Total per agent**: ~0.06 IOTX. **Two agents**: ~0.12 IOTX. Within
the 5 IOTX wallet budget.

### Section 6.2 — GitHub Apps Registration

**App 1: `vapi-anchor-sentry[bot]`**

- App name: `vapi-anchor-sentry`
- App description: "Anchor Sentry — VAPI Operator Agent for provenance
  binding (off-chain wiki ↔ on-chain attestation chain)"
- Permissions:
  - **Contents**: Read & write (for committing to wiki/, provenance/,
    events/ paths only — enforced by path-scope gate)
  - **Pull requests**: Write (for opening PRs in P2+)
  - **Metadata**: Read
  - **Issues**: Read
- Subscribe to events: `pull_request`, `push`, `workflow_run`
- Webhook URL: `https://<bridge-host>/webhook/vapi-anchor-sentry`
  (deferred to P1+; webhook handler not in P0 scope)
- Private key: KMS-backed (see Section 6.3)

**App 2: `vapi-guardian[bot]`**

- App name: `vapi-guardian`
- App description: "Guardian — VAPI Operator Agent for operational
  health stewardship (FSCA monitoring, invariant audit, autoresearch
  evaluation)"
- Permissions: same as Anchor Sentry, but path-scope gate enforces
  ops/, audits/, sweeps/, invariants/ paths only.
- Webhook URL: `https://<bridge-host>/webhook/vapi-guardian` (deferred)

Both apps installed on the `ConWan30/vapi-pebble-prototype` repository.

### Section 6.3 — KMS Key Provisioning

**KMS provider decision** (AMENDED 2026-05-02 — see Section 12 —
supersedes 2026-05-01 amendment in Section 11): AWS KMS in `us-east-1`
per the 2026-05-02 amendment, reverting the 2026-05-01 substitution
to Lit Protocol after Q1-Q5 expanded investigation revealed Lit
Protocol's iteration velocity (Datil V0 → Naga V1 → Chipotle V3 in
approximately 12 months, with Naga V1 production lifespan only ~3.5
months) and absence of formal stability commitments to production
users (no SLA, no LTS, no deprecation policy). VAPI's operator
agents are an outer governance layer; the protocol trust root is
hardware-anchored to DualShock Edge ECDSA-P256 PoAC chain and
remains unaffected by KMS provider choice. AWS KMS's 12-year API
stability + formal SLA + minimal API churn outweigh DePIN thesis
preservation at the operator-agent layer for VAPI's specific use
case (long-lived agent identity for permanent on-chain attestation).

*Original Pass 2C provisional (2026-04-27, preserved for historical
context)*: AWS KMS preferred per architecture document section 7.
Operator must have AWS account with KMS access. If AWS unavailable
to the operator, alternative providers (GCP KMS, Azure Key Vault,
HashiCorp Vault) require equivalent capabilities (asymmetric ECDSA
key generation, signing API, audit logging).

*2026-05-01 substitution to Lit Protocol (superseded by 2026-05-02
amendment — historical record at Section 11)*: Lit Protocol PKPs
were chosen on DePIN-thesis-preservation grounds at the
highest-leverage point (agent commits become protocol truth
claims). The 2026-05-02 amendment reverts this based on Q1-Q5
findings; see Section 12 for full revision rationale and Section 11
for the 2026-05-01 reasoning preserved as historical record.

**Phase O0 KMS provisioning steps** (AMENDED 2026-05-02 — see
Section 12 — supersedes 2026-05-01 amendment in Section 11):
1. Create AWS KMS key per agent (2 keys total) in `us-east-1`:
   `KeySpec=ECC_SECG_P256K1` (curve correction preserved from
   2026-05-01 amendment matching DID template's
   `EcdsaSecp256k1VerificationKey2019` declaration + IoTeX EVM
   secp256k1 native compatibility; original Pass 2C 2026-04-27
   specified `ECC_NIST_P256` which V1 verification revealed
   inconsistent with the DID template), `KeyUsage=SIGN_VERIFY`. Key
   aliases: `alias/vapi-anchor-sentry-signing` and
   `alias/vapi-guardian-signing`.
2. Configure key policy + IAM credentials (**design target — verify
   applied per the private DR runbook; see D3 reconciliation note**):
   only the bridge IAM role can `kms:Sign` on these 2 specific KMS keys
   (minimum-privilege scoping); only the operator's IAM user can
   `kms:UpdateKeyDescription`, `kms:DisableKey`, `kms:DeleteKey`,
   etc. (administrative actions). Bridge IAM user credentials
   delivered as long-lived AWS IAM env vars in
   `bridge/.env` (gitignored, mode 600 directory; matches existing
   pattern for the IoTeX wallet key, GitHub App PEM paths, and
   API-key placeholders).
3. Export public key from KMS via `aws kms get-public-key` (one-time,
   post-creation). DER-encoded SubjectPublicKeyInfo; convert to hex
   for the DID document.
4. Use the public key as the agent's ioID DID `publicKeyHex` in
   Section 6.1 minting flow (matches DID template's
   `EcdsaSecp256k1VerificationKey2019` declaration).
5. **GitHub App authentication unchanged from Section 6.2** (per
   2026-05-01 amendment, reaffirmed 2026-05-02) — the GitHub-issued
   RSA-2048 PEMs at `bridge/secrets/vapi-anchor-sentry.pem` and
   `bridge/secrets/vapi-guardian.pem` (mode 600, gitignored) are
   the GitHub App authentication credentials. **No KMS migration.
   No Option B export ceremony.** V2 verification (2026-05-01)
   confirmed Section 6.2 already issued RSA-2048 PEMs satisfying
   GitHub's PEM-format auth requirement; the original Pass 2C step
   5 KMS-managed migration was solving a problem Section 6.2 had
   already implicitly resolved.

**Backup/DR posture** (per D2 in 2026-05-02 amendment): single-region
AWS KMS deployment in `us-east-1`. Recovery from AWS account loss via
DID rotation per Section 10 Note 6 — provision new KMS keys in a new
AWS account, mint replacement DID with new public keys (derived from
new KMS keys), register replacement in AgentRegistry. The TBA
persists; only the signing capability rotates. Multi-region replica
considered and rejected: AWS KMS supports multi-region replicas
natively but this addresses regional outage, not the realistic
failure mode (AWS account loss). Consistent with VAPI's existing
trust model where bridge wallet IoTeX private key in `bridge/.env`
has the same single-point-of-failure profile on a single host.

**KMS-vs-import constraint** (AMENDED 2026-05-02 — see Section 12 —
MOOT under amendments, reasoning updated from 2026-05-01): The
Option (a)/(b) split below applied to the GitHub App auth key, which
the 2026-05-01 amendment removed from KMS scope entirely (V2 finding:
Section 6.2 already issued RSA-2048 PEMs satisfying GitHub's
PEM-format auth requirement; no migration needed). The commit-signing
key (now AWS KMS in `us-east-1` per the 2026-05-02 amendment) uses
**Option (a)**: KMS-generated, signed via `kms:Sign` API call, key
material never leaves AWS KMS HSM. No export ceremony needed because
GitHub App auth keys are out of KMS scope (RSA PEMs retained per
2026-05-01 amendment). The original constraint analysis below is
preserved for historical reference of the design phase reasoning.

*Original constraint analysis (preserved as historical record)*:
GitHub Apps require a private key in PEM format for app authentication
(JWT signing for App-to-GitHub auth). KMS can either:
- (a) Generate the private key and never expose it; the bridge
  proxies signing requests through KMS API. This requires
  modifying the bridge's GitHub App auth flow to call KMS instead
  of using a local PEM file. Higher security, more complex
  implementation.
- (b) Generate the private key in KMS, then export it (one-time, with
  audit trail) for import to GitHub. Simpler but loses some KMS
  benefits.

*Original Phase O0 recommendation (now superseded by Section 11
amendment)*: Option (a) for the agent's commit signing key
(high-security); Option (b) for the GitHub App auth key (lower
sensitivity since GitHub already validates app-to-app). Decision
logged in Section 9 Open Question 3.

### Section 6.4 — Agent Registration in AgentRegistry

After Sections 6.1-6.3 complete, both agents are registered in the
AgentRegistry contract via owner-only `registerAgent(...)` call.

**Per-agent registration parameters**:
- `agentId`: `keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))`
  — bytes32 binding the DID and TBA together.
- `publicKey`: agent's ECDSA-secp256k1 public key from KMS
  (uncompressed, derived to address).
- `scopeHash`: `bytes32(0)` at Phase O0 exit (empty Cedar bundle —
  no operational authority).
- `status`: `DEFINED=0` (Phase O0 exit state per Section 3.1 enum).

**Verification**: `getAgent(agentId)` returns the registration tuple;
status = DEFINED confirms Phase O0 provisioning complete but agent
inactive.

---

## Section 7 — Phase O0 Operational Mode

Per architecture document section 9, Phase O0 is foundations only with
no agent operational authority. The agents do not yet act. Phase O0
provisions identity, scope contracts, primitive infrastructure, and
auth scaffolding so Phase O1 (shadow mode) can begin without further
prerequisite work.

### What Phase O0 explicitly does NOT include

**No agent process startup.** Both agents are registered in
AgentRegistry with `status=DEFINED`. No agent process runs. Neither
agent makes API calls to Anthropic, queries the bridge, observes
fleet state, or executes any logic. The agents exist as registered
identities but are not running software.

**No bridge endpoint allowlisting for agent tokens.** The 5 audit
endpoints from Section 4.4 are deployed and protected by
`_check_agent_token` middleware. But no token has been issued to
either agent. Phase O0 mints the OAuth client_id/secret and HMAC
signing keys; distribution to running agents is P1 work.

**No commit authority granted.** Both GitHub Apps are registered but
neither bot has yet pushed a commit. Path-scope gate enforces "if a
commit is authored by `vapi-anchor-sentry[bot]`, only paths in their
lane can be modified" — but no such commits exist yet at Phase O0
exit.

**No on-chain transactions from agent identities.** The agents have
ioID DIDs and ERC-6551 TBAs, but neither TBA has been used to send a
transaction. Both TBAs hold zero IOTX. Funding the TBAs (so they can
pay gas for on-chain anchors) is part of P3 (write tournament gate)
or P4 (invariant authorization) preparation.

**No EAS deployment.** Per Pass 2A V10 Option C: AGENT_COMMIT v1 is
VAPI-native; no EAS contracts deployed.

**No SPIRE/SPIFFE infrastructure.** Per Pass 2A V2 Option B: mTLS
deferred to P3+. The bridge runs as single Python asyncio process; no
service mesh.

**No Cedar policy bundles.** AgentScope contract ships with bundle
storage capability but bundle Merkle root is `bytes32(0)` for both
agents at Phase O0 exit. Cedar bundle authoring is P1+ work.

**No Tessera log infrastructure.** AuditLog contract ships with
append-only Merkle root storage. The upstream Tessera signed-tree-head
feed is not yet live. AuditLog has zero checkpoints at Phase O0 exit.

**No autoresearch loop modifications.** The existing autoresearch
infrastructure (`vapi_autoresearch.py`, FSCA in `fleet_signal_coherence_agent.py`)
runs independently of the Operator Agents in Phase O0. P1 begins to
wire Guardian's reasoning over FSCA outputs.

### What Phase O0 DOES include (summary)

- Identity registered (DIDs, TBAs, AgentRegistry)
- Identity backed by cryptographic signing capability (KMS keys)
- Identity associated with GitHub Apps
- Cryptographic primitives ready (AGENT_COMMIT v1, PHYSICAL_DATA_ATTESTATION v1)
- Authentication scaffolding ready (OAuth issuer + HMAC verification)
- CI gate enforcing path-scope discipline (CODEOWNERS-driven)
- Lane reorganization complete (audits/, sweeps/ at top level)
- Five new contracts deployed and tested

The transition from Phase O0 to Phase O1 is operator-triggered: when
the operator decides Phase O0 exit criteria are met (Section 8), they
authorize the start of P1 by issuing OAuth tokens to the agents and
turning on agent process startup.

---

## Section 8 — Phase O0 Exit Criteria (Revised)

Original architecture document section 9 P0 exit criteria (verbatim):

> "AgentRegistry, AgentScope, AuditLog, AgentSlashing written, audited
> internally, deployed to IoTeX testnet alongside the existing 46.
> ioID DIDs minted for both agents in ProjectRegistry and ioIDRegistry.
> ERC-6551 TBAs bound. EAS schemas registered. KMS keys provisioned.
> Two GitHub Apps registered. SPIRE issuing SVIDs. Cedar policies
> drafted and unit-tested. Tessera log running."

**Revised exit criteria** reflecting resolved inputs:

| # | Criterion | Verification method |
|---|---|---|
| 1 | AgentRegistry deployed on IoTeX testnet | `eth_getCode` returns nonempty bytecode at AgentRegistry address |
| 2 | AgentScope deployed | Same; address recorded in `deployed-addresses.json` |
| 3 | AuditLog deployed | Same |
| 4 | AgentSlashing deployed | Same |
| 5 | AgentAdjudicationRegistry deployed | Same; this contract is NEW per Pass 1 Conflict 1 |
| 6 | All 5 contracts pass internal Hardhat audit | `npx hardhat test contracts/test/PhaseO0_*.test.js` returns 30-50 passing tests, 0 failing |
| 7 | Contract count rises from 46 to 51 | `deployed-addresses.json` count + CLAUDE.md note block updated |
| 8 | AGENT_COMMIT v1 primitive infrastructure live | `bridge/vapi_bridge/agent_commit.py` exists; `agent_commit_log` table created; `chain.anchor_agent_commit` callable; tests passing |
| 9 | PHYSICAL_DATA_ATTESTATION v1 primitive infrastructure live | `bridge/vapi_bridge/physical_data_attestation.py` exists; `physical_data_attestation_log` table created; `chain.anchor_pda_attestation` callable; tests passing |
| 10 | INV-AGENT-COMMIT-001/002 + INV-PDA-001/002 in invariant gate | `python scripts/vapi_invariant_gate.py --report` shows 32 invariants (28 + 4 new); all PASS |
| 11 | INVARIANTS_ALLOWLIST.json regenerated | `.github/INVARIANTS_ALLOWLIST.json` contains 32 entries; governance event posted |
| 12 | ioID DIDs minted for both agents | `eth_getBalance` of TBA addresses returns nonzero state (TBA exists); ioID NFT tokenIds recorded |
| 13 | ERC-6551 TBAs bound for both agents | `getAccount(ioIDNFT, tokenId, ...)` view call returns the TBA address |
| 14 | KMS keys provisioned for both agents | KMS key aliases exist; signing capability tested via test signature |
| 15 | Two GitHub Apps registered | `vapi-anchor-sentry[bot]` and `vapi-guardian[bot]` visible in GitHub Apps; webhook URLs configured (placeholder OK at P0) |
| 16 | Both agents registered in AgentRegistry with status=DEFINED | `AgentRegistry.getAgent(agentId)` returns expected tuple |
| 17 | OAuth issuer + HMAC middleware live | `bridge/vapi_bridge/agent_auth.py` exists; `_check_agent_token` dependency works; mock token round-trip test passes |
| 18 | 5 new agent endpoints protected by `_check_agent_token` | curl test against each endpoint without token returns 401; with valid token returns 200 |
| 19 | `vapi_path_scope_gate.py` enforcing CODEOWNERS rules in CI | `.github/workflows/vapi-path-scope-gate.yml` runs on every PR; mock violation produces failure |
| 20 | `.github/CODEOWNERS` exists with 6 lane rules + human-only paths | File present; format valid per GitHub CODEOWNERS spec |
| 21 | Lane reorg complete: `audits/` + `sweeps/` at top-level | `audits/` and `sweeps/` directories exist; `wiki/audits/` + `wiki/sweeps/` removed; `vapi_wiki_engine.py` references updated |
| 22 | All bridge tests passing | `python -m pytest bridge/tests/` returns 2517 + ~16 new (PhaseO0 primitives) = ~2533 passing |
| 23 | All Hardhat tests passing | `npx hardhat test` returns 528 + 30-50 new = ~558-578 passing |
| 24 | Wallet balance ≥3 IOTX maintained throughout | `eth_getBalance` confirms wallet didn't drop below 3 IOTX during deploy sequence |

**Removed from original criteria**:
- "EAS schemas registered" (per Pass 2A V10 Option C — no EAS deploy)
- "SPIRE issuing SVIDs" (per Pass 2A V2 Option B — deferred to P3+)
- "Cedar policies drafted and unit-tested" (deferred to P1+ — agents
  have empty scope at P0 exit)
- "Tessera log running" (deferred to P1+ — AuditLog contract ships,
  feed deferred)

**Added to original criteria**:
- AgentAdjudicationRegistry (per Pass 1 Conflict 1)
- AGENT_COMMIT v1 primitive (per Pass 2A V10)
- PHYSICAL_DATA_ATTESTATION v1 primitive (per Pass 2B Path 3)
- OAuth + HMAC auth layer (per Pass 2A V2 Option B)
- Path scope gate + CODEOWNERS (per Pass 2A V5 Option B)
- Lane reorganization (per Pass 1 Conflict 3)
- 4 new PV-CI invariants

Phase O0 is exited when all 24 criteria are verified. Each criterion
has a specific test or query that can be run to confirm.

---

## Section 9 — Open Questions for Phase O0 Implementation

These questions arose during Pass 2C synthesis but cannot be resolved
without operator decision before implementation begins. They are the
final operator-decision points before Phase O0 ships.

### Question 1 — OAuth issuer hosting topology

Per Pass 2B Section 8 Open Question 3 (carried forward from Pass 2A
V2): does the OAuth 2.1 token issuer run as:
- (a) A module within the existing bridge process
  (`bridge/vapi_bridge/oauth_issuer.py`), sharing the asyncio event
  loop?
- (b) A separate process on the bridge host (new Python service)?
- (c) A third-party self-hosted service (Authelia, Keycloak)?

Pass 2C provisionally specifies (a) for simplicity, but (b) provides
better isolation (token issuer compromise doesn't compromise bridge
DB) and (c) leverages existing tooling. Operator decision needed.

### Question 2 — KMS key for GitHub App auth: KMS-backed or imported?

Per Section 6.3, the GitHub App authentication private key has two
provisioning options:
- (a) KMS-generated, never exported, bridge proxies signing requests
  through KMS API.
- (b) KMS-generated, exported once for import to GitHub.

Pass 2C provisionally specifies (a) for the agent's commit signing
key (high-security) and (b) for the GitHub App auth key (lower
sensitivity). Operator decision: confirm split, or apply one
option uniformly?

### Question 3 — Anthropic API key per-agent management

Per V6 finding open question 5 (carried forward): how are per-agent
Anthropic API keys provisioned and rotated? Phase O0 doesn't yet need
the keys (agents are inactive) but P1 does. Three options:
- (a) Single shared `ANTHROPIC_API_KEY` in `bridge/.env` (existing
  pattern; SessionAdjudicator already uses this).
- (b) Per-agent keys in `bridge/.env`
  (`ANTHROPIC_API_KEY_SENTRY`, `ANTHROPIC_API_KEY_GUARDIAN`) for
  billing/rate-limit isolation.
- (c) KMS-managed keys alongside git signing keys.

Phase O0 decision matters because P1 implementation depends on it.
Operator decision: provision now or defer to P1 prep?

### Question 4 — Phase O0 deferral of branch protection enforcement

Per Pass 2B Section 8 Open Question 6: GitHub supports CODEOWNERS-
required reviewer enforcement at the branch protection level (require
approval from CODEOWNERS for each protected path before merge). Should
Phase O0 enable this branch protection on `main`, OR should the
path-scope gate be the sole enforcement mechanism?

Both are defensible. Branch protection adds an extra layer (reviewers
must approve in addition to gate passing). Path-scope-gate-only relies
on gate correctness. Operator decision.

### Question 5 — Drain-class structural fix scope

Per Pass 2A V8 Section 9 Open Question 9: should Phase O0 (or an
adjacent pre-O0 phase) include a structural fix to the
DualShock + batcher retry-blind paths that caused the Phase 237.5 Path
C+ wallet drain? Currently kill-switch-mitigated but not structurally
fixed. The risk is small but real if the kill-switch is ever lifted
inadvertently during Phase O0+ work.

Pass 2C does NOT include this in the implementation plan (out of scope
per "no Phase O0 scope expansion"), but flags for operator decision
whether a parallel work stream addresses it. If declined, the wallet's
5 IOTX target carries the drain-margin headroom to survive an
incident.

### Question 6 — Test count verification at Phase O0 exit

Phase O0 adds approximately:
- 30-50 Hardhat tests (5 contracts × 6-10 tests each)
- 12-16 bridge tests (2 primitives × 6-8 tests each)
- 0 SDK tests (Phase O0 doesn't ship SDK changes)

Final test counts at Phase O0 exit:
- Bridge: 2517 + 12-16 = 2529-2533
- Hardhat: 528 + 30-50 = 558-578
- SDK: 539 (unchanged)
- Contracts: 46 + 5 = 51

The CLAUDE.md note block update at Phase O0 exit should reflect these
counts. Operator decision: any additional tests required for Phase O0
exit beyond the categories above (e.g., E2E integration tests for the
full identity-mint flow)?

### Question 7 — DID document IPFS pinning provider

Section 6.1 specifies storing DID document JSON-LD on IPFS. IPFS pin
service options:
- (a) Pinata (commercial, ~$0.001 per pin) — operator account exists?
- (b) Web3.storage (Filecoin-backed, free tier).
- (c) Self-hosted IPFS node on bridge host.

Phase O0 provisionally specifies Pinata for simplicity and reliability.
Operator decision: confirm provider, or use alternative?

### Question 8 — `model_class` field in DID metadata

Per V6 finding open question 6: should the DID metadata include
`modelClass` (e.g., `"claude-sonnet-4-6"`) so the on-chain attestation
trace records which model produced the agent's reasoning? Anthropic
doesn't sign API responses, so the model claim is self-asserted, but
binding it to the DID prevents silent model-switching without
identity-trace.

Pass 2C provisionally includes `modelClass` in Section 6.1 DID
metadata. Operator decision: include in P0, defer, or omit entirely?

### Question 9 — Agent ID encoding canonical form

Section 6.4 specifies
`agentId = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))`.
Alternative encodings exist:
- (a) `keccak256(ioID_DID_address || TBA_address)` — concatenation.
- (b) Use ioID DID address directly as `bytes32` (zero-padded).
- (c) Use TBA address directly as `bytes32` (zero-padded).

The canonical form is FROZEN once first agent is registered (any later
change breaks AgentRegistry lookups). Operator decision: confirm
provisional choice or specify alternative?

### Question 10 — IPFS-of-Cedar-bundle storage strategy

Phase O0 doesn't ship Cedar bundles (deferred to P1+) but the bundle
storage strategy affects AgentScope.sol's design. Options:
- (a) Bundle stored on IPFS; bundle Merkle root anchored on-chain. P1
  authors the first bundle.
- (b) Bundle stored in repo (`bridge/vapi_bridge/cedar_bundles/`);
  bundle Merkle root anchored on-chain. P1 commits the first bundle.
- (c) Bundle stored on Tessera log; checkpoint anchored on-chain.

Pass 2C provisionally specifies (b) for simplicity. Operator decision
matters because AgentScope.sol's `setAgentScopeRoot` semantics could
include a bundle-fetch URL field in option (a) that doesn't exist in
option (b).

### Question 11 — Reconsidering prior-pass decisions

(Per the prompt's instruction: "If during implementation planning you
discover that a resolved decision needs revisiting, surface it as a
Section 9 open question for operator decision rather than treating it
as a Pass 2C finding.")

Pass 2C synthesis revealed no resolved-decision conflicts. All nine
resolved inputs map cleanly to Phase O0 deliverables (Section 2). No
recommendation to revisit prior decisions.

### Operator decisions (2026-04-27)

The operator confirmed all eleven question resolutions. The
resolutions are preserved verbatim in this permanent record so future
operators encountering Phase O0 implementation can read the exact
decisions that were made and the reasoning shape that produced them.

**Q1 (OAuth issuer hosting topology) — Option A confirmed**: OAuth
issuer runs as a module within the existing bridge process
(`bridge/vapi_bridge/oauth_issuer.py`) for Phase O0. Revisit at P3
when agents gain write authority — at that point separate-process or
third-party-service isolation may become load-bearing for security
posture, but in P0 (agents inactive) and P1-P2 (read-only / shadow /
suggestion) the in-process simplicity outweighs the isolation benefit.

**Q2 (KMS key for GitHub App auth: KMS-backed or imported) — Provisional
split confirmed**: Option A (KMS-generated, never exported, bridge
proxies signing requests through KMS API) for the agent's commit-signing
key (high-security — agent commits become protocol record). Option B
(KMS-generated, exported once for import to GitHub) for the GitHub App
auth key (lower sensitivity — GitHub already validates app-to-app, and
the auth key only authenticates the app to GitHub's API). Split
provisioning matches the asymmetric sensitivity of the two keys.

**Q3 (Anthropic API key per-agent management) — Defer to P1 prep**:
Phase O0 agents are inactive; they make no Anthropic API calls. Per-
agent key provisioning is therefore a P1 prep concern. The decision
between options (a) shared `ANTHROPIC_API_KEY`, (b) per-agent env-var
keys, or (c) KMS-managed keys is logged for P1 prep but not made in
Phase O0.

**Q4 (Branch protection + path-scope gate) — Enable both (defense in
depth)**: Phase O0 enables CODEOWNERS-required reviewer enforcement at
the branch protection level on `main` AND ships
`vapi_path_scope_gate.py` running on every PR. Both layers must pass
for a commit to merge. Branch protection requires CODEOWNERS approval;
path-scope gate confirms the diff respects path-scope rules. Either
layer's failure blocks merge. Defense-in-depth posture matches the
audience priority — businesses and institutions evaluating data
sovereignty expect multiple independent enforcement layers.

**Q5 (Drain-class structural fix scope) — Decline for Phase O0 scope**:
The DualShock + batcher retry-blind paths that caused the Phase 237.5
Path C+ wallet drain are mitigated by the `CHAIN_SUBMISSION_PAUSED`
kill-switch, not structurally fixed. The 5 IOTX wallet target carries
sufficient drain-margin headroom (~10× per-incident drain rate at the
~3 IOTX/hour observed rate) to survive an accidental kill-switch
lift. Structural fix is parallel work not folded into Phase O0. The
combination of kill-switch + 5 IOTX margin is sufficient for the Phase
O0 deploy window.

**Q6 (Test count verification at Phase O0 exit) — Accept test
categories as listed**: 30-50 new Hardhat tests + 12-16 new bridge
tests + 0 SDK tests. No additional E2E integration tests required for
Phase O0 exit. Final counts at Phase O0 exit: Bridge ~2529-2533,
Hardhat ~558-578, SDK 539, Contracts 51. The agent identity flow
(GitHub Apps + KMS + ioID + ERC-6551 + AgentRegistry registration) is
exercised through individual Hardhat tests for each contract; full
end-to-end agent-mint integration test is not required because the
agents remain inactive at Phase O0 exit.

**Q7 (DID document IPFS pinning provider) — Pinata confirmed**: Pinata
commercial pinning service (~$0.001 per pin) is the Phase O0 IPFS
storage provider. Operator account exists. Per-agent DID document JSON
pinned at Phase O0 deploy; pin URLs recorded for audit reproducibility.

**Q8 (modelClass field in DID metadata) — Included**: Phase O0 DID
documents include `metadata.modelClass: "claude-sonnet-4-6"` per
Section 6.1. The claim is self-asserted (Anthropic does not sign API
responses) but binding it to the DID prevents silent model-switching
without identity-trace. Self-asserted is acceptable given audience
expectations around model accountability — businesses and institutions
evaluating data sovereignty expect explicit model-class declaration as
part of the agent's identity rather than silent model substitution.
Future model migration (e.g., agent moves to Sonnet 4.7) requires DID
document update with new modelClass per Section 10 Note 12; old
attestations remain valid for the period the agent ran on the old
model.

**Q9 (Agent ID encoding canonical form) — Provisional choice
confirmed**: `agentId = keccak256(abi.encode(ioID_DID_address,
ERC6551_TBA_address))`. FROZEN at first agent registration in
AgentRegistry — once the first agent's record is written, this
encoding is the protocol's permanent agent-identity-binding shape. Any
later change would break AgentRegistry lookups across all subsequent
records. The encoding binds the DID and TBA together cryptographically;
neither component alone is sufficient as agentId.

**Q10 (Cedar bundle storage strategy) — Option B confirmed**: Cedar
bundles stored in repo (`bridge/vapi_bridge/cedar_bundles/`); bundle
Merkle root anchored on-chain via AgentScope. P1 commits the first
bundle as a normal repo commit (path-scope gate enforces lane
discipline). The repo-stored approach is simpler than IPFS-stored
(Option A) and provides version-control history through git. Tessera
log integration (Option C) deferred to P1+ when the upstream feed is
live. AgentScope's `setAgentScopeRoot` interprets the root as a hash
of the bundle's canonical bytes; the bundle's location (repo path) is
off-chain knowledge that the bridge knows.

**Q11 (Reconsidering prior-pass decisions) — None require revisiting**:
Pass 2C synthesis revealed no conflicts between the nine resolved
inputs and the implementation work specified. All resolved inputs map
cleanly to Phase O0 deliverables per Section 2. No recommendation to
revisit any prior decision.

These eleven resolutions complete the design phase. Phase O0
implementation begins as the next session, proceeding atomically per
this plan with operator review at each contract deployment, primitive
freeze, and exit-criteria checkpoint per Section 8's 24 verifiable
criteria.

---

## Section 10 — Forward Compatibility Notes

Decisions made in Phase O0 that constrain future Operator series
phases. Each note identifies a Phase O0 commitment and what later
phases must respect to honor it.

### Note 1 — AGENT_COMMIT v1 hash formula is FROZEN at Phase O0 exit

Once Phase O0 ships INV-AGENT-COMMIT-001 + INV-AGENT-COMMIT-002, the
formula `compute_agent_commit_hash(agent_id, commit_sha, prev_commit_hash,
repo_uri_sha, ts_ns)` is FROZEN. Any change requires:
- AGENT_COMMIT v2 with new domain tag `b"VAPI-AGENT-COMMIT-v2"`
- Parallel infrastructure (new module, new store table, new chain
  wrapper, new invariants)
- Migration plan for existing v1 records (preserved as historical
  artifacts; new commits go through v2)

P1+ phases must NOT modify AGENT_COMMIT v1 in any way. Adding new
fields requires v2.

### Note 2 — PHYSICAL_DATA_ATTESTATION v1 hash formula is FROZEN at Phase O0 exit

Same as Note 1, applied to PDA v1.

### Note 3 — actionType vocabulary expansion is governance-event

Phase O0's actionType vocabulary (Section 4.3) is `{"AGENT_COMMIT",
"PHYSICAL_DATA_ATTESTATION", "AUDIT_LOG_CHECKPOINT", "BOUNDARY_UPDATE"}`.
Adding a new actionType requires `--reason "ceremony_update: ..."`
governance event matching the invariant gate's --confirm-governance
discipline. Removing an actionType is harder — existing on-chain
records would become orphaned. Effectively, the vocabulary is
append-only after Phase O0.

### Note 4 — AgentAdjudicationRegistry contract is FROZEN at Phase O0 deploy

The deployed contract address becomes a protocol identity. Replacing
the contract requires migration of all anchored records — a
substantial event. Phase O0 implementation must verify the contract's
correctness before deploy (Hardhat tests passing, internal audit
clean). If issues are discovered post-deploy, the path is either
(a) deploy fix as a new contract and migrate, or (b) accept the
limitation and work around it. Neither is cheap.

### Note 5 — ioID DID is permanent agent identity

Once an agent's ioID DID is minted in Phase O0, the DID identifier
(`did:io:0x<address>`) becomes the agent's protocol identity.
Re-minting would create a new identity — all AGENT_COMMIT v1, PDA v1,
and AgentRegistry records reference the original DID. P1+ phases
must NOT re-mint agent DIDs without explicit migration planning.

### Note 6 — KMS key rotation requires DID document update

If the agent's KMS key is rotated, the DID document
`verificationMethod.publicKeyHex` becomes stale. The DID specification
allows multiple verification methods (key rotation via adding new key
+ deprecating old key in a single DID document update); Phase O0's
DID document JSON-LD structure (Section 6.1) supports this. P1+ key
rotation procedures must use this pattern, not re-mint DID.

### Note 7 — Path-scope gate enforcement is from Phase O0 onward

Once `.github/CODEOWNERS` lands and `vapi_path_scope_gate.py`
workflow runs, every commit by `vapi-anchor-sentry[bot]` or
`vapi-guardian[bot]` is enforced. P0 has no agent commits yet; P2+
will. The CODEOWNERS rules are the source of truth — adding a new
agent or new lane requires CODEOWNERS update + path-scope gate
re-validation.

### Note 8 — OAuth scope hierarchy is established but expandable

Phase O0 ships scopes `bridge:agent:phases:read` (and the broader
read scope set). P1+ adds:
- `bridge:agent:agent-commit:write` (P2 — agents drafting PRs)
- `bridge:agent:contract:invoke:adjudication` (P3 — agents writing
  on-chain anchors)
- `bridge:agent:invariant:propose` (P4 — agents proposing invariant
  changes)

The scope hierarchy is hierarchical — `bridge:agent:*` matches all
agent scopes. P1+ phases must add new scopes as needed but should
not collapse the hierarchy.

### Note 9 — AuditLog contract supports Tessera but doesn't require it

Phase O0 deploys AuditLog with empty checkpoints. Tessera upstream
feed is deferred to P1+. The AuditLog contract has anti-replay
constraints (unique merkleRoot, monotonic treeSize, ±3600s
timestamp) that the Tessera feed must respect when first activated.
P1+ Tessera integration can use any signed-tree-head implementation
that produces (root, size, ts) tuples meeting these constraints.

### Note 10 — Phase O0 contracts use bridge wallet as initial owner

All five contracts deploy with `initialOwner = bridge wallet`. P3+
ownership transition to a multi-sig or governance contract is
forward work. Phase O0 does NOT include ownership renunciation or
multi-sig migration — that's a separate phase concern.

### Note 11 — Lane reorg is irreversible at the engine level

Once `vapi_wiki_engine.py:108` becomes `SWEEPS_DIR = REPO_ROOT /
"sweeps"`, reverting to `WIKI / "sweeps"` is a code change. New
sweeps will land in the new path; historical sweeps are at the new
path post-migration. P1+ phases should not reverse the reorg.

### Note 12 — DID metadata `modelClass` field, if included, is part of
identity claim

If Phase O0 includes `modelClass: "claude-sonnet-4-6"` in DID metadata
(per Question 8), this becomes part of the agent's identity claim
on-chain. Future model migration (e.g., agent moves to Sonnet 4.7)
requires DID document update with new modelClass, and the old DID
attestations remain valid for the period when the agent ran on the
old model. Auditors checking attestation validity must consider model
class at attestation time, not current model class.

---

## Section 11 — Section 6.3 Amendment (2026-05-01) — Architectural Revision

This section amends Section 6.3 of the original Pass 2C design phase
specification based on V1-V7 verification findings completed
2026-05-01. The amendment ships through Verification-First Discipline
(canonicalized in commit `94bed715`): pre-implementation verification
with operator approval at the verification checkpoint, implementation
against approved scope, post-implementation verification, operator
approval before commit, atomic commit with architectural reasoning
preserved, push to origin/main.

### 11.1 — Verification trail

V1-V7 verification (Pattern C hybrid amendment session, 2026-05-01)
surfaced the following empirical findings:

- **V1 — DID template P-256 dependency: NONE.**
  `agents/did_templates/vapi-anchor-sentry.did.template.json` and
  `vapi-guardian.did.template.json` declare verification methods using
  only `EcdsaSecp256k1VerificationKey2019`. Zero P-256, Ed25519, or RSA
  cryptographic verification methods. The DID templates are
  secp256k1-pure.

- **V2 — GitHub App PEM key type: RSA-2048, NOT P-256.**
  Both `bridge/secrets/vapi-anchor-sentry.pem` and
  `bridge/secrets/vapi-guardian.pem` are RSA-2048 (PKCS#1 BEGIN/END
  RSA PRIVATE KEY headers; openssl confirms 2048-bit, 2 primes).
  GitHub issued these PEMs by default during Section 6.2 App
  registration; no operator action overrode the default. **The
  Pass 2C Section 6.3 step 1 specification of `KeySpec=ECC_NIST_P256`
  was made architecturally WITHOUT verifying what Section 6.2 had
  already issued.**

- **V3 — Bridge GitHub library imports: NONE.**
  Phase O0 GitHub App authentication code is not yet written; agents
  are DORMANT, no GitHub API calls happen from the bridge runtime.
  Library choice for P1+ implementation remains open.

- **V4 — Pass 2C Section 6.3 step 1 wording: architectural choice,
  not GitHub requirement.** Section 6.3 step 5 says "PEM-encoded
  private key" — RSA-2048 satisfies this requirement. The
  `ECC_NIST_P256` specification in step 1 has no documented
  justification beyond the architecture document's general AWS KMS
  preference (which is provider-level, not curve-level).

V5-V7 re-confirmed V1-V2 evidence and verified amendment-session
prerequisites: clean canonical state at `d019c067`, no PV-CI gate
impact (Pass 2C is not in `.github/INVARIANTS_ALLOWLIST.json`), no
governance_provenance_chain entry required (this is documentation
revision of a design proposal, not an `invariant_change` category
governance event).

### 11.2 — Architectural revision summary

| Dimension | Original Pass 2C (2026-04-27) | Amended (2026-05-01) |
|-----------|-------------------------------|----------------------|
| KMS keys | 4 (2 commit-signing + 2 GitHub App auth) | **2** (2 commit-signing only) |
| KMS providers | 2 (commit-signing + GitHub App auth providers) | **1** (Lit Protocol) |
| Curve for commit-signing | NIST P-256 (`ECC_NIST_P256`) | **secp256k1** (matches DID template + IoTeX EVM) |
| GitHub App auth key handling | Option B export ceremony from KMS to GitHub | **Retain GitHub-issued RSA-2048 PEMs in `bridge/secrets/`** |
| Provider for commit-signing | AWS KMS | **Lit Protocol PKPs (Naga V1 mainnet)** |
| First-of-its-kind precedent risk | Yes (Web3 KMS → GitHub App JWT) | **None** (RSA-2048 PEMs use GitHub's standard auth) |

### 11.3 — Amendment Section 1 — Backup/DR posture for simplified architecture

**Lit Protocol PKP recovery**: PKPs are non-exportable by design (MPC
TSS network never assembles the full key in any single location). Loss
of the bridge wallet's NFT-control over a PKP requires DID rotation
per Section 10 Note 6 — provision new PKP, mint replacement DID with
new public key, register replacement in AgentRegistry. The TBA
persists; only the signing capability rotates. Lit Naga V1's MPC TSS
network distribution across the operator-set selected by the
December 2025 Stake Weight Contest provides resilience without
operator-side multi-region replica.

**GitHub App PEM rotation**: Standard GitHub App key rotation
procedure applies — generate new key in App settings UI, replace
`bridge/secrets/<agent>.pem`, restart bridge. No KMS dependency. The
RSA-2048 PEM lifecycle remains operator-managed per VAPI's existing
trust model (the bridge wallet IoTeX private key in `bridge/.env` has
the same risk profile and is operationally accepted; GitHub App PEM
KMS-isolation would be inconsistent with the bridge wallet's current
on-disk storage).

### 11.4 — Amendment Section 2 — Q3 (Anthropic API key plane) status update

**Resolution unchanged from 2026-04-27**: Option (b) per-agent env-var
keys (`ANTHROPIC_API_KEY_SENTRY`, `ANTHROPIC_API_KEY_GUARDIAN`) is
the resolved decision, with implementation deferred to P1 prep.
Reasoning: Anthropic API keys are bearer tokens, not signing keys;
KMS adds no cryptographic value (KMS protects against key extraction;
bearer tokens transit in cleartext over TLS). Per-agent isolation
matters operationally for billing and rate-limit blast radius. The
amendment logs this Option (b) confirmation explicitly so future
operators reading the audit trail see the path was decided rather
than left ambiguous.

### 11.5 — Amendment Section 3 — Verification Gap Acknowledgment

**Pattern**: Pass 2C Section 6.3 step 1 specified `ECC_NIST_P256`
architecturally without empirically verifying that Section 6.2 had
already issued RSA-2048 PEMs. The verification gap propagated through
downstream architectural reasoning (the operator's empirical KMS
provider survey researched provider P-256 support extensively, and
the in-session "path c" recommendation inherited the P-256 commitment)
before being caught by V2 in the pre-amendment verification checkpoint.

**Discipline pattern observation**: The 5-minute V-check sequence
(V1-V7) caught the gap at the verification step, by design.
Verification-First Discipline (canonical name from commit `94bed715`)
operates through pre-implementation verification before architectural
commitments compound. The amendment preserves this pattern in the
protocol's permanent record: future operators reading the audit trail
will see how an unverified design phase commitment was caught before
implementation, what evidence verification produced, and how the
architectural revision flowed from empirical findings rather than from
re-debate of the original architectural reasoning.

**Cost of the verification gap had it propagated unchecked**: ~3-4
hours additional implementation, one additional KMS provider
integration (Turnkey or AWS KMS for P-256), one additional bridge
module (`turnkey_client.py` or `aws_kms_client.py`), six additional
bridge tests, and a first-of-its-kind precedent risk (no production
deployment of decentralized KMS signing GitHub App JWTs exists). The
verification checkpoint eliminated all of these costs.

### 11.6 — Amendment Section 4 — Operator decisions (2026-05-01)

The operator confirmed the Section 6.3 amendment 2026-05-01. The
2026-04-27 operator decisions block at line 1441 is preserved
verbatim as historical record; this 2026-05-01 block documents what
changed and why, by sibling reference rather than overwriting the
prior decisions.

**Q2 revision (KMS key for GitHub App auth: KMS-backed or imported)**:

- 2026-04-27 confirmation: Option A for commit-signing (KMS-generated,
  never exported), Option B for GitHub App auth (KMS-generated,
  exported once for import to GitHub). Provisional split confirmed.
- 2026-05-01 amendment: Option A confirmed and migrated from AWS KMS
  to Lit Protocol PKP (secp256k1 commit-signing). **Option B
  eliminated entirely** — V2 finding showed Section 6.2 already
  issued RSA-2048 PEMs satisfying GitHub App PEM-format requirement;
  the Option B ceremony Pass 2C originally specified was solving a
  problem already resolved by Section 6.2's GitHub App registration
  default behavior.

**Q-curve (NEW; 2026-05-01)**: KMS curve selection for commit-signing
keys. **secp256k1 confirmed** matching the DID template's
`EcdsaSecp256k1VerificationKey2019` declaration and IoTeX EVM
secp256k1 native compatibility. The original `ECC_NIST_P256`
specification was an architectural drift from the DID template that
V1 verification surfaced.

**Q-provider (NEW; 2026-05-01)**: KMS provider for commit-signing
keys. **Lit Protocol confirmed** based on the operator's Lit Protocol
empirical research and the architectural fit (DePIN thesis
preservation at the highest-leverage point — agent commits become
protocol truth claims; Lit's MPC TSS network with on-chain access
control conditions composes natively with VAPI's existing IoTeX
governance contracts; PKP NFTs holdable by ERC-6551 TBAs make agent
signing capability literally an asset under on-chain governance).

### 11.7 — Phase O0 Section 8 exit criterion #14 update

Original Section 8 exit criterion #14: "KMS keys provisioned for both
agents | KMS key aliases exist; signing capability tested via test
signature."

**Amended (2026-05-01)**: "Lit Protocol PKPs minted for both agents |
PKP tokenIds exist on Lit Chronicle L3; signing capability tested via
test signature against secp256k1 PKP. GitHub App auth keys remain the
GitHub-issued RSA-2048 PEMs at `bridge/secrets/<agent>.pem`."

The verification method for criterion #14 changes from
`aws kms list-keys` + `aws kms sign` to a Lit Protocol PKP query +
Lit `executeJs` test signature.

### 11.8 — Implementation effort revision

| Metric | Original Pass 2C (path c v2 with Lit + Turnkey) | Amended (Lit only) |
|--------|--------------------------------------------------|--------------------|
| Implementation effort | ~9-11 hr | **~6-7 hr** |
| Bridge modules | 2 (`lit_client.py` + `turnkey_client.py`) | **1** (`lit_client.py`) |
| Bridge tests added | +12 | **+6** |
| KMS keys | 4 | **2** |
| Providers | 2 | **1** |

The amendment reduces Phase O0 Section 6.3 implementation cost by
roughly one-third while strengthening the DePIN thesis alignment
(single decentralized KMS provider for the load-bearing commit-signing
key) and eliminating the first-of-its-kind precedent risk that the
original 4-key architecture would have incurred.

---

This Section 11 amendment is the canonical reference for Section 6.3
implementation work. Section 6.3's original text remains in this
document for historical record (in-line edits at items 1-4 carry
"AMENDED 2026-05-01 — see Section 11" callouts pointing here); the
2026-04-27 operator decisions block at line 1441 remains untouched
as historical record of the original design phase confirmation.

**[NOTE 2026-05-02]: Section 11 is itself superseded by Section 12
(2026-05-02 amendment) which reverts the Lit Protocol provider
substitution to AWS KMS following Q1-Q5 expanded investigation that
revealed Lit Protocol Naga V1 had been sunset April 1, 2026 (~1 month
before the 2026-05-01 amendment landed) and that Lit Protocol provides
no formal stability commitments to production users. Section 11
content is preserved verbatim as historical record per the discipline
pattern; readers should consult Section 12 for the current canonical
KMS architecture (AWS KMS, secp256k1 curve preserved, RSA-2048 PEM
GitHub App auth lifecycle preserved).**

---

## Section 12 — Section 6.3 Second Amendment (2026-05-02) — Provider Revision Reversal

This section is the second amendment to Section 6.3 of the original
Pass 2C design phase specification. It supersedes the 2026-05-01
amendment in Section 11 specifically on the KMS provider choice (Lit
Protocol → AWS KMS reversal) while preserving the curve correction
(`ECC_SECG_P256K1`) and GitHub App auth lifecycle fix (RSA-2048 PEMs
retained) that emerged from V1-V7 verification in the 2026-05-01
amendment. The amendment ships through Verification-First Discipline
(canonicalized in commit `94bed715`): pre-implementation verification
(V1-V7) with operator approval at the verification checkpoint,
implementation against approved scope, post-implementation
verification, operator approval before commit, atomic commit with
architectural reasoning preserved, push to origin/main.

### 12.1 — Verification trail (Q1-Q5 expanded investigation findings)

The 2026-05-01 amendment specified Lit Protocol Naga V1 mainnet as
the KMS provider. Section 6.3 prerequisite investigation initiated
2026-05-02 surfaced that Naga V1 had been sunset on April 1, 2026 —
approximately one month before the 2026-05-01 amendment landed.
Expanded Q1-Q5 investigation produced the following empirical
findings:

- **Q1 — Chipotle V3 longevity**: No public stability commitment.
  No V4/V5 mentions but also no "Chipotle is final architecture"
  statement. Lit Protocol's version timeline (Datil V0 ~2 years,
  Naga V1 ~3.5 months production lifespan, V2 skipped, Chipotle V3
  launched March 25, 2026) signals architectural iteration is the
  norm, not the exception.

- **Q2 — PKP migration across Lit network versions**: Confirmed PKPs
  do NOT migrate across Lit network versions. Lit's official Datil
  sunset documentation states explicitly: "PKPs will not be migrated
  from Datil to Naga, meaning you'll need to mint new PKPs on the
  Naga network." Each Lit network transition forces re-minting + DID
  rotation + AgentRegistry re-registration.

- **Q3 — Lit Protocol stability commitments**: NONE FORMAL. No SLA,
  no LTS, no deprecation policy, no breaking-change communication
  protocol. Governance via Lit Association (Swiss non-profit
  multisig) with Lit Improvement Proposals (LIPs) process.
  Production users have no contractual recourse for breaking changes.

- **Q4 — Decentralized KMS alternative comparison**: No decentralized
  KMS is BOTH more stable than Lit AND VAPI-compatible. Ika
  (dWallet) is more stable (~2 years, only feature additions) but
  Sui-native and not VAPI-compatible. Self-hosted FROST is
  research-grade with curve mismatch (Schnorr-only). The viable
  production-stable options are all centralized (AWS KMS 12 years,
  GCP KMS 9 years, Azure Key Vault 10 years, Turnkey 3 years) or
  self-hosted (HashiCorp Vault 10 years).

- **Q5 — AWS KMS reassessment under Q1-Q3 findings**: AWS KMS's
  12-year production track record + formal SLA + minimal API churn
  (zero major architecture transitions in 12 years) outweigh DePIN
  thesis preservation at the operator-agent layer for VAPI's
  specific use case. The DePIN thesis preservation at VAPI's protocol
  trust root (DualShock Edge ECDSA-P256 hardware-anchored PoAC
  chain) remains unaffected by KMS provider choice for the
  operator-agent layer.

### 12.2 — Architectural reassessment summary

| Dimension | Original Pass 2C (2026-04-27) | 1st Amendment (2026-05-01) | 2nd Amendment (2026-05-02) |
|-----------|-------------------------------|----------------------------|----------------------------|
| KMS provider | AWS KMS (provisional) | Lit Protocol PKPs (Naga V1 mainnet) | **AWS KMS in `us-east-1`** (revert) |
| KMS keys | 4 (2 commit-signing + 2 GitHub App auth) | 2 (commit-signing only) | **2 (commit-signing only)** (preserved) |
| Curve | NIST P-256 (`ECC_NIST_P256`) | secp256k1 (Lit-specific) | **secp256k1 (`ECC_SECG_P256K1`)** (preserved) |
| GitHub App auth | KMS-managed Option B export ceremony | RSA-2048 PEMs retained from Section 6.2 | **RSA-2048 PEMs retained** (preserved) |
| Backup/DR posture | Not explicitly addressed | Lit MPC TSS resilience + DID rotation | **Single-region (us-east-1) + DID rotation per Section 10 Note 6** |
| IAM credentials delivery | Not explicitly addressed | N/A (Lit auth model) | **Long-lived AWS IAM creds in bridge/.env (mode 600 gitignored); kms:Sign minimum-privilege scoping is the DESIGN TARGET — as-deployed scope verified privately, see D3 reconciliation note** |
| Architectural risk | Verification gaps in P-256 + GitHub App auth assumptions | Naga V1 sunset risk (unverified at amendment time) | **Stable production infrastructure (12-year AWS KMS API stability)** |
| First-of-its-kind precedent risk | Yes (Web3 KMS → GitHub App JWT) | None (RSA-2048 standard auth) | **None preserved** |
| DePIN thesis at operator-agent layer | Compromised (AWS centralization) | Preserved (Lit decentralization) | **Compromised, but bounded — protocol trust root remains hardware-anchored** |

### 12.3 — Provider revision reversal: Lit Protocol → AWS KMS

The 2026-05-01 amendment substituted AWS KMS with Lit Protocol on
DePIN-thesis-preservation grounds at "the highest-leverage point —
agent commits become protocol truth claims." Q1-Q5 findings
demonstrate this framing was incomplete:

1. **No Lit Protocol stability commitments to production users**
   means VAPI's Operator agents would inherit Lit's iteration
   velocity as recurring operational maintenance work (estimated
   ~3-4hr per Lit network transition × ~3-4 transitions per year at
   Lit's observed velocity = ~10-15 hr/year ongoing maintenance
   beyond initial implementation).

2. **PKP non-portability across Lit network versions** means each
   Lit transition forces DID rotation, breaking the "single signing
   key per agent identity" simplicity that long-lived agent identity
   for permanent on-chain attestation requires.

3. **Lit Protocol iteration velocity uniquely high** means the
   provider that the original survey called "production-ready" is
   in active architectural transition. The empirical pattern (Naga
   V1 production lifespan ~3.5 months) does not support assuming
   Chipotle's lifespan will be different.

4. **AWS KMS 12-year API stability with formal SLA** provides the
   operational stability that long-lived agent identity requires.
   AWS KMS's deprecation cadence (multi-year notice for SDK v1 EOL)
   matches VAPI's multi-year phase progression timescales.

5. **VAPI operator agents are outer governance layer, not protocol
   trust root**. The PoAC chain hardware-anchored to DualShock Edge
   ECDSA-P256 is the trust root and remains unaffected by KMS
   provider choice. Compromising DePIN thesis at the operator-agent
   layer (centralized AWS KMS) does NOT compromise VAPI's core
   DePIN claims for the protocol itself. The "first decentralized
   KMS for agent commit signing" framing was a marketing
   consideration, not an architectural one.

### 12.4 — Backup/DR posture (D2 from 2026-05-02 operator decisions)

Single-region AWS KMS deployment in `us-east-1`. Recovery from AWS
account loss via DID rotation per Pass 2C Section 10 Note 6 —
provision new KMS keys in a new account, mint replacement DID with
new public keys (derived from new KMS keys), register replacement
in AgentRegistry. The TBA persists; only the signing capability
rotates.

**Multi-region replica considered and rejected**: AWS KMS supports
multi-region replicas natively (replicate keys across us-east-1 +
us-west-2 with key material remaining non-exportable in each region).
This addresses regional outage but does NOT address the realistic
failure mode (AWS account loss). The cost ($4/month vs $2/month) adds
complexity without addressing the actual risk. Consistent with VAPI's
existing trust model where bridge wallet IoTeX private key has the
same single-point-of-failure profile on a single host.

### 12.5 — Architectural drift acknowledgment as discipline pattern record

The 2026-05-01 amendment was based on the original Lit Protocol
research synthesis which treated Lit Protocol's stability as
established fact rather than verifiable claim. The Q1-Q5 expanded
investigation revealed external service state had changed (Naga V1
sunset, Chipotle V3 launch) since the research was conducted in
April 2026.

**Discipline pattern lesson preserved**: External service state
warrants verification when architectural decisions depend on that
state, particularly for services with limited stability commitments
(no SLA, no LTS, no formal deprecation policy). Future amendments
to design phase documents that target external services should
include external state verification as part of pre-amendment
V-checks. Specific pattern: when a design phase document references
an external service version or network (e.g., "Lit Protocol Naga V1
mainnet"), pre-amendment verification should re-confirm that the
referenced version/network is still the live production target at
amendment time.

This is the same Verification-First Discipline pattern that caught
the RSA-2048 finding in 2026-05-01 V2 verification, applied at
external service state level rather than internal repository state
level. The cost of NOT catching the Naga sunset finding before
implementation: ~6-7 hr of Section 6.3 implementation work targeting
a sunset network, with implementation failing at first SDK call when
Naga endpoints returned 404. The Q1-Q5 investigation cost ~1 hr and
saved that.

The cumulative discipline pattern across the 2026-05-01 and
2026-05-02 amendments: three Verification-First Discipline findings
in this design pass arc — (1) PS5 stick-attachment recurrence under
PS5_COMPAT_MODE=true (operator field observation, separate
diagnostic thread), (2) RSA-2048 PEMs already in place (Pass 2C
Section 6.3 P-256 spec was unverified — caught by V2 in pre-amendment
verification, 2026-05-01), (3) Naga V1 sunset (Pass 2C amendment
Section 11 content unverified against current Lit Protocol state —
caught by Q1-Q5 in prerequisite investigation, 2026-05-02). Each
finding was caught at a verification step before architectural
commitment compounded into wasted implementation work.

### 12.6 — 2026-05-02 operator decisions block (sibling to 2026-04-27 and 2026-05-01)

The operator confirmed the Section 6.3 second amendment 2026-05-02.
Original 2026-04-27 operator decisions block (line 1441) and
2026-05-01 operator decisions block (Section 11.6) preserved
verbatim as historical record. This 2026-05-02 block documents what
changed and why, by sibling reference rather than overwriting prior
decisions.

**Q2 final resolution (KMS key for GitHub App auth: KMS-backed or
imported)**:
- 2026-04-27: Provisional split (Option A for commit-signing,
  Option B for GitHub App auth) confirmed.
- 2026-05-01: Option A confirmed and migrated from AWS KMS to Lit
  Protocol PKP. Option B eliminated entirely (V2 finding:
  GitHub-issued RSA-2048 PEMs satisfy GitHub App auth without KMS).
- 2026-05-02: Option A reaffirmed; provider reverted from Lit
  Protocol to AWS KMS in us-east-1 with `KeySpec=ECC_SECG_P256K1`
  (the curve correction from 2026-05-01 preserved). Option B
  remains eliminated (RSA-2048 PEM retention from 2026-05-01
  preserved).

**D1 (AWS region)**: us-east-1. Default ecosystem; latency immaterial
to bridge agent operation; broadest tooling/docs.

**D2 (Backup/DR posture)**: Single-region (us-east-1) + DID rotation
recovery per Pass 2C Section 10 Note 6. Multi-region replica
considered and rejected (does not address AWS account loss failure
mode).

**D3 (IAM credentials delivery)**: Long-lived AWS IAM user access
keys delivered as env vars in `bridge/.env` (gitignored, mode
600 directory). Bridge IAM user has `kms:Sign` minimum-privilege
scoping on the 2 specific KMS keys only; operator IAM user retains
administrative actions.

> **[Reconciliation 2026-06-13 — design target vs as-deployed]** The
> `kms:Sign` minimum-privilege scoping described above is the **required
> design target**, NOT a verified as-deployed claim. As-deployed IAM-scope
> verification status and any remediation gap are tracked in
> `docs/disaster-recovery-runbook.private.md` (gitignored, operator-local).
> Until that private verification confirms the scope-down has been applied,
> treat bridge IAM minimum-privilege as a design target, not an implemented
> control. (This note resolves the design-vs-reality discrepancy flagged in
> the F-EXT sweep without restating the private finding.)

**D4 (KMS-vs-import constraint block treatment)**: Preserve MOOT
callout. Update reasoning from Lit-specific "non-exportable by MPC
TSS architecture" to AWS KMS Option (a) reasoning: commit-signing
keys KMS-generated, signed via `kms:Sign` API, key material never
leaves AWS KMS HSM. No export ceremony needed because GitHub App
auth keys are out of KMS scope.

**Curve correction (`ECC_SECG_P256K1`)**: Reaffirmed from 2026-05-01
amendment. Matches DID template's `EcdsaSecp256k1VerificationKey2019`
declaration + IoTeX EVM secp256k1 native compatibility.

**GitHub App auth lifecycle (RSA-2048 PEMs retained in
`bridge/secrets/`)**: Reaffirmed from 2026-05-01 amendment. No KMS
migration. No Option B export ceremony.

**Anthropic API key plane (Q3) Option (b) per-agent env-var keys**:
Reaffirmed from 2026-05-01 amendment. Implementation deferred to P1
prep.

### 12.7 — Phase O0 Section 8 exit criterion #14 update

Original Section 8 exit criterion #14: "KMS keys provisioned for
both agents | KMS key aliases exist; signing capability tested via
test signature."

2026-05-01 amendment specified: "Lit Protocol PKPs minted for both
agents | PKP tokenIds exist on Lit Chronicle L3; signing capability
tested via test signature against secp256k1 PKP."

**2026-05-02 amendment (supersedes 2026-05-01)**: "AWS KMS keys
provisioned for both agents in us-east-1 | KMS key aliases
`alias/vapi-anchor-sentry-signing` and `alias/vapi-guardian-signing`
exist; signing capability tested via `aws kms sign --key-id
alias/vapi-anchor-sentry-signing --message <test-payload>
--message-type RAW --signing-algorithm ECDSA_SHA_256` returning a
valid secp256k1 ECDSA signature."

The verification method for criterion #14 reverts from Lit Protocol
PKP query + Lit `executeJs` test signature to standard AWS CLI
`aws kms sign` test signature.

### 12.8 — Implementation effort revision

| Metric | Original Pass 2C | 1st Amendment (Lit) | 2nd Amendment (AWS KMS) |
|--------|------------------|---------------------|--------------------------|
| Implementation effort | ~9-11 hr (with Lit + Turnkey) | ~6-7 hr (Lit only) | **~5-6 hr** (AWS KMS only) |
| Bridge modules | 2 (`lit_client.py` + `turnkey_client.py`) | 1 (`lit_client.py`) | **1 (`kms_client.py` boto3 wrapper)** |
| Bridge tests added | +12 | +6 | **+6** (same count, simpler implementation) |
| KMS keys | 4 | 2 | **2** (preserved) |
| Providers | 2 | 1 (Lit) | **1 (AWS)** |
| External dependencies | Lit JS SDK + Node.js v19.9+ | Lit Python SDK Node.js bridge wrapper | **boto3 native Python (no Node.js)** |
| Maintenance overhead | TBD | ~10-15 hr/year (Lit network transitions) | **Negligible (AWS KMS rarely requires migration)** |

The 2026-05-02 amendment reduces Phase O0 Section 6.3 implementation
cost relative to the 2026-05-01 amendment (~5-6 hr vs ~6-7 hr) due
to mature boto3 SDK and well-documented patterns versus Lit Protocol
Python SDK Node.js bridge complexity. More significantly, the
2nd amendment eliminates the ~10-15 hr/year ongoing maintenance
overhead that would have accumulated under the 1st amendment from
Lit network transitions.

---

This Section 12 second amendment is the canonical reference for
Section 6.3 implementation work. Section 6.3's original text remains
in this document for historical record (in-line edits at lines 1095,
1110, 1138 carry "AMENDED 2026-05-02 — see Section 12" callouts
pointing here, layered on top of the 2026-05-01 callouts which
themselves remain as historical record); the 2026-04-27 operator
decisions block at line 1441 and the 2026-05-01 operator decisions
block in Section 11.6 both remain untouched as historical record of
the design phase confirmation and first-amendment confirmation
respectively. The discipline pattern preserves both Section 11 and
Section 12 as siblings, with Section 12 superseding Section 11 on
the specific provider choice while preserving Section 11's curve
correction and GitHub App auth lifecycle fixes.

---

## Section 13 — Section 6.4 Corrections — Third Amendment (2026-05-02) — On-Chain Registration Architectural Drift

This section is the third amendment to the Pass 2C design phase
specification. Unlike Sections 11 and 12 (which both edit Section 6.3),
this amendment's in-line edits land in **Section 6.1** because that is
where the affected specifications (ioIDRegistry.register signature,
ERC-6551 binding salt, NFT contract address, mint sequence ordering)
were originally written. The amendment retains the "Section 6.4" label
to reflect the implementation lifecycle stage (operator agent on-chain
registration in AgentRegistry) that surfaced the findings — matching
the single-label precedent established by Sections 11 and 12 (which
carry "Section 6.3 Amendment" labels even when their operator decisions
blocks at Sections 11.6 and 12.6 sit in different layout positions
from the Section 6.3 text they amend).

The amendment ships through Verification-First Discipline (canonicalized
in commit `94bed715`): pre-implementation read-only investigation against
deployed IoTeX testnet contracts cross-referenced against canonical source,
operator approval at the verification checkpoint, atomic amendment commit
with architectural reasoning preserved, push to origin/main. The
implementation session that follows this amendment commit will produce
corrected `agent_registration.py` referencing this Section 13 as canonical
specification.

### 13.1 — Investigation methodology

The investigation session that preceded this amendment performed
read-only RPC introspection against deployed IoTeX testnet contracts
(`https://babel-api.testnet.iotex.io`) cross-referenced against the
canonical ioID-contracts source at
`github.com/iotexproject/ioID-contracts` at commit
`b94ad092b84f83fba068ed83bc28b72dd6f2cc4f` (2025-02-12, message:
"feat: add multicall for verifying proxy"). Five prerequisite checks
P1-P5 covered ABI verification (P1), project NFT prerequisite (P2),
agent NFT semantics (P3), wallet balance (P4), and post-execution
verification path (P5).

The investigation cost approximately 30 minutes of read-only work.
The saved cost was the on-chain registration session that would have
failed at first contract call against deployed ioIDRegistry, wasting
gas and producing no useful state. The investigation surfaced five
blocking issues prevented from reaching irreversible on-chain
commitment by the H1a "test-first, defer on-chain to operator
session" decision (commit `dcaf5015`).

The in-line corrections produced by this amendment land in Section 6.1
(lines 1007 onward) because that is where the affected specifications
were originally written. The amendment retains the "Section 6.4"
label to reflect the lifecycle stage of the implementation that
surfaced the findings (operator agent on-chain registration), matching
the single-label precedent established by Sections 11 and 12 per K2
operator decision.

### 13.2 — ABI mismatch findings

Two contracts had inline ABIs in `bridge/vapi_bridge/agent_registration.py`
at commit `dcaf5015` that did not match deployed bytecode:

**ioIDRegistry at `0x0A7e595C7889dF3652A19aF52C18377bF17e027D`**
(proxy implementation `0x66152a6be42600903b87b6292016496b6dbabf53`):

```solidity
// dcaf5015 inline ABI (WRONG — selector NOT in deployed bytecode):
function register(uint256 projectId, address deviceAddress)
    external returns (address didAddress);
    // selector 0xdbbdf083 — not in dispatch table

// Actual deployed signature (verified empirically — selector
// 0x39a4a241 found in deployed bytecode dispatch table):
function register(
    address deviceContract,    // The IProject NFT contract address
    uint256 tokenId,           // The project's NFT tokenId
    address device,            // The agent's ETH address (KMS-derived)
    bytes32 hash,              // Content hash of the DID document
    string calldata uri,       // IPFS URI for the DID document
    uint8 v, bytes32 r, bytes32 s   // EIP-712 signature by `device`
) external;
    // selector 0x39a4a241
```

Canonical source: `github.com/iotexproject/ioID-contracts` at commit
`b94ad092` path `contracts/ioIDRegistry.sol`.

**ProjectRegistry at `0x060581AA1A4e0cC92FBd74d251913238De2F13cd`**
(proxy implementation `0x16c250eb91b475447f1048d8f454ba6ae0e51287`):

```solidity
// dcaf5015 inline ABI (EMPTY PLACEHOLDER):
PROJECT_REGISTRY_ABI: list = []

// Actual functions found in deployed bytecode dispatch table:
function register(string memory name, uint8 projectType) external;
    // selector 0x767b79ed (canonical)
function register(string memory name) external;
    // selector 0xf2c298be (overload variant)
function register() external;
    // selector 0x1aa3a008 (deprecated)
function project() external view returns (address);
    // selector 0xf60ca60d (returns IProject NFT contract address)
function initialize(address) external;
    // selector 0xc4d66de8 (initializer)
```

Canonical source: `github.com/iotexproject/ioID-contracts` at commit
`b94ad092` path `contracts/ProjectRegistry.sol`.

**ERC-6551 Registry at `0x000000006551c19487814612e58FE06813775758`**
(canonical singleton per EIP-6551): inline ABI matches deployed
bytecode (selectors `0x246a0021` for `account` view + `0x8a54c52f`
for `createAccount` confirmed in dispatch table). No correction
required.

**AgentRegistry at `0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4`**
(Stream 2-deploy): ABI loaded from Hardhat artifact at
`contracts/artifacts/contracts/AgentRegistry.sol/AgentRegistry.json`;
signatures verified via direct introspection. No correction required.

(IoTeXScan verified-source links for ioIDRegistry and ProjectRegistry
deferred to amendment implementation session — V4 verification
during the pre-amendment checkpoint encountered IoTeXScan SPA loading
state, inconclusive. Implementation session uses IoTeXScan API
directly or waits for full SPA render to add verified-source callouts
where available.)

### 13.3 — Missing EIP-712 signature flow

The corrected ioIDRegistry.register signature requires EIP-712
signature components `(uint8 v, bytes32 r, bytes32 s)` signed by
the device (the agent's KMS-derived ETH address). The original
Section 6.1 specification did not include EIP-712 signature flow.
The amendment implementation session must add the following
components to `bridge/vapi_bridge/agent_registration.py`:

**EIP-712 domain construction**:

```python
domain = {
    "name": "ioIDRegistry",     # empirically verified during amendment
                                # implementation against DOMAIN_SEPARATOR()
                                # view call return value
    "version": "1",             # empirically verified
    "chainId": 4690,            # IoTeX testnet
    "verifyingContract": "0x0A7e595C7889dF3652A19aF52C18377bF17e027D",
}
```

**Digest computation**: matches ioIDRegistry's expected hash format
(typed data structure for the `Register` message containing
`device`, `hash`, and `uri` fields per ioID-contracts source at
commit `b94ad092`). The exact `EIP712Domain` + `Register` typed
data structures are empirically verified during amendment
implementation session against `DOMAIN_SEPARATOR()` view call and
canonical source cross-reference.

[NOTE 2026-05-02 fourth amendment: original specification was
empirically wrong; corrected per Section 14.3. Canonical signing
is permit-style (`Permit(address owner, uint256 nonce)` type hash;
signed data is `(user, nonce(device))`; recovered signer must
equal device) — NOT data-attestation over `(device, hash, uri)`
as this section originally implied. The `(hash, uri)` content is
NOT cryptographically bound to the signature; replay protection
comes from per-device nonce auto-incremented inside
`_useNonce(device)`. EIP-712 domain parameters confirmed empirically:
computed DOMAIN_SEPARATOR matches on-chain value byte-for-byte.]

**KMS signing invocation**: `kms_client.sign(agent, digest)` — the
existing async method at `bridge/vapi_bridge/kms_client.py` (commit
`d3b30d58`) returns DER-encoded ECDSA signature. The signing
identifier is the agent's KMS alias (`alias/vapi-anchor-sentry-signing`
or `alias/vapi-guardian-signing` per Section 12 operator decisions).

**DER-to-(v, r, s) parsing**: the `eth_account` or `eth_keys` libraries
provide DER-to-(v, r, s) helpers. The `v` value is computed as the
recovery ID (0 or 1) by attempting recovery against the known device
public key; libraries like `eth_keys.KeyAPI.ecdsa_to_signature` handle
this. Output: `uint8 v, bytes32 r, bytes32 s` ready for the
ioIDRegistry.register call.

The `kms_client.get_public_key` method already produces the agent's
ETH address via the `derive_eth_address_from_kms_public_key` helper
at `bridge/vapi_bridge/agent_registration.py` (per `dcaf5015` G2
operator decision — dual-purpose helper for both ETH address and
DID document `publicKeyHex` derivation). The same KMS key signs via
`kms_client.sign`, producing the EIP-712 signature components.
This composes natively with existing infrastructure; no new KMS
key material is required.

### 13.4 — Project NFT prerequisite + canonical NFT address clarification

The corrected ioIDRegistry.register signature binds devices to a
project NFT (the `(deviceContract, tokenId)` pair) distinguished
by unique device addresses. ioIDRegistry requires the project NFT
to exist before any device can be registered against it. The bridge
wallet at `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` owned
zero project NFTs at investigation time (`IProject.balanceOf(bridge_wallet)`
returned `0`).

**Project NFT prerequisite resolution path**: operator-driven session
(separate from the amendment implementation session) executes:

```solidity
ProjectRegistry.register("VAPI Operator Agents", <projectType>);
```

once per VAPI deployment, minting one IProject NFT to the bridge
wallet. The returned `tokenId` becomes the canonical
`project_token_id` used in all subsequent agent registrations
(both Sentry and Guardian register against the same `project_token_id`
distinguished by their unique device addresses + per-agent ERC-6551
salts per K1a + I2b).

[NOTE 2026-05-02 fourth amendment: this specification was
canonically infeasible at three independent layers. Layer 1 —
ioIDRegistry consumes the `(deviceContract, tokenId)` pair via
`registeredNFT` mapping plus `safeTransferFrom` (cannot be reused
across agents; NFT is transferred away from bridge_wallet on first
registration). Layer 2 — ioIDStore enforces bidirectional 1:1
`deviceContract`-to-`projectId` mapping (IProject contract cannot
be registered as deviceContract for two projects). Layer 3 —
empirical RPC confirmation: `deviceContractProject(IProject)`
returns `0` (IProject is the project-NFT contract, not a registered
device-NFT contract). Corrected per Section 14.4 to N2 β-canonical:
deploy a custom DeviceNFT contract per `contracts/examples/DeviceNFT.sol`
pattern; mint per-agent device tokenIds; identity distinction at
device-tokenId and TBA-tokenId layers rather than salt layer. K1a's
spirit ("one project for both agents") is preserved at the project
NFT layer; the implementation route changes.]

The exact `projectType` uint8 value is empirically verified during
amendment implementation against ioID-contracts canonical source
at commit `b94ad092` and on-chain enum query (delegated per
Section 13.6 OQ2). Likely value is `0 = generic`; ioID-contracts
source documents the canonical type enum.

**Canonical NFT address clarification (per K3 operator decision)**:

Two distinct NFT contracts appear in the ioID architecture, and the
original Section 6.1 conflated them:

| Contract | Address | Role | ERC-6551-bindable? |
|----------|---------|------|---------------------|
| **IProject NFT** (canonical) | `0xf07336e1c77319b4e740b666eb0c2b19d11fc14f` | Project NFTs minted via `ProjectRegistry.register`. Returned by `ProjectRegistry.project()` view call. | **YES — this is the contract bound by ERC-6551 createAccount per the corrected ioID architecture** |
| ioID NFT (per-DID) | `0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` | Per-DID NFTs minted internally by ioIDRegistry as a side effect of device registration. | NO — this is internal ioID infrastructure, not ERC-6551-bindable |

The original Section 6.1 step 3 specified the per-DID address
(`0x45Ce...`) as the ERC-6551 binding target. The corrected step 4
(in-line edit at line 1018 region) targets the IProject contract
(`0xf07336e1c77319b4e740b666eb0c2b19d11fc14f`).

The IProject contract address was discovered empirically by calling
`ProjectRegistry.project()` view (selector `0xf60ca60d`) on the
deployed ProjectRegistry. This is the operator-canonical method
for resolving the IProject contract address; future operators can
verify the address remains current by re-running this view call.

### 13.5 — Orchestration order correction

The original Section 6.1 mint sequence implied a register-then-pin
ordering (step 2 mints the ioID DID, with no IPFS pin step shown
before it). The corrected ioIDRegistry.register signature requires
the IPFS URI and content hash as inputs, meaning IPFS pin must
precede the on-chain register call.

**Corrected orchestration** (the amendment implementation session
encodes this as the new `register_full_flow` implementation in
`agent_registration.py`):

```
1.  populate_did_document
       Read DID document template (frozen JSON-LD shape per Section 6.1).
       Populate verificationMethod from kms_client.get_public_key(agent).
       Populate metadata.createdAt with ISO 8601 timestamp.
       Output: DID document dict ready for canonical serialization.

2.  mint_project_nft (ONE-TIME, separate operator session, NOT per agent)
       ProjectRegistry.register("VAPI Operator Agents", <projectType>)
       Output: project_token_id (uint256). Captured once; reused for
       both agents.

3.  pin_did_document
       PinataClient.pin_json(did_document, name=<agent>)
       Output: IPFS CID (string).

4.  compute_did_content_hash
       canonical = json.dumps(did_document, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")
       hash = keccak256(canonical)
       Output: bytes32 content hash matching ioID-contracts hash
       convention (empirically verified during amendment implementation).

5.  compute_eip712_digest
       Per Section 13.3 — EIP-712 domain + Register typed data
       message containing (device, hash, uri).
       Output: bytes32 digest ready for KMS signing.

6.  kms_sign_eip712_digest
       kms_client.sign(agent, digest)
       Output: DER-encoded ECDSA signature (bytes).

7.  parse_eip712_signature
       DER → (v, r, s) via eth_keys helper (per Section 13.3).
       Output: (uint8 v, bytes32 r, bytes32 s).

8.  mint_ioid_did
       ioIDRegistry.register(
           IProject_address,           # 0xf07336e1c77319b4e740b666eb0c2b19d11fc14f
           project_token_id,           # from step 2
           agent_eth_address,          # from kms_client.get_public_key()
           content_hash,               # from step 4
           uri,                        # CID from step 3
           v, r, s                     # from step 7
       )
       Output: did:io:<agent_eth_address> identifier (the device address itself).

9.  derive_erc6551_tba
       ERC6551Registry.account(
           implementation,
           per_agent_salt,             # keccak256("vapi-anchor-sentry") for Sentry
                                       # keccak256("vapi-guardian") for Guardian
                                       # per I2b
           4690,                       # IoTeX testnet chainId
           IProject_address,           # 0xf07336e1c77319b4e740b666eb0c2b19d11fc14f
           project_token_id            # from step 2 (same project NFT for both agents)
       )
       Output: TBA address (distinct per agent due to per-agent salt).

10. compute_agent_id
       agent_id = keccak256(abi.encode(did_address, tba_address))
       per Pass 2C Q9 FROZEN encoding (unchanged from original).

11. register_agent
       AgentRegistry.registerAgent(agent_id, publicKey, scopeHash, status)
       per Section 6.4 (unchanged from original; P5 verification confirmed
       these specs match deployed AgentRegistry bytecode).
```

The pin-then-register inversion at the agent-registration boundary
(steps 3-8) is the orchestration correction. Steps 1, 2, 9, 10, 11
are unchanged from the original architectural intent (though step 2
is newly prerequisite, step 9 uses per-agent salt + corrected NFT
address per K1a + I2b + K3, and step 10 was already correct per
Q9).

### 13.6 — Open questions resolved during investigation + delegated empirical sub-tasks

Three OQs surfaced during investigation; all delegated to amendment
implementation per Section 12 Q5 precedent of delegating empirical
verification work to implementation sessions.

**OQ1 (shared TBA versus per-agent TBAs)**: resolved as **I2b** —
per-agent TBA derivation with distinct salts. Preserves identity
distinction at the on-chain level matching the capability spec
distinction (Sentry's wiki / provenance / attestation lane vs
Guardian's audits / sweeps / operational stewardship lane) at
commit `52978771`. Per K1a, this layers onto a single shared
project NFT (one IProject token) — distinct salt per agent
produces distinct TBA addresses despite shared `(deviceContract,
tokenId)`. Architectural rationale: ioIDRegistry binds devices to
project NFTs distinguished by unique device addresses (multiple
devices register against same project NFT); capability-level
distinction lives at the agent layer (capability specs at commit
`52978771`), not at the project NFT layer; one project + per-agent
salts is operationally and cost-simpler than two projects + shared
salt while preserving the same security properties.

**OQ2 (project type uint8 value for ProjectRegistry.register)**:
delegated to amendment implementation session as empirical
verification against ioID-contracts canonical source at commit
`b94ad092` (`contracts/ProjectRegistry.sol` — type enum
declaration) and on-chain enum query if ProjectRegistry exposes a
projectType-listing view. Likely value `0 = generic`. Resolution
captured in amendment implementation commit message as a
sub-finding.

**OQ3 (EIP-712 domain parameters for ioIDRegistry signature)**:
delegated to amendment implementation session as empirical
verification via `DOMAIN_SEPARATOR()` view call return value (if
exposed) and canonical source cross-reference at commit `b94ad092`
(`contracts/ioIDRegistry.sol`). The Section 13.3 placeholder values
(`name="ioIDRegistry"`, `version="1"`, `chainId=4690`) are
provisional pending empirical verification.

**Multicall delegation note (NEW; surfaced 2026-05-02)**: the
canonical ioID-contracts commit `b94ad092` carries the message
"feat: add multicall for verifying proxy", suggesting multicall
functionality exists in the canonical ioID flow. Amendment
implementation session determines empirically whether canonical
ioID device registration uses multicall to batch proxy verification
with device registration (potentially reducing per-agent gas cost
+ atomicity surface), or whether direct ioIDRegistry.register
calls per agent remain the canonical path. The decision matters
for the orchestration sequence at Section 13.5 (steps 3-8 may
collapse into a single multicall) and for the per-agent gas
estimate at the wallet-balance check (currently 1.5 IOTX × 1.5
buffer = 2.25 IOTX per Section 13.7). Sub-task delegated per
Section 12 Q5 precedent.

[NOTE 2026-05-02 fourth amendment: multicall sub-task resolved
empirically — Block A confirmed canonical ioID-contracts repository
contains NO multicall files; the "feat: add multicall for verifying
proxy" commit refers to `contracts/proxies/VerifyingProxy.sol`
(separate proxy verification flow), NOT to ioIDRegistry. Pattern A
(direct register call per agent) is canonical. Additionally, the
parenthetical 1.5 IOTX × 1.5 buffer = 2.25 IOTX budget did NOT
include `activeIoID` fee (0.1 IOTX per device = 0.2 IOTX for two
agents) or DeviceNFT contract deployment cost (~0.3 IOTX per N2 β
resolution at Section 14.4). Reassessed per Section 14.6 to
~1.73 IOTX total with 50% safety buffer; bridge wallet balance
16.973199 IOTX provides 9.8x headroom. Sufficient.]

### 13.7 — 2026-05-02 third amendment operator decisions block (sibling to 2026-04-27, 2026-05-01, and 2026-05-02 second amendment)

The operator confirmed the Section 6.4 third amendment 2026-05-02.
The original 2026-04-27 operator decisions block at line 1515 (not
1441 as Sections 11 and 12 reference; the correct line is 1515 —
the 1441 reference in Sections 11 and 12 is pre-existing drift in
those amendments that this third amendment leaves untouched per
the "do not modify Section 11 or Section 12 contents" constraint),
the 2026-05-01 first amendment operator decisions block at
Section 11.6, and the 2026-05-02 second amendment operator decisions
block at Section 12.6 are all preserved verbatim as historical
record. This third-amendment 13.7 block documents what changed and
why, by sibling reference rather than overwriting prior decisions.

**I1a (commit shape)**: Single amendment commit superseding
`dcaf5015` with a comprehensive commit message documenting the
architectural drift `dcaf5015` had and the corrections this
amendment applies. `dcaf5015` stays in git history; force-push
reversion would compromise the audit trail. The discipline pattern
preserves erroneous commits alongside their corrections rather
than rewriting history.

**I2b (TBA derivation strategy)**: Per-agent TBA derivation with
distinct salts. Sentry: `keccak256("vapi-anchor-sentry")`.
Guardian: `keccak256("vapi-guardian")`. Preserves identity
distinction at the on-chain level matching the capability spec
distinction (Sentry's wiki / provenance / attestation lane vs
Guardian's audits / sweeps / operational stewardship lane) at
commit `52978771`.

[NOTE 2026-05-02 fourth amendment: I2b per-agent salts are
canonically infeasible per Section 14.6 M6 finding — the salt
parameter is hardcoded to `0` inside `ioID.mint` and not exposed
to bridge code. No code path allows bridge to specify per-agent
salts. Identity distinction at TBA layer is preserved through
distinct ioID tokenIds (auto-incremented per registration), which
produce distinct TBA addresses regardless of salt (different
last argument to ERC-6551 derivation). I2b's intent (per-agent
distinct TBAs) is honored by the canonical mechanic; only the
salt-based implementation route is superseded.]

**J1b (Section 13 cross-reference shape)**: Section 13 cross-
references include both Solidity function signatures (Section 13.2)
and canonical source links to `github.com/iotexproject/ioID-contracts`
at commit `b94ad092b84f83fba068ed83bc28b72dd6f2cc4f`. Future
operators can verify against canonical source via two independent
paths: the GitHub URL at the pinned commit and the on-chain
deployed bytecode (via `eth_getCode` + selector matching).

**K1a (project NFT architecture)**: One-project architecture
confirmed. One `ProjectRegistry.register` call per VAPI deployment,
producing one IProject NFT named `"VAPI Operator Agents"` (or
similar; exact name confirmed at amendment implementation time
against any ProjectRegistry name uniqueness constraints). Both
agents share the project NFT, distinguished by per-agent salts in
ERC-6551 derivation per I2b. The in-line edit at the original
Section 6.1 lines 1009-1011 replaces the two-project step with a
one-project step.

[NOTE 2026-05-02 fourth amendment: K1a was empirically infeasible
in its specified implementation route ("agents share the project
NFT directly"); superseded by N2 β-canonical at Section 14.7. K1a's
spirit ("one project for both agents") is preserved at the project
NFT layer per Section 14.4 — ProjectRegistry.register is still
called once per VAPI deployment, producing one IProject NFT for
"VAPI Operator Agents" — but the implementation route changes from
"shared project NFT serves both agents directly as deviceContract"
to "shared project NFT plus custom DeviceNFT contract holding
per-agent device tokenIds." See Section 14.4 for the canonical
NFT consumption model and Section 14.5 for the ioIDStore prerequisite
chain that must execute before any agent registration.]

**K2 option (a) (in-line edit location + Section 13 label)**: Apply
in-line edits to **Section 6.1** where affected specifications were
originally written (lines 1009-1011 project registration, line 1012
ioIDRegistry.register signature, line 1018 ERC-6551 binding with
salt and address corrections). Keep Section 13 title as
"Section 6.4 corrections — third amendment" reflecting the
implementation lifecycle stage that surfaced findings. Section 13.1
narrative documents the location reasoning explicitly. Matches
Sections 11/12 single-label precedent (which carry "Section 6.3
Amendment" labels even when their operator decisions blocks at
Sections 11.6 and 12.6 sit in different layout positions from the
Section 6.3 text they amend).

**K3 (NFT address clarification)**: Explicit NFT address
clarification at Section 13.4. The IProject contract at
`0xf07336e1c77319b4e740b666eb0c2b19d11fc14f` is the canonical NFT
contract for ERC-6551 binding per the corrected ioID architecture;
project NFTs minted via `ProjectRegistry.register` are held in
IProject. The ioID NFT contract at
`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` mentioned in the
original Section 6.1 step 3 is per-DID NFT infrastructure (minted
internally by ioIDRegistry as a side effect of device registration,
not ERC-6551-bindable); the original Section 6.1 conflated these
two NFT contracts. The in-line edit at the original Section 6.1
line 1018 region corrects the address reference to point at
IProject.

[NOTE 2026-05-02 fourth amendment: K3's correction was directionally
reversed. Original Section 6.1 step 3 named
`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` (ioID contract) as
the ERC-6551 binding target — actually CORRECT per `ioID.mint`
canonical source (TBA token contract = `address(this)` = ioID
contract; verified at Section 14.6 M6). K3 "corrected" it to
IProject `0xf07336e1c77319b4e740b666eb0c2b19d11fc14f` which is
correct as `deviceContract` parameter of `ioIDRegistry.register`
ONLY IF IProject were also registered via
`ioIDStore.setDeviceContract` — which it is NOT, and cannot be
under N2 β resolution (the registered deviceContract is the custom
VAPIOperatorAgentNFT deployed during Block B). Per Section 14.7
N4 clarification: both addresses are real and serve different
layers of the ioID architecture. The actual `deviceContract`
used in agent registration (per N2 β at Section 14.4) is the
custom DeviceNFT contract, NOT IProject. The TBA token contract
read via `ioID.wallet(ioID_tokenId)` is the ioID contract
`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` (matching original
Section 6.1's address before K3's reversal).]

**Multicall sub-task delegation (NEW)**: per Section 13.6 closing
note, amendment implementation session determines empirically
whether canonical ioID device registration uses multicall to batch
proxy verification with device registration. Sub-task delegated
per Section 12 Q5 precedent.

### 13.8 — Discipline pattern note

The H1a "test-first, defer on-chain to operator session" decision
(dcaf5015) protected the protocol from executing broken code
against real testnet contracts. The Section 6.4 implementation
pre-implementation V9 verification produced an assertion (we will
use minimal inline ABIs based on EIP-6551 spec and IoTeX docs)
rather than empirical verification (the inline ABIs match deployed
contract bytecode). The implementation tested correctly against
mocks because the mocks did not replicate deployed bytecode
behavior; mock fidelity is bounded by the assertion shape mocks
encode.

The investigation session that preceded this amendment produced
the empirical verification V9 should have produced. The findings
caught architectural drift before it produced irreversible state.
The investigation cost approximately 30 minutes of read-only RPC
introspection; the saved cost was the on-chain registration
session that would have failed at first contract call (wasting
gas + diagnostic time + emotional cost of debugging on-chain
failures).

**Lesson preserved**: pre-implementation verification of contract
interfaces against deployed bytecode is required when the
implementation will execute against real testnet contracts.
Documentation-based ABI assumptions warrant empirical verification
before being canonized in implementation code. The Verification-
First Discipline pattern's V-numbered checks must include
"empirically verify ABIs against deployed bytecode" as a standard
V-check whenever the implementation will perform on-chain
state-changing calls. This V-check joins the existing protocol
vocabulary of pre-implementation verifications (read state,
confirm assumptions, identify drift) with a specific empirical
mode for on-chain integration code.

The dcaf5015 commit stays in git history (per I1a) as a worked
example of the failure mode this lesson protects against. Future
operators encountering this lesson can read both the erroneous
commit and the third amendment that corrects it, learning from
the pair.

---

This Section 13 third amendment is the canonical reference for
Section 6.4 implementation work. Section 6.1's original mint
sequence remains in this document for historical record (the
in-line edit at the original Section 6.1 lines 1007-1021 replaced
the original mint sequence with the corrected version + AMENDED
2026-05-02 callout pointing here, with the original three-step
sequence preserved verbatim as a quoted historical-record block);
the 2026-04-27 operator decisions block at line 1515, the
2026-05-01 first amendment operator decisions block in Section
11.6, and the 2026-05-02 second amendment operator decisions
block in Section 12.6 all remain untouched as historical record
of the design phase confirmation, first-amendment confirmation,
and second-amendment confirmation respectively. The discipline
pattern preserves Sections 11, 12, and 13 as siblings, with
Section 13 amending Section 6.1 (a different section than Sections
11 and 12 amend) while sharing their layout convention and
amendment-shape precedent.

---

## Section 14 — Section 6.4 Block A Empirical Refinements — Fourth Amendment (2026-05-02) — Canonical Architectural Drift

This section is the fourth amendment to the Pass 2C design phase
specification. Like Section 13 (third amendment), this amendment
captures architectural drift surfaced by L4a empirical verification
at amendment implementation session start. Unlike Section 13's
single investigation pass, this amendment captures TWO verification
passes: Block A (canonical source function-body reading for
`ioIDRegistry.register`) and Block A extension (canonical source
function-body reading for `ioIDStore`, `ioID.mint`, `Project`,
plus on-chain RPC introspection for fee structure and prerequisite
mappings).

The fourth amendment supersedes Section 13's substantive specifications
on six points (M1 register overload selection, M2 EIP-712 signing
semantics, M3 NFT consumption model, M4 ioIDStore prerequisite chain,
M5 fee structure, M6 TBA creation locus) plus one direction-reversal
clarification (K3 NFT address conflation). Section 13 stays in this
document as historical record per the Pattern C precedent established
by Sections 11 and 12; supersession callouts at affected lines
(2531-2537, 2581-2583, 2750-2752, 2776-2782, 2792-2800, 2815-2827
per Section 13's pre-fourth-amendment line numbering) point forward
to this Section 14.

The amendment ships through Verification-First Discipline (canonicalized
in commit `94bed715`): pre-implementation read-only investigation
across two verification passes, operator approval at multiple
checkpoints (Block A end, Block A extension end, V1-V5 end, P1-P9
end), atomic amendment commit with architectural reasoning preserved.
Block B implementation is OUT OF SCOPE for the session that ships
this amendment; per Option B session pacing decision, Block B is
deferred to a separate session for fresh focus.

### 14.1 — Investigation methodology

L4a empirical verification at amendment implementation session start
across two layers:

**Block A** (Section 13 third amendment investigation pass) read
function bodies for `ioIDRegistry.register` at canonical
`github.com/iotexproject/ioID-contracts` commit
`b94ad092b84f83fba068ed83bc28b72dd6f2cc4f`. The third amendment
investigation captured ABI selectors via deployed bytecode dispatch
table introspection but did not exercise function body semantics.
Block A revealed:

- Both 8-param and 9-param register overloads are deployed; the
  8-param version is a wrapper that calls 9-param with
  `user = msg.sender` (M1)
- The signed digest uses `Permit(address owner, uint256 nonce)`
  type hash, NOT a `Register` data-attestation struct as Section
  13.3 specified (M2)
- `ioIDRegistry.register` consumes the `(deviceContract, tokenId)`
  pair via `registeredNFT` mapping plus `safeTransferFrom` —
  invalidating K1a "shared project NFT" specification (M3)

**Block A extension** read function bodies for `ioIDStore` (the
prerequisite contract that `ioIDRegistry.register` queries),
`ioID.mint` (the per-DID NFT minter that `ioIDRegistry.register`
calls internally), and `Project` / `IProject` (the project NFT
implementation). Combined with on-chain RPC introspection of
`ioIDStore.price()` and `ioIDStore.deviceContractProject(IProject)`,
the extension revealed:

- `ioIDStore.setDeviceContract` enforces bidirectional 1:1
  `deviceContract`-to-`projectId` mapping — invalidating M3-arch γ
  alternative (M4)
- `ioIDStore.price` returns 0.1 IOTX per device registration globally
  (no per-project pricing) — quantifying M5
- `ioID.mint` internally calls `ERC6551Registry.createAccount` with
  salt hardcoded to `0` and token contract = `address(this)` (the
  ioID contract address) — invalidating I2b per-agent salts and
  reversing K3 directional clarification (M6)

Investigation cost: ~30 minutes Block A + ~30 minutes Block A
extension = under one hour of read-only work. Saved cost: Block B
implementation against incorrect specifications producing transactions
that would have failed at first contract call ("nft already used"
revert from M3, "invalid signature" revert from M2, or
"only hardware project" revert from M4).

### 14.2 — M1 finding: register overload selection

Both 8-param and 9-param register overloads are deployed in
`ioIDRegistry` bytecode dispatch table at implementation address
`0x66152a6be42600903b87b6292016496b6dbabf53` (verified empirically
via `eth_getCode`):

```
Selector 0x39a4a241 (8-param)  ✓ present in dispatch table
Selector 0xb20187f1 (9-param)  ✓ present in dispatch table
```

Canonical source `contracts/ioIDRegistry.sol` lines 69-92 at commit
`b94ad092`:

```solidity
function register(
    address deviceContract,
    uint256 tokenId,
    address device,
    bytes32 hash,
    string calldata uri,
    uint8 v,
    bytes32 r,
    bytes32 s
) external payable override {
    register(deviceContract, tokenId, msg.sender, device, hash, uri, v, r, s);
}

function register(
    address deviceContract,
    uint256 tokenId,
    address user,
    address device,
    bytes32 hash,
    string calldata uri,
    uint8 v,
    bytes32 r,
    bytes32 s
) public payable override { ... }
```

The 8-param version is a wrapper that calls the 9-param version
with `user = msg.sender`. For VAPI Operator Agents where the bridge
wallet IS the intended `user`, the 8-param wrapper is operationally
equivalent to the 9-param explicit call.

**Operator decision M1**: 8-param wrapper canonical. No information
loss when bridge_wallet is the intended user; matches Section 13.2
investigation finding (selector `0x39a4a241`); call-shape is simpler.

### 14.3 — M2 finding: canonical permit-style signing semantics

Section 13.3 specified a data-attestation signature signing
`(device, hash, uri)`. This was empirically wrong. Canonical source
`contracts/ioIDRegistry.sol` lines 22-26 + 103-110 at commit
`b94ad092`:

```solidity
bytes32 public constant EIP712DOMAIN_TYPEHASH =
    keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

bytes32 internal constant PERMIT_TYPE_HASH =
    keccak256("Permit(address owner,uint256 nonce)");

// inside register():
bytes32 digest = keccak256(
    abi.encodePacked(
        "\x19\x01",
        DOMAIN_SEPARATOR,
        keccak256(abi.encode(PERMIT_TYPE_HASH, user, _useNonce(device)))
    )
);
require(ecrecover(digest, v, r, s) == device, "invalid signature");
```

The signed struct is `Permit(address owner, uint256 nonce)`
matching ERC-2612 pattern. Only `(user, nonce(device))` is signed;
the `(hash, uri)` content is NOT cryptographically bound to the
signature. The recovered signer must equal `device` (the agent's
KMS-derived ETH address).

**EIP-712 domain confirmed empirically**:

```
name              = "ioIDRegistry"                                 (canonical source)
version           = "1"                                            (canonical source)
chainId           = 4690 (eth_chainId returned 0x1252)             (RPC)
verifyingContract = 0x0A7e595C7889dF3652A19aF52C18377bF17e027D     (canonical address)

EIP712DOMAIN_TYPEHASH = 0x8b73c3c69bb8fe3d512ecc4cf759cc79239f7b179b0ffacaa9a75d522b39400f
PERMIT_TYPE_HASH      = 0xe36c3d5cb707dcfeb19a6a4b1d7b82c8c20d841769c752e659da03b2a8b729f9

Computed DOMAIN_SEPARATOR = 0x4e31e01d4e41f6c9dc9d68103971ef473adf267bd74326f72170daac66329bcc
On-chain DOMAIN_SEPARATOR = 0x4e31e01d4e41f6c9dc9d68103971ef473adf267bd74326f72170daac66329bcc
                            ✓ MATCH (confirms domain construction)
```

**VAPI threat model accepts permit-style signing** because
bridge_wallet IS the trusted relayer in VAPI's architecture (matches
existing pattern from BridgePoolV2 and broader IoTeX ecosystem
ioID flows). The `(hash, uri)` content is operator-controlled —
the bridge knows what DID document it pinned to IPFS; substitution
by a malicious relayer would require compromising the bridge itself,
which already controls the entire registration flow. The protection
this signing pattern provides is anti-replay (per-device nonce)
and anti-spoofing (recovered signer must equal device).

**Implementation requirements per M2** (Block B will encode these):

- Read current nonce via `ioIDRegistry.nonces(device)` view before signing
- Compute Permit struct hash: `keccak256(abi.encode(PERMIT_TYPE_HASH, user, nonce))`
- Compose final digest with EIP-712 envelope: `keccak256("\x19\x01" || DOMAIN_SEPARATOR || struct_hash)`
- KMS signs the digest; `eth_account` or `eth_keys` parses the DER signature into `(v, r, s)`
- Defensive check: locally verify recovered signer == device address before submitting transaction
- Replay protection comes from per-device nonce auto-incremented inside `_useNonce(device)`

### 14.4 — M3 finding: NFT consumption model and N2 β-canonical resolution

Section 13 K1a "shared project NFT" specification was canonically
infeasible at three independent layers:

**Layer 1**: ioIDRegistry consumes the `(deviceContract, tokenId)`
pair (canonical source `contracts/ioIDRegistry.sol` lines 95, 117):

```solidity
require(!registeredNFT[deviceContract][tokenId], "nft already used");
// ...
IERC721(deviceContract).safeTransferFrom(user, _wallet, tokenId);
```

Each successful registration marks the pair as registered (preventing
re-registration) AND transfers the NFT away from the user (the
bridge wallet) to the device's IoID-bound TBA wallet. Sentry's
registration would consume `(IProject, X)` and remove it from
bridge wallet ownership; Guardian's subsequent registration of
`(IProject, X)` would revert with "nft already used" AND bridge
wallet wouldn't own the NFT to transfer.

**Layer 2**: ioIDStore enforces bidirectional 1:1
`deviceContract`-to-`projectId` mapping (canonical source
`contracts/ioIDStore.sol`):

```solidity
function setDeviceContract(uint256 _projectId, address _contract) external override {
    require(IERC721(project).ownerOf(_projectId) == msg.sender, "invald project owner");
    require(projectDeviceContract[_projectId] == address(0), "project setted");
    require(deviceContractProject[_contract] == 0, "contract setted");
    projectDeviceContract[_projectId] = _contract;
    deviceContractProject[_contract] = _projectId;
}
```

A given `deviceContract` address can map to AT MOST ONE `_projectId`.
This invalidates M3-arch γ alternative (which proposed two
ProjectRegistry.register calls producing two IProject tokenIds X
and Y, each used as `(IProject, X)` and `(IProject, Y)` pairs):
the IProject contract address can be set as `deviceContract` for
AT MOST one project, regardless of how many tokenIds it holds.

**Layer 3**: empirical RPC confirmation. `deviceContractProject`
view called against IProject `0xf07336e1c77319b4e740b666eb0c2b19d11fc14f`
returns `0` — IProject is NOT a registered deviceContract for any
project. This is consistent with IProject being the project-NFT
contract (holding project identifiers), distinct from the
device-NFT contract (holding device identifiers, registered via
`setDeviceContract`).

**Architectural alternatives evaluated**:

| Option | Description | Status |
|--------|-------------|--------|
| α | Two separate ProjectRegistry projects (one per agent), each with its own DeviceNFT | More expensive (2× project NFTs + 2× DeviceNFT contracts); against K1a's spirit |
| β | One project (shared "VAPI Operator Agents") + one custom DeviceNFT contract holding per-agent tokenIds | **Closest to K1a's spirit; canonical pattern per `examples/DeviceNFT.sol`** |
| γ | Two IProject tokenIds (X, Y) used as `(IProject, X)` and `(IProject, Y)` pairs | Canonically infeasible (Layer 2 — IProject can map to only one project) |
| skip-ioID | Bypass ioID entirely; use AgentRegistry + KMS keys as identity primitives | Compromises DePIN-thesis alignment for operator agents |

**Operator decision N2 β-canonical**:

```
Step 1: ProjectRegistry.register("VAPI Operator Agents", 0)
        → mints IProject NFT tokenId X (project identifier; bridge_wallet owns)

Step 2: Bridge_wallet deploys VAPIOperatorAgentNFT contract
        → custom DeviceNFT instance per contracts/examples/DeviceNFT.sol pattern
        → at address Y

Step 3: VAPIOperatorAgentNFT.initialize("VAPI Operator Agent NFT", "VOA")
        → standard ERC-721 initialization

Step 4: VAPIOperatorAgentNFT.configureMinter(bridge_wallet, 2)
        → grants bridge_wallet allowance to mint 2 device NFTs

Step 5: ioIDStore.setDeviceContract(X, Y)
        → sets deviceContractProject[Y] = X (bidirectional 1:1 mapping established)
        → callable only by bridge_wallet (X's owner)

Step 6: ioIDStore.applyIoIDs(X, 2) {value: 0.2 IOTX}  [OPTIONAL pre-pay]
        → pre-pays 0.2 IOTX for 2 device activations
        → OR pay-as-you-go via activeIoID at 0.1 IOTX each

Step 7: VAPIOperatorAgentNFT.mint(bridge_wallet) × 2
        → mints device tokenId 1 (Sentry) and tokenId 2 (Guardian)

Step 8: For Sentry — ioIDRegistry.register(VAPIOperatorAgentNFT, 1, sentry_device, ...)
        → consumes (Y, 1); transfers device NFT to Sentry's TBA wallet
        → ioID contract mints per-DID NFT for Sentry; ERC-6551 TBA created internally

Step 9: For Guardian — ioIDRegistry.register(VAPIOperatorAgentNFT, 2, guardian_device, ...)
        → consumes (Y, 2); transfers device NFT to Guardian's TBA wallet
        → ioID contract mints per-DID NFT for Guardian; ERC-6551 TBA created internally
```

**Identity distinction at four layers** (corrected from K1a's
three-layer + on-chain-shared model):

| Layer | Sentry | Guardian | Distinct? |
|-------|--------|----------|-----------|
| Capability lane (commit `52978771`) | wiki/provenance/attestation | audits/sweeps/operational stewardship | ✓ |
| Cryptographic capability (commit `d3b30d58`) | KMS alias `vapi-anchor-sentry-signing` | KMS alias `vapi-guardian-signing` | ✓ |
| Off-chain attribution (commit `fc61d93d` Section 6.2) | GitHub App `vapi-anchor-sentry[bot]` | GitHub App `vapi-guardian[bot]` | ✓ |
| On-chain identity (this amendment N2 β + M6) | Device tokenId 1 → ioID tokenId N → TBA address | Device tokenId 2 → ioID tokenId N+1 → TBA address | ✓ (via tokenId) |

K1a's intent ("one project for both agents") is preserved at the
project NFT layer (Step 1 mints one IProject NFT; both agents
register against the same project per `setDeviceContract` mapping).
K1a's failure (per-agent on-chain distinction collapsed to salt-only)
is corrected at the device-tokenId layer (distinct device NFTs from
the same custom contract) and the ioID-tokenId layer (auto-incremented
per registration). Identity distinction is now load-bearing at FOUR
layers, not three.

### 14.5 — M4 finding: ioIDStore prerequisite chain

Two ioIDStore functions enable a project to register devices.
Canonical source `contracts/ioIDStore.sol` at commit `b94ad092`:

**`applyIoIDs(uint256 _projectId, uint256 _amount) external payable`**:

```solidity
function applyIoIDs(uint256 _projectId, uint256 _amount) external payable override {
    require(IProject(project).projectType(_projectId) == 0, "only hardware project");
    require(msg.value >= _amount * price, "insufficient fund");
    if (feeReceiver != address(0)) {
        (bool success, ) = feeReceiver.call{value: msg.value}("");
        require(success, "collect fee fail");
    }
    unchecked {
        projectAppliedAmount[_projectId] += _amount;
    }
    emit ApplyIoIDs(_projectId, _amount);
}
```

Anyone can call this function (no access restriction beyond payment).
Pre-pays activeIoID fees at 0.1 IOTX per device. **Type constraint**:
`projectType` must equal `0` ("only hardware project") — confirms
Section 13's M3 OQ2 recommendation that VAPI Operator Agents project
should use `_type=0` in the ProjectRegistry.register call.

**`setDeviceContract(uint256 _projectId, address _contract) external`**:

```solidity
function setDeviceContract(uint256 _projectId, address _contract) external override {
    require(IERC721(project).ownerOf(_projectId) == msg.sender, "invald project owner");
    require(projectDeviceContract[_projectId] == address(0), "project setted");
    require(deviceContractProject[_contract] == 0, "contract setted");
    projectDeviceContract[_projectId] = _contract;
    deviceContractProject[_contract] = _projectId;
    emit SetDeviceContract(_projectId, _contract);
}
```

Only the project NFT owner (bridge wallet, after ProjectRegistry.register
mints the project to it) can call this function. Sets the
**bidirectional 1:1 mapping** between projectId and deviceContract
address. Once set, neither side can be replaced without a separate
`changeDeviceContract` call.

**Operator-driven prerequisite chain per N2 β** (must execute before
any agent registration; encoded as a separate operator-driven session,
NOT in `agent_registration.py` register_full_flow):

1. `ProjectRegistry.register("VAPI Operator Agents", 0)` — mints
   IProject NFT tokenId X to bridge_wallet
2. Deploy VAPIOperatorAgentNFT (custom DeviceNFT contract) — gets
   address Y
3. Initialize VAPIOperatorAgentNFT + configure bridge_wallet as
   minter with allowance 2
4. `ioIDStore.setDeviceContract(X, Y)` — establishes the 1:1 mapping
5. (Optional) `ioIDStore.applyIoIDs(X, 2) {value: 0.2 IOTX}` —
   pre-pay for 2 device slots
6. `VAPIOperatorAgentNFT.mint(bridge_wallet)` × 2 — mints device
   tokenIds 1 and 2

After steps 1-6, `ioIDRegistry.register` calls can succeed for both
Sentry and Guardian. The `agent_registration.py` register_full_flow
covers steps 7-9 from the Section 14.4 sequence (the per-agent
registration steps); the operator-driven prerequisite session covers
steps 1-6.

### 14.6 — M5 finding: activeIoID fee structure + M6 finding: TBA creation internal to ioID.mint

**M5 fee structure**:

Single global `price` value in ioIDStore (no per-project differentiation):

```
ioIDStore.price() returned 0x000000000000000000000000000000000000000000000000016345785d8a0000
                         = 100,000,000,000,000,000 wei
                         = 0.1 IOTX per device registration
```

Two payment paths:
- **Pay-as-you-go**: each `ioIDRegistry.register` call forwards
  `msg.value >= price` through `ioIDStore.activeIoID`. Bridge sends
  0.1 IOTX with each agent registration.
- **Pre-pay batch**: `ioIDStore.applyIoIDs(projectId, amount)` pays
  `amount × price` upfront. Subsequent `activeIoID` calls don't
  require payment until the pre-paid balance is exhausted (logic
  at `ioIDStore.activeIoID`: `if (_projectAppliedAmount == _projectActivedAmount)`
  triggers the fee charge; otherwise no msg.value required).

For two-agent registration: 0.2 IOTX in registration fees regardless
of payment path.

**Reassessed wallet budget for full N2 β registration flow**:

| Step | Action | Cost (IOTX) |
|------|--------|------|
| 1 | Deploy VAPIOperatorAgentNFT contract | ~0.30 |
| 2 | DeviceNFT.initialize + configureMinter | ~0.05 |
| 3 | ProjectRegistry.register("VAPI Operator Agents", 0) | ~0.04 |
| 4 | ioIDStore.setDeviceContract(projectId, deviceNFT) | ~0.03 |
| 5 | ioIDStore.applyIoIDs(projectId, 2) {value: 0.2 IOTX} (optional pre-pay) | 0.20 + 0.02 gas |
| 6 | VAPIOperatorAgentNFT.mint(bridge_wallet) × 2 | ~0.05 |
| 7 | ioIDRegistry.register × 2 (8-param) | ~0.40 |
| 8 | AgentRegistry.registerAgent × 2 | ~0.06 |
| **Subtotal** | | **~1.15** |
| **Safety buffer 50%** | | **~0.58** |
| **Total budget** | | **~1.73 IOTX** |

Bridge wallet balance: **16.973199 IOTX** (queried live during Block A
extension via `eth_getBalance`). Headroom: **9.8x over budget**.
**SUFFICIENT.**

Section 13.6 wallet budget parenthetical (1.5 IOTX × 1.5 buffer =
2.25 IOTX) was understated because it didn't include `activeIoID`
fees (M5) or DeviceNFT deployment cost (M3 β). The reassessed
budget accounts for both.

**M6 TBA creation internal to ioID.mint**:

ERC-6551 TBA creation happens INSIDE `ioID.mint`, not as an external
orchestration step. Canonical source `contracts/ioID.sol` at commit
`b94ad092`:

```solidity
address _wallet = IERC6551Registry(walletRegistry).createAccount(
    walletImplementation,
    0,                       // salt HARDCODED to 0
    block.chainid,
    address(this),           // token contract = ioID contract (0x45Ce...)
    id_                      // token ID = newly minted ioID tokenId
);
```

The `walletRegistry` and `walletImplementation` addresses are set
during `ioID.initialize` and immutable thereafter. The salt is
**hardcoded to `0`** and not exposed to bridge code. The TBA token
contract is `address(this)` — the ioID contract address
`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7`, NOT the IProject
address that Section 13 K3 corrected to.

**Implications for `agent_registration.py`** (Block B will encode
these):

1. **Bridge code MUST NOT call `ERC6551Registry.createAccount`**.
   Section 13.5 step 9 (`derive_erc6551_tba` calling
   `ERC6551Registry.createAccount` or `account` view) was wrong as
   an external bridge call. The TBA is created automatically inside
   `ioIDRegistry.register → ioID.mint`. Bridge code reads back the
   TBA address via `ioID.wallet(ioID_tokenId)` (read-only view that
   internally calls `ERC6551Registry.account`).

2. **I2b per-agent salts are canonically infeasible**. The salt
   parameter is hardcoded to `0` inside `ioID.mint` and not exposed.
   No code path allows bridge to specify per-agent salts.

3. **Identity distinction at TBA layer comes from distinct ioID
   tokenIds**, NOT from per-agent salts. Sentry's registration
   produces ioID tokenId N; Guardian's produces N+1. Different last
   argument to ERC-6551 derivation produces different TBA addresses
   regardless of salt. I2b's intent (per-agent distinct TBAs) is
   preserved by the canonical mechanic; only the implementation
   route changes.

4. **TBA token contract is the ioID contract**
   (`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7`), NOT IProject
   (`0xf07336e1c77319b4e740b666eb0c2b19d11fc14f`). Per N4 directional
   reversal clarification at Section 14.7: K3 conflated these two
   addresses in the opposite direction from the original Section
   6.1's conflation.

### 14.7 — 2026-05-02 fourth amendment operator decisions block (sibling to 2026-04-27, 2026-05-01, 2026-05-02 second amendment, and 2026-05-02 third amendment)

The operator confirmed the Section 6.4 fourth amendment 2026-05-02.
The original 2026-04-27 operator decisions block at line 1645 (post
prior-amendment shifts; was 1515 pre-Section-13), the 2026-05-01
first amendment block at Section 11.6, the 2026-05-02 second amendment
block at Section 12.6, and the 2026-05-02 third amendment block at
Section 13.7 are all preserved verbatim as historical record. This
fourth-amendment 14.7 block documents what changed and why, by
sibling reference rather than overwriting prior decisions.

**M1 (8-param register wrapper canonical)**: Both 8-param (selector
`0x39a4a241`) and 9-param (selector `0xb20187f1`) overloads are
deployed; 8-param is the canonical source-provided wrapper that
calls 9-param with `user = msg.sender`. For VAPI's bridge-wallet-
as-relayer model, the 8-param wrapper is operationally equivalent
to the 9-param explicit call.

**M2 (canonical permit-style signing semantics)**: Section 13.3
specification was empirically wrong; canonical signing uses
`Permit(address owner, uint256 nonce)` type hash signing
`(user, nonce(device))`. Implementation reads nonce via
`ioIDRegistry.nonces(device)` view, computes Permit struct hash,
composes EIP-712 envelope, KMS signs, recovered signer must equal
device. VAPI threat model accepts permit-style signing because
bridge_wallet IS the trusted relayer in VAPI's architecture.

**N2 (β-canonical NFT consumption resolution)**: Deploy custom
DeviceNFT contract per `contracts/examples/DeviceNFT.sol` pattern.
ProjectRegistry.register produces ONE project NFT for "VAPI Operator
Agents" (preserving K1a's spirit). VAPIOperatorAgentNFT contract
holds per-agent device tokenIds (corrects K1a's per-agent on-chain
distinction). ioIDStore.setDeviceContract maps project to DeviceNFT
contract. ioIDRegistry.register consumes (DeviceNFT, tokenId) per
agent. Identity distinction at four layers (capability + cryptographic +
off-chain attribution + on-chain via tokenId).

**N3 (M6-acknowledge — per-agent salts canonically infeasible)**:
ERC-6551 salt is hardcoded to `0` inside `ioID.mint` and not
exposed to bridge code. I2b per-agent salts cannot be implemented.
Identity distinction at TBA layer is preserved through distinct
ioID tokenIds (auto-incremented per registration). I2b's intent
(per-agent distinct TBAs) honored by canonical mechanic.

**N4 (K3 directional reversal clarification)**: Both NFT addresses
serve different purposes. The IProject contract
`0xf07336e1c77319b4e740b666eb0c2b19d11fc14f` is correct as
`deviceContract` parameter of `ioIDRegistry.register` IF and ONLY
IF IProject were also registered via `ioIDStore.setDeviceContract`
— which it is NOT, and cannot be (per N2 β, the registered
deviceContract is the custom VAPIOperatorAgentNFT). The ioID
contract `0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` is the TBA
token contract (the second-to-last argument to ERC-6551 derivation
inside `ioID.mint`). K3's correction conflated the two addresses
in the opposite direction from the original Section 6.1's
conflation. Both addresses are real and serve different layers
of the ioID architecture.

**M4 (ioIDStore deviceContractProject prerequisite chain)**:
Two-function prerequisite (`setDeviceContract` + optional
`applyIoIDs`) that must execute before any agent registration.
`setDeviceContract` enforces bidirectional 1:1 mapping. `applyIoIDs`
requires `projectType == 0`. Both are operator-driven steps
(state-changing, not in `agent_registration.py` register_full_flow).

**M5 (activeIoID fee structure + reassessed wallet budget)**:
`ioIDStore.price` returns 0.1 IOTX per device globally. Pay-as-you-go
or pre-pay via `applyIoIDs`. Reassessed total budget for N2 β
registration flow: ~1.73 IOTX with 50% safety buffer. Bridge wallet
balance 16.973199 IOTX provides 9.8x headroom. SUFFICIENT.

**Path 1.5-prime (sequencing)**: Section 14 fourth amendment lands
before Block B implementation references it as canonical specification.
Spec-then-implement pattern preserved per Phase O0's design-document-
precedes-implementation convention.

**N1b (structural choice)**: Section 14 as sibling top-level
amendment matching Sections 11, 12, 13 precedent. Each amendment
lives at its own navigable section with operator decisions block,
supersession markers at affected earlier sections, and architectural
reasoning preserved.

**Option B (session pacing)**: Block B implementation deferred to
a separate session for fresh focus. The session that ships this
amendment ends after commit and push; Block B begins fresh.

### 14.8 — Discipline pattern note

Each verification layer surfaces architectural patterns the prior
layer did not exercise:

| Layer | Verification depth | Findings caught |
|-------|--------------------|-----------------|
| Pre-implementation V9 (Section 6.4 dcaf5015) | Documentation assumption | (none — assumption shape only) |
| Third amendment investigation | ABI selector match against deployed bytecode | M1 (selector existence) |
| Block A function-body reading | `ioIDRegistry.register` body semantics | M2 (permit signing), M3 (NFT consumption) |
| Block A extension function-body reading | `ioIDStore`, `ioID.mint`, `Project` body semantics + on-chain RPC for fee + prerequisite mapping | M4 (prerequisite chain), M5 (fee structure), M6 (TBA internal), K3 reversal |

The pattern of "operator decisions made at insufficient depth of
canonical verification" happened **twice** in this amendment chain:

- **Third amendment K1a**: captured "shared project NFT" without
  verifying NFT consumption mechanic in `ioIDRegistry.register`
  body. Block A reading caught the infeasibility.
- **Fourth amendment brief M3-arch γ**: captured "two IProject
  tokenIds" without verifying bidirectional 1:1 `deviceContractProject`
  mapping in `ioIDStore.setDeviceContract` body. Block A extension
  caught the infeasibility.

Each error was caught by the next verification layer, but the
pattern suggests humility about whether canonical specifications
are feasible until empirically verified at function body depth.
ABI selector verification confirms function existence; function
body verification confirms architectural feasibility. **Both are
required for amendment specifications targeting on-chain contract
interactions.**

**Lesson preserved**: operator decisions on architectural alternatives
that depend on canonical contract interactions warrant empirical
verification at function body depth before being canonized in
amendment specifications. Future amendment specifications targeting
on-chain contract interactions should include function body reading
at canonical source as a **pre-amendment verification step**, not
as an amendment-implementation-session verification step.

The verification sequence for canonical-source-dependent amendments:

1. ABI selector match against deployed bytecode (confirms function
   exists)
2. Function body reading at canonical source commit (confirms what
   the function does)
3. Cross-check against ALL related contracts the function calls
   internally (confirms architectural feasibility across the
   prerequisite chain)
4. On-chain RPC introspection for state-dependent values (fees,
   ownership, mapping content) at the time of amendment authoring

The L4a empirical verification at amendment implementation session
start caught what investigation should have caught at amendment
writing session start. The discipline pattern caught the errors
before Block B implementation built on incorrect specifications.
Cost was ~30 minutes Block A + ~30 minutes Block A extension = under
one hour of read-only work. Saved cost was Block B implementation
against incorrect spec plus operator-driven on-chain session that
would have failed at first contract call.

The fourth amendment ships through the same Pattern C hybrid
shape as Sections 11/12/13. Section 13 stays in this document as
historical record per the discipline pattern's "preserve erroneous
specifications alongside their corrections rather than rewriting
history" precedent. The supersession callouts at Section 13's
affected lines point forward to Section 14 subsections. Future
operators reading Section 13 see the supersession callouts and
follow them to Section 14 for the canonical specification.

---

This Section 14 fourth amendment is the canonical reference for
Section 6.4 Block B implementation work. Section 13's main body
remains in this document for historical record (in-line supersession
callouts at lines 2531-2537 / 2581-2583 / 2750-2752 / 2776-2782 /
2792-2800 / 2815-2827 carry "[NOTE 2026-05-02 fourth amendment]"
markers pointing here). The 2026-04-27 original operator decisions
block at line 1645, the 2026-05-01 first amendment operator decisions
block in Section 11.6, the 2026-05-02 second amendment operator
decisions block in Section 12.6, and the 2026-05-02 third amendment
operator decisions block in Section 13.7 all remain untouched as
historical record. The discipline pattern preserves Sections 11,
12, 13, and 14 as siblings, with Section 14 superseding Section 13
on six substantive points (M1, M2, M3, M4, M5, M6) plus one
clarification (N4 K3 directional reversal) while sharing the same
amendment-shape precedent.

---

This document holds for review. No code. No contract implementations.
No bridge module code. No agent definition files. No commits.
