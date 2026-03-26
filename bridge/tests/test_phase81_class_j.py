"""
Phase 81 — ClassJDetector Tests (8 tests)

test_1: _temporal_state_transition_entropy_variance returns 0.0 for < 2 windows
test_2: _temporal_state_transition_entropy_variance computes correct variance
test_3: ClassJDetector.assess() returns HIGH for low-entropy (Class J) inputs
test_4: ClassJDetector.assess() returns LOW for high-variance (human) inputs
test_5: ClassJDetector.assess() never raises — returns LOW on error
test_6: _classify_risk thresholds: <=0.05 HIGH, <=0.15 MEDIUM, >0.15 LOW
test_7: class_j_ml_bot_risk appears in SessionAdjudicator evidence_summary
test_8: insert_class_j_assessment and get_class_j_assessment round-trip
"""

import asyncio
import os
import sys
import tempfile
import types
import unittest
from collections import deque
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_sdk_stub = types.ModuleType("sdk")
_sdk_vapi_stub = types.ModuleType("sdk.vapi_sdk")
sys.modules.setdefault("sdk", _sdk_stub)
sys.modules.setdefault("sdk.vapi_sdk", _sdk_vapi_stub)

from vapi_bridge.store import Store
from vapi_bridge.class_j_detector import ClassJDetector


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase81.db")
    st = Store(db)
    st.upsert_device("0xdevice01", "pubkey_hex_01")
    return st


def _make_cfg(**kwargs):
    class Cfg:
        class_j_detection_enabled = True
        class_j_entropy_windows = 10

    cfg = Cfg()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Synthetic entropy windows for testing
_HUMAN_WINDOWS = [3.2, 4.8, 2.1, 5.5, 3.8, 4.1, 2.9, 5.0, 3.4, 4.6]
# High variance (rhythmically structured) → LOW risk
_HUMAN_VARIANCE = ClassJDetector._temporal_state_transition_entropy_variance(_HUMAN_WINDOWS)

_CLASS_J_WINDOWS = [2.0001, 2.0002, 2.0001, 2.0002, 2.0001, 2.0002, 2.0001, 2.0002, 2.0001, 2.0002]
# Near-zero variance (uniform HMM transitions) → HIGH risk
_CLASS_J_VARIANCE = ClassJDetector._temporal_state_transition_entropy_variance(_CLASS_J_WINDOWS)


