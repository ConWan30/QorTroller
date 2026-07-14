# QorTroller — Architecture

**One-page reference** for grant reviewers, Stage A research recruits, and contributors.
Detail lives in `CLAUDE.md` + `wiki/`. This file is the on-ramp.

## What it is

QorTroller is the reference implementation of **Verifiable Autonomous Physical Intelligence (V.A.P.I.)** — a DePIN sub-category for protocols where the physical-input source is also the cryptographic agency-holder over the data those interactions generate. In QorTroller's case: a competitive gamer holding a certified controller is the only party that can sign attestations about that controller's outputs. The controller's silicon roots the trust; the gamer's wallet roots the consent.

## Pipeline

```
┌───────────────────────────────────────────┐   ┌─────────────────────────────────┐
│ DualSense Edge — Sony CFI-ZCP1            │   │ HDMI capture card (UVC 1080p60) │
│ 1002 Hz HID polling, IMU, adaptive trigger│   │ retina: killfeed OCR authorship │
└──────────────────┬────────────────────────┘   └───────────────┬─────────────────┘
                   │ raw inputs + sensor commitments             │ observation plane
                   ▼                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ bridge/vapi_bridge/  (Python asyncio)          ASSERTION ∥ OBSERVATION planes    │
│ • PITL L0–L5 deployed; L6 default-OFF; L7/L8 spec-only                           │
│ • 29 standalone + 3 steward agents (Sentry / Guardian / Curator)                 │
│ • ZK prover (Groth16 BN254) — first REAL replay proof verified on-chain 2026-07  │
│ • Arc 7 PQ sidecar (ML-DSA-65 off-chain) · W3bstream wasm mechanical verify      │
│ • PoSP synchronized-presence + kill-authorship (~17/17 witnessed live 2026-07-13)│
└──────────────────┬──────────────────────────────────────────────────────────────┘
                   │ 228-byte PoAC + sidecar commits + session proof roots
                   ▼
┌───────────────────────────────────────────┐   ┌─────────────────────────────────┐
│ IoTeX Testnet — chain ID 4690             │   │ qortroller product CLI + UI     │
│ PoAC verifier · VHP · Consent registries  │◄──│ setup/play/stop/receipt/score/  │
│ Marketplace · beacons · node-ledger anchor│   │ ledger/anchor · StreamView SPA  │
└──────────────────┬────────────────────────┘   └─────────────────────────────────┘
                   ▼
   DePIN node: derived node_id · contribution ledger · first anchor block 45613440
```

## FROZEN-v1 cryptographic primitive families

PATTERN-017: each family pins a domain tag, a preimage formula, and an invariant that fails CI closed if drift occurs. Selected 8 of **15** families below (the 15th: `VAPI-RETINA-STATE-v3`, promoted candidate→FROZEN by operator seal 2026-07-12); the full set lives in `scripts/vapi_invariant_gate.py` (**183** pinned invariants as of 2026-07-13). Candidate (non-FROZEN, REFERENCE-AND-BIND) tags also exist — e.g. `QORTROLLER-POSP-v0`, `QORTROLLER-NODE-v0`, `QORTROLLER-NODE-LEDGER-v0` — 42 distinct byte-string domain tags total.

| Family | Domain tag | Commits | Verified at |
|---|---|---|---|
| PoAC wire | `codec.py` | 228 B record (164 body + 64 sig); chain hash SHA-256(raw[:164]) | INV-001 / INV-002 |
| Grind Integrity Chain | `b"VAPI-GIC-GENESIS-v1"` | session-by-session cognitive continuity | INV-GIC-001/002/003 |
| Watchdog Event Chain | `b"VAPI-WEC-GENESIS-v1"` | bridge process operational continuity | Phase 236-WATCHDOG |
| Corpus Snapshot | `b"VAPI-CORPUS-SNAPSHOT-v1"` | wiki + agent root + ratio + corpus N + ts | Phase 236-CORPUS-SNAPSHOT |
| Biometric Snapshot | `b"VAPI-BIOMETRIC-SNAPSHOT-v1"` | sanitized biometric trace root + N | Phase 237-ZK-SEPPROOF |
| Consent | `b"VAPI-CONSENT-v1"` | gamer-sovereign consent receipt | Phase 237-CONSENT |
| Fleet Readiness Root | `b"VAPI-FRR-v1"` | 3-agent phase-state attestation | Phase O1-FRR-PARALLEL |
| Temporal Beacon (PoSR) | `b"VAPI-TEMPORAL-BEACON-v1"` | session open/close ↔ IoTeX blockhash | Arc 6 (`INV-TBR-001/002`) |

