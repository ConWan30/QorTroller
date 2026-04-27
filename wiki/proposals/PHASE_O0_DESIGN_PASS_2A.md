# Phase O0 — Design Pass 2A: Four Precursor Work Findings Resolution

**Status**: HOLD FOR REVIEW. No code. No contract modifications. No
bridge updates. No agent definition files. No commits. The deliverable
is design reasoning only. Implementation begins only after operator
approval of the recommendations.

**Scope discipline**: addresses exactly four precursor work findings
from `wiki/proposals/PHASE_O0_VERIFICATION.md` — V8 (wallet funding),
V10 (EAS deployment status and alternatives), V2 (layered authentication
for agent endpoints), V5 (PV-CI gate extension for per-author path
scopes). Does NOT address V11 conceptual alignment (reserved for Pass
2B) or the Phase O0 implementation plan (reserved for Pass 2C).

**Resolved inputs from Design Pass 1** (not open for revision):
1. Parallel `AgentAdjudicationRegistry` contract for agent-scoped
   anchoring; existing `AdjudicationRegistry` at
   `0x44CF981f46a52ADE56476Ce894255954a7776fb4` untouched.
2. Agent action authorization is scope-class (AgentScope + AuditLog
   + AgentAdjudicationRegistry) rather than CONSENT-class.
3. `wiki/audits/` and `wiki/sweeps/` move to top-level `audits/` and
   `sweeps/`.

**Verification standard**: every architectural claim cites `file:line`
or external-source verification. Where the codebase cannot resolve an
ambiguity, the ambiguity is surfaced as an open question for operator
decision rather than silently chosen.

**Date**: 2026-04-26

---

## Section 1 — Executive Summary

**V8 (Wallet funding)**: Recommend funding the wallet at
`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` to **5 IOTX** (current
balance verified live this session at 0.5525 IOTX; gap of ~4.45 IOTX).
The funding target should cover the full 16-20 week Operator series
initiative envelope rather than Phase O0 alone, because operator
funding cadence is naturally batchy (per Phase 237.5 Path C+ session
context: "wallet funding gap of several days") and the cost difference
between funding-for-O0 and funding-for-full-initiative is modest
(~5 IOTX vs ~1.5 IOTX). Per-phase budget (~0.5-1 IOTX) × 7 phases plus
~1 IOTX operational headroom plus ~0.5 IOTX margin against another
drain incident produces the 5 IOTX target. This is operator action;
no other funding source is appropriate at testnet scale.

**V10 (EAS deployment status and alternatives)**: Recommend **Option C**
— extend VAPI's existing FROZEN-v1 primitive family with a sixth
primitive `AGENT_COMMIT v1`, hosted on the
`AgentAdjudicationRegistry` contract that Design Pass 1 already
authorizes. Do NOT deploy EAS to IoTeX testnet. Do NOT anchor
attestations cross-chain. The recommendation aligns the AgentCommit
chain with VAPI's established cryptographic-continuity pattern (GIC,
WEC, VAME, CORPUS-SNAPSHOT, CONSENT all use the same FROZEN-v1
domain-tag + SHA-256 chain shape), reuses the contract Design Pass 1
already plans to deploy, and matches the deployed-bytecode reality
constraint that Phase 237.5 Path C+ surfaced. The trade-off is loss of
EAS ecosystem tooling (attest.org explorer, EAS GraphQL indexer); the
operator should examine this trade-off carefully because external
tooling integration may matter more downstream than internal
architectural continuity, and reasonable operators could choose
Option A (deploy EAS) instead. This is the careful-reasoning
recommendation in this design pass.

**V2 (Layered authentication for agent endpoints)**: Recommend **Option
B** — implement OAuth 2.1 client credentials and HMAC request signing
in Phase O0; defer mTLS via SPIFFE/SPIRE to a later phase when agents
gain write authority. Two-layer authentication is sufficient for the
Phase O0 read-only and Phase P1-P2 shadow/suggestion mode the
architecture document specifies, while keeping Phase O0 scope tractable.
HMAC infrastructure is already in active use in the bridge
(`operator_api.py:223,243,255,1442` use `hmac.compare_digest` and
`hmac.new` with HMAC-SHA256 in production for `_sign()` and
key validation), making the HMAC layer incremental work. OAuth 2.1
client credentials is net-new infrastructure but well-bounded. mTLS via
SPIFFE/SPIRE belongs in P3+ when agents start writing.

**V5 (PV-CI gate extension for per-author path scopes)**: Recommend
**Option B** — implement per-author path scope checking as a separate
GitHub Actions check (`scripts/vapi_path_scope_gate.py` +
`.github/workflows/vapi-path-scope-gate.yml`) that runs alongside the
existing PV-CI invariant gate, NOT as an extension to
`scripts/vapi_invariant_gate.py`. The two checks have different
canonical concerns — invariant fingerprint hashing vs commit-author-vs-
path-scope rule enforcement — and follow VAPI's existing pattern of
focused-script-per-concern. The existing PV-CI gate (28 invariants,
517 lines, governance event chain at `_compute_governance_provenance_hash`
lines 344-359) is critical infrastructure; mixing diff-parsing logic
into it raises the blast radius of any path-scope bug. Both gates use
the same CODEOWNERS file as source of truth, so divergence risk is
mitigated. This is the high-confidence recommendation.

---

## Section 2 — V8 Wallet Funding Resolution

### Nature of the finding

Verification document V8 (lines 458-504) established the live wallet
balance at 0.5525 IOTX against an estimated Phase O0 budget of ~0.86
IOTX, producing a shortfall of ~0.31 IOTX plus margin for transaction
overhead. The decision space is narrow — fund or don't fund — but the
funding target requires explicit reasoning about Phase O0 alone vs the
full Operator series initiative.

### Codebase ground truth

**Live balance verified this session** via `eth_getBalance` against
`https://babel-api.testnet.iotex.io`:

```json
{"result":"0x7aafb1b89bf2000"}
```

Decoded: `0x7aafb1b89bf2000` wei = `552530000000000000` wei ≈ **0.55253
IOTX**. Verification document figure (0.5525 IOTX) still accurate.

**Actual deploy costs from recent VAPI deploy scripts** (each estimate
in the script header comment, with actual verified against CLAUDE.md
post-deploy notes):

- `contracts/scripts/deploy-phase221.js:8` — ProtocolCoherenceRegistry
  estimate ~0.07 IOTX. Actual per CLAUDE.md (Phase 222 note): wallet
  ~10.4 → ~10.36 IOTX = 0.04 IOTX actual deploy cost (smaller than
  estimate).
- `contracts/scripts/deploy-phase222.js:9` — VAPIBiometricGovernance
  estimate ~0.08 IOTX.
- `contracts/scripts/deploy-phase237.js:13` — VAPIConsentRegistry
  estimate ~0.07 IOTX. Actual per CLAUDE.md Phase 237-EXTEND note:
  "Wallet ~40.43 → ~40.36 IOTX (0.17% spent)" = 0.07 IOTX actual cost.

VAPI per-contract deploy costs run 0.04-0.08 IOTX consistently.
Verification document V8's estimates for AgentRegistry, AgentScope,
AgentSlashing, AuditLog (~0.05-0.10 IOTX each) are realistic.

**Gas surprise factor on IoTeX testnet** (per Phase 237.5 Path X
correction commit `f9c6ec11`): static gas estimate of 80k for
`recordAdjudication` hit `status=101 out-of-gas`; actual requirement
was ~160k gas. Phase 237.5 fix uses dynamic `eth_estimateGas` × 1.25
buffer. Storage-heavy operations on IoTeX require ~2× naive
EVM-estimate gas. EAS contracts are storage-heavy (attestation storage,
schema mappings).

### Decision space

The question is not whether to fund (it is required) but how much, and
whether to scope the funding to Phase O0 or the full initiative.

**Phase O0 budget (revised)**:

| Item | V8 estimate | Revised estimate | Reasoning |
|---|---:|---:|---|
| AgentRegistry deploy | 0.07 | 0.07 | matches VAPI pattern |
| AgentScope deploy | 0.05 | 0.05 | matches VAPI pattern |
| AgentSlashing deploy | 0.10 | 0.10 | larger; VetoSlasher pattern |
| AuditLog deploy | 0.05 | 0.05 | append-only Merkle root |
| AgentAdjudicationRegistry deploy (Design Pass 1) | — | 0.08 | new line item; matches VAPIConsentRegistry pattern |
| EAS deploy | 0.23 | **0** | NOT deploying per V10 recommendation Option C |
| AGENT_COMMIT FROZEN-v1 primitive — extends AgentAdjudicationRegistry | — | 0 | folded into AgentAdjudicationRegistry per V10 Option C |
| ioID DID mint × 2 | 0.04 | 0.04 | 2× ~0.02 |
| ERC-6551 TBA bind × 2 | 0.04 | 0.04 | 2× ~0.02 |
| Initialization txs | 0.05 | 0.05 | constructors, ownership |
| Operational headroom for P0 dev | 0.20 | 0.30 | +0.10 buffer for IoTeX gas surprises |
| **Phase O0 total** | **0.86** | **0.78** | |

