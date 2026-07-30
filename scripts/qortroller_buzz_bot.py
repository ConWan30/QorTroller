"""
QorTroller Buzz bot — Phase 1 (WIRED read path + Rust-helper publish).

Implements Architecture C from docs/design/buzz-qortroller-gamer-mvp-v0.md:
  Python (truth plane)  ──►  Rust helper (bytes on the wire)
    BridgeClient HTTP          qortroller-buzz publish
    computes digest JSON       signs kind 9 + custom tags
    never touches crypto       NIP-42 + NIP-OA via buzz-ws-client

Read path:
  - _read_rig_state  → BridgeClient sync HTTP (/health, /dualshock/status,
    /retina/status) → same HardwareState enum the TUI watcher uses.
  - _read_session_postcard → BridgeClient GET /player/session-status
    (x-api-key header) → extracts the digest fields that actually exist
    in the response (poep_enabled, l6b_enabled, l6b_probe_count,
    is_fully_eligible, humanity_prob, device_id). No fabricated fields.

Publish path:
  - _publish_event builds {channel, content, tags} JSON and pipes it to
    the qortroller-buzz Rust helper's stdin. The helper signs + sends.
  - No Nostr signing in Python (F-2: no BIP-340 Schnorr library here).

Command loop:
  - Polls `buzz messages get --channel <id> --since <ts> --kinds 9` for
    kind 9 messages, filters for !commands from non-self authors, replies
    via the publish helper.

NO raw biometrics, NO nsec in source, NO fabricated SYNCHRONIZED.
Honesty flags posted as-is: poep_enabled=false, l6b_enabled=false until
the operator actually flips them.
"""
from __future__ import annotations

import json
import os
import subprocess
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
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "")  # optional (fail-open in dev)

# Keys MUST come from env. Refuse to run if missing.
BOT_PRIVKEY = os.environ.get("BUZZ_PRIVATE_KEY", "")
OWNER_PRIVKEY = os.environ.get("BUZZ_OWNER_PRIVATE_KEY", "")  # optional (NIP-OA)

# Path to the Rust helper binary (built from buzz/examples/qortroller-buzz).
BUZZ_HELPER_PATH = os.environ.get(
    "BUZZ_HELPER_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "buzz", "target", "debug", "qortroller-buzz.exe",
    ),
)
# Path to the buzz CLI binary (for `buzz messages get` polling).
BUZZ_CLI_PATH = os.environ.get(
    "BUZZ_CLI_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "buzz", "target", "debug", "buzz.exe",
    ),
)

# Poll intervals (seconds).
STATUS_INTERVAL = float(os.environ.get("BUZZ_STATUS_INTERVAL", "30"))
COMMAND_POLL_INTERVAL = float(os.environ.get("BUZZ_COMMAND_POLL_INTERVAL", "10"))


@dataclass
class BotConfig:
    relay_url: str
    channel_ids: list[str]
    bot_name: str
    bot_about: str
    device_id: str
    ioid_token: str
    bridge_base_url: str
    bridge_api_key: str
    owner_attested: bool
    helper_path: str
    cli_path: str
    status_interval: float
    command_poll_interval: float


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
        bridge_api_key=BRIDGE_API_KEY,
        owner_attested=bool(OWNER_PRIVKEY),
        helper_path=BUZZ_HELPER_PATH,
        cli_path=BUZZ_CLI_PATH,
        status_interval=STATUS_INTERVAL,
        command_poll_interval=COMMAND_POLL_INTERVAL,
    )


# --- QorTroller state reads (truth plane) ------------------------------------

