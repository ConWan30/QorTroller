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


def make_stick_parser(rx_offset: int, ry_offset: int) -> StickParser:
    """Parser for explicit right-stick byte offsets (from l9_presence.hid_probe)."""
    def _parse(report: bytes) -> Tuple[float, float]:
        if len(report) > max(rx_offset, ry_offset):
            return float(report[rx_offset]), float(report[ry_offset])
        return 128.0, 128.0
    return _parse


def _default_stick_parser() -> StickParser:
    """Documented USB fallback for the standard DualSense input report (id 0x01):
    right stick X=byte3, Y=byte4 (0-255). VALIDATE with l9_presence.hid_probe first —
    the Edge's vendor 'full' report and BT use different offsets."""
    return make_stick_parser(3, 4)


@dataclass
class SessionData:
    in_ts: np.ndarray
    in_sx: np.ndarray
    in_sy: np.ndarray
    mo_ts: np.ndarray
    mo_yaw: np.ndarray
    mo_pitch: np.ndarray
    label: str
    in_fire: Optional[np.ndarray] = None   # R2/fire analog per input sample (0-255); enables engagement-locked analysis


def record_session(out_path: str, duration_s: float = 60.0, label: str = "human",
                   region: Optional[Region] = None,
                   stick_parser: Optional[StickParser] = None,
                   backend: str = "mss", fire_offset: int = 6) -> str:
    """Record one labeled probe session to .npz. Hardware + Remote Play required.

    backend defaults to "mss": on Python 3.13 the DXGI backends (dxcam/bettercam)
    crash in comtypes COM-release, and mss captures Remote Play's overlay surface
    non-black anyway (confirmed on the reference rig). Crop with `region` for speed
    (full monitor ~4fps; a 640x360 crop ~24fps via mss)."""
    if not opencv_available():
        raise RuntimeError("opencv-python required (pip install opencv-python)")
    try:
        import hid  # hidapi
    except Exception as exc:
        raise RuntimeError(f"hidapi required (pip install hidapi): {exc}")

    parse = stick_parser or _default_stick_parser()
    cap = ScreenCapturer(region=region, backend=backend)
    mx = MotionExtractor()
    dev = hid.device(); dev.open(DUALSENSE_VID, DUALSENSE_EDGE_PID); dev.set_nonblocking(True)

    in_ts, in_sx, in_sy, in_fire = [], [], [], []
    mo_ts, mo_yaw, mo_pitch = [], [], []
    t0 = time.time()
    try:
        while time.time() - t0 < duration_s:
            now_ms = (time.time() - t0) * 1000.0
            rep = dev.read(64)
            if rep:
                rb = bytes(rep)
                sx, sy = parse(rb)
                fire = float(rb[fire_offset]) if len(rb) > fire_offset else 0.0
                in_ts.append(now_ms); in_sx.append(sx); in_sy.append(sy); in_fire.append(fire)
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
             in_fire=np.array(in_fire),
             mo_ts=np.array(mo_ts), mo_yaw=np.array(mo_yaw), mo_pitch=np.array(mo_pitch),
             label=label)
    return out_path


def load_session(path: str) -> SessionData:
    d = np.load(path, allow_pickle=True)
    fire = d["in_fire"] if "in_fire" in d.files else None  # back-compat: pre-fire sessions
    return SessionData(d["in_ts"], d["in_sx"], d["in_sy"],
                       d["mo_ts"], d["mo_yaw"], d["mo_pitch"], str(d["label"]), fire)


def analyze_session_data(s: SessionData) -> dict:
    """Score an in-memory SessionData through the coupling oracle. Returns a result
    dict with coupling_score, decoupled_energy, negative_control, and the margin."""
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


def analyze_session(path: str) -> dict:
    """Load a recorded .npz session and score it (see analyze_session_data)."""
    return analyze_session_data(load_session(path))


