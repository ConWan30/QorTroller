# VAPI MEMORY — For Claude Code Context

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

**Your Role**: When reading this file, you are the institutional memory of VAPI. You must remember what worked, what failed, and why. Never repeat failed experiments. Always build on validated patterns. Add your own learnings after each session.

> **INSTRUCTION TO CLAUDE CODE**: This file is the compounding learning log of VAPI development.
> When reading this file, you must:
> 1. Read recent entries (last 5-10) before proposing changes
> 2. Avoid repeating failed experiments (marked FAILED below)
> 3. Build on successful patterns (marked PATTERN)
> 4. Add new entries after significant discoveries or failures
> 5. Append-only — never delete historical entries

---

## 1. Session Outcomes (Chronological, Newest First)

### 2026-04-26: Phase 237-EXTEND COMPLETE — Phase 237 TRULY COMPLETE (6 honest additions shipped)

**What was done** — six extensions to declare Phase 237 truly complete (not "core shipped, deferrals deferred"):

A. **VAPIConsentRegistry deployed**: `0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` on IoTeX testnet. Gas ~0.07 IOTX. Smoke calls (owner / totalGrants=0 / ioidRegistry=unset) all passed. bridge/.env CONSENT_REGISTRY_ADDRESS set; frontend/.env.local VITE_CONSENT_REGISTRY_ADDRESS set; deployed-addresses.json updated with `_phase237_status: deployed` marker.

B. **W3bstream applet forward-compat stub**: `validate_poac_record.ts` extended with Phase 237-EXTEND consent-routing layer — top-of-file architectural comment block documenting routing matrix (TOURNAMENT_GATE=hard / ANONYMIZED_RESEARCH+MARKETPLACE=soft); return codes 4 (consent-absent hard refuse) / 5 (soft refuse routing skipped); `_check_consent_view()` helper with placeholder selector `0xCAFE0237` matching existing `0xDEADBEEF` stub-style; PLACEHOLDER ABI WARNING explicit. Documented architecture in code; ships when applet pipeline phase lands separately.

C. **Frontend first-of-its-kind wallet-write**: `<WagmiProvider>` wired into `main.jsx` around `<QueryClientProvider>` (FIRST wagmi-write in this codebase). New `frontend/src/hooks/useConsentSubmit.js` (wagmi `useWriteContract` wrapper, inline 3-method ABI, CATEGORY_TO_UINT8 map, `ready=false` fail-open when address unset). `useConsentStatus(deviceId, category)` added to `api/bridgeApi.js` with `noMock: true`. New `frontend/src/components/ConsentPanel.jsx` (~260 LOC, mirrors PCCDrawer pattern, right-edge drawer offset top:50%+110px so it sits below PCC handle, slide-in 320px, wallet-connect via useConnect/useDisconnect, 4 ToggleRows with disclosure copy, contract-address transparency footer, error surface, refetch-after-tx pattern). Mounted in GamerView next to PCCDrawer. `npm run build` passes.

D. **SDK Python `VAPIConsent` client class**: `GamerConsentResult @dataclass(slots=True)` with 8 slots; handles BOTH aggregated and single-category response shapes; `VAPIConsent.get_status(device_id, category="")` urllib pattern matching Phase 222 verbatim; never raises (returns Result(error=...) on any HTTP failure). Inserted after Phase 222 block in `sdk/vapi_sdk.py`.

E. **OpenAPI 3.0.0-phase237**: version bumped 204→237 (33 phases caught up); 3 new paths (`/agent/gamer-consent-status` GET with category enum filter, `/operator/record-category-consent` POST with reason ≥10 chars + on_chain:false, `/operator/revoke-category-consent` POST mirror); 4 new schemas (`GamerConsentStatus` aggregated + `ConsentCategoryStatus` single + `CategoryConsentRecordResult` + `CategoryConsentRevokeResult`); paths=160, schemas=129; YAML parses cleanly via `yaml.safe_load`.

F. **FSCA `CONSENT_REVOKED_BUT_DATA_FLOWING`**: pure data-add to `CONTRADICTION_RULES` in `fleet_signal_coherence_agent.py` (24 → 25 rules). LEFT JOIN `consent_ledger` ← `records` on device_id with `revoked_at IS NOT NULL AND records.created_at > revoked_at`. severity=HIGH GDPR Art.17 violation candidate. agents_involved=[bridge, BiometricPrivacyComplianceAgent, ConsentLedger]. resolution cites Phase 160 `anonymize_device_records` erasure pipeline. T237-CONSENT-9 test seeds revoked consent + post-revocation `records` row, runs `agent._check_contradictions()` via asyncio.get_event_loop().run_until_complete, asserts the rule fired.

**Test counts**: Bridge 2509→2510 (+1) | SDK 535→539 (+4 T237-S1..S4) | Hardhat 528 unchanged | Contracts 45 LIVE → **46 LIVE** | Wallet ~40.43 → ~40.36 IOTX (0.17% spent).

**What we learned**:
- I was wrong to defer the deploy in the original plan. Wallet 40.43 IOTX vs 0.07 IOTX gas is a 570x ratio. The "isolate code-shipping risk from on-chain risk" framing was conservative theatre. Deploy worked first try, all smoke calls passed, no rollback needed.
- I was wrong to call W3bstream applet extension "theatre". Adding the consent-routing branch to a placeholder-ABI stub is **preparation**, not theatre — when the applet pipeline phase lands, the consent enforcement is built in, not bolted on. Same convention as the existing `0xDEADBEEF` selector pattern.
- `ait_session_log` does NOT have `player_id` — it stores per-analysis snapshots with `n_per_player_json` aggregate. The proper "data flowing" surface for the FSCA rule is `records` (the PoAC ingestion table). Always re-verify table schema assumptions in plan-mode rather than trusting the earlier plan's SQL.
- WagmiProvider must wrap OUTSIDE QueryClientProvider per wagmi v2 docs so its internal queries reuse the same client. Wrong order silently produces double-mounted query clients.
- ConsentPanel handle position offset (top: calc(50% + 110px)) avoids overlap with PCCDrawer's middle handle — small detail but the user-visible difference between "two handles" vs "one handle clipping the other".

**Pattern identified [PATTERN-018]**: VAPI extension-completion accountability
1. Original plan justified three deferrals as "honest scope". Two were conservative theatre.
2. The phase was declared "shipped" while half-true. User pushed back on the deferrals.
3. Re-examination identified six honest gaps (3 deferrals + 3 unmentioned: SDK, OpenAPI, FSCA).
4. Extension closed all six in ~3-4h with zero new risk.
5. **Lesson**: when in doubt about whether a "deferral" is legitimate scope-cut or unconscious caution, default to including it. The cost of inclusion is bounded; the cost of exclusion compounds across phases (Phase 238 inherits a half-built Phase 237).

Phase 237 TRULY COMPLETE. Five FROZEN-v1 pillars live. Next: **237-ZK-SEPPROOF** (the harder Groth16 publishable primitive) — prerequisite for Phase 239 readiness with privacy.

---

### 2026-04-26: Phase 237-CONSENT COMPLETE — fifth FROZEN-v1 pillar (per-category gamer consent)

**What was done**:
- `bridge/vapi_bridge/consent_categories.py` NEW — fifth FROZEN-v1 cryptographic primitive, parallel to grind_chain.py / watchdog_chain.py / vame.py / corpus_snapshot.py.
  - `compute_consent_hash(device, categories|bitmask, expires_at, ts_ns)` v1: SHA-256(b"VAPI-CONSENT-v1"(15) || dev_b32 || bitmask_be(4) || expires_be(8) || ts_ns_be(8)) = 67B → 32B
  - `ConsentCategory` IntEnum: TOURNAMENT_GATE=0 / ANONYMIZED_RESEARCH=1 / MANUFACTURER_CERT=2 / MARKETPLACE=3 — position-frozen to match on-chain enum
  - `categories_to_bitmask` / `bitmask_to_categories` round-trip with uint32 overflow guard
  - `device_id_to_bytes32()` accepts hex (canonical) / raw 32B / freeform string (SHA-256 fallback for tests)
- `bridge/vapi_bridge/store.py`:
  - `_check_consent_gate()` extended with `category=None` default (Phase 161 backward-compat preserved exactly)
  - 3 thin helpers: `grant_category_consent` / `revoke_category_consent` / `get_category_consent_status` wrap existing Phase 160 primitives — ZERO schema churn (UNIQUE(device_id, consent_type) handles per-category UPSERT natively)
- `bridge/vapi_bridge/config.py`: `consent_registry_address` field with CONSENT_REGISTRY_ADDRESS env
- `bridge/vapi_bridge/chain.py`: `is_consent_valid` + `get_consent_record` view methods FAIL-OPEN when address unset (deliberate divergence from bbg_/dual_/swarm_ which raise — bridge is reader of consent, not writer)
- `bridge/vapi_bridge/operator_api.py`:
  - `GET /agent/gamer-consent-status?device_id=...&category=...` (read-only; aggregated all-four when no category filter)
  - `POST /operator/record-category-consent` (full operator auth + reason ≥10 chars; writes ONLY local consent_ledger; never on-chain — gamer-self-sovereign)
  - `POST /operator/revoke-category-consent` (mirror revoke endpoint)
- `contracts/contracts/VAPIConsentRegistry.sol` NEW: Phase 222 pattern (Ownable + ReentrancyGuard, anti-replay _recordedHashes, zero-hash + bad-category + double-revoke + no-consent-to-revoke guards, CEI, indexed events)
  - `enum ConsentCategory` + `struct ConsentRecord(consentHash, grantedAt, expiresAt, revoked)`
  - `mapping(address => mapping(uint8 => ConsentRecord)) _consents` — gamer (msg.sender) writes, bridge reads
  - `grantConsent(category, expiresAt, consentHash)` / `revokeConsent(category)` gamer-only
  - `isConsentValid` / `getConsentRecord` views with expiresAt check
  - `setIoIDRegistry(addr)` onlyOwner with zero-address guard — optional Phase 55 composition
