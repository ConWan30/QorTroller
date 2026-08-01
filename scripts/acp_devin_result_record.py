#!/usr/bin/env python3
"""Append a Devin result record to `audits/acp_devin_results.jsonl`.

This is an operator/Devin helper, not a Buzz tool. The ACP gateway's
`diagnose status` command reads the file this script appends to.

Usage:
    python scripts/acp_devin_result_record.py \
        --topic "vss seat helper" \
        --pr-url "https://github.com/ConWan30/QorTroller/pull/123" \
        --summary "Fixed race in _poll_eligibility"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Reuse the same scrub logic the gateway uses.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw

RESULTS_PATH = Path(
    os.environ.get("ACP_DEVIN_RESULTS", str(REPO_ROOT / "audits" / "acp_devin_results.jsonl"))
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a Devin result for the EA result bridge.")
    parser.add_argument("--path", type=Path, default=RESULTS_PATH, help="Result JSONL path")
    parser.add_argument("--topic", required=True, help="Topic from the original diagnose queue")
    parser.add_argument("--pr-url", default="", help="Pull request URL")
    parser.add_argument("--summary", default="", help="One-line summary")
    parser.add_argument("--status", default="done", choices=["done", "deferred", "aborted"])
    parser.add_argument("--job-id", default="", help="SAP job_id from queue or plan")
    args = parser.parse_args(argv)

    record = {
        "ts": int(__import__("time").time()),
        "topic": gw.scrub(args.topic[:200]),
        "status": args.status,
        "pr_url": gw.scrub(args.pr_url[:200]),
        "summary": gw.scrub(args.summary[:500]),
    }
    if args.job_id:
        record["job_id"] = gw.scrub(args.job_id[:64])
    args.path.parent.mkdir(parents=True, exist_ok=True)
    with args.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"recorded: {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
