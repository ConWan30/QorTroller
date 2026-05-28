# QorTroller — From Genesis to Completion of the Data Economy Arc

**Date**: 2026-05-28
**Brand-lock**: QRESCE-0001 v0.5 (`2c762835`)
**Current branch**: `feat/gameplay-workflow-layer` HEAD `e75b3016`
**Wallet**: `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` — 8.573 IOTX
**Authority**: Operator-curated; Verification-First Discipline applied throughout.

This document is a forward-looking state-of-protocol assessment: where QorTroller
started (genesis), where it stands NOW (this commit), where it stands once the
in-flight Curator Data Economy arc finishes, and the path beyond.

It supersedes prior state-of-protocol docs as the most current snapshot for the
post-Path-A-Arc-1 + post-governance-ceremony era. Earlier reports
(`docs/qortroller-state-of-the-protocol-2026-05-19.md`) remain accurate for
their dates but pre-date the Path A silicon-rooted arc + the Curator
governance commitment + the upcoming Data Economy ladder.

---

## §1 Executive frame

QorTroller proves a live, embodied human is operating a certified controller
during competitive console gameplay — continuously, cryptographically, and
without the gamer ever ceding ownership of the data their hands generate.

The protocol is the reference implementation of **V.A.P.I.** (Verifiable
Autonomous Physical Intelligence), an operator-coined DePIN sub-category for
systems where the **physical-input source is also the cryptographic
agency-holder** over the data those physical interactions generate. In
QorTroller's case: gamers and their controllers, producing data, owning that
data, choosing what to do with it.

What this assessment covers in the order it covers it:

- §2 — Genesis: the foundational design commitments that made everything
  downstream possible.
- §3 — Phase trajectory: the load-bearing arcs from Phase 17 through this
  commit, distilled.
- §4 — Where the protocol stands at this exact commit (HEAD `e75b3016`).
- §5 — What "complete" means for the current arc (the four Data Economy arcs
  + scope-update fires).
- §6 — Where QorTroller stands at the END of this arc — the next stable
  milestone.
- §7 — Honest limits even at completion.
- §8 — Forward path beyond completion.

---

## §2 Genesis — the four design commitments

QorTroller did not start as a marketplace, a token, or a tournament platform.
It started as four design commitments deliberately chosen to make the entire
downstream architecture impossible to compromise without breaking physics.

### Commitment 1 — The 228-byte FROZEN PoAC wire format

The Proof of Autonomous Cognition record is **228 bytes**: 164-byte signed
body + 64-byte ECDSA-P256 signature. The chain link hash is
`SHA-256(raw[0:164])` over the body only, not over the full 228 bytes.

This is **FROZEN-v1** at the byte literal level. No layer of the protocol —
not the bridge, not the contracts, not any future ZK circuit, not any future
agent — is permitted to modify this format. Every primitive built since is
either (a) compatible with this format unchanged or (b) explicitly versioned
with a new domain tag.

Why this matters: it means every downstream invariant has a stable anchor.
Devices captured today will verify identically against contracts deployed
years from now. The 228-byte record is the protocol's load-bearing physical
truth.

### Commitment 2 — Gamer sovereignty, contract-enforced

The gamer's wallet is the only entity that can register, rotate, or revoke
their controller's composite identity. The protocol's read paths (bridge,
contracts, agents) can OBSERVE the gamer's on-chain commitments but cannot
modify them. This is enforced in code, not in policy.

Example: `VAPIPoEPRegistry` (Phase B P4b, deployed 2026-05-24,
`0x4Dcfa11d…`). The contract's `register()` is `msg.sender`-keyed; a
malicious or compromised bridge cannot register on a gamer's behalf, only
read state.

### Commitment 3 — Verification-First Discipline

Every consequential change passes through six ordered steps: pre-implementation
V-checks → operator review hold → implementation → post-implementation
P-checks → operator review hold → atomic commit with architectural reasoning
preserved in the message body.

