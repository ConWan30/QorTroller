"""VSS-S3 — Consent-gated highlight / verify pointer tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vapi_bridge.vss_highlight import (  # noqa: E402
    DEFAULT_VERIFY_POINTER,
    build_highlight_event,
    format_verify_pointer_digest,
    validate_highlight_event,
)

import qortroller_acp_gateway as g  # noqa: E402


class TestS3Highlight(unittest.TestCase):
    def test_1_refuse_without_consent(self):
        with self.assertRaises(ValueError) as ctx:
            build_highlight_event(consent_ok=False, highlight_note="hi")
        self.assertIn("consent", str(ctx.exception).lower())

    def test_2_build_with_consent_and_note(self):
        ev = build_highlight_event(
            consent_ok=True,
            session_id="sess_1",
            highlight_note="match sealed",
            use_default_verify_pointer=True,
        )
        self.assertIn("consent=true", ev.to_content())
        self.assertIn("session: sess_1", ev.to_content())
        self.assertIn("verify:", ev.to_content())
        self.assertEqual(validate_highlight_event(ev.to_tags(), ev.to_content()), [])

    def test_3_need_payload(self):
        with self.assertRaises(ValueError):
            build_highlight_event(consent_ok=True)

    def test_4_forbidden_pattern_in_note(self):
        with self.assertRaises(ValueError):
            build_highlight_event(
                consent_ok=True,
                highlight_note="leaked nsec material",
            )

    def test_5_validate_requires_consent_tag(self):
        ev = build_highlight_event(
            consent_ok=True,
            highlight_note="ok",
            use_default_verify_pointer=True,
        )
        tags = [t for t in ev.to_tags() if t[0] != "consent_ok"]
        errs = validate_highlight_event(tags, ev.to_content())
        self.assertTrue(any("consent" in e for e in errs))

    def test_6_format_verify_pointer_display(self):
        s = format_verify_pointer_digest(session_id="grind_phase235_v1")
        self.assertIn("grind_phase235_v1", s)
        self.assertIn("portcert", s.lower())
        self.assertIn("display-only", s)

    def test_7_default_verify_pointer_constant(self):
        self.assertIn("portcert_full_verify", DEFAULT_VERIFY_POINTER)

    def test_8_acp_tool_allow_listed(self):
        self.assertIn(g.TOOL_STREAM_VERIFY_POINTER, g.ALLOWED_TOOLS)
        self.assertIn(g.TOOL_STREAM_VERIFY_POINTER, g.GROK_ONLY_TOOLS)
        self.assertIn(g.TOOL_STREAM_VERIFY_POINTER, g.TOOL_IMPLS)

    def test_9_intent_verify_pointer(self):
        cfg = g.GatewayConfig(operator_pubkeys=("aa" * 32,), rig_ops_channel="ch")
        intent = g._match_intent("verify pointer", cfg)
        self.assertIsInstance(intent, g.Intent)
        self.assertEqual(intent.tool, g.TOOL_STREAM_VERIFY_POINTER)

    def test_10_tool_returns_digest(self):
        cfg = g.GatewayConfig()
        result = g._tool_stream_verify_pointer(
            g.Intent(g.TOOL_STREAM_VERIFY_POINTER), cfg
        )
        self.assertTrue(result.ok)
        self.assertIn("verify-pointer", result.summary)
        tags = {t[0]: t[1] for t in result.tags}
        self.assertEqual(tags.get("consent_required_to_publish"), "true")


if __name__ == "__main__":
    unittest.main()
