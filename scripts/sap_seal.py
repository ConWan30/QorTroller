#!/usr/bin/env python3
"""Local SAP seal log — operator-only, no Buzz publish by default.

Usage:
    python scripts/sap_seal.py --job-id sap_abc123 --accept \
        --ref https://github.com/ConWan30/QorTroller/pull/125 \
        --note "reviewed and merged"

Record shape (appended to audits/acp_sap_seals.jsonl):
    {
      "ts": 0,
      "job_id": "sap_…",
      "verdict": "accept",
      "ref": "https://github.com/…/pull/N",
      "note": "optional",
      "operator": "local"
    }

The seal is not a protocol/population proof. It is a local operator record.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw

SEALS_PATH = Path(
    os.environ.get("ACP_SAP_SEALS", str(REPO_ROOT / "audits" / "acp_sap_seals.jsonl"))
)


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


QUEUE_PATH = Path(
    os.environ.get("ACP_DEVIN_QUEUE", str(REPO_ROOT / "audits" / "acp_devin_queue.jsonl"))
)
PLANS_PATH = Path(
    os.environ.get("ACP_PLANS_FILE", str(REPO_ROOT / "audits" / "acp_plans.jsonl"))
)
RESULTS_PATH = Path(
    os.environ.get("ACP_DEVIN_RESULTS", str(REPO_ROOT / "audits" / "acp_devin_results.jsonl"))
)


def _known_job_id(job_id: str) -> bool:
    """A job_id is known if it appears in queue, plans, or results."""
    queue = _read_jsonl(QUEUE_PATH)
    plans = _read_jsonl(PLANS_PATH)
    results = _read_jsonl(RESULTS_PATH)
    for row in (*queue, *plans, *results):
        if str(row.get("job_id", "")) == job_id:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a local SAP seal record.")
    parser.add_argument("--path", type=Path, default=SEALS_PATH, help="Seals JSONL path")
    parser.add_argument("--job-id", required=True, help="SAP job_id from queue/plan/result")
    verdict = parser.add_mutually_exclusive_group(required=True)
    verdict.add_argument("--accept", action="store_true", help="Seal as accepted")
    verdict.add_argument("--reject", action="store_true", help="Seal as rejected")
    verdict.add_argument("--hold", action="store_true", help="Seal as on hold")
    parser.add_argument("--ref", default="", help="PR URL, SHA, or other reference")
    parser.add_argument("--note", default="", help="Optional operator note")
    parser.add_argument("--operator", default="local", help="Operator identifier")
    parser.add_argument("--force", action="store_true", help="Allow unknown job_id")
    args = parser.parse_args(argv)

    job_id = args.job_id.strip()
    if not job_id.startswith("sap_"):
        print(f"[!] job_id must start with 'sap_': {job_id}", file=sys.stderr)
        return 2

    if not args.force and not _known_job_id(job_id):
        print(f"[!] unknown job_id: {job_id} (use --force to seal anyway)", file=sys.stderr)
        return 1

    if args.accept:
        verdict_str = "accept"
    elif args.reject:
        verdict_str = "reject"
    else:
        verdict_str = "hold"

    record: dict[str, object] = {
        "ts": int(time.time()),
        "job_id": job_id,
        "verdict": verdict_str,
        "ref": gw.scrub(args.ref[:200]),
        "note": gw.scrub(args.note[:500]),
        "operator": gw.scrub(args.operator[:64]),
    }
    args.path.parent.mkdir(parents=True, exist_ok=True)
    with args.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"sealed: {job_id} = {verdict_str} -> {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
