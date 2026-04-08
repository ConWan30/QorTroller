# VAPI Wiki Engine — Claude Code Integration Prompt
# vapi_wiki.py — No Anthropic API required
#
# Paste this entire prompt into Claude Code.
# You are the LLM. The engine handles file I/O only.

---

```
Read MEMORY.md to confirm Phase 166 state, then execute these steps in order.
You are the intelligence layer. vapi_wiki.py handles file management only.
No external API is called at any point.

---

STEP 1 — INIT

python vapi_wiki.py init

Confirm: wiki/ directory created with phases/, entities/, concepts/,
synthesis/, what_if/, briefs/ subdirectories.
Confirm: all 9 corpus files listed as FOUND in the output.
If any corpus file shows ✗ MISSING — find it and move it to project root.

---

STEP 2 — GENERATE INGEST BRIEF FOR MEMORY.md

python vapi_wiki.py brief MEMORY.md 166

This creates: wiki/briefs/brief_MEMORY.md_166.md

Read that brief file now. It contains:
- Pre-extracted metrics (separation ratio, test counts, agent count)
- Domain detection (which VAPI domains the file covers)
- A page plan (which wiki pages to create)
- Provenance tag to use: [VAPI:Phase166:MEMORY.md:MEASURED]
- Frozen values that must appear correctly

---

STEP 3 — GENERATE PAGES FROM MEMORY.md BRIEF

Based on what you read in the brief, write the following wiki pages.
For each page, first check invariants:
  python vapi_wiki.py check "<key sentences from the page content>"

Then write the page directly to the appropriate wiki/ subdirectory.
Use this exact format for every page:

```markdown
# [PAGE TYPE]: [Entity Name]

[VAPI:Phase166:MEMORY.md:MEASURED]

## Current State
[description with provenance on each factual claim]

## Key Values
| Field | Value | Status |
|-------|-------|--------|
| Separation ratio (free-form) | 0.569 | BELOW GATE (0.70) |
| Separation gate | 0.70 | Phase 166 lowered from 1.0 |

