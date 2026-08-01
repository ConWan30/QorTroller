#!/usr/bin/env python3
"""Build an offline context pack for a Devin session (EA-ACP-5).

This is a read-only, no-secrets script for the operator or Devin to open a
heavy session with the right repo state, queue record, and design docs.

Usage:
    python scripts/acp_devin_context_pack.py --topic "vss seat helper"
    python scripts/acp_devin_context_pack.py --plan-id abc123 --output pack.md
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _queue_path(repo_root: Path) -> Path:
    return Path(
        os.environ.get("ACP_DEVIN_QUEUE", str(repo_root / "audits" / "acp_devin_queue.jsonl"))
    )


def _plans_path(repo_root: Path) -> Path:
    return Path(
        os.environ.get("ACP_PLANS_FILE", str(repo_root / "audits" / "acp_plans.jsonl"))
    )


def _results_path(repo_root: Path) -> Path:
    return Path(
        os.environ.get("ACP_DEVIN_RESULTS", str(repo_root / "audits" / "acp_devin_results.jsonl"))
    )


RELEVANT_DOCS: dict[str, Path] = {
    "acp": REPO_ROOT / "docs" / "design" / "buzz-ea-acp-harness-integration-v0.md",
    "gateway runbook": REPO_ROOT / "docs" / "design" / "buzz-phase4-acp-gateway-runbook.md",
    "vss": REPO_ROOT / "docs" / "design" / "buzz-vss-stream-seat-scope-v0.md",
    "agent import proposal": REPO_ROOT / "docs" / "design" / "buzz-ea-agent-import-proposal.md",
}


def _repo_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except Exception:
        pass
    return "unknown"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _find_queue_row(topic: str, repo_root: Path) -> dict | None:
    for row in reversed(_read_jsonl(_queue_path(repo_root))):
        if topic.lower() in str(row.get("topic", "")).lower():
            return row
    return None


def _find_plan(plan_id: str, repo_root: Path) -> dict | None:
    for row in reversed(_read_jsonl(_plans_path(repo_root))):
        if str(row.get("plan_id", "")) == plan_id:
            return row
    return None


def _read_doc_headings(path: Path, limit: int = 8) -> list[str]:
    if not path.is_file():
        return []
    headings: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") or stripped.startswith("## "):
            heading = stripped.lstrip("# ").strip()
            if heading:
                headings.append(heading)
                if len(headings) >= limit:
                    break
    return headings


def build_pack(topic: str, plan_id: str, repo_root: Path) -> str:
    sections: list[str] = ["# Devin Context Pack\n"]

    sections.append(f"## Repo state")
    sections.append(f"- SHA: `{_repo_sha()}`")
    sections.append(f"- Generated: `{int(__import__('time').time())}`")
    sections.append("")

    sections.append("## Relevant design docs")
    for name, path in RELEVANT_DOCS.items():
        headings = _read_doc_headings(path)
        sections.append(f"### {name} — `{path.relative_to(REPO_ROOT).as_posix()}`")
        if headings:
            sections.append("- " + "\n- ".join(headings))
        else:
            sections.append("(no headings or file missing)")
        sections.append("")

    if plan_id:
        plan = _find_plan(plan_id, repo_root)
        sections.append("## Matching plan")
        if plan:
            sections.append(f"```json\n{json.dumps(plan, indent=2)}\n```")
        else:
            sections.append(f"No plan found for id `{plan_id}`.")
        sections.append("")

    if topic:
        row = _find_queue_row(topic, repo_root)
        sections.append("## Matching Devin queue row")
        if row:
            sections.append(f"```json\n{json.dumps(row, indent=2)}\n```")
        else:
            sections.append(f"No queue row found matching topic `{topic}`.")
        sections.append("")

    sections.append("## Result history (last 3)")
    results = _read_jsonl(_results_path(repo_root))[-3:]
    if results:
        for r in reversed(results):
            sections.append(f"- `{r.get('status')}` {r.get('topic')} — {r.get('pr_url')} — {r.get('summary', '')[:80]}")
    else:
        sections.append("No result records yet.")
    sections.append("")

    sections.append("## Verification commands")
    sections.append("```powershell")
    sections.append("python -m pytest bridge/tests/test_qortroller_acp_gateway.py -q")
    sections.append("python -m pytest bridge/tests/test_qortroller_acp_gateway.py bridge/tests/test_vss_*.py -q")
    sections.append("python scripts/vapi_invariant_gate.py --report")
    sections.append("```")
    sections.append("")

    return "\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Devin context pack.")
    parser.add_argument("--topic", default="", help="Topic to match in the queue")
    parser.add_argument("--plan-id", default="", help="Plan id to include")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repo root for queue/plans/results")
    parser.add_argument("--output", type=Path, default=None, help="Output file (default: stdout)")
    args = parser.parse_args(argv)

    if not args.topic and not args.plan_id:
        parser.error("Provide --topic and/or --plan-id")

    pack = build_pack(args.topic, args.plan_id, args.repo_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(pack, encoding="utf-8")
        print(f"context pack written: {args.output}")
    else:
        print(pack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
