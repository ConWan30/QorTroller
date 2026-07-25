#!/usr/bin/env python3
"""RWM NOV-3 dispute escrow CLI — offline, post-session only.

    python scripts/rwm_dispute_escrow.py build \\
      --archive retina_kf_archive/<label>_<stamp> \\
      --reveal 10,11,12 \\
      --reason "tournament dispute: clip 00:12-00:18" \\
      --case-id CASE-001 \\
      [--include-media] \\
      [--out audits/rwm_escrow_CASE-001.json]

    python scripts/rwm_dispute_escrow.py verify \\
      --escrow audits/rwm_escrow_CASE-001.json \\
      [--archive retina_kf_archive/<label>_<stamp>]

Exit: 0 ok · 1 build/verify fail · 2 usage / missing path.

Consent: dispute media may be biometric-adjacent. This tool never uploads.
Hold consent before any share path.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "bridge"))

from vapi_bridge.rwm_dispute_escrow import (  # noqa: E402
    EscrowError,
    build_escrow,
    verify_escrow,
)

_CONSENT = (
    "CONSENT: dispute media may be biometric-adjacent (controller capture / on-screen identity). "
    "This tool does not upload. Hold operator/gamer consent before any share path."
)


def _parse_reveal(s: str) -> list[int]:
    parts = [p.strip() for p in s.replace(" ", "").split(",") if p.strip()]
    if not parts:
        raise SystemExit("empty --reveal")
    return [int(p) for p in parts]


def _cmd_build(a: argparse.Namespace) -> int:
    archive = Path(a.archive)
    if not archive.is_absolute():
        archive = _REPO / archive
    if not archive.is_dir():
        print(f"archive not found: {archive}", file=sys.stderr)
        return 2

    print(_CONSENT)
    try:
        pkg = build_escrow(
            archive,
            _parse_reveal(a.reveal),
            a.reason,
            case_id=a.case_id or "",
            external_ref=a.external_ref or "",
            include_media=bool(a.include_media),
        )
    except EscrowError as e:
        print(f"BUILD FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"BUILD ERROR: {e!r}", file=sys.stderr)
        return 1

    out = Path(a.out) if a.out else _REPO / "audits" / f"rwm_escrow_{(a.case_id or 'case')}.json"
    if not out.is_absolute():
        out = _REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    if a.include_media:
        media_dir = out.with_suffix("").parent / (out.stem + "_media")
        if media_dir.exists():
            shutil.rmtree(media_dir)
        media_dir.mkdir(parents=True, exist_ok=True)
        for r in pkg["revealed"]:
            src = archive / r["marked_relpath"]
            if src.is_file():
                dest = media_dir / Path(r["marked_relpath"]).name
                shutil.copy2(src, dest)
        print(f"media copies -> {media_dir} ({len(list(media_dir.glob('*')))} files)")

    print(f"BUILD OK: root={pkg['commitment_root'][:16]}… revealed={len(pkg['revealed'])} -> {out}")
    return 0


def _cmd_verify(a: argparse.Namespace) -> int:
    ep = Path(a.escrow)
    if not ep.is_absolute():
        ep = _REPO / ep
    if not ep.is_file():
        print(f"escrow not found: {ep}", file=sys.stderr)
        return 2
    pkg = json.loads(ep.read_text(encoding="utf-8"))
    archive = None
    if a.archive:
        archive = Path(a.archive)
        if not archive.is_absolute():
            archive = _REPO / archive
        if not archive.is_dir():
            print(f"archive not found: {archive}", file=sys.stderr)
            return 2

    result = verify_escrow(pkg, archive)
    for c in result["checks"]:
        mark = "PASS" if c["ok"] else "FAIL"
        note = f" — {c['note']}" if c.get("note") else ""
        print(f"  [{mark}] {c['name']}{note}")
    if result["ok"]:
        print("VERIFY OK")
        return 0
    print("VERIFY FAIL", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="RWM NOV-3 dispute escrow (offline)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build escrow package from L0 archive")
    b.add_argument("--archive", required=True)
    b.add_argument("--reveal", required=True, help="comma-separated frame_index list")
    b.add_argument("--reason", required=True)
    b.add_argument("--case-id", default="")
    b.add_argument("--external-ref", default="")
    b.add_argument("--include-media", action="store_true")
    b.add_argument("--out", default=None)
    b.set_defaults(fn=_cmd_build)

    v = sub.add_parser("verify", help="verify escrow package")
    v.add_argument("--escrow", required=True)
    v.add_argument("--archive", default=None)
    v.set_defaults(fn=_cmd_verify)

    a = ap.parse_args()
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
