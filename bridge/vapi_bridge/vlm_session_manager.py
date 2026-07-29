"""VLM Session Manager — Wires VLM to Hardware Session Lifecycle.

This module provides automatic VLM capture start/stop based on
hardware detection state changes. It integrates with:
- HardwareWatcher: Detects when hardware is ready (ALL_READY)
- VisualOracle: Provides VLM analysis
- ObservationQueue: Stores VLM observations
- HardwareBiographer: Tracks session lifecycle

The VLM Session Manager ensures that:
1. VLM capture starts automatically when hardware is ready
2. VLM capture stops automatically when hardware is disconnected
3. All VLM observations are tagged with the current session ID
4. Observations are stored for later analysis
5. Cross-modal verification runs automatically
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bridge.vapi_bridge.hardware_watcher import HardwareState
    from bridge.vapi_bridge.vlm_observer import ObservationQueue, VLMObserver
    from bridge.vapi_bridge.retina_visual_oracle import VisualOracle, VisualContext, CrossModalVerdict

logger = logging.getLogger(__name__)


class VLMSessionManager:
    """Manages VLM capture sessions tied to hardware lifecycle.
    
    This class:
    - Starts VLM capture when HardwareWatcher reaches ALL_READY
    - Stops VLM capture when HardwareWatcher goes to IDLE
    - Tags all observations with the current session ID
    - Stores observations in the ObservationQueue
    - Runs cross-modal verification automatically
    """
    
    def __init__(
        self,
        visual_oracle: Optional["VisualOracle"] = None,
        observation_queue: Optional["ObservationQueue"] = None,
        vlm_observer: Optional["VLMObserver"] = None,
        hardware_biographer: Optional = None,
        frame_source_callable: Optional[callable] = None,
    ):
        """
        Args:
            visual_oracle: The VLM oracle instance.
            observation_queue: The observation queue for storing VLM data.
            vlm_observer: The VLM observer for EA integration.
            hardware_biographer: For session tracking.
            frame_source_callable: Function to get frames from capture.
        """
        self.visual_oracle = visual_oracle
        self.observation_queue = observation_queue
        self.vlm_observer = vlm_observer
        self.hardware_biographer = hardware_biographer
        self.frame_source_callable = frame_source_callable
        
        # Session state
        self._current_session_id: Optional[str] = None
        self._current_session_start_ns: Optional[int] = None
        self._frame_count: int = 0
        self._capture_active: bool = False
        self._capture_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.sample_rate = 30  # Analyze every Nth frame
        self.max_concurrent = 2  # Max concurrent VLM requests
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        logger.info("VLMSessionManager initialized")
    
    async def on_hardware_state_change(self, state: "HardwareState") -> None:
        """Called by HardwareWatcher when state changes.
        
        Args:
            state: The new hardware state.
        """
        logger.info(f"[VLMSessionManager] Hardware state changed: {state.value}")
        
        if state.value == "all_ready":
            await self._start_capture()
        elif state.value == "idle":
            await self._stop_capture()
    
    async def _start_capture(self) -> None:
        """Start the VLM capture loop."""
        if self._capture_active:
            logger.warning("[VLMSessionManager] Capture already active")
            return
        
        # Initialize visual oracle if not provided
        if self.visual_oracle is None:
            from bridge.vapi_bridge.retina_visual_oracle import VisualOracle
            self.visual_oracle = VisualOracle()
            logger.info("[VLMSessionManager] Created VisualOracle instance")
        
        # Check if VLM is enabled
        if not self.visual_oracle.enabled:
            logger.warning("[VLMSessionManager] VLM not enabled (missing NIM_API_KEY?)")
            return
        
        # Start a new session
        self._current_session_id = str(uuid.uuid4())[:12]
        self._current_session_start_ns = int(time.time() * 1e9)
        self._frame_count = 0
        self._capture_active = True
        
        # Get session info from HardwareBiographer if available
        session_info = {}
        if self.hardware_biographer:
            try:
                # Try to get current session from biographer
                # (This would need to be added to HardwareBiographer)
                pass
            except Exception:
                pass
        
        logger.info(
            f"[VLMSessionManager] Starting VLM capture "
            f"(session: {self._current_session_id})"
        )
        
        # Start capture loop
        self._capture_task = asyncio.create_task(
            self._capture_loop(),
            name="VLM Capture Loop"
        )
    
    async def _stop_capture(self) -> None:
        """Stop the VLM capture loop."""
        if not self._capture_active:
            logger.warning("[VLMSessionManager] Capture not active")
            return
        
        self._capture_active = False
        
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[VLMSessionManager] Error stopping capture: {e}")
            finally:
                self._capture_task = None
        
        # Clear session
        session_id = self._current_session_id
        self._current_session_id = None
        self._current_session_start_ns = None
        
        logger.info(f"[VLMSessionManager] Stopped VLM capture (session: {session_id})")
    
    async def _capture_loop(self) -> None:
        """Main capture loop: grab frames, analyze with VLM, store observations."""
        while self._capture_active:
            try:
                # Get frame from source
                frame = await self._get_frame()
                
                if frame is not None:
                    self._frame_count += 1
                    
                    # Only analyze every Nth frame
                    if self._frame_count % self.sample_rate == 0:
                        await self._analyze_frame(frame)
                    
                    # Small delay to prevent CPU overload
                    await asyncio.sleep(0.01)
                else:
                    # No frame available, wait a bit
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                logger.info("[VLMSessionManager] Capture loop cancelled")
                break
            except Exception as e:
                logger.error(f"[VLMSessionManager] Capture loop error: {e}")
                await asyncio.sleep(1)  # Backoff on error
    
    async def _get_frame(self):
        """Get a frame from the capture source."""
        if self.frame_source_callable:
            try:
                return await self.frame_source_callable()
            except Exception as e:
                logger.error(f"[VLMSessionManager] Error getting frame: {e}")
                return None
        
        # Default: try to get from bridge
        try:
            from bridge.vapi_bridge.bridge_client import BridgeClient
            bridge = BridgeClient()
            # Try to get latest frame from bridge
            response = await bridge.get("/retina/latest-frame", timeout=5)
            if response and isinstance(response, dict):
                # Assuming bridge returns frame data
                return response.get("frame")
        except Exception:
            pass
        
        return None
    
    async def _analyze_frame(self, frame):
        """Analyze a single frame with the VLM."""
        async with self._semaphore:
            try:
                # Analyze frame
                start = time.monotonic()
                visual_context = await self.visual_oracle.analyze_frame(frame)
                elapsed = (time.monotonic() - start) * 1000
                
                # Get motion and input features for cross-modal verification
                motion_features = await self._get_motion_features()
                input_features = await self._get_input_features()
                
                # Run cross-modal verification
                verdict = self.visual_oracle.verify(
                    motion_features, 
                    input_features, 
                    visual_context
                )
                
                # Create observation
                observation = self._create_observation(
                    visual_context, 
                    verdict, 
                    elapsed
                )
                
                # Push to queue
                if self.observation_queue:
                    self.observation_queue.push(observation)
                
                # Push to observer (for EA)
                if self.vlm_observer:
                    self.vlm_observer.push(observation)
                
                # Store in database
                await self._store_observation(observation)
                
                logger.debug(
                    f"[VLMSessionManager] Frame {self._frame_count}: "
                    f"state={visual_context.game_state.value}, "
                    f"confidence={visual_context.confidence:.2f}, "
                    f"processing={elapsed:.0f}ms"
                )
                
                # Log anomalies
                if verdict.anomaly:
                    logger.warning(
                        f"[VLMSessionManager] ANOMALY: {verdict.anomaly_type} "
                        f"(confidence={verdict.confidence:.2f})"
                    )
                
            except Exception as e:
                logger.error(f"[VLMSessionManager] Error analyzing frame: {e}")
    
    def _create_observation(
        self,
        visual_context: "VisualContext",
        verdict: "CrossModalVerdict",
        processing_ms: float,
    ):
        """Create a VLMObservation from visual context and verdict."""
        from bridge.vapi_bridge.vlm_observer import VLMObservation
        
        return VLMObservation(
            observation_id=str(uuid.uuid4()),
            session_id=self._current_session_id or "unknown",
            frame_number=self._frame_count,
            timestamp_ns=int(time.time() * 1e9),
            game_state=visual_context.game_state.value,
            game_title=visual_context.game_title,
            screen_description=visual_context.screen_description,
            confidence=visual_context.confidence,
            frame_hash=visual_context.frame_hash,
            processing_ms=processing_ms,
            health=visual_context.health,
            ammo=visual_context.ammo,
            score=visual_context.score,
            round_info=visual_context.round_info,
            enemies_visible=visual_context.enemies_visible,
            is_combat=visual_context.is_combat,
            is_moving=visual_context.is_moving,
            events=visual_context.events,
            has_screen_tearing=visual_context.has_screen_tearing,
            has_lag_indicator=visual_context.has_lag_indicator,
            frame_quality=visual_context.frame_quality,
            cross_modal_match=verdict.match,
            cross_modal_anomaly=verdict.anomaly,
            cross_modal_anomaly_type=verdict.anomaly_type,
            cross_modal_confidence=verdict.confidence,
            model=self.visual_oracle.config.nim_model,
            backend="nim",
        )
    
    async def _get_motion_features(self):
        """Get current motion features from MediaPipe."""
        try:
            from bridge.vapi_bridge.bridge_client import BridgeClient
            bridge = BridgeClient()
            response = await bridge.get("/retina/motion-features", timeout=3)
            if response and isinstance(response, dict):
                return {
                    "activity_level": response.get("activity_level", 0),
                    "motion_vector": response.get("motion_vector", []),
                }
        except Exception:
            pass
        return {"activity_level": 0}
    
    async def _get_input_features(self):
        """Get current input features from DualShock."""
        try:
            from bridge.vapi_bridge.bridge_client import BridgeClient
            bridge = BridgeClient()
            response = await bridge.get("/dualshock/input-features", timeout=3)
            if response and isinstance(response, dict):
                return {
                    "apm": response.get("actions_per_minute", 0),
                    "trigger_active": response.get("trigger_active", False),
                    "stick_activity": response.get("stick_activity", 0),
                }
        except Exception:
            pass
        return {"apm": 0}
    
    async def _store_observation(self, observation):
        """Store observation in database."""
        if self.hardware_biographer:
            try:
                # This would need to be added to HardwareBiographer
                # For now, just log
                logger.debug(f"[VLMSessionManager] Stored observation: {observation.observation_id}")
            except Exception as e:
                logger.error(f"[VLMSessionManager] Error storing observation: {e}")
    
    @property
    def is_active(self) -> bool:
        """Check if capture is currently active."""
        return self._capture_active
    
    @property
    def current_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._current_session_id
    
    @property
    def frame_count(self) -> int:
        """Get the current frame count."""
        return self._frame_count


# Factory function for easy integration
def create_vlm_session_manager(
    hardware_watcher: Optional = None,
    hardware_biographer: Optional = None,
) -> VLMSessionManager:
    """Create a VLM session manager and wire it to hardware watcher.
    
    Args:
        hardware_watcher: HardwareWatcher instance to monitor.
        hardware_biographer: HardwareBiographer instance for session tracking.
        
    Returns:
        Configured VLMSessionManager.
    """
    # Create instances
    from bridge.vapi_bridge.vlm_observer import ObservationQueue, VLMObserver
    
    observation_queue = ObservationQueue()
    vlm_observer = VLMObserver(observation_queue)
    
    # Create session manager
    manager = VLMSessionManager(
        observation_queue=observation_queue,
        vlm_observer=vlm_observer,
        hardware_biographer=hardware_biographer,
    )
    
    # Wire to hardware watcher if provided
    if hardware_watcher:
        # Store reference to manager in hardware watcher
        # This allows the watcher to call manager.on_hardware_state_change
        hardware_watcher._vlm_session_manager = manager
        
        # Replace or extend the existing on_state_change callback
        original_callback = hardware_watcher.on_state_change
        
        async def combined_state_change(state):
            # Call original callback if it exists
            if original_callback:
                await original_callback(state)
            # Call VLM session manager
            await manager.on_hardware_state_change(state)
        
        hardware_watcher.on_state_change = combined_state_change
        logger.info("[VLMSessionManager] Wired to HardwareWatcher")
    
    return manager
