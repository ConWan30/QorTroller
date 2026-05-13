# VAPI: A Verified Autonomous Physical Intelligence Protocol for Competitive Gaming

## Whitepaper v4 — Canonical Successor to v3

**Author:** Contravious Battle (Independent Researcher)
**Network:** IoTeX testnet (chain ID 4690)
**Architecture anchor commit:** `e81e04aa` (Phase O4-VPM-INTEGRATION close, 2026-05-13)
**Documentation revamp commit:** `9f8581cd` (README + Whitepaper v4 successor landing, 2026-05-13)
**Supersedes:** v3 (Zenodo DOI 10.5281/zenodo.18966169, Phase 68–70 baseline)
**Citation:** DOI assignment pending Zenodo release. Until v4 minting: cite v3 + reference this file at architecture anchor `e81e04aa` (documentation revamp commit `9f8581cd`).
**License:** Copyright © 2026 Contravious Battle. All Rights Reserved.

---

## Abstract

VAPI (Verified Autonomous Physical Intelligence) introduces a Decentralized Physical Infrastructure (DePIN) architecture on IoTeX for cryptographic human-gameplay verification in competitive gaming. Each controller input event produces a 228-byte Proof of Autonomous Cognition (PoAC) record binding raw sensor commitments (Inertial Measurement Unit dynamics, analog trigger dynamics, stick/button timing, biometric feature commitments) to a hardware-rooted ECDSA-P256 signature and a SHA-256 hash-chained sequence anchored on the IoTeX EVM. A nine-level Physical Input Trust (PITL) stack interprets each record through layered detectors — from hardware presence (L0) to active haptic challenge-response (L6) — and exposes the resulting per-session eligibility through a single composable on-chain view call, `VAPIProtocolLens.isFullyEligible(deviceIdHash)`. The on-chain gate minimizes integrator trust by reducing eligibility to a public view call over previously anchored protocol state; integrators do not need to operate a private publisher API or inspect raw biometric data themselves.

As of Phase O4-VPM-INTEGRATION close (2026-05-13), the protocol comprises 49 substantive live smart contracts on IoTeX testnet (51 contract registry slots), a 38-agent bridge runtime fleet including three on-chain registered Operator Initiative agents, 77 PV-CI invariants pinning load-bearing source-code regions at PR time, 26 FSCA (Fleet Signal Coherence Agent) contradiction rules, a 10-element family of FROZEN-v1 cryptographic primitives (PATTERN-017), seven shipped Zero-Knowledge Biometric Artifact (ZKBA) classes (AIT, GIC, VHP, HARDWARE, CONSENT, TOURNAMENT, MARKET) composing through one deterministic compiler pipeline, six active Verified Projection Media (VPM) compilers under a three-layer Anti-Hype Visual Grammar discipline, and a three-agent Operator Initiative fleet (Sentry, Guardian, Curator) at lifecycle O1_SHADOW with Cedar v2 lane authority bundles dual-anchored on AgentScope + AgentRegistry. Test coverage stands at 3344 bridge tests, 562 SDK tests, 528 Hardhat contract tests, and 26 Vitest frontend tests.

The protocol's headline tournament gate — inter-person separation ratio > 1.0 with all-pairs separability — is empirically cleared for the Active Isometric Trigger (AIT) calibration battery at ratio 1.199 with N=37 sessions (Phase 229–231 breakthrough), sufficient as AIT-based testnet/demo eligibility evidence in the current corpus. The touchpad_corners battery remains an open blocker at ratio 0.728 for actual tournament BLOCK enforcement; corpus expansion work continues. The token launch invariant ("no Token Generation Event before separation_ratio > 1.0 confirmed and all_pairs_above_1=True") remains in force for legal/economic defensibility.

This whitepaper supersedes v3 in scope and currency. v3 captures Phase 68–70 (Ruling Registry + MPC ceremony) baseline; v4 captures the full architectural state through Phase O4 (Verified Projection Media output layer). v3's Zenodo DOI is preserved for historical continuity; v4 receives a new DOI at Zenodo release.

The architectural contribution claimed: VAPI's reference implementation simultaneously pins (1) the FROZEN-v1 primitive family, (2) the deterministic content-addressed compiler, (3) the FROZEN six-state visual grammar enforced at three independent runtime layers, and (4) the FROZEN browser-iframe sandbox attribute. Together these four enforcement surfaces form a quadruple-bind around the protocol's emitted cryptographic claims. Each emitted claim is independently verifiable by anyone with the canonical-JSON algorithm + SHA-256 + the public source of the four enforcement layers.

---

## 1. Protocol problem statement

Cheat detection in competitive gaming has no cryptographic anchor.

The dominant industry solutions — Riot Vanguard (Valorant), Easy Anti-Cheat (Fortnite, Apex Legends, many others), BattlEye (PUBG, Rainbow Six Siege), and the closed-source detection systems of platform holders — share an identical architecture: ring-0 kernel drivers continuously scan running processes, memory, and input streams against a publisher-controlled allowlist or anomaly model. They are effective against the attacks they are designed to detect, but the protocol-architectural posture is one of total trust in the publisher: an external observer (tournament organizer, viewer, sponsor, regulator) cannot independently verify any specific match was clean. The publisher's word is the entire root of trust.

This produces three structural failures:

1. **Cross-publisher non-interoperability.** A player banned by one publisher's anti-cheat has no portable, cryptographically attested record of cleanness usable by another publisher's tournament. Each ecosystem operates a parallel reputation regime.
2. **Forensic opacity for dispute resolution.** When a match outcome is contested (suspected aimbot, suspected wallhack, suspected input-injection), the referee has no cryptographic evidence trail — only logs the publisher chooses to expose.
3. **No legal-economic anchor for token issuance.** A protocol that wishes to issue tokens conditional on "cleanness" (e.g., DePIN rewards for verified human gameplay sessions) cannot defensibly do so without a separation primitive that cryptographically distinguishes a human from a bot, and one player from another, in a way that survives downstream audit.

VAPI's design hypothesis: the input event itself is the right cryptographic boundary. Every controller input — every trigger pull, every stick deflection, every button press — produces a 228-byte record signed by hardware-rooted keys on a certified controller, chained into a tamper-evident sequence, and anchored on a public blockchain. The protocol does not trust the publisher, does not trust the player, does not trust the operator. It trusts only the cryptographic primitives.

What the protocol provides instead of trust:

- A FROZEN-v1 wire format (228 bytes; INV-001 pinned) that any external verifier can parse without protocol-specific tooling.
- A FROZEN chain-link hash discipline (`SHA-256(raw[:164])`; INV-002 pinned) that any external verifier can recompute.
- A FROZEN nine-level PITL stack of signals where layers L0–L3 are tournament-BLOCKING and layers L4–L7 are advisory but cryptographically logged.
- A FROZEN domain-tag taxonomy (`b"VAPI-*-v1"`) under which ten distinct cryptographic primitives (PATTERN-017) compose without ambiguity.
- A FROZEN seven-class Zero-Knowledge Biometric Artifact (ZKBA) family that wraps the protocol's verified state into stakeholder-specific projections.
- A FROZEN three-layer Anti-Hype Visual Grammar that surfaces overclaim attempts at compile time, audit time, and browser-render time.

The phrase "FROZEN" in this whitepaper is load-bearing. A FROZEN region of source code is pinned by the PV-CI (Persistent-Validation Continuous-Integration) invariant gate. Any byte-level modification to the region fails CI unless the modification is preceded by an explicit governance ceremony (`--confirm-governance` + a typed confirmation phrase + a category-tagged reason text). The protocol's authority structure is encoded in source-code pins, not in operator goodwill.

---

## 2. The 228-byte PoAC wire format (FROZEN)

The Proof of Autonomous Cognition record is the protocol's primitive cryptographic unit. Each PoAC record is exactly 228 bytes:

| Bytes | Field | Notes |
|---|---|---|
| 0..3 | `magic` | `b"VAPI"` literal; FROZEN |
| 4..7 | `record_version` | uint32 BE; v1 = 1 |
| 8..15 | `session_seq` | uint64 BE; per-session monotonic |
| 16..47 | `device_id_hash` | bytes32; SHA-256 of canonical device-name UTF-8 bytes |
| 48..79 | `prev_record_hash` | bytes32; chain-link to prior record |
| 80..87 | `ts_ns` | uint64 BE; monotonic per-session nanos |
| 88..127 | sensor commitments | 40 bytes; IMU + trigger + stick deflection |
| 128..159 | biometric vector commitment | 32 bytes |
| 160..163 | `cheat_codes` | 4 bytes; bitfield of hard + advisory codes (see §3) |
| **164..227** | **`signature`** | **64 bytes; ECDSA-P256 over `SHA-256(raw[0..163])`** |

The chain link hash discipline is FROZEN by INV-002:

```
record_hash = SHA-256(raw[0..163])
```

The hash is computed over the **body only** — bytes 0 through 163 inclusive — **not** the full 228 bytes. This separation prevents a chain-link forgery where a malicious party could replace the signature without breaking the hash chain; the hash chain commits to the body, the signature commits to the body, the two cryptographic surfaces compose without circular dependency.

The `cheat_codes` field is a 4-byte bitfield with two tiers:

**Hard cheat codes** (tournament-BLOCKING; trigger an immediate eligibility revocation):
- `0x28` DRIVER_INJECT — software-driver-level input injection detected (L2 IMU-vs-HID discrepancy or L2C stick-IMU correlation failure)
- `0x29` WALLHACK — wallhack-class TinyML signal from the L3 behavioral classifier
- `0x2A` AIMBOT — aimbot-class TinyML signal from the L3 behavioral classifier

