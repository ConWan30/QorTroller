#!/usr/bin/env python3
"""TRL-1 R1 - Card-arrival UVC capture smoke (Trio Readiness Loop).

Enumerates capture devices the SAME way the retina daemon's UvcFrameSource opens
them (CAP_DSHOW -> fallback, MJPG FOURCC, request WxH@fps, prove a frame), reports
the ACTUAL delivered resolution/fps per index, and gives a GO / NO-GO verdict for
the target index. So the AMANKA capture card is productive the hour it arrives
instead of after a day of debugging. Reports honestly with no card attached.

Uses the SAME env vars as the daemon (RETINA_UVC_INDEX / WIDTH / HEIGHT / FPS /
FOURCC) - so a GO here means the daemon's exact open path works on this card.

  python scripts/retina_card_smoke.py                 # probe 0..5, verdict on RETINA_UVC_INDEX
  RETINA_UVC_INDEX=1 python scripts/retina_card_smoke.py
  python scripts/retina_card_smoke.py --max-index 8

ASCII-only output (runs on any console). Needs opencv-python (cv2) for a live
probe; reports NO-CV2 honestly if absent. Runbook:
docs/retina-card-arrival-runbook-2026-07-11.md
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

# Defaults MATCH UvcFrameSource (bridge/vapi_bridge/qortroller_retina_capture.py).
_ENV = {
    "index":  int(os.environ.get("RETINA_UVC_INDEX", "0") or 0),
    "width":  int(os.environ.get("RETINA_UVC_WIDTH", "1920") or 1920),
    "height": int(os.environ.get("RETINA_UVC_HEIGHT", "1080") or 1080),
    "fps":    int(os.environ.get("RETINA_UVC_FPS", "60") or 60),
    "fourcc": (os.environ.get("RETINA_UVC_FOURCC", "MJPG") or "MJPG"),
}
# "usable" bar for a GO (ideal is 1920x1080@60; 720p30 still works for retina).
MIN_WIDTH = 1280
MIN_FPS = 30

GO, NO_GO, NO_DEVICE, NO_CV2 = "GO", "NO-GO", "NO-DEVICE", "NO-CV2"


@dataclass
class DeviceReport:
    index: int
    opened: bool
    grabbed: bool
    width: int
    height: int
    fps: float
    note: str = ""


def _probe_uvc(index, width, height, fps, fourcc):
    """Open index EXACTLY as UvcFrameSource does (CAP_DSHOW -> fallback, MJPG,
    request WxH@fps, prove a frame). Returns a dict, or None if cv2 is absent."""
    try:
        import cv2
    except ImportError:
        return None
    cap = None
    try:
        cap = cv2.VideoCapture(index, getattr(cv2, "CAP_DSHOW", 0))
        if not cap.isOpened():
            cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            return {"opened": False, "grabbed": False, "width": 0, "height": 0, "fps": 0.0}
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*(fourcc + "    ")[:4]))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        ok, frame = cap.read()
        return {
            "opened": True,
            "grabbed": bool(ok and frame is not None),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0),
        }
    except Exception as exc:  # noqa: BLE001 - a probe error is reported, never a crash
        return {"opened": False, "grabbed": False, "width": 0, "height": 0, "fps": 0.0,
                "note": repr(exc)[:60]}
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:  # noqa: BLE001
                pass


def enumerate_devices(max_index, width, height, fps, fourcc, probe=_probe_uvc):
    """Probe indices 0..max_index. Returns (reports, cv2_present)."""
    reports = []
    cv2_present = True
    for i in range(max_index + 1):
        r = probe(i, width, height, fps, fourcc)
        if r is None:
            cv2_present = False
            break
        reports.append(DeviceReport(index=i, opened=r["opened"], grabbed=r["grabbed"],
                                    width=r["width"], height=r["height"], fps=r["fps"],
                                    note=r.get("note", "")))
    return reports, cv2_present


def verdict(reports, target_index, min_width=MIN_WIDTH, min_fps=MIN_FPS):
    """Pure GO/NO-GO. GO iff the target index delivered a frame meeting the bar."""
    live = [r for r in reports if r.opened and r.grabbed]
    if not live:
        return (NO_DEVICE, "no capture device delivered a frame - plug the card in, "
                           "check the USB + HDMI cables and drivers (HDCP passthrough?)")
    tgt = next((r for r in reports if r.index == target_index), None)
    if tgt and tgt.opened and tgt.grabbed and tgt.width >= min_width and tgt.fps >= min_fps:
        ideal = "" if (tgt.width >= 1920 and tgt.fps >= 60) else " (below ideal 1920x1080@60)"
        return (GO, f"index {target_index}: {tgt.width}x{tgt.height}@{tgt.fps:.0f} meets the bar{ideal}")
    other = [r for r in live if r.width >= min_width and r.fps >= min_fps and r.index != target_index]
    if other:
        b = max(other, key=lambda r: (r.width, r.fps))
        return (NO_GO, f"index {target_index} not usable, but index {b.index} delivers "
                       f"{b.width}x{b.height}@{b.fps:.0f} - set RETINA_UVC_INDEX={b.index}")
    return (NO_GO, f"a device is present at index {target_index} but below the bar "
                   f"(need >={min_width}px, >={min_fps}fps) - check MJPG FOURCC / USB3 port / HDCP")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # plug-and-play; ASCII strings below regardless
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="TRL-1 R1 UVC capture smoke")
    ap.add_argument("--max-index", type=int, default=5, help="highest device index to probe (default 5)")
    a = ap.parse_args()

    print("=" * 74)
    print("  TRL-1 R1 - RETINA CARD-ARRIVAL UVC SMOKE")
    print("=" * 74)
    print(f"  Target : RETINA_UVC_INDEX={_ENV['index']}  request "
          f"{_ENV['width']}x{_ENV['height']}@{_ENV['fps']} {_ENV['fourcc']}")

    reports, cv2_present = enumerate_devices(a.max_index, _ENV["width"], _ENV["height"],
                                             _ENV["fps"], _ENV["fourcc"])
    if not cv2_present:
        print("  NO-CV2 : opencv-python (cv2) not installed - pip install opencv-python for a live probe")
        print("=" * 74)
        return 2

    print(f"  Probed : indices 0..{a.max_index}")
    print("-" * 74)
    print("  idx  opened  frame   resolution      fps   note")
    for r in reports:
        res = f"{r.width}x{r.height}" if r.opened else "-"
        print(f"  {r.index:<4} {('yes' if r.opened else 'no'):<7} "
              f"{('yes' if r.grabbed else 'no'):<7} {res:<15} {r.fps:<5.0f} {r.note}")
    print("-" * 74)
    st, reason = verdict(reports, _ENV["index"])
    print(f"  VERDICT: {st} - {reason}")
    if st == GO:
        print("  Next   : set RETINA_CAPTURE_SOURCE=uvc; then run TRL-1 R2 (OCR crop recalibration)")
        print("           before trusting authorship OCR on the card feed.")
    else:
        print("  Next   : see docs/retina-card-arrival-runbook-2026-07-11.md")
    print("=" * 74)
    return 0 if st == GO else 1


if __name__ == "__main__":
    raise SystemExit(main())
