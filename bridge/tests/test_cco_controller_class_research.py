"""CCO Phase G — controller-class research scaffold tests."""
import unittest

from vapi_bridge.cco_controller_class_research import (
    assemble_controller_class_research,
    resolve_controller_class_tier,
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


if __name__ == "__main__":
    unittest.main()
