#!/usr/bin/env python3
"""Dual-connect play-attested RWM session continuum (operator rig).

One command that:
  1. Loads a verified L0 RWM archive (optical plane + U1 session_id + device_id)
  2. Runs sealed PoEP live challenges on the RUNNING bridge single-HID ring
     (POST /operator/poep/fire + capture-health) co-joined to that session_id
  3. Composes continuum with ioID ceremony → SYNCHRONIZED_CONTINUUM iff real fires
     mint presence_session_candidate_ok

Topology (only valid play path):
  DualShock Edge USB-C → laptop (bridge reader) AND Bluetooth → PS5 (game).
  Operator plays NCAA CFB 26; triggers must be active for preflight.

Gates:
  POEP_LIVE_FIRE_ENABLED=1 on this shell AND the bridge process
  bridge l6b_enabled=true (operator seal)
  OPERATOR_API_KEY for capture-health / fire endpoint

    POEP_LIVE_FIRE_ENABLED=1 python scripts/rwm_continuum_dual_connect_live.py \\
      --archive retina_kf_archive/cfb_rwm_live_10_1784953588 \\
      --label cfb_rwm_live_10 --stamp 1784953588 \\
      --ioid audits/ioid_edge_live_ceremony.json \\
      --wait-active-s 60 --require-candidate \\
      --out audits/rwm_continuum_LIVE10_PLAY_ATTESTED.json

Honesty: play-attested means real bridge fires verified under sealed summarize_live_session.
Does NOT flip poep_enabled. Does NOT prove optical frames were co-temporal unless this runs
during the same daemon session that produced the archive (preferred: mid-session write of
archive/poep_live_summary.json before stop continuum emit).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "scripts"))

from rwm_session_continuum_cli import main as continuum_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--archive", required=True)
    ap.add_argument("--label", default=None)
    ap.add_argument("--stamp", default=None)
    ap.add_argument("--ioid", default="audits/ioid_edge_live_ceremony.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--poep-out", default=None)
    ap.add_argument("--bridge-url", default="http://localhost:8080")
    ap.add_argument("--api-key", default=os.environ.get("OPERATOR_API_KEY", ""))
    ap.add_argument("--fire-timeout", type=float, default=25.0)
    ap.add_argument("--wait-active-s", type=float, default=60.0)
    ap.add_argument("--poll-s", type=float, default=1.0)
    ap.add_argument("--amplitude", type=int, default=60)
    ap.add_argument("--challenges", type=int, default=2)
    ap.add_argument("--require-candidate", action="store_true", default=True)
    ap.add_argument("--no-require-candidate", action="store_true")
    ap.add_argument("--auto-nov2-bind", action="store_true", default=True)
    a = ap.parse_args(argv)

    if os.environ.get("POEP_LIVE_FIRE_ENABLED", "") != "1":
        print(
            "REFUSED: set POEP_LIVE_FIRE_ENABLED=1 on this shell (and bridge). "
            "Dual-connect live fire is operator-gated, never CI.",
            file=sys.stderr,
        )
        return 2

    print(
        "READY CHECK (operator): Edge USB→laptop + BT→PS5; bridge UP; l6b_enabled; "
        "gameplay ACTIVE (R2 presses) within wait window. Fires adaptive-trigger probes."
    )

    out = a.out
    if not out and a.label and a.stamp:
        out = f"audits/rwm_continuum_{a.label}_{a.stamp}_PLAY_ATTESTED.json"
    elif not out:
        out = "audits/rwm_continuum_PLAY_ATTESTED.json"

    argv2 = [
        "build",
        "--archive",
        a.archive,
        "--mint-bridge-live-poep",
        "--ioid",
        a.ioid,
        "--bridge-url",
        a.bridge_url,
        "--api-key",
        a.api_key or "",
        "--fire-timeout",
        str(a.fire_timeout),
        "--wait-active-s",
        str(a.wait_active_s),
        "--poll-s",
        str(a.poll_s),
        "--amplitude",
        str(a.amplitude),
        "--challenges",
        str(a.challenges),
        "--out",
        out,
    ]
    if a.label:
        argv2.extend(["--label", a.label])
    if a.stamp:
        argv2.extend(["--stamp", str(a.stamp)])
    if a.poep_out:
        argv2.extend(["--poep-out", a.poep_out])
    if a.auto_nov2_bind:
        argv2.append("--auto-nov2-bind")
    if a.require_candidate and not a.no_require_candidate:
        argv2.append("--require-candidate")

    return continuum_main(argv2)


if __name__ == "__main__":
    raise SystemExit(main())
