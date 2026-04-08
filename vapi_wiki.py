"""
vapi_wiki.py — VAPI Protocol-Anchored Knowledge Engine
=======================================================
Pure Python. No Anthropic API. No external LLM calls.
Claude Code IS the intelligence layer.

This engine handles everything that doesn't require reasoning:
  - File structure (wiki/ directory, page creation)
  - Provenance citations ([VAPI:Phase{N}:source:type])
  - Invariant enforcement (same rules as MCP vapi_validate_proposal)
  - Eval harness scoring (same rubric as vapi_eval_harness.py)
  - Cryptographic snapshots (SHA-256 of wiki state)
  - Lint scanning (pure regex — no LLM)
  - WHAT_IF corpus appending (writes to VAPI_WHAT_IF.md directly)
  - AutoResearch feed (writes gaps to experiments/log.jsonl)
  - Memory sync (appends sweep summaries to MEMORY.md)

Claude Code handles everything that requires reasoning:
  - Synthesizing source content into wiki pages
  - Resolving contradictions
  - Generating W1/W2 WHAT_IF entries from observed gaps
  - Deciding which pages to update

Integration architecture (no duplication, no API):

  VAPI_*.md files  ←→  MCP knowledge_server.py  (reads same files)
       ↕                        ↕
  wiki/ pages      ←→  Claude Code context       (reads naturally)
       ↕                        ↕
  VAPI_WHAT_IF.md  ←→  vapi_query_what_if tool   (MCP finds new entries)
       ↕                        ↕
  experiments/     ←→  vapi_autoresearch.py       (shared log)
  log.jsonl               ↕
                   vapi_eval_harness.py  ←→  score_wiki_proposal()

Usage:
  python vapi_wiki.py init
  python vapi_wiki.py ingest MEMORY.md 166
  python vapi_wiki.py brief MEMORY.md 166     # generates Claude Code brief (no API)
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot
  python vapi_wiki.py what_if "enrollment count gate" W1 166
  python vapi_wiki.py autoresearch_feed        # sync wiki gaps → experiment log
  python vapi_wiki.py status                   # full wiki health report
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Paths — everything relative to project root
# ─────────────────────────────────────────────────────────────

ROOT         = Path(".")

# Wiki (new pages written here)
WIKI         = ROOT / "wiki"
WIKI_PHASES  = WIKI / "phases"
WIKI_ENTITIES= WIKI / "entities"
WIKI_CONCEPTS= WIKI / "concepts"
WIKI_SYNTH   = WIKI / "synthesis"
WIKI_WHATIF  = WIKI / "what_if"

# Wiki meta files
WIKI_LOG     = WIKI / "log.md"
WIKI_INDEX   = WIKI / "index.md"
WIKI_CONTRADICT = WIKI / "contradictions.md"
WIKI_BLOCKED    = WIKI / "blocked_updates.md"
WIKI_SNAPSHOTS  = WIKI / "snapshots.md"
WIKI_BRIEFS     = WIKI / "briefs"       # Claude Code ingest briefs

# Existing VAPI corpus (read-only — MCP server reads these too)
_WF = ROOT / "VAPI-WORKFLOW.v2"
CORPUS = {
    "invariants":   _WF / "VAPI_INVARIANTS.md",
    "what_if":      _WF / "VAPI_WHAT_IF.md",
    "agents":       _WF / "VAPI_AGENTS.md",
    "corpus":       _WF / "VAPI_CORPUS.md",
    "skills":       _WF / "VAPI_SKILLS.md",
    "privacy":      _WF / "VAPI_BIOMETRIC_PRIVACY.md",
    "context":      _WF / "VAPI_CONTEXT.md",
    "memory":       ROOT / "MEMORY.md",
    "controller":   _WF / "VAPI_CONTROLLER_INTELLIGENCE.md",
}

# AutoResearch integration (shared paths with vapi_autoresearch.py)
AR_LOG       = ROOT / "vapi-autoresearch" / "experiments" / "log.jsonl"
AR_PROGRAM   = ROOT / "vapi-autoresearch" / "program.md"
AR_WHATIF    = ROOT / "vapi-autoresearch" / "what_if_corpus"

# Eval harness (import for scoring — same rubric as AutoResearch)
HARNESS_PATH = ROOT / "vapi-autoresearch" / "vapi_eval_harness.py"

# ─────────────────────────────────────────────────────────────
# Frozen VAPI Invariants
# Mirrors MCP vapi_validate_proposal AND vapi_eval_harness.MANDATORY_INVARIANTS
# Single source of truth — kept in sync by Skill 14 PostCode sweep
# ─────────────────────────────────────────────────────────────

FROZEN = {
    # Protocol constants (Phase 1, never change)
    "poac_bytes":          "228",
    "record_hash":         "SHA-256(raw[:164])",
    "nPublic":             "5",
    "zk_hash":             "Poseidon(8)",
    "ceremony_beacon":     "#41723255",

    # Calibrated thresholds (Phase 57, N=74)
    "l4_anomaly":          "7.009",
    "l4_continuity":       "5.367",

    # Protocol governance (Phase 147 hardened)
    "epistemic_threshold": "0.65",
    "triage_prereq":       "True",
    "auto_activate":       "False",

    # ioSwarm quorum (Phase 109)
    "block_quorum":        "0.67",
    "mint_quorum":         "0.80",

    # VHP (Phase 99C)
    "vhp_expiry_days":     "90",

    # Current gate (Phase 166 lowered from 1.0)
    "separation_gate":     "0.70",
}

# ─────────────────────────────────────────────────────────────
# Invariant enforcement
# Same logic as MCP server's vapi_validate_proposal.
# Returns (passes: bool, violations: list[str])
# ─────────────────────────────────────────────────────────────

def check_invariants(text: str) -> tuple[bool, list[str]]:
    low = text.lower()
    v   = []

    if "sha-256(raw[:228])" in low or "sha256(raw[:228])" in low:
        v.append(
            "CHAIN_HASH: Must be SHA-256(raw[:164]) — signature bytes excluded. "
            "Any reference to [:228] is wrong and must be rejected."
        )

    if re.search(r"npublic\s*[=:]\s*(?!5)[\d]", low):
        v.append(
            "ZK_CIRCUIT: nPublic=5 frozen since Phase 62 ceremony at IoTeX #41723255. "
            "Changing nPublic requires full MPC re-run."
        )

    if "auto_activate_on_breakthrough" in low:
        if "=false" not in low.replace(" ", "").replace("_", ""):
            v.append(
                "PERMANENT: auto_activate_on_breakthrough=False is a "
                "compile-time constant. Non-negotiable."
            )

    if re.search(r"epistemic.{0,60}0\.[0-5]\d", low):
        v.append(
            "EPISTEMIC: Threshold 0.65 (Phase 147 hardening). "
            "Cannot regress. triage_prereq_required=True also required."
        )

    if re.search(r"separation_ratio\s*=\s*[\d.]+", text):
        v.append(
            "HARDCODE: separation_ratio must not be assigned a literal value. "
            "Always sourced from live analyze_interperson_separation.py output."
        )

    if re.search(r"(bluetooth|\\bbt\\b).{0,80}(7\.009|5\.367)", low):
        v.append(
            "BT_THRESHOLD: USB thresholds (7.009/5.367 at 1002Hz) must not apply "
            "to BT sessions (250Hz). Separate calibration track required."
        )

    if re.search(r"dry_run\s*=\s*false", low):
        if "n>=100" not in low and "n≥100" not in low:
            v.append(
                "DRY_RUN: dry_run=False requires N≥100 live adjudications with "
                "zero false positives. Phase 97 3-condition guard not bypassed."
            )

    if re.search(r"poac.{0,30}(229|227|230)\s*byte", low):
        v.append(
            "WIRE_FORMAT: PoAC is exactly 228 bytes (164 body + 64 signature). "
            "No other size is valid."
        )

    if "gsr_enabled=true" in low or "gsr_enabled = true" in low:
        v.append(
            "GSR_GATE: GSR_ENABLED=True requires N≥30 calibration sessions per player. "
            "Current N=0. MockGSRGrip only."
        )

    return len(v) == 0, v

# ─────────────────────────────────────────────────────────────
# Eval harness scoring (optional — uses existing harness if available)
# ─────────────────────────────────────────────────────────────

def score_wiki_proposal(proposal_text: str) -> dict:
    """
    Scores a proposed wiki page against the eval harness rubric.
    Uses vapi_eval_harness.evaluate_proposal() if available.
    Falls back to local invariant check only.
    """
    passes, violations = check_invariants(proposal_text)

    result = {
        "passed":       passes,
        "violations":   violations,
        "score":        None,
        "harness_used": False,
    }

    if not HARNESS_PATH.exists():
        result["score"] = 1.0 if passes else 0.0
        return result

    try:
        import importlib.util
        spec   = importlib.util.spec_from_file_location("harness", HARNESS_PATH)
        mod    = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        eval_result = mod.evaluate_proposal(
            proposal_text=proposal_text,
            current_skill_md="",
            experiment_log=[],
        )
        result["score"]        = eval_result.score
        result["passed"]       = eval_result.passed and passes
        result["harness_used"] = True
        result["harness_detail"] = eval_result.reason if hasattr(eval_result, "reason") else ""
    except Exception as e:
        result["score"]         = 1.0 if passes else 0.0
        result["harness_error"] = str(e)

    return result

# ─────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────

def prov(phase: int, source: str, kind: str = "MEASURED") -> str:
    """[VAPI:Phase166:MEMORY.md:MEASURED]"""
    return f"[VAPI:Phase{phase}:{source}:{kind}]"

def wiki_hash() -> str:
    """SHA-256 of entire wiki state."""
    h = hashlib.sha256()
    if WIKI.exists():
        for p in sorted(WIKI.rglob("*.md")):
            h.update(p.read_bytes())
    return h.hexdigest()

# ─────────────────────────────────────────────────────────────
# File helpers
# ─────────────────────────────────────────────────────────────

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def append_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)

def log_op(operation: str, pages: list[str], provenance: str, outcome: str):
    ts    = datetime.now(timezone.utc).isoformat()
    pages_str = ", ".join(pages) if pages else "—"
    append_file(WIKI_LOG, f"{ts} | {operation} | {pages_str} | {provenance} | {outcome}\n")
    print(f"  [{operation}] {outcome}")

# ─────────────────────────────────────────────────────────────
# INIT
# Creates wiki directory structure.
# Existing VAPI_*.md corpus files are NOT touched.
# ─────────────────────────────────────────────────────────────

def cmd_init():
    """
    Creates wiki/ directory structure.
    Run once per project. Safe to re-run (idempotent).
    """
    dirs = [
        WIKI_PHASES, WIKI_ENTITIES, WIKI_CONCEPTS,
        WIKI_SYNTH, WIKI_WHATIF, WIKI_BRIEFS,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()

    if not WIKI_INDEX.exists():
        write(WIKI_INDEX, f"""# VAPI Wiki Index

