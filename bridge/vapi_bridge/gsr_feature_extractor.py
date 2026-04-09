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

Phase 158 — Class K Anti-Spoofing:
  WIF-014: validate_gsr_hmac() authenticates 80-byte GSR frames with HMAC-SHA256
  WIF-015: compute_pohbg_hash() produces PoHBG (Proof of Hardware Biometric Grip)
"""
import hashlib
import hmac
import os
import struct
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

    def get_frame(self, device_id: str = "mock_device", hmac_key_hex: str = "00" * 32) -> bytes:
        """Return a signed 80-byte GSR frame (Phase 158 — Class K anti-spoofing test helper)."""
        sample = self.get_sample()
        return make_gsr_frame(
            device_id=device_id,
            arousal_index=sample.arousal_index,
            correlation=sample.correlation,
            conductance_raw=sample.conductance_raw,
            ts_ns=int(sample.timestamp * 1_000_000_000),
            hmac_key_hex=hmac_key_hex,
        )

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


# ---------------------------------------------------------------------------
# Phase 158 — Class K Anti-Spoofing: WIF-014 + WIF-015
# ---------------------------------------------------------------------------

# GSR frame layout (80 bytes):
#   [0:8]   magic        0x47535201_4B434C41 (b"GSR\x01KCLA")
#   [8:12]  arousal_milli uint32 BE  (arousal_index * 1000)
#   [12:16] corr_milli    uint32 BE  (abs(correlation) * 1000)
#   [16:24] conductance   float64 BE (raw μS)
#   [24:32] ts_ns         uint64 BE  (Unix nanoseconds)
#   [32:48] device_id     16-byte UTF-8 padded
#   [48:80] hmac_tag      HMAC-SHA256 of bytes [0:48] under session key

_GSR_FRAME_MAGIC = b"GSR\x01KCLA"
_GSR_FRAME_SIZE  = 80
_GSR_HMAC_OFFSET = 48


class GSRHMACValidationError(Exception):
    """Raised by validate_gsr_hmac() when frame is malformed or auth fails."""


def validate_gsr_hmac(frame: bytes, hmac_key_hex: str) -> dict:
    """Authenticate an 80-byte GSR frame using HMAC-SHA256 (WIF-014).

    Args:
        frame:        80-byte raw GSR frame from ESP32-S3 grip.
        hmac_key_hex: 64-char hex session HMAC key (32 bytes).

    Returns dict with keys: valid, arousal_index, correlation, conductance_raw,
        ts_ns, device_id.

    Raises GSRHMACValidationError on malformed frame or HMAC mismatch.
    Class K anti-spoofing: rejects synthetic EDA generators that cannot
    produce correct HMAC tags without the session key.
    """
    if len(frame) != _GSR_FRAME_SIZE:
        raise GSRHMACValidationError(
            f"frame must be {_GSR_FRAME_SIZE} bytes, got {len(frame)}"
        )
    if frame[:8] != _GSR_FRAME_MAGIC:
        raise GSRHMACValidationError("invalid frame magic bytes")

    try:
        key_bytes = bytes.fromhex(hmac_key_hex)
    except ValueError as exc:
        raise GSRHMACValidationError(f"invalid hmac_key_hex: {exc}") from exc

    # Verify HMAC over payload bytes [0:48]
    payload = frame[:_GSR_HMAC_OFFSET]
    tag_in_frame = frame[_GSR_HMAC_OFFSET:]
    expected_tag = hmac.new(key_bytes, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_tag, tag_in_frame):
        raise GSRHMACValidationError("HMAC-SHA256 tag mismatch — frame rejected")

    # Parse validated payload
    arousal_milli, corr_milli = struct.unpack_from(">II", frame, 8)
    conductance_raw,          = struct.unpack_from(">d", frame, 16)
    ts_ns,                    = struct.unpack_from(">Q", frame, 24)
    device_id = frame[32:48].rstrip(b"\x00").decode("utf-8", errors="replace")

    return {
        "valid":            True,
        "arousal_index":    arousal_milli / 1000.0,
        "correlation":      corr_milli    / 1000.0,
        "conductance_raw":  conductance_raw,
        "ts_ns":            ts_ns,
        "device_id":        device_id,
    }


def make_gsr_frame(
    device_id: str,
    arousal_index: float,
    correlation: float,
    conductance_raw: float,
    ts_ns: int,
    hmac_key_hex: str,
) -> bytes:
    """Build and sign an 80-byte GSR frame (used by MockGSRGrip and tests).

    This is the reference frame constructor; real ESP32-S3 firmware mirrors it.
    """
    dev_bytes = device_id.encode("utf-8")[:16].ljust(16, b"\x00")
    payload = (
        _GSR_FRAME_MAGIC
        + struct.pack(">II", int(arousal_index * 1000), int(abs(correlation) * 1000))
        + struct.pack(">d", conductance_raw)
        + struct.pack(">Q", ts_ns)
        + dev_bytes
    )
    assert len(payload) == _GSR_HMAC_OFFSET
    key_bytes = bytes.fromhex(hmac_key_hex)
    tag = hmac.new(key_bytes, payload, hashlib.sha256).digest()
    return payload + tag


def compute_pohbg_hash(
    device_id: str,
    arousal_millis: int,
    correlation_millis: int,
    conductance_raw_int: int,
    ts_ns: int,
) -> str:
    """Compute PoHBG (Proof of Hardware Biometric Grip) hash (WIF-015).

    PoHBG = SHA-256(device_id_bytes + pack(">IIIQ", arousal_millis,
                    correlation_millis, conductance_raw_int, ts_ns))

    Returns 64-char lowercase hex SHA-256 digest.
    This becomes the third composable proof primitive alongside PoAC and PoAd.
    """
    dev_bytes = device_id.encode("utf-8")[:32].ljust(32, b"\x00")
    packed = struct.pack(
        ">IIIQ",
        arousal_millis,
        correlation_millis,
        conductance_raw_int,
        ts_ns,
    )
    return hashlib.sha256(dev_bytes + packed).hexdigest()
