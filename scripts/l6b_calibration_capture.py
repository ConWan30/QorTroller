"""
l6b_calibration_capture.py — Operator monitor for L6B reflex calibration (N toward 50).

Prerequisites (local test env only — see docs/l6b-calibration-test-env.example):
  - bridge/.env: L6B_ENABLED=true (never committed; CI default remains false)
  - Bridge running with DualSense Edge connected via USB (pydualsense path)
  - python scripts/l6_hardware_check.py — all steps PASS

Each completed L6b probe is persisted to l6b_probe_log with reflex_verdict by the
bridge session loop. This script polls the DB and reports N after each new probe.

At N>=50 the script stops and prints the CCO Phase B operator gate checklist
(CCO_PHASE_B_DESIGN_v1.md section 5).

USAGE
-----
  python scripts/l6b_calibration_capture.py --player P1 --game "NCAA Football 26"
  python scripts/l6b_calibration_capture.py --target 50 --interval 5

Desk USB-only (bridge stopped) — operator-fired probes with immediate diagnostics:
  python scripts/l6b_desk_reaction_session.py --player P1 --protocol still
"""

from __future__ import annotations

import argparse
import datetime
import signal
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import requests
except ImportError:
    print("ERROR: pip install requests")
    raise SystemExit(1)

from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.store import Store

BRIDGE_URL = "http://localhost:8080"
POLL_INTERVAL_S = 5
TARGET_N_DEFAULT = 50

DS_EDGE_VID = 0x054C
DS_EDGE_PID = 0x0DF2


def _check_hid() -> bool:
    try:
        import hid
    except ImportError:
        print("  WARN: hidapi not installed — skipping HID enumeration")
        return True
    for dev in hid.enumerate(DS_EDGE_VID, DS_EDGE_PID):
        if dev.get("interface_number") == 3:
            return True
    return False


def _check_bridge_health(base_url: str) -> bool:
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _print_operator_gate_checklist() -> None:
    print()
    print("=" * 60)
    print("  CCO PHASE B — OPERATOR GATE (before L6B_ENABLED=true in prod)")
    print("  Source: wiki/methodology/CCO_PHASE_B_DESIGN_v1.md section 5")
    print("=" * 60)
    print()
    print("  [ ] 1. Phase B implementation merged; tests pass with L6B_ENABLED=false.")
    print("  [ ] 2. Operator attests N>=50 L6B calibration probes in l6b_probe_log.")
    print("  [ ] 3. DualSense-class hardware validated (IMU + adaptive trigger path).")
    print("  [ ] 4. poep_enabled remains false; REFLEX_OBSERVED does not imply")
    print("         tournament eligibility.")
    print()
    print("  Do NOT flip production L6B_ENABLED until all boxes are operator-signed.")
    print("=" * 60)


def _print_session_checklist(player: str, game: str, target: int) -> None:
    print()
    print("=" * 60)
    print("  L6B CALIBRATION SESSION CHECKLIST")
    print("=" * 60)
    print(f"  Player:   {player}")
    print(f"  Game:     {game}")
    print(f"  Target:   N={target} probes in l6b_probe_log (global corpus)")
    print()
    print("  Before starting:")
    print("    [ ] bridge/.env has L6B_ENABLED=true (test only — not in CI)")
    print("    [ ] docs/l6b-calibration-test-env.example — L6B_PROBE_INTERVAL_TICKS tuned")
    print("    [ ] Bridge restarted after .env edit")
    print("    [ ] DualSense Edge on USB; run l6_hardware_check.py PASS")
    print()
    print("  During session (~6-7 minutes per gameplay burst; Ctrl-C between bursts):")
    print("    [ ] Play NCAA normally; probes fire only when R2 is at rest (between plays)")
    print("    [ ] Do not anticipate probes — quiet huddle moments are the reflex window")
    print("    [ ] Hold controller in normal gaming posture")
    print("    [ ] Each probe logs classification + reflex_verdict to l6b_probe_log automatically")
    print()
    print("  Ctrl-C ends monitoring early; corpus rows are retained.")
    print("=" * 60)
    print()


