"""HWFL-1 Sensor B v0.2 companion — multi-source URL reachability runner.

Closes F-HWFL-5-1: probes a list of candidate URLs (or a JSON file
mapping topic → urls) via HEAD requests and writes a markdown
reachability report. Operator runs this BEFORE manual vendor-catalog
intel-gathering to route around dead pages.

Network boundary lives here; the pure module never touches the net.

Usage:
  python scripts/probe_vendor_urls.py URL [URL ...] --label s2-atecc608a
  python scripts/probe_vendor_urls.py --urls-file audits/cycle5_urls.json
  python scripts/probe_vendor_urls.py URL --out audits/foo.md --user-agent "..."
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge.vapi_bridge.multi_source_prober import (  # noqa: E402
    ProbeResult,
    probe as probe_urls,
)


DEFAULT_USER_AGENT = "qortroller-hwfl1-prober/0.2 (HEAD-only reachability check)"
DEFAULT_TIMEOUT_S = 15


def make_fetcher(user_agent: str, timeout_s: int):
    def _fetch(url: str) -> ProbeResult:
        start = time.monotonic()
        req = urllib.request.Request(
            url, method="HEAD",
            headers={"User-Agent": user_agent, "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                elapsed = int((time.monotonic() - start) * 1000)
                return ProbeResult(url=url, status=resp.status, elapsed_ms=elapsed)
        except urllib.error.HTTPError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return ProbeResult(url=url, status=exc.code, elapsed_ms=elapsed)
        except urllib.error.URLError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            reason = str(exc.reason)
            if "timed out" in reason.lower() or "timeout" in reason.lower():
                return ProbeResult(url=url, status=None, error=f"timeout after {timeout_s}s: {reason}", elapsed_ms=elapsed)
            return ProbeResult(url=url, status=None, error=f"URLError: {reason}", elapsed_ms=elapsed)
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.monotonic() - start) * 1000)
            return ProbeResult(url=url, status=None, error=f"{type(exc).__name__}: {exc}", elapsed_ms=elapsed)
    return _fetch


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="HWFL-1 multi-source URL reachability probe")
    p.add_argument("urls", nargs="*", help="URLs to probe (HEAD-only)")
    p.add_argument("--urls-file", type=Path, default=None,
                   help="JSON file: either a list of URLs or {label: [urls]} dict")
    p.add_argument("--label", default="ad-hoc",
                   help="Topic label for the report")
    p.add_argument("--out", type=Path, default=None,
                   help="Output markdown path (default: audits/url-reachability-<UTC-date>.md)")
    p.add_argument("--cycle", type=int, default=None,
                   help="Cycle number for filename")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    args = p.parse_args(argv)

    if args.urls_file is not None:
        try:
            data = json.loads(args.urls_file.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"ERROR reading {args.urls_file}: {exc}", file=sys.stderr)
            return 2
        if isinstance(data, list):
            url_groups = {args.label: [str(u) for u in data]}
        elif isinstance(data, dict):
            url_groups = {str(k): [str(u) for u in v] for k, v in data.items() if not str(k).startswith("_")}
        else:
            print(f"ERROR: urls-file must be a list or dict, got {type(data).__name__}", file=sys.stderr)
            return 2
    else:
        if not args.urls:
            p.error("either positional URLs or --urls-file is required")
        url_groups = {args.label: list(args.urls)}

    fetcher = make_fetcher(args.user_agent, args.timeout)
    ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_md: List[str] = []
    for label, urls in url_groups.items():
        report = probe_urls(urls, label, fetcher, ts_iso=ts_iso)
        all_md.append(report.to_markdown())

    md = "\n\n---\n\n".join(all_md)

    if args.out is not None:
        out_path = args.out
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if args.cycle is not None:
            out_path = ROOT / "audits" / f"url-reachability-cycle-{args.cycle}-{today}.md"
        else:
            out_path = ROOT / "audits" / f"url-reachability-{today}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n[wrote] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
