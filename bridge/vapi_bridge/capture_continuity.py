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

        # Phase 235-PCC-SPC: Statistical Process Control + 3-signal haptic-tolerance
        self._spc_enabled: bool = bool(getattr(cfg, "pcc_spc_enabled", False)) if cfg else False
        self._upper_hz: int = int(getattr(cfg, "pcc_upper_hz", 3500)) if cfg else 3500
        self._haptic_tolerance_window_s: float = (
            float(getattr(cfg, "pcc_haptic_tolerance_window_ms", 500)) / 1000.0
            if cfg else 0.5
        )
        self._haptic_min_dip_hz: int = int(getattr(cfg, "pcc_haptic_min_dip_hz", 200)) if cfg else 200
        self._spc_window_n: int = int(getattr(cfg, "pcc_spc_window_n", 30)) if cfg else 30
        self._spc_in_control_pct: float = float(getattr(cfg, "pcc_spc_in_control_pct", 0.85)) if cfg else 0.85
        self._haptic_tremor_min_hz: float = float(getattr(cfg, "pcc_haptic_tremor_min_hz", 4.0)) if cfg else 4.0
        self._haptic_tremor_max_hz: float = float(getattr(cfg, "pcc_haptic_tremor_max_hz", 60.0)) if cfg else 60.0
        self._haptic_accel_threshold: float = float(getattr(cfg, "pcc_haptic_accel_threshold", 0.0003)) if cfg else 0.0003

        self._lock = threading.Lock()
        # Each sample: (rate_hz, monotonic_ts, trigger_active, accel_var, tremor_peak_hz)
        # Phase 235-PCC-SPC: extended from 2-tuple to 5-tuple to carry game-context.
        # Backward-compat: existing unpack sites use `for r, _ts, *_ in samples`.
        self._samples: deque[tuple[float, float, bool, float, float]] = deque(maxlen=self._SAMPLE_MAXLEN)
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

    def update_sample(
        self,
        n_frames: int,
        window_s: float,
        *,
        trigger_active: bool = False,
        accel_var: float = 0.0,
        tremor_peak_hz: float = 0.0,
    ) -> str | None:
        """Record one collection interval result.  Returns new state if transition occurred.

        Args:
            n_frames:       Number of HID frames collected in this interval.
            window_s:       Duration of the collection interval in seconds (typically 1.0).
            trigger_active: Phase 235-PCC-SPC kw-only — whether L2/R2 trigger fired
                            in the most recent record.  Used by SPC haptic-tolerance
                            binding (Signal 1).  Default False = no game-context.
            accel_var:      Phase 235-PCC-SPC kw-only — micro_tremor_accel_variance
                            from the most recent record.  Used by SPC haptic-tolerance
                            binding (Signal 2).  Default 0.0 = no haptic event.
            tremor_peak_hz: Phase 235-PCC-SPC kw-only — tremor_peak_hz from the most
                            recent record.  Used by INV-PCC-005 frequency-band gate
                            (must fall within [haptic_tremor_min_hz, haptic_tremor_max_hz]
                            for tolerance to fire).  Default 0.0 = no spectral signature.

        Returns:
            New CaptureState.value if a state transition just occurred, else None.

        Phase 235-PCC-SPC INV-PCC-002: kw-only-with-default signature preserves backward
        compatibility — pre-Phase-235-PCC-SPC callers using update_sample(n_frames, window_s)
        continue to work; defaults yield byte-identical behavior to Phase 234.7.
        """
        now = time.monotonic()
        rate = (n_frames / window_s) if window_s > 0 else 0.0

        with self._lock:
            self._samples.append((rate, now, bool(trigger_active), float(accel_var), float(tremor_peak_hz)))
            self._last_sample_ts = now
            self._disconnect_reason = ""
            return self._recompute(now)

    def signal_disconnect(self, reason: str = "timeout") -> None:
        """Explicitly mark DISCONNECTED (call on HID timeout / poll error).

        Phase 235-PCC-SPC INV-PCC-003: signal_disconnect ALWAYS overrides SPC
        classification — explicit disconnect cannot be masked by in-control
        capability or haptic-tolerance binding.  Fail-closed precedence preserved.
        """
        now = time.monotonic()
        with self._lock:
            # Phase 235-PCC-SPC: append zero-rate sample with no game-context (forced disconnect).
            self._samples.append((0.0, now, False, 0.0, 0.0))
            self._last_sample_ts = now
            self._disconnect_reason = reason
            self._recompute(now)

    def get_status(self) -> dict:
        """Return a snapshot dict suitable for JSON serialisation."""
        now = time.monotonic()
        with self._lock:
            # INV-PCC-001: recompute before reading cached state so a HID stall
            # that occurred since the last update_sample() call is reflected here.
            self._recompute(now)
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
            # INV-PCC-001: recompute before reading cached state.
            self._recompute(now)
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
        # INV-PCC-003: this precedence is preserved regardless of _spc_enabled.
        if self._disconnect_reason:
            effective_rate = 0.0
        # Staleness: if no sample in 3× the expected interval, treat as disconnected
        elif samples and (now - samples[-1][1]) > 3.0:
            effective_rate = 0.0
        elif samples:
            # Weighted recent average: use the last 10 samples for responsiveness.
            # Phase 235-PCC-SPC: 5-tuple unpacking via `*_` to ignore game-context fields.
            recent = samples[-10:]
            effective_rate = sum(r for r, _ts, *_ in recent) / len(recent)
        else:
            effective_rate = 0.0

        self._poll_rate_hz = effective_rate

        # Phase 235-PCC-SPC: branch classifier on _spc_enabled
        if self._spc_enabled and not self._disconnect_reason:
            new_state = self._classify_capture_state_spc(samples, effective_rate, now)
        else:
            # Classic classification (Phase 234.7) — byte-identical when _spc_enabled=False
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

    def _classify_capture_state_spc(self, samples: list, effective_rate: float, now: float) -> CaptureState:
        """Phase 235-PCC-SPC alternative classifier.

        Decision tree (top-down; first match wins):
          1. Haptic-tolerance fires (3-signal binding + frequency-band gate per
             INV-PCC-004 + INV-PCC-005)  → NOMINAL (suppress sub-second dip)
          2. SPC capability: ≥ in_control_pct of last spc_window_n samples
             within [LSL=nominal_hz, USL=upper_hz]                                → NOMINAL
          3. Effective rate ≥ LSL                                                  → NOMINAL (classic path)
          4. Effective rate ≥ degraded_hz                                          → DEGRADED
          5. Else                                                                  → DISCONNECTED

        Note: INV-PCC-003 fail-closed override (signal_disconnect → DISCONNECTED)
        is checked at _recompute level *before* dispatching to this method.
        """
        # Step 1: haptic-tolerance gate
        if self._haptic_tolerance_active(samples, now, effective_rate):
            return CaptureState.NOMINAL

        # Step 2: SPC in-control capability
        recent_n = samples[-self._spc_window_n:] if len(samples) >= self._spc_window_n else samples
        if recent_n:
            # Trim outliers above USL from CV calc (treated as outliers, not stability data).
            in_band = sum(
                1 for r, _ts, *_ in recent_n
                if self._nominal_hz <= r <= self._upper_hz
            )
            in_control_frac = in_band / len(recent_n)
            mean_recent = sum(r for r, _ts, *_ in recent_n) / len(recent_n)
            # In-control when fraction in spec ≥ threshold AND mean is in spec.
            # Mean check prevents bot from sustaining 800 Hz baseline + 6 spike
            # samples crossing LSL → would NOT be NOMINAL despite 6 in-band.
            if in_control_frac >= self._spc_in_control_pct and self._nominal_hz <= mean_recent <= self._upper_hz:
                return CaptureState.NOMINAL

        # Step 3-5: classic classification (matches Phase 234.7 logic)
        if effective_rate >= self._nominal_hz:
            return CaptureState.NOMINAL
        if effective_rate >= self._degraded_hz:
            return CaptureState.DEGRADED
        return CaptureState.DISCONNECTED

    def _haptic_tolerance_active(self, samples: list, now: float, effective_rate: float) -> bool:
        """Phase 235-PCC-SPC INV-PCC-004 + INV-PCC-005 — 3-signal haptic-tolerance binding.

        ALL of the following must hold for tolerance to fire:
          (a) Most recent sample(s) within tolerance window: trigger_active=True
              AND accel_var ≥ haptic_accel_threshold AND
              haptic_tremor_min_hz ≤ tremor_peak_hz ≤ haptic_tremor_max_hz
          (b) Effective rate dip is bounded: rate ≥ haptic_min_dip_hz AND rate < nominal_hz
              (sub-floor dips and full-NOMINAL rates don't need tolerance)
          (c) Tolerance window has not been exceeded: a binding sample exists
              within haptic_tolerance_window_s (i.e., the dip is sub-second)

        Returns True iff ALL three hold; False otherwise (fall through to classic path).
        """
        # (b) — rate must be in DEGRADED band (between min_dip and LSL)
        if effective_rate < self._haptic_min_dip_hz:
            return False
        if effective_rate >= self._nominal_hz:
            return False

        # (a) + (c) — find a binding sample within tolerance window
        cutoff = now - self._haptic_tolerance_window_s
        for rate, ts, ta, av, tp in reversed(samples):
            if ts < cutoff:
                break  # samples ordered chronologically; older ones can't bind
            if (
                ta
                and av >= self._haptic_accel_threshold
                and self._haptic_tremor_min_hz <= tp <= self._haptic_tremor_max_hz
            ):
                return True
        return False

    def _infer_host_state(self, samples: list, rate: float) -> HostState:
        """Infer host arbitration state from per-sample rate variance."""
        # Phase 235-PCC-SPC: 5-tuple unpacking via `*_` to ignore game-context fields.
        rates = [r for r, _ts, *_ in samples if r > 0]
        if len(rates) < 5:
            return HostState.UNKNOWN
        if rate < self._degraded_hz:
            return HostState.UNKNOWN

        mean = sum(rates) / len(rates)
        if mean < 1e-6:
            return HostState.UNKNOWN

        std = math.sqrt(sum((r - mean) ** 2 for r in rates) / len(rates))
        cv = std / mean

        # At nominal USB rate, the host has exclusive control regardless of CV.
        # Haptic feedback and adaptive trigger motors cause bursty HID delivery
        # (high CV) at 1000+ Hz — this is not PS5 BT contention, which always
        # drops rate to ~250 Hz. CV threshold only applies in the ambiguous zone.
        if mean >= self._nominal_hz:
            return HostState.EXCLUSIVE_USB
        # ~250 Hz stable = BT (not expected when USB-only)
        if self._BT_RATE_LOW <= mean <= self._BT_RATE_HIGH and cv < 0.20:
            return HostState.EXCLUSIVE_BT
        # Contested: high variance below nominal rate (genuine host arbitration)
        if cv >= self._CONTESTED_CV and mean >= self._CONTESTED_MIN_RATE_HZ:
            return HostState.CONTESTED
        if cv >= self._CONTESTED_CV:
            return HostState.CONTESTED
        return HostState.UNKNOWN

    def _is_grind_ready_locked(self, now: float) -> bool:
        if self._capture_state != CaptureState.NOMINAL:
            return False
        if self._host_state not in (HostState.EXCLUSIVE_USB, HostState.UNKNOWN):
            return False
        if self._nominal_since is None:
            return False
        return (now - self._nominal_since) >= self._stable_s
