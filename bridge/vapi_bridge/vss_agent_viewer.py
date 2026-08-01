"""VSS-S1 — Agent viewer policy helpers (summarize + flag-down).

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §9 later-spine S1
and §4 (Who can open): agents may VIEW / summarize / flag a down seat;
they must never OPEN a gamer seat.

Pure functions over the VSS-1 eligibility dict. No Nostr signing, no
chain writes, no FROZEN wire, no gamer key handling.
"""
from __future__ import annotations

from typing import Any, Optional

# Machine-readable flag outcomes for ACP digests.
FLAG_DOWN = "FLAG_DOWN"
SEAT_OK = "SEAT_OK"
SEAT_UNKNOWN = "SEAT_UNKNOWN"

# Hard policy: agent viewers never open seats (VSS-7 / F3).
AGENT_CAN_OPEN = False


def agent_may_open_seat() -> bool:
    """Always False — humans open seats; agents view (scope §4 + S1)."""
    return AGENT_CAN_OPEN


def summarize_seat(elig: Optional[dict[str, Any]]) -> str:
    """Build a digest-only agent viewer summary from eligibility.

    Never fabricates eligibility. Bridge None → unknown, fail-closed wording.
    """
    if elig is None:
        return (
            "agent-view: stream seat UNKNOWN | bridge unreachable "
            "(fail-closed) | agents may READ only, cannot OPEN"
        )

    eligible = bool(elig.get("eligible", False))
    capture_up = bool(elig.get("capture_up", False))
    oracle = bool(elig.get("retina_oracle_running", False))
    reason = str(elig.get("reason_if_closed") or "").strip()
    honesty = elig.get("honesty") or {}

    state = "ELIGIBLE" if eligible else "DOWN"
    parts = [
        f"agent-view: stream seat {state}",
        f"capture: {'up' if capture_up else 'down'}",
        f"oracle: {'running' if oracle else 'stopped'}",
        f"poep={bool(honesty.get('poep_enabled', False))}",
        f"l6b={bool(honesty.get('l6b_enabled', False))}",
        f"candidate={bool(honesty.get('candidate_ok', False))}",
        "agents: READ-only (cannot OPEN)",
    ]
    if reason:
        parts.append(f"reason: {reason[:80]}")
    return " | ".join(parts)


def flag_seat_down(elig: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Agent flag-down decision for a stream seat.

    Returns a small dict:
      flag: FLAG_DOWN | SEAT_OK | SEAT_UNKNOWN
      should_flag: bool
      summary: digest string
    """
    if elig is None:
        return {
            "flag": SEAT_UNKNOWN,
            "should_flag": False,  # cannot assert DOWN without data
            "eligible": None,
            "summary": (
                "agent-flag: UNKNOWN | bridge unreachable "
                "(fail-closed — do not invent DOWN)"
            ),
        }

    eligible = bool(elig.get("eligible", False))
    capture_up = bool(elig.get("capture_up", False))
    oracle = bool(elig.get("retina_oracle_running", False))
    reason = str(elig.get("reason_if_closed") or "").strip()

    if eligible:
        return {
            "flag": SEAT_OK,
            "should_flag": False,
            "eligible": True,
            "capture_up": capture_up,
            "oracle_running": oracle,
            "summary": (
                "agent-flag: SEAT_OK | capture up + oracle running "
                "| no flag (agents cannot OPEN)"
            ),
        }

    # Ineligible → agent may flag down (view-only signal)
    why = reason[:80] if reason else (
        f"capture={'up' if capture_up else 'down'}; "
        f"oracle={'running' if oracle else 'stopped'}"
    )
    return {
        "flag": FLAG_DOWN,
        "should_flag": True,
        "eligible": False,
        "capture_up": capture_up,
        "oracle_running": oracle,
        "summary": f"agent-flag: FLAG_DOWN | {why} | agents READ-only (cannot OPEN)",
    }
