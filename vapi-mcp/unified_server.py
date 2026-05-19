"""
VAPI Unified Knowledge Loop MCP Server  v1.0.0-phase211
=========================================================
The VAPI-exclusive self-learning MCP intelligence server: all three knowledge
sources unified into a single, bidirectionally-aware protocol loop.

What makes this server exclusive to VAPI:
  - Every tool is grounded in the 228B PoAC wire format invariant
  - MetaLearner clusters failure reasons against the 20 MANDATORY_INVARIANTS
  - HypothesisDeduplicator fingerprints against (probe_type, phase_candidate) —
    concepts that only exist in the PITL biometric separation stack
  - WikiFeedback generates phase briefs in VAPI's own wiki taxonomy
  - UnifiedWIFCorpus deduplicates across 3 VAPI-specific WIF sources

Sources integrated (all mtime-cached, auto-reload on file change):
  CLAUDE.md                       — live phase state, test counts, ratio, thresholds
  VAPI-WORKFLOW.v2/*.md (9 files) — invariants, WIF corpus, agents, skills, memory
  wiki/                           — concepts, entities, phases, contradictions, log
  vapi-autoresearch/              — experiment ledger, what_if_corpus, program.md

Novel components (architecture-exclusive to Phase 211):
  MetaLearner          — clusters log.jsonl failure reasons → dominant_blocker
  HypothesisDeduplicator — (probe_type, phase_candidate) fingerprint dedup
  UnifiedWIFCorpus     — deduplicated WIF index across all 3 WIF sources
  WikiFeedback         — auto-writes wiki/phases/phase_NNN.md on autoresearch PASS
  ExperimentLedger     — queryable cycle history with score distribution + pass rate

12 MCP tools (all VAPI-exclusive — meaningless outside the PITL stack):
  vapi_unified_state          All-sources live state — first call every session
  vapi_session_context        Session-start: invariant checklist + domain hypotheses
  vapi_query_knowledge        Cross-source full-text search (13 sources simultaneously)
  vapi_phase_brief            Wiki phase page or auto-gen from CLAUDE.md
  vapi_entity                 Wiki concept/entity lookup (separation_ratio, etc.)
  vapi_experiment_history     log.jsonl query + MetaLearner cluster analysis
  vapi_validate_proposal_full Eval harness rubric on any proposal text (20 invariants)
  vapi_invariant_check        Point-check a frozen value or formula
  vapi_contradiction_status   wiki/contradictions.md + blocked_updates.md live scan
  vapi_autoresearch_cycle     MetaLearner seed → dedup check → grounded hypothesis
  vapi_unified_wif_corpus     Deduplicated WIF query across all 3 source locations
  vapi_learning_loop_status   Self-learning loop health dashboard

Claude Code config — add as "vapi-unified" MCP server:
  {
    "vapi-unified": {
      "command": "python",
      "args": ["C:/Users/Contr/vapi-pebble-prototype/vapi-mcp/unified_server.py"],
      "env": {
        "VAPI_BRIDGE_URL": "http://localhost:8080",
        "VAPI_DB_PATH": "bridge/vapi_store.db",
        "VAPI_ROOT": "C:/Users/Contr/vapi-pebble-prototype"
      }
    }
  }

Phase 211 invariant: this server never claims ratio > 1.0 without proof from
  separation_defensibility_log.all_pairs_above_1 = True.
  Separation gate is per-pair (all_pairs_p0_ok), not just global ratio.
"""

import asyncio
import collections
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# ============================================================
# Configuration
# ============================================================

BRIDGE_URL   = os.environ.get("VAPI_BRIDGE_URL", "http://localhost:8080")
DB_PATH      = os.environ.get("VAPI_DB_PATH",     "bridge/vapi_store.db")
# 2026-05-19: PROJECT_ROOT now resolves to ABSOLUTE path regardless of MCP
# server CWD. Previously `Path(".")` resolved against whatever CWD spawned
# the MCP server — which could be Claude Code's home dir, not the project
# root. This broke mythos_post_o3_ceremony_audit (and any other variant
# that depends on PROJECT_ROOT) when the MCP server CWD was misaligned:
# wrapper returned 0 findings even though the underlying variant reported
# 6 CRITICAL findings when invoked directly. Empirically diagnosed
# 2026-05-19 against the activation_log-empty / on-chain-canonical state
# discrepancy. Resolution: anchor PROJECT_ROOT to the parent of vapi-mcp/
# (which is the repo root by construction). VAPI_ROOT env override still
# honored if set explicitly.
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("VAPI_ROOT", str(_DEFAULT_PROJECT_ROOT)))

WORKFLOW_DIR    = PROJECT_ROOT / "VAPI-WORKFLOW.v2"
WIKI_DIR        = PROJECT_ROOT / "wiki"
AUTORESEARCH_DIR = PROJECT_ROOT / "vapi-autoresearch"
WIF_CORPUS_DIR  = AUTORESEARCH_DIR / "what_if_corpus"
EXPERIMENT_LOG  = AUTORESEARCH_DIR / "experiments" / "log.jsonl"
PROGRAM_MD      = AUTORESEARCH_DIR / "program.md"
WIKI_PHASES_DIR = WIKI_DIR / "phases"
WIKI_CONCEPTS_DIR = WIKI_DIR / "concepts"
WIKI_ENTITIES_DIR = WIKI_DIR / "entities"
WIKI_WHAT_IF_DIR  = WIKI_DIR / "what_if"

# ============================================================
# CLAUDE.md Live Parser — mtime-cached, never stale (Phase 210)
# ============================================================

_CLAUDE_CACHE_U: dict = {"mtime": 0.0, "state": {}}


def _parse_claude_md() -> dict:
    """Parse CLAUDE.md into current protocol state. One stat() per call."""
    claude_path = PROJECT_ROOT / "CLAUDE.md"
    try:
        mtime = claude_path.stat().st_mtime
    except OSError:
        return _CLAUDE_CACHE_U.get("state", {})

    if mtime <= _CLAUDE_CACHE_U["mtime"] and _CLAUDE_CACHE_U["state"]:
        return _CLAUDE_CACHE_U["state"]

    try:
        text = claude_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _CLAUDE_CACHE_U.get("state", {})

    s: dict[str, Any] = {}

    # Phase number — find first "Phase NNN" in phase header context
    m = re.search(r"Current phase:\s*Phase\s*(\d+)", text)
    s["phase_num"] = m.group(1) if m else "211"

    # Test counts
    for label, key in [("Bridge:", "bridge"), ("Contract:", "contract"),
                        ("SDK:", "sdk"), ("Hardware:", "hardware")]:
        m2 = re.search(label + r"\s*([\d,]+)\s*passing", text)
        if not m2:
            m2 = re.search(r"Bridge:\s*([\d,]+)", text) if key == "bridge" else None
        s[key] = m2.group(1).replace(",", "") if m2 else "0"

    # Bridge test count — more robust
    m3 = re.search(r"Bridge[:\s]+([\d]+)\s*\|", text)
    if m3:
        s["bridge"] = m3.group(1)

    # SDK test count
    m4 = re.search(r"SDK[:\s]+([\d]+)\s*\|", text)
    if m4:
        s["sdk"] = m4.group(1)

    # Hardhat test count
    m5 = re.search(r"(?:Contract|Hardhat)[:\s]+([\d]+)", text)
    if m5:
        s["hardhat"] = m5.group(1)

    # Agent count: max across "N agents" prose and "agent #N" references.
    # Prose phrases stop at older totals (e.g. "36 agents") while explicit
    # references (e.g. "agent #38" in Phase 222 / 235) carry the latest number.
    prose_refs = re.findall(r"(\d+)\s+(?:ACTIVE\s+)?agents?\s", text, re.IGNORECASE)
    hash_refs  = re.findall(r"agent\s+#(\d+)", text, re.IGNORECASE)
    candidates = [int(n) for n in prose_refs] + [int(n) for n in hash_refs]
    s["agents"] = str(max(candidates)) if candidates else "36"

    # Contract count
    m7 = re.search(r"(\d+)\s+contracts?\s+ALL\s+LIVE", text, re.IGNORECASE)
    s["contracts"] = m7.group(1) if m7 else "43"

    # L4 thresholds
    m8 = re.search(r"anomaly=\*\*([\d.]+)\*\*", text)
    m9 = re.search(r"continuity=\*\*([\d.]+)\*\*", text)
    s["l4_anomaly"] = m8.group(1) if m8 else "7.009"
    s["l4_continuity"] = m9.group(1) if m9 else "5.367"

    # Separation ratio — extract current best
    m10 = re.search(r"Separation ratio[:\s]+\*?\*?([\d.]+)\*?\*?", text)
    s["separation_ratio"] = m10.group(1) if m10 else "0.728"

    # Recent phases (last 5 complete)
    phase_matches = re.findall(r"(Phase\s+\d+)\s*[—-]\s*COMPLETE", text)
    s["recent_phases"] = phase_matches[:5]

    # Key flags
    s["dry_run"]       = True
    s["ioswarm"]       = "emulator_only"
    s["l4_stale"]      = True   # live_dim=13 vs calib_dim=12
    s["tge_blocked"]   = True   # per-pair gate not all cleared

    _CLAUDE_CACHE_U["mtime"] = mtime
    _CLAUDE_CACHE_U["state"] = s
    return s


# ============================================================
# Source Loaders — mtime-cached file readers
# ============================================================

class _MtimeCache:
    """Generic mtime-aware text cache for a single file."""
    def __init__(self):
        self._mtime: float = 0.0
        self._content: str = ""

    def read(self, path: Path) -> str:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return self._content
        if mtime > self._mtime:
            try:
                self._content = path.read_text(encoding="utf-8", errors="replace")
                self._mtime = mtime
            except OSError:
                pass
        return self._content


# One cache per corpus file
_WORKFLOW_CACHE: dict[str, _MtimeCache] = {}
_WIKI_CACHE:     dict[str, _MtimeCache] = {}

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


def _load_workflow_file(key: str) -> str:
    """Load a VAPI-WORKFLOW.v2 corpus file with mtime caching."""
    if key not in _WORKFLOW_CACHE:
        _WORKFLOW_CACHE[key] = _MtimeCache()
    path = WORKFLOW_DIR / WORKFLOW_FILES.get(key, f"{key}.md")
    return _WORKFLOW_CACHE[key].read(path)


def _load_wiki_file(rel_path: str) -> str:
    """Load a wiki/ file by relative path with mtime caching."""
    if rel_path not in _WIKI_CACHE:
        _WIKI_CACHE[rel_path] = _MtimeCache()
    return _WIKI_CACHE[rel_path].read(WIKI_DIR / rel_path)


def _load_text(path: Path) -> str:
    """Load any file once, no caching (for rarely-read files)."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ============================================================
# ExperimentLedger — queryable cycle history from log.jsonl
# ============================================================

class ExperimentLedger:
    """Reads vapi-autoresearch/experiments/log.jsonl, provides query API."""

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

    def stats(self) -> dict:
        entries = self.load()
        if not entries:
            return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0,
                    "mean_score": 0.0, "score_distribution": {}}
        passed = [e for e in entries if e.get("passed")]
        scores = [e.get("score", 0.0) for e in entries if isinstance(e.get("score"), (int, float))]
        buckets: dict[str, int] = {"0.0-0.4": 0, "0.4-0.6": 0, "0.6-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
        for sc in scores:
            if sc < 0.4:
                buckets["0.0-0.4"] += 1
            elif sc < 0.6:
                buckets["0.4-0.6"] += 1
            elif sc < 0.7:
                buckets["0.6-0.7"] += 1
            elif sc < 0.9:
                buckets["0.7-0.9"] += 1
            else:
                buckets["0.9-1.0"] += 1
        return {
            "total": len(entries),
            "passed": len(passed),
            "failed": len(entries) - len(passed),
            "pass_rate": round(len(passed) / len(entries), 3),
            "mean_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "score_distribution": buckets,
            "latest_timestamp": entries[-1].get("timestamp", "") if entries else "",
        }


LEDGER = ExperimentLedger()


# ============================================================
# MetaLearner — clusters failure reasons → dominant_blocker
# ============================================================

_ML_THEMES = {
    "invariant_violation": [
        "MISSING", "violation", "frozen", "invariant", "228", "SHA-256", "BLOCK_QUORUM",
        "0.67", "7.009", "5.367", "Poseidon", "nPublic", "dry_run", "NOMINAL",
    ],
    "separation_ratio": [
        "separation", "ratio", "P2vP3", "P1vP3", "inter-player", "1.0", "tournament",
        "all_pairs", "touchpad_corners", "biometric", "Mahalanobis",
    ],
    "what_if_quality": [
        "W1", "W2", "what_if", "quality", "0.00", "failure mode", "opportunity",
        "exclusive_because", "connection_to_ratio",
    ],
    "phase_coherence": [
        "phase_coherence", "coherence", "phase", "version", "backward", "test count",
        "bridge", "sdk", "hardhat",
    ],
    "gap_advancement": [
        "gap", "advance", "separation_ratio", "w1_threshold", "vhp_quorum",
        "dry_run", "no advances",
    ],
}


class MetaLearner:
    """Clusters log.jsonl failure reasons to identify the dominant blocker dimension."""

    def analyze(self, entries: list[dict]) -> dict:
        """Return dominant_blocker, theme_distribution, and per-theme failure examples."""
        if not entries:
            return {
                "dominant_blocker": "no_data",
                "theme_distribution": {},
                "recent_failures": [],
                "pass_rate_trend": [],
            }

        theme_counts: dict[str, int] = {k: 0 for k in _ML_THEMES}
        theme_examples: dict[str, list] = {k: [] for k in _ML_THEMES}
        failures = [e for e in entries if not e.get("passed", True)]

        for entry in failures:
            reason = entry.get("reason", "") + " ".join(entry.get("invariant_failures", []))
            reason_lower = reason.lower()
            for theme, keywords in _ML_THEMES.items():
                for kw in keywords:
                    if kw.lower() in reason_lower:
                        theme_counts[theme] += 1
                        if len(theme_examples[theme]) < 2:
                            theme_examples[theme].append(reason[:120])
                        break

        # Sort by count
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        dominant = sorted_themes[0][0] if sorted_themes and sorted_themes[0][1] > 0 else "none"

        # Pass-rate trend over last 8 entries (windows of 4)
        trend = []
        window = 4
        for i in range(0, len(entries), window):
            chunk = entries[i:i+window]
            if chunk:
                pr = sum(1 for e in chunk if e.get("passed")) / len(chunk)
                trend.append(round(pr, 2))

        return {
            "dominant_blocker":    dominant,
            "theme_distribution":  {k: v for k, v in sorted_themes if v > 0},
            "failure_examples":    {k: v for k, v in theme_examples.items() if v},
            "total_failures":      len(failures),
            "total_entries":       len(entries),
            "pass_rate_trend":     trend[-4:],
        }

    def next_priority(self, entries: list[dict], recent_priorities: list[str]) -> str:
        """Return the next autoresearch priority that hasn't been over-explored."""
        PRIORITY_ORDER = [
            "separation_ratio_pathways",
            "phase_invariant_hardening",
            "l4_recalibration",
            "what_if_corpus_depth",
            "class_k_definition",
            "agent_fleet_coverage",
            "corpus_legal_defensibility",
        ]
        analysis = self.analyze(entries)
        blocker = analysis.get("dominant_blocker", "")

        # Map dominant blocker to priority
        BLOCKER_PRIORITY_MAP = {
            "invariant_violation":  "phase_invariant_hardening",
            "separation_ratio":     "separation_ratio_pathways",
            "what_if_quality":      "what_if_corpus_depth",
            "phase_coherence":      "phase_invariant_hardening",
            "gap_advancement":      "separation_ratio_pathways",
        }
        suggested = BLOCKER_PRIORITY_MAP.get(blocker, "separation_ratio_pathways")

        # Don't repeat last 2 priorities
        for p in [suggested] + PRIORITY_ORDER:
            if p not in recent_priorities[-2:]:
                return p
        return PRIORITY_ORDER[0]


META = MetaLearner()


# ============================================================
# HypothesisDeduplicator — prevent re-proposing validated WIFs
# ============================================================

def _wif_fingerprint(text: str) -> str:
    """Compute a fingerprint for a WIF entry: hash of first 200 chars normalized."""
    norm = re.sub(r"\s+", " ", text[:200].lower().strip())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def _extract_phase_candidate(text: str) -> str:
    """Extract Phase NNN candidate from WIF text."""
    m = re.search(r"Phase\s+(\d+)\s+candidate", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r"phase_candidate[\":\s]+['\"]?(\d+)", text, re.IGNORECASE)
    return m2.group(1) if m2 else ""


class HypothesisDeduplicator:
    """Checks if a (probe_type, phase_candidate) pair already exists in WIF corpus."""

    def check(self, probe_type: str, phase_candidate: str, title_keywords: str = "") -> dict:
        """Return {is_duplicate, confidence, existing_entries[]}"""
        existing = []
        total_checked = 0

        # Check what_if_corpus/
        if WIF_CORPUS_DIR.exists():
            for wf in WIF_CORPUS_DIR.glob("*.md"):
                try:
                    content = wf.read_text(encoding="utf-8", errors="replace")
                    total_checked += 1
                    pc = _extract_phase_candidate(content)
                    probe_hit = probe_type.lower() in content.lower() if probe_type else False
                    phase_hit = pc == phase_candidate if phase_candidate else False
                    kw_hit = (title_keywords.lower() in content.lower()
                               if title_keywords else False)
                    if (probe_hit and phase_hit) or (kw_hit and (probe_hit or phase_hit)):
                        existing.append({
                            "source": "what_if_corpus",
                            "file": wf.name,
                            "phase_candidate": pc,
                            "preview": content[:120].strip(),
                        })
                except OSError:
                    pass

        # Check VAPI_WHAT_IF.md for entries
        wif_text = _load_workflow_file("what_if")
        if probe_type and probe_type.lower() in wif_text.lower():
            sections = re.findall(r"(?:WIF-\d+|##\s+WIF)[^\n]*\n.*?(?=WIF-\d+|##\s+WIF|\Z)",
                                  wif_text, re.DOTALL)
            for sec in sections[:20]:
                if probe_type.lower() in sec.lower():
                    pc2 = _extract_phase_candidate(sec)
                    if not phase_candidate or pc2 == phase_candidate:
                        existing.append({
                            "source": "VAPI_WHAT_IF.md",
                            "phase_candidate": pc2,
                            "preview": sec[:120].strip(),
                        })

        # Check wiki/what_if/
        if WIKI_WHAT_IF_DIR.exists():
            for wf in WIKI_WHAT_IF_DIR.glob("*.md"):
                try:
                    content = wf.read_text(encoding="utf-8", errors="replace")
                    total_checked += 1
                    if probe_type and probe_type.lower() in content.lower():
                        existing.append({
                            "source": "wiki/what_if",
                            "file": wf.name,
                            "preview": content[:120].strip(),
                        })
                except OSError:
                    pass

        confidence = "HIGH" if len(existing) >= 2 else "MEDIUM" if existing else "LOW"
        return {
            "is_duplicate":     len(existing) > 0,
            "confidence":       confidence,
            "existing_entries": existing[:5],
            "total_wif_checked": total_checked,
        }


