# DECON-1 Stream 2 — Store / Operator-API Partition Map

**Date:** 2026-06-09  
**Status:** VERIFICATION PASS (read-only) — HOLD for operator decisions D-DECON-2/3/4.  
**Scope:** `bridge/vapi_bridge/store.py` (18,794 lines) + `bridge/vapi_bridge/operator_api.py` (10,798 lines).

This document is the Phase 2.0 deliverable. Phase 2.1+ (mechanical extraction, one commit per domain) does NOT begin until decisions land.

---

## F-DECON-2.1 — store.py is a SINGLE GOD-CLASS, not module-level helpers

**The prompt assumed module-level functions** ("which helper cluster touches"). Reality, verified at line 35:

```
bridge/vapi_bridge/store.py:16   class CorpusRegressionError(ValueError):
bridge/vapi_bridge/store.py:35   class Store:
bridge/vapi_bridge/store.py:38       def __init__(self, db_path, consent_ledger_enabled=False):
```

**534 methods** (`grep -c '^    (def|async def)'`) hang off `class Store`. There are no top-level helper functions worth splitting. Two module-level names exist (`Store`, `STATUS_VERIFIED`, `STATUS_DEAD_LETTER`) — all imported by tests.

**Implication for partition strategy** — three options exist; only **(A)** satisfies the "zero call-site churn" hard invariant:

| Strategy | Mechanism | Call-site churn | Risk |
|---|---|---|---|
| **(A) Mixin classes (recommended)** | `class CalibrationMixin: def insert_ait_session(self, ...): ...` then `class Store(CoreMixin, CalibrationMixin, BiometricMixin, ...):`. Each mixin in its own file under `store/`. `self.x()` calls between methods still resolve via MRO. | **Zero.** `from vapi_bridge.store import Store` still works. Every `store.method_x()` call site untouched. | Low. MRO + method ownership clarity at the cost of slightly less natural file boundaries. |
| (B) Composition (`store.calibration.x()`) | Each domain becomes a separate class instantiated in `Store.__init__`; callers traverse the attribute. | **High.** ~318 files have `store.method_x()` → must become `store.calibration.method_x()`. Violates hard invariant. | Out of scope for DECON-1. |
| (C) Module-level helper extraction | Pull pure-function logic out; methods become thin wrappers calling helpers. | Low at call sites, but very limited extractable surface — most methods access `self._conn`. | Marginal gain; not worth the churn. |

**Recommendation: (A) Mixin classes.** Each domain becomes a `*Mixin` class in `store/<domain>.py`. `store/__init__.py` exposes the composed `Store` symbol unchanged. `STATUS_VERIFIED` / `STATUS_DEAD_LETTER` constants live in `store/_constants.py` and are re-exported from `store/__init__.py`.

---

## F-DECON-2.2 — operator_api.py is a register-function pattern, NOT APIRouter

**The prompt proposed APIRouter per domain.** Reality, verified by the route decorator pattern:

```
bridge/vapi_bridge/operator_api.py:360     @app.get("/health")
bridge/vapi_bridge/operator_api.py:368     @app.get("/gate/{device_id}")
bridge/vapi_bridge/operator_api.py:385     @app.post("/agent")
...
```

All 241 routes use `@app.<verb>(...)` (NOT `@router.<verb>(...)`), inside a single function that takes the FastAPI `app` as a parameter. Routes attach directly to `app`. This is the **register-routes(app)** pattern.

**Implication** — two extraction strategies:

| Strategy | Mechanism | Risk |
|---|---|---|
| **(A) Split register-functions (recommended)** | Each domain gets `def register_<domain>_routes(app: FastAPI) -> None:` in its own file. `operator_api.py` becomes a thin shim calling each `register_*` in declared order. Route paths, methods, auth dependencies, response shapes byte-identical. **Order preserved by call sequence.** | Very low. Truly mechanical. No FastAPI semantic change. |
| (B) Convert to APIRouter | Each domain becomes an `APIRouter()`; main shim does `app.include_router(r1); app.include_router(r2); ...`. | Higher — APIRouter has its own prefix/tag/dependency machinery; subtle behavioral differences possible (e.g., dependency override resolution). Defer. |

