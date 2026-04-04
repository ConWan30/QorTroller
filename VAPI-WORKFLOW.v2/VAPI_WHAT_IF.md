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

**Document Version**: 1.2 (Phase 156)
**Last Updated**: 2026-04-04
**W1 Count**: 13 entries (added WIF-011 W1 CLOSED Phase 151, WIF-012 W1 OPEN Phase 157, WIF-013 W1 Phase 157)
**W2 Count**: 10 entries (added WIF-011 W2, WIF-012 W2, WIF-013 W2)
**W3 Count**: 5 entries
**Update Method**: Append-only, status updates inline
**Key Phase 156 Updates**: WIF-011 CLOSED (Phase 151); WIF-012 OPEN count-gate (Phase 157); WIF-013 NEW PoFC triple-proof (Phase 157); AutoResearch cycle 4 score=1.000
