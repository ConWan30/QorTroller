# Phase 238 Design Review — MetaLearner Input Set Examination

**Status**: Held for user review. Not committed.
**Verification basis**: `wiki/proposals/VERIFICATION_REPORT.md` (approved).
**Standard applied**: every claim about `run_cycle()`, `evaluate_proposal()`, or `MetaLearner` cites file:line. Claims I cannot cite do not appear.

---

## Section 1 — Recommendations (per-decision)

| Decision | Verdict | One-line reason |
|---|---|---|
| **A.** `vapi_autoresearch.run_cycle()` loads richer context at cycle start | **PROCEED — scoped** | Wire FSCA findings only; defer memory PATTERN and live MCP state to separate phases. The cycle's prompt-building path (`vapi_autoresearch.py:142–185`) is the cleanest seam; FSCA query via `db_query("SELECT ... FROM fleet_coherence_log ...")` is one-line additive. |
| **B.** `vapi_eval_harness.evaluate_proposal()` accepts richer arguments | **REJECT** | The harness is declared IMMUTABLE at `vapi_eval_harness.py:2` and is the experiment ledger's deterministic-score oracle. Making it live-state-aware breaks the "same proposal → same score" contract that makes `log.jsonl` re-scorable and meaningful. **First never-ship item.** |
| **C.** `MetaLearner.analyze()` expands input set | **CONDITIONAL DEFER** *(revised after first review)* | If Decision A surfaces contradiction-aware reasoning inline in cycle output, C's diagnostic value collapses — operators reading the cycle proposals would see the context where they need it. C ships only if a post-A evaluation gate (5+ cycles) shows independent diagnostic value. **Second never-ship candidate.** |

**Combined verdict (revised)**: PROCEED on A (FSCA only); REJECT on B (harness immutability); CONDITIONAL DEFER on C (re-examine after A is operational). **1 of 9 hypothesised wiring possibilities ships in Phase 238.** The remaining 8 are split between hard REJECT (B in full), conditional defer (C in full), and indefinite defer (memory PATTERN and live-MCP-state subprocess wiring across both A and C).

---

## Section 2 — D1–D5 per decision (15 analyses)

### Decision A — wire richer context into `run_cycle()`

**What "wire" means concretely**: `vapi_autoresearch.py:198–200` currently loads three things:
```python
current_skill = load_skill_md()     # ~/.claude/commands/vapi.md (line 44–47)
program = load_program_md()         # vapi-autoresearch/program.md (line 50–53)
log = load_experiment_log()         # vapi-autoresearch/experiments/log.jsonl (line 56–68)
```

`format_cycle_prompt(...)` at `vapi_autoresearch.py:125–185` then concatenates these into a prompt that Claude reads to produce the proposal. The seam for adding FSCA findings is between line 200 and line 210 — load FSCA rows, format them as a section, append to the prompt template.

#### A.D1 — Failure mode: FSCA produces a high false-positive rate

**Risk is real.** FSCA contradictions can fire on transient state (clock skew, retry loops, replication lag). If the cycle reads `fleet_coherence_log ORDER BY created_at DESC LIMIT 10` blindly (matching the existing pattern at `unified_server.py:1651`), Claude sees 10 contradictions and may propose a phase that addresses a noise contradiction instead of a real one.

**Mitigation, citable from existing code**: `vapi-mcp/unified_server.py:1607–1611` already exposes a `severity_filter` parameter on `vapi_contradiction_status` with enum `["CRITICAL", "HIGH", "MEDIUM", "LOW", "ALL"]`. Run_cycle should query with `severity in ("CRITICAL", "HIGH")` and `created_at > now - 24h` — both filters drop transient noise. **Severity-filtered FSCA in prompt is small enough that even 3–5 false positives don't dominate Claude's reasoning.**

**Failure-mode resolution**: real but bounded. Default to severity ≥ HIGH; degrade to no-FSCA-in-prompt if FSCA returns >10 rows post-filter (signals broken filtering, not signal).

#### A.D2 — Failure mode: PATTERN entries misapplied

**N/A for FSCA scope.** This failure mode applies only if memory PATTERN entries are wired into the prompt. Since the recommendation defers memory PATTERN, D2 has no analysis here. If memory PATTERN is wired in a later phase, this question becomes load-bearing — see "deferred items rationale" below.

