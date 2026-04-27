# Phase O0 — Design Pass 1: Three Architectural Conflicts Resolution

**Status**: APPROVED 2026-04-26. All three recommendations confirmed by
operator (Conflict 1 Option A, Conflict 2 Option C, Conflict 3 Option A).
Conflict 2 scope-class classification locked per operator reasoning
recorded in Section 3. This document is the permanent design record;
implementation work proceeds in Design Pass 2 with these three
foundational decisions as resolved inputs. No code or contract changes
ship as part of this commit — this is a standalone documentation commit.

**Scope discipline**: addresses exactly three architectural conflicts from
`wiki/proposals/PHASE_O0_VERIFICATION.md` (findings 4, 7, 8 in the
"surprising findings" list). Does NOT address precursor work (V8 wallet,
V10 EAS deploy, V2 layered auth, V5 PV-CI gate, V6 Python SDK version),
the V11 conceptual alignment finding, or the Phase O0 implementation
plan. Those concerns belong to the second design pass once these three
conflicts are resolved.

**Verification standard**: every claim cites `file:line` or external
source. Where the codebase cannot resolve an ambiguity, the ambiguity is
surfaced as an open question (Section 6) rather than silently chosen.

**Date**: 2026-04-26

---

## Section 1 — Executive Summary

**Conflict 1 (AdjudicationRegistry drift)**: Recommend **Option A** —
deploy a parallel `AgentAdjudicationRegistry` contract for agent-scoped
anchoring while leaving the existing `AdjudicationRegistry` at
`0x44CF981f46a52ADE56476Ce894255954a7776fb4` untouched. Phase 237.5's
`anchor_corpus_snapshot` path continues to call `recordAdjudication` on
the existing contract; the inaugural CORPUS_SNAPSHOT anchor (still
deferred per Phase 237.5 Path C+ wallet funding gap) lands on the
existing contract uninterrupted. The new contract handles agent-scoped
anchoring with `requireAgentScope` built in from deployment. Bridge
routing logic distinguishes the two contracts by call-site; explicit
naming makes the routing self-documenting. The cryptographic claim of
contract-level agent-scope enforcement is preserved at full strength.

**Conflict 2 (VAPIConsentRegistry FROZEN-v1)**: Recommend **Option C** —
locate agent action authorization in the new `AgentScope.sol` and
`AuditLog.sol` contracts (already proposed by the architecture
document), NOT in an extension or duplication of the CONSENT primitive.
The verification's FROZEN-v1 conflict is downstream of a semantic
question the architecture document conflates: the document proposes
extending CONSENT (a privacy/data-subject primitive) to cover agent
action authorization (a policy/scope concern). These are different
semantic classes. CONSENT v1 stays FROZEN forever and continues to mean
gamer-self-sovereign data processing consent; agent action
authorization lives in AgentScope policy bounds + AuditLog action
records, both with their own cryptographic properties. **This
recommendation requires operator confirmation of the semantic
classification** — if the operator's vision is that agent action IS
CONSENT-class semantically, then Option A (CONSENT v2) is the correct
path instead. This is the most careful-reasoning recommendation in this
design pass.

**Conflict 3 (lane collision)**: Recommend **Option A** — move
`wiki/audits/` to top-level `audits/` and `wiki/sweeps/` to top-level
`sweeps/`, updating the wiki engine constant `WIKI_SWEEPS` at
`vapi_wiki_engine.py:108` and any documentation references. Three files
total move. Lane discipline becomes path-clean: `wiki/**` is purely
Anchor Sentry's domain, `audits/**` and `sweeps/**` are purely
Guardian's. The migration cost is genuinely small for the current repo
state; the architectural clarity gain is permanent. CODEOWNERS rules
become unambiguous from Phase O0 onward.

---

## Section 2 — Conflict 1 Resolution: AdjudicationRegistry Drift

### Nature of the conflict

The architecture document (page 9, P0 row) proposes hooking the new
`AgentRegistry`, `AgentScope`, `AgentSlashing`, `AuditLog` contracts
into existing VAPI infrastructure including a `requireAgentScope(agentId,
action)` modifier on `AdjudicationRegistry`. The verification document
finding 7 establishes that this modifier cannot be added to the deployed
contract without redeployment, AND that any redeployment cascades into
Phase 237.5's just-shipped CORPUS_SNAPSHOT anchoring path.

**Codebase ground truth**:

- `contracts/contracts/AdjudicationRegistry.sol:53-99` — source contains
  both legacy `recordAdjudication(bytes32, bytes32, bool)` (lines 53-69)
  and VAPI-EXT `anchorAdjudication(bytes32, string)` overloads (lines
  79-99). Every mutating function uses `external onlyOwner`.
- `contracts/deployed-addresses.json:76-80` — deployed at
  `0x44CF981f46a52ADE56476Ce894255954a7776fb4` (Phase 111, 2026-03-27);
  Phase 112 wrapper code-complete but never activated
  (`POAD_ON_CHAIN_ENABLED=false` per `_phase112_status` field).
- Per Phase 237.5 verification: deployed bytecode contains selector
  `0x5fa83f4b` (recordAdjudication) but NOT `0xae7cd267` or `0x79dcce3f`
  (the two VAPI-EXT `anchorAdjudication` overloads). VAPI-EXT exists in
  source only.
- `bridge/vapi_bridge/chain.py:2487-2546` — `record_adjudication`
  wrapper (Phase 112, code-complete, never activated).
- `bridge/vapi_bridge/chain.py:2569-2680` — `anchor_corpus_snapshot`
  wrapper (Phase 237.5 Path X correction). Calls `recordAdjudication`
  with constant `_CORPUS_SNAPSHOT_DEVICE_ID = SHA-256(b"VAPI_CORPUS_SNAPSHOT_v1")`.
  Currently kill-switched (`CHAIN_SUBMISSION_PAUSED=true` in
  `bridge/.env`); inaugural anchor pending wallet funding.