**Recommendation: (A) register-function split.** Path order matters in FastAPI (first match wins on path conflicts); preserving the call order of `register_*(app)` preserves the original registration order byte-identically. No `APIRouter` constructor introduced in this stream.

This is **drift from the prompt's "APIRouter per domain"** — surfaced per loop protocol step 1, not silently corrected.

---

## F-DECON-2.3 — Table count and prefix clustering

**~170 distinct tables** identified via `CREATE TABLE IF NOT EXISTS` (134 in `_init_schema` at lines 103–4222; ~16 lazy-created elsewhere e.g. `operator_initiative_auto_supersede_log:16357`, `operator_agent_chain_spending_log:16501`, `operator_agent_signature_log:16721`, `consent_event_log:18695`).

Tables cluster by semantic prefix into 12 domains. The proposed partition assigns each table to a single owner based on dominant access pattern, not strict prefix:

### Proposed `store/` partition

| Domain | File | Tables (representative; full list in commit message of Phase 2.1) | Method count est. |
|---|---|---|---|
| **core** | `store/_core.py` | `devices`, `records`, `submissions`, `schema_versions`, `frame_checkpoints` + the `Store.__init__` / `_conn` / `_init_schema` / `db_execute` / `_run_migrations` machinery | ~40 |
| **calibration** | `store/calibration.py` | `player_calibration_profiles`, `l6_capture_sessions`, `threshold_history`, `calibration_agent_sessions`, `l6b_probe_log`, `separation_ratio_snapshots`, `l4_calibration_log`, `l4_threshold_tracks`, `l4_battery_calibration_runs`, `l4_threshold_router_log`, `l4_recalibration_jobs`, `l4_dim_sync_log`, `tournament_preflight_log`, `separation_defensibility_log`, `centroid_velocity_log`, `separation_ratio_registry_log`, `capture_stagnation_log`, `controller_hardware_profiles`, `enrollment_guidance_log`, `ait_session_log`, `capture_health_log`, `gameplay_classification_disagreements`, `tremor_convergence_log`, `dry_run_graduation_log`, `graduation_autowatch_log`, `per_pair_gap_*` (4 tables), `capture_velocity_oracle_log`, `tournament_blocker_summary_log`, `separation_ratio_recovery_log`, `corpus_ratio_regression_guard_log`, `corpus_regression_override_log`, `separation_ratio_breakthrough_log`, `active_play_occupancy_log` | ~120 |
| **biometric** | `store/biometric.py` | `biometric_fingerprint_store`, `continuity_claims`, `gsr_samples`, `biometric_renewal_log`, `biometric_renewal_chain_log`, `biometric_stationarity_log`, `biometric_snapshot_log`, `persona_break_log`, `persona_break_attestation_log`, `attestation_opsec_log`, `attestation_bound_renewal_log`, `maturity_elevation_log`, `renewal_consent_snapshot_log`, `gsr_hmac_validation_log`, `ipact_renewal_commitments` | ~70 |
| **consent** | `store/consent.py` | `consent_ledger`, `right_to_erasure_log`, `consent_gate_violation_log`, `consent_snapshot_log`, `post_erasure_ratio_log`, `erasure_certificate_log`, `privacy_compliance_log`, `consent_event_log`, `data_provenance_dag` | ~50 |
| **vhp_credentials** | `store/vhp.py` | `phg_checkpoints`, `phg_credential_mints`, `vhp_issuances`, `vhp_renewal_log`, `vhp_reenrollment_badge_log`, `vhp_dual_gate_log`, `tournament_passports`, `credential_enforcement`, `device_enrollments`, `device_risk_labels`, `detection_policies` | ~50 |
| **marketplace** | `store/marketplace.py` | `pending_listings`, `curator_packaging_log`, `marketplace_listing_log`, `curator_listing_review_log` | ~25 |
| **agents_rulings** | `store/agents.py` | `agent_sessions`, `agent_events`, `agent_rulings`, `ruling_streaks`, `on_chain_rulings`, `ruling_validation_log`, `ruling_provenance_anchors`, `agent_calibration_health`, `agent_context_log`, `agent_commit_log`, `mythos_finding_log`, `mythos_cadence_log`, `escalation_ruling_log`, `reactive_adjudication_log`, `supervisor_health_log`, `shadow_enforcement_log`, `divergence_triage_reports` | ~70 |
| **tournament_activation** | `store/tournament.py` | `activation_simulation_log`, `activation_state`, `live_mode_transitions`, `live_mode_readiness_reports`, `tournament_readiness_snapshots`, `live_mode_guard_log`, `enforcement_certificates`, `live_mode_activation_log`, `tournament_activation_chain_log`, `epistemic_consensus_log`, `epistemic_threshold_history` | ~40 |
| **ioswarm** | `store/ioswarm.py` | `ioswarm_consensus_log`, `ioswarm_renewal_log`, `ioswarm_adjudication_log`, `ioswarm_vhp_mint_log`, `ioswarm_node_registry`, `ioswarm_poad_anchor_log`, `ioswarm_node_health_log`, `poad_registry_log`, `dual_eligibility_checks`, `swarm_quorum_validation_log` | ~30 |
| **chain_anchors** | `store/chain_log.py` | `oracle_publications`, `ceremony_audit_log`, `gate_attestations`, `governance_provenance_chain`, `allowlist_change_log`, `invariant_gate_log`, `bbg_proposal_log`, `poac_chain_audit_log`, `age_weight_analysis_log`, `protocol_coherence_log`, `fleet_coherence_log`, `coherence_fingerprint_log` | ~40 |
| **snapshots_grind** | `store/snapshots.py` | `corpus_snapshot_log`, `watchdog_event_log`, `corpus_entropy_log`, `feature_correlation_log`, `session_contribution_weight_log`, `federation_corpus_quality_log`, `data_readiness_certificate_log` | ~30 |
| **operator_initiative** | `store/operator_initiative.py` | `operator_initiative_auto_supersede_log`, `operator_agent_chain_spending_log`, `operator_agent_signature_log`, `operator_agent_activation_log`, `operator_agent_shadow_log`, `operator_agent_drift_log`, `operator_agent_drafts`, `operator_initiative_advancement_log`, `operator_registrations`, `operator_audit_log` | ~40 |
| **zkba_vpm_witness** | `store/zkba_vpm.py` | `zkba_artifact_log`, `vpm_artifact_log`, `cfss_lane_drift_log`, `mlga_session_log`, `bt_witness_log`, `physical_data_attestation_log` | ~25 |