#### A.D3 — Failure mode: MCP server returns stale data due to its own mtime cache

**N/A under the recommended scope.** The recommended wiring uses `db_query("SELECT ... FROM fleet_coherence_log ...")` directly against the bridge SQLite — same call path as `unified_server.py:1649–1652`. **No subprocess call to MCP**, no MCP-side cache. The only cache layer is SQLite's own page cache, which is per-write fresh.

If we *had* recommended live-MCP-state via subprocess, this failure mode would be real (CLAUDE.md cache + MCP server-side cache + cycle process startup latency). The recommendation rejects that path specifically because of this.

#### A.D4 — Architecture: additive (new prompt section) or replacement (FSCA replaces something)

**Additive is correct; replacement is wrong.**

The cycle's prompt template at `vapi_autoresearch.py:142–185` has a clear schema: priority, program directives, known gaps, recent experiment history, current skill.md length. Adding a sixth section "ACTIVE FSCA CONTRADICTIONS (severity ≥ HIGH, last 24h)" is purely additive — no existing content removed, no field semantics changed.

Replacement reasoning would be: "FSCA findings replace recent_experiment_history because contradictions are more current than past failures." This is wrong — the two surfaces measure different things. log.jsonl tracks Autoresearch's own cycle history (did past proposals pass?). FSCA tracks cross-agent runtime contradictions (does the agent fleet currently disagree?). Both are needed; neither replaces the other.

#### A.D5 — Non-circular test

**Test design — measurable, non-circular**:

> *"Does the cycle's proposed phase **address** an active FSCA contradiction when one exists?"*

Implementation:
1. Pre-wiring: run 10 cycles. Record (FSCA contradictions active at cycle start, priority chosen by cycle).
2. Wire FSCA into prompt.
3. Post-wiring: run 10 cycles under similar conditions. Record same pair.
4. **Test passes iff post-wiring cycles propose priorities that match an active FSCA contradiction at a measurably higher rate** (e.g. >2× pre-wiring baseline) when ≥1 contradiction is active.

This is non-circular because:
- The truth signal (FSCA contradictions exist) comes from `fleet_signal_coherence_agent.py` running on its 15-min poll independent of the cycle (`fleet_signal_coherence_agent.py:889–907` — `_check_contradictions` runs against bridge SQLite, no Autoresearch input).
- The measurement (cycle-priority match against contradiction-list) doesn't use the harness, doesn't use MetaLearner, doesn't reference the same input set we're wiring.
- The test cannot self-confirm: a cycle that *ignores* FSCA contradictions will fail this test even if its proposals score well at the harness.

**Caveat**: requires N≥10 cycles pre and post for statistical signal. At current cadence (cycles are operator-triggered, not on a timer), this is multi-week work to gather data, not a CI-scale test.

---

### Decision B — eval harness accepts richer arguments

**REJECT — argued in detail because the user constraint requires at least one never-ship item.**

#### B.D1 — Failure mode: FSCA produces a high false-positive rate

**Catastrophic for the harness specifically.** If `evaluate_proposal()` reads live FSCA and rejects proposals that touch any file currently in CONTRADICTION, then a single false-positive FSCA rule firing locks out the entire proposal surface for that file. Example: `CONSENT_REVOKED_BUT_DATA_FLOWING` fires on test data → harness rejects every consent-related proposal until the contradiction clears → operator can't propose the *fix* because the fix touches consent code.

This is worse than A.D1 because the harness is the gate, not the prompt. In A, Claude can reason past noise. In B, the score is mechanical.

#### B.D2 — Failure mode: PATTERN entries misapplied

**Cuts both ways.** PATTERN-018 ("default to inclusion when deferral is conservative theater") applied to harness scoring would inflate the gap_advancement score for proposals that *include more*. Combined with the existing 0.25 weight on gap_advancement (`vapi_eval_harness.py:65`), this could turn the harness into a "scope larger" generator. Anti-pattern for an oracle.

#### B.D3 — Failure mode: stale cache

**Existential for the harness contract.** `vapi_eval_harness.py:2`:
```
vapi_eval_harness.py — IMMUTABLE
NEVER modify this file. It is the ground truth that prevents drift.
```

