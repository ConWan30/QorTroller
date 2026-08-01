# Buzz Workflow Policy Routers (v0)

**Status:** IMPLEMENTATION FRAMEWORK  
**Date:** 2026-08-01  
**Parents:**
- `docs/design/buzz-ea-agent-import-proposal.md` (Options A/B **shipped**)
- `docs/design/buzz-ea-acp-harness-integration-v0.md`
- `docs/design/sap-qortroller-buzz-integration-v0.md`

**Non-goals:** Second Buzz bot identity, free-form LLM policy, auto-merge, VSS OPEN, chain spend, HTML-in-chat as authority, raw substrate on Nostr.

---

## 1. What a policy router is

A **workflow policy router** is a small, deterministic program (or Buzz workflow step) that:

1. **Sees** a trigger (schedule, GitHub webhook, file change, channel keyword, cron).
2. **Matches** a **policy row** (table-driven rules).
3. **Emits** one allow-listed ACP command string.
4. **Calls** the existing Face via **webhook** (`POST /buzz`) or **MCP** (`ask_ea`).
5. **Optionally** asks a human workflow to **publish** the returned digest as `@EA`.

It does **not** interpret natural language as authority. It does **not** hold gamer keys. It does **not** seal SAP jobs unless the operator later runs `sap_seal.py`.

```text
Trigger → Policy table → Command template
                ↓
     webhook / MCP (operator pubkey)
                ↓
         handle_message → fixed-argv tools
                ↓
     digest JSON {content, tags, tool, harness}
                ↓
     (optional) publish as @EA
```

---

## 2. Why this is the right shape for QorTroller

| Alternative | Problem |
|-------------|---------|
| New `@PolicyBot` in the community | Identity matrix break |
| LLM decides which shell to run | Violates `shell=False` / allow-list |
| Workflow writes Nostr as itself | Second face; claim drift |
| Router bypasses gateway | Duplicate tool impl; safety fork |

**Router = thin policy.** **Gateway = only tool executor.** Same contract as agent-import §3.

---

## 3. Policy as data

Policies live in a versioned file (repo or operator-local):

**Suggested path:** `config/buzz_workflow_policies.yaml` (or `.json`)  
**Operator overlay:** `audits/workflow_policies.local.yaml` (gitignored) for secrets-free toggles only.

### 3.1 Row schema

```yaml
version: 1
policies:
  - id: daily-repo-health
    enabled: true
    trigger:
      type: cron          # cron | github | queue_nonempty | keyword | manual
      expr: "0 9 * * *"   # example; runner-specific
    match: {}             # optional filters
    action:
      content: "@EA repo health"
      require_operator_pubkey: true
    limits:
      max_per_hour: 1
      cooldown_s: 3600
    publish:
      mode: return_only   # return_only | ea_if_ok | never
    notes: "Morning digest; human may relay to #rig-ops"
```

| Field | Meaning |
|-------|---------|
| `id` | Stable policy id (audit + rate keys) |
| `enabled` | Hard off switch |
| `trigger.type` | What wakes the router |
| `action.content` | **Exact** `@EA …` string from the allow-listed grammar |
| `limits` | Anti-spam |
| `publish.mode` | Whether caller may auto-post as `@EA` |

**Forbidden in `action.content`:** shell metacharacters as free text, spend/git push phrases, VSS OPEN, anything not already parseable by `parse_mention`.

### 3.2 Starter policy catalog (safe defaults)

| id | Trigger | Command | Publish |
|----|---------|---------|---------|
| `daily-repo-health` | cron daily | `@EA repo health` | return_only |
| `daily-invariants` | cron daily | `@EA invariant status` | return_only |
| `on-queue-depth` | queue_nonempty | `@EA diagnose status` | return_only |
| `on-ci-fail-keyword` | keyword in ops (optional) | `@EA failing` | return_only |
| `seat-read-hourly` | cron hourly | `@EA seat` | return_only |
| `manual-full-check` | manual | `@EA plan full check` | return_only (**confirm still human**) |

