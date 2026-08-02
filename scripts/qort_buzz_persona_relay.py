#!/usr/bin/env python3
"""QorT Buzz Persona Relay — live-relay bot for the QorT pack.

This is a *test harness* that runs the QorT persona outside of Buzz desktop.
It polls channels and DMs, triggers on @QorT or QorTroller keywords, and relays
safe `@EA` commands through the QorTroller ACP gateway. It is NOT a replacement
for the Buzz agent runtime; it is a way to smoke-test the persona on a live
Buzz relay before/after importing the pack.

Usage:
  $env:BUZZ_PRIVATE_KEY="nsec1..."            # gamer or operator key
  $env:BUZZ_RELAY_URL="ws://localhost:3000"
  $env:ACP_OPERATOR_PUBKEYS="<operator-hex>"  # for @EA commands
  $env:QORTROLLER_REPO_ROOT="C:\...\vapi-pebble-prototype"
  python scripts/qort_buzz_persona_relay.py

Stop:
  python scripts/qort_buzz_persona_relay.py --stop
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
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = Path("audits")
STATE_FILE = AUDIT_DIR / "qort_buzz_persona_relay_state.json"
STOP_FILE = AUDIT_DIR / "qort_buzz_persona_relay.STOP"
QORT_PACK = REPO_ROOT / "buzz-persona-qortroller"

# --- .env loading ------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = REPO_ROOT / "scripts" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, encoding="utf-8")
except ImportError:
    pass


def _to_http(url: str) -> str:
    if url.startswith("ws://"):
        return "http://" + url[len("ws://"):]
    if url.startswith("wss://"):
        return "https://" + url[len("wss://"):]
    return url

logging = None


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
class BotConfig:
    enabled: bool
    relay_url: str
    cli_path: Path
    private_key: str
    bot_name: str
    channels: list[str]
    dms: bool
    poll_interval: float
    dry_run: bool
    operator_pubkey: str
    acp_gateway_timeout: float


def _load_config() -> BotConfig:
    pk = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not pk:
        sys.exit("BUZZ_PRIVATE_KEY is required. Never commit it.")
    channels = [c.strip() for c in os.environ.get("BUZZ_QORT_CHANNEL_IDS", "#rig-ops").split(",") if c.strip()]
    # The CLI uses channel UUIDs. If the user puts names like #rig-ops, we will fail
    # gracefully and ask for UUIDs. This is a relay smoke-test, not a production bot.
    return BotConfig(
        enabled=os.environ.get("QORT_BUZZ_PERSONA_RELAY_ENABLED", "0") == "1",
        relay_url=os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000").rstrip("/"),
        cli_path=Path(
            os.environ.get(
                "BUZZ_CLI_PATH",
                str(REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe"),
            )
        ),
        private_key=pk,
        bot_name=os.environ.get("QORT_BUZZ_PERSONA_NAME", "QorT"),
        channels=channels,
        dms=os.environ.get("QORT_BUZZ_PERSONA_DMS", "1") == "1",
        poll_interval=float(os.environ.get("QORT_BUZZ_PERSONA_INTERVAL_S", "10")),
        dry_run=os.environ.get("QORT_BUZZ_PERSONA_DRY_RUN", "0") == "1",
        operator_pubkey=os.environ.get("ACP_OPERATOR_PUBKEYS", ""),
        acp_gateway_timeout=float(os.environ.get("QORT_ACP_GATEWAY_TIMEOUT", "30")),
    )


class BuzzCliClient:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self._env = os.environ.copy()
        self._env["BUZZ_PRIVATE_KEY"] = cfg.private_key
        self._env["BUZZ_RELAY_URL"] = _to_http(cfg.relay_url)
        self._env["BUZZ_HELPER_PATH"] = os.environ.get(
            "BUZZ_HELPER_PATH",
            str(REPO_ROOT / "buzz" / "target" / "debug" / "qortroller-buzz.exe"),
        )

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

    def get_messages(self, channel_id: str, limit: int = 20, since: int = 0) -> list[dict]:
        args = ["messages", "get", "--channel", channel_id, "--limit", str(limit)]
        if since:
            args.extend(["--since", str(since)])
        data = self._run(*args)
        if data and isinstance(data, list):
            return data
        return []

    def send_message(self, channel_id: str, content: str, reply_to: Optional[str] = None) -> Optional[dict]:
        if self.cfg.dry_run:
            _log().info("[dry-run] would send to %s: %s", channel_id, content[:120])
            return {"dry_run": True}
        args = ["messages", "send", "--channel", channel_id, "--content", content]
        if reply_to:
            args.extend(["--reply-to", reply_to])
        return self._run(*args)


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


def _is_qort_trigger(text: str) -> bool:
    t = text.lower()
    triggers = ["@qort", "qortroller", "qort", "rig", "session", "ioID", "PoAC", "VAPI", "invariant"]
    return any(tr in t for tr in triggers)


def _extract_ea_command(text: str) -> Optional[str]:
    m = re.search(r"@EA\s+(.+?)(?:$|[.!?])", text, re.IGNORECASE)
    if m:
        return f"@EA {m.group(1).strip()}"
    return None


def _acp_eval(cmd: str, pubkey: str, timeout: float) -> str:
    """Run the QorTroller ACP gateway in one-shot --eval mode."""
    if not pubkey:
        return "rejected: ACP_OPERATOR_PUBKEYS is not set; I cannot relay @EA commands."
    env = os.environ.copy()
    env["ACP_OPERATOR_PUBKEYS"] = pubkey
    try:
        proc = subprocess.run(
            [sys.executable, "scripts/qortroller_acp_gateway.py", "--eval", cmd, pubkey],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
            timeout=timeout,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0 and not out:
            return f"rejected: ACP gateway failed ({err or proc.returncode})"
        return out or err or "(no reply)"
    except Exception as e:
        return f"rejected: ACP gateway error: {e}"


def _extract_factory_command(text: str) -> Optional[list[str]]:
    """Parse '@QorT create ...' and '@QorT brainstorm ...' commands."""
    t = text.strip()
    m = re.match(r"@?qort\s+(.+)", t, re.IGNORECASE)
    if not m:
        return None
    body = m.group(1).strip()
    parts = body.split()
    if len(parts) < 2:
        return None
    return [p.lower() for p in parts]


def _my_hex(private_key: str) -> str:
    try:
        from nostr_sdk import Keys
        return Keys.parse(private_key).public_key().to_hex()
    except Exception:
        return ""


def _is_authorized_factory_user(pubkey: str, cfg: BotConfig) -> bool:
    """Allow factory commands from the bot itself or configured operators."""
    if not pubkey:
        return False
    my_hex = _my_hex(cfg.private_key)
    if pubkey == my_hex:
        return True
    allowed = {p.strip() for p in (cfg.operator_pubkey or "").split(",") if p.strip()}
    return pubkey in allowed


def _factory_eval(cmd: list[str], cfg: BotConfig) -> str:
    """Run buzz_agent_factory.py as a subprocess."""
    if not cmd:
        return "rejected: empty factory command"
    action = cmd[0]
    if action not in ("create", "brainstorm"):
        return "rejected: I only understand 'create' and 'brainstorm'"

    env = os.environ.copy()
    env["BUZZ_PRIVATE_KEY"] = cfg.private_key
    env["BUZZ_RELAY_URL"] = _to_http(cfg.relay_url)
    env["BUZZ_CLI_PATH"] = str(cfg.cli_path)
    env["BUZZ_HELPER_PATH"] = os.environ.get(
        "BUZZ_HELPER_PATH",
        str(REPO_ROOT / "buzz" / "target" / "debug" / "qortroller-buzz.exe"),
    )

    factory_args = [sys.executable, str(REPO_ROOT / "scripts" / "buzz_agent_factory.py")]

    if action == "brainstorm":
        if len(cmd) < 2:
            return "rejected: brainstorm needs a topic"
        topic = " ".join(cmd[1:])
        factory_args += ["brainstorm", "--topic", topic]
    elif action == "create":
        if len(cmd) < 3:
            return "rejected: create needs a type and name"
        artifact = cmd[1]
        name = cmd[2]
        rest = cmd[3:]
        if artifact == "agent":
            role = rest[0] if rest else "concierge"
            factory_args += ["create-agent", "--name", name, "--role", role]
        elif artifact == "channel":
            desc = " ".join(rest) if rest else f"{name} channel"
            factory_args += ["create-channel", "--name", name, "--description", desc]
        elif artifact == "project":
            goal = " ".join(rest) if rest else "expand QorTroller"
            factory_args += ["create-project", "--name", name, "--goal", goal]
        elif artifact == "workflow":
            steps = ",".join(rest) if rest else "define,execute,verify"
            factory_args += ["create-workflow", "--name", name, "--steps", steps]
        elif artifact == "template":
            desc = " ".join(rest) if rest else f"{name} template"
            factory_args += ["create-template", "--name", name, "--description", desc]
        else:
            return f"rejected: I can create agent/channel/project/workflow/template, not '{artifact}'"
    else:
        return "rejected: unknown factory action"

    try:
        proc = subprocess.run(
            factory_args,
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
            timeout=120,
        )
        if proc.returncode != 0:
            return f"rejected: factory failed ({proc.stderr.strip()[:500]})"
        return f"created:\n```\n{proc.stdout.strip()[:1500]}\n```"
    except Exception as e:
        return f"rejected: factory error: {e}"


def _qort_reply(text: str, cfg: BotConfig, author_pubkey: str = "") -> Optional[str]:
    if not _is_qort_trigger(text):
        return None

    factory_cmd = _extract_factory_command(text)
    if factory_cmd:
        if not _is_authorized_factory_user(author_pubkey, cfg):
            return "rejected: you are not authorized to mint channels/agents"
        return _factory_eval(factory_cmd, cfg)

    ea_cmd = _extract_ea_command(text)
    if ea_cmd:
        digest = _acp_eval(ea_cmd, cfg.operator_pubkey, cfg.acp_gateway_timeout)
        return f"QorT relay: `{ea_cmd}`\n\n{digest[:1500]}"

    return (
        "I am QorT, the QorTroller Rig Steward. I can:\n"
        "- create agents, channels, projects, workflows, templates\n"
        "- brainstorm new QorTroller ideas\n"
        "- relay safe `@EA` commands (e.g. `@EA status`)\n\n"
        "I do not hold keys, start live capture, or touch raw biometrics."
    )


def _process_messages(client: BuzzCliClient, cfg: BotConfig, channel_id: str, state: dict) -> dict:
    my_pk = client.my_pubkey()
    if not my_pk:
        _log().warning("could not get own pubkey")
        return state

    last_ts = state.get(channel_id, 0)
    messages = client.get_messages(channel_id, limit=20, since=last_ts)
    if not messages:
        return state

    for message in messages:
        ts = message.get("created_at", 0)
        if ts <= last_ts:
            continue
        if message.get("pubkey") == my_pk:
            state[channel_id] = ts
            continue

        text = message.get("content", "")
        author = message.get("pubkey", "")
        reply = _qort_reply(text, cfg, author)
        if reply:
            event_id = message.get("id")
            client.send_message(channel_id, reply, reply_to=event_id)
            _log().info("replied in %s to %s", channel_id, text[:60])

        state[channel_id] = ts

    return state


def _process_dms(client: BuzzCliClient, cfg: BotConfig, state: dict) -> dict:
    my_pk = client.my_pubkey()
    if not my_pk:
        return state

    dms = client.list_dms()
    for dm in dms:
        dm_id = dm.get("dm_id")
        if not dm_id:
            continue
        state = _process_messages(client, cfg, dm_id, state)
    return state


def _touch_stop() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.touch()
    print("Stop signal written. The relay bot will exit on its next loop.")


def _is_stopped() -> bool:
    return STOP_FILE.exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true", help="Write stop signal and exit")
    parser.add_argument("--dry-run", action="store_true", help="Read messages but do not send")
    args = parser.parse_args()

    if args.stop:
        _touch_stop()
        return 0

    cfg = _load_config()
    if not cfg.enabled:
        _log().error(
            "QORT_BUZZ_PERSONA_RELAY_ENABLED is not 1. Set it, BUZZ_PRIVATE_KEY, and ACP_OPERATOR_PUBKEYS to start."
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

    _log().info("[QorT relay] starting as %s... dry_run=%s", my_pk, cfg.dry_run)
    _log().info("[QorT relay] watching channels: %s", cfg.channels)

    try:
        while True:
            if _is_stopped():
                _log().info("stop signal found; exiting")
                break

            state = _load_state()
            for channel_id in cfg.channels:
                state = _process_messages(client, cfg, channel_id, state)

            if cfg.dms:
                state = _process_dms(client, cfg, state)

            _save_state(state)
            time.sleep(cfg.poll_interval)
    except KeyboardInterrupt:
        _log().info("interrupted; exiting")

    return 0


if __name__ == "__main__":
    sys.exit(main())
