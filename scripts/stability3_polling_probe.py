"""Phase 235.x-STABILITY-3 polling probe (PROBE-FIX 2026-05-08).

Mimics WIF-064/065 baseline polling load:
  - /health                                    every 1s   (no auth)
  - /operator/bridge/capture-health            every 3s   (x-api-key required)
  - /operator/bridge/grind-chain-status        every 5s   (x-api-key required)

Phase 235.x-STABILITY-3-PROBE-FIX corrections:
  - Path doubled-prefix per WIF-061 (operator app mounted at /operator;
    routes inside it declared at /bridge/X → real URL /operator/bridge/X)
  - x-api-key header sourced from OPERATOR_API_KEY env / bridge/.env
  - Fail-fast self-test: every configured endpoint must return non-404
    within FAIL_FAST_DEADLINE_S=10s, otherwise abort before main load
    starts. Without this, a 30-min run can silently waste itself on a
    50% probe error rate as it did 2026-05-08T22:32:09Z (first run).

Logs every poll outcome (status, latency_ms, body_excerpt) as JSONL so the
bisection-correlation step can detect timeout windows that line up with
LOOP STARVATION warnings emitted by the bridge.

Stops when the duration elapses or SIGTERM is received.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

FAIL_FAST_DEADLINE_S = 30.0  # Phase 235.x-STABILITY-3 — boot+settle window
                              # is empirically up to ~30s under real-controller
                              # load. Keep below probe.timeout_s × 3.


def _read_env_file(path: Path) -> dict:
    """Parse KEY=VALUE lines from a .env file. No external dep."""
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _resolve_api_key(explicit: Optional[str]) -> str:
    """Resolve operator API key from explicit arg, env, or bridge/.env.

    Returns empty string when no key found (caller handles fail-fast)."""
    if explicit:
        return explicit
    env_key = os.environ.get("OPERATOR_API_KEY", "").strip()
    if env_key:
        return env_key
    repo_root = Path(__file__).resolve().parent.parent
    parsed = _read_env_file(repo_root / "bridge" / ".env")
    return parsed.get("OPERATOR_API_KEY", "").strip()


def _poll_once(url: str, timeout: float, headers: Optional[dict] = None) -> dict:
    started = time.monotonic()
    started_ns = time.time_ns()
    out = {
        "ts_ns": started_ns,
        "url": url,
        "status": None,
        "latency_ms": None,
        "error": None,
    }
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def _self_test(host: str, endpoints: list, headers: dict, timeout: float) -> tuple[bool, list]:
    """Verify every endpoint is REACHABLE (not 404/401/403) — slow-but-alive
    counts as OK since slowness is the signal the main load is meant to
    measure.

    Returns (all_ok, per_endpoint_results). per_endpoint_results is a list
    of dicts with keys path/status/error suitable for inclusion in JSONL
    header for audit trail.

    Fail conditions:
      - 404 (wrong path; won't recover)
      - 401/403 (auth missing/wrong; won't recover without operator action)
      - ConnectionRefused / URLError (bridge not listening)

    Pass conditions (recovery-likely or working):
      - 2xx/3xx response (working)
      - 5xx response (bridge up but erroring; data still useful)
      - asyncio.TimeoutError / socket.timeout (bridge alive but starved —
        EXACTLY what the probe exists to measure)
    """
    deadline = time.monotonic() + FAIL_FAST_DEADLINE_S
    results = []
    all_ok = True
    for path, _ in endpoints:
        url = f"{host}{path}"
        rec = _poll_once(url, timeout, headers if path != "/health" else None)
        status = rec["status"]
        err = rec["error"] or ""

        if status in (404, 401, 403):
            ok = False  # Path or auth is wrong — won't self-correct
        elif status is not None:
            ok = True  # Any other HTTP status (incl 5xx) means bridge IS up
        elif "TimeoutError" in err or "timed out" in err.lower():
            ok = True  # Bridge alive but starved — the signal we want
        elif "URLError" in err or "ConnectionRefused" in err:
            ok = False  # Bridge not listening
        else:
            ok = False  # Unknown failure mode — fail-closed

        results.append({
            "path": path,
            "status": status,
            "error": rec["error"],
            "latency_ms": rec["latency_ms"],
            "ok": ok,
        })
        if not ok:
            all_ok = False
        if time.monotonic() > deadline:
            results.append({"path": "_DEADLINE_EXCEEDED", "ok": False})
            return False, results
    return all_ok, results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:8080")
    p.add_argument("--duration-s", type=float, default=1800.0)
    p.add_argument("--out", required=True, help="JSONL output path")
    p.add_argument("--timeout-s", type=float, default=10.0)
    p.add_argument("--api-key", default=None,
                   help="x-api-key for operator endpoints. Defaults to "
                        "OPERATOR_API_KEY env or bridge/.env entry.")
    p.add_argument("--skip-self-test", action="store_true",
                   help="Skip fail-fast self-test (not recommended)")
    args = p.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    api_key = _resolve_api_key(args.api_key)
    headers = {"x-api-key": api_key} if api_key else {}

    endpoints = [
        ("/health", 1.0),
        ("/operator/bridge/capture-health", 3.0),
        ("/operator/bridge/grind-chain-status", 5.0),
    ]

    sys.stderr.write(
        f"[probe] start host={args.host} duration={args.duration_s}s "
        f"out={out_path} api_key_resolved={'yes' if api_key else 'NO'}\n"
    )
    sys.stderr.flush()

    # PROBE-FIX: fail-fast self-test before main load.
    self_test_results = []
    if not args.skip_self_test:
        ok, self_test_results = _self_test(args.host, endpoints, headers, args.timeout_s)
        if not ok:
            sys.stderr.write(
                f"[probe] SELF_TEST_FAILED. Aborting before main load.\n"
                f"        Results: {json.dumps(self_test_results, indent=2)}\n"
            )
            sys.stderr.flush()
            # Still write a header to out_path so the operator can audit.
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "_kind": "self_test_failure",
                    "host": args.host,
                    "self_test": self_test_results,
                    "started_ts_ns": time.time_ns(),
                }) + "\n")
            return 2

    next_poll = {ep: 0.0 for ep, _ in endpoints}

    started = time.monotonic()
    deadline = started + args.duration_s

    n_polls = 0
    n_errors = 0
    n_slow = 0

    with open(out_path, "w", encoding="utf-8") as fh:
        # Header line: probe params + self-test results
        fh.write(json.dumps({
            "_kind": "header",
            "host": args.host,
            "duration_s": args.duration_s,
            "endpoints": [{"path": p, "interval_s": i} for p, i in endpoints],
            "api_key_resolved": bool(api_key),
            "self_test": self_test_results,
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
                    poll_headers = headers if path != "/health" else None
                    rec = _poll_once(url, args.timeout_s, poll_headers)
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
