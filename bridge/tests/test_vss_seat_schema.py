"""VSS-2 — Seat event schema constants and validator tests.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §5 + §8 (VSS-2):
  Acceptance: "Fixture seat event validates; ribbon + optional session_id"

Test coverage:
  1. Valid OPEN event passes validation
  2. Valid CLOSED event passes validation
  3. Honesty ribbon present and defaults to all-false
  4. Ribbon never invents true (must be explicit)
  5. Optional session_id (F2 bind slot)
  6. Optional ioid_token (never required)
  7. OPEN without media_url fails
  8. Forbidden patterns (nsec, frames, HID) rejected
  9. Missing required tags fail
  10. Invalid seat/capture/oracle states fail
  11. build_seat_event + to_tags round-trip
  12. to_content produces correct content string
"""
import unittest

from vapi_bridge.vss_seat_schema import (
    VSS_KIND,
    SEAT_OPEN,
    SEAT_CLOSED,
    CAPTURE_UP,
    CAPTURE_DOWN,
    ORACLE_RUNNING,
    ORACLE_STOPPED,
    RIBBON_FALSE,
    RIBBON_TRUE,
    build_seat_event,
    validate_seat_event,
)


class TestSeatEventSchema(unittest.TestCase):
    """VSS-2 schema validation tests."""

    def test_1_valid_open_event(self):
        """A valid OPEN event with all fields passes validation."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        errors = validate_seat_event(event.to_tags(), event.to_content())
        self.assertEqual(errors, [], f"OPEN event should validate: {errors}")

    def test_2_valid_closed_event(self):
        """A valid CLOSED event passes validation (media_url optional)."""
        event = build_seat_event(
            seat_state=SEAT_CLOSED,
            capture=CAPTURE_DOWN,
            retina_oracle=ORACLE_STOPPED,
        )
        errors = validate_seat_event(event.to_tags(), event.to_content())
        self.assertEqual(errors, [], f"CLOSED event should validate: {errors}")

    def test_3_ribbon_defaults_all_false(self):
        """Honesty ribbon defaults to all-false (honest absence)."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        self.assertEqual(event.ribbon["poep_enabled"], RIBBON_FALSE)
        self.assertEqual(event.ribbon["l6b_enabled"], RIBBON_FALSE)
        self.assertEqual(event.ribbon["candidate_ok"], RIBBON_FALSE)

    def test_4_ribbon_never_invents_true(self):
        """Ribbon must be explicitly set to true — builder never invents it."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        tags = {t[0]: t[1] for t in event.to_tags()}
        # All ribbon values must be "false" when not explicitly passed
        for key in ("poep_enabled", "l6b_enabled", "candidate_ok"):
            self.assertEqual(tags[key], RIBBON_FALSE,
                             f"{key} must default to false, not invented true")

        # When explicitly passed true, it's honored
        event_true = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            poep_enabled=True,
        )
        tags_true = {t[0]: t[1] for t in event_true.to_tags()}
        self.assertEqual(tags_true["poep_enabled"], RIBBON_TRUE)

    def test_5_optional_session_id(self):
        """session_id is optional (F2 watch-party bind slot)."""
        event_with = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            session_id="sess_abc123",
        )
        tags_with = {t[0]: t[1] for t in event_with.to_tags()}
        self.assertEqual(tags_with["session_id"], "sess_abc123")
        errors = validate_seat_event(event_with.to_tags(), event_with.to_content())
        self.assertEqual(errors, [])

        event_without = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        tags_without = {t[0]: t[1] for t in event_without.to_tags()}
        self.assertNotIn("session_id", tags_without)
        errors = validate_seat_event(event_without.to_tags(), event_without.to_content())
        self.assertEqual(errors, [])

    def test_6_optional_ioid_token_never_required(self):
        """ioid_token is optional and never required (VSS §2)."""
        event_with = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            ioid_token="498",
        )
        tags_with = {t[0]: t[1] for t in event_with.to_tags()}
        self.assertEqual(tags_with["ioid_token"], "498")
        errors = validate_seat_event(event_with.to_tags(), event_with.to_content())
        self.assertEqual(errors, [])

        event_without = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        tags_without = {t[0]: t[1] for t in event_without.to_tags()}
        self.assertNotIn("ioid_token", tags_without)
        errors = validate_seat_event(event_without.to_tags(), event_without.to_content())
        self.assertEqual(errors, [])

    def test_7_open_without_media_url_fails(self):
        """OPEN without media_url should fail validation."""
        with self.assertRaises(ValueError, msg="OPEN without media_url should raise"):
            build_seat_event(
                seat_state=SEAT_OPEN,
                capture=CAPTURE_UP,
                retina_oracle=ORACLE_RUNNING,
                media_url=None,
            )

    def test_8_forbidden_patterns_rejected(self):
        """Forbidden patterns (nsec, frames, HID) are rejected."""
        for forbidden in ("nsec1abc", "base64videodata", "frame_0_raw", "hid_raw_data"):
            with self.assertRaises(ValueError,
                                   msg=f"should reject '{forbidden}'"):
                build_seat_event(
                    seat_state=SEAT_OPEN,
                    capture=CAPTURE_UP,
                    retina_oracle=ORACLE_RUNNING,
                    media_url=f"https://example.com/{forbidden}",
                )

        # Also test via validate_seat_event with raw tags
        bad_tags = [
            ["qortroller", "1"],
            ["vss", "1"],
            ["seat", "OPEN"],
            ["capture", "up"],
            ["retina_oracle", "running"],
            ["media_url", "https://example.com/nsec1secret"],
            ["poep_enabled", "false"],
            ["l6b_enabled", "false"],
            ["candidate_ok", "false"],
        ]
        errors = validate_seat_event(bad_tags)
        self.assertTrue(any("nsec" in e for e in errors),
                        f"should flag nsec pattern: {errors}")

    def test_9_missing_required_tags_fail(self):
        """Missing required tags should produce validation errors."""
        # Missing vss tag
        tags = [
            ["qortroller", "1"],
            ["seat", "OPEN"],
            ["capture", "up"],
            ["retina_oracle", "running"],
            ["media_url", "https://example.com/live"],
            ["poep_enabled", "false"],
            ["l6b_enabled", "false"],
            ["candidate_ok", "false"],
        ]
        errors = validate_seat_event(tags)
        self.assertTrue(any("vss" in e for e in errors),
                        f"should flag missing vss tag: {errors}")

    def test_10_invalid_seat_state_fails(self):
        """Invalid seat/capture/oracle states fail validation."""
        with self.assertRaises(ValueError):
            build_seat_event(
                seat_state="PAUSED",  # invalid
                capture=CAPTURE_UP,
                retina_oracle=ORACLE_RUNNING,
                media_url="https://example.com/live",
            )
        with self.assertRaises(ValueError):
            build_seat_event(
                seat_state=SEAT_OPEN,
                capture="maybe",  # invalid
                retina_oracle=ORACLE_RUNNING,
                media_url="https://example.com/live",
            )
        with self.assertRaises(ValueError):
            build_seat_event(
                seat_state=SEAT_OPEN,
                capture=CAPTURE_UP,
                retina_oracle="thinking",  # invalid
                media_url="https://example.com/live",
            )

    def test_11_build_and_roundtrip(self):
        """build_seat_event → to_tags → validate_seat_event round-trips clean."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
            session_id="sess_xyz",
            ioid_token="498",
            poep_enabled=False,
            l6b_enabled=False,
            candidate_ok=False,
        )
        tags = event.to_tags()
        content = event.to_content()
        errors = validate_seat_event(tags, content)
        self.assertEqual(errors, [], f"round-trip should validate: {errors}")

        # Verify all expected tags present
        tag_names = {t[0] for t in tags}
        expected = {"qortroller", "vss", "seat", "capture", "retina_oracle",
                    "media_url", "session_id", "ioid_token",
                    "poep_enabled", "l6b_enabled", "candidate_ok"}
        self.assertEqual(tag_names, expected,
                         f"tag set mismatch: {tag_names ^ expected}")

    def test_12_content_string(self):
        """to_content produces the correct human-readable content string."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        content = event.to_content()
        self.assertIn("stream seat OPEN", content)
        self.assertIn("capture: up", content)
        self.assertIn("oracle: running", content)
        self.assertIn("media: https://stream.example.com/live", content)

        # CLOSED without media_url
        event_closed = build_seat_event(
            seat_state=SEAT_CLOSED,
            capture=CAPTURE_DOWN,
            retina_oracle=ORACLE_STOPPED,
        )
        content_closed = event_closed.to_content()
        self.assertIn("stream seat CLOSED", content_closed)
        self.assertIn("capture: down", content_closed)
        self.assertIn("oracle: stopped", content_closed)
        self.assertNotIn("media:", content_closed)

    def test_13_vss_kind_is_9(self):
        """VSS seat events are kind 9 (NIP-29 channel message)."""
        self.assertEqual(VSS_KIND, 9)

    def test_14_closed_with_media_url_optional(self):
        """CLOSED event may optionally include media_url (e.g. replay pointer)."""
        event = build_seat_event(
            seat_state=SEAT_CLOSED,
            capture=CAPTURE_DOWN,
            retina_oracle=ORACLE_STOPPED,
            media_url="https://stream.example.com/replay",
        )
        errors = validate_seat_event(event.to_tags(), event.to_content())
        self.assertEqual(errors, [], f"CLOSED with media_url should validate: {errors}")

    def test_15_no_ioid_in_required_tags(self):
        """ioid_token is NOT in REQUIRED_TAGS — it's optional (VSS §2)."""
        from vapi_bridge.vss_seat_schema import REQUIRED_TAGS, OPTIONAL_TAGS
        self.assertNotIn("ioid_token", REQUIRED_TAGS)
        self.assertIn("ioid_token", OPTIONAL_TAGS)

    def test_16_dollar_h_not_in_output_tags(self):
        """h tag is NOT in to_tags output — Rust helper derives it."""
        event = build_seat_event(
            seat_state=SEAT_OPEN,
            capture=CAPTURE_UP,
            retina_oracle=ORACLE_RUNNING,
            media_url="https://stream.example.com/live",
        )
        tag_names = [t[0] for t in event.to_tags()]
        self.assertNotIn("h", tag_names,
                         "h tag must not be in caller-supplied tags (Rust helper derives it)")


if __name__ == "__main__":
    unittest.main()
