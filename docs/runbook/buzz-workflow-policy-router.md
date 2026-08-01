# QorTroller Workflow Policy Router — Runbook

**Scope:** WPR-1 / WPR-2 / WPR-3 from `docs/design/buzz-workflow-policy-routers-*.md`

- `config/buzz_workflow_policies.json` — catalog
- `scripts/workflow_policy_router.py` — CLI + library
- `bridge/vapi_bridge/operator_api/workflow_policies.py` — dashboard API
- `audits/workflow_router_state.jsonl` — operator-local rate/cooldown state

---

## Quick start

```powershell
# List policies
python scripts/workflow_policy_router.py --list

# Dry-run a policy (prints the @EA command, no tool executed)
python scripts/workflow_policy_router.py --policy-id daily-repo-health --dry-run

# Run a policy against the ACP gateway
ACP_OPERATOR_PUBKEYS=<op-pubkey-hex> python scripts/workflow_policy_router.py --policy-id daily-repo-health

# HTTP (WPR-3): POST to a local webhook
WORKFLOW_WEBHOOK_URL=http://localhost:8080/buzz \
    ACP_OPERATOR_PUBKEYS=<op-pubkey-hex> \
    python scripts/workflow_policy_router.py --policy-id daily-repo-health
```

Dashboard API:

```powershell
curl -H "x-api-key: <read-key>" http://localhost:8000/operator/workflow-policies

curl -X POST -H "x-api-key: <read-key>" \
    "http://localhost:8000/operator/workflow-policies/daily-repo-health/run?dry_run=true"
```

---

## Policy catalog

Each policy row must be:

```jsonc
{
  "id": "daily-repo-health",
  "enabled": true,
  "trigger": { "type": "cron", "expr": "0 9 * * *" },
  "action": { "content": "@EA repo health", "require_operator_pubkey": true },
  "limits": { "max_per_hour": 1, "cooldown_s": 3600 },
  "publish": { "mode": "return_only" }
}
```

| Field | Meaning |
|-------|---------|
| `id` | Stable policy id (audit + rate key) |
| `enabled` | Hard off switch |
| `trigger.type` | `cron` / `queue_nonempty` / `manual` (declarative for v1) |
| `action.content` | Exact `@EA …` command from the allow-listed grammar |
| `action.require_operator_pubkey` | Require an operator pubkey before running |
| `limits.max_per_hour` | Maximum non-skipped attempts per rolling hour |
| `limits.cooldown_s` | Minimum seconds between non-skipped attempts |
| `publish.mode` | `return_only` only in v1 |

**Forbidden in `action.content`:** shell metacharacters, chain spend terms, raw-substrate terms, `confirm plan` without a separate human step.

---

## Caveats (read before relying on limits / automation)

### 1. Cron and `queue_nonempty` are declarative only

WPR-1 does **not** include a scheduler daemon. `trigger.type = cron` and `trigger.type = queue_nonempty` describe intent; something else must wake the router:

- `cron`: system cron or Windows Task Scheduler calling `--policy-id <id>`
- `queue_nonempty`: an operator process that polls `audits/acp_devin_queue.jsonl` and calls the policy
- `manual`: the operator or a dashboard button calls the policy directly

A later work package (WPR-4) may add a queue-depth trigger helper; WPR-5 may add a crontab example.

### 2. Cooldown counts attempts, not just successes

`_count_runs_in_window` counts **non-skipped attempts** (including failed ACP runs and rejected commands). After a failed run, the cooldown still applies. This is fail-closed and consistent with the ACP gateway — do not read a `skipped: cooldown` as a sign that the previous run was green.

### 3. `ok` heuristic

The in-process runner inspects the ACP reply tags: if any tag has key `rejected`, the run is `ok: false`. This is more precise than text grepping but still a heuristic. A tool that returns natural language containing the word "error" will not be marked failed unless the gateway tagged it `rejected`.

### 4. `POST /operator/workflow-policies/{id}/run` uses a read-key

The bridge endpoint reuses `check_read_key` (same as `/player/session-status` and other operator GETs). For the current v1 surface this is acceptable because all actions are bounded `@EA` digests and the ACP gateway itself enforces the operator allow-list. If future policies gain write side effects (seal, queue fire, chain), split to a separate write-key check.

### 5. `action.content` is statically validated at load time

Policies are rejected if `action.content` does not start with `@EA` or contains a banned pattern. This is a safety rail, not a semantic guarantee — the ACP gateway still has final say on whether the command is allow-listed.

### 6. State file is operator-local and gitignored

`audits/workflow_router_state.jsonl` is in `.gitignore`. It contains timestamps and outcomes per policy. Treat it like `audits/acp_sap_seals.jsonl` — it should not be committed.

### 7. No auto-publishing to Nostr

`publish.mode: return_only` means the router returns the result. A human or a separate process must decide to publish it as `@EA` in a Buzz channel. WPR does not hold a Nostr signing key and does not post on its own.

### 8. `mergeable_state: unstable` / CI

Always confirm the PR is green on GitHub before merge. Local `254 passed + 188 PV-CI` is strong signal, but the canonical gate is the repo’s CI. Do not land on local green alone for consequential work.

---

## Crontab example

```cron
# Run daily at 09:00
0 9 * * * cd /path/to/QorTroller && . .env && python scripts/workflow_policy_router.py --policy-id daily-repo-health >> /var/log/qortroller-wpr.log 2>&1

# Run hourly seat check
0 * * * * cd /path/to/QorTroller && . .env && python scripts/workflow_policy_router.py --policy-id seat-read-hourly >> /var/log/qortroller-wpr.log 2>&1
```

Use the operator `.env` that sets `ACP_OPERATOR_PUBKEYS` (not `BUZZ_PRIVATE_KEY`).

---

## Buzz workflow dashboard integration

The Buzz desktop **Create Workflow** UI can add an HTTP step that POSTs to the QorTroller dashboard API:

```
POST /operator/workflow-policies/{policy_id}/run
Host: qortroller-bridge:8000
x-api-key: <bridge-read-key>
```

The response is the same `{ok, content, tags, tool, harness}` shape the webhook returns, so a Buzz workflow can publish the reply as a kind-9 message in the chosen channel.

For shared-secret webhook integration (WPR-3), set `BUZZ_WEBHOOK_SECRET` and `WORKFLOW_WEBHOOK_URL` and use the existing `/buzz` endpoint in `qortroller_buzz_webhook.py` with a payload like:

```json
{
  "pubkey": "<operator-hex>",
  "content": "@EA repo health"
}
```

Mapping a Buzz workflow trigger to a QorTroller policy by id is a future refinement.
