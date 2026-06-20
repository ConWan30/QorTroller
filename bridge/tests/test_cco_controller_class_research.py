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


if __name__ == "__main__":
    unittest.main()
