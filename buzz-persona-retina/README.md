# QorTroller Retina Specialist — Buzz Persona Pack

A Buzz-importable AI agent for Retina / VSS session-integrity work.

## What it is

- **Name:** `retina` / **Display:** `Retina`
- **Purpose:** Explain the Retina Visual Oracle, diagnose VSS/session state, and relay safe `devin @EA` commands.
- **Model:** `xai:grok-4.5`
- **Agent runtime (harness):** `goose` by default — override to a custom `devin` runtime if you have one installed.
- **QorTroller ACP harness default:** `devin` (every `ask_ea` call uses `devin @EA <command>`)
- **Subscribes to:** `#rig-ops`, `#matches`, `#lobby`
- **Triggers:** @mentions + Retina/VSS keywords

## Install

### Option A: Single-file import (recommended)

1. Open Buzz desktop.
2. Go to **Agents → Import Agent**.
3. Select `buzz-persona-retina/qortroller-retina.agent.json`.
4. After import, open Retina’s settings.
5. Set **Runtime / Harness** to your ACP runtime (e.g. `goose`, or a custom `devin` command if available).
6. Set **Provider** to `xai` and **Model** to `grok-4.5`.
7. If you want the agent to call `@EA`, add the QorTroller ACP MCP:
   - Command: `python`
   - Args: `mcp/qortroller_acp_stdio.py` (from this pack)
   - Env: `ACP_OPERATOR_PUBKEYS=<operator-pubkey-hex>`, `QORTROLLER_REPO_ROOT=<absolute-path-to-QorTroller-repo>`

### Option B: Pack install

1. Open Buzz desktop.
2. **Agents → Install Pack**.
3. Point at the folder `buzz-persona-retina/`.

## Files

- `.plugin/plugin.json` — pack manifest
- `agents/retina.persona.md` — the Retina persona (devin ACP harness default)
- `instructions.md` — pack rules
- `skills/retina/SKILL.md` — quick reference
- `.mcp.json` — MCP config
- `mcp/qortroller_acp_stdio.py` — stdio MCP bridge (copied from QorT pack)
- `qortroller-retina.agent.json` — single-file snapshot
- `build_agent_snapshot.py` — rebuild script

## Notes

- This agent **defaults to the `devin` ACP harness** when calling QorTroller. Use `grok-build` only if the user asks.
- It never starts live capture, never holds keys, and never requests raw HID/IMU/L4/frames.