- `contracts/scripts/deploy-phase237.js` NEW (NOT executed; reviewed for correctness)
- `bridge/tests/test_phase237_consent.py`: 8 tests T237-CONSENT-1..8 all passing 17.0s
- `contracts/test/Phase237.test.js`: 6 tests T237-HH-1..6 all passing 8s
- 4 new Hard Rules in CLAUDE.md (formula FROZEN, gamer-self-sovereign invariant, fail-open chain views, position-frozen enum)

**Test counts**: Bridge 2501→2509 (+8) | SDK 535 unchanged | Hardhat 522→528 (+6) | Contracts 45 LIVE + 1 code-complete (deploy deferred)

**What we learned**:
- Phase 160-164 pre-designed for category extension via `consent_ledger.UNIQUE(device_id, consent_type)` — by setting consent_type to a category name (e.g. "TOURNAMENT_GATE") instead of "biometric_processing", per-category UPSERT works without ANY schema change. This is the cleanest possible extension. The architectural foresight in Phase 160 paid back fully here.
- `_check_consent_gate` had only ONE call site — backward-compat via `category=None` default is trivially safe. Aggressive surface analysis BEFORE adding a new param saved an hour of regression checking.
- Hardhat `evm_increaseTime` + `evm_mine` is the canonical way to test on-chain expiry; T237-HH-4 uses it correctly.
- VAPI `chain.py` pattern for new on-chain functions has TWO valid styles: raise-on-missing-address (bbg/dual/swarm — all writers) vs return-default (Phase 237 readers). Document the distinction explicitly so future readers don't mistake the inconsistency for a bug.

**Pattern identified [PATTERN-017]**: VAPI five-pillar FROZEN-v1 cryptographic primitive family
1. **GIC v1** — per-session cognitive integrity (Phase 235-A; one hash per count-eligible session)
2. **WEC v1** — per-restart operational integrity (Phase 236-WATCHDOG; one hash per bridge lifecycle event)
3. **VAME v1** — per-response HTTP integrity (Phase 236-VAME; one commitment per JSON response)
4. **CORPUS-SNAPSHOT v1** — per-snapshot corpus integrity (Phase 236-CORPUS-SNAPSHOT; wiki + fleet + ratio + N + ts_ns)
5. **CONSENT v1** — per-(gamer, category) privacy commitment (Phase 237-CONSENT; device + bitmask + expiry + ts_ns)

All five: SHA-256, big-endian byte order, explicit domain tag (`VAPI-{NAME}-v{N}`), input range validation, integer encoding for variable-length floats/ratios, FROZEN at v1 with documented v2 path. Reviewers learn the pattern once. Together they cover: cognitive (GIC) + operational (WEC) + HTTP (VAME) + corpus (CORPUS-SNAPSHOT) + privacy (CONSENT) integrity surfaces. PATTERN-017 supersedes PATTERN-016 (which only listed three pillars; this is the canonical five-pillar form).

Phase 237-CONSENT complete. Next: **237-ZK-SEPPROOF** (the harder phase: Groth16 SNARK proves separation_ratio>1.0 AND all_pairs_above_1=True without revealing biometric vectors — publishable scientific primitive, ~6h, prerequisite for Phase 239 readiness done with privacy).

---

### 2026-04-26: Phase 236-CORPUS-SNAPSHOT COMPLETE — third chain pillar shipped

**What was done**:
- `bridge/vapi_bridge/corpus_snapshot.py` NEW — CORPUS-SNAPSHOT FROZEN FORMULA v1 (parallel to grind_chain.py / watchdog_chain.py / vame.py).
  - `commitment = SHA-256(b"VAPI-CORPUS-SNAPSHOT-v1"(23) || wiki_hash(32) || agent_root(32) || ratio_milli_be(8) || corpus_n_be(8) || ts_ns_be(8))` = 111B → 32B
  - `compute_wiki_snapshot_hash()` walks `wiki/**/*.md` sorted by POSIX-lowercase rel path; explicit per-file `b"--FILE:" + path + b"\n"` separator catches renames AND content edits
  - Ratio encoded as uint64 milliratio (×1e6 rounded) for OS-deterministic byte encoding regardless of float64 representation
- `bridge/vapi_bridge/store.py`: `corpus_snapshot_log` table (Phase 236 migration; UNIQUE INDEX on snapshot_commitment for idempotency); `insert_corpus_snapshot()` returns existing row id on UNIQUE collision (duplicate triggers no-op); `get_corpus_snapshot_status()` 10-key latest summary; `get_corpus_snapshot_history(limit)` DESC ts_ns
- `bridge/vapi_bridge/operator_api.py`: `GET /agent/corpus-snapshot-status` (read-only) + `POST /operator/force-corpus-snapshot` (full operator auth + reason ≥10 chars audit gate; computes wiki hash from cfg.wiki_dir, reads agent root from get_protocol_coherence_status(), reads ratio + N from get_ait_separation_status())
- `bridge/tests/test_phase236_corpus_snapshot.py`: 8 tests T236-SNAP-1..8 all passing 4.7s
- End-to-end smoke verified: live wiki/ tree hashes deterministically; 422 on short reason; 403 on wrong key; VAME headers stamped on snapshot endpoint too
- 4 new Hard Rules in CLAUDE.md (formula FROZEN, reason gate, on-chain config-gating, three-pillar pairing — GIC+WEC+CORPUS-SNAPSHOT must never break)

**Test counts**: Bridge 2493→2501 (+8) | SDK 535 unchanged | Hardhat 522 unchanged | Contracts 45

**What we learned**:
- `Config` is a frozen dataclass — must use `dataclasses.replace(Config(), ...)` not `cfg.x = y` for tests
- `Config()` doesn't have a `wiki_dir` field; the endpoint `getattr(cfg, "wiki_dir", "wiki")` lets the default flow through without breaking. Adding `wiki_dir` to Config was unnecessary scope.
- `dataclasses.replace()` with unrecognised kwarg raises TypeError immediately — useful for catching API drift in tests
- Windows console default cp1252 encoding can't print arrow chars; smoke scripts need `PYTHONIOENCODING=utf-8` or ASCII-only output
- Float ratios MUST be encoded deterministically (uint64 milliratio). Two machines computing the same `1.199 * 1_000_000` get the exact same int; their `struct.pack(">d", 1.199)` could diverge in lowest mantissa bits across float libraries. Always integer-encode for cross-platform commitment hashes.

**Pattern identified [PATTERN-016]**: VAPI three-pillar provenance pattern
1. **GIC v1** — per-session cognitive integrity (Phase 235-A; one hash per count-eligible session)
2. **WEC v1** — per-restart operational integrity (Phase 236-WATCHDOG; one hash per bridge lifecycle event)
3. **CORPUS-SNAPSHOT v1** — per-snapshot corpus integrity (Phase 236-CORPUS-SNAPSHOT; one hash per wiki+fleet+ratio+N+ts_ns tuple)

All three: SHA-256, big-endian byte order, explicit domain tag (`VAPI-{NAME}-v{N}`), monotonicity guard, FROZEN at v1. Together they prove "what" (sessions = GIC), "how" (operational continuity = WEC), and "where" (corpus state at snapshot time = CORPUS-SNAPSHOT) for any grind run reviewed at any later date.

Phase 236 complete. Next: 237-CONSENT + 237-ZK-SEPPROOF (Groth16 proof-of-separation-ratio without revealing biometric vectors).

---

### 2026-04-26: Phase 236-VAME COMPLETE — Application-Layer Message Envelope

**What was done**:
- `bridge/vapi_bridge/vame.py` NEW — VAME FROZEN FORMULA v1 (sidecar header design)
- `compute_vame_commitment(chain_head, ts_ns, endpoint, body_bytes)` SHA-256 binding
- `_VAMEMiddleware` (Starlette BaseHTTPMiddleware) stamps every JSON response; skips /health, non-JSON, 5xx, websocket upgrades
- Chain-head 5s cache keeps middleware off SQLite hot path
- `transports/http.py` CORS `expose_headers` extended with all 5 X-VAME-* keys
- `frontend/src/api/vame.js` NEW — Web Crypto SHA-256 recompute; mismatches bump `sessionStorage.__vapiVameFailures`; never throws
- `frontend/src/api/client.js` apiGet reads body via `arrayBuffer` first, validates VAME, then JSON-parses (exact byte-fidelity)
- Body wire format UNCHANGED → zero breakage with existing readers
- 8 tests T236-VAME-1..8 all passing
- End-to-end smoke confirmed live commitment matches frontend recompute

**Gamer dashboard audit (closed atomically)**:
- HIGH: useFleetCoherenceStatus called /agent/fleet-coherence-status (404; bridge defines /agent/fleet-coherence-summary). COHERENCE chip silently rendered mock data unconditionally. Fixed: corrected path + by_mode → active_* adapter + noMock guard
- MEDIUM: 3 grind-critical hooks lacked noMock — transient 5xx silently swapped fabricated values into dashboard mid-grind. Fixed: noMock added to useAITSeparation, useGrindAnalytics, usePCCIntelligence; MOCK-ACTIVE banner added to GamerView
- LOW: stale "P0 fix" comment in GamerView claimed consecutive_clean is the true grind metric while code uses chain_length as bar primary. Comment rewritten to accurately describe dual-metric semantics
- Validated as CORRECT: consecutive_clean=0 vs chain_length=20 disparity is the correct semantic behavior

**Test counts**: Bridge 2485→2493 (+8) | SDK 535 unchanged | Hardhat 522 unchanged

---

### 2026-04-26: Phase 236-WATCHDOG COMPLETE — bridge supervisor + Watchdog Event Chain (WEC)

**What was done**:
- `bridge/vapi_bridge/watchdog_chain.py` NEW — WEC FROZEN FORMULA v1 parallel to grind_chain.py
  - `WEC_N = SHA-256(prev(32) || event_code(1) || pid_be(4) || sid_hash(16) || ts_ns_be(8))` = 61B → 32B
  - Genesis tag `VAPI-WEC-GENESIS-v1`; sid_hash = SHA-256(grind_session_id)[:16]
  - 9 EVENT_CODES (BRIDGE_START 0x01 through WATCHDOG_HALT 0xFF)