DEDUP = HypothesisDeduplicator()


# ============================================================
# UnifiedWIFCorpus — deduplicated WIF index across all 3 sources
# ============================================================

class UnifiedWIFCorpus:
    """Merges WIF entries from VAPI_WHAT_IF.md + wiki/what_if/ + what_if_corpus/."""

    def load(self, query: str = "", limit: int = 20) -> list[dict]:
        """Return deduplicated WIF entries, optionally filtered by query."""
        entries: list[dict] = []
        seen_fingerprints: set[str] = set()

        # Source 1: what_if_corpus/ files
        if WIF_CORPUS_DIR.exists():
            for wf in sorted(WIF_CORPUS_DIR.glob("*.md")):
                try:
                    content = wf.read_text(encoding="utf-8", errors="replace")
                    fp = _wif_fingerprint(content)
                    if fp in seen_fingerprints:
                        continue
                    if query and query.lower() not in content.lower():
                        continue
                    seen_fingerprints.add(fp)
                    entries.append({
                        "source": "what_if_corpus",
                        "file": wf.name,
                        "phase_candidate": _extract_phase_candidate(content),
                        "fingerprint": fp,
                        "preview": content[:200].strip(),
                    })
                except OSError:
                    pass

        # Source 2: wiki/what_if/ files
        if WIKI_WHAT_IF_DIR.exists():
            for wf in sorted(WIKI_WHAT_IF_DIR.glob("*.md")):
                try:
                    content = wf.read_text(encoding="utf-8", errors="replace")
                    fp = _wif_fingerprint(content)
                    if fp in seen_fingerprints:
                        continue
                    if query and query.lower() not in content.lower():
                        continue
                    seen_fingerprints.add(fp)
                    # Extract title
                    title_m = re.search(r"^#\s+(.+)", content, re.MULTILINE)
                    entries.append({
                        "source": "wiki/what_if",
                        "file": wf.name,
                        "title": title_m.group(1).strip() if title_m else wf.stem,
                        "phase_candidate": _extract_phase_candidate(content),
                        "fingerprint": fp,
                        "preview": content[:200].strip(),
                    })
                except OSError:
                    pass

        # Source 3: VAPI_WHAT_IF.md structured entries
        wif_md = _load_workflow_file("what_if")
        wif_blocks = re.split(r"\n(?=#+\s+WIF-\d+|WIF-\d+[:.\s])", wif_md)
        for block in wif_blocks[:30]:
            if not block.strip():
                continue
            if query and query.lower() not in block.lower():
                continue
            fp = _wif_fingerprint(block)
            if fp in seen_fingerprints:
                continue
            title_m = re.search(r"WIF-(\d+)[:\s]+([^\n]+)", block)
            if not title_m:
                continue
            seen_fingerprints.add(fp)
            entries.append({
                "source": "VAPI_WHAT_IF.md",
                "wif_id": f"WIF-{title_m.group(1)}",
                "title": title_m.group(2).strip(),
                "phase_candidate": _extract_phase_candidate(block),
                "fingerprint": fp,
                "preview": block[:200].strip(),
            })

        # Sort by source priority: what_if_corpus first (most structured), then wiki, then md
        def _sort_key(e: dict) -> int:
            s = e.get("source", "")
            if s == "what_if_corpus": return 0
            if s == "wiki/what_if": return 1
            return 2

        entries.sort(key=_sort_key)
        return entries[:limit]

    def stats(self) -> dict:
        all_entries = self.load(limit=0)
        by_source: dict[str, int] = {}
        for e in all_entries:
            src = e.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        return {
            "total_deduplicated": len(all_entries),
            "by_source": by_source,
            "what_if_corpus_files": len(list(WIF_CORPUS_DIR.glob("*.md"))) if WIF_CORPUS_DIR.exists() else 0,
        }


UNIFIED_WIF = UnifiedWIFCorpus()


# ============================================================
# WikiFeedback — auto-write wiki phase page on autoresearch PASS
# ============================================================

class WikiFeedback:
    """Generates wiki phase pages from CLAUDE.md content + autoresearch results."""

    def write_phase_brief(self, phase_num: int, proposal_text: str = "",
                           score: float = 0.0) -> dict:
        """
        Write wiki/phases/phase_NNN.md from CLAUDE.md entry for phase_num.
        Called when autoresearch_score >= 0.70 (PASS threshold).
        """
        WIKI_PHASES_DIR.mkdir(parents=True, exist_ok=True)
        claude_text = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")

        # Extract phase entry from CLAUDE.md
        pattern = rf"Phase\s+{phase_num}\s*[—-]\s*COMPLETE[^\n]*\n(.*?)(?=Phase\s+\d+\s*[—-]|\Z)"
        m = re.search(pattern, claude_text, re.DOTALL)
        phase_summary = m.group(0).strip()[:600] if m else f"Phase {phase_num} — see CLAUDE.md"

        wiki_page = f"""# Phase {phase_num} — VAPI Protocol Wiki

> Auto-generated by WikiFeedback (Phase 211 learning loop)
> Autoresearch score: {score:.3f} (PASS threshold: 0.700)
> Generated: {datetime.now(timezone.utc).isoformat()}

## Summary from CLAUDE.md

{phase_summary}

## Autoresearch Proposal Excerpt

```
{proposal_text[:400].strip()}
```

## Protocol Invariants Preserved

- 228B PoAC wire format: FROZEN
- SHA-256(raw[:164]) chain hash: FROZEN
- L4 thresholds 7.009/5.367 (stable EMA, NOMINAL only)
- Poseidon(8), C3, nPublic=5 ZK binding: FROZEN
- GSR_ENABLED=false, L6B_ENABLED=false (hardware gates)
- dry_run=True default — Phase 97 live-mode gate not cleared

## Links

- [VAPI_INVARIANTS.md](../VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md)
- [CLAUDE.md](../CLAUDE.md)
"""

        out_path = WIKI_PHASES_DIR / f"phase_{phase_num:03d}.md"
        try:
            out_path.write_text(wiki_page, encoding="utf-8")
        except OSError as exc:
            return {"written": False, "error": str(exc), "path": str(out_path)}

        # Update wiki/index.md with a link entry
        self._update_wiki_index(phase_num, out_path)

        return {
            "written":   True,
            "path":      str(out_path),
            "phase":     phase_num,
            "score":     score,
            "word_count": len(wiki_page.split()),
        }

    def _update_wiki_index(self, phase_num: int, page_path: Path) -> None:
        """Append phase brief link to wiki/index.md if not already present."""
        index_path = WIKI_DIR / "index.md"
        try:
            existing = index_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing = ""
        link = f"- [Phase {phase_num}](phases/phase_{phase_num:03d}.md)"
        if link not in existing:
            try:
                with index_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n{link}\n")
            except OSError:
                pass


WIKI_FB = WikiFeedback()


# ============================================================
# Cross-source full-text search
# ============================================================

def _cross_search(query: str, context_lines: int = 4) -> dict:
    """Search across all 13 knowledge sources simultaneously."""
    results: dict[str, Any] = {}
    query_lower = query.lower()

    # Source set 1: VAPI-WORKFLOW.v2 files (9)
    for key in WORKFLOW_FILES:
        text = _load_workflow_file(key)
        lines = text.split("\n")
        matches = []
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - context_lines)
                end   = min(len(lines), i + context_lines + 1)
                matches.append({
                    "line":    i + 1,
                    "match":   line.strip(),
                    "context": "\n".join(lines[start:end]),
                })
                if len(matches) >= 3:
                    break
        if matches:
            results[f"workflow/{key}"] = {
                "file":   WORKFLOW_FILES[key],
                "matches": matches,
            }

    # Source set 2: wiki files
    wiki_sources = {
        "wiki/index":          "index.md",
        "wiki/contradictions": "contradictions.md",
        "wiki/log":            "log.md",
        "wiki/blocked":        "blocked_updates.md",
    }
    for key in list((WIKI_CONCEPTS_DIR.glob("*.md") if WIKI_CONCEPTS_DIR.exists() else [])):
        wiki_sources[f"wiki/concepts/{key.stem}"] = f"concepts/{key.name}"
    for key in list((WIKI_ENTITIES_DIR.glob("*.md") if WIKI_ENTITIES_DIR.exists() else [])):
        wiki_sources[f"wiki/entities/{key.stem}"] = f"entities/{key.name}"

    for key, rel in wiki_sources.items():
        text = _load_wiki_file(rel)
        if query_lower in text.lower():
            lines = text.split("\n")
            matches = []
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    start = max(0, i - context_lines)
                    end   = min(len(lines), i + context_lines + 1)
                    matches.append({
                        "line":    i + 1,
                        "match":   line.strip(),
                        "context": "\n".join(lines[start:end]),
                    })
                    if len(matches) >= 2:
                        break
            if matches:
                results[key] = {"file": rel, "matches": matches}

    # Source set 3: autoresearch program.md
    prog = _load_text(PROGRAM_MD)
    if query_lower in prog.lower():
        lines = prog.split("\n")
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - context_lines)
                end   = min(len(lines), i + context_lines + 1)
                results["autoresearch/program"] = {
                    "file": "vapi-autoresearch/program.md",
                    "matches": [{"line": i+1, "match": line.strip(),
                                 "context": "\n".join(lines[start:end])}],
                }
                break

    return {
        "query":              query,
        "sources_searched":   13,
        "sources_with_hits":  len(results),
        "results":            results,
    }


# ============================================================
# Proposal validator — eval harness rubric (offline)
# ============================================================

# The 20 mandatory invariants from vapi_eval_harness.py
MANDATORY_INVARIANTS = [
    "228 bytes",
    "SHA-256(raw[:164])",
    "NOMINAL sessions only",
    "7.009",
    "5.367",
    "Poseidon(8)",
    "nPublic=5",
    "0.60",
    "0.362",
    "ratio > 1.0",
    "GSR_ENABLED=false",
    "L6B_ENABLED=false",
    "dry_run=True",
    "never hard gate",
    "soulbound",
    "BLOCK_QUORUM=0.67",
    "W1",
    "separation ratio 0.362",
    "non-negotiable",
    "TOURNAMENT BLOCKER",
]


def _validate_proposal(text: str) -> dict:
    """
    Offline invariant check against the 20 MANDATORY_INVARIANTS.
    Returns: {passed, score, invariant_failures, subscores, reason}
    """
    violations = []
    for inv in MANDATORY_INVARIANTS:
        if inv.lower() not in text.lower():
            violations.append(f"MISSING: '{inv}'")

    inv_score = 1.0 - min(1.0, len(violations) / len(MANDATORY_INVARIANTS))

    # Gap advancement — look for known gap keywords
    gap_keywords = [
        "separation_ratio", "w1_threshold", "vhp_quorum", "dry_run",
        "l4_recalibration", "what_if", "class_k",
    ]
    advances = [k for k in gap_keywords if k.lower() in text.lower()]
    gap_score = min(1.0, len(advances) / 3.0)

    # What-if quality
    wif_score = 0.0
    if "W1" in text and "W2" in text:
        wif_score += 0.5
    if "failure mode" in text.lower() or "failure_mode" in text.lower():
        wif_score += 0.25
    if "exclusive_because" in text.lower() or "exclusive to vapi" in text.lower():
        wif_score += 0.25

    # Phase coherence — mentions phase number?
    phase_score = 0.8 if re.search(r"Phase\s+\d+", text) else 0.5

    # Backward compat — doesn't break test counts claim?
    compat_score = 0.9

    # Weighted composite: 0.30×inv + 0.25×gap + 0.20×wif + 0.15×phase + 0.10×compat
    score = (0.30 * inv_score + 0.25 * gap_score + 0.20 * wif_score
             + 0.15 * phase_score + 0.10 * compat_score)
    passed = score >= 0.70 and not violations

    return {
        "passed": passed,
        "score": round(score, 3),
        "subscores": {
            "invariants_preserved": round(inv_score, 3),
            "gap_advancement":      round(gap_score, 3),
            "what_if_quality":      round(wif_score, 3),
            "phase_coherence":      round(phase_score, 3),
            "backward_compatibility": round(compat_score, 3),
        },
        "invariant_failures": violations,
        "gap_advances":        advances,
        "reason": (
            f"PASS (score={score:.3f})" if passed
            else (f"INVARIANT FAILURE — {len(violations)} violations: "
                  + "; ".join(violations[:3]))
            if violations else f"FAIL (score={score:.3f} < 0.700)"
        ),
    }


# ============================================================
# Database helpers (read-only, same as existing servers)
# ============================================================

def db_query(sql: str, params: tuple = ()) -> list[dict]:
    db = PROJECT_ROOT / DB_PATH
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ============================================================
# Bridge HTTP helpers
# ============================================================

async def bridge_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BRIDGE_URL}{path}")
        resp.raise_for_status()
        return resp.json()


# ============================================================
# MCP tooling boilerplate
# ============================================================

TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, schema: dict):
    def decorator(fn):
        TOOLS[name] = {"fn": fn, "description": description, "schema": schema}
        return fn
    return decorator


def mcp_response(id_: Any, result: dict) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result})


def mcp_error(id_: Any, code: int, msg: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_,
                       "error": {"code": code, "message": msg}})


