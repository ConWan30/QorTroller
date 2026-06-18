"""
QorTroller Daemon Tool Schemas & Governance Rules
==================================================

Single source of truth for all daemon governance:
  - PROPOSE_ONLY_PATHS: files the daemon can never directly write
  - FROZEN_PATTERNS: path-suffix matches for frozen primitives
  - TEST_DIRECTORIES: always read-only
  - Shell sandbox: sealed env + metacharacter ban + command whitelist
  - Rate-limiting: per-tool + cross-tool global budget, persisted to disk
  - Daemon identity: ED25519 signing; sign-fail BLOCKS the proposal
  - GovernanceHardStop: finalize_plan() raises this — no execution after

CRITICAL META-RULE (L1):
  This file itself is in its own FROZEN_PATTERNS. The daemon cannot
  modify the governance module. Any edit here must go through propose_edit()
  and operator review. Without this, all seven layers collapse simultaneously.

DEFAULT FOR UNLISTED PATHS (L1):
  An unknown path is treated as PROPOSE_ONLY, not as an error.
  Fail toward caution. Exception-handling is an attack surface.
"""

import hashlib
import json
import os
import re
import sqlite3
import time
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
#  HARD STOP — raised by finalize_plan() to terminate execution (L7)
# ═══════════════════════════════════════════════════════════════════════════════

