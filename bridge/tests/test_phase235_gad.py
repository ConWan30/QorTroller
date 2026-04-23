"""Phase 235-GAD — Gameplay Activity Discrimination: Phase 3 Implementation Tests

Gate: ruling_validation_log.gameplay_context drives consecutive_clean gate.
  ACTIVE_GAMEPLAY  → counts (trigger activity detected in 20-record evidence window)
  MENU_DETECTED    → breaks streak (zero trigger activity)
  NULL             → pass-through (pre-GAD row, no activity data — benefit of doubt)

Operator override: POST /operator/override-gameplay-context sets ACTIVE_GAMEPLAY and
  logs to gameplay_classification_disagreements for post-hoc analysis.

Tests:
  T235-GAD-1: ACTIVE_GAMEPLAY row counts toward consecutive_clean
  T235-GAD-2: MENU_DETECTED row breaks streak
  T235-GAD-3: NULL gameplay_context passes through (fail-open for unknown)
  T235-GAD-4: override_gameplay_context() flips MENU_DETECTED → ACTIVE_GAMEPLAY → counts
"""

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


def _make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    td = tmp_dir or tempfile.mkdtemp()
    return Store(str(Path(td) / "gad_phase3.db"))


def _insert_row(store, device_id, gameplay_context, divergence=0):
    """Insert a fully-eligible validation row with the given gameplay_context."""
    ruling_id = store.insert_agent_ruling(
        device_id=device_id,
        verdict="FLAG",
        confidence=0.05,
        reasoning="test",
        evidence_json="{}",
        commitment_hash="ab" * 32,
    )
    return store.insert_validation_record(
        ruling_id=ruling_id,
        device_id=device_id,
        llm_verdict="FLAG",
        fallback_verdict="FLAG",
        llm_confidence=0.05,
        fallback_confidence=0.05,
        divergence=divergence,
        pcc_state="NOMINAL",
        pcc_host_state="EXCLUSIVE_USB",
        gameplay_context=gameplay_context,
    )


class TestGameplayContextGate(unittest.TestCase):

    def test_1_active_gameplay_counts(self):
        """T235-GAD-1: ACTIVE_GAMEPLAY gameplay_context counts toward consecutive_clean."""
        store = _make_store()
        store.upsert_device("dev_gad1", "00" * 32)
        _insert_row(store, "dev_gad1", "ACTIVE_GAMEPLAY")
        summary = store.get_validation_summary(gate_n=100)
        self.assertEqual(summary["consecutive_clean"], 1,
                         "ACTIVE_GAMEPLAY must count toward consecutive_clean")

    def test_2_menu_detected_breaks_streak(self):
        """T235-GAD-2: MENU_DETECTED breaks the consecutive_clean streak."""
        store = _make_store()
        store.upsert_device("dev_gad2", "00" * 32)
        # First row: ACTIVE_GAMEPLAY (counts)
        _insert_row(store, "dev_gad2", "ACTIVE_GAMEPLAY")
        # Second row: MENU_DETECTED (breaks streak)
        _insert_row(store, "dev_gad2", "MENU_DETECTED")
        summary = store.get_validation_summary(gate_n=100)
        self.assertEqual(
            summary["consecutive_clean"], 0,
            "MENU_DETECTED must break streak — consecutive_clean resets to 0"
        )

    def test_3_null_gameplay_context_passes_through(self):
        """T235-GAD-3: NULL gameplay_context passes through (fail-open for pre-GAD rows).

        Pre-GAD rows lack trigger_active data. They should not be blocked — only
        explicit MENU_DETECTED evidence (confirmed non-gameplay) breaks the streak.
        """
        store = _make_store()
        store.upsert_device("dev_gad3", "00" * 32)
        _insert_row(store, "dev_gad3", None)  # NULL = no activity data
        summary = store.get_validation_summary(gate_n=100)
        self.assertEqual(
            summary["consecutive_clean"], 1,
            "NULL gameplay_context must pass through (benefit of doubt for pre-GAD rows)"
        )

    def test_4_operator_override_flips_menu_to_active(self):
        """T235-GAD-4: override_gameplay_context() changes MENU_DETECTED to ACTIVE_GAMEPLAY.

        After override, the row counts toward consecutive_clean.
        Logs to gameplay_classification_disagreements for audit trail.
        """
        store = _make_store()
        store.upsert_device("dev_gad4", "00" * 32)
        row_id = _insert_row(store, "dev_gad4", "MENU_DETECTED")

        # Before override: streak broken
        summary_before = store.get_validation_summary(gate_n=100)
        self.assertEqual(summary_before["consecutive_clean"], 0,
                         "MENU_DETECTED must break streak before override")

        # Apply override
        store.override_gameplay_context(
            row_id, "Stick fault during competitive match — false MENU_DETECTED", device_id="dev_gad4"
        )

        # After override: row now ACTIVE_GAMEPLAY → counts
        summary_after = store.get_validation_summary(gate_n=100)
        self.assertEqual(
            summary_after["consecutive_clean"], 1,
            "After override to ACTIVE_GAMEPLAY the row must count toward consecutive_clean"
        )


if __name__ == "__main__":
    unittest.main()
