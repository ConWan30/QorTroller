# EA ACP Harness — Integration Contract & Engineering-Assistant Roadmap (v0)

**Status:** DESIGN — integration contract for Devin + phased EA capability growth  
**Date:** 2026-08-01  
**Parents:**
- `docs/design/buzz-phase4-acp-grok-devin-addendum.md`
- `docs/design/buzz-phase4-acp-gateway-runbook.md`
- `docs/design/buzz-phase4-ops-acceptance-checklist.md`
- `docs/design/buzz-vss-stream-seat-scope-v0.md`

**Code truth:** `scripts/qortroller_acp_gateway.py` (gateway), `scripts/qortroller_buzz_bot.py` (Phase 1–3 house radio)  
**Harnesses:** Grok Build (primary) · Devin (heavy / queued)  
**Community face:** single bot `@EA` only — harnesses are **not** Buzz members

---

## 0. Purpose

1. Give **Devin** a single, attackable integration contract so ACP work lands without inventing a second Buzz identity.
2. Define how **EA becomes a stronger engineering assistant** while remaining:
   - one community bot (`role=bot`)
   - allow-listed tools only (`shell=False`)
   - operator-authorized (fail-closed allow-list)
   - digest-only on Nostr
   - **no** commit, spend, gamer-key, or VSS OPEN authority

**Product intent (honest):** EA should feel like a competent **rig + repo ops assistant** in `#rig-ops`, not a free-form chat LLM and not a gamer substitute.

---

## 1. Identity map (non-negotiable)

| Name | Plane | Create in Buzz? | Authority |
|------|--------|-----------------|-----------|
| **EA (`@EA`)** | Social (Buzz) | **Yes** — only community bot | Publish digests; surface ACP; never gamer/OPEN/spend |
| **Grok Build** | ACP harness | **No** | Execute allow-listed fixed-argv tools |
| **Devin** | ACP harness + external session | **No** | Queue heavy work; operator invokes; operator merges |
| **Operator** | Human | Member + `ACP_OPERATOR_PUBKEYS` | Sole commit / spend / ceremony / merge |
| **Sentry / Guardian / Curator** | Protocol fleet (O3) | **No** | Protocol lanes; optional future digest via EA only |
| **Gamer** | Human | Member | Own key for VSS OPEN |

```text
Operator  --@EA cmd-->  EA (Buzz npub)
                           |
                      ACP gateway
                      /          \
               Grok Build      Devin queue
               (default)       (diagnose / heavy)
                      \          /
                       digests back as EA
```

Devin **integrates code and queue consumers**. Devin does **not** become a second `@Devin` in the community.

---

## 2. Landed gateway contract (what Devin must preserve)

### 2.1 Pipeline (do not reorder semantics)

```text
handle_message(pubkey, content, cfg)
  parse_mention   → None | Intent | Rejection
  authorize       → fail-closed if ACP_OPERATOR_PUBKEYS empty or pubkey missing
  route(tool)     → grok-build | devin
  execute         → TOOL_IMPLS[tool]  # fixed argv, shell=False
  format_reply    → scrub + length cap + [acp,1] [harness,…] tags
  audit           → audits/acp_gateway.jsonl (gitignored)
```

Publish path: **Architecture C** via `qortroller_buzz_bot._publish_event` (Rust helper). Gateway never signs Nostr itself.

### 2.2 Allow-listed tools (current code)

| Tool id | Typical mention | Harness |
|---------|-----------------|---------|
| `run_pytest` | `@EA run pytest <path>` | Grok (or Devin if `@EA devin run pytest …`) |
| `run_invariant_gate` | `@EA invariant status` | Grok |
| `get_rig_status` | `@EA status` / `rig status` | Grok-only |
| `get_session_summary` | `@EA session [id]` | Grok |
| `list_ceremony_steps` | `@EA ceremony steps` | Grok-only |
| `health_check` | `@EA health` | Grok-only |
| `deep_diagnose` | `@EA diagnose <topic>` | **Devin-only** (queue) |
| `get_stream_seat_status` | `@EA seat` / `vss` | Grok-only |
| `summarize_stream_seat` | `@EA summarize seat` | Grok-only |
| `flag_stream_seat_down` | `@EA flag seat down` | Grok-only |
| `get_stream_verify_pointer` | `@EA verify pointer` | Grok-only |
| `get_organizer_pilot_status` | `@EA organizer pilot` | Grok-only |

**Pytest roots only:** `bridge/tests`, `sdk/tests`, `tests`, `autoresearch/tests` (existing path, no `..`, no shell metacharacters).

### 2.3 Hard bans (must stay)