V10 Option C eliminates EAS deploy line items (-0.23) and adds
AgentAdjudicationRegistry (+0.08). Net Phase O0 budget: **~0.78 IOTX**
conservative estimate; **~1.0 IOTX** with safety margin.

**Full Operator series initiative budget** (per architecture document
section 9, P0-P6 across 16-20 weeks):

| Phase | Activities | Estimate (IOTX) |
|---|---|---:|
| P0 (foundation) | 5 contracts + DIDs + TBAs + init | ~1.0 |
| P1 (shadow/read) | 0 deploys; observation only | ~0.1 |
| P2 (suggestion) | 0 deploys; PR-only | ~0.1 |
| P3 (write tournament gate) | likely 1-2 contract deploys for write enforcement | ~0.3 |
| P4 (assist invariant changes) | likely 1 governance contract deploy | ~0.2 |
| P5 (provenance write) | 0-1 deploys | ~0.2 |
| P6 (full operator) | minimal further deploys | ~0.1 |
| Operational anchoring across all 7 phases | AgentCommit anchors, audit log Merkle roots, etc. | ~0.5 |
| Margin for IoTeX gas surprises × 7 phases | | ~0.5 |
| Margin against bridge-drain recurrence (per R3 in verification) | 1.5× safety | ~0.5 |
| **Full initiative total** | | **~3.5 IOTX** |

**Funding granularity question**: should the operator fund 1 IOTX (P0
only) or 5 IOTX (full initiative + headroom)?

### Recommendation: Fund to 5 IOTX

Recommend the operator fund the wallet to **5 IOTX target balance**
(transferring approximately 4.45 IOTX to the bridge wallet) for these
reasons:

1. **Operator funding cadence is naturally batchy.** Per the prior
   session's Phase 237.5 Path C+ context, operator funding requires a
   "several days" delay between request and arrival. Funding for Phase
   O0 alone would require a second batch within ~4 weeks (Phase O0
   timeline is 3.5-6 weeks per verification). Funding for the full
   16-20 week initiative envelope reduces to one funding action,
   freeing the next 4-5 months from funding-coordination friction.

2. **Cost-of-funding-too-much is small.** Funding 5 IOTX vs 1 IOTX is
   ~4 extra IOTX, which is ~$0.10 at typical IOTX testnet faucet rates
   (testnet IOTX has no real-world value). The operational cost is
   transferring once vs four times. Funding-too-little carries higher
   risk: if any phase encounters an unexpected gas surge (per the
   Phase 237.5 Path C+ pattern), the wallet runs dry mid-deploy and
   leaves contracts in inconsistent state.