**Critical operational state observation**: per `wiki/phases/phase_237_5.md`
"Inaugural anchor: DEFERRED" section, the four `corpus_snapshot_log` rows
(c24f1949, 1edbb57f, 974f4896, 6065d043) all have `on_chain_confirmed=false`
— **nothing has actually anchored on-chain yet**. The
AdjudicationRegistry contract has `totalAdjudications=0` (verified live
via `eth_call` in this session's earlier work). There is **no on-chain
state to migrate**. The "preservation of Phase 237.5's operational state"
criterion is therefore primarily about preserving the **code path** and
the **address reference in deployed-addresses.json + chain.py** — not
about preserving on-chain state that doesn't yet exist.

### Evaluation of the three options

Three options the prompt enumerates evaluated against three criteria:
(1) preservation of Phase 237.5's operational state, (2) architectural
cleanliness of the resulting Phase O0 design, (3) strength of the
cryptographic claim VAPI can make about agent-scoped on-chain
enforcement.

**Option A — Parallel `AgentAdjudicationRegistry`**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Phase 237.5 preservation | **STRONG** | Existing contract untouched. `chain.anchor_corpus_snapshot` continues to call `recordAdjudication` on the original address. Inaugural anchor (when wallet funded) lands on the existing contract uninterrupted. |
| (2) Architectural cleanliness | **MODERATE** | Two contracts now serve adjacent purposes. Bridge routing logic must distinguish them — but explicit naming (`AdjudicationRegistry` for legacy + Phase 237.5 paths; `AgentAdjudicationRegistry` for agent-scoped) makes routing self-documenting. The two contracts have clean single purposes individually. |
| (3) Cryptographic claim strength | **STRONG** | Agent-scope enforcement happens at the contract layer (best possible) via the `requireAgentScope` modifier built into `AgentAdjudicationRegistry` from initial deployment. |

**Option B — Migrate `AdjudicationRegistry` to a new deployment**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Phase 237.5 preservation | **MODERATE** | Code preserved (chain.py wrappers updated to point at new address); but address change requires coordinated update across Phase 237.5 ship commit references in `wiki/phases/phase_237_5.md`, the Path X correction memo, `deployed-addresses.json`, `CLAUDE.md`. Migration of on-chain state is trivial (totalAdjudications=0; nothing to migrate) — the prompt's "real migration risk" warning is overstated for this codebase state. The real cost is text-reference updates and the conceptual disruption of "Phase 237.5 anchored to address X, but now address X is deprecated." |
| (2) Architectural cleanliness | **STRONG** | One contract serves all anchoring purposes — VAPI-EXT extensions + `requireAgentScope` modifier folded into a single deployment. |
| (3) Cryptographic claim strength | **STRONG** | Agent-scope enforcement at contract layer, same as Option A. |

**Option C — Defer requireAgentScope, enforce at bridge layer**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Phase 237.5 preservation | **STRONG** | Contract entirely untouched. |
| (2) Architectural cleanliness | **MODERATE** | Agent-scope semantics live at the bridge layer (Cedar policies + PV-CI gate) rather than the contract layer. This places agent-scope enforcement in two places (Cedar + bridge code) rather than one canonical location — which is a step back from the architecture document's intent but is operationally functional. |
| (3) Cryptographic claim strength | **WEAKEST** | "Enforced by bridge code" is a meaningfully weaker claim than "enforced by contract logic." A future external auditor reading the contract source cannot see that agent-scope is enforced; they have to trust that the bridge layer enforces it correctly. The architecture document's vision of "first non-human Operators cryptographically attested" steps down here — agents would be cryptographically attested as Operators (via AgentRegistry) but their scope enforcement is software-enforced rather than contract-enforced. |

### Recommendation: Option A

Recommend **Option A — deploy a parallel `AgentAdjudicationRegistry`
contract** for these reasons:

1. **Phase 237.5's pending inaugural anchor lands cleanly on the
   existing contract** when the wallet is funded. The Path X correction
   work (`anchor_corpus_snapshot` calling `recordAdjudication` with
   constant `deviceIdHash`) was carefully verified end-to-end in the
   prior session. Option A preserves that work fully — the deferred
   inaugural anchor + the four `corpus_snapshot_log` historical rows
   that document the diagnosis arc all remain coherent.

2. **The architecture document's intent for `requireAgentScope` is
   honored at full cryptographic strength** without requiring the
   existing contract to be redeployed. New contract = new modifier built
   in from deployment = contract-level enforcement.

3. **CORPUS_SNAPSHOT can migrate to `AgentAdjudicationRegistry` later
   when both Operator Agents exist and CORPUS_SNAPSHOT becomes an
   agent-scoped operation.** Today, CORPUS_SNAPSHOT is operator-triggered
   (per Phase 237.5 Path C+ design — milestone-only anchoring). When
   Anchor Sentry is live (Phase O5+), CORPUS_SNAPSHOT anchoring becomes
   an agent action and naturally migrates to the agent-scoped contract.
   Option A creates the destination for that future migration without
   disturbing the operator-triggered current path.

4. **"Operational confusion" objection mitigated by naming + comment
   discipline**. The two contracts have content-typed names:
   `AdjudicationRegistry` for legacy + Phase 237.5 CORPUS_SNAPSHOT,
   `AgentAdjudicationRegistry` for agent-scoped Phase O0+. Bridge
   routing logic in `chain.py` is one switch statement (or two
   distinct wrapper functions, mirroring the existing
   `record_adjudication` / `anchor_corpus_snapshot` separation). The
   pattern is the same shape as Phase 237-EXTEND's
   `VAPIConsentRegistry` deployed alongside `VAPIBiometricGovernance`
   — two adjacent contracts with cleanly distinct purposes.

5. **`onlyOwner` access control on the existing contract is unaffected.**
   The bridge wallet retains owner status on the existing contract
   (verified per Phase 237.5 V5 work: `eth_call` to selector `0x8da5cb5b`
   returned the active bridge wallet address). The new contract gets
   its own owner (also the bridge wallet) at deployment, and adds
   `requireAgentScope(agentId, action)` as the additional access control
   layer specifically for agent calls.

### Architectural details for Option A

The recommendation requires the following design decisions in Phase O0
(but no implementation in this session):

- **Contract naming**: `AgentAdjudicationRegistry.sol`. Mirrors the
  existing `AdjudicationRegistry.sol` semantically: both anchor verdict
  hashes; the new one specifically anchors agent-scoped action verdicts.
- **Function signatures** (design only): the new contract should have
  `anchorAgentAction(bytes32 actionHash, bytes32 agentId, string
  actionType)` with the `requireAgentScope(agentId, actionType)`
  modifier. It should also have `isRecorded(bytes32 actionHash)` and
  `getAgentActionType(bytes32 actionHash)` view functions for downstream
  consumers (ZK-SEPPROOF binding patterns).
- **Event emission**: `AgentActionAnchored(bytes32 indexed agentId,
  bytes32 indexed actionHash, string actionType, uint256 blockNumber)`.
  Indexed `agentId` lets future query patterns filter actions by agent
  efficiently.
- **Access control pattern**: `Ownable + ReentrancyGuard + requireAgentScope`.
  Matches the Phase 222 `VAPIBiometricGovernance` + Phase 179
  `CeremonyAuditRegistry` pattern. The new modifier looks up
  `agentId → scopeHash` from `AgentRegistry.sol` (sibling contract per
  architecture doc) and validates that `actionType` falls within
  `scopeHash`'s allowed actions.
- **Bridge routing**: `chain.py` gains a new wrapper
  `anchor_agent_action(action_hash_hex, agent_id_hex, action_type)`
  alongside the existing `record_adjudication` and
  `anchor_corpus_snapshot`. Each wrapper targets its own contract
  address; routing decision is per-call-site based on what's being
  anchored.
- **Address registration**: new entry in `contracts/deployed-addresses.json`
  for `AgentAdjudicationRegistry`. CLAUDE.md / VAPI_CONTEXT.md note
  blocks updated with the new address at deploy time.

This recommendation does not require modifying
`AdjudicationRegistry.sol` source. The VAPI-EXT extensions
(`anchorAdjudication` overloads) remain in source as code-complete
work whose deployment is no longer Phase O0's responsibility — they may
ship in a future phase if needed, or stay as documented unfired
extensions indefinitely.

### Confidence

**HIGH CONFIDENCE.** The codebase evidence supports this recommendation
strongly. Phase 237.5 preservation is non-negotiable; cryptographic
claim strength is non-negotiable; the only criterion where Option A
trades off (architectural cleanliness — two contracts vs one) is
mitigated by naming discipline and matches existing VAPI patterns.

---

## Section 3 — Conflict 2 Resolution: VAPIConsentRegistry FROZEN-v1

### Nature of the conflict

The architecture document section 4 (page 4) proposes "extending consent
records to capture the agent identity that performed the action" —
calling this "the natural extension of the CONSENT FROZEN-v1 primitive
to non-human consenters." The verification document finding 8
establishes that this extension conflicts with the FROZEN-v1
commitment.

**Codebase ground truth**:

- `bridge/vapi_bridge/consent_categories.py:47` — `_CONSENT_TAG = b"VAPI-CONSENT-v1"`
  (15 bytes; the domain tag).
- `bridge/vapi_bridge/consent_categories.py:149-186` — `compute_consent_hash`
  function. Inputs to the hash:
  ```
  consent_hash = SHA-256(
      _CONSENT_TAG (15 bytes)
      + dev_b (32 bytes, device_id_to_bytes32)
      + struct.pack(">I", bitmask) (4 bytes, uint32 BE)
      + struct.pack(">Q", expires_at_ts) (8 bytes, uint64 BE)
      + struct.pack(">Q", ts_ns) (8 bytes, uint64 BE)
  )                                = 67 bytes → 32 bytes
  ```
- `VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md:393-396` — INV-CONSENT-001
  explicitly states: "Any change to byte order, domain tag, bitmask
  layout, or scaling factor requires v2 + new domain tag." This is the
  literal escape hatch the document already anticipates.
- `VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md:397-401` — INV-CONSENT-002
  locks the `ConsentCategory` enum positions: TOURNAMENT_GATE=0,
  ANONYMIZED_RESEARCH=1, MANUFACTURER_CERT=2, MARKETPLACE=3. Adding a
  category is itself a v2 break.
- `VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md:402-407` — INV-CONSENT-003:
  "The bridge READS on-chain consent via `chain.is_consent_valid()`
  view calls but NEVER writes on the gamer's behalf. Grant/revoke must
  be msg.sender-signed by the gamer's wallet."
- `bridge/vapi_bridge/store.py:1626-1645` — `consent_ledger` table
  schema: `(device_id, consent_type, consent_given, consent_ts,
  revoked_at, revocation_reason, erasure_requested, erasure_completed)`.
  Phase 160 BP-002 (privacy ledger). UNIQUE on `(device_id,
  consent_type)`.
- `VAPI-WORKFLOW.v2/VAPI_BIOMETRIC_PRIVACY.md:4-10` — BP-002 is
  ZK-Attested Consent (per-category consent + on-chain anchor LIVE
  Phase 237). Specifically: "Gamer-self-sovereign (msg.sender writes);
  bridge reads-only."

**Critical semantic observation**: the CONSENT primitive was designed
for **human gamer-self-sovereign data processing consent**. INV-CONSENT-003
explicitly enshrines this: bridge reads only; gamer writes via their
own wallet. The architecture document's proposed "extension to
non-human consenters" is conceptually different from this:

- For humans: "I (gamer) consent to data X being processed for purpose Y."
  Properties: gamer-self-sovereign (msg.sender = gamer), opt-in/opt-out,
  privacy-preserving (categories without revealing data content),
  GDPR-aligned.
- For agents (per architecture doc framing): "agent action authorization
  recorded as a consent-class operation." Properties: agent's own wallet
  signs (msg.sender = agent), but the semantics are "this action is
  within my scope" — that's an authorization/attestation, not
  data-subject consent.

The architecture document's own contract designs already provide
authorization semantics:

- **AgentScope.sol** (architecture doc page 4): "stores a Merkle root
  of the policy bundle (Cedar or Rego) the bridge verifies against at
  request time" — this IS agent action authorization. When the agent
  invokes a bridge endpoint or contract function, the bridge checks
  the request against the policy Merkle root.
- **AuditLog.sol** (architecture doc page 4 + page 7): "records full
  agent action history... append-only Merkle log" — this records
  every agent action with cryptographic proof. The audit log IS the
  agent's record of its own actions.

The verification's FROZEN-v1 conflict is downstream of an
architectural conflation: the document proposes putting agent action
authorization into CONSENT (a privacy/data-subject primitive) when
AgentScope (a policy/scope primitive) and AuditLog (an action-record
primitive) are already designed for exactly that purpose.

### Evaluation of the three options

Three criteria from the prompt: (1) preservation of FROZEN-v1
commitment for existing CONSENT, (2) architectural appropriateness of
where agent consent lives, (3) strength of the cryptographic claim
VAPI can make about agent consent specifically.

**Option A — CONSENT v2 supersedes v1**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) FROZEN-v1 preservation | **STRONG** | CONSENT v1 stays FROZEN forever per INV-CONSENT-001's explicit v2 escape clause. v2 is a new primitive with its own formula. |
| (2) Architectural appropriateness | **MIXED** | Agent action authorization lives in CONSENT family — but CONSENT family is privacy/data-subject. Stretches the meaning of CONSENT to cover concerns it wasn't designed for. External observers reading "VAPI consent v2 covers agent actions" may misread it as "agents consent to their own data processing." |
| (3) Cryptographic claim strength | **STRONG** | Full primitive properties (hash chaining, schema, version tag); cryptographic claim is well-formed. |
| Side-effect | — | Sets the precedent for v2 extensions of FROZEN primitives. This is both a pro (clear pattern for future extensions) and a con (other primitives may now be tempted to extend rather than stay simple). |

