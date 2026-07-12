"""TRA-1 T6.4 - PoSP retina_perception_root join (standard, F-TRA0-1 ordered).

Produces the STANDARD ``retina_perception_root`` for the session PoSP (``l9_presence.posp.build_posp``):
the ORDERED conformant retina.event/0.1 Poseidon root (F-TRA0-1) over the T6.1 event stream - the
OBSERVATION side of the PoSP's two NAMED roots.

ADDITIVE: it does NOT change the LUMEN-4a ``roll_perception_root`` engine (a shared dual-consumer
engine with the M14 regression anchor, which rolls a ``sha256_v1`` UNORDERED root). Switching the
daemon's issued PoSP from that candidate to this standard root is T6.6 + an operator decision under
the dual-consumer regression discipline - never autonomous.

§2.3 rail (the load-bearing disambiguation): ``retina_perception_root`` is a NAMED PARALLEL root - the
OBSERVATION side - NEVER conflated with the ASSERTION-plane ``kas_session_root``. Honest null: an
empty event stream yields None (no fabricated root), matching the LUMEN-4a fail-open discipline.

OBSERVATION-plane only. No PoAC / 228B / ASSERTION-plane / chain contact.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .retina_event_std import ordered_events_root

PERCEPTION_ROOT_SCHEME = "poseidon_ordered_v1"   # vs the LUMEN-4a candidate's sha256_v1


def standard_perception_root(events: Sequence[Mapping[str, Any]], *, chain_fn=None) -> Optional[str]:
    """The STANDARD retina_perception_root: the ORDERED conformant retina.event/0.1 Poseidon root
    (F-TRA0-1) over the stream, hex. Empty stream -> None (honest null, never fabricated). Validates
    the stream (conformance + separation law) via ordered_events_root -> raises on an illegal event."""
    if not events:
        return None
    return ordered_events_root(events, chain_fn=chain_fn).hex()


def posp_retina_join(session_id: Optional[str], events: Sequence[Mapping[str, Any]], *,
                     v3_commitment: Optional[str] = None, chain_fn=None) -> dict:
    """The OBSERVATION-plane retina fields for the session PoSP, keyed by ``session_id``: the standard
    (ordered) ``retina_perception_root`` + its scheme, plus - advisory - the T6.3 v3 commitment as a
    NAMED PARALLEL reference. Contains NO assertion field (no ``kas_session_root``) by construction: it
    is only the observation side of §2.3. Feed ``retina_perception_root`` into ``build_posp(...)``."""
    return {
        "session_id": session_id,
        "retina_perception_root": standard_perception_root(events, chain_fn=chain_fn),
        "retina_perception_root_scheme": PERCEPTION_ROOT_SCHEME,
        "retina_state_v3_commitment": v3_commitment,     # advisory named-parallel ref (T6.3); may be None
    }