Other live families: `VAPI-AGENT-COMMIT-v1`, `VAPI-VAME-v1`, `VAPI-ZKBA-ARTIFACT-v1`, `VAPI-CEDAR-BUNDLE-v1`, `VAPI-LISTING-v1`, `VAPI-O3-SUPERSEDE-v1`, `QORTROLLER-IPACT-RENEWAL-v1`. Source: `grep -rE 'b"(VAPI|QORTROLLER)-[A-Z0-9-]+-v[12]"' bridge/ l9_presence/`.

## Contracts — live vs code-complete

| Surface | Count | Source |
|---|---|---|
| Solidity source files in `contracts/contracts/*.sol` | 82 | `ls contracts/contracts/*.sol \| wc -l` (2026-07-13) |
| Deployed contract addresses on IoTeX testnet | 69 | addr-shaped non-meta keys in `deployed-addresses.json` (Sensor-A live-verified 2026-07-13; +3 since the 66-count audit, incl. `VAPIWorldModelConsentRegistry` 2026-07-11) |
| Currently-active (excludes superseded + deprecated-by-versioning) | ~61 | `audits/contract-status-cycle-15-2026-06-13.md` classified 58-of-66 ACTIVE / 3 SUPERSEDED / 5 deprecated-by-versioning; the 3 post-audit deploys are active |

The 82 ↔ 69 gap = mocks / test verifiers / library helpers / undeployed candidates. Superseded contracts (e.g., `VAPIProtocolLens_v1_superseded`) remain on-chain and callable — supersession is a classification overlay, not a removal.

## Honest status (2026-07-13)

1. **Testnet only.** IoTeX testnet chain ID 4690. Zero mainnet deploys. `CHAIN_SUBMISSION_PAUSED=true` kill-switch in `bridge/.env`; every chain write is operator-fired, estimate-first, hard-capped.
2. **Proven live, single-operator:** first REAL Groth16 replay proof verified on-chain (block 45479067); PoSP synchronized presence across three evidence surfaces; kill-feed authorship recall ~17/17 witnessed in a live match (2026-07-13; zero false authorship across ~850 reads); first certified-human WMP data bundle VERIFIED 5/5; **DePIN node born + first contribution anchored** (tx `0xb985f035…`, block 45613440). All `developer_self` scope — one gamer, who is also the operator.
3. **N=3 calibration corpus.** AIT separation ratio 1.199 at N=37 (defensibility gate CLEAR); touchpad_corners 0.728 at N=35 (tournament blocker); per-pair P1×P3 = 0.032 fails `all_pairs_p0_ok`. AUTHORED (causal, hygiene-gated) kill binding awaits the HID-topology/PoEP seam — witnessed ≠ authored, and the artifacts say which is which.
4. **Stage A measurement gates OPEN** for BT calibration v1.1 and L4 sensor-stack v2.1 — see `wiki/methodology/`.
5. **No external Solidity audit yet.** Slither static-analysis gate added 2026-06-09 (report-only first pass).
6. **No fiat or token launch, nothing for sale.** TGE gate is non-negotiable on `all_pairs_p0_ok=True` AND N≥100 live adjudications AND external smart-contract audit.

## Deeper docs

- `CLAUDE.md` — full project state, gotchas, phase table, hard rules (~76 k chars).
- `docs/disaster-recovery-runbook.md` — total-loss recovery (DECON-1 Stream 3).
- `wiki/methodology/` — POMDP framing, BT canonical anchor, sensor-stack v2.1 anchor.
- `wiki/assessments/` — third-party-readable architectural framings.
- `wiki/phases/` — phase archive (Phases 17–229+ summary + per-phase wikis).
- `audits/decon-store-map.md` — Stream 2 store partition map.
- `docs/vapi-whitepaper-v4.md` — protocol whitepaper (DOI pending; v3 at Zenodo `10.5281/zenodo.18966169`).

## Repository layout

```
bridge/        Python asyncio bridge + 29 agents + ZK prover + retina capture
contracts/     82 Solidity 0.8.20 sources, IoTeX EVM (P256 precompile @ 0x0100)
sdk/           Python SDK (647 tests collected)
scripts/       qortroller product CLI, invariant gate, A2A relay bus, anchors, audits
frontend/      Vite + React operator console + StreamView gamer environment
w3bstream/     Rust applet → wasm32-unknown-unknown mechanical-verify sandbox
wiki/          Methodology, phase archive, assessments, runbooks
l9_presence/   PoEP / L9-PoCP / kill-authorship / PoSP standalone sub-project
audits/        Session proofs (receipts/scorecards/PoSP/v3), drift artifacts, maps
docs/a2a/      The AI-to-AI engineering loop rounds (PKG/HARD/VALID/DEPIN/STREAM)
```

## License

Source available for inspection and security audit. No open-source license is declared. Commercial integration requires explicit license agreement with the QorTroller Foundation. Contact via the GitHub repo issues.
