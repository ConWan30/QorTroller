"""
VSD Cycle 25 experiment: Synchronized Module Tether Pulses (SMTP)

Low-amplitude, player-rhythm-synchronized micro actuations on the adaptive
triggers (via L6/driver path) intended to keep the DualShock Edge's internal
wireless module state "attached to PS5" while the bridge uses high-rate USB
for capture (EXCLUSIVE_USB + grind_mode).

This is a prototype to test if the novel use case can work:
- Uses the project's own biometric surfaces (triggers) as active state anchor.
- Gated, tiny, duty-cycled, derived from live player data.
- Does not replace ps5_compat_mode (read-only preference); it is a controlled
  "tether exception" using sub-perceptible forces.

See:
- s-usb-bt-tether-pulse-generator-design.md
- s-usb-bt-dual-stability-module-notification.md
- dualshock_integration.py (integration points)
- capture_continuity.py (when to activate)
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class TetherConfig:
    enabled: bool = False
    amplitude_max: int = 12          # 0-255 LSB, keep << noticeable
    duration_ms: int = 35
    min_interval_s: float = 1.2
    sync_to_player_rhythm: bool = True


class TetherPulseGenerator:
    """
    Computes and emits micro tether pulses.

    Integration: caller feeds recent bio (e.g. right trigger force) and
    periodically calls maybe_send_tether(now) in the hot path or a low-rate tick.

    The send_action is injected (to allow using L6 driver or direct trigger
    writes under the existing to_thread + ps5_compat guards).
    """

    def __init__(
        self,
        cfg: TetherConfig,
        send_action: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self.cfg = cfg
        self._send = send_action  # (amp, dur_ms) -> None ; executed safely by caller
        self._last_pulse = 0.0
        self._recent: deque[tuple[float, float]] = deque(maxlen=8)  # (ts, force)

    def feed_biomarker(self, trigger_force: float, ts: float) -> None:
        """Called from bio extraction hot path with recent R2 or similar."""
        if self.cfg.sync_to_player_rhythm and trigger_force is not None:
            self._recent.append((ts, max(0.0, float(trigger_force))))

    def maybe_send_tether(self, now: float) -> bool:
        """Return True if a tether pulse was emitted this tick."""
        if not self.cfg.enabled or self._send is None:
            return False
        if now - self._last_pulse < self.cfg.min_interval_s:
            return False
        amp = self._compute_adaptive_amplitude()
        if amp <= 0:
            return False

        # The actual USB write (setForce) is performed by the injected action,
        # which must be wrapped in the caller's to_thread / bounded executor /
        # ps5_compat guards. We only decide amp + timing here.
        try:
            self._send(amp, self.cfg.duration_ms)
        except Exception:
            return False

        self._last_pulse = now
        return True

    def due(self, now: float) -> int:
        """Decision-only (hardened path): return the amp to emit now, or 0 if not due / no recent
        player force. Records the pulse time when it returns > 0 so the CALLER performs the actual
        HID write off the event loop (via asyncio.to_thread). Separating decision from emission is
        what lets the production wiring keep the USB write + restore off the ingestion loop."""
        if not self.cfg.enabled:
            return 0
        if now - self._last_pulse < self.cfg.min_interval_s:
            return 0
        amp = self._compute_adaptive_amplitude()
        if amp <= 0:
            return 0
        self._last_pulse = now
        return amp

    def _compute_adaptive_amplitude(self) -> int:
        if not self._recent:
            return 0
        avg = sum(f for _, f in self._recent) / len(self._recent)
        # Small fraction of recent player force; floor to 2 for "something"
        amp = max(2, min(self.cfg.amplitude_max, int(avg * 0.06)))
        return amp

    @property
    def last_pulse_ts(self) -> float:
        return self._last_pulse
