# Workflow Policy Routers — Grok / Devin Work Packages

**Parent:** `docs/design/buzz-workflow-policy-routers-v0.md`  
**Depends on:** ACP gateway, webhook #122, MCP #123, SAP optional  
**Start at:** **WPR-1**

---

## Rails (every PR)

- [ ] No new Buzz bot npub  
- [ ] All actions are exact `@EA` strings parseable by `parse_mention`  
- [ ] Prefer in-process `handle_message` for local CLI  
- [ ] `shell=False` unchanged in gateway  
- [ ] No auto seal / VSS OPEN / chain  
- [ ] `confirm plan` not in default catalog  
- [ ] PV-CI PASS  

---

## WPR-1 — Policy file + loader + CLI dry spine

**Goal:** Load YAML/JSON policies; run one policy by id; call gateway in-process; print JSON result.

### Deliverables

- `config/buzz_workflow_policies.yaml` — starter catalog (repo health, invariant, seat, diagnose status)
- `scripts/workflow_policy_router.py`
  - `--policy-id`
  - `--dry-run` (print content, no execute)
  - `--pubkey` or env `ACP_OPERATOR_PUBKEYS` first key
  - `--config` path override
- Audit append: `audits/workflow_router_audit.jsonl` (gitignored pattern or under audits/)
- Tests: load, unknown id, disabled, dry-run

### Grok-first

- Schema validation pure functions  
- parse_mention checks for each catalog `content`  

### Devin-first

- CLI wiring, YAML dependency choice (PyYAML if already in project—**or JSON-only v0 to avoid new deps**)

**Prefer JSON v0** if YAML is not already a dependency: `config/buzz_workflow_policies.json`.

### Acceptance

```text
python scripts/workflow_policy_router.py --policy-id daily-repo-health --dry-run
→ {"policy_id": "...", "content": "@EA repo health", ...}

ACP_OPERATOR_PUBKEYS=… python scripts/workflow_policy_router.py --policy-id daily-repo-health
→ gateway result JSON with content/tags
```

---

## WPR-2 — Cooldown / rate limits

**Goal:** `audits/workflow_router_state.jsonl` or small state file; enforce `max_per_hour` and `cooldown_s`.

### Acceptance

Second run within cooldown → exit 0 with `skipped: cooldown` (or exit 3—**pick one and test**); no double tool spam.

---

## WPR-3 — Optional webhook transport

**Goal:** `--transport inprocess|webhook` with `WORKFLOW_WEBHOOK_URL` + optional bearer.

### Acceptance

Webhook path hits `qortroller_buzz_webhook` contract; same policy content.

---

## WPR-4 — Queue-depth trigger helper

**Goal:** `--trigger queue_nonempty` reads `ACP_DEVIN_QUEUE`; if any `status=queued`, run mapped policy (default `on-queue-depth` → `@EA diagnose status`).

### Acceptance

Empty queue → skip; non-empty → one diagnose status call respecting cooldown.

---

## WPR-5 — Docs + crontab example

**Goal:** Short runbook section or `docs/runbook/buzz-workflow-policy-router.md` with example crontab and “never auto-confirm” warning.

---

## PR template

```markdown
## WPR-N
- [ ] …

## Rails
- [ ] no new Buzz identity
- [ ] catalog commands parse_mention clean
- [ ] no confirm plan in default cron set
- [ ] PV-CI PASS
```

---

## Out of scope

Adaptive LLM routers, multi-operator policy markets, Nostr-native policy kinds as authority.

---

**End of WPR work packages**
