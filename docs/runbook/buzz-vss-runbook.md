# Verifiable Stream Seat (VSS) — operator runbook (v0)

Implements `docs/design/buzz-vss-stream-seat-scope-v0.md` §8 (VSS-5).
Code: `scripts/buzz_vss_seat.py`, `bridge/vapi_bridge/vss_seat_schema.py`,
`bridge/vapi_bridge/operator_api/agent_vss.py`,
`scripts/qortroller_acp_gateway.py`.
Tests: `bridge/tests/test_vss_eligibility.py`,
`bridge/tests/test_vss_seat_schema.py`,
`bridge/tests/test_vss_seat_helper.py`,
`bridge/tests/test_vss_seat_status_acp.py`.

## What it is

VSS lets a human gamer open a "stream seat" on Buzz — a proof-adjacent
broadcast pointer that is OPEN only while the rig eligibility holds
(capture up + retina oracle running). The seat carries an honesty
ribbon (poep/l6b/candidate flags as-is), a media URL pointer, and
optional session/ioID bind slots. It is **not** video on Nostr; it is
a protocol object on the social plane that points to external media.

Three-plane split:
- **Buzz (social plane):** seat events, ACP status replies, claim language
- **QorTroller (truth plane):** eligibility, honesty ribbon, bridge state
- **External media:** gamer-controlled URL (Twitch, YouTube, etc.)

## Prerequisites