**Option B — New AGENT-CONSENT-v1 parallel primitive**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) FROZEN-v1 preservation | **STRONG** | CONSENT v1 untouched. |
| (2) Architectural appropriateness | **MIXED** | Distinct primitive for agent semantics. But the name "AGENT-CONSENT" still implies CONSENT-class semantics. If the operator's vision is that agent actions are CONSENT-class, this name fits; if not, it's misleading. |
| (3) Cryptographic claim strength | **STRONG** | Full primitive properties for AGENT-CONSENT-v1. |
| Side-effect | — | FROZEN-v1 primitive count grows from 5 to 6. Architecture document section 8 says the SIXTH FROZEN-v1 primitive is OPERATOR (the agent's existence-as-Operator). If AGENT-CONSENT also lands as a FROZEN-v1 primitive, the count grows to 7 (or AGENT-CONSENT becomes the sixth and OPERATOR becomes seventh). Either way, this expansion deserves explicit operator endorsement. |

**Option C — Capture agent action authorization through different mechanism (AgentScope + AuditLog)**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) FROZEN-v1 preservation | **STRONG** | CONSENT v1 untouched, kept exclusively for its designed purpose (gamer-self-sovereign data processing consent). |
| (2) Architectural appropriateness | **STRONG** | Agent action authorization lives in AgentScope (policy bounds) and AuditLog (action records) — both already proposed by the architecture document for exactly these concerns. Each primitive is used for what it was designed for. |
| (3) Cryptographic claim strength | **STRONG (different claim)** | The "cryptographic claim about agent consent" is the wrong framing. The right claim is **"agent action authorization"** (proven by AgentScope policy match) and **"agent action record"** (proven by AuditLog inclusion). Both have full cryptographic properties; they're just different cryptographic claims than CONSENT's. The prompt's framing of Option C as "loses CONSENT primitive properties" presupposes that CONSENT properties are the right ones for agent actions. They aren't. |

