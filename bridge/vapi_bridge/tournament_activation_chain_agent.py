"""
TournamentActivationChainAgent — Phase 135 / Phase 178

Agent #16. Subscribes to `separation_ratio_breakthrough` bus event (fired by
SeparationRatioMonitorAgent when pooled_ratio >= 1.0 for 2 consecutive snapshots).

On breakthrough:
- Logs gate-open notification to tournament_activation_chain_log
- Publishes `tournament_gate_open_notification` bus event
- Does NOT auto-activate — auto_activate_on_breakthrough=False is PERMANENT

Phase 178 — Biometric Credential TTL Gate (WIF-029 W1 closure):
- check_biometric_credential_ttl() computes age_days from latest SeparationRatioRegistry.sol
  commitment and compares against cfg.biometric_credential_ttl_days (default 90).
- ttl_expired=True → BLOCKS tournament authorization + sets recalibration_required=True.
- Result logged to biometric_renewal_log for audit trail.
- Never part of the one-shot breakthrough handler — runs on operator preflight queries.

Protocol invariant: VAPI never auto-activates on a ratio breakthrough.
Tournament activation always requires explicit operator action via
POST /agent/commit-activation (Phase 97/127 gate enforced separately).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_message_bus import AgentMessageBus
    from .config import Config
    from .store import Store

log = logging.getLogger("tournament_activation_chain_agent")

# PERMANENT INVARIANT: never change this constant
_AUTO_ACTIVATE_ON_BREAKTHROUGH = False


class TournamentActivationChainAgent:
    """One-shot notification agent that fires when separation ratio crosses 1.0.

    INVARIANT: auto_activate_on_breakthrough is PERMANENTLY False.
    This agent logs a gate-open notification and publishes a bus event only.
    Actual tournament activation requires operator action (Phase 97/127 gate).
    """

    def __init__(self, cfg: "Config", store: "Store", bus: "AgentMessageBus | None" = None):
        self._cfg = cfg
        self._store = store
        self._bus = bus
        self._fired = False  # one-shot guard

    async def run_event_consumer(self) -> None:
        """Subscribe to separation_ratio_breakthrough bus event and handle it."""
        if self._bus is None:
            return
        try:
            await self._bus.subscribe(
                "separation_ratio_breakthrough",
                self._on_breakthrough,
            )
            # Keep alive
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.debug("TournamentActivationChainAgent run_event_consumer: %s", exc)

    async def _on_breakthrough(self, payload: dict) -> None:
        """Handle separation_ratio_breakthrough event. One-shot guard prevents re-fire."""
        if self._fired:
            log.debug("TournamentActivationChainAgent: one-shot guard active, skipping re-fire")
            return
        self._fired = True
        try:
            ratio = float(payload.get("ratio", 0.0))
            n_players = int(payload.get("n_players", 0))
            log.info(
                "TournamentActivationChainAgent: separation ratio breakthrough received "
                "(ratio=%.3f, n_players=%d) — gate-open notification fired; "
                "auto_activate_on_breakthrough=False (PERMANENT INVARIANT)",
                ratio, n_players,
            )
            # Log to store
            self._store.insert_tournament_activation_chain(
                event_type="breakthrough_received",
                separation_ratio=ratio,
                n_players=n_players,
                gate_open_notified=True,
                notes=(
                    "Separation ratio crossed 1.0 (2 consecutive snapshots). "
                    "Gate-open notification fired. Operator action required to activate."
                ),
            )
            # Publish notification bus event
            if self._bus is not None:
                try:
                    await self._bus.publish(
                        "tournament_gate_open_notification",
                        {
                            "separation_ratio": ratio,
                            "n_players": n_players,
                            "auto_activate": _AUTO_ACTIVATE_ON_BREAKTHROUGH,
                            "operator_action_required": True,
                            "timestamp": time.time(),
                        },
                    )
                except Exception as exc:
                    log.debug("TournamentActivationChainAgent: bus publish failed: %s", exc)
        except Exception as exc:
            log.debug("TournamentActivationChainAgent._on_breakthrough error: %s", exc)

    def check_biometric_credential_ttl(self) -> "dict":
        """Check whether the latest on-chain separation ratio commitment has expired (Phase 178).

        Computes age_days = (now - latest_commit_ts_ns / 1e9) / 86400 from the most recent
        SeparationRatioRegistry.sol commitment stored in separation_ratio_registry_log.
        When age_days > cfg.biometric_credential_ttl_days:
          - ttl_expired=True
          - recalibration_required=True
          - result logged to biometric_renewal_log for audit trail

        Returns dict with 8 keys matching GET /agent/biometric-credential-age response shape.
        Never raises — on any error returns ttl_expired=False (fail-open for backward compat).
        """
        try:
            ttl_days = float(self._cfg.biometric_credential_ttl_days)
            status = self._store.get_biometric_credential_age_status(ttl_days=ttl_days)
            age_days = float(status.get("age_days", 0.0))
            commit_hash = str(status.get("commit_hash", ""))
            ttl_expired = age_days > ttl_days and bool(commit_hash)
            recalibration_required = ttl_expired
            # Log every TTL check to biometric_renewal_log for audit trail
            self._store.insert_biometric_renewal_log(
                commit_hash=commit_hash,
                age_days=age_days,
                ttl_days=ttl_days,
                ttl_expired=ttl_expired,
                recalibration_required=recalibration_required,
            )
            if ttl_expired:
                log.warning(
                    "TournamentActivationChainAgent: biometric credential EXPIRED "
                    "(age_days=%.1f > ttl_days=%.1f, commit=%s) — "
                    "tournament authorization BLOCKED; recalibration required",
                    age_days, ttl_days, commit_hash[:16] if commit_hash else "(none)",
                )
            return {
                "ttl_enabled":            True,
                "commit_hash":            commit_hash,
                "commit_ts":              float(status.get("commit_ts", 0.0)),
                "age_days":               round(age_days, 4),
                "ttl_days":               ttl_days,
                "ttl_expired":            ttl_expired,
                "recalibration_required": recalibration_required,
                "timestamp":              time.time(),
            }
        except Exception as exc:
            log.debug("TournamentActivationChainAgent.check_biometric_credential_ttl error: %s", exc)
            return {
                "ttl_enabled":            True,
                "commit_hash":            "",
                "commit_ts":              0.0,
                "age_days":               0.0,
                "ttl_days":               90.0,
                "ttl_expired":            False,
                "recalibration_required": False,
                "timestamp":              time.time(),
            }
