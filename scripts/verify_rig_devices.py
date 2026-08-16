#!/usr/bin/env python3
"""
Verify the operator rig map (config/rig_devices.json) against reality.
=====================================================================
Fail early at rig startup instead of grabbing the wrong camera.

What it CAN check (without opening any capture device):
  - config self-consistency (unique indices, required roles present)
  - expected device NAMES appear in the ffmpeg DirectShow enumeration
    (e.g. "OBS Virtual Camera")

What it CANNOT check:
  - OpenCV index ordering. cv2 index order differs per backend (MSMF vs
    DSHOW) and per machine — that is exactly why the map is locked. Index
    correctness is confirmed the documented way: eye-check
    logs/eye_check_*.png after starting the stack. This script deliberately
    never opens a camera (a health check must not disturb a live rig).

Exit codes: 0 = OK or skipped-with-reason, 1 = mismatch/violation.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "rig_devices.json"

REQUIRED_ROLES = {"house-webcam", "bridge-capture-card", "streamer-virtual-camera"}


def load_and_validate_config() -> tuple[dict, list[str]]:
    errors: list[str] = []
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    devices = cfg.get("devices", [])
    indices = [d.get("index") for d in devices]
    if len(indices) != len(set(indices)):
        errors.append("duplicate indices in rig_devices.json")
    roles = {d.get("role") for d in devices}
    missing = REQUIRED_ROLES - roles
    if missing:
        errors.append(f"missing required roles: {sorted(missing)}")
    if not cfg.get("locked"):
        errors.append("config lacks 'locked' date (map must be explicitly locked)")
    return cfg, errors


def list_dshow_devices() -> list[str] | None:
    """Names from `ffmpeg -list_devices true -f dshow -i dummy` (never opens a camera)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    # ffmpeg exits 0/1 depending on version; the listing is on stderr as
    # `[dshow @ ...] "NAME" (video)` lines. ffmpeg 8 prints no section
    # header, so match device lines directly.
    blob = proc.stderr
    return [m for m in re.findall(r'\[dshow @ [^\]]*\]\s+"([^"]+)"\s+\(video\)', blob)]


def main() -> int:
    if not CONFIG_PATH.is_file():
        print(f"FAIL: {CONFIG_PATH} missing")
        return 1
    cfg, errors = load_and_validate_config()

    print(f"rig map (locked {cfg.get('locked')}):")
    for d in cfg.get("devices", []):
        print(f"  [{d['index']}] {d['role']:<26} expect={d.get('name_contains')!r} backend={d.get('backend')}")

    names = list_dshow_devices()
    if names is None:
        print("\nWARN: ffmpeg not available or listing failed — name checks skipped "
              "(config consistency only). Eye-check PNGs remain authoritative for indices.")
    else:
        print(f"\ndshow devices seen ({len(names)}):")
        for n in names:
            print(f"  - {n}")
        for d in cfg.get("devices", []):
            expect = d.get("name_contains")
            if expect is None:
                continue
            if not any(expect.lower() in n.lower() for n in names):
                errors.append(f"expected device matching {expect!r} (index {d['index']}, {d['role']}) not in dshow list")

    if errors:
        print("\nRIG MAP FAIL:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nrig map OK (index correctness still requires eye-check PNGs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
