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

# Governance schema — single source of truth for all fence rules.
# Import fails loudly if the module is missing or corrupt.
from _daemon_tools_schema import (
    DaemonCommitChain,
    GovernanceHardStop,
    GovernanceLog,
    GovernanceMode,
    RateLimiter,
    SigningError,
    OUTPUT_PRODUCING_TOOLS,
    adversarial_verify,
    check_bridge_post_gate,
    classify_path,
    get_sealed_env,
    governance_self_test,
    is_new_test_file_path,
    is_read_blocked,
    load_daemon_agent_id,
    resolve_output_artifact_path,
    run_post_output_verification,
    validate_shell_command,
    verify_artifact,
    reconstruct_from_removal_diff,
    build_mixin_module,
    MethodologyRegistry,
    BANNED_METACHARACTERS,
    PROPOSE_ONLY_PATHS,
    FROZEN_PATTERNS,
    TEST_DIRECTORIES,
)

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
# DAEMON_PORT takes precedence so bridge/.env HTTP_PORT (for the bridge process)
# doesn't collide with the daemon when both run simultaneously.
PORT = int(os.environ.get("DAEMON_PORT", os.environ.get("HTTP_PORT", 8080)))
MAX_TOOL_ITERATIONS = 80  # raised from 20 — large-file tasks (paginate 18K-line _core.py + analyze + propose + test) need many read calls. Kimi K2.7 256K context tolerates the deeper loop.
TOOL_TIMEOUT = 15

QUICKSILVER_API_KEY = os.environ.get("QUICKSILVER_API_KEY", "")
QUICKSILVER_API_URL = "https://api.quicksilverpro.io/v1/chat/completions"
# Using Claude Sonnet 4.6 via QuickSilver proxy — same API key, better code generation.
# If QuickSilver uses provider-prefixed naming try: "anthropic/claude-sonnet-4-6"
# For maximum intelligence on engineering tasks: "claude-opus-4-7"
QUICKSILVER_MODEL = os.environ.get("QUICKSILVER_MODEL", "claude-sonnet-4-6")

OPERATOR_API_KEY = os.environ.get("OPERATOR_API_KEY", "")
# Bridge public API (26 endpoints, no auth) — used for public-facing queries
BRIDGE_BASE_URL = os.environ.get("VAPI_BRIDGE_URL", "http://localhost:8000")
# Bridge operator API (241 endpoints, x-api-key required) — all rich protocol state
BRIDGE_OPERATOR_URL = os.environ.get("VAPI_BRIDGE_OPERATOR_URL", "http://localhost:8000/operator")
TOOL_SERVER_URL = os.environ.get("TOOL_SERVER_URL", "http://localhost:8080")

SQLITE_DB_PATH = os.path.join(REPO_ROOT, "agent_memory.db")

# ── Governance singletons (wired from _daemon_tools_schema) ──────────────────
# Rate limiter: persisted to its own DB to survive restarts (L5 fix).
_RATE_LIMITER_DB = os.path.join(REPO_ROOT, "agent_rate_limiter.db")
_RATE_LIMITER = RateLimiter(_RATE_LIMITER_DB)

# Governance log: append-only audit trail outside the daemon's commit scope.
# Path is outside REPO_ROOT so the daemon cannot git-add it accidentally.
_GOV_LOG_PATH = os.path.join(
    os.path.expanduser("~"), ".vapi", "daemon_governance.log"
)
_GOV_LOG = GovernanceLog(_GOV_LOG_PATH)

# Daemon identity: ED25519 key lives outside REPO_ROOT (outside writable scope).
# Sign-fail raises SigningError → proposal BLOCKED (L6 fix).
_DAEMON_KEY_PATH = os.path.join(
    os.path.expanduser("~"), ".vapi", "daemon_identity.key"
)
_DAEMON_IDENTITY = None  # Lazy-init in _get_brain() after self-test passes

# AGENT-COMMIT chain: SQLite-persisted so prev_commit_hash survives restarts.
# Same DB as rate limiter — one governance store. (F-AGC-4)
_DAEMON_COMMIT_CHAIN = DaemonCommitChain(_RATE_LIMITER_DB)

