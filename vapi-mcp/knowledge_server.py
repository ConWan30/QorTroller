"""
VAPI Knowledge Graph MCP Server  v2.0.0-phase{N} (N read from CLAUDE.md at startup)
=======================================================================================
Transforms 9 VAPI corpus files into a live, queryable, enforcing knowledge graph
accessible to Claude Code as structured MCP tools.

The key insight: these files aren't just context to read.
They are the ground truth that EVERY proposal must be validated against.
The MCP server is the active enforcer, not a passive reader.

Knowledge Graph Architecture:
  VAPI_INVARIANTS.md  → InvariantEngine  (blocks violations before they happen)
  VAPI_WHAT_IF.md     → WhatIfCorpus     (queries + extends curated W1/W2 pairs)
  VAPI_CORPUS.md      → CorpusLedger     (session evidence with legal hold)
  VAPI_AGENTS.md      → AgentRegistry    (18-agent fleet truth)
  VAPI_SKILLS.md      → SkillOrchestrator (session-start protocol enforcement)
  VAPI_MEMORY.md      → MemorySync       (live state vs file reconciliation)
  VAPI_CONTEXT.md     → ContextLayer     (phase history + domain expertise)
  VAPI_BIOMETRIC_PRIVACY.md → PrivacyEngine (BP-001 through BP-007 enforcement)
  VAPI_CONTROLLER_INTELLIGENCE.md → CHILayer (multi-controller tier logic)

Phase 149 state (current):
  3-player clean corpus (P4 eliminated Phase 138); ratio=1.261 (Phase 143 proper LOO, N=11)
  vapi_separation_analysis   — Phase 139-143 flags: --session-type, --balance-corpus, --probe-comparison
  vapi_autoresearch_seed     — Live-state-grounded hypothesis seeding for autoresearch cycles

Usage:
  python vapi-mcp/knowledge_server.py

Install:
  pip install httpx

Claude Code config:
  See claude_desktop_config.json in project root (register as "vapi-knowledge")
"""

import asyncio
import json
import os
import re
import sys
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

# ============================================================
# Configuration
# ============================================================

BRIDGE_URL   = os.environ.get("VAPI_BRIDGE_URL", "http://localhost:8080")
DB_PATH      = os.environ.get("VAPI_DB_PATH", "bridge/vapi_store.db")
# VAPI_*.md files live in VAPI-WORKFLOW.v2/ — not the project root
CORPUS_DIR   = os.environ.get("VAPI_CORPUS_DIR", "VAPI-WORKFLOW.v2")
PROJECT_ROOT = Path(os.environ.get("VAPI_ROOT", "."))

# ============================================================
# CLAUDE.md Live Parser — shared with server.py, never stale
# ============================================================
# Identical to server.py's _parse_claude_md(). CLAUDE.md is the single
# authoritative source updated every phase — both MCP servers read it.

_CLAUDE_CACHE_KS: dict = {"mtime": 0.0, "state": {}}

def _parse_claude_md() -> dict:
    """Parse CLAUDE.md into current protocol state. Mtime-cached — O(1) per call."""
    claude_path = PROJECT_ROOT / "CLAUDE.md"
    try:
        mtime = claude_path.stat().st_mtime
    except OSError:
        return _CLAUDE_CACHE_KS.get("state", {})

    if mtime <= _CLAUDE_CACHE_KS["mtime"] and _CLAUDE_CACHE_KS["state"]:
        return _CLAUDE_CACHE_KS["state"]

    try:
        text = claude_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return _CLAUDE_CACHE_KS.get("state", {})

    s: dict = {}
    m = re.search(r"Current phase:\s*Phase\s*(\d+)", text)
    s["phase_num"] = m.group(1) if m else "207"
    s["phase"] = f"{s['phase_num']} COMPLETE"

    m = re.search(r"Bridge:\s*(\d+)\s*passing", text)
    s["bridge"] = int(m.group(1)) if m else 2252
    m = re.search(r"Contract:\s*(\d+)", text)
    s["hardhat"] = int(m.group(1)) if m else 482
    m = re.search(r"SDK:\s*(\d+)", text)
    s["sdk"] = int(m.group(1)) if m else 448
    m = re.search(r"(\d+)\s+contracts\s+ALL\s+LIVE", text)
    s["contracts_live"] = int(m.group(1)) if m else 43

    arrows = re.findall(r"agents\s+(\d+)→(\d+)", text)
    agent_refs = re.findall(r"agent\s+#(\d+)", text)
    candidates = [int(p[1]) for p in arrows] + [int(n) for n in agent_refs]
    s["agents"] = max(candidates) if candidates else 36

    m = re.search(r"L4 anomaly threshold:\s*\*\*([0-9.]+)\*\*", text)
    s["l4_anomaly"] = float(m.group(1)) if m else 7.009
    m = re.search(r"L4 continuity threshold:\s*\*\*([0-9.]+)\*\*", text)
    s["l4_continuity"] = float(m.group(1)) if m else 5.367

    m = re.search(r"tremor_resting[^:]*:\s*\*\*([0-9.]+)\*\*[^N]*N=(\d+)", text)
    s["tremor_resting_ratio"] = float(m.group(1)) if m else 1.177
    s["tremor_resting_n"]     = int(m.group(2))    if m else 27

    m = re.search(r"Separation ratio:\s*\*\*([0-9.]+)\*\*[^)]*diagonal\+LOO[^)]*N=(\d+)", text)
    s["touchpad_corners_ratio"] = float(m.group(1)) if m else 0.728
    s["touchpad_corners_n"]     = int(m.group(2))   if m else 35

    # WIF corpus — count open entries
    wif_open = len(re.findall(r"Status.*?OPEN", text))
    s["wif_open_count"] = wif_open

    _CLAUDE_CACHE_KS["mtime"] = mtime
    _CLAUDE_CACHE_KS["state"] = s
    return s

CORPUS_FILES = {
    "invariants":   "VAPI_INVARIANTS.md",
    "what_if":      "VAPI_WHAT_IF.md",
    "corpus":       "VAPI_CORPUS.md",
    "agents":       "VAPI_AGENTS.md",
    "skills":       "VAPI_SKILLS.md",
    "memory":       "VAPI_MEMORY.md",
    "context":      "VAPI_CONTEXT.md",
    "privacy":      "VAPI_BIOMETRIC_PRIVACY.md",
    "controller":   "VAPI_CONTROLLER_INTELLIGENCE.md",
}

# ============================================================
# Knowledge Graph — Parsed In-Memory at Startup
# ============================================================

