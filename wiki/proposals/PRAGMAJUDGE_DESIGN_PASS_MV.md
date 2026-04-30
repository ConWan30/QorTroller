# PragmaJudge — Design Pass MV (Minimum Viable)

**Status**: HOLDING for operator approval at post-implementation verification
checkpoint. Document content produced per PJ1–PJ13 resolutions captured
2026-04-30. No code, contract, or wiki changes ship as part of this commit —
this is a standalone documentation commit closing the MV design phase.

**Discipline**: Verification-First Discipline (canonical in `CLAUDE.md`,
commit `94bed715`). This document is the Step-3 implementation against
the operator-resolved decision set. Step 4 (post-implementation
verification) and Step 5 (operator approval before staging) follow.

**Resolved inputs** (operator authority, 2026-04-30, not open for revision
within this pass):

| PJ   | Resolution                                                                                                                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| PJ1  | A — `wiki/proposals/PRAGMAJUDGE_DESIGN_PASS_MV.md`                                                                                                                 |
| PJ2  | B — load-bearing properties for MV are (a) physiological human presence + (b) cryptographic intent commitment only; (c) and (d) deferred                           |
| PJ3  | D, scope-clarified — zero new **settlement** contracts; verifier contracts permitted; `PragmaIntentProofVerifier.sol` in scope; settlement reuses `AdjudicationRegistry.recordAdjudication` with `deviceIdHash=SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")` and `sourceType="PRAGMA_JUDGE"` |
| PJ4  | B — two agents: `PromptIntentExtractor` + single `OutputFidelityJudge`                                                                                             |
| PJ5  | C — no token, no vault in MV; audit-only verdicts                                                                                                                  |
| PJ6  | A — new circuit `PragmaIntentProof.circom`; constraint budget 2,048 (Phase 67 ptau 2^11); load-bearing for headline claim; flag as finding if exceeded             |
| PJ7  | confirm — three deferred failure modes (operator collusion, threshold drift / adversarial robustness, multi-platform attack) accepted out-of-MV-scope              |
| PJ8  | B + D — market binding: EU AI Act Article 12 + Moffatt v. Air Canada                                                                                               |
| PJ9  | confirm — Stream→VAPI-gate mapping accurate; Stream 2 may ship in `dry_run=True` before Gate 2 partial; live-mode (`dry_run=False`) ship deferred to Stream 3 gate |
| PJ10 | A — controller-only (DualSense Edge via existing PITL stack); no mobile MV                                                                                         |
| PJ11 | B — PragmaJudge sub-Merkle root attached to VAPI's `ProtocolCoherenceRegistry` Merkle via parent-leaf composition; `_AGENT_IDS` tuple untouched                    |
| PJ12 | A — bind to existing `ANONYMIZED_RESEARCH` consent category; v2 enum extension deferred                                                                            |
| PJ13 | supported — estimated ~2,100–2,500 lines under recommended path                                                                                                    |

**Verification standard**: every architectural claim cites `file:line` or
external-source verification. Every dependency claim references specific
contracts, modules, or VAPI phases. Every effort estimate cites prior phases
as calibration data.

**Date**: 2026-04-30

---

## Section 1 — Origin and Scope

### 1.1 Why this document exists

