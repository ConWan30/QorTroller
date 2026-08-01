"""VSS-S5 — Organizer pilot room (seat + pin + portcert) composition.

Scope later-spine S5 (after VSS-6): bind the three organizer surfaces into
one digest checklist without conflating planes:

  Buzz social:  #streams seat + optional #matches pin event id
  QorTroller:   eligibility + session_id (truth)
  Verify:       public portcert command pointer (G5-VER)

Composition only — does not pin the canvas itself, does not spend chain,
does not invent eligibility or pin ids. Optional publish is consent-gated
(gamer/operator --consent-ok), same discipline as S3 highlights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from vapi_bridge.vss_seat_schema import (
    FORBIDDEN_PATTERNS,
    QORTROLLER_TAG,
    QORTROLLER_VERSION,
    VSS_TAG,
    VSS_VERSION,
    _check_forbidden,
)
from vapi_bridge.vss_highlight import DEFAULT_VERIFY_POINTER

PILOT_EVENT_TAG = "vss_event"
PILOT_EVENT_VALUE = "organizer_pilot"
SESSION_ID_TAG = "session_id"
PIN_EVENT_TAG = "pin_event_id"
MEDIA_URL_TAG = "media_url"
VERIFY_URL_TAG = "verify_url"
STREAMS_CHANNEL_TAG = "streams_channel"
MATCHES_CHANNEL_TAG = "matches_channel"
SEAT_ELIGIBLE_TAG = "seat_eligible"
CONSENT_OK_TAG = "consent_ok"

DEFAULT_PORTCERT_CMD = DEFAULT_VERIFY_POINTER


@dataclass
class PilotInputs:
    """Inputs for an organizer pilot digest (all optional except honesty)."""

    seat_eligible: Optional[bool] = None
    session_id: Optional[str] = None
    media_url: Optional[str] = None
    pin_event_id: Optional[str] = None
    streams_channel: Optional[str] = None
    matches_channel: Optional[str] = None
    portcert_cmd: str = DEFAULT_PORTCERT_CMD


@dataclass
class PilotChecklist:
    """Machine + human checklist for organizer pilot readiness."""

    seat_ok: bool
    session_bound: bool
    pin_present: bool
    verify_pointer_present: bool
    ready: bool
    missing: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class PilotEvent:
    inputs: PilotInputs
    checklist: PilotChecklist
    consent_ok: bool = True

    def to_tags(self) -> list[list[str]]:
        tags: list[list[str]] = [
            [QORTROLLER_TAG, QORTROLLER_VERSION],
            [VSS_TAG, VSS_VERSION],
            [PILOT_EVENT_TAG, PILOT_EVENT_VALUE],
            [CONSENT_OK_TAG, "true"],
            [
                SEAT_ELIGIBLE_TAG,
                (
                    "unknown"
                    if self.inputs.seat_eligible is None
                    else ("true" if self.inputs.seat_eligible else "false")
                ),
            ],
        ]
        i = self.inputs
        if i.session_id:
            tags.append([SESSION_ID_TAG, i.session_id])
        if i.pin_event_id:
            tags.append([PIN_EVENT_TAG, i.pin_event_id])
        if i.media_url:
            tags.append([MEDIA_URL_TAG, i.media_url])
        if i.portcert_cmd:
            tags.append([VERIFY_URL_TAG, i.portcert_cmd])
        if i.streams_channel:
            tags.append([STREAMS_CHANNEL_TAG, i.streams_channel])
        if i.matches_channel:
            tags.append([MATCHES_CHANNEL_TAG, i.matches_channel])
        return tags

    def to_content(self) -> str:
        c = self.checklist
        parts = [
            "vss organizer-pilot",
            f"ready={'yes' if c.ready else 'no'}",
            f"seat={'ok' if c.seat_ok else 'down/unknown'}",
            f"session={'bound' if c.session_bound else 'absent'}",
            f"pin={'yes' if c.pin_present else 'absent'}",
            f"portcert={'yes' if c.verify_pointer_present else 'absent'}",
        ]
        if self.inputs.session_id:
            parts.append(f"session_id: {self.inputs.session_id}")
        if self.inputs.pin_event_id:
            pe = self.inputs.pin_event_id
            parts.append(f"pin_event: {pe[:16]}…")
        if self.inputs.media_url:
            parts.append(f"media: {self.inputs.media_url}")
        parts.append(f"verify: {self.inputs.portcert_cmd}")
        if c.missing:
            parts.append("missing: " + ",".join(c.missing))
        parts.append("consent=true")
        return " | ".join(parts)


def build_checklist(inputs: PilotInputs) -> PilotChecklist:
    """Compute organizer pilot readiness without fabricating evidence."""
    missing: list[str] = []
    seat_ok = inputs.seat_eligible is True
    if inputs.seat_eligible is None:
        missing.append("seat_eligibility")
    elif not inputs.seat_eligible:
        missing.append("seat_not_eligible")

    session_bound = bool(inputs.session_id and str(inputs.session_id).strip())
    if not session_bound:
        missing.append("session_id")

    pin_present = bool(inputs.pin_event_id and str(inputs.pin_event_id).strip())
    if not pin_present:
        missing.append("pin_event_id")

    verify_pointer_present = bool(
        inputs.portcert_cmd and str(inputs.portcert_cmd).strip()
    )
    if not verify_pointer_present:
        missing.append("portcert_pointer")

    # Pilot "ready" = seat eligible + session bound + verify pointer.
    # Pin is recommended but not required for a pilot room to open
    # (pin may land after the match postcard exists).
    ready = seat_ok and session_bound and verify_pointer_present
    summary_bits = [
        f"organizer-pilot ready={ready}",
        f"seat_ok={seat_ok}",
        f"session_bound={session_bound}",
        f"pin_present={pin_present}",
        f"portcert={verify_pointer_present}",
    ]
    if missing:
        summary_bits.append("missing=" + ",".join(missing))
    return PilotChecklist(
        seat_ok=seat_ok,
        session_bound=session_bound,
        pin_present=pin_present,
        verify_pointer_present=verify_pointer_present,
        ready=ready,
        missing=missing,
        summary=" | ".join(summary_bits),
    )


def build_pilot_event(
    *,
    consent_ok: bool,
    inputs: PilotInputs,
) -> PilotEvent:
    """Build a publishable organizer pilot digest. Consent required."""
    if not consent_ok:
        raise ValueError(
            "consent_ok required (S5: organizer pilot digest is consent-gated)"
        )

    # Scrub string fields
    for name in (
        "session_id",
        "media_url",
        "pin_event_id",
        "streams_channel",
        "matches_channel",
        "portcert_cmd",
    ):
        val = getattr(inputs, name)
        if val is None:
            continue
        s = str(val).strip()
        if not s:
            setattr(inputs, name, None)
            continue
        _check_forbidden(s)
        setattr(inputs, name, s)

    if not inputs.portcert_cmd:
        inputs.portcert_cmd = DEFAULT_PORTCERT_CMD

    checklist = build_checklist(inputs)
    return PilotEvent(inputs=inputs, checklist=checklist, consent_ok=True)


def validate_pilot_event(tags: list[list[str]], content: str = "") -> list[str]:
    errors: list[str] = []
    tag_map: dict[str, str] = {}
    for tag in tags:
        if not isinstance(tag, list) or len(tag) < 2:
            errors.append(f"malformed tag: {tag}")
            continue
        tag_map[tag[0]] = tag[1]

    if tag_map.get(QORTROLLER_TAG) != QORTROLLER_VERSION:
        errors.append("missing/wrong qortroller")
    if tag_map.get(VSS_TAG) != VSS_VERSION:
        errors.append("missing/wrong vss")
    if tag_map.get(PILOT_EVENT_TAG) != PILOT_EVENT_VALUE:
        errors.append("vss_event must be organizer_pilot")
    if tag_map.get(CONSENT_OK_TAG) != "true":
        errors.append("consent_ok must be true")

    full = content + " " + " ".join(tag_map.values())
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in full.lower():
            errors.append(f"forbidden pattern: {pattern}")
    return errors


def pilot_from_eligibility(
    elig: Optional[dict[str, Any]],
    *,
    session_id: Optional[str] = None,
    media_url: Optional[str] = None,
    pin_event_id: Optional[str] = None,
    streams_channel: Optional[str] = None,
    matches_channel: Optional[str] = None,
    portcert_cmd: str = DEFAULT_PORTCERT_CMD,
) -> PilotChecklist:
    """Build checklist from VSS-1 eligibility + organizer fields (no publish)."""
    seat_eligible: Optional[bool]
    if elig is None:
        seat_eligible = None
    else:
        seat_eligible = bool(elig.get("eligible", False))
    return build_checklist(
        PilotInputs(
            seat_eligible=seat_eligible,
            session_id=session_id,
            media_url=media_url,
            pin_event_id=pin_event_id,
            streams_channel=streams_channel,
            matches_channel=matches_channel,
            portcert_cmd=portcert_cmd,
        )
    )


def organizer_commands(
    *,
    session_id: Optional[str] = None,
    media_url: Optional[str] = None,
    pin_event_id: Optional[str] = None,
) -> list[str]:
    """Fixed command templates organizers can run (shell=False friendly argv docs)."""
    cmds = [
        "python scripts/buzz_vss_seat.py --media-url <url> --session-id <sid>",
        "python scripts/buzz_pin_match.py <postcard_event_id>",
        "python scripts/portcert_full_verify.py",
        "python scripts/buzz_vss_highlight.py --consent-ok --default-verify-pointer --session-id <sid>",
        "python scripts/buzz_vss_organizer_pilot.py --consent-ok --session-id <sid>",
    ]
    if session_id:
        cmds[0] = (
            f"python scripts/buzz_vss_seat.py --media-url "
            f"{media_url or '<url>'} --session-id {session_id}"
        )
        cmds[3] = (
            f"python scripts/buzz_vss_highlight.py --consent-ok "
            f"--default-verify-pointer --session-id {session_id}"
        )
        cmds[4] = (
            f"python scripts/buzz_vss_organizer_pilot.py --consent-ok "
            f"--session-id {session_id}"
        )
    if pin_event_id:
        cmds[1] = f"python scripts/buzz_pin_match.py {pin_event_id}"
    return cmds