Protocol-Anchored Knowledge Engine — Phase 166
Initialized: {ts}

## VAPI Corpus Files (read-only, used as wiki context by MCP server)
{chr(10).join(f'- [{k}]({v})' for k, v in CORPUS.items() if v.exists())}

## Wiki Pages (generated by vapi_wiki.py + Claude Code)
""")

    if not WIKI_LOG.exists():
        write(WIKI_LOG, f"""# VAPI Wiki Log

Append-only. Never delete entries.
Format: timestamp | operation | pages | provenance | outcome

{ts} | INIT | wiki/ | [SYSTEM] | created
""")

    if not WIKI_SNAPSHOTS.exists():
        write(WIKI_SNAPSHOTS, """# VAPI Wiki Snapshots

Append-only ledger of wiki state — equivalent to VAPI's ceremony beacon.
| Timestamp | SHA-256 (24 chars) | Pages | Log lines |
|-----------|-------------------|-------|-----------|
""")

    if not WIKI_CONTRADICT.exists():
        write(WIKI_CONTRADICT, """# VAPI Wiki Contradictions

Flagged contradictions requiring resolution.
Format: entity | new claim | existing claim | provenance | status

""")

    if not WIKI_BLOCKED.exists():
        write(WIKI_BLOCKED, """# VAPI Wiki Blocked Updates

