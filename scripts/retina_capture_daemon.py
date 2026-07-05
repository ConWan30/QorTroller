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
    # U1 (design doc §2.6): mint the shared session identifier ONCE here — the same {label}_{stamp} string
    # that names the log/corpus/archive — and thread it to the bridge child so PITL co-capture meta carries
    # the join key the KAS record + archive manifest also carry. Internal wiring only; no default change.
    try:
        from l9_presence.session_identity import (ENV_SESSION_DISPLAY, ENV_SESSION_ID,
                                                  derive_session_id, session_display)
        env[ENV_SESSION_ID] = derive_session_id(a.label, stamp)
        env[ENV_SESSION_DISPLAY] = session_display(a.label, stamp)
    except Exception:  # noqa: BLE001 — the join key is additive; its absence never blocks capture
        pass
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
    if getattr(a, "session_anchor", False):              # per-session feed-cut anchor auto-generation (killer-slot)
        env["RETINA_SESSION_ANCHOR_ENABLED"] = "true"
    if getattr(a, "ocr_bootstrap", False):               # OCR-verified bootstrap catch (rendering-independent)
        env["RETINA_OCR_BOOTSTRAP_ENABLED"] = "true"
    if getattr(a, "dense_classify", False):              # W.2 dense-tail: tighter in-window classify cadence
        env["RETINA_DENSE_CLASSIFY_ENABLED"] = "true"
    if getattr(a, "classify_burst", False):              # Phase C: R2-onset-triggered high-frequency polling
        env["RETINA_CLASSIFY_BURST_ENABLED"] = "true"
    if getattr(a, "hid_events", False):                  # HID lobe: device-clock R2-onset stream (dual-lobe KAS)
        env["RETINA_HID_EVENTS_ENABLED"] = "true"
    if getattr(a, "death_window", False):                # LOOP 2: post-death stick-activity corpus (no verdict)
        env["RETINA_DEATH_WINDOW_ENABLED"] = "true"
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


