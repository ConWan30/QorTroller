"""Phase 238 Step I — VAPICurator SDK tests.

Tests CuratorReviewResult / CuratorStatusResult dataclasses + VAPICurator
client class (review_listing, status, get_review, flagged_listings, bulk_review).

Network calls mocked via urllib.request.urlopen patching so tests run
without a live bridge.

T-238-CUR-SDK-1..7.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SDK_DIR = Path(__file__).parents[1]
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from vapi_sdk import (  # noqa: E402
    VAPICurator,
    CuratorReviewResult,
    CuratorStatusResult,
)


def _fake_urlopen(payload: dict):
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    cm.__exit__.return_value = False
    return cm


# T-238-CUR-SDK-1 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_1_review_result_slots():
    """CuratorReviewResult has slots — refuses ad-hoc attribute injection."""
    r = CuratorReviewResult()
    assert r.row_id == 0
    assert r.verdict == ""
    assert r.shadow_mode is True
    assert r.error == ""
    with pytest.raises(AttributeError):
        r.injected = "x"  # type: ignore[attr-defined]


# T-238-CUR-SDK-2 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_2_status_result_slots():
    r = CuratorStatusResult()
    assert r.total_reviews == 0
    assert r.shadow_mode is True
    with pytest.raises(AttributeError):
        r.injected = "x"  # type: ignore[attr-defined]


# T-238-CUR-SDK-3 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_3_review_short_reason_local_validation():
    """reason <10 chars → SDK rejects locally without network call."""
    client = VAPICurator("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen") as mock_urlopen:
        result = client.review_listing(commitment_hex="ab" * 32, reason="short")
    assert result.error != ""
    assert "at least 10 characters" in result.error
    mock_urlopen.assert_not_called()


# T-238-CUR-SDK-4 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_4_review_success_parse():
    """Successful POST → all 13 fields populated correctly."""
    payload = {
        "row_id":                       42,
        "commitment_hex":               "ab" * 32,
        "verdict":                      "FLAGGED_TIER_MISMATCH",
        "severity":                     "WARN",
        "anchors_recorded_count":       2,
        "anchors_recorded_breakdown":   {"sepproof": True, "biometric": True,
                                         "corpus": False, "gic": False},
        "consent_marketplace_bit_set":  True,
        "ipfs_resolvable":              None,
        "declared_tier":                3,
        "tier_at_review_time":          2,
        "tier_changed":                 True,
        "shadow_mode":                  True,
        "ts_ns":                        1_778_700_000_000_000_000,
    }
    client = VAPICurator("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = client.review_listing(
            commitment_hex="ab" * 32,
            reason="phase_238_step_i_curator_audit",
        )
    assert result.error == ""
    assert result.row_id == 42
    assert result.verdict == "FLAGGED_TIER_MISMATCH"
    assert result.severity == "WARN"
    assert result.anchors_recorded_count == 2
    assert result.anchors_recorded_breakdown == {
        "sepproof": True, "biometric": True, "corpus": False, "gic": False
    }
    assert result.declared_tier == 3
    assert result.tier_at_review_time == 2
    assert result.tier_changed is True


# T-238-CUR-SDK-5 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_5_review_http_error():
    client = VAPICurator("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", side_effect=ConnectionError("conn refused")):
        result = client.review_listing(
            commitment_hex="ab" * 32,
            reason="phase_238_curator_audit_string",
        )
    assert result.error != ""
    assert "conn refused" in result.error
    assert result.row_id == 0
    assert result.verdict == ""


# T-238-CUR-SDK-6 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_6_status_parse():
    payload = {
        "curator_review_enabled":     False,
        "total_reviews":              17,
        "approved_reviews":           10,
        "flagged_reviews":            5,
        "rejected_reviews":           2,
        "latest_verdict":             "FLAGGED_ANCHOR_STALE",
        "latest_listing_commitment":  "ef" * 32,
        "latest_review_ts_ns":        1_778_800_000_000_000_000,
        "shadow_mode":                True,
        "timestamp":                  1_778_800_001.0,
    }
    client = VAPICurator("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        status = client.status()
    assert status.error == ""
    assert status.total_reviews == 17
    assert status.flagged_reviews == 5
    assert status.rejected_reviews == 2
    assert status.latest_verdict == "FLAGGED_ANCHOR_STALE"
    assert status.shadow_mode is True


# T-238-CUR-SDK-7 ────────────────────────────────────────────────────────────
def test_t_238_cur_sdk_7_flagged_listings_and_get_review():
    """flagged_listings + get_review return parsed dicts; error → empty dict."""
    flagged_payload = {
        "listings": [
            {"listing_commitment": "aa" * 32, "verdict": "FLAGGED_TIER_MISMATCH",
             "severity": "WARN", "anchors_recorded_count": 2, "ts_ns": 1},
            {"listing_commitment": "bb" * 32, "verdict": "REJECTED_NO_ANCHORS",
             "severity": "HIGH", "anchors_recorded_count": 0, "ts_ns": 2},
        ],
        "total":         2,
        "since_minutes": 1440,
        "capped":        False,
    }
    client = VAPICurator("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(flagged_payload)):
        flagged = client.flagged_listings(since_minutes=1440, limit=20)
    assert flagged != {}
    assert flagged["total"] == 2
    assert len(flagged["listings"]) == 2

    # get_review parses timeline
    timeline_payload = {
        "listing_commitment": "ab" * 32,
        "reviews": [{"verdict": "APPROVED", "severity": "INFO", "ts_ns": 1}],
        "total":   1,
    }
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(timeline_payload)):
        timeline = client.get_review("ab" * 32)
    assert timeline["total"] == 1

    # 404 / error → empty dict
    with patch("urllib.request.urlopen", side_effect=Exception("not found")):
        empty = client.get_review("00" * 32)
    assert empty == {}
