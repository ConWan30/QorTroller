# Phase 238 Verification Report — MetaLearner Input Set Examination

**Status**: STEP 0 only. Design review held pending review of Q1–Q4.
**Standard**: Every claim cites file:line. Source quotes in fenced blocks.
**Files read in full**: `vapi_eval_harness.py` (467 lines), `vapi_autoresearch.py` (529 lines).
**Files read in focus**: `vapi-mcp/unified_server.py` (3020 lines — sections 1–225, 252–417, 469–730, 945–1090, 1335–1730, 2965–2980).

---

## Q1 — What inputs does `MetaLearner.analyze()` actually consume today?

**Answer**: One input: a list of dicts loaded from `vapi-autoresearch/experiments/log.jsonl` via `ExperimentLedger.load()`. Nothing else.

### Evidence

**Method signature** — `vapi-mcp/unified_server.py:339`:
```python
def analyze(self, entries: list[dict]) -> dict:
```

**The function reads only two fields off each entry** — `vapi-mcp/unified_server.py:351–354`:
```python
failures = [e for e in entries if not e.get("passed", True)]

for entry in failures:
    reason = entry.get("reason", "") + " ".join(entry.get("invariant_failures", []))
```

**The keyword check list `_ML_THEMES` is a module-level Python literal** — `vapi-mcp/unified_server.py:312–333`. Five themes (invariant_violation / separation_ratio / what_if_quality / phase_coherence / gap_advancement), each a list of substrings. No file I/O, no DB calls, no MCP cross-calls inside `analyze()`.

### Where the `entries` argument comes from — every call site

All 5 call sites of `META.analyze(...)` load from `LEDGER.load()`:

| File:Line | Load call |
|---|---|
| `unified_server.py:1127–1128` | `learner_entries = LEDGER.load(limit=20); meta = META.analyze(learner_entries)` |
| `unified_server.py:1425–1426` | `all_entries = LEDGER.load(); result["meta_learner"] = META.analyze(all_entries)` |
| `unified_server.py:1722–1724` | `all_entries = LEDGER.load(); ... meta = META.analyze(all_entries)` |
| `unified_server.py:2015–2016` | `all_entries = LEDGER.load(); meta = META.analyze(all_entries)` |
| `unified_server.py:2249–2250` | `all_entries = LEDGER.load(); meta = META.analyze(all_entries)` |

**`ExperimentLedger.load()` reads exactly one file** — `vapi-mcp/unified_server.py:255–273`:
```python
def load(self, limit: int = 0) -> list[dict]:
    """Return all (or last N) experiment entries from log.jsonl."""
    entries = []
    if not EXPERIMENT_LOG.exists():
        return entries
    try:
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").strip().split("\n")
        for line in lines:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    if limit > 0:
        return entries[-limit:]
    return entries
```

`EXPERIMENT_LOG` is defined at `unified_server.py:88`: `EXPERIMENT_LOG = AUTORESEARCH_DIR / "experiments" / "log.jsonl"`.

### What is NOT consumed (verified by absence)

Inside `MetaLearner.analyze()` body (lines 339–384), there are **zero** references to:
- `_load_workflow_file(...)` — confirmed by absence in body
- `db_query(...)` — confirmed by absence in body
- `_parse_claude_md(...)` — confirmed by absence in body
- `httpx`/`subprocess` — no external calls
- `_load_wiki_file(...)` — confirmed by absence in body
- Any of the 9 `WORKFLOW_FILES` keys (line 212–222), including `"memory"`

### Critical observation for the design hypothesis

The user's hypothesis frames MetaLearner as part of "the Autoresearch self-learning loop." Verified: the standalone autoresearch script `vapi_autoresearch.py` (529 lines, fully read) **never imports or calls `MetaLearner`**. The class lives only in `unified_server.py` and is invoked only by MCP tools.

`vapi_autoresearch.py:38–41` shows what the script does import:
```python
sys.path.insert(0, str(Path(__file__).parent))
from vapi_eval_harness import evaluate_proposal, KNOWN_GAPS, PASS_THRESHOLD
```

It imports the harness, not MetaLearner. The cycle path (`run_cycle` → `apply_proposal` → `evaluate_proposal`) is fully traceable in the script and contains zero MCP cross-calls.

This means: "wiring inputs to MetaLearner" only changes what an **operator-facing diagnostic tool** returns when called from a Claude Code session. It does not change what the autonomous cycle (`vapi_autoresearch.py --cycle N`) consumes when scoring proposals.

---

## Q2 — What inputs does the eval harness use across its 5 subscores?

