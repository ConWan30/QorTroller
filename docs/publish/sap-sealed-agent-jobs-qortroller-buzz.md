# Sealed Agent Jobs on a Community Relay
## A QorTroller × Buzz use case (public note)

**Status:** REFERENCE-READY — SAP-1..4 implemented and unit-tested; operator machine dogfood recommended before public thread  
**Project:** [QorTroller](https://github.com/ConWan30/QorTroller)  
**Community plane:** Buzz (Nostr-based workspace)  
**Audience:** builders of operator agents, Nostr/Buzz communities, agent harness authors  
**Not claiming:** universal A2A standard, ZK agent cognition, tournament-grade proof, auto-merge bots

---

### The problem

Teams put coding agents in the same rooms as humans. Useful — until:

- the bot’s chat message is treated as “done,”
- two harnesses blur into one identity,
- or a shell-from-chat shortcut becomes the real API.

QorTroller’s operator surface had the opposite requirement: **proof and spend stay human-gated**, digests stay honest, and agents help **without** becoming the authority.

---

### The pattern: sealed agent jobs (SAP)

We name a thin lifecycle on top of an allow-listed agent gateway:

1. **Job** — operator opens work (`@EA diagnose …`, or a staged plan).  
2. **Receipts** — fixed tools run (tests, invariant gate, health, seat *status* reads).  
3. **Claims** — heavy harness (Devin) records results locally (e.g. PR URL), without impersonating the community bot.  
4. **Seal** — operator merge / explicit local seal — not the model’s final paragraph.  
5. **Digest** — Buzz/`@EA` posts short scrubbed status, not full logs or raw device data.

Call it **SAP (Sealed Agent Protocol)** if you want a handle. The substance is the lifecycle, not the acronym.

```text
Human operator  →  Face bot (@EA)  →  Harnesses (Grok / Devin)
                         ↑                    ↓
                      digests              receipts / queue
                         ↑                    ↓
                      Seal is human (merge, accept, hold)
```

---

### Why Buzz (and not “agents on the video pipe”)

Buzz is a **membership community + signed events**. It is a strong **coordination and digest** plane. It is a weak place to put gameplay frames or unbounded agent memory.

QorTroller keeps:

- **Truth** on the local bridge and verifiers,  
- **Ops agents** on an allow-listed gateway behind one bot face,  
- **Gamer live seats (VSS)** on a separate path: humans OPEN, agents may only view.

Sealed jobs apply to **operator engineering and live-ops checks**, not to “the bot is the streamer.”

---

### What we actually run

| Piece | Role |
|-------|------|
| `@EA` | Single community face (`role=bot`) |
| ACP gateway | Parse → authorize → route → fixed-argv tools → digest |
| Grok Build | Fast receipts (pytest, PV-CI, health, plan confirm steps) |
| Devin | Queued heavy work; results recorded offline; human merges |
| Webhook adapter | Optional machine client into the **same** gateway |
| MCP `ask_ea` | Machine client into the **same** gateway |
| `scripts/sap_seal.py` | Operator-only local seal log; no auto-publish |
| `challenge job <id> <demand>` | Lightweight challenge record; max depth 1 |
| `job status <id>` | Queue → results → seal digest |
| Allow-list | Empty operator pubkey list ⇒ nothing runs |

Agents do not gain commit, chain spend, or gamer seat OPEN from this surface.

---

### Challenge without theater

A claim like “tests are green” is answered by **re-running the tool**, not by another bot voting. Policy violations (shell, spend, raw substrate) are **rejected by name** and audited locally.

That is the entire challenge philosophy for v0: **re-execution and evidence pointers**, then human seal.

---

### What this is good for

- Operator digests in a private or community ops channel  
- Staging engineering work to a heavy harness without a second chat persona  
- Preflight checklists (health, invariants, stream *eligibility* reads)  
- Keeping “done” aligned with **merge / accept**, not model confidence  

### What this is not

- A replacement for MCP tool schemas everywhere  
- A global multi-agent standard  
- Proof that a player is tournament-legal  
- Autonomous production deploy  

---

### Why publish a use case at all?

Because many “agent communities” skip the boring part: **authority separation**.  
If your bot can talk, people will treat talk as action. Sealed jobs make the missing step visible.

QorTroller × Buzz is one reference: cryptographic gaming protocol for the truth plane, Buzz for membership digests, sealed agent jobs for operator harnesses.

---

### Pointers

- Repo: https://github.com/ConWan30/QorTroller  
- Design: `docs/design/sap-qortroller-buzz-integration-v0.md`  
- EA/ACP contract: `docs/design/buzz-ea-acp-harness-integration-v0.md`  
- Buzz: open-source Nostr workspace (Block) — run your own relay or join a community  

---

### Suggested X / short post (optional)

> We don’t let coding agents “finish” work by sending a chat message.  
> On QorTroller’s Buzz ops channel, agents open **jobs**, tools leave **receipts**, and only a human **seal** (merge/accept) counts. One bot face. Allow-listed tools. Digests only.  
> Pattern: sealed agent jobs on a community relay — not autonomous authority.

---

**License of this note:** same as repo documentation practice; factual claims about the protocol remain subject to QorTroller claim register honesty rules.
