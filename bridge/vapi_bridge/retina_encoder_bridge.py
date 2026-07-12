"""TRA-1 T6.5 - trio-retina encoder bridge (adopt the REAL MachineFi encoder standard).

Wires the real ``machinefi/trio-retina`` library (import name ``retina``; Apache-2.0;
``pip install trio-retina``; core is numpy-only) THROUGH QorTroller's validate+canonicalize+commit
boundary (T6.1-6.3), per the T5 Option C decision. Two seams:

  * ``cross_validate(event)`` - validate a QorTroller ``retina.event/0.1`` event against BOTH our
    stdlib validator + separation law AND the REAL ``retina.validate()`` when the library is present
    (verified 2026-07-12: our events pass the real validator unmodified - the reimplementation is
    faithful). Also guards the standard's ``ext`` extension for asserting fields (our top-level
    separation-law scan does not reach nested ext).
  * ``event_from_trio`` / ``worldstate_from_trio`` - convert the encoder's ``Event`` / ``WorldState``
    dataclass output into QorTroller dicts that flow through our rails + commit (T6.1/T6.2/T6.3).

The HEAVY perception encoders (``YoloDetector`` / ``DinoV2Embedder`` / ``VJepa2Embedder`` -> the
``[yolo]``/``[dino]``/``[vjepa]``/``[video]`` extras: torch / opencv / ultralytics) are NOT imported
or run here - they are CARD-GATED (they need live frames + the heavy supply-chain surface). This is
the light seam; running the encoder over live capture is T6.6.

``trio-retina`` is an OPTIONAL dependency: absent -> the bridge degrades gracefully (our own
validator governs; the real-validate leg is skipped). OBSERVATION-plane only; no PoAC/228B/chain.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Mapping, Optional, Sequence

from .retina_event_std import _ASSERTING_FIELDS, separation_law_problems, validate_event
from .retina_session_worldstate import worldstate_from_observation
from .retina_worldstate_std import make_entity


def trio_retina_available() -> bool:
    """True iff the real trio-retina library (``retina``) is importable."""
    try:
        import retina  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _real_validate(event: Mapping[str, Any]) -> list[str]:
    """Problems from the REAL ``retina.validate()``, or [] if the library is absent (our validator
    still governs) / errors (reported, never raised)."""
    try:
        import retina
    except Exception:  # noqa: BLE001
        return []
    try:
        return list(retina.validate(dict(event)))
    except Exception as exc:  # noqa: BLE001
        return [f"real retina.validate error: {exc!r}"]


def _ext_asserting(event: Mapping[str, Any]) -> list[str]:
    """Guard the standard's ``ext`` extension against asserting fields (the top-level separation-law
    scan does not reach nested ext)."""
    ext = event.get("ext")
    if isinstance(ext, Mapping):
        return [f"ext.{k!r}: asserting field forbidden on the OBSERVATION plane" for k in ext
                if k in _ASSERTING_FIELDS]
    return []


def cross_validate(event: Mapping[str, Any]) -> list[str]:
    """Conformance against EVERY governor: QorTroller's validator + separation law (+ ext guard) AND
    the REAL trio-retina ``retina.validate()`` when installed. [] == valid on all."""
    return (validate_event(event) + separation_law_problems(event)
            + _ext_asserting(event) + _real_validate(event))


def _omit_empty(d: Mapping[str, Any]) -> dict:
    return {k: v for k, v in d.items() if v is not None and v != "" and v != [] and v != {}}


def event_from_trio(ev: Any) -> dict:
    """Convert a trio-retina ``Event`` (dataclass) into a QorTroller ``retina.event/0.1`` dict
    (omit-empty), guarded by every governor. Raises ValueError on a non-conformant / asserting event
    - the encoder's output is checked BEFORE it enters our boundary."""
    d = _omit_empty(dataclasses.asdict(ev) if dataclasses.is_dataclass(ev) else dict(ev))
    problems = cross_validate(d)
    if problems:
        raise ValueError(f"trio-retina event not conformant at our boundary: {problems[:5]}")
    return d


def worldstate_from_trio(ws: Any, *, controller_id: Any = None,
                         input_locus: Optional[Sequence[float]] = None) -> dict:
    """Convert a trio-retina ``WorldState`` (dataclass) into a QorTroller WorldState dict: its video
    entities (``bbox`` + model-tagged ``vec``) pass through ``make_entity`` (biometric-floor +
    separation-law guarded), and the certified controller is ADDED as a locus-only entity (T6.2
    fusion) when an input locus is available. Raises on any rail breach."""
    raw = dataclasses.asdict(ws) if dataclasses.is_dataclass(ws) else dict(ws)
    video_entities = []
    for ent in raw.get("entities") or []:
        e = _omit_empty(ent)
        extra = {k: v for k, v in (e.get("attrs") or {}).items()}
        if e.get("conf") is not None:
            extra["conf"] = e["conf"]
        video_entities.append(make_entity(e.get("id"), e.get("type"),
                                          bbox=e.get("bbox"), vec=e.get("vec"), **extra))
    return worldstate_from_observation(
        raw.get("t"), src=raw.get("src") or "retina.session", frame=raw.get("frame"),
        controller_id=controller_id, input_locus=input_locus, video_entities=video_entities)
