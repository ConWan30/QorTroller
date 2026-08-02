#!/usr/bin/env python3
"""
buzz_ioid_claim.py — Gamer-side ioID claim flow for Buzz.

Phase 3 gamer sovereignty: the gamer posts their OWN kind 0 profile and a
#lobby claim message linking their Buzz npub to their QorTroller ioID.
The operator never holds the gamer private key — the gamer runs this script
(or their personal agent runs it with their key) from their own machine.

The claim is a self-asserted pointer: "I am npub X and I claim ioID tokenId 498."
The cryptographic proof still lives in QorTroller (the ioID registry on IoTeX).
A future version can add relay-side ioID verification.

Usage:
  python scripts/buzz_ioid_claim.py --ioid-token 498 --device-id 581a836c
  python scripts/buzz_ioid_claim.py --ioid-token 498 --gamer-name "Con" --dry-run

Requirements:
  - BUZZ_PRIVATE_KEY (the GAMER's key, NOT the bot/operator key)
  - BUZZ_LOBBY_CHANNEL_ID (preferred) or first entry in BUZZ_CHANNEL_IDS
  - BUZZ_RELAY_URL (default ws://localhost:3000 for the qortroller-buzz helper)
  - BUZZ_HTTP_RELAY_URL (default http://localhost:3000 for the buzz CLI)
  - buzz CLI binary (BUZZ_CLI_PATH or auto-detected)
  - qortroller-buzz helper (BUZZ_HELPER_PATH or auto-detected)

The script:
  1. Sets the gamer kind 0 profile with --name and an about line that mentions
     the ioID token and device id.
  2. Posts a kind 9 claim message to #lobby with custom tags (npub, ioid_claim,
     device_id, qortroller).

Never touches the operator's key. Never posts raw biometrics.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def _to_ws(url: str) -> str:
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    return url


def _to_http(url: str) -> str:
    if url.startswith("ws://"):
        return "http://" + url[len("ws://"):]
    if url.startswith("wss://"):
        return "https://" + url[len("wss://"):]
    return url


_raw_relay = os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000")
RELAY_URL = _to_ws(_raw_relay)
HTTP_RELAY_URL = os.environ.get("BUZZ_HTTP_RELAY_URL") or _to_http(_raw_relay) or "http://localhost:3000"


def _default_cli_path() -> str:
    return str(REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe")


def _default_helper_path() -> str:
    return str(REPO_ROOT / "buzz" / "target" / "debug" / "qortroller-buzz.exe")


def _cli_path() -> str:
    env = os.environ.get("BUZZ_CLI_PATH", "")
    if env and os.path.isfile(env):
        return env
    default = _default_cli_path()
    if os.path.isfile(default):
        return default
    return env or default


def _helper_path() -> str:
    env = os.environ.get("BUZZ_HELPER_PATH", "")
    if env and os.path.isfile(env):
        return env
    default = _default_helper_path()
    if os.path.isfile(default):
        return default
    return env or default


def _buzz_cli(args: list[str]) -> tuple[int, str, str]:
    """Run a buzz CLI command. Returns (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = HTTP_RELAY_URL
    # Gamer self-claims do not use owner attestation (NIP-OA). A stale or
    # mismatched BUZZ_AUTH_TAG will cause the relay to reject the event.
    env.pop("BUZZ_AUTH_TAG", None)
    cli = _cli_path()
    try:
        result = subprocess.run(
            [cli] + args,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def _whoami_bech32() -> Optional[str]:
    """Return the bech32 npub for BUZZ_PRIVATE_KEY, or None."""
    pk = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not pk:
        return None
    try:
        from nostr_sdk import Keys
        keys = Keys.parse(pk)
        return keys.public_key().to_bech32()
    except Exception:
        # Try the qortroller-buzz helper and convert hex to bech32
        hex_pk = _whoami_hex()
        if not hex_pk:
            return None
        try:
            from nostr_sdk import PublicKey
            return PublicKey.from_hex(hex_pk).to_bech32()
        except Exception:
            return None


def _whoami_hex() -> str:
    """Get the gamer pubkey hex from the qortroller-buzz helper."""
    helper = _helper_path()
    if not os.path.isfile(helper):
        return ""
    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = RELAY_URL
    env.pop("BUZZ_AUTH_TAG", None)
    try:
        result = subprocess.run(
            [helper, "whoami"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            shell=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _get_profile(npub: str) -> Optional[dict]:
    """Read the current kind 0 profile for the given bech32 npub."""
    rc, stdout, _ = _buzz_cli(["users", "get", "--pubkey", npub])
    if rc != 0 or not stdout:
        return None
    try:
        data = json.loads(stdout)
        if isinstance(data, list) and data:
            return data[0]
        return data
    except json.JSONDecodeError:
        return None


def _set_profile(name: str, about: str, dry_run: bool) -> bool:
    """Set the gamer kind 0 profile via the buzz CLI.

    The buzz CLI `users set-profile` does not support custom tags, so the
    ioID token and device id are placed in the `about` field. This is a
    self-asserted pointer; the proof lives in QorTroller.
    """
    if dry_run:
        print(f"[dry-run] would set kind 0 profile: name={name!r} about={about!r}")
        return True

    if not name:
        # Try to keep existing name
        npub = _whoami_bech32()
        existing = _get_profile(npub) if npub else None
        name = (existing or {}).get("display_name") or (existing or {}).get("name") or ""

    args = ["users", "set-profile", "--about", about]
    if name:
        args += ["--name", name]

    rc, _, stderr = _buzz_cli(args)
    if rc != 0:
        print(f"[!] profile update failed: {stderr}", file=sys.stderr)
        return False
    return True


def _lobby_channel_id(args_lobby: str) -> str:
    if args_lobby:
        return args_lobby
    env_lobby = os.environ.get("BUZZ_LOBBY_CHANNEL_ID", "").strip()
    if env_lobby:
        return env_lobby
    channels = os.environ.get("BUZZ_CHANNEL_IDS", "")
    first = [c.strip() for c in channels.split(",") if c.strip()]
    if first:
        return first[0]
    return ""


def _post_claim_message(
    channel_id: str, npub: str, ioid_token: str, device_id: str, dry_run: bool
) -> bool:
    """Post a kind 9 claim message to #lobby with NIP-29 `h` tag."""
    helper = _helper_path()
    if not os.path.isfile(helper):
        print(f"[!] qortroller-buzz helper not found: {helper}", file=sys.stderr)
        return False

    content = f"ioID claim: {npub} links to ioID tokenId {ioid_token}"
    if device_id:
        content += f" (device {device_id})"
    content += ". Proof lives in QorTroller."

    tags = [
        ["qortroller", "1"],
        ["ioid_claim", str(ioid_token)],
        ["npub", npub],
    ]
    if device_id:
        tags.append(["device_id", device_id])

    payload = json.dumps({
        "channel": channel_id,
        "content": content,
        "tags": tags,
    })

    if dry_run:
        print(f"[dry-run] would post to #lobby channel {channel_id}:")
        print(payload)
        return True

    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = RELAY_URL
    # Gamer self-claims do not use owner attestation (NIP-OA).
    env.pop("BUZZ_AUTH_TAG", None)
    try:
        result = subprocess.run(
            [helper, "publish"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        if result.returncode != 0:
            print(f"[!] claim publish failed: {result.stderr.strip()}", file=sys.stderr)
            return False
        resp = json.loads(result.stdout.strip())
        return resp.get("accepted", False)
    except Exception as e:
        print(f"[!] claim publish error: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post a gamer ioID claim to Buzz (gamer sovereignty)."
    )
    parser.add_argument(
        "--ioid-token", required=True,
        help="ioID tokenId (e.g. 498)",
    )
    parser.add_argument(
        "--device-id", default="",
        help="Controller device ID (e.g. 581a836c)",
    )
    parser.add_argument(
        "--gamer-name", default="",
        help="Display name for the kind 0 profile",
    )
    parser.add_argument(
        "--lobby-channel", default="",
        help="Channel UUID to post the claim message (default: BUZZ_LOBBY_CHANNEL_ID or first BUZZ_CHANNEL_IDS entry)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be posted without signing or sending",
    )
    args = parser.parse_args()

    privkey = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not privkey:
        print("[!] BUZZ_PRIVATE_KEY is required (the GAMER's key, not the bot's)", file=sys.stderr)
        return 1

    npub = _whoami_bech32()
    if not npub:
        print("[!] could not determine your npub — check BUZZ_PRIVATE_KEY", file=sys.stderr)
        return 1
    print(f"[*] your npub: {npub}", file=sys.stderr)

    lobby = _lobby_channel_id(args.lobby_channel)
    if not lobby:
        print("[!] no lobby channel configured. Set BUZZ_LOBBY_CHANNEL_ID or BUZZ_CHANNEL_IDS.", file=sys.stderr)
        return 1

    about = f"Gamer. ioID tokenId {args.ioid_token}. Proof lives in QorTroller."
    if args.device_id:
        about += f" Device id {args.device_id}."

    ok = True
    print(f"[*] setting kind 0 profile with ioid_token={args.ioid_token}...", file=sys.stderr)
    if _set_profile(args.gamer_name, about, args.dry_run):
        print("[*] profile updated", file=sys.stderr)
    else:
        print("[!] profile update failed", file=sys.stderr)
        ok = False

    print(f"[*] posting claim to #lobby {lobby[:8]}...", file=sys.stderr)
    if _post_claim_message(lobby, npub, args.ioid_token, args.device_id, args.dry_run):
        print(f"[*] claim posted! npub={npub} ioID={args.ioid_token}", file=sys.stderr)
    else:
        print("[!] claim message failed to post", file=sys.stderr)
        ok = False

    if ok:
        print(f"[*] done. Your npub {npub} now claims ioID tokenId {args.ioid_token}.", file=sys.stderr)
        print("[*] The operator never touched your private key.", file=sys.stderr)
        return 0
    print("[!] claim flow completed with errors.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
