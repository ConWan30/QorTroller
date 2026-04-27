# Phase O0 — Design Pass 2B: V11 Conceptual Alignment

**Status**: APPROVED 2026-04-27. Path 3 confirmed by operator —
PHYSICAL_DATA_ATTESTATION v1 ships as the seventh FROZEN-v1 primitive
hosted on AgentAdjudicationRegistry. Reasoning preserved in Section 6's
"Operator confirmation (2026-04-27)" subsection as the permanent
architectural record. This document is the design record;
implementation work proceeds in Pass 2C with this and all prior
resolved inputs as foundational decisions. No code or contract changes
ship as part of this commit — this is a standalone documentation
commit.

**Scope discipline**: addresses exactly the V11 conceptual alignment
finding from `wiki/proposals/PHASE_O0_VERIFICATION.md` (Section 1, V11,
lines 605-708). Does NOT address Phase O0 implementation plan
(reserved for Pass 2C). Does NOT propose modifications to the resolved
decisions from Design Pass 1 or Pass 2A — those are settled inputs.

**Resolved inputs from prior design passes** (not open for revision):

From **Design Pass 1**:
1. Parallel `AgentAdjudicationRegistry` contract for agent-scoped
   anchoring; existing `AdjudicationRegistry` at
   `0x44CF981f46a52ADE56476Ce894255954a7776fb4` untouched.
2. Agent action authorization is scope-class (AgentScope + AuditLog +
   AgentAdjudicationRegistry) rather than CONSENT-class.
3. `wiki/audits/` and `wiki/sweeps/` move to top-level `audits/` and
   `sweeps/`.

From **Pass 2A**:
4. Wallet funding to 5 IOTX target (operator action; full 16-20 week
   initiative envelope).
5. OAuth 2.1 client credentials + HMAC request signing in Phase O0;
   mTLS via SPIFFE/SPIRE deferred to P3+.
6. Separate `scripts/vapi_path_scope_gate.py` + new GitHub Actions
   workflow for per-author path scope checking.
7. AGENT_COMMIT v1 as the sixth FROZEN-v1 primitive, hosted on
   `AgentAdjudicationRegistry`; no EAS deployment to IoTeX.
8. Audience clarity: VAPI's future consumers are businesses and
   institutions evaluating data sovereignty infrastructure, with
   physiological data as a catalyst for gamer data ownership claims.

**Verification standard**: every architectural claim cites `file:line`
or external-source verification. Where the codebase cannot resolve an
ambiguity, the ambiguity is surfaced as a question for operator
decision rather than chosen silently. This pass is conceptual analysis
rather than codebase-driven recommendation; the operator's vision is
the deciding factor.

**Date**: 2026-04-27

---

## Section 1 — Executive Summary

### The conceptual question

The architecture as written makes cryptographic claims about agent
identity (who took an action) and bounded action scope (what scope the
action falls within). Per the verification document V11 (lines 605-708),
these claims do NOT directly express the binding between agent actions
and hardware-derived data flows. The operator's stated vision includes
cryptographic attestation that connects real-world hardware and IoT
device data to AI through the agents themselves, with physiological
data serving as a catalyst for gamer data ownership claims and the
audience being businesses and institutions evaluating data sovereignty
infrastructure.

The conceptual gap is between:

- **What the architecture currently expresses**: "agent identity X
  performed action Y within scope Z, recorded on-chain at time T."
- **What the operator envisions**: "agent identity X serves as a
  verification primitive between physical-world data flow Z and the
  digital protocol, cryptographically binding hardware-derived data to
  the agent's attestation in a manner auditable by businesses and
  institutions."

The first formulation is verifiable through the chain of existing VAPI
primitives (PoAC records, CORPUS-SNAPSHOT v1, AGENT_COMMIT v1, etc.).
The second formulation requires either a stronger reading of those
existing primitives (Path 1, with extensive auditor documentation) OR a
new architectural surface that makes the binding explicit (Paths 2 and
3).

### The three paths

**Path 1 — Accept the architecture as written**: The four contracts
(AgentRegistry, AgentScope, AgentSlashing, AuditLog) ship as designed.
The cryptographic claim is "agent identity X took action Y within scope
Z." The connection to hardware-derived data flows is implicit, derived
from chains of existing primitives. Auditors who want to verify
hardware-data binding walk a multi-step chain through VAPI's existing
primitive family.

**Path 2 — Extend AgentRegistry with `attestationCapability` fields**:
Each registered agent declares a typed enumeration of physical-data
domains they are authorized to attest to. The cryptographic claim
becomes "agent identity X with declared attestation capability C took
action Y about hardware-data flow Z." Authorization to attest to a
domain is explicit at registration; binding from action to specific
hardware-data instance remains derived from the primitive chain.

**Path 3 — Build PHYSICAL_DATA_ATTESTATION v1 as a new FROZEN-v1
primitive**: A seventh FROZEN-v1 primitive directly captures the
binding between hardware-derived data, the agent that produced or
verified an attestation about that data, and the on-chain commitment
anchoring the attestation. The cryptographic claim becomes "agent
identity X cryptographically attested to hardware-data flow Z, with
the attestation chain anchored on AgentAdjudicationRegistry." The
physical-to-digital bridge becomes a first-class primitive.

### Overall assessment

The audience clarity established during Pass 2A — businesses and
institutions evaluating VAPI's data sovereignty infrastructure — places
weight on the auditability of the cryptographic claim. Path 3 produces
the strongest direct claim: a single primitive that an auditor can
verify with one hash recomputation rather than a multi-step chain
inference. Path 1 produces the leanest architecture but the weakest
direct claim, requiring auditors to combine multiple primitives plus
documentation to derive what Path 3 expresses natively. Path 2 is a
compromise that adds authorization clarity (a real gain) but does not
solve the binding-vs-authorization distinction (the load-bearing
concern).

This pass's analysis suggests Path 3 best matches the audience clarity
established in Pass 2A. **But this is a conceptual question where the
operator's vision is the deciding factor and the codebase cannot
resolve the choice.** Reasonable operators with different priorities —
particularly operators who weigh architectural leanness against direct
expressiveness, or who view the FROZEN-v1 family's growth as a cost
that should be minimized — could legitimately choose Path 1 or Path 2.
Section 6's recommendation is framed as architectural analysis, not as
a definitive answer.

---

## Section 2 — Path One Analysis: Accept the Architecture as Written

### The path's specific architectural changes

Path 1 makes no changes beyond the architecture document's original
specification plus the resolved inputs from Design Pass 1 and Pass 2A.
Phase O0 deploys the four contracts (AgentRegistry, AgentScope,
AgentSlashing, AuditLog) plus AgentAdjudicationRegistry per Design Pass
1 Conflict 1. AGENT_COMMIT v1 ships as the sixth FROZEN-v1 primitive
per Pass 2A V10 Option C.

The `AgentRegistry` schema is the architecture document's specification
verbatim: `(agentId → publicKey, scopeHash, status)` per V1 finding
(verification doc lines 49-59). No `attestationCapability` field. No
new primitive. No new contracts beyond what Pass 2A authorized.

### The cryptographic claim the path produces

The cryptographic claim under Path 1 is the conjunction of multiple
primitive-level claims:

- **Identity claim**: agent X is registered as an Operator (per
  AgentRegistry).
- **Scope claim**: action Y falls within agent X's declared
  scopeHash (per AgentScope.sol policy bundle Merkle root).
- **Action claim**: agent X took action Y at time T, anchored on-chain
  via AgentAdjudicationRegistry (per AGENT_COMMIT v1 attestation hash).
- **Audit claim**: action Y appears in agent X's AuditLog Merkle
  history (per AuditLog.sol nightly checkpoint).

The cryptographic claim about hardware-derived data is not a primitive-
level claim. It is a **derived claim** that the auditor reconstructs by
chaining: AGENT_COMMIT → CORPUS-SNAPSHOT (or other VAPI primitive
referenced by the commit) → bridge-side data structures (e.g.,
`ait_session_log` rows) → individual session captures → PoAC records
→ controller hardware ECDSA-P256 keys.

### Audit trail walk-through

**Scenario**: Anchor Sentry produces an AGENT_COMMIT v1 attestation
to a CORPUS-SNAPSHOT v1 capturing the AIT separation ratio (1.199, N=37
per CLAUDE.md "Calibration Corpus State 2026-04-11" line 233). The
underlying biometric tremor FFT data was captured from three gamers'
DualShock Edge controllers. A business auditor — call them TrustCo, a
hypothetical institutional analyst evaluating VAPI for licensing as a
biometric data sovereignty substrate — wants to verify the cryptographic
chain from Anchor Sentry's commit back to the original controller
hardware.

