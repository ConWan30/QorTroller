#!/usr/bin/env python3
"""UC-15 runner -- render the self-analytics HTML from the two verified artifacts.

VERIFY-BEFORE-RENDER: both cited artifacts are re-verified (resume summary-integrity + strata
re-derivation) BEFORE any HTML is produced -- a page is never rendered from artifacts that no
longer verify. Offline, stdlib, no bridge, 0 IOTX.

  python scripts/build_self_analytics.py --resume audits/play_resume_2026-07-11.json \
      --strata audits/skill_strata_2026-07-11.json [--out audits/self_analytics_<date>.html]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.play_resume import sha256_bytes, verify_play_resume
from l9_presence.self_analytics import build_self_analytics_html, validate_self_view
from l9_presence.skill_strata import verify_strata_report


def _loader(path: str):
    p = path if os.path.isabs(path) else os.path.join(_REPO, path)
    try:
        return open(p, "rb").read()
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="UC-15 self-analytics HTML")
    ap.add_argument("--resume", required=True)
    ap.add_argument("--strata", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    refs = {}
    docs = {}
    for name, path in (("resume", a.resume), ("strata", a.strata)):
        raw = _loader(path)
        if raw is None:
            print(f"ERROR: {name} not found: {path}", file=sys.stderr)
            return 2
        rel = path if not os.path.isabs(path) else os.path.relpath(path, _REPO).replace("\\", "/")
        refs[name] = {"path": rel, "sha256": sha256_bytes(raw)}
        docs[name] = json.loads(raw.decode("utf-8"))

    err = validate_self_view(docs["resume"])
    if err:
        print(f"REFUSED (self-view rail): {err}", file=sys.stderr)
        return 1
    v1 = verify_play_resume(docs["resume"], _loader)
    v2 = verify_strata_report(docs["strata"], _loader)
    print(f"  resume verify : {'OK' if v1['ok'] else 'FAIL'} ({len(v1['checks'])} checks)")
    print(f"  strata verify : {'OK' if v2['ok'] else 'FAIL'} ({len(v2['checks'])} checks)")
    if not (v1["ok"] and v2["ok"]):
        for c in [c for c in v1["checks"] + v2["checks"] if not c["ok"]][:6]:
            print(f"    FAIL {c['name']}: {c['note']}", file=sys.stderr)
        print("REFUSED: artifacts no longer verify — fix them before rendering", file=sys.stderr)
        return 1

    page = build_self_analytics_html(docs["resume"], docs["strata"],
                                     resume_ref=refs["resume"], strata_ref=refs["strata"],
                                     generated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    out = a.out or os.path.join("audits", f"self_analytics_{time.strftime('%Y-%m-%d')}.html")
    outp = out if os.path.isabs(out) else os.path.join(_REPO, out)
    with open(outp, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"  written       : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