### Recommendation: Option C (with operator confirmation)

Recommend **Option C — locate agent action authorization in AgentScope.sol
and AuditLog.sol; do NOT extend or duplicate CONSENT** for these reasons:

1. **CONSENT was designed for a specific semantic class** —
   gamer-self-sovereign data processing consent (per INV-CONSENT-003
   and the BP-002 framing in `VAPI_BIOMETRIC_PRIVACY.md`). Extending it
   to cover agent action authorization stretches the primitive into a
   domain it wasn't designed for. Future protocol auditors reading
   "CONSENT v2 covers agents" may misread the cryptographic claim.

2. **The architecture document already proposes the right mechanisms**
   (`AgentScope.sol` for policy-bounded agent action authorization;
   `AuditLog.sol` for agent action records). The CONSENT extension
   was over-specified — those two contracts cover the semantics
   without requiring CONSENT to grow.

3. **CONSENT v1 stays FROZEN forever** for its designed purpose. INV-CONSENT-001
   is preserved without invoking the v2 escape clause. The
   five-primitives FROZEN-v1 family (GIC + WEC + VAME + CORPUS-SNAPSHOT
   + CONSENT) stays at five.

4. **"OPERATOR" can become the sixth FROZEN-v1 primitive** as
   architecture document section 8 envisions, without competing with
   AGENT-CONSENT for the slot.

5. **The cryptographic claim shifts to its honest formulation**:
   - Agent identity is attested via AgentRegistry + ioID DID + ERC-8004 + ERC-5484 SBT
   - Agent action authorization is proven by AgentScope policy match
   - Agent action history is recorded in AuditLog
   - Agent commits are EAS-attested with the AgentCommit chain
   These are FOUR distinct cryptographic claims, each at the right
   layer. Conflating them under "agent consent" weakens VAPI's
   external defensibility.

### Operator-vision dependency

