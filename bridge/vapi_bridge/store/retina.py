"""Store mixin — Retina perception event log (Phase B)."""

from __future__ import annotations

import json
import time
from typing import Any


class RetinaMixin:
    """retina_event_log persistence for trio-retina advisory events."""

    def insert_retina_event_batch(
        self,
        *,
        device_id: str,
        events_json: str,
        world_state_json: str = "",
        record_hash_hex: str = "",
        anomaly_count: int = 0,
        state_commitment_hex: str = "",
        ts_ns: int | None = None,
        source: str = "hid",
    ) -> int:
        ts = float((ts_ns or time.time_ns()) / 1e9)
        _src = str(source or "hid")[:32]
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO retina_event_log (
                    device_id, events_json, world_state_json,
                    record_hash_hex, state_commitment_hex, anomaly_count,
                    created_at, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    events_json,
                    world_state_json,
                    record_hash_hex or "",
                    state_commitment_hex or "",
                    int(anomaly_count),
                    ts,
                    _src,
                ),
            )
            return int(cur.lastrowid)

    def insert_retina_policy_log(
        self,
        *,
        event_type: str,
        arm_source: str = "",
        device_id: str = "",
        qualifiers_json: str = "{}",
        effective_perception: bool = False,
        ts: float | None = None,
    ) -> int:
        created = float(ts if ts is not None else time.time())
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO retina_policy_log (
                    event_type, arm_source, device_id, qualifiers_json,
                    effective_perception, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    arm_source,
                    device_id,
                    qualifiers_json,
                    1 if effective_perception else 0,
                    created,
                ),
            )
            return int(cur.lastrowid)

    def get_retina_policy_status(self, limit: int = 10) -> dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM retina_policy_log
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        latest = dict(rows[0]) if rows else {}
        return {
            "total_log_rows": len(rows),
            "latest_event_type": latest.get("event_type", ""),
            "latest_arm_source": latest.get("arm_source", ""),
            "latest_device_id": latest.get("device_id", ""),
            "latest_effective_perception": bool(latest.get("effective_perception")),
            "latest_created_at": latest.get("created_at", 0.0),
            "entries": [dict(r) for r in rows],
        }

    def get_retina_event_status(self, device_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    """
                    SELECT * FROM retina_event_log
                    WHERE device_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM retina_event_log
                    ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            latest = dict(rows[0]) if rows else {}
            anomaly_total = sum(int(r["anomaly_count"] or 0) for r in rows)
            return {
                "total_rows": len(rows),
                "anomaly_count_recent": anomaly_total,
                "latest_record_hash": latest.get("record_hash_hex", ""),
                "latest_state_commitment": latest.get("state_commitment_hex", ""),
                "latest_device_id": latest.get("device_id", ""),
                "latest_created_at": latest.get("created_at", 0.0),
                "entries": [dict(r) for r in rows],
            }

    def get_retina_alerts_since(self, since_ts: float, limit: int = 50) -> list[dict[str, Any]]:
        """Rows with anomaly_count > 0 since ``since_ts`` (for TUI / SSE polling)."""
        limit = max(1, min(int(limit), 200))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, device_id, record_hash_hex, state_commitment_hex,
                       anomaly_count, created_at, events_json
                FROM retina_event_log
                WHERE created_at >= ? AND anomaly_count > 0
                ORDER BY id DESC LIMIT ?
                """,
                (since_ts, limit),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                evs = json.loads(d.get("events_json") or "[]")
                d["events"] = evs[:5]
            except json.JSONDecodeError:
                d["events"] = []
            del d["events_json"]
            out.append(d)
        return out

    def get_retina_by_record_hash(self, record_hash_hex: str) -> dict[str, Any] | None:
        """Latest retina_event_log row for a PoAC record hash (adjudicator / FSCA join)."""
        if not record_hash_hex:
            return None
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM retina_event_log
                WHERE record_hash_hex = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (record_hash_hex,),
            ).fetchone()
        return dict(row) if row else None
