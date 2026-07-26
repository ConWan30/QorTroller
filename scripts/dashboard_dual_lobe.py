#!/usr/bin/env python3
"""
Dual-Lobe Real-Time Dashboard
==============================

A FastAPI-based real-time dashboard for monitoring Dual-Lobe Retina metrics.
This dashboard provides live visibility into the CPU-optimized inference framework
for Trio-Retina, including:

- L0 poll rate monitoring (Thread C isolation)
- Screen lobe HUD parsing statistics
- Controller lobe input event metrics
- Causal coherence assessment results
- Tri-channel fusion verdicts
- ONNX Runtime inference performance
- MediaPipe motion tracking stats

Usage:
    python scripts/dashboard_dual_lobe.py
    
Then open: http://localhost:8080

Environment Variables:
    DASHBOARD_PORT: Port to listen on (default: 8080)
    DASHBOARD_HOST: Host to bind to (default: 0.0.0.0)
"""

import sys
import os
import json
import time
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from collections import defaultdict, deque
from datetime import datetime

# Setup paths
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "bridge"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("dual_lobe_dashboard")

# ============================================================
# Data Models
# ============================================================

@dataclass
class ScreenLobeMetrics:
    """Metrics for the screen (OCR) lobe."""
    hud_parse_count: int = 0
    hud_parse_errors: int = 0
    events_detected: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    ocr_dropout_count: int = 0
    motion_vectors_computed: int = 0
    motion_vector_errors: int = 0
    avg_hud_parse_ms: float = 0.0
    last_hud_text: Optional[str] = None
    last_hud_state: Optional[Dict[str, Any]] = None


@dataclass
class ControllerLobeMetrics:
    """Metrics for the controller (HID) lobe."""
    input_events: int = 0
    trigger_onsets: int = 0
    stick_jumps: int = 0
    tremor_anomalies: int = 0
    poll_rate_hz: float = 0.0
    poll_rate_min: float = 1000.0
    poll_rate_max: float = 0.0
    avg_poll_interval_ms: float = 0.0
    last_poll_ts: Optional[float] = None


@dataclass
class CoherenceMetrics:
    """Metrics for causal coherence assessment."""
    assessments: int = 0
    verdict_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    coherence_ratio_avg: float = 0.0
    coherence_ratio_min: float = 1.0
    coherence_ratio_max: float = 0.0
    n_matched_total: int = 0
    n_required_total: int = 0
    avg_matched_per_assessment: float = 0.0
    last_verdict: Optional[str] = None
    last_coherence_ratio: Optional[float] = None


@dataclass
class FusionMetrics:
    """Metrics for tri-channel fusion."""
    assessments: int = 0
    verdict_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    coupling_score_avg: float = 0.0
    coupling_score_min: float = 1.0
    coupling_score_max: float = 0.0
    negative_control_avg: float = 0.0
    decoupled_energy_avg: float = 0.0
    last_verdict: Optional[str] = None
    last_coupling_score: Optional[float] = None
    last_negative_control: Optional[float] = None
    last_decoupled_energy: Optional[float] = None


@dataclass
class ThreadCMetrics:
    """Metrics for Thread C isolation."""
    invocations: int = 0
    blocked: int = 0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    poll_rate_min: float = 1000.0
    poll_rate_max: float = 0.0
    safe: bool = True
    last_blocked_reason: Optional[str] = None
    last_latency_ms: Optional[float] = None


@dataclass
class ONNXMetrics:
    """Metrics for ONNX Runtime inference."""
    invocations: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    avg_trajectory_features: int = 0
    enabled: bool = False
    model_loaded: bool = False
    last_invocation_ts: Optional[float] = None


@dataclass
class MediaPipeMetrics:
    """Metrics for MediaPipe motion tracking."""
    frames_processed: int = 0
    motion_vectors_extracted: int = 0
    tracking_success_count: int = 0
    tracking_failure_count: int = 0
    avg_confidence: float = 0.0
    avg_motion_magnitude: float = 0.0
    enabled: bool = False
    last_frame_ts: Optional[float] = None