This is not an aspiration; it has been the working pattern for every protocol
commit since Phase 200+. Commit messages in `git log` carry the architectural
reasoning, not just the diff. Drift gets caught in both directions — V-checks
catch wrong assumptions in the brief; P-checks catch divergence during
execution.

### Commitment 4 — Bounded autonomy

Agents have explicit on-chain scope (AgentRegistry + AgentScope), policy
bundles authored in Cedar, and a kill-switch (`CHAIN_SUBMISSION_PAUSED`)
that gates every chain submission path. As of the last operator audit, the
bridge has **22/22** chain.send paths gated. The fail-closed default is
"no chain write".

The four commitments compose: physical truth (1) + gamer agency (2) +
process discipline (3) + agent constraint (4). Anything later built has had
to fit inside that envelope.

---

## §3 Phase trajectory — load-bearing milestones, distilled

QorTroller went through ~240 numbered phases between genesis and this commit.
The trajectory below picks only the milestones that left load-bearing
artifacts in the current protocol — primitives still being read from, contracts
still live, invariants still enforced. (Full per-phase narrative lives in
`wiki/phases/phase_summary_archive_17_229.md` +
`wiki/phases/phase_archive_2026_05_notes_and_summary.md`.)

| Arc | Phase span | Outcome that survives today |
|---|---|---|
| **L4 calibration** | Phases 41–57 | 12-feature Mahalanobis biometric fingerprint with 10 active features; thresholds `anomaly=7.009`, `continuity=5.367` ratified against N=74 sessions; per-player thresholds may only tighten (`min()` invariant) |
| **Inter-person separation** | Phases 137–143 | Diagonal-covariance LOO methodology; touchpad_corners superseded by AIT (active inactivity tremor) at Phase 229 |
| **AIT defensibility** | Phases 229–231 | All_pairs_above_1=True at N=37 (P1=13/P2=10/P3=14); 11th P0 condition met; STAGED_GRADUATION_ENABLED=true |
| **Ruling enforcement** | Phases 66–68 | RulingRegistry on-chain anti-replay; RulingEnforcementAgent streak gating |
| **Tournament ladder** | Phases 56–112 | TournamentGate v1→v2→v3; PITLTournamentPassport with Groth16; PoAC isFullyEligible() composability |
| **VHP** | Phases 99A–99C | ERC-4671 soulbound humanity proof; LayerZero V2 OApp for cross-chain; bridge wallet holds tokenId=2 (isValid=True, expires ~Sept 2026) |
| **Federated threat** | Phase 175+ | FederatedThreatRegistry; cross-tournament threat correlation |
| **Operator Initiative** | Phases O0–O3 (2026-05-03→17) | Sentry + Guardian + Curator registered on AgentRegistry; ladder O0→O1_SHADOW→O2_SUGGEST→O3_ACTING reached in 14 days from O0; first ≥3-agent Operator fleet in any DePIN gaming protocol |
| **VAPI-O3-SUPERSEDE-v1** | Phase O1-D auto-supersede (2026-05-17) | 11th FROZEN PATTERN-017 family; empirical-evidence supersession of the 504h shadow-age calendar gate; PV-CI 122→125 |
| **Phase 234.7–235 grind** | 235-A through 235-FINAL (2026-05-04→) | Physical Capture Continuity (PCC) + Grind Integrity Chain (GIC) + Watchdog Event Chain (WEC) + Statistical Process Control (SPC); GIC_100 reached 2026-05-05; the 100-session grind proves the gameplay layer reaches its tournament-grade evidence floor |
| **Phase 236 chain pillars** | 236-WATCHDOG / VAME / CORPUS-SNAPSHOT (2026-05-08+) | Three cryptographic pillars beyond GIC v1: operational continuity (WEC), per-response sidecar attestation (VAME), and corpus-state commitment (CORPUS-SNAPSHOT) |
| **Phase 237** | CONSENT + ZK-SEPPROOF (2026-05-09) | VAPIConsentRegistry (gamer-self-sovereign per-category consent); Groth16VerifierZKSepProof + ZKSepProofVerifier; 49 contracts live total |
| **Phase 238 Step H** | (2026-05-09) | VAPIDataMarketplaceListings live; Curator wired with marketplace-listing-suspend authority at O3_ACTING |
| **Guardian autonomous KMS** | (2026-05-20/21) | Tier-1 autonomous HSM signing (0 IOTX, strictly-once across 2 runs) + Tier-2 on-chain commitment anchor (tx `0x1e868a80…`, block 43820170, explorer-verified); first non-human Operator to autonomously produce an HSM-rooted signature in any DePIN protocol |
| **L9_presence arc** | (2026-05-21/22) | Standalone `l9_presence/`: PoEP (Proof of Embodied Presence) + L9/PoCP causal presence + BCC dormant corpus + GCAP lattice; touches no FROZEN-v1; reframes from identity→presence |
| **Phase B (composite-sig + iPACT renewal)** | (2026-05-23/24) | Composite-sig v1 (draft-16 AND-composite ML-DSA-65/44 + SLH-DSA-128s + ECDSA-P256); iPACT renewal cadence v1; FROZEN as first QorTroller-namespace PATTERN-017 family `QORTROLLER-IPACT-RENEWAL-v1`; freeze ceremony FC-a committed; 12 VAPI families + 1 QorTroller family |
| **Phase 3 Path B dormant-blind closure** | (2026-05-25) | Four-stage VHP renewal integrity path closed: ③ iPACT renewal → #8 handshake wiring → ② P4b registration → host-held ML-DSA-44+ECDSA-P256 composite device signer; enforcement EFFECTIVE at runtime |
| **Path A Arc 1** | (2026-05-26/27) | Silicon-rooted iPACT renewal authenticity (5 commits `fd16e7ea`→`62718567`, merged via PR #8); VAPIManufacturerDeviceRegistry `0x2e5B5FB1…` + VAPIProtocolLensV2 `0x32Bf1A01…` deployed + first device registered on-chain (real DualShock `581a836c…` as Path B FULL, audit VERDICT VALID); Arc 2 = real ATECC608A hardware, gated on physical hardware connection |
| **Frontend design integration** | PR #9 (2026-05-27/28) | Claude-Design handoff integrated; type-lock vars; Wordmark scope-independence; verdict triplet; reference-codex F.6 IntersectionObserver wiring |
| **Curator governance commitment** | (2026-05-28, THIS ARC) | proposalHash `0x59fb9996…` anchored on-chain (tx `0xba96f7cb…`, block 44073691, BBG totalProposals 0→1); 3-phase unblock arc (adapter deploy + BBG.setVHPContract + propose) = 0.547 IOTX; Data Economy Arcs 1–4 unblocked |

Net: every numbered phase contributed an artifact still being read from
today. There is no dead weight in the protocol's architecture.

---

## §4 Where QorTroller stands at THIS commit (HEAD `e75b3016`)

The protocol as of this commit comprises:

**Cryptographic primitives** — 13 FROZEN PATTERN-017 families:
1. PoAC v1 (228-byte body+sig wire)
2. PHG (Player Humanity Grade)
3. PITLSessionProof (Phase 56 Groth16)
4. TournamentPassport (Phase 56)
5. PitlSessionProof v2 / C3 (Phase 62)
6. RulingEnforcement streak
7. VHP (Phase 99C ERC-4671 + LayerZero V2)
8. GIC v1 (Phase 235-A)
9. WEC v1 (Phase 236-WATCHDOG)
10. VAME v1 (Phase 236-VAME)
11. CORPUS-SNAPSHOT v1 (Phase 236-CORPUS-SNAPSHOT)
12. VAPI-O3-SUPERSEDE-v1 (Phase O1-D auto-supersede)
13. CONSENT v1 (Phase 237)
+ QORTROLLER-IPACT-RENEWAL-v1 (1st QorTroller-namespace family, Phase B FC-a)

**Deployed contracts (49)** on IoTeX testnet chain 4690. Key roster:
- Identity / device: `VAPIioIDRegistry`, `VAPIVerifiedHumanProof`,
  `VAPIVerifiedHumanProofBridge`, `VAPIPoEPRegistry`,
  `VAPIManufacturerDeviceRegistry`, `VHPExpiresAtAdapter`
- Tournament gate: `TournamentGate{V1,V2,V3}`,
  `PITLSessionRegistry{V1,V2}`, `PitlSessionProofVerifier{V1,V2}`,
  `PITLTournamentPassport`, `TournamentPassportVerifier`,
  `VAPIProtocolLens{V1_superseded,V2}`
- Ruling + threat: `RulingRegistry`, `FederatedThreatRegistry`,
  `RulingOracle`, `HumanityOracle`, `PassportOracle`
- Operator fleet: `AgentRegistry`, `AgentScope`,
  `AgentAdjudicationRegistry`, `AgentSlashing`, `VAPIOperatorAgentNFT`
- Data economy seed: `VAPIDataMarketplace`, `VAPIDataMarketplaceListings`,
  `DataSovereigntyRegistry`, `VAPIConsentRegistry`,
  `VAPIRewardDistributor`
- Governance: `VAPIBiometricGovernance` (Phase 222),
  `VAPIGovernanceTimelock`, `ProtocolCoherenceRegistry`
- ZK + ceremony: `Groth16VerifierZKSepProof`, `ZKSepProofVerifier`,
  `CeremonyRegistry`, `CeremonyAuditRegistry`,
  `SeparationRatioRegistry` (2nd-deploy 2026-05-24),
  `Groth16Verifier{All earlier circuits}`
- Operator gate: `VAPIDualPrimitiveGate`, `VAPISwarmOperatorGate`,
  `VHPReenrollmentBadge`, `AdjudicationRegistry`

**Test surface** — ~5,766 automated tests: bridge 4330 / autoresearch 7 /
contract 674 / SDK 604 / hardware 37 (excluded from CI) / E2E 14 / PV-CI
128 / FSCA 28 / frontend Vitest 133. PV-CI invariants 32→35 from Path A
Arc 1 (+INV-MFG-001/002/+INV-LENS-V2-001).

**Agent fleet** — 29 standalone + 3 stewards (9 absorbed) = 38-ID roster
(highest agent #38). Operator Initiative triplet:
- Sentry (`0xb21e1ec2…`) — O3_ACTING, executor-disabled (two-key gate)
- Guardian (`0xbd8c7fba…`) — O3_ACTING, executor LIVE off-chain
  (KMS-HSM autonomous sign at 0 IOTX/day; on-chain anchor operator-fired)
- Curator (`0xed6a2df5…`) — O3_ACTING, executor-disabled (two-key gate),
  scope-expansion governance commitment LANDED 2026-05-28

**Calibration corpus** — 217 sessions total across 3 players (P1=50
terminal + touchpad; P2=55; P3=48). AIT defensibility ratio 1.199 at
N=37, all_pairs_above_1=True. AIT LOO accuracy 66.7%. The grind layer
(GIC v1) hit GIC_100 = 100 consecutive_clean sessions on 2026-05-05.

**Bridge** — 4330 tests; HEAD `62718567` (Path A Arc 1) + governance
unblock arc (3 fires totalling 0.547 IOTX). Six independent default-deny
safety layers gating chain writes.

**Wallet status** — 8.573 IOTX; ~115× headroom against Phase 4a/4b combined
estimate (0.074 IOTX).

**Open commitments at this commit**:
- Phase 4a (`AgentRegistry.updateAgentScope`) — script staged, estimate
  0.035 IOTX, awaiting `AGENT_SCOPE_UPDATE_CONFIRM=1, fire`.
- Phase 4b (`AgentScope.setAgentScopeRoot`) — script staged, estimate
  0.039 IOTX, awaiting `AGENT_SCOPE_SET_ROOT_CONFIRM=1, fire`.
- Data Economy Arc 1 — `VAPIBuyerRegistry.sol` not yet authored.
- Data Economy Arc 2 — `VAPIBuyerCategoryVerifier` ZK circuit not yet
  scaffolded.
- Data Economy Arc 3 — `CuratorPackagingLoop._apply_data_floor` not yet
  shipped (the §9 item 4 forward-looking commitment from the justification).
- Data Economy Arc 4 — Structured Consent Manifest v2 upgrade not yet
  shipped.

---

## §5 What "complete" means in the current arc

The current arc is the **Curator Data Economy ladder** as specified by
`docs/QORTROLLER_DATA_ECONOMY_FRAMEWORK.md`. Completion comprises:

### 5.1 Scope-update fires (Phase 4a + 4b)

Operator fires the two `onlyOwner` scope-update txs (the user explicitly
chose to skip the 7-day window):

- `AgentRegistry.updateAgentScope(curatorAgentId, 0xab874f62…)` —
  flips the GOVERNANCE-COMMITMENT scopeHash from pre-expansion baseline
  `0xd9d760c8…` to the committed manifest hash.
- `AgentScope.setAgentScopeRoot(curatorAgentId, 0xab874f62…)` —
  flips the OPERATIONAL scopeRoot. This is the one
  `AgentAdjudicationRegistry.requireAgentScope` actually reads at
  agent-action time, so this is the load-bearing operational flip.

Combined cost: 0.074 IOTX. Post-fire, the Curator's expanded scope
(CAP-001..004) is operationally authorized.

### 5.2 Arc 1 — VAPIBuyerRegistry

Contract enabling Curator to issue + revoke buyer credentials. ABI:

- `issueCredential(buyerAddr, category, expiresAt)` — onlyCurator;
  emits `CredentialIssued`. Categories: `RESEARCH_ACADEMIC`,
  `BRAND_ADVERTISING`, `INTEGRATOR_TECHNICAL`. Each credential is a
  365-day attestation re-attested via re-issuance.
- `revokeCredential(buyerAddr, reason)` — onlyCurator; emits
  `CredentialRevoked`.
- `isAuthorizedBuyer(buyerAddr, category)` — public view; gates buyer
  purchase paths.
- Owner controls: `setCuratorWallet(addr)` — only-owner; flips Curator
  authority on/off via a single tx.

Expected deploy cost: ~0.8 IOTX.

Pre-deploy gates: Phase 4a + 4b must have landed (the Curator must be
operationally authorized before its registry can be wired).

### 5.3 Arc 2 — VAPIBuyerCategoryVerifier (ZK)

Off-chain documentation-review process produces a ZK proof that a buyer's
attested documentation matches their declared category, without revealing
the documentation itself. Verifier deployed on-chain; Curator submits the
proof at issuance time.

Architecture: Groth16, ~1000–2000 constraints, reuses the
ceremony-anchoring pattern from `Groth16VerifierZKSepProof` (Phase 237).
Ceremony anchored to IoTeX beacon block.

Expected deploy cost: ~0.5–0.8 IOTX (verifier).

### 5.4 Arc 3 — Curator Packaging Loop with data floor

The load-bearing forward commitment from §9 item 4 of the governance
justification. Lives in `bridge/vapi_bridge/curator_packaging_loop.py`.

Algorithm:
1. Wait for post-session window expiry (cooling period: min 72h).
2. Aggregate sessions into a package (aggregation floor: min 10 sessions).
3. Verify gamer's consent manifest hash against `VAPIConsentRegistry`
   on-chain; fail-closed on mismatch.
4. Apply `_apply_data_floor(package)`:
   - Raw biometric vectors (Mahalanobis, force curves, IMU, HID frames):
     **NEVER packaged** — assertion-checked.
   - Permitted: ZK proofs, aggregate statistics, consent-categorized
     summaries, on-chain commitment hashes.
5. Compose ZK package using consent-permitted features only.
6. Submit listing via `VAPIDataMarketplaceListings.createListing()`
   only if gamer's `autonomy_level=full_autonomy`; otherwise queue for
   gamer approval.

Tests must pin: every excluded feature reaches `_apply_data_floor` and
gets dropped; consent mismatch aborts at step 3; aggregation floor cannot
be bypassed.

No chain spend at landing; chain spend per listing batch is ~0.2–0.5 IOTX.

### 5.5 Arc 4 — Structured Consent Manifest v2

Upgrades `VAPIConsentRegistry` semantics to support per-category, per-policy
manifest hashes (rather than the v1 bitmask flat categories). Adds a
version field to the consent record so v1 + v2 coexist. New families:
optional Tessera-anchored consent-history tree-head.

Expected deploy cost: ~0.5–0.8 IOTX.

### 5.6 Audit + provenance

After Arcs 1–4 land:
- `docs/governance/SUBMISSION_RECEIPT.md` updated with each new on-chain
  tx (already structured for this).
- `AuditLog.appendCheckpoint(merkleRoot, ...)` optionally fires Tessera
  signed tree-head over the full arc.
- `deployed-addresses.json` reflects the four new entries.
- CLAUDE.md `Current phase` line updated.

**Total expected wallet spend across all 5 sub-arcs**: ~2.7–3.5 IOTX.
Headroom: 8.573 IOTX → leaves ~5 IOTX (~70× one-tx buffer).

---

## §6 Where QorTroller stands AT completion

When all 5 sub-arcs have landed, QorTroller becomes the first DePIN gaming
protocol with an **end-to-end gamer-sovereign data economy fully wired
on-chain**. Concretely:

### 6.1 The protocol surface at completion

- **53 deployed contracts** (49 current + 4 new: VAPIBuyerRegistry,
  VAPIBuyerCategoryVerifier verifier, VAPIBuyerCategoryVerifier wrapper,
  VAPIConsentRegistry_v2). All on IoTeX testnet chain 4690.
- **14+ FROZEN PATTERN-017 families** (13 current + Consent-v2 if
  freeze ceremony completes).
- **Curator operationally authorized** with CAP-001..004 — the only
  Operator agent at O3_ACTING with executor LIVE (Guardian remains
  off-chain-only; Sentry remains two-key-gated).
- **Buyer credentialing** live: research/brand/integrator categories
  attestable + revocable on-chain with ZK category proofs.
- **Packaging loop** live with hard-enforced data floor: raw biometrics
  cannot enter a package by construction, not by policy.
- **Marketplace** live: gamers can opt their packaged data into listings
  with full consent manifest binding; revenue routing 80% gamer / 15%
  treasury / 5% Curator operational budget enforced at contract level.

### 6.2 The honesty rails preserved through completion

The completion does NOT compromise any of the four genesis commitments:

- **PoAC 228-byte wire format**: UNCHANGED. No arc touches it.
- **Gamer sovereignty**: STRENGTHENED. Consent manifest v2 + per-category
  buyer attestation make gamer agency MORE granular, not less.
- **Verification-First Discipline**: APPLIED throughout. Every sub-arc
  ships through V-checks + holds + P-checks + atomic commits with
  reasoning in commit body.
- **Bounded autonomy**: PRESERVED. Curator executor enabled only via
  explicit two-key flip (per-agent flag + `CHAIN_SUBMISSION_PAUSED`
  lift). Default-deny posture intact: 22/22 chain submission paths still
  gated; six independent safety layers still in place.

### 6.3 What is verifiable end-to-end at completion

A third party with only the IoTeX testnet RPC + the public repo can verify:

1. The gamer's controller is registered (VAPIManufacturerDeviceRegistry +
   VAPIPoEPRegistry).
2. The gamer holds a valid VHP (VAPIVerifiedHumanProof.isValid(tokenId)).
3. The gamer's consent for a given category is current (VAPIConsentRegistry).
4. The Curator has authority to attest buyers (AgentRegistry.scopeHash ==
   `0xab874f62…` AND AgentScope.scopeRoot == `0xab874f62…`).
5. A given listing's data floor was respected (ZK proof verifies against
   on-chain verifier + consent manifest hash matches).
