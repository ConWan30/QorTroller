# QorTroller — Core Controllers of their gaming data

## A Reference Implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.) on IoTeX

### Whitepaper v5 — Brand-Layer Reframing of v4

**Author:** Contravious Battle (Independent Researcher)
**Project:** QorTroller (the reference implementation)
**Category:** Verifiable Autonomous Physical Intelligence (V.A.P.I.) — a coined Decentralized Physical Infrastructure (DePIN) sub-category
**Network:** IoTeX testnet (chain ID 4690)
**Architecture anchor commit:** `e81e04aa` (Phase O4-VPM-INTEGRATION close, 2026-05-13)
**Brand-lock commit:** `2c762835` (QRESCE-0001 v0.5, 2026-05-18)
**Supersedes:** v4 (`docs/vapi-whitepaper-v4.md`, brand-layer; technical content preserved unchanged)
**License:** Copyright © 2026 Contravious Battle. All Rights Reserved.

---

## Abstract

**QorTroller** is the reference implementation of **Verifiable Autonomous Physical Intelligence (V.A.P.I.)** — a coined Decentralized Physical Infrastructure (DePIN) sub-category for protocols where the **physical-input source is also the cryptographic agency-holder** over the data those physical interactions generate. In QorTroller's case: gamers and their controllers, producing data, owning that data, attesting to its provenance without surrendering sovereignty.

Built native to IoTeX's Internet of Trusted Things foundation. Anchored on IoTeX L1. Composable as a single on-chain call. Designed so cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty.

Each controller input event produces a 228-byte Proof of Autonomous Cognition (PoAC) record binding raw sensor commitments (IMU dynamics, analog trigger dynamics, stick/button timing, biometric feature commitments) to a hardware-rooted ECDSA-P256 signature and a SHA-256 hash-chained sequence anchored on the IoTeX EVM. A nine-level Physical Input Trust (PITL) stack interprets each record through layered detectors — from hardware presence (L0) to active haptic challenge-response (L6) — and exposes the resulting per-session eligibility through a single composable on-chain view call, `VAPIProtocolLens.isFullyEligible(deviceIdHash)`. The on-chain gate minimizes integrator trust by reducing eligibility to a public view call over previously anchored protocol state; integrators do not need to operate a private publisher API or inspect raw biometric data themselves.

As of Phase O4-VPM-INTEGRATION close (2026-05-13), the protocol comprises 49 substantive live smart contracts on IoTeX testnet (51 contract registry slots), a 38-agent bridge runtime fleet including three on-chain registered Operator Initiative agents, PV-CI invariants pinning load-bearing source-code regions at PR time, FSCA contradiction rules, a family of FROZEN-v1 cryptographic primitives (PATTERN-017), seven shipped Zero-Knowledge Biometric Artifact (ZKBA) classes composing through one deterministic compiler pipeline, six active Verified Projection Media (VPM) compilers under a three-layer Anti-Hype Visual Grammar discipline, and a three-agent Operator Initiative fleet (Sentry, Guardian, Curator) at lifecycle O1_SHADOW with Cedar v2 lane authority bundles dual-anchored on AgentScope + AgentRegistry.

The protocol's headline tournament gate — inter-person separation ratio > 1.0 with all-pairs separability — is empirically cleared for the Active Isometric Trigger (AIT) calibration battery at ratio 1.199 with N=37 sessions (Phase 229–231 breakthrough), sufficient as AIT-based testnet/demo eligibility evidence in the current corpus. The touchpad_corners battery remains an open blocker at ratio 0.728 for actual tournament BLOCK enforcement; corpus expansion work continues. The token launch invariant ("no Token Generation Event before separation_ratio > 1.0 confirmed and all_pairs_above_1=True") remains in force for legal/economic defensibility.

This whitepaper supersedes v4 at the **brand-layer** only. v4's technical content stands unchanged. The 879-line technical architecture documented in v4 is preserved in `docs/vapi-whitepaper-v4.md` and remains the authoritative source for protocol details. This v5 document reframes the project identity (QorTroller) and category (V.A.P.I.) at the front-matter without re-deriving the technical substrate.

