#!/usr/bin/env python3
"""A2A-PKG round-03 -- the `qortroller` CLI spine (PKG-D-01 subset + PKG-D-03 receipt).

The Phase D product surface over the EXISTING daemon (wraps, never forks): five verbs that retire
the tribal shell knowledge measured live in T6.6b:

    python scripts/qortroller.py setup      # node provisioning v0: port preflight + card probe -> node.toml
    python scripts/qortroller.py play       # start a session (persisted config; session-scoped dirs)
    python scripts/qortroller.py status     # honest liveness: port owner, daemon state, ring freshness
    python scripts/qortroller.py status --json  # PKG-UI-04 machine-readable snapshot for Stream UI
    python scripts/qortroller.py ui         # offline Stream shell (observes CLI JSON; no second plane)
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

# PKG-D-10: pack matrix -- capability ENVELOPES of PUBLIC env pins, applied to the session child
# process only (never merged into bridge/.env). Env names corrected to repo reality (round-04 wrote
# KF_ENGINE/KILLFEED_ROI shorthand; the real names carry the RETINA_ prefix). `observer-only` =
# maximum proof surface, minimum side-effect surface: kill-switch FORCED on, hard-rule biometric
# layers FORCED off, grind off, DA witness off. Secrets are structurally impossible here (the
# secret-shaped-key detector polices node.toml; PACKS carries names only, checked by test).
PACKS: dict[str, dict[str, str]] = {
    "observer-only": {
        "RETINA_CAPTURE_SOURCE": "uvc",
        "RETINA_PERCEPTION_ENABLED": "true",     # observation plane on for the pilot
        "RETINA_DA_WITNESS_ENABLED": "false",    # DePIN DA side-path off until opt-in
        "CHAIN_SUBMISSION_PAUSED": "true",       # HARD: the kit never spends/deploys
        "L6_CHALLENGES_ENABLED": "false",        # hard rule (N gate)
        "L6B_ENABLED": "false",                  # hard rule (N gate)
        "GSR_ENABLED": "false",                  # hard rule (N=0)
        "GRIND_MODE": "false",                   # observer != grind
    },
    # developer-full: the operator's existing shell/bridge/.env governs -- the pack pins ONLY the
    # safety floor (kill-switch). Everything else is deliberately NOT pinned (dev freedom).
    "developer-full": {
        "CHAIN_SUBMISSION_PAUSED": "true",
    },
}


def apply_pack_env(pack: str, env: dict) -> dict:
    """Apply a pack's pins onto an env mapping (session child only). Unknown pack -> observer-only
    (fail-safe to the tightest envelope). Returns the same mapping for chaining."""
    for k, v in PACKS.get(pack, PACKS["observer-only"]).items():
        env[k] = v
    return env


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


# ---------------------------------------------------------------- PKG-D-11/12/13 pure helpers

# Birth-state machine for a witness node (PKG-D-11). Not an install progress bar.
NODE_STATE_UNPROVISIONED = "UNPROVISIONED"
NODE_STATE_PROVISIONING = "PROVISIONING"
NODE_STATE_FIRST_PROOF_PENDING = "FIRST_PROOF_PENDING"
NODE_STATE_NODE_BORN = "NODE_BORN"
NODE_STATE_LIVE = "LIVE"

HONESTY_NOTES_SCHEMA = "qortroller-honesty-notes-v1"  # PKG-D-13


def compute_node_state(home: Path, *, session: dict | None = None,
                       port_owners: list | None = None,
                       capture_live: bool = False) -> dict:
    """PKG-D-11: product state for a node. status prints this so "did I finish setup?" is gone.

    Priority (first match wins after LIVE check):
      LIVE                 -- session state present AND capture ring fresh (or port held by us)
      UNPROVISIONED        -- no node.toml
      PROVISIONING         -- node.toml but Stage-3 ROI and/or Stage-4 controller ack missing
      FIRST_PROOF_PENDING  -- ROI + Stage-4 acked, birth_receipt.json missing (Path A or B)
      NODE_BORN            -- birth_receipt present
    """
    node = home / "node.toml"
    roi = home / "setup" / "stage3_roi_pass.json"
    stage4 = home / "setup" / "stage4_controller_pass.json"
    birth_path = home / "birth_receipt.json"
    owners = port_owners or []
    if capture_live or (session and owners):
        # LIVE only when we have a known session AND something that looks active
        if session and (capture_live or owners):
            return {"state": NODE_STATE_LIVE,
                    "detail": f"session={session.get('label', '?')} capture active",
                    "label": session.get("label"), "stamp": session.get("stamp")}
    if not node.exists():
        return {"state": NODE_STATE_UNPROVISIONED, "detail": "run: qortroller setup"}
    if not roi.exists():
        return {"state": NODE_STATE_PROVISIONING,
                "detail": "ROI pending -- run: qortroller setup --stage roi"}
    if not stage4.exists():
        return {"state": NODE_STATE_PROVISIONING,
                "detail": "controller presence pending -- run: qortroller setup --stage controller"}
    birth = _load_json(birth_path)
    if not birth:
        cfg = read_node_config(node)
        path_b = bool(cfg.get("stage5_deferred", False))
        detail = ("node provisioned, first proof pending"
                  + (" (Path B: play a real match, then stop)" if path_b
                     else " (run: qortroller drill  OR  play -> stop)"))
        return {"state": NODE_STATE_FIRST_PROOF_PENDING, "detail": detail,
                "stage5_deferred": path_b}
    return {"state": NODE_STATE_NODE_BORN,
            "detail": f"first_session_id={birth.get('first_session_id', '?')}",
            "first_session_id": birth.get("first_session_id"),
            "birth_path": "path_b" if birth.get("path") == "B" else birth.get("path", "A")}


# ---------------------------------------------------------------- PKG-D-15 Stage 4: controller presence

# DualSense Edge CFI-ZCP1 (Sony) -- public USB IDs only; never a secret surface.
EDGE_VID = 0x054C
EDGE_PID = 0x0DF2
STAGE4_SCHEMA = "qortroller-stage4-controller-v1"

# Fields that MUST NOT be written to stage4_controller_pass.json (path/serial fingerprint risk).
_STAGE4_FORBIDDEN_KEYS = frozenset({
    "path", "serial", "serial_number", "usage", "usage_page", "release_number",
    "interface_number", "bus_type",
})

DUAL_CONNECTION_NOTE = (
    "Dual-connection (recommended for live match proof):\n"
    "  USB-C DATA cable to this laptop  ->  HID presence (this stage reads it)\n"
    "  AND Bluetooth paired to PS5      ->  gameplay (NCAA CFB 26 etc.)\n"
    "  This check is USB-HID only -- BT to PS5 is invisible here (do NOT unpair PS5).\n"
    "  CaptureHealthMonitor / grind dual-connection docs: same rule."
)


def classify_controller_presence(devices: list, *, vid: int = EDGE_VID,
                                 pid: int = EDGE_PID) -> dict:
    """PKG-D-15 pure: map hid.enumerate()-shaped dicts -> safe presence result.

    PERSIST-SAFE (may land on disk): present, vid_hex, pid_hex, product, n_matches,
    detection, schema. Never serial, never HID path, never usage pages.
    """
    matches = []
    for d in devices or []:
        if not isinstance(d, dict):
            continue
        try:
            dv = int(d.get("vendor_id", -1))
            dp = int(d.get("product_id", -1))
        except (TypeError, ValueError):
            continue
        if dv == vid and dp == pid:
            matches.append(d)
    present = len(matches) > 0
    product = "DualSense Edge CFI-ZCP1"
    if present:
        raw = (matches[0].get("product_string") or "").strip()
        # Display/persist product marketing name only (truncate; strip control chars)
        if raw:
            product = "".join(ch for ch in raw if 32 <= ord(ch) < 127)[:64] or product
    return {
        "schema": STAGE4_SCHEMA,
        "present": present,
        "vid_hex": f"{vid:04X}",
        "pid_hex": f"{pid:04X}",
        "product": product,
        "n_matches": len(matches),
        "detection": "injected",
    }


def build_stage4_pass_record(presence: dict, *, operator_ack: bool,
                             dual_connection_note_shown: bool,
                             operator_skip: bool = False,
                             ts: int | None = None) -> dict:
    """PKG-D-15 pure: stage4_controller_pass.json body. Fail-closed strip of forbidden keys."""
    ts = int(ts if ts is not None else time.time())
    rec = {
        "schema": STAGE4_SCHEMA,
        "present": bool(presence.get("present")),
        "vid_hex": str(presence.get("vid_hex", f"{EDGE_VID:04X}")),
        "pid_hex": str(presence.get("pid_hex", f"{EDGE_PID:04X}")),
        "product": str(presence.get("product", "DualSense Edge CFI-ZCP1"))[:64],
        "n_matches": int(presence.get("n_matches") or 0),
        "detection": str(presence.get("detection", "unknown"))[:32],
        "ts": ts,
        "operator_ack": bool(operator_ack),
        "dual_connection_note_shown": bool(dual_connection_note_shown),
        "operator_skip": bool(operator_skip),
    }
    # Defense in depth: never let a caller smuggle serial/path through presence dict
    for k in list(rec.keys()):
        if k in _STAGE4_FORBIDDEN_KEYS or secret_shaped(k):
            del rec[k]
    return rec


def probe_controller_presence(*, enumerate_fn=None) -> dict:
    """Live HID probe for Edge VID/PID. Never raises. Serial/path never returned.

    enumerate_fn: optional injectable (tests) returning list[dict] like hid.enumerate().
    """
    if enumerate_fn is not None:
        try:
            devices = list(enumerate_fn(EDGE_VID, EDGE_PID) or [])
        except Exception:  # noqa: BLE001
            devices = []
        out = classify_controller_presence(devices)
        out["detection"] = "injected"
        return out

    last_err = None
    for pkg in ("hid", "hidapi"):
        try:
            mod = __import__(pkg)
            devices = list(mod.enumerate(EDGE_VID, EDGE_PID) or [])
            # Strip forbidden fields before classification (path/serial never enter the result)
            safe_devs = []
            for d in devices:
                if not isinstance(d, dict):
                    continue
                safe_devs.append({
                    "vendor_id": d.get("vendor_id"),
                    "product_id": d.get("product_id"),
                    "product_string": d.get("product_string") or "",
                    # deliberately omit path / serial_number
                })
            out = classify_controller_presence(safe_devs)
            out["detection"] = pkg
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    return {
        "schema": STAGE4_SCHEMA,
        "present": False,
        "vid_hex": f"{EDGE_VID:04X}",
        "pid_hex": f"{EDGE_PID:04X}",
        "product": "DualSense Edge CFI-ZCP1",
        "n_matches": 0,
        "detection": "unavailable",
        "note": f"hid probe unavailable ({last_err!r})" if last_err else "no hid backend",
    }


# ---------------------------------------------------------------- PKG-D-16 dogfood report schema

DOGFOOD_REPORT_SCHEMA = "qortroller-dogfood-report-v1"
DOGFOOD_REPORT_REQUIRED = frozenset({
    "schema", "run_label", "path", "operator_would_rerun_without_chat",
})
DOGFOOD_REPORT_OPTIONAL = frozenset({
    "started_at", "finished_at", "time_to_first_proof_s", "stages_completed",
    "friction_events", "wizard_wording_confused", "receipt_ok", "share_ok",
    "verify_tier", "node_state_at_end", "f_t66b1_status_seen", "blocked_on",
    "freeform_notes", "pack", "ts",
})
# Friction event codes (closed set for cross-run aggregation; freeform goes in detail)
DOGFOOD_FRICTION_CODES = frozenset({
    "PORT_PHANTOM", "CARD_INDEX", "ROI_CONFUSION", "CONTROLLER_MISSING",
    "RP5_BLOCK", "DAEMON_FAIL", "RECEIPT_MISSING", "SHARE_CONFUSION",
    "WIZARD_WORDING", "OTHER",
})


def scaffold_dogfood_report(*, run_label: str = "dogfood_1", path: str = "B",
                            pack: str = "observer-only") -> dict:
    """PKG-D-16: empty operator-fillable report. Local only; never uploaded by the kit."""
    return {
        "schema": DOGFOOD_REPORT_SCHEMA,
        "run_label": run_label,
        "path": path if path in ("A", "B") else "B",
        "pack": pack,
        "started_at": "",
        "finished_at": "",
        "time_to_first_proof_s": None,
        "stages_completed": [],  # e.g. [0, 1, 3, 4, 5]
        "friction_events": [],   # [{code, stage, detail}]
        "wizard_wording_confused": [],  # [{stage, quote, expected}]
        "receipt_ok": None,
        "share_ok": None,
        "verify_tier": None,     # INDICATIVE | STRANGER_OK | n/a
        "node_state_at_end": None,
        "f_t66b1_status_seen": None,  # OPEN | MEASURED | HISTORICAL_GAP
        "blocked_on": [],
        "operator_would_rerun_without_chat": None,  # THE Phase D dogfood bar
        "freeform_notes": "",
        "ts": int(time.time()),
    }


def validate_dogfood_report(report: dict) -> tuple[bool, list[str]]:
    """PKG-D-16 pure: structural validation. Returns (ok, errors). Never raises."""
    errs: list[str] = []
    if not isinstance(report, dict):
        return False, ["report must be a dict"]
    if report.get("schema") != DOGFOOD_REPORT_SCHEMA:
        errs.append(f"schema must be {DOGFOOD_REPORT_SCHEMA}")
    for k in DOGFOOD_REPORT_REQUIRED:
        if k not in report:
            errs.append(f"missing required field: {k}")
    # Refuse secret-shaped keys anywhere in the top level
    for k in report:
        if secret_shaped(str(k)):
            errs.append(f"secret-shaped key refused: {k}")
        if str(k) not in DOGFOOD_REPORT_REQUIRED | DOGFOOD_REPORT_OPTIONAL:
            # unknown keys are soft-warn only for forward compat -- still ok
            pass
    path = report.get("path")
    if path is not None and path not in ("A", "B"):
        errs.append("path must be A or B")
    for fe in report.get("friction_events") or []:
        if not isinstance(fe, dict):
            errs.append("friction_events entries must be objects")
            continue
        code = fe.get("code")
        if code and code not in DOGFOOD_FRICTION_CODES:
            errs.append(f"unknown friction code: {code}")
        for fk in fe:
            if secret_shaped(str(fk)):
                errs.append(f"secret-shaped key in friction_event: {fk}")
    bar = report.get("operator_would_rerun_without_chat")
    if bar is not None and not isinstance(bar, bool):
        errs.append("operator_would_rerun_without_chat must be bool or null")
    return (len(errs) == 0), errs


def build_honesty_notes(*, own_kill_recall: tuple | None = None,
                        capture_era_has_metric: bool | None = None,
                        f_t66b1_open: bool = True) -> list:
    """PKG-D-13: versioned honesty notes. Never invent recall for sessions that lacked it.

    own_kill_recall: optional (numerator, denominator) when OCR metric exists for THIS session.
    capture_era_has_metric:
      True  -> session was captured under code that could measure recall
      False -> historical capture; re-render must not pretend new OCR saw old kills
      None  -> unknown / current default OPEN disclosure
    """
    notes: list[dict] = []
    if own_kill_recall is not None:
        n, d = own_kill_recall
        notes.append({"code": "F-T66B-1", "status": "MEASURED",
                      "detail": f"own_kill_recall={n}/{d}",
                      "as_of_schema": HONESTY_NOTES_SCHEMA})
    elif capture_era_has_metric is False:
        notes.append({"code": "F-T66B-1", "status": "HISTORICAL_GAP",
                      "detail": "F-T66B-1 applied at capture time; not re-scored by later OCR",
                      "as_of_schema": HONESTY_NOTES_SCHEMA})
    elif f_t66b1_open:
        notes.append({"code": "F-T66B-1", "status": "OPEN",
                      "detail": "own-kill OCR recall incomplete (fix in progress); "
                                "zero-false-read holds",
                      "as_of_schema": HONESTY_NOTES_SCHEMA})
    notes.append({"code": "VERDICT_AS_IS", "status": "FROZEN",
                  "detail": "PARTIAL/UNVERIFIABLE never upgraded on render",
                  "as_of_schema": HONESTY_NOTES_SCHEMA})
    return notes


def format_honesty_notes(notes: list, *, share: bool = False) -> list[str]:
    """Render honesty notes as receipt lines. SHARE keeps code+status; omits long paths."""
    lines = ["  Honesty notes:"]
    for n in notes:
        code = n.get("code", "?")
        status = n.get("status", "?")
        detail = n.get("detail", "")
        if share and len(detail) > 80:
            detail = detail[:77] + "..."
        lines.append(f"   - [{status}] {code}: {detail}")
    return lines


# ---------------------------------------------------------------- PKG-UI Stream UX pure helpers (round-11)

# Status / stream / receipt-reveal / birth-ceremony schemas for the gamer UI track.
# UI observes these models; it never invents capture state (PKG-D-06 held).
STATUS_SNAPSHOT_SCHEMA = "qortroller-status-snapshot-v1"
STREAM_VIEW_SCHEMA = "qortroller-stream-view-v1"
RECEIPT_REVEAL_SCHEMA = "qortroller-receipt-reveal-v1"
BIRTH_CEREMONY_SCHEMA = "qortroller-birth-ceremony-v1"

# Stream freshness taxonomy (gamer surface). Share postcard keeps coarser FRESH|STALE|UNKNOWN.
FRESHNESS_LIVE = "LIVE"       # age < 120s -- witness pulse active
FRESHNESS_FRESH = "FRESH"     # 120s <= age < 300s -- recent, not mid-pulse
FRESHNESS_STALE = "STALE"     # age >= 300s
FRESHNESS_EMPTY = "EMPTY"     # no crops in session ring
FRESHNESS_UNKNOWN = "UNKNOWN" # age not observed

# Verdict dignity tones -- honest, never green-check theater (PKG-UI-02).
VERDICT_TONE_EARNED = "earned"           # SYNCHRONIZED / clear presence
VERDICT_TONE_PARTIAL = "partial"         # PARTIAL / PARTIAL_SURFACES -- dignified truth
VERDICT_TONE_HONEST_NULL = "honest_null" # missing / UNVERIFIABLE -- not a failure
VERDICT_TONE_HYGIENE = "hygiene"         # HYGIENE_FAIL -- capture hygiene, not "you failed"
VERDICT_TONE_ABSENT = "absent"           # no artifact at all

# Stream view: fields deliberately ABSENT from the gamer mid-match surface.
STREAM_DELIBERATELY_ABSENT = frozenset({
    "crop_counts", "fps", "frame_rate", "raw_biometric", "scrolling_hashes",
    "grind_bar", "green_check_theater", "mock_liveness", "consent_controls",
    "keys", "operator_drawers", "mlga", "fleet_coherence",
})


def classify_freshness_class(age_s: float | None, *, n_crops: int | None = None) -> str:
    """PKG-UI-01 pure: stream freshness-class (never raw counts as the liveness signal).

    LIVE   age < 120
    FRESH  120 <= age < 300
    STALE  age >= 300
    EMPTY  n_crops == 0 or age is +inf
    UNKNOWN age is None
    """
    if age_s is None:
        return FRESHNESS_UNKNOWN
    if n_crops is not None and n_crops == 0:
        return FRESHNESS_EMPTY
    try:
        if age_s == float("inf") or age_s != age_s:  # inf or NaN
            return FRESHNESS_EMPTY
    except Exception:  # noqa: BLE001
        return FRESHNESS_UNKNOWN
    if age_s < 120:
        return FRESHNESS_LIVE
    if age_s < 300:
        return FRESHNESS_FRESH
    return FRESHNESS_STALE


def freshness_for_share(age_s: float | None) -> str:
    """Share postcard taxonomy (FROZEN PKG-D-09 redaction): FRESH | STALE | UNKNOWN only."""
    if age_s is None:
        return FRESHNESS_UNKNOWN
    try:
        if age_s == float("inf") or age_s != age_s:
            return FRESHNESS_STALE
    except Exception:  # noqa: BLE001
        return FRESHNESS_UNKNOWN
    return FRESHNESS_FRESH if age_s < 300 else FRESHNESS_STALE


def build_status_snapshot(*, home: Path, session: dict | None = None,
                          port_owners: list | None = None,
                          capture_dir: Path | None = None,
                          now_s: float | None = None,
                          pack: str = "observer-only") -> dict:
    """PKG-UI-04 pure: machine-readable status for the gamer UI (CLI-written truth).

    No secret-shaped keys. No crop counts as primary liveness (freshness_class only).
    No keys, no consent authority, no fabricated liveness.
    """
    now = float(now_s if now_s is not None else time.time())
    owners = list(port_owners or [])
    n_crops, age = (0, float("inf"))
    if capture_dir is not None:
        n_crops, age = ring_freshness(capture_dir, now)
    elif session and session.get("capture_dir"):
        # Relative capture_dir is resolved by the caller when possible; fail-soft to EMPTY.
        try:
            n_crops, age = ring_freshness(Path(session["capture_dir"]), now)
        except Exception:  # noqa: BLE001
            n_crops, age = 0, float("inf")
    fclass = classify_freshness_class(None if age == float("inf") and n_crops == 0 else age,
                                      n_crops=n_crops)
    if n_crops == 0:
        fclass = FRESHNESS_EMPTY
    capture_live = fclass == FRESHNESS_LIVE
    ns = compute_node_state(home, session=session, port_owners=owners, capture_live=capture_live)
    label = (session or {}).get("label")
    stamp = (session or {}).get("stamp")
    sid = f"{label}_{stamp}" if label and stamp else (label or None)
    snap = {
        "schema": STATUS_SNAPSHOT_SCHEMA,
        "ts": int(now),
        "node_state": ns.get("state"),
        "node_detail": ns.get("detail"),
        "pack": pack,
        "session_label": label,
        "session_stamp": stamp,
        "session_id_display": _trunc_session_id(sid) if sid else None,
        "port_8080_owners": owners,
        "freshness_class": fclass,
        "witness_live": fclass == FRESHNESS_LIVE,
        # Explicit absences -- UI must not invent these.
        # Field names avoid secret_shaped markers (no "key"/"secret"/"token" substrings).
        "signing_material_present": False,
        "consent_authority": False,
        "mock": False,
        "fabricated_liveness": False,
    }
    # Refuse secret-shaped keys (pack boundary rail)
    bad = [k for k in snap if secret_shaped(str(k))]
    if bad:
        raise ValueError(f"status snapshot refused secret-shaped key(s): {bad}")
    return snap


def build_stream_view_model(snapshot: dict) -> dict:
    """PKG-UI-01 pure: what the gamer Stream View shows mid-match (and what it hides).

    Novelty: 'your witness is live' -- a single presence respiration from freshness_class,
    not an FPS-counter clone. Deliberately absent: counts, biometrics, green-check theater.
    """
    if not isinstance(snapshot, dict):
        snapshot = {}
    fclass = snapshot.get("freshness_class") or FRESHNESS_UNKNOWN
    node = snapshot.get("node_state") or NODE_STATE_UNPROVISIONED
    witness_live = bool(snapshot.get("witness_live")) or fclass == FRESHNESS_LIVE
    if witness_live and node == NODE_STATE_LIVE:
        presence_line = "your witness is live"
        presence_tone = "live"
    elif fclass == FRESHNESS_FRESH:
        presence_line = "witness recent -- not mid-pulse"
        presence_tone = "recent"
    elif fclass == FRESHNESS_STALE:
        presence_line = "witness quiet -- ring not advancing"
        presence_tone = "quiet"
    elif fclass == FRESHNESS_EMPTY:
        presence_line = "no capture in this session ring yet"
        presence_tone = "empty"
    else:
        presence_line = "witness state unknown"
        presence_tone = "unknown"
    # Mid-match: minimal HUD only
    on_screen = {
        "presence_line": presence_line,
        "presence_tone": presence_tone,
        "node_state": node,
        "freshness_class": fclass,
        "session_id_display": snapshot.get("session_id_display"),
        "session_label": snapshot.get("session_label"),
        "pack": snapshot.get("pack"),
        "f_t66b1_disclosure_visible": True,  # wherever authorship will later render
    }
    return {
        "schema": STREAM_VIEW_SCHEMA,
        "surface": "stream",
        "on_screen": on_screen,
        "deliberately_absent": sorted(STREAM_DELIBERATELY_ABSENT),
        "novelty": "witness_respiration",
        "novelty_note": ("Single presence indicator from capture-ring freshness-class; "
                         "not FPS, not crop counts, not biometric theater."),
        "mock": False,
        "fabricated_liveness": False,
        "signing_material_present": False,
        "consent_authority": False,
    }


def _verdict_tone(surface: str, verdict: str | None, *, present: bool) -> dict:
    """Map an artifact verdict to a dignified tone + gamer-facing line (never failure-shaming)."""
    v = (verdict or "").upper() if verdict else ""
    if not present:
        return {"tone": VERDICT_TONE_ABSENT, "verdict": None,
                "line": f"{surface}: not observed this session",
                "dignity": "honest_null"}
    if v in ("SYNCHRONIZED", "AUTHORED", "CERTIFY", "CLEAR", "PRESENT"):
        return {"tone": VERDICT_TONE_EARNED, "verdict": verdict,
                "line": f"{surface}: {verdict} (earned)",
                "dignity": "earned"}
    if v in ("PARTIAL", "PARTIAL_SURFACES"):
        return {"tone": VERDICT_TONE_PARTIAL, "verdict": verdict,
                "line": f"{surface}: {verdict} -- partial truth, held as-is",
                "dignity": "partial_truth"}
    if v in ("HYGIENE_FAIL",):
        return {"tone": VERDICT_TONE_HYGIENE, "verdict": verdict,
                "line": f"{surface}: capture hygiene -- not a player failure",
                "dignity": "hygiene_not_shame"}
    if v in ("UNVERIFIABLE", "NONE", "HONEST-NULL", "HONEST_NULL"):
        return {"tone": VERDICT_TONE_HONEST_NULL, "verdict": verdict,
                "line": f"{surface}: {verdict or 'honest-null'} -- not yet joinable",
                "dignity": "honest_null"}
    # Unknown verdict string: still AS-IS, never upgrade
    return {"tone": VERDICT_TONE_PARTIAL, "verdict": verdict,
            "line": f"{surface}: {verdict} (as-is)",
            "dignity": "as_is"}


def build_receipt_reveal_model(label: str, kas: dict | None, posp: dict | None,
                               v3: dict | None, manifest: dict | None, *,
                               pack: str = "?", stranger_verified: bool | None = None,
                               ring_age_s: float | None = None,
                               honesty_notes: list | None = None) -> dict:
    """PKG-UI-02 pure: stop-moment Receipt Reveal (LOCAL full + SHARE postcard) as data.

    Choreography stages are declarative (UI animates them); verdicts stay AS-IS.
    Honest-null / PARTIAL / HYGIENE_FAIL render as dignified truth, not red failure states.
    """
    notes = honesty_notes if honesty_notes is not None else build_honesty_notes()
    gap = next((n for n in notes if n.get("code") == "F-T66B-1"), None)
    surfaces = {
        "posp": _verdict_tone("PoSP", (posp or {}).get("verdict"), present=bool(posp)),
        "kas": _verdict_tone("KAS", (kas or {}).get("verdict"), present=bool(kas)),
        "v3": (_verdict_tone("RETINA-STATE-v3", "present", present=True) if v3
               else _verdict_tone("RETINA-STATE-v3", "honest-null", present=False)),
    }
    # Share surface uses coarser freshness; never crop counts
    share_fresh = freshness_for_share(ring_age_s)
    local_text = render_receipt(label, kas, posp, v3, manifest,
                                stranger_verified=stranger_verified, pack=pack,
                                honesty_notes=notes)
    share_text = render_share_postcard(label, kas, posp, v3, manifest,
                                       stranger_verified=stranger_verified, pack=pack,
                                       ring_age_s=ring_age_s, honesty_notes=notes)
    return {
        "schema": RECEIPT_REVEAL_SCHEMA,
        "session_label": label,
        "pack": pack,
        "choreography": [
            {"stage": "SETTLE", "ms": 400, "copy": "session closed -- sealing the pack"},
            {"stage": "SURFACES", "ms": 800, "copy": "presence + authorship + state"},
            {"stage": "HONESTY", "ms": 500, "copy": "known gaps disclosed, never hidden"},
            {"stage": "SHARE_SPLIT", "ms": 600,
             "copy": "LOCAL full stays here; SHARE postcard is redacted for strangers"},
        ],
        "surfaces": surfaces,
        "f_t66b1": {
            "code": "F-T66B-1",
            "status": (gap or {}).get("status", "OPEN"),
            "visible_on_local": True,
            "visible_on_share": True,
            "line": "incomplete -- not hidden. Zero-false-read holds.",
        },
        "local": {
            "surface": "LOCAL",
            "redaction": "none",
            "body_text": local_text,
            "shows_full_preimages": True,
        },
        "share": {
            "surface": "SHARE",
            "redaction": "qortroller-share-v1",
            "body_text": share_text,
            "freshness_class": share_fresh,
            "shows_full_preimages": False,
            "shows_crop_counts": False,
        },
        "stranger_verified": stranger_verified,
        "mock": False,
        "signing_material_present": False,
        "consent_authority": False,
    }


def build_birth_ceremony_map(home: Path) -> dict:
    """PKG-UI-03 pure: setup wizard stages as a guided visual flow map.

    ROI is the inherently visual y/N moment (check.png). Node-birth FEELS like a
    staged witness provisioning, not an app installer progress bar.
    """
    home = Path(home)
    node = home / "node.toml"
    roi_pass = home / "setup" / "stage3_roi_pass.json"
    roi_png = home / "setup" / "stage3_roi_check.png"
    stage4 = home / "setup" / "stage4_controller_pass.json"
    birth = home / "birth_receipt.json"
    cfg = read_node_config(node) if node.exists() else {}

    def _st(done: bool, current: bool) -> str:
        if done:
            return "done"
        if current:
            return "current"
        return "pending"

    has_node = node.exists()
    has_roi = roi_pass.exists()
    has_s4 = stage4.exists()
    has_birth = birth.exists()
    # First incomplete stage is current
    stages = []
    stages.append({
        "id": "port", "n": 0, "title": "Host preflight",
        "verb": "qortroller setup",
        "feel": "clear the channel -- no phantom port owns the witness seat",
        "visual": "port_owner_list",
        "status": _st(has_node, not has_node),
    })
    stages.append({
        "id": "card", "n": 1, "title": "Capture card",
        "verb": "qortroller setup",
        "feel": "pick the game HDMI frame, not the webcam",
        "visual": "uvc_frame_pick",
        "status": _st(has_node, has_node and not has_roi and not has_s4 and not has_birth),
    })
    stages.append({
        "id": "roi", "n": 3, "title": "Killfeed ROI",
        "verb": "qortroller setup --stage roi",
        "feel": "the y/N judgment -- does this box frame the killfeed?",
        "visual": "roi_overlay_png",
        "overlay_path": str(roi_png) if roi_png.exists() else None,
        "overlay_exists": roi_png.exists(),
        "status": _st(has_roi, has_node and not has_roi),
    })
    stages.append({
        "id": "controller", "n": 4, "title": "Controller presence",
        "verb": "qortroller setup --stage controller",
        "feel": "Edge on USB -- dual-connection note (USB laptop + BT PS5)",
        "visual": "hid_presence",
        "status": _st(has_s4, has_roi and not has_s4),
    })
    path_b = bool(cfg.get("stage5_deferred", False))
    stages.append({
        "id": "drill", "n": 5, "title": "First proof (birth)",
        "verb": "qortroller drill" + (" --path B" if path_b else ""),
        "feel": "your node is born when the first honest pack seals -- SYNCHRONIZED not required",
        "visual": "receipt_reveal",
        "path_b_deferred": path_b,
        "status": _st(has_birth, has_s4 and not has_birth),
    })
    ns = compute_node_state(home)
    return {
        "schema": BIRTH_CEREMONY_SCHEMA,
        "node_state": ns.get("state"),
        "node_detail": ns.get("detail"),
        "stages": stages,
        "ceremony_complete": has_birth,
        "feel_summary": ("Witness-node birth: staged provisioning with a visual ROI judgment "
                         "and an honest first pack -- not an installer progress bar."),
        "signing_material_present": False,
        "consent_authority": False,
    }


def parse_share_claims(text: str) -> dict:
    """PKG-D-12: extract claimed labels from a SHARE postcard (markdown or plain). Fail-soft."""
    claims: dict = {"posp": None, "kas": None, "v3": None, "f_t66b1": False,
                    "kas_prefix": None, "v3_prefix": None, "retina_prefix": None}
    low = text
    import re
    m = re.search(r"PoSP\s*:\s*(\S+)", low)
    if m:
        claims["posp"] = m.group(1).strip()
    m = re.search(r"KAS:\s*(\S+)", low)
    if m:
        claims["kas"] = m.group(1).strip()
    if "honest-null" in low and "RETINA-STATE-v3" in low:
        claims["v3"] = "honest-null"
    elif "RETINA-STATE-v3" in low and "present" in low:
        claims["v3"] = "present"
    claims["f_t66b1"] = "F-T66B-1" in low
    m = re.search(r"kas\s+([0-9a-fA-F]{8,16})\.\.\.", low)
    if m:
        claims["kas_prefix"] = m.group(1).lower()
    m = re.search(r"v3\s+([0-9a-fA-F]{8,16})\.\.\.", low)
    if m:
        claims["v3_prefix"] = m.group(1).lower()
    m = re.search(r"retina\s+([0-9a-fA-F]{8,16})\.\.\.", low)
    if m:
        claims["retina_prefix"] = m.group(1).lower()
    return claims


def verify_share_postcard(text: str, *, kas: dict | None = None, posp: dict | None = None,
                          v3: dict | None = None, pack_provided: bool = False) -> dict:
    """PKG-D-12: two-tier stranger check. Postcard alone is INDICATIVE_ONLY -- never STRANGER_OK.

    With pack artifacts (kas/posp/v3 dicts): prefix-match roots + verdict equality + F-T66B-1
    presence when required. Returns {tier, verdict, checks, note}.
    """
    claims = parse_share_claims(text)
    if not pack_provided and kas is None and posp is None and v3 is None:
        return {"tier": "POSTCARD", "verdict": "INDICATIVE",
                "checks": [{"name": "postcard_parse", "ok": True,
                            "detail": f"claims posp={claims.get('posp')} kas={claims.get('kas')}"}],
                "note": "INDICATIVE_ONLY -- postcard is not a proof; re-verify with --pack"}

    checks = []
    mismatches = []

    def _pfx_ok(claimed, full) -> bool:
        if not claimed:
            return full in (None, "", "null")  # both empty ok
        s = str(full or "").lower().replace("0x", "")
        return bool(s) and s.startswith(claimed.lower())

    # (1) PoSP verdict equality (never upgrade)
    if posp is not None:
        local_v = str(posp.get("verdict") or "none")
        ok = claims.get("posp") == local_v
        checks.append({"name": "posp_verdict", "ok": ok,
                       "detail": f"card={claims.get('posp')} local={local_v}"})
        if not ok:
            mismatches.append("posp_verdict")
    # (2) KAS verdict
    if kas is not None:
        local_v = str(kas.get("verdict") or "none")
        ok = claims.get("kas") == local_v
        checks.append({"name": "kas_verdict", "ok": ok,
                       "detail": f"card={claims.get('kas')} local={local_v}"})
        if not ok:
            mismatches.append("kas_verdict")
    # (3) root prefixes
    if kas is not None and claims.get("kas_prefix"):
        ok = _pfx_ok(claims["kas_prefix"], kas.get("commitment"))
        checks.append({"name": "kas_prefix", "ok": ok, "detail": claims["kas_prefix"]})
        if not ok:
            mismatches.append("kas_prefix")
    if v3 is not None and claims.get("v3_prefix"):
        ok = _pfx_ok(claims["v3_prefix"], v3.get("commitment"))
        checks.append({"name": "v3_prefix", "ok": ok, "detail": claims["v3_prefix"]})
        if not ok:
            mismatches.append("v3_prefix")
    if posp is not None and claims.get("retina_prefix"):
        er = posp.get("events_roots") or {}
        ok = _pfx_ok(claims["retina_prefix"], er.get("retina_perception_root"))
        checks.append({"name": "retina_prefix", "ok": ok, "detail": claims["retina_prefix"]})
        if not ok:
            mismatches.append("retina_prefix")
    # (4) F-T66B-1 must stay disclosed
    ok_gap = bool(claims.get("f_t66b1"))
    checks.append({"name": "f_t66b1_disclosed", "ok": ok_gap,
                   "detail": "present" if ok_gap else "MISSING on postcard"})
    if not ok_gap:
        mismatches.append("f_t66b1")

    if not checks:
        return {"tier": "PACK", "verdict": "INCOMPLETE_PACK",
                "checks": [], "note": "pack artifacts missing -- cannot stranger-check"}
    if mismatches:
        return {"tier": "PACK", "verdict": "MISMATCH", "checks": checks,
                "note": f"mismatch: {','.join(mismatches)}"}
    return {"tier": "PACK", "verdict": "STRANGER_OK", "checks": checks,
            "note": "prefix+verdict match; full crypto on local pack only"}


def append_dogfood_event(home: Path, event: dict, *, enabled: bool) -> None:
    """PKG-D-14: optional local friction telemetry. Allowlisted fields only; never biometrics."""
    if not enabled:
        return
    # Fail-closed field allowlist (names only -- values still must not be secret-shaped keys)
    allowed = {"event", "stage", "duration_ms", "choice", "n_loops", "recapture_count",
               "preflight_code", "play_ok", "stop_ok", "receipt_ok", "pack", "ts", "path",
               "friction_code"}
    safe = {k: v for k, v in event.items() if k in allowed and not secret_shaped(str(k))}
    if "event" not in safe:
        return
    safe.setdefault("ts", int(time.time()))
    path = home / "dogfood_events.jsonl"
    home.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(safe, separators=(",", ":")) + "\n")


def dogfood_enabled(cfg: dict | None = None) -> bool:
    """Default OFF. Explicit node.toml dogfood_telemetry=true or env QORTROLLER_DOGFOOD=1."""
    if os.environ.get("QORTROLLER_DOGFOOD", "").strip() in ("1", "true", "TRUE", "yes"):
        return True
    cfg = cfg or {}
    return bool(cfg.get("dogfood_telemetry", False))


def render_receipt(label: str, kas: dict | None, posp: dict | None, v3: dict | None,
                   manifest: dict | None, *, stranger_verified: bool | None = None,
                   pack: str = "?", honesty_notes: list | None = None) -> str:
    """PKG-D-03: the human Proof Receipt over the machine artifacts. Honest verdicts AS-IS."""
    notes = honesty_notes if honesty_notes is not None else build_honesty_notes()
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
          "-" * 62]
    L += format_honesty_notes(notes, share=False)
    L.append("=" * 62)
    return "\n".join(L)


def _trunc_hex(h, keep: int = 16) -> str:
    """Truncate a hex root/commitment for the SHARE surface: prefix only, uniqueness-claimable but
    not a full join key. None/empty -> 'null'."""
    s = str(h or "")
    return (s[:keep] + "...") if len(s) > keep else (s or "null")


def _trunc_session_id(sid) -> str:
    """SHARE form of a session id: first4...last4 (or 'null')."""
    s = str(sid or "")
    return f"{s[:4]}...{s[-4:]}" if len(s) > 12 else (s or "null")


def render_share_postcard(label: str, kas: dict | None, posp: dict | None, v3: dict | None,
                          manifest: dict | None, *, stranger_verified: bool | None = None,
                          pack: str = "?", ring_age_s: float | None = None,
                          honesty_notes: list | None = None) -> str:
    """PKG-D-09: the SHARE-redacted postcard. FROZEN Phase D redaction matrix (fail-closed omit):
    verdicts AS-IS (never rounded up) + F-T66B-1 disclosure ALWAYS; session_id truncated; device ids /
    absolute paths / usernames NEVER; roots truncated to 16-hex prefix; crop counts -> freshness CLASS
    only (counts without age mislead -- the T6.6b lesson)."""
    fresh_class = freshness_for_share(ring_age_s)
    er = (posp or {}).get("events_roots") or {}
    notes = honesty_notes if honesty_notes is not None else build_honesty_notes()
    # Always surface F-T66B-1 line on SHARE (trust requires the gap) even if notes evolve.
    gap_line = next((n for n in notes if n.get("code") == "F-T66B-1"), None)
    gap_status = (gap_line or {}).get("status", "OPEN")
    L = ["+" + "-" * 52 + "+",
         "|  QorTroller - Proof Postcard",
         '|  "I played. My node observed. This is the',
         '|   cryptographic shape of that session."',
         "|",
         f"|  Session : {label}  ({time.strftime('%Y-%m-%d')})",
         f"|  Pack    : {pack}",
         f"|  PoSP    : {(posp or {}).get('verdict', 'none')}"
         f"    KAS: {(kas or {}).get('verdict', 'none')}",
         f"|  RETINA-STATE-v3 : {'present' if v3 else 'honest-null'}"
         + (f"  verified={stranger_verified}" if stranger_verified is not None else ""),
         f"|  Archive : {fresh_class}",
         "|",
         f"|  Known gap (disclosed): F-T66B-1 [{gap_status}]",
         "|  incomplete -- not hidden. Zero-false-read holds.",
         "|",
         f"|  Roots (prefix only): kas {_trunc_hex((kas or {}).get('commitment'))}",
         f"|    v3 {_trunc_hex((v3 or {}).get('commitment'))}"
         f"  retina {_trunc_hex(er.get('retina_perception_root'))}",
         "|  Full preimages: local receipt only.",
         "|  Stranger verify: qortroller verify --share <this> --pack <dir>",
         "+" + "-" * 52 + "+"]
    return "\n".join(L)


def html_wrap(title: str, body_text: str) -> str:
    """Minimal offline HTML receipt (PKG-D-09): single page, brand tokens, print-friendly, ZERO live
    calls -- a static artifact around the canonical text."""
    import html as _html
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{_html.escape(title)}</title>"
            "<style>body{background:#0a0a0a;color:#e8e8e8;font-family:Consolas,monospace;"
            "padding:2rem;max-width:720px;margin:auto}pre{white-space:pre-wrap;"
            "border:1px solid #ff6a00;padding:1.2rem;border-radius:6px}"
            "h1{color:#ff6a00;font-size:1.1rem}em{color:#00e5ff}</style></head>"
            f"<body><h1>{_html.escape(title)}</h1>"
            f"<pre>{_html.escape(body_text)}</pre>"
            "<em>Offline artifact - verify with: python scripts/qortroller.py verify</em>"
            "</body></html>")


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
    """Apply the session env (frictions #2/#3): same values at play AND stop, from config not memory.
    PKG-D-10: the pack envelope is applied FIRST, then the session-specific knobs."""
    apply_pack_env(str(cfg.get("pack", "observer-only")), os.environ)
    os.environ["RETINA_KF_ENGINE"] = str(cfg.get("kf_engine", "rapidocr"))
    os.environ["RETINA_STATE_V3_EMIT_ENABLED"] = "true" if cfg.get("emit_v3", True) else "false"
    os.environ["RETINA_KILLFEED_CAPTURE_DIR"] = capture_dir


# ---------------------------------------------------------------- verbs

def _grab_still(index: int, out_path: Path) -> bool:
    """One warmed-up frame from the card (the C0 open-path). Fail-open -> False with guidance."""
    try:
        import cv2
        cap = cv2.VideoCapture(index, getattr(cv2, "CAP_DSHOW", 0))
        if not cap.isOpened():
            cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        frame = None
        for _ in range(20):
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
        cap.release()
        if frame is None:
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), frame)
        return True
    except Exception:  # noqa: BLE001
        return False


def _setup_stage_roi(cfg: dict) -> int:
    """PKG-D-07: Stage 3 ROI ceremony -- still -> overlay -> operator y/N decision loop. The human
    judgment ("does the green box sit on the feed?") is the product moment; the ack is persisted."""
    import hashlib
    sys.path.insert(0, str(_REPO / "scripts"))
    from retina_crop_recalibrate import draw_overlay, parse_roi  # noqa: PLC0415
    setup_dir = _HOME / "setup"
    roi_s = str(cfg.get("killfeed_roi", _DEFAULTS["killfeed_roi"]))
    while True:
        stamp = int(time.time())
        still = setup_dir / f"roi_still_{stamp}.png"
        print("- Stage 3: KILLFEED ROI -- freezing one frame from the card...")
        if not _grab_still(int(cfg.get("uvc_index", 1)), still):
            print("  FAIL: no frame. Card busy (OBS/Camera open?) or wrong index -- re-run stage 1.")
            return 1
        overlay = setup_dir / f"roi_overlay_{stamp}.png"
        roi = parse_roi(roi_s)
        if roi is None:
            print(f"  invalid ROI {roi_s!r}; resetting to default")
            roi_s = _DEFAULTS["killfeed_roi"]
            roi = parse_roi(roi_s)
        draw_overlay(str(still), str(overlay), [("killfeed", roi)])
        try:
            os.startfile(str(overlay))  # noqa: S606 -- Windows default viewer (operator machine)
        except Exception:  # noqa: BLE001
            pass
        print(f"  overlay -> {overlay}")
        print("  Look at the GREEN box. Does it sit on the killfeed text?")
        ans = input("  [y] correct  [n] enter new fractions  [r] re-capture  [q] quit stage: ").strip().lower()
        if ans == "y":
            cfg["killfeed_roi"] = roi_s
            write_flat_toml(_NODE_TOML, cfg)
            pass_rec = {"roi": roi_s, "still_sha256": hashlib.sha256(still.read_bytes()).hexdigest(),
                        "ts": stamp, "operator_ack": True}
            (setup_dir / "stage3_roi_pass.json").write_text(json.dumps(pass_rec, indent=2), encoding="utf-8")
            print(f"  ROI acked + persisted -> {_NODE_TOML}")
            print("  Next: setup --stage controller  ->  drill (or drill --path B)")
            return 0
        if ans == "n":
            roi_s = input("  new ROI 'fx,fy,fw,fh' (fractions 0..1): ").strip()
        elif ans == "q":
            print("  stage aborted; node.toml unchanged")
            return 1


def _setup_stage_controller(cfg: dict) -> int:
    """PKG-D-15: Stage 4 controller presence -- HID VID/PID + dual-connection note.

    Persist ONLY display-safe fields (vid/pid/product/present/acks). Never serial, never HID path.
    Soft-skip allowed (operator_skip) so pure-observation dogfood is not blocked without Edge USB.
    """
    setup_dir = _HOME / "setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    print("- Stage 4: CONTROLLER PRESENCE (DualSense Edge CFI-ZCP1)")
    print(DUAL_CONNECTION_NOTE)
    print(f"  Looking for USB HID {EDGE_VID:04X}:{EDGE_PID:04X} ...")
    while True:
        presence = probe_controller_presence()
        mark = "FOUND" if presence.get("present") else "NOT FOUND"
        print(f"  [{mark}] product={presence.get('product')}  "
              f"vid:pid={presence.get('vid_hex')}:{presence.get('pid_hex')}  "
              f"n={presence.get('n_matches')}  via={presence.get('detection')}")
        if presence.get("note"):
            print(f"  note: {presence['note']}")
        # DISPLAY-only line (not persisted): reminder of what we refuse to store
        print("  (serial number + HID path are NEVER stored -- presence is VID/PID + product only)")
        if presence.get("present"):
            ans = input("  [y] ack presence  [r] re-probe  [q] quit stage: ").strip().lower()
            if ans == "y":
                rec = build_stage4_pass_record(
                    presence, operator_ack=True, dual_connection_note_shown=True, operator_skip=False)
                (setup_dir / "stage4_controller_pass.json").write_text(
                    json.dumps(rec, indent=2), encoding="utf-8")
                print(f"  Stage 4 acked -> {setup_dir / 'stage4_controller_pass.json'}")
                print("  Next: drill (Path A)  OR  drill --path B  then play a real match + stop")
                append_dogfood_event(_HOME, {"event": "stage4_ack", "stage": "controller",
                                             "choice": "present"},
                                     enabled=dogfood_enabled(cfg))
                return 0
            if ans == "q":
                print("  stage aborted; no stage4 pass written")
                return 1
            continue
        # not present
        ans = input("  [r] re-probe  [s] soft-skip (ceremony continues; present=false)  "
                    "[q] quit: ").strip().lower()
        if ans == "s":
            rec = build_stage4_pass_record(
                presence, operator_ack=True, dual_connection_note_shown=True, operator_skip=True)
            (setup_dir / "stage4_controller_pass.json").write_text(
                json.dumps(rec, indent=2), encoding="utf-8")
            print("  Stage 4 soft-skipped (present=false, operator_skip=true) -- first proof still allowed.")
            print("  Re-run setup --stage controller later when Edge is USB-connected.")
            append_dogfood_event(_HOME, {"event": "stage4_skip", "stage": "controller",
                                         "choice": "skip"},
                                 enabled=dogfood_enabled(cfg))
            return 0
        if ans == "q":
            print("  stage aborted; no stage4 pass written")
            return 1
        # r or anything else -> re-probe


def cmd_setup(a) -> int:
    stage = getattr(a, "stage", "all")
    if stage == "roi":
        return _setup_stage_roi(read_node_config())
    if stage == "controller":
        return _setup_stage_controller(read_node_config())
    print("QorTroller node provisioning (stages 0-1 + `--stage roi` + `--stage controller`)")
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
    # PKG-D-14: explicit dogfood telemetry flip (default remains off / prior value)
    if getattr(a, "dogfood_telemetry", None) == "on":
        cfg["dogfood_telemetry"] = True
        print("- dogfood telemetry: ON (local ~/.qortroller/dogfood_events.jsonl only; no upload)")
    elif getattr(a, "dogfood_telemetry", None) == "off":
        cfg["dogfood_telemetry"] = False
        print("- dogfood telemetry: OFF")
    write_flat_toml(_NODE_TOML, cfg)
    print(f"- node config written -> {_NODE_TOML}")
    print("  Reminders: PS5 HDCP OFF (Settings > System > HDMI); OBS/Camera CLOSED (single-holder).")
    print("  Next: setup --stage roi  ->  setup --stage controller  ->  drill / drill --path B")
    return 0


def _rp5_gate(*, capture_dir: str | None = None, force: bool = False) -> int:
    """PKG-D-11: wire RP-5 (match_preflight) before capture. Exit 0=GO/GO_WITH_WARNINGS, 1=NO_GO.

    Never silent-skip. --i-know (force=True) logs override and proceeds (operator only).
    """
    cmd = [sys.executable, str(_REPO / "scripts" / "match_preflight.py")]
    if capture_dir:
        cmd += ["--capture-dir", capture_dir]
    try:
        rc = subprocess.call(cmd, cwd=str(_REPO))
    except Exception as e:  # noqa: BLE001
        print(f"RP-5 preflight unavailable ({e!r}) -- treating as UNVERIFIABLE/NO_GO")
        rc = 2
    # match_preflight: 0=GO, 1=GO_WITH_WARNINGS, 2=NO_GO
    if rc in (0, 1):
        if rc == 1:
            print("RP-5: GO_WITH_WARNINGS -- proceed with eyes open")
        return 0
    print("RP-5: NO_GO -- contention hygiene failed (OBS/zombie python/CPU/DB/stale ring).")
    print("  Fix blockers above, or re-run with --i-know if you accept the risk (logged).")
    if force:
        print("  OVERRIDE: --i-know accepted; proceeding anyway (operator ack).")
        append_dogfood_event(_HOME, {"event": "rp5_override", "preflight_code": "NO_GO_FORCE"},
                             enabled=dogfood_enabled(read_node_config()))
        return 0
    append_dogfood_event(_HOME, {"event": "rp5_block", "preflight_code": "NO_GO"},
                         enabled=dogfood_enabled(read_node_config()))
    return 1


def cmd_play(a) -> int:
    cfg = read_node_config()
    force = bool(getattr(a, "i_know", False))
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
    # PKG-D-11: RP-5 contention gate (CLEAR required unless --i-know)
    if _rp5_gate(force=force) != 0:
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
    append_dogfood_event(_HOME, {"event": "play_start", "pack": str(cfg.get("pack")), "play_ok": True},
                         enabled=dogfood_enabled(cfg))
    return subprocess.call(cmd, cwd=str(_REPO))


def cmd_status(a) -> int:
    """Honest liveness + node birth state. PKG-UI-04: --json emits the status snapshot."""
    as_json = bool(getattr(a, "json", False))
    write_ui = bool(getattr(a, "write_ui", False))
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=20).stdout
        owners = parse_netstat_owners(out, 8080)
    except Exception:  # noqa: BLE001
        owners = []
    st = load_session_state()
    cfg = read_node_config()
    cap_path = None
    n, age = 0, float("inf")
    if st and st.get("capture_dir"):
        cap_path = _REPO / st["capture_dir"]
        n, age = ring_freshness(cap_path, time.time())
    snap = build_status_snapshot(
        home=_HOME, session=st, port_owners=owners, capture_dir=cap_path,
        pack=str(cfg.get("pack", "observer-only")),
    )
    # Stream model always available for UI consumers (never printed unless --json)
    stream = build_stream_view_model(snap)
    if write_ui or as_json:
        ui_dir = _HOME / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "status.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
        (ui_dir / "stream.json").write_text(json.dumps(stream, indent=2), encoding="utf-8")
    if as_json:
        print(json.dumps({"status": snap, "stream": stream}, indent=2))
        return 0
    # Human terminal path (unchanged honesty; still notes freshness vs counts)
    print(f"port 8080 owner(s): {owners or 'none'}")
    if st:
        fresh = snap.get("freshness_class", "?")
        print(f"session ring: {st['capture_dir']}  crops={n}  newest_age={age:.0f}s  [{fresh}]")
        print("  (freshness, not counts, proves capture -- a full ring can be a previous session)")
    print(f"node state: {snap.get('node_state')}  -- {snap.get('node_detail')}")
    print(f"witness: {stream['on_screen']['presence_line']}")
    subprocess.call([sys.executable, str(_DAEMON), "status"], cwd=str(_REPO))
    return 0


def cmd_ui(a) -> int:
    """PKG-UI-04 thin: open/write the offline Stream shell (observes CLI JSON; no second plane).

    Does NOT start capture, hold keys, or talk to bridge auth. Serves only static files under
    ~/.qortroller/ui/ (status.json + stream.json + offline shell.html). Full SPA is GATED.
    """
    # Refresh snapshot first (best-effort)
    class _A:
        json = False
        write_ui = True
    cmd_status(_A())
    ui_dir = _HOME / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    shell = ui_dir / "stream_shell.html"
    shell.write_text(_stream_shell_html(), encoding="utf-8")
    # Also write birth ceremony map for setup wizard consumers
    ceremony = build_birth_ceremony_map(_HOME)
    (ui_dir / "ceremony.json").write_text(json.dumps(ceremony, indent=2), encoding="utf-8")
    print(f"[qortroller] ui shell -> {shell}")
    print(f"[qortroller] ui status -> {ui_dir / 'status.json'}")
    print(f"[qortroller] ui stream -> {ui_dir / 'stream.json'}")
    print(f"[qortroller] ui ceremony -> {ui_dir / 'ceremony.json'}")
    print("  Rails: offline shell reads local JSON only; no keys; no consent authority;")
    print("  noMock: if status.json is missing, shell shows UNKNOWN -- never fabricates LIVE.")
    if not getattr(a, "no_open", False):
        try:
            import webbrowser
            webbrowser.open(shell.resolve().as_uri())
        except Exception as e:  # noqa: BLE001
            print(f"  (browser open skipped: {e!r})")
    return 0


def _stream_shell_html() -> str:
    """Minimal offline Stream shell -- brand tokens, reads sibling status/stream JSON via file://
    is restricted by browsers; shell embeds a note to open via `qortroller ui` after status write,
    and shows last-known values from a same-dir fetch when served, else a static placeholder.

    Honesty: never paints LIVE without a freshness_class==LIVE reading.
    """
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>QorTroller — Stream</title>
<style>
  :root { --void:#04060a; --amber:#f0a868; --cyan:#00e5ff; --ink:#e8e8e8; --dim:#6a7380; }
  html,body{margin:0;background:var(--void);color:var(--ink);
    font-family: 'JetBrains Mono', Consolas, monospace; min-height:100vh;}
  .wrap{max-width:520px;margin:0 auto;padding:2.5rem 1.5rem;}
  h1{color:var(--amber);font-size:0.95rem;letter-spacing:0.12em;text-transform:uppercase;
    font-weight:500;margin:0 0 2rem;}
  .pulse{width:14px;height:14px;border-radius:50%;display:inline-block;margin-right:0.6rem;
    background:var(--dim); box-shadow:0 0 0 0 transparent;}
  .pulse.live{background:var(--cyan); box-shadow:0 0 12px var(--cyan);
    animation: breath 2s ease-in-out infinite;}
  .pulse.recent{background:var(--amber);}
  .pulse.quiet,.pulse.empty,.pulse.unknown{background:var(--dim);}
  @keyframes breath{0%,100%{opacity:0.55}50%{opacity:1}}
  @media (prefers-reduced-motion: reduce){.pulse.live{animation:none}}
  .presence{font-size:1.25rem;line-height:1.4;margin:0.5rem 0 1.5rem;}
  .meta{color:var(--dim);font-size:0.8rem;line-height:1.7;}
  .meta b{color:var(--ink);font-weight:500;}
  .note{margin-top:2rem;padding:0.9rem 1rem;border:1px solid #1a2030;border-radius:6px;
    color:var(--dim);font-size:0.75rem;}
  .note em{color:var(--cyan);font-style:normal;}
</style></head>
<body><div class="wrap">
  <h1>QorTroller · Stream</h1>
  <div id="row"><span id="dot" class="pulse unknown"></span>
    <span class="presence" id="presence">loading local witness state…</span></div>
  <div class="meta">
    <div>node <b id="node">—</b></div>
    <div>freshness <b id="fresh">—</b></div>
    <div>session <b id="sid">—</b></div>
    <div>pack <b id="pack">—</b></div>
  </div>
  <div class="note">
    Offline shell · reads <em>stream.json / status.json</em> written by
    <em>qortroller status --json</em> or <em>qortroller ui</em>.
    Never fabricates LIVE. No keys. No consent authority. F-T66B-1 disclosed on receipt surfaces.
  </div>
</div>
<script>
/* noMock discipline: missing JSON => UNKNOWN, never LIVE */
async function load() {
  const set = (id, t) => { const e = document.getElementById(id); if (e) e.textContent = t; };
  const dot = document.getElementById('dot');
  try {
    const r = await fetch('stream.json', { cache: 'no-store' });
    if (!r.ok) throw new Error('no stream.json');
    const m = await r.json();
    const on = m.on_screen || {};
    set('presence', on.presence_line || 'witness state unknown');
    set('node', on.node_state || '—');
    set('fresh', on.freshness_class || 'UNKNOWN');
    set('sid', on.session_id_display || on.session_label || '—');
    set('pack', on.pack || '—');
    const tone = on.presence_tone || 'unknown';
    dot.className = 'pulse ' + tone;
  } catch (e) {
    set('presence', 'witness state unknown');
    set('fresh', 'UNKNOWN');
    set('node', '—');
    dot.className = 'pulse unknown';
  }
}
load();
setInterval(load, 3000);
</script>
</body></html>
"""


def _maybe_complete_path_b_birth(label: str, stamp, cfg: dict) -> None:
    """Path B birth: first successful stop after stage5_deferred writes birth_receipt."""
    birth_path = _HOME / "birth_receipt.json"
    if birth_path.exists():
        return
    if not cfg.get("stage5_deferred", False):
        return
    kas, posp, v3, _m = _collect_artifacts(label)
    birth = {"stages_passed": ["preflight", "path_b_match", "stop", "receipt"],
             "path": "B",
             "first_session_id": f"{label}_{stamp}",
             "verdicts_as_is": {"kas": (kas or {}).get("verdict"),
                                "posp": (posp or {}).get("verdict"),
                                "v3": "present" if v3 else "honest-null"},
             "f_t66b1_disclosed": True, "ts": int(time.time())}
    _HOME.mkdir(parents=True, exist_ok=True)
    birth_path.write_text(json.dumps(birth, indent=2), encoding="utf-8")
    # Clear deferred flag so status flips to NODE_BORN
    cfg = dict(cfg)
    cfg["stage5_deferred"] = False
    try:
        write_flat_toml(_NODE_TOML, cfg)
    except ValueError:
        pass
    print(f"[qortroller] Path B BIRTH complete -> {birth_path}")
    print("  (honest verdicts pass the birth; SYNCHRONIZED is earned, not required)")


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
    _maybe_complete_path_b_birth(st["label"], st.get("stamp", "?"), cfg)
    append_dogfood_event(_HOME, {"event": "stop", "stop_ok": rc == 0, "receipt_ok": True,
                                 "pack": str(cfg.get("pack"))},
                         enabled=dogfood_enabled(cfg))
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


def _print_and_write_receipt(label: str, cfg: dict, stranger_verified, *,
                             share: bool = False, html: bool = False) -> Path:
    kas, posp, v3, manifest = _collect_artifacts(label)
    pack = str(cfg.get("pack", "?"))
    text = render_receipt(label, kas, posp, v3, manifest,
                          stranger_verified=stranger_verified, pack=pack)
    out = _REPO / "audits" / f"session_receipt_{label}.md"
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"[qortroller] receipt -> {out.relative_to(_REPO)}")
    if html:
        h = _REPO / "audits" / f"session_receipt_{label}.html"
        h.write_text(html_wrap(f"QorTroller Session Receipt - {label}", text), encoding="utf-8")
        print(f"[qortroller] receipt html -> {h.relative_to(_REPO)}")
    if share:                                             # PKG-D-09: NEVER overwrites the local full file
        st = load_session_state() or {}
        age = None
        if st.get("capture_dir"):
            _, age = ring_freshness(_REPO / st["capture_dir"], time.time())
        card = render_share_postcard(label, kas, posp, v3, manifest,
                                     stranger_verified=stranger_verified, pack=pack, ring_age_s=age)
        sh = _REPO / "audits" / f"session_receipt_{label}.share.md"
        sh.write_text(card + "\n", encoding="utf-8")
        print(card)
        print(f"[qortroller] SHARE postcard -> {sh.relative_to(_REPO)} (redacted; full stays local)")
        if html:
            shh = _REPO / "audits" / f"session_receipt_{label}.share.html"
            shh.write_text(html_wrap(f"QorTroller Proof Postcard - {label}", card), encoding="utf-8")
            print(f"[qortroller] SHARE html -> {shh.relative_to(_REPO)}")
    return out


