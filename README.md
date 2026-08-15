# QorTroller — Core Controllers of their gaming data

[![GitHub](https://img.shields.io/badge/github-ConWan30%2FQorTroller-181717?logo=github)](https://github.com/ConWan30/QorTroller)
[![Website](https://img.shields.io/badge/website-GitHub%20Pages-blue)](https://conwan30.github.io/QorTroller/)
[![Discussions](https://img.shields.io/badge/discussions-open-orange)](https://github.com/ConWan30/QorTroller/discussions)
[![Wiki](https://img.shields.io/badge/wiki-operator%20notes-informational)](https://github.com/ConWan30/QorTroller/wiki)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18966169.svg)](https://doi.org/10.5281/zenodo.18966169)

> **The reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.)** — a Decentralized Physical Infrastructure (DePIN) sub-category coined to describe protocols where the physical-input source is also the cryptographic agency-holder over the data those physical interactions generate. In QorTroller's case: gamers and their controllers, producing data, owning that data.
>
> Built native to IoTeX's Internet of Trusted Things foundation. Anchored on IoTeX L1. Composable as a single on-chain call. Designed so cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty.

**V.A.P.I.** — pronounced as the acronym; styled with periods to distinguish from unrelated similarly-named projects in other categories. As a coined DePIN sub-category, V.A.P.I. is the conceptual scope; QorTroller is the project that implements it for competitive gaming.

### Parent truth plane · sibling observation plane

| Plane | Repo | What it is |
|---|---|---|
| **Truth (this repo)** | [ConWan30/QorTroller](https://github.com/ConWan30/QorTroller) | Cryptographic receipts, consent, eligibility, gamer sovereignty |
| **Observation** | [ConWan30/Qoresence](https://github.com/ConWan30/Qoresence) | Local HDMI + DualSense glasses. No humanity / chain claims by default |

Compose them. Do not merge optical activity into `poep_enabled`. Qoresence site: [conwan30.github.io/Qoresence](https://conwan30.github.io/Qoresence/). This site: [conwan30.github.io/QorTroller](https://conwan30.github.io/QorTroller/).

### Start here — no secrets required

Anyone else can use this repository without a GitHub PAT, wallet key, Buzz `nsec`, or `bridge/.env`. Those stay on the operator machine.

```powershell
git clone https://github.com/ConWan30/QorTroller.git
cd QorTroller
python scripts/vapi_invariant_gate.py          # fail-closed protocol invariants
python scripts/verify_wmp_ladder.py            # stranger re-check of the published bundle
```

- **Read:** this README · [SECURITY.md](SECURITY.md) · [PRIVACY.md](PRIVACY.md) · [CONTRIBUTING.md](CONTRIBUTING.md)
- **Talk:** [Discussions](https://github.com/ConWan30/QorTroller/discussions) · [Wiki](https://github.com/ConWan30/QorTroller/wiki)
- **Do not commit:** `.env`, PATs, wallet keys, `nsec` values, `sessions/` captures. Copy `*.env.example` locally only.

Hardware capture, Buzz posting, and IoTeX writes are **opt-in operator paths**. They are documented below. They are not required for a stranger to verify the public claim surface.

**Author:** Contravious Battle (Independent Researcher) · **Network:** IoTeX testnet (chain ID 4690) · **Phase:** PATH A ARC 1 + DATA ECONOMY ARC 2 + ARC 4 + ARC 5 + ARC 6 **DEPLOYED**; ARC 7 PQ SIDECAR BUILT (v2 wrapper ceremony-gated); Trio-Retina + CCO×PoEP Fusion + L9 coupled-retina presence BUILT (advisory, default-OFF); **PoSP synchronized presence + kill-authorship (live RP authored) + first real on-chain ZK replay proof + PORT-CERT full VERIFIED + organizer pilot package SHIPPED (2026-07); WMP data-economy Phase-2 LIVE — first certified-human action-demonstration bundle VERIFIED 5/5, the gamer's own wallet signing consent on-chain (2026-07-11); DEPIN NODE LIVE — node born from the registered controller, kill-feed recall proven ~17/17 witnessed live, first contribution ANCHORED on IoTeX block 45613440, operator-fired (2026-07-13)** — **public repo · IoTeX testnet** · **Date:** 2026-07-13

## In plain English — what this actually is

When you play a competitive match, QorTroller watches two things: the **screen** (like security-camera footage) and your **controller's real physical signals** (like door-badge swipes). After the match it seals both into a tamper-evident **receipt** proving a real human was at the controller and that *their* trigger pulls caused the kills on screen. Anyone — a tournament organizer, a rival, a journalist — can re-check that receipt with one command, without trusting us.

**What it catches:** the "nobody's-actually-there" cheats — bots, replays, account farms, remote input streaming — exactly the class that's invisible to normal anti-cheat when a match runs over cloud gaming or Remote Play.
**What it doesn't:** a real human using an aimbot (they're genuinely present), or *which* human is playing. It's one honest layer, built to stack with existing tools.

### Two engines on one controller — and the gamer owns both

That same receipt has a second life. The proof that *a real human produced real inputs* is exactly what the AI industry is now starved for — as the internet fills with machine-generated content, **provably-human** data gets rarer and more valuable, and labs training agents that *act* (game bots, robots) specifically lack real human demonstrations. So QorTroller runs as **two engines on one pipeline**: catch cheaters on one side, and mint **certified-human action data** on the other — from the very same match, the very same proofs.

**"Core Controllers of their Data" is the load-bearing part.** The person holding the controller holds the keys. Whether that data is ever shared or sold is granted and revoked by the **gamer's own wallet signature** on-chain — the system is built so we *structurally cannot* do it for them (a Solidity `msg.sender == gamer` check the bridge can never satisfy). The anti-cheat model most projects use is zero-sum, protocol *vs.* gamer; QorTroller inverts it — the gamer is the sovereign supplier, not the surveilled subject.

**Proven, not promised (2026-07-11):** the first real match was packaged as a certified-human data bundle, and **anyone can verify the whole data-economy ladder with one command — trusting us for nothing, installing nothing.** Clone the repo and run `python scripts/verify_wmp_ladder.py` (pure Python standard library, no dependencies, no network). It re-checks every rung over the real published bundle: the certified export, the hardened zero-trust verifier (which we hardened by *forging our own data* — and fixed a real gap it exposed), the gamer's verifiable derived claims, selective disclosure, and the ceremony-/breadth-gated rungs (honestly deferred, never faked). For the full cryptographic legs — real Groth16 humanity proof, on-chain consent view-call, Poseidon matrix↔root — add `--full` (needs Node + snarkjs). One-page walkthrough: **[Verify it yourself](docs/wmp-verify-it-yourself-brief-2026-07-11.md)**.

**Today's grade:** advisory pilot + demonstration on a test network — a smoke detector, not a judge; a *proof the machine works*, not a data business yet. One match, by one person, no buyer, **no token and nothing for sale**. The honest limits are stated in every artifact.

*(Organizer-facing plain-English docs: [pilot walkthrough](docs/pilot-organizer-walkthrough-2026-07-10.md) · [pilot one-pager](docs/pilot-organizer-onepager-2026-07-10.md) · [ops runbook](docs/pilot-ops-runbook-2026-07-10.md). Data-economy: [WMP first-bundle report](audits/wmp-phase2-first-real-bundle-2026-07-11.md) · [ecosystem portfolio](docs/wmp-data-ecosystem-portfolio-2026-07-11.md).)*

| Surface | Status |
|---|---|
| **Bridge tests** | ~6,462 collected (pytest --collect-only, 2026-07-25); see `docs/a2a/ci-debt/backlog.md` for the named-failures ledger |
| **SDK tests** | 647 collected (pytest --collect-only, 2026-07-25) |
| **Hardhat contract tests** | **760 passing** (13 pre-existing unrelated failures, see baseline) |
| **Frontend Vitest** | **155 passing** (Consent Cockpit + VHR Proof Panel additions, 2026-06-04/05) |
| **PV-CI invariant gate** | **184 / 184 pinned** (`scripts/vapi_invariant_gate.py` verified `PASS — 184` 2026-07-25), governance-ceremony-locked; CI-enforced on every PR. Verified locally with `make init` (submodule init) since two firmware-pinned invariants live inside `bridge/firmware/joypad-os` and require it. |
| **FSCA contradiction rules** | 28 active |
| **Contracts LIVE on IoTeX testnet** | **69 deployed** (chain 4690; +3 since the 2026-06-13 contract-status audit `audits/contract-status-cycle-15-2026-06-13.md`, which counted 66 = 58 ACTIVE / 3 SUPERSEDED / 5 deprecated-by-versioning — the +3 are the Arc 7 v2 replay-verifier pair + the WMP-4 world-model consent registry). All remain on-chain and callable; supersession is a classification overlay. See `contracts/deployed-addresses.json`. Recent deploys: **WMP-4 `VAPIWorldModelConsentRegistry` `0x06836Fb8…` (block 45534708, 2026-07-11)**; **Arc 2 `VAPIBuyerCategoryVerifier` `0x5B1D82AA…` (block 44355501, 2026-06-05)**; **Arc 6 `VAPITemporalBeaconRegistry` `0x96244031…` (block 44355513, 2026-06-05)**; Arc 5 v1 `VAPIReplayProofVerifier` `0x5182372d…` (block 44053167, 2026-05-30) |
| **Gamer-facing dApps** | **Consent Cockpit at `/consent`** — first standalone gamer-sovereign consent surface in the protocol (Cockpit F1–F5 shipped 2026-06-05); `BRIDGE NEVER GRANTS OR REVOKES CONSENT` invariant displayed as headline UX, signing always `msg.sender == gamer` |
| **Operator Initiative agents** | **3 LIVE at O3_ACTING** (Sentry / Guardian / Curator) — first ≥3-agent fleet at full action authority in any DePIN gaming protocol; ceremony fired live 2026-05-17, Fleet Readiness Root `0x54b4b698…` permanently anchored |
| **ZKBA artifact classes** | 7 of 7 shipped (Layer 7 closed) |
| **VPM compilers active** | 6 (4 internal + 2 consumer-facing) |
| **Cryptographic chain primitives** | **14 FROZEN-v1 (PATTERN-017)** including #14 `VAPI-TEMPORAL-BEACON-v1` (Arc 6 PoSR, FROZEN 2026-05-30, registry now LIVE 2026-06-05) |
| **Arc 7 — PQ cryptographic sidecar** | `pqCommitment` parameter threaded through Arc 6 verification path (`verifyWithRecency`, `verifyBeacon`); registry rejects zero commitments; Thread C `asyncio.to_thread` prover offload prevents ingestion-loop jitter. v2 wrapper deploy operator-interactive snarkjs ceremony-gated. |
| **First gamer-self-sovereign consent manifest on-chain** | Written 2026-06-05 from real wallet (`0x0Cf36dB57…`) to `VAPIConsentManifestRegistry` at `0x5F7c8068…` — tx `0xd02c051e…20bd` block 44354567, `allowReplayProofs=true` verified on-chain. Gamer-self-sovereignty invariant verified by Solidity `msg.sender == gamer` check; bridge structurally incapable of writing this. |
| **GIC_100 cognitive chain head** | Permanently anchored 2026-05-06 (block 43348052) |
| **World Model Provenance Lane (WMP) — Phase-2 LIVE (the data economy)** | **UC-1 LIVE 2026-07-11.** The lane that turns anti-cheat evidence into a certified-human action-demonstration product for AI/world-model consumers — action-channel-only, post-φ sanitized, the biometric moat never exports. **First real bundle VERIFIED 5/5 zero-stub** (`wmp_corpus_real/wmp_corpus.jsonl`): a stranger runs `scripts/wmp_full_verify.py` and cryptographically confirms real-human (snarkjs Groth16) + on-chain consent (live `isWorldModelConsentGranted` view-call) + matrix↔root (Poseidon, closing the long-open Arc 5 off-circuit finding) with zero trust in us. Recency explicitly-deferred on M17 (one anchored beacon; next keeper-anchored match = true 5/5). `VAPIWorldModelConsentRegistry` deployed `0x06836Fb8…` (block 45534708); first gamer-signed `setWorldModelConsent(true)` tx `0x8f70bca3…` (block 45534743, `msg.sender == gamer`). Ceilings: `developer_self`, N=1, no buyer implied, TGE frozen. Report `audits/wmp-phase2-first-real-bundle-2026-07-11.md`; blueprint `docs/world-model-provenance.md`. |
| **Gamer data-economy portfolio (UC-1..15)** | **The three-ring economy, documented + partly built:** the gamer self-consumes their own verified output (the inner ring is SHIPPED — [play-résumé](l9_presence/play_resume.py) · [skill-strata](l9_presence/skill_strata.py) · [self-analytics](l9_presence/self_analytics.py), all off-rig, verify-or-refuse); skill-structured corpora + services sell to labs/studios/organizers (UC-1 LIVE, others code-only-gated); the network itself produces via fleet/federation/flywheel. Financial/derivative and data-DAO lenses CLOSED-BY-RAIL (TGE frozen). Full catalog: `docs/wmp-data-ecosystem-portfolio-2026-07-11.md`. |
| **Daemon Brain** | **30-tool persistent cognitive layer** (`qortroller_daemon.py`) — hive-mind architecture with CLI + TUI rendering clients; QuickSilver API (`claude-sonnet-4-6`, switched from deepseek-v4-flash 2026-06-16); **Tier 1–3 governance fences** (`verify_artifact` anti-fabrication, `extract_with_diff` deterministic reconstruction, `propose_edit`/`finalize_plan` propose-only, health monitor); drove the DECON-2 monolith decomposition under fences; SQLite shared memory across sessions; QorTroller-native tools: GIC chain visualizer, live IoTeX on-chain queries, Mythos audit runner, GIC cryptographic replay, calibration status |
| **CI matrix** | GitHub Actions: Python 3.10/3.11/3.12 × Node 18/20 + Rust stable + WASM target enforcing the 184-invariant gate on every PR. Governance gates (PV-CI, Mythos, Path Scope) green; full integration matrix has tracked pre-existing toolchain debt (hardhat-ABI ordering) under repair — branch-protection draft proposes making the governance gates blocking. **Caveat as of 2026-07-25:** the bulk of the documented ci-debt-cleanup work lives unmerged on `origin/fix/ci-debt-backlog` (~280 net commits diverged from `main`); a fresh clone of `main` carries every named-but-unfixed item in `docs/a2a/ci-debt/backlog.md`. See that file's 'Update, fifth pass' section for details. |
| **Trio-Retina (advisory perception oracle — RESEARCH, default-OFF)** | **BUILT through Phase 3, NOT live** — controller-embed → perception → `retina_state_commitment` → Poseidon `events_root` (off-chain ZK-prep) → on-chain PDA attestation; W3bstream `retina_state_commitment` validation + DA bulk/witness sidecar (same decoupled-pointer pattern as Arc 7 PQ). Wired read-only into `session_adjudicator` as a second forensic oracle; **does NOT touch the 228-byte PoAC wire** (`RETINA_PERCEPTION_ENABLED`/`RETINA_DA_WITNESS_ENABLED` default false in production). Tests live in `bridge/tests/test_retina_*`. Only the operator can flip these flags. |
| **CCO × PoEP Fusion (two-axis — identity × presence, advisory PRESENT verdict)** | **Phases A–F shipped; live verdict operator-gated (default-OFF)** — `CapabilityOracle` + `ChallengeVerifier` (Edge `adaptive_force` + measured DualSense `rumble_imu`) + identity×presence grid + off-chain composability on `GET /player/session-status`. **Phase G measurement VALIDATED + operator-attested** under `developer_self` scope: PREMIUM_EDGE `sony_dualshock_edge_v1` N=210, MID_TIER `sony_dualsense_v1` N=130 (HUMAN N=50, FRR proxy 0.0); MINIMAL_PAD deferred (no hardware). Live PoEP `PRESENT` verdict remains **operator-gated** (default-OFF, N≥50 corpus + env flip) — the operator-attested measurements are NOT live on production matches. |
| **PoSP + kill-authorship stack (2026-07)** | **QORTROLLER-POSP-v0 synchronized presence proven live across matches**; kill-authorship (KAS) live under Remote Play — **first live RP authored sessions 2026-07-10 (authored=14, then 11)**; offline **deferred-attestation** tier recovers authorship from sealed archives when live capture is lag-thinned (three consecutive live-0→offline-recovery archives) |
| **First REAL on-chain ZK replay proof** | Groth16 `VAPIReplayProofVerifier` proof from a real match (M17) **accepted on IoTeX testnet** — `ReplayProofVerified`, block **45479067** (`audits/vhr_proof2_m17/`) |
| **Golden offline authored pack** | `python scripts/golden_offline_authored.py` → deterministic card-free `authored>0` re-proof (bars A–H frozen in `docs/golden-offline-authored-pack.md`; exit 0 mandatory before any external claim) |
| **PORT-CERT full VERIFIED** | Portable match certificate re-check end-to-end: `scripts/portcert_full_verify.py` → **`OVERALL: VERIFIED`** demonstrated on M17 (C5 snarkjs Groth16 re-verify + C6 on-chain anchor read, one command, 0 IOTX) |
| **Organizer pilot package** | One-pager (claim-audited) + ops runbook (rig-validated) + plain-English walkthrough — **four claim ceilings frozen**: advisory never-ban · offline-primary reliability · developer-self scope (no field-FAR/identity/population) · testnet no-token |
| **Wallet posture** | `CHAIN_SUBMISSION_PAUSED=true` held; zero-trust sandbox compliant; every chain-write path operator-fired |

---

## Milestones from genesis to now (plain-English timeline)

| When | Milestone | Why it matters in plain terms |
|---|---|---|
| Genesis | **The 228-byte PoAC record** — every controller input cryptographically signed and chained | The atom of the system: an input event that can't be quietly rewritten |
| 2026-04 | **3-player biometric corpus; AIT separation gate cleared (1.199, N=37)** | First evidence real people are statistically tellable-apart by grip physics alone |
| 2026-05-06 | **GIC_100 anchored on IoTeX** (block 43348052) | 100 consecutive clean play sessions chained + timestamped on a public blockchain |
| 2026-05-17 | **3-agent autonomous operator fleet live at full authority** (Sentry/Guardian/Curator) | The protocol's maintenance runs under cryptographic, auditable rules — not admin whim |
| 2026-05-26→30 | **Path A silicon-rooted device registry + Data-economy arcs built** (replay proofs, recency beacons, post-quantum sidecar) | Controllers get birth certificates; match data gets an owner-controlled marketplace rail |
| 2026-06-05 | **First gamer-signed consent manifest on-chain; 66 contracts live** (that day; 69 now) | The player flipped their own data switches with their own wallet — provably not us |
| 2026-07-04→07 | **PoSP — synchronized presence proof, proven live** (incl. first Remote-Play-born PoSP) | Three independent evidence surfaces (authorship log, biometric co-capture, sealed archive) agree it was one real session |
| 2026-07-08 | **First *real* zero-knowledge replay proof verified on-chain** (block 45479067) | Math, not promises: a real match's replay integrity checked by a public contract |
| 2026-07-08→10 | **Kill-authorship: kills bound to real trigger pulls — offline path institutional** | The receipt names *which kills* the physical controller caused; reproducible from a sealed archive with one command, every time |
| 2026-07-10 | **First live Remote-Play authored sessions** (authored=14, then 11) | The hardest capture path (cloud streaming) attributed kills *during live play* |
| 2026-07-10 | **First full certificate re-check: `OVERALL: VERIFIED`** | An outsider can re-run our proof end-to-end — ZK proof + blockchain anchor — in one command |
| 2026-07-10 | **Pilot package published** (organizer one-pager · ops runbook · plain-English walkthrough) | A tournament organizer can evaluate and run this without us re-explaining anything |
| 2026-07-11 | **The inner data-economy ring shipped** (verified play-résumé → skill-strata → self-analytics) | The gamer can hold their own provable play history — and a page that *refuses to render* unless its evidence still verifies |
| **2026-07-11** | **WMP data-economy Phase-2 LIVE — the first certified-human data bundle, VERIFIED 5/5** (consent registry `0x06836Fb8…`, gamer-signed consent `0x8f70bca3…`) | The second engine turned on: anti-cheat evidence became a *verifiable product* — a stranger confirms real-human + own-wallet consent + data-matches-proof with one command. **Gamers proven to be the Core Controllers of their Data.** |
| 2026-07-12/13 | **The `qortroller` product + the autonomous A2A engineering engine** (six AI-to-AI loops: CLI + StreamView gamer UI + honest self-scorecard + adversarially-hardened kill authorship) | The developer rig became an installable product path — setup wizard, play, stop, receipt — designed and built by two AIs cross-verifying each other over a terminal bus, every honesty rail intact |
| 2026-07-13 | **Kill-feed recall proven live: ~17/17 kills witnessed** (was 0/21) — after an honest 0-score led to a mined root cause and a one-line fix | The witness now *sees the gamer's kills as they happen*; the fix was proven on real match data before the claim was made — and the score that found it refused to round itself up |
| **2026-07-13** | **DEPIN NODE LIVE — born + first contribution ANCHORED** (node from the registered Edge; ledger entry #000 = a real 17-kill match; tx `0xb985f035…` block 45613440, operator-fired, 0.143 IOTX) | A gamer's controller became a DePIN node with an on-chain history: identity derived from a registered device, a tamper-evident contribution ledger, and its first entry anchored on IoTeX — **re-verifiable by any stranger from the tx hash** |

---

## What QorTroller is

**The problem.** Cheat detection in competitive gaming has no cryptographic anchor. Existing solutions (BattlEye, Riot Vanguard, Easy Anti-Cheat) are kernel-level enforcement layers with no public verifiability surface; tournament organizers and viewers must trust the publisher's claim that a match was clean. Bot software keeps improving; controllers get repurposed; signed binaries get repurposed; injection vectors keep multiplying. Worse: the enforcement model is zero-sum — the protocol *vs.* the gamer. The gamer surrenders sovereignty over their biometric, behavioral, and consent surfaces to participate.

**The category — V.A.P.I.** Verifiable Autonomous Physical Intelligence is a coined DePIN sub-category for protocols where the **physical-input source is also the cryptographic agency-holder** over the data those physical interactions generate. V.A.P.I. inverts the enforcement frame: cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty. Other future V.A.P.I.-compliant projects could implement the category for mobile, console, VR, IoT-sensor, or wearable scopes. QorTroller is the first.

**The project — QorTroller.** Binds every controller input event to a tamper-evident, on-chain-verifiable cryptographic record — a **Proof of Autonomous Cognition (PoAC)**. Each 228-byte PoAC binds raw sensor commitments (IMU dynamics, analog trigger dynamics, stick/button timing, biometric feature commitments) to a hardware-rooted ECDSA-P256 signature, hash-chains them into a per-session sequence, and exposes the resulting state through a single composable on-chain call: `VAPIProtocolLens.isFullyEligible(deviceIdHash)`. External tournament organizers can gate eligibility on that one view call without trusting a private publisher API or manually inspecting raw biometric data — the on-chain gate minimizes integrator trust by reducing eligibility to a public view-call over previously anchored protocol state. The gamer keeps cryptographic credentials (PHGCredential / VHP), grants per-category consent (CONSENT v1), and exercises GDPR Article 17 right-to-be-forgotten — `msg.sender` on `VAPIConsentRegistry` IS the gamer.

**The architecture.** Nine layers of Physical Input Trust (PITL L0–L6 deployed, L7 GSR advisory, L8 BT gated) verify each input event at increasing levels of biometric specificity. A 10-element family of FROZEN-v1 cryptographic primitives (PATTERN-017) anchors session continuity, cognition integrity, watchdog events, application-layer messaging, biometric snapshots, consent state, and Layer 7 ZKBA artifacts. Three Operator Initiative agents (Sentry, Guardian, Curator) hold Cross-Fleet Skill Separation (CFSS) lane authority on Cedar v2 bundles dual-anchored on chain.

**The output.** Seven Zero-Knowledge Biometric Artifact (ZKBA) classes (AIT, GIC, VHP, HARDWARE, CONSENT, TOURNAMENT, MARKET) compile through a deterministic Verified Projection Media (VPM) compiler with three-layer Anti-Hype Visual Grammar enforcement (compile-time + bridge-time + browser-time). Every cryptographic claim is independently verifiable by anyone with the canonical-JSON algorithm + SHA-256 + the public source of the four enforcement layers.

**The economy — "Core Controllers of their gaming data."** The same anti-cheat evidence trail is a supply of the scarcest thing the AI economy now needs: **provably-human demonstration data**. The World Model Provenance (WMP) lane packages a consented session as a certified-human action bundle — post-φ action-channel only (60 Hz, 4-bit; the discriminative biometric micro-signal that powers the anti-cheat *structurally cannot* be in the export), carrying a real Groth16 humanity proof, a temporal-recency anchor, and an on-chain consent reference. A world-model researcher runs one consumer verifier and confirms *real human · real consent · data matches the proof* without trusting QorTroller at all. **As of 2026-07-11 this is LIVE, not designed:** the first real bundle verifies 5/5. And it is the tagline made literal — the person on the controller signs their own consent on-chain (`msg.sender == gamer`); the bridge is cryptographically incapable of doing it for them; the gamer is the sovereign *supplier* of their data, not the surveilled subject of it. Provenance cannot be bolted onto data after the fact — it must be born at the moment of physical action, on the input device itself. That is precisely the V.A.P.I. definition, working end to end.

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
| **Arc 6 — `VAPITemporalBeaconRegistry` LIVE** | `0x962440312a995b21d4E203bE6d93021CC22bA051` · tx `0x7d87bdef875f0507fca9f3f2b6a99efccc275415a1dcd3a3d080c2b768da0140` · block 44355513 | FROZEN-v1 #14 `VAPI-TEMPORAL-BEACON-v1` registry now on-chain. `INV-TBR-001` (BEACON_DOMAIN keccak256 pin) + `INV-TBR-002` (`ANCHOR_CADENCE=64` pin) byte-equal-checked at deploy. **Keeper set 2026-06-25** (first anchor block 45008576) — the PoSR recency leg is now live. *(This June-5 block predates that; the keeper note was true as-of-deploy.)* The fail-open contract was preserved exactly; bridge readiness never depended on Arc 6. |

**Total session on-chain spend:** ~1.34 IOTX (consent manifest 0.18 IOTX + Arc 2 0.54 IOTX + Arc 6 0.46 IOTX, plus marginal gas overhead). Wallet `0x0Cf36dB57…` remaining: ~31.96 IOTX. `CHAIN_SUBMISSION_PAUSED=true` in `bridge/.env` held throughout — these were direct hardhat deploys signed by the bridge/deployer wallet, NOT bridge-side transactions.

## 2026-07-11 milestone — WMP data-economy Phase-2 LIVE (the second engine turns on)

The first time anti-cheat evidence became a **verifiable product**. One real match (M17) exported as a certified-human action-demonstration bundle that a stranger re-verifies 5/5 with one command, trusting QorTroller for nothing. This is the tagline made literal — *the gamer's own wallet* signs the consent that lets the data exist as a product; the bridge cannot.

| Milestone | Address / tx | Significance |
|---|---|---|
| **WMP-4 `VAPIWorldModelConsentRegistry` LIVE** | `0x06836Fb87B64A05D81ebec9C9e234c01c2DEc5C4` · tx `0x5456e576ecb4c480a6ba7cf3a2a5e37d75b15de607399692d8bac604eaafa8f1` · block 45534708 | The greenfield, single-purpose (gamer ⇒ bool) world-model export consent registry. A gamer can permit training-corpus export while withholding replay sale, or vice-versa — granular sovereignty across use-cases. `msg.sender == gamer` enforced; bridge structurally cannot write it. |
| **First gamer-signed `setWorldModelConsent(true)`** | tx `0x8f70bca3bd3ab084a271f51d410027a196eba17bc7b787689ac639a0ba658a22` · block 45534743 | Wallet `0x0Cf36dB57…` granted world-model export consent, readback `true`. `developer_self` scope: the operator IS the gamer (single-developer testnet), stated on-chain-adjacent and in every artifact. |
| **First real WMP bundle VERIFIED 5/5 zero-stub** | `wmp_corpus_real/wmp_corpus.jsonl` (published) | `scripts/wmp_full_verify.py` → `VERIFIED` — real snarkjs Groth16 (the same proof accepted on-chain at block 45479067) + Poseidon matrix↔root (**closing the long-open Arc 5 off-circuit-root finding on REAL data**) + LIVE on-chain consent view-call, all un-stubbed; recency explicitly-deferred (one anchored beacon near M17; next keeper-anchored match = true 5/5). Matrix-swap tamper drill → REJECTED. |

**Total session on-chain spend:** **0.247443 IOTX measured** (`eth_getBalance` 29.118262 → 28.870819). Report: `audits/wmp-phase2-first-real-bundle-2026-07-11.md`. Ceilings carried verbatim: action-only, macro-intent-not-biomechanics, `developer_self`, N=1 corpus, no buyer implied, TGE frozen. `CHAIN_SUBMISSION_PAUSED=true` held (direct hardhat/CLI, operator-fired).

## 2026-07-13 milestone — DEPIN NODE LIVE (born, witnessed, anchored)

The two-day arc that turned the protocol into a **product with a live DePIN node**. Six autonomous AI-to-AI engineering loops (Claude builds/grounds ↔ grok designs/attacks, cross-verifying each other over a sealed terminal bus) shipped the `qortroller` CLI, the StreamView gamer UI, an honest match self-scorecard, and an adversarially-hardened kill-authorship chain — then the operator validated it all live.

| Milestone | Evidence | Significance |
|---|---|---|
| **Kill-feed recall closed live: ~17/17 witnessed** (was 0/21) | `audits/recall-closed-17kill-match-2026-07-13.md` — 205 conformant events, 117 exact-match own-kill reads in one real match | An honest 0-score triggered a desk mining pass that found the root cause (OCR was reading 5×-downscaled thumbnails), a one-line fix, and a live landslide — **zero false authorship across ~850 reads**, including 20 minutes accidentally pointed at a wall |
| **Node BORN** — `node_id 01a574e7ca7f…` derived from the registered Edge | `audits/node-birth-and-first-anchor-2026-07-13.md` | The birth ceremony **refused an impostor controller** (a standard pad plugged in first) and bound identity only to the on-chain-registered device (VMDR tx `0x68f6cf49…`). The node_id is *derived, not minted* — and every surface says so |
| **First contribution ANCHORED on IoTeX** | tx `0xb985f035ab24819d…` · block 45613440 · status 1 · **0.143115 IOTX measured** | Ledger entry #000 (the 17-kill match, PoSP SYNCHRONIZED) went from local `PENDING` → `ANCHORED` only after the real receipt — **fired by the operator in their own shell, four gates deep; the agent structurally declined the spend.** A gamer's controller now has a verifiable on-chain contribution history |

Honest ceilings, stated everywhere: AUTHORED (causal R2-binding + hygiene) remains 0 on this match — the dual-connection HID constraint is a *separate, known seam*, not an OCR problem; the scorecard prints the strictest number, tagged `[MEASURED]`/`[OPERATOR-REPORTED]`, and never rounds up. One node, one operator, testnet, no token, nothing for sale.

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

**Claim ceilings (frozen 2026-07-10):** advisory soft-signal, never a ban input · offline sealed-archive authorship is the reliability path (live capture is best-effort; we do not claim it "healthy" — the self-starving criterion is OPEN per `docs/f2x-residual-capture-contention-2026-07-10.md`) · developer-self scope — no field error rates, no identity claims, no population certification yet · testnet only, no token. The presence oracle is SEPARATED against *modeled* automation only (`audits/p0a-presence-op-v2-2026-07-09.json`); real-adversary and multi-player studies are deliberately queued behind demand, not ahead of it.

**On-chain anchored milestones (IoTeX testnet, chain 4690):**
- **GIC_100 cognitive chain head** permanently anchored 2026-05-06 — tx `0xe807347eb837...` block 43348052. A 100-link cognitive-session integrity chain anchored on IoTeX testnet.
- **Cedar v2 lane authority bundles** for all three Operator Initiative agents dual-anchored 2026-05-12 on AgentScope (operational FIRST) + AgentRegistry (governance SECOND). Merkle roots: Sentry `0x39e8b65f...db1f23` / Guardian `0x6818a9ad...0a9a0` / Curator `0x0ade0c92...60a80b3d`.
- **Inaugural CORPUS-SNAPSHOT** anchored 2026-05-09 — tx `0x24e4ddb6...` (closes Phase 237.5 Path C+ wallet-drain audit trail).
- **VHP demo mint** tokenId=2 — humanity credential bound to all three protocol layers (canonical Sony DualShock Edge CFI-ZCP1 device + GIC_100 milestone + ZK ceremony VK hash).
- **WMP-4 world-model consent registry + first gamer-signed export consent** (2026-07-11) — registry `0x06836Fb8…` block 45534708; consent tx `0x8f70bca3…` block 45534743; first real certified-human data bundle verified 5/5 (the second engine, above).

**Data-economy honesty (WMP Phase-2, 2026-07-11):** UC-1 is LIVE but it is a **demonstration, not a business** — one match, one gamer (who is the operator), no buyer, N=1 corpus, on testnet, with no token. The export is post-φ action-only; the biometric signal that powers the anti-cheat cannot be in it. Recency shipped explicitly-deferred on this bundle (one anchored beacon near the match; a keeper-anchored open/close pair on a future match earns the true 5/5-with-recency). "Provably-human data is valuable" is a demand thesis the milestone makes *demonstrable*, not booked revenue.

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
# Initialize git submodules first (required by the invariant gate — INV-FIRMWARE-001/002
# pin files inside the bridge/firmware/joypad-os submodule). One-time per fresh clone.
make init

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

## QorTroller Daemon Brain

The **QorTroller Daemon** (`qortroller_daemon.py`) is a persistent, protocol-aware cognitive layer that sits over the entire QorTroller codebase and live on-chain state. It uses a hive-mind architecture: one central AI brain owns the LLM connection, tool execution loop, and SQLite conversation memory; multiple rendering clients (CLI, TUI) connect as dumb frontends that display results without holding any AI state themselves.

```
┌─────────────────┐    POST /chat     ┌──────────────────────┐
│  CLI Agent      │ ────────────────→ │                      │  QuickSilver API
│  (Rich terminal)│ ←── GET /history  │  QorTroller Daemon   │ ─────────────→
└─────────────────┘                   │  (one brain)         │  deepseek-v4-flash
┌─────────────────┐    POST /chat     │                      │
│  TUI Agent      │ ────────────────→ │  agent_memory.db     │
│  (Textual)      │ ←── GET /history  │  (shared memory)     │
└─────────────────┘                   └──────────────────────┘
```

### Start the daemon

```bash
# Terminal 1 — start the brain
python qortroller_daemon.py

# Terminal 2 — CLI rendering client (Rich terminal UI)
python qortroller_cli_agent.py

# Terminal 3 (optional) — TUI rendering client
pip install textual
python qortroller_tui.py
```

Requires `QUICKSILVER_API_KEY` in `bridge/.env`. The daemon listens on `localhost:8080` and persists all conversations in `agent_memory.db` across restarts.

### What the brain can do

The daemon has **30 tools** organized across three tiers:

**Codebase intelligence**

| Tool | What it does |
|---|---|
| `read_file(path)` | Read any repo file (max 12KB) |
| `write_file(path, content)` | Write files (blocked for protocol invariant files) |
| `list_files()` | List all project files |
| `search_code(pattern, glob?)` | ripgrep/git grep across the codebase |
| `git_history()` | Last 10 commits (oneline) |
| `git_log_full(ref?, n?)` | Full commit detail with stats |
| `execute_shell(command)` | Run any shell command from repo root |

**Protocol state (QorTroller-native)**

| Tool | What it does |
|---|---|
| `gic_chain_status(n?)` | Visual GIC chain progress bar toward GIC_100 — chain length, head hash, consecutive_clean, genesis + latest timestamps. Reads live bridge or falls back to local DB. |
| `gic_replay(n?, session_id?)` | Cryptographic replay of last N GIC links — recomputes each SHA-256 hash and flags tamper or corruption. Works without the bridge. |
| `calibration_status()` | Full enrollment readiness: live L4 thresholds from `calibration_profile_live.json`, AIT separation ratio, GIC progress bar, all P0 tournament gate conditions. |
| `run_mythos(variant)` | Run any of the 17 Mythos audit variants on demand. Findings sorted CRITICAL → HIGH → MEDIUM → LOW. Fast variants (16=`path_a_spec_impl_parity`, 14=`doc_number_consistency`, 5=`crypto_drift`) need no DB. |
| `run_invariant_gate()` | Full PV-CI gate (182 invariants) from the chat prompt. |
| `poac_status()` | Single-call protocol status snapshot: GIC, PCC, contract count, git HEAD. |

**On-chain truth (no bridge required)**

| Tool | What it does |
|---|---|
| `query_chain(query, device_id?)` | Direct IoTeX testnet RPC. Queries: `wallet_balance`, `is_fully_eligible`, `get_device_tier`, `beacon_registry`, `block_number`, or `all`. Resolves against live deployed contracts from `deployed-addresses.json`. |
| `list_contracts()` | All deployed contracts with addresses (69 as of 2026-07-11). |
| `bridge_get(path)` | GET any bridge endpoint. |
| `bridge_post(path, payload?)` | POST to bridge endpoints — trigger actions, not just read state. |

**Domain analysis (Goose-contributed)**

`protocol_phase`, `tournament_readiness`, `separation_deep_dive`, `biometric_vault`, `governance_audit`, `fleet_coherence`, `corpus_health`, `l4_calibration`, `epoch_windows`, `protocol_maturity`, `chain_overview`, `daemon_diagnose`

### What makes it protocol-native

The system prompt has the PITL stack, the 228-byte FROZEN wire format, the L4 thresholds, the separation ratio history, and the verification-first discipline baked in. When you ask it "should I adjust the L4 threshold?", it knows the answer is no — thresholds can only tighten, enforced by `min()`. When you ask it "is my device eligible?", it calls `query_chain` against the live IoTeX contract instead of guessing.

The brain accumulates conversation history in `agent_memory.db` across sessions. Unlike Claude Code (which starts fresh each session), the daemon remembers every prior conversation about calibration, GIC chain state, Mythos findings, and on-chain queries — building a persistent operational context over time.

### Daemon API endpoints

```
POST /chat                     — Send message to AI brain (full autonomous tool loop)
GET  /history                  — Fetch unified chat history from SQLite
GET  /status                   — Brain status (thinking / idle / running tool: X)
GET  /health                   — Health check
GET  /tools                    — List all 30 available tools with schemas
POST /agent/local-host/execute — Direct tool execution (operator-authenticated)
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
│   ├── vapi_invariant_gate.py      PV-CI 182-invariant gate
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
├── qortroller_daemon.py     Hive Mind central brain — 30 tools, SQLite memory, QuickSilver API
├── qortroller_cli_agent.py  Rich terminal rendering client (connects to daemon)
├── qortroller_tui.py        Textual TUI rendering client (connects to daemon)
├── agent_memory.db          Persistent conversation memory (gitignored; created at first run)
├── CLAUDE.md                Operator-authoritative state file (single source of truth)
├── contracts/deployed-addresses.json   Authoritative on-chain registry
└── .github/INVARIANTS_ALLOWLIST.json   182-entry PV-CI digest pin file
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
- **PV-CI invariant gate** runs on every PR — currently 182 invariants. Modifying a frozen region without a `--confirm-governance` ceremony fails CI.
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