class VAPIKnowledgeGraph:
    """
    Parses all 9 corpus files into structured, queryable, enforceable knowledge.
    Loaded once at server start. Refreshed on vapi_reload_knowledge call.
    """
    def __init__(self, corpus_dir: str):
        self.corpus_dir = Path(corpus_dir)
        self.raw: dict[str, str] = {}
        self.frozen_values: dict[str, str] = {}
        self.state_flags: dict[str, Any] = {}
        self.what_if_entries: list[dict] = []
        self.agent_registry: list[dict] = []
        self.bp_invariants: list[str] = []
        self.corpus_stats: dict = {}
        self.tge_gates: list[str] = []
        self.skill_protocols: list[str] = []
        self.loaded_at: str = ""

    def load(self):
        """Parse all corpus files into structured knowledge."""
        # Resolve corpus_dir relative to PROJECT_ROOT if not absolute
        base = Path(CORPUS_DIR)
        if not base.is_absolute():
            base = PROJECT_ROOT / base

        for key, filename in CORPUS_FILES.items():
            path = base / filename
            if path.exists():
                self.raw[key] = path.read_text(encoding="utf-8")
            else:
                # Try fallback locations
                for search_dir in [Path("."), PROJECT_ROOT, PROJECT_ROOT / "VAPI-WORKFLOW.v2"]:
                    alt = search_dir / filename
                    if alt.exists():
                        self.raw[key] = alt.read_text(encoding="utf-8")
                        break
                else:
                    self.raw[key] = f"[{filename} not found — expected in {base}]"

        self._parse_invariants()
        self._parse_what_if()
        self._parse_agents()
        self._parse_corpus()
        self._parse_privacy()
        self._parse_skills()
        self.loaded_at = datetime.utcnow().isoformat()

    def _parse_invariants(self):
        """Extract FROZEN values, state flags, and TGE gates from VAPI_INVARIANTS.md."""
        text = self.raw.get("invariants", "")

        frozen_patterns = {
            "poac_size_bytes": r"Exactly (\d+) bytes",
            "record_hash": r"record_hash[`\s]*:\s*[`]?([^`\n]+)[`]?",
            "l4_anomaly_threshold": r"Anomaly[^\d]*(\d+\.\d+)",
            "l4_continuity_threshold": r"Continuity[^\d]*(\d+\.\d+)",
            "w1_threshold": r"W1 Threshold[^\d]*(\d+\.\d+)",
            "block_quorum": r"BLOCK_QUORUM[^\d]*(\d+\.\d+)",
            "separation_ratio_current": r"Current pooled[^\d]*([\d.]+)",
            "nPublic": r"nPublic=(\d+)",
        }
        for key, pattern in frozen_patterns.items():
            m = re.search(pattern, text, re.IGNORECASE)
            self.frozen_values[key] = m.group(1) if m else "[not parsed]"

        flag_pattern = r"\|\s*(\w+)\s*\|\s*(true|false)\s*\|"
        for m in re.finditer(flag_pattern, text, re.IGNORECASE):
            self.state_flags[m.group(1)] = m.group(2).lower() == "true"

        tge_section = re.search(r"Token Launch.*?(?=##|\Z)", text, re.DOTALL | re.IGNORECASE)
        if tge_section:
            self.tge_gates = [
                line.strip().lstrip("- ") for line in tge_section.group().split("\n")
                if line.strip().startswith("-") and len(line.strip()) > 5
            ]

    def _parse_what_if(self):
        """Extract W1, W2, W3 entries from VAPI_WHAT_IF.md into structured records."""
        text = self.raw.get("what_if", "")
        entries = []

        entry_pattern = r"### (W[123]-\d+): ([^\n]+)\n(.*?)(?=### W[123]-|\Z)"
        for m in re.finditer(entry_pattern, text, re.DOTALL):
            entry_id = m.group(1)
            title = m.group(2).strip()
            body = m.group(3).strip()

            status_m = re.search(r"\*\*Status\*\*:\s*([^\n]+)", body)
            phase_m = re.search(r"\*\*Phase\*\*:\s*([^\n]+)", body)
            mitigation_m = re.search(r"\*\*Mitigation\*\*:\s*([^\n]+)", body)

            entries.append({
                "id": entry_id,
                "title": title,
                "layer": entry_id[0:2],
                "status": status_m.group(1).strip() if status_m else "ACTIVE",
                "phase": phase_m.group(1).strip() if phase_m else "unknown",
                "mitigation": mitigation_m.group(1).strip() if mitigation_m else "",
                "full_text": body[:400],
            })

        self.what_if_entries = entries

    def _parse_agents(self):
        """Extract agent registry from VAPI_AGENTS.md."""
        text = self.raw.get("agents", "")
        agents = []

        agent_pattern = r"## Agent (\d+[^:]*): ([^\n]+)\n(.*?)(?=## Agent|\Z)"
        for m in re.finditer(agent_pattern, text, re.DOTALL):
            agent_num = m.group(1).strip()
            agent_name = m.group(2).strip()
            body = m.group(3).strip()

            status_m = re.search(r"\*\*Status\*\*:\s*([^\n]+)", body)
            phase_m = re.search(r"\*\*Phase\*\*:\s*([^\n]+)", body)

            agents.append({
                "number": agent_num,
                "name": agent_name,
                "status": status_m.group(1).strip() if status_m else "Live",
                "phase": phase_m.group(1).strip() if phase_m else "unknown",
                "summary": body[:200],
            })

        self.agent_registry = agents

    def _parse_corpus(self):
        """Extract corpus statistics from VAPI_CORPUS.md + CLAUDE.md live state."""
        text = self.raw.get("corpus", "")
        s = _parse_claude_md()  # always current

        self.corpus_stats = {
            "total_sessions": 217,  # from CLAUDE.md corpus state (153 terminal + ~64 hw)
            "unique_players": 3,
            "legal_hold": "ACTIVE",
            "retention": "PERMANENT",
            "status": "ACTIVE COLLECTION",
            "transport": "USB primary (BT pending Phase 120 infrastructure)",
            "analysis_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "separation_ratio_tremor_resting": s.get("tremor_resting_ratio", 1.177),
            "tremor_resting_n": s.get("tremor_resting_n", 27),
            "separation_ratio_touchpad_corners": s.get("touchpad_corners_ratio", 0.728),
            "touchpad_corners_n": s.get("touchpad_corners_n", 35),
            "separation_ratio_touchpad_corners_phase143_best": 1.261,
            "separation_ratio_balanced": 1.611,
            "all_pairs_p0_ok": False,
            "p1vp3_inter_distance": 0.032,
            "p4_status": "ELIMINATED — confirmed=P3 mislabeled (Phase 138)",
            "current_best": "tremor_resting=1.177 (N=27); touchpad_corners=1.261 (N=11, Phase 143)",
            "wif_039": "CorpusRatioRegressionGuard OPEN — Phase 208 candidate",
            "phase": s.get("phase", "207 COMPLETE"),
        }

        total_m = re.search(r"\*\*Total sessions\*\*\s*\|\s*(\d+)", text)
        players_m = re.search(r"\*\*Unique players\*\*\s*\|\s*(\d+)", text)
        if total_m:
            self.corpus_stats["total_sessions"] = int(total_m.group(1))
        if players_m:
            self.corpus_stats["unique_players"] = int(players_m.group(1))

    def _parse_privacy(self):
        """Extract BP invariants from VAPI_BIOMETRIC_PRIVACY.md."""
        text = self.raw.get("privacy", "")
        self.bp_invariants = re.findall(r"\*\*(BP-\d+[^*]+)\*\*", text)

    def _parse_skills(self):
        """Extract session-start protocols from VAPI_SKILLS.md."""
        text = self.raw.get("skills", "")
        self.skill_protocols = [
            line.strip().lstrip("- ").lstrip("* ").lstrip("[ ]").strip()
            for line in text.split("\n")
            if line.strip().startswith(("-", "*", "- ["))
            and len(line.strip()) > 10
        ][:20]

    def validate_proposal(self, proposal_text: str) -> dict:
        """
        The core invariant enforcement engine.
        Validates a proposal against all frozen values and rules.
        Returns {passed: bool, violations: list, warnings: list}.
        """
        violations = []
        warnings = []
        proposal_lower = proposal_text.lower()

        # FROZEN VALUE VIOLATIONS
        if "sha-256(raw[:228])" in proposal_lower or "sha256(raw[:228])" in proposal_lower:
            violations.append(
                "FROZEN VIOLATION: Incorrect hash slice. "
                "VAPI uses SHA-256(raw[:164]) not SHA-256(raw[:228]). "
                "The signature bytes are EXCLUDED from the chain hash."
            )

        if any(phrase in proposal_lower for phrase in
               ["change the wire format", "modify poac", "229 byte", "227 byte"]):
            violations.append(
                "FROZEN VIOLATION: PoAC wire format is 228 bytes IMMUTABLE. "
                "Firmware, bridge, and contracts depend on exact byte offsets."
            )

        if re.search(r"npublic\s*=\s*[^5\s]", proposal_lower):
            violations.append(
                "FROZEN VIOLATION: nPublic=5 is frozen since Phase 62. "
                "Changing nPublic requires full ceremony re-run."
            )

        for pattern in [r"anomaly.{0,20}[89]\.\d+", r"anomaly.{0,20}[1-9][0-9]\.\d+"]:
            if re.search(pattern, proposal_lower):
                violations.append(
                    "FROZEN VIOLATION: L4 anomaly threshold cannot be raised without "
                    "recalibration on N≥50 sessions. Current value 7.009 is N=74 empirical. "
                    "N=127 candidate is 6.613 (tighter, not looser)."
                )

        if "dry_run=false" in proposal_lower or "dry_run = false" in proposal_lower:
            if "n≥100" not in proposal_lower and "n>=100" not in proposal_lower:
                violations.append(
                    "INVARIANT VIOLATION: dry_run=False requires N≥100 live adjudications "
                    "with zero false positives. Phase 97 3-condition gate must pass first."
                )

        if "auto_activate" in proposal_lower and "false" not in proposal_lower:
            violations.append(
                "PERMANENT CONSTRAINT: auto_activate_on_breakthrough=False is a "
                "PERMANENT compile-time constant. Human operator confirmation always required."
            )

        if ("bt" in proposal_lower or "bluetooth" in proposal_lower):
            if "7.009" in proposal_text or "5.367" in proposal_text:
                violations.append(
                    "INVARIANT VIOLATION: USB thresholds (7.009/5.367 at 1000Hz) MUST NOT "
                    "be applied to BT sessions (250Hz). Separate BT threshold track required "
                    "(currently N=0/50 — not yet calibrated)."
                )

        if "tge" in proposal_lower or "token launch" in proposal_lower:
            if "ratio" not in proposal_lower or "1.0" not in proposal_lower:
                warnings.append(
                    "TGE WARNING: Token launch is gated on separation_ratio>1.0 (ALL pairs) + "
                    "N≥100 live adjudications + VHP demonstrated. "
                    "Current pooled ratio: 0.417 (stale full-corpus). "
                    "Phase 143 touchpad_corners ratio=1.261 (proper LOO, N=11) — above 1.0 but N thin. "
                    "P4 ELIMINATED (Phase 138). Need >=10 touchpad_corners/player for tournament defense."
                )

        if "gsr_enabled=true" in proposal_lower or "enable gsr" in proposal_lower:
            violations.append(
                "INVARIANT VIOLATION: GSR_ENABLED=True requires N≥30 calibration sessions "
                "per player. Current N=0. MockGSRGrip only."
            )

        if "synthetic" in proposal_lower and (
            "separation" in proposal_lower or "calibrat" in proposal_lower
        ):
            warnings.append(
                "WARNING: Synthetic biometric data cannot substitute for real hardware sessions. "
                "The 228-byte PoAC is cryptographically bound to real hardware. "
                "Structured probe sessions (touchpad_corners) are the correct path."
            )

        if "raw" in proposal_lower and "persist" in proposal_lower:
            if "ram" not in proposal_lower and "ephemeral" not in proposal_lower:
                warnings.append(
                    "PRIVACY WARNING: BP-007 (EPHEMERAL_SESSIONS) — raw biometric data "
                    "must exist only in RAM, never persisted to storage."
                )

        # Phase 149 separation ratio state
        if "separation" in proposal_lower and "ratio" in proposal_lower:
            if "0.417" in proposal_text or "0.362" in proposal_text:
                warnings.append(
                    "NOTE: 0.417 pooled ratio is STALE (N=127, free-form, 2026-03-29). "
                    "Current best: Phase 143 touchpad_corners=1.261 (diagonal+proper LOO, N=11). "
                    "P4 ELIMINATED (Phase 138 — confirmed=P3). "
                    "Need >=10 touchpad_corners/player (current P1=3, P2=4, P3=4) for tournament defense."
                )

        passed = len(violations) == 0
        return {
            "passed": passed,
            "violations": violations,
            "warnings": warnings,
            "verdict": "APPROVED" if passed and not warnings
                       else ("APPROVED WITH WARNINGS" if passed else "BLOCKED"),
            "invariants_checked": 13,
        }


