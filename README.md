# VAPI-AutoResearch
## Session-Based Orchestration Improvement Loop

A novel adaptation of the Karpathy AutoResearch pattern, stripped of all
GPU/ML dependencies and repurposed exclusively as an interactive self-improving
expert system for the `/vapi` workflow orchestration skill.

**No GPU. No overnight loops. No background processes.**
Runs only while you are actively in a Claude Code session.

---

## What This Is

Standard AutoResearch: propose → train neural net → eval → keep/revert
VAPI-AutoResearch: propose → improve skill.md → eval against VAPI invariants → keep/revert

The "model" being optimized is your `/vapi` orchestration skill.
The "training data" is VAPI's own documented gaps, invariants, and phase architecture.
The "loss function" is the eval harness — rooted in VAPI's tournament readiness conditions.

**The recursive insight**: VAPI itself uses a self-improving calibration loop
(CalibrationIntelligenceAgent, Mode 6, ±15%/cycle). AutoResearch applies the same
pattern one level up — to the tool that builds VAPI.

---

## File Structure

```
vapi-autoresearch/
├── program.md              — Living strategy document (YOU edit this)
├── vapi_eval_harness.py    — IMMUTABLE eval rubric (never modify)
├── vapi_autoresearch.py    — EDITABLE orchestrator (Claude can improve this)
├── experiments/
│   ├── log.jsonl           — All cycle results (auto-generated)
│   └── cycle_NNNN_prompt.txt — Per-cycle prompts (auto-generated)
└── what_if_corpus/
    └── wif_*.md            — Validated WHAT_IF pairs (auto-saved on pass)
```

---

## Setup (one-time)

```bash
# From vapi-pebble-prototype root
cp -r vapi-autoresearch/ .
python vapi-autoresearch/vapi_eval_harness.py  # Smoke test
```

---

## Usage in Claude Code Sessions

### Start an improvement cycle
```bash
python vapi-autoresearch/vapi_autoresearch.py --cycle 1
```
Claude Code reads the generated prompt and produces a `---PROPOSAL_START---` block.

### Apply Claude's proposal
```bash
# Save Claude's proposal to a file, then:
python vapi-autoresearch/vapi_autoresearch.py --apply proposal.txt
```
The eval harness validates it. Pass → git commit + WHAT_IF corpus update. Fail → git revert.

### Force a specific priority
```bash
python vapi-autoresearch/vapi_autoresearch.py --cycle 1 --priority separation_ratio_pathways
python vapi-autoresearch/vapi_autoresearch.py --cycle 1 --priority class_k_definition
python vapi-autoresearch/vapi_autoresearch.py --cycle 1 --priority phase_109_113_precision
```

### Preview without committing
```bash
python vapi-autoresearch/vapi_autoresearch.py --cycle 1 --dry-run
```

### Check experiment history
```bash
python vapi-autoresearch/vapi_autoresearch.py --status
```

### Run multiple cycles in one session
```bash
python vapi-autoresearch/vapi_autoresearch.py --cycle 5
```

---

## What Gets Improved Each Cycle

Every cycle produces exactly three outputs:
1. **skill.md delta** — one targeted improvement to the /vapi orchestration skill
2. **WHAT_IF addition** — one validated W1+W2 pair added to the corpus
3. **Experiment log entry** — scored result saved to experiments/log.jsonl

---

## The Eval Harness (Immutable Rules)

Every proposal is scored against VAPI's own ground truth:

| Criterion | Weight | What It Checks |
|-----------|--------|---------------|
| Invariants preserved | 30% | All 20 mandatory invariants in skill.md |
| Gap advancement | 25% | Advances one of 5 known gaps |
| WHAT_IF quality | 20% | W1 grounded, W2 novel and VAPI-exclusive |
| Phase coherence | 15% | Consistent with Phase 109–113 architecture |
| Backward compatibility | 10% | No regression on Phase 62/66/67 |

**Pass threshold: 0.70**

Mandatory invariants (if missing → instant fail):
`228 bytes`, `SHA-256(raw[:164])`, `7.009`, `5.367`, `Poseidon(8)`, `0.362`,
`GSR_ENABLED=false`, `dry_run=True`, `TOURNAMENT BLOCKER`, `non-negotiable`, and 10 more.

---

## Five Improvement Priorities (from program.md)

1. `what_if_corpus_depth` — Build curated library of 20+ validated WHAT_IF pairs
2. `phase_109_113_precision` — Improve ioSwarm instruction depth to match Phase 62 ZK quality
3. `separation_ratio_pathways` — Skill autonomously suggests terminal script + analysis command
4. `class_k_definition` — Define Class K (GSR spoofer) detection approach
5. `legal_defensibility` — Generate legally-precise language for each verdict tier

The orchestrator auto-selects the priority least addressed in recent history.

---

## Why This Is Better Than Generic AutoResearch

Generic AutoResearch optimizes a model against a benchmark.
VAPI-AutoResearch optimizes the orchestration skill against VAPI's own documented reality.

The eval harness IS VAPI's invariant checklist. The scoring gaps ARE the tournament
readiness conditions. The WHAT_IF corpus IS the accumulated adversarial threat model.

Every improvement cycle makes Claude Code better at building VAPI specifically —
not better at generic software engineering.

---

## Session Cadence

- **Deep work day**: 3–5 cycles at session start, then manual development
- **Normal session**: 1 cycle, then work
- **Hardware/calibration session**: 0 cycles (no orchestration improvement needed)
- **Phase planning session**: 2 cycles focused on next phase coherence

The skill improves alongside the protocol. By Phase 113, the orchestration layer
will have accumulated 50+ validated improvement cycles and a curated WHAT_IF corpus
covering every documented risk in the VAPI threat model.
