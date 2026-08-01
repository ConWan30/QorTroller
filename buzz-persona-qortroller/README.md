# QorTroller Rig Steward — Buzz Persona Pack

A Buzz-importable AI agent persona for QorTroller operations.

## What it is

- **Name:** QorT
- **Purpose:** Explain QorTroller, diagnose via the ACP, and relay safe `@EA` commands.
- **Model:** `xai:grok-4.5`
- **ACP harness default:** `grok-build`
- **Subscribes to:** `#rig-ops`, `#general`, `#lobby`
- **Triggers:** @mentions + keywords (qortroller, rig, session, ioID, PoAC, VAPI, invariant, verdict, postcard)

## Install

### Option A: Install from this repo (recommended)

1. Open Buzz desktop.
2. Go to **Agents → Install Pack**.
3. Point the file picker at this directory: `buzz-persona-qortroller/`.
4. After import, open QorT’s settings.
5. Set **Harness / Runtime** to your ACP runtime (e.g. `goose` or `claude-code`).
6. Set **Model** to `xai:grok-4.5` (or any other provider; `grok-4.5` is the pack default).
7. If you want the agent to actually call `@EA`, set the environment variables in the harness runtime:
   - `ACP_OPERATOR_PUBKEYS=<operator-pubkey-hex>`
   - `ACP_MCP_SECRET=<optional-secret>`
   - `QORTROLLER_REPO_ROOT=<absolute-path-to-QorTroller-repo>` (so the stdio bridge can find `qortroller_acp_gateway.py`)

### Option B: Zip and import

```powershell
# From the QorTroller repo root
Compress-Archive -Path "buzz-persona-qortroller\*" -DestinationPath "qortroller-rig-steward.buzzpack.zip"
```

Then import the zip in Buzz.

## Files

- `.plugin/plugin.json` — pack manifest
- `agents/qortroller.persona.md` — the QorT persona prompt
- `instructions.md` — pack-level rules
- `skills/qortroller/SKILL.md` — QorTroller quick reference
- `.mcp.json` — MCP server config for the QorTroller ACP
- `mcp/qortroller_acp_stdio.py` — stdio MCP bridge (if present; see below)

## The QorTroller ACP bridge

The persona pack references an MCP server `qortroller-acp`. To make it work:

1. Copy `scripts/qortroller_acp_mcp_stdio.py` from the QorTroller repo into `mcp/qortroller_acp_stdio.py` inside this pack.
2. Or set `QORTROLLER_REPO_ROOT` so the bridge can locate `qortroller_acp_gateway.py`.

The bridge is a minimal stdio MCP server that exposes one tool:

- `ask_ea({ content: "@EA ...", pubkey: "..." })` → returns QorTroller ACP digest.

## Notes

- This agent **does not hold keys**.
- It cannot spend IOTX, sign transactions, or run shell commands.
- Operator commands are gated by `ACP_OPERATOR_PUBKEYS` in the ACP, not the persona.
- For live match/session pinning, the operator must still run `scripts/buzz_pin_match.py` themselves.