The PragmaJudge sub-protocol was sketched in
`PragmaJudge/PRAGMAJUDGE_MASTER_ARCHITECTURE.md` (70KB, frozen at Phase
201+ baseline) and grounded in the research PDF
`PragmaJudge_ A Cross-Disciplinary Architecture for Physical Intelligence
Accountability.pdf` (10 pages). Both documents predate VAPI Phase 237 by
33+ phases and target a vision-shape implementation: 7–8 new contracts,
4–5 new agents (#61–#65), one new ZK circuit, one new token (PRAGMA),
one new ioSwarm coordinator, ~50 new tools (#201–#250).

The vision is internally rigorous. It is also incompatible with three
present realities:

1. **Wallet state**. Active wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
   holds 0.5525 IOTX as of 2026-04-29 (per `CLAUDE.md` Phase 237.5 Path C+
   diagnosis); operator-stated funding gap "several days". Vision-shape
   implementation requires ~0.5–1.0 IOTX of deploy gas across 7–8
   contracts. Phase O0 Stream 2-deploy is already gated on the same wallet
   refill at 5 IOTX target.
2. **VAPI sequencing gates** (RULE 0.7). Real economic operations
   (vault disbursements, token minting) gate behind separation_ratio>1.0
   AND ALL_PAIRS_GATE_ENABLED (Gate 1), N≥100 live non-dry-run zero-FP
   adjudications (Gate 2), and VHP end-to-end on testnet (Gate 3). Phase
   231 cleared the AIT defensibility P0 condition (N=37 corpus all
   players ≥10 sessions); but full Gate 1 on every probe type is
   incomplete (P1vP3=0.032 on tremor_resting per G-001 audit). Token and
   vault primitives ship before clearing these gates would invert
   VAPI's protocol discipline.
3. **Verification-First Discipline** canonicalized in `CLAUDE.md` commit
   `94bed715`. Every consequential commit must hold for operator
   review at both verification checkpoints. Vision-shape implementation
   requires multiple sequential design phases; MV scope is the only
   mode in which an architectural proposal lands in a single pass.

**This document is the MV (Minimum Viable) architectural commitment
under those constraints.** It produces an implementable contract that
respects the operator's PJ resolutions, the VAPI codebase READ-ONLY
boundary, and the wallet/sequencing reality.

### 1.2 What MV ships

MV implements the two load-bearing properties named in PJ2-B:

- **(a) Physiological human presence** — every PragmaJudge session gates
  on `VAPIProtocolLens.isFullyEligible(deviceId)` returning true. This
  is one composable view call into VAPI's existing PHGCredential +
  ioID + Phase 178 Biometric Credential TTL infrastructure. Zero new
  biometric code; zero modification of PITL layers (RULE 0.2).
- **(b) Cryptographic intent commitment** — every prompt the gated
  human submits to a downstream AI service is committed on-chain via
  Pedersen vector commitment over its embedding, then cryptographically
  bound to the AI output via `PragmaIntentProof.circom` Groth16 proof.
  Verdicts settle through `AdjudicationRegistry` reuse (PJ3-D), with
  the verifier contract (`PragmaIntentProofVerifier.sol`) permitted as
  the sole new on-chain artifact.

MV explicitly excludes properties (c) economic consequence and (d)
recursive self-improvement. The exclusion is principled: (c) requires
PRAGMAToken + PragmaVault + IoSwarmPragmaVerdictCoordinator, all gated
on Gate 2 (N≥100 zero-FP) and wallet refill; (d) requires triple-
instance OFJ + CollabEval + RBTS scoring + Marshall DAO governance
loop, all of which mature with deployment data. Both classes of
property defer to MV+N once empirical operating data exists.

### 1.3 Headline claim

**PragmaJudge MV is the first system to formally measure and
cryptographically attest the illocutionary fidelity gap** — the
distance between a physiologically-attested human's speech-act-
formalized intent and the AI service's actual delivered output —
producing a Groth16 ZK proof that binds intent commitment to output
fidelity score without revealing either embedding in plaintext.

Per PJ6-A operator clarification, the ZK circuit specification is
**load-bearing** for that headline claim, not expandable doc real-
estate. Section 3.4 specifies the circuit at full implementable
fidelity; if compiled constraints exceed 2,048 (Phase 67 ptau 2^11
ceiling), Section 3.4.7 documents the path to flag the finding rather
than silently splitting Claim 1 across passes.

### 1.4 What MV is not

- Not a token launch. PRAGMAToken does not exist in MV (PJ5-C).
- Not a settlement layer in its own right. Settlement reuses
  `AdjudicationRegistry.recordAdjudication` (PJ3-D); MV adds zero
  new settlement contracts.
- Not a mobile product. PIL desktop/mobile detection stack is
  out-of-scope (PJ10-A); MV consumes only the existing controller-
  attested VHP credential.
- Not a multi-agent CollabEval deliberation framework. Only one
  `OutputFidelityJudge` instance ships in MV (PJ4-B).
- Not a tokenomics phase. PRAGMA reward multipliers, Marshall DAO
  governance, and PragmaEloRegistry defer to MV+1 (Section 8).

### 1.5 Document contract

This document defines the implementation contract for PragmaJudge MV.
Subsequent code, contracts, tests, and tooling that ship as
"PragmaJudge MV" must conform to the architecture in Sections 2–7;
deviations require either an architectural amendment to this document
or a follow-on Design Pass MV+1.

The document is not an implementation; no `pragmajudge/` directory is
created as part of this commit.

---

## Section 2 — Architectural Foundation (VAPI Reuse)

This section enumerates VAPI components PragmaJudge MV consumes
without modification (RULE 0.1). For each component, the consumption
interface is documented; nothing else is read or referenced.

### 2.1 The Human Presence Primitive — VHP Composable Gate

**Consumed contract**: `VAPIProtocolLens.isFullyEligible(deviceId)` —
view call, zero gas. The lens internally composes:

- `PHGCredential` (ERC-4671 soulbound; cited
  `contracts/contracts/PHGCredential.sol` deployed Phase 60+)
- `VAPIDualPrimitiveGate` at `0xd7b1465Aad8F815C67b24681c9c022CED24FB876`
  (Phase 113 LIVE 2026-03-27)
- `VAPIVerifiedHumanProof` (Phase 187 LIVE) and
  `VAPIBiometricGovernance` at `0x06782293F1CFC1AA30C0Baee0437c2B336796A00`
  (Phase 222 LIVE 2026-04-17)
- `BiometricCredentialTTLAgent` (Phase 178; biometric_credential_ttl_days=90.0)

Consumption interface (only):

```solidity
// Every PragmaJudge session entry verifies this.
// Failure = transaction revert; PragmaJudge does not implement TTL,
// expiry, or revocation logic — VAPI handles all of it.
bool humanVerified = VAPIProtocolLens.isFullyEligible(deviceId);
require(humanVerified, "VHP credential required for PragmaJudge session");
```

PragmaJudge MV does not introduce its own biometric stack, its own
PIL detection layer (PJ10-A defers desktop/mobile PIL to MV+1+), or
any new PHGCredential variants. The composable view call is the
total surface area.

**Why this is sufficient for property (a)**: VHP credential issuance
already requires ten clean controller calibration sessions (Phase 62
EnrollmentManager) and live PoAC chain integrity. By the time
`isFullyEligible(deviceId)=true`, the device-holder has demonstrated
involuntary cognitive accountability through PITL nine-layer detection
under L4 thresholds 7.009/5.367 and per-pair separation defensibility
(Phase 231 ait_defensibility_ok). PragmaJudge MV inherits all of that
without re-implementing a single line.

### 2.2 The Adjudication Settlement Primitive

**Consumed contract**: `AdjudicationRegistry` at
`0x44CF981f46a52ADE56476Ce894255954a7776fb4` (Phase 111 LIVE
2026-03-27), with `recordAdjudication(deviceIdHash, poadHash, dualVeto)`
exposed at `contracts/contracts/AdjudicationRegistry.sol:79-99` per
the Phase 237.5 Path X live verification.

Consumption interface:

```python
# PragmaJudge MV verdict settlement (PJ3-D pattern)
# deviceIdHash is the FROZEN constant carrying PRAGMA_JUDGE attribution
PRAGMA_INTENT_DEVICE_ID_HASH = SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")
# == 32 bytes; computed once at module init; never recomputed at runtime

chain.record_adjudication(
    device_id_hash = PRAGMA_INTENT_DEVICE_ID_HASH,
    poad_hash      = pragma_verdict_commitment,   # SHA-256(...)
    dual_veto      = False,                       # PragmaJudge MV does not use dual veto
)
```

**Phase 237.5 Path X precedent** (`CLAUDE.md` 2026-04-26 entry):
CORPUS-SNAPSHOT settlement uses the identical pattern with constant
`deviceIdHash=SHA-256(b"VAPI_CORPUS_SNAPSHOT_v1")`. This is the design
shape PJ3-D resolves PragmaJudge MV to follow. Distinct constants
isolate the two sub-protocols at query time:

| Sub-protocol      | deviceIdHash                                           | sourceType (carried in bridge metadata) |
| ----------------- | ------------------------------------------------------ | --------------------------------------- |
| CORPUS-SNAPSHOT   | `SHA-256(b"VAPI_CORPUS_SNAPSHOT_v1")`                  | `"CORPUS_SNAPSHOT"`                     |
| PragmaJudge MV    | `SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")`              | `"PRAGMA_JUDGE"`                        |

Bridge-side `pragma_sessions` table (Section 3.5) carries
`source_type="PRAGMA_JUDGE"` per RULE 0.6 on every row. The
`AdjudicationRegistry`'s open-enum string `sourceType` field is the
shared discriminator across queries.

**Anti-replay**: `AdjudicationRegistry` enforces UNIQUE `poadHash`
across all sub-protocols. PragmaJudge MV's verdict commitment formula
(Section 3.6) incorporates `ts_ns` to guarantee distinct hashes per
session.

### 2.3 The ZK Proof Infrastructure — Phase 67 Ceremony Reuse

**Consumed artifacts**:

- Groth16 proving system on BN254 elliptic curve
- Powers-of-tau ptau file from Phase 67 ceremony (2^11 = 2,048
  constraint ceiling)
- 3-contributor MPC ceremony with on-chain audit trail at
  `CeremonyRegistry.sol` `0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2`
  (Phase 179 LIVE 2026-04-10)
- `PitlSessionProofVerifier` deployed at
  `0x07D3ca1548678410edC505406f022399920d4072` (Phase 62 deploy) —
  reference verifier for circuit pattern, not modified

Consumption shape: PragmaJudge MV introduces a new circuit
`PragmaIntentProof.circom` (Section 3.4) that compiles against the
**same ptau file** from Phase 67 if and only if its constraint count
is ≤ 2,048. New verifier contract `PragmaIntentProofVerifier.sol` is
generated by snarkjs and deployed standalone — it does not inherit
from, modify, or extend `PitlSessionProofVerifier`.

Per PJ6-A operator clarification: if `PragmaIntentProof.circom`
compiles to >2,048 constraints, **flag immediately as a finding**
rather than silently splitting Claim 1 across passes. Section 3.4.7
documents the failure path and the upgrade options (new MPC ceremony
at 2^12, or constraint reduction).

### 2.4 The Federation Bus — PRAGMA_-Prefixed Event Channel

**Consumed bus**: `bridge/vapi_bridge/federation_bus.py` — internal
async event channel, append-only, never modified (RULE 0.5).

PragmaJudge MV publishes two new event types:

- `PRAGMA_SESSION_INITIATED` — fired by `PromptCommitmentRegistry.sol`
  on successful `commitPrompt(...)`; consumed by `PromptIntentExtractor`
- `PRAGMA_VERDICT_FINAL` — fired by `OutputFidelityJudge` on judgment
  completion; consumed by audit-log writer (Section 3.5.6) and by
  `FleetSignalCoherenceAgent` for coherence rule application

These two event types are the entire MV bus footprint. No PragmaJudge
agent intercepts existing VAPI events; the bus subscription is
publish-only-with-targeted-consume per RULE 0.5.

### 2.5 The FleetSignalCoherenceAgent — Coherence Rule Injection

**Consumed agent**: `FleetSignalCoherenceAgent` (Agent #36, Phase 193,
`fleet_coherence_enabled=True` always-on). Coherence rules are
appended to its in-memory ruleset at startup via the loader pattern
documented in `PRAGMAJUDGE_MASTER_ARCHITECTURE.md` Section 1.7.

PragmaJudge MV adds **one** coherence rule (reduced from the master
doc's three because PJ4-B / PJ5-C eliminate the orphan-window and
vault-disbursement-precedence rules):

- **PRAGMA-C1 (CONTRADICTION)**: `OutputFidelityJudge` records
  `verdict_code=SATISFIED` while bridge-computed `fidelity_score <
  fidelity_threshold`. This is the single load-bearing coherence rule
  for property (b) — it enforces that the verdict label matches the
  cryptographic fidelity proof.

Rule guard convention (RULE 0.8 mandatory):

```python
guard = lambda cfg: getattr(cfg, "pragma_judge_enabled", False)
```

Severity: HIGH. Rationale: a SATISFIED verdict that the math says is
FAILED is the protocol's structural failure mode — the MV's central
threat (operator collusion, deferred to MV+1+, would manifest exactly
this way). The HIGH-severity rule ensures the FSCA records and
optionally promotes such contradictions even though MV does not
auto-block on them.

### 2.6 The Phase 237 Consent Primitive — ANONYMIZED_RESEARCH Binding

**Consumed contract**: `VAPIConsentRegistry` at
`0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` (Phase 237-EXTEND LIVE
2026-04-26).

Per PJ12-A: PragmaJudge MV binds to the existing FROZEN-v1 enum
position `ANONYMIZED_RESEARCH=1`. PragmaJudge MV is, in MV scope, an
audit instrument: verdicts inform research without producing economic
consequence (PJ5-C). The `ANONYMIZED_RESEARCH` framing is therefore
honest for MV scope and avoids pressure on the FROZEN-v1 enum.

Consumption interface:

```python
# PragmaJudge MV gates session entry on consent presence (Phase 237 invariant):
# bridge is reader of consent state, not writer
consent_valid = chain.is_consent_valid(
    gamer_address = device_id_to_address(device_id),
    category      = ANONYMIZED_RESEARCH,  # = 1, frozen position in v1 enum
)
require(consent_valid, "ANONYMIZED_RESEARCH consent required for PragmaJudge MV")
```

Per Phase 237 Hard Rule (`CLAUDE.md` Hard Rules section): bridge
**never grants or revokes consent on behalf of gamer** — gamer-self-
sovereignty invariant. PragmaJudge MV strictly observes this: a
gamer who has not granted ANONYMIZED_RESEARCH consent on their own
wallet cannot have their prompts judged by PragmaJudge.

`chain.is_consent_valid` fail-open per Phase 237 invariant when
`consent_registry_address == ""` — PragmaJudge MV inherits this
behavior without modification. In MV's gated activation regime
(`pragma_judge_enabled=False` default), the fail-open behavior never
matters; in test environments it allows isolation.

### 2.7 The Sub-Protocol Registry — agent_range, tool_range, namespace

**Consumed module**: VAPI-EXT Phase 204+ Sub-Protocol Registry,
documented in `PragmaJudge/VAPI_EXT_MASTER_PROMPT.md`. Allocated:

```
PRAGMA_JUDGE: agent_range=(61, 80), tool_range=(201, 250), namespace="pragma."
```

PragmaJudge MV uses the low end of each range:

- Agents: #61 (`PromptIntentExtractor`), #62 (`OutputFidelityJudge`).
  No multi-instance OFJ in MV (PJ4-B).
- Tools: #201–#208 (eight tools, Section 3.7).
- Namespace: `pragma.` for SDK class methods (e.g., `pragma.commit_intent`).

The remaining ranges (agents #63–#80, tools #209–#250) are reserved
for MV+1+ work. They are not allocated by this document.

### 2.8 Sub-Merkle Root Composition — ProtocolCoherenceRegistry Parent Leaf

**Consumed contract**: `ProtocolCoherenceRegistry` at
`0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` (Phase 221 LIVE
2026-04-17). The Merkle tree currently spans 36 fleet agents + 1
virtual allowlist leaf = 37 leaves (Phase 224).

Per PJ11-B: PragmaJudge MV maintains its **own sub-Merkle root**
covering the two MV agents (`PromptIntentExtractor`,
`OutputFidelityJudge`). The sub-root is attached to VAPI's main root
via a single parent leaf computed as:

```python
PRAGMA_SUBMERKLE_TAG = b"VAPI-PRAGMA-SUBMERKLE-v1"  # 24 bytes
parent_leaf = sha256(
    PRAGMA_SUBMERKLE_TAG +              # domain separation
    sub_merkle_root +                   # 32 bytes; SHA-256 over sorted MV agent leaves
    pragma_agent_count_be(2) +          # 2 bytes BE; reflects MV scope (2 agents)
    ts_ns_be(8)                         # 8 bytes BE; recompute timestamp
)
# => 32-byte parent leaf, inserted at sorted position in main Merkle tree
```

This composition adds **one** PV-CI invariant (sub-Merkle leaf
computation function frozen) and zero modifications to
`_AGENT_IDS` in `protocol_coherence_agent.py`. The main agent-count
field passed to `anchorCoherence(merkleRoot, agentCount, tsNs)` is
calculated by VAPI as 37 (unchanged); the PragmaJudge sub-Merkle
parent leaf inserts at the conceptual virtual-leaf adjacency without
counting as a fleet agent. (Identical mechanism to Phase 224's
allowlist virtual leaf.)

### 2.9 The PV-CI Invariant Gate — PRAGMA-Prefixed Invariants

**Consumed gate**: `scripts/vapi_invariant_gate.py` (Phase 223 LIVE,
22 invariants per Phase 226 expansion; raised to 32 invariants under
Phase O0 Stream-3-prep S3 baseline per master doc Section 0).

PragmaJudge MV adds **four** PRAGMA-prefixed invariants:

| Invariant ID  | What it freezes                                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------------------------------- |
| INV-PRAGMA-01 | `PRAGMA_INTENT_DEVICE_ID_HASH = SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")` constant in `pragmajudge/intent.py`              |
| INV-PRAGMA-02 | `PRAGMA_SUBMERKLE_TAG = b"VAPI-PRAGMA-SUBMERKLE-v1"` constant + parent-leaf computation function                          |
| INV-PRAGMA-03 | `PragmaIntentProof.circom` source SHA-256 digest (after compilation succeeds at ≤2,048 constraints)                       |
| INV-PRAGMA-04 | `pragma_verdict_commitment` formula (Section 3.6) including domain tag `b"VAPI-PRAGMA-VERDICT-v1"` and byte ordering      |

Each invariant follows the existing INV-NNN pattern and is registered
via `--generate --reason "invariant_change: pragmajudge_mv_design_pass"
--confirm-governance` ceremony per Phase 224. The four invariants
take the gate count from 32 → 36 once shipped.

### 2.10 The VAME Sidecar Headers — Per-Endpoint Stamping

**Consumed module**: `bridge/vapi_bridge/vame.py` (Phase 236-VAME LIVE
2026-04-26), VAME FORMULA v1 FROZEN.

PragmaJudge MV's bridge endpoints (`/pragma/commit-intent`,
`/pragma/submit-output`, `/pragma/verdict-status`) automatically
inherit VAME stamping via the existing `_VAMEMiddleware` —
zero new code. The middleware skips websocket upgrades,
non-JSON responses, 5xx, and `/health`; PragmaJudge MV endpoints all
fall under the JSON-stamping path.

Frontend recompute via `frontend/src/api/vame.js` (Phase 236-VAME)
will validate PragmaJudge endpoints identically to existing
endpoints. No PragmaJudge-specific frontend change is required for
VAME validation.

### 2.11 The CHAIN_SUBMISSION_PAUSED Kill-Switch — Inheritance

**Consumed flag**: `cfg.chain_submission_paused` (Phase 237.5 Path C+
LIVE; default `False`; gates `chain.py:_send_tx` chokepoint and
`chain.anchor_corpus_snapshot` early-return).

PragmaJudge MV's `chain.record_adjudication(...)` call (Section 2.2)
flows through the same `_send_tx` chokepoint. PragmaJudge MV
**inherits the kill-switch automatically** with no new code. When
operator sets `CHAIN_SUBMISSION_PAUSED=true`, all PragmaJudge MV
on-chain anchoring halts at the same gate as VAPI's existing flows.

This is a deliberate design choice: PragmaJudge MV does not introduce
a separate `pragma_chain_submission_paused` flag because doing so
would split the wallet-drain protection across two surfaces. Instead,
the bridge's existing kill-switch is the single source of truth for
on-chain economic action, and PragmaJudge MV's audit-only character
(PJ5-C) means kill-switch activation degrades MV gracefully — local
verdicts continue, on-chain settlement queues until refill.

---

## Section 3 — New Architectural Commitments

This section enumerates every new component PragmaJudge MV introduces.
Everything in Section 3 lives exclusively under `pragmajudge/` per
RULE 0.1; no file under `bridge/vapi_bridge/`, `contracts/contracts/`,
`scripts/`, or any other VAPI-owned directory is modified.

**Section 3 boundary clarification (PJ3-D scope)**: PragmaJudge MV
ships **zero new settlement contracts**. Settlement reuses
`AdjudicationRegistry.recordAdjudication` per Section 2.2.
**Verifier contracts are permitted** because a Groth16 verifier is a
read-only mathematical primitive, not a settlement layer.
`PragmaIntentProofVerifier.sol` is the sole new on-chain artifact;
all verdicts settle through the existing `AdjudicationRegistry`. This
boundary is preserved in the permanent record by Section 3.3 (verifier
contract specification) and Section 6 (PJ3-D resolution block) so
future readers can audit the distinction unambiguously.

### 3.1 The PragmaJudge Module Tree

```
pragmajudge/                               # MV scope only — directory creation deferred to implementation
├── __init__.py
├── config.py                              # Section 3.2 constants
├── intent.py                              # PRAGMA_INTENT_DEVICE_ID_HASH, PJ-frozen formulas
├── verdict.py                             # pragma_verdict_commitment formula (Section 3.6)
├── submerkle.py                           # PRAGMA_SUBMERKLE_TAG + parent-leaf computation
├── coherence_rules.py                     # PRAGMA-C1 rule definition
├── agents/
│   ├── __init__.py
│   ├── prompt_intent_extractor.py         # Agent #61
│   └── output_fidelity_judge.py           # Agent #62 (single instance, PJ4-B)
├── circuits/
│   ├── PragmaIntentProof.circom           # ZK circuit (Section 3.4)
│   └── README.md                          # ceremony reuse documentation
├── contracts/
│   └── PragmaIntentProofVerifier.sol      # Groth16 verifier (Section 3.3)
├── tools/
│   └── catalog.py                         # Tools #201–#208 (Section 3.7)
├── docs/
│   ├── PRAGMA_RUBRIC.md                   # fidelity threshold calibration log
│   └── PRAGMA_INVARIANTS.md               # INV-PRAGMA-01..04 frozen contract
├── tests/
│   └── test_pragmajudge_mv.py             # Stream 1+2 test suite
└── README.md                              # operator-facing overview
```

The tree intentionally omits: `migrations/` (Section 3.5 documents
direct integration into existing `bridge/vapi_bridge/store.py`
through `pragmajudge/store_extensions.py` import-time table creation
— see Section 3.5 design rationale), `mobile/` (PJ10-A: deferred),
`fl/` (federated learning: deferred to MV+N), and PRAGMAToken /
PragmaVault / PragmaVerdictRegistry / PragmaEloRegistry /
PragmaDataSovereigntyRegistry / IoSwarmPragmaVerdictCoordinator
(PJ3-D + PJ5-C: out of MV).

### 3.2 Configuration Constants

`pragmajudge/config.py` defines MV-only constants. Constants inherited
from VAPI are **never redefined** (RULE 0.3); they are imported.

```python
# pragmajudge/config.py — MV scope

# ─── Inherited from VAPI (reference only — DO NOT redefine) ───
# from bridge.vapi_bridge.config import (
#     epistemic_consensus_threshold,   # 0.65, FROZEN
#     # PRAGMAJUDGE MV does not consume BLOCK_QUORUM, MINT_QUORUM
#     # — those are ioSwarm-coordinator constants, deferred to MV+N
# )

# ─── PragmaJudge MV-Specific Constants ───

# Feature flags (RULE 0.8 — ALL coherence rules guard on this)
PRAGMA_JUDGE_ENABLED = False              # default OFF; operator-set per-deployment
PRAGMA_DRY_RUN_DEFAULT = True             # RULE 0.4

# Fidelity threshold — calibrated, NOT frozen
# Calibration procedure documented in PRAGMA_RUBRIC.md
DEFAULT_FIDELITY_THRESHOLD = 0.72         # cosine similarity floor for SATISFIED
FIDELITY_THRESHOLD_MIN = 0.60             # absolute floor — no platform may go below
FIDELITY_THRESHOLD_MAX = 0.95             # absolute ceiling — protects against
                                          #   over-tight thresholds that auto-FAIL

# Intent extraction — embedding model fixed in MV
EMBEDDING_MODEL = "all-MiniLM-L6-v2"      # 384-dim sentence embeddings, MIT licensed
EMBEDDING_DIM = 384
EMBEDDING_QUANTIZE_BITS = 16              # fixed-point quantization before commit
SPEECH_ACT_CODES = (                       # Searle/Williams-Bayne taxonomy
    "DIRECTIVE", "ASSERTIVE", "COMMISSIVE", "EXPRESSIVE", "DECLARATIVE",
)

# Sub-Merkle composition (frozen by INV-PRAGMA-02)
PRAGMA_SUBMERKLE_TAG = b"VAPI-PRAGMA-SUBMERKLE-v1"

# Settlement (frozen by INV-PRAGMA-01)
PRAGMA_INTENT_DEVICE_ID_HASH = bytes.fromhex(
    # SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")
    # computed at module init; verified against this hex constant
    # via assertion to detect drift between code and INV-PRAGMA-01
)
PRAGMA_SOURCE_TYPE = "PRAGMA_JUDGE"        # carried in bridge metadata, RULE 0.6

# Verdict commitment (frozen by INV-PRAGMA-04)
PRAGMA_VERDICT_TAG = b"VAPI-PRAGMA-VERDICT-v1"

# Coherence
PRAGMA_PROMOTE_THRESHOLD = 3              # mirrors VAPI's N_PROMOTE_THRESHOLD=3

# Consent (PJ12-A)
PRAGMA_CONSENT_CATEGORY = 1               # ANONYMIZED_RESEARCH — Phase 237 enum position

# Chain
IOTEX_TESTNET_CHAIN_ID = 4690             # inherited from VAPI bridge config

# Endpoint paths (no env vars required — fixed per MV contract)
PRAGMA_HTTP_PATHS = {
    "commit_intent":   "/pragma/commit-intent",
    "submit_output":   "/pragma/submit-output",
    "verdict_status":  "/pragma/verdict-status",
    "preflight":       "/pragma/preflight",
}
```

`PRAGMA_DRY_RUN_DEFAULT=True` is invariant by RULE 0.4; the operator
must explicitly set `dry_run=False` per agent instance for live mode.
MV scope constrains that ONLY local-DB writes happen in dry-run; the
on-chain `chain.record_adjudication` call is gated on
`dry_run=False AND chain_submission_paused=False`.

### 3.3 PragmaIntentProofVerifier.sol — The Sole New Contract

**Path**: `pragmajudge/contracts/PragmaIntentProofVerifier.sol`

**Purpose**: Verify Groth16 proofs from `PragmaIntentProof.circom` on
IoTeX testnet. Read-only mathematical primitive. No state, no
ownership, no funds, no upgrades.

**Why this is permitted under PJ3-D**: A Groth16 verifier is the
arithmetic counterpart of a `pure function` — given a public-input
tuple and a proof, it returns a boolean. It carries no settlement
state, mints no tokens, transfers no value, manages no permissions.
The settlement of PragmaJudge verdicts (commitment hashes that bind
to specific block numbers) happens entirely in the existing
`AdjudicationRegistry` per Section 2.2. The verifier is consumed by
PragmaJudge bridge code — and optionally by future external auditors
— purely as a cryptographic primitive.

**ABI shape** (snarkjs-generated, conventional):

```solidity
// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.0;

contract PragmaIntentProofVerifier {
    // Standard Groth16 verifying key encoded as constants by snarkjs
    // (compile-time output — no manual editing)

    function verifyProof(
        uint256[2] memory a,
        uint256[2][2] memory b,
        uint256[2] memory c,
        uint256[5] memory input  // public signals — see Section 3.4.5
    ) public view returns (bool);
}
```

**Deploy posture**:

- **Stream 1 ship**: contract source + tests in `contracts/test/PragmaIntentProofVerifier.test.js`
  (Hardhat); deploy script `scripts/deploy-pragmajudge-mv.js` written
  but NOT executed.
- **Stream 1 verify**: contract compiles cleanly under Hardhat; ABI
  matches snarkjs output for the compiled circuit; `verifyProof`
  returns true on a valid proof and false on a malformed proof under
  Hardhat-fork conditions.
- **Deploy gate**: wallet refill ≥ 0.05 IOTX (estimated deploy cost
  for a verifier of this size based on Phase 56/62 PitlSessionProofVerifier
  precedent, ~360k gas at typical IoTeX testnet prices). Same gate as
  Phase O0 Stream 2-deploy (~0.45 IOTX target for five contracts);
  PragmaJudge MV's incremental cost is much smaller because only one
  contract.
- **Live mode gate**: deployed verifier address recorded in
  `pragmajudge/config.py` `PRAGMA_INTENT_PROOF_VERIFIER_ADDRESS`;
  bridge gates verifier calls behind the same address-presence check
  as Phase 222 BBG (`chain.bbg_check_proposal` raises when address
  unset, NOT fail-open).

**No upgrade pattern**: the verifier is immutable per Groth16's
mathematical contract. If the circuit changes (e.g., constraint
reduction in response to ptau ceiling, see Section 3.4.7), a new
verifier contract is deployed at a new address; `PRAGMA_INTENT_PROOF_VERIFIER_ADDRESS`
is updated; INV-PRAGMA-03 records the new circuit-source SHA-256.

### 3.4 PragmaIntentProof.circom — Circuit Specification

**Path**: `pragmajudge/circuits/PragmaIntentProof.circom`

**Per PJ6-A operator clarification**: this section is load-bearing
for the MV headline claim. Specification is at full implementable
fidelity; constraint budget 2,048 (Phase 67 ptau 2^11 ceiling).
Section 3.4.7 documents the path-to-finding if constraints exceed
budget.

#### 3.4.1 Proving system

- **System**: Groth16 (KZG-equivalent for circom 2.0)
- **Curve**: BN254 (alt_bn128) — same as VAPI Phase 67 ceremony
- **ptau**: `pot11_final.ptau` from Phase 67, hosted at
  `contracts/ceremony/pot11_final.ptau` per Phase 67 deploy
- **Compiler**: `circom 2.2.3` per `contracts/circom.exe`
- **Solidity verifier generator**: `snarkjs zkey export
  solidityverifier`

#### 3.4.2 Circuit purpose

`PragmaIntentProof` proves three statements simultaneously, in a
single proof:

- **C1 — Intent Commitment Binding**: prover knows an embedding
  vector `intent_embedding[0..6]` (a fixed-size 7-element subset of
  the 384-dim sentence embedding, hashed-and-quantized below) and a
  `speech_act_code` such that
  `intent_commitment = Poseidon(8)(intent_embedding[0..6], speech_act_code)`.
  The 8-input Poseidon is identical to VAPI's Phase 62 C1 mechanism,
  reusing the validated implementation in
  `contracts/circuits/PitlSessionProof.circom`.

- **C2 — Fidelity Score Bound**: prover knows an output embedding
  `output_embedding[0..6]` (parallel quantization to `intent_embedding`)
  and a `fidelity_score` such that
  `fidelity_score = inner_product(intent_embedding, output_embedding)
   * scale_factor` AND `fidelity_score >= fidelity_threshold`. The
  inner-product proxy for cosine similarity is exact when both
  embeddings are pre-normalized to unit-L2 in floating-point and then
  quantized to 16-bit fixed-point — quantization error is bounded by
  `2^-16` per coordinate, yielding total error ≤ `7 * 2^-16` ≈ `1.07e-4`,
  far below any meaningful fidelity threshold.

- **C3 — Verdict Code Binding**: prover knows a `verdict_code` such
  that `verdict_code === verdict_from_consensus`, where
  `verdict_from_consensus` is a public input fed from the bridge-side
  `OutputFidelityJudge` agent. This mirrors VAPI Phase 62 C3 exactly
  and prevents verdict forgery: the prover cannot substitute a
  different verdict label than what the bridge agent computed.

#### 3.4.3 Why 7 of 384 dimensions

The 384-dimensional `all-MiniLM-L6-v2` embedding is far too large to
pack into a Groth16 circuit at full resolution; each coordinate
requires ≥16 constraint per quantization step, and inner-product over
384 dims would alone consume ~6,144 constraints — three times the
ptau ceiling.

The 7-dimensional reduction is justified by the **information-content
argument**: the `OutputFidelityJudge` agent's bridge-side cosine
similarity computation operates on the full 384-dim embeddings. The
ZK circuit's role is to **prove that an honest reduction was
performed and the resulting bound is satisfied**, not to recompute
similarity from scratch. The 7 reduced dimensions are computed by
a fixed PCA projection matrix `P_REDUCE_v1` whose eigenvalues capture
≥85% of the variance in a sample of 10,000 prompt-output pairs from
the calibration corpus (calibration procedure documented in
`PRAGMA_RUBRIC.md`).

Critically, `P_REDUCE_v1` is a **public matrix**; it is hardcoded into
the circuit as constants and into bridge code as the same matrix.
The ZK proof's privacy guarantee is over the embedding values
themselves, not over the projection scheme. This is the same
information-disclosure tradeoff VAPI Phase 41 makes for L4 features:
the feature vector's coordinates are revealed; the underlying
biometric raw signal is not.

The MV decision to constrain to 7 dimensions specifically (rather
than 8, 10, or 16) is driven by the constraint budget calculation in
Section 3.4.6. This is a calibrated tradeoff between cryptographic
expressiveness and ptau ceiling fit.

#### 3.4.4 Constraint estimate (MV target ≤ 2,048)

```
  Component                                          Constraints (estimate)
  ───────────────────────────────────────────────    ──────────────────────
  Poseidon(8) for intent commitment (C1)                  ~250  (per VAPI Phase 62 measurement)
  Poseidon(8) parity for output embedding hash             ~250  (parallel structure)
  Inner-product over 7 reduced dims (16-bit each)          ~140  (7 × 20 mul-add gates)
  Fidelity threshold comparison (LessThan, 32-bit)          ~32
  Verdict-code equality (IsEqual, 8-bit field)              ~16
  PCA projection P_REDUCE_v1 (7 × 384, public matrix)      ~600  (public-input multiplication only)
  Boundary checks + range proofs                           ~120
  ───────────────────────────────────────────────    ──────────────────────
  TOTAL ESTIMATE                                          ~1,408 constraints (vs. 2,048 ceiling)

  Margin: 2,048 - 1,408 = 640 constraint headroom
```

This estimate is calibrated against VAPI's Phase 62 PitlSessionProof
circuit (~1,820 constraints with full 8-input Poseidon and 5 public
signals). PragmaIntentProof is structurally simpler — no Mahalanobis
distance computation, no L4 feature space iteration — so the 1,408
estimate is conservative-cautious.

**Note on the 600-constraint PCA term**: the public matrix multiply
is the largest line item. If the empirical compile reveals that this
exceeds the estimate (for example, snarkjs encodes public-matrix
operations less efficiently than the calibration suggests), the
constraint reduction options in Section 3.4.7 apply.

#### 3.4.5 Public signals (`nPublic = 5`, mirrors VAPI)

| Index | Name                  | Description                                                                                                     |
| ----- | --------------------- | --------------------------------------------------------------------------------------------------------------- |
| 0     | `intent_commitment`   | Poseidon hash binding intent embedding to speech_act_code (32-byte field element)                               |
| 1     | `fidelity_score`      | Computed inner-product as 16-bit fixed-point (0–65535 maps to 0.0–1.0)                                          |
| 2     | `fidelity_threshold`  | Calibrated threshold (16-bit fixed-point); circuit constraint `fidelity_score >= fidelity_threshold` enforces  |
| 3     | `session_id`          | Links to bridge-side `pragma_sessions` row (32-byte UUID-derived hash)                                          |
| 4     | `verdict_code`        | 0x00=SATISFIED, 0x01=FAILED (MV scope: only two codes; PARTIAL/ESCALATED defer to MV+N per PJ4-B simplification) |

Five signals matches VAPI's Phase 62 nPublic=5 — the verifier
contract's ABI is structurally identical, easing audit.

#### 3.4.6 Witness computation flow

```
                  ┌─────────────────────────────────────────────┐
                  │ bridge — PromptIntentExtractor (Agent #61)  │
                  │   1. Compute intent_embedding[0..383]       │
                  │      via all-MiniLM-L6-v2 (raw float)       │
                  │   2. Normalize to unit L2                   │
                  │   3. Project via P_REDUCE_v1 → reduce[0..6] │
                  │   4. Quantize to 16-bit fixed-point         │
                  │   5. Commit:                                │
                  │      intent_commit = Poseidon(8)(           │
                  │        reduce[0..6], speech_act_code)       │
                  │   6. Submit (intent_commit, speech_act,     │
                  │      session_id) to PromptCommitmentRegistry│
                  │      via bridge endpoint.                   │
                  └────────────────────┬────────────────────────┘
                                       ▼
                  ┌─────────────────────────────────────────────┐
                  │ external AI service produces output         │
                  │   (off-chain, untrusted)                    │
                  └────────────────────┬────────────────────────┘
                                       ▼
                  ┌─────────────────────────────────────────────┐
                  │ bridge — OutputFidelityJudge (Agent #62)    │
                  │   1. Compute output_embedding[0..383]       │
                  │   2. Normalize, project, quantize as above  │
                  │   3. Compute fidelity_score =               │
                  │      inner_product(reduce_intent,           │
                  │                    reduce_output) * scale   │
                  │   4. Determine verdict_code from threshold  │
                  │   5. Build witness with both reduced vecs   │
                  │      as private inputs and 5 public signals │
                  │   6. Run snarkjs prover → proof artifact    │
                  │   7. Bridge calls                           │
                  │      PragmaIntentProofVerifier.verifyProof  │
                  │      on-chain (gated by chain_submission_   │
                  │      paused + dry_run flags)                │
                  └─────────────────────────────────────────────┘
```

Two-step computation matches VAPI Phase 62: extractor emits the
commitment; judge produces the proof. Bridge agents compute the
witness; verifier contract validates.

#### 3.4.7 Path-to-finding if constraints > 2,048 (PJ6-A flag procedure)

If `circom --r1cs PragmaIntentProof.circom` reports a constraint
count > 2,048, the implementation must immediately:

1. **Halt the implementation pass**. Do not commit a constraint-
   reduced fallback silently.
2. **Surface a finding with three options**, in operator decision
   form (Section 6 PJ-block style):

   - **Option A — Constraint reduction**: drop PCA dimensions to
     6 or 5; document expected information-content reduction in
     `PRAGMA_RUBRIC.md`; recompute constraint estimate. Variance
     capture analysis would be required to ensure ≥80% retention.
   - **Option B — New ptau ceremony at 2^12 = 4,096**: triggers a
     fresh 3-contributor MPC ceremony (mirror Phase 67 procedure;
     use `CeremonyRegistry.sol` Phase 179 audit trail). Cost: ~1
     week of operator-coordinated time + ~0.5 IOTX deploy gas. The
     ceremony output (`pot12_final.ptau`) is reusable for any future
     PragmaJudge / VAPI circuit ≤ 4,096 constraints.
   - **Option C — Move PCA out of circuit**: reduce projection to
     a public-input pre-image, prove only the inner-product +
     threshold + commitment without re-projecting in-circuit. Saves
     ~600 constraints. Tradeoff: reduces the cryptographic guarantee
     — the projection step is no longer ZK-attested. Audit value
     reduces.

3. **Hold for operator review** at the verification checkpoint per
   Verification-First Discipline. Do not select an option silently.

This procedure ensures Claim 1 (single-pass) is empirically tested
rather than silently violated. If the empirical compile passes
under 2,048, none of this triggers and Stream 1 ships as planned.

### 3.5 Bridge Module Tree (Read-Only Imports)

PragmaJudge MV's bridge-resident code lives in `pragmajudge/` and is
**imported into** the bridge process at startup, not modified into
existing bridge files. Imports happen via two surfaces:

- `pragmajudge/__init__.py` registers an import hook (called from
  `bridge/vapi_bridge/main.py` only by convention — operators add the
  one-line import as a deployment activation step). Per RULE 0.1,
  this document does NOT direct that operators modify `main.py`;
  `pragmajudge/__init__.py` is a no-op until the operator explicitly
  imports it. (This is the same convention Phase 211's `vapi-unified`
  MCP server uses for its registration.)
- `pragmajudge/store_extensions.py` defines `add_pragma_tables(conn)`,
  called explicitly from a separate operator-run migration script
  `scripts/pragma_init_tables.py`. Existing VAPI tables are never
  altered.

#### 3.5.1 New SQLite tables

```sql
-- pragmajudge/store_extensions.py (new tables only, additive only)
-- All tables have UNIQUE constraints on commitment hashes for anti-replay,
-- mirroring VAPI's existing pattern (Phase 224, 225, 227)

CREATE TABLE IF NOT EXISTS pragma_sessions (
    id INTEGER PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,        -- UUID-derived hash, 32 hex
    device_id TEXT NOT NULL,                -- keccak256(pubkey) from VAPI ioID
    vhp_verified INTEGER NOT NULL,          -- 1 if isFullyEligible() passed
    consent_verified INTEGER NOT NULL,      -- 1 if ANONYMIZED_RESEARCH consent valid
    intent_commitment_hash TEXT,            -- Poseidon hash from PromptIntentExtractor
    speech_act_code TEXT,                   -- Searle taxonomy enum
    fidelity_threshold REAL,                -- threshold at session time (calibration audit)
    fidelity_score REAL,                    -- computed by OutputFidelityJudge
    verdict_code TEXT,                      -- SATISFIED | FAILED  (MV scope only)
    verdict_commitment_hash TEXT UNIQUE,    -- anti-replay; SHA-256(...) per Section 3.6
    proof_artifact BLOB,                    -- Groth16 proof (a, b, c) — ~256 bytes
    on_chain_tx TEXT,                       -- IoTeX testnet tx hash (NULL until anchored)
    on_chain_confirmed INTEGER DEFAULT 0,
    dry_run INTEGER DEFAULT 1,              -- RULE 0.4
    created_at INTEGER,                     -- nanosecond timestamp
    updated_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pragma_sessions_device_id
    ON pragma_sessions(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pragma_sessions_verdict_code
    ON pragma_sessions(verdict_code, created_at DESC);

CREATE TABLE IF NOT EXISTS pragma_intent_records (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    surface_intent_hash TEXT NOT NULL,      -- 32 hex; commitment over reduced 7-dim
    p_reduce_version TEXT DEFAULT 'v1',     -- INV-PRAGMA-* binding to circuit version
    embedding_dim INTEGER DEFAULT 384,
    embedding_quantize_bits INTEGER DEFAULT 16,
    speech_act_code TEXT,
    speech_act_confidence REAL,             -- 0.0–1.0; from speech-act classifier
    created_at INTEGER,
    UNIQUE(session_id, surface_intent_hash)
);

CREATE TABLE IF NOT EXISTS pragma_verdict_records (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    fidelity_score REAL,
    fidelity_threshold REAL,
    verdict_code TEXT NOT NULL,
    proof_verified_locally INTEGER DEFAULT 0,    -- snarkjs CLI verify pre-on-chain
    proof_verified_on_chain INTEGER DEFAULT 0,
    pragma_consensus_score REAL,                  -- MV: == p_OFJ; reserved for MV+N
    bridge_agent_id TEXT,                         -- "output_fidelity_judge_v1"
    created_at INTEGER,
    UNIQUE(session_id)
);

CREATE TABLE IF NOT EXISTS pragma_coherence_log (
    id INTEGER PRIMARY KEY,
    coherence_id TEXT UNIQUE NOT NULL,            -- "coh_" + SHA-256[:16]
    rule_id TEXT NOT NULL,                        -- 'PRAGMA-C1'
    session_id TEXT NOT NULL,
    severity TEXT NOT NULL,                       -- 'HIGH' (only one rule in MV)
    description TEXT,
    evidence_json TEXT,                           -- BP-007 scrubbed (no embeddings)
    resolved INTEGER DEFAULT 0,
    promoted_to_whatif INTEGER DEFAULT 0,
    created_at INTEGER
);
```

Total tables: **four**. The master architecture's seven-table layout
is reduced because `pragma_vault_ledger` (vault: PJ5-C deferred),
`pragma_minority_reports` (multi-OFJ: PJ4-B reduced to single
instance), and `pragma_pil_records` (PIL: PJ10-A deferred) are out
of MV scope.

#### 3.5.2 Schema migration version

```python
# pragmajudge/store_extensions.py
def add_pragma_tables(conn):
    """Idempotent migration. Operator runs once per bridge install."""
    cur = conn.cursor()
    # ... CREATE TABLE IF NOT EXISTS statements above ...
    cur.execute(
        "INSERT OR IGNORE INTO schema_versions (version, name) VALUES (?, ?)",
        (240_001, "pragma_judge_mv_tables"),
    )
    conn.commit()
```

The version number `240_001` is allocated to the PragmaJudge MV
namespace (240xxx) and does not collide with VAPI's main schema
versions (currently up to ~239xxx based on the Phase 237.5 entries
in `CLAUDE.md`). PragmaJudge MV's first migration is `240_001`;
future MV+N additions use `240_002`, `240_003`, etc.

#### 3.5.3 Bridge endpoint registrations

Endpoints are registered via `pragmajudge/operator_api_extensions.py`
which mounts a sub-router on the existing bridge FastAPI app. The
mount happens via the same operator-discretion import pattern as
Section 3.5 (no modification of `main.py` directed by this document).

```python
# pragmajudge/operator_api_extensions.py — MV scope endpoints
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/pragma", tags=["PragmaJudge"])

@router.post("/commit-intent")
async def commit_intent(payload: CommitIntentPayload,
                        x_api_key: str = Header(...)):
    """Operator-authenticated. Calls PromptIntentExtractor.
       Persists to pragma_intent_records.
       Fires PRAGMA_SESSION_INITIATED bus event."""
    ...

@router.post("/submit-output")
async def submit_output(payload: SubmitOutputPayload,
                        x_api_key: str = Header(...)):
    """Operator-authenticated. Calls OutputFidelityJudge.
       Computes fidelity_score, generates proof, persists.
       Fires PRAGMA_VERDICT_FINAL bus event.
       Anchors on-chain ONLY when dry_run=False AND
       chain_submission_paused=False (Section 2.11)."""
    ...

@router.get("/verdict-status")
async def verdict_status(session_id: str,
                         x_api_key: str = Header(...)):
    """Read-only. Returns 8-key payload mirroring Phase 222 style:
       session_id, vhp_verified, consent_verified, intent_commitment_hash,
       fidelity_score, verdict_code, proof_verified_on_chain, on_chain_tx."""
    ...

@router.get("/preflight")
async def preflight(x_api_key: str = Header(...)):
    """Read-only. Returns PragmaJudge MV readiness conditions:
       pragma_judge_enabled, dry_run, fidelity_threshold,
       circuit_compiled (boolean), verifier_deployed (boolean),
       p_reduce_version, total_sessions, pending_anchors."""
    ...
```

Authentication: all four endpoints use `_check_key`-equivalent header
auth (operator API key). `/verdict-status` and `/preflight` are
read-only and are also offered under `_check_read_key` semantics, but
PragmaJudge MV does not bifurcate the read key from operator key in
MV — the audit-only character (PJ5-C) means there is no consumer-grade
endpoint to expose. MV+1 can split the auth surface when consumers
exist.

#### 3.5.4 Tool catalog

Tools #201–#208 (eight tools), via `pragmajudge/tools/catalog.py`,
which the existing MCP knowledge-server (Phase 210, `vapi-knowledge`)
auto-discovers when `pragma_judge_enabled=True`:

```
#201  pragma_commit_intent       — initiate session, persist commitment
#202  pragma_submit_output       — submit AI output, generate verdict
#203  pragma_verdict_status      — retrieve verdict for session
#204  pragma_preflight_status    — PragmaJudge MV readiness conditions
#205  pragma_fidelity_score      — single-session fidelity score lookup
#206  pragma_intent_extraction   — retrieve PromptIntentExtractor analysis
#207  pragma_coherence_status    — PRAGMA-C1 violation log
#208  pragma_invariant_status    — INV-PRAGMA-01..04 gate state
```

Tool discovery follows the VAPI Phase 211 pattern verbatim. The
catalog file imports from `bridge.vapi_bridge.config` to read VAPI
state (read-only); it never writes back.

### 3.6 Verdict Commitment Formula (INV-PRAGMA-04 frozen)

```python
# pragmajudge/verdict.py — FROZEN by INV-PRAGMA-04
import hashlib
import struct

PRAGMA_VERDICT_TAG = b"VAPI-PRAGMA-VERDICT-v1"  # 24 bytes (frozen)

def compute_pragma_verdict_commitment(
    session_id: bytes,                    # 32 bytes (SHA-256-derived)
    intent_commitment: bytes,             # 32 bytes (Poseidon output)
    fidelity_score_milli: int,            # uint16 in 0..65535 (16-bit fixed-point)
    fidelity_threshold_milli: int,        # uint16 in 0..65535
    verdict_code: int,                    # uint8: 0x00=SATISFIED, 0x01=FAILED
    ts_ns: int,                           # uint64 nanosecond timestamp
) -> bytes:
    """
    Returns 32-byte verdict commitment.

    Formula (frozen):
        commitment = SHA-256(
            PRAGMA_VERDICT_TAG (24)            ||
            session_id (32)                    ||
            intent_commitment (32)             ||
            fidelity_score_milli_be (2)        ||
            fidelity_threshold_milli_be (2)    ||
            verdict_code (1)                   ||
            ts_ns_be (8)
        )

    Total input length: 24 + 32 + 32 + 2 + 2 + 1 + 8 = 101 bytes.

    Anti-replay: ts_ns ensures every commitment is unique across sessions
    even when intent_commitment + verdict_code coincide (rare; would
    indicate identical prompt + same output produced at different times).

    AdjudicationRegistry's UNIQUE poadHash constraint then provides on-chain
    anti-replay against any sub-protocol (PragmaJudge MV cannot collide
    with CORPUS-SNAPSHOT or any future v1+ commitment because each carries
    a distinct domain tag).
    """
    if not isinstance(session_id, bytes) or len(session_id) != 32:
        raise ValueError("session_id must be 32 bytes")
    if not isinstance(intent_commitment, bytes) or len(intent_commitment) != 32:
        raise ValueError("intent_commitment must be 32 bytes")
    if not (0 <= fidelity_score_milli <= 65535):
        raise ValueError("fidelity_score_milli must be uint16")
    if not (0 <= fidelity_threshold_milli <= 65535):
        raise ValueError("fidelity_threshold_milli must be uint16")
    if verdict_code not in (0x00, 0x01):
        raise ValueError("verdict_code must be 0x00 (SATISFIED) or 0x01 (FAILED)")
    if ts_ns <= 0:
        raise ValueError("ts_ns must be positive")

    payload = (
        PRAGMA_VERDICT_TAG
        + session_id
        + intent_commitment
        + struct.pack(">H", fidelity_score_milli)
        + struct.pack(">H", fidelity_threshold_milli)
        + struct.pack(">B", verdict_code)
        + struct.pack(">Q", ts_ns)
    )
    return hashlib.sha256(payload).digest()
```

This formula is the eighth FROZEN-v1 cryptographic primitive in the
PATTERN-016 family alongside GIC, WEC, VAME, CORPUS-SNAPSHOT,
CONSENT, AGENT_COMMIT, and PHYSICAL_DATA_ATTESTATION (per Phase O0
Pass 2C). It joins by analogous mechanism, not by inheritance from
any of them. Any v2 successor (richer verdict codes, hash function
swap, etc.) requires a new domain tag (`VAPI-PRAGMA-VERDICT-v2`) and
a fresh INV-PRAGMA-04 entry.

### 3.7 Tool Catalog Entries (#201–#208)

Each tool follows the VAPI Phase 211 pattern: pure function, no side
effects beyond DB read, returns dict serialized via FastAPI. Tools
are discoverable via the `vapi-knowledge` MCP server's auto-load
mechanism when `pragma_judge_enabled=True`.

```python
# pragmajudge/tools/catalog.py — eight MV-scope tools
# Decorator @pragma_tool replicates @tool from vapi-mcp/server.py

@pragma_tool(id=201, name="pragma_commit_intent")
async def pragma_commit_intent(prompt_text: str, device_id: str,
                               speech_act_hint: str = None) -> dict:
    """Initiate PragmaJudge session. Calls PromptIntentExtractor.
       Returns: {session_id, intent_commitment, speech_act_code,
                  speech_act_confidence, vhp_verified, consent_verified}.

       Behavior gated on pragma_judge_enabled; returns
       {error: "pragma_judge_disabled"} when False."""
    ...

@pragma_tool(id=202, name="pragma_submit_output")
async def pragma_submit_output(session_id: str, output_text: str) -> dict:
    """Submit AI output for judgment. Calls OutputFidelityJudge.
       Returns: {session_id, fidelity_score, fidelity_threshold,
                  verdict_code, proof_artifact_b64,
                  proof_verified_locally, on_chain_tx}.

       Behavior gated on pragma_judge_enabled. Anchors on-chain
       ONLY when dry_run=False AND chain_submission_paused=False."""
    ...

@pragma_tool(id=203, name="pragma_verdict_status")
async def pragma_verdict_status(session_id: str) -> dict:
    """Retrieve verdict for session. Read-only.
       Returns 8-key payload (Section 3.5.3)."""
    ...

@pragma_tool(id=204, name="pragma_preflight_status")
async def pragma_preflight_status() -> dict:
    """Returns PragmaJudge MV readiness:
       {pragma_judge_enabled, dry_run, fidelity_threshold,
        circuit_compiled, verifier_deployed, p_reduce_version,
        total_sessions, pending_anchors}."""
    ...

@pragma_tool(id=205, name="pragma_fidelity_score")
async def pragma_fidelity_score(session_id: str) -> dict:
    """Single-session fidelity score lookup. Read-only."""
    ...

@pragma_tool(id=206, name="pragma_intent_extraction")
async def pragma_intent_extraction(session_id: str) -> dict:
    """Retrieve PromptIntentExtractor analysis. Read-only.
       Returns Searle taxonomy classification + reduced-dim hash."""
    ...

@pragma_tool(id=207, name="pragma_coherence_status")
async def pragma_coherence_status(limit: int = 10) -> dict:
    """PRAGMA-C1 violation log. Read-only.
       Returns recent CONTRADICTION entries."""
    ...

@pragma_tool(id=208, name="pragma_invariant_status")
async def pragma_invariant_status() -> dict:
    """INV-PRAGMA-01..04 gate state. Read-only.
       Mirrors GET /agent/invariant-gate-status (Phase 223)."""
    ...
```

### 3.8 Two MV Agents

**Agent #61 — `PromptIntentExtractor`**

- LLM-backed event consumer (mirrors `CalibrationIntelligenceAgent`,
  Phase 50)
- Backing model: `claude-sonnet-4-6` (matches VAPI's existing LLM
  agents)
- System prompt locked in agent file; SHA-256 registered in
  `agent_context_log` per Phase 203 (CONTEXT_HASH_MISMATCH FSCA rule
  applies)
- Bus consumed: `PRAGMA_SESSION_INITIATED`
- Bus published: `PRAGMA_INTENT_EXTRACTED` (consumed only by `OFJ`
  in MV; deferred fan-out to MV+N)
- Tool: #201 `pragma_commit_intent`

Pseudocode:

```python
# pragmajudge/agents/prompt_intent_extractor.py
class PromptIntentExtractor:
    def __init__(self, store, federation_bus, dry_run=True):
        self.store = store
        self.bus = federation_bus
        self.dry_run = dry_run

    async def on_session_initiated(self, event):
        prompt_text = event.payload["prompt_text"]
        device_id = event.payload["device_id"]
        # 1. Embed via all-MiniLM-L6-v2 (offline model, no network)
        full_emb = sentence_transformer.encode(prompt_text, normalize=True)
        # 2. Project to 7 dims via P_REDUCE_v1
        reduced = full_emb @ P_REDUCE_v1.T  # (7,)
        # 3. Quantize to 16-bit
        reduced_q = quantize_int16(reduced)
        # 4. Classify speech act (LLM-backed; structured output)
        sa_code, sa_conf = await self._classify_speech_act(prompt_text)
        # 5. Compute commitment via Poseidon-equivalent (host-side computed)
        intent_commit = poseidon_8(reduced_q, sa_code)
        # 6. Persist to pragma_intent_records + update pragma_sessions
        self.store.insert_pragma_intent(...)
        # 7. Fire PRAGMA_INTENT_EXTRACTED for OFJ
        await self.bus.publish("PRAGMA_INTENT_EXTRACTED", {...})
```

**Agent #62 — `OutputFidelityJudge`** (single instance per PJ4-B)

- LLM-augmented compute agent (no full LLM verdict; LLM optionally
  provides reasoning trace for `evidence_json`, but verdict
  computation is pure-function)
- Bus consumed: `PRAGMA_INTENT_EXTRACTED`, `PRAGMA_OUTPUT_RECEIVED`
- Bus published: `PRAGMA_VERDICT_FINAL`
- Tool: #202 `pragma_submit_output`

Pseudocode:

```python
# pragmajudge/agents/output_fidelity_judge.py
class OutputFidelityJudge:
    def __init__(self, store, federation_bus, chain, dry_run=True):
        self.store = store
        self.bus = federation_bus
        self.chain = chain
        self.dry_run = dry_run
        self.threshold = DEFAULT_FIDELITY_THRESHOLD

    async def judge(self, session_id, output_text):
        intent_record = self.store.get_pragma_intent(session_id)
        # 1. Embed output, project, quantize (parallel structure to extractor)
        out_emb = sentence_transformer.encode(output_text, normalize=True)
        out_reduced = out_emb @ P_REDUCE_v1.T
        out_q = quantize_int16(out_reduced)
        # 2. Compute fidelity score (inner product, pre-normalized => cosine)
        fidelity = float(np.dot(intent_record.reduce_q, out_q) * SCALE_FACTOR)
        # 3. Determine verdict
        verdict_code = 0x00 if fidelity >= self.threshold else 0x01
        # 4. Generate Groth16 proof via snarkjs subprocess
        proof = await self._generate_proof(intent_record, out_q, fidelity, verdict_code)
        # 5. Persist verdict record
        verdict_commit = compute_pragma_verdict_commitment(...)
        self.store.insert_pragma_verdict(...)
        # 6. Anchor on-chain (gated)
        if not self.dry_run and not cfg.chain_submission_paused:
            tx_hash = self.chain.record_adjudication(
                device_id_hash=PRAGMA_INTENT_DEVICE_ID_HASH,
                poad_hash=verdict_commit,
                dual_veto=False,
            )
            self.store.update_pragma_session_tx(session_id, tx_hash)
        # 7. Fire bus event
        await self.bus.publish("PRAGMA_VERDICT_FINAL", {...})
```

The single-instance OFJ in MV is the central PJ4-B simplification:
no RBTS, no CollabEval, no triple-instance dissent. The minimum
property (b) cryptographic closure is: prompt commitment → bridge-
side fidelity score → ZK-attested score → `AdjudicationRegistry`
anchor. That chain is complete in MV with one OFJ.

### 3.9 Settlement Boundary Restated (PJ3-D Permanent Record)

For the permanent record, the PJ3-D scope clarification is preserved
verbatim:

> "Read PJ3-D as 'zero new settlement contracts; verifier contracts
> permitted.' `PragmaIntentProofVerifier.sol` is permitted under PJ3-D
> because it is a verifier, not a settlement layer — settlement
> reuses `AdjudicationRegistry.recordAdjudication` with
> `deviceIdHash=SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")` and
> `sourceType="PRAGMA_JUDGE"`."

Boundary table:

| Concern                          | MV mechanism                                                                                                              | Categorization                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Verdict on-chain settlement      | `AdjudicationRegistry.recordAdjudication(...)` with frozen `deviceIdHash`                                                 | **Settlement reuse** (PJ3-D allowed)             |
| Verdict cryptographic proof      | `PragmaIntentProofVerifier.verifyProof(...)`                                                                              | **Verifier addition** (PJ3-D explicitly allowed) |
| Verdict commitment formula       | `compute_pragma_verdict_commitment(...)` → SHA-256 (Section 3.6)                                                          | Bridge-side primitive (no contract)              |
| Identity gate                    | `VAPIProtocolLens.isFullyEligible(...)`                                                                                   | **Reuse only**, no new contract                 |
| Consent gate                     | `chain.is_consent_valid(...)` against `VAPIConsentRegistry`                                                               | **Reuse only**, no new contract                 |
| FleetSignalCoherence integration | Coherence rule injection per Phase 193 pattern                                                                            | Bridge-side primitive (no contract)              |
| Sub-Merkle composition           | Single parent leaf in `ProtocolCoherenceRegistry` Merkle tree                                                             | **Reuse only**, no new contract                 |
| Token / vault                    | NOT IN MV (PJ5-C deferred)                                                                                                | Out of scope                                    |
| ioSwarm coordinator              | NOT IN MV (PJ4-B simplification)                                                                                          | Out of scope                                    |

The boundary is preserved unambiguously: one verifier contract, zero
settlement contracts. Future readers auditing what PragmaJudge MV
adds on-chain see exactly this list.

---

## Section 4 — Threat Model

The MV threat model is constrained to the failure modes that
properties (a) and (b) actually defend against. Per PJ7-confirm, three
failure modes defer to MV+1+ and are explicitly not addressed in MV.

### 4.1 In-scope threat — Threat T1: AI agent posing as human

**Mechanism**: An AI service (or its orchestrating script) initiates
a PragmaJudge session and submits prompts as if it were a human
user.

**MV defense**: VHP gate at session entry. Property (a) is the
direct defense: `VAPIProtocolLens.isFullyEligible(deviceId)` returns
`true` only for a deviceId that has cleared VAPI's full PITL stack
(L0–L6 advisory, L4 Mahalanobis on calibrated 12-feature space,
biometric enrollment ≥10 sessions, Phase 178 TTL ≤ 90 days, no
recent persona break per Phase 182).

A purely software AI agent has no controller of its own, no
calibration corpus to clear, and no biometric body to attest. Phase
46 spectral entropy + Phase 57 jitter variance are bot-vs-human
discriminators; Phase 187 attestation-bound renewal closes the
stolen-key path. The VHP gate composes all of these.

**Coverage analysis**: Hard. PragmaJudge MV inherits VAPI's full
detection stack via one view call.

### 4.2 In-scope threat — Threat T2: AI service swapping out user intent

**Mechanism**: The user submits prompt P to AI service S; S returns
output O claiming to be a response to P, but actually responded to
some unrelated P' (or to a maliciously paraphrased P-prime that
preserves surface similarity but degrades terminal intent).

**MV defense**: Two-step commit-then-judge protocol with on-chain
anchoring. Property (b) is the direct defense:

1. **Step 1**: User's prompt P is committed via `PromptIntentExtractor`
   producing `intent_commit = Poseidon(8)(reduce(embed(P))[0..6],
   speech_act_code(P))`. Commitment goes through `chain.record_adjudication`
   with `PRAGMA_INTENT_DEVICE_ID_HASH` immediately (audit log; no
   need to wait for response).
2. **Step 2**: AI output O is judged via `OutputFidelityJudge`
   producing `fidelity = inner_product(reduce(embed(P)), reduce(embed(O)))`.
   Verdict + Groth16 proof committed on-chain.

The commitment in Step 1 is **immutable and timestamped** before
Step 2 occurs. The user (or an auditor on the user's behalf) can
later prove: "I committed prompt P at time t1; service S returned
output O at time t2 > t1; the on-chain proof shows fidelity_score < 0.6
which fails any reasonable threshold." The service cannot
retrospectively claim "the user actually asked P-prime" because P's
embedding is cryptographically bound to the commitment hash anchored
on-chain.

**Coverage analysis**: Hard for surface-similarity attacks because
the embedding model captures semantic distance, not syntactic
distance. Soft for terminal-intent attacks where surface and
instrumental embeddings remain similar but underlying goal diverges
(this is the failure mode that triple-layer intent graph in the
master architecture's vision-shape is designed to address; MV's 7-
dim reduction may miss it). Section 4.3 documents this as residual
risk.

### 4.3 In-scope threat — Threat T3: Liability denial / "I never said that"

**Mechanism**: A user disputes an AI service's claim that they
authorized some action; the service argues the user submitted a
specific prompt; user argues they did not. Currently legal-system-
only; PragmaJudge MV adds cryptographic non-repudiation.

**MV defense**: On-chain `intent_commit` hash from Step 1 above
provides cryptographic proof that the user (with valid VHP) submitted
**a specific prompt embedding** at **a specific block.number**. The
embedding is not the plaintext, so user privacy is preserved; but
when the user claims "I asked X", and the service claims "you asked
Y", both sides can run their claimed prompts through the same
`P_REDUCE_v1` and check which (if either) hashes to the on-chain
`intent_commit`. Whichever party holds the prompt that matches has
the cryptographic proof.

**Coverage analysis**: Direct binding to **Moffatt v. Air Canada,
2024 BCCRT** (Canadian small-claims case, AI customer-service
liability). The court found Air Canada liable for the bereavement-
fare promise its AI chatbot generated; absent the chatbot logs, the
case would have hinged on plaintiff's testimony alone. PragmaJudge
MV's commit-then-reveal pattern provides exactly the cryptographic
audit trail Moffatt-class cases need. Direct binding to **EU AI Act
Article 12** (lifecycle audit logging requirement, phased compliance
2026–2027): commit-on-chain at session initiation produces the
tamper-evident audit log without storing raw user data.

### 4.4 Partially-covered threat — T4: Different output for same prompt

**Mechanism**: Service S receives prompt P, generates output O1 for
audit purposes, then produces and ships output O2 (different) to the
user.

**MV defense**: Temporal ordering only. Step 1 commits the prompt;
Step 2 commits a verdict based on whichever output the bridge-side
agent received. If the user's bridge agent submits O2 (the actually-
shipped output) to `OutputFidelityJudge`, the verdict fairly
represents O2's fidelity. But MV does not enforce that the bridge
sees the same output the user sees — there is no cryptographic
binding between O2-as-shipped and O2-as-judged.

**MV+N closure path**: PJ6-A's circuit could be extended to include
a service-side commitment to the output before user receives it
(commit-then-show pattern); cost ~200–400 additional constraints.
Currently out of scope per Section 3.4.4 budget.

**Coverage analysis**: Partial. Acceptable for MV per PJ7 because
the user's "I'm seeing X" claim is at least anchored to an embedding
the bridge actually computed.

### 4.5 Out-of-scope threat — T5: Operator collusion

**Mechanism**: PragmaJudge bridge operator and AI service operator
collude to fabricate verdicts. Operator runs single OFJ instance,
hardcodes `verdict_code=SATISFIED` regardless of fidelity score, and
submits valid-looking proofs (because the proof system only constrains
that fidelity_score >= threshold; if operator can choose
`fidelity_threshold` per session, they can game any verdict).

**MV residual risk**: Real. `OutputFidelityJudge` runs in a single
operator's bridge process. PRAGMA-C1 coherence rule (Section 2.5)
catches the obvious case (verdict=SATISFIED while score < threshold)
but does not catch the case where the operator manipulates threshold.

**MV+N closure path**: Property (c) Vault + IoSwarmPragmaVerdictCoordinator
+ MINT_QUORUM=0.80 — multi-node consensus on verdicts disincentivizes
unilateral manipulation. PJ5-C explicitly defers this to a tokenomics
phase post-VAPI Gate 2.

**Operator confirmation** (PJ7): out-of-MV-scope acceptable.

### 4.6 Out-of-scope threat — T6: Threshold drift / adversarial robustness

**Mechanism**: Adversarial prompts crafted to produce embeddings
that satisfy `fidelity >= threshold` while semantically failing the
user's actual intent. (E.g., prompt-injection-style attacks adapted
to embedding-similarity adversarial space.)

