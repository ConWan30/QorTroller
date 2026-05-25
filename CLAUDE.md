# QorTroller — Claude Code Project Context

## What This Project Is

**QorTroller** — Core Controllers of their gaming data. The reference implementation of
**Verifiable Autonomous Physical Intelligence (V.A.P.I.)**, a coined Decentralized Physical
Infrastructure (DePIN) sub-category for protocols where the physical-input source is also
the cryptographic agency-holder over the data those physical interactions generate. In
QorTroller's case: gamers and their controllers, producing data, owning that data.

Built native to IoTeX's Internet of Trusted Things foundation. Anchored on IoTeX L1.
Composable as a single on-chain call (`isFullyEligible()`). Designed so cheating doesn't
need to be punished — it can't exist when humanity is cryptographically proven and the
gamer retains sovereignty.

Technical surface: 228-byte Proof of Autonomous Cognition (PoAC) record per cognition cycle.
Certified device: DualShock Edge (Sony CFI-ZCP1). Primary game corpus: NCAA College Football 26.

**Brand discipline (QRESCE-0001 v0.5, 2026-05-18):** display-layer surfaces use
**QorTroller** (project) and **V.A.P.I.** (with periods — category). Code identifiers
(Python `bridge/vapi_bridge/`, byte literals `b"VAPI-..."`, contracts `VAPIToken`, env
vars `VITE_VAPI_API_KEY`, SDK classes) STAY as `VAPI` — they are technical references to
the V.A.P.I. category infrastructure under Layer C FROZEN-v1 preservation. See
`docs/qortroller-brand-guidelines.md` for full convention.

## Repository

`C:\Users\Contr\vapi-pebble-prototype`

