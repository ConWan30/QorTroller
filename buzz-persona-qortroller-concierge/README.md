# Retina — Buzz Agent Pack

A gamer-facing self-service concierge for QorTroller, modeled on the QorT (Rig Steward) pack.

- **Model:** `z-ai/glm-5.2`
- **Runtime:** `hermes`
- **Respond to:** `owner-only`

## Import into Buzz

The simplest way is the pre-built `.agent.json` snapshot:

1. Open Buzz Desktop → Settings → Agents → Import Agent.
2. Select this file: `buzz-persona-qortroller-concierge/qortroller-concierge.agent.json`.
3. The agent is `Retina` and responds to DMs and mentions.
4. Set Runtime / Harness to `hermes` if Buzz asks.

## Rebuild the snapshot

```powershell
python buzz-persona-qortroller-concierge/build_agent_snapshot.py
```

## Pack layout

- `agents/qortroller-concierge.persona.md` — agent identity, channels, commands, and rules.
- `instructions.md` — appended to the system prompt.
- `skills/qortroller-concierge/SKILL.md` — quick reference.
- `mcp/qortroller_concierge_acp_stdio.py` — MCP bridge to the QorTroller ACP (`ask_ea`).
- `.mcp.json` — MCP server wiring.
- `build_agent_snapshot.py` — assembles the snapshot.
- `qortroller-concierge.agent.json` — pre-built single-file agent snapshot.

## What Retina can do

- Answer DMs: `status`, `analytics`, `claim <token> <device>`, `help`.
- Propose/hire: `propose <...>` and `hire <name> --clause P-...`.
- Seed brainstorms: `brainstorm <topic>`.
- Relay safe `@EA` read/diagnose commands via `ask_ea` when the caller is an operator.

## Safety rails

- Does not store or ask for private keys.
- Does not run shell, git, chain-spend, or raw-HID operations.
- Does not post raw biometrics.
- Does not overwrite the user's personal Buzz profile.

## MCP setup

The pack expects the QorTroller ACP gateway at `scripts/qortroller_acp_gateway.py`.
Environment variables for the MCP server:

- `ACP_OPERATOR_PUBKEYS` — comma-separated operator pubkeys.
- `ACP_MCP_SECRET` — optional shared secret.
- `ACP_MAX_REPLY_CHARS` — max reply length.
- `QORTROLLER_REPO_ROOT` — repo root if not running inside the repo.
