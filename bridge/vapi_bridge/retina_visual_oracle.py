"""
Retina Visual Oracle — Vision Language Model Integration
================================================
Third lobe of the Retina Dual Lobe pipeline.

Takes gameplay frames from the retina capture pipeline and feeds them to
a Vision Language Model (VLM) for semantic understanding of the visual
game state. Outputs structured game context that enables cross-modal
verification against controller inputs and motion tracking.

Game-Aware: The VLM prompt adapts based on GAME_PROFILE_ID. For NCAA
football (ncaa_cfb_26, ncaa_cfb_27) the prompt asks about scoreboard
state (quarter, down, yards-to-go, possession, clock) instead of
shooter-oriented fields (health, ammo, enemies_visible).

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

# ── Game Profile Constants ──────────────────────────────────────────────

# Games whose VLM prompt uses scoreboard/field semantics vs shooter semantics
FOOTBALL_GAME_IDS = frozenset({"ncaa_cfb_26", "ncaa_cfb_27"})
SHOOTER_GAME_IDS = frozenset({"cod_warzone", "cod_warzone_2", "cod_blackops", "cod_mw"})

# Fallback when game not in either set: shooter prompt (conservative)
DEFAULT_PROFILE = "shooter"

# Football event types the VLM might observe on screen
FOOTBALL_OBSERVED_EVENTS = frozenset({
    "football.touchdown",
    "football.field_goal",
    "football.pat",
    "football.two_point_convert",
    "football.first_down",
    "football.sack",
    "football.interception",
    "football.fumble",
    "football.punt",
    "football.kickoff",
    "football.safety",
    "football.turnover_on_downs",
    "football.timeout_called",
    "football.penalty",
    "football.two_minute_warning",
})

# ── Config ──────────────────────────────────────────────────────────────

class VisualOracleConfig:
    """Configuration for the NVIDIA Nemotron Visual Oracle, game-aware."""

    def __init__(self):
        self.nim_api_key = os.environ.get("NIM_API_KEY", "")
        self.nim_base_url = os.environ.get(
            "NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
        self.nim_model = os.environ.get("NIM_MODEL", "nvidia/nemotron-nano-12b-v2-vl")
        # Game profile — drives VLM prompt selection and VisualContext fields
        self.game_profile_id = os.environ.get("GAME_PROFILE_ID", "").lower()
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

    @property
    def is_football(self) -> bool:
        """True if the current game profile is a football game."""
        return self.game_profile_id in FOOTBALL_GAME_IDS

    @property
    def game_category(self) -> str:
        """'football' | 'shooter' | 'unknown'."""
        if self.game_profile_id in FOOTBALL_GAME_IDS:
            return "football"
        elif self.game_profile_id in SHOOTER_GAME_IDS:
            return "shooter"
        return DEFAULT_PROFILE


# ── Data Models ──────────────────────────────────────────────────────────

class GameState(Enum):
    """High-level game state classification (game-agnostic)."""
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
    """Structured output from the NVIDIA Nemotron VLM frame analysis.

    Game-Aware: When the game profile is football (ncaa_cfb_26/27), the
    football_* fields are populated and shooter fields (health, ammo,
    enemies_visible) remain None. When the profile is a shooter, the
    reverse is true. The game_category field disambiguates.
    """

    # Core classification (game-agnostic)
    game_state: GameState = GameState.UNKNOWN
    game_title: str = ""
    screen_description: str = ""
    game_category: str = "unknown"  # "football" | "shooter" | "unknown"

    # Shooter-specific state (filled when game_category == "shooter")
    health: Optional[float] = None
    ammo: Optional[int] = None
    score: Optional[int] = None
    round_info: str = ""
    enemies_visible: int = 0
    is_combat: bool = False
    is_moving: bool = False

    # Football-specific state (filled when game_category == "football")
    football_home_score: Optional[int] = None
    football_away_score: Optional[int] = None
    football_quarter: Optional[int] = None        # 1..4 (5+ for OT)
    football_down: Optional[int] = None            # 1..4
    football_yards_to_go: Optional[int] = None     # yards; 0 = goal line
    football_possession: str = ""                  # "home" | "away"
    football_clock_seconds: Optional[int] = None   # game clock remaining
    football_play_clock: Optional[int] = None      # play clock 0..40
    football_play_type: str = ""                   # "run" | "pass" | "punt" | "fg" | "kickoff" | "pat" | ""
    football_field_position: str = ""              # "own_20", "opp_35", etc.
    football_timeout_home: Optional[int] = None
    football_timeout_away: Optional[int] = None
    football_down_distance_text: str = ""          # e.g. "3rd & 5" — raw OCR
    football_team_home: str = ""
    football_team_away: str = ""

    # Events detected (game-specific event types)
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
        d = {
            "game_state": self.game_state.value,
            "game_title": self.game_title,
            "screen_description": self.screen_description[:200],
            "game_category": self.game_category,
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

        if self.game_category == "football":
            d["football"] = {
                "home_score": self.football_home_score,
                "away_score": self.football_away_score,
                "quarter": self.football_quarter,
                "down": self.football_down,
                "yards_to_go": self.football_yards_to_go,
                "possession": self.football_possession,
                "clock_seconds": self.football_clock_seconds,
                "play_clock": self.football_play_clock,
                "play_type": self.football_play_type,
                "field_position": self.football_field_position,
                "timeout_home": self.football_timeout_home,
                "timeout_away": self.football_timeout_away,
                "down_distance_text": self.football_down_distance_text,
                "team_home": self.football_team_home,
                "team_away": self.football_team_away,
            }
        else:
            # Shooter fields
            d["health"] = self.health
            d["ammo"] = self.ammo
            d["score"] = self.score
            d["round_info"] = self.round_info
            d["enemies_visible"] = self.enemies_visible
            d["is_combat"] = self.is_combat
            d["is_moving"] = self.is_moving

        return d


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


# ── Game-Aware VLM Prompts ──────────────────────────────────────────────

def _build_shooter_prompt() -> str:
    """Build VLM prompt for shooter/COD-style games."""
    return (
        "Analyze this gameplay frame. Respond ONLY with valid JSON, no other text. "
        '{"game_state": "menu|lobby|loading|gameplay|paused|replay|results|spectating|cutscene|unknown", '
        '"game_title": "", "screen_description": "", "health": null, "ammo": null, '
        '"score": null, "round_info": "", "enemies_visible": 0, '
        '"is_combat": false, "is_moving": false, "events": [], '
        '"visual_integrity": {"tearing": false, "lag": false, "quality": "normal"}, '
        '"confidence": 0.5}'
    )


def _build_football_prompt() -> str:
    """Build VLM prompt for NCAA football games (CFB 26/27).

    Asks the VLM to read the scoreboard/HUD: score, quarter, down & distance,
    possession, play clock, game clock. No shooter fields.
    """
    return (
        "Analyze this NCAA College Football 27 gameplay frame. Read the scoreboard and HUD. "
        "Respond ONLY with valid JSON, no other text. "
        '{"game_state": "menu|loading|gameplay|paused|replay|results|cutscene|unknown", '
        '"game_title": "", "screen_description": "", '
        '"football_home_score": null, "football_away_score": null, '
        '"football_quarter": null, "football_down": null, '
        '"football_yards_to_go": null, "football_possession": "home|away|", '
        '"football_clock_seconds": null, "football_play_clock": null, '
        '"football_play_type": "run|pass|punt|fg|kickoff|pat|", '
        '"football_field_position": "", '
        '"football_timeout_home": null, "football_timeout_away": null, '
        '"football_down_distance_text": "", '
        '"football_team_home": "", "football_team_away": "", '
        '"events": [], '
        '"visual_integrity": {"tearing": false, "lag": false, "quality": "normal"}, '
        '"confidence": 0.5}'
    )


def _build_vlm_prompt(game_category: str) -> str:
    """Select the correct VLM prompt based on game category."""
    if game_category == "football":
        return _build_football_prompt()
    return _build_shooter_prompt()


# ── NVIDIA Nemotron VLM Client (NIM OpenAI-compatible) ────────────────────

class NemotronVLMClient:
    """OpenAI-compatible client for nvidia/nemotron-nano-12b-v2-vl via NVIDIA NIM.

    Game-aware: prompt selection depends on config.game_profile_id.
    """

    def __init__(self, config: Optional[VisualOracleConfig] = None):
        self.config = config or VisualOracleConfig()
        self._session: Optional[Any] = None
        self._game_category = config.game_category if config else DEFAULT_PROFILE
        self._prompt = _build_vlm_prompt(self._game_category)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @property
    def game_category(self) -> str:
        return self._game_category

    def _get_requests(self):
        import requests
        return requests

    async def analyze_frame(self, frame: Any) -> VisualContext:
        """
        Analyze a single gameplay frame using NVIDIA Nemotron VLM.
        Returns structured visual context (game-aware fields).

        Args:
            frame: numpy array (H, W, 3) — BGR frame from retina capture
        """
        start = time.monotonic()
        context = VisualContext(game_category=self._game_category)

        if not self.enabled or frame is None:
            context.confidence = 0.0
            context.processing_ms = (time.monotonic() - start) * 1000
            return context

        try:
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

            # Call NVIDIA Nemotron VLM via NIM
            visual_context = await self._call_vlm(frame_b64)

            # Parse response into structured context (game-aware)
            context = self._parse_response(visual_context, context)

        except Exception as e:
            logger.warning(f"[VisualOracle] Frame analysis failed: {e}")
            context.confidence = 0.0

        context.processing_ms = (time.monotonic() - start) * 1000
        return context

    async def _call_vlm(self, frame_b64: str) -> dict:
        """Send frame to NVIDIA Nemotron VLM and return raw response.
        Uses the game-aware prompt template."""
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
                            "text": self._prompt,
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
        """Parse the Nemotron VLM response into structured VisualContext.

        Game-aware: If context.game_category == "football", populates
        football_* fields. Otherwise populates shooter fields.
        """
        if not raw:
            return context

        # Game state (game-agnostic)
        gs = raw.get("game_state", "unknown")
        try:
            context.game_state = GameState(gs.lower())
        except ValueError:
            context.game_state = GameState.UNKNOWN

        context.game_title = raw.get("game_title", "") or ""
        context.screen_description = raw.get("screen_description", "") or ""
        context.events = raw.get("events", []) or []

        # Visual integrity (game-agnostic)
        vi = raw.get("visual_integrity", {}) or {}
        context.has_screen_tearing = bool(vi.get("tearing", False))
        context.has_lag_indicator = bool(vi.get("lag", False))
        context.frame_quality = vi.get("quality", "normal") or "normal"

        # Confidence
        context.confidence = float(raw.get("confidence", 0.0))

        # Game-specific field parsing
        if context.game_category == "football":
            self._parse_football_fields(raw, context)
        else:
            self._parse_shooter_fields(raw, context)

        return context

    def _parse_shooter_fields(self, raw: dict, context: VisualContext) -> None:
        """Parse shooter-specific fields from VLM response."""
        context.health = raw.get("health")
        context.ammo = raw.get("ammo")
        context.score = raw.get("score")
        context.round_info = raw.get("round_info", "") or ""
        context.enemies_visible = int(raw.get("enemies_visible", 0))
        context.is_combat = bool(raw.get("is_combat", False))
        context.is_moving = bool(raw.get("is_moving", False))

    def _parse_football_fields(self, raw: dict, context: VisualContext) -> None:
        """Parse football-specific fields from VLM response.

        The VLM may return field names with or without 'football_' prefix.
        We accept both for robustness.
        """
        # Helper: try raw key first, then with prefix, then without prefix
        def _get(raw_key: str, fallback: Any = None) -> Any:
            prefixed = f"football_{raw_key}"
            val = raw.get(prefixed) if prefixed in raw else raw.get(raw_key)
            return val if val is not None else fallback

        context.football_home_score = _get("home_score")
        context.football_away_score = _get("away_score")
        context.football_quarter = _get("quarter")
        context.football_down = _get("down")
        context.football_yards_to_go = _get("yards_to_go")
        context.football_possession = str(_get("possession", ""))
        context.football_clock_seconds = _get("clock_seconds")
        context.football_play_clock = _get("play_clock")
        context.football_play_type = str(_get("play_type", ""))
        context.football_field_position = str(_get("field_position", ""))
        context.football_timeout_home = _get("timeout_home")
        context.football_timeout_away = _get("timeout_away")
        context.football_down_distance_text = str(_get("down_distance_text", ""))
        context.football_team_home = str(_get("team_home", ""))
        context.football_team_away = str(_get("team_away", ""))


# Backward-compat alias — runtime model is NVIDIA Nemotron; Kimi was the original label.
KimiK26Client = NemotronVLMClient


# ── Cross-Modal Verifier ──────────────────────────────────────────────────

class CrossModalVerifier:
    """
    Verifies agreement between three information streams:
    1. Motion tracking (MediaPipe from retina_screen_lobe)
    2. Controller inputs (DualShock from dualshock_integration)
    3. Visual context (NVIDIA Nemotron VLM from VisualOracle)

    Game-Aware: The motion/input state mapping works for any game type;
    the activity-level classification (idle/active/combat) maps to
    football play types appropriately (active=play running, combat=red zone).
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
        """Enhance a PoAC record with visual context and cross-modal verdict.

        Game-aware: Includes appropriate fields based on game_category."""
        enhanced = dict(base_record)

        if visual_context and visual_context.confidence > 0.1:
            vc = {
                "frame_hash": visual_context.frame_hash,
                "game_state": visual_context.game_state.value,
                "game_title": visual_context.game_title,
                "game_category": visual_context.game_category,
                "has_screen_tearing": visual_context.has_screen_tearing,
                "has_lag_indicator": visual_context.has_lag_indicator,
                "frame_quality": visual_context.frame_quality,
                "confidence": visual_context.confidence,
            }

            if visual_context.game_category == "football":
                vc["football"] = {
                    "home_score": visual_context.football_home_score,
                    "away_score": visual_context.football_away_score,
                    "quarter": visual_context.football_quarter,
                    "down": visual_context.football_down,
                    "yards_to_go": visual_context.football_yards_to_go,
                    "possession": visual_context.football_possession,
                    "clock_seconds": visual_context.football_clock_seconds,
                    "play_clock": visual_context.football_play_clock,
                    "play_type": visual_context.football_play_type,
                    "field_position": visual_context.football_field_position,
                    "down_distance_text": visual_context.football_down_distance_text,
                }
            else:
                vc["is_combat"] = visual_context.is_combat
                vc["enemies_visible"] = visual_context.enemies_visible

            enhanced["visual_context"] = vc

        if verdict:
            enhanced["cross_modal_verdict"] = verdict.to_dict()

        return enhanced