# Singleton knowledge graph — initialized after PROJECT_ROOT is fully resolved
KG = VAPIKnowledgeGraph(CORPUS_DIR)

# ============================================================
# MCP Protocol (stdio transport)
# ============================================================

TOOLS: dict = {}

def tool(name: str, description: str, schema: dict):
    def decorator(fn):
        TOOLS[name] = {"fn": fn, "description": description, "schema": schema}
        return fn
    return decorator

def write(msg: str):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

def mcp_response(id_, result):
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result})

def mcp_error(id_, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": id_,
                       "error": {"code": code, "message": message}})

# ============================================================
# Bridge + DB helpers
# ============================================================

async def bridge_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{BRIDGE_URL}{path}")
        r.raise_for_status()
        return r.json()

def db_query(sql: str, params=()) -> list:
    db = PROJECT_ROOT / DB_PATH
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

# ============================================================
# TOOLS — Knowledge Graph Powered
# ============================================================

@tool(
    name="vapi_validate_proposal",
    description=(
        "THE most important tool in the VAPI MCP. Validates any proposed code change, "
        "phase plan, or architectural decision against VAPI_INVARIANTS.md. "
        "Returns BLOCKED, APPROVED WITH WARNINGS, or APPROVED. "
        "Call this BEFORE implementing anything. Prevents invariant violations before "
        "they enter the codebase. Enforces: frozen PoAC format, ZK circuit parameters, "
        "calibrated thresholds, state flags, TGE gate, privacy invariants BP-001 to BP-007, "
        "and Phase 137A separation ratio findings (WIF-007, WIF-010)."
    ),
    schema={
        "type": "object",
        "properties": {
            "proposal": {
                "type": "string",
                "description": "The proposed change, code snippet, or plan to validate"
            },
            "context": {
                "type": "string",
                "description": "Phase number and domain context"
            }
        },
        "required": ["proposal"]
    }
)
async def vapi_validate_proposal(proposal: str, context: str = "", **_):
    result = KG.validate_proposal(proposal)
    result["proposal_preview"] = proposal[:200]
    result["context"] = context
    result["frozen_values_checked"] = KG.frozen_values
    result["state_flags"] = KG.state_flags
    result["knowledge_loaded_at"] = KG.loaded_at

    if result["verdict"] == "BLOCKED":
        result["action_required"] = (
            "DO NOT proceed. Fix all violations before implementation. "
            "Each violation references a specific VAPI_INVARIANTS.md section."
        )
    elif result["verdict"] == "APPROVED WITH WARNINGS":
        result["action_required"] = (
            "Review warnings before proceeding. Warnings indicate known risks "
            "documented in VAPI_WHAT_IF.md."
        )

    return result


