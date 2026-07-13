#!/usr/bin/env python3
"""A2A-PKG round-03 -- the `qortroller` CLI spine (PKG-D-01 subset + PKG-D-03 receipt).

The Phase D product surface over the EXISTING daemon (wraps, never forks): five verbs that retire
the tribal shell knowledge measured live in T6.6b:

    python scripts/qortroller.py setup      # node provisioning v0: port preflight + card probe -> node.toml
    python scripts/qortroller.py play       # start a session (persisted config; session-scoped dirs)
    python scripts/qortroller.py status     # honest liveness: port owner, daemon state, ring freshness
    python scripts/qortroller.py stop       # end session (env re-applied from state) + write the Proof Receipt
    python scripts/qortroller.py receipt    # (re)render the receipt for the last / a named session
    python scripts/qortroller.py verify     # offline stranger-check of the session's v3 record

Kills the live frictions: #1 phantom port-8080 (preflight names the owner PID), #2 stale ring
(session-scoped capture dirs `retina_kf_crops/<label>_<stamp>`), #3 env amnesia (config persisted in
`~/.qortroller/node.toml` + per-session `session.json`; stop re-applies automatically).

Rails: additive (the daemon verbs work unchanged); no secrets read/written (node.toml carries PUBLIC
knobs only -- a name-allowlist refuses secret-shaped keys); honest verdicts render AS-IS (UNVERIFIABLE/
PARTIAL never rounded up; F-T66B-1 disclosed); kill-switch untouched. ASCII-only output.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_HOME = Path(os.environ.get("QORTROLLER_HOME", "")) if os.environ.get("QORTROLLER_HOME") else (Path.home() / ".qortroller")
_NODE_TOML = _HOME / "node.toml"
_SESSION_JSON = _HOME / "session.json"
_DAEMON = _REPO / "scripts" / "retina_capture_daemon.py"

# PKG-D-05 rail: node.toml carries PUBLIC knobs only. Any key whose name looks secret-shaped is
# refused at write AND at load (fail-closed) -- the pack boundary enforces the no-secrets rule.
_SECRET_MARKERS = ("key", "secret", "token", "password", "private", "mnemonic", "seed")

_DEFAULTS = {
    "pack": "observer-only",
    "uvc_index": 1,
    "killfeed_roi": "0.0,0.45,0.26,0.19",
    "kf_engine": "rapidocr",
    "emit_v3": True,
    "label_prefix": "session",
}


# ---------------------------------------------------------------- pure helpers (tested)

def secret_shaped(key: str) -> bool:
    k = key.lower()
    return any(m in k for m in _SECRET_MARKERS)


def write_flat_toml(path: Path, cfg: dict) -> None:
    """Tiny flat-TOML writer (str/int/float/bool). Refuses secret-shaped keys (PKG-D-05 rail)."""
    bad = [k for k in cfg if secret_shaped(k)]
    if bad:
        raise ValueError(f"refusing secret-shaped key(s) in node config: {bad}")
    lines = ["# QorTroller node config -- PUBLIC knobs only (secret-shaped keys are refused)."]
    for k, v in cfg.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        else:
            lines.append(f'{k} = "{v}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_node_config(path: Path = _NODE_TOML) -> dict:
    """node.toml -> dict over defaults. Fail-open to defaults; fail-CLOSED on secret-shaped keys."""
    cfg = dict(_DEFAULTS)
    try:
        import tomllib
        if path.exists():
            loaded = tomllib.loads(path.read_text(encoding="utf-8"))
            bad = [k for k in loaded if secret_shaped(k)]
            if bad:
                raise ValueError(f"node config carries secret-shaped key(s) {bad} -- remove them; "
                                 f"secrets never live in the kit config")
            cfg.update(loaded)
    except ValueError:
        raise
    except Exception:  # noqa: BLE001 -- unreadable config -> defaults (fail-open)
        pass
    return cfg


def parse_netstat_owners(netstat_text: str, port: int) -> list[int]:
    """PIDs LISTENING on :port from `netstat -ano` output (friction #1 preflight)."""
    pids = set()
    needle = f":{port}"
    for line in netstat_text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and "LISTENING" in line.upper():
            if parts[1].endswith(needle):
                try:
                    pids.add(int(parts[-1]))
                except ValueError:
                    continue
    return sorted(pids)


def ring_freshness(capture_dir: Path, now_s: float) -> tuple[int, float]:
    """(n_crops, age_seconds_of_newest) for a session capture dir. (0, inf) when empty -- freshness,
    not counts, is the liveness signal (friction #2)."""
    try:
        crops = list(capture_dir.glob("panel_*.png"))
        if not crops:
            return 0, float("inf")
        newest = max(c.stat().st_mtime for c in crops)
        return len(crops), max(0.0, now_s - newest)
    except Exception:  # noqa: BLE001
        return 0, float("inf")


def render_receipt(label: str, kas: dict | None, posp: dict | None, v3: dict | None,
                   manifest: dict | None, *, stranger_verified: bool | None = None,
                   pack: str = "?") -> str:
    """PKG-D-03: the human Proof Receipt over the machine artifacts. Honest verdicts AS-IS."""
    L = ["=" * 62, "  QorTroller Session Receipt", "=" * 62,
         f"  Session : {label}", f"  Pack    : {pack}",
         f"  Date    : {time.strftime('%Y-%m-%d %H:%M')}", "-" * 62]
    if kas:
        L.append(f"  KAS authorship  : {kas.get('verdict', '?')}  authored={kas.get('authored_kills', '?')}"
                 f"  commit={str(kas.get('commitment', ''))[:16]}...")
    else:
        L.append("  KAS authorship  : (no record)")
    if posp:
        er = posp.get("events_roots") or {}
        L.append(f"  PoSP presence   : {posp.get('verdict', '?')}"
                 f"  fusion_rows={((posp.get('fusion') or {}).get('n_id_verified', 0))}"
                 f"  retina_root={str(er.get('retina_perception_root') or 'null')[:16]}")
    else:
        L.append("  PoSP presence   : (no record)")
    if v3:
        L.append(f"  RETINA-STATE-v3 : present  n_events={v3.get('n_events', '?')}"
                 f"  commitment={str(v3.get('commitment', ''))[:16]}...")
        if stranger_verified is not None:
            L.append(f"  stranger_verified: {stranger_verified}")
    else:
        L.append("  RETINA-STATE-v3 : honest-null (no conformant events captured)")
    if manifest:
        L.append(f"  Archive         : {manifest.get('count', '?')} crops  schema={manifest.get('schema', '?')}")
    L += ["-" * 62,
          "  What you hold: a cryptographic pack a stranger can re-verify",
          "  offline. Not a highlight reel. A presence+authorship receipt.",
          "-" * 62,
          "  Honesty notes:",
          "   - F-T66B-1: own-kill OCR recall incomplete (fix in progress);",
          "     zero-false-read holds (nothing is ever falsely authored).",
          "   - PARTIAL/UNVERIFIABLE verdicts render as-is, never upgraded.",
          "=" * 62]
    return "\n".join(L)


def find_latest(pattern: str, root: Path) -> Path | None:
    hits = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def _load_json(path: Path | None) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- session state

def save_session_state(label: str, stamp: int, capture_dir: str) -> None:
    _HOME.mkdir(parents=True, exist_ok=True)
    _SESSION_JSON.write_text(json.dumps(
        {"label": label, "stamp": stamp, "capture_dir": capture_dir}), encoding="utf-8")


def load_session_state() -> dict | None:
    return _load_json(_SESSION_JSON)


def _session_env(cfg: dict, capture_dir: str) -> None:
    """Apply the session env (frictions #2/#3): same values at play AND stop, from config not memory."""
    os.environ["RETINA_KF_ENGINE"] = str(cfg.get("kf_engine", "rapidocr"))
    os.environ["RETINA_STATE_V3_EMIT_ENABLED"] = "true" if cfg.get("emit_v3", True) else "false"
    os.environ["RETINA_KILLFEED_CAPTURE_DIR"] = capture_dir


# ---------------------------------------------------------------- verbs

def cmd_setup(a) -> int:
    print("QorTroller node provisioning (v0: stages 0-1; ROI/controller stages land next increment)")
    print("- Stage 0: HOST PREFLIGHT")
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=20).stdout
        owners = parse_netstat_owners(out, 8080)
    except Exception:  # noqa: BLE001
        owners = []
    if owners:
        print(f"  WARNING: port 8080 already LISTENING (pid={owners}). A stale bridge here made two")
        print("  sessions capture NOTHING while looking healthy. Close it (taskkill /F /PID <pid>)")
        print("  before `play`, or expect the same failure.")
    else:
        print("  port 8080: FREE")
    print("- Stage 1: CAPTURE CARD (C0 probe)")
    idx = a.uvc_index
    if idx is None:
        try:
            sys.path.insert(0, str(_REPO / "scripts"))
            from retina_card_smoke import enumerate_devices  # noqa: PLC0415
            reports, cv2_ok = enumerate_devices(5, 1920, 1080, 60, "MJPG")
            live = [r for r in reports if r.opened and r.grabbed]
            for r in live:
                print(f"    index {r.index}: {r.width}x{r.height}@{r.fps:.0f}")
            best = max(live, key=lambda r: (r.width, r.fps), default=None)
            idx = best.index if best else 1
            print(f"  selected uvc_index={idx} (highest-res frame source; --uvc-index to override)")
        except Exception as e:  # noqa: BLE001
            idx = 1
            print(f"  probe unavailable ({e!r}) -> defaulting uvc_index=1")
    cfg = read_node_config()
    cfg.update({"uvc_index": int(idx), "pack": a.pack})
    if a.killfeed_roi:
        cfg["killfeed_roi"] = a.killfeed_roi
    write_flat_toml(_NODE_TOML, cfg)
    print(f"- node config written -> {_NODE_TOML}")
    print("  Reminders: PS5 HDCP OFF (Settings > System > HDMI); OBS/Camera CLOSED (single-holder).")
    return 0


