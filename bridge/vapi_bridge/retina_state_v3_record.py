"""TRA-1 T6.3 - per-session VAPI-RETINA-STATE-v3 record (the FROZEN verify-rung over a session).

Binds the ORDERED retina.event/0.1 stream (T6.1 `kill_events_from_rows`) and the session WorldState
(T6.2 `worldstate_from_observation`) into one per-session record carrying the FROZEN-v1
``VAPI-RETINA-STATE-v3`` commitment (INV-RETINA-STATE-V3):

    commitment = SHA-256( VAPI-RETINA-STATE-v3 || device(32) || ts_ns_be(8)
                          || ordered_events_root(32) || worldstate_digest(32) )

The record is **self-verifying**: it carries both component roots (so the commitment recomputes from
the record) and, by default, the replayable event stream + WorldState (so the roots recompute too).
`compute_retina_state_commitment_v3` fail-closes on a non-conformant/asserting event stream or a
biometric-floor/asserting WorldState - the record cannot be built over an illegal state.

OBSERVATION-plane only. No PoAC / 228B / ASSERTION-plane / chain contact. The v3 FORMULA IS FROZEN
(`retina_state_commitment`) - this only assembles a record around it; it does not touch the bytes.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .retina_event_std import ordered_events_root
from .retina_state_commitment import (
    DOMAIN_TAG_V3, compute_retina_state_commitment_v3, compute_worldstate_digest,
)

SCHEMA = "qortroller-retina-state-v3"


def build_retina_state_v3_record(device_id_hex: str, ts_ns: int,
                                 events: Sequence[Mapping[str, Any]],
                                 worldstate: Optional[Mapping[str, Any]] = None, *,
                                 chain_fn=None, embed: bool = True) -> dict:
    """Assemble the per-session v3 state record. Fail-closes (ValueError) on a non-conformant event
    stream or WorldState (both rails, via the FROZEN primitive). `embed=True` includes the replayable
    events + WorldState so the record is fully self-verifying; `embed=False` keeps roots + commitment
    only."""
    # The FROZEN primitive validates BOTH rails and computes both roots internally; it raises on any
    # illegal state, so nothing is emitted for a non-conformant session.
    commitment = compute_retina_state_commitment_v3(
        device_id_hex, ts_ns, events, worldstate=worldstate, chain_fn=chain_fn)
    events_root = ordered_events_root(events, chain_fn=chain_fn, validate=False)  # already validated above
    ws_digest = compute_worldstate_digest(worldstate)
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "domain": DOMAIN_TAG_V3.decode("ascii"),
        "device_id": device_id_hex,
        "ts_ns": int(ts_ns),
        "ordered_events_root": events_root.hex(),
        "worldstate_digest": ws_digest.hex(),
        "commitment": commitment,
        "n_events": len(events),
    }
    if embed:
        record["events"] = [dict(e) for e in events]
        record["worldstate"] = dict(worldstate) if worldstate else None
    return record


def verify_retina_state_v3_record(record: Mapping[str, Any], *, chain_fn=None) -> bool:
    """Recompute the v3 commitment from the record's EMBEDDED events + WorldState and check it matches
    ``record['commitment']``. Requires an ``embed=True`` record; False on missing fields / mismatch /
    any error (never raises)."""
    try:
        events = record.get("events")
        if events is None:
            return False
        recomputed = compute_retina_state_commitment_v3(
            record["device_id"], record["ts_ns"], events,
            worldstate=record.get("worldstate"), chain_fn=chain_fn)
        return recomputed == record.get("commitment")
    except Exception:  # noqa: BLE001 - a verifier reports False, never raises
        return False
