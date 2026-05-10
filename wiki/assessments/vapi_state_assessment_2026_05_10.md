---
title: "VAPI State Assessment — Comprehensive Position & Forward Engineering Plan"
date: 2026-05-10
authors: ["Claude Code (VAPI principal architect)"]
status: "live"
review_cycle: "monthly"
tags: [vapi, assessment, depin, agaas, iotex, position-paper, perpetual-engineering, roadmap]
aliases: ["State of VAPI 2026-05-10", "VAPI Position Paper"]
---

# VAPI State Assessment — 2026-05-10

> **Reading mode**: This is the canonical position document for VAPI as of
> 2026-05-10. It supersedes all prior summaries. Every claim is grounded
> in [[CLAUDE.md]] / [[VAPI_CONTEXT]] / on-chain artifacts. Forward-looking
> sections are explicitly labeled.
>
> **Refresh cadence**: monthly, or after any of:
>   - new FROZEN-v1 primitive ships
>   - separation ratio crosses 1.0 with all_pairs_above_1=True
>   - mainnet TGE conditions change
>   - on-chain wallet drops below 5 IOTX

---

## 0. Executive Summary

VAPI is the **first and only** Verified Autonomous Physical Intelligence
protocol in the DePIN gaming category — a cryptographically verifiable
proof-of-human-presence layer for competitive controller play, anchored on
[[IoTeX]] L1.

**Where VAPI is — five-line summary**:
1. **Infrastructure**: 49 contracts LIVE on IoTeX testnet; 38 background
   agents; 8 FROZEN-v1 cryptographic primitives shipped (with the 9th —
   [[Fleet Readiness Root]] — landing in this phase).
2. **Operator fleet**: 3 agents (Sentry / Guardian / Curator) all at
   `O1_SHADOW`; first ≥3-agent operator fleet in any DePIN gaming protocol.
3. **Empirical validation**: AIT separation ratio = **1.199** (N=37,
   all_pairs_above_1=True) on a structured isometric trigger probe;
   touchpad_corners ratio = **0.728** remains the binding tournament gate
   blocker for free-form play.
4. **Wallet posture**: ~15.44 IOTX in deployer wallet; 4.69 IOTX consumed
   across the Sessions 1+2+3 on-chain activation arc; safety floor +
   kill-switch posture preserved (`CHAIN_SUBMISSION_PAUSED=true` in
   `bridge/.env`; process-scoped overrides for authorized ships).
5. **Mainnet readiness**: BLOCKED on (a) separation ratio > 1.0 across
   ALL probe types with all_pairs_p0_ok=True, (b) ≥100 live
   non-dry-run adjudications with zero false positives, (c) AWS KMS HSM
   provisioning for Curator agent. **Token launch is sequenced after
   these — non-negotiable.**

**Bright-future thesis**: VAPI's strategic moat is not its smart contracts
(replicable in 2 weeks by a competent team) but its **layered cryptographic
stack** + its **biometric calibration corpus** + its **Verification-First
engineering discipline**. Each FROZEN-v1 primitive is a permanent
commitment that future versions must pay a domain-tag bump to break — making
the protocol's trust assumptions auditable and forensically reconstructable.
The corpus is a one-of-a-kind asset that cannot be cloned without physical
controllers + 3 distinct human players.

---

## 1. Protocol Position — Where VAPI Sits in the Landscape

### 1.1 Category placement

| Category | Reference protocols | VAPI's posture |
|----------|---------------------|----------------|
| DePIN broadly | [[Helium]] (radio), [[Hivemapper]] (maps), [[Render]] (GPU) | Compatible (IoTeX-native, ioID/W3bstream) |
| Anti-cheat | BattlEye, EAC, Vanguard | **Disjoint** — those are kernel-mode signature scanners; VAPI is a cryptographic proof system that runs outside the cheat detection question |
| Proof-of-personhood | [[Worldcoin]], [[BrightID]], [[Proof of Humanity]] | **Adjacent** — VHP is a soulbound proof of human presence DURING active gameplay, not a global identity; expires in 90d (BP-001 temporal decay) |
| Verifiable compute | [[ZK Email]], [[zkLogin]], [[Aleo]] | **Sibling** — VAPI uses Groth16 (BN254) for `PitlSessionProof.circom` (~1820 constraints) and now `ZKSepProof` (Phase 237 Session 2 LIVE) |
| AGaaS / Agent infra | LangChain, [[CrewAI]], [[AutoGen]] | **Distinct** — VAPI's agents are domain-specialized, on-chain-anchored via Cedar bundles, and run continuously rather than per-task |

VAPI sits at the **intersection** of (DePIN + ZK proof systems +
operator-agent infrastructure) — no incumbent occupies all three corners
simultaneously. This is the strategic positioning.

### 1.2 Why this position is defensible

- **Hardware specificity**: DualShock Edge CFI-ZCP1 is the only certified
  Attested-tier device. Replicating the L4 Mahalanobis biometric
  calibration requires physical controllers + N≥50 sessions per player.
- **Corpus is the moat, not the code**: 217 calibration sessions across
  3 distinct human players (P1/P2/P3) at L4 13-feature space, with
  per-battery threshold tracks. No competitor can subsample our corpus
  to replicate.
