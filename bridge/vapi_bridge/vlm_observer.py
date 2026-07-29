"""VLM Observer — Real-time observation queue for Engineering Assistant integration.

This module provides:
1. ObservationQueue — Ring buffer of VLM events
2. VLMObserver — Subscribes to VLM events and feeds EA context
3. Integration with HardwareWatcher for auto-start/stop

Design:
- VLM observations are pushed to a queue (not polled)
- EA subscribes to the queue and receives real-time updates
- Observations are tagged with session_id for provenance
- Queue has configurable size (default: 100 observations)

This enables the EA to be situationally aware in real-time,
not just reactive to tool calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Deque

logger = logging.getLogger(__name__)


@dataclass
class VLMObservation:
    """A single VLM observation with full provenance."""
    
    # Identification
    observation_id: str
    session_id: str
    frame_number: int
    timestamp_ns: int
    
    # VLM output
    game_state: str
    game_title: str
    screen_description: str
    confidence: float
    frame_hash: str
    processing_ms: float
    
    # Game state details
    health: Optional[float] = None
    ammo: Optional[int] = None
    score: Optional[int] = None
    round_info: str = ""
    enemies_visible: int = 0
    is_combat: bool = False
    is_moving: bool = False
    events: list[str] = field(default_factory=list)
    
    # Visual integrity
    has_screen_tearing: bool = False
    has_lag_indicator: bool = False
    frame_quality: str = "normal"
    
    # Cross-modal verdict (if available)
    cross_modal_match: Optional[bool] = None
    cross_modal_anomaly: Optional[bool] = None
    cross_modal_anomaly_type: Optional[str] = None
    cross_modal_confidence: Optional[float] = None
    
    # Metadata
    model: str = "nvidia/nemotron-nano-12b-v2-vl"
    backend: str = "nim"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "observation_id": self.observation_id,
            "session_id": self.session_id,
            "frame_number": self.frame_number,
            "timestamp_ns": self.timestamp_ns,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S", 
                                          time.localtime(self.timestamp_ns / 1e9)),
            "game_state": self.game_state,
            "game_title": self.game_title,
            "screen_description": self.screen_description,
            "confidence": self.confidence,
            "frame_hash": self.frame_hash,
            "processing_ms": self.processing_ms,
            "health": self.health,
            "ammo": self.ammo,
            "score": self.score,
            "round_info": self.round_info,
            "enemies_visible": self.enemies_visible,
            "is_combat": self.is_combat,
            "is_moving": self.is_moving,
            "events": self.events,
            "has_screen_tearing": self.has_screen_tearing,
            "has_lag_indicator": self.has_lag_indicator,
            "frame_quality": self.frame_quality,
            "cross_modal_match": self.cross_modal_match,
            "cross_modal_anomaly": self.cross_modal_anomaly,
            "cross_modal_anomaly_type": self.cross_modal_anomaly_type,
            "cross_modal_confidence": self.cross_modal_confidence,
            "model": self.model,
            "backend": self.backend,
        }
    
    def to_summary(self, max_length: int = 200) -> str:
        """Generate a brief summary for EA context injection."""
        parts = []
        if self.game_state and self.game_state != "unknown":
            parts.append(f"game_state={self.game_state}")
        if self.screen_description:
            desc = self.screen_description[:100]
            if len(self.screen_description) > 100:
                desc += "..."
            parts.append(f"description={desc}")
        if self.confidence > 0:
            parts.append(f"confidence={self.confidence:.2f}")
        if self.cross_modal_anomaly:
            parts.append(f"ANOMALY={self.cross_modal_anomaly_type}")
        
        summary = ", ".join(parts)
        return summary[:max_length]
    
    def to_ea_context(self) -> str:
        """Format for EA context injection."""
        timestamp = time.strftime("%H:%M:%S", time.localtime(self.timestamp_ns / 1e9))
        lines = [
            f"[VLM Observation @ {timestamp}]",
            f"  Session: {self.session_id[:8]}...",
            f"  Frame: #{self.frame_number}",
            f"  Game State: {self.game_state}",
        ]
        if self.screen_description:
            lines.append(f"  Description: {self.screen_description[:150]}")
        if self.confidence > 0:
            lines.append(f"  Confidence: {self.confidence:.2f}")
        if self.cross_modal_anomaly:
            lines.append(f"  ⚠️  ANOMALY: {self.cross_modal_anomaly_type}")
        if self.is_combat:
            lines.append(f"  Combat: Yes (enemies: {self.enemies_visible})")
        if self.health is not None:
            lines.append(f"  Health: {self.health:.1%}")
        
        return "\n".join(lines)


class ObservationQueue:
    """Ring buffer for VLM observations.
    
    Thread-safe queue that stores the most recent N observations.
    Used to feed VLM data to the Engineering Assistant in real-time.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Args:
            max_size: Maximum number of observations to keep in the queue.
        """
        self._queue: Deque[VLMObservation] = deque(maxlen=max_size)
        self._subscribers: list[Callable[[VLMObservation], None]] = []
        self._lock = asyncio.Lock()
        
    def push(self, observation: VLMObservation) -> None:
        """Push a new observation to the queue."""
        self._queue.append(observation)
        # Notify subscribers
        for subscriber in self._subscribers:
            try:
                subscriber(observation)
            except Exception as e:
                logger.error(f"[ObservationQueue] Subscriber error: {e}")
    
    def recent(self, n: int = 10) -> list[VLMObservation]:
        """Get the most recent N observations."""
        return list(self._queue)[-n:]
    
    def since(self, timestamp_ns: int) -> list[VLMObservation]:
        """Get observations since a specific timestamp."""
        return [obs for obs in self._queue if obs.timestamp_ns >= timestamp_ns]
    
    def last(self) -> Optional[VLMObservation]:
        """Get the most recent observation."""
        return self._queue[-1] if self._queue else None
    
    def by_session(self, session_id: str) -> list[VLMObservation]:
        """Get all observations for a specific session."""
        return [obs for obs in self._queue if obs.session_id == session_id]
    
    def subscribe(self, callback: Callable[[VLMObservation], None]) -> None:
        """Subscribe to new observations."""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[VLMObservation], None]) -> None:
        """Unsubscribe from observations."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def clear(self) -> None:
        """Clear all observations."""
        self._queue.clear()
    
    @property
    def size(self) -> int:
        """Number of observations in the queue."""
        return len(self._queue)
    
    @property
    def empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0


