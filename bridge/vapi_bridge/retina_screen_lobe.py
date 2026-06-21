"""QorTroller × Trio-Retina — SCREEN (outcome) lobe (pure logic).

The controller lobe (retina_controller_embedder.py) encodes the INPUT world: what the
hands did, as retina WorldState/Events. This lobe encodes the OUTCOME world: what the game
SHOWED, parsed from the HUD via OCR. For NCAA CFB the HUD is dense + discrete + legible
(down & distance, play clock, score, quarter) -- the ideal first retina detector beyond the
controller stream, and the cheapest of retina's native detector menu (vs YOLO/VLM/DINO).

The point is NOT "also run OCR." It is to produce a parallel stream of OUTCOME events that
the causal-coherence fusion (retina_causal_coherence.py) checks against the controller's
INPUT events: every on-screen outcome must be explained by a preceding input from THIS
certified device. That cross-lobe binding is what catches replay-to-headless / relay.

Pure: OCR text -> HudState -> ScreenEvents. The OCR/screen-capture I/O lives at the edge
(probe_screen.read_screen_region / the cocapture pipeline). Default-off; no FROZEN/PoAC/
chain touch. Score parsing is best-effort and marked provisional; down/distance/play-clock
are the load-bearing, reliably-legible fields.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

SCHEMA_TAG = "vapi-retina-screen-v1"

# Outcome event types (namespace mirrors the controller lobe's "controller.*").
EVT_DOWN_ADVANCED = "scene.down_advanced"      # 1st->2nd etc.  -> input-caused (a play ran)
EVT_FIRST_DOWN = "scene.first_down"            # down reset to 1 -> input-caused
EVT_SCORE_CHANGED = "scene.score_changed"      # either score up -> input-caused
EVT_PLAYCLOCK_RESET = "scene.playclock_reset"  # snap boundary   -> marker (not input-required)
EVT_QUARTER_CHANGED = "scene.quarter_changed"  # time boundary   -> marker (not input-required)

# which outcomes the causal fusion REQUIRES a preceding input for
_INPUT_CAUSED = {EVT_DOWN_ADVANCED, EVT_FIRST_DOWN, EVT_SCORE_CHANGED}


@dataclass(frozen=True)
class HudState:
    down: Optional[int] = None          # 1..4
    distance: Optional[int] = None      # yards to go; GOAL -> 0
    play_clock: Optional[int] = None    # 0..40
    quarter: Optional[int] = None       # 1..4 (5+ OT)
    score_a: Optional[int] = None       # provisional (OCR of scoreboard is noisy)
    score_b: Optional[int] = None       # provisional


@dataclass(frozen=True)
class ScreenEvent:
    type: str
    t: float
    input_caused: bool
    ext: Optional[dict] = None


_DOWN_DIST = re.compile(r"\b([1-4])\s*(?:st|nd|rd|th)\s*&\s*(\d{1,2}|goal)\b", re.IGNORECASE)
_PLAYCLOCK = re.compile(r"\bplay ?clock\b[^0-9]{0,8}(\d{1,2})", re.IGNORECASE)
_QUARTER = re.compile(r"\b([1-4])\s*(?:st|nd|rd|th)\s+(?:qtr|quarter)\b", re.IGNORECASE)
_SCORE_PAIR = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b")  # "21-14" style; provisional


def parse_hud(text: Optional[str]) -> HudState:
    """Best-effort structured HUD from an OCR string. Missing fields stay None."""
    if not text:
        return HudState()
    down = distance = play_clock = quarter = score_a = score_b = None
    m = _DOWN_DIST.search(text)
    if m:
        down = int(m.group(1))
        dd = m.group(2).lower()
        distance = 0 if dd == "goal" else int(dd)
    m = _PLAYCLOCK.search(text)
    if m:
        v = int(m.group(1))
        if 0 <= v <= 40:
            play_clock = v
    m = _QUARTER.search(text)
    if m:
        quarter = int(m.group(1))
    m = _SCORE_PAIR.search(text)
    if m:
        score_a, score_b = int(m.group(1)), int(m.group(2))
    return HudState(down=down, distance=distance, play_clock=play_clock,
                    quarter=quarter, score_a=score_a, score_b=score_b)


def diff_hud(prev: HudState, curr: HudState, t: float) -> list[ScreenEvent]:
    """Emit outcome ScreenEvents for meaningful HUD transitions prev -> curr at time t.

    Conservative: only fields present in BOTH states can produce a transition event, so a
    momentary OCR dropout (field -> None) never fabricates an outcome."""
    out: list[ScreenEvent] = []

    if prev.down is not None and curr.down is not None:
        if curr.down == prev.down + 1:
            out.append(ScreenEvent(EVT_DOWN_ADVANCED, t, True,
                                   {"from": prev.down, "to": curr.down}))
        elif prev.down > 1 and curr.down == 1:
            # down reset to 1 = a new set of downs (first down gained, or change of
            # possession). Either way a play resolved that input must explain.
            out.append(ScreenEvent(EVT_FIRST_DOWN, t, True,
                                   {"from": prev.down, "dist": curr.distance}))

    if (prev.score_a is not None and curr.score_a is not None and curr.score_a > prev.score_a) or \
       (prev.score_b is not None and curr.score_b is not None and curr.score_b > prev.score_b):
        out.append(ScreenEvent(EVT_SCORE_CHANGED, t, True,
                               {"a": curr.score_a, "b": curr.score_b, "provisional": True}))

    if (prev.play_clock is not None and curr.play_clock is not None
            and curr.play_clock > prev.play_clock + 10):
        out.append(ScreenEvent(EVT_PLAYCLOCK_RESET, t, False,
                               {"from": prev.play_clock, "to": curr.play_clock}))

    if prev.quarter is not None and curr.quarter is not None and curr.quarter != prev.quarter:
        out.append(ScreenEvent(EVT_QUARTER_CHANGED, t, False,
                               {"from": prev.quarter, "to": curr.quarter}))

    return out


def is_input_caused(event_type: str) -> bool:
    """True iff this outcome type should require a preceding controller input."""
    return event_type in _INPUT_CAUSED
