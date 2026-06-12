"""HWFL-1 Sensor A v0.2 runner — fetches live state and renders drift report.

Network/subprocess boundary lives here per D-HWFL-31; the pure
sensor module never touches the outside world. All errors are
caught and returned as *_fetch_error strings on LiveFetchResult so
the sensor's fail-open posture has explicit evidence to render.

Live sources:
  - Wallet:   eth_getBalance on babel-api.testnet.iotex.io (Cycle 4
              precedent — User-Agent header required to bypass 403).
  - Contract: count of top-level keys in contracts/deployed-addresses.json.
  - Tests:    pytest --collect-only -q for bridge/ + sdk/, plus
              hardhat test count from contracts/test/*.test.js + .ts
              file scan (full hardhat run is too slow + flaky for
              a sensor pass; we count test() / it() occurrences
              statically as a *lower-bound proxy* — D-HWFL-32 noted
              that test-count probing has Windows/subprocess friction).

Usage:
  python scripts/run_sensor_a_live.py                # writes audits/live-state-drift-<UTC-date>.md
  python scripts/run_sensor_a_live.py --cycle 10     # names artifact cycle-10
  python scripts/run_sensor_a_live.py --skip-tests   # skips P-TESTS subprocess
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge.vapi_bridge.sensor_a_live_drift import (  # noqa: E402
    LiveFetchResult,
    assemble_drift_report,
)


WALLET_ADDRESS = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
IOTX_RPC = "https://babel-api.testnet.iotex.io"
DEPLOYED_ADDRESSES = ROOT / "contracts" / "deployed-addresses.json"
HARDHAT_TESTS_DIR = ROOT / "contracts" / "test"
BRIDGE_TESTS_DIR = ROOT / "bridge" / "tests"
SDK_TESTS_DIR = ROOT / "sdk" / "tests"
CLAUDE_MD = ROOT / "CLAUDE.md"


def fetch_wallet_balance() -> Tuple[Optional[float], Optional[str]]:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [WALLET_ADDRESS, "latest"],
        "id": 1,
    }).encode("utf-8")
    req = urllib.request.Request(
        IOTX_RPC,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "qortroller-sensor-a-live/0.2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return None, f"eth_getBalance HTTP error: {exc!r}"
    try:
        result = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        return None, f"eth_getBalance JSON parse error: {exc!r}"
    if "error" in result:
        return None, f"eth_getBalance RPC error: {result['error']!r}"
    hex_wei = result.get("result")
    if not isinstance(hex_wei, str) or not hex_wei.startswith("0x"):
        return None, f"eth_getBalance unexpected shape: {result!r}"
    try:
        wei = int(hex_wei, 16)
    except ValueError as exc:
        return None, f"eth_getBalance hex parse error: {exc!r}"
    return wei / 1e18, None


def fetch_contract_count() -> Tuple[Optional[int], Optional[str]]:
    try:
        data = json.loads(DEPLOYED_ADDRESSES.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"deployed-addresses.json not found at {DEPLOYED_ADDRESSES}"
    except Exception as exc:  # noqa: BLE001
        return None, f"deployed-addresses.json read/parse error: {exc!r}"
    if not isinstance(data, dict):
        return None, f"deployed-addresses.json unexpected shape (not dict): {type(data).__name__}"
    # Honest count: non-meta keys (no leading underscore) whose value is an
    # addr-shaped string ("0x" + 40 hex). Meta keys (_note, _phaseNNN_status,
    # etc.) are bookkeeping; non-addr values would be config blobs.
    count = sum(
        1 for k, v in data.items()
        if not k.startswith("_")
        and isinstance(v, str)
        and v.startswith("0x")
        and len(v) == 42
    )
    return count, None


_TEST_PATTERN = re.compile(r"^\s*(?:it|test)\s*\(", re.MULTILINE)


def _count_hardhat_tests() -> int:
    total = 0
    for path in HARDHAT_TESTS_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".js", ".ts"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += len(_TEST_PATTERN.findall(text))
    return total


def _count_pytest(tests_dir: Path) -> Tuple[Optional[int], Optional[str]]:
    if not tests_dir.exists():
        return None, f"tests dir not found at {tests_dir}"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(tests_dir)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    out = proc.stdout
    # pytest --collect-only -q ends with a "N tests collected" line
    match = re.search(r"^(\d+) tests? collected", out, re.MULTILINE)
    if match:
        return int(match.group(1)), None
    # Fallback: count nodeids (one per line, excluding blanks/summary)
    nodeids = [ln for ln in out.splitlines() if "::" in ln]
    if nodeids:
        return len(nodeids), None
    return None, f"pytest --collect-only produced no parseable count (exit={proc.returncode})"


def fetch_test_counts(skip_tests: bool) -> Tuple[Optional[Dict[str, int]], Optional[str]]:
    if skip_tests:
        return None, "skipped via --skip-tests"
    bridge_n, bridge_err = _count_pytest(BRIDGE_TESTS_DIR)
    if bridge_err:
        return None, f"bridge: {bridge_err}"
    sdk_n, sdk_err = _count_pytest(SDK_TESTS_DIR)
    if sdk_err:
        return None, f"sdk: {sdk_err}"
    try:
        hardhat_n = _count_hardhat_tests()
    except Exception as exc:  # noqa: BLE001
        return None, f"hardhat scan error: {exc!r}"
    return {"bridge": bridge_n, "sdk": sdk_n, "hardhat": hardhat_n}, None


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="HWFL-1 Sensor A v0.2 live drift runner")
    parser.add_argument("--cycle", type=int, default=None, help="cycle number for artifact filename")
    parser.add_argument("--skip-tests", action="store_true", help="skip P-TESTS subprocess (faster smoke)")
    parser.add_argument("--out", type=Path, default=None, help="explicit output path")
    args = parser.parse_args(argv)

    wallet_balance, wallet_err = fetch_wallet_balance()
    contract_count, contract_err = fetch_contract_count()
    test_counts, test_err = fetch_test_counts(args.skip_tests)

    fetch = LiveFetchResult(
        wallet_balance_iotx=wallet_balance,
        wallet_fetch_error=wallet_err,
        contract_count=contract_count,
        contract_fetch_error=contract_err,
        test_counts=test_counts,
        test_fetch_error=test_err,
    )

    claude_md_text = CLAUDE_MD.read_text(encoding="utf-8")
    report = assemble_drift_report(claude_md_text, fetch)

    if args.out is not None:
        out_path = args.out
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if args.cycle is not None:
            out_path = ROOT / "audits" / f"live-state-drift-cycle-{args.cycle}-{today}.md"
        else:
            out_path = ROOT / "audits" / f"live-state-drift-{today}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.to_markdown(), encoding="utf-8")
    print(report.to_markdown())
    print(f"\n[wrote] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