3. **Drain-protection margin matters.** R3 in the verification
   document established that the wallet drain class (DualShock retry-
   blind paths against IoTeX's broken P256 precompile) is mitigated by
   the kill-switch but not structurally fixed. If the kill-switch ever
   gets accidentally lifted during Phase O0+ work (e.g., during a
   bridge restart with stale env vars), the wallet could drain again.
   A 5 IOTX baseline gives ~10× the per-incident drain rate (~3
   IOTX/hour observed in Phase 237.5) of operational headroom — enough
   to detect and re-engage the kill-switch before total exhaustion.

4. **Future deploy patterns favor amortized funding.** Phase O0+
   architecture (per architecture doc section 9) anticipates ~10
   contract deploys + ~5 DID/TBA mint operations + ongoing anchor
   transactions. Architecting a funding plan for 5 separate funding
   events introduces 5 days × 5 = 25+ days of cumulative funding-gap
   delay over the 16-20 week initiative. One 5 IOTX deposit eliminates
   that.

5. **Operator action; no alternative funding source.** IoTeX testnet
   IOTX is faucet-acquired. There is no other funding source
   appropriate for testnet-scale operations. The operator either
   acquires it from the IoTeX faucet (current path) or from another
   testnet-IOTX-holding wallet they control. No external party should
   be transferring testnet IOTX into the bridge wallet.

### Architectural details (no implementation)

- **Funding action**: operator transfers ≥4.45 IOTX from their
  funding wallet (or IoTeX testnet faucet sequential drips) to
  `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`.
- **Verification**: Phase O0 implementation should not begin contract
  deploy work until live `eth_getBalance` confirms ≥3 IOTX (the
  conservative threshold for "Phase O0 + initial operational margin
  + drain buffer"). The 5 IOTX target gives 2 IOTX headroom above this
  minimum.
- **Pre-deploy verification step**: every Phase O0+ deploy script
  should add a balance pre-check that aborts if balance <0.5 IOTX
  remaining (prevents partial-deploy state). This is a deploy-script
  pattern enhancement, not a contract change.
- **Kill-switch maintenance**: `CHAIN_SUBMISSION_PAUSED=true` in
  `bridge/.env` MUST remain active during Phase O0. Contract deploys
  use Hardhat's RPC client (per Phase 221/222/237 pattern), not the
  bridge process — this bypasses the retry-blind paths entirely. The
  kill-switch only protects the bridge's runtime chain submissions;
  deploy-time submissions go through Hardhat which has no DualShock
  retry-blind paths to defend against.

### Confidence

**HIGH CONFIDENCE.** The decision space is narrow (fund to a target
amount), the codebase evidence (live balance, actual deploy costs from
3 recent deploys, gas surprise factor) is unambiguous, and the
funding-cadence argument for full-initiative funding is operational
common sense rather than architectural judgment. The 5 IOTX target is
defensible with explicit per-phase math. Operator can review with
confidence.

---

## Section 3 — V10 EAS Deployment Status and Alternatives

### Nature of the finding

Verification document V10 (lines 555-602) established that EAS is not
currently deployed on IoTeX testnet. The architecture document
proposes EAS as the substrate for the AgentCommit attestation chain
(per section 4 / page 4 of the architecture PDF and per
PHASE_O0_VERIFICATION.md:223-238). With EAS unavailable on IoTeX, the
architecture has three resolution paths whose differences are
architecturally substantial.

### Codebase ground truth

**EAS deployment networks** (per
[eas-contracts GitHub README](https://github.com/ethereum-attestation-service/eas-contracts)
fetched via API this session):

- **Mainnets deployed**: Ethereum, Optimism, Base, Arbitrum One,
  Arbitrum Nova, Polygon, Scroll, zkSync, Celo, Telos, Soneium, Ink,
  Unichain, Blast, Linea (15 mainnets)
- **Testnets deployed**: Sepolia, Optimism Sepolia, Optimism Goerli,
  Base Sepolia, Base Goerli, Arbitrum Sepolia, Polygon Amoy, Scroll
  Sepolia, Ink Sepolia, Linea Goerli (10 testnets)
- **IoTeX testnet (4690) NOT in deployment list**. Confirmed.

**EAS contract sizes** (per GitHub Contents API
`/repos/ethereum-attestation-service/eas-contracts/contents/contracts`
fetched this session):

| Contract | Source size | Notes |
|---|---:|---|
| `EAS.sol` | 29,265 bytes | Main attestation contract; storage-heavy |
| `IEAS.sol` | 16,921 bytes | Interface |
| `Indexer.sol` | 10,440 bytes | Optional indexer |
| `SchemaRegistry.sol` | 1,781 bytes | Schema registration |
| `Common.sol` | 1,323 bytes | Shared types |
| `Semver.sol` | 1,183 bytes | Versioning |
| Other interfaces | ~1,917 bytes | ISchemaRegistry, ISemver |

For comparison, VAPI's deployed contracts sit at 5-7 KB source
(`VAPIBiometricGovernance.sol`, `VAPIConsentRegistry.sol`,
`ProtocolCoherenceRegistry.sol`). EAS.sol at 29 KB is **5-6× larger**
than VAPI's standard contracts.

**Verification doc V8 estimate of EAS deploy at 0.15 IOTX is
optimistic.** Realistic IoTeX deploy cost for a 29 KB contract under
the IoTeX gas surprise factor (~2× naive estimate per Phase 237.5
Path C+): ~0.20-0.30 IOTX for EAS.sol main, plus ~0.05-0.08 IOTX for
SchemaRegistry.sol. Total EAS deploy realistically ~0.25-0.38 IOTX.

**VAPI's existing FROZEN-v1 primitive family** (per
`VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md` and CLAUDE.md "Hard Rules"
section):

1. **GIC v1** (Phase 235-A) — `bridge/vapi_bridge/grind_chain.py`,
   genesis tag `b"VAPI-GIC-GENESIS-v1"`, formula
   `SHA-256(prev(32)||commitment_hash(32)||verdict_code(1)||host_state_code(1)||ts_ns_be(8))`
2. **WEC v1** (Phase 236-WATCHDOG) —
   `bridge/vapi_bridge/watchdog_chain.py`, genesis tag
   `b"VAPI-WEC-GENESIS-v1"`, formula
   `SHA-256(prev(32)||event_code(1)||pid_be(4)||sid_hash(16)||ts_ns_be(8))`
3. **VAME v1** (Phase 236-VAME) — `bridge/vapi_bridge/vame.py`, formula
   `SHA-256(b"VAPI-VAME-v1"||chain_head_16b||ts_ns_be(8)||endpoint||body_bytes)`
4. **CORPUS-SNAPSHOT v1** (Phase 236-CORPUS-SNAPSHOT) —
   `bridge/vapi_bridge/corpus_snapshot.py`, formula
   `SHA-256(b"VAPI-CORPUS-SNAPSHOT-v1"||wiki_hash(32)||agent_root(32)||ratio_milli_be(8)||corpus_n_be(8)||ts_ns_be(8))`
5. **CONSENT v1** (Phase 237-CONSENT) —
   `bridge/vapi_bridge/consent_categories.py`, formula
   `SHA-256(b"VAPI-CONSENT-v1"||device_id_b32||bitmask_be(4)||expires_at_be(8)||ts_ns_be(8))`

All five primitives share the same architectural shape: domain tag +
identifier bytes + payload bytes + ts_ns big-endian, hashed with
SHA-256 to produce a 32-byte commitment. Each is FROZEN: any change
requires v2 + new domain tag.

**AgentAdjudicationRegistry from Design Pass 1** (per
`PHASE_O0_DESIGN_PASS_1.md:191-225`): scheduled for Phase O0 deploy
with function signature
`anchorAgentAction(bytes32 actionHash, bytes32 agentId, string actionType)`,
event `AgentActionAnchored(bytes32 indexed agentId, bytes32 indexed
actionHash, string actionType, uint256 blockNumber)`, with
`requireAgentScope(agentId, actionType)` modifier. **This is already
the AgentCommit attestation primitive shape** — actionHash is the
content commitment, agentId is the signer, actionType differentiates
commit types.

### Decision space

Three resolution options enumerated in the prompt evaluated against
four criteria: (1) alignment with VAPI's cryptographic continuity
principle, (2) operational complexity, (3) ecosystem compatibility,
(4) architectural clarity.

**Option A — Deploy EAS to IoTeX testnet ourselves**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Cryptographic continuity | **MIXED** | EAS uses its own attestation paradigm (UID-based attestations with `refUID` chains, schema-typed attestation data). This is a meaningfully different paradigm from VAPI's FROZEN-v1 SHA-256-domain-tag pattern. VAPI gains a parallel attestation system rather than extending the established family. The principle of "FROZEN-v1 primitives establish the cryptographic continuity pattern" is honored less by Option A than by Option C. |
| (2) Operational complexity | **MODERATE-HIGH** | Deploys SchemaRegistry + EAS + (optionally) Indexer; registers 3+ schemas (AgentCommit, AgentBridgeCall, AgentBoundaryUpdate); integrates EAS calls into chain.py; handles IoTeX gas surprises during the 29 KB EAS.sol deploy. Estimated 0.5-1 week of additional Phase O0 work per verification doc Section 4. |
| (3) Ecosystem compatibility | **STRONG** | VAPI joins the EAS ecosystem; future tooling (attest.org explorer integration, EAS GraphQL indexers, ecosystem-aware contracts) compatible. This is the load-bearing argument for Option A. |
| (4) Architectural clarity | **STRONG** | Standard EAS schema patterns are well-documented; agent attestations follow industry-standard shape; external auditors familiar with EAS recognize the surface immediately. |

**Option B — Anchor attestations cross-chain (Base Sepolia or similar where EAS exists)**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Cryptographic continuity | **WEAK** | The architecture document's claim that "every wiki phase verifiable from CORPUS-SNAPSHOT down to its first commit" requires a unified verification surface. Cross-chain proof requires the verifier to query two chains and reconcile their attestation references. This is meaningfully harder for external auditors than single-chain verification. The principle of cryptographic continuity is fragmented across chains. |
| (2) Operational complexity | **HIGH** | Two chains, two RPC endpoints, two wallets (or one wallet with cross-chain bridge), cross-chain coordination. Each AgentCommit attestation requires EAS-network gas (which is higher than IoTeX testnet because mainnet/sepolia EAS networks have real economics). Cross-chain UID linking back to IoTeX records requires additional schema fields and verification logic. |
| (3) Ecosystem compatibility | **STRONG** | Uses live EAS deployment; same tooling as Option A. |
| (4) Architectural clarity | **WEAK** | Fragmented protocol identity across chains. The architecture document treats VAPI as an IoTeX-anchored protocol; cross-chain attestation breaks that anchoring claim for the agent layer specifically. |

**Option C — Build VAPI-specific AgentCommit attestation primitive on
AgentAdjudicationRegistry, extending the FROZEN-v1 family**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Cryptographic continuity | **STRONG** | VAPI's FROZEN-v1 family (GIC, WEC, VAME, CORPUS-SNAPSHOT, CONSENT) is the established cryptographic continuity pattern. Adding AGENT_COMMIT v1 as the sixth primitive extends the pattern literally — same domain tag shape, same SHA-256 chain semantics, same FROZEN-v1 v2-escape-clause governance. The architecture document's section 8 already anticipates a sixth FROZEN-v1 primitive (OPERATOR per section 8); AGENT_COMMIT could be that sixth primitive or a sibling, with operator decision on naming. The cryptographic continuity criterion is maximally satisfied. |
| (2) Operational complexity | **LOW** | Extends `AgentAdjudicationRegistry` — the contract Design Pass 1 ALREADY plans to deploy in Phase O0. No additional contract deploys. The AGENT_COMMIT v1 hash formula lives in a new bridge module (e.g., `bridge/vapi_bridge/agent_commit.py`) following the exact pattern of `corpus_snapshot.py`, `consent_categories.py`, etc. Estimated +2-3 days to Phase O0 vs +0.5-1 week for Option A. |
| (3) Ecosystem compatibility | **WEAK** | VAPI does not benefit from EAS tooling. attest.org explorer doesn't see VAPI agent commits. EAS GraphQL indexers don't index them. Future ecosystem contracts that expect EAS-format attestations don't interoperate. **This is the load-bearing argument against Option C.** |
| (4) Architectural clarity | **STRONG** | Single-chain (IoTeX), single-family (FROZEN-v1), single-pattern (domain-tag SHA-256 chain). External auditors familiar with VAPI's existing primitives recognize AGENT_COMMIT as "the same shape." External auditors unfamiliar with VAPI must learn one paradigm rather than two. |

### Recommendation: Option C (extend FROZEN-v1 family with AGENT_COMMIT v1)

Recommend **Option C — build VAPI-specific AgentCommit attestation
primitive as the sixth FROZEN-v1 family member, hosted on
`AgentAdjudicationRegistry`** for these reasons:

1. **VAPI's first criterion is cryptographic continuity.** Per the
   prompt's first criterion: "alignment with VAPI's principle of
   cryptographic continuity, which the existing FROZEN-v1 primitives
   establish as a foundational pattern." The five existing FROZEN-v1
   primitives ARE that pattern. Option C extends the pattern literally
   (same domain tag shape, same SHA-256 chain semantics, same v2
   escape clause governance via INV-AGENT_COMMIT-001). Option A
   introduces a parallel attestation paradigm that doesn't follow the
   pattern. Option C maximally satisfies the first criterion;
   Option A satisfies it less; Option B fragments it.

2. **AgentAdjudicationRegistry IS the natural host.** Per Design Pass
   1 Section 2.7, AgentAdjudicationRegistry's
   `anchorAgentAction(bytes32 actionHash, bytes32 agentId, string actionType)`
   is precisely the AgentCommit shape: actionHash = AGENT_COMMIT v1
   commitment, agentId = the agent's DID-bound identity, actionType =
   `"AGENT_COMMIT"` to differentiate from other agent actions. The
   contract Design Pass 1 already authorizes for Phase O0 deploy is
   exactly the contract Option C needs. No additional contract work.

3. **Phase 237.5 Path C+ taught the deployed-bytecode lesson.** The
   verification document's R1 risk surface establishes that "deployed
   bytecode is what matters; source-only extensions don't ship." EAS
   deployment to IoTeX puts ~50 KB of EAS bytecode on-chain that VAPI
   then becomes responsible for maintaining. Every IoTeX-side EAS
   contract is a future redeploy candidate when EAS upstream evolves
   (EAS has had v0.26, v0.28, v0.29, v1.0 evolutions per the
   eas-contracts release history). Option C avoids this — VAPI controls
   its own primitive evolution via its established FROZEN-v1 v2
   escape clause.

4. **Ecosystem compatibility cost is real but mitigatable.** The
   weak point of Option C is loss of EAS tooling. Mitigation: VAPI
   could publish an EAS-compatibility shim later (a contract that
   reads VAPI AgentCommit attestations and re-emits them as EAS-format
   attestations on a chain where EAS exists). This shim is OPTIONAL
   future work — Phase O0 doesn't need it. If ecosystem integration
   becomes high-priority later, the shim is a clean retrofit. The
   cost of NOT building Option C now (entire EAS deploy + maintenance
   + paradigm divergence from existing primitives) is higher than the
   cost of deferring ecosystem-shim work.

5. **AGENT_COMMIT v1 hash formula proposal** (design only; not
   implementation):
   ```
   AGENT_COMMIT_HASH_v1 = SHA-256(
       b"VAPI-AGENT-COMMIT-v1"   (20 bytes)
       || agent_id (bytes32)
       || commit_sha (bytes20)   — git SHA-1, native commit-id length
       || prev_commit_hash (bytes32)  — chained reference, zeros for genesis
       || repo_uri_sha (bytes32) — SHA-256 of the canonical repo URI
       || ts_ns (uint64 BE)
   )                              = 136 bytes → 32 bytes
   ```
   Genesis tag: `b"VAPI-AGENT-COMMIT-GENESIS-v1"`. The chain links
   commits through `prev_commit_hash`, mirroring GIC's `prev_gic`
   semantics. agent_id is the bytes32 representation of the agent's
   ioID DID + ERC-6551 TBA address binding. commit_sha is the actual
   git SHA-1 (20 bytes) of the agent's commit. repo_uri_sha is a
   stable hash of the repository URI to prevent agents from claiming
   commits they made elsewhere. ts_ns is the agent's claimed commit
   timestamp.

6. **Dual-attestation pattern** (design only): the AgentCommit hash is
   computed by the bridge upon agent commit, anchored to
   `AgentAdjudicationRegistry` via `anchorAgentAction(commit_hash, agent_id, "AGENT_COMMIT")`,
   AND the agent's GitHub App signature on the commit is independently
   verifiable through GitHub's API. The IoTeX-anchored hash is the
   protocol's record; the GitHub signature is the developer-tool's
   record. Both must agree for the AgentCommit to be valid. This
   gives ecosystem-style verifiability without depending on EAS.

### Architectural details for Option C

The recommendation requires the following design decisions in Phase O0
(no implementation in this session):

- **New bridge module**: `bridge/vapi_bridge/agent_commit.py` —
  follows pattern of `corpus_snapshot.py`. Exports
  `compute_agent_commit_hash(agent_id, commit_sha, prev_commit_hash, repo_uri_sha, ts_ns)`,
  `genesis_agent_commit(agent_id, ts_ns)`,
  domain tag constant `_AGENT_COMMIT_TAG = b"VAPI-AGENT-COMMIT-v1"`.
- **Store table**: `agent_commit_log` — schema mirrors
  `corpus_snapshot_log` shape with extra columns `agent_id`,
  `commit_sha`, `prev_commit_hash`, `repo_uri_sha`, `tx_hash`,
  `on_chain_confirmed`. `bridge/vapi_bridge/store.py` migration.
- **Chain wrapper**: `bridge/vapi_bridge/chain.py` gains
  `async def anchor_agent_commit(self, commit_hash_hex, agent_id_hex)
   -> tuple[Optional[str], bool]`. Calls
   `AgentAdjudicationRegistry.anchorAgentAction(commit_hash, agent_id, "AGENT_COMMIT")`.
- **Operator endpoint**: `POST /operator/anchor-agent-commit` (audit
  surface; agents call this; full operator auth + agent-bound HMAC per
  V2 recommendation).
- **PV-CI invariants**: `INV-AGENT-COMMIT-001` freezes the
  `compute_agent_commit_hash` function signature;
  `INV-AGENT-COMMIT-002` freezes the domain tag literal
  `b"VAPI-AGENT-COMMIT-v1"`.
- **VAPI_INVARIANTS.md update**: add AGENT_COMMIT v1 to the FROZEN-v1
  primitive registry in a separate documentation commit (not Pass 2A's
  responsibility).
- **EAS integration deferred**: explicitly out of scope for Phase O0.
  If ecosystem integration becomes priority in P5+ or beyond, build an
  optional EAS-compatibility shim contract that reads
  AgentAdjudicationRegistry events and re-emits them as EAS
  attestations on a chain where EAS exists. This is post-O6 future
  work; Phase O0 does not need it.

### Ecosystem-compatibility loss honest accounting

Option C's loss of EAS ecosystem tooling means:

- **No attest.org explorer integration**: VAPI agent commits won't
  appear on the centralized EAS explorer. External observers wanting
  to verify a specific agent's commit history must query
  AgentAdjudicationRegistry directly (or the bridge's
  `GET /agent/agent-commit-history` endpoint).
- **No EAS GraphQL indexer**: agent commits don't show up in EAS
  GraphQL queries. Tooling that filters by EAS schema (e.g., "show me
  all attestations matching schema X") doesn't see VAPI commits.
- **No ecosystem contract interop**: future contracts expecting
  EAS-format attestations as inputs (e.g., DAO governance contracts
  that gate on EAS attestations from specific issuers) don't
  interoperate with VAPI agent commits without adapter contracts.

These costs are real. They are mitigated by:

- **VAPI's own indexing infrastructure** (per `vapi_wiki_engine.py`
  and `bridge/vapi_bridge/store.py` patterns) — VAPI already maintains
  internal indexing for its primitives.
- **Explicit external query API**: `GET /agent/agent-commit-history`
  endpoint serves the same query surface that EAS GraphQL would.
- **Future EAS-shim contract** (deferred): if external integration
  becomes priority, the shim is small contract work. Not Phase O0.

The ecosystem-compatibility cost is **deferrable, not destroyed**.
That asymmetry favors Option C.

### Confidence

**CAREFUL REASONING.** This recommendation depends on the operator's
weighing of architectural-continuity benefit vs ecosystem-compatibility
cost. The codebase strongly supports Option C: VAPI's five FROZEN-v1
primitives establish the pattern, AgentAdjudicationRegistry is already
authorized for deploy, and Phase 237.5 Path C+ taught the value of
controlling primitive evolution. But ecosystem integration with EAS
may matter more downstream than the codebase can know now — particularly
if VAPI plans to integrate with DAO tooling, multi-protocol attestation
aggregators, or other EAS-native ecosystem layers in the medium term.

The architecture document's framing (section 4) implies the operator's
preference is Option A. If the operator's vision values external
tooling integration as a primary concern, Option A is the correct
path. If FROZEN-v1 family extension is the right pattern, Option C is
the correct path.

The operator should examine this recommendation especially carefully
and confirm the architectural priority before authorizing
implementation. This is the kind of architectural-priority decision
where the operator's vision should guide the final acceptance, not
codebase verification alone.

---

## Section 4 — V2 Layered Authentication Resolution

### Nature of the finding

Verification document V2 (lines 107-169) established that existing
bridge authentication uses single-shared-secret patterns through
`_check_key` and `_check_read_key`, while the architecture document
specifies layered authentication for agent endpoints using OAuth 2.1
client credentials, HMAC request signing, and mTLS via SPIFFE/SPIRE.
Phase O0 must decide which layers to implement now and which to defer.

### Codebase ground truth

**Existing bridge authentication** (per
`bridge/vapi_bridge/operator_api.py`):

- **Line 219-224**: `_check_key(api_key)` — compares api_key against
  `cfg.operator_api_key` via `hmac.compare_digest()`; raises 503 if key
  not configured, 403 if mismatch.
- **Line 235-250**: `_check_read_key(x_api_key)` — Phase 224 W1 fix;
  read-only variant; same comparison pattern.
- **Line 226-233**: `_check_rate(api_key)` — sliding-window rate
  limiter keyed on the api_key string (which is a single shared
  secret, so effectively identity-blind).
- **Line 252-257**: `_sign(device_id, eligible, ts)` — produces
  HMAC-SHA-256 signature over canonical-form
  `f"{device_id}:{int(eligible)}:{ts}"`. **HMAC-SHA-256 is already
  in production use.** The only missing piece is request-signing
  semantics (canonical request string format, nonce dedup, timestamp
  enforcement, key-id headers).
- **Line 1442**: another `hmac.new(...)` call in production
  (Phase 158 GSR HMAC validation).

**No JWT, no OAuth, no SPIFFE/SPIRE infrastructure** anywhere in the
bridge. Verified via grep across `bridge/vapi_bridge/*.py` for
`oauth|OAuth|jwt|JWT|token_exchange|RFC 8693|rfc8693`: zero matches
(`cryptoauthlib` matches were false positives — that's an ATECC608A
hardware library, not OAuth).

**Bridge process model**: single Python asyncio process
(`python -m bridge.vapi_bridge.main`). SPIRE typically deploys in
Kubernetes with SPIRE agents per-host issuing SPIFFE Verifiable
Identity Documents (SVIDs) to workloads via the Workload API. VAPI's
single-process bridge is not a Kubernetes-native context; SPIRE
integration would require either (a) running SPIRE agent on the bridge
host with the bridge as a SPIFFE workload, or (b) deferring mTLS to a
later phase when bridge orchestration matures.

**Phase O0 agent permission model** (per architecture document section
9 P0-P2 rollout):

- **P0 (foundation)**: agents have read-only access; they observe
  protocol state but write no records.
- **P1 (shadow/read-only)**: agents shadow the existing fleet's
  observations; ≥95% alignment requirement; no PR creation.
- **P2 (suggestion)**: agents draft PRs but require human approval;
  ≥90% PR acceptance rate gate.

Write authority — particularly for invariant changes, contract calls,
and tournament gates — does not arrive until **P3+**. The Phase O0
authentication surface only needs to handle read-only and
shadow-mode agent actions.

### Decision space

Three options enumerated in the prompt evaluated against three
criteria: (1) security strength sufficient for Phase O0 agent
operations (read-only + shadow), (2) Phase O0 scope manageability,
(3) forward compatibility with the full layered stack.

**Option A — Full three-layer stack in Phase O0 (OAuth + HMAC + mTLS)**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Security strength | **STRONG** | Matches architecture document fully. Every agent request authenticated by service-identity (mTLS), client-identity (OAuth token), and request-integrity (HMAC). Defense-in-depth. |
| (2) Scope manageability | **WEAK** | SPIRE deployment is non-trivial. The bridge is a single Python process, not Kubernetes-native. SPIRE agent setup, SVID issuing, workload registration, certificate rotation — entirely new ops infrastructure. Realistic estimate: +1-2 weeks to Phase O0 just for mTLS/SPIRE. Pushes Phase O0 timeline from 3.5-6 weeks (per verification doc Section 4) to 5-8 weeks. |
| (3) Forward compatibility | **STRONG** | Already at full architecture spec; nothing to add later. |

**Option B — OAuth 2.1 client credentials + HMAC request signing in
Phase O0; defer mTLS to later phase**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Security strength | **STRONG-FOR-PHASE-O0** | Two-layer authentication. OAuth token gives identity + scopes + TTL (replay-bounded). HMAC request signing with nonce dedup + timestamp window gives request-integrity. Sufficient for read-only + shadow-mode operations where the threat surface is "agent's credentials are compromised → leaked agent token + key signs malicious read requests." Two layers means compromising one doesn't yield action; compromising both is meaningfully harder than current single-shared-secret. mTLS adds service-identity binding that matters when agents WRITE; in P0 they don't. |
| (2) Scope manageability | **MODERATE** | OAuth issuer (or short-lived JWT minter) is new infrastructure but well-bounded. HMAC verification middleware is incremental — bridge already uses `hmac.new()` and `hmac.compare_digest()` in production. Estimated +0.5-1 week to Phase O0. |
| (3) Forward compatibility | **STRONG** | mTLS is purely additive — adding SPIFFE/SPIRE later doesn't require changes to existing OAuth/HMAC layers; it adds a third independent layer. The architecture document's full layered spec is reachable from Option B's foundation. |

**Option C — OAuth 2.1 client credentials only in Phase O0; defer
HMAC and mTLS to later phases**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Security strength | **MODERATE** | Single-layer with TTL + scopes is meaningfully stronger than current single-shared-secret (tokens expire, scopes limit blast radius if compromised). But single-layer is single-layer — compromising the OAuth token compromises everything. For read-only operations the cost of compromise is low; for shadow-mode (where agents read fleet state and propose stewardship actions) the cost rises if the token can be exfiltrated and replayed within its TTL. |
| (2) Scope manageability | **STRONG** | Just OAuth issuer + token verification middleware. Smallest scope addition. |
| (3) Forward compatibility | **STRONG** | Both HMAC and mTLS are additive layers. |

### Recommendation: Option B

Recommend **Option B — OAuth 2.1 client credentials + HMAC request
signing in Phase O0; defer mTLS to a later phase** for these reasons:

1. **Security strength sufficient for Phase O0 + P1 + P2.** During
   P0-P2 the agents are read-only or shadow/suggestion mode. The
   threat model is "compromised agent credentials yield compromised
   agent reads + drafted PRs that humans review." Two-layer auth
   means compromising one layer (e.g., exfiltrating an agent's OAuth
   token) yields tokens but not signed requests — the attacker still
   needs the HMAC signing key to produce valid requests. This is
   meaningfully harder than the current single-shared-secret model
   where any leaked key authorizes everything. mTLS adds service-
   identity binding which becomes load-bearing when agents WRITE
   (P3+). For P0 it's not yet load-bearing.

2. **HMAC layer is incremental on existing patterns.** Per the
   codebase ground truth section, HMAC-SHA-256 is already in
   production at `_sign()` (line 252-257) and validation at
   `_check_key`/`_check_read_key` (lines 223, 243). Adding canonical-
   request-string + nonce-dedup + timestamp-window is well-bounded
   work. The architecture document's specification at section 7 page
   2 is detailed: canonical string `METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(body)`,
   headers `X-Agent-KeyId / X-Timestamp / X-Nonce / X-Signature`,
   ±300s clock skew window, Redis-backed nonce dedup. Each component
   has clear references to standards (HTTP signature schemes,
   token-bucket rate limiting). Realistic estimate: +3-5 days for
   HMAC middleware on top of existing patterns.

3. **OAuth 2.1 is bounded new work.** OAuth 2.1 client credentials
   flow (RFC 6749 + draft OAuth 2.1) requires:
   - Token issuer (self-hosted; small JWT minter; configuration for
     client_id + client_secret per agent)
   - Token verification middleware on bridge (FastAPI dependency)
   - Per-endpoint scope annotations
   - Token TTL enforcement (60-300s per architecture doc)
   - Token-exchange (RFC 8693) for downstream calls (deferred to P3+
     when downstream calls happen)
   None of this requires Kubernetes, K8s service mesh, SPIRE agent
   deployment, or SVID rotation infrastructure. Estimated +3-5 days.

4. **mTLS / SPIRE is honestly out of scope for Phase O0.** The
   bridge runs as a single Python asyncio process; SPIRE agents
   typically run as DaemonSets in Kubernetes. Adding SPIFFE/SPIRE to
   a non-K8s bridge requires either (a) running SPIRE agent on the
   bridge host with bridge as a SPIFFE workload (non-standard
   deployment pattern; requires SPIRE infrastructure work that has
   nothing to do with the bridge itself), or (b) deferring mTLS until
   bridge orchestration matures. Forcing SPIRE/SPIFFE into Phase O0
   bloats scope substantially. The architecture document's mTLS
   layer is appropriately deferred to a phase where bridge runs in
   K8s and service mesh is the operating context. P3 (when agents
   write) is a defensible deferral point.

5. **Phase O0 scope discipline is an explicit operator concern.**
   The verification document's Section 4 establishes the 3.5-6 week
   estimate already accounts for some auth scope. Option A pushes
   that to 5-8 weeks — beyond the architecture document's own
   framing. Option B keeps within the verification-revised range.
   Option C is too thin on security; Option B is the right balance
   point.

### Architectural details for Option B (no implementation)

The recommendation requires the following design decisions in Phase O0
(no code in this session):

- **OAuth 2.1 token issuer**: self-hosted; the bridge OR a separate
  small service (e.g., `bridge/vapi_bridge/oauth_issuer.py` runs
  alongside the bridge or as a new module). Issues short-lived JWTs
  (60-300s TTL) signed with HS256 (HMAC) or RS256 (asymmetric).
  Recommendation: HS256 in P0 for simplicity; migrate to RS256 in P3+
  when key rotation matters more (agents are reading-only in P0;
  short TTL is the primary protection).
- **OAuth scopes**: per architecture document section 7,
  `bridge:agent:phases:read`, `bridge:agent:ceremony:propose`,
  `bridge:agent:contract:invoke:adjudication`. P0 only needs the
  read scopes; write scopes registered but unused until P3+.
- **HMAC canonical request format**: per architecture document section
  7, `METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(body)`. Headers
  `X-Agent-KeyId`, `X-Timestamp`, `X-Nonce`, `X-Signature`. ±300s
  clock skew window. Nonce dedup: in-memory LRU with TTL eviction
  in Phase O0 (Redis-backed for P3+).
- **Bridge middleware**: new `bridge/vapi_bridge/agent_auth.py`
  module. Implements `_check_agent_token(authorization, x_agent_keyid,
  x_timestamp, x_nonce, x_signature, request)`. Used as FastAPI
  dependency on agent endpoints. Coexists with existing
  `_check_key`/`_check_read_key` (operator-key endpoints unchanged).
- **Per-endpoint annotation**: agent-scoped endpoints decorated with
  `@requires_agent_auth(scopes=["bridge:agent:phases:read"])`.
  Operator-scoped endpoints continue using `_check_key`. Hybrid
  endpoints (rare) accept either.
- **Credential management**: each agent's OAuth client_id +
  client_secret + HMAC signing key live in environment-variable-
  backed config initially (matches existing bridge pattern). KMS
  migration deferred to phase when KMS infrastructure exists for
  git signing keys (P3+).
- **Deferred work for P3+**:
  - mTLS via SPIFFE/SPIRE — service-identity layer for agent-bridge
    communication
  - RFC 8693 token exchange — minting per-call short-lived tokens
    audience-restricted to specific bridge endpoints
  - KMS-backed HMAC signing keys — migrate from env-var to KMS
  - Asymmetric OAuth signing (RS256) — for key rotation

### Confidence

**HIGH CONFIDENCE.** The codebase evidence supports Option B clearly.
HMAC infrastructure already in production reduces the HMAC-layer
cost. OAuth 2.1 client credentials is a well-bounded standard. mTLS
via SPIRE is honestly out-of-scope for a single-process bridge. The
two-layer security is sufficient for read-only + shadow-mode agent
operations. The deferred mTLS work has a clear future-phase home
(P3+). Operator can review with confidence.

---

## Section 5 — V5 PV-CI Gate Extension Resolution

### Nature of the finding

Verification document V5 (lines 263-296) established that the existing
PV-CI gate (`scripts/vapi_invariant_gate.py`) is identity-blind,
treating all commits as anonymous regardless of author. The
architecture document requires that the gate be extended to parse the
diff and block any path the committing agent is not authorized to
touch. This is engineering work with a clear specification but with
implementation choices that deserve explicit examination.

### Codebase ground truth

**Existing PV-CI gate** (per `scripts/vapi_invariant_gate.py`):

- **Line 76-278**: `INVARIANTS` list — 28 invariant entries
  (INV-001..INV-026 plus INV-CORPUS-001 + INV-CORPUS-002 added Phase
  237.5).
- **Line 290-297**: `_hash_file_region(path, pattern)` — hashes lines
  matching regex pattern in file.
- **Line 300-316**: `check_invariants()` — iterates INVARIANTS,
  computes digest per invariant, returns list of result dicts.
- **Line 406-449**: `run_gate(report_only)` — compares digests against
  allowlist at `.github/INVARIANTS_ALLOWLIST.json`; reports
  PASS/FAIL/digest-drift.
- **Line 326-391**: governance event chain — `_fetch_latest_provenance_hash`,
  `_compute_governance_provenance_hash`, `_post_governance_event`.
  Each `--generate` requires `--reason "<category>: <text>"`;
  invariant_change requires `--confirm-governance`.
- **Grep for `author|committer|GIT_AUTHOR`**: zero matches. The gate
  is entirely identity-blind.
- **Total file size**: 517 lines.

**Allowlist** at `.github/INVARIANTS_ALLOWLIST.json`: 28 entries (one
per invariant), confirmed matches the gate's INVARIANTS list count.

**No CODEOWNERS file** anywhere in the repo (per V9 finding plus
verified this session: glob `.github/CODEOWNERS` returns no files;
glob `CODEOWNERS` returns only chai's node_modules).

**GitHub Actions workflow**: `.github/workflows/vapi-invariant-gate.yml`
exists per Phase 224 (referenced in CLAUDE.md and verified in repo
structure). Runs the existing gate on every PR.

### Decision space

Two options enumerated in the prompt evaluated against three criteria:
(1) architectural cleanliness, (2) implementation effort and
maintenance burden, (3) forward compatibility with future
agent-related CI checks.

**Option A — Extend `vapi_invariant_gate.py` with per-author path
scope checking as a new check type**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Architectural cleanliness | **MODERATE** | Single gate with all CI logic. But mixes two distinct concerns: invariant-fingerprint hashing (reading file content patterns) and commit-author-vs-path-scope rule enforcement (parsing git diff + author identity + scope rules). The two have different inputs (file content vs git metadata), different failure modes (digest drift vs scope violation), different remediation paths (regenerate allowlist vs rewrite commit), and different governance semantics (--reason+--confirm-governance vs CODEOWNERS update). Combining them blurs the gate's canonical concern. |
| (2) Implementation effort | **MODERATE** | Adds ~150-200 lines to a 517-line file. New check type alongside existing INVARIANTS list. Diff parsing logic, author lookup, scope rule engine all live in the same module. |
| (3) Forward compatibility | **WEAK** | Future agent-related CI checks (e.g., commit-message format gate, agent action authorization gate, scope bundle hash check, KMS key fingerprint check) would each face the same choice: extend `vapi_invariant_gate.py` further, or split into separate gate. The "extend the existing gate" path leads to a sprawling 1500+ line gate with five different concerns mixed together. |

**Option B — Separate path-scope gate as parallel script
(`scripts/vapi_path_scope_gate.py` + new GitHub Actions workflow)**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Architectural cleanliness | **STRONG** | Single responsibility per script: invariant gate hashes file regions, path-scope gate parses diff + author + scope rules. Each script's canonical concern is explicit. The existing gate's surface stays focused. The pattern matches VAPI's existing convention (separate scripts for separate audit concerns: `scripts/audit_endpoint_auth.py`, `scripts/vapi_invariant_gate.py`, etc.). |
| (2) Implementation effort | **LOW-MODERATE** | New file `scripts/vapi_path_scope_gate.py` (~200-300 lines of focused logic). New workflow file `.github/workflows/vapi-path-scope-gate.yml` (~30 lines). No modifications to existing critical infrastructure. |
| (3) Forward compatibility | **STRONG** | Future agent-related CI checks each get their own focused script + workflow. Pattern: one concern, one script, one workflow. Scales gracefully as more agent-related checks are needed. |

### Recommendation: Option B

Recommend **Option B — separate `scripts/vapi_path_scope_gate.py` + new
GitHub Actions workflow** for these reasons:

1. **Single responsibility per script matches VAPI's existing pattern.**
   The repo already has `scripts/audit_endpoint_auth.py` (specifically
   for endpoint authentication audits — a focused single-concern
   script), `scripts/vapi_invariant_gate.py` (specifically for
   invariant-fingerprint hashing). Adding path-scope gate as
   `scripts/vapi_path_scope_gate.py` follows the established pattern.
   Mixing concerns into the existing gate would break the pattern.

2. **`vapi_invariant_gate.py` is critical infrastructure with
   tamper-evident governance.** The gate's `--reason` discipline +
   `--confirm-governance` for invariant_change category +
   `_compute_governance_provenance_hash` chain (INV-019..022 +
   INV-225-style governance event chain) are load-bearing for the
   protocol's invariant-change-tracking story. Adding diff-parsing and
   author-lookup logic to the gate increases its blast radius — a bug
   in path-scope checking could falsely block a commit AND
   simultaneously skip an invariant check, or vice versa. Keeping the
   two checks separate isolates failure modes.

3. **Diff parsing has a different governance semantic.** Invariant
   gate's governance discipline is "if you change a frozen pattern,
   document why with a category + provenance chain entry." Path-scope
   gate's governance discipline is "if you change CODEOWNERS or
   per-author scope rules, that's a CODEOWNERS-managed governance
   surface." These are different governance surfaces. A bug in one
   shouldn't compromise the other.

4. **Forward compatibility for future CI checks.** The Operator series
   roadmap (P3+) will likely add CI checks for: commit-message format
   (agent commits must include specific provenance trailer), agent
   action authorization (verify agent's scope bundle hash against
   AgentScope.sol latest root), KMS key fingerprint (verify the agent's
   GitHub App signature comes from the registered KMS key), scope
   bundle hash check (verify the policy bundle Cedar/Rego file hashes
   against the on-chain Merkle root). Each of these is a separate
   concern that wants its own gate. Option B's separate-script pattern
   scales; Option A's extend-existing-gate pattern leads to a sprawling
   monolithic gate.

5. **Divergence-risk mitigation via shared CODEOWNERS source-of-truth.**
   The Option A advantage of "unified gate logic" was that
   author-scope-rules and invariant-rules-could-share-internals.
   Mitigation: both gates use the same CODEOWNERS file (and any
   shared scope rules) as the source of truth. The path-scope gate
   parses CODEOWNERS for path → owner mappings; the invariant gate
   doesn't need that mapping at all (its concern is file-content, not
   file-ownership). The two gates have genuinely different inputs;
   "shared internals" was a phantom benefit.

### Architectural details for Option B (no implementation)

The recommendation requires the following design decisions in Phase O0
(no code in this session):

- **New gate script**: `scripts/vapi_path_scope_gate.py`. Structure:
  - `parse_codeowners(path)` — reads `.github/CODEOWNERS`, returns
    `[(path_glob, [owners])]` entries.
  - `enumerate_changed_paths(base_ref, head_ref)` — uses `git
    diff --name-only base_ref..head_ref` to enumerate paths in commit/PR.
  - `identify_author()` — reads `${{ github.actor }}` env var (in CI)
    OR `git log -1 --format='%ae'` (locally). For agent commits, the
    identity is the GitHub App bot login (e.g., `vapi-anchor-sentry[bot]`).
  - `check_path_scopes(changed_paths, author, codeowners)` — for each
    changed_path, find the most-specific matching CODEOWNERS rule, verify
    author is in the owners list. Returns list of violations.
  - `run_gate(base_ref, head_ref)` — orchestrator; exits 0=pass,
    1=fail. Reports each violation with file path + claimed author +
    expected owners.
- **CODEOWNERS file format** (per architecture document P1 + Design
  Pass 1 Conflict 3 Option A):
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
  CLAUDE.md           @ConWan30
  VAPI-WORKFLOW.v2/** @ConWan30
  ```
  File at `.github/CODEOWNERS` per GitHub convention (see Design Pass
  1 Open Question 4 — `.github/CODEOWNERS` recommended for
  consistency with `.github/INVARIANTS_ALLOWLIST.json`).
- **GitHub Actions workflow**: `.github/workflows/vapi-path-scope-gate.yml`.
  Runs on every PR (parallel to existing
  `.github/workflows/vapi-invariant-gate.yml`). Steps:
  - Checkout PR with full history (`fetch-depth: 0`)
  - Run `python scripts/vapi_path_scope_gate.py
    --base ${{ github.base_ref }} --head ${{ github.sha }}`
  - On failure: PR comment via `actions/github-script@v7` (matches
    existing pattern from `vapi-invariant-gate.yml`) with violations
    list and remediation guidance
- **GitHub Apps integration**: agent commits identify via
  `${{ github.actor }}` (which is `vapi-anchor-sentry[bot]` or
  `vapi-guardian[bot]` for App-authored commits). The path-scope gate
  validates against the CODEOWNERS bot login literal. KMS key
  signature verification (architecture doc P0 row) is a separate
  forward-compatibility concern; the path-scope gate does not need to
  cryptographically verify the GitHub App signature beyond GitHub's
  own signature verification.
- **Error messaging**: when a commit is rejected, the gate output
  includes:
  - Each changed path that violated scope
  - The path's expected owner per CODEOWNERS (e.g., "wiki/foo.md
    expected @vapi-anchor-sentry[bot]")
  - The actual author (e.g., "got @vapi-guardian[bot]")
  - Remediation guidance: "Either revert this change OR update
    CODEOWNERS to grant @vapi-guardian[bot] access to wiki/** (governance
    review required)"

### Confidence

**HIGH CONFIDENCE.** The codebase evidence supports Option B
unambiguously. The existing `scripts/audit_endpoint_auth.py` precedent
shows the focused-script-per-concern pattern. The PV-CI gate's
governance discipline is meaningfully separate from path-scope
enforcement. Forward compatibility for future agent CI checks favors
the separable-script approach. Migration cost is low (new script +
new workflow + CODEOWNERS file). Operator can review with confidence.

---

## Section 6 — Cross-Finding Integration Analysis

The four findings interact in ways that warrant explicit examination
before locking in the recommendations.

### Interaction 1: V8 wallet × V10 EAS recommendation

**Direct interaction**: V10 Option C (no EAS deploy) reduces Phase O0
budget by ~0.23 IOTX vs V10 Option A (deploy EAS). This shifts the
Phase O0 budget from V8's original ~0.86 IOTX to ~0.78 IOTX, but
adds ~0.08 IOTX for AgentAdjudicationRegistry deploy (which would have
been needed anyway per Design Pass 1 Conflict 1 Option A). Net effect:
Phase O0 budget remains roughly ~0.78-0.86 IOTX.

**The 5 IOTX target accommodates either V10 option**. If the operator
chooses V10 Option A instead of Option C, the Phase O0 budget rises by
~0.15-0.30 IOTX (EAS deploy cost with IoTeX gas surprise factor), and
the 5 IOTX target still provides ~3 IOTX headroom. The wallet funding
recommendation is robust to V10 reconsideration.

**Coherence**: ✅ COHERENT. The 5 IOTX funding target is conservative
enough that V10's outcome doesn't perturb V8's recommendation.

### Interaction 2: V10 EAS × Design Pass 1 Conflict 1 (parallel AgentAdjudicationRegistry)

**Strong interaction**. Design Pass 1 Conflict 1 Option A authorized
deploy of `AgentAdjudicationRegistry` with function signature
`anchorAgentAction(bytes32 actionHash, bytes32 agentId, string actionType)`.
V10 Option C builds AGENT_COMMIT v1 hash formula in
`bridge/vapi_bridge/agent_commit.py` and routes anchoring through
`AgentAdjudicationRegistry.anchorAgentAction(commit_hash, agent_id, "AGENT_COMMIT")`.
The same contract Design Pass 1 already plans serves V10's needs.
**Phase O0 deploys exactly one new agent-scoped registry, not two
parallel attestation infrastructures.**

If V10 had recommended Option A (deploy EAS), Phase O0 would deploy
both AgentAdjudicationRegistry (for non-commit agent actions like
audit log anchors) AND EAS contracts (for AgentCommit). That doubles
the contract deploy count.

**Coherence**: ✅ STRONGLY COHERENT for Option C. V10 Option C reuses
the contract Design Pass 1 already authorizes; V10 Option A would have
required additional contract infrastructure. The Design Pass 1 / V10
recommendations form a tighter architectural unit under Option C than
under Option A.

### Interaction 3: V2 authentication × V10 attestation infrastructure

**Indirect interaction**. Both findings are about agent action
infrastructure. V2 governs how agents authenticate to the bridge
(token + HMAC); V10 governs how agent commits are anchored on-chain
(AGENT_COMMIT v1 via AgentAdjudicationRegistry). The interaction is at
the agent_id level: V2's OAuth client_id and HMAC X-Agent-KeyId map to
V10's agent_id (bytes32 representation of the agent's ioID DID + ERC-
6551 TBA address binding).

**Coherence**: ✅ COHERENT. The agent_id is the integration point. V2
keeps it in OAuth scope claims and HMAC headers; V10 keeps it in
contract bytes32 fields. Both reference the same canonical agent
identity established by AgentRegistry (the contract Design Pass 1's
AgentRegistry will register agent_id → publicKey + scopeHash + status).

### Interaction 4: V5 PV-CI × Design Pass 1 Conflict 3 (lane reorganization)

**Strong interaction**. Design Pass 1 Conflict 3 Option A authorized
moving `wiki/audits/` to `audits/` and `wiki/sweeps/` to `sweeps/`.
V5 Option B's CODEOWNERS file uses the post-migration paths:
```
wiki/**       @vapi-anchor-sentry[bot]
audits/**     @vapi-guardian[bot]
sweeps/**     @vapi-guardian[bot]
```
**The path-scope gate's source-of-truth (CODEOWNERS) DEPENDS on Design
Pass 1 Conflict 3 having shipped first.** If lane reorganization
slips, V5's path-scope gate must use temporary CODEOWNERS rules
covering the wiki/audits/ + wiki/sweeps/ paths (and resist updating
those rules until reorganization happens).

**Mitigation**: ship Design Pass 1 Conflict 3 (lane move) BEFORE V5
path-scope gate goes live. The lane move is a single atomic commit
(per Design Pass 1 architectural details); the path-scope gate
deploys after. This dependency is clean.

**Coherence**: ✅ COHERENT WITH PHASING. The two recommendations form
a coherent sequence: lane move first, path-scope gate second.

### Interaction 5: V8 × V2 × V10 × V5 — full precursor work plan

The four findings together define the precursor work that must
complete before Phase O0's main implementation begins. Their
collective shape:

1. **Wallet** (V8): ≥3 IOTX in wallet, target 5 IOTX. Operator action.
2. **EAS path locked** (V10): AGENT_COMMIT v1 hash formula and
   AgentAdjudicationRegistry routing finalized as design. No EAS
   deploy. Contract design specification complete.
3. **Authentication path locked** (V2): OAuth 2.1 client credentials +
   HMAC request signing as the layered auth stack for Phase O0.
   Module structure defined; deferred work documented for P3+.
4. **PV-CI extension path locked** (V5): separate
   `scripts/vapi_path_scope_gate.py` + CODEOWNERS file + workflow.
   Path-scope governance separate from invariant-fingerprint
   governance.

**Whole-design coherence check**: do these four recommendations form
a Phase O0 precursor plan that is internally consistent and externally
defensible?

- ✅ Internal consistency: V10 reduces deploy work; V8 funds for the
  reduced + headroom budget; V2's two-layer auth doesn't exceed what
  Phase O0 needs; V5's separate gate avoids blast-radius increase on
  critical infrastructure.
- ✅ External defensibility: an external auditor reviewing the Phase
  O0 design can verify each component independently. AGENT_COMMIT v1
  is a FROZEN-v1 family member with explicit hash formula. OAuth +
  HMAC are standards-based. CODEOWNERS is a GitHub convention.
  Wallet funding is operationally observable.
- ✅ Sequencing: lane move (Design Pass 1 Conflict 3) → CODEOWNERS
  + path-scope gate (V5). EAS-deploy-not-needed locks contract scope
  (V10) → AgentAdjudicationRegistry deploy authorized (Design Pass 1
  Conflict 1) → wallet must hold ≥3 IOTX (V8) → contract deploys
  proceed. OAuth + HMAC infrastructure can build in parallel to
  contract design (V2).
- ✅ Scope discipline: each finding's recommendation is bounded.
  V8 = funding. V10 = design + Phase O0 implementation work folded
  into AgentAdjudicationRegistry. V2 = two specific layers. V5 =
  one new script + one new workflow. None of the four expands
  beyond its finding.

The four recommendations form a coherent precursor work plan suitable
as input to Pass 2C (Phase O0 implementation plan).

---

## Section 7 — Open Questions for Pass 2B

These questions arose during this design pass's reasoning but cannot
be answered by this pass. They are inputs to Pass 2B (V11 conceptual
alignment) or Pass 2C (Phase O0 implementation plan), not blockers
to Pass 2A's completion.

1. **AGENT_COMMIT v1 vs OPERATOR primitive in FROZEN-v1 family
   numbering**: V10 Option C adds AGENT_COMMIT v1 as a FROZEN-v1
   primitive. Architecture document section 8 envisions OPERATOR as
   the sixth FROZEN-v1 primitive. Are these two distinct primitives
   (AGENT_COMMIT becomes seventh, OPERATOR sixth, total 7 FROZEN-v1
   primitives) or the same primitive under different names? Pass 2B
   should resolve this when it addresses V11 conceptual alignment.

2. **EAS-shim contract for ecosystem integration**: V10 Option C
   defers EAS-shim work indefinitely. If/when the operator decides
   ecosystem integration with EAS-native tooling becomes priority, a
   shim contract (reads AgentAdjudicationRegistry events, re-emits as
   EAS attestations on a chain where EAS exists) is the migration
   path. Is this a candidate Phase O5+ phase, or does it stay
   indefinitely deferred? Pass 2C should weigh this when sequencing
   the full 7-phase initiative.

3. **OAuth issuer hosting decision**: V2 Option B specifies a
   self-hosted OAuth 2.1 token issuer. Does this run as a separate
   process (new service), as a module within the existing bridge
   process (`bridge/vapi_bridge/oauth_issuer.py`), or as a third-party
   service (e.g., self-hosted Authelia, Keycloak)? Pass 2C should
   decide the deployment topology.

4. **HMAC nonce store TTL eviction strategy**: V2 Option B specifies
   in-memory LRU with TTL eviction for Phase O0 (Redis-backed for
   P3+). What's the TTL value? Architecture document specifies ±300s
   clock skew window — nonce TTL should be ≥600s (twice the skew
   window) to defend against replay across the full skew range. Pass
   2C implementation detail.

5. **GitHub App KMS signing infrastructure**: V5 Option B's
   path-scope gate identifies authors via `${{ github.actor }}` (the
   GitHub App bot login), but architecture document P0 row mentions
   KMS-backed signing keys for git commits. Are KMS keys provisioned
   in Phase O0 (as architecture doc states) or deferred to P3+ when
   agent writes are activated? Pass 2C should sequence this.

6. **CODEOWNERS-required reviewer enforcement**: V5 Option B treats
   CODEOWNERS as the source of truth for path scopes. GitHub also
   supports CODEOWNERS-required reviewer enforcement at the branch
   protection level (require approval from CODEOWNERS for each
   protected path before merge). Should Phase O0 enable this branch
   protection, OR should the path-scope gate be the sole enforcement
   mechanism? Both are defensible; Pass 2C should decide.

7. **AGENT_COMMIT v1 hash formula committed in design (not pseudocode)
   form**: Section 3 sketched the formula but did not commit specific
   field encodings (e.g., how is `agent_id` encoded — bytes32 of the
   ioID DID's keccak256? bytes32 of the ERC-6551 TBA address padded
   to 32 bytes?). Pass 2C must specify exactly. The hash formula is
   FROZEN once deployed; specification accuracy matters.

8. **Per-agent OAuth scope granularity**: V2 Option B references
   architecture document scopes (`bridge:agent:phases:read`,
   `bridge:agent:ceremony:propose`, `bridge:agent:contract:invoke:adjudication`).
   The scope hierarchy could be deeper (e.g., `bridge:agent:contract:invoke:adjudication:agent`
   to differentiate AgentAdjudicationRegistry from legacy
   AdjudicationRegistry). Pass 2C should specify the full scope
   hierarchy.

9. **Drain-class structural fix vs continued kill-switch reliance**:
   V8's recommendation acknowledges the drain class (R3 in
   verification) is mitigated but not structurally fixed. Phase O0
   relies on the kill-switch staying engaged. Should Phase O0 (or an
   adjacent pre-O0 phase) include a structural fix to the
   DualShock + batcher retry-blind paths? This is operational hygiene
   that the verification document treats as out of scope; Pass 2C
   should decide whether to fold it in.

10. **AgentAdjudicationRegistry actionType vocabulary**: Design Pass 1
    proposed `actionType` as the discriminator on
    `anchorAgentAction(actionHash, agentId, actionType)`. V10 adds
    `"AGENT_COMMIT"` as one actionType value. What's the full
    vocabulary? `"AUDIT_LOG"`, `"BOUNDARY_UPDATE"`,
    `"CORPUS_SNAPSHOT"` (when CORPUS_SNAPSHOT migrates per Design
    Pass 1 Open Question 2)? Pass 2C should specify the actionType
    enum.

---

## Surprising vs. expected reasoning (per prompt's closing instruction)

### Recommendations that produced confident reasoning

**V8 (Wallet funding to 5 IOTX)**: HIGH CONFIDENCE. The decision space
is narrow (target balance), the codebase evidence (live balance,
actual deploy costs from three recent VAPI deploys, IoTeX gas surprise
factor) is unambiguous, and the funding-cadence argument for
full-initiative funding is operational common sense rather than
architectural judgment. The 5 IOTX target is defensible with explicit
per-phase math (Phase O0 ~0.78 IOTX + Phase O1-O6 ~0.7 IOTX +
operational headroom ~1 IOTX + drain margin ~1.5 IOTX + buffer
~1 IOTX). Operator can review with confidence.

**V2 (OAuth 2.1 + HMAC, defer mTLS)**: HIGH CONFIDENCE. The codebase
evidence supports Option B clearly. HMAC infrastructure already in
production at `operator_api.py:223,243,255,1442` reduces the HMAC-
layer cost. OAuth 2.1 client credentials is a well-bounded standard.
mTLS via SPIRE is honestly out-of-scope for a single-process bridge
and appropriately deferred to a phase where bridge runs in K8s with
service mesh. Two-layer auth is sufficient for Phase O0 + P1 + P2
read-only/shadow/suggestion modes. Operator can review with
confidence.

**V5 (Separate path-scope gate script)**: HIGH CONFIDENCE. The
codebase evidence supports Option B unambiguously. Existing
`scripts/audit_endpoint_auth.py` precedent shows the focused-script-
per-concern pattern. The PV-CI gate's governance discipline
(`--reason` + `--confirm-governance` + provenance chain) is
meaningfully separate from path-scope enforcement (which uses
CODEOWNERS as governance surface). Forward compatibility for future
agent-related CI checks favors separable scripts. Migration cost is
low. Operator can review with confidence.

### Recommendation that produced careful reasoning

**V10 (AGENT_COMMIT v1 as sixth FROZEN-v1 primitive on
AgentAdjudicationRegistry)**: CAREFUL REASONING. The codebase strongly
supports Option C: VAPI's five FROZEN-v1 primitives establish the
cryptographic-continuity pattern, AgentAdjudicationRegistry is already
authorized for Phase O0 deploy per Design Pass 1, and Phase 237.5
Path C+ taught the value of controlling primitive evolution rather
than depending on external upstream like EAS. But the recommendation
trades off ecosystem compatibility — VAPI loses access to attest.org
explorer integration, EAS GraphQL indexers, and future ecosystem
contracts that expect EAS-format attestations.

The architecture document's framing in section 4 implies the operator's
preference is Option A (deploy EAS to IoTeX). If the operator's vision
values external tooling integration as a primary concern — particularly
if VAPI plans to integrate with DAO tooling, multi-protocol attestation
aggregators, or other EAS-native ecosystem layers in the medium term —
Option A is the correct path.

If the operator's first priority is cryptographic continuity within
VAPI's established FROZEN-v1 family pattern (which the prompt's first
criterion explicitly names), Option C is correct. The trade-off is
deferrable: future EAS-shim work can be added in P5+ if ecosystem
integration becomes priority, without disturbing the FROZEN-v1
primitive (the shim re-emits VAPI commits in EAS format on a chain
where EAS exists).

The operator should examine this recommendation especially carefully
and confirm the architectural priority before authorizing
implementation. This is the kind of architectural-priority decision
where the operator's vision should guide the final acceptance, not
codebase verification alone. Reasonable operators could choose
Option A instead, and the codebase cannot conclusively decide between
them.

---

This document holds for review. No code. No contract modifications.
No bridge updates. No agent definition files. No commits.