Claims rejected by invariant enforcement gate.
Format: source | claim | violation | timestamp

""")

    print(f"[INIT] Wiki structure created under wiki/")
    print(f"  wiki/phases/     — one page per phase (phase_166.md, etc.)")
    print(f"  wiki/entities/   — agents, contracts, features, thresholds")
    print(f"  wiki/concepts/   — separation ratio, Mahalanobis, epistemic consensus")
    print(f"  wiki/synthesis/  — cross-entity insights (generated from queries)")
    print(f"  wiki/what_if/    — W1/W2 entries")
    print(f"  wiki/briefs/     — Claude Code ingest briefs (no API needed)")
    print(f"\nCorpus files found:")
    for k, v in CORPUS.items():
        status = "[FOUND]" if v.exists() else "[MISSING]"
        print(f"  {status}  {v}")
    print(f"\nNext: python vapi_wiki.py brief MEMORY.md 166")

# ─────────────────────────────────────────────────────────────
# BRIEF — the no-API ingest operation
#
# Instead of calling an LLM to process the source, this creates
# a structured "brief" that Claude Code reads natively in its
# context window. Claude Code then generates the wiki pages
# directly during the session.
#
# This is the correct architecture: Claude Code IS the LLM.
# ─────────────────────────────────────────────────────────────

def cmd_brief(source_path: str, phase: int):
    """
    Pre-processes a source file into a structured Claude Code brief.
    No API call. Claude Code reads the brief and generates wiki pages.

    The brief tells Claude Code exactly what to do:
    - Which wiki pages to create/update
    - What provenance to use
    - Which invariants to check before writing
    - How to format the output
    - Where to write the files
    """
    source = Path(source_path)
    if not source.exists():
        print(f"ERROR: {source_path} not found")
        return

    text        = source.read_text(encoding="utf-8")
    source_name = source.name
    provenance  = prov(phase, source_name)
    ts          = datetime.now(timezone.utc).isoformat()

    # Pre-scan: extract key metrics for the brief
    # These patterns work for MEMORY.md and VAPI_*.md files
    metrics = _extract_metrics(text)

    # Pre-scan: detect which domains the source touches
    domains = _detect_domains(text)

    # Pre-scan: detect potential invariant violations in source text
    passes, violations = check_invariants(text)

    brief_content = f"""# VAPI Wiki Ingest Brief
## Source: {source_name} | Phase {phase} | {ts}
## Provenance tag: {provenance}

---

## INSTRUCTION TO CLAUDE CODE

You are reading this brief to generate VAPI wiki pages.
No external API is called. You are the LLM.

Do the following in order:
1. Read the source content below
2. For each domain listed, create or update the corresponding wiki page
3. Every factual claim must include: {provenance}
4. Run check_invariants() on your proposed content before writing
   (call: python vapi_wiki.py check "<proposed_content_snippet>")
5. Write each page using:
   python vapi_wiki.py write_page <page_type> "<entity_name>" 166 "<content>"
   OR write the markdown file directly to wiki/<type>/<name>.md
6. After all pages are written: python vapi_wiki.py snapshot

---

## Pre-Scan Results

### Invariant Check on Source
Status: {"PASS — no violations detected in source text" if passes else "WARNINGS DETECTED"}
{chr(10).join(f"  [WARN] {v}" for v in violations) if violations else ""}

### Extracted Metrics
{json.dumps(metrics, indent=2)}

### Domains Detected in Source
{json.dumps(domains, indent=2)}

---

## Pages to Create/Update

Based on domain detection, Claude Code should create these wiki pages:

{_generate_page_plan(domains, phase, source_name)}

---

## Provenance Rules (enforce these — do not skip)

- Every factual claim: {provenance}
- Measured values: {prov(phase, source_name, 'MEASURED')}
- Designed (not yet measured): {prov(phase, source_name, 'DESIGNED')}
- Frozen protocol constants: {prov(phase, 'VAPI_INVARIANTS.md', 'FROZEN')}
- Claims without source: tag as [NEEDS_PROVENANCE]
- Contradictions: preserve BOTH claims, mark [CONTRADICTION: unresolved]

---

## FROZEN VALUES (never modify these in wiki pages)

{json.dumps(FROZEN, indent=2)}

If the source text contradicts any frozen value, flag it as:
[CONTRADICTION: source claims X | frozen value is Y | {provenance}]
Write to: wiki/contradictions.md