class GovernanceHardStop(Exception):
    """
    Raised by finalize_plan() to end the daemon's execution path.

    L7 fix: this is NOT a return value the daemon can ignore.
    The daemon's process_message() loop must propagate this upward.
    No tool calls, no LLM calls, no file writes after this is raised.
    """
    def __init__(self, review_path: str, plan_name: str):
        self.review_path = review_path
        self.plan_name = plan_name
        super().__init__(
            f"GOVERNANCE HARD STOP — plan '{plan_name}' finalized. "
            f"Review at {review_path}. No further execution permitted."
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  GOVERNANCE MODE (L2)
# ═══════════════════════════════════════════════════════════════════════════════

class GovernanceMode(Enum):
    """
    Tool governance posture. Enum means daemon cannot invent new modes at runtime.
    Unknown mode → rejected (fail-closed).
    """
    AUTONOMOUS = "autonomous"    # New files only; never critical paths
    PROPOSE_ONLY = "propose_only"  # Generates diff; source never touched
    READ_ONLY = "read_only"      # No writes of any kind
    RESTRICTED = "restricted"    # Special constraints (shell sandbox, bridge POST gate)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROPOSE_ONLY PATHS (L1)
#
#  META-RULE: this file and the daemon's own source are in this set.
#  A daemon that can edit its own governance module or its own source
#  can rewrite its safety checks out of existence across sessions.
# ═══════════════════════════════════════════════════════════════════════════════

PROPOSE_ONLY_PATHS: frozenset = frozenset({
    # ── The governance module itself (meta-rule, L1) ──────────────────────
    "_daemon_tools_schema.py",
    # ── The daemon's own source (cross-cutting gap) ───────────────────────
    "qortroller_daemon.py",
    # ── Bridge startup / entry point ─────────────────────────────────────
    "bridge/vapi_bridge/main.py",
    # ── Core store (FROZEN surfaces live here) ────────────────────────────
    "bridge/vapi_bridge/store/_core.py",
    # ── Operator API (241 endpoints) ─────────────────────────────────────
    "bridge/vapi_bridge/operator_api.py",
    # ── Wallet / chain / signing ──────────────────────────────────────────
    "bridge/vapi_bridge/chain.py",
    # ── FROZEN-v1 chain primitives ────────────────────────────────────────
    "bridge/vapi_bridge/grind_chain.py",
    "bridge/vapi_bridge/watchdog_chain.py",
    "bridge/vapi_bridge/codec.py",
    "bridge/vapi_bridge/corpus_snapshot.py",
    "bridge/vapi_bridge/biometric_snapshot.py",
    "bridge/vapi_bridge/agent_commit.py",
    # ── Session pipeline (complex state machine) ──────────────────────────
    "bridge/vapi_bridge/session_adjudicator.py",
    "bridge/vapi_bridge/session_adjudicator_validator.py",
    # ── Invariant gate + allowlist ────────────────────────────────────────
    "scripts/vapi_invariant_gate.py",
    ".github/INVARIANTS_ALLOWLIST.json",
    # ── Credentials (never touch) ─────────────────────────────────────────
    ".env",
    "bridge/.env",
    # ── Contract deployments ──────────────────────────────────────────────
    "contracts/deployed-addresses.json",
    "contracts/hardhat.config.js",
})

# FROZEN_PATTERNS: path-suffix matches for frozen primitives.
# Both path AND name must be checked — a file named after a frozen primitive
# (e.g., fake_pipeline.py) is treated as frozen even if it's new.
FROZEN_PATTERNS: frozenset = frozenset({
    # The governance module itself (catches any path ending in this filename)
    "_daemon_tools_schema.py",
    # FROZEN-v1 replay primitives
    "replay_proof_pipeline/pipeline.py",
    "physical_data_attestation.py",
    "zkba_artifact.py",
    "consent_manifest.py",
    "vapi_swarm_operator.py",
})

# Test directories — split governance:
#   edit_file() on existing test → BLOCKED (tests are the verification rail; never edit)
#   write_file() creating new test → PROPOSE_ONLY (new test files need operator review)
#   read_file() on any test → always allowed
TEST_DIRECTORIES: frozenset = frozenset({
    "bridge/tests/",
    "sdk/tests/",
    "contracts/test/",
})

# bridge_post() approval gate (F-GOV-1):
# bridge_post() is RESTRICTED — it can trigger real chain ops via OPERATOR_API_KEY.
# Gate: caller must pass approved=True AND env BRIDGE_POST_GATE_ENABLED=1.
# Without both, the tool returns BLOCKED with operator instructions.
BRIDGE_POST_GATE_ENV = "BRIDGE_POST_GATE_ENABLED"

# Credential file patterns (regex)
CREDENTIAL_PATTERNS: tuple = (
    r"\.env($|\..*)",
    r".*_private\.key$",
    r".*_secret\..+$",
    r".*keystore.*",
    r".*wallet.*\.json$",
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SHELL SANDBOX (L3)
#
#  Metacharacter ban + whitelist + sealed execution environment.
#  env var injection (e.g., PYTHONPATH=/attacker) bypasses the metacharacter
#  check entirely — the daemon gets a sealed env, not just a filtered command.
# ═══════════════════════════════════════════════════════════════════════════════

# Shell metacharacters that enable injection — BANNED
BANNED_METACHARACTERS: frozenset = frozenset(
    {'&', ';', '|', '>', '<', '$', '`', '(', ')', '[', ']', '{', '}', '\\', '!'}
)

# Whitelisted command prefixes — only these may execute
SAFE_SHELL_PREFIXES: frozenset = frozenset({
    "git log",
    "git status",
    "git diff",
    "git show",
    "git branch",
    "git tag",
    "python -m pytest",
    "npm test",
    "cargo test",
    "python scripts/",
    "pwd",
    "echo",
    # NOTE: file-read commands (type, dir, find, grep, ls, cat) are DELIBERATELY
    # excluded. They accept arbitrary path arguments that the metacharacter ban
    # does not constrain (/ : . are not banned), enabling exfiltration of
    # ~/.vapi/daemon_identity.key and bridge/.env via e.g. "type C:/.../key".
    # File inspection MUST go through the governed read_file / read_file_range /
    # search_code tools, which the daemon controls and cannot be pointed at
    # secret paths. (Security review SEC-1, 2026-06-17)
})

# Sealed execution environment — no arbitrary env injection
# PATH is locked to system defaults; PYTHONPATH is controlled.
def get_sealed_env() -> dict:
    """
    Return a sealed environment dict for subprocess execution.
    Strips all inherited env vars except a controlled allowlist.
    Daemon cannot inject PYTHONPATH, LD_PRELOAD, or other attack vectors.
    """
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
        "PYTHONPATH": "",  # No external path injection
        "HOME": os.environ.get("HOME", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows
        "USERPROFILE": os.environ.get("USERPROFILE", ""),  # Windows
    }


def validate_shell_command(command: str) -> Optional[str]:
    """
    Validate shell command against sandbox rules.
    Returns error message if violated, None if OK.
    """
    if not command or not command.strip():
        return "Empty command not allowed"

    # Metacharacter ban
    for char in BANNED_METACHARACTERS:
        if char in command:
            return (
                f"Shell metacharacter '{char}' not allowed. "
                f"Commands must be literal strings with no composition, "
                f"substitution, or redirection."
            )

    # Whitelist check
    if not any(command.startswith(prefix) for prefix in SAFE_SHELL_PREFIXES):
        return (
            f"Command not whitelisted. "
            f"Allowed prefixes: {', '.join(sorted(SAFE_SHELL_PREFIXES))}"
        )

    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PATH GOVERNANCE HELPERS (L1)
# ═══════════════════════════════════════════════════════════════════════════════

def classify_path(path: str) -> GovernanceMode:
    """
    Classify a file path by governance mode.

    DEFAULT FOR UNLISTED PATHS: PROPOSE_ONLY (L1 fix).
    Fail toward caution. Unknown path is treated as critical,
    not as an error the loop can catch and retry around.

    Test directories (F-GOV-2 ruling):
      READ_ONLY  → used by edit_file() to BLOCK edits to existing tests
      PROPOSE_ONLY → used by write_file() for new test file creation (needs review)
    These are distinguished by the caller, not by classify_path() alone.
    classify_path() returns READ_ONLY for test dirs; callers that handle
    new-file creation check is_new_test_file_path() separately.
    """
    # Normalize to forward slashes
    p = path.replace("\\", "/").lstrip("/")

    # Explicit PROPOSE_ONLY set (exact match)
    if p in PROPOSE_ONLY_PATHS:
        return GovernanceMode.PROPOSE_ONLY

    # Frozen pattern suffix match (catches renamed primitives)
    if any(p.endswith(pat) for pat in FROZEN_PATTERNS):
        return GovernanceMode.PROPOSE_ONLY

    # Test directory prefix → READ_ONLY signals "never edit existing tests"
    if any(p.startswith(td) for td in TEST_DIRECTORIES):
        return GovernanceMode.READ_ONLY

    # Credential pattern
    for pattern in CREDENTIAL_PATTERNS:
        if re.match(pattern, os.path.basename(p)):
            return GovernanceMode.PROPOSE_ONLY

    # DEFAULT: unlisted path → PROPOSE_ONLY (not error, not AUTONOMOUS)
    return GovernanceMode.PROPOSE_ONLY


def is_new_test_file_path(path: str) -> bool:
    """
    Returns True if path is under a test directory.
    Used by write_file() to route new test file creation through PROPOSE_ONLY.

    F-GOV-2 ruling: new test files are PROPOSE_ONLY (not autonomous).
    Tests are part of the verification surface even when new.
    edit_file() on existing tests → BLOCKED (READ_ONLY via classify_path).
    write_file() creating new tests → PROPOSE_ONLY (this function).
    """
    p = path.replace("\\", "/").lstrip("/")
    return any(p.startswith(td) for td in TEST_DIRECTORIES)


def is_read_blocked(path: str) -> Optional[str]:
    """
    Block reads of secret files even through the governed read tools.

    The shell read commands were removed (SEC-1), so read_file / read_file_range /
    search_code are now the only file-inspection path. They must refuse to return
    the daemon's identity key, .env files, wallet keys, and PEM material — otherwise
    the LLM can exfiltrate them through the very tools meant to be safe.

    Returns a reason string if the read is blocked, None if allowed.
    """
    p = path.replace("\\", "/").lstrip("/")
    base = os.path.basename(p)

    # Credential filename patterns
    for pattern in CREDENTIAL_PATTERNS:
        if re.match(pattern, base):
            return f"Read blocked: '{p}' matches a credential pattern"

    # Explicit secret paths
    SECRET_SUFFIXES = (".env", ".key", ".pem")
    if base.endswith(SECRET_SUFFIXES) or base == ".env":
        return f"Read blocked: '{p}' is a secret file"
    if ".env" in base:  # .env.local, .env.production
        return f"Read blocked: '{p}' is an environment file"
    # The daemon's own identity / governance store
    if "daemon_identity" in base or base.endswith(".db") and "rate_limiter" in base:
        return f"Read blocked: '{p}' is daemon identity/governance state"

    return None


def is_autonomous_write_allowed(path: str) -> bool:
    """
    Returns True ONLY if the daemon may directly write to this path.
    The bar is high: only files that don't match any frozen/critical/test pattern.
    """
    mode = classify_path(path)
    if mode != GovernanceMode.PROPOSE_ONLY and mode != GovernanceMode.READ_ONLY:
        return True
    # Even if mode were AUTONOMOUS, test directories are never autonomous
    if is_new_test_file_path(path):
        return False
    return False


def check_bridge_post_gate(args: dict) -> Optional[str]:
    """
    F-GOV-1: bridge_post() approval gate.

    bridge_post() can trigger real chain ops via OPERATOR_API_KEY.
    Two conditions BOTH required to execute:
      1. args contains approved=True (explicit per-call flag)
      2. Env var BRIDGE_POST_GATE_ENABLED=1 is set by operator

    Returns error string if blocked, None if approved.
    """
    import os as _os
    approved_arg = args.get("approved", False)
    gate_env = _os.environ.get(BRIDGE_POST_GATE_ENV, "").strip()

    if not approved_arg:
        return (
            "OPERATOR_HOLD: bridge_post() requires explicit approval. "
            "Pass approved=True in the call AND set env var "
            f"{BRIDGE_POST_GATE_ENV}=1 to enable. "
            "Rationale: bridge_post() can trigger real chain operations "
            "via OPERATOR_API_KEY. Manual approval prevents autonomous "
            "chain mutations."
        )

    if gate_env != "1":
        return (
            f"OPERATOR_HOLD: bridge_post() is gated by env {BRIDGE_POST_GATE_ENV}. "
            f"Set {BRIDGE_POST_GATE_ENV}=1 in your shell before running the daemon "
            "to enable POST operations. This env var must be set deliberately — "
            "it is not in bridge/.env."
        )

    return None  # Both conditions met — POST is approved


# ═══════════════════════════════════════════════════════════════════════════════
#  RATE LIMITER (L5) — persisted to disk, global cross-tool budget
#
#  Fixes:
#  1. State persists to SQLite across restarts (not lost on process exit)
#  2. Global cross-tool budget prevents tool-rotation attacks
#  3. Per-tool budget as before
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimitBudget:
    """Rate limit thresholds."""
    # Per-tool budgets
    PER_MINUTE = 10
    PER_HOUR = 100
    PER_DAY = 1000
    # Global cross-tool budgets (all tools combined)
    GLOBAL_PER_MINUTE = 30
    GLOBAL_PER_HOUR = 500
    GLOBAL_PER_DAY = 5000
    # Exponential backoff sequence (milliseconds)
    BACKOFF_SEQUENCE = [60_000, 600_000, 3_600_000, 86_400_000]  # 1m, 10m, 1h, 24h


class RateLimiter:
    """
    Per-tool + global cross-tool rate limiter with disk persistence.

    State is stored in SQLite so restart does not reset budget.
    Uses atomic writes to prevent corruption on crash.
    """

    GLOBAL_KEY = "__global__"

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS rate_calls (
                    tool_name   TEXT NOT NULL,
                    called_at   REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rate_calls
                    ON rate_calls(tool_name, called_at);
                CREATE TABLE IF NOT EXISTS rate_errors (
                    tool_name       TEXT PRIMARY KEY,
                    error_count     INTEGER NOT NULL DEFAULT 0,
                    backoff_until   REAL NOT NULL DEFAULT 0
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _count_since(self, conn: sqlite3.Connection, tool_name: str, cutoff: float) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM rate_calls WHERE tool_name=? AND called_at>?",
            (tool_name, cutoff)
        ).fetchone()
        return row[0] if row else 0

    def can_call(self, tool_name: str) -> tuple:
        """Check if tool can be called. Returns (allowed: bool, reason: str|None)."""
        now = time.time()
        conn = self._conn()
        try:
            # Per-tool backoff check
            row = conn.execute(
                "SELECT backoff_until FROM rate_errors WHERE tool_name=?",
                (tool_name,)
            ).fetchone()
            if row and row[0] > now:
                remaining = int(row[0] - now)
                return (False, f"Tool '{tool_name}' on backoff for {remaining}s")

            minute_ago = now - 60
            hour_ago = now - 3600
            day_ago = now - 86400

            # Per-tool limits
            if self._count_since(conn, tool_name, minute_ago) >= RateLimitBudget.PER_MINUTE:
                return (False, f"{RateLimitBudget.PER_MINUTE} calls/min exceeded for '{tool_name}'")
            if self._count_since(conn, tool_name, hour_ago) >= RateLimitBudget.PER_HOUR:
                return (False, f"{RateLimitBudget.PER_HOUR} calls/hr exceeded for '{tool_name}'")
            if self._count_since(conn, tool_name, day_ago) >= RateLimitBudget.PER_DAY:
                return (False, f"{RateLimitBudget.PER_DAY} calls/day exceeded for '{tool_name}'")

            # Global cross-tool limits
            g = self.GLOBAL_KEY
            if self._count_since(conn, g, minute_ago) >= RateLimitBudget.GLOBAL_PER_MINUTE:
                return (False, f"Global {RateLimitBudget.GLOBAL_PER_MINUTE} calls/min exceeded")
            if self._count_since(conn, g, hour_ago) >= RateLimitBudget.GLOBAL_PER_HOUR:
                return (False, f"Global {RateLimitBudget.GLOBAL_PER_HOUR} calls/hr exceeded")
            if self._count_since(conn, g, day_ago) >= RateLimitBudget.GLOBAL_PER_DAY:
                return (False, f"Global {RateLimitBudget.GLOBAL_PER_DAY} calls/day exceeded")

            return (True, None)
        finally:
            conn.close()

    def record_call(self, tool_name: str):
        """Record a successful call (per-tool + global)."""
        now = time.time()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO rate_calls (tool_name, called_at) VALUES (?, ?)",
                (tool_name, now)
            )
            conn.execute(
                "INSERT INTO rate_calls (tool_name, called_at) VALUES (?, ?)",
                (self.GLOBAL_KEY, now)
            )
            conn.execute(
                "INSERT OR REPLACE INTO rate_errors (tool_name, error_count, backoff_until)"
                " VALUES (?, 0, 0)",
                (tool_name,)
            )
            conn.commit()
        finally:
            conn.close()

    def record_error(self, tool_name: str):
        """Record a tool error, apply exponential backoff, persist to disk."""
        now = time.time()
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT error_count FROM rate_errors WHERE tool_name=?",
                (tool_name,)
            ).fetchone()
            error_count = (row[0] + 1) if row else 1
            idx = min(error_count - 1, len(RateLimitBudget.BACKOFF_SEQUENCE) - 1)
            backoff_until = now + (RateLimitBudget.BACKOFF_SEQUENCE[idx] / 1000.0)
            conn.execute(
                "INSERT OR REPLACE INTO rate_errors (tool_name, error_count, backoff_until)"
                " VALUES (?, ?, ?)",
                (tool_name, error_count, backoff_until)
            )
            conn.commit()
        finally:
            conn.close()

    def prune_old_records(self, days: int = 2):
        """Prune call records older than N days (maintenance)."""
        cutoff = time.time() - (days * 86400)
        conn = self._conn()
        try:
            conn.execute("DELETE FROM rate_calls WHERE called_at<?", (cutoff,))
            conn.commit()
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  DAEMON IDENTITY (L6) — ED25519 signing; sign-fail BLOCKS the proposal
#
#  Fixes:
#  1. Sign-fail → BLOCKED (not marked-unsigned and allowed through)
#  2. Key lives outside daemon's writable scope (caller must provide path)
#  3. Identity is verifiable but not secret (public key embedded in proposal)
# ═══════════════════════════════════════════════════════════════════════════════

class SigningError(Exception):
    """Raised when proposal signing fails — blocks the proposal."""


class DaemonIdentity:
    """
    Cryptographic identity for this daemon instance.

    Key discipline:
    - Private key lives at key_path (must be OUTSIDE the daemon's writable scope)
    - If key_path is inside PROPOSE_ONLY_PATHS, the key is protected
    - Sign-fail raises SigningError → proposal is BLOCKED, not accepted unsigned
    - Public key is embedded in every proposal for traceability

    Not a security measure: keys are not secret.
    Purpose: integrity audit trail — which daemon generated which artifact.
    """

    def __init__(self, key_path: str):
        self._key_path = key_path
        self._public_key: Optional[str] = None
        self._private_key_bytes: Optional[bytes] = None
        self._load_or_create_key()

    def _load_or_create_key(self):
        """Load existing keypair or generate new one. Raises SigningError on failure."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
            from cryptography.hazmat.primitives.serialization import (
                Encoding, NoEncryption, PrivateFormat, PublicFormat,
            )
        except ImportError:
            raise SigningError(
                "cryptography package not installed. "
                "Run: pip install cryptography. "
                "Daemon cannot sign proposals without it."
            )

        key_file = Path(self._key_path)
        if key_file.exists():
            try:
                raw = key_file.read_bytes()
                private_key = Ed25519PrivateKey.from_private_bytes(raw)
            except Exception as e:
                raise SigningError(f"Cannot load keypair from {self._key_path}: {e}")
        else:
            try:
                key_file.parent.mkdir(parents=True, exist_ok=True)
                private_key = Ed25519PrivateKey.generate()
                key_file.write_bytes(
                    private_key.private_bytes(
                        encoding=Encoding.Raw,
                        format=PrivateFormat.Raw,
                        encryption_algorithm=NoEncryption(),
                    )
                )
            except Exception as e:
                raise SigningError(f"Cannot create keypair at {self._key_path}: {e}")

        self._private_key_bytes = private_key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )
        self._public_key = private_key.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        ).hex()

    @property
    def public_key(self) -> str:
        """Public key hex — embedded in every proposal."""
        if not self._public_key:
            raise SigningError("Daemon identity not initialized")
        return self._public_key

    def sign(self, content: bytes) -> str:
        """
        Sign content and return signature hex.
        Raises SigningError on any failure — callers must treat this as BLOCKED.
        """
        if not self._private_key_bytes:
            raise SigningError("Private key not loaded — proposal BLOCKED")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            private_key = Ed25519PrivateKey.from_private_bytes(self._private_key_bytes)
            return private_key.sign(content).hex()
        except Exception as e:
            raise SigningError(f"Signing failed — proposal BLOCKED: {e}")

    def sign_file(self, file_path: str) -> dict:
        """
        Sign a proposal file. Returns signature metadata dict.
        Raises SigningError if signing fails (caller must NOT write the proposal).
        """
        try:
            content = Path(file_path).read_bytes()
        except Exception as e:
            raise SigningError(f"Cannot read proposal for signing: {e}")

        content_hash = hashlib.sha256(content).hexdigest()
        signature = self.sign(content)

        return {
            "daemon_public_key": self.public_key,
            "proposal_sha256": content_hash,
            "signature_ed25519": signature,
            "algorithm": "ed25519",
            "key_path": self._key_path,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  APPEND-ONLY GOVERNANCE LOG (cross-cutting)
#
#  Logs are outside the daemon's writable scope by design:
#  the log file path must be outside REPO_ROOT or in PROPOSE_ONLY territory.
#  GovernanceLog opens append-only — no seek, no truncate, no overwrite.
# ═══════════════════════════════════════════════════════════════════════════════

class GovernanceLog:
    """
    Append-only audit log for governance events.

    Every BLOCKED, PROPOSED, HARD_STOP, RATE_LIMITED event is logged here.
    The daemon can only append — it cannot read back or modify prior entries.
    Log path must be outside the daemon's writable scope.
    """

    def __init__(self, log_path: str):
        self._log_path = log_path
        # Ensure parent directory exists
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    def _write(self, level: str, event: str, detail: dict):
        """Append a governance event. Atomic per-line JSON."""
        entry = json.dumps({
            "ts": time.time(),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level,
            "event": event,
            **detail,
        })
        # Open in append mode — no seek, no truncate via this path.
        # LIMITATION: Python "a" mode does not use OS-level O_APPEND, so a
        # compromised process holding the fd could still seek+truncate.
        # Follow-up: replace with os.open(path, os.O_WRONLY|os.O_CREAT|os.O_APPEND)
        # or route to a separate log process for true append-only enforcement.
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    def blocked(self, tool: str, path: str, rule: str):
        self._write("BLOCKED", "write_blocked", {"tool": tool, "path": path, "rule": rule})

    def proposed(self, path: str, diff_path: str, daemon_public_key: str):
        self._write("PROPOSED", "proposal_written", {
            "path": path, "diff_path": diff_path, "signer": daemon_public_key,
        })

    def sign_failed(self, path: str, error: str):
        self._write("BLOCKED", "sign_failed_proposal_blocked", {"path": path, "error": error})

    def rate_limited(self, tool: str, reason: str):
        self._write("RATE_LIMITED", "tool_rate_limited", {"tool": tool, "reason": reason})

    def hard_stop(self, plan_name: str, review_path: str):
        self._write("HARD_STOP", "finalize_plan_terminal", {
            "plan_name": plan_name, "review_path": review_path,
        })

    def shell_blocked(self, command: str, reason: str):
        self._write("BLOCKED", "shell_command_blocked", {"command": command[:200], "reason": reason})

    def agent_commit(self, commitment_hex: str, plan_name: str, daemon_public_key: str):
        self._write("AGENT_COMMIT", "finalize_plan_committed", {
            "commitment_hex": commitment_hex,
            "plan_name": plan_name,
            "daemon_public_key": daemon_public_key,
        })


# ═══════════════════════════════════════════════════════════════════════════════
#  DAEMON COMMIT CHAIN (F-AGC-4) — SQLite-persisted AGENT-COMMIT v1 chain
#
#  prev_commit_hash MUST survive restarts. Memory-only = false genesis on every
#  restart = chain fragments into disconnected shards. Same governance SQLite DB
#  as the rate limiter; same WAL write discipline.
#
#  D-DAEMON-1 Path A provisional-identity migration note (F-AGC-2 fix):
#  This chain uses provisional agentId = SHA-256(ed25519_pubkey). When
#  D-DAEMON-1 resolves and the daemon receives an on-chain canonical agentId,
#  a NEW chain starts with that agentId. A junction entry in the new chain
#  records the last provisional chain commitment as prev_commit_hash. The
#  provisional chain is NOT invalidated or retroactively modified — it retains
#  its own verifiable history. "Genesis re-anchored" is WRONG and would corrupt
#  every subsequent link. Document this as "chain junction at D-DAEMON-1
#  resolution" everywhere.
# ═══════════════════════════════════════════════════════════════════════════════

class DaemonCommitChain:
    """SQLite-persisted AGENT-COMMIT v1 chain for daemon finalize_plan() outputs."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_table()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_table(self):
        conn = self._conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS daemon_commit_chain (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    commitment_hex  TEXT NOT NULL UNIQUE,
                    ts_ns           INTEGER NOT NULL,
                    plan_name       TEXT NOT NULL,
                    review_path     TEXT NOT NULL,
                    created_at      TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def get_last_commitment(self) -> bytes:
        """
        Return last commitment as 32 bytes, or 32 zero bytes for genesis.
        Called before each finalize_plan() to get prev_commit_hash.
        """
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT commitment_hex FROM daemon_commit_chain ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return bytes.fromhex(row[0]) if row else b"\x00" * 32
        finally:
            conn.close()

    def record_commitment(
        self, commitment_hex: str, ts_ns: int, plan_name: str, review_path: str
    ):
        """Persist new commitment. Atomic write; WAL journal prevents corruption."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO daemon_commit_chain "
                "(commitment_hex, ts_ns, plan_name, review_path, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (commitment_hex, ts_ns, plan_name, review_path,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            )
            conn.commit()
        finally:
            conn.close()

    def chain_length(self) -> int:
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) FROM daemon_commit_chain").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  STARTUP SELF-TEST — run before any tool invocation
#
#  A misconfigured governance module fails loudly on boot, not silently at
#  the moment of first violation. Ten lines, high leverage.
#  Call this from _get_brain() before constructing QorTrollerBrain.
# ═══════════════════════════════════════════════════════════════════════════════

def governance_self_test():
    """
    Assert that the governance module's own rules are internally consistent.
    Raises AssertionError with a descriptive message if any invariant is violated.
    Called at daemon startup — failure here aborts boot before any tool runs.
    """
    failures = []

    # L1 meta-rule: governance module protects itself
    if "_daemon_tools_schema.py" not in PROPOSE_ONLY_PATHS:
        failures.append("CRITICAL: _daemon_tools_schema.py missing from PROPOSE_ONLY_PATHS — L1 meta-rule violated")
    if "_daemon_tools_schema.py" not in FROZEN_PATTERNS:
        failures.append("CRITICAL: _daemon_tools_schema.py missing from FROZEN_PATTERNS — L1 meta-rule violated")

    # L1: daemon source is protected
    if "qortroller_daemon.py" not in PROPOSE_ONLY_PATHS:
        failures.append("CRITICAL: qortroller_daemon.py missing from PROPOSE_ONLY_PATHS — daemon can edit itself")

    # L1: critical paths classify correctly
    critical_checks = {
        "bridge/vapi_bridge/main.py": GovernanceMode.PROPOSE_ONLY,
        "bridge/vapi_bridge/store/_core.py": GovernanceMode.PROPOSE_ONLY,
        "scripts/vapi_invariant_gate.py": GovernanceMode.PROPOSE_ONLY,
        "_daemon_tools_schema.py": GovernanceMode.PROPOSE_ONLY,
        "qortroller_daemon.py": GovernanceMode.PROPOSE_ONLY,
        ".env": GovernanceMode.PROPOSE_ONLY,
        "bridge/.env": GovernanceMode.PROPOSE_ONLY,
    }
    for path, expected in critical_checks.items():
        actual = classify_path(path)
        if actual != expected:
            failures.append(
                f"classify_path('{path}') returned {actual.value!r}, expected {expected.value!r}"
            )

    # L1: test directories classify as READ_ONLY
    for td in TEST_DIRECTORIES:
        actual = classify_path(td + "test_something.py")
        if actual != GovernanceMode.READ_ONLY:
            failures.append(
                f"classify_path('{td}test_something.py') returned {actual.value!r}, expected 'read_only'"
            )

    # L1: unlisted path defaults to PROPOSE_ONLY (not error, not autonomous)
    unlisted = classify_path("bridge/vapi_bridge/some_brand_new_module.py")
    if unlisted != GovernanceMode.PROPOSE_ONLY:
        failures.append(
            f"Unlisted path classified as {unlisted.value!r} — must default to propose_only"
        )

    # L3: metacharacter ban is active
    for char in {'&', ';', '|', '>', '<', '$', '`'}:
        err = validate_shell_command(f"git log {char} rm -rf .")
        if err is None:
            failures.append(f"validate_shell_command did not catch metacharacter '{char}'")

    # L3: sealed env has no PYTHONPATH injection surface
    sealed = get_sealed_env()
    if sealed.get("PYTHONPATH") != "":
        failures.append(f"get_sealed_env() returned non-empty PYTHONPATH: {sealed.get('PYTHONPATH')!r}")

    # F-GOV-1: bridge_post() gate exists and blocks without approval
    gate_err = check_bridge_post_gate({})
    if gate_err is None:
        failures.append("check_bridge_post_gate({}) returned None — gate missing, unapproved POST would execute")
    gate_err_approved_only = check_bridge_post_gate({"approved": True})
    if gate_err_approved_only is None:
        failures.append(
            "check_bridge_post_gate(approved=True) returned None without env var — "
            "both conditions required, env var alone should not suffice when arg is missing"
        )

    # F-GOV-2: test directory paths classify as READ_ONLY (edit block)
    for td in TEST_DIRECTORIES:
        actual = classify_path(td + "test_something.py")
        if actual != GovernanceMode.READ_ONLY:
            failures.append(
                f"classify_path('{td}test_something.py') = {actual.value!r}, expected 'read_only'"
            )
    # F-GOV-2: is_new_test_file_path() catches new file creation under tests/
    for td in TEST_DIRECTORIES:
        if not is_new_test_file_path(td + "test_new_module.py"):
            failures.append(f"is_new_test_file_path('{td}test_new_module.py') returned False")
    # F-GOV-2: is_autonomous_write_allowed() returns False for test paths
    for td in TEST_DIRECTORIES:
        if is_autonomous_write_allowed(td + "test_new_module.py"):
            failures.append(f"is_autonomous_write_allowed('{td}test_new_module.py') returned True")

    # L7: GovernanceHardStop is an Exception subclass (not a return value)
    if not issubclass(GovernanceHardStop, Exception):
        failures.append("GovernanceHardStop must be an Exception subclass for hard-stop semantics")

    # L6: SigningError is an Exception subclass
    if not issubclass(SigningError, Exception):
        failures.append("SigningError must be an Exception subclass")

    if failures:
        msg = "\n".join(f"  - {f}" for f in failures)
        raise AssertionError(
            f"GOVERNANCE SELF-TEST FAILED — daemon boot aborted.\n"
            f"{len(failures)} invariant(s) violated:\n{msg}\n\n"
            f"Fix _daemon_tools_schema.py before restarting the daemon."
        )

    # Count: critical_checks + test READ_ONLY + test is_new + test no_autonomous + metachar + sealed + hard_stop + signing_error + bridge_post_gate (2)
    n = len(critical_checks) + len(TEST_DIRECTORIES) * 3 + 7 + 2
    return f"governance_self_test: {n} checks passed"


# ═══════════════════════════════════════════════════════════════════════════════
#  TIER 1 — FABRICATION DETECTOR (verify_artifact)
#
#  The daemon hallucinated "READY" with a file body it never wrote. That is a
#  CLASS of failure (LLM hallucinated-completion), not a one-time bug. This
#  primitive makes the daemon prove its outputs the way PV-CI proves invariants.
# ═══════════════════════════════════════════════════════════════════════════════

def verify_artifact(path: str, expected_shape: dict) -> dict:
    """
    Verify a produced artifact matches its claimed shape. Lightweight, deterministic.

    expected_shape keys (all optional):
      exists: bool, min_lines/max_lines: int, min_bytes/max_bytes: int,
      python_valid: bool, must_contain: list[str], must_not_contain: list[str],
      class_name: str (implies python_valid).

    Returns {"ok": bool, "checks": [...], "failures": [...]}.
    """
    import ast as _ast
    checks, failures = [], []

    exists = os.path.isfile(path)
    want_exists = expected_shape.get("exists", True)
    checks.append(f"exists={exists} (want {want_exists})")
    if want_exists and not exists:
        return {"ok": False, "checks": checks, "failures": [f"artifact missing: {path}"]}
    if not want_exists and exists:
        return {"ok": False, "checks": checks, "failures": [f"artifact should not exist: {path}"]}
    if not exists:
        return {"ok": True, "checks": checks, "failures": failures}

    try:
        content = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return {"ok": False, "checks": checks, "failures": [f"read error: {e}"]}

    nlines = content.count("\n") + 1
    nbytes = len(content.encode("utf-8"))
    if "min_lines" in expected_shape:
        checks.append(f"lines={nlines}>={expected_shape['min_lines']}")
        if nlines < expected_shape["min_lines"]:
            failures.append(f"too few lines: {nlines} < {expected_shape['min_lines']}")
    if "max_lines" in expected_shape:
        checks.append(f"lines={nlines}<={expected_shape['max_lines']}")
        if nlines > expected_shape["max_lines"]:
            failures.append(f"too many lines: {nlines} > {expected_shape['max_lines']}")
    if "min_bytes" in expected_shape and nbytes < expected_shape["min_bytes"]:
        failures.append(f"too small: {nbytes}B < {expected_shape['min_bytes']}B")
    if "max_bytes" in expected_shape and nbytes > expected_shape["max_bytes"]:
        failures.append(f"too large: {nbytes}B > {expected_shape['max_bytes']}B")

    want_class = expected_shape.get("class_name")
    want_py = expected_shape.get("python_valid", bool(want_class))
    if want_py:
        try:
            tree = _ast.parse(content)
            checks.append("python_valid=True")
            if want_class:
                classes = [nd.name for nd in tree.body if isinstance(nd, _ast.ClassDef)]
                checks.append(f"classes={classes}")
                if want_class not in classes:
                    failures.append(f"class '{want_class}' not defined (found {classes})")
        except SyntaxError as e:
            failures.append(f"not valid Python: {e}")

    for s in expected_shape.get("must_contain", []):
        if s not in content:
            failures.append(f"missing required substring: {s!r}")
    for s in expected_shape.get("must_not_contain", []):
        if s in content:
            failures.append(f"contains forbidden substring: {s!r}")

    return {"ok": not failures, "checks": checks, "failures": failures}


# ═══════════════════════════════════════════════════════════════════════════════
#  TIER 1 — METHODOLOGY REGISTRY (lessons compound across sessions)
# ═══════════════════════════════════════════════════════════════════════════════

_SEED_METHODOLOGY = {
    "VERBATIM_RELOCATION": {
        "anti_pattern": "Ask the LLM to re-emit large code blocks verbatim in a write_file/tool_call. Causes 524 timeouts upstream and risks transcription drift; the LLM may then hallucinate completion.",
        "correct_pattern": "LLM proposes the structural CUT as a removal diff (small response). A deterministic tool (extract_with_diff) reconstructs the moved code from the diff's '-' lines. LLM never relocates verbatim.",
        "agent_commit": "ec94cbddbca457b993f4f9860cf252bfbf5b4fb353e6f0deafcb89e8c85ca057",
        "discovered": "2026-06-18 marketplace extraction",
    },
    "LARGE_FILE_WRITE": {
        "anti_pattern": "write_file with thousands of lines in one LLM turn — exceeds upstream generation timeout.",
        "correct_pattern": "Reconstruct large new-file bodies deterministically from an authoritative source; write_file on propose-only paths emits a .proposed artifact rather than discarding content.",
        "agent_commit": "ec94cbddbca457b993f4f9860cf252bfbf5b4fb353e6f0deafcb89e8c85ca057",
        "discovered": "2026-06-18",
    },
    "HALLUCINATED_COMPLETION": {
        "anti_pattern": "Declare a plan READY / claim a file was written without verifying the artifact exists with the expected shape.",
        "correct_pattern": "Call verify_artifact(path, expected_shape) after every output-producing tool, before finalize_plan. Fail closed if missing or malformed.",
        "agent_commit": "ec94cbddbca457b993f4f9860cf252bfbf5b4fb353e6f0deafcb89e8c85ca057",
        "discovered": "2026-06-18",
    },
    "FROZEN_SURFACE_TOUCH": {
        "anti_pattern": "edit_file / write_file directly against main.py, store/_core.py, chain.py, or any PROPOSE_ONLY path.",
        "correct_pattern": "Use propose_edit (existing files) or the .proposed new-file path (new files). Operator applies via git apply.",
        "agent_commit": "05e237c6798519626ba011f2bd0fbe527621056d836bd6d11d889a89a55274f3",
        "discovered": "2026-06-18 store assessment",
    },
    "MIXIN_MISSING_IMPORTS": {
        "anti_pattern": "Extract methods into a mixin module without carrying the source module's top-level imports. Methods that used module-globals (time, json, hashlib...) NameError at runtime — and import-only integration tests miss it because the error only fires when the method executes.",
        "correct_pattern": "build_mixin_module auto-detects which of _core.py's imports the moved block references (detect_needed_imports) and injects them. Integration test must EXECUTE a method (run the domain's pytest), not just import the class.",
        "agent_commit": "(consent extraction 2026-06-18)",
        "discovered": "2026-06-18 consent extraction — test_phase237_consent caught NameError 'time'",
    },
}


class MethodologyRegistry:
    """JSON-backed registry of daemon methodology, keyed by failure class."""

    def __init__(self, path: str):
        self._path = path
        if not os.path.isfile(path):
            self._write(_SEED_METHODOLOGY)

    def _write(self, data: dict):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def all(self) -> dict:
        try:
            return json.load(open(self._path, encoding="utf-8"))
        except Exception:
            return dict(_SEED_METHODOLOGY)

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

    def add(self, failure_class: str, anti_pattern: str, correct_pattern: str,
            agent_commit: str = "", discovered: str = "") -> bool:
        data = self.all()
        data[failure_class] = {
            "anti_pattern": anti_pattern, "correct_pattern": correct_pattern,
            "agent_commit": agent_commit,
            "discovered": discovered or time.strftime("%Y-%m-%d", time.gmtime()),
        }
        self._write(data)
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  TIER 1 — DIFF ORACLE (reconstruct moved code from a removal diff; no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

def reconstruct_from_removal_diff(diff_text: str) -> list:
    """Return the exact removed lines (the '-' lines, sans marker) from a unified diff."""
    removed = []
    for line in diff_text.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
    while removed and not removed[0].strip():
        removed.pop(0)
    while removed and not removed[-1].strip():
        removed.pop()
    return removed


def detect_needed_imports(method_block: str, source_module_text: str) -> list:
    """
    Determine which of source_module's top-level imports the moved method block
    actually references. Moved methods lose the source module's import scope, so
    these must be carried into the mixin (the MIXIN_MISSING_IMPORTS lesson).
    Returns a list of import-statement strings.
    """
    import ast as _ast
    # Map: name -> import statement, from the source module's top-level imports
    src_imports = {}
    try:
        for node in _ast.parse(source_module_text).body:
            if isinstance(node, _ast.Import):
                for a in node.names:
                    nm = a.asname or a.name.split(".")[0]
                    src_imports[nm] = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            elif isinstance(node, _ast.ImportFrom):
                mod = node.module or ""
                for a in node.names:
                    nm = a.asname or a.name
                    src_imports[nm] = f"from {mod} import {a.name}" + (f" as {a.asname}" if a.asname else "")
    except SyntaxError:
        return []
    # Names referenced in the block (wrapped in a throwaway class to parse)
    try:
        btree = _ast.parse("class _X:\n" + method_block)
    except SyntaxError:
        try:
            btree = _ast.parse(method_block)
        except SyntaxError:
            return []
    used, defined = set(), set()
    for n in _ast.walk(btree):
        if isinstance(n, _ast.Name):
            (defined if isinstance(n.ctx, _ast.Store) else used).add(n.id)
        elif isinstance(n, _ast.Attribute) and isinstance(n.value, _ast.Name):
            used.add(n.value.id)
        if isinstance(n, _ast.FunctionDef):
            defined.add(n.name)
            for a in n.args.args:
                defined.add(a.arg)
            if n.args.vararg: defined.add(n.args.vararg.arg)
            if n.args.kwarg: defined.add(n.args.kwarg.arg)
    needed = sorted({src_imports[u] for u in used if u in src_imports and u not in defined})
    return needed


def build_mixin_module(class_name: str, removed_lines: list, docstring: str = "",
                       source_module_text: str = "") -> str:
    """Wrap removed (4-space-indented) Store methods as a standalone Mixin module.

    If source_module_text is provided, auto-detects and injects the top-level
    imports the moved methods reference (MIXIN_MISSING_IMPORTS lesson — moved
    methods lose the source module's import scope and NameError at runtime).
    """
    ds = docstring or f"{class_name} — D-DECON-2 domain extraction (diff-oracle reconstructed)."
    body = "\n".join(removed_lines)
    imports = detect_needed_imports(body, source_module_text) if source_module_text else []
    import_block = ("\n" + "\n".join(imports) + "\n") if imports else ""
    header = (
        f'"""{ds}\n\n'
        f'Extracted verbatim from store/_core.py via the diff-oracle pattern\n'
        f'(removal diff is the canonical source). CREATE TABLE statements stay\n'
        f'centralized in _core.py._init_schema per D-DECON-2.\n'
        f'"""\n'
        f'from __future__ import annotations\n'
        f'{import_block}\n\n'
        f'class {class_name}:\n'
        f'    """Domain methods extracted from Store; resolved via MRO."""\n'
    )
    return header + body + "\n"
