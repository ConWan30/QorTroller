"""
Phase 192 — CorpusDataCuratorAgent (agent #35) bridge tests.

Tests (14 total, 2 per task):
  T192-1: data_provenance_dag table created by Store.__init__
  T192-2: insert_provenance_node / get_provenance_chain round-trip

  T192-3: corpus_entropy_log table created by Store.__init__
  T192-4: insert_corpus_entropy / get_latest_corpus_entropy round-trip

  T192-5: erasure_certificate_log table created by Store.__init__
  T192-6: compute_erasure_certificate returns SHA-256 prefixed hex; insert_erasure_certificate stores it

  T192-7: federation_corpus_quality_log table created by Store.__init__
  T192-8: insert_federation_corpus_quality / get_federated_corpus_quality round-trip

  T192-9: feature_correlation_log table created by Store.__init__
  T192-10: insert_feature_correlation / get_feature_correlation round-trip

  T192-11: data_readiness_certificate_log table created by Store.__init__
  T192-12: insert_data_readiness_certificate / get_latest_data_readiness_certificate round-trip

  T192-13: session_contribution_weight_log table created by Store.__init__
  T192-14: insert_session_contribution_weight / get_session_weight / get_session_weights round-trip
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import time
import types as _types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Stubs for optional heavy imports
# ---------------------------------------------------------------------------

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402


@pytest.fixture()
def tmp_db():
    _d = tempfile.mkdtemp()
    _p = os.path.join(_d, "test_phase192.db")
    yield _p


@pytest.fixture()
def store(tmp_db):
    return Store(db_path=tmp_db)


@pytest.fixture()
def cfg():
    return Config()


# ===========================================================================
# Task 1: Provenance DAG
# ===========================================================================

def test_t192_1_provenance_dag_table_created(store):
    """T192-1: data_provenance_dag table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "data_provenance_dag" in tables


def test_t192_2_provenance_chain_roundtrip(store):
    """T192-2: insert_provenance_node (dict API) / get_provenance_chain round-trip."""
    # Insert root node via dict API
    root_hash = hashlib.sha256(b"root_session_P1").hexdigest()
    inserted_id = store.insert_provenance_node({
        "node_id": "root_P1_001",
        "node_type": "calibration_session",
        "source_table": "separation_defensibility_log",
        "source_row_id": 1,
        "source_hash": root_hash,
        "parent_node_id": None,
        "edge_type": None,
        "phase_produced": 192,
        "player_id": "P1",
        "on_chain_ref": None,
    })
    assert inserted_id == "root_P1_001"

    # Insert child node linked to root
    child_hash = hashlib.sha256(b"defensibility_P1").hexdigest()
    store.insert_provenance_node({
        "node_id": "child_P1_001",
        "node_type": "defensibility_check",
        "source_table": "separation_defensibility_log",
        "source_row_id": 2,
        "source_hash": child_hash,
        "parent_node_id": "root_P1_001",
        "edge_type": "produces",
        "phase_produced": 192,
        "player_id": "P1",
        "on_chain_ref": None,
    })

    # get_provenance_chain walks from leaf to root
    chain = store.get_provenance_chain("child_P1_001", max_depth=20)
    assert len(chain) >= 1
    node_ids = [n.get("node_id", "") for n in chain]
    assert "child_P1_001" in node_ids


# ===========================================================================
# Task 2: Corpus Entropy Monitor
# ===========================================================================

def test_t192_3_corpus_entropy_table_created(store):
    """T192-3: corpus_entropy_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "corpus_entropy_log" in tables


def test_t192_4_corpus_entropy_roundtrip(store):
    """T192-4: insert_corpus_entropy / get_latest_corpus_entropy round-trip."""
    per_player = json.dumps({"P1": 2.1, "P2": 2.5, "P3": 2.4})
    per_feature = json.dumps({"micro_tremor_accel_variance": 1.8, "stick_autocorr_lag1": 2.3})
    low_feats = json.dumps([])

    row_id = store.insert_corpus_entropy(
        score=2.34,
        per_player_json=per_player,
        per_feature_json=per_feature,
        low_entropy_features_json=low_feats,
        clustering_warning=False,
        n_sessions=20,
        session_type_filter="touchpad_corners",
    )
    assert row_id > 0

    row = store.get_latest_corpus_entropy(session_type="touchpad_corners")
    assert row is not None
    assert abs(row["corpus_entropy_score"] - 2.34) < 0.001
    assert row["clustering_warning"] is False
    assert row["n_sessions_analyzed"] == 20


# ===========================================================================
# Task 3: Proof-of-Erasure Certificate
# ===========================================================================

def test_t192_5_erasure_certificate_table_created(store):
    """T192-5: erasure_certificate_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "erasure_certificate_log" in tables


def test_t192_6_erasure_certificate_sha256(store):
    """T192-6: compute_erasure_certificate returns sha256:-prefixed hex; insert stores it."""
    erased_tables = {
        "separation_defensibility_log": [1, 2, 3],
        "session_contribution_weight_log": [4, 5],
    }
    ts_ns = int(time.time_ns())
    cert = store.compute_erasure_certificate(
        device_id="device_P2_test",
        player_id="P2",
        erased_tables=erased_tables,
        post_erasure_ratio=0.569,
        ts_ns=ts_ns,
    )
    # Must be sha256:-prefixed + 64-char hex
    assert cert.startswith("sha256:"), f"Certificate should start with 'sha256:': {cert!r}"
    hex_part = cert[len("sha256:"):]
    assert len(hex_part) == 64
    int(hex_part, 16)  # validates hex

    row_id = store.insert_erasure_certificate(
        certificate_hash=cert,
        device_id="device_P2_test",
        player_id="P2",
        erased_tables_json=json.dumps(list(erased_tables.keys())),
        erased_row_count=5,
        post_erasure_ratio=0.569,
        ts_ns=ts_ns,
    )
    assert row_id > 0

    row = store.get_erasure_certificate("device_P2_test")
    assert row is not None
    assert row["player_id"] == "P2"
    assert row["certificate_hash"] == cert


