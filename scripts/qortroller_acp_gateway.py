"""
QorTroller ACP Gateway — Phase 4 (Grok Build primary, Devin secondary).

Implements docs/design/buzz-phase4-acp-grok-devin-addendum.md.

  #rig-ops  (@EA <command>)
        -> parse mention + intent
        -> authorize (operator pubkey allow-list, fail-closed)
        -> route by complexity (Grok Build | Devin)
        -> execute through the safe tool surface (shell=False, no arbitrary shell)
        -> reply to #rig-ops (digest only)
        -> local JSONL audit trail (never on Nostr)

Phase 4 sits on top of the Phase 1-3 bot: it re-uses that bot's bridge read
path and its Rust-helper publish path (Architecture C). Nothing here signs a
Nostr event, holds a gamer key, touches HID, or writes to chain.

Honesty rails:
  - Every tool is a fixed argv template. No user string ever reaches a shell.
  - Unknown intents are rejected, not guessed. Fail-closed on an empty
    operator allow-list.
  - `deep_diagnose` does not pretend to be Devin: it writes a hand-off record
    and replies "queued". Devin is an external harness, invoked by the
    operator, and never gets commit/spend authority from here.
  - Replies are digests: bounded length, scrubbed of secret-shaped text, and
    never carrying raw HID / IMU / L4 / frames / full PoAC payloads.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_buzz_bot as bot  # noqa: E402  (needs the scripts/ path above)

# --- Harnesses ---------------------------------------------------------------

HARNESS_GROK = "grok-build"
HARNESS_DEVIN = "devin"

# --- Tool surface (addendum Section 5) ---------------------------------------

TOOL_RUN_PYTEST = "run_pytest"
TOOL_INVARIANT_GATE = "run_invariant_gate"
TOOL_RIG_STATUS = "get_rig_status"
TOOL_SESSION_SUMMARY = "get_session_summary"
TOOL_CEREMONY_STEPS = "list_ceremony_steps"
TOOL_HEALTH_CHECK = "health_check"
# EA-ACP-2 — engineering read tools (Grok-only)
TOOL_LIST_FAILING_TESTS = "list_failing_tests"
TOOL_REPO_HEALTH = "repo_health"
TOOL_SHOW_WP_STATUS = "show_wp_status"
# EA-ACP-3 — plan/confirm (agentic, not autonomous)
TOOL_PLAN = "plan"
TOOL_CONFIRM_PLAN = "confirm_plan"
# EA-ACP-4 — Devin result bridge (operator-mediated read)
TOOL_DIAGNOSE_STATUS = "diagnose_status"
# SAP-3 — job status digest
TOOL_GET_JOB_STATUS = "get_job_status"
# SAP-4 — challenge record
TOOL_CHALLENGE_JOB = "challenge_job"
TOOL_DEEP_DIAGNOSE = "deep_diagnose"
TOOL_STREAM_SEAT_STATUS = "get_stream_seat_status"
# VSS-S1 — agent viewers: summarize digests + flag a down seat (never OPEN)
TOOL_STREAM_SEAT_SUMMARY = "summarize_stream_seat"
TOOL_STREAM_SEAT_FLAG = "flag_stream_seat_down"
# VSS-S3 — READ-only verify-pointer digest (publish is consent-gated elsewhere)
TOOL_STREAM_VERIFY_POINTER = "get_stream_verify_pointer"
# VSS-S5 — organizer pilot checklist (seat + pin + portcert composition)
TOOL_ORGANIZER_PILOT = "get_organizer_pilot_status"

ALLOWED_TOOLS = (
    TOOL_RUN_PYTEST,
    TOOL_INVARIANT_GATE,
    TOOL_RIG_STATUS,
    TOOL_SESSION_SUMMARY,
    TOOL_CEREMONY_STEPS,
    TOOL_HEALTH_CHECK,
    TOOL_LIST_FAILING_TESTS,
    TOOL_REPO_HEALTH,
    TOOL_SHOW_WP_STATUS,
    TOOL_PLAN,
    TOOL_CONFIRM_PLAN,
    TOOL_DIAGNOSE_STATUS,
    TOOL_GET_JOB_STATUS,
    TOOL_CHALLENGE_JOB,
    TOOL_DEEP_DIAGNOSE,
    TOOL_STREAM_SEAT_STATUS,
    TOOL_STREAM_SEAT_SUMMARY,
    TOOL_STREAM_SEAT_FLAG,
    TOOL_STREAM_VERIFY_POINTER,
    TOOL_ORGANIZER_PILOT,
)

# Tools Devin owns regardless of phrasing.
DEVIN_ONLY_TOOLS = (TOOL_DEEP_DIAGNOSE,)
# Tools that stay on Grok Build even if the operator says "devin" — routing a
# read-only status call to the heavy harness buys nothing.
GROK_ONLY_TOOLS = (
    TOOL_RIG_STATUS,
    TOOL_CEREMONY_STEPS,
    TOOL_HEALTH_CHECK,
    TOOL_LIST_FAILING_TESTS,
    TOOL_REPO_HEALTH,
    TOOL_SHOW_WP_STATUS,
    TOOL_PLAN,
    TOOL_CONFIRM_PLAN,
    TOOL_DIAGNOSE_STATUS,
    TOOL_GET_JOB_STATUS,
    TOOL_CHALLENGE_JOB,
    TOOL_STREAM_SEAT_STATUS,
    TOOL_STREAM_SEAT_SUMMARY,
    TOOL_STREAM_SEAT_FLAG,
    TOOL_STREAM_VERIFY_POINTER,
    TOOL_ORGANIZER_PILOT,
)

BOT_HANDLE = os.environ.get("ACP_BOT_HANDLE", "@EA")

# Where a pytest target may live. Anything else is rejected.
PYTEST_ROOTS = ("bridge/tests", "sdk/tests", "tests", "autoresearch/tests")

# EA-ACP-2: allowed work-package docs. Keys are the slugs operators may type.
WP_DOCS: dict[str, Path] = {
    "acp": REPO_ROOT / "docs" / "design" / "buzz-ea-acp-harness-integration-v0.md",
    "gateway": REPO_ROOT / "docs" / "design" / "buzz-phase4-acp-gateway-runbook.md",
    "mvp": REPO_ROOT / "docs" / "design" / "buzz-qortroller-gamer-mvp-v0.md",
    "vss": REPO_ROOT / "docs" / "design" / "buzz-vss-stream-seat-scope-v0.md",
}

# EA-ACP-3: pre-declared plan templates. Unknown goals fall back to a single
# `deep_diagnose` step — the tool is pre-declared, the topic is the goal.
PLAN_REGISTRY: dict[str, list[dict[str, dict[str, str]]]] = {
    "full check": [
        {"tool": TOOL_REPO_HEALTH, "args": {}},
        {"tool": TOOL_LIST_FAILING_TESTS, "args": {}},
    ],
    "vss verify": [
        {"tool": TOOL_STREAM_SEAT_STATUS, "args": {}},
        {"tool": TOOL_STREAM_VERIFY_POINTER, "args": {}},
    ],
    "acp health": [
        {"tool": TOOL_HEALTH_CHECK, "args": {}},
        {"tool": TOOL_INVARIANT_GATE, "args": {}},
    ],
}

PLANS_PATH = Path(
    os.environ.get("ACP_PLANS_FILE", str(REPO_ROOT / "audits" / "acp_plans.jsonl"))
)

# EA-ACP-4: operator/Devin writes result records here; gateway reads only.
DEVIN_RESULTS_PATH = Path(
    os.environ.get("ACP_DEVIN_RESULTS", str(REPO_ROOT / "audits" / "acp_devin_results.jsonl"))
)

# SAP-2: operator-only seal log; no Nostr publish by default.
SEALS_PATH = Path(
    os.environ.get("ACP_SAP_SEALS", str(REPO_ROOT / "audits" / "acp_sap_seals.jsonl"))
)

# SAP-4: lightweight challenge records.
CHALLENGES_PATH = Path(
    os.environ.get("ACP_SAP_CHALLENGES", str(REPO_ROOT / "audits" / "acp_sap_challenges.jsonl"))
)

# Reply bounds (digest discipline).
MAX_REPLY_CHARS = int(os.environ.get("ACP_MAX_REPLY_CHARS", "480"))

# Per-tool subprocess timeouts (seconds).
PYTEST_TIMEOUT = float(os.environ.get("ACP_PYTEST_TIMEOUT", "300"))
GATE_TIMEOUT = float(os.environ.get("ACP_GATE_TIMEOUT", "180"))
SMOKE_TIMEOUT = float(os.environ.get("ACP_SMOKE_TIMEOUT", "60"))

AUDIT_LOG_PATH = Path(
    os.environ.get("ACP_AUDIT_LOG", str(REPO_ROOT / "audits" / "acp_gateway.jsonl"))
)
DEVIN_QUEUE_PATH = Path(
    os.environ.get("ACP_DEVIN_QUEUE", str(REPO_ROOT / "audits" / "acp_devin_queue.jsonl"))
)

# Operator-fired ceremony steps (chain-spend skill). Returned as a checklist,
# never executed by the gateway — chain writes are human-only.
CEREMONY_STEPS = (
    "1. kill switch: lift CHAIN_SUBMISSION_PAUSED process-scoped only, never in bridge/.env",
    "2. estimate first: estimate_gas before every send; a revert at estimation is the answer",
    "3. triple gate: intent env var + explicit --execute/--confirm + hard spend cap vs live balance",
    "4. identity check: deployer must equal the bridge wallet (2x balance guard)",
    "5. operator fires the transaction; agents prepare and verify only",
    "6. report measured cost from a live balance read, never an echoed figure",
)

# Rejection reasons.
REJECT_NOT_ADDRESSED = "not_addressed"
REJECT_UNKNOWN_INTENT = "unknown_intent"
REJECT_UNAUTHORIZED = "unauthorized"
REJECT_BANNED = "banned_tool_surface"
REJECT_BAD_TARGET = "invalid_target"

# Phrases that name a hard-banned capability (addendum Section 5). Matched on the
# raw command so a rejection is logged instead of silently falling through to
# "unknown intent".
BANNED_PATTERNS = (
    re.compile(r"\b(sh|bash|powershell|cmd|exec|eval|subprocess|shell)\b", re.I),
    re.compile(r"\b(wallet|private[\s_-]?key|nsec|seed[\s_-]?phrase|mnemonic)\b", re.I),
    re.compile(r"\b(deploy|gas|spend|transfer|mint|approve|sign[\s_-]?tx|on[\s_-]?chain)\b", re.I),
    re.compile(r"\b(raw[\s_-]?hid|imu|l4[\s_-]?features|frames?|poac[\s_-]?payload)\b", re.I),
    re.compile(r"\b(git\s+(push|commit|merge)|force[\s_-]?push)\b", re.I),
)

# Secret-shaped text scrubbed out of every reply before it leaves the process.
_SCRUB_PATTERNS = (
    (re.compile(r"nsec1[0-9a-z]+", re.I), "[redacted-nsec]"),
    (re.compile(r"\b(sk|xoxb|ghp|gho)-[A-Za-z0-9_\-]{8,}"), "[redacted-token]"),
    (
        re.compile(
            r"([A-Za-z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PRIVKEY))"
            r"\s*[:=]\s*\S+",
            re.I,
        ),
        r"\1=[redacted]",
    ),
)


@dataclass
class GatewayConfig:
    """Gateway configuration. Keys are never held here — only identifiers."""

    repo_root: Path = REPO_ROOT
    bot_handle: str = BOT_HANDLE
    operator_pubkeys: tuple[str, ...] = ()
    rig_ops_channel: str = ""
    audit_log_path: Path = AUDIT_LOG_PATH
    devin_queue_path: Path = DEVIN_QUEUE_PATH
    plans_path: Path = PLANS_PATH
    devin_results_path: Path = DEVIN_RESULTS_PATH
    seals_path: Path = SEALS_PATH
    challenges_path: Path = CHALLENGES_PATH
    max_reply_chars: int = MAX_REPLY_CHARS
    dry_run: bool = False


@dataclass
class Intent:
    tool: str
    args: dict[str, str] = field(default_factory=dict)
    harness: str = HARNESS_GROK
    explicit_devin: bool = False
    raw: str = ""


@dataclass
class Rejection:
    reason: str
    detail: str = ""
    raw: str = ""


@dataclass
class ToolResult:
    tool: str
    harness: str
    ok: bool
    summary: str
    tags: list[list[str]] = field(default_factory=list)
    job_id: str | None = None


def load_config() -> GatewayConfig:
    """Build the gateway config from env. Operator allow-list is fail-closed."""
    pubkeys = tuple(
        p.strip()
        for p in os.environ.get("ACP_OPERATOR_PUBKEYS", "").split(",")
        if p.strip()
    )
    channels = [
        c.strip() for c in os.environ.get("BUZZ_CHANNEL_IDS", "").split(",") if c.strip()
    ]
    return GatewayConfig(
        operator_pubkeys=pubkeys,
        rig_ops_channel=os.environ.get("ACP_RIG_OPS_CHANNEL_ID", "")
        or (channels[0] if channels else ""),
        dry_run=os.environ.get("ACP_DRY_RUN", "").lower() in ("1", "true", "yes"),
    )


# --- Authorization -----------------------------------------------------------

def authorize(pubkey: str, cfg: GatewayConfig) -> bool:
    """Only allow-listed operator pubkeys may drive the gateway.

    Fail-closed: an empty allow-list authorizes nobody.
    """
    if not cfg.operator_pubkeys:
        return False
    return pubkey.strip().lower() in {p.lower() for p in cfg.operator_pubkeys}


# --- Intent parsing ----------------------------------------------------------

def _strip_handle(content: str, handle: str) -> Optional[str]:
    """Return the command text if the message addresses the bot, else None."""
    text = content.strip()
    if not text:
        return None
    lowered = text.lower()
    handle = handle.lower()
    if not lowered.startswith(handle):
        return None
    return text[len(handle):].strip()


def _validate_pytest_target(target: str, repo_root: Path) -> Optional[str]:
    """Return a repo-relative pytest target, or None if it is not allowed."""
    candidate = target.strip().strip("'\"")
    if not candidate or any(ch in candidate for ch in " ;|&$`\n\t"):
        return None
    normalized = candidate.replace("\\", "/").lstrip("./")
    if ".." in normalized.split("/"):
        return None
    if not normalized.startswith(PYTEST_ROOTS):
        return None
    resolved = (repo_root / normalized).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return None
    if not resolved.exists():
        return None
    return normalized


def parse_mention(
    content: str, cfg: Optional[GatewayConfig] = None
) -> Intent | Rejection | None:
    """Parse an `@EA <command>` message into an Intent.

    Returns None when the message does not address the bot at all (the common
    case in a busy channel — stay silent), a Rejection when it addresses the
    bot but asks for something outside the allow-list, and an Intent otherwise.
    """
    cfg = cfg or GatewayConfig()
    command = _strip_handle(content, cfg.bot_handle)
    if command is None:
        return None
    if not command:
        return Rejection(REJECT_UNKNOWN_INTENT, "empty command", content)

    lowered = command.lower()
    explicit_devin = bool(re.match(r"^devin\b", lowered))
    if explicit_devin:
        command = command[len("devin"):].strip()

    matched = _match_intent(command, cfg)
    if isinstance(matched, Intent):
        matched.explicit_devin = explicit_devin
        matched.harness = route(matched.tool, explicit_devin)
        matched.raw = content.strip()
        return matched
    if isinstance(matched, Rejection):
        matched.raw = content.strip()
        return matched

    # No allow-listed intent matched. If the text names a banned capability,
    # say so explicitly — a rejected shell request must be auditable.
    for pattern in BANNED_PATTERNS:
        if pattern.search(command):
            return Rejection(REJECT_BANNED, pattern.pattern, content.strip())
    return Rejection(REJECT_UNKNOWN_INTENT, command[:80], content.strip())


def _match_intent(command: str, cfg: GatewayConfig) -> Intent | Rejection | None:
    """Match the command text against the allow-listed intents.

    Matching is case-insensitive, but captured arguments (pytest targets,
    session ids) keep the operator's original casing.
    """
    m = re.match(r"^(?:run\s+)?pytest\s+(\S+)$", command, re.I)
    if m:
        target = _validate_pytest_target(m.group(1), cfg.repo_root)
        if target is None:
            return Rejection(
                REJECT_BAD_TARGET,
                f"pytest target must be an existing path under {'/'.join(PYTEST_ROOTS)}",
            )
        return Intent(TOOL_RUN_PYTEST, {"target": target})

    if re.match(
        r"^(?:run\s+)?(?:invariant|invariants|pv-ci|pvci)"
        r"(?:\s+(?:status|gate|check))?$",
        command,
        re.I,
    ):
        return Intent(TOOL_INVARIANT_GATE)

    if re.match(r"^(?:get\s+)?(?:rig\s*)?status$|^rig$", command, re.I):
        return Intent(TOOL_RIG_STATUS)

    # VSS-S1: more-specific agent-viewer intents before generic "seat"
    if re.match(
        r"^(?:summarize\s+(?:stream\s+)?seat(?:\s+status)?|"
        r"stream\s+seat\s+summary|seat\s+summary)$",
        command,
        re.I,
    ):
        return Intent(TOOL_STREAM_SEAT_SUMMARY)

    if re.match(
        r"^(?:flag\s+(?:stream\s+)?seat(?:\s+down)?|"
        r"(?:is\s+)?(?:stream\s+)?seat\s+down|"
        r"flag\s+stream\s+down)$",
        command,
        re.I,
    ):
        return Intent(TOOL_STREAM_SEAT_FLAG)

    # VSS-S3: verify pointer display (not a publish)
    if re.match(
        r"^(?:get\s+)?(?:stream\s+)?verify(?:\s+pointer)?$"
        r"|^verify\s+stream$|^portcert\s+pointer$",
        command,
        re.I,
    ):
        return Intent(TOOL_STREAM_VERIFY_POINTER)

    # VSS-S5: organizer pilot checklist
    if re.match(
        r"^(?:get\s+)?organizer\s+pilot(?:\s+status)?$"
        r"|^pilot\s+checklist$|^pilot\s+status$|^organizer\s+status$",
        command,
        re.I,
    ):
        return Intent(TOOL_ORGANIZER_PILOT)

    if re.match(
        r"^(?:get\s+)?stream(?:\s+seat)?(?:\s+status)?$|^seat$|^vss$",
        command,
        re.I,
    ):
        return Intent(TOOL_STREAM_SEAT_STATUS)

    m = re.match(r"^(?:get\s+)?session(?:\s+summary)?(?:\s+(\S+))?$", command, re.I)
    if m:
        session_id = (m.group(1) or "").strip()
        if session_id and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", session_id):
            return Rejection(REJECT_BAD_TARGET, "session id must be alphanumeric")
        return Intent(TOOL_SESSION_SUMMARY, {"session_id": session_id})

    if re.match(r"^(?:list\s+)?ceremony(?:\s+steps)?$", command, re.I):
        return Intent(TOOL_CEREMONY_STEPS)

    if re.match(r"^health(?:\s+check)?$", command, re.I):
        return Intent(TOOL_HEALTH_CHECK)

    # EA-ACP-2: engineering read tools
    if re.match(r"^(?:list\s+)?failing(?:\s+tests?)?$", command, re.I):
        return Intent(TOOL_LIST_FAILING_TESTS)

    if re.match(r"^(?:repo\s+)?health$|^repo\s+status$", command, re.I):
        return Intent(TOOL_REPO_HEALTH)

    m = re.match(r"^(?:wp|work(?:\s*|-)?package)\s+(\S+)$", command, re.I)
    if m:
        slug = m.group(1).strip().lower()
        if slug not in WP_DOCS:
            return Rejection(REJECT_BAD_TARGET, f"unknown wp: {slug}")
        return Intent(TOOL_SHOW_WP_STATUS, {"wp": slug})

    # EA-ACP-3: plan/confirm. `plan` stages, `confirm` executes.
    m = re.match(r"^plan\s+(.+)$", command, re.I)
    if m:
        goal = m.group(1).strip()[:200]
        return Intent(TOOL_PLAN, {"goal": goal})

    m = re.match(r"^confirm\s+plan\s+(\S+)$", command, re.I)
    if m:
        return Intent(TOOL_CONFIRM_PLAN, {"plan_id": m.group(1).strip().lower()[:16]})

    # EA-ACP-4: operator asks for the latest Devin result digest.
    if re.match(r"^(?:diagnose|devin)\s+status$", command, re.I):
        return Intent(TOOL_DIAGNOSE_STATUS)

    # SAP-3: job status across queue / results / seals.
    m = re.match(r"^(?:job|sap)\s+status\s+(\S+)$", command, re.I)
    if m:
        return Intent(TOOL_GET_JOB_STATUS, {"job_id": m.group(1).strip().lower()[:64]})

    # SAP-4: challenge a job with a demand (e.g. "pytest bridge/tests/..." or "invariant").
    m = re.match(r"^challenge\s+(?:job\s+)?(\S+)\s+(.+)$", command, re.I)
    if m:
        return Intent(
            TOOL_CHALLENGE_JOB,
            {
                "job_id": m.group(1).strip().lower()[:64],
                "demand": m.group(2).strip()[:200],
            },
        )

    m = re.match(r"^(?:deep\s+)?diagnose\s+(.+)$", command, re.I)
    if m:
        raw = m.group(1).strip()
        # EA-ACP-1: optional acceptance/priority fields after '|'
        parts = [p.strip() for p in raw.split("|")]
        topic = parts[0]
        acceptance = None
        priority = None
        for part in parts[1:]:
            low = part.lower()
            if low.startswith("acceptance "):
                acceptance = part[11:].strip()[:200]
            elif low.startswith("priority "):
                priority = part[9:].strip()[:32]
            else:
                # Unknown pipe segment — keep it in the topic, do not invent fields.
                topic += " | " + part
        args: dict[str, str] = {"topic": topic[:200]}
        if acceptance:
            args["acceptance"] = acceptance
        if priority:
            args["priority"] = priority
        return Intent(TOOL_DEEP_DIAGNOSE, args)

    return None


# --- Routing -----------------------------------------------------------------

def route(tool: str, explicit_devin: bool = False) -> str:
    """Grok Build is primary; Devin takes heavy or explicitly-addressed work."""
    if tool in DEVIN_ONLY_TOOLS:
        return HARNESS_DEVIN
    if tool in GROK_ONLY_TOOLS:
        return HARNESS_GROK
    if explicit_devin:
        return HARNESS_DEVIN
    return HARNESS_GROK


# --- Safe tool surface (fixed argv, shell=False) ------------------------------

def _run(argv: list[str], cfg: GatewayConfig, timeout: float) -> tuple[int, str]:
    """Run a fixed argv with no shell. Returns (returncode, combined output)."""
    try:
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            cwd=str(cfg.repo_root),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f}s"
    except Exception as exc:  # missing interpreter, permissions, ...
        return 127, f"invocation failed: {exc}"
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _pytest_summary(output: str) -> str:
    """Pull the terse pass/fail line out of pytest output."""
    for line in reversed(output.strip().splitlines()):
        if re.search(r"\b\d+\s+(passed|failed|error|errors|skipped|deselected)", line):
            return line.strip().strip("= ")
    return "no pytest summary line"


def _tool_run_pytest(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    target = intent.args["target"]
    code, output = _run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-header", "--tb=line"],
        cfg,
        PYTEST_TIMEOUT,
    )
    summary = _pytest_summary(output)
    return ToolResult(
        intent.tool,
        intent.harness,
        code == 0,
        f"pytest {target}: {summary}",
        [["acp_tool", intent.tool], ["target", target], ["exit_code", str(code)]],
    )


def _tool_invariant_gate(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    code, output = _run(
        [sys.executable, "scripts/vapi_invariant_gate.py"], cfg, GATE_TIMEOUT
    )
    m = re.search(r"(\d+)\s+invariants", output)
    count = m.group(1) if m else "unknown"
    verdict = "PASS" if code == 0 else "FAIL"
    return ToolResult(
        intent.tool,
        intent.harness,
        code == 0,
        f"PV-CI {verdict} — {count} invariants",
        [["acp_tool", intent.tool], ["pv_ci", count], ["verdict", verdict]],
    )


def _tool_rig_status(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    bot_cfg = bot._load_config()
    state = bot._read_rig_state(bot_cfg)
    tags = bot._status_tags(cfg.rig_ops_channel, state) + [["acp_tool", intent.tool]]
    return ToolResult(
        intent.tool,
        intent.harness,
        state["bridge_health"] == "healthy",
        bot._status_event_content(state),
        tags,
    )


def _tool_session_summary(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    bot_cfg = bot._load_config()
    postcard = bot._read_session_postcard(bot_cfg, intent.args.get("session_id", ""))
    if postcard is None:
        return ToolResult(
            intent.tool,
            intent.harness,
            False,
            "session: bridge unreachable or no active session",
            [["acp_tool", intent.tool]],
        )
    tags = bot._postcard_tags(cfg.rig_ops_channel, postcard) + [["acp_tool", intent.tool]]
    return ToolResult(
        intent.tool, intent.harness, True, bot._postcard_content(postcard), tags
    )


def _tool_stream_seat_status(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """VSS-4 — Read stream seat status (digest only, scrubbed).

    Reads /operator/vss/eligibility (VSS-1) from the bridge and returns a digest.
    Never carries raw HID/IMU/L4/frames, keys, or full PoAC. The reply
    is scrubbed by format_reply() before publishing to #rig-ops.

    Fail-closed: if the bridge is unreachable, returns ok=False with a
    clear message — never fabricates eligibility.
    """
    bot_cfg = bot._load_config()
    # Operator sub-app is mounted at /operator (see main.py app.mount).
    elig = bot._bridge_get("/operator/vss/eligibility", bot_cfg)
    if elig is None:
        return ToolResult(
            intent.tool,
            intent.harness,
            False,
            "stream seat: bridge unreachable — eligibility unknown (fail-closed)",
            [["acp_tool", intent.tool], ["eligible", "unknown"]],
        )

    eligible = bool(elig.get("eligible", False))
    capture_up = bool(elig.get("capture_up", False))
    oracle_running = bool(elig.get("retina_oracle_running", False))
    reason = elig.get("reason_if_closed", "")
    honesty = elig.get("honesty", {})

    # Build digest-only summary (no raw substrate, no keys)
    parts = [
        f"stream seat: {'ELIGIBLE' if eligible else 'CLOSED'}",
        f"capture: {'up' if capture_up else 'down'}",
        f"oracle: {'running' if oracle_running else 'stopped'}",
    ]
    if reason:
        parts.append(f"reason: {reason[:80]}")
    poep = honesty.get("poep_enabled", False)
    l6b = honesty.get("l6b_enabled", False)
    cand = honesty.get("candidate_ok", False)
    parts.append(f"poep={poep} l6b={l6b} candidate={cand}")

    summary = " | ".join(parts)
    tags = [
        ["acp_tool", intent.tool],
        ["eligible", "true" if eligible else "false"],
        ["capture", "up" if capture_up else "down"],
        ["oracle", "running" if oracle_running else "stopped"],
        ["poep_enabled", "true" if poep else "false"],
        ["l6b_enabled", "true" if l6b else "false"],
        ["candidate_ok", "true" if cand else "false"],
    ]

    return ToolResult(
        intent.tool,
        intent.harness,
        eligible,  # ok=True only if eligible
        summary,
        tags,
    )


def _tool_stream_seat_summary(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """VSS-S1 — Agent viewer summary of stream seat (digest only).

    Agents may READ/summarize; they never OPEN (scope §4 + S1).
    """
    # Import path: bridge package when repo root is cwd / sys.path
    bridge_path = str(REPO_ROOT / "bridge")
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    from vapi_bridge.vss_agent_viewer import (  # noqa: WPS433
        agent_may_open_seat,
        summarize_seat,
    )

    bot_cfg = bot._load_config()
    elig = bot._bridge_get("/operator/vss/eligibility", bot_cfg)
    summary = summarize_seat(elig)
    ok = elig is not None
    tags = [
        ["acp_tool", intent.tool],
        ["agent_can_open", "true" if agent_may_open_seat() else "false"],
        ["eligible", "unknown" if elig is None else ("true" if elig.get("eligible") else "false")],
    ]
    return ToolResult(intent.tool, intent.harness, ok, summary, tags)


def _tool_stream_seat_flag(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """VSS-S1 — Agent flag-down for a stream seat (view-only signal).

    FLAG_DOWN when eligibility is false; SEAT_OK when true; UNKNOWN if
    bridge unreachable. Never fabricates DOWN. Never opens a seat.
    """
    bridge_path = str(REPO_ROOT / "bridge")
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    from vapi_bridge.vss_agent_viewer import (  # noqa: WPS433
        FLAG_DOWN,
        agent_may_open_seat,
        flag_seat_down,
    )

    bot_cfg = bot._load_config()
    elig = bot._bridge_get("/operator/vss/eligibility", bot_cfg)
    decision = flag_seat_down(elig)
    tags = [
        ["acp_tool", intent.tool],
        ["flag", str(decision.get("flag", "UNKNOWN"))],
        ["should_flag", "true" if decision.get("should_flag") else "false"],
        ["agent_can_open", "true" if agent_may_open_seat() else "false"],
    ]
    # ok=True for a successful evaluation (including FLAG_DOWN); False only unknown
    ok = decision.get("flag") != "SEAT_UNKNOWN"
    # Prefer flagging DOWN as the actionable agent signal
    if decision.get("flag") == FLAG_DOWN:
        ok = True
    return ToolResult(
        intent.tool,
        intent.harness,
        ok,
        str(decision.get("summary", "")),
        tags,
    )


def _tool_organizer_pilot(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """VSS-S5 — Organizer pilot checklist (seat + pin + portcert). Digest only."""
    bridge_path = str(REPO_ROOT / "bridge")
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    from vapi_bridge.vss_organizer_pilot import (  # noqa: WPS433
        organizer_commands,
        pilot_from_eligibility,
    )

    bot_cfg = bot._load_config()
    elig = bot._bridge_get("/operator/vss/eligibility", bot_cfg)
    session_id = intent.args.get("session_id") or os.environ.get("VSS_SESSION_ID") or ""
    pin = intent.args.get("pin_event_id") or os.environ.get("VSS_PIN_EVENT_ID") or ""
    checklist = pilot_from_eligibility(
        elig,
        session_id=session_id or None,
        pin_event_id=pin or None,
        streams_channel=os.environ.get("VSS_STREAMS_CHANNEL") or None,
        matches_channel=os.environ.get("BUZZ_MATCHES_CHANNEL_ID") or None,
    )
    cmds = organizer_commands(session_id=session_id or None, pin_event_id=pin or None)
    summary = checklist.summary + " | cmds: " + " ; ".join(cmds[:3])
    if len(summary) > MAX_REPLY_CHARS:
        summary = summary[: MAX_REPLY_CHARS - 3] + "..."
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        [
            ["acp_tool", intent.tool],
            ["ready", "true" if checklist.ready else "false"],
            ["seat_ok", "true" if checklist.seat_ok else "false"],
            ["session_bound", "true" if checklist.session_bound else "false"],
            ["pin_present", "true" if checklist.pin_present else "false"],
        ],
    )


def _tool_stream_verify_pointer(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """VSS-S3 — Display public verify pointer (READ-only; does not publish).

    Publishing a highlight requires gamer --consent-ok via buzz_vss_highlight.py.
    This tool only shows the stranger-runnable pointer digest.
    """
    bridge_path = str(REPO_ROOT / "bridge")
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    from vapi_bridge.vss_highlight import format_verify_pointer_digest  # noqa: WPS433

    session_id = intent.args.get("session_id") or os.environ.get("VSS_SESSION_ID") or ""
    summary = format_verify_pointer_digest(
        session_id=session_id or None,
        verify_url=None,
    )
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        [
            ["acp_tool", intent.tool],
            ["consent_required_to_publish", "true"],
            ["session_id", session_id or "none"],
        ],
    )


def _tool_ceremony_steps(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        "operator-fired ceremony — " + " / ".join(CEREMONY_STEPS),
        [["acp_tool", intent.tool], ["steps", str(len(CEREMONY_STEPS))]],
    )


# Smoke checks from AGENTS.md "Baseline health commands". Fixed argv only.
HEALTH_CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("ea", [sys.executable, "-c", "import qortroller, qortroller_daemon"]),
    (
        "oracle",
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'bridge'); "
            "from vapi_bridge.retina_visual_oracle import VisualOracleConfig; "
            "VisualOracleConfig()",
        ],
    ),
    (
        "shell-false",
        [
            sys.executable,
            "-c",
            "import inspect, qortroller; "
            "assert 'shell=False' in inspect.getsource(qortroller)",
        ],
    ),
)


def _tool_health_check(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    results: list[str] = []
    all_ok = True
    for name, argv in HEALTH_CHECKS:
        code, _ = _run(argv, cfg, SMOKE_TIMEOUT)
        ok = code == 0
        all_ok = all_ok and ok
        results.append(f"{name}: {'ok' if ok else 'FAIL'}")
    return ToolResult(
        intent.tool,
        intent.harness,
        all_ok,
        "health — " + " | ".join(results),
        [["acp_tool", intent.tool], ["healthy", "true" if all_ok else "false"]],
    )


def _tool_list_failing_tests(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """EA-ACP-2: Read lastfailed cache and return a bounded digest.

    Does not re-run tests; only reports what pytest already recorded.
    """
    cache_path = cfg.repo_root / ".pytest_cache" / "v" / "cache" / "lastfailed"
    if not cache_path.is_file():
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            "failing tests: no cache (run pytest first)",
            [["acp_tool", intent.tool], ["count", "0"], ["cache", "missing"]],
        )
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        nodeids = sorted(str(k) for k in data.keys())
    except (json.JSONDecodeError, OSError):
        return ToolResult(
            intent.tool,
            intent.harness,
            False,
            "failing tests: cache unreadable",
            [["acp_tool", intent.tool], ["count", "?"]],
        )
    count = len(nodeids)
    if count == 0:
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            "failing tests: 0 (empty cache)",
            [["acp_tool", intent.tool], ["count", "0"]],
        )
    # Bound the digest to MAX_REPLY_CHARS; keep the first N node ids.
    joined = ", ".join(nodeids)
    if len(joined) > MAX_REPLY_CHARS - 80:
        joined = joined[: MAX_REPLY_CHARS - 100].rsplit(", ", 1)[0] + f", … (+{count - 3} more)"
    summary = f"failing tests: {count} — {joined}"
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        [["acp_tool", intent.tool], ["count", str(count)]],
    )


def _tool_repo_health(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """EA-ACP-2: Compose health + PV-CI one-liner."""
    health = _tool_health_check(intent, cfg)
    pvci = _tool_invariant_gate(intent, cfg)
    ok = health.ok and pvci.ok
    summary = f"repo health — {health.summary} | {pvci.summary}"
    tags = [
        ["acp_tool", intent.tool],
        ["healthy", "true" if health.ok else "false"],
        ["pv_ci", next((t[1] for t in pvci.tags if t[0] == "pv_ci"), "?")],
        ["verdict", "PASS" if ok else "FAIL"],
    ]
    return ToolResult(intent.tool, intent.harness, ok, summary, tags)


def _tool_show_wp_status(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """EA-ACP-2: Read headings from an allow-listed work-package doc."""
    slug = intent.args.get("wp", "")
    doc_path = WP_DOCS.get(slug)
    if not doc_path or not doc_path.is_file():
        return ToolResult(
            intent.tool,
            intent.harness,
            False,
            f"wp: {slug} not found",
            [["acp_tool", intent.tool], ["wp", slug], ["found", "false"]],
        )
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ToolResult(
            intent.tool,
            intent.harness,
            False,
            f"wp: {slug} unreadable ({exc})",
            [["acp_tool", intent.tool], ["wp", slug]],
        )
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") or stripped.startswith("## "):
            heading = stripped.lstrip("# ").strip()
            if heading:
                headings.append(heading)
    if not headings:
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            f"wp {slug}: no headings",
            [["acp_tool", intent.tool], ["wp", slug], ["headings", "0"]],
        )
    # Build a bounded digest of headings.
    joined = " | ".join(headings[:8])
    if len(joined) > MAX_REPLY_CHARS - 60:
        joined = joined[: MAX_REPLY_CHARS - 80].rsplit(" | ", 1)[0] + " | …"
    summary = f"wp {slug}: {joined}"
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        [
            ["acp_tool", intent.tool],
            ["wp", slug],
            ["headings", str(len(headings))],
            ["found", "true"],
        ],
    )


def _load_latest_plan(plans_path: Path, plan_id: str) -> dict | None:
    """Return the most recent record for a given plan_id, or None."""
    if not plans_path.is_file():
        return None
    latest: dict | None = None
    for line in plans_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("plan_id") == plan_id:
            if latest is None or record.get("ts", 0) > latest.get("ts", 0):
                latest = record
    return latest


def _save_plan_record(plans_path: Path, record: dict) -> None:
    _append_jsonl(plans_path, record)


def _plan_steps_from_goal(goal: str) -> list[dict[str, dict[str, str]]]:
    """Look up a pre-declared plan, or fall back to a single deep_diagnose step.

    The fallback keeps every `plan` command useful while the tool itself is
    still from the allow-list. Unknown goals never generate arbitrary shell.
    """
    return PLAN_REGISTRY.get(goal.lower()) or [
        {"tool": TOOL_DEEP_DIAGNOSE, "args": {"topic": goal}}
    ]


def _tool_plan(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """EA-ACP-3: stage a plan. No tool executes until `confirm plan <id>`."""
    goal = intent.args.get("goal", "")
    steps = _plan_steps_from_goal(goal)
    plan_id = secrets.token_hex(3)  # 6 hex chars, short enough to type
    # SAP-1: job_id aliases plan_id for stable cross-file tracing.
    job_id = f"sap_{plan_id}"
    record: dict[str, object] = {
        "ts": int(time.time()),
        "plan_id": plan_id,
        "job_id": job_id,
        "goal": goal,
        "status": "pending",
        "steps": steps,
    }
    _save_plan_record(cfg.plans_path, record)
    step_lines = ", ".join(
        f"{i + 1}. {s['tool']}" + (f" ({s['args'].get('topic', '')})"[:40] if s.get("args") else "")
        for i, s in enumerate(steps)
    )
    summary = f"plan {plan_id}: {goal[:80]} — {step_lines} (reply `@EA confirm plan {plan_id}` to run)"
    tags = [
        ["acp_tool", intent.tool],
        ["plan_id", plan_id],
        ["steps", str(len(steps))],
        ["status", "pending"],
    ]
    return ToolResult(intent.tool, intent.harness, True, summary, tags, job_id=job_id)


def _tool_confirm_plan(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """EA-ACP-3: execute a staged plan, one allow-listed tool at a time."""
    plan_id = intent.args.get("plan_id", "")
    plan = _load_latest_plan(cfg.plans_path, plan_id)
    if plan is None or plan.get("status") != "pending":
        return ToolResult(
            intent.tool,
            intent.harness,
            False,
            f"confirm: plan {plan_id} not found or already completed",
            [["acp_tool", intent.tool], ["plan_id", plan_id], ["found", "false"]],
        )

    # Execute each step through the same safe execute() path.
    step_results: list[dict[str, object]] = []
    all_ok = True
    for step in plan.get("steps", []):
        step_tool = step.get("tool", "")
        step_args = step.get("args", {})
        step_intent = Intent(
            step_tool,
            {k: str(v) for k, v in step_args.items()},
            harness=route(step_tool),
            raw=f"plan {plan_id} step {step_tool}",
        )
        step_result = execute(step_intent, cfg)
        all_ok = all_ok and step_result.ok
        step_results.append(
            {
                "tool": step_tool,
                "ok": step_result.ok,
                "summary": step_result.summary,
            }
        )

    completed_record = {
        "ts": int(time.time()),
        "plan_id": plan_id,
        "job_id": plan.get("job_id"),
        "goal": plan.get("goal", ""),
        "status": "completed",
        "steps_ok": all_ok,
        "step_results": step_results,
    }
    _save_plan_record(cfg.plans_path, completed_record)

    # Build a bounded, honest digest.
    parts = []
    for sr in step_results:
        mark = "ok" if sr["ok"] else "fail"
        parts.append(f"{sr['tool']}: {mark}")
    completed_summary = " | ".join(parts)
    if len(completed_summary) > MAX_REPLY_CHARS - 80:
        completed_summary = completed_summary[: MAX_REPLY_CHARS - 100].rsplit(" | ", 1)[0] + " | …"
    summary = f"plan {plan_id} executed — {completed_summary}"
    tags = [
        ["acp_tool", intent.tool],
        ["plan_id", plan_id],
        ["steps", str(len(step_results))],
        ["steps_ok", "true" if all_ok else "false"],
        ["status", "completed"],
    ]
    job_id = plan.get("job_id")
    return ToolResult(
        intent.tool,
        intent.harness,
        all_ok,
        summary,
        tags,
        job_id=job_id,
    )


def _tool_diagnose_status(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """EA-ACP-4: read the local Devin results file and post a bounded digest.

    The gateway never auto-publishes a Devin result as protocol truth. This
    tool only reads what an operator or Devin has already written to the
    local `acp_devin_results.jsonl`.
    """
    if not cfg.devin_results_path.is_file():
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            "diagnose status: no results yet",
            [["acp_tool", intent.tool], ["count", "0"], ["status", "empty"]],
        )
    rows: list[dict] = []
    for line in cfg.devin_results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            "diagnose status: no results yet",
            [["acp_tool", intent.tool], ["count", "0"], ["status", "empty"]],
        )
    # Show latest 3 by default.
    latest = list(reversed(rows))[:3]
    parts: list[str] = []
    for r in latest:
        topic = scrub(str(r.get("topic", "?"))[:50])
        status = scrub(str(r.get("status", "?")))
        pr_url = scrub(str(r.get("pr_url", ""))[:80])
        one_line = scrub(str(r.get("summary", ""))[:80])
        piece = f"{topic} [{status}]"
        if pr_url:
            piece += f" pr={pr_url}"
        if one_line:
            piece += f" — {one_line}"
        parts.append(piece)
    summary = "diagnose status: " + " | ".join(parts)
    if len(summary) > MAX_REPLY_CHARS - 80:
        summary = summary[: MAX_REPLY_CHARS - 100].rsplit(" | ", 1)[0] + " | …"
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        [
            ["acp_tool", intent.tool],
            ["count", str(len(rows))],
            ["status", "ok"],
        ],
    )


def _tool_challenge_job(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """SAP-4: append a lightweight challenge record for a job."""
    job_id = intent.args.get("job_id", "")
    demand = intent.args.get("demand", "")
    record: dict[str, object] = {
        "ts": int(time.time()),
        "job_id": job_id,
        "demand": scrub(demand),
        "status": "open",
        "verdict": "",
    }
    _append_jsonl(cfg.challenges_path, record)
    summary = f"challenge {job_id}: {demand[:120]}"
    tags = [
        ["acp_tool", intent.tool],
        ["job", job_id],
        ["status", "open"],
    ]
    if demand:
        tags.append(["demand", scrub(demand)[:120]])
    return ToolResult(intent.tool, intent.harness, True, summary, tags, job_id=job_id)


def _latest_record_by_job_id(path: Path, job_id: str) -> dict | None:
    """Return the most recent JSONL record with the given job_id, or None."""
    if not path.is_file():
        return None
    latest: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(record.get("job_id", "")) == job_id:
            if latest is None or record.get("ts", 0) > latest.get("ts", 0):
                latest = record
    return latest


def _satisfies_challenge(challenge: dict, records: list[dict]) -> bool:
    """Heuristic check: does a later record satisfy the challenge demand?

    This is intentionally local and approximate. It never invents evidence.
    """
    demand = scrub(str(challenge.get("demand", ""))).lower()
    challenge_ts = challenge.get("ts", 0)
    if not demand:
        return False

    demand_tokens = [t for t in demand.split() if len(t) > 1]
    # Order invariant / pytest / generic.
    for record in records:
        if record.get("ts", 0) < challenge_ts:
            continue
        text = " ".join(
            str(record.get(k, "")) for k in ("topic", "summary", "reply", "demand", "goal")
        ).lower()
        tool = str(record.get("tool", "")).lower()
        ok = record.get("ok")

        if demand.startswith("pytest") or "pytest" in demand:
            path_tokens = [t for t in demand.split() if t.endswith(".py") or "/" in t]
            if tool == TOOL_RUN_PYTEST and ok is True:
                return True
            if "pytest" in text:
                if not path_tokens or any(pt in text for pt in path_tokens):
                    if any(w in text for w in ("passed", "green", "ok", "all green")):
                        return True

        if any(w in demand for w in ("invariant", "pv-ci", "gate")):
            if tool in (TOOL_INVARIANT_GATE, "vapi_invariant_gate") and ok is True:
                return True
            if all(w in text for w in ("invariant", "pass")) or "188" in text:
                return True

        if any(w in demand for w in ("health", "repo health")):
            if tool in (TOOL_REPO_HEALTH, TOOL_HEALTH_CHECK) and ok is True:
                return True
            if all(w in text for w in ("health", "ok")):
                return True

        # Generic: demand words appear with a positive completion signal.
        if all(t in text for t in demand_tokens[:4]):
            if any(w in text for w in ("done", "ok", "passed", "green", "accept")):
                return True
    return False


def _all_records_by_job_id(
    job_id: str, cfg: GatewayConfig
) -> list[dict]:
    """Collect all queue/plan/result/seal/challenge rows for the job."""
    records: list[dict] = []
    for path in (
        cfg.audit_log_path,
        cfg.devin_queue_path,
        cfg.plans_path,
        cfg.devin_results_path,
        cfg.seals_path,
        cfg.challenges_path,
    ):
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(record.get("job_id", "")) == job_id:
                    records.append(record)
    return records


def _challenge_summary(challenges: list[dict], records: list[dict]) -> list[str]:
    """Build bounded challenge status lines."""
    lines: list[str] = []
    for ch in challenges:
        demand = scrub(str(ch.get("demand", ""))[:60])
        state = "satisfied" if _satisfies_challenge(ch, records) else "open"
        lines.append(f"challenge: {demand} [{state}]")
    return lines


def _tool_get_job_status(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """SAP-3: one digest tying queue, results, seals, and challenges for a job_id."""
    job_id = intent.args.get("job_id", "")
    queue = _latest_record_by_job_id(cfg.devin_queue_path, job_id)
    plan = _latest_record_by_job_id(cfg.plans_path, job_id)
    result = _latest_record_by_job_id(cfg.devin_results_path, job_id)
    seal = _latest_record_by_job_id(cfg.seals_path, job_id)

    # SAP-4: collect challenges and cross-check against all job records.
    records = _all_records_by_job_id(job_id, cfg)
    challenges = [r for r in records if r.get("demand") and r.get("status") == "open"]

    if not any((queue, plan, result, seal, records)):
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            f"job {job_id}: unknown job",
            [["acp_tool", intent.tool], ["job", job_id], ["status", "unknown"]],
        )

    pieces: list[str] = [f"job {job_id}"]
    if queue:
        pieces.append(f"queued: {scrub(str(queue.get('topic', ''))[:60])}")
    elif plan:
        pieces.append(f"planned: {scrub(str(plan.get('goal', ''))[:60])}")

    if result:
        status = scrub(str(result.get("status", "?")))
        topic = scrub(str(result.get("topic", ""))[:50])
        pieces.append(f"result: {topic} [{status}]")
        if result.get("pr_url"):
            pieces.append(f"pr: {scrub(str(result['pr_url'])[:80])}")

    if seal:
        verdict = scrub(str(seal.get("verdict", "?")))
        ref = scrub(str(seal.get("ref", ""))[:60])
        note = scrub(str(seal.get("note", ""))[:60])
        pieces.append(f"sealed: {verdict}")
        if ref:
            pieces.append(f"ref: {ref}")
        if note:
            pieces.append(f"note: {note}")

    for line in _challenge_summary(challenges, records):
        pieces.append(line)

    summary = " | ".join(pieces)
    if len(summary) > MAX_REPLY_CHARS - 80:
        summary = summary[: MAX_REPLY_CHARS - 100].rsplit(" | ", 1)[0] + " | …"
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        [
            ["acp_tool", intent.tool],
            ["job", job_id],
            ["status", "ok"],
        ],
    )


def _new_job_id() -> str:
    """Generate a stable SAP job id: sap_<ts_hex>_<4-hex nonce>."""
    return f"sap_{int(time.time()):x}_{secrets.token_hex(2)}"


def _repo_sha_hint(cfg: GatewayConfig) -> str:
    """Return the current HEAD SHA for the hand-off record (EA-ACP-1).

    Fail-open: if git is missing or the repo is not a git checkout, return "".
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cfg.repo_root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except Exception:
        pass
    return ""


