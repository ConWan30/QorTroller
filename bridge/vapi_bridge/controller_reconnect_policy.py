"""Controller hot-plug reconnection policy (pure, testable).

Decision core for the DualShock transport's autonomous USB re-acquire: when the session loop sees N
consecutive poll failures the controller is likely gone, so it re-opens the reader on a capped backoff
schedule instead of requiring a full bridge restart. This module holds ONLY the decision math (no HID,
no asyncio, no state) so it is deterministic and unit-testable; the loop owns the failure counters and
performs the actual (blocking) reader re-open off the event loop.

Mirrors the watchdog's restart-ceiling discipline: bounded cadence, never hammer the USB stack, retry
indefinitely at the cap (a replug can happen at any time, so giving up would defeat the purpose).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    # Consecutive poll failures (timeout / error / empty-while-expecting) before the FIRST re-open
    # attempt. Small enough to recover quickly (~a few seconds at the 1s session interval), large
    # enough to ride out a transient USB hiccup without churning the handle.
    reconnect_after_failures: int = 5
    # Seconds to wait BETWEEN reconnect attempts; the last entry is the steady-state cap.
    backoff_schedule: tuple[float, ...] = field(default=(5.0, 10.0, 30.0, 60.0))

    def should_attempt(self, consecutive_failures: int) -> bool:
        """True once the failure run is long enough that the device is presumed gone (not a hiccup)."""
        return consecutive_failures >= self.reconnect_after_failures

    def backoff_for_attempt(self, attempt: int) -> float:
        """Seconds to sleep after reconnect ATTEMPT number `attempt` (1-based) fails.

        attempt 1 -> schedule[0], 2 -> [1], ... clamped to the last (cap). attempt<=0 -> first entry.
        """
        if not self.backoff_schedule:
            return 5.0
        idx = max(0, attempt - 1)
        idx = min(idx, len(self.backoff_schedule) - 1)
        return self.backoff_schedule[idx]
