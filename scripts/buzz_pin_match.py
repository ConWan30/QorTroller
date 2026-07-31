"""
buzz_pin_match.py — Pin a QorTroller session postcard as an official result.

Phase 3 match-pin workflow: the operator reviews a session postcard in
#matches, then runs this script to pin it to the channel canvas as an
official result. The canvas becomes the verifiable record — each entry
carries the postcard event ID, session_id, verdict, and honesty flags.

Usage:
  python scripts/buzz_pin_match.py <event_id>

Requirements:
  - BUZZ_PRIVATE_KEY (operator or bot key with canvas write access)
  - BUZZ_RELAY_URL
  - BUZZ_MATCHES_CHANNEL_ID (or defaults to BUZZ_CHANNEL_IDS first entry)
  - buzz CLI binary (BUZZ_CLI_PATH or auto-detected)

The script:
  1. Fetches the postcard message from #matches by event_id
  2. Extracts the digest tags (session_id, verdict, commitment_root, etc.)
  3. Reads the current canvas
  4. Appends the pinned result entry
  5. Writes the updated canvas back

Never pins a postcard with fabricated fields — it reads the tags as-is
from the relay event. If a tag is missing, it records "unknown".
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# --- .env loading ------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, encoding="utf-8")
except ImportError:
    pass

RELAY_URL = os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000")
MATCHES_CHANNEL = os.environ.get("BUZZ_MATCHES_CHANNEL_ID", "")
CLI_PATH = os.environ.get(
    "BUZZ_CLI_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "buzz", "target", "debug", "buzz.exe",
    ),
)

# Tags we extract from the postcard for the pinned record.
POSTCARD_TAGS = (
    "session_id",
    "verdict",
    "commitment_root",
    "n_challenges",
    "poep_enabled",
    "l6b_enabled",
    "candidate_ok",
)


def _buzz_cli(args: list[str]) -> dict | list | None:
    """Run a buzz CLI command and return parsed JSON, or None on failure."""
    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = RELAY_URL
    try:
        result = subprocess.run(
            [CLI_PATH] + args,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        if result.returncode != 0:
            print(f"[!] buzz CLI error: {result.stderr.strip()}", file=sys.stderr)
            return None
        raw = result.stdout.strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"[!] buzz CLI failed: {e}", file=sys.stderr)
        return None


def _get_message(channel_id: str, event_id: str) -> dict | None:
    """Fetch a single message by event_id from the channel."""
    # buzz messages get returns recent messages; we filter by event_id.
    data = _buzz_cli([
        "messages", "get",
        "--channel", channel_id,
        "--limit", "50",
    ])
    if not data:
        return None
    if isinstance(data, dict):
        data = [data]
    for msg in data:
        if msg.get("event_id") == event_id or msg.get("id") == event_id:
            return msg
    return None


def _get_canvas(channel_id: str) -> str:
    """Read the current canvas content."""
    data = _buzz_cli(["canvas", "get", "--channel", channel_id])
    if data is None:
        return ""
    if isinstance(data, dict):
        return data.get("content", "")
    return str(data) if data else ""


def _set_canvas(channel_id: str, content: str) -> bool:
    """Write the canvas content."""
    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = RELAY_URL
    try:
        result = subprocess.run(
            [CLI_PATH, "canvas", "set",
             "--channel", channel_id,
             "--content", content],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        if result.returncode != 0:
            print(f"[!] canvas set failed: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"[!] canvas set failed: {e}", file=sys.stderr)
        return False


def _extract_tags(msg: dict) -> dict:
    """Extract postcard tags from a message's tags list."""
    tags_list = msg.get("tags", [])
    result = {}
    for tag in tags_list:
        if isinstance(tag, list) and len(tag) >= 2:
            key = tag[0]
            val = tag[1]
            if key in POSTCARD_TAGS:
                result[key] = val
    return result


def _format_pinned_entry(event_id: str, tags: dict, content: str) -> str:
    """Format a pinned result entry for the canvas."""
    sid = tags.get("session_id", "unknown")
    verdict = tags.get("verdict", "unknown")
    commit = tags.get("commitment_root", "unknown")
    n = tags.get("n_challenges", "0")
    poep = tags.get("poep_enabled", "false")
    l6b = tags.get("l6b_enabled", "false")
    candidate = tags.get("candidate_ok", "false")

    return (
        f"### {sid}\n"
        f"- **event_id:** `{event_id}`\n"
        f"- **verdict:** {verdict}\n"
        f"- **commitment_root:** `{commit}`\n"
        f"- **n_challenges:** {n}\n"
        f"- **poep_enabled:** {poep}\n"
        f"- **l6b_enabled:** {l6b}\n"
        f"- **candidate_ok:** {candidate}\n"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/buzz_pin_match.py <event_id>", file=sys.stderr)
        return 1

    event_id = sys.argv[1].strip()
    channel_id = MATCHES_CHANNEL
    if not channel_id:
        channels = os.environ.get("BUZZ_CHANNEL_IDS", "").split(",")
        channel_id = channels[0].strip() if channels else ""
    if not channel_id:
        print("[!] no matches channel configured (BUZZ_MATCHES_CHANNEL_ID)", file=sys.stderr)
        return 1

    if not os.path.isfile(CLI_PATH):
        print(f"[!] buzz CLI not found: {CLI_PATH}", file=sys.stderr)
        return 1

    print(f"[*] fetching postcard {event_id[:16]}… from channel {channel_id[:8]}…", file=sys.stderr)
    msg = _get_message(channel_id, event_id)
    if not msg:
        print(f"[!] postcard not found in channel — check the event_id", file=sys.stderr)
        return 1

    tags = _extract_tags(msg)
    content = msg.get("content", "")
    print(f"[*] postcard: {content}", file=sys.stderr)
    print(f"[*] tags: {tags}", file=sys.stderr)

    # Read current canvas
    canvas = _get_canvas(channel_id)
    if not canvas:
        canvas = "# Matches — Official Results\n\n## Pinned Results\n"

    # Replace the placeholder or append
    entry = _format_pinned_entry(event_id, tags, content)
    if "_(no results pinned yet)_" in canvas:
        canvas = canvas.replace("_(no results pinned yet)_", entry)
    else:
        # Append before any closing section, or at the end
        canvas = canvas.rstrip() + "\n" + entry

    print(f"[*] updating canvas…", file=sys.stderr)
    if _set_canvas(channel_id, canvas):
        print(f"[*] pinned! event_id={event_id}", file=sys.stderr)
        print(f"[*] session_id={tags.get('session_id', 'unknown')}", file=sys.stderr)
        print(f"[*] verdict={tags.get('verdict', 'unknown')}", file=sys.stderr)
        return 0
    else:
        print(f"[!] failed to update canvas", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
