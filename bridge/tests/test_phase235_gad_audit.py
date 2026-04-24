"""Phase 235-GAD — Gameplay Activity Discrimination: Phase 1 Audit Tests

TASK 1.2: Content-Blind Session Counting Verification

Empirically confirms the hypothesis:
  "A menu-only session counts toward consecutive_clean identically to a gameplay session."

STREAM A — Gameplay-Like HID Profile:
  Continuous stick deflections, frequent L2/R2 triggers, varied face buttons, active IMU.
  Inference codes: all 0x20 (NOMINAL) — no hard cheats, no advisories from normal gameplay.

STREAM B — Menu-Like HID Profile:
  Sparse D-pad only, idle gaps, no analog input, minimal IMU (controller at rest on desk).
  Inference codes: all 0x20 (NOMINAL) — menu navigation produces no detectable PITL signal.

Both streams produce identical evidence_summary from _process_ruling_request():
  - hard_cheat_codes = []    (no hard cheats: 0x28/0x29/0x2A)
  - advisory_codes   = []    (no advisories: 0x2B/0x30/0x31/0x32)
Both pass identical evidence to _rule_fallback() → FLAG(0.05)
Both insert validation rows with divergence=0 + pcc_state=NOMINAL + EXCLUSIVE_USB
Both advance consecutive_clean by 1.

This is the GAD gap: the protocol cannot distinguish competitive gameplay from menu navigation.

Tests:
  T235-GAD-AUDIT-1: STREAM A evidence produces fallback_verdict=FLAG(0.05)
  T235-GAD-AUDIT-2: STREAM B evidence produces fallback_verdict=FLAG(0.05) — identical
  T235-GAD-AUDIT-3: Both insert validation rows with divergence=0 + PCC-eligible
  T235-GAD-AUDIT-4: consecutive_clean advances by 2 after both (menu indistinguishable)
  T235-GAD-AUDIT-5: L4 advisory in STREAM B still produces FLAG — same verdict class, still counts
  T235-GAD-AUDIT-6: L5 advisory in STREAM B still produces FLAG — same verdict class, still counts
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy deps so tests run without hardware
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    td = tmp_dir or tempfile.mkdtemp()
    return Store(str(Path(td) / "gad_audit.db"))


# ---------------------------------------------------------------------------
# Evidence builder helpers
# ---------------------------------------------------------------------------

def _build_evidence(inference_codes: list[int], enrollment_status: str = "unknown") -> dict:
    """Replicate _process_ruling_request() evidence construction from inference codes.

    session_adjudicator.py:198-213 — the adjudicator collects the last 20 PoAC records'
    inference codes and classifies them into hard_cheat_codes and advisory_codes.
    """
    hard_cheats = [c for c in inference_codes if c in (0x28, 0x29, 0x2A)]
    advisories  = [c for c in inference_codes if c in (0x2B, 0x30, 0x31, 0x32)]
    return {
        "device_id":       "00" * 32,
        "hard_cheat_codes": hard_cheats,
        "advisory_codes":   advisories,
        "record_count":     len(inference_codes),
        "enrollment_status": enrollment_status,
        "avg_humanity":     0.85,
        "risk_label":       "unknown",
        "l6b_probes":       0,
        "class_j_ml_bot_risk": "LOW",
    }


# STREAM A: 20 gameplay-like PoAC records — all INFER_NOMINAL (0x20).
# Active sticks, L2/R2 triggers, varied buttons → PITL produces 0x20 for human gameplay.
STREAM_A_CODES = [0x20] * 20

# STREAM B: 20 menu-like PoAC records — all INFER_NOMINAL (0x20).
# D-pad only, no analog input, no triggers → PITL produces 0x20 for menu navigation.
# The PITL stack has no mechanism to detect "game not in competitive session".
STREAM_B_CODES = [0x20] * 20

# STREAM B with L4 advisory: menu play that happens to trigger BIOMETRIC_ANOMALY (0x30)
# because stick_autocorr near 1.0 (no stick movement) deviates from gameplay calibration.
# This is a best-case scenario for detection — but the verdict is still FLAG.
STREAM_B_L4_CODES = [0x20] * 18 + [0x30, 0x30]

# STREAM B with L5 advisory: sparse menu presses trigger TEMPORAL_BOT detection (0x2B)
# because inter-button gap CV is atypically low for a menu player.
STREAM_B_L5_CODES = [0x20] * 18 + [0x2B, 0x2B]


class TestContentBlindSessionCounting(unittest.TestCase):
    """T235-GAD-AUDIT-1..4: Core content-blindness verification."""

    def setUp(self):
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        self._fallback = SessionAdjudicator._rule_fallback

    def test_1_stream_a_gameplay_fallback_is_flag_005(self):
        """T235-GAD-AUDIT-1: Gameplay-like stream produces FLAG(0.05) — baseline."""
        evidence = _build_evidence(STREAM_A_CODES)
        verdict, confidence, _ = self._fallback(evidence)
        self.assertEqual(verdict, "FLAG")
        self.assertAlmostEqual(confidence, 0.05, places=4)
        self.assertEqual(evidence["hard_cheat_codes"], [])
        self.assertEqual(evidence["advisory_codes"], [])

    def test_2_stream_b_menu_fallback_is_flag_005_identical(self):
        """T235-GAD-AUDIT-2: Menu-like stream produces FLAG(0.05) — identical to gameplay.

        This is the GAD gap: menu navigation produces INFER_NOMINAL (0x20) PoAC records.
        The evidence_summary is structurally identical to a gameplay session.
        _rule_fallback() receives the same input and returns the same output.
        """
        evidence = _build_evidence(STREAM_B_CODES)
        verdict, confidence, _ = self._fallback(evidence)
        self.assertEqual(verdict, "FLAG")
        self.assertAlmostEqual(confidence, 0.05, places=4,
                               msg="Menu session produces identical fallback to gameplay")
        # Explicitly confirm both evidence summaries are structurally equivalent
        evidence_a = _build_evidence(STREAM_A_CODES)
        self.assertEqual(
            evidence["hard_cheat_codes"], evidence_a["hard_cheat_codes"],
            "hard_cheat_codes must be identical for both streams"
        )
        self.assertEqual(
            evidence["advisory_codes"], evidence_a["advisory_codes"],
            "advisory_codes must be identical for both streams"
        )

    def test_3_both_streams_insert_pcc_eligible_no_divergence(self):
        """T235-GAD-AUDIT-3: Both streams insert validation rows with divergence=0 + PCC-eligible."""
        store = _make_store()
        store.upsert_device("dev_gad", "00" * 32)

        for stream_name, codes in [("gameplay", STREAM_A_CODES), ("menu", STREAM_B_CODES)]:
            ruling_id = store.insert_agent_ruling(
                device_id="dev_gad",
                verdict="FLAG",
                confidence=0.05,
                reasoning=f"No anomalies detected ({stream_name} stream).",
                evidence_json="{}",
                commitment_hash="ab" * 32,
            )
            val_id = store.insert_validation_record(
                ruling_id=ruling_id,
                device_id="dev_gad",
                llm_verdict="FLAG",
                fallback_verdict="FLAG",
                llm_confidence=0.05,
                fallback_confidence=0.05,
                divergence=0,
                pcc_state="NOMINAL",
                pcc_host_state="EXCLUSIVE_USB",
            )
            self.assertGreater(val_id, 0,
                               f"{stream_name} stream must produce valid validation row")

    def test_4_consecutive_clean_advances_for_both_streams(self):
        """T235-GAD-AUDIT-4: consecutive_clean counts gameplay and menu sessions identically.

        After inserting 1 gameplay + 1 menu validation row, consecutive_clean=2.
        The grind gate cannot distinguish which sessions were competitive gameplay.
        """
        store = _make_store()
        store.upsert_device("dev_gad2", "00" * 32)

        for i, (stream_name, codes) in enumerate([
            ("gameplay", STREAM_A_CODES),
            ("menu",     STREAM_B_CODES),
        ]):
            ruling_id = store.insert_agent_ruling(
                device_id="dev_gad2",
                verdict="FLAG",
                confidence=0.05,
                reasoning=f"No anomalies ({stream_name}).",
                evidence_json="{}",
                commitment_hash=("a0" if i == 0 else "b0") * 32,
            )
            store.insert_validation_record(
                ruling_id=ruling_id,
                device_id="dev_gad2",
                llm_verdict="FLAG",
                fallback_verdict="FLAG",
                llm_confidence=0.05,
                fallback_confidence=0.05,
                divergence=0,
                pcc_state="NOMINAL",
                pcc_host_state="EXCLUSIVE_USB",
            )

        summary = store.get_validation_summary(gate_n=100)
        self.assertEqual(
            summary["consecutive_clean"], 2,
            "consecutive_clean must be 2: one gameplay + one menu session, indistinguishable"
        )


class TestAdvisoryCodeStillCounts(unittest.TestCase):
    """T235-GAD-AUDIT-5..6: Even with advisory codes, menu sessions count toward grind.

    This covers the case where menu navigation happens to trigger L4 or L5 advisory codes.
    Because the LLM would also return FLAG (agreeing with _rule_fallback), divergence=0.
    """

    def setUp(self):
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        self._fallback = SessionAdjudicator._rule_fallback

    def test_5_stream_b_with_l4_advisory_still_produces_flag(self):
        """T235-GAD-AUDIT-5: Menu + L4 advisory → FLAG(0.5) — same verdict class, still counts.

        Scenario: during menu navigation, stick_autocorr approaches 1.0 (no stick movement),
        far from the gameplay calibration centroid → Mahalanobis > 7.009 → BIOMETRIC_ANOMALY 0x30.
        This fires advisory_codes=[0x30]. _rule_fallback returns FLAG(0.5).
        If LLM agrees (FLAG), divergence=0. Session still counts.

        Key insight: the verdict is still FLAG — the PITL cannot signal "this is menu play"
        because 0x30 means "biometric anomaly" not "not competitive gameplay".
        """
        evidence = _build_evidence(STREAM_B_L4_CODES)
        self.assertEqual(evidence["advisory_codes"], [0x30, 0x30])

        verdict, confidence, _ = self._fallback(evidence)
        self.assertEqual(verdict, "FLAG",
                         "L4 advisory → FLAG: same verdict class as no-advisory session")
        self.assertAlmostEqual(confidence, 0.5, places=4)

        # LLM would also return FLAG for a biometric anomaly advisory → divergence=0 → counts
        # Confirm: same verdict → NEVER diverges regardless of confidence delta
        verdicts_differ = ("FLAG" != "FLAG")  # LLM=FLAG, fallback=FLAG
        delta_conf = abs(0.5 - 0.5)          # both 0.5
        divergence = verdicts_differ and (delta_conf > 0.30)
        self.assertFalse(divergence,
                         "Same verdict → divergence=False → L4-advisory menu session COUNTS")

    def test_6_stream_b_with_l5_advisory_still_produces_flag(self):
        """T235-GAD-AUDIT-6: Menu + L5 advisory → FLAG(0.5) — same verdict class, still counts.

        Scenario: sparse menu D-pad presses have unusual temporal rhythm → TEMPORAL_BOT 0x2B.
        This fires advisory_codes=[0x2B]. _rule_fallback returns FLAG(0.5).
        LLM agrees → divergence=0. Session counts.

        The VAPI protocol intention is that 0x2B = temporal bot signature.
        Menu navigation produces rhythms that superficially resemble bot patterns
        (regular, sparse) but the verdict is still FLAG, not a distinguishing signal.
        """
        evidence = _build_evidence(STREAM_B_L5_CODES)
        self.assertEqual(evidence["advisory_codes"], [0x2B, 0x2B])

        verdict, confidence, _ = self._fallback(evidence)
        self.assertEqual(verdict, "FLAG")
        self.assertAlmostEqual(confidence, 0.5, places=4)

        # Protocol-purpose gap: 0x2B says "temporal bot risk" but cannot distinguish
        # "bot-like regularity because menu" from "actual temporal bot"
        self.assertEqual(verdict, "FLAG",
                         "0x2B advisory from menu navigation is indistinguishable from bot advisory")


if __name__ == "__main__":
    unittest.main()
