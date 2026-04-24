"""
bridge/tests/test_phase229_ait_separation.py
Phase 229 — AIT (Active Isometric Trigger) Separation (8 tests)

T229-1: insert_ait_session() stores row; get_ait_separation_status() returns it correctly
T229-2: get_ait_separation_status() returns disabled defaults when table empty
T229-3: GET /agent/ait-separation-status returns 200 with required keys
T229-4: separation_ratio and all_pairs_above_1 match stored values
T229-5: n_sessions and pair_distances returned correctly
T229-6: ait_separation_enabled=True reflects config when row exists
T229-7: multiple inserts; GET returns latest row
T229-8: inter_player_mean / intra_player_mean / loo_accuracy returned correctly
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

import types
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.messages"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

import os
import sqlite3
import tempfile


def make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    return Store(os.path.join(tmp_dir, "test_phase229.db"))


def make_cfg(**overrides):
    from vapi_bridge.config import Config
    cfg = Config()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


_SAMPLE_PAIRS = {"P1vP2": 1.850, "P1vP3": 1.846, "P2vP3": 1.349}


def _insert_sample(store, n=24, ratio=1.199, all_pairs=True, date="2026-04-18"):
    return store.insert_ait_session(
        n_sessions        = n,
        n_per_player      = {"P1": 6, "P2": 5, "P3": 13},
        separation_ratio  = ratio,
        all_pairs_above_1 = all_pairs,
        inter_player_mean = 1.682,
        intra_player_mean = 0.991,
        loo_accuracy      = 0.667,
        cov_mode          = "full",
        pair_distances    = _SAMPLE_PAIRS,
        analysis_date     = date,
    )


# ---------------------------------------------------------------------------
# T229-1: insert + retrieve round-trip
# ---------------------------------------------------------------------------

def test_t229_1_insert_and_retrieve(tmp_path):
    """insert_ait_session() stores a row; get_ait_separation_status() retrieves it."""
    store = make_store(str(tmp_path))
    row_id = _insert_sample(store)
    assert row_id > 0

    status = store.get_ait_separation_status()
    assert status["n_sessions"] == 24
    assert abs(status["separation_ratio"] - 1.199) < 1e-6
    assert status["all_pairs_above_1"] is True
    assert status["analysis_date"] == "2026-04-18"


# ---------------------------------------------------------------------------
# T229-2: empty table returns disabled defaults
# ---------------------------------------------------------------------------

def test_t229_2_empty_table_returns_defaults(tmp_path):
    """get_ait_separation_status() returns ait_separation_enabled=False when no rows."""
    store = make_store(str(tmp_path))
    status = store.get_ait_separation_status()

    assert status["ait_separation_enabled"] is False
    assert status["n_sessions"] == 0
    assert status["separation_ratio"] == 0.0
    assert status["all_pairs_above_1"] is False
    assert status["last_run_ts"] is None


# ---------------------------------------------------------------------------
# T229-3: GET /agent/ait-separation-status returns 200 with required keys
# ---------------------------------------------------------------------------

def test_t229_3_endpoint_returns_200_with_keys(tmp_path):
    """GET /agent/ait-separation-status returns HTTP 200 with at least 8 expected keys."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    _insert_sample(store)

    # Clear OPERATOR_API_KEY so _check_read_key is a no-op (fail-open when unconfigured)
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        cfg = make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/ait-separation-status")

    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "ait_separation_enabled", "n_sessions", "separation_ratio",
        "all_pairs_above_1", "inter_player_mean", "intra_player_mean",
        "loo_accuracy", "timestamp",
    ):
        assert key in body, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# T229-4: separation_ratio and all_pairs_above_1 match stored values
# ---------------------------------------------------------------------------

def test_t229_4_ratio_and_all_pairs_match(tmp_path):
    """separation_ratio and all_pairs_above_1 in GET response match inserted values."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    _insert_sample(store, ratio=1.199, all_pairs=True)

    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        cfg = make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        body = client.get("/agent/ait-separation-status").json()

    assert abs(body["separation_ratio"] - 1.199) < 1e-4
    assert body["all_pairs_above_1"] is True


# ---------------------------------------------------------------------------
# T229-5: n_sessions and pair_distances returned correctly
# ---------------------------------------------------------------------------

def test_t229_5_n_sessions_and_pair_distances(tmp_path):
    """n_sessions and pair_distances are returned correctly from the status endpoint."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    _insert_sample(store)

    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        cfg = make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        body = client.get("/agent/ait-separation-status").json()

    assert body["n_sessions"] == 24
    pd = body.get("pair_distances", {})
    assert abs(pd.get("P1vP2", 0) - 1.850) < 1e-4
    assert abs(pd.get("P2vP3", 0) - 1.349) < 1e-4


# ---------------------------------------------------------------------------
# T229-6: ait_separation_enabled=True reflects config when row exists
# ---------------------------------------------------------------------------

def test_t229_6_enabled_flag_reflects_config(tmp_path):
    """ait_separation_enabled=True in response when config flag is True and rows exist."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    _insert_sample(store)

    # AIT_SEPARATION_ENABLED defaults to True; clear key so endpoint is reachable
    with unittest.mock.patch.dict(
        os.environ, {"OPERATOR_API_KEY": "", "AIT_SEPARATION_ENABLED": "true"}, clear=False
    ):
        cfg = make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        body = client.get("/agent/ait-separation-status").json()

    assert body["ait_separation_enabled"] is True


# ---------------------------------------------------------------------------
# T229-7: multiple inserts; GET returns latest row
# ---------------------------------------------------------------------------

def test_t229_7_multiple_inserts_returns_latest(tmp_path):
    """When multiple rows exist, GET /agent/ait-separation-status returns the most recent."""
    store = make_store(str(tmp_path))
    cfg = make_cfg()

    _insert_sample(store, n=18, ratio=0.980, all_pairs=False, date="2026-04-10")
    _insert_sample(store, n=24, ratio=1.199, all_pairs=True,  date="2026-04-18")

    status = store.get_ait_separation_status()
    assert status["n_sessions"] == 24
    assert abs(status["separation_ratio"] - 1.199) < 1e-4
    assert status["all_pairs_above_1"] is True
    assert status["analysis_date"] == "2026-04-18"


# ---------------------------------------------------------------------------
# T229-8: inter/intra/loo_accuracy fields returned correctly
# ---------------------------------------------------------------------------

def test_t229_8_inter_intra_loo_accuracy(tmp_path):
    """inter_player_mean, intra_player_mean and loo_accuracy are returned correctly."""
    store = make_store(str(tmp_path))
    row_id = _insert_sample(store)
    assert row_id > 0

    status = store.get_ait_separation_status()
    assert abs(status["inter_player_mean"] - 1.682) < 1e-4
    assert abs(status["intra_player_mean"] - 0.991) < 1e-4
    assert abs(status["loo_accuracy"] - 0.667) < 1e-4
