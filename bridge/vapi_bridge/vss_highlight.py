"""VSS-S3 — Consent-gated highlight / verify pointer.

Scope later-spine S3 (after VSS-6): after a stream seat, the gamer may
optionally post a highlight note and/or a public verify pointer. Both are
**consent-gated** — never auto-fired by the bridge or EA bot.

Hard rules:
  - consent_ok must be explicit True to build/publish (no default-on)
  - verify pointer is a URL or command pointer only — never raw HID/PoAC
  - highlight text is short digest prose, forbidden-pattern scrubbed
  - agents cannot author highlights (gamer key only — enforced by publish path)
  - no FROZEN wire / chain / commitment formula changes
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from vapi_bridge.vss_seat_schema import (
    QORTROLLER_TAG,
    QORTROLLER_VERSION,
    VSS_TAG,
    VSS_VERSION,
    FORBIDDEN_PATTERNS,
    _check_forbidden,
)

# Tags for kind-9 highlight / verify-pointer messages
HIGHLIGHT_KIND_TAG = "vss_event"
HIGHLIGHT_KIND_VALUE = "highlight"
VERIFY_URL_TAG = "verify_url"
HIGHLIGHT_NOTE_TAG = "highlight_note"
SESSION_ID_TAG = "session_id"
CONSENT_OK_TAG = "consent_ok"
CONSENT_OK_TRUE = "true"

MAX_HIGHLIGHT_CHARS = 200
MAX_VERIFY_URL_CHARS = 512

# Default public verify pointer (stranger-runnable, no operator keys)
DEFAULT_VERIFY_POINTER = (
    "python scripts/portcert_full_verify.py  # G5-VER public verify"
)


@dataclass
class HighlightEvent:
    """Consent-gated highlight + optional verify pointer (digest only)."""

    session_id: Optional[str]
    verify_url: Optional[str]
    highlight_note: Optional[str]
    consent_ok: bool = True

    def to_tags(self) -> list[list[str]]:
        tags: list[list[str]] = [
            [QORTROLLER_TAG, QORTROLLER_VERSION],
            [VSS_TAG, VSS_VERSION],
            [HIGHLIGHT_KIND_TAG, HIGHLIGHT_KIND_VALUE],
            [CONSENT_OK_TAG, CONSENT_OK_TRUE],
        ]
        if self.session_id:
            tags.append([SESSION_ID_TAG, self.session_id])
        if self.verify_url:
            tags.append([VERIFY_URL_TAG, self.verify_url])
        if self.highlight_note:
            tags.append([HIGHLIGHT_NOTE_TAG, self.highlight_note])
        return tags

    def to_content(self) -> str:
        parts = ["vss highlight"]
        if self.session_id:
            parts.append(f"session: {self.session_id}")
        if self.verify_url:
            parts.append(f"verify: {self.verify_url}")
        if self.highlight_note:
            parts.append(f"note: {self.highlight_note}")
        parts.append("consent=true")
        return " | ".join(parts)


def build_highlight_event(
    *,
    consent_ok: bool,
    session_id: Optional[str] = None,
    verify_url: Optional[str] = None,
    highlight_note: Optional[str] = None,
    use_default_verify_pointer: bool = False,
) -> HighlightEvent:
    """Build a highlight/verify pointer. Raises if consent missing or content invalid.

    Fail-closed: consent_ok must be True. At least one of verify_url,
    highlight_note, or use_default_verify_pointer must be set.
    """
    if not consent_ok:
        raise ValueError(
            "consent_ok required (S3: highlight/verify pointer is consent-gated; "
            "never auto-publish)"
        )

    if session_id is not None and not str(session_id).strip():
        session_id = None
    if highlight_note is not None:
        highlight_note = str(highlight_note).strip()
        if not highlight_note:
            highlight_note = None
        elif len(highlight_note) > MAX_HIGHLIGHT_CHARS:
            raise ValueError(
                f"highlight_note max {MAX_HIGHLIGHT_CHARS} chars, got {len(highlight_note)}"
            )
        else:
            _check_forbidden(highlight_note)

    if use_default_verify_pointer and not verify_url:
        verify_url = DEFAULT_VERIFY_POINTER
    if verify_url is not None:
        verify_url = str(verify_url).strip()
        if not verify_url:
            verify_url = None
        elif len(verify_url) > MAX_VERIFY_URL_CHARS:
            raise ValueError(
                f"verify_url max {MAX_VERIFY_URL_CHARS} chars, got {len(verify_url)}"
            )
        else:
            _check_forbidden(verify_url)

    if session_id:
        _check_forbidden(session_id)

    if not verify_url and not highlight_note:
        raise ValueError(
            "need highlight_note and/or verify_url "
            "(or use_default_verify_pointer=True)"
        )

    return HighlightEvent(
        session_id=session_id,
        verify_url=verify_url,
        highlight_note=highlight_note,
        consent_ok=True,
    )


def validate_highlight_event(tags: list[list[str]], content: str = "") -> list[str]:
    """Validate highlight tags/content. Empty list = valid."""
    errors: list[str] = []
    tag_map: dict[str, str] = {}
    for tag in tags:
        if not isinstance(tag, list) or len(tag) < 2:
            errors.append(f"malformed tag: {tag}")
            continue
        tag_map[tag[0]] = tag[1]

    if tag_map.get(QORTROLLER_TAG) != QORTROLLER_VERSION:
        errors.append("missing or wrong qortroller tag")
    if tag_map.get(VSS_TAG) != VSS_VERSION:
        errors.append("missing or wrong vss tag")
    if tag_map.get(HIGHLIGHT_KIND_TAG) != HIGHLIGHT_KIND_VALUE:
        errors.append("vss_event must be 'highlight'")
    if tag_map.get(CONSENT_OK_TAG) != CONSENT_OK_TRUE:
        errors.append("consent_ok must be 'true' (S3 consent gate)")

    if VERIFY_URL_TAG not in tag_map and HIGHLIGHT_NOTE_TAG not in tag_map:
        errors.append("need verify_url and/or highlight_note")

    full = content + " " + " ".join(tag_map.values())
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in full.lower():
            errors.append(f"forbidden pattern: '{pattern}'")

    return errors


def format_verify_pointer_digest(
    *,
    session_id: Optional[str] = None,
    verify_url: Optional[str] = None,
) -> str:
    """READ-only digest for ACP: how a stranger can verify (no consent needed to display)."""
    parts = ["verify-pointer"]
    if session_id:
        parts.append(f"session: {session_id}")
    url = (verify_url or DEFAULT_VERIFY_POINTER).strip()
    parts.append(f"pointer: {url}")
    parts.append("consent-gated to publish; this line is display-only")
    return " | ".join(parts)