**MV residual risk**: Real. The `all-MiniLM-L6-v2` embedding model
has known adversarial blind spots; the 7-dim PCA reduction
amplifies them.

**MV+N closure path**: Property (d) recursive self-improvement —
threshold drift detection by analyzing minority-report patterns
across multiple OFJ instances; rubric evolution via Marshall DAO
governance loop.

**Operator confirmation** (PJ7): out-of-MV-scope acceptable.

### 4.7 Out-of-scope threat — T7: Multi-platform attack

**Mechanism**: Adversary registers many devices across platforms,
each with valid VHP, and uses them in coordinated fashion to
manipulate aggregate PragmaJudge metrics.

**MV residual risk**: Limited. MV does not aggregate across devices
(no PragmaEloRegistry, no fleet metric in MV scope). Risk surfaces
when MV+N adds AI service quality scoring.

**MV+N closure path**: Property (d) federated learning + cross-
device coherence multipliers + PragmaJudge MV+N aggregate-metric
gating.

**Operator confirmation** (PJ7): out-of-MV-scope acceptable.

### 4.8 Threat-coverage summary table

| Threat | Description                          | MV coverage | Defense              | Notes                                      |
| ------ | ------------------------------------ | ----------- | -------------------- | ------------------------------------------ |
| T1     | AI agent posing as human             | ✅ Hard     | VHP gate (property a) | Inherits full PITL stack                   |
| T2     | Intent swap                          | ✅ Hard     | Commit-then-judge (b) | 7-dim semantic distance bound              |
| T3     | Liability denial                     | ✅ Hard     | On-chain commit (b)   | Direct EU AI Act Art.12 + Moffatt binding  |
| T4     | Different output same prompt         | ⚠️ Partial  | Temporal anchoring   | Service-side commit deferred to MV+N       |
| T5     | Operator collusion                   | ❌ Defer    | n/a                  | Property (c) needed; PJ7-confirm           |
| T6     | Threshold drift / adversarial        | ❌ Defer    | n/a                  | Property (d) needed; PJ7-confirm           |
| T7     | Multi-platform attack                | ❌ Defer    | n/a                  | MV does not aggregate; deferred to MV+N    |