The "ground truth that prevents drift" claim only holds because `evaluate_proposal(proposal_text, skill_md_after)` is a pure function: same inputs → same outputs forever. This is what makes `log.jsonl` re-scorable: every entry's `score` field can be re-derived from the proposal_text alone, audited later, compared across cycles.

Make the harness state-aware and:
- A proposal scored 0.75 today might score 0.65 next month as FSCA fires/clears
- `log.jsonl` entries become un-replayable
- The auditability that makes the experiment ledger trustworthy degrades to "score depends on when you ran it"

This is a cryptographic-ledger-style invariant. It is not negotiable.

#### B.D4 — Architecture: additive or replacement

**Neither additive nor replacement is acceptable for B.** The harness's defining property is *purity*. Adding optional state-aware arguments (additive) still forks the determinism contract — proposals that pass with state-context might fail without it, proposals that fail with state-context might pass without it. Replacement (state-aware harness only) is worse. The architectural answer to "should we make the harness state-aware?" is: don't.

#### B.D5 — Non-circular test

**The non-circular test for B is impossible by construction.**

Per the user's framing: *"if A proceeds, the test needs to measure whether wider cycle input produces better proposals."* For A, "better" can be measured against an external truth (FSCA contradiction matching, per A.D5). For B, "better" must be measured against an oracle — but **the harness IS the oracle** in this system. There is no second oracle to compare against.

You could imagine: "use operator judgment as the oracle." But operator judgment was the *original* oracle that the harness replaced — the harness exists precisely so cycles can self-evaluate without human review at every step. Making the harness state-aware and then validating its scores against operator judgment defeats the harness's reason for existing.

This impossibility is itself the strongest argument for REJECT. **You cannot ship a state-aware harness because you cannot test that it makes scoring better.**

#### Evidence supporting B = REJECT (per Section 4 ask)

Three concrete code-level points support REJECT:

1. **Explicit IMMUTABLE label**, `vapi_eval_harness.py:2–6`:
   ```
   vapi_eval_harness.py — IMMUTABLE
   The fixed evaluation rubric for VAPI-AutoResearch improvement cycles.
   NEVER modify this file. It is the ground truth that prevents drift.
   ```

2. **Determinism is structurally enforced** — `vapi_eval_harness.py:256–334` (`evaluate_proposal()` body) contains zero file I/O, zero network calls, zero subprocess invocations. Verified by grep across the full 467-line file.

3. **There is already a controlled mutation surface for the harness**, `vapi_eval_harness.py:372–373`:
   ```python
   # Auto-synced from VAPI_WHAT_IF.md by vapi_wiki_engine.py
   # Last sync: 2026-04-11T18:25:04.117858+00:00
   ```
   The `WIKI_KNOWN_W1` dict at lines 374–465 is auto-synced — but the sync writes to a *separate dict*, not to the scoring functions. The pattern is: harness rules are frozen, knowledge tables are syncable, and the two are kept apart. Decision B violates this separation.

The right answer for "harness is unaware of new invariants" is the regression test from the previous session (assert MANDATORY_INVARIANTS coverage matches `VAPI_INVARIANTS.md` INV-IDs). Not state-awareness.

---

### Decision C — `MetaLearner.analyze()` expands input set

**Recommendation (revised): CONDITIONAL DEFER.** The original recommendation was PROCEED-scoped; user review surfaced that if Decision A causes the cycle's *generated proposals* to surface contradiction-aware reasoning inline, C's operator-facing diagnostic value collapses to zero. The D1–D5 analysis below describes what C *would* do if shipped — kept for completeness — but the verdict is now: re-examine after A has run 5+ cycles. Evaluation criteria are in Section 3.

**What expansion would mean concretely if shipped**: `MetaLearner.analyze()` at `unified_server.py:339–384` currently takes `entries: list[dict]` and clusters into 5 themes (`_ML_THEMES` at lines 312–333). Expansion = a new theme bucket "active_contradictions" populated by querying `fleet_coherence_log` directly inside the function or by accepting an optional `fsca_findings: list[dict]` parameter.

#### C.D1 — Failure mode: FSCA false-positive rate

