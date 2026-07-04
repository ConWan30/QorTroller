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


def cross_lobe_coherence(screen_events: Optional[Sequence[Mapping[str, Any]]] = None,
                         hid_events: Optional[Sequence[Mapping[str, Any]]] = None,
                         window_s: Optional[float] = None) -> dict:
    """Input->outcome causal coherence over the two lobes: each screen kill-OUTCOME (killfeed AUTHORED) matched
    to a preceding HID R2-onset INPUT within the causal window (retina_causal_coherence.assess_coherence). This
    is where the cross-lobe latency BECOMES MEASURABLE — `latencies_s` is the per-outcome nearest_input_dt
    (screen frame-capture ts minus the HID onset device-clock ts).

    UNCALIBRATED by construction: the causal map + window are a hypothesis, and the latency is only as good as
    the two independent wall-anchors agree (screen WGC vs HID device clock — each HID event carries its raw
    device_ts + wall_ms so that agreement is auditable). Advisory: this rides into the KAS record as a readout
    over the events already bound by the events_root; it does NOT gate any verdict. Fail-open: any error ->
    {'calibration':'UNCALIBRATED','error':...} so issuance never breaks."""
    try:
        from l9_presence.killfeed_hid_event import to_timed_event as _hid_te
        from l9_presence.killfeed_screen_event import to_timed_event as _screen_te

        from .retina_causal_coherence import CoherenceConfig, TimedEvent, assess_coherence
        tes = []
        for e in (screen_events or []):
            kw = _screen_te(e)
            if kw:
                tes.append(TimedEvent(**kw))
        for e in (hid_events or []):
            kw = _hid_te(e)
            if kw:
                tes.append(TimedEvent(**kw))
        cfg = CoherenceConfig(window_s=float(window_s)) if window_s else CoherenceConfig()
        rep = assess_coherence(tes, cfg)
        d = rep.to_dict()
        d["latencies_s"] = [round(m.nearest_input_dt, 4)
                            for m in rep.matches if m.nearest_input_dt is not None]
        d["n_hid_inputs"] = sum(1 for t in tes if t.kind == "input")
        return d
    except Exception as e:  # noqa: BLE001 — advisory readout; never blocks issuance
        return {"calibration": "UNCALIBRATED", "error": repr(e)}
