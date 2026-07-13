"""TRA-1 T6.1 - kill-feed rows -> conformant `retina.event/0.1` events.

Maps OBSERVED kill-feed rows (`killfeed_raw_reader.read_rows` output: killer-left token lists) into
IoTeX Trio Retina `retina.event/0.1` events using the standard's namespaced-custom-type extension
(``x_qortroller.kill`` per F-TRA0-2 - kills are not the surveillance-CV zone/line/count vocab). Each
event carries ONLY the observed killer + victim text; it NEVER carries an authorship verdict / own
flag / presence score - the encoder emits STATE, never a claim (separation law, T4). Which killer is
"you" is a FUSION-layer decision (match `canon(killer)` to the own handle), not an event field.

Decoupled: this adapter takes rows, not the card or the reader - so it is desk-testable and card-free.
The frame -> rows -> events wiring into the live daemon is T6.6. OBSERVATION-plane only: no PoAC /
228B / ASSERTION / chain contact. `make_event` fail-closes on any non-conformant or asserting event;
a row that cannot form a conformant event is skipped, never forced.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .retina_event_std import make_event

KILL_EVENT_TYPE = "x_qortroller.kill"
DEFAULT_SRC = "retina.killfeed"
# a feed row whose victim slot is only one of these is a status line, not a kill -> skip it.
_STATUS_TOKENS = frozenset({"connected", "disconnected", "joined", "left", "reconnected"})


def _canon_word(s: str) -> str:
    return "".join(c for c in str(s).lower() if c.isalnum())


def kill_event(killer: str, victim: str, t, *, src: str = DEFAULT_SRC,
               frame: Optional[int] = None) -> dict:
    """One conformant ``x_qortroller.kill`` event carrying the OBSERVED killer + victim only."""
    return make_event(KILL_EVENT_TYPE, t, src, killer=str(killer), victim=str(victim), frame=frame)


def kill_events_from_rows(rows: Sequence[Sequence[str]], t, *, src: str = DEFAULT_SRC,
                          frame: Optional[int] = None) -> list[dict]:
    """Ordered kill-feed rows -> ordered ``x_qortroller.kill`` events (F-TRA0-1 order preserved). A
    kill row is killer (leftmost token) + >=1 victim token; single-token rows and status lines
    (e.g. ``"... Connected"``) are skipped. Fail-closed per row: a non-conformant row is skipped,
    never forced into an event."""
    events: list[dict] = []
    for row in rows:
        toks = [str(x) for x in row if x and str(x).strip()]
        if len(toks) < 2:
            continue
        killer, victim = toks[0], " ".join(toks[1:])
        if _canon_word(victim) in _STATUS_TOKENS:
            continue
        try:
            events.append(kill_event(killer, victim, t, src=src, frame=frame))
        except ValueError:
            continue
    return events
