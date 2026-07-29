"""
ioSwarm task-spec + node-emulator tests (Phases 109A/109B/109C/110).

Covers four frozen spec dataclasses and the deterministic node emulator:
  - VAPISwarmTaskSpec            (ioswarm_task_spec)
  - VHPRenewalSwarmTaskSpec      (ioswarm_renewal_spec)
  - VAPIAdjudicationSwarmTaskSpec(ioswarm_adjudication_spec)
  - VAPIVHPMintSwarmTaskSpec     (ioswarm_vhp_mint_spec)
  - IoSwarmNodeEmulator          (ioswarm_node_emulator)

The quorum thresholds and fail directions asserted here are protocol invariants:
renewal 0.60 < enforcement 0.67 < mint 0.80, and mint fails CLOSED while
adjudication/renewal fail OPEN.
"""
import dataclasses
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.ioswarm_adjudication_spec import VAPIAdjudicationSwarmTaskSpec
from vapi_bridge.ioswarm_node_emulator import IoSwarmNodeEmulator
from vapi_bridge.ioswarm_renewal_spec import VHPRenewalSwarmTaskSpec
from vapi_bridge.ioswarm_task_spec import VAPISwarmTaskSpec
from vapi_bridge.ioswarm_vhp_mint_spec import VAPIVHPMintSwarmTaskSpec


class TestVAPISwarmTaskSpec(unittest.TestCase):

    def test_defaults_and_frozen(self):
        spec = VAPISwarmTaskSpec()
        self.assertEqual(spec.task_id, "vapi_pitl_adjudication_v1")
        self.assertEqual(spec.executor, "vapi_bridge")
        self.assertEqual(spec.quorum_threshold, 0.60)
        self.assertEqual(spec.block_quorum_threshold, 0.67)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.quorum_threshold = 0.99

    def test_to_json_schema(self):
        doc = VAPISwarmTaskSpec().to_json()
        self.assertEqual(doc["status"], "phase109a_infrastructure_only")
        self.assertEqual(
            sorted(doc["input_schema"]),
            ["device_id", "evidence_json", "inference_code", "record_hash"],
        )
        self.assertEqual(doc["quorum_config"]["tie_resolution"], "HOLD")
        self.assertEqual(doc["quorum_config"]["general_threshold"], 0.60)
        self.assertEqual(doc["quorum_config"]["block_threshold"], 0.67)
        self.assertEqual(doc["chain"]["chain_id"], 4690)
        self.assertEqual(
            doc["w3bstream_applets"], ["validate_poac_record", "process_gsr_packet"]
        )
        spec = VAPISwarmTaskSpec()
        self.assertEqual(
            doc["vhp_authorization_gate"]["address"], spec.protocol_lens_address
        )

    def test_write_spec_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "spec.json")
            spec = VAPISwarmTaskSpec()
            spec.write_spec_file(path)
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), spec.to_json())


class TestVHPRenewalSwarmTaskSpec(unittest.TestCase):

    def test_renewal_quorum_is_lower_than_enforcement(self):
        renewal = VHPRenewalSwarmTaskSpec()
        self.assertEqual(renewal.quorum_threshold, 0.60)
        self.assertLess(
            renewal.quorum_threshold,
            VAPIAdjudicationSwarmTaskSpec().classj_block_quorum,
        )

    def test_to_json_schema(self):
        doc = VHPRenewalSwarmTaskSpec().to_json()
        self.assertEqual(doc["task_id"], "vapi_vhp_renewal_v1")
        self.assertEqual(doc["status"], "phase109b_infrastructure_only")
        self.assertEqual(doc["output_schema"]["verdict"], "CERTIFY_RENEW | SKIP_RENEW | HOLD")
        self.assertEqual(doc["quorum_config"]["min_nodes"], 3)
        self.assertEqual(doc["quorum_config"]["tie_resolution"], "HOLD")
        self.assertEqual(doc["chain"]["chain_id"], 4690)

    def test_write_spec_file_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "dir", "renewal.json")
            VHPRenewalSwarmTaskSpec().write_spec_file(path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["task_id"], "vapi_vhp_renewal_v1")


