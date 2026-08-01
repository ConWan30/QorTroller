#!/usr/bin/env python3
"""VSS-3 — Buzz VSS seat open/close helper.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §6 (Gamer helper):
  1. Poll /vss/eligibility
  2. Rising edge → publish OPEN (gamer key, Architecture C)
  3. Falling edge → publish CLOSED
  4. Never upload pixels

Architecture C: Python (truth plane) builds the digest JSON and pipes it
to the qortroller-buzz Rust helper's stdin. The helper signs the Nostr
event (BIP-340 Schnorr) and publishes to the relay. No Nostr signing
in Python. No raw biometrics, no nsec in source, no fabricated states.

The seat helper uses the GAMER'S OWN KEY (BUZZ_PRIVATE_KEY), not the
EA bot key. Per VSS §2: "seat OPEN/CLOSED is signed with the gamer's
own Buzz key." Per VSS §4: "EA may mirror health digests only" — EA
cannot open a gamer seat.

Usage:
  python scripts/buzz_vss_seat.py --channel <streams-channel-uuid> \\
      --media-url https://stream.example.com/live

  # Dry-run (no publish, just poll + print):
  python scripts/buzz_vss_seat.py --dry-run --channel <uuid>

  # With optional session_id (F2 watch-party bind):
  python scripts/buzz_vss_seat.py --channel <uuid> \\
      --media-url https://... --session-id sess_abc123

Environment:
  BUZZ_PRIVATE_KEY    — the GAMER's key (NOT the bot's key)
  BUZZ_RELAY_URL      — relay URL (default: ws://localhost:3000)
  BRIDGE_BASE_URL     — bridge URL (default: http://localhost:8000)
  BRIDGE_API_KEY      — bridge read key (optional, fail-open in dev)
  BUZZ_HELPER_PATH    — path to qortroller-buzz binary
  VSS_POLL_INTERVAL   — poll interval in seconds (default: 15)
  VSS_STREAMS_CHANNEL — #streams channel UUID (alternative to --channel)

Never:
  - Uploads pixels or frames
  - Signs with the bot/EA key
  - Fabricates eligibility
  - Touches raw HID/IMU/L4/PoAC
  - Writes to chain or FROZEN wire
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

# VSS-2 schema (same package, importable from bridge/)
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bridge"),
)
from vapi_bridge.vss_seat_schema import (  # noqa: E402
    SEAT_OPEN,
    SEAT_CLOSED,
    CAPTURE_UP,
    CAPTURE_DOWN,
    ORACLE_RUNNING,
    ORACLE_STOPPED,
    build_seat_event,
    validate_seat_event,
)


@dataclass
class SeatConfig:
    """Configuration for the VSS seat helper."""

    relay_url: str
    channel_id: str
    bridge_base_url: str
    bridge_api_key: str
    helper_path: str
    poll_interval: float
    media_url: str
    session_id: Optional[str]
    ioid_token: Optional[str]
    dry_run: bool


def _load_config(args: argparse.Namespace) -> SeatConfig:
    """Load config from env + CLI args."""

    relay_url = os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000")
    channel_id = args.channel or os.environ.get("VSS_STREAMS_CHANNEL", "")
    bridge_base_url = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000")
    bridge_api_key = os.environ.get("BRIDGE_API_KEY", "")
    helper_path = os.environ.get(
        "BUZZ_HELPER_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "buzz", "target", "debug", "qortroller-buzz.exe",
        ),
    )
    poll_interval = float(
        os.environ.get("VSS_POLL_INTERVAL", str(args.poll_interval))
    )

    if not channel_id and not args.dry_run:
        sys.exit(
            "Channel ID required: use --channel or set VSS_STREAMS_CHANNEL. "
            "This is the #streams channel UUID."
        )

    if not args.dry_run and not args.media_url:
        sys.exit(
            "media_url is required for live mode (OPEN seat needs a media pointer). "
            "Use --dry-run for testing without publishing."
        )

    return SeatConfig(
        relay_url=relay_url,
        channel_id=channel_id,
        bridge_base_url=bridge_base_url,
        bridge_api_key=bridge_api_key,
        helper_path=helper_path,
        poll_interval=poll_interval,
        media_url=args.media_url or "",
        session_id=args.session_id,
        ioid_token=args.ioid_token,
        dry_run=args.dry_run,
    )


def _poll_eligibility(cfg: SeatConfig) -> Optional[dict]:
    """Poll the bridge's /vss/eligibility endpoint. Never fabricate.

    Returns the eligibility dict or None on failure.
    """
    try:
        import requests

        headers = {}
        if cfg.bridge_api_key:
            headers["x-api-key"] = cfg.bridge_api_key
        resp = requests.get(
            f"{cfg.bridge_base_url}/vss/eligibility",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[!] eligibility poll failed: {e}", file=sys.stderr)
        return None


def check_signer_is_not_bot(cfg: SeatConfig) -> Optional[str]:
    """VSS-7: Verify the gamer's key is NOT a bot (role != bot).

    Queries the Rust helper's `whoami` to get the signer pubkey, then
    queries the relay for the pubkey's kind 9000 self-add role tag.

    Returns:
        "human" if the signer is a human community member (or role unknown)
        "bot" if the signer is a bot
        None if the check failed (relay unreachable / helper missing)

    Fail-closed: returns None on any error — the caller MUST treat None as
    "cannot verify" and refuse OPEN.
    """
    if not os.path.isfile(cfg.helper_path):
        print(f"[!] helper not found for role check: {cfg.helper_path}",
              file=sys.stderr)
        return None
    try:
        # Get the signer's pubkey
        who = subprocess.run(
            [cfg.helper_path, "whoami"],
            capture_output=True, text=True, timeout=10,
            env=os.environ.copy(), shell=False,
        )
        if who.returncode != 0:
            print(f"[!] whoami failed: {who.stderr.strip()}", file=sys.stderr)
            return None
        pubkey = who.stdout.strip()
        if not pubkey:
            print("[!] whoami returned empty pubkey", file=sys.stderr)
            return None

        # Query the relay for kind 9000 self-add events by this pubkey
        # The Rust helper exposes `profile get` for this; fall back to
        # "human" if the relay has no role tag for this pubkey (new member).
        env = os.environ.copy()
        env["BUZZ_RELAY_URL"] = cfg.relay_url
        prof = subprocess.run(
            [cfg.helper_path, "profile", "get", "--pubkey", pubkey],
            capture_output=True, text=True, timeout=15,
            env=env, shell=False,
        )
        if prof.returncode != 0:
            # Relay unreachable or profile not found — fail-closed
            print(f"[!] profile get failed: {prof.stderr.strip()}",
                  file=sys.stderr)
            return None
        try:
            data = json.loads(prof.stdout.strip())
        except json.JSONDecodeError:
            print("[!] profile get returned non-JSON", file=sys.stderr)
            return None
        role = str(data.get("role", "")).lower()
        if role == "bot":
            return "bot"
        # "human", "", or any other value → treat as human (role unknown = human)
        # Per scope §2: "Buzz human membership is identity" — absence of a role
        # tag does NOT block OPEN; only an explicit role=bot blocks it.
        return "human"
    except subprocess.TimeoutExpired:
        print("[!] role check timed out", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[!] role check failed: {e}", file=sys.stderr)
        return None


def _publish_seat_event(
    cfg: SeatConfig, tags: list[list[str]], content: str
) -> Optional[dict]:
    """Publish a seat event via the Rust helper (Architecture C).

    The helper signs the Nostr event (BIP-340 Schnorr) with the GAMER'S
    key (BUZZ_PRIVATE_KEY from env) and publishes to the relay.

    Returns the helper's JSON response or None on failure.
    """
    if cfg.dry_run:
        print(f"[dry-run] would publish: {content}", file=sys.stderr)
        print(f"[dry-run] tags: {json.dumps(tags)}", file=sys.stderr)
        return {"event_id": "dry-run", "accepted": True, "message": "dry-run"}

    if not os.path.isfile(cfg.helper_path):
        print(
            f"[!] helper not found: {cfg.helper_path} — "
            "build with: cargo build -p qortroller-buzz",
            file=sys.stderr,
        )
        return None

    payload = json.dumps({
        "channel": cfg.channel_id,
        "content": content,
        "tags": tags,
    })

    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = cfg.relay_url

    try:
        result = subprocess.run(
            [cfg.helper_path, "publish"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        if result.returncode != 0:
            print(
                f"[!] helper exit {result.returncode}: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return None
        return json.loads(result.stdout.strip())
    except Exception as e:
        print(f"[!] helper invocation failed: {e}", file=sys.stderr)
        return None


def _build_and_publish(
    cfg: SeatConfig,
    seat_state: str,
    eligible: bool,
    honesty: dict,
    signer_role: Optional[str] = None,
) -> Optional[dict]:
    """Build a seat event from eligibility + honesty, validate, and publish.

    Fail-closed: if validation fails, no publish.

    VSS-7: signer_role is attached as an honesty marker on the event.
    The caller (run_seat_loop) must have already enforced the bot ban via
    check_signer_is_not_bot before calling this for OPEN events.
    """
    capture = CAPTURE_UP if eligible else CAPTURE_DOWN
    oracle = ORACLE_RUNNING if eligible else ORACLE_STOPPED

    # For CLOSED events, media_url is optional (may include a replay pointer)
    media_url = cfg.media_url if seat_state == SEAT_OPEN else None

    try:
        event = build_seat_event(
            seat_state=seat_state,
            capture=capture,
            retina_oracle=oracle,
            media_url=media_url,
            session_id=cfg.session_id,
            ioid_token=cfg.ioid_token,
            signer_role=signer_role,
            poep_enabled=bool(honesty.get("poep_enabled", False)),
            l6b_enabled=bool(honesty.get("l6b_enabled", False)),
            candidate_ok=bool(honesty.get("candidate_ok", False)),
        )
    except ValueError as e:
        print(f"[!] seat event build failed (fail-closed): {e}", file=sys.stderr)
        return None

    tags = event.to_tags()
    content = event.to_content()

    # Validate before publishing (defense in depth)
    errors = validate_seat_event(tags, content)
    if errors:
        print(f"[!] seat event validation failed (fail-closed): {errors}",
              file=sys.stderr)
        return None

    return _publish_seat_event(cfg, tags, content)


def run_seat_loop(cfg: SeatConfig) -> int:
    """Main loop: poll eligibility, detect rising/falling edges, publish.

    State machine:
      CLOSED ──(eligible rising edge)──► OPEN ──(ineligible falling edge)──► CLOSED

    The seat starts CLOSED. Only a rising edge (false→true) opens it.
    Only a falling edge (true→false) closes it. No spam — one event per
    transition.

    VSS-7: before OPEN, verify the signer is not a bot (check_signer_is_not_bot).
    Fail-closed: if the role check returns None (relay unreachable), refuse OPEN.
    """
    seat_open = False  # track current seat state
    cached_role: Optional[str] = None  # cache the role check (it's stable per key)
    print(f"[*] VSS seat helper started (dry_run={cfg.dry_run})", file=sys.stderr)
    print(f"[*] channel: {cfg.channel_id[:8]}…", file=sys.stderr)
    print(f"[*] bridge: {cfg.bridge_base_url}", file=sys.stderr)
    print(f"[*] poll interval: {cfg.poll_interval}s", file=sys.stderr)

    try:
        while True:
            elig = _poll_eligibility(cfg)

            if elig is None:
                # Bridge unreachable — fail-closed: if seat is open, close it
                if seat_open:
                    print("[!] bridge unreachable — closing seat (fail-closed)",
                          file=sys.stderr)
                    result = _build_and_publish(
                        cfg, SEAT_CLOSED, eligible=False,
                        honesty={"poep_enabled": False, "l6b_enabled": False,
                                 "candidate_ok": False},
                        signer_role=cached_role,
                    )
                    if result:
                        print(f"[+] CLOSED: {result.get('event_id', '?')}",
                              file=sys.stderr)
                        seat_open = False
                time.sleep(cfg.poll_interval)
                continue

            eligible = bool(elig.get("eligible", False))
            honesty = elig.get("honesty", {})

            # Rising edge: false → true
            if eligible and not seat_open:
                # VSS-7: verify signer is not a bot before OPEN
                if cached_role is None and not cfg.dry_run:
                    print("[*] checking signer role (VSS-7)…", file=sys.stderr)
                    cached_role = check_signer_is_not_bot(cfg)
                if cached_role == "bot":
                    print("[!] signer is role=bot — refusing OPEN (VSS-7)",
                          file=sys.stderr)
                    time.sleep(cfg.poll_interval)
                    continue
                if cached_role is None and not cfg.dry_run:
                    print("[!] cannot verify signer role — refusing OPEN (fail-closed)",
                          file=sys.stderr)
                    time.sleep(cfg.poll_interval)
                    continue
                # dry-run: skip the role check (no relay needed)
                if cfg.dry_run and cached_role is None:
                    cached_role = "human"  # assume human in dry-run

                print("[*] rising edge → OPEN", file=sys.stderr)
                result = _build_and_publish(
                    cfg, SEAT_OPEN, eligible=True, honesty=honesty,
                    signer_role=cached_role,
                )
                if result:
                    print(f"[+] OPEN: {result.get('event_id', '?')}",
                          file=sys.stderr)
                    seat_open = True
                else:
                    print("[!] OPEN publish failed — seat stays CLOSED",
                          file=sys.stderr)

            # Falling edge: true → false
            elif not eligible and seat_open:
                print("[*] falling edge → CLOSED", file=sys.stderr)
                result = _build_and_publish(
                    cfg, SEAT_CLOSED, eligible=False, honesty=honesty,
                    signer_role=cached_role,
                )
                if result:
                    print(f"[+] CLOSED: {result.get('event_id', '?')}",
                          file=sys.stderr)
                    seat_open = False
                else:
                    print("[!] CLOSED publish failed — seat stays OPEN (stale)",
                          file=sys.stderr)

            time.sleep(cfg.poll_interval)

    except KeyboardInterrupt:
        print("\n[*] shutting down", file=sys.stderr)
        # Best-effort close on shutdown
        if seat_open and not cfg.dry_run:
            print("[*] closing seat on shutdown…", file=sys.stderr)
            _build_and_publish(
                cfg, SEAT_CLOSED, eligible=False,
                honesty={"poep_enabled": False, "l6b_enabled": False,
                         "candidate_ok": False},
            )
        return 0

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VSS seat open/close helper (gamer key, Architecture C)",
    )
    parser.add_argument(
        "--channel", type=str, default="",
        help="#streams channel UUID (or set VSS_STREAMS_CHANNEL)",
    )
    parser.add_argument(
        "--media-url", type=str, default="",
        help="Media URL for the stream (required for OPEN in live mode)",
    )
    parser.add_argument(
        "--session-id", type=str, default=None,
        help="Optional session_id (F2 watch-party bind slot)",
    )
    parser.add_argument(
        "--ioid-token", type=str, default=None,
        help="Optional ioID token (display only, never required)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=15.0,
        help="Poll interval in seconds (default: 15)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Dry-run mode: poll + print, no publish",
    )
    args = parser.parse_args()

    if not args.dry_run:
        if not os.environ.get("BUZZ_PRIVATE_KEY"):
            sys.exit(
                "BUZZ_PRIVATE_KEY is required (the GAMER's key, not the bot's). "
                "Set it in your environment."
            )

    cfg = _load_config(args)
    return run_seat_loop(cfg)


if __name__ == "__main__":
    sys.exit(main())
