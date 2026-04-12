# VAPI WHAT_IF — For Claude Code Context

## Agent Identity: VAPI Master Expert

**You are Claude Code, the Architectural Infrastructure Creator of VAPI and an Expert across all domains comprising the VAPI ecosystem.**

**Your Expertise Profile**:
- **DePIN/Blockchain Architect**: IoTeX L1 integration, Solidity smart contract design, ZK proof systems (Groth16), on-chain verification, token economics, distributed consensus (ioSwarm), wallet management, MPC ceremonies
- **AI/ML/FL/AGI Engineer**: PITL stack (L0-L6) classification, behavioral ML for anti-cheat, federated learning threat correlation, Mahalanobis biometric analysis, temporal rhythm detection, humanoid bot classification, epistemic consensus protocols
- **IoT-Sensors-Electronics Engineer**: HID protocol implementation, sensor fusion (accelerometer/gyroscope), embedded firmware (C/Zephyr RTOS), real-time data acquisition, hardware calibration, BLE transport, power management, ATECC608A secure elements
- **Cryptographic Systems Engineer**: SHA-256/Poseidon hashing, ECDSA-P256 signatures, zero-knowledge circuits, Merkle proofs, device identity (ioID), credential lifecycle (VHP soulbound tokens)
- **Distributed Systems Architect**: Asyncio agent orchestration, SQLite WAL concurrency, MQTT/Mosquitto messaging, FastAPI bridge services, cross-bridge threat correlation, event-driven architectures
- **Anti-Cheat Systems Specialist**: Gaming anti-cheat protocols, wallhack/aimbot detection, injection detection (HID-XInput Oracle), tournament integrity, competitive gaming ecosystems
- **Firmware Engineer**: nRF9160 embedded development, Zephyr RTOS, sensor polling optimization, 228-byte PoAC record generation, power-efficient cryptography
- **Full-Stack Integration Engineer**: Python SDK design, OpenAPI client generation, dataclass/slot optimization, pytest automation, Hardhat contract testing

**Your Role**: When reading this file, you are the risk/opportunity analyst. You must think in three recursive layers: W1 (protocol risks), W2 (novel opportunities), W3 (meta-risks to the system itself). Every proposal must be grounded, exclusive to VAPI, and phase-coherent.

> **INSTRUCTION TO CLAUDE CODE**: This file is the recursive risk/opportunity ontology for VAPI.
> When reading this file, you must:
> 1. Check W1_LAYER before proposing features (avoid known failure modes)
> 2. Reference W2_LAYER for novel opportunities (build on validated ideas)
> 3. Monitor W3_LAYER for meta-risks (protect the protection system)
> 4. Add new entries with evidence and phase candidates
> 5. Never delete entries — append-only with status updates

---

## Layer Structure

VAPI WHAT_IF operates in three recursive layers:

- **W1_LAYER**: Risks to the VAPI protocol (failure modes)
- **W2_LAYER**: Opportunities for VAPI enhancement (novel features)
- **W3_LAYER**: Meta-risks (risks to the risk system itself)

**Recursion**: W3 protects W1/W2, W1/W2 advance the protocol, protocol state feeds W3 monitoring.

---

## W1_LAYER: Known Failure Modes

> **INSTRUCTION**: Before proposing any feature, check if it addresses or respects these failure modes.

### W1-001: ioSwarm Node-Pool Homogeneity (Phase 110)

**Failure Mode**: MINT_QUORUM=0.80 trivially satisfied if all 5 nodes operated by same entity, collapsing distributed consensus to 1-party signature.

**Implication**:
- Soulbound VHP tokens minted without genuine distributed authorization
- Swarm fingerprint (SHA-256 of node_verdicts) cryptographically valid but economically meaningless
- Fail-CLOSED direction preserved, but distributed guarantee voided
- Indistinguishable from legitimate quorum on-chain

**Detection**:
- All 5 node staker_addresses identical or controlled by same entity
- Swarm fingerprint shows self-consistency, not distributed consensus
- No way to detect from on-chain data alone

**Mitigation Available**:
- ✅ VAPISwarmOperatorGate.sol: enforces minimum 3 distinct staker addresses in node pool
- ✅ Stake-weight cap: 1.5× per node prevents whale capture
- ✅ Phase 112 candidate: isSufficientlyDecentralized() as additive 5th gate on POST /agent/mint-vhp

**Status**: Code complete, deployment **BLOCKED** (wallet ~0.35 IOTX < 0.40 needed)

**Evidence**: scripts/vapi-vhp-mint-swarm-agent.json (task spec)

**First Identified**: Phase 109A (2026-03-15)

**Claude Code Guidance**: When working on ioSwarm, always check node diversity. Never enable minting without VAPISwarmOperatorGate validation.

---

### W1-002: Separation Ratio Calibration Deadline (Phase 108/129)

**Failure Mode**: Inter-person separation ratio remains <1.0 through Phase 113 if touchpad recapture hardware session indefinitely deferred.

**Implication**:
- TOURNAMENT BLOCKER persists (ratio > 1.0 is non-negotiable TGE gate)
- All 4 tournament readiness conditions unmet
- VHP minting proceeds on testnet but live tournament integration impossible
- Token launch blocked regardless of ioSwarm phase completion

**Current State**:
- Full corpus pooled: 0.417 (N=127, 3-player, 2026-03-29) — BLOCKER for free-form gameplay
- Touchpad corners (Phase 143): **1.261** (N=11, diagonal+proper LOO, 3-player, 2026-04-02) — ABOVE GATE
- Sessions captured: N=120 included (5 excluded), 3 players; P4→P3 merge confirmed (Phase 138)
- BT calibration: 0/50 sessions (separate workstream)

**Detection**:
- separation_ratio_snapshots table: touchpad_corners now logs 1.261
- 6-signal tournament readiness score: separation component now partially passing (touchpad_corners)
- Full corpus free-form still below 1.0 (0.417)

**Mitigation Available**:
- ✅ Touchpad corners already above gate (N=11 thin but real data, 3 players)
- ✅ Tournament path: capture ~19 more touchpad_corners sessions to reach N≥30
- ✅ Phase 143 proper LOO + Phase 142 diagonal auto-fallback produce honest estimate
- ⚠️ Free-form gameplay separation (0.417) still requires new probe types or players

**Status**: PARTIALLY RESOLVED — touchpad_corners ABOVE GATE (1.261, N=11 thin); free-form still BLOCKER (0.417)

**Evidence**: touchpad_corners N=11 (P1=3/P2=4/P3=4), diagonal covariance, proper LOO (Phase 143)
Previous W1-002 full corpus estimate: N=177 corpus, pooled=0.417

**First Identified**: Phase 108 (2026-03-10)
**Breakthrough Achieved**: Phase 143 (2026-04-02) — touchpad_corners 1.261

**Claude Code Guidance**: Touchpad-specific sessions are the tournament path. Any new capture should be touchpad_corners or touchpad_freeform (ratio=1.270). Free-form bulk sessions do not improve separation meaningfully.

---

### W1-003: L4 Threshold Staleness (Phase 123)

**Failure Mode**: Feature dimension drift (12→13) applies stale thresholds to live 13-dimensional space, degrading L4 precision silently.

**Mechanism**:
- Phase 121: touchpad_spatial_entropy added (index 12)
- Old thresholds: calibrated on 12 dimensions (Phase 46)
- Application: 12-dim threshold on 13-dim data = partial feature ignorance
- Result: False positives/negatives increase silently

**Detection**:
- l4_calibration_log staleness flag: live_feature_dim (13) ≠ calibration_feature_dim (12)
- Unexpected L4 anomaly rates
- Mahalanobis scores drifting from historical baselines

**Mitigation Available**:
- ✅ Phase 123: Staleness detection (stale=True flag in logs)
- ✅ Automatic recalibration suggestion when stale=True
- ✅ Per-battery threshold tracks (Phase 124) enable granular updates
- ✅ Recalibration via Phase 134 pipeline

**Status**: DETECTED — stale=True (calib_dim=12 vs live_dim=13). NOTE: Phase 134 pipeline confirmed thresholds 7.009/5.367 are numerically correct even with dim mismatch because touchpad_spatial_entropy is structurally 0 in gameplay sessions (non-touchpad games). L4 thresholds remain valid for gameplay.

**Evidence**: calibration_feature_dim=12, live_feature_dim=13 in logs

**First Identified**: Phase 123 (2026-03-22)

**Claude Code Guidance**: Always check staleness before trusting L4 scores. Stale thresholds are WRONG even if mathematically computed.

---

### W1-004: BT Transport Threshold Pollution (Phase 120)

**Failure Mode**: USB-calibrated thresholds (1000 Hz) applied to BT sessions (250 Hz), causing false L4 positives.

**Mechanism**:
- USB: ~1000 samples/window (50ms coverage)
- BT: ~250 samples/window (200ms coverage)
- Human micro-tremor (8-12 Hz) completes more cycles per window at BT rates
- Gyro_std variance artificially elevated → higher Mahalanobis distance

**Current State**:
- BT_L4_ANOMALY_THRESHOLD: 7.009 (mirrors USB — WRONG)
- BT sessions captured: 0/50 minimum
- BT calibration: NOT DONE

**Mitigation Available**:
- ✅ Separate BT calibration required (N≥50 sessions)
- ✅ Per-battery threshold tracks enable BT-specific values
- ✅ BT transport detection in session metadata
- ⚠️ BT transport currently disabled (bt_transport_enabled=False)

**Status**: ACKNOWLEDGED — BT calibration separate workstream, not tournament-blocking

**Evidence**: bluetooth-threshold-analysis.md (structural difference documented)

**First Identified**: Phase 120 (2026-03-18)

**Claude Code Guidance**: Never enable BT transport without N≥50 calibration. USB and BT thresholds are structurally incompatible.

---

### W1-005: Confidence Multiplier Penalty (Phase 122)

**Failure Mode**: bt_strat_ratio as VHP confidence multiplier penalizes non-touchpad sessions (ratio=0.0 → confidence=0.0).

**Mechanism**:
- Touchpad-dominant sessions: bt_strat_ratio > 0
- No-touchpad sessions: bt_strat_ratio = 0
- Multiplier: confidence_score *= max(floor, min(1.0, bt_strat_ratio))
- Result: No-touchpad sessions get near-zero confidence

**Current State**:
- confidence_multiplier_enabled: False (default, safety)
- confidence_multiplier_floor: 0.0
- Per-battery lookup: Not yet implemented

**Mitigation Available**:
- ✅ Disabled by default (no penalty applied)
- ✅ Per-battery multiplier lookup candidate (Phase 124+)
- ✅ Advisory-only mode (never hard-gate)

**Status**: MITIGATED (disabled, not removed)

**Evidence**: l4_calibration_log shows touchpad vs non-touchpad stratification

**First Identified**: Phase 122 (2026-03-20)

**Claude Code Guidance**: If enabling confidence multiplier, implement per-battery lookup first. Never apply uniform multiplier across battery types.

---

### W1-006: Wallet Funding Exhaustion (Ongoing)

**Failure Mode**: Bridge wallet (~0.35 IOTX) insufficient for contract deployments, blocking Phase 130B+ on-chain progress.

**Requirements**:
- Current: ~0.35 IOTX
- VAPISwarmOperatorGate.sol: ~0.13 IOTX
- Total needed: ~0.40 IOTX
- Shortfall: ~0.05 IOTX

**Impact**:
- Phase 130B deployment BLOCKED
- ioSwarm live node registration blocked
- Tournament operator gate incomplete

**Mitigation**:
- Faucet request or bridge funding required
- Non-critical path for Tikhonov breakthrough
- Critical path for full tournament deployment

**Status**: BLOCKING on-chain work, not blocking analysis

**Claude Code Guidance**: Check wallet balance before proposing any contract deployment. Faucet funding is a prerequisite for on-chain phases.

---

### W1-007: Corpus Imbalance Covariance Bias (Phase 137A — CONFIRMED)

**Failure Mode**: Player 1's 53 sessions (vs P2=34, P3=33) dominate global covariance matrix, artificially suppressing inter-player distances and deflating pooled separation ratio.

**Mechanism**:
- Pooled covariance estimated from combined N=120 sessions
- P1 contributes 53/120 = 44% of samples → P1 eigenspace dominates
- P2/P3 distances measured against P1-biased covariance → compressed
- Result: pooled ratio 0.417 vs balanced ratio 1.611 (n=3/player seed=42, Phase 137A)

**Evidence**:
- Phase 137A balanced corpus: ratio=1.611 (n=3/player N=12) vs pooled=0.417 (N=127)
- WIF-007 confirmed: 4× inflation/deflation depending on analysis method

**Mitigation Available**:
- ✅ --balance-corpus flag in analyze_interperson_separation.py (Phase 137A)
- ✅ Balanced analysis: min(N_per_player) sessions per player (seed=42)
- ✅ Session-type filter (--session-type touchpad_corners) + proper LOO (Phase 143)

**Status**: CONFIRMED — mitigated by Phase 142/143 diagonal+LOO method; pooled ratio misleading

**First Identified**: Phase 137A (2026-03-30)

**Claude Code Guidance**: Never report pooled ratio as sole metric. Always include balanced or per-probe-type ratio. Pooled 0.417 reflects corpus imbalance, not human biometric distinctiveness.

---

### W1-008: Touchpad Coverage Asymmetry and Thin N (Phase 140/143)

**Failure Mode**: Separation ratio breakthroughs are measured on N=11 touchpad_corners sessions — legally thin for tournament deployment and statistically fragile to single-session outliers.

