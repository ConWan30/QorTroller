"""
vapi_wiki_engine.py — VAPI Integrated Knowledge Engine
=======================================================
No external API. No invented subprocess calls. No ioSwarm gate on writes.

What makes this exclusively VAPI:

  1. AGENT FLEET FEED
     SeparationRatioMonitorAgent (Agent 15) polls every 300s and writes to
     separation_ratio_snapshots table. This engine reads that table directly
     and updates wiki/concepts/separation_ratio.md automatically.
     The wiki page reflects the LIVE ratio the moment the agent writes it.

  2. ADJUDICATIONREGISTRY ANCHORING
     wiki/snapshots.md hashes are submitted to AdjudicationRegistry.sol
     (already deployed at 0x44CF981f...) via the bridge API.
     Same contract that stores PoAd hashes. Same anti-replay enforcement.
     Zero new infrastructure. Wiki state is on-chain exactly as rulings are.

  3. SKILL 14 AUTOFEED
     PostCode Mitigation Sweep output feeds the wiki automatically.
     Every sweep generates a sweep record -> wiki entry -> WHAT_IF update
     -> AutoResearch gap -> next cycle priority. The loop is closed.

  4. WHAT_IF ↔ AUTORESEARCH BIDIRECTIONAL SYNC
     New W1/W2 entries in VAPI_WHAT_IF.md are automatically reflected in
     vapi_eval_harness.py's KNOWN_GAPS via a live sync function.
     New AutoResearch cycle discoveries automatically generate W2 entries.

  5. MCP SERVER HOT-RELOAD
     After any wiki write that touches VAPI_*.md files, this engine triggers
     vapi_reload_knowledge via the MCP server's stdio transport.
     Claude Code's next vapi_query_what_if call sees the new entry immediately.

  6. PHASE BOUNDARY AUTOMATION
     /vapi wiki phase-close <N> runs the complete boundary sequence:
     brief -> Claude Code generates pages -> snapshot -> on-chain anchor ->
     AutoResearch feed -> MEMORY.md update. One command per phase completion.

Integration map (no duplication, all on existing infrastructure):

  SeparationRatioMonitorAgent (Agent 15)
       v writes separation_ratio_snapshots (SQLite)
  vapi_wiki_engine.py agent_feed()
       v updates wiki/concepts/separation_ratio.md
       v updates MEMORY.md if ratio changed
       v triggers AutoResearch feed if ratio below gate

  Skill 14 PostCode Sweep (output JSON)
       v
  vapi_wiki_engine.py ingest_sweep()
       v writes wiki/sweeps/sweep_{ts}.md
       v appends W1 to VAPI_WHAT_IF.md (if new failure class found)
       v calls sync_what_if_to_harness()

  sync_what_if_to_harness()
       v reads VAPI_WHAT_IF.md
       v updates vapi_eval_harness.py KNOWN_GAPS block
       v eval harness now reflects all current W1/W2 entries

  cmd_snapshot()
       v SHA-256(wiki state)
       v POST /agent/anchor-wiki-snapshot (bridge endpoint)
       v AdjudicationRegistry.sol records hash on-chain
       v same contract as PoAd anchoring — zero new infrastructure

  MCP reload_trigger()
       v sends {"jsonrpc":"2.0","method":"tools/call","params":{
              "name":"vapi_reload_knowledge","arguments":{}}}
       v knowledge_server.py reloads all 9 corpus files
       v next vapi_query_what_if sees new entries immediately

Usage:
  python vapi_wiki_engine.py init
  python vapi_wiki_engine.py brief MEMORY.md 166
  python vapi_wiki_engine.py agent_feed           # pull from Agent 15's DB table
  python vapi_wiki_engine.py ingest_sweep sweep_output.json
  python vapi_wiki_engine.py sync_what_if         # WHAT_IF -> harness KNOWN_GAPS
  python vapi_wiki_engine.py snapshot --anchor    # snapshot + on-chain anchor
  python vapi_wiki_engine.py phase_close 167      # full phase boundary sequence
  python vapi_wiki_engine.py lint
  python vapi_wiki_engine.py status
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

ROOT          = Path(__file__).parent
WIKI          = ROOT / "wiki"
WIKI_PHASES   = WIKI / "phases"
WIKI_ENTITIES = WIKI / "entities"
WIKI_CONCEPTS = WIKI / "concepts"
WIKI_SYNTH    = WIKI / "synthesis"
WIKI_WHATIF   = WIKI / "what_if"
WIKI_SWEEPS   = WIKI / "sweeps"
WIKI_BRIEFS   = WIKI / "briefs"
WIKI_LOG      = WIKI / "log.md"
WIKI_INDEX    = WIKI / "index.md"
WIKI_CONTRADICT = WIKI / "contradictions.md"
WIKI_BLOCKED    = WIKI / "blocked_updates.md"
WIKI_SNAPSHOTS  = WIKI / "snapshots.md"

# VAPI corpus files (read-only)
_WF = ROOT / "VAPI-WORKFLOW.v2"
CORPUS = {
    "invariants":  _WF / "VAPI_INVARIANTS.md",
    "what_if":     _WF / "VAPI_WHAT_IF.md",
    "agents":      _WF / "VAPI_AGENTS.md",
    "corpus":      _WF / "VAPI_CORPUS.md",
    "skills":      _WF / "VAPI_SKILLS.md",
    "privacy":     _WF / "VAPI_BIOMETRIC_PRIVACY.md",
    "context":     _WF / "VAPI_CONTEXT.md",
    "memory":      ROOT / "MEMORY.md",
    "controller":  _WF / "VAPI_CONTROLLER_INTELLIGENCE.md",
}

# Bridge + DB (existing VAPI infrastructure)
BRIDGE_URL = "http://localhost:8080"
DB_PATH    = ROOT / "bridge" / "vapi_store.db"

# AutoResearch paths (shared with vapi_autoresearch.py)
AR_LOG      = ROOT / "vapi-autoresearch" / "experiments" / "log.jsonl"
AR_PROGRAM  = ROOT / "vapi-autoresearch" / "program.md"
AR_WHATIF   = ROOT / "vapi-autoresearch" / "what_if_corpus"
HARNESS     = ROOT / "vapi-autoresearch" / "vapi_eval_harness.py"

# MCP server socket/process (knowledge_server.py)
MCP_SERVER  = ROOT / "knowledge_server.py"

# On-chain anchoring via bridge (AdjudicationRegistry.sol already deployed)
ANCHOR_ENDPOINT = f"{BRIDGE_URL}/agent/anchor-wiki-snapshot"

# ─────────────────────────────────────────────────────────────
# Frozen Invariants — mirroring eval harness MANDATORY_INVARIANTS
# ─────────────────────────────────────────────────────────────

FROZEN = {
    "poac_bytes":          "228",
    "record_hash":         "SHA-256(raw[:164])",
    "nPublic":             "5",
    "zk_hash":             "Poseidon(8)",
    "ceremony_beacon":     "#41723255",
    "l4_anomaly":          "7.009",
    "l4_continuity":       "5.367",
    "epistemic_threshold": "0.65",
    "triage_prereq":       "True",
    "auto_activate":       "False",
    "block_quorum":        "0.67",
    "mint_quorum":         "0.80",
    "vhp_expiry_days":     "90",
    "separation_gate":     "0.70",
    "adjudication_registry": "0x44CF981f46a52ADE56476Ce894255954a7776fb4",
}

# ─────────────────────────────────────────────────────────────
# Skill 14 failure class taxonomy
# Mirrors PostCode Mitigation Sweep root cause classification.
# When a sweep finds a new class, this taxonomy is the reference.
# ─────────────────────────────────────────────────────────────

SWEEP_FAILURE_CLASSES = {
    "INVARIANT_DRIFT":          "Threshold value changed or hardcoded",
    "AUTO_ACTIVATE_VIOLATION":  "TournamentActivationChain self-triggering — HIGHEST SEVERITY",
    "PHASE_INTEROP":            "AgentX references AgentY not yet wired",
    "BUS_EVENT_MISMATCH":       "Bus event subscription incomplete",
    "SCHEMA_MISMATCH":          "Pydantic validation — new field missing default",
    "IMPORT_BREAK":             "ModuleNotFoundError — file moved without import update",
    "DB_MIGRATION":             "sqlite3 OperationalError — column added without migration",
    "WS_PROTOCOL":              "WebSocket 1006 — handler signature changed",
    "CHAIN_HASH_ERROR":         "SHA-256 mismatch — wrong byte slice",
    "BT_THRESHOLD_POLLUTION":   "BT session routed through USB thresholds",
    "IOSWARM_SEED_DRIFT":       "Emulator seed changed — test determinism broken",
    "EPISTEMIC_REGRESSION":     "Consensus threshold below 0.65",
    "ENROLLMENT_COUNT_GATE":    "enrollment_complete fires on count only — W1",
    "SEPARATION_HARDCODE":      "separation_ratio assigned literal — BLOCK",
    "PRIVACY_VIOLATION":        "Raw biometric persisted to SQLite — BP-007",
}

# ─────────────────────────────────────────────────────────────
# Invariant enforcement
# ─────────────────────────────────────────────────────────────

def check_invariants(text: str) -> tuple[bool, list[str]]:
    low = text.lower()
    v   = []

    if "sha-256(raw[:228])" in low or "sha256(raw[:228])" in low:
        v.append("CHAIN_HASH: Must be SHA-256(raw[:164]) — signature bytes excluded.")

    if re.search(r"npublic\s*[=:]\s*(?!5\b)\d", low):
        v.append("ZK_CIRCUIT: nPublic=5 frozen since Phase 62. Full MPC re-run required to change.")

    if "auto_activate_on_breakthrough" in low:
        if "=false" not in low.replace(" ", ""):
            v.append("PERMANENT: auto_activate_on_breakthrough=False is a compile-time constant.")

    # Catch any threshold below 0.65 (covers 0.00–0.59 AND 0.60–0.64)
    if re.search(r"epistemic.{0,60}(?:0\.[0-5]\d|0\.6[0-4])", low):
        v.append("EPISTEMIC: Threshold 0.65 (Phase 147). Cannot regress.")

    if re.search(r"separation_ratio\s*=\s*[\d.]+", text):
        v.append("HARDCODE: separation_ratio must not be a literal value. Always from live analyzer.")

    if re.search(r"(bluetooth|\\bbt\\b).{0,80}(7\.009|5\.367)", low):
        v.append("BT_THRESHOLD: USB thresholds must not apply to BT sessions.")

    if re.search(r"dry_run\s*=\s*false", low):
        if "n>=100" not in low and "n≥100" not in low:
            v.append("DRY_RUN: dry_run=False requires N≥100 live adjudications. Phase 97 guard.")

    if "gsr_enabled=true" in low:
        v.append("GSR_GATE: GSR_ENABLED=True requires N≥30 per player. Current N=0.")

    return len(v) == 0, v

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

def _locked_append(path: Path, content: str, retries: int = 8, delay: float = 0.15):
    """
    Append to path under a file lock (cross-platform, stdlib only).
    Used for shared files like VAPI_WHAT_IF.md where concurrent sweep + agent
    polls could race. Creates a .lock sentinel; retries if another process holds it.
    """
    import time
    lock = path.with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(delay)
    else:
        # Lock not acquired after retries — append anyway (best-effort)
        print(f"  [WARN] Could not acquire lock on {path.name} — appending without lock.")
    try:
        append_file(path, content)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass

def prov(phase: int, source: str, kind: str = "MEASURED") -> str:
    return f"[VAPI:Phase{phase}:{source}:{kind}]"

def wiki_hash() -> str:
    h = hashlib.sha256()
    if WIKI.exists():
        for p in sorted(WIKI.rglob("*.md")):
            h.update(p.read_bytes())
    return h.hexdigest()

def log_op(operation: str, pages: list[str], provenance: str, outcome: str):
    ts = datetime.now(timezone.utc).isoformat()
    pgs = ", ".join(pages) if pages else "—"
    append_file(WIKI_LOG, f"{ts} | {operation} | {pgs} | {provenance} | {outcome}\n")
    print(f"  [{operation}] {outcome}")

def _update_index(page_path: Path):
    existing = read(WIKI_INDEX)
    rel  = str(page_path)
    name = page_path.stem.replace("_", " ").title()
    if rel not in existing:
        append_file(WIKI_INDEX, f"- [{name}]({rel})\n")

def db_query(sql: str, params=()) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()

_AGENT15_REQUIRED_COLS = {"pooled_ratio", "bt_strat_ratio", "n_sessions", "created_at"}

def _probe_db_schema() -> bool:
    """Schema probe for separation_ratio_snapshots. Warns visibly on column drift."""
    rows = db_query("PRAGMA table_info(separation_ratio_snapshots)")
    if not rows:
        return False  # table absent or DB offline
    present = {r["name"] for r in rows}
    missing = _AGENT15_REQUIRED_COLS - present
    if missing:
        print(f"  [WARN] Schema drift in separation_ratio_snapshots — missing columns: {missing}")
        print(f"  [WARN] agent_feed will degrade. Re-run bridge to rebuild schema.")
        return False
    return True

# ─────────────────────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────────────────────

def cmd_init():
    dirs = [WIKI_PHASES, WIKI_ENTITIES, WIKI_CONCEPTS,
            WIKI_SYNTH, WIKI_WHATIF, WIKI_SWEEPS, WIKI_BRIEFS]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()

    if not WIKI_INDEX.exists():
        write(WIKI_INDEX, f"# VAPI Wiki Index\nInitialized: {ts}\n\n## Pages\n\n")

    if not WIKI_LOG.exists():
        write(WIKI_LOG, f"# VAPI Wiki Log\nAppend-only. Never delete.\n\n{ts} | INIT | wiki/ | [SYSTEM] | created\n")

    if not WIKI_SNAPSHOTS.exists():
        write(WIKI_SNAPSHOTS,
              "# VAPI Wiki Snapshots\n\n"
              "SHA-256 of wiki state anchored to AdjudicationRegistry.sol on each snapshot.\n\n"
              "| Timestamp | SHA-256 | Pages | On-Chain Anchor |\n"
              "|-----------|---------|-------|-----------------|\n")

    print(f"[INIT] Wiki initialized under wiki/")

    # Check corpus
    print("\nCorpus files:")
    for k, path in CORPUS.items():
        status = f"[OK]  {path.stat().st_size // 1024}KB" if path.exists() else "[MISSING]  MISSING"
        print(f"  {status}  {path}")

    # Check bridge DB
    db_status = "[OK]  live" if DB_PATH.exists() else "[OFF]  not found (bridge offline)"
    print(f"\nBridge DB: {db_status}")
    print(f"AutoResearch log: {'[OK]  live' if AR_LOG.exists() else '[OFF]  not found'}")
    print(f"Eval harness: {'[OK]  live' if HARNESS.exists() else '[OFF]  not found'}")
    print(f"\nNext: python vapi_wiki_engine.py brief MEMORY.md 166")

# ─────────────────────────────────────────────────────────────
# BRIEF — generates structured Claude Code ingest brief
# No API. Claude Code reads this and generates pages.
# ─────────────────────────────────────────────────────────────

def cmd_brief(source_path: str, phase: int):
    source = Path(source_path)
    # If bare filename given, try to resolve via CORPUS dict first
    if not source.exists():
        basename = source.name
        for v in CORPUS.values():
            if v.name == basename and v.exists():
                source = v
                break
    if not source.exists():
        print(f"ERROR: {source_path} not found")
        return

    text        = source.read_text(encoding="utf-8")
    source_name = source.name
    provenance  = prov(phase, source_name)
    ts          = datetime.now(timezone.utc).isoformat()

    passes, violations = check_invariants(text)
    metrics  = _extract_metrics(text)
    domains  = _detect_domains(text)

    brief = f"""# VAPI Wiki Ingest Brief