Shell/exec · wallet/nsec · deploy/gas/spend/sign-tx · raw HID/IMU/L4/frames/PoAC · git push/commit/merge from gateway.

### 2.4 Devin queue contract (seamless hand-off)

`deep_diagnose` **appends** one JSONL record and replies honestly:

```json
{
  "ts": 0,
  "harness": "devin",
  "tool": "deep_diagnose",
  "topic": "<operator text ≤200 chars>",
  "status": "queued"
}
```

Path: `audits/acp_devin_queue.jsonl` (env `ACP_DEVIN_QUEUE` override).

**Devin integration rules:**

1. **Never** post to Buzz as Devin or forge EA replies that claim “Devin said … result …” without operator mediation.
2. Consumer may: watch the queue file, open a Devin session on topic + repo SHA, produce a PR.
3. **Operator** merges; gateway does not auto-apply patches.
4. Optional later: `status: done` + `pr_url` written **back** to a separate local file for operator eyes — still not auto-published as protocol truth.

### 2.5 Env surface (operator machine)

```ini
# EA bot (Buzz)
BUZZ_PRIVATE_KEY=<ea-bot-secret>
BUZZ_AUTH_TAG=["auth",...]
BUZZ_RELAY_URL=ws://127.0.0.1:3000
BUZZ_CHANNEL_IDS=<rig-ops>,<matches-optional>
BUZZ_HELPER_PATH=<qortroller-buzz binary>

# ACP
ACP_BOT_HANDLE=@EA
ACP_RIG_OPS_CHANNEL_ID=<rig-ops-uuid>
ACP_OPERATOR_PUBKEYS=<operator-hex>
ACP_DRY_RUN=0
ACP_AUDIT_LOG=audits/acp_gateway.jsonl
ACP_DEVIN_QUEUE=audits/acp_devin_queue.jsonl
BRIDGE_BASE_URL=http://localhost:8000
```

Preflight: `python scripts/qortroller_acp_gateway.py --preflight`  
Eval: `python scripts/qortroller_acp_gateway.py --eval "@EA health"`

### 2.6 Processes (two, not one)

| Process | Role |
|---------|------|
| `qortroller_buzz_bot.py` | Autonomous status + postcards + `!status`/`!ready`/`!session` |
| `qortroller_acp_gateway.py` | `@EA` tool desk + Grok/Devin routing |

Both may share EA key and `#rig-ops`. Do not merge into one process unless a dedicated WP proves no regression on poll/prefix separation.

---

## 3. “Smarter / more agentic EA” — what that means here

### 3.1 Allowed meaning

EA becomes a better **engineering assistant** by:

- richer **allow-listed** tools (repo facts, test selection, log tails with scrubbing, work-package checklists)
- **multi-step plans** that still end in operator “go / no-go”
- tighter **queue protocol** with Devin (structured tickets, acceptance criteria)
- better **digests** (what failed, which file, next human step) — still bounded and scrubbed

### 3.2 Forbidden meaning

| Anti-goal | Why |
|-----------|-----|
| Free-form LLM replies as protocol truth | Claim / honesty collapse |
| Auto `git commit` / `push` / merge | Operator sole merge |
| Auto chain spend | Ceremony rails |
| VSS OPEN as EA | Gamer key only; VSS-7 |
| Raw substrate in channel | Privacy + bus rules |
| Impersonating Devin results on Nostr | Identity matrix |
| Grok/Devin as Buzz agents | Harness ≠ community member |

**Agentic ≠ autonomous authority.** Agentic = better routing, planning, and tool use **under** operator authority.

---

## 4. Roadmap — EA engineering assistant (phased WPs)

Each WP is Devin-integrable: single PR class, tests, no FROZEN/chain, claim-safe copy.

### EA-ACP-0 — Contract freeze (this doc)

**Acceptance:** Operator ack; Devin uses this file as source of truth for ACP changes.

### EA-ACP-1 — Structured Devin tickets (seamless hand-off)

**Goal:** Queue records become actionable tickets, not one-line topics.

Extend queue JSON (additive fields only):

```json
{
  "ts": 0,
  "harness": "devin",
  "tool": "deep_diagnose",
  "topic": "…",
  "status": "queued",
  "repo_sha_hint": "optional",
  "acceptance": "optional short string",
  "priority": "normal"
}
```

Optional companion: `scripts/acp_devin_queue_watch.md` or a tiny watcher that prints new rows for the operator/Devin session.

**Acceptance:** `@EA diagnose …` still replies “queued…”; new fields optional;  tests for JSON shape; no Buzz identity for Devin.

### EA-ACP-2 — Engineering read tools (Grok-primary)

Add **fixed-argv** tools only (examples — each needs its own allow-list + tests):

