"""
LivePresenceSignalingAgent — Phase 190, agent #34.

Translates the 33-agent fleet's semantic bus events into bidirectional
VAPI presence signals: controller LED color sequences + haptic pulses
(ps5_compat_aware) and a real-time ANSI terminal color stream (always).

Dual-path routing:
  Path A — Controller HID: LED + haptic pulses via dualshock_integration
            write path. Suppressed when ps5_compat_mode=True to prevent
            PS5 Bluetooth reconnect notifications.
  Path B — Terminal stream: ANSI-colored stdout lines. Always fires
            regardless of ps5_compat_mode. Provides real-time visual
            feedback during gameplay even when controller writes blocked.

Signal vocabulary (signal_type → LED RGB, haptic_duration_ms):
  HARD_CHEAT_DETECTED      → Red     (255, 0, 0)     + 3×200ms haptic
  CERTIFY_ADJUDICATION     → Blue    (0, 80, 255)    + 1×100ms haptic
  BIOMETRIC_ANOMALY        → Amber   (255, 140, 0)   + 1×80ms haptic
  PERSONA_BREAK_DETECTED   → Yellow  (255, 220, 0)   + 1×150ms haptic
  ENROLLMENT_MILESTONE     → Purple  (160, 0, 255)   + 1×200ms haptic
  MATURITY_ELEVATION       → White   (255, 255, 255) + 1×100ms haptic
  SEPARATION_BREAKTHROUGH  → Gold    (255, 200, 0)   + 2×150ms haptic
  CHAIN_MILESTONE          → Cyan    (0, 255, 200)   + no haptic
  SESSION_CONNECT          → Pulse   White→Blue→White, 3-pulse signature
  IDLE_RESET               → Dim-blue (0, 0, 40)     + no haptic

Signal sources (bus event_types subscribed):
  "persona_break"                   → PERSONA_BREAK_DETECTED
  "biometric_window_alert"          → BIOMETRIC_ANOMALY (adversarial)
  "reenrollment_authorized"         → ENROLLMENT_MILESTONE
  "enrollment_guidance_update"      → ENROLLMENT_MILESTONE (overall_ready only)
  "ratio_recovery_needed"           → BIOMETRIC_ANOMALY (trend alert)
  "maturity_elevation_available"    → MATURITY_ELEVATION
  "separation_ratio_breakthrough"   → SEPARATION_BREAKTHROUGH
  "pir_chain_broken"                → HARD_CHEAT_DETECTED (chain integrity attack)

Infrastructure-first default: live_presence_signaling_enabled=False.
Fail-open: exceptions → WARNING logged, signal skipped (never blocks bus loop).
"""

import asyncio
import logging
import queue
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 30       # how often to check chain milestone counter
_LED_RESET_DELAY_S = 2.0    # seconds before resetting LED to idle dim-blue

# LED color table — (R, G, B)
_LED = {
    "HARD_CHEAT_DETECTED":     (255,   0,   0),
    "CERTIFY_ADJUDICATION":    (  0,  80, 255),
    "BIOMETRIC_ANOMALY":       (255, 140,   0),
    "PERSONA_BREAK_DETECTED":  (255, 220,   0),
    "ENROLLMENT_MILESTONE":    (160,   0, 255),
    "MATURITY_ELEVATION":      (255, 255, 255),
    "SEPARATION_BREAKTHROUGH": (255, 200,   0),
    "CHAIN_MILESTONE":         (  0, 255, 200),
    "IDLE_RESET":              (  0,   0,  40),
}

# Haptic durations in ms (0 = no haptic)
_HAPTIC_MS = {
    "HARD_CHEAT_DETECTED":     200,    # 3 pulses (handled in _fire_controller)
    "CERTIFY_ADJUDICATION":    100,
    "BIOMETRIC_ANOMALY":        80,
    "PERSONA_BREAK_DETECTED":  150,
    "ENROLLMENT_MILESTONE":    200,
    "MATURITY_ELEVATION":      100,
    "SEPARATION_BREAKTHROUGH": 150,    # 2 pulses
    "CHAIN_MILESTONE":           0,
    "IDLE_RESET":                0,
}

# ANSI terminal labels
_ANSI = {
    "HARD_CHEAT_DETECTED":     "\033[91m[VAPI] HARD CHEAT DETECTED\033[0m",
    "CERTIFY_ADJUDICATION":    "\033[94m[VAPI] CERTIFY adjudication\033[0m",
    "BIOMETRIC_ANOMALY":       "\033[93m[VAPI] biometric anomaly signal\033[0m",
    "PERSONA_BREAK_DETECTED":  "\033[33m[VAPI] persona break detected — re-enrollment needed\033[0m",
    "ENROLLMENT_MILESTONE":    "\033[95m[VAPI] enrollment milestone\033[0m",
    "MATURITY_ELEVATION":      "\033[97m[VAPI] maturity elevation available\033[0m",
    "SEPARATION_BREAKTHROUGH": "\033[33m[VAPI] separation ratio breakthrough!\033[0m",
    "CHAIN_MILESTONE":         "\033[96m[VAPI] PoAC chain milestone\033[0m",
    "IDLE_RESET":              "\033[90m[VAPI] idle\033[0m",
}