---

## Wiki Page Format

Each page must follow this structure:

```markdown
# [Page Type]: [Entity Name]

[VAPI:Phase{phase}:{source_name}:MEASURED]

## Current State
[factual description with provenance on each claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|
| ... | ... | {provenance} | LIVE/DESIGNED/STALE |

## Related Pages
- [[entity_1]]
- [[entity_2]]
```

---

## Source Content

{text[:6000]}
{"... [truncated — full content in " + source_path + "]" if len(text) > 6000 else ""}

---

## After Writing Pages

Run these commands in order:
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot
  python vapi_wiki.py autoresearch_feed

The autoresearch_feed command syncs any wiki gaps into the AutoResearch
experiment log so the next /vapi autoresearch cycle can address them.
"""

    brief_path = WIKI_BRIEFS / f"brief_{source_name}_{phase}.md"
    write(brief_path, brief_content)

    log_op("BRIEF", [str(brief_path)], provenance,
           f"domains={domains['count']}, metrics_extracted={len(metrics)}, "
           f"invariant_violations={len(violations)}")

    print(f"\n[BRIEF] Generated: {brief_path}")
    print(f"\nHow to use this brief:")
    print(f"  1. In Claude Code, read the brief file:")
    print(f"     Read wiki/briefs/brief_{source_name}_{phase}.md")
    print(f"  2. Claude Code generates wiki pages from the instructions")
    print(f"  3. Claude Code writes pages to wiki/")
    print(f"  4. Run: python vapi_wiki.py snapshot")
    print(f"\nNo API key needed — Claude Code IS the intelligence layer.")

def _extract_metrics(text: str) -> dict:
    """Extracts key VAPI metrics from source text using regex."""
    metrics = {}

    patterns = {
        "separation_ratio":    r"(?:separation.{0,20}ratio|ratio).{0,10}([\d.]+)",
        "bridge_tests":        r"bridge.{0,10}(\d{1,4}).{0,10}(?:test|pass)",
        "sdk_tests":           r"sdk.{0,10}(\d{1,3}).{0,10}(?:test|pass)",
        "hardhat_tests":       r"hardhat.{0,10}(\d{1,3}).{0,10}(?:test|pass)",
        "agents":              r"(\d{1,2}).{0,10}agents?.{0,10}(?:live|active|fleet)",
        "phase":               r"phase.{0,5}(\d{2,3})",
        "contracts":           r"(\d{2}).{0,10}contracts?.{0,10}live",
        "l4_anomaly":          r"anomaly.{0,10}([\d.]+)",
        "l4_continuity":       r"continuity.{0,10}([\d.]+)",
        "epistemic":           r"epistemic.{0,20}([\d.]+)",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            metrics[key] = m.group(1)

    return metrics

def _detect_domains(text: str) -> dict:
    """Detects which VAPI domains the source text covers."""
    low = text.lower()
    domains = {
        "phase_state":      any(x in low for x in ["phase 16", "current phase", "phase complete"]),
        "separation_ratio": any(x in low for x in ["separation ratio", "inter-person", "pooled ratio"]),
        "agents":           any(x in low for x in ["agent fleet", "agent #", "agent fleet"]),
        "contracts":        any(x in low for x in ["contract", "deployed", "testnet"]),
        "l4_calibration":   any(x in low for x in ["l4", "mahalanobis", "anomaly threshold"]),
        "what_if":          any(x in low for x in ["w1", "w2", "w3", "what_if", "failure mode"]),
        "privacy":          any(x in low for x in ["gdpr", "erasure", "temporal decay", "consent"]),
        "zk_circuit":       any(x in low for x in ["poseidon", "groth16", "npublic", "zkp"]),
        "ioswarm":          any(x in low for x in ["ioswarm", "quorum", "operator node"]),
    }
    domains["count"] = sum(1 for v in domains.values() if v is True)
    return domains

def _generate_page_plan(domains: dict, phase: int, source_name: str) -> str:
    """Generates the list of wiki pages to create based on detected domains."""
    pages = []
    prov_tag = prov(phase, source_name)

    if domains.get("phase_state"):
        pages.append(f"- wiki/phases/phase_{phase}.md [TYPE: PHASE]\n"
                     f"  Content: what was built, test counts, state flags, separation ratio\n"
                     f"  Provenance: {prov_tag}")

    if domains.get("separation_ratio"):
        pages.append(f"- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]\n"
                     f"  Content: current value, gate, root cause, mixed probe status\n"
                     f"  Provenance: {prov_tag}")

    if domains.get("agents"):
        pages.append(f"- wiki/entities/agent_fleet.md [TYPE: ENTITY]\n"
                     f"  Content: all {phase} agents, new agents added this phase, epistemic threshold\n"
                     f"  Provenance: {prov_tag}")

    if domains.get("l4_calibration"):
        pages.append(f"- wiki/entities/l4_thresholds.md [TYPE: ENTITY]\n"
                     f"  Content: 7.009/5.367 frozen values, staleness (12-feat vs 13-feat), recalibration candidate\n"
                     f"  Provenance: {prov(phase, 'VAPI_INVARIANTS.md', 'FROZEN')}")

    if domains.get("what_if"):
        pages.append(f"- wiki/what_if/w1_w2_entries.md [TYPE: WHAT_IF]\n"
                     f"  Content: new W1/W2 entries from this phase\n"
                     f"  Provenance: {prov_tag}")

    if domains.get("privacy"):
        pages.append(f"- wiki/concepts/privacy_framework.md [TYPE: CONCEPT]\n"
                     f"  Content: GDPR Art.17 erasure, consent ledger, temporal decay TBD(t)=e^{{-λt}}\n"
                     f"  Provenance: {prov_tag}")

    if domains.get("zk_circuit"):
        pages.append(f"- wiki/concepts/zk_circuit.md [TYPE: CONCEPT]\n"
                     f"  Content: Groth16, BN254, Poseidon(8), nPublic=5, ceremony block #41723255\n"
                     f"  Provenance: {prov(phase, 'VAPI_INVARIANTS.md', 'FROZEN')}")

    if not pages:
        pages.append("- wiki/synthesis/misc.md [TYPE: SYNTHESIS]\n"
                     "  Content: general state update from this source")

    return "\n".join(pages)

# ─────────────────────────────────────────────────────────────
# INGEST (legacy/direct — no brief, Claude Code writes pages
# immediately in the session by reading this output)
# ─────────────────────────────────────────────────────────────

def cmd_ingest(source_path: str, phase: int):
    """
    Thin wrapper that runs brief() and prints a Claude Code instruction.
    Claude Code reads the brief and writes the pages — no API needed.
    """
    cmd_brief(source_path, phase)
    print(f"\n[INGEST] Brief generated. Claude Code will:")
    print(f"  1. Read the brief above")
    print(f"  2. Generate wiki pages from the source content")
    print(f"  3. Write them to wiki/ directly (no API call)")

# ─────────────────────────────────────────────────────────────
# WRITE PAGE — called by Claude Code to write a wiki page
# with invariant enforcement before the write
# ─────────────────────────────────────────────────────────────

def cmd_write_page(page_type: str, entity_name: str, phase: int, content: str):
    """
    Called by Claude Code to write a wiki page.
    Enforces invariants before writing. Logs the result.
    If blocked, writes to wiki/blocked_updates.md.
    """
    passes, violations = check_invariants(content)
    safe = re.sub(r"[^\w\s\-]", "", entity_name).strip().replace(" ", "_").lower()

    page_type_map = {
        "phase":    WIKI_PHASES   / f"phase_{phase}.md",
        "entity":   WIKI_ENTITIES / f"{safe}.md",
        "concept":  WIKI_CONCEPTS / f"{safe}.md",
        "synthesis":WIKI_SYNTH    / f"{safe}.md",
        "what_if":  WIKI_WHATIF   / f"{safe}.md",
    }

    page_path = page_type_map.get(page_type.lower(),
                                  WIKI_ENTITIES / f"{safe}.md")

    provenance = prov(phase, "claude_code_session")

    if not passes:
        ts = datetime.now(timezone.utc).isoformat()
        block_entry = (
            f"\n## Blocked: {entity_name} ({ts})\n"
            + "\n".join(f"- {v}" for v in violations)
            + "\n"
        )
        append_file(WIKI_BLOCKED, block_entry)
        log_op("BLOCKED", [str(page_path)], provenance,
               f"{len(violations)} violations — not written")
        print(f"\n[BLOCKED] {entity_name}")
        for v in violations:
            print(f"  [VIOLATION] {v}")
        return False

    # Score against eval harness
    score_result = score_wiki_proposal(content)
    if not score_result["passed"]:
        print(f"[SCORE] Failed harness: {score_result.get('harness_detail', 'invariant violation')}")
        return False

    write(page_path, content)
    _update_index(page_path)
    log_op("WRITE", [str(page_path)], provenance,
           f"type={page_type}, score={score_result.get('score', 'N/A')}")
    print(f"[WRITE] {page_path}")
    return True

# ─────────────────────────────────────────────────────────────
# CHECK — inline invariant check (used by Claude Code before writing)
# ─────────────────────────────────────────────────────────────

def cmd_check(text: str):
    """Checks content against invariants. Prints result. No file writes."""
    passes, violations = check_invariants(text)
    if passes:
        print("[CHECK] PASS — no invariant violations")
    else:
        print(f"[CHECK] BLOCKED — {len(violations)} violations:")
        for v in violations:
            print(f"  [VIOLATION] {v}")
    return passes, violations

# ─────────────────────────────────────────────────────────────
# WHAT_IF — appends a new W1 or W2 entry to VAPI_WHAT_IF.md
# MCP server's vapi_query_what_if will find it immediately
# ─────────────────────────────────────────────────────────────

def cmd_what_if(topic: str, layer: str, phase: int,
                mechanism: str = "", mitigation: str = ""):
    """
    Appends a new WHAT_IF entry to VAPI_WHAT_IF.md.
    The MCP server's vapi_query_what_if tool reads VAPI_WHAT_IF.md directly,
    so the entry is immediately queryable via the MCP server.
    Also writes to wiki/what_if/ and AR_WHATIF corpus.
    """
    what_if_path = CORPUS.get("what_if")
    if not what_if_path or not what_if_path.exists():
        print(f"ERROR: VAPI_WHAT_IF.md not found at {what_if_path}")
        return

    # Determine next ID
    existing = what_if_path.read_text(encoding="utf-8")
    layer_up  = layer.upper()
    existing_ids = re.findall(rf"{layer_up}-(\d+)", existing)
    next_n    = max((int(x) for x in existing_ids), default=0) + 1
    entry_id  = f"{layer_up}-{next_n:03d}"

    ts         = datetime.now(timezone.utc).isoformat()
    provenance = prov(phase, "vapi_wiki.py", "MEASURED")

    if layer_up == "W1":
        entry = f"""
