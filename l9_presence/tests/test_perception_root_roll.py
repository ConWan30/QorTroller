"""LUMEN-4a/4b shared-engine tests — roll_perception_root.

Pins: root determinism + equality with compute_events_root; span filtering; fail-open
(missing DB / empty table / malformed rows) -> (None, stats) NEVER a fabricated root;
record-hash binding stats; the dual-consumer contract (runner + daemon stop both call
this one implementation; the M14 anchor 4f335588... is the live regression check run
at wiring time).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from lumen4a_perception_root import roll_perception_root  # noqa: E402

from bridge.vapi_bridge.retina_state_commitment import compute_events_root  # noqa: E402


def _mk_db(tmp_path, rows):
    db = str(tmp_path / "t.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE retina_event_log (id INTEGER PRIMARY KEY, "
                "events_json TEXT, record_hash_hex TEXT, created_at REAL)")
    con.executemany("INSERT INTO retina_event_log (events_json, record_hash_hex, "
                    "created_at) VALUES (?, ?, ?)", rows)
    con.commit()
    con.close()
    return db


def _ev(t, kind="controller.trigger.onset"):
    return {"type": kind, "t": t, "conf": 1.0}


def test_root_matches_compute_events_root(tmp_path):
    e1, e2, e3 = _ev(0.1), _ev(0.2, "controller.stick.radial_jump"), _ev(0.3)
    db = _mk_db(tmp_path, [
        (json.dumps([e1, e2]), "hashA", 1000.0),
        (json.dumps([e3]), "hashB", 1500.0),
    ])
    root, stats = roll_perception_root(db, 900.0, 2000.0)
    assert root == compute_events_root([e1, e2, e3]).hex()
    assert stats["n_rows"] == 2 and stats["n_events"] == 3
    assert stats["record_hash_bindings"] == 2
    assert stats["event_types"]["controller.trigger.onset"] == 2


def test_span_filter_excludes_out_of_session_rows(tmp_path):
    inside, outside = _ev(0.1), _ev(9.9)
    db = _mk_db(tmp_path, [
        (json.dumps([inside]), "in1", 1000.0),
        (json.dumps([outside]), "out1", 99999.0),      # different session, later
    ])
    root, stats = roll_perception_root(db, 900.0, 2000.0)
    assert stats["n_rows"] == 1
    assert root == compute_events_root([inside]).hex()


def test_missing_db_fails_open():
    root, stats = roll_perception_root("Z:/nope/never.db", 0.0, 1.0)
    assert root is None and "not found" in (stats["error"] or "")


def test_empty_table_fails_open_never_fabricates(tmp_path):
    """The empty-set root exists mathematically; it is deliberately NOT emitted."""
    db = _mk_db(tmp_path, [])
    root, stats = roll_perception_root(db, 0.0, 1e12)
    assert root is None and stats["n_rows"] == 0 and stats["error"] is None


def test_malformed_rows_skipped_honestly(tmp_path):
    good = _ev(0.5)
    db = _mk_db(tmp_path, [
        ("NOT JSON {", "bad1", 1000.0),
        (json.dumps([good]), "good1", 1100.0),
        (None, "null1", 1200.0),
    ])
    root, stats = roll_perception_root(db, 900.0, 2000.0)
    assert stats["n_rows"] == 3 and stats["n_events"] == 1
    assert root == compute_events_root([good]).hex()


def test_determinism(tmp_path):
    rows = [(json.dumps([_ev(i / 10)]), f"h{i}", 1000.0 + i) for i in range(5)]
    db = _mk_db(tmp_path, rows)
    r1, _ = roll_perception_root(db, 900.0, 2000.0)
    r2, _ = roll_perception_root(db, 900.0, 2000.0)
    assert r1 == r2 and r1 is not None
