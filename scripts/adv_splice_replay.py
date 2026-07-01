#!/usr/bin/env python
"""Replay-splice adversarial replay source (Phase 1, archive-only replay).

Reconstructs full frames from the GENUINE archived panel crops (retina_kf_archive/seg3_*) — placing
each panel crop back at its fractional panel-ROI position on a black frame — and plays them FULLSCREEN
on the capture monitor at the original inter-crop cadence, looping. The retina daemon (monitor capture)
sees the replayed kill rows; the operator presses R2 live. This is the "reconstruct fullscreen from
archived crops" D-ADV-1 source: it re-captures the EXACT genuine kill rows through a second WGC encode,
so a composite AUTHORED fire here is a pure timing coincidence (splice), never live authorship.

READ-ONLY on the genuine archive. Writes a per-frame ground-truth log (which kill/death/roster row was
on screen when) to a session-scoped file for exact measured-FAR correlation. Does NOT touch the cert,
thresholds, or any genuine sink.

    python scripts/adv_splice_replay.py --loops 2 --monitor 1
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "bridge"))

from l9_presence import killfeed_cv as kc  # noqa: E402

PANEL_ROI = (0.0, 0.28, 0.32, 0.67)   # matches config default retina_capture_panel_roi
FRAME_W, FRAME_H = 1920, 1080
FLOOR = kc.DEFAULT_MATCH_FLOOR
KMAX = kc.KILLER_MAX_FRAC_PANEL
YGATE = kc.FEED_REGION_MAX_YFRAC


def _label(anchor, im) -> tuple[str, float]:
    """Ground-truth label for a crop by the deployed rule: killer-pos>=floor=KILL, victim-pos=DEATH,
    roster=ROSTER, else BG."""
    s, cx, cy, sc = kc.multiscale_match(anchor, kc.binarize_glyphs(im))
    H, W = im.shape[:2]
    if s < FLOOR or cx is None:
        return "BG", float(s)
    xf, yf = cx / W, cy / H
    if yf >= YGATE:
        return "ROSTER", float(s)
    return ("KILL" if xf < KMAX else "DEATH"), float(s)


def _reconstruct(im) -> np.ndarray:
    full = np.zeros((FRAME_H, FRAME_W, 3), np.uint8)
    x, y, w, h = (int(PANEL_ROI[0] * FRAME_W), int(PANEL_ROI[1] * FRAME_H),
                  int(PANEL_ROI[2] * FRAME_W), int(PANEL_ROI[3] * FRAME_H))
    full[y:y + h, x:x + w] = cv2.resize(im, (w, h))
    return full


def _gameplay_segment(crops):
    """Select the dense gameplay run (drop the 6h idle gap). Keep the contiguous block whose inter-crop
    gaps are < 20s — that's the ~149-crop / ~640s segment holding the 3 kills + 2 deaths."""
    ts = [int(p.split("panel_")[1].split(".")[0]) for p in crops]
    pairs = sorted(zip(ts, crops))
    # find the largest gap; keep everything after it
    gaps = [(pairs[i + 1][0] - pairs[i][0], i) for i in range(len(pairs) - 1)]
    _, split = max(gaps)
    seg = pairs[split + 1:]
    return seg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loops", type=int, default=2, help="how many times to loop the gameplay segment")
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--speed", type=float, default=1.0, help="cadence multiplier (2.0 = 2x faster)")
    ap.add_argument("--max-gap-ms", type=float, default=6000.0, help="cap inter-frame wait (idle crops)")
    ap.add_argument("--archive", default="retina_kf_archive/seg3_*")
    args = ap.parse_args()

    crops = sorted(glob.glob(str(_REPO / args.archive / "panel_*.png")),
                   key=lambda p: int(p.split("panel_")[1].split(".")[0]))
    if not crops:
        print("[replay] no crops found under", args.archive)
        return 1
    seg = _gameplay_segment(crops)
    anchor = kc.load_anchor(str(_REPO / "l9_presence/assets/own_handle_anchor.png"))

    # precompute reconstructed frames + labels (no classify during display)
    print("[replay] preparing %d gameplay-segment frames ..." % len(seg), flush=True)
    prepared = []
    for ts, p in seg:
        im = cv2.imread(p)
        lab, sc = _label(anchor, im)
        prepared.append((ts, _reconstruct(im), lab, sc, Path(p).name))
    # trim to the kill-dense window: [first hot - margin, last hot + margin] so the loop is short + shows
    # every KILL/DEATH without the trailing idle BG (measurement efficiency; kill-density does not bias the
    # per-kill coincidence rate — each kill appearance is an independent trial).
    hot_ts = [ts for ts, _, lab, _, _ in prepared if lab in ("KILL", "DEATH")]
    if hot_ts:
        margin = 90_000 * 1_000_000  # 90s in ns
        lo, hi = min(hot_ts) - margin, max(hot_ts) + margin
        prepared = [f for f in prepared if lo <= f[0] <= hi]
    frames = prepared
    counts = {}
    for _, _, lab, _, _ in frames:
        counts[lab] = counts.get(lab, 0) + 1
    print("[replay] kill-dense window: %d frames, span %.0fs, label counts: %s"
          % (len(frames), (frames[-1][0] - frames[0][0]) / 1e9 if frames else 0, json.dumps(counts)))
    n_kill = counts.get("KILL", 0)
    print("[replay] %d KILL rows / loop x %d loops = %d spliceable kill appearances"
          % (n_kill, args.loops, n_kill * args.loops), flush=True)

    stamp = int(time.time())
    shown_log = _REPO / ("adv_splice_shown_%d.jsonl" % stamp)
    slog = open(shown_log, "w", encoding="utf-8")

    win = "adv_splice_replay"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    print("[replay] FULLSCREEN replay starting on the primary monitor — put the retina daemon on "
          "--monitor %d. Press R2 naturally. Ctrl-C or 'q' in the window to stop early." % args.monitor,
          flush=True)

    try:
        for loop in range(args.loops):
            for i, (ts, frame, lab, sc, name) in enumerate(frames):
                wall = time.time() * 1000.0
                cv2.imshow(win, frame)
                slog.write(json.dumps({"wall_ms": round(wall, 1), "loop": loop, "src_ts_ns": ts,
                                       "label": lab, "score": round(sc, 4), "src": name}) + "\n")
                slog.flush()
                # inter-frame wait = original cadence / speed, capped
                if i + 1 < len(frames):
                    dt = (frames[i + 1][0] - ts) / 1e6 / max(args.speed, 0.01)
                    dt = min(dt, args.max_gap_ms)
                else:
                    dt = 500.0
                if cv2.waitKey(max(1, int(dt))) & 0xFF == ord("q"):
                    raise KeyboardInterrupt
            print("[replay] loop %d/%d done" % (loop + 1, args.loops), flush=True)
    except KeyboardInterrupt:
        print("[replay] stopped early", flush=True)
    finally:
        cv2.destroyAllWindows()
        slog.close()
    print("[replay] shown-frame ground-truth log ->", shown_log.name, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