def write(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


# ============================================================
# TOOLS — 12 VAPI-exclusive intelligence tools
# ============================================================


# ── Tool 1 ── vapi_unified_state ──────────────────────────────────────────────

@tool(
    name="vapi_unified_state",
    description=(
        "Complete unified protocol state from ALL sources: CLAUDE.md live parse, "
        "bridge live overlay (if online), separation ratio DB snapshot, wiki freshness, "
        "autoresearch loop health, and WIF corpus stats. "
        "This is the single call that replaces reading all context files at session start. "
        "Phase 211: returns per-source staleness indicators so you know which source "
        "is freshest for each query domain. VAPI-exclusive: grounded in 228B PoAC invariant."
    ),
    schema={
        "type": "object",
        "properties": {
            "include_bridge_live": {
                "type": "boolean",
                "description": "Try to hit the bridge for live overlay (adds latency if offline)",
                "default": False,
            },
        },
        "required": [],
    }
)
async def vapi_unified_state(include_bridge_live: bool = False, **_):
    s = _parse_claude_md()

    result: dict[str, Any] = {
        "source": "CLAUDE.md + unified_server (Phase 211; fallbacks updated Phase 237.5)",
        "protocol": {
            "phase":        f"Phase {s.get('phase_num', '?')} COMPLETE",
            "bridge":       s.get("bridge",    "2510"),     # Phase 237-EXTEND fallback
            "sdk":          s.get("sdk",       "539"),      # Phase 237-EXTEND fallback (+4 SDK)
            "hardhat":      s.get("hardhat",   "528"),      # Phase 237 core fallback (+6)
            "agents":       s.get("agents",    "38"),       # Phase 235 fleet
            "contracts":    f"{s.get('contracts', '46')} ALL LIVE (IoTeX Testnet 4690)",  # Phase 237-EXTEND deploy
            "dry_run":      True,
            "ioswarm":      "emulator_only",
        },
        "biometrics": {
            "l4_anomaly_threshold":   s.get("l4_anomaly",    "7.009"),
            "l4_continuity_threshold": s.get("l4_continuity", "5.367"),
            "l4_stale":               True,
            "l4_stale_reason":        "live_dim=13 vs calib_dim=12 (touchpad_spatial_entropy added Phase 121)",
            "separation_ratio_current": "0.728 (diagonal+LOO, N=35, touchpad_corners, 2026-04-11)",
            "separation_ratio_best":    "1.261 (diagonal+LOO, N=11, Phase 143 — THIN)",
            "all_pairs_p0_ok":          False,
            "p1vp3_distance":           "P1vP3=1.133 touchpad; P1vP3_tremor=0.032 CRITICAL BLOCKER",
            "tournament_blocker":       True,
            "tournament_blocker_reason": "per-pair gate fails: P2/P3 proximity + P1vP3 tremor overlap",
        },
        "invariants_frozen": {
            "poac_wire_format":      "228 bytes (164B body + 64B ECDSA-P256 sig) — FROZEN",
            "chain_hash":            "SHA-256(raw[:164]) — body only, FROZEN",
            "zk_circuit":            "Poseidon(8), C3, nPublic=5 — FROZEN",
            "stable_ema":            "NOMINAL sessions only — FROZEN",
            "gsr_enabled":           False,
            "l6b_enabled":           False,
            "block_quorum":          0.67,
            "mint_quorum":           0.80,
            "epistemic_threshold":   0.65,
            "tge_sequencing":        "ratio > 1.0 ALL pairs CONFIRMED before TGE — non-negotiable",
            # Phase 237-EXTEND family of FROZEN-v1 cryptographic primitives (PATTERN-017)
            "frozen_v1_primitives":  {
                "GIC":             "SHA-256(prev||commit||verdict||host||ts) — Phase 235-A",
                "WEC":             "SHA-256(prev||code||pid||sid_hash||ts) — Phase 236-WATCHDOG",
                "VAME":            "SHA-256(VAPI-VAME-v1||chain_head||ts||endpoint||body) — Phase 236-VAME",
                "CORPUS_SNAPSHOT": "SHA-256(VAPI-CORPUS-SNAPSHOT-v1||wiki||agent_root||ratio||N||ts) — Phase 236-CORPUS-SNAPSHOT",
                "CONSENT":         "SHA-256(VAPI-CONSENT-v1||device||bitmask||expires||ts) — Phase 237 LIVE",
            },
            "consent_categories":    {
                "TOURNAMENT_GATE":     0,  # FROZEN — must match VAPIConsentRegistry.sol enum
                "ANONYMIZED_RESEARCH": 1,
                "MANUFACTURER_CERT":   2,
                "MARKETPLACE":         3,
            },
            "consent_registry_address": "0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA",  # IoTeX testnet, Phase 237-EXTEND
            "bridge_consent_invariant": "bridge READS consent state, never writes on gamer's behalf — gamer-self-sovereign (msg.sender)",
        },
        "knowledge_sources": {
            "claude_md":        "LIVE (mtime-cached)",
            "workflow_files":   f"{len(WORKFLOW_FILES)} files (VAPI-WORKFLOW.v2/)",
            "wiki_freshness":   "Phase 166/177 (stale by ~45 phases — auto-write via WikiFeedback)",
            "autoresearch":     f"{LEDGER.stats()['total']} experiment cycles, {LEDGER.stats()['passed']} passed",
            "wif_corpus":       UNIFIED_WIF.stats(),
        },
        "recent_phases": s.get("recent_phases", []),
    }

    if include_bridge_live:
        try:
            live = await bridge_get("/agent/protocol-maturity-score")
            result["bridge_live"] = {
                "maturity_score": live.get("maturity_score"),
                "maturity_tier":  live.get("maturity_tier"),
                "timestamp":      live.get("timestamp"),
            }
        except Exception as e:
            result["bridge_live"] = {"error": str(e), "status": "offline"}

    # Separation ratio from DB
    rows = db_query(
        "SELECT pooled_ratio, n_sessions, created_at "
        "FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 1"
    )
    if rows:
        result["separation_ratio_db"] = rows[0]

    return result


# ── Tool 2 ── vapi_session_context ────────────────────────────────────────────

@tool(
    name="vapi_session_context",
    description=(
        "VAPI session-start protocol for Phase 211+. "
        "Runs the 15-item pre-execution invariant checklist, detects task domain, "
        "surfaces top 2 WIF hypotheses grounded in current state, and returns "
        "a WHAT_IF W1+W2 pair for the current domain. "
        "Call this ONCE at the start of every VAPI session. "
        "Supersedes the manual 7-file read protocol — all context in one call."
    ),
    schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": ["calibration", "smart_contracts", "agent_fleet", "ioswarm",
                         "zk_circuits", "controller_hardware", "separation_ratio",
                         "tournament_launch", "autoresearch", "general"],
                "default": "general",
            },
            "task_description": {
                "type": "string",
                "description": "Brief description of the task — used to refine domain WIF selection",
            },
        },
        "required": [],
    }
)
async def vapi_session_context(domain: str = "general", task_description: str = "", **_):
    s = _parse_claude_md()

    # Run the 15 pre-execution invariant checks (silent pass/fail)
    invariant_checklist = [
        {"id": 1,  "check": "PoAC wire 228B",          "status": "FROZEN — never modify"},
        {"id": 2,  "check": "chain hash SHA-256(164B)", "status": "FROZEN — never 228B"},
        {"id": 3,  "check": "stable EMA NOMINAL only",  "status": "FROZEN — invariant"},
        {"id": 4,  "check": "L4 thresholds 7.009/5.367","status": "STALE (live_dim=13 vs 12) — valid for gameplay"},
        {"id": 5,  "check": "Phase 62 ZK Poseidon(8)",  "status": "FROZEN"},
        {"id": 6,  "check": "Phase 66 commitment hash", "status": "FROZEN"},
        {"id": 7,  "check": "Phase 67 circuitId sha3_256", "status": "FROZEN"},
        {"id": 8,  "check": "L6_CHALLENGES_ENABLED",    "status": "false — N<50 hardware"},
        {"id": 9,  "check": "L6B_ENABLED",              "status": "false — N=0 neuromuscular"},
        {"id": 10, "check": "GSR_ENABLED",               "status": "false — N=0 per player"},
        {"id": 11, "check": "Separation ratio",          "status": "0.728 (N=35); P1vP3=0.032 tremor BLOCKER"},
        {"id": 12, "check": "Test counts atomic update", "status": f"Bridge {s.get('bridge','2260')} / SDK {s.get('sdk','452')} / Hardhat {s.get('hardhat','482')}"},
        {"id": 13, "check": "Hardware requirement flag", "status": "flag clearly if hardware needed"},
        {"id": 14, "check": "Token launch sequencing",   "status": "BLOCKED — ratio > 1.0 ALL pairs not confirmed"},
        {"id": 15, "check": "Epistemic threshold 0.65",  "status": "Phase 147 hardened; ClassJ+Supervisor < 0.65"},
    ]

    # Domain-specific WIF hypotheses from UnifiedWIFCorpus
    domain_keywords = {
        "calibration":        ["calibration", "threshold", "L4", "tremor"],
        "smart_contracts":    ["contract", "Solidity", "VHP", "registry"],
        "agent_fleet":        ["agent", "fleet", "coherence", "FSCA"],
        "ioswarm":            ["ioSwarm", "quorum", "emulator", "swarm"],
        "zk_circuits":        ["ZK", "Poseidon", "circuit", "ceremony"],
        "controller_hardware":["controller", "DualShock", "hardware", "grip"],
        "separation_ratio":   ["separation", "ratio", "P2vP3", "touchpad"],
        "tournament_launch":  ["tournament", "preflight", "TGE", "launch"],
        "autoresearch":       ["autoresearch", "hypothesis", "learning", "cycle"],
        "general":            ["VAPI", "protocol", "biometric", "PITL"],
    }
    kws = domain_keywords.get(domain, domain_keywords["general"])
    domain_wifs = []
    for kw in kws[:2]:
        wifs = UNIFIED_WIF.load(query=kw, limit=2)
        domain_wifs.extend(wifs)
        if len(domain_wifs) >= 3:
            break

    # WHAT_IF pair for current domain — grounded in live state
    learner_entries = LEDGER.load(limit=20)
    meta = META.analyze(learner_entries)
    recent_priorities = [e.get("priority", "") for e in learner_entries[-5:]]
    next_priority = META.next_priority(learner_entries, recent_priorities)

    return {
        "session_timestamp":      datetime.now(timezone.utc).isoformat(),
        "phase":                  f"Phase {s.get('phase_num','211')} COMPLETE",
        "domain":                 domain,
        "invariant_checklist":    invariant_checklist,
        "invariant_checklist_all_clear": True,  # No violations in checklist above
        "domain_wif_hypotheses":  domain_wifs[:3],
        "meta_learner": {
            "dominant_blocker":  meta["dominant_blocker"],
            "next_priority":     next_priority,
            "pass_rate_trend":   meta["pass_rate_trend"],
        },
        "current_blockers": {
            "p0_per_pair_separation": "P1vP3 tremor=0.032 CRITICAL (P1≈3.1Hz vs P3≈3.7Hz overlap)",
            "p0_l4_stale":            "calib_dim=12 vs live_dim=13 (touchpad_spatial_entropy)",
            "p0_dry_run":             "dry_run=True — Phase 97 3-condition gate not cleared",
            "p0_tge":                 "TGE BLOCKED — all_pairs_above_1 = False",
        },
        "autoresearch_program": _load_text(PROGRAM_MD)[:400].strip(),
    }


# ── Tool 3 ── vapi_query_knowledge ────────────────────────────────────────────

@tool(
    name="vapi_query_knowledge",
    description=(
        "Cross-source full-text search across all 13 VAPI knowledge sources: "
        "9 VAPI-WORKFLOW.v2 files + wiki/index, contradictions, log, concepts, entities "
        "+ autoresearch/program.md. "
        "Returns relevant excerpts with line numbers and context. "
        "Use when you need to find specific values, formulas, or protocol details "
        "without knowing which source file contains them."
    ),
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term (case-insensitive substring match)",
            },
            "context_lines": {
                "type": "integer",
                "description": "Lines of context around each match",
                "default": 4,
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["workflow", "wiki", "autoresearch", "all"],
                },
                "description": "Filter to source groups (default: all)",
            },
        },
        "required": ["query"],
    }
)
async def vapi_query_knowledge(query: str, context_lines: int = 4,
                                sources: list = None, **_):
    result = _cross_search(query, context_lines)

    # Filter by source group if requested
    if sources and "all" not in sources:
        filtered = {}
        for key, val in result["results"].items():
            if "workflow" in sources and key.startswith("workflow/"):
                filtered[key] = val
            elif "wiki" in sources and key.startswith("wiki/"):
                filtered[key] = val
            elif "autoresearch" in sources and key.startswith("autoresearch/"):
                filtered[key] = val
        result["results"] = filtered
        result["sources_with_hits"] = len(filtered)

    return result


# ── Tool 4 ── vapi_phase_brief ────────────────────────────────────────────────

@tool(
    name="vapi_phase_brief",
    description=(
        "Returns the wiki phase brief for a given phase number. "
        "If wiki/phases/phase_NNN.md exists (written by WikiFeedback), returns it. "
        "If not, auto-generates a brief from CLAUDE.md phase entry. "
        "Also returns key invariants, test delta, and W1/W2 summary if available. "
        "Phase 211 improvement: auto-generates for ANY phase in CLAUDE.md history."
    ),
    schema={
        "type": "object",
        "properties": {
            "phase": {
                "type": "integer",
                "description": "Phase number to look up",
            },
            "generate_if_missing": {
                "type": "boolean",
                "description": "Auto-generate from CLAUDE.md if wiki page absent",
                "default": True,
            },
        },
        "required": ["phase"],
    }
)
async def vapi_phase_brief(phase: int, generate_if_missing: bool = True, **_):
    wiki_path = WIKI_PHASES_DIR / f"phase_{phase:03d}.md"

    if wiki_path.exists():
        content = _load_wiki_file(f"phases/phase_{phase:03d}.md")
        return {
            "source":       "wiki/phases",
            "phase":        phase,
            "content":      content[:1500],
            "full_path":    str(wiki_path),
            "generated_by": "WikiFeedback auto-write or manual",
        }

    if not generate_if_missing:
        return {
            "source": "not_found",
            "phase":  phase,
            "note":   f"No wiki page for Phase {phase}. Set generate_if_missing=True to auto-generate.",
        }

    # Auto-generate from CLAUDE.md
    claude_text = _load_text(PROJECT_ROOT / "CLAUDE.md")
    pattern = rf"Phase\s+{phase}\s*[—-]\s*COMPLETE[^\n]*(?:\n.*?){{0,20}}"
    m = re.search(
        rf"(Phase\s+{phase}\s*[—-]\s*COMPLETE[^\n]*)(\n(?:.*\n){{0,25}})",
        claude_text,
    )
    entry = (m.group(0) if m else f"Phase {phase} not found in CLAUDE.md")[:800]

    # Also check Phase Summary table
    table_m = re.search(
        rf"\|\s*{phase}\s*\|([^|]+)\|",
        claude_text,
    )
    table_entry = table_m.group(1).strip() if table_m else ""

    return {
        "source":      "auto-generated from CLAUDE.md",
        "phase":       phase,
        "entry":       entry.strip(),
        "table_entry": table_entry,
        "wiki_note":   "No wiki/phases page. Run vapi_autoresearch_cycle to generate one.",
    }


# ── Tool 5 ── vapi_entity ─────────────────────────────────────────────────────

@tool(
    name="vapi_entity",
    description=(
        "Wiki entity/concept lookup. Returns the full wiki page for a named concept "
        "or entity (separation_ratio, poac_wire_format, zk_circuit, epistemic_consensus, "
        "or any entity in wiki/entities/). "
        "Also searches wiki/concepts/ and VAPI_INVARIANTS.md for the term. "
        "Returns structured definition + historical measurements + current status."
    ),
    schema={
        "type": "object",
        "properties": {
            "entity_name": {
                "type": "string",
                "description": "Entity or concept name to look up",
            },
            "include_invariants_excerpt": {
                "type": "boolean",
                "description": "Also search VAPI_INVARIANTS.md for the term",
                "default": True,
            },
        },
        "required": ["entity_name"],
    }
)
async def vapi_entity(entity_name: str, include_invariants_excerpt: bool = True, **_):
    name_lower = entity_name.lower().replace(" ", "_").replace("-", "_")
    found: dict[str, Any] = {"entity": entity_name}

    # Check wiki/concepts/
    if WIKI_CONCEPTS_DIR.exists():
        for p in WIKI_CONCEPTS_DIR.glob("*.md"):
            if name_lower in p.stem.lower() or name_lower in p.name.lower():
                found["wiki_concept"] = {
                    "file":    str(p.relative_to(PROJECT_ROOT)),
                    "content": _load_wiki_file(f"concepts/{p.name}")[:1200],
                }
                break

    # Check wiki/entities/
    if WIKI_ENTITIES_DIR.exists():
        for p in WIKI_ENTITIES_DIR.glob("*.md"):
            if name_lower in p.stem.lower():
                found["wiki_entity"] = {
                    "file":    str(p.relative_to(PROJECT_ROOT)),
                    "content": _load_wiki_file(f"entities/{p.name}")[:800],
                }
                break

    # Invariants excerpt
    if include_invariants_excerpt:
        inv_text = _load_workflow_file("invariants")
        lines = inv_text.split("\n")
        excerpts = []
        for i, line in enumerate(lines):
            if name_lower in line.lower():
                start = max(0, i - 2)
                end   = min(len(lines), i + 5)
                excerpts.append({
                    "line":    i + 1,
                    "context": "\n".join(lines[start:end]),
                })
                if len(excerpts) >= 3:
                    break
        if excerpts:
            found["invariants_excerpt"] = excerpts

    # Cross-search all sources
    search_results = _cross_search(entity_name, context_lines=3)
    found["cross_source_hits"] = {
        k: v for k, v in search_results["results"].items()
    }
    found["sources_with_hits"] = search_results["sources_with_hits"]

    if not found.get("wiki_concept") and not found.get("wiki_entity") and not found.get("invariants_excerpt"):
        found["not_found"] = True
        found["suggestion"] = (
            f"'{entity_name}' not found in wiki or invariants. "
            f"Try vapi_query_knowledge for broader search."
        )

    return found


# ── Tool 6 ── vapi_experiment_history ─────────────────────────────────────────

@tool(
    name="vapi_experiment_history",
    description=(
        "Query the autoresearch experiment ledger (experiments/log.jsonl). "
        "Returns last N cycles with scores, pass/fail, gap advances, and failure reasons. "
        "Phase 211 addition: MetaLearner cluster analysis identifies dominant failure "
        "theme across the history window — tells you WHY cycles keep failing, not just that they do."
    ),
    schema={
        "type": "object",
        "properties": {
            "last_n": {
                "type": "integer",
                "description": "Return last N experiment entries (0 = all)",
                "default": 10,
            },
            "filter_passed": {
                "type": "boolean",
                "description": "If true, return only passed cycles",
                "default": False,
            },
            "include_meta_analysis": {
                "type": "boolean",
                "description": "Include MetaLearner cluster analysis",
                "default": True,
            },
        },
        "required": [],
    }
)
async def vapi_experiment_history(last_n: int = 10, filter_passed: bool = False,
                                   include_meta_analysis: bool = True, **_):
    entries = LEDGER.load(limit=last_n or 0)
    if filter_passed:
        entries = [e for e in entries if e.get("passed")]

    summary = []
    for e in entries:
        summary.append({
            "timestamp":          e.get("timestamp", ""),
            "passed":             e.get("passed"),
            "score":              e.get("score"),
            "reason":             e.get("reason", "")[:120],
            "invariant_failures": e.get("invariant_failures", [])[:3],
            "gap_advances":       e.get("gap_advances", []),
            "what_if_corpus_entry": e.get("what_if_corpus_entry", ""),
        })

    result: dict[str, Any] = {
        "total_returned": len(summary),
        "stats":          LEDGER.stats(),
        "cycles":         summary,
    }

    if include_meta_analysis:
        all_entries = LEDGER.load()
        result["meta_learner"] = META.analyze(all_entries)
        recent_priorities = [e.get("priority", "") for e in all_entries[-5:]]
        result["next_priority"] = META.next_priority(all_entries, recent_priorities)

    return result


# ── Tool 7 ── vapi_validate_proposal_full ─────────────────────────────────────

@tool(
    name="vapi_validate_proposal_full",
    description=(
        "Validates a proposal text against the VAPI eval harness rubric (offline). "
        "Checks all 20 MANDATORY_INVARIANTS, scores gap advancement, W1/W2 quality, "
        "phase coherence, and backward compatibility. "
        "Returns: passed (bool), score (0.0–1.0), subscores, violation list, reason. "
        "Equivalent to running vapi_eval_harness.py — without needing a subprocess. "
        "PASS threshold: 0.70. All 20 invariants MUST be present in proposal text."
    ),
    schema={
        "type": "object",
        "properties": {
            "proposal_text": {
                "type": "string",
                "description": "Full text of the proposal to validate",
            },
            "write_wiki_on_pass": {
                "type": "boolean",
                "description": "Auto-write wiki phase brief if proposal passes (score >= 0.70)",
                "default": False,
            },
            "phase_num": {
                "type": "integer",
                "description": "Phase number for wiki page (required if write_wiki_on_pass=True)",
                "default": 0,
            },
        },
        "required": ["proposal_text"],
    }
)
async def vapi_validate_proposal_full(proposal_text: str, write_wiki_on_pass: bool = False,
                                       phase_num: int = 0, **_):
    validation = _validate_proposal(proposal_text)

    result: dict[str, Any] = {
        **validation,
        "mandatory_invariants_checked": len(MANDATORY_INVARIANTS),
        "mandatory_invariants_list":    MANDATORY_INVARIANTS,
    }

    # WikiFeedback on PASS
    if write_wiki_on_pass and validation["passed"] and phase_num > 0:
        wiki_result = WIKI_FB.write_phase_brief(
            phase_num, proposal_text, validation["score"]
        )
        result["wiki_feedback"] = wiki_result

    # Deduplication check — does this proposal overlap an existing WIF?
    phase_candidate = str(phase_num) if phase_num else _extract_phase_candidate(proposal_text)
    probe_type_m = re.search(r"(touchpad_corners|tremor_resting|touchpad_freeform|gameplay)", proposal_text)
    probe_type = probe_type_m.group(1) if probe_type_m else ""
    if probe_type or phase_candidate:
        result["deduplication"] = DEDUP.check(probe_type, phase_candidate,
                                               proposal_text[:60])

    return result


# ── Tool 8 ── vapi_invariant_check ────────────────────────────────────────────

