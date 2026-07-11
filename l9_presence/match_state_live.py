"""LUMEN-2b -- Live match-state tracker (the offline detector made stream-safe).

THE PROBLEM THE OFFLINE DETECTOR DIDN'T FACE (KC-2b-1): span snapping is retroactive.
Offline, "the match ended at last activity" is computed once, after the fact. Live, an
open activity group's end is PROVISIONAL at every tick -- emitting MATCH_ENDED at the
first quiet bucket would flap on every reload/rotation pause (M14 measured a 183s
in-match no-fire gap). So the live tracker separates two timestamps per event:

    ts_ms        WHEN the transition happened (retroactively snapped, same as offline)
    detected_at  WHEN the tracker became CONFIDENT enough to say so

MATCH_STARTED emits as soon as a group is confirmed (kill anchor, or enter_consecutive
active buckets). MATCH_ENDED emits only once (now - last_activity) > exit_gap -- the
same 240s hysteresis, applied forward in time. Detection latency is therefore inherent
and HONEST: a match start is announced ~20-30s in; a match end is announced ~4min after
the last activity, timestamped AT the last activity. Consumers get the truth late rather
than a guess early.

PURE core: signals are pushed in (onsets / windows / kill spans); tick(now_ms) re-runs
the SAME detect_match_state used offline (one implementation, dual consumers -- the
offline M14/M13 validation is this tracker's regression anchor) and diffs confirmed
transitions against what it already emitted. Advisory; never gates anything; the
cryptographic session boundary remains the daemon manifest seal. Stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from l9_presence.match_state import (
    DEFAULT_BUCKET_S,
    DEFAULT_ENTER_CONSECUTIVE,
    DEFAULT_EXIT_GAP_S,
    IN_MATCH,
    MATCH_ENDED,
    MATCH_STARTED,
    detect_match_state,
)


@dataclass(slots=True)
class LiveTransition:
    event: str            # MATCH_STARTED / MATCH_ENDED
    ts_ms: float          # when it happened (retroactively snapped)
    detected_at_ms: float  # when the tracker became confident

    def to_dict(self) -> dict:
        return {"event": self.event, "ts_ms": round(self.ts_ms, 1),
                "detected_at_ms": round(self.detected_at_ms, 1)}


@dataclass
class LiveMatchStateTracker:
    session_start_ms: float
    session_id: Optional[str] = None
    bucket_s: float = DEFAULT_BUCKET_S
    enter_consecutive: int = DEFAULT_ENTER_CONSECUTIVE
    exit_gap_s: float = DEFAULT_EXIT_GAP_S
    onsets_ms: list = field(default_factory=list)
    windows_ms: list = field(default_factory=list)
    kill_spans_ms: list = field(default_factory=list)
    _emitted: set = field(default_factory=set)          # dedup keys
    _open_match_start_ms: Optional[float] = None        # started, not yet ended

    # --- signal feeders (append-only; caller pushes as logs grow) --------------------
    def push_onset(self, t_ms: float) -> None:
        self.onsets_ms.append(float(t_ms))

    def push_window(self, gate_ms: float, end_ms: float) -> None:
        self.windows_ms.append((float(gate_ms), float(end_ms)))

    def push_kill_span(self, start_ms: float, end_ms: float) -> None:
        """K>=anchor_k clusters ONLY (the F-LUMEN-2 sighting discipline is the feeder's job)."""
        self.kill_spans_ms.append((float(start_ms), float(end_ms)))

    # --- the tick ---------------------------------------------------------------------
    def _last_activity_ms(self) -> Optional[float]:
        cands = list(self.onsets_ms)
        cands += [w[1] for w in self.windows_ms]
        cands += [k[1] for k in self.kill_spans_ms]
        return max(cands) if cands else None

    def tick(self, now_ms: float) -> list:
        """Re-detect over [session_start, now]; return NEW confirmed transitions (possibly
        empty). MATCH_ENDED for the newest match is withheld until exit-gap confidence."""
        now_ms = float(now_ms)
        if now_ms <= self.session_start_ms:
            return []
        tl = detect_match_state(
            session_span_ms=(self.session_start_ms, now_ms),
            onsets_ms=self.onsets_ms, windows_ms=self.windows_ms,
            kill_spans_ms=self.kill_spans_ms, session_id=self.session_id,
            bucket_s=self.bucket_s, enter_consecutive=self.enter_consecutive,
            exit_gap_s=self.exit_gap_s)

        last_act = self._last_activity_ms()
        end_confident = (last_act is not None
                         and (now_ms - last_act) > self.exit_gap_s * 1000.0)

        out: list = []
        matches = [s for s in tl.spans if s.state == IN_MATCH]
        for i, span in enumerate(matches):
            is_newest = (i == len(matches) - 1)
            start_key = (MATCH_STARTED, round(span.start_ms / (self.bucket_s * 1000.0)))
            if start_key not in self._emitted:
                self._emitted.add(start_key)
                self._open_match_start_ms = span.start_ms
                out.append(LiveTransition(MATCH_STARTED, span.start_ms, now_ms))
            # An OLDER match's end is already separated from newer activity by > exit_gap
            # (that's why the detector split them) -> confident by construction. The NEWEST
            # match's end is provisional until the forward hysteresis clears (KC-2b-1).
            if (not is_newest) or end_confident:
                end_key = (MATCH_ENDED, round(span.end_ms / (self.bucket_s * 1000.0)))
                if end_key not in self._emitted:
                    self._emitted.add(end_key)
                    if self._open_match_start_ms == span.start_ms:
                        self._open_match_start_ms = None
                    out.append(LiveTransition(MATCH_ENDED, span.end_ms, now_ms))
        return out

    def close_session(self, now_ms: float) -> list:
        """Session is over (daemon stop): flush the newest match's end WITHOUT waiting for
        forward hysteresis -- the manifest seal is a harder boundary than any gap.

        F-ARCB-1: path (A) alone (emit ENDED for the IN_MATCH spans re-detect finds) returned
        NOTHING at a live stop while match_state was IN_MATCH (n_ended=0 observed 2026-07-10),
        so no MATCH_ENDED sealed the session. Path (B) force-closes a still-open match off the
        _open_match_start_ms flag (set when STARTED fired) -- detect-independent AND
        clock-independent, so the seal is guaranteed once a match opened. Advisory; never gates;
        the cryptographic session boundary stays the daemon manifest seal."""
        tl = detect_match_state(
            session_span_ms=(self.session_start_ms, float(now_ms)),
            onsets_ms=self.onsets_ms, windows_ms=self.windows_ms,
            kill_spans_ms=self.kill_spans_ms, session_id=self.session_id,
            bucket_s=self.bucket_s, enter_consecutive=self.enter_consecutive,
            exit_gap_s=self.exit_gap_s)
        out: list = []
        matches = [s for s in tl.spans if s.state == IN_MATCH]
        for span in matches:                                    # (A) detect path (multi-match / snapped ends)
            end_key = (MATCH_ENDED, round(span.end_ms / (self.bucket_s * 1000.0)))
            if end_key not in self._emitted:
                self._emitted.add(end_key)
                out.append(LiveTransition(MATCH_ENDED, span.end_ms, float(now_ms)))
        if not matches and self._open_match_start_ms is not None:   # (B) F-ARCB-1 force seal
            force_key = (MATCH_ENDED, "session_close")              # single-shot per tracker lifetime
            if force_key not in self._emitted:
                self._emitted.add(force_key)
                last_act = self._last_activity_ms()
                end_ts = last_act if last_act is not None else float(now_ms)  # ts=truth, detected=now
                out.append(LiveTransition(MATCH_ENDED, end_ts, float(now_ms)))
        self._open_match_start_ms = None
        return out

    def state_now(self, now_ms: float) -> str:
        """Advisory current state: IN_MATCH once a match is confirmed-open and activity is
        within the exit gap; else LOBBY."""
        if self._open_match_start_ms is None:
            return "LOBBY"
        last_act = self._last_activity_ms()
        if last_act is not None and (float(now_ms) - last_act) > self.exit_gap_s * 1000.0:
            return "LOBBY"
        return IN_MATCH


def seal_open_match_from_jsonl(jsonl_path: str, session_id: str, now_ms: float) -> Optional[dict]:
    """F-ARCB-1b -- daemon-side MATCH_ENDED seal.

    The retina daemon's `stop` force-kills the bridge (taskkill /F), so RGC.stop() ->
    LiveMatchStateTracker.close_session NEVER runs and a live-open match is left un-sealed (a
    MATCH_STARTED with no matching MATCH_ENDED in retina_match_state.jsonl). This pure helper lets
    the daemon emit the seal the same way it harvests KAS/PoSP -- independent of the killed bridge
    process. It scans the persisted jsonl for `session_id`; if the MATCH_STARTED count exceeds the
    MATCH_ENDED count, it returns ONE MATCH_ENDED seal dict (the caller appends it). Returns None
    when already balanced / file absent / never started -- idempotent, so a second stop never
    double-seals (by then the counts are balanced).

    ts_ms = now (session-close time): unlike the in-process close_session, which snaps ts to the
    last activity, the daemon does not hold the tracker's signals, so the honest timestamp is the
    session-close moment; `reason="daemon_session_close"` marks the provenance. Advisory; never
    gates; the cryptographic session boundary stays the daemon manifest seal."""
    import json
    import os
    if not os.path.exists(jsonl_path):
        return None
    started = ended = 0
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:  # noqa: BLE001 -- skip a malformed line, never crash the seal
                    continue
                if d.get("session_id") != session_id:
                    continue
                ev = d.get("event")
                if ev == MATCH_STARTED:
                    started += 1
                elif ev == MATCH_ENDED:
                    ended += 1
    except Exception:  # noqa: BLE001 -- unreadable jsonl -> no seal, never break stop
        return None
    if started <= ended:
        return None                                      # already sealed / never started -> no-op
    return {"event": MATCH_ENDED, "ts_ms": round(float(now_ms), 1),
            "detected_at_ms": round(float(now_ms), 1),
            "schema": "qortroller-match-state-live-v0", "session_id": session_id,
            "advisory": True, "reason": "daemon_session_close"}
