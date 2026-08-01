#!/usr/bin/env python3
"""VSS-S5 — Organizer pilot room digest (seat + pin + portcert).

Composition checklist + optional consent-gated publish to #streams.

Usage:
  # Checklist only (no publish)
  python scripts/buzz_vss_organizer_pilot.py --check \\
      --session-id grind_phase235_v1 \\
      --pin-event-id <postcard_event_id>

  # Dry-run publish payload
  python scripts/buzz_vss_organizer_pilot.py --consent-ok --dry-run \\
      --session-id grind_phase235_v1

  # Live publish (gamer/operator key)
  python scripts/buzz_vss_organizer_pilot.py --consent-ok \\
      --session-id grind_phase235_v1 \\
      --media-url https://example.com/live \\
      --pin-event-id <id>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "bridge"))

from vapi_bridge.vss_organizer_pilot import (  # noqa: E402
    PilotInputs,
    build_pilot_event,
    organizer_commands,
    pilot_from_eligibility,
    validate_pilot_event,
)

_SECRET_KEYS = frozenset(
    {"BUZZ_PRIVATE_KEY", "BUZZ_AUTH_TAG", "BUZZ_OWNER_PRIVATE_KEY"}
)


def _load_env(path: Path, *, skip_secrets: bool = False) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if skip_secrets and k in _SECRET_KEYS:
            continue
        if not os.environ.get(k):
            os.environ[k] = v


def _poll_eligibility(base: str, api_key: str) -> dict | None:
    try:
        import requests

        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        r = requests.get(
            f"{base.rstrip('/')}/operator/vss/eligibility",
            headers=headers,
            timeout=8,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[!] eligibility poll failed: {e}", file=sys.stderr)
        return None


def main() -> int:
    p = argparse.ArgumentParser(description="VSS-S5 organizer pilot digest")
    p.add_argument("--check", action="store_true", help="Print checklist only")
    p.add_argument("--consent-ok", action="store_true",
                   help="Required to publish (never auto)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--channel", default="", help="#streams channel (or VSS_STREAMS_CHANNEL)")
    p.add_argument("--session-id", default=None)
    p.add_argument("--media-url", default=None)
    p.add_argument("--pin-event-id", default=None,
                   help="Optional #matches postcard event id to reference")
    p.add_argument("--matches-channel", default=None)
    p.add_argument("--portcert-cmd", default=None)
    args = p.parse_args()

    gamer_pre = bool(os.environ.get("BUZZ_PRIVATE_KEY"))
    _load_env(ROOT / "scripts" / ".env", skip_secrets=gamer_pre)
    if gamer_pre:
        os.environ.pop("BUZZ_AUTH_TAG", None)
        os.environ.pop("BUZZ_OWNER_PRIVATE_KEY", None)
    _load_env(ROOT / "bridge" / ".env")
    if not os.environ.get("BRIDGE_API_KEY") and os.environ.get("OPERATOR_API_KEY"):
        os.environ["BRIDGE_API_KEY"] = os.environ["OPERATOR_API_KEY"]

    session_id = args.session_id or os.environ.get("VSS_SESSION_ID")
    if not session_id:
        # honest grind session from root .env if present
        for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines() if (ROOT / ".env").is_file() else []:
            if line.strip().startswith("GRIND_SESSION_ID="):
                session_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    streams = (
        args.channel
        or os.environ.get("VSS_STREAMS_CHANNEL", "")
    )
    matches = (
        args.matches_channel
        or os.environ.get("VSS_MATCHES_CHANNEL")
        or os.environ.get("BUZZ_MATCHES_CHANNEL_ID")
    )
    media = args.media_url or os.environ.get("VSS_MEDIA_URL")
    pin = args.pin_event_id
    portcert = args.portcert_cmd or os.environ.get(
        "VSS_PORTCERT_CMD",
        "python scripts/portcert_full_verify.py",
    )

    base = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000")
    elig = _poll_eligibility(base, os.environ.get("BRIDGE_API_KEY", ""))

    checklist = pilot_from_eligibility(
        elig,
        session_id=session_id,
        media_url=media,
        pin_event_id=pin,
        streams_channel=streams or None,
        matches_channel=matches,
        portcert_cmd=portcert,
    )

    out = {
        "checklist": {
            "ready": checklist.ready,
            "seat_ok": checklist.seat_ok,
            "session_bound": checklist.session_bound,
            "pin_present": checklist.pin_present,
            "verify_pointer_present": checklist.verify_pointer_present,
            "missing": checklist.missing,
            "summary": checklist.summary,
        },
        "commands": organizer_commands(
            session_id=session_id,
            media_url=media,
            pin_event_id=pin,
        ),
    }

    if args.check or (not args.consent_ok and not args.dry_run):
        print(json.dumps(out, indent=2))
        if not args.check and not args.consent_ok:
            print(
                "[*] checklist only — pass --consent-ok to publish, "
                "or --check for explicit checklist mode",
                file=sys.stderr,
            )
        return 0 if checklist.ready or args.check else 1

    # Publish path
    if not args.consent_ok:
        sys.exit("refused: --consent-ok required to publish organizer pilot digest")
    if not streams and not args.dry_run:
        sys.exit("channel required (VSS_STREAMS_CHANNEL)")
    if not args.dry_run and not os.environ.get("BUZZ_PRIVATE_KEY"):
        sys.exit("BUZZ_PRIVATE_KEY required for publish")

    try:
        event = build_pilot_event(
            consent_ok=True,
            inputs=PilotInputs(
                seat_eligible=(
                    None if elig is None else bool(elig.get("eligible", False))
                ),
                session_id=session_id,
                media_url=media,
                pin_event_id=pin,
                streams_channel=streams or None,
                matches_channel=matches,
                portcert_cmd=portcert,
            ),
        )
    except ValueError as e:
        sys.exit(f"build failed: {e}")

    tags = event.to_tags()
    content = event.to_content()
    errs = validate_pilot_event(tags, content)
    if errs:
        sys.exit(f"validation failed: {errs}")

    print(f"[*] content: {content}", file=sys.stderr)
    if args.dry_run:
        out["publish"] = {"dry_run": True, "content": content, "tags": tags}
        print(json.dumps(out, indent=2))
        return 0

    helper = os.environ.get(
        "BUZZ_HELPER_PATH",
        str(ROOT / "buzz" / "target" / "debug" / "qortroller-buzz.exe"),
    )
    payload = json.dumps({"channel": streams, "content": content, "tags": tags})
    env = os.environ.copy()
    env.pop("BUZZ_AUTH_TAG", None)
    proc = subprocess.run(
        [helper, "publish"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        shell=False,
    )
    if proc.returncode != 0:
        sys.exit(f"publish failed: {(proc.stderr or proc.stdout).strip()}")
    try:
        result = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        result = {"raw": proc.stdout}
    out["publish"] = result
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