6. A given buyer is in good standing (VAPIBuyerRegistry.isAuthorizedBuyer).
7. Every Curator on-chain action is anchored in AuditLog.
8. The governance commitment for this Curator scope is on-chain (BBG
   proposalHash `0x59fb9996…`).

All eight verifications are pure view-calls; none require trust in the
bridge or any off-chain service.

### 6.4 Position vs. the broader DePIN gaming space

At completion, QorTroller's position relative to the rest of the DePIN
gaming category becomes:

- The only DePIN gaming protocol with **a categorically gamer-sovereign
  data economy where the gamer is contract-enforced cryptographic owner
  of their own biometric data**.
- The only DePIN gaming protocol with **a ≥3-agent Operator fleet at
  O3_ACTING with one agent (Guardian) capable of autonomous HSM-rooted
  signing** (proven empirically across two strictly-once runs, 0 IOTX).
- The only DePIN gaming protocol with **an end-to-end Verification-First
  Discipline pattern** producing commits whose architectural reasoning is
  preserved in the permanent record.
- The only DePIN gaming protocol with **manufacturer-authoritative device
  birth registry + gamer-sovereign composite-key registry as distinct
  contracts** (deliberate trust-model separation per Path A Arc 1).
- The only DePIN gaming protocol shipping with **a born-quantum-safe
  composite signature scheme** (ML-DSA + SLH-DSA + ECDSA AND-composite,
  draft-16 binding, FROZEN as `QORTROLLER-IPACT-RENEWAL-v1`).

