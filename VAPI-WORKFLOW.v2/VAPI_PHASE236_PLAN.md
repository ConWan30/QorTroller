# VAPI Phase 236+ Comprehensive Architecture Plan

## Context

Phase 235 COMPLETE (2026-04-25). GIC_1 STAMPED. Grind underway (chain_length=16, grind_target=100).
The immediate pipeline (auto_grind.py driving adjudication + bridge running) is functional.
This plan addresses the six-component architecture vision requested for Phase 236+ development,
plus the Personal Readiness Dashboard (Component 7) added as a post-Phase-236 candidate.

**Authoritative state:** Bridge 2477 | SDK 535 | Hardhat 502 | Contracts 45 LIVE | 29 standalone agents + 3 stewards (9 absorbed)
AIT ratio=1.199 (all_pairs_p0_ok=True) | tremor_resting=1.177 (all_pairs_p0_ok=False P1vP3=0.032)
L4: anomaly=7.009 / continuity=5.367 | dry_run=True | GIC formula v1 FROZEN

---

## Component 1 — Backend-Frontend Reliability Loop

### Honest Assessment: 90% Already Solved

**What exists:**
- `auto_grind.py` — autonomous grind driver (already in repo, untracked). Polls bridge every 60s,
  fires `/agent/adjudicate` when `grind_ready=True` and `ctx != MENU_DETECTED`, throttles to one
  trigger per 5 min, stops at `chain_length >= grind_target`. Safe to Ctrl+C (chain state on bridge).
- `frontend/src/shared/api/bridgeApi.js` — mock fallback system. `get()` always tries live bridge
  first, `deactivateMock()` on success. `noMock: true` on `useGrindChain` + `useCaptureHealth`
  prevents swap on failure. Dashboard degrades gracefully to mock when bridge is offline.
- Vite proxy: all `/operator`, `/agent`, `/bridge`, `/ws` routes → `http://127.0.0.1:8080`.

**What's missing: process watchdog.**
Bridge crashes or is manually stopped — no auto-restart exists. The grind requires bridge
running continuously for days (100 sessions). A single crash breaks the grind session if the
operator doesn't notice.

### Implementation: `scripts/bridge_watchdog.py`

```python
# Monitors bridge health via /health endpoint
# Auto-restarts via subprocess.Popen(['python', '-m', 'bridge.vapi_bridge.main'])
# Exponential backoff: 5s → 10s → 30s → 60s (cap)
# Writes restart events to watchdog_log.json
# Max 3 restarts per hour before alerting operator (GRIND_SESSION_ID preserved in .env)
```

**Critical invariant**: GRIND_SESSION_ID in bridge/.env must survive restarts. The watchdog must
NOT touch bridge/.env. Chain state is in SQLite (persists across process restarts).

**Three-terminal grind setup (post-watchdog):**
1. Terminal 1: `python scripts/bridge_watchdog.py` (monitors + restarts bridge)
2. Terminal 2: `python auto_grind.py` (drives adjudication)
3. Terminal 3: `cd frontend && npm run dev` (dashboard monitoring)

**Effort:** ~2 hours. No new tests needed (watchdog is operational tooling, not protocol logic).
**Phase:** 236-WATCHDOG candidate (before grind autonomous phase begins).

---

## Component 2 — Decentralized Wiki Snapshot Database

### Honest Assessment: Git Already Does This — The Novel Part Is ZK Attestation

**What exists:**
- `wiki/snapshots/grind_readiness_phase_235.json` committed to main — git IS the decentralized
  versioned snapshot store for anything committed.
