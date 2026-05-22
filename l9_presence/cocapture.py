"""QorTroller L9 Fusion F1 — co-capture recorder + autonomous F3-readiness.

Captures, in ONE gameplay session, BOTH feature views needed for fusion:
  * L9 render-loop features (right-stick -> camera coupling), and
  * L4 controller-biometric features (the 13-dim BiometricFeatureExtractor vector),
both derived from a single dedicated 1 kHz HID reader thread running parallel to the
mss frame loop. Output plugs straight into the F0 fusion harness (l9_presence.fusion).

It ALSO answers, autonomously, the operator's real question: **does F3 need more
players?** `fusion_readiness()` inspects the co-captured corpus and returns a precise
ready / needs-capture verdict (which players, how many more sessions) — so capture is
demand-driven, not guesswork.

HONESTY: right-stick (bytes 3/4) and triggers (5/6) are on-device validated. The IMU
byte mapping/scaling (gyro/accel ~16-27) is PROVISIONAL and load-bearing for L4 quality
— it needs the same on-device validation the stick got (an IMU analog of hid_probe).
So the recorder ALWAYS stores the raw 1 kHz buffer; L4 is recomputable offline once the
mapping is confirmed, and is flagged l4_provisional=True until then.

No FROZEN-v1 primitive, no PoAC, no chain, no contract. Reuses the existing
controller.tinyml_biometric_fusion.BiometricFeatureExtractor (no reinvention).
"""
from __future__ import annotations

import glob
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from .biometric_features import _SEP_FEATURES, extract_feature_vector
from .session_recorder import SessionData

DUALSENSE_VID = 0x054C
DUALSENSE_EDGE_PID = 0x0DF2
CALIBRATION_WINDOW_FRAMES = 1025   # tinyml extractor offline/calibration mode

# DualSense report 0x01 byte map. sticks/triggers VALIDATED; IMU PROVISIONAL (validate on-device).
DEFAULT_OFFSETS = {
    "lx": 1, "ly": 2, "rx": 3, "ry": 4, "l2": 5, "r2": 6,
    "gyro_x": 16, "gyro_y": 18, "gyro_z": 20,     # int16 LE @ these offsets — PROVISIONAL
    "accel_x": 22, "accel_y": 24, "accel_z": 26,  # int16 LE — PROVISIONAL
}
_IMU_SCALE = 1.0 / 8192.0   # nominal raw->g-ish scale (PROVISIONAL; accel_z≈1.0 rest expected)


def _i16le(b: bytes, i: int) -> int:
    return int.from_bytes(b[i:i + 2], "little", signed=True) if len(b) >= i + 2 else 0


VALIDATED_OFFSETS_PATH = os.path.join("cocapture_l9", "imu_offsets.json")