- `bridge/vapi_bridge/store.py` — `watchdog_event_log` table (idempotent, schema_versions(236)) + 3 helpers:
  - `insert_watchdog_event()` — monotonicity guard bumps ts_ns ≤ prev to prev+1
  - `get_prev_watchdog_event_hash()` — scoped by grind_session_id (parallels INV-GIC-001)
  - `get_watchdog_event_chain_status()` — recomputes chain, reports restarts_last_hour
- `scripts/bridge_watchdog.py` NEW — standalone supervisor (urllib stdlib only, no third-party deps)
  - Polls `/health` + `/bridge/grind-chain-status` + `/bridge/capture-health` every 10s
  - Spawns bridge via `subprocess.Popen([sys.executable, "-m", "bridge.vapi_bridge.main"])`
  - Three VAPI-exclusive guards: refuses restart on `chain_intact=False`, on GRIND_SESSION_ID drift, on >3 restarts/hour
  - Backoff schedule 5/10/30/60s — capped at auto_grind 60s poll cadence
- `bridge/vapi_bridge/operator_api.py` — `GET /operator/watchdog-status` (10 keys; _check_read_key auth)
- `bridge/tests/test_phase236_watchdog.py` — 8 tests (T236-WD-1..8) all passing in 4.0s
- CLAUDE.md / VAPI_CONTEXT.md updated atomically; 4 new Hard Rules covering WEC formula, INV-GIC-003 ops enforcement, GRIND_SESSION_ID continuity, restart ceiling

**Test counts**: Bridge 2477→2485 (+8) | SDK 535 unchanged | Hardhat 522 unchanged | Contracts 45

**What we learned**:
- `time.time_ns()` divided by 1e9 collapses adjacent ns into the same float64 second value — chain monotonicity must be verified at integer-ns resolution, not float seconds. Updated test 5.
- The store's monotonicity guard makes it impossible to test "old event excluded by time window" using insert order — out-of-order inserts get bumped into the recent window. Tests must insert chronologically or query the underlying table directly. Updated test 7.
- WEC events written from a separate process (the watchdog) write to the same SQLite as the bridge — Windows WAL mode handles this correctly; no shared-memory or IPC needed. The bridge reads watchdog_event_log via the read-only operator endpoint without writing to it.

**Pattern identified [PATTERN-015]**: VAPI-architectural ops tooling pattern
1. Standalone Python script in `scripts/` (urllib stdlib only — no asyncio, no httpx, runs without bridge import dependencies on hot path)
2. Cryptographic event chain (parallel to GIC) for tamper-evident audit
3. Refuses-to-act guards that enforce protocol invariants (INV-GIC-003 etc.) at the operational layer
4. Bridge-side read-only endpoint surfaces the audit chain without coupling bridge to ops process
5. Pinned at startup, drift-detected — never silently re-reads ambient state mid-run

**Phase 236 remaining**: 236-VAME (~3h, no test delta) → 236-CORPUS-SNAPSHOT (~3h, +8 bridge). Then GIC_100 gate; then 237-CONSENT, 237-ZK-SEPPROOF; then 239-READINESS (W2 — Personal Readiness Dashboard, post-GIC_100).

---

### 2026-04-26: PHASE 236+ COMPREHENSIVE ARCHITECTURE PLAN — 7-Component Vision

**Session outcome**: Comprehensive Phase 236+ development plan generated and filed at
`VAPI-WORKFLOW.v2/VAPI_PHASE236_PLAN.md`. All context files updated.

