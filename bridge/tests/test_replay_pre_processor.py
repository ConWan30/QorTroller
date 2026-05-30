"""Data Economy Arc 5 — ReplayPreProcessor verification suite.

Verifies the implementation satisfies the formal non-invertibility claim of
docs/VAPI_REPLAY_PROOF_PIPELINE_SPEC (1).md §1.2: φ is surjective, not
injective, so distinct biometric inputs collapse to a single quantized output.

Adapted to the real data model (drift D-5/D-6/D-7 in pre_processor.py): frames
are dicts with keys left_stick_x / l2_trigger / accel_x etc., stick axes are
0-255 bytes (neutral 128), triggers 0-255.
"""

import math

import numpy as np
import pytest

from bridge.vapi_bridge.replay_proof_pipeline.pre_processor import (
    DataFloorViolationError,
    NEUTRAL_SECTOR,
    RADIAL_SECTORS,
    ReplayPreProcessor,
    TRIGGER_STATES,
    WINDOW_FRAMES,
    OUTPUT_HZ,
    RADIAL_BITS,
    TRIGGER_BITS,
    IMU_BITS,
)

pp = ReplayPreProcessor()


# --- helpers ---------------------------------------------------------------
def _frame(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
           ax=0.0, ay=0.0, az=1.0, buttons=0):
    return {
        "left_stick_x": lx, "left_stick_y": ly,
        "right_stick_x": rx, "right_stick_y": ry,
        "l2_trigger": l2, "r2_trigger": r2,
        "accel_x": ax, "accel_y": ay, "accel_z": az,
        "buttons_raw": buttons,
    }


def _stick_held_midsector(jitter_amplitude_bytes):
    """A left stick held in the middle of a radial sector with an AIT-style
    tremor of given amplitude.

    The hold direction (≈30° NE, sector 1 of 16) sits well clear of a sector
    boundary; the tremor perturbs the stick by up to ``jitter_amplitude_bytes``
    around it. All such tremors must collapse to the same radial sector — the
    AIT amplitude is not recoverable. (A hold placed *on* a sector boundary
    would legitimately straddle two sectors under jitter; that is correct
    quantizer behaviour, not a non-invertibility breach.)
    """
    rng = np.random.default_rng(0)
    frames = []
    for _ in range(WINDOW_FRAMES):
        dx = rng.uniform(-jitter_amplitude_bytes, jitter_amplitude_bytes)
        dy = rng.uniform(-jitter_amplitude_bytes, jitter_amplitude_bytes)
        frames.append(_frame(lx=int(np.clip(230 + dx, 0, 255)),
                             ly=int(np.clip(190 + dy, 0, 255))))
    return frames


# --- §2.3 non-invertibility verification -----------------------------------
def test_ait_equivalence_class_stick():
    """100 distinct AIT tremor amplitudes → identical sector output."""
    sectors = set()
    for amp in np.linspace(0.5, 30.0, 100):     # bytes of tremor around a hold
        frames = _stick_held_midsector(amp)
        flat = pp._temporal_flatten_window(frames)
        sectors.add(pp._spatial_quantize_stick(
            flat["left_stick_x"], flat["left_stick_y"]))
    assert len(sectors) == 1, f"AIT tremors must collapse to one sector, got {sectors}"


def test_subms_jitter_erased():
    """50 distinct sub-window jitter patterns → identical 60 Hz window output."""
    outputs = []
    for seed in range(50):
        rng = np.random.default_rng(seed)
        frames = []
        for _ in range(WINDOW_FRAMES):
            # mid-sector hold with tiny timing-jitter perturbations
            frames.append(_frame(
                lx=int(np.clip(230 + rng.uniform(-2, 2), 0, 255)),
                ly=int(np.clip(190 + rng.uniform(-2, 2), 0, 255)),
                l2=int(np.clip(200 + rng.uniform(-3, 3), 0, 255)),
            ))
        flat = pp._temporal_flatten_window(frames)
        outputs.append((
            pp._spatial_quantize_stick(flat["left_stick_x"], flat["left_stick_y"]),
            pp._quantize_trigger(flat["l2_trigger"]),
        ))
    assert all(o == outputs[0] for o in outputs), "jitter must not change the tick"


def test_data_floor_at_db_query_level():
    """Fetching any forbidden biometric column raises DataFloorViolationError."""
    for col in ReplayPreProcessor.FORBIDDEN_COLUMNS:
        with pytest.raises(DataFloorViolationError):
            pp._fetch_structural_frames(
                "test", frames=[], _force_column=col,
            )


def test_data_floor_rejects_smuggled_biometric_frame():
    """A frame carrying a biometric key fails closed even if not force-injected."""
    bad = _frame()
    bad["l4_mahalanobis_distance"] = 9.3
    with pytest.raises(DataFloorViolationError):
        pp._fetch_structural_frames("test", frames=[bad])