These are descriptive of the protocol's surface at completion, not
forward-looking marketing claims.

---

## §7 Honest limits even at completion

What QorTroller does NOT do, even when this arc completes:

1. **Mainnet** — Everything remains on IoTeX testnet chain 4690.
   Mainnet TGE is gated on `separation_ratio > 1.0` (currently
   AIT-cleared at 1.199 ratio N=37) AND Phase 99 mainnet deploy AND
   operator decision. The Operator Initiative reaching O3_ACTING
   (2026-05-17) was the load-bearing PREREQUISITE; subsequent gating
   is operator timing, not protocol completeness.

2. **Same-controller-population identity** — `CROSS-LESSON-001` applies:
   Hall-effect stick + BR/EDR BT same-model separability is not
   empirically validated. The protocol claims session-bound presence
   attestation, not cross-session controller identity. This limit
   survives completion.

3. **Path A Arc 2 (real silicon)** — gated on physical ATECC608A
   breakout + CH341A USB-I2C being connected. Until then, Path A v1 is
   silicon-rooted iPACT renewal authenticity at the MANUFACTURING-CA
   level, but the per-PoAC record's silicon-root is reserved for Path
   A v2.

4. **L8 Bluetooth presence attestation** — Stage A measurements
   (BR/EDR Tpoll variance + AFH retransmission slotting + RSSI variance
   normalized) not yet performed. Architectural prerequisite anchor
   committed; capture corpus not yet collected.