**Method count estimates sum to ~630** vs the actual 534 — overlap is expected (some tables/methods listed under their dominant domain even when secondary-accessed elsewhere; methods that genuinely cross domains stay in `_core.py` or are duplicated in commit-level review).

**Cross-cutting concerns** that should NOT be split into domains:
- `_conn()` / `db_execute()` / `_init_schema()` / migration runner → `_core.py` only
- `set_gic_chain_broken()` and the broken-chain flag → `_core.py`
- Schema-version bookkeeping → `_core.py`

---

## F-DECON-2.4 — `operator_api.py` route domain map

241 routes identified via `@app.<verb>(...)` count. Natural clustering by URL prefix:

| Domain | File | Route prefix(es) | Route count |
|---|---|---|---|
| **health_gate** | `operator_api/health_gate.py` | `/health`, `/gate/*` | 3 |
| **agent_calibration** | `operator_api/agent_calibration.py` | `/agent/l4-*`, `/agent/separation-*`, `/agent/centroid-*`, `/agent/capture-*`, `/agent/per-pair-*`, `/agent/ait-*`, `/agent/tournament-preflight-*`, `/agent/dry-run-*`, `/agent/graduation-*`, `/agent/corpus-regression-*`, `/agent/l4-dim-*`, `/agent/accel-tremor-*`, `/agent/tremor-*`, `/agent/probe-gate-*` | ~50 |
| **agent_biometric** | `operator_api/agent_biometric.py` | `/agent/vhp-*`, `/agent/biometric-*`, `/agent/persona-*`, `/agent/attestation-*`, `/agent/reenrollment-*`, `/agent/maturity-*`, `/agent/renewal-chain-*`, `/agent/poep-*` | ~35 |
| **agent_consent** | `operator_api/agent_consent.py` | `/agent/consent-*`, `/agent/register-consent`, `/agent/revoke-consent`, `/agent/erasure-*`, `/agent/gamer-consent-status`, `/operator/record-category-consent`, `/operator/revoke-category-consent` | ~12 |
| **agent_marketplace_curator** | `operator_api/agent_marketplace.py` | `/curator/*`, `/agent/marketplace-*`, `/agent/curator-*`, `/operator/curator-*`, `/operator/list-data-session`, `/agent/twin-stream*` | ~25 |
| **agent_tournament** | `operator_api/agent_tournament.py` | `/agent/activation-*`, `/agent/commit-activation`, `/agent/request-activation`, `/agent/tournament-readiness*`, `/agent/live-mode-*`, `/agent/enforcement-*`, `/agent/escalation-*`, `/agent/triage-report`, `/agent/run-readiness-validation` | ~25 |
| **agent_ioswarm** | `operator_api/agent_ioswarm.py` | `/agent/ioswarm-*`, `/agent/poad-*`, `/agent/adjudication-registry-*`, `/agent/swarm-*`, `/agent/dual-primitive-*`, `/agent/check-dual-eligibility`, `/agent/vhp-dual-gate-*` | ~15 |
| **agent_operator_initiative** | `operator_api/agent_operator_initiative.py` | `/operator/operator-agent-*`, `/operator/operator-initiative-*`, `/operator/anchor-cedar-bundle`, `/operator/fleet-readiness-root`, `/operator/evaluate-agent-action`, `/operator/mythos-findings`, `/operator/cfss-lane-drift-*`, `/operator/g7-curator-*`, `/operator/curator-graduation-*`, `/operator/operator-status` | ~15 |
| **agent_zkba_vpm** | `operator_api/agent_zkba_vpm.py` | `/operator/zkba-*`, `/operator/vpm-*` | ~12 |
| **agent_supervisor** | `operator_api/agent_supervisor.py` | `/agent/supervisor-status`, `/agent/warm-up`, `/agent/gate-readiness`, `/agent/run-synthetic-corpus`, `/agent/corpus-status`, `/agent/campaign-status`, `/agent/reactive-adjudication-log`, `/agent/protocol-intelligence`, `/agent/shadow-enforcement-log`, `/agent/epistemic-*`, `/agent/protocol-maturity*`, `/agent/poac-chain-integrity`, `/agent/age-weight-*`, `/agent/post-erasure-*`, `/agent/run-agent-self-test`, `/agent/data-provenance-*`, `/agent/corpus-entropy-*`, `/agent/federated-corpus-*`, `/agent/feature-correlation-*`, `/agent/data-readiness-*`, `/agent/session-contribution-*`, `/agent/fleet-coherence-*`, `/agent/coherence-fingerprint-*`, `/agent/protocol-metabolism-*`, `/agent/protocol-coherence-*`, `/agent/gamer-readiness-*`, `/agent/invariant-gate-*`, `/agent/run-invariant-gate`, `/agent/allowlist-governance-*`, `/agent/bbg-*` | ~40 |
| **agent_grind** | `operator_api/agent_grind.py` | `/bridge/capture-health`, `/bridge/grind-chain-status`, `/grind/*`, `/operator/gic-reset`, `/operator/watchdog-status`, `/operator/force-corpus-snapshot`, `/operator/anchor-biometric-snapshot`, `/operator/override-gameplay-context`, `/agent/mlga-live-session-status`, `/agent/active-play-occupancy-status`, `/agent/corpus-snapshot-status`, `/agent/biometric-snapshot-status`, `/agent/auto-trigger-status`, `/operator/ipact-challenge`, `/agent/agent-commit-*`, `/agent/physical-data-attestation-*`, `/agent/agent-registry-status` | ~20 |
| **agent_misc** | `operator_api/agent_misc.py` | `/insights`, `/digest`, `/enforcement`, `/calibration/*`, `/federation/*`, `/agent/operator-status`, `/agent/wallet-devices`, `/agent/config`, `/agent/edge-ai-profile`, `/agent/quicksilver-status`, `/agent/mint-vhp`, `/agent/first-vhp-status`, `/agent/run-activation-simulation`, `/agent/ruling-provenance/*`, `/agent/validation-stats`, `/agent/validation-gate`, `/agent/biometric-privacy-status`, `/agent/pohbg-status`, `/agent/live-presence-signaling-status`, `/agent/pir-chain-*`, `/agent/create-pir`, `/agent/confidence-score-multiplier-status`, `/agent/bt-transport-status`, `/agent/epoch-window-*` (6), `/agent/usb-stability-status`, `/agent/ioswarm-node-health`, `/agent/tournament-activation-chain`, `/agent/run-l4-recalibration`, `/agent/l4-recalibration-status`, `/agent/auto-separation-snapshot-status`, `/agent/calibration-health`, `/agent/separation-defensibility-status`, `/agent/enrollment-capture-guidance`, `/agent/enrollment-auto-guidance-status`, `/agent/fleet-consensus-snapshot`, `/agent/ceremony-audit-*`, `/agent/register-ceremony-participant`, `/agent/separation-ratio-recovery-status`, `/agent/biometric-credential-age`, `/agent/biometric-ttl-scaling-status`, `/agent/per-pair-gap-projection`, `/agent/tournament-blocker-summary`, `/agent/capture-velocity-oracle`, `/agent/per-pair-gap-trend`, `/agent/per-pair-gap-status`, `/player/session-status`, `/agent/run-tournament-preflight`, `/agent/tournament-preflight-status`, `/agent/tournament-readiness-score`, `/agent/separation-ratio-breakthrough`, `/agent/swarm-operator-gate-status`, `/agent/ioswarm-node-registry-status`, `/agent/separation-ratio-registry-status`, `/agent/commit-separation-ratio`, `/agent/capture-stagnation-status`, `/agent/controller-hardware-status`, `/agent/anchor-erasure-certificate`, `/agent/anchor-data-readiness-certificate`, `/agent/resolve-coherence-entry`, `/agent/fleet-coherence-history`, `/agent/run-tournament-preflight`, `/agent/renewal-chain-status`, `/agent/renew-separation-ratio-commitment`, `/operator/suspension/*` (3) | ~80 |