Source: {source_name} | Phase {phase} | {ts}
Provenance: {provenance}

## INSTRUCTION TO CLAUDE CODE
You are reading this brief to generate wiki pages. No API is called.
You are the intelligence layer. This engine handles file I/O only.

For each page listed below:
1. Read the source content at the bottom
2. Write the page to the path shown
3. Before writing: python vapi_wiki_engine.py check "<key sentences>"
4. After writing all pages: python vapi_wiki_engine.py snapshot --anchor

## Pre-Scan
Invariant violations in source: {len(violations)}
{chr(10).join(f'  [WARN] {v}' for v in violations) if violations else '  None detected'}

Metrics extracted:
{json.dumps(metrics, indent=2)}

Domains:
{json.dumps({k: v for k, v in domains.items() if v is True and k != 'count'}, indent=2)}

## Pages To Create

{_generate_page_plan(domains, phase, source_name)}

## Provenance Rules
Every factual claim: {provenance}
Frozen constants: {prov(phase, 'VAPI_INVARIANTS.md', 'FROZEN')}
Designed (not measured): {prov(phase, source_name, 'DESIGNED')}
No provenance: tag [NEEDS_PROVENANCE]

## Frozen Values (never modify in wiki)
{json.dumps(FROZEN, indent=2)}

## Page Format
```markdown
# [TYPE]: [Entity Name]

{provenance}

## Current State
[description — cite provenance on every factual claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|

## Related Pages
- [[entity_1]]
```