The audit walk under Path 1:

1. **TrustCo queries AgentAdjudicationRegistry** for the AGENT_COMMIT
   anchor by `tx_hash`. Returns the on-chain record:
   `(actionHash, agentId, "AGENT_COMMIT", blockNumber)`.
2. **TrustCo verifies the AGENT_COMMIT v1 hash formula** off-chain:
   `actionHash = SHA-256(b"VAPI-AGENT-COMMIT-v1" || agent_id ||
   commit_sha || prev_commit_hash || repo_uri_sha || ts_ns_be)`. They
   need the source values to recompute. These come from VAPI's
   `agent_commit_log` SQLite table (per Pass 2A Section 3
   architectural details). TrustCo queries
   `GET /agent/agent-commit-history?commit_sha=...` to retrieve them.
3. **TrustCo verifies agent_id resolves to Anchor Sentry** via
   `AgentRegistry.getAgent(agentId)` — returns publicKey, scopeHash,
   status. They confirm Anchor Sentry is registered and active.
4. **TrustCo verifies action scope** by checking the AgentScope policy
   bundle's Merkle root matches the on-chain record. The agent had
   authority to make AGENT_COMMIT actions within the scope at the
   time of the commit.
5. **TrustCo follows commit_sha to git repository state**. The
   AGENT_COMMIT references a specific git commit. Git commits are
   off-chain; TrustCo clones the repo and verifies commit_sha exists.
6. **The git commit modifies wiki content** — say,
   `wiki/phases/phase_X.md` (or new top-level paths post Design Pass 1
   Conflict 3 lane reorganization). The wiki content references a
   specific `corpus_snapshot_log` row by `snapshot_commitment` hash.
7. **TrustCo queries** `GET /agent/corpus-snapshot-status` with that
   `snapshot_commitment` and retrieves the source values:
   `(wiki_hash, agent_root, ratio_milli, corpus_n, ts_ns)`.
8. **TrustCo recomputes the CORPUS-SNAPSHOT v1 hash** per the formula
   at `bridge/vapi_bridge/corpus_snapshot.py:25-36`:
   `commitment = SHA-256(b"VAPI-CORPUS-SNAPSHOT-v1" (23B) || wiki_hash
   (32B) || agent_root (32B) || ratio_milli_be (8B) || corpus_n_be (8B)
   || ts_ns_be (8B))`. Match confirms the snapshot is the one Anchor
   Sentry committed to.
9. **TrustCo verifies the on-chain anchor** of the CORPUS-SNAPSHOT
   per Phase 237.5 — the snapshot_commitment is also recorded on
   AdjudicationRegistry (the legacy contract, not
   AgentAdjudicationRegistry, per Design Pass 1 Conflict 1's
   "CORPUS_SNAPSHOT can migrate later" framing).
10. **TrustCo wants to reach the underlying tremor data**. The
    snapshot's `corpus_n=37` indicates 37 sessions contributed to the
    AIT separation ratio. But CORPUS-SNAPSHOT v1 doesn't enumerate
    those sessions directly — it captures their collective state
    through `wiki_hash + agent_root + ratio_milli + corpus_n`. TrustCo
    must query VAPI's bridge for the AIT session list at or before
    `ts_ns`.
11. **TrustCo queries** `GET /agent/ait-separation-status` for the
    `ait_session_log` rows. The bridge returns 37 rows with
    `per_player_features_json` (per `store.py:13639-13768` — the
    Phase 235-DASH-UPGRADE-3 schema field). Each row contains tremor
    FFT features for a single session.
12. **For each session, TrustCo traces to PoAC records**. The session
    references PoAC records (228-byte signed records). Each PoAC has
    chain link hash `SHA-256(raw[:164])` per the FROZEN PoAC wire
    format (CLAUDE.md "PoAC Wire Format" line 195). TrustCo verifies
    the chain link integrity for the session's PoAC sequence.
13. **For each PoAC, TrustCo verifies** `device_id = keccak256(pubkey)`
    points to a registered DualShock Edge controller via
    `VAPIioIDRegistry` (per V3 verification: contract LIVE at
    `0x0A7e595C7889dF3652A19aF52C18377bF17e027D`).
14. **Finally, TrustCo traces** the controller's pubkey to the
    DualShock Edge ECDSA-P256 hardware secure element. This is the
    "hardware sensor" terminus — the tremor data physically originated
    from the IMU + analog stick reading by this specific controller.

**Audit chain length**: 14 steps. Crosses 5 distinct primitives
(AGENT_COMMIT, CORPUS-SNAPSHOT, PoAC, ioID, hardware identity), 2
on-chain contracts (AgentAdjudicationRegistry, AdjudicationRegistry,
plus VAPIioIDRegistry for hardware lookup), and 3 off-chain query
surfaces (corpus_snapshot_log, ait_session_log, agent_commit_log).

### What TrustCo can verify cryptographically vs what they must infer

**Cryptographically verifiable**:
- Agent identity registration (Step 3)
- AGENT_COMMIT v1 hash (Step 2)
- CORPUS-SNAPSHOT v1 hash (Step 8)
- On-chain CORPUS-SNAPSHOT anchor (Step 9)
- Per-PoAC chain link hash (Step 12)
- Device public key registration (Step 13)
- The hardware secure element produced the signature on each PoAC
  (assuming hardware certification path is verified)

**Must be inferred from chain or trusted from VAPI documentation**:
- The connection between AGENT_COMMIT and the specific
  `corpus_snapshot_log` row (Steps 5-7) — git commit content
  references it, but the reference is in markdown text rather than a
  cryptographic field of AGENT_COMMIT v1 itself.
- The connection between CORPUS-SNAPSHOT v1 commitment and the
  specific 37 sessions (Steps 10-11) — the snapshot captures
  aggregate state (`corpus_n + ratio_milli + agent_root`), not
  enumerated session list. Auditor must trust that the bridge's
  `ait_session_log` rows at `ts_ns` are the ones that produced the
  ratio.
- The connection between session and underlying tremor FFT data is
  through `per_player_features_json` (off-chain bridge field).
- The connection between AGENT_COMMIT (the action) and the specific
  physical-data sensor output (the entire derived chain).

### Cryptographic claim TrustCo can make at the end

> "VAPI's primitives, when chained together with off-chain bridge
> queries, produce a verifiable trail from Anchor Sentry's
> AGENT_COMMIT to a specific CORPUS-SNAPSHOT, which references 37
> biometric sessions captured at or before the snapshot timestamp,
> which in turn reference per-controller PoAC records signed by
> controller hardware ECDSA-P256 keys registered on VAPIioIDRegistry."

This is verifiable but indirect. The claim is "the chain is
consistent" rather than "this agent cryptographically attested to
this hardware-data flow."

### New architectural complexity

Path 1 introduces **zero new architectural complexity** beyond what
Pass 2A already authorized. The agent contracts ship as designed.
AGENT_COMMIT v1 is the sixth FROZEN-v1 primitive.

What Path 1 does require to make the audit story work:

- **Auditor documentation**: VAPI must publish a comprehensive guide
  for businesses and institutions explaining how to walk the audit
  chain. The 14 steps above need to be turned into a published audit
  protocol with example queries, reference implementations of each
  hash recomputation, and clear language about what is verifiable
  cryptographically vs derived from chain inference.
- **Off-chain query API stability**: TrustCo's audit relies on
  `GET /agent/corpus-snapshot-status`, `GET /agent/ait-separation-status`,
  `GET /agent/agent-commit-history`, etc. These endpoints become
  audit surfaces and must be versioned with audit-trail stability
  guarantees (auditors who recorded queries today must still get
  matching results in 5 years).
- **Rich event indexing**: business audit workflows benefit from
  searchable indices of past attestations. Path 1 means VAPI must
  build/maintain its own indexer — there's no EAS GraphQL fallback
  (per Pass 2A V10 Option C).

### Strengths against the operator's stated vision

- **Architectural leanness**: no new primitive, no schema additions to
  existing primitives, no expansion of the FROZEN-v1 family. The
  protocol stays as architecturally simple as Pass 2A's outcome.
