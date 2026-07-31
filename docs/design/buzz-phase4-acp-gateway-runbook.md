# Phase 4 ACP Gateway — operator runbook (v0)

Implements `docs/design/buzz-phase4-acp-grok-devin-addendum.md`.
Code: `scripts/qortroller_acp_gateway.py`. Tests:
`bridge/tests/test_qortroller_acp_gateway.py`.

## What it is

A thin, long-running Python process that turns `@EA <command>` mentions in
`#rig-ops` into allow-listed tool calls, routes them (Grok Build primary,
Devin for heavy work), and replies with a digest. It sits **on top of** the
Phase 1–3 bot: the bridge read path, the Rust publish helper, and the NIP-OA
EA identity are all re-used, not re-implemented.

## Command surface

| Mention | Tool | Harness |
|---|---|---|
| `@EA status` / `@EA rig status` | `get_rig_status` | Grok Build |
| `@EA invariant status` (`pv-ci`) | `run_invariant_gate` | Grok Build |
| `@EA health` | `health_check` | Grok Build |
| `@EA ceremony steps` | `list_ceremony_steps` | Grok Build |
| `@EA session [<id>]` | `get_session_summary` | Grok Build |
| `@EA run pytest <path>` | `run_pytest` | Grok Build (`@EA devin run pytest …` → Devin) |
| `@EA diagnose <topic>` | `deep_diagnose` | Devin (queued hand-off) |

Everything else is rejected. Requests naming a banned capability (shell,
wallet/chain, raw HID/IMU/L4/frames/PoAC, git write) are rejected *by name* so
the refusal lands in the audit log instead of being silently dropped.

## Rails

- **Fail-closed authorization.** `ACP_OPERATOR_PUBKEYS` is the operator
  allow-list; empty means nobody is authorized.
- **No shell.** Every tool is a fixed argv run with `shell=False`. Operator
  text never reaches a command line — pytest targets must resolve to an
  existing path under `bridge/tests`, `sdk/tests`, `tests`, or
  `autoresearch/tests`.
- **No chain, no keys, no substrate.** `list_ceremony_steps` returns the
  checklist; the operator still fires every transaction. The gateway holds no
  bot key — publishing goes through the Rust helper as in Phase 1–3.
- **Digest-only replies.** Bounded length, secret-shaped text scrubbed, no
  caller-supplied `h` tag (the helper derives it).
- **Local audit trail.** Every invocation and rejection is appended to
  `audits/acp_gateway.jsonl` (gitignored, never on Nostr). Devin hand-offs go
  to `audits/acp_devin_queue.jsonl`.
- **Devin is not impersonated.** `deep_diagnose` queues a hand-off and says
  so; the operator invokes Devin, and Devin gets no commit or spend authority
  from this surface.

## Running it

```powershell
# scripts/.env — see scripts/qortroller_buzz_bot.env.example

# readiness check before the live acceptance run (publishes nothing)
python scripts/qortroller_acp_gateway.py --preflight

python scripts/qortroller_acp_gateway.py

# one-shot local evaluation (no relay, no publish)
python scripts/qortroller_acp_gateway.py --eval "@EA invariant status"
```

`ACP_DRY_RUN=1` parses, authorizes, routes, and audits without executing any
tool — the safe first run against a live channel.

`--preflight` checks the four things that make the live run behave as documented
— a non-empty operator allow-list, a `#rig-ops` channel, a signing key in the
environment, a reachable publish helper — plus a writable audit log and a
working local tool surface, then prints the acceptance script. It reports key
*presence* only, never a value, and exits non-zero if any check fails.

## Acceptance (addendum §6)

1. `@EA run pytest bridge/tests/test_retina_visual_oracle.py` → Grok Build →
   in-thread reply `[grok-build] pytest …: N passed …`.
2. `@EA invariant status` → current PV-CI count.
3. `@EA health` → `ea | oracle | shell-false` component block.
4. `@EA devin diagnose <topic>` → queued Devin hand-off.
5. No chain interaction, no secrets, no raw biometrics in any reply.

Note: the live gate currently reports **188** invariants, not the 184 quoted in
the addendum (the baseline grew after that count was written). The gateway
reports whatever the gate returns rather than asserting a pinned number.
