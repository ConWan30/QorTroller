# A2A-PKG mailbox — terminal-native agent bus

**Novel channel.** Peer agents no longer wait on operator paste alone. They seal
round files into **hash-bound envelopes** and fire each other via CLI.

```text
docs/a2a/pkg/mailbox/
  outbox/      sealed envelopes (sender proof)
  inbox/       pending for the peer
  delivered/   after fire
  ledger.jsonl append-only event log
  prompt_*.md  rendered fire prompts
  fire_*.log   peer CLI stdout
```

## Envelope schema `qortroller-a2a-envelope-v1`

| Field | Meaning |
|---|---|
| `envelope_id` | SHA-256(canonical JSON sans id)[:16] |
| `body_path` + `body_sha256` | round file + integrity |
| `from_agent` / `to_agent` | grok ↔ claude |
| `expected_reply_path` | next round file the peer must write |
| `mandate` | role + rails (no secrets, no commit, PV-CI clean) |
| `channel` | `terminal-cli` \| `tui-file` \| `operator-paste` |
| `operator_authorized_autonomous_fire` | set when operator ok'd unattended fire |

## Commands

```bash
# Seal a design round for Claude (ground+build)
python scripts/a2a_pkg_relay.py post \
  --from grok --to claude \
  --round docs/a2a/pkg/round-04-grok-design.md \
  --prior docs/a2a/pkg/round-03-claude-ground-build.md \
  --expect docs/a2a/pkg/round-05-claude-ground-build.md \
  --subject "R04 design → ground+build" \
  --autonomous

# Fire Claude CLI with sealed prompt (background)
python scripts/a2a_pkg_relay.py deliver --envelope <id> --fire claude --background

# Status / ack
python scripts/a2a_pkg_relay.py status
python scripts/a2a_pkg_relay.py ack --envelope <id>
```

## Rails

- Operator remains **sole committer** (agents stage only).
- Body hash checked before every fire — tamper → fail closed.
- No secrets in envelopes; round files must stay public-safe.
- Autonomous fire only when `--autonomous` was set on post (operator intent bit).

*Shipped 2026-07-12 as the A2A-PKG terminal bus.*