- **Permitted divergence between primitive design and audit narrative**:
  the audit story can be marketed and updated independently of the
  contracts. If VAPI later identifies a better way to walk the chain,
  the audit guide updates without touching deployed contracts.
- **Reuse of existing primitive expressiveness**: the existing
  primitives (PoAC, CORPUS-SNAPSHOT, CONSENT, etc.) already encode the
  hardware-data binding implicitly. Path 1 honors that work rather
  than duplicating it.

### Weaknesses against the operator's stated vision

- **Audit chain length is the weakness**. A 14-step audit walk is
  meaningfully harder for businesses and institutions to perform than
  a 2-3 step walk. Compliance teams typically prefer claims they can
  verify in a single contract call or a single hash recomputation.
- **Claim formulation does not match vision wording**. The operator's
  vision wording is "cryptographic attestation that connects real-
  world hardware to AI through the agents." Path 1's primitive-level
  claim is "agent identity X took action Y within scope Z." The
  hardware-to-AI connection lives in markdown documentation, not in
  the primitive itself.
- **Indirect claim is harder to defend in adversarial settings**. If
  a regulator or competitor challenges "show me where in your contracts
  the binding between agent and hardware data is expressed," the
  Path 1 answer is "it's not in the contracts directly; it's in the
  audit chain." This may be acceptable to sophisticated technical
  auditors but is harder to defend to non-technical regulators or
  marketing-context audiences.
- **Audit dependency on bridge availability**. Steps 7, 11, and 12
  query bridge endpoints. If the bridge is down or its DB has been
  rolled back, the audit chain has gaps. Path 1's audit story has a
  liveness dependency that primitive-level claims do not.

### Honest accounting

Path 1 is acceptable if VAPI's audience accepts indirect
cryptographic claims with extensive documentation. It is meaningfully
weaker for the specific audience identified in Pass 2A — businesses
and institutions evaluating data sovereignty infrastructure, who
typically need direct verifiability for compliance and risk
assessment. The path does not undermine the data ownership thesis
outright, but it places that thesis on a foundation of
"derive-the-binding-from-the-chain" rather than
"verify-the-binding-with-one-hash."

Whether this weakness is acceptable is the operator's judgment. If
the operator's vision tolerates "the binding is verifiable through
documentation and tooling" as a sufficient claim, Path 1 fits. If the
vision requires the binding itself to be a primitive-level
cryptographic claim, Path 1 falls short.

---

## Section 3 — Path Two Analysis: Extend AgentRegistry with `attestationCapability` Fields

### The path's specific architectural changes

Path 2 modifies the `AgentRegistry.sol` schema (which Phase O0 has
not yet deployed — modification is design-time, not redeploy-time)
to include a structured `attestationCapability` field per registered
agent. The field is a typed enumeration declaring which physical-data
domains the agent is authorized to attest to.

The proposed capability enum aligns with VAPI's L0-L7 PITL stack
(per CLAUDE.md "PITL Nine-Level Stack" line 200):

| Capability | Maps to | Hardware-data domain |
|---|---|---|
| `BIOMETRIC_TREMOR_FFT` | L4 anomaly detector + AIT pipeline | Accel magnitude FFT 4-15 Hz tremor |
| `BIOMETRIC_TOUCHPAD` | L4 + touchpad spatial entropy | DualSense touchpad XY positions |
| `BIOMETRIC_GSR` | L7 (currently uncalibrated) | Galvanic skin response (future) |
| `BIOMETRIC_GRIP` | L4 grip asymmetry | Trigger pressure + grip features |
| `BIOMETRIC_REFLEX` | L6/L6b reflex baselines | Stimulus-response timing |
| `HARDWARE_CERTIFICATION` | Phase 99+ certification | Manufacturer attestation |
| `CORPUS_INTEGRITY` | CORPUS-SNAPSHOT operations | Aggregate corpus state |
| `FLEET_COHERENCE` | FSCA, ProtocolCoherenceAgent | Fleet observation aggregation |

The field is `bytes32[]` on-chain (each capability a `keccak256("BIOMETRIC_TREMOR_FFT")`
or similar deterministic hash). At registration, the agent's
`attestationCapability` is set; at action time,
`AgentAdjudicationRegistry.anchorAgentAction(actionHash, agentId, actionType)`
checks via `requireAgentScope` modifier (per Design Pass 1 Conflict 1
Option A) that `actionType` matches one of the agent's declared
capabilities. Mismatch → reverts.

### The cryptographic claim the path produces

The cryptographic claim under Path 2 is the conjunction of:

- All claims from Path 1 (identity, scope, action, audit)
- **Capability authorization claim**: agent X's
  `attestationCapability` includes capability C at the time the
  action was anchored.

The claim formulation: "agent identity X with declared attestation
capability C took action Y about hardware-data flow Z."

The new word in the claim is **"with declared attestation capability
C."** This is meaningful because it makes capability part of the
cryptographic claim — an external auditor can verify "this agent was
authorized to attest to tremor-class data" with one
`AgentRegistry.getAttestationCapabilities(agentId)` view call.

But notice what the claim does **not** include: a direct binding from
agent action Y to specific hardware-data instance Z. The capability
is an authorization (CAN attest) not a binding (DID attest about THIS
specific data). The binding from action to specific hardware-data
remains derived from the primitive chain, exactly as in Path 1.

### Audit trail walk-through

Same TrustCo scenario. Anchor Sentry's AGENT_COMMIT to a
CORPUS-SNAPSHOT capturing AIT separation ratio.

The audit walk under Path 2 differs from Path 1 only at one inserted
step (after the existing Step 3, before the existing Step 4):

1. (same as Path 1)
2. (same as Path 1)
3. TrustCo verifies agent_id resolves to Anchor Sentry via
   AgentRegistry.
4. **NEW**: TrustCo queries `AgentRegistry.getAttestationCapabilities(agentId)`
   and verifies the returned `bytes32[]` includes
   `keccak256("CORPUS_INTEGRITY")` (or whichever capability maps to
   AGENT_COMMIT-with-CORPUS-SNAPSHOT-content).
5. (continues as Path 1 Step 4 onward — scope check, then chain to
   wiki content, corpus_snapshot_log, ait_session_log, PoAC records,
   hardware identity)

**Audit chain length**: 15 steps (one inserted). Same primitives
crossed. Same off-chain query surfaces.

### What TrustCo can verify cryptographically vs what they must infer

**Cryptographically verifiable** (additions over Path 1):
- Agent's declared attestation capabilities at the time of the action
  (Step 4)
- The specific capability value matches the action type (single hash
  comparison)

**Must still be inferred from chain or trusted from VAPI documentation**
(unchanged from Path 1):
- All the same chain-walk steps from Path 1 (the connection between
  AGENT_COMMIT and corpus_snapshot_log row, the connection between
  CORPUS-SNAPSHOT commitment and specific 37 sessions, etc.)

### Cryptographic claim TrustCo can make at the end

> "VAPI's primitives, when chained together with off-chain bridge
> queries, plus the agent's on-chain declared attestation capabilities,
> produce a verifiable trail showing this agent was authorized to
> attest to corpus-integrity-class data and made an attestation
> referenced in their AGENT_COMMIT, with the underlying biometric
> data sourced from controller hardware ECDSA-P256 keys."

Stronger than Path 1 in one specific way: the auditor can answer "is
this agent allowed to do this?" with a single primitive-level query.
Unchanged from Path 1 in the load-bearing way: the auditor cannot
answer "did this agent cryptographically attest to THIS specific
hardware-data instance?" with a single primitive — that binding
remains derived.

### New architectural complexity

Path 2 introduces moderate architectural complexity:

- **Capability schema design**: a controlled vocabulary of hardware-data
  domains must be defined. This vocabulary becomes part of the
  protocol — adding a capability later is a governance event. The
  initial vocabulary needs to anticipate future hardware-data domains
  (GSR if/when L7 calibration completes, controller types beyond
  DualShock Edge, future biometric modalities) without becoming
  unwieldy. Versioning of the vocabulary is its own concern.
- **Capability-to-actionType mapping**: each `actionType` value passed
  to `AgentAdjudicationRegistry.anchorAgentAction` must map
  deterministically to a capability. The mapping needs to be on-chain
  (so the `requireAgentScope` modifier can enforce it) or off-chain
  with the modifier trusting an off-chain table. On-chain is cleaner
  but more rigid (changing the mapping requires governance);
  off-chain is more flexible but introduces a trust boundary.
