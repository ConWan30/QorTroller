# QorTroller — Architecture

**One-page reference** for grant reviewers, Stage A research recruits, and contributors.
Detail lives in `CLAUDE.md` + `wiki/`. This file is the on-ramp.

## What it is

QorTroller is the reference implementation of **Verifiable Autonomous Physical Intelligence (V.A.P.I.)** — a DePIN sub-category for protocols where the physical-input source is also the cryptographic agency-holder over the data those interactions generate. In QorTroller's case: a competitive gamer holding a certified controller is the only party that can sign attestations about that controller's outputs. The controller's silicon roots the trust; the gamer's wallet roots the consent.

## Pipeline

```
┌───────────────────────────────────────────┐
│ DualSense Edge — Sony CFI-ZCP1            │
│ 1002 Hz HID polling, IMU, adaptive trigger│
└──────────────────┬────────────────────────┘
                   │ raw inputs + sensor commitments
                   ▼
┌───────────────────────────────────────────┐
│ bridge/vapi_bridge/  (Python asyncio)     │
│ • PITL L0–L5 deployed; L6 default-OFF;    │
│   L7/L8 spec-only                         │
│ • 29 standalone + 3 steward agents        │
│   (Sentry / Guardian / Curator)           │
│ • ZK prover (Groth16 BN254, ~1.8k constr.)│
│ • Arc 7 PQ sidecar (ML-DSA-65 off-chain)  │
└──────────────────┬────────────────────────┘
                   │ 228-byte PoAC + sidecar commits
                   ▼
┌───────────────────────────────────────────┐
│ IoTeX Testnet — chain ID 4690             │
│ PoAC verifier · VHP · Consent registries  │
│ Marketplace · Cedar policy anchors · KMS  │
└──────────────────┬────────────────────────┘
                   │
                   ▼
   Frontend dApps · Curator marketplace · Operator fleet
```

## FROZEN-v1 cryptographic primitive families

PATTERN-017: each family pins a domain tag, a preimage formula, and an invariant that fails CI closed if drift occurs. Selected 8 of 14 families below; the full set lives in `scripts/vapi_invariant_gate.py` (174 pinned invariants as of 2026-06-10).

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
| Solidity source files in `contracts/contracts/*.sol` | 80 | `ls contracts/contracts/*.sol \| wc -l` |
| Deployed addresses on IoTeX testnet | 68 | `contracts/deployed-addresses.json` (count of 0x-prefixed string values) |
| Substantive (excludes mocks + superseded versions) | ~55 | per `README.md` headline; manual roll-up |

The 80 ↔ 68 gap = mocks / test verifiers / library helpers / undeployed candidates. The 68 ↔ 55 gap = superseded versions (e.g., `VAPIProtocolLens_v1_superseded`) + auxiliary registries.

## Honest status (2026-06-10)

1. **Testnet only.** IoTeX testnet chain ID 4690. Zero mainnet deploys. `CHAIN_SUBMISSION_PAUSED=true` kill-switch in `bridge/.env`.
2. **N=3 calibration corpus.** AIT separation ratio 1.199 at N=37 (above 1.0 — defensibility gate CLEAR); touchpad_corners 0.728 at N=35 (below — tournament blocker); per-pair P1×P3 = 0.032 fails `all_pairs_p0_ok`.
3. **Stage A measurement gates OPEN** for both BT calibration v1.1 and L4 sensor-stack v2.1 — see `wiki/methodology/bt_calibration_v1_1_architectural_revision.md` + `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`.
4. **No external Solidity audit yet.** Slither static-analysis gate added 2026-06-09 (report-only first pass).
5. **No fiat or token launch.** TGE gate is non-negotiable on `all_pairs_p0_ok=True` AND N≥100 live adjudications AND external smart-contract audit.

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
bridge/        Python asyncio bridge + 29 agents + ZK prover
contracts/     80 Solidity 0.8.20 sources, IoTeX EVM (P256 precompile @ 0x0100)
sdk/           Python SDK (604 tests)
scripts/       Static-analysis gate, backup_store.py, ZKBA compilers, audits
frontend/      Vite + React operator console + gamer dashboards
w3bstream/     Rust applet → wasm32-unknown-unknown ingestion sandbox
wiki/          Methodology, phase archive, assessments, runbooks
l9_presence/   PoEP / L9-PoCP / BCC / GCAP standalone sub-project
audits/        Static-analysis baselines, decon-1 maps, prior-art audits
```

## License

Source available for inspection and security audit. No open-source license is declared. Commercial integration requires explicit license agreement with the QorTroller Foundation. Contact via the GitHub repo issues.
