# Buzz Gamer Personal Agent — Runbook

A gamer-facing DM concierge that runs under the **gamer's own `BUZZ_PRIVATE_KEY`**. It is **not** the operator `@EA` bot.

## What it does

- Polls your Buzz DMs every `BUZZ_PERSONAL_AGENT_INTERVAL_S` seconds.
- Answers gamer-self questions by reading the QorTroller bridge.
- Replies in the same DM with digest-only answers.
- Never touches `@EA`, operator commands, shell, chain writes, or raw biometrics.

## Supported DM commands

| Command | Bridge call | Reply |
|---------|-------------|-------|
| `status` | `GET /player/session-status` | Rig/session status digest |
| `analytics` | `GET /player/self-analytics` | Your own verified data summary |
| `claim` | none (docs) | How to run `scripts/buzz_ioid_claim.py` |
| `help` | none | Command list |

Anything starting with `@EA`, `devin @EA`, `run `, etc. is rejected.

## Activation

1. Generate a **gamer key** (separate from the operator key):
   ```powershell
   python -c "from nostr_sdk import Keys; k=Keys.generate(); print(k.secret_key().to_bech32())"
   ```
2. From your gamer profile, open a DM with the agent's pubkey:
   ```powershell
   $env:BUZZ_PRIVATE_KEY="<gamer-nsec>"
   buzz/target/debug/buzz.exe dms open --pubkey <agent-pubkey>
   ```
3. Copy `scripts/buzz_personal_agent.env.example` to a local `.env` and fill:
   - `BUZZ_PRIVATE_KEY` — agent key (not the gamer key)
   - `BUZZ_RELAY_URL` — e.g. `http://localhost:3000`
   - `BUZZ_PERSONAL_AGENT_DM_IDS` — the `dm_id` from step 2
   - `BRIDGE_BASE_URL` — e.g. `http://localhost:8000`
   - `BRIDGE_API_KEY` (if bridge requires it)
   - `BUZZ_PERSONAL_AGENT_ENABLED=1`
4. Run:
   ```powershell
   python scripts/buzz_personal_agent.py
   ```

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
