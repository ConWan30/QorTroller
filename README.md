# QorTroller — Core Controllers of their gaming data

> **The reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.)** — a Decentralized Physical Infrastructure (DePIN) sub-category coined to describe protocols where the physical-input source is also the cryptographic agency-holder over the data those physical interactions generate. In QorTroller's case: gamers and their controllers, producing data, owning that data.
>
> Built native to IoTeX's Internet of Trusted Things foundation. Anchored on IoTeX L1. Composable as a single on-chain call. Designed so cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty.

**V.A.P.I.** — pronounced as the acronym; styled with periods to distinguish from unrelated similarly-named projects in other categories. As a coined DePIN sub-category, V.A.P.I. is the conceptual scope; QorTroller is the project that implements it for competitive gaming.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18966169.svg)](https://doi.org/10.5281/zenodo.18966169) (v3 — historical; v4 DOI pending release)

**Author:** Contravious Battle (Independent Researcher) · **Network:** IoTeX testnet (chain ID 4690) · **Phase:** PATH A ARC 1 + DATA ECONOMY ARC 2 + ARC 4 + ARC 5 + ARC 6 **DEPLOYED**; ARC 7 PQ SIDECAR BUILT (v2 wrapper ceremony-gated) — **public repo, mainnet-ready** · **Date:** 2026-06-05

| Surface | Status |
|---|---|
| **Bridge tests** | 4330+ passing |
| **SDK tests** | 604 passing |
| **Hardhat contract tests** | **760 passing** (13 pre-existing unrelated failures, see baseline) |
| **Frontend Vitest** | **155 passing** (Consent Cockpit + VHR Proof Panel additions, 2026-06-04/05) |
| **PV-CI invariant gate** | **174 / 174 pinned**, governance-ceremony-locked; CI-enforced on every PR |
| **FSCA contradiction rules** | 28 active |
| **Contracts LIVE on IoTeX testnet** | **66 deployed, 58 currently-active** (chain 4690; per the 2026-06-13 contract-status audit `audits/contract-status-cycle-15-2026-06-13.md` — 58 ACTIVE / 3 explicitly SUPERSEDED / 5 deprecated-by-versioning; supersession is a classification overlay, all 66 remain on-chain and callable). See `contracts/deployed-addresses.json`. Recent deploys: **Arc 2 `VAPIBuyerCategoryVerifier` `0x5B1D82AA…` (block 44355501, 2026-06-05)**; **Arc 6 `VAPITemporalBeaconRegistry` `0x96244031…` (block 44355513, 2026-06-05)**; Arc 5 v1 `VAPIReplayProofVerifier` `0x5182372d…` (block 44053167, 2026-05-30); Arc 4 `VAPIConsentManifestRegistry` `0x5F7c8068…` (block 44053171, 2026-05-30) |
| **Gamer-facing dApps** | **Consent Cockpit at `/consent`** — first standalone gamer-sovereign consent surface in the protocol (Cockpit F1–F5 shipped 2026-06-05); `BRIDGE NEVER GRANTS OR REVOKES CONSENT` invariant displayed as headline UX, signing always `msg.sender == gamer` |
| **Operator Initiative agents** | **3 LIVE at O3_ACTING** (Sentry / Guardian / Curator) — first ≥3-agent fleet at full action authority in any DePIN gaming protocol; ceremony fired live 2026-05-17, Fleet Readiness Root `0x54b4b698…` permanently anchored |
| **ZKBA artifact classes** | 7 of 7 shipped (Layer 7 closed) |
| **VPM compilers active** | 6 (4 internal + 2 consumer-facing) |
| **Cryptographic chain primitives** | **14 FROZEN-v1 (PATTERN-017)** including #14 `VAPI-TEMPORAL-BEACON-v1` (Arc 6 PoSR, FROZEN 2026-05-30, registry now LIVE 2026-06-05) |
| **Arc 7 — PQ cryptographic sidecar** | `pqCommitment` parameter threaded through Arc 6 verification path (`verifyWithRecency`, `verifyBeacon`); registry rejects zero commitments; Thread C `asyncio.to_thread` prover offload prevents ingestion-loop jitter. v2 wrapper deploy operator-interactive snarkjs ceremony-gated. |
| **First gamer-self-sovereign consent manifest on-chain** | Written 2026-06-05 from real wallet (`0x0Cf36dB57…`) to `VAPIConsentManifestRegistry` at `0x5F7c8068…` — tx `0xd02c051e…20bd` block 44354567, `allowReplayProofs=true` verified on-chain. Gamer-self-sovereignty invariant verified by Solidity `msg.sender == gamer` check; bridge structurally incapable of writing this. |
| **GIC_100 cognitive chain head** | Permanently anchored 2026-05-06 (block 43348052) |
| **World Model Provenance Lane (WMP)** | **Architectural blueprint published 2026-06-05** — additive packaging + export + consumer-verifier lane over Arc 5 (VHR) + Arc 6 (PoSR) + Arc 4 (Consent). Honest POMDP placement (provenance source, NOT a world model); action-channel-only; post-φ sanitized data only; consumer-side Poseidon matrix↔root re-hash closes the long-open Arc 5 off-circuit finding. W1-D operator decision: fixtures-first ship, deferred-export guard, minimal `VAPIWorldModelConsentRegistry` as flagged Phase-2 promote. |
| **CI matrix** | GitHub Actions: Python 3.10/3.11/3.12 × Node 18/20 + Rust stable + WASM target enforcing 174-invariant gate on every PR |
| **Wallet posture** | `CHAIN_SUBMISSION_PAUSED=true` held; zero-trust sandbox compliant; every chain-write path operator-fired |

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

## 2026-06-05 milestone block — operator-authorized session deploys

Three first-class on-chain milestones landed in a single operator-authorized session, materially closing the Arc 2 / Arc 4 / Arc 6 deployment surface against the World Model Provenance Lane (WMP) architectural blueprint:

| Milestone | Address / tx | Significance |
|---|---|---|
| **First gamer-self-sovereign Arc 4 consent manifest write on IoTeX** | tx `0xd02c051e3ced085bccd148a8501a0e86f9f4956910e6ddfda16ec7919c6b20bd` · block 44354567 | Wallet `0x0Cf36dB57…` wrote a 19-field structured consent manifest to `VAPIConsentManifestRegistry` `0x5F7c8068…` — including `allowReplayProofs=true` opting in to Arc 5 VHR proof production. Verified post-write: `manifestHash` on-chain matches expected; gamer-self-sovereignty invariant (`msg.sender == gamer`) structurally enforced by the contract. The bridge is cryptographically incapable of writing this on behalf of any gamer. |
| **Arc 2 — `VAPIBuyerCategoryVerifier` LIVE** | `0x5B1D82AAc2FD662f8850C49e40A94573f624440A` · tx `0x578c6e3ee7191d9c1519eb84fee79e377a2f1eefe70d03603169e82894727fa3` · block 44355501 | Buyer-category Groth16 verifier wrapper now on-chain. Buyer-side marketplace ZK gating wired. Closes the long-standing Arc 2 deploy-hold. |
| **Arc 6 — `VAPITemporalBeaconRegistry` LIVE** | `0x962440312a995b21d4E203bE6d93021CC22bA051` · tx `0x7d87bdef875f0507fca9f3f2b6a99efccc275415a1dcd3a3d080c2b768da0140` · block 44355513 | FROZEN-v1 #14 `VAPI-TEMPORAL-BEACON-v1` registry now on-chain. `INV-TBR-001` (BEACON_DOMAIN keccak256 pin) + `INV-TBR-002` (`ANCHOR_CADENCE=64` pin) byte-equal-checked at deploy. **Keeper not yet set** — until `setKeeper(...)` + first `anchorBeacon(...)`, the bridge's PoSR binder returns `None` honestly (no fabrication), and VHR proofs land in v1 Arc 5 behavior (no recency upgrade). The fail-open contract was preserved exactly; bridge readiness never depended on Arc 6. |

**Total session on-chain spend:** ~1.34 IOTX (consent manifest 0.18 IOTX + Arc 2 0.54 IOTX + Arc 6 0.46 IOTX, plus marginal gas overhead). Wallet `0x0Cf36dB57…` remaining: ~31.96 IOTX. `CHAIN_SUBMISSION_PAUSED=true` in `bridge/.env` held throughout — these were direct hardhat deploys signed by the bridge/deployer wallet, NOT bridge-side transactions.

## Consent Cockpit dApp — first standalone gamer-sovereign surface

Live at `/consent` (alias `/cockpit`) — separate from the operator dashboard and Evidence OS workspaces. Shipped 2026-06-05 across F1–F5:

| Pane | What it does |
|---|---|
| **Posture banner** | Displays `✓ REGISTRY LIVE` or `⚠ DEPLOY-HOLD` based on env-wired registry address. Banner headline: *"You are the only authority over your consent."* |
| **Identity card (dual-identity)** | Renders wallet (AUTHORITY — the signer) AND device_id (SUBJECT — the certified controller) as **distinct fields**. device_id resolved on-chain via `useWalletDevices` against `VAPIPoEPRegistry.DeviceRegistered` (primary, gamer-signed) + `VAPIVerifiedHumanProof.tokenOfAddress` (fallback, operator-attested). Multi-controller selector when >1 binding exists. Honest empty state when no on-chain controller is registered. **Never derives device_id from wallet.** |
| **Authority matrix** | `ConsentMatrix` in edit mode against the 4-bit FROZEN bitmask (Phase 237 `VAPIConsentRegistry`). Live wagmi `useWriteContract` → `useWaitForTransactionReceipt` propagation status indicator (IDLE → SIGNING → PENDING → MINED). |
| **Receipt timeline** | Append-only `consent_event_log` table (Phase 244 migration) — every GRANT/REVOKE/re-GRANT recorded as a distinct row. A grant→revoke→regrant cycle produces 3 rows (state-table upsert would erase intermediate transitions; the dedicated append-only log preserves the regulator-facing audit trail). |
| **Sovereignty disclosure** | Loud restatement of `BRIDGE NEVER GRANTS OR REVOKES CONSENT` with link to the CLAUDE.md hard rule in this public repo. |

**Companion VHR Proof Panel on GamerView** (bottom-left, previously vacated by ConsentPanelOverlay) — shows the most recent `on_session_complete_vhr` outcome from `curator_packaging_log`: `PROOF BUILT` / `DEFERRED` / `NO CONSENT` / `—`. noMock; honest empty state; bridge-offline state holds last-known value.

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
# Open the deployed-addresses.json to see all 53 substantive live testnet contracts
cat contracts/deployed-addresses.json | python -m json.tool | head -60
```

Headline contracts to inspect on IoTeX testnet explorer (chain ID 4690):

- **PoACVerifier** — wire-format + ECDSA-P256 + chain integrity
- **VAPIProtocolLens** — the singular `isFullyEligible(deviceIdHash)` view-call gate
- **AdjudicationRegistry** `0x44CF981f46a52ADE56476Ce894255954a7776fb4` — PoAd anchors (Phase 111 LIVE)
- **AgentRegistry / AgentScope** — Operator Initiative fleet on-chain governance
- **ProtocolCoherenceRegistry** `0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` — fleet Merkle anchor
- **VAPIConsentRegistry** `0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` — per-category gamer consent
- **VAPIConsentManifestRegistry** `0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743` — Arc 4 structured 8-dimension consent (DEPLOYED 2026-05-30; first manifest write 2026-06-05)
- **VAPIReplayProofVerifier v1** `0x5182372d1D033db0c9230843DFDE606733D5F91B` — Arc 5 VHR Groth16 wrapper (DEPLOYED 2026-05-30)
- **VAPIBuyerCategoryVerifier** `0x5B1D82AAc2FD662f8850C49e40A94573f624440A` — Arc 2 buyer-category ZK gate (DEPLOYED 2026-06-05)
- **VAPITemporalBeaconRegistry** `0x962440312a995b21d4E203bE6d93021CC22bA051` — Arc 6 PoSR (FROZEN-v1 #14 `VAPI-TEMPORAL-BEACON-v1`, DEPLOYED 2026-06-05; INV-TBR-001/002 byte-checked at deploy; keeper not yet set)
- **VAPIManufacturerDeviceRegistry** `0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0` — Path A Arc 1 silicon-rooted hardware identity
- **VAPIProtocolLensV2** `0x32Bf1A01a0a2629955A3Fd5ce74c0571DAd7C989` — Path A Arc 1 composable lens (`isFullyEligible_PathA`)

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
├── contracts/               Solidity 0.8 + Hardhat — 55 substantive live testnet contracts
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
- **PV-CI invariant gate** runs on every PR — currently 174 invariants. Modifying a frozen region without a `--confirm-governance` ceremony fails CI.
- **CHAIN_SUBMISSION_PAUSED kill-switch** held in `bridge/.env` — every chain-write path is gated; operator three-factor authorization (env var + env var + `--confirm` CLI flag) required to lift.

Complete invariant list: `scripts/vapi_invariant_gate.py` + `.github/INVARIANTS_ALLOWLIST.json`.

---

## Phase O4-VPM-INTEGRATION (historical milestone, closed 2026-05-13)

> Marker section preserved — Phase O4 closed the Methodology Layer (Layer 7) delivery stack with three-layer anti-overclaim defense. Arcs 5, 6, and 7 have shipped subsequently (see *Advanced Security Arcs & Capabilities* below); Phase O4 is now historical context for those arcs' production substrate.

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

## Advanced Security Arcs & Capabilities

Since the completion of Phase O4, the QorTroller protocol has integrated several state-of-the-art security features and cryptographic primitives to protect against hardware virtualization, trace injection, and backdating attacks:

### 1. Proof of Session Recency (PoSR - Arc 6) **— REGISTRY LIVE 2026-06-05**
* **Goal**: Defends against replay backdating, pre-computation trace generation, and stale session re-listing attacks.
* **Mechanism**: Binds the creation and validation of gameplay records directly to recent IoTeX L1 blockhashes. The [VAPITemporalBeaconRegistry](file:///C:/Users/Contr/vapi-pebble-prototype/contracts/contracts/VAPITemporalBeaconRegistry.sol) records block hashes at a defined cadence (`ANCHOR_CADENCE=64` per `INV-TBR-002`). The [PoSRBeaconBinder](file:///C:/Users/Contr/vapi-pebble-prototype/bridge/vapi_bridge/replay_proof_pipeline/posr.py) binds the session commitments to these beacon blocks.
* **Deploy status**: Registry **LIVE on IoTeX testnet** at `0x962440312a995b21d4E203bE6d93021CC22bA051` (tx `0x7d87bdef…0140`, block 44355513, 2026-06-05). `INV-TBR-001` (BEACON_DOMAIN keccak256 pin) + `INV-TBR-002` (ANCHOR_CADENCE pin) byte-equal-checked at deploy. Next operator-fired ops: `reg.setKeeper(...)` + first `anchorBeacon(...)`.
* **Verification**: Uses `VAPIReplayProofVerifier_v2.circom` which enforces Groth16 circuit-level temporal ordering of sessions (close block > open block) and re-hashes commitments using in-circuit Poseidon structures. The v2 wrapper deploy remains operator-interactive snarkjs-ceremony-gated; until ceremony fires, VHR proofs land in v1 Arc 5 behavior (no recency upgrade) and the bridge's PoSR binder returns `None` honestly — never fabricates a beacon claim.

### 2. Verified Human Replay (VHR - Arc 5)
* **Goal**: Proves raw gameplay liveness using downsampled, non-invertible replay matrices.
* **Mechanism**: A multi-stage pre-processor converts 1000 Hz HID reports into a 60 Hz median window containing stick radial sectors (4-bit), trigger thresholds, and IMU gravity-sign octants. Critical biometric features are strictly filtered out (Data Floor enforcement).
* **On-Chain Verification**: The [VAPIReplayProofVerifier](file:///C:/Users/Contr/vapi-pebble-prototype/contracts/contracts/VAPIReplayProofVerifier.sol) re-hashes the sanitized trace root using off-circuit Poseidon sponge commitments to run Groth16 verify checks. Integrates with the [VAPIConsentManifestRegistry](file:///C:/Users/Contr/vapi-pebble-prototype/contracts/contracts/VAPIConsentManifestRegistry.sol) to ensure players consent to replay tracing.

### 3. Path A: Silicon-Rooted Hardware Identity (Path A Arc 1)
* **Goal**: Upgrades the security boundary from host-held software keys (Path B) to silicon-rooted secure elements (e.g., ATECC608A) embedded directly in the controller hardware.
* **Mechanism**: Introduces the [VAPIManufacturerDeviceRegistry](file:///C:/Users/Contr/vapi-pebble-prototype/contracts/contracts/VAPIManufacturerDeviceRegistry.sol) which registers hardware birth certificates signed by the Manufacturer Root CA.
* **Composability**: Exposes [VAPIProtocolLensV2](file:///C:/Users/Contr/vapi-pebble-prototype/contracts/contracts/VAPIProtocolLensV2.sol) which allows calling contracts to verify eligibility of Path A silicon devices via a single view-call (`isFullyEligible_PathA()`).

### 4. Guardian KMS-HSM & Signature Anchoring
* **Goal**: Secures the operator actions of the Guardian agent using Cloud HSMs.
* **Mechanism**: Operator actions and audit logs are signed using an AWS KMS HSM (secp256k1).
* **On-Chain Commitments**: Guardian's operational signatures are anchored to the [AdjudicationRegistry](file:///C:/Users/Contr/vapi-pebble-prototype/contracts/contracts/AdjudicationRegistry.sol) as immutable cryptographic commitments.

### 5. Embodied Presence & L9 Presence Arc
* **Goal**: Establishes player presence on the controller through physical force dynamics and challenge-responses rather than biometric fingerprint templates.
* **Mechanism**: The Proof of Embodied Presence (PoEP) challenge-response requires nonce-bound player reflexes, wrapping feature commitments using post-quantum hybrid signatures (ECDSA + ML-DSA-65/IIP-64).

### 6. Arc 7 — Post-Quantum Cryptographic Sidecar
* **Goal**: Forward-secures the Arc 6 PoSR verification path against post-quantum signature threats without modifying any FROZEN-v1 surface (additive integration).
* **Mechanism**: A `pqCommitment` (bytes32) parameter is threaded through `VAPIReplayProofVerifier_v2.verifyWithRecency` and `verifyWithRecencyView`; the registry's `verifyBeacon(blockNumber, claimedHash, pqCommitment)` enforces non-zero commitment (`require(pqCommitment != bytes32(0), "VAPI: Zero PQ Commitment Disallowed")`). The PQ commitment binds an off-circuit post-quantum proof artifact alongside the beacon hash; the registry remains opaque to the PQ algorithm choice (forward-compatible with ML-DSA, SLH-DSA, or hybrid composites).
* **Ingestion-loop isolation**: The VHR prover task is offloaded to **Thread C** via `asyncio.to_thread`, preventing PQ-signing overhead (which can be 10–100× ECDSA-P256 cost depending on PQ scheme) from jittering the 1002 Hz HID ingestion ring buffer. Matches Phase 235.x-STABILITY's loop-block discipline.
* **Test coverage**: T-VHR-V2-8 explicitly asserts the zero-pqCommitment revert; Arc 6 wrapper tests pass all 18 assertions including the additive PQ binding path.
* **Deploy status**: PQ sidecar code path BUILT + integrated; **v2 wrapper deploy remains operator-interactive snarkjs-ceremony-gated** (Groth16 trusted-setup contribute step requires physical operator input). Arc 7 PQ functionality only activates against a deployed v2 wrapper; current production stays on v1.

### 7. Arc 2 — Buyer-Category ZK Gating **— DEPLOYED 2026-06-05**
* **Goal**: Cryptographic gating of buyer-side marketplace queries by category eligibility, without exposing the buyer's full identity or query plan.
* **Mechanism**: A Groth16 verifier wrapper validates buyer-category proofs against an on-chain trusted-setup verifying key. Pairs with Curator's marketplace listing flow to scope which gamer-listed bundles a given buyer is eligible to query.
* **Deploy status**: `VAPIBuyerCategoryVerifier` **LIVE on IoTeX testnet** at `0x5B1D82AAc2FD662f8850C49e40A94573f624440A` (tx `0x578c6e3e…7fa3`, block 44355501, 2026-06-05).

### 8. World Model Provenance Lane (WMP) — Architectural Blueprint
* **Goal**: Package + export + consumer-verify provenance-attested human-action traces for world-model researchers and labs who currently lack a cryptographically-verifiable source of real (human, recent, consenting) demonstration data — the bottleneck Fei-Fei Li / World Labs explicitly named in *A Functional Taxonomy of World Models* (June 2026).
* **Honest placement**: QorTroller is **NOT** a world model. It does not output pixels (renderer), state (simulator), or actions (planner). It instruments the **agent→action edge** of a real human in the loop and stamps that edge with cryptographic provenance. WMP is the lane that packages this provenance for consumers who need trustable demonstration data.
* **Architecture**: Additive lane built on Arc 5 (VHR humanity proof) + Arc 6 (PoSR recency proof) + Arc 4 (consent reference). Assembles a `ProvenanceBundle v1` per consented session; ships a JSONL exporter; and ships a **consumer-side verifier** with five checks: humanity proof, **Poseidon matrix↔root re-hash** (canonical home — closes the long-open Arc 5 off-circuit finding), recency beacon, consent, scope honesty.
* **Honesty rails**: Post-φ sanitized data only (60 Hz, 4-bit quantized; FORBIDDEN_COLUMNS-wiped). Action channel only — never the observation channel (no framebuffer capture; permanently forbidden by data floor). Real sessions only — synthetic data would void the falsifiable empirical claim. No generative model. No human-likeness scoring oracle. Action exports carry no liveness-grade biometric signal — the anti-cheat moat lives in the high-frequency micro-tremor variance that φ destroys.
* **W1-D operator decision (2026-06-05)**: Ship full lane on fixtures (no real-data export tonight); deferred-export guard hard-coded to `False` in v1; minimal greenfield `VAPIWorldModelConsentRegistry` (single `gamer => bool` mapping, `setWorldModelConsent` gated by `msg.sender == gamer`) shipped as Solidity + hardhat test in a flagged Phase-2 commit (no on-chain deploy tonight). Preserves cryptographic verifiability of consent, sidesteps Arc 4 v2 storage-layout-freeze migration, distinct from replay consent.
* **Status**: Architectural blueprint published; commit plan WMP-1 through WMP-5 written against W1-D; implementation pending operator authorization.

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

## In-Depth Architectural Assessment

For an in-depth exploration of QorTroller's underlying design, including its zero-trust physics-based anti-cheat paradigm, detailed breakdown of the Physical Input Trust Layer (PITL L0–L9) signals, Proof of Session Recency (PoSR) replay defenses, and player data privacy protection details, see the [QorTroller Architecture Assessment](file:///C:/Users/Contr/vapi-pebble-prototype/docs/QORTROLLER_IN_DEPTH_ASSESSMENT.md).

---

## Contact

Issues, security disclosures, and partnership inquiries should be filed via GitHub Issues on this repository or directed to the author through Zenodo's contact path on the v3 DOI page.

---

*QorTroller is the reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.) — a Decentralized Physical Infrastructure (DePIN) sub-category — for competitive gaming on IoTeX. This repository contains the canonical implementation as of Phase O4-VPM-INTEGRATION close — architecture anchor `e81e04aa` (2026-05-13), documentation commit `9f8581cd`. Brand-rename QRESCE-0001 v0.5 landed 2026-05-18 (codebase identifiers preserve `VAPI` as categorical references per Layer C FROZEN-v1 discipline; project identity displays as **QorTroller** per medial-cap brand convention).*
