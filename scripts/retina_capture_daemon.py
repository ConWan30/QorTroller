"""Detached retina capture daemon — long, disconnect-surviving dev-cert calibration sessions.

The bridge captures LOCALLY and is started DETACHED, so it survives this shell exiting AND the remote-access
view dropping when the operator fullscreens the game. Dense coupling sampling (RETINA_DIAG_EVERY) makes a few
minutes of play yield enough cross-channel samples to actually calibrate.

  start :  launch the bridge detached (dense sampling) + wait for /health + print CAPTURE LIVE, then EXIT
           (the bridge keeps running). Play as long as you want; your link to me can drop — capture stays up.
  status:  is it up + how many RGC-diag samples captured so far.
  stop  :  harvest the log into a <label> calibration corpus + SUMMARY + kill the bridge.
  calibrate: fit tau_lag from a genuine + a forged corpus.

Advisory presence calibration only. CHAIN_SUBMISSION_PAUSED stays on; no chain / IOTX / FROZEN-v1 / PoAC.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO / "scripts"))
_STATE = _REPO / "retina_daemon.state.json"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0   # CREATE_NO_WINDOW — never pop a console window


def _health_ok(port: int, timeout: int = 3) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=timeout) as r:  # noqa: S310
            return r.status == 200
    except Exception:
        return False


def _ready_port(cand_ports, timeout: int = 2):
    for p in cand_ports:
        if _health_ok(p, timeout):
            return p
    return None


def _kill_tree(pid: int) -> None:
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True,
                           creationflags=_NO_WINDOW)
        else:
            os.kill(pid, 15)
    except Exception:
        pass


def cmd_start(a) -> int:
    if _STATE.exists():
        st = json.loads(_STATE.read_text(encoding="utf-8"))
        if _health_ok(st.get("port", a.port)):
            print(f"[daemon] already running (pid={st.get('pid')}, port={st.get('port')}). Run 'stop' first.")
            return 1
    stamp = int(time.time())
    log_path = _REPO / f"retina_daemon_{a.label}_{stamp}.log"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(_REPO / "bridge"), str(_REPO), env.get("PYTHONPATH", "")])
    env.update({
        "RETINA_GAME_CAPTURE_ENABLED": "true",
        "RETINA_GAME_CAPTURE_MONITOR": str(a.monitor),   # monitor capture (works for fullscreen Remote Play)
        "RETINA_CAPTURE_BURST_ENABLED": "false",         # CONTINUOUS capture (start() called) — guaranteed
        "RETINA_CAPTURE_MIN_INTERVAL_MS": str(a.min_interval_ms),  # throttle (~30fps) to limit observer-effect lag
        "RETINA_DIAG_EVERY": str(a.diag_every),          # dense sampling -> enough calibration samples
        "DEVELOPER_SELF_CERT_ENABLED": "true",
        "PRESENCE_LEAN_MODE": "true",
        "NQPV_COCAPTURE_ENABLED": "true",                # REQUIRED with lean mode, else coupling=None
        "GRIND_MODE": "false",
        "CHAIN_SUBMISSION_PAUSED": "true",               # kill-switch ON
        "HTTP_PORT": str(a.port),
    })
    if getattr(a, "killfeed", False):                    # kill-feed authorship (anti-spectate differentiator)
        env["RETINA_KILLFEED_ENABLED"] = "true"
        if a.killfeed_roi:
            env["RETINA_KILLFEED_ROI"] = a.killfeed_roi
    if getattr(a, "capture", False):                     # dense left-panel crop capture (calibration corpus)
        env["RETINA_KILLFEED_CAPTURE_ENABLED"] = "true"
        if getattr(a, "capture_dir", ""):
            env["RETINA_KILLFEED_CAPTURE_DIR"] = a.capture_dir
    if getattr(a, "killfeed_inline", False):             # R2-gated INLINE authorship classification (live)
        env["RETINA_KILLFEED_INLINE_ENABLED"] = "true"
    lf = open(log_path, "w", encoding="utf-8")
    # DETACHED so the bridge survives this process exiting AND the remote-access drop.
    if sys.platform == "win32":
        flags = 0x00000200 | _NO_WINDOW                 # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW (no popup)
        proc = subprocess.Popen([sys.executable, "-m", "bridge.vapi_bridge.main"], cwd=str(_REPO), env=env,
                                stdout=lf, stderr=subprocess.STDOUT, creationflags=flags, close_fds=True)
    else:
        proc = subprocess.Popen([sys.executable, "-m", "bridge.vapi_bridge.main"], cwd=str(_REPO), env=env,
                                stdout=lf, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    cand = [a.port, 8080, 8000]
    print(f"[daemon] bridge starting detached (pid={proc.pid}) -> {log_path.name}; waiting for /health ...",
          flush=True)
    t0 = time.time()
    port = None
    while time.time() - t0 < a.health_timeout:
        port = _ready_port(cand)
        if port:
            break
        if proc.poll() is not None:
            print("[daemon] FAIL: bridge exited during startup — see log")
            return 1
        time.sleep(3)
    if not port:
        print("[daemon] FAIL: bridge not healthy in time; killing")
        _kill_tree(proc.pid)
        return 1
    _STATE.write_text(json.dumps({
        "pid": proc.pid, "port": port, "log": log_path.name, "label": a.label,
        "monitor": a.monitor, "diag_every": a.diag_every, "started_at": stamp,
    }, indent=2), encoding="utf-8")
    print(f"[daemon] CAPTURE LIVE — pid={proc.pid} port={port} monitor={a.monitor} "
          f"diag_every={a.diag_every} log={log_path.name}")
    print("[daemon] Play as long as you want (your link to me can drop — capture stays up). "
          "Run 'retina_capture_daemon.py stop' when done.")
    return 0


def _read_state():
    if not _STATE.exists():
        print("[daemon] no active session (no state file).")
        return None
    return json.loads(_STATE.read_text(encoding="utf-8"))


def cmd_status(a) -> int:
    st = _read_state()
    if st is None:
        return 1
    up = _health_ok(st["port"])
    log = _REPO / st["log"]
    n = 0
    if log.exists():
        n = sum(1 for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if "RGC diag:" in ln)
    print(json.dumps({"up": up, "pid": st["pid"], "port": st["port"], "label": st["label"],
                      "rgc_diag_samples": n, "log": st["log"]}, indent=2))
    return 0


def cmd_stop(a) -> int:
    st = _read_state()
    if st is None:
        return 1
    import capture_latency_calibration as cap
    from l9_presence.cross_channel_latency import assess_latency_agreement
    log = _REPO / st["log"]
    label = a.label or st["label"]
    out = _REPO / f"{label}_{st['started_at']}.jsonl"
    diags = cap.parse_rgc_diag(log.read_text(encoding="utf-8", errors="replace")) if log.exists() else []
    sessions = []
    with open(out, "w", encoding="utf-8") as o:
        for d in diags:
            ch = cap.sample_to_channels(d)
            if len(ch) >= 2:
                o.write(json.dumps([c.__dict__ for c in ch]) + "\n")
                sessions.append(ch)
    ts_src, verdicts = {}, {}
    for d in diags:
        ts_src[d.get("ts_source")] = ts_src.get(d.get("ts_source"), 0) + 1
    for s in sessions:
        v = assess_latency_agreement(s).verdict.value
        verdicts[v] = verdicts.get(v, 0) + 1
    _kill_tree(st["pid"])
    _STATE.unlink(missing_ok=True)
    print("[daemon] STOPPED + harvested. SUMMARY: " + json.dumps({
        "label": label, "rgc_diag_samples": len(diags), "calibration_sessions_ge2ch": len(sessions),
        "ts_source_counts": ts_src, "agreement_verdicts": verdicts, "corpus": out.name,
    }, indent=2))
    if len(sessions) < 10:
        print(f"[daemon] NOTE: {len(sessions)} usable sessions (<10/class floor) — play longer next time "
              "or lower --diag-every.")
    return 0


def cmd_calibrate(a) -> int:
    import capture_latency_calibration as cap
    from l9_presence.cross_channel_latency import calibrate_tau_lag
    res = calibrate_tau_lag(cap.load_sessions(a.genuine), cap.load_sessions(a.forged))
    print(json.dumps(res.to_dict(), indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="detached retina capture daemon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.set_defaults(fn=cmd_start)
    s.add_argument("--label", default="genuine"); s.add_argument("--monitor", type=int, default=1)
    s.add_argument("--diag-every", type=int, default=4, help="emit RGC diag every N records (dense=lower)")
    s.add_argument("--min-interval-ms", type=int, default=33, help="WGC capture rate cap (ms); 33=~30fps, "
                   "limits the observer-effect lag of continuous capture")
    s.add_argument("--killfeed", action="store_true", help="enable kill-feed authorship OCR (needs tesseract)")
    s.add_argument("--killfeed-roi", default="", help="fractional 'fx,fy,fw,fh' kill-feed ROI (default top-right)")
    s.add_argument("--capture", action="store_true",
                   help="dense left-panel (feed+roster) crop capture -> calibration corpus")
    s.add_argument("--capture-dir", default="", help="dir for dense panel crops (default retina_kf_crops)")
    s.add_argument("--killfeed-inline", action="store_true",
                   help="R2-gated INLINE authorship classification (live classify_panel + near-margin log)")
    s.add_argument("--port", type=int, default=8080); s.add_argument("--health-timeout", type=int, default=180)
    st = sub.add_parser("status"); st.set_defaults(fn=cmd_status)
    sp = sub.add_parser("stop"); sp.set_defaults(fn=cmd_stop); sp.add_argument("--label", default=None)
    c = sub.add_parser("calibrate"); c.set_defaults(fn=cmd_calibrate)
    c.add_argument("--genuine", required=True); c.add_argument("--forged", required=True)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