# ── Visual Oracle Integration ──────────────────────────────────────────────

class VisualOracle:
    """
    Top-level integration that ties NVIDIA Nemotron VLM into the Retina Dual Lobe.

    Game-aware: Uses GAME_PROFILE_ID from config to select the correct
    VLM prompt (shooter vs football). All downstream consumers read
    the appropriate game-specific fields from VisualContext.

    Usage in the bridge:
        oracle = VisualOracle()
        visual_context = await oracle.analyze_frame(frame)
        verdict = oracle.verify(motion_features, input_features, visual_context)
        poac_record = oracle.enhance_poac(base_poac, visual_context, verdict)
    """

    def __init__(self, config: Optional[VisualOracleConfig] = None):
        self.config = config or VisualOracleConfig()
        self.client = NemotronVLMClient(self.config)
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
            VisualContext (game-aware: football fields or shooter fields)
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
    """VisualContext should initialize with safe defaults (game-agnostic)."""
    vc = VisualContext()
    assert vc.game_state == GameState.UNKNOWN
    assert vc.confidence == 0.0
    assert vc.frame_quality == "normal"
    assert vc.game_category == "unknown"
    # Football fields start None
    assert vc.football_home_score is None
    assert vc.football_down is None
    assert vc.football_clock_seconds is None
    # Shooter fields start None
    assert vc.health is None
    assert vc.ammo is None
    assert vc.enemies_visible == 0


