#!/usr/bin/env python3
"""G2' replay gate — drive the REAL wired session-anchor path over an archived match's crops (timestamp
order), OCR-bootstrap ON vs OFF, and report bootstrap->cut->promote + post-promotion recall. READ-ONLY: no
daemon, no live capture, no chain/IOTX; constructs a bare RetinaGameCapture (bypassing WGC __init__, same as
the wiring test) with the real InlineAuthorshipMonitor + SessionAnchorGenerator so the exact production
_session_anchor_fold logic runs — offline and live cannot diverge.

The gate question: does the OCR-verified bootstrap catch+cut+promote where the marginal feed_v1 template
(max 0.566 this session) could not, and what is the post-promotion killer-slot recall? Pre-registered
expectation: OCR-ON promotes on this archive (feed_v1-OFF baseline may not), post-promotion recall near the
offline-59, kills-before-promotion counted as the honest R1 coverage gap.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(_REPO, "bridge"), _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

import cv2  # noqa: E402

from l9_presence import killfeed_cv as kc  # noqa: E402
from l9_presence.killfeed_inline import InlineAuthorshipMonitor  # noqa: E402
from l9_presence.killfeed_session_anchor import SessionAnchorGenerator  # noqa: E402
from vapi_bridge.qortroller_retina_capture import RetinaGameCapture  # noqa: E402

_TS = re.compile(r"panel_(\d+)")


def _ts_of(path: str) -> int:
    m = _TS.search(os.path.basename(path))
    return int(m.group(1)) if m else 0


def _bare_rgc(anchor, archive_dir: str, ocr_on: bool):
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)
    rgc._inline_monitor = InlineAuthorshipMonitor(match_floor=0.66, killer_max_frac=0.28,
                                                  feed_region_max_yfrac=0.42, anchor_id="feed_v1")
    rgc._session_anchor = SessionAnchorGenerator(session_id="replay", killer_max_frac=0.28,
                                                 feed_region_max_yfrac=0.42, k_consistency=3)
    rgc._anchor = anchor
    rgc._prev_killer_gray = None
    rgc._last_killer_fresh_ms = -1e18
    rgc._session_anchor_dir = archive_dir
    rgc._ocr_bootstrap_enabled = bool(ocr_on)
    return rgc


def replay(crops, anchor, archive_dir: str, ocr_on: bool) -> dict:
    rgc = _bare_rgc(anchor, archive_dir, ocr_on)
    gen, mon = rgc._session_anchor, rgc._inline_monitor
    mon.mark_onset(0.0)                                  # one long R2 window so folds accumulate
    catch_i = promote_i = None
    kills_before_promotion = 0
    post_promo_recall = 0
    for i, p in enumerate(crops):
        bgr = cv2.imread(p)
        if bgr is None:
            continue
        now_ms = float(i * 100)
        res = kc.classify_panel(bgr, rgc._anchor)       # feed_v1 result (victim path + ev)
        pre = gen.regime
        rgc._session_anchor_fold(bgr, res, res.evidence or {}, now_ms)
        if catch_i is None and gen.regime != "BOOTSTRAP" and pre == "BOOTSTRAP":
            catch_i = i
        if promote_i is None and gen.is_promoted():
            promote_i = i
        # honest R1 coverage gap: fresh killer rows seen while still pre-promotion
        if not gen.is_promoted():
            sc, cx, cy = kc.killer_slot_best(bgr, rgc._anchor)
            if cx is not None and cx < 0.28 and cy < 0.42 and sc >= 0.55:
                kills_before_promotion += 1
        else:
            act = gen.active_anchor()
            if act is not None:
                sc, cx, cy = kc.killer_slot_best(bgr, act)
                if cx is not None and cx < 0.28 and cy < 0.42 and sc >= 0.66:
                    post_promo_recall += 1
    st = gen.status()
    return {"ocr_on": ocr_on, "n_crops": len(crops), "catch_crop": catch_i, "promote_crop": promote_i,
            "promoted": gen.is_promoted(), "bootstrap_source": st["bootstrap_source"],
            "bootstrap_catches": st["bootstrap_catches"], "promotions": st["promotions"],
            "fp_fires": st["fp_fires"], "demotions": st["demotions"],
            "kills_before_promotion": kills_before_promotion, "post_promotion_recall": post_promo_recall,
            "coverage_note": gen.coverage_note()}


def main():
    ap = argparse.ArgumentParser(description="G2' session-anchor replay gate (read-only).")
    ap.add_argument("--crops", default="retina_kf_crops")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--stride", type=int, default=1, help="sample every Nth crop — mimic the LIVE sparse "
                    "R2-gated classify rate (dense replay masks feed_v1's fragile 2/150 catch)")
    ap.add_argument("--anchor", default="l9_presence/assets/own_handle_anchor_feed.png")
    a = ap.parse_args()
    crop_dir = a.crops if os.path.isabs(a.crops) else os.path.join(_REPO, a.crops)
    crops = sorted(glob.glob(os.path.join(crop_dir, "panel_*.png")), key=_ts_of)
    if a.stride > 1:
        crops = crops[::a.stride]
    if a.limit > 0:
        crops = crops[:a.limit]
    anchor = kc.load_anchor(os.path.join(_REPO, a.anchor))
    archive = os.path.join(_REPO, "retina_kf_anchors")
    print(f"replaying {len(crops)} crops (ts-ordered) from {crop_dir}\n")
    import json
    for ocr_on in (False, True):                        # baseline first, then the OCR-bootstrap fix
        r = replay(crops, anchor, archive, ocr_on)
        print(f"=== OCR bootstrap {'ON' if ocr_on else 'OFF (baseline)'} ===")
        print(json.dumps(r, indent=2))
        print()


if __name__ == "__main__":
    main()
