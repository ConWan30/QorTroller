"""Phase 235.x-STABILITY-3 polling probe.

Mimics WIF-064/065 baseline polling load:
  - /health                       every 1s
  - /bridge/capture-health        every 3s
  - /bridge/grind-chain-status    every 5s

Logs every poll outcome (status, latency_ms, body_excerpt) as JSONL so the
bisection-correlation step can detect timeout windows that line up with
LOOP STARVATION warnings emitted by the bridge.

Stops when the duration elapses or SIGTERM is received.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _poll_once(url: str, timeout: float) -> dict:
    started = time.monotonic()
    started_ns = time.time_ns()
    out = {
        "ts_ns": started_ns,
        "url": url,
        "status": None,
        "latency_ms": None,
        "error": None,
    }
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            out["status"] = resp.status
            out["latency_ms"] = round((time.monotonic() - started) * 1000.0, 2)
            out["body_excerpt"] = body[:120]
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["latency_ms"] = round((time.monotonic() - started) * 1000.0, 2)
        out["error"] = f"HTTPError: {e.reason}"
    except Exception as e:  # noqa: BLE001 — probe must never crash
        out["latency_ms"] = round((time.monotonic() - started) * 1000.0, 2)
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:8080")
    p.add_argument("--duration-s", type=float, default=1800.0)
    p.add_argument("--out", required=True, help="JSONL output path")
    p.add_argument("--timeout-s", type=float, default=10.0)
    args = p.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    endpoints = [
        ("/health", 1.0),
        ("/bridge/capture-health", 3.0),
        ("/bridge/grind-chain-status", 5.0),
    ]
    next_poll = {ep: 0.0 for ep, _ in endpoints}

    started = time.monotonic()
    deadline = started + args.duration_s

    sys.stderr.write(
        f"[probe] start host={args.host} duration={args.duration_s}s out={out_path}\n"
    )
    sys.stderr.flush()

    n_polls = 0
    n_errors = 0
    n_slow = 0

    with open(out_path, "w", encoding="utf-8") as fh:
        # Header line so reader knows probe parameters
        fh.write(json.dumps({
            "_kind": "header",
            "host": args.host,
            "duration_s": args.duration_s,
            "endpoints": [{"path": p, "interval_s": i} for p, i in endpoints],
            "started_ts_ns": time.time_ns(),
        }) + "\n")
        fh.flush()

        while True:
            now = time.monotonic()
            if now >= deadline:
                break
            for path, interval in endpoints:
                if now >= next_poll[path]:
                    url = f"{args.host}{path}"
                    rec = _poll_once(url, args.timeout_s)
                    fh.write(json.dumps(rec) + "\n")
                    n_polls += 1
                    if rec["error"] is not None:
                        n_errors += 1
                    elif rec["latency_ms"] is not None and rec["latency_ms"] > 1000.0:
                        n_slow += 1
                    next_poll[path] = now + interval
            fh.flush()
            time.sleep(0.2)  # 5 Hz outer loop

        # Footer summary
        fh.write(json.dumps({
            "_kind": "footer",
            "ended_ts_ns": time.time_ns(),
            "n_polls": n_polls,
            "n_errors": n_errors,
            "n_slow_gt_1s": n_slow,
            "elapsed_s": round(time.monotonic() - started, 1),
        }) + "\n")

    sys.stderr.write(
        f"[probe] done polls={n_polls} errors={n_errors} slow_gt_1s={n_slow}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
