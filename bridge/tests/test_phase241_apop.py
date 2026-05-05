"""Phase 241-APOP — Active Play Occupancy Proof tests."""

import sys
import tempfile
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _records(n=30, trigger_active=0, humanity=0.62):
    return [
        {
            "record_hash": f"{i:064x}",
            "trigger_active": trigger_active,
            "pitl_humanity_prob": humanity,
            "pitl_l5_rhythm_humanity": 0.70,
        }
        for i in range(n)
    ]


def _checkpoint(frames):
    return [{"record_hash": "aa" * 32, "frames": frames, "frame_count": len(frames)}]


def _active_frames(n=60):
    return [
        {
            "left_stick_x": 220 if i % 2 == 0 else 36,
            "left_stick_y": 128,
            "right_stick_x": 128,
            "right_stick_y": 128,
            "gyro_x": 0.8,
            "gyro_y": 1.2,
            "gyro_z": 5.0,
            "accel_x": 0.02 * (i % 3),
            "accel_y": 0.01,
            "accel_z": 1.0,
            "l2_trigger": 0,
            "r2_trigger": 0,
        }
        for i in range(n)
    ]


def _playcall_frames(n=60):
    frames = []
    for i in range(n):
        frames.append({
            "left_stick_x": 128,
            "left_stick_y": 128,
            "right_stick_x": 128,
            "right_stick_y": 128,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
            "l2_trigger": 0,
            "r2_trigger": 0,
            "buttons_cross": int(i % 4 == 0),
            "buttons_square": int(i % 4 == 1),
            "buttons_dpad_up": int(i % 4 == 2),
            "buttons_dpad_right": int(i % 4 == 3),
        })
    return frames


def _trigger_hold_frames(n=60):
    return [
        {
            "left_stick_x": 128,
            "left_stick_y": 128,
            "right_stick_x": 128,
            "right_stick_y": 128,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
            "l2_trigger": 0,
            "r2_trigger": 220,
        }
        for _ in range(n)
    ]


def _idle_frames(n=60):
    return [
        {
            "left_stick_x": 128,
            "left_stick_y": 128,
            "right_stick_x": 128,
            "right_stick_y": 128,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 1.0,
            "l2_trigger": 0,
            "r2_trigger": 0,
        }
        for _ in range(n)
    ]


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "phase241_apop.db"))


def _insert_validation(store, context, idx=1):
    store.upsert_device("dev_apop", "00" * 32)
    ruling_id = store.insert_agent_ruling(
        device_id="dev_apop",
        verdict="FLAG",
        confidence=0.05,
        reasoning="phase241",
        evidence_json='{"trigger_active_fraction":0.0}',
        commitment_hash=f"{idx:064x}",
    )
    validation_id = store.insert_validation_record(
        ruling_id=ruling_id,
        device_id="dev_apop",
        llm_verdict="FLAG",
        fallback_verdict="FLAG",
        llm_confidence=0.05,
        fallback_confidence=0.05,
        divergence=0,
        pcc_state="NOMINAL",
        pcc_host_state="EXCLUSIVE_USB",
        gameplay_context=context,
    )
    return ruling_id, validation_id


class TestActivePlayOccupancyClassifier(unittest.TestCase):
    def test_active_stick_plus_imu_is_match_play(self):
        from vapi_bridge.active_play_occupancy import (
            ACTIVE_MATCH_PLAY,
            classify_active_play_occupancy,
        )
        result = classify_active_play_occupancy(_records(), _checkpoint(_active_frames()))
        self.assertEqual(result.state, ACTIVE_MATCH_PLAY)
        self.assertGreater(result.score, 0.40)

    def test_play_call_cadence_is_competitive_control(self):
        from vapi_bridge.active_play_occupancy import (
            COMPETITIVE_CONTROL,
            classify_active_play_occupancy,
        )
        result = classify_active_play_occupancy(_records(), _checkpoint(_playcall_frames()))
        self.assertEqual(result.state, COMPETITIVE_CONTROL)

    def test_sustained_r2_hold_counts_without_trigger_onset(self):
        from vapi_bridge.active_play_occupancy import (
            COMPETITIVE_CONTROL,
            classify_active_play_occupancy,
        )
        records = _records(trigger_active=0)
        result = classify_active_play_occupancy(records, _checkpoint(_trigger_hold_frames()))
        self.assertEqual(result.state, COMPETITIVE_CONTROL)

    def test_idle_stream_is_non_competitive_menu(self):
        from vapi_bridge.active_play_occupancy import (
            NON_COMPETITIVE_MENU,
            classify_active_play_occupancy,
        )
        result = classify_active_play_occupancy(_records(humanity=0.35), _checkpoint(_idle_frames()))
        self.assertEqual(result.state, NON_COMPETITIVE_MENU)

    def test_missing_evidence_is_unknown_low_evidence(self):
        from vapi_bridge.active_play_occupancy import (
            UNKNOWN_LOW_EVIDENCE,
            classify_active_play_occupancy,
        )
        result = classify_active_play_occupancy([], [])
        self.assertEqual(result.state, UNKNOWN_LOW_EVIDENCE)