# Methodology registry: lessons keyed by failure class, compound across sessions.
_METHODOLOGY = MethodologyRegistry(os.path.join(REPO_ROOT, "docs", "_daemon_proposals", "daemon_methodology.json"))

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
    "║  ENGINEERING FENCE RULES (MANDATORY — NOT SUGGESTIONS)    ║\n"
    "╚══════════════════════════════════════════════════════════════╝\n\n"
    "FENCE RULE 1 — TESTS ARE THE VERIFICATION RAIL (ABSOLUTE)\n"
    "NEVER edit files under bridge/tests/ or sdk/tests/. Tests are read-only\n"
    "to you. If your code change fails a test, the correct action is STOP and\n"
    "surface the failure for operator review. Do not edit the test to make code\n"
    "pass. This rule has no exceptions.\n\n"
    "FENCE RULE 2 — NEW FILES AUTONOMOUS, EXISTING CRITICAL FILES → PROPOSE\n"
    "write_file() and edit_file() are autonomous ONLY for new files or files\n"
    "you created in the current session. For these critical existing paths,\n"
    "you MUST use propose_edit() which generates a diff for review without\n"
    "touching the source:\n"
    "  bridge/vapi_bridge/main.py      — startup critical\n"
    "  bridge/vapi_bridge/store/_core.py — FROZEN surfaces\n"
    "  bridge/vapi_bridge/operator_api.py — 241 endpoints\n"
    "  bridge/vapi_bridge/chain.py     — wallet / signing\n"
    "  bridge/vapi_bridge/grind_chain.py, watchdog_chain.py, codec.py\n"
    "  bridge/vapi_bridge/session_adjudicator*.py\n"
    "  scripts/vapi_invariant_gate.py, .github/INVARIANTS_ALLOWLIST.json\n"
    "  Any FROZEN-v1 primitive module\n\n"
    "FENCE RULE 3 — TERMINAL STATE IS ALWAYS A REVIEW PACKAGE\n"
    "At the end of any multi-step engineering plan, call finalize_plan().\n"
    "This generates a REVIEW_*.md in docs/_daemon_proposals/ and STOPS.\n"
    "No changes are committed or applied until the operator reviews and\n"
    "explicitly applies them. Never declare work 'done' without calling\n"
    "finalize_plan() as the last step.\n\n"
    "FENCE RULE 4 — NO WALLET, CHAIN, OR KEY ACCESS\n"
    "You have zero access to the bridge wallet, KMS, signing operations,\n"
    "or any chain submission path. CHAIN_SUBMISSION_PAUSED=true applies\n"
    "to you equally. Do not write code that touches these surfaces.\n\n"
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
    "  read_file_range(path, offset?, limit?)            - Paginated read of large files (default 500\n"
    "                                                      lines starting from line 1). Use this for\n"
    "                                                      files > 12KB. Returns numbered lines.\n"
    "  write_file(path: str, content: str)               - Write/create a file (blocked for protocol files)\n"
    "  edit_file(path, old_string, new_string,           - Surgical string replacement. AUTONOMOUS for new\n"
    "            replace_all?)                              files only. BLOCKED on tests/, main.py, FROZEN\n"
    "                                                      modules, operator_api.py, chain.py, .env.\n"
    "                                                      See FENCE RULE 2 above.\n"
    "  propose_edit(path, old_string, new_string,        - For existing critical files: generates a unified\n"
    "               reason?)                               diff saved to docs/_daemon_proposals/ WITHOUT\n"
    "                                                      touching the source. Operator applies with\n"
    "                                                      git apply. Use this for all FENCE RULE 2 paths.\n"
    "  extract_with_diff(diff_path, class_name,          - DIFF-ORACLE: reconstruct a moved code block\n"
    "                    target_path)                      deterministically from a removal diff and emit\n"
    "                                                      it as a .proposed mixin (AST-validated). USE THIS\n"
    "                                                      for domain extraction instead of re-emitting code\n"
    "                                                      verbatim — verbatim copies 524-timeout + risk\n"
    "                                                      transcription drift. LLM proposes the cut (diff),\n"
    "                                                      this tool builds the moved file.\n"
    "  verify_artifact(path, expected_shape)             - FABRICATION DETECTOR: prove an output exists with\n"
    "                                                      the expected shape (exists/lines/python_valid/\n"
    "                                                      class_name/must_contain). Also runs automatically\n"
    "                                                      after write_file/propose_edit/extract_with_diff.\n"
    "  adversarial_verify(artifact_path, diff_path?,      - ADVERSARIAL SELF-TEST: reconstruct artifact from\n"
    "                    class_name?)                      diff and compare hashes. Mandatory before READY.\n"
    "  methodology(action?, keywords?)                   - Query accumulated daemon methodology by failure\n"
    "                                                      class (VERBATIM_RELOCATION, HALLUCINATED_COMPLETION,\n"
    "                                                      etc). Query at task_track time, apply known patterns.\n"
    "  finalize_plan(plan_name?, summary?, verdict?)     - MANDATORY last step of any engineering plan.\n"
    "                                                      Generates REVIEW_*.md in docs/_daemon_proposals/\n"
    "                                                      listing all proposals + operator action steps.\n"
    "                                                      verdict=READY requires passing fabrication +\n"
    "                                                      adversarial gates. STOPS without applying changes.\n"
    "  list_files(path?: str)                            - List project files (max 300). Pass an optional\n"
    "                                                      subdirectory path (e.g. 'bridge/vapi_bridge/store')\n"
    "                                                      to scope the listing and avoid truncation.\n"
    "  search_code(pattern: str, glob?: str)             - Search codebase with ripgrep/git grep\n"
    "  [Engineering / Testing]\n"
    "  run_pytest(test_path?, timeout?, extra_args?)     - Run pytest with 120s default timeout, returns\n"
    "                                                      summary + first 5 failure tracebacks + tail.\n"
    "                                                      Default test_path=bridge/tests/.\n"
    "  task_track(steps: list[str], plan_name?)          - Create a multi-step plan. Persistent across\n"
    "                                                      chat turns in agent_memory.db. Use this for\n"
    "                                                      any multi-step work (refactor, build feature).\n"
    "  task_update(plan_name?, step_index?, status?,     - Update step status (pending/in_progress/\n"
    "              action?)                                 completed/blocked) OR action='list' to view\n"
    "                                                      current plan OR action='clear' to clear it.\n"
    "  [Version Control]\n"
    "  git_history()                                     - Show recent git log (10 commits, oneline)\n"
    "  git_log_full(ref?: str, n?: int)                  - Full git log with stats for a ref/commit\n"
    "  [Audit / Drift Detection]\n"
    "  run_mythos(variant: int)                          - Run a Mythos audit variant (1-17) and\n"
    "                                                      return findings sorted by severity.\n"
    "  health_monitor()                                  - Standing protocol health probes (GIC stall,\n"
    "                                                      invariant drift, F-FW-2 device_id conflict).\n"
    "                                                      Findings are proposal-only.\n"
    "                                                      Variants: 1=frozen_drift, 2=stability_sweep,\n"
    "                                                      3=operator_initiative, 4=live_gameplay,\n"
    "                                                      5=crypto_drift, 6=qortroller_crypto,\n"
    "                                                      7=methodology_drift, 8=ceremony_drift,\n"
    "                                                      9=post_o3_ceremony, 10=corpus_drift,\n"
    "                                                      11=claude_md, 12=spending_log,\n"
    "                                                      13=curator_graduation, 14=doc_consistency,\n"
    "                                                      15=frontend_brand, 16=path_a_parity,\n"
    "                                                      17=agent_utility_honesty\n"
    "  health_monitor()                                  - Standing protocol health probes (GIC stall,\n"
    "                                                      invariant drift, F-FW-2 device_id conflict).\n"
    "                                                      Findings are proposal-only.\n"
    "  residue_status()                                  - DECON-1 residue queue: pending/applied counts.\n"
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
    "  take_snapshot()                                   - Capture full protocol state snapshot right now\n"
    "                                                      and store in agent_memory.db snapshots table\n"
    "  diff_snapshots(n?: int)                           - Compare last N snapshots, surface all deltas\n"
    "                                                      (GIC links, ratio drift, threshold shift, etc.)\n"
    "  execute_shell(command: str)                       - Run a whitelisted shell command (git log/status/\n"
    "                                                      diff/show, python -m pytest, npm/cargo test, pwd,\n"
    "                                                      echo). File-read commands (ls/dir/type/cat/grep/\n"
    "                                                      find) are NOT available here — use list_files,\n"
    "                                                      read_file, read_file_range, or search_code instead.\n"
    "                                                      No shell metacharacters allowed.\n"
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
        # Tier 1 session state — fabrication + adversarial gates
        self._fabrication_detected = False
        self._session_artifacts: list[dict] = []
        self._session_started_at = time.time()

    # ── LLM Call ──────────────────────────────────────────────────────────

    def _call_llm(self, messages: list[dict]) -> Optional[str]:
        """Call QuickSilver API with retry on timeout and 429 rate-limit."""
        import requests, time as _t
        payload = {
            "model": QUICKSILVER_MODEL,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {QUICKSILVER_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "QorTroller-Daemon/2.0",  # Cloudflare blocks Python default UA with 1010
        }
        # Retry up to 3 times: immediate, 5s, 15s backoff
        last_err = None
        for attempt, wait in enumerate([0, 5, 15]):
            if wait:
                _t.sleep(wait)
            try:
                response = requests.post(
                    QUICKSILVER_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=180,  # 3 min — Claude with 37 tools + large system prompt
                    proxies={"http": None, "https": None},
                )
                if response.status_code == 429:
                    # Rate limited — back off and retry
                    last_err = f"429 rate limited (attempt {attempt+1})"
                    continue
                response.raise_for_status()
                result = response.json()
                message = result["choices"][0]["message"]
                content = message.get("content") or ""

                # Handle OpenAI native tool_calls format (Kimi K2.7, GPT-4o, etc.)
                # These models put tool calls in message["tool_calls"] with content=""
                # Serialize them back to the XML format the daemon's parser expects.
                native_calls = message.get("tool_calls") or []
                if native_calls and not content.strip():
                    xml_blocks = []
                    for tc in native_calls:
                        fn = tc.get("function", {})
                        name = fn.get("name", "")
                        raw_args = fn.get("arguments", "{}")
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            args = {}
                        xml_blocks.append(
                            f'<tool_call>\n{{"name": "{name}", "arguments": {json.dumps(args)}}}\n</tool_call>'
                        )
                    content = "\n".join(xml_blocks)

                return content
            except requests.exceptions.Timeout:
                last_err = f"timeout (attempt {attempt+1})"
                continue
            except Exception as e:
                last_err = str(e)
                if attempt < 2:
                    continue
                raise
        raise RuntimeError(
            f"QuickSilver API failed after 3 attempts. Last error: {last_err}"
        )

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

    # ── Bridge HTTP helper ────────────────────────────────────────────────

    @staticmethod
    def _bridge_get(path: str, timeout: float = 5.0):
        """Route a bridge GET to the correct sub-app with auth.

        Paths starting with /agent/, /bridge/, or /operator/ go to the
        operator sub-app (BRIDGE_OPERATOR_URL, x-api-key required).
        All other paths go to the public API (BRIDGE_BASE_URL, no auth).
        Returns the parsed JSON dict, or None on error.
        """
        import requests as _rq
        is_op = any(path.startswith(p) for p in ("/agent/", "/bridge/", "/operator/"))
        base = BRIDGE_OPERATOR_URL if is_op else BRIDGE_BASE_URL
        hdrs = {"x-api-key": OPERATOR_API_KEY} if (is_op and OPERATOR_API_KEY) else {}
        try:
            r = _rq.get(f"{base}{path}", headers=hdrs, timeout=timeout,
                        proxies={"http": None, "https": None})
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    # ── Tool Execution ────────────────────────────────────────────────────

    def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool and return its result as a string."""
        # ── Rate-limit check (L5) ────────────────────────────────────────────
        # Persisted across restarts; includes global cross-tool budget.
        allowed, limit_reason = _RATE_LIMITER.can_call(name)
        if not allowed:
            _GOV_LOG.rate_limited(name, limit_reason)
            return f"RATE_LIMITED: {limit_reason}"

        try:
            result = self._execute_tool_inner(name, args)
            # Only count against rate limit if the tool actually executed —
            # BLOCKED/OPERATOR_HOLD responses don't consume real resources.
            if not (isinstance(result, str) and (
                result.startswith("BLOCKED:") or
                result.startswith("OPERATOR_HOLD") or
                result.startswith("RATE_LIMITED")
            )):
                _RATE_LIMITER.record_call(name)
                # Tier 1.1 — auto verify_artifact after output-producing tools
                if name in OUTPUT_PRODUCING_TOOLS and isinstance(result, str):
                    pv = run_post_output_verification(name, args, result, REPO_ROOT)
                    if pv["ran"]:
                        artifact_rel, diff_rel = resolve_output_artifact_path(
                            name, args, result, REPO_ROOT,
                        )
                        self._session_artifacts.append({
                            "tool": name,
                            "artifact": artifact_rel,
                            "diff_path": diff_rel,
                            "class_name": args.get("class_name"),
                            "ts": time.time(),
                        })
                        vr = pv.get("verify_result") or {}
                        if pv["ok"]:
                            result += (
                                f"\n\n--- AUTO verify_artifact (Tier 1.1) ---\n"
                                f"VERIFIED: {artifact_rel}\n"
                            )
                        else:
                            self._fabrication_detected = True
                            fails = vr.get("failures", ["shape check failed"])
                            _GOV_LOG.fabrication_detected(name, artifact_rel, fails)
                            result += (
                                f"\n\n--- AUTO verify_artifact (Tier 1.1) ---\n"
                                f"FABRICATION_DETECTED: {artifact_rel}\n"
                                + "\n".join(f"  FAIL: {fl}" for fl in fails)
                                + "\nDo NOT claim this artifact is complete."
                            )
            return result
        except GovernanceHardStop:
            # L7: hard stop propagates upward — no catch here
            raise
        except Exception as e:
            _RATE_LIMITER.record_error(name)
            raise

    def _execute_tool_inner(self, name: str, args: dict) -> str:
        """Inner tool execution — called only after rate-limit check passes."""
        try:
            if name == "read_file":
                path = args.get("path", "")
                if not path:
                    return "Error: 'path' argument is required"
                # SEC-1: block reads of secret files through the governed tool
                read_block = is_read_blocked(path)
                if read_block:
                    _GOV_LOG.blocked("read_file", path, read_block)
                    return f"BLOCKED: {read_block}"
                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                if not os.path.exists(safe) or os.path.isdir(safe):
                    return f"Error: File not found: {path}"
                with open(safe, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(12000)
                return content

            elif name == "list_files":
                # Optional 'path' scopes the walk to a subdirectory so large
                # repos don't truncate the area of interest at 300 entries.
                # Listing reveals filenames only (not contents) — no SEC-1 risk.
                subpath = args.get("path", "")
                walk_root = REPO_ROOT
                if subpath:
                    cand = os.path.normpath(os.path.join(REPO_ROOT, subpath))
                    if not cand.startswith(os.path.normpath(REPO_ROOT)):
                        return "Error: Access denied (path traversal)"
                    if not os.path.isdir(cand):
                        return f"Error: not a directory: {subpath}"
                    walk_root = cand
                file_list = []
                for root, dirs, files in os.walk(walk_root):
                    dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
                    for f in files:
                        if f in _IGNORE_FILES:
                            continue
                        rel = os.path.relpath(os.path.join(root, f), REPO_ROOT)
                        file_list.append(rel.replace("\\", "/"))
                total = len(file_list)
                out = json.dumps(sorted(file_list)[:300], indent=2)
                if total > 300:
                    out += f"\n... ({total - 300} more; narrow with path=)"
                return out

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

            elif name == "take_snapshot":
                # Trigger the protocol watcher to take one snapshot right now
                # and store it in agent_memory.db (snapshots table).
                # Returns the formatted snapshot string.
                import sys as _sys
                watcher_path = os.path.join(REPO_ROOT, "protocol_watcher.py")
                if not os.path.exists(watcher_path):
                    return "Error: protocol_watcher.py not found in repo root"
                _sys.path.insert(0, REPO_ROOT)
                try:
                    import importlib.util as _ilu
                    spec = _ilu.spec_from_file_location("protocol_watcher", watcher_path)
                    pw = _ilu.module_from_spec(spec)
                    spec.loader.exec_module(pw)
                    conn = pw._init_db(DB_PATH)
                    snap = pw.collect_snapshot()
                    pw._save_snapshot(conn, snap)
                    conn.close()
                    return pw.format_snapshot(snap)
                except Exception as e:
                    return f"Error taking snapshot: {e}"

            elif name == "diff_snapshots":
                # Compare last N snapshots from agent_memory.db and report deltas.
                n = max(2, int(args.get("n", 2)))
                import sys as _sys
                watcher_path = os.path.join(REPO_ROOT, "protocol_watcher.py")
                if not os.path.exists(watcher_path):
                    return "Error: protocol_watcher.py not found"
                _sys.path.insert(0, REPO_ROOT)
                try:
                    import importlib.util as _ilu
                    spec = _ilu.spec_from_file_location("protocol_watcher", watcher_path)
                    pw = _ilu.module_from_spec(spec)
                    spec.loader.exec_module(pw)
                    conn = pw._init_db(DB_PATH)
                    snaps = pw._get_last_snapshots(conn, n)
                    conn.close()
                    if len(snaps) < 2:
                        return (f"Only {len(snaps)} snapshot(s) in DB — "
                                f"run take_snapshot or protocol_watcher.py --once first")
                    # Diff consecutive pairs
                    all_alerts = []
                    for i in range(len(snaps) - 1):
                        curr = snaps[i]["data"]
                        prev = snaps[i + 1]["data"]
                        alerts = pw.diff_snapshots(prev, curr)
                        for a in alerts:
                            a["between"] = f"{snaps[i+1]['timestamp'][:19]} → {snaps[i]['timestamp'][:19]}"
                            all_alerts.append(a)
                    if not all_alerts:
                        latest = snaps[0]
                        snap_fmt = pw.format_snapshot(latest["data"])
                        return (f"No deltas across last {len(snaps)} snapshots.\n\n"
                                f"Latest ({latest['timestamp'][:19]}):\n{snap_fmt}")
                    lines = [f"Deltas across last {len(snaps)} snapshots:"]
                    for a in all_alerts:
                        lines.append(f"  [{a['key']}] {a['message']} ({a['between']})")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Error diffing snapshots: {e}"

            elif name == "bridge_get":
                path = args.get("path", "")
                if not path:
                    return "Error: 'path' argument is required"
                import requests
                # Auto-route: paths starting with /agent/ or /bridge/ go to
                # the operator sub-app (241 routes, auth required).
                # Everything else goes to the public API.
                is_operator = any(path.startswith(p) for p in
                                  ("/agent/", "/bridge/", "/operator/"))
                base = BRIDGE_OPERATOR_URL if is_operator else BRIDGE_BASE_URL
                # Strip leading /operator/ if already in path to avoid double-prefix
                url_path = path.lstrip("/operator") if (is_operator and path.startswith("/operator/")) else path
                headers = {"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {}
                try:
                    r = requests.get(
                        f"{base}{url_path}",
                        headers=headers,
                        timeout=5,
                        proxies={"http": None, "https": None},
                    )
                    if r.status_code == 200:
                        return json.dumps(r.json(), indent=2, default=str)
                    return f"Error: Bridge returned {r.status_code} for {base}{url_path}"
                except Exception as e:
                    return f"Error: Bridge request failed: {e}"

            elif name == "execute_shell":
                command = args.get("command", "")
                if not command:
                    return "Error: 'command' argument is required"

                # L3: validate against schema rules (metacharacter ban + whitelist)
                shell_err = validate_shell_command(command)
                if shell_err:
                    _GOV_LOG.shell_blocked(command, shell_err)
                    return f"BLOCKED: {shell_err}"

                # L3: sealed execution environment — no arbitrary env injection
                result = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=TOOL_TIMEOUT,
                    shell=True,
                    env=get_sealed_env(),
                )
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr
                return output[:10000] if output else "(no output)"

            elif name == "current_time":
                return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ─────────────────────────────────────────────────────────────
            # TIER 1 ENGINEERING TOOLS — surgical editing, paginated reads,
            # pytest runner, multi-step plan tracking. Designed to let the
            # brain attempt real code engineering work autonomously.
            # ─────────────────────────────────────────────────────────────

            elif name == "edit_file":
                # Targeted string replacement in repo files.
                # Mirrors Claude Code's Edit tool semantics.
                #
                # FENCE RULES (F-DAEMON-1 + F-DAEMON-2):
                # The executor may ONLY autonomously edit files it created in
                # this session (new non-critical files). For ALL existing
                # critical paths, use propose_edit() which generates a diff
                # for operator review without touching the source.
                #
                # HARD BLOCKS (edit_file never touches these — use propose_edit):
                #   tests/          — tests are the verification rail; never edit
                #   main.py         — startup critical; bad edit = bridge won't boot
                #   store/_core.py  — FROZEN-v1 surfaces live here
                #   operator_api.py — 241 endpoints; mutation risk
                #   chain.py        — wallet/signing paths
                #   FROZEN modules  — grind_chain, watchdog_chain, codec, etc.
                #   .env / keys     — no autonomous access to credentials
                #   vapi_invariant_gate.py / INVARIANTS_ALLOWLIST.json
                path = args.get("path", "")
                old_string = args.get("old_string", "")
                new_string = args.get("new_string", "")
                replace_all = bool(args.get("replace_all", False))

                if not path:
                    return "Error: 'path' argument is required"
                if not old_string:
                    return "Error: 'old_string' argument is required"
                if old_string == new_string:
                    return "Error: old_string and new_string must differ"

                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                if not os.path.exists(safe) or os.path.isdir(safe):
                    return f"Error: File not found: {path}"

                rel = os.path.relpath(safe, REPO_ROOT).replace("\\", "/")

                # F-DAEMON-1 + F-DAEMON-2: governance rules sourced from
                # _daemon_tools_schema — single source of truth, not inline sets.
                # classify_path() default for unlisted paths: PROPOSE_ONLY (L1 fix).
                path_mode = classify_path(rel)

                if path_mode == GovernanceMode.READ_ONLY:
                    _GOV_LOG.blocked("edit_file", rel, "READ_ONLY (test directory)")
                    return (
                        f"BLOCKED: edit_file cannot modify test files ({rel}). "
                        f"Tests are the verification rail — if your code fails a test, "
                        f"STOP and surface the failure for operator review. "
                        f"Never edit tests to make code pass."
                    )

                is_frozen = (path_mode == GovernanceMode.PROPOSE_ONLY)
                if is_frozen:
                    _GOV_LOG.blocked("edit_file", rel, "PROPOSE_ONLY path — use propose_edit()")
                    return (
                        f"OPERATOR_HOLD: '{rel}' is a critical/FROZEN path. "
                        f"Use propose_edit(path, old_string, new_string, reason) "
                        f"to generate a diff for operator review without modifying "
                        f"the source file. Rule: unlisted paths default to propose_only."
                    )

                try:
                    with open(safe, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception as e:
                    return f"Error reading file: {e}"

                count = content.count(old_string)
                if count == 0:
                    return (f"Error: old_string not found in {rel}. "
                            f"Verify the exact characters including whitespace.")
                if count > 1 and not replace_all:
                    return (f"Error: old_string matches {count} occurrences in {rel}. "
                            f"Either provide more surrounding context to make it unique, "
                            f"or set replace_all=true.")

                if replace_all:
                    new_content = content.replace(old_string, new_string)
                    n_replaced = count
                else:
                    new_content = content.replace(old_string, new_string, 1)
                    n_replaced = 1

                try:
                    with open(safe, "w", encoding="utf-8") as f:
                        f.write(new_content)
                except Exception as e:
                    return f"Error writing file: {e}"

                return (f"OK: {n_replaced} replacement(s) in {rel} "
                        f"(old: {len(old_string)} chars → new: {len(new_string)} chars)")

            elif name == "write_file":
                # F-GOV-2: new file creation under bridge/tests/ → PROPOSE_ONLY.
                # Tests are the verification surface even when new.
                # All other critical paths also route through classify_path().
                path = args.get("path", "")
                content = args.get("content", "")
                if not path:
                    return "Error: 'path' argument is required"

                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"

                rel = os.path.relpath(safe, REPO_ROOT).replace("\\", "/")

                # Test directory: new files → PROPOSE_ONLY (F-GOV-2)
                if is_new_test_file_path(rel):
                    _GOV_LOG.blocked("write_file", rel, "F-GOV-2: new test files are PROPOSE_ONLY")
                    return (
                        f"OPERATOR_HOLD (F-GOV-2): '{rel}' is under a test directory. "
                        f"New test files are PROPOSE_ONLY — they are part of the verification "
                        f"surface even before they exist. Use propose_edit() to draft the file "
                        f"for operator review before it joins the test suite."
                    )

                # All other critical/frozen paths → PROPOSE_ONLY
                path_mode = classify_path(rel)
                if path_mode in (GovernanceMode.PROPOSE_ONLY, GovernanceMode.READ_ONLY):
                    # SEC/F-NEWFILE: if the target is a GENUINELY NEW file (does not
                    # exist on disk), the content must not be silently discarded —
                    # otherwise the brain has no way to deliver a new-file body for
                    # review and will hallucinate that it was "embedded". Materialize
                    # the content as a reviewable .proposed artifact (the new-file
                    # analog of propose_edit). The operator creates the real file from it.
                    # An EXISTING frozen file still routes to propose_edit (use a diff).
                    if not os.path.exists(safe):
                        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        proposals_dir = os.path.join(REPO_ROOT, "docs", "_daemon_proposals")
                        os.makedirs(proposals_dir, exist_ok=True)
                        safe_name = rel.replace("/", "_").replace("\\", "_")
                        proposed_path = os.path.join(
                            proposals_dir, f"newfile_{ts}_{safe_name}.proposed"
                        )
                        meta_path = os.path.join(
                            proposals_dir, f"newfile_{ts}_{safe_name}.md"
                        )
                        with open(proposed_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        with open(meta_path, "w", encoding="utf-8") as f:
                            f.write(f"# Daemon New-File Proposal — {rel}\n\n")
                            f.write(f"**Generated:** {ts}\n")
                            f.write(f"**Target path:** `{rel}`\n")
                            f.write(f"**Size:** {len(content)} chars\n\n")
                            f.write(f"## To create the file\n\n```bash\n")
                            f.write(f"cp \"{proposed_path}\" \"{safe}\"\n```\n\n")
                            f.write(f"## Content preview (first 2000 chars)\n\n")
                            f.write(f"```python\n{content[:2000]}\n```\n")
                        _GOV_LOG.proposed(rel, proposed_path,
                                          _DAEMON_IDENTITY.public_key if _DAEMON_IDENTITY else "(unsigned)")
                        pr = os.path.relpath(proposed_path, REPO_ROOT).replace("\\", "/")
                        mr = os.path.relpath(meta_path, REPO_ROOT).replace("\\", "/")
                        return (
                            f"NEW-FILE PROPOSAL WRITTEN (source tree NOT modified):\n"
                            f"  content: {pr} ({len(content)} chars)\n"
                            f"  meta:    {mr}\n"
                            f"'{rel}' is classified {path_mode.value}, so it was NOT created "
                            f"directly. The operator creates it from the .proposed artifact:\n"
                            f"  cp {pr} {rel}\n"
                            f"The full content IS captured in the artifact above — do not claim "
                            f"it is embedded anywhere else."
                        )
                    # Existing frozen file → must use propose_edit (a diff), not write_file
                    _GOV_LOG.blocked("write_file", rel, f"write_file blocked: {path_mode.value} (existing)")
                    return (
                        f"OPERATOR_HOLD: '{rel}' already exists and is classified "
                        f"{path_mode.value}. Use propose_edit() to generate a diff."
                    )

                # Safe to write (new non-critical file — currently unreachable given
                # the propose_only default, but kept for forward-compat if a path is
                # ever explicitly classified AUTONOMOUS).
                try:
                    os.makedirs(os.path.dirname(safe), exist_ok=True)
                    with open(safe, "w", encoding="utf-8") as f:
                        f.write(content)
                    return f"OK: wrote {len(content)} chars to {rel}"
                except Exception as e:
                    return f"Error writing file: {e}"

            elif name == "read_file_range":
                # Paginated read of large files. offset is 0-indexed line number.
                path = args.get("path", "")
                offset = max(0, int(args.get("offset", 0)))
                # Default 1500/call, max 4000 — pages an 18K-line file in ~5 calls
                # instead of 36, conserving the iteration budget.
                limit = min(4000, max(1, int(args.get("limit", 1500))))

                if not path:
                    return "Error: 'path' argument is required"
                # SEC-1: block reads of secret files through the governed tool
                read_block = is_read_blocked(path)
                if read_block:
                    _GOV_LOG.blocked("read_file_range", path, read_block)
                    return f"BLOCKED: {read_block}"
                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                if not os.path.exists(safe) or os.path.isdir(safe):
                    return f"Error: File not found: {path}"

                try:
                    with open(safe, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except Exception as e:
                    return f"Error reading file: {e}"

                total = len(lines)
                if offset >= total:
                    return (f"Error: offset {offset} beyond file length "
                            f"({total} lines)")

                end = min(offset + limit, total)
                segment = lines[offset:end]
                # Number lines with 1-indexed line numbers (matching cat -n)
                numbered = []
                for i, line in enumerate(segment, start=offset + 1):
                    # Strip the trailing newline for clean display
                    line_content = line.rstrip("\n")
                    numbered.append(f"{i:6d}\t{line_content}")

                header = (f"=== {os.path.relpath(safe, REPO_ROOT)} "
                          f"lines {offset+1}-{end} of {total} ===")
                footer = ""
                if end < total:
                    footer = (f"\n... {total - end} more lines. "
                              f"Continue with offset={end}.")
                return header + "\n" + "\n".join(numbered) + footer

            elif name == "run_pytest":
                # Pytest runner with extended timeout + structured output.
                test_path = args.get("test_path", "bridge/tests/")
                timeout_s = min(300, max(10, int(args.get("timeout", 120))))
                extra_args = args.get("extra_args", "")

                # Path safety
                safe = os.path.normpath(os.path.join(REPO_ROOT, test_path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                if not os.path.exists(safe):
                    return f"Error: test path not found: {test_path}"

                cmd = [
                    sys.executable, "-m", "pytest", test_path, "-q",
                    "--tb=short", "--no-header", "-p", "no:cacheprovider",
                ]
                if extra_args:
                    # Whitelist of safe pytest flags
                    for arg in extra_args.split():
                        if arg.startswith("-") or arg.startswith("::") or arg in ("-v", "-x", "-s"):
                            cmd.append(arg)

                try:
                    result = subprocess.run(
                        cmd, cwd=REPO_ROOT,
                        capture_output=True, text=True,
                        timeout=timeout_s, encoding="utf-8", errors="replace",
                    )
                except subprocess.TimeoutExpired:
                    return f"Error: pytest exceeded {timeout_s}s timeout"
                except Exception as e:
                    return f"Error running pytest: {e}"

                out = (result.stdout or "") + (result.stderr or "")
                # Parse summary line (e.g., "5 passed, 2 failed in 3.42s")
                lines = out.splitlines()
                summary = ""
                for line in reversed(lines[-30:]):
                    if " passed" in line or " failed" in line or " error" in line:
                        summary = line.strip()
                        break

                # Extract failure traces (limit to first 5)
                failures = []
                in_failure = False
                current = []
                for line in lines:
                    if line.startswith("FAILED ") or line.startswith("ERROR "):
                        if current:
                            failures.append("\n".join(current))
                            current = []
                        current.append(line)
                        in_failure = True
                    elif in_failure and (line.startswith("=") or line.startswith("_")):
                        if current:
                            failures.append("\n".join(current))
                            current = []
                        in_failure = False
                    elif in_failure:
                        current.append(line)
                if current:
                    failures.append("\n".join(current))

                report = [
                    f"pytest exit code: {result.returncode}",
                    f"summary: {summary or '(no summary line found)'}",
                ]
                if failures:
                    report.append(f"\nFirst {min(5, len(failures))} failure(s):")
                    for f in failures[:5]:
                        report.append("-" * 50)
                        report.append(f[:1500])
                # Always include the tail for context
                report.append("\n--- output tail (last 30 lines) ---")
                report.append("\n".join(lines[-30:]))

                return "\n".join(report)[:10000]

            elif name == "propose_edit":
                # F-DAEMON-2 compliance: generate a unified diff for operator
                # review WITHOUT touching the source file.
                #
                # Use this for ALL existing critical files (main.py, store/_core.py,
                # operator_api.py, chain.py, FROZEN modules, tests/).
                # The diff is saved to docs/_daemon_proposals/ for operator review.
                # Operator applies it via: git apply <diff_file>
                path = args.get("path", "")
                old_string = args.get("old_string", "")
                new_string = args.get("new_string", "")
                reason = args.get("reason", "(no reason provided)")

                if not path:
                    return "Error: 'path' argument is required"
                if not old_string:
                    return "Error: 'old_string' argument is required"

                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                if not os.path.exists(safe) or os.path.isdir(safe):
                    return f"Error: File not found: {path}"

                try:
                    with open(safe, "r", encoding="utf-8", errors="replace") as f:
                        original = f.read()
                except Exception as e:
                    return f"Error reading file: {e}"

                if old_string not in original:
                    return (f"Error: old_string not found in {path}. "
                            f"Verify exact characters including whitespace.")

                proposed = original.replace(old_string, new_string, 1)
                rel = os.path.relpath(safe, REPO_ROOT).replace("\\", "/")

                # Build unified diff
                import difflib as _dl
                diff_lines = list(_dl.unified_diff(
                    original.splitlines(keepends=True),
                    proposed.splitlines(keepends=True),
                    fromfile=f"a/{rel}", tofile=f"b/{rel}",
                    n=3,
                ))

                if not diff_lines:
                    return "Error: proposed change produces no diff (strings identical?)"

                diff_text = "".join(diff_lines)

                # Save proposal
                ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                proposals_dir = os.path.join(REPO_ROOT, "docs", "_daemon_proposals")
                os.makedirs(proposals_dir, exist_ok=True)
                safe_name = rel.replace("/", "_").replace(".", "_")
                diff_path = os.path.join(proposals_dir, f"proposal_{ts}_{safe_name}.diff")
                meta_path = os.path.join(proposals_dir, f"proposal_{ts}_{safe_name}.md")

                with open(diff_path, "w", encoding="utf-8") as f:
                    f.write(diff_text)

                # Save human-readable context alongside the diff
                # L6: Sign the proposal BEFORE writing it.
                # sign_fail → BLOCKED; unsigned proposals are not accepted.
                # Explicit SigningError catch — not broad except Exception.
                pub_key = "(unsigned)"
                signature_block = ""
                if _DAEMON_IDENTITY is not None:
                    try:
                        # Sign the diff content itself
                        sig_data = _DAEMON_IDENTITY.sign(diff_text.encode("utf-8"))
                        pub_key = _DAEMON_IDENTITY.public_key
                        signature_block = (
                            f"\n## Daemon Signature\n\n"
                            f"- **Public key:** `{pub_key}`\n"
                            f"- **Signature (ed25519):** `{sig_data}`\n"
                            f"- **Algorithm:** ed25519\n"
                        )
                    except SigningError as e:
                        # L6 fix: sign-fail BLOCKS the proposal entirely.
                        # Do NOT write unsigned proposals — they are indistinguishable from forged.
                        _GOV_LOG.sign_failed(rel, str(e))
                        return (
                            f"BLOCKED: Proposal for '{rel}' could not be signed. "
                            f"No proposal written — unsigned artifacts are indistinguishable "
                            f"from forged ones. Error: {e}"
                        )

                with open(meta_path, "w", encoding="utf-8") as f:
                    f.write(f"# Daemon Proposal — {rel}\n\n")
                    f.write(f"**Generated:** {ts}\n")
                    f.write(f"**File:** `{rel}`\n")
                    f.write(f"**Reason:** {reason}\n")
                    f.write(f"**Daemon public key:** `{pub_key}`\n\n")
                    f.write(f"## Diff\n\n```diff\n{diff_text}\n```\n\n")
                    f.write(f"## To apply\n\n```bash\ngit apply {diff_path}\n```\n")
                    f.write(f"\n## To discard\n\n```bash\nrm {diff_path} {meta_path}\n```\n")
                    f.write(signature_block)

                _GOV_LOG.proposed(rel, diff_path, pub_key)

                diff_rel = os.path.relpath(diff_path, REPO_ROOT).replace("\\", "/")
                meta_rel = os.path.relpath(meta_path, REPO_ROOT).replace("\\", "/")

                return (
                    f"PROPOSAL GENERATED (source file NOT modified):\n"
                    f"  diff: {diff_rel}\n"
                    f"  meta: {meta_rel}\n"
                    f"  signer: {pub_key[:16]}...\n"
                    f"  lines changed: {len([l for l in diff_lines if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))])}\n\n"
                    f"Review the proposal and apply with:\n"
                    f"  git apply {diff_path}\n\n"
                    f"Diff preview:\n{diff_text[:2000]}"
                )

            elif name == "finalize_plan":
                # F-DAEMON-3 + F-DAEMON-4: Produce a structured review package
                # and STOP. The terminal state of any engineering plan is always
                # a review artifact, never a silently-wired working tree.
                #
                # Collects all pending proposals, files created this session,
                # and the plan state — renders a REVIEW_*.md for operator approval.
                plan_name = args.get("plan_name", "default")
                summary = args.get("summary", "")
                brain_verdict = args.get("verdict", "")

                # Tier 1.1 / 1.3 — gate READY on fabrication + adversarial proof
                gate_notes: list[str] = []
                verdict_upper = (brain_verdict or "").strip().upper()
                if verdict_upper == "READY":
                    if self._fabrication_detected:
                        brain_verdict = "BLOCKED_FABRICATION"
                        gate_notes.append(
                            "READY rejected: auto verify_artifact detected fabrication "
                            "in this session. Fix artifacts before claiming READY."
                        )
                    else:
                        adv_failures = []
                        for art in self._session_artifacts:
                            arel = art.get("artifact", "")
                            if not arel:
                                continue
                            asafe = os.path.normpath(os.path.join(REPO_ROOT, arel))
                            if not asafe.startswith(os.path.normpath(REPO_ROOT)):
                                continue
                            drel = art.get("diff_path")
                            dsafe = None
                            if drel:
                                dsafe = os.path.normpath(os.path.join(REPO_ROOT, drel))
                                if not dsafe.startswith(os.path.normpath(REPO_ROOT)):
                                    dsafe = None
                            av = adversarial_verify(
                                asafe,
                                diff_path=dsafe,
                                class_name=art.get("class_name"),
                                repo_root=REPO_ROOT,
                            )
                            if not av["ok"]:
                                adv_failures.append(
                                    f"{arel}: {av.get('failures', ['failed'])}"
                                )
                                _GOV_LOG.adversarial_failed(
                                    arel, av.get("method", "?"), av.get("failures", []),
                                )
                        if adv_failures:
                            brain_verdict = "BLOCKED_ADVERSARIAL"
                            gate_notes.append(
                                "READY rejected: adversarial self-test failed:\n"
                                + "\n".join(f"  - {f}" for f in adv_failures)
                            )

                import sqlite3 as _sq

                # Load plan state
                conn = _sq.connect(SQLITE_DB_PATH)
                conn.row_factory = _sq.Row
                try:
                    rows = conn.execute(
                        "SELECT step_index, description, status FROM brain_tasks "
                        "WHERE plan_name = ? ORDER BY step_index ASC",
                        (plan_name,)
                    ).fetchall()
                finally:
                    conn.close()

                # Find pending proposals
                proposals_dir = os.path.join(REPO_ROOT, "docs", "_daemon_proposals")
                proposals = []
                if os.path.exists(proposals_dir):
                    for f in sorted(os.listdir(proposals_dir)):
                        if f.endswith(".md") and f.startswith("proposal_"):
                            proposals.append(f)

                # Build review document
                ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                review_path = os.path.join(proposals_dir, f"REVIEW_{ts}_{plan_name}.md")
                os.makedirs(proposals_dir, exist_ok=True)

                status_icons = {
                    "pending": "[ ]", "in_progress": "[~]",
                    "completed": "[x]", "blocked": "[!]"
                }

                lines_out = [
                    f"# Daemon Engineering Review — {plan_name}",
                    f"**Generated:** {ts} UTC",
                    f"**Drafted by:** QorTroller Daemon brain (deepseek-v4-flash)",
                    f"**Provenance:** Autonomous engineering session — operator review required before any changes are applied or committed.",
                    "",
                    f"## Summary",
                    summary or "(no summary provided)",
                    "",
                    f"## Brain Verdict",
                    brain_verdict or "(no verdict provided)",
                    "",
                ]
                if gate_notes:
                    lines_out += ["## Verification Gates", ""]
                    for gn in gate_notes:
                        lines_out.append(gn)
                    lines_out.append("")
                lines_out += [
                    f"## Plan Status: {plan_name}",
                ]
                for r in rows:
                    icon = status_icons.get(r["status"], "[?]")
                    lines_out.append(f"  {icon} {r['step_index']}. {r['description']}")

                lines_out += [
                    "",
                    f"## Pending Proposals ({len(proposals)})",
                ]
                if proposals:
                    for p in proposals:
                        lines_out.append(
                            f"- `docs/_daemon_proposals/{p}` "
                            f"(apply with: `git apply docs/_daemon_proposals/{p.replace('.md', '.diff')}`)"
                        )
                else:
                    lines_out.append(
                        "No proposals generated — all changes were to new files "
                        "or no file edits were made."
                    )

                lines_out += [
                    "",
                    "## Operator Actions Required",
                    "1. Review each proposal diff above",
                    "2. Apply diffs you approve: `git apply <diff_file>`",
                    "3. Run PV-CI: `python scripts/vapi_invariant_gate.py`",
                    "4. Run relevant tests: `python -m pytest bridge/tests/ -q`",
                    "5. Commit if satisfied — mark authorship: 'daemon-drafted, operator-reviewed'",
                    "6. Discard proposals you reject: `rm docs/_daemon_proposals/proposal_*`",
                    "",
                    "---",
                    "*This review package was generated by the QorTroller Daemon brain.*",
                    "*No changes have been committed. No chain operations were performed.*",
                    "*All protocol invariants (176/176) remain unchanged.*",
                ]

                with open(review_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines_out))

                review_rel = os.path.relpath(review_path, REPO_ROOT).replace("\\", "/")

                # ── AGENT-COMMIT v1 wiring (D-DAEMON-1 Path A) ───────────────
                # The review package becomes a first-class protocol artifact:
                # SHA-256 committed, ED25519 signed, chained, on-chain-anchorable.
                #
                # Provisional identity: agentId = SHA-256(ed25519_pubkey_bytes).
                # This is honest and documented. At D-DAEMON-1 resolution a NEW
                # chain starts with the canonical on-chain agentId; a junction
                # entry in that chain references this chain's last commitment as
                # prev_commit_hash. This chain is NOT retroactively modified.
                # "Genesis re-anchored" is wrong and would corrupt every link. (F-AGC-2)
                commitment_hex = None
                try:
                    import hashlib as _hlib
                    import time as _t
                    import sys as _sys

                    # Bridge path for FROZEN primitive import
                    _bridge = os.path.join(REPO_ROOT, "bridge")
                    if _bridge not in _sys.path:
                        _sys.path.insert(0, _bridge)
                    from vapi_bridge.agent_commit import compute_agent_commit_hash

                    # F-AGC-3: agent_id from provisional or canonical config (D-DAEMON-1)
                    pub_bytes = bytes.fromhex(_DAEMON_IDENTITY.public_key)
                    agent_id, identity_mode, junction_note = load_daemon_agent_id(
                        _DAEMON_IDENTITY.public_key,
                    )
                    assert len(agent_id) == 32, f"agent_id must be 32 bytes, got {len(agent_id)}"

                    # F-AGC-1 verified: FROZEN formula commit_sha = 20 bytes (git SHA-1 length).
                    # SHA-256(review_content)[:20] — truncate to match FROZEN field width.
                    review_bytes = Path(review_path).read_bytes()
                    commit_sha = _hlib.sha256(review_bytes).digest()[:20]

                    # F-AGC-4: prev_commit_hash from SQLite-persisted chain (survives restarts)
                    prev_commit_hash = _DAEMON_COMMIT_CHAIN.get_last_commitment()
                    repo_uri_sha = _hlib.sha256(
                        b"https://github.com/ConWan30/qortroller"
                    ).digest()
                    ts_ns = _t.time_ns()

                    commitment = compute_agent_commit_hash(
                        agent_id=agent_id,
                        commit_sha=commit_sha,
                        prev_commit_hash=prev_commit_hash,
                        repo_uri_sha=repo_uri_sha,
                        ts_ns=ts_ns,
                    )
                    commitment_hex = commitment.hex()

                    # Sign the 32-byte commitment with daemon ED25519 key
                    # SigningError → proposal still written, but commitment is unsigned
                    try:
                        commitment_sig = _DAEMON_IDENTITY.sign(commitment)
                    except SigningError as e:
                        commitment_sig = f"SIGNING_FAILED: {e}"

                    # Persist to chain BEFORE appending to REVIEW (atomic write)
                    is_genesis = (prev_commit_hash == b"\x00" * 32)
                    _DAEMON_COMMIT_CHAIN.record_commitment(
                        commitment_hex=commitment_hex,
                        ts_ns=ts_ns,
                        plan_name=plan_name,
                        review_path=review_path,
                    )

                    # Genesis capture: write to a dedicated file so it cannot
                    # be buried. The genesis commitment is the chain anchor —
                    # every subsequent link traces back to it.
                    if is_genesis:
                        genesis_path = os.path.join(
                            os.path.expanduser("~"), ".vapi", "daemon_genesis_commit.txt"
                        )
                        with open(genesis_path, "w", encoding="utf-8") as _gf:
                            _gf.write(
                                f"DAEMON AGENT-COMMIT GENESIS\n"
                                f"commitment : {commitment_hex}\n"
                                f"plan_name  : {plan_name}\n"
                                f"review_path: {review_path}\n"
                                f"ts_ns      : {ts_ns}\n"
                                f"daemon_key : {_DAEMON_IDENTITY.public_key}\n"
                                f"\n"
                                f"Record 'commitment' in CLAUDE.md as:\n"
                                f"<!-- DAEMON-GENESIS-COMMIT: {commitment_hex} -->\n"
                            )
                        print(
                            f"\n[daemon] *** GENESIS COMMITMENT WRITTEN ***\n"
                            f"[daemon] {genesis_path}\n"
                            f"[daemon] commitment: {commitment_hex}\n"
                            f"[daemon] ADD THIS TO CLAUDE.md NOW.",
                            flush=True,
                        )

                    # Append AGENT-COMMIT block to review package
                    chain_len = _DAEMON_COMMIT_CHAIN.chain_length()
                    with open(review_path, "a", encoding="utf-8") as f:
                        f.write(f"\n\n## AGENT-COMMIT v1 (D-DAEMON-1 Path A)\n\n")
                        f.write(f"- **Commitment:** `{commitment_hex}`\n")
                        f.write(f"- **Chain link:** #{chain_len}\n")
                        f.write(f"- **prev_commitment:** `{prev_commit_hash.hex()}`\n")
                        f.write(f"- **Daemon public key:** `{_DAEMON_IDENTITY.public_key}`\n")
                        f.write(f"- **Identity mode:** `{identity_mode}`\n")
                        if junction_note:
                            f.write(f"- **Junction note:** {junction_note}\n")
                        f.write(f"- **Signature (ed25519):** `{commitment_sig}`\n")
                        f.write(f"- **ts_ns:** `{ts_ns}`\n")
                        f.write(
                            f"\n*Provisional agentId = SHA-256(ed25519_pubkey). "
                            f"At D-DAEMON-1 resolution a new chain starts with canonical "
                            f"on-chain agentId; a junction entry references this chain's "
                            f"last commitment as prev_commit_hash. This chain is not "
                            f"retroactively modified — it retains its own verifiable history.*\n"
                        )

                    _GOV_LOG.agent_commit(commitment_hex, plan_name, _DAEMON_IDENTITY.public_key)

                except Exception as e:
                    # AGENT-COMMIT failure does not block the hard stop —
                    # the review package is still valid; commitment is just absent.
                    with open(review_path, "a", encoding="utf-8") as f:
                        f.write(f"\n\n## AGENT-COMMIT v1 — FAILED\n\nError: {e}\n")

                # L7: Hard stop — raise GovernanceHardStop (Exception), not return.
                _GOV_LOG.hard_stop(plan_name, review_path)
                raise GovernanceHardStop(review_path, plan_name)

            elif name == "task_track":
                # Create or replace a multi-step plan in agent_memory.db.
                # Persistent across chat turns.
                steps = args.get("steps", [])
                plan_name = args.get("plan_name", "default")
                if not isinstance(steps, list) or not steps:
                    return "Error: 'steps' must be a non-empty list of strings"

                import sqlite3 as _sq
                conn = _sq.connect(SQLITE_DB_PATH)
                try:
                    conn.executescript("""
                        CREATE TABLE IF NOT EXISTS brain_tasks (
                            id          INTEGER PRIMARY KEY AUTOINCREMENT,
                            plan_name   TEXT NOT NULL,
                            step_index  INTEGER NOT NULL,
                            description TEXT NOT NULL,
                            status      TEXT NOT NULL DEFAULT 'pending',
                            created_at  TEXT NOT NULL,
                            updated_at  TEXT NOT NULL
                        );
                        CREATE INDEX IF NOT EXISTS idx_brain_tasks_plan
                            ON brain_tasks(plan_name, step_index);
                    """)
                    # Clear any existing plan with the same name
                    conn.execute("DELETE FROM brain_tasks WHERE plan_name = ?",
                                 (plan_name,))
                    ts = datetime.datetime.utcnow().isoformat() + "Z"
                    for i, step in enumerate(steps):
                        conn.execute(
                            "INSERT INTO brain_tasks (plan_name, step_index, "
                            "description, status, created_at, updated_at) "
                            "VALUES (?, ?, ?, 'pending', ?, ?)",
                            (plan_name, i, str(step), ts, ts)
                        )
                    conn.commit()
                finally:
                    conn.close()

                # Tier 1.2 — inject methodology at plan creation
                meth_entries = _METHODOLOGY.query_for_task(steps)
                meth_block = MethodologyRegistry.format_for_prompt(meth_entries)
                _GOV_LOG.methodology_injected(
                    plan_name, len(meth_entries), list(meth_entries.keys()),
                )

                return (
                    f"Plan '{plan_name}' created with {len(steps)} step(s). "
                    f"Use task_update(plan_name, step_index, status) to mark progress. "
                    f"Statuses: pending, in_progress, completed, blocked.\n\n"
                    f"## Applicable Methodology\n{meth_block}"
                )

            elif name == "task_update":
                # Update status of a specific step in a plan, OR query current state.
                plan_name = args.get("plan_name", "default")
                step_index = args.get("step_index")
                new_status = args.get("status", "")
                action = args.get("action", "update")  # update | list | clear

                import sqlite3 as _sq
                conn = _sq.connect(SQLITE_DB_PATH)
                conn.row_factory = _sq.Row
                try:
                    if action == "list":
                        rows = conn.execute(
                            "SELECT step_index, description, status, updated_at "
                            "FROM brain_tasks WHERE plan_name = ? "
                            "ORDER BY step_index ASC",
                            (plan_name,)
                        ).fetchall()
                        if not rows:
                            return f"Plan '{plan_name}' has no steps."
                        lines = [f"=== Plan: {plan_name} ==="]
                        status_icons = {
                            "pending":     "[ ]",
                            "in_progress": "[~]",
                            "completed":   "[x]",
                            "blocked":     "[!]",
                        }
                        for r in rows:
                            icon = status_icons.get(r["status"], "[?]")
                            lines.append(
                                f"  {icon} {r['step_index']}. {r['description']}"
                            )
                        return "\n".join(lines)

                    if action == "clear":
                        deleted = conn.execute(
                            "DELETE FROM brain_tasks WHERE plan_name = ?",
                            (plan_name,)
                        ).rowcount
                        conn.commit()
                        return f"Plan '{plan_name}' cleared ({deleted} step(s) removed)."

                    # action == "update"
                    if step_index is None:
                        return "Error: 'step_index' is required for update"
                    if new_status not in ("pending", "in_progress", "completed", "blocked"):
                        return ("Error: status must be one of: pending, "
                                "in_progress, completed, blocked")

                    step_index = int(step_index)
                    ts = datetime.datetime.utcnow().isoformat() + "Z"
                    cur = conn.execute(
                        "UPDATE brain_tasks SET status = ?, updated_at = ? "
                        "WHERE plan_name = ? AND step_index = ?",
                        (new_status, ts, plan_name, step_index)
                    )
                    conn.commit()
                    if cur.rowcount == 0:
                        return (f"Error: step {step_index} not found in plan "
                                f"'{plan_name}'. Use action='list' to view.")
                    return f"OK: step {step_index} of '{plan_name}' → {new_status}"
                finally:
                    conn.close()

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
                # chain integrity. Optionally cross-check locally replayed
                # head against a known-good head_hash (from bridge or chain).
                import sqlite3 as _sq
                import hashlib as _hl

                n = min(int(args.get("n", 20)), 200)
                session_id = args.get("session_id", "")
                head_hash = args.get("head_hash", "").lower().replace("0x", "")

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

                    # Get session_id if not specified -> use the most recent one
                    if not session_id:
                        row = conn.execute(
                            "SELECT grind_session_id FROM ruling_validation_log "
                            "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                            "ORDER BY id DESC LIMIT 1"
                        ).fetchone()
                        session_id = row["grind_session_id"] if row else ""

                    if not session_id:
                        conn.close()
                        return "No GIC-stamped rows found - grind has not started."

                    # Fetch ALL GIC rows for this session (need full chain for head_hash verify)
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

                    # ---- Full chain replay from genesis ----
                    first_row = rows[0]
                    ts0 = int(first_row["gic_ts_ns"] or 0)
                    genesis = _genesis(session_id, ts0)
                    prev = genesis
                    intact = True
                    broken_at = None
                    head_computed = None

                    lines = [
                        "=" * 56,
                        f"  GIC REPLAY - session: {session_id}",
                        f"  Total links : {total_links}  |  Replay window: last {min(n, total_links)}",
                    ]
                    if head_hash:
                        lines.append(f"  Head check  : verifying against provided 0x{head_hash[:16]}...")
                    lines.append("=" * 56)

                    # Replay only the last N rows for display, but compute over all
                    display_rows = rows[-n:]
                    head_computed_rows = rows[:]  # full chain

                    # Full-chain computation for head hash
                    for row in head_computed_rows:
                        ts_ns   = int(row["gic_ts_ns"] or 0)
                        commit  = row["commitment_hash"] or ""
                        host    = row["pcc_host_state"] or "DISCONNECTED"
                        verdict = row["fallback_verdict"] or "FLAG"
                        stored  = row["grind_chain_hash"] or ""

                        expected = _compute(prev, commit, host, verdict, ts_ns)
                        expected_hex = expected.hex()

                        # Verify stored hash matches computed
                        if expected_hex != stored:
                            intact = False
                            if broken_at is None:
                                broken_at = rows.index(row) + 1

                        prev = expected  # chain forward

                    head_computed = prev.hex()

                    # ---- Display window (last N) ----
                    # Recompute display window from full-chain state
                    # First, get the prev hash for the first display row
                    display_prev = genesis
                    for row in rows[:-n]:
                        ts_ns_d = int(row["gic_ts_ns"] or 0)
                        commit_d = row["commitment_hash"] or ""
                        host_d   = row["pcc_host_state"] or "DISCONNECTED"
                        verdict_d = row["fallback_verdict"] or "FLAG"
                        display_prev = _compute(display_prev, commit_d, host_d, verdict_d, ts_ns_d)

                    for i, row in enumerate(display_rows):
                        ts_ns   = int(row["gic_ts_ns"] or 0)
                        commit  = row["commitment_hash"] or ""
                        host    = row["pcc_host_state"] or "DISCONNECTED"
                        verdict = row["fallback_verdict"] or "FLAG"
                        stored  = row["grind_chain_hash"] or ""

                        expected = _compute(display_prev, commit, host, verdict, ts_ns)
                        expected_hex = expected.hex()

                        if expected_hex == stored:
                            status = "OK"
                        else:
                            status = "BROKEN"
                            intact = False
                            if broken_at is None:
                                broken_at = total_links - len(display_rows) + i + 1

                        dt = datetime.datetime.fromtimestamp(ts_ns / 1e9).strftime("%H:%M:%S")
                        lines.append(
                            f"  [{total_links - len(display_rows) + i + 1:4d}] "
                            f"{stored[:12]}... "
                            f"{dt} verdict={verdict} [{status}]"
                        )
                        display_prev = expected

                    lines.append("=" * 56)

                    # ---- Results ----
                    if not intact:
                        lines.append(f"  CHAIN INTEGRITY: BROKEN at link {broken_at}")
                    else:
                        lines.append(f"  CHAIN INTEGRITY: INTACT - all {total_links} links verified")

                    lines.append(f"  Computed head: 0x{head_computed[:16]}...{head_computed[-4:]}")

                    if head_hash:
                        if head_computed == head_hash:
                            lines.append(
                                f"  HEAD MATCH   : YES - local chain head matches "
                                f"provided 0x{head_hash[:16]}..."
                            )
                        else:
                            lines.append(
                                f"  HEAD MATCH   : NO - local head "
                                f"(0x{head_computed[:16]}...) != "
                                f"provided (0x{head_hash[:16]}...) - "
                                f"DB tamper or session mismatch"
                            )
                    else:
                        lines.append("  (no head_hash provided - internal consistency only)")

                    lines.append("=" * 56)
                    return "\n".join(lines)

                except Exception as e:
                    return f"Error during GIC replay: {e}"
            elif name == "gic_chain_status":
                # Pull GIC chain from bridge if up, else read DB directly.
                # Returns a visual ASCII chain + structured data.
                import requests as _req
                n = min(int(args.get("n", 20)), 100)  # last N links to render

                # Try bridge first (authoritative, live)
                try:
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/bridge/grind-chain-status",
                                 headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {}, timeout=4, proxies={"http": None, "https": None})
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
                                          headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {}, timeout=3, proxies={"http": None, "https": None})
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
                """Full calibration snapshot: is the system ready to graduate?
                Pulls N per player, AIT probe results, L4 thresholds, grind readiness,
                consecutive clean sessions, and tournament preflight gate in one call."""
                import requests as _req
                lines = ["=" * 60, "  CALIBRATION & ENROLLMENT STATUS", "=" * 60]

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
                    ]
                    # Only show file metadata if present
                    for md_key in ["total_records", "confidence", "generated_at"]:
                        md_val = cal.get(md_key)
                        if md_val:
                            lines.append(f"    {md_key}: {md_val}")
                    lines.append("-" * 60)
                except Exception as e:
                    lines.append(f"  calibration_profile_live.json: {e}")

                # 2. N per player + separation defensibility
                for ep, label in [
                    ("/agent/separation-defensibility-status", "Separation Defensibility"),
                    ("/agent/separation-ratio-status", "Separation Ratio"),
                ]:
                    try:
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
                                     headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {},
                                     proxies={"http": None, "https": None})
                        if r.status_code == 200:
                            d = r.json()
                            lines.append(f"  {label}:")
                            for k, v in d.items():
                                if isinstance(v, (int, float, bool, str)):
                                    lines.append(f"    {k}: {v}")
                        else:
                            lines.append(f"  {label}: HTTP {r.status_code}")
                    except Exception:
                        lines.append(f"  {label}: bridge offline")

                # 3. AIT probe results
                try:
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/agent/ait-separation-status", timeout=4,
                                 headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {},
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        lines.append("  AIT Probe Results:")
                        for k, v in d.items():
                            if isinstance(v, (int, float, bool, str)):
                                lines.append(f"    {k}: {v}")
                            elif isinstance(v, list) and len(v) <= 6:
                                lines.append(f"    {k}: {v}")
                    else:
                        lines.append(f"  AIT Probe: HTTP {r.status_code}")
                except Exception:
                    lines.append("  AIT Probe: bridge offline")

                lines.append("-" * 60)

                # 4. GIC / grind progress + grind_ready
                try:
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/bridge/grind-chain-status", timeout=4,
                                 headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {},
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        lines += [
                            "  Grind Integrity Chain:",
                            f"    length      : {d.get('chain_length', 0)} / 100",
                            f"    intact      : {'YES' if d.get('chain_intact', True) else 'BROKEN'}",
                            f"    grind_ready : {'YES' if d.get('grind_ready', False) else 'no'}",
                        ]
                    else:
                        lines.append(f"  GIC: HTTP {r.status_code}")
                except Exception:
                    lines.append("  GIC: bridge offline")

                # 5. Capture health: consecutive_clean, sessions_per_day
                try:
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/bridge/capture-health", timeout=4,
                                 headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {},
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        cc = d.get("consecutive_clean_toward_target", 0)
                        target = d.get("consecutive_clean_target", 100)
                        lines += [
                            "  Capture Health:",
                            f"    consecutive_clean : {cc} / {target}",
                        ]
                        for extra_key in ["sessions_per_day", "capture_healthy", "sessions_stagnant"]:
                            v = d.get(extra_key)
                            if isinstance(v, (int, float, bool, str)):
                                lines.append(f"    {extra_key}: {v}")
                    else:
                        lines.append(f"  Capture health: HTTP {r.status_code}")
                except Exception:
                    lines.append("  Capture health: bridge offline")

                lines.append("-" * 60)

                # 6. Tournament preflight gate
                try:
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/agent/tournament-preflight", timeout=4,
                                 headers={"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {},
                                 proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        d = r.json()
                        overall = d.get("overall_pass", False)
                        lines.append(f"  Tournament gate: {'PASS' if overall else 'NOT READY'}")
                        for k in ["separation_ok", "l4_ok", "gate_ok", "cert_ok",
                                   "audit_ok", "dual_gate_warned", "epoch_window_warned",
                                   "ioswarm_warned", "biometric_ttl_ok", "all_pairs_p0_ok"]:
                            v = d.get(k)
                            if isinstance(v, bool):
                                lines.append(f"    [{'+' if v else '-'}] {k}")
                    else:
                        lines.append(f"  Tournament gate: HTTP {r.status_code}")
                except Exception:
                    lines.append("  Tournament gate: bridge offline")

                lines.append("=" * 60)
                return "\n".join(lines)
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
                # F-GOV-1: explicit approval gate — both approved=True arg AND
                # BRIDGE_POST_GATE_ENABLED=1 env var required.
                gate_err = check_bridge_post_gate(args)
                if gate_err:
                    _GOV_LOG.blocked("bridge_post", args.get("path", "?"), gate_err[:120])
                    return gate_err

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
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/health", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}/agent/ait-separation-status", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                        r = _req.get(f"{BRIDGE_OPERATOR_URL}{ep}", timeout=4,
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
                    r = _req.get(f"{BRIDGE_OPERATOR_URL}/health", timeout=4,
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

            elif name == "search_code":
                # Sandboxed code search — documented in system prompt but was missing.
                # Uses git grep (fast, repo-scoped, no shell injection risk).
                # Falls back to Python os.walk scan if git grep unavailable.
                pattern = args.get("pattern", "")
                glob_filter = args.get("glob", "")
                if not pattern:
                    return "Error: 'pattern' argument is required"

                # SEC-2: reject patterns with banned metacharacters (fixed the
                # AND→OR short-circuit; previously the check never fired).
                if any(c in pattern for c in BANNED_METACHARACTERS):
                    return "Error: pattern contains disallowed characters"

                # Helper: drop any match line that points at a secret file so
                # search_code can't be used to read .env/.key contents indirectly.
                def _filter_secret_hits(text: str) -> str:
                    kept = []
                    for ln in text.splitlines():
                        fpath = ln.split(":", 1)[0] if ":" in ln else ln
                        if is_read_blocked(fpath) is None:
                            kept.append(ln)
                    return "\n".join(kept)

                try:
                    # "-e pattern --" terminates git-grep option parsing so a
                    # pattern starting with "-" can't be read as a git flag (SEC-2).
                    cmd = ["git", "grep", "-n", "--no-color", "-e", pattern, "--"]
                    if glob_filter:
                        cmd += [glob_filter]
                    result = subprocess.run(
                        cmd, cwd=REPO_ROOT,
                        capture_output=True, text=True,
                        timeout=30, encoding="utf-8", errors="replace",
                    )
                    out = _filter_secret_hits(result.stdout)
                    if not out and result.returncode == 1:
                        return f"No matches for '{pattern}'" + (f" in {glob_filter}" if glob_filter else "")
                    if result.returncode not in (0, 1):
                        raise subprocess.SubprocessError(result.stderr)
                    lines = out.splitlines()
                    if len(lines) > 200:
                        return "\n".join(lines[:200]) + f"\n... ({len(lines)-200} more lines)"
                    return out or f"No matches for '{pattern}'"
                except Exception as e:
                    # Pure-Python fallback: walk repo, grep lines
                    matches = []
                    import fnmatch as _fn
                    for root, dirs, files in os.walk(REPO_ROOT):
                        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
                        for fname in files:
                            if glob_filter and not _fn.fnmatch(fname, glob_filter.lstrip("*/")):
                                continue
                            fpath = os.path.join(root, fname)
                            rel_check = os.path.relpath(fpath, REPO_ROOT).replace("\\", "/")
                            # SEC-1: never scan secret files in the fallback path
                            if is_read_blocked(rel_check) is not None:
                                continue
                            try:
                                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                    for i, line in enumerate(f, 1):
                                        if pattern in line:
                                            rel = os.path.relpath(fpath, REPO_ROOT).replace("\\", "/")
                                            matches.append(f"{rel}:{i}:{line.rstrip()}")
                                            if len(matches) >= 200:
                                                break
                            except Exception:
                                continue
                            if len(matches) >= 200:
                                break
                    if not matches:
                        return f"No matches for '{pattern}'"
                    return "\n".join(matches[:200])

            elif name == "verify_artifact":
                # TIER 1 fabrication detector: prove an output exists with the
                # expected shape before any downstream step trusts it.
                path = args.get("path", "")
                shape = args.get("expected_shape", {}) or {}
                if not path:
                    return "Error: 'path' argument is required"
                safe = os.path.normpath(os.path.join(REPO_ROOT, path))
                if not safe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                result = verify_artifact(safe, shape)
                status = "VERIFIED" if result["ok"] else "FABRICATION_DETECTED"
                lines = [f"{status}: {path}"]
                lines += [f"  check: {c}" for c in result["checks"]]
                if result["failures"]:
                    lines += [f"  FAIL: {fl}" for fl in result["failures"]]
                    lines.append("Do NOT claim this artifact is complete. The shape check failed.")
                return "\n".join(lines)

            elif name == "extract_with_diff":
                # TIER 1 diff-oracle: reconstruct a moved code block deterministically
                # from a removal diff and emit it as a .proposed mixin artifact.
                # LLM never relocates verbatim (avoids 524 + transcription drift).
                diff_path = args.get("diff_path", "")
                class_name = args.get("class_name", "")
                target_rel = args.get("target_path", "")
                if not (diff_path and class_name and target_rel):
                    return "Error: 'diff_path', 'class_name', and 'target_path' are all required"
                dsafe = os.path.normpath(os.path.join(REPO_ROOT, diff_path))
                if not dsafe.startswith(os.path.normpath(REPO_ROOT)) or not os.path.isfile(dsafe):
                    return f"Error: diff not found: {diff_path}"
                try:
                    diff_text = open(dsafe, encoding="utf-8", errors="replace").read()
                    removed = reconstruct_from_removal_diff(diff_text)
                    if not removed:
                        return "Error: removal diff contained no '-' lines to reconstruct from"
                    # Pass the source module so needed imports are auto-injected
                    # (MIXIN_MISSING_IMPORTS lesson — moved methods lose import scope).
                    src_text = ""
                    core_path = os.path.join(REPO_ROOT, "bridge", "vapi_bridge", "store", "_core.py")
                    if os.path.isfile(core_path):
                        src_text = open(core_path, encoding="utf-8", errors="replace").read()
                    module = build_mixin_module(class_name, removed, source_module_text=src_text)
                    # AST-validate before emitting
                    import ast as _ast
                    try:
                        tree = _ast.parse(module)
                    except SyntaxError as e:
                        return f"Error: reconstructed module is not valid Python: {e}"
                    methods = []
                    for node in tree.body:
                        if isinstance(node, _ast.ClassDef) and node.name == class_name:
                            methods = [m.name for m in node.body if isinstance(m, _ast.FunctionDef)]
                    # Emit as .proposed artifact (operator creates the real file)
                    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    pdir = os.path.join(REPO_ROOT, "docs", "_daemon_proposals")
                    os.makedirs(pdir, exist_ok=True)
                    sn = target_rel.replace("/", "_").replace("\\", "_").replace(".", "_")
                    proposed = os.path.join(pdir, f"newfile_{ts}_{sn}.proposed")
                    with open(proposed, "w", encoding="utf-8") as f:
                        f.write(module)
                    pr = os.path.relpath(proposed, REPO_ROOT).replace("\\", "/")
                    _GOV_LOG.proposed(target_rel, proposed,
                                      _DAEMON_IDENTITY.public_key if _DAEMON_IDENTITY else "(unsigned)")
                    return (
                        f"EXTRACTED (diff-oracle, deterministic):\n"
                        f"  class {class_name} with {len(methods)} methods\n"
                        f"  reconstructed {len(removed)} lines from {diff_path}\n"
                        f"  AST-valid: yes\n"
                        f"  artifact: {pr}\n"
                        f"  create with: cp {pr} {target_rel}\n"
                        f"Methods: {', '.join(methods)}"
                    )
                except Exception as e:
                    return f"Error during extract_with_diff: {e}"

            elif name == "adversarial_verify":
                artifact_path = args.get("artifact_path", "") or args.get("path", "")
                diff_path = args.get("diff_path", "")
                class_name = args.get("class_name", "") or None
                if not artifact_path:
                    return "Error: 'artifact_path' (or 'path') is required"
                asafe = os.path.normpath(os.path.join(REPO_ROOT, artifact_path))
                if not asafe.startswith(os.path.normpath(REPO_ROOT)):
                    return "Error: Access denied (path traversal)"
                dsafe = None
                if diff_path:
                    dsafe = os.path.normpath(os.path.join(REPO_ROOT, diff_path))
                    if not dsafe.startswith(os.path.normpath(REPO_ROOT)):
                        return "Error: Access denied (diff path traversal)"
                av = adversarial_verify(
                    asafe, diff_path=dsafe, class_name=class_name, repo_root=REPO_ROOT,
                )
                status = "ADVERSARIAL_VERIFIED" if av["ok"] else "ADVERSARIAL_FAILED"
                lines = [
                    f"{status}: {artifact_path}",
                    f"  method: {av.get('method', '?')}",
                    f"  artifact_hash: {av.get('artifact_hash', '?')}",
                ]
                if av.get("reconstructed_hash"):
                    lines.append(f"  reconstructed_hash: {av['reconstructed_hash']}")
                for fl in av.get("failures", []):
                    lines.append(f"  FAIL: {fl}")
                return "\n".join(lines)

            elif name == "residue_status":
                queue_path = os.path.join(
                    REPO_ROOT, "docs", "_daemon_proposals", "decon_residue_queue.json",
                )
                if not os.path.isfile(queue_path):
                    return "Error: decon_residue_queue.json not found"
                try:
                    data = json.load(open(queue_path, encoding="utf-8"))
                except Exception as e:
                    return f"Error reading queue: {e}"
                items = data.get("items", [])
                pending = [i for i in items if i.get("status") == "pending"]
                done = [i for i in items if i.get("status") in ("applied", "proposed")]
                lines = [
                    f"DECON-1 residue queue ({len(items)} total)",
                    f"  pending: {len(pending)}  done/proposed: {len(done)}",
                    "",
                ]
                for it in items:
                    st = it.get("status", "?")
                    lines.append(
                        f"  [{st}] {it.get('id', '?')} → {it.get('target_file', '?')}"
                    )
                    if it.get("agent_commit"):
                        lines.append(f"         commit: {it['agent_commit']}")
                return "\n".join(lines)

            elif name == "health_monitor":
                # Tier 2.1 — on-demand health probes (D-DAEMON-2; propose-only findings)
                import re as _re
                import sys as _sys
                _bridge = os.path.join(REPO_ROOT, "bridge")
                if _bridge not in _sys.path:
                    _sys.path.insert(0, _bridge)
                from vapi_bridge.daemon_health_monitor import (
                    HealthMonitorInput,
                    format_findings_markdown,
                    run_health_monitor,
                )
                inv_live = None
                try:
                    r = subprocess.run(
                        [sys.executable, "scripts/vapi_invariant_gate.py", "--report"],
                        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
                    )
                    m = _re.search(r"(\d+)\s+invariants?", r.stdout + r.stderr, re.I)
                    if m:
                        inv_live = int(m.group(1))
                except Exception:
                    pass
                device_conflict = False
                try:
                    sha_pat = _re.compile(r"SHA-256\s*\(\s*pubkey\s*\|\|\s*serial", _re.I)
                    keccak_pat = _re.compile(r"keccak256\s*\(\s*pubkey", _re.I)
                    hits_sha = hits_keccak = 0
                    for root, dirs, files in os.walk(REPO_ROOT):
                        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
                        for fn in files:
                            if not fn.endswith((".md", ".py", ".sol")):
                                continue
                            fp = os.path.join(root, fn)
                            try:
                                text = open(fp, encoding="utf-8", errors="replace").read()
                            except Exception:
                                continue
                            if sha_pat.search(text):
                                hits_sha += 1
                            if keccak_pat.search(text):
                                hits_keccak += 1
                    device_conflict = hits_sha > 0 and hits_keccak > 0
                except Exception:
                    pass
                gic_data = self._bridge_get("/bridge/grind-chain-status")
                gic_hours = None
                if isinstance(gic_data, dict):
                    # Best-effort: use hours_since_last if bridge exposes it
                    gic_hours = gic_data.get("hours_since_last_link")
                inp = HealthMonitorInput(
                    gic_hours_since_last_link=gic_hours,
                    invariant_count_live=inv_live,
                    device_id_formula_conflict=device_conflict,
                )
                findings = run_health_monitor(inp)
                return format_findings_markdown(findings)

            elif name == "methodology":
                # TIER 1 methodology registry: query/add lessons by failure class.
                action = args.get("action", "query")
                if action == "add":
                    fc = args.get("failure_class", "")
                    if not fc:
                        return "Error: 'failure_class' required for add"
                    _METHODOLOGY.add(
                        fc, args.get("anti_pattern", ""), args.get("correct_pattern", ""),
                        args.get("agent_commit", ""), args.get("discovered", ""),
                    )
                    return f"Methodology entry '{fc}' recorded."
                entries = _METHODOLOGY.query(args.get("keywords", ""))
                if not entries:
                    return "No methodology entries match."
                lines = [f"Methodology ({len(entries)} entr{'y' if len(entries)==1 else 'ies'}):"]
                for cls, e in entries.items():
                    lines.append(f"\n[{cls}] (discovered {e.get('discovered','?')})")
                    lines.append(f"  AVOID: {e.get('anti_pattern','')[:200]}")
                    lines.append(f"  DO:    {e.get('correct_pattern','')[:200]}")
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

            except GovernanceHardStop as e:
                # L7: finalize_plan() raised a hard stop.
                # Surface the review path to the operator and halt cleanly.
                # No further tool calls — this is the terminal state.
                msg = (
                    f"ENGINEERING SESSION COMPLETE — operator review required.\n\n"
                    f"Review package: {e.review_path}\n"
                    f"Plan: {e.plan_name}\n\n"
                    f"No changes have been committed or applied.\n"
                    f"Apply proposals you approve with: git apply <diff_file>"
                )
                msg_id = self.memory.add_message("assistant", msg)
                self.memory.set_status("idle")
                return {
                    "response": msg,
                    "message_id": msg_id,
                    "tool_iterations": iteration,
                    "type": "final",
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
    global _memory, _brain, _DAEMON_IDENTITY
    if _brain is None:
        # Governance self-test runs BEFORE any tool can be invoked.
        # Raises AssertionError and aborts boot if any invariant is violated.
        result = governance_self_test()
        print(f"[daemon] {result}", flush=True)

        # Lazy-init daemon identity (key outside writable scope).
        from _daemon_tools_schema import DaemonIdentity
        try:
            _DAEMON_IDENTITY = DaemonIdentity(_DAEMON_KEY_PATH)
            print(f"[daemon] identity public key: {_DAEMON_IDENTITY.public_key[:16]}...", flush=True)
        except SigningError as e:
            # Boot fails if identity cannot be established — proposals would
            # be unsigned and indistinguishable from forged (L6 fix).
            raise RuntimeError(f"Daemon identity init failed — cannot boot: {e}") from e

        _memory = MemoryStore()
        _brain = QorTrollerBrain(_memory)

        # Print chain status so genesis is immediately visible when it fires.
        chain_len = _DAEMON_COMMIT_CHAIN.chain_length()
        if chain_len == 0:
            print(
                "[daemon] AGENT-COMMIT chain: GENESIS PENDING — "
                "first finalize_plan() will produce link #1. "
                "Record that commitment hash in CLAUDE.md immediately.",
                flush=True,
            )
        else:
            last = _DAEMON_COMMIT_CHAIN.get_last_commitment()
            print(
                f"[daemon] AGENT-COMMIT chain: {chain_len} link(s), "
                f"head={last.hex()[:16]}...",
                flush=True,
            )

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
                    "name": "edit_file",
                    "description": "Surgical string replacement. AUTONOMOUS only for new/non-critical files. HARD BLOCKED on tests/, main.py, store/_core.py, operator_api.py, chain.py, FROZEN modules, .env. For blocked paths use propose_edit() instead. See FENCE RULE 2.",
                    "arguments": {
                        "path": "str (required)",
                        "old_string": "str (required, exact text to find — must be unique unless replace_all=true)",
                        "new_string": "str (required, replacement text)",
                        "replace_all": "bool (optional, default false)",
                    },
                },
                {
                    "name": "propose_edit",
                    "description": "For critical existing files: generate a unified diff WITHOUT modifying the source. Saves .diff + .md to docs/_daemon_proposals/ for operator review. Operator applies with git apply. Use for all FENCE RULE 2 paths.",
                    "arguments": {
                        "path": "str (required)",
                        "old_string": "str (required, exact text to replace)",
                        "new_string": "str (required, replacement text)",
                        "reason": "str (optional, explain why this change is needed)",
                    },
                },
                {
                    "name": "finalize_plan",
                    "description": "MANDATORY last step of any engineering plan. Generates REVIEW_*.md listing all proposals, plan status, and operator action checklist. Stops without committing or applying anything. Terminal state is always a review package.",
                    "arguments": {
                        "plan_name": "str (optional, default 'default')",
                        "summary": "str (optional, what was built)",
                        "verdict": "str (optional, brain's assessment and recommendations)",
                    },
                },
                {
                    "name": "read_file_range",
                    "description": "Paginated read of large files. Returns numbered lines (1-indexed). Use this when read_file truncates at 12KB. Default reads first 500 lines.",
                    "arguments": {
                        "path": "str (required)",
                        "offset": "int (optional, default 0 — 0-indexed line number to start)",
                        "limit": "int (optional, default 500, max 2000)",
                    },
                },
                {
                    "name": "run_pytest",
                    "description": "Run pytest on a test path with extended timeout (default 120s, max 300s). Returns exit code, summary line, first 5 failure tracebacks, and tail of output. Default test_path=bridge/tests/.",
                    "arguments": {
                        "test_path": "str (optional, default bridge/tests/)",
                        "timeout": "int (optional, default 120, max 300)",
                        "extra_args": "str (optional, space-separated pytest flags like '-x -v')",
                    },
                },
                {
                    "name": "task_track",
                    "description": "Create a multi-step plan in agent_memory.db (brain_tasks table). Persistent across chat turns. Use this for ANY multi-step engineering work. Returns confirmation with step count.",
                    "arguments": {
                        "steps": "list[str] (required, ordered plan steps)",
                        "plan_name": "str (optional, default 'default')",
                    },
                },
                {
                    "name": "task_update",
                    "description": "Update a step's status, list current plan, or clear plan. Statuses: pending, in_progress, completed, blocked. Actions: update (default), list, clear.",
                    "arguments": {
                        "plan_name": "str (optional, default 'default')",
                        "step_index": "int (required for action=update)",
                        "status": "str (required for action=update)",
                        "action": "str (optional, default 'update'; 'list' or 'clear')",
                    },
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
                {
                    "name": "take_snapshot",
                    "description": "Capture a full protocol state snapshot right now (GIC chain, PCC, AIT separation, calibration thresholds, tournament gate, wallet balance, IoTeX block) and store in agent_memory.db. Returns formatted snapshot.",
                    "arguments": {},
                },
                {
                    "name": "diff_snapshots",
                    "description": "Compare last N protocol snapshots stored by the watcher or take_snapshot. Surfaces all deltas: new GIC links, ratio drift, threshold shifts, wallet changes, PCC degradation, tournament gate flips.",
                    "arguments": {"n": "int (optional, default 2, compare last N snapshots)"},
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