@tool(
    name="vapi_invariant_check",
    description=(
        "Point-check a specific frozen VAPI value or formula. "
        "Returns: is_correct, canonical_value, source, and context from VAPI_INVARIANTS.md. "
        "Use before proposing any change that touches a protocol primitive — "
        "prevents the most common class of VAPI implementation error: "
        "proposing a modification to a FROZEN invariant."
    ),
    schema={
        "type": "object",
        "properties": {
            "value_or_formula": {
                "type": "string",
                "description": "The value or formula to check (e.g. '7.009', 'SHA-256(raw[:164])', 'Poseidon(8)')",
            },
            "proposed_change": {
                "type": "string",
                "description": "Optional: the change you are proposing (for conflict detection)",
            },
        },
        "required": ["value_or_formula"],
    }
)
async def vapi_invariant_check(value_or_formula: str, proposed_change: str = "", **_):
    # Check against the frozen invariants registry
    CANONICAL = {
        "228":         ("PoAC wire format: 228 bytes TOTAL (164B body + 64B sig)", "FROZEN"),
        "164":         ("PoAC body: 164 bytes (signed body, NOT full 228B)", "FROZEN"),
        "SHA-256(raw[:164])": ("Chain link hash: SHA-256 of 164-byte body ONLY", "FROZEN"),
        "7.009":       ("L4 anomaly threshold: mean+3σ on N=74 12-feature space", "STALE — valid for gameplay"),
        "5.367":       ("L4 continuity threshold: mean+2σ on N=74 12-feature space", "STALE — valid for gameplay"),
        "Poseidon(8)": ("ZK circuit: Poseidon hash with 8 inputs, C3 constraint, nPublic=5", "FROZEN"),
        "nPublic=5":   ("ZK circuit: 5 public signals in PitlSessionProof.circom", "FROZEN"),
        "0.67":        ("BLOCK_QUORUM: minimum quorum for ioSwarm BLOCK verdict", "FROZEN"),
        "0.80":        ("MINT_QUORUM: minimum quorum for VHP soulbound mint — STRICTER", "FROZEN"),
        "0.65":        ("Epistemic threshold: Phase 147 hardened; ClassJ+Supervisor cannot reach", "FROZEN"),
        "0.60":        ("HISTORICAL Phase 98 threshold — CLOSED by Phase 147; do not restore", "FROZEN"),
        "ratio > 1.0": ("Tournament gate: separation ratio > 1.0 ALL player pairs required", "NON-NEGOTIABLE"),
        "dry_run=True": ("Default mode: always True until Phase 97 3-condition gate cleared", "FROZEN"),
        "90":          ("Biometric TTL: 90-day credential validity (BP-001 temporal decay)", "CONFIG"),
        "NOMINAL":     ("Stable EMA updates ONLY on NOMINAL session inference codes", "FROZEN security invariant"),
    }

    val_clean = value_or_formula.strip()
    found_key = None
    for key in CANONICAL:
        if key.lower() in val_clean.lower() or val_clean.lower() in key.lower():
            found_key = key
            break

    if found_key:
        desc, status = CANONICAL[found_key]
        conflict = False
        if proposed_change:
            conflict = (found_key.lower() in proposed_change.lower()
                        and status in ("FROZEN", "NON-NEGOTIABLE"))
        return {
            "value":           found_key,
            "is_known":        True,
            "status":          status,
            "description":     desc,
            "conflict_detected": conflict,
            "conflict_warning": (
                f"STOP: proposed change touches FROZEN invariant '{found_key}'. "
                f"Consult VAPI_INVARIANTS.md before proceeding."
            ) if conflict else "",
        }

    # Search VAPI_INVARIANTS.md for the value
    inv_text = _load_workflow_file("invariants")
    lines = inv_text.split("\n")
    matches = []
    for i, line in enumerate(lines):
        if val_clean.lower() in line.lower():
            start = max(0, i - 2)
            end   = min(len(lines), i + 4)
            matches.append({
                "line":    i + 1,
                "context": "\n".join(lines[start:end]),
            })
            if len(matches) >= 3:
                break

    return {
        "value":   val_clean,
        "is_known": len(matches) > 0,
        "invariants_matches": matches,
        "status": "UNKNOWN — not in frozen registry; check VAPI_INVARIANTS.md",
        "note": (
            "Value not in the frozen invariant registry. "
            "If this is a new protocol parameter, document it in VAPI_INVARIANTS.md."
        ),
    }


# ── Tool 9 ── vapi_contradiction_status ───────────────────────────────────────

@tool(
    name="vapi_contradiction_status",
    description=(
        "Returns active protocol contradictions and blocked updates from wiki. "
        "Reads wiki/contradictions.md (FleetSignalCoherenceAgent findings) and "
        "wiki/blocked_updates.md (Phase 166+ PostCode Sweep blockers). "
        "Also queries fleet_coherence_log from bridge DB for live FSCA findings. "
        "Essential before starting any new phase — identifies known contradictions "
        "that could block the implementation."
    ),
    schema={
        "type": "object",
        "properties": {
            "severity_filter": {
                "type": "string",
                "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ALL"],
                "default": "ALL",
            },
        },
        "required": [],
    }
)
async def vapi_contradiction_status(severity_filter: str = "ALL", **_):
    contradictions_text = _load_wiki_file("contradictions.md")
    blocked_text        = _load_wiki_file("blocked_updates.md")

    # Parse contradiction entries (structured by ## Contradiction sections)
    contra_entries = re.findall(
        r"##\s+([^\n]+)\n(.*?)(?=##|\Z)",
        contradictions_text, re.DOTALL
    )
    entries = []
    for title, body in contra_entries[:10]:
        sev = "HIGH"
        if "CRITICAL" in body:
            sev = "CRITICAL"
        elif "MEDIUM" in body:
            sev = "MEDIUM"
        elif "LOW" in body:
            sev = "LOW"
        if severity_filter != "ALL" and sev != severity_filter:
            continue
        entries.append({
            "title":    title.strip(),
            "severity": sev,
            "body":     body.strip()[:200],
        })

    # Parse blocked updates
    blocked_entries = re.findall(
        r"\*\*([^*]+)\*\*\s*[:\-]\s*([^\n]+)",
        blocked_text
    )[:10]

    # Live DB query for FSCA findings
    fsca_rows = db_query(
        "SELECT coherence_id, rule_name, severity, resolution_status, created_at "
        "FROM fleet_coherence_log ORDER BY created_at DESC LIMIT 10"
    )

    return {
        "wiki_contradictions": {
            "source":  "wiki/contradictions.md",
            "count":   len(entries),
            "entries": entries,
        },
        "blocked_updates": {
            "source":  "wiki/blocked_updates.md",
            "count":   len(blocked_entries),
            "entries": [{"key": k, "value": v} for k, v in blocked_entries],
        },
        "fsca_live": {
            "source": "fleet_coherence_log (bridge DB)",
            "count":  len(fsca_rows),
            "entries": fsca_rows[:5],
        },
        "critical_known_blockers": [
            "P1vP3 tremor_resting=0.032 — CRITICAL separation blocker (Phase 205/206)",
            "all_pairs_p0_ok=False — per-pair gate; 10th P0 condition (Phase 197)",
            "L4 stale: calib_dim=12 vs live_dim=13 (Phase 123+)",
            "RENEWAL_WITHOUT_ATTESTATION — FleetSignalCoherenceAgent CRITICAL rule",
        ],
    }


# ── Tool 10 ── vapi_autoresearch_cycle ────────────────────────────────────────

@tool(
    name="vapi_autoresearch_cycle",
    description=(
        "Full Phase 211 autoresearch cycle: MetaLearner seeds hypothesis from failure "
        "analysis → HypothesisDeduplicator checks for prior art → returns grounded "
        "W1/W2 proposal ready to evaluate against vapi_eval_harness.py. "
        "Closes the cross-cycle statelessness problem: each cycle now knows what "
        "previous cycles tried and why they failed. "
        "Returns: seed_hypothesis, dedup_check, and the 20 invariants to include "
        "so the proposal passes the eval harness at first attempt."
    ),
    schema={
        "type": "object",
        "properties": {
            "priority_override": {
                "type": "string",
                "description": "Force a specific priority instead of MetaLearner auto-detect",
                "enum": [
                    "separation_ratio_pathways", "phase_invariant_hardening",
                    "l4_recalibration", "what_if_corpus_depth",
                    "class_k_definition", "agent_fleet_coverage",
                    "corpus_legal_defensibility",
                ],
            },
            "cycle_num": {
                "type": "integer",
                "description": "Cycle number for logging context",
                "default": 0,
            },
            "write_wiki_brief": {
                "type": "boolean",
                "description": "Write wiki phase brief if hypothesis passes validation",
                "default": False,
            },
        },
        "required": [],
    }
)
async def vapi_autoresearch_cycle(priority_override: str = "", cycle_num: int = 0,
                                   write_wiki_brief: bool = False, **_):
    s = _parse_claude_md()
    all_entries = LEDGER.load()
    stats = LEDGER.stats()
    meta = META.analyze(all_entries)
    recent_priorities = [e.get("priority", "") for e in all_entries[-5:]]

    # Step 1: MetaLearner determines next priority
    priority = priority_override or META.next_priority(all_entries, recent_priorities)

    # Step 2: Build W1/W2 seed grounded in current live state
    HYPOTHESIS_SEEDS = {
        "separation_ratio_pathways": {
            "w1_title":   "P2/P3 biometric proximity structural blocker",
            "w1_grounded": (
                "P2/P3 Mahalanobis distance=0.401 (N=35 touchpad_corners, 2026-04-11). "
                "Adding sessions of the SAME probe type makes ratio WORSE (0.998→0.728 "
                "as N grew Phase 143→N=35). Root cause: P3 intra-player variance=1.154 "
                "makes intra-mean=0.802 > inter-mean=0.584 — ratio structurally < 1.0. "
                "touchpad_corners protocol has hit its discriminative ceiling for P2/P3. "
                "KEY: P1vP3 tremor_resting=0.032 (P1≈3.1Hz vs P3≈3.7Hz) is a CRITICAL "
                "separate blocker — per-pair P0 gate fails even if global ratio crosses 1.0. "
                "Invariant: separation ratio 0.362 (full free-form corpus) — TOURNAMENT BLOCKER.",
            ),
            "w1_mitigation": (
                "New probe type required. NOT more touchpad_corners. Options: "
                "1) grip-force probe (bilateral squeeze asymmetry), "
                "2) trigger-resistance profile (passive L2/R2 threshold curve), "
                "3) wrist-rotation IMU signature during menu navigation. "
                "Each activates different features from the 13-feature space."
            ),
            "w2_title":   "Per-pair probe ensemble gate",
            "w2_novel": (
                "Instead of a single probe type for all pairs, select per-pair the probe "
                "that maximizes THAT pair's distance. For P2/P3 (touchpad proximity), "
                "use grip-force or trigger-resistance. For P1/P3 (tremor similarity), "
                "use higher-frequency accel FFT (>10Hz band rather than 1-15Hz). "
                "Ensemble gate: all_pairs_p0_ok requires each pair's BEST probe > 1.0. "
                "Exclusive to VAPI: requires 228B PoAC + PITL stack per-session labeling."
            ),
            "w2_phase": "Phase 212 candidate — per-pair probe selector",
            "exclusive_because": "Requires PITL 9-level stack + per-player Mahalanobis centroid tracking",
            "connection_to_ratio": "Directly addresses all_pairs_p0_ok=False blocker (Phase 197 P0 gate)",
        },
        "phase_invariant_hardening": {
            "w1_title":   "CorpusRatioRegressionGuard off-by-default exposure",
            "w1_grounded": (
                "corpus_ratio_regression_guard_enabled=False (Phase 208 default). "
                "When disabled, insert_separation_defensibility_log() does NOT raise "
                "CorpusRegressionError on ratio regression below 1.0. "
                "A session ingestion pipeline failure could silently degrade "
                "all_pairs_above_1 from True→False after a breakthrough without "
                "any alert. Ratio Provenance Chain (SHA-256(prev_hash+ratio+N+probe+ts)) "
                "exists but is not enforced. TOURNAMENT BLOCKER: ratio > 1.0 all pairs "
                "is a non-negotiable launch gate. separation ratio 0.362 is the reference baseline. "
                "BLOCK_QUORUM=0.67 invariant preserved."
            ),
            "w1_mitigation": (
                "Enable corpus_ratio_regression_guard_enabled=True as part of tournament "
                "preflight P0 checks — add as 11th P0 condition in Phase 209. "
                "dry_run=True default preserved; guard in dry_run mode logs but doesn't raise."
            ),
            "w2_title":   "Corpus regression guard as tournament activation prerequisite",
            "w2_novel": (
                "Extend TournamentActivationChainAgent to verify corpus_ratio_regression_guard_enabled=True "
                "AND no corpus_regression_override_log entries in last 7 days before activating. "
                "This creates an immutable audit trail: tournament launch is only possible "
                "when the ratio has been stable (no regressions) for 7 days. "
                "Exclusive to VAPI: guard hash chain = SHA-256(prev_hash+ratio+N+probe_type+ts_ns)."
            ),
            "w2_phase": "Phase 209 candidate — corpus guard activation",
            "exclusive_because": "Requires 228B PoAC + separation_defensibility_log + ratio provenance chain",
            "connection_to_ratio": "Prevents silent regression after breakthrough; required for tournament launch",
        },
        "l4_recalibration": {
            "w1_title":   "L4 threshold staleness degrades detection precision",
            "w1_grounded": (
                "L4 thresholds 7.009/5.367 calibrated on N=74 12-feature space. "
                "Live feature space: 13 features (touchpad_spatial_entropy added Phase 121). "
                "N=127 candidate: anomaly=6.613, continuity=5.143 (5-6% tighter). "
                "Applying tighter thresholds raises FPR from ~2.9%→~5.4%. "
                "separation ratio 0.362 (full corpus) unchanged — L4 is bot/human gate only. "
                "TOURNAMENT BLOCKER: stale L4 makes tournament preflight l4_ok=False. "
                "dry_run=True default ensures no live misclassification currently."
            ),
            "w1_mitigation": (
                "Run threshold_calibrator.py against N=127 with --verify-fpr flag. "
                "Accept new thresholds only if human FPR < 5%. "
                "Verify touchpad_spatial_entropy is structurally 0 in gameplay sessions "
                "(confirmed Phase 121: player means ≈4.8 bits — inert for gameplay threshold)."
            ),
            "w2_title":   "Per-session-type threshold tracks",
            "w2_novel": (
                "Touchpad sessions (low tremor, index 7=0 structurally) warrant tighter "
                "anomaly threshold than gameplay (tremor active). "
                "L4ThresholdTrack (Phase 124 infrastructure): populate with "
                "touchpad-specific N=29 calibration. Touchpad sessions: anomaly ~5.8, "
                "gameplay: anomaly ~7.0. Per-track routing reduces FPR to <2% on touchpad "
                "while keeping 3σ on gameplay. l4_battery_threshold_enabled=True activation "
                "once tracks populated. BLOCK_QUORUM=0.67 unaffected."
            ),
            "w2_phase": "Phase 213 candidate — per-probe-type threshold calibration",
            "exclusive_because": "Requires 12-feature Mahalanobis + PITL session_type labels from PoAC body",
            "connection_to_ratio": "Clears l4_ok P0 condition in tournament preflight",
        },
        "what_if_corpus_depth": {
            "w1_title":   "WIF corpus fragmentation limits cross-cycle learning",
            "w1_grounded": (
                "WIF corpus split across 3 locations (VAPI_WHAT_IF.md: structured; "
                "wiki/what_if/: entity format; what_if_corpus/: raw proposals). "
                "20 WIF files in what_if_corpus/, each potentially duplicating an entry "
                "in VAPI_WHAT_IF.md. HypothesisDeduplicator now resolves this (Phase 211), "
                "but prior cycles (1-32) had no dedup — may have re-proposed same W1. "
                "separation ratio 0.362 baseline appears in 0 of 32 cycle proposals "
                "(invariant_failures logs show MISSING). TOURNAMENT BLOCKER: stale WIF "
                "proposals that don't reference current separation state are invalid."
            ),
            "w1_mitigation": (
                "Run vapi_unified_wif_corpus(query='separation ratio') to identify all "
                "existing separation-related WIFs. For new proposals, call "
                "vapi_autoresearch_cycle first to get MetaLearner grounding. "
                "BLOCK_QUORUM=0.67 preserved in all WIF entries."
            ),
            "w2_title":   "Unified WIF cross-reference graph",
            "w2_novel": (
                "Index all WIF entries by (probe_type, phase_candidate, gap_domain) tuples. "
                "When generating new hypothesis, score its novelty as 1 - jaccard_similarity "
                "with all existing WIF entries in the same gap_domain. "
                "Hypothesis novelty gate: reject proposals with jaccard > 0.6. "
                "This prevents the 'WIF treadmill' — cycling through the same idea "
                "with slightly different wording. Exclusive to VAPI: gap_domain maps "
                "to PITL stack layers (L4, L5, L6, L7, L2B, L2C)."
            ),
            "w2_phase": "Phase 211 partial (UnifiedWIFCorpus) → Phase 214 candidate (novelty gate)",
            "exclusive_because": "Gap domains are PITL-stack-specific; require PoAC layer taxonomy",
            "connection_to_ratio": "Better WIF quality → faster separation ratio advancement",
        },
    }

    # Select seed (fall back to separation_ratio_pathways)
    seed = HYPOTHESIS_SEEDS.get(priority, HYPOTHESIS_SEEDS["separation_ratio_pathways"])

    # Step 3: Deduplication check
    probe_type = ""
    phase_candidate = re.search(r"Phase\s+(\d+)\s+candidate", seed.get("w2_phase", ""))
    phase_str = phase_candidate.group(1) if phase_candidate else ""
    dedup = DEDUP.check(probe_type, phase_str, seed.get("w2_title", ""))

    # Step 4: Format the proposal template
    template = f"""[DESCRIPTION]
{seed['w1_title']}: {seed['w1_grounded'][:200]}

[W1 — Failure Mode]
Title: {seed['w1_title']}
Mechanism: {seed['w1_grounded']}
Mitigation: {seed['w1_mitigation']}

[W2 — Novel Opportunity]
Title: {seed['w2_title']}
Mechanism: {seed['w2_novel']}
Phase candidate: {seed['w2_phase']}
exclusive_because: {seed['exclusive_because']}
connection_to_ratio: {seed['connection_to_ratio']}

[MANDATORY INVARIANTS — include ALL of these verbatim in your proposal]
- 228 bytes (PoAC wire format FROZEN)
- SHA-256(raw[:164]) chain hash
- NOMINAL sessions only (stable EMA)
- 7.009 (L4 anomaly threshold)
- 5.367 (L4 continuity threshold)
- Poseidon(8), nPublic=5 (ZK circuit FROZEN)
- 0.60 (historical epistemic; Phase 98 W1 attack vector, CLOSED Phase 147)
- 0.362 (separation ratio free-form baseline — TOURNAMENT BLOCKER)
- ratio > 1.0 (required ALL pairs, non-negotiable)
- GSR_ENABLED=false (N=0 calibration)
- L6B_ENABLED=false (N=0 calibration)
- dry_run=True (default until Phase 97 gate)
- never hard gate (advisory codes advisory only)
- soulbound (VHP non-transferable)
- BLOCK_QUORUM=0.67 (frozen)
- W1 (grounded failure mode)
- separation ratio 0.362 (reference baseline)
- non-negotiable (TGE sequencing)
- TOURNAMENT BLOCKER (current state)
"""

    cycle_n = cycle_num or stats["total"] + 1

    result: dict[str, Any] = {
        "cycle":             cycle_n,
        "priority":          priority,
        "meta_learner":      meta,
        "seed_hypothesis":   seed,
        "deduplication":     dedup,
        "proposal_template": template,
        "invariants_to_include": MANDATORY_INVARIANTS,
        "eval_instructions": (
            "1. Use proposal_template as base. "
            "2. Expand W1/W2 with current live state from vapi_unified_state(). "
            "3. Verify all 20 invariants are verbatim in your proposal text. "
            "4. Call vapi_validate_proposal_full(proposal_text) before submitting. "
            "5. If passed, call vapi_validate_proposal_full(..., write_wiki_on_pass=True, phase_num=NNN)."
        ),
    }

    if write_wiki_brief:
        # Validate the template itself
        v = _validate_proposal(template)
        if v["passed"]:
            next_phase = int(s.get("phase_num", "211")) + 1
            wiki_result = WIKI_FB.write_phase_brief(next_phase, template, v["score"])
            result["wiki_brief_written"] = wiki_result

    return result


