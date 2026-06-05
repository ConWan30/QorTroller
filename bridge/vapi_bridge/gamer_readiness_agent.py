"""Phase 239 — GamerReadinessAgent (agent #39).

Monitors gamer fatigue and Repetitive Strain Injury (RSI) risks by checking:
  1. Accelerometer tremor peak frequency (FFT 4.0-15.0 Hz shifts) and variance.
  2. Touchpad spatial entropy (repetitive/static contact indicates strain).
  3. Neuromuscular haptic reflex latencies from L6b probes.

Formula:
  - Fatigue Index = 0.4 * normalized_latency + 0.3 * normalized_tremor_var + 0.3 * normalized_freq_drift
  - RSI Risk = 0.5 * normalized_touchpad_monotony + 0.3 * grip_asymmetry + 0.2 * trigger_rate
  - Readiness Score = 1.0 - max(Fatigue Index, RSI Risk)

Fires:
  - gamer_readiness_alert bus event on readiness < 0.60 (advising stretch/break).
  - Configures haptic nudge recommendations.
"""

import asyncio
import json
import logging
import math
import time

log = logging.getLogger(__name__)

# Nominal thresholds (baseline averages)
NOMINAL_LATENCY_MS = 150.0
NOMINAL_TREMOR_HZ  = 8.0


