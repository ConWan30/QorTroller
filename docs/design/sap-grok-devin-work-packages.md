# SAP — Grok Build × Devin Collaboration Work Packages

**Status:** IMPLEMENTATION INSTRUMENTS  
**Date:** 2026-08-01  
**Parent:** `docs/design/sap-qortroller-buzz-integration-v0.md`  
**Code base:** `scripts/qortroller_acp_gateway.py`, EA-ACP-1..5, webhook PR #122  
**Harness split:** Grok = default tools + tests in-PR; Devin = multi-file / queue consumer paths

---

## 0. Collaboration rules (both harnesses)

1. Single Buzz face `@EA` — no Grok/Devin community agents.  
2. Reuse `handle_message` / `execute` / `format_reply` / `scrub`.  
3. `shell=False`; allow-listed tools only.  
4. JSONL under `audits/` stays gitignored for operator data.  
5. Tests in `bridge/tests/test_qortroller_acp_gateway.py` (or `test_sap_*.py`).  
6. `python scripts/vapi_invariant_gate.py` PASS (188+).  
7. No FROZEN wire, chain, VSS OPEN, or claim-register grade inflation.  
8. PR body must include the Devin checklist from EA ACP integration doc.

**Grok-first:** parse/route/tool digests, small pure helpers, unit tests.  
**Devin-first:** cross-file plumbing, scripts UX, watchers, richer status tools.

---

## SAP-1 — Stable `job_id` propagation

**Goal:** One id ties queue ticket, plan (optional), audit, and Devin result.

### Spec

- Generate `job_id` as `sap_<short_hash>` or `sap_<ts>_<nonce>` when:
  - `deep_diagnose` queues
  - `plan` stages (plan_id may equal or alias job_id — pick one rule and test it)
- Write `job_id` into:
  - `audits/acp_devin_queue.jsonl`
  - `audits/acp_gateway.jsonl` audit rows for that tool
  - `audits/acp_plans.jsonl` when plan created from diagnose-like goals
- `acp_devin_result_record.py --job-id` optional arg (required for SAP-2 link)
- Reply digest may include `job: sap_…` within `MAX_REPLY_CHARS`

### Grok Build

- [ ] ID helper pure function + unit tests
- [ ] diagnose path attaches job_id
- [ ] reply/audit include job_id

### Devin

- [ ] result_record + context_pack read/write job_id
- [ ] queue_watch prints job_id
- [ ] Integration tests across queue → result

### Acceptance

```text
@EA diagnose example topic
→ queue row has job_id
→ audit row has job_id
scripts/acp_devin_result_record.py --job-id … --status done
→ results row has same job_id
```

---

## SAP-2 — Local seal log (`scripts/sap_seal.py`)

**Goal:** Operator-only seal without implying protocol/population proof.

### Spec

```text
python scripts/sap_seal.py --job-id sap_… --accept|--reject|--hold \
  [--ref PR_URL_OR_SHA] [--note "…"]
→ appends audits/acp_sap_seals.jsonl
```

Record shape:

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

- No Nostr publish from this script by default
- Refuse unknown job_id unless `--force` (default refuse)
- `.gitignore` seals file

### Grok Build

- [ ] CLI + validation tests
- [ ] refuse missing job_id

### Devin

- [ ] Wire job_id index lookup from queue/results
- [ ] Document operator flow in runbook blurb under `docs/design/` or runbook pointer

### Acceptance

Seal file append-only; reject path works; no Buzz side effects.

---

## SAP-3 — `@EA job status <job_id>`

**Goal:** One digest: queue → results → seal.

### Spec

- New tool `get_job_status` (Grok-only)
- Parse: `job status <id>` / `sap status <id>`
- Read local JSONL only; honest “unknown job” if missing
- Summary example: `job sap_…: queued|done|sealed-accept | pr: … | note: …`
- Scrub + bound

### Grok Build

- [ ] Tool + parse + tests

### Devin

- [ ] Edge cases: sealed without result; result without seal; duplicate ids latest-wins rule documented

### Acceptance

```text
@EA job status sap_…
→ [grok-build] job … digest
```

---

## SAP-4 — Optional challenge records (lightweight)

**Goal:** Record re-exec challenges without a social voting system.

### Spec

- `audits/acp_sap_challenges.jsonl` optional
- CLI or tool: challenge job_id with demand `pytest …` or `invariant`
- Satisfaction = later receipt audit row matching demand (heuristic ok for v0)
- Max depth 1 in v0 (no challenge chains)

### Prefer Devin for multi-file; Grok for parse/tool stub.

### Acceptance

Challenge append + status line on `job status` optional field.

**Skip** if SAP-1..3 dogfood is enough for first public note.

---

## SAP-5 — Publish gate (docs only)

**Goal:** Freeze public narrative only after local dogfood.

### Checklist

- [ ] SAP-1..3 on operator machine once
- [ ] No identity matrix regression
- [ ] Edit `docs/publish/sap-sealed-agent-jobs-qortroller-buzz.md` “Status” to **reference-ready**
- [ ] Optional: wiki mirror / X thread from that file — **no** overclaim grades

### Owners

Operator + Grok copy-edit; Devin only if link/CI path automation requested.

---

## PR template (copy into each SAP PR)

```markdown
## SAP WP
- [ ] SAP-N title

## Rails
- [ ] @EA only face
- [ ] shell=False / allow-list
- [ ] job_id additive only
- [ ] no auto-seal from harness
- [ ] no VSS OPEN / chain
- [ ] PV-CI PASS
- [ ] tests listed

## Mapping
Job / Receipt / Seal touched: …
```

---

## Out of scope for these WPs

- Nostr-native SAP kinds
- ZK receipts
- Multi-operator seals
- Sentry/Guardian/Curator as SAP peers on Buzz
- Replacing webhook or Phase 1 bot

---

**End of SAP Grok × Devin Work Packages**