- **Capability governance**: adding a new capability requires
  amending AgentRegistry's allowed-capability list. This is a
  governance event of similar shape to invariant_change governance
  (per `scripts/vapi_invariant_gate.py:344-359` provenance chain
  pattern). The governance surface for capabilities lives alongside
  the existing invariant governance surface.
- **Capability vs scope distinction**: scope (per Design Pass 1
  Conflict 2 Option C) bounds what the agent CAN do at policy level;
  capability (per Path 2) declares what hardware-data domains the
  agent can attest to. These are two different authorization layers.
  Operators must understand both layers and their interaction —
  capability is a coarse-grained authorization at registration time,
  scope is a fine-grained authorization at action time. Conceptual
  overlap could create confusion in operator and auditor mental
  models.
- **Capability versioning**: as VAPI evolves and new capabilities are
  added, existing agents' `attestationCapability` lists may need to
  be updated. The architecture must specify how capability addition
  flows (per-agent re-registration with extended list, or all-agent
  governance event with backward compatibility).

### Strengths against the operator's stated vision

- **Authorization clarity**: the operator can answer "is this agent
  authorized to attest to tremor-class data?" with one view call.
  This is a real audit win over Path 1.
- **Capability is on-chain**: external observers can enumerate all
  registered agents and their declared capabilities without bridge
  cooperation. Lists are inspectable, auditable, and stable across
  bridge versions.
- **Capability rejection at action time**: the `requireAgentScope`
  modifier rejects out-of-capability actions on-chain. This is
  enforcement, not just declaration. The cryptographic claim
  "this agent was authorized to attest to this domain at the time of
  the action" is enforced by contract logic.
- **Foundation for future binding work**: Path 2 doesn't preclude
  Path 3 later. If at P3+ or beyond the operator decides direct
  binding is also needed, PHYSICAL_DATA_ATTESTATION v1 can be added
  on top of capability infrastructure. Path 2 is a one-way ratchet
  toward more expressiveness.

### Weaknesses against the operator's stated vision

- **Authorization ≠ binding**. The load-bearing concern in V11 is the
  binding from agent action to hardware-data flow. Path 2 strengthens
  authorization (which Pass 2A's scope-class decision already
  addresses) but does not strengthen binding. The conceptual gap V11
  identified is not closed by Path 2.
- **Vocabulary fragility**. A controlled capability enum becomes
  protocol-level identity. Choosing the wrong granularity now
  produces friction later. Too coarse (`BIOMETRIC` as a single
  capability) and the auditor learns nothing useful; too fine
  (`BIOMETRIC_TREMOR_FFT_ACCEL_X_AXIS_4HZ_BIN`) and the vocabulary
  becomes a maintenance burden.
- **Audit narrative complexity grows**. Path 2's audit story is
  Path 1 + an additional capability check. The audit chain length is
  15 instead of 14. The "is this agent authorized?" question gets a
  cleaner answer, but the dominant audit cost (walking from action
  to hardware-data) is unchanged.
- **Agents must be registered with foresight**. At agent registration
  time, the operator must declare all capabilities the agent will
  ever need. Adding capabilities later requires governance. This
  imposes upfront thinking that may be premature for early agents
  whose actual usage patterns aren't yet known.

### Honest accounting

Path 2 is a real improvement over Path 1 in one dimension
(authorization clarity) and adds moderate complexity in two
dimensions (vocabulary + governance + capability-vs-scope mental
model). The improvement does not address the load-bearing concern
V11 identified — direct binding from agent action to hardware-data
flow remains derived from the primitive chain, exactly as in Path 1.

If the operator's primary concern is "businesses need a clean
on-chain answer to 'is this agent allowed to attest about this
domain?'", Path 2 satisfies that concern. If the operator's primary
concern is "businesses need a clean cryptographic binding between the
specific agent action and the specific hardware-data flow it
attested to," Path 2 does not satisfy that concern any better than
Path 1.

Path 2 is best understood as **Path 1 plus authorization clarity,
not Path 3 minus complexity**. It's not the midpoint between Path 1
and Path 3; it's a sidestep that addresses authorization without
addressing binding.

---

## Section 4 — Path Three Analysis: Build PHYSICAL_DATA_ATTESTATION v1 as a New FROZEN-v1 Primitive

### The path's specific architectural changes

Path 3 introduces a new FROZEN-v1 primitive named
**PHYSICAL_DATA_ATTESTATION v1** (PDA v1) as the seventh member of
the FROZEN-v1 family, joining GIC, WEC, VAME, CORPUS-SNAPSHOT,
CONSENT, and AGENT_COMMIT (assuming AGENT_COMMIT v1 lands as the
sixth per Pass 2A V10 Option C).

The primitive directly captures the binding between hardware-derived
data, the agent that produced or verified an attestation about that
data, and the on-chain commitment that anchors the attestation. It
follows the established SHA-256-with-domain-tag pattern of the
existing primitives (per `bridge/vapi_bridge/corpus_snapshot.py:25-36`,
`consent_categories.py:47`, etc.).

**Proposed PHYSICAL_DATA_ATTESTATION v1 hash formula** (design only;
not implementation):

```
PDA_v1_commitment = SHA-256(
    b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"  (32 bytes)  — domain separation
    || hardware_data_hash                  (32 bytes)  — SHA-256 of the
                                                           specific physical-
                                                           data flow being
                                                           attested to (e.g.,
                                                           PoAC chain root,
                                                           tremor FFT vector
                                                           hash, corpus snapshot
                                                           commitment)
    || agent_id                            (32 bytes)  — bytes32 representation
                                                           of the agent's ioID
                                                           DID + ERC-6551 TBA
                                                           binding (matches
                                                           AGENT_COMMIT v1)
    || attestation_type                    (32 bytes)  — keccak256 of the
                                                           attestation type
                                                           string (e.g.,
                                                           "BIOMETRIC_CORPUS_SNAPSHOT",
                                                           "POAC_CHAIN_INTEGRITY",
                                                           "TREMOR_FFT_FEATURE_VECTOR")
    || ts_ns_be                            (8 bytes)   — uint64 BE: attestation
                                                           timestamp
)                                       = 136 bytes → SHA-256 → 32 bytes
```