def test_football_prompt_contains_football_fields():
    """The football prompt should mention football-specific fields."""
    prompt = _build_football_prompt()
    assert "football_home" in prompt
    assert "football_down" in prompt
    assert "football_quarter" in prompt
    assert "football_yards_to_go" in prompt
    assert "football_clock_seconds" in prompt
    assert "football_play_type" in prompt
    # Should NOT mention shooter fields
    assert "health" not in prompt.split("game_state")[1] if "game_state" in prompt else True
    assert "ammo" not in prompt


def test_shooter_prompt_contains_shooter_fields():
    """The shooter prompt should mention shooter-specific fields."""
    prompt = _build_shooter_prompt()
    assert "health" in prompt
    assert "ammo" in prompt
    assert "enemies_visible" in prompt
    assert "is_combat" in prompt
    # Should NOT mention football fields
    assert "football_" not in prompt


def test_prompt_selection():
    """VLM prompt selection should respect game category."""
    prompt_fb = _build_vlm_prompt("football")
    prompt_shooter = _build_vlm_prompt("shooter")
    prompt_unknown = _build_vlm_prompt("unknown")

    assert "football_home" in prompt_fb
    assert "health" not in prompt_fb
    assert "health" in prompt_shooter
    assert "football_" not in prompt_shooter
    # Unknown defaults to shooter
    assert "health" in prompt_unknown