**Total ~330** estimated routes vs actual 241 — overlap because some routes are listed under both their dominant and secondary domain in the table above; assignment is fixed in Phase 2.1 mapping.

**Path-collision check (preliminary):** parametrized paths like `/agent/ruling-provenance/{ruling_id}` vs hypothetical static paths like `/agent/ruling-provenance/static` could collide if order changes. None observed in the current 241; will be re-verified at extraction time.

---

## F-DECON-2.5 — Import surface (Hard Invariant verification)

**Public symbols currently imported from `vapi_bridge.store`:**
- `Store` (the class) — dominant, ~250+ files
- `STATUS_VERIFIED`, `STATUS_DEAD_LETTER` — module-level string constants used by batcher tests

**Public symbols currently imported from `vapi_bridge.operator_api`:**
- The route-register function (called from `main.py`)
- (Test files mostly use HTTP client against the app, not direct imports)

**Re-export strategy after partition:**
- `store/__init__.py` does `from ._core import Store; from ._constants import STATUS_VERIFIED, STATUS_DEAD_LETTER` etc. `from vapi_bridge.store import Store` continues to work byte-identically. `from vapi_bridge import store; store.STATUS_VERIFIED` continues to work.
- `operator_api/__init__.py` does `from .main import register_routes` (or whatever the current entry symbol is named). Tests and `main.py` unchanged.

