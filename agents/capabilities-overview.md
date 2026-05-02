# VAPI Operator Agent Capability Specifications

**Status**: Phase O0 supplementary documentation (capability specifications bridging Phase O0 contract specifications to Phase O1 shadow mode activation)
**Authored**: 2026-05-02
**Scope per E1c**: O1 shadow mode + O2 suggestion mode only. O3+ activation phases deferred to subsequent design phase work.
**Architecture per E2c**: Hybrid capability surface — shared base + agent-specific extensions.
**Structure per E3d**: `agents/skills/<name>/SKILL.md` and `agents/tools/<name>.md` following the Anthropic skill pattern.

## Architecture

VAPI Operator Agents (`vapi-anchor-sentry`, `vapi-guardian`) operate through a layered capability stack:

```
┌───────────────────────────────────────────┐
│ Skills (composable behavioral primitives) │  Each skill = directory + SKILL.md
├───────────────────────────────────────────┤
│ Tools (atomic operations)                 │  Each tool = single Markdown file
├───────────────────────────────────────────┤
│ Agent identity layer                      │  KMS keys (Pass 2C Section 12: AWS KMS us-east-1)
├───────────────────────────────────────────┤
│ On-chain contracts (Stream 2-deploy)      │  AgentRegistry, AgentScope, AuditLog,
│                                           │  AgentSlashing, AgentAdjudicationRegistry
└───────────────────────────────────────────┘
```

Skills compose tools to produce agent behavior. Tools are atomic operations (one IoTeX RPC query, one KMS sign call, one git operation). Skills are reusable behavioral primitives (correlate events, draft an audit, record provenance) that orchestrate multiple tools.

## Shared capability surface (both Sentry and Guardian)

| Skill | Purpose | Tools composed |
|-------|---------|----------------|
| [`repo-inspection`](skills/repo-inspection/SKILL.md) | Read-only walk of working tree + git state | `git-operations` (read subset) |
| [`on-chain-state-querying`](skills/on-chain-state-querying/SKILL.md) | Verified reads of VAPI on-chain state | `iotex-rpc-query`, `agent-registry-query`, `audit-log-query` |
| [`cryptographic-signing`](skills/cryptographic-signing/SKILL.md) | Produce ECDSA secp256k1 signatures via agent's KMS key | `kms-sign` |

| Tool | Purpose | Composed by |
|------|---------|-------------|
| [`git-operations`](tools/git-operations.md) | Read git state (O1+); commit + PR (O2 only) | `repo-inspection`, `audit-drafting`, `provenance-recording` |
| [`iotex-rpc-query`](tools/iotex-rpc-query.md) | JSON-RPC client for IoTeX (read-only) | `on-chain-state-querying`, `agent-registry-query`, `audit-log-query` |
| [`kms-sign`](tools/kms-sign.md) | AWS KMS Sign API wrapper (ECDSA secp256k1) | `cryptographic-signing` |
| [`ipfs-pin`](tools/ipfs-pin.md) | Pinata pinning (O2 only for agent invocation) | `provenance-recording`, `audit-drafting` |
| [`agent-registry-query`](tools/agent-registry-query.md) | `AgentRegistry.getAgent` wrapper | `on-chain-state-querying`, `audit-drafting`, `provenance-recording` |
| [`audit-log-query`](tools/audit-log-query.md) | `AuditLog.getLatestCheckpoint` wrapper | `operational-diagnostic`, `audit-drafting` |

## Sentry-specific capabilities (`vapi-anchor-sentry`)

Sentry's stewardship lane (per [`.claude/agents/vapi-anchor-sentry.md`](../.claude/agents/vapi-anchor-sentry.md) and CODEOWNERS): `wiki/`, `provenance/`, `events/`.

| Skill | Purpose | Tools composed |
|-------|---------|----------------|
| [`event-correlation`](skills/event-correlation/SKILL.md) | Walk causal sequences across wiki/provenance/events | `repo-inspection`, `iotex-rpc-query` |
| [`provenance-recording`](skills/provenance-recording/SKILL.md) | Compose + sign + (at O2) anchor PDA v1 attestations | `cryptographic-signing`, `pda-attestation-anchor`, `git-operations`, `agent-registry-query` |

| Tool | Purpose | Composed by |
|------|---------|-------------|
| [`pda-attestation-anchor`](tools/pda-attestation-anchor.md) | `chain.anchor_pda_attestation` wrapper (O2 only) | `provenance-recording` |

## Guardian-specific capabilities (`vapi-guardian`)

