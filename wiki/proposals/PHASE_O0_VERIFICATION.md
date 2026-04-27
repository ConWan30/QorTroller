# Phase O0 — Pre-Design Verification (Operator Series Inaugural)

**Status**: HOLD FOR REVIEW. No design proposal. No agent definition files. No
contracts. No commits. Verification standard from Phase 237.5 / Phase 238 /
Phase 237-ZK-SEPPROOF applied: every architectural claim cites file:line or
external-source verification (eth_getCode RPC, npm/PyPI registry, attest.org
docs, eas-contracts GitHub).

**Architecture document under verification**: `VAPI Operator Agents:
Architecting the First Non-Human Protocol Stewards on IoTeX.pdf` (974 KB,
13 pages, dated 2026-04-26, located in operator's Downloads folder; the
referenced path `wiki/proposals/VAPI_OPERATOR_AGENTS_ARCHITECTURE.md` does
not exist in repo or Downloads — PDF is the canonical artifact).

**Date**: 2026-04-26

---

## Section 1 — Question-by-Question Answers (V1–V11)

### V1 — Existing VAPI contract architecture compatibility

**`AdjudicationRegistry.sol`** (`contracts/contracts/AdjudicationRegistry.sol`):

The proposed `requireAgentScope(agentId, action)` modifier is **not directly
compatible** with the current contract code without modification. Every
mutating function uses `onlyOwner` access control:

- `recordAdjudication(...)` at line 53-69: `external onlyOwner`
- `anchorAdjudication(bytes32, string)` at line 79-84: `external onlyOwner`
- `anchorAdjudication(bytes32)` at line 87-89: `external onlyOwner`
- Internal `_anchorAdjudication(bytes32, string)` at line 92-99 has no
  agent-aware logic.

Adding `requireAgentScope` requires either (a) replacing `onlyOwner` with the
new modifier, or (b) layering both — but (b) would still require the contract
to import an `AgentRegistry` interface and look up `agentId → scope` at
call time, which is a contract-source change.

**Critical Phase 237.5 finding still applies**: per the deployed-bytecode
verification done in commit `f9c6ec11`, the contract DEPLOYED at
`0x44CF981f46a52ADE56476Ce894255954a7776fb4` is the **Phase 111 original**
(selector `0x5fa83f4b` for `recordAdjudication` only). The VAPI-EXT
extensions (`anchorAdjudication` overloads at selectors `0xae7cd267` and
`0x79dcce3f`) are in source but NOT in deployed bytecode. So the proposed
extension to add `requireAgentScope` would require redeploying the contract,
not just modifying source. This is a real Phase O0 prerequisite.

**`VAPIBiometricGovernance.sol`** (`contracts/contracts/VAPIBiometricGovernance.sol`):

The architecture document proposes a "sibling AgentRegistry contract to
VAPIBiometricGovernance." Current BBG structure at lines 30-127 is
self-contained and **does not block sibling-contract registration patterns**.
BBG's surface (lines 86-114, `proposeWithVHP(proposalHash, vhpTokenId)`)
operates only on human-owned VHP soulbound tokens; AgentRegistry would be a
parallel contract with `(agentId → publicKey + scopeHash + status)` mapping
per architecture document section 4. **Compatible without BBG modification**.
What's needed: deployment of the new sibling contract; no changes to BBG
itself.

**`ProtocolCoherenceRegistry.sol`** (`contracts/contracts/ProtocolCoherenceRegistry.sol`):

The architecture document proposes adding "an invariant that no agent can
mutate any of the 28 frozen invariants" to PCR. PCR's current schema
(`CoherenceAnchor` struct, lines 29-35) anchors `(merkleRoot, agentCount,
tsNs, anchoredAt, governanceProvenanceHash)`. There is no direct hook for
agent-mutation prohibition; this would need to be enforced at the
**off-chain bridge layer** OR via a new on-chain enforcement contract that
reads PCR state. The architecture's claim that "no agent can mutate any of
the 28 frozen invariants" is more naturally enforced at the **PV-CI gate
layer** (see V5) than at PCR. Surface as design-phase question: is "encoded
in ProtocolCoherenceRegistry as a contract-level invariant" a literal claim
about new contract logic, or a claim about runtime enforcement that PCR's
existing surface anchors after-the-fact?

**`VAPIConsentRegistry.sol`** (`contracts/contracts/VAPIConsentRegistry.sol`):

The architecture document proposes "extending consent records to capture the
agent identity that performed the action." Current `ConsentRecord` struct at
lines 43-49 has no `agentId` field. The proposed extension requires:

1. Schema change: add `bytes32 agentId` (or similar) to `ConsentRecord`
2. Function signature change: `grantConsent(uint8 category, uint64 expiresAt,
   bytes32 consentHash)` at line 106-128 must accept agentId or derive it
3. **FROZEN-v1 hash formula conflict**: the architecture document calls this
   "the natural extension of the CONSENT FROZEN-v1 primitive to non-human
   consenters." But CONSENT FROZEN v1 is in `bridge/vapi_bridge/consent_categories.py`
   and the formula `compute_consent_hash` is **explicitly frozen** (per
   CLAUDE.md "Hard Rules" section). Extending the on-chain record without
   extending the off-chain hash formula creates an inconsistency.

**Open question for design phase**: does extending `ConsentRecord` to capture
`agentId` constitute a CONSENT v2 (requires new domain tag
`b"VAPI-CONSENT-v2"` + parallel pillar) or can the agentId be carried as
metadata that's NOT part of the FROZEN-v1 commitment? The architecture
document does not resolve this.

**`CeremonyAuditRegistry.sol`** (`contracts/contracts/CeremonyAuditRegistry.sol`):

CeremonyAuditRegistry is **not in the architecture document's proposed
extension list**. It is a Phase 179 ZK ceremony multi-party audit gate
(struct at lines 20-26 stores ceremony participants per circuit). No
proposed Phase O0 changes here. Marked compatible-by-omission.

---

### V2 — Bridge endpoint authentication compatibility

Existing patterns at `bridge/vapi_bridge/operator_api.py:219-250`:

```python
def _check_key(api_key: str) -> None:
    """Raise HTTP 503/403 if key is missing or wrong."""
    if not cfg.operator_api_key:
        raise HTTPException(503, "Operator API not configured...")
    if not hmac.compare_digest(api_key, cfg.operator_api_key):
        raise HTTPException(403, "Invalid API key")

def _check_read_key(x_api_key: str) -> None:
    """Phase 224 W1 fix: for read-only /agent/* status endpoints..."""
    if cfg.operator_api_key:
        if not hmac.compare_digest(x_api_key, cfg.operator_api_key):
            raise HTTPException(403, "Invalid x-api-key header")
    if not _limiter.is_allowed(x_api_key):
        raise HTTPException(...)
```

**Single shared-secret model.** Both `_check_key` and `_check_read_key`
compare the request-supplied key against a single `cfg.operator_api_key`
value. There is **no concept of per-caller identity**. Rate limiting at
`_check_rate` (line 226-233) keys on the api_key string itself — but since
all callers pass the same key, the rate limit is effectively
identity-blind.

The architecture document specifies a layered authentication stack (page 7):

