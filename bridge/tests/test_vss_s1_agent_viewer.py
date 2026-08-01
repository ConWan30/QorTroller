"""VSS-S1 — Agent viewers: summarize + flag-down (never OPEN).

Scope: docs/design/buzz-vss-stream-seat-scope-v0.md §9 S1 + §4.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vapi_bridge.vss_agent_viewer import (  # noqa: E402
    FLAG_DOWN,
    SEAT_OK,
    SEAT_UNKNOWN,
    agent_may_open_seat,
    flag_seat_down,
    summarize_seat,
)

import qortroller_acp_gateway as g  # noqa: E402


def _cfg() -> g.GatewayConfig:
    return g.GatewayConfig(
        operator_pubkeys=("aa" * 32,),
        rig_ops_channel="ch",
        dry_run=False,
    )


class TestS1PurePolicy(unittest.TestCase):
    def test_1_agent_cannot_open(self):
        self.assertFalse(agent_may_open_seat())

    def test_2_summarize_eligible(self):
        elig = {
            "eligible": True,
            "capture_up": True,
            "retina_oracle_running": True,
            "reason_if_closed": "",
            "honesty": {
                "poep_enabled": False,
                "l6b_enabled": False,
                "candidate_ok": False,
            },
        }
        s = summarize_seat(elig)
        self.assertIn("ELIGIBLE", s)
        self.assertIn("cannot OPEN", s)
        self.assertNotIn("nsec", s)

    def test_3_summarize_down(self):
        elig = {
            "eligible": False,
            "capture_up": False,
            "retina_oracle_running": True,
            "reason_if_closed": "capture down",
            "honesty": {},
        }
        s = summarize_seat(elig)
        self.assertIn("DOWN", s)
        self.assertIn("capture: down", s)

    def test_4_summarize_unknown(self):
        s = summarize_seat(None)
        self.assertIn("UNKNOWN", s)
        self.assertIn("fail-closed", s)

    def test_5_flag_down_when_ineligible(self):
        d = flag_seat_down(
            {
                "eligible": False,
                "capture_up": False,
                "retina_oracle_running": False,
                "reason_if_closed": "oracle stopped",
            }
        )
        self.assertEqual(d["flag"], FLAG_DOWN)
        self.assertTrue(d["should_flag"])
        self.assertIn("FLAG_DOWN", d["summary"])

    def test_6_flag_ok_when_eligible(self):
        d = flag_seat_down(
            {
                "eligible": True,
                "capture_up": True,
                "retina_oracle_running": True,
                "reason_if_closed": "",
            }
        )
        self.assertEqual(d["flag"], SEAT_OK)
        self.assertFalse(d["should_flag"])

    def test_7_flag_unknown_when_bridge_none(self):
        d = flag_seat_down(None)
        self.assertEqual(d["flag"], SEAT_UNKNOWN)
        self.assertFalse(d["should_flag"])


class TestS1AcpSurface(unittest.TestCase):
    def test_8_tools_allow_listed(self):
        self.assertIn(g.TOOL_STREAM_SEAT_SUMMARY, g.ALLOWED_TOOLS)
        self.assertIn(g.TOOL_STREAM_SEAT_FLAG, g.ALLOWED_TOOLS)
        self.assertIn(g.TOOL_STREAM_SEAT_SUMMARY, g.GROK_ONLY_TOOLS)
        self.assertIn(g.TOOL_STREAM_SEAT_FLAG, g.GROK_ONLY_TOOLS)
        self.assertIn(g.TOOL_STREAM_SEAT_SUMMARY, g.TOOL_IMPLS)
        self.assertIn(g.TOOL_STREAM_SEAT_FLAG, g.TOOL_IMPLS)

    def test_9_intent_summarize(self):
        intent = g._match_intent("summarize stream seat", _cfg())
        self.assertIsInstance(intent, g.Intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_SUMMARY)

    def test_10_intent_flag(self):
        intent = g._match_intent("flag seat down", _cfg())
        self.assertIsInstance(intent, g.Intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_FLAG)

    def test_11_generic_seat_still_status(self):
        intent = g._match_intent("seat", _cfg())
        self.assertIsInstance(intent, g.Intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_SEAT_STATUS)

    def test_12_summary_tool_eligible(self):
        elig = {
            "eligible": True,
            "capture_up": True,
            "retina_oracle_running": True,
            "reason_if_closed": "",
            "honesty": {"poep_enabled": False},
        }
        with patch.object(g.bot, "_load_config", return_value=MagicMock()), patch.object(
            g.bot, "_bridge_get", return_value=elig
        ):
            result = g._tool_stream_seat_summary(
                g.Intent(g.TOOL_STREAM_SEAT_SUMMARY), _cfg()
            )
        self.assertTrue(result.ok)
        self.assertIn("ELIGIBLE", result.summary)
        self.assertIn("cannot OPEN", result.summary)

    def test_13_flag_tool_down(self):
        elig = {
            "eligible": False,
            "capture_up": False,
            "retina_oracle_running": False,
            "reason_if_closed": "capture down",
        }
        with patch.object(g.bot, "_load_config", return_value=MagicMock()), patch.object(
            g.bot, "_bridge_get", return_value=elig
        ):
            result = g._tool_stream_seat_flag(
                g.Intent(g.TOOL_STREAM_SEAT_FLAG), _cfg()
            )
        self.assertTrue(result.ok)
        self.assertIn("FLAG_DOWN", result.summary)
        flag_tags = {t[0]: t[1] for t in result.tags}
        self.assertEqual(flag_tags.get("flag"), FLAG_DOWN)
        self.assertEqual(flag_tags.get("agent_can_open"), "false")


if __name__ == "__main__":
    unittest.main()