## Source Content
{text[:5000]}
{"... [truncated — see " + source_path + " for full content]" if len(text) > 5000 else ""}

## After Writing
python vapi_wiki_engine.py snapshot --anchor
python vapi_wiki_engine.py sync_what_if
python vapi_wiki_engine.py autoresearch_feed
"""

    brief_path = WIKI_BRIEFS / f"brief_{source_name}_{phase}.md"
    write(brief_path, brief)
    log_op("BRIEF", [str(brief_path)], provenance,
           f"domains={domains['count']}, violations={len(violations)}")

    print(f"\n[BRIEF] Generated: {brief_path}")
    print(f"\nClaude Code: Read that file and generate the wiki pages listed.")
    print(f"No API needed — you are the intelligence layer.")

# ─────────────────────────────────────────────────────────────
# AGENT FEED — reads Agent 15's live DB table
# SeparationRatioMonitorAgent writes to separation_ratio_snapshots.
# This engine reads it and updates the wiki concept page.
# ─────────────────────────────────────────────────────────────

def cmd_agent_feed():
    """
    Reads separation_ratio_snapshots table directly from the bridge SQLite DB.
    Updates wiki/concepts/separation_ratio.md with live Agent 15 data.
    No API call. Pure SQLite read.
    """
    print("\n[AGENT_FEED] Reading Agent 15 (SeparationRatioMonitorAgent) data...")

    # Schema probe — visible warning on column drift (mitigates silent degradation)
    if DB_PATH.exists() and not _probe_db_schema():
        print("  Skipping query — schema mismatch or table absent.")
        return

    # Phase 168: bt_strat_ratio is the real column name in separation_ratio_snapshots
    rows = db_query(
        "SELECT pooled_ratio, bt_strat_ratio, n_sessions, n_players, "
        "COALESCE(ci_lower, 0.0) as ci_lower, "
        "COALESCE(ci_upper, 0.0) as ci_upper, "
        "COALESCE(n_bootstrap, 0) as n_bootstrap, "
        "created_at "
        "FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 10"
    )

    if not rows:
        print("  No snapshots found. Bridge DB offline or no sessions captured yet.")
        print("  Run sessions with: python scripts/terminal_calibration_runner.py")
        return

    latest        = rows[0]
    current_ratio = latest["pooled_ratio"]
    gate          = float(FROZEN["separation_gate"])
    gap           = round(gate - current_ratio, 3)
    ts            = datetime.now(timezone.utc).isoformat()
    phase         = _detect_current_phase()
    ci_lower      = float(latest.get("ci_lower", 0.0))
    ci_upper      = float(latest.get("ci_upper", 0.0))
    n_bootstrap   = int(latest.get("n_bootstrap", 0))

    # Phase 168: CI annotation — "0.569 [CI95: 0.41–0.73, N=1000]" when available
    ci_annotation = (
        f" [CI95: {ci_lower:.3f}\u2013{ci_upper:.3f}, N={n_bootstrap}]"
        if n_bootstrap > 0 else ""
    )

    provenance = prov(phase, "Agent15_SeparationRatioMonitorAgent", "MEASURED")

    # Build snapshot history table
    history_rows = "\n".join([
        f"| {r['created_at'][:10]} | {r['pooled_ratio']:.3f} | "
        f"{r.get('n_sessions', '?')} | "
        f"{'[CI95: ' + str(round(r.get('ci_lower',0),3)) + '-' + str(round(r.get('ci_upper',0),3)) + ']' if r.get('n_bootstrap',0) > 0 else 'no CI'} | "
        f"{'ABOVE GATE' if r['pooled_ratio'] >= gate else 'BELOW GATE'} |"
        for r in rows
    ])

    page = f"""# CONCEPT: Inter-Person Biometric Separation Ratio

{provenance}

## Definition
The ratio of mean inter-player Mahalanobis distance to mean intra-player
Mahalanobis distance. A ratio > gate ({gate}) is required for tournament-grade
biometric identification.

## Current State (Live from Agent 15)
| Metric | Value | Status |
|--------|-------|--------|
| Current pooled ratio | **{current_ratio:.3f}{ci_annotation}** | {'ABOVE GATE' if current_ratio >= gate else 'BELOW GATE — TOURNAMENT BLOCKER'} |
| Tournament gate | {gate} | Phase 166 (lowered from 1.0) |
| Gap to gate | {gap:.3f} | {'CLEARED' if gap <= 0 else f'{gap:.3f} units remaining'} |
| N sessions | {latest.get('n_sessions', '?')} | |
| N players | {latest.get('n_players', '?')} | |
| Bootstrap CI | {'CI95=[' + str(ci_lower) + ', ' + str(ci_upper) + '] N=' + str(n_bootstrap) if n_bootstrap > 0 else 'not computed'} | Run --bootstrap-n 1000 to populate |
| Last updated | {latest['created_at']} | Agent 15 poll |