# ===========================================================================
# Task 4: Federated Corpus Quality
# ===========================================================================

def test_t192_7_federation_quality_table_created(store):
    """T192-7: federation_corpus_quality_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "federation_corpus_quality_log" in tables


def test_t192_8_federation_quality_roundtrip(store):
    """T192-8: insert_federation_corpus_quality / get_federated_corpus_quality round-trip."""
    bridge_hash = hashlib.sha256(b"bridge_test_001").hexdigest()[:16]
    row_id = store.insert_federation_corpus_quality(
        bridge_id_hash=bridge_hash,
        session_type="touchpad_corners",
        n_sessions=15,
        entropy_score=2.31,
        stationarity_score=0.85,
        centroid_velocity_mean=0.003,
        received_at_ts=int(time.time()),
    )
    assert row_id > 0

    rows = store.get_federated_corpus_quality(session_type="touchpad_corners", limit=5)
    assert len(rows) >= 1
    assert rows[0]["bridge_id_hash"] == bridge_hash
    assert rows[0]["n_sessions"] == 15
    assert abs(rows[0]["entropy_score"] - 2.31) < 0.001


# ===========================================================================
# Task 5: Cross-Feature Temporal Correlation
# ===========================================================================

def test_t192_9_feature_correlation_table_created(store):
    """T192-9: feature_correlation_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "feature_correlation_log" in tables


def test_t192_10_feature_correlation_roundtrip(store):
    """T192-10: insert_feature_correlation / get_feature_correlation round-trip."""
    # Minimal upper-triangle correlation matrix (stored as JSON string)
    corr_upper = json.dumps([[1.0, 0.42], [0.42, 1.0]])
    high_pairs = json.dumps([{"pair": ("micro_tremor_accel_variance", "stick_autocorr_lag1"),
                               "r": 0.42}])
    row_id = store.insert_feature_correlation(
        player_id="P1",
        session_type="touchpad_corners",
        n_sessions_used=6,
        correlation_upper_tri=corr_upper,
        high_correlation_pairs=high_pairs,
        frobenius_vs_p1=None,
        frobenius_vs_p2=0.71,
        frobenius_vs_p3=0.83,
        correlation_separable=True,
    )
    assert row_id > 0

    row = store.get_feature_correlation(player_id="P1", session_type="touchpad_corners")
    assert row is not None
    assert row["player_id"] == "P1"
    assert row["n_sessions_used"] == 6
    assert row["correlation_separable"] is True


# ===========================================================================
# Task 6: Data Readiness Certificate
# ===========================================================================

def test_t192_11_data_readiness_table_created(store):
    """T192-11: data_readiness_certificate_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "data_readiness_certificate_log" in tables


def test_t192_12_data_readiness_roundtrip(store):
    """T192-12: insert_data_readiness_certificate / get_latest round-trip."""
    dims = {
        "separation_ok": True,
        "l4_calibration_ok": True,
        "vhp_enrolled_ok": False,
        "erasure_compliant": True,
    }
    dims_json = json.dumps(dims)
    cert_hash = "sha256:" + hashlib.sha256(dims_json.encode()).hexdigest()
    ts_ns = int(time.time_ns())
    row_id = store.insert_data_readiness_certificate(
        certificate_hash=cert_hash,
        certification_status="NOT_READY",
        blocking_failures=json.dumps(["vhp_enrolled_ok"]),
        advisory_warnings=json.dumps([]),
        dimension_results=dims_json,
        separation_ratio=0.569,
        valid_until_ts=int(time.time()) + 86400,
        ts_ns=ts_ns,
    )
    assert row_id > 0

    row = store.get_latest_data_readiness_certificate()
    assert row is not None
    assert row["certificate_hash"] == cert_hash
    assert row["certification_status"] == "NOT_READY"
    assert abs(row["separation_ratio"] - 0.569) < 0.001


# ===========================================================================
# Task 7: Session Contribution Weights
# ===========================================================================

def test_t192_13_contribution_weight_table_created(store):
    """T192-13: session_contribution_weight_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "session_contribution_weight_log" in tables


def test_t192_14_contribution_weight_roundtrip(store):
    """T192-14: insert_session_contribution_weight / get_session_weight / get_session_weights."""
    _LAMBDA = math.log(2) / 90.0
    age_days = 10.0
    tbd_weight = math.exp(-_LAMBDA * age_days)
    type_mult = 1.2
    stat_mult = 1.0
    effective = tbd_weight * type_mult * stat_mult

    session_file = "touchpad_corners_P3_007.json"
    store.insert_session_contribution_weight(
        session_file=session_file,
        player_id="P3",
        session_type="touchpad_corners",
        session_captured_at_ts=int(time.time()) - int(age_days * 86400),
        age_days=age_days,
        tbd_weight=tbd_weight,
        type_multiplier=type_mult,
        stationarity_multiplier=stat_mult,
        effective_weight=effective,
    )

    # Single-file lookup returns float
    w = store.get_session_weight(session_file=session_file)
    assert abs(w - effective) < 1e-6

    # Player-level lookup returns list
    rows = store.get_session_weights(player_id="P3")
    assert len(rows) >= 1
    assert rows[0]["session_file"] == session_file
    assert abs(rows[0]["effective_weight"] - effective) < 1e-6