def load_validated_offsets(path: str = VALIDATED_OFFSETS_PATH):
    """Load on-device-validated IMU offsets+scale from imu_probe, or None if absent.
    Returns (offsets_dict, scale) where offsets merges validated IMU over stick/trigger."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            v = json.load(fh)
        if "gyro_x" not in v:
            return None
        offs = dict(DEFAULT_OFFSETS)
        for k in ("gyro_x", "gyro_y", "gyro_z", "accel_x", "accel_y", "accel_z"):
            offs[k] = int(v[k])
        return offs, float(v.get("scale", _IMU_SCALE))
    except Exception:
        return None


def raw_reports_to_snapshots(reports, ts_us, offsets=None, scale=None):
    """Map raw 64-byte HID reports -> _InputSnapshotLike objects for the extractor.
    IMU fields are PROVISIONAL unless `offsets`/`scale` come from imu_probe validation."""
    from controller.tinyml_biometric_fusion import _InputSnapshotLike  # guarded by caller
    o = offsets or DEFAULT_OFFSETS
    sc = scale if scale is not None else _IMU_SCALE
    snaps = []
    for k, rb in enumerate(reports):
        dt_us = int(ts_us[k] - ts_us[k - 1]) if k > 0 else 1000
        snaps.append(_InputSnapshotLike(
            left_stick_x=rb[o["lx"]], left_stick_y=rb[o["ly"]],
            right_stick_x=rb[o["rx"]], right_stick_y=rb[o["ry"]],
            l2_trigger=rb[o["l2"]], r2_trigger=rb[o["r2"]],
            gyro_x=_i16le(rb, o["gyro_x"]) * sc,
            gyro_y=_i16le(rb, o["gyro_y"]) * sc,
            gyro_z=_i16le(rb, o["gyro_z"]) * sc,
            accel_x=_i16le(rb, o["accel_x"]) * sc,
            accel_y=_i16le(rb, o["accel_y"]) * sc,
            accel_z=_i16le(rb, o["accel_z"]) * sc,
            inter_frame_us=max(1, dt_us)))
    return snaps


def compute_l4_features(reports, ts_us, offsets=None, scale=None) -> Optional[np.ndarray]:
    """13-dim L4 biometric vector via the existing BiometricFeatureExtractor, or None
    if the extractor isn't importable. Uses imu_probe-validated offsets/scale when
    available (offsets/scale args override; else falls back to provisional defaults)."""
    try:
        from controller.tinyml_biometric_fusion import BiometricFeatureExtractor
    except Exception:
        return None
    if len(reports) < 8:
        return None
    snaps = raw_reports_to_snapshots(reports, ts_us, offsets, scale)
    frame = BiometricFeatureExtractor().extract(snaps, window_frames=CALIBRATION_WINDOW_FRAMES)
    return np.asarray(frame.to_vector(), float)


@dataclass
class CoCaptureSession:
    player: str
    l9_vec: list                 # the _SEP_FEATURES values (render view)
    l4_vec: Optional[list]       # 13-dim controller-biometric view (None if unavailable)
    l9_reliable: bool
    l9_coupling: float
    l4_provisional: bool         # True until the IMU mapping is on-device validated
    n_hid: int = 0
    n_frames: int = 0


def save_cocapture(path: str, s: CoCaptureSession, raw_reports=None, ts_us=None,
                   l9_streams=None) -> str:
    payload = dict(player=s.player, l9_vec=np.array(s.l9_vec, float),
                   l4_vec=(np.array(s.l4_vec, float) if s.l4_vec is not None else np.array([])),
                   l9_reliable=s.l9_reliable, l9_coupling=s.l9_coupling,
                   l4_provisional=s.l4_provisional, n_hid=s.n_hid, n_frames=s.n_frames)
    if raw_reports is not None and ts_us is not None:   # keep raw for offline L4 recompute
        payload["raw"] = np.array([list(r[:64]) for r in raw_reports], dtype=np.uint8)
        payload["raw_ts_us"] = np.array(ts_us, dtype=np.int64)
    if l9_streams is not None:   # keep L9 streams so coupling is recomputable / diagnosable
        for k in ("in_ts", "in_sx", "in_sy", "mo_ts", "mo_yaw", "mo_pitch"):
            payload[k] = np.asarray(l9_streams[k], float)
    np.savez(path, **payload)
    return path


def recompute_l9_from_file(path: str) -> dict:
    """Re-run the L9 coupling analysis from a co-capture file's stored streams (for
    verifying/diagnosing the recorder). Returns the full analyze_session_data dict."""
    from .session_recorder import analyze_session_data
    d = np.load(path, allow_pickle=True)
    if "in_ts" not in d.files:
        return {"status": "no_l9_streams_stored"}
    sd = SessionData(d["in_ts"], d["in_sx"], d["in_sy"], d["mo_ts"], d["mo_yaw"],
                     d["mo_pitch"], "human", None, str(d["player"]))
    r = analyze_session_data(sd)
    r["stick_x_std"] = float(np.std(d["in_sx"]))
    r["stick_y_std"] = float(np.std(d["in_sy"]))
    r["n_hid"] = int(d["in_ts"].size)
    r["n_frames"] = int(d["mo_ts"].size)
    return r


def load_cocapture(path: str) -> CoCaptureSession:
    d = np.load(path, allow_pickle=True)
    l4 = d["l4_vec"]
    return CoCaptureSession(
        player=str(d["player"]), l9_vec=list(d["l9_vec"]),
        l4_vec=(list(l4) if l4.size else None),
        l9_reliable=bool(d["l9_reliable"]), l9_coupling=float(d["l9_coupling"]),
        l4_provisional=bool(d["l4_provisional"]),
        n_hid=int(d["n_hid"]), n_frames=int(d["n_frames"]))


def to_multiview(sessions):
    """CoCaptureSessions -> F0 MultiViewSession list (reliable + both views present)."""
    from .fusion import MultiViewSession
    out = []
    for s in sessions:
        if s.l9_reliable and s.l4_vec is not None:
            out.append(MultiViewSession(s.player, {"l9": list(s.l9_vec), "l4": list(s.l4_vec)}))
    return out


def fusion_readiness(corpus_dir: str = "cocapture_l9", min_per_player: int = 5,
                     min_players: int = 2, tournament_players: int = 3) -> dict:
    """AUTONOMOUS F3-readiness: does fusion (F3) have enough co-captured data, or does
    it need more players / sessions? Counts sessions with BOTH views present and a
    reliable L9 signal, per player, and emits an exact gap list."""
    paths = sorted(glob.glob(os.path.join(corpus_dir, "*.npz")))
    sessions = [load_cocapture(p) for p in paths]
    usable = [s for s in sessions if s.l9_reliable and s.l4_vec is not None]
    per_player: dict = {}
    for s in usable:
        per_player[s.player] = per_player.get(s.player, 0) + 1
    players = sorted(per_player)
    n_players = len(players)
    short = {pl: min_per_player - per_player[pl] for pl in players if per_player[pl] < min_per_player}
    gaps = []
    if n_players < tournament_players:
        gaps.append(f"need {tournament_players - n_players} more player(s) for tournament-grade "
                    f"(have {n_players})")
    for pl, need in short.items():
        gaps.append(f"{pl} needs {need} more reliable co-captured session(s)")
    runnable = n_players >= min_players and all(per_player[pl] >= min_per_player for pl in players)
    provisional = any(s.l4_provisional for s in usable)
    return {
        "corpus_dir": corpus_dir,
        "total_sessions": len(sessions),
        "usable_sessions": len(usable),
        "players": per_player,
        "f3_runnable": bool(runnable),
        "tournament_grade_possible": bool(runnable and n_players >= tournament_players),
        "needs_capture": not runnable or n_players < tournament_players,
        "gaps": gaps,
        "l4_provisional_warning": bool(provisional),
        "recommendation": ("F3 can run now" if runnable else "capture more before F3: " + "; ".join(gaps)),
    }


@dataclass
class CoCaptureConfig:
    player: str = "P1"
    duration_s: float = 60.0
    region: Optional[Tuple[int, int, int, int]] = (640, 360, 1280, 720)
    backend: str = "mss"
    out_dir: str = "cocapture_l9"
    coupling_floor: float = 0.2


class CoCaptureRecorder:
    """Live co-capture: a 1 kHz HID reader thread (raw report 0x01) parallel to the mss
    frame loop. Derives the L9 view from the stick stream + camera, the L4 view from the
    raw buffer via the existing extractor, and stores both + the raw buffer."""

    def __init__(self, cfg: Optional[CoCaptureConfig] = None) -> None:
        self.cfg = cfg or CoCaptureConfig()
        os.makedirs(self.cfg.out_dir, exist_ok=True)

    def record_once(self) -> dict:
        import threading
        import hid
        from .screen_capture import ScreenCapturer
        from .cv_motion import MotionExtractor, opencv_available
        if not opencv_available():
            raise RuntimeError("opencv-python required")
        reports, ts_us = [], []
        stop = threading.Event()
        t0 = time.time()   # SHARED zero for BOTH streams — keeps stick/camera lag aligned

        def _hid_loop():
            d = hid.device(); d.open(DUALSENSE_VID, DUALSENSE_EDGE_PID); d.set_nonblocking(True)
            try:
                while not stop.is_set():
                    r = d.read(64)
                    if r:
                        reports.append(bytes(r)); ts_us.append(int((time.time() - t0) * 1e6))
                    else:
                        time.sleep(0.0002)
            finally:
                d.close()

        th = threading.Thread(target=_hid_loop, daemon=True); th.start()
        cap = ScreenCapturer(region=self.cfg.region, backend=self.cfg.backend)
        mx = MotionExtractor()
        mo_ts, mo_yaw, mo_pitch = [], [], []
        frame_start = time.time()   # frames span duration_s from here; timestamps stay vs shared t0
        try:
            while time.time() - frame_start < self.cfg.duration_s:
                now_ms = (time.time() - t0) * 1000.0
                frame = cap.grab()
                if frame is not None:
                    out = mx.push_frame(frame, now_ms)
                    if out is not None:
                        _, m = out
                        mo_ts.append(now_ms); mo_yaw.append(m.yaw_rate); mo_pitch.append(m.pitch_rate)
        finally:
            stop.set(); th.join(timeout=2.0); cap.close()

        # L9 view from the 1 kHz stick stream + camera
        rx, ry = DEFAULT_OFFSETS["rx"], DEFAULT_OFFSETS["ry"]
        in_ts = np.array([t / 1000.0 for t in ts_us])           # ms
        in_sx = np.array([float(r[rx]) for r in reports])
        in_sy = np.array([float(r[ry]) for r in reports])
        sd = SessionData(in_ts, in_sx, in_sy, np.array(mo_ts), np.array(mo_yaw),
                         np.array(mo_pitch), "human", None, self.cfg.player)
        fv = extract_feature_vector(sd, self.cfg.coupling_floor)
        l9_vec = [fv[k] for k in _SEP_FEATURES] if fv else [0.0] * len(_SEP_FEATURES)
        validated = load_validated_offsets()
        if validated:
            voff, vscale = validated
            l4 = compute_l4_features(reports, ts_us, voff, vscale)
        else:
            l4 = compute_l4_features(reports, ts_us)
        s = CoCaptureSession(
            player=self.cfg.player, l9_vec=l9_vec,
            l4_vec=(list(map(float, l4)) if l4 is not None else None),
            l9_reliable=bool(fv["reliable"]) if fv else False,
            l9_coupling=float(fv["dominant_coupling"]) if fv else 0.0,
            l4_provisional=(validated is None) or (l4 is None),
            n_hid=len(reports), n_frames=len(mo_ts))
        n = len(glob.glob(os.path.join(self.cfg.out_dir, f"{self.cfg.player}_*.npz"))) + 1
        out = os.path.join(self.cfg.out_dir, f"{self.cfg.player}_{n:02d}.npz")
        l9_streams = {"in_ts": in_ts, "in_sx": in_sx, "in_sy": in_sy,
                      "mo_ts": mo_ts, "mo_yaw": mo_yaw, "mo_pitch": mo_pitch}
        save_cocapture(out, s, raw_reports=reports, ts_us=ts_us, l9_streams=l9_streams)
        motion_std = float(max(np.std(mo_yaw) if mo_yaw else 0.0,
                               np.std(mo_pitch) if mo_pitch else 0.0))
        res = {"path": out, "player": s.player, "l9_reliable": s.l9_reliable,
               "l9_coupling": round(s.l9_coupling, 4), "l4_present": s.l4_vec is not None,
               "camera_motion_std": round(motion_std, 4),
               "n_hid": s.n_hid, "n_frames": s.n_frames}
        if motion_std < 0.5:
            res["warning"] = ("CAMERA STATIC (no on-screen motion) — the moving game must be "
                              "VISIBLE in the capture region. Bring Remote Play to the front "
                              "(don't let the terminal/another window cover the screen center).")
        return res


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="L9 F1 co-capture + F3 readiness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("capture", help="record co-capture session(s) for one player")
    pc.add_argument("--player", required=True)
    pc.add_argument("--count", type=int, default=1, help="number of back-to-back sessions")
    pc.add_argument("--duration", type=float, default=60.0)
    pc.add_argument("--region", nargs=4, type=int, default=[640, 360, 1280, 720])
    pc.add_argument("--backend", default="mss", choices=("auto", "wgc", "bettercam", "dxcam", "mss"),
                    help="capture backend; use 'wgc' for 60fps (sharper lag) once windows-capture is installed")
    pc.add_argument("--out-dir", default="cocapture_l9")
    pr = sub.add_parser("readiness", help="autonomously check if F3 needs more players")
    pr.add_argument("--corpus-dir", default="cocapture_l9")
    pr.add_argument("--min-per-player", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "capture":
        cfg = CoCaptureConfig(player=a.player, duration_s=a.duration,
                              region=tuple(a.region), backend=a.backend, out_dir=a.out_dir)
        rec = CoCaptureRecorder(cfg)
        for k in range(a.count):
            r = rec.record_once()
            print(f"[{k + 1}/{a.count}] {a.player}: {r['path']} "
                  f"(l9_reliable={r['l9_reliable']}, motion_std={r['camera_motion_std']}, "
                  f"l4={r['l4_present']})")
            if "warning" in r:
                print(f"    !! {r['warning']}")
                if k == 0:
                    print("    Stopping the batch — fix the capture window, then re-run.")
                    break
        return 0
    if a.cmd == "readiness":
        print(json.dumps(fusion_readiness(a.corpus_dir, a.min_per_player), indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
