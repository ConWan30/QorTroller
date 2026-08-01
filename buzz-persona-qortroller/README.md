# QorTroller Rig Steward — Buzz Persona Pack

A Buzz-importable AI agent persona for QorTroller operations.

## What it is

- **Name:** QorT
- **Purpose:** Explain QorTroller, diagnose via the ACP, and relay safe `@EA` commands.
- **Model:** `xai:grok-4.5`
- **ACP harness default for @EA relay:** `grok-build`
- **Subscribes to:** `#rig-ops`, `#general`, `#lobby`
- **Triggers:** @mentions + keywords (qortroller, rig, session, ioID, PoAC, VAPI, invariant, verdict, postcard)

## Install

### Option A: Single-file import (recommended)

The simplest way to get QorT into Buzz is the pre-built `.agent.json` snapshot:

1. Open Buzz desktop.
2. Go to **Agents → Import Agent** (or **Create Agent → Import**).
3. Select this file: `buzz-persona-qortroller/qortroller-rig-steward.agent.json`.
4. After import, open QorT’s settings.
5. Set **Runtime / Harness** to **goose**.
6. Set **Provider** to **xai** and **Model** to **grok-4.5**.
7. If you want the agent to actually call `@EA`, add the QorTroller ACP MCP server:
   - Command: `python`
   - Args: `mcp/qortroller_acp_stdio.py` (from this pack)
   - Env: `ACP_OPERATOR_PUBKEYS=<operator-pubkey-hex>`, `QORTROLLER_REPO_ROOT=<absolute-path-to-QorTroller-repo>`

### Option B: Install as a Persona Pack

1. Open Buzz desktop.
2. Go to **Agents → Install Pack** (if available).
3. Point the file picker at the folder `buzz-persona-qortroller/`.
4. After import, set the same harness/model/env as above.

### Option C: Zip and import as a pack

```powershell
# From the QorTroller repo root
Compress-Archive -Path "buzz-persona-qortroller\*" -DestinationPath "qortroller-rig-steward.buzzpack.zip" -Force
```

Then in Buzz: **Agents → Install Pack → `qortroller-rig-steward.buzzpack.zip`**.

## Files

- `.plugin/plugin.json` — pack manifest
- `agents/qortroller.persona.md` — the QorT persona prompt
- `instructions.md` — pack-level rules
- `skills/qortroller/SKILL.md` — QorTroller quick reference
- `.mcp.json` — MCP server config for the QorTroller ACP
- `mcp/qortroller_acp_stdio.py` — stdio MCP bridge
- `qortroller-rig-steward.agent.json` — single-file agent snapshot for **Import Agent**
- `build_agent_snapshot.py` — rebuild script for the `.agent.json`

## The QorTroller ACP bridge

The persona pack and the `.agent.json` both expect a QorTroller ACP MCP server. To make it work:

1. The file `mcp/qortroller_acp_stdio.py` is already in this pack.
2. Set `QORTROLLER_REPO_ROOT` so the bridge can locate `qortroller_acp_gateway.py`.
3. Set `ACP_OPERATOR_PUBKEYS` to the operator(s) who may run `@EA` commands.

The bridge is a minimal stdio MCP server that exposes one tool:

- `ask_ea({ content: "@EA ...", pubkey: "..." })` → returns QorTroller ACP digest.

## Notes

- This agent **does not hold keys**.
- It cannot spend IOTX, sign transactions, or run shell commands.
- Operator commands are gated by `ACP_OPERATOR_PUBKEYS` in the ACP, not the persona.
- For live match/session pinning, the operator must still run `scripts/buzz_pin_match.py` themselves.
