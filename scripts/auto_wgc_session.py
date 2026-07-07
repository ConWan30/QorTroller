"""Automated dev-cert WGC capture session (background-friendly; the operator just plays).

Starts the bridge with the dev-cert + retina capture env, waits for /health, captures for a play window
while the operator plays (the bridge logs `RGC diag:` lines with the per-channel coupling lags), then
harvests them into a calibration corpus + prints a SUMMARY and stops the bridge. Run in the background:
the operator plays, and the run self-completes (no need to message back).

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


def _health_ok(url: str, timeout: int = 3) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:   # noqa: S310 (localhost)
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="automated dev-cert WGC capture session")
    ap.add_argument("--label", default="genuine", help="genuine | forged (spectate)")
    ap.add_argument("--minutes", type=float, default=8.0, help="play/capture window length")
    ap.add_argument("--health-timeout", type=int, default=180, help="max s to wait for bridge /health")
    ap.add_argument("--port", type=int, default=8080, help="HTTP_PORT to bind + health-check (config default 8080)")
    ap.add_argument("--monitor", type=int, default=1, help="display index for WGC capture (1=laptop; monitor "
                    "mode is what works — window 'Remote Play' is usually not a real window title)")
    a = ap.parse_args()

    stamp = int(time.time())
    log_path = _REPO / f"wgc_session_{a.label}_{stamp}.log"
    out_jsonl = _REPO / f"{a.label}_{stamp}.jsonl"

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(_REPO / "bridge"), str(_REPO), env.get("PYTHONPATH", "")])
    env.update({
        "RETINA_GAME_CAPTURE_ENABLED": "true",
        "RETINA_GAME_CAPTURE_MONITOR": str(a.monitor),   # MONITOR capture (continuous start()) — window mode
        "RETINA_GAME_CAPTURE_WINDOW": "Remote Play",     #   fails ('Remote Play' is not a real window title)
        "DEVELOPER_SELF_CERT_ENABLED": "true",
        "PRESENCE_LEAN_MODE": "true",                     # gate the agent fleet -> less CPU/observer-effect
        "NQPV_COCAPTURE_ENABLED": "true",                # REQUIRED with lean mode, else coupling=None
        "GRIND_MODE": "false",
        "CHAIN_SUBMISSION_PAUSED": "true",               # kill-switch ON — nothing goes on-chain
        "HTTP_PORT": str(a.port),                        # bind the port we health-check (avoid 8000/8080 skew)
    })

    print(f"[auto] starting bridge (dev-cert/lean) -> {log_path.name}", flush=True)
    lf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "bridge.vapi_bridge.main"],
                            cwd=str(_REPO), env=env, stdout=lf, stderr=subprocess.STDOUT)
    # probe the bound port first, with 8080/8000 fallbacks in case .env forces a different one
    seen: set = set()
    cand_ports = [p for p in (a.port, 8080, 8000) if not (p in seen or seen.add(p))]
    try:
        t0 = time.time()
        ready = False
        while time.time() - t0 < a.health_timeout:
            for p in cand_ports:
                if _health_ok(f"http://localhost:{p}/health"):
                    ready = True
                    a.port = p
                    break
            if ready:
                break
            if proc.poll() is not None:
                print("[auto] FAIL: bridge exited during startup — see log", flush=True)
                break
            time.sleep(3)
        if not ready:
            print("[auto] FAIL: bridge not healthy in time; aborting (do not bother playing)", flush=True)
            return 1
        print(f"[auto] BRIDGE READY at {time.strftime('%H:%M:%S')} — PLAY NOW ({a.label}); "
              f"capturing {a.minutes:.0f} min", flush=True)
        time.sleep(a.minutes * 60.0)
        print(f"[auto] capture window closed at {time.strftime('%H:%M:%S')}; harvesting", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        lf.close()

    # harvest the RGC-diag log -> calibration corpus + summary
    import capture_latency_calibration as cap
    from l9_presence.cross_channel_latency import assess_latency_agreement

    text = log_path.read_text(encoding="utf-8", errors="replace")
    diags = cap.parse_rgc_diag(text)
    sessions = []
    with open(out_jsonl, "w", encoding="utf-8") as o:
        for d in diags:
            ch = cap.sample_to_channels(d)
            if len(ch) >= 2:
                o.write(json.dumps([c.__dict__ for c in ch]) + "\n")
                sessions.append(ch)

    ts_src: dict = {}
    for d in diags:
        k = d.get("ts_source")
        ts_src[k] = ts_src.get(k, 0) + 1
    verdicts: dict = {}
    for s in sessions:
        v = assess_latency_agreement(s).verdict.value
        verdicts[v] = verdicts.get(v, 0) + 1
    summary = {
        "label": a.label,
        "rgc_diag_samples": len(diags),
        "calibration_sessions_ge2ch": len(sessions),
        "ts_source_counts": ts_src,                 # want 'timespan' dominant (the #1 enhancement live)
        "agreement_verdicts": verdicts,             # PRESENT_COHERENT vs INCOHERENT vs INSUFFICIENT
        "corpus": out_jsonl.name,
        "log": log_path.name,
    }
    print("[auto] SUMMARY: " + json.dumps(summary, indent=2), flush=True)
    if len(diags) == 0:
        print("[auto] NOTE: 0 RGC diag samples — controller connected? Remote Play visible? retina capture on?",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