This recommendation depends on the operator agreeing with the semantic
classification. **If the operator's vision is that agent action
authorization IS semantically a CONSENT-class operation** (a
specifically VAPI-architectural choice that "every action by any
identity is a consent record by that identity"), then Option A
(CONSENT v2) is the correct path. The operator's vision determines
which option is correct.

The verification standard mandates surfacing this ambiguity rather
than choosing silently. The recommendation here is Option C with the
caveat that the operator should confirm the semantic classification
before implementation. If the operator confirms agent actions are NOT
CONSENT-class, proceed with Option C. If they ARE, proceed with
Option A.

### Operator confirmation (2026-04-26)

The operator confirmed the scope-class semantic classification for
VAPI specifically. The reasoning is preserved in this permanent record
so future operators encountering this question can read why scope-class
was chosen over CONSENT-class.

**Architectural consistency**: VAPI separates gamer authorization
(CONSENT) from operator authorization (governance) as a foundational
design pattern. Agent capability is operator-governance, not
gamer-consent. Locating agent action authorization under CONSENT would
collapse the gamer/operator authorization boundary that the rest of
the protocol takes care to maintain.

**FROZEN-v1 preservation**: the CONSENT v1 commitment carries
architectural weight that should not be disturbed without overwhelming
necessity. Scope-class avoids the disturbance entirely. INV-CONSENT-001's
v2 escape clause exists for genuine privacy primitive evolution; burning
it on a classification that may not be CONSENT-class is expensive and
sets a precedent that other primitives may follow toward dilution.

**Extensibility**: scope-class scales gracefully as new agents and
capabilities are added through operator governance. Each new agent
gets its scope bundle defined in AgentScope; each new capability gets
an actionType in AuditLog. CONSENT-class would require ongoing
re-consent friction that compounds with each addition — every new
agent or capability would surface new consent prompts to gamers,
eroding the data-subject consent UX that CONSENT v1 was designed
specifically to provide.

**User mental model**: gamers reason about consent in terms of data
category usage (TOURNAMENT_GATE, ANONYMIZED_RESEARCH, MANUFACTURER_CERT,
MARKETPLACE). Agent operational machinery is not what they expect to
consent to per-action. Asking gamers to consent per-agent or per-action
would be a category error — the gamer has consented to data uses, and
the agents act within scopes the operator authorized to fulfill those
uses.

This confirmation locks Option C as the resolution for Conflict 2 and
permits the second design pass to proceed treating scope-class agent
authorization as a settled architectural decision.

### Architectural details for Option C

The recommendation requires the following design decisions in Phase O0
(no implementation in this session):

- **AgentScope.sol** retains its architecture-document-specified
  responsibility: store the policy Merkle root, expose verification
  queries that the bridge calls at request time. No agent-consent
  field. No category enum.
- **AuditLog.sol** retains its architecture-document-specified
  responsibility: nightly Merkle checkpoint of Tessera signed-tree-head
  + per-action records. The schema for action records can include an
  `actionType` field that encompasses what would have been "consent
  category" semantics if needed downstream (e.g.,
  `actionType="DATA_PROCESSING"` for actions that touch gamer
  biometric data).
- **VAPIConsentRegistry.sol** stays exactly as deployed
  (`0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA`). No schema change.
  No contract modification. The contract continues to serve
  gamer-self-sovereign data processing consent for its four
  categories.
- **`bridge/vapi_bridge/consent_categories.py`** stays FROZEN at v1.
  No new domain tag. No formula change. No category additions.
- **No AGENT-CONSENT primitive defined** at the FROZEN-v1 level.
- **The architecture document's framing on page 4 ("VAPIConsentRegistry
  extends consent records to capture the agent identity") becomes a
  documentation correction to make in a separate doc commit (not this
  session's responsibility per the prompt's constraint that "the
  document needs to be updated in a separate documentation commit
  that is not your responsibility to make in this session").**

### Confidence

**CAREFUL REASONING — RESOLVED 2026-04-26.** The recommendation depended
on the operator's view of whether agent action authorization is
semantically a CONSENT-class operation. The codebase strongly supported
Option C (CONSENT was designed for gamer-self-sovereign data consent;
AgentScope + AuditLog cover the agent-action concerns); the operator
confirmed the scope-class classification per the four reasons recorded
above (architectural consistency, FROZEN-v1 preservation, extensibility,
user mental model).

Option C is therefore the locked resolution for Conflict 2. Future
design passes treat scope-class agent action authorization as a settled
architectural decision; CONSENT v1 stays FROZEN for gamer-self-sovereign
data processing consent.

---

## Section 4 — Conflict 3 Resolution: Lane Collision

### Nature of the conflict

The architecture document section 5 (page 5) specifies path-based lane
ownership:

- Anchor Sentry owns `wiki/**`, `provenance/**`, `events/**`
- Guardian owns `ops/**`, `audits/**`, `invariants/**`

The verification document finding 4 establishes that existing
`wiki/audits/` and `wiki/sweeps/` subdirectories sit under Sentry's
`wiki/**` lane but are content-typed as Guardian's domain (audit work,
sweep results). Path-based CODEOWNERS rules cannot cleanly enforce
lane discipline until this collision is resolved.

**Codebase ground truth**:

- Live filesystem audit (this session): `wiki/audits/` and `wiki/sweeps/`
  exist with the following content:
  - `wiki/audits/contradictions.md` — distinct from
    `wiki/contradictions.md` (top-level); appears to be a separate
    audit-style document
  - `wiki/audits/phase_224_legacy_endpoint_audit.md` — historical
    Phase 224 audit
  - `wiki/sweeps/sweep_20260426_clean.md` — Skill 14 sweep output from
    the Phase 237.5 Path C+ session
- `vapi_wiki_engine.py:108` — `WIKI_SWEEPS = WIKI / "sweeps"` (the
  engine constant for sweep output path).
- `vapi_wiki_engine.py:329` — `init_wiki()` includes WIKI_SWEEPS in its
  directory list creation.
- `vapi_wiki_engine.py:701` — `cmd_ingest_sweep` writes to `WIKI_SWEEPS /
  f"sweep_{ts[:10].replace('-', '')}_{status.lower()}.md"`.
- `vapi_wiki_engine.py:112` — `WIKI_CONTRADICT = WIKI / "contradictions.md"`
  (top-level, NOT inside wiki/audits/). `bridge/vapi_bridge/fleet_signal_coherence_agent.py:1145, 1165`
  imports and uses `WIKI_CONTRADICT` to append FSCA findings.
- **`wiki/audits/contradictions.md` is therefore a distinct file** from
  `wiki/contradictions.md` — the FSCA-driven contradictions registry is
  at top-level wiki/, NOT in wiki/audits/. The wiki/audits/contradictions.md
  appears to have been manually created (no engine writer found via
  grep).

**No CODEOWNERS file exists anywhere** (per V9 verification finding) —
the entire path-ownership pattern is greenfield. This is good news for
migration: nothing references CODEOWNERS rules to break during reorg.

### Evaluation of the three options

Three criteria from the prompt: (1) preservation of lane discipline,
(2) architectural clarity of where audit and sweep content lives,
(3) migration cost and risk to existing wiki engine functions and
documentation.

