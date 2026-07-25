#!/usr/bin/env python3
"""RWM session continuum CLI — bind optical L0 into the rest of QorTroller.

    python scripts/rwm_session_continuum_cli.py build \\
      --archive retina_kf_archive/<label>_<stamp> \\
      [--label cfb_rwm_live_10] [--stamp 1784953588] \\
      [--ioid path.json] [--poep path.json] \\
      [--mint-sim-live-poep] [--poep-out audits/poep_live_summary_....json] \\
      [--auto-nov2-bind] \\
      [--out audits/rwm_continuum_....json]

    python scripts/rwm_session_continuum_cli.py verify \\
      --continuum audits/rwm_continuum_....json \\
      [--archive retina_kf_archive/...]

--mint-sim-live-poep: mint a sealed summarize_live_session presence_summary with the
live-simulator fire path (real_hardware=True). MECHANISM dogfood for SYNCHRONIZED_CONTINUUM
— not a claim that the optical capture co-ran dual-connect PoEP under play.

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
    BRIDGE_LIVE_POEP_CEILING,
    ContinuumError,
    SIM_LIVE_POEP_CEILING,
    SYNCHRONIZED_CONTINUUM,
    build_continuum_from_archive,
    load_rwm_surface,
    mint_bridge_live_poep_summary,
    mint_sealed_sim_live_poep_summary,
    verify_continuum,
)
from l9_presence.session_continuum import build_session_continuum  # noqa: E402


def _abs(p: str | Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = _REPO / path
    return path


def _resolve_archive(p: str) -> Path | None:
    archive = _abs(p)
    if archive.is_dir():
        return archive
    alt = Path(r"C:\Users\Contr\vapi-pebble-prototype") / p
    if alt.is_dir():
        return alt
    return None


def _write(out: Path, obj: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    print(f"wrote {out}")


def _cmd_build(a: argparse.Namespace) -> int:
    archive = _resolve_archive(a.archive)
    if archive is None:
        print(f"archive not found: {a.archive}", file=sys.stderr)
        return 2

    poep_src = _abs(a.poep) if a.poep else None

    if a.mint_sim_live_poep and a.mint_bridge_live_poep:
        print("use only one of --mint-sim-live-poep / --mint-bridge-live-poep", file=sys.stderr)
        return 2

    if a.mint_sim_live_poep or a.mint_bridge_live_poep:
        try:
            rwm = load_rwm_surface(archive, require_verified=not a.allow_unverified_l0)
        except ContinuumError as e:
            print(f"L0 FAIL: {e}", file=sys.stderr)
            return 1
        if a.mint_sim_live_poep:
            print("CEILING:", SIM_LIVE_POEP_CEILING)
            try:
                pkg = mint_sealed_sim_live_poep_summary(
                    device_id=rwm["device_id_hex"],
                    session_id=rwm["session_id"],
                )
            except ContinuumError as e:
                print(f"MINT FAIL: {e}", file=sys.stderr)
                return 1
            default_poep_name = f"poep_live_summary_{rwm['session_id'][:16]}_sim.json"
        else:
            print("CEILING:", BRIDGE_LIVE_POEP_CEILING)
            print(
                "[dual-connect] USB Edge→laptop + BT→PS5; bridge holds pad; "
                "POEP_LIVE_FIRE_ENABLED=1 + l6b_enabled required. Waiting ACTIVE_GAMEPLAY…"
            )
            try:
                import os

                pkg = mint_bridge_live_poep_summary(
                    device_id=rwm["device_id_hex"],
                    session_id=rwm["session_id"],
                    n_go=max(2, int(a.challenges)),
                    amplitude=int(a.amplitude),
                    bridge_url=a.bridge_url,
                    api_key=a.api_key or os.environ.get("OPERATOR_API_KEY", ""),
                    fire_timeout_s=float(a.fire_timeout),
                    wait_active_s=float(a.wait_active_s),
                    poll_s=float(a.poll_s),
                    require_candidate=bool(a.require_candidate),
                )
            except ContinuumError as e:
                print(f"MINT FAIL: {e}", file=sys.stderr)
                return 1
            default_poep_name = f"poep_live_summary_{rwm['session_id'][:16]}_bridge.json"

        poep_out = _abs(a.poep_out) if a.poep_out else (_REPO / "audits" / default_poep_name)
        _write(poep_out, pkg)
        try:
            _write(archive / "poep_live_summary.json", pkg)
        except OSError as e:
            print(f"archive poep sidecar skip: {e!r}")
        poep_src = poep_out
        print(
            f"minted presence_session_candidate_ok="
            f"{pkg['presence_summary'].get('presence_session_candidate_ok')} "
            f"play_attested={pkg.get('play_attested')} "
            f"session={rwm['session_id'][:16]}…"
        )

    try:
        cont = build_continuum_from_archive(
            archive,
            label=a.label,
            stamp=a.stamp,
            session_display=a.session_display,
            ioid=_abs(a.ioid) if a.ioid else None,
            poep_live=poep_src,
            nov2_bind=_abs(a.nov2_bind) if a.nov2_bind else None,
            escrow=_abs(a.escrow) if a.escrow else None,
            posp=_abs(a.posp) if a.posp else None,
            kas=_abs(a.kas) if a.kas else None,
            require_l0_verified=not a.allow_unverified_l0,
            auto_nov2_bind=bool(a.auto_nov2_bind),
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
    if cont["verdict"] == SYNCHRONIZED_CONTINUUM:
        if a.mint_bridge_live_poep:
            print(
                "SYNCHRONIZED_CONTINUUM reached (PLAY-ATTESTED dual-connect bridge ring — "
                "see claim_ceiling)"
            )
        elif a.mint_sim_live_poep:
            print("SYNCHRONIZED_CONTINUUM reached (mechanism dogfood — see claim_ceiling)")
    if a.out:
        _write(_abs(a.out), cont)
    else:
        print(json.dumps(cont, indent=2))
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
        archive = _resolve_archive(a.archive)
        if archive is None:
            print(f"archive not found: {a.archive}", file=sys.stderr)
            return 2
        try:
            rwm = load_rwm_surface(archive, require_verified=True)
        except ContinuumError as e:
            print(f"L0 FAIL: {e}", file=sys.stderr)
            return 1
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
        if not tip_match:
            print("FAIL: L0 tip mismatch vs continuum package", file=sys.stderr)
            return 1
        if rebuilt.verdict != cont.get("verdict"):
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
    b.add_argument(
        "--mint-sim-live-poep",
        action="store_true",
        help="mint sealed sim-live presence_summary (mechanism dogfood → SYNCHRONIZED)",
    )
    b.add_argument(
        "--mint-bridge-live-poep",
        action="store_true",
        help="dual-connect PLAY-ATTESTED mint via bridge single-HID ring (POST /operator/poep/fire)",
    )
    b.add_argument("--poep-out", default=None, help="where to write minted PoEP package")
    b.add_argument("--bridge-url", default="http://localhost:8080")
    b.add_argument("--api-key", default="", help="operator key (default OPERATOR_API_KEY env)")
    b.add_argument("--fire-timeout", type=float, default=25.0)
    b.add_argument("--wait-active-s", type=float, default=45.0)
    b.add_argument("--poll-s", type=float, default=1.0)
    b.add_argument("--amplitude", type=int, default=60)
    b.add_argument("--challenges", type=int, default=2)
    b.add_argument(
        "--require-candidate",
        action="store_true",
        help="fail if bridge-live did not mint presence_session_candidate_ok",
    )
    b.add_argument("--nov2-bind", default=None)
    b.add_argument("--auto-nov2-bind", action="store_true")
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
