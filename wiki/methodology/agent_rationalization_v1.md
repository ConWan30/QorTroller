# Agent Rationalization v1 — Steward-Aligned Fleet Compression

**Phase:** post-STABILITY-9 (2026-05-17)
**Authority:** operator directive 2026-05-17 — "make the novel determination for which agents may not be necessary if they continue to cause unnecessary loops instead of doing the tasks and job their programming/development purpose garners correctly. those agents purpose then could be orchestrated and fused seamlessly with the 3 steward operator agents based on their alignment"
**Status:** ROADMAP — analysis + per-agent disposition, no code changes in this doc

---

## 1. Operating premise

The Operator Initiative ships 3 cryptographically-attested stewards (Sentry, Guardian, Curator) each with a defined authority lane:

| Steward | Authority lane | Cedar permits at O3_ACTING |
|---|---|---|
| **Sentry** | `lane://provenance/**` | `kms-sign`, `provenance-recording`, `pda-attestation-anchor` |
| **Guardian** | `lane://audits/**` + `lane://ops/**` | `audit-drafting`, `operational-diagnostic` |
| **Curator** | `lane://marketplace/**` + `chain://iotex-testnet` | `marketplace-listing-review`, `marketplace-listing-suspend` |

These three lanes cover the protocol's full external write surface (chain ops, audit trail, marketplace state). The 50+ pre-Operator-Initiative agents either (a) feed into these surfaces, (b) compute derivative metrics, (c) are disabled by default, or (d) detect events that should be steward-orchestrated.

The thundering-herd of ~50 concurrent asyncio tasks all firing initial polls within seconds of bridge boot is a known cause of the STABILITY-9 startup STARVATION wave (62 events over 7.5 min, observed 2026-05-17). Compressing the fleet is BOTH an architectural cleanup AND a stability fix.

## 2. Disposition framework

Each agent receives one of four dispositions:

- **DELETE** — agent is disabled by default + has no path to becoming active in current protocol design
- **ABSORB → {steward}** — agent's purpose folds into a steward's skill set; the perpetual loop is replaced by steward poll + on-demand skill invocation
- **EVENT-DRIVE** — agent's purpose is episodic; replace poll loop with bus subscription
- **RETAIN** — agent does load-bearing work that doesn't map to any steward and runs at a frequency the event loop can tolerate

## 3. Per-agent disposition

### 3.1 DELETE (5 agents)

These agents are guarded `False` by default and have no active use case:

| Agent | Reason |
|---|---|
| `GSRRegistryAgent` (Phase 99B, `GSR_ENABLED=false`) | Galvanic-skin-response hardware not in canonical sensor stack; N=0 calibration; deferred indefinitely per Hard Rule in CLAUDE.md |
| `FederationBroadcastAgent` (Phase 80, `FEDERATION_BROADCAST_ENABLED=false`) | No federation peers configured; reactivate only if multi-bridge deployment |
| `BiometricGovernanceAgent / BBG` (Phase 222, `BBG_ENABLED=false`) | VHP-gated proposal flow; only fires when proposals exist + BBG opted in |
| `ProtocolCoherenceAgent` (Phase 221, `PROTOCOL_COHERENCE_ENABLED=false`) | Fleet Merkle root on-chain anchor; superseded by FRR (Phase O1-FRR) which Sentry will anchor at O3_ACTING |
| `MempoolOpSecAdvisorAgent` (Phase 187, `MEMPOOL_OPSEC_ENABLED=false`) | Advisory only; no on-chain activity = no advisory output |

**Action:** remove from `main.py` task-spawn block. Keep modules + tests intact for future re-activation. Save 5 background asyncio tasks at boot.

### 3.2 ABSORB into Guardian (6 agents)

Guardian's authority is audit + diagnostic. The following agents produce diagnostic data that belongs in audit-drafting:

| Agent | Current poll | Fold into |
|---|---|---|
| `ProtocolIntelligenceAgent` (Phase 89) | per-event + 60s | Guardian skill `operational-diagnostic`: maturity score becomes a field on every audit entry |
| `ProtocolMaturityScoringAgent` (Phase 177) | 300s | Same — even more derivative; Guardian computes once per audit |
| `MaturityElevationGateAgent` (Phase 183) | per-event | Guardian skill `audit-drafting`: elevation decisions ARE audit-bearing governance events |
| `AgentSupervisor` (Phase 83) | 15min | Guardian skill `operational-diagnostic`: fleet health snapshot rolled into ops diagnostic. With fewer agents to supervise (per this doc), Guardian self-monitors the 3-steward fleet. |
| `AgentCalibrationMonitor` (Phase 148) | 900s | Guardian periodic skill `operational-diagnostic`: 16 self-tests become a Guardian audit category |
| `RulingEnforcementAgent` (Phase 66/67) | 300s | Guardian skill `audit-drafting`: streak escalations are governance-bearing audit entries; Guardian's audit-drafting captures them. Live BLOCK/HOLD writes inherit from Cedar's lane authority. |