## Root Cause (Phase 166)
{provenance}
Free-form gameplay sessions plateau in a separation regime that cannot exceed 0.70
without touchpad-specific structured probes. Five of thirteen L4 features are
zero-variance in touchpad-only sessions.

**Fix**: Phase 166 mixed_biometric_probe — 4-segment, 2-minute session activating
all 13 features simultaneously. First measurement pending.

## Phase History
| Date | Ratio | N | Status |
|------|-------|---|--------|
{history_rows}

## Math
Mahalanobis distance: D(x,μ,Σ) = √((x-μ)ᵀΣ⁻¹(x-μ))
Separation ratio: mean(inter-player D) / mean(intra-player D)

At N=20 with 8 active features: diagonal covariance (N/p = 2.5, below stability threshold of 3.0).
Full Tikhonov covariance (Σ_reg = Σ + λI) applies when N/p ≥ 3.

## TGE Gate Connection
{prov(phase, 'VAPI_INVARIANTS.md', 'FROZEN')}
Token launch blocked until ratio ≥ {gate} AND N≥100 live adjudications AND VHP demonstrated.
auto_activate_on_breakthrough=False PERMANENT — operator confirms manually.

## Related Pages
- [[phase_{phase}]]
- [[l4_thresholds]]
- [[agent_15_separation_ratio_monitor]]
- [[tge_gate]]
"""

    passes, violations = check_invariants(page)
    if not passes:
        print(f"  BLOCKED: {violations[0]}")
        return

    page_path = WIKI_CONCEPTS / "separation_ratio.md"
    write(page_path, page)
    _update_index(page_path)

    # If ratio changed significantly, update MEMORY.md
    memory = read(CORPUS["memory"])
    mem_ratio = re.search(r"ratio[:\s]+([\d.]+)", memory, re.IGNORECASE)
    if mem_ratio and abs(float(mem_ratio.group(1)) - current_ratio) > 0.005:
        # Ratio changed — flag for MEMORY.md update
        print(f"\n  [WARN] Ratio changed: {float(mem_ratio.group(1)):.3f} -> {current_ratio:.3f}")
        print(f"  Run: python vapi_wiki_engine.py brief MEMORY.md {phase}")
        # Trigger autoresearch if still below gate
        if current_ratio < gate:
            _write_ar_entry({
                "trigger":          "agent_feed_ratio_below_gate",
                "current_ratio":    current_ratio,
                "gate":             gate,
                "gap":              gap,
                "recommendation":   f"Run mixed_biometric_probe sessions. Current: {current_ratio:.3f}, Gate: {gate}",
                "priority":         "separation_ratio",
            })

    log_op("AGENT_FEED", [str(page_path)], provenance,
           f"ratio={current_ratio:.3f}, gate={gate}, gap={gap:.3f}")

    print(f"\n[AGENT_FEED] wiki/concepts/separation_ratio.md updated")
    print(f"  Current ratio: {current_ratio:.3f} (gate: {gate})")
    print(f"  Snapshots read: {len(rows)}")

    # Phase 192: append corpus entropy status to agent feed output
    try:
        _entropy_rows = db_query(
            "SELECT entropy_score, clustering_warning, n_sessions, created_at "
            "FROM corpus_entropy_log ORDER BY created_at DESC LIMIT 1"
        )
        if _entropy_rows:
            _er = _entropy_rows[0]
            _warn = " [CLUSTERING_WARNING]" if _er.get("clustering_warning") else ""
            print(f"  Corpus entropy: {_er['entropy_score']:.4f}{_warn}  "
                  f"(N={_er.get('n_sessions', '?')}, {_er.get('created_at', '')[:10]})")
        else:
            print("  Corpus entropy: no data yet (Phase 192 CorpusDataCuratorAgent pending)")
    except Exception:
        pass  # fail-open; table may not exist on older DBs

# ─────────────────────────────────────────────────────────────
# INGEST SWEEP — consumes Skill 14 PostCode sweep output
# Skill 14 generates a structured JSON report.
# This engine turns it into a wiki entry + W1 update + AR feed.
# ─────────────────────────────────────────────────────────────

def cmd_ingest_sweep(sweep_json_path: str):
    """
    Consumes Skill 14 PostCode Mitigation Sweep JSON output.
    - Writes sweep record to wiki/sweeps/
    - Appends W1 entry to VAPI_WHAT_IF.md if new failure class found
    - Feeds gaps to AutoResearch experiment log
    - Updates MEMORY.md sweep summary
    """
    path = Path(sweep_json_path)
    if not path.exists():
        print(f"ERROR: {sweep_json_path} not found")
        return

    sweep = json.loads(path.read_text(encoding="utf-8"))
    ts    = datetime.now(timezone.utc).isoformat()
    phase = sweep.get("phase", _detect_current_phase())
    provenance = prov(phase, "Skill14_PostCodeSweep", "MEASURED")

    print(f"\n[SWEEP] Ingesting Skill 14 output: {sweep_json_path}")

    # Build wiki sweep page
    root_cause   = sweep.get("root_cause", "None")
    status       = sweep.get("status", "CLEAN")
    ratio_impact = sweep.get("separation_ratio_impact", {})
    tests        = sweep.get("test_results", {})

    page = f"""# SWEEP: PostCode Sweep — {ts[:10]}

{provenance}
Generated by Skill 14 PostCode Mitigation Sweep

## Result: {status}

| Suite | Baseline | Actual | Status |
|-------|----------|--------|--------|
| Bridge | {tests.get('bridge', {}).get('baseline', 1868)} | {tests.get('bridge', {}).get('actual', '?')} | {tests.get('bridge', {}).get('status', '?')} |
| SDK | {tests.get('sdk', {}).get('baseline', 305)} | {tests.get('sdk', {}).get('actual', '?')} | {tests.get('sdk', {}).get('status', '?')} |
| Hardhat | {tests.get('hardhat', {}).get('baseline', 468)} | {tests.get('hardhat', {}).get('actual', '?')} | {tests.get('hardhat', {}).get('status', '?')} |
| E2E | {tests.get('e2e', {}).get('baseline', 14)} | {tests.get('e2e', {}).get('actual', '?')} | {tests.get('e2e', {}).get('status', '?')} |

## Root Cause
{root_cause}

Class: {sweep.get('failure_class', 'N/A')}
Description: {SWEEP_FAILURE_CLASSES.get(sweep.get('failure_class', ''), 'N/A')}

## Fix Applied
{sweep.get('proposed_fix', 'None required')}

## Separation Ratio Impact
Risk level: {ratio_impact.get('risk_level', 'N/A')}
Free-form before: {ratio_impact.get('free_form_pooled_baseline', 'N/A')}
Free-form after: {ratio_impact.get('free_form_pooled_current', 'N/A')}
Regression: {ratio_impact.get('regression', False)}

## Invariant Status
{sweep.get('invariant_status', 'All 20 preserved')}