def _format_probe_line(progress: dict) -> str:
    n = progress["probe_count"]
    target = progress.get("target_n", TARGET_N_DEFAULT)
    latest = progress.get("latest_probe") or {}
    rv = latest.get("reflex_verdict", "-")
    cls = latest.get("classification", "-")
    lat = latest.get("latency_ms")
    lat_s = f"{lat:.1f}" if lat is not None else "-"
    return (
        f"N={n}/{target}"
        f" | latest reflex_verdict={rv}"
        f" classification={cls}"
        f" latency_ms={lat_s}"
    )


def main() -> int:
    global BRIDGE_URL
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--player", "-p", required=True, help="Player label (audit notes only)")
    parser.add_argument("--game", "-g", required=True, help="Game title (audit notes only)")
    parser.add_argument(
        "--target", "-t", type=int, default=TARGET_N_DEFAULT,
        help=f"Stop at this probe count (default: {TARGET_N_DEFAULT})",
    )
    parser.add_argument(
        "--interval", type=float, default=POLL_INTERVAL_S,
        help=f"DB poll interval seconds (default: {POLL_INTERVAL_S})",
    )
    parser.add_argument("--bridge-url", default=BRIDGE_URL, help="Bridge base URL")
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    parser.add_argument("--device-id", default=None, help="Filter progress to one device")
    parser.add_argument("--no-prompt", action="store_true", help="Skip ENTER prompt")
    args = parser.parse_args()
    BRIDGE_URL = args.bridge_url

    cfg = Config()
    db_path = args.db or cfg.db_path
    store = Store(db_path)

    print("L6B Calibration Capture Monitor")
    print(f"Bridge: {BRIDGE_URL}")
    print(f"DB:     {db_path}")
    print(f"Player: {args.player}  Game: {args.game}")
    print()

    print("Pre-flight:")
    if not _check_hid():
        print("  FAIL: DualSense Edge not found on USB.")
        return 1
    print("  PASS: DualSense Edge HID present (or hidapi skipped)")

    if not _check_bridge_health(BRIDGE_URL):
        print(f"  FAIL: Bridge not reachable at {BRIDGE_URL}")
        print("  Start: python -m bridge.vapi_bridge.main")
        return 1
    print(f"  PASS: Bridge healthy")

    if not getattr(cfg, "l6b_enabled", False):
        print()
        print("  WARN: Config.l6b_enabled is False in this process.")
        print("        Ensure bridge/.env has L6B_ENABLED=true and bridge was restarted.")
        print("        See docs/l6b-calibration-test-env.example")
    else:
        print("  PASS: L6B_ENABLED=true in loaded Config")

    progress = store.get_l6b_calibration_progress(device_id=args.device_id)
    print()
    print(f"  Starting corpus: {_format_probe_line(progress)}")

    if progress["probe_count"] >= args.target:
        print()
        print(f"  TARGET ALREADY REACHED: N={progress['probe_count']} >= {args.target}")
        _print_operator_gate_checklist()
        return 0

    _print_session_checklist(args.player, args.game, args.target)
    if not args.no_prompt:
        input("  Press ENTER to start monitoring (Ctrl-C to end)...")

    done = False
    last_n = progress["probe_count"]
    session_start = time.monotonic()

    def _handle_sigint(_sig, _frame):
        nonlocal done
        done = True

    signal.signal(signal.SIGINT, _handle_sigint)

    print()
    print("Monitoring l6b_probe_log — new probes print N immediately.")
    print()

    try:
        while not done:
            progress = store.get_l6b_calibration_progress(device_id=args.device_id)
            n = progress["probe_count"]
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            elapsed = time.monotonic() - session_start

            if n > last_n:
                delta = n - last_n
                print(f"[{ts}] +{delta} probe(s) | {_format_probe_line(progress)}")
                last_n = n
            else:
                print(f"\r[{ts}] elapsed={elapsed:.0f}s | waiting... N={n}/{args.target}", end="", flush=True)

            if n >= args.target:
                print()
                print()
                print(f"  TARGET REACHED: N={n} >= {args.target}")
                _print_operator_gate_checklist()
                return 0

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass

    print()
    print()
    progress = store.get_l6b_calibration_progress(device_id=args.device_id)
    print("SESSION ENDED (operator interrupt)")
    print(f"  Duration: {time.monotonic() - session_start:.0f}s")
    print(f"  Corpus:   {_format_probe_line(progress)}")
    print()
    print("  Resume anytime — corpus is cumulative in l6b_probe_log.")
    if progress["probe_count"] < args.target:
        print(f"  Remaining: {args.target - progress['probe_count']} probes to operator gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
