# SAP × QorTroller × Buzz — Integration Framework (v0)

**Status:** DESIGN — maps Sealed Agent Protocol onto **landed** EA/ACP/VSS code  
**Date:** 2026-08-01 (handoff refresh)  
**HEAD context:** main includes **PR #123 MCP** (`ask_ea` → `handle_message`) after EA-ACP-1..5 + webhook (#118–#122)  
**Parents:**
- `docs/design/buzz-ea-acp-harness-integration-v0.md`
- `docs/design/buzz-phase4-acp-grok-devin-addendum.md`
- `docs/design/buzz-ea-agent-import-proposal.md` (Options A+B **shipped**)
- `docs/design/sap-grok-devin-work-packages.md` ← **Devin implements from here**

**Non-goals:** ZK, new Buzz agent identities, chain spend, VSS OPEN via SAP, global A2A standard theater.

---

## Handoff (read first)

| Question | Answer |
|----------|--------|
| Conflict with recent merges? | **No.** MCP/webhook are additional **clients**; they do not fork the gateway. |
| Integration style | **Additive** fields + small scripts/tools on existing JSONL / `handle_message` |
| First code WP | **SAP-1** (`job_id`) — see work-packages doc |
| Do not touch | VSS OPEN path, chain, FROZEN, second Buzz bot identity |

```text
@EA chat  ─┐
Webhook   ─┼─→  qortroller_acp_gateway.handle_message  →  execute / queue / plans
MCP ask_ea─┘
```

Any SAP tool added to the gateway is available on **all three** clients automatically.

---

## 0. Recent stage (why SAP is thin, not greenfield)

### Merged 2026-08-01 (representative)

| PR | What landed | SAP reading |
|----|-------------|-------------|
| #118 EA-ACP-1 | Structured Devin queue tickets + `repo_sha_hint` | **Job** stub + acceptance |
| #119 EA-ACP-2 | failing tests / repo health / wp status | **Receipt** generators |
| #120 EA-ACP-3 | `@EA plan` / `confirm plan` | Plan = unsealed job; confirm = execute |
| #121 EA-ACP-4/5 | Devin results JSONL + context pack | **Claim/receipt** from harness; offline pack |
| #122 webhook | `POST /buzz` → `handle_message` | External ACP client |
| **#123 MCP** | `POST /mcp/tools/ask_ea` → `handle_message` | **Machine ACP client** (Option B) |
| #112–#117 VSS | Live dogfood, F2, S1–S5, anti-farm | **Separate** gamer plane (not SAP authority) |

**PV-CI:** 188. **Identity:** single `@EA` face. Grok primary / Devin queued. Operator allow-list fail-closed.

SAP does **not** replace this stack. It **names the lifecycle** and adds minimal **`job_id` / seal / job status** instrumentation.

---

## 1. SAP in one paragraph (QorTroller use case)

**Sealed Agent Protocol (SAP)** here means: operator-driven agent work is a **Job**; tools emit **Receipts**; peers may **Challenge**; only the **operator Seal** (merge, confirm completion, or explicit accept) makes the work product binding; Buzz carries **Digests** only.

```text
Operator --@EA / webhook / MCP--> Face (EA / ACP gateway)
                                    |
                               Job (+ plan)
                                    |
                    Grok receipts  +  Devin queue/results
                                    |
                          optional Challenge
                                    |
                          Operator Seal (merge / sap_seal.py)
                                    |
                          Digest in #rig-ops (optional)
```

---

## 2. Object map → existing files

| SAP object | Landed instrument | Path / command |
|------------|-------------------|----------------|
| **Job open** | `@EA diagnose …` queue row; `@EA plan …` | `audits/acp_devin_queue.jsonl`, `audits/acp_plans.jsonl` |
| **Job id** | *(missing — SAP-1)* | Stable `job_id` on queue/plan/audit/results |
| **Receipt** | Tool audit row; pytest/PV-CI/health | `audits/acp_gateway.jsonl` |
| **Claim** | Devin result summary / PR pointer | `audits/acp_devin_results.jsonl` via `acp_devin_result_record.py` |
| **Challenge** | Follow-up `@EA` / MCP tool call | Re-exec pytest / invariant |
| **Seal** | Operator merge; **SAP-2** local log | `scripts/sap_seal.py` → `audits/acp_sap_seals.jsonl` |
| **Digest** | EA reply / diagnose status / **job status** | `#rig-ops` or client JSON |
| **Context pack** | Offline Devin bundle | `scripts/acp_devin_context_pack.py` |
| **Clients** | Chat, webhook, MCP | All call `handle_message` |

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

1. **Additive fields only** on existing JSONL (`job_id`, seal, optional challenge_id).  
2. **No second gateway.** Chat / webhook / MCP all use `handle_message` / `execute`.  
3. **Seal is never automatic** from Grok/Devin/MCP.  
4. **Buzz remains digest plane.**  
5. **VSS stays orthogonal** (eligibility receipts allowed; OPEN not a SAP seal).  
6. **Publishing** only after SAP-1..3 dogfood (`docs/publish/sap-sealed-agent-jobs-qortroller-buzz.md`).

---

## 5. Target operator flows (after SAP-1..3)

### Flow A — Diagnose → Devin → Seal

```text
@EA diagnose capture lag | acceptance: lag < 50ms | priority high
  → Job open (queue + job_id)
Devin works; acp_devin_result_record.py --job-id … --status done --pr-url …
@EA diagnose status   # or @EA job status sap_…
  → Digest (not auto-seal)
Operator merges PR
  → python scripts/sap_seal.py --job-id … --accept --ref <pr>
```

Same text can be sent via **webhook** or **MCP `ask_ea`** with the operator pubkey.

### Flow B — Plan / confirm (EA-ACP-3)

```text
@EA plan full check
@EA confirm plan <id>
  → Receipts per step; product seal still human for ship/merge
```

### Flow C — Challenge

```text
@EA run pytest bridge/tests/…
  → Receipt satisfies or fails “tests green”
```

---

## 6. Work package index

**Implement:** `docs/design/sap-grok-devin-work-packages.md`

| WP | Intent | Depends |
|----|--------|---------|
| **SAP-0** | Design + publish draft | done |
| **SAP-1** | `job_id` on queue, plans, audit, results | EA-ACP-1..5 + #122/#123 |
| **SAP-2** | `scripts/sap_seal.py` | SAP-1 |
| **SAP-3** | `@EA job status <job_id>` (inherits MCP/webhook) | SAP-1..2 |
| **SAP-4** | Optional challenge JSONL | optional |
| **SAP-5** | Public note → reference-ready | SAP-1..3 dogfood |

---

## 7. Acceptance for “SAP integrated”

- [ ] Every diagnose queue row has `job_id`
- [ ] Result records can reference `job_id`
- [ ] Operator can append seal without Buzz publish
- [ ] `@EA job status` shows job → results → seal
- [ ] Webhook + MCP still only wrap `handle_message` (no duplicate tool impl)
- [ ] No new Buzz bots; PV-CI PASS; VSS OPEN unchanged
- [ ] Claim language: ops/process only, not population evidence

---

## 8. Public narrative

Internal: SAP = lifecycle discipline on ACP.  
Public: `docs/publish/sap-sealed-agent-jobs-qortroller-buzz.md` after dogfood — narrow use case, not world standard.

---

**End of SAP × QorTroller × Buzz Integration Framework (v0)**
