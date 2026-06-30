"""QorTroller L9 — Kill-feed authorship CV (color-agnostic, fail-closed; CALIBRATION-STAGE).

The anti-spectate differentiator is SEMANTIC: your own handle appearing as the KILLER (left slot) of a
kill-feed row means you authored that kill in your OWN game — correlation can't prove this (cycle-56). Two
hard constraints from the live ground-truth frames + operator review shape this module:

  1. COLOR IS OUT. The local-player slot color is NOT match-stable (it can be yellow/red/green/blue in a
     random match), so nothing here keys on color — neither matching nor locating. The only invariant is the
     GLYPH SHAPE of the handle text, matched after binarization.
  2. KILLER-LEFT / VICTIM-RIGHT is VERIFIED from real frames (kf_kill1: own handle left = killer;
     kf_kill2: teammates left, own handle absent). Own handle counts ONLY in the left/killer slot.

STATUS: CALIBRATION-STAGE, FAIL-CLOSED. On the current N=2 ground truth the roster-anchor->feed binarized
match does NOT yet separate authored from spectated (documented in test_killfeed_cv). Until a dense
feed-crop corpus (see qortroller_retina_capture dense capture) calibrates the match floor, classify_feed()
returns UNVERIFIABLE below a conservative floor — NEVER a guessed AUTHORED, never a guessed SPECTATED. A
false-positive authorship label corrupts the corpus labeller, so ambiguity fails to UNVERIFIABLE.

PURE + cv2-guarded: no FROZEN-v1 / 228B PoAC / chain / IOTX. Advisory presence-authorship only. The handle
comes from QORTROLLER_HANDLE via killfeed_authorship.default_handle (single source of the only name used).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .killfeed_authorship import AuthorshipVerdict, default_handle

# Conservative match floor. Set deliberately HIGH so the un-calibrated scaffold abstains rather than guesses
# — on the N=2 frames the genuine feed match scored ~0.39, well under this, so it correctly fails closed to
# UNVERIFIABLE. A dense-corpus calibration cycle lowers/justifies this with a measured FAR-safe threshold.
DEFAULT_MATCH_FLOOR = float(os.getenv("KILLFEED_CV_MATCH_FLOOR", "0.62"))
# killer occupies the LEFT of a feed row (verified); a confident match whose centre is left of this fraction
# is the killer slot -> authorship-eligible. Right of it = victim (your death) -> neutral, never authored.
KILLER_MAX_FRAC = float(os.getenv("KILLFEED_CV_KILLER_MAX_FRAC", "0.5"))
_SCALES = (0.6, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 1.7)


@dataclass
class CvAuthorshipResult:
    verdict: AuthorshipVerdict
    score: float                 # best multi-scale normalized match score (0..1)
    x_frac: Optional[float]      # match-centre x as a fraction of the feed width (None if no match attempted)
    killer_slot: Optional[bool]  # True=left/killer, False=right/victim, None=undetermined
    handle: str
    note: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"verdict": self.verdict.value, "score": round(self.score, 4), "x_frac": self.x_frac,
                "killer_slot": self.killer_slot, "handle": self.handle, "note": self.note,
                "evidence": self.evidence}


def save_crop_bounded(out_dir: str, prefix: str, bgr, ts_ns: Optional[int] = None,
                      max_files: int = 600) -> Optional[str]:
    """Write a crop PNG to out_dir/<prefix>_<ts_ns>.png and prune oldest <prefix>_*.png beyond max_files —
    a bounded RING so a long match can't fill the disk. Used by the dense feed/roster crop capture to build
    the offline-review corpus the killfeed detector needs. cv2-guarded; never raises (returns None on any
    failure). max_files <= 0 disables (returns None)."""
    if bgr is None or max_files <= 0:
        return None
    try:
        import glob
        import time as _t

        import cv2
        os.makedirs(out_dir, exist_ok=True)
        ts = ts_ns if ts_ns is not None else _t.time_ns()
        path = os.path.join(out_dir, f"{prefix}_{int(ts)}.png")
        if not cv2.imwrite(path, bgr):
            return None
        existing = sorted(glob.glob(os.path.join(out_dir, f"{prefix}_*.png")))
        for old in existing[:-max_files]:        # keep the newest max_files, prune the rest
            try:
                os.remove(old)
            except OSError:
                pass
        return path
    except Exception:
        return None


def binarize_glyphs(bgr):
    """Color-agnostic glyph binarization: grayscale -> contrast-stretch -> Otsu, text rendered WHITE on
    black regardless of the original glyph colour. Returns a uint8 {0,255} image, or None on bad input.
    This is the whole point of the color constraint — yellow/red/green/blue handles binarize identically."""
    try:
        import cv2
        import numpy as np
        if bgr is None or getattr(bgr, "size", 0) == 0:
            return None
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
        g = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if bw.mean() > 127:          # text is the minority ink -> keep glyphs white
            bw = 255 - bw
        return bw
    except Exception:
        return None


def load_anchor(path: Optional[str]):
    """Load + binarize a saved handle anchor crop (the operator-extracted glyphs of the own handle). Returns
    the binarized template or None (missing/unreadable/cv2 absent) -> classify fail-closes to UNVERIFIABLE."""
    if not path or not os.path.exists(path):
        return None
    try:
        import cv2
        return binarize_glyphs(cv2.imread(path))
    except Exception:
        return None


def multiscale_match(anchor_bw, target_bw, scales=_SCALES):
    """Best multi-scale normalized template match of a binarized anchor against a binarized target.
    Returns (score, cx, cy, scale) with cx/cy the match-box CENTRE in target pixels, or (0.0, None, None,
    None) if no scale fits / inputs bad. Pure (cv2)."""
    try:
        import cv2
        if anchor_bw is None or target_bw is None:
            return 0.0, None, None, None
        best = (0.0, None, None, None)
        th, tw = target_bw.shape[:2]
        for s in scales:
            import cv2 as _cv
            a = _cv.resize(anchor_bw, None, fx=s, fy=s, interpolation=_cv.INTER_NEAREST)
            ah, aw = a.shape[:2]
            if ah >= th or aw >= tw or ah < 4 or aw < 4:
                continue
            res = cv2.matchTemplate(target_bw, a, cv2.TM_CCOEFF_NORMED)
            _, mx, _, mxloc = cv2.minMaxLoc(res)
            if mx > best[0]:
                best = (float(mx), int(mxloc[0] + aw / 2), int(mxloc[1] + ah / 2), round(float(s), 2))
        return best
    except Exception:
        return 0.0, None, None, None


def classify_feed(feed_bgr, anchor_bw, *, handle: Optional[str] = None,
                  match_floor: float = DEFAULT_MATCH_FLOOR,
                  killer_max_frac: float = KILLER_MAX_FRAC) -> CvAuthorshipResult:
    """Classify a kill-feed ROI crop for own-handle authorship — FAIL-CLOSED.

    AUTHORED_PRESENT  iff a confident (>= match_floor) glyph match lands in the LEFT/killer slot.
    OWN_KILL_UNBOUND  (reused as 'own handle as VICTIM') iff a confident match lands in the right/victim slot
                      — that's your death, neutral, NOT authorship.
    UNVERIFIABLE      otherwise — below the floor we CANNOT distinguish 'handle absent' from 'match failed',
                      so we never emit SPECTATED here (that would risk a false negative becoming a label).
    """
    h = handle or default_handle()
    if anchor_bw is None:
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, 0.0, None, None, h,
                                  "no anchor template (fail-closed)")
    target = binarize_glyphs(feed_bgr)
    if target is None:
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, 0.0, None, None, h,
                                  "feed crop unreadable (fail-closed)")
    score, cx, cy, scale = multiscale_match(anchor_bw, target)
    tw = target.shape[1]
    x_frac = (cx / tw) if (cx is not None and tw) else None
    killer_slot = (x_frac is not None and x_frac < killer_max_frac)
    ev = {"match_floor": match_floor, "scale": scale, "feed_w": int(tw)}
    if score < match_floor:
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, score, x_frac, killer_slot, h,
                                  f"match {score:.3f} < floor {match_floor:.2f} — abstain (uncalibrated)", ev)
    if killer_slot:
        return CvAuthorshipResult(AuthorshipVerdict.AUTHORED_PRESENT, score, x_frac, True, h,
                                  "own handle matched in KILLER (left) slot — authored", ev)
    return CvAuthorshipResult(AuthorshipVerdict.OWN_KILL_UNBOUND, score, x_frac, False, h,
                              "own handle matched in VICTIM (right) slot — your death, neutral", ev)