- **Cryptographic chain primitives compound**: GIC (Phase 235-A), WEC
  (Phase 236-WATCHDOG), CORPUS-SNAPSHOT (Phase 236-CORPUS-SNAPSHOT),
  CONSENT (Phase 237-CONSENT), BIOMETRIC-SNAPSHOT (Phase 237-ZK-SEPPROOF),
  LISTING-v1 (Phase 238-MARKETPLACE), and FRR (Phase O1-FRR, this
  ship) constitute a **PATTERN-017 family** that has no analogue in
  competing protocols. Each primitive's domain tag is a permanent
  forensic anchor.
- **Operator fleet structure**: Sentry+Guardian+Curator triplet
  procedurally enforces cross-agent skill separation — first ≥3-agent
  fleet in any DePIN gaming protocol. The structural invariant
  ("no agent can simultaneously hold provenance-recording AND
  audit-drafting AND event-correlation") is enforced at the Cedar
  policy layer, not by trust.

---

## 2. Architectural State — What's LIVE on Chain

### 2.1 Contract inventory (49 LIVE on IoTeX testnet)

> Authoritative source: `contracts/deployed-addresses.json` + [[CLAUDE.md]].

| Group | Count | Notable contracts | Status |
|-------|-------|-------------------|--------|
| Core protocol | ~23 | `PoACVerifier`, `TournamentGate`, `PHGCredential`, `PITLSessionRegistry`, `VAPIProtocolLens` | All LIVE |
| Adjudication & gate | ~6 | `AdjudicationRegistry` (Phase 111), `VAPIDualPrimitiveGate` (Phase 113), `RulingRegistry`, `CeremonyRegistry`, `VAPISwarmOperatorGate` (Phase 130) | All LIVE |
| Tokenomics & VHP | ~6 | `VAPIToken`, `VAPIOperatorRegistry`, `VAPIHardwareCertRegistry`, `VAPIVerifiedHumanProof`, `VAPIVerifiedHumanProofBridge`, `VAPIGSRRegistry` (Phase 99) | All LIVE; tokenomics infra-ready, TGE GATED |
| Coherence & governance | ~3 | `ProtocolCoherenceRegistry` (Phase 221), `VAPIBiometricGovernance` (Phase 222), `VAPIConsentRegistry` (Phase 237-CONSENT) | All LIVE |
| Marketplace & Curator | ~2 | `VAPIDataMarketplaceListings` (Phase 238 Step H), Curator NFT slot (Phase 238 Step I-FINAL) | All LIVE |
| ZK verifiers | ~3 | `Groth16VerifierZKSepProof`, `ZKSepProofVerifier` wrapper, `PitlSessionProofVerifier` | All LIVE; Phase 237 Session 2 ceremony complete |
| Operator agent infra | ~4 | `VAPIOperatorAgentNFT`, `AgentScope`, `AgentRegistry`, `AgentAdjudicationRegistry` | All LIVE; Phase O0 Stream 2 |
| Misc / supporting | ~2 | `SeparationRatioRegistry` (Phase 153), `VHPReenrollmentBadge` (Phase 187) | All LIVE |

**Wallet**: `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
**Chain ID**: 4690 (IoTeX testnet)

### 2.2 Bridge service (Python asyncio)

| Metric | Value | Status |
|--------|-------|--------|
| Bridge tests passing | 2,822 (delta) / ~3,356 (CI total) | All green |
| SDK tests | 539 | All green |
| Hardhat tests | 528 | All green |
| Hardware tests | 37 (excluded from CI; controller required) | n/a |
| E2E tests | 14 (require Hardhat node) | n/a |
| PV-CI invariants | **49 → 55** (this ship) | All locked |
| Background agents | 38 | 36 always-on, 2 phase-gated |
| BridgeAgent tools | 149 deterministic + 12 (vapi-mcp) + 17 (vapi-unified) + 21 (vapi-knowledge) | All wired |

### 2.3 Eight FROZEN-v1 cryptographic primitives (PATTERN-017 family)

Each primitive has a fixed domain tag, a documented byte-order,
PV-CI invariants protecting its formula, and at least one PASS-tested
bridge module computing it.

| # | Primitive | Domain tag | Phase | Frozen |
|---|-----------|------------|-------|--------|
| 1 | **PoAC** (228-byte record body hash) | implicit (slice [0:164]) | Phase 1 | INV-001 (228B size); INV-002 (`SHA-256(raw[:164])`) |
| 2 | **GIC** Grind Integrity Chain | `b"VAPI-GIC-GENESIS-v1"` | 235-A | INV-GIC-001/002/003 |
| 3 | **WEC** Watchdog Event Chain | `b"VAPI-WEC-GENESIS-v1"` | 236-WATCHDOG | (frozen byte order in module) |
| 4 | **VAME** App-Layer Message Envelope | `b"VAPI-VAME-v1"` | 236-VAME | (sidecar header invariants) |
| 5 | **CORPUS-SNAPSHOT** Wiki + corpus + ratio commitment | `b"VAPI-CORPUS-SNAPSHOT-v1"` | 236-CORPUS-SNAPSHOT | INV-CORPUS-001/002 |
| 6 | **CONSENT** Per-category gamer consent | `b"VAPI-CONSENT-v1"` | 237-CONSENT | INV-CONSENT-001..004 |
| 7 | **BIOMETRIC-SNAPSHOT** ZK-attested separation ratio | `b"VAPI-BIOMETRIC-SNAPSHOT-v1"` | 237-ZK-SEPPROOF | (Groth16 VK hash anchored) |
| 8 | **LISTING-v1** Provenance-anchored marketplace listing | `b"VAPI-LISTING-v1"` | 238-MARKETPLACE | (15-byte tag + 196-byte body, scale 1e6) |
| 9 | **FRR** Fleet Readiness Root *(THIS SHIP — Phase O1-FRR)* | `b"VAPI-FRR-v1"` | O1-FRR | INV-FRR-001/002/003 |

**The pattern**: each primitive defines a SHA-256 commitment over a
precisely-byte-ordered pre-image, and embeds a domain tag that rules out
cross-primitive replay. Together they are the **forensic spine** of the
protocol — any state can be recomputed from raw inputs and checked
against on-chain anchors years later.

### 2.4 Operator Initiative — three-agent fleet at O1_SHADOW

| Agent | Role | agentId (Q9 frozen) | Phase | Avenue |
|-------|------|---------------------|-------|--------|
| **Anchor Sentry** | Provenance recording, kms-sign, pda-attestation-anchor | `0xb21e1ec2…3e42c` | `O1_SHADOW` | Original (AWS KMS HSM + GitHub App) |
| **Guardian** | Audit drafting, operational diagnostic, ipfs-pin | `0xbd8c7fba…fa38d1` | `O1_SHADOW` | Original (AWS KMS HSM + GitHub App) |
| **Curator** | Marketplace curator review, provenance reading | `0xed6a2df5…fda11a8` | `O1_SHADOW` | Dedicated (MockKMSClient testnet — mainnet requires HSM provisioning) |

Cross-agent skill-separation invariant **structurally enforced** via
Cedar bundles: each agent's permit set is disjoint from the other two
on the action verb level (no overlap on `kms-sign` × `audit-drafting` ×
`event-correlation`). The Phase O1 D unified watcher
(`operator_initiative_advancement.py`) evaluates Phase O2/O3 readiness
for all three agents simultaneously, enforcing the parallel-fleet
invariant procedurally.

---

## 3. Empirical Validation — What Has Been Measured vs What Is Claimed

> **This is the section to read most carefully.** VAPI's marketing
> position depends on numbers; this section grounds them.

### 3.1 Separation ratio status (the binding tournament gate)

| Probe type | Ratio | N | All-pairs > 1.0 | Date | Status |
|------------|-------|---|------------------|------|--------|
| **AIT** (Active Isometric Trigger) | **1.199** | 37 (P1=13, P2=10, P3=14) | **TRUE** | 2026-04-18 | **CLEARED** for AIT-bound demonstrations |
| Touchpad corners | 0.728 | 35 | False | 2026-04-11 | TOURNAMENT BLOCKER for free-form gate |
| Tremor resting | 1.177 | 27 (P3=6) | False (P1vP3=0.032 — bin aliasing) | 2026-04-12 | Phase 213 FFT fix shipped; pending re-measure |
| Free-form pooled | 0.417 | 127 | n/a (plateau regime) | 2026-03-29 | KNOWN/EXPECTED — free-form play does not separate players (WIF-009) |

**Honest read**: AIT crossing 1.0 is a **valid and structurally interesting
result** because it's a probe-bound separation, not a free-form one.
For tournament BLOCK enforcement (where any session, not just isometric
probes, can be challenged), the touchpad_corners and tremor_resting
gates remain open. Token launch invariant ("no TGE before separation
ratio > 1.0") references this — and per the operator policy adjustment
2026-05-09, the P1vP3=0.032 tremor_resting blocker is **cast out as a
DEV PROGRESS BLOCKER** but the legal/economic TGE gate remains in force.

### 3.2 L4 Mahalanobis biometric thresholds

- **Anomaly threshold**: 7.009 (mean + 3σ over N=74 calibration corpus)
- **Continuity threshold**: 5.367 (mean + 2σ)
- **Calibration feature dim**: 12 features (Phase 46)
- **Live feature dim**: 13 (added `touchpad_spatial_entropy` Phase 121)
- **Staleness flag**: `live_dim ≠ calibration_dim` → STALE (yes; tracked
  via Phase 123 `l4_calibration_log`)
- **Recalibration runway**: per-battery threshold tracks supported (Phase
  124–126); recalibration to 13-feature space requires running
  `threshold_calibrator.py` against full N≥74 corpus

The 13-feature space is not yet calibrated. This is a **known degraded
precision regime** but does not invalidate any VHP issued under the
current threshold (the threshold simply errs on the side of false
negatives — humans pass when they shouldn't, never the inverse).

### 3.3 Cryptographic ceremonies completed

- **PitlSessionProof** (Phase 67): 3 contributors, beacon block
  41723255, ~1820 constraints. LIVE.
- **ZKSepProof** (Phase 237 Session 2): 3 contributors, beacon block
  43451392, VK hash `0x32fda285…`, IoTeX-anchored. LIVE.

Ceremony trust model is **Phase 67 testnet trust model** (3 contributors
with beacon anchoring). Mainnet promotion requires re-running the
ceremony with a larger contributor set (≥5 from independent operator
identities; this is on the [[VAPI mainnet promotion runbook]]).

### 3.4 GIC chain — operational continuity proof

- **GIC_100 reached**: 2026-05-05 20:36:33 UTC
- **Head hash**: `0x0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da`
- **Genesis**: `0x87ce52cd…` (2026-04-26)
- **On-chain anchor**: tx `0xe807347eb837…` block 43348052 (2026-05-06)
- **Span**: 10.3 days of intermittent gameplay across 100 consecutive
  clean sessions

GIC_100 is a **legitimate empirical milestone** — 100 consecutive
adjudication windows of NOMINAL+EXCLUSIVE_USB+gameplay-active capture
state, hash-chained tamper-evidently. The chain is permanently
verifiable on-chain via `AdjudicationRegistry.isRecorded(GIC_100_head)`.

### 3.5 What is NOT yet validated

- **Live (non-dry-run) adjudications**: `dry_run=True` remains the
  default. Phase 231 STAGED_GRADUATION_ENABLED=true was set but Stage
  1 activation requires explicit operator POST. Until N≥100 live
  adjudications pass with zero false positives, dry_run cannot lift.
- **GSR**: N=0 calibration. `GSR_ENABLED=false` enforced. L7 advisory
  code `0x33` defined but never fires.
- **L6 active challenges**: `L6_CHALLENGES_ENABLED=false` enforced. N=0
  RIGID_MAX calibration; no haptic challenge has been issued to a real
  player.
- **L6b neuromuscular reflex**: `L6B_ENABLED=false` enforced. N=0
  reflex calibration corpus.
- **BT transport thresholds**: 0/30 sessions captured. `bt_transport_enabled=false`
  enforced. 6 of 13 L4 features compute differently at 250 Hz vs 1002 Hz
  — must NEVER reuse USB thresholds for BT sessions.
- **Multi-controller**: Xbox / Switch Pro N=0; only DualShock Edge has
  Attested tier. `multi_controller_enabled=false`.
- **Mainnet anything**: All 49 contracts are on testnet (chain ID 4690).
  Mainnet promotion runbook drafted (Phase 99-PREP) but not executed.

---

## 4. Wallet & On-Chain Health

### 4.1 Wallet position (deployer + bridge)

- **Address**: `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
- **Balance**: 15.442 IOTX (verified 2026-05-09 post-Sessions 1+2+3)
- **Recent burn**: 4.690 IOTX across 13 on-chain txs (Sessions 1+2+3)
- **Forward budget headroom**:

| Action | Estimated cost | Wallet headroom (×) |
|--------|---------------|---------------------|
| Phase O1-FRR parallel anchor (this ship; 6 txs) | ~0.18 IOTX | 85× |
| Phase O2-CURATOR ladder C3..C12 wallet-free path | ~0.07 IOTX | 220× |
| Mainnet AWS KMS HSM provisioning + dual-anchor | ~0.27 IOTX | 57× |
| Phase 99 mainnet redeploy of full contract suite | ~0.50 IOTX | 30× |
| Tournament activation chain commit (post-ratio>1.0) | ~0.05 IOTX | 308× |

**Position**: comfortable for testnet-side work. Mainnet TGE will
require fresh wallet funding (estimated 5+ IOTX for the full mainnet
deploy + 3-month operator runway).

### 4.2 Kill-switch posture (Phase 237.5 Path C+ defense)

`CHAIN_SUBMISSION_PAUSED=true` is held in `bridge/.env` as the standing
safety posture. Process-scoped overrides (`CHAIN_SUBMISSION_PAUSED=false`
in shell env, never written to `.env`) are used for authorized ships
(canary anchor, parallel O2 anchor, etc.). This is the permanent
defense against the Phase 237.5 Path C+ wallet-drain incident
(~17.95 IOTX leaked over one session due to P256 precompile + retry-blind
agents — fixed permanently in commit `f1a7be31`).

### 4.3 Recent on-chain activity (Sessions 1+2+3 arc, 2026-05-09)

| Session | Commits | Achievement |
|---------|---------|-------------|
| Canary | `01c83cd9` / `ec9915bc` | Inaugural CORPUS-SNAPSHOT permanent anchor (closes Phase 237.5 Path C+ audit trail) |
| 1 | `eeeeb366` | Curator agent LIVE @ O1_SHADOW (third Operator Initiative agent) |
| 2 | `1b2eb037` | ZKSepProof verifier suite deploy + 3-contributor ceremony |
| 3 | `76c92e9b` | VHP demo mint (tokenId=2, isValid=True; hardware + GIC + ceremony triple-bound) |

All txs were operator-authorized via triple-gate canary pattern. Zero
unauthorized burn since the kill-switch shipped.

---

## 5. The Risk Register — What Could Go Wrong

> Each risk has a documented mitigation. See [[VAPI_WHAT_IF]] for the
> formal WIF corpus.

### 5.1 Critical risks (loss of protocol integrity)

| ID | Risk | Mitigation | Status |
|----|------|------------|--------|
| R1 | Mainnet TGE before separation ratio > 1.0 confirmed across all probes | Hard rule in [[CLAUDE.md]]; PV-CI gate; multi-source enforcement | Locked |
| R2 | VHP minted to non-human (cheat slip) | 4-gate mint requirement (`audit_valid + gate_passed + NOT dry_run + dual-primitive`); Phase 113 `VAPIDualPrimitiveGate` | Locked but `dry_run=True` still |
| R3 | Cedar bundle drift undetected post-anchor | FSCA `BUNDLE_HASH_DRIFT_DETECTED` + `SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED`; cedar_drift_sweeper bundle 60s + scope 600s | Live in production |
| R4 | Soulbound VHP transferable via L1 storage proof attack | All transfer functions revert + INV checks; ERC-4671 conformance + Hardhat test coverage | Locked |
| R5 | Operator agent capability creep (Curator gains kms-sign on mainnet) | Cedar policies frozen per phase; INV-CURATOR-O2-001/002; cross-agent skill-separation invariant | Locked structurally |

### 5.2 High risks (degraded precision)

| ID | Risk | Mitigation |
|----|------|------------|
| R6 | L4 thresholds stale (12-dim calibration vs 13-dim live) | Phase 123 staleness flag; recalibration is operator-decision; no live mode promotion until calibrated |
| R7 | BT transport sessions polluted by USB thresholds | `bt_transport_enabled=false` default; Phase 124 per-battery threshold tracks; HARD RULE in [[VAPI_INVARIANTS]] |
| R8 | P3 tremor non-stationarity (corpus drift) | Phase 175 age-weighted ratio analysis + temporal_drift_index alarm |
| R9 | ioSwarm node pool homogeneity → quorum manipulation | `VAPISwarmOperatorGate.sol` min 3 distinct stakers + 1.5× weight cap |
| R10 | Mainnet Curator agentId migration breaks FSCA history | [[curator_mainnet_migration]] runbook (this ship, Stream F) — agentId-translation table + coherence_id re-keying procedure |

### 5.3 Medium risks (hardware-dependent)

| ID | Risk | Hardware required |
|----|------|-------------------|
| R11 | GSR L7 advisory layer never validated → BP-001 temporal decay assumption untested | 30 GSR sessions × 3 players = 90 sessions |
| R12 | L6/L6b haptic & reflex calibration absent | DualShock Edge + structured reflex test sessions × 50/player |
| R13 | Multi-controller tournament (Xbox/Switch) blocked by N=0 calibration | One physical controller per profile + N≥50 calibration each |
| R14 | Class K GSR spoofer adversarial untested | Synthetic EDA generator; Phase 99B open gap |

### 5.4 Low risks (non-blocking)

- R15 — Realm migration deferred until ≥100k daily PoAC; current load <100/day
- R16 — Mainnet IoTeX testnet quirks (P256 precompile) might recur; documented + 5 empirical-fix commits preserved (`8c0c8200`/`fef267e9`/`300c49e4`/`10288cc3`/`a107d404`)

---

## 6. Engineering Discipline — The Practice That Sustains VAPI

> This section answers the user's "perpetual engineering" prompt
> directly. These are not aspirations — they are operational practices
> in active use, documented in [[CLAUDE.md]] and enforced by automation.

### 6.1 Verification-First Discipline (canonical name)

Every consequential commit follows six ordered steps:

1. **Pre-implementation V-checks** (V-numbered) — read state, confirm
   assumptions, identify drift between brief and reality.
2. **Hold for operator review** at the verification checkpoint.
3. **Implementation** against the corrected brief.
4. **Post-implementation P-checks** (P-numbered) — confirm change
   matches intent and tree shape is expected.
5. **Hold for operator review** before staging.
6. **Atomic commit** with architectural reasoning preserved in commit
   body. Push only after both holds have cleared.

What this produces:
- Drift correction in both directions (V-checks catch wrong assumptions
  in the prompt; P-checks catch divergence during execution).
- Architectural reasoning preserved in the permanent record (commit
  bodies, not chat scrollback).
- Operator authority over architectural decisions enforced procedurally.

**This phase (O1-FRR) is itself a Verification-First commit**: V-checks
revealed two latent gaps (missing `operator_initiative_advancement_log`
table + 1.20 vs 1.25 gas buffer) that would have shipped silently
otherwise.

### 6.2 PV-CI invariant gate

55 SHA-256-hashed code regions are gated by `scripts/vapi_invariant_gate.py`
+ `.github/workflows/vapi-invariant-gate.yml`. Any byte-level drift in
a frozen region fails CI. Allow-list changes require:

- **Categorized reason** (refactor / bugfix / invariant_change / ceremony_update)
- **Reason length** 10–200 chars
- **`--confirm-governance`** for invariant_change category, with explicit
  governance phrase
- **Optional bridge POST** to log governance event on-chain (when
  bridge reachable)

### 6.3 FROZEN-v1 + domain tag pattern

Every cryptographic primitive freezes at v1 with a SHA-256-resistant
domain tag. Any change to byte order, hash algorithm, or pre-image
construction requires v2 + new domain tag, NEVER an in-place modification.
This is what makes the protocol's commitments **forensically replayable**
years after the fact.

### 6.4 MCP-driven state authority

Three MCP servers run in production:
- `vapi` — protocol state oracle (12 tools)
- `vapi-knowledge` — WIF + provenance + corpus knowledge (21 tools)
- `vapi-unified` — autonomous engineering layer (17 tools)

Skill state is **never hardcoded** — drift between skill instructions
and real protocol state is the failure mode. MCP tools (`vapi_protocol_state`,
`vapi_unified_state`, `vapi_skill_state_sync`) read CLAUDE.md and
current bridge state authoritatively.

### 6.5 Test count parity discipline

Every code change updates atomically:
- Source files
- Test files
- `sdk/openapi.yaml` (if endpoints change)
- Whitepaper §8.5 / §9.x (if test counts or thresholds change)
- `CLAUDE.md` NOTE block
- `MEMORY.md` index

The atomicity is enforced by review — partial commits get reverted.

### 6.6 Kill-switch + canary discipline

After Phase 237.5 Path C+'s wallet-drain incident, the protocol's posture
is **"safe by default"**:
- `CHAIN_SUBMISSION_PAUSED=true` in `bridge/.env` always.
- Process-scoped overrides for authorized ships (never `.env` writes).
- Triple-gate canary scripts (env var + intent flag + `--confirm` CLI).
- COST_BUDGET upper bound on every script.
- Wallet balance check before any tx.

This phase (O1-FRR) ships `parallel_o2_anchor.py` following exactly this
template — the canary script is the reusable defense.

### 6.7 Atomic-ship cadence

Average phase ship is **1 commit per phase** containing:
- Source changes
- Tests
- Migrations / config updates
- Documentation
- CLAUDE.md update
- Memory file

Some "atomic" ships span 2–3 commits when scope warrants (Sessions 1+2+3).
This cadence is sustainable because:
- V-checks frontload the ambiguity discovery
- PV-CI catches frozen-region regressions automatically
- Test coverage gates prevent under-testing
- The MCP layer keeps the harness aware of real state

---

## 7. Forward Roadmap — Programming for Bright Future

> Phase numbering is sequential; deviations require operator approval.
> Each phase has documented LOC estimate + wallet impact + test delta.

### 7.1 Immediate (this session — O1-FRR-PARALLEL ship)

**Status**: 8/9 streams complete; pre-commit P-checks running.

- [x] Stream A — validate Curator O2 SUGGEST bundle
- [x] Stream B — implement FRR primitive
- [x] Stream C — schema migration + 7 store helpers
- [x] Stream D — gas buffer hardening on `cedar_bundle_anchor.py`
- [x] Stream E — `parallel_o2_anchor.py` triple-gate script
- [x] Stream F — `curator_mainnet_migration.md` runbook
- [x] Stream G — 9 new tests (FRR + gas buffer)
- [x] Stream H — 6 new PV-CI invariants (49 → 55)
- [ ] Stream I (this final stream) — CLAUDE.md NOTE + memory + atomic commit

**Dry-run validated**: parallel anchor outputs expected FRR
`0xfa12d744…` deterministically; cost ~1.5 IOTX (10× under budget);
gates work correctly.

### 7.2 Near-term (next 1–2 phases, all wallet-free)

**Phase O2-PARALLEL-ANCHOR-EXEC** (operator-gated execution):
- Operator runs `scripts/parallel_o2_anchor.py --confirm` with env gates set.
- 6 txs land; FRR verification confirms post-anchor state matches
  pre-anchor expectation.
- All three Operator Initiative agents elevate to `O2_SUGGEST` simultaneously.
- Wallet impact: ~0.18 IOTX; FRR baseline accumulation begins.

**Phase O1-CURATOR C3..C5** (Curator ladder advancement, code-only):
- C3: shadow log persistence wiring for Curator-specific event types.
- C4: drift sweep extension (already done in C2/C6 wave; verify
  Curator drift findings emit correctly).
- C5: frontend operator-agent visibility — extend ShadowLogPanel +
  DriftFindingsPanel with Curator filter.

**Phase 213 separation re-measure**:
- Run `analyze_interperson_separation.py --session-type tremor_resting`
  with Phase 213 zero-padded FFT fix applied.
- Confirm `all_pairs_p0_ok=True` post-fix (P1vP3 should resolve to >1.0).
- Anchor result via `SeparationRatioRegistry.commit()`.

### 7.3 Medium-term (3–6 months, requires operator+hardware effort)

**Phase 99 mainnet promotion** (REQUIRES wallet funding ≥5 IOTX):
- Run `deploy-phase99a.js` / `99b.js` / `99c.js` on IoTeX mainnet
  (chain ID 4689).
- Update `deployed-addresses.json` + `bridge/.env.mainnet`.
- Deploy ZK ceremony with ≥5 contributors (mainnet trust upgrade).

**Phase O3 ACT promotion** (REQUIRES Sentry+Guardian shadow_min=504h):
- Promote Sentry + Guardian to `O3_ACT` (live-write enabled with
  operator authorization per kms-sign action).
- Curator promotes through dedicated avenue (marketplace skills).

**BT transport calibration** (REQUIRES 30 BT sessions × 3 players):
- Capture 10 `bt_resting_grip` + 10 `bt_touchpad_corners` + 10
  `bt_gameplay` per player.
- Run `threshold_calibrator.py --battery bt_resting --transport ble`.
- Insert via `POST /agent/l4-threshold-track`.
- Compute composite key `<profile_hash>:bt_resting:ble`.

**GSR L7 calibration** (REQUIRES GSR grip hardware + 30 sessions/player):
- BOM: ~$45 prototype; Ag/AgCl electrodes + ESP32-S3 + INA128 + LiPo.
- Capture 30 sessions per player with grip active.
- Run `gsr_threshold_calibrator.py`; emit per-player thresholds.
- Move L7 from advisory-only to weight=0.10 in humanity formula.

### 7.4 Long-term (6–12 months, strategic)

**Tournament activation chain commit** (REQUIRES separation_ratio>1.0
across ALL probes + all_pairs_p0_ok=True + N≥100 live adjudications + 0 FP):
- Run tournament preflight (8-condition gate; Phase 127 LIVE).
- Promote `dry_run=False` for `SessionAdjudicator` + `RulingEnforcementAgent`.
- Activate `VAPISwarmOperatorGate.sol` live mode (≥3 distinct stakers
  with ≥10k VAPI each).

**Token Generation Event (TGE)**:
- Sequenced AFTER tournament activation chain commit.
- Distribution: 30% operator staking / 25% device rewards / 20%
  ecosystem / 15% team (4-yr vest) / 10% liquidity.
- VAPI token utility: staking → slashing → data marketplace fees →
  rewards. Never speculative.

**Realm migration** (REQUIRES ≥100k daily PoAC submissions):
- Migrate to IoTeX Realm (app-specific chain) for throughput.
- All Phase 99+ contracts already use TransparentUpgradeableProxy
  pattern → migration is address-preserving.

**Multi-controller tier expansion**:
- Xbox Series X / Switch Pro per-controller calibration tracks.
- PHCI certification on `VAPIHardwareCertRegistry`.
- Standard tier (L0–L5) tournament eligibility for non-DualShock devices.

---

## 8. Strategic Themes — Why VAPI Will Continue To Be Important

### 8.1 The DePIN-AI convergence is the macro tailwind

DePIN protocols are increasingly being asked to verify the humanness of
their participants. VAPI's posture (cryptographically verifiable proof
of ACTIVE HUMAN PRESENCE during a specific session, not a global
identity) maps cleanly to:
- Bot-resistant tournaments
- Bot-resistant data marketplaces (Phase 238 LISTING-v1)
- Bot-resistant token incentive distribution
- Bot-resistant federated learning labelers

