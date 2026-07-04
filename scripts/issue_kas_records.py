#!/usr/bin/env python3
"""Retro-issue Kill-Authorship Session Records over archived matches (Increment 2 step 2; read-only).

For each (label, daemon log): parse the session's wall-clock span + anchor event trail + hygiene (last RGC
diag) + th2 coupling corroboration from the log, select that span's composites from retina_kf_composite.jsonl
(composite ts_ms is epoch ms — same clock family as the log lines), build the record, write one JSON per
session + a summary. These 5 records are the G4 POSITIVE corpus. No daemon, no live path, no chain."""
from __future__ import annotations

import ast
import glob
import json
import os
import re
import sys
import time
from typing import Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(_REPO, "bridge"), _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

from l9_presence.kill_authorship_session import build_session_record  # noqa: E402

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
# The optional ` engine=.. match=.. raw=..` tail is the C3 provenance (added 2026-07-03 after sess_ab showed
# the KAS trail carried engine/match/raw=None). raw is rest-of-line so a spacey misread can't break the parse;
# old logs without the tail still match (the group is optional).
_EV = re.compile(r"session-anchor: (\w+) regime=(\w+) sha=(\S+)"
                 r"(?: engine=(\S+) match=(\S+) raw=(.*))?\s*$")


def _epoch_ms(stamp: str) -> float:
    return time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S")) * 1000.0


def parse_log(path: str):
    first = last = None
    events = []
    diag = None
    coupled_true = 0
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = _TS.match(line)
            if m:
                last = m.group(1)
                if first is None:
                    first = m.group(1)
            e = _EV.search(line)
            if e and m:
                ev = {"ts": m.group(1), "event": e.group(1), "regime": e.group(2), "sha": e.group(3)}
                if e.group(4) is not None:                       # C3 provenance tail present
                    ev["engine"] = e.group(4)
                    ev["match_kind"] = None if e.group(5) == "-" else e.group(5)
                    ev["raw_read"] = None if e.group(6) in ("-", "") else e.group(6)
                events.append(ev)
            if "RGC diag: {" in line:
                try:
                    diag = ast.literal_eval(line.split("RGC diag: ", 1)[1].strip())
                except Exception:
                    pass
            if "'th2_coupled': True" in line:
                coupled_true += 1
    hygiene = None
    coupling = None
    if diag:
        hygiene = {"frame_errs": diag.get("frame_errs"), "frame_stall_s": diag.get("frame_stall_s"),
                   "ts_source": diag.get("ts_source")}
        coupling = {"th2_coupled_true_ticks": coupled_true,
                    "inline_classifications": diag.get("inline_classifications"),
                    "inline_composite_windows": diag.get("inline_composite_windows")}
    span = (_epoch_ms(first), _epoch_ms(last)) if first and last else None
    return span, events, hygiene, coupling


