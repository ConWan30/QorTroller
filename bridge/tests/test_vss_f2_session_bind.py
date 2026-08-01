"""VSS-F2 — Verifiable watch-party session bind.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §9 F2:
  - Optional session_id on seat (schema slot + content line)
  - Optional matches_channel pointer
  - resolve_session_id: explicit / bridge probe / honest absence
  - require_session_bind fail-closed OPEN
  - R-VSS-06 sayable when bind is real (claim register)

Acceptance: a stranger can tell "watching a URL" from
"room claims session X"; missing bind is honest absence.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vapi_bridge.vss_seat_schema import (  # noqa: E402
    SEAT_OPEN,
    CAPTURE_UP,
    ORACLE_RUNNING,
    MATCHES_CHANNEL_TAG,
    build_seat_event,
    validate_seat_event,
)

import buzz_vss_seat  # noqa: E402

CLAIM_REGISTER = REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register-v0.md"
RUNBOOK = REPO_ROOT / "docs" / "runbook" / "buzz-vss-runbook.md"


def _cfg(**kw):
    defaults = dict(
        relay_url="ws://localhost:3000",
        channel_id="streams-uuid-test",
        bridge_base_url="http://localhost:8000",
        bridge_api_key="testkey",
        helper_path="/fake/helper",
        poll_interval=0.01,
        media_url="https://stream.example.com/live",
        session_id=None,
        ioid_token=None,
        matches_channel=None,
        bind_session=False,
        require_session_bind=False,
        dry_run=True,
    )
    defaults.update(kw)
    return buzz_vss_seat.SeatConfig(**defaults)


class TestF2Schema(unittest.TestCase):
    def test_1_content_includes_session_when_bound(self):
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            session_id="sess_abc123",
        )
        content = event.to_content()
        self.assertIn("session: sess_abc123", content)
        self.assertTrue(event.session_bound)
        self.assertEqual(validate_seat_event(event.to_tags(), content), [])

    def test_2_content_omits_session_when_absent(self):
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        content = event.to_content()
        self.assertNotIn("session:", content)
        self.assertFalse(event.session_bound)

    def test_3_matches_channel_tag_optional(self):
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            session_id="sess_1",
            matches_channel="matches-uuid-deadbeef",
        )
        tags = {t[0]: t[1] for t in event.to_tags()}
        self.assertEqual(tags[MATCHES_CHANNEL_TAG], "matches-uuid-deadbeef")
        self.assertEqual(tags["session_id"], "sess_1")
        self.assertEqual(validate_seat_event(event.to_tags(), event.to_content()), [])

    def test_4_empty_session_id_is_honest_absence(self):
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            session_id="   ",
        )
        self.assertIsNone(event.session_id)
        self.assertFalse(event.session_bound)


class TestF2Resolve(unittest.TestCase):
    def test_5_explicit_session_id_wins(self):
        cfg = _cfg(session_id="explicit_sess", bind_session=True)
        with patch.object(buzz_vss_seat, "_extract_session_id_from_status") as m:
            sid = buzz_vss_seat.resolve_session_id(cfg)
        self.assertEqual(sid, "explicit_sess")
        m.assert_not_called()

    def test_6_bind_session_reads_bridge(self):
        cfg = _cfg(bind_session=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "session_id": "from_bridge_sess",
            "device_id": "should_not_use_alone",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        with patch.dict("sys.modules", {"requests": mock_requests}):
            sid = buzz_vss_seat.resolve_session_id(cfg)
        self.assertEqual(sid, "from_bridge_sess")

    def test_7_extract_never_uses_device_id_alone(self):
        sid = buzz_vss_seat._extract_session_id_from_status(
            {"device_id": "dev_only", "session_active": True}
        )
        self.assertIsNone(sid)

    def test_8_extract_prefers_grind_session_id(self):
        sid = buzz_vss_seat._extract_session_id_from_status(
            {"grind_session_id": "grind_phase_v1", "device_id": "dev"}
        )
        self.assertEqual(sid, "grind_phase_v1")

    def test_9_require_session_bind_blocks_open(self):
        cfg = _cfg(require_session_bind=True, session_id=None, bind_session=False)
        result = buzz_vss_seat._build_and_publish(
            cfg,
            buzz_vss_seat.SEAT_OPEN,
            eligible=True,
            honesty={"poep_enabled": False, "l6b_enabled": False, "candidate_ok": False},
            signer_role="human",
        )
        self.assertIsNone(result)

    def test_10_open_with_session_publishes_tags(self):
        cfg = _cfg(session_id="sess_live_f2", dry_run=True)
        result = buzz_vss_seat._build_and_publish(
            cfg,
            buzz_vss_seat.SEAT_OPEN,
            eligible=True,
            honesty={"poep_enabled": False, "l6b_enabled": False, "candidate_ok": False},
            signer_role="human",
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.get("accepted"))


class TestF2ClaimRegister(unittest.TestCase):
    def test_11_rvss06_sayable_when_bind_live(self):
        text = CLAIM_REGISTER.read_text(encoding="utf-8")
        self.assertIn("R-VSS-06", text)
        # F2 live: sayable when session_id present (row documents the gate)
        m = re.search(r"R-VSS-06.*?yes", text, re.I | re.S)
        self.assertIsNotNone(
            m, "R-VSS-06 should be sayable after F2 bind is live"
        )

    def test_12_runbook_documents_f2(self):
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("session_id", text)
        self.assertTrue(
            "F2" in text or "watch-party" in text.lower() or "session bind" in text.lower(),
            "runbook should document F2 bind",
        )


if __name__ == "__main__":
    unittest.main()
