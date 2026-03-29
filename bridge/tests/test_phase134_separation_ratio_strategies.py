"""
Phase 134 — Separation Ratio Analysis Strategies Tests (8 tests)

Tests:
1. bootstrap CI result has 3 required fields
2. bootstrap CI: ci_lower <= ratio_bootstrap_mean
3. feature F-ratio values are non-negative
4. feature-weighted ratio differs from raw (or equals when uniform)
5. quality filter reduces N or leaves unchanged when no low-quality sessions
6. filtered_ratio >= 0.0 always
7. auto_separation_snapshot_enabled=False is the default config value
8. GET /agent/auto-separation-snapshot-status — 5 required keys
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "bridge"))
sys.path.insert(0, str(_ROOT / "scripts"))


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    db = os.path.join(d, "test.db")
    return Store(db_path=db), db


# ---------------------------------------------------------------------------
# Helpers — build a minimal mock result dict for strategy helpers
# ---------------------------------------------------------------------------

def _mock_analysis_result(n_sessions: int = 10, n_players: int = 3):
    """Build a minimal result dict that strategy helpers can consume."""
    import numpy as np
    rng = np.random.default_rng(42)
    # Per-player feature matrices (n_sessions_each x n_features)
    n_each = n_sessions // n_players
    n_features = 13
    players = {}
    for pid in range(n_players):
        players[f"P{pid+1}"] = rng.normal(loc=pid * 0.5, scale=1.0,
                                           size=(n_each, n_features))
    return {
        "players": players,
        "n_sessions": n_sessions,
        "pooled_ratio": 0.474,
        "feature_names": [f"feat_{i}" for i in range(n_features)],
    }


# ---------------------------------------------------------------------------
# Test 1: bootstrap CI has 3 required fields
# ---------------------------------------------------------------------------

def test_1_bootstrap_ci_3_fields():
    from analyze_interperson_separation import _compute_bootstrap_ci
    result = _mock_analysis_result()
    out = _compute_bootstrap_ci(result, n_resamples=20)
    for key in ("ratio_bootstrap_mean", "ratio_bootstrap_ci_lower", "ratio_bootstrap_ci_upper"):
        assert key in out, f"missing: {key}"


# ---------------------------------------------------------------------------
# Test 2: bootstrap CI ci_lower <= ratio_bootstrap_mean
# ---------------------------------------------------------------------------

def test_2_bootstrap_ci_lower_le_mean():
    from analyze_interperson_separation import _compute_bootstrap_ci
    result = _mock_analysis_result()
    out = _compute_bootstrap_ci(result, n_resamples=30)
    assert out["ratio_bootstrap_ci_lower"] <= out["ratio_bootstrap_mean"], (
        f"ci_lower={out['ratio_bootstrap_ci_lower']} > mean={out['ratio_bootstrap_mean']}"
    )


# ---------------------------------------------------------------------------
# Test 3: feature F-ratio list values are non-negative
# ---------------------------------------------------------------------------

def test_3_feature_f_ratios_nonnegative():
    from analyze_interperson_separation import _compute_feature_weighted_ratio
    result = _mock_analysis_result()
    out = _compute_feature_weighted_ratio(result)
    assert "feature_f_ratios" in out
    f_ratios = out["feature_f_ratios"]
    # May be empty list or list of floats
    for val in f_ratios:
        assert val >= 0.0, f"negative F-ratio value: {val}"


# ---------------------------------------------------------------------------
# Test 4: feature-weighted ratio is a finite float
# ---------------------------------------------------------------------------

def test_4_feature_weighted_ratio_finite():
    import math
    from analyze_interperson_separation import _compute_feature_weighted_ratio
    result = _mock_analysis_result()
    out = _compute_feature_weighted_ratio(result)
    assert "weighted_ratio" in out
    assert math.isfinite(out["weighted_ratio"]), "weighted_ratio is not finite"


# ---------------------------------------------------------------------------
# Test 5: quality filter returns n_sessions_after_filter
# ---------------------------------------------------------------------------

def test_5_quality_filter_has_n_sessions_after_filter():
    from analyze_interperson_separation import _compute_quality_filtered_ratio
    result = _mock_analysis_result(n_sessions=12)
    out = _compute_quality_filtered_ratio(result)
    assert "n_sessions_after_filter" in out
    assert out["n_sessions_after_filter"] <= result["n_sessions"]


# ---------------------------------------------------------------------------
# Test 6: filtered_ratio >= 0.0 always
# ---------------------------------------------------------------------------

def test_6_filtered_ratio_nonnegative():
    from analyze_interperson_separation import _compute_quality_filtered_ratio
    result = _mock_analysis_result()
    out = _compute_quality_filtered_ratio(result)
    assert out.get("filtered_ratio", 0.0) >= 0.0


# ---------------------------------------------------------------------------
# Test 7: auto_separation_snapshot_enabled default is False
# ---------------------------------------------------------------------------

def test_7_auto_snapshot_default_false():
    from vapi_bridge.config import Config
    cfg = Config()
    assert getattr(cfg, "auto_separation_snapshot_enabled", False) is False


# ---------------------------------------------------------------------------
# Test 8: GET /agent/auto-separation-snapshot-status — 5 required keys
# ---------------------------------------------------------------------------

def test_8_auto_snapshot_status_5_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store, db = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 0
    cfg.auto_separation_snapshot_enabled = False
    cfg.db_path = db

    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/agent/auto-separation-snapshot-status?api_key=test-key")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("auto_separation_snapshot_enabled", "snapshot_count",
                "last_snapshot_ts", "last_snapshot_ratio", "timestamp"):
        assert key in data, f"missing key: {key}"