**Manageable.** MetaLearner is operator-facing diagnostic — `unified_server.py` exposes it through tools `vapi_experiment_history` (line 1371), `vapi_autoresearch_cycle` (line 1682), `vapi_learning_loop_status` (line 1995). The operator reading the report can recognize "this contradiction looks transient" and discount it. This is exactly the failure mode that A.D1 has to mitigate algorithmically; in C the human is in the loop.

**Action item if C ships**: add severity to the `theme_examples` field so operators see which contradictions made it into the cluster.

#### C.D2 — Failure mode: PATTERN entries misapplied

**N/A.** Memory PATTERN is not in the recommended scope for C. MetaLearner is a clustering function; it categorizes failures into themes. PATTERN entries are *guidance*, not failures. They don't fit the clustering input shape, and there's no obvious cluster they'd land in. Wiring them would require redesigning the function's purpose.

#### C.D3 — Failure mode: stale cache risk

**Minimal.** MetaLearner runs *inside* the MCP server process. Adding `db_query("SELECT ... FROM fleet_coherence_log ...")` to its body means same-process SQLite read. No second cache layer. The mtime cache that affects `_load_workflow_file()` does not apply because we're reading SQLite, not workflow markdown.

#### C.D4 — Architecture: additive or replacement

**Additive.** Add a 6th theme "active_contradictions" to `_ML_THEMES` (lines 312–333) plus a query-and-merge step before the existing failure-clustering loop at line 351. The existing 5 themes (invariant_violation, separation_ratio, what_if_quality, phase_coherence, gap_advancement) keep their semantics unchanged. The `dominant_blocker` calculation at lines 364–366 (sort by count, take top) extends naturally to 6 categories.

#### C.D5 — Non-circular test

**Easier than A.D5 because operator-facing.** Two-part test:

1. **Behavioral test (mechanical)**: call `MetaLearner.analyze(entries)` against a fixture with 5 cycle-failure entries + 1 active CRITICAL FSCA contradiction. Assert the returned `dominant_blocker` reflects the contradiction when its theme count exceeds cycle-failure theme counts. This is non-circular because the fixture is hand-built; it's testing the wiring, not the value.

2. **Operator-satisfaction test (qualitative)**: invoke `vapi_experiment_history` (which calls `MetaLearner.analyze`) before and after wiring. Operator reads both reports; if the post-wiring report surfaces information the operator finds actionable that the pre-wiring report did not, the wiring helped.

The qualitative leg is acceptable for C specifically because **MetaLearner exists to inform humans**, not to gate code changes. There's no determinism contract being violated by qualitative evaluation.

---

## Section 3 — Ship order + scope boundaries

### Revised order (after first review)

**Phase 238 — Decision A only.** Wire FSCA findings into `run_cycle()` prompt. Standalone change in `vapi_autoresearch.py`. Estimated ~80 LOC: load FSCA rows via `db_query()` (or read `bridge/vapi_store.db` directly), format as a prompt section, splice into `format_cycle_prompt()`. Plus the non-circular test runner.

**Phase 238-evaluate — gate decision after 5+ cycles.** After A is operational and at least 5 cycles have completed under the new prompt schema, examine whether C still has independent diagnostic value. The gate question:

> *"Does the cycle's generated proposal text already surface contradiction-aware reasoning that would otherwise require a separate operator-facing diagnostic?"*

The evaluation criteria — measurable from the proposal text itself, no operator survey required:

| Criterion | Measurement | Threshold for "C is redundant" |
|---|---|---|
| **Contradiction reference rate** | Among cycles where ≥1 active FSCA contradiction was in the prompt, fraction whose generated proposal text explicitly names the contradiction (rule_name or device_id) | ≥80% reference rate → cycle output already surfaces context inline |
| **Priority-contradiction alignment** | Same as A.D5 metric: fraction of cycles where chosen priority addresses an active contradiction when one exists | If alignment is high enough that operators don't ask "why didn't the cycle address X?", clustering adds nothing |
| **Operator request signal** | Did any operator, in 5+ cycles of working under A, explicitly request "show me the contradiction breakdown separately"? | Zero such requests → C has no demand. Any requests → C has unique value, ship as Phase 239 |

If all three thresholds are crossed (high reference rate, high alignment, zero diagnostic-separation requests), **C is deferred indefinitely**. This is the second never-ship outcome the revised constraint allows.