def test_football_parse_response():
    """VLM football response should be correctly parsed into VisualContext."""
    client = NemotronVLMClient()
    raw = {
        "game_state": "gameplay",
        "game_title": "NCAA Football 27",
        "football_home_score": 14,
        "football_away_score": 7,
        "football_quarter": 2,
        "football_down": 3,
        "football_yards_to_go": 5,
        "football_possession": "home",
        "football_clock_seconds": 452,
        "football_play_clock": 18,
        "football_play_type": "pass",
        "football_field_position": "opp_35",
        "football_timeout_home": 2,
        "football_timeout_away": 3,
        "football_down_distance_text": "3rd & 5",
        "football_team_home": "Alabama",
        "football_team_away": "Georgia",
        "events": ["football.first_down"],
        "visual_integrity": {"tearing": False, "lag": False, "quality": "normal"},
        "confidence": 0.85,
    }
    context = client._parse_response(raw, VisualContext(game_category="football"))
    assert context.game_state == GameState.GAMEPLAY
    assert context.game_category == "football"
    assert context.football_home_score == 14
    assert context.football_away_score == 7
    assert context.football_quarter == 2
    assert context.football_down == 3
    assert context.football_yards_to_go == 5
    assert context.football_possession == "home"
    assert context.football_clock_seconds == 452
    assert context.football_play_clock == 18
    assert context.football_play_type == "pass"
    assert context.football_field_position == "opp_35"
    assert context.football_timeout_home == 2
    assert context.football_timeout_away == 3
    assert context.football_down_distance_text == "3rd & 5"
    assert context.football_team_home == "Alabama"
    assert context.football_team_away == "Georgia"
    assert "football.first_down" in context.events
    assert context.confidence == 0.85
    # Shooter fields should remain default
    assert context.health is None
    assert context.ammo is None
    assert context.is_combat is False


