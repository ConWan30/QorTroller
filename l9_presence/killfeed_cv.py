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

# Match floor — CALIBRATED on a 243-crop full-res Warzone corpus (2026-06-30): background scores p95=0.658,
# genuine own-handle matches 0.682-0.856 -> a 0.66 floor cleanly separates present from absent (no false
# AUTHORED across 243 crops). The prior 0.62 was a pre-corpus placeholder. Env-overridable.
DEFAULT_MATCH_FLOOR = float(os.getenv("KILLFEED_CV_MATCH_FLOOR", "0.66"))
# killer occupies the LEFT of a feed row (verified). For a PRE-CROPPED tight feed strip, killer is the left
# half (classify_feed default). For the full LEFT-PANEL crop (classify_panel), the feed row occupies only the
# left portion, so the killer/victim boundary is CALIBRATED to frac 0.28 (measured natural gap: killers
# cluster at x-frac 0.18, victims at 0.38-0.55 -> a 0.20-wide gap centred at 0.279).
KILLER_MAX_FRAC = float(os.getenv("KILLFEED_CV_KILLER_MAX_FRAC", "0.5"))
KILLER_MAX_FRAC_PANEL = float(os.getenv("KILLFEED_CV_KILLER_MAX_FRAC_PANEL", "0.28"))
# In the panel crop, feed rows sit in the upper region (y-frac 0.31-0.47) and the persistent squad roster in
# the lower region (y-frac ~0.97). A match ABOVE this y-frac is a feed event; below it is roster presence
# (persistent, NOT a kill) -> neutral. CALIBRATED on the same corpus.
FEED_REGION_MAX_YFRAC = float(os.getenv("KILLFEED_CV_FEED_MAX_YFRAC", "0.42"))
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


def killer_slot_best(panel_bgr, anchor_bw, *, killer_max_frac: float = KILLER_MAX_FRAC_PANEL,
                     feed_region_max_yfrac: float = FEED_REGION_MAX_YFRAC):
    """Region-RESTRICTED best match: max normalized-template score whose match-box centre lands in the
    KILLER slot (x_frac < killer_max_frac) AND the feed region (y_frac < feed_region_max_yfrac). Unlike
    multiscale_match's GLOBAL best (which the persistent roster entry can win, masking a feed kill), this
    isolates the killer-slot signal the per-session anchor generator gates on. Returns (score, x_frac,
    y_frac) or (0.0, None, None). Pure (cv2+numpy)."""
    try:
        import cv2
        import numpy as np
        target = binarize_glyphs(panel_bgr)
        if target is None or anchor_bw is None:
            return 0.0, None, None
        th, tw = target.shape[:2]
        best = (0.0, None, None)
        for s in _SCALES:
            a = cv2.resize(anchor_bw, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
            ah, aw = a.shape[:2]
            if ah >= th or aw >= tw or ah < 4 or aw < 4:
                continue
            res = cv2.matchTemplate(target, a, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.mgrid[0:res.shape[0], 0:res.shape[1]]
            cxf = (xs + aw / 2.0) / tw
            cyf = (ys + ah / 2.0) / th
            mask = (cyf < feed_region_max_yfrac) & (cxf < killer_max_frac)
            if mask.any():
                idx = int(np.argmax(np.where(mask, res, -1.0)))
                r, c = np.unravel_index(idx, res.shape)
                sc = float(res[r, c])
                if sc > best[0]:
                    best = (sc, float((c + aw / 2.0) / tw), float((r + ah / 2.0) / th))
        return best
    except Exception:
        return 0.0, None, None


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


def classify_panel(panel_bgr, anchor_bw, *, handle: Optional[str] = None,
                   match_floor: float = DEFAULT_MATCH_FLOOR,
                   killer_max_frac: float = KILLER_MAX_FRAC_PANEL,
                   feed_region_max_yfrac: float = FEED_REGION_MAX_YFRAC) -> CvAuthorshipResult:
    """Calibrated authorship classifier over the DENSE-CAPTURE LEFT PANEL crop (feed + roster), FAIL-CLOSED.

    Thresholds measured on a 243-crop full-res Warzone corpus (2026-06-30), validated against labelled
    ground truth (own-kill -> AUTHORED; own-death + roster-presence + background -> not authored; ZERO false
    AUTHORED). Two calibrated geometry gates on top of the match floor:
      * feed vs roster: a match ABOVE feed_region_max_yfrac (upper region) is a live feed event; below it is
        the persistent squad-roster entry (presence, not a kill) -> UNVERIFIABLE-for-authorship.
      * killer vs victim: within the feed, own handle left of killer_max_frac is the KILLER slot -> AUTHORED;
        right of it is the VICTIM slot (your death) -> neutral. The panel boundary (0.28) is TIGHTER than a
        tight-strip 0.5 because the feed row occupies only the left portion of the wider panel — using 0.5
        here would misclassify a death as a kill (the false-positive that corrupts the labeller).

    Verdicts: AUTHORED_PRESENT (own kill) | OWN_KILL_UNBOUND (own death, neutral — evidence.region='feed',
    slot='victim') | UNVERIFIABLE (roster presence, or below floor). evidence carries region/slot/score so
    the offline labeller can bucket own-kill vs own-death vs neither.
    """
    h = handle or default_handle()
    if anchor_bw is None:
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, 0.0, None, None, h,
                                  "no anchor template (fail-closed)")
    target = binarize_glyphs(panel_bgr)
    if target is None:
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, 0.0, None, None, h,
                                  "panel crop unreadable (fail-closed)")
    score, cx, cy, scale = multiscale_match(anchor_bw, target)
    ph, pw = target.shape[:2]
    x_frac = (cx / pw) if (cx is not None and pw) else None
    y_frac = (cy / ph) if (cy is not None and ph) else None
    ev = {"match_floor": match_floor, "scale": scale, "x_frac": x_frac, "y_frac": y_frac,
          "killer_max_frac": killer_max_frac, "feed_region_max_yfrac": feed_region_max_yfrac}
    if score < match_floor:
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, score, x_frac, None, h,
                                  f"match {score:.3f} < floor {match_floor:.2f} — no confident handle", ev)
    if y_frac is None or y_frac >= feed_region_max_yfrac:
        ev["region"] = "roster"
        return CvAuthorshipResult(AuthorshipVerdict.UNVERIFIABLE, score, x_frac, None, h,
                                  "own handle in ROSTER region — persistent presence, not a kill", ev)
    ev["region"] = "feed"
    killer_slot = x_frac is not None and x_frac < killer_max_frac
    if killer_slot:
        ev["slot"] = "killer"
        return CvAuthorshipResult(AuthorshipVerdict.AUTHORED_PRESENT, score, x_frac, True, h,
                                  "own handle in feed KILLER (left) slot — authored kill", ev)
    ev["slot"] = "victim"
    return CvAuthorshipResult(AuthorshipVerdict.OWN_KILL_UNBOUND, score, x_frac, False, h,
                              "own handle in feed VICTIM (right) slot — your death, neutral", ev)