def _tool_deep_diagnose(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """Queue a Devin hand-off. The gateway never impersonates the harness."""
    topic = intent.args.get("topic", "")
    acceptance = intent.args.get("acceptance")
    priority = intent.args.get("priority", "normal")
    job_id = _new_job_id()
    record: dict[str, object] = {
        "ts": int(time.time()),
        "harness": HARNESS_DEVIN,
        "tool": intent.tool,
        "topic": topic,
        "status": "queued",
        "priority": priority,
        "job_id": job_id,
    }
    if acceptance:
        record["acceptance"] = acceptance
    sha = _repo_sha_hint(cfg)
    if sha:
        record["repo_sha_hint"] = sha
    _append_jsonl(cfg.devin_queue_path, record)
    tags = [
        ["acp_tool", intent.tool],
        ["harness", HARNESS_DEVIN],
        ["status", "queued"],
        ["ticket", str(record["ts"])],
    ]
    if priority != "normal":
        tags.append(["priority", priority])
    summary = f"queued for Devin: {topic[:120]}"
    if acceptance:
        summary += f" | acceptance: {acceptance[:60]}"
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        summary,
        tags,
        job_id=job_id,
    )


TOOL_IMPLS: dict[str, Callable[[Intent, GatewayConfig], ToolResult]] = {
    TOOL_RUN_PYTEST: _tool_run_pytest,
    TOOL_INVARIANT_GATE: _tool_invariant_gate,
    TOOL_RIG_STATUS: _tool_rig_status,
    TOOL_SESSION_SUMMARY: _tool_session_summary,
    TOOL_CEREMONY_STEPS: _tool_ceremony_steps,
    TOOL_HEALTH_CHECK: _tool_health_check,
    TOOL_LIST_FAILING_TESTS: _tool_list_failing_tests,
    TOOL_REPO_HEALTH: _tool_repo_health,
    TOOL_SHOW_WP_STATUS: _tool_show_wp_status,
    TOOL_PLAN: _tool_plan,
    TOOL_CONFIRM_PLAN: _tool_confirm_plan,
    TOOL_DIAGNOSE_STATUS: _tool_diagnose_status,
    TOOL_GET_JOB_STATUS: _tool_get_job_status,
    TOOL_CHALLENGE_JOB: _tool_challenge_job,
    TOOL_DEEP_DIAGNOSE: _tool_deep_diagnose,
    TOOL_STREAM_SEAT_STATUS: _tool_stream_seat_status,
    TOOL_STREAM_SEAT_SUMMARY: _tool_stream_seat_summary,
    TOOL_STREAM_SEAT_FLAG: _tool_stream_seat_flag,
    TOOL_STREAM_VERIFY_POINTER: _tool_stream_verify_pointer,
    TOOL_ORGANIZER_PILOT: _tool_organizer_pilot,
}


