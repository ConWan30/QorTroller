"""WMP UC-15 — Self-analytics: the gamer consuming their OWN verified data (demand-side seed).

The self-consumption loop that makes the data economy sticky BEFORE any external buyer exists: the
producing gamer's own dashboard over their verified history — verified-session cadence, clean-rate,
current clean streak, authored-kill progression. Every figure derives from ALREADY-COMPUTED protocol
truth (GIC-stamped ruling rows = sessions that passed every gate; grind analytics; KAS authored-kill
counts). No proof needed — it's the gamer's own data, zero consent friction.

HARD RAILS (portfolio ceiling):
  - SELF-VIEW ONLY. No cross-player comparison, no percentile, no rank, no "best player" — those
    re-enter the population gate (separation ratio science, not shipped). This module holds NO other
    player's data and refuses to synthesize a comparison.
  - `population_certified=False`, `advisory=True`, `developer_self` scale (N=1 rig capacity).
  - READ-ONLY. Never writes, never grants/revokes consent, never touches chain. No biometric — all
    figures are post-verdict aggregates, not raw capture.

Pure functions (testable, no DB) + a thin read-only Store adapter over public getters.
"""
from __future__ import annotations

SCHEMA = "qortroller-wmp-self-analytics-v0"
_NS_PER_DAY = 86_400 * 1_000_000_000


def compute_clean_streaks(clean_flags: list[bool]) -> dict:
    """Streaks over an ordered (oldest->newest) sequence of clean/eligible session flags.

    A 'clean' session = one that passed every gate (GIC-stamped). Handles breaks: the current streak is
    the trailing run; max is the longest run; segments lists every run's length.
    """
    segments: list[int] = []
    run = 0
    for c in clean_flags:
        if c:
            run += 1
        else:
            if run:
                segments.append(run)
            run = 0
    if run:
        segments.append(run)
    total = len(clean_flags)
    n_clean = sum(1 for c in clean_flags if c)
    return {
        "current_clean_streak": run,                 # trailing run (0 if the last session broke it)
        "max_clean_streak": max(segments) if segments else 0,
        "streak_segments": segments,
        "total_clean_sessions": n_clean,
        "total_sessions": total,
        "clean_rate": round(n_clean / total, 4) if total else 0.0,
    }


def compute_session_cadence(timestamps_ns: list[int]) -> dict:
    """Verified-session cadence from session timestamps (ns). Self-view — no comparison."""
    if not timestamps_ns:
        return {"total_sessions": 0, "active_days": 0, "span_days": 0.0, "sessions_per_active_day": 0.0,
                "first_ts_ns": None, "last_ts_ns": None}
    ts = sorted(int(t) for t in timestamps_ns)
    span_days = (ts[-1] - ts[0]) / _NS_PER_DAY
    active_days = len({t // _NS_PER_DAY for t in ts})
    return {
        "total_sessions": len(ts),
        "active_days": active_days,
        "span_days": round(span_days, 2),
        "sessions_per_active_day": round(len(ts) / active_days, 2) if active_days else 0.0,
        "first_ts_ns": ts[0],
        "last_ts_ns": ts[-1],
    }


def compute_authored_progression(per_match: list[int]) -> dict:
    """Cumulative authored-kill progression across the gamer's own matches (chronological)."""
    cumulative: list[int] = []
    running = 0
    for c in per_match:
        running += max(0, int(c))
        cumulative.append(running)
    n = len(per_match)
    return {
        "authored_total": running,
        "matches": n,
        "per_match": [max(0, int(c)) for c in per_match],
        "cumulative": cumulative,
        "authored_per_match_mean": round(running / n, 2) if n else 0.0,
        "best_match": max((max(0, int(c)) for c in per_match), default=0),
    }


def compute_self_analytics(*, clean_flags: list[bool], session_timestamps_ns: list[int],
                           authored_per_match: list[int] | None = None,
                           current_streak_override: int | None = None) -> dict:
    """Assemble the gamer's self-analytics view. Pure — no DB, no chain, no comparison."""
    authored_per_match = authored_per_match or []
    streaks = compute_clean_streaks(clean_flags)
    if current_streak_override is not None:
        # authoritative current streak from the live GIC chain status (survives partial-log reads)
        streaks["current_clean_streak"] = int(current_streak_override)
    return {
        "schema": SCHEMA,
        "self_view_only": True,
        "cross_player_comparison": False,
        "population_certified": False,
        "advisory": True,
        "scope": "developer_self",
        "clean_streaks": streaks,
        "session_cadence": compute_session_cadence(session_timestamps_ns),
        "authored_kills": compute_authored_progression(authored_per_match),
        "note": "Self-consumption view over the gamer's OWN verified protocol history. Every figure "
                "derives from already-computed protocol truth (GIC-stamped ruling rows = sessions that "
                "passed every gate) + authored-kill counts + session timestamps. NO rank, NO cross-player "
                "comparison (that re-enters the population gate), NO biometric export. Read-only: no chain "
                "write, no consent write; developer_self N=1 scale.",
    }


def self_analytics_from_store(store, *, grind_session_id: str = "",
                              authored_per_match: list[int] | None = None) -> dict:
    """Read-only Store adapter (public getters only). Fail-soft: missing data -> zeroed sections, never
    fabricated figures. `authored_per_match` is passed in from the gamer's match record source (KAS /
    scorecards); absent -> empty (honest: no authored data rather than invented)."""
    clean_flags: list[bool] = []
    session_ts: list[int] = []
    try:
        rows = store.get_ruling_rows_for_chain(grind_session_id)  # GIC-stamped (verified) rows, ts ASC
        for r in rows:
            clean_flags.append(bool(r.get("grind_chain_hash")))
            ts = r.get("gic_ts_ns")
            if ts:
                session_ts.append(int(ts))
    except Exception:  # noqa: BLE001 - fail-soft self-view
        pass

    current_streak = None
    try:
        status = store.get_grind_chain_status(grind_session_id) if grind_session_id else store.get_grind_chain_status("")
        if isinstance(status, dict) and status.get("chain_intact"):
            current_streak = int(status.get("chain_length", 0) or 0)
    except Exception:  # noqa: BLE001
        pass

    return compute_self_analytics(
        clean_flags=clean_flags, session_timestamps_ns=session_ts,
        authored_per_match=authored_per_match or [], current_streak_override=current_streak,
    )