def engagement_locked_residual(s: SessionData, fire_threshold: float = 64.0) -> dict:
    """Residual (unexplained-aim) energy DURING fire vs the rest of the session.

    A real aimbot's unexplained corrections cluster at engagement moments (the
    trigger pull), so its residual spikes when firing; a human aims with their own
    stick whether or not they're firing, so fire ~ rest. This catches the partial-
    assist case the global residual averages away. Requires a session recorded with
    the fire (R2) stream. Metric: per-window decoupled-energy fraction; fire_minus_rest
    > 0 is the engagement-locked aimbot signature."""
    fire = s.in_fire
    if fire is None or np.asarray(fire).size < 4:
        return {"status": "no_fire_data"}
    o = _oracle_for(s.in_ts, s.in_sx, s.in_sy, s.mo_ts, s.mo_yaw, s.mo_pitch)
    feat = o.extract_features()
    if feat is None:
        return {"status": "insufficient_aim_activity"}
    in_ts = np.asarray(s.in_ts, float)
    mo_ts = np.asarray(s.mo_ts, float)
    t0, t1 = max(in_ts[0], mo_ts[0]), min(in_ts[-1], mo_ts[-1])
    grid = np.arange(t0, t1, 1000.0 / C.COMMON_RATE_HZ)
    axis_x = s.in_sx if feat.dominant_axis == "yaw" else s.in_sy
    axis_cam = s.mo_yaw if feat.dominant_axis == "yaw" else s.mo_pitch
    stick = np.asarray(axis_x, float)
    stick = stick - np.median(stick)
    pred_g = C.resample_uniform(in_ts, C.aim_response(stick), grid)
    meas_g = C.resample_uniform(mo_ts, np.asarray(axis_cam, float), grid)
    fire_g = C.resample_uniform(in_ts, np.asarray(fire, float), grid)
    lag = int(round(feat.lag_ms / 1000.0 * C.COMMON_RATE_HZ))
    resid, meas_al = C.residual_series(pred_g, meas_g, lag)
    fire_al = fire_g[: resid.size]  # input-time aligned with the residual (see residual_series)
    mask = fire_al > fire_threshold
    if int(mask.sum()) < 5 or int((~mask).sum()) < 5:
        return {"status": "too_few_fire_frames", "fire_frames": int(mask.sum())}

    def _frac(sel) -> float:
        v = float(meas_al[sel].var())
        return float(resid[sel].var() / v) if v > 1e-12 else 0.0

    fire_res, rest_res = _frac(mask), _frac(~mask)
    return {
        "dominant_axis": feat.dominant_axis,
        "lag_ms": feat.lag_ms,
        "fire_frames": int(mask.sum()),
        "rest_frames": int((~mask).sum()),
        "residual_energy_fire": fire_res,
        "residual_energy_rest": rest_res,
        "fire_minus_rest": fire_res - rest_res,
    }


def engagement_locked_session(path: str) -> dict:
    return engagement_locked_residual(load_session(path))


def compare_sessions(paths: list[str]) -> dict:
    """Analyze many sessions and contrast coupling/residual by label — the GO/NO-GO.

    Returns per-label means and the separation between human and scripted coupling.
    A real signal: human coupling_score distribution clearly above scripted, with
    each label's negative_control collapsed near 0."""
    rows = []
    for p in paths:
        try:
            r = analyze_session(p)
        except Exception as exc:  # keep going; report the bad file
            r = {"label": "?", "status": f"error: {exc}", "path": p}
        r["path"] = p
        rows.append(r)

    def _by(label: str, key: str) -> list[float]:
        return [r[key] for r in rows if r.get("label") == label and key in r
                and isinstance(r.get(key), (int, float))]

    out: dict = {"n_sessions": len(rows), "rows": rows, "labels": {}}
    for label in sorted({r.get("label", "?") for r in rows}):
        cs = _by(label, "coupling_score")
        de = _by(label, "decoupled_energy")
        nc = _by(label, "negative_control")
        out["labels"][label] = {
            "n": len(cs),
            "coupling_mean": float(np.mean(cs)) if cs else None,
            "coupling_std": float(np.std(cs)) if cs else None,
            "decoupled_mean": float(np.mean(de)) if de else None,
            "neg_control_mean": float(np.mean(nc)) if nc else None,
        }
    h = out["labels"].get("human", {}).get("coupling_mean")
    s = out["labels"].get("scripted", {}).get("coupling_mean")
    out["coupling_separation"] = (h - s) if (h is not None and s is not None) else None
    return out


def _oracle_for(in_ts, in_sx, in_sy, mo_ts, mo_yaw, mo_pitch):
    o = C.InputOutputCouplingOracle()
    for t, x, y in zip(in_ts, in_sx, in_sy):
        o.push_input(float(t), float(x), float(y))
    for t, yaw, pitch in zip(mo_ts, mo_yaw, mo_pitch):
        o.push_frame_motion(float(t), float(yaw), float(pitch))
    return o


