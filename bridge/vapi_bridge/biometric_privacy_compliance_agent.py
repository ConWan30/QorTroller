"""Phase 159 — BiometricPrivacyComplianceAgent (agent #22).

Implements BP-001 Temporal Biometric Decay monitoring:
  TBD(t) = e^(-λt) where λ = ln(2) / τ_half; τ_half = 90 days (configurable).
  Effective biometric weight = raw_weight × TBD(age_days).

The agent monitors enrolled player records for biometric age, computing the
mean decay factor across all enrolled sessions. When the mean decay factor
falls below the warning threshold (0.25 = ~2 half-lives), it fires a
biometric_decay_warning bus event.

BP-001 regulatory alignment:
  GDPR Art.5.1.e — Storage limitation via automatic decay weighting
  CCPA retention minimization — No indefinite biometric storage
  EU AI Act — High-risk biometric data time-boxed

Agent #22 is the last agent in the initial fleet of 22.
Infrastructure-first: biometric_privacy_enabled=True default but BP-001
decay weighting is advisory only — does NOT modify stored threshold values.
"""
import asyncio
import logging
import math
import time

log = logging.getLogger(__name__)

# BP-001 constants (frozen — per VAPI_INVARIANTS.md §6)
BP_001_HALF_LIFE_DAYS: float = 90.0
BP_001_DECAY_LAMBDA: float   = math.log(2) / BP_001_HALF_LIFE_DAYS
BP_001_WARNING_THRESHOLD: float = 0.25  # ~2 half-lives ≈ 180 days


def tbd_decay_factor(age_days: float, half_life_days: float = BP_001_HALF_LIFE_DAYS) -> float:
    """Compute BP-001 Temporal Biometric Decay factor for a record of given age.

    Returns value in (0, 1.0]:
      age=0d  → 1.000  (fresh)
      age=90d → 0.500  (one half-life)
      age=180d→ 0.250  (two half-lives — warning threshold)
      age=365d→ 0.065  (4+ half-lives — near zero weight)

    Never raises; returns 0.0 for negative age (clamps to 0).
    """
    if age_days < 0:
        return 0.0
    lam = math.log(2) / max(half_life_days, 1.0)
    return math.exp(-lam * age_days)


class BiometricPrivacyComplianceAgent:
    """Agent #22 — BP-001 Temporal Biometric Decay monitor.

    Polls enrolled player records every 6h (21600s default).
    For each enrolled session, computes its biometric age and TBD decay factor.
    Stores the fleet-wide summary to privacy_compliance_log.
    Publishes biometric_decay_warning bus event when mean_decay_factor < 0.25.

    Privacy budget tracking (future BP-003 DPT):
      privacy_budget_epsilon is stored as advisory metadata only.
      Phase 159 scope = BP-001 monitoring; BP-002..BP-007 are future phases.
    """

    POLL_INTERVAL_S: int = 21600  # 6 hours

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    def _compute_compliance_report(self) -> dict:
        """Compute BP-001 decay report across all enrolled sessions.

        Returns dict with: records_monitored, records_expired, mean_decay_factor,
        oldest_session_days, privacy_budget_epsilon (advisory), warning_triggered.
        Never raises.
        """
        try:
            half_life = float(getattr(self._cfg, "bp001_half_life_days", BP_001_HALF_LIFE_DAYS))
            now_s = time.time()

            # Pull enrolled sessions from device_enrollments
            records_monitored = 0
            decay_factors     = []
            oldest_days       = 0.0

            try:
                with self._store._conn() as con:
                    rows = con.execute(
                        "SELECT created_at FROM device_enrollments "
                        "WHERE enrollment_status='enrolled' ORDER BY created_at ASC"
                    ).fetchall()
                for r in rows:
                    created_at = float(r[0]) if r[0] else now_s
                    age_days   = (now_s - created_at) / 86400.0
                    df         = tbd_decay_factor(age_days, half_life)
                    decay_factors.append(df)
                    oldest_days = max(oldest_days, age_days)
                    records_monitored += 1
            except Exception as exc:
                log.debug("BiometricPrivacyComplianceAgent: enrollment query error %s", exc)

            mean_df  = sum(decay_factors) / len(decay_factors) if decay_factors else 1.0
            expired  = sum(1 for df in decay_factors if df < BP_001_WARNING_THRESHOLD)
            # Privacy budget: advisory ε — increments by 1 per half-life elapsed for oldest record
            eps      = oldest_days / max(half_life, 1.0) if oldest_days > 0 else 0.0
            warning  = mean_df < BP_001_WARNING_THRESHOLD

            return {
                "records_monitored":    records_monitored,
                "records_expired":      expired,
                "mean_decay_factor":    round(mean_df, 6),
                "oldest_session_days":  round(oldest_days, 2),
                "privacy_budget_epsilon": round(eps, 4),
                "warning_triggered":    warning,
            }
        except Exception as exc:
            log.warning("BiometricPrivacyComplianceAgent: compute error %s", exc)
            return {
                "records_monitored":    0,
                "records_expired":      0,
                "mean_decay_factor":    1.0,
                "oldest_session_days":  0.0,
                "privacy_budget_epsilon": 0.0,
                "warning_triggered":    False,
            }

    async def _check_and_store(self) -> None:
        """Run one compliance check cycle, persist to store, publish bus event if warned."""
        try:
            report = self._compute_compliance_report()
            self._store.insert_privacy_compliance_log(
                records_monitored    = report["records_monitored"],
                records_expired      = report["records_expired"],
                mean_decay_factor    = report["mean_decay_factor"],
                oldest_session_days  = report["oldest_session_days"],
                privacy_budget_epsilon = report["privacy_budget_epsilon"],
                warning_triggered    = report["warning_triggered"],
            )
            if report["warning_triggered"] and self._bus is not None:
                try:
                    self._bus.publish_sync(
                        "biometric_decay_warning",
                        {
                            "mean_decay_factor": report["mean_decay_factor"],
                            "records_expired":   report["records_expired"],
                            "agent":             "BiometricPrivacyComplianceAgent",
                        },
                    )
                except Exception as bus_exc:
                    log.debug("BiometricPrivacyComplianceAgent: bus publish error %s", bus_exc)
        except Exception as exc:
            log.warning("BiometricPrivacyComplianceAgent: _check_and_store error %s", exc)

    async def run_poll_loop(self) -> None:
        """Long-running 6h poll loop.  Never raises."""
        log.info("BiometricPrivacyComplianceAgent (agent #22) starting poll loop")
        # Phase 235.x-STABILITY-9 stage 5 2026-05-17: startup-jitter.
        from .startup_grace import startup_grace
        await startup_grace(self._cfg, agent_name="BiometricPrivacyComplianceAgent")
        while True:
            try:
                enabled = bool(getattr(self._cfg, "biometric_privacy_enabled", True))
                if enabled:
                    await self._check_and_store()
            except Exception as exc:
                log.warning("BiometricPrivacyComplianceAgent: poll iteration error %s", exc)
            await asyncio.sleep(self.POLL_INTERVAL_S)