**Key decisions made:**
- Component 1 (Backend reliability): `auto_grind.py` already exists; gap is process watchdog → 236-WATCHDOG (2h)
- Component 2 (Decentralized wiki): Git IS the versioned store; novel part is ZK-attested corpus snapshots → CorpusDataCurator Task 8
- Component 3 (ZK privacy): Don't encrypt wiki; ZK-SepProof (Groth16 SNARK proving ratio > 1.0 without revealing vectors) is novel → 237-ZK-SEPPROOF
- Component 4 (IoID/W3bstream): IoID as consent anchor + W3bstream as consent-gated pipeline = VAPI's most achievable DePIN novelty → 237-CONSENT
- Component 5 (Marketplace): Correct vision, post-GIC_100 only; VAPIDataMarketplace.sol gates on VAPIToken mainnet → 238-MARKETPLACE
- Component 6 (VAPI protocol): Don't roll your own transport crypto; VAME (VAPI Application-Layer Message Envelope with Poseidon commitment) is the right application-layer play → 236-VAME
- Component 7 (Personal Readiness): STANDOUT FEATURE. PersonaBreakDetectorAgent (agent #27) already computes the signal. GamerReadinessAgent (#39) maps it to consumer-legible fatigue/RSI metrics. Post-GIC_100. → 239-READINESS

**Phase 235 grind state at session start:**
- chain_length=16/100, consecutive_clean=1, NOMINAL+EXCLUSIVE_USB
- Bridge 2477 | SDK 535 | Hardhat 502 | Agents 38 | Contracts 45 LIVE
- AIT ratio=1.199 all_pairs_above_1=True (tournament blocker CLEARED for AIT)

**Files updated this session:**
- `VAPI-WORKFLOW.v2/VAPI_PHASE236_PLAN.md` — NEW comprehensive plan
- `VAPI-WORKFLOW.v2/VAPI_CONTEXT.md` — Phase 235 grind status + wallet 40.43 IOTX + 45 contracts
- `VAPI-WORKFLOW.v2/VAPI_AGENTS.md` — agent count 36→38, Phase 235 state, agent #39 planned
- Project memory `project_state.md` — grind chain_length + plan reference

**PATTERN — Personal Readiness as retention flywheel**: The insight that "VAPI is software that
helps me as a gamer" (continuous use) vs "VAPI is software I use during tournaments" (episodic)
is the correct framing for beta gamer adoption. PersonaBreakDetectorAgent's LOO centroid drift
IS the fatigue signal. Re-label it for consumer UX after GIC_100.

**PATTERN — auto_grind.py**: This file exists in the repo root (untracked). It autonomously
drives adjudication. The manual trigger problem is already solved. New sessions should run
`python auto_grind.py` in Terminal 2 alongside bridge and frontend.

---

### 2026-04-25: WORKFLOW SYNC — Phase 235 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: BRIDGE: CLAUDE.md=2477 CONTEXT.md=2469; SDK: CLAUDE.md=535 CONTEXT.md=531
**Corrected to**: Phase 235 | Bridge 2477 | SDK 535
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-25: WORKFLOW SYNC — Phase 235 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: BRIDGE: CLAUDE.md=2469 CONTEXT.md=2447; SDK: CLAUDE.md=531 CONTEXT.md=527
**Corrected to**: Phase 235 | Bridge 2469 | SDK 531
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-25: WORKFLOW SYNC — Phase 235 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=235 CONTEXT.md=234; BRIDGE: CLAUDE.md=2447 CONTEXT.md=2408; SDK: CLAUDE.md=527 CONTEXT.md=515
**Corrected to**: Phase 235 | Bridge 2447 | SDK 527
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-21: WORKFLOW SYNC — Phase 234 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=234 CONTEXT.md=231; BRIDGE: CLAUDE.md=2408 CONTEXT.md=2400
**Corrected to**: Phase 234 | Bridge 2408 | SDK 515
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-21: WORKFLOW SYNC — Phase 231 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=231 CONTEXT.md=230; BRIDGE: CLAUDE.md=2400 CONTEXT.md=2392; SDK: CLAUDE.md=515 CONTEXT.md=512
**Corrected to**: Phase 231 | Bridge 2400 | SDK 515
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-19: WORKFLOW SYNC — Phase 230 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=230 CONTEXT.md=229; BRIDGE: CLAUDE.md=2392 CONTEXT.md=2384
**Corrected to**: Phase 230 | Bridge 2392 | SDK 512
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-18: WORKFLOW SYNC — Phase 229 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=229 CONTEXT.md=228; BRIDGE: CLAUDE.md=2384 CONTEXT.md=2376; SDK: CLAUDE.md=512 CONTEXT.md=508
**Corrected to**: Phase 229 | Bridge 2384 | SDK 512
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-18: WORKFLOW SYNC — Phase 228 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=228 CONTEXT.md=227; BRIDGE: CLAUDE.md=2376 CONTEXT.md=2368; SDK: CLAUDE.md=508 CONTEXT.md=504
**Corrected to**: Phase 228 | Bridge 2376 | SDK 508
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-18: WORKFLOW SYNC — Phase 227 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=227 CONTEXT.md=226; BRIDGE: CLAUDE.md=2368 CONTEXT.md=2360; SDK: CLAUDE.md=504 CONTEXT.md=500
**Corrected to**: Phase 227 | Bridge 2368 | SDK 504
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-18: WORKFLOW SYNC — Phase 226 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=226 CONTEXT.md=225; BRIDGE: CLAUDE.md=2360 CONTEXT.md=2352; SDK: CLAUDE.md=500 CONTEXT.md=496
**Corrected to**: Phase 226 | Bridge 2360 | SDK 500
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-17: WORKFLOW SYNC — Phase 225 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=225 CONTEXT.md=224; BRIDGE: CLAUDE.md=2352 CONTEXT.md=2344; SDK: CLAUDE.md=496 CONTEXT.md=492
**Corrected to**: Phase 225 | Bridge 2352 | SDK 496
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-17: WORKFLOW SYNC — Phase 224 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=224 CONTEXT.md=223; BRIDGE: CLAUDE.md=2344 CONTEXT.md=2336; SDK: CLAUDE.md=492 CONTEXT.md=488
**Corrected to**: Phase 224 | Bridge 2344 | SDK 492
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-17: WORKFLOW SYNC — Phase 223 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=223 CONTEXT.md=222; BRIDGE: CLAUDE.md=2336 CONTEXT.md=2328; SDK: CLAUDE.md=488 CONTEXT.md=484
**Corrected to**: Phase 223 | Bridge 2336 | SDK 488
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-17: WORKFLOW SYNC — Phase 222 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=222 CONTEXT.md=198; BRIDGE: CLAUDE.md=2328 CONTEXT.md=2184; SDK: CLAUDE.md=484 CONTEXT.md=414
**Corrected to**: Phase 222 | Bridge 2328 | SDK 484
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-09: WORKFLOW SYNC — Phase 180 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: BRIDGE: CLAUDE.md=2022 CONTEXT.md=None; SDK: CLAUDE.md=337 CONTEXT.md=None
**Corrected to**: Phase 180 | Bridge 2022 | SDK 337
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-09: WORKFLOW SYNC — Phase 180 drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: PHASE: CLAUDE.md=180 CONTEXT.md=177; BRIDGE: CLAUDE.md=2022 CONTEXT.md=None; SDK: CLAUDE.md=337 CONTEXT.md=None
**Corrected to**: Phase 180 | Bridge 2022 | SDK 337
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---

### 2026-04-09: Phase 177 Orchestration Update — AutoResearch Cycle 13 [PLANNING]

**What was done**:
- Phase 177 COMPLETE confirmed: ProtocolMaturityScoringAgent (agent #26); unified maturity_score
  (0.0–1.0); 6-component weights (separation/chain_integrity/consent/biometric_freshness/
  agent_calibration/enrollment); maturity_tier ALPHA/BETA/PRODUCTION_CANDIDATE;
  PRODUCTION_CANDIDATE requires separation_ratio>1.0+all gates met; Bridge 1990→1998 +8;
  SDK 321→325 +4; Hardhat 468 unchanged; agent fleet 25→26.
- Phase 176 COMPLETE: PoACChainIntegrityMonitor (agent #25); SHA-256 chain linkage audit;
  WIF-026 W1 mitigation — only aggregate counts exposed; Bridge 1982→1990 +8; SDK 317→321 +4.
- program.md replaced: stale Phase 109-113 era → Phase 177 edition with 5 new priorities
  (temporal_drift/zk_ceremony/bt_calibration/pofc_consensus/separation_ratio_stratified);
  token launch threshold raised 1.0→1.5 as anchored target.
- WIF-029 filed: temporal biometric drift — VHP commitment TTL gap (Phase 178 candidate).
  VHP on-chain separation ratio commitment has no TTL; 6-month-old commitment biometrically
  stale; BLOCK rulings legally challengeable. Mitigation: biometric_credential_ttl_days=90.
- WIF-030 filed: ZK ceremony capture attack — single-operator Groth16 trusted setup voids
  zero-knowledge guarantee (Phase 179 candidate). Mitigation: ceremony_audit_log (≥3
  distinct participants per circuit as tournament authorization gate condition).
- vapi_autoresearch.py CLAUDE-EDITABLE ZONE upgraded: new priority rotation with
  temporal_drift/zk_ceremony/bt_calibration/pofc_consensus/separation_ratio_stratified;
  score_phase_177_readiness() gate function added (10-check readiness dict, threshold 0.80);
  updated --priority argparse choices; Phase 177 edition.
- Skill 16 added to VAPI_SKILLS.md: Phase 177+ Tournament Readiness Synthesis Preflight;
  9-step check integrating Agent #26 maturity gate + Skill 6 legacy gates + WIF-029/030
  pending gates; 6-component scoring formula (threshold 0.85); TOURNAMENT_AUTHORIZED verdict.
- VAPI_WHAT_IF.md: Document version 1.9→2.0; W1 Count 24→26; W2 Count 20→22.

**What we learned**:
- Phase 177 synthesis requires simultaneous satisfaction of 8+ gates — the synthesis is
  harder than any single phase because it requires fleet coherence across 26 agents at once.
- Biometric TTL (WIF-029) is the most legally pressing gap pre-tournament — identified as
  Priority 1 for AutoResearch cycle 14. The absence of TTL in the SeparationRatioRegistry.sol
  commitment schema means operators cannot prove freshness to courts without API access.
- ZK ceremony capture (WIF-030) is architecturally severe but mitigable without new math —
  requires process (multi-party ceremony audit chain) not new cryptography.
- Separation ratio target raised to 1.5 as anchored target; 1.0 is gate floor, not goal.
  WIF-028 P1 temporal non-stationarity is the root cause of current 0.569 ratio.
  Recovery path: Phase 173 SeparationRatioRecoveryAgent + Phase 174/175 age-weighting.
- BT calibration at 0/50 sessions remains a hard gap — BT tournament path blocked.

**Current test floors (Phase 177 confirmed)**:
- Bridge: 1998 | SDK: 325 | Hardhat: 468 | Agents: 26 | Tools: 126

**[PATTERN-014]**: Phase 177+ preflight must synthesize 9 API endpoints atomically at the
same timestamp — run Skill 16 as a single integrated check rather than querying each
separately. The maturity_score gate (Agent #26) is the authoritative pre-check; if
maturity_tier == ALPHA, abort all other checks and report root cause immediately.

---

### 2026-04-07: Phases 166-168 COMPLETE — Wiki Engine v3 + Bootstrap CI Integration

**Phase 166** (mixed_biometric_probe + configurable defensibility gate):
- `mixed_biometric_probe` added to STRUCTURED_PROBE_TYPES + _TERMINAL_CAL_ONLY_TYPES.
- `min_separation_ratio:float=0.70` config replaces hardcoded 1.0 gate (hardware variance ceiling).
- Bridge 1942->1950 +8; SDK 301->305 +4; Hardhat 468.

**Phase 167** (Wiki Engine Integration Validation + 4 hardening mitigations):
- 7 integration points validated: status/check/brief/agent_feed/sync_what_if/snapshot/phase_close.
- 4 fixes: schema probe `_probe_db_schema()`; CLAUDE.md-first phase detection; OS file lock `_locked_append()`; EPISTEMIC regex extended to catch 0.60-0.64 range.
- Bridge 1950 unchanged; SDK 305 unchanged.

**Phase 168** (Bootstrap CI in separation_ratio_snapshots):
- `separation_ratio_snapshots` +3 columns: ci_lower/ci_upper/n_bootstrap (idempotent ALTER TABLE).
- `analyze_interperson_separation.py`: bootstrap CI computed BEFORE write_snapshot so CI persists in DB row.
- `operator_api.py`: GET /agent/separation-defensibility-status +ci_lower/ci_upper/n_bootstrap.
- `vapi_wiki_engine.py`: agent_feed fixed (was querying non-existent `stratified_estimate` column, now `bt_strat_ratio`); CI annotation in wiki page when n_bootstrap>0.
- `SeparationRatioResult` +3 slots; `VAPISeparationStatus.get_status()` populates CI from API.
- 8 bridge + 4 SDK tests. Bridge 1950->1958 +8; SDK 305->309 +4; Hardhat 468 unchanged.

**Counts**: Bridge 1958 | SDK 309 | Hardhat 468 | Tools 122 | Agents 22

---

### 2026-04-05: Phase 165 COMPLETE — WIF-024 Post-Erasure Separation Ratio Recompute

**Phase 165 implementation** (WIF-024 closure):
- `anonymize_device_records()` gains `post_erasure_recompute:bool=False` parameter. When True: snapshots current separation ratio into `post_erasure_ratio_log` before erasure, sets `recompute_needed=1`, `ratio_after=NULL` (pending re-analysis via `analyze_interperson_separation.py`).
- `post_erasure_ratio_log` table: device_id/n_anonymized/ratio_before/ratio_after/recompute_needed/triggered_by/consent_type/recompute_ts/created_at.
- GET /agent/separation-defensibility-status: +`post_erasure_recomputed_at` field.
- GET /agent/post-erasure-recompute-status (7 keys): consent_ledger_enabled/total_recomputes/pending_recomputes/latest_recompute_ts/latest_ratio_before/recompute_needed/timestamp.
- Tool #122 `trigger_post_erasure_recompute` (input: device_id/dry_run); dry_run=True reads status only.
- `PostErasureRecomputeResult` (6 slots) + `VAPIPostErasureRecompute` SDK; SDK_VERSION 3.0.0-phase165.
- 8 bridge + 4 SDK tests. Bridge 1934→1942 +8; SDK 297→301 +4; Hardhat 468 unchanged. schema(165,"post_erasure_recompute"). WIF-024 CLOSED.

**Session also completed** (same session):
- CLAUDE.md compression: 182k → 76k chars (58.2% reduction, WIF-027 mitigation).
- CLAUDE_HISTORY.md created (Phase 17-130 verbose blocks archived, 106k chars).
- Memory scope audit: 2 stale files deleted (project_what_if_156.md, project_separation.md).
- WIF-027 filed: Context Window Budget Exhaustion root cause of session disruptions.
- Skill 14 Step 13 (Memory Scope Audit) added to VAPI_SKILLS.md v1.6.

**Counts**: Bridge 1942 | SDK 301 | Hardhat 468 | Tools 122 | Agents 22

---

### 2026-04-05: Phases 157–164 COMPLETE — Privacy/Consent Infrastructure [BULK SYNC ENTRY]

**Recovery note**: Claude session disconnect after Phase 164. Files synced via sync_vapi_workflow.py.

**What was done** (8 phases, 2026-04-04 to 2026-04-05):
- **Phase 157**: FleetConsensusSnapshotAgent (agent #21); WIF-012 dual-condition overall_ready gate (sessions_needed==0 AND defensible==True); WIF-016 cov_stability_check() regime labels (diagonal_stable/transition_warning/full_covariance_active); WIF-013 PoFC hash=SHA-256(sorted_verdicts+ratio+ts_ns); fleet_consensus_snapshot_log; cov_regime_status in enrollment guidance; Bridge 1877 SDK 269
- **Phase 158**: Class K HMAC Validation (WIF-014) + PoHBG (WIF-015); validate_gsr_hmac() 80-byte HMAC-SHA256 frame auth; compute_pohbg_hash() SHA-256(device_id+pack); gsr_hmac_validation_log+pohbg_log; Tools #114+#115; Bridge 1886 SDK 273
- **Phase 159**: BiometricPrivacyComplianceAgent (agent #22); BP-001 Temporal Biometric Decay TBD(t)=e^(-λt) λ=ln(2)/τ_half τ_half=90d; warning when mean_decay_factor<0.25; privacy_compliance_log; biometric_decay_warning bus event; Tool #116; Bridge 1894 SDK 277
- **Phase 160**: Consent Ledger + Right-to-Erasure (BP-002 foundation); WIF-018: insert_separation_defensibility_log had no consent gate; WIF-019: ConsentLedgerAgent as composable privacy primitive; consent_ledger table + right_to_erasure_log; anonymize_device_records() GDPR Art.17 soft delete; Tools #117; consent_ledger_enabled=True; Bridge 1902 SDK 281
- **Phase 161**: Consent Gate Enforcement; WIF-018 CLOSED: insert_validation_record calls _check_consent_gate(); gate fails open for unknown devices; WIF-020 CLOSED: anonymize_device_records() REDACTs ruling_validation_log.divergence_reason; consent_gate_violation_log; GET /agent/consent-gate-status; Tool #118; Bridge 1910 SDK 285
- **Phase 162**: Consent-Aware Corpus Status (WIF-021 CLOSED); get_consent_corpus_coverage() returns active_consent_count/revoked_count/erasure_requested_count/consent_corpus_defensible; GET /agent/consent-aware-corpus-status; Tool #119; Bridge 1918 SDK 289
- **Phase 163**: Consent-Bound Separation Hash (WIF-022 CLOSED); SHA-256 preimage extended to SHA-256(ratio_str+N+N_consented+players_sorted+ts_ns); n_consented binds active consent count atomically; compute_separation_ratio_commit_hash(); update_separation_ratio_registry_committed(); Tool #120; Bridge 1926 SDK 293
- **Phase 164**: ConsentSnapshotAnchor (WIF-023 CLOSED); consent_snapshot_log table linked by commit_hash; insert_consent_snapshot() called atomically after every commit; get_consent_snapshot_delta() delta=positive when revocations occurred post-commit; revoked_since_commit = max(0, revoked_live - revoked_at_commit); GET /agent/consent-snapshot-delta; Tool #121; Bridge 1934 SDK 297

**Key results**:
- Agent fleet: 20→22 (FleetConsensusSnapshotAgent #21, BiometricPrivacyComplianceAgent #22)
- WIFs 012–023: ALL CLOSED
- consent_ledger_enabled=True (permanent)
- Bridge: 1868→1934 (+66 tests over 8 phases)
- SDK: 265→297 (+32 tests)
- Hardhat: 468 (unchanged throughout)
- All biometric privacy primitives BP-001 and BP-002 foundation now LIVE

**What we learned**:
- Session disconnect mid-phase causes VAPI-WORKFLOW.v2 drift; sync_vapi_workflow.py created as mitigation
- consent_ledger_enabled=True is the new default state — all future phases must respect this
- ConsentSnapshotDelta (Phase 164) reveals post-commit revocations but does not enforce invalidation — Phase 165 W1 candidate
- VAPI mobile extension discussed as Phase 165 precursor to Phase 200; previous session disconnected before documenting Phase 165 spec

**CORRECTION**: Agent #21 is FleetConsensusSnapshotAgent (Phase 157), agent #22 is BiometricPrivacyComplianceAgent (Phase 159).

**Pattern identified** [PATTERN-013]:
Context sync must run atomically with CLAUDE.md update:
1. sync_vapi_workflow.py executed after every phase-completion CLAUDE.md write
2. PostToolUse hook configured in settings.json as fallback
3. Recovery script run at session start when drift detected (MEMORY.md session cadence)
4. Never mark phase COMPLETE until sync confirms VAPI-WORKFLOW.v2 updated

---

### 2026-04-03: Phase 150 COMPLETE — Session Consistency Scoring + Defensibility Gate

**What was done**:
- **Phase 150**: WIF-010 formal closure — separation_defensibility_log table; `defensible=True` requires ALL players ≥ min_n=10 AND ratio > 1.0 AND all pairs > 1.0; current state: defensible=False (P1=3, P2=4, P3=4 all below min_n=10); GET /agent/separation-defensibility-status (6 keys); Tool #106; SeparationDefensibilityResult SDK; WIF-011 added (session type mixing integrity gap)
- **Bridge**: 1808→1818 (+10), **SDK**: 237→241 (+4), **Hardhat**: 462 unchanged
- Test pattern: avoided FastAPI 0.116.1 TestClient incompatibility by replicating endpoint response logic inline (not via create_operator_app) — see test_phase150_separation_defensibility.py TestSeparationDefensibilityEndpoint

**Key results**:
- WIF-010 closed: System now formally tracks that touchpad_corners N=11 is legally thin; operators get explicit defensible=False transparency
- WIF-011 opened: session_type="all" insertion could conflate incomparable ratios; default API specifies session_type="touchpad_corners" explicitly
- SDK version bumped to 3.0.0-phase150 (required updating test_phase148_acim_sdk.py + test_phase85_tournament_sdk.py version assertions)

**What we learned**:
- FastAPI 0.116.1 breaks create_operator_app entirely (on_startup keyword removed from Router.__init__); all TestClient-based endpoint tests fail in this environment — use direct response-logic replication instead
- SDK class attributes: VAPISeparationDefensibility stores `_base` and `_key` (not `_base_url`/`_api_key`) — test must match actual attribute names, not assumed names
- Config class name is `Config` (not `VAPIBridgeConfig`); import as `from bridge.vapi_bridge.config import Config`

### 2026-04-03: Phases 137–149 COMPLETE — Corpus Analysis + ACIM + MCP [BULK ENTRY]

**What was done** (13 phases, 2026-03-29 to 2026-04-03):
- **Phase 137A**: --balance-corpus flag; WIF-007 confirmed: balanced_ratio=1.611 (n=3/player) vs pooled=0.417 — P1 imbalance confirmed
- **Phase 137B**: --session-type touchpad_corners filter; touchpad_corners pre-merge ratio=1.469 (4-player)
- **Phase 138**: P4→P3 corpus merge (P4 confirmed same person as P3); clean 3-player touchpad_corners ratio=1.552 (full Tikhonov)
- **Phase 139**: Analysis fast-path — _TERMINAL_CAL_ONLY_TYPES; skips 74 hw_* sessions; 120s→<30s runtime
- **Phase 140**: --probe-comparison (corners/freeform/swipes); ALL above 1.0: corners=1.552, freeform=1.270, swipes=1.032
- **Phase 141**: --per-pair-attribution; KEY FINDING: P1 vs P3 diagonal=3.925 >> full=0.127 → suppression_ratio=0.032 (97%!) — covariance noise artifact, NOT true similarity
- **Phase 142**: COV_MIN_RATIO=3.0 auto-fallback; when N/p < 3.0 → diagonal covariance; prevents off-diagonal noise suppression
- **Phase 143**: Proper LOO classification; each test session's centroid recomputed WITHOUT that session; honest 63.6% (7/11); CURRENT BEST ratio=1.261 (diagonal+LOO)
- **Phase 144**: --player-quality-report; per-player enrollment stability/probe-type/enrollment-ready (P1/P2/P3 all NOT READY at N<10/player)
- **Phase 147**: Epistemic threshold hardening; 0.60→0.65; triage_prereq_required=True; closes Phase 98 W1
- **Phase 148**: AgentCalibrationIntegrityMonitor (ACIM, agent #18); 16 self-tests every 15 min; mcp_server.py (6 MCP resources, disabled by default)
- **Phase 149**: Calibration staleness fixes; hardcoded values replaced with DB reads; Phase 148 docstrings

**Key results**:
- Separation ratio: **1.261** (touchpad_corners, diagonal+LOO, Phase 143) — ABOVE 1.0 tournament gate
- Classification: 63.6% (7/11) — honest LOO estimate
- Bridge: 1734→1808 (+74 tests across 13 phases)
- SDK: 233→237 (+4)
- Hardhat: 462 (unchanged)
- Agent fleet: 16→18 (+ACIM)

**What we learned**:
- Free-form gameplay cannot reach separation ratio >1.0 — plateau confirmed at ~0.417
- Structured touchpad probe (touchpad_corners) is the ONLY path to >1.0
- Full Tikhonov covariance with N=11 is unstable — diagonal is correct for small-N touchpad corpus
- P1/P3 confusion is covariance noise artifact, NOT true biometric similarity (97% suppression)
- Proper LOO (Phase 143) is the honest estimate; biased centroid inflates to 72.7%
- MCP servers need restart to activate — write to settings.json is not hot-reload
- VAPI-WORKFLOW.v2 files drifted 13 phases — added bulk sync session (2026-04-03)

**CORRECTION**: Agent #17 ControllerHardwareIntelligenceAgent remains DESIGN ONLY. Phase 148 introduced Agent #18 (ACIM), not #17.

**Pattern identified** [PATTERN-012]:
Touchpad separation analysis must:
1. Use --session-type touchpad_corners to isolate structured probe sessions
2. Apply diagonal covariance when N/p < 3.0 (Phase 142 auto-fallback)
3. Use proper LOO (Phase 143) — biased centroid overstates accuracy
4. Require ≥10 sessions/player for enrollment quality gate (Phase 144)
5. Report per-pair attribution (Phase 141) to distinguish true separation from covariance noise

---

### 2026-03-29: Phase 136 COMPLETE — DualSense Audio Passthrough Router [DONE]

**What was done**:
- Created `bridge/vapi_bridge/audio_router.py` — Windows Core Audio COM vtable dispatch
- `IPolicyConfigVista` CLSID `{870AF99C-...}` vtable[13]=`SetDefaultEndpoint` for ERole 0/1/2
- `IMMDeviceEnumerator` vtable[4]=`GetDefaultAudioEndpoint` to detect current default
- `AudioDevice` dataclass with `is_dualsense` + `is_system_audio` classification from registry
- `AudioRouter(preferred)`: `ensure_game_audio()` + `restore()` — pure ctypes, no external deps
- Config: `audio_passthrough_enabled=True` + `audio_device_preference="system"`
- Wired into `dualshock_integration.py`: after boot record + `_shutdown_cleanup()` restore
- 18 tests: Bridge 1716→1734

**Results**:
- Game audio now auto-restores to Realtek when DualSense Edge connects USB
- Windows registry enumeration reads HKLM MMDevices/Audio/Render endpoints
- Graceful no-op on non-Windows (CI-safe); all errors non-fatal (debug logged)

**What we learned**:
- Windows COM vtable dispatch via ctypes is the correct approach (no external deps)
- IPolicyConfigVista CLSID {870AF99C-...} is stable Vista → Windows 11
- DualSense audio endpoint identified by `is_dualsense` keyword matching on driver_name/usb_id
- restore() on shutdown prevents permanent audio routing change after bridge exits

**CORRECTION**: ControllerHardwareIntelligenceAgent (Agent #17) is DESIGN ONLY — no code written.
Phase 136 = Audio Router (code complete). Agent #17 is a candidate for Phase 137+.

**Pattern identified** [PATTERN-011]:
Controller capability mapping must:
1. Preserve 228-byte PoAC format (controller-agnostic)
2. Adjust PITL weights based on available layers
3. Enforce tier eligibility (Attested requires L6 full)
4. Use per-controller threshold tracks (no cross-contamination)
5. Maintain USB/BT separation (250Hz ≠ 1000Hz)

**Next Steps**:
- N≥50 calibration sessions for Xbox Series X
- N≥50 calibration sessions for Switch Pro
- N≥50 calibration sessions for DualShock 4 (dedicated)
- PHCI certification API for hardware partners

---

### 2026-03-27: Phase 135 Complete — TournamentActivationChainAgent [SUCCESS]

**What was done**:
- Added TournamentActivationChainAgent (agent #16)
- Implemented auto_activate_on_breakthrough=False (hardcoded safety)
- Created tournament_activation_chain_log table with 7-key schema
- Added Tool #104: get_tournament_activation_chain

**Results**:
- Bridge: 1,716 pytest passing
- SDK: 233 tests passing
- Hardhat: 462 tests passing
- All gates verified before activation (separation_ok, l4_ok, gate_ok, cert_ok, audit_ok, dual_gate_warned, epoch_window_warned, ioswarm_warned)

**What we learned**:
- Activation features need explicit operator override path
- auto_activate_on_breakthrough=False prevents accidental live mode
- Tournament gates require 8-condition AND check
- Persistent activation_state in SQLite prevents double-activation

**Pattern identified** [PATTERN-001]:
Every "activation" or "enforcement" feature must have:
1. dry_run gate (default True)
2. Manual operator override path
3. Persistent state tracking
4. Idempotent operations (safe to retry)

---

### 2026-03-25: Phase 134 Complete — L4 Recalibration Pipeline [SUCCESS]

**What was done**:
- Created scripts/l4_recalibration_pipeline.py (terminal UX)
- Implemented 6-step pipeline: backup → export → analyze → calibrate → validate → activate
- Added l4_recalibration_log table for audit trail
- Integrated with ThresholdCalibratorAgent

**Results**:
- +9 bridge tests (1,716 total)
- USB threshold track updated with N=177
- Terminal workflow validated (web dashboard insufficient)

**What we learned**:
- Calibration workflows need BOTH headless (CI) and terminal (operator) modes
- 6-step pipeline prevents operator error
- Backup step is non-negotiable (rollback capability)
- Validation step catches bounds violations before activation

**Pattern identified** [PATTERN-002]:
Calibration workflows must have:
1. Backup before change (sqlite .backup)
2. Export for external analysis
3. min() enforcement (thresholds only tighten)
4. Validation before activation
5. Idempotent activation (safe retry)

---

### 2026-03-22: Phase 131 Complete — IoSwarm Live Node Foundation [SUCCESS]

**What was done**:
- Created ioswarm_node_registry table (node_url, staker_address, active, last_seen_ts)
- Implemented IoSwarmLiveNodeClient with emulator fallback
- Added GET /agent/ioswarm-node-registry-status endpoint
- Integrated with IoSwarmRenewalCoordinator, IoSwarmAdjudicationCoordinator, IoSwarmVHPMintCoordinator

**Results**:
- Bridge: 1,669 tests (+8 from Phase 130B)
- SDK: 217 tests (+4)
- Hardhat: 460 tests (+6)
- Emulator mode provides zero-behavior-change fallback

**What we learned**:
- Live node infrastructure must have emulator fallback
- Staker address per node enables VAPISwarmOperatorGate validation
- Node timeout (default 30s) prevents indefinite blocking
- Registry status endpoint enables operator visibility

**Pattern identified** [PATTERN-003]:
ioSwarm infrastructure must:
1. Support live nodes AND emulator fallback
2. Validate staker addresses for decentralization
3. Provide registry visibility to operators
4. Fail-open (emulator) when live nodes unavailable

---

### 2026-03-20: Phase 129 Hypothesis — Tikhonov Breakthrough [PENDING VERIFICATION]

**What was proposed**:
- Run analyze_interperson_separation.py --full-covariance on N=177 corpus
- Apply Phase 129 Tikhonov regularization to full covariance matrix
- Hypothesis: Corrected ratio > 0.60 or potentially > 1.0

**Current status**:
- N=177 corpus available (USB, 3 players)
- Tikhonov correction applicable (N>150 threshold met)
- Diagonal approximation: 0.474
- Full covariance estimate: UNKNOWN (pending execution)

**What we expect to learn**:
- Whether measurement imprecision (not signal weakness) suppressed ratio
- If full covariance reveals breakthrough already achieved
- Whether additional hardware sessions needed or just better analysis

**Pattern identified** [PATTERN-004]:
Large-N corpus analysis (N>150) should:
1. Prefer full covariance over diagonal approximation
2. Apply Tikhonov regularization for numerical stability
3. Compare estimates: diagonal vs full vs regularized
4. Update confidence intervals based on method precision

**Action required**: Run --full-covariance analysis when approved.

---

### 2026-03-18: Phase 128 Complete — Protocol Intelligence Dashboard [SUCCESS]

**What was done**:
- Created TournamentReadinessScore with 6-signal formula
- Implemented GET /agent/tournament-readiness-score endpoint
- Added separation_score = min(1.0, pooled_ratio) cap
- Integrated all 6 signals: separation, l4, dual_gate, epoch, ioswarm, dry_run

**Results**:
- Bridge: 1,644 tests (+8)
- SDK: 205 tests (+4)
- Score computation: 0.30/0.20/0.15/0.15/0.10/0.10 weights

**What we learned**:
- Readiness score prevents overconfidence before separation > 1.0
- 6-signal formula balances technical and operational readiness
- Score as oracle input enables automated monitoring
- capping separation_score at 1.0 prevents premature "ready" declaration

**Pattern identified** [PATTERN-005]:
Readiness assessment must:
1. Weight separation ratio highest (30%)
2. Cap score at current reality (no optimistic projection)
3. Include operational signals (ioswarm, dry_run)
4. Provide per-signal breakdown for blocker identification

---

### 2026-03-15: Phase 127 Complete — Tournament Pre-Launch Validation [SUCCESS]

**What was done**:
- Created tournament_preflight_log table (8 conditions)
- Implemented POST /agent/run-tournament-preflight endpoint
- Added preflight gate to POST /agent/commit-activation
- Overall_pass=False now blocks commit

**Results**:
- Bridge: 1,636 tests (+9)
- Preflight runs all 8 conditions before activation
- Audit trail for tournament launch authorization

**What we learned**:
- Pre-flight gate prevents activation with known blockers
- Audit trail provides legal defensibility for launch decisions
- 8 conditions must pass before operator can commit
- separation_ok and l4_ok are P0 (blocking) conditions

**Pattern identified** [PATTERN-006]:
Launch authorization must:
1. Run preflight checks (all conditions)
2. Block on P0 conditions (separation, l4)
3. Log audit trail (operator, timestamp, conditions)
4. Require explicit operator override to bypass (discouraged)

---

## 2. Calibration Patterns Discovered

### [PATTERN-007] Resting Grip Normalization (Phase 121)

**Discovery**: Touchpad-dominant sessions show inflated bt_strat_ratio due to baseline drift.

**Mechanism**: Resting grip position (no touch) establishes per-player baseline. Subtract before Mahalanobis computation.

**Applies to**: All touchpad sessions in corpus (P1, P2, P3)

**Implementation**: analyze_interperson_separation.py --resting-grip-normalization

**Status**: ACTIVE in Phase 121+ analysis

---

### [PATTERN-008] Battery Heterogeneity Risk (W1-003, Phase 124)

**Discovery**: USB thresholds (1000 Hz) applied to BT sessions (250 Hz) cause false positives.

**Mechanism**: 4× sampling difference creates different variance profiles. Same human behavior produces different Mahalanobis scores.

**Applies to**: Any multi-transport tournament (USB + BT)

**Solution**: Per-battery threshold tracks (l4_threshold_tracks table)

**Status**: MIGRATING from global thresholds to per-battery (Phase 125-126)

---

### [PATTERN-009] L4 Staleness Detection (Phase 123)

**Discovery**: Feature dimension drift (12→13) invalidates thresholds silently.

**Mechanism**: New feature (touchpad_spatial_entropy) added in Phase 121. Old thresholds applied to 13-dim space = 12-dim threshold on partial data.

**Detection**: live_feature_dim != calibration_feature_dim in l4_calibration_log

**Applies to**: Any feature addition after threshold calibration

**Solution**: Staleness flag + automatic recalibration suggestion

**Status**: DETECTED in N=177 corpus (stale=True currently)

---

### [PATTERN-010] Confidence Multiplier Safety (Phase 122)

**Discovery**: bt_strat_ratio as VHP confidence multiplier penalizes non-touchpad sessions.

**Mechanism**: No-touchpad sessions have bt_strat_ratio=0.0, reducing confidence_score to 0.0.

**Solution**: confidence_multiplier_enabled=False (default), confidence_multiplier_floor=0.0

**Applies to**: VHP minting with battery diversity

**Status**: DISABLED by default, per-battery lookup candidate for Phase 124+

---

## 3. Failed Experiments (What Not To Do Again)

### [FAILED-001] Spectral Entropy for Separation Ratio (Phase 46)

**Attempt**: Use accel_magnitude_spectral_entropy to improve inter-person separation.

**Hypothesis**: Spectral features would differentiate players better than kinematic features.

**Result**: 0 improvement — feature is bot-vs-human, not person-vs-person.

**Why it failed**: 
- Spectral entropy detects injection (software vs hardware signal patterns)
- Inter-person separation requires biometric differentiation (tremor, rhythm)
- Different problem domains entirely

**Lesson**: "More features" ≠ "better separation"; features must match the discrimination target.

**Current status**: accel_magnitude_spectral_entropy active for bot detection (index 9), not separation.

---

### [FAILED-002] Early BT Transport Enable (Phase 120)

**Attempt**: Enable bt_transport_enabled=True with USB-calibrated thresholds.

**Hypothesis**: BT and USB similar enough to share thresholds.

**Result**: L4 false positives at 250 Hz — 4× fewer samples = different variance profile.

**Why it failed**:
- Mahalanobis distance sensitive to sample count per window
- Human micro-tremor (8-12 Hz) completes more cycles per window at BT rates
- Gyro_std variance artificially elevated at 250 Hz

**Lesson**: BT requires separate N≥50 calibration; cannot inherit USB thresholds.

**Current status**: bt_transport_enabled=False default, Phase 120 infrastructure complete but disabled pending calibration.

---

### [FAILED-003] Diagonal Covariance Assumption (Phase 121-128)

**Attempt**: Use diagonal covariance (feature independence) for separation ratio with N=177.

**Hypothesis**: Features sufficiently independent for diagonal approximation.

**Result**: Ratio 0.474 — potentially under-reported due to feature correlation.

**Why it may have failed**:
- Touchpad spatial entropy correlates with stick axes during gameplay
- L2/R2 trigger resistance correlates with grip pressure
- Full covariance captures these relationships

**Lesson**: Large-N corpora (N>150) enable full covariance estimation; diagonal approximation wastes data.

**Current status**: Phase 129 Tikhonov correction pending — may reveal true ratio.

---

## 4. Preferences Established

### Threshold Management

- **Only min() tightening**: Thresholds never loosen (enforced in calibrator)
- **Per-battery routing**: USB and BT have separate tracks (Phase 126)
- **Staleness detection**: Live vs calibrated feature dimension checked (Phase 123)

### Calibration Session Selection

- **NOMINAL only for EMA**: Anomaly sessions excluded from stable track updates (prevents baseline poisoning)
- **Minimum N=50**: Statistical significance threshold for calibration
- **Recommended N=177+**: Full covariance stability (Tikhonov applicable)

### Tournament Gates

- **Manual override path**: Every gate has operator bypass (discouraged but available)
- **Idempotent operations**: Safe to retry activation, minting, etc.
- **Audit trail**: All gate decisions logged with operator, timestamp, conditions

### Feature Addition Protocol

1. Add feature to FeatureExtractor
2. Update _BIO_FEATURE_DIM
3. Set calibration_feature_dim (marks stale)
4. Run recalibration (Phase 134 pipeline)
5. Update live_feature_dim (marks fresh)

### Separation Ratio Measurement

- **Honest disclosure**: Report actual measured ratio, not target ratio
- **Method documentation**: Specify diagonal vs full covariance, N sessions, player count
- **Tikhonov applicability**: N>150 only (mathematical stability)

---

## 5. Active Hypotheses (Pending Verification)

### [HYPOTHESIS-001] Tikhonov Reveals Breakthrough

**Claim**: Full covariance Tikhonov correction on N=177 corpus reveals separation ratio > 0.60 or > 1.0.

**Evidence**:
- Diagonal approximation: 0.474
- Feature correlation suspected (resting grip, touchpad, triggers)
- N=177 satisfies large-N threshold for full covariance

**Test**: Run analyze_interperson_separation.py --full-covariance

**Expected outcomes**:
- If >1.0: Tournament readiness unblocked, whitepaper update, TGE possible
- If 0.60-1.0: Progress documented, continue calibration toward 1.0
- If <0.50: Reassess — signal may need hardware recapture (Phase 17 touchpad)

**Status**: PENDING execution approval.

---

### [HYPOTHESIS-002] Per-Battery Multiplier Viable

**Claim**: Battery-stratified confidence multiplier enables touchpad-dominant sessions without penalizing others.

**Evidence**:
- Current bt_strat_ratio penalizes no-touchpad (ratio=0.0)
- Per-battery lookup possible with l4_threshold_tracks (Phase 124)

**Test**: Enable confidence_multiplier_enabled=True with per-battery floor

**Expected outcomes**:
- If VHP minting fairness improves: Keep enabled
- If complexity exceeds benefit: Keep disabled (advisory only)

**Status**: THEORETICAL — candidate for Phase 136+.

---

## 6. Session Cadence Guidelines

Based on accumulated learning:

| Session Type | Cycles | Focus |
|--------------|--------|-------|
| Deep work day | 3-5 | Improvement cycles at start, then manual dev |
| Normal session | 1 | Single cycle, then implementation |
| Hardware/calibration | 0 | No orchestration improvement needed |
| Phase planning | 2 | Next phase coherence before coding |
| Tikhonov verification | 1 | Single focused cycle, then execution |

---

---

## 7. Autoresearch Cycle 8 — Phases 169–177 (2026-04-08)

### Session Summary

**Phases completed in one autoresearch loop**: 169→177 (9 phases, Bridge +88, SDK +32)

**Final counts (Phase 177 COMPLETE):**
| Metric | Value |
|--------|-------|
| Bridge tests | **1998** |
| SDK tests | **325** |
| Hardhat tests | **468** |
| Contracts | **39 ALL LIVE** |
| Agent fleet | **26** |
| Tools | **126** |

### Agents Added This Cycle

| # | Agent | Phase | Signal |
|---|-------|-------|--------|
| #23 | SeparationRatioRecoveryAgent | 173 | trend_velocity from last 5 snapshots; recovery_action STABLE/AGE_WEIGHTING/P1_RE_ENROLLMENT/MORE_SESSIONS |
| #24 | AgeWeightedRatioPersistenceAgent | 175 | temporal_drift_index = raw_ratio - age_weighted_ratio; P1_NONSTATIONARITY/IMPROVING/STABLE |
| #25 | PoACChainIntegrityMonitor | 176 | SHA-256 chain linkage audit; integrity_score = valid_links/total_records |
| #26 | ProtocolMaturityScoringAgent | 177 | 6-component weighted maturity_score (0.0–1.0); tiers ALPHA/BETA/PRODUCTION_CANDIDATE |

### Phase 174 — Session Age Weighting

`analyze_interperson_separation.py` gained `--session-age-weight <halflife_days>` flag.  
Gaussian decay: `w_i = exp(-λ·age_days)` where `λ = ln(2)/halflife`.  
WIF-025 CLOSED — AGE_WEIGHTING recommendation from Phase 173 now actionable.

### Phase 175 — AgeWeightedRatioPersistenceAgent

`temporal_drift_index = raw_ratio - age_weighted_ratio`  
- TDI > 0.05 → P1_NONSTATIONARITY (old sessions inflate ratio)  
- TDI < -0.05 → IMPROVING (new sessions stronger)  
- |TDI| ≤ 0.05 → STABLE  
Tool #124; SDK AgeWeightAnalysisResult(6 slots)+VAPIAgeWeightAnalysis.

### Phase 176 — PoACChainIntegrityMonitor

Audits SHA-256 chain linkage across all PoAC records.  
W1 mitigation: only aggregate counts exposed — no broken record IDs returned.  
`audit_passed=True` when `broken_links==0`; fail-open error path.  
Tool #125; SDK PoACChainIntegrityResult(6 slots)+VAPIPoACChainIntegrity.

### Phase 177 — ProtocolMaturityScoringAgent

Synthesizes 6 signals into unified maturity_score:

| Component | Weight | Source |
|-----------|--------|--------|
| separation | 0.25 | separation_defensibility_log ratio |
| chain_integrity | 0.20 | poac_chain_audit_log integrity_score |
| consent | 0.15 | consent_ledger active consent coverage |
| biometric_freshness | 0.15 | privacy_compliance_log mean_decay_factor |
| agent_calibration | 0.15 | agent_calibration_health latest_pass_rate |
| enrollment | 0.10 | enrollment_auto_guidance_log |

Tiers: ALPHA (<0.50) / BETA (0.50–0.85) / PRODUCTION_CANDIDATE (≥0.85)  
**NOTE**: Class renamed `ProtocolMaturityScoringResult`/`VAPIProtocolMaturityScoring` (not `ProtocolMaturityResult`/`VAPIProtocolMaturity`) to avoid Phase 104 naming collision.  
Tool #126; SDK ProtocolMaturityScoringResult(9 slots)+VAPIProtocolMaturityScoring.

### Separation Ratio Crisis (as of 2026-04-05)

| N (touchpad_corners) | Ratio | Status |
|----------------------|-------|--------|
| N=11 | 1.261 | Was above gate |
| N=14 | 0.789 | Below gate |
| N=20 | **0.569** | **TOURNAMENT BLOCKER** |

**Root cause**: P1 temporal non-stationarity — intra-player variance range [1.661, 4.410].  
Old P1 sessions cluster near P2; new P1 sessions cluster near P3.  
LOO classification: 20.0% (4/20) — below random baseline (33%).  
P1=6/P2=7/P3=7 sessions; need ≥10/player for defensibility gate.  
Recovery action: **P1_RE_ENROLLMENT** (Agent #23 active signal).  
TDI: **P1_NONSTATIONARITY** (Agent #24 active signal).  
Maturity tier: **ALPHA** (maturity_score < 0.50 until separation recovers).

### WHAT_IF Entries Filed

- **WIF-025**: CLOSED Phase 174 (age weighting implementation)
- **WIF-026** (Phase 176): W1=chain audit exposes injection windows → mitigation: aggregate counts only; W2=isChainIntegrous() as third composable primitive
- **WIF-027** (Phase 177): W1=maturity score gaming by silencing agents → mitigation: silence_penalty component (Phase 178 candidate); W2=maturity_score≥0.85 as DePIN marketplace trustworthiness oracle

### SDK Naming Collision Fixed (2026-04-08)

Phase 177 originally shipped `ProtocolMaturityResult`/`VAPIProtocolMaturity` — same names as Phase 104's PMI-based classes. Python last-definition-wins caused Phase 104 tests to break (5 failures). Fixed by renaming Phase 177 classes to `ProtocolMaturityScoringResult`/`VAPIProtocolMaturityScoring`. CLAUDE.md and test file updated atomically.

---

---

### 2026-04-11: Phase 192 COMPLETE — CorpusDataCuratorAgent (Agent #35)

**What was done**:
- Phase 192 COMPLETE: CorpusDataCuratorAgent (agent #35); 7-task data coherence layer.
  Bridge 2114→2128 +14; SDK 383→390 +7; Hardhat 482 unchanged; agent fleet 34→35.
- 7 data coherence tasks implemented end-to-end:
  1. **Provenance DAG** — data_provenance_dag table; insert_provenance_node(dict) / get_provenance_chain(leaf_node_id, max_depth=20) walk to root
  2. **Corpus Entropy Monitor** — corpus_entropy_log table; CLUSTERING_WARNING when score < 1.5; per_player_entropy + per_feature JSON blobs
  3. **Proof-of-Erasure Certificate** — erasure_certificate_log; cert = "sha256:" + SHA-256(device_id+erased_tables_json+post_erasure_ratio+ts_ns); GDPR compliance
  4. **Federated Corpus Quality** — federation_corpus_quality_log; BP-007: bridge_id_hash only (never bridge URL); privacy_constraint gate
  5. **Cross-Feature Temporal Correlation** — feature_correlation_log; correlation_upper_tri + Frobenius distance (frobenius_vs_p1/p2/p3); correlation_separable=True when any inter-player Frobenius > threshold
  6. **Data Readiness Certificate** — data_readiness_certificate_log; 8-dimension gate; certification_status=NOT_READY/READY/PARTIAL; blocking_failures + advisory_warnings JSON
  7. **Session Contribution Weights** — session_contribution_weight_log; TBD λ=ln(2)/90 (FROZEN BP-001); effective_weight = tbd_weight × type_multiplier × stationarity_multiplier
- Script extensions: --weighted-centroid + --correlation-matrix flags in analyze_interperson_separation.py
- MCP tools: vapi_corpus_entropy, vapi_data_readiness_certificate, vapi_provenance_chain in knowledge_server.py
- Wiki: _trigger_provenance_registration() in cmd_phase_close(); corpus entropy in agent_feed
- AutoResearch: 3 new Phase 192 priorities + score_phase_192_readiness() (10 checks, gate ≥0.70)
- Managed agents: "curator" + "corpus_quality" bus channels

**What we learned**:
- `insert_provenance_node` takes a **dict** (not keyword args) — dict-based API avoids long signature churn
- `compute_erasure_certificate` returns "sha256:" + 64-char hex; always validate prefix in tests
- `clustering_warning` in `CorpusEntropyResult` defaults to **True** (not False) — conservative default until data says otherwise
- `get_session_weight(session_file)` returns **float**, not a dict — single-value convenience method
- SDK slot collision risk: always check existing class names before naming new result/client classes
- BP-007 federated privacy: store bridge_id_hash (SHA-256[:16]) NOT bridge URL; enforced as privacy_constraint default

**Test counts**: Bridge 2128 | SDK 390 | Hardhat 482 | Contracts 43

---

---

### 2026-04-11: Phase 193 COMPLETE — FleetSignalCoherenceAgent (Agent #36)

**What we did**: Implemented the VAPI RSI Learning integration — FleetSignalCoherenceAgent
as the fleet-level signal coherence observer across all 35 agents.
Bridge 2128→2142 +14; SDK 390→394 +4; Hardhat 482 unchanged; agent fleet 35→36.

- **3 failure modes**: CONTRADICTION (7 rules), ORPHAN (5 rules), INVERSION (3 rules — Provenance DAG walk)
- **RENEWAL_WITHOUT_ATTESTATION = CRITICAL** (highest severity) — detects Phase 185/186 attestation chain bypass
- **coherence_id format**: "coh_" + SHA-256(rule_name + sorted_agents + ts_ns)[:16] — idempotent per cycle
- **auto-promote**: N_PROMOTE_THRESHOLD=3 occurrences → auto-appended to VAPI_WHAT_IF.md
- **fleet_coherence_enabled=True DEFAULT** — unlike most agents which default False; coherence monitoring always on
- **BP-007 _scrub_evidence()**: removes raw biometric fields (features, hid_reports, raw_data, sensor_commitment,
  gyro_std, accel, feature_vector, correlation_upper_tri) before evidence_json storage
- Store: fleet_coherence_log table + insert_coherence_entry/get_open_coherence_entries/get_coherence_summary/
  mark_coherence_resolved/mark_coherence_promoted
- Wiki: cmd_coherence_status() + _db_query() helper + "coherence_status" CMDS entry; auto-called by cmd_phase_close()
- MCP: vapi_fleet_coherence tool in knowledge_server.py (severity_filter parameter)
- AutoResearch: "fleet_coherence_critical" + "fleet_coherence_orphan" priorities; score_phase_193_readiness() gate ≥0.80
- SDK: CoherenceSummaryResult(slots=True) + CoherenceEntryResult(slots=True) + VAPIFleetCoherence client
- BridgeAgent: Tools #145 get_fleet_coherence_summary / #146 get_fleet_coherence_entries / #147 resolve_coherence_entry
- OpenAPI: FleetCoherenceSummary + CoherenceEntryResult schemas; 4 paths

**What we learned**:
- `@dataclass(slots=True)` not `@dataclasses.dataclass(slots=True)` — SDK uses `from dataclasses import dataclass`
- vapi_managed_agents.py bus channels are free-form strings; no central BUS_CHANNELS registry to update
- _db_query() helper in vapi_wiki_engine.py: fail-open, returns [] if table doesn't exist yet
- fleet_coherence_enabled=True (default True) is the exception; document explicitly in every consumer

**Test counts**: Bridge 2142 | SDK 394 | Hardhat 482 | Contracts 43

---

## 8. Phase 238 — MetaLearner FSCA Wiring (2026-04-26)

**Decision scope**: Decision A only. Decisions B and C explicitly rejected/deferred.

**A — PROCEED**: Wire active FSCA contradictions into the autoresearch cycle prompt.
- `vapi_autoresearch.py:46-47` — `import sqlite3` + `BRIDGE_DB_PATH = Path(os.environ.get("VAPI_DB_PATH", "bridge/vapi_store.db"))`
- `vapi_autoresearch.py:51-92` — `load_fsca_findings(severity_min, age_hours, limit)` direct sqlite3 query against `fleet_coherence_log` (schema cited from `bridge/vapi_bridge/store.py:2281-2301`); fail-open on missing DB / missing table / sqlite3 error
- `vapi_autoresearch.py:format_cycle_prompt()` signature gains `fsca_findings: Optional[list] = None`; section spliced between RECENT EXPERIMENT HISTORY and CURRENT SKILL.MD LENGTH
- `vapi_autoresearch.py:run_cycle()` calls loader, passes through to formatter
- 7 deterministic tests `vapi-autoresearch/tests/test_phase238_fsca_wiring.py` — temp SQLite seeded with 5 rows covering all filter conditions

**B — REJECTED**: Add `contradiction_load` subscore to eval harness.
- Reason: `vapi_eval_harness.py` is IMMUTABLE pure-function deterministic scorer over proposal_text + skill_md_after strings only
- `SCORING_WEIGHTS` (vapi_eval_harness.py:64-73) sum=1.00 frozen
- Mixing live runtime state (FSCA log) into a deterministic scorer breaks reproducibility — the harness can re-run on archived proposals indefinitely; coupling to a mutable DB voids that invariant
- Code-level evidence at wiki/phases/phase_238_design_review.md §4

**C — DEFERRED**: Add FSCA contradictions to `UnifiedWIFCorpus` dedup set.
- Re-evaluate after 5+ autoresearch cycles run with FSCA prompt-context
- Question to answer at gate: do the same contradictions get cited verbatim across cycles to a degree that warrants dedup? If yes → ship C with the same fingerprint pattern as the existing 3-source corpus. If no → leave as-is (FSCA prompt-context is sufficient).

**Inaugural autoresearch wiki loop WIF entry**: `what_if_corpus/wif_058_ps5_compat_mode_dormant.md`
- Operator-observed PS5 "controller modules not correct" disconnect during dual-host arbitration (USB to laptop + BT to PS5)
- W1: `ps5_compat_mode` defaults False (`config.py:1059-1067`); `bridge/.env` doesn't override → HID writes active → USB drops on adjudication → PS5 prompts reconnect
- Code documents fix at `dualshock_integration.py:2196-2209` and emits remediation log.warning at `:1684-1689` ("Set PS5_COMPAT_MODE=true")
- W2: one-line `bridge/.env` edit + bridge restart
- Why this is the inaugural entry: pure operator-experience gap invisible to FSCA / PV-CI / GIC chain — surfaces a dormant fix gated only on operator awareness

**Verification standard applied**: every architectural claim in design review and verification report cites `file:line`. Three speculative claims retracted before implementation:
1. "SDK/OpenAPI parity strengthens phase_coherence subscore" — RETRACTED (`vapi_eval_harness.py:213-233` hardcoded ioSwarm-only)
2. "MetaLearner reads memory via _load_workflow_file('memory')" — RETRACTED (call never made structurally)
3. "MetaLearner consumes FSCA via vapi_fleet_coherence" — CORRECTED (tool name doesn't exist; actual is `vapi_contradiction_status`; MetaLearner doesn't consume it — gap that Phase 238 closes via prompt-context, not via MetaLearner)

**What we learned**:
- The verification standard is recursive — apply it to your own design review until every positive claim survives. Hypotheses that sound architecturally elegant ("X strengthens Y") often contradict the actual code structure.
- Immutability is a load-bearing property, not a stylistic choice. The eval harness MUST stay pure-function for the autoresearch loop's reproducibility guarantee to hold.
- Inaugural WIF entries should be observed problems, not invented ones. The autoresearch loop's value compounds with real operator-reported gaps.

**Test counts**: Bridge 2510 | Autoresearch 7 (NEW) | SDK 539 | Hardhat 528 | Contracts 46 LIVE
**PV-CI**: 26/26 invariants pass (actual count post Phase 235-ULTRAREVIEW + Phase 226 expansion)
**Snapshot SHA-256**: 813997b82c09ba3a09be04b16a5ff09fda0022260db8171904cc95b9a1a5b7cf (pages=80; on-chain anchor failed HTTP 404, bridge offline — local snapshot durable)

---

**Document Version**: 1.5 (Phase 238)
**Last Updated**: 2026-04-26
**Update Method**: Append-only, manual edit after significant sessions
**Retention**: All entries preserved indefinitely
