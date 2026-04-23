"""Phase 234.7 — Physical Capture Continuity (PCC).

Monitors HID poll rate, infers controller host arbitration state, and enforces
fail-closed session counting during grind-mode calibration.

CaptureHealthMonitor is a lightweight, thread-safe observer called from
DualShockIntegration._session_loop() once per collection interval (~1 second).
It does NOT generate PoAC records — it observes the rate at which the HID loop
produces frames and infers capture health from that signal.

States
------
NOMINAL      ≥ pcc_nominal_hz (default 950 Hz) — clean capture
DEGRADED     pcc_degraded_hz ≤ rate < pcc_nominal_hz — partial capture
DISCONNECTED < pcc_degraded_hz or explicit disconnect signal

Host states (inferred from poll rate variance, not HID descriptor flags)
--------------------------------------------------------------------------
EXCLUSIVE_USB  stable ~1000 Hz, low variance — controller owned by this host
EXCLUSIVE_BT   stable ~250 Hz — controller on BT (not expected in bridge mode)
CONTESTED      high variance or long-gap events — host arbitration in progress
UNKNOWN        insufficient data to classify

Layer 5: Grind-mode readiness gate
------------------------------------
grind_ready = (capture_state == NOMINAL) AND
              (host_state in {EXCLUSIVE_USB, UNKNOWN}) AND
              (sustained at NOMINAL for >= pcc_stable_window_s seconds)

When grind_mode=True and grind_ready=False, session_counting_paused=True is
exposed in the API — a soft block that the user acts on. Deep enforcement
(blocking PoAC generation) requires dualshock_integration cooperation already
wired at the update_sample() call site.
"""

import math
import threading
import time
from collections import deque
from enum import Enum


class CaptureState(str, Enum):
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"


class HostState(str, Enum):
    EXCLUSIVE_USB = "EXCLUSIVE_USB"
    EXCLUSIVE_BT = "EXCLUSIVE_BT"
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"