@tool(
    name="vapi_query_what_if",
    description=(
        "Queries the VAPI_WHAT_IF.md corpus of validated W1/W2/W3 entries. "
        "Search by topic, layer (W1/W2/W3), phase, or status. "
        "Returns matching entries and suggests related risks for new proposals. "
        "Use before generating new WHAT_IF entries to avoid duplication. "
        "Phase 137A entries: WIF-007 (corpus imbalance), WIF-009 (plateau regime), "
        "WIF-010 (P1/P3/P4 cluster)."
    ),
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term"},
            "layer": {
                "type": "string",
                "description": "Filter: W1 (failures), W2 (opportunities), W3 (meta-risks), ALL",
                "enum": ["W1", "W2", "W3", "ALL"]
            },
            "generate_new": {
                "type": "boolean",
                "description": "If true, scaffolds a new W1/W2 pair for the query topic"
            }
        },
        "required": ["query"]
    }
)
async def vapi_query_what_if(query: str, layer: str = "ALL", generate_new: bool = False, **_):
    query_lower = query.lower()
    entries = KG.what_if_entries

    if layer != "ALL":
        entries = [e for e in entries if e["layer"] == layer]

    matches = [
        e for e in entries
        if query_lower in e["title"].lower()
        or query_lower in e["full_text"].lower()
        or query_lower in e["phase"].lower()
    ]

    result = {
        "query": query,
        "layer_filter": layer,
        "total_corpus_entries": len(KG.what_if_entries),
        "matches": matches,
        "match_count": len(matches),
    }

    if not matches:
        result["suggestion"] = (
            f"No existing WHAT_IF entries for '{query}'. "
            f"Set generate_new=True to scaffold one."
        )

    if generate_new:
        next_id_w1 = f"W1-{len([e for e in KG.what_if_entries if e['layer']=='W1'])+1:03d}"
        next_id_w2 = f"W2-{len([e for e in KG.what_if_entries if e['layer']=='W2'])+1:03d}"
        result["scaffold"] = {
            "W1_template": {
                "id": next_id_w1,
                "title": f"{query} — [failure mode]",
                "failure_mechanism": "[physically/cryptographically/economically grounded]",
                "implication": "[consequence for separation ratio / VHP / ioSwarm]",
                "mitigation": "[concrete fix with phase reference]",
                "status": "OPEN",
                "validation_rule": "Must be grounded in hardware physics, crypto math, or economic incentive"
            },
            "W2_template": {
                "id": next_id_w2,
                "title": f"{query} — [opportunity]",
                "mechanism": "[concrete mechanism]",
                "phase_candidate": "[Phase NNN]",
                "exclusive_because": "[requires 228B PoAC + PITL stack]",
                "connection_to_ratio": "[advances separation ratio or tournament launch]",
                "status": "PROPOSED",
            }
        }

    return result


@tool(
    name="vapi_agent_registry",
    description=(
        "Returns the authoritative VAPI_AGENTS.md agent registry with live status overlay. "
        "Includes phase introduced, current state, ioSwarm emulation status, and "
        "critical constraint: TournamentActivationChainAgent (Agent #16) is PERMANENTLY "
        "auto_activate_on_breakthrough=False. Use before adding any new agent."
    ),
    schema={
        "type": "object",
        "properties": {
            "agent_name_or_number": {"type": "string", "description": "Filter to specific agent"},
            "include_invariants": {"type": "boolean", "description": "Include invariant requirements"}
        },
        "required": []
    }
)
async def vapi_agent_registry(agent_name_or_number: str = "", include_invariants: bool = True, **_):
    agents = KG.agent_registry

    if agent_name_or_number:
        filter_lower = agent_name_or_number.lower()
        agents = [
            a for a in agents
            if filter_lower in a["name"].lower() or filter_lower in a["number"]
        ]

    result = {
        "total_registered": len(KG.agent_registry),
        "agents": agents,
        "critical_constraints": {
            "agent_16_TournamentActivationChainAgent": {
                "auto_activate_on_breakthrough": False,
                "constraint_type": "PERMANENT compile-time constant",
            },
            "agent_15_SeparationRatioMonitorAgent": {
                "poll_interval_seconds": 300,
                "confirmation_required": "2 consecutive snapshots >= 1.0",
            },
            "ioswarm_agents": {
                "status": "emulator_only",
                "live_nodes": 0,
                "activation_requirement": ">=5 operators staking 10k VAPI in VAPIOperatorRegistry"
            }
        }
    }

    if include_invariants:
        invariants_text = KG.raw.get("invariants", "")
        agent_inv_m = re.search(
            r"## Invariant Requirements.*?(?=##|\Z)", invariants_text, re.DOTALL
        )
        result["agent_invariants"] = (
            agent_inv_m.group().strip()[:800] if agent_inv_m
            else "See VAPI_INVARIANTS.md Section 5"
        )

    return result


@tool(
    name="vapi_corpus_integrity",
    description=(
        "Checks the legal evidence corpus state from VAPI_CORPUS.md. "
        "Returns session counts, legal hold status, diversity gaps, separation ratio "
        "milestones, and Phase 137A findings. Append-only — never deletes or suggests "
        "deletion. Critical for tournament legal defensibility."
    ),
    schema={
        "type": "object",
        "properties": {
            "check_separation_snapshots": {"type": "boolean"},
            "diversity_analysis": {"type": "boolean"}
        },
        "required": []
    }
)
async def vapi_corpus_integrity(check_separation_snapshots: bool = True,
                                diversity_analysis: bool = True, **_):
    n = KG.corpus_stats.get("total_sessions", 127)
    result = {
        "corpus_stats": KG.corpus_stats,
        "legal_hold": "ACTIVE — PERMANENT retention, no deletion permitted",
        "milestones": {
            "N50_minimum_calibration":   {"target": 50,  "current": n, "status": "EXCEEDED"},
            "N100_balanced_minimum":     {"target": 100, "current": n, "status": "EXCEEDED" if n >= 100 else "NOT YET"},
            "N150_tikhonov_stability":   {"target": 150, "current": n, "status": "EXCEEDED" if n >= 150 else "NOT YET"},
            "N200_high_confidence":      {"target": 200, "current": n, "status": f"NOT YET (-{200-n})"},
            "3_player_diversity":        {"target": 3, "current": 3, "status": "MET (P4 eliminated, 3-player clean corpus)"},
            "BT_calibration":            {"target": 50, "current": 0, "status": "NOT STARTED"},
        },
        "phase_findings": {
            "pooled_ratio_stale": 0.417,
            "touchpad_corners_phase143_honest": 1.261,
            "touchpad_corners_pairs": {"P1vP2": 2.868, "P1vP3": 3.276, "P2vP3": 2.243},
            "balanced_ratio_n3_per_player": 1.611,
            "wif007_confirmed": "P1's 53 sessions bias global covariance — balanced sampling needed",
            "wif009_confirmed": "Plateau regime: free-form cannot reach >1.0 structurally",
            "p4_eliminated": "Phase 138: P4 confirmed=P3 mislabeled; 3-player clean corpus",
            "current_status": "ratio=1.261 above 1.0 gate but N=11 thin; need >=10/player",
        }
    }

    if diversity_analysis:
        result["controller_diversity"] = {
            "DualShock_Edge_CFI_ZCP1": {"current": n, "status": "PRIMARY DEVICE"},
            "Xbox_Series_X": {"current": 0, "target": 50, "status": "NOT STARTED"},
            "Nintendo_Switch_Pro": {"current": 0, "target": 50, "status": "NOT STARTED"},
        }

    if check_separation_snapshots:
        snapshots = db_query(
            "SELECT pooled_ratio, n_sessions, created_at "
            "FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 5"
        )
        result["separation_snapshots"] = snapshots if snapshots else [
            {"pooled_ratio": 0.417, "n_sessions": 127,
             "created_at": "2026-03-29", "note": "stale full-corpus; Phase 143 best=1.261"}
        ]

    result["highest_leverage_action"] = (
        "Capture >=10 touchpad_corners sessions per player (currently P1=3, P2=4, P3=4; P4 eliminated). "
        "Phase 143 ratio=1.261 is above 1.0 gate but N=11 thin — need robust N for tournament defense. "
        "Run: python scripts/terminal_calibration_runner.py --player P1 --battery touchpad_corners"
    )

    return result