**Advisory cheat codes** (logged, cryptographically chained, but not tournament-BLOCKING):
- `0x2B` TEMPORAL_BOT — L5 temporal-rhythm anomaly (coefficient-of-variation or quantization signature)
- `0x30` BIOMETRIC_ANOMALY — L4 Mahalanobis-distance threshold exceeded
- `0x31` IMU_PRESS_DECOUPLED — L2B IMU-button causal-latency advisory
- `0x32` STICK_IMU_DECOUPLED — L2C stick-IMU cross-correlation advisory (inactive in dead-zone-stick games)
- `0x33` GSR_CORRELATION_ABSENT — L7 galvanic-skin-response advisory (only when `GSR_ENABLED=true`, which requires N≥30 calibration sessions per player; currently disabled)

Every PoAC record's `cheat_codes` field is logged regardless of whether any code is set. Even a clean session produces a chained record; tournament eligibility is evaluated over the full session's record set, not over any single record.

---

## 3. The nine-level Physical Input Trust (PITL) stack

Each PoAC record carries enough signal to evaluate against nine independent detection layers. Layers L0–L3 produce hard cheat codes that block tournament eligibility; layers L2B, L2C, L4, L5, L6, L7 produce advisory codes that are cryptographically logged but do not block tournament play.

| Layer | Code | Type | Signal | Status |
|---|---|---|---|---|
| **L0** | — | Structural | HID presence (USB enumeration at 1000 Hz polling rate) | LIVE |
| **L1** | — | Structural | PoAC chain integrity (SHA-256 hash-chain unbroken) | LIVE; INV-002 pinned |
| **L2** | `0x28` | Hard cheat | IMU gravity vector + HID/XInput discrepancy | LIVE; tournament-BLOCKING |
| **L3** | `0x29` / `0x2A` | Hard cheat | TinyML behavioral classifier (9-feature space; aimbot + wallhack heads) | LIVE; tournament-BLOCKING |
| **L2B** | `0x31` | Advisory | IMU-button causal latency (Δt between trigger-onset and IMU recoil) | LIVE |
| **L2C** | `0x32` | Advisory | Stick-IMU cross-correlation (`abs(max_causal_corr) < threshold`) | LIVE; inactive in dead-zone-stick games (e.g., NCAA CFB 26) |
| **L4** | `0x30` | Advisory | 13-feature Mahalanobis biometric fingerprint | LIVE; anomaly threshold 7.009 / continuity threshold 5.367 |
| **L5** | `0x2B` | Advisory | Temporal rhythm (coefficient of variation, entropy, quantization detection) | LIVE |
| **L6** | — | Advisory | Active haptic challenge-response (sub-perceptual haptic stimulus → reflex window detection) | GATED — `L6_CHALLENGES_ENABLED=false` until N≥50 hardware calibration sessions |
| **L7-GSR** | `0x33` | Advisory | Galvanic skin response sympathetic-arousal correlation with game events | GATED — `GSR_ENABLED=false` until N≥30 per-player GSR sessions; N=0 today |
| **L8** | — | Transport | Bluetooth 250 Hz BLE controller path | GATED — `bt_transport_enabled=false` until N≥30/player BT MVCP |

Layer codes that are present in the protocol enumeration but currently gated by calibration requirements are deliberately disabled by default. The protocol's invariant discipline is that a layer cannot be enabled without the corresponding empirical calibration N being met; flipping `L6_CHALLENGES_ENABLED=true` without N≥50 calibration sessions would violate INV-007/008 and fail CI.

The default humanity probability formula (without L6 active, which is the production posture for current corpus state):

```
humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·p_L2B + 0.10·p_L2C
```

L2C resolves to a 0.5 neutral prior in dead-zone-stick games where the cross-correlation signal is uninformative (NCAA College Football 26, the primary game corpus). The formula effectively runs as a four-signal probability sum for that game family.

---

## 4. L4 biometric calibration — the tournament-gate primitive

The L4 layer is the protocol's per-player anomaly detector and the source of the inter-person separation primitive that gates tournament eligibility.

### 4.1 The 13-feature Mahalanobis space

Each PoAC record contributes a 13-dimensional feature vector. The features were selected through three calibration cycles (Phase 17 → Phase 46 → Phase 57) and represent the smallest space that empirically distinguishes one human from another using a single certified controller (Sony DualShock Edge CFI-ZCP1) without per-player hardware customization.

| # | Feature | Source signal | Active? |
|---|---|---|---|
| 0 | `trigger_resistance_change_rate` | Adaptive trigger force curve derivative | Structurally zero on current hardware; excluded |
| 1 | `trigger_onset_velocity_L2` | L2 trigger onset velocity | LIVE |
| 2 | `trigger_onset_velocity_R2` | R2 trigger onset velocity | LIVE |
| 3 | `micro_tremor_accel_variance` | Accelerometer micro-tremor variance | LIVE |
| 4 | `grip_asymmetry` | Left/right palm pressure differential | LIVE |
| 5 | `stick_autocorr_lag1` | Right-stick autocorrelation at lag 1 frame | LIVE |
| 6 | `stick_autocorr_lag5` | Right-stick autocorrelation at lag 5 frames | LIVE |
| 7 | `tremor_peak_hz` | FFT peak frequency in 4–15 Hz band (4096-point zero-padded FFT, parabolic interpolation; Phase 213) | LIVE |
| 8 | `tremor_band_power` | FFT power in 8–12 Hz band | LIVE |
| 9 | `accel_magnitude_spectral_entropy` | Shannon entropy of 0–500 Hz accel magnitude spectrum (Phase 46) | LIVE |
| 10 | `touch_position_variance` | Touchpad 2D position variance | Structurally zero in gameplay sessions; excluded by zero-variance auto-exclusion |
| 11 | `press_timing_jitter_variance` | Inter-button-press IBI variance (Phase 57) | LIVE |
| 12 | `touchpad_spatial_entropy` | 8×8 Shannon entropy heatmap of touchpad contact (Phase 121) | LIVE |

Live feature dimension at Phase O4 close: **13** (down from a nominal 13 minus 2 structurally zero features that the zero-variance auto-exclusion in `analyze_interperson_separation.py` excludes).

### 4.2 Calibration thresholds (Phase 57, N=74)

The current production thresholds:

- L4 anomaly threshold: **7.009** (mean + 3σ over 74 calibration sessions)
- L4 continuity threshold: **5.367** (mean + 2σ over 74 calibration sessions)

