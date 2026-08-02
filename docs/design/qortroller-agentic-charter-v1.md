# QorTroller Agentic Charter v1

**Status:** charter sealed for engineering · implementation rails live  
**Date:** 2026-08-02  
**Supersedes:** [`qortroller-agentic-charter-v0.md`](qortroller-agentic-charter-v0.md)  
**Rails:** `scripts/buzz_agent_factory.py`, `agents/registry.json`, ACP gateway, persona packs  

This is a **redesign**, not a paste-over of v0. v0 optimized for Buzz membership (create channel / create agent). v1 optimizes for QorTroller’s reason to exist: **cryptographically real human play**, **gamer sovereignty** over that data, and **honest social pointers** — not agent theater.

---

## 1. North star

| | Principle |
|---|---|
| **v0** | Agents are first-class Buzz members who mint social artifacts. |
| **v1** | Agents are specialized intelligence aligned to QorTroller’s planes, hired to make verifiable physical play and gamer sovereignty **legible, operable, and extensible** — without becoming the **authority of record**. |

### Purpose stack (non-negotiable)

```text
Physical agency      →  attested controller + human in the loop
Cryptographic agency →  PoAC / consent / eligibility / export gates
Social legibility    →  Buzz digests, claims, seats, studio/WMP boards
Agent role           →  deepen legibility + ops + frameworks
                        never invent truth, spend, or OPEN
```

**Creation rights** (channels, child agents) are **privileges of a role after standards**, not the definition of the agent.

### Hard non-authority

Agents **never**:

- invent truth-plane facts (session verdicts, eligibility, chain state)
- spend IOTX or flip `CHAIN_SUBMISSION_PAUSED`
- publish VSS **OPEN** (or any seat act reserved for gamer/operator keys)
- upgrade **candidate → certified** in language or tags
- expand the `@EA` operator allow-list
- hold or request private keys

---

## 2. Three planes (charter spine)

| Plane | What is real here | Who may act |
|---|---|---|
| **Truth** | Bridge, proofs, sessions, chain, VSS eligibility | Human operator / gamer keys; agents **read & explain only** |
| **Ops** | `@EA` allow-list, SAP jobs, WPR policies, invariants | Operator pubkey → EA; agents may **relay**, not expand the allow-list |
| **Sense-making** | Channels, frameworks, briefs, hiring of specialist agents | Agents + humans under **Role Standards** (§5) |

v0 collapsed Sense-making into “mint anything.”  
v1 makes Sense-making **purposeful**: every channel and hire must map to a **purpose clause**.

**Compose, do not conflate:** Buzz announces; QorTroller measures; chain anchors only what humans sealed.

---

## 3. Purpose clauses

Every agent, channel, and project declares **one primary clause**. No clause → **no hire, no channel**.

| Clause ID | QorTroller purpose | Agent work product |
|---|---|---|
| **P-SOV** | Gamer sovereignty (consent, claim, export gate) | Consent digests, claim hygiene, plain-language rights |
| **P-ATT** | Attestation legibility (session postcard, continuum, pin) | Explain verdicts; never upgrade candidate → certified |
| **P-VSS** | Verifiable stream seat | Seat status, flag-down; **never OPEN** |
| **P-WMP** | Provenance for labs/studios (not “we are a world model”) | Verify pointers; deferred-export honesty |
| **P-OPS** | Rig / invariant / SAP engineering | Diagnose packs, job status, challenge language |
| **P-FRM** | Conceptual → implementable frameworks | Design notes that cite rails, non-claims, WP splits |
| **P-STU** | Game-developer integration | SDK / claim-safe pitch language, studio channel hygiene |

### Clause discipline

- Primary clause is **one**. Secondary collab is via **handoff** (§6), not dual-clause minting.
- Cross-clause synthesis is **Synthetist only** (optional), and still ends in a **human seal**.
- “Meta” surfaces (`#agent-roster`) are administrative, not a purpose substitute for work channels.

---

## 4. Novel channels (purpose-bound, not clutter)

### Stable set (create once)