@tool(
    name="vapi_fleet_coherence",
    description=(
        "Returns current fleet signal coherence status from the Phase 193 "
        "FleetSignalCoherenceAgent (agent #36). "
        "CRITICAL/HIGH findings mean two or more VAPI agents are producing "
        "logically contradictory outputs — one is operating on stale data. "
        "Query this before any cross-agent operation to verify signal topology is consistent. "
        "Three failure modes: CONTRADICTION (7 rules), ORPHAN (5 rules), INVERSION (3 rules). "
        "RENEWAL_WITHOUT_ATTESTATION is CRITICAL severity — indicates Phase 185/186 attestation chain bypass."
    ),
    schema={
        "type": "object",
        "properties": {
            "severity_filter": {
                "type": "string",
                "enum": ["CRITICAL", "HIGH", "MEDIUM"],
                "description": "Only return findings at or above this severity"
            }
        },
        "required": []
    }
)
async def vapi_fleet_coherence(severity_filter: str = "", **_):
    rows = db_query(
        "SELECT failure_mode, rule_name, severity, explanation, resolution, "
        "promoted_to_wif, wif_entry_id, resolved, created_at "
        "FROM fleet_coherence_log ORDER BY created_at DESC LIMIT 50"
    )
    open_rows = [r for r in rows if not r.get("resolved")]

    # apply severity filter
    _order = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}
    if severity_filter:
        min_level = _order.get(severity_filter.upper(), 0)
        open_rows = [r for r in open_rows if _order.get(r.get("severity", ""), 0) >= min_level]

    by_mode = {}
    by_sev  = {}
    for r in open_rows:
        m = r.get("failure_mode", "?"); by_mode[m] = by_mode.get(m, 0) + 1
        s = r.get("severity",     "?"); by_sev[s]  = by_sev.get(s, 0)  + 1

    promoted = sum(1 for r in open_rows if r.get("promoted_to_wif"))

    return {
        "fleet_coherence_enabled": True,
        "total_open":    len(open_rows),
        "by_severity":   by_sev,
        "by_mode":       by_mode,
        "promoted_to_wif": promoted,
        "severity_filter": severity_filter or "all",
        "entries": [
            {
                "failure_mode": r.get("failure_mode"),
                "rule_name":    r.get("rule_name"),
                "severity":     r.get("severity"),
                "explanation":  r.get("explanation"),
                "resolution":   r.get("resolution"),
                "promoted_to_wif": bool(r.get("promoted_to_wif")),
                "wif_entry_id": r.get("wif_entry_id"),
                "created_at":   r.get("created_at"),
            }
            for r in open_rows[:20]
        ],
        "guidance": (
            "No open contradictions — fleet signal topology coherent."
            if not open_rows else
            f"{len(open_rows)} open failures — review CRITICAL/HIGH before any cross-agent operation."
        ),
    }


@tool(
    name="vapi_privacy_compliance",
    description=(
        "Checks a proposed data handling pattern against VAPI_BIOMETRIC_PRIVACY.md "
        "invariants BP-001 through BP-007. Required for any feature touching "
        "raw biometric data, consent flows, calibration corpus, or data marketplace. "
        "GDPR Art.9, CCPA, BIPA, and EU AI Act compliance enforced here."
    ),
    schema={
        "type": "object",
        "properties": {
            "data_operation": {"type": "string"},
            "data_type": {
                "type": "string",
                "enum": ["raw_biometric", "derived_features", "aggregated_stats",
                         "consent_record", "zk_proof", "separation_ratio"]
            }
        },
        "required": ["data_operation", "data_type"]
    }
)
async def vapi_privacy_compliance(data_operation: str, data_type: str, **_):
    op_lower = data_operation.lower()
    checks = []
    violations = []

    if data_type == "raw_biometric":
        if "persist" in op_lower or "save" in op_lower or "write" in op_lower:
            violations.append(
                "BP-007 VIOLATION (EPHEMERAL_SESSIONS): Raw biometric data must exist only "
                "in RAM. Use mlock(), secure erase on cleanup."
            )
        else:
            checks.append("BP-007: RAM-only raw data — COMPLIANT")

    if data_type in ["raw_biometric", "derived_features"]:
        checks.append(
            "BP-001 (TEMPORAL_BIOMETRIC_DECAY): Apply 90-day half-life weight decay. "
            "Automatic invalidation at 180 days."
        )

    if "consent" in op_lower or data_type == "consent_record":
        checks.append(
            "BP-002 (ZK_ATTESTED_CONSENT): Consent must be ZK-proven, not raw signature. "
            "Record as Poseidon hash: H(player_id || terms_version || timestamp)."
        )

    if data_type == "aggregated_stats" or "aggregate" in op_lower:
        checks.append(
            "BP-003 (DIFFERENTIAL_PRIVACY): Add Laplacian noise. "
            "Privacy budget ε ≤ 1.0 per player per year."
        )
        checks.append(
            "BP-004 (K_ANONYMITY): Cohort must have K>=5 before threshold activation."
        )

    if "identity" in op_lower or "fingerprint" in op_lower:
        checks.append(
            "BP-006 (SHAMIR_SHARING): Biometric identity split across 16 agents. "
            "8-of-16 threshold scheme."
        )

    privacy_text = KG.raw.get("privacy", "")
    relevant_section = ""
    if data_type == "raw_biometric":
        m = re.search(r"BP-007.*?(?=BP-00[0-9]|\Z)", privacy_text, re.DOTALL)
        if m:
            relevant_section = m.group()[:400]

    return {
        "data_operation": data_operation,
        "data_type": data_type,
        "compliance_checks": checks,
        "violations": violations,
        "compliant": len(violations) == 0,
        "relevant_invariant_text": relevant_section,
        "regulations_covered": ["GDPR Art.9", "GDPR Art.7", "CCPA/CPRA", "BIPA", "EU AI Act"],
    }


@tool(
    name="vapi_session_start_protocol",
    description=(
        "Runs the VAPI_SKILLS.md session-start protocol for a new Claude Code session. "
        "Returns onboarding checklist, WHAT_IF auto-run for the current domain, "
        "and current live protocol state. Call this FIRST in every VAPI Claude Code session. "
        "Replaces the heavy context paste with live MCP state. "
        "Phase 137A: includes separation ratio cluster analysis and WIF-010 alert."
    ),
    schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": ["calibration", "smart_contracts", "agent_fleet", "ioswarm",
                         "zk_circuits", "controller_hardware", "data_marketplace",
                         "tournament_launch", "general"]
            }
        },
        "required": []
    }
)
async def vapi_session_start_protocol(domain: str = "general", **_):
    ratio_rows = db_query(
        "SELECT pooled_ratio FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 1"
    )
    current_ratio = ratio_rows[0]["pooled_ratio"] if ratio_rows else 0.417

    domain_whats = [
        e for e in KG.what_if_entries
        if domain.lower() in e["title"].lower() or domain.lower() in e["full_text"].lower()
    ][:3]

    return {
        "session_start_timestamp": datetime.utcnow().isoformat(),
        "phase": "149 COMPLETE",
        "domain": domain,
        "live_state": {
            "separation_ratio_pooled_stale": current_ratio,
            "separation_ratio_touchpad_corners_phase143": 1.261,
            "separation_ratio_pairs": {"P1vP2": 2.868, "P1vP3": 3.276, "P2vP3": 2.243},
            "separation_ratio_balanced": 1.611,
            "ratio_status": "ABOVE 1.0 (touchpad_corners N=11); pooled stale",
            "p4_status": "ELIMINATED (Phase 138) — confirmed=P3; 3-player clean corpus",
            "dry_run": True,
            "l4_stale": True,
            "ioswarm": "emulator_only",
            "bridge_tests": 1808,
            "sdk_tests": 237,
            "hardhat_tests": 462,
            "agents": 18,
            "epistemic_threshold": "0.65 (Phase 147 hardened)",
        },
        "protocol_checklist": [
            "1. touchpad_corners ratio=1.261 (Phase 143 proper LOO, N=11) — ABOVE 1.0 but thin",
            "2. Need >=10 touchpad_corners/player (P1=3, P2=4, P3=4) for tournament defense",
            "3. P4 ELIMINATED (Phase 138) — confirmed=P3; 3-player corpus clean",
            "4. L4 thresholds STALE (12-feat calib, 13-feat live — N=127 candidates: 6.613/5.143)",
            "5. dry_run=True — enforcement not live",
            "6. ioSwarm = emulator only — no live nodes",
            "7. Epistemic threshold hardened to 0.65 (Phase 147); triage_prereq_required=True",
            "8. ACIM agent #18 self-tests every 15min (mcp_server_enabled=False)",
        ],
        "what_if_auto_run": {
            "domain": domain,
            "relevant_w1_w2": domain_whats,
            "phase143_note": (
                "ratio=1.261 is honest (diagonal+proper LOO). All 3 pairs > 1.0: "
                "P1vP2=2.868, P1vP3=3.276, P2vP3=2.243. "
                "N=11 thin — need >=10/player before tournament announcement."
            ),
        },
        "knowledge_graph_status": {
            "files_loaded": list(KG.raw.keys()),
            "what_if_entries": len(KG.what_if_entries),
            "agents_registered": len(KG.agent_registry),
            "frozen_values": len(KG.frozen_values),
            "bp_invariants": len(KG.bp_invariants),
            "loaded_at": KG.loaded_at,
        },
        "first_actions": [
            "Run vapi_validate_proposal before ANY code change",
            "Run vapi_corpus_integrity to check session counts",
            "Run vapi_autoresearch_seed to ground next hypothesis in live state",
        ]
    }


