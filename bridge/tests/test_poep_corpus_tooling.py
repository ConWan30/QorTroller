"""A2A-POEP-CORPUS-TOOLING T-CT-1..6 — player stamp, audit no-clobber, latency report pure fns."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def test_t_ct_1_player_column_migration_idempotent():
    """T-CT-1: Store init adds player column; second open does not raise."""
    from bridge.vapi_bridge.store import Store

    d = tempfile.mkdtemp()
    db = str(Path(d) / "t.db")
    s1 = Store(db)
    with s1._conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(l6b_probe_log)").fetchall()}
    assert "player" in cols
    s2 = Store(db)
    with s2._conn() as conn:
        cols2 = {r[1] for r in conn.execute("PRAGMA table_info(l6b_probe_log)").fetchall()}
    assert "player" in cols2


def test_t_ct_2_persist_writes_player():
    """T-CT-2: insert_l6b_probe stores player tag."""
    from bridge.vapi_bridge.store import Store

    d = tempfile.mkdtemp()
    db = str(Path(d) / "t.db")
    store = Store(db)
    rid = store.insert_l6b_probe(
        device_id="dev1",
        probe_ts_ms=1,
        latency_ms=300.0,
        classification="HUMAN",
        accel_delta_peak=1500.0,
        reflex_verdict="REFLEX_OBSERVED",
        policy_ref="edge_operator_reflex_v1",
        player="P2",
    )
    assert rid >= 1
    with store._conn() as conn:
        row = conn.execute(
            "SELECT player, policy_ref FROM l6b_probe_log WHERE id=?", (rid,)
        ).fetchone()
    assert row["player"] == "P2"
    assert row["policy_ref"] == "edge_operator_reflex_v1"


def test_t_ct_3_double_capture_no_clobber():
    """T-CT-3: two same-day audit paths differ; first file survives second write."""
    from scripts.poep_live_capture import audit_capture_path

    d = Path(tempfile.mkdtemp())
    t1 = datetime(2026, 7, 16, 22, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 7, 16, 22, 20, 0, tzinfo=timezone.utc)
    p1 = audit_capture_path(d, "P1", when=t1)
    p2 = audit_capture_path(d, "P1", when=t2)
    assert p1 != p2
    p1.write_text(json.dumps({"block": 1, "n": 8}), encoding="utf-8")
    p2.write_text(json.dumps({"block": 2, "n": 8}), encoding="utf-8")
    assert json.loads(p1.read_text(encoding="utf-8"))["block"] == 1
    assert "221000" in p1.name
    assert "222000" in p2.name


def test_t_ct_4_held_out_split_lengths():
    from scripts.poep_latency_report import held_out_split

    xs = list(range(10))  # 0..9
    train, hold = held_out_split(xs, train_frac=0.70)
    assert len(train) == 7
    assert len(hold) == 3
    assert train + hold == xs
    train1, hold1 = held_out_split([42.0])
    assert train1 == [42.0] and hold1 == []


def test_t_ct_5_draft_ceiling():
    from scripts.poep_latency_report import draft_ceiling

    assert draft_ceiling(427.8, band_hi=450.0, margin_ms=15.0) == 443
    assert draft_ceiling(440.0, band_hi=450.0, margin_ms=15.0) == 450  # min(450, 455)
    assert draft_ceiling(100.0, band_hi=450.0, margin_ms=15.0) == 115


def test_t_ct_6_band_constants_match_live_verify():
    from l9_presence.poep_live_verify import REACTION_BAND_MS
    from scripts import poep_latency_report as rep

    assert rep.BAND_LO == REACTION_BAND_MS[0]
    assert rep.BAND_HI == REACTION_BAND_MS[1]
    assert REACTION_BAND_MS == (80.0, 450.0)
