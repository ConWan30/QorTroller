#!/usr/bin/env python3
"""Tiny Devin queue watcher (EA-ACP-1 optional companion).

Reads `audits/acp_devin_queue.jsonl` and prints the most recent structured
hand-off records for the operator or a Devin session. Never publishes to Buzz.

Usage:
    python scripts/acp_devin_queue_watch.py --limit 5
    python scripts/acp_devin_queue_watch.py --follow --interval 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVIN_QUEUE_PATH = Path(
    os.environ.get("ACP_DEVIN_QUEUE", str(REPO_ROOT / "audits" / "acp_devin_queue.jsonl"))
)


def _read_rows(path: Path) -> list[dict]:
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


def _format_row(row: dict) -> str:
    ts = row.get("ts", "?")
    topic = row.get("topic", "")
    status = row.get("status", "?")
    priority = row.get("priority", "normal")
    sha = row.get("repo_sha_hint", "")[:12]
    extra = f" priority={priority}"
    if sha:
        extra += f" sha={sha}"
    if row.get("acceptance"):
        extra += f" acceptance={row['acceptance'][:60]}"
    return f"[{ts}] {status}: {topic[:80]}{extra}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch the ACP Devin queue.")
    parser.add_argument("--path", type=Path, default=DEVIN_QUEUE_PATH, help="Queue JSONL path")
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to show")
    parser.add_argument("--follow", action="store_true", help="Tail and print new rows")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in follow mode")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"queue not found: {args.path}", file=sys.stderr)
        return 1

    if args.follow:
        seen = 0
        while True:
            rows = _read_rows(args.path)
            for row in rows[seen:]:
                print(_format_row(row))
            seen = len(rows)
            time.sleep(args.interval)

    rows = _read_rows(args.path)
    for row in rows[-args.limit:]:
        print(_format_row(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
