"""VSS-7 — Agent viewer policy (bot cannot OPEN, can READ) tests.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §4 (Who can open)
+ §8 (work package VSS-7) + F3 (Gamer sovereignty).
Acceptance: "Bot cannot OPEN; can READ"

Test coverage:
  Schema layer (vss_seat_schema.py):
   1. signer_role tag constant exists
   2. SIGNER_ROLE_BOT / SIGNER_ROLE_HUMAN constants
   3. build_seat_event accepts signer_role
   4. build_seat_event with signer_role=human OPEN succeeds
   5. build_seat_event with signer_role=bot OPEN raises ValueError
   6. build_seat_event with signer_role=bot CLOSED succeeds (bots can close)
   7. build_seat_event with invalid signer_role raises ValueError
   8. signer_role=None (omitted) succeeds for both OPEN and CLOSED
   9. validate_seat_event rejects bot OPEN tags
  10. validate_seat_event accepts human OPEN tags
  11. validate_seat_event accepts bot CLOSED tags
  12. SeatEvent.to_tags() includes signer_role when set
  13. SeatEvent.to_tags() omits signer_role when None

  Helper layer (buzz_vss_seat.py):
  14. check_signer_is_not_bot returns "bot" when role=bot
  15. check_signer_is_not_bot returns "human" when role=human
  16. check_signer_is_not_bot returns None on relay unreachable (fail-closed)
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from vapi_bridge.vss_seat_schema import (
    SEAT_OPEN,
    SEAT_CLOSED,
    CAPTURE_UP,
    CAPTURE_DOWN,
    ORACLE_RUNNING,
    ORACLE_STOPPED,
    SIGNER_ROLE_TAG,
    SIGNER_ROLE_HUMAN,
    SIGNER_ROLE_BOT,
    SIGNER_ROLES,
    build_seat_event,
    validate_seat_event,
)
from buzz_vss_seat import (
    SeatConfig,
    check_signer_is_not_bot,
    _build_and_publish,
)


def _make_cfg(**kw):
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
        dry_run=False,
    )
    defaults.update(kw)
    return SeatConfig(**defaults)


class TestSchemaSignerRole(unittest.TestCase):
    """VSS-7 schema layer tests."""

    def test_1_signer_role_tag_constant(self):
        """signer_role tag constant exists."""
        self.assertEqual(SIGNER_ROLE_TAG, "signer_role")

    def test_2_role_constants(self):
        """SIGNER_ROLE_BOT / SIGNER_ROLE_HUMAN constants."""
        self.assertEqual(SIGNER_ROLE_HUMAN, "human")
        self.assertEqual(SIGNER_ROLE_BOT, "bot")
        self.assertIn(SIGNER_ROLE_HUMAN, SIGNER_ROLES)
        self.assertIn(SIGNER_ROLE_BOT, SIGNER_ROLES)

    def test_3_build_accepts_signer_role(self):
        """build_seat_event accepts signer_role parameter."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            signer_role=SIGNER_ROLE_HUMAN,
        )
        self.assertEqual(event.signer_role, SIGNER_ROLE_HUMAN)

    def test_4_human_open_succeeds(self):
        """build_seat_event with signer_role=human OPEN succeeds."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            signer_role=SIGNER_ROLE_HUMAN,
        )
        self.assertEqual(event.seat_state, SEAT_OPEN)

    def test_5_bot_open_raises(self):
        """build_seat_event with signer_role=bot OPEN raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            build_seat_event(
                seat_state=SEAT_OPEN,
                capture=CAPTURE_UP,
                retina_oracle=ORACLE_RUNNING,
                media_url="https://stream.example.com/live",
                signer_role=SIGNER_ROLE_BOT,
            )
        self.assertIn("bot cannot OPEN", str(ctx.exception))

    def test_6_bot_closed_succeeds(self):
        """build_seat_event with signer_role=bot CLOSED succeeds (bots can close)."""
        event = build_seat_event(
            seat_state=SEAT_CLOSED,
            capture=CAPTURE_DOWN,
            retina_oracle=ORACLE_STOPPED,
            signer_role=SIGNER_ROLE_BOT,
        )
        self.assertEqual(event.seat_state, SEAT_CLOSED)

    def test_7_invalid_role_raises(self):
        """build_seat_event with invalid signer_role raises ValueError."""
        with self.assertRaises(ValueError):
            build_seat_event(
                seat_state=SEAT_OPEN,
                capture=CAPTURE_UP,
                retina_oracle=ORACLE_RUNNING,
                media_url="https://stream.example.com/live",
                signer_role="admin",
            )

    def test_8_none_role_succeeds(self):
        """signer_role=None (omitted) succeeds for both OPEN and CLOSED."""
        ev_open = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        self.assertIsNone(ev_open.signer_role)
        ev_closed = build_seat_event(
            seat_state=SEAT_CLOSED,
            capture=CAPTURE_DOWN,
            retina_oracle=ORACLE_STOPPED,
        )
        self.assertIsNone(ev_closed.signer_role)

    def test_9_validate_rejects_bot_open(self):
        """validate_seat_event rejects bot OPEN tags."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            signer_role=SIGNER_ROLE_HUMAN,  # build succeeds with human
        )
        # Now manually craft tags with bot role to test the validator
        tags = event.to_tags()
        # Replace the signer_role tag value with bot
        for tag in tags:
            if tag[0] == SIGNER_ROLE_TAG:
                tag[1] = SIGNER_ROLE_BOT
        errors = validate_seat_event(tags, event.to_content())
        self.assertTrue(any("bot cannot OPEN" in e for e in errors),
                        f"Expected bot OPEN rejection, got: {errors}")

    def test_10_validate_accepts_human_open(self):
        """validate_seat_event accepts human OPEN tags."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            signer_role=SIGNER_ROLE_HUMAN,
        )
        errors = validate_seat_event(event.to_tags(), event.to_content())
        self.assertEqual(errors, [], f"Human OPEN should validate: {errors}")

    def test_11_validate_accepts_bot_closed(self):
        """validate_seat_event accepts bot CLOSED tags."""
        event = build_seat_event(
            seat_state=SEAT_CLOSED,
            capture=CAPTURE_DOWN,
            retina_oracle=ORACLE_STOPPED,
            signer_role=SIGNER_ROLE_BOT,
        )
        errors = validate_seat_event(event.to_tags(), event.to_content())
        self.assertEqual(errors, [], f"Bot CLOSED should validate: {errors}")

    def test_12_to_tags_includes_role(self):
        """SeatEvent.to_tags() includes signer_role when set."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            signer_role=SIGNER_ROLE_HUMAN,
        )
        tags = event.to_tags()
        role_tags = [t for t in tags if t[0] == SIGNER_ROLE_TAG]
        self.assertEqual(len(role_tags), 1)
        self.assertEqual(role_tags[0][1], SIGNER_ROLE_HUMAN)

    def test_13_to_tags_omits_none_role(self):
        """SeatEvent.to_tags() omits signer_role when None."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        tags = event.to_tags()
        role_tags = [t for t in tags if t[0] == SIGNER_ROLE_TAG]
        self.assertEqual(len(role_tags), 0)


