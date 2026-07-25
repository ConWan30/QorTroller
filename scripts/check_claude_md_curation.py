#!/usr/bin/env python3
"""scripts/check_claude_md_curation.py

Thin CLI wrapper around vapi_bridge.mythos_variants.mythos_claude_md_curation.

Usage:
    python scripts/check_claude_md_curation.py            # report-only (default)
    python scripts/check_claude_md_curation.py --strict    # exit 1 on any finding

Exit codes:
    0 — no findings (healthy) OR --strict not set and findings found (report-only)
    1 --strict set AND at least one finding
    2 — could not run the variant (import error / IO error)

This exists so CI can gate CLAUDE.md size drift without standing up the
vapi-mcp MCP server. The variant itself is unchanged — this script just
calls the same function the MCP tool calls, prints findings, and translates
report-vs-strict mode into an exit code.

Default thresholds (--target-chars 60000, --warn-chars 100000) match the
existing curation contract; the OVERSIZE finding fires above warn_chars and
the OVER_TARGET finding (added 2026-07-25) fires between target and warn.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


async def _run(target_chars: int, warn_chars: int, stale_days: int) -> list:
    sys.path.insert(0, str(REPO_ROOT / "bridge"))
    # Local import after path insert; do not move to module top.
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    return await mythos_claude_md_curation(
        repo_root=REPO_ROOT,
        target_chars=target_chars,
        warn_chars=warn_chars,
        stale_days_threshold=stale_days,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the mythos_claude_md_curation variant as a CI gate."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any finding fires (default: report-only, exit 0).",
    )
    parser.add_argument("--target-chars", type=int, default=60_000)
    parser.add_argument("--warn-chars", type=int, default=100_000)
    parser.add_argument("--stale-days", type=int, default=30)
    args = parser.parse_args()

    try:
        findings = asyncio.run(
            _run(args.target_chars, args.warn_chars, args.stale_days)
        )
    except Exception as exc:
        print(f"[claude_md_curation] ERROR: {exc}", file=sys.stderr)
        return 2

    if not findings:
        print("[claude_md_curation] PASS — 0 findings.")
        return 0

    print(f"[claude_md_curation] {len(findings)} finding(s):")
    for f in findings:
        print(f"  [{f.severity}] {f.description}")
        if f.file_path:
            loc = f.file_path
            if f.line_number:
                loc += f":{f.line_number}"
            print(f"      at: {loc}")
        if f.recommended_fix:
            print(f"      fix: {f.recommended_fix}")

    if args.strict:
        print(
            f"\n[claude_md_curation] FAIL ({len(findings)} finding(s), --strict)",
            file=sys.stderr,
        )
        return 1
    print(f"\n[claude_md_curation] {len(findings)} finding(s) (report-only).")
    return 0


if __name__ == "__main__":
    raise sys.exit(main())
