"""VSS-4 — ACP get_stream_seat_status tool tests.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §7 (ACP read tool)
+ §8 (work package VSS-4).
Acceptance: "Agent can read seat status (digest only, scrubbed)"

Test coverage:
  1. Tool is in ALLOWED_TOOLS
  2. Tool is in GROK_ONLY_TOOLS (read-only, stays on Grok)
  3. Tool is in TOOL_IMPLS
  4. Intent matching: "stream seat status" → TOOL_STREAM_SEAT_STATUS
  5. Intent matching: "seat" → TOOL_STREAM_SEAT_STATUS
  6. Intent matching: "vss" → TOOL_STREAM_SEAT_STATUS
  7. Intent matching: "get stream seat" → TOOL_STREAM_SEAT_STATUS
  8. Eligible bridge → ok=True, ELIGIBLE in summary
  9. Ineligible bridge → ok=False, CLOSED in summary
 10. Bridge unreachable → ok=False, fail-closed message
 11. Honesty ribbon in tags (poep/l6b/candidate)
 12. No raw substrate in summary (no frames, HID, IMU, nsec)
 13. Dry-run mode returns dry-run result
 14. Routing: tool stays on Grok even if operator says "devin"
 15. Reason field included when present
 16. Reason field truncated to 80 chars
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as g  # noqa: E402


class TestStreamSeatStatusTool(unittest.TestCase):
    """VSS-4 ACP get_stream_seat_status tests."""

    def test_1_tool_in_allowed_tools(self):
        """Tool is in ALLOWED_TOOLS."""
        self.assertIn(g.TOOL_STREAM_SEAT_STATUS, g.ALLOWED_TOOLS)

    def test_2_tool_in_grok_only(self):
        """Tool is in GROK_ONLY_TOOLS (read-only, stays on Grok)."""
        self.assertIn(g.TOOL_STREAM_SEAT_STATUS, g.GROK_ONLY_TOOLS)

    def test_3_tool_in_impls(self):
        """Tool is in TOOL_IMPLS."""
        self.assertIn(g.TOOL_STREAM_SEAT_STATUS, g.TOOL_IMPLS)

    def test_4_intent_stream_seat_status(self):
        """Intent matching: 'stream seat status' → TOOL_STREAM_SEAT_STATUS."""
        cfg = g.GatewayConfig()
        intent = g._match_intent("stream seat status", cfg)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_STATUS)

    def test_5_intent_seat(self):
        """Intent matching: 'seat' → TOOL_STREAM_SEAT_STATUS."""
        cfg = g.GatewayConfig()
        intent = g._match_intent("seat", cfg)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_STATUS)

    def test_6_intent_vss(self):
        """Intent matching: 'vss' → TOOL_STREAM_SEAT_STATUS."""
        cfg = g.GatewayConfig()
        intent = g._match_intent("vss", cfg)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_STATUS)

    def test_7_intent_get_stream_seat(self):
        """Intent matching: 'get stream seat' → TOOL_STREAM_SEAT_STATUS."""
        cfg = g.GatewayConfig()
        intent = g._match_intent("get stream seat", cfg)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_STATUS)

    def test_8_eligible_bridge(self):
        """Eligible bridge → ok=True, ELIGIBLE in summary."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        elig_response = {
            "eligible": True,
            "capture_up": True,
            "retina_oracle_running": True,
            "reason_if_closed": "",
            "honesty": {"poep_enabled": True, "l6b_enabled": False,
                        "candidate_ok": False},
        }
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=elig_response):
            result = g._tool_stream_seat_status(intent, cfg)
        self.assertTrue(result.ok)
        self.assertIn("ELIGIBLE", result.summary)
        self.assertIn("capture: up", result.summary)
        self.assertIn("oracle: running", result.summary)

    def test_9_ineligible_bridge(self):
        """Ineligible bridge → ok=False, CLOSED in summary."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        elig_response = {
            "eligible": False,
            "capture_up": False,
            "retina_oracle_running": True,
            "reason_if_closed": "capture_down",
            "honesty": {"poep_enabled": False, "l6b_enabled": False,
                        "candidate_ok": False},
        }
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=elig_response):
            result = g._tool_stream_seat_status(intent, cfg)
        self.assertFalse(result.ok)
        self.assertIn("CLOSED", result.summary)
        self.assertIn("capture: down", result.summary)

    def test_10_bridge_unreachable(self):
        """Bridge unreachable → ok=False, fail-closed message."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=None):
            result = g._tool_stream_seat_status(intent, cfg)
        self.assertFalse(result.ok)
        self.assertIn("bridge unreachable", result.summary)
        self.assertIn("fail-closed", result.summary)

    def test_11_honesty_ribbon_in_tags(self):
        """Honesty ribbon (poep/l6b/candidate) present in tags."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        elig_response = {
            "eligible": True,
            "capture_up": True,
            "retina_oracle_running": True,
            "honesty": {"poep_enabled": True, "l6b_enabled": False,
                        "candidate_ok": True},
        }
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=elig_response):
            result = g._tool_stream_seat_status(intent, cfg)
        tag_map = {t[0]: t[1] for t in result.tags}
        self.assertEqual(tag_map["poep_enabled"], "true")
        self.assertEqual(tag_map["l6b_enabled"], "false")
        self.assertEqual(tag_map["candidate_ok"], "true")

    def test_12_no_raw_substrate_in_summary(self):
        """No raw substrate (frames, HID, IMU, nsec) in summary."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        elig_response = {
            "eligible": True,
            "capture_up": True,
            "retina_oracle_running": True,
            "honesty": {"poep_enabled": False, "l6b_enabled": False,
                        "candidate_ok": False},
        }
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=elig_response):
            result = g._tool_stream_seat_status(intent, cfg)
        for forbidden in ("frame", "base64", "hid_raw", "imu_raw",
                          "nsec", "poac_payload", "l4_features"):
            self.assertNotIn(forbidden, result.summary.lower(),
                             f"summary must not contain '{forbidden}'")

    def test_13_dry_run(self):
        """Dry-run mode returns dry-run result."""
        cfg = g.GatewayConfig(dry_run=True)
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        result = g.execute(intent, cfg)
        self.assertTrue(result.ok)
        self.assertIn("dry-run", result.summary)

    def test_14_routing_stays_grok(self):
        """Tool stays on Grok even if operator says 'devin'."""
        routed = g.route(g.TOOL_STREAM_SEAT_STATUS, explicit_devin=True)
        self.assertEqual(routed, g.HARNESS_GROK)

    def test_15_reason_field_included(self):
        """Reason field included when present."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        elig_response = {
            "eligible": False,
            "capture_up": False,
            "retina_oracle_running": True,
            "reason_if_closed": "capture_down",
            "honesty": {"poep_enabled": False, "l6b_enabled": False,
                        "candidate_ok": False},
        }
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=elig_response):
            result = g._tool_stream_seat_status(intent, cfg)
        self.assertIn("reason: capture_down", result.summary)

    def test_16_reason_field_truncated(self):
        """Reason field truncated to 80 chars."""
        cfg = g.GatewayConfig()
        intent = g.Intent(g.TOOL_STREAM_SEAT_STATUS)
        long_reason = "x" * 200
        elig_response = {
            "eligible": False,
            "capture_up": False,
            "retina_oracle_running": False,
            "reason_if_closed": long_reason,
            "honesty": {"poep_enabled": False, "l6b_enabled": False,
                        "candidate_ok": False},
        }
        with patch("qortroller_acp_gateway.bot._load_config"), \
             patch("qortroller_acp_gateway.bot._bridge_get",
                    return_value=elig_response):
            result = g._tool_stream_seat_status(intent, cfg)
        # The reason in the summary should be truncated to 80 chars
        self.assertIn("reason: " + "x" * 80, result.summary)
        self.assertNotIn("x" * 81, result.summary)


if __name__ == "__main__":
    unittest.main()