**Option A — Move `wiki/audits/` to `audits/` and `wiki/sweeps/` to `sweeps/`**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Lane discipline | **STRONG** | Perfect path-based ownership: `wiki/**` is purely Sentry's, `audits/**` and `sweeps/**` are purely Guardian's. CODEOWNERS rules become unambiguous. |
| (2) Architectural clarity | **STRONG** | Top-level `audits/` and `sweeps/` are the obvious locations for operational audit/sweep work. Future operators looking for audit results know where to look. |
| (3) Migration cost | **MODERATE** | Three files move (`wiki/audits/contradictions.md`, `wiki/audits/phase_224_legacy_endpoint_audit.md`, `wiki/sweeps/sweep_20260426_clean.md`). One engine constant updates (`WIKI_SWEEPS` at `vapi_wiki_engine.py:108`). One init list updates (`vapi_wiki_engine.py:329`). Documentation references in CLAUDE.md / VAPI_CONTEXT.md / VAPI_MEMORY.md / wiki/phases/phase_237_5.md / Phase 237.5 Path C+ commit message — all need text updates if they cite the old paths (text references stay valid as historical truth at commit time but path-as-resolved would break). Quantitatively: ~5-10 file modifications, single atomic commit. |

**Option B — Sentry keeps `wiki/audits/`, Guardian uses `ops/audits/`**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Lane discipline | **MODERATE** | Discipline preserved if you treat `wiki/audits/` as a specific Sentry sub-domain (audit-as-doc) and `ops/audits/` as Guardian's audit lane. But this means audit content is split by *when it was produced*, which is brittle. Future operators may write to either path depending on context, eroding the boundary. |
| (2) Architectural clarity | **WEAKER** | Two locations for audit content based on a temporal boundary is confusing. Search "where do I find audit X" returns ambiguous answer. Phase 224 audit and Phase 237.5 sweep go into Sentry territory; future Guardian audit goes into ops/audits/. The semantic split (doc vs operational) is real but not self-explanatory. |
| (3) Migration cost | **STRONG** | Zero migration. Existing files stay where they are. New Guardian work goes to new path. |

**Option C — Hybrid shared territory with handoff protocols**:

| Criterion | Score | Reasoning |
|---|---|---|
| (1) Lane discipline | **WEAK** | "Shared territory" violates lane discipline by definition. The architecture document's two-agent partnership pattern is designed to AVOID shared writes (per page 5: "Both read everything; only one writes each path"). Specifying which agent handles which aspect within a path introduces coordination overhead — exactly what lane discipline was designed to eliminate. |
| (2) Architectural clarity | **WEAK** | Path-based ownership with intra-path responsibility splits is not path-based ownership. Operators reading the design must learn additional rules (which agent does what within wiki/audits/) on top of the path lookup. |
| (3) Migration cost | **STRONG** | Zero migration. Existing files stay where they are. |

### Recommendation: Option A

Recommend **Option A — move `wiki/audits/` to `audits/` and
`wiki/sweeps/` to `sweeps/`** for these reasons:

1. **Lane discipline is the foundational principle of the two-agent
   partnership** per architecture document section 5. The whole
   design depends on path-based ownership being unambiguous. Option A
   produces unambiguous path-based ownership; Options B and C do not.
   The prompt's first criterion is specifically about preservation of
   this principle.

2. **Migration cost for THIS repo state is small** — three files,
   one engine constant, ~5-10 file modifications. The "real
   reorganization" framing the prompt uses is accurate but
   quantitatively modest. The Phase 237.5 Path C+ session already
   demonstrated this codebase can handle multi-file atomic commits
   (commit `f1a9f3f2` touched 13 files).

3. **The future cost of NOT migrating is larger.** Every future
   audit file that goes into `wiki/audits/` (instead of `audits/`)
   compounds the collision. Resolving now while only 3 files exist
   is cheaper than resolving later when 30+ files exist.

4. **Top-level `audits/` and `sweeps/` align with how operators
   intuitively search for audit/sweep content.** "Where do I find
   the audit results?" → `audits/`. Self-evident.

5. **CODEOWNERS rules become trivial to write and maintain**:
   ```
   wiki/**     @vapi-anchor-sentry[bot]
   provenance/** @vapi-anchor-sentry[bot]
   events/**   @vapi-anchor-sentry[bot]
   ops/**      @vapi-guardian[bot]
   audits/**   @vapi-guardian[bot]
   sweeps/**   @vapi-guardian[bot]
   invariants/** @vapi-guardian[bot]
   ```
   Six lines, no exceptions, no special cases.

### Architectural details for Option A

Migration plan (design only; no implementation in this session):

**File moves** (use `git mv` to preserve history):
1. `git mv wiki/audits/contradictions.md audits/contradictions.md`
2. `git mv wiki/audits/phase_224_legacy_endpoint_audit.md audits/phase_224_legacy_endpoint_audit.md`
3. `git mv wiki/sweeps/sweep_20260426_clean.md sweeps/sweep_20260426_clean.md`
4. `rmdir wiki/audits/` and `rmdir wiki/sweeps/` (after moves complete)

**Engine constant updates** (`vapi_wiki_engine.py`):
- Line 108: `WIKI_SWEEPS = WIKI / "sweeps"` → new constant
  `SWEEPS_DIR = Path("sweeps")` (top-level path)
- Line 329 (or wherever `init_wiki` enumerates init dirs): remove
  `WIKI_SWEEPS` from the WIKI subdir init list; add `SWEEPS_DIR.mkdir(parents=True, exist_ok=True)`
  to a parallel init step OR include in a new top-level init list
- Line 701: `sweep_path = WIKI_SWEEPS / f"sweep_..."` → `sweep_path = SWEEPS_DIR / f"sweep_..."`
- Update header docstring at line 52 from "v writes wiki/sweeps/" to
  "writes sweeps/"

**Documentation reference sweeps** (text-only updates; preserve historical
references in commit messages but update working-document references):
- `CLAUDE.md` — search for `wiki/sweeps/` and `wiki/audits/`; update
  any working-document references to `sweeps/` and `audits/`