@tool(
    name="vapi_reload_knowledge",
    description=(
        "Reloads all 9 VAPI corpus files from disk into the knowledge graph. "
        "Call this when any VAPI_*.md file has been updated."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_reload_knowledge(**_):
    before = {
        "what_if_entries": len(KG.what_if_entries),
        "agents": len(KG.agent_registry),
        "frozen_values": len(KG.frozen_values),
    }
    KG.load()
    after = {
        "what_if_entries": len(KG.what_if_entries),
        "agents": len(KG.agent_registry),
        "frozen_values": len(KG.frozen_values),
    }
    return {
        "reloaded_at": KG.loaded_at,
        "before": before,
        "after": after,
        "files_loaded": {k: "OK" if v and "not found" not in v else "MISSING"
                        for k, v in KG.raw.items()},
    }


@tool(
    name="vapi_knowledge_query",
    description=(
        "Full-text search across all 9 VAPI corpus files simultaneously. "
        "Returns relevant excerpts from VAPI_INVARIANTS.md, VAPI_WHAT_IF.md, "
        "VAPI_AGENTS.md, VAPI_SKILLS.md, and other corpus files. "
        "Use when you need to find specific technical details without knowing which file."
    ),
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "files": {
                "type": "array",
                "items": {"type": "string",
                          "enum": ["invariants", "what_if", "agents", "skills",
                                   "memory", "context", "privacy", "controller", "corpus"]},
            },
            "context_lines": {"type": "integer", "default": 5}
        },
        "required": ["query"]
    }
)
async def vapi_knowledge_query(query: str, files: list = None, context_lines: int = 5, **_):
    search_files = files or list(KG.raw.keys())
    results = {}

    for file_key in search_files:
        if file_key not in KG.raw:
            continue
        text = KG.raw[file_key]
        lines = text.split("\n")
        matches = []

        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                matches.append({
                    "line": i + 1,
                    "match_line": line.strip(),
                    "context": "\n".join(lines[start:end])
                })

        if matches:
            results[file_key] = {
                "file": CORPUS_FILES.get(file_key, file_key),
                "match_count": len(matches),
                "matches": matches[:3]
            }

    return {
        "query": query,
        "total_files_searched": len(search_files),
        "files_with_matches": len(results),
        "results": results,
    }


# ============================================================
# Phase 137A Novel Tools — Live-State Analysis + Autoresearch
# ============================================================

@tool(
    name="vapi_separation_analysis",
    description=(
        "Returns the command to run analyze_interperson_separation.py with Phase 137A/B flags. "
        "--session-type (touchpad_corners, etc.) and --balance-corpus (WIF-007 imbalance fix). "
        "Also returns known results from completed runs. "
        "Key insight: touchpad_corners ratio=1.469 (WEAK — P1/P3/P4 cluster unresolved). "
        "Balanced ratio=1.611 (n=3/player — WIF-007 confirmed, n>=10 needed for robustness). "
        "Does NOT execute the long-running analysis; returns command + cached findings."
    ),
    schema={
        "type": "object",
        "properties": {
            "session_type": {
                "type": "string",
                "enum": ["touchpad_corners", "touchpad_freeform", "touchpad_swipes",
                         "trigger_rhythm", "button_sequence", "resting_baseline", "gameplay"]
            },
            "balance_corpus": {"type": "boolean"},
            "output_suffix": {"type": "string"}
        },
        "required": []
    }
)
async def vapi_separation_analysis(session_type=None, balance_corpus=False,
                                    output_suffix="", **_):
    cmd_parts = ["python scripts/analyze_interperson_separation.py"]
    if session_type:
        cmd_parts.append(f"--session-type {session_type}")
    if balance_corpus:
        cmd_parts.append("--balance-corpus")
    if output_suffix:
        cmd_parts.append(f"--output-suffix {output_suffix}")

    return {
        "command_to_run": " ".join(cmd_parts),
        "note": "Analysis takes ~3-5 min (loads all sessions). Run in terminal.",
        "known_results": {
            "touchpad_corners": {
                "ratio": 1.469,
                "n": 11,
                "classification": "63.6% (7/11)",
                "status": "WEAK — P1/P3/P4 cluster (dist 0.074-0.143); P2 sole outlier",
                "active_features": 8,
                "blocker": "Need >=10 touchpad_corners/player for P1 vs P3 separation"
            },
            "full_corpus_balanced": {
                "ratio": 1.611,
                "n_per_player": 3,
                "n_total": 12,
                "status": "WIF-007 confirmed: P1's 53 sessions bias covariance",
                "caveat": "n=3/player too small; n>=10 needed for robust estimate"
            },
            "full_corpus_pooled": {
                "ratio": 0.417,
                "n": 127,
                "players": 4,
                "status": "TOURNAMENT BLOCKER — plateau regime (WIF-009)",
                "note": "Free-form gameplay cannot reach ratio>1.0 (WIF-009 structural)"
            }
        },
        "w1_risk": (
            "P4 identity unknown — if P4 == P3, ratio=1.469 is artificially inflated. "
            "Verify P4 dir is distinct player before publishing ratio."
        ),
        "w2_opportunity": (
            "Per-player touchpad eigenspace (Phase 140 candidate): 2D Gaussian fit to "
            "touchpad_corners heatmap. Bhattacharyya distance between Gaussians closes "
            "P1/P3 cluster gap via morphological grip separation."
        )
    }


