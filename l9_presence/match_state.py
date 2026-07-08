"""LUMEN-2 -- Match-State Detector (qortroller-match-state-v0, offline-first).

Answers "when did a match begin/end inside this session?" from signals the stack already
computes -- the first Lumen-style understanding over a session timeline. ADVISORY by
construction: match-state events annotate; they never gate a verdict, never move a
certificate, and the cryptographic session boundary REMAINS daemon start/stop (the
manifest seal). This is observation-plane structuring, not assertion.

DESIGN (v0, pre-registered rules -- input-anchored, splice-consistent):
  A time-bucketed activity state machine. A bucket is ACTIVE when it contains any of:
    - a raw R2 onset (retina_hid_events.jsonl)          [input lobe]
    - a live R2 window overlap (retina_kf_composite)     [input lobe]
    - a kill-row cluster overlap (v2 precision scan)     [screen lobe, K>=1 read]
  Kill-cluster buckets are DEFINITIVE anchors (a killfeed row with the operator's handle
  cannot happen in a menu). Transitions:
    LOBBY -> IN_MATCH : >= enter_consecutive active buckets, OR one kill-anchored bucket
    IN_MATCH -> LOBBY : > exit_gap_s of consecutive inactivity
  SPAN SNAPPING: match spans snap to the FIRST/LAST active bucket -- hysteresis decides
  confidence, activity decides boundaries (a generous exit gap never inflates the span).
  Warzone reality encoded: M14 had a 183s no-fire rotation INSIDE the match, so
  exit_gap_s defaults to 240s.

HONEST LIMITS (v0):
  - END_SCREEN is not a distinct state (needs a HUD-template study); match end = last
    activity, so post-match victory/summary screens read as LOBBY.
  - Warzone pre-game warmup allows firing -> warmup may read as IN_MATCH (behavioral
    detector, not HUD-semantic). Both are LUMEN-2.x refinements, not bugs at v0 scope.
  - Offline v0: MATCH_STARTED ts is retroactively snapped; a live variant would confirm
    with enter_consecutive latency.

FAIL-OPEN: no signals -> a single UNKNOWN span, never a guessed match. PURE stdlib.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

MATCH_STATE_SCHEMA = "qortroller-match-state-v0"   # schema string only -- not a domain tag

LOBBY = "LOBBY"
IN_MATCH = "IN_MATCH"
UNKNOWN = "UNKNOWN"

MATCH_STARTED = "MATCH_STARTED"
MATCH_ENDED = "MATCH_ENDED"

DEFAULT_BUCKET_S = 10.0
DEFAULT_ENTER_CONSECUTIVE = 2      # active buckets to confirm a match (kills confirm alone)
DEFAULT_EXIT_GAP_S = 240.0         # M14 measured a 183s in-match no-fire rotation


@dataclass(slots=True)
class StateSpan:
    state: str
    start_ms: float
    end_ms: float

    def to_dict(self) -> dict:
        return {"state": self.state, "start_ms": round(self.start_ms, 1),
                "end_ms": round(self.end_ms, 1)}


@dataclass
class MatchStateTimeline:
    schema: str
    session_id: Optional[str]
    session_display: Optional[str]
    spans: list = field(default_factory=list)        # StateSpan, contiguous over the session
    events: list = field(default_factory=list)       # {ts_ms, event} at transitions
    n_matches: int = 0
    bucket_s: float = DEFAULT_BUCKET_S
    notes: list = field(default_factory=list)
    advisory: bool = True

    def state_at(self, ts_ms: float) -> str:
        for s in self.spans:
            if s.start_ms <= ts_ms <= s.end_ms:
                return s.state
        return UNKNOWN

    def to_dict(self) -> dict:
        return {"schema": self.schema, "session_id": self.session_id,
                "session_display": self.session_display,
                "spans": [s.to_dict() for s in self.spans], "events": self.events,
                "n_matches": self.n_matches, "bucket_s": self.bucket_s,
                "notes": self.notes, "advisory": self.advisory}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _bucket_activity(session_span_ms, bucket_s: float, onsets_ms, windows_ms,
                     kill_spans_ms):
    """Bucketize the session; per bucket -> (active: bool, kill_anchored: bool)."""
    t0, t1 = float(session_span_ms[0]), float(session_span_ms[1])
    width = bucket_s * 1000.0
    n = max(1, int((t1 - t0) / width) + 1)
    active = [False] * n
    anchored = [False] * n

    def _idx(ts: float) -> Optional[int]:
        i = int((float(ts) - t0) / width)
        return i if 0 <= i < n else None

    for ts in (onsets_ms or []):
        i = _idx(ts)
        if i is not None:
            active[i] = True
    for w in (windows_ms or []):
        a, b = _idx(float(w[0])), _idx(float(w[1]))
        if a is None and b is None:
            continue
        a = 0 if a is None else a
        b = n - 1 if b is None else b
        for i in range(min(a, b), max(a, b) + 1):
            active[i] = True
    for k in (kill_spans_ms or []):
        a, b = _idx(float(k[0])), _idx(float(k[1]))
        if a is None and b is None:
            continue
        a = 0 if a is None else a
        b = n - 1 if b is None else b
        for i in range(min(a, b), max(a, b) + 1):
            active[i] = True
            anchored[i] = True
    return active, anchored, t0, width


def detect_match_state(*, session_span_ms, onsets_ms=None, windows_ms=None,
                       kill_spans_ms=None, session_id: Optional[str] = None,
                       session_display: Optional[str] = None,
                       bucket_s: float = DEFAULT_BUCKET_S,
                       enter_consecutive: int = DEFAULT_ENTER_CONSECUTIVE,
                       exit_gap_s: float = DEFAULT_EXIT_GAP_S) -> MatchStateTimeline:
    """Detect IN_MATCH spans inside [session_start_ms, session_end_ms]. See module doc."""
    tl = MatchStateTimeline(schema=MATCH_STATE_SCHEMA, session_id=session_id,
                            session_display=session_display, bucket_s=bucket_s)
    if not session_span_ms or float(session_span_ms[1]) <= float(session_span_ms[0]):
        tl.spans = []
        tl.notes.append("unknown: empty/invalid session span")
        return tl
    if not (onsets_ms or windows_ms or kill_spans_ms):
        tl.spans = [StateSpan(UNKNOWN, float(session_span_ms[0]), float(session_span_ms[1]))]
        tl.notes.append("unknown: no activity signals supplied -- never guessing a match")
        return tl

    active, anchored, t0, width = _bucket_activity(session_span_ms, bucket_s,
                                                   onsets_ms, windows_ms, kill_spans_ms)
    exit_gap_buckets = max(1, int(exit_gap_s * 1000.0 / width))

    # Pass 1: find match groups -- runs of active buckets merged across gaps < exit_gap.
    matches = []            # list of (first_active_idx, last_active_idx, has_anchor)
    cur_first = cur_last = None
    cur_anchor = False
    for i, a in enumerate(active):
        if a:
            if cur_first is None:
                cur_first, cur_last = i, i
            elif i - cur_last > exit_gap_buckets:
                matches.append((cur_first, cur_last, cur_anchor))
                cur_first, cur_last, cur_anchor = i, i, False
            else:
                cur_last = i
            cur_anchor = cur_anchor or anchored[i]
    if cur_first is not None:
        matches.append((cur_first, cur_last, cur_anchor))

    # Pass 2: confirmation -- a group is a MATCH if kill-anchored OR spans
    # >= enter_consecutive active buckets (count within the group).
    confirmed = []
    for first, last, has_anchor in matches:
        n_active = sum(1 for i in range(first, last + 1) if active[i])
        if has_anchor or n_active >= enter_consecutive:
            confirmed.append((first, last))
        else:
            tl.notes.append(f"activity group at bucket {first} unconfirmed "
                            f"({n_active} active, no kill anchor) -- left as LOBBY")

    # Pass 3: emit contiguous spans + transition events (spans SNAP to activity).
    spans, events = [], []
    cursor = float(session_span_ms[0])
    for first, last in confirmed:
        m_start = t0 + first * width
        m_end = t0 + (last + 1) * width
        if m_start > cursor:
            spans.append(StateSpan(LOBBY, cursor, m_start))
        spans.append(StateSpan(IN_MATCH, m_start, m_end))
        events.append({"ts_ms": round(m_start, 1), "event": MATCH_STARTED})
        events.append({"ts_ms": round(m_end, 1), "event": MATCH_ENDED})
        cursor = m_end
    if cursor < float(session_span_ms[1]):
        spans.append(StateSpan(LOBBY, cursor, float(session_span_ms[1])))

    tl.spans = spans
    tl.events = events
    tl.n_matches = len(confirmed)
    if not confirmed:
        tl.notes.append("no confirmed match in session")
    return tl


def evaluate_containment(timeline: MatchStateTimeline, *, kill_spans_ms=None,
                         windows_ms=None) -> dict:
    """The honest evaluation: every kill cluster and every live R2 window MUST fall
    inside a detected IN_MATCH span (they are ground-truth in-match facts). Returns
    counts + misses -- a miss is a finding, never silently absorbed."""
    def _contained(span) -> bool:
        mid = (float(span[0]) + float(span[1])) / 2.0
        return timeline.state_at(mid) == IN_MATCH

    kills = list(kill_spans_ms or [])
    wins = list(windows_ms or [])
    k_in = sum(1 for k in kills if _contained(k))
    w_in = sum(1 for w in wins if _contained(w))
    return {"kills_contained": f"{k_in}/{len(kills)}",
            "windows_contained": f"{w_in}/{len(wins)}",
            "ok": k_in == len(kills) and w_in == len(wins),
            "missed_kills": [k for k in kills if not _contained(k)],
            "missed_windows": [w for w in wins if not _contained(w)]}