class TestActivePlayOccupancyGate(unittest.TestCase):
    def test_shadow_mode_does_not_rescue_legacy_menu(self):
        from vapi_bridge.active_play_occupancy import ACTIVE_MATCH_PLAY
        store = _make_store()
        ruling_id, validation_id = _insert_validation(store, "MENU_DETECTED", 1)
        store.insert_active_play_occupancy_log(
            validation_id, ruling_id, "dev_apop", ACTIVE_MATCH_PLAY, 0.7, 0.8, "{}", "hybrid"
        )
        self.assertEqual(store.get_validation_summary(gate_n=100)["consecutive_clean"], 0)

    def test_hybrid_mode_rescues_competitive_false_menu(self):
        from vapi_bridge.active_play_occupancy import ACTIVE_MATCH_PLAY
        store = _make_store()
        ruling_id, validation_id = _insert_validation(store, "MENU_DETECTED", 2)
        store.insert_active_play_occupancy_log(
            validation_id, ruling_id, "dev_apop", ACTIVE_MATCH_PLAY, 0.7, 0.8, "{}", "hybrid"
        )
        summary = store.get_validation_summary(gate_n=100, active_play_gate_mode="hybrid")
        self.assertEqual(summary["consecutive_clean"], 1)

    def test_hybrid_mode_blocks_confident_non_competitive_menu(self):
        from vapi_bridge.active_play_occupancy import NON_COMPETITIVE_MENU
        store = _make_store()
        ruling_id, validation_id = _insert_validation(store, "ACTIVE_GAMEPLAY", 3)
        store.insert_active_play_occupancy_log(
            validation_id, ruling_id, "dev_apop", NON_COMPETITIVE_MENU, 0.05, 0.8, "{}", "hybrid"
        )
        summary = store.get_validation_summary(gate_n=100, active_play_gate_mode="hybrid")
        self.assertEqual(summary["consecutive_clean"], 0)

    def test_unknown_low_evidence_falls_back_to_legacy_in_hybrid(self):
        from vapi_bridge.active_play_occupancy import UNKNOWN_LOW_EVIDENCE
        store = _make_store()
        ruling_id, validation_id = _insert_validation(store, "ACTIVE_GAMEPLAY", 4)
        store.insert_active_play_occupancy_log(
            validation_id, ruling_id, "dev_apop", UNKNOWN_LOW_EVIDENCE, 0.0, 0.2, "{}", "hybrid"
        )
        summary = store.get_validation_summary(gate_n=100, active_play_gate_mode="hybrid")
        self.assertEqual(summary["consecutive_clean"], 1)

    def test_strict_mode_fails_closed_on_unknown(self):
        from vapi_bridge.active_play_occupancy import UNKNOWN_LOW_EVIDENCE
        store = _make_store()
        ruling_id, validation_id = _insert_validation(store, "ACTIVE_GAMEPLAY", 5)
        store.insert_active_play_occupancy_log(
            validation_id, ruling_id, "dev_apop", UNKNOWN_LOW_EVIDENCE, 0.0, 0.2, "{}", "strict"
        )
        summary = store.get_validation_summary(gate_n=100, active_play_gate_mode="strict")
        self.assertEqual(summary["consecutive_clean"], 0)


if __name__ == "__main__":
    unittest.main()
