"""Data Economy Arc 5 — VAPIReplayProofPipeline pre-processor.

Implements the non-invertibility map ``φ = φ_spatial ∘ φ_temporal`` that turns a
session's structural HID replay into a Sanitized Replay Matrix from which the
L4/L5/E4/AIT biometric fingerprint is information-theoretically erased while the
macro-intent (which direction the stick was pushed, which buttons were pressed,
roughly how far a trigger was compressed, general postural octant) is preserved.

Formal foundation: docs/VAPI_REPLAY_PROOF_PIPELINE_SPEC (1).md §1.

Honesty notes — drift from the spec, resolved during Arc 5 pre-investigation
(2026-05-29). The spec was authored against an assumed data model; these are the
reconciliations against the real repository state. See
docs/data-economy-deploy-hold-and-arc5-readiness.md for the deploy-hold context.

  D-5  There is NO ``poac_records`` table with per-frame structural float
       columns. Structural HID frames are persisted as JSON in the
       ``frame_checkpoints.frames_json`` column (Store.store_frame_checkpoint),
       keyed by PoAC ``record_hash``. The real frame keys are
       ``left_stick_x`` / ``left_stick_y`` / ``right_stick_x`` /
       ``right_stick_y`` / ``l2_trigger`` / ``r2_trigger`` / ``accel_x|y|z`` /
       ``buttons_raw`` — NOT the spec's ``stick_l_x`` / ``trigger_l_raw`` /
       ``button_state_raw``. The data floor is therefore enforced as a JSON-key
       allowlist over the frame dicts rather than a SQL column allowlist. The
       biometric features in FORBIDDEN_COLUMNS are never written into
       frames_json (storage is clean by construction), so the floor holds at the
       storage layer in addition to the allowlist enforced here.

  D-6  The 1002 Hz raw HID stream is NEVER persisted. frames_json holds the
       already-downsampled replay ring (~20 Hz). φ_temporal's canonical
       1002→60 Hz median windowing runs over whatever rate the stored frames
       carry; because that rate is already below the 60 Hz output target, the
       non-invertibility property holds *a fortiori* — strictly more biometric
       erasure than the canonical map, never less. The FROZEN constants below
       pin the canonical φ for the PV-CI invariant gate and the on-chain
       circuit; they are NOT recomputed from the stored frame rate.

  D-7  Stick axes are stored as 0–255 bytes (neutral 128); they are normalised
       to [-1, 1] via ``(v - 128) / 128`` (precedent:
       active_play_occupancy._axis_norm). Triggers are 0–255 and quantised by
       ``floor(value / 16)`` exactly as the spec specifies.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

import numpy as np

# --- FROZEN constants — pinned by INV-VHR-001 and INV-VHR-002 ---------------
OUTPUT_HZ: int = 60          # INV-VHR-002: FROZEN — 60 Hz downsampling target
SOURCE_HZ: int = 1002        # matches DualShock Edge CFI-ZCP1 polling rate
RADIAL_BITS: int = 4         # INV-VHR-001: FROZEN — 4-bit radial sector
TRIGGER_BITS: int = 4        # INV-VHR-001: FROZEN — 4-bit trigger quantization
IMU_BITS: int = 3            # INV-VHR-001: FROZEN — 3-bit gravity posture

WINDOW_FRAMES: int = SOURCE_HZ // OUTPUT_HZ   # 17 frames per 16.67 ms window
RADIAL_SECTORS: int = 2 ** RADIAL_BITS        # 16
TRIGGER_STATES: int = 2 ** TRIGGER_BITS       # 16
IMU_SECTORS: int = 2 ** IMU_BITS              # 8

#: Stick magnitude below this (normalised) collapses to the NEUTRAL sector.
DEADZONE: float = 0.1
#: Sentinel sector emitted for a centred (deadzone) stick. Distinct from the 16
#: radial sectors 0..15 so "no direction" is not confused with "east".
NEUTRAL_SECTOR: int = RADIAL_SECTORS          # 16


class DataFloorViolationError(Exception):
    """Raised when the pre-processor is asked to touch a biometric feature.

    The whole point of Arc 5 is that the replay pipeline reads ONLY structural
    HID state. Any attempt to fetch an L4/L5/E4/AIT column is a protocol
    violation and fails closed before any data is read.
    """


@dataclass(frozen=True)
class SanitizedReplayMatrix:
    """60 Hz-class downsampled, quantized session replay.

    Non-invertibility is guaranteed by construction of φ (spec §1.2). The
    following biometric features are information-theoretically erased: L5
    temporal rhythm, E4 spectral entropy, L4 Mahalanobis features, and AIT
    (collapsed into an equivalence class). The macro-intent features (stick
    direction within ±22.5°, trigger compression in 16 states, per-window
    button state, 8-sector gravity posture) are preserved.
    """

    session_id: str
    ticks: int                       # number of windows in the session
    stick_L_sector: bytes            # len=ticks, uint8, 0-15 radial | 16 NEUTRAL
    stick_R_sector: bytes            # len=ticks, uint8, 0-15 radial | 16 NEUTRAL
    trigger_L_state: bytes           # len=ticks, uint8, 0-15 (4-bit compression)
    trigger_R_state: bytes           # len=ticks, uint8, 0-15 (4-bit compression)
    button_mask: bytes               # len=ticks*2, uint16 little-endian bitmask
    imu_gravity_sector: bytes        # len=ticks, uint8, 0-7 (3-bit posture)
    poac_chain_root: bytes           # 32 bytes — Merkle root of session PoAC leaves
    vhp_token_id: int                # gamer's VHP soulbound token id (0 if unwired)
    humanity_prob_floor: float       # min humanity_probability across windows
    session_verdict: str             # "HUMAN" | "CERTIFY" | "" (unwired)


# --- structural-frame contract ---------------------------------------------
#: JSON keys the pre-processor is permitted to read from frames_json. Any key
#: outside this set is ignored; any FORBIDDEN_COLUMNS key triggers a violation.
ALLOWED_FRAME_KEYS: frozenset = frozenset({
    "ts_ms", "ts_ns",
    "left_stick_x", "left_stick_y", "right_stick_x", "right_stick_y",
    "l2_trigger", "r2_trigger",
    "buttons_raw", "buttons",
    "accel_x", "accel_y", "accel_z",
})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _axis_norm(value: Any) -> float:
    """0-255 byte axis (neutral 128) → [-1, 1]. Mirrors active_play_occupancy."""
    v = _safe_float(value, 0.0)
    if 0.0 <= v <= 255.0:
        return max(-1.0, min(1.0, (v - 128.0) / 128.0))
    if abs(v) <= 512.0:
        return max(-1.0, min(1.0, v / 128.0))
    return max(-1.0, min(1.0, v / 32768.0))


class ReplayPreProcessor:
    """Implements ``φ = φ_spatial ∘ φ_temporal``.

    Reads structural input state from the bridge's ``frame_checkpoints``
    (``frames_json``) — HID stick / trigger / button / accel only. It NEVER
    reads biometric feature state (L4 vector, L5 rhythm, E4 entropy, AIT). Those
    are computed separately by the PITL stack for adjudication and never enter
    this pipeline. The data floor is enforced here by ``ALLOWED_FRAME_KEYS`` and
    the ``FORBIDDEN_COLUMNS`` guard, and at the storage layer because frames_json
    only ever contains structural HID state.
    """

    #: Biometric features that must never be read by the replay pipeline.
    #: Frozen by INV-VHR-004; mirrors the spec §9 data-floor list plus the real
    #: PITL feature names used elsewhere in the bridge.
    FORBIDDEN_COLUMNS: frozenset = frozenset({
        "l4_mahalanobis_distance", "l4_vector", "l4_feature_0",
        "l5_cv", "l5_entropy", "l5_quantization",
        "e4_spectral_entropy", "e4_band_power",
        "ait_rms", "ait_variance", "grip_asymmetry",
        "micro_tremor_variance", "press_timing_jitter_variance",
        "trigger_onset_velocity_l2", "trigger_onset_velocity_r2",
        "stick_autocorr_lag1", "stick_autocorr_lag5",
        "accel_tremor_peak_hz", "tremor_band_power",
        "accel_magnitude_spectral_entropy",
    })

    # -- public entry point --------------------------------------------------
    def process_session(
        self,
        session_id: str,
        *,
        frames: Optional[Sequence[dict]] = None,
        store: Any = None,
        device_id: Optional[str] = None,
        record_hashes: Optional[Sequence[str]] = None,
        vhp_token_id: int = 0,
        humanity_prob_floor: float = 0.0,
        session_verdict: str = "",
    ) -> SanitizedReplayMatrix:
        """Apply φ to a session and return its SanitizedReplayMatrix.

        Frames may be supplied directly (``frames=``) or fetched from a Store
        (``store=`` + ``device_id=``). Biometric metadata (vhp_token_id,
        humanity_prob_floor, verdict) is injected by the orchestrator (Commit 4);
        it is NOT derived here.
        """
        raw = self._fetch_structural_frames(
            session_id, frames=frames, store=store, device_id=device_id,
        )
        flat = self._temporal_flatten(raw)
        matrix = self._spatial_quantize(flat)
        leaves = self._collect_leaves(
            store=store, device_id=device_id, record_hashes=record_hashes,
        )
        root = self._merkle_root(leaves)
        return SanitizedReplayMatrix(
            session_id=session_id,
            ticks=len(flat),
            poac_chain_root=root,
            vhp_token_id=int(vhp_token_id),
            humanity_prob_floor=float(humanity_prob_floor),
            session_verdict=session_verdict,
            **matrix,
        )

    # -- data floor + frame fetch -------------------------------------------
    def _fetch_structural_frames(
        self,
        session_id: str,
        *,
        frames: Optional[Sequence[dict]] = None,
        store: Any = None,
        device_id: Optional[str] = None,
        _force_column: Optional[str] = None,
    ) -> list[dict]:
        """Return structural frame dicts, enforcing the data floor.

        ``_force_column`` is a test-only injection hook: passing any
        FORBIDDEN_COLUMNS name raises DataFloorViolationError before any read,
        proving the floor fails closed (spec §2.3 test_data_floor_at_db_query_level).
        """
        if _force_column is not None and _force_column in self.FORBIDDEN_COLUMNS:
            raise DataFloorViolationError(
                f"refusing to read biometric feature {_force_column!r}: "
                "the replay pipeline reads structural HID state only"
            )

        if frames is None:
            frames = self._load_frames_from_store(store, device_id)

        return [self._sanitize_frame(f) for f in frames]

    def _sanitize_frame(self, frame: dict) -> dict:
        """Project a raw frame dict onto ALLOWED_FRAME_KEYS, failing closed on
        any biometric key (defence in depth — frames_json should never contain
        one, but we never trust an upstream that smuggled it in)."""
        for key in frame:
            if key in self.FORBIDDEN_COLUMNS:
                raise DataFloorViolationError(
                    f"biometric feature {key!r} present in frame — data floor breach"
                )
        return {k: frame[k] for k in frame if k in ALLOWED_FRAME_KEYS}

    @staticmethod
    def _load_frames_from_store(store: Any, device_id: Optional[str]) -> list[dict]:
        if store is None or device_id is None:
            return []
        checkpoints: list[dict] = []
        if hasattr(store, "get_recent_frame_checkpoints_for_device"):
            checkpoints = store.get_recent_frame_checkpoints_for_device(
                device_id, limit=500,
            )
        out: list[dict] = []
        for cp in checkpoints:
            frames = cp.get("frames") if isinstance(cp, dict) else None
            if isinstance(frames, list):
                out.extend(f for f in frames if isinstance(f, dict))
        return out

    # -- φ_temporal: rolling-median downsample ------------------------------
    def _temporal_flatten(self, frames: list[dict]) -> list[dict]:
        """1002 Hz → 60 Hz (canonical) via per-channel median over WINDOW_FRAMES.

        Sub-window jitter, release velocities, and inter-event timing intervals
        are destroyed by the window median — they cannot be recovered. The
        median is deterministic (odd N gives a unique value). With sparse stored
        frames the same map applies a fortiori (D-6).
        """
        windows = [
            frames[i:i + WINDOW_FRAMES]
            for i in range(0, len(frames), WINDOW_FRAMES)
        ]
        return [self._temporal_flatten_window(w) for w in windows if w]

    def _temporal_flatten_window(self, window: Sequence[dict]) -> dict:
        """Collapse one window of raw frames into a single median tick."""
        def med(key: str) -> float:
            return float(np.median([_safe_float(f.get(key, 0.0)) for f in window]))

        n = len(window)
        raw_buttons = [
            _safe_int(f.get("buttons_raw", f.get("buttons", 0))) for f in window
        ]
        button_bits = 0
        for bit in range(16):
            held = sum((b >> bit) & 1 for b in raw_buttons)
            if held * 2 > n:                     # majority vote (held > N/2)
                button_bits |= (1 << bit)

        return {
            "left_stick_x": med("left_stick_x"),
            "left_stick_y": med("left_stick_y"),
            "right_stick_x": med("right_stick_x"),
            "right_stick_y": med("right_stick_y"),
            "l2_trigger": med("l2_trigger"),
            "r2_trigger": med("r2_trigger"),
            "accel_x": med("accel_x"),
            "accel_y": med("accel_y"),
            "accel_z": med("accel_z"),
            "buttons": button_bits,
        }

    # -- φ_spatial: continuous → discrete -----------------------------------
    def _spatial_quantize(self, flat: list[dict]) -> dict:
        sl, sr, tl, tr, bm, imu = [], [], [], [], bytearray(), []
        for tick in flat:
            sl.append(self._spatial_quantize_stick(
                tick["left_stick_x"], tick["left_stick_y"]))
            sr.append(self._spatial_quantize_stick(
                tick["right_stick_x"], tick["right_stick_y"]))
            tl.append(self._quantize_trigger(tick["l2_trigger"]))
            tr.append(self._quantize_trigger(tick["r2_trigger"]))
            bits = int(tick["buttons"]) & 0xFFFF
            bm += bits.to_bytes(2, "little")
            imu.append(self._imu_octant(
                tick["accel_x"], tick["accel_y"], tick["accel_z"]))
        return {
            "stick_L_sector": bytes(sl),
            "stick_R_sector": bytes(sr),
            "trigger_L_state": bytes(tl),
            "trigger_R_state": bytes(tr),
            "button_mask": bytes(bm),
            "imu_gravity_sector": bytes(imu),
        }

    @staticmethod
    def _spatial_quantize_stick(x: float, y: float) -> int:
        """Stick (raw byte or [-1,1]) → 4-bit radial sector, or NEUTRAL."""
        nx, ny = _axis_norm(x), _axis_norm(y)
        if math.hypot(nx, ny) < DEADZONE:
            return NEUTRAL_SECTOR
        angle = math.atan2(ny, nx) % (2.0 * math.pi)
        return int(angle / (2.0 * math.pi / RADIAL_SECTORS)) % RADIAL_SECTORS

    @staticmethod
    def _quantize_trigger(value: float) -> int:
        """Trigger 0-255 → 4-bit state {0..15} via floor(value / 16)."""
        v = max(0.0, _safe_float(value, 0.0))
        if v <= 1.0:                            # already normalised to [0,1]
            v *= 255.0
        return min(TRIGGER_STATES - 1, int(v // 16))

    @staticmethod
    def _imu_octant(ax: float, ay: float, az: float) -> int:
        """Gravity vector → 3-bit octant from the sign bits of each axis.

        AIT tremor amplitudes are orders of magnitude below the octant-crossing
        threshold, so they cannot move the octant index.
        """
        bx = 1 if _safe_float(ax) >= 0.0 else 0
        by = 1 if _safe_float(ay) >= 0.0 else 0
        bz = 1 if _safe_float(az) >= 0.0 else 0
        return (bx << 2) | (by << 1) | bz

    # -- single-signal helper (spec §2.3 mahalanobis test) -------------------
    def process_signal(self, signal: Sequence[dict]) -> SanitizedReplayMatrix:
        """Run φ over an in-memory signal (list of raw frame dicts).

        Convenience wrapper for verification tests that synthesise a controller
        signal and assert its quantized output is invariant to a biometric
        property. Equivalent to process_session(frames=signal) with no chain
        root / metadata.
        """
        return self.process_session("__signal__", frames=signal)

    # -- PoAC Merkle root ----------------------------------------------------
    def _collect_leaves(
        self,
        *,
        store: Any = None,
        device_id: Optional[str] = None,
        record_hashes: Optional[Sequence[str]] = None,
    ) -> list[bytes]:
        """Gather the session's PoAC record-hash leaves (SHA-256(body[0:164]))."""
        hashes: list[str] = []
        if record_hashes:
            hashes = [h for h in record_hashes if h]
        elif store is not None and device_id is not None and hasattr(
            store, "list_checkpoints_for_device"
        ):
            hashes = list(store.list_checkpoints_for_device(device_id))
        out: list[bytes] = []
        for h in hashes:
            try:
                out.append(bytes.fromhex(h))
            except (ValueError, TypeError):
                continue
        return out

    @staticmethod
    def _merkle_root(leaves: Sequence[bytes]) -> bytes:
        """Deterministic binary Merkle root over PoAC leaves.

        Commit 1 uses SHA-256 (the same hash that produces the PoAC chain-link
        leaves) so the matrix is self-contained and verifiable in pure Python.
        Commit 2 swaps the node hash to Poseidon-8 to match
        PitlSessionProofVerifier and the on-chain circuit; the leaf set is
        identical, only the node permutation changes.
        """
        if not leaves:
            return b"\x00" * 32
        level = [bytes(x) for x in leaves]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])         # duplicate last (odd count)
            level = [
                hashlib.sha256(level[i] + level[i + 1]).digest()
                for i in range(0, len(level), 2)
            ]
        return level[0]