**Mechanism**:
- N=11 (P1=3, P2=4, P3=4) is below the N≥30 threshold for defensible tournament claims
- Proper LOO (Phase 143) reduces effective centroid training set to N-1 per test
- With P1 having only 3 sessions: P1 centroid from N=2 sessions when testing 3rd P1 session
- Adding 1 unusual session could shift ratio significantly

**Evidence**:
- Phase 143: 7/11 correct (63.6%), 4 misclassified — not tournament-robust at N=11
- Phase 140 probe comparison: corners=1.552, freeform=1.270, swipes=1.032 (all >1.0 but vary significantly)

**Mitigation Available**:
- ✅ Target N≥30 touchpad_corners (need ~19 more mixed across P1/P2/P3)
- ✅ All 3 probe types above 1.0 — multiple verification paths
- ⚠️ No mitigation for thin N — must capture more sessions

**Status**: ACKNOWLEDGED — thin N is the #1 remaining gap for tournament readiness

**First Identified**: Phase 143 (2026-04-02)

**Claude Code Guidance**: Do not claim tournament readiness on N=11 alone. Separation breakthrough is real but requires session reinforcement before legal deployment.

---

### W1-009: Free-Form Gameplay Separation Plateau (Phase 137B — CONFIRMED)

**Failure Mode**: Free-form NCAA CFB 26 gameplay sessions plateau at separation ratio 0.417 regardless of N, because variable gameplay states introduce session-to-session variance exceeding inter-player signal.

**Mechanism**:
- Free-form gameplay: player changes game state (defense/offense/menus) mid-session
- Session features average over heterogeneous states → high intra-player variance
- Touchpad unused during most gameplay → touchpad_spatial_entropy = 0 structurally
- Result: signal drowns in within-session noise; more sessions don't help

**Evidence**:
- Phase 137B: free-form sessions = ratio ~0.417 regardless of N
- Phase 140: swipes=1.032 (marginal) vs corners=1.261 (clear) — structured probes win

**Mitigation Available**:
- ✅ Structured probe sessions (touchpad_corners/freeform/swipes) instead of bulk gameplay
- ✅ Probe comparison now automated via --probe-comparison flag (Phase 140)
- ✅ Fast-path analysis skips bulk gameplay sessions (Phase 139)

**Status**: CONFIRMED — free-form gameplay is NOT the separation path; structured touchpad probes required

**First Identified**: Phase 137B (2026-03-30)

**Claude Code Guidance**: Never recommend "capture more gameplay sessions" to improve separation ratio. Recommend structured touchpad probe sessions. This is the single most important lesson from Phases 137-143.

---

### W1-010: ACIM Single-Validator Risk (Phase 148)

**Failure Mode**: Single AgentCalibrationIntegrityMonitor (ACIM) as the sole validator of calibration invariants creates a single point of failure — if ACIM miscalibrates or becomes compromised, no other agent catches it.