**Answer**: Every subscore reads only its `proposal_text` (and one also reads `skill_md_after`) string arguments. All check lists are module-level Python literals. No file I/O, no DB, no MCP, no memory.

### Subscore weights

`vapi_eval_harness.py:64–73`:
```python
SCORING_WEIGHTS = {
    "invariants_preserved":      0.30,  # Mandatory — all or nothing
    "gap_advancement":           0.25,  # Advances one of the 5 priorities
    "what_if_quality":           0.20,  # W1 grounded, W2 novel
    "phase_coherence":           0.15,  # Consistent with Phase 109–113
    "backward_compatibility":    0.10,  # No regression on Phase 62/66/67
}

PASS_THRESHOLD = 0.70
```

### Per-subscore input verification

**1. `invariants_preserved` (weight 0.30)** — `vapi_eval_harness.py:143–153`:
```python
def check_invariants(proposal_text: str, skill_md_after: str) -> tuple[bool, list]:
    failures = []
    text_to_check = skill_md_after.lower()
    for invariant in MANDATORY_INVARIANTS:
        if invariant.lower() not in text_to_check:
            failures.append(f"MISSING: '{invariant}'")
    return len(failures) == 0, failures
```
Inputs: `proposal_text` (unused — only `skill_md_after` is read at line 149), and the 20-entry `MANDATORY_INVARIANTS` list at lines 37–58. Both string-only.

**2. `gap_advancement` (weight 0.25)** — `vapi_eval_harness.py:156–168`:
```python
def score_gap_advancement(proposal_text: str) -> tuple[float, list]:
    proposal_lower = proposal_text.lower()
    advances = []
    for gap_name, gap_info in KNOWN_GAPS.items():
        if any(kw.lower() in proposal_lower for kw in gap_info["keywords"]):
            advances.append(gap_name)
    score = min(1.0, len(advances) * 0.25)
    return score, advances
```
Inputs: `proposal_text` and the 5-entry `KNOWN_GAPS` dict at lines 79–110. String-only.

**3. `what_if_quality` (weight 0.20)** — `vapi_eval_harness.py:171–210`:
```python
def score_what_if_quality(proposal_text: str) -> tuple[float, str]:
    if "[WHAT_IF]" not in proposal_text and "W1 —" not in proposal_text:
        return 0.5, "No WHAT_IF section in proposal (neutral score)"
    ...
    w1_quality_markers = [
        "implication" in w1_section.lower(),
        "mitigation" in w1_section.lower(),
        ...
    ]
```
Input: `proposal_text` only. Heuristic substring checks for "implication", "mitigation", "cryptograph", etc.

**4. `phase_coherence` (weight 0.15)** — `vapi_eval_harness.py:213–233`:
```python
def score_phase_coherence(proposal_text: str) -> float:
    phase_109_113_markers = [
        "ioswarm", "ioSwarm", "IoSwarm",
        "quorum", "BLOCK_QUORUM",
        "VHP auth gate", "vhp_authorization",
        "AdjudicationRegistry", "PoAd",
        "SeparationRatioRegistry",
        "IoSwarmConsensusAggregator",
        "VAPISwarmOperatorGate",
        "Phase 109", "Phase 110", "Phase 111",
        "Phase 112", "Phase 113",
        "node emulator", "ioswarm_node_emulator",
    ]
    proposal_lower = proposal_text.lower()
    matches = sum(1 for m in phase_109_113_markers if m.lower() in proposal_lower)
    if matches == 0:
        return 0.5  # Neutral if not ioSwarm-related
    return min(1.0, 0.5 + matches * 0.1)
```
Input: `proposal_text` only. Confirmed by code: this subscore is **literally hardcoded to ioSwarm/Phase-109-113 keywords**. Phase 237-EXTEND additions (CONSENT, FROZEN-v1 family, SDK patterns) score 0.5 (neutral) here. Doc comment also confirms scope: *"Score coherence with Phase 109–113 architecture"* (line 215).

**5. `backward_compatibility` (weight 0.10)** — `vapi_eval_harness.py:236–253`:
```python
def score_backward_compatibility(proposal_text: str) -> float:
    regression_red_flags = [
        "change the wire format",
        "modify sha-256",
        "remove poseidon",
        ...
    ]
    proposal_lower = proposal_text.lower()
    for flag in regression_red_flags:
        if flag in proposal_lower:
            return 0.0  # Hard fail
    return 1.0
```
Input: `proposal_text` only. 7 hardcoded red-flag substrings.

### `evaluate_proposal()` does no additional I/O