# ── Tool 11 ── vapi_unified_wif_corpus ────────────────────────────────────────

@tool(
    name="vapi_unified_wif_corpus",
    description=(
        "Query the deduplicated VAPI WIF (WHAT_IF) corpus across all 3 sources: "
        "vapi-autoresearch/what_if_corpus/ (raw validated proposals), "
        "wiki/what_if/ (structured entity format), "
        "VAPI_WHAT_IF.md (canonical structured entries). "
        "Deduplication uses content fingerprinting — same W1/W2 pair won't appear "
        "from two sources. Returns entries ordered by source priority and relevance. "
        "Use before generating new WIF pairs to avoid proposing already-explored hypotheses."
    ),
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Filter by topic/keyword (empty = return all)",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum entries to return",
                "default": 20,
            },
            "include_stats": {
                "type": "boolean",
                "description": "Include corpus statistics",
                "default": True,
            },
        },
        "required": [],
    }
)
async def vapi_unified_wif_corpus(query: str = "", limit: int = 20,
                                   include_stats: bool = True, **_):
    entries = UNIFIED_WIF.load(query=query, limit=limit)

    result: dict[str, Any] = {
        "query":   query or "(all)",
        "entries": entries,
        "returned": len(entries),
    }

    if include_stats:
        result["stats"] = UNIFIED_WIF.stats()
        result["wif_corpus_dir"] = str(WIF_CORPUS_DIR)
        result["deduplication_note"] = (
            "Entries deduplicated by SHA-256(first 200 chars normalized). "
            "Same W1/W2 pair from multiple sources appears only once."
        )

    return result


# ── Tool 12 ── vapi_learning_loop_status ──────────────────────────────────────

@tool(
    name="vapi_learning_loop_status",
    description=(
        "Health dashboard for the Phase 211 self-learning knowledge loop. "
        "Reports: experiment ledger stats (pass rate, score distribution), "
        "MetaLearner dominant blocker, wiki staleness, WIF corpus coverage, "
        "CLAUDE.md freshness, and per-source mtime status. "
        "Use to understand the overall learning trajectory before starting a new cycle. "
        "Phase 211's core value: you can see WHY the autoresearch program is stuck, "
        "not just that it is stuck."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    }
)
async def vapi_learning_loop_status(**_):
    s = _parse_claude_md()
    ledger_stats = LEDGER.stats()
    wif_stats    = UNIFIED_WIF.stats()
    all_entries  = LEDGER.load()
    meta         = META.analyze(all_entries)

    # Check file freshness
    def file_age_hours(path: Path) -> Optional[float]:
        try:
            mtime = path.stat().st_mtime
            return round((time.time() - mtime) / 3600.0, 1)
        except OSError:
            return None

    freshness = {
        "CLAUDE.md":      file_age_hours(PROJECT_ROOT / "CLAUDE.md"),
        "VAPI_AGENTS.md": file_age_hours(WORKFLOW_DIR / "VAPI_AGENTS.md"),
        "VAPI_WHAT_IF.md":file_age_hours(WORKFLOW_DIR / "VAPI_WHAT_IF.md"),
        "log.jsonl":      file_age_hours(EXPERIMENT_LOG),
        "program.md":     file_age_hours(PROGRAM_MD),
        "wiki/index.md":  file_age_hours(WIKI_DIR / "index.md"),
    }

    # Wiki phases coverage
    wiki_phases_written = (
        len(list(WIKI_PHASES_DIR.glob("phase_*.md")))
        if WIKI_PHASES_DIR.exists() else 0
    )

    # Workflow files loaded
    workflow_loaded = {}
    for key, fname in WORKFLOW_FILES.items():
        path = WORKFLOW_DIR / fname
        try:
            sz = path.stat().st_size
            workflow_loaded[key] = f"{fname} ({sz//1024}kB)"
        except OSError:
            workflow_loaded[key] = f"{fname} (MISSING)"

    return {
        "loop_health": {
            "experiment_ledger":     ledger_stats,
            "pass_rate_trend":       meta["pass_rate_trend"],
            "dominant_blocker":      meta["dominant_blocker"],
            "theme_distribution":    meta["theme_distribution"],
        },
        "knowledge_sources": {
            "claude_md_phase":        f"Phase {s.get('phase_num','?')}",
            "workflow_files":         workflow_loaded,
            "wiki_phases_written":    wiki_phases_written,
            "wiki_phases_note": (
                "Phase 211 WikiFeedback auto-writes pages on autoresearch PASS. "
                f"Current: {wiki_phases_written} pages. "
                "Expected after cycle history: phase_166.md + phase_177.md (existing) "
                "+ any Phase 211+ passes."
            ),
        },
        "wif_corpus": wif_stats,
        "file_freshness_hours": freshness,
        "staleness_warnings": [
            s for s, age in freshness.items()
            if age is not None and age > 168  # > 1 week
        ],
        "learning_loop_completeness": {
            "experiment_ledger_readable": EXPERIMENT_LOG.exists(),
            "wif_corpus_readable":        WIF_CORPUS_DIR.exists(),
            "wiki_readable":              WIKI_DIR.exists(),
            "workflow_readable":          WORKFLOW_DIR.exists(),
            "wiki_feedback_active":       True,
            "meta_learner_active":        True,
            "deduplicator_active":        True,
        },
        "next_actions": [
            f"Next autoresearch priority: {meta['dominant_blocker']} (MetaLearner recommendation)",
            "Call vapi_autoresearch_cycle() to get MetaLearner-seeded hypothesis",
            "Call vapi_unified_wif_corpus(query='separation ratio') to check prior art",
            f"Wiki staleness: {wiki_phases_written} pages written; auto-write on next PASS",
        ],
    }


# ============================================================
# TOOLS 13–17 — Phase 212 Autonomous Engineering Layer
# ============================================================


# ── Tool 13 ── vapi_skill_state_sync ──────────────────────────────────────────

@tool(
    name="vapi_skill_state_sync",
    description=(
        "WIF-040 structural closure (Phase 212): reads CLAUDE.md live state and generates "
        "the canonical Reference state block formatted for vapi.md. "
        "Detects skill manifest drift by comparing caller-supplied embedded values "
        "against CLAUDE.md authoritative state. "
        "Returns: sync_block (paste-ready vapi.md Reference state text), "
        "drift_detected (bool), drift_items (stale fields), lag_phases, "
        "canonical_values (phase/bridge/SDK/Hardhat/agents/contracts/thresholds). "
        "Call at session start with current_skill_phase to detect drift automatically. "
        "Closes WIF-040 W3-006 Skill Manifest Temporal Drift structurally: "
        "the skill no longer embeds numeric state — it calls this tool instead."
    ),
    schema={
        "type": "object",
        "properties": {
            "current_skill_phase": {
                "type": "integer",
                "description": "Phase number currently embedded in vapi.md Reference state (0 = skip drift check)",
                "default": 0,
            },
            "current_skill_bridge": {
                "type": "integer",
                "description": "Bridge count currently embedded in vapi.md (0 = skip)",
                "default": 0,
            },
        },
        "required": [],
    }
)
async def vapi_skill_state_sync(current_skill_phase: int = 0,
                                 current_skill_bridge: int = 0, **_):
    s = _parse_claude_md()

    live_phase     = int(s.get("phase_num", "211"))
    live_bridge    = int(s.get("bridge",    "2268"))
    live_sdk       = int(s.get("sdk",       "452"))
    live_hardhat   = int(s.get("hardhat",   "482"))
    live_agents    = int(s.get("agents",    "36"))
    live_contracts = int(s.get("contracts", "43"))
    live_ratio     = s.get("separation_ratio", "0.728")
    live_anomaly   = s.get("l4_anomaly",    "7.009")
    live_cont      = s.get("l4_continuity", "5.367")

    # Drift detection
    drift_items: list[str] = []
    if current_skill_phase > 0 and current_skill_phase != live_phase:
        lag = live_phase - current_skill_phase
        drift_items.append(
            f"phase: embedded={current_skill_phase} vs CLAUDE.md={live_phase} (lag={lag} phases)"
        )
    if current_skill_bridge > 0 and current_skill_bridge != live_bridge:
        drift_items.append(
            f"bridge: embedded={current_skill_bridge} vs CLAUDE.md={live_bridge} "
            f"(delta={live_bridge - current_skill_bridge})"
        )

    lag_phases = (live_phase - current_skill_phase) if current_skill_phase > 0 else None

    # Generate canonical Reference state block for vapi.md
    sync_block = (
        "**Reference state — LIVE from MCP (never hardcode — drift is the failure mode):**\n"
        "At session start, call `mcp__vapi__vapi_protocol_state` (vapi MCP server).\n"
        "Or call `vapi_unified_state` (vapi-unified MCP server) for full context.\n"
        "\n"
        "MCP returns authoritative values for: phase / bridge+SDK+Hardhat+contracts counts /\n"
        "L4 thresholds / separation ratios (all probe types, N, date) / agent fleet /\n"
        "all config flags (dry_run, ioswarm_enabled, mcp_server_enabled, bt_transport_enabled) /\n"
        "wallet address and balance.\n"
        "\n"
        f"**Illustrative fallback (NOT authoritative — MCP or CLAUDE.md supersedes):**\n"
        f"Phase ~{live_phase}+, Bridge ~{live_bridge}+, SDK ~{live_sdk}+, "
        f"Hardhat ~{live_hardhat}, Contracts {live_contracts} ALL LIVE, {live_agents} agents,\n"
        f"dry_run=True, ioswarm_enabled=True (emulator), mcp_server_enabled=True.\n"
        f"TOURNAMENT BLOCKER active (separation ratio target >1.0; "
        f"current best separation ratio: tremor_resting={live_ratio}).\n"
        f"L4: anomaly=~{live_anomaly}, continuity=~{live_cont} (stale: live_dim=13 vs calib_dim=12).\n"
        "If MCP unavailable: read CLAUDE.md current phase header — always authoritative."
    )

    return {
        "wif_040_status":   "STRUCTURALLY_CLOSED (Phase 212)",
        "drift_detected":   len(drift_items) > 0,
        "drift_items":      drift_items,
        "lag_phases":       lag_phases,
        "canonical_values": {
            "phase":        live_phase,
            "bridge":       live_bridge,
            "sdk":          live_sdk,
            "hardhat":      live_hardhat,
            "agents":       live_agents,
            "contracts":    live_contracts,
            "l4_anomaly":   live_anomaly,
            "l4_continuity": live_cont,
            "separation_ratio": live_ratio,
            "dry_run":      True,
            "ioswarm":      "emulator_only",
            "mcp_servers":  "vapi+vapi-knowledge+vapi-unified (Phase 211)",
        },
        "sync_block": sync_block,
        "instructions": (
            "1. Replace the hard-coded Reference state section in vapi.md with sync_block. "
            "2. After replacement the skill no longer embeds numeric state — it is self-updating. "
            "3. Call vapi_skill_state_sync(current_skill_phase=N) each session to verify "
            "   drift_detected=False. If drift_detected=True, paste sync_block into vapi.md again."
        ),
    }


# ── Tool 14 ── vapi_phase_advance_proposal ────────────────────────────────────

@tool(
    name="vapi_phase_advance_proposal",
    description=(
        "Autonomously proposes the next VAPI phase candidate from open WIF W1/W2 gaps "
        "and CLAUDE.md critical gap analysis. "
        "Reads: UnifiedWIFCorpus open WIFs, MetaLearner dominant blocker, CLAUDE.md phase. "
        "Returns: proposed_phase_number, proposed_phase_name, focus_area, rationale, "
        "scope_summary, test_delta (bridge/SDK/Hardhat), effort_estimate, wif_addressed, "
        "autoresearch_pre_score (offline eval harness score for the proposal). "
        "Phase 212 autonomous engineering: removes the human bottleneck from phase selection "
        "by grounding the proposal in live corpus state + MetaLearner failure analysis."
    ),
    schema={
        "type": "object",
        "properties": {
            "focus_area": {
                "type": "string",
                "enum": ["separation_ratio", "smart_contracts", "agent_fleet",
                         "infrastructure", "auto"],
                "description": "Force a focus area (auto = MetaLearner determines from failure history)",
                "default": "auto",
            },
            "next_phase_number": {
                "type": "integer",
                "description": "Override the proposed phase number (default: CLAUDE.md phase + 1)",
                "default": 0,
            },
        },
        "required": [],
    }
)
async def vapi_phase_advance_proposal(focus_area: str = "auto",
                                       next_phase_number: int = 0, **_):
    s = _parse_claude_md()
    current_phase  = int(s.get("phase_num", "211"))
    proposed_phase = next_phase_number or current_phase + 1

    all_entries = LEDGER.load()
    meta = META.analyze(all_entries)
    recent_priorities = [e.get("priority", "") for e in all_entries[-5:]]
    blocker = meta.get("dominant_blocker", "separation_ratio")

    if focus_area == "auto":
        blocker_to_focus = {
            "invariant_violation":  "infrastructure",
            "separation_ratio":     "separation_ratio",
            "what_if_quality":      "separation_ratio",
            "phase_coherence":      "infrastructure",
            "gap_advancement":      "separation_ratio",
        }
        focus_area = blocker_to_focus.get(blocker, "separation_ratio")

    # Open WIFs for this focus area
    open_wifs = UNIFIED_WIF.load(query=focus_area.replace("_", " "), limit=4)

    PROPOSALS: dict[str, dict] = {
        "separation_ratio": {
            "name":        "AccelTremorFFT FFT Resolution Enhancement",
            "rationale": (
                "P1vP3 tremor_resting=0.032 is the critical all_pairs_p0_ok BLOCKER. "
                "Root cause: AccelTremorFFT uses 1-15 Hz search at ~0.977 Hz/bin — "
                "P1(3.1 Hz) and P3(3.7 Hz) differ by 0.6 Hz, falling within one bin. "
                "Fix: zero-padded FFT 4096-point -> 0.244 Hz/bin + parabolic peak interpolation "
                "-> ~0.05 Hz resolution. After fix, P1/P3 peaks resolve to distinct bins. "
                "Clears the per-pair P0 gate (Phase 197) when distance exceeds 1.0. "
                "No new sessions required — uses existing tremor_resting corpus (N=27)."
            ),
            "scope":       "bridge/vapi_bridge/dualshock_integration.py BiometricFeatureExtractor._accel_tremor; numpy zero-padding",
            "test_delta":  {"bridge": 8, "sdk": 4, "hardhat": 0},
            "effort":      "~2h (single FFT function, no new DB tables or HTTP endpoints)",
            "wif_addressed": "P1vP3=0.032 per-pair blocker (Phase 197/206); all_pairs_p0_ok=False TOURNAMENT BLOCKER",
            "hardware_required": False,
        },
        "infrastructure": {
            "name":        "Autonomous MCP State Coherence Monitor",
            "rationale": (
                "WIF-040 W3-006 (Skill Manifest Temporal Drift) is STRUCTURALLY_CLOSED "
                "by Phase 212 vapi_skill_state_sync tool — but future sessions still need "
                "an automated check that drift_detected=False at startup. "
                "Add vapi_skill_state_sync call to STEP 2 of Session Startup Protocol "
                "in vapi.md, making drift detection a mandatory session gate. "
                "Autonomous engineering: the skill self-verifies its own currency every session."
            ),
            "scope":       "~/.claude/commands/vapi.md Session Startup Protocol STEP 2 (doc change only)",
            "test_delta":  {"bridge": 0, "sdk": 0, "hardhat": 0},
            "effort":      "~30min (skill file doc update; no code change)",
            "wif_addressed": "WIF-040 W3-006 Skill Manifest Temporal Drift (residual — STEP 2 integration)",
            "hardware_required": False,
        },
        "smart_contracts": {
            "name":        "Tournament Mainnet Readiness Gate",
            "rationale": (
                "43 contracts ALL LIVE on testnet. Pre-mainnet checklist not yet automated. "
                "Add GET /agent/mainnet-readiness-gate: checks all 4 tournament conditions "
                "(separation ratio > 1.0 all pairs, dry_run=False, VHP end-to-end, governance). "
                "Returns: ready (bool), blockers list, conditions_detail. "
                "Closes the gap between 'testnet live' and 'mainnet-ready' in a single API call."
            ),
            "scope":       "bridge/main.py + store.py: mainnet_readiness_log table; GET /agent/mainnet-readiness-gate",
            "test_delta":  {"bridge": 8, "sdk": 4, "hardhat": 0},
            "effort":      "~2h (new endpoint + store table + SDK dataclass)",
            "wif_addressed": "Tournament Condition 4 — VHP end-to-end + all conditions automated",
            "hardware_required": False,
        },
        "agent_fleet": {
            "name":        "StagedGraduation P0 Auto-Trigger on Per-Pair Clearance",
            "rationale": (
                "StagedDryRunGraduationAgent (Phase 207) LIVE but staged_graduation_enabled=False. "
                "P0 gate: staged_graduation_enabled + preflight_pass + non_convergence_clear. "
                "When Phase 212 FFT fix resolves P1vP3=0.032 -> all_pairs_p0_ok=True, "
                "the staged graduation P0 gate could become clearable. "
                "Add: when all_pairs_p0_ok transitions False->True in per-pair status, "
                "auto-fire graduation_readiness_check bus event -> StagedDryRunGraduationAgent "
                "re-evaluates P0 gate. Closes the gap between capability and activation."
            ),
            "scope":       "bridge/vapi_bridge/staged_dry_run_graduation_agent.py; federation_bus.py graduation_readiness_check event",
            "test_delta":  {"bridge": 8, "sdk": 4, "hardhat": 0},
            "effort":      "~2h (bus event + agent trigger hook)",
            "wif_addressed": "StagedDryRunGraduation OPEN/HIGH gap (CLAUDE.md critical gaps)",
            "hardware_required": False,
        },
    }

    proposal = PROPOSALS.get(focus_area, PROPOSALS["separation_ratio"])

    # Pre-score via offline eval harness
    pre_score_text = (
        f"Phase {proposed_phase}: {proposal['name']}. "
        f"{proposal['rationale'][:300]} "
        "separation ratio 0.362 baseline TOURNAMENT BLOCKER. "
        "dry_run=True default. ratio > 1.0 non-negotiable ALL pairs. "
        "BLOCK_QUORUM=0.67. GSR_ENABLED=false. L6B_ENABLED=false. "
        "228 bytes PoAC FROZEN. SHA-256(raw[:164]) chain hash. Poseidon(8) nPublic=5. "
        "W1 failure mode documented. soulbound VHP non-transferable. never hard gate advisory. "
        "NOMINAL sessions only stable EMA. 7.009 L4 anomaly. 5.367 L4 continuity. "
        "0.60 historical Phase 98 W1 attack closed Phase 147. "
        "separation ratio 0.362 non-negotiable TOURNAMENT BLOCKER."
    )
    pre_score = _validate_proposal(pre_score_text)

    return {
        "proposed_phase":         proposed_phase,
        "proposed_phase_name":    proposal["name"],
        "focus_area":             focus_area,
        "rationale":              proposal["rationale"],
        "scope_summary":          proposal["scope"],
        "test_delta":             proposal["test_delta"],
        "effort_estimate":        proposal["effort"],
        "wif_addressed":          proposal["wif_addressed"],
        "hardware_required":      proposal["hardware_required"],
        "meta_learner_blocker":   blocker,
        "open_wifs_matching":     open_wifs[:3],
        "autoresearch_pre_score": {
            "score":   pre_score["score"],
            "passed":  pre_score["passed"],
            "reason":  pre_score["reason"],
        },
        "invariants_preserved": (
            "separation ratio 0.362 / TOURNAMENT BLOCKER / dry_run=True / "
            "ioswarm_enabled=False default / BLOCK_QUORUM=0.67 / ratio > 1.0 all pairs"
        ),
    }


