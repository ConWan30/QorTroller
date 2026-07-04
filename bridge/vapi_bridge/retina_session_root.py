"""Retina session events_root unification (Increment B, Phase B2).

ONE events_root per session window over BOTH lobes — the screen-outcome events (killfeed AUTHORED, tagged
kind="outcome") AND the HID-input events (kind="input") — via the EXISTING
retina_state_commitment.compute_events_root (canonical sorted-line SHA-256, sha256_v1). NO new frozen tag is
minted here: this is OPERATIONAL infrastructure; a v-freeze of the unified schema is an explicit later
decision. NO chain write / DA submission — the DA-witness path stays a named destination.

The KAS certificate references this root, upgrading its claim from "authorship evidence existed this session"
to "these kill outcomes were bound to this HID commitment chain in this window." The root is order-INDEPENDENT
(compute_events_root sorts canonical lines) and deterministic (re-derive -> identical), so a verifier with the
event set can reproduce it.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .retina_events_root import EVENTS_ROOT_SCHEME_SHA256_V1
from .retina_state_commitment import compute_events_root_for_scheme

LOBE_SCREEN = "screen"
LOBE_HID = "hid"


def _tag_lobe(events: Sequence[Mapping[str, Any]], lobe: str) -> list[dict]:
    """Copy each event with a `lobe` field so the two lobes never collide in the canonical line set."""
    return [{**dict(e), "lobe": lobe} for e in (events or [])]


def unify_session_events_root(screen_events: Optional[Sequence[Mapping[str, Any]]] = None,
                              hid_events: Optional[Sequence[Mapping[str, Any]]] = None,
                              scheme: str = EVENTS_ROOT_SCHEME_SHA256_V1) -> dict:
    """Combine both lobes' events -> one events_root. Returns {events_root(hex), scheme, lobes, n_screen,
    n_hid}. lobes lists which lobes actually contributed (so a screen-only session is honestly labelled)."""
    screen = _tag_lobe(screen_events or [], LOBE_SCREEN)
    hid = _tag_lobe(hid_events or [], LOBE_HID)
    combined = screen + hid
    root = compute_events_root_for_scheme(combined, scheme=scheme)
    lobes = []
    if screen:
        lobes.append(LOBE_SCREEN)
    if hid:
        lobes.append(LOBE_HID)
    return {"events_root": root.hex(), "scheme": scheme, "lobes": lobes,
            "n_screen": len(screen), "n_hid": len(hid)}