**Never auto:** `@EA confirm plan …` from a timer without a separate **human** step.  
**Never:** diagnose that invents topics from untrusted GitHub PR titles without an allow-listed map.

---

## 4. Runtime components

### 4.1 `scripts/workflow_policy_router.py` (core)

Responsibilities:

1. Load policy file(s).  
2. Evaluate trigger context (CLI args for v0: `--policy-id`, `--trigger-payload`).  
3. Enforce `enabled`, cooldown, max_per_hour (local JSONL state under `audits/workflow_router_state.jsonl`).  
4. Build request body `{pubkey, content}`.  
5. POST to local webhook **or** call `handle_message` in-process.  
6. Print / return `{ok, content, tags, tool, harness, policy_id}`.  
7. Write audit row (policy_id, trigger, ok, tool)—no secrets.

**v0 preference:** in-process `handle_message` when run on the operator machine (fewer moving parts). Webhook URL optional for remote Buzz-hosted workflows.

### 4.2 Trigger adapters (thin)

| Adapter | Input | Emits |
|---------|-------|-------|
| CLI | `--policy-id daily-repo-health` | run once |
| Cron | system crontab / Buzz schedule | CLI |
| GitHub Actions | `repository_dispatch` / `workflow_run` | CLI with mapped policy_id only |
| Queue watcher | `acp_devin_queue.jsonl` mtime/depth | `on-queue-depth` |

No adapter may construct arbitrary `@EA` strings outside the policy file.

### 4.3 Publish gate

| mode | Behavior |
|------|----------|
| `return_only` | Default. Workflow or human decides. |
| `ea_if_ok` | Only if `ok` and tool in a **publish allow-list** (health, invariant, seat, diagnose status)—still uses bot publish path, never a new npub. |
| `never` | Discard body after audit (test policies). |

`ea_if_ok` requires existing `qortroller_buzz_bot` publish + `BUZZ_PRIVATE_KEY` for **EA only**.

---

## 5. Authorization

| Key | Role |
|-----|------|
| `ACP_OPERATOR_PUBKEYS` | Pubkey sent in webhook/MCP body must match |
| Optional `WORKFLOW_ROUTER_SECRET` | If router calls remote webhook |
| EA bot key | Publish path only; router should not embed gamer keys |

Router process is an **operator harness**, same as import proposal §5.

---

## 6. Relation to SAP

| SAP object | Router interaction |
|------------|-------------------|
| `job_id` | Router does not create jobs unless policy action is `diagnose` / `plan` |
| Seal | **Never** auto-called from router |
| `job status` | Allowed as read policy action |
| Challenge | Manual / human; not cron |

Scheduled **reads** are the sweet spot; scheduled **diagnose** only with fixed topic strings in the policy file.

---

## 7. Security and honesty rails

1. Policy file is code-reviewable; treat changes like allow-list changes.  
2. Cooldown + max_per_hour on every enabled row.  
3. Content must parse via existing `parse_mention` in tests (fixture: each catalog command → Intent, not Rejection).  
4. Fail-closed if operator pubkey missing.  
5. Digests remain scrubbed/bounded inside gateway.  
6. Claim language: router posts **ops digests**, not population evidence.  
7. Log policy_id in ACP audit when possible (optional tag `policy`).

---

## 8. Acceptance criteria (“routers implemented”)

- [ ] `config/buzz_workflow_policies.yaml` with ≥3 safe read policies  
- [ ] `scripts/workflow_policy_router.py --policy-id …` exits 0 and returns gateway-shaped JSON  
- [ ] Cooldown enforced  
- [ ] Unknown policy_id → non-zero exit  
- [ ] Disabled policy → no gateway call  
- [ ] Tests: policy load, match, rate limit, command parse_mention  
- [ ] PV-CI still PASS; no new Buzz identity  
- [ ] Docs point at import proposal Options A/B  

---

## 9. Out of scope (v0)

- Learning/adaptive policies  
- Multi-tenant SaaS router  
- Auto `confirm plan`  
- Cross-community policy federation  
- Replacing EA ACP tools  

---

**End of Buzz Workflow Policy Routers (v0)**
