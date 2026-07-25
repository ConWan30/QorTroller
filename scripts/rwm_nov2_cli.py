#!/usr/bin/env python3
"""RWM NOV-2 CLI — offline bind / checkpoint inventory / SHARE postcard.

    python scripts/rwm_nov2_cli.py bind \\
      --archive retina_kf_archive/<label>_<stamp> \\
      [--kind none|poac_segment|gic_tip|dual] \\
      [--poac-tip path_or_hex] [--gic-tip path_or_hex] \\
      [--escrow audits/rwm_escrow_....json] \\
      [--require-bind] \\
      [--out audits/rwm_bind_....json]

    python scripts/rwm_nov2_cli.py checkpoints \\
      --archive retina_kf_archive/<label>_<stamp> \\
      [--indices 0,10,20] \\
      [--out audits/rwm_cp_inv_....json]

    python scripts/rwm_nov2_cli.py share \\
      --escrow audits/rwm_escrow_....json \\
      [--out audits/rwm_share_....json]

Exit: 0 ok · 1 fail · 2 usage.
Consent: SHARE/bind surfaces may be biometric-adjacent. Never uploads.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "bridge"))

from vapi_bridge.rwm_checkpoint_inventory import (  # noqa: E402
    InventoryError,
    build_inventory,
    verify_inventory,
)
from vapi_bridge.rwm_session_bind import (  # noqa: E402
    BindError,
    attach_bind,
    build_bind,
    verify_bind,
)
from vapi_bridge.rwm_share_postcard import (  # noqa: E402
    ShareError,
    to_share,
    verify_share,
)

_CONSENT = (
    "CONSENT: dispute media may be biometric-adjacent (controller capture / on-screen identity). "
    "This tool does not upload. Hold operator/gamer consent before any share path."
)


def _abs(p: str | Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = _REPO / path
    return path


def _write(out: Path, obj: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _cmd_bind(a: argparse.Namespace) -> int:
    archive = _abs(a.archive)
    if not archive.is_dir():
        print(f"archive not found: {archive}", file=sys.stderr)
        return 2
    print(_CONSENT)
    try:
        bind = build_bind(
            archive,
            bind_kind=a.kind,
            poac_source=a.poac_tip,
            gic_source=a.gic_tip,
            require_bind=bool(a.require_bind),
        )
    except BindError as e:
        print(f"BIND FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"BIND ERROR: {e!r}", file=sys.stderr)
        return 1

    vr = verify_bind(bind, archive_dir=archive)
    if not vr["ok"]:
        print(f"BIND VERIFY FAIL: {vr}", file=sys.stderr)
        return 1

    out = _abs(a.out) if a.out else _REPO / "audits" / f"rwm_bind_{archive.name}.json"
    _write(out, bind)
    print(f"BIND OK: kind={bind['bind_kind']} bind_ok={bind['bind_ok']} -> {out}")

    if a.escrow:
        ep = _abs(a.escrow)
        if not ep.is_file():
            print(f"escrow not found: {ep}", file=sys.stderr)
            return 2
        escrow = json.loads(ep.read_text(encoding="utf-8"))
        try:
            merged = attach_bind(escrow, bind)
        except BindError as e:
            print(f"ATTACH FAIL: {e}", file=sys.stderr)
            return 1
        eout = _abs(a.escrow_out) if a.escrow_out else ep.with_name(ep.stem + "_bound.json")
        _write(eout, merged)
        print(f"ATTACHED session_bind -> {eout}")
    return 0


def _cmd_checkpoints(a: argparse.Namespace) -> int:
    archive = _abs(a.archive)
    if not archive.is_dir():
        print(f"archive not found: {archive}", file=sys.stderr)
        return 2
    indices = None
    if a.indices:
        indices = [int(x.strip()) for x in a.indices.split(",") if x.strip()]
    try:
        inv = build_inventory(archive, checkpoint_indices=indices)
    except InventoryError as e:
        print(f"CHECKPOINTS FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"CHECKPOINTS ERROR: {e!r}", file=sys.stderr)
        return 1

    vr = verify_inventory(inv, archive)
    if not vr["ok"]:
        print(f"CHECKPOINTS VERIFY FAIL: {vr}", file=sys.stderr)
        return 1

    out = _abs(a.out) if a.out else _REPO / "audits" / f"rwm_cp_inv_{archive.name}.json"
    _write(out, inv)
    print(f"CHECKPOINTS OK: n={inv['n_checkpoints']} frames={inv['n_frames']} -> {out}")
    return 0


def _cmd_share(a: argparse.Namespace) -> int:
    ep = _abs(a.escrow)
    if not ep.is_file():
        print(f"escrow not found: {ep}", file=sys.stderr)
        return 2
    print(_CONSENT)
    escrow = json.loads(ep.read_text(encoding="utf-8"))
    try:
        card = to_share(escrow)
    except ShareError as e:
        print(f"SHARE FAIL: {e}", file=sys.stderr)
        return 1
    vr = verify_share(card)
    if not vr["ok"]:
        print(f"SHARE VERIFY FAIL: {vr}", file=sys.stderr)
        return 1
    out = _abs(a.out) if a.out else _REPO / "audits" / f"rwm_share_{ep.stem}.json"
    _write(out, card)
    print(f"SHARE OK: root={card['commitment_root'][:16]}… -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RWM NOV-2 offline CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bind", help="build session bind package")
    b.add_argument("--archive", required=True)
    b.add_argument("--kind", default="none", choices=["none", "poac_segment", "gic_tip", "dual"])
    b.add_argument("--poac-tip", default=None, help="path or 64-hex tip")
    b.add_argument("--gic-tip", default=None, help="path or 64-hex tip")
    b.add_argument("--require-bind", action="store_true")
    b.add_argument("--escrow", default=None, help="optional LOCAL escrow to attach bind into")
    b.add_argument("--escrow-out", default=None)
    b.add_argument("--out", default=None)
    b.set_defaults(func=_cmd_bind)

    c = sub.add_parser("checkpoints", help="build multi-checkpoint inventory")
    c.add_argument("--archive", required=True)
    c.add_argument("--indices", default=None, help="comma frame indices (default quintile)")
    c.add_argument("--out", default=None)
    c.set_defaults(func=_cmd_checkpoints)

    s = sub.add_parser("share", help="SHARE-redacted postcard from LOCAL escrow")
    s.add_argument("--escrow", required=True)
    s.add_argument("--out", default=None)
    s.set_defaults(func=_cmd_share)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