def test_l4_mahalanobis_not_recoverable():
    """Distinct L4 Mahalanobis 'distances' → identical quantized sector.

    We synthesise the structural surface that would underlie a range of L4
    distances (a held-east stick with increasing tremor variance, the dominant
    L4 feature) and assert the sector is invariant — the distance is erased.
    """
    sectors = set()
    for d in [5.0, 7.0, 9.0, 12.0, 20.0]:       # below and above threshold 7.009
        frames = _stick_held_midsector(d)       # variance scales with d
        m = pp.process_signal(frames)
        sectors.add(m.stick_L_sector[0])
    assert len(sectors) == 1, f"Mahalanobis distance leaked into sector: {sectors}"


# --- φ_spatial correctness -------------------------------------------------
def test_stick_radial_sectors_and_deadzone():
    """Known directions map to known sectors; centre maps to NEUTRAL."""
    # centre stick (128,128) → NEUTRAL
    assert pp._spatial_quantize_stick(128, 128) == NEUTRAL_SECTOR
    # hard east (255,128) → sector 0 (angle 0)
    assert pp._spatial_quantize_stick(255, 128) == 0
    # hard north (128,255) maps to the quarter-circle sector
    north = pp._spatial_quantize_stick(128, 255)
    assert north == RADIAL_SECTORS // 4
    # every non-deadzone direction yields a valid sector 0..15
    for ang in np.linspace(0, 2 * math.pi, 64, endpoint=False):
        x = int(np.clip(128 + 120 * math.cos(ang), 0, 255))
        y = int(np.clip(128 + 120 * math.sin(ang), 0, 255))
        s = pp._spatial_quantize_stick(x, y)
        assert 0 <= s < RADIAL_SECTORS


def test_trigger_quantization():
    """0-255 trigger → floor(value/16), clamped to 15."""
    assert pp._quantize_trigger(0) == 0
    assert pp._quantize_trigger(15) == 0
    assert pp._quantize_trigger(16) == 1
    assert pp._quantize_trigger(255) == TRIGGER_STATES - 1
    # normalised [0,1] input is rescaled before quantizing
    assert pp._quantize_trigger(1.0) == TRIGGER_STATES - 1


def test_imu_octant_sign_bits():
    """IMU octant is the 3 sign bits of the gravity vector; 8 distinct octants."""
    seen = set()
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                seen.add(pp._imu_octant(sx * 0.4, sy * 0.4, sz * 0.9))
    assert seen == set(range(8))
    # an AIT-scale tremor cannot flip an octant away from a clear posture
    base = pp._imu_octant(0.3, 0.3, 0.9)
    assert pp._imu_octant(0.3001, 0.2999, 0.9001) == base


# --- end-to-end + frozen-constant pinning ----------------------------------
def test_process_session_shapes():
    """A multi-window session yields aligned per-tick byte arrays."""
    frames = []
    for _ in range(WINDOW_FRAMES * 3):
        frames.append(_frame(lx=255, l2=128, az=0.98))
    m = pp.process_session("sess-1", frames=frames, vhp_token_id=2,
                           humanity_prob_floor=0.91, session_verdict="HUMAN")
    assert m.ticks == 3
    assert len(m.stick_L_sector) == 3
    assert len(m.stick_R_sector) == 3
    assert len(m.trigger_L_state) == 3
    assert len(m.imu_gravity_sector) == 3
    assert len(m.button_mask) == 3 * 2          # uint16 per tick
    assert m.vhp_token_id == 2
    assert m.session_verdict == "HUMAN"
    assert len(m.poac_chain_root) == 32


def test_poac_merkle_root_deterministic():
    """The Merkle root is deterministic and order-sensitive over leaves."""
    leaves = [bytes([i]) * 32 for i in range(5)]
    hexes = [l.hex() for l in leaves]
    r1 = pp._merkle_root(leaves)
    r2 = pp._merkle_root(leaves)
    assert r1 == r2 and len(r1) == 32
    assert pp._merkle_root(list(reversed(leaves))) != r1
    # empty session → zero root
    assert pp._merkle_root([]) == b"\x00" * 32
    # via _collect_leaves from record_hashes
    collected = pp._collect_leaves(record_hashes=hexes)
    assert pp._merkle_root(collected) == r1


def test_frozen_constants_pinned():
    """INV-VHR-001 / INV-VHR-002 frozen parameters must not drift."""
    assert OUTPUT_HZ == 60
    assert RADIAL_BITS == 4
    assert TRIGGER_BITS == 4
    assert IMU_BITS == 3
    assert WINDOW_FRAMES == 1002 // 60
    assert RADIAL_SECTORS == 16 and TRIGGER_STATES == 16
