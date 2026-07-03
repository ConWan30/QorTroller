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

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(_REPO, "bridge"), _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

from l9_presence.kill_authorship_session import build_session_record  # noqa: E402

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_EV = re.compile(r"session-anchor: (\w+) regime=(\w+) sha=(\S+)")


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
                events.append({"ts": m.group(1), "event": e.group(1), "regime": e.group(2),
                               "sha": e.group(3)})
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
