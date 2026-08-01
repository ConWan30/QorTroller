# Buzz Workflow / Agent Import — Integration Proposal (v0)

**Status:** PROPOSAL — design note for a future Buzz agent/workflow feature.  
**Parents:**
- `docs/design/buzz-ea-acp-harness-integration-v0.md`
- `docs/design/buzz-phase4-acp-gateway-runbook.md`
- `docs/design/buzz-qortroller-gamer-mvp-v0.md` §4 (ACP for EA ops)

**Scope:** how an external Buzz agent, workflow, or LLM orchestrator imports the `@EA` tool surface without multiplying community identities.

---

## 1. Problem statement

Buzz may add a "projects" or "workflow" feature that lets operators create automated agents. The risk is that every new agent becomes a new community identity, breaking the identity map and the claim discipline. This proposal describes a single import surface that reuses `@EA` as the community face and the existing ACP gateway as the control plane.

## 2. Non-negotiable identity boundary

| Entity | Buzz identity? | Role |
|---|---|---|
| `@EA` | **Yes** — the only published bot | Digests, status, tool results, plan confirmations |
| Buzz workflow / external LLM | **No** | Harness / orchestrator that drives `@EA` through the gateway |
| Operator | Yes, member | Authorizes agent pubkeys, merges, ceremonies |
| Grok / Devin | No | Existing harnesses for fast and queued work |

A Buzz agent is **not** a new `@something` in the channel. It is an operator-authorized caller of the ACP gateway.

## 3. Import contract

Any external agent (Buzz workflow, MCP server, local LLM, CI hook) has three integration options:

### 3.1 Event-driven — agent posts through `@EA`

```text
Buzz workflow
  -> writes Nostr event to #rig-ops as @EA (via qortroller_buzz_bot publish path)
  -> qortroller_buzz_bot polls
  -> qortroller_acp_gateway.handle_message(pubkey, content, cfg)
  -> reply published as @EA
```

The workflow must use the same `qortroller_buzz_bot._publish_event` path. It never signs an event with its own key.

### 3.2 Programmatic — MCP tool surface

```text
External process
  -> scripts/qortroller_acp_mcp_server.py (or direct import)
  -> POST /mcp/tools/ask_ea {pubkey, content}
  -> (content, tags) returned
  -> workflow decides whether to publish as @EA
```

This is useful for Claude, Cursor, or any MCP-aware coding agent. The server and the webhook both route through the same `handle_message` call.

### 3.3 File-driven — agent watches queue / plan files

```text
Buzz workflow
  -> reads audits/acp_devin_queue.jsonl
  -> opens Devin session with repo_sha_hint + topic
  -> writes result back to local file only
  -> optional: asks @EA to post a digest
```

The file surfaces are the canonical sync points; no API key for Grok or Devin is required in the gateway.

## 4. Agent capabilities vs. authority

A Buzz agent can invoke anything in `ALLOWED_TOOLS`, including the ACP-3 `plan`/`confirm` flow. It **cannot**:

- commit, push, merge
- spend chain funds or sign transactions
- open a VSS seat (gamer-key only)
- run shell commands outside the fixed-argv allow-list
- publish as anything other than `@EA`

## 5. Authorization model

For an external agent to drive `@EA`, its caller pubkey must be added to `ACP_OPERATOR_PUBKEYS`. This keeps the existing fail-closed operator allow-list. The agent may hold its own key pair, but it is still an operator-authorized harness, not a community member.

## 6. Suggested workflow: strategic engineering tasks

A typical Buzz agent flow under this contract:

1. **Trigger:** a new commit, an alert, or a scheduled cadence wakes the workflow.
2. **Observe:** agent calls `@EA repo health` and `@EA failing` to get a digest.
3. **Plan:** agent calls `@EA plan investigate <topic>` to stage a Devin ticket.
4. **Operator go/no-go:** a human says `@EA confirm plan <id>`, or the workflow itself calls `handle_message` with an operator-signed event.
5. **Execute:** the gateway runs the plan steps; Devin steps land in the queue.
6. **Report:** `@EA` posts a bounded digest of what happened.

## 7. Implementation options

| Option | Status | When |
|---|---|---|
| A — Webhook adapter | **Shipped** | `scripts/qortroller_buzz_webhook.py` — `POST /buzz` |
| B — MCP server wrapper | **Shipped** | `scripts/qortroller_acp_mcp_server.py` — `/mcp/tools/ask_ea` |
| C — Buzz-native bot plugin | Future | Wait for Buzz to expose an agent SDK and implement a thin adapter |

Both A and B reuse the same `qortroller_acp_gateway.handle_message` path. Option C is a future rewrite when the Buzz SDK is stable.

## 8. Acceptance criteria

- Single community face remains `@EA`.
- External agents authenticate through `ACP_OPERATOR_PUBKEYS` or a dedicated agent-allow-list.
- All agent commands are fixed-argv, `shell=False`, and digest-only.
- Queue and plan files remain the hand-off surface for Devin.
- No chain spend, no gamer key, no VSS OPEN, no auto-merge.

## 9. Relation to roadmap

- ACP-1 (structured Devin queue) is the file hand-off.
- ACP-2 (engineering read tools) is the information surface an agent consumes.
- ACP-3 (plan/confirm) is the go/no-go orchestration primitive.
- This proposal is the **import contract** that lets external agents use those three without inventing a second community bot.

---

**End of Buzz Workflow / Agent Import Proposal (v0)**
