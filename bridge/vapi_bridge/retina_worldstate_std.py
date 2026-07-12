"""TRA-1 T2 - `retina.event/0.1` WorldState assembler + controller-sensor fusion (`locus`/`vec`).

Expresses QorTroller's multi-modal fusion in MachineFi Trio Retina's OWN `WorldState` schema:
video entities carry `bbox` (pixels); the certified controller carries `locus` - a metric
position in INPUT space (the standard's typed home for non-bbox field signals, SPEC.md 0.2+:
"CSI, radar, lidar, GPS"). The `vec` latent channel is populated by VISION (model-tagged ReID /
V-JEPA embeddings), never by the controller. Audio stays dropped (BIPA/GDPR sovereignty).

Two honesty rails on the exportable state:
  * separation law (T4): no asserting/humanity field (reused from ``retina_event_std``).
  * biometric floor: the anti-cheat MOAT never enters the exportable WorldState. The FROZEN
    `pre_processor.FORBIDDEN_COLUMNS` (INV-VHR-004) are refused as keys; the controller carries
    only its phi-quantized coarse `locus` and NO `vec` (a controller latent would be
    biometric-adjacent).

OBSERVATION-plane only. No PoAC / 228B wire / ASSERTION-plane / chain contact.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .retina_event_std import separation_law_problems

# Mirror of pre_processor.FORBIDDEN_COLUMNS (data floor, INV-VHR-004) - the biometric moat that
# must never enter the exportable OBSERVATION WorldState. A test pins this in sync with source.
_FORBIDDEN_BIOMETRIC = frozenset({
    "l4_mahalanobis_distance", "l4_vector", "l4_feature_0",
    "l5_cv", "l5_entropy", "l5_quantization",
    "e4_spectral_entropy", "e4_band_power",
    "ait_rms", "ait_variance", "grip_asymmetry",
    "micro_tremor_variance", "press_timing_jitter_variance",
    "trigger_onset_velocity_l2", "trigger_onset_velocity_r2",
    "stick_autocorr_lag1", "stick_autocorr_lag5",
    "accel_tremor_peak_hz", "tremor_band_power",
    "accel_magnitude_spectral_entropy",
})

_VEC_DTYPES = frozenset({"fp32", "fp16", "int8", "uint8"})


def make_vec(model: str, dim: int, *, dtype: str = "fp32", values: Sequence[float] = None,
             ref: str = None) -> dict:
    """A model-tagged latent (SPEC: always tag `{model, dim, dtype}`); EXACTLY one of inline
    `values` or by-reference `ref`. The tag says what produced it - a FaceNet-128 and a
    V-JEPA-1024 can't share an index."""
    if not model or not isinstance(model, str):
        raise ValueError("vec.model must be a non-empty string")
    if not isinstance(dim, int) or isinstance(dim, bool) or dim <= 0:
        raise ValueError("vec.dim must be a positive int")
    if dtype not in _VEC_DTYPES:
        raise ValueError(f"vec.dtype must be one of {sorted(_VEC_DTYPES)}")
    if (values is None) == (ref is None):
        raise ValueError("vec must carry exactly one of inline 'values' or by-reference 'ref'")
    vec: dict[str, Any] = {"model": model, "dim": dim, "dtype": dtype}
    if values is not None:
        if len(values) != dim:
            raise ValueError(f"vec.values length {len(values)} != dim {dim}")
        vec["values"] = list(values)
    else:
        vec["ref"] = ref
    return vec


def _entity_structural_problems(ent: Mapping[str, Any]) -> list[str]:
    """Entity shape + biometric floor (NOT the separation law - the caller applies that once)."""
    problems: list[str] = []
    if not isinstance(ent, Mapping):
        return ["entity must be an object"]
    if not ent.get("id") or not ent.get("type"):
        problems.append("entity requires non-empty id + type")
    box = ent.get("bbox")
    if box is not None and (not isinstance(box, (list, tuple)) or len(box) != 4):
        problems.append("entity.bbox must be [x1,y1,x2,y2] pixels")
    loc = ent.get("locus")
    if loc is not None and (not isinstance(loc, (list, tuple)) or not loc):
        problems.append("entity.locus must be a non-empty metric coordinate list")
    for k in ent:
        if k in _FORBIDDEN_BIOMETRIC:
            problems.append(f"entity.{k}: biometric floor - the moat must not enter the exportable WorldState")
    return problems


def make_entity(id: Any, type: str, *, bbox: Sequence[float] = None,
                locus: Sequence[float] = None, vec: Mapping[str, Any] = None,
                **extra: Any) -> dict:
    """A WorldState entity: `bbox` (image pixels) and/or `locus` (metric field position),
    with an optional model-tagged `vec`. Fail-closed on the biometric floor + separation law."""
    ent: dict[str, Any] = {"id": str(id), "type": type}
    if bbox is not None:
        ent["bbox"] = list(bbox)
    if locus is not None:
        ent["locus"] = list(locus)
    if vec is not None:
        ent["vec"] = dict(vec)
    ent.update(extra)
    problems = _entity_structural_problems(ent) + separation_law_problems(ent)
    if problems:
        raise ValueError(f"non-conformant WorldState entity: {problems}")
    return ent


def controller_entity(id: Any, *, input_locus: Sequence[float]) -> dict:
    """The QorTroller fusion piece: the certified controller as a FIELD SUBJECT whose exportable
    state is a point in INPUT space (`locus` = phi-quantized coarse stick/trigger position,
    public-safe), NOT a pixel box and NOT a latent. It carries NO `vec` on purpose - a
    controller latent would be biometric-adjacent (the anti-cheat moat), which never exports."""
    return make_entity(id, "controller", locus=input_locus)


def validate_worldstate(ws: Mapping[str, Any]) -> list[str]:
    """Fail-closed WorldState conformance: required `src`/`t`, well-formed entities, the
    biometric floor, and the separation law (top-level + nested entities/relations)."""
    if not isinstance(ws, Mapping):
        return ["WorldState must be a JSON object"]
    problems: list[str] = []
    if not ws.get("src"):
        problems.append("missing required field: src")
    if ws.get("t") in (None, ""):
        problems.append("missing required field: t")
    for k in ws:
        if k in _FORBIDDEN_BIOMETRIC:
            problems.append(f"WorldState.{k}: biometric floor violated")
    problems.extend(separation_law_problems(ws))                      # top-level + nested asserting
    for i, ent in enumerate(ws.get("entities") or []):
        problems.extend(f"entities[{i}] {p}" for p in _entity_structural_problems(ent))
    return problems


def make_worldstate(src: str, t: Any, *, frame: int = None, entities: Sequence = (),
                    relations: Sequence = (), scene: Mapping[str, Any] = None) -> dict:
    """Assemble a conformant WorldState snapshot (the standard's object-centric state). The
    smallest valid state is ``{src, t}``; entities/relations/scene are added when present."""
    ws: dict[str, Any] = {"src": src, "t": t}
    if frame is not None:
        ws["frame"] = frame
    if entities:
        ws["entities"] = list(entities)
    if relations:
        ws["relations"] = list(relations)
    if scene is not None:
        ws["scene"] = dict(scene)
    problems = validate_worldstate(ws)
    if problems:
        raise ValueError(f"non-conformant WorldState: {problems}")
    return ws


def emits_state_only(ws: Mapping[str, Any]) -> bool:
    return not validate_worldstate(ws)
