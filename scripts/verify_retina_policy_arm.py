#!/usr/bin/env python3
"""Hardware smoke: verify Retina policy auto-arm via /bridge/retina-policy-status.

Usage (bridge running with DualSense Edge USB + DUALSHOCK_ENABLED=true):
  python scripts/verify_retina_policy_arm.py --base-url http://127.0.0.1:8080 --api-key KEY
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Retina DePIN policy arm state")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--expect-armed", action="store_true", default=True)
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/bridge/retina-policy-status"
    req = urllib.request.Request(
        url,
        headers={"x-api-key": args.api_key} if args.api_key else {},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()[:500]}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(body, indent=2))
    armed = bool(body.get("armed"))
    if args.expect_armed and not armed:
        print(
            f"FAIL: expected armed=true, got armed={armed} "
            f"summary={body.get('qualifiers_summary')}",
            file=sys.stderr,
        )
        return 2
    if not args.expect_armed and armed:
        print("FAIL: expected unarmed", file=sys.stderr)
        return 2
    print("PASS: retina policy state matches expectation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