**318 files** matched the import grep for store/operator_api. After partition, target is **0 files modified** in the call surface. Phase 2.1+ commit shall not appear in `git status` for any file under `bridge/tests/`, `sdk/tests/`, `scripts/`, or non-touched `bridge/vapi_bridge/*.py`.

---

## F-DECON-2.6 — FROZEN-v1 primitive modules

Per the prompt's hard invariant: FROZEN-v1 primitive helper modules are NOT moved in this stream.

Modules that touch FROZEN-v1 primitives (read-only verification — none move):
- `corpus_snapshot.py` — VAPI-CORPUS-SNAPSHOT-v1
- `biometric_snapshot.py` — VAPI-BIOMETRIC-SNAPSHOT-v1
- `agent_commit.py` — VAPI-AGENT-COMMIT-v1
- `grind_chain.py` — VAPI-GIC-GENESIS-v1
- `watchdog_chain.py` — VAPI-WEC-GENESIS-v1

These are PV-CI-pinned and may write into store-owned tables (`corpus_snapshot_log`, `biometric_snapshot_log`, etc.). After partition, they continue to import the unchanged `Store` symbol. Their tables move to the `snapshots` or `agents` domain inside `store/`, but the FROZEN modules themselves don't move and don't change their import lines. **PV-CI baseline 174 unchanged by this stream.**