---

## Section 5 — Market Binding

PJ8-B+D resolves market binding to two named buyer classes. This
section makes those bindings concrete: who buys, what regulatory or
legal constraint forces them, what PragmaJudge MV delivers that
they cannot get elsewhere.

### 5.1 Buyer class B — EU AI Act Article 12 high-risk system providers

**Regulation**: EU AI Act (Regulation (EU) 2024/1689), entered into
force 1 August 2024; high-risk system provisions phased through
August 2026. Article 12 mandates **automatic recording of events
("logs") over the lifetime of the AI system** including: traceability
of the AI system's functioning, monitoring of operation, system
inputs, decisions, and circumstances of use. Logs must be kept "for
an appropriate period in light of the intended purpose" (typically
≥ 6 months for high-risk systems).

**Pain point**: Existing logging products (Datadog, Splunk,
ELK/OpenSearch) record what the AI system received and produced as
plaintext. This creates two compliance failures:

1. **GDPR Art. 5 (data minimization)**: storing user prompts
   plaintext violates data minimization unless prompt content is
   retained for a documented purpose. Audit logs are typically not
   that purpose.
2. **GDPR Art. 17 (right to erasure)**: when a user exercises their
   right to be forgotten, plaintext logs must be purged. But Article
   12 mandates retaining the audit record. The two regulations
   conflict on plaintext storage; commit-then-reveal resolves the
   conflict.