1. **Bridge running** with capture monitor + retina oracle (VSS-1 eligibility)
2. **Buzz relay running** at `ws://localhost:3000`
3. **`#streams` channel** created (operator live community task — not automated)
4. **Gamer key** set in env (`BUZZ_PRIVATE_KEY` — the gamer's own key, NOT the bot/EA key)
5. **Rust helper** built (`cargo build -p qortroller-buzz`)
6. **PV-CI green** (`python scripts/vapi_invariant_gate.py`)

## VSS-1: Eligibility endpoint

**Code:** `bridge/vapi_bridge/operator_api/agent_vss.py`
**Route:** `GET /operator/vss/eligibility`
(Operator sub-app is mounted at `/operator`; route on the sub-app is `/vss/eligibility`.)

Returns:
```json
{
  "eligible": true,
  "capture_up": true,
  "retina_oracle_running": true,
  "reason_if_closed": "",
  "honesty": {
    "poep_enabled": false,
    "l6b_enabled": false,
    "candidate_ok": false
  }
}
```

Fail-closed: if capture is down OR oracle is stopped → `eligible: false`.
Bridge unreachable → `eligible: false`. Never fabricates.

## VSS-2: Seat event schema

**Code:** `bridge/vapi_bridge/vss_seat_schema.py`

Seat events are kind 9 (NIP-29 channel message) with tags:
- Required: `qortroller=1`, `vss=1`, `seat={OPEN|CLOSED}`, `capture={up|down}`, `retina_oracle={running|stopped}`
- Required ribbon: `poep_enabled`, `l6b_enabled`, `candidate_ok` (all `true`/`false`, posted as-is)
- Optional: `media_url` (required for OPEN), `session_id` (F2 bind slot), `ioid_token` (never required)

Forbidden in content/tags: nsec, base64, frames, HID, IMU, PoAC payload, L4 features, keys.

## VSS-3: Seat open/close helper

**Code:** `scripts/buzz_vss_seat.py`

### Starting a seat (live mode)

```powershell
# Set gamer key (NOT the bot key)
$env:BUZZ_PRIVATE_KEY = "<gamer-nsec>"

# Set channel + media URL
$env:VSS_STREAMS_CHANNEL = "<streams-channel-uuid>"

python scripts/buzz_vss_seat.py `
    --media-url https://stream.example.com/live `
    --poll-interval 15
```

### Dry-run (no publish, just poll + print)

```powershell
python scripts/buzz_vss_seat.py --dry-run
```

### State machine

```
CLOSED --(eligible rising edge)--> OPEN --(ineligible falling edge)--> CLOSED
```

- **Rising edge** (false→true): publishes OPEN with media URL + ribbon
- **Falling edge** (true→false): publishes CLOSED
- **No transition:** no publish (no spam — one event per transition)
- **Bridge unreachable:** fail-closed CLOSE if seat was OPEN
- **Ctrl+C:** best-effort CLOSE on shutdown

### Safety rails

- Uses the **gamer's own key** (BUZZ_PRIVATE_KEY), not the bot/EA key
- Architecture C: Python builds digest JSON, Rust helper signs + sends
- `shell=False` on all subprocess calls
- Never uploads pixels, frames, or raw biometrics
- Never signs with the bot key
- Never fabricates eligibility
- VSS-2 schema validation before every publish

### Optional fields

```powershell
# With session_id (F2 watch-party bind slot)
python scripts/buzz_vss_seat.py --session-id sess_abc123 ...

# F2: probe bridge for session_id (never fabricates; URL-only if absent)
python scripts/buzz_vss_seat.py --bind-session --media-url https://...

# F2: refuse OPEN unless a session_id is resolved
python scripts/buzz_vss_seat.py --require-session-bind --session-id sess_abc123 ...

# F2: optional #matches channel UUID pointer on the seat
python scripts/buzz_vss_seat.py --matches-channel <matches-uuid> ...

# With ioID token (display only, never required)
python scripts/buzz_vss_seat.py --ioid-token 498 ...
```

### F2 — Verifiable watch-party bind

When `session_id` is present on the seat:

- Tags include `session_id=<id>`
- Content includes `session: <id>` so a stranger can distinguish
  “watching a URL” from “room claims sealed session X”
- Optional `matches_channel` points at `#matches` (UUID only — not proof)
- **R-VSS-06** is sayable **only** for that bound seat (not for URL-only seats)

Honest absence: omit `--session-id` / leave bind probe empty → no session tag.
Never invent a session id. Never use `device_id` alone as the session bind.

## VSS-4: ACP status tool

**Code:** `scripts/qortroller_acp_gateway.py` (tool: `get_stream_seat_status`)

### Reading seat status via Buzz

```
@EA stream seat status
@EA seat
@EA vss
@EA get stream seat
```

Returns a digest-only reply (scrubbed, no raw substrate):
```
[grok-build] stream seat: ELIGIBLE | capture: up | oracle: running | poep=False l6b=False candidate=False
```

Fail-closed: bridge unreachable → "stream seat: bridge unreachable — eligibility unknown (fail-closed)"

Routing: stays on Grok Build even if operator says `@EA devin seat`.

## VSS-S1: Agent viewers (summarize + flag-down)

**Code:** `bridge/vapi_bridge/vss_agent_viewer.py`, ACP tools on the gateway.

Agents may **READ / summarize / flag DOWN**. Agents **cannot OPEN** (VSS-7 / F3).

```
@EA summarize stream seat
@EA seat summary
@EA flag seat down
@EA is seat down
```

| Tool | Role |
|------|------|
| `summarize_stream_seat` | Digest agent-view of eligibility + ribbon + READ-only reminder |
| `flag_stream_seat_down` | `FLAG_DOWN` if ineligible; `SEAT_OK` if eligible; `UNKNOWN` if bridge down (never invents DOWN) |

Never: agent-authored seat OPEN, raw HID/frames, humanity-proven language.

## VSS-S2: Anti-farm (one seat per key)

**Code:** `bridge/vapi_bridge/vss_anti_farm.py` (wired into `buzz_vss_seat.py`)

- **Empty OPEN refused** — no `media_url` → no OPEN (schema + helper)
- **One OPEN at a time** per (channel, signer pubkey) via local state
  `audits/vss_seat_local_state.json` (override with `VSS_SEAT_STATE_PATH`)
- CLOSED clears the slot so the same key can OPEN again
- Local ops state only — not a cryptographic ban ledger

## VSS-5: Claim rows

**Doc:** `docs/design/buzz-phase5-claim-register-v0.md` (§6 — VSS rows)

Claim rows R-VSS-01..07 are **draft** until promoted in a reviewed commit.
See the claim register for grades, gates, and the never-sayable list.

### Key honesty rules

- **R-VSS-04** ("Stream is humanity-proven / tournament-grade") is **G4 — Forbidden** until Phase 5 gates
- "Process running" ≠ "humanity proven" — the oracle gate is process health, not a population cert
- Honesty ribbon is posted **as-is** — never invents `true`
- `@EA` output is G0 (a statement about the repository, never about a population)

## End-to-end operator checklist

1. **Verify PV-CI:** `python scripts/vapi_invariant_gate.py` (expect 188 PASS)
2. **Verify VSS tests:** `python -m pytest bridge/tests/test_vss_*.py -q` (expect 58 passed)
3. **Start bridge:** ensure capture monitor + retina oracle are running
4. **Check eligibility:** `curl http://localhost:8000/operator/vss/eligibility` (expect `eligible: true`)
5. **Set gamer key:** `$env:BUZZ_PRIVATE_KEY = "<gamer-nsec>"`
6. **Set channel:** `$env:VSS_STREAMS_CHANNEL = "<streams-channel-uuid>"`
7. **Dry-run first:** `python scripts/buzz_vss_seat.py --dry-run`
8. **Go live:** `python scripts/buzz_vss_seat.py --media-url https://...`
9. **Monitor via ACP:** `@EA seat` in `#rig-ops`
10. **Stop:** Ctrl+C (best-effort CLOSE published)

## Never

- Start a stream as EA (bot cannot OPEN a gamer seat)
- Hold gamer media keys in the bot
- Post frames, base64 video, or raw biometrics on Nostr
- Flip oracle enablement without a human ceremony
- Say "humanity-proven" or "tournament-grade" for a stream seat (R-VSS-04 is G4 forbidden)
- Require IoID to stream (Buzz human membership is the only membership gate)
- Touch FROZEN wire, commitment tags, or spend chain

## Out of scope for this runbook

- VSS-6 / VSS-7 / live dogfood (shipped + operator-confirmed)
- Proper relay `profile get` for VSS-7 role verify (helper enhancement)
- Multi-gamer seats (after G5-MULTI)
- Real production CDN / Twitch integration (media URL is gamer-controlled)

---

**End of VSS operator runbook (v0)**
