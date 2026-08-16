#!/usr/bin/env python3
"""
QorTroller persistent memory
============================
MethodologyRegistry + SessionHistory, extracted verbatim from qortroller.py
(first step of the monolith split; qortroller.py re-exports both as a
façade, so `from qortroller import MethodologyRegistry` still works).

DATA_DIR derivation is duplicated from qortroller.py on purpose: both files
live at repo root and read QORTROLLER_ROOT the same way, keeping this
module importable without pulling in the whole assistant.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import subprocess
import time
import uuid
from typing import Optional

REPO_ROOT = os.environ.get(
    "QORTROLLER_ROOT",
    os.path.dirname(os.path.abspath(__file__))
)

# Paths (must stay identical to qortroller.py's DATA_DIR block)
DATA_DIR = os.path.join(REPO_ROOT, ".qortroller")
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_DB_PATH = os.path.join(DATA_DIR, "sessions.db")
METHODOLOGY_PATH = os.path.join(DATA_DIR, "methodology.json")

# Session rows record the active model (same env read as qortroller.py)
QUICKSILVER_MODEL = os.environ.get("QUICKSILVER_MODEL", "deepseek-v4-flash")


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