The architectural contribution claimed: QorTroller's reference implementation simultaneously pins (1) the FROZEN-v1 V.A.P.I. primitive family, (2) the deterministic content-addressed compiler, (3) the FROZEN six-state visual grammar enforced at three independent runtime layers, and (4) the FROZEN browser-iframe sandbox attribute. Together these four enforcement surfaces form a quadruple-bind around the protocol's emitted cryptographic claims. Each emitted claim is independently verifiable by anyone with the canonical-JSON algorithm + SHA-256 + the public source of the four enforcement layers.

---

## 1. The Category — Verifiable Autonomous Physical Intelligence (V.A.P.I.)

### 1.1 What V.A.P.I. names

Verifiable Autonomous Physical Intelligence (V.A.P.I.) is a coined Decentralized Physical Infrastructure (DePIN) sub-category. It describes protocols meeting four criteria:

1. **Physical-input source**: the protocol observes data produced by a physical interaction (gamepad button press, GSR electrode reading, IMU tremor signature, etc.) — not synthetic / simulated / network-only data.

2. **Cryptographic verifiability**: every observation is bound at capture-time to a tamper-evident cryptographic commitment (signature, hash chain, ZK proof, on-chain anchor) such that any third party with the public algorithms can independently verify the observation's authenticity.

3. **Autonomous attestation**: the protocol's verification surface does NOT require trusting a centralized operator. The cryptographic primitives + public verifier code suffice. Operators may run infrastructure; they cannot forge the attestations.

4. **Agency-holder identity**: the physical-input source IS also the cryptographic agency-holder over the data those physical interactions generate. The human producing the input owns the credentials that attest to it, grants per-category consent for downstream use, and retains the right to revoke / be-forgotten.

The fourth criterion is the load-bearing one. It distinguishes V.A.P.I. from generic anti-cheat (where the platform owns the data), from generic biometric capture (where the capture-vendor owns the data), and from generic DePIN (where the device-operator owns the data). V.A.P.I. inverts these ownership patterns: the human-as-input-source owns the data they produce.

### 1.2 Why V.A.P.I. is a distinct DePIN sub-category

IoTeX's Internet of Trusted Things thesis frames DePIN as decentralized infrastructure for trustworthy physical-world data. Within that thesis, multiple specializations exist:

- **Sensor-network DePIN** (Helium, etc.): physical sensors deployed in the field; the sensor-operator earns rewards for valid data submission. The sensor data subject (e.g., RF spectrum) has no agency.
- **Hardware-attestation DePIN** (IoTeX ioID itself): physical devices register on-chain via hardware-rooted identity. The device owns the attestation; the human user of the device has no direct cryptographic role.
- **Verifiable-compute DePIN** (W3bstream applets, etc.): off-chain compute produces verifiable output bound to on-chain state. The computation is the subject, not the human.

**V.A.P.I. fills the gap where the HUMAN is the data subject AND the cryptographic agency-holder.** This requires:

- Capture infrastructure (controller / sensor) hardware-rooted to detect that a real human produced the input
- Per-event cryptographic commitments preserving forensic auditability of every input
- Per-category consent primitives where the human grants / revokes downstream use
- Right-to-be-forgotten enforcement via on-chain revocation observable in real-time by all consumers
- Cross-chain composability so attestations can be verified by parties outside the originating chain

QorTroller implements all five for the competitive-gaming domain. Future V.A.P.I.-compliant projects could implement the category for adjacent domains (mobile gameplay, console-platform-native, VR-controller, IoT-sensor-wearable, professional-esports-arbitration, etc.). V.A.P.I.-as-category is not VAPI-as-brand; the brand belongs to QorTroller as the reference implementation.

### 1.3 The V.A.P.I. inversion vs traditional anti-cheat

Traditional anti-cheat (BattlEye, Easy Anti-Cheat, Riot Vanguard, VAC, RICOCHET) frames the problem as enforcement: the platform-as-authority detects violations and punishes violators. The data flow is one-way: gamer → platform → platform's centralized records. The gamer surrenders sovereignty over biometric / behavioral / consent data to participate.

V.A.P.I. inverts this:

| Dimension | Traditional anti-cheat | V.A.P.I. (QorTroller implements) |
|---|---|---|
| Data ownership | Platform owns gamer's data | Gamer owns gamer's data |
| Verification authority | Platform's word is root of trust | Cryptographic primitives are root of trust |
| Enforcement mode | Detection + punishment (zero-sum) | Attestation + sovereignty (positive-sum) |
| Cross-platform portability | None (each platform's anti-cheat is silo'd) | Cryptographic attestations portable across platforms by design |
| Right-to-be-forgotten | Limited; platform discretion | GDPR Art. 17 enforced by FSCA contradiction rule + on-chain revocation |
| Trust requirement for tournament | Trust the publisher's word | Verify on-chain view call (`isFullyEligible`) |
| Bot defeat mechanism | Pattern-match against bot-software allowlist | Cryptographically prove human-presence; bots can't fake the attestation |

The V.A.P.I. inversion removes punishment as the operational mode. Cheating doesn't need to be punished because it can't exist when humanity is cryptographically proven and the gamer retains sovereignty. The architecture makes the wrong outcome cryptographically impossible rather than punishable-after-the-fact.

---

## 2. The Project — QorTroller

### 2.1 Brand identity

**QorTroller** is the reference implementation of V.A.P.I. for competitive gaming. The brand encodes the dual-meaning of its design:

- **Surface meaning**: the protocol verifies physical gaming **controllers** (currently Sony DualShock Edge CFI-ZCP1; future expansion to other certified gamepad families)
- **Deep meaning**: the gamers themselves are the agentic **Core Controllers** of their own gaming data — they hold the cryptographic credentials, grant per-category consent, exercise GDPR Article 17 right-to-be-forgotten, and `msg.sender` on `VAPIConsentRegistry` IS the gamer

The brand tagline — **"Core Controllers of their gaming data"** — frames both meanings simultaneously.

