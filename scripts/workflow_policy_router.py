"""Workflow Policy Router (WPR-1) for QorTroller Buzz integration.

Implements the deterministic policy layer from
`docs/design/buzz-workflow-policy-routers-v0.md`:

    Trigger → Policy table → Command template → ACP gateway → digest

- Loads a JSON catalog of workflow policies.
- Evaluates a policy by id (CLI or in-process).
- Enforces enabled, cooldown, and max_per_hour limits.
- Calls `qortroller_acp_gateway.handle_message` in-process or POSTs to a
  webhook URL.
- Writes audit state to `audits/workflow_router_state.jsonl`.

No natural-language interpretation. No new Buzz identity. No chain spend.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw  # noqa: E402

DEFAULT_POLICIES_PATH = REPO_ROOT / "config" / "buzz_workflow_policies.json"
DEFAULT_STATE_PATH = REPO_ROOT / "audits" / "workflow_router_state.jsonl"
DEFAULT_WEBHOOK_URL = os.environ.get("WORKFLOW_WEBHOOK_URL", "").strip()


@dataclass
class Policy:
    id: str
    enabled: bool
    trigger: dict
    match: dict
    action: dict
    limits: dict
    publish: dict
    notes: str = ""


@dataclass
class PolicyRun:
    policy_id: str
    ok: bool
    skipped: bool
    content: str
    tags: list[list[str]]
    tool: str
    harness: str
    error: str
    ts: float


class RouterError(Exception):
    """Fail-closed router error."""


def _now() -> float:
    return time.time()


def _load_policies(path: Path | str) -> dict[str, Policy]:
    """Load and validate a policy catalog."""
    p = Path(path)
    if not p.is_file():
        raise RouterError(f"policy file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RouterError(f"invalid JSON in {p}: {e}") from e

    if raw.get("version") != 1:
        raise RouterError("only policy version 1 is supported")

    out: dict[str, Policy] = {}
    for row in raw.get("policies", []):
        pid = str(row.get("id", ""))
        if not pid:
            raise RouterError("policy missing id")
        if pid in out:
            raise RouterError(f"duplicate policy id: {pid}")
        action = row.get("action") or {}
        content = str(action.get("content", ""))
        if not content:
            raise RouterError(f"policy {pid}: missing action.content")
        if not _is_allow_listed(content):
            raise RouterError(f"policy {pid}: content is not an @EA mention")
        if _has_banned_pattern(content):
            raise RouterError(f"policy {pid}: content contains banned pattern")
        out[pid] = Policy(
            id=pid,
            enabled=bool(row.get("enabled", False)),
            trigger=dict(row.get("trigger") or {}),
            match=dict(row.get("match") or {}),
            action=action,
            limits=dict(row.get("limits") or {}),
            publish=dict(row.get("publish") or {}),
            notes=str(row.get("notes", "")),
        )
    return out


def _is_allow_listed(content: str) -> bool:
    """An @EA command is the only allowed action surface."""
    lowered = content.strip().lower()
    return lowered.startswith(("@ea ", "@ea")) and len(content) >= 3


def _has_banned_pattern(content: str) -> bool:
    """Reject policy content that names a banned tool surface."""
    for pattern in gw.BANNED_PATTERNS:
        if pattern.search(content):
            return True
    return False


def _read_state(state_path: Path) -> list[dict[str, Any]]:
    """Read audit state lines (newest first)."""
    if not state_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with state_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _append_state(state_path: Path, record: dict[str, Any]) -> None:
    """Append one audit record to the JSONL state file."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _count_runs_in_window(
    state: list[dict[str, Any]], policy_id: str, window_s: float
) -> int:
    """Count non-skipped runs for policy in the last window_s seconds."""
    now = _now()
    return sum(
        1
        for r in state
        if r.get("policy_id") == policy_id
        and r.get("ts", 0) > now - window_s
        and not r.get("skipped", False)
    )


def _last_run_ts(state: list[dict[str, Any]], policy_id: str) -> float:
    """Return the timestamp of the most recent run (including skipped)."""
    for r in state:
        if r.get("policy_id") == policy_id:
            return float(r.get("ts", 0))
    return 0.0


