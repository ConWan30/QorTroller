"""Real-capture session loader for Phase 2 of the consistency experiment.

Reads the bridge SQLite DB and assembles REAL LabeledWindows for operator-labelled
session windows, then the SAME harness (signal_adapter + consistency_eval) consumes
them. Bypasses synthetic_sessions.py. Stdlib sqlite3 only -- no bridge import.

Binding (experiment-only, by construction): a labelled session is one device + one
class + one time window; the presence probes (l6b_probe_log), retina rows
(retina_event_log), and L4 (records.pitl_l4_distance) inside that window belong
together. Each retina row is a WINDOW; L4 joins by record_hash; presence is the most
recent l6b probe within `presence_freshness_s` (challenge-response is sparse, so a
recent proof is carried forward, else the window's presence is UNKNOWN).

Timestamp bases (confirmed against store/_core.py):
  - l6b_probe_log.probe_ts_ms : INTEGER milliseconds  -> /1000.0
  - retina_event_log.created_at: REAL epoch seconds
  - records.created_at         : REAL epoch seconds
Sessions are specified in epoch SECONDS.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .session_class import LabeledSession, LabeledWindow, Provenance, SessionClass

DEFAULT_PRESENCE_FRESHNESS_S = 30.0


@dataclass(frozen=True)
class SessionLabel:
    device_id: str
    t_start: float            # epoch seconds (inclusive)
    t_end: float              # epoch seconds (inclusive)
    class_label: SessionClass
    presence_freshness_s: float = DEFAULT_PRESENCE_FRESHNESS_S


def load_labels_from_json(path: str) -> list[SessionLabel]:
    """Manifest format: a JSON list of
    {device_id, t_start, t_end, class_label, presence_freshness_s?}."""
    raw = json.loads(open(path, encoding="utf-8").read())
    out = []
    for r in raw:
        out.append(SessionLabel(
            device_id=r["device_id"],
            t_start=float(r["t_start"]),
            t_end=float(r["t_end"]),
            class_label=SessionClass(r["class_label"]),
            presence_freshness_s=float(r.get("presence_freshness_s", DEFAULT_PRESENCE_FRESHNESS_S)),
        ))
    return out


def _presence_for_window(conn: sqlite3.Connection, device_id: str, wt_s: float,
                         freshness_s: float):
    """Most recent l6b probe within [wt - freshness, wt]. Returns (challenged, passed)."""
    lo_ms = int((wt_s - freshness_s) * 1000)
    hi_ms = int(wt_s * 1000)
    row = conn.execute(
        "SELECT classification, reflex_verdict FROM l6b_probe_log "
        "WHERE device_id=? AND probe_ts_ms BETWEEN ? AND ? "
        "ORDER BY probe_ts_ms DESC LIMIT 1",
        (device_id, lo_ms, hi_ms),
    ).fetchone()
    if row is None:
        return False, False  # no challenge bound to this window -> UNKNOWN presence
    classification, reflex_verdict = row[0], row[1]
    passed = (reflex_verdict == "REFLEX_OBSERVED") or (classification == "HUMAN")
    return True, bool(passed)


def _l4_for_record(conn: sqlite3.Connection, record_hash: str):
    if not record_hash:
        return None
    row = conn.execute(
        "SELECT pitl_l4_distance FROM records WHERE record_hash=? LIMIT 1",
        (record_hash,),
    ).fetchone()
    return None if row is None else row[0]


def load_labeled_sessions_from_db(db_path: str, labels: list[SessionLabel]) -> list[LabeledSession]:
    """Assemble REAL LabeledSessions from captured DB rows for each operator label."""
    conn = sqlite3.connect(db_path)
    try:
        sessions: list[LabeledSession] = []
        for lab in labels:
            retina_rows = conn.execute(
                "SELECT record_hash_hex, anomaly_count, created_at FROM retina_event_log "
                "WHERE device_id=? AND created_at BETWEEN ? AND ? ORDER BY created_at ASC",
                (lab.device_id, lab.t_start, lab.t_end),
            ).fetchall()

            sid = f"{lab.class_label.value}_{lab.device_id[:8]}_{int(lab.t_start)}"
            windows = []
            for record_hash, anomaly_count, created_at in retina_rows:
                wt = float(created_at)
                challenged, passed = _presence_for_window(
                    conn, lab.device_id, wt, lab.presence_freshness_s)
                windows.append(LabeledWindow(
                    session_id=sid,
                    ts_ns=int(wt * 1_000_000_000),
                    presence_challenged=challenged,
                    presence_reacted=passed,
                    presence_in_band=passed,
                    device_auth_pass=passed,
                    retina_anomaly_count=int(anomaly_count or 0),
                    l4_distance=_l4_for_record(conn, record_hash),
                    class_label=lab.class_label,
                    provenance=Provenance.REAL,
                    provisional=False,  # real data; scope limit (N=1) is handled at report level
                ))
            sessions.append(LabeledSession(
                session_id=sid, class_label=lab.class_label,
                provenance=Provenance.REAL, windows=windows, provisional=False))
        return sessions
    finally:
        conn.close()