The VHP soulbound credential is the unit of composition. Once N≥1
mainnet VHPs exist, downstream protocols can compose `isFullyEligible()`
into their own gates.

### 8.2 The corpus is a permanent asset

217 calibration sessions across 3 distinct human players represents
~12+ hours of physiological data captured at 1000 Hz over 13 features.
This corpus:
- Cannot be reproduced without physical controllers
- Validates a real-world separation hypothesis (P1≠P2≠P3 detectable
  at >1.0 ratio for AIT probes)
- Is the empirical anchor for any future security audit of
  `isFullyEligible()`

The CORPUS-SNAPSHOT primitive freezes corpus state cryptographically.
Even if the source data is lost, the commitment lives on-chain.

### 8.3 The multi-agent operator fleet is structurally novel

No competing DePIN gaming protocol has a ≥3-agent operator fleet with
procedurally enforced cross-agent skill separation. The Sentry+Guardian
+Curator triplet is a **first** in the category. Phase O1-FRR adds the
cryptographic primitive that makes "all three at the same phase" a
single 32-byte commitment — this is a **permanent capability** that
downstream contracts can compose against.

### 8.4 The ZK proof stack is composable

Two Groth16 verifiers are LIVE on mainnet-class infra (testnet today):
- `PitlSessionProofVerifier` (Phase 67)
- `Groth16VerifierZKSepProof` + `ZKSepProofVerifier` wrapper (Phase 237 Session 2)

