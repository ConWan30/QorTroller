"""VSS-S5 — Organizer pilot room (seat + pin + portcert) tests."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vapi_bridge.vss_organizer_pilot import (  # noqa: E402
    PilotInputs,
    build_checklist,
    build_pilot_event,
    organizer_commands,
    pilot_from_eligibility,
    validate_pilot_event,
)

import qortroller_acp_gateway as g  # noqa: E402


class TestS5Pilot(unittest.TestCase):
    def test_1_not_ready_without_session(self):
        c = build_checklist(
            PilotInputs(seat_eligible=True, session_id=None, portcert_cmd="cmd")
        )
        self.assertFalse(c.ready)
        self.assertIn("session_id", c.missing)

    def test_2_ready_with_seat_session_portcert(self):
        c = build_checklist(
            PilotInputs(
                seat_eligible=True,
                session_id="sess_1",
                portcert_cmd="python scripts/portcert_full_verify.py",
            )
        )
        self.assertTrue(c.ready)
        self.assertTrue(c.seat_ok)
        self.assertTrue(c.session_bound)
        self.assertFalse(c.pin_present)  # pin optional for ready

    def test_3_pin_optional_but_tracked(self):
        c = build_checklist(
            PilotInputs(
                seat_eligible=True,
                session_id="sess_1",
                pin_event_id="abcd" * 16,
                portcert_cmd="python scripts/portcert_full_verify.py",
            )
        )
        self.assertTrue(c.ready)
        self.assertTrue(c.pin_present)

    def test_4_consent_required_to_build_event(self):
        with self.assertRaises(ValueError):
            build_pilot_event(
                consent_ok=False,
                inputs=PilotInputs(seat_eligible=True, session_id="s"),
            )

    def test_5_build_and_validate(self):
        ev = build_pilot_event(
            consent_ok=True,
            inputs=PilotInputs(
                seat_eligible=True,
                session_id="grind_phase235_v1",
                media_url="https://example.com/live",
                pin_event_id="e" * 64,
                streams_channel="streams-uuid",
                matches_channel="matches-uuid",
            ),
        )
        self.assertIn("organizer-pilot", ev.to_content())
        self.assertIn("grind_phase235_v1", ev.to_content())
        self.assertEqual(validate_pilot_event(ev.to_tags(), ev.to_content()), [])

    def test_6_from_eligibility_none(self):
        c = pilot_from_eligibility(None, session_id="s")
        self.assertFalse(c.seat_ok)
        self.assertIn("seat_eligibility", c.missing)

    def test_7_organizer_commands_fill_session(self):
        cmds = organizer_commands(session_id="sess_x", pin_event_id="pin123")
        self.assertTrue(any("sess_x" in c for c in cmds))
        self.assertTrue(any("pin123" in c for c in cmds))
        self.assertTrue(any("portcert_full_verify" in c for c in cmds))

    def test_8_acp_allow_listed(self):
        self.assertIn(g.TOOL_ORGANIZER_PILOT, g.ALLOWED_TOOLS)
        self.assertIn(g.TOOL_ORGANIZER_PILOT, g.GROK_ONLY_TOOLS)
        self.assertIn(g.TOOL_ORGANIZER_PILOT, g.TOOL_IMPLS)

    def test_9_intent_pilot(self):
        cfg = g.GatewayConfig(operator_pubkeys=("aa" * 32,), rig_ops_channel="ch")
        intent = g._match_intent("organizer pilot", cfg)
        self.assertIsInstance(intent, g.Intent)
        self.assertEqual(intent.tool, g.TOOL_ORGANIZER_PILOT)

    def test_10_acp_tool_runs(self):
        elig = {
            "eligible": True,
            "capture_up": True,
            "retina_oracle_running": True,
            "reason_if_closed": "",
        }
        with patch.object(g.bot, "_load_config", return_value=MagicMock()), patch.object(
            g.bot, "_bridge_get", return_value=elig
        ), patch.dict(os.environ, {"VSS_SESSION_ID": "sess_live"}, clear=False):
            result = g._tool_organizer_pilot(
                g.Intent(g.TOOL_ORGANIZER_PILOT), g.GatewayConfig()
            )
        self.assertTrue(result.ok)
        self.assertIn("organizer-pilot", result.summary)
        tags = {t[0]: t[1] for t in result.tags}
        self.assertEqual(tags.get("session_bound"), "true")


if __name__ == "__main__":
    unittest.main()
