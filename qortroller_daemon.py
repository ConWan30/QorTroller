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
    "  read_file(path: str)                              - Read a file from the codebase (max 12KB)\n"
    "  write_file(path: str, content: str)               - Write/create a file (blocked for protocol files)\n"
    "  list_files()                                      - List all project files (max 300)\n"
    "  search_code(pattern: str, glob?: str)             - Search codebase with ripgrep/git grep\n"
    "  git_history()                                     - Show recent git log (10 commits, oneline)\n"
    "  git_log_full(ref?: str, n?: int)                  - Full git log with stats for a ref/commit\n"
    "  bridge_get(path: str)                             - GET a bridge API endpoint\n"
    "  bridge_post(path: str, payload?: dict)            - POST to a bridge API endpoint\n"
    "  run_invariant_gate()                              - Run PV-CI invariant gate (176 invariants)\n"
    "  poac_status()                                     - Quick protocol status (GIC/PCC/contracts/HEAD)\n"
    "  list_contracts()                                  - List all 66 deployed contracts\n"
    "  gic_chain_status(n?: int)                         - GIC chain visual: links, head, progress to GIC_100\n"
    "  query_chain(query: str, device_id?: str)          - Query IoTeX testnet directly: wallet_balance,\n"
    "                                                      is_fully_eligible, get_device_tier,\n"
    "                                                      beacon_registry, block_number, all\n"
    "  calibration_status()                              - Full enrollment status: L4 thresholds, AIT\n"
    "                                                      separation ratio, GIC progress, tournament gate\n"
    "  execute_shell(command: str)                       - Run a shell command in the repo root\n"
    "  current_time()                                    - Get the current date and time\n\n"
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
        """
        calls = []
        start_tag = "<tool_call>"
        end_tag = "</tool_call>"
        pos = 0
        while True:
            start = text.find(start_tag, pos)
            if start == -1:
                break
            content_start = start + len(start_tag)
            end = text.find(end_tag, content_start)
            if end == -1:
                break
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
                # Call IoTeX testnet directly via urllib (no web3 dep in daemon).
                # Supports: wallet_balance, is_fully_eligible, get_device_tier,
                #           beacon_registry, raw_eth_call.
                import urllib.request as _ur
                import struct

                RPC = "https://babel-api.testnet.iotex.io"
                WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"

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
                    # babel-api.testnet.iotex.io requires User-Agent header
                    # (returns 403 without it — documented in F-HWFL-4-1)
                    req = _ur.Request(RPC, data=payload, headers={
                        "Content-Type": "application/json",
                        "User-Agent": "QorTroller-Daemon/2.0",
                    })
                    with _ur.urlopen(req, timeout=10) as resp:
                        return json.loads(resp.read())

                query = args.get("query", "wallet_balance").lower()
                lines = []

                if query in ("wallet_balance", "all", ""):
                    res = _rpc("eth_getBalance", [WALLET, "latest"])
                    wei = int(res["result"], 16)
                    iotx = wei / 1e18
                    lines.append(f"Wallet ({WALLET[:10]}...): {iotx:.6f} IOTX")

                if query in ("is_fully_eligible", "all"):
                    device_id = args.get("device_id", "")
                    lens_addr = addrs.get("VAPIProtocolLensV2", addrs.get("VAPIProtocolLens", ""))
                    if not lens_addr:
                        lines.append("isFullyEligible: VAPIProtocolLens address not found")
                    elif not device_id:
                        lines.append("isFullyEligible: provide device_id argument (32-byte hex)")
                    else:
                        # keccak4("isFullyEligible(bytes32)") = 0x...
                        # selector hardcoded from ABI
                        selector = "0x5f04e8a4"
                        padded = device_id.replace("0x","").zfill(64)
                        data = selector + padded
                        res = _rpc("eth_call", [{"to": lens_addr, "data": data}, "latest"])
                        result_hex = res.get("result", "0x")
                        eligible = result_hex.endswith("1")
                        lines.append(f"isFullyEligible({device_id[:10]}...): {eligible}")

                if query in ("get_device_tier", "all"):
                    device_id = args.get("device_id", "")
                    lens_addr = addrs.get("VAPIProtocolLensV2", addrs.get("VAPIProtocolLens", ""))
                    if lens_addr and device_id:
                        selector = "0x7f87d5c3"  # getDeviceTier(bytes32)
                        padded = device_id.replace("0x","").zfill(64)
                        data = selector + padded
                        res = _rpc("eth_call", [{"to": lens_addr, "data": data}, "latest"])
                        result_hex = res.get("result", "0x0")
                        tier = int(result_hex, 16) if result_hex and result_hex != "0x" else 0
                        tier_name = {1: "FULL (CFI-ZCP1)", 2: "STANDARD (CFI-ZCT1)", 3: "BASIC"}.get(tier, f"UNKNOWN ({tier})")
                        lines.append(f"getDeviceTier({device_id[:10]}...): {tier_name}")

                if query in ("beacon_registry", "all"):
                    tbr_addr = addrs.get("VAPITemporalBeaconRegistry", "")
                    if tbr_addr:
                        # latestBeacon() selector
                        selector = "0x5a2e3b93"
                        res = _rpc("eth_call", [{"to": tbr_addr, "data": selector}, "latest"])
                        raw = res.get("result", "0x")
                        if raw and raw != "0x" and len(raw) > 2:
                            block_num = int(raw[2:66], 16) if len(raw) >= 66 else 0
                            lines.append(f"TemporalBeaconRegistry: latest anchor block={block_num}")
                        else:
                            lines.append("TemporalBeaconRegistry: no beacon anchored yet")
                    else:
                        lines.append("TemporalBeaconRegistry: address not found in deployed-addresses.json")

                if query in ("block_number", "all"):
                    res = _rpc("eth_blockNumber", [])
                    block = int(res["result"], 16)
                    lines.append(f"IoTeX testnet block: {block:,}")

                if not lines:
                    lines.append(
                        f"Unknown query '{query}'. Valid: wallet_balance, is_fully_eligible, "
                        f"get_device_tier, beacon_registry, block_number, all"
                    )

                return "\n".join(lines)

            # ── #9 calibration_status ─────────────────────────────────────
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
                    "description": "Full enrollment and calibration status: L4 thresholds from calibration_profile_live.json, AIT separation ratio, GIC chain progress, tournament preflight gate conditions",
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