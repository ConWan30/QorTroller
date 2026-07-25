#!/usr/bin/env python3
"""RWM session continuum CLI — bind optical L0 into the rest of QorTroller.

    python scripts/rwm_session_continuum_cli.py build \\
      --archive retina_kf_archive/<label>_<stamp> \\
      [--label cfb_rwm_live_10] [--stamp 1784953588] \\
      [--session-display cfb_rwm_live_10_1784953588] \\
      [--ioid path.json] [--poep path.json] \\
      [--nov2-bind path.json] [--escrow path.json] \\
      [--posp path.json] [--kas path.json] \\
      [--out audits/rwm_continuum_....json]

    python scripts/rwm_session_continuum_cli.py verify \\
      --continuum audits/rwm_continuum_....json \\
      [--archive retina_kf_archive/...]   # optional re-load optical plane

Exit: 0 ok · 1 fail · 2 usage.
Offline only. No upload. No chain spend. CANDIDATE composition only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO))

from vapi_bridge.rwm_session_continuum import (  # noqa: E402
    ContinuumError,
    build_continuum_from_archive,
    load_rwm_surface,
    verify_continuum,
)
from l9_presence.session_continuum import build_session_continuum  # noqa: E402


def _abs(p: str | Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = _REPO / path
    return path


def _write(out: Path, obj: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    print(f"wrote {out}")


def _cmd_build(a: argparse.Namespace) -> int:
    archive = _abs(a.archive)
    if not archive.is_dir():
        # also try main-repo sibling path for worktree dogfood
        alt = Path(r"C:\Users\Contr\vapi-pebble-prototype") / a.archive
        if alt.is_dir():
            archive = alt
        else:
            print(f"archive not found: {archive}", file=sys.stderr)
            return 2
    try:
        cont = build_continuum_from_archive(
            archive,
            label=a.label,
            stamp=a.stamp,
            session_display=a.session_display,
            ioid=_abs(a.ioid) if a.ioid else None,
            poep_live=_abs(a.poep) if a.poep else None,
            nov2_bind=_abs(a.nov2_bind) if a.nov2_bind else None,
            escrow=_abs(a.escrow) if a.escrow else None,
            posp=_abs(a.posp) if a.posp else None,
            kas=_abs(a.kas) if a.kas else None,
            require_l0_verified=not a.allow_unverified_l0,
        )
    except ContinuumError as e:
        print(f"BUILD FAIL: {e}", file=sys.stderr)
        return 1

    print(f"verdict={cont['verdict']}")
    print(
        f"bits optical={cont['optical_rwm']} session_join={cont['session_join']} "
        f"device_join={cont['device_join']} identity={cont['identity_bound']} "
        f"presence={cont['presence_candidate']} stack={cont['stack_cited']}"
    )
    print(f"session_id={cont.get('session_id')}")
    print(f"device_id={(cont.get('device_id') or '')[:16]}…")
    if a.out:
        _write(_abs(a.out), cont)
    else:
        print(json.dumps(cont, indent=2))
    # soft structural verify
    vr = verify_continuum(cont)
    if not vr["ok"]:
        print(f"VERIFY WARN structural: {vr}", file=sys.stderr)
        return 1
    print("BUILD+VERIFY OK")
    return 0


def _cmd_verify(a: argparse.Namespace) -> int:
    path = _abs(a.continuum)
    if not path.is_file():
        print(f"continuum not found: {path}", file=sys.stderr)
        return 2
    cont = json.loads(path.read_text(encoding="utf-8"))
    vr = verify_continuum(cont)
    print(f"structural ok={vr['ok']} verdict={vr.get('verdict')}")
    for c in vr.get("checks") or []:
        mark = "PASS" if c["ok"] else "FAIL"
        print(f"  [{mark}] {c['name']}" + (f" — {c['note']}" if c.get("note") else ""))

    if a.archive:
        archive = _abs(a.archive)
        if not archive.is_dir():
            alt = Path(r"C:\Users\Contr\vapi-pebble-prototype") / a.archive
            archive = alt if alt.is_dir() else archive
        try:
            rwm = load_rwm_surface(archive, require_verified=True)
        except ContinuumError as e:
            print(f"L0 FAIL: {e}", file=sys.stderr)
            return 1
        # rebuild from live optical + stored optional surfaces
        rebuilt = build_session_continuum(
            device_id=cont.get("device_id") or rwm["device_id_hex"],
            session_id=cont.get("session_id") or rwm["session_id"],
            session_display=cont.get("session_display"),
            rwm=rwm,
            ioid=cont.get("ioid"),
            poep_live_summary=cont.get("poep_live"),
            stack=_stack_from_cont(cont),
        )
        tip_match = (rwm.get("l0_chain_tip_hex") or "") == (
            (cont.get("rwm") or {}).get("l0_chain_tip_hex") or ""
        )
        print(f"L0 re-verify ok tip_match={tip_match} rebuilt={rebuilt.verdict}")
        if not tip_match or rebuilt.verdict != cont.get("verdict"):
            # tip mismatch is hard fail; verdict drift with richer surfaces is soft warn
            if not tip_match:
                print("FAIL: L0 tip mismatch vs continuum package", file=sys.stderr)
                return 1
            print(
                f"WARN: rebuilt verdict {rebuilt.verdict} != package {cont.get('verdict')}"
            )
    return 0 if vr["ok"] else 1


def _stack_from_cont(cont: dict) -> dict | None:
    s = cont.get("stack")
    if not isinstance(s, dict):
        return None
    out: dict = {}
    for key in ("nov2_bind", "escrow", "posp", "kas"):
        sub = s.get(key)
        if isinstance(sub, dict):
            out[key] = {
                "session_id": sub.get("session_id"),
                "ok": sub.get("ok"),
                "bind_ok": sub.get("ok"),
                "l0_chain_tip_hex": sub.get("l0_chain_tip_hex"),
                "bind_kind": sub.get("bind_kind"),
            }
    for k in ("poac_tip_hex", "gic_tip_hex"):
        if s.get(k):
            out[k] = s[k]
    return out or None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RWM session continuum (CANDIDATE)")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Build continuum from L0 archive + optional surfaces")
    b.add_argument("--archive", required=True)
    b.add_argument("--label", default=None)
    b.add_argument("--stamp", default=None)
    b.add_argument("--session-display", default=None)
    b.add_argument("--ioid", default=None)
    b.add_argument("--poep", default=None)
    b.add_argument("--nov2-bind", default=None)
    b.add_argument("--escrow", default=None)
    b.add_argument("--posp", default=None)
    b.add_argument("--kas", default=None)
    b.add_argument("--out", default=None)
    b.add_argument(
        "--allow-unverified-l0",
        action="store_true",
        help="Allow l0_verified=false surface (still fail-closed optical bit)",
    )
    b.set_defaults(func=_cmd_build)

    v = sub.add_parser("verify", help="Verify continuum package (structural + optional L0)")
    v.add_argument("--continuum", required=True)
    v.add_argument("--archive", default=None)
    v.set_defaults(func=_cmd_verify)

    a = p.parse_args(argv)
    return int(a.func(a))


if __name__ == "__main__":
    raise SystemExit(main())
