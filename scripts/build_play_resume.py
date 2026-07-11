#!/usr/bin/env python3
"""UC-4 runner -- build / verify the verified play-resume.

  build  : scan an audits dir for KAS / PoSP / deferred records, roll them into ONE
           qortroller-play-resume-v0 document (REFERENCE-AND-BIND: path + sha256 per source),
           run the verifier mirror BEFORE writing, print the summary table.
  verify : re-verify an existing resume off-rig (summary-integrity: hashes + field re-extract
           + totals re-derive). The underlying crypto is each artifact's own verifier.

Offline, stdlib only, no rig, no chain, 0 IOTX.

  python scripts/build_play_resume.py build [--audits-dir audits] [--handle NAME] [--out PATH]
  python scripts/build_play_resume.py verify --resume audits/play_resume_<date>.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.play_resume import build_play_resume, sha256_bytes, verify_play_resume

_PATTERNS = (("kas", "kas_record_*.json"),
             ("posp", "posp_record_*.json"),
             ("deferred", "kas_deferred_record_*.json"))


def _load_sources(audits_dir: str) -> list:
    out = []
    for kind, pat in _PATTERNS:
        for p in sorted(glob.glob(os.path.join(audits_dir, pat))):
            try:
                raw = open(p, "rb").read()
                out.append({"kind": kind, "path": os.path.relpath(p, _REPO).replace("\\", "/"),
                            "sha256": sha256_bytes(raw),
                            "doc": json.loads(raw.decode("utf-8"))})
            except Exception as exc:  # noqa: BLE001 -- a bad file is skipped loudly, never crashes
                print(f"  skip (unreadable): {p} ({exc})", file=sys.stderr)
    return out


def _loader(path: str):
    p = path if os.path.isabs(path) else os.path.join(_REPO, path)
    try:
        return open(p, "rb").read()
    except OSError:
        return None


def cmd_build(a) -> int:
    audits = a.audits_dir if os.path.isabs(a.audits_dir) else os.path.join(_REPO, a.audits_dir)
    sources = _load_sources(audits)
    resume = build_play_resume(sources, handle=a.handle,
                               generated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    v = verify_play_resume(resume, _loader)          # verifier mirror BEFORE writing
    sep = "-" * 72
    t = resume["totals"]
    print(f"\n{sep}\n  VERIFIED PLAY-RESUME -- {resume.get('handle') or '(no handle)'}\n{sep}")
    print(f"  sessions             : {t['sessions']}  (PoSP SYNCHRONIZED: {t['posp_synchronized']})")
    print(f"  authored kills live  : {t['authored_kills_live']}")
    print(f"  authored deferred    : {t['authored_kills_deferred']}")
    print(f"  authored BEST        : {t['authored_kills_best']}  (per-session max, never sum)")
    for r in resume["sessions"]:
        k, d, p_ = r.get("kas") or {}, r.get("deferred") or {}, r.get("posp") or {}
        print(f"    {str(r['session'])[:34]:34} kas={str(k.get('verdict'))[:18]:18} "
              f"live={k.get('authored_kills') if k else '-'} "
              f"def={d.get('deferred_authored') if d else '-'} posp={p_.get('verdict') or '-'}")
    bad = [c for c in v["checks"] if not c["ok"]]
    print(f"  verifier             : {'OK' if v['ok'] else 'FAIL'} "
          f"({len(v['checks'])} checks{', ' + str(len(bad)) + ' failed' if bad else ''})")
    for c in bad[:6]:
        print(f"    FAIL {c['name']}: {c['note']}")
    if not v["ok"]:
        return 1
    out = a.out or os.path.join("audits", f"play_resume_{time.strftime('%Y-%m-%d')}.json")
    outp = out if os.path.isabs(out) else os.path.join(_REPO, out)
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(resume, fh, indent=2, sort_keys=True)
    print(f"  written              : {out}\n{sep}\n")
    return 0


def cmd_verify(a) -> int:
    resume = json.load(open(a.resume, encoding="utf-8"))
    v = verify_play_resume(resume, _loader)
    bad = [c for c in v["checks"] if not c["ok"]]
    print(json.dumps({"ok": v["ok"], "checks_total": len(v["checks"]),
                      "checks_failed": [c for c in bad][:10]}, indent=2))
    print(f"\nOVERALL: {'VERIFIED (summary-integrity)' if v['ok'] else 'FAIL'}")
    return 0 if v["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="UC-4 verified play-resume build/verify")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--audits-dir", default="audits")
    b.add_argument("--handle", default=None)
    b.add_argument("--out", default=None)
    b.set_defaults(fn=cmd_build)
    v = sub.add_parser("verify")
    v.add_argument("--resume", required=True)
    v.set_defaults(fn=cmd_verify)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