**Mechanism**:
- ACIM (Agent #18) runs 16 self-tests every 15 minutes
- Self-tests validate other agents' invariants
- But ACIM itself has no external validator — it reports on itself
- Compromised ACIM could report false health across entire fleet

**Mitigation Available**:
- ✅ Phase 148 design: ACIM cross-validates each agent independently (W1 anti-single-validator)
- ✅ 16 self-tests run against actual runtime state, not cached values
- ✅ `agent_calibration_health` table logged separately from agent runtime state
- ✅ Knowledge server (vapi-knowledge MCP) reads ACIM health as external check
- ⚠️ No separate watchdog validates ACIM itself — Phase 150 candidate

**Status**: MITIGATED (Phase 148 cross-validation design) — but ACIM self-validation gap remains open

**First Identified**: Phase 148 (2026-04-03)

**Claude Code Guidance**: When ACIM reports healthy, treat as strong signal but not absolute proof. External MCP query of ACIM health provides independent verification path.

---

### W1-011: Defensibility Gate Passes Prematurely via Session Type Mixing (Phase 150)

**Failure Mode**: The separation_defensibility_log defensibility check applies min_n_per_player=10 per session_type, but an operator could mix session types (touchpad_corners + freeform + swipes) to inflate N-count past threshold while never achieving a clean single-type separation proof.

**Mechanism**:
- `get_separation_defensibility_status(session_type=None)` returns the latest row regardless of session type
- If an operator inserts a mixed-type snapshot (session_type="all") with n_per_player={"P1": 12, "P2": 11, "P3": 11}, defensible=True is stored
- But individual session types may still have thin N (corners N=11, freeform N=11, swipes N=11)
- The ratio for mixed sessions (0.417 pooled free-form) is not the ratio for touchpad_corners (1.261)
- Result: defensible=True displayed for a session_type="all" snapshot that conflates incomparable ratios

**Evidence**:
- Phase 140 probe comparison: corners=1.261, freeform=1.270, swipes=1.032 — very different ratios by type
- Phase 143: proper LOO on touchpad_corners specific = honest 63.6% (7/11); mixed-type LOO would be misleading
- Free-form gameplay sessions have ratio=0.417 — including them in a defensibility check inflates n but deflates ratio

**Mitigation Available**:
- ✅ Phase 150 INSERT always includes session_type field — operators must specify type explicitly
- ✅ Tool #106 and endpoint accept `session_type` param — defaults to "touchpad_corners" (the honest type)
- ✅ `analyze_interperson_separation.py --session-consistency --session-type touchpad_corners` enforces type purity
- ✅ **Phase 151 CLOSED**: Store.STRUCTURED_PROBE_TYPES frozenset enforced at insert time; ValueError on 'gameplay' / any non-structured type; insert_separation_defensibility_log raises W1-011 error before DB write

**Status**: CLOSED (Phase 151, 2026-04-03) — ValueError on invalid session_type; 'gameplay' and free-form types permanently rejected; only touchpad_corners / touchpad_freeform / touchpad_swipes accepted

**First Identified**: Phase 150 (2026-04-03)

**Claude Code Guidance**: When reporting defensibility status, always specify session_type="touchpad_corners" explicitly. Never query session_type=None for tournament-facing decisions. The honest touchpad_corners N=11 defensible=False state is correct; any defensible=True report must cite the specific session_type and N-count.

---

## W2_LAYER: Novel Opportunities

> **INSTRUCTION**: Build on these opportunities. Each requires exclusivity argument (why VAPI-only).

### W2-001: Proof of Adjudication (PoAd) as Composable Primitive (Phase 111)

**Opportunity**: Second on-chain primitive enabling tournament contracts to verify clean adjudication history alongside isFullyEligible().

**Mechanism**:
1. PoAd_hash = SHA-256(sorted(node_verdicts_json) + quorum_str + ts_ns_str)
2. AdjudicationRegistry.sol stores per-cycle digests
3. hasCleanAdjudicationHistory(deviceId, lookback_days) query
4. Tournament integrators choose: isFullyEligible() OR hasCleanAdjudicationHistory() OR both

**Current State**:
- PoAdAnchorAgent: Active (60-sec cycle)
- AdjudicationRegistry.sol: Deployed (Phase 111)
- PoAd on-chain: Enabled for testnet

**Exclusivity**:
- No competitor has distributed per-device adjudication records
- Presupposes ioSwarm node_verdicts anchored to PoAC chain integrity (SHA-256(raw[:164]) + 228B format)
- Only valid because PoAC is already anchored

**Phase Candidate**: Phase 111 (COMPLETE), Phase 112 (integration)

**Dependencies**: ioSwarm node_verdicts on-chain (Phase 110)

**First Identified**: wif_1774484928.md (2026-03-27)

**Claude Code Guidance**: Promote PoAd as differentiator for tournament integrators. Two primitives > one primitive.

---

### W2-002: SeparationRatioRegistry.sol (Phase 112 Candidate)

**Opportunity**: On-chain immutable audit trail of each separation ratio measurement, anchored to calibration session hash and player count.

**Mechanism**:
1. separation_ratio_commitment = SHA-256(ratio_str + N_sessions + player_ids_sorted + ts_ns)
2. Operator signature on IoTeX L1
3. Cryptographic proof that ratio > 1.0 confirmed empirically before TGE
4. Legally defensible sequencing compliance

**Use Case**:
- Tournament regulators audit ratio measurement
- Token launch legal defense ("we proved human differentiation")
- Whitepaper reproducibility (on-chain evidence)

**Exclusivity**:
- VAPI's Mahalanobis inter-person distance metric is only calibrated biometric separation measure in anti-cheat
- No competitor has separation ratio as token launch gate
- 177-session hardware corpus is unique dataset

**Phase Candidate**: Phase 150+ (post-N≥30 touchpad_corners verification — N=11 currently thin)

**Dependencies**: Touchpad_corners N≥30 yielding ratio > 1.0 confirmed with statistical confidence

**First Identified**: wif_1774484928.md (2026-03-27)

**Claude Code Guidance**: Prepare contract spec now. Deploy immediately after Tikhonov confirms >1.0.

---

### W2-003: Tikhonov Auto-Detection at N>150 (Phase 137 Candidate)

**Opportunity**: Automatic --full-covariance when corpus exceeds stability threshold.

**Mechanism**:
1. analyze_interperson_separation.py detects N>150 automatically
2. Switches from --diagonal (fast) to --full-covariance (precise)
3. Applies Tikhonov regularization for numerical stability
4. Updates confidence intervals based on method precision

**Benefits**:
- No operator decision required (automatic precision upgrade)
- Large corpora get full analysis without manual flag
- Measurement imprecision reduced as N grows

**Exclusivity**:
- VAPI's 177-session hardware corpus is only anti-cheat dataset with N>150
- Tikhonov regularization requires specific feature correlation structure (VAPI-specific)
- No competitor has longitudinal hardware calibration data

**Phase Candidate**: PARTIALLY ADDRESSED — Phase 142 COV_MIN_RATIO=3.0 auto-fallback implements automatic diagonal vs full covariance switching; remaining opportunity is N-threshold auto-upgrade to recommend structured probe sessions

**Dependencies**: Phase 142 complete (diagonal auto-fallback); Phase 143 complete (proper LOO); remaining: automated probe-type recommendation when N/p < threshold

**First Identified**: VAPI_MEMORY.md 2026-03-20 entry

**Claude Code Guidance**: Implement as default behavior for N>150. Log method used for reproducibility.

---

### W2-004: Private Calibration Beta (Phase 137 Candidate)

**Opportunity**: Invite-only calibration program for trusted players to accelerate separation ratio improvement.

**Mechanism**:
1. Beta client with enhanced session capture (more metadata)
2. Trusted player cohort (N=10-20 players, not just 3)
3. Dedicated hardware loaners (DualShock Edge)
4. Direct feedback loop: session → analysis → threshold update

**Benefits**:
- Faster calibration than public beta
- Higher-quality data (dedicated hardware, consistent setup)
- Player incentive alignment (early VHP eligibility)

**Exclusivity**:
- VAPI's hardware-rooted approach requires physical controller
- No competitor can replicate without DualShock Edge integration
- Beta infrastructure (enrollment, credentialing) already exists

**Phase Candidate**: Phase 137 (post-TGE preparation)

**Dependencies**: Tournament readiness (separation > 1.0)

**First Identified**: wif_1774484928.md (2026-03-27)

**Claude Code Guidance**: Design beta infrastructure now. Deploy after TGE to accelerate ecosystem growth.

---

### W2-005: Multi-Controller Ecosystem (Phase 136 Candidate)

**Opportunity**: VAPI becomes the universal hardware authenticator for competitive gaming, supporting Xbox, Switch, and third-party controllers alongside DualShock Edge.

**Mechanism**:
1. ControllerHardwareIntelligenceAgent (Agent #17) maps capabilities to PITL layers
2. Controller profiles (YAML) define feature matrices per device
3. Tier eligibility: Attested (L0-L6 full) vs Standard (L0-L5 partial)
4. Per-controller calibration tracks (composite key: profile+battery+transport)
5. PHCI certification program for hardware partners

**Benefits**:
- 3× addressable market (Xbox + Switch + PC gamepad users)
- Tournament organizers can support all major controllers
- PHCI certification generates revenue
- VAPI becomes industry standard for hardware attestation

**Exclusivity**:
- No competitor supports hardware-rooted attestation across controller brands
- VAPI's PITL stack is uniquely adaptable to partial feature sets
- Controller-agnostic PoAC format (228-byte) works with any HID device
- No competitor has 177-session hardware corpus for calibration reference

**Phase Candidate**: Phase 150+ (Agent #17 DESIGN ONLY — no code written as of Phase 149)

**Dependencies**: 
- Agent #17 implementation (ControllerHardwareIntelligenceAgent)
- N≥50 calibration per new controller type (Xbox, Switch)
- PHCI certification API
- Note: Phase 143 touchpad_corners breakthrough confirms touchpad is the key discriminator → PHCI certification should require touchpad probe sessions as certification gate

**First Identified**: Phase 135 (2026-03-29)

**Claude Code Guidance**: Promote VAPI as the "Universal Authenticator" for gaming hardware. Touchpad spatial entropy (touchpad_spatial_entropy) is the key multi-player discriminator — PHCI certification must require touchpad-capable hardware.

---

### W2-006: MCP Corpus Auto-Sync via SessionStart Hook (Phase 150 Candidate)

**Opportunity**: Use Claude Code SessionStart hook to automatically re-read VAPI-WORKFLOW.v2 corpus files at session start, ensuring knowledge_server.py always loads current invariants without manual restart.

**Mechanism**:
1. `.claude/settings.json` SessionStart hook triggers `python vapi-mcp/knowledge_server.py --reload`
2. knowledge_server.py re-parses all 9 VAPI-WORKFLOW.v2 files
3. Stale invariants (separation ratio, threshold values, phase number) auto-updated in MCP context
4. Claude Code session opens with guaranteed current corpus state
5. Zero-config for operator — automatic invariant freshness

**Why VAPI-Only**:
- VAPI's corpus files are the ground truth for 9 specialized knowledge domains
- No other protocol has a dual MCP server architecture (live-state + corpus-enforcer)
- Auto-sync closes the session-restart gap that causes stale invariant violations

**Phase Candidate**: Phase 150 (~1 day effort: SessionStart hook + knowledge_server reload endpoint)

**Dependencies**: MCP servers running (post-restart activation complete)

**First Identified**: This session (2026-04-03)

**Claude Code Guidance**: When configuring hooks in settings.json, add SessionStart type to trigger corpus reload. This converts VAPI-WORKFLOW.v2 files from static reads to live truth.

---

### W2-007: Per-Player Touchpad Eigenspace as Tournament Identity Anchor (Phase 151 Candidate)

**Opportunity**: Each player's touchpad_corners session cluster defines a personal eigenspace (touchpad position + entropy + variance pattern) that serves as a cryptographic biometric anchor for tournament identity — complementing GSR grip (L7) with a hardware-agnostic touchpad fingerprint.

**Mechanism**:
1. Per-player centroid in 3D touchpad feature space (touch_position_variance, touchpad_spatial_entropy, micro_tremor interaction)
2. Store centroid as ZK-committed biometric anchor: `H(player_id || touchpad_centroid_quantized || ts)`
3. Tournament check: "Is this session within 2σ of enrolled centroid?" (Mahalanobis distance on touchpad features)
4. Phase 143 result shows: P1/P2/P3 have stable cluster centers (intra-mean 2.963/1.976/1.711)
5. Cluster stability = biometric distinctiveness without needing full PITL stack

**Why VAPI-Only**:
- Only VAPI has 11 labeled touchpad_corners sessions across 3 players with validated separation
- Touchpad eigenspace requires DualShock Edge touchpad (1000 Hz, 16-bit) — not available on Xbox/Switch
- Complements existing 228-byte PoAC without changing wire format (touchpad features already in L4 features)

**Phase Candidate**: Phase 151 (~2 weeks: enrollment pipeline + centroid store + ZK-committed anchor)

**Dependencies**: 
- N≥30 touchpad_corners sessions first (currently N=11)
- Per-player enrollment quality report (Phase 144 foundation ready)
- ZK consent system (BP-002 from privacy roadmap)

**First Identified**: Phase 143 analysis (2026-04-02)

**Claude Code Guidance**: When P3 touchpad cluster is tight (intra-mean=1.711) and P1 vs P3 distance=3.276 in diagonal space, that gap is exploitable as a biometric anchor. This is the most promising near-term biometric differentiation feature.

---

### W1-012: On-Chain Ratio Commitment Before N Reaches Defensible Threshold (Phase 152)

**Failure Mode**: Committing ratio=1.261 N=11 to SeparationRatioRegistry.sol creates permanent underpowered legal liability before N reaches defensible threshold (min_n=10/player). Tournament regulators reading `isRatioRecorded(ratioHash)` on-chain see a committed ratio>1.0 without the N-count context. Cannot un-commit once anchored. This inverts the defensibility gate that Phase 150/151 built.

**Evidence**:
- Phase 150 defensibility gate: defensible=False when any player < min_n=10 (current P1=3/P2=4/P3=4)
- W2-002 (SeparationRatioRegistry.sol) candidate notes: "Deploy immediately after Tikhonov confirms >1.0" — but "legally defensible" requires N≥10/player, not just ratio>1.0
- Phase 151 whitelist closes session_type mixing; does NOT fix N thinness

**Mitigation**:
- ✅ Gate SeparationRatioRegistry.sol commit behind `defensible=True` (Phase 150 gate: all players ≥ min_n AND ratio>1.0 AND all_pairs_above_1)
- ✅ Include `n_per_player_json` and `all_n_met` boolean in on-chain commitment
- ✅ Current state: defensible=False → commit naturally blocked; safe to deploy contract infrastructure
- Record `min_n_per_player` and `n_sessions_total` in on-chain struct for auditor transparency

**Status**: MITIGATED BY DESIGN — deploy contract; commit only after defensible=True fires

**First Identified**: Phase 152 planning (2026-04-03)

**Claude Code Guidance**: SeparationRatioRegistry.sol can be deployed NOW (infrastructure-first). The commit transaction must only fire when defensible=True. Bridge code must read separation_defensibility_log.defensible before calling chain.record_separation_ratio(). Never commit at ratio>1.0 alone — defensible=True is the stronger gate.

---

### W1-013: Capture Stagnation Trap — Silent Infinite ETA (Phase 153)

**Failure Mode**: If all players stop capturing touchpad_corners sessions, the enrollment gap (19 sessions) will never close. The bridge has no stagnation detector — `get_enrollment_capture_guidance()` reports a gap but never fires an alert if capture rate is zero for days/weeks. The TournamentActivationChainAgent (#16) will never progress without a stagnation signal.

**Evidence**:
- Phase 151 enrollment_capture_guidance: sessions_needed_total=19 with no velocity tracking
- No mechanism exists to detect when last insertion was >N days ago per player per probe
- SeparationRatioMonitorAgent (#15) polls separation_ratio_snapshots but does not detect capture stagnation

**Mitigation**:
- ✅ Phase 153 candidate: CaptureStagnationMonitorAgent (agent #19) polls defensibility log for per-player last-insertion timestamps; fires stagnation alert after STAGNATION_ALERT_DAYS (default 7)
- ✅ `capture_stagnation_log` table tracks per-player per-probe last_seen_ts + days_stagnant + alert_fired

**Status**: OPEN — no stagnation detection exists

**First Identified**: Phase 152 planning (2026-04-03)

**Claude Code Guidance**: When checking tournament readiness, always check days_since_last_capture per player per probe type. A defensibility gap of 19 sessions with zero capture velocity is a tournament-blocking condition. Stagnation alert should feed TournamentActivationChainAgent.

---

### W2-012: Per-Player Centroid Velocity as Biometric Identity Anchor Oracle (Phase 152)

**Opportunity**: As players accumulate touchpad_corners sessions, their per-player centroid in touchpad feature space converges. Tracking δ(centroid) per new session provides a software-only "biometric identity anchor ready" signal that feeds the Phase 135 TournamentActivationChainAgent — no new hardware required.

**Mechanism**:
1. For each player, compute centroid from all available touchpad_corners defensibility records (touch_position_variance, touchpad_spatial_entropy, micro_tremor cluster means stored in n_per_player_json)
2. Track δ = Euclidean distance between centroid(n) and centroid(n-1) per new insertion
3. When ALL players' δ < 0.01 for ≥3 consecutive snapshots → centroid_stable=True
4. `centroid_stability_log` table persists per-player convergence history
5. GET /agent/touchpad-centroid-stability (players / stable_count / sessions_needed / all_stable)
6. TournamentActivationChainAgent reads centroid_stable as a new activation condition

**Why VAPI-Only**:
- Presupposes Phase 143 diagonal Mahalanobis feature space (touchpad_spatial_entropy at dim 12)
- Presupposes Phase 151 whitelist integrity (only structured probe types enter defensibility log)
- Presupposes Phase 150 per-player N tracking (n_per_player_json is the centroid data source)
- No competitor has labeled per-player touchpad sessions + Mahalanobis separation infrastructure

**Phase Candidate**: Phase 152 (~3h: centroid_velocity_log table + store methods + GET endpoint + Tool #108 + SDK CentroidStabilityResult)

**Dependencies**: Phase 150 (n_per_player_json in defensibility log), Phase 151 (whitelist integrity)

**First Identified**: Phase 152 planning (2026-04-03)

**Claude Code Guidance**: The centroid is computed from n_per_player_json fields across all defensibility log entries for a given player+probe_type pair. This is a DB-only computation — no new calibration sessions required. Centroid stability is a leading indicator that eigenspace (W2-007) will be reliable when N reaches min_n.

---

### W2-013: SeparationRatioRegistry.sol as Cryptographic Proof-of-Calibration for Token Launch Sequencing (Phase 153)

**Opportunity**: Once defensible=True fires (all players ≥ min_n=10, ratio>1.0, all_pairs_above_1), commit the ratio measurement to SeparationRatioRegistry.sol as immutable on-chain proof. This creates a cryptographically verifiable audit trail for the token launch sequencing gate — legally defensible evidence that human differentiation was confirmed before TGE.

**Mechanism**:
1. `ratio_commitment = SHA-256(ratio_str + ":" + str(N_sessions) + ":" + sorted_player_ids_joined + ":" + str(ts_ns))` — FROZEN formula
2. SeparationRatioRegistry.sol: `recordRatioMeasurement(bytes32 commitment, uint32 nSessions, uint32 minNPerPlayer, bool allNMet, uint32 ratioMillis)` onlyOwner; UNIQUE anti-replay on commitment; `isRatioRecorded(bytes32) view`; `getLatestRatio() view`
3. Bridge commits only when separation_defensibility_log.defensible=True (W1-012 mitigation)
4. VAPIProtocolLens can query SeparationRatioRegistry to verify separation_proof_on_chain for tournament gate composability

**Why VAPI-Only**:
- No competing protocol has per-player biometric separation ratio as a token launch gate
- 228-byte PoAC corpus (N=177) is unique dataset; ratio measurement is VAPI-specific
- Composability with isFullyEligible() via VAPIProtocolLens is unique VAPI architectural property

**Phase Candidate**: Phase 153 (~4h: SeparationRatioRegistry.sol + deploy script + 6 Hardhat tests + bridge + SDK)

**Dependencies**: W1-012 mitigation (defensible=True gate; currently defensible=False — deploy infrastructure now, commit after N≥10/player)

**First Identified**: Phase 152 planning (2026-04-03)

**Claude Code Guidance**: Deploy SeparationRatioRegistry.sol immediately. Wire bridge to commit only after defensible=True. This converts the Phase 150/151 defensibility gate into a blockchain-anchored proof-of-human-differentiation. The ratio commitment is immutable — it will stand as tournament launch evidence.

---

## W3_LAYER: Meta-Risks (Risks to the Risk System)

> **INSTRUCTION**: These risks threaten the WHAT_IF system itself. Monitor continuously.

### W3-001: WHAT_IF Corpus Contamination

**Meta-Risk**: AutoResearch loop proposes WHAT_IF entries that are:
- Physically implausible (violates W1 grounded requirement)
- Duplicate of existing entry (corpus bloat)
- Mislabeled W1/W2 (wrong category)

**Implication**:
- Risk ontology degrades
- Future cycles reference invalid risks
- Decision quality declines

**Detection**:
- Manual audit of new WHAT_IF entries
- Fuzzy matching against existing entries
- W1 groundedness check (physically/cryptographically/economically)

**Mitigation**:
- ✅ Eval harness WHAT_IF quality criteria (W1_CRITERIA, W2_CRITERIA)
- ✅ Minimum 0.20 weight in scoring
- ✅ Mandatory "First identified" timestamp and evidence field
- ✅ Human review of W3 additions (meta-meta-risk)

**Status**: MONITORING — no contamination detected

**First Identified**: This document (2026-03-29)

---

### W3-002: AutoResearch Invariant Violation Proposal

**Meta-Risk**: Loop proposes change to VAPI_INVARIANTS.md or violates invariant in implementation.

**Implication**:
- Cascading failure across firmware↔bridge↔contract
- System incompatibility
- 228-byte format corruption

**Detection**:
- Eval harness invariant check (instant fail if ANY missing)
- Golden hash verification in VAPI_INVARIANTS.md footer
- Parse and verify before ANY proposal generation

**Mitigation**:
- ✅ VAPI_INVARIANTS.md read-only (file system permissions)
- ✅ Pre-flight SHA-256 check
- ✅ Explicit invariant checklist in cycle prompt template
- ✅ 30% scoring weight on invariants_preserved

**Status**: PROTECTED — no violations to date

**First Identified**: This document (2026-03-29)

---

### W3-003: Claude Context Window Truncation

**Meta-Risk**: Long sessions exceed context window; critical invariants "forgotten" by prompt truncation.

**Implication**:
- Late-session proposals may violate invariants
- W1/W2 entries proposed without proper grounding
- Agent expertise lost from context

**Detection**:
- Monitoring token usage (Claude Code shows remaining context)
- Invariant presence check in generated proposals
- Proposal quality degradation over session length

**Mitigation**:
- ✅ VAPI_INVARIANTS.md as explicit file read (not context-dependent)
- ✅ Short cycle length (1 improvement per cycle, not 5)
- ✅ Mid-session invariant re-injection prompt
- ✅ File-based context (not just conversation history)

**Status**: MONITORING — use short cycles

**First Identified**: This document (2026-03-29)

---

### W3-004: Expert Agent Consensus Failure

**Meta-Risk**: Parallel expert agents disagree on proposal; epistemic weighting fails.

**Implication**:
- No consensus reached
- System deadlocks or makes arbitrary decision
- Human operator escalation required repeatedly

**Detection**:
- Cross-agent vote divergence > 0.30
- Low confidence scores across all agents
- HOLD decisions with no clear path forward

**Mitigation**:
- ✅ Explicit epistemic weighting: {0.35, 0.35, 0.30} for 3-agent votes
- ✅ Tie-breaking: HOLD (no change) over aggressive change
- ✅ Escalation to human operator on HOLD×2
- ✅ Consensus timeout (fail to HOLD after 3 rounds)

**Status**: THEORETICAL — not yet triggered

**First Identified**: This document (2026-03-29)

---

### W3-005: Corpus Evidence Degradation

**Meta-Risk**: Session files corrupted, deleted, or modified; forensic integrity lost.

**Implication**:
- Tournament legal defense compromised
- Whitepaper reproducibility violated
- 177-session corpus value destroyed

**Detection**:
- Periodic SHA-256 verification of session files
- Corpus hash (Merkle root) comparison
- Backup integrity checks

**Mitigation**:
- ✅ VAPI_CORPUS.md with integrity hashes
- ✅ Multiple backup locations (local, cloud, git LFS)
- ✅ Append-only retention (no deletions)
- ✅ Legal hold status for tournament evidence

**Status**: PROTECTED — integrity verified on [date]

**First Identified**: This document (2026-03-29)

---

## Corpus Evolution Rules

### Entry Requirements

**W1 additions**:
- Require: Evidence of failure mode OR theoretical grounding
- Must: Specify physically/cryptographically/economically grounded mechanism
- Must: Include detection method
- Must: Include mitigation (even if "none yet")

**W2 additions**:
- Require: Exclusivity argument (why VAPI-only)
- Must: Specify phase candidate
- Must: Include mechanism description
- Must: Show dependency chain

**W3 additions**:
- Require: Recursive justification (risk to risk system)
- Must: Show how it threatens W1/W2 integrity
- Must: Include detection method for meta-risk
- Must: Include mitigation (often process-based)

### Status Transitions

```
OPEN → MITIGATED → CLOSED (with phase number)
  ↓
HYPOTHESIS (pending verification)
  ↓
CONFIRMED / REJECTED
```

**Never delete**: All entries preserved for historical audit.

---

---

## WIF-011 — Session Type Mixing Integrity Gap (Phase 151 formal closure)

**W1 — Failure mode**: Free-form gameplay sessions passed to `insert_separation_defensibility_log` contaminate the structured probe analysis, inflating or deflating defensibility status.
  Implication: Pre-Phase 151 code allowed any `session_type` into the defensibility gate; a `gameplay` session with random touchpad activity would be counted as contributing to the touchpad_corners enrollment gate.
  Mitigation: CLOSED Phase 151. `STRUCTURED_PROBE_TYPES` frozenset `{touchpad_corners, touchpad_freeform, touchpad_swipes}` enforced in `insert_separation_defensibility_log` — raises `ValueError` on any invalid session_type.
  **Status**: CLOSED (Phase 151)

**W2 — Structured probe corpus as the canonical tournament biometric evidence trail.**
  Mechanism: All enrolled sessions in `STRUCTURED_PROBE_TYPES` are SHA-256 committed via `SeparationRatioRegistry.sol` (Phase 153). Downstream tournament contracts can verify: "These N sessions of type touchpad_corners, from these players, produced ratio=1.261." Full audit trail from probe capture to on-chain commitment.
  Phase candidate: Phase 153 COMPLETE (registry code-complete; deploy deferred — wallet).

---

## WIF-012 — Enrollment Count-Gate Without Quality Gate (Phase 157 candidate)

**W1 — Failure mode**: `enrollment_complete` bus event fires when `sessions_needed_total == 0` without requiring `defensible=True` from `separation_defensibility_log`.
  Implication: Adversary captures exactly `min_n_per_player` sessions of any type (not necessarily defensible), satisfying the count-gate and triggering TournamentActivationChainAgent without achieving separation ratio > 1.0. The activation chain is breached without tournament-viable biometric separation.
  Cryptographic grounding: `defensible=True` requires SHA-256-committed ratio > 1.0 via `SeparationRatioRegistry.sol`. Count-gate bypass is economically motivated (VHP mint → tournament entry → prize eligibility).
  Mitigation (Phase 157): Dual-condition enforcement in `EnrollmentAutoGuidanceAgent._compute_overall_ready()`:
  ```python
  overall_ready = (sessions_needed_total == 0) AND (defensible == True)
  ```
  **Status**: OPEN — Phase 157 candidate. Filed 2026-04-04.

**W2 — Dual-condition enrollment_complete as enforceable tournament entry contract.**
  Mechanism: When `overall_ready` requires both count AND defensibility, the `enrollment_complete` bus event becomes a legally enforceable signal: "This player has N sessions AND separation ratio > 1.0 with defensive coverage." Tournament operators can rely on it as a single composable gate.
  Phase candidate: Phase 157, ~2h effort.

---

## WIF-013 — Fleet Consensus Snapshot (PoFC) as Third Composable Proof Primitive (Phase 157 candidate)

**W2 — Opportunity**: Agent #21 FleetConsensusSnapshotAgent computes SHA-256(sorted(agent_verdicts) + separation_ratio + ts_ns) = "Proof of Fleet Consensus" (PoFC), creating the composable triple: PoAC + PoAd + PoFC.
  Mechanism:
  - Agent #21 polls all 20 agents on 1h schedule, collects their last verdict
  - SHA-256(sorted(verdicts) + ratio + ts_ns) = PoFC hash
  - Stored in `fleet_consensus_snapshot_log`, anchored via `SeparationRatioRegistry.sol` pattern
  - GET /agent/fleet-consensus-snapshot exposes current PoFC
  - Tournament contracts can require: `isFullyEligible() AND isRecorded(poadHash) AND isFleetConsensus(pfcHash)` — triple-proof gate
  Exclusive because: requires VAPI's 20-agent fleet + PoAC (Phase 1 frozen) + PoAd (Phase 111) already deployed. No competing gaming DePIN protocol has this composable triple.
  Phase candidate: Phase 157, ~2h effort.

**W1 — Single-epoch fleet snapshot could be weakened by coordinated agent delay.**
  Implication: If all 20 agents are polled simultaneously and a malicious operator controls the clock, they could stall certain agents to exclude their verdicts from the PoFC hash.
  Mitigation: Use `ts_ns` per individual agent verdict (not just snapshot time); include each agent's last-verdict timestamp in the hash input. Byzantine fault tolerance: require 16/20 agents present before computing PoFC.

---

## WIF-014 — Class K Synthetic EDA Generator: Feature-Level Bypass of L7 GSR (Phase 158 candidate)

**W1 — Failure mode**: Adversary injects synthetic EDA signals into the BLE GSR packet stream, producing plausible SCR morphology that passes all four L7 feature checks (sympathetic_arousal_index, gsr_game_event_correlation, baseline_conductance_drift, cognitive_load_variance). L7 advisory code 0x33 GSR_CORRELATION_ABSENT never fires because correlation IS present — with synthetic data.
  Implication: Current 48-byte GSR packet format (magic 0x47535201) contains no HMAC field; BLE broadcast is unauthenticated. The Class K adversary is economically motivated (VHP mint → tournament entry). MockGSRGrip source code doubles as a Class K attack blueprint — $15 ESP32-S3 + BLE advertisement injection is sufficient.
  Cryptographic grounding: No cryptographic commitment exists on the current GSR packet. Packet injection requires only BLE advertisement spoofing + knowledge of MockGSRGrip morphology parameters.
  Mitigation (Phase 158): Extend GSR packet from 48B to 80B (+32B HMAC-SHA256). ESP32-S3 signs each batch with ATECC608A device private key. certLevel=2 in VAPIHardwareCertRegistry records HMAC public key. Bridge validates HMAC before L7 feature extraction; rejects unsigned packets with 0x33 advisory at WARNING.
  **Status**: OPEN — Phase 158 candidate. Filed 2026-04-04 (AutoResearch cycle 5).

**W2 — Hardware-Bound GSR Proof (PoHBG) as Fourth Composable Proof Primitive.**
  Mechanism: PoHBG_hash = SHA-256(sorted_samples + ts_ns + device_pubkey_hash_bytes32). Composable quadruple: PoAC + PoAd + PoFC + PoHBG. Shifts GSR from advisory signal (0x33) to cryptographically hardware-bound proof. Phase 158, ~4h effort.
  Exclusive because: requires certLevel=2 VAPIHardwareCertRegistry (Phase 99A LIVE) + GSRRegistryAgent (Phase 99B) + 20-agent fleet + PoAC + PoAd + PoFC. No competing gaming DePIN protocol has hardware-attested biometric composable proof.

---

## WIF-016 — Covariance Regime Instability at N~24 Transition Point (Phase 157 candidate)

**W1 — Failure mode**: Legitimate touchpad_corners enrollment growth from N=11 to N=24 crosses Phase 142 COV_MIN_RATIO=3.0 threshold (N/p = 24/8 = 3.0), triggering silent covariance regime switch that collapses P1/P3 distance from 3.276 to ~0.127 — invalidating tournament eligibility without any fraudulent sessions.
  Implication: get_separation_defensibility_status() re-evaluates dynamically. An N/p crossing event at N=24 causes defensible=True to flip to defensible=False with no visible root cause. Adversary exploit: capture 3 sessions targeting a competitor's enrollment, push their N/p to exactly 3.0, collapse their separation ratio.
  Cryptographic grounding: Phase 153 SeparationRatioRegistry commits ratio on-chain at N=11. Live re-evaluation at N=24 disagrees — verifiable on-chain/off-chain inconsistency. Economically motivated: tournament exclusion of a competitor has direct prize-pool benefit.
  Mitigation (Phase 157): COV_STABILITY_MARGIN_NP=0.5 check in get_separation_defensibility_status(); COVARIANCE_TRANSITION_WARNING flag; EnrollmentAutoGuidanceAgent urgency HIGH when in transition zone. Resolution: stay diagonal OR grow to N/p ≥ 5.0 (N ≥ 40/player).
  **Status**: OPEN — Phase 157 candidate. Filed 2026-04-04 (AutoResearch cycle 6).

**W2 — Adaptive Covariance-Aware Probe Sequencing in EnrollmentAutoGuidanceAgent.**
  Mechanism: cov_regime_status field ("diagonal_stable" / "transition_warning" / "full_covariance_active"); recommended_action adapts to covariance transition zone. Prevents blind enrollment growth into instability zone. Phase 157, ~2h effort. First biometric enrollment system with Mahalanobis covariance-regime-aware enrollment sequencing.

---

## WIF-018 — Biometric Data Used After Consent Revocation: No Gate in Defensibility Pipeline (Phase 160 candidate)

**W1 — Failure mode**: `insert_separation_defensibility_log` accepts structured probe sessions for any device regardless of consent status. A player who revokes consent (GDPR Art.7) or requests erasure (GDPR Art.17) can still have new biometric sessions inserted into the separation defensibility log.

**Implication**: Phase 151 STRUCTURED_PROBE_TYPES whitelist enforces session type purity but does NOT check consent. `BiometricPrivacyComplianceAgent` (Phase 159) tracks decay but has no consent query interface. No consent ledger → no processing lawfulness audit trail → regulatory exposure for tournament operators.

**Cryptographic grounding**: GDPR Art.9 (special category biometric data) + Art.7(3) (withdrawal as easy as giving) + Art.17 (erasure without undue delay). Tournament operators face €20M or 4% global revenue fines for unlawful biometric processing after consent revocation.

**Mitigation (Phase 160)**: `consent_ledger` table + `insert_separation_defensibility_log` consent guard + `anonymize_device_records()` + `right_to_erasure_log` table.

**Status**: OPEN — Phase 160 candidate. Filed 2026-04-04 (AutoResearch cycle 7).

---

## WIF-019 — Consent Ledger as Composable Privacy Primitive (Phase 160 candidate)

**W2 — Opportunity**: `get_consent_status(device_id)` as a queryable bridge primitive enabling every data-writing agent to check consent before storing biometric records. Composable gate: `consent_given AND defensible AND decay_factor > 0.25` = full privacy-compliant enrollment gate.

**Mechanism**: `consent_ledger` table + `right_to_erasure_log` + `get_consent_status()` store method + `POST /agent/register-consent` + `POST /agent/revoke-consent` + `GET /agent/consent-status/{device_id}` + Tool #117 + `ConsentLedgerResult` SDK.

**Exclusive because**: Requires Phase 151 STRUCTURED_PROBE_TYPES whitelist + Phase 159 BiometricPrivacyComplianceAgent (BP-001) + Phase 150 separation defensibility gate. No competing gaming DePIN protocol has per-device biometric consent as a queryable primitive composable with on-chain separation ratio registry.

**Phase candidate**: Phase 160 (~3h effort).

**Status**: NEW — Phase 160 candidate. Filed 2026-04-04 (AutoResearch cycle 7).

---

## WIF-020 — GDPR Art.17 Erasure Gap: ruling_validation_log Not Covered (Phase 161)

**W1 — Failure mode**: Phase 160 `anonymize_device_records()` only redacts `agent_rulings`
(`evidence_json` + `reasoning`). `ruling_validation_log.divergence_reason` contains biometric
inference reasoning per device (`llm_verdict`/`fallback_verdict`/`divergence_reason`), all of which
constitute "personal biometric data" under GDPR Art.9. After a GDPR Art.17 erasure request,
`ruling_validation_log` rows remain unredacted.

**Implication**: Regulatory exposure identical to WIF-018. Erasure appears complete (`agent_rulings`
redacted) but biometric evidence trail survives in `ruling_validation_log`. Phase 160 closes the
most visible gap but leaves a secondary audit trail. Security auditors performing GDPR compliance
review will find `divergence_reason` entries post-erasure.

**Cryptographic grounding**: GDPR Art.9 + Art.17. `ruling_validation_log` rows contain `device_id`,
`llm_verdict`, `fallback_verdict`, and `divergence_reason` (a JSON string of non-nominal biometric
evidence fields). This constitutes a biometric inference chain linkable to the data subject via
`device_id`.

**Mitigation (Phase 161)**: Extend `anonymize_device_records()` to also:
```python
UPDATE ruling_validation_log
SET divergence_reason='[redacted - GDPR Art.17 erasure]'
WHERE device_id=?
```

**Status**: CLOSED (Phase 161). Filed 2026-04-04 (AutoResearch cycle 8).

---

**W2 — Comprehensive erasure coverage as compliance signal for tournament operators.**

**Mechanism**: `get_erasure_log()` return includes `fields_anonymized` across BOTH `agent_rulings`
AND `ruling_validation_log`. Operator audit report shows complete GDPR Art.17 coverage. Composable
with Phase 160 consent ledger for defensible regulatory paper trail.

**Phase candidate**: Phase 161 (bundled with WIF-018 closure).

---

## WIF-021 — Consent-Unaware Separation Corpus: Revoked Devices Contribute to Defensibility Analysis (Phase 162)

**W1 — Failure mode**: `insert_separation_defensibility_log()` operates at corpus level (no
`device_id` parameter); `get_enrollment_capture_guidance()` and
`scripts/analyze_interperson_separation.py` do not filter revoked-consent players from the corpus
before computing separation ratio. A player who revokes consent continues to contribute biometric
sessions to the defensibility gate.

**Implication**: Corpus contamination from GDPR-revoked devices produces legally indefensible
separation ratio attestations on `SeparationRatioRegistry.sol`. Tournament operator relies on
ratio > 1.0 signal that includes data from revoked participants. Downstream court challenge:
"Player X revoked consent on date D; your ratio includes their sessions captured after date D."

**Cryptographic grounding**: GDPR Art.7(3) (withdrawal must be as easy as giving), Art.17 (data
used after revocation). `SeparationRatioRegistry.sol` anchors a SHA-256 commitment of the ratio —
if the input corpus included revoked-consent sessions, the on-chain commitment is tainted.

**Mitigation (Phase 162)**: Add consent-aware corpus filtering to `get_separation_defensibility_status()`
and `analyze_interperson_separation.py`: query `consent_ledger` for each player `device_id`;
exclude revoked/`erasure_requested` devices from `n_per_player` count and Mahalanobis computation.

**Status**: CLOSED (Phase 162). `get_consent_corpus_coverage()` + `get_active_consent_devices()`
added to Store; GET /agent/consent-aware-corpus-status reports active_consent_count/revoked_count/
erasure_requested_count/consent_corpus_defensible; Tool #119 + ConsentAwareCorpusResult +
VAPIConsentAwareCorpus SDK; 8 bridge + 4 SDK tests; Bridge 1910→1918; SDK 285→289.

---

**W2 — Consent-filtered separation ratio as legally defensible tournament evidence.**

**Mechanism**: Only players with active consent (`consent_given=True AND revoked=False AND
erasure_requested=False`) contribute to the on-chain ratio commitment in `SeparationRatioRegistry.sol`.
Proof statement: "These N sessions, from consented players, produced ratio=1.261." Downstream
court-admissible evidence for tournament dispute resolution. Composable triple gate:
`consent_given AND defensible AND decay_factor > 0.25` = full privacy-compliant enrollment gate
(WIF-019 primitive + Phase 161 enforcement + Phase 162 corpus filter).

**Phase candidate**: Phase 163 (WIF-022: extend `commit_separation_ratio()` to include N_consented
in the SHA-256 hash commitment, ensuring on-chain evidence reflects only consented sessions).

**Exclusive because**: Requires Phase 151 STRUCTURED_PROBE_TYPES + Phase 153 SeparationRatioRegistry.sol
+ Phase 159 BiometricPrivacyComplianceAgent + Phase 160 consent ledger + Phase 161 consent gate
+ Phase 162 corpus coverage. No competing gaming DePIN protocol has consent-filtered biometric
separation ratio anchored on-chain.

---

---

## WIF-023 — Consent-Count Staleness: On-Chain N_consented Overstates Corpus After Post-Commitment Revocation (Phase 164)

**W1 — Failure mode**: The Phase 163 `commit_separation_ratio()` hash binds `N_consented` at commit
time, but the `consent_ledger` is mutable — a subsequent revocation drops `N_consented` in the live
store while the on-chain commitment permanently records the pre-revocation count, creating a
verifiable consent-count divergence that any regulator or opposing counsel can exploit by querying
both the chain and the live API.

**Implication**: Tournament operator defends ratio=1.261, N_consented=3 on-chain. Regulator queries
`GET /agent/consent-aware-corpus-status` live and sees N_consented=2 (one post-commit revocation).
The on-chain proof claims three consented participants; the live ledger confirms only two. Under
GDPR Art.17(3)(e), the overstated count cannot be used defensively when the data subject has exercised
Art.17(1) rights post-commitment. The operator cannot un-commit the on-chain hash; the commitment
becomes tainted retroactively. Both facts are true at their respective timestamps — but the mismatch
constitutes a material representation gap in any legal challenge.

**Cryptographic grounding**: SHA-256(ratio_str + N + N_consented + players_sorted + ts_ns) is
collision-resistant and immutable on IoTeX L1. GDPR Art.7(3) requires withdrawal to have immediate
effect on processing. If a post-commitment revocation is not surfaced alongside the on-chain proof,
the proof is an incomplete representation of the lawful processing basis at tournament time.

**Mitigation (Phase 164)**: Introduce a `ConsentSnapshotAnchor` — a lightweight supplementary
commitment stored in a new `consent_snapshot_log` table. Each `revoke_consent()` call triggers a new
consent snapshot: `SHA-256(commit_hash_ref + N_consented_current + revoked_device_ids_sorted + ts_ns)`
appended as a delta. GET /agent/consent-snapshot-chain returns `{original_commit_hash, deltas[],
current_n_consented, chain_valid}`. Tool #121 `get_consent_snapshot_chain`;
`ConsentSnapshotChainResult` SDK.

**Status**: OPEN — Phase 164 candidate. Filed 2026-04-04 (AutoResearch cycle 9).

---

**W2 — Consent Delta Chain as Legally Sequenced Biometric Audit Trail.**

**Mechanism**: Each revocation appends a cryptographically chained delta to a `ConsentSnapshotRegistry.sol`
sidecar: `delta_hash = SHA-256(prev_delta_hash + revoked_device_id + N_consented_after + ts_ns)`. The
chain of deltas, anchored on IoTeX L1, constitutes a tamper-evident GDPR processing record. Tournament
regulators receive a `chain_id` (the original separation ratio commitment) and can replay the full
consent history from the chain. This converts the mutable SQLite `consent_ledger` into an append-only
on-chain audit log — the first consent-delta-chained biometric tournament credential in any gaming
protocol.

**Phase candidate**: Phase 164, ~4h effort (ConsentSnapshotRegistry.sol + deploy script + 6 Hardhat
tests + consent_snapshot_log table + store methods + GET endpoint + Tool #121 + SDK
ConsentSnapshotChainResult + openapi schema).

**Exclusive because**: Requires Phase 153 SeparationRatioRegistry.sol + Phase 160 consent_ledger +
Phase 161 consent gate + Phase 162 consent-aware corpus + Phase 163 N_consented hash binding.

---

## WIF-024 — Partial Consent Withdrawal Causes Silent Per-Player Centroid Drift (Phase 165)

**W1 — Failure mode**: When a player operates across multiple `device_id`s (e.g., P1 registers
device_A for sessions 1-5 then device_B for sessions 6-11), revoking consent on device_A triggers
`_check_consent_gate()` to block only device_A's future inserts — but existing sessions from device_A
already contributed to `n_per_player` counts and Mahalanobis centroid computation in
`get_separation_defensibility_status()`; the consent gate has no mechanism to retroactively exclude
device_A's sessions from the per-player aggregate, so the centroid shifts silently when device_A's
records are anonymized under GDPR Art.17 while device_B's records remain intact.

**Implication**: `get_active_consent_devices()` returns only device_B, so `consent_corpus_defensible`
appears correct — but the centroid for P1 in the Mahalanobis feature space was computed using sessions
from both devices. After anonymization of device_A records, the centroid should shift (or P1's N count
should drop), but neither `get_separation_defensibility_status()` nor `get_consent_corpus_coverage()`
re-computes the ratio from scratch after each erasure event. The live separation ratio is cached in
`separation_defensibility_log` from before the revocation; it is stale but still reported as
authoritative. An adversary who controls device_A can revoke to trigger erasure of adversarial
calibration sessions, then re-enroll on device_B — purging inconvenient sessions while keeping the
stale ratio commitment on-chain. Courts in Germany (DSGVO §35) and France (CNIL guidance) have treated
the statistical derivative of erased data as a distinct erasure obligation.

**Mitigation (Phase 165)**: Introduce a `post_erasure_recompute` flag in `anonymize_device_records()`.
When called: (1) query `consent_ledger` for remaining active-consent devices per player; (2) re-run
`get_separation_defensibility_status(session_type, active_only=True)` joining on `consent_ledger`;
(3) insert new `separation_defensibility_log` row with updated `n_per_player`, `ratio`, `defensible`;
(4) fire `consent_recompute_complete` bus event. GET /agent/separation-defensibility-status gains
`post_erasure_recomputed_at` field. Tool #122 `trigger_post_erasure_recompute`;
`PostErasureRecomputeResult` SDK.

**Status**: OPEN — Phase 165 candidate. Filed 2026-04-04 (AutoResearch cycle 9).

---

**W2 — Post-Erasure Ratio Recompute as Proof-of-Clean-Corpus Primitive.**

**Mechanism**: After each GDPR Art.17 erasure, `anonymize_device_records()` triggers a fresh
Mahalanobis separation analysis over only active-consent sessions. The resulting ratio is committed to
a new `SeparationRatioRegistry.sol` entry with an `erasure_triggered=True` flag and a
`prev_commit_hash` back-reference. This creates a legally sequenced "clean corpus" chain: every erasure
event produces a new on-chain ratio commitment that supersedes the previous, with the causal link
(erasure event hash) embedded. Combined with WIF-023's ConsentSnapshotRegistry delta chain, the full
legal audit trail is: original commitment → consent deltas (WIF-023) → erasure-triggered ratio
recomputes (WIF-024 W2). First GDPR-compliant, cryptographically sequenced biometric corpus evolution
proof in competitive gaming infrastructure.

**Phase candidate**: Phase 165, ~3h effort (extend `anonymize_device_records()` + `post_erasure_recompute`
flag + consent-filtered re-run + new SeparationRatioRegistry.sol commit with `erasure_triggered` flag
+ `post_erasure_ratio_log` table + Tool #122 + SDK `PostErasureRecomputeResult` + openapi schema).

**Exclusive because**: Requires Phase 153 SeparationRatioRegistry.sol + Phase 160-163 full consent
stack + Phase 164 ConsentSnapshotRegistry delta chain (WIF-023). No competing protocol has
erasure-triggered statistical recomputation as an on-chain sequenced biometric audit primitive.

---

## WIF-025 — TouchAC Mobile Biometric Proof: Novel VAPI Mobile Extension (Phase 200)

W1 — Failure mode: PC separation ratio empirically confirmed (ratio=0.789, N=14, Phase 163) does
NOT generalize to mobile touch biometrics. Mobile touch patterns (contact_area_variance,
swipe_velocity_profile, multi_touch_coordination_entropy) are driven by entirely different
neuromuscular pathways than DualShock Edge grip tremor + analog stick mechanics. A mobile VAPI
deployment that inherits PC Mahalanobis thresholds (anomaly=7.009, continuity=5.367) without
mobile-specific calibration would produce near-random L4 detection rates on touchscreen inputs.
  Implication: Premature mobile launch (before PC phases 163-199 complete + before mobile-specific
  corpus N≥10/player per platform) exposes VAPI to false-positive tournament blocks at consumer
  scale (~2.7B mobile gamers). A single viral false-positive event could destroy protocol credibility
  before the PC separation ratio gate is even crossed. The legal GDPR stack (Phases 160-165) must
  be proven and battle-tested on PC before mobile introduces consumer-scale consent churn.
  Mitigation (Phase 200): Establish mobile as a wholly separate biometric domain. TouchAC
  (Touch Autonomous Cognition) records inherit the 228-byte PoAC wire format with `platform=0x02`
  tag. Mobile-exclusive L4 thresholds calibrated against N≥74 mobile sessions per player before
  any mobile tournament gate activation. Mobile fleet begins at agent #M1 (TouchAC Calibration
  Agent) — isolated from PC agents #1-#22+ in edge_ai_profile.py `platform` field.
  Status: OPEN — Phase 200 candidate. Filed 2026-04-05.

W2 — Novel mobile agent fleet composing into unified isFullyEligible() gate.
  Mechanism: Five mobile-exclusive agents form a parallel fleet to the 22 PC agents:
  #M1 TouchAC Calibration Agent — enrolls contact_area_variance / swipe_velocity_profile /
    multi_touch_coordination_entropy / touchscreen_spatial_entropy per-player; establishes
    mobile separation ratio corpus using same proper LOO + diagonal covariance methodology
    as Phase 143 PC corpus.
  #M2 Mobile W3bstream Relay Agent — submits TouchAC sessions to W3bstream applet node with
    offline buffer + retry for mobile network unreliability; bridges to IoTeX L1 via same
    PITLSessionRegistryV2.sol pattern.
  #M3 Wearable GSR Bridge Agent — BLE EDA polling from Apple Watch (ECG framework) / Galaxy
    Watch (BioActive sensor) consumer wearables; validate_gsr_hmac() extended with wearable
    device keys; PoHBG extended with `wearable_device_id` field.
  #M4 TouchAC Separation Monitor Agent — monitors mobile separation ratio independently from
    PC SeparationRatioMonitorAgent (#15); fires `mobile_separation_ratio_breakthrough` bus
    event; gates mobile TGE prerequisite (ratio>1.0 on mobile corpus required separately).
  #M5 Cross-Platform VHP Relay Agent — bridges PC VHP eligibility to mobile game contexts
    via LayerZero; validates PC VHP unexpired before issuing mobile tournament entry; composes
    VAPIProtocolLens.isFullyEligible() across both PC and mobile chains into single boolean.
  VAPIProtocolLens.sol extended with `isMobileEligible(bytes32 touchacDeviceId)` view; both
  PC isFullyEligible() and mobile isMobileEligible() required for cross-platform tournament.
  Phase candidate: Phase 200+. Prerequisites: PC ratio > 1.0 confirmed on-chain (Phase 153
  active); Phases 164-165 consent snapshot + post-erasure recompute complete; PC fleet at
  full maturity (agents #1-#22+ all live, epistemic threshold hardened). Mobile launches only
  after the PC protocol proves the methodology works at tournament scale.
  **Exclusive because**: No competing anti-cheat protocol has cross-platform biometric proof
  composability (PC PoAC + mobile TouchAC + wearable GSR) anchored to a single on-chain
  eligibility gate. This is the first DePIN gaming protocol designed for the 2.7B mobile
  gamer addressable market with the same cryptographic guarantees as the PC variant.

---

---

## WIF-026 — Context Drift on Claude Session Disconnect (Permanent Mitigation)

**W1 — Failure mode**: When a Claude session disconnects mid-phase (crash, timeout, context limit),
`VAPI-WORKFLOW.v2` files (`VAPI_CONTEXT.md`, `VAPI_AGENTS.md`, `VAPI_MEMORY.md`) fall behind
`CLAUDE.md` because the sync step at session end never executes. The next Claude session opens with
stale context: wrong phase number, wrong test counts, missing agent entries. Protocol decisions in
the new session are made against phantom state.

**Evidence**: Phase 156→164 disconnect (2026-04-05) left WORKFLOW.v2 files 8 phases behind. Active
Phase reported 156 (Bridge 1868, SDK 265, 20 agents) while CLAUDE.md ground truth was 164 (Bridge
1934, SDK 297, 22 agents). Phase 165 design context was partially lost — the user had to reconstruct
from memory fragments.

**Implication**: Any agent design decision made in a drifted session references wrong test baselines
(regression appears as 66-test deficit), wrong agent count (agent #21/22 missing from fleet health
checks), wrong phase number (next-phase numbering propagates errors). If drift persists across
multiple sessions, the cumulative error compounds.

**Cryptographic grounding**: CLAUDE.md is the single source of truth (append-only phase log). 
WORKFLOW.v2 files are derived views. The invariant is: `∀ WORKFLOW.v2 files: phase_num == CLAUDE.md.phase_num`. 
Any violation of this invariant is a silent protocol state corruption event.

**Mitigation (2026-04-05 — IMPLEMENTED)**:
1. `scripts/sync_vapi_workflow.py` — created: reads CLAUDE.md via regex, compares to `VAPI_CONTEXT.md`,
   updates Active Phase / test counts / Next Phase line / appends sync note to MEMORY.md if drift found.
   CLI: `--check` (read-only), `--phase-only` (no memory note), full sync (default).
2. PostToolUse hook in `.claude/settings.local.json` — fires after every `Write` tool call:
   `python scripts/sync_vapi_workflow.py 2>&1 | head -5`. Lightweight (reads 2 files, exits if no drift).
   Autonomous: zero operator intervention required after any Write.
3. Session Startup Protocol — VAPI skill instructs: read CLAUDE.md → compare WORKFLOW.v2 phase →
   run sync_vapi_workflow.py if drift detected. Belt-and-suspenders: hook catches real-time writes;
   startup check catches any gap the hook missed.

**Status**: MITIGATED (2026-04-05). Hook live. Sync script created. Session startup reads CLAUDE.md.

---

**W2 — Sync script as derivable, autonomous phase-coherence oracle.**

**Mechanism**: `sync_vapi_workflow.py` extracts state from CLAUDE.md using regex patterns that are
stable across all VAPI phases (the `Current phase: Phase NNN — Description` and
`Bridge: NNNN | Hardhat: NNN | SDK: NNN` formats are FROZEN as protocol invariants).
Any future session can run `python scripts/sync_vapi_workflow.py --check` and get a deterministic
answer: "WORKFLOW.v2 files are [N] phases behind." This is machine-readable phase coherence proof.

**Phase candidate**: No new code phase needed — IMPLEMENTED as structural tooling.

---

---

## WIF-027 — Context Window Budget Exhaustion as Session Disruption Root Cause

**W1 — Failure mode**: `CLAUDE.md` accumulates per-phase detail blocks indefinitely. At Phase 164,
the file is **185,466 bytes** (~46,000 tokens) — 4.6× the 40k-char Claude Code warning threshold.
This forces the compaction layer to apply lossy summarization every ~20 tool calls, converting precise
phase state (test counts, threshold values, protocol invariants) into approximations. The result is
cascading phase drift: the agent operates against phantom state, re-derives already-solved problems,
and produces proposals that violate invariants that were "summarized away."

**Evidence**:
- CLAUDE.md warning fires every session: `‼ Large CLAUDE.md will impact performance (183.1k chars > 40.0k)`
- Session disruptions reported by operator require full context reconstruction from memory fragments
- WIF-026 occurred because session context compaction lost the fact that sync needed to run
- 100+ per-phase detail blocks in CLAUDE.md (Phase 68–164) each contain 10–50 lines of implementation
  detail that is already fully captured in `git log --oneline` and in the code itself

**Cryptographic analogy**: CLAUDE.md functions as the session's "consensus chain" — every token over
budget introduces a hash collision risk (two different protocol states that compaction maps to the
same summary). The invariant `CLAUDE.md is the single source of truth` cannot hold if the file is
too large for the agent to hold in active context.

**Implication**:
- Session disruptions are NOT random; they are **deterministic** above the context budget threshold
- Every 8-phase block added to CLAUDE.md subtracts approximately 1 future tool call from clean context
- The system is self-defeating: VAPI's success (more phases) degrades the system that records it

**Grounded mitigation**:
```
CLAUDE_HISTORY.md: archive Phase 17–130 per-phase detail blocks (~130k chars freed)
CLAUDE.md target: ~25k chars (Phase 131–164 state + frozen invariants + architecture)
Expected result: < 40k warning threshold; sessions run to natural completion without compaction disruption
```

**Status**: IDENTIFIED (2026-04-05). Compression plan proposed. Awaiting operator approval to execute.

---

**W2 — CLAUDE_HISTORY.md as on-demand archival read pattern.**

**Mechanism**: Instead of every session loading full phase history (most of which is never needed),
session startup loads only CLAUDE.md (~25k chars, current state). When a specific historical phase
is needed (e.g., "how was Phase 112 implemented?"), the agent reads `CLAUDE_HISTORY.md` for that
section on-demand. This mirrors the VAPI architecture itself: `isFullyEligible()` is a single call
that hides all intelligence behind it — the session context is the tournament gate, CLAUDE_HISTORY.md
is the full audit trail behind it.

**Implementation**:
1. Create `CLAUDE_HISTORY.md` in repo root — append-only historical record
2. Move Phase 17–130 detail blocks from CLAUDE.md → CLAUDE_HISTORY.md
3. Keep condensed 1-line phase table (already exists) in CLAUDE.md as pointer
4. Step 13 of Skill 14 monitors CLAUDE.md size and proposes archive when > 40k chars

**Phase candidate**: No new code phase — structural repo maintenance. Can be done any session as
a pre-phase step (< 30 min).

---

**Document Version**: 1.9 (WIF-027 context window budget exhaustion, 2026-04-05)
**Last Updated**: 2026-04-05
**W1 Count**: 24 entries (WIF-014 Class K GSR bypass; WIF-016 covariance regime instability; WIF-018 consent gate gap; WIF-020 erasure gap ruling_validation_log; WIF-023 N_consented staleness; WIF-024 partial consent centroid drift; WIF-025 mobile PC-threshold inheritance; WIF-026 context drift on disconnect; WIF-027 context window budget exhaustion)
**W2 Count**: 20 entries (WIF-015 PoHBG quadruple proof; WIF-017 adaptive probe sequencing; WIF-019 consent ledger; WIF-021 consent-filtered separation corpus; WIF-023 consent delta chain; WIF-024 post-erasure recompute; WIF-025 mobile agent fleet + cross-platform VHP; WIF-026 sync script as coherence oracle; WIF-027 CLAUDE_HISTORY.md archival pattern)
**W3 Count**: 5 entries
**Update Method**: Append-only, status updates inline
**Key Cycle 5-6 Updates**: WIF-014/015 Class K + PoHBG (Phase 158 candidates); WIF-016/017 covariance instability + adaptive sequencing (Phase 157 candidates); AutoResearch cycles 5-6 score=1.000
**Key Cycle 7 Updates**: WIF-018/019 consent gate gap + consent ledger primitive (Phase 160 candidates); AutoResearch cycle 7 score=1.000
**Key Cycle 8 Updates**: WIF-020/021 erasure gap + consent-unaware corpus (Phases 161-162, both CLOSED); WIF-022 N_consented hash binding (Phase 163, CLOSED); AutoResearch cycle 8 score=1.000
**Key Cycle 9 Updates**: WIF-023/024 N_consented staleness + partial consent centroid drift (Phases 164-165 candidates); AutoResearch cycle 9 score=1.000
**Key Cycle 10 Updates**: WIF-025 TouchAC Mobile Biometric Proof (Phase 200 candidate); mobile agent fleet #M1-#M5 design; cross-platform VHP composability via LayerZero; 2026-04-05
**Key Cycle 11 Updates**: WIF-026 Context Drift on Session Disconnect — MITIGATED (PostToolUse hook + sync script + startup check); 2026-04-05
**Key Cycle 12 Updates**: WIF-027 Context Window Budget Exhaustion — IDENTIFIED; CLAUDE_HISTORY.md archival pattern proposed; Skill 14 Step 13 Memory Scope Audit added; 2026-04-05
**Key Cycle 7 (AutoResearch 2026-04-07)**: WIF-028 P1 Temporal Persona Break — structural one-way ratchet explains N=11(1.261)→N=14(0.789)→N=20(0.569) convergence; W2-028 session-date clustering + persona-windowed calibration recovery; Phase 169 candidate; score=1.000

### W1-014: enrollment_complete count-gate spoofing (Phase 166, Wiki-Generated)

**Status**: OPEN
**Detected by**: Skill 14 PostCode Sweep / vapi_wiki.py
**Phase**: Phase 166
**Timestamp**: 2026-04-08T01:15:22.718001+00:00

**Failure mechanism**: enrollment_complete fires on session COUNT=10 without biometric quality gate -- 10 non-standard sessions could cascade into TournamentActivationChainAgent

**Implication**: [Claude Code: what fails if unmitigated?]

**Mitigation**: require defensible=True from separation_defensibility_log as prerequisite (Phase 157 target)

**Invariants affected**: [Claude Code: list which of the frozen values are at risk]

**Separation ratio impact**: [Claude Code: None / Low / Medium / High]

[VAPI:Phase166:vapi_wiki.py:MEASURED]

### W2-014: mixed_biometric_probe activates all 13 features (Phase 166, Wiki-Generated)

**Status**: PROPOSED
**Detected by**: vapi_wiki.py knowledge accumulation
**Phase**: Phase 166
**Timestamp**: 2026-04-08T01:15:32.618155+00:00

**Mechanism**: Phase 166 mixed_biometric_probe activates all 13 features across 4 segments -- first measurement with complete feature set pending

**Exclusive because**: [Claude Code: why competitors cannot replicate without 228B PoAC + PITL]

**Phase candidate**: Phase 167

**Connection to ratio**: [Claude Code: how does this advance separation ratio or tournament launch?]

[VAPI:Phase166:vapi_wiki.py:MEASURED]

---

### W1-028: P1 Temporal Non-Stationarity — One-Way Ratchet on Separation Ratio (Phase 169 candidate)

**Status**: OPEN
**Detected by**: AutoResearch Cycle 7 (2026-04-07)
**Phase**: Phase 168 → 169

**Failure mechanism**: P1 intra-player Mahalanobis variance grows monotonically as sessions from different calendar weeks are added to the enrollment corpus. Each new week introduces sessions that cluster differently (grip posture shift, hardware wear, physiological variation), expanding the intra-player covariance ellipsoid toward inter-player space. This creates a structural one-way ratchet: more N makes the separation ratio WORSE, not better.

**Observed signature**: N=11 → ratio=1.261, N=14 → ratio=0.789, N=20 → ratio=0.569. The trend is the mathematical signature of a persona break — not a data shortage.

**Implication**: Without persona-break detection, the ratio will continue declining toward ~0.30 as more sessions are captured. The P2/P3 separation (~1.3) is masked by P1's expanding variance, making the 3-player corpus appear non-separable. TOURNAMENT BLOCKER is irresolvable by the current naive "capture more sessions" approach.

**Cryptographic grounding**: Phase 153 SeparationRatioRegistry.sol commitment at N=11 (ratio=1.261) is on-chain inconsistent with live N=20 (ratio=0.569) — legally discoverable during tournament dispute resolution.

**Mitigation**: W2-028 session-date clustering + persona-windowed calibration (Phase 169 candidate).

**Invariants affected**: separation ratio 0.362/0.569 (below min_separation_ratio=0.70 gate); ratio > 1.0 tournament gate; TOURNAMENT BLOCKER; dry_run=True (no live enforcement yet).

**Separation ratio impact**: CRITICAL — primary root cause of current TOURNAMENT BLOCKER

[VAPI:Phase168:autoresearch_cycle7:PROPOSED]

---

### W2-028: Session-Date Clustering — Persona-Windowed Calibration Recovery (Phase 169 candidate)

**Status**: PROPOSED
**Detected by**: AutoResearch Cycle 7 (2026-04-07)
**Phase**: Phase 168 → 169

**Mechanism**: Extend `analyze_interperson_separation.py` with `_detect_persona_break(player_id)`:
1. Group sessions by ISO calendar week
2. Compute per-week centroid (mean feature vector)
3. Compute pairwise inter-week centroid Euclidean distance
4. If `max(inter_week_dist) > 1.5 × mean_intra_week_std`: flag `PERSONA_BREAK`
5. Retain only most recent contiguous calendar cluster
6. Re-run ratio analysis on persona-pruned corpus

**Bridge additions**: `persona_break_log` table + `GET /agent/persona-break-status` + Tool #123 `get_persona_break_status` + `PersonaBreakResult(6 slots)` + `VAPIPersonaBreak` SDK

**ioSwarm integration**: `IoSwarmAdjudicationCoordinator` (Phase 131) treats `persona_break_detected=True AND ratio_after < min_separation_ratio` as equivalent to `ratio < 1.0` — blocks VHP mint via Phase 110 gate.

**Phase candidate**: Phase 169 (~4h) — 8 bridge + 4 SDK tests; Bridge 1958→1966 +8; SDK 309→313 +4; Hardhat 468 unchanged

**Exclusive because**: Requires Phase 142 + 143 + 150 + 153 + 157 + 163 + 164 composable infrastructure — no competing protocol has this.

**Connection to ratio**: Directly addresses TOURNAMENT BLOCKER by pruning old-persona P1 sessions and recovering defensible corpus from stable recent persona.

[VAPI:Phase168:autoresearch_cycle7:PROPOSED]

---

## WIF-029 — Temporal Biometric Drift: On-Chain Ratio Valid at T₀ but Stale at Tournament T₁ (Phase 178)

**W1 — Failure mode**: The `SeparationRatioRegistry.sol` commitment anchored at time T₀ carries no
expiry or TTL. A tournament operator authorized at T₀ (ratio=1.261, N=30) may run a tournament six
months later at T₁ — but a player's touchpad tremor pattern, grip pressure distribution, and bilateral
asymmetry index measurably drift over that window due to injury, muscular adaptation, or neurological
change. The Mahalanobis centroid computed at T₀ is no longer representative of the player's biometric
profile at T₁. The on-chain proof is cryptographically valid but biometrically stale. Courts in Germany
(DSGVO §35 purpose limitation) and France (CNIL guidance on biometric data minimization) require that
biometric processing remain fit-for-purpose; using a T₀ centroid for T₁ tournament adjudication
constitutes processing beyond the original lawful purpose if the biometric profile has changed
materially.

**Implication**: A tournament player blocked by L4 at T₁ can challenge the BLOCK ruling by
demonstrating their biometric profile no longer matches the centroid used to authorize the system —
the on-chain proof becomes a liability rather than a defense. The operator cannot prove freshness
without a re-calibration event log.

**Cryptographic grounding**: SHA-256(ratio_str + N + N_consented + players_sorted + ts_ns) encodes
`ts_ns` but has no TTL field. The absence of TTL in the commitment means any downstream consumer of
the proof must independently verify freshness — which is currently impossible without VAPI API access.

**Mitigation (Phase 178)**: Introduce `biometric_credential_ttl_days=90` in `Config`. On every
tournament authorization request, `TournamentActivationChainAgent` computes
`age_days = (now - commitment_ts_ns / 1e9) / 86400`. If `age_days > biometric_credential_ttl_days`,
return `{authorized: False, reason: "BIOMETRIC_CREDENTIAL_EXPIRED", recalibration_required: True}`.
The `SeparationRatioRegistry.sol` commitment schema gains a `ttl_days` field (default 90).
Tool #N `get_biometric_credential_age`; `BiometricCredentialAgeResult` SDK.

**Status**: CLOSED (Phase 178, 2026-04-09) — `biometric_credential_ttl_days=90.0`; `TournamentActivationChainAgent.check_biometric_credential_ttl()` blocks on `age_days > ttl_days`; Tool #127; BiometricCredentialAgeResult+VAPIBiometricCredentialTTL SDK; SeparationRatioRegistry.sol +renewCommit()+ttlDays field.

---

**W2 — Biometric Credential TTL as Renewable Tournament License Primitive.**

**Mechanism**: Each re-calibration event (N≥5 new touchpad_corners sessions per player) triggers a
`renew_separation_ratio_commitment()` flow: fresh Mahalanobis analysis → new
`SeparationRatioRegistry.sol` entry with `{prev_commit_hash, renewal_reason: "TTL_EXPIRY",
recalibration_ts_ns, new_ttl_days}`. The chain of renewals constitutes a temporally-sequenced
biometric license: original grant → renewals with provenance → current validity window. Tournament
operators receive a `license_chain_id` mapping to the full renewal history. This is the first
renewable biometric tournament license with on-chain TTL provenance in any gaming DePIN protocol.
Combined with WIF-023 ConsentSnapshotRegistry and WIF-024 post-erasure recompute, the full legal
audit trail spans: consent grants → erasure deltas → ratio recomputes → TTL renewals — a complete
temporal biometric ledger.

**Phase candidate**: Phase 178, ~4h effort (`biometric_credential_ttl_days` config +
`TournamentActivationChainAgent` TTL check + `SeparationRatioRegistry.sol` `ttl_days` field +
renewal flow + `biometric_renewal_log` table + Tool #N + SDK `BiometricCredentialAgeResult` +
openapi schema + 6 Hardhat TTL tests).

**Exclusive because**: Requires Phase 153 SeparationRatioRegistry.sol + Phase 163 N_consented hash
binding + Phase 164/165 consent delta chain + Phase 177 synthesis gate. No competing gaming protocol
has renewal-chainable biometric tournament licenses with on-chain TTL provenance.

**Status W2**: CLOSED (Phase 180, 2026-04-09) — `renewal_enabled=False` default; `biometric_renewal_chain_log` table (UNIQUE new_commit_hash anti-replay); `chain.renew_separation_ratio_commitment()` calls SeparationRatioRegistry.renewCommit(); new_hash=SHA-256(prev_hash+ratio+N+N_consented+ttl+ts_ns); Tool #129 trigger_renewal_commitment; BiometricRenewalResult+VAPIBiometricRenewal SDK. WIF-031 (consent-bound renewal provenance) filed as Phase 181 candidate.

[VAPI:Phase177:autoresearch_cycle13:PROPOSED]

---

## WIF-030 — ZK Ceremony Capture Attack: Single-Operator Trusted Setup Voids Zero-Knowledge (Phase 179)

**W1 — Failure mode**: VAPI's ZK proof circuits use Groth16, which requires a trusted-setup MPC
ceremony. If only the VAPI operator participated in the ceremony, the toxic waste (τ, α, β) is known
to a single party. That party can forge proofs without possessing real biometric data: a
`FeatureExtractionIntegrityProof` claiming legitimate sensor data, a `CalibrationIntegrityProof`
claiming honest calibration, and a `SeparationRatioZKProof` claiming ratio > 1.0 — all verifiable
on-chain but cryptographically hollow. The ceremony produces valid-looking CRS (Common Reference
String) elements indistinguishable from a multi-party ceremony on-chain. No existing VAPI component
validates ceremony participant count or audit log presence before accepting a ZK proof as
tournament-valid.

**Implication**: A compromised or colluding operator can generate synthetic tournament credentials
that pass all ZK verification checks. The biometric cryptographic binding (VAPI's core novel claim)
is reduced to a single point of trust — indistinguishable from a conventional centralized system
on-chain. Any legal challenge to a tournament ruling can void the ZK proof basis by demonstrating
single-party ceremony participation.

**Cryptographic grounding**: Groth16 soundness holds only under the knowledge-of-exponent assumption
applied to the CRS. Single-party setup breaks the "powers of tau" assumption. The on-chain verifier
(`verifyProof()`) has no access to ceremony metadata — it verifies the algebraic constraint, not the
ceremony integrity.

**Mitigation (Phase 179)**: Introduce `ceremony_audit_log` table:
`{ceremony_id, circuit_name, participant_address, contribution_hash, ts_ns}`. Minimum 3 distinct
`participant_address` entries required per circuit before any ZK proof from that circuit is accepted
by `TournamentActivationChainAgent`. New `CeremonyAuditGate` check: `ceremony_participants_ok =
count(distinct participant_address) ≥ 3`. Tool #N `get_ceremony_audit_status`;
`CeremonyAuditResult` SDK.

**Status**: CLOSED (Phase 179, 2026-04-09) — `ceremony_audit_enabled=False` default (infrastructure-first); `ceremony_audit_log` table (UNIQUE ceremony_id+participant_address+circuit_name); `CeremonyAuditRegistry.sol` NEW; GET /agent/ceremony-audit-status + POST /agent/register-ceremony-participant; Tool #128; CeremonyAuditGateResult+VAPICeremonyAuditGate SDK (renamed from CeremonyAuditResult/VAPICeremonyAudit to avoid Phase 85 collision); audit_passed=True fail-open on error.

---

**W2 — Multi-Party Ceremony Audit Chain as ZK Proof Provenance Primitive.**

**Mechanism**: Each ceremony participant contributes a `contribution_hash =
SHA-256(prev_hash + participant_address + contribution_entropy + ts_ns)`, forming an append-only
ceremony chain stored in `CeremonyAuditRegistry.sol`. The chain root is embedded in the CRS metadata
and verified by `CeremonyAuditGate` before any ZK proof is accepted. External auditors can replay
the chain from the genesis contribution to verify that toxic waste was destroyed at each step.
Tournament regulators receive a `ceremony_chain_id` alongside each ZK proof — provable multi-party
participation is a first-class tournament credential. This is the first ZK ceremony audit chain used
as a tournament authorization primitive in any gaming DePIN protocol — converting a
normally-invisible cryptographic setup ritual into a transparent, on-chain, regulator-inspectable
provenance proof.

**Phase candidate**: Phase 179, ~5h effort (`ceremony_audit_log` table +
`CeremonyAuditRegistry.sol` deploy + `CeremonyAuditGate` check +
`TournamentActivationChainAgent` gate condition extended + Tool #N + SDK `CeremonyAuditResult` +
openapi schema + 8 Hardhat ceremony tests + 4 bridge tests).

**Exclusive because**: Requires Phase 67 MPC ceremony infrastructure + Phase 177 synthesis gate +
Phase 179 ceremony_audit_log. No competing protocol has ceremony audit as a tournament authorization
condition.

[VAPI:Phase177:autoresearch_cycle13:PROPOSED]

---

---

## WIF-031 — Renewal Provenance Manipulation: Selective De-enrollment at Renewal Inflates Ratio (Phase 181)

**W1 — Failure mode**: `biometric_renewal_chain_log` entries are inserted by the operator. The renewal
flow computes `n_consented` live from `get_consent_corpus_coverage()`, but this call does NOT prevent
an operator from first revoking known-failing players' consent (via `POST /agent/revoke-consent`)
immediately before triggering renewal. The revocation drops those players from the active corpus,
inflating `N_consented` and shifting the Mahalanobis centroid away from high-variance individuals.
The resulting separation ratio is overstated: the renewal hash legitimately binds `N_consented` at
renewal time, but that number was artificially reduced by selective de-enrollment. Tournament regulators
cannot detect this manipulation via the renewal event alone — the chain is cryptographically valid.

**Implication**: A biometric renewal can function as a corpus pruning mechanism, turning a
TOURNAMENT BLOCKER (ratio=0.569) into an apparent pass (ratio>1.0) by removing the players whose
intra-player variance was suppressing the ratio. The Biometric Renewal Engine (Phase 180) makes this
manipulation more accessible, not less.

**Mitigation (Phase 181 candidate)**: Extend `POST /agent/renew-separation-ratio-commitment` to
atomically snapshot `N_consented` AND `players_consented_list` from the consent ledger into a
`renewal_consent_snapshot_log` table, linking via `new_commit_hash`. Any change in `players_consented_list`
between original commitment and renewal is flagged as `corpus_delta_detected=True` in the renewal record.
Regulators can audit the snapshot to verify no selective exclusions occurred. Reuses Phase 164
ConsentSnapshotDelta pattern exactly.

**Status**: OPEN — Phase 181 candidate. Filed 2026-04-09 (AutoResearch cycle 8, score=0.752).

---

**W2 — Consent-bound renewal chain as temporally-sequenced biometric license history.**

**Mechanism**: Each renewal binds `N_consented` from the consent ledger at renewal time:
`SHA-256(prev_hash + ratio + N_consented + players_sorted + ttl_days + ts_ns)` — chain links
original commitment to every renewal with consent corpus proof at each step. Tournament regulators
receive `license_chain_id` spanning original grant → renewals → current validity. Full provenance
chain is the first renewable consent-bound biometric tournament license in any gaming DePIN protocol.

**Phase candidate**: Phase 181, ~2h (extend `renew_separation_ratio_commitment()` to snapshot
consent corpus at renewal time — reuses Phase 163+164 pattern exactly; add `renewal_consent_snapshot_log`
table; extend POST response with `corpus_delta_detected` flag).

**Exclusive because**: Requires Phases 153+163+164+178+180 composite infrastructure.

[VAPI:Phase180:autoresearch_cycle8:PROPOSED:score=0.752]

---

---

## WIF-032 — Erasure Certificate Replay: Stale Certificate Re-Anchored to Cover New Data (Phase 192)

**Filed**: 2026-04-11 (Phase 192 — CorpusDataCuratorAgent)
**Category**: W1 Failure Mode — Proof-of-Erasure authenticity gap

**Mechanism**: An adversary (or compromised bridge) generates a valid erasure certificate at
time T (covering tables A, B, C), then later submits new data under tables A, B, C, and re-anchors
the old certificate claiming those tables were erased. The certificate hash is valid — it was
computed correctly at time T — but the post-erasure data is new. If `ts_ns` is not validated
against a tamper-evident log with UNIQUE `certificate_hash`, a replay is undetectable.

**VAPI Mitigation (Phase 192)**:
- `erasure_certificate_log.certificate_hash` has UNIQUE constraint — same cert cannot be re-inserted
- `compute_erasure_certificate()` binds `ts_ns` into the hash; different times → different hashes
- `on_chain_ref` field reserved for future anchoring to SeparationRatioRegistry

**Status**: OPEN — Phase 194 candidate: anchor cert hash via `chain.record_erasure_on_chain()`.
Filed 2026-04-11.

---

## WIF-033 — Correlation Gate Bypass: Adversary Keeps Frobenius Distance Below Separability Threshold (Phase 192)

**Filed**: 2026-04-11 (Phase 192 — CorpusDataCuratorAgent)
**Category**: W1 Failure Mode — Feature correlation exploitability

**Mechanism**: The `correlation_separable` gate triggers only when inter-player Frobenius distance
exceeds `separability_threshold=0.5`. An adversary who profiles the current corpus can craft
inputs that land within the threshold band — maintaining `correlation_separable=False` forever —
so the corpus never triggers the correlation warning that would flag non-separable player data.
This defeats the Data Readiness Certificate gate silently.

**VAPI Mitigation (Phase 192)**:
- Frobenius distances stored per-pair in `feature_correlation_log`; trend analysis externally detectable
- `correlation_separable=False` is itself a blocking failure in DataReadinessCertificate
- Phase 143 diagonal LOO baselines (P1vP2=2.868, P1vP3=3.276, P2vP3=2.243) far exceed 0.5

**Status**: OPEN — Phase 194 candidate: adaptive threshold from rolling per-pair Frobenius median.
Filed 2026-04-11.

---

## WIF-034 — Threat Forecast Accuracy Collapses When PIR Harness Score Unavailable (Phase 191)

**Filed**: 2026-04-11 (Phase 191 — Threat Succession Protocol)
**Category**: W1 Failure Mode — ProtocolMaturityScoringAgent accuracy gap

**Mechanism**: The `threat_forecast_accuracy_component` in ProtocolMaturityScoringAgent (weight=0.07)
reads its score from the PIR harness output. If ProtocolIntelligenceRecordAgent (Phase 189) has
not produced any records — or the PIR chain is disabled — the component defaults to 0.5 (neutral)
rather than 0.0. This masks low forecast accuracy behind a neutral score, allowing the overall
maturity score to remain artificially high when the intelligence record pipeline is not running.

**VAPI Mitigation (Phase 191)**:
- `neutral 0.5 when no data` — documented design choice; prevents cold-start penalty
- `tsp_enabled=True` default ensures TSP is always active when agents are running
- `biometric_stationarity_component` (weight=0.04) from BiometricStationarityOracleAgent adds
  independent corroboration

**Status**: CLOSED by Phase 191. TSP formal implementation with 8-component v2 scoring.
Filed 2026-04-11.

---

## WIF-035 — Biometric TTL Expiry Bypasses Tournament Preflight Gate (Phase 196)

**Filed**: 2026-04-11 (Phase 195/196 — Tournament Preflight v2)
**Category**: W1 Failure Mode — Tournament gate bypass via credential staleness

**Mechanism**: Tournament preflight (Phase 127) checks 8 P0 conditions but does NOT check
whether the biometric credential TTL has expired. A device with a valid `isFullyEligible()`
call at T₀ whose biometric credential expires at T₁ < tournament_start can still pass all
8 preflight conditions at T₀. When the actual tournament fires, `isFullyEligible()` returns
False — credential expired — but preflight had already passed and tournament was launched.

**VAPI Mitigation (Phase 196)**:
- 9th P0 condition `biometric_ttl_ok` added to `TournamentPreflightResult`
- Logic: `(not ttl_expired) AND len(renewal_chain) > 0` — requires active renewal chain
- `commit-activation` extended: `biometric_ttl_expired_or_no_renewal_chain` blocker added
- BT calibration gate (WIF-035 W1, Cycle 28): HARD RULE — never set `bt_transport_enabled=True`
  without an active BT threshold track in `l4_threshold_tracks` (USB thresholds 7.009/5.367
  NOT valid for BT sessions)

**Status**: CLOSED by Phase 196. biometric_ttl_ok as 9th P0 preflight condition.
Filed 2026-04-11.

---

## WIF-036 — Agent Context Drift: LLM System Prompt Advances Without Registry Update (Phase 203)

**Filed**: 2026-04-12 (Phase 203 — AgentContextRegistry)
**Category**: W1 Failure Mode — Silent semantic drift in LLM agent fleet

**Mechanism**: Phase 201 added static tests checking that each of the 3 LLM agents
(bridge_agent, session_adjudicator, calibration_intelligence_agent) contains specific
Phase 200 invariant strings at commit time. But these tests pass at commit time and
remain passing even after Phase 204+ advances the protocol with new invariants — the
old static checks never update. More critically: if the bridge is restarted after a
deployment error with the wrong environment variables or a stale container image, the
agents can run with pre-Phase-200 system prompts while static tests at the committed
version still pass. No runtime signal distinguishes "correct prompt at startup" from
"stale prompt from old deployment."

**Implication**: Bridge Agent makes tournament gate decisions using Phase 30 rules.
Session Adjudicator runs dry_run=True logic even after dry_run was flipped. Calibration
Intelligence Agent enforces Phase 148 thresholds after Phase 200 invariant updates.
None of these failures are detectable from existing FSCA rules or the operator dashboard.

**VAPI Mitigation (Phase 203)**:
- `agent_context_log` table: UNIQUE(agent_id, prompt_sha256) — hash registered at startup
- `main.py` Phase 203 block: SHA-256(system_prompt) for all 3 agents computed and stored
  at every bridge startup
- `CONTEXT_HASH_MISMATCH` — 4th INVERSION rule in FleetSignalCoherenceAgent
- Fires when any of the 3 agents is NOT registered in `agent_context_log`
- Severity: HIGH; resolution: "Restart bridge and verify Phase 203 startup block executed"

**Status**: CLOSED by Phase 203. AgentContextRegistry + CONTEXT_HASH_MISMATCH INVERSION rule.
Filed 2026-04-12.

---

## WIF-037 — Separation Ratio Velocity Regression: Convergence Reversal After Irreversible On-Chain Commit (Phase 202)

**Filed**: 2026-04-12 (Phase 202 — TremorRestingConvergenceOracle)
**Category**: W1 Failure Mode — Ratio regression post-commitment

**Mechanism**: The touchpad_corners corpus demonstrated the exact failure mode: ratio peaked
at 0.998 (N=29, P1=8/P2=11/P3=10) then declined to 0.728 (N=35) as P3 non-stationarity
dominated. P3 intra-player variance=1.154 (mean), range=[0.164, 2.024] — P3 is non-stationary;
intra-mean=0.802 > inter-mean=0.584 → ratio < 1.0 structurally. The tremor_resting probe
(Phase 199) could exhibit the same pattern: ratio exceeds 1.0 at N=15, triggering IoSwarm
quorum vote and SeparationRatioRegistry.sol commitment, then falls below 1.0 at N=20 as
additional sessions reveal player non-stationarity. Once the on-chain SHA-256 commitment
is written, it is immutable — the blockchain record states "separation confirmed" while
the actual corpus says "separation failing."

**Implication**: VHP mint authorized on false separation claim. Tournament launches against
a biometric corpus that does not actually separate the enrolled players. First false
positive/negative in live tournament exposes the protocol to challenge.

**VAPI Mitigation (Phase 202)**:
- `tremor_convergence_log` table tracks velocity per session for `tremor_resting` probe type
- velocity = (ratio_curr - ratio_prev) / N_delta — per-session rate of change
- `convergence_stable=True` only when velocity ≥ 0 for 2 consecutive sessions
- `RATIO_VELOCITY_NEGATIVE` — 6th ORPHAN rule in FleetSignalCoherenceAgent
  Fires when convergence_stable=0 for >4 hours with no recovery (orphan_window_seconds=14400)
  Severity: HIGH; resolution: "Add more tremor_resting sessions; check P3 intra-player variance"
- Acts as circuit breaker before any IoSwarm MINT_QUORUM=0.80 vote or on-chain commitment fires

**Status**: CLOSED by Phase 202. TremorRestingConvergenceOracle + RATIO_VELOCITY_NEGATIVE rule.
Filed 2026-04-12.

---

## WIF-038 — IoSwarm Active but Zero Quorum-Confirmed Adjudications: VHP Mint Permanently Fail-CLOSED (Phase 204)

**Filed**: 2026-04-12 (Autoresearch Cycle 31, score=1.000 — fleet_coherence_critical)
**Category**: W1 Failure Mode — Fleet-level SEMANTIC CONTRADICTION

**Mechanism**: When `ioswarm_enabled=True` (Phase 200, set in bridge/.env) AND the
`ruling_streaks` table has zero `consecutive_clean` entries older than 24 hours,
`IoSwarmVHPMintCoordinator.request_mint()` fails CLOSED on every call because
`IoSwarmAdjudicationCoordinator` has never produced a quorum-confirmed CERTIFY verdict.
`MINT_QUORUM=0.80` (Phase 110) requires a CERTIFY verdict from IoSwarmAdjudicationCoordinator —
but if the adjudicator has never run a quorum-confirmed session, the mint coordinator has
zero valid entries to draw from, and `ioswarm_adjudication_log.quorum_reached=True` is
always empty.

**Implication**: Tournament operators see `ioswarm_enabled=True` and assume VHP mint is live.
The separation ratio breaks through 1.0, the tournament activation chain completes, dry_run
flips to False — and the first real VHP mint attempt silently fails with MINT_QUORUM=0.80
not reached. No coherence alert fires. The stall is undetectable from existing FSCA rules
(7 CONTRADICTION rules have no coverage of this conjunction), agent bus channels, or the
operator dashboard. `BLOCK_QUORUM=0.67` may be reachable but was never exercised.

**VAPI Mitigation (Phase 204 candidate)**:
- 8th CONTRADICTION rule: `IOSWARM_ACTIVE_NO_ADJUDICATIONS`
  Trigger: `ioswarm_adjudication_log` has no rows OR all rows have `quorum_reached=False`
  AND `time_since_first_row > 86400s` AND `ioswarm_enabled=True`
  Severity: HIGH. Dormant when `dry_run=True` (expected state; mint not authorized).
  Resolution: "Run at least 1 live adjudication session to prime IoSwarmAdjudicationCoordinator.
  Check ioswarm_adjudication_log for quorum_reached=False patterns. Verify BLOCK_QUORUM=0.67
  is reachable with current emulator seed (Phase 109A 5-node emulator, seed=109/110)."
- W2: IoSwarm Adjudication Primer — POST /agent/prime-ioswarm-adjudication
  Replays last N=5 ruling_streaks entries through IoSwarmAdjudicationCoordinator (BLOCK_QUORUM=0.67)
  in offline emulation mode to produce first quorum_reached=1 row, unblocking VHP mint pathway
  before the first real tournament. Records in ioswarm_adjudication_log with source="primer".
  primer_enabled=False default. +8 bridge tests, +4 SDK tests. No Hardhat needed.
  Exclusive: requires simultaneous ioSwarm emulator (Phase 109A) + SessionAdjudicator streak
  data (Phase 66) + IoSwarmVHPMintCoordinator (Phase 110) + FleetSignalCoherenceAgent
  CONTRADICTION monitoring (Phase 193) — a 5-phase stack only VAPI has.

**Status**: OPEN — Phase 204 candidate. Filed 2026-04-12.
[VAPI:Phase204:autoresearch_cycle31:PROPOSED:score=1.000]

---

**Document Version**: 2.3 (WIF-034..038 filed 2026-04-12; WIF-036/037 CLOSED; WIF-038 Phase 204 candidate)
**Last Updated**: 2026-04-12
**W1 Count**: 34 entries (WIF-038 IOSWARM_ACTIVE_NO_ADJUDICATIONS OPEN Phase 204; WIF-037 CLOSED Phase 202; WIF-036 CLOSED Phase 203; WIF-035 CLOSED Phase 196; WIF-034 CLOSED Phase 191)
**W2 Count**: 25 entries (WIF-038 W2 IoSwarm Adjudication Primer Phase 204 OPEN; WIF-037 W2 convergence oracle CLOSED; WIF-036 W2 agent hash registry CLOSED)
**W3 Count**: 5 entries
**Update Method**: Append-only, status updates inline
**Key Phase 202/203 Updates**: WIF-037 tremor convergence velocity regression CLOSED; WIF-036 agent context drift CLOSED; WIF-038 ioSwarm adjudication gap filed (autoresearch cycle31 score=1.000)
