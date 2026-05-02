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

**Mint sequence per agent** (executed twice, once for each agent):

1. Register agent project on ProjectRegistry. Project name:
   `"vapi-anchor-sentry"` for Sentry; `"vapi-guardian"` for Guardian.
   Output: project_id (uint256).
2. Mint ioID DID via ioIDRegistry. Input: project_id, deviceAddress
   (the agent's ECDSA public key, derived from KMS-backed signing
   key — see Section 6.3).
   Output: did:io:<address> identifier + ioID NFT tokenId.
3. Bind ERC-6551 TBA via the ERC-6551 Registry. Input: ioID NFT
   contract address (`0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7`),
   tokenId (from step 2), salt=bytes32(0), implementation address
   (standard ERC-6551 Account implementation).
   Output: TBA address (the agent's on-chain account).

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
2. Configure key policy + IAM credentials: only the bridge IAM role
   can `kms:Sign` on these 2 specific KMS keys (minimum-privilege
   scoping); only the operator's IAM user can
   `kms:UpdateKeyDescription`, `kms:DisableKey`, `kms:DeleteKey`,
   etc. (administrative actions). Bridge IAM user credentials
   delivered as long-lived `AWS_ACCESS_KEY_ID` +
   `AWS_SECRET_ACCESS_KEY` + `AWS_REGION=us-east-1` env vars in
   `bridge/.env` (gitignored, mode 600 directory; matches existing
   pattern for `BRIDGE_PRIVATE_KEY` IoTeX wallet, GitHub App PEM
   paths at `bridge/secrets/`, and `ANTHROPIC_API_KEY` placeholders).
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
| IAM credentials delivery | Not explicitly addressed | N/A (Lit auth model) | **Long-lived AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in bridge/.env (mode 600 gitignored), kms:Sign minimum-privilege scoping** |
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
keys delivered as `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` +
`AWS_REGION=us-east-1` env vars in `bridge/.env` (gitignored, mode
600 directory). Bridge IAM user has `kms:Sign` minimum-privilege
scoping on the 2 specific KMS keys only; operator IAM user retains
administrative actions.

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

This document holds for review. No code. No contract implementations.
No bridge module code. No agent definition files. No commits.