def decoupled_control(paths: list[str]) -> dict:
    """Cross-session decoupled control — a real-data aimbot/injection analog.

    For each session, score the TRUE pair (its own input + its own camera) and a
    DECOUPLED pair (its camera + a DIFFERENT session's input). Decoupled = on-screen
    motion that real human input did NOT cause = the injection signature. If the
    probe discriminates, decoupled coupling collapses toward the negative control
    while true coupling stays elevated. Stronger than the in-session shuffle because
    the mismatched input is real, structured human aiming."""
    sessions = [load_session(p) for p in paths]
    n = len(sessions)
    if n < 2:
        return {"status": "need >= 2 sessions for a cross-session control"}
    true_scores, dec_scores = [], []
    for i, s in enumerate(sessions):
        ft = _oracle_for(s.in_ts, s.in_sx, s.in_sy, s.mo_ts, s.mo_yaw, s.mo_pitch).extract_features()
        if ft is not None:
            true_scores.append(ft.coupling_score)
        other = sessions[(i + 1) % n]  # this camera + next session's input
        fd = _oracle_for(other.in_ts, other.in_sx, other.in_sy,
                         s.mo_ts, s.mo_yaw, s.mo_pitch).extract_features()
        if fd is not None:
            dec_scores.append(fd.coupling_score)
    tmean = float(np.mean(true_scores)) if true_scores else None
    dmean = float(np.mean(dec_scores)) if dec_scores else None
    return {
        "n_sessions": n,
        "true_coupling_mean": tmean,
        "true_coupling_std": float(np.std(true_scores)) if true_scores else None,
        "decoupled_coupling_mean": dmean,
        "decoupled_coupling_std": float(np.std(dec_scores)) if dec_scores else None,
        "separation": (tmean - dmean) if (tmean is not None and dmean is not None) else None,
    }


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="L9 session recorder / analyzer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("record", help="record one labeled session to .npz")
    pr.add_argument("--out", required=True)
    pr.add_argument("--label", default="human", choices=("human", "scripted"))
    pr.add_argument("--duration", type=float, default=60.0)
    pr.add_argument("--rx", type=int, default=3, help="right-stick X byte offset (see hid_probe)")
    pr.add_argument("--ry", type=int, default=4, help="right-stick Y byte offset (see hid_probe)")
    pr.add_argument("--region", nargs=4, type=int, metavar=("L", "T", "R", "B"), default=None)
    pr.add_argument("--backend", default="mss", choices=("auto", "bettercam", "dxcam", "mss"))
    pr.add_argument("--fire-offset", type=int, default=6, help="R2/fire byte offset (standard report=6)")

    pa = sub.add_parser("analyze", help="analyze one recorded session")
    pa.add_argument("path")

    pe = sub.add_parser("engagement", help="engagement-locked residual (needs fire stream)")
    pe.add_argument("path")
    pe.add_argument("--fire-threshold", type=float, default=64.0)

    pc = sub.add_parser("compare", help="contrast human vs scripted across sessions")
    pc.add_argument("paths", nargs="+")

    pd = sub.add_parser("decouple-control",
                        help="cross-session decoupled control (real-data aimbot analog)")
    pd.add_argument("paths", nargs="+")

    a = ap.parse_args()
    if a.cmd == "record":
        region = tuple(a.region) if a.region else None
        out = record_session(a.out, duration_s=a.duration, label=a.label, region=region,
                             stick_parser=make_stick_parser(a.rx, a.ry), backend=a.backend,
                             fire_offset=a.fire_offset)
        print(f"recorded {a.label} session -> {out}")
        return 0
    if a.cmd == "analyze":
        import json
        print(json.dumps(analyze_session(a.path), indent=2, default=str))
        return 0
    if a.cmd == "engagement":
        import json
        print(json.dumps(engagement_locked_residual(load_session(a.path), a.fire_threshold),
                         indent=2, default=str))
        return 0
    if a.cmd == "compare":
        import json
        res = compare_sessions(a.paths)
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2, default=str))
        return 0
    if a.cmd == "decouple-control":
        import json
        print(json.dumps(decoupled_control(a.paths), indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