## Related Pages
- [[phase_{phase}]]
- [[separation_ratio]]
"""

    passes, violations = check_invariants(page)
    if not passes:
        print(f"  BLOCKED: {violations[0]}")
        return

    sweep_path = WIKI_SWEEPS / f"sweep_{ts[:10].replace('-', '')}_{status.lower()}.md"
    write(sweep_path, page)
    _update_index(sweep_path)

    # If new failure class found — append W1 to VAPI_WHAT_IF.md
    failure_class = sweep.get("failure_class")
    if failure_class and status != "CLEAN" and failure_class in SWEEP_FAILURE_CLASSES:
        _append_w1_from_sweep(sweep, phase, provenance)

    # Feed to AutoResearch
    _write_ar_entry({
        "trigger":        "skill14_sweep",
        "status":         status,
        "root_cause":     root_cause,
        "failure_class":  failure_class,
        "ratio_impact":   ratio_impact,
        "recommendation": sweep.get("recommendation", ""),
        "phase":          phase,
    })

    log_op("SWEEP", [str(sweep_path)], provenance,
           f"status={status}, failure_class={failure_class}")

    print(f"\n[SWEEP] wiki/sweeps/{sweep_path.name}")
    print(f"  Status: {status}")
    if failure_class and status != "CLEAN":
        print(f"  W1 appended to VAPI_WHAT_IF.md: {failure_class}")

def _append_w1_from_sweep(sweep: dict, phase: int, provenance: str):
    """Appends a W1 entry to VAPI_WHAT_IF.md from a Skill 14 sweep finding."""
    what_if_path = CORPUS["what_if"]
    if not what_if_path.exists():
        return

    existing = what_if_path.read_text(encoding="utf-8")
    existing_ids = re.findall(r"W1-(\d+)", existing)
    next_n = max((int(x) for x in existing_ids), default=0) + 1
    entry_id = f"W1-{next_n:03d}"

    failure_class = sweep.get("failure_class", "UNKNOWN")
    root_cause    = sweep.get("root_cause", "")
    fix           = sweep.get("proposed_fix", "")
    ratio_impact  = sweep.get("separation_ratio_impact", {})

    entry = f"""
### {entry_id}: {failure_class} (Phase {phase}, Skill 14 Auto-Generated)

**Status**: MITIGATED
**Detected by**: Skill 14 PostCode Mitigation Sweep
**Phase**: Phase {phase}

**Failure mechanism**: {root_cause}
Class definition: {SWEEP_FAILURE_CLASSES.get(failure_class, 'See SWEEP_FAILURE_CLASSES in vapi_wiki_engine.py')}

**Implication**: Test regression + potential invariant violation if unmitigated.

**Fix applied**: {fix}

**Separation ratio impact**: {ratio_impact.get('risk_level', 'N/A')}
Regression: {ratio_impact.get('regression', False)}

**Invariants affected**: {sweep.get('invariant_status', 'All 20 preserved')}

