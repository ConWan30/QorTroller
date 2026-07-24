"""CFB27 play-event extractor (CANDIDATE proxy) — OCR-free snap-adjacent event timestamps.

Produces the GAME-EVENT half of the U3 real-play-liveness correlation from captured frames, so the
optical co-presence / Composite-B CANDIDATE thresholds can start becoming measured. No tesseract on
this box, so this is change-detection on the scoreboard's down-&-distance region — NOT digit OCR.

WHAT IT DETECTS (honest scope):
  A **play-transition event** = the moment the scoreboard's down-&-distance strip ("4th & inches" ->
  "1st & 10" ...) changes, i.e. a new play's down/distance was set. That is a snap-ADJACENT proxy,
  not the exact snap instant, and not a label-verified snap. At ~5fps the timestamp is +/-200ms.

WHAT IT IS NOT:
  * NOT ground-truth snap detection (no labels; a penalty/replayed-down may not change the text;
    a cinematic/replay that hides the scoreboard then restores it is a false-positive risk — gated
    by the scoreboard-presence check but not eliminated).
  * NOT a calibrator — emitting events != flipping calibrated=True. Advisory measurement input only.

Design: the event-detection CORE (`detect_play_events`) is a PURE function over precomputed
(ts, present, signature) samples — unit-testable with no images. The runner does frame I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

try:
    import numpy as np
except Exception:  # noqa: BLE001 — numpy always present in the bridge env; guard for import-time safety
    np = None  # type: ignore


@dataclass(frozen=True, slots=True)
class ScoreboardROI:
    """Fractional (of full frame) rectangles for the CFB27 bottom-center scoreboard, calibrated
    against the run1_cfb27 capture (1920x1080). fx,fy,fw,fh in [0,1]."""
    # down & distance strip ("4th & inches") — the per-play change signal. Calibrated against the
    # run1_cfb27 capture: tightly on the RED text strip (a lower/looser box captures the black area
    # BELOW the text and the signature stops changing between plays — the r02 under-detection bug).
    downdist: tuple[float, float, float, float] = (0.43, 0.883, 0.14, 0.026)
    # game-clock center box — used for the scoreboard-PRESENT gate (bright box when HUD is up)
    presence: tuple[float, float, float, float] = (0.455, 0.855, 0.09, 0.045)


# CANDIDATE thresholds (hypotheses tuned against the N=1 capture — NOT calibrated ground-truth)
DEFAULT_CHANGE_THR: float = 25.0      # mean abs delta on the BINARIZED down&distance text sig -> a play
DEFAULT_DEBOUNCE_S: float = 3.0       # min seconds between distinct play events (flicker guard)
DEFAULT_PRESENCE_MIN_BRIGHT: float = 60.0   # mean brightness of the presence box to count HUD as up
DEFAULT_MIN_PRESENT_RUN: int = 2      # need N consecutive present frames before trusting a change


@dataclass
class PlayEvent:
    ts_s: float
    method: str = "downdist_change"
    change_score: float = 0.0
    def to_dict(self) -> dict:
        return {"ts_s": round(self.ts_s, 3), "method": self.method,
                "change_score": round(self.change_score, 2), "kind": "play_transition_proxy"}


@dataclass(frozen=True, slots=True)
class Sample:
    ts_s: float
    present: bool
    signature: Optional["np.ndarray"]   # small grayscale vector of the down&distance ROI, or None


def signature_distance(a, b) -> float:
    """Mean absolute grayscale delta between two down&distance signatures (0..255)."""
    if a is None or b is None or np is None:
        return 0.0
    if a.shape != b.shape:
        return 255.0
    return float(np.mean(np.abs(a.astype("int16") - b.astype("int16"))))


def detect_play_events(
    samples: Sequence[Sample],
    change_thr: float = DEFAULT_CHANGE_THR,
    debounce_s: float = DEFAULT_DEBOUNCE_S,
    min_present_run: int = DEFAULT_MIN_PRESENT_RUN,
) -> list[PlayEvent]:
    """PURE core. A play-transition event fires when the down&distance signature changes by
    >= change_thr between two frames that are BOTH in a run of >= min_present_run present frames,
    debounced by debounce_s. Absent->present transitions do NOT fire (that's HUD reappearing, not a
    play), which is the scoreboard-cutscene false-positive guard."""
    events: list[PlayEvent] = []
    present_run = 0
    last_sig = None
    last_event_ts = -1e9
    for s in samples:
        if not s.present or s.signature is None:
            present_run = 0
            last_sig = None          # break continuity across HUD-absent gaps (no cross-gap event)
            continue
        present_run += 1
        if last_sig is not None and present_run >= min_present_run:
            d = signature_distance(s.signature, last_sig)
            if d >= change_thr and (s.ts_s - last_event_ts) >= debounce_s:
                events.append(PlayEvent(ts_s=s.ts_s, change_score=d))
                last_event_ts = s.ts_s
        last_sig = s.signature
    return events


# ---- frame-side helpers (need numpy/cv2; the runner uses these, tests use detect_play_events) ----

def crop_frac(frame, rect: tuple[float, float, float, float]):
    h, w = frame.shape[:2]
    fx, fy, fw, fh = rect
    x0, y0 = int(w * fx), int(h * fy)
    x1, y1 = int(w * (fx + fw)), int(h * (fy + fh))
    return frame[y0:y1, x0:x1]


def downdist_signature(frame, roi: ScoreboardROI, cv2mod, size=(120, 20), text_thr: int = 140):
    """BINARIZED white-text signature of the down&distance strip. Raw grayscale under-detects because
    white-on-red text of similar density ("2ND & 3" vs "3RD & 2") barely moves the mean; thresholding
    to the text mask makes the character-PATTERN change register. Stable per play; changes on new play."""
    crop = crop_frac(frame, roi.downdist)
    g = cv2mod.cvtColor(crop, cv2mod.COLOR_BGR2GRAY)
    _, b = cv2mod.threshold(g, text_thr, 255, cv2mod.THRESH_BINARY)
    return cv2mod.resize(b, size)


def scoreboard_present(frame, roi: ScoreboardROI, cv2mod,
                       min_bright: float = DEFAULT_PRESENCE_MIN_BRIGHT) -> bool:
    """HUD-present gate: the center game-clock box is a bright element when the scoreboard is up;
    during full-field cinematics / replays / menus it's dark or absent."""
    crop = crop_frac(frame, roi.presence)
    g = cv2mod.cvtColor(crop, cv2mod.COLOR_BGR2GRAY)
    return float(g.mean()) >= min_bright