- `VAPI-WORKFLOW.v2/VAPI_CONTEXT.md` — same scan
- `VAPI-WORKFLOW.v2/VAPI_MEMORY.md` — same scan (Section 10 has
  `monitoring/skill14_phase237_5.json; ingested as
  wiki/sweeps/sweep_20260426_clean.md` — update)
- `wiki/phases/phase_237_5.md` — has explicit reference to
  `wiki/sweeps/sweep_20260426_clean.md` — update
- `monitoring/skill14_phase237_5.json` — has reference to wiki/sweeps/ —
  update

**CODEOWNERS file creation** (Phase O0 work; design only here):
- Create `CODEOWNERS` at repo root or `.github/CODEOWNERS` (GitHub
  convention is `.github/CODEOWNERS`)
- Encode the 6 rules above
- Apply branch protection on `main` requiring CODEOWNERS approval

**Atomic commit shape**: single commit titled "Phase O0 Design Pass 1 —
lane reorganization (wiki/audits → audits/, wiki/sweeps → sweeps/)"
covering all moves + engine update + documentation references. Tests
should still pass post-migration since no test references the old
paths (verifiable by grep before commit).

### Confidence

**HIGH CONFIDENCE.** The codebase evidence supports Option A
unambiguously. Lane discipline is the foundational architecture
principle and Options B and C compromise it. Migration cost is
genuinely small for the current repo state. No legitimate trade-off
favors B or C over A in this codebase context.

---

## Section 5 — Cross-Conflict Integration Analysis

The three conflicts are not entirely independent. Examining the
recommended resolutions for interactions:

### Interaction 1: Conflict 1 (Option A) × Conflict 2 (Option C)

Recommendation A for Conflict 1 deploys `AgentAdjudicationRegistry.sol`
with `requireAgentScope` modifier. Recommendation C for Conflict 2
locates agent action authorization in AgentScope.sol and AuditLog.sol.

**Interaction**: AgentScope.sol is the policy primitive that
`requireAgentScope` modifier on AgentAdjudicationRegistry queries.
Architecture document section 4 already establishes this:
"AgentScope.sol stores a Merkle root of the policy bundle (Cedar or
Rego) the bridge verifies against at request time." The modifier on
the new contract is the on-chain enforcement of what AgentScope
declares.

**Coherence**: ✅ STRONGLY COHERENT. Both recommendations point in the
same direction — agent-scoped enforcement at the contract layer,
backed by AgentScope's policy bundle, recorded in AuditLog. The
two recommendations reinforce each other.

### Interaction 2: Conflict 1 (Option A) × Conflict 3 (Option A)

Recommendation A for Conflict 1 deploys a new contract address in
`contracts/deployed-addresses.json`. Recommendation A for Conflict 3
moves files and updates `vapi_wiki_engine.py` paths.

**Interaction**: Both involve atomic-commit work with documentation
reference updates. The Phase 237.5 Path C+ pattern (commit
`f1a9f3f2`) demonstrated the discipline — single atomic commit with
multi-file changes including doc updates. The Phase O0 Design Pass 1
implementation (when authorized) would follow the same pattern but
across two distinct atomic commits (one for the contract deploy + chain
wrapper; one for the lane reorganization).

**Coherence**: ✅ COHERENT. The two atomic commits are independent
(deploy commit doesn't touch wiki paths; lane commit doesn't touch
contracts) so they can ship in either order without interaction.

### Interaction 3: Conflict 2 (Option C) × Conflict 3 (Option A)

Recommendation C for Conflict 2 keeps CONSENT primitives untouched.
Recommendation A for Conflict 3 moves audit/sweep files but does not
touch consent infrastructure.

**Interaction**: None directly. Consent infrastructure
(`bridge/vapi_bridge/consent_categories.py`,
`contracts/contracts/VAPIConsentRegistry.sol`,
`bridge/vapi_bridge/store.py:consent_ledger`) lives outside both
the audit/sweep paths and the agent-scope contract paths.

**Coherence**: ✅ COHERENT. No interaction; no risk of conflict.

### Cross-conflict whole-design coherence

The three recommendations together produce a coherent architectural
position:

1. **CONSENT v1 stays FROZEN** for gamer-self-sovereign data
   processing consent (Conflict 2 / Option C).
2. **Agent action authorization lives in AgentScope (policy) +
   AuditLog (records) + AgentAdjudicationRegistry (enforcement)** —
   three separate primitives each at the right layer (Conflict 1
   Option A + Conflict 2 Option C).
3. **Lane discipline becomes path-clean** — `wiki/**` is Sentry's
   provenance domain; `audits/**` and `sweeps/**` are Guardian's
   operational domain (Conflict 3 Option A).
4. **Phase 237.5's CORPUS_SNAPSHOT path is preserved** — existing
   `AdjudicationRegistry` continues to serve recordAdjudication
   calls; Phase 237.5 inaugural anchor lands cleanly when wallet is
   funded (Conflict 1 Option A).
5. **Future migration paths are clear** — CORPUS_SNAPSHOT can
   migrate to `AgentAdjudicationRegistry` when CORPUS_SNAPSHOT
   becomes an agent action in Phase O5+; CONSENT v2 remains
   available via INV-CONSENT-001's escape clause if ever needed for
   a future genuine privacy primitive extension.

The three recommendations form a coherent architectural whole: each
primitive serves its designed purpose, each agent has unambiguous
write authority, each cryptographic claim is at the right layer.

---

## Section 6 — Open Questions for Second Design Pass

These questions arose during this design pass's reasoning but cannot
be answered by this pass. They are inputs to the second design pass,
not blockers to this pass's completion.

1. **Operator semantic confirmation for Conflict 2**: does the
   operator agree that agent action authorization is NOT a
   CONSENT-class operation (favoring Option C), or is the
   architecture document's framing of "every agent action is a
   consent record by the agent's registered identity" the operator's
   actual vision (favoring Option A — CONSENT v2)? This is the load-
   bearing question for the Conflict 2 recommendation.

2. **Future migration of CORPUS_SNAPSHOT to agent-scoped contract**:
   when Anchor Sentry is live (Phase O5+), CORPUS_SNAPSHOT anchoring
   becomes an agent action and naturally migrates from
   `AdjudicationRegistry` to `AgentAdjudicationRegistry`. The migration
   pattern needs design specification: do we deploy a CORPUS_SNAPSHOT
   v2 with migration semantics, or deprecate-in-place with a flag in
   chain.py routing? Out of scope here; surfaces in the second design
   pass's Phase O5 work.

