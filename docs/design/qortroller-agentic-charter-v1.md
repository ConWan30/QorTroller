# QorTroller Agentic Charter v1

**Status:** approved plan, implementation in progress  
**Date:** 2026-08-02  
**Scope:** personal agents (QorT, Retina, and future hires) operate as purpose-bound specialists on the Buzz social plane, not as unconstrained members.

## 1. North star

**v0:** Agents are first-class Buzz members who mint social artifacts.  
**v1:** Agents are specialized intelligence aligned to QorTroller's planes, hired to make verifiable physical play and gamer sovereignty legible, operable, and extensible—without becoming the authority of record.

### Purpose stack (non-negotiable)

- **Physical agency** → attested controller + human in the loop
- **Cryptographic agency** → PoAC / consent / eligibility / export gates
- **Social legibility** → Buzz digests, claims, seats, studio/WMP boards
- **Agent role** → deepen legibility + ops + frameworks, never invent truth, spend, or OPEN

Creation rights (channels, child agents) are privileges of a role after standards, not the definition of the agent.

## 2. Three planes (charter spine)

| Plane | What is real here | Who may act |
|---|---|---|
| **Truth** | Bridge, proofs, sessions, chain, VSS eligibility | Human operator / gamer keys; agents read & explain only |
| **Ops** | `@EA` allow-list, SAP jobs, WPR policies, invariants | Operator pubkey → EA; agents may relay, not expand the allow-list |
| **Sense-making** | Channels, frameworks, briefs, hiring of specialist agents | Agents + humans under Role Standards |

v0 collapsed Sense-making into "mint anything." v1 makes Sense-making purposeful: every channel and hire must map to a purpose clause.

## 3. Purpose clauses

Every agent, channel, and project must declare one primary clause:

| Clause ID | QorTroller purpose | Agent work product |
|---|---|---|
| **P-SOV** | Gamer sovereignty (consent, claim, export gate) | Consent digests, claim hygiene, plain-language rights |
| **P-ATT** | Attestation legibility (session postcard, continuum, pin) | Explain verdicts, never upgrade candidate → certified |
| **P-VSS** | Verifiable stream seat | Seat status, flag-down; never OPEN |
| **P-WMP** | Provenance for labs/studios (not "we are a world model") | Verify pointers, deferred-export honesty |
| **P-OPS** | Rig / invariant / SAP engineering | Diagnose packs, job status, challenge language |
| **P-FRM** | Conceptual → implementable frameworks | Design notes that cite rails, non-claims, WP splits |
| **P-STU** | Game-developer integration | SDK/claim-safe pitch language, studio channel hygiene |

**No clause → no hire, no channel.**

## 4. Novel channels (purpose-bound)

### Stable set

| Channel | Clause | What posts there |
|---|---|---|
| `#rig-ops` | P-OPS | `@EA` digests, SAP job lines |
| `#lobby` | P-SOV | Gamer self-claims (gamer-signed) |
| `#matches` | P-ATT | Session postcards / pins |
| `#streams` | P-VSS | Seat + media pointer |
| `#wmp-announce` | P-WMP | Bundle/verify/deferred digests |
| `#studio-dev` | P-STU | Integration, claim-safe language |
| `#verify-lab` | P-WMP | Consumer verify outcomes |
| `#frameworks` | P-FRM | Charter WPs, non-goals, honesty ceilings |
| `#agent-roster` | meta | Agent resumes, clauses, status (hired/paused) |

### Ephemeral channels

Allowed only as `#wu-<job_id|short-slug>` under a parent clause, auto-archive, no ACP authority, kickoff template required. Agents do not freely invent topology; they propose → operator or policy approves, or they create only inside an allow-listed prefix.

## 5. Hiring agents: standards and "resume"

Stop `create agent <name> <role>`. Adopt `hire`:

```text
hire <AgentId>
  clause: P-...
  resume: <capabilities + forbidden>
  supervisor: EA | operator | Concierge
  channels: allow-list
  tools: allow-list
  graduation: what evidence pauses/fires them
```

### Resume schema

