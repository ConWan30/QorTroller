#!/usr/bin/env python3
"""QorTroller-side wrap entry. Operator-fired. Bridge cannot grant consent."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compose" / "clock-notary"))

from clock_notary.cli import main  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        argv = ["wrap", "--help"]
    raise SystemExit(main(argv))
