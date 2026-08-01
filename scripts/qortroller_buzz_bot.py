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
from pathlib import Path
from typing import Optional

# Phase 1 Nostr wiring: use a real library (nostr-sdk) for key/event crypto.
# The Rust helper remains a valid publish transport; nostr-sdk is the default
# when the helper is absent or BUZZ_USE_NOSTR_SDK is set.
try:
    from nostr_sdk import Keys, Event, EventBuilder, Tag, Client, Kind, NostrSigner, RelayUrl

    _NOSTR_SDK = True
except ImportError:
    _NOSTR_SDK = False

# --- .env loading (scripts/.env) --------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, encoding="utf-8")
except ImportError:
    pass

# --- Config -----------------------------------------------------------------

RELAY_URL = os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000")
CHANNEL_IDS = [
    c.strip() for c in os.environ.get("BUZZ_CHANNEL_IDS", "").split(",") if c.strip()
]
# Matches channel — where session postcards (§3.2) are published for pinning.
# Defaults to the second channel in CHANNEL_IDS if not explicitly set.
MATCHES_CHANNEL_ID = os.environ.get("BUZZ_MATCHES_CHANNEL_ID", "")
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
# Session digest interval (seconds). Posts a §3.2 postcard periodically.
# Default 120s — less frequent than rig status, since session state changes slowly.
SESSION_DIGEST_INTERVAL = float(os.environ.get("BUZZ_SESSION_DIGEST_INTERVAL", "120"))


