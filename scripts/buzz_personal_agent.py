#!/usr/bin/env python3
"""Buzz Gamer Personal Agent — QorTroller self-service DM concierge.

A *gamer-facing* agent (not the operator @EA bot). It:
  - Polls your Buzz DMs for new messages.
  - Answers QorTroller self-queries by reading the bridge (no operator keys).
  - Replies in the same DM with digest-only answers.
  - Never touches @EA, shell, chain writes, or raw biometrics.

This is the "personal agent" that runs under the gamer's own BUZZ_PRIVATE_KEY.

Usage:
  $env:BUZZ_PRIVATE_KEY="nsec1..."
  $env:BUZZ_RELAY_URL="ws://localhost:3000"
  $env:BRIDGE_BASE_URL="http://localhost:8000"
  $env:BUZZ_PERSONAL_AGENT_ENABLED="1"
  python scripts/buzz_personal_agent.py

Stop:
  python scripts/buzz_personal_agent.py --stop
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = Path("audits")
STATE_FILE = AUDIT_DIR / "buzz_personal_agent_state.json"
STOP_FILE = AUDIT_DIR / "buzz_personal_agent.STOP"

# --- .env loading ------------------------------------------------------------
# Prefer a user-specific env so the agent can be a permanent, gamer-owned
# identity without colliding with the operator bot's scripts/.env.
try:
    from dotenv import load_dotenv
    _personal_env = Path(__file__).resolve().parent / "buzz_personal_agent.env"
    _fallback_env = Path(__file__).resolve().parent / ".env"
    if _personal_env.exists():
        load_dotenv(_personal_env, encoding="utf-8")
    elif _fallback_env.exists():
        load_dotenv(_fallback_env, encoding="utf-8")
except ImportError:
    pass

logging = None  # lazy setup


def _setup_logging() -> Any:
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return _logging


def _log() -> Any:
    global logging
    if logging is None:
        logging = _setup_logging()
    return logging


@dataclass
class AgentConfig:
    enabled: bool
    relay_url: str
    bridge_base_url: str
    bridge_api_key: str
    bot_name: str
    bot_about: str
    persona_pack_file: str
    private_key: str
    ioid_token: str
    device_id: str
    cli_path: Path
    interval_s: float
    dry_run: bool
    dm_ids: list[str]
    lobby_channel_id: str
    greet_on_start: bool
    greeting_text: str


def _load_persona_pack(path: Optional[str]) -> tuple[str, str, str]:
    """Load display name and about from a Buzz agent snapshot .agent.json.

    Returns (name, about, pack_file_name). Defaults are used if the pack is
    missing or unreadable so the agent can still start.
    """
    default_name = "QorTroller Concierge"
    default_about = "Gamer self-service agent for QorTroller. I only answer your own bridge queries."
    if path:
        pack_path = Path(path)
    else:
        pack_path = REPO_ROOT / "buzz-persona-qortroller-concierge" / "qortroller-concierge.agent.json"
    if not pack_path.exists():
        return default_name, default_about, ""
    try:
        data = json.loads(pack_path.read_text(encoding="utf-8"))
        profile = data.get("profile", {})
        name = profile.get("displayName") or default_name
        about = profile.get("about") or default_about
        return name, about, pack_path.name
    except Exception as e:
        _log().warning("failed to load persona pack %s: %s", pack_path, e)
        return default_name, default_about, ""


def _load_config() -> AgentConfig:
    pk = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not pk:
        sys.exit(
            "BUZZ_PRIVATE_KEY is required. This is the gamer key, not an operator key. "
            "Never commit it."
        )
    pack_path = os.environ.get("BUZZ_PERSONAL_AGENT_PERSONA_PACK", "")
    pack_name, pack_about, pack_file = _load_persona_pack(pack_path)
    return AgentConfig(
        enabled=os.environ.get("BUZZ_PERSONAL_AGENT_ENABLED", "0") == "1",
        relay_url=os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000").rstrip("/"),
        bridge_base_url=os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000").rstrip("/"),
        bridge_api_key=os.environ.get("BRIDGE_API_KEY", ""),
        bot_name=os.environ.get("BUZZ_PERSONAL_AGENT_NAME") or pack_name,
        bot_about=os.environ.get("BUZZ_PERSONAL_AGENT_ABOUT") or pack_about,
        persona_pack_file=pack_file,
        private_key=pk,
        ioid_token=os.environ.get("PERSONAL_AGENT_IOID_TOKEN", "498"),
        device_id=os.environ.get("PERSONAL_AGENT_DEVICE_ID", "581a836c"),
        cli_path=Path(
            os.environ.get(
                "BUZZ_CLI_PATH",
                str(REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe"),
            )
        ),
        interval_s=float(os.environ.get("BUZZ_PERSONAL_AGENT_INTERVAL_S", "10")),
        dry_run=os.environ.get("BUZZ_PERSONAL_AGENT_DRY_RUN", "0") == "1",
        dm_ids=[
            c.strip() for c in os.environ.get("BUZZ_PERSONAL_AGENT_DM_IDS", "").split(",")
            if c.strip()
        ],
        lobby_channel_id=os.environ.get("BUZZ_LOBBY_CHANNEL_ID", ""),
        greet_on_start=os.environ.get("BUZZ_PERSONAL_AGENT_GREET_ON_START", "0") == "1",
        greeting_text=os.environ.get(
            "BUZZ_PERSONAL_AGENT_GREETING",
            "Hello — I'm your QorTroller Concierge, running under my own agent key with the Grok 4.5 persona pack loaded. "
            "I can answer status, analytics, claim, create, and brainstorm. DM me any time.",
        ),
    )


def _my_npub(private_key: str) -> str:
    """Return bech32 npub for the given private key."""
    try:
        from nostr_sdk import Keys
        return Keys.parse(private_key).public_key().to_bech32()
    except Exception as e:
        _log().warning("could not derive npub: %s", e)
        return ""


def _to_http(url: str) -> str:
    if url.startswith("ws://"):
        return "http://" + url[len("ws://"):]
    if url.startswith("wss://"):
        return "https://" + url[len("wss://"):]
    return url


class BuzzCliClient:
    """Wrap the buzz CLI for DM polling and replies."""

    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self._env = os.environ.copy()
        self._env["BUZZ_PRIVATE_KEY"] = cfg.private_key
        self._env["BUZZ_RELAY_URL"] = _to_http(cfg.relay_url)

    def _run(self, *args: str, timeout: float = 30) -> Optional[dict | list]:
        cmd = [str(self.cfg.cli_path), *args]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._env,
                timeout=timeout,
            )
            if proc.returncode != 0:
                _log().error("buzz CLI failed: %s", proc.stderr.strip()[:500])
                return None
            text = proc.stdout.strip()
            if not text:
                return None
            return json.loads(text)
        except Exception as e:
            _log().error("buzz CLI error: %s", e)
            return None

    def my_pubkey(self) -> Optional[str]:
        data = self._run("users", "get")
        if data and isinstance(data, list) and data:
            return data[0].get("pubkey")
        return None

    def list_dms(self) -> list[dict]:
        data = self._run("dms", "list")
        if data and isinstance(data, list):
            return data
        return []

    def get_messages(self, dm_id: str, limit: int = 20) -> list[dict]:
        data = self._run("messages", "get", "--channel", dm_id, "--limit", str(limit))
        if data and isinstance(data, list):
            return data
        return []

    def send_message(self, dm_id: str, content: str, reply_to: Optional[str] = None) -> Optional[dict]:
        if self.cfg.dry_run:
            _log().info("[dry-run] would reply to %s: %s", dm_id, content[:120])
            return {"dry_run": True}
        args = ["messages", "send", "--channel", dm_id, "--content", content]
        if reply_to:
            args += ["--reply-to", reply_to]
        return self._run(*args)


def _send_startup_greeting(client: BuzzCliClient, cfg: AgentConfig) -> None:
    """Send a one-time greeting to each configured DM on startup.

    This is what makes the Concierge feel agentic — it reaches out first.
    """
    if not cfg.greet_on_start or not cfg.dm_ids:
        return
    for dm_id in cfg.dm_ids:
        _log().info("sending startup greeting to DM %s", dm_id)
        client.send_message(dm_id, cfg.greeting_text)


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _bridge_get(path: str, cfg: AgentConfig, timeout: float = 10) -> Optional[dict]:
    try:
        import requests
        headers = {}
        if cfg.bridge_api_key:
            headers["x-api-key"] = cfg.bridge_api_key
        resp = requests.get(f"{cfg.bridge_base_url}{path}", headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        _log().debug("bridge GET %s failed: %s", path, e)
        return None


def _fmt_status(data: Optional[dict]) -> str:
    if not data:
        return "Bridge is unreachable right now. Try again when the bridge is running."
    lines = ["QorTroller self-status:"]
    for k in ["device_id", "ioid_token", "rig_state", "bridge_health", "oracle", "eligible"]:
        v = data.get(k)
        if v is not None:
            lines.append(f"- {k}: {v}")
    if data.get("session_id"):
        lines.append(f"- session_id: {data.get('session_id')}")
    if data.get("verdict"):
        lines.append(f"- verdict: {data.get('verdict')}")
    if data.get("is_fully_eligible") is not None:
        lines.append(f"- is_fully_eligible: {data.get('is_fully_eligible')}")
    return "\n".join(lines)


def _fmt_self_analytics(data: Optional[dict]) -> str:
    if not data:
        return "Self-analytics are not available right now."
    return f"Self-analytics digest:\n```json\n{json.dumps(data, indent=2)}\n```"


def _handle_help(cfg: AgentConfig) -> str:
    pack_note = ""
    if cfg.persona_pack_file:
        pack_note = (
            f"\nThis relay runs from the Buzz persona pack `{cfg.persona_pack_file}`. "
            "You can also import `buzz-persona-qortroller-concierge/qortroller-concierge.agent.json` "
            "as a managed agent in Buzz Desktop.\n"
        )
    return (
        "Hey — here's what I can do for you:\n"
        "- `status` — check your current session / bridge status\n"
        "- `analytics` — your own verified data summary\n"
        "- `claim <token> <device>` — post your ioID claim to #lobby\n"
        "- `create <agent|channel|project|workflow|template> <name> [...]` — create a new Buzz artifact\n"
        "- `brainstorm <topic>` — seed a brainstorm in the community\n"
        "- `help` — bring this list back\n\n"
        "If `BUZZ_LOBBY_CHANNEL_ID` is set, `claim` actually posts.\n"
        "`create` and `brainstorm` run `scripts/buzz_agent_factory.py` with your key.\n"
        "I don't run @EA operator commands and I never ask for a private key."
        + pack_note
    )


def _handle_claim(cfg: AgentConfig, args: list[str]) -> str:
    token = args[0] if len(args) > 0 else cfg.ioid_token
    device = args[1] if len(args) > 1 else cfg.device_id

    if not cfg.lobby_channel_id:
        return (
            "I need a #lobby channel to post your claim. Set BUZZ_LOBBY_CHANNEL_ID, then:\n\n"
            f"```\n"
            f"python scripts/buzz_ioid_claim.py --ioid-token {token} --device-id {device} --lobby-channel <channel-uuid>\n"
            f"```"
        )

    if cfg.dry_run:
        return (
            f"[dry-run] I would post an ioID claim to #lobby for token {token}, device {device}."
        )

    # Run the claim script as the gamer. This agent is assumed to be running with
    # the gamer's own BUZZ_PRIVATE_KEY; the script signs with that key.
    try:
        cmd = [
            sys.executable,
            "scripts/buzz_ioid_claim.py",
            "--ioid-token", str(token),
            "--device-id", str(device),
            "--lobby-channel", cfg.lobby_channel_id,
        ]
        env = os.environ.copy()
        env["BUZZ_LOBBY_CHANNEL_ID"] = cfg.lobby_channel_id
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
            env=env,
            shell=False,
        )
        if result.returncode == 0:
            return (
                f"ioID claim posted to #lobby!\n"
                f"- token: {token}\n"
                f"- device: {device}\n"
                f"- channel: {cfg.lobby_channel_id[:8]}...\n\n"
                f"The proof still lives in QorTroller; this is a self-asserted pointer."
            )
        return (
            f"ioID claim failed:\n```\n{result.stderr.strip()[:500]}\n```\n\n"
            f"You can run it manually:\n"
            f"```\npython scripts/buzz_ioid_claim.py --ioid-token {token} --device-id {device} --lobby-channel {cfg.lobby_channel_id}\n```"
        )
    except Exception as e:
        return f"ioID claim error: {e}. Run the script manually as shown in `help`."


def _parse_command(text: str) -> tuple[str, list[str]]:
    t = text.strip().lower()
    parts = t.split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _handle_factory(cfg: AgentConfig, cmd: str, args: list[str]) -> str:
    """Run buzz_agent_factory.py to create an agent, channel, project, etc."""
    if not args:
        return (
            "Usage: `create <agent|channel|project|workflow|template> <name> [args...]`\n"
            "Examples:\n"
            "- `create agent AlphaBot watcher`\n"
            "- `create channel brainstorm Agent brainstorming room`\n"
            "- `create project SAP-Portal Make SAP jobs visible`\n"
            "- `create workflow Claim-Flow define,execute,verify`\n"
            "- `create template Onboarding-Template`\n"
            "- `brainstorm What if agents self-onboard via ioID?`"
        )

    artifact = args[0]
    name = args[1] if len(args) > 1 else ""
    rest = args[2:]
    if not name:
        return f"I need a name for the {artifact}."

    if artifact not in ("agent", "channel", "project", "workflow", "template"):
        return f"I can create agent/channel/project/workflow/template, not '{artifact}'."

    if cfg.dry_run:
        return f"[dry-run] I would create a {artifact} named '{name}'."

    factory_cmd = [sys.executable, "scripts/buzz_agent_factory.py"]
    if artifact == "agent":
        role = rest[0] if rest else "concierge"
        factory_cmd += ["create-agent", "--name", name, "--role", role]
    elif artifact == "channel":
        desc = " ".join(rest) if rest else f"{name} channel"
        factory_cmd += ["create-channel", "--name", name, "--description", desc]
    elif artifact == "project":
        goal = " ".join(rest) if rest else "expand QorTroller"
        factory_cmd += ["create-project", "--name", name, "--goal", goal]
    elif artifact == "workflow":
        steps = ",".join(rest) if rest else "define,execute,verify"
        factory_cmd += ["create-workflow", "--name", name, "--steps", steps]
    elif artifact == "template":
        desc = " ".join(rest) if rest else f"{name} template"
        factory_cmd += ["create-template", "--name", name, "--description", desc]

    env = os.environ.copy()
    env["BUZZ_PRIVATE_KEY"] = cfg.private_key
    env["BUZZ_RELAY_URL"] = cfg.relay_url
    if cfg.lobby_channel_id:
        env["BUZZ_LOBBY_CHANNEL_ID"] = cfg.lobby_channel_id

    try:
        result = subprocess.run(
            factory_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
            env=env,
            shell=False,
        )
        if result.returncode == 0:
            return f"{artifact} '{name}' created:\n```\n{result.stdout.strip()[:1500]}\n```"
        return f"{artifact} creation failed:\n```\n{result.stderr.strip()[:1000]}\n```"
    except Exception as e:
        return f"factory error: {e}"


def _handle_brainstorm(cfg: AgentConfig, args: list[str]) -> str:
    if not args:
        return "Usage: `brainstorm <topic>`"
    topic = " ".join(args)
    channel_id = os.environ.get("BUZZ_BRAINSTORM_CHANNEL_ID", "")
    if not channel_id:
        return "I need `BUZZ_BRAINSTORM_CHANNEL_ID` set to post a brainstorm."
    if cfg.dry_run:
        return f"[dry-run] I would brainstorm: {topic}"
    factory_cmd = [
        sys.executable, "scripts/buzz_agent_factory.py",
        "brainstorm", "--topic", topic, "--channel", channel_id,
    ]
    env = os.environ.copy()
    env["BUZZ_PRIVATE_KEY"] = cfg.private_key
    env["BUZZ_RELAY_URL"] = cfg.relay_url
    try:
        result = subprocess.run(
            factory_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
            env=env,
            shell=False,
        )
        if result.returncode == 0:
            return f"Brainstorm seeded: {topic}"
        return f"Brainstorm failed:\n```\n{result.stderr.strip()[:1000]}\n```"
    except Exception as e:
        return f"brainstorm error: {e}"


def _handle_chat(text: str, cfg: AgentConfig) -> Optional[str]:
    """Friendly natural-language responses for small talk and QorTroller explainers.

    Returns None if the message should fall through to the unknown fallback.
    """
    lowered = text.lower()

    # Greetings
    if any(lowered.startswith(w) for w in ("hello", "hi", "hey", "yo", "sup")):
        return (
            f"Hey — I'm {cfg.bot_name}. Ask me about `status`, `analytics`, "
            "`claim`, `create`, or `brainstorm`, or just ask what QorTroller is."
        )

    # Farewells
    if any(w in lowered for w in ("bye", "goodbye", "see ya", "later")):
        return "Catch you later."

    # Thanks
    if any(w in lowered for w in ("thank", "thx", "thanks")):
        return "You're welcome."

    # How the agent feels about QorTroller
    if any(p in lowered for p in (
        "how do you feel",
        "what do you think",
        "what is your opinion",
        "do you like qortroller",
        "do you love qortroller",
    )):
        return (
            "I think QorTroller is the real deal. Gamers and their controllers as the "
            "cryptographic agency-holders of their own data, with cheating made "
            "cryptographically inexpressible — that's the V.A.P.I. thesis in action. "
            "What part do you want to dig into?"
        )

    # QorTroller explainer
    if any(p in lowered for p in (
        "what is qortroller",
        "what's qortroller",
        "tell me about qortroller",
        "explain qortroller",
    )):
        return (
            "QorTroller is the reference V.A.P.I. implementation — a DePIN protocol where "
            "the gamer and their controller are also the cryptographic owners of the data "
            "they generate. It runs on IoTeX, uses the certified Sony DualShock Edge, and "
            "produces 228-byte Proof of Autonomous Cognition records per cognition cycle. "
            "The big idea: honest gamers reach `isFullyEligible()` on-chain without needing "
            "to be punished for cheating, because cheating becomes cryptographically "
            "inexpressible."
        )

    # ioID explainer
    if any(p in lowered for p in (
        "what is ioid",
        "what's ioid",
        "explain ioid",
        "tell me about ioid",
    )):
        return (
            "ioID is the IoTeX decentralized identity layer. In QorTroller, your "
            "controller (the certified Edge, device id `581a836c`) is bound to an ioID "
            "token and an ERC-6551 token-bound account, so the device is owned by your "
            "DID, not the other way around. It lets the gamer prove device provenance "
            "without revealing raw biometrics."
        )

    # PoAC explainer
    if any(p in lowered for p in (
        "what is poac",
        "what's poac",
        "proof of autonomous cognition",
    )):
        return (
            "PoAC — Proof of Autonomous Cognition — is the 228-byte attestation record "
            "QorTroller produces each cognition cycle. It binds controller input, session "
            "context, and a cryptographic commitment so the gamer can prove their "
            "gameplay is genuine without leaking the raw HID/IMU substrate."
        )

    # PoEP explainer
    if any(p in lowered for p in (
        "what is poep",
        "what's poep",
        "proof of embodied play",
    )):
        return (
            "PoEP — Proof of Embodied Play — is the controller-side liveness check. It "
            "proves a real human is at the controls using reflex/IMU signals from the "
            "DualShock Edge, not just a script replaying inputs."
        )

    return None


def _handle_unknown(cfg: AgentConfig) -> str:
    return (
        "I didn't catch that as a command I can run right now. "
        "I do `status`, `analytics`, `claim`, `create`, and `brainstorm`. "
        "You can also ask me about QorTroller, ioID, PoAC, or PoEP. "
        "For operator stuff like @EA, hit up #rig-ops."
    )


def _process_message(message: dict, cfg: AgentConfig) -> str:
    text = message.get("content", "").strip()
    if not text:
        return ""

    cmd, args = _parse_command(text)

    if cmd in ("status", "st", "state"):
        data = _bridge_get("/player/session-status", cfg)
        return _fmt_status(data)

    if cmd in ("analytics", "stats", "me"):
        data = _bridge_get("/player/self-analytics", cfg)
        return _fmt_self_analytics(data)

    if cmd in ("claim", "ioid"):
        return _handle_claim(cfg, args)

    if cmd in ("create", "mint"):
        return _handle_factory(cfg, cmd, args)

    if cmd in ("brainstorm", "bs"):
        return _handle_brainstorm(cfg, args)

    if cmd in ("help", "?", "h"):
        return _handle_help(cfg)

    # Reject anything that looks like an operator command.
    if text.startswith("@ea") or text.startswith("devin @ea") or text.startswith("run "):
        return (
            "I can only answer gamer-self questions. "
            "For operator commands like @EA, use #rig-ops with an operator key."
        )

    chat_reply = _handle_chat(text, cfg)
    if chat_reply:
        return chat_reply

    return _handle_unknown(cfg)


def _is_from_self(message: dict, my_pubkey: str) -> bool:
    return message.get("pubkey") == my_pubkey


def _should_process(message: dict, my_pubkey: str, last_ts: int) -> bool:
    if _is_from_self(message, my_pubkey):
        return False
    ts = message.get("created_at", 0)
    return ts > last_ts


def _run_once(client: BuzzCliClient, cfg: AgentConfig, state: dict) -> dict:
    my_pk = client.my_pubkey()
    if not my_pk:
        _log().warning("could not get my own pubkey from buzz CLI")
        return state

    dms = [
        {"dm_id": dm_id} for dm_id in cfg.dm_ids
    ] or client.list_dms()
    for dm in dms:
        dm_id = dm.get("dm_id")
        if not dm_id:
            continue

        last_ts = state.get(dm_id, 0)
        messages = client.get_messages(dm_id, limit=20)
        if not messages:
            continue

        # Process the newest message that is newer than last_ts and not from self.
        for message in reversed(messages):
            ts = message.get("created_at", 0)
            if not _should_process(message, my_pk, last_ts):
                continue

            reply = _process_message(message, cfg)
            if reply:
                event_id = message.get("id")
                client.send_message(dm_id, reply, reply_to=event_id)
                _log().info("replied to DM %s: %s", dm_id, reply[:80].replace("\n", " "))

            state[dm_id] = ts
            break

    return state


def _touch_stop() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.touch()
    print("Stop signal written. The agent will exit on its next loop.")


def _is_stopped() -> bool:
    return STOP_FILE.exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true", help="Write stop signal and exit")
    parser.add_argument("--dry-run", action="store_true", help="Read DMs but do not send replies")
    args = parser.parse_args()

    if args.stop:
        _touch_stop()
        return 0

    cfg = _load_config()
    if not cfg.enabled:
        _log().error(
            "BUZZ_PERSONAL_AGENT_ENABLED is not 1. Set it and your BUZZ_PRIVATE_KEY to start."
        )
        return 1

    if args.dry_run:
        cfg.dry_run = True

    if _is_stopped():
        STOP_FILE.unlink(missing_ok=True)

    client = BuzzCliClient(cfg)
    my_pk = client.my_pubkey()
    if not my_pk:
        _log().error("buzz CLI could not derive your pubkey. Check BUZZ_PRIVATE_KEY and BUZZ_RELAY_URL.")
        return 1

    my_npub = _my_npub(cfg.private_key)
    _log().info(
        "[%s] starting as npub %s (relay %s, dry_run=%s)",
        cfg.bot_name, my_npub or my_pk, cfg.relay_url, cfg.dry_run
    )
    _log().info("DM me at %s to trigger status/analytics/claim/help", my_npub or my_pk)
    if cfg.persona_pack_file:
        _log().info("loaded persona pack: %s", cfg.persona_pack_file)

    _send_startup_greeting(client, cfg)

    try:
        while True:
            if _is_stopped():
                _log().info("stop signal found; exiting")
                break

            state = _load_state()
            new_state = _run_once(client, cfg, state)
            _save_state(new_state)
            time.sleep(cfg.interval_s)
    except KeyboardInterrupt:
        _log().info("interrupted; exiting")

    return 0


if __name__ == "__main__":
    sys.exit(main())
