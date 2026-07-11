#!/usr/bin/env python3
"""UC-2 runner -- build / verify the skill-strata report over a verified play-resume.

  build  : load a play-resume (UC-4), derive session demonstration bands, run the
           re-derivation verifier BEFORE writing, print the distribution.
  verify : re-verify an existing strata report (re-derive every label from the cited resume).

Offline, stdlib only, no DB, no rig, 0 IOTX.

  python scripts/build_skill_strata.py build --resume audits/play_resume_2026-07-11.json
  python scripts/build_skill_strata.py verify --report audits/skill_strata_<date>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.skill_strata import (DEFAULT_HIGH_DENSITY_KPM, build_strata_report,
                                      sha256_bytes, verify_strata_report)


def _loader(path: str):
    p = path if os.path.isabs(path) else os.path.join(_REPO, path)
    try:
        return open(p, "rb").read()
    except OSError:
        return None


def cmd_build(a) -> int:
    rp = a.resume if os.path.isabs(a.resume) else os.path.join(_REPO, a.resume)
    raw = open(rp, "rb").read()
    resume = json.loads(raw.decode("utf-8"))
    rel = os.path.relpath(rp, _REPO).replace("\\", "/")
    report = build_strata_report(resume, resume_path=rel, resume_sha256=sha256_bytes(raw),
                                 high_density_kpm=a.high_density_kpm,
                                 generated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    v = verify_strata_report(report, _loader)            # re-derivation mirror BEFORE writing
    sep = "-" * 72
    print(f"\n{sep}\n  SKILL-STRATA REPORT (session demonstration bands — never player rank)\n{sep}")
    print(f"  resume cited         : {rel}")
    print(f"  threshold            : {a.high_density_kpm} authored-kills/min (v0 provisional)")
    for band, n in report["distribution"].items():
        if n:
            print(f"    {band:24} {n}")
    print(f"  corpus-eligible      : {report['corpus_eligible_sessions']} / "
          f"{len(report['sessions'])} sessions")
    bad = [c for c in v["checks"] if not c["ok"]]
    print(f"  verifier (re-derive) : {'OK' if v['ok'] else 'FAIL'} "
          f"({len(v['checks'])} checks{', ' + str(len(bad)) + ' failed' if bad else ''})")
    for c in bad[:6]:
        print(f"    FAIL {c['name']}: {c['note']}")
    if not v["ok"]:
        return 1
    out = a.out or os.path.join("audits", f"skill_strata_{time.strftime('%Y-%m-%d')}.json")
    outp = out if os.path.isabs(out) else os.path.join(_REPO, out)
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    print(f"  written              : {out}\n{sep}\n")
    return 0


def cmd_verify(a) -> int:
    report = json.load(open(a.report, encoding="utf-8"))
    v = verify_strata_report(report, _loader)
    bad = [c for c in v["checks"] if not c["ok"]]
    print(json.dumps({"ok": v["ok"], "checks_total": len(v["checks"]),
                      "checks_failed": bad[:10]}, indent=2))
    print(f"\nOVERALL: {'VERIFIED (re-derived from cited resume)' if v['ok'] else 'FAIL'}")
    return 0 if v["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="UC-2 skill-strata build/verify")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--resume", required=True)
    b.add_argument("--high-density-kpm", type=float, default=DEFAULT_HIGH_DENSITY_KPM)
    b.add_argument("--out", default=None)
    b.set_defaults(fn=cmd_build)
    v = sub.add_parser("verify")
    v.add_argument("--report", required=True)
    v.set_defaults(fn=cmd_verify)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