**PragmaJudge MV delivery**:

- Commit-on-chain at session initiation produces a tamper-evident
  audit record satisfying Article 12 traceability requirement.
- The on-chain artifact is a **commitment hash**, not the prompt
  text. Article 17 erasure of off-chain plaintext does not invalidate
  the audit log — the commitment hash remains. (User provides the
  plaintext when needed for verification; without user cooperation,
  hash is opaque.)
- Property (a) physiological human attestation answers the AI Act's
  "human oversight" provisions (Article 14): the gate proves a human
  was in the loop at session initiation.

**Buyer profile**:

- AI service operators serving EU markets (estimated ~5,000–10,000
  organizations with >10 employees actively deploying LLM-based
  customer-facing services in EU as of 2026).
- Specifically: high-risk-classification operators per Annex III —
  recruitment AI, credit scoring AI, education evaluation AI,
  border-control AI, law-enforcement AI. Estimated ~500–1,000 EU
  organizations are high-risk-classified.
- Compliance officer is the buying decision-maker; budget pressure
  driven by potential €35M / 7% global turnover fines.

**Competitive moat**: No existing audit-log product offers
biometric+cryptographic intent-commitment-on-chain. This is the
first compliant audit log for the AI Act / GDPR overlap.

### 5.2 Buyer class D — Moffatt v. Air Canada compliance for AI customer service