| Channel | Clause | What posts there |
|---|---|---|
| `#rig-ops` | P-OPS | `@EA` digests, SAP job lines |
| `#lobby` | P-SOV | Gamer self-claims (**gamer-signed**) |
| `#matches` | P-ATT | Session postcards / pins |
| `#streams` | P-VSS | Seat + media pointer |
| `#wmp-announce` | P-WMP | Bundle / verify / deferred digests |
| `#studio-dev` | P-STU | Integration, claim-safe language |
| `#verify-lab` | P-WMP | Consumer verify outcomes |
| `#frameworks` | P-FRM | Charter WPs, non-goals, honesty ceilings |
| `#agent-roster` | meta | Agent resumes, clauses, status (hired / paused / candidate) |

### Ephemeral channels (Tyler-compatible)

Allowed **only** as:

```text
#wu-<job_id|short-slug>
```

Rules:

- Must declare a **parent clause** (inherited from the WP or job)
- **Auto-archive** after job seal / timeout
- **No ACP authority** (never an `@EA` home)
- **Kickoff template required** (problem + non-claims + acceptance)
- Agents do **not** freely invent topology: **propose → operator/policy approves**, or create only inside an **allow-listed prefix**

### Topology policy

| Action | Default |
|---|---|
| New stable channel | **propose** to `#frameworks` / operator |
| Ephemeral `#wu-*` | allowed if prefix allow-listed + parent clause |
| Rename / repurpose stable channel | operator only |
| Agent invents `#random-*` | **reject** |

Env / policy hooks:

- `BUZZ_FRAMEWORKS_CHANNEL_ID` — proposal + WP posts
- `BUZZ_AGENT_ROSTER_CHANNEL_ID` — hire / pause announcements
- `BUZZ_CREATION_APPROVED=1` or operator `--approve` — mint after standards
- `BUZZ_AGENT_MINTERS` — allow-list for recursive child hire (operator-controlled; empty = no recursive mint)

---

## 5. Hiring agents: standards and resume

Stop free-form `create agent <name> <role>`. Adopt **hire**:

```text
hire <AgentId>
  clause: P-…
  resume: <capabilities + forbidden>
  supervisor: EA | operator | Concierge | QorT
  channels: allow-list
  tools: allow-list
  graduation: what evidence pauses / fires them
```

Factory surface:

```powershell
python scripts/buzz_agent_factory.py hire `
  --name Seatwarden `
  --clause P-VSS `
  --resume "competence: eligibility language, flag-down; forbidden: VSS OPEN, keys, shell; channels: #streams" `
  --supervisor operator
# candidate until operator --approve
```

### Resume schema (engineering, not persona fluff)

| Field | Meaning | Required |
|---|---|---|
| **clause** | Primary `P-*` | yes |
| **competence** | Concrete skills (e.g. “explain PoAC postcard fields,” “draft WMP non-claim copy,” “build SAP context pack”) | yes (≥1) |
| **evidence_bar** | What must be true before output is trusted (cite bridge, claim register, tests) | yes for hire→enabled |
| **forbidden** | Keys, shell, chain, VSS OPEN, claim inflation, silent topology | yes (default injected if omitted) |
| **collab_graph** | Who they may message (EA, Concierge, Frameworks, Studio) | recommended |
| **channels** | Channel allow-list | yes for enabled |
| **tools** | Tool allow-list (`ask_ea`, `propose`, `post_digest`, …) | yes for enabled |
| **output_types** | `digest` · `sap_link` · `proposal` | yes |
| **sap_link** | Optional: work ships as `job_id` + human seal | optional |

### Hire bar (fail-closed)

An agent **without** `clause` + `forbidden` + channel allow-list **cannot be started** (`ENABLED` stays off / status stays `candidate`).

- **Children** inherit **narrower** resumes than parents.
- No recursive `hire` / `create agent` without operator mint allow-list (`BUZZ_AGENT_MINTERS`).
- `create-agent` CLI is **deprecated** → redirects to `hire` semantics; must not silently mint as “fully hired” without `--approve`.

### Core roster (profound, small — not 50 children)

