"""TRA-1 T1 - `retina.event/0.1` emitter + validator (adopt the MachineFi Trio Retina standard).

Emits QorTroller OBSERVATION-plane events in [machinefi/trio-retina](https://github.com/machinefi/trio-retina)'s
`retina.event/0.1` format and validates them against the standard's required-field + vocabulary
rules. Gaming events use the standard's OWN namespaced-custom-type extension (TRA-1 F-TRA0-2) -
never force-fit onto the surveillance-CV primitives (`zone.*`/`line.cross`/`count.*`). Serializes
as an ORDERED JSON-Lines stream (F-TRA0-1, replayable), and can commit that stream with the
order-preserving Poseidon root.

Canonical reference: trio-retina `retina/event.schema.json` (JSON Schema draft 2020-12). This
module checks the documented required/optional/vocabulary rules in pure stdlib (no `jsonschema`
dep); a later cycle may validate against the vendored schema file directly.

OBSERVATION-plane only. No PoAC / 228B wire / ASSERTION-plane / chain contact.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

RETINA_EVENT_VERSION = "retina.event/0.1"

# The closed 0.1 primitive vocabulary (surveillance-CV shaped) - SPEC.md.
KNOWN_TYPES = frozenset({
    "zone.enter", "zone.exit", "zone.dwell", "line.cross", "count.threshold",
})

# Reserved primitive domains: a custom type may not squat these namespaces.
_RESERVED_DOMAINS = frozenset({"zone", "line", "count"})

# Required fields (JWT-minimal): the smallest valid event is {type, t, src}.
REQUIRED = ("type", "t", "src")

# Registered optional fields -> expected python type(s), for validation.
_OPTIONAL_TYPES: dict[str, Any] = {
    "id": int, "label": str, "zone": str, "dur": (int, float), "dir": str,
    "n": int, "conf": (int, float), "box": (list, tuple), "by": str,
    "frame": int, "clip": str, "eid": str, "vec": dict,
}


def is_namespaced_type(t: str) -> bool:
    """A custom (non-primitive) type is legal iff it is namespaced per the standard's own
    extension convention (SPEC.md: 'just add a key, namespace it'): an ``x_`` prefix, or
    ``namespace.verb`` with a non-empty, non-reserved namespace."""
    if t.startswith("x_") and len(t) > 2:
        return True
    if "." in t:
        ns, _, verb = t.partition(".")
        return bool(ns) and bool(verb) and ns not in _RESERVED_DOMAINS
    return False


def validate_event(event: Mapping[str, Any]) -> list[str]:
    """Return a list of problems ([] == valid) - mirrors trio-retina's ``validate()``."""
    if not isinstance(event, Mapping):
        return ["event must be a JSON object"]
    problems: list[str] = []

    for k in REQUIRED:
        if k not in event or event[k] is None or event[k] == "":
            problems.append(f"missing required field: {k}")

    t = event.get("type")
    if isinstance(t, str) and t:
        if t not in KNOWN_TYPES and not is_namespaced_type(t):
            problems.append(
                f"unknown bare type {t!r}: not a retina.event/0.1 primitive and not "
                f"namespaced - use 'x_*' or 'ns.verb' per the extension rule (F-TRA0-2)"
            )
    elif "type" in event and not (isinstance(t, str) and t):
        problems.append("type must be a non-empty string")

    ts = event.get("t")
    if "t" in event and ts not in (None, "") and not isinstance(ts, (int, float, str)):
        problems.append("t must be epoch-seconds (number) or an RFC3339 string")
    if isinstance(ts, bool):  # bool is an int subclass - reject as a timestamp
        problems.append("t must not be a boolean")

    src = event.get("src")
    if "src" in event and src not in (None, "") and not isinstance(src, str):
        problems.append("src must be a string")

    for k, expected in _OPTIONAL_TYPES.items():
        if k in event and event[k] is not None:
            if isinstance(event[k], bool) and expected in (int, (int, float)):
                problems.append(f"field {k!r} must not be a boolean")
            elif not isinstance(event[k], expected):
                problems.append(f"field {k!r} has wrong type")

    return problems


def is_valid(event: Mapping[str, Any]) -> bool:
    return not validate_event(event)


def make_event(type: str, t: Any, src: str, **fields: Any) -> dict:
    """Construct a conformant event, omitting null/empty optionals (SPEC: omit-empty).
    Raises ValueError if the assembled event is not conformant."""
    ev: dict[str, Any] = {"type": type, "t": t, "src": src}
    for k, v in fields.items():
        if v is None or v == "":
            continue
        ev[k] = v
    problems = validate_event(ev)
    if problems:
        raise ValueError(f"non-conformant retina.event: {problems}")
    return ev


def validate_stream(events: Sequence[Mapping[str, Any]]) -> list[str]:
    problems: list[str] = []
    for i, e in enumerate(events):
        problems.extend(f"[{i}] {p}" for p in validate_event(e))
    return problems


def to_jsonl(events: Sequence[Mapping[str, Any]], *, validate: bool = True) -> str:
    """Serialize an ORDERED JSON-Lines stream (emission order preserved - the standard's
    replayable format, F-TRA0-1). Each event canonicalized (sorted keys, omit-empty); the
    LINE order is the event order. Optionally validates the stream first."""
    if validate:
        problems = validate_stream(events)
        if problems:
            raise ValueError(f"stream has non-conformant events: {problems[:5]}")
    lines = []
    for e in events:
        clean = {k: v for k, v in dict(e).items() if v is not None and v != ""}
        lines.append(json.dumps(clean, sort_keys=True, separators=(",", ":")))
    return "\n".join(lines)


def ordered_events_root(
    events: Sequence[Mapping[str, Any]],
    *,
    chain_fn=None,
    validate: bool = True,
) -> bytes:
    """Validate + compute the order-PRESERVING Poseidon events_root over a conformant stream
    (the F-TRA0-1 resolution - commits the replayable order, not a sorted set)."""
    if validate:
        problems = validate_stream(events)
        if problems:
            raise ValueError(f"stream has non-conformant events: {problems[:5]}")
    from .retina_events_root import compute_events_root_poseidon_ordered
    return compute_events_root_poseidon_ordered(events, chain_fn=chain_fn)