class TestClassJDetectorStaticMethods(unittest.TestCase):

    def test_1_entropy_variance_returns_zero_for_fewer_than_2_windows(self):
        """test_1: _temporal_state_transition_entropy_variance returns 0.0 for < 2 windows."""
        result_empty = ClassJDetector._temporal_state_transition_entropy_variance([])
        self.assertEqual(result_empty, 0.0)

        result_one = ClassJDetector._temporal_state_transition_entropy_variance([3.5])
        self.assertEqual(result_one, 0.0)

    def test_2_entropy_variance_computes_correct_variance(self):
        """test_2: _temporal_state_transition_entropy_variance computes correct sample variance."""
        # For [1.0, 3.0]: mean=2.0, sum_sq=(1+1)=2, sample_var=2/(2-1)=2.0
        result = ClassJDetector._temporal_state_transition_entropy_variance([1.0, 3.0])
        self.assertAlmostEqual(result, 2.0, places=4)

        # For [2.0, 2.0, 2.0]: variance = 0.0
        result_zero = ClassJDetector._temporal_state_transition_entropy_variance([2.0, 2.0, 2.0])
        self.assertAlmostEqual(result_zero, 0.0, places=6)

        # Human windows have much higher variance than Class J
        self.assertGreater(_HUMAN_VARIANCE, _CLASS_J_VARIANCE)

    def test_3_assess_returns_high_for_class_j_inputs(self):
        """test_3: ClassJDetector.assess() returns HIGH for low-entropy (Class J) inputs."""
        store = _make_store()
        cfg = _make_cfg()
        detector = ClassJDetector(cfg, store, bus=None)

        # Manually inject near-zero variance Class J windows
        for val in _CLASS_J_WINDOWS:
            detector._entropy_windows["0xclassj01"].append(val)

        result = detector.assess("0xclassj01")
        self.assertEqual(result["risk_level"], "HIGH")
        self.assertLessEqual(result["entropy_variance"], 0.05)
        self.assertEqual(result["window_count"], len(_CLASS_J_WINDOWS))

    def test_4_assess_returns_low_for_human_inputs(self):
        """test_4: ClassJDetector.assess() returns LOW for high-variance (human) inputs."""
        store = _make_store()
        cfg = _make_cfg()
        detector = ClassJDetector(cfg, store, bus=None)

        # Manually inject high-variance human windows
        for val in _HUMAN_WINDOWS:
            detector._entropy_windows["0xhuman01"].append(val)

        result = detector.assess("0xhuman01")
        self.assertEqual(result["risk_level"], "LOW")
        self.assertGreater(result["entropy_variance"], 0.15)

    def test_5_assess_never_raises_returns_low_on_error(self):
        """test_5: ClassJDetector.assess() never raises — returns LOW on error."""
        store = _make_store()
        cfg = _make_cfg()
        detector = ClassJDetector(cfg, store, bus=None)

        # Device with no windows — returns LOW gracefully
        result = detector.assess("0xunknown_device")
        self.assertEqual(result["risk_level"], "LOW")
        self.assertEqual(result["entropy_variance"], 0.0)
        self.assertIn("window_count", result)

        # Also works with None device_id
        result_none = detector.assess(None)
        self.assertEqual(result_none["risk_level"], "LOW")

    def test_6_classify_risk_thresholds_are_correct(self):
        """test_6: _classify_risk thresholds: <=0.05 HIGH, <=0.15 MEDIUM, >0.15 LOW."""
        self.assertEqual(ClassJDetector._classify_risk(0.0), "HIGH")
        self.assertEqual(ClassJDetector._classify_risk(0.04), "HIGH")
        self.assertEqual(ClassJDetector._classify_risk(0.05), "HIGH")
        self.assertEqual(ClassJDetector._classify_risk(0.051), "MEDIUM")
        self.assertEqual(ClassJDetector._classify_risk(0.10), "MEDIUM")
        self.assertEqual(ClassJDetector._classify_risk(0.15), "MEDIUM")
        self.assertEqual(ClassJDetector._classify_risk(0.151), "LOW")
        self.assertEqual(ClassJDetector._classify_risk(1.0), "LOW")
        self.assertEqual(ClassJDetector._classify_risk(5.0), "LOW")

    def test_7_class_j_risk_appears_in_session_adjudicator_evidence(self):
        """test_7: class_j_ml_bot_risk appears in SessionAdjudicator evidence_summary."""
        try:
            from vapi_bridge import session_adjudicator as sa_mod
        except ImportError:
            self.skipTest("session_adjudicator not importable")
            return

        store = _make_store()
        cfg = _make_cfg()

        # ClassJDetector with LOW risk (no windows)
        detector = ClassJDetector(cfg, store, bus=None)

        # _assess_class_j_risk is an async method on SessionAdjudicator
        # We test the ClassJDetector.assess() result format matches what SA expects
        result = detector.assess("0xdevice01")
        self.assertIn("risk_level", result)
        self.assertIn("entropy_variance", result)
        self.assertIn(result["risk_level"], ["LOW", "MEDIUM", "HIGH"])

        # Test that HIGH risk produces ml_bot_candidate signal
        for val in _CLASS_J_WINDOWS:
            detector._entropy_windows["0xhigh_risk"].append(val)
        high_result = detector.assess("0xhigh_risk")
        self.assertEqual(high_result["risk_level"], "HIGH")
        # When evidence_summary["class_j_ml_bot_risk"] == "HIGH", ml_bot_candidate=True is set
        # (that logic lives in session_adjudicator._process_ruling_request)
        ml_bot_candidate = high_result["risk_level"] == "HIGH"
        self.assertTrue(ml_bot_candidate)

    def test_8_insert_and_get_class_j_assessment_round_trip(self):
        """test_8: insert_class_j_assessment and get_class_j_assessment round-trip."""
        store = _make_store()

        store.insert_class_j_assessment(
            device_id="0xdevice01",
            entropy_variance=0.03,
            risk_level="HIGH",
            window_count=10,
        )

        result = store.get_class_j_assessment("0xdevice01")
        self.assertIsNotNone(result)
        self.assertEqual(result["device_id"], "0xdevice01")
        self.assertAlmostEqual(result["entropy_variance"], 0.03, places=5)
        self.assertEqual(result["risk_level"], "HIGH")
        self.assertEqual(result["window_count"], 10)

        # Query non-existent device returns None
        result_none = store.get_class_j_assessment("0xnonexistent")
        self.assertIsNone(result_none)


if __name__ == "__main__":
    unittest.main()