def cmd_play(a) -> int:
    cfg = read_node_config()
    # friction #1: refuse to start behind a phantom port-holder
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=20).stdout
        owners = parse_netstat_owners(out, 8080)
    except Exception:  # noqa: BLE001
        owners = []
    if owners:
        print(f"REFUSING to start: port 8080 is already LISTENING (pid={owners}).")
        print("A stale holder here answers /health while the new bridge captures NOTHING (T6.6b lesson).")
        print(f"Fix: taskkill /F /T /PID {owners[0]}   then re-run `play`.")
        return 1
    stamp = int(time.time())
    label = a.label or f"{cfg.get('label_prefix', 'session')}"
    capture_dir = f"retina_kf_crops/{label}_{stamp}"          # friction #2: session-scoped ring
    _session_env(cfg, capture_dir)
    save_session_state(label, stamp, capture_dir)
    cmd = [sys.executable, str(_DAEMON), "start", "--uvc-index", str(cfg.get("uvc_index", 1)),
           "--label", label, "--killfeed", "--killfeed-roi", str(cfg.get("killfeed_roi")),
           "--capture", "--capture-dir", capture_dir, "--session-anchor"]
    print(f"[qortroller] pack={cfg.get('pack')} label={label} capture_dir={capture_dir}")
    return subprocess.call(cmd, cwd=str(_REPO))


