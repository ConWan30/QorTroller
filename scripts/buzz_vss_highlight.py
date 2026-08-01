#!/usr/bin/env python3
"""VSS-S3 — Consent-gated highlight / verify pointer publish.

Usage:
  # Explicit gamer consent required every time:
  $env:BUZZ_PRIVATE_KEY = "<gamer-nsec>"
  python scripts/buzz_vss_highlight.py --consent-ok \\
      --session-id grind_phase235_v1 \\
      --note "match sealed — verify with public tools" \\
      --default-verify-pointer

  python scripts/buzz_vss_highlight.py --consent-ok \\
      --verify-url "https://example.com/verify/sess" \\
      --note "clip pointer only"

Never: auto-publish, bot key as gamer, raw frames, humanity-proven language.
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

from vapi_bridge.vss_highlight import (  # noqa: E402
    build_highlight_event,
    validate_highlight_event,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VSS-S3 consent-gated highlight / verify pointer",
    )
    parser.add_argument(
        "--consent-ok",
        action="store_true",
        help="Required: gamer explicitly consents to publish this highlight",
    )
    parser.add_argument("--channel", type=str, default="",
                        help="#streams channel UUID (or VSS_STREAMS_CHANNEL)")
    parser.add_argument("--session-id", type=str, default=None)
    parser.add_argument("--note", type=str, default=None,
                        help="Short highlight note (max 200 chars)")
    parser.add_argument("--verify-url", type=str, default=None,
                        help="Public verify URL or command pointer")
    parser.add_argument(
        "--default-verify-pointer",
        action="store_true",
        help="Use default portcert public verify command pointer",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.consent_ok:
        sys.exit(
            "refused: --consent-ok required (S3 consent gate — never auto-publish)"
        )

    gamer_pre = bool(os.environ.get("BUZZ_PRIVATE_KEY"))
    _load_env(ROOT / "scripts" / ".env", skip_secrets=gamer_pre)
    if gamer_pre:
        os.environ.pop("BUZZ_AUTH_TAG", None)
        os.environ.pop("BUZZ_OWNER_PRIVATE_KEY", None)

    channel = args.channel or os.environ.get("VSS_STREAMS_CHANNEL", "")
    if not channel and not args.dry_run:
        sys.exit("channel required (--channel or VSS_STREAMS_CHANNEL)")

    if not args.dry_run and not os.environ.get("BUZZ_PRIVATE_KEY"):
        sys.exit("BUZZ_PRIVATE_KEY required (gamer key, not bot)")

    try:
        event = build_highlight_event(
            consent_ok=True,
            session_id=args.session_id or os.environ.get("VSS_SESSION_ID"),
            verify_url=args.verify_url,
            highlight_note=args.note,
            use_default_verify_pointer=args.default_verify_pointer,
        )
    except ValueError as e:
        sys.exit(f"build failed: {e}")

    tags = event.to_tags()
    content = event.to_content()
    errors = validate_highlight_event(tags, content)
    if errors:
        sys.exit(f"validation failed: {errors}")

    print(f"[*] content: {content}", file=sys.stderr)
    if args.dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "content": content, "tags": tags}))
        return 0

    helper = os.environ.get(
        "BUZZ_HELPER_PATH",
        str(ROOT / "buzz" / "target" / "debug" / "qortroller-buzz.exe"),
    )
    if not Path(helper).is_file():
        sys.exit(f"helper not found: {helper}")

    payload = json.dumps({"channel": channel, "content": content, "tags": tags})
    env = os.environ.copy()
    env.pop("BUZZ_AUTH_TAG", None)
    try:
        proc = subprocess.run(
            [helper, "publish"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
    except Exception as e:
        sys.exit(f"publish failed: {e}")

    if proc.returncode != 0:
        sys.exit(f"helper exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()}")

    try:
        result = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        result = {"raw": proc.stdout}
    print(json.dumps({"ok": True, "result": result, "content": content}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