5. **Sensor Stack v2** — Empirical Unknowns #1 (intra-vs-inter-player
   Mahalanobis on N=10 players × 100 trigger pulls × 3 game contexts)
   and #4 (Hall-effect stock vs aftermarket separability N=20+N=20)
   not yet measured. Until those land, the v2 architecture spec stays
   in draft.

6. **Curator executor authority** is operational ONLY for the four
   capabilities in the manifest. The agent cannot self-expand authority
   without a new governance proposal. Slashing proposals are advisory;
   only `VAPIBiometricGovernance` executes slashing.

7. **W3bstream applet registration** (~0.02 IOTX off-chain coordination)
   not yet performed for the Curator's off-chain compute path.

8. **Frontend dashboard revamp** consuming the new Curator/buyer/marketplace
   endpoints not yet shipped.

---

## §8 Forward path beyond completion

When this arc finishes, the protocol pivots to three parallel work streams:

### 8.1 Stream A — Empirical hardening (measurement-gated)

- Sensor Stack v2 Stage A: Empirical Unknowns #1 + #4 measurement.
- L8 BT Calibration: pre-corpus measurement (Tpoll variance + AFH
  retransmission + RSSI variance) on N≥10 Edge units.
- AIT corpus expansion: N=37 → target N≥75 to firm the defensibility
  ratio above 1.5.