def cmd_status(a) -> int:  # noqa: ARG001
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=20).stdout
        owners = parse_netstat_owners(out, 8080)
        print(f"port 8080 owner(s): {owners or 'none'}")
    except Exception:  # noqa: BLE001
        print("port 8080 owner(s): (netstat unavailable)")
    subprocess.call([sys.executable, str(_DAEMON), "status"], cwd=str(_REPO))
    st = load_session_state()
    if st:
        n, age = ring_freshness(_REPO / st["capture_dir"], time.time())
        fresh = "LIVE" if age < 120 else ("STALE" if n else "EMPTY")
        print(f"session ring: {st['capture_dir']}  crops={n}  newest_age={age:.0f}s  [{fresh}]")
        print("  (freshness, not counts, proves capture -- a full ring can be a previous session)")
    return 0


def cmd_stop(a) -> int:
    st = load_session_state()
    if not st:
        print("no persisted session state -- falling back to daemon stop with no v3 env (dev path)")
        return subprocess.call([sys.executable, str(_DAEMON), "stop", "--kas"], cwd=str(_REPO))
    cfg = read_node_config()
    _session_env(cfg, st["capture_dir"])                      # friction #3: env re-applied, not re-typed
    rc = subprocess.call([sys.executable, str(_DAEMON), "stop", "--label", st["label"], "--kas"],
                         cwd=str(_REPO))
    _print_and_write_receipt(st["label"], cfg, stranger_verified=None)
    return rc