class CaptureHealthMonitor:
    """Thread-safe HID capture health observer (Phase 234.7).

    Call update_sample(n_frames, window_s) from _session_loop() after each
    frame collection interval.  Call signal_disconnect(reason) on TimeoutError.

    Thresholds (configurable via cfg):
      pcc_nominal_hz        ≥ 950 Hz → NOMINAL
      pcc_degraded_hz       ≥ 100 Hz → DEGRADED
      pcc_stable_window_s   30 s sustained NOMINAL → grind_ready

    Host state inference uses coefficient of variation of per-sample rates:
      CV < 0.20 AND rate ≥ 900 Hz  → EXCLUSIVE_USB
      CV ≥ 0.40 OR long-gap count  → CONTESTED
      rate 200–350 Hz, low CV      → EXCLUSIVE_BT
      otherwise                    → UNKNOWN
    """

    _SAMPLE_MAXLEN = 60      # rolling window: 60 samples (60 s at 1 Hz)
    _CONTESTED_CV = 0.40     # inter-sample rate CV above this = CONTESTED
    _CONTESTED_MIN_RATE_HZ = 300  # below this, CONTESTED rather than EXCLUSIVE_BT if high CV
    _BT_RATE_LOW = 200
    _BT_RATE_HIGH = 350

    def __init__(self, cfg=None) -> None:
        self._nominal_hz: int = getattr(cfg, "pcc_nominal_hz", 950) if cfg else 950
        self._degraded_hz: int = getattr(cfg, "pcc_degraded_hz", 100) if cfg else 100
        self._stable_s: int = getattr(cfg, "pcc_stable_window_s", 30) if cfg else 30

        self._lock = threading.Lock()
        # Each sample: (rate_hz, monotonic_ts)
        self._samples: deque[tuple[float, float]] = deque(maxlen=self._SAMPLE_MAXLEN)
        self._poll_rate_hz: float = 0.0
        self._capture_state: CaptureState = CaptureState.DISCONNECTED
        self._host_state: HostState = HostState.UNKNOWN
        self._state_entered: float = time.monotonic()   # monotonic ts when current state began
        self._nominal_since: float | None = None        # monotonic ts when NOMINAL streak started
        self._last_sample_ts: float = 0.0
        self._disconnect_reason: str = ""
        self._state_transitions: list[dict] = []        # recent transitions for Layer 3

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_sample(self, n_frames: int, window_s: float) -> str | None:
        """Record one collection interval result.  Returns new state if transition occurred.

        Args:
            n_frames:  Number of HID frames collected in this interval.
            window_s:  Duration of the collection interval in seconds (typically 1.0).

        Returns:
            New CaptureState.value if a state transition just occurred, else None.
        """
        now = time.monotonic()
        rate = (n_frames / window_s) if window_s > 0 else 0.0

        with self._lock:
            self._samples.append((rate, now))
            self._last_sample_ts = now
            self._disconnect_reason = ""
            return self._recompute(now)

    def signal_disconnect(self, reason: str = "timeout") -> None:
        """Explicitly mark DISCONNECTED (call on HID timeout / poll error)."""
        now = time.monotonic()
        with self._lock:
            self._samples.append((0.0, now))
            self._last_sample_ts = now
            self._disconnect_reason = reason
            self._recompute(now)

    def get_status(self) -> dict:
        """Return a snapshot dict suitable for JSON serialisation."""
        now = time.monotonic()
        with self._lock:
            sustained = round(now - self._state_entered, 1)
            grind_ready = self._is_grind_ready_locked(now)
            return {
                "capture_state":       self._capture_state.value,
                "host_state":          self._host_state.value,
                "poll_rate_hz":        round(self._poll_rate_hz, 1),
                "sustained_duration_s": sustained,
                "grind_ready":         grind_ready,
                "disconnect_reason":   self._disconnect_reason,
                "sample_count":        len(self._samples),
            }

    def is_grind_ready(self) -> bool:
        now = time.monotonic()
        with self._lock:
            return self._is_grind_ready_locked(now)

    def pop_transitions(self) -> list[dict]:
        """Return and clear the buffered state transition records (for store logging)."""
        with self._lock:
            out = list(self._state_transitions)
            self._state_transitions.clear()
            return out

    # ------------------------------------------------------------------
    # Internal helpers (called under self._lock)
    # ------------------------------------------------------------------

    def _recompute(self, now: float) -> str | None:
        """Recompute state from current sample buffer.  Returns new state name on transition."""
        samples = list(self._samples)

        # Explicit disconnect overrides rate averaging immediately
        if self._disconnect_reason:
            effective_rate = 0.0
        # Staleness: if no sample in 3× the expected interval, treat as disconnected
        elif samples and (now - samples[-1][1]) > 3.0:
            effective_rate = 0.0
        elif samples:
            # Weighted recent average: use the last 10 samples for responsiveness
            recent = samples[-10:]
            effective_rate = sum(r for r, _ in recent) / len(recent)
        else:
            effective_rate = 0.0

        self._poll_rate_hz = effective_rate

        # Classify capture state
        if effective_rate >= self._nominal_hz:
            new_state = CaptureState.NOMINAL
        elif effective_rate >= self._degraded_hz:
            new_state = CaptureState.DEGRADED
        else:
            new_state = CaptureState.DISCONNECTED

        # Classify host state
        new_host = self._infer_host_state(samples, effective_rate)
        self._host_state = new_host

        # State transition bookkeeping
        if new_state != self._capture_state:
            old_state = self._capture_state
            self._capture_state = new_state
            self._state_entered = now
            if new_state == CaptureState.NOMINAL:
                self._nominal_since = now
            else:
                self._nominal_since = None
            # Buffer the transition for store logging
            self._state_transitions.append({
                "old_state":       old_state.value,
                "new_state":       new_state.value,
                "host_state":      new_host.value,
                "poll_rate_hz":    round(effective_rate, 1),
                "reason":          self._disconnect_reason or "rate_change",
                "ts":              time.time(),
            })
            return new_state.value

        return None

    def _infer_host_state(self, samples: list, rate: float) -> HostState:
        """Infer host arbitration state from per-sample rate variance."""
        rates = [r for r, _ in samples if r > 0]
        if len(rates) < 5:
            return HostState.UNKNOWN
        if rate < self._degraded_hz:
            return HostState.UNKNOWN

        mean = sum(rates) / len(rates)
        if mean < 1e-6:
            return HostState.UNKNOWN

        std = math.sqrt(sum((r - mean) ** 2 for r in rates) / len(rates))
        cv = std / mean

        # Stable ~1000 Hz, low variance
        if mean >= 900 and cv < 0.20:
            return HostState.EXCLUSIVE_USB
        # Contested: high variance or sudden dips amidst high-rate polling
        if cv >= self._CONTESTED_CV and mean >= self._CONTESTED_MIN_RATE_HZ:
            return HostState.CONTESTED
        # ~250 Hz stable = BT (not expected when USB-only)
        if self._BT_RATE_LOW <= mean <= self._BT_RATE_HIGH and cv < 0.20:
            return HostState.EXCLUSIVE_BT
        # High CV at any rate
        if cv >= self._CONTESTED_CV:
            return HostState.CONTESTED
        # Moderate rate, moderate variance
        if mean >= 900:
            return HostState.EXCLUSIVE_USB
        return HostState.UNKNOWN

    def _is_grind_ready_locked(self, now: float) -> bool:
        if self._capture_state != CaptureState.NOMINAL:
            return False
        if self._host_state not in (HostState.EXCLUSIVE_USB, HostState.UNKNOWN):
            return False
        if self._nominal_since is None:
            return False
        return (now - self._nominal_since) >= self._stable_s
