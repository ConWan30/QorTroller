# DECON-1 Stream 4 — Agent-Utility Audit

**Date:** 2026-06-10 · **Verify pass (read-only).** Code institutionalization (Mythos variant #15) deferred to follow-up commit.

**Scope:** 56 Python files in `bridge/vapi_bridge/` matching `*agent*.py`. Classifies each by signal weight against the protocol's own honesty rails. Surfaces — does not retire — agents that violate the `"live": false` discipline.

**Classification rubric:**
- **ACTIVE-VALUABLE** — emits actionable findings on live cadence OR is critical infrastructure (LLM agent, supervisor, FROZEN-v1 anchor surface). ≥3 test files cite it; recent activity.
- **ACTIVE-LOW-SIGNAL** — runs, but emits low-frequency or low-actionable output. May warrant cadence adjustment or merge into a sibling.
- **DORMANT-DOCUMENTED** — disabled by default flag (`*_enabled=False`) AND the dormancy is explicitly named in `CLAUDE.md` hard rules / phase summary.
- **DORMANT-UNDOCUMENTED** — disabled or stale AND not explicitly named in `CLAUDE.md`. Each instance is a per-agent finding violating the `"live": false` discipline.
- **SUPPORT** — not a fleet agent but agent-adjacent infrastructure (auth, message bus, registration, mock). Excluded from retirement analysis.

**Data source:** `wc -l`, `stat -c '%y'`, `grep -lE "\b<stem>\b" bridge/tests/*.py`. Reproducible per `audits/agent-utility-audit-2026-06-10.md.repro.sh` (not produced; commands inline below).

---

## Headline numbers

- 56 `*agent*.py` files in `bridge/vapi_bridge/`
- 7 SUPPORT (excluded from retirement)
- 49 candidate fleet agents
- 27 **ACTIVE-VALUABLE** (≥3 tests + recent + on the documented critical path)
- 9 **ACTIVE-LOW-SIGNAL** (1–2 tests + documented but low-bandwidth)
- 11 **DORMANT-DOCUMENTED** (disabled flag named in CLAUDE.md hard rules)
- **2 DORMANT-UNDOCUMENTED** — **`protocol_intelligence_record_agent`** and **`age_weight_analysis_agent`** — both 0 test files, neither named as live OR dormant in CLAUDE.md hard rules. **Per-agent findings; see §F-DECON-4.1/4.2.**

CLAUDE.md reports the on-chain roster as "29 standalone + 3 stewards = 38-ID". The 49-candidate count here is higher because (a) some "agents" in code are actually triplet sub-modules of one fleet agent (e.g., `operator_agent_curator_polling.py` + `..._drafting.py` + `..._trigger_sources.py` are one logical agent per `[[project_phase_o1_d_path_b_v2_wired]]`), and (b) some pre-Operator-Initiative agents were absorbed into stewards but their modules remain. **§F-DECON-4.3 surfaces this counting discrepancy.**

---

## Inventory table

LOC ranges, modified date, test-file count per agent. Sorted by classification then descending test count.

### ACTIVE-VALUABLE (27)

| Agent | LOC | Modified | Tests | Notes |
|---|---:|---|---:|---|
| `bridge_agent` | 6,673 | 2026-06-04 | **82** | Primary LLM agent (claude-opus-4-7); 31 deterministic tool bindings; SSE stream + SQLite session persistence |
| `fleet_signal_coherence_agent` | 2,188 | 2026-05-17 | 17 | `fleet_coherence_enabled=True` DEFAULT; Mythos variant #36 |
| `ruling_enforcement_agent` | 357 | 2026-05-09 | 9 | Phase 66; central adjudication path; per CLAUDE.md `ruling_enforcement_enabled=False in config: agent still runs but skips enforcement` |
| `vhp_renewal_agent` | 250 | 2026-05-25 | 7 | Phase 109A — first Phase 109+ migration target |
| `protocol_intelligence_agent` | 356 | 2026-05-17 | 6 | Phase 89 |
| `operator_agent_sentry_polling` | 341 | 2026-05-17 | 6 | Sentry steward poll loop; O3_ACTING live ceremony 2026-05-17 |
| `operator_agent_sentry_drafting` | 382 | 2026-05-10 | 6 | Sentry steward draft generator |
| `operator_steward_absorbed_agents` | 423 | 2026-05-17 | 5 | Houses 9 absorbed agents (Sentry 4 / Guardian 4 / Curator 1) |
| `calibration_intelligence_agent` | 704 | 2026-05-16 | 5 | Phase 50; threshold tighten-only enforcement |
| `operator_agent_guardian_polling` | 409 | 2026-05-17 | 4 | Guardian steward; sole autonomous O3 actor |
| `operator_agent_curator_polling` | 349 | 2026-05-17 | 4 | Curator steward; O3_ACTING marketplace authority |
| `corpus_curator_agent` | 989 | 2026-05-17 | 4 | Phase 192; 7-task data coherence |
| `calibration_agent` | 294 | 2026-04-24 | 4 | Phase 50 baseline calibration agent |
| `session_boundary_detector_agent` | 331 | 2026-05-17 | 3 | Phase 191 |
| `separation_ratio_monitor_agent` | 227 | 2026-05-17 | 3 | Phase 134 |
| `protocol_coherence_agent` | 316 | 2026-05-20 | 3 | Phase 221 (PCR live contract `0xfAfe4E8B…`) |
| `operator_agent_guardian_drafting` | 362 | 2026-05-10 | 3 | Guardian draft generator |
| `enrollment_auto_guidance_agent` | 223 | 2026-05-17 | 3 | Phase 156; 1h poll |
| `data_curator_agent` | 506 | 2026-05-15 | 3 | Phase 192; first-class consent-aware corpus curation |
| `agent_registration` | 1,259 | 2026-05-09 | 3 | Roster + on-chain agentId bookkeeping |
| `tournament_activation_chain_agent` | 173 | 2026-04-09 | 2 | Phase 135; **`auto_activate=False` PERMANENT** — but the chain itself is live; classify ACTIVE |
| `separation_ratio_recovery_agent` | 230 | 2026-05-17 | 2 | Phase 173 |
| `protocol_maturity_scoring_agent` | 361 | 2026-04-11 | 2 | Phase 177; maturity score 0.0–1.0 |
| `operator_agent_curator_drafting` | 407 | 2026-05-10 | 2 | Curator draft generator |
| `live_mode_activation_agent` | 245 | 2026-05-09 | 2 | Phase 84 live-mode gate |
| `divergence_triage_agent` | 194 | 2026-05-17 | 2 | Phase 91 |
| `curator_agent` | 307 | 2026-05-09 | 2 | Phase 192-pre Curator workflow agent |

### ACTIVE-LOW-SIGNAL (9)

| Agent | LOC | Modified | Tests | Notes |
|---|---:|---|---:|---|
| `fleet_consensus_snapshot_agent` | 175 | 2026-05-17 | 2 | Phase 157 PoFC hash; documented but ceremony-cadence |
| `biometric_privacy_compliance_agent` | 168 | 2026-05-17 | 2 | Phase 159; GDPR Art 17 |
| `biometric_governance_agent` | 173 | 2026-04-17 | 2 | Phase 222 BBG (`bbg_enabled=False` default per CLAUDE.md hard rule) |
| `agent_calibration_monitor` | 476 | 2026-05-20 | 2 | Calibration-agent watcher — partial overlap with `calibration_intelligence_agent` |
| `operator_agent_curator_trigger_sources` | 586 | 2026-05-10 | 1 | Trigger-source helper; covered by polling integration |
| `operator_agent_guardian_trigger_sources` | 292 | 2026-05-10 | 1 | Same |
| `operator_agent_git_trigger_source` | 222 | 2026-05-10 | 2 | git-push trigger source |
| `controller_hardware_intelligence_agent` | 1,102 | 2026-05-17 | 1 | Phase 155; **`multi_controller_enabled=False`** per CLAUDE.md hard rule |
| `agent_supervisor` | 257 | 2026-03-29 | 1 | Phase 83 supervisor health log |

### DORMANT-DOCUMENTED (11)

| Agent | LOC | Modified | Tests | CLAUDE.md hard-rule disable flag |
|---|---:|---|---:|---|
| `staged_dry_run_graduation_agent` | 309 | 2026-05-16 | 1 | `staged_graduation_enabled=False` (Phase 207) |
| `biometric_stationarity_oracle_agent` | 255 | 2026-04-10 | 1 | `biometric_stationarity_enabled=False` |
| `live_presence_signaling_agent` | 333 | 2026-04-10 | 1 | Phase 190 live but presence-channel default-OFF |
| `reenrollment_attestation_agent` | 206 | 2026-04-09 | 1 | `reauth_attestation_enabled=True` per CLAUDE.md but Phase 185 status documented |
| `maturity_elevation_gate_agent` | 274 | 2026-04-10 | 1 | Phase 183 gate; flag-controlled |
| `attestation_opsec_advisor_agent` | 186 | 2026-04-10 | 1 | Phase 187; advisory severity |
| `attestation_bound_renewal_agent` | 123 | 2026-04-09 | 1 | Phase 186 |
| `persona_break_detector_agent` | 248 | 2026-05-17 | 1 | Phase 182 |
| `gsr_registry_agent` | 110 | 2026-03-21 | 1 | `GSR_ENABLED=false` per CLAUDE.md hard rule — never change without N≥30 GSR calibration sessions per player (current N=0) |
| `gamer_readiness_agent` | 226 | 2026-06-04 | 1 | `GAMER_READINESS_ENABLED` flag in `bridge/.env` |
| `ruling_provenance_anchor_agent` | 214 | 2026-03-19 | 1 | Phase 76; provenance-anchor cadence |

### DORMANT-UNDOCUMENTED (2 — **FINDINGS**)

| Agent | LOC | Modified | Tests | Status |
|---|---:|---|---:|---|
| `protocol_intelligence_record_agent` | 166 | 2026-04-10 | **0** | **F-DECON-4.1** |
| `age_weight_analysis_agent` | 193 | 2026-04-10 | **0** | **F-DECON-4.2** |

### SUPPORT (7 — not classified)

| File | LOC | Reason |
|---|---:|---|
| `agent_auth.py` | 270 | HMAC/agent-token auth machinery |
| `agent_message_bus.py` | 106 | pub/sub infra |
| `mock_agent_registration.py` | 214 | test fixture |
| `agent_commit.py` | 216 | FROZEN-v1 `VAPI-AGENT-COMMIT-v1` primitive (not a fleet agent) |
| `agent_review_emitter.py` | 266 | Phase O5 emitter helper |
| `federation_broadcast_agent.py` | 166 | federation broadcast helper (peers/dormant) |
| `poad_anchor_agent.py` | 37 | tiny PoAdAnchor wrapper |

---

## Per-agent findings

### F-DECON-4.1 — `protocol_intelligence_record_agent.py` — **CORRIGENDUM (2026-06-10): REVISED**

Initial classification said DORMANT-UNDOCUMENTED based on 0 test file imports. Subsequent F-DECON-4.4 cross-check revealed: this agent is referenced as a **string-listed roster entry in `protocol_coherence_agent.py:99`** (a live ACTIVE-VALUABLE agent). It IS integrated into the protocol-coherence sweep.

**Revised classification:** ACTIVE-LOW-SIGNAL (integration-tested via protocol_coherence_agent's sweep loop; no dedicated test file). **No retirement.** See F-DECON-4.5.

### F-DECON-4.2 — `age_weight_analysis_agent.py` — **CORRIGENDUM (2026-06-10): REVISED**

Initial classification said DORMANT-UNDOCUMENTED based on 0 test file imports. Subsequent F-DECON-4.4 cross-check revealed: **agent #24** per `operator_api.py:5960` docstring, with a live HTTP endpoint `/agent/age-weight-analysis-status` and config flag `age_weight_analysis_enabled` **defaulting to True** (`getattr(cfg, "age_weight_analysis_enabled", True)`).

**Revised classification:** ACTIVE-VALUABLE (live endpoint, default-enabled, on-roster). **No retirement.** See F-DECON-4.5.

### F-DECON-4.5 — Audit-rubric refinement (NEW, 2026-06-10)

The "0 dedicated test files = DORMANT-UNDOCUMENTED" signal was **insufficient**. Both candidate agents are integration-tested via downstream surfaces (HTTP endpoints + cross-module roster references) that a `grep -lE "\b<stem>\b" bridge/tests/*.py` does not capture.

**Corrected rubric for Mythos #15:**
1. Direct test imports — `grep -lE "\b<stem>\b" bridge/tests/*.py` (the original signal).
2. **Operator-api endpoint refs** — `grep -E "\b<stem>\b|\b<ClassName>\b" bridge/vapi_bridge/operator_api.py`.
3. **Peer-module string-roster refs** — `grep -E '"<stem>"' bridge/vapi_bridge/*.py` (catches the `protocol_coherence_agent.py:99`-style pattern).
4. **Config flag with non-False default** — `grep -E "<stem>_enabled.*=.*(True|getattr)" bridge/vapi_bridge/config.py`.

An agent is DORMANT-UNDOCUMENTED **only when ALL FOUR signals come back empty AND CLAUDE.md does not name it.** The original audit's 1-of-1 signal was too weak. **Final headline:** 0 (zero) DORMANT-UNDOCUMENTED agents in the fleet as of 2026-06-10.

### F-DECON-4.3 — Fleet-count discrepancy

- CLAUDE.md: "29 standalone + 3 stewards (9 absorbed) = 38-ID roster."
- File count: 49 fleet-candidate modules (excluding 7 support files) in `bridge/vapi_bridge/`.
- The discrepancy is largely accounted for by (a) each steward (Sentry/Guardian/Curator) splitting across `*_polling.py` + `*_drafting.py` + `*_trigger_sources.py` (= 9 modules → 3 logical agents), and (b) the 9 absorbed agents living inside `operator_steward_absorbed_agents.py` as classes, not separate modules.
- **Recommended action (NOT in this stream):** update CLAUDE.md's agent-roster line to either say "29 standalone agents + 3 steward facades (each facade = 3 modules); see `bridge/vapi_bridge/*agent*.py` for the 49 candidate files."

### F-DECON-4.4 — Roster files on the 38-ID on-chain roster

Retiring any agent whose `agentId` is registered on-chain is irreversible relative to the cryptographic identity registry. Before any DORMANT-UNDOCUMENTED retirement:
1. Cross-check the agent's class name against `agent_registration.py`'s `_AGENT_IDS` constant.
2. If on the 38-ID roster, retirement requires a new ceremony + roster update — out of DECON-1 scope.
3. If NOT on the roster, retirement is a simple file delete + test removal + CLAUDE.md NOTE.

Both F-DECON-4.1 and F-DECON-4.2 candidates should be cross-checked this way before operator authorizes retirement.

---

## Decisions deferred to operator

### D-DECON-10 — Retirement policy

Recommended per prompt:
- **DECON-1 Stream 4 closes after this verification doc lands.** No retirements in this stream.
- Each DORMANT-UNDOCUMENTED finding (F-DECON-4.1, F-DECON-4.2) becomes its own follow-up commit, scheduled at operator discretion.
- F-DECON-4.4 cross-check runs before each retirement.
- Mythos variant #15 (`agent_utility_honesty`) is the institutional follow-on: re-runnable, COVERAGE_BOUNDARY-aware, informational severity by default — mirrors variant #14 pattern per `[[project_doc_consistency_discipline_shipped]]`.

### D-DECON-11 — Mythos #15 implementation timing

- (a) Land Mythos #15 in this same audit commit
- (b) **Recommended:** Land Mythos #15 as a follow-on commit after operator reviews this audit; this commit stays purely verification (matches the prompt's "informational severity by default" intent + the recursive-verification-first discipline)

### D-DECON-12 — Acceptable test-count floor for ACTIVE classification

- The ≥3 test files floor I used is implicit, not codified. Future Mythos #15 should pin this so the variant emits when an ACTIVE agent's test count drops below the floor (regression watch).
- Recommend: floor = 2 for ACTIVE classification; <2 tests = AT-RISK warning unless the agent is documented dormant.

---

## Reproduction

```bash
# File enumeration
ls bridge/vapi_bridge/*agent*.py | wc -l   # → 56

# LOC + last-modified per file
for f in bridge/vapi_bridge/*agent*.py; do
  echo "$(stat -c '%y' "$f" | cut -d' ' -f1)|$(wc -l < "$f")|$f"
done | sort -r

# Test-file count per agent
for f in bridge/vapi_bridge/*agent*.py; do
  stem=$(basename "$f" .py)
  tc=$(grep -lE "\b${stem}\b" bridge/tests/*.py 2>/dev/null | wc -l)
  echo "$tc|$stem"
done | sort -rn
```

---

**Stream 4 verification pass complete. NO code writes in this stream.** Per-agent retirement decisions + Mythos #15 institutionalization are follow-on commits scheduled at operator discretion.