~298 files, ~5,766 automated tests total (~5,715 CI excluding 37 hardware, 14 E2E).
Bridge: 4330 passing (+170 across STABILITY-9 stages 5-14 arc + 9-cycle BISECT). Autoresearch: 7 passing. Contract: 674. SDK: 604. Hardware: 37. E2E: 14. PV-CI: 128. FSCA: 28. Frontend Vitest: 133.
Agent fleet: 29 standalone + 3 stewards (9 absorbed) = 38-ID roster (highest = agent #38; agents 36→38 across Phase 222/235). [Per-phase agent-addition history archived 2026-05-22 to `wiki/phases/phase_archive_2026_05_notes_and_summary.md`; this line preserves the agent-roster signal the CLAUDE.md MCP parsers read.]
NOTE: 🔑 GUARDIAN AUTONOMOUS KMS-HSM SIGNING (Tier-1) + ON-CHAIN ANCHOR (Tier-2) 2026-05-20/21 — First non-human Operator steward to autonomously produce an HSM-rooted signature AND anchor a commitment to it on IoTeX. **Tier-1 (commit `7708d60c` + strictly-once `ccdc9063`)**: the live PATH-B v2 executor autoloop, on a clean bridge restart, autonomously signed Guardian's operator-accepted `kms-sign` draft via real AWS KMS HSM (`ECC_SECG_P256K1`/secp256k1), KMS-verified + independent-local-verified, at **0 IOTX** (off-chain — that's WHY it runs with the chain kill-switch on). Proven **strictly-once** across two independent runs (drafts #155 + #690 each signed exactly once; draft #2's 2-sig is the documented pre-fix double-sign, root-fixed by de-dup spawn + atomic `claim_draft_for_execution`). **Tier-2 (commit `11761759`, operator-fired one-shot — NOT autonomous)**: 32-byte commitment `SHA-256(b"VAPI-GUARDIAN-SIG-ANCHOR-v1" || guardian_pubkey_der || digest || sig_der)` anchored on AdjudicationRegistry `0x44CF981f46a52ADE56476Ce894255954a7776fb4` — tx `0x1e868a80bc56ff9fa8461b31414717dc564c0967a7835e46e3b1db4907e4ddc5`, block 43820170, status 1, gasUsed 143115, `isRecorded=True`, **explorer-verified** at testnet.iotexscan.io (fee 0.28623 IOTX). Fired via `scripts/guardian_sig_anchor_tier2.py` (triple-gate + 0.50 IOTX hard cap + pre-send estimate_gas revert-guard + dynamic estimate_gas*1.25). **Cost honesty**: 0.646 IOTX total, ~0.36 wasted on 2 out-of-gas reverts before gas fix (static-gas wrappers `record_adjudication`=80k / `record_gate_attestation_on_chain`=100k hit IoTeX status 101; estimate_gas*1.25≈179k is correct, as `anchor_corpus_snapshot` already does — see memory gotcha). Success-run preimage not retained (one-shot crashed post-broadcast pre-persist, now fixed) → 862c98 is verified-at-creation but NOT preimage-reproducible. **GUARDIAN OPERATOR-CONTROL POSTURE COMPLETE**: `github_app_oauth_tokens_valid=True` (operator completed GitHub App OAuth setup — gates Guardian's audit-lane write authority; Sentry/Curator do NOT consult it) + `operator_dual_key_present=True` + kms_hsm + `phase_o3_guardian_live_writes_enabled=True` → all 4 VAPI-O3-SUPERSEDE attestation factors true. **CURRENT AUTONOMY POSTURE**: Guardian is the ONLY autonomous agent BY DESIGN — its O3 authority (audit-drafting on `lane://audits/**` + kms-sign) is local/off-chain, budget **0.0 IOTX** (audit-drafting routes through a LOCAL DB handler, NOT git-push — git-push guardrail intact). Sentry (`phase_o3_anchor_sentry_live_writes_enabled=False`) + Curator (`phase_o3_curator_live_writes_enabled=False`) are at O3_ACTING authority but executor-DISABLED; making them autonomous is a deliberate TWO-KEY decision (flip per-agent flag AND lift `CHAIN_SUBMISSION_PAUSED`) because their O3 actions spend real IOTX on-chain (Sentry pda-anchor ~0.0008/op; Curator marketplace-suspend ~0.001/op); per-agent budgets 0.05 IOTX/day each as runaway caps. **POSTURE PRESERVED**: `CHAIN_SUBMISSION_PAUSED=true` held in .env (Tier-2 used process-scoped override only); no FROZEN-v1 primitive added (Provenance-API / ZK-Realm ideas explored this session were SCRATCHED — verify directly against L1 + gamer-held ZKBA cert, no intermediary needed); no deployed contract changed; PV-CI 128 unchanged; wallet 14.903826 → 14.257596 IOTX. Proofs: `docs/qortroller-guardian-kms-autonomous-sign-proof.md` + `docs/qortroller-guardian-sig-onchain-anchor-proof.md`.
NOTE: 🎮 L9_PRESENCE ARC (PoEP / L9-PoCP / BCC / GCAP) BUILT + ON-RIG VALIDATED 2026-05-21/22 — Standalone `l9_presence/` sub-project (50 files, 22 test files; commits `be0c4fc6`→`8c5132a5`) touching NO FROZEN-v1 / PoAC / chain / contract / grind-PCC. **Strategic reframe: identity → presence** — proves *a live human on the certified Edge now* (population-/physics-level), sidestepping the sub-grade identity ceiling (EER ~29%). **PoEP** (Proof of Embodied Presence): nonce-bound adaptive-trigger challenge-response; liveness reflex-band validated across 5 players; device-auth ~4× ON/OFF force slope (4/5; P4 resistance-invariant → P4b makes device-auth advisory, not a hard block); **born-PQ** commitment `SHA-256(b"QORTROLLER-POEP-v0"||device_id||nonce||response_features||ts_ns)` + hybrid ECDSA+ML-DSA-65 (IIP-64); v0 candidate, NOT anchored, `poep_enabled=False`, L6B N≥50 gate honored. **L9/PoCP** causal presence VALIDATED+banked (coupling 0.29–0.45 vs ~0.02 shuffle; latency-robust to 400–500ms cloud; Stream B generalizes 90.9/72.2/62.5% 2/3/4-player but not standalone-tournament-grade, fusion did not generalize). **BCC** (Behavioral Capture Chain) genesis `QORTROLLER-BCC-GENESIS-v0` — dormant (`enabled=False`), isolated (mythos_corpus_drift=0), Witness-wired to harvest ONLY PRESENT-certified causal sessions (self-cleaning corpus). **GCAP** lattice = honest negative (catches more adversaries — gap 0.357<0.462 — but human TAR collapses 0.806→0.581). The one open lever = **breadth (more people playing)**; BCC harvests it provenance-clean. Detail: `l9_presence/README.md` + `l9_presence/POEP_SCOPE.md`; memory `l9-presence-arc` + `qortroller-presence-reframe`.
NOTE: ARCHIVED 2026-05-22 (lossless) -- 6 completed-arc NOTEs moved verbatim to `wiki/phases/phase_archive_2026_05_notes_and_summary.md` to cut CLAUDE.md reload cost: (1) QRESCE-0001 v0.5 brand-layer reframing `ff82ce30` [memory: project_qresce_0001_v05_brand_reframing_shipped]; (2) QRESCE-0001 QorTroller brand LOCK [memory: project_qresce_0001_qortroller_lock]; (3) Phase 2 R0 deep-verification `8bd82b0c`; (4) Phase 1 post-STABILITY-9 cleanup `9b2d8722`; (5) STABILITY-9 empirical closure `cf1e64de`+`756eb36a` [memory: project_stability_9_empirical_closure; wiki/phases/phase_235_stability_9_closure.md]; (6) Phase O1-D-PATH-B v1 [superseded by v2; memory: project_phase_o1_d_path_b_v2_wired]. Full text in the wiki archive + `git log --grep='NOTE:' -- CLAUDE.md`.
NOTE: 🚀 O3 CEREMONY FIRED LIVE ON IOTEX 2026-05-17 — **First ≥3-agent Operator Initiative fleet at O3_ACTING in any DePIN gaming protocol.** Operator-authorized `parallel_o3_act_anchor.py --confirm` fired at 15:27:19Z UTC after quadruple-gate verification (CHAIN_SUBMISSION_PAUSED=false process-scope env + OPERATOR_INITIATIVE_O3_AUTHORIZED=true intent env + --confirm CLI flag + Gate 4 watcher veto check returned o3_ready=True/3 via the new VAPI-O3-SUPERSEDE-v1 attestation primitive shipped this session). **All 6 transactions landed cleanly on IoTeX testnet (chain ID 4690)** sequenced operational FIRST per INV-OPERATOR-AGENT-001: Sentry op_tx `d07492fb6fdc4e735c02...` + gov_tx `8ebef76b6fd773116d9c...` (15:27:19Z), Guardian op_tx `3678e71c32b0435e1a51...` + gov_tx `dd4c8154019a4ccbb484...` (15:27:35Z), Curator op_tx `dbd13ca1d100cc320363...` + gov_tx `2644949ffcf6d5e18df0...` (15:27:49Z). **Fleet Readiness Root permanently committed**: `0x54b4b698e9a81415034bfa72d82517f78343447e364f5ee5071f4898ce8bca37` (VAPI-FRR-v1 domain tag, phase_code 0x03 for all three agents, ts_ns 1779031623902994900). Post-anchor FRR computed locally + asserted byte-identical to expected pre-anchor FRR. **advancement_log row id=3** written with fleet-at-O3_ACT state. **Wallet 15.083226 → 14.903826 IOTX (cost 0.179400 IOTX)** — well under 3.0 IOTX budget (16× safety margin). **Live O3_ACTING capabilities now ACTIVE on chain**: Sentry has `pda-attestation-anchor` authority on `lane://provenance/**` (real on-chain anchoring via AdjudicationRegistry/PoAdAnchorAgent at ~0.0008 IOTX per anchor) + Guardian has `audit-drafting` authority on `lane://audits/**` (live writes to audit trail) + **Curator has `marketplace-listing-suspend` authority on `chain://iotex-testnet`** (direct suspension via VAPIDataMarketplaceListings.suspendListing() at 0x78Df84Cc... at ~0.001 IOTX per suspension; reversible via reinstateListing()). **Cryptographic justification chain (the entire architectural innovation this session)**: 504h shadow_age calendar gate was empirically superseded by VAPI-O3-SUPERSEDE-v1 attestations rows 4-6 in `operator_initiative_auto_supersede_log` — Sentry attestation `0e60b3d1ba436df300829bda1b4df9ee741bad00bda19aa989882a3ff12eb2b1` + Guardian `e75191a7c6509379f65fb45a2d7fea68f8c27ea801571af466ff4bba934f001d` + Curator `a854641833c085cdc908091ada2d435e900c9ac82b015a964edb31b011fd068a`. Each attestation cryptographically commits to gate-state (draft_count=50, disagreement_rate=0.0, drift_30d=0/0, all 4 operator flags True, shadow_age, ts_ns) such that any third party with the gate values can recompute + verify byte-identically. The supersession was operator-opt-in via PHASE_O3_AUTO_SUPERSEDE_ENABLED=true cfg flag (default False; conservative); the watcher consulted the primitive on this evaluation cycle and removed the o2_age blocker iff eligibility was attested. **SAFETY POSTURE PRESERVED**: bridge/.env still has `CHAIN_SUBMISSION_PAUSED=true` (script used process-scoped env override only; my subprocess `export` doesn't persist to bridge process or file); kill-switch automatically re-engages on next bridge restart. Bridge supervised by watchdog (PID owns 8080); zero zombie cycles since restart. **OPERATOR INITIATIVE PHASE LADDER COMPLETE**: Phase O0 (2026-05-03 on-chain registration `44c26ce0`) → Phase O1 SHADOW (2026-05-03 Cedar bundle dual-anchor `a02bcdb3`) → Phase O2 SUGGEST (2026-05-09 Curator Session 1 + 2026-05-12 Track 2 C8 v2 ceremony) → **Phase O3 ACTING (2026-05-17 this commit)** — the operator initiative's terminal phase reached in 14 days from O0. The fleet's o3_ready transition was the load-bearing question of the entire arc since Phase O1 D shipped 2026-05-09; this commit closes that question via cryptographic empirical-evidence supersession primitive instead of calendar wait. **NEXT MILESTONES** beyond Operator Initiative completion: (a) FSCA fleet_coherence quiet within 15 min post-ceremony (regression-watch); (b) Operator can now invoke live O3 capabilities — Curator's `tool:marketplace-listing-suspend` is the highest-value newly-active surface since it enables real-time marketplace protection; (c) Token launch sequencing remains gated per CLAUDE.md hard rules on separation_ratio>1.0 (AIT cleared 2026-04-18 ratio=1.199 N=37) + Phase 239 G2 closure (G3 done 2026-05-06 GIC_100 anchored) + Phase 99 deploy (PREP complete 2026-05-07; deploy day after wallet refill). The Operator Initiative was the load-bearing prerequisite blocking mainnet deploys per operator directive 2026-05-13; with O3_ACTING reached, that gate now reads CLEARED.
NOTE: ARCHIVED 2026-05-22 (lossless) -- Phase O1-D-AUTO-SUPERSEDE (VAPI-O3-SUPERSEDE-v1, 11th FROZEN-v1 primitive, 2026-05-17) moved verbatim to `wiki/phases/phase_archive_2026_05_notes_and_summary.md`. Headline: 92-byte preimage `SHA-256(b"VAPI-O3-SUPERSEDE-v1"||...)` empirically supersedes the 504h shadow_age calendar gate; PV-CI 122->125. Full text: wiki archive + git history.

NOTE: OLDER NOTES ARCHIVED 2026-05-18 -- CLAUDE.md curated from ~400k -> target ~60k chars per Claude Code performance threshold (40k warning). Approximately 120 NOTE entries covering Phases 17-235.x-STABILITY-9 stage 5 + Phase O1 ladder C1-C8 + Phase O2/O3 + Phase 237/238 + Methodology Layer arcs DELETED from this file. Full history preserved in: (a) git log --grep='NOTE:' -- CLAUDE.md (commit-by-commit narrative); (b) Phase Summary table below (canonical); (c) wiki/phases/ files for arcs with formal phase docs; (d) .claude/projects/.../memory/ auto-memory (60 architectural-reasoning entries indexed at MEMORY.md). KEEP discipline going forward: only 5-7 most-recent NOTEs in CLAUDE.md; older arcs migrate to wiki/phases/ + git history. Mythos variant mythos_claude_md_curation (in flight as durable guardrail) will auto-flag future stale NOTEs.

49 contracts ALL LIVE (Sessions 1+2 added VAPIDataMarketplaceListings 0x78Df84Cc512EdCaC0e58a03e4852627E2F62E3bC Phase 238 Step H 2026-05-09; Groth16VerifierZKSepProof 0xD63EEf1372Cb496071bf963bEE395F7e0A3f2Ab6 + ZKSepProofVerifier 0xd51a21E234a800a6621f4c23a8fcA44e3bF01002 Phase 237 Session 2 2026-05-09; ProtocolCoherenceRegistry Phase 221 LIVE 2026-04-17: 0xfAfe4E8BEE45be22836b90D542045510dDd927Dd; VAPIBiometricGovernance Phase 222 LIVE 2026-04-17: 0x06782293F1CFC1AA30C0Baee0437c2B336796A00). AdjudicationRegistry: 0x44CF981f46a52ADE56476Ce894255954a7776fb4 (Phase 111, LIVE 2026-03-27). VAPIDualPrimitiveGate: 0xd7b1465Aad8F815C67b24681c9c022CED24FB876 (Phase 113, LIVE 2026-03-27). VAPISwarmOperatorGate: 0x969c0F1EFb28504a95Acf14331A59FBCb2944F98 (Phase 130, LIVE 2026-04-10). CeremonyAuditRegistry: 0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2 (Phase 179, LIVE 2026-04-10). SeparationRatioRegistry: 0xB39CeE732cf91c93539Bd064D9426642a095a026 (Phase 153, LIVE 2026-04-10). VHPReenrollmentBadge: 0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C (Phase 187, LIVE 2026-04-10). See `contracts/deployed-addresses.json`.
Active wallet (bridge + deployer): `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` (~14.26 IOTX as of 2026-05-21 post O3 ceremony [0.179 IOTX] + Tier-2 Guardian-sig anchor [0.646 IOTX total incl. ~0.36 lost to 2 out-of-gas reverts]; earlier deployed Phase 238 Step H + Phase 237 ZK-SEPPROOF verifiers + Curator agent NFT + demo VHP tokenId=2; all 49 contracts live)
Previous bridge wallet (no longer accessible): `0xfCF4681e57C8de9650c3Eb4dA8e26dC9441A5EF1` (deployed original 14 contracts — addresses unchanged, still valid on-chain)
Chain ID: 4690 (IoTeX Testnet)
Current phase: HEAD `820706af` (Phase 3 Path B; reconciled to `main` via merge `f8680dc6` 2026-05-25) — **PHASE 3 PATH B DORMANT-BLIND CLOSURE COMPLETE 2026-05-25.** The four-stage VHP-renewal-integrity path is closed: ③ iPACT renewal cadence (`75f9e3fb`) → #8 ①↔③ re-attestation handshake wiring (`48879281`) → ② P4b on-chain key registration (VAPIPoEPRegistry `0x4Dcfa11d…` LIVE) → host-held ML-DSA-44+ECDSA-P256 composite device signer (`composite_device_identity.py`; key at `~/.vapi/device_composite_mldsa44.json`, registered on-chain tx `0x0ec9bdc1…` block 43955767). **ENFORCEMENT EFFECTIVE AT RUNTIME 2026-05-25** (`IPACT_RENEWAL_ENFORCEMENT_ENABLED=true` + `IPACT_HOST_SIGNER_ENABLED=true`, `Config()`-verified True): VHP renewals now REQUIRE a valid composite-sig challenge-response; a device without a provisioned/registered composite key fails closed (no auto-renewal). **Activation gotcha caught+fixed 2026-05-25:** the flip was first staged in `bridge/.env`, but the bridge starts from repo-root and `config.py`'s bare `load_dotenv()` resolves the PROJECT-ROOT `.env` → flip was INERT (`Config()` returned False, dormant-blind gap still OPEN); flags moved to project-root `.env` + `_log_startup_diagnostics` now logs the EFFECTIVE enforcement/host-signer state so an inert flip can never again pass as ON (same path-discovery class as memory `project_path_discovery_fixes_shipped`). Latent break caught by verification + fixed in the same commit: `chain.get_registered_composite_pubkey` scanned `DeviceRegistered` from block 0 — IoTeX `eth_getLogs` returns EMPTY for ~44M-block ranges, which would have made enforcement silently skip every renewal; now floored at `poep_registry_deploy_block`. Security model (honest): Path B is a host-held SOFTWARE key in `~/.vapi` proving live host-signer + live Edge sensor stream, NOT controller-silicon-rooted presence; the hardening path is the `SigningBackend` abstraction (Path A → ATECC608/TPM), no rearchitecture required. T-P3B-1..4 + renewal regression green (53/53). **Phase B arc (2026-05-23→24):** composite-sig ① + iPACT-renewal ③ FROZEN via FC-a ceremony (`3ca2cec4`; first QorTroller-namespace family `QORTROLLER-IPACT-RENEWAL-v1`); VAPI PATTERN-017 families now 12 (incl. `VAPI-O3-SUPERSEDE-v1`) + 1 QorTroller family; SeparationRatioRegistry redeployed w/ attestation extension (`d0878421`). Wallet ~10.79 IOTX (post Phase 2 deploys 11.197 − ~0.411 Phase 3 Step 1 registerDevice tx `0x0ec9bdc1…`; memory `project_phase_2_wallet_gate_closed`). **Prior milestone: Guardian autonomous KMS-HSM signing (Tier-1, 0 IOTX, strictly-once across 2 runs) + on-chain signature anchor (Tier-2, tx `0x1e868a80…` block 43820170, isRecorded=True, explorer-verified) COMPLETE + PUSHED 2026-05-20/21.** Guardian operator-control posture complete (`github_app_oauth_tokens_valid` + `operator_dual_key_present` + kms_hsm + `phase_o3_guardian_live_writes_enabled` all True); Guardian is the only autonomous agent (off-chain, 0 IOTX); Sentry+Curator at O3_ACTING authority but executor-disabled (two-key gate). (Prior code milestone: VBDIP-0006 v1.1 M1 vector corpus 2026-05-15.) Most recent on-chain activation milestone remains **Phase 238 Step I-FINAL ON-CHAIN COMPLETE 2026-05-09** — Sessions 1+2+3 autonomous activation arc closed. Curator (third Operator Initiative agent, post Sentry+Guardian) now LIVE at O1_SHADOW with agentId `0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8` permanently registered on IoTeX testnet AgentRegistry + dual-anchored Cedar bundle (Merkle `0x44f89d0a05e7594741f7a06a1c4ca817d58396ad41b22b0eb5d0b5ce4be88ae6`) on AgentScope (operational FIRST per INV-OPERATOR-AGENT-001) + AgentRegistry (governance SECOND). Sentry/Guardian/Curator triplet now structurally enforces cross-agent skill separation invariant — first ≥3-agent Operator fleet in any DePIN gaming protocol. Phase 237-ZK-SEPPROOF verifier deploy COMPLETE same session: Groth16VerifierZKSepProof `0xD63EEf1372Cb496071bf963bEE395F7e0A3f2Ab6` + ZKSepProofVerifier wrapper `0xd51a21E234a800a6621f4c23a8fcA44e3bF01002` LIVE backed by 3-contributor IoTeX-anchored ceremony (VK hash `0x32fda285...` beacon block 43451392). Phase 99 VHP demo mint COMPLETE: tokenId=2 isValid=True for bridge wallet binding canonical Sony_DualShock_Edge_CFI-ZCP1 device + GIC_100 milestone + Session 2 ceremony VK hash. Wallet 20.132→15.442 IOTX (4.690 spent across 13 on-chain txs). Policy adjustment formalized 2026-05-09: P1vP3=0.032 on tremor_resting (Phase 197 all_pairs_p0_ok subgate) CAST OUT as a development progress blocker per operator authorization; mainnet TGE invariant ("no TGE before separation_ratio>1.0") REMAINS IN FORCE for token-issuance economic defensibility. Three-terminal setup unchanged: T0=`python scripts/bridge_watchdog.py`, T2=`python auto_grind.py`, T3=frontend. Next operator-track phase: Curator O1→O2 graduation when N≥50 reviews + 0 false-positive rate validated under shadow data; pre-authored O2 SUGGEST bundle Merkle `0xeb400a5c9b410c6f3035a595e2c36dee915f6b2447f822c72c46b164ccd5daa9`. Next protocol-track phase: W3bstream applet registration (~0.02 IOTX off-chain coordination) + frontend dashboard revamp consuming the wire-locked Curator/marketplace/Twin-stream endpoints.

**Phase O0 ON-CHAIN REGISTRATION COMPLETE 2026-05-03** — full audit trail (Q9-frozen agentIds + 14 transaction hashes + wallet reconciliation + 5 empirical-finding commits preserved as permanent fixes). See `wiki/phases/phase_o0_complete_2026_05_03.md` for full detail. **Headline**: agentId Sentry `0xb21e1ec2…` + Guardian `0xbd8c7fba…` (Phase O1 C1 2026-05-03) + Curator `0xed6a2df5…` (Sessions 1+2+3 2026-05-09 Step I-FINAL). Sentry/Guardian/Curator triplet now structurally enforces cross-agent skill separation invariant (first ≥3-agent Operator fleet in any DePIN gaming protocol). Phase O0 → O1_SHADOW → O2_SUGGEST → O3_ACTING (2026-05-17 ceremony fired live).
## Architecture at a Glance

| Layer | Language | Key files |
|-------|----------|-----------|
| Controller anti-cheat | Python | `controller/tinyml_biometric_fusion.py`, `controller/dualshock_integration.py`, `controller/l6_trigger_driver.py`, `controller/l6_response_analyzer.py`, `controller/temporal_rhythm_oracle.py`, `controller/hid_xinput_oracle.py`, `controller/l2b_imu_press_correlation.py`, `controller/l2c_stick_imu_correlation.py` |
| Bridge service | Python asyncio | `bridge/vapi_bridge/` — `insight_synthesizer.py`, `bridge_agent.py`, `calibration_intelligence_agent.py`, `behavioral_archaeologist.py`, `network_correlation_detector.py`, `federation_bus.py`, `alert_router.py` |
| Smart contracts | Solidity | `contracts/` — `PoACVerifier.sol`, `PHGRegistry.sol`, `PHGCredential.sol`, `TournamentGateV3.sol`, `PITLSessionRegistry.sol`, `SkillOracle.sol`, `FederatedThreatRegistry.sol` |
| Scripts | Python | `scripts/threshold_calibrator.py`, `scripts/run_adversarial_validation.py` (9-feature proxy Phase 49), `scripts/interperson_separation_analyzer.py`, `scripts/l6_threshold_calibrator.py`, `scripts/phase_coherence_calibration.py` (negative result, keep), `scripts/generate_professional_adversarial.py` (Phase 48) |
| Calibration data | JSON | `sessions/human/hw_005` through `sessions/hw_078` (N=74, 3 players) |
| Frontend dashboard | React JSX | `frontend/VAPIDashboard.jsx` — 850+ lines, void-black + electric orange + cyan |
| Whitepaper | Markdown | `docs/vapi-whitepaper-v3.md` |

## PoAC Wire Format — FROZEN, DO NOT MODIFY

228 bytes total: 164-byte signed body + 64-byte ECDSA-P256 signature.
Chain link hash = SHA-256(raw[0:164]) — 164-byte body only, NOT full 228 bytes.

## PITL Nine-Level Stack

| Layer | Code | Type | Signal |
|-------|------|------|--------|
| L0 | — | Structural | HID presence |
| L1 | — | Structural | PoAC chain integrity |
| L2 | 0x28 | Hard cheat | IMU gravity + HID/XInput discrepancy |
| L3 | 0x29/0x2A | Hard cheat | TinyML behavioral classifier |
| L2B | 0x31 | Advisory | IMU-button causal latency |
| L2C | 0x32 | Advisory | Stick-IMU cross-correlation (inactive in dead-zone stick games) |
| L4 | 0x30 | Advisory | 12-feature Mahalanobis biometric fingerprint |
| L5 | 0x2B | Advisory | Temporal rhythm (CV, entropy, quantization) |
| L6 | — | Advisory | Active haptic challenge-response (disabled by default) |

Hard codes {0x28, 0x29, 0x2A} block tournament eligibility.
L2C returns None in dead-zone stick games (NCAA CFB 26) — 0.10 weight resolves to 0.5 neutral prior.

## Calibration Corpus State (2026-04-11) — 3-PLAYER CORPUS (P4 ELIMINATED)

- Total session files: **153 terminal + ~64 hw = 217 total** (5 excluded; massive new captures 2026-04-11)
  - Player 1: 50 terminal sessions (hw_005–hw_042 exc. 2 polling-rate + terminal_cal_P1; **8 touchpad_corners sessions**)
  - Player 2: 55 terminal sessions (terminal_cal_P2; **11 touchpad_corners sessions**)
  - Player 3: 48 terminal sessions (terminal_cal_P3; **10 touchpad_corners sessions**)
  - Player 4: **ELIMINATED** — confirmed same person as Player 3; all terminal_cal_P4 files moved to terminal_cal_P3
  - 5 excluded (polling_rate_hz outside [800, 1100]: hw_043, hw_044, hw_067, hw_069, hw_073)
- **CURRENT STATE (2026-04-20, UPDATED): AIT DEFENSIBILITY GATE CLEAR — all players >=10 sessions**
  - **AIT probe (Phase 229, 2026-04-18)**: ratio=**1.199**, all_pairs_above_1=**True** (N=24: P1=6/P2=5/P3=13) — Phase 229 baseline
  - **AIT corpus (Phase 231, 2026-04-20)**: N=37 total — P1=13/P2=10/P3=14; all players >=10; ait_defensibility_ok=True; STAGED_GRADUATION_ENABLED=true
  - AIT inter-player: P1vP2=1.850, P1vP3=1.846, P2vP3=1.349 — ALL >1.0 (TOURNAMENT BLOCKER CLEARED for AIT)
  - AIT LOO accuracy: 66.7% (16/24); cov_mode=full (N/p=6.0 > COV_MIN_RATIO=3.0)
  - AIT features [4]: accel_tremor_peak_hz (4096-pt FFT 4-15 Hz, parabolic interp) + roll_cos/roll_sin/pitch_cos (gravity postural fingerprint, circular encoding)
  - AIT physics: L2 hold at 50% (90-180 analog), 30s; still-hold activates accel tremor (right_stick=128 neutral); gravity vector anatomically stable per player in normal gaming posture
  - **Touchpad corners (superseded for primary gate)**: N=35, ratio=0.728 (2026-04-11); P2/P3 biometric proximity structurally prevents crossing 1.0; diagnostic ceiling confirmed
  - **tremor_resting corpus (2026-04-12)**: ratio=0.748 (N=24); all_pairs_p0_ok=False (P1vP3=0.032 per G-001); tremor_peak_hz now non-zero via Phase 205 AccelTremorFFT; P3 non-stationarity still limiting
  - **Path forward**: AIT defensibility gate CLEAR (Phase 231 — P1=13/P2=10/P3=14 all>=10); run POST /agent/activate-graduation-stage {agent_id: "ruling_enforcement_agent"} to execute Stage 1; then run --session-type ait --write-snapshot to persist N=37 corpus to DB
  - NOTE: Phase 231 COMPLETE — ait_defensibility_ok=True (11th P0 condition); STAGED_GRADUATION_ENABLED=true; Stage 1 pending API call; Phase 230 NOTE: insert_ait_session() mirrors to separation_defensibility_log; all_pairs_p0_ok=True
  - WIF-024: CLOSED Phase 165 — post_erasure_recompute audit trail implemented
- **Full corpus (N=217, all session types)**: ratio=0.060 — EXPECTED/KNOWN (free-form gameplay doesn't separate players; this is the WIF-009 plateau regime result; never use this as the tournament gate metric)
- **PHASE 143 RESULT (2026-04-02): N=11 — historical baseline (superseded by N=14 above)**
  - Separation ratio: **1.261** (diagonal covariance, N/p=1.375 < 3.0, Phase 142 auto-fallback)
  - Classification: **63.6% (7/11, proper LOO)** — honest estimate (Phase 143); 4 misclassified sessions
  - Inter-player pairs: P1 vs P2=2.868, P1 vs P3=3.276, P2 vs P3=2.243
  - Intra-player: P1 mean=2.963 (N=3), P2 mean=1.976 (N=4), P3 mean=1.711 (N=4)
  - NOTE: diagonal covariance correct for N=11; full Tikhonov suppressed P1/P3 to 0.127 (97% suppression)
  - Per-pair attribution: P1vP2 top=micro_tremor+stick_autocorr; P1vP3 top=touch_position_variance+touchpad_spatial_entropy
- **PHASE 138 RESULT (2026-04-02): Full Tikhonov covariance (SUPERSEDED by Phase 143)**
  - Separation ratio: **1.552** — inflated by full covariance; P1 vs P3 distance=0.127 was noise-suppressed
  - Classification: 63.6% (7/11, biased-centroid LOO) — same classification but different error profile
  - Inter-player pairs: P1 vs P2=1.428, P1 vs P3=0.127, P2 vs P3=1.304
  - Intra-player: P1 mean=0.839 (N=3, full covariance), P2 mean=0.505, P3 mean=0.499
  - **P1/P3 distance=0.127 was covariance noise artifact** — diagonal (Phase 142) gives P1vP3=3.276
- **PHASE 137B RESULT (2026-03-30): PRE-MERGE reference only**
  - Ratio was 1.469 (N=11, 4 players P1=3/P2=4/P3=3/P4=1) — P4 counted as separate → SUPERSEDED
  - P3 vs P4 distance=0.074 was intra-player variance (same person), incorrectly counted as inter-player
- **PHASE 137A RESULT (2026-03-30): WIF-007 balanced corpus confirmation**
  - Balanced ratio: **1.611** (n=3/player, N=12 balanced; seed=42; per-player equalization)
  - WIF-007 confirmed: P1's 53 sessions bias global covariance; balanced ratio >> pooled ratio
  - Reliable estimate requires ≥10 sessions/player balanced
- Full corpus separation ratio: **0.417 pooled** (N=127 pre-merge, 2026-03-29) — STALE, superseded by 1.261 (diagonal+LOO, touchpad_corners, Phase 143)
  - Classification rate on full corpus: 30.8% — free-form gameplay insufficient for separation
- L4 thresholds CONFIRMED (2026-04-02): ran threshold_calibrator.py on all 74 hw_*.json → anomaly=**7.009**, continuity=**5.367** — IDENTICAL to stored values; staleness is dimension-only (calib_dim=12 vs live_dim=13); touchpad_spatial_entropy is structurally 0 in gameplay sessions so adding it doesn't change thresholds; thresholds remain valid for gameplay sessions
- Phase 139 COMPLETE: _TERMINAL_CAL_ONLY_TYPES fast-path in analyze_interperson_separation.py — skips 74 hw_* sessions when session_type_filter in {touchpad_corners, freeform, swipes, ...}; reduces analysis runtime from 120s+ to <30s; Bridge +8 (1734→1742); SDK 233 unchanged; Hardhat 462 unchanged
- Phase 144 COMPLETE: --player-quality-report flag; _compute_player_quality_scores() per-player stability/probe-type/enrollment-ready/recommendations; ENROLLMENT_STABILITY_THRESHOLD=0.70 ENROLLMENT_MIN_PROBE_TYPES=2; Bridge +8 (1774→1782); SDK 233 unchanged; Hardhat 462 unchanged
- Phase 140 COMPLETE: --probe-comparison flag; runs all 3 touchpad probe types (corners/freeform/swipes) and outputs comparison table with ratio/classification/inter/intra/P1vP3; Bridge +8 (1742→1750); SDK 233 unchanged; Hardhat 462 unchanged
- Touchpad coverage: P1=6 touchpad_corners, P2=7 touchpad_corners, **P3=7 touchpad_corners** (total 20, 2026-04-05)
  - touchpad_freeform and touchpad_swipes: roughly symmetric with corners; exact counts from analysis script

## L4 Calibration State (Phase 57, N=74)

- Calibration corpus: hw_005–hw_078 (N=74 including newer tremor/touchpad sessions)
- Feature space: 12 features, 10 active (Phase 46 added accel_magnitude_spectral_entropy; Phase 57 added press_timing_jitter_variance)
- Active features (10): trigger_resistance_change_rate(excl), trigger_onset_velocity_L2,
  trigger_onset_velocity_R2, micro_tremor_accel_variance, grip_asymmetry,
  stick_autocorr_lag1, stick_autocorr_lag5, tremor_peak_hz, tremor_band_power,
  accel_magnitude_spectral_entropy, touch_position_variance(excl pending recapture),
  press_timing_jitter_variance (index 11 — normalised IBI variance; human 0.001–0.05; bot macro <0.00005)
- Structurally zero / excluded: trigger_resistance_change_rate, touch_position_variance
  (touchpad_active_fraction replaced by accel_magnitude_spectral_entropy in Phase 46)
- L4 anomaly threshold: **7.009** (mean+3σ, Phase 57, N=74, 12-feature space — was 6.726 Phase 46)
- L4 continuity threshold: **5.367** (mean+2σ, Phase 57, N=74, 12-feature space — was 5.097 Phase 46)
- Threshold rise (+4.2%/+5.3%): expected — press_timing_jitter_variance adds real variance, expands Mahalanobis distribution
- Inter-person separation ratio: 0.362 — L4 is intra-player anomaly detector only
- Human false positive rate: ~2.9% (expected at 3σ)

## accel_magnitude_spectral_entropy (Phase 46, index 9)

Replaces structurally-zero touchpad_active_fraction.
Physics: Shannon entropy of the 0–500 Hz power spectrum of DC-removed ||accel||.
Requires 1000 Hz polling — cannot be computed on standard HID (125–250 Hz) devices.
Ring buffer: 1024 frames, follows Phase 41 pattern (returns 0.0 until filled).
Human range: 3–8.6 bits, tightly centered at 4.8–4.9 bits (std 1.303).
Static injection: 0.0 (variance guard). Random noise: ~9.0 bits (detectable).
Player means nearly identical (P1: 4.878, P2: 4.882, P3: 4.767) — bot-vs-human
discriminator only, NOT inter-player identifier. Does not improve separation ratio.
Negative result documented: docs/phase-coherence-calibration.md (accel_phase_coherence
ruled out — gravity dominates accel during still frames in handheld gaming grip).

## Humanity Probability Formula (Phase 46)

Without L6 (default):
  humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·p_L2B + 0.10·p_L2C
  NOTE: p_L2C resolves to 0.5 neutral prior in dead-zone stick games (NCAA CFB 26).
  Formula runs as effective 4-signal in practice for this game corpus.

With L6 active:
  p_human = 0.23·p_L4 + 0.22·p_L5 + 0.15·p_E4 + 0.15·p_L6 + 0.15·p_L2B + 0.10·p_L2C

## Phase Summary

| Phase | Key milestone |
|-------|---------------|
| ... | _Phase 17 through Phase 229 archived to `wiki/phases/phase_summary_archive_17_229.md` (28 rows; foundational arcs through pre-grind hardening). Inline table below retains Phase 230+ (current operational phases)._ |
| 236-WATCHDOG | Bridge Process Watchdog + Watchdog Event Chain (WEC) — VAPI-exclusive supervisor for the GIC grind. scripts/bridge_watchdog.py NEW (urllib stdlib only): polls /health every 10s; spawns bridge via subprocess.Popen([sys.executable, "-m", "bridge.vapi_bridge.main"]); exp backoff 5/10/30/60s capped at auto_grind 60s cadence; 3 restarts/hr ceiling → WATCHDOG_HALT. Three guards make it VAPI-architectural (not generic supervisord): (1) refuses restart when chain_intact=False — preserves INV-GIC-003 at ops layer; (2) refuses restart when GRIND_SESSION_ID drifts in bridge/.env — silent-rotation guard; (3) restart-rate ceiling. bridge/vapi_bridge/watchdog_chain.py NEW: WEC FROZEN FORMULA v1 — WEC_N=SHA-256(prev(32)||code(1)||pid(4)||sid_hash(16)||ts_ns_be(8))=61B→32B; genesis tag VAPI-WEC-GENESIS-v1; sid_hash=SHA-256(grind_session_id)[:16]; EVENT_CODES (BRIDGE_START 0x01 / HEALTHY 0x02 / UNRESPONSIVE 0x03 / RESTART_TRIGGERED 0x04 / RESTART_REFUSED_GIC 0x05 / RESTART_REFUSED_SID 0x06 / DEGRADED_HOST 0x07 / BACKOFF_CEILING 0xFE / HALT 0xFF). store.py: watchdog_event_log table (Phase 236 migration; 2 indexes); insert_watchdog_event() with monotonicity guard (ts_ns≤prev → bumped to prev+1); get_watchdog_event_chain_status() recomputes full chain + reports restarts_last_hour. operator_api.py: GET /operator/watchdog-status (10 keys; _check_read_key auth). T236-WD-1..8: 8 bridge tests (genesis det / single-link / 3-event chain / tamper detect / monotonicity / session scoping / restart count / invalid input ValueError). Pairs with GIC chain (Phase 235-A): GIC=cognitive-session continuity, WEC=operational continuity. Together = tamper-evident provenance for grind run. Bridge 2477→2485 +8; SDK 535 unchanged; Hardhat 522 unchanged; Contracts 45 unchanged |
| 235-GAD | Gameplay Activity Discrimination — binary trigger-active gate on consecutive_clean; ACTIVE_GAMEPLAY=any L2/R2 press (trigger_active_fraction>0); MENU_DETECTED=zero presses (breaks streak); NULL=pass-through (pre-GAD rows); gameplay_discrimination_enabled:bool=True config; trigger_active column on records; gameplay_context column on ruling_validation_log; gameplay_classification_disagreements table; dualshock_integration.py: trigger_active derived from trigger_onset_velocity_l2/r2>0; session_adjudicator.py: trigger_active_fraction in evidence_summary; session_adjudicator_validator.py: gameplay_context from evidence + 4th GIC eligibility condition (gameplay_ok=ctx!="MENU_DETECTED"); operator_api.py: GET /bridge/capture-health +gameplay_context_enabled+latest_gameplay_context; GET /bridge/grind-chain-status +latest_gameplay_context; POST /operator/override-gameplay-context; 10 bridge+2 SDK; Bridge 2434→2444; SDK 525→527 |
| 235-GPC | Pre-Grind Validation — 10-category verification before 100-session grind; regression fixes: pcc_state/pcc_host_state backfilled in 7 test files + activation_simulation.py seed_validation_records(); store.get_prev_gic_ts_ns() NEW; session_adjudicator_validator: time.time_ns()+monotonicity guard (INV-GIC-002); main.py: import os + GRIND_SESSION_ID startup log (warns if env var not set); operator_api.py: POST /operator/gic-reset (requires api_key query param + reason≥10 chars; clears app._gic_chain_broken; logs to agent_events; was_broken+reason+timestamp response); bridge/tests/test_phase235_grind_precheck.py: 4 tests (T235-GPC-1: LLM exception→fallback deterministic; T235-GPC-2: llm_verdict==fallback_verdict→divergence=0→consecutive_clean advances; T235-GPC-3: gic-reset 403 without key; T235-GPC-4: gic-reset clears flag+returns JSON); docs/pre_grind_validation_report.md NEW (10-category report); 4 bridge; Bridge 2430→2434; SDK 525; Hardhat 522 |
| 235-A | Grind Integrity Chain (GIC) — FROZEN SHA-256 chain over grind sessions; GIC_N=SHA-256(prev(32)||ch(32)||verdict(1)||host(1)||ts_ns_be(8)); genesis_gic(grind_session_id,ts_ns); only fallback_verdict hashed (not llm_verdict); grind_chain.py NEW (VERDICT_CODES/PCC_HOST_CODES/genesis_gic/compute_gic); config grind_session_id; store: gic_ts_ns column+get_prev_grind_chain_hash+update_grind_chain_hash+get_grind_chain_status; operator_api: GET /bridge/grind-chain-status; GrindChainResult(7 slots)+VAPIGrindChain SDK; startup chain integrity check; 8 bridge+4 SDK; Bridge 2422→2430; SDK 521→525 |
| 235-PCC-SPC | Statistical Process Control + 3-signal haptic-tolerance binding + frequency-band gate + outlier trim. Data-anchored from session 2026-05-03 (887 PCC snapshots / 26.6K record obs). capture_continuity.py: 5-tuple sample buffer (rate, ts, trigger_active, accel_var, tremor_peak_hz); _classify_capture_state_spc decision tree (haptic-tolerance → SPC capability → classic fallback); _haptic_tolerance_active 3-signal binding (trigger_active=1 AND accel_var≥0.0003 AND tremor_peak in [4,60]Hz, window≤500ms). dualshock_integration.py: _last_bio_features snapshot + 3 update_sample call sites pass kwargs. config: 8 SPC fields + _env_float helper (USL=3500, in_control=0.85, freq band [4,60]Hz). PV-CI 32→36 (+INV-PCC-002/003/004/005). 15 tests T-SPC-1..15. Pcc_spc_enabled=False default (opt-in via PCC_SPC_ENABLED env). When False, classifier byte-identical to Phase 234.7. INV-PCC-003 fail-closed precedence: signal_disconnect ALWAYS overrides SPC. Three Novel Assurances accepted with bindings: A (3-signal haptic evidence) + B (LSL strict, USL trim only) + C (disconnect override). Wallet zero. Bridge 2517→2532 +15; SDK 539 unchanged; Hardhat 528 unchanged |
| 235-B | PCC Attestation Slot — ruling_validation_log +pcc_state+pcc_host_state+grind_chain_hash+gic_ts_ns (Phase 2350 migration); consecutive_clean PCC gate: pcc_state=NOMINAL AND pcc_host_state in (EXCLUSIVE_USB,UNKNOWN) required (NULL=fail-closed); session_adjudicator_validator: PCC snapshot via get_capture_health_status() at validation time; 4 bridge+2 SDK; Bridge 2418→2422; SDK 519→521 |
| 234.7 | Physical Capture Continuity (PCC) — CaptureHealthMonitor (NOMINAL/DEGRADED/DISCONNECTED + EXCLUSIVE_USB/CONTESTED/UNKNOWN host state inference via poll-rate CV); grind_ready gate (NOMINAL+EXCLUSIVE_USB/UNKNOWN+30s sustained); session_counting_paused=grind_mode AND NOT grind_ready; 6 config fields (pcc_enabled/pcc_nominal_hz/pcc_degraded_hz/pcc_stable_window_s/grind_mode/grind_target); capture_health_log store; GET /bridge/capture-health (11 keys); CaptureHealthResult(11 slots)+VAPICaptureContinuity SDK; DualShockTransport.set_pcc_monitor() wiring; 10 bridge+4 SDK; Bridge 2408→2418; SDK 515→519 |
| 234 | InsightSynthesizer HTTP Timeout Fix — Mode 6 _synthesize_living_calibration_sync extracted; asyncio.to_thread wrapper prevents 54s event loop stall on startup; 8 bridge; Bridge 2400→2408; SDK 515; Hardhat 522 |
| 234.5 | Consecutive Clean Semantics Audit — divergence=verdicts_differ AND delta>0.30; advisory codes→FLAG→no divergence; clean sessions→FLAG(0.05); enrollment eligible→CERTIFY(0.8); same verdict never diverges; no code changes |
| 231 | AIT Defensibility P0 Gate + Stage 1 Graduation — ait_defensibility_ok 11th P0 condition (all_pairs_above_1=True AND all players >=10 AIT sessions; fail-closed); store.py: ALTER TABLE +ait_defensibility_ok; get_ait_separation_status() +n_per_player; operator_api.py: ait_defensibility_ok in overall_pass+conditions+response+commit-activation blocker; TournamentPreflightResult 11 slots; openapi +ait_defensibility_ok; analyze_interperson_separation.py Phase 231 write-snapshot gap fixed; STAGED_GRADUATION_ENABLED=true; AIT corpus P1=13/P2=10/P3=14 N=37 all>=10; 8 bridge+4 SDK; Bridge 2392→2400; SDK 511→515 |
| 230 | AIT P0 Gate Wire-up — insert_ait_session() mirrors into separation_defensibility_log (session_type='ait'); tournament_preflight all_pairs_p0_ok reads AIT; operator_api.py bugfix: get_biometric_renewal_chain_status(limit=1)→() + len()>0→total_renewals check; heals Phase 127 test_4; 8 bridge; Bridge 2384→2392; SDK 512; Hardhat 522 |
| <=229 | _Phases 109A-229 archived 2026-05-22 to `wiki/phases/phase_archive_2026_05_notes_and_summary.md` (full per-phase detail preserved verbatim). Earlier Phase 17-229 narrative in `wiki/phases/phase_summary_archive_17_229.md`. Inline table below retains Phase 230+ only, per curation discipline._ |

## Open Gaps

Historical Phase 48 open-gaps roster archived to `wiki/phases/closed_gaps_phase_48.md` (4 items: L2C phantom CLOSED, separation ratio still OPEN/HIGH but tracked via Phase 229 AIT breakthrough, touchpad recapture pending hardware, professional adversarial data CLOSED). Current open gaps tracked in MEMORY.md auto-memory entries + WIF corpus.
## ZK Circuit

Groth16, BN254, ~1,820 constraints, 2^11 powers-of-tau.
PITLSessionRegistry: `0x8da0A497234C57914a46279A8F938C07D3Eb5f12`
PitlSessionProofVerifier: `0x07D3ca1548678410edC505406f022399920d4072`

## BridgeAgent + CalibrationIntelligenceAgent (Phase 50) + Game Profile (Phase 51)

BridgeAgent: claude-sonnet-4-6. 28 deterministic tool bindings (17 original + 3 Phase 50 + 1 Phase 51 + 4 Phase 58 + 1 Phase 59).
GET /operator/agent/stream (SSE, 60 req/min). SQLite session persistence.
Phase 50: check_threshold_drift() wired to InsightSynthesizer Mode 6 callback.
Phase 50: react() emits recalibration_needed agent_events when drift_velocity > 0.6.
Phase 51: get_game_profile() tool — returns active game profile, L5 priority, L6-Passive stats.

CalibrationIntelligenceAgent: claude-sonnet-4-6. 6 calibration specialist tools.
GET /operator/calibration/stream + POST /operator/calibration/agent.
run_event_consumer() polls agent_events table every 30 min.
Enforces min() unconditionally on trigger_recalibration — thresholds can only tighten.

## Game-Aware Profiling (Phase 51)

Active profile: ncaa_cfb_26 (set via GAME_PROFILE_ID=ncaa_cfb_26 in bridge/.env).
L5 button priority overridden: R2 (sprint) > Cross > L2_dig > Triangle — football-specific.
L6-Passive: per-press R2 onset tracking (no controller writes, no PS5 conflict). Bootstrap N=20,
EMA α=0.15, flag_ratio=1.5 (50% slower than personal mean = PS5 haptic resistance event).
game_profile.py: GameProfile frozen dataclass + registry; ncaa_cfb_26 registered at import.
rhythm_hash() canonical order UNCHANGED — sensor commitment invariant preserved.

## Hardware

DualShock Edge CFI-ZCP1, USB-C, Windows 11, hidapi VID=0x054C PID=0x0DF2 interface 3.
USB polling: 1002 Hz. Injection margin: 14,000× (accel), 10,000× (gyro).
Micro-tremor variance: 278,239 LSB².

## roadmap_post_stage_1

Captured ideas for post-grind / post-Stage-1 work. Do NOT implement
or design further — these are intentionally minimal stubs preserved
so they're not lost between phases. Promote to a real phase only
after Stage 1 graduation activates and GIC_100 is deposited.

- **Phase 240+ candidate — L6-Response (haptic-driven stimulus-response biometric layer)**:
  Leverage DualSense Edge haptic motor commands and adaptive trigger
  output as ambient stimuli during normal play. Capture player reflex
  response in the 80–280 ms window post-stimulus (within human
  voluntary-reaction-time band; faster = bot, slower = inattention).
  Build per-player stimulus-response baselines from the GIC_100+
  corpus once it exists. Activate `L6_CHALLENGES_ENABLED` only when
  N≥50 calibration sessions exist per player. Do NOT activate before
  GIC_100 lands — without that corpus the baselines are
  unstable. Sub-perceptual amplitudes (≤60/255) so play experience is
  unaffected. Exclusive to PS5-class haptic hardware; not replicable
  on generic gamepads.

## Verification-First Discipline

Canonical name for the work pattern that has shaped VAPI's protocol commits. Joins the existing protocol vocabulary (FROZEN-v1, PV-CI, AGaaS, deferred-activation) without redefining those terms.

The pattern structures consequential architectural work as six ordered steps:

1. **Pre-implementation verification** (V-numbered checks). Read state, confirm assumptions, identify drift between the operator's brief and observable reality.
2. **Hold for operator review at the verification checkpoint.** Surface findings, including any drift; the operator decides whether to proceed, refine the brief, or abort.
3. **Implementation.** Execute against the corrected brief.
4. **Post-implementation verification** (P-numbered checks). Confirm the change matches intent and the working tree is in the expected shape.
5. **Hold for operator review before staging.** No commit happens without explicit approval.
6. **Atomic commit with architectural reasoning preserved in the message body**, then push.

What the pattern produces:
- Drift correction in both directions. V-checks catch wrong assumptions in the prompt (the brief revises against reality); P-checks catch divergence during execution (the implementation revises against the brief).
- Architectural reasoning preserved in the permanent record. Decision blocks, rejected alternatives, and "why this rather than that" land in commit bodies — not in chat scrollback that disappears at the next compaction.
- Operator authority over architectural decisions enforced procedurally. Holds are not optional; the pattern fails closed if a checkpoint is skipped.

Demonstrating commits (Phase O0 pause-period work, 2026-04-27 → 2026-04-29):
- The eighteen-commit Phase O0 implementation arc (Streams 1–5 source-and-tests).
- `b261b546` — Stream 2-deploy local Hardhat dry-run runbook.
- `f8c577ab` — Phase O0 pause-point capture (commit roster, dependency graph, resumption checklist).
- `e3fbebd4` — Phase 237.5 Path C+ residual: batcher dead-letters `chain_submission_paused` errors immediately.
- `97a0eab4` — Frontend connectivity verification report.
- `29b57707` — Dead frontend code cleanup identified by the connectivity verification.
- `9ee11471` — Chain wrapper verification report.

Where the pattern applies:
- Consequential architectural work (new primitives, contract changes, agent additions, invariant edits).
- Multi-step atomic commits where the diff alone doesn't carry the reasoning.
- Verification-reference documents that future sessions read instead of re-deriving state.

Where it does not apply:
- Conversational discussion, brief-clarification, brainstorming.
- Operational coordination (scheduling agents, drafting messages, status updates).
- Read-only information gathering with no resulting commit.

The pattern itself is the canonical name's claim: protocol commits ship through it, including the commit that introduces this section.

## BT Calibration: Canonical Prerequisite Anchor

**[CANONICAL]** Any BT-related design work in VAPI must read `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf` before producing architectural proposals, feature definitions, threat-model claims, or capture-session plans. This document is the canonical prerequisite anchor for the protocol's Bluetooth expansion path. It establishes the literature anchors, the empirical unknowns that must be resolved by pre-corpus measurement, and the constraint envelope for what L8 v1 claims and does not claim.

The four corrections that the canonical anchor establishes against the v1.0 architectural proposal are: (1) the DualSense and DualSense Edge transport is Bluetooth Classic BR/EDR with HIDP, not BLE/HOGP, which means BLE-named primitives such as advertising interval, connection events, advDelay, and GATT do not exist on this transport and any feature derived from them is structurally invalid; (2) of the four originally-proposed L4 features, only `rssi_variance_normalized` survives unmodified, with the rest either reframed against BR/EDR primitives (poll-interval Tpoll variance, AFH-aware retransmission slotting) or dropped entirely (advertisement_period_drift has no BR/EDR analog); (3) the threat-model anchor narrows from broad "spatial co-presence attestation" to the specific cloud-gaming-bot stealth pattern, with concrete documented attack instances (WormVision Lite MAX userscript published 2024-12-26, NVIDIA's GeForce NOW anti-cheat compatibility guide conceding the cloud-client attestation gap, Activision RICOCHET Season 02 input-pattern detection rolling out against this attack class on the input-stream side); (4) the novelty claim splits into a detection layer that inherits BlueShield's published FN floors as a baseline (5.84% CFO, 8.72% RSSI, 2.37% combined FP per Wu et al. RAID 2020) and a forensic/governance layer where the genuine novelty lives — cross-tournament portability of witness signatures, non-repudiable temporal ordering for adjudication disputes, on-chain TWC commitments verifiable months later by parties not in the original trust chain.

The witness device for v1 is LAN-tower-only (BlueZ + USB BT dongle + Python wrapper, ~one week of engineering on top of the architectural prerequisites). Mobile witness is structurally degraded — iOS Core Bluetooth throttles RSSI reads to ~1 Hz per peripheral and does not expose raw HCI events to user-space apps, while Android BLE APIs do not expose raw HCI without root and custom firmware — and is deferred to v2. The L8 v1 claim is session-bound presence attestation only; cross-session and cross-tournament controller identity claims require a same-model separability study for N≥3 identical DualSense Edges that does not exist in the public literature, and are explicitly out of scope until that study is completed.

**[SUPERSEDED-BT-CALIB-LESSON-001]** The v1.0 BT calibration architectural proposal naming BLE-derived L4 features (`connection_interval_jitter`, `advertisement_period_drift`, BLE-specific `retransmission_rate`) is superseded by the canonical anchor and the v1.1 architectural revision. The verification gap that produced the supersession is documented in `lessons.md` entry `BT-CALIB-LESSON-001`. Future BT design work cites the canonical anchor and the v1.1 revision; it does not re-derive features from the v1.0 proposal.

**Application protocol.** Architectural revisions live in `wiki/methodology/bt_calibration_v*.md` with monotonic version numbers. Each revision supersedes prior versions explicitly with a `[SUPERSEDED-{version}]` annotation. Prototype code, whitepaper revisions, and external review materials cite the highest-version revision document by path. Capture-session planning is gated on the v1.1 revision document being read and acknowledged in the current session.

## Sensor Stack v2: Canonical Prerequisite Anchor

**[CANONICAL]** Any DualSense Edge sensor-stack design work in VAPI must read `wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf` before producing architectural proposals, feature definitions, threat-model claims, or capture-session plans for the v2 L4 feature set. This document is the canonical prerequisite anchor for the protocol's DualSense Edge sensor-surface expansion path. It establishes the per-surface verification blocks (vendor-spec + open-source driver + literature anchor, three independent classes per BT-CALIB-LESSON-001 application rule), the per-surface tier assignments (PRIMARY / CO-SIGNAL / ADVISORY / DROPPED), the empirical unknowns that must be resolved by pre-corpus measurement, and the same-controller-population separability constraint applied per-surface.

The six surface-tier assignments the Track 1 research established are: **Surface 1 (adaptive trigger force-curve) → PRIMARY DISCRIMINATOR**, vendor-spec verified through `hid-playstation.c` + PSDevWiki + SensePost + DualSense-Windows + pydualsense; 8-bit per trigger axis at ~1 kHz on Edge over USB; inter-subject EER 1-15% lab-to-field per Saevanee 2009 / Antal 2015 / Wakita 2006 / Miyajima 2007 / Van Vugt 2013; adversarial spoof cost very high because translator-class hardware (Cronus Zen / XIM / reWASD) does not synthesize biomechanically-structured continuous force curves; also functions as L4-coupled-to-L6 challenge-response channel via `Slope` / `Vibration` adaptive-trigger output reports. **Surface 2 (touchpad capacitive) → CO-SIGNAL**, 12-bit X/Y 2-point with no pressure proxy, binding constraint is data volume per session not per-event separability. **Surface 3 (microphone array) → DROPPED at default scope** on privacy-falsification grounds (Cruz v. Fireflies AI analog plus single-channel-post-DSP reality invalidates multi-mic literature transfer); narrow non-speech RIR feature subset is research-only and not on v2 L4 critical path. **Surface 4 (lightbar optical emission) → CO-SIGNAL** as challenge-response witness channel only (tournament-station camera observes host-issued 3-color symbol stream at 5-15 symbols/second producing 25-75 bits over 5-second authentication window; analog of LAN-tower BlueZ BT witness with fully-passive camera advantage). **Surface 5 (battery drain) → ADVISORY ONLY** (4-bit 11-bucket level at multi-minute change cadence; too coarse for per-round/per-match temporal structure; useful as session-integrity check over 30+ minute windows only). **Surface 6 → split**: stick analog noise floor → CO-SIGNAL (held/unheld binary plus tremor-band variance as supporting evidence at the 8-bit quantization floor); Hall-effect stick per-unit fingerprinting → ADVISORY ONLY, marked session-bound presence only, blocked from cross-session controller identity until same-model separability study runs per CROSS-LESSON-001.

**Stage A measurement gates** (must complete before v2 L4 architecture spec exits draft state): Empirical Unknown #1 (intra-player vs inter-player Mahalanobis on N=10 players × 100 trigger pulls × 3 game contexts; decision threshold > 1.0 separation ratio for primary discriminator status) and Empirical Unknown #4 (Hall-effect stick same-model same-batch separability on N=20 stock + N=20 batched-aftermarket Edge units; decision threshold > 20% rank-1 on same-model same-batch). **Stage B** (after Stage A measurements land): implement adaptive-trigger challenge-response as L4-coupled-to-L6 in v2.

**Critical fact-correction load-bearing for future work:** The DualSense Edge ships from Sony with ALPS Alpine **potentiometer-based** stick modules, NOT Hall-effect. The Edge's **trigger** sensors are Hall-effect from factory (gamepadtest.app), but the stick sensors are not. Aftermarket Hall-effect (GuliKit, ZeroStick Pro) and TMR modules (MODDEDZONE, Battle Beaver, XP Controllers) exist and are increasingly common in the competitive Edge scene. Any future architectural reference to "DualSense Edge Hall-effect sticks" without aftermarket qualifier is incorrect.

**[SUPERSEDED-TRACK1-LESSON-002]** The v2.0 sensor-stack ideation naming the microphone array as a multi-mic acoustic-fingerprinting surface is superseded by the canonical anchor and the v2.1 architectural revision; the DualSense exposes a single mono UAC1 stream post-DSP, not a multi-mic array, and the multi-mic literature does not transfer. The verification gap that produced the supersession is documented in `lessons.md` entry `TRACK1-LESSON-002`.

**[SUPERSEDED-TRACK1-LESSON-003]** The v2.0 sensor-stack ideation framing the microphone array as a "narrow non-speech feature subset can preserve privacy" path is superseded by the canonical anchor and the v2.1 architectural revision; concrete BIPA litigation (Beil v. Petco, Cruz v. Fireflies AI), GDPR Art. 9, and CIPA two-party-consent regimes attach to capture-and-storage regardless of downstream use, and tournament terms-of-service consent does not reach incidentally-captured household third parties. The verification gap is documented in `lessons.md` entry `TRACK1-LESSON-003`. The optical-witness path on Surface 4 is strictly preferable on every privacy axis if a passive-presence channel is later required.

**Cross-lesson dependency.** `lessons.md` entry `CROSS-LESSON-001` (same-controller-population separability constraint) applies cross-surface to both L8 BT and L4 v2 Hall-effect stick. The constraint is now load-bearing for all future controller-internal physical fingerprint claims and is referenced by both `bt_calibration_v1_1_architectural_revision.md` and `sensor_stack_v2_1_architectural_revision.md`.

**Application protocol.** Architectural revisions live in `wiki/methodology/sensor_stack_v*.md` with monotonic version numbers (parallel to BT calibration `wiki/methodology/bt_calibration_v*.md`). Each revision supersedes prior versions explicitly with a `[SUPERSEDED-{version}]` annotation. Prototype code, whitepaper revisions, and external review materials cite the highest-version revision document by path. The v2 L4 architecture spec is gated on Stage A pre-corpus measurements (Empirical Unknowns #1 and #4) being completed and the v2.1 revision document being read and acknowledged in the current session.

## Hard Rules

- Never modify the 228-byte PoAC wire format
- Never change chain link hash from SHA-256(164B body)
- Hardware tests gated @pytest.mark.hardware, excluded from CI
- E2E tests require running Hardhat node
- L6_CHALLENGES_ENABLED=false is the correct default
- GSR_ENABLED=false — never change without N≥30 GSR calibration sessions per player (current N=0)
- L6B_ENABLED=false — never change without N≥50 neuromuscular reflex calibration (current N=0)
- Per-player L4 thresholds can only tighten, never loosen (enforced by min())
- Stable EMA track updates on NOMINAL sessions only
- Whitepaper test counts: 1158 bridge, ~1,635 total, ~1,607 CI (stale; CLAUDE.md is authoritative: 2216 bridge, 426 SDK, 482 Hardhat)
- Operator endpoints (/operator/passport, /operator/passport/issue) require valid x-api-key header matching cfg.operator_api_key; return 503 if key unconfigured, 401 if wrong key
- L2C phantom weight must be acknowledged in any humanity formula discussion
- accel_magnitude_spectral_entropy is bot-vs-human only — never claim it improves separation ratio
- ioswarm_enabled=false — never change without live ioSwarm nodes registered
- BLOCK_QUORUM=0.67 — never lower below GENERAL_QUORUM (0.60); W1 mitigation
- Epistemic weight sum = 1.0: {0.35,0.35,0.15,0.15} (swarm on) or {0.40,0.40,0.20} (off)
- Phase 109+ migration order — VHPRenewalAgent first, SessionAdjudicator LAST
- scripts/vapi-swarm-agent.json — single source of truth for ioSwarm task spec; never hand-edit
- WEC FORMULA v1 FROZEN (Phase 236-WATCHDOG) — `WEC_N = SHA-256(prev(32)||code(1)||pid(4)||sid_hash(16)||ts_ns_be(8))`. Genesis tag `VAPI-WEC-GENESIS-v1`. Any change to byte order, event-code table, or hash algorithm requires WEC v2 and a new genesis tag. The WEC chain pairs with GIC v1 — together they prove operational + cognitive continuity for a grind run; never break this pairing
- INV-GIC-003 enforcement at watchdog level — `scripts/bridge_watchdog.py` MUST refuse to restart the bridge when `chain_intact=False` (HTTP) OR `_gic_chain_broken=True` (Store fallback). Restarting masks the break instead of fixing it. Recovery path is operator-only: `POST /operator/gic-reset` + bridge restart
- GRIND_SESSION_ID continuity — watchdog reads bridge/.env once at startup and pins; refuses restart if a different session_id appears mid-lifetime. Watchdog NEVER writes to bridge/.env
- Watchdog rate ceiling — 3 restarts/hour max; beyond that, WATCHDOG_HALT and operator intervention required. Cascading auto-restarts mask faults rather than reveal them
- VAME FORMULA v1 FROZEN (Phase 236-VAME) — `commitment = SHA-256(b"VAPI-VAME-v1" || chain_head_16b || ts_ns_be(8) || endpoint || body_bytes)`. Sidecar response headers ONLY (X-VAME-*), never body wrapper. Any change to byte order, domain tag, or chain-head length requires VAME v2 and a new tag. Hash function will move to Poseidon at Phase 237-ZK-SEPPROOF when circomlib is already a dep — at that point v2 ships. The novelty is the GIC-chain-head binding, not the hash function
- VAME validation never throws — frontend validateVame() returns NO_VAME / OK / MISMATCH; mismatches bump sessionStorage[__vapiVameFailures] but never block the response. Treat VAME as defense-in-depth, not a gate
- Frontend grind-critical hooks MUST set `noMock: true` — useCaptureHealth / useGrindChain / useAutoTriggerStatus / useFleetCoherenceStatus / useAITSeparation / useGrindAnalytics / usePCCIntelligence / useWatchdogStatus all set this. Without it, a transient 5xx flips the dashboard to fabricated mock data with no UI indication mid-grind. Mock fallback is reserved exclusively for first-load discovery before bridge is reachable
- CORPUS-SNAPSHOT FORMULA v1 FROZEN (Phase 236-CORPUS-SNAPSHOT) — `commitment = SHA-256(b"VAPI-CORPUS-SNAPSHOT-v1" || wiki_hash(32) || agent_root(32) || ratio_milli_be(8) || corpus_n_be(8) || ts_ns_be(8))`. Wiki hash walks `wiki/**/*.md` sorted by POSIX-lowercase relative path with explicit `b"--FILE:" + path + b"\n"` separator before each file's bytes. Ratio encoded as uint64 milliratio (ratio×1e6 rounded) for OS-deterministic byte encoding. Any change to byte order, separator format, sort key, or scaling factor requires v2 + new domain tag. The CORPUS-SNAPSHOT chain is the third pillar alongside GIC v1 (per-session cognitive integrity) and WEC v1 (per-restart operational integrity); together they constitute the full grind-run provenance. Never break this triple-pairing
- POST /operator/force-corpus-snapshot requires `reason ≥ 10 chars` (audit field), full `cfg.operator_api_key` authentication (not read-only), and rate-limit-budgeted. On-chain anchoring is intentionally NOT auto-fired — operator must explicitly invoke ProtocolCoherenceRegistry anchor reuse when budget permits. Local snapshot is always written (never gated on chain availability)
- CONSENT FORMULA v1 FROZEN (Phase 237-CONSENT) — `consent_hash = SHA-256(b"VAPI-CONSENT-v1" || device_id_b32 || category_bitmask_be(4) || expires_at_be(8) || ts_ns_be(8))`. Categories enum FROZEN at TOURNAMENT_GATE=0 / ANONYMIZED_RESEARCH=1 / MANUFACTURER_CERT=2 / MARKETPLACE=3 — values are part of the bitmask domain and MUST match VAPIConsentRegistry.sol position-for-position. Any reorder/insert is a v2 break. The consent primitive is the fifth pillar in PATTERN-016 alongside GIC + WEC + VAME + CORPUS-SNAPSHOT
- BRIDGE NEVER GRANTS OR REVOKES CONSENT ON BEHALF OF GAMER — gamer-self-sovereignty invariant. POST /operator/record-category-consent and /operator/revoke-category-consent write ONLY to the local `consent_ledger` (operational truth until on-chain deploy). On-chain `VAPIConsentRegistry.grantConsent / revokeConsent` MUST be called by the gamer's own wallet (msg.sender). The bridge's `chain.is_consent_valid` / `chain.get_consent_record` are READ-ONLY view calls; a malicious or compromised bridge cannot modify consent state, only observe it
- Phase 237 chain.is_consent_valid / get_consent_record FAIL-OPEN (return False / empty dict) when `consent_registry_address == ""`. This is INTENTIONAL — bridge readiness must not depend on contract deploy. The deliberate divergence from `bbg_check_proposal` / `is_dual_eligible` (which raise RuntimeError) reflects: bridge is reader of consent state, not writer; missing on-chain registry must not block local consent_ledger operation

## ioSwarm Integration (Phase 109A+)
- Phase 109A: infrastructure COMPLETE — task spec + consensus aggregator + W3bstream bindings
- ioswarm_enabled=true (Phase 200: set in bridge/.env; emulator mode, no live nodes)
- Phase 109B: VHPRenewalAgent first task spec migration
- Phase 110: VHP as ioSwarm physical action authorization gate (IoTeX DePIN)
- scripts/vapi-swarm-agent.json: ioSwarm task spec (infrastructure only, not yet registered)
- VHP auth gate: require(VAPIProtocolLens.isFullyEligible(operatorDeviceId))

## Build & Test Commands

```bash
python -m pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -q  # 1480 passed
python -m pytest sdk/tests/ -v                                                   # 125
cd contracts && npx hardhat test                                                  # 440
pytest tests/hardware/ -v -m hardware -s                                         # 36 (needs controller)
# Hardware calibration watcher (run while playing NCAA CFB 26):
python scripts/hardware_calibration_watcher.py                                   # writes calibration_sessions/hardware_calibration_progress.json
# ZK ceremony (unblocks 5 skips):
cd /c/Users/Contr/vapi-pebble-prototype/contracts && PATH="$(pwd):$PATH" npx hardhat run scripts/run-ceremony.js
# E2E (needs Hardhat node):
HARDHAT_RPC_URL=http://127.0.0.1:8545 python -m pytest bridge/tests/test_e2e_simulation.py -v
# L6 capture workflow:
python scripts/l6_hardware_check.py
python scripts/l6_capture_session.py --player P1 --game "NCAA Football 26" --target 50
python scripts/l6_threshold_calibrator.py --from-db
```

## Phase 71 Candidate Roadmap (2026-03-19) — ARCHIVED

Historical PHASE_ADVANCE output from 2026-03-19 archived to `wiki/phases/phase_71_candidate_archive.md`. Phases 71-73 long completed (see Phase Summary table for current state). Current candidate roadmap tracked via Mythos audit + operator decisions, not a hardcoded list.
## Key Gotchas (Windows / HID)

- `hidapi` library: `pip install hidapi` (NOT `hid`)
- HID Cross button: bit5 of `buttons_0` raw HID byte; `cross = (buttons_0 >> 5) & 1`
- L2C sign bug: use `abs(max_causal_corr) < threshold` — anti-correlation is physical coupling
- Windows SQLite tests: use `tempfile.mkdtemp()` NOT `TemporaryDirectory` (WAL PermissionError)
- Windows print encoding: ASCII (PASS: / ->) NOT Unicode (✓ / →) in test print() calls
- Web3/eth_account stub: mock `web3`, `web3.exceptions`, `eth_account` before import
- EWCWorldModel INPUT_DIM=30 (tests need 30-dim input, not 10)
- ZK circuits: `pragma circom 2.0.0;` — requires circom2 Rust binary; circom.exe v2.2.3 in `contracts/`
- IoTeX: chain ID 4689 mainnet, 4690 testnet; P256 precompile at 0x0100
- hardhat.config.js: viaIR=true (stack-too-deep fix for PoACVerifier)
- conftest.py: autouse event loop fixture prevents Python 3.13 asyncio teardown crash
- Batch analysis: always use max_frames=0 — default 30k limit misses presses in 180s sessions
- Phase 199 prototype mode: set ALL_PAIRS_GATE_ENABLED=false in bridge/.env to bypass per-pair P0 gate; ratio=0.728 already passes separation_ok (>= min_separation_ratio=0.70 Phase 166 default)
- Phase 200: IOSWARM_ENABLED=true in bridge/.env; emulator mode (5-node seed=109/110); VAPISwarmOperatorGate.sol LIVE 0x969c0F1E. Test T199-8 isolated via os.environ.pop to prevent bridge/.env contamination.
- tremor_resting probe: 30s still-hold session; valid STRUCTURED_PROBE_TYPE (Phase 199); primary discriminator tremor_peak_hz (P1 ~9.37Hz, P2 ~1.71Hz, P3 ~2.85Hz)
- SDK naming: Phase 199 ProbeGateConfigResult/VAPIProbeGateConfig + TremorRestingProbeResult/VAPITremorRestingProbe — distinct from all prior Phase 182/183 names
- Batch analysis: always use max_frames=0 — default 30k limit misses presses in 180s sessions
- Phase 234: InsightSynthesizer Mode 6 no longer blocks event loop — _synthesize_living_calibration() is now a thin async wrapper calling asyncio.to_thread(_synthesize_living_calibration_sync); HTTP API responds in <1s during startup
- grind_semantics (Phase 234.5+235-B+235-GAD): consecutive_clean = leading non-divergent + PCC-attested + gameplay-confirmed streak from most recent ruling_validation_log (DESC LIMIT 100); divergence = verdicts_differ AND |llm_conf - fallback_conf| > 0.30; SAME VERDICT never diverges; pcc_state=NOMINAL AND pcc_host_state in (EXCLUSIVE_USB, UNKNOWN) REQUIRED — NULL or DEGRADED or CONTESTED breaks streak immediately (fail-closed); gameplay_context=MENU_DETECTED breaks streak (confirmed menu session); NULL gameplay_context passes through (benefit of doubt for pre-GAD rows or rows where discrimination disabled); ACTIVE_GAMEPLAY counts normally; advisory codes → fallback=FLAG(0.5) → LLM=FLAG → NO DIVERGENCE; clean session → fallback=FLAG(0.05) → LLM=FLAG → NO DIVERGENCE; after enrollment(N>=10 NOMINAL) → fallback=CERTIFY(0.8) → LLM must also return CERTIFY to avoid break; grind target: 100 consecutive_clean at gate_n=100; GIC stamped only on count-eligible sessions (NOMINAL+EXCLUSIVE_USB/UNKNOWN+non-divergent+gameplay_ok+grind_mode=True)
- gameplay_context_classification (Phase 235-GAD): binary gate — ACTIVE_GAMEPLAY = trigger_active_fraction > 0.0 (any L2/R2 press in 20-record evidence window); MENU_DETECTED = trigger_active_fraction == 0.0 (zero trigger presses confirmed); NULL = trigger_active_fraction missing from evidence (pre-GAD row). trigger_onset_velocity > 0.0 is the mathematical zero point, not a tuned threshold — returns exactly 0.0 iff no onset events occurred. Normal competitive play requires ≥1 R2 snap per adjudication window → ACTIVE_GAMEPLAY. Pure menu navigation → MENU_DETECTED. Operator override via POST /operator/override-gameplay-context (api_key + reason≥10 chars); logs to gameplay_classification_disagreements for audit. MIXED category eliminated entirely — binary is sufficient and unambiguous for NCAA CFB 26.
- capture_integrity (Phase 234.7 PCC / 235-PCC-CLARIFY): CaptureHealthMonitor observes HID poll rate via update_sample(n_frames, window_s) once per _session_loop interval; signal_disconnect(reason) forces immediate DISCONNECTED by bypassing rate averaging; host state inferred PURELY from CV of rolling 60-sample window — NO BT pairing state is read (CV<0.20+rate≥900→EXCLUSIVE_USB; CV≥0.40→CONTESTED; 200-350Hz→EXCLUSIVE_BT); grind_ready requires NOMINAL+EXCLUSIVE_USB/UNKNOWN+30s sustained; session_counting_paused=True when grind_mode=True AND NOT grind_ready (soft block, not hard gate); DUAL-CONNECTION (USB to laptop + BT to PS5 for gameplay) is the ONLY valid grind setup and reports EXCLUSIVE_USB when USB polling is stable — BT pairing to PS5 is INVISIBLE to CaptureHealthMonitor; PS Remote Play (streaming video/audio of PS5 to the laptop via PSRemotePlay app) during grind: NOT recommended — Remote Play sends USB audio/HID traffic that may cause poll rate variance (→ CONTESTED); normal BT-to-PS5 gameplay connection does NOT cause CONTESTED
- grind_procedure (Phase 235-GPC / 235-PCC-CLARIFY): PRE-GRIND CHECKLIST (12 steps) — PHYSICAL SETUP: NCAA CFB 26 is PS5-exclusive; the only valid grind configuration is DUAL-CONNECTION (USB-C to laptop AND BT-paired to PS5). CaptureHealthMonitor infers host_state from USB poll-rate statistics ONLY — it is blind to BT pairing state. Dual-connection where USB polling is stable at ~1000 Hz reports EXCLUSIVE_USB regardless of PS5 BT connection. (1) Keep DualSense Edge BT-paired to PS5 — DO NOT unpair. BT pairing is REQUIRED to play NCAA CFB 26. PCC does not care about BT pairing and cannot detect it. (2) USB-C DATA cable from DualSense Edge to laptop — this is what CaptureHealthMonitor reads. Verify the cable carries data (not power-only) by confirming poll_rate_hz ≈ 1000 in GET /bridge/capture-health. (3) Set GRIND_SESSION_ID=grind_phase235_v1 in bridge/.env (CRITICAL: same ID across ALL bridge restarts; different ID = new genesis = chain restart); (4) Set GRIND_MODE=true in bridge/.env; (5) Set GRIND_TARGET=100 in bridge/.env; (6) Confirm ANTHROPIC_API_KEY is set (LLM failure is graceful but WARNING-level — see external_dependencies); (7) Start bridge: python bridge/main.py — confirm startup log shows "GRIND SESSION ID : grind_phase235_v1" and "GRIND MODE : ACTIVE"; (8) Power on PS5 and launch NCAA CFB 26. BT connection auto-establishes. Wait for GET /bridge/capture-health → capture_state=NOMINAL + host_state=EXCLUSIVE_USB + grind_ready=False (pre-warmup); (9) Wait 30s sustained NOMINAL+EXCLUSIVE_USB → grind_ready=True + session_counting_paused=False; (10) Verify GET /bridge/grind-chain-status → chain_intact=True (new chain: chain_length=0, no entries yet); (11) Play NCAA CFB 26. DO NOT press PS button to navigate to PS5 home screen during an active grind session — this may cause transient USB rate instability (CONTESTED). Watch consecutive_clean_toward_target count up toward grind_target=100 via GET /bridge/capture-health; (12) At consecutive_clean=100: run POST /agent/run-tournament-preflight then POST /agent/activate-graduation-stage {agent_id: ruling_enforcement_agent}. WARMUP INDICATORS: session_counting_paused=True means grind is paused (waiting for EXCLUSIVE_USB+NOMINAL+30s); grind_ready=True is the green light; first GIC entry appears after the first count-eligible session (chain_length=1). CONTESTED RECOVERY: if host_state=CONTESTED fires mid-session (poll rate became unstable), the current session will not count; finish current play safely, wait for EXCLUSIVE_USB to return; 30s warmup window restarts. Sessions already counted are NOT retroactively removed. CHAIN-BREAK RECOVERY: if startup check detects chain_intact=False, bridge sets _gic_chain_broken=True blocking new GIC stamps; investigate with GET /bridge/grind-chain-status; if DB is clean (external tamper ruled out), call POST /operator/gic-reset with mandatory reason field (≥10 chars), then restart bridge. See docs/phase_235_pcc_dual_connection_clarification.md for full PCC dual-connection audit.
- pcc_invariants (Phase 234.8): INV-PCC-001: CaptureHealthMonitor.update_sample() is the ONLY authorized path for updating poll_rate_hz; signal_disconnect() is the ONLY authorized path for forcing DISCONNECTED state; _recompute() MUST check _disconnect_reason before rate averaging — overriding this allows silent capture degradation to be masked as NOMINAL during grind sessions
- prior_art_anchor (Phase 234.8): VAPI is the first input-attestation protocol to treat controller host arbitration as a first-class, cryptographically-anchored session integrity signal. Host arbitration state (EXCLUSIVE_USB/CONTESTED) is derived from HID poll-rate coefficient of variation and surfaced via capture_health_log + GET /bridge/capture-health, enabling grind-mode fail-closed enforcement when controller ownership is contested between gaming PC and PS5.
- gic_invariants (Phase 235-A/GPC): INV-GIC-001: GIC formula v1 is FROZEN — byte order prev_gic(32)||commitment_hash(32)||verdict_code(1)||host_state_code(1)||ts_ns_be(8) = 74B → SHA-256 → 32B. VERDICT_CODES = {CLEAR:0x00,CERTIFY:0x01,FLAG:0x10,HOLD:0x11,BLOCK:0x20}. PCC_HOST_CODES = {EXCLUSIVE_USB:0x01,UNKNOWN:0x02,EXCLUSIVE_BT:0x10,CONTESTED:0x20,DEGRADED:0x30,DISCONNECTED:0xFF}. Genesis tag = b"VAPI-GIC-GENESIS-v1". Only fallback_verdict (deterministic _rule_fallback() output) is hashed — llm_verdict (LLM API, non-deterministic) is NEVER an input. Any change to byte order, code tables, or hash algorithm requires GIC v2 and new genesis tag. grind_chain.py is a standalone pure-Python module with no bridge imports — suitable for independent verification. GIC_100 = final hash after 100 consecutive_clean sessions = Phase 236 Zenodo deposit headline artifact. INV-GIC-002: gic_ts_ns is strictly monotonically increasing — implemented via time.time_ns() (OS-native integer nanoseconds; no float precision loss) + explicit guard in session_adjudicator_validator: _prev_ts = store.get_prev_gic_ts_ns(); if _ts_ns <= _prev_ts: _ts_ns = _prev_ts + 1. This protects against backward NTP corrections creating duplicate or regressing timestamps in the audit chain. Do NOT use int(time.time() * 1e9) (float precision loses ~300 ns precision) or time.monotonic_ns() (resets on process restart — breaks cross-session monotonicity during multi-day grind). INV-GIC-003: chain-break detection runs at startup (main.py): if get_grind_chain_status()["chain_length"] > 0 AND NOT chain_intact → app._gic_chain_broken = True → consecutive_clean gate refuses to advance until cleared. Recovery: (a) use POST /operator/gic-reset (requires valid operator api_key query param + reason≥10 chars; logs to agent_events + clears flag; bridge restart still required for clean startup check); (b) operator then restarts bridge to verify chain_intact=True before grind resumes.
- external_dependencies (Phase 235-GPC): SessionAdjudicator uses claude-opus-4-6 via Anthropic API (ANTHROPIC_API_KEY env). LLM API FAILURE MODES — all 6 modes fall back deterministically via _rule_fallback() and GIC chain integrity is NEVER affected: (a) missing ANTHROPIC_API_KEY → AuthenticationError caught → fallback; (b) key valid but credits depleted → RateLimitError or PermissionDeniedError caught → fallback; (c) network unreachable → ConnectionError caught → fallback; (d) model unavailable (maintenance) → APIStatusError caught → fallback; (e) response times out → asyncio.TimeoutError caught → fallback; (f) malformed response → any Exception caught → fallback. In all cases: _llm_ruling() catches `except Exception` at its outermost scope and returns _rule_fallback(evidence) as a 3-tuple (verdict, confidence, reasoning). The stored llm_verdict becomes identical to fallback_verdict → divergence=0 → consecutive_clean advances normally. GIC stamps fallback_verdict (not llm_verdict), so Anthropic API availability has ZERO effect on chain integrity. ANTHROPIC_API_KEY missing: logs WARNING once per adjudication attempt. Recommended: set ANTHROPIC_API_KEY in bridge/.env for full LLM operation, but grind can proceed without it — fallback verdicts are equally valid for GIC purposes.
- event_loop_invariants (Phase 235-EVENTLOOP): Every `async def` function that does NOT contain an internal `await` expression MUST include an explicit `await asyncio.sleep(0)` yield point before or after its synchronous body — otherwise it runs as a blocking coroutine and stalls the event loop for the full duration of its CPU work. Long-running synchronous work (SQLite scans >5ms, numpy computation, file I/O) MUST be moved to `asyncio.to_thread()` or `loop.run_in_executor(None, fn)` — NOT just wrapped in `async def`. Background tasks that run at startup MUST include an initial `await asyncio.sleep(N)` delay (N ≥ 30s) before their first heavy operation, so Uvicorn can complete its binding and accept connections before the task's sync blocks begin. Sequential sync task loops (like curator's TASK_SEQUENCE) MUST add `await asyncio.sleep(0)` after each task iteration — not just at the outer `while True` boundary. Index coverage on high-cardinality tables is mandatory before production: the `records` table (192k+ rows) must have indexes on every query pattern used by startup tasks; missing index + cold-start WAL = 400-1500ms blocking query on the event loop thread = HTTP timeout. Violation consequence: any 10-second HTTP timeout on a zero-DB endpoint (`/health`) indicates a SQLite write-lock contention where the event loop thread is blocked waiting for a background thread to release the WAL write lock; `timeout=10` is the signature.
- dashboard_access (Phase 235-FINAL): Start bridge first: `python -m bridge.vapi_bridge.main` (from project root `C:\Users\Contr\vapi-pebble-prototype`). Start dashboard: `cd frontend && npm run dev`. Dashboard URL: http://localhost:5173 (Vite default). Navigate to Gamer view (leftmost tab) to see the GRIND INTEGRITY CHAIN panel at the top of the stats panel — shows progress bar (consecutive_clean / grind_target), PCC state, HOST state (green=EXCLUSIVE_USB, red=CONTESTED, amber=DEGRADED), READY flag, CHAIN link count, GAMEPLAY context (green=ACTIVE_GAMEPLAY, red=MENU_DETECTED), and session ID. Polling intervals: capture-health 3s (useCaptureHealth hook), grind-chain-status 5s (useGrindChain hook). When bridge is offline, dashboard auto-falls back to mock data (sessionStorage key __vapiMockActive=true) — mock shows grind_phase235_v1 session with drifting values. Prerequisites: Node.js + `npm install` (already done); no additional env vars needed for frontend; OPERATOR_API_KEY must be set in bridge/.env for authenticated bridge endpoints (x-api-key header). Full procedure: docs/phase_235_grind_start_procedure.md.