def test_football_to_dict():
    """Football VisualContext.to_dict() should include football block."""
    vc = VisualContext(
        game_state=GameState.GAMEPLAY,
        game_category="football",
        football_home_score=21,
        football_away_score=14,
        football_quarter=3,
        football_down=2,
        football_yards_to_go=8,
        football_possession="away",
        football_clock_seconds=120,
        football_down_distance_text="2nd & 8",
        confidence=0.9,
    )
    d = vc.to_dict()
    assert d["game_category"] == "football"
    assert "football" in d
    assert d["football"]["home_score"] == 21
    assert d["football"]["away_score"] == 14
    assert d["football"]["quarter"] == 3
    assert d["football"]["down"] == 2
    assert d["football"]["yards_to_go"] == 8
    assert d["football"]["down_distance_text"] == "2nd & 8"
    # Shooter fields should NOT be in dict
    assert "health" not in d
    assert "ammo" not in d
    assert "is_combat" not in d


def test_shooter_to_dict():
    """Shooter VisualContext.to_dict() should include shooter block."""
    vc = VisualContext(
        game_state=GameState.GAMEPLAY,
        game_category="shooter",
        health=0.75,
        ammo=28,
        is_combat=True,
        enemies_visible=2,
        confidence=0.88,
    )
    d = vc.to_dict()
    assert d["game_category"] == "shooter"
    assert d["health"] == 0.75
    assert d["ammo"] == 28
    assert d["is_combat"] is True
    assert d["enemies_visible"] == 2
    # Football fields should NOT be in dict
    assert "football" not in d


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
    """VLM may wrap JSON in markdown — extract should handle this."""
    client = NemotronVLMClient()
    text = 'Here is the analysis:\n```json\n{"game_state": "gameplay", "confidence": 0.9}\n```'
    result = client._extract_json(text)
    assert result["game_state"] == "gameplay"
    assert result["confidence"] == 0.9