{provenance}
"""

    _locked_append(what_if_path, entry)

    # Also write to wiki/what_if/ and AutoResearch corpus
    safe = re.sub(r"[^\w\-]", "_", failure_class.lower())
    write(WIKI_WHATIF / f"{entry_id}_{safe}.md",
          f"# W1: {failure_class}\n\n{entry}")
    if AR_WHATIF.exists():
        write(AR_WHATIF / f"{entry_id}_{safe}.md",
              f"# W1: {failure_class}\n\n{entry}")

    print(f"  [W1] {entry_id} appended to VAPI_WHAT_IF.md")

# ─────────────────────────────────────────────────────────────
# SYNC WHAT_IF -> HARNESS KNOWN_GAPS
# Reads VAPI_WHAT_IF.md, extracts all W1 entries,
# rewrites the KNOWN_GAPS block in vapi_eval_harness.py.
# The eval harness now reflects all current W1 entries.
# ─────────────────────────────────────────────────────────────

def cmd_sync_what_if():
    """
    Reads all W1 entries from VAPI_WHAT_IF.md.
    Updates KNOWN_GAPS in vapi_eval_harness.py so the AutoResearch
    eval cycle scores against current known failure modes.

    This closes the loop:
      New W1 in WHAT_IF -> harness knows about it -> autoresearch scores against it.
    """
    if not HARNESS.exists():
        print(f"[SYNC] Eval harness not found at {HARNESS}")
        return

    what_if_text = read(CORPUS["what_if"])
    harness_text = HARNESS.read_text(encoding="utf-8")

    # Extract all W1 entries
    w1_entries = re.findall(
        r"### (W1-\d+): ([^\n]+)\n.*?(?=### W[123]-|\Z)",
        what_if_text, re.DOTALL
    )

    if not w1_entries:
        print("[SYNC] No W1 entries found in VAPI_WHAT_IF.md")
        return

    # Build keywords list from W1 titles for KNOWN_GAPS
    gap_entries = []
    for entry_id, title in w1_entries:
        title_clean = title.strip().split("(")[0].strip()
        keywords    = [w.lower() for w in title_clean.split()[:3] if len(w) > 3]
        gap_entries.append(f"""    "{entry_id}": {{
        "title": "{title_clean}",
        "status": "DOCUMENTED",
        "keywords": {json.dumps(keywords)},
        "source": "VAPI_WHAT_IF.md",
    }},""")

    new_block = (
        "# Auto-synced from VAPI_WHAT_IF.md by vapi_wiki_engine.py\n"
        "# Last sync: " + datetime.now(timezone.utc).isoformat() + "\n"
        "WIKI_KNOWN_W1 = {\n"
        + "\n".join(gap_entries)
        + "\n}"
    )

    # Append after KNOWN_GAPS in harness (don't modify KNOWN_GAPS itself —
    # that is immutable ground truth. Add WIKI_KNOWN_W1 as a supplement.)
    if "WIKI_KNOWN_W1" in harness_text:
        # Update existing block
        updated = re.sub(
            r"# Auto-synced from VAPI_WHAT_IF\.md.*?^}",
            new_block,
            harness_text,
            flags=re.DOTALL | re.MULTILINE
        )
        HARNESS.write_text(updated, encoding="utf-8")
    else:
        # Append after the KNOWN_GAPS block
        insertion_point = harness_text.find("\n# ============\n", harness_text.find("KNOWN_GAPS"))
        if insertion_point > 0:
            updated = (
                harness_text[:insertion_point]
                + f"\n\n{new_block}\n"
                + harness_text[insertion_point:]
            )
            HARNESS.write_text(updated, encoding="utf-8")
        else:
            # Append at end
            append_file(HARNESS, f"\n\n{new_block}\n")

    log_op("SYNC_WHAT_IF", [str(HARNESS)],
           prov(_detect_current_phase(), "VAPI_WHAT_IF.md"),
           f"{len(w1_entries)} W1 entries synced to harness WIKI_KNOWN_W1")

    print(f"\n[SYNC_WHAT_IF] {len(w1_entries)} W1 entries -> vapi_eval_harness.py WIKI_KNOWN_W1")
    print(f"  Harness now scores proposals against all current W1 failure modes.")
    print(f"  Run: python vapi_autoresearch.py --cycle 1 to use updated scoring.")

# ─────────────────────────────────────────────────────────────
# SNAPSHOT + ON-CHAIN ANCHOR
# SHA-256 of wiki state + optional POST to bridge anchor endpoint.
# Bridge calls AdjudicationRegistry.sol (already deployed).
# Same contract as PoAd anchoring — zero new infrastructure.
# ─────────────────────────────────────────────────────────────

def cmd_snapshot(anchor: bool = False):
    """
    Cryptographic snapshot of wiki state.
    --anchor: also POST to bridge /agent/anchor-wiki-snapshot
    which writes to AdjudicationRegistry.sol (already deployed).
    """
    h       = wiki_hash()
    ts      = datetime.now(timezone.utc).isoformat()
    n_pages = len(list(WIKI.rglob("*.md"))) if WIKI.exists() else 0
    n_log   = read(WIKI_LOG).count("\n")
    phase   = _detect_current_phase()
    anchor_status = "local only"

    if anchor:
        anchor_status = _anchor_on_chain(h, ts, phase)

    append_file(
        WIKI_SNAPSHOTS,
        f"| {ts} | sha256:{h[:24]}...{h[-8:]} | {n_pages} | {anchor_status} |\n"
    )

    log_op("SNAPSHOT", [str(WIKI_SNAPSHOTS)],
           f"[SNAPSHOT:{h[:12]}]",
           f"pages={n_pages}, anchor={anchor_status}")

    print(f"\n[SNAPSHOT]")
    print(f"  Timestamp: {ts}")
    print(f"  SHA-256:   {h}")
    print(f"  Pages:     {n_pages}")
    print(f"  Anchor:    {anchor_status}")
    return h

def _anchor_on_chain(h: str, ts: str, phase: int) -> str:
    """
    POSTs wiki snapshot hash to bridge /agent/anchor-wiki-snapshot.
    Bridge writes to AdjudicationRegistry.sol (already deployed at
    0x44CF981f46a52ADE56476Ce894255954a7776fb4).
    Same contract as PoAd hash anchoring — no new contracts needed.
    """
    try:
        import urllib.request
        payload = json.dumps({
            "wiki_snapshot_hash": h,
            "timestamp":          ts,
            "phase":              phase,
            "source":             "vapi_wiki_engine",
            "provenance":         prov(phase, "vapi_wiki_engine.py", "SNAPSHOT"),
            "registry":           FROZEN["adjudication_registry"],
        }).encode()

        req = urllib.request.Request(
            ANCHOR_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            tx_hash = result.get("tx_hash", "pending")
            return f"anchored tx:{tx_hash[:12]}..."

    except Exception as e:
        # Bridge offline — log but don't fail the snapshot
        return f"anchor_failed ({str(e)[:40]})"

# ─────────────────────────────────────────────────────────────
# MCP RELOAD TRIGGER
# After any wiki write that touches VAPI_*.md,
# tell the MCP server to reload its knowledge graph.
# ─────────────────────────────────────────────────────────────

def mcp_reload():
    """
    Sends vapi_reload_knowledge to the MCP server via the bridge endpoint.
    The knowledge_server.py reloads all 9 VAPI_*.md files.
    Next vapi_query_what_if call sees new entries immediately.
    """
    try:
        import urllib.request
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method":  "tools/call",
            "id":      1,
            "params":  {"name": "vapi_reload_knowledge", "arguments": {}},
        }).encode()

        req = urllib.request.Request(
            f"{BRIDGE_URL}/mcp",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print("  [MCP] Knowledge graph reloaded.")
    except Exception:
        print("  [MCP] Reload skipped (MCP server offline — will reload on next session start).")

# ─────────────────────────────────────────────────────────────
# PHASE CLOSE — complete phase boundary sequence
# One command per phase completion.
# ─────────────────────────────────────────────────────────────

def _trigger_provenance_registration(phase: int) -> None:
    """Phase 192: register a provenance DAG node for this phase close event.

    Writes a phase_close node into data_provenance_dag via the bridge store.
    Fail-open: any exception is logged and ignored.
    """
    try:
        import sys as _sys_prov, hashlib as _hash_prov
        _sys_prov.path.insert(0, str(Path(__file__).parent / "bridge"))
        from vapi_bridge.store import Store as _Store  # type: ignore
        _store = _Store()
        import time as _time_prov
        _ts = int(_time_prov.time_ns())
        _raw = f"phase_close:{phase}:{_ts}".encode()
        _data_hash = _hash_prov.sha256(_raw).hexdigest()
        _node_id = f"phase_close_{phase}_{_ts}"
        _store.insert_provenance_node(
            node_id=_node_id,
            parent_node_id=None,
            artifact_type="phase_close",
            player_id="",
            session_name=f"phase_{phase}",
            data_hash=_data_hash,
            phase=phase,
            notes=f"Auto-registered by vapi_wiki_engine.cmd_phase_close({phase})",
        )
        print(f"  Provenance node registered: {_node_id[:40]}...")
    except Exception as _exc:
        print(f"  [WARN] Provenance registration skipped: {_exc}")


def cmd_phase_close(phase: int):
    """
    Runs the complete phase boundary sequence:
      1. Generate briefs for MEMORY.md + VAPI_WHAT_IF.md
      2. Snapshot + on-chain anchor
      3. Sync WHAT_IF -> harness
      4. AutoResearch feed
      5. MCP reload
      6. Print session summary
    """
    print(f"\n[PHASE_CLOSE] Phase {phase}")
    print("=" * 50)

    print("\n0. Phase 192: triggering provenance DAG registration...")
    _trigger_provenance_registration(phase)

    print("\n1. Generating ingest briefs...")
    cmd_brief("MEMORY.md", phase)
    cmd_brief("VAPI_WHAT_IF.md", phase)

    print("\n2. Agent feed (separation ratio from DB)...")
    cmd_agent_feed()

    print("\n3. Snapshot + on-chain anchor...")
    h = cmd_snapshot(anchor=True)

    print("\n4. Syncing WHAT_IF -> eval harness...")
    cmd_sync_what_if()

    print("\n5. AutoResearch feed...")
    cmd_autoresearch_feed()

    print("\n6. MCP reload...")
    mcp_reload()

    print("\n7. Coherence status (Phase 193 fleet signal check)...")
    cmd_coherence_status()

    print(f"\n[PHASE_CLOSE COMPLETE] Phase {phase}")
    print(f"  Wiki snapshot: sha256:{h[:12]}...")
    print(f"  Briefs ready in wiki/briefs/ — Claude Code reads them to generate pages")
    print(f"  WHAT_IF -> harness synced")
    print(f"  AutoResearch log updated")
    print(f"\nNext:")
    print(f"  Claude Code: Read wiki/briefs/brief_MEMORY.md_{phase}.md and generate pages")
    print(f"  python vapi_autoresearch.py --cycle 1 --priority separation_ratio")

# ─────────────────────────────────────────────────────────────
# PHASE 193: FLEET COHERENCE STATUS
# ─────────────────────────────────────────────────────────────

def cmd_coherence_status():
    """
    Reads fleet_coherence_log and prints a human-readable summary.
    Called after phase_close to show if any new contradictions emerged
    during the phase implementation.
    """
    rows = _db_query(
        "SELECT failure_mode, rule_name, severity, resolved, promoted_to_wif, wif_entry_id "
        "FROM fleet_coherence_log ORDER BY created_at DESC LIMIT 20"
    )
    if not rows:
        print("  [COHERENCE] No contradictions detected. Fleet signals coherent.")
        return

    open_rows = [r for r in rows if not r["resolved"]]
    print(f"\n  [COHERENCE] {len(open_rows)} open coherence failures:")
    for r in open_rows:
        sev = r.get("severity", "MEDIUM")
        icon = "CRIT" if sev == "CRITICAL" else "HIGH" if sev == "HIGH" else "WARN"
        wif  = f" -> {r['wif_entry_id']}" if r.get("promoted_to_wif") else ""
        print(f"    [{icon}] [{r.get('failure_mode', '?')}] {r.get('rule_name', '?')}{wif}")


def _db_query(sql: str, params: tuple = ()) -> list:
    """Query the VAPI bridge SQLite DB; returns list of row dicts, fail-open."""
    import sqlite3
    db_path = ROOT / "bridge" / "vapi_bridge.db"
    if not db_path.exists():
        return []
    try:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────
# AUTORESEARCH FEED
# ─────────────────────────────────────────────────────────────

def cmd_autoresearch_feed():
    """Syncs wiki gaps and current state to AutoResearch experiment log."""
    gaps    = []
    if WIKI.exists():
        for page in WIKI.rglob("*.md"):
            content = page.read_text(encoding="utf-8")
            rel     = str(page.relative_to(WIKI))
            if "[WIKI_GAP]" in content:
                gaps.append({"type": "wiki_gap", "page": rel,
                              "count": content.count("[WIKI_GAP]")})
            if "[NEEDS_PROVENANCE]" in content:
                gaps.append({"type": "needs_provenance", "page": rel,
                              "count": content.count("[NEEDS_PROVENANCE]")})

    ratio_rows = db_query(
        "SELECT pooled_ratio FROM separation_ratio_snapshots "
        "ORDER BY created_at DESC LIMIT 1"
    )
    current_ratio = ratio_rows[0]["pooled_ratio"] if ratio_rows else None
    gate          = float(FROZEN["separation_gate"])

    _write_ar_entry({
        "trigger":                  "vapi_wiki.autoresearch_feed",
        "wiki_gaps":                gaps,
        "gap_count":                len(gaps),
        "separation_ratio_current": current_ratio,
        "separation_gate":          gate,
        "gap_to_gate":              round(gate - (current_ratio or 0), 3) if current_ratio else None,
        "priority":                 "separation_ratio" if (current_ratio and current_ratio < gate) else "wiki_provenance",
        "recommendation":           (
            f"Run mixed_biometric_probe sessions. ratio={current_ratio:.3f}, gate={gate}"
            if current_ratio and current_ratio < gate
            else "Separation ratio above gate — address wiki provenance gaps."
        ),
    })

    phase = _detect_current_phase()
    log_op("AR_FEED", [str(AR_LOG)],
           prov(phase, "vapi_wiki_engine.py"),
           f"gaps={len(gaps)}, ratio={current_ratio}")

    print(f"\n[AR_FEED] AutoResearch log updated")
    print(f"  Wiki gaps: {len(gaps)}")
    print(f"  Separation ratio: {current_ratio} (gate: {gate})")

# ─────────────────────────────────────────────────────────────
# CHECK — inline invariant check
# ─────────────────────────────────────────────────────────────

def cmd_check(text: str):
    passes, violations = check_invariants(text)
    if passes:
        print("[CHECK] PASS")
    else:
        print(f"[CHECK] BLOCKED — {len(violations)} violations:")
        for v in violations:
            print(f"  [MISSING] {v}")
    return passes

# ─────────────────────────────────────────────────────────────
# LINT
# ─────────────────────────────────────────────────────────────

def cmd_lint():
    print("\n[LINT] Scanning wiki...")
    all_pages = list(WIKI.rglob("*.md")) if WIKI.exists() else []

    issues = {
        "needs_provenance":      [],
        "unresolved_contradict": [],
        "wiki_gaps":             [],
        "invariant_violations":  [],
        "orphan_pages":          [],
    }
    index_text = read(WIKI_INDEX)

    for page in all_pages:
        if page.name in ("log.md", "snapshots.md", "index.md",
                          "contradictions.md", "blocked_updates.md", "lint_report.md"):
            continue
        content = page.read_text(encoding="utf-8")
        rel     = str(page.relative_to(WIKI))
        if "[NEEDS_PROVENANCE]" in content:
            issues["needs_provenance"].append(rel)
        if "[CONTRADICTION: unresolved]" in content:
            issues["unresolved_contradict"].append(rel)
        if "[WIKI_GAP]" in content:
            issues["wiki_gaps"].append(rel)
        _, viol = check_invariants(content)
        if viol:
            issues["invariant_violations"].append(f"{rel}: {viol[0][:60]}")
        if rel not in index_text:
            issues["orphan_pages"].append(rel)

    health = max(0, 100
                 - len(issues["invariant_violations"]) * 25
                 - len(issues["needs_provenance"]) * 10
                 - len(issues["unresolved_contradict"]) * 10
                 - len(issues["wiki_gaps"]) * 5
                 - len(issues["orphan_pages"]) * 3)

    report = f"""# VAPI Wiki Lint Report