Guardian's stewardship lane (per [`.claude/agents/vapi-guardian.md`](../.claude/agents/vapi-guardian.md) and CODEOWNERS): `audits/`, `sweeps/`, `ops/`, `invariants/`.

| Skill | Purpose | Tools composed |
|-------|---------|----------------|
| [`audit-drafting`](skills/audit-drafting/SKILL.md) | Compose audit entry Markdown; (at O2) PR-draft | `repo-inspection`, `on-chain-state-querying`, `audit-log-query`, `audit-entry-draft`, `git-operations` |
| [`operational-diagnostic`](skills/operational-diagnostic/SKILL.md) | Diagnose FSCA/sweep/invariant/capture health | `iotex-rpc-query`, `audit-log-query` |

| Tool | Purpose | Composed by |
|------|---------|-------------|
| [`audit-entry-draft`](tools/audit-entry-draft.md) | Compose audit Markdown content (no commit) | `audit-drafting` |

## Activation phase availability matrix

| Skill / Tool | O0 (DORMANT) | O1 (Shadow Mode) | O2 (Suggestion Mode) |
|--------------|:------------:|:----------------:|:--------------------:|
| `repo-inspection` | defined | active (read) | active (read) |
| `on-chain-state-querying` | defined | active (read) | active (read) |
| `cryptographic-signing` | defined | active (sign drafts in side channel) | active (sign commit hashes) |
| `event-correlation` (Sentry) | defined | active (graph drafts) | active (graphs feed PDA v1 drafts) |
| `provenance-recording` (Sentry) | defined | active (drafts only, no anchor) | active (PR-merged anchors fire) |
| `audit-drafting` (Guardian) | defined | active (side-channel drafts) | active (PR drafts → operator merge) |
| `operational-diagnostic` (Guardian) | defined | active (diagnostic reports) | active (reports feed audit drafts) |
| `git-operations` | defined | read subset only | read + add + commit + PR (no direct push) |
| `iotex-rpc-query` | defined | active (read) | active (read) |
| `kms-sign` | defined* | active (draft signing) | active (commit signing) |
| `ipfs-pin` | defined | inactive (operator-led setup only) | active (DID/audit pinning) |
| `agent-registry-query` | defined | active | active |
| `audit-log-query` | defined | active | active |
| `pda-attestation-anchor` (Sentry) | defined | inactive | active (post PR merge) |
| `audit-entry-draft` (Guardian) | defined | active (Markdown compose) | active (Markdown compose for PR) |

\* `kms-sign` requires Section 6.3 KMS provisioning per Pass 2C Section 12 amendment; tool defined at O0 but cannot execute until keys exist.

## Composability principles

1. **Lower phases compose into higher phases.** O1 skills produce drafts; O2 skills convert drafts into PRs. The skill at O1 doesn't change behavior at O2 — what changes is the destination of its output (side channel at O1; PR draft at O2).

2. **Tools are atomic; skills orchestrate.** A tool does one thing (sign a digest, query a contract). A skill chains tools to produce a structured output.

3. **Lane discipline is enforced at every layer.** Skills and tools both check lane before reading/writing. CODEOWNERS path-scope gate is the final enforcement layer at PR merge time.

4. **Read before write, always.** Every write operation (O2) is preceded by read operations that establish current state. This makes outputs reproducible and verifiable.

## Boundary specifications (deferred to subsequent design phase work)

The following capabilities are explicitly NOT specified in this Phase O0 supplementary documentation. They are reserved for O3+ activation phase work, which begins as a separate design phase when O3+ scope is formalized.

- **Autonomous PR merge.** All PRs at O2 require operator approval to merge. Autonomous merge requires O3+ governance work specifying when (if ever) operator approval can be elided.
- **Cross-agent communication.** Sentry and Guardian do not communicate directly. Cross-lane findings flow through the operator. Direct agent-to-agent messaging is O3+ design work.
- **Direct on-chain transaction submission.** O0-O2 agents never submit transactions directly. Bridge chain wrappers (`chain.anchor_pda_attestation`, etc.) are invoked by the bridge process; agents request via bridge endpoints. Direct agent-side `eth_sendTransaction` is O3+ work requiring stake/slashing economics.
- **MCP servers.** Phase O0 baseline tools exclude MCP. MCP integration is O1+ infrastructure work but specific MCP server choices and security model are deferred.
- **Cedar policy bundle authorship.** Agents do not write Cedar bundles; bundles are operator-authored at P1+. Agents at O3+ might propose bundle changes via Cedar-aware skills (TBD).
- **Slashing proposal submission.** Agents do not propose slashings. `AgentSlashing.proposeSlash()` is operator-only. Agents at O3+ might propose slashings under formal economic framework (TBD).

