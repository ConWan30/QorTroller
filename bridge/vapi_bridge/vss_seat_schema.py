"""VSS-2 — Seat event schema constants and validator.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §5 (Buzz surface):
  - Seat event kind 9 tag schema
  - Honesty ribbon (poep_enabled, l6b_enabled, candidate_ok)
  - Optional session_id (F2 watch-party bind slot)
  - Optional ioid_token (never required, display only)

This module defines the SCHEMA ONLY. The publish path (VSS-3) and the
ACP read tool (VSS-4) consume these constants. No Nostr signing, no
chain writes, no FROZEN wire changes.

Seat event shape (kind 9, digest-only):

  content: "stream seat OPEN | capture: up | oracle: running | media: <url>"
  tags: [
    ["h", "<streams-channel-uuid>"],        # derived by Rust helper
    ["qortroller", "1"],
    ["vss", "1"],
    ["seat", "OPEN" | "CLOSED"],
    ["capture", "up" | "down"],
    ["retina_oracle", "running" | "stopped"],
    ["media_url", "https://..."],           # required for OPEN, optional for CLOSED
    ["session_id", "<optional>"],           # F2 bind slot
    ["ioid_token", "<optional — never required>"],
    ["poep_enabled", "true" | "false"],     # honesty ribbon
    ["l6b_enabled", "true" | "false"],      # honesty ribbon
    ["candidate_ok", "true" | "false"],     # honesty ribbon
  ]

Forbidden in content/tags: frames, base64 video, raw HID, nsec, full PoAC.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- Schema constants ---

VSS_KIND = 9
VSS_TAG = "vss"
VSS_VERSION = "1"
QORTROLLER_TAG = "qortroller"
QORTROLLER_VERSION = "1"

SEAT_TAG = "seat"
SEAT_OPEN = "OPEN"
SEAT_CLOSED = "CLOSED"
SEAT_STATES = frozenset({SEAT_OPEN, SEAT_CLOSED})

CAPTURE_TAG = "capture"
CAPTURE_UP = "up"
CAPTURE_DOWN = "down"
CAPTURE_STATES = frozenset({CAPTURE_UP, CAPTURE_DOWN})

ORACLE_TAG = "retina_oracle"
ORACLE_RUNNING = "running"
ORACLE_STOPPED = "stopped"
ORACLE_STATES = frozenset({ORACLE_RUNNING, ORACLE_STOPPED})

MEDIA_URL_TAG = "media_url"
SESSION_ID_TAG = "session_id"
IOID_TOKEN_TAG = "ioid_token"
# F2: optional pointer from #streams seat → #matches channel UUID
MATCHES_CHANNEL_TAG = "matches_channel"

# VSS-7: signer role tag (optional, but if present must NOT be "bot" for OPEN)
SIGNER_ROLE_TAG = "signer_role"
SIGNER_ROLE_HUMAN = "human"
SIGNER_ROLE_BOT = "bot"
SIGNER_ROLES = frozenset({SIGNER_ROLE_HUMAN, SIGNER_ROLE_BOT})

# Honesty ribbon (always present, posted as-is — never invents "true")
RIBBON_TAGS = ("poep_enabled", "l6b_enabled", "candidate_ok")
RIBBON_TRUE = "true"
RIBBON_FALSE = "false"
RIBBON_VALUES = frozenset({RIBBON_TRUE, RIBBON_FALSE})

# Required tags for every seat event (h tag is derived by the Rust helper,
# not caller-supplied — see qortroller_buzz_bot._status_tags note)
REQUIRED_TAGS = (
    QORTROLLER_TAG,
    VSS_TAG,
    SEAT_TAG,
    CAPTURE_TAG,
    ORACLE_TAG,
) + RIBBON_TAGS

# Optional tags (present only when the gamer provides them)
OPTIONAL_TAGS = (
    MEDIA_URL_TAG,
    SESSION_ID_TAG,
    IOID_TOKEN_TAG,
    SIGNER_ROLE_TAG,
    MATCHES_CHANNEL_TAG,
)

# Tags that must NEVER appear in a seat event (substrate leakage guard)
FORBIDDEN_PATTERNS = (
    "nsec",
    "base64",
    "frame",
    "hid_raw",
    "imu_raw",
    "poac_payload",
    "l4_features",
    "private_key",
    "wallet_key",
)


@dataclass
class SeatEvent:
    """Validated VSS seat event (kind 9, digest-only).

    Use build_seat_event() to construct from raw fields; it enforces
    fail-closed semantics and ribbon honesty.
    """

    seat_state: str  # OPEN or CLOSED
    capture: str  # up or down
    retina_oracle: str  # running or stopped
    media_url: str | None = None
    session_id: str | None = None
    ioid_token: str | None = None
    signer_role: str | None = None  # VSS-7: optional, but bot cannot OPEN
    matches_channel: str | None = None  # F2: optional #matches channel UUID
    ribbon: dict[str, str] = field(default_factory=lambda: {
        "poep_enabled": RIBBON_FALSE,
        "l6b_enabled": RIBBON_FALSE,
        "candidate_ok": RIBBON_FALSE,
    })

    @property
    def session_bound(self) -> bool:
        """True when F2 watch-party bind is present (session_id non-empty)."""
        return bool(self.session_id and str(self.session_id).strip())

    def to_tags(self) -> list[list[str]]:
        """Serialize to Nostr tag list (excluding h tag — Rust helper derives it)."""
        tags: list[list[str]] = [
            [QORTROLLER_TAG, QORTROLLER_VERSION],
            [VSS_TAG, VSS_VERSION],
            [SEAT_TAG, self.seat_state],
            [CAPTURE_TAG, self.capture],
            [ORACLE_TAG, self.retina_oracle],
        ]
        if self.media_url:
            tags.append([MEDIA_URL_TAG, self.media_url])
        if self.session_id:
            tags.append([SESSION_ID_TAG, self.session_id])
        if self.ioid_token:
            tags.append([IOID_TOKEN_TAG, self.ioid_token])
        if self.signer_role:  # VSS-7
            tags.append([SIGNER_ROLE_TAG, self.signer_role])
        if self.matches_channel:  # F2
            tags.append([MATCHES_CHANNEL_TAG, self.matches_channel])
        # Honesty ribbon — always present, posted as-is
        for key in RIBBON_TAGS:
            tags.append([key, self.ribbon.get(key, RIBBON_FALSE)])
        return tags

    def to_content(self) -> str:
        """Serialize to the human-readable content string."""
        parts = [
            f"stream seat {self.seat_state}",
            f"capture: {self.capture}",
            f"oracle: {self.retina_oracle}",
        ]
        if self.media_url:
            parts.append(f"media: {self.media_url}")
        # F2: stranger-readable bind (URL alone ≠ sealed session claim)
        if self.session_id:
            parts.append(f"session: {self.session_id}")
        return " | ".join(parts)


def build_seat_event(
    *,
    seat_state: str,
    capture: str,
    retina_oracle: str,
    media_url: str | None = None,
    session_id: str | None = None,
    ioid_token: str | None = None,
    signer_role: str | None = None,
    matches_channel: str | None = None,
    poep_enabled: bool = False,
    l6b_enabled: bool = False,
    candidate_ok: bool = False,
) -> SeatEvent:
    """Build a validated SeatEvent with fail-closed defaults.

    Ribbon defaults to all-false (honest). The caller may pass true values
    but must do so explicitly — the builder never invents true.

    VSS-7: signer_role is optional. If present, must be "human" or "bot".
    The schema rejects bot-authored OPEN events; the seat helper must
    ALSO verify the role against the relay (kind 9000 self-add) — the
    schema tag is an honesty marker, not the enforcement point.

    F2: session_id is optional. When present, the seat claims a sealed
    session bind (R-VSS-06). Absence is honest — URL-only watch is still valid.
    matches_channel is an optional #matches UUID pointer (not a second proof).
    """
    if seat_state not in SEAT_STATES:
        raise ValueError(f"seat_state must be one of {SEAT_STATES}, got '{seat_state}'")
    if capture not in CAPTURE_STATES:
        raise ValueError(f"capture must be one of {CAPTURE_STATES}, got '{capture}'")
    if retina_oracle not in ORACLE_STATES:
        raise ValueError(f"retina_oracle must be one of {ORACLE_STATES}, got '{retina_oracle}'")
    if seat_state == SEAT_OPEN and not media_url:
        raise ValueError("media_url is required for OPEN seat events")
    if signer_role is not None and signer_role not in SIGNER_ROLES:
        raise ValueError(f"signer_role must be one of {SIGNER_ROLES} or None, got '{signer_role}'")
    if seat_state == SEAT_OPEN and signer_role == SIGNER_ROLE_BOT:
        raise ValueError("bot cannot OPEN a seat (VSS-7 / scope §4: humans open seats; agents view)")

    # Normalize empty strings to None (honest absence of F2 bind)
    if session_id is not None and not str(session_id).strip():
        session_id = None
    if matches_channel is not None and not str(matches_channel).strip():
        matches_channel = None

    # Forbidden content guard
    for field_val in (media_url, session_id, ioid_token, matches_channel):
        if field_val:
            _check_forbidden(field_val)

    ribbon = {
        "poep_enabled": RIBBON_TRUE if poep_enabled else RIBBON_FALSE,
        "l6b_enabled": RIBBON_TRUE if l6b_enabled else RIBBON_FALSE,
        "candidate_ok": RIBBON_TRUE if candidate_ok else RIBBON_FALSE,
    }

    return SeatEvent(
        seat_state=seat_state,
        capture=capture,
        retina_oracle=retina_oracle,
        media_url=media_url,
        session_id=session_id,
        ioid_token=ioid_token,
        signer_role=signer_role,
        matches_channel=matches_channel,
        ribbon=ribbon,
    )


def validate_seat_event(tags: list[list[str]], content: str = "") -> list[str]:
    """Validate a seat event's tags + content against the VSS schema.

    Returns a list of error strings. Empty list = valid.
    Never raises — returns errors for the caller to act on.
    """
    errors: list[str] = []

    # Build a tag lookup
    tag_map: dict[str, str] = {}
    for tag in tags:
        if not isinstance(tag, list) or len(tag) < 2:
            errors.append(f"malformed tag: {tag}")
            continue
        name, value = tag[0], tag[1]
        if name in tag_map:
            errors.append(f"duplicate tag: {name}")
        tag_map[name] = value

    # Check required tags
    for req in REQUIRED_TAGS:
        if req not in tag_map:
            errors.append(f"missing required tag: {req}")

    # Check qortroller version
    if QORTROLLER_TAG in tag_map and tag_map[QORTROLLER_TAG] != QORTROLLER_VERSION:
        errors.append(f"qortroller version must be '{QORTROLLER_VERSION}', got '{tag_map[QORTROLLER_TAG]}'")

    # Check vss version
    if VSS_TAG in tag_map and tag_map[VSS_TAG] != VSS_VERSION:
        errors.append(f"vss version must be '{VSS_VERSION}', got '{tag_map[VSS_TAG]}'")

    # Check seat state
    if SEAT_TAG in tag_map and tag_map[SEAT_TAG] not in SEAT_STATES:
        errors.append(f"seat must be one of {SEAT_STATES}, got '{tag_map[SEAT_TAG]}'")

    # Check capture state
    if CAPTURE_TAG in tag_map and tag_map[CAPTURE_TAG] not in CAPTURE_STATES:
        errors.append(f"capture must be one of {CAPTURE_STATES}, got '{tag_map[CAPTURE_TAG]}'")

    # Check oracle state
    if ORACLE_TAG in tag_map and tag_map[ORACLE_TAG] not in ORACLE_STATES:
        errors.append(f"retina_oracle must be one of {ORACLE_STATES}, got '{tag_map[ORACLE_TAG]}'")

    # Check ribbon values
    for ribbon_key in RIBBON_TAGS:
        if ribbon_key in tag_map and tag_map[ribbon_key] not in RIBBON_VALUES:
            errors.append(f"{ribbon_key} must be 'true' or 'false', got '{tag_map[ribbon_key]}'")

    # OPEN requires media_url
    if tag_map.get(SEAT_TAG) == SEAT_OPEN and MEDIA_URL_TAG not in tag_map:
        errors.append("media_url is required for OPEN seat events")

    # VSS-7: signer_role check — bot cannot OPEN
    if SIGNER_ROLE_TAG in tag_map:
        if tag_map[SIGNER_ROLE_TAG] not in SIGNER_ROLES:
            errors.append(
                f"{SIGNER_ROLE_TAG} must be one of {SIGNER_ROLES}, "
                f"got '{tag_map[SIGNER_ROLE_TAG]}'"
            )
        if (
            tag_map.get(SEAT_TAG) == SEAT_OPEN
            and tag_map[SIGNER_ROLE_TAG] == SIGNER_ROLE_BOT
        ):
            errors.append(
                "bot cannot OPEN a seat (VSS-7: humans open seats; agents view)"
            )

    # Forbidden content guard
    full_text = content + " " + " ".join(str(v) for v in tag_map.values())
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in full_text.lower():
            errors.append(f"forbidden pattern in content/tags: '{pattern}'")

    return errors


def _check_forbidden(value: str) -> None:
    """Raise ValueError if a forbidden pattern is found in the value."""
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in value.lower():
            raise ValueError(f"forbidden pattern in field: '{pattern}'")