### {entry_id}: {topic} (Phase {phase}, Wiki-Generated)

**Status**: OPEN
**Detected by**: Skill 14 PostCode Sweep / vapi_wiki.py
**Phase**: Phase {phase}
**Timestamp**: {ts}

**Failure mechanism**: {mechanism or "[Claude Code: describe the physically/cryptographically/economically grounded failure]"}

**Implication**: [Claude Code: what fails if unmitigated?]

**Mitigation**: {mitigation or "[Claude Code: specify phase candidate and concrete fix]"}

**Invariants affected**: [Claude Code: list which of the frozen values are at risk]

**Separation ratio impact**: [Claude Code: None / Low / Medium / High]

{provenance}
"""
    else:  # W2
        entry = f"""
### {entry_id}: {topic} (Phase {phase}, Wiki-Generated)

**Status**: PROPOSED
**Detected by**: vapi_wiki.py knowledge accumulation
**Phase**: Phase {phase}
**Timestamp**: {ts}

**Mechanism**: {mechanism or "[Claude Code: describe the concrete novel mechanism]"}

**Exclusive because**: [Claude Code: why competitors cannot replicate without 228B PoAC + PITL]

**Phase candidate**: Phase {phase + 1}

**Connection to ratio**: [Claude Code: how does this advance separation ratio or tournament launch?]