def _issue_posp(label: str, stamp, kas_rec: dict) -> None:
    """U2b: issue the PoSP reference-and-bind record at session close, after KAS issuance.

    Surfaces collected: KAS (always present when called), NQPV co-capture rows from bridge DB
    (fail-open if DB unreachable — new sessions won't have rows yet if this is the first run after U2a),
    tier-1 archive manifest (written by _archive_ring). Writes audits/posp_record_<label>_<date>.json.

    REFERENCE-AND-BIND design (D-CERT-5.1 hybrid b→a): no new commitment / domain tag / FROZEN-v1
    family. Integrity derives entirely from the commitments PoSP references (KAS commitment, PoAC hashes,
    archive SHA-256s). Never mistake this for an eleventh FROZEN-v1 family.
    """
    import sqlite3
    from datetime import date
    from l9_presence.posp import build_posp

    sid = kas_rec.get("session_id")

    # --- NQPV fusion rows from bridge DB (fail-open) ---
    # DB_PATH may be set in bridge/.env (e.g. presence_lean.db) but not in the daemon process
    # environment. Fall back to bridge/.env so _issue_posp() finds the same DB the bridge wrote to.
    fusion_rows: list = []
    try:
        _db_path_from_env = os.environ.get("DB_PATH")
        if not _db_path_from_env:
            _dot_env = _REPO / "bridge" / ".env"
            if _dot_env.exists():
                for _line in _dot_env.read_text(encoding="utf-8").splitlines():
                    _line = _line.strip()
                    if _line.startswith("DB_PATH="):
                        _db_path_from_env = _line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        db_path = _db_path_from_env or str(Path.home() / ".vapi" / "bridge.db")
        if Path(db_path).exists():
            with sqlite3.connect(db_path, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                if sid:
                    rows = conn.execute(
                        "SELECT * FROM nqpv_cocapture_log WHERE session_id = ? "
                        "ORDER BY created_at DESC LIMIT 500",
                        (sid,),
                    ).fetchall()
                    fusion_rows = [dict(r) for r in rows]
        else:
            print(f"[daemon] PoSP: bridge DB not found at {db_path} — fusion rows unavailable")
    except Exception as e:  # noqa: BLE001
        print(f"[daemon] PoSP: DB query failed (non-fatal): {e!r}")

    # --- Tier-1 archive manifest (written by _archive_ring) ---
    archive_manifest = None
    try:
        manifest_path = _REPO / "retina_kf_archive" / f"{label}_{stamp}" / "manifest.json"
        if manifest_path.exists():
            archive_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[daemon] PoSP: manifest read failed (non-fatal): {e!r}")

    # retina_perception_root is the Trio-Retina perception events_root (Phase 3c DA witness path);
    # the KAS events_root is the KAS dual-lobe root (§2.3 — two named, parallel roots).
    rec = build_posp(
        session_id=sid,
        session_display=kas_rec.get("session_display"),
        kas_record=kas_rec,
        fusion_rows=fusion_rows or None,
        archive_manifest=archive_manifest,
        retina_perception_root=None,   # Phase 3c: perception root from retina_controller_embedder path
    )
    out = _REPO / "audits" / f"posp_record_{label}_{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rec.to_json(), encoding="utf-8")
    kas_ok = rec.kas.get("id_verified") if rec.kas else None
    fusion_n = rec.fusion.get("n_id_verified", 0) if rec.fusion else 0
    arch_ok = rec.archive.get("id_verified") if rec.archive else None
    print(f"[daemon] PoSP: {rec.verdict} kas_verified={kas_ok} fusion_rows={fusion_n} "
          f"archive_verified={arch_ok} -> {out.relative_to(_REPO)}")
    if rec.notes:
        for note in rec.notes:
            print(f"[daemon] PoSP NOTE: {note}")


def _archive_ring(label, started_at):
    """R3 fix (2026-07-03, 2nd archive-loss): copy the dense ring into a per-session archive at STOP so the
    NEXT session's captures can't overwrite this session's rendering. The rolling 600-crop ring silently cost
    the g3mp/g3wz2/recut/gatedcut renderings (why the recognition bake-off's B2 was capped at 2-3 families).
    COPY not move (ring stays intact until naturally overwritten); dst is gitignored (retina_kf_archive/).
    Fail-open -> None. Returns (dst, n_copied)."""
    import shutil
    ring = _REPO / os.environ.get("RETINA_KILLFEED_CAPTURE_DIR", "retina_kf_crops")
    crops = sorted(ring.glob("panel_*.png")) if ring.exists() else []
    if not crops:
        return None
    dst = _REPO / "retina_kf_archive" / f"{label}_{started_at}"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    copied = []
    for c in crops:
        try:
            shutil.copy2(c, dst / c.name)
            copied.append(c.name)
            n += 1
        except Exception:  # noqa: BLE001 — per-file best-effort; never break stop
            pass
    # U1 tier-1 standing manifest (design doc §2.6 sink iii; generalizes the 2026-07-04 one-off archive
    # script into the daemon's standing stop behavior). Carries the SAME session_id the KAS record and the
    # PITL co-capture meta carry — the three-artifact join. Per-file SHA-256 so evidence survives
    # rolling-buffer eviction verifiably. Fail-open: a manifest failure never breaks the stop path.
    try:
        import hashlib
        import time as _time
        from l9_presence.session_identity import derive_session_id, session_display

        def _sha(p):
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        manifest = {"schema": "qortroller-session-archive-v1",
                    "session_id": derive_session_id(label, started_at),
                    "session_display": session_display(label, started_at),
                    "label": label, "started_at": int(started_at),
                    "archived_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
                    "count": n,
                    "files": [{"file": name, "sha256": _sha(dst / name)} for name in copied]}
        (dst / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return dst, n


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
    # R3 ring-archival (DEFAULT-ON; --no-archive-ring to skip): preserve this session's rendering before the
    # next session overwrites the rolling ring. Fail-open — archival never breaks the stop path.
    if not getattr(a, "no_archive_ring", False):
        try:
            res = _archive_ring(label, st["started_at"])
            if res is None:
                print("[daemon] ring-archive: ring empty — nothing to archive")
            else:
                dst, n = res
                print(f"[daemon] ring-archive: copied {n} crops -> {dst.relative_to(_REPO)}")
        except Exception as e:  # noqa: BLE001
            print(f"[daemon] ring-archive failed (non-fatal): {e!r}")
    # Increment 2 step 5 (G4 green 2026-07-03): session-close KAS certificate issuance — EXPLICIT opt-in
    # (--kas), default-OFF. Issues the Kill-Authorship Session Record over THIS session's log + composites
    # (fail-closed enum; a bad session honestly reads INSUFFICIENT_KILLS / HYGIENE_FAIL, never a false cert).
    _kas_rec = None
    if getattr(a, "kas", False):
        try:
            from issue_kas_records import issue_record_for_label
            _kas_rec = issue_record_for_label(label)
            if _kas_rec is None:
                print("[daemon] KAS: no issuable record (log/span unusable)")
            else:
                print(f"[daemon] KAS: {_kas_rec['verdict']} authored={_kas_rec['authored_kills']} "
                      f"commit={_kas_rec['commitment'][:16]} -> {_kas_rec['_path']}")
        except Exception as e:  # noqa: BLE001 — issuance must never break the stop path
            print(f"[daemon] KAS issuance failed (non-fatal): {e!r}")
    # U2b: PoSP reference-and-bind record — only when KAS issued and rec is available (fail-open).
    # Writes audits/posp_record_<label>_<date>.json with verdict SYNCHRONIZED/PARTIAL/UNVERIFIABLE.
    if _kas_rec is not None:
        try:
            _issue_posp(label, st["started_at"], dict(_kas_rec))
        except Exception as e:  # noqa: BLE001
            print(f"[daemon] PoSP issuance failed (non-fatal): {e!r}")
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
    s.add_argument("--session-anchor", action="store_true",
                   help="per-session feed-cut anchor auto-gen (killer-slot; bootstrap->cut->promote@0.66)")
    s.add_argument("--ocr-bootstrap", action="store_true",
                   help="OCR-verified bootstrap catch (rendering-independent; needs --session-anchor + tesseract)")
    s.add_argument("--dense-classify", action="store_true",
                   help="W.2 dense-tail: tighter in-window classify cadence (still R2-gated; fixes sparse-sampling starvation)")
    s.add_argument("--classify-burst", action="store_true",
                   help="Phase C: R2-onset-triggered high-frequency classify polling (independent of "
                        "--dense-classify's min_gap; fixes the ~1Hz _session_loop cadence ceiling directly)")
    s.add_argument("--hid-events", action="store_true",
                   help="HID lobe: device-clock R2-onset stream -> retina_hid_events.jsonl (dual-lobe KAS root + cross-lobe latency; needs --killfeed-inline)")
    s.add_argument("--death-window", action="store_true",
                   help="LOOP 2: post-death stick-activity corpus (consumes loop-1 victim-slot; no verdict)")
    s.add_argument("--port", type=int, default=8080); s.add_argument("--health-timeout", type=int, default=180)
    st = sub.add_parser("status"); st.set_defaults(fn=cmd_status)
    sp = sub.add_parser("stop"); sp.set_defaults(fn=cmd_stop); sp.add_argument("--label", default=None)
    sp.add_argument("--kas", action="store_true",
                    help="issue the Kill-Authorship Session Record at close (G4-green; default-OFF)")
    sp.add_argument("--no-archive-ring", action="store_true",
                    help="skip R3 ring-archival (default archives the dense ring to retina_kf_archive/ at stop)")
    c = sub.add_parser("calibrate"); c.set_defaults(fn=cmd_calibrate)
    c.add_argument("--genuine", required=True); c.add_argument("--forged", required=True)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
