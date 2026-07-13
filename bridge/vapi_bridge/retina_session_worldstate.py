"""TRA-1 T6.2 - session WorldState assembler from live observation.

Assembles a conformant `retina.event/0.1` WorldState (`retina_worldstate_std`) for a capture
session: the certified controller as a locus-only FIELD SUBJECT (the QorTroller fusion piece),
plus any video/perception entities (added when the T6.5 trio-retina encoder lands). Kill activity
lives in the PARALLEL retina.event stream (T6.1 `kill_events_from_rows`), NOT in the WorldState -
events and latent state are the two separate encoder outputs the v3 commitment (T6.3) binds.

Honest ASSERTION-plane gate: the controller's input locus is the phi-quantized coarse
stick/trigger position, sourced from the controller HID. While BT-paired to the console the USB HID
can be blind (dual-connection), so the caller passes ``input_locus=None`` (no controller entity -
an honest omission) or the documented ``PRESENCE_LOCUS`` marker. Never a fabricated live reading.

OBSERVATION-plane only. No PoAC / 228B / ASSERTION-plane / chain contact. Both rails are enforced:
`make_worldstate`/`make_entity` cover top-level + entities, and this assembler additionally guards
the nested ``scene`` (which the T2 primitive does not scan) against the biometric floor + the
separation law.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .retina_event_std import _ASSERTING_FIELDS
from .retina_worldstate_std import _FORBIDDEN_BIOMETRIC, controller_entity, make_worldstate

DEFAULT_SRC = "retina.session"
# A caller MAY mark "controller present, no live input reading" with this input-space-origin locus.
# It is a PRESENCE marker, NOT a measured stick/trigger position - use only when the HID is blind.
PRESENCE_LOCUS = (0.0, 0.0)


def _scene_forbidden_keys(scene: Optional[Mapping[str, Any]]) -> list[str]:
    """Shallow guard: scene is flat observation metadata; reject any biometric-floor or asserting
    key (the T2 primitive scans top-level + entities/relations, but not the nested scene)."""
    if not scene:
        return []
    return [k for k in scene if k in _FORBIDDEN_BIOMETRIC or k in _ASSERTING_FIELDS]


def worldstate_from_observation(t, *, src: str = DEFAULT_SRC, frame: Optional[int] = None,
                                controller_id: Any = None,
                                input_locus: Optional[Sequence[float]] = None,
                                video_entities: Sequence[Mapping[str, Any]] = (),
                                scene: Optional[Mapping[str, Any]] = None) -> dict:
    """Assemble the session WorldState. Adds the certified controller as a locus-only entity ONLY
    when both ``controller_id`` and a non-empty ``input_locus`` are given (honest omission when the
    HID is blind); passes through video/perception entities (T6.5). Fail-closed on both rails,
    including the nested ``scene``."""
    bad = _scene_forbidden_keys(scene)
    if bad:
        raise ValueError(f"scene carries forbidden field(s) (biometric floor / separation law): {bad}")
    entities = list(video_entities)
    if controller_id is not None and input_locus:
        entities.append(controller_entity(controller_id, input_locus=list(input_locus)))
    return make_worldstate(src, t, frame=frame, entities=entities, scene=scene)
