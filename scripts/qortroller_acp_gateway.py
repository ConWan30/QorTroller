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
TOOL_DEEP_DIAGNOSE = "deep_diagnose"

ALLOWED_TOOLS = (
    TOOL_RUN_PYTEST,
    TOOL_INVARIANT_GATE,
    TOOL_RIG_STATUS,
    TOOL_SESSION_SUMMARY,
    TOOL_CEREMONY_STEPS,
    TOOL_HEALTH_CHECK,
    TOOL_DEEP_DIAGNOSE,
)

# Tools Devin owns regardless of phrasing.
DEVIN_ONLY_TOOLS = (TOOL_DEEP_DIAGNOSE,)
# Tools that stay on Grok Build even if the operator says "devin" — routing a
# read-only status call to the heavy harness buys nothing.
GROK_ONLY_TOOLS = (TOOL_RIG_STATUS, TOOL_CEREMONY_STEPS, TOOL_HEALTH_CHECK)

BOT_HANDLE = os.environ.get("ACP_BOT_HANDLE", "@EA")

# Where a pytest target may live. Anything else is rejected.
PYTEST_ROOTS = ("bridge/tests", "sdk/tests", "tests", "autoresearch/tests")

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

    m = re.match(r"^(?:deep\s+)?diagnose\s+(.+)$", command, re.I)
    if m:
        topic = m.group(1).strip()
        return Intent(TOOL_DEEP_DIAGNOSE, {"topic": topic[:200]})

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


def _tool_deep_diagnose(intent: Intent, cfg: GatewayConfig) -> ToolResult:
    """Queue a Devin hand-off. The gateway never impersonates the harness."""
    topic = intent.args.get("topic", "")
    record = {
        "ts": int(time.time()),
        "harness": HARNESS_DEVIN,
        "tool": intent.tool,
        "topic": topic,
        "status": "queued",
    }
    _append_jsonl(cfg.devin_queue_path, record)
    return ToolResult(
        intent.tool,
        intent.harness,
        True,
        f"queued for Devin: {topic[:120]} (operator invokes the harness; no result yet)",
        [["acp_tool", intent.tool], ["harness", HARNESS_DEVIN], ["status", "queued"]],
    )


TOOL_IMPLS: dict[str, Callable[[Intent, GatewayConfig], ToolResult]] = {
    TOOL_RUN_PYTEST: _tool_run_pytest,
    TOOL_INVARIANT_GATE: _tool_invariant_gate,
    TOOL_RIG_STATUS: _tool_rig_status,
    TOOL_SESSION_SUMMARY: _tool_session_summary,
    TOOL_CEREMONY_STEPS: _tool_ceremony_steps,
    TOOL_HEALTH_CHECK: _tool_health_check,
    TOOL_DEEP_DIAGNOSE: _tool_deep_diagnose,
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
    limit = max(cfg.max_reply_chars, 32)
    if len(body) > limit:
        body = body[: limit - 1].rstrip() + "…"
    tags = [["qortroller", "1"], ["acp", "1"], ["harness", result.harness]]
    for tag in result.tags:
        if tag and tag[0] not in ("h",):
            tags.append([str(part) for part in tag])
    return f"[{result.harness}] {body}", tags


def rejection_reply(rejection: Rejection) -> str:
    if rejection.reason == REJECT_BANNED:
        return "rejected: outside the ACP allow-list (no shell, chain, or raw-substrate tools)"
    if rejection.reason == REJECT_UNAUTHORIZED:
        return "rejected: operator allow-list"
    if rejection.reason == REJECT_BAD_TARGET:
        return f"rejected: {rejection.detail}"
    return "rejected: unknown command — try status | invariant | health | ceremony | session | pytest <path>"


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
    audit(
        cfg,
        {
            "pubkey": pubkey,
            "tool": parsed.tool,
            "harness": parsed.harness,
            "args": parsed.args,
            "ok": result.ok,
            "duration_s": round(time.time() - started, 3),
            "reply": reply,
        },
    )
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