class LivePresenceSignalingAgent:
    """Agent #34 — Phase 190 bidirectional VAPI presence signaling.

    Subscribes to 8 bus event channels and routes semantic verdicts to:
      - Controller LED + haptic (when ps5_compat_mode=False)
      - ANSI terminal stream (always)

    Priority queue drains at ≥500ms spacing to prevent LED flicker.
    Persists every signal to live_presence_signaling_log via store.
    """

    def __init__(self, store, cfg, bus=None, ds_integration=None):
        """
        Args:
            store: Store instance for persistence.
            cfg: Config instance.
            bus: AgentMessageBus instance for subscriptions.
            ds_integration: Optional DualShockIntegration instance for
                            direct LED/haptic calls. When None, controller
                            path is skipped (terminal stream still fires).
        """
        self._store = store
        self._cfg = cfg
        self._bus = bus
        self._ds = ds_integration
        self._signal_q: "queue.PriorityQueue[tuple]" = queue.PriorityQueue(maxsize=50)
        self._last_chain_record_count: int = 0

    # ------------------------------------------------------------------
    # Bus event → signal_type mapping
    # ------------------------------------------------------------------

    def _event_to_signal_type(self, event_type: str, payload: dict) -> "str | None":
        """Map a bus event to a signal_type string (or None to skip)."""
        if event_type == "persona_break":
            if payload.get("persona_break_detected", False):
                return "PERSONA_BREAK_DETECTED"
        elif event_type == "biometric_window_alert":
            verdict = payload.get("stationarity_verdict", "")
            if verdict == "ADVERSARIAL_WINDOW":
                return "BIOMETRIC_ANOMALY"
            return "BIOMETRIC_ANOMALY"   # any biometric alert is amber
        elif event_type == "reenrollment_authorized":
            return "ENROLLMENT_MILESTONE"
        elif event_type == "enrollment_guidance_update":
            if payload.get("overall_ready", False):
                return "ENROLLMENT_MILESTONE"
        elif event_type == "ratio_recovery_needed":
            return "BIOMETRIC_ANOMALY"
        elif event_type == "maturity_elevation_available":
            return "MATURITY_ELEVATION"
        elif event_type == "separation_ratio_breakthrough":
            return "SEPARATION_BREAKTHROUGH"
        elif event_type == "pir_chain_broken":
            return "HARD_CHEAT_DETECTED"
        return None

    # ------------------------------------------------------------------
    # Signal delivery
    # ------------------------------------------------------------------

    def _fire_terminal(self, signal_type: str) -> None:
        """Print ANSI terminal presence signal (always fires)."""
        try:
            label = _ANSI.get(signal_type, f"[VAPI] {signal_type}")
            ts_str = time.strftime("%H:%M:%S")
            print(f"{ts_str} {label}", flush=True)
        except Exception as exc:
            log.debug("LivePresenceSignalingAgent._fire_terminal: %s", exc)

    def _fire_controller(self, signal_type: str) -> bool:
        """Set controller LED and haptic for signal_type.

        Returns True if HID write was attempted (ps5_compat_mode=False and
        ds_integration is available), False if suppressed.
        """
        _ps5 = bool(getattr(self._cfg, "ps5_compat_mode", False))
        if _ps5 or self._ds is None:
            return False

        _haptic_en = bool(getattr(self._cfg, "live_presence_haptic_enabled", True))
        _rgb = _LED.get(signal_type, (0, 0, 40))
        _dur = _HAPTIC_MS.get(signal_type, 0)

        try:
            _reader = getattr(self._ds, "_reader", None)
            if _reader is None:
                return False

            if signal_type == "HARD_CHEAT_DETECTED":
                # 3 rapid Red pulses
                for _ in range(3):
                    _reader.set_led(*_rgb)
                    if _haptic_en and _dur > 0:
                        _reader.haptic(_dur, _dur)
                    time.sleep(0.25)
                    _reader.set_led(0, 0, 40)
                    time.sleep(0.1)
            elif signal_type == "SEPARATION_BREAKTHROUGH":
                # 2 Gold pulses
                for _ in range(2):
                    _reader.set_led(*_rgb)
                    if _haptic_en and _dur > 0:
                        _reader.haptic(_dur, _dur)
                    time.sleep(0.2)
                    _reader.set_led(0, 0, 40)
                    time.sleep(0.1)
            else:
                _reader.set_led(*_rgb)
                if _haptic_en and _dur > 0:
                    _reader.haptic(_dur, _dur)
                time.sleep(_LED_RESET_DELAY_S)
                _reader.set_led(0, 0, 40)  # idle reset

            return True
        except Exception as exc:
            log.debug("LivePresenceSignalingAgent._fire_controller: %s", exc)
            return False

    def _dispatch_signal(self, signal_source: str, signal_type: str) -> None:
        """Fire terminal stream, controller (if available), and persist to DB."""
        _ps5 = bool(getattr(self._cfg, "ps5_compat_mode", False))
        self._fire_terminal(signal_type)
        _ctrl = self._fire_controller(signal_type)
        _rgb = _LED.get(signal_type, (0, 0, 40))
        _dur = _HAPTIC_MS.get(signal_type, 0)
        _label = _ANSI.get(signal_type, signal_type)
        # Strip ANSI codes for DB storage
        import re as _re
        _plain = _re.sub(r"\033\[[0-9;]*m", "", _label)
        try:
            self._store.insert_presence_signal(
                signal_source=signal_source,
                signal_type=signal_type,
                led_rgb=_rgb,
                haptic_duration=_dur,
                terminal_output=_plain,
                controller_fired=_ctrl,
                ps5_compat_mode=_ps5,
            )
        except Exception as exc:
            log.warning("LivePresenceSignalingAgent.insert_presence_signal: %s", exc)

    # ------------------------------------------------------------------
    # Chain milestone check (polled)
    # ------------------------------------------------------------------

    def _check_chain_milestone(self) -> None:
        """Fire CHAIN_MILESTONE signal every N PoAC records (Phase 190)."""
        try:
            _interval = int(getattr(self._cfg, "live_presence_chain_milestone_interval", 100))
            if _interval <= 0:
                return
            _status = self._store.get_pir_chain_status(limit=1)
            # We use total_pirs as a proxy; for PoAC records use the record count
            # Actually use the poac_chain_audit_log count if available
            try:
                _count_row = self._store._conn().__enter__().execute(
                    "SELECT COUNT(*) FROM pitl_session_proofs"
                ).fetchone()
                _count = int(_count_row[0]) if _count_row else 0
                self._store._conn().__enter__().close()
            except Exception:
                _count = 0

            _prev = self._last_chain_record_count
            if _count > 0 and _count // _interval > _prev // _interval:
                self._dispatch_signal("chain_milestone", "CHAIN_MILESTONE")
            self._last_chain_record_count = _count
        except Exception as exc:
            log.debug("LivePresenceSignalingAgent._check_chain_milestone: %s", exc)

    # ------------------------------------------------------------------
    # Bus subscription loop
    # ------------------------------------------------------------------

    async def _subscribe_and_dispatch(self, event_type: str) -> None:
        """Subscribe to a single bus event type and dispatch signals."""
        if self._bus is None:
            return
        try:
            _q = await self._bus.subscribe(event_type)
        except Exception as exc:
            log.warning("LivePresenceSignalingAgent.subscribe(%s): %s", event_type, exc)
            return

        while True:
            try:
                _envelope = await asyncio.wait_for(_q.get(), timeout=120.0)
                _payload  = _envelope.get("payload", {})
                _sig_type = self._event_to_signal_type(event_type, _payload)
                if _sig_type:
                    self._dispatch_signal(event_type, _sig_type)
                    await asyncio.sleep(0.5)  # ≥500ms spacing prevents LED flicker
            except asyncio.TimeoutError:
                pass  # no event received — loop continues
            except Exception as exc:
                log.warning(
                    "LivePresenceSignalingAgent._subscribe_and_dispatch(%s): %s",
                    event_type, exc,
                )
                await asyncio.sleep(5.0)

    # ------------------------------------------------------------------
    # Poll loop (chain milestone + keepalive)
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Start bus subscriptions and poll for chain milestones."""
        log.info(
            "LivePresenceSignalingAgent started (agent #34, Phase 190; "
            "ps5_compat_mode=%s, haptic=%s, milestone_interval=%d)",
            getattr(self._cfg, "ps5_compat_mode", False),
            getattr(self._cfg, "live_presence_haptic_enabled", True),
            getattr(self._cfg, "live_presence_chain_milestone_interval", 100),
        )

        _BUS_CHANNELS = [
            "persona_break",
            "biometric_window_alert",
            "reenrollment_authorized",
            "enrollment_guidance_update",
            "ratio_recovery_needed",
            "maturity_elevation_available",
            "separation_ratio_breakthrough",
            "pir_chain_broken",
        ]

        # Start one coroutine per bus channel
        _tasks = []
        for _ch in _BUS_CHANNELS:
            _t = asyncio.ensure_future(self._subscribe_and_dispatch(_ch))
            _t.set_name(f"LivePresenceSignaling.{_ch}")
            _tasks.append(_t)

        # Poll loop for chain milestones
        while True:
            await asyncio.sleep(_POLL_INTERVAL_S)
            try:
                self._check_chain_milestone()
            except Exception as exc:
                log.warning("LivePresenceSignalingAgent poll: %s", exc)
