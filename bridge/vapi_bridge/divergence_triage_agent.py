"""Phase 91 — Divergence Triage Agent.

Polls ruling_validation_log for diverged sessions with non-nominal reasons
(populated by Phase 88 _extract_divergence_fields). Groups by device_id,
detects adversarial pattern clusters, escalates via bus and stores in
divergence_triage_reports table.

Pattern escalation thresholds:
  ML-bot cluster:     device has >=2 divergences with class_j_ml_bot_risk=HIGH
  Cheat cluster:      device has >=1 divergence with hard_cheat_codes non-empty
  Enrollment anomaly: device has >=3 divergences with enrollment_status != 'eligible'

triage_confidence_score = clean_devices / all_diverged_devices (Phase 89 component).
Publishes divergence_pattern_detected bus event per escalation.
Never raises.
"""
import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300
_ML_BOT_THRESHOLD = 2
_CHEAT_THRESHOLD = 1
_ENROLLMENT_THRESHOLD = 3


class DivergenceTriageAgent:
    """Phase 91 — Cross-session divergence pattern detector and escalator."""

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus

    async def run_event_consumer(self) -> None:
        log.info("DivergenceTriageAgent started (Phase 91)")
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._triage_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("DivergenceTriageAgent: cycle error: %s", exc)

    async def _triage_cycle(self) -> None:
        try:
            with self._store._conn() as conn:
                rows = conn.execute(
                    "SELECT device_id, divergence_reason FROM ruling_validation_log "
                    "WHERE divergence=1 AND divergence_reason IS NOT NULL "
                    "AND divergence_reason != '{}' "
                    "ORDER BY device_id, created_at ASC"
                ).fetchall()
        except Exception as exc:
            log.warning("DivergenceTriageAgent: query failed: %s", exc)
            return

        if not rows:
            return

        device_reasons: dict[str, list[dict]] = {}
        for row in rows:
            did = row["device_id"]
            try:
                reason = json.loads(row["divergence_reason"] or "{}")
            except (json.JSONDecodeError, TypeError):
                reason = {}
            if reason:
                device_reasons.setdefault(did, []).append(reason)

        for device_id, reasons in device_reasons.items():
            await self._triage_device(device_id, reasons)

    async def _triage_device(self, device_id: str, reasons: list[dict]) -> None:
        ml_bot_high_count = sum(
            1 for r in reasons if r.get("class_j_ml_bot_risk") == "HIGH"
        )
        cheat_count = sum(
            1 for r in reasons if r.get("hard_cheat_codes")
        )
        enrollment_anomaly_count = sum(
            1 for r in reasons
            if r.get("enrollment_status") and r["enrollment_status"] != "eligible"
        )

        patterns = []
        if ml_bot_high_count >= _ML_BOT_THRESHOLD:
            patterns.append(f"ml_bot_cluster:{ml_bot_high_count}x_HIGH")
        if cheat_count >= _CHEAT_THRESHOLD:
            patterns.append(f"cheat_cluster:{cheat_count}x_codes")
        if enrollment_anomaly_count >= _ENROLLMENT_THRESHOLD:
            patterns.append(f"enrollment_anomaly:{enrollment_anomaly_count}x")

        escalated = len(patterns) > 0
        pattern_str = ",".join(patterns) if patterns else None

        self._store.insert_divergence_triage_report(
            device_id=device_id,
            divergence_count=len(reasons),
            escalated=int(escalated),
            patterns=pattern_str,
            ml_bot_high_count=ml_bot_high_count,
            cheat_count=cheat_count,
            enrollment_anomaly_count=enrollment_anomaly_count,
        )

        if escalated:
            log.warning(
                "DivergenceTriageAgent: ESCALATED device=%s patterns=%s divergences=%d",
                device_id[:12], pattern_str, len(reasons),
            )
            if self._bus is not None:
                try:
                    import asyncio as _asyncio
                    _asyncio.ensure_future(self._bus.publish(
                        "divergence_pattern_detected",
                        {
                            "device_id": device_id,
                            "patterns": patterns,
                            "divergence_count": len(reasons),
                        },
                        "divergence_triage_agent",
                    ))
                except Exception as _bus_exc:
                    log.debug("DivergenceTriageAgent: bus publish failed: %s", _bus_exc)
        else:
            log.info(
                "DivergenceTriageAgent: device=%s clean (%d divergences, no pattern)",
                device_id[:12], len(reasons),
            )