def cut_killer_name_anchor(panel_bgr, kxf, kyf, *, pad_y: int = 20, pad_x: int = 90, col_gap: int = 6):
    """Scale-aware KILLER-NAME anchor cut with a live quality gate (G3 matches 2+3 fix). Returns a binarized
    anchor or None (None -> caller stays BOOTSTRAP and waits for the next kill row).

    WHY (validated on the 19-kill BR archive 2026-07-03): the old fixed +/-72x14px box was implicitly sized
    for MP's larger rows; on BR's smaller rows it swept in the weapon icon / victim columns and produced
    weak anchors (0-2/18 recall). Structure of the fix:
      1. generous box around the located killer signal;
      2. COLUMN-CLUSTER: keep only the glyph cluster containing the match centre (the killer name),
         splitting on >=col_gap empty columns — drops icon/victim bleed;
      3. row-tighten to the glyph band;
      4. QUALITY GATE (the live-checkable signature of every K=3-capable cut in the archive sweep —
         accepted 5/19, 5/5 promoted-capable; every dud rejected):
           - vertical isolation: tightened height < 0.85 * box height (hitting the box bounds means the row
             was not isolated — multi-row / noisy binarization);
           - name-plausible width 60..200px (rejects fragments and multi-slot bleeds; spans BR ~95px and
             MP ~145px renderings).
    Pure (cv2+numpy); fail-open None."""
    try:
        import numpy as np
        h, w = panel_bgr.shape[:2]
        if kxf is None or kyf is None:
            return None
        cx, cy = int(kxf * w), int(kyf * h)
        x0g = max(0, cx - pad_x)
        crop = panel_bgr[max(0, cy - pad_y):min(h, cy + pad_y), x0g:min(w, cx + pad_x)]
        a = binarize_glyphs(crop)
        if a is None:
            return None
        col = a.sum(axis=0) > 0
        if int(col.sum()) < 20:
            return None
        idx = np.where(col)[0]
        splits = np.where(np.diff(idx) > col_gap)[0]
        clusters = np.split(idx, splits + 1)
        centre = cx - x0g
        keep = None
        for c in clusters:
            if c[0] - col_gap <= centre <= c[-1] + col_gap:
                keep = c
                break
        if keep is None:
            keep = max(clusters, key=len)
        x0, x1 = max(0, int(keep[0]) - 2), min(a.shape[1], int(keep[-1]) + 3)
        sub = a[:, x0:x1]
        ys = np.nonzero(sub.sum(axis=1))[0]
        if len(ys) == 0:
            return None
        t = sub[max(0, int(ys.min()) - 2):int(ys.max()) + 3, :]
        if t.shape[0] > 0.85 * a.shape[0]:      # row not vertically isolated -> reject
            return None
        if not (60 <= t.shape[1] <= 200):        # fragment / multi-slot bleed -> reject
            return None
        if t.shape[0] < 6:
            return None
        return t
    except Exception:
        return None