If `D-DECON-3` later approves a separate ceremony to move the FROZEN modules into `primitives/`, that is a separate commit with its own `--confirm-governance` flag and allowlist digest update. Not in DECON-1 scope.

---

## Decision blocks

### D-DECON-2 — Partition boundaries (approve / amend / reject)

The table-domain map in §F-DECON-2.3 (12 store/ domains) and route map in §F-DECON-2.4 (12 operator_api/ domains). Specific points for operator review:

1. Is **`zkba_vpm_witness`** the right single owner for `physical_data_attestation_log` and `bt_witness_log`, or should those split into their own `witness/` domain?
2. **`ioswarm`** — emulator-only (no live nodes); domain could fold into `agents` if simpler. Operator preference?
3. **`agent_misc`** route file is ~80 routes — should it sub-split? Or is one "leftovers" file acceptable for the first pass with a future cleanup phase?
4. Method names like `insert_ait_session` (calibration) vs `get_ait_separation_status` (calibration) cluster cleanly. Cross-domain methods like `commit_activation` touch `activation_state`, `tournament_activation_chain_log`, AND `consent_ledger` — should these stay in `_core.py` for the first pass?

### D-DECON-3 — FROZEN primitive module relocation (ceremony required if approved)

Recommend: **defer**. Keep `corpus_snapshot.py` / `biometric_snapshot.py` / `agent_commit.py` / `grind_chain.py` / `watchdog_chain.py` flat at `bridge/vapi_bridge/*.py`. They are working FROZEN-v1 surfaces; moving them requires PV-CI allowlist digest changes and `--confirm-governance`, which is outside DECON-1's "no new ceremonies" posture. If approved later, it becomes a separate operator-fired commit.

### D-DECON-4 — Commit granularity

Recommend: **one commit per extracted domain** for both `store/` and `operator_api/`. Concrete plan:

- store/: 13 commits (core first, then calibration → biometric → consent → vhp_credentials → marketplace → agents_rulings → tournament_activation → ioswarm → chain_anchors → snapshots_grind → operator_initiative → zkba_vpm_witness)
- operator_api/: 12 commits (health_gate first, then by route count)

Total: ~25 commits. Each one runs the full bridge pytest suite + PV-CI gate locally before commit. Bisectable; revertible. Mega-commit alternative is faster but loses the bisect property — if a single domain extraction silently broke something, the mega-commit must be wholly reverted.

### D-DECON-5 (NEW, surfaced by verification) — Operator_api split mechanism

Approve **register-function pattern** (§F-DECON-2.2 strategy (A)) over APIRouter? This is drift from the prompt; surfacing per loop step 1. The register-function pattern is lower risk because it matches the existing decoration model byte-identically.

---

## Phase 2.0 verification deltas

- Files read: `store.py` (header + grep), `operator_api.py` (header + grep)
- Files written: this audit doc only
- Tests run: none (read-only phase)
- PV-CI: unchanged (174)
- 0 IOTX; no FROZEN edits; no chain writes
- CLAUDE.md: NOT updated this phase (NOTE drafted at Phase 2.1 first extraction commit)

**Awaiting D-DECON-2 / D-DECON-3 / D-DECON-4 / D-DECON-5 decisions before any code write.**
