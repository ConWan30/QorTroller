"""Phase 99B — L7 Galvanic Skin Response feature extraction.

GSR_ENABLED=false is the correct default. All code paths are guarded by
cfg.gsr_enabled or the module-level GSR_ENABLED env var.

MockGSRGrip provides reproducible synthetic EDA for tests and development.
Real hardware replaces MockGSRGrip transparently (same interface).
Hardware BOM: ~$30–45 prototype: Ag/AgCl electrodes, ESP32-S3, INA128
instrumentation amp, LiPo; 4th-order Butterworth LP at 5 Hz; 128 Hz sampling.

Precedent: L6b (Phase 63) and ClassJDetector (Phase 81) both shipped with
enabled=false before physical calibration. Same code-before-hardware pattern.

Inference code: 0x33 GSR_CORRELATION_ABSENT — ADVISORY ONLY, never hard gate.
"""
import os
import time
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Module-level guard — mirrors bridge cfg.gsr_enabled
GSR_ENABLED: bool = os.getenv("GSR_ENABLED", "false").lower() in ("1", "true", "yes")


@dataclass
class GSRSample:
    """A single galvanic skin response measurement."""
    timestamp: float        # Unix seconds
    conductance_raw: float  # μS (microsiemens)
    arousal_index: float    # 0.0–1.0 normalized SCR amplitude
    correlation: float      # Pearson r with game events (-1.0 to +1.0)


class MockGSRGrip:
    """Synthetic GSR signal generator for code-before-hardware development.

    Generates realistic EDA signal: Gaussian noise with synthetic SCR events
    injected every 15–60s to simulate natural sympathetic arousal episodes.

    Seed-reproducible: MockGSRGrip(seed=42) always produces the same sequence.
    Two instances with the same seed produce identical get_sample() streams.

    Precedent: MockProbeDriver (Phase 63 L6b), MockEntropySource (Phase 81 ClassJ).
    """

    def __init__(self, seed: int = 42):
        import random
        self._rng = random.Random(seed)
        self._base_conductance = 5.0 + self._rng.gauss(0, 0.5)  # μS baseline
        self._next_scr_at = time.time() + self._rng.uniform(15, 60)
        self._seed = seed  # preserved for repr / equality checks

    def get_sample(self) -> GSRSample:
        """Return a single synthetic GSR sample."""
        now = time.time()
        noise = self._rng.gauss(0, 0.1)
        scr_amplitude = 0.0
        if now >= self._next_scr_at:
            scr_amplitude = self._rng.uniform(0.3, 1.0)
            self._next_scr_at = now + self._rng.uniform(15, 60)
        conductance = max(0.1, self._base_conductance + noise + scr_amplitude * 2.0)
        arousal = min(1.0, scr_amplitude + abs(noise) * 0.1)
        # Synthetic game event correlation: positive during SCR events (human-like)
        if scr_amplitude > 0:
            correlation = 0.4 + self._rng.gauss(0, 0.1)
        else:
            correlation = self._rng.gauss(0, 0.05)
        return GSRSample(
            timestamp=now,
            conductance_raw=conductance,
            arousal_index=arousal,
            correlation=max(-1.0, min(1.0, correlation)),
        )


def extract_l7_features(gsr_window: list) -> dict:
    """Extract L7_GSR features from a window of GSRSample objects.

    Returns dict with 4 features. Never raises — returns zeros on error.

    Features:
      sympathetic_arousal_index     — mean SCR amplitude (0.0–1.0)
      gsr_game_event_correlation    — mean Pearson r with game events (-1.0–1.0)
      baseline_conductance_drift    — linear regression slope of raw conductance (μS/s)
      cognitive_load_variance       — variance of inter-SCR intervals (ICV)

    Minimum window size: 10 samples. Returns zeros for smaller windows.
    """
    try:
        if len(gsr_window) < 10:
            return _zero_features()

        arousal_vals = [s.arousal_index for s in gsr_window]
        corr_vals = [s.correlation for s in gsr_window]
        conductance_vals = [s.conductance_raw for s in gsr_window]

        # Inter-SCR intervals for cognitive_load_variance
        scr_times = [s.timestamp for s in gsr_window if s.arousal_index > 0.2]
        icv = 0.0
        if len(scr_times) >= 2:
            intervals = [scr_times[i + 1] - scr_times[i]
                         for i in range(len(scr_times) - 1)]
            mean_i = sum(intervals) / len(intervals)
            icv = sum((x - mean_i) ** 2 for x in intervals) / len(intervals)

        # Baseline drift: simple linear regression slope of conductance over time
        n = len(conductance_vals)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(conductance_vals) / n
        denom = sum((x - x_mean) ** 2 for x in xs)
        if denom < 1e-9:
            slope = 0.0
        else:
            slope = sum(
                (xs[i] - x_mean) * (conductance_vals[i] - y_mean) for i in range(n)
            ) / denom

        return {
            "sympathetic_arousal_index": sum(arousal_vals) / len(arousal_vals),
            "gsr_game_event_correlation": sum(corr_vals) / len(corr_vals),
            "baseline_conductance_drift": slope,
            "cognitive_load_variance": icv,
        }
    except Exception as exc:
        log.warning("extract_l7_features: error %s — returning zeros", exc)
        return _zero_features()


def _zero_features() -> dict:
    return {
        "sympathetic_arousal_index": 0.0,
        "gsr_game_event_correlation": 0.0,
        "baseline_conductance_drift": 0.0,
        "cognitive_load_variance": 0.0,
    }