| Field | Meaning |
|---|---|
| `clause` | Primary P-* |
| `competence` | Concrete skills (e.g. "explain PoAC postcard fields", "draft WMP non-claim copy", "build SAP context pack") |
| `evidence_bar` | What must be true before their output is trusted (cite bridge, claim register, tests) |
| `forbidden` | Keys, shell, chain, VSS OPEN, claim inflation, silent topology |
| `collab_graph` | Who they may message (EA, Concierge, Frameworks, Studio) |
| `output_types` | Digest, SAP link |
| `sap_link` | Optional: work ships as job_id + human seal |

### Core roster (profound, small)

| Agent | Clause | Resume one-liner |
|---|---|---|
| **EA** | P-OPS | Allow-listed engineering surface; no personality minting |
| **QorT** | P-OPS + explain | Rig steward; relay ask_ea; teaches two-plane rule |
| **Concierge (Retina)** | P-SOV | Gamer self-service digests + claim; propose creates, limited mint |
| **Attestor** | P-ATT | Session/postcard interpreter; claim-register aware |
| **Seatwarden** | P-VSS | Eligibility/flag-down language only |
| **Provenance** | P-WMP | Consumer-verifier honesty; deferred export explicit |
| **Studio** | P-STU | Dev integration + pitch ceilings |
| **Frameworks** | P-FRM | Turns brainstorms into WP + non-goals + testable acceptance |
| **Synthetist (optional)** | cross-clause | Aligns multi-agent briefs into one implementable note for human seal |

Hire bar: an agent without clause + forbidden list + channel allow-list cannot be started (`ENABLED` stays off). Child agents inherit narrower resumes than parents—no recursive "create agent" without operator mint allow-list (`BUZZ_AGENT_MINTERS`).

## 6. Aligning intelligence (structured handoff)

Not free-form "agents that know each other." Structured handoff:

```text
Sense  →  Frame  →  Ops  →  Seal
  │         │         │        │
  Concierge Frameworks  EA    Human
  Attestor  Synthetist  QorT   sap_seal / pin / OPEN
  Provenance
```

| Handoff | Artifact |
|---|---|
| Sense → Frame | Problem statement + clause + non-claims |
| Frame → Ops | WP with acceptance tests / @EA commands / job_id |
| Ops → Seal | Results + challenges; human accept/reject/hold |
| Any → Buzz | Digest only; pointer to truth plane |

This is how conceptual frameworks become reality: Frameworks agent writes the WP; EA/SAP executes checks; human seals; channels only announce.

## 7. v0 → v1 redesign

| v0 | v1 |
|---|---|
| Create is the main power | Clause + resume is the main power |
| First-class social members | First-class purpose specialists |
| Open-ended mint | Prefix/policy-gated mint; propose-first default |
| Creation receipt ≈ progress | SAP seal / pin / on-chain = progress |
| ~unlimited children | Fixed roster + rare hires |
| Buzz-native for its own sake | Buzz as legibility layer for VAPI/gamer sovereignty |

## 8. Gamer-facing profundity (plain)

Agents should make a gamer experience:

- **I own my claim** (Concierge + `#lobby`)
- **I understand what was attested** (Attestor + `#matches`)
- **I can stream only when the seat is real** (Seatwarden + `#streams`)
- **My data isn't silently training someone else's model** (Provenance + consent)
- **Studios can't overclaim me** (Studio + claim register)

Engineering profundity = those five staying true under automation, not more bots in more rooms.

## 9. Implementation sketch

1. Replace charter doc with v1 (this doc).
2. Extend factory: `hire` requires clause + resume JSON; reject incomplete; `propose` before create.
3. Concierge/QorT: propose channel/agent by default; create only if policy allows.
4. `#agent-roster` + `agents/registry.json` (parent, clause, status).
5. Frameworks path: brainstorm → mandatory WP skeleton in `#frameworks`.
6. Keep EA/SAP/WPR untouched as the Ops plane.

## 10. One-sentence charter v1

QorTroller agents are hired intelligences bound to purpose clauses—sovereignty, attestation, seats, provenance, ops, frameworks, and studio honesty—who collaborate through structured handoffs to turn conceptual work into sealed, testable reality, while the human remains the only authority over truth-plane acts.
