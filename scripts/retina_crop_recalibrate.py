#!/usr/bin/env python3
"""TRL-1 R2 - Retina OCR crop-recalibration harness (Trio Readiness Loop).

HONEST FINDING (this cycle): the retina kill-feed / panel crops are stored as
FRACTIONS (0..1) and converted to pixels at runtime by
qortroller_retina_capture._roi_px -> they are RESOLUTION-INDEPENDENT. Moving from
the WGC window to the card's full 1080p does NOT shift them by resolution (R1's
runbook overstated this). The residual risk is CONTENT-FRAMING: aspect ratio,
letterbox bars, or HUD-position differences between the WGC capture and the raw
card feed. This harness makes that risk a one-glance check instead of a blind
guess:

  --report                 validate the crops + show the exact pixel rects at the
                           card resolution (default 1920x1080)  [pure, no deps]
  --overlay FRAME --out P  draw the crop rectangles on a real card frame so you can
                           eyeball alignment in one image  [needs opencv-python]
  --src-content / --dst-content   remap crops for a content-framing difference
                           (e.g. a letterboxed source -> full-frame card)

Reads the same env vars as the daemon (RETINA_KILLFEED_ROI,
RETINA_CAPTURE_PANEL_ROI) or --killfeed-roi / --panel-roi. ASCII-only output.
Runbook: docs/retina-card-arrival-runbook-2026-07-11.md

RAIL 7 (TRL-1): this proposes + verifies crops; it does NOT make authorship trust
them. Authorship stays UNCALIBRATED on the card feed until the zero-false-read gate
re-passes on it.
"""
from __future__ import annotations

import argparse
import os
import sys

# Daemon defaults (bridge/vapi_bridge/config.py).
_DEFAULT_KILLFEED = os.environ.get("RETINA_KILLFEED_ROI", "0.62,0.10,0.36,0.22")
_DEFAULT_PANEL = os.environ.get("RETINA_CAPTURE_PANEL_ROI", "0.0,0.28,0.32,0.67")


# -- pure ROI utilities (mirror qortroller_retina_capture._parse_roi / _roi_px) --

def parse_roi(s):
    """'fx,fy,fw,fh' (0..1) -> tuple or None (matches the daemon's _parse_roi)."""
    try:
        parts = [float(x) for x in str(s).split(",")]
        if len(parts) == 4 and all(0.0 <= p <= 1.0 for p in parts):
            return tuple(parts)
    except (TypeError, ValueError):
        pass
    return None


def roi_px(width, height, roi):
    """Fractional (fx,fy,fw,fh) -> (x0, y0, x1, y1) pixels (matches _roi_px order,
    re-ordered x-first for drawing)."""
    fx, fy, fw, fh = roi
    x0 = int(width * fx)
    x1 = int(width * min(1.0, fx + fw))
    y0 = int(height * fy)
    y1 = int(height * min(1.0, fy + fh))
    return x0, y0, x1, y1


def validate_roi(roi):
    """Return a list of issue strings ([] = clean)."""
    if roi is None:
        return ["unparseable (need 'fx,fy,fw,fh' with each 0..1)"]
    fx, fy, fw, fh = roi
    issues = []
    if fw <= 0 or fh <= 0:
        issues.append("degenerate (fw/fh must be > 0)")
    if fx + fw > 1.0 + 1e-9:
        issues.append(f"overflows right edge (fx+fw={fx + fw:.3f} > 1)")
    if fy + fh > 1.0 + 1e-9:
        issues.append(f"overflows bottom edge (fy+fh={fy + fh:.3f} > 1)")
    return issues


def remap_content_box(roi, src_box, dst_box):
    """Remap a fractional ROI for a content-framing difference. src_box/dst_box are
    (cx,cy,cw,ch) fractions locating the GAME CONTENT within the source (WGC) and
    dest (card) frames. Identity when both are full-frame (0,0,1,1)."""
    fx, fy, fw, fh = roi
    scx, scy, scw, sch = src_box
    dcx, dcy, dcw, dch = dst_box
    rx = (fx - scx) / scw
    ry = (fy - scy) / sch
    return (dcx + rx * dcw, dcy + ry * dch, fw / scw * dcw, fh / sch * dch)


