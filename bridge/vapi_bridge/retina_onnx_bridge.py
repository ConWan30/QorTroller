"""QorTroller × Trio-Retina — ONNX Runtime + OpenVINO CPU-optimized inference bridge.

This module provides CPU-optimized trajectory-authenticity model inference using
ONNX Runtime with OpenVINO backend for AVX2/AVX-512 vector instructions on laptop CPUs.
Resolves the structural Throughput Bottleneck (F-HW-1) and Python ProactorEventLoop starvation
by offloading dynamics math to a "Super-Thread-C" inference sidecar.

Key innovations:
- Thread C isolation to prevent event-loop starvation
- CPU vector instruction optimization (AVX2/AVX-512) 
- Fail-open design for missing ONNX dependencies
- Preserves existing retina_controller_embedder functionality
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Callable, Any
import asyncio

# ONNX Runtime integration (optional, gated by availability)
try:
    import onnxruntime as ort
    import numpy as np
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

log = logging.getLogger(__name__)

SCHEMA_TAG = "vapi-retina-onnx-bridge-v1"


@dataclass
class ONNXInferenceResult:
    """Result from ONNX Runtime trajectory-authenticity inference."""
    trajectory_features: Optional["np.ndarray"] = None
    latency_ms: float = 0.0
    error: str = ""
    model_version: str = ""


class ThreadCIsolationGuard:
    """Thread C isolation guard to maintain 1000 Hz HID poll rate stability.
    
    Monitors L0 poll rate and auto-kills Screen Lobe if poll_rate_hz drops below 990,
    preserving the "anti-cheat moat" per INV-RETINA-LOOP-001.
    """
    
    def __init__(self, min_poll_rate_hz: float = 990.0):
        self.min_poll_rate_hz = min_poll_rate_hz
        self.current_poll_rate = 1000.0  # Assume healthy start
        self.executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="inference_thread_c_"
        )
    
    def update_poll_rate(self, current_hz: float):
        """Update current L0 poll rate from HID telemetry."""
        self.current_poll_rate = current_hz
    
    def check_safe_to_proceed(self) -> bool:
        """Check if Thread C can safely proceed without degrading L0 stability."""
        return self.current_poll_rate >= self.min_poll_rate_hz
    
    def run_isolated(self, inference_fn: Callable) -> Any:
        """Run inference in isolated Thread C with L0 monitoring.
        
        Args:
            inference_fn: Function to run in isolated thread
            
        Returns:
            Result from inference_fn
            
        Raises:
            ThreadCSafetyError: If L0 poll rate degraded below threshold
        """
        if not self.check_safe_to_proceed():
            raise ThreadCSafetyError(
                f"L0 poll rate {self.current_poll_rate:.1f} Hz below "
                f"threshold {self.min_poll_rate_hz} Hz - killing Screen Lobe"
            )
        
        # Run in isolated Thread C to prevent event-loop starvation
        future = self.executor.submit(inference_fn)
        return future.result()
    
    async def run_isolated_async(self, inference_fn: Callable) -> Any:
        """Async wrapper for isolated Thread C execution."""
        if not self.check_safe_to_proceed():
            raise ThreadCSafetyError(
                f"L0 poll rate {self.current_poll_rate:.1f} Hz below "
                f"threshold {self.min_poll_rate_hz} Hz - killing Screen Lobe"
            )
        
        # Offload to Thread C using asyncio.to_thread
        return await asyncio.to_thread(inference_fn)
    
    def shutdown(self):
        """Clean up Thread C resources."""
        self.executor.shutdown(wait=True)


class ThreadCSafetyError(Exception):
    """Raised when Thread C execution would degrade L0 stability."""
    pass


class ONNXInferenceSession:
    """ONNX Runtime inference session for trajectory-authenticity models.
    
    CPU-optimized using OpenVINO backend for AVX2/AVX-512 vector instructions.
    Fail-open design: gracefully degrades if ONNX Runtime unavailable.
    """
    
    def __init__(self, model_path: Optional[str] = None, enabled: bool = True):
        self.enabled = enabled and ONNX_AVAILABLE
        self.model_path = model_path
        self.session = None
        self.thread_c_guard = ThreadCIsolationGuard()
        
        if self.enabled and model_path:
            try:
                # Configure ONNX Runtime for CPU optimization
                so = ort.SessionOptions()
                so.intra_op_num_threads = 2  # Limit to prevent CPU saturation
                so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                
                # Use OpenVINO if available for CPU vector instruction optimization
                providers = ['CPUExecutionProvider']
                if 'OpenVINOExecutionProvider' in ort.get_available_providers():
                    providers.insert(0, 'OpenVINOExecutionProvider')
                
                self.session = ort.InferenceSession(model_path, so, providers=providers)
                log.info(f"ONNX Runtime session loaded: {model_path} with providers {providers}")
            except Exception as e:
                # Fail-open if ONNX Runtime initialization fails
                self.enabled = False
                log.warning(f"ONNX Runtime initialization failed: {e}, falling back to pure Python")
    
    def run_trajectory_inference(
        self, 
        hid_sequence: Any,
        use_thread_c: bool = True
    ) -> ONNXInferenceResult:
        """Run trajectory-authenticity inference on HID sequence.
        
        Args:
            hid_sequence: HID telemetry sequence (controller window)
            use_thread_c: Whether to use Thread C isolation
            
        Returns:
            ONNXInferenceResult with trajectory features or error
        """
        if not self.enabled or self.session is None:
            return ONNXInferenceResult(
                error="ONNX Runtime not available or session not loaded"
            )
        
        def _inference_fn():
            import time
            start = time.time()
            
            try:
                # Prepare input tensor (assuming normalized controller state)
                if hasattr(hid_sequence, '__iter__'):
                    input_array = self._prepare_input_tensor(hid_sequence)
                else:
                    input_array = hid_sequence
                
                # Run ONNX inference
                outputs = self.session.run(
                    None, 
                    {'hid_sequence': input_array}
                )
                
                latency_ms = (time.time() - start) * 1000.0
                return ONNXInferenceResult(
                    trajectory_features=outputs[0] if outputs else None,
                    latency_ms=latency_ms,
                    model_version="onnx-v1"
                )
            except Exception as e:
                return ONNXInferenceResult(error=str(e))
        
        if use_thread_c:
            try:
                return self.thread_c_guard.run_isolated(_inference_fn)
            except ThreadCSafetyError as e:
                return ONNXInferenceResult(error=str(e))
        else:
            return _inference_fn()
    
    async def run_trajectory_inference_async(
        self, 
        hid_sequence: Any
    ) -> ONNXInferenceResult:
        """Async version of trajectory inference using Thread C isolation."""
        if not self.enabled or self.session is None:
            return ONNXInferenceResult(
                error="ONNX Runtime not available or session not loaded"
            )
        
        def _inference_fn():
            import time
            start = time.time()
            
            try:
                input_array = self._prepare_input_tensor(hid_sequence)
                outputs = self.session.run(None, {'hid_sequence': input_array})
                latency_ms = (time.time() - start) * 1000.0
                return ONNXInferenceResult(
                    trajectory_features=outputs[0] if outputs else None,
                    latency_ms=latency_ms,
                    model_version="onnx-v1"
                )
            except Exception as e:
                return ONNXInferenceResult(error=str(e))
        
        try:
            return await self.thread_c_guard.run_isolated_async(_inference_fn)
        except ThreadCSafetyError as e:
            return ONNXInferenceResult(error=str(e))
    
    def _prepare_input_tensor(self, hid_sequence: Any) -> "np.ndarray":
        """Prepare HID sequence as ONNX input tensor."""
        # Convert HID sequence to numpy array with expected shape
        # This is a simplified version - actual implementation depends on model format
        if isinstance(hid_sequence, list):
            return np.array(hid_sequence, dtype=np.float32)
        elif hasattr(hid_sequence, '__array__'):
            return np.asarray(hid_sequence, dtype=np.float32)
        else:
            # Fallback for single sample
            return np.array([[hid_sequence]], dtype=np.float32)
    
    def update_l0_poll_rate(self, current_hz: float):
        """Update L0 poll rate for Thread C safety monitoring."""
        self.thread_c_guard.update_poll_rate(current_hz)
    
    def close(self):
        """Clean up ONNX Runtime and Thread C resources."""
        if self.session is not None:
            # ONNX Runtime sessions don't have explicit close in Python API
            self.session = None
        self.thread_c_guard.shutdown()


def create_onnx_bridge(
    model_path: Optional[str] = None,
    enabled: bool = True
) -> ONNXInferenceSession:
    """Factory function to create ONNX inference bridge.
    
    Args:
        model_path: Path to ONNX model file (optional for testing)
        enabled: Whether to enable ONNX Runtime (auto-disables if unavailable)
        
    Returns:
        ONNXInferenceSession instance
    """
    return ONNXInferenceSession(model_path=model_path, enabled=enabled)