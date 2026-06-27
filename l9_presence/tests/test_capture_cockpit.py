"""Tests for the capture cockpit's read-only DB helpers + one-frame render."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import capture_cockpit as cc  # noqa: E402

_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"


def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="vapi_cockpit_"), "bridge.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE retina_event_log (id INTEGER PRIMARY KEY, device_id TEXT, "
                 "record_hash_hex TEXT, anomaly_count INTEGER, created_at REAL)")
    conn.execute("CREATE TABLE l6b_probe_log (id INTEGER PRIMARY KEY, device_id TEXT, "
                 "probe_ts_ms INTEGER, classification TEXT, reflex_verdict TEXT)")
    t0 = 1000.0
    # 3 retina windows in [t0, t0+100]; only the first is within 30s of the probe
    for i, t in enumerate((t0 + 10, t0 + 50, t0 + 80)):
        conn.execute("INSERT INTO retina_event_log VALUES (?,?,?,?,?)",
                     (i, _DEV, f"rh{i}", 0, t))
    # a probe 5s before window@t0+10 (binds it), none near the others
    conn.execute("INSERT INTO l6b_probe_log VALUES (?,?,?,?,?)",
                 (1, _DEV, int((t0 + 6) * 1000), "HUMAN", "REFLEX_OBSERVED"))
    conn.commit()
    conn.close()
    return path


def test_counts():
    conn = cc._connect_ro(_db())
    assert cc.count_retina_windows(conn, _DEV, 1000.0, 1100.0) == 3
    assert cc.count_presence_probes(conn, _DEV, 1000.0, 1100.0) == 1
    conn.close()


def test_binding_coverage():
    conn = cc._connect_ro(_db())
    rt, bound, pct = cc.binding_coverage(conn, _DEV, 1000.0, 1100.0, freshness_s=30.0)
    assert rt == 3 and bound == 1   # only window@1010 has a probe within 30s before it
    assert pct == round(100.0 / 3, 1)
    conn.close()


def test_binding_coverage_empty():
    conn = cc._connect_ro(_db())
    assert cc.binding_coverage(conn, _DEV, 9000.0, 9100.0, 30.0) == (0, 0, 0.0)
    conn.close()


def test_render_once_no_crash():
    mf = os.path.join(tempfile.mkdtemp(prefix="vapi_cockpit_mf_"), "sessions.json")
    args = argparse.Namespace(
        device=_DEV, db=_db(), manifest=mf,
        bridge="http://127.0.0.1:9", api_key="x", freshness=30.0, no_color=True,
    )
    out = cc.render(args, cc._color(False))
    assert "Capture Cockpit" in out
    assert "BRIDGE" in out and "DB" in out and "READY" in out
