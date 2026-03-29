"""
TournamentActivationChainAgent — Phase 135

Agent #16. Subscribes to `separation_ratio_breakthrough` bus event (fired by
SeparationRatioMonitorAgent when pooled_ratio >= 1.0 for 2 consecutive snapshots).

On breakthrough:
- Logs gate-open notification to tournament_activation_chain_log
- Publishes `tournament_gate_open_notification` bus event
- Does NOT auto-activate — auto_activate_on_breakthrough=False is PERMANENT

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
