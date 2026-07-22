# A2A round 02 — ASM-Loop auditor packet: CFB snap-event extractor

You are the AUDITOR in an A2A verification loop. The builder produced the work below with a numbered
claims list. Break the claims — do not be agreeable, do not rewrite.

Rules: attack each C1..Cn individually (cite files/lines); return F1..Fn tagged BLOCK/WARN/INFO;
look hardest for over-claims, untested paths presented as tested, and ambiguity; end with ONE
verdict HOLD or PASS; unverifiable-as-presented = WARN not pass. Write findings to
`docs/a2a/cfb-snap-extractor/round-03-grok-audit.md`.

Context: QorTroller, branch feat/l9-consistency-adversarial-harness. This produces the GAME-EVENT
half of the U3 real-play-liveness measurement from the captured frames
(`~/.vapi/u3_captures/run1_cfb27_20260721`: 1139 frames @~5fps + 7129 HID events, live CFB27).
Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator. Advisory
offline analysis only.

## Work delivered
- `l9_presence/cfb_snap_extractor.py` — OCR-free play-transition detector (no tesseract on this box).
  Pure core `detect_play_events(samples, ...)` over (ts, present, signature); frame helpers
  `downdist_signature` (BINARIZED white-text mask of the down&distance strip), `scoreboard_present`
  (HUD gate via center-box brightness). ScoreboardROI calibrated to the capture.
- `scripts/cfb_extract_snaps.py` — runner → `snap_events.jsonl` (17 events written for run1).
- `bridge/tests/test_cfb_snap_extractor.py` — 7 pure-core tests (green).

## Validation done
- Ground truth: a filmstrip of the scoreboard every 8s was read by eye = ~16 distinct plays
  (KICKOFF→1st&10→2nd&3→3rd&2→4th&inches→1st&10→2nd&9→3rd&9→4th&5→1st&10→2nd&18→FLAG→2nd&18→
  1st&10→2nd&11→[quarter break 192s]→1st&10→2nd&12).
- Detector output: 17 events at [11,34,47,57,69,87,97,108,118,129,140,176,187,192,215,226,235]s —
  aligns with the ground-truth transitions (incl. the 192s quarter-break HUD change).
- First correlation with input (R2 press onsets, football window 0.5–8s, via
  l9_presence/optical_copresence): hit_rate=0.82, null_q95=0.88 → **event_coupled=FALSE**.

## Numbered claims (attack these)
- **C1.** The extractor detects CFB play-transition events OCR-free via binarized down&distance
  change-detection; against run1 it found 17 events aligning with ~16 eyeballed ground-truth plays.
- **C2.** The first ROI under-detected (4–6 events) because it sat too low, capturing the black area
  BELOW the red text strip (signature barely changed); the corrected ROI (0.43,0.883,0.14,0.026) +
  binarized white-text signature fixed it to 17. This is stated as a real bug found + fixed.
- **C3.** The correlation is a MEASURED NEGATIVE, not a validation: naive "any R2 press within
  0.5–8s of a play-transition" does NOT beat the circular-shift null (0.82 < 0.88) — with frequent
  R2 (37) and a wide window the null is too high. It does NOT show session co-presence for football
  and is NOT claimed to.
- **C4.** It is a CANDIDATE **proxy**: a down&distance CHANGE is snap-ADJACENT, not the exact snap
  instant; ~5fps → ±200ms; N=1 session; not label-verified frame-by-frame; penalties/quarter-breaks
  can false-fire (the 192s event is the quarter-break HUD change, not a play).
- **C5.** The pure event-detection core is unit-tested (7 tests incl. debounce, absent→present
  guard, min-present-run gate); the ROI + thresholds are tuned-against-N=1 hypotheses, NOT
  calibrated ground truth.
- **C6.** Advisory/offline only — does not flip `calibrated=True` or any protocol flag, no chain, no
  FROZEN/PoAC edit, PV-CI 184 unchanged, imported by no live path.
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

from dataclasses import dataclass, field
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