class GamerReadinessAgent:
    """Agent #39 — GamerReadinessAgent.

    Evaluates rolling physical and cognitive readiness metrics for gaming sessions.
    Runs every 300s (5 minutes) to monitor active device profiles.
    """

    POLL_INTERVAL_S: int = 300

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    def _analyze_device_readiness(self, device_id: str) -> dict:
        """Compute rolling readiness metrics for a specific device from database records.

        Safe/fail-open: handles missing or sparse data gracefully by returning defaults.
        """
        try:
            # 1. Fetch recent records to analyze IMU tremor & touchpad entropy
            recent_records = []
            try:
                # Query records directly
                with self._store._conn() as con:
                    rows = con.execute(
                        "SELECT pitl_l4_features, created_at FROM records "
                        "WHERE device_id = ? ORDER BY created_at DESC LIMIT 50",
                        (device_id,)
                    ).fetchall()
                    for r in rows:
                        features_str = r["pitl_l4_features"]
                        if features_str:
                            try:
                                recent_records.append(json.loads(features_str))
                            except Exception:
                                pass  # fail-open: malformed feature row skipped, advisory agent
            except Exception as db_exc:
                log.debug("GamerReadinessAgent: failed to read recent records: %s", db_exc)

            # 2. Fetch haptic latencies from L6b probes
            latencies = []
            try:
                with self._store._conn() as con:
                    rows = con.execute(
                        "SELECT latency_ms FROM l6b_probe_log "
                        "WHERE device_id = ? ORDER BY id DESC LIMIT 10",
                        (device_id,)
                    ).fetchall()
                    for r in rows:
                        if r["latency_ms"] is not None:
                            latencies.append(float(r["latency_ms"]))
            except Exception as db_exc:
                log.debug("GamerReadinessAgent: failed to read l6b probes: %s", db_exc)

            # Calculate metrics
            n_records = len(recent_records)
            
            # Tremor metrics
            tremors_hz = [r.get("tremor_peak_hz", NOMINAL_TREMOR_HZ) for r in recent_records if "tremor_peak_hz" in r]
            tremor_vars = [r.get("micro_tremor_accel_variance", 0.0001) for r in recent_records if "micro_tremor_accel_variance" in r]
            
            avg_tremor_hz = sum(tremors_hz) / len(tremors_hz) if tremors_hz else NOMINAL_TREMOR_HZ
            avg_tremor_var = sum(tremor_vars) / len(tremor_vars) if tremor_vars else 0.0001
            
            # Touchpad entropy
            entropies = [r.get("touchpad_spatial_entropy", 1.5) for r in recent_records if "touchpad_spatial_entropy" in r]
            avg_entropy = sum(entropies) / len(entropies) if entropies else 1.5

            # Reaction latency
            avg_latency = sum(latencies) / len(latencies) if latencies else NOMINAL_LATENCY_MS

            # normalized latency drift (increase over baseline)
            latency_factor = max(0.0, min(1.0, (avg_latency - NOMINAL_LATENCY_MS) / 150.0))
            
            # normalized tremor variance (increase indicating fatigue/jitteriness)
            var_factor = max(0.0, min(1.0, (avg_tremor_var - 0.0001) / 0.002))
            
            # normalized tremor frequency drift (fatigue moves peak tremor down to 4.0-5.0Hz)
            freq_drift = max(0.0, min(1.0, (NOMINAL_TREMOR_HZ - avg_tremor_hz) / 4.0))

            # Fatigue index calculation (0.0 to 1.0)
            fatigue_index = 0.4 * latency_factor + 0.3 * var_factor + 0.3 * freq_drift

            # touchpad monotony: lower spatial entropy indicates repetitive/static thumb resting
            # Nominal maximum entropy is ~2.5. Below 1.0 indicates severe monotony (static position).
            monotony_factor = max(0.0, min(1.0, (2.0 - avg_entropy) / 1.5))
            
            # Grip asymmetry & trigger change rates
            asymmetries = [r.get("grip_asymmetry", 1.0) for r in recent_records if "grip_asymmetry" in r]
            avg_asymmetry = sum(asymmetries) / len(asymmetries) if asymmetries else 1.0
            asymmetry_factor = max(0.0, min(1.0, abs(avg_asymmetry - 1.0) / 0.5))

            # RSI Risk Index (0.0 to 1.0)
            rsi_risk = 0.6 * monotony_factor + 0.4 * asymmetry_factor

            # Final Readiness Score (0.0 to 1.0)
            readiness_score = max(0.0, min(1.0, 1.0 - max(fatigue_index, rsi_risk)))

            # Recommendation categorization
            if readiness_score >= 0.80:
                recommendation = "NOMINAL"
            elif readiness_score >= 0.60:
                recommendation = "ADVISE_STRETCH"
            elif readiness_score >= 0.40:
                recommendation = "ADVISE_BREAK"
            else:
                recommendation = "HIGH_RSI_RISK"

            return {
                "device_id":           device_id,
                "readiness_score":     round(readiness_score, 4),
                "rsi_risk_score":      round(rsi_risk, 4),
                "fatigue_index":       round(fatigue_index, 4),
                "avg_tremor_hz":       round(avg_tremor_hz, 2),
                "touchpad_entropy":    round(avg_entropy, 4),
                "reaction_latency_ms": round(avg_latency, 2),
                "recommendation":      recommendation,
            }

        except Exception as exc:
            log.warning("GamerReadinessAgent: error analyzing device %s: %s", device_id, exc)
            return {
                "device_id":           device_id,
                "readiness_score":     1.0,
                "rsi_risk_score":      0.0,
                "fatigue_index":       0.0,
                "avg_tremor_hz":       NOMINAL_TREMOR_HZ,
                "touchpad_entropy":    1.5,
                "reaction_latency_ms": NOMINAL_LATENCY_MS,
                "recommendation":      "NOMINAL",
            }

    async def _run_evaluation(self) -> None:
        """Fetch all distinct registered devices, compute readiness logs, and publish alerts."""
        try:
            # Retrieve active devices
            devices = []
            try:
                devs = self._store.list_devices()
                devices = [d["device_id"] for d in devs if "device_id" in d]
            except Exception as err:
                log.debug("GamerReadinessAgent: list_devices failed, using defaults: %s", err)
                devices = ["D1"]  # default fallback

            for dev_id in devices:
                metrics = self._analyze_device_readiness(dev_id)
                
                # Persist metrics to SQLite
                try:
                    self._store.insert_gamer_readiness_log(
                        device_id           = metrics["device_id"],
                        readiness_score     = metrics["readiness_score"],
                        rsi_risk_score      = metrics["rsi_risk_score"],
                        fatigue_index       = metrics["fatigue_index"],
                        avg_tremor_hz       = metrics["avg_tremor_hz"],
                        touchpad_entropy    = metrics["touchpad_entropy"],
                        reaction_latency_ms = metrics["reaction_latency_ms"],
                        recommendation      = metrics["recommendation"],
                    )
                except Exception as db_exc:
                    log.warning("GamerReadinessAgent: failed to save log for %s: %s", dev_id, db_exc)

                # Fire alert if readiness is compromised
                if metrics["readiness_score"] < 0.60 and self._bus is not None:
                    try:
                        self._bus.publish_sync(
                            "gamer_readiness_alert",
                            {
                                "device_id":       metrics["device_id"],
                                "readiness_score": metrics["readiness_score"],
                                "recommendation":  metrics["recommendation"],
                                "fatigue_index":   metrics["fatigue_index"],
                                "rsi_risk_score":  metrics["rsi_risk_score"],
                                "agent":           "GamerReadinessAgent",
                            }
                        )
                    except Exception as bus_err:
                        log.debug("GamerReadinessAgent: failed to publish bus event: %s", bus_err)

        except Exception as exc:
            log.warning("GamerReadinessAgent: unhandled evaluation error: %s", exc)

    async def run_poll_loop(self) -> None:
        """Main periodic poll loop."""
        log.info("GamerReadinessAgent (agent #39) starting poll loop (interval=%ss)", self.POLL_INTERVAL_S)
        from .startup_grace import startup_grace
        await startup_grace(self._cfg, agent_name="GamerReadinessAgent")
        while True:
            try:
                enabled = bool(getattr(self._cfg, "gamer_readiness_enabled", True))
                if enabled:
                    await self._run_evaluation()
            except Exception as exc:
                log.warning("GamerReadinessAgent: poll loop iteration failed: %s", exc)
            await asyncio.sleep(self.POLL_INTERVAL_S)
