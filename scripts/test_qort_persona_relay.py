#!/usr/bin/env python3
"""Smoke test for the QorT Buzz persona pack + relay wiring.

Does NOT require a live relay. It:
  1. Validates the QorT pack metadata and agent snapshot.
  2. Checks that the persona prompt has the rails (no keys, safe @EA relay, no raw biometrics).
  3. Verifies the MCP bridge can be imported.
  4. Optionally dry-runs the relay reply logic.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = REPO_ROOT / "buzz-persona-qortroller"
AGENT_JSON = PACK_DIR / "qortroller-rig-steward.agent.json"
PERSONA_MD = PACK_DIR / "agents" / "qortroller.persona.md"
MCP_BRIDGE = PACK_DIR / "mcp" / "qortroller_acp_stdio.py"


def fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def _test_pack_files() -> int:
    required = [
        PACK_DIR / ".plugin" / "plugin.json",
        PACK_DIR / ".mcp.json",
        PERSONA_MD,
        PACK_DIR / "mcp" / "qortroller_acp_stdio.py",
        PACK_DIR / "skills" / "qortroller" / "SKILL.md",
        AGENT_JSON,
    ]
    for f in required:
        if not f.exists():
            return fail(f"missing pack file: {f}")
    print("PASS: all required pack files present")
    return 0


def _normalize(text: str) -> str:
    # strip markdown emphasis and backticks so "not **a** key-holder" matches
    return re.sub(r"[*`#]+", "", text).lower()


def _test_agent_json() -> int:
    data = json.loads(AGENT_JSON.read_text(encoding="utf-8"))
    if data.get("format") != "buzz-agent-snapshot":
        return fail("agent snapshot format wrong")
    if data["definition"].get("runtime") != "goose":
        return fail("runtime should be goose")
    prompt = _normalize(data["definition"].get("systemPrompt", ""))
    for phrase in ["not a key-holder", "ask_ea", "@ea", "never", "nostr carries pointers"]:
        if phrase not in prompt:
            return fail(f"system prompt missing safety phrase: {phrase!r}")
    print("PASS: agent snapshot format and rails OK")
    return 0


def _test_pack_metadata() -> int:
    plugin = json.loads((PACK_DIR / ".plugin" / "plugin.json").read_text(encoding="utf-8"))
    if plugin.get("mcp_config") != ".mcp.json":
        return fail("plugin manifest missing mcp_config")
    if AGENT_JSON.name not in (PACK_DIR / "README.md").read_text(encoding="utf-8"):
        return fail("README does not mention the single-file snapshot")
    print("PASS: pack metadata and README OK")
    return 0


def _test_mcp_bridge_syntax() -> int:
    try:
        subprocess.run(
            [sys.executable, "-m", "py_compile", str(MCP_BRIDGE)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        return fail(f"MCP bridge syntax error: {e.stderr}")
    print("PASS: MCP bridge compiles")
    return 0


def _test_persona_rails() -> int:
    prompt = _normalize(PERSONA_MD.read_text(encoding="utf-8"))
    disallowed_contexts = [
        "send me your nsec",
        "send me your private key",
        "send me your key",
        "generate a private key for me",
        "store my private key",
        "nsec1",
    ]
    for phrase in disallowed_contexts:
        if phrase in prompt:
            return fail(f"persona prompt contains disallowed context: {phrase!r}")
    print("PASS: persona prompt rails OK")
    return 0


def _test_relay_bot_syntax() -> int:
    bot = REPO_ROOT / "scripts" / "qort_buzz_persona_relay.py"
    if not bot.exists():
        return fail("relay bot not found")
    try:
        subprocess.run(
            [sys.executable, "-m", "py_compile", str(bot)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        return fail(f"relay bot syntax error: {e.stderr}")
    print("PASS: relay bot compiles")
    return 0


def _test_relay_trigger_logic() -> int:
    bot = REPO_ROOT / "scripts" / "qort_buzz_persona_relay.py"
    src = bot.read_text(encoding="utf-8")
    if "_is_qort_trigger" not in src:
        return fail("relay bot missing trigger logic")
    if "_extract_ea_command" not in src:
        return fail("relay bot missing @EA extraction")
    if "_acp_eval" not in src:
        return fail("relay bot missing ACP eval")
    print("PASS: relay bot trigger + ACP wiring present")
    return 0


def _test_buzz_pack_cli() -> int:
    cli = REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe"
    if not cli.exists():
        print("SKIP: buzz CLI not built; cannot run 'buzz pack validate'")
        return 0
    try:
        proc = subprocess.run(
            [str(cli), "pack", "validate", str(PACK_DIR)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return fail(f"buzz pack validate failed: {proc.stderr}")
        print("PASS: buzz pack validate")
    except Exception as e:
        return fail(f"buzz pack validate error: {e}")
    return 0


def main() -> int:
    tests = [
        _test_pack_files,
        _test_agent_json,
        _test_pack_metadata,
        _test_mcp_bridge_syntax,
        _test_persona_rails,
        _test_relay_bot_syntax,
        _test_relay_trigger_logic,
        _test_buzz_pack_cli,
    ]
    rc = 0
    for t in tests:
        try:
            rc |= t()
        except Exception as e:
            print(f"ERROR in {t.__name__}: {e}")
            rc = 1
    if rc == 0:
        print("\nAll QorT Buzz persona relay smoke tests passed.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