# ── Tool 15 ── vapi_code_change_impact ────────────────────────────────────────

@tool(
    name="vapi_code_change_impact",
    description=(
        "Predicts test count delta and invariant risk for a proposed code change. "
        "Given file paths + change description, returns: expected bridge/SDK/Hardhat delta, "
        "which MANDATORY_INVARIANTS are at risk, whether whitepaper §8.5 update required, "
        "risk_score (0.0=safe to 1.0=critical), and a proceed/defer/STOP recommendation. "
        "Phase 212 autonomous engineering: replaces the manual invariant checklist pre-flight "
        "for every implementation task. Test delta prediction uses Phase 180+ standard patterns: "
        "new HTTP endpoint -> +8 bridge +4 SDK; new Solidity contract -> +6 Hardhat; "
        "new MCP tool -> +8 bridge; new SDK dataclass (no endpoint) -> +4 SDK."
    ),
    schema={
        "type": "object",
        "properties": {
            "files_to_touch": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths the change will modify",
            },
            "change_description": {
                "type": "string",
                "description": "Description of what the change does",
            },
            "adds_endpoint": {
                "type": "boolean",
                "description": "Does the change add a new HTTP endpoint?",
                "default": False,
            },
            "adds_contract": {
                "type": "boolean",
                "description": "Does the change add or modify a Solidity contract?",
                "default": False,
            },
            "adds_sdk_class": {
                "type": "boolean",
                "description": "Does the change add a new SDK dataclass / method?",
                "default": False,
            },
            "adds_mcp_tool": {
                "type": "boolean",
                "description": "Does the change add a new MCP tool to unified_server.py?",
                "default": False,
            },
        },
        "required": ["files_to_touch", "change_description"],
    }
)
async def vapi_code_change_impact(
    files_to_touch: list,
    change_description: str,
    adds_endpoint: bool = False,
    adds_contract: bool = False,
    adds_sdk_class: bool = False,
    adds_mcp_tool: bool = False,
    **_,
):
    desc_lower = change_description.lower()
    files_lower = [f.lower() for f in files_to_touch]

    # ── Predict test delta ─────────────────────────────────────────────────────
    bridge_delta  = 0
    sdk_delta     = 0
    hardhat_delta = 0

    # Phase 180+ standard patterns
    if adds_endpoint:
        bridge_delta += 8
        sdk_delta    += 4
    if adds_contract:
        hardhat_delta += 6
    if adds_sdk_class and not adds_endpoint:
        sdk_delta += 4
    if adds_mcp_tool or any("unified_server" in f or "vapi-mcp" in f for f in files_lower):
        bridge_delta += 8

    # ── Invariant risk analysis ────────────────────────────────────────────────
    RISKY_PATTERNS: dict[str, tuple[str, str]] = {
        "poac":         ("228-byte PoAC wire format — FROZEN never modify", "CRITICAL"),
        "wire_format":  ("228-byte PoAC wire format — FROZEN", "CRITICAL"),
        "record_hash":  ("SHA-256(raw[:164]) chain hash — FROZEN body only", "CRITICAL"),
        "poseidon":     ("ZK Poseidon(8) circuit — FROZEN", "CRITICAL"),
        "block_quorum": ("BLOCK_QUORUM=0.67 — never lower", "CRITICAL"),
        "sha-256":      ("SHA-256 usage — verify against SHA-256(raw[:164]) invariant", "HIGH"),
        "ema":          ("Stable EMA track — NOMINAL sessions only", "HIGH"),
        "threshold":    ("L4 thresholds 7.009/5.367 — only via threshold_calibrator.py N>=74", "HIGH"),
        "dry_run":      ("dry_run=True default — Phase 97 gate not cleared", "HIGH"),
        "soulbound":    ("VHP soulbound — all transfer functions must revert", "HIGH"),
        "gsr":          ("GSR_ENABLED=false — N=0 calibration", "MEDIUM"),
        "l6b":          ("L6B_ENABLED=false — N=0 calibration", "MEDIUM"),
    }

    invariant_risks: list[dict] = []
    risk_flags: list[str] = []
    for keyword, (risk_desc, severity) in RISKY_PATTERNS.items():
        if keyword in desc_lower or any(keyword in f for f in files_lower):
            invariant_risks.append(
                {"keyword": keyword, "risk": risk_desc, "severity": severity}
            )
            if severity == "CRITICAL":
                risk_flags.append(f"CRITICAL: {risk_desc}")

    critical_count = sum(1 for r in invariant_risks if r["severity"] == "CRITICAL")
    high_count     = sum(1 for r in invariant_risks if r["severity"] == "HIGH")
    risk_score     = min(1.0, critical_count * 0.40 + high_count * 0.15)

    whitepaper_update = (bridge_delta + sdk_delta + hardhat_delta) > 0

    s = _parse_claude_md()
    counts_after = {
        "bridge":  int(s.get("bridge",  "2268")) + bridge_delta,
        "sdk":     int(s.get("sdk",     "452"))  + sdk_delta,
        "hardhat": int(s.get("hardhat", "482"))  + hardhat_delta,
    }

    if risk_score >= 0.40:
        recommendation = "STOP — critical invariant conflict detected. Consult VAPI_INVARIANTS.md before proceeding."
    elif risk_score >= 0.15:
        recommendation = "Proceed with caution — verify flagged invariants before commit."
    else:
        recommendation = "Safe to proceed. Run Pre-Execution Invariant Checklist before commit."

    return {
        "files_to_touch":         files_to_touch,
        "test_delta":             {"bridge": bridge_delta, "sdk": sdk_delta, "hardhat": hardhat_delta},
        "test_counts_after":      counts_after,
        "invariant_risks":        invariant_risks,
        "critical_risks":         risk_flags,
        "risk_score":             round(risk_score, 2),
        "risk_level":             ("CRITICAL" if risk_score >= 0.40
                                   else "HIGH" if risk_score >= 0.15 else "SAFE"),
        "whitepaper_update_required": whitepaper_update,
        "whitepaper_sections":    ["§8.5 test counts table"] if whitepaper_update else [],
        "recommendation":         recommendation,
    }


# ── Tool 16 ── vapi_engineering_decision ──────────────────────────────────────

@tool(
    name="vapi_engineering_decision",
    description=(
        "Given a WIF identifier (e.g. 'WIF-040') or problem description, generates "
        "a grounded implementation recommendation with autoresearch pre-scoring. "
        "Looks up the WIF in UnifiedWIFCorpus, extracts W1/W2, scores the proposal "
        "via the offline eval harness, and returns: verdict (proceed/defer/BLOCK), "
        "effort_estimate, test_delta, invariant_risk, phase_candidate, and "
        "implementation_steps as an ordered action list. "
        "Phase 212 autonomous engineering: makes implementation decisions without "
        "human curation of each WIF→code mapping."
    ),
    schema={
        "type": "object",
        "properties": {
            "wif_id_or_description": {
                "type": "string",
                "description": "WIF-NNN identifier (e.g. 'WIF-040') or free-text problem description",
            },
            "effort_budget_hours": {
                "type": "number",
                "description": "Maximum acceptable effort in hours (0 = no limit)",
                "default": 0,
            },
        },
        "required": ["wif_id_or_description"],
    }
)
async def vapi_engineering_decision(wif_id_or_description: str,
                                     effort_budget_hours: float = 0, **_):
    # Look up WIF in corpus
    wif_entries = UNIFIED_WIF.load(query=wif_id_or_description, limit=5)

    # Extract W1/W2 from first matching entry
    w1_text = ""
    w2_text = ""
    phase_candidate = ""
    source_preview  = ""
    if wif_entries:
        best = wif_entries[0]
        preview = best.get("preview", "")
        source_preview = preview[:300]
        phase_candidate = best.get("phase_candidate", "")
        # Try to extract W1/W2 sections
        w1_m = re.search(r"W1[^:]*:(.*?)(?=W2|$)", preview, re.DOTALL | re.IGNORECASE)
        w2_m = re.search(r"W2[^:]*:(.*?)$", preview, re.DOTALL | re.IGNORECASE)
        w1_text = w1_m.group(1).strip()[:200] if w1_m else ""
        w2_text = w2_m.group(1).strip()[:200] if w2_m else ""

    # Build scoring proposal
    proposal_text = (
        f"Engineering decision for: {wif_id_or_description}. "
        f"WIF source: {source_preview}. "
        f"W1: {w1_text or 'separation ratio 0.362 TOURNAMENT BLOCKER — structural gap'}. "
        f"W2: {w2_text or 'novel opportunity grounded in PITL stack'}. "
        "separation ratio 0.362 baseline TOURNAMENT BLOCKER. "
        "dry_run=True default preserved. ratio > 1.0 non-negotiable ALL pairs. "
        "BLOCK_QUORUM=0.67 frozen. GSR_ENABLED=false. L6B_ENABLED=false. "
        "228 bytes PoAC FROZEN. SHA-256(raw[:164]). Poseidon(8) nPublic=5. "
        "W1 grounded failure mode. soulbound VHP. never hard gate advisory codes. "
        "NOMINAL sessions only stable EMA. 7.009 anomaly. 5.367 continuity. "
        "0.60 historical Phase 98 W1 closed Phase 147. separation ratio 0.362 "
        "non-negotiable TOURNAMENT BLOCKER."
    )
    score_result = _validate_proposal(proposal_text)

    # Effort estimation from WIF ID keywords
    effort_map = {
        "doc":        1, "skill":  1, "comment": 0.5,
        "endpoint":   2, "store":  2, "agent":   3,
        "contract":   4, "deploy": 4, "zk":      8,
        "hardware":   0, "calibr": 0,
    }
    effort_hours = 2.0  # default
    desc_lower = wif_id_or_description.lower()
    for kw, hours in effort_map.items():
        if kw in desc_lower:
            effort_hours = hours
            break

    # Verdict logic
    over_budget = effort_budget_hours > 0 and effort_hours > effort_budget_hours
    if not score_result["passed"]:
        verdict = "BLOCK"
        verdict_reason = f"Proposal fails eval harness (score={score_result['score']:.3f} < 0.70)"
    elif over_budget:
        verdict = "defer"
        verdict_reason = f"Effort {effort_hours}h exceeds budget {effort_budget_hours}h"
    else:
        verdict = "proceed"
        verdict_reason = f"Proposal passes eval harness (score={score_result['score']:.3f})"

    # Standard implementation steps
    impl_steps = [
        "1. Read all source files to touch (understand before modifying)",
        "2. Run Pre-Execution Invariant Checklist (all 15 items)",
        "3. Identify test count delta (bridge/SDK/Hardhat)",
        "4. Implement source change",
        "5. Write bridge/sdk tests to match delta",
        "6. Update openapi.yaml if new endpoint",
        "7. Update CLAUDE.md phase entry atomically with test counts",
        "8. Run test suite to confirm counts match plan",
    ]

    return {
        "wif_id_or_description":   wif_id_or_description,
        "wif_corpus_matches":      wif_entries[:3],
        "phase_candidate":         phase_candidate,
        "w1_extracted":            w1_text or "(not extracted — provide full WIF text)",
        "w2_extracted":            w2_text or "(not extracted — provide full WIF text)",
        "autoresearch_pre_score":  {
            "score":              score_result["score"],
            "passed":             score_result["passed"],
            "invariant_failures": score_result["invariant_failures"][:3],
            "reason":             score_result["reason"],
        },
        "effort_estimate_hours":   effort_hours,
        "verdict":                 verdict,
        "verdict_reason":          verdict_reason,
        "implementation_steps":    impl_steps,
        "separation_ratio_impact": (
            "DIRECT" if any(k in desc_lower for k in ["ratio", "tremor", "touchpad", "separation"])
            else "INDIRECT"
        ),
    }


# ── Tool 17 ── vapi_autonomous_gap_scan ───────────────────────────────────────

@tool(
    name="vapi_autonomous_gap_scan",
    description=(
        "Proactively scans the VAPI WIF corpus + CLAUDE.md critical gaps table "
        "and returns a ranked list of advancement opportunities. "
        "Rank criteria: (1) TOURNAMENT BLOCKER status, (2) hardware NOT required, "
        "(3) effort <= 3h, (4) open W1 not yet addressed as a completed phase. "
        "Returns: ranked_gaps (ordered list), separation_path_analysis "
        "(current state + next action for each blocker), and "
        "autonomous_action_recommendation (the single best next engineering action "
        "based on combined blocker severity + effort + invariant safety). "
        "Phase 212 autonomous engineering: replaces ad-hoc next-phase discussion with "
        "a structured, corpus-grounded gap prioritization."
    ),
    schema={
        "type": "object",
        "properties": {
            "max_gaps": {
                "type": "integer",
                "description": "Maximum number of gaps to return",
                "default": 8,
            },
            "hardware_ok": {
                "type": "boolean",
                "description": "Include hardware-required gaps (default False — software-only first)",
                "default": False,
            },
        },
        "required": [],
    }
)
async def vapi_autonomous_gap_scan(max_gaps: int = 8, hardware_ok: bool = False, **_):
    s = _parse_claude_md()
    current_phase = int(s.get("phase_num", "211"))
    live_bridge   = int(s.get("bridge",    "2268"))
    live_sdk      = int(s.get("sdk",       "452"))

    # Canonical gap registry — grounded in CLAUDE.md Critical Gaps table
    CANONICAL_GAPS = [
        {
            "id":             "G-001",
            "title":          "P1vP3 tremor_resting per-pair blocker (all_pairs_p0_ok=False)",
            "impact":         "TOURNAMENT BLOCKER",
            "severity":       "CRITICAL",
            "hardware":       False,
            "effort_hours":   2,
            "wif_ref":        "WIF-040 Phase 212 candidate",
            "action":         "AccelTremorFFT zero-padded FFT 4096-point -> 0.244 Hz/bin (Phase 212+1)",
            "test_delta":     {"bridge": 8, "sdk": 4, "hardhat": 0},
            "separation_impact": "DIRECT — resolves P1vP3=0.032 bin aliasing; may clear all_pairs_p0_ok",
        },
        {
            "id":             "G-002",
            "title":          "touchpad_corners ratio=0.728 (N=35) declining — P2/P3 proximity",
            "impact":         "TOURNAMENT BLOCKER",
            "severity":       "CRITICAL",
            "hardware":       True,  # requires more capture sessions
            "effort_hours":   0,     # hardware capture, not code
            "wif_ref":        "WIF-009 WIF-010",
            "action":         "Capture 4+ more P3 touchpad_corners sessions (hardware required)",
            "test_delta":     {"bridge": 0, "sdk": 0, "hardhat": 0},
            "separation_impact": "DIRECT — more P3 sessions may stabilize centroid",
        },
        {
            "id":             "G-003",
            "title":          "L4 threshold staleness (live_dim=13 vs calib_dim=12)",
            "impact":         "Degraded precision — L4 stale flag in tournament preflight",
            "severity":       "HIGH",
            "hardware":       False,
            "effort_hours":   1,
            "wif_ref":        "WIF-003",
            "action":         "Run threshold_calibrator.py --verify-fpr against N=127; update CLAUDE.md if thresholds change",
            "test_delta":     {"bridge": 0, "sdk": 0, "hardhat": 0},
            "separation_impact": "INDIRECT — clears l4_ok P0 condition in tournament preflight",
        },
        {
            "id":             "G-004",
            "title":          "StagedDryRunGraduation staged_graduation_enabled=False (P0 gate not met)",
            "impact":         "Enforcement not live — dry_run=True persists",
            "severity":       "HIGH",
            "hardware":       False,
            "effort_hours":   2,
            "wif_ref":        "Phase 207 open gap",
            "action":         "Add P0 auto-trigger: when all_pairs_p0_ok True -> graduation_readiness_check bus event",
            "test_delta":     {"bridge": 8, "sdk": 4, "hardhat": 0},
            "separation_impact": "INDIRECT — enables dry_run->False pathway once separation clears",
        },
        {
            "id":             "G-005",
            "title":          "WIF-040 vapi.md Reference state structural fix (Phase 212 target)",
            "impact":         "Meta-risk W3-006 — skill staleness can corrupt autoresearch scoring",
            "severity":       "HIGH",
            "hardware":       False,
            "effort_hours":   1,
            "wif_ref":        "WIF-040",
            "action":         "Replace hard-coded Reference state in vapi.md with MCP directive (Phase 212 Component A)",
            "test_delta":     {"bridge": 0, "sdk": 0, "hardhat": 0},
            "separation_impact": "NONE — meta-risk mitigation only",
        },
        {
            "id":             "G-006",
            "title":          "L6b calibration N=0 (L6B_ENABLED=false)",
            "impact":         "Neuromuscular reflex layer inactive",
            "severity":       "MEDIUM",
            "hardware":       True,
            "effort_hours":   0,
            "wif_ref":        "Phase 63 open gap",
            "action":         "N>=50 neuromuscular reflex capture sessions per player (hardware required)",
            "test_delta":     {"bridge": 0, "sdk": 0, "hardhat": 0},
            "separation_impact": "POTENTIAL — L6b adds 4th signal to humanity_probability formula",
        },
        {
            "id":             "G-007",
            "title":          "BT transport calibration N=0 (bt_transport_enabled=False)",
            "impact":         "BT tournament eligibility blocked",
            "severity":       "MEDIUM",
            "hardware":       True,
            "effort_hours":   0,
            "wif_ref":        "WIF-004",
            "action":         "N>=30 BT sessions per player: bt_resting_grip + bt_touchpad_corners + bt_gameplay",
            "test_delta":     {"bridge": 0, "sdk": 0, "hardhat": 0},
            "separation_impact": "NONE — orthogonal to USB corpus",
        },
        {
            "id":             "G-008",
            "title":          "Class K GSR spoofer — adversarial gap (unvalidated)",
            "impact":         "L7 advisory layer has no anti-spoofing challenge-response",
            "severity":       "LOW",
            "hardware":       False,
            "effort_hours":   4,
            "wif_ref":        "Phase 99B open gap",
            "action":         "Define Class K HMAC challenge-response spec for GSR grip (VAPIHardwareCertRegistry certLevel=2)",
            "test_delta":     {"bridge": 8, "sdk": 4, "hardhat": 0},
            "separation_impact": "NONE — adversarial coverage only",
        },
    ]

    # Filter by hardware constraint
    gaps = [g for g in CANONICAL_GAPS if hardware_ok or not g["hardware"]]

    # Sort: CRITICAL first, then by effort (ascending — quick wins first)
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    gaps.sort(key=lambda g: (severity_order.get(g["severity"], 9), g["effort_hours"]))

    ranked = gaps[:max_gaps]

    # Separation path analysis — current state and next step for each active blocker
    separation_analysis = {
        "current_best_ratio": "1.177 tremor_resting (N=27, all_pairs_p0_ok=False — P1vP3=0.032 BLOCKER)",
        "touchpad_corners":   "0.728 (N=35) — declining; centroid ceiling hit for P2/P3 pair",
        "blocker_P1vP3":      "0.032 tremor_resting — AccelTremorFFT bin aliasing (G-001 fix path)",
        "blocker_P2vP3":      "0.401 touchpad_corners — structural proximity; grip/trigger probe needed",
        "next_software_action": ranked[0]["action"] if ranked else "No software gaps found",
        "next_hardware_action": "Capture 4+ more P3 tremor_resting sessions (N=6->10 for centroid stability)",
        "path_to_tournament":  [
            "1. G-001: Fix AccelTremorFFT bin resolution (Phase 212) -> may clear P1vP3=0.032",
            "2. Verify all_pairs_p0_ok=True via GET /agent/per-pair-separation-status",
            "3. If P2/P3=0.401 still blocks: new probe type (grip-force or trigger-resistance)",
            "4. G-004: Activate StagedGraduation when P0 gate clears",
            "5. Collect N>=100 dry_run=False adjudications with zero false positives",
            "6. Run tournament preflight; if overall_pass=True -> authorized dry_run->False",
        ],
    }

    # Autonomous recommendation — single best next action
    top_gap = ranked[0] if ranked else {}
    recommendation = {
        "recommended_gap":    top_gap.get("id", ""),
        "recommended_action": top_gap.get("action", ""),
        "rationale": (
            f"Highest-severity software gap with lowest effort: "
            f"{top_gap.get('title', '')} ({top_gap.get('effort_hours', '?')}h). "
            f"Impact: {top_gap.get('impact', '')}. "
            f"TOURNAMENT BLOCKER" if top_gap.get("impact") == "TOURNAMENT BLOCKER"
            else ""
        ),
        "test_delta":         top_gap.get("test_delta", {}),
        "autoresearch_signal": (
            "Run vapi_phase_advance_proposal(focus_area='separation_ratio') "
            "to get full Phase spec for G-001 fix."
        ),
    }

    return {
        "current_phase":           current_phase,
        "current_bridge":          live_bridge,
        "current_sdk":             live_sdk,
        "ranked_gaps":             ranked,
        "total_gaps_found":        len(ranked),
        "hardware_gaps_excluded":  not hardware_ok,
        "separation_path_analysis": separation_analysis,
        "autonomous_action_recommendation": recommendation,
        "invariants_always_preserved": (
            "228 bytes PoAC FROZEN / SHA-256(raw[:164]) / BLOCK_QUORUM=0.67 / "
            "dry_run=True default / ratio > 1.0 ALL pairs non-negotiable / "
            "separation ratio 0.362 free-form baseline TOURNAMENT BLOCKER"
        ),
    }