## Related Pages
- [[phase_166]]
- [[l4_thresholds]]
```

Minimum pages to create from MEMORY.md:
  wiki/phases/phase_166.md         [TYPE: PHASE]
  wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  wiki/entities/agent_fleet.md      [TYPE: ENTITY]

Write each page, then confirm it passes the check command before proceeding.

---

STEP 4 — GENERATE BRIEF FOR VAPI_INVARIANTS.md

python vapi_wiki.py brief VAPI_INVARIANTS.md 166

Read the brief. Write the following pages:
  wiki/entities/l4_thresholds.md
  wiki/concepts/poac_wire_format.md
  wiki/concepts/zk_circuit.md
  wiki/concepts/epistemic_consensus.md

CRITICAL: These pages document frozen values.
Every frozen value must appear with [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
Run check on each page before writing — any violation blocks the write.

---

STEP 5 — GENERATE BRIEF FOR VAPI_WHAT_IF.md

python vapi_wiki.py brief VAPI_WHAT_IF.md 166

Read the brief. Write individual pages for each W1/W2/W3 entry:
  wiki/what_if/w1_001_ioswarm_homogeneity.md
  wiki/what_if/w1_002_separation_ratio_calibration.md
  wiki/what_if/w2_001_poad_composable_primitive.md
  [continue for all entries found in brief]

Each WHAT_IF page gets provenance: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

---

STEP 6 — GENERATE BRIEF FOR VAPI_AGENTS.md

python vapi_wiki.py brief VAPI_AGENTS.md 166

Read the brief. Write:
  wiki/entities/agent_fleet_registry.md   (all 22 agents in one table)
  wiki/entities/agent_22_biometric_privacy.md  (newest agent)
  wiki/entities/agent_21_fleet_consensus.md    (PoFC agent)

---

STEP 7 — ADD NEW WHAT_IF ENTRIES FROM PHASE 166

The Phase 166 assessment identified two active issues. Add them now:

# Add the enrollment count-gate W1
python vapi_wiki.py what_if "enrollment_complete count-gate spoofing" W1 166 \
  "enrollment_complete fires on session COUNT=10 without biometric quality gate — 10 non-standard sessions could cascade into TournamentActivationChainAgent" \
  "require defensible=True from separation_defensibility_log as prerequisite (Phase 157 target)"

# Add the mixed probe W2
python vapi_wiki.py what_if "mixed_biometric_probe activates all 13 features" W2 166 \
  "Phase 166 mixed_biometric_probe activates all 13 features across 4 segments — first measurement with complete feature set pending" \
  "Run 3 sessions per player with mixed probe, check ratio lift from 0.569"

Confirm both entries appear in VAPI_WHAT_IF.md.
Confirm MCP tool can find them: the MCP server reads VAPI_WHAT_IF.md directly.

---

STEP 8 — FIRST LINT PASS

python vapi_wiki.py lint

Review the output. Address P0 issues before continuing.

P0 = invariant violations in wiki pages → fix the page content
P0 = [NEEDS_PROVENANCE] on a frozen value claim → add citation
P1 = [CONTRADICTION: unresolved] → resolve by keeping both claims visible
P2 = orphan pages → add to wiki/index.md

---

STEP 9 — FIRST SNAPSHOT

python vapi_wiki.py snapshot

Record the SHA-256 hash output. This is the genesis snapshot.

---

STEP 10 — SYNC TO AUTORESEARCH

python vapi_wiki.py autoresearch_feed

This writes wiki gaps into experiments/log.jsonl.
The next /vapi autoresearch cycle will see them.

---

STEP 11 — ADD SKILL 15 TO VAPI_SKILLS.md

Open VAPI_SKILLS.md. Find the line:
  ## Skill Proposal Template

Insert the following block immediately before that line:

---
## Skill 15: VAPI Wiki Engine

**Command**: `/vapi wiki <operation>`

**Purpose**: Protocol-anchored knowledge base that accumulates VAPI protocol
knowledge permanently. No Anthropic API. Claude Code IS the intelligence layer.
Every claim has provenance. Every write is invariant-checked. Every session
ends with a cryptographic snapshot.

### Operations

| Command | What it does |
|---------|-------------|
| `python vapi_wiki.py init` | Create wiki/ structure (once) |
| `python vapi_wiki.py brief <file> <phase>` | Generate Claude Code ingest brief |
| `python vapi_wiki.py check "<text>"` | Invariant check before writing |
| `python vapi_wiki.py write_page <type> <entity> <phase>` | Write page with enforcement |
| `python vapi_wiki.py what_if "<topic>" W1\|W2 <phase>` | Append WHAT_IF to VAPI_WHAT_IF.md |
| `python vapi_wiki.py autoresearch_feed` | Sync wiki gaps → AutoResearch log |
| `python vapi_wiki.py lint` | Health check (no API) |
| `python vapi_wiki.py snapshot` | SHA-256 snapshot of wiki state |
| `python vapi_wiki.py status` | Full integration health |

### Integration Points (no duplication)

| System | How it connects |
|--------|----------------|
| MCP knowledge_server.py | Reads same VAPI_*.md files — wiki entries visible immediately |
| vapi_autoresearch.py | Shares experiments/log.jsonl — wiki feeds gaps to research loop |
| vapi_eval_harness.py | score_wiki_proposal() uses same rubric as AutoResearch |
| VAPI_WHAT_IF.md | what_if command appends directly — MCP vapi_query_what_if finds it |
| MEMORY.md | Wiki pages sourced from MEMORY.md — brief command extracts structure |

### Standard Session Protocol

**Start of session** (after /vapi start):
  python vapi_wiki.py status

**After completing a phase**:
  python vapi_wiki.py brief MEMORY.md <new_phase>
  [Claude Code reads brief and writes pages]
  python vapi_wiki.py snapshot
  python vapi_wiki.py autoresearch_feed

**After any WHAT_IF is identified**:
  python vapi_wiki.py what_if "<topic>" W1 <phase>
  [MCP server finds it immediately via vapi_query_what_if]

**End of session**:
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot

### Invariant Checks (enforced before every page write)

- BLOCK: SHA-256(raw[:228]) — wrong hash slice
- BLOCK: nPublic≠5 — ZK circuit frozen
- BLOCK: auto_activate_on_breakthrough set to anything but False
- BLOCK: epistemic threshold < 0.65
- BLOCK: separation_ratio hardcoded to literal value
- BLOCK: dry_run=False without N≥100 adjudications context
- BLOCK: USB thresholds applied to BT sessions

### Why No API

Claude Code IS the LLM. Calling the Anthropic API from within a Claude Code
session is redundant — it would lose all CLAUDE.md context, cost money, and
split the reasoning across two separate contexts. The engine handles only:
  - File I/O (wiki/ directory management)
  - Provenance formatting ([VAPI:Phase{N}:source:type])
  - Invariant enforcement (pure Python regex)
  - Eval harness scoring (imports vapi_eval_harness.py)
  - Cryptographic snapshots (SHA-256)
  - Lint scanning (pure regex)
  - WHAT_IF corpus appending (writes to VAPI_WHAT_IF.md)
  - AutoResearch feed (writes to experiments/log.jsonl)

Claude Code handles all reasoning, synthesis, and page generation.

### Outputs

```json
{
  "operation":      "brief|write_page|what_if|lint|snapshot",
  "pages_affected": ["wiki/phases/phase_166.md"],
  "provenance":     "[VAPI:Phase166:MEMORY.md:MEASURED]",
  "invariant_check":"PASS",
  "snapshot_hash":  "sha256:abc123...",
  "ar_feed_gaps":   2,
  "health_score":   87
}
```

### Last Run
**Status**: COMPLETE (Phase 166 integration)
**Result**: wiki/ initialized, 4 corpus briefs generated, genesis snapshot taken
**Next**: Run brief after every phase completion. Snapshot at end of every session.
---

---

STEP 12 — FINAL SNAPSHOT AND COMMIT

python vapi_wiki.py snapshot

Then commit everything:
  git add wiki/ vapi_wiki.py VAPI_SKILLS.md VAPI_WHAT_IF.md
  git commit -m "Phase 166: VAPI Wiki Engine (Skill 15) — no API, pure Python

  - vapi_wiki.py: Protocol-Anchored Knowledge Engine
  - wiki/: initialized with Phase 166 state (MEMORY, INVARIANTS, WHAT_IF, AGENTS)
  - wiki/snapshots.md: genesis snapshot sha256:[first 12 chars]
  - VAPI_SKILLS.md: Skill 15 added
  - VAPI_WHAT_IF.md: W1 enrollment count-gate, W2 mixed probe entries added
  - Integrates with: knowledge_server.py, vapi_autoresearch.py, vapi_eval_harness.py
  - No Anthropic API — Claude Code is the intelligence layer"

Replace [first 12 chars] with the actual SHA-256 prefix from snapshot output.

---

VERIFICATION

[ ] wiki/ exists with all subdirectories
[ ] wiki/briefs/ has briefs for MEMORY.md, VAPI_INVARIANTS.md, VAPI_WHAT_IF.md, VAPI_AGENTS.md
[ ] wiki/phases/phase_166.md exists and cites [VAPI:Phase166:MEMORY.md:MEASURED]
[ ] wiki/concepts/separation_ratio.md shows 0.569 / gate 0.70
[ ] wiki/entities/l4_thresholds.md shows 7.009/5.367 as [FROZEN]
[ ] VAPI_WHAT_IF.md has new entries for enrollment count-gate and mixed probe
[ ] wiki/snapshots.md has 2 entries
[ ] experiments/log.jsonl has wiki gap feed entry
[ ] VAPI_SKILLS.md contains Skill 15
[ ] python vapi_wiki.py status shows all ✓
[ ] python vapi_wiki.py lint shows health score ≥ 70
```