@dataclass
class BotConfig:
    relay_url: str
    channel_ids: list[str]
    matches_channel_id: str
    bot_name: str
    bot_about: str
    device_id: str
    ioid_token: str
    bridge_base_url: str
    bridge_api_key: str
    bot_privkey: str
    owner_attested: bool
    helper_path: str
    cli_path: str
    status_interval: float
    command_poll_interval: float
    session_digest_interval: float


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
        matches_channel_id=MATCHES_CHANNEL_ID,
        bot_name=BOT_NAME,
        bot_about=BOT_ABOUT,
        device_id=DEVICE_ID,
        ioid_token=IOID_TOKEN,
        bridge_base_url=BRIDGE_BASE_URL,
        bridge_api_key=BRIDGE_API_KEY,
        bot_privkey=BOT_PRIVKEY,
        owner_attested=bool(OWNER_PRIVKEY),
        helper_path=BUZZ_HELPER_PATH,
        cli_path=BUZZ_CLI_PATH,
        status_interval=STATUS_INTERVAL,
        command_poll_interval=COMMAND_POLL_INTERVAL,
        session_digest_interval=SESSION_DIGEST_INTERVAL,
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

    Endpoint paths:
      /health                          — root app (no auth)
      /operator/bridge/capture-health  — DualShock HID poll rate + capture state
      /operator/bridge/retina-status   — retina perception + capture active
    """
    health = _bridge_get("/health", cfg, timeout=5)
    bridge_up = bool(health and health.get("status") in ("ok", "healthy"))

    # DualShock state from the PCC monitor (capture-health endpoint)
    ds = _bridge_get("/operator/bridge/capture-health", cfg, timeout=3) or {}
    capture_state = ds.get("capture_state", "")
    host_state = ds.get("host_state", "")
    poll_rate = ds.get("poll_rate_hz", 0)
    dualshock = (
        capture_state in ("NOMINAL", "DEGRADED")
        or host_state in ("EXCLUSIVE_USB", "EXCLUSIVE_BT")
        or poll_rate > 0
    )

    # Retina/capture state from the retina-status endpoint
    retina = _bridge_get("/operator/bridge/retina-status", cfg, timeout=3) or {}
    capture = bool(
        retina.get("retina_perception_effective")
        or retina.get("retina_perception_enabled")
        or retina.get("capture_active")
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
        # Capture detail (from /operator/bridge/capture-health)
        "capture_state": capture_state,
        "host_state": host_state,
        "poll_rate_hz": poll_rate,
        # Retina detail (from /operator/bridge/retina-status)
        "retina_perception_enabled": bool(retina.get("retina_perception_enabled")),
        "retina_perception_effective": bool(retina.get("retina_perception_effective")),
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
    path = "/operator/player/session-status"
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
    parts = [
        f"rig: {state['rig_state']}",
        f"bridge: {state['bridge_health']}",
        f"oracle: {'enabled' if state['oracle_enabled'] else 'disabled'}",
    ]
    if state.get("capture_state"):
        parts.append(f"capture: {state['capture_state']}")
    if state.get("poll_rate_hz"):
        parts.append(f"poll: {state['poll_rate_hz']:.0f}Hz")
    if state.get("host_state"):
        parts.append(f"host: {state['host_state']}")
    return " | ".join(parts)


def _status_tags(channel_id: str, state: dict) -> list[list[str]]:
    # NOTE: do NOT include ["h", channel_id] — the Rust helper derives the
    # h tag from the "channel" field in the publish payload and refuses
    # caller-supplied h tags (safety rail against tag injection).
    tags = [
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
    # NOTE: do NOT include ["h", channel_id] — the Rust helper derives it.
    tags = [["qortroller", "1"]]
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


def _postcard_content(postcard: dict) -> str:
    """Build the human-readable content line for a session postcard (§3.2)."""
    sid = postcard.get("session_id", "?")
    verdict = postcard.get("verdict", "UNKNOWN")
    n = postcard.get("n_challenges", 0)
    poep = postcard.get("poep_enabled", False)
    l6b = postcard.get("l6b_enabled", False)
    candidate = postcard.get("candidate_ok", False)
    eligible = postcard.get("is_fully_eligible", False)
    humanity = postcard.get("humanity_prob")
    parts = [
        f"session {sid}",
        f"verdict: {verdict}",
        f"N: {n}",
        f"poep: {poep}",
        f"l6b: {l6b}",
        f"candidate_ok: {candidate}",
    ]
    if eligible:
        parts.append("eligible: true")
    if humanity is not None:
        parts.append(f"humanity_prob: {humanity:.3f}")
    return " | ".join(parts)


# --- Nostr event signing / publish (Phase 1 wiring with nostr-sdk) -----------

def _tags_to_nostr_sdk(tags: list[list[str]]) -> list:
    """Convert our tag lists to nostr-sdk Tag objects."""
    return [Tag.parse(t) for t in tags]


def _sign_event(keys: Keys, kind: int, content: str, tags: list[list[str]]) -> Event:
    """Sign a Nostr event with nostr-sdk. Fail-closed on invalid input."""
    builder = EventBuilder(Kind(kind), content).tags(_tags_to_nostr_sdk(tags))
    return builder.sign_with_keys(keys)


async def _publish_nostr_sdk_async(
    cfg: BotConfig, event: Event
) -> Optional[dict]:
    """Publish a signed event via nostr-sdk Client.

    This is async and wrapped in asyncio.run by the sync caller. It does not
    require the Rust helper. Returns {event_id, accepted: True} on success.
    """
    if not _NOSTR_SDK or not cfg.bot_privkey:
        return None
    try:
        keys = Keys.parse(cfg.bot_privkey)
        signer = NostrSigner.keys(keys)
        client = Client(signer)
        await client.add_relay(RelayUrl.parse(cfg.relay_url))
        await client.connect()
        await client.send_event(event)
        await client.disconnect()
        return {"event_id": event.id().to_hex(), "accepted": True}
    except Exception as e:
        print(f"[!] nostr-sdk publish failed: {e}", file=sys.stderr)
        return None


def _publish_nostr_sdk(
    cfg: BotConfig, content: str, tags: list[list[str]]
) -> Optional[dict]:
    """Sync wrapper around the nostr-sdk publish coroutine."""
    import asyncio

    if not _NOSTR_SDK or not cfg.bot_privkey:
        return None
    try:
        keys = Keys.parse(cfg.bot_privkey)
    except Exception as e:
        print(f"[!] invalid BUZZ_PRIVATE_KEY: {e}", file=sys.stderr)
        return None
    event = _sign_event(keys, 9, content, tags)
    try:
        return asyncio.run(_publish_nostr_sdk_async(cfg, event))
    except Exception as e:
        print(f"[!] nostr-sdk publish runner failed: {e}", file=sys.stderr)
        return None


# --- Publish via Rust helper (Architecture C) --------------------------------

def _publish_event(
    cfg: BotConfig, channel_id: str, content: str, tags: list[list[str]]
) -> Optional[dict]:
    """Publish a digest to the Buzz relay.

    Uses the Rust helper by default (NIP-42 auth + NIP-OA attestation).
    Falls back to nostr-sdk when the helper is missing or BUZZ_USE_NOSTR_SDK=1.
    Returns {event_id, accepted} or None on failure.
    """
    use_sdk = _NOSTR_SDK and (os.environ.get("BUZZ_USE_NOSTR_SDK") == "1" or not os.path.isfile(cfg.helper_path))
    if use_sdk:
        return _publish_nostr_sdk(cfg, content, tags)

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

def _poll_commands(
    cfg: BotConfig, since_ts: int, prefixes: tuple[str, ...] = ("!",)
) -> list[dict]:
    """Poll for kind 9 messages since the given Unix timestamp.

    Returns a list of {pubkey, content} dicts for messages that start with one
    of `prefixes` — `!` for the Phase 1 bot commands, `@EA` for the Phase 4 ACP
    gateway. Filters out self-authored messages (by comparing to the bot's
    pubkey via `whoami`).
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
                if content.lower().startswith(tuple(p.lower() for p in prefixes)):
                    messages.append({"pubkey": pubkey, "content": content})
        except Exception:
            continue
    return messages


def _whoami(cfg: BotConfig) -> str:
    """Get the bot's own pubkey.

    Prefer nostr-sdk (real Nostr library) over the Rust helper's whoami command.
    """
    if _NOSTR_SDK and cfg.bot_privkey:
        try:
            keys = Keys.parse(cfg.bot_privkey)
            return keys.public_key().to_hex()
        except Exception:
            pass
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


# --- ACP gateway bridge (Phase 4 integration) -------------------------------