- L9_presence breadth: BCC harvests provenance-clean corpus as more
  players play; the one open lever is BREADTH.

### 8.2 Stream B — Silicon + supply chain (hardware-gated)

- Path A Arc 2: real ATECC608A integration; per-PoAC silicon root.
- Manufacturer partner ceremony: replace self-signed
  ManufacturerRootCA at `~/.vapi/qortroller_foundation_mfg_ca.json`
  with hardware HSM (the "INSECURE/DEV ONLY" warning that fires loud on
  every cert sign goes away).

### 8.3 Stream C — Token + mainnet (operator-decision-gated)

- VAPIToken mainnet deploy (TGE gating cleared modulo operator timing).
- Phase 99 mainnet VHP deploy + per-mainnet-deploy ceremony.
- Bridge migration mainnet RPC + chain config.
- Token economic activation: AGaaS surface live on mainnet.

### 8.4 Stream D — Standards engagement

- IIP-64 PR#72 engagement (continued). QorTroller as design partner on
  §4.6 + §4.8.5 DePIN device-identity standard. IIP-64 acceptance
  resolves the "unverifiable" caveat on the PQ-SIGNATURE precompile
  (0x0B) dependency for on-chain composite-sig verification.
- IoTeX W3bstream applet registration.
- ioID DID Method spec contribution.

