#!/usr/bin/env python3
"""
QorTroller Engineering Assistant
================================
One file. One process. One tool to rule them all.

Replaces: qortroller_tui.py + qortroller_daemon.py + _daemon_tools_schema.py
Provider: QuickSilver Pro (IoTeX) — model-agnostic
Interface: Textual TUI / REPL / MCP

Features:
  - QuickSilver Pro LLM client (any model, model-agnostic)
  - 30+ inline engineering tools (edit, shell, git, pytest, bridge, chain)
  - Hardware Watcher (DualShock Edge, capture card, bridge health)
  - Contradiction Oracle (30 FSCA rules, real-time pre-action check)
  - Invariant Sentinel (188 PV-CI invariants, continuous background check)
  - Autonomous Debug Loop (detect → fix → learn)
  - Protocol State Visualizer (live TUI panel)
  - Ceremony Bot (triple-gate ceremony management)
  - Hardware Biographer (DualShock Edge lifecycle tracking)
  - Reflex Concierge (operator state adaptation)
  - Cross-Session Continuity Engine (persistent memory across sessions)
  - Methodology Registry (persistent learning, grows with every session)
  - FROZEN governance gates (imported from _daemon_tools_schema.py)

Usage:
  python qortroller.py              # TUI mode (default)
  python qortroller.py --cli         # REPL mode
  python qortroller.py --mcp         # MCP server mode
  python qortroller.py --exec "cmd"  # One-shot command

Environment:
  QUICKSILVER_API_KEY    — QuickSilver Pro API key (required)
  QUICKSILVER_MODEL      — Model name (default: deepseek-v4-flash)
  BRIDGE_BASE_URL        — Bridge URL (default: http://localhost:8000)
  QORTROLLER_ROOT        — Repo root (default: auto-detect)
"""

from __future__ import annotations

import logging
import asyncio
import datetime
import hashlib
import hmac
import json
import os
import re
import sqlite3
import shlex
import subprocess
import sys
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Auto-detect repo root
REPO_ROOT = os.environ.get(
    "QORTROLLER_ROOT",
    os.path.dirname(os.path.abspath(__file__))
)

# ── Auto-load .env files ──────────────────────────────────────────────────
# Loads root .env first, then bridge/.env (later files override earlier ones)
for _env_path in (
    os.path.join(REPO_ROOT, ".env"),
    os.path.join(REPO_ROOT, "bridge", ".env"),
):
    if os.path.isfile(_env_path):
        try:
            with open(_env_path, "r", encoding="utf-8", errors="ignore") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        _k = _k.strip()
                        _v = _v.strip().strip('"').strip("'")
                        if _k not in os.environ:
                            os.environ[_k] = _v
        except Exception:
            pass  # Non-fatal — env files are best-effort

# QuickSilver Pro
QUICKSILVER_API_KEY = os.environ.get("QUICKSILVER_API_KEY", "")
QUICKSILVER_API_URL = "https://api.quicksilverpro.io/v1/chat/completions"
QUICKSILVER_MODEL = os.environ.get("QUICKSILVER_MODEL", "deepseek-v4-flash")

# Bridge
BRIDGE_BASE_URL = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000")

# Paths
DATA_DIR = os.path.join(REPO_ROOT, ".qortroller")
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_DB_PATH = os.path.join(DATA_DIR, "sessions.db")
METHODOLOGY_PATH = os.path.join(DATA_DIR, "methodology.json")
HARDWARE_DB_PATH = os.path.join(DATA_DIR, "hardware.db")
DECISIONS_PATH = os.path.join(DATA_DIR, "decisions.jsonl")

# Version
VERSION = "2.0.0"
APP_NAME = "QorTroller Engineering Assistant"

# ═══════════════════════════════════════════════════════════════════════════════
#  IMPORTS FROM EXISTING CODEBASE
# ═══════════════════════════════════════════════════════════════════════════════

# Try to import governance tools from the existing codebase
try:
    sys.path.insert(0, REPO_ROOT)
    from _daemon_tools_schema import (
        MethodologyRegistry as _MethodologyRegistry,
        classify_path,
        GovernanceMode,
        GovernanceHardStop,
        verify_artifact,
        adversarial_verify,
        run_post_output_verification,
        build_mixin_module,
        detect_needed_imports,
        reconstruct_from_removal_diff,
        DaemonCommitChain,
        GovernanceLog,
        daemon_identity_config_path,
        load_daemon_agent_id,
        write_chain_junction_config,
    )
    _HAS_GOVERNANCE = True
except ImportError:
    _HAS_GOVERNANCE = False
    # Fallback stubs
    class GovernanceMode(Enum):
        READ_ONLY = "read_only"
        PROPOSE_ONLY = "propose_only"
        AUTONOMOUS = "autonomous"
    def classify_path(path): return GovernanceMode.PROPOSE_ONLY
    def verify_artifact(path, shape): return {"ok": True, "failures": []}
    def adversarial_verify(*a, **kw): return {"ok": True, "failures": []}

# Try to import bridge modules
try:
    from bridge.vapi_bridge.config import VapiBridgeConfig as BridgeConfig
    _HAS_BRIDGE_CONFIG = True
except ImportError:
    _HAS_BRIDGE_CONFIG = False

# ═══════════════════════════════════════════════════════════════════════════════
#  METHODOLOGY REGISTRY (persistent learning)
# ═══════════════════════════════════════════════════════════════════════════════