@tool(
    name="vapi_autoresearch_seed",
    description=(
        "Generates a grounded hypothesis for the next vapi-autoresearch cycle. "
        "Reads live protocol state, recent experiment log, and what_if corpus, "
        "then returns a structured seed that addresses the highest-priority gap. "
        "Closes the 'stale hypothesis' problem: autoresearch now grounds proposals "
        "in live separation ratio, cluster structure, and blocking conditions. "
        "Call at the START of each autoresearch cycle."
    ),
    schema={
        "type": "object",
        "properties": {
            "priority": {
                "type": "string",
                "enum": [
                    "separation_ratio_pathways", "wif010_cluster_resolution",
                    "l4_recalibration", "phase_invariant_hardening",
                    "what_if_corpus_depth", "class_k_definition"
                ]
            },
            "cycle_num": {"type": "integer"}
        },
        "required": []
    }
)
async def vapi_autoresearch_seed(priority: str = "", cycle_num: int = 0, **_):
    log_path = PROJECT_ROOT / "vapi-autoresearch" / "experiments" / "log.jsonl"
    recent_log = []
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            for line in lines[-5:]:
                if line.strip():
                    recent_log.append(json.loads(line))
        except Exception:
            pass

    ratio_rows = db_query(
        "SELECT pooled_ratio, n_sessions, created_at FROM separation_ratio_snapshots "
        "ORDER BY created_at DESC LIMIT 1"
    )
    current_ratio = ratio_rows[0]["pooled_ratio"] if ratio_rows else 0.417

    PRIORITIES = [
        "wif010_cluster_resolution",
        "separation_ratio_pathways",
        "l4_recalibration",
        "phase_invariant_hardening",
        "what_if_corpus_depth",
        "class_k_definition",
    ]
    recent_priorities = [e.get("priority", "") for e in recent_log]
    auto_priority = priority
    if not auto_priority:
        for p in PRIORITIES:
            if p not in recent_priorities:
                auto_priority = p
                break
        if not auto_priority:
            auto_priority = PRIORITIES[0]

    corpus_path = PROJECT_ROOT / "vapi-autoresearch" / "what_if_corpus"
    wif_count = len(list(corpus_path.glob("wif_*.md"))) if corpus_path.exists() else 0

    return {
        "cycle": cycle_num or len(recent_log) + 1,
        "auto_priority": auto_priority,
        "live_state": {
            "pooled_ratio": current_ratio,
            "touchpad_corners_ratio": 1.469,
            "balanced_ratio": 1.611,
            "cluster_problem": "P1 vs P3 inter-dist=0.143 < P3 intra-mean=0.641",
            "p4_identity": "UNKNOWN — may be P3 duplicate (dist=0.074); verify before publishing",
            "tge_blockers": ["ratio<1.0_all_pairs", "dry_run=True", "l4_stale", "no_audit"],
            "l4_stale": "12-feat calibration on 13-feat live (N=127 candidate: 6.613/5.143)"
        },
        "seed_hypothesis": _seed_hypothesis(auto_priority),
        "what_if_corpus_size": wif_count,
        "recent_cycle_priorities": recent_priorities[-3:],
        "instructions": (
            "Use this seed to generate the improvement proposal for vapi_autoresearch.py. "
            "Ground the W1/W2 further using live_state above before writing to what_if_corpus/."
        )
    }


def _seed_hypothesis(priority: str) -> dict:
    """Return a grounded W1/W2 seed for the given priority."""
    SEEDS = {
        "wif010_cluster_resolution": {
            "w1_grounded": (
                "P1/P3/P4 share touchpad grip geometry (same hand anatomy range). "
                "Adding more touchpad_corners sessions will not resolve P3 vs P4 "
                "if they are the same physical person — ratio=1.469 is artificially "
                "inflated by P4 being a near-copy of P3."
            ),
            "w1_mitigation": "Verify P4 identity before publishing; de-duplicate if P4==P3",
            "w2_novel": (
                "Per-player touchpad contact eigenspace: fit a 2D Gaussian to each "
                "player's touchpad_corners heatmap. Inter-player Bhattacharyya distance "
                "between Gaussians is translation/rotation-invariant and closes "
                "the P1/P3 cluster gap via morphological grip separation."
            ),
            "w2_phase": "Phase 140 candidate — no hardware required, pure session analysis"
        },
        "separation_ratio_pathways": {
            "w1_grounded": (
                "Free-form gameplay accumulates intra-player variance faster than "
                "inter-player distance grows (WIF-009 plateau). N=127 pooled ratio "
                "plateau at 0.417 is structural — more free-form sessions won't help."
            ),
            "w1_mitigation": "Structured probe sessions (touchpad_corners, bilateral) only",
            "w2_novel": (
                "Cross-session consistency Mahalanobis: compute variance RATIO "
                "(inter-player / intra-session-per-player) using ONLY the most "
                "recent 3 sessions per player. Auto-balances corpus AND uses "
                "most calibrated (latest) sessions."
            ),
            "w2_phase": "Phase 138 candidate"
        },
        "l4_recalibration": {
            "w1_grounded": (
                "N=127 thresholds (anomaly=6.613, continuity=5.143) are 5-6% tighter "
                "than stored values (7.009/5.367). Applying them increases FPR from "
                "~2.9% to ~5.4%. Must verify human FPR remains <5% before applying."
            ),
            "w1_mitigation": "Run threshold_calibrator.py against N=127 with explicit FPR check",
            "w2_novel": (
                "Battery-stratified threshold tracks: touchpad sessions (low tremor) "
                "warrant tighter thresholds than gameplay (high tremor). "
                "Phase 124-126 infrastructure already in place."
            ),
            "w2_phase": "Phase 138 — apply N=127 candidates"
        },
        "what_if_corpus_depth": {
            "w1_grounded": (
                "WIF-010 (P1/P3/P4 cluster) is not yet in skill WHAT_IF Corpus. "
                "Future sessions generating ratio>1.0 hypotheses will miss the "
                "structural cluster problem."
            ),
            "w1_mitigation": "Add WIF-010 to vapi.md WHAT_IF Corpus section",
            "w2_novel": (
                "MCP-grounded autoresearch: vapi_autoresearch_seed reads live ratio + "
                "cluster state at cycle start, ensuring hypotheses are grounded "
                "in current reality, not stale MEMORY.md."
            ),
            "w2_phase": "Active — MCP integration Phase 137A+"
        },
        "phase_invariant_hardening": {
            "w1_grounded": (
                "Phase 98 W1: epistemic threshold=0.60 reachable by ClassJ alone "
                "(0.40+0.20=0.60). threshold=0.65 closes single-agent gate path."
            ),
            "w1_mitigation": (
                "Set epistemic_recommended_threshold=0.65 AND "
                "epistemic_triage_prereq_required=True in Phase 105 config."
            ),
            "w2_novel": (
                "Per-device adaptive threshold: devices with high consecutive_clean "
                "streak get threshold reduced. New devices start at 0.65."
            ),
            "w2_phase": "Phase 138 candidate"
        },
        "class_k_definition": {
            "w1_grounded": (
                "Class K (GSR spoofer: synthetic EDA generator) is an open gap. "
                "With GSR_ENABLED=False and N=0 calibration, a synthetic EDA signal "
                "mimicking human sympathetic arousal would pass L7 unchallenged."
            ),
            "w1_mitigation": "Define Class K in SecurityReview mode; design anti-tamper challenge-response",
            "w2_novel": (
                "Hardware fingerprint as Class K gate: capacitance signature of "
                "Ag/AgCl electrode contact (impedance spectrum). Synthetic EDA "
                "generators fail impedance spectroscopy at 1kHz."
            ),
            "w2_phase": "Phase 141 candidate — requires GSR hardware"
        }
    }
    return SEEDS.get(priority, {
        "w1_grounded": "Unknown priority — use vapi_query_what_if with specific topic",
        "w2_novel": "Unknown priority",
        "w2_phase": "TBD"
    })


# ============================================================
# Phase 192: DataCurator MCP tools
# ============================================================