1. **OAuth 2.1 client credentials** with fine-grained scopes
   (`bridge:agent:phases:read`, `bridge:agent:ceremony:propose`,
   `bridge:agent:contract:invoke:adjudication`), with RFC 8693 token
   exchange to mint per-call short-lived tokens (60-300s TTL,
   audience-restricted)
2. **HMAC request signing** layered on top — canonical string
   `METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(body)` signed with HMAC-SHA-256,
   headers `X-Agent-KeyId`, `X-Timestamp`, `X-Nonce`, `X-Signature`,
   server enforces ±300s clock skew with Redis-backed nonce dedup
3. **mTLS via SPIFFE/SPIRE** for service-to-service

**Verification finding**: the existing `_check_key` / `_check_read_key`
patterns **cannot be extended** to the layered stack because:

- They have no notion of caller identity (just a shared secret)
- They have no notion of scopes (the same key authorizes everything)
- They have no nonce-dedup, no timestamp enforcement, no replay protection
- They have no mTLS or service-identity infrastructure

A **parallel authentication path** must be built. Bridge endpoints would
need a 2-tier auth pattern: existing operator-key path (current 154+
endpoints) coexisting with a new agent-token path (Phase O0+ endpoints
exposed to Sentry/Guardian). This is not a small extension. It involves:

- Token issuance service (OAuth 2.1 authorization server or self-hosted
  short-lived JWT minter)
- HMAC verification middleware with nonce store (Redis or in-memory with
  TTL eviction)
- SPIFFE Workload API integration via SPIRE agent on bridge host
- New `_check_agent_token(...)` function alongside `_check_key`
- Per-endpoint annotation deciding which path applies

---

### V3 — IoTeX testnet contract address verification

Live `eth_getCode` calls against `https://babel-api.testnet.iotex.io`
performed this session. All four addresses from architecture document
section 2 verified:

| Address | Description | bytecode chars | Has code? |
|---|---|---|---|
| `0x060581AA1A4e0cC92FBd74d251913238De2F13cd` | ProjectRegistry | 2320 | ✅ YES |
| `0x0A7e595C7889dF3652A19aF52C18377bF17e027D` | ioIDRegistry | 2320 | ✅ YES |
| `0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7` | ioID NFT | 2320 | ✅ YES |
| `0x000000006551c19487814612e58FE06813775758` | ERC-6551 Registry | 1144 | ✅ YES |

The first three return identical-length bytecode (2320 chars / ~1160 bytes),
consistent with proxy or template-deployed contracts. The ERC-6551 Registry
returns shorter bytecode (1144 chars / ~572 bytes), consistent with the
known ERC-6551 singleton's CREATE2 wrapper pattern.

**All four addresses verify successfully.** Phase O0 ioID DID minting and
ERC-6551 TBA binding can proceed against these confirmed-deployed contracts
without prerequisite work on the IoTeX side.

---

### V4 — Wiki engine and provenance infrastructure

Current wiki engine at `vapi_wiki_engine.py:872-902` (`cmd_snapshot`):

```python
def cmd_snapshot(anchor: bool = False):
    h       = wiki_hash()
    ts      = datetime.now(timezone.utc).isoformat()
    n_pages = len(list(WIKI.rglob("*.md"))) if WIKI.exists() else 0
    ...
    if anchor:
        anchor_status = _anchor_on_chain(h, ts, phase)
```

Current anchoring at `vapi_wiki_engine.py:904-935` (`_anchor_on_chain`):

```python
def _anchor_on_chain(h: str, ts: str, phase: int) -> str:
    """POSTs wiki snapshot hash to bridge /agent/anchor-wiki-snapshot.
    Bridge writes to AdjudicationRegistry.sol (already deployed at
    0x44CF981f46a52ADE56476Ce894255954a7776fb4).
    Same contract as PoAd hash anchoring — no new contracts needed."""
```

**Each snapshot is independently anchored.** No `refUID` linking between
consecutive snapshots. No attestation-chain semantics. The current model is
"each call produces a new hash; each hash anchored separately."

The proposed AgentCommit attestation chain pattern (architecture doc section 4):

```
AgentCommit: (commitSha, repoUri, agentId, prevCommitAttestUid,
              timestamp, agentSig)
```

with each attestation `refUID`-ing the previous one. **This pattern is NEW
infrastructure** that doesn't exist in the current wiki engine. Specifically
needed:

- EAS contract deployment on IoTeX (V10 finding: not currently deployed)
- New schema registration via SchemaRegistry
- New chain wrapper function `chain.anchor_agent_commit(commit_sha,
  prev_uid, ...)` that calls EAS `attest()` with `refUID = prev_uid`
- Modification of `cmd_snapshot` to thread the previous attestation UID
  through each snapshot

The closest existing pattern in the codebase is the **GIC chain** (Phase 235-A,
`bridge/vapi_bridge/grind_chain.py`) which uses SHA-256 chained hashes with
`prev_gic` as input. This is the conceptual precedent but operates at a
different layer (per-session, off-chain SQLite) than what AgentCommit needs
(per-commit, on-chain EAS).

The **`corpus_snapshot_log`** schema at `bridge/vapi_bridge/store.py:3279-3306`
also doesn't have a `refUID` or `prev_attestation_uid` field. From Phase 236
verification: `tx_hash`, `on_chain_confirmed`, `ipfs_cid` fields exist —
suitable for "this snapshot was anchored at tx X" semantics, NOT suitable
for "this snapshot's attestation references the prior snapshot's
attestation" without schema extension.

**`reactive_adjudication_log`** at `store.py:767-779` and
**`ioswarm_adjudication_log`** at `store.py:1069-1086` exist — the
architecture document refers to "adjudication_log" generically but there's
no plain `adjudication_log` in the schema; the closest concept is
`AdjudicationRegistry.records` mapping on-chain.

---

### V5 — PV-CI gate path-scope by author

Current gate at `scripts/vapi_invariant_gate.py:300-449` is a pure
invariant-pattern checker:

- `check_invariants()` (line 283) iterates the static `INVARIANTS` list
  (28 entries) and hashes file regions matching each invariant's regex
  pattern
- `run_gate(report_only=False)` (line 406) compares hashes against the
  allowlist at `.github/INVARIANTS_ALLOWLIST.json` and reports
  PASS/FAIL/digest-drift
- Grep for `author|committer|GIT_AUTHOR` in the gate script returns
  nothing — **the gate is entirely identity-blind**

**No author awareness, no path-scope checking, no diff parsing.** The
architecture document's requirement that "the PV-CI gate must be extended
to parse the diff and block any path the committing agent is not
authorized to touch" requires substantial new infrastructure:

1. Diff enumeration: `git diff --name-only HEAD~1..HEAD` or PR-based diff
   from GitHub Actions context
2. Author identification: `git log -1 --format='%ae'` or PR author from
   GitHub Actions `${{ github.actor }}`
3. Author-to-scope map: lookup table (likely from CODEOWNERS or
   `.claude/agents/*.yaml` files) mapping commit author identity to
   allowed-path globs
4. Rejection logic: if any changed path is outside author's allowed
   globs → fail gate

This is a **new gate component** (probably `scripts/vapi_path_scope_gate.py`)
that runs alongside the existing invariant gate, OR an extension to
`run_gate()` that conditionally runs path-scope checks when a commit is
detected. The current gate cannot be retrofitted with a one-line change.

---

### V6 — Claude Agent SDK + Claude API integration