class VLMObserver:
    """Observer that feeds VLM data to the Engineering Assistant.
    
    This class:
    1. Maintains an ObservationQueue
    2. Provides methods for EA to get recent observations
    3. Formats observations for EA context injection
    4. Can trigger autonomous EA responses based on observations
    """
    
    def __init__(self, queue: Optional[ObservationQueue] = None):
        """
        Args:
            queue: Optional ObservationQueue to use. If None, creates a new one.
        """
        self.queue = queue or ObservationQueue()
        self._autonomous_callbacks: list[Callable[[VLMObservation], str]] = []
        self._last_autonomous_response: Optional[str] = None
        self._last_autonomous_time: Optional[float] = None
        
    def push(self, observation: VLMObservation) -> None:
        """Push a new observation to the queue."""
        self.queue.push(observation)
        # Check for autonomous triggers
        self._check_autonomous_triggers(observation)
    
    def recent(self, n: int = 5, max_age_seconds: Optional[float] = None) -> list[VLMObservation]:
        """Get recent observations for EA context."""
        observations = self.queue.recent(n)
        if max_age_seconds is not None:
            cutoff = time.time() - max_age_seconds
            cutoff_ns = int(cutoff * 1e9)
            observations = [obs for obs in observations if obs.timestamp_ns >= cutoff_ns]
        return observations
    
    def get_context_summary(self, max_observations: int = 5, max_age_seconds: float = 30.0) -> str:
        """Get a summary of recent observations for EA context injection.
        
        Args:
            max_observations: Maximum number of observations to include.
            max_age_seconds: Only include observations from the last N seconds.
            
        Returns:
            String summary for injection into EA context.
        """
        observations = self.recent(max_observations, max_age_seconds)
        if not observations:
            return ""
        
        lines = ["Recent Visual Observations:"]
        for obs in observations:
            lines.append(f"  - {obs.to_summary(100)}")
        
        return "\n".join(lines)
    
    def get_autonomous_prompt(self, max_observations: int = 3) -> str:
        """Get observations formatted as a system prompt for autonomous EA.
        
        This is used to give the EA situational awareness without user input.
        """
        observations = self.recent(max_observations)
        if not observations:
            return ""
        
        prompt_parts = ["Current Game Context (from visual analysis):"]
        for obs in observations:
            prompt_parts.append(obs.to_ea_context())
        prompt_parts.append("")
        prompt_parts.append("Use this context to provide situationally aware assistance.")
        
        return "\n".join(prompt_parts)
    
    def register_autonomous_callback(
        self, 
        callback: Callable[[VLMObservation], str]
    ) -> None:
        """Register a callback for autonomous EA responses.
        
        The callback receives a VLMObservation and returns a response string.
        This allows the EA to proactively respond to visual events.
        """
        self._autonomous_callbacks.append(callback)
    
    def _check_autonomous_triggers(self, observation: VLMObservation) -> None:
        """Check if this observation should trigger an autonomous EA response."""
        # Rate limit: don't trigger more than once per second
        now = time.time()
        if self._last_autonomous_time and now - self._last_autonomous_time < 1.0:
            return
        
        # Only trigger on high-confidence, significant observations
        if observation.confidence < 0.7:
            return
        
        # Significant state changes that warrant autonomous response
        significant_states = ["gameplay", "combat", "boss"]
        if any(state in observation.game_state.lower() for state in significant_states):
            self._last_autonomous_time = now
            for callback in self._autonomous_callbacks:
                try:
                    response = callback(observation)
                    self._last_autonomous_response = response
                    logger.info(f"[VLMObserver] Autonomous trigger: {response[:100]}")
                except Exception as e:
                    logger.error(f"[VLMObserver] Autonomous callback error: {e}")
    
    @property
    def last_autonomous_response(self) -> Optional[str]:
        """Get the last autonomous response."""
        return self._last_autonomous_response
    
    def clear(self) -> None:
        """Clear all observations and state."""
        self.queue.clear()
        self._last_autonomous_response = None
        self._last_autonomous_time = None


# Global singleton instances (optional, for convenience)
_observation_queue: Optional[ObservationQueue] = None
_vlm_observer: Optional[VLMObserver] = None


def get_observation_queue() -> ObservationQueue:
    """Get or create the global observation queue."""
    global _observation_queue
    if _observation_queue is None:
        _observation_queue = ObservationQueue()
    return _observation_queue


def get_vlm_observer() -> VLMObserver:
    """Get or create the global VLM observer."""
    global _vlm_observer
    if _vlm_observer is None:
        _vlm_observer = VLMObserver(get_observation_queue())
    return _vlm_observer
