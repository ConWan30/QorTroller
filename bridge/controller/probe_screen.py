"""Screen-side stoppage detector for NCAA CFB 26 (pure classifier + optional OCR reader).

The heaviest, most semantic lull source: read the on-screen play state. Football has a
very legible rhythm -- a play clock counts down pre-snap (quiet, hands waiting = ideal
probe window), and stoppages show explicit banners (TIMEOUT / OFFICIAL / REVIEW / etc).

Split, as everywhere else, into a PURE classifier (text -> verdict; fully testable) and an
OPTIONAL edge reader that uses the existing screen-capture pipeline + pytesseract. The
reader degrades to None when OCR or capture deps are absent, so this never hard-fails the
challenger -- it's an opt-in enhancement, not a dependency.

HONESTY: OCR on a streamed game (PS Remote Play) is noisy; treat the screen verdict as a
SUPPORTING vote (AND-ed with the IMU lull-gate), never the sole authority. The play-clock
read in particular can misfire on HUD occlusion; PRE_SNAP requires a plausible 0-40 value.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class ScreenVerdict(str, Enum):
    PRE_SNAP = "PRE_SNAP"    # play clock counting down, ball not snapped -> ideal probe window
    STOPPAGE = "STOPPAGE"    # timeout / review / official stoppage -> quiet window
    LIVE = "LIVE"            # play in progress (game clock running, no play clock) -> defer
    UNKNOWN = "UNKNOWN"      # nothing legible -> defer (fail-safe)


_STOPPAGE_PAT = re.compile(
    r"\b(time ?out|official|review|injury|measurement|challenge flag|"
    r"end of (quarter|half)|two ?minute warning|commercial)\b", re.IGNORECASE)
_PLAYCLOCK_PAT = re.compile(r"\bplay ?clock\b[^0-9]{0,8}(\d{1,2})", re.IGNORECASE)
_BARE_SMALL_INT = re.compile(r"\b([0-3]?\d)\b")  # 0..39 (play clock max is 40)


def classify_screen(text: Optional[str], *, playclock_value: Optional[int] = None) -> ScreenVerdict:
    """Classify a screen-region OCR string (and/or a parsed play-clock value).

    Precedence: explicit stoppage banner > a valid pre-snap play clock (1..40) > LIVE/UNKNOWN.
    A play-clock value at 0 is the snap boundary, NOT a safe pre-snap window."""
    if playclock_value is not None and 1 <= playclock_value <= 40:
        pc_verdict: Optional[ScreenVerdict] = ScreenVerdict.PRE_SNAP
    else:
        pc_verdict = None

    if text:
        if _STOPPAGE_PAT.search(text):
            return ScreenVerdict.STOPPAGE
        m = _PLAYCLOCK_PAT.search(text)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 40:
                return ScreenVerdict.PRE_SNAP

    if pc_verdict is not None:
        return pc_verdict
    return ScreenVerdict.UNKNOWN


def clear_to_fire_screen(text: Optional[str], *, playclock_value: Optional[int] = None,
                         allow_stoppage: bool = True) -> tuple[bool, ScreenVerdict]:
    """True for a good on-screen probe window: PRE_SNAP always; STOPPAGE if allowed."""
    v = classify_screen(text, playclock_value=playclock_value)
    clear = v is ScreenVerdict.PRE_SNAP or (allow_stoppage and v is ScreenVerdict.STOPPAGE)
    return clear, v


def read_screen_region(region: tuple[int, int, int, int]) -> Optional[str]:
    """OPTIONAL edge reader: grab `region` (x, y, w, h) and OCR it. Returns the text, or
    None if screen-capture or pytesseract isn't available (caller treats None as inert).

    Kept dependency-light + guarded: nothing here is imported unless this is called."""
    try:
        import pytesseract  # type: ignore
        from .screen_capture import ScreenCapturer  # reuse the cocapture grabber
    except Exception:
        return None
    try:
        cap = ScreenCapturer(region=region, backend="mss")
        frame = cap.grab()
        cap.close()
        if frame is None:
            return None
        return pytesseract.image_to_string(frame)
    except Exception:
        return None
