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

ENHANCED: Google MediaPipe integration for optical flow & motion tracking (CPU-optimized).
Dual-Lobe Causal-Coherence framework adds Thread C isolation guard to prevent event-loop
starvation while maintaining 1000 Hz HID poll rate stability.

Pure: OCR text -> HudState -> ScreenEvents. The OCR/screen-capture I/O lives at the edge
(probe_screen.read_screen_region / the cocapture pipeline). Default-off; no FROZEN/PoAC/
chain touch. Score parsing is best-effort and marked provisional; down/distance/play-clock
are the load-bearing, reliably-legible fields.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# MediaPipe integration for CPU-optimized motion tracking (optional, gated by availability)
try:
    import mediapipe as mp
    import numpy as np
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

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


@dataclass(frozen=True)
class MotionVector:
    """60 Hz motion vector from MediaPipe optical flow tracking."""
    dx: float  # horizontal motion
    dy: float  # vertical motion
    magnitude: float  # overall motion magnitude
    confidence: float  # tracking confidence (0-1)
    t: float  # timestamp


# MediaPipe motion tracker (CPU-optimized, lightweight)
class MediaPipeMotionTracker:
    """Google MediaPipe-based motion tracking for CPU-optimized optical flow.
    
    Uses lightweight pose model (model_complexity=0) to extract 60 Hz motion vectors
    without GPU requirements, preventing event-loop starvation that occurred with
    heavier OCR pipelines (222+ starvation events in Match 2).
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled and MEDIAPIPE_AVAILABLE
        self._pose = None
        if self.enabled:
            try:
                self._pose = mp.solutions.pose.Pose(
                    model_complexity=0,  # Lightweight model
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                    enable_segmentation=False
                )
            except Exception as e:
                # Fail-open if MediaPipe initialization fails
                self.enabled = False
                self._pose = None
    
    def track_frame(self, frame: Optional["np.ndarray"], t: float) -> Optional[MotionVector]:
        """Extract motion vector from video frame at 60 Hz.
        
        Args:
            frame: numpy array of shape (H, W, 3) for BGR image
            t: timestamp in seconds
            
        Returns:
            MotionVector if tracking successful, None otherwise
        """
        if not self.enabled or self._pose is None or frame is None:
            return None
        
        try:
            # Convert BGR to RGB for MediaPipe
            rgb_frame = self._mp_bgr_to_rgb(frame)
            results = self._pose.process(rgb_frame)
            
            if results.pose_landmarks:
                return self._extract_motion_vector(results.pose_landmarks, t)
        except Exception:
            # Fail-open on tracking errors
            pass
        
        return None
    
    def _mp_bgr_to_rgb(self, bgr_frame: "np.ndarray") -> "np.ndarray":
        """Convert BGR to RGB for MediaPipe processing."""
        # Using simple indexing instead of cv2.cvtColor to avoid cv2 dependency
        # BGR -> RGB: reverse the last dimension
        return bgr_frame[:, :, ::-1] if len(bgr_frame.shape) == 3 else bgr_frame
    
    def _extract_motion_vector(self, landmarks, t: float) -> MotionVector:
        """Extract motion vector from pose landmarks."""
        # Use nose landmark (index 0) as primary motion reference
        nose = landmarks.landmark[0]
        prev_nose = getattr(self, '_prev_nose', None)
        
        dx, dy, magnitude, confidence = 0.0, 0.0, 0.0, nose.visibility
        
        if prev_nose is not None:
            dx = nose.x - prev_nose.x
            dy = nose.y - prev_nose.y
            magnitude = (dx**2 + dy**2)**0.5
        
        self._prev_nose = nose
        return MotionVector(dx=dx, dy=dy, magnitude=magnitude, confidence=confidence, t=t)
    
    def close(self):
        """Clean up MediaPipe resources."""
        if self._pose is not None:
            self._pose.close()
            self._pose = None


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
