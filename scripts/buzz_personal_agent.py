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
    private_key: str
    ioid_token: str
    device_id: str
    cli_path: Path
    interval_s: float
    dry_run: bool
    dm_ids: list[str]
    lobby_channel_id: str


def _load_config() -> AgentConfig:
    pk = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not pk:
        sys.exit(
            "BUZZ_PRIVATE_KEY is required. This is the gamer key, not an operator key. "
            "Never commit it."
        )
    return AgentConfig(
        enabled=os.environ.get("BUZZ_PERSONAL_AGENT_ENABLED", "0") == "1",
        relay_url=os.environ.get("BUZZ_RELAY_URL", "ws://localhost:3000").rstrip("/"),
        bridge_base_url=os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000").rstrip("/"),
        bridge_api_key=os.environ.get("BRIDGE_API_KEY", ""),
        bot_name=os.environ.get("BUZZ_PERSONAL_AGENT_NAME", "QorTroller Concierge"),
        bot_about=os.environ.get(
            "BUZZ_PERSONAL_AGENT_ABOUT",
            "Gamer self-service agent for QorTroller. I only answer your own bridge queries.",
        ),
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
    )


class BuzzCliClient:
    """Wrap the buzz CLI for DM polling and replies."""

    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self._env = os.environ.copy()
        self._env["BUZZ_PRIVATE_KEY"] = cfg.private_key
        self._env["BUZZ_RELAY_URL"] = cfg.relay_url

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


def _handle_help() -> str:
    return (
        "I can answer these gamer-self questions:\n"
        "- `status` — your current session / bridge status\n"
        "- `analytics` — your own verified data summary\n"
        "- `claim <token> <device>` — post your ioID claim to #lobby\n"
        "- `help` — this message\n\n"
        "If `BUZZ_LOBBY_CHANNEL_ID` is set, `claim` actually posts.\n"
        "I do not run @EA commands and I never ask for a private key."
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

    if cmd in ("help", "?", "h"):
        return _handle_help()

    # Reject anything that looks like an operator command.
    if text.startswith("@ea") or text.startswith("devin @ea") or text.startswith("run "):
        return (
            "I can only answer gamer-self questions. "
            "For operator commands like @EA, use #rig-ops with an operator key."
        )

    return (
        "I didn't understand that. Send `help` for what I can do. "
        "I only handle gamer-self bridge queries."
    )


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

    _log().info(
        "[QorTroller Concierge] starting as pubkey %s... (dry_run=%s)", my_pk, cfg.dry_run
    )

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