| Tool | Intent example | Behavior |
|------|----------------|----------|
| `list_failing_tests` | `@EA failing tests` | Run a pinned pytest collect/last-failed summary if artifact exists; else honest “no cache” |
| `repo_health` | `@EA repo health` | Compose existing health + PV-CI one-liner |
| `show_wp_status` | `@EA wp vss` | Read **design/runbook headings only** from known paths under `docs/` (path allow-list) |

**Acceptance:** path traversal impossible; scrubbing on; Grok-only unless explicitly heavy.

### EA-ACP-3 — Plan-then-confirm (agentic, not autonomous)

New intent pattern:

```text
@EA plan <goal>
→ reply: numbered plan (≤ N steps), no execution
@EA confirm plan <id>   # operator only
→ runs only pre-declared allow-listed tools from the plan registry
```

Until `confirm`, **nothing** mutates repo or queue beyond writing a local plan file under `audits/` (gitignored).

**Acceptance:** no tool runs on `plan` alone; `confirm` refuses unknown plan ids; audit both.

### EA-ACP-4 — Devin result bridge (operator-mediated)

Local file `audits/acp_devin_results.jsonl`:

```json
{"ts":0,"topic":"…","status":"done","pr_url":"https://github.com/…/pull/N","summary":"…"}
```

Optional: `@EA diagnose status` reads **last N local results** and posts a **digest** (PR URL + one line). Still not “Devin speaks on Nostr.”

**Acceptance:** missing file → honest empty; scrub URLs; no auto-merge.

### EA-ACP-5 — Context pack for Devin (offline)

Script (operator/Devin runs, not required on Nostr):

`scripts/acp_devin_context_pack.py --topic "…"`

Emits a markdown bundle: relevant docs paths, recent queue row, `git rev-parse HEAD`, test commands. **No secrets.**

**Acceptance:** dry-run safe; used in Devin session open; not published by EA unless operator pastes.

### Out of roadmap (explicit)

- LLM-generated unbounded chat as EA voice without tool grounding  
- Steward fleet (Sentry/Guardian/Curator) as three Buzz bots  
- Gamer coach agent using ACP on operator allow-list without separate design  

---

## 5. Devin implementation checklist (copy into PR body)

When changing ACP / EA assistant behavior:

- [ ] Single community face remains `@EA` (no new Buzz agent profiles)
- [ ] New capabilities are **named tools** in `ALLOWED_TOOLS` + `TOOL_IMPLS` + parse tests
- [ ] `shell=False`; no operator string on a shell command line
- [ ] Pytest/doc paths allow-listed and resolved under `REPO_ROOT`
- [ ] Grok vs Devin routing updated deliberately (`GROK_ONLY_TOOLS` / `DEVIN_ONLY_TOOLS`)
- [ ] `deep_diagnose` still queues; never impersonates Devin results as live tool output unless EA-ACP-4
- [ ] Replies go through `format_reply` / `scrub`; `MAX_REPLY_CHARS` honored
- [ ] Audit JSONL written; secrets never logged in clear
- [ ] Tests in `bridge/tests/test_qortroller_acp_gateway.py` (or sibling) green
- [ ] `python scripts/vapi_invariant_gate.py` still PASS (no baseline games)
- [ ] No FROZEN wire, commitment, or chain writes
- [ ] Claim language: ACP output is G0 repo/ops statement, not population evidence

---

## 6. How the operator should *feel* EA after the roadmap

| Today | After EA-ACP-1…4 |
|-------|------------------|
| Status + fixed tools + “queued for Devin” | Same, plus structured tickets and plan/confirm |
| Engineering help is mostly outside chat | Chat can **stage** engineering work; humans/Devin **execute** under rails |
| EA is a steward reporter | EA is a steward **ops engineer’s assistant** — still not the engineer of record |

You remain the engineer of record. EA gets sharper tools and clearer Devin synchronization; it does not get your merge key.

---

## 7. Relationship to other agents

| Agent | Relation to this doc |
|-------|----------------------|
| Phase 1–3 bot | Unchanged house radio; ACP stays separate process unless a later WP merges carefully |
| VSS tools | Already on gateway; keep Grok-only; never OPEN |
| Operator Initiative stewards | Not Buzz agents; optional future `@EA fleet status` digest only |
| Grok / Devin | Harnesses only; integrate via this contract |

---

## 8. Greenlight

Devin may implement **EA-ACP-1** after operator ack of this document.  
**EA-ACP-2+** require a one-line operator greenlight per WP (tool list + acceptance).

---

**End of EA ACP Harness Integration & Engineering-Assistant Roadmap (v0)**