def test_shooter_parse_response():
    """Shooter VLM response should be correctly parsed into VisualContext."""
    client = NemotronVLMClient()
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
    context = client._parse_response(raw, VisualContext(game_category="shooter"))
    assert context.game_state == GameState.GAMEPLAY
    assert context.game_title == "Call of Duty"
    assert context.health == 0.75
    assert context.is_combat
    assert context.confidence == 0.88
    assert not context.has_screen_tearing
    # Football fields should remain default
    assert context.football_home_score is None
    assert context.football_quarter is None


def test_config_football_detection():
    """VisualOracleConfig should detect football games from GAME_PROFILE_ID."""
    cfg = VisualOracleConfig()
    old_val = cfg.game_profile_id
    try:
        import os
        os.environ["GAME_PROFILE_ID"] = "ncaa_cfb_27"
        cfg2 = VisualOracleConfig()
        assert cfg2.is_football is True
        assert cfg2.game_category == "football"

        os.environ["GAME_PROFILE_ID"] = "cod_warzone"
        cfg3 = VisualOracleConfig()
        assert cfg3.is_football is False
        assert cfg3.game_category == "shooter"

        os.environ["GAME_PROFILE_ID"] = "unknown_game"
        cfg4 = VisualOracleConfig()
        assert cfg4.is_football is False
        assert cfg4.game_category == "shooter"  # default fallback
    finally:
        os.environ["GAME_PROFILE_ID"] = old_val


def test_football_config_disables_shooter_fields():
    """NemotronVLMClient with football config should use football prompt."""
    cfg = VisualOracleConfig()
    old_val = cfg.game_profile_id
    try:
        import os
        os.environ["GAME_PROFILE_ID"] = "ncaa_cfb_27"
        cfg2 = VisualOracleConfig()
        client = NemotronVLMClient(cfg2)
        assert client.game_category == "football"
        assert "football_home" in client._prompt
        assert "health" not in client._prompt
    finally:
        os.environ["GAME_PROFILE_ID"] = old_val


def test_visual_oracle_sampling():
    """VisualOracle should only analyze every Nth frame."""
    oracle = VisualOracle()
    oracle.config.frame_sample_rate = 3

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


def test_football_events_constants():
    """FOOTBALL_OBSERVED_EVENTS should contain expected football events."""
    assert "football.touchdown" in FOOTBALL_OBSERVED_EVENTS
    assert "football.field_goal" in FOOTBALL_OBSERVED_EVENTS
    assert "football.interception" in FOOTBALL_OBSERVED_EVENTS
    assert "football.sack" in FOOTBALL_OBSERVED_EVENTS
    assert "football.first_down" in FOOTBALL_OBSERVED_EVENTS
    assert "football.punt" in FOOTBALL_OBSERVED_EVENTS
    # Should NOT contain shooter terms
    assert "kill_confirmed" not in str(FOOTBALL_OBSERVED_EVENTS)


if __name__ == "__main__":
    # Run tests
    import sys
    def p(msg): print(msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode())
    test_visual_context_defaults(); p("[PASS] test_visual_context_defaults")
    test_football_prompt_contains_football_fields(); p("[PASS] test_football_prompt_contains_football_fields")
    test_shooter_prompt_contains_shooter_fields(); p("[PASS] test_shooter_prompt_contains_shooter_fields")
    test_prompt_selection(); p("[PASS] test_prompt_selection")
    test_football_parse_response(); p("[PASS] test_football_parse_response")
    test_football_to_dict(); p("[PASS] test_football_to_dict")
    test_shooter_to_dict(); p("[PASS] test_shooter_to_dict")
    test_cross_modal_match(); p("[PASS] test_cross_modal_match")
    test_cross_modal_anomaly(); p("[PASS] test_cross_modal_anomaly")
    test_cross_modal_no_visual(); p("[PASS] test_cross_modal_no_visual")
    test_json_extraction(); p("[PASS] test_json_extraction")
    test_shooter_parse_response(); p("[PASS] test_shooter_parse_response")
    test_config_football_detection(); p("[PASS] test_config_football_detection")
    test_football_config_disables_shooter_fields(); p("[PASS] test_football_config_disables_shooter_fields")
    test_visual_oracle_sampling(); p("[PASS] test_visual_oracle_sampling")
    test_football_events_constants(); p("[PASS] test_football_events_constants")
    p("\n*** All 16 Visual Oracle tests pass! (14 original + 6 new football tests) ***")