def overlay_rects(width, height, rois):
    """Pure: [(label, (x0,y0,x1,y1), color_bgr), ...] for drawing. Green=killfeed,
    cyan=panel."""
    colors = {"killfeed": (0, 255, 0), "panel": (255, 255, 0)}
    out = []
    for label, roi in rois:
        if roi is not None:
            out.append((label, roi_px(width, height, roi), colors.get(label, (0, 0, 255))))
    return out


def draw_overlay(frame_path, out_path, rois):
    """Draw the crop rectangles on a real frame and save. Needs opencv-python."""
    import cv2
    img = cv2.imread(frame_path)
    if img is None:
        raise FileNotFoundError(f"could not read frame {frame_path!r}")
    h, w = img.shape[:2]
    for label, (x0, y0, x1, y1), color in overlay_rects(w, h, rois):
        cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
        cv2.putText(img, label, (x0 + 4, max(0, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.imwrite(out_path, img)
    return (w, h)


def _resolve_rois(a):
    kf = a.killfeed_roi if a.killfeed_roi else _DEFAULT_KILLFEED
    pn = a.panel_roi if a.panel_roi else _DEFAULT_PANEL
    rois = [("killfeed", parse_roi(kf)), ("panel", parse_roi(pn))]
    if a.src_content and a.dst_content:
        sb, db = parse_roi(a.src_content), parse_roi(a.dst_content)
        if sb and db:
            rois = [(lbl, remap_content_box(r, sb, db) if r else None) for lbl, r in rois]
    return rois


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="TRL-1 R2 retina crop recalibration")
    ap.add_argument("--killfeed-roi", default="")
    ap.add_argument("--panel-roi", default="")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--src-content", default="", help="content box in the WGC frame 'cx,cy,cw,ch'")
    ap.add_argument("--dst-content", default="", help="content box in the card frame 'cx,cy,cw,ch'")
    ap.add_argument("--report", action="store_true", help="validate + show pixel rects (default action)")
    ap.add_argument("--overlay", default="", help="draw the crops on this frame PNG")
    ap.add_argument("--out", default="retina_crop_overlay.png")
    a = ap.parse_args()
    rois = _resolve_rois(a)

    if a.overlay:
        try:
            w, h = draw_overlay(a.overlay, a.out, rois)
        except ImportError:
            print("  NO-CV2: opencv-python not installed - pip install opencv-python for --overlay")
            return 2
        except FileNotFoundError as exc:
            print(f"  ERROR: {exc}")
            return 1
        print(f"  OVERLAY: wrote {a.out} ({w}x{h}) - green=killfeed, cyan=panel; eyeball the alignment")
        return 0

    print("=" * 74)
    print("  TRL-1 R2 - RETINA OCR CROP RECALIBRATION")
    print("=" * 74)
    print("  Finding: crops are FRACTIONS -> resolution-INDEPENDENT (converted to px")
    print("           at runtime by _roi_px). WGC->card does NOT shift them by")
    print("           resolution; the residual risk is CONTENT-FRAMING (aspect/letterbox).")
    if a.src_content and a.dst_content:
        print(f"  Remap  : content {a.src_content} -> {a.dst_content} applied")
    print(f"  Target : {a.width}x{a.height} (card)")
    print("-" * 74)
    ok = True
    for label, roi in rois:
        issues = validate_roi(roi)
        if roi is None:
            print(f"  {label:<9} unparseable")
            ok = False
            continue
        x0, y0, x1, y1 = roi_px(a.width, a.height, roi)
        flag = "OK" if not issues else "; ".join(issues)
        if issues:
            ok = False
        print(f"  {label:<9} {roi[0]:.3f},{roi[1]:.3f},{roi[2]:.3f},{roi[3]:.3f}  ->  "
              f"px x[{x0}..{x1}] y[{y0}..{y1}]  ({x1 - x0}x{y1 - y0})  {flag}")
    print("-" * 74)
    print("  Next (card-arrival): grab one card frame, then")
    print("    python scripts/retina_crop_recalibrate.py --overlay card_frame.png --out check.png")
    print("  and confirm the boxes land on the HUD. Authorship stays UNCALIBRATED until the")
    print("  zero-false-read gate re-passes on the card feed (TRL-1 rail 7).")
    print("=" * 74)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