| Agent | Clause | Resume one-liner | Status target |
|---|---|---|---|
| **EA** | P-OPS | Allow-listed engineering surface; no personality minting | ops plane (ACP) |
| **QorT** | P-OPS + explain | Rig steward; relay `ask_ea`; teaches two-plane rule | hired |
| **Concierge (Retina)** | P-SOV | Gamer self-service digests + claim; propose creates, limited mint | hired |
| **Attestor** | P-ATT | Session/postcard interpreter; claim-register aware | hire when needed |
| **Seatwarden** | P-VSS | Eligibility / flag-down language only | hire when needed |
| **Provenance** | P-WMP | Consumer-verifier honesty; deferred export explicit | hire when needed |
| **Studio** | P-STU | Dev integration + pitch ceilings | hire when needed |
| **Frameworks** | P-FRM | Brainstorms → WP + non-goals + testable acceptance | hire when needed |
| **Synthetist** *(optional)* | cross-clause | Multi-agent briefs → one implementable note for human seal | rare |

Registry of record: `agents/registry.json` (schema + roster). Social mirror: `#agent-roster`.

---

## 6. Aligning intelligence (structured handoff)

Not free-form “agents that know each other.” **Structured handoff only.**

```text
Sense  →  Frame  →  Ops  →  Seal
  │         │         │        │
  Concierge Frameworks  EA    Human
  Attestor  Synthetist  QorT   sap_seal / pin / (gamer) OPEN
  Provenance
```

| Handoff | Artifact |
|---|---|
| **Sense → Frame** | Problem statement + clause + non-claims |
| **Frame → Ops** | WP with acceptance tests / `@EA` commands / `job_id` |
| **Ops → Seal** | Results + challenges; human accept / reject / hold |
| **Any → Buzz** | **Digest only**; pointer to truth plane |

### How frameworks become reality

1. **Frameworks** writes the WP (`propose-wp` → `#frameworks`)
2. **EA / SAP** executes checks (`job_id`, invariant packs, diagnose)
3. **Human seals** (accept / reject / hold)
4. **Channels only announce** (digest / pin / roster line)

No channel post is the work. Digests are **pointers after seal**.

### Handoff non-goals

- Agents do not “vote” truth into existence
- Multi-agent chat without a WP is not progress
- SAP job without human seal is not progress
- Buzz creation receipt is not progress

---

## 7. What changes vs charter v0

| v0 | v1 redesign |
|---|---|
| Create is the main power | **Clause + resume** is the main power |
| First-class social members | First-class **purpose specialists** |
| Open-ended mint | Prefix/policy-gated mint; **propose-first** default |
| Creation receipt ≈ progress | **SAP seal / pin / on-chain** = progress |
| ~unlimited children | **Fixed roster + rare hires** |
| Buzz-native for its own sake | Buzz as **legibility layer** for VAPI / gamer sovereignty |

### Migration rules

| Surface | Action |
|---|---|
| `create agent <name> <role>` in personas | Rewrite to `hire … --clause --resume` |
| Channels without clause | Assign clause or archive |
| Child agents with no resume | status `paused` until resume filled |
| Unlimited brainstorm channels | Route to `#frameworks` + ephemeral `#wu-*` |
| Docs claiming agents “mint freely” | Point here; mark v0 deprecated |

---

## 8. Gamer-facing profundity (plain)

Agents should make a gamer experience:

| Feeling | Owner | Surface |
|---|---|---|
| **I own my claim** | Concierge | `#lobby` (gamer-signed) |
| **I understand what was attested** | Attestor | `#matches` postcards / pins |
| **I can stream only when the seat is real** | Seatwarden | `#streams` (status / flag-down; never agent OPEN) |
| **My data isn’t silently training someone else’s model** | Provenance + consent | `#wmp-announce` / `#verify-lab` + export gates |
| **Studios can’t overclaim me** | Studio + claim register | `#studio-dev` claim-safe language |

**Engineering profundity** = those five staying true under automation — not more bots in more rooms.

### Operator-facing profundity

| Feeling | Owner |
|---|---|
| **I can diagnose without theater** | EA + QorT on `#rig-ops` |
| **Ideas become testable WPs** | Frameworks on `#frameworks` |
| **Who is hired, under which clause** | `#agent-roster` + `agents/registry.json` |

---

## 9. Non-claims matrix (must not erode)

| Claim agents must never make | Why |
|---|---|
| “Humanity proven” from optical / overlay activity | Streamer perception / retina events are **advisory** |
| “Tournament eligible” without truth-plane gates | Eligibility is bridge / chain / operator ceremony |
| “OPEN for you” without gamer/operator seat act | VSS OPEN is truth-plane authority |
| “Your session is certified” when only candidate_ok | Candidate ≠ certified; Attestor explains, never upgrades |
| “We are the world model” | WMP is **provenance / deferred export**, not model ownership theater |
| “I spent / deployed / registered for you” | Chain writes are operator-fired |
| “I expanded who can run @EA” | Allow-list is ops-plane human policy |