## Cross-references

### Phase O0 design pass documents (Pass 2C synthesis)

- [`wiki/proposals/PHASE_O0_VERIFICATION.md`](../wiki/proposals/PHASE_O0_VERIFICATION.md) — Initial V1-V11 verification
- [`wiki/proposals/PHASE_O0_DESIGN_PASS_1.md`](../wiki/proposals/PHASE_O0_DESIGN_PASS_1.md) — Three architectural conflicts resolved
- [`wiki/proposals/PHASE_O0_DESIGN_PASS_2A.md`](../wiki/proposals/PHASE_O0_DESIGN_PASS_2A.md) — V8 wallet refill + V10 EAS rejection
- [`wiki/proposals/PHASE_O0_DESIGN_PASS_2B.md`](../wiki/proposals/PHASE_O0_DESIGN_PASS_2B.md) — V11 PHYSICAL_DATA_ATTESTATION v1 path
- [`wiki/proposals/PHASE_O0_DESIGN_PASS_2C.md`](../wiki/proposals/PHASE_O0_DESIGN_PASS_2C.md) — Implementation plan + Section 11 (1st amendment, 2026-05-01) + Section 12 (2nd amendment, 2026-05-02 — current canonical KMS architecture)

### Agent role definitions (`.claude/agents/`)

- [`.claude/agents/vapi-anchor-sentry.md`](../.claude/agents/vapi-anchor-sentry.md) — Sentry role, lane assignment, operational constraints, FROZEN-v1 primitive surface
- [`.claude/agents/vapi-guardian.md`](../.claude/agents/vapi-guardian.md) — Guardian role, lane assignment, operational constraints, contradiction tracking responsibility

### DID document templates (`agents/did_templates/`)

- [`agents/did_templates/vapi-anchor-sentry.did.template.json`](did_templates/vapi-anchor-sentry.did.template.json) — Sentry's DID document template (populated during Section 6.4)
- [`agents/did_templates/vapi-guardian.did.template.json`](did_templates/vapi-guardian.did.template.json) — Guardian's DID document template

### Forward-references to subsequent activation phase work

- **Section 6.3 implementation session** (subsequent session): provisions AWS KMS keys per Pass 2C Section 12 spec; activates `kms-sign` tool. Until then, all skills depending on `kms-sign` cannot execute even at O1.
- **Section 6.4 agent registration** (subsequent session): mints DIDs, binds ERC-6551 TBAs, registers agents in AgentRegistry. Activates `agent-registry-query` returning non-zero registration tuples for these agents.
- **P1 prep work** (subsequent phase): OAuth token issuance, Anthropic API key per-agent provisioning (Q3 Option b confirmed). Activates HTTP client tooling for bridge `/agent/agent-*` audit endpoints.
- **P1 shadow mode activation** (post-prep): operator turns on agent runtime; O1 capabilities listed in this document begin executing.
- **O2 suggestion mode activation** (subsequent governance event): explicit decision to enable PR-drafting capability. Bot commits begin landing via operator-approved PRs.
- **O3+ design phase** (future): formalizes the boundary capabilities currently deferred. `capabilities-overview.md` may need extension at that phase, following the same amendment-with-supersession-marker pattern Pass 2C established.

## Verification-First Discipline note

This capability specification document was authored under the same Verification-First Discipline pattern that governs Pass 2C amendments (see Section 11 + Section 12 of `wiki/proposals/PHASE_O0_DESIGN_PASS_2C.md` for the discipline pattern in action across two amendments). Pre-implementation V-checks (V1-V6) confirmed:

- V1: clean canonical state at `fc61d93d` (Pass 2C Section 6.3 second amendment commit)
- V2: agent definitions at `.claude/agents/`, capability docs at `agents/skills/` + `agents/tools/` (intentional architectural separation: `.claude/` is harness configuration; `agents/` is protocol-managed agent infrastructure, co-located with `agents/did_templates/`)
- V3: no existing capability/skill/tool framework in design pass docs (greenfield)
- V4: `agents/skills/` and `agents/tools/` did not exist (greenfield create)
- V5: O1/O2 activation phase definitions extracted from Pass 2C + agent definitions (canonical reading)
- V6: E1c/E2c/E3d aligned with existing commitments

Post-implementation P-checks (P1-P8) confirm file structure, pattern conformance, lane respect, and zero side effects.

The capability surface specified here is the **first formal capability framework** for VAPI Operator Agents. Subsequent activation phase work will reference and extend (never overwrite) these specifications, following the same amendment-with-supersession-marker pattern Pass 2C established across its two amendments.
