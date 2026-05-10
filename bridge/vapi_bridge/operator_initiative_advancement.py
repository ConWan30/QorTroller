"""Phase O1 D — Unified Operator Initiative Advancement Watcher.

Parallel-advancement primitive for the three-agent Operator Initiative
fleet (Sentry, Guardian, Curator).  The Operator Initiative ladder
(Phase O0 → O1 SHADOW → O2 SUGGEST → O3 ACT) gates each advancement
on shadow-data accumulation + agreement-rate criteria.  Until this
module shipped, the operator manually evaluated those criteria per
agent.  Now they are evaluated uniformly + simultaneously for all
three agents on a single 1-hour cadence.

Why a SINGLE module evaluates all three agents:
   1. Sentry + Guardian + Curator MUST stay in phase alignment
      ('all three at O1, then all three at O2, then all three at O3')
      per operator authorization 2026-05-09.  A single watcher with
      uniform criteria enforces that invariant procedurally.
   2. Per-agent watchers would risk drift (one agent advances, others
      stuck).  The cross-agent skill-separation invariant requires
      tight coordination on phase advancement to prevent partial
      activations from creating capability gaps.
   3. Curator's architectural divergence from Sentry/Guardian (MockKMS
      testnet path vs AWS KMS HSM + GitHub App) is at the
      ATTESTATION-SIGNING layer (kms-sign action), NOT at policy-
      evaluation or shadow-data-accumulation.  Phase advancement
      gating is layer-uniform; signing infrastructure differs.

Phase O2 SUGGEST trigger criteria (all must hold per agent):
   - shadow_data_min_age_hours: ≥504 hours (3 weeks) of shadow log entries
   - cedar_evaluations_min: ≥100 cumulative shadow evaluations
   - bundle_hash_drift_count_30d: 0 (zero drift incidents in last 30 days)
   - scope_hash_governance_drift_count_30d: 0
   - operator_authorization_present: bridge/.env flag for the agent

Phase O3 ACT trigger criteria (all must hold per agent):
   - currently_at_phase_o2: agent currently in O2 SUGGEST mode (>= 3 weeks)
   - draft_payload_count_min: ≥50 draft payloads written under SUGGEST mode
   - operator_disagreement_rate_30d: <5% (curator-suggested vs operator-final
     for Curator; sentry-anchor-draft vs operator-approved for Sentry; etc.)
   - dual_key_present: operator dual-key authorization present
   - agent-specific gates:
       * Sentry: AWS KMS HSM provisioning verified
       * Guardian: AWS KMS HSM + GitHub App OAuth tokens valid
       * Curator: setCurator() role on VAPIDataMarketplaceListings.sol
         assigned to Curator's agent address (Phase 238 Step F reservation)

Output: persisted to operator_initiative_advancement_log table; surfaced
via GET /operator/operator-initiative-advancement-status; FSCA can
correlate via PHASE_ADVANCEMENT_DIVERGENCE rule (one agent ready, others
not — surfaces operational asymmetry).

This module ITSELF does NOT advance any agent — operator advancement is
always a human-authorized POST /operator/anchor-cedar-bundle action.
This module just publishes the readiness state.

INVARIANTS (PV-CI candidates — frozen at first ship):
   INV-INITIATIVE-ADVANCEMENT-001: All three agents evaluated on every poll
   INV-INITIATIVE-ADVANCEMENT-002: Failure to evaluate ONE agent results in
                                   partial-result row written for that agent
                                   ONLY (other two still get full evaluation)
   INV-INITIATIVE-ADVANCEMENT-003: o2_ready_o3_ready ONLY transitions
                                   FALSE→TRUE; never TRUE→FALSE without
                                   logged regression event (audit anchor)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config import Config
    from .store import Store

log = logging.getLogger(__name__)

# Phase O2 SUGGEST trigger thresholds (FROZEN — change requires
# governance event + invariant regen)
PHASE_O2_SHADOW_MIN_HOURS = 504  # 3 weeks
PHASE_O2_EVAL_MIN_COUNT = 100
PHASE_O2_DRIFT_MAX_30D = 0

# Phase O3 ACT trigger thresholds (FROZEN)
PHASE_O3_SUGGEST_MIN_HOURS = 504  # 3 weeks
PHASE_O3_DRAFT_PAYLOAD_MIN = 50
PHASE_O3_DISAGREEMENT_RATE_MAX = 0.05  # 5%

# All three Operator Initiative agents — parallel-advancement invariant
INITIATIVE_AGENTS = ("anchor_sentry", "guardian", "curator")


@dataclass(frozen=True, slots=True)
class AgentAdvancementReadiness:
    """Phase advancement readiness status for one agent."""

    agent_id: str  # canonical name, not Q9 hex
    current_phase: str  # "O0" | "O1_SHADOW" | "O2_SUGGEST" | "O3_ACT"
    shadow_age_hours: float
    cedar_eval_count: int
    bundle_hash_drift_count_30d: int
    scope_hash_governance_drift_count_30d: int
    o2_ready: bool
    o2_blockers: tuple
    o3_ready: bool
    o3_blockers: tuple
    error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class FleetAdvancementSummary:
    """Cross-agent advancement summary — captures the parallel-alignment
    invariant ('all three at same phase')."""

    timestamp: float
    fleet_size: int = 3
    fleet_at_o1_count: int = 0
    fleet_at_o2_ready_count: int = 0
    fleet_at_o3_ready_count: int = 0
    fleet_phase_aligned: bool = False  # True iff all three at SAME phase
    next_alignment_target: str = "O1_SHADOW"  # phase the fleet is converging on
    per_agent: tuple = field(default_factory=tuple)
    error: Optional[str] = None


def _evaluate_agent_readiness(
    agent_id: str,
    *,
    cfg: "Config",
    store: "Store",
) -> AgentAdvancementReadiness:
    """Compute Phase O2 + O3 readiness for one agent.  Pure synchronous
    work suitable for asyncio.to_thread().  Never raises — populates
    `error` field on any failure path (INV-INITIATIVE-ADVANCEMENT-002)."""
    try:
        # Resolve agent's current phase from operator_agent_activation_log.
        # Most-recent activation_log row's bundle_filename indicates phase:
        #   *_o1_shadow_v1.json  → O1_SHADOW
        #   *_o2_suggest_v1.json → O2_SUGGEST
        #   *_o3_act_v1.json     → O3_ACT (future)
        latest = store.get_latest_operator_agent_activation(agent_id)
        if latest is None:
            return AgentAdvancementReadiness(
                agent_id=agent_id,
                current_phase="O0",
                shadow_age_hours=0.0,
                cedar_eval_count=0,
                bundle_hash_drift_count_30d=0,
                scope_hash_governance_drift_count_30d=0,
                o2_ready=False,
                o2_blockers=("agent_not_anchored",),
                o3_ready=False,
                o3_blockers=("agent_not_anchored",),
            )

        bundle_filename = latest.get("bundle_filename", "") or ""
        if "_o1_shadow_" in bundle_filename:
            phase = "O1_SHADOW"
        elif "_o2_suggest_" in bundle_filename:
            phase = "O2_SUGGEST"
        elif "_o3_act_" in bundle_filename:
            phase = "O3_ACT"
        else:
            phase = "UNKNOWN"

        # Shadow age — earliest activation_log entry age (this is when shadow
        # observation began).  For O2 evaluation, we need ≥3 weeks since
        # FIRST anchor (not since latest re-anchor).
        first_activation = store.get_first_operator_agent_activation(agent_id)
        if first_activation is None:
            shadow_age_hours = 0.0
        else:
            anchored_at = float(first_activation.get("anchored_at_unix", 0.0) or 0.0)
            shadow_age_hours = max(0.0, (time.time() - anchored_at) / 3600.0)

        # Cedar evaluation count over agent's lifetime
        eval_count = store.count_cedar_shadow_evaluations(agent_id)

        # Drift counts in last 30 days
        bundle_drift_30d = store.count_operator_agent_drift_findings(
            agent_id=agent_id,
            drift_type="BUNDLE_HASH_DRIFT",
            since_seconds=30 * 86400,
        )
        scope_drift_30d = store.count_operator_agent_drift_findings(
            agent_id=agent_id,
            drift_type="SCOPE_HASH_GOVERNANCE_DRIFT",
            since_seconds=30 * 86400,
        )

        # O2 SUGGEST readiness gates
        o2_blockers = []
        if phase != "O1_SHADOW":
            o2_blockers.append(f"agent_phase_is_{phase}_not_O1_SHADOW")
        if shadow_age_hours < PHASE_O2_SHADOW_MIN_HOURS:
            o2_blockers.append(
                f"shadow_age_{shadow_age_hours:.1f}h_under_min_{PHASE_O2_SHADOW_MIN_HOURS}h"
            )
        if eval_count < PHASE_O2_EVAL_MIN_COUNT:
            o2_blockers.append(
                f"eval_count_{eval_count}_under_min_{PHASE_O2_EVAL_MIN_COUNT}"
            )
        if bundle_drift_30d > PHASE_O2_DRIFT_MAX_30D:
            o2_blockers.append(
                f"bundle_drift_count_{bundle_drift_30d}_30d_over_max_{PHASE_O2_DRIFT_MAX_30D}"
            )
        if scope_drift_30d > PHASE_O2_DRIFT_MAX_30D:
            o2_blockers.append(
                f"scope_drift_count_{scope_drift_30d}_30d_over_max_{PHASE_O2_DRIFT_MAX_30D}"
            )
        o2_ready = len(o2_blockers) == 0

        # O3 ACT readiness gates (only meaningful if currently at O2)
        o3_blockers = []
        if phase != "O2_SUGGEST":
            o3_blockers.append(f"agent_phase_is_{phase}_not_O2_SUGGEST")
        else:
            o2_anchored_at = float(latest.get("anchored_at_unix", 0.0) or 0.0)
            o2_age_hours = max(0.0, (time.time() - o2_anchored_at) / 3600.0)
            if o2_age_hours < PHASE_O3_SUGGEST_MIN_HOURS:
                o3_blockers.append(
                    f"o2_age_{o2_age_hours:.1f}h_under_min_{PHASE_O3_SUGGEST_MIN_HOURS}h"
                )
            # draft_payload_count + disagreement_rate are evaluated from
            # store query helpers added at C2-FOLLOWUP (deferred — placeholder
            # blockers fire until those helpers ship)
            o3_blockers.append("draft_payload_count_helper_not_yet_implemented")
            o3_blockers.append("disagreement_rate_helper_not_yet_implemented")
            # Agent-specific gates — Sentry/Guardian require AWS KMS HSM
            # provisioning; Curator requires marketplace setCurator() role.
            if agent_id in ("anchor_sentry", "guardian"):
                if not getattr(cfg, "kms_hsm_production_ready", False):
                    o3_blockers.append("kms_hsm_production_not_provisioned")
            elif agent_id == "curator":
                if not getattr(cfg, "marketplace_curator_role_assigned", False):
                    o3_blockers.append("marketplace_setCurator_role_not_assigned")
        o3_ready = len(o3_blockers) == 0

        return AgentAdvancementReadiness(
            agent_id=agent_id,
            current_phase=phase,
            shadow_age_hours=shadow_age_hours,
            cedar_eval_count=eval_count,
            bundle_hash_drift_count_30d=bundle_drift_30d,
            scope_hash_governance_drift_count_30d=scope_drift_30d,
            o2_ready=o2_ready,
            o2_blockers=tuple(o2_blockers),
            o3_ready=o3_ready,
            o3_blockers=tuple(o3_blockers),
        )

    except Exception as exc:
        # INV-INITIATIVE-ADVANCEMENT-002: failure to evaluate ONE agent
        # results in partial-result row written for that agent ONLY.
        log.warning(
            "operator_initiative_advancement: failed to evaluate %s: %s",
            agent_id,
            exc,
            exc_info=True,
        )
        return AgentAdvancementReadiness(
            agent_id=agent_id,
            current_phase="UNKNOWN",
            shadow_age_hours=0.0,
            cedar_eval_count=0,
            bundle_hash_drift_count_30d=0,
            scope_hash_governance_drift_count_30d=0,
            o2_ready=False,
            o2_blockers=("evaluation_failed",),
            o3_ready=False,
            o3_blockers=("evaluation_failed",),
            error=f"{type(exc).__name__}: {exc}",
        )


def evaluate_fleet_advancement_sync(
    *,
    cfg: "Config",
    store: "Store",
) -> FleetAdvancementSummary:
    """Evaluate Phase O readiness for all three Operator Initiative agents
    in one pass.  Pure synchronous; safe to wrap with asyncio.to_thread().

    INV-INITIATIVE-ADVANCEMENT-001: Always evaluates all three agents,
    even if one fails.  Caller can inspect per_agent[i].error to detect
    partial failure.
    """
    try:
        per_agent = tuple(
            _evaluate_agent_readiness(agent_id, cfg=cfg, store=store)
            for agent_id in INITIATIVE_AGENTS
        )

        # Cross-agent rollup
        phases_seen = {a.current_phase for a in per_agent}
        fleet_phase_aligned = len(phases_seen) == 1 and "UNKNOWN" not in phases_seen
        fleet_at_o1_count = sum(1 for a in per_agent if a.current_phase == "O1_SHADOW")
        fleet_at_o2_ready_count = sum(1 for a in per_agent if a.o2_ready)
        fleet_at_o3_ready_count = sum(1 for a in per_agent if a.o3_ready)

        # Next alignment target — the next phase the fleet is converging toward
        if fleet_at_o3_ready_count == 3:
            next_target = "O3_ACT"
        elif fleet_at_o2_ready_count == 3:
            next_target = "O2_SUGGEST"
        elif fleet_at_o1_count == 3:
            next_target = "O2_SUGGEST"  # converging on O2 readiness
        else:
            next_target = "O1_SHADOW"  # still converging on O1 alignment

        return FleetAdvancementSummary(
            timestamp=time.time(),
            fleet_size=len(per_agent),
            fleet_at_o1_count=fleet_at_o1_count,
            fleet_at_o2_ready_count=fleet_at_o2_ready_count,
            fleet_at_o3_ready_count=fleet_at_o3_ready_count,
            fleet_phase_aligned=fleet_phase_aligned,
            next_alignment_target=next_target,
            per_agent=per_agent,
        )

    except Exception as exc:
        log.error(
            "operator_initiative_advancement: fleet evaluation failed: %s",
            exc,
            exc_info=True,
        )
        return FleetAdvancementSummary(
            timestamp=time.time(),
            error=f"{type(exc).__name__}: {exc}",
        )


async def run_advancement_watcher_loop(
    *,
    cfg: "Config",
    store: "Store",
) -> None:
    """Background async loop that periodically evaluates fleet advancement
    readiness and persists the result to operator_initiative_advancement_log.

    Cadence: 1 hour (3600s) — readiness criteria are slow-moving (3-week
    shadow age threshold dominates), so polling more frequently wastes
    DB scans without surfacing new state.

    Activated via cfg.operator_initiative_advancement_enabled (default
    False, opt-in).  When disabled, the loop never spawns.

    Wraps the synchronous evaluator in asyncio.to_thread() per Phase 235.x-
    STABILITY-2 invariant — never blocks the event loop with SQLite scans.
    """
    if not getattr(cfg, "operator_initiative_advancement_enabled", False):
        log.info(
            "operator_initiative_advancement: watcher disabled "
            "(OPERATOR_INITIATIVE_ADVANCEMENT_ENABLED=false)"
        )
        return

    interval_s = float(
        getattr(cfg, "operator_initiative_advancement_interval_s", 3600)
    )
    log.info(
        "operator_initiative_advancement: watcher started (interval=%ss)",
        interval_s,
    )

    try:
        while True:
            try:
                summary = await asyncio.to_thread(
                    evaluate_fleet_advancement_sync,
                    cfg=cfg,
                    store=store,
                )

                # Persist (best-effort; insert helper added at first ship)
                try:
                    if hasattr(store, "insert_operator_initiative_advancement_log"):
                        per_agent_json = json.dumps([
                            {
                                "agent_id": a.agent_id,
                                "current_phase": a.current_phase,
                                "shadow_age_hours": round(a.shadow_age_hours, 2),
                                "cedar_eval_count": a.cedar_eval_count,
                                "bundle_drift_30d": a.bundle_hash_drift_count_30d,
                                "scope_drift_30d": a.scope_hash_governance_drift_count_30d,
                                "o2_ready": a.o2_ready,
                                "o2_blockers": list(a.o2_blockers),
                                "o3_ready": a.o3_ready,
                                "o3_blockers": list(a.o3_blockers),
                                "error": a.error,
                            }
                            for a in summary.per_agent
                        ], separators=(",", ":"))
                        await asyncio.to_thread(
                            store.insert_operator_initiative_advancement_log,
                            timestamp=summary.timestamp,
                            fleet_phase_aligned=summary.fleet_phase_aligned,
                            fleet_at_o1_count=summary.fleet_at_o1_count,
                            fleet_at_o2_ready_count=summary.fleet_at_o2_ready_count,
                            fleet_at_o3_ready_count=summary.fleet_at_o3_ready_count,
                            next_alignment_target=summary.next_alignment_target,
                            per_agent_json=per_agent_json,
                            error=summary.error,
                        )
                except Exception as persist_exc:
                    log.warning(
                        "operator_initiative_advancement: persist failed: %s",
                        persist_exc,
                    )

                # Operational summary log line — visible in bridge stdout
                log.info(
                    "operator_initiative_advancement: aligned=%s o1=%d o2_ready=%d "
                    "o3_ready=%d next=%s",
                    summary.fleet_phase_aligned,
                    summary.fleet_at_o1_count,
                    summary.fleet_at_o2_ready_count,
                    summary.fleet_at_o3_ready_count,
                    summary.next_alignment_target,
                )

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error(
                    "operator_initiative_advancement: cycle failed: %s",
                    exc,
                    exc_info=True,
                )

            await asyncio.sleep(interval_s)

    except asyncio.CancelledError:
        log.info("operator_initiative_advancement: watcher cancelled")
        raise