def execute(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """Execute an allow-listed intent. Anything else is refused here too."""
    if intent.tool not in ALLOWED_TOOLS or intent.tool not in TOOL_IMPLS:
        return ToolResult(
            intent.tool, intent.harness, False, f"rejected: {intent.tool} is not allow-listed"
        )
    if cfg.dry_run:
        return ToolResult(
            intent.tool,
            intent.harness,
            True,
            f"dry-run: would execute {intent.tool} on {intent.harness}",
            [["acp_tool", intent.tool], ["dry_run", "true"]],
        )
    return TOOL_IMPLS[intent.tool](intent, cfg)


# --- Reply formatting --------------------------------------------------------

def scrub(text: str) -> str:
    """Strip secret-shaped substrings from anything about to be published."""
    for pattern, replacement in _SCRUB_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def format_reply(result: ToolResult, cfg: GatewayConfig) -> tuple[str, list[list[str]]]:
    """Build the (content, tags) pair for the #rig-ops reply."""
    body = scrub(" ".join(result.summary.split()))
    # SAP-1: surface the job_id in the digest when it fits.
    if result.job_id:
        job_part = f" | job: {result.job_id}"
        if len(body) + len(job_part) <= cfg.max_reply_chars:
            body += job_part
    limit = max(cfg.max_reply_chars, 32)
    if len(body) > limit:
        body = body[: limit - 1].rstrip() + "…"
    tags = [["qortroller", "1"], ["acp", "1"], ["harness", result.harness]]
    for tag in result.tags:
        if tag and tag[0] not in ("h",):
            tags.append([str(part) for part in tag])
    if result.job_id:
        tags.append(["job", result.job_id])
    return f"[{result.harness}] {body}", tags


def rejection_reply(rejection: Rejection) -> str:
    if rejection.reason == REJECT_BANNED:
        return "rejected: outside the ACP allow-list (no shell, chain, or raw-substrate tools)"
    if rejection.reason == REJECT_UNAUTHORIZED:
        return "rejected: operator allow-list"
    if rejection.reason == REJECT_BAD_TARGET:
        return f"rejected: {rejection.detail}"
    return "rejected: unknown command — try status | invariant | health | failing | repo health | wp <name> | plan <goal> | confirm plan <id> | job status <id> | diagnose status | ceremony | session | pytest <path>"


# --- Audit trail (local only, never on Nostr) --------------------------------

def _append_jsonl(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"[!] audit write failed: {exc}", file=sys.stderr)


def audit(cfg: GatewayConfig, record: dict) -> None:
    record = {"ts": int(time.time()), **record}
    _append_jsonl(cfg.audit_log_path, {k: scrub(str(v)) if isinstance(v, str) else v
                                       for k, v in record.items()})


# --- Message handling --------------------------------------------------------

def handle_message(
    pubkey: str, content: str, cfg: GatewayConfig
) -> Optional[tuple[str, list[list[str]]]]:
    """Full gateway pipeline for one channel message.

    Returns the (content, tags) reply to publish, or None to stay silent.
    """
    parsed = parse_mention(content, cfg)
    if parsed is None:
        return None
    if isinstance(parsed, Rejection):
        audit(cfg, {"pubkey": pubkey, "rejected": parsed.reason, "detail": parsed.detail})
        return rejection_reply(parsed), [["qortroller", "1"], ["acp", "1"], ["rejected", parsed.reason]]
    if not authorize(pubkey, cfg):
        audit(cfg, {"pubkey": pubkey, "rejected": REJECT_UNAUTHORIZED, "tool": parsed.tool})
        return (
            rejection_reply(Rejection(REJECT_UNAUTHORIZED)),
            [["qortroller", "1"], ["acp", "1"], ["rejected", REJECT_UNAUTHORIZED]],
        )

    started = time.time()
    result = execute(parsed, cfg)
    reply, tags = format_reply(result, cfg)
    audit_record: dict[str, object] = {
        "pubkey": pubkey,
        "tool": parsed.tool,
        "harness": parsed.harness,
        "args": parsed.args,
        "ok": result.ok,
        "duration_s": round(time.time() - started, 3),
        "reply": reply,
    }
    if result.job_id:
        audit_record["job_id"] = result.job_id
    audit(cfg, audit_record)
    return reply, tags


# --- Runtime loop (publishes through the Phase 1-3 bot's helper) -------------

def _publish(cfg: GatewayConfig, content: str, tags: list[list[str]]) -> None:
    bot_cfg = bot._load_config()
    channel = cfg.rig_ops_channel or bot_cfg.channel_ids[0]
    result = bot._publish_event(bot_cfg, channel, content, tags)
    if result:
        print(f"[*] replied: {result.get('event_id', '?')}", file=sys.stderr)


def run_once(cfg: GatewayConfig, since_ts: int) -> int:
    """Poll #rig-ops once, handle every addressed message, return the new cursor."""
    bot_cfg = bot._load_config()
    if cfg.rig_ops_channel:
        bot_cfg = replace(bot_cfg, channel_ids=[cfg.rig_ops_channel])
    now = int(time.time())
    for msg in bot._poll_commands(bot_cfg, since_ts, prefixes=(cfg.bot_handle,)):
        reply = handle_message(msg.get("pubkey", ""), msg.get("content", ""), cfg)
        if reply is None:
            continue
        content, tags = reply
        print(f"[*] {msg.get('pubkey', '')[:8]}… → {content}", file=sys.stderr)
        _publish(cfg, content, tags)
    return now


def preflight(cfg: GatewayConfig) -> list[tuple[bool, str, str]]:
    """Operator-local readiness check for the §1 acceptance run.

    Returns `(required, label, detail)` rows. Reads configuration presence only — never a key
    value, never the relay, never the chain. A False row on a required check means the live
    acceptance run would not behave as documented.
    """
    rows: list[tuple[bool, str, str]] = []

    rows.append(
        (
            bool(cfg.operator_pubkeys),
            "ACP_OPERATOR_PUBKEYS",
            f"{len(cfg.operator_pubkeys)} operator pubkey(s)"
            if cfg.operator_pubkeys
            else "empty — fail-closed, every command would be rejected",
        )
    )
    rows.append(
        (
            bool(cfg.rig_ops_channel),
            "#rig-ops channel",
            cfg.rig_ops_channel or "set ACP_RIG_OPS_CHANNEL_ID or BUZZ_CHANNEL_IDS",
        )
    )
    rows.append(
        (
            bool(os.environ.get("BUZZ_PRIVATE_KEY")),
            "BUZZ_PRIVATE_KEY",
            "present in env" if os.environ.get("BUZZ_PRIVATE_KEY") else "absent — the bot cannot sign",
        )
    )

    helper = os.environ.get("BUZZ_HELPER_PATH") or getattr(bot, "BUZZ_HELPER_PATH", "")
    helper_ok = bool(helper) and (Path(helper).exists() or shutil.which(str(helper)) is not None)
    rows.append((helper_ok, "publish helper", str(helper) if helper else "BUZZ_HELPER_PATH unset"))

    try:
        cfg.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with cfg.audit_log_path.open("a", encoding="utf-8"):
            pass
        rows.append((True, "audit log", str(cfg.audit_log_path)))
    except OSError as exc:
        rows.append((False, "audit log", f"{cfg.audit_log_path}: {exc}"))

    health = _tool_health_check(Intent(tool=TOOL_HEALTH_CHECK), cfg)
    rows.append((health.ok, "local tool surface", health.summary))

    return rows


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cfg = load_config()

    # Operator readiness check for the addendum §1 acceptance run. Publishes nothing.
    if argv and argv[0] == "--preflight":
        rows = preflight(cfg)
        for ok, label, detail in rows:
            print(f"  [{'ok' if ok else 'FAIL'}] {label}: {detail}")
        print(f"  [--] dry-run: {'on — replies are printed, not published' if cfg.dry_run else 'off'}")
        failed = [label for ok, label, _ in rows if not ok]
        if failed:
            print(f"\npreflight FAILED: {', '.join(failed)}")
            return 1
        print(
            "\npreflight OK. Acceptance run:\n"
            "  1. ACP_DRY_RUN=1 python scripts/qortroller_acp_gateway.py   (watch, publish nothing)\n"
            f"  2. post in #rig-ops: {cfg.bot_handle} run pytest bridge/tests/test_retina_visual_oracle.py\n"
            f"  3. post in #rig-ops: {cfg.bot_handle} invariant status | {cfg.bot_handle} health\n"
            f"  4. post in #rig-ops: {cfg.bot_handle} devin diagnose <topic>\n"
            "  5. confirm each reply is a digest — no secrets, no raw substrate, no chain call."
        )
        return 0

    # One-shot local evaluation: `python scripts/qortroller_acp_gateway.py --eval "@EA health"`
    if argv and argv[0] == "--eval":
        if len(argv) < 2:
            print('usage: --eval "@EA <command>" [pubkey]', file=sys.stderr)
            return 1
        pubkey = argv[2] if len(argv) > 2 else (cfg.operator_pubkeys[0] if cfg.operator_pubkeys else "")
        reply = handle_message(pubkey, argv[1], cfg)
        if reply is None:
            print("(silent — message does not address the bot)")
            return 0
        print(reply[0])
        return 0

    if not cfg.operator_pubkeys:
        print(
            "[!] ACP_OPERATOR_PUBKEYS is empty — the gateway is fail-closed and will "
            "reject every command. Set it to the operator pubkey(s) before running.",
            file=sys.stderr,
        )
    print(f"[*] ACP gateway — handle {cfg.bot_handle}, channel {cfg.rig_ops_channel[:8] or '?'}…", file=sys.stderr)
    print(f"[*] harnesses: {HARNESS_GROK} (primary) / {HARNESS_DEVIN} (heavy)", file=sys.stderr)
    print(f"[*] audit log: {cfg.audit_log_path}", file=sys.stderr)

    interval = float(os.environ.get("ACP_POLL_INTERVAL", "10"))
    cursor = int(time.time())
    try:
        while True:
            cursor = run_once(cfg, cursor)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[*] shutting down", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
