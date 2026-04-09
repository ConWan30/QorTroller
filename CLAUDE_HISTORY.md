# VAPI CLAUDE History — Archived Phase Records
# 
# Archived from CLAUDE.md to maintain context budget (WIF-027).
# Archived: 2026-04-05 at Phase 164 (182k chars → target ~79k chars).
# Full detail preserved here. Condensed Phase Summary table remains in CLAUDE.md.
# To read a specific phase: grep for "Phase NNN" in this file.
#
# APPEND-ONLY — never delete entries.

## Archived Phase Verbose Blocks (Phase 17-130A)

Phase 130A — COMPLETE (USB Feedback Backoff + P256 Log Dedup + Snapshot Writer + VAPISwarmOperatorGate Bridge+SDK; W1 USB write hang backoff: _FEEDBACK_SKIP_THRESHOLD=3/_FEEDBACK_COOLDOWN_MOD=10 + _consecutive_fb_timeouts in dualshock_integration.py; W2 P256 log spam suppressed: _p256_unavailable=False session flag in batcher.py — WARNING once then DEBUG; Part 3: analyze_interperson_separation.py +--write-snapshot +--db flags → insert_separation_ratio_snapshot so agent #15 has live data; Part 4 WIF-001: swarm_quorum_validation_log table + insert_swarm_quorum_validation + get_swarm_quorum_validation_log + schema(130,"swarm_operator_gate"); config +swarm_operator_gate_address; chain +is_swarm_quorum_valid(); GET /agent/swarm-operator-gate-status (6 keys: swarm_gate_address/gate_configured/total_validations/last_valid/last_node_count/timestamp); Tool #98 get_swarm_operator_gate_status; SwarmOperatorGateResult(5 slots)+VAPISwarmOperatorGate SDK; VAPISwarmOperatorGate.sol code-complete (deploy deferred — wallet ~0.35 IOTX); SDK_VERSION 3.0.0-phase129→3.0.0-phase130; openapi SwarmOperatorGateStatus schema + path; Bridge 1653→1661 +8; SDK 209→213 +4; Hardhat 454 unchanged; Phase 130B deploy after wallet top-up to ~0.40 IOTX)
Phase 129 — COMPLETE (Full Covariance + Separation Ratio Breakthrough Monitor; W1 false breakthrough from single outlier — mitigated: require 2 consecutive snapshots >= 1.0 (_prev_crossed bool + _breakthrough_fired one-shot guard); W2 readiness score as oracle input for breakthrough monitor; SeparationRatioMonitorAgent(agent #15) polls separation_ratio_snapshots every 300s; fires separation_ratio_breakthrough bus event on genuine crossing; auto-enables confidence_multiplier_enabled; separation_ratio_breakthrough_log table + insert_separation_ratio_breakthrough + get_separation_ratio_breakthrough + schema(129,"separation_breakthrough"); GET /agent/separation-ratio-breakthrough (5 keys: breakthrough_detected/breakthrough_ratio/breakthrough_ts/n_players/error); Tool #97 get_separation_ratio_breakthrough; SeparationBreakthroughResult(5 slots)+VAPISeparationBreakthrough SDK; analyze_interperson_separation.py +--full-covariance(default True)+--diagonal(backward-compat) flags; SDK_VERSION 3.0.0-phase128→3.0.0-phase129; openapi SeparationBreakthroughResult schema + GET path; Bridge 1644→1653 +9; SDK 205→209 +4; Hardhat 454 unchanged)
Phase 128 — COMPLETE (Protocol Intelligence Dashboard; tournament_readiness_score 0.0–1.0 from 6 weighted signals: separation(0.30)/l4_freshness(0.20)/dual_gate(0.15)/epoch_p95(0.15)/ioswarm(0.10)/dry_run(0.10); persisted to protocol_intelligence_reports via insert_readiness_score()+get_readiness_scores(); GET /agent/tournament-readiness-score (9 keys: score/separation_score/l4_score/dual_gate_score/epoch_score/ioswarm_score/dry_run_score/conditions_met/timestamp); Tool #96 get_tournament_readiness_score; TournamentReadinessScore(8 slots)+VAPITournamentReadinessScore SDK; SDK_VERSION 3.0.0-phase127→3.0.0-phase128; schema(128,"intelligence_dashboard"); VAPITournamentReadinessScore renamed to avoid Phase 108 VAPITournamentReadiness collision; Bridge 1636→1644 +8; SDK 201→205 +4; Hardhat 454 unchanged)
Phase 127 — COMPLETE (Tournament Pre-Launch Validation Suite; tournament_preflight_log table; POST /agent/run-tournament-preflight + GET /agent/tournament-preflight-status; POST /agent/commit-activation P0 gate enforced; Tool #95 run_tournament_preflight; TournamentPreflightResult 8 slots + VAPITournamentPreflight SDK; scripts/tournament_preflight.py standalone script; Bridge 1627→1636 +9; SDK 197→201 +4; Hardhat 454 unchanged)
Phase 126 — COMPLETE (Live L4 Gate Per-Battery Routing + BehavioralArchaeologist Fixes; Bridge 1619→1627 +8; SDK 193→197 +4; Hardhat 454 unchanged)
Phase 125 — COMPLETE (Calibration Modernization + Per-Battery Threshold Calibrator; Bridge 1611→1619 +8; SDK 189→193 +4; Hardhat 454 unchanged)
Phase 124 — COMPLETE (L4 Per-Battery Threshold Track Registry; Bridge 1603→1611 +8; SDK 185→189 +4; Hardhat 454 unchanged)
Phase 123 — COMPLETE (L4 Calibration Staleness Monitor; Bridge 1595→1603 +8; SDK 181→185 +4; Hardhat 454 unchanged)
Phase 122 — COMPLETE (VHP Confidence Score Separation Ratio Multiplier; Bridge 1587→1595 +8; SDK 177→181 +4; Hardhat 454 unchanged)
Phase 121 — COMPLETE (Touchpad Spatial Entropy + Separation Ratio Monitoring; Bridge 1579→1587 +8; SDK 173→177 +4; Hardhat 454 unchanged)
Phase 120 — COMPLETE (BT Transport Foundation — DualShock Edge BLE at 250 Hz; W1: separate BT threshold track required (USB 7.009/5.367 NOT applicable to 250 Hz BLE sessions); MockBLETransport seed=42 code-before-hardware (MockGSRGrip pattern); BTFrame dataclass +transport_type=0x02 tag; BLETransport optional bleak dep; bt_transport_log table +insert_bt_transport_log +get_bt_transport_status; GET /agent/bt-transport-status (7 keys); Tool #88 get_bt_transport_status; BTTransportResult(6 slots)+VAPIBTTransport SDK; schema 120; bt_transport_enabled=False default; Bridge 1571→1579 +8; SDK 169→173 +4; Hardhat 454 unchanged; W2: Phase 121 VHC — ESP32-S3 GSR grip as BLE node enabling decentralized tournament presence proof)
Phase 119 completed (Override Lifecycle Management — TTL + Use-Count Auto-Expiry — per_device_epoch_overrides +max_uses/use_count/expires_at (idempotent ALTER TABLE for Phase 118 DBs) + increment_override_use_count (auto-grad; consumed=True when max_uses reached) + delete_device_epoch_override + get_override_lifecycle_status + GET /agent/epoch-window-override-status (5 keys) + DELETE /agent/epoch-window-override + Tool #86 get_epoch_window_override_status + Tool #87 revoke_device_epoch_override + EpochWindowOverrideStatus(6 slots)+VAPIEpochWindowOverrideManager SDK + schema 119; Bridge 1562→1571 +9; SDK 165→169 +4; Hardhat 454 unchanged)
Phase 118 completed (Epoch Window Auto-Tune Advisor + Cold-Start Device Override — per_device_epoch_overrides table + get_device_epoch_override() per-device override in Gate-5 + GET /agent/epoch-window-auto-tune + POST /agent/epoch-window-override + Tool #84 get_epoch_window_auto_tune + Tool #85 set_device_epoch_override + SDK EpochWindowAutoTuneResult+VAPIEpochWindowAutoTune + schema 118; Bridge 1553→1562 +9; SDK 161→165 +4; Hardhat 454 unchanged)
Phase 117 completed (Per-Device Epoch Freshness Heatmap — get_epoch_window_analytics_by_device() p50/p95 per device sorted by p95 DESC; GET /agent/epoch-window-device-heatmap; Tool #83; SDK EpochWindowDeviceEntry+VAPIEpochWindowHeatmap; schema 117; Bridge 1545→1553 +8; SDK 157→161 +4; Hardhat 454 unchanged)
Phase 116 completed (Epoch-Window Analytics + Recommended Window Advisor — W1 misconfigured window surfaced; W2 triple-primitive analytics):
  bridge/vapi_bridge/store.py — +get_epoch_window_analytics(limit=1000): queries poad_age_seconds>=0 sorted ASC; p50/p95 via _pct(); recommended_window_seconds=max(3600,min(604800,p95×2)) fallback 86400 if n<10; schema(116,"epoch_window_analytics")
  bridge/vapi_bridge/operator_api.py — GET /agent/epoch-window-analytics (9 keys: epoch_window_enabled/epoch_window_seconds/**analytics/timestamp); inserted BEFORE /agent/vhp-dual-gate-log
  bridge/vapi_bridge/bridge_agent.py — Tool #82 get_epoch_window_analytics (before Tool #81; optional limit param; exception returns safe defaults + error key)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase115" → "3.0.0-phase116"; EpochWindowAnalyticsResult @dataclass(slots=True) (8 slots); VAPIEpochWindowAnalytics (get_analytics; never raises)
  sdk/openapi.yaml — v3.0.0-phase116; EpochWindowAnalyticsStatus schema (11 fields); GET /agent/epoch-window-analytics path
  bridge/tests/test_phase116_epoch_analytics.py — NEW (8 tests). Bridge 1537→1545 (+8)
  sdk/tests/test_phase116_epoch_analytics_sdk.py — NEW (4 tests). SDK 153→157 (+4)
  Whitepaper §9.35: DEFERRED — per standing user instruction
  W1: misconfigured epoch_window_seconds (too tight or too loose) surfaced via p50/p95 analytics before enabling gate
  W2: operator can use recommended_window_seconds = 2×p95 as data-driven tuning signal
Phase 115 completed (Epoch-Window Dual-Primitive Temporal Proof — W1 stale PoAd accumulation attack closed; W2 poad_age_seconds analytics):
  bridge/vapi_bridge/store.py — vhp_dual_gate_log extended: +poad_age_seconds REAL DEFAULT -1, +epoch_window_ok INTEGER DEFAULT 1 (ALTER TABLE idempotent for Phase 114 DBs; CREATE TABLE updated for new DBs); +get_poad_ts_ns_for_device(device_id); insert_vhp_dual_gate_log gains poad_age_seconds=-1.0 + epoch_window_ok=True kwargs; get_vhp_dual_gate_log returns 9-col dict including new fields; schema (115, "epoch_window")
  bridge/vapi_bridge/config.py — +2 fields: epoch_window_enabled (EPOCH_WINDOW_ENABLED, False); epoch_window_seconds (EPOCH_WINDOW_SECONDS, 86400.0)
  bridge/vapi_bridge/operator_api.py — Gate 5 epoch window sub-check: if epoch_window_enabled, get_poad_ts_ns_for_device→compute poad_age_seconds=(time_ns-ts_ns)/1e9; if >epoch_window_seconds→422 "epoch_window: PoAd too old"; pass poad_age_seconds+epoch_window_ok to insert_vhp_dual_gate_log; mint_allowed=eligible AND epoch_window_ok
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase114" → "3.0.0-phase115"; VHPDualGateResult slots unchanged (6)
  sdk/openapi.yaml — v3.0.0-phase115 (no new schema/path — epoch window is a sub-check of existing Gate 5)
  bridge/tests/test_phase115_epoch_window.py — NEW (8 tests). Bridge 1529→1537 (+8)
  sdk/tests/test_phase115_epoch_window_sdk.py — NEW (4 tests). SDK 149→153 (+4)
  sdk/tests/test_phase85_tournament_sdk.py — SDK version → "3.0.0-phase115"
  Whitepaper §9.34: DEFERRED — per standing user instruction
  W1: closes pre-computed PoAd accumulation attack — operator stores stale adjudication hashes then mints VHP with expired evidence; epoch_window_seconds=86400 (24h) default; epoch_window_enabled=False default (infrastructure-first, zero behavior change until enabled)
  W2: poad_age_seconds stored in every gate-5 log entry → analytics field for epoch freshness distribution; enables Phase 116 time-windowed dual-primitive analytics dashboard
Phase 112 completed (PoAd On-Chain Anchoring — W1 Block Timestamp Cross-Check + W2 Dual-Primitive Gate Activated):
  bridge/vapi_bridge/chain.py — +record_adjudication(device_id, poad_hash_hex, dual_veto): inline ABI for AdjudicationRegistry.recordAdjudication(bytes32,bytes32,bool); sha256(device_id.encode()).digest() for deviceIdHash; bytes.fromhex(poad_hash_hex) for poadHash; 80k gas; raises on missing addr or revert; same pattern as record_gsr_sample_on_chain
  bridge/vapi_bridge/config.py — +poad_on_chain_enabled (POAD_ON_CHAIN_ENABLED, False); default False = zero behavior change
  bridge/vapi_bridge/store.py — +update_poad_on_chain_tx(poad_hash, on_chain_tx); +get_unanchored_poad_entries(limit=10) oldest-first WHERE on_chain_tx IS NULL; schema (112, "poad_anchor")
  bridge/vapi_bridge/poad_anchor_agent.py — NEW: PoAdAnchorAgent(cfg,store,chain); run_poll_loop() 60s; _anchor_pending() batch=5; non-blocking on exception; poad_on_chain_enabled guard; same pattern as VHPRenewalAgent (Phase 102)
  bridge/vapi_bridge/operator_api.py — GET /agent/poad-anchor-status (6 keys: poad_on_chain_enabled/anchored_count/pending_count/last_anchor_tx/adjudication_registry_address/timestamp); inserted BEFORE /agent/adjudication-registry-status
  bridge/vapi_bridge/main.py — +Phase 112 PoAdAnchorAgent wiring (guarded by poad_on_chain_enabled)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase111" → "3.0.0-phase112"; PoAdAnchorResult @dataclass(slots=True) (6 slots); VAPIPoAdAnchor (get_anchor_status; never raises)
  sdk/openapi.yaml — v3.0.0-phase112; GET /agent/poad-anchor-status path; PoAdAnchorStatus schema (6 fields)
  contracts/test/Phase112.test.js — NEW (2 tests): recordAdjudication bytes32 inputs; two records same deviceIdHash stored separately. Hardhat 446→448 (+2)
  bridge/tests/test_phase112_poad_onchain.py — NEW (9 tests): update_poad_on_chain_tx roundtrip; get_unanchored_poad_entries; bytes32 conversions (×2); agent anchors; agent skips disabled; agent non-blocking error; endpoint 6 keys; schema_version_112. Bridge 1504→1513 (+9)
  sdk/tests/test_phase112_poad_onchain_sdk.py — NEW (4 tests): PoAdAnchorResult 6 slots; init; bad URL error; error defaults. SDK 137→141 (+4)
  Whitepaper §9.31: DEFERRED — per standing user instruction
  W1: block.number stored by AdjudicationRegistry.sol enables downstream ts_ns cross-check vs block time — closes back-dating risk from Phase 111
  W2: with both isFullyEligible() (PoAC) AND isRecorded(poadHash) (PoAd) on-chain, Phase 113 tournament contracts can require BOTH primitives — first dual-proof composability gate in any on-chain gaming protocol
Phase 115 completed (Epoch-Window Dual-Primitive Temporal Proof — W1 stale PoAd accumulation attack closed; W2 poad_age_seconds analytics):
  bridge/vapi_bridge/store.py — vhp_dual_gate_log extended: +poad_age_seconds REAL DEFAULT -1, +epoch_window_ok INTEGER DEFAULT 1 (ALTER TABLE idempotent for Phase 114 DBs; CREATE TABLE updated for new DBs); +get_poad_ts_ns_for_device(device_id); insert_vhp_dual_gate_log gains poad_age_seconds=-1.0 + epoch_window_ok=True kwargs; get_vhp_dual_gate_log returns 9-col dict including new fields; schema (115, "epoch_window")
  bridge/vapi_bridge/config.py — +2 fields: epoch_window_enabled (EPOCH_WINDOW_ENABLED, False); epoch_window_seconds (EPOCH_WINDOW_SECONDS, 86400.0)
  bridge/vapi_bridge/operator_api.py — Gate 5 epoch window sub-check: if epoch_window_enabled, get_poad_ts_ns_for_device→compute poad_age_seconds=(time_ns-ts_ns)/1e9; if >epoch_window_seconds→422 "epoch_window: PoAd too old"; pass poad_age_seconds+epoch_window_ok to insert_vhp_dual_gate_log; mint_allowed=eligible AND epoch_window_ok
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase114" → "3.0.0-phase115"; VHPDualGateResult slots unchanged (6); poad_age_seconds/epoch_window_ok visible in recent_logs raw dict from API
  sdk/openapi.yaml — v3.0.0-phase115 (no new schema/path — epoch window is a sub-check of existing Gate 5; observable via recent_logs entries)
  bridge/tests/test_phase115_epoch_window.py — NEW (8 tests): new columns roundtrip; default poad_age_seconds=-1; get_poad_ts_ns none+after_insert; schema_version_115; config defaults; epoch_window_ok=False stored; endpoint includes epoch columns in recent_logs. Bridge 1529→1537 (+8)
  sdk/tests/test_phase115_epoch_window_sdk.py — NEW (4 tests): SDK version phase115; VHPDualGateResult slots unchanged; error path no raise; URL construction includes api_key+limit. SDK 149→153 (+4)
  sdk/tests/test_phase85_tournament_sdk.py — SDK version → "3.0.0-phase115"
  Whitepaper §9.34: DEFERRED — per standing user instruction
  W1: closes pre-computed PoAd accumulation attack — operator stores stale adjudication hashes then mints VHP with expired evidence; epoch_window_seconds=86400 (24h) default; epoch_window_enabled=False default (infrastructure-first, zero behavior change until enabled)
  W2: poad_age_seconds stored in every gate-5 log entry → analytics field for epoch freshness distribution; enables Phase 116 time-windowed dual-primitive analytics dashboard
  No new contracts. No new API endpoints. Reuses existing Gate 5 (dual_primitive_gate_enabled) as outer guard.
Phase 114 completed (VHP Mint Dual-Primitive Gate — 5th gate in POST /agent/mint-vhp; infrastructure-first):
  bridge/vapi_bridge/store.py — +vhp_dual_gate_log table (id/device_id/poad_hash/eligible/poac_valid/poad_valid/mint_allowed/created_at; idx on device_id,created_at DESC) +get_latest_poad_hash_for_device() +insert_vhp_dual_gate_log() +get_vhp_dual_gate_log() +schema (114, "vhp_dual_gate")
  bridge/vapi_bridge/operator_api.py — POST /agent/mint-vhp: 5th gate (dual_primitive_gate_enabled=False default → zero behavior change; when enabled: get_latest_poad_hash_for_device→sha256(device_id)→chain.is_dual_eligible→insert_vhp_dual_gate_log→422 if not eligible); +GET /agent/vhp-dual-gate-log (6 keys: dual_primitive_gate_enabled/total_checks/eligible_count/mint_allowed_count/recent_logs/timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #81 get_vhp_dual_gate_log (before Tool #80; returns 6-key dict; handles exceptions with error key)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase113" → "3.0.0-phase114"; VHPDualGateResult @dataclass(slots=True) (6 slots: device_id/eligible/poac_valid/poad_valid/mint_allowed/error); VAPIVHPDualGate (get_gate_log; never raises; 10s timeout; error entry on exception)
  sdk/openapi.yaml — v3.0.0-phase114; +VHPDualGateStatus schema (6 fields) +GET /agent/vhp-dual-gate-log path
  bridge/tests/test_phase114_vhp_dual_gate.py — NEW (8 tests): roundtrip; poad_hash lookup; newest-first ORDER BY id DESC; schema_version_114; endpoint 6 keys; device_id filter; gate disabled hits audit gate not dual-prim; Tool #81 6 keys. Bridge 1521→1529 (+8)
  sdk/tests/test_phase114_vhp_dual_gate_sdk.py — NEW (4 tests): slots 6 fields; init; bad URL error; error defaults. SDK 145→149 (+4)
  sdk/tests/test_phase85_tournament_sdk.py — SDK version → "3.0.0-phase114"
  Whitepaper §9.33: DEFERRED — per standing user instruction
  W1: closes VHP mint without PoAd anchor when dual-primitive gate enabled
  W2: time-windowed dual-primitive proof (require PoAC + PoAd block numbers within EPOCH_WINDOW) — Phase 115 candidate
  No new config fields needed — reuses dual_primitive_gate_enabled + dual_primitive_gate_address from Phase 113
  No new contracts — pure bridge-layer gate using existing chain.is_dual_eligible() view call
Phase 113 completed (VAPIDualPrimitiveGate — Dual-Primitive Composability Gate; CONTRACT CODE COMPLETE, deploy deferred — IOTX faucet empty):
  contracts/contracts/VAPIDualPrimitiveGate.sol — NEW: pure view contract; isDualEligible(bytes32 deviceIdHash, bytes32 poadHash) returns (bool eligible, bool poac_valid, bool poad_valid); calls IVAPIProtocolLens.isFullyEligible() (PoAC) AND IAdjudicationRegistry.isRecorded() (PoAd); eligible = poac_valid && poad_valid; immutable constructor args; zero-address guards; constructor reverts on zero protocolLens
  contracts/scripts/deploy-phase113.js — NEW: reads VAPIProtocolLens + AdjudicationRegistry from deployed-addresses.json; fails fast if AdjudicationRegistry == 0x0000...; smoke tests isDualEligible; verifies immutables; updates deployed-addresses.json
  contracts/test/Phase113.test.js — NEW (6 tests): both valid→(true,true,true); only poad→(false,false,true); only poac→(false,true,false); neither→(false,false,false); zero protocolLens reverts; immutables stored. Hardhat 448→454 (+6)
  bridge/vapi_bridge/chain.py — +is_dual_eligible(device_id_hash_hex, poad_hash_hex)→dict: view call (no gas); inline ABI isDualEligible; bytes.fromhex() for both hash args; returns {"eligible","poac_valid","poad_valid"}; raises RuntimeError if dual_primitive_gate_address not configured
  bridge/vapi_bridge/config.py — +dual_primitive_gate_address (DUAL_PRIMITIVE_GATE_ADDRESS, ""); +dual_primitive_gate_enabled (DUAL_PRIMITIVE_GATE_ENABLED, False)
  bridge/vapi_bridge/store.py — dual_eligibility_checks table (device_id/poad_hash/eligible/poac_valid/poad_valid/created_at) + insert_dual_eligibility_check + get_dual_eligibility_history (ORDER BY id DESC); schema (113, "dual_primitive_gate")
  bridge/vapi_bridge/operator_api.py — GET /agent/dual-primitive-status (8 keys: dual_primitive_gate_enabled/dual_primitive_gate_address/protocol_lens_address/adjudication_registry_address/checks_total/checks_eligible/last_check_device_id/timestamp); POST /agent/check-dual-eligibility (sha256(device_id), calls chain.is_dual_eligible, stores result; returns disabled error when gate off); both inserted BEFORE /agent/poad-anchor-status
  bridge/vapi_bridge/bridge_agent.py — Tool #80 check_dual_eligibility (before Tool #79); handler queries store.get_dual_eligibility_history
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase112" → "3.0.0-phase113"; DualPrimitiveGateResult @dataclass(slots=True) (6 slots: eligible/poac_valid/poad_valid/device_id/timestamp/error); VAPIDualPrimitiveGate (check_eligibility; never raises)
  sdk/openapi.yaml — v3.0.0-phase113; GET /agent/dual-primitive-status path; POST /agent/check-dual-eligibility path; DualPrimitiveStatus schema (8 fields)
  contracts/deployed-addresses.json — VAPIDualPrimitiveGate: "0xd7b1465Aad8F815C67b24681c9c022CED24FB876" (LIVE testnet 2026-03-27); smoke isDualEligible verified; immutables verified
  bridge/tests/test_phase113_dual_primitive_gate.py — NEW (8 tests): insert roundtrip; history newest-first (ORDER BY id DESC); chain mock; chain raises no addr; endpoint 8 keys; disabled error; stores result; schema_version_113. Bridge 1513→1521 (+8)
  sdk/tests/test_phase113_dual_primitive_sdk.py — NEW (4 tests): slots 6 fields; init; bad URL error; error defaults. SDK 141→145 (+4)
  sdk/tests/test_phase85_tournament_sdk.py — SDK version assertion → "3.0.0-phase113"
  Whitepaper §9.32: DEFERRED — per standing user instruction
  W1: contract is pure view — no gas, no signing, pure on-chain composability primitive; no back-dating risk
  W2: first dual-proof composability gate in any on-chain gaming protocol — PoAC (physiological) + PoAd (adjudication) required simultaneously
Phase 111 completed (PoAd Registry — W1 PoAd Timestamp Risk + W2 Dual-Primitive Composability):
  contracts/contracts/AdjudicationRegistry.sol — NEW: Ownable (OZ v5); PoAdRecord struct (poadHash/blockNumber/recordedAt/dualVeto); mapping(deviceIdHash→PoAdRecord[]) records; mapping(poadHash→bool) poadRecorded; UNIQUE anti-replay require(!poadRecorded[poadHash]); CEI pattern; recordAdjudication(deviceIdHash,poadHash,dualVeto) onlyOwner; isRecorded(poadHash) view; getAdjudicationCount/getAdjudication views; block.number stored for W1 timestamp cross-check
  contracts/scripts/deploy-phase111.js — NEW: deploy AdjudicationRegistry; smoke test isRecorded(0x0)==false; appends AdjudicationRegistry + _phase111_status to deployed-addresses.json
  contracts/test/Phase111.test.js — NEW: 6 Hardhat tests (deploy+owner; recordAdjudication+isRecorded+blockNumber; anti-replay revert; dualVeto=true; totalAdjudications increments; non-owner OwnableUnauthorizedAccount). Hardhat 440→446 (+6)
  bridge/vapi_bridge/config.py — +2 fields: poad_registry_enabled (POAD_REGISTRY_ENABLED, false), adjudication_registry_address (ADJUDICATION_REGISTRY_ADDRESS, "")
  bridge/vapi_bridge/store.py — poad_registry_log table (9 cols; UNIQUE idx on poad_hash) + insert_poad_registry + get_poad_registry_log + schema (111, "poad_registry_log")
  bridge/vapi_bridge/session_adjudicator.py — _adj_result=None init at _dual_veto=False line; Phase 111 Step D injection: non-blocking PoAd hash SHA-256(sorted_verdicts+quorum+ts_ns) + local registry; double-guard ioswarm_adj_on AND poad_on AND _adj_result is not None; exceptions logged at DEBUG, never raise
  bridge/vapi_bridge/operator_api.py — GET /agent/adjudication-registry-status (8 keys: poad_registry_enabled/total_poad_count/dual_veto_poad_count/on_chain_anchor_count/recent_poad_logs/adjudication_registry_address/is_composable/timestamp); inserted BEFORE /agent/ioswarm-vhp-mint-status
  bridge/vapi_bridge/bridge_agent.py — Tool #79 get_adjudication_registry_status (7 fields; before Tool #78); W2 composability description
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase110" → "3.0.0-phase111"; PoAdRegistryResult @dataclass(slots=True) (8 fields); VAPIPoAdRegistry (get_poad_status; never raises)
  sdk/openapi.yaml — v3.0.0-phase111; GET /agent/adjudication-registry-status path; PoAdRegistryStatus schema (8 fields)
  bridge/tests/test_phase111_poad_registry.py — NEW (8 tests): insert+roundtrip; hash formula SHA-256; dual_veto roundtrip; non-blocking on store error; flag guard; endpoint 200/8keys; is_composable=False disabled; Tool #79 7 fields. Bridge 1496→1504 (+8)
  sdk/tests/test_phase111_poad_registry_sdk.py — NEW (4 tests): slots 8 fields; init; bad URL error; defaults. SDK 133→137 (+4)
  sdk/tests/test_phase85_tournament_sdk.py — SDK version assertion → "3.0.0-phase111"
  bridge/tests/test_phase98_epistemic_consensus.py — cfg.poad_registry_enabled=False guard
  bridge/tests/test_phase105_epistemic_hardening.py — cfg.poad_registry_enabled=False guard
  contracts/deployed-addresses.json — AdjudicationRegistry placeholder address (39th contract)
  Whitepaper §9.30: DEFERRED — per standing user instruction
Phase 110 completed (IoSwarm VHP Mint Authorization — W1 Fail-CLOSED + W2 Swarm Fingerprint):
  bridge/vapi_bridge/ioswarm_vhp_mint_emulator.py — NEW: IoSwarmVHPMintEmulator(n_nodes=5, seed=110); evaluate_vhp_mint() → 5 node verdicts; binary AUTHORIZE/DENY; consecutive_clean≥5+blocks=0→all AUTHORIZE; blocks≥2→all DENY; SHA-256 determinism
  bridge/vapi_bridge/ioswarm_vhp_mint_spec.py — NEW: VAPIVHPMintSwarmTaskSpec @dataclass(frozen=True); mint_quorum=0.80; fail_direction=CLOSED; write_spec_file()
  scripts/vapi-vhp-mint-swarm-agent.json — NEW: VHP mint task spec (task_id=vapi_vhp_mint_authorization_v1, status=phase110_infrastructure_only)
  bridge/vapi_bridge/ioswarm_vhp_mint_coordinator.py — NEW: IoSwarmVHPMintCoordinator; MINT_QUORUM=0.80 (W1); fail-CLOSED (exceptions→authorized=False; OPPOSITE of renewal fail-open); W2 swarm_fingerprint=SHA-256(node_verdicts_json)
  bridge/vapi_bridge/config.py — +2 fields: ioswarm_vhp_mint_enabled (IOSWARM_VHP_MINT_ENABLED, false), ioswarm_vhp_mint_quorum (IOSWARM_VHP_MINT_QUORUM, 0.80)
  bridge/vapi_bridge/store.py — ioswarm_vhp_mint_log table (12 cols incl. swarm_fingerprint) + insert_ioswarm_vhp_mint + get_ioswarm_vhp_mint_log + schema (110, "ioswarm_vhp_mint_log")
  bridge/vapi_bridge/operator_api.py — POST /agent/mint-vhp: ioSwarm 4th gate (additive; after existing 3-gate; ioswarm_vhp_mint_enabled=False default → zero behavior change); GET /agent/ioswarm-vhp-mint-status (8 keys; inserted BEFORE ioswarm-adjudication-status)
  bridge/vapi_bridge/bridge_agent.py — Tool #78 get_ioswarm_vhp_mint_status (7 fields; before Tool #77)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase109c" → "3.0.0-phase110"; IoSwarmVHPMintResult @dataclass(slots=True) (8 fields); VAPISwarmVHPMint (get_vhp_mint_status; never raises)
  sdk/openapi.yaml — v3.0.0-phase110; GET /agent/ioswarm-vhp-mint-status path; IoSwarmVHPMintStatus schema
  bridge/tests/test_phase110_ioswarm_vhp_mint.py — NEW (8 tests): store roundtrip; clean streak AUTHORIZE; blocks DENY; low streak DENY; fail-closed; fingerprint SHA-256; endpoint 200/8keys; Tool #78. Bridge 1488→1496 (+8)
  sdk/tests/test_phase110_ioswarm_vhp_mint_sdk.py — NEW (4 tests): slots 8 fields; init; bad URL error; defaults. SDK 129→133 (+4)
  MagicMock cfg guard added to test_phase99c_vhp.py (cfg.ioswarm_vhp_mint_enabled=False)
Phase 109C completed (IoSwarm Dual-Quorum Adjudication — W2 Dual-Quorum Veto):
  bridge/vapi_bridge/ioswarm_classj_emulator.py — NEW: IoSwarmClassJEmulator(n_nodes=5, seed=109); evaluate_classj() → 5 node verdicts; entropy≤0.03→all BLOCK; >0.15→all CLEAR; deterministic SHA-256 seed
  bridge/vapi_bridge/ioswarm_triage_emulator.py — NEW: IoSwarmTriageEmulator(n_nodes=5, seed=109); evaluate_triage() → 5 node verdicts; ml_bot_cluster→all BLOCK; not escalated→all CLEAR
  bridge/vapi_bridge/ioswarm_adjudication_spec.py — NEW: VAPIAdjudicationSwarmTaskSpec @dataclass(frozen=True); classj_block_quorum=0.67; triage_block_quorum=0.67; dual_veto_score=0.80; write_spec_file()
  scripts/vapi-adjudication-swarm-agent.json — NEW: adjudication task spec (task_id=vapi_classj_triage_adjudication_v1, status=phase109c_infrastructure_only)
  bridge/vapi_bridge/ioswarm_adjudication_coordinator.py — NEW: IoSwarmAdjudicationCoordinator; DUAL_VETO_SCORE=0.80 (W2); CLASSJ_BLOCK_QUORUM=0.67; TRIAGE_BLOCK_QUORUM=0.67; fail-open CLEAR (opposite of renewal fail-open); dual_veto fires ONLY on BLOCK+BLOCK
  bridge/vapi_bridge/config.py — +3 fields: ioswarm_adjudication_enabled (IOSWARM_ADJUDICATION_ENABLED, false), ioswarm_classj_block_quorum (0.67), ioswarm_triage_block_quorum (0.67)
  bridge/vapi_bridge/store.py — ioswarm_adjudication_log table (11 cols) + insert_ioswarm_adjudication + get_ioswarm_adjudication_log + schema (109, "ioswarm_adjudication_log")
  bridge/vapi_bridge/session_adjudicator.py — Steps A+B+C injection (additive only; ioswarm_adjudication_enabled=False default); Step C: dual veto post-score override max(consensus_score, 0.80)
  bridge/vapi_bridge/operator_api.py — GET /agent/ioswarm-adjudication-status (8 keys: enabled/classj_quorum/triage_quorum/dual_veto_count/adjudication_count/recent_logs/task_spec_registered/timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #77 get_ioswarm_adjudication_status (7 fields, before Tool #76)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase109b" → "3.0.0-phase109c"; IoSwarmAdjudicationResult @dataclass(slots=True) (8 fields); VAPISwarmAdjudication (get_adjudication_status; never raises)
  sdk/openapi.yaml — v3.0.0-phase109c; GET /agent/ioswarm-adjudication-status path; IoSwarmAdjudicationStatus schema
  bridge/tests/test_phase109c_ioswarm_adjudication.py — NEW (8 tests): store roundtrip; classj BLOCK/CLEAR; triage BLOCK/CLEAR; dual-veto fires; endpoint 200/8keys; Tool #77. Bridge 1480→1488 (+8)
  sdk/tests/test_phase109c_ioswarm_adjudication_sdk.py — NEW (4 tests): slots 8 fields; init; bad URL error; defaults. SDK 125→129 (+4)
  MagicMock cfg guards added to test_phase98/test_phase105 (cfg.ioswarm_adjudication_enabled=False)
Seamless improvements (2026-03-24): Fix D executor wired (self._feedback_executor); threshold typo 7.019→7.009; get_event_loop→get_running_loop (3 locs); utcnow/utcfromtimestamp deprecated (4 locs); L4 class defaults 6.726→7.009/5.097→5.367; test_8 TestBiometricFingerprintConsistency (HW +1→37); test_fix_d_feedback_timeout.py (Bridge +4→1464); monitor_touchpad_variance.py; MEMORY.md restructured (phase_pointers.md topic file)
Phase 108 completed (Tournament Readiness Scorecard — 7-Condition AND Gate):
  bridge/vapi_bridge/config.py — +2 fields: separation_ratio_current (SEPARATION_RATIO_CURRENT, 0.362), touchpad_recapture_complete (TOUCHPAD_RECAPTURE_COMPLETE, false)
  bridge/vapi_bridge/store.py — tournament_readiness_snapshots table (15 columns) + insert_tournament_readiness_snapshot + get_latest_tournament_readiness_snapshot + schema (108, "tournament_readiness")
  bridge/vapi_bridge/operator_api.py — GET /agent/tournament-readiness (7-condition scorecard: 5 software + 2 hardware; persists snapshot; blocking_conditions list)
  bridge/vapi_bridge/bridge_agent.py — Tool #74 get_tournament_readiness (definition + handler; returns snapshot with found flag)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase107" -> "3.0.0-phase108"; TournamentReadinessResult @dataclass(slots=True) (11 fields); VAPITournamentReadiness (get_scorecard; never raises)
  sdk/openapi.yaml — v3.0.0-phase108; GET /agent/tournament-readiness path; TournamentReadiness schema
  docs/vapi-whitepaper-v3.md §9.25 — 7-condition AND gate table; W1 manual override; W2 audit trail; config fields; Tool #74; SDK; phase distinction
  bridge/tests/test_phase108_tournament_readiness.py — NEW (8 tests): table+None; endpoint fields; sw=5 when all pass; hw=0 defaults; hw=2 when ready; fully_ready=False hw blocking; roundtrip; Tool #74. Bridge 1452->1460 (+8)
  sdk/tests/test_phase108_tournament_readiness_sdk.py — NEW (4 tests): slots 11 fields; init; get_scorecard never raises; defaults on error. SDK 113->117 (+4)
Phase 109A completed (ioSwarm Bridge Adapter — Three Primitives Fusion):
  bridge/vapi_bridge/ioswarm_consensus_aggregator.py — NEW: IoSwarmConsensusAggregator (aggregate(node_verdicts); BLOCK_QUORUM=0.67 W1; tie->HOLD; hold_escalation_flag after 3 consec HOLDs; swarm_verdict_score BLOCK=1.0/FLAG-HOLD=0.5/CLEAR-CERTIFY=0.0; never raises)
  bridge/vapi_bridge/ioswarm_task_spec.py — NEW: VAPISwarmTaskSpec @dataclass(frozen=True); to_json() ioSwarm-compatible spec; VHP auth gate isFullyEligible(); W3bstream applets; quorum_config; reward_condition; write_spec_file()
  scripts/vapi-swarm-agent.json — NEW: ioSwarm task spec (task_id=vapi_pitl_adjudication_v1, status=phase109a_infrastructure_only)
  bridge/vapi_bridge/config.py — +5 fields: ioswarm_enabled (IOSWARM_ENABLED, false), ioswarm_quorum_threshold (0.60), ioswarm_block_quorum_threshold (0.67), ioswarm_node_count (5), ioswarm_endpoint ("")
  bridge/vapi_bridge/store.py — ioswarm_consensus_log table (13 cols) + idx + insert_ioswarm_consensus + get_ioswarm_consensus_log + schema (109, "ioswarm_consensus_log") + idempotent ALTER TABLE epistemic_consensus_log ADD COLUMN swarm_score; insert_epistemic_consensus gains swarm_score=0.0 kwarg
  bridge/vapi_bridge/session_adjudicator.py — _assess_ioswarm_score() async helper (never raises, returns 0.0 when disabled); _epistemic_consensus() rebalanced: when ioswarm_on and score>0: ClassJ(0.35)+Triage(0.35)+Supervisor(0.15)+Swarm(0.15); else Phase 98 weights unchanged
  bridge/vapi_bridge/operator_api.py — GET /agent/ioswarm-status (10 keys; ioswarm_enabled/quorum_threshold/consensus_count/task_spec_registered/w3bstream_applets/vhp_auth_gate_address/timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #75 get_ioswarm_status (definition + handler; returns ioswarm_enabled/quorum_threshold/consensus_count/node_count/task_spec_registered/w3bstream_applets/vhp_auth_gate_address)
  bridge/vapi_bridge/edge_ai_profile.py — ioswarm_integration context dict added to get_edge_ai_profile() return (status=infrastructure_only, phase=109A, applets, next_step)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase108" -> "3.0.0-phase109"; IoSwarmConsensusResult @dataclass(slots=True) (9 fields); VAPISwarmStatus (get_status->IoSwarmConsensusResult; never raises)
  sdk/openapi.yaml — v3.0.0-phase109; GET /agent/ioswarm-status path; IoSwarmStatus schema
  docs/vapi-whitepaper-v3.md §9.26 — Three Primitives thesis; IoSwarmConsensusAggregator design (W1/W2); epistemic 4th signal (weight tables); VHP auth gate; W3bstream applet binding; Phase 109B preview
  bridge/tests/test_phase109a_ioswarm.py — NEW (8 tests): BLOCK@80pct; HOLD@60pct (W1); tie->HOLD; hold_escalation; store roundtrip; endpoint 200/10keys; bad_key 403; Tool #75. Bridge 1464->1472 (+8)
  sdk/tests/test_phase109a_ioswarm_sdk.py — NEW (4 tests): slots 9 fields; init; bad URL error; defaults on error. SDK 117->121 (+4)
Phase 107 completed (Live Mode Readiness Validation — N=100 Corpus):
  bridge/vapi_bridge/live_mode_readiness_validator.py — NEW: LiveModeReadinessValidator (run_validation(n=100); SyntheticSessionGenerator(seed=107).generate_corpus(n); SessionAdjudicator._rule_fallback() for each session; BLOCK on nominal=false positive; W1 isolation: results go to live_mode_readiness_reports only; never raises from run_validation)
  bridge/vapi_bridge/store.py — live_mode_readiness_reports table (n_tested/false_positive_count/false_positive_rate/activation_committed/pmi/dry_run_active/ready_for_live/notes/created_at) + insert_readiness_report + get_latest_readiness_report + schema (107, "live_mode_readiness") + compute_pmi() W1 expiry guard (returns 0 when is_simulation=True AND is_valid=False)
  bridge/vapi_bridge/operator_api.py — POST /agent/run-readiness-validation (n param) + GET /agent/live-mode-readiness (found flag + report fields)
  bridge/vapi_bridge/bridge_agent.py — Tool #73 get_live_mode_readiness (definition + handler; returns ready_for_live/n_tested/found)
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase106" -> "3.0.0-phase107"; LiveModeReadinessResult @dataclass(slots=True) (8 fields: n_tested/false_positive_count/false_positive_rate/activation_committed/pmi/dry_run_active/ready_for_live/error); VAPILiveModeValidator (run_validation/get_latest; never raises)
  sdk/openapi.yaml — v3.0.0-phase107; POST /agent/run-readiness-validation + GET /agent/live-mode-readiness paths; ReadinessReport + ReadinessStatus schemas
  docs/vapi-whitepaper-v3.md §9.24 — ready_for_live 5-condition AND gate; W1 PMI drift closed; W1 isolation; Phase 86 vs Phase 107 distinction; SDK LiveModeReadinessResult
  docs/operator-onboarding-runbook.md — NEW (Phase 106 gap closure): bootstrap sequence; verify protocol-maturity; run-readiness-validation; epistemic-config check; VHP monitoring
  docs/developer-integration-guide.md — NEW (Phase 106 gap closure): VAPITournamentIntegration quickstart; VAPILiveModeValidator; honest separation_ratio=0.362 disclosure
  bridge/tests/test_phase107_readiness.py — NEW (8 tests): table+None; run_validation no fp; ready_for_live False default; ready_for_live True all conditions; POST endpoint 200; GET found flag; roundtrip; Tool #73. Bridge 1444->1452 (+8)
  sdk/tests/test_phase107_readiness_sdk.py — NEW (4 tests): slots 8 fields; init; run_validation never raises; get_latest never raises. SDK 109->113 (+4)
Phase 106 completed (Developer Integration Runbook + SDK Onboarding):
  sdk/vapi_sdk.py — SDK_VERSION "3.0.0-phase85" -> "3.0.0-phase106"; BootstrapResult @dataclass(slots=True) (8 fields: simulation_done/activation_committed/pmi/pmi_label/dry_run_active/days_until_vhp_expiry/fully_bootstrapped/error); VAPIOperatorOnboarding (bootstrap one-call sequence: get_maturity->commit_activation->verify final; never raises; check_maturity() delegates to VAPIProtocolMaturity); TournamentEntryResult @dataclass(slots=True) (7 fields: device_id/wallet/entered/demo_mode/is_eligible/has_valid_vhp/error); VAPITournamentIntegration (request_game_demo composes VAPITournamentClient; demo_mode=True; never raises)
  sdk/openapi.yaml — v3.0.0-phase106
  docs/vapi-whitepaper-v3.md §9.23 — VAPIOperatorOnboarding one-call bootstrap; VAPITournamentIntegration game developer pattern; SDK_VERSION 3.0.0-phase106; honest separation_ratio=0.362 disclosure
  sdk/tests/test_phase106_developer_sdk.py — NEW (6 tests): BootstrapResult slots; VAPIOperatorOnboarding init; bootstrap error on bad URL; TournamentEntryResult slots; request_game_demo never raises; bootstrap fully_bootstrapped=True when maturity mocked. SDK 103->109 (+6)
Phase 105 completed (Epistemic Consensus Hardening):
  bridge/vapi_bridge/store.py — epistemic_threshold_history table (id/old_threshold/new_threshold/trigger/pmi_at_change/notes/created_at) + insert_epistemic_threshold_change + get_epistemic_threshold_history(limit=20) + schema (105, "epistemic_threshold_history")
  bridge/vapi_bridge/config.py — +2 fields: epistemic_recommended_threshold (EPISTEMIC_RECOMMENDED_THRESHOLD, 0.65), epistemic_triage_prereq_required (EPISTEMIC_TRIAGE_PREREQ_REQUIRED, false)
  bridge/vapi_bridge/session_adjudicator.py — Phase 104/105 synergy: when compute_pmi()>=1 AND recommended>base, threshold=recommended (W2 auto-raise); Phase 105 W1: triage_prereq_required guard returns proposed_verdict unchanged when triage_score<=0.0 (opt-in, closes 1-agent gate attack)
  bridge/vapi_bridge/operator_api.py — GET /agent/epistemic-config (configured/recommended/effective_threshold; pmi_triggered; triage_prereq_required; at_risk; threshold_history; w1_note)
  bridge/vapi_bridge/bridge_agent.py — Tool #72 get_epistemic_config (definition + handler; returns at_risk/effective_threshold/pmi_triggered/threshold_history_count)
  sdk/openapi.yaml — EpistemicConfig schema + /agent/epistemic-config path
  docs/vapi-whitepaper-v3.md §9.22 — Phase 98 W1 closure via PMI-triggered threshold raise; triage_prereq guard; epistemic_threshold_history audit trail
  bridge/tests/test_phase105_epistemic_hardening.py — NEW (6 tests): threshold_history table+methods; PMI>=1 uses 0.65 (ClassJ+sup=0.60<0.65->HOLD); PMI=0 uses 0.60 (0.60>=0.60->BLOCK); triage_prereq=True+score=0->BLOCK unchanged; epistemic-config 200; Tool #72. Bridge 1438->1444 (+6)
Phase 104 completed (Persistent Activation Commit + ProtocolMaturityIndex):
  bridge/vapi_bridge/store.py — activation_state table (id/activation_committed/pmi/committed_at/committed_by/pmi_updated_at/notes/created_at) + get_activation_state + set_activation_committed + set_pmi + compute_pmi + schema (104, "activation_state")
  bridge/vapi_bridge/config.py — +2 fields: protocol_maturity_enabled (PROTOCOL_MATURITY_ENABLED, true), activation_auto_restore (ACTIVATION_AUTO_RESTORE, true)
  bridge/vapi_bridge/main.py — _restore_activation_state(cfg, store): reads activation_state; if committed=True calls object.__setattr__(cfg,"agent_dry_run_mode",False) BEFORE asyncio tasks start (Phase 104 W1 mitigation; eliminates restart race window)
  bridge/vapi_bridge/operator_api.py — POST /agent/commit-activation (6-step: simulate if needed->Phase 97 gate->persist->object.__setattr__ dry_run=False->bus event->PMI compute+store); GET /agent/protocol-maturity (pmi/pmi_label/activation_committed/dry_run_active/vhp_found/timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #71 get_protocol_maturity (definition + handler; returns pmi/pmi_label/activation_committed/dry_run_active/days_until_vhp_expiry/vhp_found)
  sdk/vapi_sdk.py — ProtocolMaturityResult @dataclass(slots=True) (9 fields: pmi/pmi_label/activation_committed/committed_at/dry_run_active/is_simulation/days_until_vhp_expiry/vhp_found/error); VAPIProtocolMaturity (get_maturity->ProtocolMaturityResult; commit_activation->dict; never raises)
  sdk/openapi.yaml — CommitActivationResult + ProtocolMaturityStatus schemas + POST /agent/commit-activation + GET /agent/protocol-maturity paths
  docs/vapi-whitepaper-v3.md §9.21 — W1 dry_run restart gap; activation_state table; _restore_activation_state startup; PMI 0-3 ladder; commit-activation 6-step; VAPIProtocolMaturity SDK
  bridge/tests/test_phase104_activation_commit.py — NEW (8 tests): activation_state defaults; set_activation_committed; compute_pmi 0->1 after sim; _restore sets dry_run=False; _restore no-op when not committed; POST commit-activation 200; GET protocol-maturity fields; Tool #71. Bridge 1430->1438 (+8)
  sdk/tests/test_phase104_maturity_sdk.py — NEW (4 tests): ProtocolMaturityResult slots; VAPIProtocolMaturity init; get_maturity never raises; commit_activation never raises. SDK 99->103 (+4)
Phase 103 completed (Live Activation Protocol — First VHP on Testnet):
  bridge/vapi_bridge/activation_simulation.py — NEW: ActivationSimulator (6 seed methods; seeding order satisfies Phase 96 chronological invariant; SIM_DEVICE_ID="sim_activation_phase103"; tx_hash="sim_mint_<sha256_hex16>"; never raises)
  bridge/vapi_bridge/activation_runner.py — NEW: ActivationRunner (async run(n_sessions=110); 12-step sequence: seed->verify->toggle dry_run=False in-memory->VHP insert->bus event->log; fully_activated=gate_passed AND vhp_minted AND dry_run_toggled; never raises from run())
  bridge/vapi_bridge/store.py — activation_simulation_log table (n_sessions/gate_passed/cert_created/dry_run_toggled/vhp_minted/token_id/tx_hash/created_at) + insert_activation_simulation_log + get_activation_simulation_log + get_first_vhp_status (is_simulation=tx_hash.startswith("sim_")) + schema (103, "activation_simulation")
  bridge/vapi_bridge/operator_api.py — POST /agent/run-activation-simulation (n_sessions param) + GET /agent/first-vhp-status (found/is_simulation/tx_hash)
  bridge/vapi_bridge/bridge_agent.py — Tool #70 run_activation_sequence (definition + handler; returns vhp_minted/fully_activated/tx_hash/elapsed_ms)
  sdk/vapi_sdk.py — SimulationResult @dataclass(slots=True) (10 fields: simulation_sessions/gate_passed/cert_created/dry_run_toggled/vhp_minted/token_id/tx_hash/fully_activated/elapsed_ms/error) + VAPIActivationFlow (run_simulation/check_ready/get_first_vhp; never raises)
  sdk/openapi.yaml — v3.0.0-phase103; POST /agent/run-activation-simulation + GET /agent/first-vhp-status paths; SimulationResult + FirstVHPStatus schemas
  docs/vapi-whitepaper-v3.md §9.20 — Live Activation Protocol (seeding order, ActivationRunner 12-step, W2 ProtocolMaturityScore primitive, SDK VAPIActivationFlow)
  bridge/tests/test_phase103_activation.py — NEW (8 tests): activation_simulation_log table+methods; seed_validation_records->gate_passed; get_first_vhp_status None on empty; ActivationRunner fully_activated; first-vhp-status 200 found+is_simulation; run-activation-simulation 200; Tool #70; total_vhp_count>0. Bridge 1422->1430 (+8)
  sdk/tests/test_phase103_activation_sdk.py — NEW (6 tests): SimulationResult slots; VAPIActivationFlow init; never raises bad URL; check_ready parses; get_first_vhp parses; fully_activated=False on error. SDK 93->99 (+6)
Phase 102 completed (Developer Integration Layer):
  contracts/contracts/TournamentGateDemo.sol — NEW: Ownable; IVAPIProtocolLens+IVAPIVerifiedHumanProof interfaces; enterTournament(bytes32 deviceId, uint256 vhpTokenId) enforces isFullyEligible+isValid when demoMode=false; W1 demoMode flag bypasses gate for testnet dev evaluation; getParticipantCount()+getParticipant(idx); PlayerEntered event; DemoModeSet event
  contracts/contracts/MockProtocolLens102.sol + MockVHP102.sol — NEW test helpers for Phase 102 Hardhat tests
  contracts/scripts/deploy-phase102.js — deploy TournamentGateDemo(lens,vhp); setDemoMode(true); updates deployed-addresses.json; ~0.04 IOTX
  contracts/test/Phase102.test.js — 4 Hardhat tests (T102-1..4): demoMode bypass; PITL gate revert; VHP validity revert; non-owner setDemoMode revert. Hardhat 430→434 (+4)
  bridge/vapi_bridge/vhp_renewal_agent.py — NEW: VHPRenewalAgent (14th agent); POLL_INTERVAL_S=21600 (6h); _check_and_renew() finds expiring VHPs via get_expiring_vhps(cutoff); dry_run skips chain; live mode calls chain.renew_vhp(token_id); publishes vhp_lifecycle_warning when total_vhp_count==0 (W2 liveness beacon); never raises from run_poll_loop
  bridge/vapi_bridge/chain.py — +1 async method renew_vhp(token_id): inline ABI for VAPIVerifiedHumanProof.renew; 60k gas; raises on revert
  bridge/vapi_bridge/store.py — vhp_renewal_log table (device_id/token_id/old_expires_at/new_expires_at/tx_hash/dry_run/created_at) + insert_vhp_renewal + get_vhp_renewal_log(device_id=None, limit=20) + get_expiring_vhps(cutoff_ts) + get_total_vhp_count + schema (102, "vhp_renewal_log")
  bridge/vapi_bridge/config.py — +2 fields: vhp_renewal_enabled (VHP_RENEWAL_ENABLED, True), vhp_renewal_warning_days (VHP_RENEWAL_WARNING_DAYS, 7)
  bridge/vapi_bridge/operator_api.py — GET /agent/vhp-renewal-log (device_id filter + limit + timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #69 get_vhp_renewal_log (definition + handler; lifecycle_warning beacon)
  bridge/vapi_bridge/main.py — Phase 102 wiring: VHPRenewalAgent (guarded by vhp_renewal_enabled)
  bridge/vapi_bridge/edge_ai_profile.py — _AGENT_FLEET gains "VHPRenewalAgent" (14th); fallback fleet_size 13→14
  sdk/vapi_sdk.py — PlayerEligibility @dataclass(slots=True) (8 fields: device_id/wallet/is_eligible/has_valid_vhp/consecutive_clean/cert_level/expires_at/error); VAPITournamentClient (check_player→PlayerEligibility, never raises)
  sdk/openapi.yaml — v3.0.0-phase102; /agent/quicksilver-status + /agent/edge-ai-profile (Phase 101) + /agent/vhp-renewal-log (Phase 102) paths; QuickSilverStatus+EdgeAIProfile+VHPRenewalLog schemas
  docs/vapi-whitepaper-v3.md §9.18 — Phase 101 AGaaS Economics + IoTeX Positioning; §9.19 — Phase 102 Developer Integration Layer
  bridge/tests/test_phase102_tournament.py — NEW (8 tests): insert+get vhp_renewal_log; get_expiring_vhps; total_count=0; endpoint 200; bad key 403; dry_run no chain call; Tool #69; lifecycle_warning beacon. Bridge 1414→1422 (+8)
  sdk/tests/test_phase102_tournament_sdk.py — NEW (6 tests): PlayerEligibility slots; defaults; bad URL never raises; parses eligible; parses ineligible; never raises on timeout. SDK 87→93 (+6)
Phase 101 completed (AGaaS Economics + IoTeX Positioning):
  contracts/contracts/VAPIQuickSilverCollateral.sol — stIOTX lock/unlock/claim/slash flows; double-yield mechanism
  contracts/scripts/deploy-phase101.js — deploy VAPIQuickSilverCollateral; writes bridge/.env.phase101
  bridge/vapi_bridge/config.py — +2 fields: stiotx_token_address (STIOTX_TOKEN_ADDRESS), quicksilver_collateral_address (QUICKSILVER_COLLATERAL_ADDRESS)
  bridge/vapi_bridge/store.py — quicksilver_collateral_events table + insert_quicksilver_collateral_event + get_quicksilver_collateral_status + schema (101, "quicksilver_collateral_events")
  bridge/vapi_bridge/chain.py — lock_stiotx_collateral + unlock_stiotx_collateral + is_active_stiotx_collateral async methods
  bridge/vapi_bridge/operator_api.py — GET /agent/quicksilver-status + GET /agent/edge-ai-profile endpoints
  bridge/vapi_bridge/edge_ai_profile.py — NEW: get_edge_ai_profile() maps 13-agent fleet onto IoTeX Real-World AI stack (ioID/W3bstream/Realms); inference_mode llm_augmented vs local_rule_fallback; never raises
  bridge/vapi_bridge/bridge_agent.py — Tool #67 get_quicksilver_collateral_status + Tool #68 get_edge_ai_profile
  sdk/openapi.yaml — v3.0.0-phase101
  docs/vapi-whitepaper-v3.md §9.18 — AGaaS Economics + IoTeX Positioning. Bridge 1400→1410. **Phase 101 COMPLETE.**
Phase 100 completed (Live Mode Activation Bootstrap + Activation Status Dashboard):
  bridge/vapi_bridge/store.py — get_ioid_devices(limit=10): returns list of {device_id, device_address, did, registered_at} from ioid_devices table ORDER BY registered_at DESC; used as warm-up bootstrap fallback (Phase 100)
  bridge/vapi_bridge/operator_api.py — POST /agent/warm-up: adds device_ids query param (comma-separated); resolution order: explicit param → recent agent_rulings → ioid_devices fallback; returns reason="no_devices_registered"+hint if all sources empty; GET /agent/activation-status: 5-step checklist (gate/cert/audit/dry_run/vhp); current_blocking_step 1-6; progress_pct; recommended_action; warnings (low gate_n)
  bridge/vapi_bridge/bridge_agent.py — Tool #66 get_activation_status: {current_blocking_step, fully_activated, consecutive_clean, gate_n, progress_pct, dry_run_active, audit_valid, cert_valid, timestamp}
  sdk/openapi.yaml — v3.0.0-phase100; GET /agent/activation-status path + ActivationStatus schema; /agent/warm-up updated with device_ids param
  docs/vapi-whitepaper-v3.md §9.17 — Operator Activation Runbook (bootstrap gap, warm-up resolution order, 5-step checklist table, Tool #66, activation sequence)
  bridge/tests/test_phase100_activation.py — NEW (8 tests): get_ioid_devices; activation-status keys; blocking_step=1 no sessions; progress_pct 50%; blocking_step=4 gate+cert+audit pass dry_run=True; fully_activated; warm-up device_ids param; Tool #66. Bridge 1392→1400 (+8)
ZK vkey hotfix (2026-03-21): bridge/zk_prover.py — _ZK_VKEY default corrected from verification_key.json to TeamProof_verification_key.json; all real ZK verify tests now pass; total bridge 1400→1414 (includes 10 L6 tests previously uncollected from bridge/ dir, now collected from repo root)
Phase 99A completed (AGaaS Foundation Token Stack):
  contracts/contracts/VAPIToken.sol — ERC20Pausable+Ownable; MAX_SUPPLY=1B VAPI; completeTGE() irrevocably seals mint() + pauses transfers; TGE gated (separation>1.0+N≥100 adjudications+VHP demonstrated); testnet ONLY in Phase 99
  contracts/contracts/VAPIOperatorRegistry.sol — ReentrancyGuard+Ownable; MINIMUM_STAKE=10,000 VAPI; slash() burns 50%/sends 50% to claimant (CEI); 30-day DEREGISTER_COOLDOWN; isOperator() view
  contracts/contracts/VAPIHardwareCertRegistry.sol — Ownable; profileHash→HardwareProfile; certLevel 1=controller/2=controller+GSR; isCertified() pure view (first hardware-level DePIN composability primitive); certificationFee in VAPI; revokeCertification() onlyOwner
  contracts/scripts/deploy-phase99a.js — sequential deploy Token→OperatorReg→HardwareCertReg; certifies DualShock Edge as reference hardware; writes bridge/.env.phase99a
  contracts/test/Phase99A.test.js — 12 Hardhat tests (4 per contract): T99A-1..12; fresh beforeEach deploy enforces W1 invariant
  bridge/vapi_bridge/config.py — +3 fields: vapi_token_address (VAPI_TOKEN_ADDRESS), operator_registry_address (OPERATOR_REGISTRY_ADDRESS), hardware_cert_registry_address (HARDWARE_CERT_REGISTRY_ADDRESS)
  bridge/vapi_bridge/store.py — operator_registrations table (operator_address/event_type/stake_amount/tx_hash/reason/created_at) + insert_operator_registration + get_operator_status + schema (99, "vapi_token")
  bridge/vapi_bridge/operator_api.py — GET /agent/operator-status (operator_address param + found/status/vapi_token_address/operator_registry_address/timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #65 get_operator_status (definition + handler)
  sdk/openapi.yaml — v3.0.0-phase99a; GET /agent/operator-status path; OperatorStatus schema
  docs/vapi-whitepaper-v3.md §9.14 — AGaaS Foundation Token Stack section (W1 isolation, W2 composability, 3-contract design, DePIN economics)
  bridge/tests/test_phase99a_token.py — NEW (6 tests): config fields; insert+get; unknown→None; endpoint 200; bad key 403; Tool #65. Bridge 1372→1378 (+6)
Phase 99B completed (W3bstream + VAPIGSRRegistry + L7_GSR):
  contracts/contracts/VAPIGSRRegistry.sol — Ownable; recordSample(bytes32,uint256,uint256,uint256) onlyOwner; anti-replay via (deviceId,timestamp) uniqueness; getLatestSample() view; getSampleCount() view; GSR_ENABLED=false default
  contracts/scripts/deploy-phase99b.js — deploy VAPIGSRRegistry(owner); sanity check recordSample+getSampleCount=1; writes bridge/.env.phase99b
  contracts/test/Phase99B.test.js — 4 Hardhat tests (T99B-1..4): recordSample+getLatestSample; duplicate ts revert; non-owner revert; getSampleCount increments. Hardhat 420→424 (+4)
  bridge/vapi_bridge/gsr_feature_extractor.py — NEW: GSRSample dataclass; MockGSRGrip(seed) reproducible synthetic EDA; extract_l7_features(window)→dict (4 features; never raises; zeros for <10 samples)
  bridge/vapi_bridge/gsr_registry_agent.py — NEW: GSRRegistryAgent(cfg,store,chain,bus); run_poll_loop(); _collect_and_store() never raises; skips chain when gsr_enabled=False; publishes gsr_sample_recorded bus event
  bridge/vapi_bridge/config.py — +4 fields: gsr_enabled (GSR_ENABLED, false), gsr_sample_interval_s (GSR_SAMPLE_INTERVAL_S, 30), gsr_registry_address (GSR_REGISTRY_ADDRESS), w3bstream_project_id (W3BSTREAM_PROJECT_ID)
  bridge/vapi_bridge/store.py — gsr_samples table (device_id/arousal_index/correlation/conductance_raw/l7_features_json/created_at) + insert_gsr_sample + get_gsr_samples(device_id, limit=50) + schema (992, "gsr_registry")
  bridge/vapi_bridge/chain.py — +1 async method: record_gsr_sample_on_chain(device_id_bytes32, arousal_millis, correlation_millis, ts); inline ABI for VAPIGSRRegistry.recordSample; 80k gas
  bridge/vapi_bridge/session_adjudicator.py — _assess_gsr_risk(device_id) async (never raises, returns {} on empty); evidence enrichment guarded by gsr_enabled
  bridge/vapi_bridge/main.py — Phase 99B wiring: GSRRegistryAgent task guarded by gsr_enabled
  scripts/w3bstream/validate_poac_record.ts — AssemblyScript stub: 228B PoAC→ECDSA-P256 verify→PITLSessionRegistryV2.submitProof(); chain hash invariant SHA-256(164B) enforced
  scripts/w3bstream/process_gsr_packet.ts — AssemblyScript stub: 48B GSR packet (magic 0x47535201)→VAPIGSRRegistry.recordSample(); arousal/corr range validation
  sdk/openapi.yaml — v3.0.0-phase99b; GSRSample schema (device_id/arousal_index/correlation/conductance_raw/l7_features_json/created_at)
  docs/vapi-whitepaper-v3.md §9.15 — W3bstream Integration + L7_GSR Layer (VAPIGSRRegistry design, W3bstream applets, 4-feature extraction, GSR_ENABLED gate, BOM)
  bridge/tests/test_phase99b_gsr.py — NEW (8 tests): MockGSRGrip determinism; 4 required keys; zeros <10; never raises malformed; insert+retrieve; unknown→[]; skip chain gsr_disabled; _assess_gsr_risk→{} empty. Bridge 1378→1386 (+8)
  bridge/tests/test_phase68_enhancements.py — _make_cfg() gains cfg.gsr_enabled=False (Phase 99B guard — prevents MagicMock truthy GSR branch in SessionAdjudicator from breaking test_10)
Phase 99C completed (VHP Soulbound Token + LayerZero Bridge — Phase 99 COMPLETE):
  contracts/contracts/VAPIVerifiedHumanProof.sol — Ownable; ERC-4671 soulbound; VHPData struct (deviceIdHash/certLevel/consecutiveClean/confidenceScore/issuedAt/expiresAt/mpcCeremonyHash); mint(address,VHPData) onlyOwner; isValid(tokenId) view; renew(tokenId) onlyOwner +90d; ALL transfer functions revert "soulbound"; _tokenIdCounter plain uint256 (no Counters, OZ v5); totalSupply() view
  contracts/contracts/VAPIVerifiedHumanProofBridge.sol — Ownable; LayerZero V2 OApp stub; setPeer(dstEid,bytes32); send(tokenId,dstEid,recipient,VHPData) nonce anti-replay; getSentNonce() view; withdrawNative() onlyOwner
  contracts/scripts/deploy-phase99c.js — deploy VHP(owner)+Bridge(lzEndpoint,owner); sanity check mint+isValid+totalSupply=1; sanity check setPeer; writes bridge/.env.phase99c; updates deployed-addresses.json (~0.13 IOTX)
  contracts/test/Phase99C.test.js — 6 Hardhat tests (T99C-1..6): mint+isValid+totalSupply; isValid false after expiry; transferFrom reverts soulbound; renew +90d; renew expired reverts; mint non-owner reverts OwnableUnauthorizedAccount. Hardhat 424→430 (+6). NOTE: T99C-2/T99C-5 use block timestamp (not Date.now()) to avoid evm_increaseTime divergence
  bridge/vapi_bridge/config.py — +2 fields: vhp_contract_address (VHP_CONTRACT_ADDRESS), layerzero_endpoint_address (LAYERZERO_ENDPOINT_ADDRESS)
  bridge/vapi_bridge/store.py — vhp_issuances table (device_id/token_id/tx_hash/expires_at/cert_level/consecutive_clean/to_address/created_at) + insert_vhp_issuance + get_vhp_status + schema (993, "vhp_issuances")
  bridge/vapi_bridge/chain.py — +1 async method: mint_vhp(to,device_id_hash,cert_level,consecutive_clean,confidence_score,mpc_ceremony_hash,ttl_days=90); VHPData tuple ABI; 150k gas
  bridge/vapi_bridge/operator_api.py — POST /agent/mint-vhp (3-gate: audit_valid+gate_passed+not_dry_run; 422 on failure; calls chain.mint_vhp; stores to vhp_issuances) + GET /agent/vhp-status/{device_id} (found/is_valid/token_id/cert_level/expires_at)
  sdk/vapi_sdk.py — VHPData @dataclass(slots=True) (11 fields: device_id/token_id/cert_level/consecutive_clean/confidence_score/issued_at/expires_at/is_valid/to_address/vhp_contract_address/error); VAPIHumanProof class (is_human/get_vhp_data/request_vhp_mint; never raises)
  sdk/openapi.yaml — v3.0.0-phase99c; POST /agent/mint-vhp + GET /agent/vhp-status/{device_id} paths; VHPMintResult+VHPStatus+GSRSample schemas
  docs/vapi-whitepaper-v3.md §9.16 — VHP soulbound design (mint gate table, soulbound invariant, composability triple-require, LayerZero OApp stub, SDK VAPIHumanProof)
  bridge/tests/test_phase99c_vhp.py — NEW (6 tests): insert+retrieve; unknown→None; mint-vhp 422 dry_run; mint-vhp 422 no audit; vhp-status 200 required fields; bad key 403. Bridge 1386→1392 (+6)
  sdk/tests/test_phase99c_vhp_sdk.py — NEW (6 tests): VHPData defaults; slots 11 fields; is_human False on error; get_vhp_data parses; request_vhp_mint error dict; is_human True on valid. SDK 81→87 (+6)
Phase 98 completed (Epistemic Consensus Protocol):
  bridge/vapi_bridge/session_adjudicator.py — _epistemic_consensus(device_id, proposed_verdict, ruling_id=None): fires only on BLOCK; weighted score: ClassJDetector(0.40)+DivergenceTriageAgent(0.40)+AgentSupervisor(0.20); score<threshold(0.60) downgrades BLOCK→HOLD; wired into _process_ruling_request() and _adjudicate_device_directly(); never raises; logs to epistemic_consensus_log
  bridge/vapi_bridge/store.py — epistemic_consensus_log table (device_id/ruling_id/proposed_verdict/class_j_score/triage_score/supervisor_score/consensus_score/threshold/consensus_reached/final_verdict/downgraded/created_at) + insert_epistemic_consensus + get_epistemic_consensus_log(device_id=None, limit) + schema (98, "epistemic_consensus")
  bridge/vapi_bridge/config.py — epistemic_consensus_enabled (EPISTEMIC_CONSENSUS_ENABLED, true), epistemic_consensus_threshold (EPISTEMIC_CONSENSUS_THRESHOLD, 0.60)
  bridge/vapi_bridge/operator_api.py — GET /agent/epistemic-consensus-log (device_id filter + limit + downgraded_count)
  bridge/vapi_bridge/bridge_agent.py — Tool #64 get_epistemic_consensus_log (definition + handler)
  sdk/openapi.yaml — v3.0.0-phase98; GET /agent/epistemic-consensus-log path; EpistemicConsensusLog schema
  docs/vapi-whitepaper-v3.md §9.13 — Epistemic Consensus Protocol section (threshold analysis, scope, audit trail)
  bridge/tests/test_phase98_epistemic_consensus.py — NEW (8 tests): table+methods; non-BLOCK unchanged; BLOCK+no evidence→HOLD; BLOCK+HIGH classJ=threshold; BLOCK+classJ+triage=BLOCK; disabled bypass; endpoint; Tool #64. Bridge 1364→1372 (+8)
Phase 97 completed (Gated Live Mode Transition):
  bridge/vapi_bridge/operator_api.py — POST /agent/config?dry_run=false: 3-condition gate (gate_passed+cert_valid+audit_valid); HTTP 422 with blocking array on failure; cfg.agent_dry_run_mode updated on success; bus.publish_sync(live_mode_enabled) for fleet-wide mode shift; GET /agent/live-mode-guard audit log; create_operator_app gains bus=None kwarg
  bridge/vapi_bridge/session_adjudicator.py — _listen_live_mode_bus() subscribes live_mode_enabled; updates cfg.agent_dry_run_mode within <1ms; spawned in run_event_consumer() alongside other bus listeners
  bridge/vapi_bridge/ruling_enforcement_agent.py — _listen_live_mode_bus() subscribes live_mode_enabled; updates cfg.agent_dry_run_mode; spawned in run_event_consumer()
  bridge/vapi_bridge/store.py — live_mode_guard_log table + insert_live_mode_guard_log + get_live_mode_guard_log + schema (97, "live_mode_guard")
  bridge/vapi_bridge/bridge_agent.py — Tool #63 get_live_mode_guard_log (definition + handler)
  sdk/openapi.yaml — POST /agent/config + GET /agent/live-mode-guard paths; LiveModeGuardLog schema
  docs/vapi-whitepaper-v3.md §9.12 — Gated Live Mode Transition section (3-condition gate, bus broadcast, audit trail)
  bridge/tests/test_phase97_live_mode_guard.py — NEW (6 tests — docstring says 8, file has 8, net +6 after test_5 flex): table+methods; blocked:gate; blocked:cert; blocked:audit; approved; dry_run=true; GET; Tool #63. Bridge 1358→1364 (+6)
Phase 96 completed (Enforcement Readiness Certificate + W1 Fix):
  bridge/vapi_bridge/store.py — W1 SQL fix: get_activation_audit_summary() adds WHERE created_at >= ? filter on gate_attestations query; enforcement_certificates table (UNIQUE audit_hash) + insert_enforcement_certificate + get_latest_enforcement_certificate + schema (96, "enforcement_certificates")
  bridge/vapi_bridge/operator_api.py — POST /agent/enforcement-certificate (audit_hash+hmac_sig+expires_at) + GET /agent/enforcement-certificate (has_certificate+is_expired)
  bridge/vapi_bridge/config.py — enforcement_cert_ttl_s (ENFORCEMENT_CERT_TTL_S, 86400)
  bridge/vapi_bridge/bridge_agent.py — Tool #62 get_enforcement_certificate (definition + handler)
  sdk/vapi_sdk.py — EnforcementReadinessCertificate dataclass (__slots__: cert_id/audit_hash/hmac_sig/audit_valid/gate_attestation_count/issued_at/expires_at/has_certificate/is_expired/error); VAPITournamentGate.create_enforcement_certificate() + .get_enforcement_certificate() — never raise, return EnforcementReadinessCertificate
  sdk/openapi.yaml — v3.0.0-phase98; EnforcementCertificate + EnforcementCertificateStatus schemas; 2 /agent/enforcement-certificate paths
  docs/vapi-whitepaper-v3.md §9.11 — ERC section (W1 fix, construction formula, portability, SDK)
  bridge/tests/test_phase96_enforcement_cert.py — NEW (8 tests): W1 pre-readiness excluded; W1 post-readiness counted; insert+dedup; empty store; POST fields; GET fields; expired advisory; Tool #62. Bridge 1350→1358 (+8)
  sdk/tests/test_phase96_enforcement_cert_sdk.py — NEW (4 tests): ERC defaults; create parses; get parses; bad URL never raises. SDK 77→81 (+4)
  bridge/tests/test_phase95_activation_audit.py — test_5 updated: "predates" assertion removed (W1 fix changes error message to "No gate attestations on-chain yet" — semantically equivalent, audit_valid=False invariant preserved)
Phase 94 completed (Class J Reactive Triage Loop):
  bridge/vapi_bridge/session_adjudicator.py — _TriageRateBucket (1/hour default, W1: 1000-entry LRU cap prevents memory leak from synthetic device_ids); _get_triage_bucket(device_id); _listen_triage_bus() subscribes divergence_pattern_detected bus; _reactive_interrupt_triage(payload) fires _adjudicate_device_directly() if not rate-limited; was_deferred=1 logged for rate-limited; run_event_consumer() spawns triage bus listener alongside class_j listener
  bridge/vapi_bridge/store.py — escalation_ruling_log table (device_id/patterns/verdict/ruling_id/was_deferred/created_at) + idx_escalation_ruling_device + insert_escalation_ruling_log + get_escalation_ruling_log + schema version (94, "escalation_ruling_log")
  bridge/vapi_bridge/config.py — triage_reactive_rate_limit (TRIAGE_REACTIVE_RATE_LIMIT, default 1) + triage_reactive_window_seconds (TRIAGE_REACTIVE_WINDOW_SECONDS, default 3600.0)
  bridge/vapi_bridge/operator_api.py — GET /agent/escalation-ruling-log (device_id filter + limit + timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #60 get_escalation_ruling_log (definition + handler; uses inputs.get())
  sdk/openapi.yaml — v3.0.0-phase94; GET /agent/escalation-ruling-log path; EscalationRulingLog schema
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 94 paragraph: reactive triage loop design, W1 LRU cap, was_deferred=1 pattern, <15s end-to-end latency
  bridge/tests/test_phase94_triage_loop.py — NEW (6 tests): table exists; rate bucket limits; bucket resets; cap at 1000; endpoint returns entries; Tool #60. Bridge 1338→1344 (+6)
Phase 93 completed (Protocol Score Dashboard Integration):
  frontend/VAPIDashboard.jsx — NEW useProtocolIntelligence() hook (polls GET /agent/protocol-intelligence every 30s); NEW ProtocolHealthPanel component (circular score gauge 0-100 color-coded, 5-component percentage bars, READY/NOT READY indicator, bottleneck display, triage escalation badge); integrated into LIVE mode section as AccordionPanel. No backend changes. Bridge 1338 unchanged.
Phase 92 completed (Automated Live Mode Activation Pipeline):
  bridge/vapi_bridge/live_mode_activation_pipeline.py — NEW: LiveModeActivationPipeline (5-min poll; _check_and_record(event_type, operator_notes=None): reads get_latest_protocol_intelligence_report, derives blocking_conditions, inserts to live_mode_activation_log, returns readiness dict with recommended_action); run_poll_loop() never raises; advisory only (never auto-activates)
  bridge/vapi_bridge/store.py — live_mode_activation_log table (event_type/ready_for_live_mode/protocol_health_score/bottleneck/blocking_conditions/operator_notes/created_at) + insert_live_mode_activation_log + get_live_mode_activation_log + schema version (92, "live_mode_activation_log")
  bridge/vapi_bridge/config.py — activation_pipeline_enabled (ACTIVATION_PIPELINE_ENABLED, true)
  bridge/vapi_bridge/operator_api.py — POST /agent/request-activation (records operator intent, returns readiness) + GET /agent/activation-log (audit trail)
  bridge/vapi_bridge/bridge_agent.py — Tool #59 get_activation_log (definition + handler)
  bridge/vapi_bridge/main.py — Phase 92 wiring block: LiveModeActivationPipeline (guarded by activation_pipeline_enabled)
  sdk/openapi.yaml — v3.0.0-phase92 (bumped to phase94); POST /agent/request-activation + GET /agent/activation-log paths; ActivationReadiness + ActivationLog schemas
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 92 paragraph: tamper-evident audit trail, SQLite+on-chain sequence, advisory-only design
  bridge/tests/test_phase92_activation_pipeline.py — NEW (8 tests): table; check_and_record stores; not-ready without report; ready when score>=85; blocking conditions; operator notes; endpoint; Tool #59. Bridge 1330→1338 (+8)
Phase 91 completed (Divergence Triage Agent):
  bridge/vapi_bridge/divergence_triage_agent.py — NEW: DivergenceTriageAgent (5-min poll; queries ruling_validation_log for devices with divergence_reason≠"{}"; _triage_device() detects: ml_bot_cluster (≥2 class_j_ml_bot_risk=HIGH), cheat_cluster (≥1 hard_cheat_codes), enrollment_anomaly (≥3 enrollment_status≠eligible); escalated=1 on any threshold; store.insert_divergence_triage_report(); bus publish class_j_triage_escalated when escalated; triage_confidence_score exported for Phase 89 bonus)
  bridge/vapi_bridge/store.py — divergence_triage_reports table + insert_divergence_triage_report + get_divergence_triage_report + get_triage_confidence_score + schema version (91, "divergence_triage")
  bridge/vapi_bridge/config.py — divergence_triage_enabled (DIVERGENCE_TRIAGE_ENABLED, true)
  bridge/vapi_bridge/operator_api.py — GET /agent/triage-report (entries + escalated_count + clean_count + timestamp)
  bridge/vapi_bridge/bridge_agent.py — Tool #58 get_triage_report (definition + handler; uses inputs.get())
  bridge/vapi_bridge/main.py — Phase 91 block: DivergenceTriageAgent wired (guarded by divergence_triage_enabled)
  bridge/vapi_bridge/protocol_intelligence_agent.py — triage_confidence_score from get_divergence_triage_report applied as +5 bonus
  sdk/openapi.yaml — v3.0.0-phase91; GET /agent/triage-report path; TriageReport schema
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 91 paragraph: cross-session pattern detection, 3 escalation tiers, synergistic chain Phase 88→91→89
  bridge/tests/test_phase91_divergence_triage.py — NEW (8 tests): empty store; ml_bot_cluster detected; cheat_cluster detected; single J not escalated; insert+retrieve; endpoint escalations; protocol integration; Tool #58. Bridge 1322→1330 (+8)
Phase 90 completed (Shadow Enforcement Layer):
  bridge/vapi_bridge/ruling_enforcement_agent.py — Phase 90 shadow mode branch in _process_ruling_completed: if getattr(cfg, "enforcement_shadow_mode", False) → _shadow_block(); else → _enforce_block(). _shadow_block() reads warmup_attack_score, sets duration_s (24h/7d), calls store.insert_shadow_enforcement_log(); never calls PHGCredential.suspend()
  bridge/vapi_bridge/store.py — shadow_enforcement_log table (device_id/ruling_id/verdict/commitment_hash/would_have_suspended/duration_s/warmup_attack_score/created_at) + insert_shadow_enforcement_log + get_shadow_enforcement_log(device_id=None, limit=50) + get_shadow_enforcement_stats → {total_shadow_blocks, unique_devices, avg_duration_s, shadow_pass_rate} + schema version (90, "shadow_enforcement")
  bridge/vapi_bridge/config.py — enforcement_shadow_mode (ENFORCEMENT_SHADOW_MODE, false)
  bridge/vapi_bridge/operator_api.py — GET /agent/shadow-enforcement-log (shadow_mode_active + entries + stats + timestamp; uses time.time())
  bridge/vapi_bridge/bridge_agent.py — Tool #57 get_shadow_enforcement_log (definition + handler; uses inputs.get())
  bridge/vapi_bridge/protocol_intelligence_agent.py — shadow_pass_score from get_shadow_enforcement_stats applied as +5 bonus to protocol_health_score
  sdk/openapi.yaml — GET /agent/shadow-enforcement-log path; ShadowEnforcementLog schema
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 90 paragraph: shadow mode design, would_have_suspended invariant, false-positive validation workflow
  bridge/tests/test_phase90_shadow_enforcement.py — NEW (8 tests): config field; shadow block logs without chain; stats empty; pass_rate computed; endpoint returns entries; Phase 89 integration; gate isolation (summary["total"] not session_count); Tool #57. Bridge 1314→1322 (+8)
  bridge/tests/test_phase66_ruling_enforcement.py — _make_cfg() gains cfg.enforcement_shadow_mode=False (prevents MagicMock truthy attr from routing to shadow path in test_16 and test_30)
Phase 89 completed (Protocol Intelligence Synthesis Agent):
  bridge/vapi_bridge/protocol_intelligence_agent.py — NEW: ProtocolIntelligenceAgent (5-min poll + bus subscriber; compute_report() → 5-component score: 0.35·gate_progress + 0.25·fleet_health + 0.20·divergence_clarity + 0.10·corpus_pass + 0.10·class_j_confidence; Phase 90 shadow_pass_score +5 bonus; Phase 91 triage_confidence_score +5 bonus; capped at 100; ready_for_live_mode = score≥85 AND gate_passed AND fleet≠CRITICAL/UNKNOWN; bottleneck = lowest component; estimated_days_to_gate from session velocity; persists to protocol_intelligence_reports)
  bridge/vapi_bridge/store.py — protocol_intelligence_reports table (protocol_health_score/gate_progress_score/fleet_health_score/divergence_clarity_score/corpus_pass_score/class_j_confidence_score/shadow_pass_score/triage_confidence_score/ready_for_live_mode/bottleneck/estimated_days_to_gate/components_json/recommendation) + insert_protocol_intelligence_report + get_latest_protocol_intelligence_report + schema version (89, "protocol_intelligence")
  bridge/vapi_bridge/config.py — protocol_intelligence_enabled (PROTOCOL_INTELLIGENCE_ENABLED, true)
  bridge/vapi_bridge/operator_api.py — GET /agent/protocol-intelligence (latest stored report or live compute)
  bridge/vapi_bridge/bridge_agent.py — Tool #56 get_protocol_intelligence (definition + handler)
  bridge/vapi_bridge/main.py — Phase 89 block: ProtocolIntelligenceAgent wired (guarded by protocol_intelligence_enabled)
  sdk/openapi.yaml — v3.0.0-phase89; GET /agent/protocol-intelligence path; ProtocolIntelligenceReport schema
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 89 paragraph: formula, bottleneck field, synergistic bonus components
  bridge/tests/test_phase89_protocol_intelligence.py — NEW (8 tests): empty store zero score; gate progress reflected; fleet degraded lowers score; ready_for_live_mode false below threshold; bottleneck identifies lowest; estimated_days from velocity; endpoint returns required fields; Tool #56. Bridge 1306→1314 (+8)
Phase 88 completed (Adjudication Campaign Tracker + Divergence Instrumentation):
  bridge/vapi_bridge/store.py — ruling_validation_log ADD COLUMN divergence_reason TEXT (idempotent ALTER TABLE); insert_validation_record() gains divergence_reason:str|None kwarg; NEW get_campaign_status(gate_n, max_divergence_rate) → dict: consecutive_clean/gate_n/progress_pct/session_count/divergence_count/divergence_rate/gate_passed/estimated_sessions_to_gate/verdict_breakdown/divergence_breakdown/recent_sessions/last_session_at/campaign_note; schema version (88, "campaign_tracker")
  bridge/vapi_bridge/session_adjudicator_validator.py — NEW module-level _extract_divergence_fields(evidence:dict)→str: captures hard_cheat_codes/advisory_codes/class_j_ml_bot_risk(≠LOW)/ml_bot_candidate/ceremony_integrity_failed/enrollment_status(≠eligible)/risk_label; returns "{}" for fully nominal evidence (W1 mitigation: divergence reasons now visible to operators); _validate_ruling() computes divergence_reason and passes to insert_validation_record
  bridge/vapi_bridge/operator_api.py — NEW GET /agent/campaign-status: _check_key + _check_rate; calls store.get_campaign_status(gate_n, max_divergence_rate)
  bridge/vapi_bridge/bridge_agent.py — Tool #55 get_campaign_status: definition added before Tool #54; handler returns store.get_campaign_status(gate_n, max_divergence_rate)
  sdk/openapi.yaml — v3.0.0-phase88; GET /agent/campaign-status path; CampaignStatus schema (13 fields, atomic snapshot description)
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 88 paragraph: campaign tracker design, _extract_divergence_fields, estimated_sessions_to_gate formula, W1 atomic read mitigation
  bridge/tests/test_phase88_campaign_tracker.py — NEW (6 tests): empty store zero progress; 5 clean sessions counts; nominal evidence → "{}"; nonstandard signals captured; endpoint returns 12 required fields; Tool #55 returns dict. Bridge 1300→1306 (+6)
Phase 87 completed (GateAttestationAnchor On-Chain Publication):
  bridge/vapi_bridge/chain.py — NEW method record_gate_attestation_on_chain(attestation_hash_hex, consecutive_clean, gate_n, divergence_rate, timestamp_ns): inline ABI for GateAttestationAnchor.sol recordGateAttestation(bytes32,uint32,uint32,uint32,uint64); divergence_rate encoded as millis (int(rate*1000)); timestamp_ns to seconds (//1_000_000_000); 100k gas; raises RuntimeError on revert; W1 docstring: callers must pass SQLite-persisted hash, never recompute
  bridge/vapi_bridge/adjudication_warm_up.py — NEW async _anchor_gate_on_chain(chain): reads get_validation_summary, computes hash ONCE via compute_gate_attestation_hash, calls chain.record_gate_attestation_on_chain, then store.insert_gate_attestation(on_chain_tx=tx_hash); never raises; returns None on any failure. run_warm_up(chain=None) accepts optional chain kwarg; calls _anchor_gate_on_chain after batch; WarmUpReport gains on_chain_published:bool + on_chain_tx:str|None
  GateAttestationAnchor.sol LIVE: 0xA39d00D3FF8C579840Fa02C01Adf06162630a449 (IoTeX testnet, deployed 2026-03-20, operator verified)
  bridge/.env.testnet — GATE_ATTESTATION_ANCHOR_ADDRESS=0xA39d00D3FF8C579840Fa02C01Adf06162630a449
  contracts/deployed-addresses.json — GateAttestationAnchor address added
  sdk/openapi.yaml — v3.0.0-phase87
  docs/vapi-whitepaper-v3.md §7.5.8 — Phase 87 on-chain publication path + W1 invariant + LIVE contract address
  bridge/tests/test_phase87_gate_anchor.py — NEW (4 tests): compute_gate_attestation_hash deterministic/64-char; record_gate_attestation_on_chain millis conversion verified; anchor skipped when no address; anchor publishes+stores on_chain_tx. Bridge 1296→1300 (+4)
Phase 86 completed (Synthetic Session Corpus Pipeline):
  bridge/vapi_bridge/synthetic_session_generator.py — NEW: SyntheticSessionGenerator (seed-reproducible; generate_session() → {session_id, device_id, inference_code, humanity_score, evidence, evidence_json, created_at}; device_id="synthetic_<hex>"; evidence: enrollment_status="eligible" + empty hard_cheat_codes + advisory_codes → rule_fallback → CERTIFY); generate_corpus(n) → list
  bridge/vapi_bridge/validation_corpus_runner.py — NEW: ValidationCorpusRunner (cfg + store; run_corpus(n) async → {generated, passed_fallback, failed_fallback, all_nominal, duration_ms, corpus_run_id, corpus_size}; calls SessionAdjudicator._rule_fallback; stores in synthetic_sessions ONLY — never touches ruling_validation_log; W1 isolation invariant)
  store.py — synthetic_sessions table (UNIQUE session_id, INSERT OR IGNORE) + idx_synthetic_session_run + insert_synthetic_session + get_corpus_status (returns total/passed/failed/run_count/last_run_at/isolation_note) + schema version (86, "synthetic_corpus")
  config.py — synthetic_corpus_enabled (SYNTHETIC_CORPUS_ENABLED, false), synthetic_corpus_size (SYNTHETIC_CORPUS_SIZE, 120)
  operator_api.py — POST /agent/run-synthetic-corpus (triggers ValidationCorpusRunner, n override param) + GET /agent/corpus-status (returns CorpusStatus with isolation_note)
  bridge_agent.py — Tool #54 get_corpus_status (definition + handler)
  sdk/openapi.yaml — v3.0.0-phase86; POST /agent/run-synthetic-corpus + GET /agent/corpus-status paths; CorpusReport + CorpusStatus schemas
  docs/vapi-whitepaper-v3.md §9.9 — Synthetic corpus design, W1 isolation invariant, rule_fallback regression detection
  bridge/tests/test_phase86_synthetic_corpus.py — NEW (8 tests); Bridge 1288→1296 (+8)
Phase 85 completed (SDK v3.0.0 Tournament Operator):
  sdk/vapi_sdk.py — SDK_VERSION 2.0.0-phase64 → 3.0.0-phase85; VAPITournamentGate (wraps GET /agent/gate-readiness, returns GateReadinessResult, is_ready() bool, never raises); VAPICeremonyAudit (wraps VAPIZKProof.verify_ceremony_integrity(), returns CeremonyAuditResult, never raises); VAPIRulingStream (async generator, SSE consumer for /operator/agent/stream, Last-Event-ID reconnect W1 mitigation, exponential backoff 1-60s, CancelledError clean exit); RulingStreamEvent dataclass; CeremonyAuditResult dataclass; GateReadinessResult dataclass
  sdk/tests/test_phase85_tournament_sdk.py — NEW (10 tests): SDK version, GateReadinessResult defaults, bad URL error surface, is_ready() false on failure, mocked response parsing, CeremonyAuditResult defaults, VAPICeremonyAudit wraps VAPIZKProof, exception capture, SSE block parse, Last-Event-ID reconnect header
  sdk/openapi.yaml — v3.0.0-phase85; GateReadinessResult + CeremonyAuditResult + RulingStreamEvent schemas
  docs/vapi-whitepaper-v3.md §7.6 — SDK v3.0.0 Tournament Operator Interface (VAPITournamentGate + VAPICeremonyAudit + VAPIRulingStream design + CI pipeline example)
  SDK 63→73 (+10 tests)
Phase 84 completed (Live Mode Gate Completion + Adjudication Warm-Up):
  GateAttestationAnchor.sol — on-chain gate proof registry: recordGateAttestation(attestationHash, consecutiveClean, gateN, divergenceRateMillis, timestamp) anti-replay via unique attestationHash; getAttestation/getLatestAttestation/getAttestationCount; 4 Hardhat tests (GAA-1..4)
  contracts/scripts/deploy-gate-anchor.js — deploy script; outputs bridge/.env.phase84 + deployed-addresses.json GateAttestationAnchor
  adjudication_warm_up.py — AdjudicationWarmUpRunner: _get_recent_devices() selects N most recently active from agent_rulings; run_warm_up() calls session_adjudicator._adjudicate_device_directly() for each; WarmUpReport includes llm_available (W1) + fallback_count; compute_gate_attestation_hash() canonical SHA-256 formula
  store.py — gate_attestations table (UNIQUE attestation_hash, INSERT OR IGNORE idempotent) + idx_gate_attestation_created + 2 methods (insert_gate_attestation, get_gate_attestations) + schema version (84, "gate_attestation_anchor")
  config.py — gate_attestation_anchor_address (GATE_ATTESTATION_ANCHOR_ADDRESS), warm_up_batch_size (WARM_UP_BATCH_SIZE, default 5)
  operator_api.py — POST /agent/warm-up (trigger AdjudicationWarmUpRunner batch, batch_size override param) + GET /agent/gate-readiness (composite: validation_gate + fleet_health + gate_attestations_count + overall_ready + dry_run_active)
  bridge_agent.py — Tool #53 get_gate_readiness (definition + handler; returns overall_ready, validation_gate, fleet_health, gate_attestations_count)
  sdk/openapi.yaml — v3.0.0-phase84; POST /agent/warm-up + GET /agent/gate-readiness paths; WarmUpReport + GateReadiness schemas
  docs/vapi-whitepaper-v3.md §7.5.8 — Gate activation sequence (4-step: warm-up → gate-readiness → AGENT_DRY_RUN=false → on-chain anchor); GateAttestationAnchor.sol design; composite endpoint table; §7.5.8 renumbered BridgeAgent section to §7.5.9
  bridge/tests/test_phase84_live_mode_gate.py — NEW (6 tests); Bridge 1282→1288 (+6)
Phase 83 completed (AgentSupervisor Fleet Health Monitor):
  agent_supervisor.py — AgentSupervisor: 9-agent health monitor; _AGENT_CHECKS dict (table/ts_col/filter/device_col per agent); HEALTHY/STALE/UNKNOWN/ZOMBIE per-agent status; fleet_health ALL_HEALTHY/DEGRADED/CRITICAL; ZOMBIE = W1 distinct_device==0 loop detection; check_fleet_health() sync (safe for tests+REST); _check_and_report() async (publishes agent_health_report to bus + persists to store); run_supervisor_loop() 5-min poll
  store.py — supervisor_health_log table + idx_supervisor_health_agent + 3 methods (get_agent_activity, insert_supervisor_health_log, get_latest_supervisor_health) + schema version (83, "supervisor_health_log")
  config.py — supervisor_enabled (SUPERVISOR_ENABLED, True), supervisor_stale_threshold_minutes (SUPERVISOR_STALE_THRESHOLD_MINUTES, 15)
  operator_api.py — GET /agent/supervisor-status (instantiates AgentSupervisor, returns check_fleet_health snapshot)
  bridge_agent.py — Tool #52 get_agent_supervisor_status (definition + handler)
  main.py — Phase 83 block: AgentSupervisor wired (guarded by supervisor_enabled)
  sdk/openapi.yaml — v3.0.0-phase83; GET /agent/supervisor-status; AgentSupervisorStatus + AgentHealthResult schemas
  docs/vapi-whitepaper-v3.md §7.5.7 — AgentSupervisor section (fleet health table, ZOMBIE W1 mitigation, AGaaS SLA context)
  bridge/tests/test_phase83_supervisor.py — NEW (10 tests); Bridge 1272→1282 (+10)
Phase 82 completed (Reactive Adjudication Interrupt):
  session_adjudicator.py — _ReactiveAdjudicationBucket (token bucket, default max 2/60s, W1 mitigation); _listen_class_j_bus() (subscribes class_j_high_risk_detected, extracts payload from bus envelope, consume() gating, asyncio.ensure_future(_reactive_interrupt)); _reactive_interrupt() (never raises, logs to reactive_adjudication_log, publishes reactive_ruling_completed); _adjudicate_device_directly() (core ruling without event bookkeeping; used by reactive path; returns (verdict, ruling_id)); run_event_consumer() spawns both ceremony and class_j bus listeners; __init__ constructs _ReactiveAdjudicationBucket from config
  store.py — reactive_adjudication_log table + idx_reactive_adj_device + 2 methods (insert_reactive_adjudication_log, get_reactive_adjudication_log) + schema version (82, "reactive_adjudication_log")
  config.py — reactive_adjudication_rate_limit (REACTIVE_ADJUDICATION_RATE_LIMIT, default 2), reactive_adjudication_window_seconds (REACTIVE_ADJUDICATION_WINDOW_SECONDS, default 60)
  operator_api.py — GET /agent/reactive-adjudication-log (device_id filter, limit param, deferred_count)
  bridge_agent.py — Tool #51 get_reactive_adjudication_status (definition + handler)
  sdk/openapi.yaml — v3.0.0-phase82; GET /agent/reactive-adjudication-log; ReactiveAdjudicationLog + ReactiveAdjudicationEntry schemas
  docs/vapi-whitepaper-v3.md §7.5.6 — Phase 82 Reactive Adjudication Interrupt paragraph; bus topology updated; end-to-end latency <10s documented
  bridge/tests/test_phase82_reactive.py — NEW (8 tests); Bridge 1264→1272 (+8)
Phase 81 completed (ClassJDetector — ML-Bot Detection):
  class_j_detector.py — ClassJDetector: per-device deque of N=10 entropy windows; _temporal_state_transition_entropy_variance (0.0 for <2 windows; sample variance otherwise); _classify_risk: HIGH <=0.05, MEDIUM <=0.15, LOW >0.15; assess() never raises; bus publish class_j_high_risk_detected on HIGH; run_poll_loop 5-min cycle; pitl_session_proofs l4_features_json as entropy source
  session_adjudicator.py — _assess_class_j_risk() async method (never raises; None → LOW); _process_ruling_request() enriches evidence_summary with class_j_ml_bot_risk + class_j_entropy_variance; HIGH → ml_bot_candidate=True
  store.py — class_j_assessments table + index idx_class_j_device + 2 methods (insert_class_j_assessment, get_class_j_assessment) + schema version (81, "class_j_detection")
  config.py — class_j_detection_enabled (True), class_j_entropy_windows (10)
  bridge_agent.py — Tool #50 get_class_j_assessment (definition + handler)
  main.py — Phase 81 block: ClassJDetector wired (guarded by class_j_detection_enabled)
  sdk/openapi.yaml — v3.0.0-phase81 + ClassJAssessment schema
  docs/vapi-whitepaper-v3.md §9.6 — Class J analysis + per-layer detection rates + entropy discriminator
  bridge/tests/test_phase81_class_j.py — NEW (8 tests); Bridge 1256→1264 (+8)
Phase 80 completed (FederationBroadcastAgent + FederatedThreatRegistry.sol):
  federation_broadcast_agent.py — FederationBroadcastAgent: first purely event-driven agent (no polling); subscribes to ruling_block_committed; _recover_unbroadcast() on startup; HMAC-SHA256 X-Federation-HMAC auth; httpx async POST to peers; <100ms peer delivery
  contracts/contracts/FederatedThreatRegistry.sol — Phase 80 redesign: addThreatSignal/revokeThreatSignal/isThreatSignaled()/getThreatSignal(); per-ruling BLOCK signal; UNIQUE active-flag anti-replay; deviceSignalCount tracking; transferOperator
  contracts/scripts/deploy-federation-registry.js — deploy script
  contracts/test/FederatedThreatRegistry.test.js — 14 Hardhat tests (replaces 8 Phase 34 + 6 new = net +6)
  ruling_enforcement_agent.py — bus kwarg; publishes ruling_block_committed after successful on-chain BLOCK commit
  store.py — federation_threat_signals table (UNIQUE commitment_hash) + 4 methods (insert_threat_signal, mark_threat_signal_broadcast, get_unbroadcast_signals, get_federation_stats) + schema version (80, "federation_threat_signals")
  config.py — federation_broadcast_enabled, federation_broadcast_peers (CSV), federation_broadcast_api_key
  operator_api.py — POST /federation/threat-signal (HMAC validated) + GET /federation/peers
  bridge_agent.py — Tool #49 get_federation_status (definition + handler)
  main.py — Phase 80 block: FederationBroadcastAgent wired (guarded by federation_broadcast_enabled)
  sdk/openapi.yaml — Federation tag updated; POST /federation/threat-signal + GET /federation/peers; ThreatSignalPayload + FederationStatus schemas
  docs/vapi-whitepaper-v3.md §7.5.6 — FederationBroadcastAgent + 150x speedup + FederatedThreatRegistry.sol design
  bridge/tests/test_phase80_federation.py — NEW (9 tests); Bridge 1247→1256 (+9); Hardhat 398→404 (+6)
Phase 79 completed (AgentMessageBus + LiveModeActivationAgent):
  agent_message_bus.py — AgentMessageBus: asyncio.Queue per topic (maxsize=100); fan-out to multiple subscribers; QueueFull caught gracefully; publish_sync() for sync contexts; lock initialized lazily
  live_mode_activation_agent.py — LiveModeActivationAgent: 5-condition checklist; get_live_mode_status(); subscribes to dry_run_gate_passed via bus; 5-min fallback poll; advisory only (never auto-activates)
  ceremony_watchdog.py — bus kwarg; publish ceremony_key_rotated to bus (replaces direct _sa_mod._CEREMONY_CACHE.clear() module import)
  session_adjudicator.py — bus kwarg; _listen_ceremony_bus() subscribes to ceremony_key_rotated; clears own _CEREMONY_CACHE on receipt
  session_adjudicator_validator.py — bus kwarg; publishes dry_run_gate_passed to bus (in addition to SQLite write)
  store.py — live_mode_transitions table + count_operator_overrides + count_ceremony_key_rotations + schema version (79, "agent_message_bus_live_mode")
  config.py — live_mode_auto_candidate (False)
  operator_api.py — GET /agent/live-mode-status
  bridge_agent.py — Tool #48 get_live_mode_status (definition + handler)
  main.py — AgentMessageBus instantiation + _init_lock(); inject bus into 4 existing agents + wire LiveModeActivationAgent
  sdk/openapi.yaml — GET /agent/live-mode-status path; LiveModeStatus schema
  docs/vapi-whitepaper-v3.md §7.5.6 — AgentMessageBus architecture + event topology + LiveMode checklist
  bridge/tests/test_phase79_live_mode.py — NEW (8 tests); Bridge 1239→1247 (+8)
Phase 78 completed (Validation Gate Rate-Tolerance):
  store.py — get_validation_summary() extended: max_divergence_rate param; trailing gate_n window for divergence_rate (W1: pre-gate divergences do not permanently block); returns divergence_rate, divergence_rate_ok, max_divergence_rate, window_size; gate_passed = (consecutive_clean >= gate_n) AND divergence_rate_ok
  store.py — get_validation_gate_status() updated: rate-specific recommended_action branch when divergence_rate > max_divergence_rate
  config.py — validation_max_divergence_rate field (VALIDATION_MAX_DIVERGENCE_RATE env var, default 1.0 = no rate limit)
  operator_api.py — GET /agent/validation-gate passes max_divergence_rate to store
  bridge_agent.py — Tool #46 handler passes max_divergence_rate; consistent gate evaluation across all 3 gate-checking locations
  session_adjudicator_validator.py — gate check uses summary["gate_passed"] (incorporates both consecutive_clean AND divergence_rate)
  sdk/openapi.yaml — v3.0.0-phase78; ValidationGate schema extended with 4 new fields (divergence_rate, divergence_rate_ok, max_divergence_rate, window_size)
  docs/vapi-whitepaper-v3.md §7.5.5 — Phase 78 rate-tolerance paragraph added
  bridge/tests/test_phase78_gate_tolerance.py — NEW (4 tests)
  Bridge 1235→1239 (+4 tests)
Phase 77 completed (CI/CD expansion):
  .github/workflows/ci.yml — Hardhat matrix: Node 18+20; Bridge matrix: Python 3.11/3.12/3.13; new yaml-lint job (pyyaml validates openapi.yaml structure + version); fail-fast: false for all matrices
  README.md — 3 CI status badges (Bridge+SDK / Smart Contracts / OpenAPI Lint)
  Bridge: 1235 unchanged (CI config only — no new test code)
Phase 76 completed (code + tests):
  ruling_provenance_anchor_agent.py — RulingProvenanceAnchorAgent (5-min poll, LEFT JOIN for unanchored rulings, compute_provenance_hash: SHA-256(commitment|ceremony_canonical|evidence_canonical), canonical int() serialization (W1 mitigation), insert_provenance_anchor, optional on-chain publication via RULING_PROVENANCE_PUBLISH_ENABLED)
  store.py — ruling_provenance_anchors table (UNIQUE on ruling_id, INSERT OR IGNORE idempotent) + 2 methods (insert_provenance_anchor, get_provenance_anchor) + schema version (76, "ruling_provenance_anchors")
  config.py — 2 new fields: ruling_provenance_enabled (True), ruling_provenance_publish_enabled (False)
  operator_api.py — GET /agent/ruling-provenance/{ruling_id} endpoint
  bridge_agent.py — Tool #47 get_ruling_provenance (definition + handler)
  main.py — Phase 76 agent wiring: RulingProvenanceAnchorAgent (guarded by RULING_PROVENANCE_ENABLED)
  sdk/openapi.yaml — v3.0.0-phase76; GET /agent/ruling-provenance/{ruling_id} path; RulingProvenance schema
  docs/vapi-whitepaper-v3.md §7.5.5 — RulingProvenanceAnchorAgent paragraph + canonical formula
  bridge/tests/test_phase76_provenance.py — NEW (6 tests)
  Bridge 1229→1235 (+6 tests)
Phase 75 completed (code + tests):
  session_adjudicator_validator.py — SessionAdjudicatorValidationAgent (5-min poll, LEFT JOIN query for unvalidated rulings, _rule_fallback cross-validation, divergence = verdicts differ AND |conf_delta| > threshold, consecutive_clean gate tracking, dry_run_gate_passed event emission)
  ceremony_watchdog.py — CeremonyWatchdogAgent (5-min poll, beacon_block_number+contributor_count fingerprint, _CEREMONY_CACHE invalidation on rotation, ceremony_key_rotated event, FLAG escalation for last 10 min)
  store.py — ruling_validation_log table + 3 methods (insert_validation_record, get_validation_summary, get_validation_gate_status) + schema version (75, "validation_gate_watchdog")
  config.py — 3 new fields: validation_divergence_threshold (0.3), validation_gate_n (100), ceremony_watchdog_enabled (True)
  operator_api.py — GET /agent/validation-gate endpoint
  bridge_agent.py — Tool #46 get_validation_gate_status (definition + handler)
  main.py — Phase 75 agent wiring: SessionAdjudicatorValidationAgent (guarded by OPERATOR_API_KEY) + CeremonyWatchdogAgent (guarded by CEREMONY_WATCHDOG_ENABLED)
  sdk/openapi.yaml — v3.0.0-phase75; GET /agent/validation-gate path; ValidationGate schema
  docs/vapi-whitepaper-v3.md §7.5.5 — CeremonyWatchdogAgent + dry-run gate paragraphs added
  bridge/tests/test_phase75_agents.py — NEW (10 tests)
  Bridge 1219→1229 (+10 tests)
Phase 74 completed (deploy):
  Phase 69 contracts LIVE 2026-03-19:
    DataSovereigntyRegistry: 0xd928d95321Fff9b9003331082A8F6b75114793C9
    HumanityOracle:          0x84069312B5363Ef8ce6d1e2e312C4A1a8596a45d
    RulingOracle:            0xfA15e1f48B0BaC624C31E8F730713C3653Ee6E21
    PassportOracle:          0x7f8cE7B689Ad9bEC5D22C9F8Dc245eBD078e0917
    VAPIRewardDistributor:   0x8ae8B577684bf328B24C7a600D3Ba29A39d661A5
    VAPIDataMarketplace:     0x15D2Ac6d5802Bb8cBb8d3E35648385a7821630cC
  Phase 70 contracts LIVE 2026-03-19:
    VAPIGovernanceTimelock:  0x0a44Ff57D2aeA4Ee64Cdd8FC854306a887670a34
    VAPIProtocolLens:        0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf
  bridge/.env.testnet — merged Phase 68+69+70 addresses (31 contracts)
  deployed-addresses.json — updated _note/_status/_iotx_spent
  Wallet remaining: ~4.1 IOTX
Phase 73 completed (code + tests):
  session_adjudicator.py — _get_ceremony_integrity() async method (TTL cache 1h, never raises); _process_ruling_request() calls it before LLM; ceremony_integrity_failed=True in evidence on mismatch without error; ceremony_integrity JSON passed to insert_agent_ruling()
  store.py — ceremony_integrity TEXT column migration (idempotent ALTER TABLE); insert_agent_ruling() ceremony_integrity kwarg
  bridge/tests/test_phase73_enrichment.py — NEW (4 tests): ceremony match no flag / registry unreachable proceeds / mismatch flags failed / store accepts column
  docs/vapi-whitepaper-v3.md §7.5.5 — SessionAdjudicator Ceremony Integrity Enrichment paragraph added
  Bridge 1215→1219 (+4 tests)
Phase 72 completed (code + tests):
  store.py — pending_suspensions table + 4 methods (propose_suspension, confirm_suspension, get_suspension_proposal, mark_suspension_executed)
  config.py — suspension_multisig_threshold: int field (SUSPENSION_MULTISIG_THRESHOLD env var, default 1)
  operator_api.py — 3 new endpoints: POST /operator/suspension/propose, /confirm/{id}, /execute/{id}; create_operator_app signature adds chain= kwarg
  sdk/openapi.yaml — v3.0.0-phase72; Governance tag; 3 paths + SuspensionProposal schema
  docs/vapi-whitepaper-v3.md §9.8 — PHGCredential bridge-layer multi-sig section added (limitation honestly documented)
  bridge/tests/test_phase72_multisig.py — NEW (8 tests)
  Tournament Condition 3 CLOSED IN CODE (software safeguard, documented)
  Bridge 1207→1215 (+8 tests)
Phase 71 completed (code + tests):
  VAPIProtocolLens.sol M-1 fix — isEligible catch default changed true→false; oracleAvailable bool added to DeviceProtocolState struct; isFullyEligible() elig default true→false
  VAPIGovernanceTimelock.sol L-1 fix — require(_coSigner != address(0)) added to setCoSigner()
  contracts/contracts/test/MockRevertingRulingOracle.sol — new test helper for test_14
  contracts/test/Phase70Governance.test.js — +2 tests: test_13 (L-1 zero co-signer revert), test_14 (M-1 oracle failure fail-closed)
  docs/security-audit-phase-70.md — M-1 and L-1 marked FIXED with commit reference
  docs/vapi-whitepaper-v3.md §9.7 — oracle failure posture paragraph added (M-1 remediation)
  Hardhat 396→398 (+2 tests)
Phase 70 completed (code + tests):
  VAPIGovernanceTimelock.sol — 48h queued operator transitions for all Phase 69 contracts; co-signer cancel-only; CEI reentrancy safety; PHGCredential excluded
  VAPIProtocolLens.sol — pure-view single eth_call synthesizing HumanityOracle+RulingOracle+PassportOracle+VAPIRewardDistributor into DeviceProtocolState; isFullyEligible() tournament gate; all subcalls try/catch safe
  deploy-phase70.js — reads Phase 69 addresses, deploys both contracts, outputs bridge/.env.phase70
  main.py — Phase 70 agent wiring: DataCuratorAgent (run_poll_loop), SessionAdjudicator (run_event_consumer), RulingEnforcementAgent (run_event_consumer) all started as supervised asyncio tasks
  bridge_agent.py — BridgeAgent tools #41–45: get_data_lineage, get_token_eligibility, get_oracle_state (HUMANITY/RULING/PASSPORT allowlist), compute_reward_score, publish_sovereignty_pledge (event-queue pattern)
  operator_api.py — GET /agent/validation-stats endpoint (proof_stats, enrollment, curator_stats, ruling_stats)
  config.py — governance_timelock_address + protocol_lens_address fields
  sdk/openapi.yaml — v3.0.0-phase70, Curator tag, 4 curator paths, ValidationStats schema
  +21 bridge tests (+1207 total), +12 Hardhat tests (+396 total)
Phase 69 completed (code + tests):
  DataSovereigntyRegistry.sol — immutable on-chain data sovereignty pledge, 3-tier licensing (MANUFACTURER/DEVELOPER/GAMER)
  HumanityOracle.sol — native VAPI oracle, queryable by any IoTeX tournament contract
  RulingOracle.sol — native VAPI oracle wrapping RulingEnforcementAgent streak state
  PassportOracle.sol — native VAPI oracle wrapping PITLTournamentPassport state
  VAPIRewardDistributor.sol — device-gated DePIN token distributor (multiplier stack: 1.5×→2.0×→2.5×→1.25×→3.0×)
  VAPIDataMarketplace.sol — three-tier data licensing exchange (70% device pool / 30% treasury)
  DataCuratorAgent (Python) — 7-class taxonomy, lineage builder, eligibility engine, oracle publisher
  3 SQLite tables: data_lineage, oracle_publications, token_eligibility
  6 config fields: curator_enabled, curator_oracle_publish, *_oracle_address (4)
  4 chain.py oracle write methods: update_humanity/ruling/passport_oracle, publish_sovereignty_pledge
  4 REST endpoints: /curator/data-lineage, /curator/token-eligibility, /curator/oracle-state, /curator/publish-oracle
  BridgeAgent tools #41–45 planned (to be added in app.py/bridge_agent.py next session)
  SDK: sdk/vapi_data_curator.py (VAPIDataCurator client, 4 methods, never raises)
  Tests: +30 bridge, +12 Hardhat, +4 SDK
Phase 68 completed (all items):
  RulingRegistry deployed: `0xa3A2356C90E642a7c510d0C726EC515EA720c621` (LIVE)
  CeremonyRegistry deployed: `0x739B5fae312834bA2a7e44525bA5f54853C5672f` (LIVE — IoTeX beacon block #41723255)
  MPC ceremony complete: 3 circuits × 3 contributors, IoTeX block anchor, verifyCeremony() OK
  ZKVerifier wired into chain.py submit_pitl_proof() — rejects invalid proofs before gas spend
  SessionAdjudicator dry_run reads AGENT_DRY_RUN config; POST /agent/config runtime toggle
  BridgeAgent tools #36–40 added; config.pitl_vkey_path + config.agent_dry_run_mode



---

## Archived: Completed Items — Do Not Re-Open (Phase 17-67)

These items are historically closed. Full phase blocks above contain implementation detail.

## Completed Items — Do Not Re-Open

- Phase 67 MPC Ceremony Hardening — Phase 66 hotfix (correct store_credential_suspension arg order); credential_enforcement reinstated/reinstated_at columns + get_expired_suspensions + mark_suspension_reinstated; _check_expired_suspensions auto-reinstate loop; GET /agent/suspension-status; CeremonyRegistry.sol + run-mpc-ceremony.js + deploy-ceremony-registry.js; ZKVerifier (Node.js subprocess); chain.record_ceremony_on_chain(); config.ceremony_registry_address; VAPIZKProof.verify_ceremony_integrity(); openapi.yaml SuspensionStatus; 20 bridge + 8 Hardhat + 4 SDK tests; bridge 1126; Hardhat 372; SDK 59
- Phase 66 Ruling Enforcement Pipeline — ruling_streaks + on_chain_rulings tables; RulingEnforcementAgent (streak escalation, on-chain commit, credential suspend); RulingRegistry.sol + deploy script + 10 Hardhat tests; chain.record_ruling_on_chain(); POST /agent/override; BridgeAgent tools #34 + #35; 3 config fields; 30 bridge tests; bridge 1106; Hardhat 364
- Phase 65 Autonomous Intelligence Layer — agent_rulings table + 3 store methods; SessionAdjudicator (5-min poll, claude-opus-4-6, _rule_fallback); GET /agent/rulings/{device_id} + POST /agent/adjudicate + POST /agent/interpret; BridgeAgent tools #32 + #33; sdk/vapi_agent.py (VAPIAgent + AgentRuling, commitment_hash formula); BLOCK/CERTIFY attestation gate; dry_run=True default; Agent OpenAPI tag + 6 schemas; 20 bridge + 15 SDK tests; bridge 1076; SDK 55
- Phase 64 SDK Parity — SDK v2.0.0-phase64; 0x31/0x32 advisory codes; VAPIEnrollment + VAPIZKProof; L2B 5th self_verify layer; openapi.yaml Enrollment tag + YAML alias fix; SDK 40 tests
- Phase 63 L6b Neuromuscular Reflex — L6B_PROBE profile (id=8, sub-perceptual); L6bReflexAnalyzer; l6b_probe_log table; 5 config fields; 4-way humanity formula; pitl_meta l6b_* fields; BridgeAgent tool #31 get_reflex_baseline; 26 tests; bridge 1056
- Phase 62 Player Enrollment + ZK C3 — EnrollmentManager; device_enrollments table; GET /enrollment/status; BridgeAgent tool #30; PitlSessionProof.circom C3 + Poseidon(8) C1; mock proof inference binding; PITLSessionRegistryV2.sol; ceremony re-run; nPublic=5 preserved; +26 tests; bridge 1026
- Phase 61 Session Replay + Feature History Scatter — frame_checkpoints (SQLite, FK to records, maxlen=60 ring, INSERT OR IGNORE idempotent); _replay_ring deque 20 Hz; /replay + /checkpoints + /features; BridgeAgent tool #29; useReplayMode + useFeatureHistory; BiometricScatter cyan DB dots; chain tile ▶ indicator; replay status bar; 12 tests; bridge 1000
- Phase 60 My Controller Enhanced Visualization (60A) — BiometricRadar 12-spoke; L5RhythmOverlay CV+entropy+quant; BiometricScatter tremor×jitter 2D cross-section; ProofShareQR modal with IoTeX explorer deeplink; 4-tab left panel; qrcode npm dep; zero backend; bridge 988 unchanged
- Phase 59 My Controller 3D Digital Twin — physics-driven controller twin; get_ibi_snapshot(); /ws/twin/{device_id} fusion WS; /controller/twin/{id} REST; BridgeAgent tool #28; ControllerTwin.jsx (R3F + Rapier + Drei); IBI Biometric Heartbeat; PoAC DNA Helix; chain timeline scrubber; 16 tests; bridge 988
- Phase 58 Security Hardening — operator endpoint auth; sliding-window rate limiter; operator_audit_log; inference_code; BridgeAgent tools #24–27; 16 tests; bridge 972
- Phase 57 jitter variance — `press_timing_jitter_variance` (index 11) added to BiometricFeatureFrame; `_BIO_FEATURE_DIM` 11→12; IBI deque tracking (Cross/L2/R2/Triangle); static `_press_timing_jitter_variance()`; 5 new tests; bridge 956
- Phase 56 ZK Tournament Passport — TournamentPassport.circom + PITLTournamentPassport.sol + deploy script; tournament_passports table + 3 store methods; generate_tournament_passport BridgeAgent tool #23; POST /operator/passport; 5 new tests; bridge 951
- Phase 55 ioID Device Identity — VAPIioIDRegistry.sol + deploy script; ioid_devices table; DID in pitl_meta + WS; chain methods ensure_ioid_registered/ioid_increment_session; get_ioid_status tool #22; 5 new tests; bridge 946
- Phase 54 runtime hardening — numpy fallback ImportError fix; `_task_done_handler` CRITICAL on 11 tasks; chain nonce reset on send failure; WS 60s receive timeout; store migration log.debug; fetchSnapshot abort dedup; WS reconnect 5→60s backoff; 5 new tests; bridge 941
- Phase 53 serialization hardening — `_safe_val()` NaN/Inf→None on all WS float fields; `controller_registered` WS event; `_pending_pitl_meta` reset per loop; gas/revert error discrimination; 21 new tests; bridge 936
- Phase 52 runtime hardening — `_run_ds_with_restart()`; `pitl_meta=None` fix; WS broadcast logging; CORS `:5174`; `hardware_block` init False; CalibIntelAgent failure counter; batcher gas dead-letter extended; bridge 915
- Tremor FFT window widening (Phase 49) — 513→1025 ring buffer, 0.977 Hz/bin, 4 Phase 49 bridge tests, batch validator 7→9 features, Attack G batch still 0% (right_stick_x preserved), whitepaper §8.5 + feature table updated, bridge 888
- Professional bot adversarial data (Phase 48) — 3 white-box attack classes G/H/I, 15 sessions, 4 unit tests, validation script updated, analysis doc, whitepaper §9.5 added
- L2C phantom weight formula integrity fix (Phase 47) — PITL layer live status, log.debug, WS flag, §7.5.4, test_9, HUMANITY tile
- accel_magnitude_spectral_entropy as active feature at index 9 (Phase 46)
- L4 thresholds recalibrated N=74 (Phase 46)
- L6 human response baseline calibration (Phase 43)
- Full covariance L4 (Phase 41)
- ZK inference code binding / pub[2]=0 gap (Phase 41)
- IoTeX testnet deployment (13 contracts live)
- PoAC chain hash bug fix
- PHGCredential auto-expiry fix

