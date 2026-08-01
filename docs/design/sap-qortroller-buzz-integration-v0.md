# SAP × QorTroller × Buzz — Integration Framework (v0)

**Status:** DESIGN — maps Sealed Agent Protocol onto **landed** EA/ACP/VSS code  
**Date:** 2026-08-01  
**HEAD context:** main @ `2a78d92` (PR #122 webhook) after EA-ACP-1..5  
**Parents:**
- `docs/design/buzz-ea-acp-harness-integration-v0.md`
- `docs/design/buzz-phase4-acp-grok-devin-addendum.md`
- `docs/design/buzz-ea-agent-import-proposal.md`

**Non-goals:** ZK, new Buzz agent identities, chain spend, VSS OPEN via SAP, global A2A standard theater.

---

## 0. Recent stage (why SAP is thin, not greenfield)

### Merged 2026-08-01 (representative)

| PR | What landed | SAP reading |
|----|-------------|-------------|
| #118 EA-ACP-1 | Structured Devin queue tickets + `repo_sha_hint` | **Job** stub + acceptance |
| #119 EA-ACP-2 | failing tests / repo health / wp status | **Receipt** generators |
| #120 EA-ACP-3 | `@EA plan` / `confirm plan` | Plan = unsealed job; confirm = execute |
| #121 EA-ACP-4/5 | Devin results JSONL + context pack | **Receipt/claim** from harness; offline pack |
| #122 webhook | `POST /buzz` → `handle_message` | External ACP client, same rails |
| #112–#117 VSS | Live dogfood, F2 bind, S1–S5, anti-farm | **Separate** gamer plane (not SAP authority) |

**PV-CI:** 188. **Identity:** single `@EA` face. Grok primary / Devin queued. Operator allow-list fail-closed.

SAP does **not** replace this stack. It **names the lifecycle** already emerging and adds minimal **job_id / seal** instrumentation so Grok and Devin share one vocabulary.

---

## 1. SAP in one paragraph (QorTroller use case)

**Sealed Agent Protocol (SAP)** here means: operator-driven agent work is a **Job**; tools emit **Receipts**; peers may **Challenge**; only the **operator Seal** (merge, confirm completion, or explicit accept) makes the work product binding; Buzz carries **Digests** only.

```text
Operator --@EA / webhook--> Face (EA / ACP gateway)
                              |
                         Job (+ plan)
                              |
              Grok receipts  +  Devin queue/results
                              |
                    optional Challenge
                              |
                    Operator Seal (merge / record done)
                              |
                    Digest in #rig-ops (optional)
```

---

## 2. Object map → existing files

| SAP object | Landed instrument | Path / command |
|------------|-------------------|----------------|
| **Job open** | `@EA diagnose …` queue row; `@EA plan …` | `audits/acp_devin_queue.jsonl`, `audits/acp_plans.jsonl` |
| **Job id** | ticket / plan_id / ts | Add stable `job_id` in SAP-1 |
| **Receipt** | Tool audit row; pytest/PV-CI/health summaries | `audits/acp_gateway.jsonl` |
| **Claim** | Devin result summary / PR pointer | `audits/acp_devin_results.jsonl` via `acp_devin_result_record.py` |
| **Challenge** | Follow-up `@EA` tool or new diagnose | Re-exec pytest / invariant |
| **Seal** | Operator merge; optional `status: sealed` result row | Human; CLI in SAP-2 |
| **Digest** | EA reply `[grok-build]…` / diagnose status | `#rig-ops` kind 9 |
| **Context pack** | Offline Devin bundle | `scripts/acp_devin_context_pack.py` |
| **External client** | Webhook | `scripts/qortroller_buzz_webhook.py` |

**Out of SAP:** `buzz_vss_seat.py` OPEN (gamer key), chain ceremony, O3 stewards as Buzz bots.

---

## 3. Role map (unchanged authority)

| Role | QorTroller binding |
|------|--------------------|
| Client / Authority | Operator pubkey in `ACP_OPERATOR_PUBKEYS` |
| Face | EA bot + `qortroller_acp_gateway.py` |
| Harness (fast) | Grok Build tools |
| Harness (heavy) | Devin via queue + result record |
| Peer / auditor | Optional second harness or human review |
| Observer | Buzz members reading digests |

---

## 4. Seamless integration principle

1. **Additive fields only** on existing JSONL (job_id, seal, challenge_id).  
2. **No second gateway.** All paths still `handle_message` / `execute`.  
3. **Seal is never automatic** from Grok/Devin.  
4. **Buzz remains digest plane.**  
5. **VSS stays orthogonal** (eligibility receipts allowed; OPEN not a SAP seal).  
6. **Publishing** only after a boring reference path exists (see `docs/publish/…`).

---

## 5. Target operator flows (after SAP-1..3)

### Flow A — Diagnose → Devin → Seal

```text
@EA diagnose capture lag | acceptance: lag < 50ms | priority high
  → Job open (queue + job_id)
Devin works; acp_devin_result_record.py --status done --pr-url …
@EA diagnose status
  → Digest of results (not auto-seal)
Operator merges PR
  → sap_seal.py --job <id> --accept --ref <pr>
```

### Flow B — Plan / confirm (already EA-ACP-3)

```text
@EA plan full check
@EA confirm plan <id>
  → Receipts per step
  → Still not “product sealed” until operator says so for ship/merge
```

### Flow C — Challenge

```text
Claim: tests green
@EA run pytest bridge/tests/…
  → Receipt satisfies or fails challenge
```

---

## 6. Work package index

Detailed Grok/Devin instruments: **`docs/design/sap-grok-devin-work-packages.md`**.

| WP | Intent | Depends |
|----|--------|---------|
| **SAP-0** | This integration doc + publish draft | — |
| **SAP-1** | `job_id` on queue, plans, audit, results | EA-ACP-1..5 |
| **SAP-2** | `scripts/sap_seal.py` local seal log | SAP-1 |
| **SAP-3** | `@EA job status <job_id>` digest | SAP-1..2 |
| **SAP-4** | Optional challenge record file | SAP-1 |
| **SAP-5** | Public note freeze after dogfood | SAP-1..3 live |

---

## 7. Acceptance for “SAP integrated”

- [ ] Every diagnose queue row has `job_id`
- [ ] Result records can reference `job_id`
- [ ] Operator can append seal without Buzz publish
- [ ] `@EA job status` (or diagnose status enriched) shows job → results → seal
- [ ] No new Buzz bots; PV-CI still PASS; VSS OPEN unchanged
- [ ] Claim language: ops/process only, not population evidence

---

## 8. Relationship to public narrative

Internal truth: SAP is a **lifecycle discipline on ACP**.  
Public truth: see `docs/publish/sap-sealed-agent-jobs-qortroller-buzz.md` — publish **after** SAP-1..3 dogfood, as a narrow use case, not a world standard.

---

**End of SAP × QorTroller × Buzz Integration Framework (v0)**
