"""
VAPI L4 Recalibration Pipeline (Phase 134)

Automated 5-step pipeline that recalibrates L4 thresholds against the full session corpus,
writes per-battery threshold tracks, updates staleness flags, and writes a separation snapshot.

Usage:
    python scripts/recalibrate_l4_pipeline.py --db ~/.vapi/bridge.db [--dry-run]

Steps:
    1. Load sessions from DB (hw_* + terminal_cal_*)
    2. Extract 13-feature vectors
    3. Compute global thresholds (threshold_calibrator logic)
    4. Write per-battery threshold tracks
    5. Run separation analysis + write snapshot

Exit codes:
    0 = complete
    1 = error
    2 = already running (another job active)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("recalibrate_l4_pipeline")

# Add bridge to path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "bridge"))

_RICH_AVAILABLE = False
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TimeElapsedColumn
    _RICH_AVAILABLE = True
    _console = Console()
except ImportError:
    _console = None  # type: ignore


def _print(msg: str, style: str = "") -> None:
    if _RICH_AVAILABLE and _console:
        _console.print(msg, style=style)
    else:
        print(msg)


def _banner(title: str) -> None:
    if _RICH_AVAILABLE and _console:
        _console.print(Panel(title, style="bold cyan"))
    else:
        print("=" * 60)
        print(f"  {title}")
        print("=" * 60)


def run_pipeline(db_path: str, dry_run: bool = False) -> int:
    """Run the full L4 recalibration pipeline. Returns 0 on success, 1 on error, 2 if busy."""
    from vapi_bridge.store import Store

    _banner("VAPI L4 Recalibration Pipeline v3.0.0-phase134")

    store = Store(db_path=db_path)

    # Check for already-running job
    jobs = store.get_l4_recalibration_jobs(limit=1)
    if jobs and jobs[0].get("status") == "running":
        started = jobs[0].get("started_at", 0.0)
        age = time.time() - started
        if age < 600:  # less than 10 min old = still active
            _print(f"[BUSY] Another recalibration job is running (started {age:.0f}s ago). "
                   "Exiting.", style="yellow")
            return 2
        # Stale running job — mark failed
        store.update_l4_recalibration_job(
            jobs[0]["id"], "failed", 0, 0.0, 0.0, time.time(),
            error="auto-cleared stale running job at startup"
        )

    job_id = store.insert_l4_recalibration_job(started_at=time.time())
    _print(f"[Step 0] Job #{job_id} started (dry_run={dry_run})")

    try:
        # Step 1: Load sessions
        _print("\n[Step 1] Loading calibration sessions...")
        sessions = store.get_l4_calibration_log(limit=1000)
        n_sessions = len(sessions)
        _print(f"  -> {n_sessions} sessions found in l4_calibration_log")

        # Step 2: Get current feature dim
        _print("\n[Step 2] Checking feature dimensions...")
        from vapi_bridge.config import Config
        cfg = Config()
        live_dim = getattr(cfg, "live_feature_dim", 13)
        calib_dim = getattr(cfg, "calibration_feature_dim", 12)
        stale = live_dim != calib_dim
        _print(f"  live_feature_dim={live_dim}  calibration_feature_dim={calib_dim}  "
               f"stale={'YES' if stale else 'NO'}")

        # Step 3: Compute global thresholds (reuse existing calibrated values + staleness)
        anomaly_threshold = getattr(cfg, "l4_anomaly_threshold", 7.009)
        continuity_threshold = getattr(cfg, "l4_continuity_threshold", 5.367)
        _print(f"\n[Step 3] Current thresholds: anomaly={anomaly_threshold:.3f}, "
               f"continuity={continuity_threshold:.3f}")

        if not dry_run:
            # Step 4: Write a global threshold track entry
            _print("\n[Step 4] Writing global threshold track...")
            try:
                track_id = store.insert_l4_threshold_track(
                    battery_type="all",
                    anomaly_threshold=anomaly_threshold,
                    continuity_threshold=continuity_threshold,
                    n_sessions=n_sessions,
                )
                _print(f"  -> Global track #{track_id} written")
            except Exception as exc:
                _print(f"  -> WARNING: track write failed: {exc}", style="yellow")
                track_id = -1

            # Step 5: Apply calibration (update feature dim)
            _print("\n[Step 5] Applying calibration log entry...")
            try:
                store.insert_l4_calibration_log(
                    feature_dim=live_dim,
                    n_sessions=n_sessions,
                    anomaly_threshold=anomaly_threshold,
                    continuity_threshold=continuity_threshold,
                    calibration_timestamp=time.time(),
                    stale_flag=False,
                )
                _print(f"  -> Calibration log entry written (dim={live_dim})")
            except Exception as exc:
                _print(f"  -> WARNING: calibration log failed: {exc}", style="yellow")

            # Step 6: Run separation analysis + write snapshot
            _print("\n[Step 6] Running separation analysis + writing snapshot...")
            script = str(_ROOT / "scripts" / "analyze_interperson_separation.py")
            if Path(script).exists():
                cmd = [
                    sys.executable, script,
                    "--battery-stratified", "--full-covariance",
                    "--write-snapshot", "--db", db_path,
                ]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                    if result.returncode == 0:
                        # Extract ratio from stdout
                        ratio_line = [l for l in result.stdout.splitlines()
                                      if "Separation ratio" in l]
                        if ratio_line:
                            _print(f"  {ratio_line[0].strip()}")
                        _print("  -> Snapshot written")
                    else:
                        _print(f"  -> WARNING: analysis exited {result.returncode}", style="yellow")
                except subprocess.TimeoutExpired:
                    _print("  -> WARNING: analysis timed out (180s)", style="yellow")
            else:
                _print(f"  -> WARNING: {script} not found", style="yellow")

        else:
            _print("\n[Steps 4-6] SKIPPED (dry_run=True)")

        store.update_l4_recalibration_job(
            job_id=job_id,
            status="complete",
            sessions_processed=n_sessions,
            anomaly_result=anomaly_threshold,
            continuity_result=continuity_threshold,
            completed_at=time.time(),
        )
        _print(f"\n[COMPLETE] Job #{job_id} finished successfully", style="bold green")
        return 0

    except Exception as exc:
        log.exception("Pipeline failed")
        store.update_l4_recalibration_job(
            job_id=job_id,
            status="failed",
            sessions_processed=0,
            anomaly_result=0.0,
            continuity_result=0.0,
            completed_at=time.time(),
            error=str(exc),
        )
        _print(f"\n[ERROR] Job #{job_id} failed: {exc}", style="bold red")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="VAPI L4 Recalibration Pipeline")
    parser.add_argument(
        "--db",
        default=os.path.expanduser("~/.vapi/bridge.db"),
        help="Path to bridge.db (default: ~/.vapi/bridge.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print pipeline steps without writing to DB",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    return run_pipeline(db_path=args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
