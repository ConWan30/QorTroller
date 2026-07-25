#!/usr/bin/env python3
"""RWM NOV-1 CLI — portable stranger-verify dispute pack (offline).

    python scripts/rwm_nov1_cli.py build \\
      --archive retina_kf_archive/<label>_<stamp> \\
      --reveal 0,10,100 \\
      --reason "tournament dispute: sample frames" \\
      [--case-id CASE-001] \\
      [--out audits/rwm_stranger_CASE-001.json]

    python scripts/rwm_nov1_cli.py verify \\
      --pack audits/rwm_stranger_CASE-001.json

Exit: 0 ok · 1 fail · 2 usage.
Consent: pack embeds marked frame media (biometric-adjacent). Never uploads.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "bridge"))

from vapi_bridge.rwm_stranger_pack import (  # noqa: E402
    StrangerPackError,
    build_stranger_pack,
    verify_stranger_pack,
)

_CONSENT = (
    "CONSENT: stranger pack embeds marked gameplay frames (may be biometric-adjacent). "
    "This tool does not upload. Hold operator/gamer consent before any share path."
)


def _abs(p: str | Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = _REPO / path
    return path


def _parse_reveal(s: str) -> list[int]:
    parts = [p.strip() for p in s.replace(" ", "").split(",") if p.strip()]
    if not parts:
        raise SystemExit("empty --reveal")
    return [int(p) for p in parts]


def _cmd_build(a: argparse.Namespace) -> int:
    archive = _abs(a.archive)
    if not archive.is_dir():
        print(f"archive not found: {archive}", file=sys.stderr)
        return 2
    print(_CONSENT)
    try:
        pack = build_stranger_pack(
            archive,
            _parse_reveal(a.reveal),
            a.reason,
            case_id=a.case_id or "",
        )
    except StrangerPackError as e:
        print(f"BUILD FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"BUILD ERROR: {e!r}", file=sys.stderr)
        return 1

    out = _abs(a.out) if a.out else _REPO / "audits" / f"rwm_stranger_{(a.case_id or 'pack')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(
        f"BUILD OK: root={pack['commitment_root'][:16]}… "
        f"revealed={len(pack['revealed'])} set_size={pack['set_size']} -> {out}"
    )
    return 0


def _cmd_verify(a: argparse.Namespace) -> int:
    pp = _abs(a.pack)
    if not pp.is_file():
        print(f"pack not found: {pp}", file=sys.stderr)
        return 2
    pack = json.loads(pp.read_text(encoding="utf-8"))
    r = verify_stranger_pack(pack)
    for c in r["checks"]:
        mark = "PASS" if c["ok"] else "FAIL"
        note = f" — {c['note']}" if c.get("note") else ""
        print(f"  [{mark}] {c['name']}{note}")
    if r["ok"]:
        print("VERIFY OK (archive-free stranger path)")
        return 0
    print("VERIFY FAIL", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RWM NOV-1 stranger pack CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build portable stranger pack from L0 archive")
    b.add_argument("--archive", required=True)
    b.add_argument("--reveal", required=True, help="comma frame indices")
    b.add_argument("--reason", required=True)
    b.add_argument("--case-id", default="")
    b.add_argument("--out", default=None)
    b.set_defaults(func=_cmd_build)

    v = sub.add_parser("verify", help="archive-free verify of stranger pack")
    v.add_argument("--pack", required=True)
    v.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