class MethodologyRegistry:
    """JSON-backed registry of lessons learned, keyed by failure class.
    Grows with every session. Never repeats the same mistake twice."""

    _SEED_METHODOLOGY = {
        "VERBATIM_RELOCATION": {
            "anti_pattern": "Rewriting a moved method by hand instead of using the removal diff as the canonical source",
            "correct_pattern": "Use extract_with_diff to reconstruct the exact removed lines from the diff. The diff is the source of truth.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "FROZEN_SURFACE_TOUCH": {
            "anti_pattern": "Editing a FROZEN file (_core.py, operator_api, etc.) without a governance proposal",
            "correct_pattern": "Use propose_edit to generate a .diff proposal. The proposal is reviewed before the operator applies it via git apply.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "MIXIN_MISSING_IMPORTS": {
            "anti_pattern": "Assuming a moved method's imports carry over from the source module",
            "correct_pattern": "Call detect_needed_imports() to auto-inject imports. Integration test must execute a method, not just import the class.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "HALLUCINATED_COMPLETION": {
            "anti_pattern": "Marking a task as DONE without running verify_artifact on the output",
            "correct_pattern": "Always run run_post_output_verification after output-producing tools. Verify artifact hash, not just existence.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "LARGE_FILE_WRITE": {
            "anti_pattern": "Writing a large file (+2000 lines) in one write call — causes timeout or truncation",
            "correct_pattern": "Use write_file for small files. For large files, write in chunks or use shell to write via subprocess.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "CHAIN_JUNCTION": {
            "anti_pattern": "Writing chain junction config without recording the provisional last commitment",
            "correct_pattern": "Record the provisional chain's last commitment hash before writing the canonical junction config. The junction is a ceremony, not a config edit.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "HARDWARE_GROUND_TRUTH": {
            "anti_pattern": "Assuming the DualShock is always connected and responding at 1000 Hz",
            "correct_pattern": "Check hardware state before every session. Use the hardware watcher to verify connection. Fall back to recorded data if hardware is unavailable.",
            "agent_commit": "seed",
            "discovered": "2026-06-16",
        },
        "RATE_LIMITER_BURST": {
            "anti_pattern": "Setting burst window too short (1s) causes false rate limiting on valid traffic",
            "correct_pattern": "Use 10/min burst, 100/hr sustained, with configurable burst window. Default window is 5s.",
            "agent_commit": "seed",
            "discovered": "2026-07-26",
        },
    }

    _TASK_KEYWORD_MAP = {
        "VERBATIM_RELOCATION": ("extract", "mixin", "relocate", "verbatim", "diff-oracle", "decon"),
        "FROZEN_SURFACE_TOUCH": ("propose_edit", "frozen", "propose", "_core.py", "operator_api", "governed"),
        "MIXIN_MISSING_IMPORTS": ("mixin", "import", "nameerror", "pytest"),
        "HALLUCINATED_COMPLETION": ("ready", "finalize", "verify", "complete", "done"),
        "LARGE_FILE_WRITE": ("write_file", "large", "timeout"),
        "CHAIN_JUNCTION": ("roster", "agent_id", "junction", "canonical", "on-chain"),
        "HARDWARE_GROUND_TRUTH": ("firmware", "flash", "silicon", "separation ratio", "hardware"),
        "RATE_LIMITER_BURST": ("rate limit", "burst", "token bucket", "throttle"),
    }

    def __init__(self, path: str = METHODOLOGY_PATH):
        self._path = path
        if not os.path.isfile(path):
            self._write(self._SEED_METHODOLOGY)

    def _write(self, data: dict):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def all(self) -> dict:
        try:
            return json.load(open(self._path, encoding="utf-8"))
        except Exception:
            return dict(self._SEED_METHODOLOGY)

    def query(self, keywords: str = "") -> dict:
        data = self.all()
        if not keywords:
            return data
        kws = [k.strip().lower() for k in keywords.replace(",", " ").split() if k.strip()]
        out = {}
        for cls, entry in data.items():
            hay = (cls + " " + entry.get("anti_pattern", "") + " " + entry.get("correct_pattern", "")).lower()
            if any(k in hay for k in kws):
                out[cls] = entry
        return out

    def query_for_task(self, task_description: str) -> dict:
        """Match methodology entries to a task description by failure-class keywords."""
        data = self.all()
        hay = task_description.lower()
        out = {}
        for cls, keywords in self._TASK_KEYWORD_MAP.items():
            if cls not in data:
                continue
            if any(kw in hay for kw in keywords):
                out[cls] = data[cls]
        # Always include core entries
        for fallback in ("VERBATIM_RELOCATION", "HALLUCINATED_COMPLETION", "FROZEN_SURFACE_TOUCH"):
            if fallback in data and fallback not in out:
                out[fallback] = data[fallback]
        return out

    @staticmethod
    def format_for_prompt(entries: dict) -> str:
        if not entries:
            return "(no matching methodology entries)"
        lines = []
        for cls, e in entries.items():
            ac = e.get("agent_commit", "?")
            lines.append(f"- **[{cls}]** (discovered {e.get('discovered', '?')}; commit `{ac}`)")
            lines.append(f"  - AVOID: {e.get('anti_pattern', '')[:240]}")
            lines.append(f"  - DO: {e.get('correct_pattern', '')[:240]}")
        return "\n".join(lines)

    def add(self, failure_class: str, anti_pattern: str, correct_pattern: str,
            agent_commit: str = "", discovered: str = "") -> bool:
        data = self.all()
        data[failure_class] = {
            "anti_pattern": anti_pattern,
            "correct_pattern": correct_pattern,
            "agent_commit": agent_commit or self._get_head_commit(),
            "discovered": discovered or time.strftime("%Y-%m-%d", time.gmtime()),
        }
        self._write(data)
        return True

    def count(self) -> int:
        return len(self.all())

    def _get_head_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, cwd=REPO_ROOT, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION HISTORY (SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

class SessionHistory:
    """Persistent session history across tool restarts. Each session is a
    conversation thread with the LLM, including tool calls and results."""

    def __init__(self, db_path: str = SESSION_DB_PATH):
        self._db_path = db_path
        self._init_db()
        self._session_id = self._create_session()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT PRIMARY KEY,
                    created_at  TEXT NOT NULL,
                    ended_at    TEXT,
                    model       TEXT NOT NULL DEFAULT 'unknown',
                    message_count INTEGER DEFAULT 0,
                    summary     TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL REFERENCES sessions(id),
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    tool_calls  TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL REFERENCES sessions(id),
                    title       TEXT NOT NULL,
                    context     TEXT,
                    decision    TEXT NOT NULL,
                    alternatives TEXT,
                    reasoning   TEXT,
                    outcome     TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_session
                    ON decisions(session_id);
            """)

    def _create_session(self) -> str:
        sid = uuid.uuid4().hex[:12]
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, created_at, model) VALUES (?, ?, ?)",
                (sid, datetime.datetime.utcnow().isoformat(), QUICKSILVER_MODEL)
            )
        return sid

    @property
    def session_id(self) -> str:
        return self._session_id

    def add_message(self, role: str, content: str, tool_calls: Optional[list] = None,
                    backend: str = "") -> int:
        with self._get_conn() as conn:
            try:
                conn.execute("ALTER TABLE messages ADD COLUMN backend TEXT DEFAULT ''")
            except Exception:
                pass
            cur = conn.execute(
                """INSERT INTO messages (session_id, role, content, tool_calls, backend)
                   VALUES (?, ?, ?, ?, ?)""",
                (self._session_id, role, content,
                 json.dumps(tool_calls) if tool_calls else None,
                 backend)
            )
            conn.execute(
                "UPDATE sessions SET message_count = message_count + 1 WHERE id = ?",
                (self._session_id,)
            )
            return cur.lastrowid

    def get_recent_messages(self, limit: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT role, content, tool_calls, created_at
                   FROM messages WHERE session_id = ?
                   ORDER BY id ASC LIMIT ?""",
                (self._session_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_last_session_summary(self) -> Optional[str]:
        """Get the most recent completed session's summary."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT summary, created_at, model, message_count
                   FROM sessions WHERE id != ? AND summary IS NOT NULL
                   ORDER BY created_at DESC LIMIT 1""",
                (self._session_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_sessions(self, limit: int = 20) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, created_at, ended_at, model, message_count, summary
                   FROM sessions ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def end_session(self, summary: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE sessions SET ended_at = ?, summary = ?
                   WHERE id = ?""",
                (datetime.datetime.utcnow().isoformat(), summary, self._session_id)
            )

    def add_decision(self, title: str, decision: str, context: str = "",
                     alternatives: str = "", reasoning: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO decisions (session_id, title, context, decision,
                   alternatives, reasoning) VALUES (?, ?, ?, ?, ?, ?)""",
                (self._session_id, title, context, decision, alternatives, reasoning)
            )
            return cur.lastrowid

    def get_decisions(self, limit: int = 20) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT title, context, decision, alternatives, reasoning,
                          outcome, created_at
                   FROM decisions WHERE session_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (self._session_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_decisions(self, limit: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT title, context, decision, alternatives, reasoning,
                          outcome, created_at
                   FROM decisions ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  QUICKSILVER PRO LLM CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class QuickSilverClient:
    """Client for QuickSilver Pro API. Model-agnostic — swap models freely."""

    def __init__(self, api_key: str = QUICKSILVER_API_KEY,
                 model: str = QUICKSILVER_MODEL):
        self.api_key = api_key
        self.model = model
        self.api_url = QUICKSILVER_API_URL
        self._session = None

    def _import_requests(self):
        """Lazy import to avoid dependency on unavailable packages."""
        try:
            import requests
            return requests
        except ImportError:
            raise ImportError(
                "requests not installed. Run: pip install requests"
            )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None,
             temperature: float = 0.7, max_tokens: int = 4096) -> dict:
        """Send a chat completion request to QuickSilver Pro."""
        if not self.configured:
            return {
                "error": "QUICKSILVER_API_KEY not configured",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": (
                            "I cannot process this request because the "
                            "QUICKSILVER_API_KEY is not configured.\n\n"
                            "Set it in your environment or .env file:\n"
                            "  QUICKSILVER_API_KEY=sk-..."
                        )
                    }
                }]
            }

        requests = self._import_requests()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": f"QorTroller/{VERSION}",
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            return {"error": "LLM request timed out after 120s"}
        except requests.exceptions.RequestException as e:
            return {"error": f"LLM request failed: {e}"}

    def ping(self) -> dict:
        """Test connectivity to QuickSilver Pro."""
        if not self.configured:
            return {"ok": False, "error": "API key not configured"}
        requests = self._import_requests()
        try:
            resp = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 10,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return {"ok": True, "model": self.model}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  BRIDGE CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class BridgeClient:
    """HTTP client for the QorTroller bridge operator API."""

    def __init__(self, base_url: str = BRIDGE_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _import_requests(self):
        try:
            import requests
            return requests
        except ImportError:
            raise ImportError("requests not installed")

    def health(self) -> dict:
        requests = self._import_requests()
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            data["status"] = "healthy"
            data["latency_s"] = resp.elapsed.total_seconds()
            return data
        except Exception as e:
            return {"status": "unreachable", "error": str(e), "latency_s": None}

    def get(self, path: str, timeout: float = 10) -> Optional[dict]:
        requests = self._import_requests()
        try:
            resp = requests.get(f"{self.base_url}{path}", timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def post(self, path: str, data: dict = None, timeout: float = 30) -> Optional[dict]:
        requests = self._import_requests()
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                json=data or {},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def is_up(self) -> bool:
        h = self.health()
        return h.get("status") == "healthy"

    def get_agent_statuses(self) -> list[dict]:
        """Get status of all bridge agents."""
        data = self.get("/agent/statuses", timeout=10)
        if data and isinstance(data, list):
            return data
        # Try alternative endpoint
        data = self.get("/agents", timeout=10)
        if data and isinstance(data, list):
            return data
        return []

    def get_contradictions(self) -> list[dict]:
        """Get current FSCA contradictions."""
        data = self.get("/agent/contradictions", timeout=10)
        if data and isinstance(data, list):
            return data
        data = self.get("/fsca/contradictions", timeout=10)
        if data and isinstance(data, list):
            return data
        return []

    def get_separation_status(self) -> Optional[dict]:
        return self.get("/agent/separation-defensibility-status", timeout=10)

    def get_tournament_eligibility(self) -> Optional[dict]:
        return self.get("/agent/tournament-eligibility", timeout=10)

    def get_protocol_state(self) -> dict:
        """Aggregate protocol state from multiple bridge endpoints."""
        return {
            "health": self.health(),
            "agents": self.get_agent_statuses(),
            "contradictions": self.get_contradictions(),
            "separation": self.get_separation_status(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ToolEngine:
    """All engineering tools available to the LLM. Each tool is a function
    that takes args and returns a string result."""

    def __init__(self, repo_root: str = REPO_ROOT,
                 bridge: Optional[BridgeClient] = None):
        self.repo_root = repo_root
        self.bridge = bridge or BridgeClient()
        self._tools_definition = self._build_tools_definition()

    def _build_tools_definition(self) -> list[dict]:
        """Build the OpenAI-compatible tool definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file's contents. For large files, use read_file_range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path from repo root"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file_range",
                    "description": "Paginated read of large files. Returns numbered lines (1-indexed).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "offset": {"type": "integer", "description": "0-indexed line number to start"},
                            "limit": {"type": "integer", "description": "Number of lines (default 500, max 2000)"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file. Creates parent directories if needed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit a file by finding and replacing text. The before text must match exactly.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "before": {"type": "string"},
                            "after": {"type": "string"}
                        },
                        "required": ["path", "before", "after"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "Execute a shell command. For git, pytest, and system operations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout_secs": {"type": "integer", "default": 30}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_pytest",
                    "description": "Run pytest on a test path. Returns exit code, summary, and failures.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "test_path": {"type": "string", "default": "bridge/tests/"},
                            "timeout": {"type": "integer", "default": 120},
                            "extra_args": {"type": "string", "default": ""}
                        },
                        "required": ["test_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_log",
                    "description": "Show recent git log.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "n": {"type": "integer", "default": 10}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "Show git diff (unstaged changes).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": ""}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Show git status.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Stage all and commit with a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"}
                        },
                        "required": ["message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bridge_health",
                    "description": "Check if the bridge is running and healthy.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bridge_get",
                    "description": "GET a bridge API endpoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "timeout": {"type": "integer", "default": 10}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bridge_post",
                    "description": "POST to a bridge API endpoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "data": {"type": "object", "default": {}},
                            "timeout": {"type": "integer", "default": 30}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "methodology_query",
                    "description": "Query the methodology registry for lessons learned.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "string", "default": ""}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "methodology_add",
                    "description": "Add a new lesson to the methodology registry.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "failure_class": {"type": "string"},
                            "anti_pattern": {"type": "string"},
                            "correct_pattern": {"type": "string"},
                            "agent_commit": {"type": "string", "default": ""}
                        },
                        "required": ["failure_class", "anti_pattern", "correct_pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for files matching a pattern.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "default": "."}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "grep",
                    "description": "Search for text in files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "default": "."},
                            "include": {"type": "string", "default": "*.py"}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_invariants",
                    "description": "Check PV-CI invariants against the codebase.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus": {"type": "string", "default": ""}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_contradictions",
                    "description": "Check for FSCA contradictions from the bridge.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "protocol_state",
                    "description": "Get the current protocol state from the bridge.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tree",
                    "description": "List directory tree with file sizes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": "."},
                            "depth": {"type": "integer", "default": 2}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "hardware_status",
                    "description": "Check current hardware state (DualShock, capture card, bridge).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
        ]

    @property
    def tool_definitions(self) -> list[dict]:
        return self._tools_definition

    def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name with given args."""
        handler = self._get_handler(name)
        if handler is None:
            return f"Error: unknown tool '{name}'"
        try:
            result = handler(**args)
            return str(result) if result is not None else "(no output)"
        except Exception as e:
            return f"Error executing {name}: {e}"

    def _get_handler(self, name: str) -> Optional[Callable]:
        handlers = {
            "read_file": self._read_file,
            "read_file_range": self._read_file_range,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "shell": self._shell,
            "run_pytest": self._run_pytest,
            "git_log": self._git_log,
            "git_diff": self._git_diff,
            "git_status": self._git_status,
            "git_commit": self._git_commit,
            "bridge_health": self._bridge_health,
            "bridge_get": self._bridge_get,
            "bridge_post": self._bridge_post,
            "methodology_query": self._methodology_query,
            "methodology_add": self._methodology_add,
            "search_files": self._search_files,
            "grep": self._grep,
            "check_invariants": self._check_invariants,
            "check_contradictions": self._check_contradictions,
            "protocol_state": self._protocol_state,
            "tree": self._tree,
            "hardware_status": self._hardware_status,
        }
        return handlers.get(name)

    def _resolve_path(self, path: str) -> str:
        """Resolve a relative path against the repo root."""
        return os.path.normpath(os.path.join(self.repo_root, path))

    def _read_file(self, path: str) -> str:
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"Error: file not found: {path}"
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if len(content) > 12000:
                return f"(File is {len(content)} bytes — showing first 12000)\n{content[:12000]}"
            return content
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _read_file_range(self, path: str, offset: int = 0, limit: int = 500) -> str:
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"Error: file not found: {path}"
        limit = min(limit, 2000)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            selected = lines[offset:offset + limit]
            result = "".join(
                f"{i + offset + 1:>6}: {l}"
                for i, l in enumerate(selected)
            )
            total = len(lines)
            end = offset + len(selected)
            return f"{path} lines {offset + 1}–{end} of {total}\n{result}"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _write_file(self, path: str, content: str) -> str:
        full = self._resolve_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        try:
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            # Verify
            if os.path.isfile(full):
                actual = os.path.getsize(full)
                return f"OK: wrote {path} ({actual} bytes)"
            return f"Error: write reported success but file not found: {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def _edit_file(self, path: str, before: str, after: str) -> str:
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"Error: file not found: {path}"
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            count = content.count(before)
            if count == 0:
                return f"Error: pattern not found in {path}"
            if count > 1:
                return f"Error: pattern found {count} times in {path} — must be unique"
            new_content = content.replace(before, after, 1)
            with open(full, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"OK: edited {path} (1 replacement)"
        except Exception as e:
            return f"Error editing {path}: {e}"

    def _shell(self, command: str, timeout_secs: int = 30) -> str:
        try:
            argv = shlex.split(command)
            result = subprocess.run(
                argv,
                shell=False, capture_output=True, text=True,
                cwd=self.repo_root, timeout=timeout_secs,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n--- stderr ---\n"
                output += result.stderr
            if result.returncode != 0:
                output = f"Exit code: {result.returncode}\n{output}"
            return output[:10000] if len(output) > 10000 else output
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout_secs}s"
        except Exception as e:
            return f"Error: {e}"

    def _run_pytest(self, test_path: str = "bridge/tests/",
                    timeout: int = 120, extra_args: str = "") -> str:
        cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short", "--no-header"]
        if extra_args:
            cmd.extend(shlex.split(extra_args))
        try:
            result = subprocess.run(
                cmd, shell=False, capture_output=True, text=True,
                cwd=self.repo_root, timeout=timeout,
            )
            output = result.stdout or result.stderr
            # Summarize
            lines = output.splitlines()
            fail_lines = [l for l in lines if "FAILED" in l]
            pass_lines = [l for l in lines if "PASSED" in l]
            summary = [l for l in lines if "passed" in l or "failed" in l]
            summary_text = "\n".join(summary[:5]) if summary else ""
            fail_text = "\n".join(fail_lines[:10]) if fail_lines else ""
            pass_count = len([l for l in lines if "PASSED" in l])
            fail_count = len(fail_lines)

            msg = f"Exit: {result.returncode} | {pass_count} passed, {fail_count} failed"
            if summary_text:
                msg += f"\n{summary_text}"
            if fail_text:
                msg += f"\n\nFailures:\n{fail_text}"
            return msg
        except subprocess.TimeoutExpired:
            return f"Error: pytest timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    def _git_log(self, n: int = 10) -> str:
        return self._shell(f"git log --oneline -{n}", 10)

    def _git_diff(self, path: str = "") -> str:
        return self._shell(f"git diff {'-- ' + path if path else ''}", 10)

    def _git_status(self) -> str:
        return self._shell("git status --short", 10)

    def _git_commit(self, message: str) -> str:
        result = self._shell("git add -A", 10)
        return self._shell(f'git commit -m "{message}"', 10)

    def _bridge_health(self) -> str:
        h = self.bridge.health()
        return json.dumps(h, indent=2, default=str)

    def _bridge_get(self, path: str, timeout: int = 10) -> str:
        result = self.bridge.get(path, timeout)
        if result is None:
            return f"Error: bridge GET {path} failed"
        return json.dumps(result, indent=2, default=str)

    def _bridge_post(self, path: str, data: dict = None, timeout: int = 30) -> str:
        result = self.bridge.post(path, data or {}, timeout)
        if result is None:
            return f"Error: bridge POST {path} failed"
        return json.dumps(result, indent=2, default=str)

    def _methodology_query(self, keywords: str = "") -> str:
        entries = self._methodology_registry.query(keywords)
        return MethodologyRegistry.format_for_prompt(entries)

    def _methodology_add(self, failure_class: str, anti_pattern: str,
                         correct_pattern: str, agent_commit: str = "") -> str:
        self._methodology_registry.add(
            failure_class, anti_pattern, correct_pattern, agent_commit
        )
        return f"OK: added methodology entry [{failure_class}]"

    def _search_files(self, pattern: str, path: str = ".") -> str:
        full = self._resolve_path(path)
        if not os.path.isdir(full):
            return f"Error: directory not found: {path}"
        matches = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                if pattern in f or pattern in os.path.join(root, f):
                    rel = os.path.relpath(os.path.join(root, f), self.repo_root)
                    matches.append(rel)
        if not matches:
            return f"No files matching '{pattern}'"
        return "\n".join(matches[:100])

    def _grep(self, pattern: str, path: str = ".", include: str = "*.py") -> str:
        full = self._resolve_path(path)
        if not os.path.isdir(full):
            return f"Error: directory not found: {path}"
        matches = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules"]
            for f in files:
                if not f.endswith(include.replace("*", "")) if "*" in include else True:
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        for i, line in enumerate(fh, 1):
                            if pattern in line:
                                rel = os.path.relpath(fpath, self.repo_root)
                                matches.append(f"{rel}:{i}: {line.rstrip()[:200]}")
                except Exception:
                    continue
        if not matches:
            return f"No matches for '{pattern}'"
        return "\n".join(matches[:100])

    def _check_invariants(self, focus: str = "") -> str:
        """Check PV-CI invariants. Attempts to import and run the self-test."""
        if _HAS_GOVERNANCE:
            try:
                from _daemon_tools_schema import governance_self_test
                result = governance_self_test()
                return json.dumps(result, indent=2, default=str)
            except Exception as e:
                return f"Error running invariant check: {e}"
        return "Invariant check not available (governance module not imported)"

    def _check_contradictions(self) -> str:
        """Check FSCA contradictions from the bridge."""
        contradictions = self.bridge.get_contradictions()
        if not contradictions:
            return "No contradictions detected (bridge may be unreachable)"
        return json.dumps(contradictions, indent=2, default=str)

    def _protocol_state(self) -> str:
        state = self.bridge.get_protocol_state()
        return json.dumps(state, indent=2, default=str)

    def _tree(self, path: str = ".", depth: int = 2) -> str:
        full = self._resolve_path(path)
        if not os.path.isdir(full):
            return f"Error: directory not found: {path}"
        result = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules"]
            rel = os.path.relpath(root, self.repo_root)
            level = rel.count(os.sep) if rel != "." else 0
            if level > depth:
                dirs.clear()
                continue
            indent = "  " * level
            result.append(f"{indent}{os.path.basename(root) or '.'}/")
            subindent = "  " * (level + 1)
            for f in files:
                if f.endswith(".pyc"):
                    continue
                fpath = os.path.join(root, f)
                try:
                    size = os.path.getsize(fpath)
                    result.append(f"{subindent}{f} ({size:,} bytes)")
                except Exception:
                    result.append(f"{subindent}{f}")
        return "\n".join(result[:200])

    def _hardware_status(self) -> str:
        """Stub — returns a placeholder. Real hardware detection is in the watcher."""
        return (
            "Hardware status depends on the Hardware Watcher thread.\n"
            "Run the tool in TUI mode to see live hardware state.\n"
            "Or check: hardware_watcher.last_state"
        )

    methodology_registry: MethodologyRegistry = None


# ═══════════════════════════════════════════════════════════════════════════════
#  HARDWARE WATCHER (background thread)
# ═══════════════════════════════════════════════════════════════════════════════

class HardwareState(Enum):
    IDLE = "idle"
    DUALSHOCK_DETECTED = "dualshock_detected"
    CAPTURE_DETECTED = "capture_detected"
    BRIDGE_UP = "bridge_up"
    ALL_READY = "all_ready"
    MONITORING = "monitoring"
    PAUSED = "paused"

class HardwareWatcher:
    """Background thread that polls for hardware state changes.
    Detects DualShock Edge, capture card, and bridge health."""

    def __init__(self, bridge: Optional[BridgeClient] = None,
                 on_state_change: Optional[Callable] = None):
        self.bridge = bridge or BridgeClient()
        self.on_state_change = on_state_change
        self.state = HardwareState.IDLE
        self.last_state = {
            "dualshock": False,
            "capture_card": False,
            "bridge": False,
            "state": "idle",
            "timestamp": None,
            "dualshock_info": {},
            "capture_info": {},
        }
        self._running = False
        self._task = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        return self._task

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self):
        """Poll hardware state every 2 seconds."""
        while self._running:
            try:
                await self._poll()
            except Exception as e:
                pass  # Logged internally
            await asyncio.sleep(2)

    def _detect_dualshock(self) -> tuple[bool, dict]:
        """Detect DualShock Edge / DS4 controller via USB HID.
        Uses pywinusb or hidapi — falls back to checking if DualShockTransport
        process is running on the bridge."""
        info = {}
        # Method 1: Check bridge for active DualShock session
        try:
            h = self.bridge.get("/dualshock/status", timeout=3)
            if h and isinstance(h, dict):
                connected = h.get("connected", False) or h.get("status") == "active"
                if connected:
                    info = h
                    return True, info
        except Exception:
            pass

        # Method 2: Try to enumerate HID devices via pywinusb
        try:
            import pywinusb.hid as hid
            all_devices = hid.HidDeviceFilter().get_devices()
            for dev in all_devices:
                vid = dev.vendor_id
                pid = dev.product_id
                # DualShock 4 v1: 0x054C:0x05C4
                # DualShock 4 v2: 0x054C:0x09CC
                # DualSense: 0x054C:0x0CE6
                # DualSense Edge: 0x054C:0x0DF2
                if vid == 0x054C and pid in (0x05C4, 0x09CC, 0x0CE6, 0x0DF2):
                    info = {"vid": hex(vid), "pid": hex(pid), "product": dev.product_name or "Unknown"}
                    return True, info
        except ImportError:
            pass

        # Method 3: Try hidapi
        try:
            import hid
            for pid in (0x05C4, 0x09CC, 0x0CE6, 0x0DF2):
                try:
                    dev = hid.enumerate(0x054C, pid)
                    if dev:
                        info = {"vid": hex(0x054C), "pid": hex(pid), "product": dev[0].get("product_string", "Unknown")}
                        return True, info
                except Exception:
                    continue
        except ImportError:
            pass

        return False, info

    def _detect_capture_card(self) -> tuple[bool, dict]:
        """Detect capture card without flashing cameras.
        Uses bridge first, then falls back to non-invasive DirectShow enumeration."""
        info = {}

        # Method 1: Check via bridge if Retina is active (no camera flash)
        try:
            h = self.bridge.get("/retina/status", timeout=3)
            if h and isinstance(h, dict):
                if h.get("capture_active") or h.get("status") == "active":
                    info = h
                    return True, info
        except Exception:
            pass

        # Method 2: Non-invasive device enumeration via DirectShow (pygrabber)
        # This lists devices without opening them (no camera flash)
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            devices = graph.get_input_devices()
            for i, name in enumerate(devices):
                # Skip internal webcams at index 0 — only flag external capture cards
                if i > 0 and name.lower() not in ("", "integrated camera", "integrated webcam", "built-in"):
                    info = {"index": i, "name": name}
                    return True, info
            return False, {"devices": devices}
        except ImportError:
            pass

        # Method 3: Quick OpenCV check (skip index 0 to avoid flashing the built-in camera)
        try:
            import cv2
            # Only check external indices (1-4) — never open index 0 (internal webcam)
            for i in range(1, 5):
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        info = {"index": i, "backend": "DirectShow"}
                        cap.release()
                        return True, info
                except Exception:
                    continue
        except ImportError:
            pass

        return False, info

    async def _poll(self):
        """Single poll cycle."""
        dualshock, ds_info = await asyncio.get_event_loop().run_in_executor(
            None, self._detect_dualshock
        )
        capture, cap_info = await asyncio.get_event_loop().run_in_executor(
            None, self._detect_capture_card
        )
        bridge = self.bridge.is_up()

        old_state = self.state
        self.last_state = {
            "dualshock": dualshock,
            "capture_card": capture,
            "bridge": bridge,
            "dualshock_info": ds_info,
            "capture_info": cap_info,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        # State machine
        if dualshock and capture and bridge:
            new_state = HardwareState.ALL_READY
        elif dualshock and capture:
            new_state = HardwareState.CAPTURE_DETECTED
        elif dualshock:
            new_state = HardwareState.DUALSHOCK_DETECTED
        elif bridge:
            new_state = HardwareState.BRIDGE_UP
        else:
            new_state = HardwareState.IDLE

        self.state = new_state
        self.last_state["state"] = new_state.value

        if new_state != old_state and self.on_state_change:
            await self.on_state_change(new_state)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONTRADICTION ORACLE
# ═══════════════════════════════════════════════════════════════════════════════

class ContradictionOracle:
    """Real-time contradiction detection. Checks FSCA rules before actions."""

    def __init__(self, bridge: Optional[BridgeClient] = None):
        self.bridge = bridge or BridgeClient()
        self._cached_contradictions: list[dict] = []
        self._last_check: Optional[float] = None

    async def refresh(self):
        """Fetch latest contradictions from the bridge."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.bridge.get_contradictions
            )
            if result:
                self._cached_contradictions = result
            self._last_check = time.time()
        except Exception:
            pass

    def check(self, action_description: str) -> list[dict]:
        """Check if an action would violate any contradiction rules.
        Returns list of relevant contradictions."""
        violations = []
        action_lower = action_description.lower()
        for c in self._cached_contradictions:
            rule_name = (c.get("rule") or c.get("name") or "").lower()
            rule_desc = (c.get("description") or c.get("message") or "").lower()
            severity = c.get("severity", "medium").lower()

            # Check if action touches the rule's domain
            if any(kw in action_lower for kw in [rule_name, rule_desc]):
                violations.append({
                    "rule": c.get("rule") or c.get("name", "unknown"),
                    "severity": severity,
                    "description": c.get("description") or c.get("message", ""),
                    "action": action_description,
                })

        return violations

    @property
    def active_contradictions(self) -> list[dict]:
        return self._cached_contradictions

    @property
    def contradiction_count(self) -> int:
        return len(self._cached_contradictions)


# ═══════════════════════════════════════════════════════════════════════════════
#  INVARIANT SENTINEL
# ═══════════════════════════════════════════════════════════════════════════════

class InvariantSentinel:
    """Background invariant checker. Checks 188 PV-CI invariants continuously."""

    def __init__(self):
        self._last_results: dict = {}
        self._last_check: Optional[float] = None
        self._check_count = 0

    async def check(self) -> dict:
        """Run invariant self-test. Returns dict with ok/failures/count."""
        if _HAS_GOVERNANCE:
            try:
                from _daemon_tools_schema import governance_self_test
                results = await asyncio.get_event_loop().run_in_executor(
                    None, governance_self_test
                )
                # Normalize: ensure it's a dict
                if isinstance(results, str):
                    results = {"ok": len(results) == 0, "failures": [results] if results else [], "count": 0}
                elif not isinstance(results, dict):
                    results = {"ok": bool(results), "failures": [], "count": 0}
                self._last_results = results
                self._last_check = time.time()
                self._check_count += 1
                return results
            except Exception as e:
                return {"ok": False, "failures": [str(e)], "count": 0}
        return {"ok": True, "failures": [], "count": 0}

    @property
    def summary(self) -> str:
        if not self._last_results:
            return "Invariants not yet checked"
        total = self._last_results.get("count", 0)
        failures = self._last_results.get("failures", [])
        if not failures:
            return f"✅ {total} invariants passed"
        return f"⚠️ {len(failures)}/{total} invariants FAILED"


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTONOMOUS DEBUG LOOP
# ═══════════════════════════════════════════════════════════════════════════════

class AutonomousDebugLoop:
    """Full debug cycle: detect failure → read traceback → search methodology
    → generate hypothesis → propose fix → apply fix → re-run → learn."""

    def __init__(self, tools: ToolEngine, methodology: MethodologyRegistry):
        self.tools = tools
        self.methodology = methodology

    def analyze_test_failure(self, test_output: str) -> dict:
        """Analyze test output to extract failure class, traceback, and hint."""
        analysis = {
            "failure_class": "UNKNOWN",
            "traceback": "",
            "file": "",
            "line": 0,
            "error_message": "",
            "hint": "",
        }

        # Extract FAILED lines
        for line in test_output.splitlines():
            if "FAILED" in line:
                analysis["failure_class"] = "TEST_FAILURE"
                # Extract file path
                parts = line.split("FAILED")[-1].strip()
                if "::" in parts:
                    analysis["file"] = parts.split("::")[0]
                else:
                    analysis["file"] = parts

        # Extract traceback
        tb_lines = []
        in_tb = False
        for line in test_output.splitlines():
            if "Traceback (most recent call last)" in line:
                in_tb = True
            if in_tb:
                tb_lines.append(line)
                if "Error:" in line or "Exception:" in line or "AssertionError" in line:
                    analysis["error_message"] = line.strip()
                    in_tb = False
        analysis["traceback"] = "\n".join(tb_lines[-20:])

        # Classify failure
        error_msg = analysis["error_message"].lower()
        if "assert" in error_msg:
            analysis["failure_class"] = "ASSERTION_FAILURE"
            analysis["hint"] = "An assertion failed. Check the expected vs actual values."
        elif "import" in error_msg and "error" in error_msg:
            analysis["failure_class"] = "IMPORT_ERROR"
            analysis["hint"] = "Missing or circular import. Check the import chain."
        elif "name" in error_msg and "not defined" in error_msg:
            analysis["failure_class"] = "MIXIN_MISSING_IMPORTS"
            analysis["hint"] = "A moved method lost its import scope. Use detect_needed_imports()."
        elif "timeout" in error_msg:
            analysis["failure_class"] = "TIMEOUT"
            analysis["hint"] = "Operation timed out. Increase timeout or optimize."
        elif "attribute" in error_msg:
            analysis["failure_class"] = "MISSING_ATTRIBUTE"
            analysis["hint"] = "Missing attribute. Check that the object has the expected interface."

        # Check methodology
        meth = self.methodology.query(analysis["failure_class"])
        if meth:
            entries = MethodologyRegistry.format_for_prompt(meth)
            analysis["methodology"] = entries

        return analysis

    def suggest_fix(self, analysis: dict) -> str:
        """Generate a fix suggestion based on failure analysis."""
        fc = analysis["failure_class"]
        file = analysis["file"]
        msg = analysis["error_message"]

        if fc == "MIXIN_MISSING_IMPORTS":
            return (
                f"Fix for {file}: The moved method lost its import scope.\n"
                f"1. Find the removal diff\n"
                f"2. Call detect_needed_imports() with the source module\n"
                f"3. Inject the detected imports into the new module"
            )
        elif fc == "ASSERTION_FAILURE":
            return (
                f"Fix for {file}: Assertion failed.\n"
                f"Error: {msg}\n"
                f"1. Read the test to understand the expected behavior\n"
                f"2. Read the source to understand the actual behavior\n"
                f"3. Fix the mismatch"
            )
        elif fc == "IMPORT_ERROR":
            return (
                f"Fix for {file}: Import error.\n"
                f"Error: {msg}\n"
                f"1. Check that the module exists in the correct path\n"
                f"2. Check for circular imports\n"
                f"3. Check for missing dependencies"
            )
        else:
            return (
                f"Fix for {file}:\n"
                f"Error: {msg}\n"
                f"1. Read the traceback\n"
                f"2. Read the relevant source\n"
                f"3. Form a hypothesis\n"
                f"4. Apply the fix\n"
                f"5. Re-run the tests"
            )


# ═══════════════════════════════════════════════════════════════════════════════
#  PROTOCOL STATE VISUALIZER (data model)
# ═══════════════════════════════════════════════════════════════════════════════

class ProtocolState:
    """Live state of the QorTroller protocol. Consumed by the TUI."""

    def __init__(self, bridge: Optional[BridgeClient] = None):
        self.bridge = bridge or BridgeClient()
        self.data = {}

    async def refresh(self):
        """Fetch latest state from the bridge."""
        try:
            state = await asyncio.get_event_loop().run_in_executor(
                None, self.bridge.get_protocol_state
            )
            self.data = state
        except Exception:
            pass

    @property
    def bridge_health(self) -> str:
        h = self.data.get("health", {})
        return h.get("status", "unknown")

    @property
    def agent_count(self) -> int:
        agents = self.data.get("agents", [])
        if isinstance(agents, list):
            return len(agents)
        return 0

    @property
    def healthy_agents(self) -> int:
        agents = self.data.get("agents", [])
        if isinstance(agents, list):
            return sum(1 for a in agents if a.get("status") == "healthy")
        return 0

    @property
    def contradiction_count(self) -> int:
        return len(self.data.get("contradictions", []))

    @property
    def separation_ratio(self) -> Optional[float]:
        sep = self.data.get("separation", {})
        return sep.get("ratio") or sep.get("separation_ratio")


# ═══════════════════════════════════════════════════════════════════════════════
#  CEREMONY BOT
# ═══════════════════════════════════════════════════════════════════════════════

class CeremonyBot:
    """Manages triple-gate ceremonies for on-chain actions.
    Generates ceremony scripts, walks the operator through steps,
    verifies each step, and logs to the audit trail."""

    CEREMONY_TEMPLATES = {
        "vhp_mint": {
            "title": "VHP Mint Ceremony",
            "steps": [
                {"name": "Verify Eligibility", "action": "check_tournament_eligibility"},
                {"name": "Generate Metadata", "action": "generate_vhp_metadata"},
                {"name": "Generate Governance Memo", "action": "generate_governance_memo"},
                {"name": "Await Operator Signature", "action": "await_signature"},
                {"name": "Log to Audit Trail", "action": "log_audit"},
            ],
        },
        "chain_junction": {
            "title": "Chain Junction Ceremony",
            "steps": [
                {"name": "Record Provisional Commitment", "action": "record_provisional"},
                {"name": "Generate Junction Config", "action": "generate_junction_config"},
                {"name": "Generate Governance Memo", "action": "generate_governance_memo"},
                {"name": "Await Operator Signature", "action": "await_signature"},
                {"name": "Log to Audit Trail", "action": "log_audit"},
            ],
        },
        "invariant_change": {
            "title": "Invariant Change Ceremony",
            "steps": [
                {"name": "Document Proposed Change", "action": "document_change"},
                {"name": "VHP Gate Check", "action": "vhp_gate_check"},
                {"name": "Generate Governance Memo", "action": "generate_governance_memo"},
                {"name": "Await Operator Signature", "action": "await_signature"},
                {"name": "Update Invariant Records", "action": "update_invariants"},
            ],
        },
    }

    def __init__(self, bridge: Optional[BridgeClient] = None,
                 methodology: Optional[MethodologyRegistry] = None):
        self.bridge = bridge or BridgeClient()
        self.methodology = methodology or MethodologyRegistry()

    def list_templates(self) -> list[str]:
        return list(self.CEREMONY_TEMPLATES.keys())

    def create_ceremony(self, template_name: str, context: dict = None) -> dict:
        """Create a new ceremony from a template."""
        template = self.CEREMONY_TEMPLATES.get(template_name)
        if not template:
            return {"error": f"Unknown ceremony template: {template_name}"}

        ceremony_id = uuid.uuid4().hex[:8]
        return {
            "id": ceremony_id,
            "title": template["title"],
            "template": template_name,
            "steps": [
                {**s, "status": "pending", "result": None}
                for s in template["steps"]
            ],
            "context": context or {},
            "created_at": datetime.datetime.utcnow().isoformat(),
            "status": "created",
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  HARDWARE BIOGRAPHER
# ═══════════════════════════════════════════════════════════════════════════════

class HardwareBiographer:
    """Tracks the lifecycle of DualShock Edge controllers.
    Builds a biography of each controller over time."""

    def __init__(self, db_path: str = HARDWARE_DB_PATH):
        self._db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS controllers (
                    controller_id TEXT PRIMARY KEY,
                    first_seen    TEXT NOT NULL,
                    last_seen     TEXT,
                    model         TEXT,
                    total_sessions INTEGER DEFAULT 0,
                    total_playtime_s REAL DEFAULT 0,
                    biometric_baseline TEXT,
                    separation_ratio REAL,
                    l4_anomaly_rate REAL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    controller_id   TEXT NOT NULL REFERENCES controllers(controller_id),
                    started_at      TEXT NOT NULL,
                    ended_at        TEXT,
                    capture_card    TEXT,
                    game            TEXT,
                    playtime_s      REAL DEFAULT 0,
                    poac_records    INTEGER DEFAULT 0,
                    cheating_events INTEGER DEFAULT 0,
                    separation_peak REAL,
                    separation_avg  REAL,
                    l4_score        REAL,
                    FOREIGN KEY (controller_id) REFERENCES controllers(controller_id)
                );
            """)

    def record_session_start(self, controller_id: str, model: str = "",
                             capture_card: str = "", game: str = "") -> int:
        now = datetime.datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            # Upsert controller
            conn.execute("""
                INSERT INTO controllers (controller_id, first_seen, model)
                VALUES (?, ?, ?)
                ON CONFLICT(controller_id) DO UPDATE SET
                    last_seen = excluded.last_seen
            """, (controller_id, now, model))
            # Create session
            cur = conn.execute("""
                INSERT INTO sessions (controller_id, started_at, capture_card, game)
                VALUES (?, ?, ?, ?)
            """, (controller_id, now, capture_card, game))
            return cur.lastrowid

    def record_session_end(self, session_id: int, playtime_s: float = 0,
                           poac_records: int = 0, cheating_events: int = 0,
                           separation_peak: float = 0, separation_avg: float = 0,
                           l4_score: float = 0):
        now = datetime.datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE sessions SET ended_at=?, playtime_s=?, poac_records=?,
                    cheating_events=?, separation_peak=?, separation_avg=?, l4_score=?
                WHERE id=?
            """, (now, playtime_s, poac_records, cheating_events,
                  separation_peak, separation_avg, l4_score, session_id))
            # Update controller totals
            row = conn.execute(
                "SELECT controller_id FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if row:
                conn.execute("""
                    UPDATE controllers SET
                        total_sessions = total_sessions + 1,
                        total_playtime_s = total_playtime_s + ?,
                        last_seen = ?
                    WHERE controller_id = ?
                """, (playtime_s, now, row["controller_id"]))

    def get_biography(self, controller_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM controllers WHERE controller_id=?",
                (controller_id,)
            ).fetchone()
            if not row:
                return None
            bio = dict(row)
            # Get sessions
            sessions = conn.execute(
                """SELECT * FROM sessions WHERE controller_id=?
                   ORDER BY started_at DESC LIMIT 20""",
                (controller_id,)
            ).fetchall()
            bio["sessions"] = [dict(s) for s in sessions]
            return bio


# ═══════════════════════════════════════════════════════════════════════════════
#  REFLEX CONCIERGE
# ═══════════════════════════════════════════════════════════════════════════════

class ReflexConcierge:
    """Monitors operator state and adjusts PoEP rig parameters.
    Tracks separation ratio over session duration to detect fatigue."""

    def __init__(self):
        self._readings: list[dict] = []
        self._baseline_separation: Optional[float] = None
        self._current_threshold: float = 0.85
        self._default_threshold: float = 0.85
        self._adjustments_made: int = 0

    def record_reading(self, separation_ratio: float, timestamp: Optional[float] = None):
        """Record a separation ratio reading."""
        ts = timestamp or time.time()
        self._readings.append({
            "separation": separation_ratio,
            "timestamp": ts,
        })
        if self._baseline_separation is None:
            self._baseline_separation = separation_ratio

        # Keep last 100 readings
        if len(self._readings) > 100:
            self._readings = self._readings[-100:]

    def assess_operator_state(self) -> dict:
        """Assess operator state based on separation ratio readings."""
        if not self._readings or self._baseline_separation is None:
            return {"state": "unknown", "recommendation": "insufficient data"}

        recent = self._readings[-10:] if len(self._readings) >= 10 else self._readings
        avg_separation = sum(r["separation"] for r in recent) / len(recent)
        drift = avg_separation - self._baseline_separation

        session_duration = 0
        if len(self._readings) > 1:
            session_duration = self._readings[-1]["timestamp"] - self._readings[0]["timestamp"]

        state = "nominal"
        recommendation = "no adjustment needed"
        fatigue_probability = 0.0

        if drift < -0.05 and session_duration > 3600:
            state = "fatigued"
            fatigue_probability = min(1.0, abs(drift) * 5)
            recommendation = "ease PoEP gate threshold by 0.05"
        elif drift < -0.03 and session_duration > 7200:
            state = "declining"
            fatigue_probability = min(1.0, abs(drift) * 3)
            recommendation = "monitor closely, consider break"
        elif drift > 0.02:
            state = "improving"
            fatigue_probability = 0.0
            recommendation = "tighten PoEP gate threshold by 0.02"

        return {
            "state": state,
            "baseline_separation": self._baseline_separation,
            "current_separation": avg_separation,
            "drift": drift,
            "session_duration_s": session_duration,
            "fatigue_probability": fatigue_probability,
            "recommendation": recommendation,
            "current_threshold": self._current_threshold,
        }

    def adjust_threshold(self, delta: float) -> float:
        """Adjust the PoEP gate threshold."""
        self._current_threshold = max(0.5, min(0.95, self._current_threshold + delta))
        self._adjustments_made += 1
        return self._current_threshold

    def reset_threshold(self):
        self._current_threshold = self._default_threshold

    @property
    def summary(self) -> str:
        state = self.assess_operator_state()
        return (
            f"Operator: {state['state']} | "
            f"Separation: {state['current_separation']:.3f} "
            f"(baseline {state['baseline_separation']:.3f}) | "
            f"Drift: {state['drift']:+.3f} | "
            f"Threshold: {state['current_threshold']:.2f} | "
            f"Adjustments: {self._adjustments_made}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  CROSS-SESSION CONTINUITY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ContinuityEngine:
    """Maintains context across sessions. Loads last session state,
    tracks long-running threads, and provides continuity."""

    def __init__(self, session_history: SessionHistory,
                 methodology: MethodologyRegistry,
                 db_path: str = SESSION_DB_PATH):
        self.session_history = session_history
        self.methodology = methodology
        self._db_path = db_path

    def get_greeting(self) -> str:
        """Generate a greeting that includes context from past sessions."""
        parts = []
        parts.append("QorTroller Engineering Assistant v2.0")

        # Model info
        parts.append(f"Model: {QUICKSILVER_MODEL}")

        # Methodology count
        meth_count = self.methodology.count()
        parts.append(f"Lessons learned: {meth_count}")

        # Last session
        last = self.session_history.get_last_session_summary()
        if last:
            last_date = last.get("created_at", "unknown")[:10]
            parts.append(f"Last session: {last_date}")
            if last.get("summary"):
                parts.append(f"Previous context: {last['summary'][:200]}")

        # All sessions count
        sessions = self.session_history.get_all_sessions(limit=1)
        if sessions:
            total = len(sessions)  # This is just the limit
            # Get actual count
            try:
                with self.session_history._get_conn() as conn:
                    row = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()
                    if row:
                        total = row["c"]
            except Exception:
                pass
            parts.append(f"Total sessions: {total}")

        # Decisions count
        decisions = self.session_history.get_all_decisions(limit=1)
        dec_count = len(decisions)
        try:
            with self.session_history._get_conn() as conn:
                row = conn.execute("SELECT COUNT(*) as c FROM decisions").fetchone()
                if row:
                    dec_count = row["c"]
        except Exception:
            pass
        if dec_count:
            parts.append(f"Decisions recorded: {dec_count}")

        return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_system_prompt(methodology: MethodologyRegistry,
                        continuity: ContinuityEngine,
                        hardware_watcher: Optional[HardwareWatcher] = None,
                        contradiction_oracle: Optional[ContradictionOracle] = None) -> str:
    """Build the system prompt for the LLM. Loaded at every request."""

    # Methodology
    meth_all = methodology.all()
    meth_context = MethodologyRegistry.format_for_prompt(meth_all)

    # Hardware state
    hw_context = ""
    if hardware_watcher:
        hw = hardware_watcher.last_state
        hw_context = (
            f"\n## Hardware State\n"
            f"- DualShock: {'Connected' if hw['dualshock'] else 'Disconnected'}\n"
            f"- Capture Card: {'Detected' if hw['capture_card'] else 'Not detected'}\n"
            f"- Bridge: {'Up' if hw['bridge'] else 'Down'}\n"
            f"- State: {hw['state']}\n"
        )

    # Contradictions
    contradiction_context = ""
    if contradiction_oracle:
        cc = contradiction_oracle.contradiction_count
        contradiction_context = f"\n## Contradictions\nActive: {cc}\n"

    # Continuity
    continuity_context = continuity.get_greeting()

    return f"""You are the QorTroller Engineering Assistant — a senior engineer who knows this codebase better than anyone.

{continuity_context}

## Your Role
- You are NOT a chatbot. You are a senior engineer.
- You brainstorm approaches when asked. You suggest improvements you see, even if not asked.
- You push back when something is architecturally wrong.
- You opinionate on tradeoffs (local vs cloud, speed vs security, simple vs flexible).
- You proactively flag issues: stale code, unrun tests, insecure configurations.
- You are expected to use tools to accomplish tasks, not just talk about them.

## Project Context
You are working on the QorTroller project at {REPO_ROOT}.
The project includes: 250+ bridge agent modules, 188 PV-CI invariants, 30 FSCA contradiction rules,
PoAC chain, PoEP hardware rig, Retina capture pipeline, DualShock Edge integration,
ZK proofs, VHP minting, data marketplace, tournament system, and curator system.

## Methodology (Lessons Learned)
These are lessons from past sessions. Apply them when relevant.
{meth_context}

## Tools Available
You have access to the following tools: read_file, read_file_range, write_file, edit_file,
shell, run_pytest, git_log, git_diff, git_status, git_commit, bridge_health, bridge_get,
bridge_post, methodology_query, methodology_add, search_files, grep, check_invariants,
check_contradictions, protocol_state, tree, hardware_status.

Use tools to accomplish tasks. When you make a mistake, learn from it.
When you discover a new failure pattern, add it to the methodology registry.

## FROZEN Governance
FROZEN files (_core.py, _daemon_tools_schema.py, operator_api/*, vapi_ext_*)
must NOT be edited directly. Use propose_edit to generate a .diff proposal.
The operator applies the diff via git apply.

## Hardware
{hw_context}
{contradiction_context}

## Decision Journal
When you make a significant judgment call (choosing approach A over B,
recommending a design, flagging a risk), log the decision to the decision journal.
Future sessions will be able to query: "Why did we choose X?"

## Operator
You are working with the QorTroller operator. They are an experienced engineer.
Be direct, be honest, be opinionated. Don't waste their time with fluff.
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  TUI (Textual)
# ═══════════════════════════════════════════════════════════════════════════════

class QorTrollerTUI:
    """Simplified TUI for the QorTroller Engineering Assistant.
    Uses Textual when available, falls back to a basic REPL."""

    def __init__(self, llm_client: QuickSilverClient,
                 tools: ToolEngine,
                 methodology: MethodologyRegistry,
                 session_history: SessionHistory,
                 continuity: ContinuityEngine,
                 hardware_watcher: Optional[HardwareWatcher] = None,
                 contradiction_oracle: Optional[ContradictionOracle] = None,
                 invariant_sentinel: Optional[InvariantSentinel] = None,
                 protocol_state: Optional[ProtocolState] = None,
                 debug_loop: Optional[AutonomousDebugLoop] = None,
                 vlm_observer: Optional = None):
        self.llm = llm_client
        self.tools = tools
        self.methodology = methodology
        self.session_history = session_history
        self.continuity = continuity
        self.hardware_watcher = hardware_watcher
        self.contradiction_oracle = contradiction_oracle
        self.invariant_sentinel = invariant_sentinel
        self.protocol_state = protocol_state
        self.debug_loop = debug_loop
        self.vlm_observer = vlm_observer
        self._conversation: list[dict] = []

    async def run(self):
        """Run the TUI. Tries Textual, falls back to REPL."""
        # Try Textual
        try:
            from textual.app import App
            from textual.widgets import Header, Footer, Static, Input, RichLog
            from textual.containers import Container, Horizontal, Vertical
            from textual.binding import Binding
            from textual.reactive import var

            class QorTrollerTextualApp(App):
                """Textual-based TUI for QorTroller Engineering Assistant."""

                BINDINGS = [
                    Binding("ctrl+c", "quit", "Quit", show=True),
                    Binding("ctrl+l", "clear", "Clear", show=True),
                    Binding("ctrl+h", "hardware", "Hardware", show=True),
                    Binding("ctrl+p", "protocol", "Protocol", show=True),
                    Binding("ctrl+m", "methodology", "Methodology", show=True),
                ]

                def compose(self):
                    with Container():
                        yield Header(show_clock=True)
                    with Horizontal():
                        with Vertical(id="main-column"):
                            yield RichLog(id="chat-log", highlight=True, markup=True)
                            yield Input(id="input-bar", placeholder="> Type a message...")
                        with Vertical(id="sidebar"):
                            yield Static(id="status-panel", classes="panel")
                            # NEW: VLM observation panel
                            yield Static(id="vlm-panel", classes="panel")
                    yield Footer()

                def on_mount(self):
                    self.query_one("#chat-log").write(
                        f"[bold green]QorTroller Engineering Assistant v{VERSION}[/]\n"
                        f"[italic]Powered by QuickSilver Pro ({QUICKSILVER_MODEL})[/]\n"
                        f"[italic]Type a message. Ctrl+C to quit. Ctrl+H for hardware.[/]\n"
                    )
                    # Show greeting
                    greeting = self.app.continuity.get_greeting()
                    self.query_one("#chat-log").write(f"\n{greeting}\n")
                    # Start background refresh
                    self.set_interval(5, self._refresh_status)
                    # NEW: Start VLM observer background refresh
                    self.set_interval(1, self._refresh_vlm)

                async def _refresh_status(self):
                    status = []
                    # Hardware
                    if self.app.hardware_watcher:
                        hw = self.app.hardware_watcher.last_state
                        ds = "🟢" if hw["dualshock"] else "🔴"
                        cc = "🟢" if hw["capture_card"] else "🔴"
                        br = "🟢" if hw["bridge"] else "🔴"
                        status.append(f"DS:{ds} CC:{cc} BR:{br}")
                    # Methodology
                    if self.app.methodology:
                        status.append(f"Methodology: {self.app.methodology.count()} lessons")
                    # Contradictions
                    if self.app.contradiction_oracle:
                        status.append(f"Contradictions: {self.app.contradiction_oracle.contradiction_count}")
                    # VLM Session Manager
                    if hasattr(self.app, 'vlm_session_manager'):
                        if self.app.vlm_session_manager.is_active:
                            status.append(f"VLM: 🟢 Active (session: {self.app.vlm_session_manager.current_session_id})")
                        else:
                            status.append("VLM: 🔴 Inactive")
                        
                    panel = self.query_one("#status-panel")
                    panel.update("\n".join(status))

                async def _refresh_vlm(self):
                    """Refresh VLM observation panel with recent observations."""
                    if not hasattr(self.app, 'vlm_observer'):
                        return
                        
                    vlm_observer = self.app.vlm_observer
                    if not vlm_observer:
                        return
                        
                    # Get recent observations
                    observations = vlm_observer.recent(max_observations=3, max_age_seconds=10)
                        
                    if not observations:
                        panel = self.query_one("#vlm-panel")
                        panel.update("[italic]No recent VLM observations[/]")
                        return
                        
                    # Format observations for display
                    lines = ["[bold]VLM Observations[/]"]
                    for obs in observations:
                        timestamp = time.strftime("%H:%M:%S", time.localtime(obs.timestamp_ns / 1e9))
                        lines.append(f"[{timestamp}] {obs.game_state}")
                        if obs.screen_description:
                            desc = obs.screen_description[:50]
                            if len(obs.screen_description) > 50:
                                desc += "..."
                            lines.append(f"  {desc}")
                        if obs.cross_modal_anomaly:
                            lines.append(f"  [bold red]⚠️ ANOMALY: {obs.cross_modal_anomaly_type}[/]")
                        
                    # Also check for autonomous responses
                    if vlm_observer.last_autonomous_response:
                        lines.append("")
                        lines.append("[bold yellow]EA Insight:[/]")
                        lines.append(vlm_observer.last_autonomous_response[:200])
                        
                    panel = self.query_one("#vlm-panel")
                    panel.update("\n".join(lines))

                def on_input_submitted(self, event: Input.Submitted):
                    """Handle user input."""
                    text = event.value.strip()
                    if not text:
                        return
                    self.query_one("#input-bar").value = ""
                    self.query_one("#chat-log").write(f"\n[bold blue]> {text}[/]")
                    # Process in background
                    self._process_input(text)

                @work(thread=False)
                async def _process_input(self, text: str):
                    log = self.query_one("#chat-log")
                    try:
                        response = await self.app._process_message(text)
                        log.write(response)
                    except Exception as e:
                        log.write(f"[bold red]Error: {e}[/]")

            app = QorTrollerTextualApp()
            app.continuity = self.continuity
            app.hardware_watcher = self.hardware_watcher
            app.methodology = self.methodology
            app.contradiction_oracle = self.contradiction_oracle
            app._process_message = self._process_message
            # NEW: VLM integration
            if hasattr(self, 'vlm_observer'):
                app.vlm_observer = self.vlm_observer
            if hasattr(self, 'vlm_session_manager'):
                app.vlm_session_manager = self.vlm_session_manager
            await app.run_async()

        except ImportError:
            # Fallback to REPL
            await self._run_repl()

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove characters that can't be encoded in the terminal's code page."""
        try:
            # Test if it can be encoded
            text.encode(sys.stdout.encoding or "utf-8")
            return text
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        # Replace non-encodable characters with safe alternatives
        result = []
        for ch in text:
            try:
                # Smart quotes and dashes -> ASCII equivalents
                if ch in ("\u2018", "\u2019", "\u201a", "\u201b"):
                    result.append("'")
                elif ch in ("\u201c", "\u201d", "\u201e", "\u201f"):
                    result.append('"')
                elif ch in ("\u2013", "\u2014"):
                    result.append("--")
                elif ch in ("\u2026",):
                    result.append("...")
                elif ch in ("\u2022", "\u2023"):
                    result.append("*")
                elif ch in ("\u00a0",):
                    result.append(" ")
                else:
                    ch.encode(sys.stdout.encoding or "utf-8")
                    result.append(ch)
            except (UnicodeEncodeError, UnicodeDecodeError):
                # Replace emoji and other non-encodable characters
                if ch in ("\u2705", "\u2714", "\u2713"):  # check marks
                    result.append("[OK]")
                elif ch in ("\u274c", "\u2717", "\u2718"):  # X marks
                    result.append("[FAIL]")
                elif ch in ("\u26a0", "\u2622"):  # warnings
                    result.append("[!]")
                elif ch in ("\U0001f534", "\U0001f7e2", "\U0001f7e1", "\U0001f7e0", "\U0001f7e3"):  # circles
                    result.append("(O)")
                elif ch in ("\U0001f9ea", "\U0001f52c"):  # test tube/microscope
                    result.append("[TEST]")
                elif ch in ("\U0001f389", "\u2728", "\u2b50"):  # celebration
                    result.append("[*]")
                elif ch in ("\U0001f4e6", "\U0001f5c4", "\U0001f4c1", "\U0001f4c2"):  # files/dirs
                    result.append("[DIR]")
                elif ch in ("\U0001f517", "\U0001f50c"):  # links
                    result.append("[LINK]")
                elif ch in ("\U0001f504", "\u23f3"):  # in-progress
                    result.append("[...]")
                elif ch in ("\u25b6", "\u27a1", "\u2192"):  # arrows
                    result.append("->")
                elif ch in ("\u25c0", "\u2b05", "\u2190"):  # arrows
                    result.append("<-")
                elif ch in ("\u25b2", "\u2b06", "\u2191"):  # arrows
                    result.append("^")
                elif ch in ("\u25bc", "\u2b07", "\u2193"):  # arrows
                    result.append("v")
                elif ch in ("\U0001f3c6", "\U0001f947", "\U0001f948", "\U0001f949"):  # awards
                    result.append("[AWARD]")
                elif ch in ("\U0001f4a1", "\U0001f526"):  # ideas
                    result.append("[IDEA]")
                elif ch in ("\U0001f680", "\U0001f6f8"):  # go/launch
                    result.append("[GO]")
                elif ch in ("\U0001f4ca", "\U0001f4c8", "\U0001f4c9"):  # charts
                    result.append("[CHART]")
                elif ch in ("\U0001f510", "\U0001f511", "\U0001f6e1"):  # security
                    result.append("[SECURE]")
                elif ch in ("\U0001f916", "\U0001f9e0", "\U0001f9be"):  # AI/robot
                    result.append("[AI]")
                elif ch in ("\U0001f310", "\u2601"):  # network/cloud
                    result.append("[NET]")
                else:
                    # Check if it's a supplementary character (emoji)
                    cp = ord(ch)
                    if cp >= 0x1F300:
                        result.append(":")  # emoji indicator
                    elif cp >= 0x2000:
                        result.append("_")  # other unicode
                    else:
                        result.append("?")
        return "".join(result)

    async def _run_repl(self):
        """Simple REPL fallback when Textual is not available."""
        print(f"\n{'=' * 60}")
        print(f"  {APP_NAME} v{VERSION}")
        print(f"  Model: {QUICKSILVER_MODEL}")
        print(f"  Lessons: {self.methodology.count()}")
        print(f"{'=' * 60}")
        print(f"  Type /help for commands, /quit to exit")
        print(f"  Ctrl+H for hardware, Ctrl+P for protocol")
        print()

        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not text:
                continue
            if text == "/quit":
                break
            if text == "/help":
                print("Commands: /quit, /help, /hardware, /protocol, /methodology")
                print("Anything else is sent to the LLM.")
                continue
            if text == "/hardware":
                if self.hardware_watcher:
                    print(json.dumps(self.hardware_watcher.last_state, indent=2, default=str))
                else:
                    print("Hardware watcher not running")
                continue
            if text == "/protocol":
                if self.protocol_state:
                    await self.protocol_state.refresh()
                    print(f"Bridge: {self.protocol_state.bridge_health}")
                    print(f"Agents: {self.protocol_state.healthy_agents}/{self.protocol_state.agent_count}")
                    print(f"Contradictions: {self.protocol_state.contradiction_count}")
                else:
                    print("Protocol state not available")
                continue
            if text == "/methodology":
                entries = self.methodology.all()
                for cls, e in entries.items():
                    print(f"\n[{cls}]")
                    print(f"  AVOID: {e.get('anti_pattern', '')[:120]}")
                    print(f"  DO: {e.get('correct_pattern', '')[:120]}")
                continue

            response = await self._process_message(text)
            print(f"\n{self._sanitize(response)}\n")

        # End session
        self.session_history.end_session(f"REPL session with {len(self._conversation)} messages")

    async def _process_message(self, user_text: str) -> str:
        """Process a user message: call LLM, execute tools, return response."""
        # Add user message to history
        self.session_history.add_message("user", user_text)
        self._conversation.append({"role": "user", "content": user_text})

        # Build system prompt with current context
        system_prompt = build_system_prompt(
            self.methodology, self.continuity,
            self.hardware_watcher, self.contradiction_oracle,
        )

        # Check contradictions if relevant
        if self.contradiction_oracle:
            violations = self.contradiction_oracle.check(user_text)
            if violations:
                warn = "⚠️ Contradiction warning:\n"
                for v in violations:
                    warn += f" - {v['rule']} ({v['severity']}): {v['description'][:120]}\n"
                warn += "\nProceed? The tool will log an override if you continue.\n"
                self._conversation.append({"role": "system", "content": warn})

        # Build messages for LLM
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # ── NEW: Inject recent VLM observations into context ──────────────
        if self.vlm_observer:
            vlm_context = self.vlm_observer.get_context_summary(
                max_observations=5, 
                max_age_seconds=30.0
            )
            if vlm_context:
                messages.append({
                    "role": "system",
                    "content": vlm_context
                })
        
        # Add recent conversation history (last 10 exchanges)
        for msg in self._conversation[-20:]:
            messages.append(msg)

        # Call LLM with tools
        response = self.llm.chat(
            messages,
            tools=self.tools.tool_definitions,
            temperature=0.7,
        )

        # Handle errors
        if "error" in response:
            error_msg = f"[bold red]LLM Error: {response['error']}[/]"
            self._conversation.append({"role": "assistant", "content": error_msg})
            self.session_history.add_message("assistant", error_msg, backend=self.llm._last_backend)
            return error_msg

        # Extract assistant message
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls", [])

        # Execute tool calls
        if tool_calls:
            results = []
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                result = self.tools.execute(name, args)
                results.append({
                    "tool_call_id": tc.get("id", ""),
                    "role": "tool",
                    "name": name,
                    "content": result,
                })

            # Add tool results to conversation
            self._conversation.append(message)
            for r in results:
                self._conversation.append(r)

            # Call LLM again with tool results
            follow_up = self.llm.chat(
                self._conversation[-30:] + [{"role": "system", "content": "Summarize the tool results for the user."}],
                temperature=0.5,
            )
            if "error" not in follow_up:
                content = follow_up.get("choices", [{}])[0].get("message", {}).get("content", "") or content

        # Add assistant message to history
        self._conversation.append({"role": "assistant", "content": content})
        self.session_history.add_message("assistant", content, tool_calls, backend=self.llm._last_backend)

        return content


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTER CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class RouterClient:
    """Router wrapper for the Engineering Assistant.

    Preserves the self.llm.chat() interface the TUI expects.
    Delegates to the bridge LLMRouter with task_class='assistant',
    so the TUI class needs zero changes.

    The router handles failover: QuickSilver → LOCAL → (NIM if allowed).
    Honesty fields (backend, model, attempts, fallback_used) are
    available on the RouteResult if needed.
    """

    def __init__(self):
        self._router = None
        self._last_result = None
        self._last_backend = ""
        self._last_model = ""
        self._init_router()

    def _init_router(self):
        try:
            from bridge.vapi_bridge.llm_routing import LLMRouter
            self._router = LLMRouter()
        except Exception as exc:
            logger.warning("RouterClient init failed: %s", exc)

    @property
    def configured(self) -> bool:
        """True if at least one backend is configured."""
        if not self._router:
            return False
        return any(
            bk.configured() for bk in self._router._backends.values()
        )

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a chat completion through the router.

        Matches the QuickSilverClient.chat() interface so the
        TUI class doesn't need changes. Returns the same
        OpenAI-shaped dict or {"error": "..."} on failure.
        """
        import asyncio

        if not self._router:
            return {"error": "LLM router not initialized"}

        try:
            result = asyncio.run(
                self._router.route(
                    task_class="assistant",
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
        except Exception as exc:
            logger.error("RouterClient.route() failed: %s", exc)
            return {"error": str(exc)}

        self._last_result = result
        self._last_backend = result.backend
        self._last_model = result.model
        if result.success and result.content:
            return {
                "choices": [{"message": {"role": "assistant", "content": result.content}}],
                "model": result.model,
            }

        return {"error": result.error or "LLM request failed"}


async def main():
    """Entry point for the QorTroller Engineering Assistant."""
    import argparse

    parser = argparse.ArgumentParser(description="QorTroller Engineering Assistant")
    parser.add_argument("--cli", action="store_true", help="REPL mode (no TUI)")
    parser.add_argument("--mcp", action="store_true", help="MCP server mode")
    parser.add_argument("--exec", type=str, help="One-shot command")
    args = parser.parse_args()

    # ── Print banner ─────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  {APP_NAME} v{VERSION}")
    print(f"  Model: {QUICKSILVER_MODEL}")
    print(f"  Repo:  {REPO_ROOT}")
    print(f"  Data:  {DATA_DIR}")
    print(f"{'=' * 60}\n")
    log = logging.getLogger(__name__)
    logger = logging.getLogger(__name__)

    # ── Initialize core components ────────────────────────────────────────
    llm = QuickSilverClient()
    if not llm.configured:
        print("⚠️  WARNING: QUICKSILVER_API_KEY not configured.")
        print("   Set it in your environment or .env file.")
        print("   The tool will run in offline mode.\n")

    methodology = MethodologyRegistry()
    session_history = SessionHistory()
    bridge = BridgeClient()
    tools = ToolEngine(bridge=bridge)
    tools.methodology_registry = methodology
    debug_loop = AutonomousDebugLoop(tools, methodology)
    continuity = ContinuityEngine(session_history, methodology)

    # ── Initialize intelligent systems ────────────────────────────────────
    contradiction_oracle = ContradictionOracle(bridge)
    invariant_sentinel = InvariantSentinel()
    protocol_state = ProtocolState(bridge)
    hardware_watcher = HardwareWatcher(bridge)

    # ── Initialize VLM Session Manager ──────────────────────────────────────
    # This wires the VLM to the hardware lifecycle - starts automatically
    # when ALL_READY and stops when IDLE
    from bridge.vapi_bridge.vlm_session_manager import create_vlm_session_manager
    from bridge.vapi_bridge.vlm_observer import get_vlm_observer, get_observation_queue

    vlm_session_manager = create_vlm_session_manager(
        hardware_watcher=hardware_watcher,
        hardware_biographer=HardwareBiographer(),
    )
    vlm_observer = get_vlm_observer()
    observation_queue = get_observation_queue()

    log.info(" VLM Session Manager: initialized (auto-starts on ALL_READY)")

    # ── Start background services ─────────────────────────────────────────
    # Hardware watcher
    hw_task = await hardware_watcher.start()

    # --- Attestation loop ---
    from bridge.vapi_bridge.attestation import AttestationTicker
    from bridge.vapi_bridge.attestation.store import AttestationStore

    attestation_store = AttestationStore(db_path=SESSION_DB_PATH)
    attestation_ticker = AttestationTicker(store=attestation_store)
    attestation_ticker.watch_hardware(hardware_watcher)
    attestation_ticker.watch_pv_ci(invariant_sentinel)
    attestation_ticker.watch_fsca(contradiction_oracle)
    attestation_ticker.watch_session_id(lambda: session_history.session_id)

    async def _on_hardware_state(old_state, new_state):
        if new_state in ("ALL_READY", "all_ready"):
            sid = session_history.session_id
            await attestation_ticker.start(sid)
            logger.info("Attestation loop started for session %s", sid)
        elif old_state in ("ALL_READY", "all_ready"):
            final = await attestation_ticker.stop()
            if final:
                log.info("Attestation loop stopped - %d ticks, hash=%s", attestation_ticker.tick_count, final.envelope_hash[:16])

    hardware_watcher.on_state_change = _on_hardware_state


    print(f"  Hardware Watcher: started")

    # Contradiction oracle refresh
    await contradiction_oracle.refresh()
    print(f"  Contradictions: {contradiction_oracle.contradiction_count} active")

    # Invariant check
    try:
        inv_results = await invariant_sentinel.check()
        failed = inv_results.get("failures", [])
        total = inv_results.get("count", 0) if isinstance(inv_results.get("count"), int) else 0
        if failed and total > 0:
            print(f"  Invariants: {len(failed)}/{total} FAILED")
        elif not failed and total > 0:
            print(f"  Invariants: {total} passed")
        else:
            print(f"  Invariants: check unavailable (bridge may not be running)")
    except Exception:
        print(f"  Invariants: check unavailable")

    # Protocol state
    await protocol_state.refresh()
    print(f"  Bridge: {protocol_state.bridge_health}")

    # ── Show greeting ─────────────────────────────────────────────────────
    greeting = continuity.get_greeting()
    print(f"\n  {greeting}\n")

    # ── Run ───────────────────────────────────────────────────────────────
    tui = QorTrollerTUI(
        llm_client=llm,
        tools=tools,
        methodology=methodology,
        session_history=session_history,
        continuity=continuity,
        hardware_watcher=hardware_watcher,
        contradiction_oracle=contradiction_oracle,
        invariant_sentinel=invariant_sentinel,
        protocol_state=protocol_state,
        debug_loop=debug_loop,
        vlm_observer=vlm_observer,
    )

    try:
        if args.exec:
            # One-shot mode
            response = await tui._process_message(args.exec)
            print(QorTrollerTUI._sanitize(response))
        elif args.mcp:
            # MCP server mode — placeholder
            print("MCP server mode not yet implemented")
        else:
            # TUI/REPL mode
            await tui.run()
    finally:
        # Cleanup
        await hardware_watcher.stop()
        session_history.end_session("Session ended by user")
        print(f"\n  Session ended. Methodology: {methodology.count()} lessons.")
        print(f"  Goodbye.\n")


if __name__ == "__main__":
    asyncio.run(main())