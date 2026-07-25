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


def _env_or_bridge_dotenv(key: str) -> str:
    """Process env wins if the key is present (even empty = explicit override).

    Otherwise read ``bridge/.env`` the same way DB_PATH / TEMPORAL_BEACON_REGISTRY_ADDRESS
    already do. ``cmd_stop`` is a *new* process — it does not inherit whatever the operator
    shell exported at ``start`` time. Without this fallback, RWM_L0_DAEMON_ENABLED=true in
    bridge/.env is silently ignored and _issue_rwm_l0 returns with no log line (observed on
    the first live rig pass cfb_rwm_live_01, 2026-07-24).
    """
    if key in os.environ:
        return os.environ[key].strip().strip('"').strip("'")
    _dot_env = _REPO / "bridge" / ".env"
    if not _dot_env.exists():
        return ""
    prefix = f"{key}="
    try:
        for _line in _dot_env.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line.startswith(prefix):
                return _line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


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
        "RETINA_GAME_CAPTURE_MONITOR": str(a.monitor),   # 0 = window-name capture ("Remote Play"); >=1 = full monitor
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
    if getattr(a, "uvc_index", None) is not None:        # OA-RP-1: direct-HDMI UVC capture card source
        env["RETINA_CAPTURE_SOURCE"] = "uvc"
        env["RETINA_UVC_INDEX"] = str(a.uvc_index)
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
        env["RETINA_KILLFEED_INLINE_ENABLED"] = "true"  # load _inline_monitor + _anchor (structural prereq for all below)
        env["RETINA_SESSION_ANCHOR_ENABLED"] = "true"
        env["RETINA_OCR_BOOTSTRAP_ENABLED"] = "true"    # auto-on with session-anchor: rendering-family-agnostic
        env["RETINA_CLASSIFY_BURST_ENABLED"] = "true"   # auto-on with session-anchor: R2-burst to catch transient kill rows
    if getattr(a, "ocr_bootstrap", False):               # explicit flag is now a no-op (always on with --session-anchor)
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