def cmd_receipt(a) -> int:
    st = load_session_state()
    label = a.label or (st and st.get("label"))
    if not label:
        print("no session known -- pass a label: qortroller receipt --label <label>")
        return 1
    _print_and_write_receipt(label, read_node_config(), stranger_verified=None,
                             share=getattr(a, "share", False), html=getattr(a, "html", False))
    return 0


def cmd_drill(a) -> int:
    """PKG-D-08 + PKG-D-11: Proof Drill birth ceremony.

    Path A (default): 90s scripted timeline -> auto-stop -> birth_receipt.
    Path B: RP-5 + port preflight only; stage5_deferred=true; operator plays a real match;
            first stop completes birth. Honest PASS = pack + receipt (never requires SYNCHRONIZED).
    """
    cfg = read_node_config()
    path = str(getattr(a, "path", "A") or "A").upper()
    force = bool(getattr(a, "i_know", False))

    class _A:  # play/stop take argparse-shaped objects
        pass

    # ----- Path B: provision for full-match first proof (no auto-stop) -----
    if path == "B":
        print("=" * 60)
        print("  PROOF DRILL Path B -- skip mini-session; first REAL match is birth")
        print("=" * 60)
        # Port + RP-5 only (do not start capture)
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=20).stdout
            owners = parse_netstat_owners(out, 8080)
        except Exception:  # noqa: BLE001
            owners = []
        if owners:
            print(f"  REFUSING: port 8080 LISTENING (pid={owners}). Clear before Path B.")
            return 1
        if _rp5_gate(force=force) != 0:
            return 1
        cfg = dict(cfg)
        cfg["stage5_deferred"] = True
        write_flat_toml(_NODE_TOML, cfg)
        print("  stage5_deferred=true written to node.toml")
        print("  node state will show: FIRST_PROOF_PENDING (provisioned, first proof pending)")
        print("  Next:  qortroller play --label <match>")
        print("         ... play your real match ...")
        print("         qortroller stop")
        print("  Birth completes on first stop that writes a receipt (honest-null OK).")
        append_dogfood_event(_HOME, {"event": "drill_path_b", "path": "B", "pack": str(cfg.get("pack"))},
                             enabled=dogfood_enabled(cfg))
        return 0

    # ----- Path A: 90s scripted drill -----
    label = f"proof_drill_{time.strftime('%Y%m%d_%H%M')}"
    print("=" * 60)
    print("  PROOF DRILL Path A -- your node's first proof (about 90 seconds)")
    print("=" * 60)
    pa = _A()
    pa.label = label
    pa.i_know = force
    if cmd_play(pa) != 0:
        print("  drill aborted at preflight (fix the port/card/RP-5 issue and re-run)")
        return 1
    script = [(15, "OPEN THE GAME -- get game pixels on the HDMI path (lobby or match)"),
              (30, "MAKE THE FEED MOVE -- scoreboard open ~5s, or play normally; no alt-tab"),
              (30, "CONTROLLER PRESENCE -- one L2/R2 press or stick wiggle on the USB pad"),
              (15, "HOLD ON -- stopping + rendering your receipt...")]
    for secs, line in script:
        print(f"  >> {line}  ({secs}s)")
        time.sleep(secs)
    sa = _A()
    rc = cmd_stop(sa)
    st = load_session_state() or {}
    kas, posp, v3, _m = _collect_artifacts(label)
    birth = {"stages_passed": ["preflight", "rp5", "capture", "stop", "receipt"],
             "path": "A",
             "first_session_id": f"{label}_{st.get('stamp', '?')}",
             "verdicts_as_is": {"kas": (kas or {}).get("verdict"), "posp": (posp or {}).get("verdict"),
                                "v3": "present" if v3 else "honest-null"},
             "f_t66b1_disclosed": True, "ts": int(time.time())}
    _HOME.mkdir(parents=True, exist_ok=True)
    (_HOME / "birth_receipt.json").write_text(json.dumps(birth, indent=2), encoding="utf-8")
    print(f"[qortroller] node BIRTH complete -> {_HOME / 'birth_receipt.json'}")
    print("  (honest verdicts pass the birth; SYNCHRONIZED is earned in real matches)")
    append_dogfood_event(_HOME, {"event": "drill_path_a", "path": "A", "pack": str(cfg.get("pack")),
                                 "stop_ok": rc == 0},
                         enabled=dogfood_enabled(cfg))
    return rc