def _collect_artifacts(label: str):
    audits = _REPO / "audits"
    kas = _load_json(find_latest(f"kas_record_{label}_*.json", audits))
    posp = _load_json(find_latest(f"posp_record_{label}_*.json", audits))
    v3 = _load_json(find_latest(f"retina_state_v3_{label}_*.json", audits))
    manifest = None
    arch = sorted((_REPO / "retina_kf_archive").glob(f"{label}_*/manifest.json"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if arch:
        manifest = _load_json(arch[0])
    return kas, posp, v3, manifest


def _print_and_write_receipt(label: str, cfg: dict, stranger_verified) -> Path:
    kas, posp, v3, manifest = _collect_artifacts(label)
    text = render_receipt(label, kas, posp, v3, manifest,
                          stranger_verified=stranger_verified, pack=str(cfg.get("pack", "?")))
    out = _REPO / "audits" / f"session_receipt_{label}.md"
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"[qortroller] receipt -> {out.relative_to(_REPO)}")
    return out


def cmd_receipt(a) -> int:
    st = load_session_state()
    label = a.label or (st and st.get("label"))
    if not label:
        print("no session known -- pass a label: qortroller receipt --label <label>")
        return 1
    _print_and_write_receipt(label, read_node_config(), stranger_verified=None)
    return 0


def cmd_verify(a) -> int:
    st = load_session_state()
    label = a.label or (st and st.get("label"))
    if not label:
        print("no session known -- pass a label: qortroller verify --label <label>")
        return 1
    _, _, v3, _ = _collect_artifacts(label)
    if not v3:
        print(f"no retina_state_v3 record for {label!r} (honest-null sessions have nothing to verify)")
        return 1
    sys.path.insert(0, str(_REPO))
    from bridge.vapi_bridge.retina_state_v3_record import verify_retina_state_v3_record  # noqa: PLC0415
    ok = verify_retina_state_v3_record(v3)
    print(f"stranger_verified: {ok}")
    _print_and_write_receipt(label, read_node_config(), stranger_verified=ok)
    return 0 if ok else 2


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="qortroller", description="QorTroller pilot-kit CLI (Phase D)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="node provisioning v0 (port preflight + card probe -> node.toml)")
    s.add_argument("--uvc-index", type=int, default=None)
    s.add_argument("--killfeed-roi", default="")
    s.add_argument("--pack", default="observer-only", choices=["observer-only", "developer-full"])
    s.set_defaults(fn=cmd_setup)
    p = sub.add_parser("play", help="start a capture session (persisted config, session-scoped dirs)")
    p.add_argument("--label", default="")
    p.set_defaults(fn=cmd_play)
    sub.add_parser("status", help="honest liveness (port owner + daemon + ring freshness)").set_defaults(fn=cmd_status)
    sub.add_parser("stop", help="end session + write the Proof Receipt").set_defaults(fn=cmd_stop)
    r = sub.add_parser("receipt", help="(re)render the session receipt")
    r.add_argument("--label", default="")
    r.set_defaults(fn=cmd_receipt)
    v = sub.add_parser("verify", help="offline stranger-check of the session's v3 record")
    v.add_argument("--label", default="")
    v.set_defaults(fn=cmd_verify)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
