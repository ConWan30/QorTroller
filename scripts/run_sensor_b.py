"""HWFL-1 Sensor B one-shot runner.

Two responsibilities — the entire network boundary lives here:
  1. STRUCTURED sources: shell out to `gh pr view` for IIP-64 PR #72.
  2. MANUAL_NARRATIVE sources: read an optional operator-edited JSON
     of pasted narrative snippets via --narratives.

Module `bridge.vapi_bridge.sensor_b_supply_watch` is pure-function; this
runner is the only file with subprocess + I/O surface. That isolates
the prompt-injection blast radius to this one script.

Usage:
    python scripts/run_sensor_b.py                       # Cycle 3, today
    python scripts/run_sensor_b.py --cycle 4 --date 2026-06-20
    python scripts/run_sensor_b.py --narratives ops_notes.json
    python scripts/run_sensor_b.py --stdout              # markdown -> stdout
    python scripts/run_sensor_b.py --no-fetch            # template-only mode
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from bridge.vapi_bridge.sensor_b_supply_watch import (  # noqa: E402
    FetchResult,
    assemble_watch_report,
)


def _fetch_iip64_pr72() -> FetchResult:
    """Fetch IIP-64 PR #72 state via gh CLI. Honest fail: any exception
    becomes a FETCH-ERROR result, never crashes the runner."""
    topic = "S1.iip64-pr72"
    if shutil.which("gh") is None:
        return FetchResult(
            topic_id=topic,
            summary="gh CLI not installed on this host",
            error="gh-not-found",
        )
    try:
        result = subprocess.run(
            [
                "gh", "pr", "view", "72",
                "--repo", "iotexproject/iips",
                "--json", "number,title,state,isDraft,mergedAt,closedAt,updatedAt,headRefName,author,additions,deletions",
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.TimeoutExpired:
        return FetchResult(topic_id=topic, summary="gh fetch timed out after 30s", error="timeout")
    except subprocess.CalledProcessError as exc:
        return FetchResult(
            topic_id=topic,
            summary="gh pr view failed",
            raw_excerpt=(exc.stderr or "")[:400],
            error=f"exit-{exc.returncode}",
        )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(topic_id=topic, summary="gh fetch raised", error=repr(exc))

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return FetchResult(topic_id=topic, summary="gh JSON parse failed", error=str(exc))

    state = data.get("state", "UNKNOWN")
    draft = " (draft)" if data.get("isDraft") else ""
    merged_at = data.get("mergedAt")
    closed_at = data.get("closedAt")
    updated_at = data.get("updatedAt", "")
    author_login = (data.get("author") or {}).get("login", "?")
    head_ref = data.get("headRefName", "?")
    title = data.get("title", "?")

    if merged_at:
        lifecycle = f"MERGED at {merged_at}"
    elif closed_at:
        lifecycle = f"CLOSED at {closed_at} (not merged)"
    else:
        lifecycle = f"{state}{draft}; last updated {updated_at}"

    summary = (
        f"PR #72 '{title}' — {lifecycle}; "
        f"author={author_login}; head={head_ref}; "
        f"+{data.get('additions', 0)}/-{data.get('deletions', 0)} lines"
    )
    raw_excerpt = json.dumps(data, indent=2, sort_keys=True)[:600]
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    return FetchResult(
        topic_id=topic,
        summary=summary,
        raw_excerpt=raw_excerpt,
        fetched_at=fetched_at,
    )


def _load_narratives(path: Path) -> dict[str, FetchResult]:
    """Load operator-edited MANUAL_NARRATIVE notes. JSON shape:
        {
          "_meta": { ... optional, ignored by loader ... },
          "S2.atecc608a-lifecycle": {
              "summary": "...",
              "fetched_at": "2026-06-10T...",
              # Optional VERIFIED-EXTERNAL precondition fields (Sensor B v0.1.1):
              "verified_by":   "operator (Con / ConWan30)",
              "sources":       ["url-or-doc-id-1", "url-or-doc-id-2"],
              "verified_date": "2026-06-10"
          },
          ...
        }
    Missing topics simply land as PENDING-OPERATOR-NOTE in the report.
    Top-level keys starting with `_` (e.g. `_meta`) are ignored — reserved
    for narrative-file metadata that doesn't map to a Sensor B topic.
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, FetchResult] = {}
    for topic_id, payload in data.items():
        if topic_id.startswith("_"):
            continue  # _meta and other reserved meta-keys
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        out[topic_id] = FetchResult(
            topic_id=topic_id,
            summary=payload.get("summary"),
            raw_excerpt=payload.get("raw_excerpt", "")[:600],
            fetched_at=payload.get("fetched_at", ""),
            error=payload.get("error", ""),
            verified_by=payload.get("verified_by", ""),
            sources=[str(s) for s in sources],
            verified_date=payload.get("verified_date", ""),
        )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run HWFL-1 Sensor B — supply/standards watch")
    p.add_argument("--cycle", type=int, default=3)
    p.add_argument("--date", default=_dt.date.today().isoformat())
    p.add_argument("--narratives", type=Path, default=None,
                   help="JSON file with operator-pasted MANUAL_NARRATIVE summaries")
    p.add_argument("--no-fetch", action="store_true",
                   help="Skip STRUCTURED fetches; template-only output")
    p.add_argument("--stdout", action="store_true")
    args = p.parse_args(argv)

    fetched: dict[str, FetchResult] = {}

    if not args.no_fetch:
        iip64 = _fetch_iip64_pr72()
        fetched[iip64.topic_id] = iip64

    if args.narratives:
        fetched.update(_load_narratives(args.narratives))

    report = assemble_watch_report(
        cycle=args.cycle, cycle_date=args.date, fetched=fetched,
    )

    if args.stdout:
        print(report.to_markdown())
        return 0

    out_dir = _REPO_ROOT / "audits"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"hardware-watch-cycle-{args.cycle}-{args.date}.md"
    out_path.write_text(report.to_markdown(), encoding="utf-8")

    counts = report.state_counts()
    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    print(f"Sensor B Cycle {args.cycle}: {len(report.lines)} sources ({summary})")
    print(f"  markdown -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