def cmd_dogfood_report(a) -> int:
    """PKG-D-16: scaffold or validate a local dogfood report (operator fills; kit never uploads)."""
    validate_path = getattr(a, "validate", "") or ""
    if validate_path:
        p = Path(validate_path)
        if not p.exists():
            print(f"report not found: {p}")
            return 1
        try:
            report = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"invalid JSON: {e!r}")
            return 1
        ok, errs = validate_dogfood_report(report)
        if ok:
            print(f"dogfood report OK  schema={report.get('schema')}  "
                  f"bar={report.get('operator_would_rerun_without_chat')!r}")
            return 0
        print("dogfood report INVALID:")
        for e in errs:
            print(f"  - {e}")
        return 2
    if getattr(a, "scaffold", False):
        report = scaffold_dogfood_report(run_label=getattr(a, "label", "dogfood_1") or "dogfood_1",
                                         path=getattr(a, "path", "B") or "B",
                                         pack=str(read_node_config().get("pack", "observer-only")))
        out = _HOME / "dogfood_report.json"
        _HOME.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"scaffolded -> {out}")
        print("  Fill operator_would_rerun_without_chat (bool) after setup->roi->controller->"
              "play/drill->stop->receipt --share. Kit never uploads this file.")
        return 0
    print("usage: qortroller dogfood-report --scaffold | --validate <path>")
    return 1