def _check_limits(policy: Policy, state: list[dict[str, Any]]) -> Optional[str]:
    """Return a skip reason if limits block the run, else None."""
    if not policy.enabled:
        return "disabled"
    limits = policy.limits
    if not limits:
        return None
    cooldown = float(limits.get("cooldown_s", 0))
    if cooldown > 0:
        last = _last_run_ts(state, policy.id)
        if _now() - last < cooldown:
            return f"cooldown ({cooldown}s)"
    max_per_hour = limits.get("max_per_hour")
    if max_per_hour is not None:
        count = _count_runs_in_window(state, policy.id, 3600.0)
        if count >= int(max_per_hour):
            return f"max_per_hour ({max_per_hour}) reached"
    return None


def _resolve_pubkey(pubkey: str | None, env: bool = True) -> str:
    """Resolve an operator pubkey from arg or env."""
    if pubkey:
        return pubkey.strip()
    if env:
        pubkeys = [
            p.strip()
            for p in os.environ.get("ACP_OPERATOR_PUBKEYS", "").split(",")
            if p.strip()
        ]
        if pubkeys:
            return pubkeys[0]
    return ""


def _run_in_process(policy: Policy, cfg: gw.GatewayConfig, pubkey: str) -> PolicyRun:
    """Execute a policy through the ACP gateway in-process."""
    content = str(policy.action.get("content", ""))
    if policy.action.get("require_operator_pubkey") and not pubkey:
        return PolicyRun(
            policy_id=policy.id,
            ok=False,
            skipped=False,
            content="",
            tags=[],
            tool="",
            harness="",
            error="operator pubkey required but not provided",
            ts=_now(),
        )

    parsed = gw.parse_mention(content, cfg)
    if isinstance(parsed, gw.Rejection):
        return PolicyRun(
            policy_id=policy.id,
            ok=False,
            skipped=False,
            content=gw.rejection_reply(parsed),
            tags=[["qortroller", "1"], ["acp", "1"], ["rejected", parsed.reason]],
            tool="",
            harness="",
            error=parsed.reason,
            ts=_now(),
        )

    reply = gw.handle_message(pubkey or "workflow-router", content, cfg)
    if reply is None:
        return PolicyRun(
            policy_id=policy.id,
            ok=False,
            skipped=False,
            content="",
            tags=[],
            tool="",
            harness="",
            error="handle_message returned None",
            ts=_now(),
        )

    reply_content, tags = reply
    # Infer tool/harness from tags or parsed intent.
    tool = ""
    harness = ""
    for tag in tags:
        if len(tag) >= 2:
            if tag[0] == "acp_tool":
                tool = tag[1]
            elif tag[0] == "harness":
                harness = tag[1]
    return PolicyRun(
        policy_id=policy.id,
        ok="rejected" not in reply_content.lower() and "error" not in reply_content.lower(),
        skipped=False,
        content=reply_content,
        tags=tags,
        tool=tool,
        harness=harness,
        error="",
        ts=_now(),
    )


