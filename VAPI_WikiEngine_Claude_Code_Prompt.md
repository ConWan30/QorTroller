# VAPI Wiki Engine — Claude Code Integration Prompt
# File: vapi_wiki_engine.py (FINAL — replaces vapi_wiki.py and vapi_knowledge_engine.py)
# No Anthropic API. No external LLM. Claude Code IS the intelligence layer.
#
# BEFORE STARTING: Delete vapi_knowledge_engine.py and vapi_wiki.py from project root.
# Keep only: vapi_wiki_engine.py (this prompt's target file)

---

```
Read MEMORY.md to confirm Phase 166 state. Then:

1. Delete these files if they exist (they are superseded):
   del vapi_knowledge_engine.py
   del vapi_wiki.py
   del VAPI_Wiki_Claude_Code_Prompt.md

2. Confirm vapi_wiki_engine.py is in the project root.

Then execute the following steps in order.

---

STEP 1 — INIT

python vapi_wiki_engine.py init

Confirm: wiki/ directory created with all subdirectories.
Confirm: all 9 corpus files listed as ✓ FOUND.
If any show ✗ MISSING — find and move to project root before continuing.

---

STEP 2 — CHECK INTEGRATION POINTS

python vapi_wiki_engine.py status

This shows the health of all four integration points:
  ✓ Bridge DB (bridge/vapi_store.db) — Agent 15 live feed
  ✓ AutoResearch log (vapi-autoresearch/experiments/log.jsonl)
  ✓ Eval harness (vapi-autoresearch/vapi_eval_harness.py)
  ✓ VAPI_WHAT_IF.md — W1 sync target

If Bridge DB shows ○ (offline) — that's expected if bridge isn't running.
agent_feed will use fallback values. All other commands work without the bridge.

---

STEP 3 — GENERATE BRIEF FOR MEMORY.md

python vapi_wiki_engine.py brief MEMORY.md 166

This creates: wiki/briefs/brief_MEMORY.md_166.md

Read that brief now. It contains:
- Pre-extracted metrics (separation ratio, test counts, agent count)
- Domain detection results
- Page plan (which wiki pages to create)
- Provenance tag: [VAPI:Phase166:MEMORY.md:MEASURED]
- Frozen values that must appear correctly

---

STEP 4 — GENERATE PAGES FROM MEMORY.md BRIEF

From the brief you just read, write these wiki pages.
Before writing each page, run the invariant check:

  python vapi_wiki_engine.py check "<key sentences from the page>"

If check returns PASS, write the file directly to wiki/.
If check returns BLOCKED, fix the violation before writing.

Minimum pages from MEMORY.md:

  wiki/phases/phase_166.md [TYPE: PHASE]
  Content: what was built (Agent 21 PoFC, Agent 22 Privacy Compliance,
  mixed_biometric_probe, Phases 159-165 GDPR), test counts 1950/468/305,
  separation ratio 0.569 (gate 0.70), state flags, active W1 (enrollment count gate)
  Provenance: [VAPI:Phase166:MEMORY.md:MEASURED]

  wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  Content: 0.569 current, 0.70 gate (Phase 166 lowered from 1.0),
  root cause (5 features zero-variance in touchpad-only sessions),
  mixed_biometric_probe fix (all 13 features, first measurement pending)
  Provenance: [VAPI:Phase166:MEMORY.md:MEASURED]

  wiki/entities/agent_fleet.md [TYPE: ENTITY]
  Content: all 22 agents table, Agent 21 (FleetConsensusSnapshotAgent),
  Agent 22 (BiometricPrivacyComplianceAgent), epistemic threshold 0.65,
  triage_prereq_required=True (Phase 147 hardening)
  Provenance: [VAPI:Phase166:MEMORY.md:MEASURED]

---

STEP 5 — GENERATE BRIEF FOR VAPI_INVARIANTS.md

python vapi_wiki_engine.py brief VAPI_INVARIANTS.md 166

Read the brief. Write these pages with FROZEN provenance:

  wiki/entities/l4_thresholds.md
  Content: 7.009/5.367 (FROZEN — N=74, Phase 57), staleness (calib_dim=12
  vs live_dim=13), candidate values 6.563/5.114 (N=171, NOT YET APPLIED)
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

  wiki/concepts/poac_wire_format.md
  Content: 228 bytes (164 body + 64 signature), SHA-256(raw[:164]) ONLY,
  SHA-256(raw[:228]) is WRONG and blocked by invariant gate
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

  wiki/concepts/epistemic_consensus.md
  Content: threshold=0.65 (Phase 147 hardened from 0.60),
  triage_prereq_required=True, consensus_score formula,
  why 0.60 was insufficient (single ClassJ agent could reach it alone)
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

---

STEP 6 — GENERATE BRIEF FOR VAPI_WHAT_IF.md

python vapi_wiki_engine.py brief VAPI_WHAT_IF.md 166

Read the brief. Write individual pages for each W1/W2/W3 entry:
  wiki/what_if/w1_001_ioswarm_homogeneity.md
  wiki/what_if/w1_002_separation_ratio_deadline.md
  wiki/what_if/w2_001_poad_composable.md
  [continue for all entries in the brief]

---

STEP 7 — GENERATE BRIEF FOR VAPI_AGENTS.md

python vapi_wiki_engine.py brief VAPI_AGENTS.md 166

Write: wiki/entities/agent_fleet_registry.md (all 22 agents, table format)

---

STEP 8 — PULL LIVE SEPARATION RATIO FROM AGENT 15

python vapi_wiki_engine.py agent_feed

This reads separation_ratio_snapshots table from bridge/vapi_store.db.
If bridge is running: updates wiki/concepts/separation_ratio.md with live data.
If bridge is offline: prints "DB offline" — the page you wrote in Step 4 stands.

This is the VAPI-exclusive integration: wiki page driven by Agent 15's live data,
not by manual entry.

---

STEP 9 — ADD PHASE 166 WHAT_IF ENTRIES

python vapi_wiki_engine.py ingest_sweep  # skip if no sweep JSON yet

Add the two active W1/W2 from Phase 166 manually:

# Enrollment count-gate W1 (identified in Phase 156 session)
python vapi_wiki_engine.py check "enrollment_complete fires on session COUNT without biometric quality gate"
# (should PASS — no invariant violation)

Then append directly to VAPI_WHAT_IF.md (the engine's what_if command does this):
Note the exact format — see VAPI_WHAT_IF.md for the W1/W2 structure.
Use W1-NNN where NNN = next available number after existing entries.

---

STEP 10 — SYNC WHAT_IF TO EVAL HARNESS

python vapi_wiki_engine.py sync_what_if

This reads all W1 entries from VAPI_WHAT_IF.md and appends WIKI_KNOWN_W1
to vapi_eval_harness.py. The AutoResearch eval cycle now scores proposals
against all current W1 failure modes.

Confirm: vapi_eval_harness.py now contains WIKI_KNOWN_W1 block at the end.

---

STEP 11 — FIRST LINT

python vapi_wiki_engine.py lint

Review output. Address P0 issues before continuing.
P0 = invariant violations in wiki pages (fix the content)
P0 = [NEEDS_PROVENANCE] on frozen values (add citation)
P1 = [CONTRADICTION: unresolved] (preserve both claims, mark for resolution)
P2 = orphan pages (add to wiki/index.md)

---

STEP 12 — SNAPSHOT + ON-CHAIN ANCHOR

# If bridge is running:
python vapi_wiki_engine.py snapshot --anchor

# If bridge is offline:
python vapi_wiki_engine.py snapshot

The --anchor flag POSTs the SHA-256 hash to AdjudicationRegistry.sol
(already deployed at 0x44CF981f...) via the bridge API.
Same contract as PoAd hashes. Zero new infrastructure.

Record the SHA-256 output — this is the genesis wiki snapshot.

---

STEP 13 — AUTORESEARCH FEED

python vapi_wiki_engine.py autoresearch_feed

Syncs wiki gaps and current separation ratio to experiments/log.jsonl.
The next /vapi autoresearch cycle sees them as active priorities.

---

STEP 14 — ADD SKILL 15 TO VAPI_SKILLS.md

Open VAPI_SKILLS.md. Find: ## Skill Proposal Template
Insert immediately before it:

---
## Skill 15: VAPI Wiki Engine

**Command**: `/vapi wiki <operation>`

**File**: vapi_wiki_engine.py (replaces vapi_wiki.py and vapi_knowledge_engine.py)

**Purpose**: Protocol-anchored knowledge base that accumulates VAPI knowledge
permanently. No Anthropic API. Claude Code IS the intelligence layer.

### Commands

| Command | What It Does |
|---------|-------------|
| `init` | Create wiki/ structure (once) |
| `brief <file> <phase>` | Generate Claude Code ingest brief |
| `check "<text>"` | Invariant check before writing |
| `agent_feed` | Pull separation ratio from Agent 15 DB → wiki page |
| `ingest_sweep <json>` | Consume Skill 14 output → wiki + W1 + AR log |
| `sync_what_if` | VAPI_WHAT_IF.md W1s → eval harness WIKI_KNOWN_W1 |
| `snapshot [--anchor]` | SHA-256 [+ AdjudicationRegistry.sol on-chain] |
| `phase_close <N>` | Complete phase boundary sequence |
| `autoresearch_feed` | Wiki gaps → AutoResearch experiment log |
| `lint` | Health check (no API) |
| `status` | Full integration health |

### Exclusive Integrations (all use existing VAPI infrastructure)

| Integration | What Connects | How |
|------------|--------------|-----|
| Agent 15 live feed | separation_ratio_snapshots table | Direct SQLite read |
| Skill 14 sweep | PostCode sweep JSON output | ingest_sweep command |
| Eval harness | KNOWN_GAPS → WIKI_KNOWN_W1 | sync_what_if command |
| AdjudicationRegistry.sol | On-chain wiki anchor | snapshot --anchor |
| MCP server | vapi_reload_knowledge | After phase_close |
| AutoResearch loop | experiments/log.jsonl | autoresearch_feed |
| VAPI_WHAT_IF.md | W1 entries → harness | Bidirectional sync |

### Standard Session Protocol

**Start of session**: `python vapi_wiki_engine.py status`

**After completing a phase**:
```bash
python vapi_wiki_engine.py phase_close <N>
# Then: Claude Code reads wiki/briefs/ and generates pages
```

**After any Skill 14 sweep**:
```bash
python vapi_wiki_engine.py ingest_sweep sweep_output.json
python vapi_wiki_engine.py sync_what_if
```

**End of session**:
```bash
python vapi_wiki_engine.py lint
python vapi_wiki_engine.py snapshot --anchor
```

### Invariant Enforcement (blocked before any wiki write)
- SHA-256(raw[:228]) — wrong hash slice
- nPublic ≠ 5 — ZK circuit frozen
- auto_activate_on_breakthrough ≠ False
- Epistemic threshold < 0.65
- separation_ratio assigned literal value
- dry_run=False without N≥100 context
- USB thresholds applied to BT sessions
- GSR_ENABLED=True without N≥30

### Why No API
Claude Code holds CLAUDE.md, all VAPI_*.md corpus files, and the full
session context. Calling the Anthropic API separately loses all of that,
costs tokens, and produces weaker results. The engine handles file I/O,
provenance, invariants, scoring, snapshots, and feed operations.
Claude Code handles all reasoning and page generation.

### Last Run
**Status**: COMPLETE (Phase 166 integration)
**Result**: Replaces vapi_wiki.py and vapi_knowledge_engine.py
**Next**: phase_close after each phase completion
---

---

STEP 15 — FINAL SNAPSHOT AND COMMIT

python vapi_wiki_engine.py snapshot --anchor

git add wiki/ vapi_wiki_engine.py VAPI_SKILLS.md VAPI_WHAT_IF.md
git rm vapi_knowledge_engine.py vapi_wiki.py VAPI_Wiki_Claude_Code_Prompt.md 2>/dev/null
git commit -m "Phase 166: VAPI Wiki Engine v3 (Skill 15)

- vapi_wiki_engine.py: replaces vapi_wiki.py + vapi_knowledge_engine.py
- Agent 15 live feed (separation_ratio_snapshots SQLite)
- Skill 14 sweep ingestion (ingest_sweep command)
- WHAT_IF → eval harness sync (sync_what_if → WIKI_KNOWN_W1)
- On-chain anchor via AdjudicationRegistry.sol (snapshot --anchor)
- phase_close: complete phase boundary in one command
- No Anthropic API — Claude Code is the intelligence layer
- wiki/ initialized with Phase 166 corpus
- genesis snapshot sha256:[first 12 chars here]"

Replace [first 12 chars here] with the actual SHA-256 prefix from snapshot output.

---

VERIFICATION CHECKLIST

[ ] vapi_knowledge_engine.py DELETED
[ ] vapi_wiki.py DELETED
[ ] vapi_wiki_engine.py in project root
[ ] wiki/ initialized with all subdirectories
[ ] wiki/phases/phase_166.md exists with [VAPI:Phase166:MEMORY.md:MEASURED]
[ ] wiki/concepts/separation_ratio.md shows 0.569 / gate 0.70
[ ] wiki/entities/l4_thresholds.md shows 7.009/5.367 as [FROZEN]
[ ] wiki/concepts/poac_wire_format.md has SHA-256(raw[:164]) correctly
[ ] vapi_eval_harness.py has WIKI_KNOWN_W1 block (from sync_what_if)
[ ] wiki/snapshots.md has genesis entry
[ ] experiments/log.jsonl has autoresearch_feed entry
[ ] VAPI_SKILLS.md has Skill 15
[ ] python vapi_wiki_engine.py status shows all ✓
[ ] python vapi_wiki_engine.py lint shows health ≥ 70
[ ] git log shows clean commit

---

ONGOING SESSION PROTOCOL

Start of every session:
  python vapi_wiki_engine.py status
  python vapi_wiki_engine.py agent_feed   # refresh ratio from Agent 15

After every phase:
  python vapi_wiki_engine.py phase_close <N>
  [Claude Code reads briefs → generates pages]

After every Skill 14 sweep:
  python vapi_wiki_engine.py ingest_sweep <sweep_output.json>

End of every session:
  python vapi_wiki_engine.py lint
  python vapi_wiki_engine.py snapshot --anchor
```
