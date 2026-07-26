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

ENHANCED: Dual-Lobe Causal-Coherence framework integrates Google MediaPipe for CPU-optimized
60 Hz motion vector tracking, preventing event-loop starvation (222+ events in Match 2).
Supports both MediaPipe Solutions API (0.8.x-0.9.x) and Tasks API (0.10.x+).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# MediaPipe integration for CPU-optimized motion tracking (optional, gated by availability)
# Supports both Solutions API (0.8.x-0.9.x) and Tasks API (0.10.x+)
MEDIAPIPE_AVAILABLE = False
MEDIAPIPE_POSE_AVAILABLE = False

try:
    import mediapipe as mp
    import numpy as np
    
    # Try Solutions API first (0.8.x-0.9.x)
    try:
        _pose_solution = mp.solutions.pose
        MEDIAPIPE_POSE_AVAILABLE = True
        MEDIAPIPE_API_VERSION = "solutions"
    except AttributeError:
        # Try Tasks API (0.10.x+)
        try:
            from mediapipe.tasks.python.vision import PoseLandmarker
            MEDIAPIPE_POSE_AVAILABLE = True
            MEDIAPIPE_API_VERSION = "tasks"
            _PoseLandmarker = PoseLandmarker
        except ImportError:
            MEDIAPIPE_POSE_AVAILABLE = False
            MEDIAPIPE_API_VERSION = None
    
    MEDIAPIPE_AVAILABLE = MEDIAPIPE_POSE_AVAILABLE
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    MEDIAPIPE_POSE_AVAILABLE = False
    MEDIAPIPE_API_VERSION = None


@dataclass
class MotionVector:
    """60 Hz motion vector from MediaPipe optical flow tracking."""
    dx: float  # horizontal motion
    dy: float  # vertical motion
    magnitude: float  # overall motion magnitude
    confidence: float  # tracking confidence (0-1)
    t: float  # timestamp


# Global motion tracker instance (lazy initialized)
_motion_tracker: Optional['MediaPipeMotionTracker'] = None


class MediaPipeMotionTracker:
    """Google MediaPipe-based motion tracking for CPU-optimized optical flow.
    
    Uses lightweight pose model to extract 60 Hz motion vectors without GPU requirements,
    preventing event-loop starvation that occurred with heavier OCR pipelines (222+
    starvation events in Match 2).
    
    Supports both MediaPipe Solutions API (0.8.x-0.9.x) and Tasks API (0.10.x+).
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled and MEDIAPIPE_POSE_AVAILABLE
        self._pose = None
        self._prev_nose = None
        self._api_version = MEDIAPIPE_API_VERSION
        
        if self.enabled:
            try:
                if self._api_version == "solutions":
                    # Solutions API (0.8.x-0.9.x)
                    import mediapipe as mp_sol
                    self._pose = mp_sol.solutions.pose.Pose(
                        model_complexity=0,  # Lightweight model
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                        enable_segmentation=False
                    )
                elif self._api_version == "tasks":
                    # Tasks API (0.10.x+) - requires model file
                    # For now, disable Tasks API if no model is available
                    # This maintains fail-open behavior
                    self.enabled = False
                    self._pose = None
                    self._api_version = None
                
            except Exception:
                # Fail-open if MediaPipe initialization fails
                self.enabled = False
                self._pose = None
                self._api_version = None
    
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
            rgb_frame = frame[:, :, ::-1] if len(frame.shape) == 3 else frame
            
            if self._api_version == "solutions":
                # Solutions API
                results = self._pose.process(rgb_frame)
                if results.pose_landmarks:
                    return self._extract_motion_vector(results.pose_landmarks, t)
            elif self._api_version == "tasks":
                # Tasks API
                # Note: Tasks API requires PIL Image or numpy array in RGB format
                import mediapipe as mp_tasks
                mp_image = mp_tasks.Image(image_format=mp_tasks.ImageFormat.SRGB, data=rgb_frame)
                results = self._pose.detect(mp_image)
                if results.pose_landmarks:
                    return self._extract_motion_vector_tasks(results.pose_landmarks, t)
                    
        except Exception:
            # Fail-open on tracking errors
            pass
        
        return None
    
    def _extract_motion_vector(self, landmarks, t: float) -> MotionVector:
        """Extract motion vector from pose landmarks (Solutions API)."""
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
    
    def _extract_motion_vector_tasks(self, landmarks, t: float) -> MotionVector:
        """Extract motion vector from pose landmarks (Tasks API)."""
        # Use nose landmark (index 0) as primary motion reference
        nose = landmarks[0]  # Tasks API returns list of landmarks
        prev_nose = getattr(self, '_prev_nose', None)
        
        # Tasks API landmark format: x, y, z, visibility
        dx, dy, magnitude, confidence = 0.0, 0.0, 0.0, nose.visibility if hasattr(nose, 'visibility') else 1.0
        
        if prev_nose is not None and hasattr(nose, 'x') and hasattr(nose, 'y'):
            dx = nose.x - prev_nose.x
            dy = nose.y - prev_nose.y
            magnitude = (dx**2 + dy**2)**0.5
        
        self._prev_nose = nose
        return MotionVector(dx=dx, dy=dy, magnitude=magnitude, confidence=confidence, t=t)
    
    def close(self):
        """Clean up MediaPipe resources."""
        if self._pose is not None:
            if self._api_version == "solutions":
                self._pose.close()
            elif self._api_version == "tasks":
                self._pose.close()
            self._pose = None


def get_motion_tracker(enabled: bool = True) -> Optional[MediaPipeMotionTracker]:
    """Get or create the global MediaPipe motion tracker instance."""
    global _motion_tracker
    if _motion_tracker is None and enabled:
        _motion_tracker = MediaPipeMotionTracker(enabled=enabled)
    return _motion_tracker


class ScreenVerdict(str, Enum):
    PRE_SNAP = "PRE_SNAP"  # play clock counting down, ball not snapped -> ideal probe window
    STOPPAGE = "STOPPAGE"  # timeout / review / official stoppage -> quiet window
    LIVE = "LIVE"  # play in progress (game clock running, no play clock) -> defer
    UNKNOWN = "UNKNOWN"  # nothing legible -> defer (fail-safe)


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


def read_screen_region(region: tuple[int, int, int, int], 
                       track_motion: bool = False) -> tuple[Optional[str], Optional[MotionVector]]:
    """OPTIONAL edge reader: grab `region` (x, y, w, h) and OCR it. 
    
    With Dual-Lobe enhancement: if track_motion=True, also extract motion vectors via MediaPipe.
    
    Returns:
        tuple of (OCR text, motion_vector) or (text, None) if motion tracking disabled/unavailable.
        Both are None if screen-capture or pytesseract isn't available.
        
    Kept dependency-light + guarded: nothing here is imported unless this is called.
    """
    try:
        import pytesseract  # type: ignore
        from .screen_capture import ScreenCapturer  # reuse the cocapture grabber
    except Exception:
        return None, None
    
    try:
        cap = ScreenCapturer(region=region, backend="mss")
        frame = cap.grab()
        
        # Extract motion vector if requested and MediaPipe available
        motion_vector = None
        if track_motion:
            tracker = get_motion_tracker(enabled=True)
            if tracker is not None:
                motion_vector = tracker.track_frame(frame, time.time())
        
        cap.close()
        
        if frame is None:
            return None, motion_vector
        
        ocr_text = pytesseract.image_to_string(frame)
        return ocr_text, motion_vector
    except Exception:
        return None, None