class TestVAPIAdjudicationSwarmTaskSpec(unittest.TestCase):

    def test_enforcement_thresholds(self):
        spec = VAPIAdjudicationSwarmTaskSpec()
        self.assertEqual(spec.classj_block_quorum, 0.67)
        self.assertEqual(spec.triage_block_quorum, 0.67)
        self.assertEqual(spec.dual_veto_score, 0.80)

    def test_dual_veto_config(self):
        doc = VAPIAdjudicationSwarmTaskSpec().to_json()
        veto = doc["dual_veto_config"]
        self.assertEqual(veto["dual_veto_score"], 0.80)
        self.assertIn("BLOCK AND", veto["dual_veto_condition"])
        # Adjudication fails toward CLEAR — opposite of the renewal fail-open verdict.
        self.assertTrue(
            doc["fail_open_direction"]["adjudication_errors"].startswith("CLEAR")
        )
        self.assertEqual(doc["quorum_config"]["tie_resolution"], "HOLD")

    def test_write_spec_file_default_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "adjudication.json")
            returned = VAPIAdjudicationSwarmTaskSpec().write_spec_file(path)
            self.assertEqual(returned, path)
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            self.assertEqual(doc["task_id"], "vapi_classj_triage_adjudication_v1")


class TestVAPIVHPMintSwarmTaskSpec(unittest.TestCase):

    def test_mint_is_strictest_and_fails_closed(self):
        spec = VAPIVHPMintSwarmTaskSpec()
        self.assertEqual(spec.mint_quorum, 0.80)
        self.assertEqual(spec.fail_direction, "CLOSED")
        self.assertGreater(spec.mint_quorum, VAPIAdjudicationSwarmTaskSpec().classj_block_quorum)

    def test_to_json_quorum_and_provenance(self):
        doc = VAPIVHPMintSwarmTaskSpec().to_json()
        self.assertEqual(doc["status"], "phase110_infrastructure_only")
        self.assertEqual(doc["quorum_config"]["threshold"], 0.80)
        self.assertEqual(doc["quorum_config"]["fail_direction"], "CLOSED")
        self.assertEqual(
            doc["w2_provenance"]["swarm_fingerprint"], "SHA-256(node_verdicts_json)"
        )
        self.assertEqual(
            doc["vhp_authorization_gate"]["method"], "isFullyEligible(operatorDeviceId)"
        )

    def test_write_spec_file_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mint", "spec.json")
            returned = VAPIVHPMintSwarmTaskSpec().write_spec_file(path)
            self.assertEqual(returned, path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["quorum_config"]["threshold"], 0.80)


class TestIoSwarmNodeEmulator(unittest.TestCase):

    def test_node_count_and_ids(self):
        nodes = IoSwarmNodeEmulator(n_nodes=3).evaluate_renewal("dev1", 1, 7)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(
            [n["node_id"] for n in nodes],
            ["ioswarm_emulator_node_0", "ioswarm_emulator_node_1", "ioswarm_emulator_node_2"],
        )

    def test_deterministic_for_same_inputs(self):
        a = IoSwarmNodeEmulator().evaluate_renewal("devA", 42, 4, recent_block_count=1)
        b = IoSwarmNodeEmulator().evaluate_renewal("devA", 42, 4, recent_block_count=1)
        self.assertEqual(a, b)

    def test_clean_streak_certifies_with_high_confidence(self):
        nodes = IoSwarmNodeEmulator().evaluate_renewal("devB", 1, 5, recent_block_count=0)
        self.assertTrue(all(n["verdict"] == "CERTIFY_RENEW" for n in nodes))
        self.assertTrue(all(0.85 <= n["confidence"] <= 0.95 for n in nodes))

    def test_moderate_streak_certifies_with_lower_confidence(self):
        nodes = IoSwarmNodeEmulator().evaluate_renewal("devC", 1, 3, recent_block_count=1)
        self.assertTrue(all(n["verdict"] == "CERTIFY_RENEW" for n in nodes))
        self.assertTrue(all(0.65 <= n["confidence"] <= 0.75 for n in nodes))

    def test_no_clean_streak_skips_renewal(self):
        nodes = IoSwarmNodeEmulator().evaluate_renewal("devD", 1, 0, recent_block_count=3)
        self.assertTrue(all(n["verdict"] == "SKIP_RENEW" for n in nodes))
        self.assertTrue(all(0.80 <= n["confidence"] <= 0.95 for n in nodes))

    def test_borderline_band_splits_verdicts_across_nodes(self):
        nodes = IoSwarmNodeEmulator(n_nodes=25).evaluate_renewal(
            "devE", 1, 1, recent_block_count=2
        )
        verdicts = {n["verdict"] for n in nodes}
        self.assertEqual(verdicts, {"CERTIFY_RENEW", "SKIP_RENEW"})
        self.assertTrue(all(0.50 <= n["confidence"] <= 0.70 for n in nodes))

    def test_different_seeds_are_independent(self):
        a = IoSwarmNodeEmulator(seed=109).evaluate_renewal("devF", 1, 1, recent_block_count=2)
        b = IoSwarmNodeEmulator(seed=777).evaluate_renewal("devF", 1, 1, recent_block_count=2)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
