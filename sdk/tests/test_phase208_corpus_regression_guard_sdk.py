"""
Phase 208 SDK Tests
T208-SDK-1..4: CorpusRegressionGuardResult / VAPICorpusRegressionGuard
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T208-SDK-1: CorpusRegressionGuardResult has required slots ───────────────
def test_T208_sdk_1_dataclass_fields():
    """CorpusRegressionGuardResult has required slots (Phase 208)."""
    from vapi_sdk import CorpusRegressionGuardResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(CorpusRegressionGuardResult)}
    assert "corpus_ratio_regression_guard_enabled" in fields
    assert "guard_active"       in fields
    assert "breakthrough_ratio" in fields
    assert "breakthrough_n"     in fields
    assert "provenance_hash"    in fields
    assert "override_count"     in fields
    assert "timestamp"          in fields
    assert "error"              in fields


# ── T208-SDK-2: CorpusRegressionGuardResult instantiation ────────────────────
def test_T208_sdk_2_result_instantiation():
    """CorpusRegressionGuardResult can be created with breakthrough data."""
    from vapi_sdk import CorpusRegressionGuardResult
    r = CorpusRegressionGuardResult(
        corpus_ratio_regression_guard_enabled = True,
        guard_active     = True,
        breakthrough_ratio = 1.261,
        breakthrough_n   = 11,
        provenance_hash  = "a" * 64,
        override_count   = 0,
        timestamp        = 1712300000.0,
    )
    assert r.corpus_ratio_regression_guard_enabled is True
    assert r.guard_active is True
    assert r.breakthrough_ratio == pytest.approx(1.261)
    assert r.breakthrough_n == 11
    assert len(r.provenance_hash) == 64
    assert r.override_count == 0
    assert r.error is None


# ── T208-SDK-3: VAPICorpusRegressionGuard returns error on network failure ────
def test_T208_sdk_3_client_network_error():
    """VAPICorpusRegressionGuard returns CorpusRegressionGuardResult with error on failure."""
    from vapi_sdk import VAPICorpusRegressionGuard, CorpusRegressionGuardResult
    client = VAPICorpusRegressionGuard("http://localhost:19999", api_key="test")
    result = client.get_status()
    assert isinstance(result, CorpusRegressionGuardResult)
    assert result.error is not None
    assert result.guard_active is False
    assert result.corpus_ratio_regression_guard_enabled is False
    assert result.breakthrough_ratio is None
    assert result.override_count == 0


# ── T208-SDK-4: VAPICorpusRegressionGuard.get_status() parses response ────────
def test_T208_sdk_4_get_status_parses_response():
    """VAPICorpusRegressionGuard.get_status() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPICorpusRegressionGuard, CorpusRegressionGuardResult

    prov_hash = "b" * 64
    body = json.dumps({
        "corpus_ratio_regression_guard_enabled": True,
        "guard_active":      True,
        "breakthrough_ratio": 1.261,
        "breakthrough_n":    11,
        "provenance_hash":   prov_hash,
        "override_count":    2,
        "timestamp":         1712300000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPICorpusRegressionGuard("http://localhost:8080", "test-key")
        result = client.get_status(probe_type="tremor_resting")

    assert result.error is None
    assert result.corpus_ratio_regression_guard_enabled is True, (
        f"Expected True; got {result.corpus_ratio_regression_guard_enabled}"
    )
    assert result.guard_active is True
    assert result.breakthrough_ratio == pytest.approx(1.261)
    assert result.breakthrough_n == 11
    assert result.provenance_hash == prov_hash
    assert result.override_count == 2
    assert result.timestamp == pytest.approx(1712300000.0)