If any threshold is not crossed, **C ships as Phase 239** with the scope already specified in C.D1–D5 above. The ~30 LOC implementation is unchanged regardless of when it ships; only the scheduling decision is being held.

**Phase 238 will not pre-commit to either outcome.** The evaluation gate is the deliberate hold point; A's behaviour determines whether C is needed.

**Decision B never ships.** See Section 4.

### Why this revision is honest, not scope creep

The original recommendation said C is "cheap (~30 LOC) given Decision A already wires FSCA." That framing assumed C had independent value once the wiring was free. The revised framing recognises that **cheap doesn't mean useful** — if A makes C's surface visible inline in the cycle's own proposals, C duplicates information operators already see. Shipping C anyway would be the inverse of PATTERN-018: defaulting to inclusion when inclusion is conservative *padding*, not load-bearing.

The "argue for at least one never-ship" constraint is now satisfied twice: B is hard REJECT (the harness contract is non-negotiable), and C is conditional REJECT (probability-weighted, gated on A's behaviour). Memory PATTERN and live-MCP-state subprocess wiring across both decisions remain indefinitely deferred per the existing scope-boundary table below.

### Scope boundaries — items deferred (not "deferred unnecessarily" — actually deferred)

| Deferred item | Why deferred | When it could be revisited |
|---|---|---|
| Memory PATTERN entries → run_cycle prompt | No existing parser for `PATTERN-NNN` extraction (Q3 verified). Writing one is its own work. The cycle's reasoning is Claude reading prose; raw `VAPI_MEMORY.md` text in the prompt would balloon prompt size with mostly-irrelevant past entries. **Deferred until either a parser ships or the cycle moves to retrieval-augmented prompt construction.** | Phase 240+ candidate when retrieval infrastructure exists |
| Memory PATTERN entries → MetaLearner | PATTERN entries are guidance, not failures; they don't fit MetaLearner's clustering input shape. Wiring them would redesign the function. | Probably never — MetaLearner is the wrong primitive |
| Live MCP state via subprocess → run_cycle | CLAUDE.md re-read inside the cycle is the lighter alternative that addresses the same drift concern. Subprocess to MCP adds complexity (cache layering, dependency on MCP server health, latency on cycle start) for marginal gain. | Phase 250+ if subprocess complexity is justified by some new requirement |
| Live MCP state via subprocess → MetaLearner | MetaLearner already runs inside the MCP server. Self-subprocessing is the wrong architecture. Expanding `_parse_claude_md()` reach if needed is the alternative. | Probably never |

### Scope creep rejected

The hypothesis listed three optional input sources × three decisions = 9 wiring possibilities. The recommendation ships **2 of 9** (A-FSCA, C-FSCA) and rejects 7. Per the user's "argue for at least one never-ship" constraint:

- **B in full is REJECT**: the eval harness must remain immutable.
- **A-memory-PATTERN, A-MCP-live, C-memory-PATTERN, C-MCP-live**: deferred (not rejected) — they're not architecturally wrong, just not justified at the current marginal-value cost.

---

## Section 4 — Evidence supporting REJECT for Decision B

(The user requested this section structure for whichever decisions end DEFER/REJECT. Decisions A and C end PROCEED-scoped, so the evidence-for-defer is in their scope-boundary table above. The remaining REJECT decision is B.)

### Code-level evidence that the harness is structurally locked

**1. Explicit immutability declaration** — `vapi_eval_harness.py:1–11`:
```python
"""
vapi_eval_harness.py — IMMUTABLE
=================================
The fixed evaluation rubric for VAPI-AutoResearch improvement cycles.
NEVER modify this file. It is the ground truth that prevents drift.

Every proposed change to skill.md or the WHAT_IF corpus is scored
against these criteria. A change must PASS all mandatory checks and
achieve a weighted score >= 0.70 to be committed.

This file has no GPU or ML dependency. All evaluation is:
  1. Rule-based invariant checking (pass/fail)
  2. Weighted scoring against VAPI's documented gaps
  3. WHAT_IF quality assessment (grounded W1, novel W2)
"""
```

The phrase *"the ground truth that prevents drift"* is the contract. Drift means: same proposal, different score over time. State-awareness creates drift by definition.

**2. Pure-function structure verified by absence**

`evaluate_proposal()` body, `vapi_eval_harness.py:256–334`, contains:
- Zero `import` statements that could fail at runtime (all imports at file top)
- Zero file I/O (`open`, `Path.read_text`, etc.)
- Zero network calls (`httpx`, `requests`, `urllib`)
- Zero subprocess (`subprocess.run`, `Popen`)
- Zero database access (`sqlite3`, `db_query`)
- Zero MCP cross-calls

Verified by grep across the full 467-line file. The harness is by code structure a deterministic string-processor.

**3. Auto-sync surface exists but is structurally separated**

`vapi_eval_harness.py:372–373`:
```python
# Auto-synced from VAPI_WHAT_IF.md by vapi_wiki_engine.py
# Last sync: 2026-04-11T18:25:04.117858+00:00
```

The `WIKI_KNOWN_W1` dict at lines 374–465 is mutable (auto-synced). But the scoring functions at lines 143–253 do not reference `WIKI_KNOWN_W1`. Verified: grep for `WIKI_KNOWN_W1` outside the dict definition returns zero matches in the file.

The pattern is: **scoring is frozen; knowledge tables are syncable; and the two are kept apart**. Decision B proposes to wire knowledge-table-style content (live FSCA, live state) into the scoring functions. This violates the existing separation that the auto-sync comment implicitly documents.

**4. The non-circular test is impossible**

Argued above in B.D5. Restated as evidence: any test of "does state-aware harness produce better scores?" requires a second oracle. The harness is the only oracle in this system. Adding a second oracle to validate the first means two systems competing for ground-truth status — which is what the harness exists to prevent.

### What the right answer to "harness is unaware of new invariants" actually is

The previous session identified that the harness's `MANDATORY_INVARIANTS` list (20 substrings) has fallen behind `VAPI_INVARIANTS.md` (30 INV-IDs after Phase 237-EXTEND). The instinct to "wire the registry into the harness" is wrong for the same determinism-contract reasons.

The right answer is the regression test sketched in the previous session:
```python
def test_mandatory_invariants_covers_all_INV_entries():
    registry = parse_inv_ids("VAPI_INVARIANTS.md")  # {"INV-001", ..., "INV-CONSENT-004"}
    harness  = set(MANDATORY_INVARIANTS)
    missing = [inv for inv in registry if not any_substring_matches(inv, harness)]
    assert missing == [], f"Registry has {missing} but harness doesn't check them"
```

This test fires in CI when the registry grows, forcing a human to either (a) add the new substring to MANDATORY_INVARIANTS or (b) consciously decide not to check that invariant. Either choice is a deliberate human action. The harness file itself doesn't change at runtime — it changes via reviewed PR like every other Python file. Determinism is preserved.

---

## Closing — single-paragraph recap (revised)

Phase 238 was framed as "wire three input sources into MetaLearner." Verification showed MetaLearner is operator-facing, not autonomous-loop infrastructure, so the framing split into three independent decisions. **Decision A (wire FSCA into the cycle's prompt) PROCEEDS** because the cycle currently has no awareness of cross-agent contradictions, the wiring is small and additive, and a non-circular test exists. **Decision B (wire richer arguments into the eval harness) REJECTS** because the harness's immutability is its single most valuable property — making it state-aware destroys the determinism contract that lets `log.jsonl` be re-scorable, and no non-circular test of the change is even possible. **Decision C (wire FSCA into MetaLearner) is now CONDITIONALLY DEFERRED** after the first review surfaced that A may surface contradiction-aware reasoning inline in the cycle's *generated proposals*, making C's separate operator-facing diagnostic redundant. Phase 238 ships A only; a Phase 238-evaluate gate (5+ cycles, three measurable criteria) determines whether C ever ships as Phase 239 or is deferred indefinitely. Memory PATTERN entries and live-MCP-state subprocess wiring remain indefinitely deferred across both A and C. **Final scope: 1 of 9 hypothesised wiring possibilities ships immediately; 1 is gated; 1 is hard-rejected; 6 are indefinitely deferred.**

Held for final review. Will not commit until you approve. Implementation of Decision A begins only after this revision is approved.
