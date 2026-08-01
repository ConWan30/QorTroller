#!/usr/bin/env python3
"""stdio MCP bridge for the QorTroller ACP.

Exposes one tool: ask_ea({ content, pubkey }) -> calls
qortroller_acp_gateway.handle_message and returns the digest as MCP text.

Reads JSON-RPC 2.0 messages from stdin, one per line.
Locates the QorTroller repo by, in order:
  1. QORTROLLER_REPO_ROOT environment variable
  2. Searching ../scripts, ../../scripts, and ../../../scripts for
     qortroller_acp_gateway.py

No shell. No keys read. Operator allow-list is enforced by the gateway.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _find_qortroller_repo() -> Path:
    """Locate the QorTroller repository root."""
    from_env = os.environ.get("QORTROLLER_REPO_ROOT")
    if from_env:
        p = Path(from_env).resolve()
        if (p / "scripts" / "qortroller_acp_gateway.py").is_file():
            return p
        raise RuntimeError(f"QORTROLLER_REPO_ROOT={from_env} does not contain scripts/qortroller_acp_gateway.py")

    script_dir = Path(__file__).resolve().parent
    for rel in ("..", "../..", "../../.."):
        candidate = (script_dir / rel).resolve()
        if (candidate / "scripts" / "qortroller_acp_gateway.py").is_file():
            return candidate

    raise RuntimeError(
        "Could not find QorTroller repository. Set QORTROLLER_REPO_ROOT "
        "or place this pack inside the QorTroller repository."
    )


def _load_gateway():
    """Import qortroller_acp_gateway and return the module."""
    repo_root = _find_qortroller_repo()
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import qortroller_acp_gateway as gw
    return gw


def _send(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _handle_initialize(msg_id) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {
                "name": "qortroller-acp-mcp",
                "version": "0.1.0",
            },
        },
    }


def _handle_tools_list(msg_id) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "tools": [
                {
                    "name": "ask_ea",
                    "description": (
                        "Relay a safe @EA command to the QorTroller ACP. "
                        "Only digest-only read/diagnose commands are allowed."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": 'The @EA command, e.g. "@EA status"',
                            },
                            "pubkey": {
                                "type": "string",
                                "description": "Operator pubkey hex (must be in ACP_OPERATOR_PUBKEYS)",
                            },
                        },
                        "required": ["content", "pubkey"],
                    },
                }
            ]
        },
    }


def _handle_tool_call(gw, msg_id, params) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name != "ask_ea":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"unknown tool: {name}"},
        }

    content = str(arguments.get("content", "")).strip()
    pubkey = str(arguments.get("pubkey", "")).strip()
    if not content or not pubkey:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32602, "message": "content and pubkey are required"},
        }

    cfg = gw.load_config()
    reply = gw.handle_message(pubkey, content, cfg)
    if reply is None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": "(no reply)"}],
                "isError": False,
            },
        }

    content_out, tags = reply
    text = f"{content_out}\n\ntags: {json.dumps(tags)}"
    has_rejected = any(t[0] == "rejected" for t in tags)
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": has_rejected,
        },
    }


def main() -> int:
    try:
        gw = _load_gateway()
    except Exception as e:
        _send({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32000, "message": f"failed to load QorTroller ACP: {e}"},
        })
        return 1

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue

        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "initialize":
            _send(_handle_initialize(msg_id))
            continue
        if method == "initialized":
            # notification, no response
            continue
        if method == "tools/list":
            _send(_handle_tools_list(msg_id))
            continue
        if method == "tools/call":
            _send(_handle_tool_call(gw, msg_id, msg.get("params", {})))
            continue
        if method == "notifications/initialized" or method.startswith("notifications/"):
            continue

        _send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        })

    return 0


if __name__ == "__main__":
    sys.exit(main())
