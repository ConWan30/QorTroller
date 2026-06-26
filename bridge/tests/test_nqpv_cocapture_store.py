"""Cycle-33 — NQPV co-capture persistence (Option B: dedicated nqpv_cocapture_log table).

Integration tests over a real temp SQLite Store: insert_nqpv_cocapture round-trips through
get_nqpv_cocapture_rows, tri-state bools survive (NULL=abstain), and the study loader's
load_human_corpus_from_cocapture consumes the persisted rows into fuse()-ready corpus records.
"""
from __future__ import annotations

import os
import tempfile

from vapi_bridge.store import Store
from vapi_bridge.nqpv_corpus_loader import (
    LABEL_HUMAN,
    fetch_cocapture_rows,
    load_human_corpus_from_cocapture,
    to_fuse_inputs,
)


def _make_store() -> tuple:
    tmpdir = tempfile.mkdtemp()
    return Store(os.path.join(tmpdir, "test_nqpv_cocap.db")), tmpdir


def test_table_exists_and_roundtrips_full_oracle_row():
    store, _ = _make_store()
    store.insert_nqpv_cocapture(
        device_id="devA", record_hash_hex="hashA",
        nqpv_cco_tier="P-T3", nqpv_l4l5l6_ok=True, nqpv_poep_present=False,
        nqpv_retina_controller_signal="CONTROLLER_CLEAN",
        nqpv_retina_coupled_verdict="COUPLED_CLEAN", humanity_prob=0.82,
    )
    rows = store.get_nqpv_cocapture_rows(limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r["device_id"] == "devA"
    assert r["record_hash_hex"] == "hashA"
    assert r["nqpv_cco_tier"] == "P-T3"
    assert r["nqpv_l4l5l6_ok"] == 1          # bool -> INTEGER
    assert r["nqpv_poep_present"] == 0
    assert r["nqpv_retina_controller_signal"] == "CONTROLLER_CLEAN"
    assert abs(r["humanity_prob"] - 0.82) < 1e-9


def test_tristate_none_persists_as_null_abstain():
    store, _ = _make_store()
    store.insert_nqpv_cocapture(
        device_id="devB", record_hash_hex="hashB",
        nqpv_cco_tier=None, nqpv_l4l5l6_ok=None, nqpv_poep_present=None,
    )
    r = store.get_nqpv_cocapture_rows()[0]
    assert r["nqpv_cco_tier"] is None
    assert r["nqpv_l4l5l6_ok"] is None       # NULL = ABSTAIN, not fabricated 0
    assert r["nqpv_poep_present"] is None


def test_device_scoped_query():
    store, _ = _make_store()
    store.insert_nqpv_cocapture(device_id="d1", record_hash_hex="r1", nqpv_l4l5l6_ok=True)
    store.insert_nqpv_cocapture(device_id="d2", record_hash_hex="r2", nqpv_l4l5l6_ok=False)
    assert len(store.get_nqpv_cocapture_rows(device_id="d1")) == 1
    assert store.get_nqpv_cocapture_rows(device_id="d1")[0]["record_hash_hex"] == "r1"


def test_loader_consumes_persisted_cocapture_rows():
    store, _ = _make_store()
    store.insert_nqpv_cocapture(
        device_id="devC", record_hash_hex="hashC",
        nqpv_cco_tier="P-T3", nqpv_l4l5l6_ok=True, nqpv_poep_present=None,
        nqpv_retina_controller_signal="CONTROLLER_CLEAN",
    )
    [rec] = load_human_corpus_from_cocapture(store)
    assert rec.label == LABEL_HUMAN
    assert rec.source == "cocapture"
    assert rec.device_id == "devC"
    assert rec.record_hash == "hashC"        # record_hash_hex normalized to record_hash
    assert rec.cco_tier == "P-T3"
    assert rec.l4_l5_l6_ok is True
    assert rec.poep_present is None           # abstain preserved end-to-end
    # controller-lobe stays metadata; never becomes the fuse() screen-lobe input
    assert rec.retina_controller_signal == "CONTROLLER_CLEAN"
    assert to_fuse_inputs(rec)["retina_report"] is None


def test_fetch_cocapture_rows_graceful_on_old_store():
    # the I/O boundary must not explode if a store lacks the method (forward/backward safety)
    class _Bare:
        pass
    assert fetch_cocapture_rows(_Bare()) == []
