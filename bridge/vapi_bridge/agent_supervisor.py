"""Phase 83 — AgentSupervisor: fleet health monitor for all VAPI agents.

Polls SQLite activity signals every 5 minutes (one check per agent).
Reports HEALTHY / STALE / UNKNOWN per agent based on last table write.
Publishes agent_health_report to AgentMessageBus for downstream consumers.
Logs results to supervisor_health_log for operator visibility.

Fleet health:
  ALL_HEALTHY — all 9 registered agents have activity within stale_threshold
  DEGRADED    — 1–2 agents STALE or UNKNOWN
  CRITICAL    — 3+ agents STALE/UNKNOWN, OR any core agent (session_adjudicator,
                ruling_enforcement_agent) is STALE

W1 mitigation: supervisor reads timestamp + count (not just timestamp) to
distinguish a genuinely active agent from a zombie writing duplicate rows.
A device-diversity check flags agents with activity_count > 0 but distinct_devices == 0
as ZOMBIE — a new health status indicating stuck/looping behaviour.
"""

import asyncio
import logging
import time

log = logging.getLogger(__name__)

_SUPERVISOR_POLL_S = 300  # 5 minutes

# Health status constants
HEALTHY = "HEALTHY"
STALE = "STALE"
UNKNOWN = "UNKNOWN"
ZOMBIE = "ZOMBIE"   # writes activity but to 0 distinct devices (W1 mitigation)

# Fleet-level health
ALL_HEALTHY = "ALL_HEALTHY"
DEGRADED = "DEGRADED"
CRITICAL = "CRITICAL"

# Core agents — STALE status here elevates to CRITICAL fleet health
_CORE_AGENTS = {"session_adjudicator", "ruling_enforcement_agent"}

# Per-agent activity check descriptors
# table: SQLite table to query
# ts_col: timestamp column (recency check)
# filter: optional WHERE clause fragment (no WHERE keyword)
# device_col: column for distinct-device diversity check (None = skip diversity)
_AGENT_CHECKS: dict[str, dict] = {
    "session_adjudicator": {
        "table": "agent_rulings",
        "ts_col": "created_at",
        "filter": "source_agent LIKE 'session_adjudicator%'",
        "device_col": "device_id",
    },
    "ruling_enforcement_agent": {
        "table": "on_chain_rulings",
        "ts_col": "created_at",
        "filter": None,
        "device_col": "device_id",
    },
    "class_j_detector": {
        "table": "class_j_assessments",
        "ts_col": "assessed_at",
        "filter": None,
        "device_col": "device_id",
    },
    "federation_broadcast_agent": {
        "table": "federation_threat_signals",
        "ts_col": "created_at",
        "filter": "broadcast_at IS NOT NULL",
        "device_col": "device_id",
    },
    "live_mode_activation_agent": {
        "table": "live_mode_transitions",
        "ts_col": "created_at",
        "filter": None,
        "device_col": None,
    },
    "session_adjudicator_validator": {
        "table": "ruling_validation_log",
        "ts_col": "created_at",
        "filter": None,
        "device_col": "device_id",
    },
    "ruling_provenance_anchor_agent": {
        "table": "ruling_provenance_anchors",
        "ts_col": "created_at",
        "filter": None,
        "device_col": None,
    },
    "data_curator_agent": {
        "table": "data_lineage",
        "ts_col": "last_updated",
        "filter": None,
        "device_col": "device_id",
    },
    "ceremony_watchdog_agent": {
        "table": "agent_events",
        "ts_col": "created_at",
        "filter": "source = 'ceremony_watchdog_agent'",
        "device_col": None,
    },
}