Honesty flags in digests (`poep_enabled`, `l6b_enabled`, `candidate_ok`, etc.) are posted **as-is**. Never polished into stronger claims.

---

## 10. Rails map (code that must stay aligned)

| Concern | Path |
|---|---|
| Factory hire / propose / propose-wp | `scripts/buzz_agent_factory.py` |
| Roster schema + status | `agents/registry.json` |
| `@EA` allow-list, digest-only, no shell | `scripts/qortroller_acp_gateway.py` |
| QorT persona (P-OPS + explain) | `buzz-persona-qortroller/` |
| Concierge / Retina (P-SOV) | `buzz-persona-qortroller-concierge/` |
| VSS seat (gamer OPEN, never agent) | `scripts/buzz_vss_seat.py`, runbooks |
| Match pin (operator) | `scripts/buzz_pin_match.py` |
| Streamer perception (advisory) | `bridge/vapi_bridge/streamer_perception.py` |

**Invariant:** factory may mint **social identity** for a child (nsec + kind 0) only after hire standards; it never grants truth-plane authority.

---

## 11. Work products and acceptance (charter WPs)

Suggested implementation WPs (each must land with tests or dogfood notes):

| WP | Acceptance |
|---|---|
| **WP-C1 Hire fail-closed** | `hire` without competence / clause exits non-zero; no registry row |
| **WP-C2 Propose-first mint** | `create-*` without `--approve` and without mint env only posts proposal |
| **WP-C3 create-agent deprecated** | CLI warns; does not auto-`approved=True` unless `--approve` |
| **WP-C4 Roster completeness** | Core agents listed; candidates lack ENABLED |
| **WP-C5 Persona grammar** | Concierge/QorT DM grammar documents `propose` / `hire`, not free `create agent` |
| **WP-C6 WP skeleton** | `propose-wp` requires problem + non-claims + acceptance |
| **WP-C7 Ephemeral prefix** | Non-`#wu-*` agent-created channels rejected or proposed only |

---

## 12. Implementation status

| Item | State |
|---|---|
| Charter v1 (this doc) | **sealed for engineering** |
| Factory `VALID_CLAUSES`, `hire`, `propose`, `propose-wp` | **live** |
| Propose-first on `create-channel|project|workflow|template` | **live** (unless `--approve` / mint env) |
| `agents/registry.json` | **live** (core + extensible) |
| Persona packs aligned to propose/hire | **in progress** (must not reintroduce create-as-power) |
| Full Attestor / Seatwarden / Provenance packs | **not required until hire** |
| EA / SAP / WPR | **untouched** Ops plane — charter does not rewrite them |

---

## 13. One-sentence charter v1

> QorTroller agents are **hired intelligences** bound to purpose clauses — sovereignty, attestation, seats, provenance, ops, frameworks, and studio honesty — who collaborate through **structured handoffs** to turn conceptual work into **sealed, testable reality**, while the **human remains the only authority** over truth-plane acts.

---

## 14. Operator quick commands

```powershell
# Propose only (default)
python scripts/buzz_agent_factory.py propose `
  --artifact channel --name verify-lab --clause P-WMP `
  --description "Consumer verify outcomes"

# Framework WP skeleton
python scripts/buzz_agent_factory.py propose-wp `
  --topic "deferred-export honesty" --clause P-WMP `
  --problem "Labs confuse pointer verify with model ownership" `
  --non-claims "We are not a world model; export is deferred and gated" `
  --acceptance "verify-lab digest cites claim register + deferred flag"

# Hire candidate (resume required)
python scripts/buzz_agent_factory.py hire `
  --name Seatwarden --clause P-VSS `
  --resume "competence: eligibility language,flag-down; forbidden: VSS OPEN,keys,shell,chain; channels: #streams; tools: post_digest" `
  --supervisor operator

# Operator mint after standards
python scripts/buzz_agent_factory.py hire `
  --name Seatwarden --clause P-VSS `
  --resume "...same..." --approve
```

---

**End of Agentic Charter v1**
