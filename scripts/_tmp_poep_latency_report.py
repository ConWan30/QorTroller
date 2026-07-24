"""Deprecated wrapper — use scripts/poep_latency_report.py (A2A-POEP-CORPUS-TOOLING T3)."""
from __future__ import annotations

import sys
from pathlib import Path

# Re-dispatch to first-class CLI (default date preserved for one-shot convenience).
if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    argv = list(sys.argv[1:])
    if "--date" not in argv:
        argv = ["--date", "2026-07-16", *argv]
    sys.argv = ["poep_latency_report.py", *argv]
    from scripts.poep_latency_report import main
    raise SystemExit(main())
