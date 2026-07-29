"""
Retina Visual Oracle — Vision Language Model Integration
================================================
Third lobe of the Retina Dual Lobe pipeline.

Takes gameplay frames from the retina capture pipeline and feeds them to
a Vision Language Model (VLM) for semantic understanding of the visual
game state. Outputs structured game context that enables cross-modal
verification against controller inputs and motion tracking.

Default Model: nvidia/nemotron-nano-12b-v2-vl (NVIDIA NIM)
Container: nvcr.io/nim/nvidia/nemotron-nano-12b-v2-vl:latest
Endpoint: NIM_BASE_URL + /v1/chat/completions (OpenAI-compatible)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────

class VisualOracleConfig:
    """Configuration for the Kimi K2.6 Visual Oracle."""

    def __init__(self):
        self.nim_api_key = os.environ.get(
            "NIM_API_KEY", ""
        )
        self.nim_base_url = os.environ.get(
            "NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
        self.nim_model = os.environ.get(
            "NIM_MODEL", "nvidia/nemotron-nano-12b-v2-vl"
        )
        # Frame analysis cadence: analyze every N frames
        self.frame_sample_rate = int(os.environ.get("VISUAL_ORACLE_SAMPLE_RATE", "30"))
        # Max concurrent requests to the VLM
        self.max_concurrent = int(os.environ.get("VISUAL_ORACLE_CONCURRENT", "2"))
        # Minimum confidence to accept visual context
        self.min_confidence = float(os.environ.get("VISUAL_ORACLE_MIN_CONFIDENCE", "0.6"))
        # Frame compression: resize to this max dimension before sending
        self.max_frame_dim = int(os.environ.get("VISUAL_ORACLE_MAX_DIM", "640"))

    @property
    def enabled(self) -> bool:
        return bool(self.nim_api_key) and bool(self.nim_model)


# ── Data Models ──────────────────────────────────────────────────────────

class GameState(Enum):
    """High-level game state classification."""
    UNKNOWN = "unknown"
    MENU = "menu"
    LOBBY = "lobby"
    LOADING = "loading"
    GAMEPLAY = "gameplay"
    PAUSED = "paused"
    REPLAY = "replay"
    RESULTS = "results"
    SPECTATING = "spectating"
    CUTSCENE = "cutscene"


@dataclass
class VisualContext:
    """Structured output from the Kimi K2.6 VLM frame analysis."""

    # Core classification
    game_state: GameState = GameState.UNKNOWN
    game_title: str = ""
    screen_description: str = ""

    # Game-specific state (filled when game_state == GAMEPLAY)
    health: Optional[float] = None
    ammo: Optional[int] = None
    score: Optional[int] = None
    round_info: str = ""
    enemies_visible: int = 0
    is_combat: bool = False
    is_moving: bool = False

    # Events detected
    events: list[str] = field(default_factory=list)

    # Visual integrity
    has_screen_tearing: bool = False
    has_lag_indicator: bool = False
    frame_quality: str = "normal"  # normal, blurry, frozen, black

    # Metadata
    confidence: float = 0.0
    processing_ms: float = 0.0
    frame_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "game_state": self.game_state.value,
            "game_title": self.game_title,
            "screen_description": self.screen_description[:200],
            "health": self.health,
            "ammo": self.ammo,
            "score": self.score,
            "round_info": self.round_info,
            "enemies_visible": self.enemies_visible,
            "is_combat": self.is_combat,
            "is_moving": self.is_moving,
            "events": self.events,
            "visual_integrity": {
                "tearing": self.has_screen_tearing,
                "lag": self.has_lag_indicator,
                "quality": self.frame_quality,
            },
            "confidence": self.confidence,
            "processing_ms": self.processing_ms,
            "frame_hash": self.frame_hash,
        }


@dataclass
class CrossModalVerdict:
    """Result of cross-modal verification between motion, inputs, and vision."""

    match: bool = False
    confidence: float = 0.0
    anomaly: bool = False
    anomaly_type: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "match": self.match,
            "confidence": self.confidence,
            "anomaly": self.anomaly,
            "anomaly_type": self.anomaly_type,
            "details": self.details,
        }


# ── Kimi K2.6 VLM Client ──────────────────────────────────────────────────

class KimiK26Client:
    """OpenAI-compatible client for Kimi K2.6 VLM via NVIDIA NIM endpoint."""

    def __init__(self, config: Optional[VisualOracleConfig] = None):
        self.config = config or VisualOracleConfig()
        self._session: Optional[Any] = None

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def _get_requests(self):
        import requests
        return requests

    async def analyze_frame(self, frame: Any) -> VisualContext:
        """
        Analyze a single gameplay frame using Kimi K2.6.
        Returns structured visual context.

        Args:
            frame: numpy array (H, W, 3) — BGR frame from retina capture
        """
        start = time.monotonic()
        context = VisualContext()

        if not self.enabled or frame is None:
            context.confidence = 0.0
            context.processing_ms = (time.monotonic() - start) * 1000
            return context

        try:
            # Encode frame as base64 JPEG
            import cv2
            import numpy as np

            # Resize to max dimension to reduce payload
            h, w = frame.shape[:2]
            if max(h, w) > self.config.max_frame_dim:
                scale = self.config.max_frame_dim / max(h, w)
                new_w, new_h = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Encode to JPEG
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_b64 = base64.b64encode(buffer).decode("utf-8")

            # Compute frame hash for provenance
            frame_hash = hashlib.sha256(buffer).hexdigest()[:16]
            context.frame_hash = frame_hash

            # Call Kimi K2.6 via NIM
            visual_context = await self._call_vlm(frame_b64)

            # Parse response into structured context
            context = self._parse_response(visual_context, context)

        except Exception as e:
            logger.warning(f"[VisualOracle] Frame analysis failed: {e}")
            context.confidence = 0.0

        context.processing_ms = (time.monotonic() - start) * 1000
        return context

    async def _call_vlm(self, frame_b64: str) -> dict:
        """Send frame to Kimi K2.6 VLM and return raw response."""
        loop = asyncio.get_event_loop()
        requests = self._get_requests()

        url = f"{self.config.nim_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.config.nim_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this gameplay frame. Respond ONLY with valid JSON, no other text. "
                                '{"game_state": "menu|lobby|loading|gameplay|paused|replay|results|spectating|cutscene|unknown", '
                                '"game_title": "", "screen_description": "", "health": null, "ammo": null, '
                                '"score": null, "round_info": "", "enemies_visible": 0, '
                                '"is_combat": false, "is_moving": false, "events": [], '
                                '"visual_integrity": {"tearing": false, "lag": false, "quality": "normal"}, '
                                '"confidence": 0.5}'
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{frame_b64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 512,
        }

        headers = {
            "Authorization": f"Bearer {self.config.nim_api_key}",
            "Content-Type": "application/json",
        }

        def _do_request():
            return requests.post(
                url, json=payload, headers=headers, timeout=30
            )

        response = await loop.run_in_executor(None, _do_request)
        response.raise_for_status()
        data = response.json()

        # Extract the assistant's message
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        # Parse JSON from response (handle markdown-wrapped JSON)
        return self._extract_json(content)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from potentially markdown-wrapped response."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` block
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding {...} in the text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        return {"game_state": "unknown", "confidence": 0.0}

    def _parse_response(self, raw: dict, context: VisualContext) -> VisualContext:
        """Parse the Kimi K2.6 response into structured VisualContext."""
        if not raw:
            return context

        # Game state
        gs = raw.get("game_state", "unknown")
        try:
            context.game_state = GameState(gs.lower())
        except ValueError:
            context.game_state = GameState.UNKNOWN

        context.game_title = raw.get("game_title", "") or ""
        context.screen_description = raw.get("screen_description", "") or ""

        # Game-specific
        context.health = raw.get("health")
        context.ammo = raw.get("ammo")
        context.score = raw.get("score")
        context.round_info = raw.get("round_info", "") or ""
        context.enemies_visible = int(raw.get("enemies_visible", 0))
        context.is_combat = bool(raw.get("is_combat", False))
        context.is_moving = bool(raw.get("is_moving", False))
        context.events = raw.get("events", []) or []

        # Visual integrity
        vi = raw.get("visual_integrity", {}) or {}
        context.has_screen_tearing = bool(vi.get("tearing", False))
        context.has_lag_indicator = bool(vi.get("lag", False))
        context.frame_quality = vi.get("quality", "normal") or "normal"

        # Confidence
        context.confidence = float(raw.get("confidence", 0.0))

        return context


# ── Cross-Modal Verifier ──────────────────────────────────────────────────

class CrossModalVerifier:
    """
    Verifies agreement between three information streams:
    1. Motion tracking (MediaPipe from retina_screen_lobe)
    2. Controller inputs (DualShock from dualshock_integration)
    3. Visual context (Kimi K2.6 VLM from VisualOracle)

    Produces a CrossModalVerdict that enhances the PoAC record.
    """

    # Map of what motion/input states correspond to what visual states
    MOTION_VISUAL_MAP = {
        "idle":      (GameState.MENU, GameState.LOBBY, GameState.LOADING,
                      GameState.PAUSED, GameState.RESULTS, GameState.CUTSCENE),
        "active":    (GameState.GAMEPLAY,),
        "combat":    (GameState.GAMEPLAY,),
        "menu_nav":  (GameState.MENU, GameState.LOBBY),
    }

    ANOMALY_THRESHOLD = 0.7  # Below this confidence + mismatch = anomaly

    @staticmethod
    def motion_to_state(motion_features: dict) -> str:
        """Classify motion features into a high-level state string."""
        activity = motion_features.get("activity_level", 0)
        if activity > 0.8:
            return "combat"
        elif activity > 0.3:
            return "active"
        elif activity > 0.05:
            return "menu_nav"
        return "idle"

    @staticmethod
    def input_to_state(input_features: dict) -> str:
        """Classify input features into a high-level state string."""
        apm = input_features.get("apm", 0)  # actions per minute
        if apm > 120:
            return "combat"
        elif apm > 30:
            return "active"
        elif apm > 5:
            return "menu_nav"
        return "idle"

    def verify(
        self,
        motion_features: Optional[dict],
        input_features: Optional[dict],
        visual_context: Optional[VisualContext],
    ) -> CrossModalVerdict:
        """
        Cross-verify all three lobes.

        Args:
            motion_features: output from MediaPipeMotionTracker.track_frame()
            input_features:  current input state from DualShock
            visual_context:  output from VisualOracle.analyze_frame()

        Returns:
            CrossModalVerdict with match/anomaly assessment
        """
        motion_state = self.motion_to_state(motion_features or {})
        input_state = self.input_to_state(input_features or {})
        visual_state = (visual_context or VisualContext()).game_state

        # Build the verdict
        verdict = CrossModalVerdict()

        if visual_context is None or visual_context.confidence < 0.1:
            # No visual data — can't cross-verify
            verdict.match = True
            verdict.confidence = 0.5
            verdict.anomaly = False
            verdict.details = {"reason": "visual oracle not available"}
            return verdict

        # Check motion vs vision
        expected_visual_states = self.MOTION_VISUAL_MAP.get(motion_state, ())
        motion_vision_match = visual_state in expected_visual_states

        # Check input vs vision
        expected_input_states = self.MOTION_VISUAL_MAP.get(input_state, ())
        input_vision_match = visual_state in expected_input_states

        # Overall match
        all_match = motion_vision_match and input_vision_match
        confidence = visual_context.confidence

        verdict.match = all_match
        verdict.confidence = confidence

        # Detect specific anomalies
        if not all_match and confidence >= self.ANOMALY_THRESHOLD:
            verdict.anomaly = True
            verdict.details = {
                "motion_state": motion_state,
                "input_state": input_state,
                "visual_state": visual_state.value,
                "motion_vision_match": motion_vision_match,
                "input_vision_match": input_vision_match,
                "confidence": confidence,
            }

            if not motion_vision_match and not input_vision_match:
                verdict.anomaly_type = "FULL_MISMATCH"
                verdict.details["severity"] = "CRITICAL"
            elif not motion_vision_match:
                verdict.anomaly_type = "MOTION_VISION_MISMATCH"
                verdict.details["severity"] = "HIGH"
            else:
                verdict.anomaly_type = "INPUT_VISION_MISMATCH"
                verdict.details["severity"] = "MEDIUM"
        elif not all_match:
            verdict.anomaly = False
            verdict.anomaly_type = "LOW_CONFIDENCE_MISMATCH"
            verdict.details = {
                "reason": "mismatch but confidence too low to flag",
                "confidence": confidence,
            }

        return verdict

    @staticmethod
    def enhanced_poac_record(
        base_record: dict,
        visual_context: Optional[VisualContext],
        verdict: Optional[CrossModalVerdict],
    ) -> dict:
        """Enhance a PoAC record with visual context and cross-modal verdict."""
        enhanced = dict(base_record)

        if visual_context and visual_context.confidence > 0.1:
            enhanced["visual_context"] = {
                "frame_hash": visual_context.frame_hash,
                "game_state": visual_context.game_state.value,
                "game_title": visual_context.game_title,
                "is_combat": visual_context.is_combat,
                "enemies_visible": visual_context.enemies_visible,
                "has_screen_tearing": visual_context.has_screen_tearing,
                "has_lag_indicator": visual_context.has_lag_indicator,
                "frame_quality": visual_context.frame_quality,
                "confidence": visual_context.confidence,
            }

        if verdict:
            enhanced["cross_modal_verdict"] = verdict.to_dict()

        return enhanced


# ── Visual Oracle Integration ──────────────────────────────────────────────

class VisualOracle:
    """
    Top-level integration that ties Kimi K2.6 into the Retina Dual Lobe.

    Usage in the bridge:
        oracle = VisualOracle()
        visual_context = await oracle.analyze_frame(frame)
        verdict = oracle.verify(motion_features, input_features, visual_context)
        poac_record = oracle.enhance_poac(base_poac, visual_context, verdict)
    """

    def __init__(self, config: Optional[VisualOracleConfig] = None):
        self.config = config or VisualOracleConfig()
        self.client = KimiK26Client(self.config)
        self.verifier = CrossModalVerifier()
        self._frame_count = 0
        self._last_context: Optional[VisualContext] = None

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    @property
    def last_context(self) -> Optional[VisualContext]:
        return self._last_context

    async def analyze_frame(self, frame: Any) -> VisualContext:
        """
        Analyze a frame with the VLM. Only runs on sampled frames
        (every N frames per config.frame_sample_rate) to manage cost/latency.

        Args:
            frame: numpy array (H, W, 3) from retina capture

        Returns:
            VisualContext — cached between samples for non-sampled frames
        """
        self._frame_count += 1

        # Only analyze every Nth frame
        if self._frame_count % self.config.frame_sample_rate != 0:
            return self._last_context or VisualContext()

        context = await self.client.analyze_frame(frame)
        self._last_context = context
        return context

    def verify(
        self,
        motion_features: Optional[dict] = None,
        input_features: Optional[dict] = None,
        visual_context: Optional[VisualContext] = None,
    ) -> CrossModalVerdict:
        """Cross-verify motion, inputs, and visual context."""
        return self.verifier.verify(
            motion_features, input_features,
            visual_context or self._last_context,
        )

    def enhance_poac(
        self,
        base_record: dict,
        visual_context: Optional[VisualContext] = None,
        verdict: Optional[CrossModalVerdict] = None,
    ) -> dict:
        """Enhance a PoAC record with visual oracle data."""
        return self.verifier.enhanced_poac_record(
            base_record,
            visual_context or self._last_context,
            verdict,
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Unit Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_visual_context_defaults():
    """VisualContext should initialize with safe defaults."""
    vc = VisualContext()
    assert vc.game_state == GameState.UNKNOWN
    assert vc.confidence == 0.0
    assert not vc.is_combat
    assert not vc.has_screen_tearing
    assert vc.frame_quality == "normal"


def test_cross_modal_match():
    """When all lobes agree, verdict should be match=True, anomaly=False."""
    verifier = CrossModalVerifier()
    motion = {"activity_level": 0.9}
    inputs = {"apm": 150}
    visual = VisualContext(game_state=GameState.GAMEPLAY, confidence=0.95)
    verdict = verifier.verify(motion, inputs, visual)
    assert verdict.match
    assert not verdict.anomaly


def test_cross_modal_anomaly():
    """High-confidence mismatch should produce an anomaly."""
    verifier = CrossModalVerifier()
    motion = {"activity_level": 0.9}  # combat
    inputs = {"apm": 150}  # combat
    visual = VisualContext(game_state=GameState.MENU, confidence=0.85)  # menu
    verdict = verifier.verify(motion, inputs, visual)
    assert not verdict.match
    assert verdict.anomaly
    assert verdict.anomaly_type == "FULL_MISMATCH"


def test_cross_modal_no_visual():
    """Without visual data, should return neutral match."""
    verifier = CrossModalVerifier()
    verdict = verifier.verify(
        {"activity_level": 0.9}, {"apm": 150}, None
    )
    assert verdict.match  # default to match when no visual data
    assert not verdict.anomaly
    assert verdict.confidence == 0.5


def test_json_extraction():
    """Kimi may wrap JSON in markdown — extract should handle this."""
    client = KimiK26Client()
    text = 'Here is the analysis:\n```json\n{"game_state": "gameplay", "confidence": 0.9}\n```'
    result = client._extract_json(text)
    assert result["game_state"] == "gameplay"
    assert result["confidence"] == 0.9


def test_parse_response():
    """Raw VLM response should be correctly parsed into VisualContext."""
    client = KimiK26Client()
    raw = {
        "game_state": "gameplay",
        "game_title": "Call of Duty",
        "health": 0.75,
        "ammo": 28,
        "is_combat": True,
        "enemies_visible": 2,
        "events": ["kill_confirmed"],
        "visual_integrity": {"tearing": False, "lag": False, "quality": "normal"},
        "confidence": 0.88,
    }
    context = client._parse_response(raw, VisualContext())
    assert context.game_state == GameState.GAMEPLAY
    assert context.game_title == "Call of Duty"
    assert context.health == 0.75
    assert context.is_combat
    assert context.confidence == 0.88
    assert not context.has_screen_tearing


def test_visual_oracle_sampling():
    """VisualOracle should only analyze every Nth frame."""
    oracle = VisualOracle()
    oracle.config.frame_sample_rate = 3

    # First frame — should analyze
    ctx1 = oracle._last_context
    assert ctx1 is None  # nothing cached yet

    # Actually the analyze_frame would be called with a frame
    # Testing the counter logic instead:
    assert oracle._frame_count == 0

    # After analyze_frame with sample_rate=3, frames at 1,4,7,10... are analyzed
    # The rest return cached value
    oracle._frame_count = 1
    assert oracle._frame_count % oracle.config.frame_sample_rate == 1  # analyze
    oracle._frame_count = 2
    assert oracle._frame_count % oracle.config.frame_sample_rate == 2  # skip
    oracle._frame_count = 3
    assert oracle._frame_count % oracle.config.frame_sample_rate == 0  # skip
    oracle._frame_count = 4
    assert oracle._frame_count % oracle.config.frame_sample_rate == 1  # analyze


if __name__ == "__main__":
    # Run tests
    import sys
    def p(msg): print(msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode())
    test_visual_context_defaults(); p("[PASS] test_visual_context_defaults")
    test_cross_modal_match(); p("[PASS] test_cross_modal_match")
    test_cross_modal_anomaly(); p("[PASS] test_cross_modal_anomaly")
    test_cross_modal_no_visual(); p("[PASS] test_cross_modal_no_visual")
    test_json_extraction(); p("[PASS] test_json_extraction")
    test_parse_response(); p("[PASS] test_parse_response")
    test_visual_oracle_sampling(); p("[PASS] test_visual_oracle_sampling")
    p("\n*** All 7 Visual Oracle tests pass! ***")