The domain tag `b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"` is 32 bytes
(longer than other domain tags by intent — distinct from
AGENT_COMMIT's `b"VAPI-AGENT-COMMIT-v1"` to prevent any collision).
The genesis tag for PDA chain semantics is
`b"VAPI-PDA-GENESIS-v1"` if chained semantics are wanted (the prompt
description is single-attestation rather than chained, so chaining
may not be needed; deferred to operator decision).

**Hosting**: PDA v1 attestations are anchored on
`AgentAdjudicationRegistry` (per Design Pass 1 Conflict 1 Option A)
via
`anchorAgentAction(pda_commitment, agent_id, "PHYSICAL_DATA_ATTESTATION")`.
The same contract that hosts AGENT_COMMIT v1 also hosts PDA v1 — they
are differentiated by `actionType`. This avoids contract
proliferation while keeping the primitives semantically distinct.

**Bridge module**: new `bridge/vapi_bridge/physical_data_attestation.py`
following the pattern of `corpus_snapshot.py`. Exports
`compute_pda_hash(hardware_data_hash, agent_id, attestation_type, ts_ns)`
and the domain tag constant.

**Store table**: new `physical_data_attestation_log` table in
`bridge/vapi_bridge/store.py` mirroring `corpus_snapshot_log` shape.

**Relationship to existing primitives**:
- **CORPUS-SNAPSHOT v1** captures CORPUS state at a moment. PDA v1
  binds an agent to an attestation about that CORPUS state. CORPUS
  is data; PDA is "this agent says this data is real."
- **AGENT_COMMIT v1** captures an agent's commit to a git repository.
  PDA v1 captures an agent's attestation to a hardware-data flow.
  Two distinct semantic classes: AGENT_COMMIT is about source code
  changes; PDA is about hardware-data verification.
- **PoAC records** are signed by hardware. PDA v1 is signed by the
  agent (off-chain) and anchored on-chain. The PDA can wrap a PoAC
  chain hash (`hardware_data_hash` = root of PoAC chain) to bind the
  agent to the chain.

### The cryptographic claim the path produces

The cryptographic claim under Path 3 is direct:

> "Agent identity X cryptographically attested to hardware-data flow
> Z (where Z is the specific data identified by `hardware_data_hash`)
> at time T, with the attestation type being a specific declared
> physical-data domain, anchored on AgentAdjudicationRegistry."

The claim is at the **primitive level**. One hash recomputation
verifies the entire claim. The auditor doesn't reconstruct the binding
from a chain — the binding is the primitive.

### Audit trail walk-through

Same TrustCo scenario. Anchor Sentry's attestation to a CORPUS-SNAPSHOT
capturing AIT separation ratio.

The audit walk under Path 3:

1. **TrustCo queries AgentAdjudicationRegistry** for the PDA anchor
   by `tx_hash`. Returns the on-chain record:
   `(actionHash=pda_commitment, agentId, "PHYSICAL_DATA_ATTESTATION", blockNumber)`.
2. **TrustCo queries** `GET /agent/physical-data-attestation-status`
   with the `pda_commitment` and retrieves source values:
   `(hardware_data_hash, agent_id, attestation_type, ts_ns)`.
3. **TrustCo recomputes the PDA v1 hash**:
   `pda_commitment = SHA-256(b"VAPI-PHYSICAL-DATA-ATTESTATION-v1" ||
   hardware_data_hash || agent_id || attestation_type || ts_ns_be)`.
   Match confirms the attestation is exactly as TrustCo claims.
4. **TrustCo verifies agent_id** maps to Anchor Sentry via
   `AgentRegistry`.
5. **TrustCo verifies attestation_type** is a recognized type
   (e.g., `keccak256("BIOMETRIC_CORPUS_SNAPSHOT")`).
6. **For TrustCo's specific compliance question** ("did this agent
   attest to this hardware data?"): the audit STOPS HERE. Steps 1-5
   answer the binding question directly.

**Optional deeper verification** if TrustCo wants to verify the
underlying hardware data is itself sound:

7. **TrustCo follows hardware_data_hash to its underlying data**.
   Since `attestation_type = "BIOMETRIC_CORPUS_SNAPSHOT"` and
   `hardware_data_hash = corpus_snapshot_commitment`, TrustCo
   continues into the CORPUS-SNAPSHOT chain (Path 1 Steps 7-14):
   queries `corpus_snapshot_log`, recomputes CORPUS-SNAPSHOT v1 hash,
   verifies on-chain anchor, follows `ait_session_log` to PoAC
   records, traces to controller hardware. Same as Path 1's deeper
   chain.

**Audit chain length**:
- For binding question: 6 steps (down from 14 in Path 1)
- For full hardware-source verification: 6 + 8 = 14 steps (same as
  Path 1)

The key observation: **the binding question and the hardware-source
question are now decoupled.** TrustCo can answer "did this agent
attest to this data?" in 6 steps. They only need the deeper 8 steps
if they also want to verify the underlying hardware data is valid.
For many compliance audits, the binding question is the primary
question and the hardware-source verification is delegated to a
separate audit of VAPI's PoAC chain integrity.

### What TrustCo can verify cryptographically vs what they must infer

**Cryptographically verifiable** (additions over Path 1):
- The single PDA v1 hash directly binds agent_id to
  hardware_data_hash to attestation_type to ts_ns (Step 3)
- The on-chain anchor of the PDA proves the attestation existed at
  block N (Step 1)

**Must be inferred from chain or trusted from VAPI documentation**:
- (Only for hardware-source verification, optional Step 7+): the
  same chain as Path 1's Steps 10-14. But this is now a separate
  audit decision, not a required step for the binding question.

### Cryptographic claim TrustCo can make at the end

> "VAPI's PHYSICAL_DATA_ATTESTATION v1 primitive directly proves
> that Anchor Sentry (agent X) attested to the specific
> hardware-data flow identified by hardware_data_hash at time T.
> The hardware-data is itself a hash that verifiably composes into
> a chain of CORPUS-SNAPSHOT v1 + PoAC records signed by registered
> controller hardware (verifiable as a separate PoAC integrity
> audit if needed)."

This is a **2-layer cryptographic claim**: PDA primitive (top layer,
direct binding) + PoAC chain (bottom layer, hardware sourcing). The
top layer is one hash recomputation. The bottom layer is the existing
PoAC integrity property VAPI already publishes.

### New architectural complexity

Path 3 introduces meaningful new architectural complexity:

- **Seventh FROZEN-v1 primitive**: the FROZEN-v1 family expands from
  6 (after Pass 2A's AGENT_COMMIT) to 7. This is a one-way decision —
  once PDA v1 ships, it stays FROZEN forever. v2 escape clauses exist
  but are expensive to invoke.
- **New bridge module + store table**: `physical_data_attestation.py`
  and `physical_data_attestation_log` table. Pattern is well-
  established (mirrors `corpus_snapshot.py` and `corpus_snapshot_log`),
  but it's still net-new code.
- **New PV-CI invariants**: INV-PDA-001 (function signature freeze),
  INV-PDA-002 (domain tag literal freeze). Allowlist grows by 2
  entries.
- **New bridge endpoint**: `GET /agent/physical-data-attestation-status`
  + `GET /agent/pda-history`. Audit surface; full read-key auth.
- **New chain wrapper**: `chain.py` gains `async def
  anchor_pda_attestation(pda_hash, agent_id, attestation_type) ->
  tuple[Optional[str], bool]`.
- **attestation_type vocabulary governance**: similar concern to
  Path 2's capability vocabulary. PDA v1 takes `attestation_type`
  as input; the recognized types must be specified somewhere. Two
  options: (a) on-chain enum-like registry of recognized types
  (governance event to add new types), or (b) off-chain
  bridge-side validation only (more flexible, less auditable). The
  decision is design-time.
- **Relationship to AGENT_COMMIT v1**: the two primitives are
  semantically distinct (commits vs hardware-data attestations), but
  agents will produce both. The bridge architecture must clearly
  distinguish them in operator-facing documentation and audit
  guides.
- **Maintenance burden of expanding primitive family**: each FROZEN-v1
  primitive carries ongoing cost (governance events when allowlist
  changes, invariant gate maintenance, audit surface updates,
  bridge module evolution). Going from 6 to 7 is incremental, but
  the cumulative burden of N primitives grows. The architecture
  document section 8 already envisioned a 6th primitive (OPERATOR);
  if Pass 2B adds PDA v1 the family is at 7 with no clear stopping
  point.

### Strengths against the operator's stated vision

- **Direct cryptographic claim about hardware-data binding**. This
  is the load-bearing strength. The operator's vision wording — "the
  agents serve as the verification primitive between physical and
  digital worlds" — is implemented as a literal primitive in Path 3.
  The vision and the code use the same word.
- **Audit chain length collapses for the binding question**. 6 steps
  vs 14 steps. Compliance teams typically prefer claims they can
  verify in a single contract call or hash recomputation; Path 3
  offers exactly that.
- **External tooling-friendly**. A primitive-level attestation can
  be indexed, queried, filtered, and aggregated by tools that don't
  understand VAPI's full primitive chain. "Show me all PDA records
  for agent X in the last 30 days" becomes a one-query operation.
- **Brand identity coherent with vision**. VAPI's website explanation
  becomes: "We have a dedicated cryptographic primitive that binds
  agent attestations to hardware-data flows." That sentence reads
  better to non-technical audiences than "We have agents whose
  attestations to hardware data are verifiable through a chain of
  cryptographic primitives that you can audit by following our
  guide."
- **Defensible in adversarial settings**. If a regulator or
  competitor asks "show me where in your contracts the agent-to-
  hardware-data binding is expressed," the answer is "PDA v1 hash
  formula and the AgentAdjudicationRegistry anchor." The answer is
  one sentence.

### Weaknesses against the operator's stated vision

- **Architectural weight**. Adding a seventh FROZEN-v1 primitive is
  the largest weight increase in the design pass series. The
  primitive family was at 5 before AGENT_COMMIT v1 (Pass 2A), goes to
  6 with AGENT_COMMIT, and to 7 with PDA. This is a substantive
  expansion of VAPI's architectural identity.
- **Attestation_type vocabulary maintenance**. Same concern as
  Path 2's capability vocabulary — choosing the right granularity
  matters for long-term maintenance.
- **Risk of primitive proliferation**. If PDA v1 lands at the
  seventh primitive, future architectural concerns may invite an
  eighth, ninth, or tenth primitive. Each addition is incremental
  but the trajectory matters. The protocol's identity becomes "the
  one with N FROZEN-v1 primitives" rather than "the one with the
  five canonical primitives." This is a brand and conceptual
  concern, not just a maintenance concern.
- **Coupling between agent action and hardware-data hash**. PDA v1
  takes `hardware_data_hash` as an input, but how does the bridge
  validate that `hardware_data_hash` actually corresponds to a
  hardware data flow? If an agent submits a PDA with a fabricated
  `hardware_data_hash`, the on-chain anchor records the fabrication
  with the same cryptographic strength as a legitimate attestation.
  The primitive proves "the agent attested to this hash" — it does
  NOT prove "this hash points to real hardware data." That latter
  claim still requires the underlying chain to be valid (PoAC
  integrity, etc.). A naive auditor could over-interpret PDA's
  strength; documentation must be precise about what PDA does and
  does not prove.

### Honest accounting

Path 3 is the architecturally heaviest path but produces the
strongest direct cryptographic claim about hardware-data binding.
The claim formulation matches the operator's vision wording almost
literally — "agent serves as verification primitive between physical
and digital worlds" becomes "PHYSICAL_DATA_ATTESTATION primitive."

The architectural cost is real: a seventh FROZEN-v1 primitive carries
ongoing maintenance burden, and the trajectory of primitive
proliferation has no natural stopping point. The trade-off is between
"strongest direct claim, heaviest architecture" (Path 3) and "leanest
architecture, weakest direct claim" (Path 1).

For the audience identified in Pass 2A — businesses and institutions
evaluating data sovereignty infrastructure — the direct claim is what
the audience is buying. Their compliance teams need claims they can
verify with one hash recomputation. Path 3 produces that. Whether the
architectural cost is worth the audit clarity is the operator's
judgment.

A subtle but important caveat about Path 3: the primitive proves
"the agent attested" but does not prove "the attestation is correct."
An agent could attest to a fabricated hardware_data_hash; the PDA
record proves the attestation occurred but does not prove the
underlying hardware data is real. Users of PDA v1 in audit narratives
must understand this distinction. Documentation must be precise about
what PDA is and isn't.

---

## Section 5 — Cross-Path Comparison

| Dimension | Path 1 (As written) | Path 2 (Capability) | Path 3 (PDA primitive) |
|---|---|---|---|
| **Strength of direct cryptographic claim about hardware-data binding** | WEAK — derived from primitive chain only; no primitive directly expresses the binding | WEAK for binding (authorization is strong; binding unchanged from Path 1) | STRONG — single primitive directly binds agent identity to hardware-data hash |
| **Auditability by businesses/institutions** | 14-step chain walk; multiple primitives + bridge queries | 15-step chain walk; one new primitive-level authorization check inserted | 6-step walk for binding question; optional 8 more for hardware-source verification |
| **Architectural complexity added** | ZERO — no new primitives or schema changes beyond what Pass 2A authorized | MODERATE — capability vocabulary, capability-to-actionType mapping, capability vs scope mental model | SUBSTANTIAL — seventh FROZEN-v1 primitive, new bridge module, new store table, new endpoint, new chain wrapper, new invariants, attestation_type vocabulary |
| **Alignment with FROZEN-v1 primitive family pattern** | NEUTRAL — doesn't extend or stress the family | NEUTRAL — adds a structured field rather than a new primitive | EXPANSIONIST — explicitly adds a seventh primitive, continuing the family pattern |
| **Match with operator's vision wording ("agents as verification primitive between physical and digital worlds")** | INDIRECT — vision is satisfied by chain inference; no primitive uses "physical" or "verification" terminology | INDIRECT for binding; DIRECT for authorization | DIRECT — primitive name itself encodes the vision |
| **Auditor's primary cryptographic verification operation** | Walk and verify multiple primitive hashes + off-chain bridge queries | Path 1 + capability-list inclusion check | Recompute one PDA hash; chain integrity is optional follow-on audit |
| **External regulator-friendly explanation** | "Verifiable through our audit guide" | "Verifiable through our audit guide; agents have on-chain authorization declarations" | "We have a dedicated primitive that cryptographically binds agent attestations to hardware data" |
| **Risk of primitive proliferation** | NONE — no new primitive | NONE — no new primitive | EXISTS — sets precedent that architectural concerns can be answered with new FROZEN-v1 primitives, with no clear stopping point |
| **Defensibility of "agent attests to hardware data" claim in adversarial settings** | "Look at our audit guide" — rhetorically harder | Path 1 + "and they're authorized to do so" — slightly harder | "Look at PDA v1" — single-sentence answer |
| **Liveness dependency on bridge availability for audit** | HIGH — multiple bridge queries throughout chain | HIGH — same as Path 1 plus one AgentRegistry view call | MODERATE — only the on-chain anchor query is required for binding question; bridge needed only for hardware-source verification |
| **Cost of being wrong** | LOW — Path 1 doesn't preclude Path 2 or Path 3 later; chain remains valid | LOW — Path 2 is a one-way ratchet; doesn't preclude Path 3 later | MODERATE — Path 3 is FROZEN; v2 requires governance and careful migration |
| **Time to implement (rough estimate)** | 0 days — already covered by Pass 2A | +2-3 days for capability schema + governance | +5-8 days for primitive + bridge module + store + endpoint + invariants |
| **Aligned with audience identified in Pass 2A (business/institutional)?** | WEAKLY — audit story works but requires extensive documentation | WEAKLY for binding; STRONGLY for authorization | STRONGLY — direct cryptographic claim is what compliance teams typically prefer |

### Side-by-side audit walk for the same scenario

To make the difference concrete, here's the SAME scenario (Anchor
Sentry attests to CORPUS-SNAPSHOT capturing AIT separation ratio
1.199, N=37) walked through each path:

**Path 1 audit** (14 steps, verifies "the chain is consistent"):
> Query AgentAdjudicationRegistry for AGENT_COMMIT → recompute
> AGENT_COMMIT v1 hash → verify agent_id in AgentRegistry → verify
> scope → follow commit_sha to git → read wiki content → query
> corpus_snapshot_log → recompute CORPUS-SNAPSHOT v1 hash → verify
> on-chain anchor → query ait_session_log for 37 sessions → for each
> session, trace to PoAC records → verify PoAC chain link hashes →
> verify device_id resolves to ioID registry → verify hardware key.

**Path 2 audit** (15 steps, verifies "the chain is consistent + agent
was authorized"):
> Path 1 + insert one step after agent_id verification: query
> AgentRegistry.getAttestationCapabilities(agentId), verify
> CORPUS_INTEGRITY is in the list.

**Path 3 audit for binding question only** (6 steps, verifies "agent
X attested to data Y"):
> Query AgentAdjudicationRegistry for PDA anchor → query
> physical_data_attestation_log → recompute PDA v1 hash → verify
> agent_id in AgentRegistry → verify attestation_type is recognized
> → STOP. Binding verified.

**Path 3 full audit** (14 steps, same as Path 1 if hardware-source
verification is also required):
> Path 3 binding (6 steps) + Path 1 hardware-source verification
> (8 steps).

The key difference Path 3 produces: **the binding question and the
hardware-source question become independently auditable.** Many
compliance audits primarily care about the binding question; Path 3
gives them a 6-step answer instead of a 14-step answer.

---

## Section 6 — Recommendation as Architectural Analysis

This pass's question is conceptual, and the operator's vision is the
deciding factor. This recommendation is one input among several the
operator will weigh.

### What I would choose if the decision were mine

I would choose **Path 3** for the following reasons:

1. **Audience alignment is the load-bearing factor.** Pass 2A
   established that VAPI's audience is businesses and institutions
   evaluating data sovereignty infrastructure. That audience needs
   compliance-grade audit clarity. A 14-step chain walk (Path 1) or
   15-step walk (Path 2) is meaningfully harder to perform than a
   6-step direct verification (Path 3). For the specific audience
   identified, audit length and directness matter.

2. **The vision wording maps to the primitive directly.** The
   operator's vision uses the phrase "verification primitive between
   physical and digital worlds." Path 3 implements that phrase as a
   literal cryptographic primitive named PHYSICAL_DATA_ATTESTATION.
   When the protocol's marketing language and its code use the same
   word, the protocol's identity is more defensible — operators,
   auditors, and skeptics all see the same noun in the same place.

3. **Path 2 doesn't solve the load-bearing concern.** V11's concern
   was the binding from agent action to hardware-data flow. Path 2
   strengthens authorization (which Pass 2A's scope-class decision
   already addressed) without strengthening binding. Path 2 is best
   understood as Path 1 + authorization clarity, not as a midpoint
   between Path 1 and Path 3. If V11's concern is binding, Path 2
   doesn't address it any better than Path 1.

4. **The marginal cost of one more primitive is bounded.** Going from
   six to seven FROZEN-v1 primitives is incremental. The pattern is
   well-established (`bridge/vapi_bridge/corpus_snapshot.py` is the
   reference implementation). The gate, store table, bridge endpoint,
   chain wrapper, and invariants are templated work. Estimated 5-8
   days of implementation.

5. **The trajectory concern is real but mitigatable.** Adding a
   seventh primitive does set a precedent for future expansion. The
   mitigation is explicit operator discipline: PDA v1 is added because
   it answers a specific load-bearing concern (V11 binding), not
   because every architectural concern deserves a new primitive.
   Future primitive proposals should be evaluated against the same
   bar — does this answer a load-bearing concern that no existing
   primitive addresses? If yes, add. If no, don't.

### Why the operator might legitimately choose differently

**The operator might choose Path 1** if they:
- Value architectural leanness over direct claim strength
- Accept that compliance audiences will use VAPI's audit guide as
  the primary documentation surface, and that a chain-walk audit is
  acceptable for sophisticated business and institutional auditors
- View the FROZEN-v1 family's growth as a cost that should be
  minimized, with new primitives admitted only when no other path
  exists
- See the hardware-data binding as adequately expressed through the
  existing primitive chain, even if it requires documentation to
  surface explicitly

**The operator might choose Path 2** if they:
- Value the authorization clarity gain (which is real and not
  available in Path 1) more than the binding-clarity gap
- Want a one-way ratchet that doesn't preclude Path 3 later but
  doesn't commit to it now
- Prefer adding structured fields to existing primitives over adding
  new primitives
- View capability declarations as themselves the answer to the V11
  concern, even though strictly the binding question is unchanged

**The operator might choose Path 3** if they (matching my own
reasoning above):
- Prioritize direct cryptographic claims over architectural minimalism
- View the FROZEN-v1 family pattern as a strength to be extended when
  load-bearing concerns demand it
- Want VAPI's vision wording and primitive names to align literally
- Believe compliance audiences will benefit from the binding
  question and the hardware-source question being independently
  auditable

### The honest framing

**The codebase cannot decide between these paths.** The codebase
provides the FROZEN-v1 family pattern (which Paths 2 and 3 can both
extend, in different ways), the existing primitive chain (which Path
1 leans on), and the audience clarity (which favors Path 3 but
doesn't mandate it). The deciding factor is the operator's
architectural priorities — architectural leanness vs direct claim
strength, primitive family minimalism vs primitive family
expressiveness, brand identity in marketing language vs brand
identity in compliance language.

This recommendation is one input among several the operator will
weigh. The operator's vision is the deciding factor, and any of the
three paths is a defensible architectural choice given the operator's
priority weights. The pass's job is to make those priority weights
visible to the operator so the choice can be made with full
information.

### Operator confirmation (2026-04-27)

The operator confirmed Path 3 — PHYSICAL_DATA_ATTESTATION v1 as the
seventh FROZEN-v1 primitive on AgentAdjudicationRegistry. The decision
rests on three converging grounds, preserved in this permanent record
so future operators encountering this question can read why Path 3
was chosen over Paths 1 and 2.

**Vision-to-architecture literal alignment**: the operator's stated
vision describes agents as "the verification primitive between
physical and digital worlds." Path 3 implements that as a literal
primitive bearing that semantic load. Paths 1 and 2 leave the vision
wording as language not anchored in primitive naming. When the
protocol's vision and its primitive name use the same noun in the
same place, the protocol's identity is more defensible — operators,
auditors, and skeptics all see the same word in the same place.

**Audience-driven audit chain optimization**: Pass 2A established
future consumers as businesses and institutions evaluating data
sovereignty infrastructure under regulatory, legal, and reputational
standards. Path 3 collapses the binding-question audit chain from 14
steps (Path 1) to 6 steps, which matches the verification posture
compliance teams require. The hardware-source verification chain
remains available as a separate audit when needed, decoupling the
binding question from the hardware-source question. For compliance
teams whose primary language is regulator-friendly verification
statements, the directness of a 6-step audit translates directly to
evaluation cost and risk-assessment confidence.

**Continuity with the family-extension posture established by prior
decisions**: Design Pass 1 Conflict 2 (scope-class authorization
preserving CONSENT v1's FROZEN status) and Pass 2A V10 (AGENT_COMMIT
v1 as the sixth FROZEN-v1 primitive over deploying EAS to IoTeX) both
chose extending VAPI's primitive family over adopting external
patterns or perturbing existing primitives. Path 3 applies the same
posture to V11 — the FROZEN-v1 family is treated as a strength to be
extended when load-bearing concerns demand it, not as a complexity
surface to be minimized. Choosing Path 1 or Path 2 would break the
pattern established by these prior decisions; Path 3 maintains
architectural continuity across the design pass series.

This confirmation locks Path 3 as the resolution for V11 and permits
Pass 2C (Phase O0 implementation plan) to proceed treating
PHYSICAL_DATA_ATTESTATION v1 as a settled architectural decision.
CONSENT v1 stays FROZEN as the fifth primitive (per Design Pass 1
Conflict 2); AGENT_COMMIT v1 ships as the sixth (per Pass 2A V10);
PHYSICAL_DATA_ATTESTATION v1 ships as the seventh.

The trajectory concern surfaced in Section 4 — that adding a seventh
primitive sets a precedent for future expansion with no clear
stopping point — is acknowledged and mitigated by explicit operator
discipline: future primitive proposals must clear the same bar this
one cleared, namely answering a load-bearing concern that no existing
primitive addresses. The bar is not "useful" but "load-bearing and
otherwise unaddressable." That bar will be applied to any future
proposed primitive in subsequent phases.

---

## Section 7 — Operator Decision Framework

Five questions the operator should ask themselves when choosing
between the paths. These are framed to surface architectural
preferences rather than push toward a specific answer. The questions
are ordered roughly by load-bearing weight in the decision.

### Question 1 — Audit clarity vs architectural leanness

> When a business or institution audits VAPI's claim that an agent's
> attestation cryptographically binds to a specific hardware-data
> flow, do you want them to verify ONE primitive's hash formula in a
> single hash recomputation, or to walk a chain of three to four
> primitives plus off-chain bridge queries?

This question surfaces the trade-off between Path 1's leanness and
Path 3's directness. If your answer is "ONE primitive," you are
favoring Path 3. If your answer is "I am willing to provide a
documented audit chain because architectural simplicity matters more,"
you are favoring Path 1.

If your answer is "the audit chain is fine for sophisticated
auditors," ask yourself a follow-up: are the businesses and
institutions you envision as customers all sophisticated technical
auditors, or do some of them include compliance teams whose primary
language is regulator-friendly verification statements? The audience
heterogeneity matters.

### Question 2 — Binding vs authorization

> Do you view "this agent is authorized to attest to tremor-class
> data" and "this specific agent attested to this specific tremor
> data instance" as the same claim, or as two distinct claims that
> auditors need to verify separately?

This question surfaces the load-bearing distinction between Paths 1/2
(authorization-only) and Path 3 (binding). If you view them as the
same claim, Path 2's capability declaration is sufficient — the
primitive chain handles the rest. If you view them as distinct,
Path 2 only handles the first; Path 3 directly handles the second.

The wording the operator uses elsewhere is a signal: phrases like
"agents that are bound to hardware-data flows" suggest binding;
phrases like "agents authorized to operate on data" suggest
authorization. Both wordings can coexist, but the architectural
expression should match the dominant intent.

### Question 3 — The primitive family pattern

> How much weight do you place on architectural leanness versus
> primitive expressiveness? Adding a seventh FROZEN-v1 primitive
> carries a maintenance burden — do you view the FROZEN-v1 family
> as a growing strength (more primitives = more directly-expressible
> cryptographic claims) or as a complexity surface that should be
> minimized (each new primitive is one more thing to maintain
> forever)?

This question surfaces the operator's strategic stance toward the
FROZEN-v1 family. The five existing primitives plus AGENT_COMMIT v1
(Pass 2A) are at six. Path 3 takes the family to seven. Whether seven
feels like growth-of-capability or growth-of-cost is a strategic
question with no objectively correct answer.

A useful sub-question: imagine VAPI's third or fourth Operator series
phase, where another architectural concern surfaces. If your default
response is "consider whether a new FROZEN-v1 primitive answers the
concern," you are operating in expansionist mode. If your default
response is "lean on the existing primitives unless absolutely
necessary," you are operating in minimalist mode. Path 3 is
consistent with expansionist mode; Path 1 is consistent with
minimalist mode; Path 2 is in between.

### Question 4 — Brand identity in product explanation

> If you imagine VAPI's marketing site in 2027 explaining the protocol
> to potential business and institutional customers, which sentence
> reads better to you:
>
> (a) "Our agents attest to hardware-derived data flows through a
> dedicated PHYSICAL_DATA_ATTESTATION primitive that cryptographically
> binds the agent identity to the hardware-data flow."
>
> (b) "Our agents perform actions whose connection to hardware data
> is verifiable through our chain of cryptographic primitives — agent
> identity, scope authorization, action anchoring, audit log
> inclusion, and primitive-chain references — all auditable through
> our published audit protocol."

Both sentences are factually correct under their respective paths.
The first describes Path 3; the second describes Path 1 (or Path 2
with capability mention added). Sentence (a) is shorter and uses
fewer compound concepts. Sentence (b) is more detailed but harder to
parse for non-technical readers.

If sentence (a) reads better to you, you are favoring Path 3. If
sentence (b) reads better — particularly if you find the explicit
chain-of-primitives explanation more honest because it acknowledges
the actual architectural reality — you are favoring Path 1.

A useful sub-question: would you rather your audience walks away
remembering "VAPI has a primitive that does X" or "VAPI has a
verifiable cryptographic chain that includes hardware-data flows"?
The first is brand-friendly; the second is technically more
accurate.

### Question 5 — Defensibility in adversarial settings

> If a regulator, competitor, or skeptical journalist asks "show me
> exactly where in your contracts the agent-to-hardware-data binding
> is expressed cryptographically," what answer do you want to be
> able to give?
>
> Path 1 answer: "The binding is derived from the chain of
> primitives. Here is our audit guide explaining the chain."
>
> Path 2 answer: "Authorization is on-chain via attestationCapability;
> binding is derived from the chain of primitives. Here is our audit
> guide."
>
> Path 3 answer: "PDA v1 hash formula and AgentAdjudicationRegistry
> anchor. The primitive directly expresses the binding."

This question surfaces preference for defensibility under skepticism.
Path 3's answer is one sentence, which non-technical questioners
can absorb. Paths 1 and 2 require the questioner to follow you into
documentation. The defensibility cost of Paths 1 and 2 is higher in
adversarial settings; the cost of Path 3 is the architectural weight
of an additional primitive.

A useful sub-question: do you anticipate adversarial settings — for
instance, regulators auditing data sovereignty claims, competitors
challenging your "first verification primitive" framing, or
journalists asking pointed questions about where the cryptographic
strength actually lives? If you anticipate adversarial settings, the
single-sentence answer matters more. If you anticipate primarily
collaborative settings (technical reviewers, partner integrations),
the documentation-based answer is acceptable.

---

## Section 8 — Open Questions for Pass 2C

These questions arose during this design pass's reasoning but cannot
be answered until the operator chooses among Paths 1, 2, and 3. They
are inputs to Pass 2C (Phase O0 implementation plan), not blockers
to Pass 2B's completion.

### Path-conditional questions

1. **If Path 1 is chosen**: what is the publishing schedule and
   format for the comprehensive audit guide? The 14-step chain walk
   needs to be a published document with reference implementations.
   Does it ship as part of Phase O0, or is it an explicit deferred
   deliverable for a later phase? The audit guide is load-bearing
   for Path 1's audience strategy and shouldn't be assumed to follow
   automatically from the contract deploys.

2. **If Path 2 is chosen**: what is the initial capability vocabulary,
   and how is the vocabulary itself governed? The capability enum
   becomes part of the protocol surface. The initial values
   (BIOMETRIC_TREMOR_FFT, BIOMETRIC_TOUCHPAD, etc.) need operator
   review. Adding a new capability later requires a governance event
   of similar shape to invariant_change governance — this needs a
   specific governance protocol and a version-management plan for
   existing agents whose capability lists may need updates.

3. **If Path 3 is chosen**: what is the relationship between the
   PDA v1 primitive and the existing CORPUS-SNAPSHOT v1 primitive at
   the contract layer? Specifically: when an agent attests to a
   CORPUS-SNAPSHOT, does the PDA v1 record become the canonical
   anchor (with CORPUS-SNAPSHOT's own anchor on AdjudicationRegistry
   becoming a sub-record), or do both anchors coexist? The
   relationship affects the audit chain shape and the contract
   actionType vocabulary.

### Cross-path questions

4. **Hardware_data_hash domain integrity** (Path 3 specifically, but
   Path 1's chain-walk audit also touches this): how does VAPI
   guarantee that a `hardware_data_hash` passed into PDA v1 actually
   corresponds to real hardware data rather than a fabrication? The
   primitive proves "the agent attested" but does not prove "the
   underlying data is real." Under Path 3, the answer is "PoAC chain
   integrity audit verifies the underlying data" — but this should
   be made explicit in audit documentation. Pass 2C must specify how
   VAPI prevents naive interpretations of PDA v1 strength.

5. **AGENT_COMMIT v1 and PDA v1 actionType differentiation** (Path 3
   specifically): both primitives anchor on
   AgentAdjudicationRegistry via `anchorAgentAction(actionHash,
   agentId, actionType)`. AGENT_COMMIT v1 uses
   `actionType="AGENT_COMMIT"`; PDA v1 uses
   `actionType="PHYSICAL_DATA_ATTESTATION"`. The full actionType
   vocabulary needs specification — what other actionType values are
   anticipated for Phase O0+? Pass 2C should produce the canonical
   actionType enum.

6. **Capability and PDA interaction** (if both Path 2 and Path 3
   were ever chosen together — which is currently not under
   consideration but the question informs the path-2-only and
   path-3-only paths): if attestationCapability declares "agent CAN
   attest to BIOMETRIC_CORPUS_SNAPSHOT" and PDA v1 records "agent DID
   attest to specific data with attestation_type=BIOMETRIC_CORPUS_SNAPSHOT,"
   the two layers reinforce each other. But Pass 2B is choosing one
   path, not combining them. Should Pass 2C revisit whether a
   Path-2-AND-Path-3 combination is worth considering? Currently
   marked out of scope.

7. **Audit endpoint stability guarantees**: regardless of path,
   compliance audits depend on bridge endpoints being stable across
   versions. `GET /agent/corpus-snapshot-status`,
   `GET /agent/agent-commit-history`, `GET /agent/physical-data-attestation-status`
   (if Path 3) all become audit surfaces. Pass 2C should specify
   API stability guarantees and versioning policy for these
   endpoints — e.g., "audit endpoints are versioned with semver;
   breaking changes require a 6-month deprecation window;
   historical query results must remain reproducible for at least
   5 years post-attestation."

8. **VAPI_INVARIANTS.md and CLAUDE.md updates for the chosen path**:
   each path produces specific updates to the FROZEN-v1 primitive
   registry documentation. Path 1 adds nothing. Path 2 adds a note
   about AgentRegistry's attestationCapability field (not a new
   primitive but a structured field worth documenting in the
   invariants registry). Path 3 adds INV-PDA-001 + INV-PDA-002 as
   new invariants. Pass 2C should specify the documentation update
   shape per chosen path.

9. **Marketing language and audience-facing documentation**: Pass 2A
   established the audience as businesses and institutions. The
   chosen path's narrative needs to be reflected in audience-facing
   materials. Pass 2C should propose what those materials look like
   under each path — at minimum, the website-language sketch from
   Section 7 Question 4, plus any compliance-team-facing docs.

10. **Reconsideration clauses**: each path is a one-way decision in
    different ways. Path 1 is fully reversible (Path 2 or Path 3 can
    be added later). Path 2 is mostly reversible (Path 3 can be
    added; reverting to Path 1 requires deprecating capability field
    semantics). Path 3 is FROZEN once shipped (v2 escape clause
    exists but is expensive). Pass 2C should specify the
    reconsideration protocol — under what conditions would the
    operator revisit the path choice in a future phase?

---

This document holds for review. No code. No contract modifications.
No bridge updates. No agent definition files. No commits.