{provenance}
"""

    append_file(what_if_path, entry)

    # Also write to wiki/what_if/ and AutoResearch corpus
    safe      = re.sub(r"[^\w\s\-]", "", topic).strip().replace(" ", "_").lower()
    wiki_path = WIKI_WHATIF / f"{entry_id}_{safe}.md"
    write(wiki_path, f"# {layer_up}: {topic}\n\n{entry}")

    ar_path = AR_WHATIF / f"{entry_id}_{safe}.md"
    if AR_WHATIF.exists():
        write(ar_path, f"# {layer_up}: {topic}\n\n{entry}")

    _update_index(wiki_path)
    log_op("WHAT_IF", [str(what_if_path), str(wiki_path)], provenance,
           f"id={entry_id}, layer={layer_up}")

    print(f"\n[WHAT_IF] {entry_id}: {topic}")
    print(f"  Written to: VAPI_WHAT_IF.md (MCP server reads this)")
    print(f"  Written to: wiki/what_if/{entry_id}_{safe}.md")
    if ar_path and AR_WHATIF.exists():
        print(f"  Written to: vapi-autoresearch/what_if_corpus/")
    print(f"\n  MCP tool vapi_query_what_if(\"{topic}\") will find this immediately.")
    print(f"  Claude Code: fill in the [Claude Code: ...] placeholders.")

# ─────────────────────────────────────────────────────────────
# AUTORESEARCH FEED
# Syncs wiki knowledge gaps into AutoResearch experiment log.
# The next /vapi autoresearch cycle can then address them.
# ─────────────────────────────────────────────────────────────

def cmd_autoresearch_feed():
    """
    Scans wiki pages for [WIKI_GAP] and [NEEDS_PROVENANCE] flags.
    Syncs them into the AutoResearch experiments/log.jsonl as
    improvement candidates for the next /vapi autoresearch cycle.
    Also extracts the current separation ratio from MEMORY.md
    to update AutoResearch's KNOWN_GAPS.
    """
    if not AR_LOG.parent.exists():
        print(f"[AR_FEED] AutoResearch log directory not found: {AR_LOG.parent}")
        print(f"  Run /vapi autoresearch first to initialize it.")
        return

    gaps     = []
    ts       = datetime.now(timezone.utc).isoformat()

    # Scan wiki for gaps
    if WIKI.exists():
        for page in WIKI.rglob("*.md"):
            content = page.read_text(encoding="utf-8")
            if "[WIKI_GAP]" in content:
                gaps.append({
                    "type":   "wiki_gap",
                    "source": str(page),
                    "count":  content.count("[WIKI_GAP]"),
                })
            if "[NEEDS_PROVENANCE]" in content:
                gaps.append({
                    "type":   "needs_provenance",
                    "source": str(page),
                    "count":  content.count("[NEEDS_PROVENANCE]"),
                })

    # Extract current separation ratio from MEMORY.md
    memory = read(CORPUS.get("memory", Path("MEMORY.md")))
    ratio_m = re.search(r"ratio[:\s]+([\d.]+)", memory, re.IGNORECASE)
    current_ratio = float(ratio_m.group(1)) if ratio_m else None

    # Write to AutoResearch experiment log
    entry = {
        "timestamp":       ts,
        "source":          "vapi_wiki.autoresearch_feed",
        "wiki_gaps":       gaps,
        "gap_count":       len(gaps),
        "separation_ratio_current": current_ratio,
        "separation_gate": float(FROZEN["separation_gate"]),
        "gap_to_gate":     round(float(FROZEN["separation_gate"]) - (current_ratio or 0), 3),
        "recommendation":  (
            "Run /vapi autoresearch with priority=separation_ratio "
            "to address open wiki gaps and advance toward 0.70 gate."
            if current_ratio and current_ratio < float(FROZEN["separation_gate"])
            else "Separation ratio above gate — focus on wiki provenance gaps."
        ),
    }

    AR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AR_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    log_op("AR_FEED", [str(AR_LOG)],
           prov(166, "vapi_wiki.py"),
           f"gaps={len(gaps)}, ratio={current_ratio}, gate={FROZEN['separation_gate']}")

    print(f"\n[AR_FEED] Synced to AutoResearch experiment log")
    print(f"  Wiki gaps found: {len(gaps)}")
    print(f"  Separation ratio: {current_ratio} (gate: {FROZEN['separation_gate']})")
    print(f"\n  Run: python vapi_autoresearch.py --cycle 1 --priority separation_ratio")

# ─────────────────────────────────────────────────────────────
# LINT — pure regex scan, no LLM
# ─────────────────────────────────────────────────────────────

def cmd_lint():
    """
    Scans wiki for health issues. Pure regex — no API.
    Outputs structured report and writes wiki/lint_report.md.
    """
    print("\n[LINT] Scanning wiki...")

    all_pages = list(WIKI.rglob("*.md")) if WIKI.exists() else []
    issues    = {
        "needs_provenance":    [],
        "unresolved_contradict": [],
        "wiki_gaps":           [],
        "stale_designed":      [],
        "invariant_in_wiki":   [],
        "orphan_pages":        [],
        "blocked_backlog":     0,
        "contradict_backlog":  0,
    }

    index_text = read(WIKI_INDEX)

    for page in all_pages:
        if page.name in ("log.md", "snapshots.md", "index.md",
                          "contradictions.md", "blocked_updates.md",
                          "lint_report.md"):
            continue

        content = page.read_text(encoding="utf-8")
        rel     = str(page.relative_to(WIKI))

        if "[NEEDS_PROVENANCE]" in content:
            issues["needs_provenance"].append(rel)

        if "[CONTRADICTION: unresolved]" in content:
            issues["unresolved_contradict"].append(rel)

        if "[WIKI_GAP]" in content:
            issues["wiki_gaps"].append(rel)

        if "[DESIGNED:" in content:
            issues["stale_designed"].append(rel)

        # Spot-check frozen values in wiki pages
        _, viol = check_invariants(content)
        if viol:
            issues["invariant_in_wiki"].append(
                f"{rel}: {viol[0][:60]}...")

        if rel not in index_text:
            issues["orphan_pages"].append(rel)

    issues["blocked_backlog"]   = read(WIKI_BLOCKED).count("\n## Blocked:")
    issues["contradict_backlog"] = read(WIKI_CONTRADICT).count("## From")

    # Severity classification
    p0 = (issues["invariant_in_wiki"] or
          [x for x in issues["needs_provenance"]
           if "frozen" in x or "invariant" in x])
    p1 = issues["unresolved_contradict"] + issues["wiki_gaps"]
    p2 = issues["orphan_pages"] + issues["stale_designed"]

    health = max(0, 100
                 - len(p0) * 20
                 - len(p1) * 10
                 - len(p2) * 3
                 - issues["blocked_backlog"] * 5)

    report = f"""# VAPI Wiki Lint Report