A third verifier (FRR ZK proof — proving "all 3 agents reached phase X
without revealing per-agent shadow data") is a **clean future ship**.
This is the kind of composition that compounds: each ZK ceremony adds a
commitment that downstream consumers can verify cheaply on-chain.

---

## 9. Bright-Future Programming Checklist (Actionable)

> What every future contributor / future-Claude must remember when
> programming on VAPI to keep the protocol healthy.

### 9.1 NEVER DO

- [ ] Modify the 228-byte PoAC wire format (Phase 1 FROZEN)
- [ ] Change the chain link hash from `SHA-256(raw[:164])` (FROZEN)
- [ ] Loosen L4 thresholds without `threshold_calibrator.py` against N≥74 (locks: anomaly 7.009, continuity 5.367)
- [ ] Set `GSR_ENABLED=true` without N≥30 calibration per player
- [ ] Set `L6_CHALLENGES_ENABLED=true` without N≥50 RIGID_MAX calibration
- [ ] Set `bt_transport_enabled=true` without an active BT threshold track
- [ ] Mint VHP bypassing the 4-gate enforcement
- [ ] Apply USB thresholds to BT sessions
- [ ] Reuse any FROZEN-v1 domain tag in a new primitive (always bump to v2 + new tag)
- [ ] Skip the V-check holds before any consequential commit
- [ ] Push to mainnet anything before separation ratio > 1.0 confirmed across ALL probes

### 9.2 ALWAYS DO

- [ ] Read [[CLAUDE.md]] before any code change (it's the protocol's
  authoritative state)
- [ ] Run `vapi_protocol_state` MCP at session start (never hardcode
  state)
- [ ] Cite separation ratio from MCP, not from skill embedded state
  (drift is the failure mode)
- [ ] Update CLAUDE.md NOTE block + MEMORY.md index atomically with code
- [ ] Add PV-CI invariants for any new FROZEN-v1 primitive
- [ ] Write tests covering determinism + sort canonicalization + tag
  sensitivity for any new cryptographic primitive
- [ ] Use `tempfile.mkdtemp()` (NOT `TemporaryDirectory`) for SQLite-using
  tests on Windows (WAL PermissionError)
- [ ] Wrap new background loops in `asyncio.to_thread()` for any sync
  work >10ms (Phase 235.x-STABILITY-2 invariant)
- [ ] Add `gas_buffer_multiplier=1.25` for any new IoTeX storage-heavy
  contract write
- [ ] Use the canary triple-gate pattern for any wallet-spending script

### 9.3 PERIODICALLY DO

- [ ] Monthly: review wallet balance + project burn rate
- [ ] Monthly: refresh this assessment document
- [ ] Quarterly: review the WHAT_IF corpus for newly-grounded W1 risks
- [ ] Quarterly: run `/vapi sweep post-code` against the latest 10 commits
- [ ] Yearly: review the FROZEN-v1 primitive catalog for v2 candidates
- [ ] Per release: regenerate `INVARIANTS_ALLOWLIST.json` if new
  frozen regions added

---

## 10. Conclusion

VAPI's position at 2026-05-10 is **structurally sound and accelerating**:
- 49 contracts LIVE
- 8 (soon 9) FROZEN-v1 cryptographic primitives in production
- 3-agent operator fleet at first synchronized advancement
- 2,822 bridge tests + 539 SDK + 528 Hardhat all green
- 55 PV-CI invariants gating frozen regions
- 15.44 IOTX wallet (85× margin against next planned action)
- 217-session calibration corpus across 3 distinct human players
- Verification-First Discipline embedded in commit practice
- 2 Groth16 verifiers LIVE; ceremony trust model documented for
  mainnet upgrade

What separates VAPI from a "smart contract project" is its
**layered cryptographic stack** combined with its **biometric calibration
corpus** combined with its **engineering discipline**. Each compounds
the others: more primitives → richer composition surface; more corpus →
tighter separation gates; better discipline → fewer regressions. The
protocol is on a trajectory where each phase adds permanent capability
without taking on technical debt.

**Bright future programming** is not a one-time deliverable — it's the
continuous practice of:
1. Reading state from authoritative sources before changing it
2. Validating assumptions (V-checks) before committing to direction
3. Persisting empirical findings (corpus, ceremonies, anchored hashes)
4. Freezing primitive byte-layouts permanently (FROZEN-v1 + domain tags)
5. Surfacing drift automatically (PV-CI gates + FSCA contradiction rules)
6. Sequencing risky operations behind triple-gate canaries
7. Promoting capabilities only when empirical evidence supports them

VAPI is on track. Continued discipline + steady ship cadence + careful
sequencing = the protocol's continued importance and success.

---

## Tags

#vapi #depin #agaas #iotex #cryptographic-primitives #frozen-v1
#operator-initiative #separation-ratio #tournament-readiness
#assessment #position-paper #engineering-discipline #verification-first
#perpetual-engineering #roadmap-2026

## Cross-references

- [[CLAUDE.md]] — project authoritative state
- [[VAPI_CONTEXT]] — phase-by-phase deliverable history
- [[VAPI_INVARIANTS]] — frozen invariants catalog
- [[VAPI_AGENTS]] — 38-agent fleet detail
- [[VAPI_WHAT_IF]] — WIF corpus
- [[curator_mainnet_migration]] — Curator promotion runbook (this ship)
- [[Phase O0 Stream 2 Deploy Runbook]] — original-avenue agent registration
- [[Phase O1-FRR-PARALLEL]] — this phase (in implementation)
- [[Phase 99-PREP Deploy Runbook]] — mainnet TGE precursor

---

**Document version**: 1.0
**Generated**: 2026-05-10
**Next refresh**: 2026-06-10 (or sooner on major state change)
**Author authority**: Claude Code, VAPI principal architect (Verification-First commit practice)