Thresholds can **only tighten** (via the `min()` operator in the bridge's threshold-update path), never loosen. This is a non-negotiable security invariant: a calibration update that would loosen a per-player threshold is refused at the bridge layer regardless of operator authorization.

### 4.3 The separation ratio — protocol headline metric

The protocol's tournament gate is gated by the inter-person separation ratio:

```
separation_ratio = mean(inter-player Mahalanobis distance)
                 / mean(intra-player Mahalanobis distance)
```

A ratio > 1.0 means "any two distinct players are on average further apart in 13-dimensional Mahalanobis space than any two sessions of the same player." The additional all-pairs invariant requires that **every** player-pair distance > 1.0, not just the average — preventing one outlier player from carrying the ratio.

**Current state across three calibration batteries (CLAUDE.md authoritative, 2026-05-13):**

| Battery | Ratio | N | `all_pairs_above_1` | `all_pairs_p0_ok` | Tournament gate |
|---|---|---|---|---|---|
| **AIT** (Active Isometric Trigger; Phase 229–231 breakthrough) | **1.199** | 37 | **True** | True | **CLEARED** for testnet/demo |
| **touchpad_corners** | 0.728 | 35 | False | False | BLOCKER for tournament BLOCK enforcement |
| **tremor_resting** | 1.177 | 27 | False | False (P1vP3=0.032; Phase 213 fix pending verification) | Open |
| pooled (free-form) | 0.417 | 127 | False | False | Historical plateau baseline; superseded by AIT |

The AIT battery breakthrough (Phase 229, 2026-04-18; corpus expanded Phase 231, 2026-04-20) was achieved through structured probe sessions: each player holds L2 trigger at 50% (90–180 analog units) for 30 seconds, generating a tremor + gravity fingerprint that is anatomically stable per player. Four features (`accel_tremor_peak_hz` at 4096-pt zero-padded FFT, `roll_cos`, `roll_sin`, `pitch_cos`) extracted from the still-hold IMU stream produced the first all-pairs-above-1 result in the protocol's history.

The token launch invariant ("no TGE before separation_ratio > 1.0 confirmed empirically and all_pairs_above_1=True") **remains in force**. The AIT clearance is sufficient for testnet/non-tournament demonstrations and for advancing the Phase 99 ERC-20 + ERC-4671 stack toward deployment-readiness; it does not by itself authorize tournament BLOCK enforcement, which is gated by touchpad_corners closure.

---

## 5. The 10-element FROZEN-v1 primitive family (PATTERN-017)

The protocol's cryptographic surface composes through ten FROZEN-v1 primitives, each with a unique 21-character byte-literal domain tag and an INV-* PV-CI gate pin. The family is enumerated and pinned in `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` Appendix B + `scripts/vapi_invariant_gate.py`.

| # | Primitive | Domain tag (FROZEN) | Output | Phase | PV-CI pin |
|---|---|---|---|---|---|
| 1 | **PoAC** wire format | (none; struct-encoded) | 228-byte record | 1 | INV-001 |
| 2 | **PoAC chain hash** | (none; SHA-256(raw[:164])) | bytes32 | 1 | INV-002 |
| 3 | **L4 Mahalanobis** | (none; distance metric) | float (anomaly score) | 17, 46, 57, 121, 213 | INV-PCC-002..005 |
| 4 | **L2B causal latency** | (none) | float (Δt seconds) | 17 | — |
| 5 | **L2C stick-IMU cross-correlation** | (none) | float (correlation coefficient) | 17 | — |
| 6 | **L5 temporal rhythm** | (none) | tuple(CV, entropy, quantization) | 17, 241 | INV-APOP-001..002 |
| 7 | **GIC** (Grind Integrity Chain) | `b"VAPI-GIC-GENESIS-v1"` | bytes32 chain head | 235-A | INV-GIC-001..003 |
| 8 | **WEC** (Watchdog Event Chain) | `b"VAPI-WEC-GENESIS-v1"` | bytes32 chain head | 236-WATCHDOG | — |
| 9 | **VAME** (VAPI Application-Layer Message Envelope) | `b"VAPI-VAME-v1"` | bytes32 commitment | 236-VAME | — |
| 10 | **ZKBA artifact** | `b"VAPI-ZKBA-ARTIFACT-v1"` | bytes32 commitment | O3-ZKBA-TRACK1 C2 | INV-ZKBA-001..003 |

Adjacent FROZEN-v1 surfaces (cryptographic primitives that are not themselves "PATTERN-017" but compose with it):

- **CORPUS-SNAPSHOT v1** — `b"VAPI_CORPUS_SNAPSHOT_v1"`; Phase 237.5; inaugural anchor 2026-05-09
- **CONSENT v1** — per-category gamer consent commitment; Phase 237; INV-VPM-WRAPPER-001 alignment via Phase O4 wrapper layer
- **BIOMETRIC-SNAPSHOT v1** — Phase 237-ZK-SEPPROOF; ZK-attested AIT corpus snapshot anchor
- **LISTING-v1** — Phase 238 MARKETPLACE listing primitive
- **VPM artifact** — `"vapi-vpm-artifact-v1"` (NOT a byte-literal; UTF-8 schema string); Phase O4 Stream A.0; INV-VPM-COMPILER-002

### 5.1 The chain primitives — operational + cognitive continuity

Three primitives in the family produce **chains**, not single commitments:

**GIC (Grind Integrity Chain)** — Phase 235-A. Per-session cognitive-integrity chain. Each grind session produces a 32-byte GIC entry; entries chain via SHA-256 with monotonic ts_ns + verdict_code + host_state_code embedded in the preimage. The chain head is the canonical "I grinded N consecutive clean sessions" attestation. **GIC_100 — the 100-link milestone — was permanently anchored on IoTeX testnet 2026-05-06 at transaction `0xe807347eb837...` block 43348052** (Phase 239 G3 close). Genesis: `0x87ce52cd21f9...`; head: `0x0e9d453d9042...`. INV-GIC-001..003 pin the formula, monotonicity guard, and chain-break detection logic.

**WEC (Watchdog Event Chain)** — Phase 236-WATCHDOG. Operational-continuity chain that hash-chains every bridge process lifetime event (BRIDGE_START / BRIDGE_HEALTHY / BRIDGE_UNRESPONSIVE / BRIDGE_RESTART_TRIGGERED / WATCHDOG_HALT) into a tamper-evident audit trail. Pairs with GIC: GIC documents cognitive continuity; WEC documents the operational continuity of the process that produced those sessions. Together they constitute the full provenance for a grind run.

**CORPUS-SNAPSHOT v1** — Phase 237.5. Anchors a hash commitment of the entire wiki/ + agent fleet Merkle root + AIT separation ratio + session count into the AdjudicationRegistry on IoTeX. Inaugural anchor 2026-05-09 at tx `0x24e4ddb6...` closed the Phase 237.5 Path C+ wallet-drain incident audit trail.

### 5.2 Composition discipline

The ZKBA-ARTIFACT primitive (#10 in the family) is structurally designed to **compose** the other primitives. A single ZKBA artifact's preimage may reference 1, 2, or 3 primitives simultaneously:

- **1-primitive artifacts** — AIT (composes corpus statistics), GIC (composes chain head), VHP (composes soulbound token state), HARDWARE (composes hardware cert), CONSENT (composes consent state)
- **2-primitive artifacts** — MARKET (composes LISTING-v1 + CONSENT v1)
- **3-primitive artifacts** — TOURNAMENT (composes VHP + GIC + ProtocolLens.isFullyEligible())

The composition lattice — which artifact composes which primitives — is rendered as an inline-SVG directed acyclic graph in the CDRR-DAG VPM (one of the four internal projection compilers shipped Phase O4 Stream A.1.c). The DAG is FROZEN at Phase O4 close: 7 nodes (one per ZKBAClass) + 5 composition edges.

---

## 6. On-chain anchoring (IoTeX testnet)

The protocol deploys to IoTeX testnet (chain ID 4690) because IoTeX provides three properties no general-purpose L1 provides:

1. **Native P-256 precompile at address `0x0100`.** ECDSA-P256 verification is the cryptographic core of PoAC; IoTeX's precompile makes verification gas-affordable (sub-100k gas per record) whereas equivalent on Ethereum mainnet would be 200k+ gas via signature-library contracts.
2. **ioID device identity stack.** Every certified controller can register a `did:io:` identifier with a deterministically-deployed ERC-6551 Token Bound Account, giving the controller itself an addressable identity separate from the player's wallet.
3. **W3bstream DePIN data layer.** Off-chain biometric data processing happens in W3bstream applets (AssemblyScript compiled to WASM) before any on-chain commitment, keeping raw biometrics out of public-chain storage while preserving cryptographic verifiability.

### 6.1 Contract registry (49 substantive live testnet contracts)

The authoritative on-chain address registry is `contracts/deployed-addresses.json`. As of Phase O4 close, the registry contains **49 substantive live testnet contracts across 51 registry slots** organized by function. Selected highlights:

**PITL stack + core protocol (5):**
- `PoACVerifier` — ECDSA-P256 verification + chain integrity
- `PITLSessionRegistry` (V1 + V2) — ZK PITL proof registry with anti-replay
- `PITLSessionProofVerifier` — Groth16 verifier
- `PHGCredential` — Proof of Humanity Gating soulbound credential
- `TournamentGateV3` — PHG + credential-active tournament entry gate

**Anchor + adjudication registries (3):**
- `AdjudicationRegistry` `0x44CF981f46a52ADE56476Ce894255954a7776fb4` (Phase 111)
- `RulingRegistry` `0xa3A2356C90E642a7c510d0C726EC515EA720c621` (Phase 68)
- `CeremonyRegistry` `0x739B5fae312834bA2a7e44525bA5f54853C5672f` (Phase 67)

**Operator Initiative governance (Phase O0):**
- `AgentRegistry` — on-chain agentId source-of-truth (Q9-frozen format)
- `AgentScope` — Cedar v2 lane authority dual-anchor (operational FIRST per INV-OPERATOR-AGENT-001)
- `AgentSlashing` + `AgentAdjudicationRegistry` + `AuditLog`

**ZK verifiers (4):**
- `Groth16VerifierZKSepProof` `0xD63EEf1372Cb496071bf963bEE395F7e0A3f2Ab6` + `ZKSepProofVerifier` `0xd51a21E234a800a6621f4c23a8fcA44e3bF01002` (Phase 237 Session 2)
- `PitlSessionProofVerifierV2` (Phase 62)

**Phase 99 AGaaS layer:**
- `VAPIToken` — ERC-20 + Pausable; MAX_SUPPLY=1B; `tgeComplete` flag
- `VAPIOperatorRegistry` — MINIMUM_STAKE=10k VAPI; slash 50%/50%
- `VAPIHardwareCertRegistry` — `isCertified(profileHash) → bool`
- `VAPIGSRRegistry` — GSR sample anti-replay
- `VAPIVerifiedHumanProof` (VHP) — ERC-4671 soulbound; 90-day TTL
- `VAPIVerifiedHumanProofBridge` — LayerZero V2 OApp for cross-chain VHP

**Phase 130+ ioSwarm + governance:**
- `VAPISwarmOperatorGate` `0x969c0F1EFb28504a95Acf14331A59FBCb2944F98` — minimum 3 distinct stakers
- `ProtocolCoherenceRegistry` `0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` — fleet Merkle anchor
- `VAPIBiometricGovernance` `0x06782293F1CFC1AA30C0Baee0437c2B336796A00`
- `VAPIGovernanceTimelock` — 2-of-3 multisig + CEI

**Phase 222+ consent + marketplace:**
- `VAPIConsentRegistry` `0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` — per-category gamer consent
- `VAPIDataMarketplaceListings` `0x78Df84Cc512EdCaC0e58a03e4852627E2F62E3bC` (Phase 238 Step H)

The bridge wallet (and protocol deployer) is `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`, holding approximately 15.03 IOTX as of Phase O4 close. The wallet was the operator-funded source of all on-chain anchoring ceremonies through Phase O4; total IOTX consumed across the entire on-chain footprint to date is approximately 4.7 IOTX (Phase O0 deployment 4.68 + Track 2 ceremony 0.23 - canary recovery 0.18 ≈ net 4.7).

`CHAIN_SUBMISSION_PAUSED=true` is held in `bridge/.env` as the default operating posture; every chain-write path in `bridge/vapi_bridge/chain.py` is gated by this kill-switch (22 audited submission paths verified in commit `f1a7be31`). Lifting the kill-switch requires explicit three-factor operator authorization (env var + env var + `--confirm` CLI flag) at the PowerShell terminal.

### 6.2 The composability claim — `isFullyEligible()`

The protocol's tournament gate exposes through a single composable on-chain view call:

```solidity
function isFullyEligible(bytes32 deviceIdHash) external view returns (bool);
```

`VAPIProtocolLens` (Phase 108) implements this view by composing:

1. `PHGCredential.isValid(deviceIdHash)` — Proof of Humanity Gating credential exists and has not expired
2. `RulingRegistry.latestRulingFor(deviceIdHash) != BLOCK` — no active BLOCK ruling
3. `PHGCredential.isSuspended(deviceIdHash) == false` — no active suspension
4. (post Track 2 + Phase 178) — biometric credential TTL within 90 days
5. (post Phase 197) — `separation_defensibility_log.all_pairs_p0_ok == true`

An external tournament organizer can implement gating with two lines of Solidity:

```solidity
IVAPIProtocolLens lens = IVAPIProtocolLens(VAPI_LENS_ADDR);
require(lens.isFullyEligible(deviceIdHash), "VAPI: ineligible");
```

The on-chain gate minimizes the integrator's trust surface: a tournament organizer reduces the eligibility decision to a public view call over previously anchored protocol state, without needing to operate a private publisher API or manually inspect raw biometric data. The protocol's broader physical-to-chain pipeline (off-chain capture, calibration, bridge integrity, operator controls, proof-generation discipline) still depends on the verifiability surfaces described elsewhere in this whitepaper — the single view call is the composability point for downstream integrators, not a claim that the entire pipeline is trustless.

---

## 7. The Operator Initiative — three-agent CFSS fleet

VAPI's autonomous governance is distributed across a 38-agent asyncio fleet inside the bridge process. Of those 38, three agents form the **Operator Initiative** — agents with on-chain registered identities, Cedar v2 lane authority bundles dual-anchored on chain, and explicit Cross-Fleet Skill Separation (CFSS) invariants.

### 7.1 The three agents

| Agent | Canonical name | On-chain agentId (Q9 frozen) | ioID DID | TokenId | Lane authority |
|---|---|---|---|---|---|
| **Anchor Sentry** | `anchor_sentry` | `0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c` | `did:io:0xeaa6fd569a964c08d541f8e154ab3ac8cd4e2743` | 495 | `tool:zk-artifact-anchor` on `draft://zk_artifacts/*` |
| **Guardian** | `guardian` | `0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1` | `did:io:0x9c577fb2162824565ef57edd1b55a8ec5f58c181` | 496 | `tool:zk-audit-trail` on `draft://zk_verifications/*` |
| **Curator** | `curator` | `0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8` | `did:io:0x7BdB744c87c8f86e348246557BB58D60641312C2` | 497 | `tool:zk-marketplace-listing` on `draft://zk_listings/*` |

All three agents are at lifecycle **O1_SHADOW** (Cedar v2 bundles anchored 2026-05-12 via the parallel Track 2 ceremony). They observe-only; their actions surface as drafts in the operator review queue rather than direct chain writes. Lifecycle advancement (O1 → O2_SUGGEST → O3_ACT) is gated by operator-runtime observation: 7-day window with ≥9/10 acceptance gate, plus N≥50 drafts accumulated, plus disagreement rate < 5% per agent.

### 7.2 Cross-Fleet Skill Separation (CFSS)

The CFSS invariant encodes a three-way agent governance separation: each agent has exclusive write authority over its lane prefix, and every other agent's Cedar policy explicitly FORBIDS the cross-lane action. The full 12-row lane authority matrix is pinned in `scripts/zkba_post_ceremony_audit.py:EXPECTED_LANE_MATRIX`:

| Agent | Action | Resource | Effect |
|---|---|---|---|
| anchor_sentry | tool:zk-artifact-anchor | draft://zk_artifacts/* | **permit** |
| anchor_sentry | skill:read | lane://zk_artifacts/** | permit |
| anchor_sentry | tool:zk-audit-trail | (any) | **forbid** |
| anchor_sentry | tool:zk-marketplace-listing | (any) | **forbid** |
| guardian | tool:zk-audit-trail | draft://zk_verifications/* | **permit** |
| guardian | skill:read | lane://zk_verifications/** | permit |
| guardian | tool:zk-artifact-anchor | (any) | **forbid** |
| guardian | tool:zk-marketplace-listing | (any) | **forbid** |
| curator | tool:zk-marketplace-listing | draft://zk_listings/* | **permit** |
| curator | skill:read | lane://zk_listings/** | permit |
| curator | tool:zk-artifact-anchor | (any) | **forbid** |
| curator | tool:zk-audit-trail | (any) | **forbid** |

The matrix encodes the structural guarantee: a compromised Sentry cannot emit a marketplace listing; a compromised Curator cannot anchor an artifact; a compromised Guardian cannot mint a humanity credential. The three lanes are **on-chain anchored** via the Cedar v2 bundle ceremony — bundle Merkle roots Sentry `0x39e8b65f...db1f23` / Guardian `0x6818a9ad...0a9a0` / Curator `0x0ade0c92...60a80b3d` — and verifiable from any external reader via `AgentScope.getScopeRoot(agentId)` + `AgentRegistry.scopeHash(agentId)`.

### 7.3 The dual-anchor discipline (INV-OPERATOR-AGENT-001)

Cedar v2 bundles are anchored to TWO contracts in a strict order: **operational FIRST** to `AgentScope` (where the bridge reads the live policy from) and **governance SECOND** to `AgentRegistry` (where downstream contracts read for governance attribution). The order is FROZEN by INV-OPERATOR-AGENT-001 — reversing it would create a window where the AgentRegistry shows authority before AgentScope has applied it, opening a TOCTOU-style attack surface. The ordering is verified at every ceremony fire by `scripts/parallel_zkba_anchor.py` Gate 4 (post-anchor FRR mismatch detection).

---

## 8. The seven ZKBA artifact classes (Layer 7 closed)

Phase O3-ZKBA-TRACK1 shipped the protocol's first composable artifact family: seven Zero-Knowledge Biometric Artifact (ZKBA) classes, each a structurally distinct projection of verified protocol state into a stakeholder-specific surface.

### 8.1 The ZKBAClass enum (FROZEN)

| Value | Class | Audience | Lane | Proof Weight | Composition depth | Commit |
|---|---|---|---|---|---|---|
| 1 | **AIT** | Operators | Sentry | CALIBRATION_PLUS_CONTEXT | 1 primitive (corpus statistics) | `bdbcf67f` |
| 2 | **GIC** | Operators | Sentry | CHAIN_ONLY | 1 primitive (chain head) | `3b3081d3` |
| 3 | **VHP** | Operators | Sentry | CHAIN_ONLY | 1 primitive (soulbound token state) | `4f399282` |
| 4 | **HARDWARE** | Manufacturers | Sentry | CHAIN_ONLY | 1 primitive (cert state) | `ece17f4f` |
| 5 | **CONSENT** | Gamers | Guardian | CHAIN_ONLY | 1 primitive (consent state) | `9bfa981e` |
| 6 | **TOURNAMENT** | Operators | Sentry | CHAIN_ONLY | 3 primitives (VHP + GIC + ProtocolLens) | `25e7f8f2` |
| 7 | **MARKET** | Buyers | Curator | MARKETPLACE_DERIVED | 2 primitives (LISTING + CONSENT) | `269e439c` |

The enum is FROZEN by INV-ZKBA-001 (function presence) + INV-ZKBA-002 (domain tag literal) + INV-ZKBA-003 (manifest schema literal). Reordering or renaming any class fails CI.

### 8.2 The Layer 7 7-of-7 closure invariant

Commit `ece17f4f` (2026-05-13) shipped the HARDWARE Participation Card, the seventh and final ZKBA artifact class. The test band `bridge/tests/test_phase_o3_zkba_hardware_card.py::test_t_zkba_hw_10_layer_7_seven_of_seven_closure` is the protocol's structural completeness gate: it iterates all 7 ZKBAClass values, computes a commitment for each over identical component bytes, and asserts that no two commitments collide. The non-collision proves the domain-tag byte in `compute_zkba_commitment` is load-bearing — if a future refactor accidentally drops the class byte from the preimage, the test fails.

This is the protocol's first formal "all seven artifact classes empirically composable through one pipeline" claim. Prior whitepaper drafts (v3, Phase 68–70) could only claim partial coverage.

### 8.3 The MANUFACTURER-bound artifact (architectural novelty)

The HARDWARE class is the protocol's **first manufacturer-attributable cryptographic artifact**. Prior six artifacts target gamer (CONSENT), operator (AIT/GIC/VHP/TOURNAMENT), or buyer (MARKET) audiences. The HARDWARE Participation Card binds the certifying manufacturer's 20-byte Ethereum address into the preimage as a publicly-attributable surface — the manufacturer address is **NOT hashed** (deliberate inverse of CONSENT v1's gamer-address hashing): hardware certification is publicly attributable by design.

The composition formula (FROZEN at v1):

```
SHA-256(
    profile_hash(32)          // keccak256(manufacturer || model || firmware)
    || device_id_hash(32)     // SHA-256(canonical device name)
    || cert_level_be(1)       // uint8 (1 = controller-only, 2 = controller+GSR)
    || manufacturer_addr(20)  // 20-byte Ethereum address, NOT hashed
    || is_certified_byte(1)   // 0x01 if active, 0x00 otherwise
) = 86-byte preimage → 32-byte commitment
```

The artifact opens a partnership-program surface: a hardware manufacturer (Sony partner program, GuliKit aftermarket TMR sticks, ZeroStick Pro modules, etc.) can present an on-chain artifact proving "this physical device, certified by us, produced VAPI-attested PoAC records under a certified profile." The 1000 VAPI `CERTIFICATION_FEE_VAPI` paid into `VAPIHardwareCertRegistry` becomes economically substantive when downstream artifacts cryptographically reference it.

---

## 9. The Verified Projection Media (VPM) output layer — Phase O4

Phase O3-ZKBA-TRACK1 produced seven cryptographic artifact classes as filesystem-only HTML in `frontend/src/artifacts/*/` (gitignored). Phase O4-VPM-INTEGRATION elevated those artifacts into a delivery surface with three-layer overclaim defense.

### 9.1 The compile pipeline

The protocol now exposes two parallel compiler entry-points in `scripts/vsd_ui_compiler.py`:

```python
compile_artifact(zkba_class, proof_weight, inputs, output_dir, html_renderer) → ZKBAManifest
    # Emits raw ZKBA artifact with manifest schema "vapi-zkba-manifest-v1"

compile_vpm_artifact(vpm_id, zkba_class, proof_weight, visual_state, capture_mode,
                    integrity_label, zkba_manifest_hash_hex, inputs, output_dir,
                    html_renderer) → VPMArtifactManifest
    # Emits VPM-wrapped artifact with manifest schema "vapi-vpm-artifact-v1"
    # PLUS post-render static guards (no external resources / no runtime network /
    # no randomness / no wall-clock / 9-field Integrity Label DOM enforced)
```

`compile_vpm_artifact` raises `VPMComplianceError` before writing to disk if the emitted HTML contains any of: `https?://`, `<link rel=>`, `<script src=>`, `@import`, `<iframe src=>`, `<img>` outside `data:` URIs, `@font-face`, `fetch()`, `XMLHttpRequest`, `new WebSocket(`, `new EventSource(`, `Math.random()`, `crypto.getRandomValues`, `Date.now()`, zero-arg `new Date()`, `performance.now()`. The static guards are pinned by INV-VPM-COMPILER-001 (function presence) and the per-pattern source lives in `_FORBIDDEN_HTML_PATTERNS` + `_FORBIDDEN_JS_PATTERNS`.

### 9.2 The six active VPM compilers

Phase O4 Streams A.1 + A.2 shipped six compilers. Each inherits the shared FROZEN 6-state visual grammar from `scripts/vpm_visual_grammar.py`:

| Compiler | Lane | ZKBA class | Proof weight | Lifecycle | Commit |
|---|---|---|---|---|---|
| HONESTY-BOARD-v1 | Sentry | GIC | CHAIN_ONLY | Test Fixture | `fd0d6699` |
| AGENT-REVIEW-v1 | Guardian | CONSENT | CHAIN_ONLY | Test Fixture | `fd0d6699` |
| CDRR-DAG-v1 (under HONESTY umbrella) | Sentry | HARDWARE | CHAIN_ONLY | Test Fixture | `fd0d6699` |
| GIC-LEDGER-BETA-v1 (under HONESTY umbrella) | Sentry | GIC | CHAIN_ONLY | Test Fixture | `fd0d6699` |
| DISPUTE-PACKET-v1 | Guardian | CONSENT | CHAIN_ONLY | Compiler Target | `7052144f` |
| MARKET-LISTING-v1 | Curator | MARKET | MARKETPLACE_DERIVED | Compiler Target | `7052144f` |

### 9.3 Procedural Geometric Art — VBDIP-0002 Market Card spec

The MARKET-LISTING-v1 compiler implements the protocol's first procedural visual fingerprint primitive. The FROZEN algorithm v1:

```
1. Parse zkba_manifest_hash_hex → 32 raw bytes.
2. Split into 8 four-byte chunks.
3. For each chunk (b0, b1, b2, b3):
     x_center      = 32 + (b0 & 0x7F)               // 32..159 in 192-wide viewBox
     y_center      = 32 + (b1 & 0x7F)               // 32..159 in 192-tall viewBox
     size_radius   = 12 + (b2 & 0x3F)               // 12..75
     hue_degrees   = (b3 * 360) // 256              // 0..359
     shape_kind    = (b0 XOR b3) & 0x03             // 0=triangle / 1=square /
                                                       2=pentagon / 3=hexagon
     rotation_deg  = ((b1 XOR b2) * 360) // 256     // 0..359
4. Render as inline SVG (192x192 viewBox; no xmlns attribute per HTML5
   inline-SVG namespace inheritance; preserves compiler discipline).
```

Cryptographic visual fingerprint property: collision resistance inherits from SHA-256. Every distinct ZKBA manifest produces a visually distinct artwork; same hash always produces byte-identical SVG. Test T-VPM-ML-ART-3 verifies per-byte sensitivity at three byte positions (0, 16, 31).

The buyer-facing implication: a marketplace catalog of cryptographically-distinct listings becomes visually scannable by a human at a glance, with the visual itself being independently verifiable from the underlying ZKBA manifest hash.

### 9.4 The three-layer Anti-Hype Visual Grammar — protocol UX defense

The visual grammar is enforced at three independent layers. Each layer catches a distinct failure mode:

**Layer 1 — Compile-time (Python).** `compile_vpm_artifact` static guards reject emitted HTML missing any of the six FROZEN visual-state DOM signatures. The compiler refuses to write the file. INV-VPM-COMPILER-001 + INV-VPM-INTEGRITY-LABEL-001 + INV-VPM-VISUAL-STATES-001 pin the enforcement.

**Layer 2 — Bridge-time (Python).** `scripts/vpm_audit.py` (a 6-section harness paralleling `zkba_post_ceremony_audit.py`) greps every active compiler's Python source for forbidden imports (`time.time`, `random`, `urllib`, `socket`); verifies every compiler imports the canonical grammar module; iterates the VBDIP-0002A §10 registry and checks each ID is at the expected lifecycle stage. Exposed at `GET /operator/vpm-audit-status` for operator-console polling.

**Layer 3 — Browser-time (JavaScript).** `frontend/src/components/VpmGrammarVerifier.jsx` reads `iframe.contentDocument.documentElement.outerHTML` after the VPM iframe loads, then runs the six FROZEN DOM signature assertions client-side. Failure surfaces as a **GRAMMAR FAIL** red badge in the Operator Console's VPM Registry tab. INV-VPM-SANDBOX-001 pins the FROZEN iframe attribute `sandbox="allow-scripts allow-same-origin"` — no expansion permitted.

The six FROZEN state-signature pairs (mirrored byte-for-byte across `scripts/vpm_visual_grammar.py:VISUAL_STATE_SIGNATURES` ↔ `frontend/src/components/VpmGrammarVerifier.jsx:VISUAL_STATE_SIGNATURES_FROZEN`):

| State | Required DOM substrings |
|---|---|
| `live` | `class="vpm-saturation-class"` + `data-vpm-visual-state="live"` |
| `dry-run` | `class="vpm-stripe-mask"` + `id="vpm-stripe-pattern"` + state marker |
| `emulated` | `class="vpm-body vpm-emulated"` + `filter: grayscale(100%)` + state marker |
| `frozen-disabled` | `class="vpm-lock-icon"` + state marker |
| `revoked` | `class="vpm-redacted-banner"` + `text-decoration: line-through` + state marker |
| `unverified` | `repeating-linear-gradient` + `#d65b78` + `#020408` + state marker |

Plus `<meta name="vpm-visual-state">` + `role="status"` aria block (§5.4 accessibility requirement) in every emitted HTML.

### 9.5 What this enforcement prevents

The Anti-Hype Visual Grammar is the protocol's first structural UX defense against three specific overclaim attacks:

1. **Demo-as-production overclaim.** A demo artifact compiled in dry-run mode that gets screenshot'd and posted to social media as "VAPI tournament eligibility proof." The stripe-mask + DRY-RUN watermark survive the screenshot; any third party can recompute the visual state by hashing the manifest dict and comparing to the rendered DOM signatures.
2. **Revoked-shown-as-active overclaim.** A consent that was revoked at time T but the VPM was compiled at T-Δ and cached. The revoked visual state checks consent status at iframe-render time via the manifest hash lookup, not at compile time, forcing line-through rendering.
3. **Unverified-shown-as-verified overclaim.** A VPM whose manifest hash doesn't match the served HTML (MITM tamper, browser extension rewrite, replay attack). The warning-band visual state fires immediately on the client-side Grammar Verifier without operator intervention.

This defense is the protocol's specific contribution to the "DePIN-photoshop-attack" threat model: cryptographically-distinct visual states surface as cryptographically-recoverable byte sequences, not just as visual flourishes.

### 9.6 The VPM Projection Registry — lifecycle ladder

Per VBDIP-0002A §10, the protocol reserves 10 VPM identifiers with a four-stage lifecycle ladder: Reserved → Draft Manifest → Compiler Target → Test Fixture → Active. After Phase O4 close, the registry state is:

| VPM ID | Audience | Lifecycle |
|---|---|---|
| HONESTY-BOARD-v1 | Ecosystem Partners | Test Fixture |
| AGENT-REVIEW-v1 | Governance / Deployer | Test Fixture |
| DISPUTE-PACKET-v1 | Referees / Ops | Compiler Target |
| MARKET-LISTING-v1 | Buyers / Curator | Compiler Target |
| PROOF-WALLET-v1 | Gamers | Draft Manifest |
| QR-ELIGIBILITY-v1 | Tournament Organizers | Draft Manifest |
| HARDWARE-LINEAGE-v1 | Manufacturers | Draft Manifest |
| CONSENT-CAPSULE-v1 | Gamers / Data Buyers | Draft Manifest |
| PROOF-TRAILER-v1 | Esports Viewers | Reserved |
| DEV-SANDBOX-v1 | Developers | Reserved |

Eight of ten IDs are now at an active lifecycle stage. PROOF-TRAILER-v1 and DEV-SANDBOX-v1 remain Reserved pending broadcast partnership (esports tournament integration) and SDK 4.x stabilization, respectively.

---

## 10. The PV-CI invariant gate + governance discipline

The protocol's source-code-region integrity is enforced by a Persistent-Validation Continuous-Integration (PV-CI) gate. As of Phase O4 close, the gate pins **77 invariants** (66 protocol + 11 VPM family).

### 10.1 Mechanics

`scripts/vapi_invariant_gate.py` maintains a list of `Invariant(id, description, file, pattern, min_matches)` entries. For each invariant, the gate:

1. Reads the file
2. Greps for the regex pattern
3. Computes a SHA-256 digest of the matching lines (with line numbers stripped)
4. Compares the digest against `.github/INVARIANTS_ALLOWLIST.json`
5. Fails CI on any DIGEST DRIFT (digest mismatch on a previously-pinned invariant)

The 77 invariants span eight namespaces:

| Namespace | Count | Coverage |
|---|---|---|
| `INV-NNN` (legacy protocol) | 16 | Phase 1..Phase 224 protocol pins (wire format / chain hash / cheat codes / ZK circuit / etc.) |
| `INV-PCC-NNN` | 4 | L4 threshold + PCC SPC classifier |
| `INV-APOP-NNN` | 2 | Phase 241 Active Play Occupancy primitives |
| `INV-GIC-NNN` | 3 | Phase 235-A Grind Integrity Chain |
| `INV-CORPUS-NNN` | 2 | Phase 237.5 CORPUS-SNAPSHOT |
| `INV-OPERATOR-AGENT-NNN` | 8 | Phase O0 + O1 operator initiative |
| `INV-CEDAR-NNN` | 3 | Cedar v2 parser + bundle schema |
| `INV-ZKBA-NNN` | 3 | PATTERN-017 ZKBA primitive |
| `INV-VPM-*` | 11 | Phase O4 VPM family (compiler / schema / Integrity Label / visual states / capture modes / wrapper ref / CSP / sandbox / endpoint / audit) |
| `INV-O1-FRR-NNN` | 5 | Fleet Readiness Root + SDK |
| `INV-O3-WATCHER-NNN` | 3 | O3 readiness watcher gates |
| `INV-O3-UI-DRAWER-NNN` | 3 | Operator console layer ordering |
| `INV-PARALLEL-ANCHOR-NNN` | 1 | Triple-gate anchor script discipline |
| `INV-CURATOR-O2-NNN` | 2 | Curator O2_SUGGEST bundle metadata |
| `VBD-INV-NNN` | 3 | VBDIP-0001 VAD methodology (markdown-normative) |

Plus three VBD invariants under the separate `VBD_INVARIANTS` registry (currently markdown-normative per VBDIP-0001 §9; programmatic enforcement deferred to VBDIP-0003).

### 10.2 The governance ceremony

Modifying a pinned region requires a typed ceremony:

```bash
python scripts/vapi_invariant_gate.py --generate \
  --reason "invariant_change: <140-char description>" \
  --confirm-governance
# Prompts: "Type confirmation phrase: "
# Required input: "I understand this changes a frozen protocol invariant"
```

The phrase is checked verbatim; mismatch exits with code 3 and no allowlist regeneration. The successful path regenerates the allowlist + (if bridge is live) POSTs a governance event to `/agent/allowlist-governance-event` for on-chain logging.

Reason categories are a FROZEN closed enum: `refactor` / `bugfix` / `invariant_change` / `ceremony_update`. The `invariant_change` category specifically requires the `--confirm-governance` ceremony; other categories regenerate the allowlist without the phrase requirement.

This discipline encodes the protocol's structural posture: **load-bearing source regions are part of the protocol authority surface alongside FROZEN methodology documents, on-chain governance events, manifests, and governance ceremonies — and PV-CI makes changes to those regions tamper-evident before merge.** PV-CI does not override governance; it complements it.

### 10.3 The VBDIP architectural framework

VBDIP-0001 (VAD: Verified Architectural Discipline) is the FROZEN methodology anchor (`wiki/methodology/VBDIP-0001-vad-framework-introduction.md`). It establishes three sub-disciplines:

- **VSD (Verified Synthesis Discipline)** — methodology for combining multiple primitives into composite artifacts
- **VED (Verified Engineering Discipline)** — retrospective methodology over existing PV-CI invariants
- **VBD (Verified Bridge Discipline)** — methodology for cross-fleet bridge composition

VBDIP-0002 (`wiki/methodology/VBDIP-0002-zkba-visual-projections.md`) v1.2 with Appendix B + Appendix C is the FROZEN spec for the ZKBA artifact family + the VPM compiler discipline. v1.2 codifies bilateral schema-name acceptance (Option C resolution): the canonical implementation schema name `vapi-zkba-manifest-v1` (pinned by INV-ZKBA-003) is the production identifier; the §9.2 spec design-time name `zkba.projection_manifest.v1` is recognized for legacy/third-party manifest validation. The G4 validator's `schema_name_form` field surfaces the drift back to consumers without forcing a v2 migration.

---

## 11. FSCA — Fleet Signal Coherence Agent

`bridge/vapi_bridge/fleet_signal_coherence_agent.py` runs a periodic (15-minute) poll across the 38-agent fleet's emitted state, evaluating each row against 26 contradiction rules + a set of orphan-detection + inversion-detection rules. The agent's role is cross-system coherence verification, not direct enforcement.

As of Phase O4 close, the 26 CONTRADICTION_RULES include:

| Severity | Count | Examples |
|---|---|---|
| CRITICAL | 4 | CONSENT_REVOKED_LISTING_ACTIVE (GDPR Art. 17), ALLOWLIST_CHANGE_WITHOUT_GOVERNANCE |
| HIGH | 15 | ZKBA_PROOF_WEIGHT_MISMATCH, BUNDLE_HASH_DRIFT_DETECTED, INVARIANT_CHANGE_WITHOUT_VHP, VPM_VISUAL_STATE_DOM_MISMATCH, VPM_MANIFEST_HASH_DRIFT |
| MEDIUM | 6 | DRAFT_UNREVIEWED_72H, DEFENSIBILITY_N_MISMATCH, VPM_LIFECYCLE_REGRESSION |
| LOW | 1 | — |

The three Phase O4-added VPM rules:

- **VPM_VISUAL_STATE_DOM_MISMATCH** (HIGH) — VPM rows in `vpm_artifact_log` with `manifest_uri` populated but `compiler_output_hash_hex` NULL (incomplete compile path)
- **VPM_MANIFEST_HASH_DRIFT** (HIGH) — VPM rows whose declared `zkba_manifest_hash_hex` doesn't join to any `commitment_hex` in `zkba_artifact_log` (forged wrapper or upstream drift)
- **VPM_LIFECYCLE_REGRESSION** (MEDIUM) — Compiler Target VPM IDs with zero recent compiles in 30-day trailing window (stagnation observation, not security event)

When FSCA detects a contradiction, it emits a `fleet_coherence_log` row with severity + rule_name + agents_involved + explanation + resolution. The Operator Console DraftReviewDrawer surfaces unresolved findings. The agent does not directly remediate; remediation requires operator action through the appropriate skill or endpoint.

The 4-rule INVERSION category (Phase 193) detects Provenance DAG timestamp anomalies (child node registered before parent). The 7-rule ORPHAN category (Phase 217) detects unresolved blocker-pair entries.

---

## 12. The PoAC → tournament-gate composability — protocol's headline claim

The protocol's structural claim — that an external tournament organizer can implement gating with two lines of Solidity — is realized through `VAPIProtocolLens.isFullyEligible(deviceIdHash)`. This is the protocol's single composable gate.

The implication for the broader DePIN ecosystem: the protocol does not require integration partners to run any VAPI-specific software. They run their existing tournament platform; they query a single view call before allowing entry. The cryptographic verification work happens entirely behind the gate; the partner's surface area is a single boolean.

The view call composes (per Phase 108 + Phase 178 + Phase 197):

1. PHG credential exists and has not expired (90-day TTL per BP-001)
2. No active BLOCK ruling in `RulingRegistry`
3. No active suspension (24h default, 7d on warmup_attack_score > 0.7)
4. Biometric credential age < `biometric_credential_ttl_days` (90.0)
5. `all_pairs_p0_ok` from `separation_defensibility_log` (currently CLEARED for AIT)

External callers see only the boolean return; the internal composition is observable but not load-bearing on the gate's correctness from the caller's perspective.

---

## 13. The DePIN data marketplace (Phase 99 + Phase 238)

VAPI's token economic model is utility, not speculation. The flywheel:

```
Certified controllers (paid VAPI cert fee)
    ↓
PoAC records emitted at 1000 Hz with hardware-rooted ECDSA-P256 signatures
    ↓
ZKBA artifacts wrap verified state into 7 audience-specific projections
    ↓
VAPIDataMarketplaceListings (Phase 238 Step H, address 0x78Df84Cc...)
exposes verified physiological data with consent gating
    ↓
Data buyers acquire under tiered consent-gated pricing
    ↓
70% device pool (gamer rewards) / 30% treasury
    ↓
Gamers earn VAPI for clean grind sessions
    ↓
More controllers + more grind sessions + higher corpus quality
```

The economic anchor: each LISTING-v1 primitive output references a Phase 237 CONSENT v1 commitment (`consent_hash`) cryptographically, with the MARKETPLACE consent bit (bit 3 of 4-bit category bitmask) enforced at listing creation. A buyer cannot acquire data from a gamer whose marketplace consent is revoked — the cryptographic chain refuses to compile a listing artifact referencing a revoked consent state.

Phase 238 added the Curator-lane authority surface: Curator reviews + verdicts (APPROVED / FLAGGED_TIER_MISMATCH / FLAGGED_ANCHOR_STALE / FLAGGED_CONSENT_AMBIGUOUS / FLAGGED_IPFS_UNAVAILABLE / REJECTED_NO_ANCHORS / REJECTED_INVALID_COMMITMENT) become the marketplace's first-line audit surface. Listing tier multipliers (1.0x / 1.5x / 2.0x / 3.0x) are computed cryptographically from AdjudicationRegistry state (`isRecorded(poadHash)`) — sellers cannot self-attest tier; the multiplier is derived from on-chain adjudication evidence.

The VAPI token (Phase 99A; not yet TGE'd) has a fixed 1 billion max supply distributed:

- 30% operator staking (MINIMUM_STAKE 10k VAPI; 30-day deregister cooldown; slash 50% burned + 50% to claimant)
- 25% device rewards (gamer earnings from grind sessions)
- 20% ecosystem
- 15% team (4-year vest)
- 10% liquidity

The TGE invariant is unambiguous: no token launch before separation_ratio > 1.0 empirically confirmed AND all_pairs_above_1=True. AIT clears the technical gate; touchpad_corners closure remains the operator's call.

---

## 14. Current calibration state — honest

The protocol has open calibration gates. They are documented because the protocol's discipline requires honesty about open work.

### 14.1 Tournament gate (separation primitive)

| Battery | Ratio | N | `all_pairs_above_1` | `all_pairs_p0_ok` | Tournament BLOCK enforcement |
|---|---|---|---|---|---|
| AIT | 1.199 | 37 | True | True | **CLEARED** for testnet/demonstration |
| touchpad_corners | 0.728 | 35 | False | False | **BLOCKER** for actual tournament BLOCK |
| tremor_resting | 1.177 | 27 | False | False (P1vP3=0.032; Phase 213 fix shipped, verification pending) | Open |
| pooled (free-form) | 0.417 | 127 | False | False | Plateau regime; superseded by AIT |

The AIT battery is the protocol's structured-probe breakthrough (Phase 229–231). The touchpad_corners battery has hit a discriminative ceiling for the P2/P3 player pair at the current corpus size; further sessions of this probe type will not cross 1.0 without protocol-level changes (per-player touchpad eigenspace gating is a candidate Phase 140 deliverable). The tremor_resting battery's open issue (P1vP3=0.032) is hypothesized to be FFT bin aliasing at the 0.977 Hz/bin resolution of the original 1024-point FFT; the Phase 213 fix (4096-point zero-padded FFT + parabolic peak interpolation, 0.244 Hz/bin) shipped but verification awaits the next corpus expansion cycle.

### 14.2 PITL layer calibration gates

| Layer | Required N | Current N | Gate state |
|---|---|---|---|
| L6 active haptic challenge | 50 | 0 | `L6_CHALLENGES_ENABLED=false` held |
| L6b neuromuscular reflex | 50 | 0 | `L6B_ENABLED=false` held |
| L7-GSR | 30/player | 0 | `GSR_ENABLED=false` held |
| L8-BT transport | 30/player | 0 | `bt_transport_enabled=false` held |

All four are gated by calibration corpus expansion work. None is a security issue; all are structurally honest invariants ("you cannot enable a layer without the calibration to make its detection meaningful").

### 14.3 Operator Initiative lifecycle gates

All three Operator Initiative agents (Sentry / Guardian / Curator) are at lifecycle **O1_SHADOW**. Advancement to O2_SUGGEST requires:

- shadow_age ≥ 504h (≈21 days; cumulative observation window per agent)
- N ≥ 100 Cedar evaluations
- Bundle/scope drift findings = 0 over 30-day trailing window

Advancement to O3_ACT additionally requires:

- N ≥ 50 drafts per agent
- Operator disagreement rate < 5% per agent
- Curator-specific: false-positive rate = 0% (ZERO TOLERANCE per Phase O3-ACT-WATCHER)
- Operator dual-key + KMS HSM production-ready flags (Sentry+Guardian only)
- GitHub App OAuth tokens valid (Guardian only)
- `setCurator()` role assigned on `VAPIDataMarketplaceListings` (Curator only)

VBDIP-0002 Appendix B §B.8 gate **G7 (Curator Review Readiness)** is the only B.8 sub-gate that remains OPEN at Phase O4 close — operator-runtime observation work, not a development deliverable.

---

## 15. What remains to be engineered

The forward roadmap distilled from Phase O4 close. Ten tiers, priority + dependency order:

1. **G7 Curator Review Readiness** — operator-runtime 7-day observation window with ≥9/10 acceptance gate. Not development work; operator action.
2. **Touchpad_corners corpus expansion** — capture sessions to close the per-pair P3 separation issue. Hardware-required.
3. **VPM Active lifecycle promotion** — promote four Draft Manifest IDs (PROOF-WALLET / QR-ELIGIBILITY / HARDWARE-LINEAGE / CONSENT-CAPSULE) to Active. Each requires external-stakeholder governance + partnership flow.
4. **VPMAnchorRegistry.sol** — on-chain anchor registry for VPM artifacts, parallel to AdjudicationRegistry. Track-2-style ceremony required; ~0.1 IOTX per anchor.
5. **Curator O1 → O2_SUGGEST graduation** — pre-authored bundle Merkle `0xeb400a5c...` is ready; gated by N≥50 reviews + 0 false-positive rate.
6. **W3bstream applet registration** — replace placeholder selector `0xCAFE0237` with real binding to `VAPIConsentRegistry.isConsentValid()`. ~0.02 IOTX off-chain.
7. **LayerZero VHP cross-chain bridge** — `VAPIVerifiedHumanProofBridge` testnet → mainnet activation. Phase 99C deliverable.
8. **Realms migration** — when daily PoAC volume ≥ 100,000/day. All Phase 99+ contracts use `TransparentUpgradeableProxy` for Realm migration readiness.
9. **BT transport calibration** — N=0 → N≥30/player MVCP (Minimum Viable Calibration Protocol). Separate workstream; gated by hardware availability.
10. **Sensor Stack v2** — Stage A pre-corpus measurements (Empirical Unknown #1 trigger-pull intra/inter-player Mahalanobis + Empirical Unknown #4 Hall-effect stick same-batch separability) + Stage B implementation per `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`.

The 10 tiers are not mutually exclusive; some (e.g., #2 + #6 + #9) can proceed in parallel. Token launch (Phase 99 TGE) remains gated by the separation invariant; closing tier #2 unblocks the TGE consideration window.

---

## 16. What is architecturally exclusive to VAPI

After Phase O4 close, VAPI's reference implementation introduces the following architectural positions. Each item is enforced in source code today and is independently verifiable against the repository at architecture anchor `e81e04aa`; the "exclusivity" claim is bounded to the protocol-architectural specifics enumerated in each row, not to broader market comparisons.

| Exclusivity | What it is | Why no competitor has it |
|---|---|---|
| **Frozen-primitive ↔ frozen-compiler ↔ frozen-visual-grammar ↔ frozen-iframe-sandbox quadruple-bind** | PATTERN-017 cryptographic primitive family + deterministic content-addressed compiler + FROZEN 6-state DOM signature matrix + FROZEN browser-iframe sandbox literal, all enforced in CI | Requires (a) FROZEN-v1 primitive discipline, (b) deterministic compiler, (c) on-chain-anchored Cedar lane authority over WHO may compile, (d) sandboxed delivery surface with byte-asserted DOM signatures — no other protocol stacks all four |
| **Three-layer Anti-Hype Visual Grammar** | Compile-time static guards + bridge-time source audit + browser-time DOM verifier | The "DePIN-photoshop-attack" defense is structural, not aspirational |
| **Procedural Geometric Art as cryptographic visual fingerprint** | Per-byte sensitivity of rendered SVG inherits from SHA-256 | Buyers scan marketplace catalogs visually; each listing is cryptographically distinct |
| **CDRR DAG composition-lattice projection** | The 7-class ZKBA composition lattice rendered as inline SVG with per-node CFSS lane attribution | No other DePIN has a frozen-primitive composition lattice at this depth to project |
| **Nine-layer PITL stack + Layer 7 Methodology** | The Methodology Layer is a peer architectural layer (not docs) with PV-CI gating + architect Ed25519 signing chain + operational reach across all 3 agent lanes | Most protocols treat methodology as a wiki; VAPI treats it as code-frozen + chain-anchored |
| **Three-agent CFSS triangle at Cedar policy level** | Sentry / Guardian / Curator with cross-fleet skill separation invariant enforced via three distinct dual-anchored Cedar bundles | Most agent fleets are 1–2 agents with shared authority; VAPI's three-agent triangle is structural |
| **Manufacturer-bound audience artifact** (HARDWARE Participation Card; protocol's first manufacturer-audience class) | Cryptographic commitment binds the certifying manufacturer's on-chain address as a publicly-attributable surface, alongside CONSENT (gamer-audience), AIT/GIC/VHP/TOURNAMENT (operator-audience), and MARKET (buyer-audience) | Requires `VAPIHardwareCertRegistry` + PATTERN-017 + per-audience Cedar lane composition |
| **PV-CI invariant gate at PR time** | 77 byte-digest pins of load-bearing source-code regions; modification fails CI | Most protocols enforce conventions in review; VAPI enforces them in CI |
| **GIC_100 permanently-anchored cognitive chain** | 100-link cryptographic chain of grind sessions, head hash `0x0e9d453d...` anchored on IoTeX testnet | The chain head plus the WEC operational-continuity chain together produce tamper-evident provenance for a 100-session grind run |
| **Operator console with cryptographic media inspection surface** | VPM Registry tab + sandboxed iframe + Layer 3 grammar verifier | The protocol's outputs are inspectable by the operator without leaving the dashboard; each VPM iframe runs Web Crypto SHA-256 + the FROZEN 6-state DOM grammar verifier client-side |
| **Wallet-free + chain-write-paused operating posture** | `CHAIN_SUBMISSION_PAUSED=true` held; 22 audited submission paths gated; operator three-factor authorization required to lift | Most protocols default to chain-write-enabled and rely on signing key separation; VAPI defaults to denied |
| **Architect Ed25519 signing chain anchored to bridge wallet via EIP-191** | Every methodology document inherits trust from one attestation | No competing protocol has formal methodology-layer cryptographic signing |

---

## 17. Citation, acknowledgments, license

### Citation

Until a Zenodo DOI is minted for v4, cite the historical v3 plus reference this file at the architecture anchor commit `e81e04aa` (documentation revamp commit `9f8581cd`):

```bibtex
@software{battle_2026_vapi_v3,
  author    = {Battle, Contravious},
  title     = {VAPI: Verifiable Controller Input Provenance with
               Physics-Backed Liveness for Competitive Gaming},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.18966169},
  url       = {https://doi.org/10.5281/zenodo.18966169},
  version   = {v3 (historical; superseded by v4 in-repo)},
  note      = {v4 in-repo: docs/vapi-whitepaper-v4.md at architecture
               anchor commit e81e04aa (Phase O4-VPM-INTEGRATION close,
               2026-05-13; documentation revamp commit 9f8581cd). v4 DOI
               assignment pending Zenodo release.}
}
```

### Acknowledgments

The protocol's calibration corpus was contributed by three anonymous players (P1, P2, P3) over the period February 2026 to May 2026 via the hardware calibration watcher pipeline. The IoTeX testnet RPC infrastructure made all on-chain ceremony work possible. The Cedar policy framework (originally from AWS, open-sourced) is the lane authority substrate for the Operator Initiative fleet.

### License

**Copyright © 2026 Contravious Battle. All Rights Reserved.**

This whitepaper, the repository at `vapi-pebble-prototype` (architecture anchor commit `e81e04aa`, documentation revamp commit `9f8581cd`), and all derivative work is the proprietary intellectual property of the author. Source is available for inspection, research review, and security audit. No open-source license is declared. Commercial integration, derivative work, or redistribution requires an explicit license agreement with the author.

Patent claims and academic citation: reference the Zenodo DOI above (v3) plus the in-repo `docs/vapi-whitepaper-v4.md` for current-state citations. The v4 successor DOI will be assigned at Zenodo release.

---

## Appendix A — Test count progression + Phase O4 commit roster

### Test counts at phase boundaries

| Phase | Bridge | SDK | Hardhat | PV-CI | Contracts LIVE |
|---|---|---|---|---|---|
| Phase 41 (v3 README baseline) | 874 | — | 354 | — | 13 |
| Phase 68–70 (v3 whitepaper baseline) | 1207 | 63 | 396 | — | 23 |
| Phase 99C (AGaaS layer) | 1392 | 87 | 430 | — | 30 |
| Phase 235 GRIND LIVE | ~2447 | 521 | 502 | 36 | 45 |
| Phase 238 Step I-FINAL (Curator LIVE) | 2779 | 539 | 528 | 49 | 49 |
| Phase O3-ZKBA-TRACK1 close (Layer 7 7-of-7) | 3160 | 562 | 528 | 67 | 49 |
| **Phase O4-VPM-INT close (this whitepaper anchor)** | **3344** | **562** | **528** | **77** | **49** substantive live (51 registry slots) |

### Phase O4 commit roster (10 commits)

```
e81e04aa  phase O4-VPM-INT close: PV-CI 77 + FSCA 26 + B.8 gate sweep + CLAUDE.md NOTE + provenance pin
0061e6d9  phase O4-VPM-INT C: VPM Registry tab + sandboxed iframe + Layer 3 grammar verifier
d5803d47  phase O4-VPM-INT B.4-B.7: VPM write + validate + audit endpoints + stability harness
1b13618d  phase O4-VPM-INT B.0-B.3: VPM store schema + 3 read endpoints
169471bb  phase O4-VPM-INT A.3 + A.4: 4 draft manifests + vpm_audit tooling
7052144f  phase O4-VPM-INT A.2: 2 consumer-facing VPM compilers + procedural geometric art
fd0d6699  phase O4-VPM-INT A.1: 4 internal VPM compilers + Anti-Hype Visual Grammar
524ae1cc  phase O4-VPM-INT A.0: compiler engine extension + T-VPM-COMPILER-1..10
603c98cb  docs(phase-o4): pre-execution V-check provenance pin 2026-05-13
168256a0  feat(observability): Layer 7 coverage audit + 7-of-7 closure doc
```

Plus the Phase O3 anchor commit immediately preceding Phase O4:

```
ece17f4f  phase O3-ZKBA-TRACK1 Track 2 follow-up: 7th (final) ZKBA artifact — Hardware Participation Card
```

---

## Appendix B — Glossary

**AdjudicationRegistry** — On-chain registry of adjudication records (PoAd hashes); Phase 111; address `0x44CF981f46a52ADE56476Ce894255954a7776fb4`.

**AGaaS (Anti-cheat as a Service)** — VAPI's delivery model for tournament operators and esports platforms: cryptographic human-gameplay verification consumed via the single `isFullyEligible()` on-chain gate. The Operator Initiative fleet (Sentry / Guardian / Curator) provides agentic protocol stewardship as a separate concern; AGaaS specifically refers to the anti-cheat / verified-human-gameplay service layer integrators consume.

**AIT (Active Isometric Trigger)** — Phase 229 calibration battery. Player holds L2 trigger at 50% for 30 seconds; tremor + gravity fingerprint extracted. Achieved ratio 1.199 N=37 with all_pairs_above_1=True — the protocol's tournament-gate breakthrough.

**Anti-Hype Visual Grammar** — Phase O4 enforcement of FROZEN 6-state DOM signatures across compile / bridge / browser layers. Protocol's first structural UX defense.

**APOP (Active Play Occupancy Proof)** — Phase 241 5-state controller-native classifier replacing Phase 235-GAD's binary trigger-onset gate. Hybrid + shadow + strict gate modes.

**Bridge wallet** — `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`. Operator-funded source of all on-chain ceremony work. ~15.03 IOTX as of Phase O4 close.

**CDRR DAG** — Cross-Domain Reasoning Record Directed Acyclic Graph. Phase O4 Stream A.1.c VPM projection of the 7-class composition lattice as inline SVG (7 nodes + 5 composition edges).

**Cedar v2** — The policy framework anchoring three-agent lane authority. Bundles dual-anchored on AgentScope (operational FIRST) + AgentRegistry (governance SECOND) 2026-05-12.

**CFSS (Cross-Fleet Skill Separation)** — The protocol's three-agent governance separation invariant. Each agent (Sentry / Guardian / Curator) has exclusive write authority over its lane; Cedar policies on other agents FORBID cross-lane action.

**CORPUS-SNAPSHOT v1** — Phase 237.5 cryptographic primitive. Anchors hash commitment of wiki/ + agent fleet Merkle root + AIT separation ratio + N. Inaugural anchor 2026-05-09 tx `0x24e4ddb6...`.

**FSCA (Fleet Signal Coherence Agent)** — Phase 193 cross-system coherence verification agent. Runs 26 CONTRADICTION rules + ORPHAN + INVERSION rules on 15-minute poll cadence.

**GIC (Grind Integrity Chain)** — Phase 235-A cryptographic primitive. Per-session cognitive-integrity chain. GIC_100 milestone anchored on chain 2026-05-06.

**Operator Initiative** — The three-agent autonomous governance fleet: Sentry (artifact anchoring), Guardian (audit trail), Curator (marketplace). All at O1_SHADOW lifecycle at Phase O4 close.

**PATTERN-017** — The 10-element FROZEN-v1 cryptographic primitive family. Single source of truth for the protocol's commitment compositions.

**PHG (Proof of Humanity Gating)** — Phase 99C ERC-4671 soulbound credential. 90-day TTL; minted when L4 / L5 / L2B / L2C all agree.

**PoAC (Proof of Autonomous Cognition)** — The 228-byte cryptographic record. FROZEN wire format; INV-001 + INV-002 pinned.

**PoAd (Proof of Adjudication)** — Phase 111 second composable primitive. Hash of sorted verdicts + quorum + ts_ns; anchored in AdjudicationRegistry.

**PV-CI (Persistent-Validation Continuous-Integration)** — The protocol's source-code-region integrity gate. 77 invariants at Phase O4 close.

**VAD (Verified Architectural Discipline)** — VBDIP-0001 FROZEN methodology framework. Three sub-disciplines: VSD / VED / VBD.

**VAME (VAPI Application-Layer Message Envelope)** — Phase 236-VAME cryptographic primitive. Sidecar response headers binding GIC chain head into HTTP responses.

**VBDIP (VAPI Bridge Design Improvement Proposal)** — Methodology proposal format. VBDIP-0001 (VAD framework FROZEN); VBDIP-0002 (ZKBA spec, v1.2 with Appendix B); VBDIP-0002A (VPM sidecar, partially absorbed).

**VHP (Verified Human Proof)** — Phase 99C ERC-4671 soulbound humanity credential. tokenId=2 demo mint live on testnet.

**VPM (Verified Projection Media)** — Phase O4 output-layer wrapper. Compiler discipline + manifest schema `vapi-vpm-artifact-v1` + 6-state Anti-Hype Visual Grammar + sandboxed iframe delivery.

**WEC (Watchdog Event Chain)** — Phase 236-WATCHDOG operational-continuity chain. Pairs with GIC for full grind-run provenance.

**ZKBA (Zero-Knowledge Biometric Artifact)** — Phase O3-ZKBA-TRACK1 artifact family. 7-class enum (AIT / GIC / VHP / HARDWARE / CONSENT / TOURNAMENT / MARKET). Layer 7 closed at commit `ece17f4f`.

---

*— VAPI Principal Architect, 2026-05-13. Anchor commit `e81e04aa`.*