def _run_acp_eval(cfg: BotConfig, pubkey: str, content: str) -> Optional[str]:
    """Run the ACP gateway in one-shot --eval mode via subprocess.

    This keeps the circular import clean: the bot calls the gateway as a CLI,
    not as a module. The operator pubkey is used for allow-list authorization.
    """
    script = Path(__file__).resolve()
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script.parent.parent / "scripts" / "qortroller_acp_gateway.py"),
                "--eval",
                content,
                pubkey,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy(),
            shell=False,
        )
        if result.returncode != 0:
            print(f"[!] acp eval exit {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
            return None
        return result.stdout.strip()
    except Exception as exc:
        print(f"[!] acp eval failed: {exc}", file=sys.stderr)
        return None


# --- Command handlers (bounded, ignore self) --------------------------------

def handle_command(
    cmd: str, cfg: BotConfig, author_pubkey: str = ""
) -> Optional[tuple[str, list[list[str]]]]:
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
        return _postcard_content(pc), _postcard_tags(cfg.channel_ids[0], pc)
    # Phase 4 ACP via Buzz: !ea <command> routes to qortroller_acp_gateway.
    if cmd.lower().startswith("!ea "):
        acp_content = cmd[4:].strip()
        if not acp_content.startswith(("@ea", "@EA")):
            acp_content = f"@EA {acp_content}"
        # The author's pubkey is what matters for ACP operator allow-list.
        caller = author_pubkey or _whoami(cfg) or ""
        reply = _run_acp_eval(cfg, caller, acp_content)
        if reply is None:
            return "ea: ACP gateway unavailable or rejected", []
        return reply, [["acp_tool", "buzz_ea"], ["harness", "buzz"]]
    return None


# --- Main loop ---------------------------------------------------------------

def main() -> int:
    cfg = _load_config()
    print(f"[*] {cfg.bot_name} → {cfg.relay_url}", file=sys.stderr)
    print(f"[*] channels: {cfg.channel_ids}", file=sys.stderr)
    if cfg.matches_channel_id:
        print(f"[*] matches channel: {cfg.matches_channel_id}", file=sys.stderr)
    print(f"[*] owner-attested: {cfg.owner_attested}", file=sys.stderr)
    print(f"[*] bridge: {cfg.bridge_base_url}", file=sys.stderr)
    print(f"[*] helper: {cfg.helper_path}", file=sys.stderr)

    helper_ok = os.path.isfile(cfg.helper_path)
    cli_ok = os.path.isfile(cfg.cli_path)
    nostr_sdk_ok = _NOSTR_SDK and bool(cfg.bot_privkey)
    publish_ok = helper_ok or nostr_sdk_ok
    if not publish_ok:
        print(
            "[!] No publish path: build the Rust helper or install nostr-sdk. "
            "Build: cargo +stable-x86_64-pc-windows-msvc build -p qortroller-buzz",
            file=sys.stderr,
        )
    elif not helper_ok and nostr_sdk_ok:
        print("[*] publish path: nostr-sdk (Rust helper not found)", file=sys.stderr)
    if not cli_ok:
        print(
            "[!] buzz CLI not built — command polling disabled (status-only mode). "
            "Build: cargo +stable-x86_64-pc-windows-msvc build -p buzz-cli",
            file=sys.stderr,
        )

    last_status_state: Optional[str] = None
    last_status_time = 0.0
    last_command_poll = int(time.time())
    last_digest_time = 0.0
    last_digest_signature: Optional[str] = None

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
                    if publish_ok:
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

            # Periodic session digest (§3.2 postcard) — on change OR every
            # session_digest_interval. Only posts when the session state
            # actually changed (signature = verdict + flags + N), so idle
            # sessions don't spam the channel.
            # Routed to #matches (not #rig-ops) — that's where pinned
            # official results live. Falls back to the first rig-ops channel
            # if no matches channel is configured.
            if now - last_digest_time >= cfg.session_digest_interval:
                postcard = _read_session_postcard(cfg)
                if postcard is not None:
                    sig = "|".join(str(postcard.get(k, "")) for k in (
                        "verdict", "poep_enabled", "l6b_enabled",
                        "candidate_ok", "n_challenges", "is_fully_eligible",
                    ))
                    if sig != last_digest_signature:
                        content = _postcard_content(postcard)
                        tags = _postcard_tags(cfg.channel_ids[0], postcard)
                        digest_channel = (
                            cfg.matches_channel_id or cfg.channel_ids[0]
                        )
                        print(f"[*] digest → #{digest_channel[:8]}: {content}", file=sys.stderr)
                        if publish_ok:
                            result = _publish_event(
                                cfg, digest_channel, content, tags
                            )
                            if result:
                                print(
                                    f"[*] digest published: "
                                    f"{result.get('event_id', '?')}",
                                    file=sys.stderr,
                                )
                        last_digest_signature = sig
                    last_digest_time = now

            # Command polling
            if cli_ok and now - last_command_poll >= cfg.command_poll_interval:
                msgs = _poll_commands(cfg, last_command_poll)
                for msg in msgs:
                    reply = handle_command(msg["content"], cfg, msg.get("pubkey", ""))
                    if reply and publish_ok:
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
