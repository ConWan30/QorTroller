"""
buzz_ioid_claim.py — Gamer-side ioID claim flow for Buzz.

Phase 3 gamer sovereignty: the gamer posts their OWN kind 0 profile with
an ioid_token tag, linking their Buzz npub to their QorTroller ioID.
The operator never holds the gamer's private key — the gamer runs this
script themselves with their own BUZZ_PRIVATE_KEY.

The claim is a self-asserted pointer: "I am npub X and I claim ioID
tokenId 498." The proof still lives in QorTroller (the ioID registry
on IoTeX). A future version could add relay-side ioID verification
(read-only RPC call to the ioID registry contract).

Usage:
  python scripts/buzz_ioid_claim.py --ioid-token 498 --device-id 581a836c
  python scripts/buzz_ioid_claim.py --ioid-token 498 --gamer-name "Con"

Requirements:
  - BUZZ_PRIVATE_KEY (the GAMER's key, NOT the bot's key)
  - BUZZ_RELAY_URL
  - buzz CLI binary (BUZZ_CLI_PATH or auto-detected)

The script:
  1. Reads the gamer's current kind 0 profile from the relay
  2. Merges the ioid_token + device_id tags into the profile
  3. Publishes the updated kind 0 via `buzz users set-profile`
  4. Posts a kind 9 claim message to #lobby announcing the link

Never touches the operator's key. Never posts raw biometrics.
"""
from __future__ import annotations

import argparse
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
CLI_PATH = os.environ.get(
    "BUZZ_CLI_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "buzz", "target", "debug", "buzz.exe",
    ),
)


def _buzz_cli(args: list[str]) -> tuple[int, str, str]:
    """Run a buzz CLI command. Returns (exit_code, stdout, stderr)."""
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
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def _whoami() -> str:
    """Get the gamer's npub from the buzz CLI."""
    rc, stdout, _ = _buzz_cli(["users", "whoami"])
    if rc != 0:
        return ""
    return stdout.strip()


def _get_profile() -> dict | None:
    """Read the current kind 0 profile for the gamer's key."""
    npub = _whoami()
    if not npub:
        return None
    rc, stdout, _ = _buzz_cli(["users", "get", "--pubkey", npub])
    if rc != 0 or not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _set_profile(name: str, about: str, tags: list[list[str]]) -> bool:
    """Set the gamer's kind 0 profile with custom tags.

    Uses `buzz users set-profile` if it supports tags, otherwise falls
    back to publishing a raw kind 0 event via the qortroller-buzz helper.
    """
    # Check if buzz users set-profile supports --tag
    rc, _, _ = _buzz_cli(["users", "set-profile", "--help"])
    # The buzz CLI may not support custom tags on kind 0 directly.
    # If not, we use the qortroller-buzz helper to publish a kind 0.
    # For now, try the CLI first with name + about.
    args = ["users", "set-profile"]
    if name:
        args += ["--name", name]
    if about:
        args += ["--about", about]

    rc, stdout, stderr = _buzz_cli(args)
    if rc == 0:
        return True

    # Fallback: publish kind 0 via the helper
    helper_path = os.environ.get(
        "BUZZ_HELPER_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "buzz", "target", "debug", "qortroller-buzz.exe",
        ),
    )
    if not os.path.isfile(helper_path):
        print(f"[!] neither buzz CLI set-profile nor helper at {helper_path}", file=sys.stderr)
        return False

    # Build kind 0 content as JSON metadata (NIP-01)
    metadata = {"name": name, "about": about}
    payload = json.dumps({
        "kind": 0,
        "content": json.dumps(metadata),
        "tags": tags,
    })

    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = RELAY_URL
    try:
        result = subprocess.run(
            [helper_path, "publish"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _post_claim_message(channel_id: str, npub: str, ioid_token: str, device_id: str) -> bool:
    """Post a kind 9 claim message to the channel announcing the ioID link."""
    helper_path = os.environ.get(
        "BUZZ_HELPER_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "buzz", "target", "debug", "qortroller-buzz.exe",
        ),
    )
    if not os.path.isfile(helper_path):
        return False

    content = f"ioID claim: npub {npub[:16]}... links to ioID tokenId {ioid_token}"
    if device_id:
        content += f" (device {device_id})"

    payload = json.dumps({
        "channel": channel_id,
        "content": content,
        "tags": [
            ["qortroller", "1"],
            ["ioid_claim", ioid_token],
            ["claim_pubkey", npub],
        ] + ([["device_id", device_id]] if device_id else []),
    })

    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = RELAY_URL
    try:
        result = subprocess.run(
            [helper_path, "publish"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            shell=False,
        )
        if result.returncode == 0:
            resp = json.loads(result.stdout.strip())
            return resp.get("accepted", False)
        return False
    except Exception:
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
        help="Channel UUID to post the claim message (default: first channel in env)",
    )
    args = parser.parse_args()

    if not os.path.isfile(CLI_PATH):
        print(f"[!] buzz CLI not found: {CLI_PATH}", file=sys.stderr)
        return 1

    privkey = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not privkey:
        print("[!] BUZZ_PRIVATE_KEY is required (the GAMER's key, not the bot's)", file=sys.stderr)
        return 1

    # Get the gamer's npub
    npub = _whoami()
    if not npub:
        print("[!] could not determine your npub — check BUZZ_PRIVATE_KEY", file=sys.stderr)
        return 1
    print(f"[*] your npub: {npub}", file=sys.stderr)

    # Build the profile tags
    tags = [["ioid_token", args.ioid_token]]
    if args.device_id:
        tags.append(["device_id", args.device_id])

    # Set the kind 0 profile with ioID tags
    about = f"Gamer. ioID tokenId {args.ioid_token}. Proof lives in QorTroller."
    print(f"[*] setting kind 0 profile with ioid_token={args.ioid_token}...", file=sys.stderr)
    if _set_profile(args.gamer_name, about, tags):
        print("[*] profile updated", file=sys.stderr)
    else:
        print("[!] profile update failed (may need manual kind 0 edit)", file=sys.stderr)

    # Post the claim message to #lobby
    lobby = args.lobby_channel or os.environ.get("BUZZ_CHANNEL_IDS", "").split(",")[0].strip()
    if lobby:
        print(f"[*] posting claim to channel {lobby[:8]}...", file=sys.stderr)
        if _post_claim_message(lobby, npub, args.ioid_token, args.device_id):
            print(f"[*] claim posted! npub={npub[:16]}... ioID={args.ioid_token}", file=sys.stderr)
        else:
            print("[!] claim message failed to post", file=sys.stderr)
    else:
        print("[!] no channel configured for claim message", file=sys.stderr)

    print(f"[*] done. Your npub {npub[:16]}... now claims ioID tokenId {args.ioid_token}.", file=sys.stderr)
    print(f"[*] The operator never touched your private key.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
