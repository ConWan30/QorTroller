"""Bridge-context lull source: reuse the protocol's own gameplay classifier (pure logic).

The IMU lull-gate (probe_gate.py) decides "is the controller physically quiet right now."
This adds a SECOND, semantic opinion from the running bridge: it already classifies the
live session via Phase 241-APOP (5-state) and Phase 235-GAD (ACTIVE_GAMEPLAY/MENU_DETECTED).
Asking the bridge "are we between plays" is richer than inferring it from raw input, and it
reuses intelligence that's already tested and on-chain-attested in the grind path.

This module is PURE: it maps a bridge status dict -> a ContextVerdict. The challenger does
the HTTP fetch at the edge and stays tolerant (bridge unreachable -> context inert, fall
back to the IMU gate; never block the probe loop on a missing bridge).

APOP 5-state (active_play_occupancy.py) -> verdict:
  ACTIVE_MATCH_PLAY / COMPETITIVE_CONTROL -> ACTIVE   (live play; defer)
  MATCH_TRANSITION                        -> IN_MATCH_LULL (between plays; ideal probe window)
  NON_COMPETITIVE_MENU                    -> MENU       (quiet but not in-match)
  UNKNOWN_LOW_EVIDENCE / missing          -> UNKNOWN    (defer; fail-safe)
GAD fallback when no APOP state present:
  ACTIVE_GAMEPLAY -> ACTIVE ; MENU_DETECTED -> MENU ; missing -> UNKNOWN
"""
from __future__ import annotations

from enum import Enum


class ContextVerdict(str, Enum):
    IN_MATCH_LULL = "IN_MATCH_LULL"  # between-plays in a live match -> ideal probe window
    MENU = "MENU"                    # non-competitive menu -> quiet, but not in-match
    ACTIVE = "ACTIVE"                # live play -> defer
    UNKNOWN = "UNKNOWN"              # low evidence / no data -> defer (fail-safe)


_APOP_MAP = {
    "ACTIVE_MATCH_PLAY": ContextVerdict.ACTIVE,
    "COMPETITIVE_CONTROL": ContextVerdict.ACTIVE,
    "MATCH_TRANSITION": ContextVerdict.IN_MATCH_LULL,
    "NON_COMPETITIVE_MENU": ContextVerdict.MENU,
    "UNKNOWN_LOW_EVIDENCE": ContextVerdict.UNKNOWN,
}
_GAD_MAP = {
    "ACTIVE_GAMEPLAY": ContextVerdict.ACTIVE,
    "MENU_DETECTED": ContextVerdict.MENU,
}


def classify_context(status: dict | None) -> ContextVerdict:
    """Map a bridge status dict (APOP status or capture-health) -> ContextVerdict.

    Prefers the APOP `latest_state` (5-state, richest); falls back to the GAD
    `latest_gameplay_context`. None/empty/unrecognised -> UNKNOWN (caller defers)."""
    if not status:
        return ContextVerdict.UNKNOWN
    apop = status.get("latest_state")
    if apop in _APOP_MAP:
        return _APOP_MAP[apop]
    gad = status.get("latest_gameplay_context")
    if gad in _GAD_MAP:
        return _GAD_MAP[gad]
    return ContextVerdict.UNKNOWN


def clear_to_fire_context(status: dict | None, *, allow_menu: bool = False) -> tuple[bool, ContextVerdict]:
    """True when the bridge context is a good probe window.

    Strict (default): only IN_MATCH_LULL (between plays in a live match) -- the window the
    consistency experiment actually wants. Lenient (allow_menu=True): also accept MENU as a
    collision-safe quiet window. Returns (clear, verdict) so the caller can log WHY."""
    v = classify_context(status)
    clear = v is ContextVerdict.IN_MATCH_LULL or (allow_menu and v is ContextVerdict.MENU)
    return clear, v
