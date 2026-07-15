"""
l6b_desk_reaction_session.py — Operator-fired desk L6B reaction capture.

Alternative to bridge interval auto-probes: YOU press ENTER for each probe,
get immediate diagnostic numbers (true_latency_ms, peak delta, reflex_gap),
and rows land in the same l6b_probe_log / l6b_probe_diagnostic tables.

Prerequisites:
  - Bridge STOPPED (avoids dual-writer on pydualsense)
  - DualSense Edge on USB
  - Optional: python scripts/l6b_probe_feel_test.py first

Protocols:
  still   — involuntary reflex attempt; keep R2 relaxed, normal grip posture
  squeeze — when you feel R2 resistance, squeeze firmly (validates IMU path)

USAGE:
  python scripts/l6b_desk_reaction_session.py --player P1 --protocol still
  python scripts/l6b_desk_reaction_session.py --player P1 --protocol squeeze --count 10
  python scripts/l6b_desk_reaction_session.py --force 128 --mode rigid --hold-ms 300
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from bridge.controller.l6_challenge_profiles import l6b_probe_profile
from bridge.controller.l6_trigger_driver import L6TriggerDriver
from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.cco_l6b_wiring import map_l6b_classification_to_reflex_verdict
from bridge.vapi_bridge.l6b_desk_session import (
    DeskProbeConfig,
    DeskProbeOutcome,
    analyze_desk_probe,
    accel_report_from_snapshot,
    collect_imu_samples,
    desk_device_id,
    expected_post_frames,
    persist_desk_probe,
)
from bridge.vapi_bridge.store import Store
from controller.dualshock_emulator import DualSenseReader, HAS_DUALSENSE


def _bridge_running(url: str) -> bool:
    if requests is None:
        return False
    try:
        return requests.get(f"{url.rstrip('/')}/health", timeout=2).status_code == 200
    except Exception:
        return False


def _protocol_instructions(protocol: str) -> str:
    if protocol == "squeeze":
        return (
            "SQUEEZE protocol: hold controller normally. When R2 resistance hits,\n"
            "  squeeze R2 firmly for ~0.5s (validates IMU sees your motion)."
        )
    return (
        "STILL protocol: hold controller in normal posture. Do NOT press R2.\n"
        "  Let your involuntary grip reflex happen if you feel the resistance."
    )


def _fire_probe_sync(
    ds: object,
    *,
    force: int,
    mode: str,
    hold_ms: int,
    reader: DualSenseReader,
    cfg: DeskProbeConfig,
) -> tuple[float, list[dict], list[dict], int]:
    """Pre-buffer, fire probe, hold effect, capture post window, clear triggers."""
    accel_scale = float(getattr(reader, "_accel_scale", None) or 8192.0)

    print(f"  Baseline IMU ({cfg.pre_samples} samples)...")
    pre_reports = collect_imu_samples(
        reader,
        cfg.pre_samples,
        poll_interval_s=cfg.poll_interval_s,
        accel_scale=accel_scale,
    )
    latest = reader.poll()
    r2_at_probe = int(getattr(latest, "r2_trigger", 0) or 0)

    profile = l6b_probe_profile(force, mode=mode)
    probe_ts = time.monotonic()
    L6TriggerDriver._sync_write(ds, profile)

    hold_s = hold_ms / 1000.0
    capture_s = cfg.capture_window_ms / 1000.0
    deadline = time.monotonic() + hold_s + capture_s
    clear_at = time.monotonic() + hold_s
    cleared = False
    driver = L6TriggerDriver()
    post_reports: list[dict] = []

    while time.monotonic() < deadline:
        snap = reader.poll()
        post_reports.append(
            accel_report_from_snapshot(snap, accel_scale=accel_scale),
        )
        now = time.monotonic()
        if not cleared and now >= clear_at:
            asyncio.run(driver.clear_triggers(ds))
            cleared = True
        if cfg.poll_interval_s > 0:
            time.sleep(cfg.poll_interval_s)

    if not cleared:
        asyncio.run(driver.clear_triggers(ds))

    return probe_ts, pre_reports, post_reports, r2_at_probe


def _resolve_registered_edge_device_id() -> str | None:
    """A2A-POEP-P2: the registered Edge's on-chain device_id (bytes32 hex) from the device birth cert,
    so the edge-reflex campaign stamps the certified device. Fail-open -> None (falls back to desk id)."""
    import json as _json
    import os as _os
    for p in (_os.path.expanduser("~/.vapi/device_birth_cert.json"),
              _os.path.expanduser("~/.vapi/qortroller_device_birth_cert.json")):
        try:
            if _os.path.exists(p):
                d = _json.load(open(p, encoding="utf-8"))
                did = d.get("device_id_hex") or d.get("device_id")
                if did:
                    return str(did).lower().removeprefix("0x")
        except Exception:  # noqa: BLE001
            pass
    return None


def run_session(args: argparse.Namespace) -> int:
    if not HAS_DUALSENSE:
        print("ERROR: pydualsense not installed — pip install pydualsense")
        return 1

    bridge_url = getattr(args, "bridge_url", "http://localhost:8080")
    if _bridge_running(bridge_url):
        print("ERROR: Bridge is running at", bridge_url)
        print("  Stop the bridge first to avoid dual-writer contention on the controller.")
        return 1

    reader = DualSenseReader()
    if not reader.connect():
        return 1

    cfg = DeskProbeConfig(
        r2_force=max(1, min(255, args.force)),
        mode=args.mode,
        hold_ms=max(50, min(2000, args.hold_ms)),
        pre_samples=args.pre_samples,
        poll_interval_s=args.poll_interval,
        capture_window_ms=args.capture_ms,
        response_threshold_lsb=args.threshold,
    )
    # A2A-POEP-P2: --campaign edge-reflex stamps policy_ref=edge_operator_reflex_v1 (the B1+B2 allowlist
    # tag) + the REGISTERED Edge device_id (auto-resolved from the device birth cert), so these probes
    # count toward the certified-device N>=50 gate -- not the desk_operator_still / desk-P1 defaults.
    policy_ref_override = None
    device_id = desk_device_id(args.player)
    if args.campaign == "edge-reflex":
        policy_ref_override = "edge_operator_reflex_v1"
        device_id = args.device_id or _resolve_registered_edge_device_id() or device_id
    store = None if args.no_store else Store(args.db or Config().db_path)

    print()
    print("=" * 60)
    print("  L6B DESK REACTION SESSION (operator-fired)")
    print("=" * 60)
    print(f"  Campaign:  {args.campaign}" + (f"  policy_ref={policy_ref_override}" if policy_ref_override else ""))
    print(f"  Player:    {args.player}")
    print(f"  Device ID: {device_id}")
    print(f"  Protocol:  {args.protocol}")
    print(f"  Probes:    {args.count}")
    print(f"  CCO profile: {args.cco_profile_id}")
    print(f"  Actuator:  mode={cfg.mode} force={cfg.r2_force} hold_ms={cfg.hold_ms}")
    print(f"  IMU:       pre={cfg.pre_samples} post~{expected_post_frames(cfg.capture_window_ms, cfg.poll_interval_s)} @ {cfg.poll_interval_s * 1000:.0f}ms")
    if store:
        print(f"  DB:        {args.db or Config().db_path}")
    else:
        print("  DB:        (dry-run — not persisting)")
    print()
    print(_protocol_instructions(args.protocol))
    print()
    print("  Adaptive R2 resistance — NOT rumble/vibration.")
    print("  Ctrl-C between probes to end early.")
    print("=" * 60)
    print()

    ds = reader.ds
    outcomes: list[DeskProbeOutcome] = []

    try:
        for idx in range(1, args.count + 1):
            print(f"--- Probe {idx}/{args.count} ---")
            if args.protocol == "squeeze":
                print("  Get ready — squeeze R2 when resistance appears.")
            else:
                print("  Get ready — relax R2, normal grip.")
            try:
                input("  Press ENTER to fire probe (Ctrl-C to quit)... ")
            except KeyboardInterrupt:
                print()
                break

            probe_ts, pre_reports, post_reports, r2_at_probe = _fire_probe_sync(
                ds,
                force=cfg.r2_force,
                mode=cfg.mode,
                hold_ms=cfg.hold_ms,
                reader=reader,
                cfg=cfg,
            )

            result, diagnostic_json = analyze_desk_probe(
                pre_reports, post_reports, probe_ts, cfg,
            )
            probe_log_id = None
            enriched_json = diagnostic_json
            if store is not None:
                probe_log_id, enriched_json = persist_desk_probe(
                    store,
                    device_id=device_id,
                    probe_ts=probe_ts,
                    result=result,
                    diagnostic_json=diagnostic_json,
                    protocol=args.protocol,
                    player=args.player,
                    r2_at_probe=r2_at_probe,
                    cco_profile_id=args.cco_profile_id,
                    policy_ref_override=policy_ref_override,
                )

            outcome = DeskProbeOutcome(
                probe_index=idx,
                protocol=args.protocol,
                player=args.player,
                device_id=device_id,
                result=result,
                diagnostic_json=enriched_json,
                reflex_verdict=map_l6b_classification_to_reflex_verdict(
                    result.classification,
                ),
                probe_log_id=probe_log_id,
                r2_at_probe=r2_at_probe,
                pre_sample_count=len(pre_reports),
                post_sample_count=len(post_reports),
            )
            outcomes.append(outcome)
            for line in outcome.summary_lines():
                print(line)
            print()

    finally:
        try:
            asyncio.run(L6TriggerDriver().clear_triggers(ds))
        except Exception:
            pass
        try:
            if reader.ds:
                reader.ds.close()
        except Exception:
            pass

    print()
    print("SESSION SUMMARY")
    print(f"  Probes completed: {len(outcomes)}")
    if outcomes:
        peaks = [o.result.accel_delta_peak for o in outcomes]
        print(f"  Peak delta range: {min(peaks):.1f} – {max(peaks):.1f} LSB")
        human = sum(1 for o in outcomes if o.result.classification == "HUMAN")
        print(f"  HUMAN count: {human}/{len(outcomes)} (legacy classifier — trust diagnostics)")
    if store and outcomes:
        print()
        print("  Report: python scripts/l6b_probe_diagnostic_report.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--player", "-p", default="P1", help="Player label")
    parser.add_argument(
        "--cco-profile-id",
        default="sony_dualshock_edge_v1",
        help="CCO profile_id tag for l6b_probe_log.cco_profile_id (Phase G tier bucketing)",
    )
    parser.add_argument(
        "--protocol",
        choices=("still", "squeeze"),
        default="still",
        help="still=involuntary reflex; squeeze=voluntary grip on cue",
    )
    parser.add_argument("--count", "-n", type=int, default=5, help="Number of probes")
    parser.add_argument("--force", type=int, default=128, help="R2 force 1-255")
    parser.add_argument(
        "--mode",
        choices=("rigid", "pulse"),
        default="rigid",
        help="Adaptive trigger mode",
    )
    parser.add_argument("--hold-ms", type=int, default=200, help="Hold resistance (ms)")
    parser.add_argument(
        "--capture-ms",
        type=float,
        default=400.0,
        help="Post-probe IMU capture window (ms)",
    )
    parser.add_argument(
        "--pre-samples",
        type=int,
        default=50,
        help="Pre-probe baseline samples",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.008,
        help="IMU poll interval seconds (~8ms = bridge rate)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=500.0,
        help="Response threshold LSB (display + classifier; unchanged prod default)",
    )
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    parser.add_argument("--campaign", choices=["desk", "edge-reflex"], default="desk",
                        help="edge-reflex: stamp policy_ref=edge_operator_reflex_v1 + registered "
                             "Edge device_id so probes count toward the certified-device N>=50 gate")
    parser.add_argument("--device-id", default=None,
                        help="explicit device_id for --campaign edge-reflex (else auto-resolved from "
                             "the device birth cert)")
    parser.add_argument(
        "--no-store",
        action="store_true",
        help="Dry-run: print diagnostics only, do not write DB",
    )
    parser.add_argument(
        "--bridge-url",
        default="http://localhost:8080",
        help="Health check URL (must be down)",
    )
    return run_session(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