def issue_record_for_label(label: str, date_tag: str = "") -> Optional[dict]:
    """Issue ONE KAS record for a daemon session by label (newest log). Reusable by the daemon's
    session-close path (`retina_capture_daemon.py stop --kas`) and by ad-hoc retro-issuance. Returns the
    record dict (written to audits/) or None if the log/span is unusable."""
    logs = sorted(glob.glob(os.path.join(_REPO, f"retina_daemon_{label}_*.log")))
    if not logs:
        return None
    span, events, hygiene, coupling = parse_log(logs[-1])
    if span is None:
        return None
    a, b = span[0] - 10_000, span[1] + 120_000
    comps = []
    comp_path = os.path.join(_REPO, "retina_kf_composite.jsonl")
    if os.path.exists(comp_path):
        for l in open(comp_path, encoding="utf-8"):
            c = json.loads(l)
            if isinstance(c.get("ts_ms"), (int, float)) and a <= c["ts_ms"] <= b:
                comps.append(c)
    # HID lobe (dual-lobe fusion): the session's device-clock R2-onset events (retina_hid_events.jsonl). onset
    # t_ms is the device-clock wall-corrected ms — the SAME wall family as the log span, so the same window
    # selects it. Screen composites = outcome lobe; HID onsets = input lobe.
    hid_raw = []
    hid_path = os.path.join(_REPO, "retina_hid_events.jsonl")
    if os.path.exists(hid_path):
        for l in open(hid_path, encoding="utf-8"):
            try:
                r = json.loads(l)
            except Exception:  # noqa: BLE001 — a torn line never blocks issuance
                continue
            if isinstance(r.get("t_ms"), (int, float)) and a <= r["t_ms"] <= b:
                hid_raw.append(r)
    # B2: derive the session's screen-outcome events + unify into ONE events_root (screen lobe here; the HID
    # lobe joins when both are captured together — the root is dual-lobe-ready). Binds outcomes to the
    # commitment; fail-open (a root failure never blocks issuance).
    events_root = ev_scheme = ev_lobes = cross_lobe = None
    # C3: the session's bootstrap provenance (actual live model id + exact|fuzzy + raw read) parsed from the
    # candidate_cut log line — threaded as the screen-events provenance DEFAULT so every screen-lobe event (and
    # thus the events_root) carries the real recognizer identity, not None. Newest cut wins (stall-recut).
    prov = {}
    for ev in events:
        if ev.get("engine"):
            prov = {"engine": ev["engine"], "match_kind": ev.get("match_kind"),
                    "raw_read": ev.get("raw_read"), "anchor_sha": ev.get("sha")}
    try:
        from l9_presence.killfeed_hid_event import session_hid_events
        from l9_presence.killfeed_screen_event import session_screen_events
        from vapi_bridge.retina_session_root import cross_lobe_coherence, unify_session_events_root
        scr = session_screen_events(comps, provenance=prov or None)
        hid = session_hid_events(hid_raw)                 # HID lobe joins when co-captured (--hid-events); else []
        u = unify_session_events_root(screen_events=scr, hid_events=hid)   # lobes = ['screen'] or ['screen','hid']
        events_root, ev_scheme, ev_lobes = u["events_root"], u["scheme"], u["lobes"]
        cross_lobe = cross_lobe_coherence(scr, hid)       # advisory input->outcome latency readout (UNCALIBRATED)
    except Exception:  # noqa: BLE001
        pass
    rec = build_session_record(session_label=label, handle=os.environ.get("QORTROLLER_HANDLE", "QorTrola30"),
                               composites=comps, event_trail=events, hygiene=hygiene, coupling=coupling,
                               events_root=events_root, events_root_scheme=ev_scheme, events_root_lobes=ev_lobes,
                               cross_lobe=cross_lobe)
    d = rec.to_dict()
    date_tag = date_tag or time.strftime("%Y-%m-%d")
    out = os.path.join(_REPO, "audits", f"kas_record_{label}_{date_tag}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2)
    d["_path"] = out
    return d


def main():
    sessions = [("g3mp", "retina_daemon_g3mp_*.log"), ("g3wz2", "retina_daemon_g3wz2_*.log"),
                ("g3br_recut", "retina_daemon_g3br_recut_*.log"),
                ("g3br_gatedcut", "retina_daemon_g3br_gatedcut_*.log"),
                ("b2trace", "retina_daemon_b2trace_*.log")]
    comps_all = [json.loads(l) for l in open(os.path.join(_REPO, "retina_kf_composite.jsonl"),
                                             encoding="utf-8")]
    out_dir = os.path.join(_REPO, "audits")
    summary = []
    for label, pat in sessions:
        logs = sorted(glob.glob(os.path.join(_REPO, pat)))
        if not logs:
            print(f"{label}: no log found — skipped")
            continue
        span, events, hygiene, coupling = parse_log(logs[-1])
        if span is None:
            print(f"{label}: unparseable log span — skipped")
            continue
        a, b = span[0] - 10_000, span[1] + 120_000
        comps = [c for c in comps_all if isinstance(c.get("ts_ms"), (int, float)) and a <= c["ts_ms"] <= b]
        rec = build_session_record(session_label=label, handle="QorTrola30", composites=comps,
                                   event_trail=events, hygiene=hygiene, coupling=coupling)
        d = rec.to_dict()
        path = os.path.join(out_dir, f"kas_record_{label}_2026-07-03.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=2)
        summary.append({"label": label, "verdict": d["verdict"], "authored": d["authored_kills"],
                        "deaths": d["own_deaths"], "windows": d["windows_total"],
                        "anchor_tags": d["anchor_tags"], "commitment": d["commitment"][:16]})
        print(f"{label:14s} {d['verdict']:20s} authored={d['authored_kills']:2d} windows={d['windows_total']:3d} "
              f"tags={d['anchor_tags']} commit={d['commitment'][:16]}")
    with open(os.path.join(out_dir, "kas_records_summary_2026-07-03.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)


if __name__ == "__main__":
    main()