def _fetch_latest_beacon() -> dict | None:
    """A3-b: read VAPITemporalBeaconRegistry.latestBeacon() (view call — zero IOTX, no
    kill-switch involvement). Registry address from env or bridge/.env. Returns
    {block_number, block_hash, registry, fetched_at} or None (fail-open)."""
    addr = os.environ.get("TEMPORAL_BEACON_REGISTRY_ADDRESS", "")
    if not addr:
        _dot_env = _REPO / "bridge" / ".env"
        if _dot_env.exists():
            for _line in _dot_env.read_text(encoding="utf-8").splitlines():
                _line = _line.strip()
                if _line.startswith("TEMPORAL_BEACON_REGISTRY_ADDRESS="):
                    addr = _line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not addr:
        return None
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider("https://babel-api.testnet.iotex.io", request_kwargs={
        "timeout": 15, "headers": {"User-Agent": "Mozilla/5.0",
                                   "Content-Type": "application/json"}}))
    abi = [{"name": "latestBeacon", "type": "function", "stateMutability": "view",
            "inputs": [], "outputs": [{"name": "blockNumber", "type": "uint256"},
                                      {"name": "blockHash", "type": "bytes32"}]}]
    reg = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
    block_number, block_hash = reg.functions.latestBeacon().call()
    if not block_number:
        return None                                # registry live but nothing anchored yet
    return {"block_number": int(block_number), "block_hash": "0x" + bytes(block_hash).hex(),
            "registry": addr, "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")}


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
    db_path = None
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

    # retina_perception_root is the Trio-Retina perception events_root (§2.3 — two named,
    # parallel roots; the KAS events_root is the KAS dual-lobe root). LUMEN-4b (2026-07-07):
    # rolled AT ISSUANCE from the session's live-captured retina_event_log rows via the
    # SHARED ENGINE (lumen4a_perception_root.roll_perception_root — same computation that
    # produced the M14 candidate 4f335588...). FAIL-OPEN: a session whose perception
    # pipeline didn't run keeps its honest null root — never fabricated.
    retina_root = None
    try:
        from lumen4a_perception_root import roll_perception_root
        _start_s = float(stamp) - 120.0
        _end_s = time.time() + 120.0
        retina_root, _p_stats = roll_perception_root(db_path, _start_s, _end_s)
        if retina_root:
            print(f"[daemon] PoSP: retina_perception_root rolled from "
                  f"{_p_stats['n_rows']} live perception rows "
                  f"({_p_stats['n_events']} events) -> {retina_root[:16]}...")
        elif _p_stats.get("error"):
            print(f"[daemon] PoSP: perception root unavailable (non-fatal): {_p_stats['error']}")
    except Exception as e:  # noqa: BLE001 — perception root must never block PoSP issuance
        print(f"[daemon] PoSP: perception-root roll failed (non-fatal): {e!r}")

    # A3-b (2026-07-08): advisory recency reference — the latest keeper-anchored temporal
    # beacon (Arc 6 registry; the keeper pays the anchoring, we only READ). Fail-open:
    # registry unset / RPC error -> None, never blocks issuance, never fabricated.
    beacon_ref = None
    try:
        beacon_ref = _fetch_latest_beacon()
        if beacon_ref:
            print(f"[daemon] PoSP: temporal beacon ref block={beacon_ref['block_number']} "
                  f"hash={str(beacon_ref['block_hash'])[:16]}...")
    except Exception as e:  # noqa: BLE001
        print(f"[daemon] PoSP: beacon fetch failed (non-fatal): {e!r}")

    rec = build_posp(
        session_id=sid,
        session_display=kas_rec.get("session_display"),
        kas_record=kas_rec,
        fusion_rows=fusion_rows or None,
        archive_manifest=archive_manifest,
        retina_perception_root=retina_root,
        temporal_beacon=beacon_ref,
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

    # T6.6a (default-off, additive): emit the FROZEN VAPI-RETINA-STATE-v3 record from the session's
    # conformant retina.event/0.1 events. Gated by RETINA_STATE_V3_EMIT_ENABLED; fail-open; does NOT
    # modify the PoSP or the M14-anchored LUMEN-4a retina_perception_root (switching to the standard
    # ordered root is a separate operator decision under the dual-consumer regression discipline).
    try:
        from retina_state_v3_emit import maybe_emit_session_v3
        maybe_emit_session_v3(label, stamp, kas_rec, db_path)
    except Exception as e:  # noqa: BLE001 — v3 emit must never block PoSP issuance
        print(f"[daemon] retina-state-v3 emit hook failed (non-fatal): {e!r}")


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


# --- RWM L0 daemon wiring (A2A rounds 02-06: grok design D1-D7 + 2 claude-code flags,
# both accepted; build list confirmed exact in round-06 before implementation) ---------
RWM_CHAIN_SCHEMA = "qortroller-rwm-session-chain-v0"   # CANDIDATE — not FROZEN-v1, no PV-CI pin
RWM_BLOCK_PX = 32
RWM_CORNER = "bottom-right"
RWM_CHECKPOINT_INDEX = 0   # D3/r06: one checkpoint per session at L0. Multi-checkpoint
                           # needs a semantic L0 doesn't have; shipping 0 is the honest choice.


def _issue_rwm_l0(label, started_at, dst):
    """Retina Witness Mark L0 over the archived ring (D1). Fail-open: never breaks stop.

    Runs ONCE at session stop over the already-archived crops -- never on the hot capture
    loop -- matching the cadence _archive_ring() already established.

    Marks each archived frame with the visual locator, writes the marked copy to a
    `marked/` SIDECAR (D3/r02-q2: never overwrite the archive; destroying an original to
    save disk is not recoverable, and it would stale the tier-1 manifest.json hashes),
    then hash-chains the bytes ACTUALLY WRITTEN.

    Default-OFF behind RWM_L0_DAEMON_ENABLED (D5).

    Flag + device_id resolve via _env_or_bridge_dotenv: process env if set, else bridge/.env.
    Stop is a separate process from start — reading only os.environ silently no-ops a correctly
    configured bridge/.env (cfb_rwm_live_01 live-pass finding, 2026-07-24).
    """
    enabled = _env_or_bridge_dotenv("RWM_L0_DAEMON_ENABLED").lower()
    if enabled not in ("1", "true", "yes"):
        return
    if dst is None:
        print("[daemon] RWM: no archive dir (ring empty) — skipping")
        return

    # D2: device_id is env-sourced and NEVER fabricated. A manifest that invents the device
    # it claims to attest is worse than no manifest -- the whole point is third-party
    # matching of footage to a SPECIFIC certified device.
    device_id_hex = _env_or_bridge_dotenv("RWM_DEVICE_ID_HEX").lower()
    if not device_id_hex:
        print("[daemon] RWM: RWM_DEVICE_ID_HEX unset — skipping (device_id is never fabricated)")
        return

    import hashlib

    import numpy as np  # noqa: F401  (cv2 decode path returns ndarray)

    from l9_presence.session_identity import derive_session_id

    _bridge = _REPO / "bridge"
    if str(_bridge) not in sys.path:
        sys.path.insert(0, str(_bridge))
    from vapi_bridge.retina_capture_manifest import build_session_chain, verify_session_chain
    from vapi_bridge.retina_witness_mark import (compute_locator_payload,
                                                 composite_mark_onto_frame, encode_mark_symbols)

    try:
        import cv2
    except ImportError:
        print("[daemon] RWM: cv2 unavailable — skipping (marked frames need a real encoder)")
        return

    session_id = derive_session_id(label, started_at)
    crops = sorted(dst.glob("panel_*.png"))
    if not crops:
        print("[daemon] RWM: no archived crops — skipping")
        return

    payload = compute_locator_payload(hashlib.sha256(session_id.encode()).digest()[:8],
                                      RWM_CHECKPOINT_INDEX)
    symbols = encode_mark_symbols(payload)
    marked_dir = dst / "marked"
    marked_dir.mkdir(parents=True, exist_ok=True)

    # D4 + Flag 2: the daemon owns time. Both RWM modules are pure with no clock read
    # (matching WEC/GIC), so the monotonicity guard lives HERE. Consequence, stated in the
    # schema below: stored ts_ns is monotonic SESSION time, not filesystem wall-clock truth.
    _prev = 0

    def _mono(ts: int) -> int:
        nonlocal _prev
        if ts <= _prev:
            ts = _prev + 1
        _prev = ts
        return ts

    genesis_ts_ns = _mono(time.time_ns())
    frames, rows = [], []
    for i, src in enumerate(crops):
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            print(f"[daemon] RWM: unreadable crop {src.name} — skipping frame")
            continue
        try:
            marked = composite_mark_onto_frame(img, symbols[i % len(symbols)],
                                               corner=RWM_CORNER, block_px=RWM_BLOCK_PX)
        except ValueError as e:   # F-RWM-9 guard: frame too small for the block.
            print(f"[daemon] RWM: {src.name} cannot be marked ({e}) — skipping frame")
            continue
        out = marked_dir / src.name
        if not cv2.imwrite(str(out), marked):
            print(f"[daemon] RWM: write failed for {src.name} — skipping frame")
            continue
        # D3 step 4 (load-bearing): hash the bytes ON DISK, not the in-memory array. A
        # third-party verifier recomputes from these archived files; hashing anything else
        # makes the chain unverifiable by exactly the party it exists for.
        digest = hashlib.sha256(out.read_bytes()).digest()
        ts = _mono(src.stat().st_mtime_ns)
        frames.append((digest, ts))
        rows.append({"file": f"marked/{out.name}", "source": src.name,
                     "frame_index": len(frames) - 1, "frame_hash_hex": digest.hex(), "ts_ns": ts})

    if not frames:
        print("[daemon] RWM: no markable frames — skipping")
        return

    chain = build_session_chain(session_id, device_id_hex, genesis_ts_ns, frames)
    # Flag 1 (claude-code r03, grok-accepted r04): explicit check, NOT `assert` -- asserts are
    # stripped under -O, and a chain self-check that silently vanishes in an optimized run is a
    # comment, not a guard. Fail-open on failure, per D5.
    if not verify_session_chain(session_id, device_id_hex, genesis_ts_ns, frames, chain):
        print("[daemon] RWM: chain self-verify FAILED — not writing manifest (fail-open)")
        return

    (dst / "rwm_manifest_chain.json").write_text(json.dumps({
        "schema": RWM_CHAIN_SCHEMA,
        "candidate": True,
        "session_id": session_id,
        "device_id_hex": device_id_hex,
        "genesis_ts_ns": genesis_ts_ns,
        "ts_ns_semantics": ("monotonic SESSION time, not filesystem wall-clock truth: source "
                            "mtimes pass through a monotonicity guard (GIC INV-GIC-002 style), "
                            "so a stored ts_ns may exceed the file's real mtime. Do NOT read "
                            "these as capture wall-clock times."),
        "locator": {"checkpoint_index": RWM_CHECKPOINT_INDEX,
                    "session_id_hash_8b_hex": hashlib.sha256(session_id.encode()).digest()[:8].hex(),
                    "block_px": RWM_BLOCK_PX, "corner": RWM_CORNER},
        "frames": rows,
        "chain_hex": [h.hex() for h in chain],
    }, indent=2), encoding="utf-8")
    # Display path only. relative_to() raises for any dst outside the repo, and this runs
    # AFTER the manifest is safely written -- letting it throw would surface a successful
    # run as "RWM L0 failed (non-fatal)" to the operator. Cosmetics must not fail the step.
    _out = dst / "rwm_manifest_chain.json"
    try:
        _shown = _out.relative_to(_REPO)
    except ValueError:
        _shown = _out
    print(f"[daemon] RWM: {len(frames)} frames marked + chained -> {_shown}")


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
    # F-ARCB-1b: daemon-side MATCH_ENDED seal. The `_kill_tree` above force-killed the bridge, so
    # RGC.stop() -> LiveMatchStateTracker.close_session NEVER ran; if this session left a live-open
    # match (MATCH_STARTED with no MATCH_ENDED) in retina_match_state.jsonl, seal it here -- the same
    # independent-of-the-killed-bridge harvest as KAS/PoSP. Fail-open: never breaks the stop path.
    try:
        from l9_presence.match_state_live import seal_open_match_from_jsonl
        from l9_presence.session_identity import derive_session_id
        _ms_path = _REPO / "retina_match_state.jsonl"
        _seal = seal_open_match_from_jsonl(str(_ms_path), derive_session_id(label, st["started_at"]),
                                           time.time() * 1000.0)
        if _seal is not None:
            with open(_ms_path, "a", encoding="utf-8") as _fh:
                _fh.write(json.dumps(_seal) + "\n")
            print(f"[daemon] match-state: sealed MATCH_ENDED (daemon_session_close) for "
                  f"{_seal['session_id'][:16]}")
    except Exception as e:  # noqa: BLE001 — advisory seal; never break stop
        print(f"[daemon] match-state seal failed (non-fatal): {e!r}")
    # R3 ring-archival (DEFAULT-ON; --no-archive-ring to skip): preserve this session's rendering before the
    # next session overwrites the rolling ring. Fail-open — archival never breaks the stop path.
    _rwm_dst = None
    if not getattr(a, "no_archive_ring", False):
        try:
            res = _archive_ring(label, st["started_at"])
            if res is None:
                print("[daemon] ring-archive: ring empty — nothing to archive")
            else:
                dst, n = res
                _rwm_dst = dst
                print(f"[daemon] ring-archive: copied {n} crops -> {dst.relative_to(_REPO)}")
        except Exception as e:  # noqa: BLE001
            print(f"[daemon] ring-archive failed (non-fatal): {e!r}")
    # D1: RWM L0 immediately after a successful archive, under the same fail-open discipline
    # as the KAS/PoSP issuance below. Default-OFF (RWM_L0_DAEMON_ENABLED); never on the hot loop.
    try:
        _issue_rwm_l0(label, st["started_at"], _rwm_dst)
    except Exception as e:  # noqa: BLE001 — RWM must never break the stop path
        print(f"[daemon] RWM L0 failed (non-fatal): {e!r}")
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
    s.add_argument("--uvc-index", type=int, default=None,
                   help="OA-RP-1: capture from a UVC HDMI capture card (device index, usually 0) instead "
                        "of WGC window/monitor grab — direct PS5 HDMI, no Remote Play encode")
    s.add_argument("--label", default="genuine"); s.add_argument("--monitor", type=int, default=0,
                   help="0=window-name capture ('Remote Play' — default; immune to monitor layout); >=1=full monitor")
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