class AgentSupervisor:
    """Phase 83 — Fleet health monitor for all VAPI autonomous agents.

    Polls SQLite activity signals every 5 minutes.
    Publishes agent_health_report to AgentMessageBus after each check.
    Logs results to supervisor_health_log for GET /agent/supervisor-status.
    Never raises — errors produce UNKNOWN health status, not crashes.
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus
        self._stale_s = float(
            getattr(cfg, "supervisor_stale_threshold_minutes", 15)
        ) * 60.0

    async def run_supervisor_loop(self) -> None:
        """Background loop: check fleet health every 5 minutes."""
        log.info(
            "AgentSupervisor started (Phase 83) stale_threshold=%.0fs",
            self._stale_s,
        )
        while True:
            try:
                await asyncio.sleep(_SUPERVISOR_POLL_S)
                await self._check_and_report()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("AgentSupervisor: cycle error: %s", exc)

    async def _check_and_report(self) -> dict:
        """Run health checks for all agents, persist, publish, and return snapshot."""
        snapshot = self.check_fleet_health()
        # Persist each agent result to supervisor_health_log
        for agent_name, result in snapshot["agents"].items():
            try:
                self._store.insert_supervisor_health_log(
                    agent_name=agent_name,
                    health=result["health"],
                    last_active_at=result.get("last_active_at"),
                    activity_count=result.get("activity_count", 0),
                )
            except Exception as exc:
                log.debug("AgentSupervisor: log write failed for %s: %s", agent_name, exc)
        # Publish to bus
        if self._bus is not None:
            try:
                await self._bus.publish(
                    "agent_health_report",
                    {
                        "fleet_health": snapshot["fleet_health"],
                        "healthy_count": snapshot["healthy_count"],
                        "stale_count": snapshot["stale_count"],
                        "unknown_count": snapshot["unknown_count"],
                        "zombie_count": snapshot.get("zombie_count", 0),
                    },
                    source="agent_supervisor",
                )
            except Exception as exc:
                log.debug("AgentSupervisor: bus publish failed: %s", exc)
        log.info(
            "AgentSupervisor: fleet=%s healthy=%d stale=%d unknown=%d",
            snapshot["fleet_health"],
            snapshot["healthy_count"],
            snapshot["stale_count"],
            snapshot["unknown_count"],
        )
        return snapshot

    def check_fleet_health(self) -> dict:
        """Synchronous fleet health snapshot. Safe to call from tests and REST handlers.

        Returns dict with:
          agents: {agent_name: {health, last_active_at, activity_count}}
          fleet_health: ALL_HEALTHY | DEGRADED | CRITICAL
          healthy_count, stale_count, unknown_count, zombie_count
          stale_threshold_minutes, timestamp
        """
        now = time.time()
        agent_results: dict[str, dict] = {}
        for agent_name, spec in _AGENT_CHECKS.items():
            try:
                result = self._store.get_agent_activity(
                    table=spec["table"],
                    ts_col=spec["ts_col"],
                    filter_sql=spec.get("filter"),
                    device_col=spec.get("device_col"),
                )
                last_active = result.get("last_active_at")
                count = result.get("activity_count", 0)
                distinct = result.get("distinct_devices")

                if last_active is None or count == 0:
                    health = UNKNOWN
                elif now - last_active > self._stale_s:
                    health = STALE
                elif distinct is not None and distinct == 0 and count > 0:
                    health = ZOMBIE
                else:
                    health = HEALTHY

                agent_results[agent_name] = {
                    "health": health,
                    "last_active_at": last_active,
                    "activity_count": count,
                    "distinct_devices": distinct,
                }
            except Exception as exc:
                log.debug("AgentSupervisor: check failed for %s: %s", agent_name, exc)
                agent_results[agent_name] = {
                    "health": UNKNOWN,
                    "last_active_at": None,
                    "activity_count": 0,
                    "distinct_devices": None,
                }

        # Compute fleet-level health
        healthy = sum(1 for r in agent_results.values() if r["health"] == HEALTHY)
        stale = sum(1 for r in agent_results.values() if r["health"] == STALE)
        unknown = sum(1 for r in agent_results.values() if r["health"] == UNKNOWN)
        zombie = sum(1 for r in agent_results.values() if r["health"] == ZOMBIE)
        non_healthy = stale + unknown + zombie

        core_stale = any(
            agent_results.get(name, {}).get("health") in (STALE, ZOMBIE)
            for name in _CORE_AGENTS
        )
        if core_stale or non_healthy >= 3:
            fleet_health = CRITICAL
        elif non_healthy >= 1:
            fleet_health = DEGRADED
        else:
            fleet_health = ALL_HEALTHY

        return {
            "agents": agent_results,
            "fleet_health": fleet_health,
            "healthy_count": healthy,
            "stale_count": stale,
            "unknown_count": unknown,
            "zombie_count": zombie,
            "stale_threshold_minutes": self._stale_s / 60.0,
            "timestamp": now,
        }
