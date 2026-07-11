"""QorTroller L9 — shared screen-lobe event schema (Increment B, Phase B1).

Normalizes a killfeed AUTHORED composite into ONE canonical event mapping that BOTH (a) feeds the retina
events_root commitment (Phase B2) and (b) produces a causal-coherence TimedEvent — so screen outcomes and HID
inputs land in the same root and the same coherence assessment.

Clock discipline (D-TRIO-1, load-bearing): the event's alignment timestamp is the kill-row FRAME-CAPTURE ts
(`killer_first_ms`), NOT the window-resolution ts (seconds late) and NOT the OCR read-completion. The engine
read latency rides a SEPARATE field, so a future recognizer swap (PP-OCRv6 21ms vs tesseract 2540ms) cannot
skew cross-lobe latency. If a composite lacks the frame-capture anchor, t falls back to the resolution ts but
the `clock` field records "resolution_fallback" — honest, never silently mixed.

C3 provenance (engine id + anchor SHA + raw pre-canon read + exact|fuzzy) is first-class event payload here,
not just KAS-trail metadata. D-TRIO-2: row_freshness rides as a verifiable field inside the event (and thus
inside the commitment). PURE: dict transforms, stdlib only.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

SCREEN_EVENT_AUTHORED = "kill_authored"
CLOCK_FRAME_CAPTURE = "frame_capture"
CLOCK_RESOLUTION_FALLBACK = "resolution_fallback"


def authored_screen_event(composite: Optional[Mapping[str, Any]], *, engine: Optional[str] = None,
                          anchor_sha: Optional[str] = None, raw_read: Optional[str] = None,
                          match_kind: Optional[str] = None,
                          row_freshness: Optional[Any] = None,
                          record_hash: Optional[str] = None) -> Optional[dict]:
    """A killfeed AUTHORED composite -> canonical screen-lobe event mapping (feeds events_root). Returns None
    unless the composite is AUTHORED_PRESENT (only own-kills are authorship outcomes).

    EVENT-BIND increment 2: `record_hash` (arg, or the composite's own) is the live PoAC anchor stamped at
    capture time so this OUTCOME and its causing HID onset share a cryptographic bind. KEY-ONLY-WHEN-STAMPED:
    absent -> byte-identical to pre-EVENT-BIND (events_root unchanged); present -> the anchor folds into the
    events_root/KAS commitment."""
    if not composite or composite.get("verdict") != "AUTHORED_PRESENT":
        return None
    kfirst = composite.get("killer_first_ms")
    if kfirst is not None:
        t_ms, clock = float(kfirst), CLOCK_FRAME_CAPTURE
    else:                                   # no frame-capture anchor -> resolution ts, FLAGGED (D-TRIO-1 unmet)
        rez = composite.get("ts_ms")
        t_ms, clock = (float(rez) if rez is not None else None), CLOCK_RESOLUTION_FALLBACK
    ev = {
        "type": SCREEN_EVENT_AUTHORED,
        "t_ms": round(t_ms, 1) if t_ms is not None else None,
        "clock": clock,                     # frame_capture | resolution_fallback (verifiable honesty)
        "read_latency_ms": composite.get("read_latency_ms"),
        "composite_score": composite.get("composite_score"),
        "window_members": composite.get("window_members"),
        "window_gate_ms": composite.get("window_gate_ms"),
        # C3 provenance (model identity + A3 assurance + raw read) — first-class event data
        "engine": engine,
        "anchor": anchor_sha or composite.get("anchor"),
        "raw_read": raw_read,
        "match_kind": match_kind,
        # D-TRIO-2: freshness evidence, verifiable inside the commitment
        "row_freshness": row_freshness,
        # anti-splice: a kill OUTCOME requires a live input cause (the R2^B2 invariant at the event level)
        "input_caused": True,
    }
    rh = record_hash if record_hash is not None else composite.get("record_hash")
    if rh is not None:
        ev["record_hash"] = str(rh)          # the shared PoAC anchor (key-only-when-stamped)
    return ev


def session_screen_events(composites, *, provenance: Optional[Mapping[str, Any]] = None) -> list[dict]:
    """Every AUTHORED composite in a session -> its screen-lobe event (the session's outcome events, feeding
    the unified events_root). `provenance` optionally supplies session-wide C3 defaults (engine/anchor_sha/
    match_kind) when per-composite provenance is absent. Non-AUTHORED composites are skipped."""
    out = []
    p = dict(provenance or {})
    for c in composites or []:
        ev = authored_screen_event(c, engine=c.get("engine") or p.get("engine"),
                                   anchor_sha=p.get("anchor_sha"), raw_read=c.get("raw_read") or p.get("raw_read"),
                                   match_kind=c.get("match_kind") or p.get("match_kind"),
                                   row_freshness=c.get("row_freshness"))
        if ev is not None:
            out.append(ev)
    return out


def to_timed_event(event: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """Screen-lobe event mapping -> causal-coherence TimedEvent kwargs (kind=outcome; t in SECONDS from the
    FRAME-CAPTURE t_ms). None if the event has no timestamp. Consumed by
    retina_causal_coherence.TimedEvent(**kwargs)."""
    if not event or event.get("t_ms") is None:
        return None
    return {"kind": "outcome", "type": str(event.get("type", SCREEN_EVENT_AUTHORED)),
            "t": float(event["t_ms"]) / 1000.0, "input_caused": bool(event.get("input_caused", True))}
