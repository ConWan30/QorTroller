"""Tests for the Phase 2 real-capture loader (real_sessions.py) against a
temp sqlite fixture mimicking the bridge schema. Windows WAL gotcha: use
tempfile.mkdtemp(), not TemporaryDirectory.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from l9_presence.adversarial.real_sessions import (  # noqa: E402
    SessionLabel,
    load_labeled_sessions_from_db,
)
from l9_presence.adversarial.session_class import Provenance, SessionClass  # noqa: E402
from l9_presence.adversarial.signal_adapter import evaluate_window  # noqa: E402
from l9_presence.presence_retina_consistency import ConsistencyVerdict  # noqa: E402

_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"


def _make_db() -> str:
    d = tempfile.mkdtemp(prefix="vapi_real_sessions_")
    path = os.path.join(d, "bridge.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE retina_event_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "device_id TEXT, record_hash_hex TEXT, anomaly_count INTEGER, created_at REAL)")
    conn.execute("CREATE TABLE l6b_probe_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "device_id TEXT, probe_ts_ms INTEGER, classification TEXT, reflex_verdict TEXT)")
    conn.execute("CREATE TABLE records (record_hash TEXT PRIMARY KEY, device_id TEXT, "
                 "pitl_l4_distance REAL, created_at REAL)")
    t0 = 1_000_000.0  # epoch seconds
    # window A @ t0+10: clean human -> recent REFLEX_OBSERVED probe + anomaly 0 + nominal L4
    conn.execute("INSERT INTO retina_event_log (device_id, record_hash_hex, anomaly_count, created_at) "
                 "VALUES (?,?,?,?)", (_DEV, "rhA", 0, t0 + 10))
    conn.execute("INSERT INTO records VALUES (?,?,?,?)", ("rhA", _DEV, 2.0, t0 + 10))
    conn.execute("INSERT INTO l6b_probe_log (device_id, probe_ts_ms, classification, reflex_verdict) "
                 "VALUES (?,?,?,?)", (_DEV, int((t0 + 5) * 1000), "HUMAN", "REFLEX_OBSERVED"))
    # window B @ t0+200: anomaly present but NO probe within freshness -> presence UNKNOWN
    conn.execute("INSERT INTO retina_event_log (device_id, record_hash_hex, anomaly_count, created_at) "
                 "VALUES (?,?,?,?)", (_DEV, "rhB", 3, t0 + 200))
    conn.execute("INSERT INTO records VALUES (?,?,?,?)", ("rhB", _DEV, 1.5, t0 + 200))
    conn.commit()
    conn.close()
    return path


def test_loader_assembles_windows_and_binds():
    path = _make_db()
    labels = [SessionLabel(device_id=_DEV, t_start=1_000_000.0, t_end=1_000_400.0,
                           class_label=SessionClass.HUMAN_CLEAN, presence_freshness_s=30.0)]
    sessions = load_labeled_sessions_from_db(path, labels)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.provenance is Provenance.REAL and s.provisional is False
    assert len(s.windows) == 2

    wA, wB = s.windows[0], s.windows[1]
    # window A: recent REFLEX_OBSERVED probe -> challenged + passed; anomaly 0; L4 nominal
    assert wA.presence_challenged is True and wA.presence_reacted is True
    assert wA.retina_anomaly_count == 0 and wA.l4_distance == 2.0
    # window B: no probe within 30s -> UNKNOWN presence; anomaly 3
    assert wB.presence_challenged is False and wB.retina_anomaly_count == 3


def test_loader_windows_run_through_engine():
    path = _make_db()
    labels = [SessionLabel(device_id=_DEV, t_start=1_000_000.0, t_end=1_000_400.0,
                           class_label=SessionClass.HUMAN_CLEAN)]
    s = load_labeled_sessions_from_db(path, labels)[0]
    vA = evaluate_window(s.windows[0]).verdict
    vB = evaluate_window(s.windows[1]).verdict
    # A: PRESENT + PLAUSIBLE -> CONSISTENT_HUMAN
    assert vA is ConsistencyVerdict.CONSISTENT_HUMAN
    # B: UNKNOWN presence + IMPLAUSIBLE trajectory -> single-oracle -> INDETERMINATE
    assert vB is ConsistencyVerdict.INDETERMINATE


def test_empty_window_yields_empty_session():
    path = _make_db()
    labels = [SessionLabel(device_id=_DEV, t_start=9_000_000.0, t_end=9_000_100.0,
                           class_label=SessionClass.PRO_SKILL)]
    s = load_labeled_sessions_from_db(path, labels)[0]
    assert s.windows == []