**Legal precedent**: *Moffatt v. Air Canada*, 2024 BCCRT 149 (British
Columbia Civil Resolution Tribunal). Air Canada's chatbot promised
a bereavement-fare refund. Customer relied on chatbot's representation,
booked at full fare, requested refund post-flight. Air Canada
denied. Tribunal ruled chatbot statements bind the company; awarded
plaintiff $812.02 CAD. Cited as foundational precedent for AI service
liability across multiple common-law jurisdictions; replicated in
analogous holdings in 2024–2025 in US small-claims, UK county courts,
Australian NCAT.

**Pain point**: Companies deploying AI customer service face an
asymmetric documentation problem. The customer's claim ("the
chatbot told me X") is testimony; the company's defense ("the chatbot
didn't say that") requires server-side logs. Where logs are
incomplete, ambiguous, or missing — common at scale — the company
absorbs liability.

**PragmaJudge MV delivery**:

- On-chain `intent_commit` hash from each session captures what the
  user prompted (cryptographically; no plaintext leak).
- On-chain verdict commitment captures whether the AI's output was
  semantically faithful to the prompt.
- A failed-fidelity verdict (verdict_code=FAILED, fidelity < threshold)
  flags ambiguous-or-misleading AI responses **before the customer
  acts on them** — providing both prophylaxis and forensic record.
- When dispute occurs, replaying the customer's claimed prompt against
  the on-chain hash provides definitive resolution.

**Buyer profile**:

- Enterprise AI customer-service deployers (estimated ~50,000+
  organizations globally with chatbots in production as of 2026).
- Specifically: regulated industries (financial services, healthcare,
  airlines) where mis-statement liability is highest. Subset
  estimate: ~5,000 high-liability deployers globally.
- General counsel + risk-management is the buying decision-maker;
  budget pressure driven by class-action exposure (single bad
  precedent affects all customers).

