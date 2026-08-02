# Buzz Gamer Personal Agent — Runbook

A gamer-facing DM concierge that runs under the **gamer's own `BUZZ_PRIVATE_KEY`**. It is **not** the operator `@EA` bot. You can set your own `BUZZ_PERSONAL_AGENT_NAME` and `BUZZ_PERSONAL_AGENT_ABOUT` so the agent has its own Buzz profile and is easy to DM.

## What it does

- Polls your Buzz DMs every `BUZZ_PERSONAL_AGENT_INTERVAL_S` seconds.
- Answers gamer-self questions by reading the QorTroller bridge.
- Creates agents, channels, projects, workflows, templates, and brainstorms via `buzz_agent_factory.py`.
- Replies in the same DM with digest-only answers.
- Never touches `@EA`, operator commands, shell, chain writes, or raw biometrics.

## Supported DM commands

| Command | Bridge call / action | Reply |
|---------|-------------|-------|
| `status` | `GET /player/session-status` | Rig/session status digest |
| `analytics` | `GET /player/self-analytics` | Your own verified data summary |
| `claim <token> <device>` | `scripts/buzz_ioid_claim.py` | Posts kind 0 profile + #lobby claim |
| `create <agent\|channel\|project\|workflow\|template> <name> [...]` | `scripts/buzz_agent_factory.py` | Creates a new Buzz artifact |
| `brainstorm <topic>` | `scripts/buzz_agent_factory.py` | Seeds a brainstorm post |
| `help` | none | Command list |

Anything starting with `@EA`, `devin @EA`, `run `, etc. is rejected.

## Activation

1. Generate or choose your **gamer key** (this IS your agent; keep it safe):
   ```powershell
   python -c "from nostr_sdk import Keys; k=Keys.generate(); print(k.secret_key().to_bech32())"
   ```
2. Create or find the `#lobby` channel. The `claim` command posts there.
3. Copy `scripts/buzz_personal_agent.env.example` to a local `scripts/buzz_personal_agent.env` and fill:
   - `BUZZ_PRIVATE_KEY` — **your gamer key** (the agent signs posts with it)
   - `BUZZ_RELAY_URL` — e.g. `wss://qortroller.communities.buzz.xyz`
   - `BUZZ_LOBBY_CHANNEL_ID` — `#lobby` channel UUID
   - `BUZZ_PERSONAL_AGENT_NAME` — your chosen display name
   - `BUZZ_PERSONAL_AGENT_ABOUT` — your bio
   - `BUZZ_PERSONAL_AGENT_SETUP_PROFILE=1` — publish your profile on startup
   - `BUZZ_PERSONAL_AGENT_DM_IDS` — DM UUID(s) to poll (optional but recommended)
   - `BRIDGE_BASE_URL` — e.g. `http://localhost:8000`
   - `BRIDGE_API_KEY` (if bridge requires it)
   - `BUZZ_PERSONAL_AGENT_ENABLED=1`
4. Run:
   ```powershell
   python scripts/buzz_personal_agent.py
   ```

The agent will print its `npub` on startup. Add it as a DM contact in the Buzz desktop and send `help` to test.

## Stop

```powershell
python scripts/buzz_personal_agent.py --stop
```

or create `audits/buzz_personal_agent.STOP`.

## Testing without sending replies

```powershell
$env:BUZZ_PERSONAL_AGENT_DRY_RUN="1"
python scripts/buzz_personal_agent.py
```

## Rails

- **One key principle:** this agent uses the **gamer key**, not the operator key.
- It can only read gamer-self endpoints (`/player/session-status`, `/player/self-analytics`).
- It never signs transactions, never spends IOTX, never starts live capture.
- Raw biometric data (HID, IMU, frames, L4 features, full PoAC) is never requested or displayed.
- If the bridge is down, it tells the user to try again later.

## State

`audits/buzz_personal_agent_state.json` tracks the latest `created_at` per DM so each message is only answered once.

## Extending

To add a new self-service query:

1. Add a bridge read endpoint to `_process_message()`.
2. Keep it gamer-only (no operator or chain-mutating endpoints).
3. Return a digest string, never raw substrate.