**Architecture document version claims** (page 1):
- TypeScript: `@anthropic-ai/claude-agent-sdk` v0.2.119
- Python: `claude-agent-sdk` v0.16.x

**Live registry verification**:

- **TypeScript**: `@anthropic-ai/claude-agent-sdk` v0.2.119 confirmed live on
  npm registry (released 2 days before search). Architecture doc version is
  accurate. ([npm](https://www.npmjs.com/package/@anthropic-ai/claude-agent-sdk))
- **Python**: `claude-agent-sdk` is on PyPI but **the latest version is
  v0.1.68 (released 2026-04-25), not v0.16.x as the architecture document
  claims**. ([PyPI](https://pypi.org/project/claude-agent-sdk/))

**Verification finding**: the Python version in the architecture document is
incorrect. v0.16.x does not currently exist on PyPI. Most likely the document
intended v0.1.x (the actual current pre-1.0 series). This is a documentation
correction the codebase forces; surface as an open question for the design
phase to confirm whether the architecture intends current 0.1.x or a
future-version dependency.

**Bridge integration path**:

- Both SDKs available as installable packages
- Python SDK bundles Claude CLI for tool execution per its v0.1.68 release
  notes
- Architecture document's recommendation of "self-hosted SDK on the bridge
  infrastructure" is feasible
- Existing bridge already imports `anthropic` package per
  `bridge/vapi_bridge/operator_api.py:208-212` (CalibrationIntelligenceAgent
  catches ImportError on `anthropic`). Adding `claude-agent-sdk` is
  additive.

**Process management**: bridge runs as a single Python asyncio process
(`python -m bridge.vapi_bridge.main`). To host two long-lived Operator Agents
in-process, asyncio coroutines could host them — but the architecture's
recommendation of Temporal substrate (page 6) for durable execution
suggests they should run as separate processes. Either pattern is achievable;
the design phase must choose. Bridge process management would change from
single-process to multi-process orchestration.

**Claude API integration architecture (operator-supplied requirement, not
fully addressed in architecture document)**:

The architecture document references the Claude Agent SDK but does not
explicitly detail the Claude API integration architecture as the operator's
prompt requires. Specifically:

- **Anthropic API key provisioning**: the architecture document specifies
  KMS-backed signing keys for git commits (page 7) but does NOT specify
  where Anthropic API keys live. Existing bridge convention (per
  `bridge/.env` pattern) puts API keys as environment variables (e.g., the
  bridge currently has `ANTHROPIC_API_KEY=...` for SessionAdjudicator). For
  the Operator Agents this is insufficient: each agent needs its own API key
  for billing/rate-limit isolation, and the keys should be KMS-managed for
  parity with the git signing keys. This is a Phase O0 concern not
  resolved in the architecture document.

- **Rate limits and concurrency**: Anthropic API rate limits are tier-based
  (TPM/RPM). Two agents polling at independent cadences (e.g., Sentry
  polling every 5 minutes, Guardian on-demand from autoresearch findings)
  must respect organization-wide TPM/RPM headroom. The architecture
  document's "polling agent firing every 5 minutes" estimate (page 1)
  assumes Haiku 4.5 routing for cheap calls, escalating to Sonnet/Opus
  only when reasoning is needed. This is the right pattern but its concrete
  implementation requires per-agent token budgets (the document mentions
  `max_budget_usd` and `task_budget` SDK ceilings at page 1 footer) and
  centralized rate-limit awareness.

- **Model selection per task type**: per architecture page 1:
  - Haiku 4.5 ($1/$5 per 1M tokens) for polling shells
  - Sonnet 4.6 ($3/$15) for routine reasoning
  - Opus 4.7 ($5/$25) for critical decisions

  The Claude Agent SDK supports model selection via `ClaudeAgentOptions`;
  the design phase must specify which task types in each agent map to
  which model. The agent definition file YAML format shown on page 11
  (`model: claude-sonnet-4-6 # Haiku 4.5 for polling shell`) suggests
  per-agent default + per-task override.

- **Cryptographic attestation distinction (CRITICAL HONEST FORMULATION)**:
  The cryptographic claim VAPI makes about its Operator Agents must
  precisely distinguish:
  - **What's attested on IoTeX**: agent identity (DID, ERC-8004 registration,
    soulbound non-transferable token); agent actions (commit signatures
    via GitHub App KMS keys, EAS attestations of `(commitSha, repoUri,
    agentId, prevAttestUid, timestamp, agentSig)`); agent scope and policy
    state (Merkle root in AgentScope.sol); slashing events (AgentSlashing.sol);
    audit log Merkle roots (AuditLog.sol).
  - **What's NOT attested on IoTeX**: the Claude reasoning that produced
    the action. The reasoning itself happens in Anthropic's infrastructure
    (Claude API call → model inference → response). The reasoning trace can
    be hashed and stored alongside the action (per architecture doc page 7
    "Why" logs satisfying W3C PROV-AGENT model), but the inference itself is
    not cryptographically verified. A different model could have produced
    different reasoning; the IoTeX chain proves only that the agent
    identified by its DID/SBT signed and submitted this action at this
    block.

  The honest formulation: **VAPI cryptographically attests that
  identity X took action Y at time T, with reasoning trace hash H. VAPI
  does NOT cryptographically attest that the reasoning was correct, or
  that the model output was H.** This distinction must be explicit in
  any external claim. The architecture document touches this at section
  7 but doesn't make it a foreground guarantee.

  Surface as open question: should the Operator Agent identity SBT
  include a "model class" field (e.g., `claude-sonnet-4-6`) so the
  attestation includes which model produced the reasoning? Anthropic
  doesn't sign individual API responses, so the model claim is
  self-asserted by the agent — but binding it to the SBT prevents an
  agent silently switching to a different model without on-chain trace.

---

### V7 — 38-agent fleet vs Operator agents distinction

Read `VAPI-WORKFLOW.v2/VAPI_AGENTS.md:34-83` (agent table for agents 1-36)
and `bridge/vapi_bridge/fleet_signal_coherence_agent.py:1-50` (FSCA
overview).

The architecture document distinguishes (page 8): "The 38-agent fleet is
bridge-side software; the two new agents are reasoning-side cognition. ...
Anchor Sentry and Guardian don't replace the fleet; they steward it."

**Distinction is architecturally clean.** The existing fleet operates as
mechanical software with hardcoded rules (CONTRADICTION_RULES dict at
fleet_signal_coherence_agent.py:50-471, polling intervals, deterministic
queries). The proposed Operator Agents add reasoning over fleet outputs.

**Multiple complementary overlaps identified**:

| Existing agent | Operator agent | Overlap class |
|---|---|---|
| Agent #18 ACIM (`AgentCalibrationIntegrityMonitor`, runs 16 self-tests every 15 min) | Guardian (operational health) | **Strongly complementary** — ACIM is mechanical cross-validation; Guardian is reasoning-based stewardship over ACIM's findings |
| Agent #35 FSCA (25 contradiction/orphan/inversion rules, polls every 15 min) | Guardian (autoresearch evaluation) | **Strongly complementary** — architecture doc explicitly calls FSCA Guardian's primary input (page 8) |
| Agent #21 FleetConsensusSnapshotAgent (PoFC hash, fleet_consensus_snapshot_log) | Anchor Sentry (provenance) | **Complementary** — fleet snapshots are events Anchor Sentry could anchor as provenance |
| Agent #32 ProtocolIntelligenceRecordAgent (PIR chained hash) | Anchor Sentry | **Complementary** — PIR is similar in shape to AgentCommit chain but different domain (threat forecasts vs commits) |
| Agent #36 CoherenceFingerprintRegistry (persistent contradiction tracking, N_PROMOTE_THRESHOLD=3) | Guardian | **Complementary** |
| Agent #34 CorpusDataCuratorAgent (7-task data coherence, Provenance DAG, Proof-of-Erasure) | Anchor Sentry + Guardian | **Complementary** — provenance work overlaps Sentry; data quality overlaps Guardian |
| Agent #27 ProtocolMaturityScoringAgent (9-component score, ALPHA/BETA/PRODUCTION tiers) | Guardian | **Complementary** — Guardian could use the score as a stewardship signal |

**No conflicting overlaps identified.** All overlaps are either
complementary (the existing agent provides data the Operator Agent reasons
over) or duplicative-but-non-conflicting (similar mechanism, different
domain — e.g., PIR vs AgentCommit chain).

The architecture document's framing — "the operational fleet is mechanical,
the Operator pair is cognitive" — is supported by the codebase. The
existing fleet's CONTRADICTION_RULES patterns (deterministic SQL queries
and threshold checks) are **not generative reasoning**; they are
mechanical detection. The Operator Agents would add the reasoning layer
that interprets fleet findings, drafts PRs, escalates to humans on
boundary violations, and writes provenance commits. The fleet stays in
its lane; the Operator pair adds a new layer.

---

### V8 — Wallet and economic feasibility for Phase O0

**Live wallet balance** (verified this session via
`eth_getBalance` on IoTeX testnet RPC):

```
Wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692: 0.552530 IOTX
```

CLAUDE.md notes the wallet was ~18.5 IOTX as of 2026-04-26, but the
Phase 237.5 Path C+ session burned ~17.95 IOTX through DualShock + batcher
retry-blind paths against the broken IoTeX P256 precompile. Wallet now at
**0.5525 IOTX**. The Path C+ kill-switch (`CHAIN_SUBMISSION_PAUSED=true`
in `bridge/.env`) prevents further drain.

**Phase O0 deploy cost estimate** (per architecture document section 9 P0
exit criteria):

| Contract / action | Estimated IOTX | Source |
|---|---:|---|
| AgentRegistry.sol deploy | ~0.07 | Pattern from VAPIBiometricGovernance Phase 222 (~0.07) |
| AgentScope.sol deploy | ~0.05 | Smaller — Merkle root storage only |
| AgentSlashing.sol deploy | ~0.10 | Larger — VetoSlasher pattern |
| AuditLog.sol deploy | ~0.05 | Append-only Merkle log root storage |
| EAS SchemaRegistry.sol deploy | ~0.08 | Standard EAS contract size |
| EAS.sol main deploy | ~0.15 | Larger — main EAS contract per eas-contracts repo |
| ioID DID mint × 2 (Sentry + Guardian) | ~0.04 | ~0.02 each, ProjectRegistry + ioIDRegistry |
| ERC-6551 TBA bind × 2 | ~0.04 | ~0.02 each |
| EAS schema registration × 3 (AgentCommit, AgentBridgeCall, AgentBoundaryUpdate) | ~0.03 | ~0.01 each |
| Initialization tx (constructor params, ownership, etc.) | ~0.05 | |
| **Subtotal (deploy work)** | **~0.66** | |
| Operational headroom for testnet activity during P0 dev | ~0.20 | 1.5× safety margin |
| **Total Phase O0 budget** | **~0.86 IOTX** | |

**Wallet has 0.5525 IOTX. Gap: ~0.31 IOTX shortfall.**

**Funding is a Phase O0 prerequisite.** Operator notes from this session's
prior Phase 237.5 Path C+ context: "wallet funding gap of several days
before refund." Phase O0 implementation cannot begin until wallet is
funded to at least ~1 IOTX (provides ~0.15 IOTX safety margin above the
estimated 0.86).

Honest range: best-case 0.40 IOTX (smaller contract sizes, no
re-deployment retries), worst-case 1.20 IOTX (if EAS contracts are larger
than estimated, or if multiple deploy attempts needed for
gas-estimation issues — a known IoTeX testnet pattern from Phase 237.5
Path C+ findings).

---

### V9 — Lane discipline directories + CODEOWNERS

Live filesystem check this session:

```
wiki/         EXISTS  (88 files)
provenance/   MISSING
events/       MISSING
ops/          MISSING
audits/       MISSING
invariants/   MISSING
```

**Only 1 of 6 proposed lane directories exists.** Phase O0 must create:
`provenance/`, `events/`, `ops/`, `audits/`, `invariants/`.

**No CODEOWNERS file anywhere** (`CODEOWNERS`, `.github/CODEOWNERS`,
`docs/CODEOWNERS` all absent). The entire path-ownership pattern is
greenfield. Phase O0 must:

1. Create CODEOWNERS at repo root or `.github/`
2. Assign Anchor Sentry's GitHub App identity (`vapi-anchor-sentry[bot]`)
   to `wiki/**`, `provenance/**`, `events/**`
3. Assign Guardian's GitHub App identity (`vapi-guardian[bot]`) to
   `ops/**`, `audits/**`, `invariants/**`

**Lane-collision finding (potential conflict)**: existing
`wiki/audits/contradictions.md` and `wiki/audits/phase_224_legacy_endpoint_audit.md`
sit under `wiki/**` (Sentry's lane per architecture doc) but are
content-typed as audits (Guardian's lane semantically).
`wiki/sweeps/sweep_20260426_clean.md` is similar — under wiki/ but is a
Skill 14 sweep artifact (operational/audit shape).

Resolution options for design phase:
1. **Move existing `wiki/audits/` and `wiki/sweeps/` content to top-level
   `audits/`** (under Guardian's lane); update wiki engine references
2. **Distinguish "wiki/audits/" (Sentry's domain — audit-as-doc) from
   top-level "audits/" (Guardian's domain — audit-as-operational-artifact)**;
   document the distinction explicitly
3. **Rename top-level Guardian lane to `ops/audits/` or similar** to
   avoid the collision

The architecture document does not anticipate this collision because the
top-level `audits/` directory does not currently exist. Surface for design
phase.

---

### V10 — EAS and TEE attestation deployment status on IoTeX

**EAS deployment on IoTeX**: Per
[eas-contracts GitHub README](https://github.com/ethereum-attestation-service/eas-contracts)
fetched this session, EAS is officially deployed on:

- **Mainnets**: Ethereum, Optimism, Base, Arbitrum One, Arbitrum Nova,
  Polygon, Scroll, zkSync, Celo, Telos, Soneium, Ink, Unichain, Blast,
  Linea
- **Testnets**: Sepolia, Optimism Sepolia, Optimism Goerli, Base Sepolia,
  Base Goerli, Arbitrum Sepolia, Polygon Amoy, Scroll Sepolia, Ink
  Sepolia, Linea Goerli

**IoTeX (mainnet 4689 or testnet 4690) is NOT in the deployed networks
list.** The architecture document's recommendation of EAS for the
AgentCommit attestation chain requires either:

1. **Deploy EAS to IoTeX testnet** (operator action; ~0.15-0.25 IOTX cost
   per V8). Use official sources from the
   `ethereum-attestation-service/eas-contracts` repo. Phase O0 prerequisite.
2. **Anchor agent attestations to a different chain where EAS exists**
   (e.g., Base Sepolia, Sepolia). Fragments VAPI's protocol identity
   across chains.
3. **Build a VAPI-specific attestation primitive on IoTeX** that
   approximates EAS semantics (custom `AgentCommitRegistry.sol`).

The architecture document anticipates option 1 in section 4 ("deploy EAS
(SchemaRegistry.sol + EAS.sol) on IoTeX testnet") — consistent. Honest
framing: this is real precursor work for Phase O0, not a drop-in
dependency.

**Phala Network and Automata Network status**:

- **Phala**: Per the architecture document section 3, Phala publishes a
  reference repo `arc-8004-tee-agent` deployed to Sepolia. Phala's
  primary deployment chain is Phala-native, not IoTeX. The architecture
  document defers Phala TEE attestation to Phase O3+ ("deferred
  dependencies"). I cannot confirm without additional research whether
  Phala has any IoTeX-side integration; the document's framing is "future
  hook" not "Phase O0 requirement," so this is consistent.
- **Automata**: Architecture document section 3 says Automata's
  Multi-Prover AVS supports "on-chain DCAP verification across 10
  chains." I cannot determine without external research whether IoTeX is
  one of those 10. Document defers Automata to Phase O3+.

Phala and Automata are **not Phase O0 requirements** per architecture
document. Mark for Phase O3+ design phase.

---

### V11 — Conceptual alignment with hardware-AI bridge vision

This is the most important question. Read sections 4, 8, 10 of the
architecture document with attention to whether AgentRegistry, AgentScope,
AgentSlashing, AuditLog satisfy the operator's stated vision of agents as
"verification primitive between physical and digital worlds."

**The architecture document's framing** (section 8, page 8, and section 10,
page 12):

> "VAPI's two Operator Agents are not a chatbot, not a trader, not a
> service worker. They are the first cognitive entities canonically
> registered as Operators of the protocol that runs them, cryptographically
> attested as protocol primitives in their own right, partnered with their
> human counterparts in a 50/50 division of stewardship..."

> "The Anchor Sentry binds the off-chain provenance graph to the on-chain
> attestation chain, every wiki phase verifiable from CORPUS-SNAPSHOT down
> to its first commit. The Guardian binds the existing 38-agent fleet's
> mechanical health to the protocol's cognitive health, every invariant
> audit a record-of-stewardship rather than a one-shot test."

> "Their existence as Operators is the sixth FROZEN-v1 primitive — call
> it OPERATOR — and the ioID DIDs anchored to ERC-8004 IdentityRegistry
> tokens with ERC-6551 MBAs and ERC-5484 soulbound revocability are the
> formal cryptographic encoding of that primitive."

**Verification of alignment with operator's stated vision**: the operator's
vision (per the prompt's V11 framing) is **cryptographic attestation that
connects real-world hardware and IoT device data to the digital world and
to AI through the agents themselves, with the agents' existence as
Operators serving as the verification primitive between the physical and
digital worlds.**

Mapping the proposed contracts to this vision:

| Proposed contract | What it attests | Connection to operator's vision |
|---|---|---|
| **AgentRegistry.sol** (`agentId → publicKey + scopeHash + status`, sibling to VAPIBiometricGovernance) | Agent identity as a protocol-registered Operator | **PARTIAL alignment**: registers the agent's existence as a non-human Operator, which is the first half of the verification primitive (the agent is a real cryptographically-attested entity). Does NOT connect this identity to physical-world data flows directly; that connection lives in the agent's actions, not its registration. |
| **AgentScope.sol** (Merkle root of policy bundle, bridge verifies at request time) | Policy boundaries on agent action | **TANGENTIAL alignment**: bounds what the agent CAN do, not what it observes from the physical world. Important for safety but doesn't bridge physical-to-digital. |
| **AgentSlashing.sol** (VetoSlasher pattern: bond → slash → 24h veto → burn) | Economic accountability for misbehavior | **TANGENTIAL alignment**: provides slashing semantics for the agent's own misconduct. Doesn't bridge physical-to-digital. |
| **AuditLog.sol** (nightly Merkle checkpoint of Tessera signed-tree-head) | The agent's full action history is auditable on-chain | **STRONG alignment**: every action the agent takes (including actions over physical-world data — e.g., observing PoAC records, anchoring corpus snapshots derived from biometric features, attesting fleet coherence over hardware-derived signals) is anchored. AuditLog is the closest contract to "verification primitive between physical and digital worlds" because it records the agent's contact with VAPI's physical-world data infrastructure. |

**Strong alignment lives in the existing primitives**, NOT in the four
new contracts directly:

- **GIC chain** (Phase 235-A) — chains physical-world session captures
  cryptographically; this is already a hardware-to-digital primitive
- **PoAC records** (Phase 1) — 228-byte signed records of physical
  controller state; already a hardware-to-digital cryptographic primitive
- **CORPUS-SNAPSHOT** (Phase 236) — anchors corpus state including
  biometric ratio, agent fleet root, ts_ns; ties physical-world derived
  data to on-chain anchor
- **VAPIConsentRegistry** (Phase 237) — gamer-self-sovereign consent
  tied to specific physical biometric categories (TOURNAMENT_GATE,
  ANONYMIZED_RESEARCH, MANUFACTURER_CERT, MARKETPLACE)

The Operator Agents become the verification primitive **by stewarding
these existing physical-to-digital flows**:

- **Anchor Sentry** binds PoAC records → corpus snapshots → wiki
  provenance → on-chain attestations. The agent's signed commits are
  the bridge between the off-chain physical-world data graph and the
  on-chain cryptographic attestation chain.
- **Guardian** binds operational health observations (fleet coherence,
  invariant audits, autoresearch evaluations) into stewardship records
  that attest the protocol's correctness over time.

**Verification finding**: the proposed four contracts (AgentRegistry,
AgentScope, AgentSlashing, AuditLog) **do not by themselves bridge
physical and digital**. They establish the agent's existence and
boundaries. The bridging happens through the **agent's actions over
existing VAPI primitives** (GIC, CORPUS-SNAPSHOT, CONSENT, etc.).

**For full alignment with the operator's vision, the design phase should
consider**:

1. **Explicit contract logic that links agent actions to physical-data
   primitives**: e.g., `AgentRegistry` could store not just `(agentId,
   publicKey, scopeHash, status)` but also `attestationCapability` —
   which physical-data primitive types this agent is authorized to
   anchor. Anchor Sentry: PoAC, corpus_snapshot. Guardian: fleet_coherence,
   audit_log.
2. **An explicit "physical-data anchor capability" attestation** —
   when Anchor Sentry attests a CORPUS-SNAPSHOT commitment, the
   attestation should include a reference to the physical-data
   pipeline that produced the snapshot (e.g., AIT corpus ratio derived
   from N=37 biometric sessions across 3 players). The architecture's
   AgentCommit schema (`commitSha, repoUri, agentId, prevCommitAttestUid,
   timestamp, agentSig`) doesn't include this.
3. **A `PhysicalDataAttestation` schema** (parallel to AgentCommit) that
   binds agent identity to specific physical-world data streams. E.g.,
   `(agentId, dataPrimitiveType, snapshotCommitment, sessionRange,
   biometricProvenance)`. This would be the explicit "verification
   primitive between physical and digital" contract.

**Conclusion for V11**: the architecture document's contracts ESTABLISH
the agents' existence as cryptographically-attested Operators. They do NOT
explicitly encode the bridge between physical and digital — that bridge
is implicit in the existing VAPI primitives the agents will steward. The
operator's vision is achievable but requires the design phase to make
the physical-to-digital bridging explicit, either through contract logic
in the four new contracts (preferred) or through dedicated attestation
schemas that link agent actions to physical-data primitives.

---

## Section 2 — Architectural Compatibility Summary

### Ready (codebase already supports)

- **IoTeX testnet ioID infrastructure** (V3): all 4 cited contracts verified
  on-chain. ioID DID minting + ERC-6551 TBA binding can proceed.
- **Sibling AgentRegistry pattern** (V1): VAPIBiometricGovernance
  structure does not block a parallel sibling registry. Deploy-only,
  no BBG modification.
- **Distinction between mechanical fleet and cognitive agents** (V7):
  architecturally clean. Multiple complementary overlaps; zero
  conflicting overlaps.
- **Claude Agent SDK availability** (V6): both TypeScript and Python
  SDKs exist on registries, are installable, and the bridge already
  imports `anthropic` for SessionAdjudicator (precedent).
- **Wiki engine snapshot pattern** (V4): the existing wiki snapshot +
  AdjudicationRegistry anchor pattern can host the agent's commits;
  the chained-attestation extension is additive.

### Needs construction (new infrastructure required)

- **AgentRegistry, AgentScope, AgentSlashing, AuditLog contracts** (V1):
  all four new; not in current codebase.
- **EAS deployment on IoTeX** (V10): EAS not deployed on IoTeX; either
  deploy or pivot.
- **EAS schema registration**: 3 schemas (AgentCommit, AgentBridgeCall,
  AgentBoundaryUpdate) must be registered post-EAS-deploy.
- **Layered authentication stack** (V2): OAuth 2.1 + HMAC + mTLS via
  SPIFFE/SPIRE — entirely new auth path; existing `_check_key` /
  `_check_read_key` cannot be retrofitted.
- **PV-CI gate path-scope component** (V5): new gate component
  parsing diff + author + scope map; current invariant gate has no
  hooks for this.
- **AgentCommit attestation chain** (V4): no `refUID`-style chained
  attestation in current wiki engine; needs new chain wrapper +
  `prev_attestation_uid` schema field on `corpus_snapshot_log` or new
  `agent_commit_log` table.
- **CODEOWNERS file** (V9): does not exist anywhere. Greenfield.
- **5 of 6 lane directories** (V9): `provenance/`, `events/`, `ops/`,
  `audits/`, `invariants/` all missing.
- **Anthropic API key per-agent management** (V6): existing bridge has
  one shared `ANTHROPIC_API_KEY` env var; per-agent keys with KMS
  management is new infrastructure.
- **Two GitHub Apps + KMS keys + SPIRE SVID issuing** (V6, architecture
  doc P0 exit criteria): all greenfield ops infrastructure.
- **Tessera audit log** (V6 / architecture doc page 7): new substrate.
- **Cedar policy bundles** (architecture doc page 7): new policy-as-code
  layer.
- **Temporal substrate** for durable execution (architecture doc page 6):
  new orchestration layer if adopted.

### Needs precursor work (must happen before Phase O0)

- **Wallet funding** (V8): current 0.5525 IOTX < estimated ~0.86 IOTX
  Phase O0 budget. Operator-side funding gap of "several days" per prior
  session context.
- **Bridge gas-drain stays mitigated**: the Phase 237.5 Path C+
  `CHAIN_SUBMISSION_PAUSED=true` kill-switch must remain active during
  Phase O0 to prevent further wallet erosion. Lifting it is gated on
  fixing the underlying retry-blind paths (out of Phase O0 scope per
  architecture document — but operationally important).
- **VAPIConsentRegistry extension decision** (V1): is the agent-identity
  field a CONSENT v2 (requires new domain tag + parallel pillar) or
  metadata that doesn't enter the FROZEN-v1 hash? Operator decision
  required before contract work begins.
- **Contract redeploy decision for AdjudicationRegistry** (V1): the
  proposed `requireAgentScope` modifier requires either redeploying
  AdjudicationRegistry (with the VAPI-EXT extensions + new modifier)
  or building agent-scope enforcement at the bridge layer. Operator
  decision.

---

## Section 3 — Open Questions for Design Phase

1. **VAPIConsentRegistry extension**: is the agent-identity capture a
   CONSENT v2 (new FROZEN-v1 domain tag, parallel pillar) or metadata
   that lives outside the commitment? V1 finding.

2. **AdjudicationRegistry redeploy**: do we redeploy the Phase 111
   contract with VAPI-EXT + `requireAgentScope` extensions, or enforce
   agent-scope at bridge layer only? Per Phase 237.5 finding, the
   deployed contract is Phase 111 original; VAPI-EXT lives in source
   but not on-chain. V1 / V11 finding.

3. **EAS deployment on IoTeX**: deploy EAS to IoTeX testnet (option 1),
   anchor to a different chain (option 2), or build VAPI-specific
   attestation primitive (option 3)? V10 finding.

4. **Python SDK version**: architecture doc says v0.16.x; PyPI shows
   v0.1.68. Does the architecture intend current 0.1.x series or a
   future-version dependency? V6 finding.

5. **Anthropic API key management**: how are per-agent keys
   provisioned and rotated? KMS-managed alongside git signing keys, or
   separate management plane? V6 finding.

6. **Cryptographic-claim formulation**: should the SBT identity for
   each Operator Agent include a `model_class` field (e.g.,
   `claude-sonnet-4-6`) so the on-chain attestation includes which
   model produced the reasoning? Anthropic doesn't sign API responses,
   so this is self-asserted, but binding it to the SBT prevents silent
   model-switching. V6 finding.

7. **Lane collision: `wiki/audits/` and `wiki/sweeps/`**: existing
   content under `wiki/**` (Sentry's lane) but content-typed as audits
   (Guardian's lane). Move to top-level `audits/`? Distinguish
   `wiki/audits/` (doc) from `audits/` (operational)? Rename Guardian
   lane? V9 finding.

8. **Phase O0 contract scope**: which of the 7 contract standards in
   the architecture doc section 4 (ERC-8004, ERC-5192/5484, ERC-6551,
   ERC-4337, Zodiac Roles, OZ Timelock, EAS) ship in Phase O0 vs
   deferred? The architecture document P0 exit criteria specify
   AgentRegistry, AgentScope, AuditLog, AgentSlashing, EAS schemas.
   ERC-4337 account abstraction and Zodiac Roles Modifier may be
   Phase O1+ candidates. Operator decision.

9. **Phala TEE integration timing**: architecture document defers to
   Phase O3+; confirm. V10 finding.

10. **Two-week P0 estimate validity**: architecture document section 9
    says ~2 weeks for P0. Verification reveals significant
    precursor work (V8 funding, V10 EAS deployment, V1 contract
    redeploys). Revise to range estimate (see Section 4).

11. **Physical-to-digital bridging in contract logic**: V11 finding —
    do we extend AgentRegistry / AgentCommit schema with explicit
    physical-data capability fields, OR rely on existing VAPI primitives
    (GIC, CORPUS-SNAPSHOT, CONSENT) to implicitly carry the
    physical-world binding? The latter is the document's current
    framing; the former more directly fulfills the operator's vision.

12. **Process management**: bridge currently runs as single asyncio
    process. Operator Agents could run in-process (asyncio coroutines)
    or as separate Temporal Workflows. Architecture document
    recommends Temporal substrate — adopt for Phase O0 or defer to
    later phase? V6 finding.

13. **Existing `ANTHROPIC_API_KEY` env var usage**: SessionAdjudicator
    (Phase 65) already uses one bridge-shared API key. Will Operator
    Agents share this key (rate-limit pressure increases) or get
    separate keys (cost / billing isolation)?

---

## Section 4 — Phase O0 Implementation Scope Estimate

**Architecture document estimate**: 2 weeks (section 9, P0 row).

**Verification-revised estimate**: **3.5 to 6 weeks**.

Reasoning for the increase:

- **+0.5 to 1 week for wallet funding** (V8): operator notes "several
  days" funding gap. P0 cannot meaningfully begin until wallet ≥1 IOTX.
- **+0.5 to 1 week for EAS deployment to IoTeX** (V10): EAS not on
  IoTeX. Deploying both `SchemaRegistry.sol` and `EAS.sol` from the
  official `eas-contracts` repo, including configuration, tests,
  schema registration. Includes time to handle gas estimation surprises
  on IoTeX testnet (Phase 237.5 Path C+ discovered IoTeX requires ~2x
  gas estimates for storage-heavy ops; same caution applies to EAS).
- **+0.5 to 1 week for layered auth path** (V2): OAuth 2.1 token issuer
  + HMAC verification middleware + SPIFFE/SPIRE setup. The architecture
  doc lists these as P0 exit criteria but they are net-new infrastructure.
  Realistic minimum is a week even for a trimmed-down implementation
  (start with OAuth 2.1 client credentials only, defer HMAC and mTLS
  to P1).
- **+0.5 to 1 week for path-scope gate component** (V5): new gate
  alongside the existing invariant gate. Diff parsing + author lookup
  + scope rule engine + GitHub Actions integration.
- **+0.5 to 1 week for KMS keys + GitHub Apps + SPIRE setup**
  (architecture doc P0 row): real DevOps work (AWS KMS provisioning,
  IAM policies, GitHub App creation per org permissions).

**Best case (3.5 weeks)**: wallet funded same day operator returns,
EAS deploy on IoTeX is clean, layered auth scope-cuts to OAuth 2.1
client credentials only, KMS + GitHub App provisioning unblocked.

**Worst case (6 weeks)**: wallet funding takes a week, EAS deploy
hits gas estimation issues like Phase 237.5 Path C+, full layered auth
stack required for P0, HMAC nonce-store integration, SPIFFE SVID
issuing requires Kubernetes context VAPI doesn't currently have.

The architecture document's 2-week estimate underweights the
precursor work surfaced in V8, V10, and V2. The verification-adjusted
range (3.5-6 weeks) makes Phase O0 a realistic month-long phase
rather than a sprint, which aligns better with the architecture
document's own framing of the full Operator series as 16-20 weeks
across 7 phases.

---

## Section 5 — Risk Surface

### R1 — Bytecode-vs-source drift on AdjudicationRegistry

**Risk**: V1 surfaced that the deployed AdjudicationRegistry is the
Phase 111 original; the VAPI-EXT extensions (`anchorAdjudication`
overloads, sourceType attribution) are in source but not on-chain. The
architecture document proposes adding `requireAgentScope` to a
contract whose deployed version doesn't even have the VAPI-EXT
extensions yet. If Phase O0 modifies source without redeploying, the
on-chain reality diverges further from the source intent.

**Mitigation for design phase**: explicitly decide whether
AdjudicationRegistry redeploys in Phase O0 (with all VAPI-EXT +
requireAgentScope changes folded together) or whether agent-scope
enforcement happens at the bridge layer entirely, leaving the
deployed contract unchanged. If redeploying, the design phase must
plan for breaking Phase 237.5's `chain.anchor_corpus_snapshot` path
(which currently targets the legacy `recordAdjudication` ABI) — this
is a real backward-compat concern that needs a transition plan.

### R2 — VAPIConsentRegistry FROZEN-v1 conflict

**Risk**: V1 surfaced that adding `agentId` to ConsentRecord conflicts
with the FROZEN-v1 hash formula declared in
`bridge/vapi_bridge/consent_categories.py`. Architecture document
calls this "the natural extension" but doesn't address the FROZEN
constraint. If implemented as v2 (new domain tag), CONSENT becomes the
sixth FROZEN-v1 primitive AND the FIRST primitive to have a v2 — that's
a precedent VAPI hasn't set yet and may have downstream implications
for the autoresearch loop's reproducibility.

**Mitigation for design phase**: explicitly choose between
(a) CONSENT v2 with new domain tag and parallel hash formula
(architecturally cleaner; sets precedent for future v2 extensions of
other FROZEN primitives), (b) agentId as off-formula metadata
(simpler; preserves FROZEN-v1; less expressive on-chain), or (c) a new
parallel primitive `AGENT_CONSENT_v1` that doesn't extend CONSENT
(simplest from invariant perspective). The architecture document's
framing implicitly assumes (a) but doesn't acknowledge the precedent
implications.

### R3 — Wallet drain class not yet structurally fixed

**Risk**: Phase 237.5 Path C+ shipped the `CHAIN_SUBMISSION_PAUSED`
kill-switch as a defense against the DualShock + batcher retry-blind
drain (~3 IOTX/hour against IoTeX's broken P256 precompile). The
underlying retry-blind paths still exist. If Phase O0 deploy work
requires `CHAIN_SUBMISSION_PAUSED=false` (to actually fire deploy
transactions), the wallet drain resumes during the deploy window. The
P0 exit criteria specify ~10 contract deploys + schema registrations;
that's potentially 10+ minutes of bridge running with chain submission
enabled.

**Mitigation for design phase**: deploy contracts via a separate
deploy-only RPC client (Hardhat or Foundry) that does NOT use the
bridge process at all. The bridge stays halted (or runs with
`CHAIN_SUBMISSION_PAUSED=true`) during the deploy window. This bypasses
the retry-blind paths entirely. Existing `contracts/scripts/` deploy
pattern (from Phase 221, 222, 237 deploys) already uses this approach
— Phase O0 can reuse it without risk.

### R4 — IoTeX gas estimation surprises

**Risk**: Phase 237.5 Path C+ discovered that IoTeX testnet requires
~2x the naive Ethereum gas estimate for storage-heavy operations.
EAS contracts (especially the main `EAS.sol`) are storage-heavy
(attestation storage, schema mappings). Naive deploy gas estimates
could underbudget by 50%+, triggering out-of-gas reverts that consume
gas without successful deploy.

**Mitigation for design phase**: include 2-3x gas safety buffer on EAS
deploys; pre-estimate via `eth_estimateGas` against a fork (Foundry
fork of IoTeX testnet) before live deploy; use higher-than-default gas
prices to ensure inclusion (failed-tx cost is recoverable; missed-block
cost is not).

### R5 — Architecture document Python SDK version

**Risk**: V6 surfaced that the architecture document cites Python SDK
v0.16.x but PyPI shows v0.1.68. If the architecture document was
written assuming an SDK version that doesn't exist, other API claims
in section 1 ("query() for one-shot agent loops, ClaudeSDKClient /
ClaudeAgentOptions for stateful long-running sessions, SessionStore
protocol") may also be slightly off-version. The architecture's
references to specific API surfaces are mostly accurate per the
TypeScript SDK at v0.2.119, but the Python SDK at v0.1.68 may differ.

**Mitigation for design phase**: actually install both SDKs and
sanity-check the API surface against the architecture document's
references. Confirm `query()`, `ClaudeSDKClient`, `ClaudeAgentOptions`,
and `SessionStore` exist on both at the cited shapes. If Python parity
lags TypeScript, plan for Python-side workarounds or use TypeScript
for the Operator Agent processes.

### R6 — Two-agent partnership pattern unproven at protocol-stewardship scale

**Risk**: Architecture document section 8 cites Othentic's EigenBets
dual-AI prediction market as the closest production analogue, but
EigenBets is a prediction-market-resolution pair, NOT a protocol-
stewardship pair. Cognition's April 2026 "narrower class works"
guidance validates the SHAPE (two complementary agents with strict
lane discipline) but not the SPECIFIC application (16-20 weeks of
sustained partnership stewarding a live protocol's repo). If the
two-agent coordination pattern fails (e.g., agents deadlock on
contested decisions, or escalate to human too aggressively, or
silently diverge in their own "current state" understanding), there's
no production precedent to fall back on.

**Mitigation for design phase**: P1 (Shadow / Read-Only) and P2
(Suggestion mode) per architecture document section 9 are exactly the
gradual-rollout phases that would surface these failure modes before
the agents have any write authority. Strict adherence to those phases
— especially the ≥95% alignment requirement in P1 and ≥90% PR
acceptance rate in P2 — is the empirical testing pattern for the
two-agent partnership. Don't shortcut these phases.

### R7 — Operator vision conceptual gap (V11)

**Risk**: V11 surfaced that the four proposed contracts (AgentRegistry,
AgentScope, AgentSlashing, AuditLog) don't directly encode the
physical-to-digital bridge that the operator's vision describes. The
bridging is implicit in the agents' actions over existing VAPI
primitives. If a future external auditor or skeptic asks "where is the
hardware-to-digital cryptographic primitive in your contract design?"
the honest answer is "it lives in the agents' actions, not in the
agent registration contracts" — which is correct but less defensible
than a contract that explicitly encodes it.

**Mitigation for design phase**: consider adding an explicit
`PhysicalDataAttestation` schema (parallel to AgentCommit) that binds
agent identity to specific physical-world data primitives. Or extend
AgentRegistry's `(agentId, publicKey, scopeHash, status)` mapping with
an additional `attestationCapability` field listing which physical-data
primitive types this agent can anchor (Sentry: PoAC, corpus_snapshot;
Guardian: fleet_coherence, audit_log). This would make the
physical-to-digital bridging explicit at the contract layer rather
than implicit in the agents' behavior.

---

## Surprising vs. expected findings (per prompt's closing instruction)

### Surprising findings (move design phase shape)

1. **Python SDK version mismatch (V6)**: architecture doc says v0.16.x;
   PyPI shows v0.1.68. The codebase ground truth contradicts the
   document. Other Python-SDK API claims in the document need
   re-verification before the design phase locks them in.
2. **No CODEOWNERS file anywhere (V9)**: entire path-ownership pattern
   is greenfield. The architecture document treats CODEOWNERS as if
   it already exists (page 5 says "Encode this in CODEOWNERS plus a
   CI check"). It does not.
3. **5 of 6 lane directories missing (V9)**: only `wiki/` exists.
   `provenance/`, `events/`, `ops/`, `audits/`, `invariants/` must all
   be created.
4. **Lane collision: `wiki/audits/` already populated (V9)**: existing
   audit-style docs sit under Sentry's wiki/** lane but are
   content-typed as Guardian's audits/** lane work. Need explicit
   reconciliation in design phase.
5. **EAS not deployed on IoTeX (V10)**: official deployment networks
   list confirms IoTeX is NOT among them. The architecture document's
   recommendation requires either deploying EAS to IoTeX, anchoring to
   a different chain, or building a custom attestation primitive.
   The doc anticipates option 1 but doesn't make explicit that EAS
   isn't there yet.
6. **Wallet shortfall (V8)**: 0.5525 IOTX vs estimated ~0.86 IOTX
   budget. Funding gap is precursor work, not just operational
   detail. This compounds with the prior session's Phase 237.5 Path C+
   wallet drain — Phase O0 cannot start until wallet recovers.
7. **AdjudicationRegistry deployed-vs-source drift (V1)**: per Phase
   237.5 verification, deployed bytecode is Phase 111 original; VAPI-EXT
   extensions only in source. Adding `requireAgentScope` requires
   redeploying the contract — the architecture document treats this as
   a simple modifier addition.
8. **VAPIConsentRegistry FROZEN-v1 conflict (V1)**: extending consent
   records to capture agentId conflicts with the FROZEN-v1 hash formula
   declared on the bridge side. Document calls it "natural extension"
   but doesn't acknowledge FROZEN constraint or propose v2.
9. **AgentCommit attestation chain is greenfield (V4)**: no
   `refUID`-style chained attestation exists in current wiki engine
   or any VAPI primitive. The closest precedent (GIC chain) operates
   at a different layer and doesn't use EAS-style refUID semantics.

### Expected findings (build confidence)

1. **All 4 IoTeX testnet contracts verified (V3)**: ProjectRegistry,
   ioIDRegistry, ioID NFT, ERC-6551 Registry all return live bytecode.
   Architecture document accurately cited.
2. **38-agent fleet vs Operator agent distinction is clean (V7)**:
   no conflicting overlaps. All overlaps are complementary.
   "Mechanical fleet, cognitive Operators" framing holds.
3. **TypeScript SDK availability matches architecture document (V6)**:
   `@anthropic-ai/claude-agent-sdk` v0.2.119 confirmed on npm.
4. **VAPIBiometricGovernance is sibling-friendly (V1)**: parallel
   AgentRegistry deployment requires no BBG modification.
5. **PV-CI gate is identity-blind (V5)**: confirmed; new component
   needed. Expected per architecture document's framing as a
   gate "extension."
6. **Bridge auth is single-shared-secret (V2)**: confirmed; layered
   stack is parallel work. Expected per architecture document's
   description of OAuth 2.1 + HMAC + mTLS as added layers.
7. **CeremonyAuditRegistry needs no Phase O0 change (V1)**: not in
   architecture document's extension list; compatible by omission.

The surprises tilt the Phase O0 estimate from the architecture
document's 2 weeks to a verification-adjusted 3.5–6 weeks (Section 4).
The surprises do NOT change the architectural feasibility of the
Operator series — every gap surfaced has a known mitigation path that
fits within the 16-20 week initiative envelope. The discipline of
front-loading these findings is the value the verification produces.

This document holds for review. No design proposal follows. No agent
definition files written. No contracts deployed. No commits.
