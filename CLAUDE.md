# VAPI — Claude Code Project Context

## What This Project Is

VAPI (Verified Autonomous Physical Intelligence) is a cryptographic anti-cheat protocol
for competitive gaming. It produces a 228-byte Proof of Autonomous Cognition (PoAC) record
per cognition cycle, anchored on IoTeX L1. The certified device is a DualShock Edge
(Sony CFI-ZCP1). The primary game corpus is NCAA College Football 26.

## Repository

`C:\Users\Contr\vapi-pebble-prototype`

~270 files, ~3,121 automated tests total (~3,070 CI excluding 37 hardware, 14 E2E).
Bridge: 2216 passing. Contract: 482. SDK: 426. Hardware: 37. E2E: 14.
NOTE: 16 pre-existing SDK version-check failures. Bridge empirical pass count ~2128 (10 env-config sensitive tests may see IOSWARM_ENABLED=true via bridge/.env; ioSwarm activated Phase 200).
NOTE: T199-8 (all_pairs_gate_enabled default=True) fixed to use os.environ.pop isolation from bridge/.env.
43 contracts ALL LIVE on testnet (0 deferred; 4 previously-deferred contracts deployed 2026-04-10). AdjudicationRegistry: 0x44CF981f46a52ADE56476Ce894255954a7776fb4 (Phase 111, LIVE 2026-03-27). VAPIDualPrimitiveGate: 0xd7b1465Aad8F815C67b24681c9c022CED24FB876 (Phase 113, LIVE 2026-03-27). VAPISwarmOperatorGate: 0x969c0F1EFb28504a95Acf14331A59FBCb2944F98 (Phase 130, LIVE 2026-04-10). CeremonyAuditRegistry: 0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2 (Phase 179, LIVE 2026-04-10). SeparationRatioRegistry: 0xB39CeE732cf91c93539Bd064D9426642a095a026 (Phase 153, LIVE 2026-04-10). VHPReenrollmentBadge: 0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C (Phase 187, LIVE 2026-04-10). See `contracts/deployed-addresses.json`.
Active wallet (bridge + deployer): `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` (~10.4 IOTX as of 2026-04-11; funded after Phase 198 completion; all 4 deferred contracts live)
Previous bridge wallet (no longer accessible): `0xfCF4681e57C8de9650c3Eb4dA8e26dC9441A5EF1` (deployed original 14 contracts — addresses unchanged, still valid on-chain)
Chain ID: 4690 (IoTeX Testnet)
Current phase: Phase 203 — COMPLETE (AgentContextRegistry — agent_context_log table; UNIQUE(agent_id, prompt_sha256); upsert_agent_context_hash()/get_agent_context_status()/get_all_agent_context_status(); main.py Phase 203 startup block: SHA-256(system_prompt) for 3 LLM agents registered at bridge start; GET /agent/context-integrity-status; CONTEXT_HASH_MISMATCH 4th INVERSION rule in FleetSignalCoherenceAgent; AgentContextIntegrityResult@dataclass(slots=True)+VAPIAgentContextIntegrity SDK; agent_context_on_chain_enabled=False default; 8 bridge+4 SDK; Bridge 2208→2216 +8; SDK 422→426 +4; Hardhat 482 unchanged; closes WIF-036 W1)
Phase 202 — COMPLETE (TremorRestingConvergenceOracle — tremor_convergence_log table; insert_tremor_convergence_log()/get_tremor_convergence_status()/get_tremor_convergence_history(); velocity=(ratio_curr-ratio_prev)/N_delta; convergence_stable=True when velocity>=0 for 2 consecutive; GET /agent/tremor-convergence-status; RATIO_VELOCITY_NEGATIVE 6th ORPHAN rule in FleetSignalCoherenceAgent; TremorConvergenceResult@dataclass(slots=True)+VAPITremorConvergence SDK; tremor_convergence_enabled=False default; 8 bridge+4 SDK; Bridge 2200→2208 +8; SDK 418→422 +4; Hardhat 482 unchanged; closes WIF-037 W1)
Phase 201 — COMPLETE (Agent Context Modernization — updated 3 LLM agent system prompts to Phase 200 state: bridge_agent._SYSTEM_PROMPT (Phase 30→200), session_adjudicator._SYSTEM_PROMPT (Phase 65→200), calibration_intelligence_agent._CALIB_SYSTEM_PROMPT (Phase 148→200); VAPI_AGENTS.md 22→36 agents; 8 bridge prompt-invariant tests; Bridge 2192→2200 +8; SDK 418 unchanged; Hardhat 482 unchanged)
Phase 200 — COMPLETE (ioSwarm Activation + Frontend Alignment Phase 199 — all_pairs_gate_enabled:bool=True config (False=prototype mode, bypasses per-pair P0 gate); tremor_resting added to STRUCTURED_PROBE_TYPES; GET /agent/probe-gate-config-status + GET /agent/tremor-resting-probe-status endpoints; ProbeGateConfigResult+VAPIProbeGateConfig + TremorRestingProbeResult+VAPITremorRestingProbe SDK; openapi ProbeGateConfigStatus+TremorRestingProbeStatus schemas; 8 bridge + 4 SDK tests; Bridge 2184→2192 +8; SDK 414→418 +4; Hardhat 482 unchanged; Tools 149 unchanged)
Phase 198 — COMPLETE (Biometric TTL Decay Scaling — effective_ttl = base_ttl × (mean_decay_factor / 0.50), clamped [base×0.25, base×4.0]; biometric_ttl_decay_scaling_enabled=False default; get_effective_biometric_ttl(base_ttl_days, scaling_enabled) store method; GET /agent/biometric-ttl-scaling-status endpoint; BiometricTTLScalingResult @dataclass(slots=True) 6 slots + VAPIBiometricTTLScaling SDK; openapi BiometricTTLScalingStatus schema; 8 bridge + 4 SDK tests; Bridge 2176→2184 +8; SDK 410→414 +4; Hardhat 482 unchanged; Tools 149 unchanged)
Phase 197 — COMPLETE (Per-Pair Separation P0 Gate — all_pairs_p0_ok 10th P0 condition in tournament preflight; reads all_pairs_above_1 from separation_defensibility_log; fail-closed default=False; biometric_ttl_ok AND all_pairs_p0_ok both required for overall_pass; commit-activation extended: per_pair_separation_below_1.0 blocker; TournamentPreflightResult +all_pairs_p0_ok slot; 8 bridge + 4 SDK tests; Bridge 2168→2176 +8; SDK 406→410 +4; Hardhat 482 unchanged)
Phase 196 — COMPLETE (Tournament Preflight v2 WIF-035 W1 closure — biometric_ttl_ok 9th P0 condition; (not ttl_expired) AND len(renewal_chain)>0; idempotent ALTER TABLE tournament_preflight_log ADD COLUMN biometric_ttl_ok; insert_tournament_preflight_log() + get_tournament_preflight_status() updated; TournamentPreflightResult +biometric_ttl_ok slot(default=True); commit-activation extended: biometric_ttl_expired_or_no_renewal_chain blocker; 8 bridge + 4 SDK tests; Bridge 2160→2168 +8; SDK 402→406 +4; Hardhat 482 unchanged)
Phase 195 — COMPLETE (Protocol Metabolism Index PMI — 9th component weight=0.03 in ProtocolMaturityScoringAgent; PMI=max(0.0, 1.0-mean_orphan_resolution_hours/48.0); _WEIGHTS v3: sep 0.18, fresh 0.11, pmi 0.03; get_orphan_resolution_stats(domain) store; GET /agent/protocol-metabolism-index; Tool #149 get_protocol_metabolism_index; PMIResult @dataclass(slots=True)+VAPIProtocolMetabolism SDK; ProtocolMaturityScoringResult +pmi_component slot; openapi ProtocolMetabolismIndexStatus schema+path; 8 bridge + 4 SDK tests; Bridge 2152→2160 +8; SDK 398→402 +4; Hardhat 482 unchanged; Tools 148→149)
Phase 194 — COMPLETE (CoherenceFingerprintRegistry — contradiction fingerprint tracking; coherence_fingerprint_log table (rule_name UNIQUE, occurrence_count, persistent=1 when count≥N_PROMOTE_THRESHOLD=3); idempotent ALTER TABLE fleet_coherence_log ADD COLUMN on_chain_confirmed; upsert_coherence_fingerprint()/get_coherence_fingerprint_status()/get_persistent_contradictions() store methods; ProtocolMaturityScoringAgent._threat_forecast_accuracy_component() Phase 194 addition: score *= (1 - min(1.0, persistent_count × 0.10)) — direct fleet-coherence→maturity feedback loop; GET /agent/coherence-fingerprint-status endpoint; Tool #148 get_coherence_fingerprint_summary; CoherenceFingerprintResult @dataclass(slots=True) + VAPICoherenceFingerprint SDK; openapi CoherenceFingerprintStatus schema; 10 bridge + 4 SDK tests; Bridge 2142→2152 +10; SDK 394→398 +4; Hardhat 482 unchanged; Tools 147→148)
Phase 193 — COMPLETE (FleetSignalCoherenceAgent — agent #36; fleet-level signal coherence observer; 3 failure modes: CONTRADICTION (7 rules), ORPHAN (5 rules), INVERSION (3 rules — Provenance DAG walk); coherence_id="coh_"+SHA-256[:16]; auto-promotes persistent contradictions (N_PROMOTE_THRESHOLD=3) to VAPI_WHAT_IF.md; fleet_coherence_enabled=True DEFAULT (always-on, unlike most agents); RENEWAL_WITHOUT_ATTESTATION=CRITICAL (highest severity — Phase 185/186 attestation chain bypass); BP-007 _scrub_evidence() removes raw biometric fields from evidence_json; fleet_coherence_log table in store.py; cmd_coherence_status() + "coherence_status" in vapi_wiki_engine.py CMDS; vapi_fleet_coherence MCP tool in knowledge_server.py; score_phase_193_readiness() gate(≥0.80) in vapi_autoresearch.py; Tools #145–#147 (get_fleet_coherence_summary/get_fleet_coherence_entries/resolve_coherence_entry); 14 bridge + 4 SDK tests; Bridge 2128→2142 +14; SDK 390→394 +4; Hardhat 482 unchanged; agents 35→36)
Phase 192 — COMPLETE (CorpusDataCuratorAgent — agent #35; 7-task data coherence layer: Provenance DAG (20-hop walk), Corpus Entropy Monitor (threshold 1.5 CLUSTERING_WARNING), Proof-of-Erasure Certificate (sha256: SHA-256(device_id+erased_tables+ratio+ts_ns)), Federated Corpus Quality (BP-007 compliant; privacy_constraint gate), Cross-Feature Temporal Correlation (Frobenius per-pair separability), Data Readiness Certificate (8-dim gate; NOT_READY/READY/PARTIAL), Session Contribution Weights (TBD λ=ln(2)/90 FROZEN BP-001); --weighted-centroid+--correlation-matrix flags in analyze_interperson_separation.py; 3 MCP tools in knowledge_server.py; provenance_dag/corpus_entropy_log/erasure_certificate_log/federation_corpus_quality_log/feature_correlation_log/data_readiness_certificate_log/session_contribution_weight_log tables in store.py; "curator"+"corpus_quality" bus channels in vapi_managed_agents.py; Tools #136–#144 (9 tools); 14 bridge + 7 SDK tests; Bridge 2114→2128 +14; SDK 383→390 +7; Hardhat 482 unchanged; agents 34→35)
Phase 191 — COMPLETE (Threat Succession Protocol — TSP; WIF-034 FORMAL; ProtocolMaturityScoringAgent 8-component v2; threat_forecast_accuracy_component(weight=0.07 from PIR harness_score)+biometric_stationarity_component(weight=0.04 from BSO confidence); _WEIGHTS v2: sep 0.25→0.20, fresh 0.15→0.12, cal 0.15→0.12, sum=1.00; neutral 0.5 when no data; tsp_enabled:bool=True config; idempotent ALTER TABLE migration; get_threat_forecast_accuracy() store; GET /agent/protocol-maturity-score +2 keys; ProtocolMaturityScoringResult +2 slots(default=0.0); openapi ProtocolMaturityScoreStatus; 8 bridge + 4 SDK tests; Bridge 2106→2114 +8; SDK 379→383 +4; Hardhat 482 unchanged; Tools 137→138)
Phase 190 — COMPLETE (LivePresenceSignalingAgent — agent #34; bidirectional presence channel; 8 bus subscriptions; 8 signal types LED+haptic vocabulary; live_presence_signaling_enabled=False default; 8 bridge+4 SDK; Bridge 2098→2106; SDK 375→379; agents 33→34; Tools 137→138)
Phase 189 — COMPLETE (ProtocolIntelligenceRecordAgent — agent #33; PIR chain hash sequence; pir_chain_enabled=False default; 8 bridge+4 SDK; Bridge 2090→2098; SDK 371→375)
Phase 188 — COMPLETE (BiometricStationarityOracleAgent — agent #32; drift cause classifier; biometric_stationarity_enabled=False default; 8 bridge+4 SDK; Bridge 2082→2090; SDK 367→371)
Phase 187 — COMPLETE (AttestationOpSecAdvisorAgent agent #31 + VHPReenrollmentBadge agent contract LIVE; mempool_opsec_enabled=False default; reenrollment_badge_enabled=False default; VHPReenrollmentBadge.sol 0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C; 16 bridge+8 SDK; Bridge 2066→2082; SDK 359→367)
Phase 186 — COMPLETE (AttestationBoundRenewalAgent — agent #30; validates attestation at renewal; attestation_bound_renewal_enabled=False default; 8 bridge+4 SDK; Bridge 2058→2066; SDK 355→359)
Phase 185 — COMPLETE (ReEnrollmentAttestationAgent — agent #29; HMAC attestation tokens on persona break; reauth_attestation_enabled=True; 8 bridge+4 SDK; Bridge 2050→2058; SDK 351→355)
Phase 184 — COMPLETE (PostCode Sweep — Skill 14 guardrail; test_t184_3 schema_versions 182+183; PersonaBreakResult+MaturityElevationResult @dataclass(slots=True); 10 bridge+4 SDK; Bridge 2040→2050; SDK 347→351)
Phase 183 — COMPLETE (MaturityElevationGateAgent — agent #28; maturity elevation plan; maturity_elevation_enabled=True; 8 bridge+4 SDK; Bridge 2032→2040; SDK 343→347)
Phase 182 — COMPLETE (PersonaBreakDetectorAgent — agent #27; LOO centroid drift; persona_break_detection_enabled=True; 8 bridge+4 SDK; Bridge 2022→2032; SDK 337→343; agents 26→27)
Phase 181 — COMPLETE (Renewal Provenance — corpus_delta_detected on BiometricRenewalResult; ceremony_audit_registry_address on VAPICeremonyAuditGate; SDK slot+init fixes; 4 bridge+4 SDK tests; Bridge 2022 unchanged; SDK 337 unchanged)
<!-- Phase 131-180 verbose blocks archived to CLAUDE_HISTORY.md on 2026-04-11 -->
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
- **CURRENT STATE (2026-04-11, UPDATED): N=35 — RATIO DECLINED, touchpad_corners protocol ceiling hit**
  - Separation ratio: **0.728** (diagonal+LOO, N=35, P1=12/P2=12/P3=11; 2026-04-11 analysis)
  - **TOURNAMENT BLOCKER**: ratio DECLINED from 0.998→0.728 as N grew; more sessions of same type make it WORSE
  - LOO classification: **54.3% (19/35)** — 54% is slightly better but 16/35 misclassified
  - **Root cause**: P3 intra-player variance=1.154 (mean), range=[0.164,2.024] — P3 is non-stationary; intra-mean=0.802 > inter-mean=0.584 → ratio < 1.0 structurally
  - **P2/P3 biometric proximity**: touchpad_spatial_entropy P2=1.385 vs P3=1.379 (gap=0.006); touch_position_variance P2=0.028 vs P3=0.030 — nearly identical; corner-tap protocol actively suppresses discriminative signal
  - **Key feature**: tremor_peak_hz P1=9.37Hz vs P2=1.71Hz vs P3=2.85Hz — NOTE: these were theoretical projections in WIF corpus (Cycle 30); ACTUAL measured: tremor_peak_hz=0.0 for ALL tremor_seed sessions because BiometricFeatureExtractor uses right_stick_x velocity FFT (neutral=128 during still-hold). Phase 205 candidate: AccelTremorFFT fallback.
  - **DIAGNOSIS**: touchpad_corners protocol has hit discriminative ceiling for P2/P3; adding more sessions of same type will not cross 1.0
  - **tremor_seed corpus (2026-04-12)**: P1=10/P2=8/P3=6 sessions; separation ratio=0.748 (diagonal+LOO, N=24); LOO accuracy=45.8% (11/24); only micro_tremor_accel_variance active; tremor_peak_hz=0 (right_stick_x=128 neutral); 4/13 features active vs 10/13 gameplay
  - **PREVIOUS STATE (superseded)**: ratio=0.998 (N=29, P1=8/P2=11/P3=10) — trend reversal was false; ratio fell as P3 sessions added
  - Inter-player distances: P1vP2=0.749, P1vP3=1.133, P2vP3=0.401 — P2/P3 still too close (0.401)
  - Intra-player: P1=0.622, P2=0.502, P3=1.165 — P3 very high variance
  - Touchpad corpus: P1=8, P2=11, P3=10 (P1 needs 2 more sessions to meet defensibility gate ≥10/player — Phase 150)
  - **Why trend reversed**: 4 new P2 sessions + 3 new P3 sessions today stabilized centroids
  - **Path to >1.0**: Phase 205 — AccelTremorFFT: modify BiometricFeatureExtractor to compute tremor_peak_hz from accel data when right_stick_x variance < threshold (still-hold sessions). Then tremor_resting sessions will show per-player tremor peak frequencies at their neurological origin. PC accel-based tremor peaks (measured 2026-04-12): P1≈3.1Hz/P2≈4.3Hz/P3≈3.7Hz — overlapping but measurable; more sessions needed post-AccelTremorFFT fix.
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
| 17 | L4 feature space 7→11; L2B/L2C oracles added |
| 38 | Mode 6 living calibration active (α=0.95, ±15%/cycle, 6h) |
| 41 | Full covariance L4; ZK inference code binding |
| 43 | L6 human response baseline; bridge 865→877 |
| 45 | accel_phase_coherence NEGATIVE RESULT — gravity dominates; reverted; documented |
| 46 | accel_magnitude_spectral_entropy shipped; thresholds 7.019→6.726 / 5.369→5.097; bridge 880 |
| 47 | L2C phantom weight closed — PITL layer table live INACTIVE indicator; stale threshold labels fixed |
| 48 | Professional adversarial data — 3 white-box attack classes (G/H/I), 15 sessions, 4 bridge tests; bridge 884 |
| 49 | Tremor FFT window 513→1025 positions (512→1024 velocity samples); 1.95→0.977 Hz/bin; 4 bins across 8–12 Hz band; batch validator 7→9 features; bridge 888 |
| 50 | CalibrationIntelligenceAgent peer (6 tools, 30-min event consumer, min() enforcement); BridgeAgent +3 tools +2 behaviors; InsightSynthesizer Mode 6 callback; agent_events/threshold_history/calibration_agent_sessions tables; /calibration/agent + /calibration/stream endpoints; bridge 902 |
| 51 | Game-Aware Profiling — NCAA CFB 26 profile (R2-first L5 priority, 11-entry button map); L6-Passive passive R2 onset tracking (no PS5 conflict); GameProfile registry; get_game_profile BridgeAgent tool #21; CORS/port/batcher/MQTT dev fixes; calibration_agent timeout 180→600s; bridge 915 |
| 52 | Runtime hardening — `_run_ds_with_restart()` (3 auto-restarts); `pitl_meta=None` NameError fix; WS broadcast `except pass` → `log.error`; CORS `:5174` fallback; `hardware_block.controller_connected` init False; CalibIntelAgent failure counter; batcher gas dead-letter + `retry_task.add_done_callback`; ProactiveMonitor decoupled from agent instance; bridge 915 (pure hardening, no new tests) |
| 53 | Serialization hardening — `_safe_val()` NaN/Inf→None wrapper on all WS float fields; `_pending_pitl_meta` reset per loop; `controller_registered` WS event on device connect (frontend triggers fetchSnapshot); chain gas/revert permanent vs transient log discrimination; schema_versions Phase 51; `retry_task.add_done_callback`; 21 new tests; bridge 936 |
| 54 | Runtime hardening — numpy fallback ImportError fix (NCD `build_distance_matrix`); `_task_done_handler` CRITICAL log on all 11 managed tasks; `send_raw_transaction` nonce reset on send failure; WS receive 60s timeout (`ws_records`/`ws_frames`); store migration `log.debug`; fetchSnapshot abort dedup; WS reconnect exponential backoff 5→60s; bridge 941 |
| 55 | ioID Device Identity — `VAPIioIDRegistry.sol`; `ioid_devices` table; DID `did:io:0x<addr>` in PITL metadata + WS; `ensure_ioid_registered()` + `ioid_increment_session()` chain calls; `get_ioid_status` BridgeAgent tool #22; 5 tests; bridge 946 |
| 56 | ZK Tournament Passport — `TournamentPassport.circom` (5 public signals); `PITLTournamentPassport.sol` (mock mode, SESSION_COUNT=5); `tournament_passports` table; `generate_tournament_passport` tool #23; `POST /operator/passport`; 5 tests; bridge 951 |
| 57 | Jitter Variance Feature — `press_timing_jitter_variance` index 11; `_BIO_FEATURE_DIM` 11→12; IBI deques (Cross/L2/R2/Triangle, maxlen=50); `_press_timing_jitter_variance()` static method; behavioral_archaeologist FEATURE_KEYS updated; threshold_calibrator `_extract_jitter_variance()`; 5 tests; bridge 956 |
| 58 | Security Hardening + BridgeAgent Expansion — operator endpoint auth (x-api-key → 401/503); sliding-window rate limiter; operator_audit_log table + log_operator_action/get_operator_audit_log; inference_code column in pitl_session_proofs; BridgeAgent tools #24–27 (analyze_threshold_impact, predict_evasion_cost, get_anomaly_trend, generate_incident_report); 16 tests; bridge 972 |
| 59 | My Controller 3D Digital Twin — physics-driven DualShock Edge CFI-ZCP1 twin page; get_ibi_snapshot() on BiometricFeatureExtractor; ibi_snapshot in pitl_meta + /ws/records; /ws/twin/{device_id} device-scoped fusion WS; GET /controller/twin/{id} + /chain REST; BridgeAgent tool #28 get_controller_twin_data; React Three Fiber + Rapier + Drei frontend (controller-twin.html); IBI Biometric Heartbeat canvas; PoAC DNA Helix; ProofAnchorPanel (ioID DID + ZK passport + separation ratio disclaimer); chain timeline scrubber; 16 tests; bridge 988 |
| 60 | My Controller Enhanced Visualization (Phase 60A) — 4-tab left panel: HEARTBEAT / RADAR / L5 RHYTHM / BIOM MAP; BiometricRadar (12-spoke canvas, mean_json, BIO_NORM[12]); L5RhythmOverlay (per-button CV bars + entropy gauge + quant flag, pitl_l5_cv/pitl_l5_entropy); BiometricScatter (2D tremor×jitter cross-section, bot zone, human 2σ ellipse, N=74); ProofShareQR (QRCode npm, IoTeX explorer deeplink, copy URL); qrcode dep; zero backend changes; bridge 988 unchanged |
| 61 | Session Replay + Feature History Scatter — frame_checkpoints table (deque maxlen=60, 20 Hz); store_frame_checkpoint/get_frame_checkpoint/list_checkpoints_for_device; _replay_ring deque + checkpoint storage in _dispatch; /replay + /checkpoints + /features endpoints; BridgeAgent tool #29 get_session_replay; useReplayMode + useFeatureHistory hooks; BiometricScatter history dots (cyan, DB feature vectors); chain tile ▶ indicator + replay status bar; Track C deployments blocked (wallet 0.43 IOTX); +12 tests; bridge 1000 |
| 62 | Player Enrollment + ZK Inference Code Binding — EnrollmentManager (auto PHGCredential mint after enrollment_min_sessions=10 NOMINAL sessions); device_enrollments table + 4 store methods; config enrollment_min/humanity_min; GET /enrollment/status/{device_id}; BridgeAgent tool #30 get_enrollment_status; PitlSessionProof.circom C3 constraint (inferenceResult === inferenceCodeFromBody); C1 Poseidon 7→8 inputs (adds inferenceCodeFromBody); mock proof commitment includes inference_result; PITLSessionRegistryV2.sol + deploy script; Phase 62 ceremony re-run; artifacts updated; +26 tests; bridge 1026 |
| 63 | L6b Neuromuscular Reflex Layer — first reactive involuntary probe; L6B_PROBE profile (id=8, amplitude 60/255, sub-perceptual); L6bReflexAnalyzer (accel-mag delta, BOT<15ms/HUMAN 80-280ms); l6b_probe_log SQLite table + insert_l6b_probe/get_l6b_baseline; 5 new config fields (l6b_enabled/probe_interval/accel_threshold/human_min_ms/human_max_ms); 4-way humanity formula (baseline/L6/L6b/both); pitl_meta l6b_* fields; BridgeAgent tool #31 get_reflex_baseline; profile 8 excluded from L6 active rotation; L6B_ENABLED=false default; +26 tests; bridge 1056 |
| 64 | SDK Phase 63 Parity — SDK v2.0.0-phase64; 0x31 IMU_PRESS_DECOUPLED + 0x32 STICK_IMU_DECOUPLED in INFERENCE_NAMES; is_advisory updated; VAPIEnrollment (GET /enrollment/status poll); VAPIZKProof (Groth16 C3 validator, PROOF_SIZE=256, N_PUBLIC=5); L2B added as 5th self_verify() layer; openapi.yaml Enrollment tag + EnrollmentStatus schema + YAML alias fix; SDK 28→40; +12 SDK tests |
| 65 | Autonomous Intelligence Layer (AIL) — agent_rulings table (commitment_hash, attestation_hash, verdict/confidence/reasoning, dry_run); insert_agent_ruling/get_agent_rulings/get_agent_ruling_by_id store methods; SessionAdjudicator background agent (5-min poll, claude-opus-4-6, rule fallback); GET /agent/rulings + POST /agent/adjudicate + POST /agent/interpret endpoints; BridgeAgent tools #32 get_autonomous_rulings + #33 request_adjudication; vapi_agent.py (VAPIAgent + AgentRuling dataclass, PoAC-gated commitment formula); BLOCK/CERTIFY require all_layers_active=True; dry_run=True default; Agent tag + 6 OpenAPI schemas; +20 bridge tests + +15 SDK tests; bridge 1076; SDK 55 |
| 66 | Ruling Enforcement Pipeline (REP) — closes Phase 65 enforcement loop; ruling_streaks + on_chain_rulings tables + 6 store methods; RulingEnforcementAgent (5-min poll, streak escalation FLAG×5→HOLD/HOLD×2→BLOCK); RulingRegistry.sol (anti-replay commitmentHash, deviceRulings history, onlyOperator); chain.record_ruling_on_chain() IoTeX testnet; PHGCredential.suspend() on BLOCK (24h default, 7d if warmup_attack_score>0.7); POST /agent/override operator endpoint; BridgeAgent tools #34 get_ruling_streak + #35 override_ruling; 3 config fields (ruling_enforcement_enabled, ruling_streak_block_threshold, ruling_registry_address); +30 bridge tests + +10 Hardhat tests; bridge 1106; Hardhat 364 |
| 67 | MPC Ceremony Hardening — Phase 66 hotfix (store_credential_suspension arg order bug); credential auto-reinstate loop (_check_expired_suspensions); GET /agent/suspension-status endpoint; CeremonyRegistry.sol (on-chain MPC audit trail, IoTeX-block beacon anchor); run-mpc-ceremony.js (3-contributor Hermez ptau ceremony); deploy-ceremony-registry.js; ZKVerifier (local Groth16 pre-verify via Node.js subprocess); chain.record_ceremony_on_chain(); config.ceremony_registry_address; VAPIZKProof.verify_ceremony_integrity() SDK method; openapi.yaml SuspensionStatus schema + path; +20 bridge tests + +8 Hardhat tests + +4 SDK tests; bridge 1126; Hardhat 372; SDK 59 |
| 68 | Production Enforcement + Synergistic Tooling — RulingRegistry `0xa3A2356C90E642a7c510d0C726EC515EA720c621` + CeremonyRegistry `0x739B5fae312834bA2a7e44525bA5f54853C5672f` LIVE; MPC ceremony complete (3 circuits × 3 contributors, IoTeX block #41723255 beacon, verifyCeremony() OK); ZKVerifier wired into submit_pitl_proof() (fail-open); config.pitl_vkey_path + config.agent_dry_run_mode; POST /agent/config operator toggle; BridgeAgent tools #36–40; +32 bridge tests; bridge 1158; 23 contracts ALL LIVE |
| 203 | AgentContextRegistry — agent_context_log (UNIQUE agent_id+prompt_sha256); upsert_agent_context_hash()/get_agent_context_status()/get_all_agent_context_status(); main.py startup: SHA-256 of 3 LLM agent prompts registered at bridge start; GET /agent/context-integrity-status; CONTEXT_HASH_MISMATCH 4th INVERSION rule in FSCA (fires when any agent NOT registered); AgentContextIntegrityResult+VAPIAgentContextIntegrity SDK; agent_context_on_chain_enabled=False; 8 bridge+4 SDK; Bridge 2208→2216; SDK 422→426 |
| 202 | TremorRestingConvergenceOracle — tremor_convergence_log; velocity=(ratio_curr-ratio_prev)/N_delta; convergence_stable when velocity>=0 for 2 consecutive; GET /agent/tremor-convergence-status; RATIO_VELOCITY_NEGATIVE 6th ORPHAN rule in FSCA (blocks VHP MINT_QUORUM=0.80 when declining); TremorConvergenceResult+VAPITremorConvergence SDK; tremor_convergence_enabled=False; 8 bridge+4 SDK; Bridge 2200→2208; SDK 418→422 |
| 199 | Prototype Separation Gate Configurability + Tremor Resting Probe — all_pairs_gate_enabled:bool=True config (False=prototype mode bypasses per-pair P0 gate); tremor_resting in STRUCTURED_PROBE_TYPES; GET /agent/probe-gate-config-status + /agent/tremor-resting-probe-status; ProbeGateConfigResult+TremorRestingProbeResult SDK; openapi ProbeGateConfigStatus+TremorRestingProbeStatus; 8 bridge+4 SDK; Bridge 2184→2192; SDK 414→418 |
| 198 | Biometric TTL Decay Scaling — effective_ttl=base_ttl×(mean_decay_factor/0.50) clamped [0.25×,4.0×]; biometric_ttl_decay_scaling_enabled=False default; get_effective_biometric_ttl() store; GET /agent/biometric-ttl-scaling-status; BiometricTTLScalingResult+VAPIBiometricTTLScaling SDK; openapi BiometricTTLScalingStatus; 8 bridge+4 SDK; Bridge 2176→2184; SDK 410→414 |
| 197 | Per-Pair Separation P0 Gate — all_pairs_p0_ok 10th P0 condition; reads all_pairs_above_1 from separation_defensibility_log; fail-closed default=False; TournamentPreflightResult +all_pairs_p0_ok; commit-activation per_pair_separation_below_1.0 blocker; 8 bridge+4 SDK; Bridge 2168→2176; SDK 406→410 |
| 196 | Tournament Preflight v2 WIF-035 W1 closure — biometric_ttl_ok 9th P0 condition; (not ttl_expired) AND len(renewal_chain)>0; idempotent ALTER TABLE tournament_preflight_log; TournamentPreflightResult +biometric_ttl_ok; 8 bridge+4 SDK; Bridge 2160→2168; SDK 402→406 |
| 195 | Protocol Metabolism Index (PMI) — 9th maturity component weight=0.03; PMI=max(0.0,1.0-mean_orphan_hours/48.0); _WEIGHTS v3 (sep 0.18, fresh 0.11); Tool #149; PMIResult+VAPIProtocolMetabolism SDK; ProtocolMaturityScoringResult +pmi_component; 8 bridge+4 SDK; Bridge 2152→2160; SDK 398→402; Tools 148→149 |
| 193 | FleetSignalCoherenceAgent (agent #36) — CONTRADICTION(7)+ORPHAN(5)+INVERSION(3) rules; coherence_id=coh_+SHA-256[:16]; auto-WIF at N=3; fleet_coherence_enabled=True DEFAULT; RENEWAL_WITHOUT_ATTESTATION=CRITICAL; Tools #145-#147; 14 bridge+4 SDK; Bridge 2128→2142 +14; SDK 390→394 +4; agents 35→36 |
| 192 | CorpusDataCuratorAgent (agent #35) — 7-task data coherence: Provenance DAG + Corpus Entropy (threshold 1.5) + Proof-of-Erasure (sha256: cert) + Federated Quality (BP-007) + Feature Correlation (Frobenius) + Data Readiness Cert (8-dim) + Session Contribution Weights (TBD λ=ln(2)/90 BP-001); Tools #136-#144; 14 bridge+7 SDK; Bridge 2114→2128 +14; SDK 383→390 +7; agents 34→35 |
| 191 | Threat Succession Protocol (TSP) — WIF-034 FORMAL; ProtocolMaturityScoringAgent 8-component v2; threat_forecast_accuracy+biometric_stationarity components; tsp_enabled=True; 8 bridge+4 SDK; Bridge 2106→2114 +8; SDK 379→383 +4 |
| 190 | LivePresenceSignalingAgent (agent #34) — bidirectional VAPI presence; 8 signal types; live_presence_signaling_enabled=False; 8 bridge+4 SDK; Bridge 2098→2106; SDK 375→379; agents 33→34 |
| 189 | ProtocolIntelligenceRecordAgent (agent #33) — PIR chain hash; pir_chain_enabled=False; 8 bridge+4 SDK; Bridge 2090→2098; SDK 371→375 |
| 188 | BiometricStationarityOracleAgent (agent #32) — drift cause classifier; biometric_stationarity_enabled=False; 8 bridge+4 SDK; Bridge 2082→2090; SDK 367→371 |
| 187 | AttestationOpSec+VHPReenrollmentBadge (agents #31+contract) — VHPReenrollmentBadge.sol LIVE 0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C; both disabled default; 16 bridge+8 SDK; Bridge 2066→2082; SDK 359→367 |
| 186 | AttestationBoundRenewalAgent (agent #30) — validates attestation at renewal; disabled default; 8 bridge+4 SDK; Bridge 2058→2066; SDK 355→359 |
| 185 | ReEnrollmentAttestationAgent (agent #29) — HMAC attestation on persona break; reauth_attestation_enabled=True; 8 bridge+4 SDK; Bridge 2050→2058; SDK 351→355 |
| 184 | PostCode Sweep guardrail — schema_versions 182+183; PersonaBreakResult+MaturityElevationResult slots=True; 10 bridge+4 SDK; Bridge 2040→2050; SDK 347→351 |
| 183 | MaturityElevationGateAgent (agent #28) — elevation plan; maturity_elevation_enabled=True; 8 bridge+4 SDK; Bridge 2032→2040; SDK 343→347 |
| 182 | PersonaBreakDetectorAgent (agent #27) — LOO centroid drift detection; persona_break_detection_enabled=True; 8 bridge+4 SDK; Bridge 2022→2032; SDK 337→343; agents 26→27 |
| 181 | Renewal Provenance — corpus_delta_detected on BiometricRenewalResult; ceremony_audit_registry_address on VAPICeremonyAuditGate; SDK slot fixes; bridge unchanged; SDK unchanged |
| 180 | Biometric Renewal Engine (WIF-029 W2 closure) — consent-bound renewal commitment chain; renewal_enabled=False default; dry_run=True default; biometric_renewal_chain_log (UNIQUE new_commit_hash); chain.renew_separation_ratio_commitment() calls SeparationRatioRegistry.renewCommit(); new_hash=SHA-256(prev_hash+ratio+N+N_consented+ttl+ts_ns); POST /agent/renew-separation-ratio-commitment + GET /agent/renewal-chain-status; Tool #129 trigger_renewal_commitment; BiometricRenewalResult(6 slots)+VAPIBiometricRenewal SDK; 8 bridge + 4 SDK tests; Bridge 2014→2022 +8; SDK 333→337 +4; Hardhat 482 unchanged |
| 179 | ZK Ceremony Audit Gate (WIF-030 W1 closure) — ceremony_audit_enabled=False default; ceremony_audit_log (UNIQUE ceremony_id+participant_address+circuit_name); CeremonyAuditRegistry.sol NEW; GET /agent/ceremony-audit-status + POST /agent/register-ceremony-participant; Tool #128; CeremonyAuditGateResult(6 slots)+VAPICeremonyAuditGate SDK (renamed from CeremonyAuditResult/VAPICeremonyAudit to avoid Phase 85 name collision — fixed Skill 14 sweep); 8 bridge + 4 SDK + 8 Hardhat tests; Bridge 2006→2014 +8; SDK 329→333 +4; Hardhat 474→482 +8; Contracts 39→40 |
| 178 | Biometric Credential TTL Gate (WIF-029 W1 closure) — biometric_credential_ttl_days=90.0; TournamentActivationChainAgent.check_biometric_credential_ttl(); biometric_renewal_log; SeparationRatioRegistry.sol +renewCommit(); GET /agent/biometric-credential-age; Tool #127; BiometricCredentialAgeResult+VAPIBiometricCredentialTTL SDK; 8 bridge + 4 SDK + 6 Hardhat tests; Bridge 1998→2006 +8; SDK 325→329 +4; Hardhat 468→474 +6 |
| 177 | ProtocolMaturityScoringAgent (agent #26) — maturity_score(0.0-1.0) from 6 components; maturity_tier ALPHA/BETA/PRODUCTION_CANDIDATE; Tool #126; ProtocolMaturityScoringResult+VAPIProtocolMaturityScoring SDK; 8 bridge+4 SDK tests; Bridge 1990→1998 +8; SDK 321→325 +4; agents 25→26 |
| 159 | BiometricPrivacyComplianceAgent — agent #22; BP-001 Temporal Biometric Decay TBD(t)=e^(-λt) τ_half=90d; warning when mean_decay_factor<0.25; privacy_compliance_log; biometric_decay_warning bus event; Tool #116; BiometricPrivacyComplianceResult+VAPIBiometricPrivacy SDK; 8 bridge+4 SDK tests; Bridge 1886→1894 +8; SDK 273→277 +4; Hardhat 468 unchanged |
| 158 | Class K HMAC Validation + PoHBG; WIF-014: validate_gsr_hmac() 80-byte HMAC-SHA256 frame auth; WIF-015: compute_pohbg_hash() PoHBG=SHA-256(device_id+pack); gsr_hmac_validation_log+pohbg_log; Tools #114+#115; GSRHMACValidationResult+PoHBGResult SDK; 9 bridge+4 SDK tests; Bridge 1877→1886 +9; SDK 269→273 +4; Hardhat 468 unchanged |
| 157 | FleetConsensusSnapshotAgent — agent #21; WIF-012 dual-condition overall_ready (sessions_needed==0 AND defensible); WIF-016 cov_stability_check() 3 regime labels; WIF-013 PoFC hash=SHA-256(sorted_verdicts+ratio+ts_ns); fleet_consensus_snapshot_log; cov_regime_status in enrollment guidance; 9 bridge + 4 SDK tests; Bridge 1868→1877 +9; SDK 265→269 +4; Hardhat 468 unchanged |
| 156 | EnrollmentAutoGuidanceAgent — agent #20; synthesizes Phase 151 guidance + Phase 154 stagnation + Phase 152 velocity + Phase 155 controller status; 1-hour poll; urgency_level HIGH/MEDIUM/LOW; fires enrollment_complete → TournamentActivationChainAgent when overall_ready; 8 bridge + 4 SDK tests; Bridge 1860→1868 +8; SDK 261→265 +4; Hardhat 462 unchanged |
| 155 | ControllerHardwareIntelligenceAgent — agent #19; Attested tier (DualShock Edge, L0-L6) vs Standard tier (Xbox/Switch, L0-L5); composite key profile_hash:battery_type:transport_type; default thresholds 7.009/5.367; multi_controller_enabled=False; 8 bridge + 4 SDK tests; Bridge 1852→1860 +8; SDK 257→261 +4; Hardhat 462 unchanged |
| 154 | Capture Stagnation Monitor — rolling sessions/day from separation_defensibility_log; stagnant when <0.5/day (7-day window); synergistic input for Phase 156 urgency; 8 bridge + 4 SDK tests; Bridge 1844→1852 +8; SDK 253→257 +4; Hardhat 462 unchanged |
| 153 | SeparationRatioRegistry.sol — on-chain SHA-256 proof-of-calibration commitment; anti-replay UNIQUE commitHash; separation_ratio_on_chain_enabled=False default; 8 bridge + 4 SDK + 6 Hardhat tests; Bridge 1836→1844 +8; SDK 249→253 +4; Hardhat 462→468 +6; deploy deferred (wallet) |
| 152 | Centroid Velocity Monitor — |ratio_curr-ratio_prev|/dt_seconds; _PLATEAU_THRESHOLD_PER_DAY=0.001; stagnant flag feeds Phase 156 urgency; 8 bridge + 4 SDK tests; Bridge 1828→1836 +8; SDK 245→249 +4; Hardhat 462 unchanged |
| 151 | Session-Type Whitelist + Enrollment Capture Guidance (W1-011 closure) — STRUCTURED_PROBE_TYPES frozenset {touchpad_corners, touchpad_freeform, touchpad_swipes}; insert_separation_defensibility_log raises ValueError on invalid session_type ('gameplay' etc.); get_enrollment_capture_guidance() per-probe per-player gap breakdown; GET /agent/enrollment-capture-guidance (5 keys: min_n_per_player/probe_types/guidance/sessions_needed_total/overall_ready); Tool #107 get_enrollment_capture_guidance; CaptureGuidanceResult(6 slots)+VAPIEnrollmentCaptureGuidance SDK; SDK_VERSION 3.0.0-phase151; 10 bridge + 4 SDK tests; Bridge 1818→1828 +10; SDK 241→245 +4; Hardhat 462 unchanged |
| 150 | Session Consistency Scoring + Separation Ratio Defensibility Gate (WIF-010 closure) — separation_defensibility_log table + insert_separation_defensibility_log + get_separation_defensibility_status(session_type=None); config +min_touchpad_sessions_per_player(10); scripts/analyze_interperson_separation.py: +_compute_session_consistency_scores() per-session LOO Mahalanobis outlier detection + _check_n_defensibility() + --session-consistency + --min-n-per-player flags; GET /agent/separation-defensibility-status (6 keys: defensible/ratio/n_per_player/min_n_per_player/all_pairs_above_1/found); Tool #106; SeparationDefensibilityResult(6 slots)+VAPISeparationDefensibility SDK; SDK_VERSION 3.0.0-phase150; schema(150,"separation_defensibility"); Bridge 1808→1818 +10; SDK 237→241 +4; Hardhat 462 unchanged |
| 109B | ioSwarm VHPRenewalAgent Migration — IoSwarmNodeEmulator(n=5,seed=109) + VHPRenewalSwarmTaskSpec + scripts/vapi-vhp-renewal-swarm-agent.json + IoSwarmRenewalCoordinator (fail-open; CERTIFY_RENEW_QUORUM=0.60; W2 consecutive_clean-weighted verdicts) + vhp_renewal_agent.py injection (ioswarm_renewal_enabled=False default) + ioswarm_renewal_log table + GET /agent/ioswarm-renewal-status + Tool #76 + SDK IoSwarmRenewalResult+VAPISwarmRenewal; Bridge 1472→1480 +8; SDK 121→125 +4 |
| 131 | IoSwarm Live Node Foundation (W1 per-node asyncio.wait_for timeout mitigation; W2 staker_address per node for VAPISwarmOperatorGate validation) — ioswarm_node_registry table (node_url/staker_address/active/last_seen_ts/node_version/registered_at/created_at) + insert_ioswarm_node_registry + get_ioswarm_node_registry + update_ioswarm_node_last_seen + schema(131,"ioswarm_node_registry"); config +ioswarm_node_urls + ioswarm_node_timeout_seconds; ioswarm_live_node_client.py (NEW: IoSwarmLiveNodeClient; is_emulator_mode()=True when urls=""; dispatch falls back to emulator zero-behavior-change); live_client=None kwarg added to IoSwarmRenewalCoordinator + IoSwarmAdjudicationCoordinator + IoSwarmVHPMintCoordinator; injected at all 3 instantiation sites (vhp_renewal_agent.py + session_adjudicator.py + operator_api.py); GET /agent/ioswarm-node-registry-status (7 keys: live_nodes/emulator_mode/node_urls/node_timeout_s/registry_count/last_quorum_ts/timestamp); Tool #99 get_ioswarm_node_registry_status; IoSwarmNodeRegistryResult @dataclass(slots=True) 6 slots + VAPIIoSwarmNodeRegistry SDK; VAPISwarmOperatorGate.sol Hardhat tests: Phase130.test.js (+6 T130-1..6) + MockOperatorRegistry130.sol; SDK_VERSION 3.0.0-phase130→3.0.0-phase131; openapi IoSwarmNodeRegistryStatus schema + path; Bridge 1661→1669 +8; SDK 213→217 +4; Hardhat 454→460 +6 |
| 129 | Full Covariance + Separation Ratio Breakthrough Monitor (W1 single-outlier false breakthrough closed — 2-consecutive guard; W2 readiness score oracle input) — SeparationRatioMonitorAgent(agent #15) polls 300s; _prev_crossed+_breakthrough_fired one-shot; fires separation_ratio_breakthrough bus; auto-enables confidence_multiplier_enabled; separation_ratio_breakthrough_log table; GET /agent/separation-ratio-breakthrough (5 keys); Tool #97; SeparationBreakthroughResult(5 slots)+VAPISeparationBreakthrough SDK; analyze_interperson_separation.py +--full-covariance+--diagonal flags; SDK_VERSION 3.0.0-phase128→3.0.0-phase129; schema(129,"separation_breakthrough"); Bridge 1644→1653 +9; SDK 205→209 +4; Hardhat 454 unchanged |
| 128 | Protocol Intelligence Dashboard (W1 score overstates readiness before separation_ratio>1.0 — mitigated: separation_score=min(1.0,pooled_ratio) caps at current 0.474; W2 readiness score as on-chain oracle input for Phase 129 SeparationRatioMonitorAgent) — insert_readiness_score(score,breakdown_json,conditions_met)+get_readiness_scores(limit=10) reuse existing protocol_intelligence_reports table (protocol_health_score/components_json/recommendation/ready_for_live_mode); GET /agent/tournament-readiness-score (9 keys: score/separation_score/l4_score/dual_gate_score/epoch_score/ioswarm_score/dry_run_score/conditions_met/timestamp); 6-signal formula: separation(0.30)+l4_freshness(0.20)+dual_gate(0.15)+epoch_p95(0.15)+ioswarm(0.10)+dry_run(0.10); score>=0.90=READY; Tool #96 get_tournament_readiness_score; TournamentReadinessScore(8 slots)+VAPITournamentReadinessScore SDK (renamed to avoid Phase 108 VAPITournamentReadiness collision); SDK_VERSION 3.0.0-phase127→3.0.0-phase128; schema(128,"intelligence_dashboard"); openapi TournamentReadinessScore schema + GET path; Bridge 1636→1644 +8; SDK 201→205 +4; Hardhat 454 unchanged |
| 127 | Tournament Pre-Launch Validation Suite (W1 commit-activation proceeds without preflight gate — P0 enforcement added: separation_ok+l4_ok checked in POST /agent/commit-activation; overall_pass=False blocks commit; W2 preflight log as audit trail for tournament launch authorization) — tournament_preflight_log table (separation_ok/l4_ok/gate_ok/cert_ok/audit_ok/dual_gate_warned/epoch_window_warned/ioswarm_warned/overall_pass/conditions_json) + insert_tournament_preflight_log + get_tournament_preflight_status + schema(127,"tournament_preflight"); POST /agent/run-tournament-preflight (runs all 8 conditions; returns 10 keys + conditions; persists to log) + GET /agent/tournament-preflight-status; POST /agent/commit-activation extended: reads latest preflight log, blocks on separation_ok=False or l4_ok=False with "preflight_p0_blocked"; Tool #95 run_tournament_preflight; TournamentPreflightResult @dataclass(slots=True) 8 slots (separation_ok/l4_ok/gate_ok/cert_ok/audit_ok/overall_pass/conditions_detail/error) + VAPITournamentPreflight SDK; SDK_VERSION 3.0.0-phase126→3.0.0-phase127; scripts/tournament_preflight.py standalone CLI (exit 0=READY/1=ERROR/2=NOT_READY); openapi TournamentPreflightResult schema + 2 paths; Bridge 1627→1636 +9; SDK 197→201 +4; Hardhat 454 unchanged |
| 126 | Live L4 Gate Per-Battery Routing + BehavioralArchaeologist Fixes (W1 per-battery routing silently falls back to global thresholds when no active track — mitigated: explicit fallback + WARNING log; W2 per-battery threshold routing now LIVE when l4_battery_threshold_enabled=True) — l4_threshold_router.py (NEW: get_thresholds(battery_type,store,cfg)→(float,float,str); source="per_battery"|"global_fallback"; never raises); behavioral_archaeologist.py: _WARMUP_COEFF=20_000 + _BURST_CV_DIVISOR=2.0 named constants (Phase 126 regression guard; closes Phase 57 TODOs); l4_threshold_router_log table + insert_l4_router_log + get_l4_router_log + schema(126,"l4_router"); GET /agent/l4-router-status (7 keys: l4_battery_threshold_enabled/total_lookups/per_battery_lookups/global_fallback_count/last_battery_type/last_source/timestamp); Tool #94 get_l4_router_status; L4RouterStatusResult(6 slots)+VAPIL4RouterStatus SDK; SDK_VERSION 3.0.0-phase125→3.0.0-phase126; openapi L4RouterStatus schema + GET path; Bridge 1619→1627 +8; SDK 193→197 +4; Hardhat 454 unchanged |
| 125 | Calibration Modernization + Per-Battery Threshold Calibrator (W1 per-battery L4 routing silently falls back to stale global thresholds when l4_threshold_tracks table empty or battery_type unmatched; W2 per-battery threshold routing Phase 126 candidate) — scripts/threshold_calibrator.py: +_BATTERY_TYPES + _detect_battery() + _calibrate_battery() + --battery {touchpad,trigger,button,gameplay,resting_grip,all} CLI flag; bridge: l4_battery_calibration_runs table (battery_type/anomaly_threshold/continuity_threshold/n_sessions/calibration_feature_dim/notes/created_at) + insert_l4_battery_calibration_run + get_l4_battery_calibration_runs(limit=10) + schema(125,"per_battery_calibration"); POST /agent/apply-l4-battery-calibration (calls insert_l4_threshold_track + insert_l4_battery_calibration_run; updates cfg.calibration_feature_dim; returns 9-key summary with stale flag; 422 on bounds violation); Tool #93 apply_l4_battery_calibration (before Tool #92); CalibrationApplyResult(5 slots: battery_type/anomaly_threshold/continuity_threshold/n_sessions/error)+VAPICalibrationApply SDK; SDK_VERSION 3.0.0-phase124→3.0.0-phase125; openapi L4BatteryCalibrationApply schema + POST path; staleness clears when calibration_feature_dim==live_feature_dim(13); Bridge 1611→1619 +8; SDK 189→193 +4; Hardhat 454 unchanged |
| 124 | L4 Per-Battery Threshold Track Registry (W1 threshold pollution attacks closed — bounds [5.0–15.0] anomaly / [3.0–10.0] continuity enforced in insert_l4_threshold_track raising ValueError→HTTP 422; W2 per-battery threshold routing Phase 125 candidate) — l4_threshold_tracks table (battery_type/anomaly_threshold/continuity_threshold/n_sessions/calibrated_at/active/created_at) + insert_l4_threshold_track (bounds enforced) + get_l4_threshold_tracks(battery_type=None, active_only=False) + schema(124,"l4_threshold_tracks"); config +l4_battery_threshold_enabled(False); GET /agent/l4-threshold-tracks (6 keys: l4_battery_threshold_enabled/track_count/active_count/battery_types_tracked/tracks/timestamp) + POST /agent/l4-threshold-track (422 on bounds violation); Tool #92 get_l4_threshold_tracks; L4ThresholdTrackResult(5 slots)+VAPIL4ThresholdTracks SDK; SDK_VERSION 3.0.0-phase123→3.0.0-phase124; openapi L4ThresholdTracksStatus schema + paths; Bridge 1603→1611 +8; SDK 185→189 +4; Hardhat 454 unchanged |
| 123 | L4 Calibration Staleness Monitor (W1 stale thresholds applied to 13-feature live space silently degrade L4 precision; W2 per-battery threshold tracks Phase 124 candidate) — l4_calibration_log table + insert_l4_calibration_log + get_l4_calibration_log + schema(123,"l4_calibration_staleness"); config +live_feature_dim(13)/calibration_feature_dim(12)/calibration_n_sessions(74)/calibration_timestamp(0.0); GET /agent/l4-calibration-status (8 keys: current_feature_dim/calibration_feature_dim/stale/anomaly_threshold/continuity_threshold/calibration_n_sessions/calibration_timestamp/timestamp); stale=True when live_feature_dim!=calibration_feature_dim; Tool #91 get_l4_calibration_status; CalibrationStatusResult(6 slots)+VAPICalibrationStatus SDK; SDK_VERSION 3.0.0-phase122→3.0.0-phase123; openapi L4CalibrationStatus schema + path; Bridge 1595→1603 +8; SDK 181→185 +4; Hardhat 454 unchanged |
| 122 | VHP Confidence Score Separation Ratio Multiplier (W1 non-touchpad sessions penalized by touchpad-dominant bt_strat_ratio — mitigated: multiplier disabled default; W2 per-battery multiplier lookup Phase 124 candidate) — confidence_multiplier_log table + insert_confidence_multiplier_log + get_confidence_multiplier_log + schema(122,"confidence_multiplier"); config +confidence_multiplier_enabled(False)/confidence_multiplier_floor(0.0); POST /agent/mint-vhp: confidence_score *= max(floor, min(1.0, bt_strat_ratio)) when enabled; mint response +pre_multiplier_score+confidence_multiplier keys; GET /agent/confidence-score-multiplier-status (7 keys); Tool #90 get_confidence_score_multiplier_status; ConfidenceMultiplierResult(6 slots)+VAPIConfidenceMultiplier SDK; SDK_VERSION 3.0.0-phase121→3.0.0-phase122; openapi ConfidenceMultiplierStatus schema + path; Bridge 1587→1595 +8; SDK 177→181 +4; Hardhat 454 unchanged |
| 121 | Touchpad Spatial Entropy + Separation Ratio Monitoring (W1 ring buffer cross-session contamination mitigated — fresh extractor per analysis session; W2 battery-stratified ratio as VHP confidence_score multiplier Phase 122 candidate) — touchpad_spatial_entropy feature (index 12, 8×8 Shannon entropy heatmap, max log2(64)≈6.0 bits) + _BIO_FEATURE_DIM 12→13 + _touchpad_xy_ring deque(maxlen=1024) + _touchpad_spatial_entropy() static method; analyze_interperson_separation.py +--battery-stratified flag + _detect_battery() + battery-grouped Mahalanobis analysis + resting-grip normalization ratio; separation_ratio_snapshots table + insert_separation_ratio_snapshot + get_separation_ratio_status + schema(121,"separation_ratio"); GET /agent/separation-ratio-status (7 keys: pooled_ratio/battery_stratified_ratio/tournament_blocker/target_ratio/gap_to_target/tournament_ready/timestamp); Tool #89 get_separation_ratio_status; SeparationRatioResult(6 slots)+VAPISeparationStatus SDK; SDK_VERSION 3.0.0-phase120→3.0.0-phase121; openapi SeparationRatioStatus schema + path; L4 threshold recalibration deferred to Phase 122 (new feature initializes to 0.0 for no-touchpad sessions); Bridge 1579→1587 +8; SDK 173→177 +4; Hardhat 454 unchanged |
| 120 | BT Transport Foundation (W1 separate BT threshold track required — USB 7.009/5.367 NOT applicable to 250 Hz BLE sessions; W2 Phase 121 VHC — ESP32-S3 GSR grip as programmable BLE node enabling decentralized tournament presence proof) — bluetooth.py: BT_POLL_HZ=250/BT_FRAME_MS=4.0/BT_WINDOW=1024/BT_HZ_PER_BIN=0.244/TRANSPORT_TYPE_BLE=0x02 + BTFrame dataclass + MockBLETransport(seed=42,n_frames=0) async generator + BLETransport optional bleak dep; bt_transport_log table + insert_bt_transport_log + get_bt_transport_status; GET /agent/bt-transport-status (7 keys); Tool #88 get_bt_transport_status; BTTransportResult(6 slots)+VAPIBTTransport SDK; schema 120; bt_transport_enabled=False default (infrastructure-first); Bridge 1571→1579 +8; SDK 169→173 +4; Hardhat 454 unchanged |
| 119 | Override Lifecycle Management — TTL + Use-Count Auto-Expiry (W1 stale permanent overrides undermine epoch window security; W2 override auto-graduation max_uses=N self-delete) — per_device_epoch_overrides +max_uses/use_count/expires_at (idempotent ALTER TABLE for Phase 118 DBs) + increment_override_use_count (auto-graduation; consumed=True when max_uses reached or expires_at exceeded) + delete_device_epoch_override + get_override_lifecycle_status + GET /agent/epoch-window-override-status (5 keys) + DELETE /agent/epoch-window-override + Tool #86 get_epoch_window_override_status + Tool #87 revoke_device_epoch_override + SDK EpochWindowOverrideStatus(6 slots)+VAPIEpochWindowOverrideManager + schema 119; Bridge 1562→1571 +9; SDK 165→169 +4; Hardhat 454 unchanged |
| 118 | Epoch Window Auto-Tune Advisor + Cold-Start Device Override (W1 cold-start false-positive block closed; W2 per-device override feed Phase 119 candidate) — per_device_epoch_overrides table + get_device_epoch_override() Gate-5 override check + GET /agent/epoch-window-auto-tune (7 keys) + POST /agent/epoch-window-override + Tool #84 get_epoch_window_auto_tune + Tool #85 set_device_epoch_override + SDK EpochWindowAutoTuneResult+VAPIEpochWindowAutoTune + schema 118; Bridge 1553→1562 +9; SDK 161→165 +4; Hardhat 454 unchanged |
| 117 | Per-Device Epoch Freshness Heatmap (W1 misbehaving devices identified before gate activation; W2 per-device windows Phase 118 candidate) — get_epoch_window_analytics_by_device() p50/p95 per device sorted p95 DESC + GET /agent/epoch-window-device-heatmap + Tool #83 + SDK EpochWindowDeviceEntry+VAPIEpochWindowHeatmap + schema 117; Bridge 1545→1553 +8; SDK 157→161 +4; Hardhat 454 unchanged |
| 116 | Epoch-Window Analytics + Recommended Window Advisor (W1 misconfigured window caught; W2 triple-primitive analytics) — get_epoch_window_analytics() p50/p95/recommended_window_seconds + GET /agent/epoch-window-analytics + Tool #82 + SDK EpochWindowAnalyticsResult+VAPIEpochWindowAnalytics + schema 116; Bridge 1537→1545 +8; SDK 153→157 +4; Hardhat 454 unchanged |
| 115 | Epoch-Window Dual-Primitive Temporal Proof (W1 stale PoAd accumulation closed; W2 poad_age_seconds analytics) — +poad_age_seconds+epoch_window_ok to vhp_dual_gate_log + get_poad_ts_ns_for_device() + epoch_window_enabled=False + epoch_window_seconds=86400 config + epoch sub-check in Gate 5; Bridge 1529→1537 +8; SDK 149→153 +4; Hardhat 454 unchanged |
| 114 | VHP Mint Dual-Primitive Gate (W1 VHP without PoAd anchor closed; W2 time-windowed dual-proof Phase 115 candidate) — 5th gate in POST /agent/mint-vhp (dual_primitive_gate_enabled=False default) + vhp_dual_gate_log table + GET /agent/vhp-dual-gate-log (6 keys) + Tool #81 + SDK VHPDualGateResult+VAPIVHPDualGate; reuses Phase 113 config; Bridge 1521→1529 +8; SDK 145→149 +4; Hardhat 454 unchanged |
| 113 | VAPIDualPrimitiveGate (W1 pure view no gas; W2 first dual-proof composability gate in any on-chain gaming protocol) — VAPIDualPrimitiveGate.sol (isDualEligible: isFullyEligible() AND isRecorded(); immutable; zero-address guard) + deploy-phase113.js + chain.is_dual_eligible() view call + dual_eligibility_checks table + GET /agent/dual-primitive-status (8 keys) + POST /agent/check-dual-eligibility + Tool #80 + SDK DualPrimitiveGateResult+VAPIDualPrimitiveGate; 2 config fields; Bridge 1513→1521 +8; SDK 141→145 +4; Hardhat 448→454 +6; deploy deferred (IOTX faucet empty) |
| 112 | PoAd On-Chain Anchoring (W1 Block Timestamp Cross-Check + W2 Dual-Primitive Gate Activated) — PoAdAnchorAgent + chain.record_adjudication() + poad_on_chain_enabled=False default + GET /agent/poad-anchor-status (6 keys) + SDK PoAdAnchorResult+VAPIPoAdAnchor; Bridge 1504→1513 +9; SDK 137→141 +4; Hardhat 446→448 +2 |
| 111 | PoAd Registry (W1 PoAd Timestamp Risk + W2 Dual-Primitive Composability) — AdjudicationRegistry.sol (Ownable, CEI, anti-replay UNIQUE poadHash; block.number stored for W1 mitigation) + deploy-phase111.js + session_adjudicator.py Step D (non-blocking PoAd hash computation + local registry; poad_registry_enabled=False default) + GET /agent/adjudication-registry-status + Tool #79 + SDK PoAdRegistryResult+VAPIPoAdRegistry; poad_registry_log table +2 config fields; Contracts 38→39; Bridge 1496→1504 +8; SDK 133→137 +4; Hardhat 440→446 +6 |
| 110 | IoSwarm VHP Mint Authorization (W1 Fail-CLOSED + W2 Swarm Fingerprint) — IoSwarmVHPMintEmulator(n=5,seed=110) + VAPIVHPMintSwarmTaskSpec + scripts/vapi-vhp-mint-swarm-agent.json + IoSwarmVHPMintCoordinator (MINT_QUORUM=0.80; fail-CLOSED; swarm_fingerprint=SHA-256(node_verdicts_json)) + POST /agent/mint-vhp ioSwarm 4th gate + GET /agent/ioswarm-vhp-mint-status + Tool #78 + SDK IoSwarmVHPMintResult+VAPISwarmVHPMint; Bridge 1488→1496 +8; SDK 129→133 +4 |
| 109C | IoSwarm Dual-Quorum Adjudication (W2 Dual-Quorum Veto) — IoSwarmClassJEmulator(n=5,seed=109) + IoSwarmTriageEmulator(n=5,seed=109) + VAPIAdjudicationSwarmTaskSpec + scripts/vapi-adjudication-swarm-agent.json + IoSwarmAdjudicationCoordinator (DUAL_VETO_SCORE=0.80; fail-open CLEAR; CLASSJ_BLOCK_QUORUM=0.67; TRIAGE_BLOCK_QUORUM=0.67) + session_adjudicator.py injection (Steps A+B+C; ioswarm_adjudication_enabled=False default) + ioswarm_adjudication_log table + GET /agent/ioswarm-adjudication-status + Tool #77 + SDK IoSwarmAdjudicationResult+VAPISwarmAdjudication; Bridge 1480→1488 +8; SDK 125→129 +4 |
| 109A | ioSwarm Bridge Adapter — IoSwarmConsensusAggregator (BLOCK_QUORUM=0.67 W1; tie→HOLD; hold escalation) + VAPISwarmTaskSpec + scripts/vapi-swarm-agent.json + epistemic 4th signal (weights 0.35/0.35/0.15/0.15 when enabled) + GET /agent/ioswarm-status + Tool #75 + SDK IoSwarmConsensusResult+VAPISwarmStatus; ioswarm_enabled=false default; Bridge 1464→1472 +8; SDK 117→121 +4 |

## Remaining Open Gaps (Phase 48, priority order)

1. **L2C phantom weight** — CLOSED (Phase 47)
   `l2c_inactive` flag in pitl_meta + WS stream; log.debug per dead-zone cycle; §7.5.4 footnote;
   test_9 formula validity; HUMANITY tile "4-signal (L2C: dead zone)" in orange; PITL layer table
   L2C row shows "INACTIVE (dead zone)" live when l2c_inactive=true; L4 thresholds updated; bridge 880.

2. **Inter-person separation ratio 0.362** — OPEN/HIGH
   Neither phase coherence nor spectral entropy improved it (both are bot-vs-human).
   True fix requires: post-Phase-17 touchpad recapture (hardware + gameplay) AND
   widening tremor FFT window beyond 120 frames.

3. **Post-Phase-17 touchpad recapture** — OPEN/HIGH (requires controller + gameplay)
   touch_position_variance structurally zero across all calibration sessions.

4. **Professional bot adversarial data** — CLOSED (Phase 48)
   3 white-box attack classes (G: randomized_bot, H: threshold_aware, I: spectral_mimicry), 15 sessions.
   H: 100% L4 detection. G/I: batch 0% (live L4+tremor and L2B respectively). Analysis: `docs/professional-adversarial-analysis.md`.
   Remaining gap: real hardware bot software (aimbot, ML-driven inputs) still untested.

5. **Multi-party ZK ceremony** — PLANNED (no hardware)

6. **PHGCredential multi-sig/timelock governance** — PLANNED (no hardware)

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

## Phase 71 — Candidate Phases (PHASE_ADVANCE Output, 2026-03-19)

After Phase 70 completes, next phases in priority order. User decision required before starting any.

| Rank | Phase | Name | Priority | Blocks |
|------|-------|------|----------|--------|
| P1 (Recommended) | 71 | Deploy Phases 69+70 + Security Audit | P1 | All on-chain functionality |
| P2 | 72 | PHGCredential SafeMultiSig Governance | P1 | Tournament Condition 3 |
| P3 | 73 | CI/CD GitHub Actions + SessionAdjudicator Live Validation | P1 | Production readiness gate |

**Phase 71 detail (deploy + audit):**
- npx hardhat run scripts/deploy-phase69.js --network iotex_testnet (~0.35 IOTX, 6 contracts)
- npx hardhat run scripts/deploy-phase70.js --network iotex_testnet (~0.13 IOTX, 2 contracts)
- Produce docs/security-audit-phase-70.md (VAPIGovernanceTimelock + VAPIProtocolLens + agent wiring + tools #41-45)
- Fix any CRITICAL/HIGH findings inline
- Update deployed-addresses.json + bridge/.env.testnet with 8 new addresses
- ~0 new tests (deploy + audit only, no new code)

**Phase 72 detail (PHGCredential SafeMultiSig):**
- SafeMultiSig.sol: 2-of-3 confirmations for suspend/reinstate on PHGCredential
- chain.py: propose_suspension() → confirm_suspension() → execute_suspension() flow
- Config: safe_signers[3], safe_threshold=2
- +6 Hardhat + 4 bridge tests
- Closes Tournament Condition 3 (governance hardened)

**Phase 73 detail (CI/CD + Live Adjudication):**
- GitHub Actions: bridge-tests.yml + hardhat-tests.yml + sdk-tests.yml + yaml-lint.yml
- Matrix: Python 3.11/3.12/3.13, Node 18/20
- POST /agent/config AGENT_DRY_RUN=false: document 100 validated sessions threshold
- +0 new tests (CI config only)

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
