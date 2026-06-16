#!/usr/bin/env python3
"""
QorTroller Daemon — Hive Mind Central Brain
=============================================

A centralized background service that owns the single QorTrollerAI brain,
the autonomous tool execution loop, and a persistent SQLite memory store.

Frontends (CLI, TUI, web) connect to this daemon as "dumb" rendering clients:
  • POST /chat    — Send a message to the AI (brain processes it fully)
  • GET  /history — Fetch unified chat history from agent_memory.db
  • GET  /status  — See current brain status (thinking, tool-running, idle)
  • GET  /health  — Daemon health check
  • POST /agent/local-host/execute — Direct tool execution (legacy)

Architecture:
  ┌─────────────┐    POST /chat     ┌────────────────────┐
  │  CLI Agent  │ ────────────────→ │                    │  QuickSilver API
  │  (dumb)     │ ←─── GET /history │  QorTrollerDaemon  │ ───────────→
  └─────────────┘                   │  (the ONE brain)   │  https://api...
  ┌─────────────┐    POST /chat     │                    │
  │  TUI Agent  │ ────────────────→ │  agent_memory.db   │
  │  (dumb)     │ ←─── GET /history │  (shared memory)   │
  └─────────────┘                   └────────────────────┘

Usage:
  python qortroller_daemon.py

  Listens on 0.0.0.0:8080 by default.
  Requires: pip install uvicorn
  Depends: QUICKSILVER_API_KEY in bridge/.env or environment.
"""

from __future__ import annotations

import asyncio
import datetime
import hmac
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
#  Bootstrap: Load .env BEFORE any other imports
# ═══════════════════════════════════════════════════════════════════════════════

_DOTENV = os.path.join(os.path.dirname(__file__), "bridge", ".env")
if os.path.isfile(_DOTENV):
    with open(_DOTENV, "r", encoding="utf-8", errors="ignore") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

# ═══════════════════════════════════════════════════════════════════════════════
#  Constants & Configuration
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "QorTroller Daemon"
APP_VERSION = "2.0.0"
DAEMON_VERSION = "hive-mind-v1"

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
PORT = int(os.environ.get("HTTP_PORT", 8080))
MAX_TOOL_ITERATIONS = 10
TOOL_TIMEOUT = 15

QUICKSILVER_API_KEY = os.environ.get("QUICKSILVER_API_KEY", "")
QUICKSILVER_API_URL = "https://api.quicksilverpro.io/v1/chat/completions"
QUICKSILVER_MODEL = os.environ.get("QUICKSILVER_MODEL", "deepseek-v4-flash")

OPERATOR_API_KEY = os.environ.get("OPERATOR_API_KEY", "")
BRIDGE_BASE_URL = os.environ.get("VAPI_BRIDGE_URL", "http://localhost:8000")
TOOL_SERVER_URL = os.environ.get("TOOL_SERVER_URL", "http://localhost:8080")

SQLITE_DB_PATH = os.path.join(REPO_ROOT, "agent_memory.db")

# ═══════════════════════════════════════════════════════════════════════════════
#  THE ONE SYSTEM PROMPT — lives only here, in the daemon
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are the QorTroller AI Agent — the cognitive interface for the "
    "QorTroller V.A.P.I. (Verifiable Autonomous Physical Intelligence) protocol. "
    "You are part of a Hive Mind architecture where your single brain runs in the "
    "QorTroller Daemon, and multiple frontends (CLI, TUI) connect as rendering clients.\n\n"
    "QorTroller is the reference implementation of V.A.P.I., a DePIN sub-category "
    "for competitive gaming. Gamers and their controllers (Sony DualShock Edge CFI-ZCP1) "
    "produce physical telemetry data and own that data. It generates a 228-byte Proof of "
    "Autonomous Cognition (PoAC) record per cognition cycle, anchored on IoTeX L1, to "
    "cryptographically prove liveness and prevent botting/cheating.\n\n"
    "The protocol operates in phases (currently ~Phase 240+). The bridge service manages "
    "38+ agents that monitor the protocol, handle attestations, publish on-chain anchors, "
    "and run the tournament eligibility pipeline.\n\n"
    "Key concepts:\n"
    "• PITL Nine-Level Stack (L0-L6, L2B, L2C, L6B) for anti-cheat\n"
    "• 228-byte PoAC wire format (FROZEN — do not modify)\n"
    "• L4 Biometric fingerprint (12-feature Mahalanobis, thresholds 7.009/5.367)\n"
    "• Separation ratio: inter-player biometric distance (currently ~1.199 for AIT probe)\n"
    "• Tournament eligibility gated by P0 conditions, VHP mint, and separation defensibility\n"
    "• ioSwarm — decentralized voting swarm with emulator (5 nodes)\n"
    "• 45+ smart contracts deployed on IoTeX Testnet (Chain ID 4690)\n"
    "• Active wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692\n\n"
    "Answer questions concisely, accurately, and with technical depth.\n\n"

    "╔══════════════════════════════════════════════════════════════╗\n"
    "║  VERIFICATION DISCIPLINE                                    ║\n"
    "╚══════════════════════════════════════════════════════════════╝\n\n"

    "RULE 1 — AUTONOMOUS VERIFICATION\n"
    "Before answering any technical question about the codebase, verify\n"
    "using the available tools. Do NOT guess file contents. Do NOT assume\n"
    "project structure. Use read_file and list_files to confirm facts.\n"
    "Your training data is stale; the codebase and bridge are truth.\n\n"

    "RULE 2 — LIVE DATA OVER MEMORY\n"
    "For protocol status (phase, separation ratio, agent count, contract\n"
    "states), ALWAYS query the bridge via bridge_get rather than recalling\n"
    "from training. Training data can be weeks old.\n\n"

    "RULE 3 — PROTOCOL INVARIANTS (FROZEN — NEVER SUGGEST CHANGES)\n"
    "  - The 228-byte PoAC wire format is FROZEN.\n"
    "  - L4 anomaly threshold = 7.009, continuity threshold = 5.367.\n"
    "    These can only tighten, never loosen.\n"
    "  - The PITL Nine-Level Stack (L0-L6 + L2B, L2C, L6B) is canonical.\n"
    "  - humanity_probability formula weights are frozen per PITL spec.\n\n"

    "RULE 4 — EVIDENCE CITATION\n"
    "When referencing code, cite the specific file path. If you cannot\n"
    "produce a citation, you have not verified the claim.\n\n"

    "RULE 5 — NO HALLUCINATION OF PROTOCOL CLAIMS\n"
    "Never invent or assume protocol behavior, attestation logic, or on-chain\n"
    "state. Rely strictly on:\n"
    "  - Physical controller telemetry (DualShock Edge CFI-ZCP1, USB HID)\n"
    "  - Existing zero-knowledge circuit artifacts (Groth16, BN254, circom)\n"
    "  - Deployed IoTeX smart contract addresses and ABIs\n"
    "  - Bridge API live data from /agent/* endpoints (use bridge_get)\n"
    "  - Files actually present in the codebase (verified via read_file)\n"
    "If you cannot find an artifact or data source through your tools,\n"
    "say so. Do not fabricate contract logic, circuit constraints, or\n"
    "protocol phase behavior.\n\n"

    "RULE 6 — UNCERTAINTY ACKNOWLEDGMENT\n"
    "If you cannot verify a claim, say so explicitly. Never fabricate\n"
    "file contents, contract addresses, deployment statuses, or phase\n"
    "numbers. Use bridge_get to check live data.\n\n"

    "RULE 7 — CHECK GOVERNANCE FILES BEFORE ARCHITECTURAL CHANGES\n"
    "Before proposing any architectural change, ALWAYS read:\n"
    "  - CLAUDE.md          — Project context, hard rules, gotchas\n"
    "  - ARCHITECTURE.md    — Canonical architecture reference\n"
    "  - scripts/vapi_invariant_gate.py  — Frozen protocol invariants\n"
    "Use read_file to load these files and verify your proposal does not\n"
    "violate any hard rule or invariant.\n\n"

    "RULE 8 — TOOL-FIRST APPROACH\n"
    "Before every response, ask: 'Can I verify this with read_file or\n"
    "bridge_get?' If yes, invoke the tool first, then answer with real data.\n\n"

    "RULE 9 — PHASE AWARENESS\n"
    "The protocol advances through numbered phases. Use bridge_get to get\n"
    "live canonical phase state from the bridge. Never quote phase\n"
    "numbers from memory.\n\n"

    "╔══════════════════════════════════════════════════════════════╗\n"
    "║  TOOL USE FORMAT                                           ║\n"
    "╚══════════════════════════════════════════════════════════════╝\n\n"
    "When you need to invoke a tool, respond with EXACTLY this format:\n\n"
    "<tool_call>\n"
    "{\n"
    "  \"name\": \"tool_name\",\n"
    "  \"arguments\": { ... }\n"
    "}\n"
    "</tool_call>\n\n"
    "Each response must contain EITHER a <tool_call> block OR a text\n"
    "answer. Never both in the same response.\n\n"
    "Available tools:\n"
    "  [Codebase / Files]\n"
    "  read_file(path: str)                              - Read a file from the codebase (max 12KB)\n"
    "  write_file(path: str, content: str)               - Write/create a file (blocked for protocol files)\n"
    "  list_files()                                      - List all project files (max 300)\n"
    "  search_code(pattern: str, glob?: str)             - Search codebase with ripgrep/git grep\n"
    "  [Version Control]\n"
    "  git_history()                                     - Show recent git log (10 commits, oneline)\n"
    "  git_log_full(ref?: str, n?: int)                  - Full git log with stats for a ref/commit\n"
    "  [Bridge / Chain]\n"
    "  bridge_get(path: str)                             - GET a bridge API endpoint\n"
    "  bridge_post(path: str, payload?: dict)            - POST to a bridge API endpoint\n"
    "  gic_chain_status(n?: int)                         - GIC chain visual: links, head, progress\n"
    "  query_chain(query: str, device_id?: str)          - Query IoTeX testnet directly\n"
    "  chain_overview()                                  - On-chain wallet, block, deployed contracts\n"
    "  [Protocol Domain Tools]\n"
    "  protocol_phase()                                  - Phase context: phase, bridge state,\n"
    "                                                      agents, contracts, git HEAD\n"
    "  tournament_readiness()                            - Tournament gate: preflight pass/fail,\n"
    "                                                      P0 conditions, all blockers\n"
    "  separation_deep_dive(session_type?: str)          - Separation analysis: ratio, per-pair\n"
    "                                                      gaps, LOO accuracy, trends, projections\n"
    "  biometric_vault()                                 - Biometric credentials: VHP status, TTL,\n"
    "                                                      renewal chain, dual primitive\n"
    "  governance_audit(run_invariant?: bool)            - Governance & invariants: PV-CI gate,\n"
    "                                                      allowlist chain, BBG, PMI\n"
    "  fleet_coherence()                                 - Fleet coherence: contradictions, orphans,\n"
    "                                                      inversions, fingerprint registry\n"
    "  corpus_health()                                   - Corpus health: capture velocity,\n"
    "                                                      data readiness, regression guard\n"
    "  l4_calibration()                                  - L4 thresholds: staleness, per-battery\n"
    "                                                      tracks, router, dim sync, FFT\n"
    "  epoch_windows()                                   - Epoch windows: analytics, auto-tune,\n"
    "                                                      device heatmap, overrides\n"
    "  protocol_maturity()                               - Maturity score with all 9 components\n"
    "  [Legacy / Utility]\n"
    "  run_invariant_gate()                              - Run PV-CI invariant gate\n"
    "  poac_status()                                     - Quick protocol status summary\n"
    "  list_contracts()                                  - List deployed contracts\n"
    "  calibration_status()                              - Full enrollment/calibration status\n"
    "  run_mythos(variant: int)                          - Run Mythos variant 1-17; 16=path_a (fast),\n"
    "                                                      1=frozen_drift, 5=crypto_drift, 14=doc_numbers\n"
    "  gic_replay(n?: int, session_id?: str)             - Replay last N GIC links from local DB,\n"
    "                                                      verify each hash — detects tamper/corruption\n"
    "  execute_shell(command: str)                       - Run a shell command\n"
    "  current_time()                                    - Get current date and time\n\n"
    "You can call multiple tools sequentially (one per LLM response). The\n"
    "system feeds each result back to you as a <tool_result> block. Keep\n"
    "calling tools until you have enough information to answer the user,\n"
    "then produce a plain text response with no <tool_call> block."
)