**Action:** for each, freeze the existing module (no further changes) but stop spawning the background loop. Add a Guardian skill stub that invokes the agent's existing compute methods on-demand (per poll cycle OR per audit-drafting trigger). Save 6 background asyncio tasks at boot.

### 3.3 ABSORB into Sentry (4 agents)

Sentry's authority is provenance + on-chain anchoring. The following agents are provenance-recording in different uniforms:

| Agent | Current poll | Fold into |
|---|---|---|
| `VHPRenewalAgent` (Phase 102) | 6h | Sentry skill `provenance-recording`: VHP renewal IS provenance work; only fires when ≥1 VHP exists |
| `CeremonyWatchdogAgent` (Phase 75) | 300s | Sentry skill `provenance-recording`: MPC ceremony state anchors on the provenance lane |
| `RulingProvenanceAnchorAgent` (Phase 76, `publish_enabled=False`) | 60s | Sentry skill `provenance-recording`: this IS Sentry's job. Pure duplication. |
| `ChainReconciler` (Phase 25) | 30s | Sentry skill `provenance-recording`: PHG checkpoint confirmation is on-chain provenance. |
| `PoAdAnchorAgent` (Phase 112, `POAD_ON_CHAIN_ENABLED=false`) | disabled | Sentry skill `pda-attestation-anchor`: at O3_ACTING this is Sentry's primary live-write capability anyway |

**Action:** freeze modules; stop spawning loops; add Sentry skill stubs. Save 4 background asyncio tasks (+1 already disabled). Sentry inherits these as on-demand capabilities triggered by its own poll cycle OR bus events from the chain.

### 3.4 ABSORB into Curator (1 agent + naming reconciliation)

Curator's authority is marketplace + data curation. There's currently a name collision:

| Agent | Disposition |
|---|---|
| `CorpusDataCuratorAgent` (Phase 192, 1800s, 7-task) | ABSORB into Curator: corpus integrity IS curation. The 7 tasks (provenance DAG, entropy, erasure certs, federation quality, correlation, readiness cert, contribution weights) become Curator periodic skills triggered every 30 min. Curator already polls at 30s; the corpus-integrity tasks ride that cadence at a 60× slower cadence. |
| `DataCuratorAgent` (Phase 69/70, 5min) | RENAME (does NOT fold) — this is a per-device-class data-oracle, distinct from the Operator Curator. Suggested rename: `DataOracleAgent` to eliminate steward confusion. Retains its own poll loop (300s) — narrow scope. |

**Action:** absorb CorpusDataCuratorAgent. Rename DataCuratorAgent → DataOracleAgent in a separate commit. Save 1 background asyncio task. Curator gains 7 corpus-integrity capabilities.

### 3.5 EVENT-DRIVE (5 agents)

These agents are episodic by design — they fire when a specific signal changes. They should subscribe to bus events instead of polling:

| Agent | Currently polls | Subscribe to |
|---|---|---|
| `ClassJDetector` (Phase 81) | 300s | `ruling_request` bus event; trigger on PoAC chain extension |
| `DivergenceTriageAgent` (Phase 91) | event-driven, but spawned as poll task | `divergence_pattern_detected` (already a bus event) |
| `PersonaBreakDetectorAgent` (Phase 182) | poll | `enrollment_complete` + `validation_record_inserted` bus events |
| `SeparationRatioMonitorAgent` (Phase 129) | 300s | `separation_ratio_recomputed` bus event from analyze_interperson_separation pipeline |
| `SeparationRatioRecoveryAgent` (Phase 173) | 3600s | Same as 129, with severity filter |

**Action:** remove the perpetual poll loop spawn; register a bus subscription via the existing `AgentMessageBus.subscribe()` pattern. Save 5 background asyncio tasks (-5 perpetual polls; +5 bus subscriptions which are essentially free).

### 3.6 RETAIN (17 agents)

These do load-bearing work that doesn't map to any steward or runs at a frequency the event loop can tolerate:

- `Batcher` — PoAC chain submission pipeline (continuous when not paused)
- `InsightSynthesizer` — 6h longitudinal digest (low frequency)
- `CalibrationIntelligenceAgent` — 30min LLM event consumer
- `BridgeAgent` — LLM tool dispatcher (request-response, not a loop)
- `ProactiveMonitor` — 60s drift sweep
- `FederationBus` — only spawns when peers configured
- `AlertRouter` — bus subscriber
- `cedar_drift_sweeper` — Phase O1 C4 (60s/600s dual-cadence)
- `FleetSignalCoherenceAgent` — 900s; CRITICAL infrastructure
- `SessionAdjudicator` + `SessionAdjudicatorValidationAgent` — per-session
- `pcc_persistence_loop` — 5s capture-health writer
- `LoopHealthMonitor` — STABILITY-3 instrument (essential)
- `loop_health_monitor` (alias) — sentinel
- `ProtocolStateCache heartbeat` — 15s SSE-feeder
- `manufacturer revocation listener` — 30s chain poll
- `OperatorAgentLiveWriteExecutor` (Path B v1) — 60s; the new authorized chain-action executor
- `SessionBoundaryDetectorAgent` — 60s; PoAC-stream-correlated; could become event-driven (Stage 7 candidate)

### 3.7 Operator Initiative core (always retained — these ARE the stewards)

- Sentry polling loop (30s)
- Guardian polling loop (30s)
- Curator polling loop (30s)
- Curator review loop (300s)
- MLGA trackers (5: session, GIC-BETA, HONESTY-BOARD, CDRR-DAG, market_listing)
- LiveModeActivationAgent, LiveModeActivationPipeline (5min)

## 4. Expected stability impact

| Metric | Pre-rationalization | Post-rationalization |
|---|---|---|
| Background asyncio tasks at boot | ~50 | ~25 |
| Initial-poll thundering herd | severe (~50 to_thread calls within seconds) | moderate (~25) |
| ThreadPoolExecutor pressure | high (64 workers saturated by herd) | low |
| Startup STARVATION wave | 62 events / 7.5 min | predicted: <5 events / <2 min |
| Per-agent change requirements | n/a | ~21 modules touched (mostly remove main.py spawn + add skill stub) |
| Steward complexity gain | n/a | Sentry +4 skills, Guardian +6 skills, Curator +1+7 skills |

## 5. Sequencing — do not ship in one commit

Per Verification-First Discipline, each disposition is its own commit:

1. **STABILITY-9 stage 4a**: DELETE — remove 5 disabled-default agent spawns from main.py (lowest risk; agents never run anyway)
2. **STABILITY-9 stage 4b**: EVENT-DRIVE — convert 5 detector agents to bus-subscribers
3. **STABILITY-9 stage 4c**: ABSORB Guardian — fold 6 agents into Guardian skill stubs
4. **STABILITY-9 stage 4d**: ABSORB Sentry — fold 4 agents into Sentry skill stubs
5. **STABILITY-9 stage 4e**: ABSORB Curator — fold CorpusDataCuratorAgent; rename DataCuratorAgent → DataOracleAgent

Each stage retains existing modules + tests (no deletion of code; just removal of `asyncio.create_task` spawn). Re-activation is a one-line revert.

## 6. Hard constraints preserved

- All FROZEN-v1 cryptographic primitives untouched (PoAC wire format, GIC chain, WEC, VAME, CORPUS-SNAPSHOT, CONSENT, BIOMETRIC-SNAPSHOT, LISTING, FRR, ZKBA, POSEIDON-AS, VAPI-O3-SUPERSEDE)
- All PV-CI invariants preserved (currently 128)
- Cedar bundle Merkle roots unchanged
- 3-steward Cedar bundles unchanged
- No agent's compute logic is deleted — only its perpetual loop spawn is removed; the methods become steward-invoked skills
- Re-activation path documented for every agent (set `<agent>_enabled=true` in cfg)

## 7. Open questions for operator review

1. Should DELETE (3.1) modules also be removed from imports, or kept importable for future re-activation? Recommendation: KEEP importable.
2. For ABSORB dispositions, should the steward skill stubs run at the steward's existing poll cadence (30s) or at the agent's previous cadence (60s-6h)? Recommendation: at the steward's cadence (faster = healthier signal).
3. For EVENT-DRIVE conversions, what should happen if no event fires for an extended period? Recommendation: each subscriber registers a "stale signal" diagnostic at FSCA so Guardian can audit-draft if a detector has been silent for >24h.
4. Should `DataCuratorAgent` (Phase 69/70) actually fold into Curator after all, despite the per-device-oracle distinction? Operator decision.

## 8. References

- CLAUDE.md NOTE chain (Phase O0 → O1_SHADOW → O2_SUGGEST → O3_ACTING ladder)
- `bridge/vapi_bridge/cedar_bundles/{anchor_sentry,guardian,curator}_o3_acting_v1.json`
- `bridge/vapi_bridge/operator_initiative_live_write_executor.py` (Path B v1)
- Phase 235.x-STABILITY-9 v0 + stage 1 + stage 2 + stage 3 commits
- `scripts/stability_9_archaeology.py` (518 antipattern candidates surfaced)

---

*Author: VAPI Principal Architect, 2026-05-17 (autonomous determination under operator authorization)*