- `CorpusDataCuratorAgent` (agent #35, Phase 192) — 7-task data coherence layer. Task 1 is the
  Provenance DAG (20-hop walk). Task 7 is Session Contribution Weights.

**What's genuinely novel: Task 8 — ZK-Attested Corpus Snapshot**

CorpusDataCuratorAgent currently runs 7 tasks sequentially. Task 8 would:
1. Hash the entire wiki state: `snapshot_hash = SHA-256(concat(sorted wiki/*.md content))`
2. Produce a Poseidon commitment over (snapshot_hash, corpus_n, separation_ratio, ts_ns)
3. Anchor on IoTeX via existing `ProtocolCoherenceRegistry` anchor cycle (reuse Phase 221 pattern)
4. Store `corpus_snapshot_log` row with IPFS CID for offline access

**When CorpusDataCurator should trigger adaptive updates:**
- New AIT session inserted (via `insert_ait_session()`)
- Separation ratio changes > 0.01 from prior snapshot
- Agent fleet Merkle root changes (any agent added/updated)
- Manual override via `POST /operator/force-corpus-snapshot`

**Honest constraint**: "decentralized" here means on-chain anchoring + IPFS pinning, not a
distributed database. The source of truth remains the bridge SQLite + git repo. The snapshot
provides cryptographic auditability for what the corpus looked like at grind time.

**Lost connection / DualShock stall scenario:**
CorpusDataCurator already handles this via `asyncio.sleep(0)` yield points (Phase 235-EVENTLOOP).
If bridge crashes mid-session: snapshot is anchored at last Task 8 completion, not mid-write.
The gap (between last anchor and crash) is bounded by Task 8 cadence (proposed: every 10 sessions).

**Implementation:**
- `store.py`: `corpus_snapshot_log` table (snapshot_hash/ipfs_cid/corpus_n/separation_ratio/ts_ns/on_chain_confirmed)
- `corpus_data_curator_agent.py`: Task 8 added to `TASK_SEQUENCE` — runs after Task 7
- `operator_api.py`: `GET /agent/corpus-snapshot-status` + `POST /operator/force-corpus-snapshot`
- 8 bridge tests (T236-SNAP-1..8)

**Phase:** 236-CORPUS-SNAPSHOT | Effort: ~3 hours | Bridge +8

---

## Component 3 — ZK Cryptographic Privacy Layer

### Honest Assessment: Right Direction, Wrong Scope — ZK at the Application Layer Is the Play

**What exists (already implemented):**
- Phase 62: Groth16 ZK circuit with Poseidon(8) — `featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)`. FROZEN formula.
- Phase 67: MPC ceremony complete (3 contributors × 3 circuits, IoTeX block #41723255 beacon).
- BP-007: Ephemeral Session Entropy — self-destructing calibration keys per session.
- BP-002: ZK-Attested Consent (designed, not yet implemented).

**What's genuinely novel for Phase 236+:**

**ZK-SepProof: Proof-of-Separation-Ratio**
The most defensible tournament-gate proof would be: a Groth16 SNARK that proves
`separation_ratio > 1.0` AND `all_pairs_above_1 = True` WITHOUT revealing individual
biometric vectors. This is architecturally achievable:
- Public inputs: commitment to player set (hashed player IDs), threshold (1.0), proof generation ts
- Private inputs: per-player biometric feature vectors, covariance matrix eigenvalues
- Circuit constraint: Mahalanobis distances between player centroids > threshold
- Output: valid proof anchored in `SeparationRatioRegistry.sol` alongside existing ratio commitment

This is **VAPI-exclusive** because: it requires the calibrated per-player biometric corpus that
VAPI has already built (N=37 AIT sessions, 4-feature space). No other protocol has this input.

**For CorpusDataCurator ZK encryption (BP-002/BP-007):**
- Don't encrypt the wiki snapshots — they're protocol documentation, not private data.
- DO encrypt per-player biometric feature vectors at rest using ephemeral session keys (BP-007).
- The ZK-SepProof proves the ratio without ever revealing the vectors in plaintext.

**Implementation path:**
1. `contracts/circuits/SepRatioProof.circom` — new Groth16 circuit (medium complexity, ~2,000 constraints)
2. `scripts/generate_sep_ratio_proof.py` — Python prover using snarkjs subprocess
3. Anchor proof hash in `SeparationRatioRegistry.sol` (Phase 153 contract, extend `renewCommit()`)
4. `GET /agent/sep-ratio-proof-status` endpoint

**Effort:** ~6 hours (circuit + prover + tests). Hardware: None. Phase: 237-ZK-SEPPROOF

**Honest caveat on "top of the line encryption":** The biometric vectors themselves are not
secret in the current pipeline (they appear in `ait_session_log`). ZK proof generation protects
the CLAIM (ratio > 1.0) without revealing the EVIDENCE (feature vectors). That's the right privacy
model. Full homomorphic encryption of the corpus is technically possible but operationally
impractical for a 37-session SQLite database at this scale.

---

## Component 4 — IoID + W3bstream for Gamer Data Sovereignty

### Honest Assessment: Most Achievable Novel Contribution — IoID as Consent Anchor Is Architecturally Clean

**What exists:**
- `VAPIioIDRegistry.sol` LIVE at `0xF7885B...` (Phase 55). DID `did:io:0x<addr>` in PITL metadata.
- W3bstream: two applet designs (`validate_poac_record` + `process_gsr_packet`) in AssemblyScript.
- `DataSovereigntyRegistry` (`0xd928d9...`) deployed — pledge precedes marketplace listing.
- MANUFACTURER/DEVELOPER/GAMER licensing tiers already designed in tokenomics.

**Novel role for IoID: Consent Transaction Registry**

Currently IoID identifies the device. The novel extension: IoID as the on-chain consent anchor
for per-category data release.

```
Gamer consent flow:
  1. Gamer calls VAPIioIDRegistry.pledgeConsent(deviceId, category[], ttl_days)
     categories: ['tournament_gate', 'anonymized_research', 'manufacturer_cert', 'marketplace']
  2. consent_hash = SHA-256(deviceId + categories + expiry + ts_ns) stored on IoTeX L1
  3. DataSovereigntyRegistry.pledge(consent_hash, categories) — existing contract, extend it
  4. W3bstream: validate_poac_record applet checks consent_hash before routing to marketplace
     (PoAC records without matching consent bypass marketplace, go only to tournament gate)
```

**Novel role for W3bstream: Consent-Gated Data Pipeline**

W3bstream is the natural enforcement point — it sits between raw PoAC submission and IoTeX L1.
The applet can:
1. Parse 228B PoAC record (already designed)
2. Verify ECDSA-P256 (already designed)  
3. Look up `consent_hash` for the device's `did:io:` DID
4. Route to: tournament gate only / + anonymized research pool / + marketplace listing

This is VAPI-exclusive because: the 228B PoAC format is proprietary. No other W3bstream applet
can parse it without the VAPI spec. The consent-gated routing makes VAPI the only DePIN protocol
where the player's biometric proof is self-sovereign at the pipeline level, not just contractually.

**Implementation:**
- Extend `scripts/w3bstream/validate_poac_record.ts` with consent lookup
- New `contracts/contracts/VAPIConsentRegistry.sol` (extends DataSovereigntyRegistry pattern)
- `GET /agent/gamer-consent-status` endpoint
- Phase: 237-CONSENT | Effort: ~4 hours

---

## Component 5 — Pay-Per-Research Data Marketplace

### Honest Assessment: Hardest Component — Correct Vision, Sequencing Matters

**What exists:**
- `DataSovereigntyRegistry` LIVE: pledge→listing flow designed
- VAPIToken tokenomics: 70% device pool / 30% treasury from marketplace
- `VAPIHardwareCertRegistry`: CERTIFICATION_FEE_VAPI=1000 VAPI (manufacturers pay to list)
- Phase 192 CorpusDataCurator: Federated Corpus Quality (BP-007 compliant) — already has the
  per-session quality weights needed for tiered pricing

**The correct marketplace architecture:**

```
Gamer consent tier → data category → buyer → VAPI token flow:

  ANONYMIZED_RESEARCH:  $0.10/session equivalent → 70% to gamer's IoID-linked wallet
  MANUFACTURER_CERT:    $1.00/session equivalent → 70% to gamer, 30% treasury
  FULL_BIOMETRIC:       $5.00/session equivalent → gated by VHP + consent + BP-002 ZAC
```

**What's NOT built yet:** `VAPIDataMarketplace.sol` — the transaction contract.
This requires VAPIToken (Phase 99A, LIVE testnet) but needs mainnet TGE for real value.
The marketplace contract is designed; deployment is sequenced AFTER Stage 1 graduation + GIC_100.

**Realistic sequencing:**
1. GIC_100 deposited (Phase 236 milestone)
2. Stage 1 graduation activated (dry_run=False for ruling_enforcement_agent)
3. N≥100 live adjudications, zero false positives documented
4. VAPIDataMarketplace.sol deployed on testnet
5. TGE consideration AFTER all above

**Don't rush this.** The marketplace without real VAPI token value is a demo, not a flywheel.
The corpus data IS valuable — the AIT separation breakthrough (ratio=1.199) is a documented
scientific result. The value accrues when there are real buyers (hardware OEMs evaluating
DualShock certification for their own controllers).

**Phase:** 238-MARKETPLACE (post-GIC_100 and post-graduation) | Effort: ~8 hours (contract + SDK + tests)

---

## Component 6 — VAPI-Exclusive Communication Protocol

### Honest Assessment: Don't Invent Transport Crypto — Invent Application-Layer Message Signing

**User's vision is right in spirit; the implementation target is wrong.**

**What NOT to do:** Replace TLS 1.3 between frontend and bridge. Rolling your own transport
crypto is how security vulnerabilities get introduced. TLS 1.3 with forward secrecy is correct.

**What IS novel and exclusive to VAPI:**

**VAPI Application-Layer Message Envelope (VAME)**

Every authenticated bridge response could carry a VAPI-exclusive integrity token:

```json
{
  "data": { ...existing response... },
  "_vame": {
    "poseidon_commitment": "0x<Poseidon(chain_length, ts_ns, grind_session_id_hash)>",
    "gic_chain_head": "0x<latest_gic_hash[:16]>",
    "version": "vame/1.0",
    "ts_ns": 1745000000000000000
  }
}
```

The frontend verifies `poseidon_commitment` matches the `chain_length` and `ts_ns` in the
response body. An attacker who MITMs the TLS session (e.g., a rogue proxy) would need to
forge the Poseidon commitment without knowing the bridge's private state. This is not transport
security — it's application-layer authenticity.

**Why this is VAPI-exclusive:**
The Poseidon commitment uses the same hash function as the Phase 62 ZK circuit. The GIC chain
head binds every response to the cryptographic grind audit trail. No other gaming API ties its
HTTP response integrity to an on-chain Merkle chain of biometric session hashes.

**Practical implementation:**
- Add `_vame` field to responses from authenticated operator endpoints
- `frontend/src/shared/api/bridgeApi.js`: validate `_vame.poseidon_commitment` on each response
- WebSocket streams: include `vame_nonce` in each frame header
- Failure: if commitment doesn't match, flag as `VAME_INTEGRITY_FAILURE` — log to FSCA

**Effort:** ~3 hours. No new tests beyond VAME validation tests. Phase: 236-VAME

---

## Component 7 — Personal Readiness Dashboard (NEW — Post-Phase-236 Priority Candidate)

### Assessment: This Is the Most Compelling Consumer Feature After GIC_100 — and It's Already 70% Built

**The user's insight is architecturally correct and directly supported by existing VAPI infrastructure.**

**Why this works technically:**

VAPI already captures, per session:
- `micro_tremor_accel_variance` — elevated with muscle fatigue
- `press_timing_jitter_variance` — elevated with cognitive fatigue and repetitive strain
- `tremor_peak_hz` — frequency shifts with fatigue (peak moves lower under sustained effort)
- `trigger_onset_velocity_L2/R2` — slows with fatigue (reaction time signal)
- L5 rhythm CV — increases with mental fatigue (temporal precision degrades)
- GSR `baseline_conductance_drift` (when enabled) — session fatigue pattern directly

After GIC_100: each player has 100 calibrated sessions establishing a personal biometric baseline.
**Deviation from that baseline IS the fatigue/strain signal.** This is not speculation — the
Mahalanobis distance machinery that detects inter-player separation works identically for
intra-player temporal drift (which is what PersonaBreakDetectorAgent, Phase 182, already does).

**What PersonaBreakDetectorAgent (agent #27, LIVE) already computes:**
`persona_break_detection_enabled=True`. LOO centroid drift — fires `persona_break_detected=True`
when current session features diverge from the player's calibrated centroid. This is literally
fatigue detection. It was designed for biometric identity continuity, but the signal is the same.

**The Personal Readiness Dashboard maps existing signals to consumer-legible metrics:**

| VAPI signal | Readiness metric | Display |
|-------------|------------------|---------|
| `micro_tremor_accel_variance` vs baseline | Hand stability | "Hands: STEADY / FATIGUED" |
| `press_timing_jitter_variance` vs baseline | Reaction precision | "Precision: SHARP / DEGRADED" |
| PersonaBreakDetectorAgent drift score | Overall readiness | Readiness % (0–100) |
| L5 rhythm CV vs baseline | Mental timing | "Timing: CRISP / SCATTERED" |
| `trigger_onset_velocity` vs baseline | Reflex speed | "Reflexes: FAST / SLOWED" |
| Session count in last 24h | Repetitive strain risk | "RSI risk: LOW / MODERATE / HIGH" |

**Repetitive strain warning (novel, VAPI-exclusive):**
- Count sessions in last 24h from `ruling_validation_log`
- If N > 8 sessions/24h AND `press_timing_jitter_variance` trending up → `RSI_WARNING`
- Display in GamerView as amber banner: "You've logged 8+ sessions today. Take a break."
- This is medically reasonable (competitive gaming repetitive strain is a real injury vector)
- No other anti-cheat protocol monitors player physical health — this is genuinely novel

**Why this drives VAPI retention:**
The user's framing is exactly right: "VAPI is software that helps me as a gamer" vs "VAPI is
software I use during tournaments." A player who sees their readiness score drop after 4 hours
has a concrete reason to keep VAPI running. Each session feeds the corpus. Each corpus improvement
makes the tournament gate stronger. The retention flywheel is self-reinforcing.

**Integration path (no new protocol invariants touched):**

New: `GamerReadinessAgent` (agent #39):
- Reads last 10 sessions from `ruling_validation_log` + `records` table
- Computes per-feature drift vs personal calibrated centroid
- Writes to `gamer_readiness_log` (readiness_score, drift_by_feature, rsi_risk, session_count_24h)
- Fires `readiness_warning` bus event when readiness_score < 0.60 or rsi_risk = HIGH
- `gamer_readiness_enabled=True` default (it's observational, never a gate)

`GET /agent/gamer-readiness-status` — 8 keys:
- `readiness_score` (0.0–1.0)
- `hand_stability` (STEADY/MILD_FATIGUE/FATIGUED)
- `reaction_precision` (SHARP/DEGRADED)
- `mental_timing` (CRISP/SCATTERED)
- `rsi_risk` (LOW/MODERATE/HIGH)
- `sessions_today`
- `recommended_break_minutes` (null if LOW)
- `timestamp`

GamerView extension:
- New bottom chip: `READY` with score and color (green >0.80, amber 0.60–0.80, red <0.60)
- Clicking chip opens right drawer: per-feature readiness bars + RSI risk + session history
- Non-intrusive: only shows warning when score drops, not on every session

**Tests:** 8 bridge (T239-READY-1..8) + 4 SDK (T239-READY-SDK-1..4)
**Effort:** ~4 hours. Bridge +8, SDK +4.
**Phase:** 239-READINESS (post-GIC_100, post-graduation)
**Phase 240+ synergy:** GamerReadinessAgent readiness_score feeds the L6-Response haptic stimulus
layer (roadmap_post_stage_1 candidate) — player's readiness determines stimulus amplitude,
preventing fatigue-confounded baseline drift in the L6 calibration corpus.

---

## Integration Sequence (Phase 236 → Phase 240)

| Phase | Component | Depends On | Effort |
|-------|-----------|------------|--------|
| 236-WATCHDOG | Bridge process watchdog | Nothing (operational) | 2h |
| 236-VAME | Application-layer message signing | Nothing | 3h |
| 236-CORPUS-SNAPSHOT | CorpusDataCurator Task 8 (ZK-attested) | Phase 236-WATCHDOG stable | 3h |
| 237-CONSENT | IoID consent registry + W3bstream routing | Phase 236 complete | 4h |
| 237-ZK-SEPPROOF | ZK proof of separation ratio | Phase 237-CONSENT | 6h |
| 238-MARKETPLACE | VAPIDataMarketplace.sol | GIC_100 + graduation + TGE path | 8h |
| 239-READINESS | GamerReadinessAgent + dashboard | GIC_100 corpus baseline | 4h |

**GIC_100 is the gate for 238 and 239.** Without 100 sessions, the personal baselines are
too sparse for readiness scoring to be meaningful. The grind IS the prerequisite.

---

## Honest Architectural Summary

| Component | Status | Novelty | Risk |
|-----------|--------|---------|------|
| Bridge watchdog | Gap — 2h to close | Operational | Low |
| Wiki snapshot DB | Git does this; ZK attestation is the novel part | Medium | Low |
| ZK privacy layer | ZK-SepProof is novel; full-homomorphic is impractical at this scale | High | Medium |
| IoID consent + W3bstream | Highest achievable novelty — consent-gated DePIN pipeline | Very High | Low |
| Pay-per-research marketplace | Correct vision, sequencing matters — post-GIC_100 | High | Medium (token dependency) |
| VAPI message signing (VAME) | Don't replace TLS; application-layer Poseidon commitment is the right play | Medium | Low |
| Personal Readiness Dashboard | Most compelling consumer feature — already 70% built via PersonaBreakDetector + biometric corpus | Very High | Very Low |

**The standout recommendation:** Component 7 (Personal Readiness Dashboard) should jump the queue.
It requires no new protocol invariants, reuses existing agent infrastructure (PersonaBreakDetectorAgent),
and produces immediate consumer value after GIC_100. It's also the feature most likely to generate
organic interest from competitive gaming communities — health-aware play is a growing priority in esports.

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `scripts/bridge_watchdog.py` | NEW — process monitor + auto-restart |
| `bridge/vapi_bridge/operator_api.py` | +VAME field on authenticated responses |
| `bridge/vapi_bridge/store.py` | +corpus_snapshot_log + gamer_readiness_log tables |
| `bridge/vapi_bridge/corpus_data_curator_agent.py` | +Task 8 (ZK-attested snapshot) |
| `bridge/vapi_bridge/gamer_readiness_agent.py` | NEW — agent #39 |
| `bridge/vapi_bridge/main.py` | +GamerReadinessAgent instantiation |
| `frontend/src/views/GamerView.jsx` | +READY chip + readiness drawer |
| `frontend/src/shared/api/hooks/index.js` | +useGamerReadiness() hook |
| `sdk/vapi_sdk.py` | +GamerReadinessResult@dataclass + VAPIGamerReadiness |
| `sdk/openapi.yaml` | +/agent/gamer-readiness-status schema |

## Verification

1. `python scripts/bridge_watchdog.py` — kill bridge manually, confirm auto-restart in <10s
2. `GET /bridge/capture-health` — verify `_vame` field present with Poseidon commitment
3. `GET /agent/corpus-snapshot-status` — confirm snapshot_hash + on_chain_confirmed=True
4. `GET /agent/gamer-readiness-status` after 10+ sessions — readiness_score in [0,1], all fields present
5. GamerView: READY chip visible, color-coded; click opens readiness drawer with per-feature bars
6. Bridge 2477+8=2485 | SDK 535+4=539 after READINESS phase complete
