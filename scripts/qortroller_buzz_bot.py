"""
QorTroller Buzz bot — Phase 1 scaffold (PROPOSED, not yet wired).

Implements the corrected "Option 1" from
docs/design/buzz-qortroller-gamer-mvp-v0.md.

Shape follows buzz/examples/countdown-bot:
  - kind 0 profile
  - kind 9000 self-add as role=bot
  - NIP-42 auth (standalone or owner-attested via NIP-OA)
  - subscribe to kind 9 on h-tagged channels
  - bounded commands (!status, !ready, !session <id>)
  - emit kind 9 status + session postcard events (digest tags only)

NO raw biometrics, NO nsec in source, NO fabricated SYNCHRONIZED.
Reads real QorTroller state from qortroller.HardwareWatcher / BridgeClient.

This file is a scaffold: the signing + WS loop is stubbed behind
`_sign_event`, `_ws_connect`, `_ws_send`, `_ws_recv` so the protocol
shape is reviewable without pulling in a Nostr library yet. Phase 1
implementation will fill those in (prefer nostr-sdk via a small Rust
shim, or python-nostr, NOT hand-rolled secp256k1).

Operator greenlight required before this is wired live — see design doc §13.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

# --- Config -----------------------------------------------------------------

RELAY_URL = os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000")
CHANNEL_IDS = [
    c.strip() for c in os.environ.get("BUZZ_CHANNEL_IDS", "").split(",") if c.strip()
]
BOT_NAME = os.environ.get("QORTROLLER_BOT_NAME", "QorTroller Rig EA")
BOT_ABOUT = os.environ.get(
    "QORTROLLER_BOT_ABOUT",
    "Operator steward: rig status + session digests. Proof lives in QorTroller, not chat.",
)
DEVICE_ID = os.environ.get("QORTROLLER_DEVICE_ID", "")
IOID_TOKEN = os.environ.get("QORTROLLER_IOID_TOKEN", "")
BRIDGE_BASE_URL = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000")

# Keys MUST come from env. Refuse to run if missing.
BOT_PRIVKEY = os.environ.get("BUZZ_PRIVATE_KEY", "")
OWNER_PRIVKEY = os.environ.get("BUZZ_OWNER_PRIVATE_KEY", "")  # optional (NIP-OA)


@dataclass
class BotConfig:
    relay_url: str
    channel_ids: list[str]
    bot_name: str
    bot_about: str
    device_id: str
    ioid_token: str
    bridge_base_url: str
    owner_attested: bool


def _load_config() -> BotConfig:
    if not BOT_PRIVKEY:
        sys.exit(
            "BUZZ_PRIVATE_KEY is required (env only, never committed). "
            "See scripts/qortroller_buzz_bot.env.example."
        )
    if not CHANNEL_IDS:
        sys.exit("BUZZ_CHANNEL_IDS must list at least one channel UUID.")
    return BotConfig(
        relay_url=RELAY_URL,
        channel_ids=CHANNEL_IDS,
        bot_name=BOT_NAME,
        bot_about=BOT_ABOUT,
        device_id=DEVICE_ID,
        ioid_token=IOID_TOKEN,
        bridge_base_url=BRIDGE_BASE_URL,
        owner_attested=bool(OWNER_PRIVKEY),
    )


# --- QorTroller state reads (truth plane) ------------------------------------

def _read_rig_state(cfg: BotConfig) -> dict:
    """Read real HardwareWatcher / BridgeClient state. Never fabricate.

    Phase 1 will import from qortroller.py without launching the TUI:
        from qortroller import HardwareWatcher, BridgeClient, HardwareState
    For now this returns an honest 'unknown' shape so the bot cannot lie.
    """
    return {
        "rig_state": "UNKNOWN",
        "bridge_health": "unknown",
        "oracle_enabled": False,
        "device_id": cfg.device_id,
        "ioid_token": cfg.ioid_token,
    }


def _read_session_postcard(session_id: str) -> Optional[dict]:
    """Look up a session postcard from .qortroller/sessions.db.

    Returns the digest shape from design doc §3.2, or None if not found.
    Never returns raw biometrics.
    """
    # Phase 1: query the EA SessionHistory sqlite for the session id and
    # surface only: session_id, verdict, commitment_root, n_challenges,
    # poep_enabled, l6b_enabled, candidate_ok.
    return None


# --- Event builders (Buzz-correct shape, digest-only) -----------------------

def _status_event_content(state: dict) -> str:
    return (
        f"rig: {state['rig_state']} | "
        f"bridge: {state['bridge_health']} | "
        f"oracle: {'enabled' if state['oracle_enabled'] else 'disabled'}"
    )


def _status_tags(channel_id: str, state: dict) -> list[list[str]]:
    tags = [
        ["h", channel_id],
        ["qortroller", "1"],
        ["rig_state", state["rig_state"]],
        ["bridge_health", state["bridge_health"]],
        ["oracle_enabled", "true" if state["oracle_enabled"] else "false"],
    ]
    if state.get("device_id"):
        tags.append(["device_id", state["device_id"]])
    if state.get("ioid_token"):
        tags.append(["ioid_token", state["ioid_token"]])
    return tags


def _postcard_tags(channel_id: str, postcard: dict) -> list[list[str]]:
    """Honesty-tagged session postcard. Missing fields are posted as-is."""
    tags = [["h", channel_id], ["qortroller", "1"]]
    for key in (
        "session_id",
        "verdict",
        "commitment_root",
        "n_challenges",
        "poep_enabled",
        "l6b_enabled",
        "candidate_ok",
    ):
        if key in postcard:
            tags.append([key, str(postcard[key])])
    return tags


# --- Nostr signing + WS loop (stubs — Phase 1 fills these in) ---------------

def _sign_event(event: dict, privkey_hex: str) -> str:  # noqa: ARG001
    raise NotImplementedError(
        "Phase 1: implement with nostr-sdk (preferred) or python-nostr. "
        "Do NOT hand-roll secp256k1 — NIP-01 id is "
        "sha256([0, pubkey, created_at, kind, tags, content]), not sort_keys JSON."
    )


def _ws_connect(url: str):  # noqa: ARG001
    raise NotImplementedError("Phase 1: implement NIP-42 auth + optional NIP-OA tag.")


def _ws_send(ws, frame: str):  # noqa: ARG001
    raise NotImplementedError


def _ws_recv(ws):  # noqa: ARG001
    raise NotImplementedError


# --- Command handlers (bounded, ignore self) --------------------------------

def handle_command(cmd: str, cfg: BotConfig) -> Optional[tuple[str, list[list[str]]]]:
    """Return (content, tags) for a channel reply, or None to stay silent."""
    cmd = cmd.strip()
    if cmd == "!status":
        state = _read_rig_state(cfg)
        return _status_event_content(state), _status_tags(cfg.channel_ids[0], state)
    if cmd == "!ready":
        state = _read_rig_state(cfg)
        ready = state["rig_state"] in ("ALL_READY", "all_ready")
        return (f"ready: {ready} (rig_state={state['rig_state']})"), []
    if cmd.startswith("!session "):
        sid = cmd[len("!session "):].strip()
        pc = _read_session_postcard(sid)
        if pc is None:
            return f"session {sid}: not found", []
        content = (
            f"session {pc.get('session_id', sid)} | "
            f"verdict: {pc.get('verdict', 'UNKNOWN')} | "
            f"N: {pc.get('n_challenges', 0)}"
        )
        return content, _postcard_tags(cfg.channel_ids[0], pc)
    return None


# --- Main loop (scaffold) ----------------------------------------------------

def main() -> int:
    cfg = _load_config()
    print(f"[*] {cfg.bot_name} → {cfg.relay_url}", file=sys.stderr)
    print(f"[*] channels: {cfg.channel_ids}", file=sys.stderr)
    print(f"[*] owner-attested: {cfg.owner_attested}", file=sys.stderr)
    print(
        "[*] scaffold only — signing/WS loop is stubbed. "
        "Phase 1 implementation required before live run.",
        file=sys.stderr,
    )
    # When wired:
    #   ws = _ws_connect(cfg.relay_url)
    #   publish kind 0 profile
    #   for ch in cfg.channel_ids: publish kind 9000 self-add role=bot
    #   subscribe kind 9 on h=ch for each channel
    #   loop: recv → if EVENT kind 9 with !command in content and not self → reply
    #   on rig state change / session end → emit status / postcard
    return 0


if __name__ == "__main__":
    sys.exit(main())
