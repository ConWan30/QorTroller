"""QorTroller L9 — synced session recorder + offline analyzer (DESIGN-ONLY).

Records a probe session for OFFLINE coupling analysis (the safe first path —
real-time comes later only if the offline signal separates):
  * captures Remote Play frames -> cv_motion -> (ts, yaw_rate, pitch_rate)
  * polls the DualShock Edge HID -> (ts, right_stick_x, right_stick_y)
  * saves both streams to an .npz, labeled human|scripted

Then analyze_session() feeds them into coupling.InputOutputCouplingOracle and
reports the coupling score, decoupled energy, and the negative control. Collect
~10 human + ~10 scripted sessions and compare the distributions = the GO/NO-GO.

NOTE (probe-grade): input is sampled at the CAPTURE rate (~60Hz), not 1kHz. Aim/
camera motion is low-frequency (<~10Hz), so 60Hz input sampling is adequate for
coupling. 1kHz HID is only needed for the L3/L4/L5 humanity sub-score, which is
computed by the EXISTING bridge layers, not here.

HID stick parsing is pluggable (parse_sticks callable) because byte offsets differ
USB vs BT — wire it to controller/hid_report_parser.py and VALIDATE on-device
before trusting recordings.

STATUS: design-only probe scaffold. No FROZEN-v1 primitive, no chain, no PoAC change.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np

from . import coupling as C
from .cv_motion import MotionExtractor, opencv_available
from .screen_capture import ScreenCapturer, Region

DUALSENSE_VID = 0x054C
DUALSENSE_EDGE_PID = 0x0DF2

StickParser = Callable[[bytes], Tuple[float, float]]


def _default_stick_parser() -> StickParser:
    """Try the project's existing HID parser; else a documented USB fallback."""
    try:
        from controller.hid_report_parser import parse_right_stick  # type: ignore
        return parse_right_stick
    except Exception:
        # USB DualSense input report 0x01: right stick X=byte3, Y=byte4 (0-255).
        # VALIDATE on-device (BT offset differs) before trusting.
        def _fallback(report: bytes) -> Tuple[float, float]:
            if len(report) > 4:
                return float(report[3]), float(report[4])
            return 128.0, 128.0
        return _fallback


@dataclass
class SessionData:
    in_ts: np.ndarray
    in_sx: np.ndarray
    in_sy: np.ndarray
    mo_ts: np.ndarray
    mo_yaw: np.ndarray
    mo_pitch: np.ndarray
    label: str


def record_session(out_path: str, duration_s: float = 60.0, label: str = "human",
                   region: Optional[Region] = None,
                   stick_parser: Optional[StickParser] = None) -> str:
    """Record one labeled probe session to .npz. Hardware + Remote Play required."""
    if not opencv_available():
        raise RuntimeError("opencv-python required (pip install opencv-python)")
    try:
        import hid  # hidapi
    except Exception as exc:
        raise RuntimeError(f"hidapi required (pip install hidapi): {exc}")

    parse = stick_parser or _default_stick_parser()
    cap = ScreenCapturer(region=region, backend="auto")
    mx = MotionExtractor()
    dev = hid.device(); dev.open(DUALSENSE_VID, DUALSENSE_EDGE_PID); dev.set_nonblocking(True)

    in_ts, in_sx, in_sy = [], [], []
    mo_ts, mo_yaw, mo_pitch = [], [], []
    t0 = time.time()
    try:
        while time.time() - t0 < duration_s:
            now_ms = (time.time() - t0) * 1000.0
            rep = dev.read(64)
            if rep:
                sx, sy = parse(bytes(rep))
                in_ts.append(now_ms); in_sx.append(sx); in_sy.append(sy)
            frame = cap.grab()
            if frame is not None:
                out = mx.push_frame(frame, now_ms)
                if out is not None:
                    _, m = out
                    mo_ts.append(now_ms); mo_yaw.append(m.yaw_rate); mo_pitch.append(m.pitch_rate)
    finally:
        dev.close(); cap.close()

    np.savez(out_path,
             in_ts=np.array(in_ts), in_sx=np.array(in_sx), in_sy=np.array(in_sy),
             mo_ts=np.array(mo_ts), mo_yaw=np.array(mo_yaw), mo_pitch=np.array(mo_pitch),
             label=label)
    return out_path


def load_session(path: str) -> SessionData:
    d = np.load(path, allow_pickle=True)
    return SessionData(d["in_ts"], d["in_sx"], d["in_sy"],
                       d["mo_ts"], d["mo_yaw"], d["mo_pitch"], str(d["label"]))


def analyze_session(path: str) -> dict:
    """Feed a recorded session through the coupling oracle. Returns a result dict
    with coupling_score, decoupled_energy, negative_control, and the honest margin."""
    s = load_session(path)
    o = C.InputOutputCouplingOracle()
    for t, x, y in zip(s.in_ts, s.in_sx, s.in_sy):
        o.push_input(float(t), float(x), float(y))
    for t, yaw, pitch in zip(s.mo_ts, s.mo_yaw, s.mo_pitch):
        o.push_frame_motion(float(t), float(yaw), float(pitch))
    f = o.extract_features()
    nc = o.negative_control()
    if f is None:
        return {"label": s.label, "status": "insufficient_aim_activity"}
    return {
        "label": s.label,
        "coupling_score": f.coupling_score,
        "decoupled_energy": f.decoupled_energy,
        "lag_ms": f.lag_ms,
        "dominant_axis": f.dominant_axis,
        "negative_control": nc,
        "neg_control_margin": (f.coupling_score - nc) if nc is not None else None,
        "coupled": f.coupled,
    }