class TestHelperRoleCheck(unittest.TestCase):
    """VSS-7 helper layer tests — check_signer_is_not_bot."""

    def test_14_returns_bot_when_role_is_bot(self):
        """check_signer_is_not_bot returns 'bot' when role=bot."""
        cfg = _make_cfg(helper_path="/fake/helper")
        mock_whoami = MagicMock(returncode=0, stdout="abc123pubkey\n", stderr="")
        mock_profile = MagicMock(
            returncode=0,
            stdout='{"role": "bot"}\n',
            stderr="",
        )
        with patch("os.path.isfile", return_value=True), \
             patch("subprocess.run", side_effect=[mock_whoami, mock_profile]):
            result = check_signer_is_not_bot(cfg)
        self.assertEqual(result, "bot")

    def test_15_returns_human_when_role_is_human(self):
        """check_signer_is_not_bot returns 'human' when role=human."""
        cfg = _make_cfg(helper_path="/fake/helper")
        mock_whoami = MagicMock(returncode=0, stdout="abc123pubkey\n", stderr="")
        mock_profile = MagicMock(
            returncode=0,
            stdout='{"role": "human"}\n',
            stderr="",
        )
        with patch("os.path.isfile", return_value=True), \
             patch("subprocess.run", side_effect=[mock_whoami, mock_profile]):
            result = check_signer_is_not_bot(cfg)
        self.assertEqual(result, "human")

    def test_16_returns_none_on_relay_unreachable(self):
        """check_signer_is_not_bot returns None on relay unreachable (fail-closed)."""
        cfg = _make_cfg(helper_path="/fake/helper")
        mock_whoami = MagicMock(returncode=0, stdout="abc123pubkey\n", stderr="")
        mock_profile = MagicMock(returncode=1, stdout="", stderr="connection refused")
        with patch("os.path.isfile", return_value=True), \
             patch("subprocess.run", side_effect=[mock_whoami, mock_profile]):
            result = check_signer_is_not_bot(cfg)
        self.assertIsNone(result, "Fail-closed: relay unreachable must return None")


if __name__ == "__main__":
    unittest.main()