Generated: {datetime.now(timezone.utc).isoformat()}
Wiki health score: {health}/100

## Summary

| Issue | Count | Severity |
|-------|-------|----------|
| Invariant violations in wiki | {len(issues['invariant_in_wiki'])} | P0 |
| [NEEDS_PROVENANCE] flags | {len(issues['needs_provenance'])} | P0 |
| [CONTRADICTION: unresolved] | {len(issues['unresolved_contradict'])} | P1 |
| [WIKI_GAP] flags | {len(issues['wiki_gaps'])} | P1 |
| Blocked update backlog | {issues['blocked_backlog']} | P1 |
| Orphan pages | {len(issues['orphan_pages'])} | P2 |
| [DESIGNED:] stale claims | {len(issues['stale_designed'])} | P2 |

## P0 Actions (resolve before next ingest)
{chr(10).join(f"- {x}" for x in p0) or "- None"}

## P1 Actions
{chr(10).join(f"- {x}" for x in p1[:5]) or "- None"}

## P2 Actions
{chr(10).join(f"- {x}" for x in p2[:5]) or "- None"}

## Commands to Resolve
```bash
# Re-ingest source files to fill provenance gaps
python vapi_wiki.py brief MEMORY.md 166
python vapi_wiki.py brief VAPI_INVARIANTS.md 166

# Feed gaps to AutoResearch
python vapi_wiki.py autoresearch_feed

# Take snapshot after resolving
python vapi_wiki.py snapshot
```
"""

    write(WIKI / "lint_report.md", report)
    log_op("LINT", [str(WIKI / "lint_report.md")],
           prov(166, "vapi_wiki.py"),
           f"health={health}, p0={len(p0)}, p1={len(p1)}, p2={len(p2)}")

    print(report)
    return health

# ─────────────────────────────────────────────────────────────
# SNAPSHOT — cryptographic commitment to wiki state
# ─────────────────────────────────────────────────────────────

def cmd_snapshot():
    """
    SHA-256 of all wiki pages. Appends to wiki/snapshots.md.
    This is the wiki's ceremony beacon — proves what it contained
    at each protocol milestone.
    """
    h       = wiki_hash()
    ts      = datetime.now(timezone.utc).isoformat()
    n_pages = len(list(WIKI.rglob("*.md"))) if WIKI.exists() else 0
    n_log   = read(WIKI_LOG).count("\n")

    append_file(
        WIKI_SNAPSHOTS,
        f"| {ts} | sha256:{h[:24]}...{h[-8:]} | {n_pages} | {n_log} |\n"
    )

    log_op("SNAPSHOT", [str(WIKI_SNAPSHOTS)],
           f"[SNAPSHOT:{h[:12]}]",
           f"pages={n_pages}, log_lines={n_log}")

    print(f"\n[SNAPSHOT]")
    print(f"  Timestamp: {ts}")
    print(f"  SHA-256:   {h}")
    print(f"  Pages:     {n_pages}")
    print(f"  Log lines: {n_log}")
    return h

# ─────────────────────────────────────────────────────────────
# STATUS — full system state summary
# ─────────────────────────────────────────────────────────────

def cmd_status():
    """Shows current wiki state, corpus coverage, and integration health."""
    print("\n[STATUS] VAPI Wiki Engine")
    print(f"  Wiki root: {WIKI.absolute()}")
    print(f"  Pages:     {len(list(WIKI.rglob('*.md'))) if WIKI.exists() else 0}")
    print(f"  Log lines: {read(WIKI_LOG).count(chr(10))}")

    snapshots = read(WIKI_SNAPSHOTS)
    snap_lines = [l for l in snapshots.split("\n") if "sha256:" in l]
    if snap_lines:
        print(f"  Snapshots: {len(snap_lines)} (last: {snap_lines[-1][:60]}...)")

    print(f"\n  Corpus files:")
    for k, path in CORPUS.items():
        status = f"[FOUND {path.stat().st_size // 1024}KB]" if path.exists() else "[MISSING]"
        print(f"    {status}  {path}")

    print(f"\n  MCP Server integration:")
    mcp = ROOT / "knowledge_server.py"
    print(f"    {'[FOUND]' if mcp.exists() else '[MISSING]'}  knowledge_server.py (reads same VAPI_*.md files)")

    print(f"\n  AutoResearch integration:")
    print(f"    {'[FOUND]' if AR_LOG.exists() else '[ABSENT]'}  experiments/log.jsonl")
    print(f"    {'[FOUND]' if AR_PROGRAM.exists() else '[ABSENT]'}  program.md")
    print(f"    {'[FOUND]' if HARNESS_PATH.exists() else '[ABSENT]'}  vapi_eval_harness.py (for scoring)")

    contradict_count = read(WIKI_CONTRADICT).count("## From") if WIKI_CONTRADICT.exists() else 0
    blocked_count    = read(WIKI_BLOCKED).count("## Blocked:") if WIKI_BLOCKED.exists() else 0
    print(f"\n  Contradiction backlog: {contradict_count}")
    print(f"  Blocked updates:       {blocked_count}")

# ─────────────────────────────────────────────────────────────
# INDEX helper
# ─────────────────────────────────────────────────────────────

def _update_index(page_path: Path):
    existing = read(WIKI_INDEX)
    rel      = str(page_path)
    name     = page_path.stem.replace("_", " ").title()
    link     = f"- [{name}]({rel})\n"
    if rel not in existing:
        append_file(WIKI_INDEX, link)

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

COMMANDS = {
    "init":             (cmd_init,            "Initialize wiki directory structure"),
    "brief":            (cmd_brief,           "Generate Claude Code ingest brief (no API)"),
    "ingest":           (cmd_ingest,          "Alias for brief — generates brief for Claude Code"),
    "check":            (cmd_check,           "Check text against invariants"),
    "write_page":       (cmd_write_page,      "Write a wiki page (with invariant enforcement)"),
    "what_if":          (cmd_what_if,         "Append W1/W2 entry to VAPI_WHAT_IF.md"),
    "autoresearch_feed":(cmd_autoresearch_feed,"Sync wiki gaps to AutoResearch experiment log"),
    "lint":             (cmd_lint,            "Scan wiki for health issues (no API)"),
    "snapshot":         (cmd_snapshot,        "Cryptographic SHA-256 snapshot of wiki state"),
    "status":           (cmd_status,          "Show wiki and integration health"),
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("VAPI Wiki Engine — Protocol-Anchored Knowledge Engine (no API)")
        print("\nCommands:")
        for cmd, (_, desc) in COMMANDS.items():
            print(f"  {cmd:<22}  {desc}")
        print("\nExamples:")
        print("  python vapi_wiki.py init")
        print("  python vapi_wiki.py brief MEMORY.md 166")
        print("  python vapi_wiki.py check \"SHA-256(raw[:228])\"")
        print("  python vapi_wiki.py what_if \"enrollment count gate\" W1 166")
        print("  python vapi_wiki.py lint")
        print("  python vapi_wiki.py snapshot")
        return

    cmd = sys.argv[1].lower()

    if cmd == "init":
        cmd_init()
    elif cmd in ("brief", "ingest"):
        if len(sys.argv) < 4:
            print(f"Usage: python vapi_wiki.py {cmd} <source_file> <phase>")
            sys.exit(1)
        cmd_brief(sys.argv[2], int(sys.argv[3]))
    elif cmd == "check":
        if len(sys.argv) < 3:
            text = sys.stdin.read()
        else:
            text = " ".join(sys.argv[2:])
        cmd_check(text)
    elif cmd == "write_page":
        if len(sys.argv) < 5:
            print("Usage: python vapi_wiki.py write_page <type> <entity> <phase> <content>")
            sys.exit(1)
        cmd_write_page(sys.argv[2], sys.argv[3], int(sys.argv[4]),
                       sys.argv[5] if len(sys.argv) > 5 else sys.stdin.read())
    elif cmd == "what_if":
        if len(sys.argv) < 5:
            print("Usage: python vapi_wiki.py what_if <topic> <W1|W2> <phase> [mechanism] [mitigation]")
            sys.exit(1)
        mechanism  = sys.argv[5] if len(sys.argv) > 5 else ""
        mitigation = sys.argv[6] if len(sys.argv) > 6 else ""
        cmd_what_if(sys.argv[2], sys.argv[3], int(sys.argv[4]),
                    mechanism, mitigation)
    elif cmd == "autoresearch_feed":
        cmd_autoresearch_feed()
    elif cmd == "lint":
        cmd_lint()
    elif cmd == "snapshot":
        cmd_snapshot()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        print("Run: python vapi_wiki.py --help")
        sys.exit(1)


if __name__ == "__main__":
    main()