`vapi_eval_harness.py:256–334`: the orchestrator simply invokes the 5 subscores in sequence, weights them, and returns an `EvalResult`. Zero file I/O, zero network calls, zero subprocess invocations.

### Verified absences

The full eval harness file (467 lines) was searched for: `import sqlite3`, `import httpx`, `subprocess`, `_load_workflow_file`, `_load_wiki_file`, `db_query`, `MetaLearner`. Result: **none of these appear**. The harness has no live-state awareness whatsoever.

---

## Q3 — What is `_load_workflow_file()` called from?

**Answer**: 6 call sites total. Two iterate over all 9 workflow files (full-text search + startup warmup); four target specific keys (`"what_if"` × 2, `"invariants"` × 2). **The `"memory"` key is loaded only as a haystack for substring search — never parsed structurally for `PATTERN-NNN` extraction or any other field-level extraction.**

### The registry

`vapi-mcp/unified_server.py:212–222`:
```python
WORKFLOW_FILES = {
    "invariants": "VAPI_INVARIANTS.md",
    "what_if":    "VAPI_WHAT_IF.md",
    "corpus":     "VAPI_CORPUS.md",
    "agents":     "VAPI_AGENTS.md",
    "skills":     "VAPI_SKILLS.md",
    "memory":     "VAPI_MEMORY.md",
    "context":    "VAPI_CONTEXT.md",
    "privacy":    "VAPI_BIOMETRIC_PRIVACY.md",
    "controller": "VAPI_CONTROLLER_INTELLIGENCE.md",
}
```

### The function

`vapi-mcp/unified_server.py:225–230`:
```python
def _load_workflow_file(key: str) -> str:
    """Load a VAPI-WORKFLOW.v2 corpus file with mtime caching."""
    if key not in _WORKFLOW_CACHE:
        _WORKFLOW_CACHE[key] = _MtimeCache()
    path = WORKFLOW_DIR / WORKFLOW_FILES.get(key, f"{key}.md")
    return _WORKFLOW_CACHE[key].read(path)
```
Returns the entire file contents as a string. No structural parsing.

### Every call site, with what it does

| Line | Caller | Key argument | What it does with the text |
|---|---|---|---|
| **469** | `vapi_unified_wif_corpus` tool body | `"what_if"` (literal) | Parses VAPI_WHAT_IF.md for WIF entries |
| **568** | (continuation in same WIF builder) | `"what_if"` (literal) | Same — second pass on same file |
| **716** | `vapi_query_knowledge` tool body | **iterates `WORKFLOW_FILES.keys()`** at line 715 | Substring-matches user `query` against EVERY line of each file (including `VAPI_MEMORY.md`). Returns line-context matches; no field extraction |
| **1335** | `vapi_invariant_check` tool body | `"invariants"` (literal) | Reads VAPI_INVARIANTS.md for INV-NNN lookup |
| **1566** | `vapi_invariant_check` again (different code path) | `"invariants"` (literal) | Same |
| **2975** | `main()` server startup | **iterates `WORKFLOW_FILES.keys()`** | Preloads all 9 files into mtime cache (warmup; results discarded) |

### Verified: `VAPI_MEMORY.md` is NEVER structurally parsed

A grep across the entire `unified_server.py` (3020 lines) for `_load_workflow_file("memory")` returns **zero matches**. The file is reachable only through:
1. Line 716 — full-text search for an arbitrary user-supplied `query` (returns substring matches, not parsed fields)
2. Line 2975 — startup cache warmup

There is **no code path that extracts `PATTERN-NNN` entries**, "Session Outcomes", `[PATTERN-NNN]` blocks, or any other structured field from `VAPI_MEMORY.md`. The hypothesis Input B description ("parse VAPI_MEMORY.md for PATTERN-NNN entries") would require **writing a new parser** — no existing code reads memory in that shape.

The same applies to `VAPI_AGENTS.md`, `VAPI_CONTROLLER_INTELLIGENCE.md`, `VAPI_BIOMETRIC_PRIVACY.md`, `VAPI_CORPUS.md`, `VAPI_SKILLS.md`, `VAPI_CONTEXT.md` — all reachable only via the search loop at line 716, never structurally parsed.

---

## Q4 — What MCP tools currently exist that COULD be called by the loop but are not?

**Answer**: 19 tools across two MCP servers. The loop (`vapi_autoresearch.py`) calls **none** of them. The hypothesis-listed tool `vapi_fleet_coherence` does not exist by that name; the FSCA-finding tool is `vapi_contradiction_status` (line 1595) in `unified_server.py`.

### Tools registered in `unified_server.py` (19 tools)

From `grep -n 'name="vapi_'`:

| Line | Tool name |
|---|---|
| 945  | `vapi_unified_state` ✓ user-listed |
| 1056 | `vapi_session_context` |
| 1157 | `vapi_query_knowledge` |
| 1213 | `vapi_phase_brief` |
| 1285 | `vapi_entity` |
| 1371 | `vapi_experiment_history` |
| 1436 | `vapi_validate_proposal_full` |
| 1497 | `vapi_invariant_check` |
| **1595** | **`vapi_contradiction_status`** ← actual name; user wrote `vapi_fleet_coherence` (not registered) |
| 1682 | `vapi_autoresearch_cycle` |
| 1939 | `vapi_unified_wif_corpus` |
| 1995 | `vapi_learning_loop_status` |
| 2101 | `vapi_skill_state_sync` |
| 2213 | `vapi_phase_advance_proposal` |
| 2379 | `vapi_code_change_impact` |
| 2518 | `vapi_engineering_decision` |
| 2647 | `vapi_autonomous_gap_scan` |
| 2900 | `vapi_bt_contention_intelligence` |
| 2937 | `vapi_grind_analytics` |

### Tools registered in `vapi-mcp/server.py`

`vapi-mcp/server.py:234`:
```python
name="vapi_protocol_state",
```
Confirmed: `vapi_protocol_state` exists. (Plus 11 others in that file: `vapi_separation_ratio`, `vapi_separation_analysis`, `vapi_run_calibration`, `vapi_agent_fleet`, `vapi_sync_memory`, `vapi_tournament_preflight`, `vapi_phase_context`, `vapi_what_if`, `vapi_autoresearch_seed`, etc.)

### What the autonomous cycle (`vapi_autoresearch.py`) actually calls

Full file read confirms the cycle imports/calls:
- `vapi_eval_harness.evaluate_proposal` (line 41, 259)
- `subprocess.run(["git", ...])` for git_snapshot/git_revert (lines 80, 81, 91)

It calls **zero MCP tools**. Cross-checked with `grep -n 'subprocess\|httpx\|requests\|mcp' vapi_autoresearch.py` — only the two git subprocess calls appear.

### Correction to the hypothesis

The hypothesis says:
> *"vapi_fleet_coherence (FSCA rule findings)"*

This tool name is not registered. The closest tool is **`vapi_contradiction_status`** at `unified_server.py:1595`, which returns FSCA findings via `db_query("SELECT ... FROM fleet_coherence_log ...")` at line 1649–1652. Any design that wires "FSCA findings into the loop" should reference `vapi_contradiction_status` (or query `fleet_coherence_log` directly via `db_query()`), not the non-existent `vapi_fleet_coherence`.

---

## Summary table — what feeds what today

| Component | Reads | Does NOT read |
|---|---|---|
| `MetaLearner.analyze()` (unified_server.py:339) | `log.jsonl` entries (via `LEDGER.load()`) | FSCA, memory, MCP, bridge state, workflow files |
| Eval harness `evaluate_proposal()` | `proposal_text`, `skill_md_after` (strings only) | Anything else — zero file I/O |
| `vapi_autoresearch.py` cycle script | `vapi.md`, `program.md`, `log.jsonl` | MCP tools, MetaLearner, FSCA, memory, bridge state |
| `_load_workflow_file("memory")` | Loaded only at server startup warmup + as haystack for full-text search | Never parsed structurally for PATTERN-NNN or any field |

**The autonomous cycle (`vapi_autoresearch.py`) and the MCP-side analysis tooling (`MetaLearner`, etc.) are loosely coupled — the cycle does not call into MCP at all.** This is a stronger statement than my previous-session correction acknowledged.

---

## Held for review

I will not produce `PHASE_238_DESIGN_REVIEW.md` until you confirm Q1–Q4 above are correctly answered. If any answer is wrong or missing evidence, point me at the file:line and I'll re-verify.

Two architectural claims in the design hypothesis already appear to be code-disprovable based on Q1 and Q4:

1. **Hypothesis frames MetaLearner as autonomous-loop infrastructure.** Code shows it is operator-invoked diagnostic infrastructure exposed via MCP — the cycle script never calls it. Wiring inputs to MetaLearner does not change what the autonomous cycle scores against.

2. **Hypothesis Input A names `vapi_fleet_coherence` as the FSCA tool.** That tool name is not registered. The actual tool is `vapi_contradiction_status`.

I am flagging these per your instruction: *"If at any point during this work you find that my design hypothesis contains an architectural claim that the code disproves — say so and correct it before incorporating into the design review."* The design review, when it comes, should re-frame the hypothesis around what the code actually shows.
