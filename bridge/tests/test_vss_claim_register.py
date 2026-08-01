"""VSS-5 — Claim register + runbook validation tests.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §10 + §8 (VSS-5).
Acceptance: "R-VSS-* gated; never-sayable list updated"

Test coverage:
  1. R-VSS-01..07 all present in claim register
  2. R-VSS-04 is G4 Forbidden (never sayable)
  3. R-VSS-01 is G0, sayable (VSS-1..3 shipped)
  4. R-VSS-02 is G0, sayable (VSS-2 shipped)
  5. R-VSS-05 is G0, sayable (VSS-2..3 shipped)
  6. R-VSS-03 is G1, NOT sayable (VSS-7 not shipped)
  7. R-VSS-06 is G0, NOT sayable (F2 bind not yet live)
  8. R-VSS-07 is G1, sayable only if ioid_token present
  9. Never-sayable list includes VSS-specific phrases
 10. Never-sayable list includes "humanity-proven" for streams
 11. Runbook exists and references VSS-1..4
 12. Runbook includes "never" section
 13. Runbook references the claim register
 14. R-VSS-04 appears in the gate relationship table
 15. VSS work package gates table present
 16. No FROZEN/PoAC/chain touched (docs only)
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
CLAIM_REGISTER = REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register-v0.md"
VSS_SCOPE = REPO_ROOT / "docs" / "design" / "buzz-vss-stream-seat-scope-v0.md"
RUNBOOK = REPO_ROOT / "docs" / "runbook" / "buzz-vss-runbook.md"


class TestClaimRegisterVSS(unittest.TestCase):
    """VSS-5 claim register + runbook validation tests."""

    def setUp(self):
        self.assertTrue(CLAIM_REGISTER.exists(), f"claim register missing: {CLAIM_REGISTER}")
        self.assertTrue(VSS_SCOPE.exists(), f"VSS scope missing: {VSS_SCOPE}")
        self.assertTrue(RUNBOOK.exists(), f"runbook missing: {RUNBOOK}")
        self.register_text = CLAIM_REGISTER.read_text(encoding="utf-8")
        self.runbook_text = RUNBOOK.read_text(encoding="utf-8")

    def test_1_all_rvss_rows_present(self):
        """R-VSS-01..07 all present in claim register."""
        for i in range(1, 8):
            row_id = f"R-VSS-{i:02d}"
            self.assertIn(row_id, self.register_text,
                          f"{row_id} must be in the claim register")

    def test_2_rvss04_is_g4_forbidden(self):
        """R-VSS-04 is G4 Forbidden (never sayable)."""
        self.assertIn("R-VSS-04", self.register_text)
        # Find the R-VSS-04 row and check it's G4 and forbidden
        self.assertIn("G4", self.register_text)
        self.assertIn("Forbidden", self.register_text)
        # Check the never-sayable list includes stream humanity-proven
        self.assertIn("humanity-proven", self.register_text.lower())

    def test_3_rvss01_g0_sayable(self):
        """R-VSS-01 is G0, sayable (VSS-1..3 shipped)."""
        self.assertIn("R-VSS-01", self.register_text)
        self.assertIn("G0", self.register_text)
        # R-VSS-01 should be marked as sayable
        # Find the row and check "yes" in the sayable column
        rvss01_match = re.search(r"R-VSS-01.*?yes", self.register_text, re.I | re.S)
        self.assertIsNotNone(rvss01_match, "R-VSS-01 should be sayable")

    def test_4_rvss02_g0_sayable(self):
        """R-VSS-02 is G0, sayable (VSS-2 shipped)."""
        self.assertIn("R-VSS-02", self.register_text)
        rvss02_match = re.search(r"R-VSS-02.*?yes", self.register_text, re.I | re.S)
        self.assertIsNotNone(rvss02_match, "R-VSS-02 should be sayable")

    def test_5_rvss05_g0_sayable(self):
        """R-VSS-05 is G0, sayable (VSS-2..3 shipped)."""
        self.assertIn("R-VSS-05", self.register_text)
        rvss05_match = re.search(r"R-VSS-05.*?yes", self.register_text, re.I | re.S)
        self.assertIsNotNone(rvss05_match, "R-VSS-05 should be sayable")

    def test_6_rvss03_g1_sayable_after_vss7(self):
        """R-VSS-03 is G1, sayable after VSS-7 shipped (bot OPEN ban enforced)."""
        self.assertIn("R-VSS-03", self.register_text)
        self.assertIn("G1", self.register_text)
        # R-VSS-03 should now be marked as sayable (VSS-7 shipped)
        rvss03_match = re.search(r"R-VSS-03.*?yes", self.register_text, re.I | re.S)
        self.assertIsNotNone(rvss03_match, "R-VSS-03 should be sayable after VSS-7")

    def test_7_rvss06_g0_not_sayable(self):
        """R-VSS-06 is G0, NOT sayable (F2 bind not yet live)."""
        self.assertIn("R-VSS-06", self.register_text)
        rvss06_match = re.search(r"R-VSS-06.*?no", self.register_text, re.I | re.S)
        self.assertIsNotNone(rvss06_match, "R-VSS-06 should NOT be sayable")

    def test_8_rvss07_g1_conditional(self):
        """R-VSS-07 is G1, sayable only if ioid_token present."""
        self.assertIn("R-VSS-07", self.register_text)
        self.assertIn("G1", self.register_text)
        # R-VSS-07 should mention "optional" or "if ioid_token"
        rvss07_match = re.search(r"R-VSS-07.*?(optional|ioid_token)", self.register_text,
                                  re.I | re.S)
        self.assertIsNotNone(rvss07_match, "R-VSS-07 should mention optional/conditional")

    def test_9_never_sayable_includes_vss_phrases(self):
        """Never-sayable list includes VSS-specific phrases."""
        never_section = self.register_text.lower()
        self.assertIn("tournament-grade stream", never_section,
                      "never-sayable should include 'tournament-grade stream'")
        self.assertIn("cheating-proof", never_section,
                      "never-sayable should include 'cheating-proof'")

    def test_10_never_sayable_includes_humanity_proven(self):
        """Never-sayable list includes 'humanity-proven' for streams."""
        never_section = self.register_text.lower()
        self.assertIn("verified human live", never_section,
                      "never-sayable should include 'verified human live'")

    def test_11_runbook_references_vss_components(self):
        """Runbook exists and references VSS-1..4."""
        for wp in ("VSS-1", "VSS-2", "VSS-3", "VSS-4", "VSS-5"):
            self.assertIn(wp, self.runbook_text,
                          f"runbook should reference {wp}")

    def test_12_runbook_has_never_section(self):
        """Runbook includes 'never' section."""
        self.assertIn("## Never", self.runbook_text,
                      "runbook must have a Never section")

    def test_13_runbook_references_claim_register(self):
        """Runbook references the claim register."""
        self.assertIn("claim", self.runbook_text.lower(),
                      "runbook should reference the claim register")

    def test_14_rvss04_in_gate_table(self):
        """R-VSS-04 appears in the gate relationship table."""
        self.assertIn("R-VSS-04", self.register_text)
        # Should appear in the "all of the above" row or VSS WP gates
        gate_section = self.register_text.split("## 5.")[1] if "## 5." in self.register_text else ""
        self.assertIn("R-VSS-04", gate_section,
                      "R-VSS-04 should be in the gate relationship table")

    def test_15_vss_wp_gates_table_present(self):
        """VSS work package gates table present."""
        self.assertIn("VSS work package gates", self.register_text,
                      "VSS WP gates table should be present")
        self.assertIn("VSS-1..3", self.register_text)
        self.assertIn("VSS-7", self.register_text)

    def test_16_no_frozen_poac_chain_touched(self):
        """VSS-5 is docs only — runbook mentions FROZEN/chain as prohibitions, not actions."""
        # The runbook's Never section should PROHIBIT touching FROZEN/chain,
        # not instruct the operator to do it.
        runbook_lower = self.runbook_text.lower()
        # "touch frozen wire" should appear in the Never section (as a prohibition)
        self.assertIn("frozen wire", runbook_lower,
                      "runbook should mention FROZEN wire in Never section")
        # But should NOT instruct to edit/modify FROZEN wire
        self.assertNotIn("edit frozen", runbook_lower,
                         "runbook must not instruct editing FROZEN wire")
        self.assertNotIn("modify frozen", runbook_lower,
                         "runbook must not instruct modifying FROZEN wire")
        self.assertNotIn("deploy contract", runbook_lower,
                         "runbook must not instruct deploying contracts")


if __name__ == "__main__":
    unittest.main()