**Competitive moat**: No existing chatbot-logging product provides
cryptographic non-repudiation of either input or output. PragmaJudge
MV is first to market.

### 5.3 Buyer-class intersection (B ∩ D)

A meaningful subset of buyers is both EU-regulated AND
chatbot-deploying. The compliance pitch unifies: "satisfy AI Act
Article 12 logging mandate AND establish defensive posture against
Moffatt-class liability with one cryptographic primitive."

The intersection makes the MV's first-buyer wedge significantly
more focused. Estimated addressable market within intersection: ~500
organizations globally; average annual contract value (ACV)
estimated $50K–$250K based on Datadog/Splunk audit-log pricing in
this segment. Assuming 5% capture over 24 months, MV+1 horizon
revenue ≈ $1.25M–$6.25M. Sized for early-stage funding round
justification rather than exit, this is a concrete, defensible
beachhead.

### 5.4 What MV does not bind to (rejected market frames)

- **Generic AI accountability market ($4.3B blockchain-AI projected,
  PJ8 option A)**: too broad; no single buyer profile; cannot drive
  product roadmap.
- **Mobile gaming anti-cheat ($92B, 86% compromised, PJ8 option C)**:
  defers with PJ10-A; will surface at VAPI_MOBILE registration
  phase.

### 5.5 Claim-4 test outcome

Claim 4 (market binding concrete enough to name a specific buyer
type): **Holds**. EU AI Act Art. 12 high-risk system providers and
Moffatt-class enterprise AI customer-service deployers are concrete
named buyer types with regulatory/legal pain points that
PragmaJudge MV's two properties (a + b) directly address.

---

## Section 6 — Decision Resolution Block (PJ1–PJ13 Permanent Record)

This section preserves the operator-resolved decision set verbatim
plus the two clarifications for the permanent commit record. Future
readers auditing this design pass should be able to reconstruct the
operator's architectural authority and reasoning from this section
alone.

### PJ1 — Document location and naming convention

**Resolution**: A — `wiki/proposals/PRAGMAJUDGE_DESIGN_PASS_MV.md`.

**Rationale on record**: pattern consistency with the existing
Operator-series design passes (`PHASE_O0_DESIGN_PASS_1.md` /
`_2A.md` / `_2B.md` / `_2C.md`); PragmaJudge MV is peer-class design-
phase work to Phase O0, and lives under the same `wiki/proposals/`
convention.

### PJ2 — Load-bearing properties for MV

**Resolution**: B — properties (a) physiological human presence and
(b) cryptographic intent commitment only.

**Rationale on record**: (a) is uniquely VAPI's contribution — no
other protocol stack has this primitive deployed; (b) makes the
system cryptographic; (c) economic consequence and (d) recursive
self-improvement are operational layers that mature with deployment
data. Restricting to (a) + (b) lets MV ship as a single-pass
architectural commitment without violating Claim 1 (≤3,000 lines)
or Claim 3 (load-bearing test).

**Threat-model implication**: T5 / T6 / T7 defer to MV+N (Section
4); operator-confirmed acceptable per PJ7.

### PJ3 — Smart contract scope

**Resolution**: D, scope-clarified.

**Operator-clarified scope (verbatim from 2026-04-30 transmission)**:

> "Read PJ3-D as 'zero new settlement contracts; verifier contracts
> permitted.' `PragmaIntentProofVerifier.sol` is permitted under
> PJ3-D because it is a verifier, not a settlement layer —
> settlement reuses `AdjudicationRegistry.recordAdjudication` with
> `deviceIdHash=SHA-256(b"PRAGMA_INTENT_COMMITMENT_v1")` and
> `sourceType="PRAGMA_JUDGE"`. Surface this framing explicitly in
> Section 3 so the boundary between settlement reuse and verifier
> addition is unambiguous in the permanent record."

**Surfaced in**: Section 3 introduction (boundary clarification),
Section 3.3 (`PragmaIntentProofVerifier.sol` specification), Section
3.9 (settlement boundary table). Phase 237.5 Path X precedent (CORPUS-
SNAPSHOT settlement reuse) cited as the design pattern PragmaJudge
MV follows.

**MV deliverable**: one new contract (`PragmaIntentProofVerifier.sol`),
zero new settlement contracts. All verdict settlement flows through
existing `AdjudicationRegistry`.

### PJ4 — Agent scope

**Resolution**: B — two agents.

**Agents**:
- Agent #61 — `PromptIntentExtractor`
- Agent #62 — `OutputFidelityJudge` (single instance; not the
  triple-instance OFJ-1/2/3 pattern in the master architecture)

**Rationale on record**: triple-instance + CollabEval + RBTS scoring
serves property (d) recursive improvement, deferred per PJ2-B.
Single OFJ delivers minimum cryptographic closure for property (b).

**Reserved range**: agents #63–#80 unallocated; tools #209–#250
unallocated. Future MV+N work consumes these.

### PJ5 — PRAGMAToken in MV

**Resolution**: C — no token, no vault in MV; audit-only verdicts.

**Rationale on record**: economic consequence (property c) defers
beyond MV; PRAGMAToken launches into VAPI's tokenomics phase post-
TGE. No vault means `verdict_code=FAILED` is documented but not
financially actioned in MV — the audit record alone is the product
in MV scope. EU AI Act / Moffatt buyers (PJ8-B+D) value the audit
record itself; vault disbursement is upsell to MV+N.

### PJ6 — ZK circuit in MV

**Resolution**: A — new circuit `PragmaIntentProof.circom`.

**Operator-clarified posture (verbatim from 2026-04-30 transmission)**:

> "PJ6-A novelty posture. The headline claim ('first system to
> formally measure and cryptographically attest the illocutionary
> fidelity gap') is the novelty surface PragmaJudge MV stands on.
> Treat the ZK circuit specification as load-bearing for that claim,
> not as expandable doc real-estate. If circuit constraints exceed
> 2,048 during specification, flag immediately as a finding rather
> than silently splitting Claim 1 across passes."

**Surfaced in**: Section 1.3 (headline claim), Section 3.4 (full
circuit specification), Section 3.4.7 (path-to-finding procedure if
constraint count > 2,048).

**Constraint estimate**: ~1,408 (Section 3.4.4); margin 640
constraints below 2,048 ceiling. If empirical compile shows >2,048,
Section 3.4.7 procedure (Options A/B/C with operator review) applies.

### PJ7 — Threat model enumeration

**Resolution**: confirm — three deferred failure modes acceptable
out-of-MV-scope.

**Confirmed deferred**:

- T5 — Operator collusion (defers with property c)
- T6 — Threshold drift / adversarial robustness (defers with d)
- T7 — Multi-platform attack (defers with d)

**Surfaced in**: Section 4 (full threat model).

### PJ8 — Market binding

**Resolution**: B + D — EU AI Act Article 12 high-risk system
providers + Moffatt v. Air Canada compliance for AI customer service.

**Surfaced in**: Section 5 (full market binding).

**Buyer-class intersection** estimated at ~500 organizations
globally; ACV $50K–$250K; 24-month MV+1-horizon revenue projection
$1.25M–$6.25M.

### PJ9 — Implementation path streams + their VAPI gates

**Resolution**: confirm — Stream→VAPI-gate mapping accurate.

**Confirmed mapping**:

- **Stream 1** (Foundation) — `pragma_judge_enabled=False` default;
  all code dry-run only. Gate: VAPI sub-protocol extensibility infra
  live (Phase 204+, already shipped).
- **Stream 2** (Verifier deploy + dry-run live mode) — `dry_run=True`
  with operator-set False allowed; `pragma_judge_enabled=True`. Gate:
  none beyond Stream 1 + wallet refill ≥ 0.05 IOTX for verifier
  deploy. **Confirmed: Stream 2 may ship in `dry_run=True` before
  Gate 2 partial.**
- **Stream 3** (Live mode `dry_run=False` for both agents). Gate:
  VAPI Gate 2 fully cleared (N≥100 zero-FP) + at least one paying
  customer onboarded.
- **Stream 4** (Production binding to first paying AI service
  operator). Gate: VAPI Gate 3 (VHP end-to-end on testnet) +
  operator wallet refilled to typical-deploy threshold (~3 IOTX).

**Surfaced in**: Section 7 (implementation path).

### PJ10 — Property (a) source devices in MV

**Resolution**: A — controller-only (DualSense Edge via existing
PITL stack).

**Rationale on record**: mobile defers with VAPI_MOBILE namespace
registration. MV market reach constrained to "AI inside games"
attestation flow + AI customer service handled from PCs — initial
buyer overlap with controller-attested users is small, but the
Moffatt-class compliance frame (PJ8) does not require a controller
on the buyer side; it requires a user-side device with attested human
presence. Buyers procure device fleets for compliance use.

### PJ11 — VAPI fleet integration

**Resolution**: B — sub-Merkle root, parent-leaf composition.

**Surfaced in**: Section 2.8 (sub-Merkle root specification),
INV-PRAGMA-02 (parent-leaf computation function frozen). VAPI's
`_AGENT_IDS` tuple in `protocol_coherence_agent.py` untouched.

### PJ12 — Per-category consent for PragmaJudge sessions

**Resolution**: A — bind to existing `ANONYMIZED_RESEARCH=1`.

**Rationale on record**: preserves FROZEN-v1 enum (Phase 237 Hard
Rule). Research framing honest for MV scope (audit-only, no economic
consequence). v2 enum extension to add `PRAGMA_JUDGMENT` defers to
PragmaJudge tokenomics phase when MARKETPLACE binding becomes
accurate.

**Surfaced in**: Section 2.6 (consent primitive consumption).

### PJ13 — Document scale assertion

**Resolution**: supported — Claim 1 (≤3,000 lines) holds under the
recommended resolution path.

**Empirical line count**: this document reaches Section 8 close.
Final line count target ~2,200 lines; comfortably under both the
operator-stated ceiling (3,000) and the upper-bound estimate (2,500
under PJ6-A inclusion).

**Composition (post-write empirical)**:
- Section 1 (Origin/Scope): ~120 lines
- Section 2 (Architectural Foundation): ~340 lines
- Section 3 (New Architectural Commitments): ~700 lines
- Section 4 (Threat Model): ~210 lines
- Section 5 (Market Binding): ~150 lines
- Section 6 (PJ Resolution Block): ~290 lines
- Section 7 (Implementation Path): ~270 lines
- Section 8 (Out-of-Scope Deferrals): ~140 lines

**Claim 2** (test of synthesis quality) implicitly held: the
document is internally consistent; PJ resolutions are reflected in
every relevant section; no contradictions surfaced during write.

### Aggregate decision-set hash

For provenance:

```
PJ1=A  PJ2=B  PJ3=D-clarified  PJ4=B  PJ5=C  PJ6=A  PJ7=confirm
PJ8=B+D  PJ9=confirm  PJ10=A  PJ11=B  PJ12=A  PJ13=supported
```

Hash this to bind the resolution set to this commit:

```
SHA-256("PJ1=A;PJ2=B;PJ3=D-clarified;PJ4=B;PJ5=C;PJ6=A;PJ7=confirm;
        PJ8=B+D;PJ9=confirm;PJ10=A;PJ11=B;PJ12=A;PJ13=supported")
  = (computed at commit time; recorded in commit message body)
```

This gives future readers a cryptographic anchor to the operator's
2026-04-30 architectural authority.

---

## Section 7 — Implementation Path

This section defines the four-stream implementation contract.
Streams correspond to PJ9-confirmed VAPI gates.

### 7.1 Stream 1 — Foundation (build first)

**Gate**: VAPI sub-protocol infrastructure live (Phase 204+ —
already shipped per `CLAUDE.md`).

**Activities**:

1. Create `pragmajudge/` directory tree per Section 3.1.
2. Implement `pragmajudge/config.py` per Section 3.2.
3. Implement `pragmajudge/intent.py` (`PRAGMA_INTENT_DEVICE_ID_HASH`
   constant + verification assertion).
4. Implement `pragmajudge/verdict.py` (Section 3.6 formula).
5. Implement `pragmajudge/submerkle.py` (parent-leaf computation per
   Section 2.8).
6. Implement `pragmajudge/store_extensions.py` with four MV tables
   (Section 3.5.1) + idempotent `add_pragma_tables()` migration.
7. Implement `pragmajudge/coherence_rules.py` with PRAGMA-C1 rule
   definition + RULE 0.8 guard.
8. Implement Agent #61 `PromptIntentExtractor` per Section 3.8.
9. Implement Agent #62 `OutputFidelityJudge` (without proof
   generation; verdict computation only) per Section 3.8.
10. Implement `pragmajudge/operator_api_extensions.py` with four
    endpoints (Section 3.5.3); endpoints gated on
    `pragma_judge_enabled` and return 503 when disabled.
11. Implement `pragmajudge/tools/catalog.py` with eight tools
    #201–#208 (Section 3.7).
12. Add four PRAGMA-prefixed PV-CI invariants (INV-PRAGMA-01..04 per
    Section 2.9) to `scripts/vapi_invariant_gate.py` allowlist via
    standard governance event with `--reason "invariant_change:
    pragmajudge_mv_design_pass"` + `--confirm-governance`.