@dataclass
class DualLobeDashboardState:
    """Complete dashboard state."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    uptime_seconds: float = 0.0
    screen_lobe: ScreenLobeMetrics = field(default_factory=ScreenLobeMetrics)
    controller_lobe: ControllerLobeMetrics = field(default_factory=ControllerLobeMetrics)
    coherence: CoherenceMetrics = field(default_factory=CoherenceMetrics)
    fusion: FusionMetrics = field(default_factory=FusionMetrics)
    thread_c: ThreadCMetrics = field(default_factory=ThreadCMetrics)
    onnx: ONNXMetrics = field(default_factory=ONNXMetrics)
    mediapipe: MediaPipeMetrics = field(default_factory=MediaPipeMetrics)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "uptime_seconds": round(self.uptime_seconds, 3),
            "screen_lobe": asdict(self.screen_lobe),
            "controller_lobe": asdict(self.controller_lobe),
            "coherence": asdict(self.coherence),
            "fusion": asdict(self.fusion),
            "thread_c": asdict(self.thread_c),
            "onnx": asdict(self.onnx),
            "mediapipe": asdict(self.mediapipe),
        }
    
    def health_summary(self) -> Dict[str, Any]:
        """Generate a health summary for the dashboard."""
        return {
            "status": "healthy" if self.thread_c.safe else "degraded",
            "l0_poll_rate_hz": round(self.controller_lobe.poll_rate_hz, 1),
            "thread_c_safe": self.thread_c.safe,
            "mediapipe_enabled": self.mediapipe.enabled,
            "onnx_enabled": self.onnx.enabled,
            "retina_capture_enabled": False,  # Would be read from config
            "retina_perception_enabled": False,  # Would be read from config
            "last_coupling_score": self.fusion.last_coupling_score,
            "last_coherence_verdict": self.coherence.last_verdict,
            "last_fusion_verdict": self.fusion.last_verdict,
        }


# ============================================================
# Dashboard Server
# ============================================================

class DualLobeDashboard:
    """Real-time dashboard for Dual-Lobe metrics."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.start_time = time.time()
        self.state = DualLobeDashboardState()
        self._lock = asyncio.Lock()
        
        # History for time-series data
        self._history_size = 100
        self._coherence_history = deque(maxlen=self._history_size)
        self._fusion_history = deque(maxlen=self._history_size)
        self._poll_rate_history = deque(maxlen=self._history_size)
    
    def update_uptime(self):
        """Update uptime in state."""
        self.state.uptime_seconds = time.time() - self.start_time
    
    async def update_screen_lobe(self, **kwargs) -> None:
        """Update screen lobe metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.screen_lobe, key):
                    setattr(self.state.screen_lobe, key, value)
    
    async def update_controller_lobe(self, **kwargs) -> None:
        """Update controller lobe metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.controller_lobe, key):
                    setattr(self.state.controller_lobe, key, value)
            
            # Update poll rate history
            if 'poll_rate_hz' in kwargs:
                self._poll_rate_history.append(kwargs['poll_rate_hz'])
                self.state.controller_lobe.poll_rate_min = min(
                    self.state.controller_lobe.poll_rate_min, kwargs['poll_rate_hz']
                )
                self.state.controller_lobe.poll_rate_max = max(
                    self.state.controller_lobe.poll_rate_max, kwargs['poll_rate_hz']
                )
    
    async def update_coherence(self, **kwargs) -> None:
        """Update coherence metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.coherence, key):
                    setattr(self.state.coherence, key, value)
            
            # Update history
            if 'last_verdict' in kwargs and 'last_coherence_ratio' in kwargs:
                self._coherence_history.append({
                    'verdict': kwargs['last_verdict'],
                    'ratio': kwargs['last_coherence_ratio'],
                    'ts': time.time()
                })
    
    async def update_fusion(self, **kwargs) -> None:
        """Update fusion metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.fusion, key):
                    setattr(self.state.fusion, key, value)
            
            # Update history
            if 'last_verdict' in kwargs:
                self._fusion_history.append({
                    'verdict': kwargs['last_verdict'],
                    'ts': time.time()
                })
    
    async def update_thread_c(self, **kwargs) -> None:
        """Update Thread C metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.thread_c, key):
                    setattr(self.state.thread_c, key, value)
    
    async def update_onnx(self, **kwargs) -> None:
        """Update ONNX metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.onnx, key):
                    setattr(self.state.onnx, key, value)
    
    async def update_mediapipe(self, **kwargs) -> None:
        """Update MediaPipe metrics."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state.mediapipe, key):
                    setattr(self.state.mediapipe, key, value)
    
    async def get_state(self) -> DualLobeDashboardState:
        """Get current dashboard state."""
        async with self._lock:
            self.update_uptime()
            return self.state
    
    async def get_health(self) -> Dict[str, Any]:
        """Get health summary."""
        state = await self.get_state()
        return state.health_summary()
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get full metrics."""
        state = await self.get_state()
        return state.to_dict()
    
    async def get_history(self) -> Dict[str, Any]:
        """Get time-series history."""
        return {
            "coherence": list(self._coherence_history),
            "fusion": list(self._fusion_history),
            "poll_rate": list(self._poll_rate_history),
        }
    
    async def start(self) -> None:
        """Start the dashboard server."""
        try:
            # Try to use FastAPI if available
            from fastapi import FastAPI
            from fastapi.middleware.cors import CORSMiddleware
            import uvicorn
            
            app = FastAPI(
                title="QorTroller Dual-Lobe Dashboard",
                description="Real-time dashboard for Dual-Lobe Retina metrics",
                version="1.0.0",
            )
            
            # CORS middleware
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            # Endpoints
            @app.get("/")
            async def root():
                return {
                    "name": "QorTroller Dual-Lobe Dashboard",
                    "version": "1.0.0",
                    "endpoints": {
                        "/health": "Health summary",
                        "/metrics": "Full metrics",
                        "/history": "Time-series history",
                        "/state": "Complete state",
                    }
                }
            
            @app.get("/health")
            async def health():
                return await self.get_health()
            
            @app.get("/metrics")
            async def metrics():
                return await self.get_metrics()
            
            @app.get("/history")
            async def history():
                return await self.get_history()
            
            @app.get("/state")
            async def state():
                state = await self.get_state()
                return state.to_dict()
            
            # Start server
            log.info(f"Starting Dual-Lobe Dashboard on {self.host}:{self.port}")
            await uvicorn.run(
                app,
                host=self.host,
                port=self.port,
                log_level="info",
            )
        
        except ImportError as e:
            log.warning(f"FastAPI not available: {e}. Falling back to simple HTTP server.")
            await self._start_simple_server()
    
    async def _start_simple_server(self) -> None:
        """Start a simple HTTP server without FastAPI."""
        import http.server
        import socketserver
        from urllib.parse import urlparse, parse_qs
        import json
        
        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                
                if parsed.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    # Use sync wrapper for async methods
                    import asyncio
                    health_data = asyncio.run(dashboard.get_health())
                    self.wfile.write(json.dumps(health_data).encode())
                
                elif parsed.path == "/metrics":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    import asyncio
                    metrics_data = asyncio.run(dashboard.get_metrics())
                    self.wfile.write(json.dumps(metrics_data).encode())
                
                elif parsed.path == "/state":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    import asyncio
                    state = asyncio.run(dashboard.get_state())
                    self.wfile.write(json.dumps(state.to_dict()).encode())
                
                elif parsed.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "name": "QorTroller Dual-Lobe Dashboard (Simple Mode)",
                        "endpoints": ["/health", "/metrics", "/state"]
                    }).encode())
                
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not Found")
            
            def log_message(self, format, *args):
                log.info(f"{self.client_address[0]} - {format % args}")
        
        with socketserver.TCPServer((self.host, self.port), DashboardHandler) as httpd:
            log.info(f"Starting Dual-Lobe Dashboard (Simple Mode) on {self.host}:{self.port}")
            httpd.serve_forever()


# ============================================================
# CLI Integration
# ============================================================

async def main():
    """Main entry point."""
    host = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.environ.get("DASHBOARD_PORT", "8080"))
    
    dashboard = DualLobeDashboard(host=host, port=port)
    
    # Add some initial data for testing
    dashboard.state.screen_lobe.hud_parse_count = 0
    dashboard.state.controller_lobe.poll_rate_hz = 1000.0
    dashboard.state.thread_c.safe = True
    
    try:
        await dashboard.start()
    except RuntimeError as e:
        # If we're running inside an existing event loop (e.g., Hermes agent)
        # this will fail. Provide a helpful message.
        if "event loop" in str(e).lower():
            log.error(
                f"Cannot start dashboard: {e}\n"
                f"This typically happens when running inside an async context like Hermes agent.\n"
                f"To run the dashboard standalone, use:\n"
                f"  python scripts/dashboard_dual_lobe.py\n"
                f"Or start it in a separate process/terminal."
            )
            raise SystemExit(1) from e
        raise



if __name__ == "__main__":
    asyncio.run(main())
