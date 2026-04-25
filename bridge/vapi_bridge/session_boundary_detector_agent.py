"""Phase 235-AUTO-TRIGGER — SessionBoundaryDetectorAgent (agent #38).

Detects natural session boundaries from gameplay records and publishes
ruling_request events to the bus, replacing manual /agent/adjudicate
POSTs during the 100-session grind.

Heuristic detection (no LLM, no ML).  All conditions must hold:

  1. cfg.auto_trigger_enabled == True              (operator opt-in)
  2. chain_length < grind_target                   (otherwise self-stop)
  3. PCC NOMINAL + EXCLUSIVE_USB / UNKNOWN         (Phase 234.7 cross-layer)
  4. Recent activity: in the most-recent activity_window records,
     >= 20% have trigger_active == 1               (Phase 235-GAD signal)
  5. Game-end quiescence: the trailing quiescence_window records ALL
     have trigger_active == 0                       (player returned to
                                                     menu, not just
                                                     between plays)
  6. Throttle: now - last_fire_at >= min_interval_s (W1 mitigation)

Steps 4 + 5 together discriminate "just finished a play" (short
quiescence between snaps) from "session over / back in menu" (long
quiescence after sustained play).  NCAA CFB 26 has natural ~30s
between plays — the default 60-record (~60s) quiescence window
filters those out.

This agent is operational infrastructure built on top of the four
headline novelty layers (PCC / GIC / GAD / CAPS) — not a fifth
novelty claim.  Its value is integration: the trigger fires only
when ALL three independent attestation layers agree on session-end.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

POLL_INTERVAL_S       = 60        # check every minute
ACTIVITY_FRACTION_MIN = 0.20      # >=20% of activity_window must be trigger_active=1


class SessionBoundaryDetectorAgent:
    """Polls every 60s, fires ruling_request events on detected
    session boundaries.  All Store calls reused from existing API.

    Args:
        cfg:    Config (reads auto_trigger_enabled, auto_trigger_min_
                interval_s, auto_trigger_quiescence_window, auto_trigger
                _activity_window, grind_session_id, grind_target).
        store:  Store instance (reads recent records + capture_health
                + grind_chain status; writes agent_events).
        bus:    Optional AgentMessageBus (currently unused; reserved
                for future bus-driven coordination).
    """

    POLL_INTERVAL_S = POLL_INTERVAL_S

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg            = cfg
        self._store          = store
        self._bus            = bus
        self._last_fire_at   = 0.0
        self._fires_this_run = 0
        self._stopped        = False

    # ------------------------------------------------------------------
    # Decision logic — single tick, returns ("FIRE"|"SKIP", reason).
    # Pulled out so unit tests can call it directly without a poll loop.
    # ------------------------------------------------------------------

    def evaluate(self, now_monotonic: float | None = None) -> tuple[str, str]:
        cfg = self._cfg
        if not bool(getattr(cfg, "auto_trigger_enabled", False)):
            return ("SKIP", "auto_trigger_enabled=False")

        # Self-stop check: chain has reached target
        try:
            grind_sid = getattr(cfg, "grind_session_id", "")
            target    = int(getattr(cfg, "grind_target", 100))
            chain_st  = self._store.get_grind_chain_status(grind_sid, cfg)
            chain_len = int(chain_st.get("chain_length", 0))
        except Exception as exc:
            return ("SKIP", f"grind_chain_status query failed: {exc}")

        if chain_len >= target:
            self._stopped = True
            return ("SKIP", f"GIC_{target} reached (chain_length={chain_len}); self-stop")

        # PCC eligibility — Phase 234.7 cross-layer attestation
        try:
            pcc = self._store.get_capture_health_status() or {}
        except Exception as exc:
            return ("SKIP", f"capture_health query failed: {exc}")
        pcc_state = pcc.get("capture_state")
        pcc_host  = pcc.get("host_state")
        if pcc_state != "NOMINAL":
            return ("SKIP", f"PCC capture_state={pcc_state} (need NOMINAL)")
        if pcc_host not in ("EXCLUSIVE_USB", "UNKNOWN"):
            return ("SKIP", f"PCC host_state={pcc_host} (need EXCLUSIVE_USB/UNKNOWN)")

        # Throttle — W1 rate-limit mitigation
        if now_monotonic is None:
            now_monotonic = time.monotonic()
        elapsed = now_monotonic - self._last_fire_at if self._last_fire_at else 9999.0
        min_iv  = float(getattr(cfg, "auto_trigger_min_interval_s", 300))
        if elapsed < min_iv:
            return ("SKIP", f"<{min_iv:.0f}s since last fire ({elapsed:.0f}s elapsed)")

        # Pull recent records from the active device.
        # We need activity_window + quiescence_window records total — the
        # quiescence_window is the trailing tail, activity_window is the
        # preceding head.
        q_window = int(getattr(cfg, "auto_trigger_quiescence_window", 60))
        a_window = int(getattr(cfg, "auto_trigger_activity_window", 120))
        total    = q_window + a_window
        try:
            recent = self._store.get_recent_records(limit=total)
        except Exception as exc:
            return ("SKIP", f"get_recent_records failed: {exc}")
        if len(recent) < total:
            return ("SKIP", f"only {len(recent)}/{total} records — bridge starting up")

        # `recent` is ordered most-recent-first per Store convention.
        # Tail (quiescence) = first q_window entries; head (activity) = the rest.
        tail = recent[:q_window]
        head = recent[q_window:q_window + a_window]

        # Quiescence: every trailing record must be trigger_active=0
        tail_active = [int(r.get("trigger_active", 0) or 0) for r in tail]
        if any(v == 1 for v in tail_active):
            return ("SKIP",
                    f"quiescence not yet — {sum(tail_active)} trigger_active "
                    f"records in trailing {q_window}")

        # Activity: head must contain enough trigger_active records to
        # confirm a gameplay session actually happened
        head_active = [int(r.get("trigger_active", 0) or 0) for r in head]
        head_frac   = sum(head_active) / max(1, len(head_active))
        if head_frac < ACTIVITY_FRACTION_MIN:
            return ("SKIP",
                    f"insufficient activity in head window — "
                    f"trigger_active_fraction={head_frac:.2f} "
                    f"< {ACTIVITY_FRACTION_MIN}")

        return ("FIRE", f"session-end detected; head_frac={head_frac:.2f}, "
                       f"quiescence={q_window} records all idle")

    # ------------------------------------------------------------------
    # Trigger fire — wraps the existing write_agent_event path so the
    # ruling_request enters the same queue POST /agent/adjudicate uses.
    # ------------------------------------------------------------------

    def fire_trigger(self, device_id: str, now_monotonic: float | None = None) -> int | None:
        if not device_id:
            log.warning("SessionBoundaryDetectorAgent: no device_id — skipping fire")
            return None
        try:
            event_id = self._store.write_agent_event(
                event_type="ruling_request",
                payload=json.dumps({
                    "device_id": device_id,
                    "attestation_hash": "",
                }),
                source="session_boundary_detector_agent",
                target="session_adjudicator",
                device_id=device_id,
            )
        except Exception as exc:
            log.warning("SessionBoundaryDetectorAgent: write_agent_event failed: %s", exc)
            return None

        if now_monotonic is None:
            now_monotonic = time.monotonic()
        self._last_fire_at    = now_monotonic
        self._fires_this_run += 1
        log.info(
            "SessionBoundaryDetectorAgent: → ruling_request fired "
            "device=%s event_id=%s fires_this_run=%d",
            device_id[:16] if device_id else "?",
            event_id,
            self._fires_this_run,
        )
        return event_id

    # ------------------------------------------------------------------
    # Device discovery — pull the device_id from the most recent record.
    # No HTTP roundtrip needed; the store has it locally.
    # ------------------------------------------------------------------

    def _current_device_id(self) -> str | None:
        try:
            recent = self._store.get_recent_records(limit=1)
        except Exception:
            return None
        if not recent:
            return None
        return recent[0].get("device_id") or None

    # ------------------------------------------------------------------
    # Telemetry — read-only snapshot for /operator/agent/auto-trigger-status
    # ------------------------------------------------------------------

    def get_telemetry(self) -> dict:
        """Return a JSON-serialisable snapshot of agent state for the operator
        endpoint.  Phase 235-DASH-UPGRADE: surfaces last-fire age and
        next-eligible-in seconds so the gamer dashboard can show a live
        status chip during the 5-min throttle windows where chain_length
        appears static.

        Monotonic timestamps are not portable across the API boundary, so
        we convert to relative seconds (last_fire_age_s) on the way out.
        """
        now = time.monotonic()
        last_age = (now - self._last_fire_at) if self._last_fire_at else None
        min_iv   = float(getattr(self._cfg, "auto_trigger_min_interval_s", 300))
        next_in  = max(0.0, min_iv - last_age) if last_age is not None else 0.0
        return {
            "auto_trigger_enabled": bool(getattr(self._cfg, "auto_trigger_enabled", False)),
            "fires_this_run":       int(self._fires_this_run),
            "last_fire_age_s":      round(last_age, 1) if last_age is not None else None,
            "next_eligible_in_s":   round(next_in, 1),
            "min_interval_s":       int(min_iv),
            "quiescence_window":    int(getattr(self._cfg, "auto_trigger_quiescence_window", 60)),
            "activity_window":      int(getattr(self._cfg, "auto_trigger_activity_window", 120)),
            "stopped":              bool(self._stopped),
        }

    # ------------------------------------------------------------------
    # Long-running poll loop — main.py awaits this via _run_*_with_restart
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        log.info(
            "Phase 235-AUTO-TRIGGER: SessionBoundaryDetectorAgent started "
            "(agent #38; poll=%ds; min_interval=%ds; quiescence_window=%d; "
            "activity_window=%d)",
            self.POLL_INTERVAL_S,
            int(getattr(self._cfg, "auto_trigger_min_interval_s", 300)),
            int(getattr(self._cfg, "auto_trigger_quiescence_window", 60)),
            int(getattr(self._cfg, "auto_trigger_activity_window", 120)),
        )
        while True:
            if self._stopped:
                log.info(
                    "SessionBoundaryDetectorAgent: stopped — "
                    "GIC_target reached this run (fires=%d)",
                    self._fires_this_run,
                )
                # Sleep indefinitely without firing further; bridge can
                # be restarted to resume if grind_target is raised.
                await asyncio.sleep(3600)
                continue

            try:
                verdict, reason = self.evaluate()
                if verdict == "FIRE":
                    device_id = self._current_device_id()
                    if device_id:
                        self.fire_trigger(device_id)
                    else:
                        log.debug("SessionBoundaryDetectorAgent: FIRE verdict but "
                                  "no device_id yet")
                else:
                    log.debug("SessionBoundaryDetectorAgent: skip — %s", reason)
            except Exception as exc:
                log.warning("SessionBoundaryDetectorAgent: cycle error: %s", exc)

            await asyncio.sleep(self.POLL_INTERVAL_S)