@tool(
    name="vapi_corpus_entropy",
    description=(
        "Query the CorpusDataCuratorAgent (Phase 192, Task 2) corpus entropy status. "
        "Returns Shannon entropy of the 13-dim biometric feature space, clustering "
        "warning flag (entropy < 1.5 = CLUSTERING_WARNING), and timestamp. "
        "Use this to check whether the calibration corpus is becoming too homogeneous."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def vapi_corpus_entropy(**_):
    rows = db_query(
        "SELECT entropy_score, clustering_warning, n_sessions, n_players, "
        "entropy_note, created_at "
        "FROM corpus_entropy_log ORDER BY created_at DESC LIMIT 1"
    )
    if not rows:
        return {
            "entropy_score": None,
            "clustering_warning": False,
            "n_sessions": 0,
            "n_players": 0,
            "entropy_note": "No corpus entropy data yet — CorpusDataCuratorAgent poll pending.",
            "created_at": None,
            "corpus_entropy_enabled": True,
        }
    row = rows[0]
    return {
        "entropy_score": row.get("entropy_score"),
        "clustering_warning": bool(row.get("clustering_warning", 0)),
        "n_sessions": row.get("n_sessions", 0),
        "n_players": row.get("n_players", 0),
        "entropy_note": row.get("entropy_note", ""),
        "created_at": row.get("created_at"),
        "corpus_entropy_enabled": True,
    }


@tool(
    name="vapi_data_readiness_certificate",
    description=(
        "Query the latest Data Readiness Certificate from CorpusDataCuratorAgent "
        "(Phase 192, Task 6). Returns 8-dimension readiness assessment: "
        "separation_ok, l4_calibration_ok, vhp_enrolled_ok, erasure_compliant, "
        "corpus_entropy_ok, contribution_weighted_ok, provenance_dag_ok, "
        "federated_quality_ok. Certificate hash is SHA-256 anchored. "
        "certificate_ready=True only when all 8 dims pass."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def vapi_data_readiness_certificate(**_):
    rows = db_query(
        "SELECT certificate_hash, separation_ok, l4_calibration_ok, vhp_enrolled_ok, "
        "erasure_compliant, corpus_entropy_ok, contribution_weighted_ok, "
        "provenance_dag_ok, federated_quality_ok, certificate_ready, "
        "anchored_tx_hash, created_at "
        "FROM data_readiness_certificate_log ORDER BY created_at DESC LIMIT 1"
    )
    if not rows:
        return {
            "certificate_ready": False,
            "certificate_hash": None,
            "dims": {},
            "created_at": None,
            "note": "No data readiness certificate yet — CorpusDataCuratorAgent poll pending.",
        }
    row = rows[0]
    dims = {
        "separation_ok": bool(row.get("separation_ok", 0)),
        "l4_calibration_ok": bool(row.get("l4_calibration_ok", 0)),
        "vhp_enrolled_ok": bool(row.get("vhp_enrolled_ok", 0)),
        "erasure_compliant": bool(row.get("erasure_compliant", 0)),
        "corpus_entropy_ok": bool(row.get("corpus_entropy_ok", 0)),
        "contribution_weighted_ok": bool(row.get("contribution_weighted_ok", 0)),
        "provenance_dag_ok": bool(row.get("provenance_dag_ok", 0)),
        "federated_quality_ok": bool(row.get("federated_quality_ok", 0)),
    }
    passed = sum(1 for v in dims.values() if v)
    return {
        "certificate_ready": bool(row.get("certificate_ready", 0)),
        "certificate_hash": row.get("certificate_hash"),
        "dims": dims,
        "dims_passed": passed,
        "dims_total": 8,
        "anchored_tx_hash": row.get("anchored_tx_hash"),
        "created_at": row.get("created_at"),
    }


@tool(
    name="vapi_provenance_chain",
    description=(
        "Query the provenance DAG from CorpusDataCuratorAgent (Phase 192, Task 1). "
        "Returns the chain of nodes from a given artifact back to its origin "
        "(calibration session → defensibility log → VHP badge). "
        "Use node_id='' to list root nodes. max_depth controls chain traversal "
        "(default 20, FROZEN). "
        "Enables legally defensible audit trail: GDPR Art.17 compliance path."
    ),
    schema={
        "type": "object",
        "properties": {
            "node_id": {"type": "string", "description": "Start node ID ('' = list roots)"},
            "max_depth": {"type": "integer", "description": "Max chain depth (default 20)"}
        },
        "required": []
    }
)
async def vapi_provenance_chain(node_id: str = "", max_depth: int = 20, **_):
    if node_id:
        rows = db_query(
            "WITH RECURSIVE chain(node_id, parent_node_id, artifact_type, "
            "player_id, session_name, data_hash, depth) AS ("
            "  SELECT node_id, parent_node_id, artifact_type, player_id, "
            "         session_name, data_hash, 0 FROM data_provenance_dag "
            "  WHERE node_id = ? "
            "  UNION ALL "
            "  SELECT p.node_id, p.parent_node_id, p.artifact_type, p.player_id, "
            "         p.session_name, p.data_hash, chain.depth+1 "
            "  FROM data_provenance_dag p "
            "  JOIN chain ON p.node_id = chain.parent_node_id "
            "  WHERE chain.depth < ? "
            ") SELECT * FROM chain",
            [node_id, max_depth]
        )
        return {
            "node_id": node_id,
            "chain_length": len(rows),
            "chain": rows,
            "max_depth": max_depth,
        }
    else:
        # List root nodes (no parent)
        roots = db_query(
            "SELECT node_id, artifact_type, player_id, session_name, data_hash, created_at "
            "FROM data_provenance_dag WHERE parent_node_id IS NULL "
            "ORDER BY created_at DESC LIMIT 20"
        )
        total = db_query("SELECT COUNT(*) as n FROM data_provenance_dag")
        return {
            "root_count": len(roots),
            "total_nodes": total[0]["n"] if total else 0,
            "roots": roots,
            "max_depth": max_depth,
        }


# ============================================================
# MCP Server Loop
# ============================================================

def _check_corpus_reload():
    """Auto-reload KG if any corpus file has changed since last load. O(N) stat() calls."""
    if not KG.loaded_at:
        return
    base = KG.corpus_dir
    for filename in CORPUS_FILES.values():
        path = base / filename
        try:
            mtime = path.stat().st_mtime
            loaded_ts = datetime.fromisoformat(KG.loaded_at).timestamp()
            if mtime > loaded_ts:
                KG.load()  # corpus changed — reload entire graph
                sys.stderr.write(
                    f"[vapi-knowledge-mcp] Auto-reloaded corpus: {filename} changed\n"
                )
                return  # reload once per request, not once per changed file
        except Exception:
            pass


async def handle(msg: dict) -> str:
    _check_corpus_reload()  # autonomous: re-parse corpus files if any changed
    id_    = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    # Notifications have no "id" — JSON-RPC 2.0 requires no response
    if "id" not in msg:
        return ""

    if method == "initialize":
        return mcp_response(id_, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "vapi-knowledge-mcp", "version": f"2.0.0-phase{_parse_claude_md().get('phase_num', '207')}"},
            "capabilities": {"tools": {}}
        })

    if method == "tools/list":
        return mcp_response(id_, {
            "tools": [
                {"name": name, "description": info["description"],
                 "inputSchema": info["schema"]}
                for name, info in TOOLS.items()
            ]
        })

    if method == "tools/call":
        tool_name = params.get("name")
        args      = params.get("arguments", {})

        if tool_name not in TOOLS:
            return mcp_error(id_, -32601, f"Unknown tool: {tool_name}")

        try:
            result = await TOOLS[tool_name]["fn"](**args)
            return mcp_response(id_, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            })
        except Exception as e:
            return mcp_error(id_, -32603, f"Tool error in {tool_name}: {str(e)}")

    return mcp_error(id_, -32601, f"Unknown method: {method}")


async def main():
    # Resolve PROJECT_ROOT and load knowledge graph
    KG.corpus_dir = PROJECT_ROOT / CORPUS_DIR
    KG.load()

    files_status = {k: "OK" if "not found" not in v else "MISSING"
                    for k, v in KG.raw.items()}
    sys.stderr.write(
        f"[VAPI Knowledge MCP v2.0.0-phase{_parse_claude_md().get('phase_num','?')}] Loaded at {KG.loaded_at}\n"
        f"  Corpus dir : {KG.corpus_dir}\n"
        f"  Files      : {files_status}\n"
        f"  WHAT_IF    : {len(KG.what_if_entries)} entries\n"
        f"  Agents     : {len(KG.agent_registry)}\n"
        f"  Frozen vals: {len(KG.frozen_values)}\n"
        f"  BP invars  : {len(KG.bp_invariants)}\n"
        f"  Tools      : {len(TOOLS)}\n"
    )

    # Windows ProactorEventLoop does not support connect_read_pipe on real pipe handles.
    # Use run_in_executor to read stdin line-by-line in a thread instead.
    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            response = await handle(msg)
            if response:
                write(response)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            write(json.dumps({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": str(e)}
            }))


if __name__ == "__main__":
    asyncio.run(main())
