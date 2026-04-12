"""
Phase 194 SDK tests — CoherenceFingerprintRegistry result classes.

Tests (4 total):
  T194S-1: CoherenceFingerprintResult has all expected slots; zero defaults
  T194S-2: VAPICoherenceFingerprint.get_status() maps API body correctly
  T194S-3: maturity_penalty stored as float; top_rules stored as JSON string
  T194S-4: get_status() error path returns CoherenceFingerprintResult with error set
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import (  # noqa: E402
    CoherenceFingerprintResult,
    VAPICoherenceFingerprint,
)


# ---------------------------------------------------------------------------
# T194S-1: slots and zero defaults
# ---------------------------------------------------------------------------

def test_t194s_1_fingerprint_result_slots():
    """T194S-1: CoherenceFingerprintResult has all expected slots with zero defaults."""
    r = CoherenceFingerprintResult()
    expected = [
        "total_rules", "persistent_count", "total_occurrences",
        "maturity_penalty", "top_rules", "n_promote_threshold", "error",
    ]
    for slot in expected:
        assert hasattr(r, slot), f"CoherenceFingerprintResult missing slot: {slot}"

    assert r.total_rules == 0
    assert r.persistent_count == 0
    assert r.total_occurrences == 0
    assert r.maturity_penalty == 0.0
    assert r.top_rules == "[]"
    assert r.n_promote_threshold == 3
    assert r.error == ""


# ---------------------------------------------------------------------------
# T194S-2: get_status() maps API body
# ---------------------------------------------------------------------------

def test_t194s_2_get_status_maps_body():
    """T194S-2: VAPICoherenceFingerprint.get_status() maps API body correctly."""
    client = VAPICoherenceFingerprint("http://localhost:9999", api_key="test")

    top_rules = [
        {
            "rule_name":       "RENEWAL_WITHOUT_ATTESTATION",
            "failure_mode":    "CONTRADICTION",
            "occurrence_count": 5,
            "persistent":      1,
            "first_seen_at":   "2026-04-11T00:00:00",
            "last_seen_at":    "2026-04-11T12:00:00",
        }
    ]
    api_body = {
        "total_rules":         3,
        "persistent_count":    2,
        "total_occurrences":   11,
        "maturity_penalty":    0.20,
        "top_rules":           top_rules,
        "n_promote_threshold": 3,
        "timestamp":           1744382400.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(api_body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_status()

    assert isinstance(result, CoherenceFingerprintResult)
    assert result.total_rules == 3
    assert result.persistent_count == 2
    assert result.total_occurrences == 11
    assert abs(result.maturity_penalty - 0.20) < 0.001
    assert result.n_promote_threshold == 3
    assert result.error == ""


# ---------------------------------------------------------------------------
# T194S-3: maturity_penalty is float; top_rules is JSON string
# ---------------------------------------------------------------------------

def test_t194s_3_field_types():
    """T194S-3: maturity_penalty stored as float; top_rules stored as JSON string."""
    client = VAPICoherenceFingerprint("http://localhost:9999", api_key="test")

    api_body = {
        "total_rules":         1,
        "persistent_count":    1,
        "total_occurrences":   3,
        "maturity_penalty":    0.10,
        "top_rules":           [{"rule_name": "RULE_X", "occurrence_count": 3}],
        "n_promote_threshold": 3,
        "timestamp":           1744382400.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(api_body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_status()

    assert isinstance(result.maturity_penalty, float)
    assert isinstance(result.top_rules, str)
    # Must be valid JSON
    parsed = json.loads(result.top_rules)
    assert len(parsed) == 1
    assert parsed[0]["rule_name"] == "RULE_X"


# ---------------------------------------------------------------------------
# T194S-4: error path
# ---------------------------------------------------------------------------

def test_t194s_4_get_status_error_path():
    """T194S-4: get_status() returns CoherenceFingerprintResult with error on exception."""
    client = VAPICoherenceFingerprint("http://localhost:9999", api_key="test")

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
        result = client.get_status()

    assert isinstance(result, CoherenceFingerprintResult)
    assert result.error != ""
    assert result.total_rules == 0
    assert result.persistent_count == 0
