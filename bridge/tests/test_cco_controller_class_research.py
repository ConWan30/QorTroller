"""CCO Phase G — controller-class research scaffold tests."""
import unittest

from vapi_bridge.cco_controller_class_research import (
    PHASE_G_TARGET_N,
    assemble_controller_class_research,
    resolve_controller_class_tier,
    resolve_corpus_measurement_grade,
)


class TestControllerClassResearch(unittest.TestCase):

    def test_t1_tier_mapping_edge(self):
        self.assertEqual(
            resolve_controller_class_tier("sony_dualshock_edge_v1"),
            "PREMIUM_EDGE",
        )

    def test_t2_tier_mapping_mid(self):
        self.assertEqual(
            resolve_controller_class_tier("sony_dualsense_v1"),
            "MID_TIER",
        )

    def test_t3_tier_mapping_minimal(self):
        self.assertEqual(
            resolve_controller_class_tier("hori_fighting_commander_ps5_v1"),
            "MINIMAL_PAD",
        )

    def test_t4_unknown_profile_conservative_minimal(self):
        self.assertEqual(
            resolve_controller_class_tier("generic_unknown_v1"),
            "MINIMAL_PAD",
        )

    def test_t5_disabled_surface(self):
        out = assemble_controller_class_research(enabled=False)
        self.assertFalse(out["enabled"])
        self.assertEqual(out["grade"], "DISABLED")

    def test_t6_edge_partial_grade(self):
        out = assemble_controller_class_research(
            enabled=True,
            profile_id="sony_dualshock_edge_v1",
            characterization_status="PARTIAL_EDGE_ONLY",
        )
        self.assertTrue(out["enabled"])
        self.assertEqual(out["controller_class_tier"], "PREMIUM_EDGE")
        self.assertEqual(out["grade"], "PARTIAL")
        self.assertEqual(out["partner_claim_ceiling"], "P-T3")
        self.assertIn("Empirical Unknown #1", out["measurement_gates_pending"][0])

    def test_t7_mid_tier_unvalidated(self):
        out = assemble_controller_class_research(
            enabled=True,
            profile_id="scuf_reflex_pro_v1",
            characterization_status="UNCHARACTERIZED",
        )
        self.assertEqual(out["grade"], "UNVALIDATED")
        self.assertEqual(out["partner_claim_ceiling"], "P-T1")

    def test_t8_mid_tier_promotes_partial_at_n50(self):
        grade = resolve_corpus_measurement_grade("MID_TIER", PHASE_G_TARGET_N)
        self.assertEqual(grade, "PARTIAL")
        self.assertEqual(
            resolve_corpus_measurement_grade("MID_TIER", PHASE_G_TARGET_N - 1),
            "UNVALIDATED",
        )

    def test_t9_premium_edge_stays_partial_baseline(self):
        self.assertEqual(
            resolve_corpus_measurement_grade("PREMIUM_EDGE", 0),
            "PARTIAL",
        )
        self.assertEqual(
            resolve_corpus_measurement_grade("PREMIUM_EDGE", PHASE_G_TARGET_N),
            "PARTIAL",
        )

    def test_t10_assemble_includes_corpus_fields_when_count_provided(self):
        out = assemble_controller_class_research(
            enabled=True,
            profile_id="scuf_reflex_pro_v1",
            tier_probe_count=PHASE_G_TARGET_N,
        )
        self.assertEqual(out["grade"], "PARTIAL")
        self.assertEqual(out["corpus_n"], PHASE_G_TARGET_N)
        self.assertEqual(out["corpus_target_n"], PHASE_G_TARGET_N)
        self.assertTrue(out["corpus_gate_reached"])
        self.assertNotEqual(out["grade"], "VALIDATED")


    def test_t11_parse_deferred_tiers(self):
        from vapi_bridge.cco_controller_class_research import (
            enrich_phase_g_progress,
            parse_phase_g_deferred_tiers,
        )

        self.assertEqual(
            parse_phase_g_deferred_tiers("MINIMAL_PAD, mid_tier "),
            frozenset({"MINIMAL_PAD", "MID_TIER"}),
        )
        progress = {
            "by_tier": {
                "MINIMAL_PAD": {"probe_count": 0, "gate_reached": False, "profiles": {}},
                "MID_TIER": {"probe_count": 50, "gate_reached": True, "profiles": {}},
                "PREMIUM_EDGE": {"probe_count": 0, "gate_reached": False, "profiles": {}},
            }
        }
        out = enrich_phase_g_progress(
            progress,
            deferred_tiers=frozenset({"MINIMAL_PAD"}),
        )
        self.assertEqual(out["by_tier"]["MINIMAL_PAD"]["measurement_status"], "deferred")
        self.assertEqual(out["by_tier"]["MID_TIER"]["measurement_status"], "reached")
        self.assertEqual(out["by_tier"]["MID_TIER"]["measurement_grade"], "PARTIAL")

    def test_t12_validated_tiers_operator_attestation(self):
        from vapi_bridge.cco_controller_class_research import (
            enrich_phase_g_progress,
            parse_phase_g_validated_tiers,
            resolve_tier_measurement_grade,
        )

        self.assertEqual(
            parse_phase_g_validated_tiers("MID_TIER, premium_edge"),
            frozenset({"MID_TIER", "PREMIUM_EDGE"}),
        )
        self.assertEqual(
            resolve_tier_measurement_grade(
                "MID_TIER",
                130,
                validated_tiers=frozenset({"MID_TIER"}),
            ),
            "VALIDATED",
        )
        progress = {
            "by_tier": {
                "MINIMAL_PAD": {"probe_count": 0, "gate_reached": False, "profiles": {}},
                "MID_TIER": {"probe_count": 130, "gate_reached": True, "profiles": {}},
                "PREMIUM_EDGE": {"probe_count": 210, "gate_reached": True, "profiles": {}},
            }
        }
        out = enrich_phase_g_progress(
            progress,
            deferred_tiers=frozenset({"MINIMAL_PAD"}),
            validated_tiers=frozenset({"MID_TIER", "PREMIUM_EDGE"}),
        )
        self.assertEqual(out["by_tier"]["MID_TIER"]["measurement_grade"], "VALIDATED")
        self.assertTrue(out["by_tier"]["MID_TIER"]["operator_validated"])
        self.assertEqual(out["validated_tiers"], ["MID_TIER", "PREMIUM_EDGE"])


if __name__ == "__main__":
    unittest.main()