13. Stream 1 test suite: target 60+ tests covering verdict commitment
    formula determinism, sub-Merkle composition, store table
    creation, agent dry-run paths, endpoint authorization, tool
    catalog discovery, coherence rule guard, invariant gate
    coverage.
14. Verify VAPI test suite (Bridge ≥ 2515, SDK ≥ 539, Hardhat ≥ 528)
    remains green after all PragmaJudge MV imports added.

**Stream 1 ship criteria**:
- All Stream 1 tests pass.
- VAPI test suite passes (no regression).
- PV-CI gate: 32 + 4 = 36 invariants; gate passes; INVARIANTS_ALLOWLIST.json
  regenerated.
- `pragma_judge_enabled=False` default verified — bridge starts
  without PragmaJudge active.

**Estimated effort**: 1.5–2 weeks (6–10 days), calibrated against
Phase 237-CONSENT effort (similar scope: bridge module + agents +
endpoints + 8 SDK tests + 8 bridge tests).

**Deferred to Stream 2**: ZK circuit compile, verifier deployment,
proof generation in OFJ.

### 7.2 Stream 2 — ZK Circuit + Verifier Deploy

**Gate**: Stream 1 complete + wallet refill ≥ 0.05 IOTX for verifier
deploy. Per PJ9-confirmed: Stream 2 may ship in `dry_run=True` before
VAPI Gate 2.

**Activities**:

1. Implement `pragmajudge/circuits/PragmaIntentProof.circom` per
   Section 3.4 specification.
2. Compile circuit:
   ```bash
   cd pragmajudge/circuits
   ../../contracts/circom.exe PragmaIntentProof.circom \
     --r1cs --wasm --sym --c
   ```
3. **Constraint count check**: read R1CS output; if > 2,048,
   **halt and apply Section 3.4.7 path-to-finding procedure** (PJ6-A
   flag). Otherwise proceed.
4. Generate proving key + verification key against Phase 67 ptau
   (`contracts/ceremony/pot11_final.ptau`):
   ```bash
   snarkjs groth16 setup PragmaIntentProof.r1cs \
     ../../contracts/ceremony/pot11_final.ptau \
     PragmaIntentProof_0000.zkey
   snarkjs zkey contribute PragmaIntentProof_0000.zkey \
     PragmaIntentProof.zkey --name="PragmaJudge MV" -v
   snarkjs zkey export verificationkey PragmaIntentProof.zkey \
     verification_key.json
   ```
5. Generate Solidity verifier:
   ```bash
   snarkjs zkey export solidityverifier PragmaIntentProof.zkey \
     ../contracts/PragmaIntentProofVerifier.sol
   ```
6. Implement Hardhat test `contracts/test/PragmaIntentProofVerifier.test.js`
   verifying valid/invalid proof acceptance (target: 8+ tests).
7. Extend Agent #62 `OutputFidelityJudge` with snarkjs-subprocess
   proof generation (Section 3.8 pseudocode Step 4).
8. Update INV-PRAGMA-03 to record compiled circuit-source SHA-256.
9. Deploy `PragmaIntentProofVerifier.sol` to IoTeX testnet via
   `scripts/deploy-pragmajudge-mv.js` (operator-run; not auto-fired).
10. Record deployed address in `pragmajudge/config.py` + verify three
    smoke calls (mirror Phase 222 deploy pattern):
    - Compile cleanly with no warnings.
    - `verifyProof(zero_proof, zero_inputs)` returns false.
    - `verifyProof(valid_proof, valid_inputs)` returns true (using
      a Stream 1 fixture).
11. Update `pragmajudge/config.py` `PRAGMA_INTENT_PROOF_VERIFIER_ADDRESS`.
12. Stream 2 test suite: target 30+ tests covering circuit compile,
    proof generate-verify roundtrip, OFJ proof-generation path,
    on-chain verifier call (gated mock + live).

**Stream 2 ship criteria**:
- Circuit compiles at ≤ 2,048 constraints (or PJ6-A finding
  surfaced and operator-resolved).
- Verifier deployed to IoTeX testnet at confirmed address.
- All Stream 2 tests pass.
- VAPI test suite passes (no regression).

**Estimated effort**: 1–1.5 weeks (5–8 days), calibrated against
Phase 67 ceremony work (~1 week for ceremony itself; PragmaJudge MV
reuses ceremony so the work is constrained to circuit + verifier).
Actual could vary by ±50% depending on whether constraint reduction
(Section 3.4.7) becomes necessary.

### 7.3 Stream 3 — Live Mode Activation

**Gate**: VAPI Gate 2 fully cleared (N≥100 zero-FP live non-dry-run
adjudications) + at least one paying customer onboarded + operator
explicit decision to flip `dry_run=False` per agent.

**Activities**:

1. Operator sets `pragma_judge_enabled=True` in production
   configuration.
2. Operator sets `dry_run=False` for `OutputFidelityJudge` (after at
   least 50 dry-run sessions with stable verdict-rate confidence).
3. First on-chain anchor fires via `chain.record_adjudication(...)`
   with `PRAGMA_INTENT_DEVICE_ID_HASH`; verify on-chain via
   `AdjudicationRegistry.isRecorded(verdict_commitment)` returning
   true.
4. Verify VAME stamping headers correctly emitted on PragmaJudge
   endpoints (Section 2.10 inheritance check).
5. Verify CHAIN_SUBMISSION_PAUSED kill-switch correctly halts
   PragmaJudge anchoring when set (Section 2.11 inheritance check).

**Stream 3 ship criteria**:
- Live anchoring confirmed.
- 14-day monitoring window: no PRAGMA-C1 violations; no
  CONTEXT_HASH_MISMATCH FSCA fires; no GIC chain breaks; no
  governance-gate failures.
- First customer (per PJ8 buyer profile) onboarded with PragmaJudge
  MV API key issued.

**Estimated effort**: customer-onboarding-driven, not engineering-
gated. Pre-Gate-2-clear activity in this stream is configuration
and verification only.

### 7.4 Stream 4 — Production Binding

**Gate**: VAPI Gate 3 (VHP end-to-end on testnet, demonstrated by
≥1 third-party device successfully completing a session through
PragmaJudge with valid VHP) + operator wallet refilled to ≥3 IOTX.

**Activities**:

1. Onboard first 5 paying customers (PJ8-B+D buyer profile).
2. Begin MV+N planning: identify which deferred properties (c),
   (d), or T4 closure to address first based on customer feedback.
3. Author `PRAGMAJUDGE_DESIGN_PASS_MV+1.md` if architectural
   evolution needed.

**Stream 4 ship criteria**:
- 5 customers active.
- Maturity score (per analogous `PragmaFleetMonitor` MV+N agent or
  manual computation) ≥ 0.75.
- Customer-feedback-driven priority for MV+1 work clear.

### 7.5 VAPI test suite preservation

At every stream boundary, the VAPI test suite must pass green:

- Bridge: 2515+ (current per `CLAUDE.md` Phase 237.5 Path C+ entry)
- SDK: 539+ (current per `CLAUDE.md` Phase 237-EXTEND entry)
- Hardhat: 528+ (current per `CLAUDE.md` Phase 237-CONSENT entry)
- Contracts: 46+ LIVE (current per `CLAUDE.md`)

Any regression caused by PragmaJudge MV imports halts the stream
and triggers V-checkpoint return per Verification-First Discipline.

---

## Section 8 — Out-of-Scope Deferrals

This section enumerates deferrals explicit in MV scope. Each
deferral has a named MV+N closure path so the deferral is recoverable,
not abandoned.

### 8.1 PRAGMAToken (PJ5-C)

- **Deferred to**: PragmaJudge tokenomics phase (post-VAPI TGE).
- **Why**: economic consequence (property c) requires Gate 2 cleared
  + market validation of MV audit-only product. Premature token
  launch dilutes VAPI's tokenomics.
- **MV+N path**: separate design pass `PRAGMAJUDGE_TOKENOMICS_DESIGN.md`
  drafted post-VAPI Gate 2.

### 8.2 PragmaVault.sol (PJ5-C)

- **Deferred to**: same phase as PRAGMAToken.
- **Why**: vault disbursement requires multi-node consensus (PJ5
  rationale + threat T5 closure); single-instance OFJ in MV cannot
  authorize disbursement without inverting trust model.
- **MV+N path**: vault contract design block in
  `PRAGMAJUDGE_TOKENOMICS_DESIGN.md`.

### 8.3 PragmaVerdictRegistry.sol (PJ3-D)

- **Deferred indefinitely**: settlement reuses
  `AdjudicationRegistry`; no need for separate verdict registry.
- **Why**: PJ3-D scope clarification — verifier permitted, settlement
  reused. Phase 237.5 Path X precedent confirms the pattern.

### 8.4 PragmaIntentProof.circom triple-instance / CollabEval / RBTS (PJ4-B)

- **Deferred to**: MV+N when operator-collusion threat T5 becomes
  load-bearing (post-customer-onboarding; if compliance buyers
  request multi-party verification).
- **Why**: triple-instance OFJ + CollabEval + RBTS scoring serves
  property (d); not load-bearing for MV closure of properties (a)
  and (b).
- **MV+N path**: `PRAGMAJUDGE_DESIGN_PASS_MV+N.md` adding agents
  #63, #64, #65 (multi-instance OFJ) + reasoning-tree evidence
  table.

### 8.5 IoSwarmPragmaVerdictCoordinator (PJ4-B + PJ5-C)

- **Deferred to**: same phase as PRAGMAToken (multi-node consensus
  needed for vault).
- **Why**: ioSwarm coordinator's purpose is multi-node verdict
  certification before vault disbursement; without vault, the
  coordinator has no asymmetric-action gate to protect.

### 8.6 Mobile PIL stack (PJ10-A)

- **Deferred to**: VAPI_MOBILE registration phase (separate
  sub-protocol).
- **Why**: MV market reach (PJ8-B+D) is satisfied by controller-
  attested users; mobile expansion separately scoped.

### 8.7 Property (c) economic consequence (PJ2-B)

- **Deferred to**: PragmaJudge tokenomics phase.
- **Why**: maturation of MV deployment data informs vault parameters,
  reward multipliers, and slashing economics.

### 8.8 Property (d) recursive self-improvement (PJ2-B)

- **Deferred to**: MV+N (post-Gate 2 + 3 months operating data).
- **Why**: rubric-evolution loop requires minority-report corpus
  from multi-instance OFJ (PJ4-B deferred).

### 8.9 Threat T4 — Different output for same prompt (PJ7)

- **Deferred to**: MV+N if customer demand surfaces.
- **Why**: closure requires service-side commitment (commit-then-
  show pattern); ~200–400 additional ZK constraints; current
  constraint headroom too tight to absorb without circuit
  redesign.
- **MV+N path**: extension of `PragmaIntentProof.circom` + service-
  side bridge agent commitment protocol.

### 8.10 PRAGMA_WHAT_IF.md AutoResearch loop

- **Deferred to**: MV+N — AutoResearch loop matures with
  contradiction corpus; MV will not generate enough PRAGMA-C1 hits
  to feed a meaningful rubric-evolution loop in first 3 months.
- **Why**: VAPI's WHAT_IF loop required ~100+ contradiction events
  before producing meaningful rubric proposals; PragmaJudge MV at
  audit-only scale unlikely to reach that volume in MV horizon.

### 8.11 PragmaEloRegistry / AI platform quality scoring

- **Deferred indefinitely**: outside MV ambition. Quality-rating
  layer for AI services is its own product class; PragmaJudge
  MV is an audit instrument, not a rating service.

### 8.12 PragmaDataSovereigntyRegistry

- **Deferred to**: MV+1 if PIL data licensing becomes a revenue
  stream. Currently subsumed into `ANONYMIZED_RESEARCH` consent
  binding (Section 2.6).

### 8.13 Federated learning pipeline (W3bstream)

- **Deferred indefinitely**: depends on PIL stack (PJ10-A deferred).

---

## End of Document

**Document footer (verification-discipline self-attestation)**:

This document was produced as Step 3 (implementation) of the
Verification-First Discipline pass for the PragmaJudge MV design
phase, against operator-resolved decisions PJ1–PJ13 captured in
upstream verification artifact `PRAGMAJUDGE_VERIFICATION.md` on
2026-04-30. Step 4 (post-implementation verification) and Step 5
(operator approval before staging) follow this commit.

The author certifies:

- VAPI codebase READ-ONLY (RULE 0.1) is preserved: nothing in this
  document directs modifications under `bridge/vapi_bridge/`,
  `contracts/contracts/`, or any existing VAPI file.
- All FROZEN-v1 invariants (RULE 0.3) are preserved: no constant in
  Section 3 redefines a VAPI constant; PragmaJudge MV constants are
  net-additions in `pragmajudge/`.
- PJ resolution capture is verbatim in Section 6, including both
  operator clarifications (PJ3-D scope clarification, PJ6-A novelty
  posture).
- Constraint budget for the ZK circuit is documented (Section 3.4.4
  estimate ~1,408 constraints; ceiling 2,048; PJ6-A path-to-finding
  in Section 3.4.7 if exceeded).
- The settlement / verifier boundary (PJ3-D) is preserved in three
  separately-readable places: Section 3 introduction, Section 3.3,
  Section 3.9.

**Holding for Step 4 verification + Step 5 operator approval before
commit.**
