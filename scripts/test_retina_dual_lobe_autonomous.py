#!/usr/bin/env python3
"""
Autonomous Dual-Lobe Retina Capture Rig Test
==============================================

Comprehensive test suite for the CPU-optimized Trio-Retina Dual-Lobe inference framework.
Tests the full stack: retina_screen_lobe, retina_causal_coherence, screen_retina_fusion,
retina_onnx_bridge, and retina_perception with Thread C isolation.

Generated: 2026-07-26
Commit: d6768f17 (feat(dual-lobe): CPU-optimized inference framework for Trio-Retina)
"""

import sys
import os
import json
import time
import logging
import traceback
from pathlib import Path
from dataclasses import asdict
from typing import Optional

# Setup paths
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO / "scripts"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("retina_dual_lobe_test_2026_07_26.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("dual_lobe_test")

# ============================================================
# Test Results Tracking
# ============================================================

class TestResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.errors = []
        self.metrics = {}
        self.start_time = time.time()
        
    def add_pass(self, test_name: str, details: dict = None):
        self.passed.append({"test": test_name, "details": details or {}, "ts": time.time()})
        log.info(f"PASS: {test_name}")
        
    def add_fail(self, test_name: str, reason: str, details: dict = None):
        self.failed.append({"test": test_name, "reason": reason, "details": details or {}, "ts": time.time()})
        log.error(f"FAIL: {test_name} - {reason}")
        
    def add_error(self, test_name: str, exception: Exception):
        self.errors.append({
            "test": test_name,
            "exception": str(exception),
            "traceback": traceback.format_exc(),
            "ts": time.time()
        })
        log.error(f"ERROR: {test_name} - {exception}")
        
    def add_metric(self, name: str, value, unit: str = "", description: str = ""):
        self.metrics[name] = {"value": value, "unit": unit, "description": description}
        
    def summary(self) -> dict:
        elapsed = time.time() - self.start_time
        return {
            "summary": {
                "total_tests": len(self.passed) + len(self.failed) + len(self.errors),
                "passed": len(self.passed),
                "failed": len(self.failed),
                "errors": len(self.errors),
                "elapsed_seconds": round(elapsed, 3),
                "success_rate": round(
                    len(self.passed) / max(1, len(self.passed) + len(self.failed) + len(self.errors)) * 100, 2
                ) if (len(self.passed) + len(self.failed) + len(self.errors)) > 0 else 0,
            },
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "metrics": self.metrics,
        }

results = TestResult()

# ============================================================
# Test 1: Import and Module Availability
# ============================================================

def test_module_imports():
    """Test that all dual-lobe modules can be imported."""
    test_name = "test_module_imports"
    try:
        # Core dual-lobe modules
        from bridge.vapi_bridge.retina_screen_lobe import (
            HudState, ScreenEvent, parse_hud, diff_hud, is_input_caused,
            MotionVector, MediaPipeMotionTracker, MEDIAPIPE_AVAILABLE,
            EVT_DOWN_ADVANCED, EVT_FIRST_DOWN, EVT_SCORE_CHANGED,
            EVT_PLAYCLOCK_RESET, EVT_QUARTER_CHANGED,
        )
        results.add_metric("mediapipe_available", MEDIAPIPE_AVAILABLE, description="MediaPipe library availability")
        
        from bridge.vapi_bridge.retina_causal_coherence import (
            CoherenceVerdict, TimedEvent, OutcomeMatch, CoherenceReport,
            CoherenceConfig, assess_coherence, from_controller_events, from_screen_events,
            INPUT_EVENT_TYPES, DEFAULT_CAUSAL_WINDOW_S,
        )
        results.add_metric("causal_window_s", DEFAULT_CAUSAL_WINDOW_S, "s", "Default causal window")
        
        from bridge.vapi_bridge.screen_retina_fusion import (
            L9FusionVerdict, ContinuousAxis, L9FusionReport,
            ContinuousConfig, fuse_screen_retina, classify_continuous,
            NCAA_CONTINUOUS_CONFIG, DEFAULT_COUPLING_THRESHOLD,
            DEFAULT_NEG_CONTROL_GAP, DEFAULT_RESIDUAL_THRESHOLD,
        )
        
        from bridge.vapi_bridge.retina_onnx_bridge import (
            ONNXInferenceResult, ONNXInferenceSession, ThreadCIsolationGuard,
            ThreadCSafetyError, ONNX_AVAILABLE, create_onnx_bridge,
        )
        results.add_metric("onnx_available", ONNX_AVAILABLE, description="ONNX Runtime availability")
        
        from bridge.vapi_bridge.retina_perception import (
            RetinaPerceptionResult, run_controller_perception,
        )
        
        results.add_pass(test_name, {
            "modules": [
                "retina_screen_lobe", "retina_causal_coherence", 
                "screen_retina_fusion", "retina_onnx_bridge", "retina_perception"
            ],
            "mediapipe": MEDIAPIPE_AVAILABLE,
            "onnx": ONNX_AVAILABLE,
        })
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 2: Screen Lobe - HUD Parsing
# ============================================================

def test_screen_lobe_hud_parsing():
    """Test HUD parsing from OCR text."""
    test_name = "test_screen_lobe_hud_parsing"
    try:
        from bridge.vapi_bridge.retina_screen_lobe import parse_hud, HudState
        
        # Test various HUD formats
        test_cases = [
            ("3RD & 7 PLAY CLOCK 21", {"down": 3, "distance": 7, "play_clock": 21}),
            ("1st & GOAL 2nd QTR", {"down": 1, "distance": 0, "quarter": 2}),
            ("HOME 21 - 14 AWAY", {"score_a": 21, "score_b": 14}),
            ("4TH & 15", {"down": 4, "distance": 15}),
            ("1ST & 10", {"down": 1, "distance": 10}),
        ]
        
        passed = 0
        for text, expected in test_cases:
            h = parse_hud(text)
            for key, val in expected.items():
                if getattr(h, key) != val:
                    results.add_fail(test_name, f"HUD parse failed for '{text}': expected {key}={val}, got {getattr(h, key)}")
                    return False
            passed += 1
        
        results.add_pass(test_name, {"tested_formats": len(test_cases), "all_passed": True})
        results.add_metric("hud_parse_tests", passed, description="HUD parsing test cases passed")
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 3: Screen Lobe - HUD Diff
# ============================================================

def test_screen_lobe_hud_diff():
    """Test HUD state diffing for event detection."""
    test_name = "test_screen_lobe_hud_diff"
    try:
        from bridge.vapi_bridge.retina_screen_lobe import (
            HudState, diff_hud, is_input_caused,
            EVT_DOWN_ADVANCED, EVT_FIRST_DOWN, EVT_SCORE_CHANGED,
            EVT_PLAYCLOCK_RESET, EVT_QUARTER_CHANGED,
        )
        
        # Test down advanced
        evs = diff_hud(HudState(down=1, distance=10), HudState(down=2, distance=6), t=5.0)
        assert len(evs) == 1
        assert evs[0].type == EVT_DOWN_ADVANCED
        assert evs[0].input_caused is True
        
        # Test first down
        evs = diff_hud(HudState(down=3, distance=2), HudState(down=1, distance=10), t=5.0)
        assert evs[0].type == EVT_FIRST_DOWN
        assert evs[0].input_caused is True
        
        # Test score change
        evs = diff_hud(HudState(down=1, score_a=0, score_b=0), HudState(down=1, score_a=7, score_b=0), t=9.0)
        assert any(e.type == EVT_SCORE_CHANGED and e.input_caused for e in evs)
        
        # Test playclock reset (marker, not input-caused)
        evs = diff_hud(HudState(play_clock=3), HudState(play_clock=40), t=1.0)
        assert evs[0].type == EVT_PLAYCLOCK_RESET
        assert evs[0].input_caused is False
        
        # Test quarter change (marker, not input-caused)
        evs = diff_hud(HudState(quarter=1), HudState(quarter=2), t=1.0)
        assert evs[0].type == EVT_QUARTER_CHANGED
        assert evs[0].input_caused is False
        
        # Test OCR dropout never fabricates
        evs = diff_hud(HudState(down=2, distance=5), HudState(down=None), t=1.0)
        assert evs == []
        
        results.add_pass(test_name, {"event_types_tested": 6})
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 4: Causal Coherence Fusion
# ============================================================

def test_causal_coherence_fusion():
    """Test input-outcome causal coherence assessment."""
    test_name = "test_causal_coherence_fusion"
    try:
        from bridge.vapi_bridge.retina_causal_coherence import (
            CoherenceVerdict, TimedEvent, assess_coherence,
            from_controller_events, from_screen_events,
        )
        from bridge.vapi_bridge.retina_screen_lobe import (
            HudState, diff_hud, EVT_DOWN_ADVANCED,
        )
        
        # Test COHERENT: every outcome has preceding input
        inputs = [TimedEvent("input", "controller.trigger.onset", t) for t in [1.0, 11.0, 21.0]]
        outcomes = [TimedEvent("outcome", EVT_DOWN_ADVANCED, t, input_caused=True) for t in [3.0, 13.0, 23.0]]
        ev = inputs + outcomes
        rep = assess_coherence(ev)
        assert rep.verdict == CoherenceVerdict.COHERENT
        assert rep.coherence_ratio() == 1.0
        assert rep.n_matched == 3
        
        # Test ORPHAN_OUTCOME: screen advances without input
        rep = assess_coherence(outcomes)
        assert rep.verdict == CoherenceVerdict.ORPHAN_OUTCOME
        assert rep.n_matched == 0
        assert rep.coherence_ratio() == 0.0
        
        # Test ORPHAN_INPUT: input present but no outcomes (need 5+ inputs per config)
        # Create 5 inputs with no outcomes
        many_inputs = [TimedEvent("input", "controller.trigger.onset", t) for t in [1.0, 2.0, 3.0, 4.0, 5.0]]
        rep = assess_coherence(many_inputs)
        assert rep.verdict == CoherenceVerdict.ORPHAN_INPUT
        
        # Test INSUFFICIENT: too few outcomes (less than 3)
        rep = assess_coherence(inputs + outcomes[:1])
        assert rep.verdict == CoherenceVerdict.INSUFFICIENT
        
        results.add_pass(test_name, {
            "verdicts_tested": ["COHERENT", "ORPHAN_OUTCOME", "ORPHAN_INPUT", "INSUFFICIENT"],
        })
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 5: Screen-Retina Fusion (Tri-channel)
# ============================================================

def test_screen_retina_fusion():
    """Test tri-channel L9 screen-retina fusion."""
    test_name = "test_screen_retina_fusion"
    try:
        from bridge.vapi_bridge.screen_retina_fusion import (
            L9FusionVerdict, ContinuousAxis, fuse_screen_retina,
            classify_continuous, NCAA_CONTINUOUS_CONFIG,
        )
        from bridge.vapi_bridge.retina_causal_coherence import CoherenceVerdict
        
        # Test LIVE_COHERENT: coupling clean AND outcomes input-caused
        rep = fuse_screen_retina(
            coupling_score=0.95,
            negative_control=0.10,
            decoupled_energy=0.05,
            coherence=CoherenceVerdict.COHERENT,
            cfg=NCAA_CONTINUOUS_CONFIG,
        )
        assert rep.verdict is L9FusionVerdict.LIVE_COHERENT
        
        # Test LIVE_COUPLED: coupling clean, outcome evidence insufficient
        rep = fuse_screen_retina(
            coupling_score=0.95,
            negative_control=0.10,
            decoupled_energy=0.05,
            coherence=CoherenceVerdict.INSUFFICIENT,
            cfg=NCAA_CONTINUOUS_CONFIG,
        )
        assert rep.verdict is L9FusionVerdict.LIVE_COUPLED
        
        # Test REPLAY_OR_RELAY: screen not driven by this controller
        rep = fuse_screen_retina(
            coupling_score=0.05,
            negative_control=0.04,
            decoupled_energy=0.01,
            coherence=CoherenceVerdict.ORPHAN_OUTCOME,
            cfg=NCAA_CONTINUOUS_CONFIG,
        )
        assert rep.verdict is L9FusionVerdict.REPLAY_OR_RELAY
        
        results.add_pass(test_name, {
            "fusion_verdicts_tested": ["LIVE_COHERENT", "LIVE_COUPLED", "REPLAY_OR_RELAY"],
        })
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 6: ONNX Bridge - Thread C Isolation
# ============================================================

def test_onnx_bridge_thread_c():
    """Test Thread C isolation guard for L0 stability."""
    test_name = "test_onnx_bridge_thread_c"
    try:
        from bridge.vapi_bridge.retina_onnx_bridge import (
            ThreadCIsolationGuard, ThreadCSafetyError,
        )
        
        guard = ThreadCIsolationGuard(min_poll_rate_hz=990.0)
        
        # Test safe to proceed at healthy poll rate
        guard.update_poll_rate(1000.0)
        assert guard.check_safe_to_proceed() is True
        
        # Test safe to proceed at threshold
        guard.update_poll_rate(990.0)
        assert guard.check_safe_to_proceed() is True
        
        # Test NOT safe below threshold
        guard.update_poll_rate(989.0)
        assert guard.check_safe_to_proceed() is False
        
        # Test ThreadCSafetyError is raised
        try:
            guard.run_isolated(lambda: "test")
            results.add_fail(test_name, "Expected ThreadCSafetyError not raised")
            return False
        except ThreadCSafetyError as e:
            assert "989.0" in str(e)
            assert "killing Screen Lobe" in str(e)
        
        results.add_pass(test_name)
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 7: ONNX Inference Session
# ============================================================

def test_onnx_inference_session():
    """Test ONNX Runtime inference session."""
    test_name = "test_onnx_inference_session"
    try:
        from bridge.vapi_bridge.retina_onnx_bridge import (
            ONNXInferenceSession, ONNXInferenceResult, ONNX_AVAILABLE,
        )
        
        # Test session creation without model (fail-open)
        session = ONNXInferenceSession(model_path=None, enabled=True)
        
        # With model_path=None, session.enabled should be True if ONNX available
        # but session.session should be None
        if ONNX_AVAILABLE:
            assert session.enabled == True
            assert session.session is None
        else:
            assert session.enabled == False
        
        # Test with non-existent model path (fail-open)
        session = ONNXInferenceSession(model_path="/nonexistent/model.onnx", enabled=True)
        # This should fail during init and set enabled=False
        assert session.enabled == False
        
        results.add_pass(test_name, {"onnx_available": ONNX_AVAILABLE})
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 8: Retina Perception Integration
# ============================================================

def test_retina_perception_integration():
    """Test retina perception with dual-lobe integration."""
    test_name = "test_retina_perception_integration"
    try:
        from bridge.vapi_bridge.retina_perception import run_controller_perception
        from bridge.vapi_bridge.retina_onnx_bridge import create_onnx_bridge
        
        # Create mock HID snapshots
        snap_buffer = []
        for i in range(100):
            snap_buffer.append({
                "right_stick_x": 128 + int(10 * (i % 20)),
                "right_stick_y": 128 + int(10 * ((i + 5) % 20)),
                "left_stick_x": 128,
                "left_stick_y": 128,
                "l2_trigger": 0,
                "r2_trigger": 255 if i % 50 == 0 else 0,
                "gyro_x": 0.0,
                "gyro_y": 0.0,
                "gyro_z": 0.0,
                "accel_x": 0.0,
                "accel_y": 0.0,
                "accel_z": 1.0,
            })
        
        # Create ONNX bridge
        onnx_bridge = create_onnx_bridge(model_path=None)
        
        # Run perception (disabled by default, but test the call)
        result = run_controller_perception(
            snap_buffer=snap_buffer,
            enabled=False,  # Explicitly disabled for test
            source_id="test_dual_lobe",
            window=50,
            onnx_bridge=onnx_bridge,
            l0_poll_rate_hz=1000.0,
        )
        
        assert result.enabled is False
        assert result.source_id == "test_dual_lobe"
        
        # Run with enabled=True but short buffer (should fail gracefully)
        result = run_controller_perception(
            snap_buffer=snap_buffer[:10],  # Too short
            enabled=True,
            source_id="test_dual_lobe",
            window=50,
            onnx_bridge=onnx_bridge,
            l0_poll_rate_hz=1000.0,
        )
        
        assert result.enabled is True
        assert "buffer_short" in result.error
        
        results.add_pass(test_name, {"snapshots_tested": len(snap_buffer)})
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 9: End-to-End Dual-Lobe Pipeline
# ============================================================

def test_end_to_end_dual_lobe():
    """Test complete dual-lobe pipeline: screen -> OCR -> events -> fusion."""
    test_name = "test_end_to_end_dual_lobe"
    try:
        from bridge.vapi_bridge.retina_screen_lobe import (
            HudState, diff_hud, parse_hud, EVT_DOWN_ADVANCED, EVT_FIRST_DOWN,
        )
        from bridge.vapi_bridge.retina_causal_coherence import (
            CoherenceVerdict, TimedEvent, assess_coherence,
            from_controller_events, from_screen_events,
        )
        from bridge.vapi_bridge.screen_retina_fusion import (
            fuse_screen_retina, NCAA_CONTINUOUS_CONFIG, L9FusionVerdict,
        )
        
        # Simulate a play sequence
        hud_states = [
            HudState(down=1, distance=10, play_clock=40, quarter=1, score_a=0, score_b=0),
            HudState(down=2, distance=5, play_clock=35, quarter=1, score_a=0, score_b=0),
            HudState(down=3, distance=2, play_clock=25, quarter=1, score_a=0, score_b=0),
            HudState(down=4, distance=8, play_clock=15, quarter=1, score_a=0, score_b=0),
            HudState(down=1, distance=10, play_clock=40, quarter=1, score_a=7, score_b=0),  # Score!
        ]
        
        # Generate screen events from HUD transitions
        screen_events = []
        for i in range(1, len(hud_states)):
            evs = diff_hud(hud_states[i-1], hud_states[i], t=float(i) * 5.0)
            screen_events.extend(evs)
        
        # Generate controller input events (simulating player actions)
        controller_events = [
            {"type": "controller.trigger.onset", "t": 2.0},  # Before first down advance
            {"type": "controller.stick.radial_jump", "t": 7.0},  # Before second down advance
            {"type": "controller.trigger.onset", "t": 12.0},  # Before third down advance
            {"type": "controller.trigger.onset", "t": 18.0},  # Before fourth down advance
            {"type": "controller.trigger.onset", "t": 22.0},  # The scoring play
        ]
        
        # Convert to TimedEvents
        input_events = from_controller_events(controller_events)
        outcome_events = from_screen_events(screen_events)
        
        # Assess causal coherence
        all_events = input_events + outcome_events
        coherence_rep = assess_coherence(all_events)
        
        # Fuse with continuous coupling (simulated)
        fusion_rep = fuse_screen_retina(
            coupling_score=0.95,
            negative_control=0.10,
            decoupled_energy=0.05,
            coherence=coherence_rep.verdict,
            cfg=NCAA_CONTINUOUS_CONFIG,
        )
        
        # Verify results
        assert coherence_rep.verdict == CoherenceVerdict.COHERENT or coherence_rep.verdict == CoherenceVerdict.INSUFFICIENT
        assert fusion_rep.verdict in [
            L9FusionVerdict.LIVE_COHERENT, 
            L9FusionVerdict.LIVE_COUPLED,
            L9FusionVerdict.INSUFFICIENT
        ]
        
        results.add_pass(test_name, {
            "hud_states": len(hud_states),
            "screen_events": len(screen_events),
            "controller_events": len(controller_events),
            "coherence_verdict": coherence_rep.verdict.value,
            "fusion_verdict": fusion_rep.verdict.value,
        })
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 10: Bridge Startup Simulation
# ============================================================

def test_bridge_startup_simulation():
    """Simulate bridge startup with dual-lobe configuration."""
    test_name = "test_bridge_startup_simulation"
    try:
        from bridge.vapi_bridge.config import Config
        
        # Create config with dual-lobe settings
        cfg = Config()
        
        # Check retina-related config
        retina_capture_enabled = getattr(cfg, 'retina_game_capture_enabled', False)
        retina_perception_enabled = getattr(cfg, 'retina_perception_enabled', False)
        retina_hid_events_enabled = getattr(cfg, 'retina_hid_events_enabled', False)
        
        results.add_pass(test_name, {
            "retina_game_capture_enabled": retina_capture_enabled,
            "retina_perception_enabled": retina_perception_enabled,
            "retina_hid_events_enabled": retina_hid_events_enabled,
        })
        
        results.add_metric("retina_capture_enabled", retina_capture_enabled, description="Retina game capture enabled")
        results.add_metric("retina_perception_enabled", retina_perception_enabled, description="Retina perception enabled")
        results.add_metric("retina_hid_events_enabled", retina_hid_events_enabled, description="Retina HID events enabled")
        
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Test 11: CPU Optimization Verification
# ============================================================

def test_cpu_optimization():
    """Verify CPU optimization features are present."""
    test_name = "test_cpu_optimization"
    try:
        from bridge.vapi_bridge.retina_onnx_bridge import (
            ThreadCIsolationGuard, ONNXInferenceSession,
        )
        from bridge.vapi_bridge.retina_screen_lobe import MediaPipeMotionTracker
        
        # Verify Thread C isolation exists
        guard = ThreadCIsolationGuard()
        assert hasattr(guard, 'check_safe_to_proceed')
        assert hasattr(guard, 'run_isolated')
        
        # Verify ONNX session exists
        session = ONNXInferenceSession()
        assert hasattr(session, 'run_trajectory_inference')
        
        # Verify MediaPipe motion tracker exists
        tracker = MediaPipeMotionTracker()
        assert hasattr(tracker, 'track_frame')
        
        results.add_pass(test_name, {
            "thread_c_isolation": True,
            "onnx_inference": True,
            "mediapipe_tracking": True,
        })
        return True
    except Exception as e:
        results.add_error(test_name, e)
        return False

# ============================================================
# Main Test Runner
# ============================================================

TESTS = [
    ("Module Imports", test_module_imports),
    ("Screen Lobe HUD Parsing", test_screen_lobe_hud_parsing),
    ("Screen Lobe HUD Diff", test_screen_lobe_hud_diff),
    ("Causal Coherence Fusion", test_causal_coherence_fusion),
    ("Screen-Retina Fusion", test_screen_retina_fusion),
    ("ONNX Bridge Thread C", test_onnx_bridge_thread_c),
    ("ONNX Inference Session", test_onnx_inference_session),
    ("Retina Perception Integration", test_retina_perception_integration),
    ("End-to-End Dual-Lobe", test_end_to_end_dual_lobe),
    ("Bridge Startup Simulation", test_bridge_startup_simulation),
    ("CPU Optimization Verification", test_cpu_optimization),
]


def run_all_tests():
    """Run all dual-lobe tests autonomously."""
    log.info("=" * 70)
    log.info("Dual-Lobe Retina Capture Rig Autonomous Test Suite")
    log.info("Commit: d6768f17 (feat(dual-lobe): CPU-optimized inference framework)")
    log.info("Date: 2026-07-26")
    log.info("=" * 70)
    
    for name, test_fn in TESTS:
        log.info(f"\n--- Running: {name} ---")
        try:
            test_fn()
        except Exception as e:
            results.add_error(name, e)
    
    # Generate summary
    summary = results.summary()
    log.info("\n" + "=" * 70)
    log.info("TEST SUMMARY")
    log.info("=" * 70)
    log.info(f"Total Tests: {summary['summary']['total_tests']}")
    log.info(f"Passed: {summary['summary']['passed']}")
    log.info(f"Failed: {summary['summary']['failed']}")
    log.info(f"Errors: {summary['summary']['errors']}")
    log.info(f"Success Rate: {summary['summary']['success_rate']}%")
    log.info(f"Elapsed Time: {summary['summary']['elapsed_seconds']}s")
    
    # Write summary to file
    with open("retina_dual_lobe_test_2026_07_26_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Write metrics to file
    with open("retina_dual_lobe_test_2026_07_26_metrics.json", "w") as f:
        json.dump(summary['metrics'], f, indent=2, default=str)
    
    log.info(f"\nResults written to:")
    log.info(f"  - retina_dual_lobe_test_2026_07_26.log")
    log.info(f"  - retina_dual_lobe_test_2026_07_26_summary.json")
    log.info(f"  - retina_dual_lobe_test_2026_07_26_metrics.json")
    
    return summary


if __name__ == "__main__":
    try:
        summary = run_all_tests()
        
        # Exit code based on results
        if summary['summary']['failed'] > 0 or summary['summary']['errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
    except Exception as e:
        log.error(f"Fatal error in test runner: {e}")
        traceback.print_exc()
        sys.exit(2)
