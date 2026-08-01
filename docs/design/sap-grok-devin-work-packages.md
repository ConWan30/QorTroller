# SAP — Grok Build × Devin Collaboration Work Packages

**Status:** IMPLEMENTATION INSTRUMENTS — **start at SAP-1**  
**Date:** 2026-08-01 (handoff refresh post-PR #123 MCP)  
**Parent:** `docs/design/sap-qortroller-buzz-integration-v0.md`  
**Code base:** `scripts/qortroller_acp_gateway.py`, EA-ACP-1..5, webhook #122, **MCP #123**  
**Harness split:** Grok = pure helpers + parse/tool tests; Devin = multi-file plumbing + scripts

---

## Handoff for Devin

1. Read parent integration doc § Handoff + §2 object map.  
2. **No merge conflict** with MCP/webhook — do **not** reimplement tools inside MCP/webhook.  
3. Implement **SAP-1** first in one PR; then SAP-2; then SAP-3.  
4. New gateway tools automatically work via `@EA`, `POST /buzz`, and `ask_ea`.  
5. Use PR template at bottom of this file.

---

## 0. Collaboration rules (both harnesses)

1. Single Buzz face `@EA` — no Grok/Devin community agents.  
2. Reuse `handle_message` / `execute` / `format_reply` / `scrub`.  
3. `shell=False`; allow-listed tools only.  
4. JSONL under `audits/` stays gitignored for operator data.  
5. Tests in `bridge/tests/test_qortroller_acp_gateway.py` and/or `bridge/tests/test_sap_*.py`.  
6. `python scripts/vapi_invariant_gate.py` PASS (188+).  
7. No FROZEN wire, chain, VSS OPEN, or claim-register grade inflation.  
8. Do **not** modify MCP/webhook except if a shared import breaks — fix at gateway.  
9. PR body: Devin checklist from EA ACP integration doc + SAP rails below.

**Grok-first:** `new_job_id()`, parse bits, unit tests.  
**Devin-first:** result_record, context_pack, queue_watch, seal CLI wiring, integration tests.

---

## SAP-1 — Stable `job_id` propagation  ← **DO THIS FIRST**

**Goal:** One id ties queue ticket, plan (optional), audit, and Devin result.

### Spec

- Generate `job_id` as `sap_<12 hex>` (preferred) or `sap_<ts>_<nonce>` when:
  - `deep_diagnose` queues a row
  - `plan` stages a plan (**rule:** set `job_id` on plan record; `plan_id` may remain the short confirm token **or** equal `job_id` — **pick one, document in PR, test both create + confirm paths**)
- Write `job_id` into:
  - `audits/acp_devin_queue.jsonl`
  - `audits/acp_gateway.jsonl` audit rows for diagnose (and plan tools)
  - `audits/acp_plans.jsonl` on plan create
- `scripts/acp_devin_result_record.py --job-id` optional (store if provided)
- `scripts/acp_devin_context_pack.py` / `acp_devin_queue_watch.py` show `job_id` when present
- Reply digest may include `job: sap_…` within `MAX_REPLY_CHARS`
- **Backward compatible:** old JSONL rows without `job_id` still parse

### Grok Build

- [ ] `new_job_id()` pure helper + unit tests
- [ ] diagnose path attaches `job_id`
- [ ] reply + audit include `job_id`

### Devin

- [ ] plan path attaches `job_id` per chosen rule
- [ ] result_record + context_pack + queue_watch
- [ ] Integration: queue row → result row same `job_id`
- [ ] Regression: existing ACP + webhook + MCP test suites still green

### Acceptance

```text
@EA diagnose example topic
→ queue row has job_id
→ audit row has job_id
python scripts/acp_devin_result_record.py --job-id sap_… --status done
→ results row has same job_id
# optional: MCP/webhook same content string behaves identically
```

---

## SAP-2 — Local seal log (`scripts/sap_seal.py`)

**Goal:** Operator-only seal without protocol/population proof claims.

### Spec

```text
python scripts/sap_seal.py --job-id sap_… --accept|--reject|--hold \
  [--ref PR_URL_OR_SHA] [--note "…"]
→ appends audits/acp_sap_seals.jsonl
```

```json
{
  "ts": 0,
  "job_id": "sap_…",
  "verdict": "accept",
  "ref": "https://github.com/…/pull/N",
  "note": "optional",
  "operator": "local"
}
```

- No Nostr publish by default
- Default: refuse if `job_id` never seen in queue/results/plans (unless `--force`)
- `.gitignore` `audits/acp_sap_seals.jsonl`

### Acceptance

Append-only seals; reject path; no Buzz side effects.

---

## SAP-3 — `@EA job status <job_id>`

**Goal:** One digest: queue → results → seal.

### Spec

- Tool `get_job_status` (**Grok-only**)
- Parse: `job status <id>` / `sap status <id>`
- Read local JSONL only; honest `unknown job` if missing
- Example: `job sap_…: queued|done|sealed-accept | pr: …`
- Available automatically via MCP/webhook once in gateway

### Acceptance

```text
@EA job status sap_…
→ [grok-build] job … digest
```

---

## SAP-4 — Optional challenge records

Lightweight `audits/acp_sap_challenges.jsonl`; **skip** if SAP-1..3 enough for first public note.

---

## SAP-5 — Publish gate (docs only)

After operator dogfood SAP-1..3: set publish doc Status to **reference-ready**. No overclaim grades.

---

## PR template (copy into each SAP PR)

```markdown
## SAP WP
- [ ] SAP-N title

## Rails
- [ ] @EA only face
- [ ] shell=False / allow-list
- [ ] job_id additive only; old rows still parse
- [ ] no auto-seal from harness
- [ ] no VSS OPEN / chain
- [ ] MCP/webhook not duplicated (gateway only)
- [ ] PV-CI PASS
- [ ] tests listed (incl. ACP and, if touched imports, webhook/MCP smoke)

## Mapping
Job / Receipt / Seal touched: …
```

---

## Out of scope

- Nostr-native SAP kinds, ZK, multi-operator seals  
- Sentry/Guardian/Curator as Buzz bots  
- Replacing webhook, MCP, or Phase 1 bot  
- Implementing SAP tools only inside MCP server  

---

**End of SAP Grok × Devin Work Packages**