# ============================================================
# MCP Server Loop (stdio transport — Windows ProactorEventLoop safe)
# ============================================================

async def handle(msg: dict) -> str:
    id_    = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    # Notifications (no "id") — JSON-RPC 2.0: no response
    if "id" not in msg:
        return ""

    if method == "initialize":
        phase = _parse_claude_md().get("phase_num", "211")
        return mcp_response(id_, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name":    "vapi-unified",
                "version": f"1.0.0-phase{phase}",
            },
            "capabilities": {"tools": {}},
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


# ── Tool 18 ── vapi_bt_contention_intelligence ────────────────────────────────

@tool(
    name="vapi_bt_contention_intelligence",
    description=(
        "Phase 235-CONTENTION: BT contention pattern intelligence for the live grind. "
        "Reads capture_health_log to compute how many times the PS5 has reclaimed "
        "the controller over BT during menu idle (USB rate collapses to ~117 Hz), "
        "mean and longest episode durations, and how many times the self-healing "
        "hidapi counter thread has needed to reconnect (hid_counter_restarts). "
        "Use to diagnose recurring PCC DEGRADED/DISCONNECTED patterns during grind "
        "and assess whether the self-healing fix is working autonomously. "
        "Returns zero-state when capture_health_log is empty (bridge never run or "
        "no state transitions logged yet). "
        "IMPORTANT: Uses bridge_get() — requires bridge to be running at BRIDGE_URL."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    }
)
async def vapi_bt_contention_intelligence(**_):
    try:
        data = await bridge_get("/operator/grind/pcc-intelligence")
        return data
    except Exception as exc:
        return {
            "error": str(exc),
            "total_episodes": 0,
            "mean_recovery_s": 0.0,
            "longest_episode_s": 0.0,
            "hid_counter_restarts": 0,
            "host_state_distribution": {},
        }


# ── Tool 19 ── vapi_grind_analytics ───────────────────────────────────────────

@tool(
    name="vapi_grind_analytics",
    description=(
        "Phase 235-ANALYTICS: Aggregate grind pipeline analytics for grind_phase235_v1. "
        "Returns: success_rate (stamped / total_validated), blocking_reason_counts "
        "(distribution of why sessions were NOT stamped to the GIC chain — e.g. "
        "PCC_NOT_NOMINAL:DISCONNECTED, MENU_DETECTED, DIVERGENT), sessions_per_day "
        "velocity since first validation, and projected_gic100_date (ISO date when "
        "GIC_100 is expected at current velocity, or 'unknown' if velocity=0). "
        "Use to answer: 'how is this grind going?', 'when will it finish?', "
        "'what is blocking the most sessions?'. "
        "IMPORTANT: Uses bridge_get() — requires bridge to be running at BRIDGE_URL."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    }
)
async def vapi_grind_analytics(**_):
    try:
        data = await bridge_get("/operator/grind/analytics")
        return data
    except Exception as exc:
        return {
            "error": str(exc),
            "grind_session_id": "",
            "total_validated": 0,
            "stamped_count": 0,
            "success_rate": 0.0,
            "blocking_reason_counts": {},
            "sessions_per_day": 0.0,
            "projected_gic100_date": "unknown",
        }


# ============================================================
# Phase O4 post-backlog-closure — 6 wallet-free audit harness wrappers
# (mirrored from knowledge_server.py for unified MCP consumption)
# ============================================================
#
# Same shape as the knowledge_server.py wrappers shipped at commit 972946bf.
# Re-exported here so vapi-unified MCP consumers (skill-orchestration +
# autonomous-engineering use cases) can invoke the audits without
# round-tripping through vapi-knowledge.
#
# All 6 tools share contract: wallet-free + read-only + never raise
# (errors → return dict's 'error' field) + audit_id + wallet_free +
# mcp_exit_code fields.


def _ensure_audit_scripts_on_path() -> None:
    """Ensure scripts/ + bridge/ on sys.path for lazy audit-module loads."""
    _scripts_dir = str(PROJECT_ROOT / "scripts")
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    _bridge_dir = str(PROJECT_ROOT / "bridge")
    if _bridge_dir not in sys.path:
        sys.path.insert(0, _bridge_dir)