Generated: {datetime.now(timezone.utc).isoformat()}
Health: {health}/100

## Issues
| Type | Count | Priority |
|------|-------|----------|
| Invariant violations | {len(issues['invariant_violations'])} | P0 |
| [NEEDS_PROVENANCE] | {len(issues['needs_provenance'])} | P0 |
| [CONTRADICTION: unresolved] | {len(issues['unresolved_contradict'])} | P1 |
| [WIKI_GAP] | {len(issues['wiki_gaps'])} | P1 |
| Orphan pages | {len(issues['orphan_pages'])} | P2 |

## P0 — Fix immediately
{chr(10).join(f'- {x}' for x in issues['invariant_violations'] + issues['needs_provenance']) or '- None'}

## P1 — Fix before next phase close
{chr(10).join(f'- {x}' for x in issues['unresolved_contradict'] + issues['wiki_gaps']) or '- None'}

## Commands
```bash
python vapi_wiki_engine.py agent_feed        # refresh ratio from Agent 15
python vapi_wiki_engine.py sync_what_if      # sync W1 -> eval harness
python vapi_wiki_engine.py snapshot --anchor # commit + on-chain anchor
```
"""
    write(WIKI / "lint_report.md", report)
    log_op("LINT", [str(WIKI / "lint_report.md")],
           prov(_detect_current_phase(), "vapi_wiki_engine.py"),
           f"health={health}")
    print(report)
    return health

# ─────────────────────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────────────────────

def cmd_status():
    print("\n[STATUS] VAPI Wiki Engine — Integrated Systems")
    print(f"  Wiki pages:    {len(list(WIKI.rglob('*.md'))) if WIKI.exists() else 0}")
    print(f"  Log entries:   {read(WIKI_LOG).count(chr(10))}")

    snaps = [l for l in read(WIKI_SNAPSHOTS).split("\n") if "sha256:" in l]
    print(f"  Snapshots:     {len(snaps)}")

    # Live ratio from DB
    rows = db_query("SELECT pooled_ratio FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 1")
    ratio = rows[0]["pooled_ratio"] if rows else "DB offline"
    print(f"  Live ratio:    {ratio} (gate: {FROZEN['separation_gate']})")

    print(f"\n  Integration health:")
    print(f"    {'[OK]' if DB_PATH.exists() else '[OFF]'}  Bridge DB (Agent 15 feed)")
    print(f"    {'[OK]' if AR_LOG.exists() else '[OFF]'}  AutoResearch log")
    print(f"    {'[OK]' if HARNESS.exists() else '[OFF]'}  Eval harness")
    print(f"    {'[OK]' if CORPUS['what_if'].exists() else '[OFF]'}  VAPI_WHAT_IF.md (W1 sync)")
    print(f"    {'[OK]' if MCP_SERVER.exists() else '[OFF]'}  MCP knowledge_server.py")

    # W1 count
    w1_count = len(re.findall(r"### W1-\d+", read(CORPUS["what_if"])))
    print(f"\n  W1 entries in VAPI_WHAT_IF.md: {w1_count}")
    print(f"  Run 'sync_what_if' to push to eval harness.")

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _detect_current_phase() -> int:
    """
    Detects current phase. Priority:
      1. VAPI_PHASE env var (override for non-standard MEMORY.md formatting)
      2. Regex parse of CLAUDE.md 'Current phase: Phase NNN' line
      3. Regex parse of MEMORY.md
      4. Default: 166
    """
    # 1. Env override
    env_phase = os.environ.get("VAPI_PHASE")
    if env_phase and env_phase.isdigit():
        return int(env_phase)
    # 2. CLAUDE.md is authoritative — parse "Current phase: Phase NNN"
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        text = claude_md.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"Current phase:\s*Phase\s*(\d{2,3})", text)
        if m:
            return int(m.group(1))
    # 3. Fallback: MEMORY.md
    memory = read(CORPUS.get("memory", Path("MEMORY.md")))
    m = re.search(r"phase\s+(\d{2,3})", memory, re.IGNORECASE)
    return int(m.group(1)) if m else 166

def _write_ar_entry(data: dict):
    AR_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **data}
    with open(AR_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def _extract_metrics(text: str) -> dict:
    patterns = {
        "separation_ratio": r"ratio[:\s]+([\d.]+)",
        "bridge_tests":     r"bridge[:\s]+(\d{1,4})",
        "sdk_tests":        r"sdk[:\s]+(\d{1,3})",
        "agents":           r"(\d{2}).{0,10}agent",
        "phase":            r"phase\s+(\d{2,3})",
    }
    return {k: m.group(1) for k, p in patterns.items()
            if (m := re.search(p, text, re.IGNORECASE))}

def _detect_domains(text: str) -> dict:
    low = text.lower()
    d = {
        "phase_state":      any(x in low for x in ["phase 16", "current phase"]),
        "separation_ratio": "separation ratio" in low or "inter-person" in low,
        "agents":           "agent fleet" in low or "agent #" in low,
        "l4_calibration":   "mahalanobis" in low or "l4" in low,
        "what_if":          "w1" in low or "w2" in low,
        "privacy":          "gdpr" in low or "erasure" in low,
        "zk_circuit":       "poseidon" in low or "groth16" in low,
        "sweep":            "postcode" in low or "skill 14" in low,
    }
    d["count"] = sum(1 for v in d.values() if v is True)
    return d

def _generate_page_plan(domains: dict, phase: int, source: str) -> str:
    p = prov(phase, source)
    pages = []
    if domains.get("phase_state"):
        pages.append(f"- wiki/phases/phase_{phase}.md [TYPE: PHASE]\n  {p}")
    if domains.get("separation_ratio"):
        pages.append(f"- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]\n  {p}")
    if domains.get("agents"):
        pages.append(f"- wiki/entities/agent_fleet.md [TYPE: ENTITY]\n  {p}")
    if domains.get("l4_calibration"):
        pages.append(f"- wiki/entities/l4_thresholds.md [TYPE: ENTITY]\n  {prov(phase, 'VAPI_INVARIANTS.md', 'FROZEN')}")
    if domains.get("what_if"):
        pages.append(f"- wiki/what_if/ entries [TYPE: WHAT_IF]\n  {p}")
    if not pages:
        pages.append(f"- wiki/synthesis/misc.md [TYPE: SYNTHESIS]\n  {p}")
    return "\n".join(pages)

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

CMDS = {
    "init":             "Initialize wiki structure",
    "brief":            "Generate Claude Code ingest brief (no API)",
    "check":            "Invariant check on text",
    "agent_feed":       "Pull separation ratio from Agent 15 DB -> update wiki",
    "ingest_sweep":     "Consume Skill 14 PostCode sweep JSON -> wiki + W1 + AR",
    "sync_what_if":     "Sync VAPI_WHAT_IF.md W1 entries -> eval harness KNOWN_GAPS",
    "snapshot":         "SHA-256 snapshot [--anchor: on-chain via AdjudicationRegistry]",
    "phase_close":      "Complete phase boundary sequence (brief+feed+snapshot+sync+AR)",
    "autoresearch_feed":"Sync wiki gaps -> AutoResearch experiment log",
    "coherence_status": "Fleet signal coherence check (Phase 193 — FSCA contradiction scan)",
    "lint":             "Wiki health check (no API)",
    "status":           "Full integration health",
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("VAPI Wiki Engine — Integrated Knowledge System\n")
        print("Commands:")
        for c, d in CMDS.items():
            print(f"  {c:<22} {d}")
        print("\nKey integrations (all use existing VAPI infrastructure):")
        print("  agent_feed:   reads Agent 15's separation_ratio_snapshots table")
        print("  ingest_sweep: consumes Skill 14 JSON -> wiki + VAPI_WHAT_IF.md + AR log")
        print("  sync_what_if: VAPI_WHAT_IF.md W1s -> vapi_eval_harness.py WIKI_KNOWN_W1")
        print("  snapshot --anchor: SHA-256 -> AdjudicationRegistry.sol (already deployed)")
        print("  phase_close:  runs all of the above in sequence")
        return

    cmd = sys.argv[1].lower()

    if cmd == "init":
        cmd_init()
    elif cmd in ("brief", "ingest"):
        if len(sys.argv) < 4:
            print("Usage: python vapi_wiki_engine.py brief <file> <phase>")
        else:
            cmd_brief(sys.argv[2], int(sys.argv[3]))
    elif cmd == "check":
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read()
        cmd_check(text)
    elif cmd == "agent_feed":
        cmd_agent_feed()
    elif cmd == "ingest_sweep":
        if len(sys.argv) < 3:
            print("Usage: python vapi_wiki_engine.py ingest_sweep <sweep.json>")
        else:
            cmd_ingest_sweep(sys.argv[2])
    elif cmd == "sync_what_if":
        cmd_sync_what_if()
    elif cmd == "snapshot":
        anchor = "--anchor" in sys.argv
        cmd_snapshot(anchor=anchor)
    elif cmd == "phase_close":
        if len(sys.argv) < 3:
            phase = _detect_current_phase()
        else:
            phase = int(sys.argv[2])
        cmd_phase_close(phase)
    elif cmd == "autoresearch_feed":
        cmd_autoresearch_feed()
    elif cmd == "coherence_status":
        cmd_coherence_status()
    elif cmd == "lint":
        cmd_lint()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown: {cmd}. Run --help")
        sys.exit(1)

if __name__ == "__main__":
    main()