**Etymology**: Qor (Qorvo NASDAQ:QRVO commercial precedent for Q-without-U coined technology brands; semantic anchor "core") + Troller (from Controller — the protocol's primary subject in both meanings). Pronunciation: **KOR-TROLL-er** (IPA `/ˈkɔːrˌtroʊlər/`, 3 syllables, primary stress 1st + secondary stress 2nd). Display styling: medial capital T (**QorTroller**) following iPhone / GitHub / OpenAI / PayPal brand convention.

### 2.2 Project-vs-category vocabulary

Throughout this whitepaper:

- **"QorTroller"** refers to the project / reference implementation / brand identity
- **"V.A.P.I."** refers to the coined DePIN sub-category
- **"VAPI"** (without periods) appears only in technical code identifiers (Python module paths, class names, byte literals like `b"VAPI-GIC-GENESIS-v1"`, deployed contract names like `VAPIToken` / `VAPIVerifiedHumanProof` / `VAPIConsentRegistry` / `VAPIProtocolLens` / `VAPIDataMarketplaceListings`) where periods would break syntax — these are V.A.P.I. category primitives preserved as `b"VAPI-..."` per Layer C FROZEN-v1 discipline forever

The distinction matters for downstream consumers:
- A tournament organizer integrating QorTroller calls `VAPIProtocolLens.isFullyEligible(deviceIdHash)` — the contract name is technical/categorical (V.A.P.I. category interface) and stays VAPI-prefixed
- The same tournament organizer markets "QorTroller-verified tournament gameplay" — the brand identity in marketing material is QorTroller
- A future V.A.P.I.-compliant project (e.g., a mobile V.A.P.I. implementation) would use compatible interfaces (VAPI-category-named) but have its own project brand (not QorTroller)

### 2.3 The 228-byte Proof of Autonomous Cognition (PoAC)

[Refer to `docs/vapi-whitepaper-v4.md` §2 for the full PoAC wire-format specification. The technical content is unchanged in v5 — only the brand-layer naming evolves.]

QorTroller produces, per cognitive cycle (≈8 ms at 1000 Hz USB polling), one 228-byte PoAC record:
- **164-byte signed body**: device identity hash + sensor commitments (IMU dynamics + analog trigger dynamics + stick/button timing + biometric feature commitments) + inference codes + chain-link binding
- **64-byte ECDSA-P256 signature**: hardware-rooted on certified DualShock Edge controller

Chain-link hash: `SHA-256(raw[0:164])` — body ONLY, never the full 228 bytes. This is FROZEN INV-002.

### 2.4 The nine-level PITL stack

[Refer to `docs/vapi-whitepaper-v4.md` §3 for the full PITL layer documentation.]

| Layer | Code | Type | Function |
|---|---|---|---|
| L0 | — | Structural | HID presence (1000 Hz USB polling) |
| L1 | — | Structural | PoAC chain integrity |
| L2 | 0x28 | Hard cheat | IMU gravity + HID/XInput discrepancy |
| L3 | 0x29 / 0x2A | Hard cheat | TinyML behavioral classifier |
| L2B | 0x31 | Advisory | IMU-button causal latency |
| L2C | 0x32 | Advisory | Stick-IMU cross-correlation |
| L4 | 0x30 | Advisory | 13-feature Mahalanobis biometric fingerprint |
| L5 | 0x2B | Advisory | Temporal rhythm |
| L6 | — | Advisory | Active haptic challenge-response |
| L7 (PITL) | 0x33 | Advisory | GSR sympathetic-arousal correlation |
| L7-Methodology | — | Output | PATTERN-017 V.A.P.I. primitives + VPM compiler |
| L8 | — | Transport | BT 250 Hz BLE (gated workstream) |
| L9 | — | Governance | Operator Initiative fleet |

### 2.5 The PATTERN-017 V.A.P.I. primitive family

[Refer to `docs/vapi-whitepaper-v4.md` §4 for the full primitive specifications.]

12 FROZEN-v1 byte literals comprise the V.A.P.I. category primitive family (the 12th, `b"VAPI-O3-SUPERSEDE-v1"`, lands at R2-PRE governance ceremony per QRESCE-0001 v0.5 §0.5 delta #1):

```
b"VAPI-GIC-GENESIS-v1"                # Grind Integrity Chain genesis
b"VAPI-WEC-GENESIS-v1"                # Watchdog Event Chain genesis
b"VAPI-VAME-v1"                       # Application-layer Message Envelope
b"VAPI-CORPUS-SNAPSHOT-v1"            # Wiki + agent-fleet snapshot anchor
b"VAPI-CONSENT-v1"                    # Per-category gamer consent
b"VAPI-BIOMETRIC-SNAPSHOT-v1"         # ZK-attested biometric corpus snapshot
b"VAPI-LISTING-v1"                    # Marketplace listing primitive
b"VAPI-FRR-v1"                        # Fleet Readiness Root
b"VAPI-ZKBA-ARTIFACT-v1"              # Zero-Knowledge Biometric Artifact
b"VAPI-AGENT-COMMIT-v1"               # Agent-commit attestation
b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"  # Physical-data attestation
b"VAPI-O3-SUPERSEDE-v1"               # Operator O3 supersedure (R2-PRE governance)
```

These byte literals are V.A.P.I. CATEGORY primitives — they belong to the sub-category that QorTroller implements + that future V.A.P.I.-compliant projects would share. Permanently `b"VAPI-..."` prefixed per FROZEN-v1 discipline (same constraint that locks the 228-byte PoAC wire format). The QorTroller PROJECT brand operates at a different layer (display / marketing / repo / external positioning); the V.A.P.I. CATEGORY primitives are technical-shared-infrastructure that don't change with project rebranding.

---

## 3. IoTeX Alignment

[Refer to `docs/vapi-whitepaper-v4.md` §5–§9 for the full architectural detail.]

QorTroller is built native to IoTeX's Internet of Trusted Things foundation:

- **IoTeX L1** anchors the 12 V.A.P.I. PATTERN-017 primitives + 16 deployed V.A.P.I.-category contracts (testnet chain ID 4690)
- **IoTeX ioID** primitive native to operator-agent identity (3 Operator Initiative agents registered on-chain via ioID at Phase O0)
- **W3bstream** applet integration for off-chain ZK verification (validate_poac_record applet)
- **IoTeX P256 precompile** for hardware-rooted ECDSA-P256 signature verification (testnet active at `0x0100`)
- **LayerZero V2 OApp** for cross-chain VHP (Verified Human Proof) accessibility
- **IoTeX QuickSilver** liquid-staking integration for operator stake (via VAPIQuickSilverCollateral)

The protocol does not require IoTeX-exclusively — it could in principle be ported to any EVM-compatible chain with similar primitives — but IoTeX is the canonical home chain for QorTroller and the originating chain for all V.A.P.I. category primitives.

---

## 4. Current State, Roadmap, and Brand Provenance

### 4.1 Current state (2026-05-18)

Per `docs/vapi-whitepaper-v4.md` §10–§15 (technical content) + CLAUDE.md (operational state):

- **Phase O3-ACTING reached** by all 3 Operator Initiative agents 2026-05-17 (first ≥3-agent operator fleet at O3_ACTING in any DePIN gaming protocol)
- **STABILITY-9 EMPIRICAL CLOSURE** shipped 2026-05-18 (14-stage incremental hardening arc + 9-cycle bisection + 41 agents individually verified; 71% peak STARVATION reduction; partial closure with 14s residual accepted-debt + structural finding documented)
- **QRESCE-0001 v0.5 brand lock** at QorTroller 2026-05-18 (this whitepaper's brand layer)
- **128 PV-CI invariants** pinned via governance-ceremony
- **9/9 domain TLDs** confirmed available for QorTroller brand registration (.com + .io + .org + .xyz + .network + .app + .dev + .tech + .ai)
- **PATCH path identified** for tertiary STABILITY-9 blocker (Windows ProactorEventLoop AsyncHTTPProvider cancellation gap on event-filter `get_logs` reads); per-method sync_w3 companions documented as Stage 15+ reservation if operational stress requires

### 4.2 Roadmap

**Phase 3 (R1+ QRESCE-0001 execution)** — pending R0 prerequisites (operator-side; trademark + domain + GitHub slot reservations + social handles + audio sample + R0 certificate signature):
- R1: plan-doc commit (`docs/qresce/QRESCE-0001-v0.5.md`)
- R2-PRE: Mythos pre-flight gate + `b"VAPI-O3-SUPERSEDE-v1"` governance ceremony (lifts FROZEN tags 11 → 12)
- R2: brand-layer mechanical rename (project identity only; V.A.P.I. category references preserved per Layer C)
- R3: Mythos post-rename verification
- R4: squash-merge + DEFPUB-0001 v0.3 staged execution (defensive publication anchor minted under QorTroller brand)
- R5: successor docs (WP6 full rewrite + GRANT-0001 IoTeX foundation submission + COMMS-0001 external comms)

**Future V.A.P.I.-compliant project space**:
- Mobile V.A.P.I. (touch-event + IMU on smartphones)
- Console-platform-native V.A.P.I. (PlayStation / Xbox / Switch directly)
- VR-controller V.A.P.I. (6DOF tracker integration)
- IoT-sensor-wearable V.A.P.I. (smart-watch GSR + ECG + step-count)
- Professional-esports-arbitration V.A.P.I. (tournament-organizer-operated V.A.P.I. node federation)

QorTroller's role within the V.A.P.I. category is as the reference implementation — the canonical example that proves the architecture and supplies the FROZEN-v1 primitives that other V.A.P.I. projects can compose against.

### 4.3 Brand provenance (for trademark prosecution support)

The QorTroller brand emerged through 5 documented iterations during operator-collaboration cycles 2026-05-17 → 18:

1. **Qoresence** (v0.2 baseline) — 3 syllables (KOR-ess-ense); abstract "core presence"
2. **Qorsence** (v0.3 interim) — 2 syllables; phonetic tightening
3. **QorSense** (v0.4) — medial-cap brand-styling pivot; rejected at Phase 2 RDAP deep-verify when `qorsense.com` confirmed registered by GoDaddy squatter (registered 2026-01-07; parking nameservers; redirects to /lander brokerage; resale $500-$50K+ expected)
4. **Qorify** (interim candidate) — eliminated when `qorify.com` confirmed actively used (Wix site, 837KB real content) + `qorify.tech` also REGISTERED
5. **ConTrolla** (interim candidate) — operator self-rejected as already-taken (Italian/Spanish common word)
6. **QorTroller** (v0.5 FINAL) — 3 syllables (KOR-TROLL-er); medial-cap; dual-meaning semantic anchor (physical controllers + agentic gamers); 9/9 domain availability + 8/8 GitHub variants + 4/4 PyPI + 5/5 npm + brand-virginity SEO (22 Bing SERP mentions vs Qorvo 46 + NASDAQ:QRVO; ratio 0.48 essentially virgin); aligns with existing protocol architecture's gamer-self-sovereignty hard rules

Each iteration validated via the same precisional verification cycle (RDAP authoritative for domains via Verisign + Identity Digital + PIR + Donuts + Google Registry + Radix + bootstrap cross-verify; HTTP probes for GitHub; PyPI/npm package registries; Bing SEO comparative for brand-virginity).

The selection process + brand-iteration trail provides clear evidence of intentional brand-distinctiveness rationale for any future trademark prosecution. Combined with the Qorvo NASDAQ:QRVO commercial precedent for Q-without-U coined technology brands, QorTroller's brand defensibility rests on:

- **Coined-prefix differentiation**: Qor (intentional Q-without-U, following established commercial precedent)
- **Semantic anchor**: dual meaning (literal hardware + philosophical agency) documented in brand guidelines
- **Brand-virginity**: SEO comparative shows zero competing commercial presence
- **Categorical positioning**: V.A.P.I. is a coined category, not an existing one — first-mover in the category framing
- **Iterative selection record**: 5-iteration deliberate-process documentation

---

## 5. References + Citations

For the full technical architecture (228-byte PoAC wire format spec, nine-level PITL detector specifications, FSCA contradiction rule catalog, Cedar bundle dual-anchor protocol, ZKBA seven-class artifact compositions, VPM compiler determinism guarantees, three-layer Anti-Hype Visual Grammar specification, Operator Initiative phase ladder O0 → O3_ACTING, complete invariant pin list, calibration corpus history, etc.), refer to:

- **`docs/vapi-whitepaper-v4.md`** — full 879-line technical baseline (architecture anchor `e81e04aa`, 2026-05-13)
- **`docs/vapi-whitepaper-v3.md`** — historical baseline (Zenodo DOI `10.5281/zenodo.18966169`, Phase 68-70)
- **`CLAUDE.md`** — operational state, phase history, hard rules, current invariant catalog
- **`wiki/methodology/METHODOLOGY_LAYER_INTEGRATION_MAP.md`** — complete cross-layer dependency graph
- **`wiki/phases/phase_235_stability_9_closure.md`** — STABILITY-9 14-stage arc + 9-cycle bisection closure documentation
- **`vsd-vault/proposals/drafts/qresce-0001-r0-artifacts/`** — QRESCE-0001 R0 prerequisite artifacts (R0_PREREQ_CERTIFICATE.DRAFT.md v3 + pronunciation_guide.md v2 + R0_artifact_summary.md v3)
- **`C:\Users\Contr\.claude\plans\qresce-0001-v0.5-brand-amendment.md`** — brand-lock amendment plan

### Suggested citation (post-Zenodo v5 mint)

```bibtex
@misc{qortroller2026,
  author    = {Contravious Battle},
  title     = {QorTroller — Core Controllers of their gaming data:
               A Reference Implementation of Verifiable Autonomous Physical
               Intelligence (V.A.P.I.) on IoTeX},
  year      = {2026},
  note      = {Whitepaper v5 (brand-layer reframing of v4). V.A.P.I. category
               coined; QorTroller is reference implementation. Built on
               IoTeX. Brand-lock commit 2c762835.},
  url       = {https://github.com/ConWan30/QorTroller}
}
```

Pre-Zenodo v5: cite v3 DOI + reference v4 technical baseline + this v5 file for brand-layer + V.A.P.I. category framing.

---

## 6. License + Brand Notice

**Copyright © 2026 Contravious Battle. All Rights Reserved.**

**Brand**: QorTroller™ (medial capital T styling; pending USPTO trademark filing per QRESCE-0001 R0). The QorTroller brand is the project identity of the V.A.P.I. (Verifiable Autonomous Physical Intelligence) reference implementation. The V.A.P.I. acronym + category description is published as defensive prior art per DEFPUB-0001 v0.3 framework; the V.A.P.I. category itself is intentionally open for compliant implementations by other projects.

The `VAPI` token in code identifiers (Python module paths, Solidity contract names, byte literals) is preserved as technical-categorical infrastructure per Layer C FROZEN-v1 discipline. The `QorTroller` brand identity operates at the display / marketing / external positioning layer. The V.A.P.I. (with periods) styling appears in display contexts to differentiate the coined V.A.P.I. DePIN sub-category from unrelated similarly-named projects in other categories.

---

*End QorTroller Whitepaper v5. Brand-layer reframing of v4. Technical content preserved unchanged. V.A.P.I. category coined; QorTroller is the reference implementation. Built on IoTeX. Brand-lock commit `2c762835`, architecture anchor `e81e04aa`. Whitepaper v6 (full rewrite for IoTeX foundation grant submission) reserved for post-R5 successor work under GRANT-0001.*
