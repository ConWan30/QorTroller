#!/usr/bin/env python3
"""Verify a Clock Notary wrap without trusting QorTroller or Qoresence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compose" / "clock-notary"))

from clock_notary.envelope import clock_commitment  # noqa: E402
from clock_notary.wrap import ConsentRecord  # noqa: E402


def verify(envelope: dict, wrap: dict) -> dict:
    checks = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    inner = wrap.get("wrap") if isinstance(wrap.get("wrap"), dict) else wrap
    ticks = list(envelope.get("ticks") or [])
    sidecars = dict(envelope.get("sidecar_hashes") or {})
    session_id = str(envelope.get("session_id") or "")
    recomputed = clock_commitment(session_id, ticks, sidecars) if session_id else ""
    claimed = str(envelope.get("clock_commitment") or "")
    add("envelope_commitment", bool(session_id) and recomputed == claimed, recomputed)
    wrap_commit = str(inner.get("envelope_commitment") or "")
    add("wrap_points_at_envelope", wrap_commit == recomputed, wrap_commit)
    portcert = inner.get("portcert") if isinstance(inner.get("portcert"), dict) else None
    add("portcert_present", portcert is not None)
    if portcert:
        add("portcert_clock", str(portcert.get("clock_commitment") or "") == recomputed)
        add("advisory", bool(portcert.get("advisory")))
        add("never_ban", bool(portcert.get("never_ban")))
        ceilings = portcert.get("ceilings") if isinstance(portcert.get("ceilings"), dict) else {}
        add("no_humanity_claim", ceilings.get("humanity_claim") is False)
        consent = portcert.get("consent") if isinstance(portcert.get("consent"), dict) else {}
        rec = ConsentRecord(
            gamer=str(consent.get("gamer") or ""),
            granted=bool(consent.get("granted")),
            purpose=str(consent.get("purpose") or "portcert"),
            signed_by=str(consent.get("signed_by") or ""),
        )
        add("gamer_signed", rec.valid_for_wrap(), f"{rec.signed_by}/{rec.gamer}")
    ok = all(c["ok"] for c in checks)
    return {
        "ok": ok,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "clock_commitment": recomputed or claimed,
        "checks": checks,
        "trust": "recomputed — producer status field ignored",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="clock-notary-verify")
    p.add_argument("--envelope", required=True)
    p.add_argument("--wrap", required=True)
    args = p.parse_args(argv)
    env = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
    wrap = json.loads(Path(args.wrap).read_text(encoding="utf-8"))
    out = verify(env, wrap)
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