def _run_webhook(policy: Policy, webhook_url: str, pubkey: str) -> PolicyRun:
    """Execute a policy by POSTing to a local webhook."""
    import urllib.request

    content = str(policy.action.get("content", ""))
    payload = json.dumps({"pubkey": pubkey, "content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else {}
    except Exception as e:  # noqa: BLE001
        return PolicyRun(
            policy_id=policy.id,
            ok=False,
            skipped=False,
            content="",
            tags=[],
            tool="",
            harness="webhook",
            error=repr(e),
            ts=_now(),
        )

    return PolicyRun(
        policy_id=policy.id,
        ok=bool(data.get("ok") or data.get("content")),
        skipped=False,
        content=data.get("content", ""),
        tags=data.get("tags", []),
        tool=data.get("tool", ""),
        harness=data.get("harness", "webhook"),
        error=data.get("error", ""),
        ts=_now(),
    )


def _run_policy(
    policy: Policy,
    *,
    cfg: gw.GatewayConfig,
    state_path: Path,
    dry_run: bool = False,
    webhook_url: str = "",
    pubkey: str = "",
) -> PolicyRun:
    """Run one policy after limits. Returns a PolicyRun and appends state."""
    state = _read_state(state_path)
    skip_reason = _check_limits(policy, state)
    if skip_reason:
        run = PolicyRun(
            policy_id=policy.id,
            ok=True,
            skipped=True,
            content="",
            tags=[["qortroller", "1"], ["workflow", "1"], ["skipped", skip_reason]],
            tool="",
            harness="",
            error=skip_reason,
            ts=_now(),
        )
        _append_state(state_path, _run_to_record(run))
        return run

    if dry_run:
        run = PolicyRun(
            policy_id=policy.id,
            ok=True,
            skipped=False,
            content=str(policy.action.get("content", "")),
            tags=[["qortroller", "1"], ["workflow", "1"], ["dry_run", "true"]],
            tool="",
            harness="dry_run",
            error="",
            ts=_now(),
        )
        _append_state(state_path, _run_to_record(run))
        return run

    if webhook_url:
        run = _run_webhook(policy, webhook_url, pubkey)
    else:
        run = _run_in_process(policy, cfg, pubkey)
    _append_state(state_path, _run_to_record(run))
    return run


def _run_to_record(run: PolicyRun) -> dict[str, Any]:
    return {
        "policy_id": run.policy_id,
        "ok": run.ok,
        "skipped": run.skipped,
        "content": run.content,
        "tags": run.tags,
        "tool": run.tool,
        "harness": run.harness,
        "error": run.error,
        "ts": run.ts,
    }


def run_policy_by_id(
    policy_id: str,
    *,
    policies_path: Path | str = DEFAULT_POLICIES_PATH,
    state_path: Path | str = DEFAULT_STATE_PATH,
    cfg: gw.GatewayConfig | None = None,
    dry_run: bool = False,
    webhook_url: str = "",
    pubkey: str = "",
) -> PolicyRun:
    """High-level helper: load catalog, find policy, run it."""
    catalog = _load_policies(policies_path)
    policy = catalog.get(policy_id)
    if policy is None:
        return PolicyRun(
            policy_id=policy_id,
            ok=False,
            skipped=False,
            content="",
            tags=[],
            tool="",
            harness="",
            error=f"unknown policy id: {policy_id}",
            ts=_now(),
        )
    if cfg is None:
        cfg = gw.load_config()
    return _run_policy(
        policy,
        cfg=cfg,
        state_path=Path(state_path),
        dry_run=dry_run,
        webhook_url=webhook_url,
        pubkey=pubkey,
    )


def list_policies(
    policies_path: Path | str = DEFAULT_POLICIES_PATH,
) -> list[dict[str, Any]]:
    """Return a list of policy rows (metadata only, no action secrets)."""
    catalog = _load_policies(policies_path)
    return [
        {
            "id": p.id,
            "enabled": p.enabled,
            "trigger": p.trigger,
            "limits": p.limits,
            "publish": p.publish,
            "notes": p.notes,
        }
        for p in catalog.values()
    ]


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QorTroller Workflow Policy Router")
    parser.add_argument("--policy-id", default="", help="Policy to run")
    parser.add_argument("--config", default=str(DEFAULT_POLICIES_PATH), help="Policy catalog path")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH), help="State JSONL path")
    parser.add_argument("--pubkey", default="", help="Operator pubkey (or ACP_OPERATOR_PUBKEYS)")
    parser.add_argument("--webhook-url", default=DEFAULT_WEBHOOK_URL, help="POST to webhook instead of in-process")
    parser.add_argument("--dry-run", action="store_true", help="Print command, do not execute")
    parser.add_argument("--list", action="store_true", help="List policies and exit")
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps(list_policies(args.config), indent=2))
        return 0

    pubkey = _resolve_pubkey(args.pubkey)
    cfg = gw.load_config()
    run = run_policy_by_id(
        args.policy_id,
        policies_path=args.config,
        state_path=args.state,
        cfg=cfg,
        dry_run=args.dry_run,
        webhook_url=args.webhook_url,
        pubkey=pubkey,
    )
    print(json.dumps(_run_to_record(run), indent=2, ensure_ascii=False))
    return 0 if (run.ok or run.skipped) else 1


if __name__ == "__main__":
    sys.exit(_main())
