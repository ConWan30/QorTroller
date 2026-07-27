"""Cost monitoring and alerting for NIM API calls.

Tracks NIM API costs and provides alerts when thresholds are exceeded.
"""
from __future__ import annotations

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class CostThreshold:
    """Cost threshold configuration."""
    warning_usd: float
    critical_usd: float
    window_hours: int


class NIMCostMonitor:
    """Monitor and alert on NIM API costs."""

    def __init__(self, store):
        self._store = store
        self._thresholds = CostThreshold(
            warning_usd=50.0,    # $50 warning
            critical_usd=100.0,  # $100 critical
            window_hours=24      # 24-hour window
        )

    def check_cost_thresholds(self) -> Dict[str, Any]:
        """Check if cost thresholds are exceeded."""
        cutoff = time.time() - (self._thresholds.window_hours * 3600)

        with self._store._conn() as conn:
            row = conn.execute(
                "SELECT SUM(estimated_cost_usd) as total_cost, "
                "COUNT(*) as call_count "
                "FROM nim_audit_log "
                "WHERE timestamp >= ?",
                (cutoff,)
            ).fetchone()

        total_cost = float(row["total_cost"] or 0.0)
        call_count = int(row["call_count"] or 0)

        status = "normal"
        if total_cost >= self._thresholds.critical_usd:
            status = "critical"
            log.critical(
                f"NIM cost critical threshold exceeded: "
                f"${total_cost:.2f} > ${self._thresholds.critical_usd:.2f}"
            )
        elif total_cost >= self._thresholds.warning_usd:
            status = "warning"
            log.warning(
                f"NIM cost warning threshold exceeded: "
                f"${total_cost:.2f} > ${self._thresholds.warning_usd:.2f}"
            )

        return {
            "window_hours": self._thresholds.window_hours,
            "total_cost_usd": total_cost,
            "call_count": call_count,
            "status": status,
            "warning_threshold_usd": self._thresholds.warning_usd,
            "critical_threshold_usd": self._thresholds.critical_usd
        }