"""Store mixin — L9 x Retina Fusion v2 oracle-panel verdict log (advisory; no PoAC/chain)."""

from __future__ import annotations

import json
import time
from typing import Any, Optional


class L9FusionMixin:
    """l9_fusion_event_log persistence for oracle-panel / tri-channel fusion reports."""

    def insert_l9_fusion_event(
        self,
        *,
        device_id: str,
        fusion_verdict: str,
        record_hash_hex: str = "",
        coupling_score: Optional[float] = None,
        negative_control: Optional[float] = None,
        decoupled_energy: Optional[float] = None,
        coherence_verdict: str = "",
        coherence_ratio: float = 0.0,
        continuous_axis: str = "",
        capture_telemetry_json: str = "{}",
        report_json: str = "{}",
        ts: float | None = None,
    ) -> int:
        created = float(ts if ts is not None else time.time())
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO l9_fusion_event_log (
                    device_id, record_hash_hex, coupling_score, negative_control,
                    decoupled_energy, coherence_verdict, coherence_ratio, fusion_verdict,
                    continuous_axis, capture_telemetry_json, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id, record_hash_hex or "", coupling_score, negative_control,
                    decoupled_energy, coherence_verdict or "", float(coherence_ratio),
                    fusion_verdict, continuous_axis or "",
                    capture_telemetry_json or "{}", report_json or "{}", created,
                ),
            )
            return int(cur.lastrowid)

    def get_l9_fusion_status(self, device_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM l9_fusion_event_log WHERE device_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM l9_fusion_event_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        latest = dict(rows[0]) if rows else {}
        telemetry: dict[str, Any] = {}
        if latest.get("capture_telemetry_json"):
            try:
                telemetry = json.loads(latest["capture_telemetry_json"])
            except (json.JSONDecodeError, TypeError):
                telemetry = {}
        return {
            "total_rows": len(rows),
            "latest_fusion_verdict": latest.get("fusion_verdict", ""),
            "latest_continuous_axis": latest.get("continuous_axis", ""),
            "latest_coherence_verdict": latest.get("coherence_verdict", ""),
            "latest_coupling_score": latest.get("coupling_score"),
            "latest_record_hash": latest.get("record_hash_hex", ""),
            "latest_device_id": latest.get("device_id", ""),
            "latest_created_at": latest.get("created_at", 0.0),
            "latest_capture_telemetry": telemetry,
            "entries": [dict(r) for r in rows],
        }