3. **Bridge routing pattern for two adjacent registries**: Conflict 1
   recommendation introduces `AgentAdjudicationRegistry` alongside
   the existing `AdjudicationRegistry`. The chain.py wrapper pattern
   needs to be specified: do `record_adjudication`,
   `anchor_corpus_snapshot`, and the new `anchor_agent_action` each
   maintain their own ABI / contract reference, OR is there a unified
   anchor abstraction with per-call-site contract selection? The
   prompt prohibits code in this design pass; this question goes to
   the second pass.

4. **CODEOWNERS file location**: GitHub convention supports both
   `CODEOWNERS` at repo root and `.github/CODEOWNERS`. Both work
   identically functionally; the choice is conventional. Recommend
   `.github/CODEOWNERS` for consistency with `.github/INVARIANTS_ALLOWLIST.json`
   already at that location.

5. **wiki/contradictions.md disposition**: this top-level file is
   FSCA's live output (per `vapi_wiki_engine.py:112` and
   `bridge/vapi_bridge/fleet_signal_coherence_agent.py:1145, 1165`).
   It is content-typed audit-style work but lives at top-level
   wiki/ rather than wiki/audits/. The Conflict 3 recommendation
   doesn't move it because it wasn't called out as a collision in the
   verification finding 4. Question for second design pass: should
   wiki/contradictions.md also move to audits/contradictions.md (and
   FSCA's writer be updated)? If yes, the file path collision with
   the existing wiki/audits/contradictions.md needs reconciliation —
   they're two different files with the same name.

6. **Architecture document corrections**: the verification surfaced
   that the architecture document's framing on (a) extending CONSENT
   to non-human consenters (Conflict 2) and (b) treating wiki/audits/
   as if it didn't already exist (Conflict 3) are both inaccurate
   relative to the codebase ground truth. The prompt explicitly says
   the document needs updates "in a separate documentation commit
   that is not your responsibility to make in this session." Question
   for the operator: should those corrections go into a new
   architecture document v2, or into errata appended to the existing
   document, or into the wiki/proposals/ design-pass documents
   themselves (linked from the architecture document)?

7. **Possible fourth conflict surfaced during this work** — the
   architecture document references "the 28 frozen invariants" at
   page 8 ("the 28 frozen invariants protected by the PV-CI gate
   become the agent's test oracle") and at the agent definition file
   YAML at page 11 ("self-check against the 28 invariants"). The
   live invariant count is **30**, not 28, per
   `VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md:419` ("invariant count history:
   ... 26 (Phase 235-ULTRAREVIEW) → 30 (Phase 237-EXTEND with
   INV-CONSENT-001..004)") AND the live PV-CI gate output from this
   session's earlier work shows "28/28 invariants verified" — wait,
   re-checking: the gate as of Phase 237.5 Path C+ commit `f1a9f3f2`
   added INV-CORPUS-001 and INV-CORPUS-002 making the count 28 in the
   gate but VAPI_INVARIANTS.md documents 30 (apparently INV-CONSENT-001..004
   are documented in VAPI_INVARIANTS.md but not all four wired into
   the PV-CI gate's `INVARIANTS` list). This is a **documentation
   drift** between the markdown specification and the gate
   implementation. **NOT a fourth architectural conflict** — both
   numbers are coherent within their own scope (PV-CI gate enforces
   28; VAPI_INVARIANTS.md documents 30 named invariants). But the
   architecture document's reference to "28 frozen invariants" needs
   to track which number is canonical: gate-enforced (28) or
   documented (30). Surface for second design pass to align before
   writing the agent's self-check logic against either number.

---

## Surprising vs. expected reasoning (per prompt's closing instruction)

### Recommendations that produced confident reasoning

**Conflict 1 (Option A — parallel `AgentAdjudicationRegistry`)**:
HIGH CONFIDENCE. The codebase evidence supports this strongly. Phase
237.5 preservation is non-negotiable and Option A delivers it
maximally. The cryptographic claim strength criterion is satisfied at
full strength. The architectural cleanliness trade-off (two contracts
vs one) is mitigated by naming discipline that matches existing VAPI
patterns (e.g., VAPIConsentRegistry alongside VAPIBiometricGovernance).
The operator can review with confidence; the codebase supports the
choice.

**Conflict 3 (Option A — move audits/sweeps to top-level)**: HIGH
CONFIDENCE. Lane discipline is foundational; Options B and C
compromise it. Migration cost is genuinely small (3 files, 1 engine
constant, ~5-10 modifications) for the current repo state. The future
cost of not migrating compounds linearly with new audit files added.
No legitimate trade-off favors B or C over A in this codebase
context. The operator can review with confidence; the codebase
supports the choice.

### Recommendation that produced careful reasoning (resolved 2026-04-26)

**Conflict 2 (Option C — locate agent action authorization in
AgentScope + AuditLog)**: CAREFUL REASONING at the time of writing,
RESOLVED on operator confirmation 2026-04-26. The recommendation
depended on the operator's view of whether agent action authorization
is semantically a CONSENT-class operation or a policy/scope-class
operation. The codebase strongly supported Option C: CONSENT was
designed for gamer-self-sovereign data processing consent (per
INV-CONSENT-003 and BP-002 framing); AgentScope and AuditLog were
designed for the agent action concerns.

The operator confirmed the scope-class classification on four grounds
(architectural consistency, FROZEN-v1 preservation, extensibility,
user mental model) — see the "Operator confirmation (2026-04-26)"
subsection inside Section 3 for the complete reasoning. Option C is
the locked resolution; CONSENT v1 stays FROZEN for gamer-self-sovereign
data processing consent; agent action authorization lives in
AgentScope (policy bounds) + AuditLog (action records) +
AgentAdjudicationRegistry (contract-layer enforcement, per Conflict 1
Option A).

All three Design Pass 1 recommendations are now operator-approved and
serve as resolved inputs to Design Pass 2.

---

This document holds for review. No code. No contract modifications.
No bridge updates. No agent definition files. No commits.