def _bridge_get(path: str, cfg: BotConfig, timeout: float = 5) -> Optional[dict]:
    """Sync HTTP GET to the bridge operator API with optional x-api-key."""
    try:
        import requests
        headers = {}
        if cfg.bridge_api_key:
            headers["x-api-key"] = cfg.bridge_api_key
        resp = requests.get(
            f"{cfg.bridge_base_url}{path}", headers=headers, timeout=timeout
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _read_rig_state(cfg: BotConfig) -> dict:
    """Read real bridge state via sync HTTP. Never fabricate.

    Mirrors HardwareWatcher._poll but as a one-shot sync read — no async
    loop, no HID enumeration (the bridge is the single source of truth for
    rig state when the bot is running alongside it).
    """
    health = _bridge_get("/health", cfg, timeout=5)
    bridge_up = bool(health and health.get("status") == "healthy")

    ds = _bridge_get("/dualshock/status", cfg, timeout=3) or {}
    dualshock = bool(ds.get("connected") or ds.get("status") == "active")

    retina = _bridge_get("/retina/status", cfg, timeout=3) or {}
    # Try the operator-facing retina status endpoint first
    if not retina:
        retina = _bridge_get("/bridge/retina-status", cfg, timeout=3) or {}
    capture = bool(
        retina.get("capture_active")
        or retina.get("status") == "active"
    )

    # State machine (same logic as HardwareWatcher._poll)
    if dualshock and capture and bridge_up:
        rig_state = "all_ready"
    elif dualshock and capture:
        rig_state = "capture_detected"
    elif dualshock:
        rig_state = "dualshock_detected"
    elif bridge_up:
        rig_state = "bridge_up"
    else:
        rig_state = "idle"

    return {
        "rig_state": rig_state,
        "bridge_health": "healthy" if bridge_up else "unreachable",
        "dualshock_connected": dualshock,
        "capture_active": capture,
        "oracle_enabled": capture,
        "device_id": cfg.device_id,
        "ioid_token": cfg.ioid_token,
    }


def _read_session_postcard(cfg: BotConfig, session_id: str = "") -> Optional[dict]:
    """Read a session postcard from the bridge /player/session-status endpoint.

    Extracts only the digest fields that actually exist in the response.
    Never returns raw biometrics. Returns None if the bridge is unreachable.

    The bridge endpoint returns the CURRENT session state for a device;
    it does not archive historical sessions by arbitrary session_id. For
    Phase 1, we read the current/active session. A historical session
    lookup requires the PoEP session runner's artifact store (Phase 2).
    """
    path = "/player/session-status"
    if cfg.device_id:
        path += f"?device_id={cfg.device_id}"
    data = _bridge_get(path, cfg, timeout=10)
    if not data:
        return None

    poep = (data.get("presence") or {}).get("poep") or {}
    cco = data.get("cco") or {}
    identity_grid = data.get("identity_grid") or {}

    return {
        "session_id": session_id or data.get("device_id", ""),
        "session_active": bool(data.get("session_active")),
        "device_id": data.get("device_id", ""),
        "verdict": (
            identity_grid.get("identity_class")
            or ("eligible" if data.get("is_fully_eligible") else "unknown")
        ),
        "is_fully_eligible": bool(data.get("is_fully_eligible")),
        "humanity_prob": data.get("humanity_prob"),
        "poep_enabled": bool(poep.get("enabled")),
        "l6b_enabled": bool(cco.get("l6b_enabled")),
        "l6b_probe_count": poep.get("l6b_probe_count", 0),
        "l6b_gate_reached": bool(poep.get("l6b_gate_reached")),
        "candidate_ok": bool(poep.get("presence_ceiling_candidate")),
        "commitment_root": None,  # not in this endpoint; Phase 2 from PoAC/GIC
        "n_challenges": poep.get("l6b_probe_count", 0),
    }


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
        if key in postcard and postcard[key] is not None:
            tags.append([key, str(postcard[key])])
    return tags


# --- Publish via Rust helper (Architecture C) --------------------------------

def _publish_event(
    cfg: BotConfig, channel_id: str, content: str, tags: list[list[str]]
) -> Optional[dict]:
    """Pipe a digest JSON to the qortroller-buzz Rust helper's stdin.

    The helper signs the Nostr event (BIP-340 Schnorr) and publishes to
    the relay with NIP-42 auth + NIP-OA attestation. Returns the helper's
    JSON response ({event_id, accepted, message}) or None on failure.
    """
    if not os.path.isfile(cfg.helper_path):
        print(
            f"[!] helper not found: {cfg.helper_path} — "
            "build with: cargo +stable-x86_64-pc-windows-msvc build -p qortroller-buzz",
            file=sys.stderr,
        )
        return None

    payload = json.dumps({
        "channel": channel_id,
        "content": content,
        "tags": tags,
    })

    env = os.environ.copy()
    # The helper reads BUZZ_PRIVATE_KEY, BUZZ_AUTH_TAG, BUZZ_RELAY_URL from env.
    # Ensure relay URL is set (it may differ from the default in the helper).
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


# --- Command polling via buzz CLI -------------------------------------------

def _poll_commands(cfg: BotConfig, since_ts: int) -> list[dict]:
    """Poll for kind 9 messages since the given Unix timestamp.

    Returns a list of {pubkey, content} dicts for messages that look like
    bot commands (!status, !ready, !session). Filters out self-authored
    messages (by comparing to the bot's pubkey via `whoami`).
    """
    if not os.path.isfile(cfg.cli_path):
        return []  # CLI not built yet — silent (status-only mode)

    bot_pubkey = _whoami(cfg)
    messages: list[dict] = []
    for ch_id in cfg.channel_ids:
        try:
            result = subprocess.run(
                [
                    cfg.cli_path, "messages", "get",
                    "--channel", ch_id,
                    "--since", str(since_ts),
                    "--kinds", "9",
                    "--limit", "20",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                env=os.environ.copy(),
                shell=False,
            )
            if result.returncode != 0:
                continue
            # buzz messages get outputs JSON (one object per line or a JSON array)
            try:
                data = json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                data = [data]
            for msg in data:
                pubkey = msg.get("pubkey", "")
                content = msg.get("content", "").strip()
                if pubkey and bot_pubkey and pubkey == bot_pubkey:
                    continue  # ignore self
                if content.startswith("!"):
                    messages.append({"pubkey": pubkey, "content": content})
        except Exception:
            continue
    return messages


def _whoami(cfg: BotConfig) -> str:
    """Get the bot's own pubkey via the Rust helper's whoami command."""
    if not os.path.isfile(cfg.helper_path):
        return ""
    try:
        result = subprocess.run(
            [cfg.helper_path, "whoami"],
            capture_output=True,
            text=True,
            timeout=10,
            env=os.environ.copy(),
            shell=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


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
    if cmd.startswith("!session"):
        parts = cmd.split(maxsplit=1)
        sid = parts[1].strip() if len(parts) > 1 else ""
        pc = _read_session_postcard(cfg, sid)
        if pc is None:
            return "session: bridge unreachable or no active session", []
        content = (
            f"session {pc.get('session_id', sid)} | "
            f"verdict: {pc.get('verdict', 'UNKNOWN')} | "
            f"N: {pc.get('n_challenges', 0)} | "
            f"poep: {pc.get('poep_enabled')} | "
            f"l6b: {pc.get('l6b_enabled')}"
        )
        return content, _postcard_tags(cfg.channel_ids[0], pc)
    return None


# --- Main loop ---------------------------------------------------------------

def main() -> int:
    cfg = _load_config()
    print(f"[*] {cfg.bot_name} → {cfg.relay_url}", file=sys.stderr)
    print(f"[*] channels: {cfg.channel_ids}", file=sys.stderr)
    print(f"[*] owner-attested: {cfg.owner_attested}", file=sys.stderr)
    print(f"[*] bridge: {cfg.bridge_base_url}", file=sys.stderr)
    print(f"[*] helper: {cfg.helper_path}", file=sys.stderr)

    helper_ok = os.path.isfile(cfg.helper_path)
    cli_ok = os.path.isfile(cfg.cli_path)
    if not helper_ok:
        print(
            "[!] Rust helper not built — publish disabled. "
            "Build: cargo +stable-x86_64-pc-windows-msvc build -p qortroller-buzz",
            file=sys.stderr,
        )
    if not cli_ok:
        print(
            "[!] buzz CLI not built — command polling disabled (status-only mode). "
            "Build: cargo +stable-x86_64-pc-windows-msvc build -p buzz-cli",
            file=sys.stderr,
        )

    last_status_state: Optional[str] = None
    last_status_time = 0.0
    last_command_poll = int(time.time())

    print("[*] entering main loop (Ctrl-C to stop)", file=sys.stderr)
    try:
        while True:
            now = time.time()

            # Periodic rig-state publish (on state change OR every status_interval)
            if now - last_status_time >= cfg.status_interval:
                state = _read_rig_state(cfg)
                if state["rig_state"] != last_status_state or last_status_state is None:
                    content = _status_event_content(state)
                    tags = _status_tags(cfg.channel_ids[0], state)
                    print(f"[*] status: {content}", file=sys.stderr)
                    if helper_ok:
                        result = _publish_event(
                            cfg, cfg.channel_ids[0], content, tags
                        )
                        if result:
                            print(
                                f"[*] published: {result.get('event_id', '?')}",
                                file=sys.stderr,
                            )
                    last_status_state = state["rig_state"]
                    last_status_time = now

            # Command polling
            if cli_ok and now - last_command_poll >= cfg.command_poll_interval:
                msgs = _poll_commands(cfg, last_command_poll)
                for msg in msgs:
                    reply = handle_command(msg["content"], cfg)
                    if reply and helper_ok:
                        content, tags = reply
                        _publish_event(cfg, cfg.channel_ids[0], content, tags)
                        print(
                            f"[*] reply to {msg['pubkey'][:8]}…: {msg['content']}",
                            file=sys.stderr,
                        )
                last_command_poll = int(now)

            time.sleep(min(cfg.command_poll_interval, 5.0))

    except KeyboardInterrupt:
        print("\n[*] shutting down", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