# ═══════════════════════════════════════════════════════════════════════════════
#  SQLite Memory Store (agent_memory.db)
# ═══════════════════════════════════════════════════════════════════════════════

_IGNORE_DIRS = {".git", "node_modules", "dist", "__pycache__", ".venv", "build", ".pytest_cache"}
_IGNORE_FILES = {".env", ".env.local", ".env.production"}


class MemoryStore:
    """SQLite-backed shared memory for the Hive Mind.

    Stores:
      • messages    — Unified chat history (id, role, content, timestamp)
      • status      — Single-row key-value for current brain activity
    """

    def __init__(self, db_path: str = SQLITE_DB_PATH):
        self._db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    timestamp   TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS status (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                INSERT OR IGNORE INTO status (key, value, updated_at)
                    VALUES ('brain_status', 'idle', '1970-01-01T00:00:00');
                INSERT OR IGNORE INTO status (key, value, updated_at)
                    VALUES ('last_message_id', '0', '1970-01-01T00:00:00');
            """)
            conn.commit()
        finally:
            conn.close()

    # ── Messages ──────────────────────────────────────────────────────────

    def add_message(self, role: str, content: str) -> int:
        """Insert a message and return its id."""
        conn = self._get_conn()
        try:
            ts = datetime.datetime.utcnow().isoformat() + "Z"
            cur = conn.execute(
                "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, ts),
            )
            msg_id = cur.lastrowid
            conn.execute(
                "UPDATE status SET value=?, updated_at=? WHERE key='last_message_id'",
                (str(msg_id), ts),
            )
            conn.commit()
            return msg_id
        finally:
            conn.close()

    def get_messages(self, since_id: int = 0, limit: int = 200) -> list[dict]:
        """Get messages since a given id."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, role, content, timestamp FROM messages "
                "WHERE id > ? ORDER BY id ASC LIMIT ?",
                (since_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_messages(self, limit: int = 500) -> list[dict]:
        """Get all messages (latest first)."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, role, content, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return list(reversed([dict(r) for r in rows]))
        finally:
            conn.close()

    def count_messages(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM messages").fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    # ── Status ────────────────────────────────────────────────────────────

    def set_status(self, value: str):
        """Update the brain status."""
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE status SET value=?, updated_at=? WHERE key='brain_status'",
                (value, ts),
            )
            conn.commit()
        finally:
            conn.close()

    def get_status(self) -> dict:
        """Get full status dict."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT key, value, updated_at FROM status").fetchall()
            result = {"message_count": self.count_messages()}
            for r in rows:
                result[r["key"]] = r["value"]
                result[f"{r['key']}_updated_at"] = r["updated_at"]
            return result
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Hive Mind Brain — The Central QorTrollerAI
# ═══════════════════════════════════════════════════════════════════════════════

class QorTrollerBrain:
    """The single central AI brain for the Hive Mind.

    Owns the LLM connection, the autonomous tool execution loop, and
    the conversation state. Multiple frontends share this one brain.
    """

    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self._lock = asyncio.Lock()
        self._conversation: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ── LLM Call ──────────────────────────────────────────────────────────

    def _call_llm(self, messages: list[dict]) -> Optional[str]:
        """Call QuickSilver API and return the text response."""
        import requests
        payload = {
            "model": QUICKSILVER_MODEL,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {QUICKSILVER_API_KEY}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            QUICKSILVER_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
            proxies={"http": None, "https": None},
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    # ── Tool Call Parsing ─────────────────────────────────────────────────

    def _parse_tool_calls(self, text: str) -> list[dict]:
        """Parse <tool_call> blocks from AI response text.

        Uses brace-counting to correctly extract nested JSON.
        Accepts both </tool_call> and </tool_calls> — LLMs output both variants.
        """
        calls = []
        start_tag = "<tool_call>"
        pos = 0
        while True:
            start = text.find(start_tag, pos)
            if start == -1:
                break
            content_start = start + len(start_tag)
            # Find whichever closing tag appears first
            end_s = text.find("</tool_call>", content_start)
            end_p = text.find("</tool_calls>", content_start)
            if end_s == -1 and end_p == -1:
                break
            if end_s == -1:
                end, end_tag = end_p, "</tool_calls>"
            elif end_p == -1:
                end, end_tag = end_s, "</tool_call>"
            else:
                end, end_tag = (end_s, "</tool_call>") if end_s < end_p else (end_p, "</tool_calls>")
            raw = text[content_start:end].strip()
            pos = end + len(end_tag)

            if not raw:
                continue

            brace_start = raw.find("{")
            if brace_start == -1:
                continue
            depth = 0
            json_end = -1
            for i in range(brace_start, len(raw)):
                ch = raw[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break
            if json_end == -1:
                continue

            block = raw[brace_start:json_end]
            try:
                parsed = json.loads(block)
                name = parsed.get("name", "")
                args = parsed.get("arguments", {})
                if name:
                    calls.append({"name": name, "arguments": args})
            except json.JSONDecodeError:
                continue
        return calls

    # ── Tool Execution ────────────────────────────────────────────────────

    def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool and return its result as a string."""
        try:
            if name == "read_file":
                path = args.get("path", "")
                if not path:
                    return "Error: 'path' argument is required"
                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                if not os.path.exists(safe) or os.path.isdir(safe):
                    return f"Error: File not found: {path}"
                with open(safe, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(12000)
                return content

            elif name == "list_files":
                file_list = []
                for root, dirs, files in os.walk(REPO_ROOT):
                    dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
                    for f in files:
                        if f in _IGNORE_FILES:
                            continue
                        rel = os.path.relpath(os.path.join(root, f), REPO_ROOT)
                        file_list.append(rel.replace("\\", "/"))
                return json.dumps(file_list[:300], indent=2)

            elif name == "git_history":
                result = subprocess.run(
                    ["git", "log", "-n", "10", "--oneline"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=TOOL_TIMEOUT,
                )
                if result.returncode == 0:
                    return result.stdout
                return f"Error: git log failed: {result.stderr}"

            elif name == "bridge_get":
                path = args.get("path", "")
                if not path:
                    return "Error: 'path' argument is required"
                import requests
                try:
                    r = requests.get(
                        f"{BRIDGE_BASE_URL}{path}",
                        timeout=5,
                        proxies={"http": None, "https": None},
                    )
                    if r.status_code == 200:
                        return json.dumps(r.json(), indent=2, default=str)
                    return f"Error: Bridge returned status {r.status_code}"
                except Exception as e:
                    return f"Error: Bridge request failed: {e}"

            elif name == "execute_shell":
                command = args.get("command", "")
                if not command:
                    return "Error: 'command' argument is required"
                result = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=TOOL_TIMEOUT,
                    shell=True,
                )
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr
                return output[:10000] if output else "(no output)"

            elif name == "current_time":
                return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ── #7 run_mythos ─────────────────────────────────────────────
            elif name == "run_mythos":
                # Run a specific Mythos variant (1-16) and return findings.
                # Variants are async functions in bridge/vapi_bridge/mythos_variants.py.
                variant_num = int(args.get("variant", 16))
                import asyncio as _aio
                import pathlib as _pl
                import sys as _sys

                bridge_path = os.path.join(REPO_ROOT, "bridge")
                if bridge_path not in _sys.path:
                    _sys.path.insert(0, bridge_path)

                # Canonical variant map (name → async function)
                MYTHOS_MAP = {
                    1:  ("frozen_drift",              "mythos_frozen_drift"),
                    2:  ("stability_sweep",           "mythos_stability_sweep"),
                    3:  ("operator_initiative_audit", "mythos_operator_initiative_audit"),
                    4:  ("live_gameplay_audit",       "mythos_live_gameplay_audit"),
                    5:  ("crypto_drift",              "mythos_crypto_drift"),
                    6:  ("qortroller_crypto_drift",   "mythos_qortroller_crypto_drift"),
                    7:  ("methodology_drift",         "mythos_methodology_drift"),
                    8:  ("ceremony_drift",            "mythos_ceremony_drift"),
                    9:  ("post_o3_ceremony_audit",    "mythos_post_o3_ceremony_audit"),
                    10: ("corpus_drift",              "mythos_corpus_drift"),
                    11: ("claude_md_curation",        "mythos_claude_md_curation"),
                    12: ("spending_log_drift",        "mythos_spending_log_drift"),
                    13: ("curator_graduation_audit",  "mythos_curator_graduation_audit"),
                    14: ("doc_number_consistency",    "mythos_doc_number_consistency"),
                    15: ("frontend_brand_drift",      "mythos_frontend_brand_drift"),
                    16: ("path_a_spec_impl_parity",   "mythos_path_a_spec_impl_parity"),
                    17: ("agent_utility_honesty",     "mythos_agent_utility_honesty"),
                }

                if variant_num not in MYTHOS_MAP:
                    valid = ", ".join(f"{k}={v[0]}" for k, v in MYTHOS_MAP.items())
                    return f"Error: unknown variant {variant_num}. Valid: {valid}"

                variant_label, fn_name = MYTHOS_MAP[variant_num]
                try:
                    from vapi_bridge import mythos_variants as _mv
                    fn = getattr(_mv, fn_name, None)
                    if fn is None:
                        return f"Error: {fn_name} not found in mythos_variants.py"

                    repo = _pl.Path(REPO_ROOT)

                    # Run in a fresh thread with its own event loop so we don't
                    # conflict with the daemon's running uvicorn event loop.
                    import concurrent.futures as _cf
                    def _run_in_thread():
                        loop = _aio.new_event_loop()
                        try:
                            return loop.run_until_complete(fn(repo_root=repo))
                        finally:
                            loop.close()

                    with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                        findings = pool.submit(_run_in_thread).result(timeout=60)
                except Exception as e:
                    return f"Error running variant {variant_num} ({variant_label}): {e}"

                if not findings:
                    return (
                        f"Mythos #{variant_num} ({variant_label}): "
                        f"0 findings — all checks passed."
                    )

                lines = [
                    f"Mythos #{variant_num} ({variant_label}): {len(findings)} finding(s)",
                    "─" * 52,
                ]
                # Sort by severity (CRITICAL > HIGH > MEDIUM > LOW)
                sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
                findings = sorted(findings, key=lambda f: sev_order.get(f.severity, 9))

                for f in findings[:15]:  # cap at 15 to stay within response limits
                    frozen_tag = " [FROZEN]" if f.frozen_region else ""
                    lines.append(
                        f"[{f.severity}{frozen_tag}] {f.description[:120]}"
                    )
                    if f.file_path:
                        lines.append(f"  file: {f.file_path}" +
                                     (f":{f.line_number}" if f.line_number else ""))
                    if f.recommended_fix:
                        lines.append(f"  fix:  {f.recommended_fix[:100]}")
                    lines.append("")

                if len(findings) > 15:
                    lines.append(f"... and {len(findings) - 15} more findings (run with variant for full output)")

                return "\n".join(lines)

            # ── #8 gic_replay ─────────────────────────────────────────────
            elif name == "gic_replay":
                # Replay the last N GIC links from the local DB and verify
                # chain integrity — same logic as bridge startup check but
                # callable from chat without starting the bridge.
                import sqlite3 as _sq
                import hashlib as _hl
                import struct as _st

                n = min(int(args.get("n", 20)), 200)
                session_id = args.get("session_id", "")

                db_path = os.path.join(REPO_ROOT, "bridge", "vapi_store.db")
                alt_db  = os.path.join(os.path.expanduser("~"), ".vapi", "bridge.db")
                db = db_path if os.path.exists(db_path) else (
                    alt_db if os.path.exists(alt_db) else None)

                if not db:
                    return ("No DB found at bridge/vapi_store.db or ~/.vapi/bridge.db. "
                            "Start the bridge at least once to create it.")

                try:
                    conn = _sq.connect(db)
                    conn.row_factory = _sq.Row

                    # Get session_id if not specified — use the most recent one
                    if not session_id:
                        row = conn.execute(
                            "SELECT grind_session_id FROM ruling_validation_log "
                            "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                            "ORDER BY id DESC LIMIT 1"
                        ).fetchone()
                        session_id = row["grind_session_id"] if row else ""

                    if not session_id:
                        conn.close()
                        return "No GIC-stamped rows found — grind has not started."

                    # Fetch last N GIC rows for this session
                    rows = conn.execute(
                        "SELECT id, grind_chain_hash, gic_ts_ns, "
                        "commitment_hash, pcc_host_state, fallback_verdict "
                        "FROM ruling_validation_log "
                        "WHERE grind_session_id = ? "
                        "AND grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                        "ORDER BY id ASC",
                        (session_id,)
                    ).fetchall()
                    total_links = len(rows)
                    rows = rows[-n:]  # take last N
                    conn.close()

                    if not rows:
                        return f"Session '{session_id}': no GIC-stamped rows found."

                    # GIC formula v1 (INV-GIC-001 FROZEN):
                    # GIC_N = SHA-256(prev_32B || commitment_32B || verdict_1B || host_1B || ts_ns_8B)
                    VERDICT_CODES = {
                        "CLEAR": 0x00, "CERTIFY": 0x01,
                        "FLAG":  0x10, "HOLD":   0x11, "BLOCK": 0x20,
                    }
                    HOST_CODES = {
                        "EXCLUSIVE_USB": 0x01, "UNKNOWN":      0x02,
                        "EXCLUSIVE_BT":  0x10, "CONTESTED":    0x20,
                        "DEGRADED":      0x30, "DISCONNECTED": 0xFF,
                    }
                    GENESIS_TAG = b"VAPI-GIC-GENESIS-v1"

                    def _genesis(sid: str, ts_ns: int) -> bytes:
                        pre = GENESIS_TAG + sid.encode("utf-8")
                        pre += ts_ns.to_bytes(8, "big")
                        return _hl.sha256(pre).digest()

                    def _compute(prev: bytes, commit_hex: str,
                                 host: str, verdict: str, ts_ns: int) -> bytes:
                        commit = bytes.fromhex(commit_hex.zfill(64)) if commit_hex else b"\x00" * 32
                        v_code = VERDICT_CODES.get(verdict, 0x10)
                        h_code = HOST_CODES.get(host, 0x02)
                        payload = (prev + commit +
                                   bytes([v_code, h_code]) +
                                   ts_ns.to_bytes(8, "big"))
                        return _hl.sha256(payload).digest()

                    # Replay
                    intact = True
                    broken_at = None
                    first_row = rows[0]
                    ts0 = int(first_row["gic_ts_ns"] or 0)

                    # If this is the very first row globally, seed with genesis
                    if total_links <= n:
                        prev = _genesis(session_id, ts0)
                    else:
                        # We're replaying a tail — can't fully verify without full history
                        prev = None

                    lines = [
                        "═" * 56,
                        f"  GIC REPLAY — session: {session_id}",
                        f"  Total links : {total_links}  |  Replaying last {len(rows)}",
                        "─" * 56,
                    ]

                    for i, row in enumerate(rows):
                        ts_ns   = int(row["gic_ts_ns"] or 0)
                        commit  = row["commitment_hash"] or ""
                        host    = row["pcc_host_state"] or "DISCONNECTED"
                        verdict = row["fallback_verdict"] or "FLAG"
                        stored  = row["grind_chain_hash"] or ""

                        if prev is None:
                            # Can't verify first row of a tail replay
                            status = "?"
                            lines.append(f"  [{i+1:4d}] {stored[:12]}... "
                                         f"verdict={verdict} host={host[:12]} [UNVERIFIABLE — tail]")
                            prev = bytes.fromhex(stored) if stored else b"\x00" * 32
                            continue

                        expected = _compute(prev, commit, host, verdict, ts_ns)
                        expected_hex = expected.hex()

                        if expected_hex == stored:
                            status = "OK"
                        else:
                            status = "BROKEN"
                            intact = False
                            if broken_at is None:
                                broken_at = i + 1

                        dt = datetime.datetime.fromtimestamp(ts_ns / 1e9).strftime("%H:%M:%S")
                        lines.append(
                            f"  [{i+1:4d}] {stored[:12]}... "
                            f"{dt} verdict={verdict} [{status}]"
                        )
                        prev = expected  # use computed for next link (catches drift early)

                    lines.append("─" * 56)
                    if prev is None:
                        lines.append("  Result: UNVERIFIABLE (tail replay, genesis not in window)")
                    elif intact:
                        lines.append(f"  Result: INTACT — all {len(rows)} replayed links verified ✓")
                    else:
                        lines.append(f"  Result: BROKEN at link {broken_at} — tamper or DB corruption")
                    lines.append("═" * 56)
                    return "\n".join(lines)

                except Exception as e:
                    return f"Error during GIC replay: {e}"

            # ── #1 GIC Chain Visualizer ───────────────────────────────────
            elif name == "gic_chain_status":
                # Pull GIC chain from bridge if up, else read DB directly.
                # Returns a visual ASCII chain + structured data.
                import requests as _req
                n = min(int(args.get("n", 20)), 100)  # last N links to render

                # Try bridge first (authoritative, live)
                try:
                    r = _req.get(f"{BRIDGE_BASE_URL}/bridge/grind-chain-status",
                                 timeout=4, proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        chain_len   = d.get("chain_length", 0)
                        intact      = d.get("chain_intact", True)
                        head        = d.get("latest_gic_hash", "")[:16]
                        session_id  = d.get("grind_session_id", "?")
                        genesis_ts  = d.get("genesis_ts", 0)
                        latest_ts   = d.get("latest_ts", 0)
                        # Also pull consecutive_clean from capture-health
                        cc = 0
                        try:
                            ch = _req.get(f"{BRIDGE_BASE_URL}/bridge/capture-health",
                                          timeout=3, proxies={"http": None, "https": None})
                            if ch.status_code == 200:
                                cc = ch.json().get("consecutive_clean_toward_target", 0)
                        except Exception:
                            pass

                        # ASCII chain visual
                        GATE = 100
                        filled = min(chain_len, n)
                        bar = ""
                        for i in range(filled):
                            bar += "[green]█[/green]"
                        for i in range(max(0, min(n, GATE) - filled)):
                            bar += "[dim]░[/dim]"

                        lines = [
                            "═" * 52,
                            f"  GIC CHAIN STATUS",
                            "═" * 52,
                            f"  Session   : {session_id}",
                            f"  Length    : {chain_len} links",
                            f"  Intact    : {'YES ✓' if intact else 'BROKEN ✗'}",
                            f"  Chain head: {head}{'...' if head else '(empty)'}",
                            f"  Consec.   : {cc} / {GATE}",
                            f"  Progress  : [{bar}] {chain_len}/{GATE}",
                            "─" * 52,
                            f"  Genesis   : {datetime.datetime.fromtimestamp(genesis_ts).isoformat() if genesis_ts else 'n/a'}",
                            f"  Latest    : {datetime.datetime.fromtimestamp(latest_ts).isoformat() if latest_ts else 'n/a'}",
                            "═" * 52,
                        ]
                        return "\n".join(lines)
                except Exception:
                    pass

                # Bridge down — try reading DB directly
                db_path = os.path.join(REPO_ROOT, "bridge", "vapi_store.db")
                alt_db  = os.path.join(os.path.expanduser("~"), ".vapi", "bridge.db")
                db = db_path if os.path.exists(db_path) else (alt_db if os.path.exists(alt_db) else None)
                if not db:
                    return "Bridge offline and no local DB found at bridge/vapi_store.db or ~/.vapi/bridge.db"

                import sqlite3 as _sq
                try:
                    conn = _sq.connect(db)
                    row = conn.execute(
                        "SELECT COUNT(*), MAX(gic_ts_ns), MIN(gic_ts_ns), "
                        "MAX(grind_chain_hash), grind_session_id "
                        "FROM ruling_validation_log "
                        "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != ''"
                    ).fetchone()
                    conn.close()
                    if not row or not row[0]:
                        return "DB: no GIC-stamped rows found (grind not started)"
                    count, max_ts, min_ts, head, sid = row
                    GATE = 100
                    bar = "█" * min(count, n) + "░" * max(0, min(n, GATE) - min(count, n))
                    genesis_dt = datetime.datetime.fromtimestamp(int(min_ts)/1e9).isoformat() if min_ts else "n/a"
                    latest_dt  = datetime.datetime.fromtimestamp(int(max_ts)/1e9).isoformat() if max_ts else "n/a"
                    return (
                        f"GIC CHAIN (from local DB)\n"
                        f"Session   : {sid}\n"
                        f"Length    : {count} links\n"
                        f"Chain head: {(head or '')[:16]}...\n"
                        f"Progress  : [{bar}] {count}/{GATE}\n"
                        f"Genesis   : {genesis_dt}\n"
                        f"Latest    : {latest_dt}\n"
                        f"(chain_intact not recomputed — bridge required for full verification)"
                    )
                except Exception as e:
                    return f"DB read failed: {e}"

            # ── #6 query_chain ────────────────────────────────────────────
            elif name == "query_chain":
                """Query IoTeX testnet directly. Supports:
                  wallet_balance           — balance of active deployer wallet
                  eth_getBalance [address] — balance of any address
                  eth_call [to] [data]     — generic eth_call to any contract
                  eth_call [contract] [fn_selector] [args...] — lookup by contract name
                  is_fully_eligible [device_id] — VAPIProtocolLens check
                  get_device_tier [device_id]  — device tier classification
                  beacon_registry          — TemporalBeacon anchor block
                  block_number             — current IoTeX testnet block
                  all [device_id]          — all of the above
                Uses urllib directly, no web3.py dependency."""
                import urllib.request as _ur

                RPC = "https://babel-api.testnet.iotex.io"
                WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"

                # --- helpers ---
                def _eth_call(to_addr: str, call_data: str) -> str:
                    res = _rpc("eth_call", [{"to": to_addr, "data": call_data}, "latest"])
                    return res.get("result", "0x")

                # Load deployed addresses once
                addr_path = os.path.join(REPO_ROOT, "contracts", "deployed-addresses.json")
                try:
                    with open(addr_path) as f:
                        addrs = json.load(f)
                except Exception as e:
                    return f"Error: cannot read deployed-addresses.json: {e}"

                def _rpc(method, params):
                    payload = json.dumps({
                        "jsonrpc": "2.0", "id": 1,
                        "method": method, "params": params,
                    }).encode()
                    req = _ur.Request(RPC, data=payload, headers={
                        "Content-Type": "application/json",
                        "User-Agent": "QorTroller-Daemon/2.0",
                    })
                    with _ur.urlopen(req, timeout=10) as resp:
                        return json.loads(resp.read())

                query = args.get("query", "wallet_balance").lower()
                lines = []

                # ── wallet_balance ─────────────────────────────────────────
                if query in ("wallet_balance", "all", ""):
                    res = _rpc("eth_getBalance", [WALLET, "latest"])
                    wei = int(res["result"], 16)
                    lines.append(f"Active wallet ({WALLET[:10]}...): {wei/1e18:.6f} IOTX")

                # ── eth_getBalance (generic, any address) ──────────────────
                if query == "eth_getBalance":
                    address = args.get("address", WALLET)
                    if not address.startswith("0x"):
                        address = WALLET
                    try:
                        res = _rpc("eth_getBalance", [address, "latest"])
                        wei = int(res["result"], 16)
                        lines.append(f"Balance({address[:10]}...): {wei/1e18:.6f} IOTX ({wei:,} wei)")
                    except Exception as e:
                        lines.append(f"eth_getBalance failed: {e}")

                # ── eth_call (generic, any contract, any function) ─────────
                if query == "eth_call":
                    to_addr = args.get("to", "")
                    call_data = args.get("data", "0x")
                    contract_name = args.get("contract", "")

                    # Resolve contract name to address
                    if contract_name and not to_addr:
                        for k, v in addrs.items():
                            if k.lower() == contract_name.lower() or contract_name.lower() in k.lower():
                                to_addr = v
                                break
                        if not to_addr:
                            lines.append(f"No contract matching '{contract_name}' in deployed-addresses.json")
                            to_addr = ""

                    # Resolve function selector
                    fn_selector = args.get("fn_selector", "")
                    if fn_selector and not call_data.startswith("0x"):
                        call_data = fn_selector

                    if not to_addr:
                        lines.append("Provide 'to' (address) or 'contract' (name from deployed-addresses.json)")
                    elif not call_data or not call_data.startswith("0x"):
                        lines.append("Provide 'data' (0x4-byte-selector + args) or 'fn_selector' (0x4-byte)")
                    else:
                        try:
                            res_str = _eth_call(to_addr, call_data)
                            label = contract_name or to_addr[:10]
                            if res_str and res_str != "0x":
                                try:
                                    val = int(res_str, 16)
                                    lines.append(f"eth_call({label}): {res_str[:66]} (int: {val:,})")
                                except ValueError:
                                    lines.append(f"eth_call({label}): 0x{res_str[:200]}")
                            else:
                                lines.append(f"eth_call({label}): empty/zero result")
                        except Exception as e:
                            lines.append(f"eth_call failed: {e}")

                # ── is_fully_eligible (via VAPIProtocolLens) ───────────────
                if query in ("is_fully_eligible", "all"):
                    device_id = args.get("device_id", "")
                    lens_addr = addrs.get("VAPIProtocolLensV2", addrs.get("VAPIProtocolLens", ""))
                    if not lens_addr:
                        lines.append("isFullyEligible: VAPIProtocolLens address not found")
                    elif not device_id:
                        lines.append("isFullyEligible: provide device_id argument (32-byte hex)")
                    else:
                        selector = "0x5f04e8a4"  # keccak4("isFullyEligible(bytes32)")
                        padded = device_id.replace("0x", "").zfill(64)
                        res_str = _eth_call(lens_addr, selector + padded)
                        eligible = res_str.endswith("1")
                        lines.append(f"isFullyEligible({device_id[:10]}...): {eligible}")

                # ── get_device_tier ────────────────────────────────────────
                if query in ("get_device_tier", "all"):
                    device_id = args.get("device_id", "")
                    lens_addr = addrs.get("VAPIProtocolLensV2", addrs.get("VAPIProtocolLens", ""))
                    if lens_addr and device_id:
                        selector = "0x7f87d5c3"  # keccak4("getDeviceTier(bytes32)")
                        padded = device_id.replace("0x", "").zfill(64)
                        res_str = _eth_call(lens_addr, selector + padded)
                        tier = int(res_str, 16) if res_str and res_str != "0x" else 0
                        tier_name = {1: "FULL (CFI-ZCP1)", 2: "STANDARD (CFI-ZCT1)", 3: "BASIC"}.get(tier, f"UNKNOWN ({tier})")
                        lines.append(f"getDeviceTier({device_id[:10]}...): {tier_name}")

                # ── beacon_registry ────────────────────────────────────────
                if query in ("beacon_registry", "all"):
                    tbr_addr = addrs.get("VAPITemporalBeaconRegistry", "")
                    if tbr_addr:
                        selector = "0x5a2e3b93"  # keccak4("latestBeacon()")
                        res_str = _eth_call(tbr_addr, selector)
                        if res_str and res_str != "0x" and len(res_str) > 2:
                            block_num = int(res_str[2:66], 16) if len(res_str) >= 66 else 0
                            lines.append(f"TemporalBeaconRegistry: latest anchor block={block_num}")
                        else:
                            lines.append("TemporalBeaconRegistry: no beacon anchored yet")
                    else:
                        lines.append("TemporalBeaconRegistry: address not found")

                # ── block_number ───────────────────────────────────────────
                if query in ("block_number", "all"):
                    res = _rpc("eth_blockNumber", [])
                    block = int(res["result"], 16)
                    lines.append(f"IoTeX testnet block: {block:,}")

                if not lines:
                    lines.append(
                        f"Unknown query '{query}'. Valid: wallet_balance, eth_getBalance, "
                        f"eth_call, is_fully_eligible, get_device_tier, beacon_registry, "
                        f"block_number, all"
                    )

                return "\n".join(lines)

            elif name == "calibration_status":
                import requests as _req
                lines = ["═" * 52, "  CALIBRATION & ENROLLMENT STATUS", "═" * 52]

                # 1. L4 thresholds from calibration_profile_live.json
                cal_path = os.path.join(REPO_ROOT, "calibration_profile_live.json")
                try:
                    with open(cal_path) as f:
                        cal = json.load(f)
                    thr = cal.get("thresholds", {})
                    lines += [
                        "  L4 Thresholds (live calibration):",
                        f"    anomaly    : {thr.get('l4_anomaly', '?'):.4f}  (baseline 7.009)",
                        f"    continuity : {thr.get('l4_continuity', '?'):.4f}  (baseline 5.367)",
                        f"    total recs : {cal.get('total_records', '?')}",
                        f"    confidence : {cal.get('confidence', '?')}",
                        f"    generated  : {cal.get('generated_at', '?')}",
                        "─" * 52,
                    ]
                except Exception as e:
                    lines.append(f"  calibration_profile_live.json: {e}")

                # 2. Separation ratio from bridge
                for ep, label in [
                    ("/agent/separation-ratio-status", "Separation Ratio"),
                    ("/agent/separation-defensibility-status", "AIT Defensibility"),
                ]:
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"  {label}:")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                        else:
                            lines.append(f"  {label}: HTTP {r.status_code} (bridge may be down)")
                    except Exception:
                        lines.append(f"  {label}: bridge offline")

                lines.append("─" * 52)

                # 3. GIC / grind progress
                try:
                    r = _req.get(f"{BRIDGE_BASE_URL}/bridge/grind-chain-status", timeout=4,
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        chain_len = d.get("chain_length", 0)
                        intact    = d.get("chain_intact", True)
                        GATE = 100
                        pct = min(100, round(chain_len / GATE * 100))
                        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                        lines += [
                            "  Grind Integrity Chain:",
                            f"    length  : {chain_len} / {GATE}",
                            f"    intact  : {'YES' if intact else 'BROKEN'}",
                            f"    progress: [{bar}] {pct}%",
                        ]
                except Exception:
                    lines.append("  GIC: bridge offline")

                lines.append("─" * 52)

                # 4. Tournament preflight gate
                try:
                    r = _req.get(f"{BRIDGE_BASE_URL}/agent/tournament-preflight", timeout=4,
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        overall = d.get("overall_pass", False)
                        lines.append(f"  Tournament gate: {'PASS ✓' if overall else 'NOT READY'}")
                        conds = d.get("conditions", {})
                        for k, v in conds.items():
                            icon = "✓" if v else "✗"
                            lines.append(f"    [{icon}] {k}")
                except Exception:
                    lines.append("  Tournament gate: bridge offline")

                lines.append("═" * 52)
                return "\n".join(lines)

            elif name == "write_file":
                path = args.get("path", "")
                content = args.get("content", "")
                if not path:
                    return "Error: 'path' argument is required"
                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                # Block writes to sensitive files
                blocked = {".env", "bridge/.env", "scripts/vapi_invariant_gate.py",
                           ".github/INVARIANTS_ALLOWLIST.json"}
                rel = os.path.relpath(safe, REPO_ROOT).replace("\\", "/")
                if rel in blocked:
                    return f"Error: Write to '{rel}' is blocked — use Claude Code for protocol files"
                os.makedirs(os.path.dirname(safe), exist_ok=True)
                with open(safe, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"OK: wrote {len(content)} chars to {rel}"

            elif name == "search_code":
                pattern = args.get("pattern", "")
                file_glob = args.get("glob", "")
                if not pattern:
                    return "Error: 'pattern' argument is required"
                cmd = ["python", "-m", "grep_module"] if False else None
                # Use ripgrep if available, else fall back to git grep
                rg_cmd = ["rg", "--no-heading", "-n", "--max-count=5",
                          "--max-filesize=500K"]
                if file_glob:
                    rg_cmd += ["--glob", file_glob]
                rg_cmd += [pattern, REPO_ROOT]
                result = subprocess.run(
                    rg_cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT
                )
                if result.returncode in (0, 1):  # 1 = no matches (not an error)
                    out = result.stdout[:8000] or "(no matches)"
                    # Make paths relative
                    out = out.replace(REPO_ROOT + os.sep, "").replace(REPO_ROOT + "/", "")
                    return out
                # Fallback: git grep
                git_cmd = ["git", "grep", "-n", "--max-count=5", pattern]
                if file_glob:
                    git_cmd += ["--", file_glob]
                result2 = subprocess.run(
                    git_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=TOOL_TIMEOUT
                )
                return result2.stdout[:8000] or "(no matches)"

            elif name == "git_log_full":
                ref = args.get("ref", "HEAD")
                n = min(int(args.get("n", 5)), 20)
                result = subprocess.run(
                    ["git", "log", f"-n{n}", "--stat", "--format=%H%n%s%n%b%n---", ref],
                    cwd=REPO_ROOT, capture_output=True, text=True, timeout=TOOL_TIMEOUT,
                )
                if result.returncode == 0:
                    return result.stdout[:8000]
                return f"Error: {result.stderr}"

            elif name == "bridge_post":
                path = args.get("path", "")
                payload = args.get("payload", {})
                api_key = args.get("api_key", OPERATOR_API_KEY)
                if not path:
                    return "Error: 'path' argument is required"
                import requests
                try:
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        headers["x-api-key"] = api_key
                    r = requests.post(
                        f"{BRIDGE_BASE_URL}{path}",
                        json=payload,
                        headers=headers,
                        timeout=10,
                        proxies={"http": None, "https": None},
                    )
                    return json.dumps(r.json(), indent=2, default=str)
                except Exception as e:
                    return f"Error: Bridge POST failed: {e}"

            elif name == "run_invariant_gate":
                result = subprocess.run(
                    ["python", "scripts/vapi_invariant_gate.py"],
                    cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
                )
                out = result.stdout + result.stderr
                return out[:6000] or "(no output)"

            elif name == "poac_status":
                # Single-call QorTroller status summary: GIC, capture health,
                # separation ratio, contract count, wallet — from live bridge + files
                import requests
                lines = []
                # Bridge endpoints (best-effort)
                for ep, label in [
                    ("/bridge/grind-chain-status", "GIC"),
                    ("/bridge/capture-health", "PCC"),
                    ("/agent/separation-status", "Separation"),
                    ("/agent/tournament-preflight", "Tournament"),
                ]:
                    try:
                        r = requests.get(
                            f"{BRIDGE_BASE_URL}{ep}", timeout=3,
                            proxies={"http": None, "https": None}
                        )
                        if r.status_code == 200:
                            data = r.json()
                            lines.append(f"[{label}] {json.dumps(data, default=str)[:300]}")
                        else:
                            lines.append(f"[{label}] HTTP {r.status_code}")
                    except Exception as e:
                        lines.append(f"[{label}] offline ({e})")
                # Deployed contract count from file
                try:
                    addr_path = os.path.join(REPO_ROOT, "contracts", "deployed-addresses.json")
                    with open(addr_path, "r") as f:
                        addrs = json.load(f)
                    addr_keys = [k for k in addrs if not k.startswith("_") and
                                 k.endswith(("Registry", "Gate", "Token", "Verifier",
                                             "Manager", "Lens", "Badge", "Oracle",
                                             "Credential", "Bus", "Notary", "Anchor",
                                             "Beacon", "Manifest"))]
                    lines.append(f"[Contracts] {len(addrs)} total keys in deployed-addresses.json")
                except Exception as e:
                    lines.append(f"[Contracts] could not read: {e}")
                # Git HEAD
                r2 = subprocess.run(
                    ["git", "log", "-1", "--oneline"],
                    cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
                )
                lines.append(f"[HEAD] {r2.stdout.strip()}")
                return "\n".join(lines)

            elif name == "list_contracts":
                try:
                    addr_path = os.path.join(REPO_ROOT, "contracts", "deployed-addresses.json")
                    with open(addr_path, "r") as f:
                        addrs = json.load(f)
                    rows = []
                    for k, v in addrs.items():
                        if k.startswith("_"):
                            rows.append(f"  [meta] {k}: {str(v)[:80]}")
                        else:
                            rows.append(f"  {k}: {v}")
                    return f"deployed-addresses.json ({len(addrs)} entries):\n" + "\n".join(rows)
                except Exception as e:
                    return f"Error: {e}"

            # ════════════════════════════════════════════════════════════════
            #  PROTOCOL-NATIVE TOOLS — Domain-level wrappers for the VAPI
            #  protocol layers. These aggregate multiple bridge /agent/*
            #  endpoints into single semantic queries the brain can reason
            #  about without raw HTTP calls.
            # ════════════════════════════════════════════════════════════════

            # ── #1 protocol_phase ────────────────────────────────────────
            elif name == "protocol_phase":
                """Live phase context: phase number, bridge/SDK/Hardhat counts,
                agent count, contract count, git HEAD."""
                import requests as _req
                lines = ["─" * 52, "  PROTOCOL PHASE CONTEXT", "─" * 52]

                # Git HEAD
                try:
                    r2 = subprocess.run(["git", "log", "-1", "--oneline"],
                                        cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
                    lines.append(f"  Git HEAD : {r2.stdout.strip()}")
                except Exception:
                    lines.append("  Git HEAD : (unknown)")

                # Phase from bridge health/status or config
                try:
                    r = _req.get(f"{BRIDGE_BASE_URL}/health", timeout=4,
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        lines.append(f"  Bridge   : {'UP' if d.get('status') == 'ok' else 'DEGRADED'}")
                        lines.append(f"  Phase    : {d.get('phase', '?')}")
                        lines.append(f"  Agents   : {d.get('agents', '?')}")
                        lines.append(f"  Contracts: {d.get('contracts', '?')}")
                    else:
                        lines.append("  Bridge   : DOWN (HTTP {r.status_code})")
                except Exception:
                    lines.append("  Bridge   : OFFLINE — cannot query live phase")

                # Try reading bridge config for phase
                try:
                    cfg_path = os.path.join(REPO_ROOT, "bridge", "vapi_bridge", "config.py")
                    if os.path.exists(cfg_path):
                        with open(cfg_path) as f:
                            cfg_text = f.read(8000)
                        for line in cfg_text.splitlines():
                            if "PHASE" in line and "=" in line and not line.strip().startswith("#"):
                                lines.append(f"  Config   : {line.strip()}")
                except Exception:
                    pass

                # Contract count from deployed-addresses.json
                try:
                    addr_path = os.path.join(REPO_ROOT, "contracts", "deployed-addresses.json")
                    with open(addr_path) as f:
                        addrs = json.load(f)
                    contract_keys = [k for k in addrs if not k.startswith("_") and
                                     k.endswith(("Registry", "Gate", "Token", "Verifier",
                                                 "Manager", "Lens", "Badge", "Oracle",
                                                 "Credential", "Bus", "Notary", "Anchor",
                                                 "Beacon", "Manifest", "Wallet"))]
                    lines.append(f"  Contracts : {len(contract_keys)} deployed")
                except Exception:
                    pass

                # Try reading last-known phase from VAPI_AGENTS.md if available
                try:
                    va_path = os.path.join(REPO_ROOT, "VAPI_AGENTS.md")
                    if os.path.exists(va_path):
                        with open(va_path) as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("Phase ") and line[6:9].isdigit():
                                    lines.append(f"  Last phase: {line.split('—')[0].strip()}")
                                    break
                except Exception:
                    pass

                lines.append("─" * 52)
                return "\n".join(lines)

            # ── #2 tournament_readiness ──────────────────────────────────
            elif name == "tournament_readiness":
                """Tournament eligibility gate: preflight pass/fail,
                all P0 conditions, blockers, separation defensibility."""
                import requests as _req
                lines = ["─" * 52, "  TOURNAMENT READINESS", "─" * 52]

                endpoints = {
                    "/agent/tournament-preflight": "Preflight Gate",
                    "/agent/tournament-blocker-summary": "Blocker Summary",
                    "/agent/tournament-readiness-score": "Readiness Score",
                    "/agent/separation-defensibility-status": "Separation Defensibility",
                    "/agent/per-pair-gap-status": "Per-Pair Gap Status",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    icon = "✓" if v is True else ("✗" if v is False else "")
                                    lines.append(f"    {k}: {icon} {v}")
                                elif isinstance(v, dict):
                                    lines.append(f"    {k}: (nested)")
                                elif isinstance(v, list) and len(v) <= 5:
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list):
                                    lines.append(f"    {k}: [{len(v)} entries]")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #3 separation_deep_dive ──────────────────────────────────
            elif name == "separation_deep_dive":
                """Deep inter-player separation analysis: ratio, per-pair gaps,
                LOO accuracy, trends, projections, blocker pairs.
                Optional session_type filter: 'ait', 'touchpad_corners', etc."""
                import requests as _req
                session_type = args.get("session_type", "")
                lines = ["─" * 52, "  SEPARATION DEEP DIVE", "─" * 52]

                if session_type:
                    lines.append(f"  Session type filter: {session_type}")

                endpoints = [
                    "/agent/separation-ratio-status",
                    "/agent/per-pair-gap-status",
                    "/agent/per-pair-gap-trend",
                    "/agent/per-pair-gap-projection",
                ]
                for ep in endpoints:
                    url = f"{BRIDGE_BASE_URL}{ep}"
                    if session_type:
                        url += f"?session_type={session_type}"
                    try:
                        r = _req.get(url, timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            label = ep.split("/")[-1].replace("-", " ").title()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list) and len(v) <= 5:
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list):
                                    lines.append(f"    {k}: [{len(v)} entries]")
                                elif isinstance(v, dict):
                                    lines.append(f"    {k}: (nested)")
                        else:
                            lines.append(f"\n  [{ep}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{ep}] offline")

                # Add AIT-specific status if relevant
                if session_type in ("", "ait"):
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}/agent/ait-separation-status", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [AIT Separation Status]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                    except Exception:
                        pass

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #4 biometric_vault ───────────────────────────────────────
            elif name == "biometric_vault":
                """Biometric credential lifecycle: VHP status, TTL,
                renewal chain, dual primitive gate, confidence multiplier."""
                import requests as _req
                lines = ["─" * 52, "  BIOMETRIC VAULT STATUS", "─" * 52]

                endpoints = {
                    "/agent/biometric-credential-age": "Credential Age/TTL",
                    "/agent/biometric-ttl-scaling-status": "TTL Decay Scaling",
                    "/agent/renewal-chain-status": "Renewal Chain",
                    "/agent/vhp-dual-gate-log": "Dual Primitive Gate",
                    "/agent/confidence-score-multiplier-status": "Confidence Multiplier",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, dict):
                                    lines.append(f"    {k}: (nested)")
                                elif isinstance(v, list) and len(v) <= 3:
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list):
                                    lines.append(f"    {k}: [{len(v)} entries]")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #5 governance_audit ──────────────────────────────────────
            elif name == "governance_audit":
                """Governance & invariants: invariant gate pass/fail,
                allowlist chain integrity, governance history, BBG status,
                protocol metabolism index."""
                import requests as _req
                lines = ["─" * 52, "  GOVERNANCE & INVARIANTS", "─" * 52]

                endpoints = {
                    "/agent/invariant-gate-status": "PV-CI Invariant Gate",
                    "/agent/allowlist-governance-history": "Allowlist Governance",
                    "/agent/bbg-status": "Biometric Governance (BBG)",
                    "/agent/protocol-metabolism-index": "Protocol Metabolism",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif k == "entries" and isinstance(v, list):
                                    lines.append(f"    entries: [{len(v)} records]")
                                elif isinstance(v, dict):
                                    lines.append(f"    {k}: (nested)")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                # Also run invariant gate if requested
                if args.get("run_invariant", False):
                    lines.append("\n  Running PV-CI invariant gate...")
                    try:
                        result = subprocess.run(
                            ["python", "scripts/vapi_invariant_gate.py"],
                            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
                        )
                        output = (result.stdout + result.stderr)[:2000]
                        lines.append(f"  Result:\n{output}")
                    except Exception as e:
                        lines.append(f"  Error: {e}")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #6 fleet_coherence ───────────────────────────────────────
            elif name == "fleet_coherence":
                """Fleet signal coherence: contradictions, orphans, inversions,
                persistent entries, coherence fingerprint summary."""
                import requests as _req
                lines = ["─" * 52, "  FLEET SIGNAL COHERENCE", "─" * 52]

                endpoints = {
                    "/agent/coherence-fingerprint-status": "Fingerprint Registry",
                    "/agent/context-integrity-status": "Agent Context Integrity",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list) and len(v) <= 5:
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list):
                                    lines.append(f"    {k}: [{len(v)} entries]")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                # Try fleet coherence summary via dedicated tool endpoint
                try:
                    r = _req.get(
                        f"{BRIDGE_BASE_URL}/agent/fleet-coherence-summary", timeout=4,
                        proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        lines.append(f"\n  [Fleet Coherence Summary]")
                        for k, v in d.items():
                            if isinstance(v, (int, float, bool, str)):
                                lines.append(f"    {k}: {v}")
                except Exception:
                    pass

                # Check fleet coherence agent coh_ entries if available
                try:
                    r = _req.get(
                        f"{BRIDGE_BASE_URL}/agent/fleet-coherence-entries?limit=5", timeout=4,
                        proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        entries = d if isinstance(d, list) else d.get("entries", [])
                        if entries:
                            lines.append(f"\n  [Recent Coherence Entries ({len(entries)})]")
                            for entry in entries[:5]:
                                rule = entry.get("rule_name", entry.get("rule", "?"))
                                sev = entry.get("severity", "?")
                                lines.append(f"    • {rule} ({sev})")
                except Exception:
                    pass

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #7 corpus_health ─────────────────────────────────────────
            elif name == "corpus_health":
                """Calibration corpus health: capture velocity, stagnation,
                data readiness, regression guard, AIT/tremor probe status."""
                import requests as _req
                lines = ["─" * 52, "  CORPUS DATA HEALTH", "─" * 52]

                endpoints = {
                    "/agent/capture-velocity-oracle": "Capture Velocity Oracle",
                    "/agent/tremor-convergence-status": "Tremor Convergence",
                    "/agent/tremor-resting-probe-status": "Tremor Resting Probe",
                    "/agent/corpus-regression-guard-status": "Regression Guard",
                    "/agent/data-readiness-certificate-status": "Data Readiness",
                    "/agent/l4-dim-sync-status": "L4 Dim Sync",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, dict):
                                    lines.append(f"    {k}: (nested)")
                                elif isinstance(v, list) and len(v) <= 3:
                                    lines.append(f"    {k}: {v}")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #8 l4_calibration ────────────────────────────────────────
            elif name == "l4_calibration":
                """L4 threshold system: calibration staleness, per-battery
                tracks, router status, dim sync confirmation."""
                import requests as _req
                lines = ["─" * 52, "  L4 CALIBRATION SYSTEM", "─" * 52]

                # From calibration_profile_live.json
                cal_path = os.path.join(REPO_ROOT, "calibration_profile_live.json")
                try:
                    with open(cal_path) as f:
                        cal = json.load(f)
                    thr = cal.get("thresholds", {})
                    lines.extend([
                        "  Live calibration file:",
                        f"    Anomaly    : {thr.get('l4_anomaly', '?'):.4f}  (baseline 7.009)",
                        f"    Continuity : {thr.get('l4_continuity', '?'):.4f}  (baseline 5.367)",
                        f"    Records    : {cal.get('total_records', '?')}",
                        f"    Confidence : {cal.get('confidence', '?')}",
                        f"    Generated  : {cal.get('generated_at', '?')}",
                    ])
                except Exception as e:
                    lines.append(f"  calibration_profile_live.json: error reading ({e})")

                # Bridge endpoints
                for ep, label in [
                    ("/agent/l4-calibration-status", "Calibration Staleness"),
                    ("/agent/l4-router-status", "L4 Router"),
                    ("/agent/l4-threshold-tracks", "Per-Battery Tracks"),
                    ("/agent/l4-dim-sync-status", "Dim Sync"),
                    ("/agent/accel-tremor-fft-status", "Accel Tremor FFT"),
                ]:
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #9 epoch_windows ─────────────────────────────────────────
            elif name == "epoch_windows":
                """Epoch window: analytics, auto-tune recommendation,
                device heatmap, override status."""
                import requests as _req
                lines = ["─" * 52, "  EPOCH WINDOW SYSTEM", "─" * 52]

                endpoints = {
                    "/agent/epoch-window-analytics": "Analytics",
                    "/agent/epoch-window-auto-tune": "Auto-Tune Advisor",
                    "/agent/epoch-window-device-heatmap": "Device Heatmap",
                    "/agent/epoch-window-override-status": "Override Status",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list) and len(v) <= 5:
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, list):
                                    lines.append(f"    {k}: [{len(v)} entries]")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #10 protocol_maturity ────────────────────────────────────
            elif name == "protocol_maturity":
                """Protocol maturity score with all components:
                separation, freshness, calibration, PITL, ioSwarm,
                dry-run, threat forecast, biometric stationarity, PMI."""
                import requests as _req
                lines = ["─" * 52, "  PROTOCOL MATURITY", "─" * 52]

                endpoints = {
                    "/agent/protocol-maturity-score": "Maturity Score",
                    "/agent/protocol-coherence-status": "Protocol Coherence (PoPC)",
                    "/agent/protocol-metabolism-index": "Metabolism Index (PMI)",
                }
                for ep, label in endpoints.items():
                    try:
                        r = _req.get(f"{BRIDGE_BASE_URL}{ep}", timeout=4,
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"\n  [{label}]")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                                elif isinstance(v, dict):
                                    lines.append(f"    {k}: (nested)")
                        else:
                            lines.append(f"\n  [{label}] HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"\n  [{label}] offline")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #11 chain_overview ───────────────────────────────────────
            elif name == "chain_overview":
                """Live on-chain overview: wallet balance, block number,
                last beacon anchor, all contract addresses grouped by role."""
                import requests as _req
                lines = ["─" * 52, "  ON-CHAIN OVERVIEW", "─" * 52]

                # Load deployed addresses
                addr_path = os.path.join(REPO_ROOT, "contracts", "deployed-addresses.json")
                try:
                    with open(addr_path) as f:
                        addrs = json.load(f)
                except Exception as e:
                    return f"Error: cannot read deployed-addresses.json: {e}"

                WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
                RPC = "https://babel-api.testnet.iotex.io"

                # Call IoTeX RPC directly
                import urllib.request as _ur
                def _rpc(method, params):
                    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
                    req = _ur.Request(RPC, data=payload, headers={
                        "Content-Type": "application/json", "User-Agent": "QorTroller-Daemon/2.0"})
                    with _ur.urlopen(req, timeout=10) as resp:
                        return json.loads(resp.read())

                try:
                    res = _rpc("eth_getBalance", [WALLET, "latest"])
                    wei = int(res["result"], 16)
                    lines.append(f"  Wallet {WALLET[:10]}...: {wei/1e18:.4f} IOTX")
                except Exception as e:
                    lines.append(f"  Wallet: RPC error ({e})")

                try:
                    res = _rpc("eth_blockNumber", [])
                    block = int(res["result"], 16)
                    lines.append(f"  IoTeX block: {block:,}")
                except Exception:
                    lines.append("  IoTeX block: RPC error")

                # Deployed address summary by category
                categories = {
                    "Gate/Verifier": [],
                    "Registry": [],
                    "Token/Credential": [],
                    "Oracle/Agent": [],
                    "Governance": [],
                    "Infrastructure": [],
                    "Badge/Anchor": [],
                }
                for k, v in addrs.items():
                    if k.startswith("_"):
                        continue
                    if any(g in k for g in ("Gate", "Verifier", "Filter")):
                        categories["Gate/Verifier"].append((k, v))
                    elif any(r in k for r in ("Registry", "Bus", "Notary")):
                        categories["Registry"].append((k, v))
                    elif any(t in k for t in ("Token", "Credential", "VHP")):
                        categories["Token/Credential"].append((k, v))
                    elif any(o in k for o in ("Oracle", "Lens", "Agent")):
                        categories["Oracle/Agent"].append((k, v))
                    elif any(g in k for g in ("Governance", "Timelock", "Proposal")):
                        categories["Governance"].append((k, v))
                    elif any(b in k for b in ("Beacon", "Anchor", "Manifest")):
                        categories["Infrastructure"].append((k, v))
                    else:
                        categories["Badge/Anchor"].append((k, v))

                for cat, entries in categories.items():
                    if entries:
                        lines.append(f"\n  {cat} ({len(entries)}):")
                        for name, addr in entries[:8]:
                            lines.append(f"    {name}: {addr[:10]}...{addr[-4:]}")
                        if len(entries) > 8:
                            lines.append(f"    ... and {len(entries) - 8} more")

                total = len([k for k in addrs if not k.startswith("_")])
                lines.append(f"\n  Total deployed: {total} contracts")

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── #12 daemon_diagnose ──────────────────────────────────────
            elif name == "daemon_diagnose":
                """Daemon self-diagnostic: bridge connectivity, LLM status,
                DB size, tools count, memory store health, system uptime."""
                import requests as _req
                lines = ["─" * 52, "  DAEMON SELF-DIAGNOSE", "─" * 52]

                # Memory store status
                try:
                    status = self.memory.get_status()
                    mc = status.get("message_count", 0)
                    bs = status.get("brain_status", "?")
                    lines.append(f"  Brain        : {bs}")
                    lines.append(f"  Messages     : {mc}")
                except Exception as e:
                    lines.append(f"  Memory store : ERROR ({e})")

                # LLM status
                lines.append(f"  LLM model    : {QUICKSILVER_MODEL}")
                lines.append(f"  LLM key      : {'CONFIGURED' if QUICKSILVER_API_KEY else 'MISSING'}")
                if QUICKSILVER_API_KEY:
                    try:
                        r = _req.post(QUICKSILVER_API_URL,
                                      json={"model": QUICKSILVER_MODEL, "messages": [{"role": "user", "content": "ping"}]},
                                      headers={"Authorization": f"Bearer {QUICKSILVER_API_KEY}", "Content-Type": "application/json"},
                                      timeout=10, proxies={"http": None, "https": None})
                        lines.append(f"  LLM ping     : {'OK' if r.status_code == 200 else f'HTTP {r.status_code}'}")
                    except Exception as e:
                        lines.append(f"  LLM ping     : FAILED ({e})")

                # Bridge connectivity
                try:
                    r = _req.get(f"{BRIDGE_BASE_URL}/health", timeout=4,
                                 proxies={"http": None, "https": None})
                    lines.append(f"  Bridge       : {'UP' if r.status_code == 200 else f'HTTP {r.status_code}'}")
                except Exception:
                    lines.append(f"  Bridge       : OFFLINE")

                # Daemon self
                lines.append(f"  Daemon port  : {PORT}")
                lines.append(f"  Version      : {APP_VERSION} ({DAEMON_VERSION})")
                lines.append(f"  DB path      : {SQLITE_DB_PATH}")

                # DB file size
                try:
                    if os.path.exists(SQLITE_DB_PATH):
                        size = os.path.getsize(SQLITE_DB_PATH)
                        lines.append(f"  DB size      : {size:,} bytes ({size/1024:.0f} KB)")
                except Exception:
                    pass

                # Tool count
                tool_count = len([m for m in dir(self) if m.startswith("_execute")]) + 16
                lines.append(f"  Tools        : {tool_count} available")

                # Git HEAD
                try:
                    r2 = subprocess.run(["git", "log", "-1", "--oneline"],
                                        cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
                    lines.append(f"  Git HEAD     : {r2.stdout.strip()}")
                except Exception:
                    pass

                lines.append("\n" + "─" * 52)
                return "\n".join(lines)

            # ── Unknown tool fallback ────────────────────────────────────
            else:
                return f"Error: Unknown tool '{name}'"

        except subprocess.TimeoutExpired:
            return f"Error: Tool '{name}' timed out"
        except Exception as e:
            return f"Error executing '{name}': {e}"

    # ── Full Autonomous Chat Processing ──────────────────────────────────

    async def process_message(self, user_text: str) -> dict:
        """Process a user message through the full autonomous tool loop.

        Returns:
            {
                "response": str,         — The final AI response text
                "message_id": int,       — DB id of the assistant message
                "tool_iterations": int,   — Number of tool iterations used
                "type": "final" | "partial"
            }
        """
        async with self._lock:
            self.memory.set_status("thinking")
            self.memory.add_message("user", user_text)
            self._conversation.append({"role": "user", "content": user_text})

            iteration = 0
            last_response = ""

            try:
                while iteration < MAX_TOOL_ITERATIONS:
                    iteration += 1

                    if iteration > 1:
                        self.memory.set_status(
                            f"processing tool result (iteration {iteration})..."
                        )

                    # Call the LLM
                    response = self._call_llm(self._conversation)

                    if not response:
                        self.memory.set_status("idle")
                        return {
                            "response": "Error: Empty response from LLM.",
                            "message_id": 0,
                            "tool_iterations": iteration,
                            "type": "final",
                        }

                    # Check for tool calls
                    tool_calls = self._parse_tool_calls(response)

                    if not tool_calls:
                        # No more tool calls — this is the final response
                        self._conversation.append(
                            {"role": "assistant", "content": response}
                        )
                        msg_id = self.memory.add_message("assistant", response)
                        self.memory.set_status("idle")
                        return {
                            "response": response,
                            "message_id": msg_id,
                            "tool_iterations": iteration,
                            "type": "final",
                        }

                    # Execute tool calls
                    for tc in tool_calls:
                        name = tc["name"]
                        args = tc["arguments"]
                        self.memory.set_status(f"running tool: {name}")

                        # Execute
                        result = self._execute_tool(name, args)

                        # Append assistant's tool call request
                        self._conversation.append({
                            "role": "assistant",
                            "content": response,
                        })

                        # Append tool result
                        self._conversation.append({
                            "role": "user",
                            "content": (
                                f"<tool_result>\n"
                                f"Tool: {name}\n"
                                f"Arguments: {json.dumps(args)}\n"
                                f"Result:\n{result}\n"
                                f"</tool_result>"
                            ),
                        })

                    last_response = response

                # Exhausted iterations
                fallback = (
                    f"I reached the maximum number of tool iterations "
                    f"({MAX_TOOL_ITERATIONS}). Here's what I have so far:\n\n"
                    f"{last_response}"
                )
                self._conversation.append({"role": "assistant", "content": fallback})
                msg_id = self.memory.add_message("assistant", fallback)
                self.memory.set_status("idle")
                return {
                    "response": fallback,
                    "message_id": msg_id,
                    "tool_iterations": iteration,
                    "type": "partial",
                }

            except Exception as e:
                error_msg = f"Error processing message: {e}"
                self.memory.set_status("idle")
                return {
                    "response": error_msg,
                    "message_id": 0,
                    "tool_iterations": iteration,
                    "type": "error",
                }


# ═══════════════════════════════════════════════════════════════════════════════
#  Global singletons
# ═══════════════════════════════════════════════════════════════════════════════

_memory: Optional[MemoryStore] = None
_brain: Optional[QorTrollerBrain] = None


def _get_brain() -> QorTrollerBrain:
    """Lazy-init the global brain singleton."""
    global _memory, _brain
    if _brain is None:
        _memory = MemoryStore()
        _brain = QorTrollerBrain(_memory)
    return _brain


# ═══════════════════════════════════════════════════════════════════════════════
#  ASGI HTTP Handlers
# ═══════════════════════════════════════════════════════════════════════════════

async def _read_body(receive) -> bytes:
    """Read full request body."""
    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body", False):
            break
    return body


async def _send_json(send, data: dict, status: int = 200):
    """Send a JSON response."""
    body = json.dumps(data).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
            [b"access-control-allow-origin", b"*"],
            [b"access-control-allow-headers", b"content-type, x-api-key"],
            [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
        ],
    })
    await send({"type": "http.response.body", "body": body})


def _check_auth(headers: dict) -> Optional[str]:
    """Return error message if auth fails, None if OK."""
    if not OPERATOR_API_KEY:
        return None
    key = headers.get("x-api-key", "")
    if key and hmac.compare_digest(key, OPERATOR_API_KEY):
        return None
    return "Invalid API key"


async def app(scope, receive, send):
    """Pure ASGI application for the Hive Mind Daemon."""
    if scope["type"] == "lifespan":
        msg = await receive()
        if msg["type"] == "lifespan.startup":
            # Initialize brain on startup
            _get_brain()
            await send({"type": "lifespan.startup.complete"})
            msg = await receive()
        if msg["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
        return

    if scope["type"] != "http":
        return

    path = scope.get("path", "")
    method = scope.get("method", "GET")
    headers = dict(scope.get("headers", []))

    # Decode header keys/values
    decoded_headers = {}
    for k, v in headers.items():
        dk = k.decode("utf-8", errors="ignore") if isinstance(k, bytes) else k
        dv = v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else v
        decoded_headers[dk.lower()] = dv

    # ── CORS preflight ────────────────────────────────────────────────────
    if method == "OPTIONS":
        await _send_json(send, {"ok": True})
        return

    # ── GET /health ───────────────────────────────────────────────────────
    if path == "/health" and method == "GET":
        brain = _get_brain()
        status_data = brain.memory.get_status()
        await _send_json(send, {
            "status": "ok",
            "mode": "qortroller-daemon-hive-mind",
            "version": DAEMON_VERSION,
            "brain": status_data.get("brain_status", "idle"),
            "message_count": status_data.get("message_count", 0),
            "llm_configured": bool(QUICKSILVER_API_KEY),
            "llm_model": QUICKSILVER_MODEL,
        })
        return

    # ── GET /status ───────────────────────────────────────────────────────
    if path == "/status" and method == "GET":
        brain = _get_brain()
        status_data = brain.memory.get_status()
        await _send_json(send, {
            "daemon_version": DAEMON_VERSION,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "brain_status": status_data.get("brain_status", "idle"),
            "brain_status_updated_at": status_data.get("brain_status_updated_at", ""),
            "message_count": status_data.get("message_count", 0),
            "last_message_id": status_data.get("last_message_id", 0),
            "llm_configured": bool(QUICKSILVER_API_KEY),
            "llm_model": QUICKSILVER_MODEL,
            "uptime": datetime.datetime.utcnow().isoformat() + "Z",
        })
        return

    # ── GET /history ──────────────────────────────────────────────────────
    if path == "/history" and method == "GET":
        # Parse query params
        qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")
        since_id = 0
        limit = 200
        if qs:
            for part in qs.split("&"):
                if "=" in part:
                    k, _, v = part.partition("=")
                    if k == "since_id":
                        try:
                            since_id = int(v)
                        except ValueError:
                            pass
                    elif k == "limit":
                        try:
                            limit = min(int(v), 500)
                        except ValueError:
                            pass

        brain = _get_brain()
        if since_id > 0:
            messages = brain.memory.get_messages(since_id=since_id, limit=limit)
        else:
            messages = brain.memory.get_all_messages(limit=limit)

        await _send_json(send, {
            "messages": messages,
            "count": len(messages),
            "since_id": since_id,
        })
        return

    # ── POST /chat ────────────────────────────────────────────────────────
    if path == "/chat" and method == "POST":
        # Chat is intentionally open — frontends need to reach the brain
        # without managing API keys. Auth is for operator/admin endpoints.
        body = await _read_body(receive)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            await _send_json(send, {"detail": "Invalid JSON"}, status=400)
            return

        user_text = req.get("message", "").strip()
        if not user_text:
            await _send_json(send, {"detail": "'message' field is required"}, status=400)
            return

        # Process through the brain
        brain = _get_brain()
        result = await brain.process_message(user_text)

        await _send_json(send, result)
        return

    # ── POST /chat/ping ───────────────────────────────────────────────────
    # Lightweight version that just stores but doesn't process AI
    if path == "/chat/ping" and method == "POST":
        body = await _read_body(receive)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            await _send_json(send, {"detail": "Invalid JSON"}, status=400)
            return

        user_text = req.get("message", "").strip()
        brain = _get_brain()
        msg_id = brain.memory.add_message("user", user_text)
        await _send_json(send, {
            "response": f"Message received (id={msg_id}). Start the daemon for AI processing.",
            "message_id": msg_id,
            "type": "stored",
        })
        return

    # ── POST /agent/local-host/execute (legacy) ──────────────────────────
    if path == "/agent/local-host/execute" and method == "POST":
        auth_err = _check_auth(decoded_headers)
        if auth_err:
            # Also check api_key query param
            qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")
            qp = {}
            for part in qs.split("&"):
                if "=" in part:
                    k, _, v = part.partition("=")
                    qp[k] = v
            api_key = decoded_headers.get("x-api-key", "") or qp.get("api_key", "")
            if OPERATOR_API_KEY and (not api_key or not hmac.compare_digest(api_key, OPERATOR_API_KEY)):
                await _send_json(send, {"detail": "Invalid API key"}, status=403)
                return

        body = await _read_body(receive)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            await _send_json(send, {"detail": "Invalid JSON"}, status=400)
            return

        tool_name = req.get("tool", "")
        tool_args = req.get("arguments", {})
        brain = _get_brain()
        result = brain._execute_tool(tool_name, tool_args)
        await _send_json(send, {"result": result})
        return

    # ── GET /tools (info about available tools) ──────────────────────────
    if path == "/tools" and method == "GET":
        await _send_json(send, {
            "available_tools": [
                {
                    "name": "read_file",
                    "description": "Read a file from the codebase (max 12KB)",
                    "arguments": {"path": "str (required)"},
                },
                {
                    "name": "write_file",
                    "description": "Write/create a file in the repo (blocked for protocol invariant files)",
                    "arguments": {"path": "str (required)", "content": "str (required)"},
                },
                {
                    "name": "list_files",
                    "description": "List all project files (max 300)",
                    "arguments": {},
                },
                {
                    "name": "search_code",
                    "description": "Search codebase with ripgrep/git grep — find symbols, patterns, strings",
                    "arguments": {"pattern": "str (required)", "glob": "str (optional, e.g. '*.py')"},
                },
                {
                    "name": "git_history",
                    "description": "Show recent git log (10 commits, oneline)",
                    "arguments": {},
                },
                {
                    "name": "git_log_full",
                    "description": "Full git log with stats for a ref or commit hash",
                    "arguments": {"ref": "str (optional, default HEAD)", "n": "int (optional, max 20)"},
                },
                {
                    "name": "bridge_get",
                    "description": "GET a bridge API endpoint (bridge must be running on localhost:8000)",
                    "arguments": {"path": "str (required)"},
                },
                {
                    "name": "bridge_post",
                    "description": "POST to a bridge API endpoint with optional JSON payload",
                    "arguments": {"path": "str (required)", "payload": "dict (optional)", "api_key": "str (optional)"},
                },
                {
                    "name": "run_invariant_gate",
                    "description": "Run the PV-CI invariant gate (scripts/vapi_invariant_gate.py) and return pass/fail",
                    "arguments": {},
                },
                {
                    "name": "poac_status",
                    "description": "Single-call QorTroller protocol status: GIC chain, PCC capture health, separation ratio, contract count, git HEAD",
                    "arguments": {},
                },
                {
                    "name": "list_contracts",
                    "description": "List all deployed contracts from contracts/deployed-addresses.json",
                    "arguments": {},
                },
                {
                    "name": "gic_chain_status",
                    "description": "GIC chain visualizer: colored link progress bar, chain length, head hash, consecutive_clean toward GIC_100. Reads from live bridge or local DB.",
                    "arguments": {"n": "int (optional, default 20 — number of links to render in bar)"},
                },
                {
                    "name": "query_chain",
                    "description": "Query IoTeX testnet directly (no bridge needed): wallet_balance, is_fully_eligible, get_device_tier, beacon_registry, block_number, or 'all'",
                    "arguments": {
                        "query": "str (required): wallet_balance | is_fully_eligible | get_device_tier | beacon_registry | block_number | all",
                        "device_id": "str (optional): 32-byte hex device identity for is_fully_eligible / get_device_tier queries",
                    },
                },
                {
                    "name": "calibration_status",
                    "description": "Full enrollment and calibration status: L4 thresholds, AIT separation ratio, GIC progress, tournament preflight gate",
                    "arguments": {},
                },
                {
                    "name": "run_mythos",
                    "description": "Run a specific Mythos audit variant (1-17) and return findings sorted by severity. Fast variants: 16=path_a_spec_impl_parity, 14=doc_number_consistency, 5=crypto_drift, 1=frozen_drift. DB-bound variants need bridge running.",
                    "arguments": {"variant": "int (required, 1-17)"},
                },
                {
                    "name": "gic_replay",
                    "description": "Replay last N GIC chain links from local DB (~/.vapi/bridge.db) and cryptographically verify each SHA-256 link hash. Detects tamper or DB corruption without the bridge running.",
                    "arguments": {
                        "n": "int (optional, default 20, max 200)",
                        "session_id": "str (optional — defaults to most recent session in DB)",
                    },
                },
                # --- Protocol Domain Tools ---
                {
                    "name": "protocol_phase",
                    "description": "Live protocol phase context: phase number, bridge health, agent count, contract count, git HEAD",
                    "arguments": {},
                },
                {
                    "name": "tournament_readiness",
                    "description": "Full tournament eligibility gate: preflight pass/fail, all P0 conditions, separation defensibility, per-pair gaps, blocker summary, readiness score",
                    "arguments": {},
                },
                {
                    "name": "separation_deep_dive",
                    "description": "Deep inter-player separation analysis: ratio, per-pair gaps, LOO accuracy, trends, projections, AIT status",
                    "arguments": {"session_type": "str (optional)"},
                },
                {
                    "name": "biometric_vault",
                    "description": "Full biometric credential lifecycle: credential age/TTL, TTL decay scaling, renewal chain, dual primitive gate, confidence multiplier",
                    "arguments": {},
                },
                {
                    "name": "governance_audit",
                    "description": "Governance and invariants: PV-CI invariant gate, allowlist governance history, BBG status, protocol metabolism index",
                    "arguments": {"run_invariant": "bool (optional)"},
                },
                {
                    "name": "fleet_coherence",
                    "description": "Fleet signal coherence: coherence fingerprint registry, agent context integrity, fleet coherence summary and recent entries",
                    "arguments": {},
                },
                {
                    "name": "corpus_health",
                    "description": "Calibration corpus data health: capture velocity oracle, tremor convergence, probe status, regression guard, data readiness, L4 dim sync",
                    "arguments": {},
                },
                {
                    "name": "l4_calibration",
                    "description": "L4 threshold calibration system: live calibration profile, staleness, per-battery tracks, router, dim sync, accel FFT config",
                    "arguments": {},
                },
                {
                    "name": "epoch_windows",
                    "description": "Epoch window system: analytics p50/p95, auto-tune recommendation, device heatmap, override lifecycle status",
                    "arguments": {},
                },
                {
                    "name": "protocol_maturity",
                    "description": "Protocol maturity score with all 9 components: separation, freshness, calibration, PITL, ioSwarm, dry-run, threat forecast, biometric stationarity, PMI",
                    "arguments": {},
                },
                {
                    "name": "chain_overview",
                    "description": "Live on-chain overview: wallet balance, block number, all deployed contracts grouped by role",
                    "arguments": {},
                },
                {
                    "name": "daemon_diagnose",
                    "description": "Daemon self-diagnostic: bridge connectivity, LLM status, DB size, tool count, memory store, git HEAD",
                    "arguments": {},
                },
                {
                    "name": "execute_shell",
                    "description": "Run a shell command in the repo root (15s timeout)",
                    "arguments": {"command": "str (required)"},
                },
                {
                    "name": "current_time",
                    "description": "Get current date and time",
                    "arguments": {},
                },
            ],
            "daemon_endpoints": {
                "POST /chat": "Send a message to the AI brain",
                "GET /history": "Fetch unified chat history",
                "GET /status": "View brain status",
                "GET /health": "Daemon health check",
                "GET /tools": "List all available tools",
                "POST /agent/local-host/execute": "Direct tool execution (legacy)",
            },
        })
        return

    # ── 404 ───────────────────────────────────────────────────────────────
    await _send_json(send, {"detail": f"Not found: {method} {path}"}, status=404)


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Launch the QorTroller Daemon."""
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    if not QUICKSILVER_API_KEY:
        print("WARNING: QUICKSILVER_API_KEY not set. Chat will be stored but not processed.")
        print("         Set it in bridge/.env as: QUICKSILVER_API_KEY=sk-...")
        print()

    print("=" * 60)
    print(f"  {APP_NAME} v{APP_VERSION} — Hive Mind Central Brain")
    print(f"  DAEMON:  {DAEMON_VERSION}")
    print("=" * 60)
    print(f"  Port        : {PORT}")
    print(f"  LLM Model   : {QUICKSILVER_MODEL}")
    print(f"  LLM Key     : {'OK (configured)' if QUICKSILVER_API_KEY else 'MISSING (NOT SET)'}")
    print(f"  Memory DB   : {SQLITE_DB_PATH}")
    print(f"  Bridge URL  : {BRIDGE_BASE_URL}")
    print(f"  Auth        : {'ENABLED' if OPERATOR_API_KEY else 'DISABLED (dev mode)'}")
    print(f"  Repo root   : {REPO_ROOT}")
    print()
    print(f"  Endpoints:")
    print(f"    POST /chat              — Send message to AI brain")
    print(f"    GET  /history           — Fetch unified chat history")
    print(f"    GET  /status            — Brain status")
    print(f"    GET  /health            — Health check")
    print(f"    GET  /tools             — Tool info")
    print(f"    POST /agent/local-host/execute — Direct tool execution")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()