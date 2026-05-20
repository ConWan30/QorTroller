# QorTroller — Core Controllers of their gaming data

> **The reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.)** — a Decentralized Physical Infrastructure (DePIN) sub-category coined to describe protocols where the physical-input source is also the cryptographic agency-holder over the data those physical interactions generate. In QorTroller's case: gamers and their controllers, producing data, owning that data.
>
> Built native to IoTeX's Internet of Trusted Things foundation. Anchored on IoTeX L1. Composable as a single on-chain call. Designed so cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty.

**V.A.P.I.** — pronounced as the acronym; styled with periods to distinguish from unrelated similarly-named projects in other categories. As a coined DePIN sub-category, V.A.P.I. is the conceptual scope; QorTroller is the project that implements it for competitive gaming.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18966169.svg)](https://doi.org/10.5281/zenodo.18966169) (v3 — historical; v4 DOI pending release)

**Author:** Contravious Battle (Independent Researcher) · **Network:** IoTeX testnet (chain ID 4690) · **Phase:** O4-VPM-INTEGRATION CLOSED 2026-05-13 · **Architecture anchor:** `e81e04aa` · **Documentation commit:** `9f8581cd`

| Surface | Status |
|---|---|
| **Bridge tests** | 3344 passing |
| **SDK tests** | 562 passing |
| **Hardhat contract tests** | 528 passing |
| **Frontend Vitest** | 26 passing (first frontend test infra) |
| **PV-CI invariant gate** | 77 / 77 pinned (governance-ceremony-locked) |
| **FSCA contradiction rules** | 26 active |
| **Contracts LIVE on IoTeX** | 49 substantive live testnet contracts (51 registry slots; see `contracts/deployed-addresses.json`) |
| **Operator Initiative agents** | 3 LIVE at O1_SHADOW (Sentry / Guardian / Curator) |
| **ZKBA artifact classes** | 7 of 7 shipped (Layer 7 closed) |
| **VPM compilers active** | 6 (4 internal + 2 consumer-facing) |
| **Cryptographic chain primitives** | 10 FROZEN-v1 (PATTERN-017) |
| **Wallet posture** | `CHAIN_SUBMISSION_PAUSED=true` held; 0 IOTX impact across Phase O4 |

---

## What QorTroller is

**The problem.** Cheat detection in competitive gaming has no cryptographic anchor. Existing solutions (BattlEye, Riot Vanguard, Easy Anti-Cheat) are kernel-level enforcement layers with no public verifiability surface; tournament organizers and viewers must trust the publisher's claim that a match was clean. Bot software keeps improving; controllers get repurposed; signed binaries get repurposed; injection vectors keep multiplying. Worse: the enforcement model is zero-sum — the protocol *vs.* the gamer. The gamer surrenders sovereignty over their biometric, behavioral, and consent surfaces to participate.

**The category — V.A.P.I.** Verifiable Autonomous Physical Intelligence is a coined DePIN sub-category for protocols where the **physical-input source is also the cryptographic agency-holder** over the data those physical interactions generate. V.A.P.I. inverts the enforcement frame: cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty. Other future V.A.P.I.-compliant projects could implement the category for mobile, console, VR, IoT-sensor, or wearable scopes. QorTroller is the first.

**The project — QorTroller.** Binds every controller input event to a tamper-evident, on-chain-verifiable cryptographic record — a **Proof of Autonomous Cognition (PoAC)**. Each 228-byte PoAC binds raw sensor commitments (IMU dynamics, analog trigger dynamics, stick/button timing, biometric feature commitments) to a hardware-rooted ECDSA-P256 signature, hash-chains them into a per-session sequence, and exposes the resulting state through a single composable on-chain call: `VAPIProtocolLens.isFullyEligible(deviceIdHash)`. External tournament organizers can gate eligibility on that one view call without trusting a private publisher API or manually inspecting raw biometric data — the on-chain gate minimizes integrator trust by reducing eligibility to a public view-call over previously anchored protocol state. The gamer keeps cryptographic credentials (PHGCredential / VHP), grants per-category consent (CONSENT v1), and exercises GDPR Article 17 right-to-be-forgotten — `msg.sender` on `VAPIConsentRegistry` IS the gamer.

**The architecture.** Nine layers of Physical Input Trust (PITL L0–L6 deployed, L7 GSR advisory, L8 BT gated) verify each input event at increasing levels of biometric specificity. A 10-element family of FROZEN-v1 cryptographic primitives (PATTERN-017) anchors session continuity, cognition integrity, watchdog events, application-layer messaging, biometric snapshots, consent state, and Layer 7 ZKBA artifacts. Three Operator Initiative agents (Sentry, Guardian, Curator) hold Cross-Fleet Skill Separation (CFSS) lane authority on Cedar v2 bundles dual-anchored on chain.

**The output.** Seven Zero-Knowledge Biometric Artifact (ZKBA) classes (AIT, GIC, VHP, HARDWARE, CONSENT, TOURNAMENT, MARKET) compile through a deterministic Verified Projection Media (VPM) compiler with three-layer Anti-Hype Visual Grammar enforcement (compile-time + bridge-time + browser-time). Every cryptographic claim is independently verifiable by anyone with the canonical-JSON algorithm + SHA-256 + the public source of the four enforcement layers.

---

## Architecture at a glance

| Layer | Code | Type | Signal / Function | Key Invariants |
|---|---|---|---|---|
| **L0** | — | Structural | HID presence (1000 Hz USB polling) | INV-001..016 protocol pins |
| **L1** | — | Structural | PoAC chain integrity (SHA-256(raw[:164])) | INV-002 chain hash discipline |
| **L2** | `0x28` | Hard cheat | IMU gravity + HID/XInput discrepancy | Tournament-BLOCKING |
| **L3** | `0x29` / `0x2A` | Hard cheat | TinyML behavioral classifier | Tournament-BLOCKING |
| **L2B** | `0x31` | Advisory | IMU-button causal latency | — |
| **L2C** | `0x32` | Advisory | Stick-IMU cross-correlation | Inactive in dead-zone stick games |
| **L4** | `0x30` | Advisory | 13-feature Mahalanobis biometric fingerprint | INV-PCC-002..005; thresholds 7.009 / 5.367 |
| **L5** | `0x2B` | Advisory | Temporal rhythm (CV, entropy, quantization) | INV-APOP-001..002 |
| **L6** | — | Advisory | Active haptic challenge-response | `L6_CHALLENGES_ENABLED=false` until N≥50 |
| **L7** (PITL) | `0x33` | Advisory | GSR sympathetic-arousal correlation | `GSR_ENABLED=false` until N≥30/player |
| **L7-Methodology** | — | Output | PATTERN-017 primitives + VPM compiler + 3-layer Anti-Hype Visual Grammar | INV-VPM-* family (11 invariants) |
| **L8** | — | Transport | BT 250 Hz BLE (gated workstream) | `bt_transport_enabled=false` until N≥30/player MVCP |
| **L9** | — | Governance | Operator Initiative fleet (Sentry/Guardian/Curator) at O1_SHADOW; Cedar v2 dual-anchored | INV-OPERATOR-AGENT-001..008; CFSS triangle |

See `wiki/methodology/METHODOLOGY_LAYER_INTEGRATION_MAP.md` for the complete cross-layer dependency graph.

---

## Current state — honest

**Tournament gate status.** The protocol's headline invariant is `inter-person separation ratio > 1.0 AND all_pairs_above_1=True`. Current state across three calibration batteries:

| Battery | Ratio | N | `all_pairs_above_1` | Status |
|---|---|---|---|---|
| **AIT** (Active Isometric Trigger — Phase 229–231) | **1.199** | 37 | **True** | **CLEARED** for the AIT separation gate in the current corpus (testnet/demo eligibility evidence) |
| **touchpad_corners** | 0.728 | 35 | False | **BLOCKER** for tournament BLOCK enforcement (per-pair P3 separation inadequate) |
| **tremor_resting** | 1.177 | 27 | False | `all_pairs_p0_ok=False`; P1vP3=0.032 — Phase 213 AccelTremorFFT fix shipped, verification pending |

The token launch invariant ("no TGE before separation_ratio > 1.0 + all_pairs_above_1") **REMAINS IN FORCE** for legal/economic defensibility of token issuance. AIT clears the technical gate for testnet/non-tournament demonstrations; touchpad_corners is the actual tournament BLOCK enforcement blocker.

**On-chain anchored milestones (IoTeX testnet, chain 4690):**
- **GIC_100 cognitive chain head** permanently anchored 2026-05-06 — tx `0xe807347eb837...` block 43348052. A 100-link cognitive-session integrity chain anchored on IoTeX testnet.
- **Cedar v2 lane authority bundles** for all three Operator Initiative agents dual-anchored 2026-05-12 on AgentScope (operational FIRST) + AgentRegistry (governance SECOND). Merkle roots: Sentry `0x39e8b65f...db1f23` / Guardian `0x6818a9ad...0a9a0` / Curator `0x0ade0c92...60a80b3d`.
- **Inaugural CORPUS-SNAPSHOT** anchored 2026-05-09 — tx `0x24e4ddb6...` (closes Phase 237.5 Path C+ wallet-drain audit trail).
- **VHP demo mint** tokenId=2 — humanity credential bound to all three protocol layers (canonical Sony DualShock Edge CFI-ZCP1 device + GIC_100 milestone + ZK ceremony VK hash).

**What's still open** (not security blockers; operator-runtime work):
- VBDIP-0002 Appendix B B.8 gate **G7** (Curator Review Readiness — 7-day observation window with ≥9/10 acceptance gate)
- Touchpad_corners corpus expansion for P3 (per-pair separation work)
- 4 VPM Draft Manifest IDs at Reserved/Draft → Active lifecycle promotion (stakeholder governance gated)

See `wiki/phases/phase_o4_vpm_integration.md` §9 for the full forward roadmap.

---

## Quick start

### Read the whitepaper

- **Canonical v4 successor** (in this repo): [`docs/vapi-whitepaper-v4.md`](docs/vapi-whitepaper-v4.md) — current state through Phase O4 close
- **Historical v3** (Zenodo-published): [`docs/vapi-whitepaper-v3.md`](docs/vapi-whitepaper-v3.md) — Phase 68–70 baseline; preserved for DOI continuity
- See [`docs/WHITEPAPER_VERSIONING.md`](docs/WHITEPAPER_VERSIONING.md) for the full v1→v4 lineage

### Inspect the deployed contracts

```bash
# Open the deployed-addresses.json to see all 49 substantive live testnet contracts (51 registry slots)
cat contracts/deployed-addresses.json | python -m json.tool | head -60
```

Headline contracts to inspect on IoTeX testnet explorer (chain ID 4690):

- **PoACVerifier** — wire-format + ECDSA-P256 + chain integrity
- **VAPIProtocolLens** — the singular `isFullyEligible(deviceIdHash)` view-call gate
- **AdjudicationRegistry** `0x44CF981f46a52ADE56476Ce894255954a7776fb4` — PoAd anchors (Phase 111 LIVE)
- **AgentRegistry / AgentScope** — Operator Initiative fleet on-chain governance
- **ProtocolCoherenceRegistry** `0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` — fleet Merkle anchor
- **VAPIConsentRegistry** `0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` — per-category gamer consent

### Run the bridge locally

```bash
# Bridge (Python asyncio)
cd bridge
pip install -r requirements.txt
python -m pytest tests/ --ignore=tests/test_e2e_simulation.py -q   # 3344 tests

# Frontend (Vite + React)
cd frontend
npm install
npm run dev          # http://localhost:5173
npm test             # 26 Vitest tests across VPM Registry components

# Contracts (Hardhat)
cd contracts
npm install
npx hardhat test     # 528 tests
```

### Inspect a VPM artifact end-to-end

```bash
# 1. Compile one of the 7 ZKBA artifact classes (canonical fixture)
python scripts/zkba_compile_hardware_card.py --profile-hash 0xa1b2c3...0000 \
  --device-id-hash 0x10e0169446ba33200000000000000000000000000000000000000000000000 \
  --cert-level 1 \
  --manufacturer-address 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 \
  --is-certified --ts-ns 1778900000000000000

# 2. Run the wallet-free Layer 7 coverage audit
python scripts/layer7_coverage_audit.py --report

# 3. Run the wallet-free VPM audit (6-section harness)
python scripts/vpm_audit.py
```

---

## Repository navigation

```
vapi-pebble-prototype/
├── bridge/                  Python asyncio bridge (PITL L0–L6 oracle pipeline + 29 standalone agents + 3 Operator Initiative stewards)
│   ├── vapi_bridge/         Source — store / chain / agents / endpoint surface
│   └── tests/               Bridge test bands (Phase O3 ZKBA + Phase O4 VPM + earlier)
├── contracts/               Solidity 0.8 + Hardhat — 49 substantive live testnet contracts
│   ├── contracts/           Source — PoACVerifier, AdjudicationRegistry, VAPIProtocolLens, AgentRegistry, etc.
│   ├── test/                528 Hardhat tests
│   └── deployed-addresses.json   Authoritative on-chain address registry
├── scripts/                 Compilers + audits + ceremonies
│   ├── zkba_compile_*.py    7 ZKBA artifact compilers (Phase O3-ZKBA-TRACK1)
│   ├── vpm_compile_*.py     6 VPM compilers (Phase O4 Streams A.1+A.2)
│   ├── vpm_drafts/          4 draft manifests (JSON; Reserved → Draft Manifest lifecycle)
│   ├── vpm_visual_grammar.py    Shared FROZEN 6-state Anti-Hype Visual Grammar
│   ├── vsd_ui_compiler.py   Deterministic compile_artifact + compile_vpm_artifact
│   ├── vsd_vpm_wrapper.py   VPM wrapper schema (vapi-vpm-manifest-v1)
│   ├── vpm_audit.py         6-section VPM compiler/registry audit harness
│   ├── layer7_coverage_audit.py    Wallet-free Layer 7 7-of-7 audit
│   ├── zkba_post_ceremony_audit.py Cedar v2 lane authority audit
│   ├── vapi_invariant_gate.py      PV-CI 77-invariant gate
│   └── parallel_*_anchor.py        Triple-gate ceremony scripts (operator-runtime)
├── sdk/                     Python SDK (562 tests) — VAPIZKBA, VAPIFleetReadinessRoot, etc.
├── frontend/                Vite + React Operator Console
│   ├── src/views/           6 top-level views (GAMER / DEVELOPER / MANUFACTURER / BRP / MARKETPLACE / VPM)
│   ├── src/components/      VpmFilterChips / VpmIframe / VpmManifestPanel / VpmGrammarVerifier + others
│   └── src/__tests__/       26 Vitest tests (first frontend test infra)
├── wiki/                    Methodology + phase + assessment archive
│   ├── methodology/         VBDIP-0001 (FROZEN) + VBDIP-0002 v1.2 with Appendix B
│   ├── phases/              Phase provenance pins (latest: phase_o4_vpm_integration.md)
│   ├── proposals/           Phase O4 plan + Operator Decision Matrix + reconciliation plans
│   ├── assessments/         V-check reports + position assessments + canonical PDFs
│   ├── concepts/ entities/ what_if/  Cross-cutting reference material
│   └── runbooks/            Operator-runtime procedures
├── docs/                    Public-facing documentation
│   ├── vapi-whitepaper-v4.md       Canonical successor (current; this commit)
│   ├── vapi-whitepaper-v3.md       Zenodo-published baseline (preserved)
│   ├── WHITEPAPER_VERSIONING.md    v1→v4 lineage
│   └── (other technical docs)
├── CLAUDE.md                Operator-authoritative state file (single source of truth)
├── contracts/deployed-addresses.json   Authoritative on-chain registry
└── .github/INVARIANTS_ALLOWLIST.json   77-entry PV-CI digest pin file
```

---

## Hard rules (non-negotiable protocol invariants)

The following rules are **FROZEN**. Changing any of them requires a `--confirm-governance` ceremony plus operator authority:

- **PoAC wire format: 228 bytes** (164-byte signed body + 64-byte ECDSA-P256 signature). Pinned by INV-001.
- **Chain link hash: `SHA-256(raw[:164])`** — body only, NOT the full 228 bytes. Pinned by INV-002.
- **`deviceId = keccak256(pubkey)`** — never swapped with `record_hash`.
- **Hard cheat codes**: `0x28` DRIVER_INJECT, `0x29` WALLHACK, `0x2A` AIMBOT — block tournament eligibility.
- **`L6_CHALLENGES_ENABLED = false`** until N≥50 RIGID_MAX calibration (current N=0).
- **`GSR_ENABLED = false`** until N≥30 GSR sessions per player (current N=0).
- **`bt_transport_enabled = false`** until N≥30 BT MVCP per player (current N=0).
- **No token launch before separation_ratio > 1.0 AND all_pairs_above_1=True** — empirically confirmed AND all-pairs above. Currently cleared for the AIT separation gate in the current corpus (1.199, N=37); touchpad_corners (0.728) remains the actual tournament BLOCK enforcement blocker.
- **Stable EMA track updates on NOMINAL sessions only** — security invariant; never override.
- **Per-player L4 thresholds tighten, never loosen** — enforced via `min()` operator.
- **PV-CI invariant gate** runs on every PR — currently 77 invariants. Modifying a frozen region without a `--confirm-governance` ceremony fails CI.
- **CHAIN_SUBMISSION_PAUSED kill-switch** held in `bridge/.env` — every chain-write path is gated; operator three-factor authorization (env var + env var + `--confirm` CLI flag) required to lift.

Complete invariant list: `scripts/vapi_invariant_gate.py` + `.github/INVARIANTS_ALLOWLIST.json`.

---

## Phase O4-VPM-INTEGRATION (just closed)

Phase O4 elevated the **Methodology Layer (Layer 7) output surface** from a collection of frozen primitives + a deterministic compiler to a complete delivery stack with multi-layer overclaim defense. Shipped across 10 atomic commits, 0 IOTX wallet impact, 0 new Cedar lanes, 0 contract deploys:

| Stream | Commit | What shipped |
|---|---|---|
| Layer 7 audit | `168256a0` | `scripts/layer7_coverage_audit.py` (917 LOC) + 7-of-7 closure provenance |
| V-check pin | `603c98cb` | `wiki/assessments/phase_o4_vchecks_2026-05-13.md` (V1..V10 pass) |
| A.0 | `524ae1cc` | `compile_vpm_artifact()` engine + T-VPM-COMPILER-1..10 (10 tests) |
| A.1 | `fd0d6699` | 4 internal compilers + Anti-Hype Visual Grammar (73 tests) |
| A.2 | `7052144f` | 2 consumer-facing compilers + procedural geometric art (46 tests) |
| A.3 + A.4 | `169471bb` | 4 draft manifests + `vpm_audit.py` (15 tests) |
| B.0–B.3 | `1b13618d` | `vpm_artifact_log` store + 3 read endpoints (14 tests) |
| B.4–B.7 | `d5803d47` | Write + validate + audit endpoints + stability harness (20 tests) |
| C | `0061e6d9` | VPM Registry tab + sandboxed iframe + Layer 3 grammar verifier (26 Vitest) |
| Close | `e81e04aa` | PV-CI 77 + FSCA 26 + B.8 gate sweep + CLAUDE.md NOTE + provenance pin |

The **three-layer Anti-Hype Visual Grammar** is the protocol's first structural UX defense — preventing demo-as-production / revoked-as-active / unverified-as-verified overclaim attacks via a FROZEN DOM signature matrix enforced at three independent layers (Python compile-time + Python bridge-time + JavaScript browser-time).

**QorTroller (as a V.A.P.I.-compliant reference implementation) now holds the frozen-primitive ↔ frozen-compiler ↔ frozen-visual-grammar ↔ frozen-iframe-sandbox quadruple-bind** — every cryptographic claim is independently verifiable by anyone with the canonical-JSON algorithm + SHA-256 + the public source of the four enforcement layers.

See [`wiki/phases/phase_o4_vpm_integration.md`](wiki/phases/phase_o4_vpm_integration.md) for the complete close provenance.

---

## Citation

Until v4 receives its own Zenodo DOI at release, cite the historical v3 whitepaper and reference v4 by commit:

```bibtex
@software{battle_2026_vapi_v3,
  author    = {Battle, Contravious},
  title     = {QorTroller (V.A.P.I. Reference Implementation): Verifiable Controller Input Provenance with
               Physics-Backed Liveness for Competitive Gaming},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.18966169},
  url       = {https://doi.org/10.5281/zenodo.18966169},
  version   = {v3 (historical; superseded by v4 in-repo)},
  note      = {v4 in-repo: docs/vapi-whitepaper-v4.md at architecture anchor
               commit e81e04aa (documentation revamp commit 9f8581cd);
               v4 DOI assignment pending Zenodo release}
}
```

---

## License

**Copyright © 2026 Contravious Battle. All Rights Reserved.**

Source is available in this repository for inspection, research review, and security audit. **No open-source license is declared.** Commercial integration, derivative work, or redistribution requires an explicit license agreement with the author.

Patent claims and academic citation: reference the Zenodo DOI above (v3) plus the in-repo `docs/vapi-whitepaper-v4.md` for current-state citations.

---

## Contact

Issues, security disclosures, and partnership inquiries should be filed via GitHub Issues on this repository or directed to the author through Zenodo's contact path on the v3 DOI page.

---

*QorTroller is the reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.) — a Decentralized Physical Infrastructure (DePIN) sub-category — for competitive gaming on IoTeX. This repository contains the canonical implementation as of Phase O4-VPM-INTEGRATION close — architecture anchor `e81e04aa` (2026-05-13), documentation commit `9f8581cd`. Brand-rename QRESCE-0001 v0.5 landed 2026-05-18 (codebase identifiers preserve `VAPI` as categorical references per Layer C FROZEN-v1 discipline; project identity displays as **QorTroller** per medial-cap brand convention).*