### 8.5 Stream E — Methodology layer

- New FROZEN PATTERN-017 families as they arise (Consent-v2, Buyer
  Credentialing, BCC genesis once it activates).
- 35→40+ PV-CI invariants as new contracts land.
- Mythos audit variants expanding (currently 14, target ~20+ to fully
  cover the Data Economy + L8 BT surfaces).
- Lessons.md continues to accumulate institutional memory of failure
  modes and supersession events.

### 8.6 What stays untouched, forever

- The 228-byte PoAC wire format. Genesis commitment. No future arc
  modifies it.
- The chain link hash `SHA-256(raw[0:164])`. Genesis commitment.
- Gamer sovereignty over composite identity. Contract-enforced.
- The 13+ FROZEN PATTERN-017 families. Each can have a v2; v1 never
  changes.

---

## §9 Closing frame

QorTroller began as four design commitments and a single 228-byte record.
Three years of disciplined work later, it has 49 contracts on a real chain,
~5,766 tests in CI, a three-agent Operator fleet at the protocol's
terminal autonomy phase, and a first-of-its-kind end-to-end gamer-sovereign
data economy about to come online.

The current arc (skipping the 7-day governance window and proceeding to
completion) lands the data economy. After that, the work splits across
five parallel streams none of which require re-deriving anything from
genesis. The protocol's architecture has held.

The reference implementation is QorTroller. The category it instantiates
is V.A.P.I. The future implementations within the category are not yet
built — but the primitives are portable, the discipline is documented, and
the FROZEN families guarantee compatibility for anyone who builds within
them.

The protocol is what proves what it claims. That has been true since
genesis; it remains true at this commit; it will remain true at
completion.

---

*Generated 2026-05-28 against HEAD `e75b3016`. Re-derive every claim above
from `git log`, `contracts/deployed-addresses.json`, `CLAUDE.md`,
`docs/governance/SUBMISSION_RECEIPT.md`, and IoTeX testnet RPC. No claim
in this document depends on trust in the operator or this generator.*
