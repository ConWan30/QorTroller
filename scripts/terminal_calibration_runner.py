"""
terminal_calibration_runner.py — VAPI Terminal Calibration Battery Orchestrator

Runs a structured, no-gameplay calibration battery directly from the terminal.
Requires only: DualShock Edge CFI-ZCP1 connected via USB.  No console, no game launch.

BATTERIES
---------
separation_focused  (RECOMMENDED — ~45–55 min per player)
    Six structured physical capture phases designed to maximise the features
    that drive inter-person Mahalanobis distance:

      Phase 1  resting_baseline   5 min  Controller at rest on desk.
                                         Noise floor, micro-tremor, gravity vector.
      Phase 2  natural_grip       7 min  Hold naturally. Vary grip pressure slightly.
                                         L4 tremor variance, grip asymmetry.
      Phase 3  trigger_rhythm     7 min  Rhythmic L2/R2 presses (~1/s, own cadence).
                                         IBI jitter, trigger onset velocity.
      Phase 4  button_sequence    7 min  Cross/Square/Triangle/Circle sequences.
                                         Per-button timing biometrics.
      Phase 5  stick_sweeps       7 min  Slow analog stick circles + stop-starts.
                                         Stick autocorrelation lag1/lag5.
      Phase 6  spectral_accel     7 min  Hold still, then small wrist rotations.
                                         accel_magnitude_spectral_entropy.

    Then runs analyze_interperson_separation.py across all available player data.
    Prints new separation ratio before exiting.

touchpad_focused  (~7 min — touchpad recapture, NO gameplay)
    Three short phases targeting touch_position_variance specifically.
    Run this for each player to unblock the structural-zero touchpad gap.

      Phase 1  touchpad_swipes   2 min  Deliberate swipes across full touchpad surface.
                                        touch_position_variance, spatial range.
      Phase 2  touchpad_freeform 2 min  Natural freeform thumb movement, no instructions.
                                        Person-specific arc/drift biometrics.
      Phase 3  touchpad_corners  1 min  Slide to each corner in sequence repeatedly.
                                        Trajectory consistency and corner preference.

quick   (15 min — development / pre-check)
    resting_baseline (3 min) + trigger_rhythm (3 min) + button_sequence (3 min)
    + analysis.  No separation computation; threshold check only.

USAGE
-----
    # Full battery, one player at a time:
    python scripts/terminal_calibration_runner.py --battery separation_focused --player P1
    python scripts/terminal_calibration_runner.py --battery separation_focused --player P2
    python scripts/terminal_calibration_runner.py --battery separation_focused --player P3

    # After all three players:
    python scripts/analyze_interperson_separation.py   # final separation ratio report

    # Quick pre-check:
    python scripts/terminal_calibration_runner.py --battery quick --player P1

    # Replay-only (analysis without new captures — useful after manual session captures):
    python scripts/terminal_calibration_runner.py --analyze-only

OUTPUT
------
    sessions/human/terminal_cal_P1/  — six JSON session files per player
    calibration_profile.json         — updated L4 thresholds (if N >= 10)
    docs/interperson-separation-analysis.md  — updated separation ratio report

NOTES
-----
- No gameplay required.  Physical controller movements only.
- Each player session takes ~45–55 minutes including setup prompts.
- Run all three players before interpreting the separation ratio.
- Existing sessions/human/hw_*.json data is included in the analysis automatically.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# Phase 134: rich terminal UX (graceful fallback to plain print)
_RICH_AVAILABLE = False
try:
    from rich.console import Console as _RichConsole
    from rich.panel import Panel as _RichPanel
    from rich.progress import (
        BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
    )
    from rich.table import Table as _RichTable
    _RICH_AVAILABLE = True
    _console = _RichConsole()
except ImportError:
    _console = None  # type: ignore

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO     = Path(__file__).resolve().parent.parent
_SCRIPTS  = _REPO / "scripts"
_SESSIONS = _REPO / "sessions" / "human"
_PYTHON   = sys.executable


# ---------------------------------------------------------------------------
# Phase definition
# ---------------------------------------------------------------------------

class _Phase(NamedTuple):
    name:        str
    label:       str
    duration_s:  int
    instruction: str


_SEPARATION_FOCUSED: list[_Phase] = [
    _Phase(
        name="resting_baseline",
        label="Phase 1/6 — RESTING BASELINE",
        duration_s=300,
        instruction=(
            "Place the controller flat on the desk in front of you.\n"
            "Do NOT hold it — let it rest naturally.\n"
            "Captures noise floor, micro-tremor, gravity vector baseline.\n"
            "Duration: 5 minutes.  You do not need to do anything."
        ),
    ),
    _Phase(
        name="natural_grip",
        label="Phase 2/6 — NATURAL GRIP",
        duration_s=420,
        instruction=(
            "Pick up the controller and hold it naturally, as if you are about to play.\n"
            "Vary your grip pressure slightly every 30–60 seconds — firm, then relaxed.\n"
            "You may shift your hands naturally.  Do NOT press any buttons.\n"
            "Captures L4 tremor variance and grip asymmetry.\n"
            "Duration: 7 minutes."
        ),
    ),
    _Phase(
        name="trigger_rhythm",
        label="Phase 3/6 — TRIGGER RHYTHM",
        duration_s=420,
        instruction=(
            "Hold the controller normally.  Press L2 and R2 alternately at your OWN natural cadence.\n"
            "Aim for roughly once per second, but follow YOUR rhythm — do not count or rush.\n"
            "Vary pressure: sometimes light tap, sometimes full depress.\n"
            "Captures IBI jitter and trigger onset velocity — the most distinctive features.\n"
            "Duration: 7 minutes."
        ),
    ),
    _Phase(
        name="button_sequence",
        label="Phase 4/6 — BUTTON SEQUENCE",
        duration_s=420,
        instruction=(
            "Press the face buttons in a repeating pattern: Cross → Square → Triangle → Circle.\n"
            "Use YOUR natural speed and timing — not a metronome pace.\n"
            "Pause naturally between cycles.  Mix in occasional double-presses if that feels natural.\n"
            "Captures per-button timing biometrics and press-timing jitter variance.\n"
            "Duration: 7 minutes."
        ),
    ),
    _Phase(
        name="stick_sweeps",
        label="Phase 5/6 — STICK SWEEPS",
        duration_s=420,
        instruction=(
            "Move the LEFT analog stick in slow circles, then stop and rest at center.\n"
            "Alternate: slow circle → hold still (5s) → quick sweep → hold still.\n"
            "Use right stick for the second half of this phase.\n"
            "Captures stick autocorrelation lag1/lag5 features.\n"
            "Duration: 7 minutes."
        ),
    ),
    _Phase(
        name="spectral_accel",
        label="Phase 6/6 — SPECTRAL ACCEL",
        duration_s=420,
        instruction=(
            "Hold the controller still for 30 seconds, then make small wrist rotations (not full arm).\n"
            "Pattern: hold still (30s) → slow wrist rotation left-right (30s) → hold still (30s).\n"
            "Repeat this cycle for the full duration.\n"
            "Captures accel_magnitude_spectral_entropy — entropy discriminates human from static bot.\n"
            "Duration: 7 minutes."
        ),
    ),
]

_TOUCHPAD_FOCUSED: list[_Phase] = [
    _Phase(
        name="touchpad_swipes",
        label="Phase 1/3 — TOUCHPAD SWIPES",
        duration_s=120,
        instruction=(
            "Place your RIGHT thumb on the LEFT edge of the touchpad.\n"
            "Slide slowly to the RIGHT edge, lift, return, repeat.\n"
            "Also do: top-to-bottom swipes, and diagonal corner-to-corner.\n"
            "KEEP CONTACT WHILE SLIDING — do not hover or tap.\n"
            "Go at your own natural speed.  No need to count.\n"
            "Duration: 2 minutes."
        ),
    ),
    _Phase(
        name="touchpad_freeform",
        label="Phase 2/3 — TOUCHPAD FREEFORM",
        duration_s=120,
        instruction=(
            "Move your thumb freely across the touchpad however feels natural.\n"
            "Circles, arcs, lazy figure-eights — whatever your thumb does naturally.\n"
            "Do NOT follow a deliberate pattern.  Just let your thumb wander.\n"
            "KEEP CONTACT — continuous sliding, not tapping.\n"
            "This phase captures your personal thumb-arc signature.\n"
            "Duration: 2 minutes."
        ),
    ),
    _Phase(
        name="touchpad_corners",
        label="Phase 3/3 — TOUCHPAD CORNERS",
        duration_s=60,
        instruction=(
            "Slide your thumb to each corner in sequence: top-left, top-right,\n"
            "bottom-right, bottom-left.  Then repeat.\n"
            "Move at your own comfortable pace.  Stay in contact throughout.\n"
            "Duration: 1 minute."
        ),
    ),
]

_QUICK: list[_Phase] = [
    _Phase("resting_baseline", "Quick Phase 1/3 — RESTING BASELINE", 180,
           "Controller at rest on desk.  Do NOT hold it.\nDuration: 3 minutes."),
    _Phase("trigger_rhythm",   "Quick Phase 2/3 — TRIGGER RHYTHM",   180,
           "Alternating L2/R2 at YOUR natural cadence.\nDuration: 3 minutes."),
    _Phase("button_sequence",  "Quick Phase 3/3 — BUTTON SEQUENCE",   180,
           "Cross → Square → Triangle → Circle at your own pace.\nDuration: 3 minutes."),
]

_RESTING_GRIP: list[_Phase] = [
    _Phase(
        name="resting_centroid",
        label="Phase 1/1 — RESTING CENTROID",
        duration_s=300,
        instruction=(
            "Hold the controller in your natural gaming grip.\n"
            "Let your RIGHT thumb rest on the touchpad — do NOT move it.\n"
            "Just hold the controller as if you are waiting for the game to start.\n"
            "KEEP YOUR THUMB STILL — continuous contact, zero movement.\n"
            "This captures your anatomically-fixed thumb resting position.\n"
            "Duration: 5 minutes."
        ),
    ),
]

_BATTERIES: dict[str, list[_Phase]] = {
    "separation_focused": _SEPARATION_FOCUSED,
    "touchpad_focused":   _TOUCHPAD_FOCUSED,
    "quick":              _QUICK,
    "resting_grip":       _RESTING_GRIP,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rprint(msg: str, style: str = "") -> None:
    """Print with rich style if available, else plain print."""
    if _RICH_AVAILABLE and _console:
        _console.print(msg, style=style)
    else:
        print(msg)


def _banner(msg: str, style: str = "bold cyan") -> None:
    if _RICH_AVAILABLE and _console:
        _console.print(_RichPanel(msg, style=style))
    else:
        width = 60
        print(f"\n{'='*width}")
        print(f"  {msg}")
        print(f"{'='*width}")


def _prompt(msg: str = "") -> None:
    if msg:
        print(f"\n  {msg}")
    print("\n  Press ENTER when ready (Ctrl+C to abort)...", end="", flush=True)
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)


def _run_capture(phase: _Phase, output_path: Path) -> bool:
    """Invoke capture_session.py as a subprocess for one phase.  Returns True on success."""
    cmd = [
        _PYTHON,
        str(_SCRIPTS / "capture_session.py"),
        "--duration", str(phase.duration_s),
        "--output",   str(output_path),
        "--notes",    phase.name,
        "--transport", "usb",
    ]
    print(f"\n  Running: {' '.join(cmd)}\n")
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as exc:
        print(f"  ERROR running capture: {exc}", file=sys.stderr)
        return False


def _run_analysis(player_id: str | None, battery: str) -> None:
    """Run threshold_calibrator.py, then (for separation_focused) analyze_interperson_separation.py."""
    _banner("ANALYSIS — computing thresholds from all available sessions")

    # Collect all hw_*.json + terminal_cal_*.json session files
    session_files = sorted(_SESSIONS.glob("hw_*.json")) + sorted(_SESSIONS.glob("terminal_cal_*/*.json"))
    if not session_files:
        print("  No session files found.  Cannot compute thresholds.")
        return

    print(f"  Found {len(session_files)} session file(s).")

    # threshold_calibrator.py
    threshold_cmd = [_PYTHON, str(_SCRIPTS / "threshold_calibrator.py")] + [str(p) for p in session_files]
    print(f"\n  Running threshold_calibrator.py ...")
    try:
        subprocess.run(threshold_cmd, check=False)
    except Exception as exc:
        print(f"  WARNING: threshold_calibrator failed: {exc}", file=sys.stderr)

    # analyze_interperson_separation.py (separation_focused + touchpad_focused + resting_grip; needs ≥2 players)
    if battery in ("separation_focused", "touchpad_focused", "resting_grip"):
        # Check how many distinct player dirs exist
        player_dirs = [d for d in _SESSIONS.iterdir() if d.is_dir() and d.name.startswith("terminal_cal_")]
        hw_groups = {"P1": [], "P2": [], "P3": []}
        for f in _SESSIONS.glob("hw_*.json"):
            # existing hw sessions go into P1 (they were all from the same primary player historically)
            hw_groups["P1"].append(f)

        total_players = len(player_dirs) + (1 if hw_groups["P1"] else 0)
        if total_players < 2:
            print(
                "\n  NOTE: Inter-person separation requires at least 2 players.\n"
                f"  Currently have data from {total_players} player source(s).\n"
                "  Run the battery for P2 and P3 then re-run --analyze-only."
            )
        else:
            print(f"\n  Running analyze_interperson_separation.py ({total_players} player sources) ...")
            sep_cmd = [_PYTHON, str(_SCRIPTS / "analyze_interperson_separation.py")]
            try:
                subprocess.run(sep_cmd, check=False)
            except Exception as exc:
                print(f"  WARNING: separation analysis failed: {exc}", file=sys.stderr)


def _verify_hid() -> bool:
    """Quick HID device check — returns True if DualShock Edge is detected."""
    try:
        import hid as _hid
        devices = _hid.enumerate(0x054C, 0x0DF2)
        return bool(devices)
    except Exception:
        return False


def _estimated_duration(phases: list[_Phase]) -> str:
    total_s = sum(p.duration_s for p in phases)
    overhead_s = len(phases) * 45  # ~45s prompt + transition overhead per phase
    total_s += overhead_s
    total_m = total_s // 60
    return f"~{total_m}–{total_m + 10} minutes"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="terminal_calibration_runner.py",
        description=(
            "VAPI Terminal Calibration Battery Orchestrator.\n"
            "Runs structured physical capture phases + analysis.\n"
            "No gameplay required — only DualShock Edge via USB."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/terminal_calibration_runner.py --battery separation_focused --player P1\n"
            "  python scripts/terminal_calibration_runner.py --battery separation_focused --player P2\n"
            "  python scripts/terminal_calibration_runner.py --battery separation_focused --player P3\n"
            "  python scripts/terminal_calibration_runner.py --analyze-only\n"
            "  python scripts/terminal_calibration_runner.py --battery quick --player P1\n"
            "  python scripts/terminal_calibration_runner.py --battery touchpad_focused --player P1\n"
            "  python scripts/terminal_calibration_runner.py --battery touchpad_focused --player P2\n"
            "  python scripts/terminal_calibration_runner.py --battery resting_grip --player P1\n"
            "  python scripts/terminal_calibration_runner.py --battery resting_grip --player P2\n"
            "  python scripts/terminal_calibration_runner.py --battery resting_grip --player P3\n"
        ),
    )
    p.add_argument(
        "--battery",
        choices=list(_BATTERIES.keys()),
        default="separation_focused",
        help="Battery preset (default: separation_focused)",
    )
    p.add_argument(
        "--player",
        type=str,
        default=None,
        help="Player identifier: P1, P2, P3, or any string (used in output directory name)",
    )
    p.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip capture — only run analysis on existing session data",
    )
    p.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip HID device verification check (useful for dry-run testing)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    battery_name = args.battery
    phases       = _BATTERIES[battery_name]

    # --- Analyze-only mode ---
    if args.analyze_only:
        _run_analysis(player_id=None, battery=battery_name)
        return 0

    # --- Require player ID for capture ---
    player_id = args.player
    if not player_id:
        print("ERROR: --player is required for capture (e.g., --player P1).", file=sys.stderr)
        print("       Use --analyze-only to skip capture.", file=sys.stderr)
        return 1

    player_id = player_id.strip().upper()
    output_dir = _SESSIONS / f"terminal_cal_{player_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Banner ---
    _banner(f"VAPI TERMINAL CALIBRATION BATTERY — {battery_name.upper()}")
    print(f"\n  Player    : {player_id}")
    print(f"  Battery   : {battery_name}")
    print(f"  Phases    : {len(phases)}")
    print(f"  Est. time : {_estimated_duration(phases)}")
    print(f"  Output    : {output_dir}")

    # --- HID verification ---
    if not args.skip_verify:
        print("\n  Checking for DualShock Edge (VID=0x054C, PID=0x0DF2) ...")
        if _verify_hid():
            print("  DualShock Edge DETECTED.")
        else:
            print(
                "\n  WARNING: DualShock Edge NOT detected.\n"
                "  Ensure the controller is connected via USB-C before continuing.\n"
                "  If connected over Bluetooth, set --transport bt in individual capture runs.\n"
                "  Continue anyway? (may fail at first capture)",
                file=sys.stderr,
            )
            _prompt("Connect controller, then press ENTER to continue (or Ctrl+C to abort)")

    # --- Pre-battery prompt ---
    print(
        f"\n  BEFORE YOU START:\n"
        f"  - Sit comfortably at your desk, controller within reach.\n"
        f"  - You will be guided through {len(phases)} phases.\n"
        f"  - Each phase has simple physical instructions — no game needed.\n"
        f"  - Total time: {_estimated_duration(phases)}.\n"
    )
    _prompt("Ready to begin?")

    # --- Run phases ---
    completed: list[str] = []
    failed: list[str] = []

    for idx, phase in enumerate(phases, 1):
        ts      = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_path = output_dir / f"{phase.name}_{ts}.json"

        _banner(f"{phase.label}  ({phase.duration_s // 60}m {phase.duration_s % 60}s)")
        print(f"\n  INSTRUCTION:\n")
        for line in phase.instruction.splitlines():
            print(f"    {line}")

        _prompt(f"Phase {idx}/{len(phases)}: ready to capture?")

        ok = _run_capture(phase, out_path)
        if ok and out_path.exists():
            size_kb = out_path.stat().st_size // 1024
            _rprint(f"\n  [bold green]OK[/bold green]  Saved: {out_path}  ({size_kb} KB)"
                    if _RICH_AVAILABLE else f"\n  OK  Saved: {out_path}  ({size_kb} KB)",
                    style="")
            completed.append(phase.name)
        else:
            _rprint(
                f"\n  [bold yellow]WARNING[/bold yellow]: Phase '{phase.name}' capture failed or produced no output."
                if _RICH_AVAILABLE else
                f"\n  WARNING: Phase '{phase.name}' capture failed or produced no output.",
                style="",
            )
            failed.append(phase.name)
            _prompt(f"Continue despite failed phase '{phase.name}'?")

    # --- Summary ---
    _banner("CAPTURE COMPLETE", style="bold green")
    _rprint(f"\n  Player    : {player_id}")
    _rprint(f"  Completed : {len(completed)}/{len(phases)} phases",
            style="bold green" if not failed else "yellow")
    if failed:
        _rprint(f"  Failed    : {', '.join(failed)}", style="bold yellow")
    _rprint(f"  Session files in: {output_dir}")

    # --- Analysis ---
    total_session_files = len(list(output_dir.glob("*.json")))
    if total_session_files > 0:
        _prompt(f"\n  {total_session_files} session file(s) captured.  Run analysis now?")
        _run_analysis(player_id=player_id, battery=battery_name)
    else:
        print("\n  No session files found — skipping analysis.")

    # --- Final guidance ---
    _banner("NEXT STEPS")
    player_dirs = [d.name for d in _SESSIONS.iterdir() if d.is_dir() and d.name.startswith("terminal_cal_")]
    print(f"\n  Players with terminal calibration data: {', '.join(sorted(player_dirs)) or 'none yet'}")

    missing = [p for p in ("P1", "P2", "P3") if f"terminal_cal_{p}" not in player_dirs]
    if missing:
        if battery_name == "touchpad_focused":
            print(f"\n  Still needed for touchpad separation contribution:")
            for m in missing:
                print(f"    python scripts/terminal_calibration_runner.py --battery touchpad_focused --player {m}")
        else:
            print(f"\n  Still needed for separation ratio computation:")
            for m in missing:
                print(f"    python scripts/terminal_calibration_runner.py --battery separation_focused --player {m}")
    else:
        print(
            "\n  All three players complete.  Run the final separation analysis:\n"
            "    python scripts/analyze_interperson_separation.py\n"
            "\n  Check docs/interperson-separation-analysis.md for the new ratio.\n"
            "  Target: separation_ratio > 1.0 (current: 0.362).\n"
            "  If ratio > 1.0: tournament deployment unblocked."
        )

    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
