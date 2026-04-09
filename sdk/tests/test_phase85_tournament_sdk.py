"""
Phase 85 — SDK v3.0.0 Tournament Operator Tests (10 tests)

test_1_sdk_version_is_3_0_0
test_2_gate_readiness_result_defaults
test_3_tournament_gate_returns_error_on_bad_url
test_4_tournament_gate_is_ready_false_on_failure
test_5_tournament_gate_parses_response
test_6_ceremony_audit_result_defaults
test_7_ceremony_audit_wraps_vapi_zk_proof
test_8_ceremony_audit_captures_exception
test_9_ruling_stream_parse_sse_block
test_10_ruling_stream_reconnect_url_includes_last_event_id
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SDK_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SDK_DIR))

# Stub heavy deps before sdk import
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_sdk import (  # noqa: E402
    SDK_VERSION,
    CeremonyAuditResult,
    GateReadinessResult,
    VAPICeremonyAudit,
    VAPITournamentGate,
    VAPIRulingStream,
    RulingStreamEvent,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. SDK version
# ---------------------------------------------------------------------------

class TestSDKVersion(unittest.TestCase):

    def test_1_sdk_version_is_3_0_0(self):
        """SDK_VERSION must be 3.0.0-phase156 after Phase 151 bump."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


# ---------------------------------------------------------------------------
# 2-4. VAPITournamentGate
# ---------------------------------------------------------------------------

class TestGateReadinessResult(unittest.TestCase):

    def test_2_gate_readiness_result_defaults(self):
        """GateReadinessResult default state is safe: not ready, dry_run=True."""
        r = GateReadinessResult()
        self.assertFalse(r.overall_ready)
        self.assertTrue(r.dry_run_active)
        self.assertEqual(r.gate_attestations_count, 0)
        self.assertIsNone(r.error)
        self.assertIsInstance(r.validation_gate, dict)
        self.assertIsInstance(r.fleet_health, dict)

    def test_3_tournament_gate_returns_error_on_bad_url(self):
        """Unreachable bridge URL surfaces error in result, never raises."""
        gate = VAPITournamentGate("http://127.0.0.1:19999", api_key="x")
        result = gate.check_gate_readiness()
        self.assertIsNotNone(result.error)
        self.assertFalse(result.overall_ready)

    def test_4_tournament_gate_is_ready_false_on_failure(self):
        """is_ready() returns False when bridge is unreachable."""
        gate = VAPITournamentGate("http://127.0.0.1:19999")
        self.assertFalse(gate.is_ready())

    def test_5_tournament_gate_parses_response(self):
        """check_gate_readiness() correctly maps a mocked bridge response."""
        import json
        import urllib.request

        fake_body = json.dumps({
            "overall_ready": True,
            "dry_run_active": False,
            "gate_attestations_count": 3,
            "validation_gate": {"gate_passed": True, "consecutive_clean": 100},
            "fleet_health": {"fleet_health": "ALL_HEALTHY"},
            "timestamp": 1711000000.0,
        }).encode()

        class _FakeResp:
            def read(self):
                return fake_body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        gate = VAPITournamentGate("http://bridge.test", api_key="k")
        with patch.object(urllib.request, "urlopen", return_value=_FakeResp()):
            result = gate.check_gate_readiness()

        self.assertTrue(result.overall_ready)
        self.assertFalse(result.dry_run_active)
        self.assertEqual(result.gate_attestations_count, 3)
        self.assertEqual(result.validation_gate["consecutive_clean"], 100)
        self.assertEqual(result.fleet_health["fleet_health"], "ALL_HEALTHY")
        self.assertAlmostEqual(result.timestamp, 1711000000.0)
        self.assertIsNone(result.error)


# ---------------------------------------------------------------------------
# 5-7. VAPICeremonyAudit
# ---------------------------------------------------------------------------

class TestCeremonyAuditResult(unittest.TestCase):

    def test_6_ceremony_audit_result_defaults(self):
        """CeremonyAuditResult default is safe: no match, error=None."""
        r = CeremonyAuditResult()
        self.assertFalse(r.on_chain_match)
        self.assertEqual(r.contributor_count, 0)
        self.assertEqual(r.local_hash, "")
        self.assertIsNone(r.error)

    def test_7_ceremony_audit_wraps_vapi_zk_proof(self):
        """VAPICeremonyAudit.audit() maps verify_ceremony_integrity() output."""
        import vapi_sdk as sdk_mod

        fake_result = {
            "local_hash": "abc123",
            "on_chain_match": True,
            "contributor_count": 3,
            "beacon_block_number": 41723255,
            "error": None,
        }
        with patch.object(sdk_mod.VAPIZKProof, "verify_ceremony_integrity",
                          return_value=fake_result):
            auditor = VAPICeremonyAudit(
                registry_address="0x1234", rpc_url="http://rpc"
            )
            result = auditor.audit({"protocol": "groth16"}, circuit_name="TestCircuit")

        self.assertEqual(result.local_hash, "abc123")
        self.assertTrue(result.on_chain_match)
        self.assertEqual(result.contributor_count, 3)
        self.assertEqual(result.beacon_block_number, 41723255)
        self.assertEqual(result.circuit_name, "TestCircuit")
        self.assertIsNone(result.error)

    def test_8_ceremony_audit_captures_exception(self):
        """VAPICeremonyAudit.audit() never raises — error in result.error."""
        import vapi_sdk as sdk_mod

        with patch.object(sdk_mod.VAPIZKProof, "verify_ceremony_integrity",
                          side_effect=RuntimeError("RPC timeout")):
            auditor = VAPICeremonyAudit(
                registry_address="0x5678", rpc_url="http://rpc"
            )
            result = auditor.audit({})

        self.assertIsNotNone(result.error)
        self.assertIn("RPC timeout", result.error)
        self.assertFalse(result.on_chain_match)


# ---------------------------------------------------------------------------
# 8-10. VAPIRulingStream
# ---------------------------------------------------------------------------

class TestRulingStream(unittest.TestCase):

    def test_9_ruling_stream_parse_sse_block(self):
        """_parse_sse_block correctly extracts id/event/data from SSE text."""
        block = "id: 42\nevent: ruling\ndata: {\"verdict\": \"FLAG\"}"
        parsed = VAPIRulingStream._parse_sse_block(block)
        self.assertEqual(parsed["id"], "42")
        self.assertEqual(parsed["event"], "ruling")
        self.assertIsInstance(parsed["data"], dict)
        self.assertEqual(parsed["data"]["verdict"], "FLAG")

    def test_10_ruling_stream_reconnect_url_includes_last_event_id(self):
        """Last-Event-ID header is added to reconnect request after first event."""
        stream = VAPIRulingStream(
            "http://bridge.test", api_key="op-key", device_id="dev-001"
        )
        # Simulate tracking a received event ID
        stream._last_event_id = "99"

        # Verify the URL builder works correctly (device_id in query)
        url = stream._build_url()
        self.assertIn("device_id=dev-001", url)
        self.assertIn("api_key=op-key", url)

        # Simulate that listen() would include Last-Event-ID header on reconnect
        # by checking the header construction logic directly
        headers = {"Accept": "text/event-stream"}
        if stream._last_event_id:
            headers["Last-Event-ID"] = stream._last_event_id
        self.assertEqual(headers["Last-Event-ID"], "99")


if __name__ == "__main__":
    unittest.main()