def cmd_verify(a) -> int:
    """Offline stranger-check. PKG-D-12: --share postcard tier; optional --pack for STRANGER_OK."""
    share_file = getattr(a, "share_file", "") or ""
    pack_dir = getattr(a, "pack_dir", "") or ""

    if share_file:
        p = Path(share_file)
        if not p.exists():
            print(f"share postcard not found: {p}")
            return 1
        text = p.read_text(encoding="utf-8")
        kas = posp = v3 = None
        pack_provided = bool(pack_dir)
        label = getattr(a, "label", "") or ""
        if not label:
            name = p.name
            if name.startswith("session_receipt_") and ".share" in name:
                label = name[len("session_receipt_"):].split(".share")[0]
        if pack_provided and label:
            kas, posp, v3, _m = _collect_artifacts(label)
        result = verify_share_postcard(text, kas=kas, posp=posp, v3=v3, pack_provided=pack_provided)
        print(f"tier: {result['tier']}")
        print(f"verdict: {result['verdict']}")
        print(f"note: {result['note']}")
        for c in result.get("checks") or []:
            mark = "OK" if c.get("ok") else "FAIL"
            print(f"  [{mark}] {c.get('name')}: {c.get('detail')}")
        if result["verdict"] == "INDICATIVE":
            return 0  # informative, not an error
        if result["verdict"] == "STRANGER_OK":
            return 0
        return 2

    st = load_session_state()
    label = a.label or (st and st.get("label"))
    if not label:
        print("no session known -- pass a label: qortroller verify --label <label>")
        print("  or: qortroller verify --share <postcard.share.md> [--pack <session_or_audits>]")
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
    s = sub.add_parser("setup", help="node provisioning (stages 0-1; --stage roi = the R2 ROI ceremony)")
    s.add_argument("--uvc-index", type=int, default=None)
    s.add_argument("--killfeed-roi", default="")
    s.add_argument("--pack", default="observer-only", choices=sorted(PACKS))
    s.add_argument("--stage", default="all", choices=["all", "roi", "controller"],
                   help="all=stages 0-1; roi=Stage 3; controller=Stage 4 HID presence")
    s.add_argument("--dogfood-telemetry", choices=["on", "off"], default=None,
                   help="PKG-D-14: explicit local friction telemetry (default off)")
    s.set_defaults(fn=cmd_setup)
    # PKG-D-16: scaffold a local dogfood report for the operator's first full product run
    dr = sub.add_parser("dogfood-report",
                        help="scaffold/validate local dogfood report (never uploaded)")
    dr.add_argument("--scaffold", action="store_true",
                    help="write empty report template to ~/.qortroller/dogfood_report.json")
    dr.add_argument("--validate", default="",
                    help="path to an existing dogfood report JSON to validate")
    dr.add_argument("--label", default="dogfood_1", help="run_label for --scaffold")
    dr.add_argument("--path", default="B", choices=["A", "B"], help="drill path for --scaffold")
    dr.set_defaults(fn=cmd_dogfood_report)
    p = sub.add_parser("play", help="start a capture session (persisted config, session-scoped dirs)")
    p.add_argument("--label", default="")
    p.add_argument("--i-know", dest="i_know", action="store_true",
                   help="operator override for RP-5 NO_GO (logged)")
    p.set_defaults(fn=cmd_play)
    stt = sub.add_parser("status", help="honest liveness + node birth/provisioning state")
    stt.add_argument("--json", action="store_true",
                     help="PKG-UI-04: emit qortroller-status-snapshot-v1 + stream model as JSON")
    stt.add_argument("--write-ui", action="store_true",
                     help="write ~/.qortroller/ui/status.json + stream.json for the Stream shell")
    stt.set_defaults(fn=cmd_status)
    uip = sub.add_parser("ui", help="open offline Stream shell (observes CLI JSON; no second plane)")
    uip.add_argument("--no-open", action="store_true", help="write files only; do not open browser")
    uip.set_defaults(fn=cmd_ui)
    sub.add_parser("stop", help="end session + write the Proof Receipt").set_defaults(fn=cmd_stop)
    d = sub.add_parser("drill", help="Proof Drill birth (Path A=90s scripted; Path B=defer to real match)")
    d.add_argument("--path", default="A", choices=["A", "B", "a", "b"],
                   help="A=scripted mini-session (default); B=skip to full match (first-proof pending)")
    d.add_argument("--i-know", dest="i_know", action="store_true",
                   help="operator override for RP-5 NO_GO (logged)")
    d.set_defaults(fn=cmd_drill)
    r = sub.add_parser("receipt", help="(re)render the session receipt")
    r.add_argument("--label", default="")
    r.add_argument("--share", action="store_true", help="also write the SHARE-redacted postcard (*.share.md)")
    r.add_argument("--html", action="store_true", help="also write offline HTML surfaces")
    r.set_defaults(fn=cmd_receipt)
    v = sub.add_parser("verify", help="offline stranger-check (v3 crypto OR --share postcard tiers)")
    v.add_argument("--label", default="")
    v.add_argument("--share", dest="share_file", default="",
                   help="path to *.share.md postcard (INDICATIVE alone; STRANGER_OK with --pack)")
    v.add_argument("--pack", dest="pack_dir", default="",
                   help="optional session/audits context for prefix+verdict stranger check")
    v.set_defaults(fn=cmd_verify)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