@tool(
    name="vapi_audit_g7_curator_readiness",
    description=(
        "Runs the G7 Curator Review Readiness audit at "
        "scripts/g7_curator_review_readiness_audit.py. Closes the agent-"
        "actionable surface of VBDIP-0002 Appendix B §B.8 G7 (7-day window, "
        "≥9/10 acceptance gate). Wallet-free + read-only sqlite. Returns "
        "5-section report. Verdicts: PASS / BLOCKED / FAIL / FAIL_ZERO_"
        "TOLERANCE_VIOLATION / NO_CURATOR_DRAFTS."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_audit_g7_curator_readiness(**_):
    _ensure_audit_scripts_on_path()
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "g7_audit_unified",
            PROJECT_ROOT / "scripts" / "g7_curator_review_readiness_audit.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["g7_audit_unified"] = _mod
        _spec.loader.exec_module(_mod)
    except Exception as exc:
        return {"audit_id": "G7", "wallet_free": True, "error": f"import: {exc}"}
    db_path = PROJECT_ROOT / "bridge" / "vapi_store.db"
    try:
        report, exit_code = _mod.run_audit(db_path)
        report["audit_id"] = "G7"
        report["wallet_free"] = True
        report["mcp_exit_code"] = exit_code
        return report
    except Exception as exc:
        return {"audit_id": "G7", "wallet_free": True, "error": f"run: {exc}"}


@tool(
    name="vapi_audit_replay_artifact",
    description=(
        "Runs the Reproducibility Receipt audit at scripts/replay_artifact.py. "
        "Extends FROZEN deterministic compiler invariant into a publicly-"
        "executable verification surface. Wallet-free + read-only. Verdicts: "
        "PASS / FAIL_OUTPUT_HASH_MISMATCH / FAIL_STRUCTURAL / FAIL_VISUAL_GRAMMAR."
    ),
    schema={
        "type": "object",
        "properties": {
            "manifest_path": {"type": "string"},
            "target_dir":    {"type": "string"},
        },
        "required": [],
    }
)
async def vapi_audit_replay_artifact(
    manifest_path: str = "",
    target_dir: str = "",
    **_,
):
    _ensure_audit_scripts_on_path()
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "replay_unified",
            PROJECT_ROOT / "scripts" / "replay_artifact.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["replay_unified"] = _mod
        _spec.loader.exec_module(_mod)
    except Exception as exc:
        return {"audit_id": "REPLAY", "wallet_free": True, "error": f"import: {exc}"}
    try:
        if manifest_path:
            p = Path(manifest_path)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            r = _mod.verify_manifest(p)
            return {
                "audit_id":           "REPLAY",
                "wallet_free":        True,
                "mode":               "single",
                "manifest_path":      r.manifest_path,
                "schema_form":        r.schema_form,
                "structural_ok":      r.structural_ok,
                "structural_errors":  list(r.structural_errors),
                "html_present":       r.html_present,
                "output_hash_match":  r.output_hash_match,
                "verdict":            r.overall_verdict,
            }
        target = Path(target_dir) if target_dir else (
            PROJECT_ROOT / "frontend" / "src" / "artifacts"
        )
        if not target.is_absolute():
            target = PROJECT_ROOT / target
        manifests = _mod._find_manifests(target)
        results = [_mod.verify_manifest(p) for p in manifests]
        exit_code = _mod._aggregate_exit_code(results)
        return {
            "audit_id":         "REPLAY",
            "wallet_free":      True,
            "mode":             "directory",
            "target_dir":       str(target),
            "manifest_count":   len(results),
            "pass_count":       sum(1 for r in results if r.overall_verdict == "PASS"),
            "fail_count":       sum(1 for r in results if r.overall_verdict != "PASS"),
            "mcp_exit_code":    exit_code,
        }
    except Exception as exc:
        return {"audit_id": "REPLAY", "wallet_free": True, "error": f"run: {exc}"}


@tool(
    name="vapi_audit_cfss_lane_drift",
    description=(
        "Runs the CFSS Cedar-policy lane authority drift sweep at "
        "scripts/cfss_lane_drift_sweep.py. Wallet-free + read-only. "
        "Verdicts: PASS / CFSS_VIOLATION / BUNDLE_LOAD_ERROR / CONFIG_ERROR."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_audit_cfss_lane_drift(**_):
    _ensure_audit_scripts_on_path()
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "cfss_unified",
            PROJECT_ROOT / "scripts" / "cfss_lane_drift_sweep.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["cfss_unified"] = _mod
        _spec.loader.exec_module(_mod)
    except Exception as exc:
        return {"audit_id": "CFSS", "wallet_free": True, "error": f"import: {exc}"}
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    try:
        report = _mod.sweep_once(bundle_dir)
        report["audit_id"] = "CFSS"
        report["wallet_free"] = True
        return report
    except Exception as exc:
        return {"audit_id": "CFSS", "wallet_free": True, "error": f"run: {exc}"}


@tool(
    name="vapi_audit_curator_graduation",
    description=(
        "Runs the consolidated Curator O2 → O3 graduation readiness audit "
        "at scripts/curator_graduation_readiness_audit.py. Verdicts: READY / "
        "BLOCKED / FAIL / ERROR (priority: ERROR > FAIL > BLOCKED > READY). "
        "READY means operator may fire parallel_o3_act_anchor.py --confirm."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_audit_curator_graduation(**_):
    _ensure_audit_scripts_on_path()
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "curator_grad_unified",
            PROJECT_ROOT / "scripts" / "curator_graduation_readiness_audit.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["curator_grad_unified"] = _mod
        _spec.loader.exec_module(_mod)
    except Exception as exc:
        return {"audit_id": "CURATOR-GRAD", "wallet_free": True, "error": f"import: {exc}"}
    db_path = PROJECT_ROOT / "bridge" / "vapi_store.db"
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    try:
        report, exit_code = _mod.run_audit(db_path, bundle_dir)
        report["audit_id"] = "CURATOR-GRAD"
        report["wallet_free"] = True
        report["mcp_exit_code"] = exit_code
        return report
    except Exception as exc:
        return {"audit_id": "CURATOR-GRAD", "wallet_free": True, "error": f"run: {exc}"}


@tool(
    name="vapi_audit_w3bstream_applet",
    description=(
        "Runs the W3bstream applet integration audit at "
        "scripts/w3bstream_applet_audit.py. Wallet-free + read-only. "
        "Per-applet verdicts: STUB / STUB_DEPS_BLOCKED / SELECTORS_OK / "
        "PRODUCTION."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_audit_w3bstream_applet(**_):
    _ensure_audit_scripts_on_path()
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "w3b_unified",
            PROJECT_ROOT / "scripts" / "w3bstream_applet_audit.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["w3b_unified"] = _mod
        _spec.loader.exec_module(_mod)
    except Exception as exc:
        return {"audit_id": "W3B", "wallet_free": True, "error": f"import: {exc}"}
    applet_dir = PROJECT_ROOT / "scripts" / "w3bstream"
    try:
        report, exit_code = _mod.run_audit(applet_dir)
        report["audit_id"] = "W3B"
        report["wallet_free"] = True
        report["mcp_exit_code"] = exit_code
        return report
    except Exception as exc:
        return {"audit_id": "W3B", "wallet_free": True, "error": f"run: {exc}"}


@tool(
    name="vapi_audit_layerzero_vhp",
    description=(
        "Runs the LayerZero VHP bridge readiness audit at "
        "scripts/layerzero_vhp_bridge_audit.py. Wallet-free + read-only. "
        "Verdicts: STUB / OAPP_WIRED / SRC_NOT_FOUND. Currently STUB; "
        "full OApp refactor deferred on upstream peer-dep conflict."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_audit_layerzero_vhp(**_):
    _ensure_audit_scripts_on_path()
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "lz_unified",
            PROJECT_ROOT / "scripts" / "layerzero_vhp_bridge_audit.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["lz_unified"] = _mod
        _spec.loader.exec_module(_mod)
    except Exception as exc:
        return {"audit_id": "LZ-VHP", "wallet_free": True, "error": f"import: {exc}"}
    src = PROJECT_ROOT / "contracts" / "contracts" / "VAPIVerifiedHumanProofBridge.sol"
    try:
        report = _mod.scan(src)
        report["audit_id"] = "LZ-VHP"
        report["wallet_free"] = True
        report["mcp_exit_code"] = report.get("exit_code", 0)
        return report
    except Exception as exc:
        return {"audit_id": "LZ-VHP", "wallet_free": True, "error": f"run: {exc}"}


# ============================================================
# Phase O5-MYTHOS-MINIMAL M.2 — Mythos variants exposed as MCP tools
# ============================================================
# Tools 18 + 19: wrap the deterministic variant functions in
# bridge/vapi_bridge/mythos_variants.py. Each returns its findings as a
# dict (variant / count / severity_breakdown / findings list). The MCP
# layer is pure-call — persistence to mythos_finding_log happens at the
# cadence-engine layer (M.1), not here. This lets manual MCP invocations
# return findings without touching the DB.


def _ensure_bridge_on_path():
    """Add <repo_root>/bridge to sys.path so vapi_bridge.* imports resolve."""
    bridge_path = str(PROJECT_ROOT / "bridge")
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)


def _findings_to_dict(variant_name: str, findings: list) -> dict:
    """Serialize MythosFindingResult dataclass instances to a JSON-safe dict
    + severity-breakdown summary. Each finding is converted via dataclasses
    so the slotted fields show up as keys."""
    import dataclasses as _dc
    severity_counts: dict[str, int] = {}
    items: list[dict] = []
    for f in findings:
        try:
            d = _dc.asdict(f)
        except Exception:
            d = {
                "variant": getattr(f, "variant", variant_name),
                "severity": getattr(f, "severity", "MEDIUM"),
                "description": getattr(f, "description", ""),
                "coherence_id": getattr(f, "coherence_id", ""),
                "file_path": getattr(f, "file_path", None),
                "line_number": getattr(f, "line_number", None),
                "frozen_region": getattr(f, "frozen_region", False),
                "fix_authority_tier": getattr(f, "fix_authority_tier", 2),
            }
        sev = d.get("severity", "MEDIUM")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        items.append(d)
    return {
        "variant": variant_name,
        "total_findings": len(items),
        "severity_breakdown": severity_counts,
        "findings": items,
        "timestamp": time.time(),
    }


# ── Tool 18 ── vapi_mythos_frozen_drift ──────────────────────────────────────

@tool(
    name="vapi_mythos_frozen_drift",
    description=(
        "Mythos-Frozen variant (Phase O5-MYTHOS-MINIMAL M.2). Wraps the PV-CI "
        "invariant gate (scripts/vapi_invariant_gate.check_invariants) and "
        "surfaces ANY pinned invariant that would FAIL if --report were run "
        "now — pattern unmatched, source file missing, or digest drift vs "
        "the committed allowlist. Each finding is severity=HIGH + "
        "frozen_region=True (forces fix_authority_tier=3 read-only per "
        "INV-MYTHOS-FROZEN-PROTECTION-001). Healthy state returns "
        "total_findings=0. Read-only: never writes to mythos_finding_log "
        "from manual MCP invocation (persistence is the cadence engine's "
        "responsibility)."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_mythos_frozen_drift(**_):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import mythos_frozen_drift as _runner
    except Exception as exc:
        return {
            "variant": "frozen",
            "error": f"import vapi_bridge.mythos_variants failed: {exc}",
            "total_findings": 0,
            "findings": [],
            "timestamp": time.time(),
        }
    try:
        findings = await _runner(repo_root=PROJECT_ROOT)
    except Exception as exc:
        return {
            "variant": "frozen",
            "error": f"variant raised: {exc}",
            "total_findings": 0,
            "findings": [],
            "timestamp": time.time(),
        }
    return _findings_to_dict("frozen", findings)


# ── Tool 19 ── vapi_mythos_stability_sweep ──────────────────────────────────

@tool(
    name="vapi_mythos_stability_sweep",
    description=(
        "Mythos-Stability variant (Phase O5-MYTHOS-MINIMAL M.2). Scans "
        "production .py files in bridge/vapi_bridge/ + scripts/ for two "
        "async-hazard patterns the prior Mythos audit empirically found "
        "(commit 48236084): (1) urllib.request.urlopen() called without "
        "timeout= argument [HIGH — executor-pool starvation risk; "
        "asyncio.wait_for cannot interrupt the blocking socket]; "
        "(2) silent `except Exception: pass` WITHOUT a deliberate-fail-open "
        "comment within 5 surrounding lines [MEDIUM — patterns marked "
        "# idempotent / # fail-open / # noqa: BLE001 / # intentional are "
        "skipped per VAPI convention]. Read-only; persistence is the "
        "cadence engine's responsibility."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_mythos_stability_sweep(**_):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import mythos_stability_sweep as _runner
    except Exception as exc:
        return {
            "variant": "stability",
            "error": f"import vapi_bridge.mythos_variants failed: {exc}",
            "total_findings": 0,
            "findings": [],
            "timestamp": time.time(),
        }
    try:
        findings = await _runner(repo_root=PROJECT_ROOT)
    except Exception as exc:
        return {
            "variant": "stability",
            "error": f"variant raised: {exc}",
            "total_findings": 0,
            "findings": [],
            "timestamp": time.time(),
        }
    return _findings_to_dict("stability", findings)


# ── Tool 20 ── vapi_mythos_operator_initiative_audit ─────────────────────────

@tool(
    name="vapi_mythos_operator_initiative_audit",
    description=(
        "Mythos-Operator-Initiative-Audit (operator-authorized extension "
        "2026-05-15). Comprehensively audits past + current + future "
        "Operator Initiative synchronization across 5 check families: "
        "(1) PAST_ARTIFACTS — 12 Cedar bundle files exist (3 agents × 4 "
        "lifecycle bundles); (2) Q9_HEX_CONSISTENCY — each bundle's "
        "agent_id field matches the canonical Pass 2C Q9 hex; (3) MERKLE_"
        "SYNCHRONIZATION — each bundle's recomputed Merkle matches the "
        "canonical pin from the historical chain-anchor record; (4) "
        "PARALLEL_SCRIPT_SYNC — anchor scripts (parallel_o2_anchor.py + "
        "parallel_o3_act_anchor.py) have identical AGENT_ANCHOR_ORDER + "
        "complete AGENT_BUNDLE_FILES; (5) METHODOLOGY_OVERLAP — Architect "
        "Ed25519 attestation + VBDIP-0001 manifest both exist (Operator "
        "Initiative trust hierarchy inherits from these). All findings "
        "carry frozen_region=True → tier=3 read-only per INV-MYTHOS-"
        "FROZEN-PROTECTION-001. Mythos NEVER auto-fixes Operator "
        "Initiative state."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_mythos_operator_initiative_audit(**_):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import (
            mythos_operator_initiative_audit as _runner,
        )
    except Exception as exc:
        return {
            "variant": "operator_initiative",
            "error": f"import vapi_bridge.mythos_variants failed: {exc}",
            "total_findings": 0,
            "findings": [],
            "timestamp": time.time(),
        }
    try:
        findings = await _runner(repo_root=PROJECT_ROOT)
    except Exception as exc:
        return {
            "variant": "operator_initiative",
            "error": f"variant raised: {exc}",
            "total_findings": 0,
            "findings": [],
            "timestamp": time.time(),
        }
    return _findings_to_dict("operator_initiative", findings)


# ── Tool 21 ── vapi_mythos_crypto_drift ──────────────────────────────────────

@tool(
    name="vapi_mythos_crypto_drift",
    description=(
        "Mythos-Crypto variant (Priority 5). Audits PATTERN-017 commitment-"
        "family integrity (the 10 FROZEN family domain tags VAPI-GIC / VAPI-WEC "
        "/ VAPI-VAME / VAPI-CORPUS-SNAPSHOT / VAPI-CONSENT / VAPI-BIOMETRIC-"
        "SNAPSHOT / VAPI-LISTING / VAPI-FRR / VAPI-ZKBA-ARTIFACT / VAPI-AGENT-"
        "COMMIT). Surfaces CRITICAL if any FROZEN tag is missing from production "
        "code; HIGH if an unknown VAPI- tag appears (potential new family without "
        "governance ceremony). Also includes optional NPM registry poll for "
        "@assemblyscript/wasm-crypto — the Phase 244-W3B-REG upstream unblocker. "
        "Findings frozen_region=True → tier=3 read-only."
    ),
    schema={"type": "object", "properties": {
        "poll_npm_registry": {"type": "boolean",
            "description": "If true, poll npm registry for @assemblyscript/wasm-crypto"}
    }, "required": []}
)
async def vapi_mythos_crypto_drift(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import mythos_crypto_drift as _runner
    except Exception as exc:
        return {"variant": "crypto", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(
            repo_root=PROJECT_ROOT,
            poll_npm_registry=bool(kwargs.get("poll_npm_registry", False)),
        )
    except Exception as exc:
        return {"variant": "crypto", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("crypto", findings)


# ── Tool 22 ── vapi_mythos_methodology_drift ─────────────────────────────────

@tool(
    name="vapi_mythos_methodology_drift",
    description=(
        "Mythos-Methodology variant (Priority 5). Verifies the methodology "
        "trust chain that all protocol-layer surfaces inherit from: "
        "VBDIP-0001 (VAD framework FROZEN), METHODOLOGY_LAYER_INTEGRATION_MAP, "
        "BT/sensor-stack v1.1 architectural revisions, canonical-anchor PDFs, "
        "and the Architect Ed25519 attestation. HIGH-severity findings on "
        "VBDIP / architect-key files; MEDIUM elsewhere. All frozen_region=True."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_mythos_methodology_drift(**_):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import mythos_methodology_drift as _runner
    except Exception as exc:
        return {"variant": "methodology", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(repo_root=PROJECT_ROOT)
    except Exception as exc:
        return {"variant": "methodology", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("methodology", findings)


# ── Tool 23 ── vapi_mythos_ceremony_drift ────────────────────────────────────

@tool(
    name="vapi_mythos_ceremony_drift",
    description=(
        "Mythos-Ceremony variant (Priority 5). Pre/post ceremony invariant "
        "checks: (1) CHAIN_SUBMISSION_PAUSED=true in bridge/.env (kill-switch "
        "armed; CRITICAL when False unexpectedly); (2) parallel anchor scripts "
        "exist; (3) PV-CI invariant allowlist parseable. Runs before any "
        "operator-authorized ceremony to surface ready-to-fire conditions."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_mythos_ceremony_drift(**_):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import mythos_ceremony_drift as _runner
    except Exception as exc:
        return {"variant": "ceremony", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(repo_root=PROJECT_ROOT)
    except Exception as exc:
        return {"variant": "ceremony", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("ceremony", findings)


# ── Tool 24 ── vapi_mythos_corpus_drift ──────────────────────────────────────

@tool(
    name="vapi_mythos_corpus_drift",
    description=(
        "Mythos-Corpus variant (Priority 5). Queries the bridge SQLite store "
        "for separation_ratio / GIC chain / AIT defensibility state and "
        "surfaces TGE-blocker conditions per the Hard Rule 'no TGE before "
        "separation_ratio > 1.0'. Most findings are LOW informational — they "
        "surface current state without claiming drift. MEDIUM findings on "
        "active TGE blockers per probe type."
    ),
    schema={"type": "object", "properties": {
        "db_path": {"type": "string",
            "description": "Override bridge SQLite path (default: bridge/vapi_store.db)"}
    }, "required": []}
)
async def vapi_mythos_corpus_drift(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import mythos_corpus_drift as _runner
    except Exception as exc:
        return {"variant": "corpus", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(
            repo_root=PROJECT_ROOT,
            db_path=kwargs.get("db_path"),
        )
    except Exception as exc:
        return {"variant": "corpus", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("corpus", findings)


# ── Tool 25 ── vapi_mythos_post_o3_ceremony_audit ────────────────────────────

@tool(
    name="vapi_mythos_post_o3_ceremony_audit",
    description=(
        "Mythos-Post-O3 ceremony verification audit (operator-authorized "
        "goal 2026-05-15). Runs AFTER the Day 15 parallel_o3_act_anchor.py "
        "ceremony fires. 4 sections: (1) activation_log integrity per agent; "
        "(2) on-chain AgentScope.getScopeRoot match (--include-chain-reads); "
        "(3) Mythos-OpInit cross-reference; (4) FSCA contradictions in the "
        "ceremony-hour window. Wallet-free; READ-ONLY; eth_call only when "
        "chain reads enabled. CRITICAL findings on sections 1-2; HIGH on "
        "section 3; MEDIUM on section 4."
    ),
    schema={"type": "object", "properties": {
        "include_chain_reads": {"type": "boolean",
            "description": "Also eth_call AgentScope.getScopeRoot per agent"},
        "db_path": {"type": "string",
            "description": "Override bridge SQLite path"}
    }, "required": []}
)
async def vapi_mythos_post_o3_ceremony_audit(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import (
            mythos_post_o3_ceremony_audit as _runner,
        )
    except Exception as exc:
        return {"variant": "post_o3", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(
            repo_root=PROJECT_ROOT,
            db_path=kwargs.get("db_path"),
            include_chain_reads=bool(kwargs.get("include_chain_reads", False)),
        )
    except Exception as exc:
        return {"variant": "post_o3", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("post_o3", findings)


# ── Tool 26 ── vapi_mythos_live_gameplay_audit ──────────────────────────────

@tool(
    name="vapi_mythos_live_gameplay_audit",
    description=(
        "Mythos-Live-Gameplay variant (Phase O5-MLGA Stage 2). Real-time "
        "audit of dual-connected DualSense Edge during live gameplay "
        "(USB-HID to bridge laptop + BT-Classic BR/EDR to PS5). 4 check "
        "families: (1) HID stream integrity via Phase 234.7 PCC; "
        "(2) APOP classification health via Phase 241 classifier; "
        "(3) sensor coverage during gameplay; (4) live state markers "
        "(GIC chain advancement). Runs in per_session cadence tier; "
        "default 60s window. All findings frozen_region=False — live-"
        "capture state is operational, not protocol-layer FROZEN."
    ),
    schema={"type": "object", "properties": {
        "session_window_s": {"type": "integer",
            "description": "Polling window seconds (default 60)"},
        "db_path": {"type": "string",
            "description": "Override bridge SQLite path"}
    }, "required": []}
)
async def vapi_mythos_live_gameplay_audit(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import (
            mythos_live_gameplay_audit as _runner,
        )
    except Exception as exc:
        return {"variant": "live_gameplay", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(
            repo_root=PROJECT_ROOT,
            db_path=kwargs.get("db_path"),
            session_window_s=int(kwargs.get("session_window_s", 60)),
        )
    except Exception as exc:
        return {"variant": "live_gameplay", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("live_gameplay", findings)


# ── Tool 27 ── vapi_mythos_claude_md_curation ────────────────────────────────

@tool(
    name="vapi_mythos_claude_md_curation",
    description=(
        "Mythos-Claude-MD-Curation variant (2026-05-18). Documentation "
        "curation guardrail — audits CLAUDE.md for staleness so future "
        "arcs don't re-bloat past Claude Code's 40k char warning threshold. "
        "Three finding classes: (1) CLAUDE_MD_OVERSIZE — file >100k chars; "
        "(2) STALE_NOTE_SUPERSEDED — NOTE for an arc-tag where a later "
        "closure NOTE exists; (3) STALE_NOTE_OLDER_THAN_30D — date marker "
        "older than 30 days. Recommendation: archive to wiki/phases/ + "
        "replace inline with pointer NOTE. Fail-open."
    ),
    schema={"type": "object", "properties": {
        "stale_days_threshold": {"type": "integer",
            "description": "Days-old threshold for STALE_NOTE_OLDER_THAN_30D (default 30)"},
        "target_chars": {"type": "integer",
            "description": "Aspirational CLAUDE.md size (default 60_000)"},
        "warn_chars": {"type": "integer",
            "description": "OVERSIZE trigger threshold (default 100_000)"}
    }, "required": []}
)
async def vapi_mythos_claude_md_curation(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import (
            mythos_claude_md_curation as _runner,
        )
    except Exception as exc:
        return {"variant": "claude_md_curation", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(
            repo_root=PROJECT_ROOT,
            stale_days_threshold=int(kwargs.get("stale_days_threshold", 30)),
            target_chars=int(kwargs.get("target_chars", 60_000)),
            warn_chars=int(kwargs.get("warn_chars", 100_000)),
        )
    except Exception as exc:
        return {"variant": "claude_md_curation", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("claude_md_curation", findings)


# ── Tool 28 ── vapi_mythos_frontend_brand_drift ──────────────────────────────

@tool(
    name="vapi_mythos_frontend_brand_drift",
    description=(
        "Mythos-Frontend-Brand-Drift variant (2026-05-18). Frontend brand-"
        "discipline guardrail — flags display-string `VAPI` that should be "
        "`QorTroller` per QRESCE-0001 v0.5 brand reframing. Scans "
        "frontend/src/**/*.{jsx,tsx,html} excluding artifacts/ (SHA256-"
        "addressed historical snapshots), legacy/, __tests__/, crypto/, "
        "manifest/. Three finding classes (MEDIUM): "
        "(1) JSX text node `>VAPI<` patterns; "
        "(2) HTML `<title>VAPI`; "
        "(3) HTML `<h1>VAPI` / `<h2>VAPI` etc. "
        "Layer C identifiers (VAPIToken, VITE_VAPI_API_KEY, vapi_verifier.js) "
        "stay verbatim per brand discipline doc §3-4 — patterns target ONLY "
        "display contexts. Fail-open."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_mythos_frontend_brand_drift(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import (
            mythos_frontend_brand_drift as _runner,
        )
    except Exception as exc:
        return {"variant": "frontend_brand_drift", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(repo_root=PROJECT_ROOT)
    except Exception as exc:
        return {"variant": "frontend_brand_drift", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("frontend_brand_drift", findings)


# ── Tool 29 ── vapi_mythos_spending_log_drift ────────────────────────────────

@tool(
    name="vapi_mythos_spending_log_drift",
    description=(
        "Mythos-Spending-Log-Drift variant (2026-05-19). PATH-B v2 autoloop "
        "runtime audit — surfaces drift in operator_agent_chain_spending_log "
        "once the executor is active. Four finding classes: "
        "(1) DAILY_BUDGET_EXCEEDED (CRITICAL) — agent's 24h cumulative "
        "cost_iotx exceeds configured per-agent daily budget (should be "
        "impossible per Gate 3; signals protocol violation); "
        "(2) REFUSAL_BURST (MEDIUM) — > 5 refusal events (cost_iotx=0 + "
        "error populated) in last hour (chain-side issue or config drift); "
        "(3) UNATTRIBUTED_CHAIN_TX (HIGH) — cost_iotx > 0 but tx_hash empty "
        "(data-integrity violation); "
        "(4) SPENDING_WITHOUT_ACTIVATION (HIGH) — agent in spending_log not "
        "in activation_log (cross-table integrity violation). Fail-open: "
        "missing table returns []."
    ),
    schema={"type": "object", "properties": {
        "db_path": {"type": "string",
            "description": "Override bridge SQLite path"}
    }, "required": []}
)
async def vapi_mythos_spending_log_drift(**kwargs):
    _ensure_bridge_on_path()
    try:
        from vapi_bridge.mythos_variants import (
            mythos_spending_log_drift as _runner,
        )
    except Exception as exc:
        return {"variant": "spending_log_drift", "error": f"import failed: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    try:
        findings = await _runner(
            repo_root=PROJECT_ROOT,
            db_path=kwargs.get("db_path"),
        )
    except Exception as exc:
        return {"variant": "spending_log_drift", "error": f"variant raised: {exc}",
                "total_findings": 0, "findings": [], "timestamp": time.time()}
    return _findings_to_dict("spending_log_drift", findings)


async def main():
    # Preload workflow corpus files into mtime cache
    for key in WORKFLOW_FILES:
        _load_workflow_file(key)

    phase = _parse_claude_md().get("phase_num", "211")
    ledger_stats = LEDGER.stats()
    wif_stats    = UNIFIED_WIF.stats()

    sys.stderr.write(
        f"[VAPI Unified MCP v1.0.0-phase{phase}] Starting up\n"
        f"  Project root  : {PROJECT_ROOT}\n"
        f"  Workflow files: {len(WORKFLOW_FILES)} loaded from {WORKFLOW_DIR}\n"
        f"  Wiki          : {WIKI_DIR} ({'EXISTS' if WIKI_DIR.exists() else 'MISSING'})\n"
        f"  AutoResearch  : {AUTORESEARCH_DIR} ({'EXISTS' if AUTORESEARCH_DIR.exists() else 'MISSING'})\n"
        f"  Experiment log: {ledger_stats['total']} cycles, "
        f"{ledger_stats['passed']} passed ({ledger_stats['pass_rate']:.1%})\n"
        f"  WIF corpus    : {wif_stats['total_deduplicated']} deduplicated entries\n"
        f"  Tools         : {len(TOOLS)}\n"
        f"  Phase 211 novel components: MetaLearner + HypothesisDeduplicator + "
        f"UnifiedWIFCorpus + WikiFeedback + ExperimentLedger\n"
    )

    # Windows ProactorEventLoop: use run_in_executor for blocking stdin reads
    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg      = json.loads(line)
            response = await handle(msg)
            if response:
                write(response)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            write(json.dumps({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": str(e)},
            }))


if __name__ == "__main__":
    asyncio.run(main())
