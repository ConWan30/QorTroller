"""Phase 238-MARKETPLACE Step G SDK tests.

Tests the ListingCreationResult / MarketplaceStatusResult dataclasses +
VAPIMarketplaceListings client class (list_data_session, status, get_listing).

Network calls are mocked via urllib.request.urlopen patching so tests run
without a live bridge.

T-238-MKT-SDK-1..7.
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
    VAPIMarketplaceListings,
    ListingCreationResult,
    MarketplaceStatusResult,
)


def _fake_urlopen(payload: dict):
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    cm.__exit__.return_value = False
    return cm


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-1: ListingCreationResult dataclass slots
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_1_listing_creation_result_slots():
    r = ListingCreationResult()
    assert r.row_id == 0
    assert r.tier == 0
    assert r.tier_name == "Basic"
    assert r.multiplier_bps == 10000
    with pytest.raises(AttributeError):
        r.injected = "x"  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-2: MarketplaceStatusResult slots + defaults
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_2_status_result_slots():
    r = MarketplaceStatusResult()
    assert r.total_listings == 0
    assert r.anchored_listings == 0
    with pytest.raises(AttributeError):
        r.injected = "x"  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-3: list_data_session locally validates reason
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_3_list_short_reason():
    """reason < 10 chars -> SDK pre-validates without network call."""
    client = VAPIMarketplaceListings("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen") as mock_urlopen:
        result = client.list_data_session(
            seller_address  = "0xseller",
            consent_bitmask = 8,
            data_class      = 0,
            price_iotx      = 1.0,
            reason          = "short",
        )
    assert result.error != ""
    assert "at least 10 characters" in result.error
    mock_urlopen.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-4: list_data_session parses success response
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_4_list_success_parse():
    payload = {
        "row_id":              42,
        "listing_commitment":  "ab" * 32,
        "ipfs_cid":            "bafybeiteststxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "ipfs_cid_hash":       "cd" * 32,
        "tier":                3,
        "tier_name":           "Premium",
        "multiplier_bps":      30000,
        "anchors_present":     4,
        "on_chain_confirmed":  True,
        "tx_hash":             "0x" + "ef" * 32,
        "ts_ns":               1_778_500_000_000_000_000,
    }
    client = VAPIMarketplaceListings("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = client.list_data_session(
            seller_address  = "0xseller",
            consent_bitmask = 8,
            data_class      = 4,
            price_iotx      = 5.0,
            reason          = "operator_test_listing",
            sepproof_commitment_hex = "aa" * 32,
            biometric_snapshot_hex  = "bb" * 32,
            corpus_snapshot_hex     = "cc" * 32,
            gic_hash_hex            = "dd" * 32,
        )
    assert result.error == ""
    assert result.row_id == 42
    assert result.tier == 3
    assert result.tier_name == "Premium"
    assert result.multiplier_bps == 30000
    assert result.anchors_present == 4
    assert result.on_chain_confirmed is True


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-5: list_data_session HTTP error -> result with error
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_5_list_http_error():
    client = VAPIMarketplaceListings("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", side_effect=ConnectionError("conn refused")):
        result = client.list_data_session(
            seller_address  = "0xseller",
            consent_bitmask = 8,
            data_class      = 0,
            price_iotx      = 1.0,
            reason          = "operator_audit_string_long_enough",
        )
    assert result.error != ""
    assert "conn refused" in result.error
    assert result.row_id == 0


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-6: status() parses bridge response
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_6_status_parse():
    payload = {
        "total_listings":         5,
        "anchored_listings":      3,
        "latest_commitment":      "01" * 32,
        "latest_seller":          "0xseller_latest",
        "latest_data_class":      4,
        "latest_price_iotx":      7.5,
        "latest_anchors_present": 4,
        "latest_ts_ns":           1_778_600_000_000_000_000,
        "latest_on_chain":        True,
        "latest_tx_hash":         "0x" + "23" * 32,
    }
    client = VAPIMarketplaceListings("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        status = client.status()
    assert status.error == ""
    assert status.total_listings == 5
    assert status.anchored_listings == 3
    assert status.latest_seller == "0xseller_latest"
    assert status.latest_anchors_present == 4
    assert status.latest_on_chain is True


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-SDK-7: get_listing parses listing dict; 404 -> empty dict
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_sdk_7_get_listing():
    payload = {
        "listing_commitment":     "fa" * 32,
        "seller_address":         "0xseller_g",
        "data_class":             4,
        "price_iotx":             3.0,
        "tier":                   2,
        "tier_name":              "Attested",
        "multiplier_bps":         20000,
        "anchors_present_count":  3,
        "on_chain_confirmed":     True,
        "tx_hash":                "0x" + "ba" * 32,
    }
    client = VAPIMarketplaceListings("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        listing = client.get_listing("fa" * 32)
    assert listing != {}
    assert listing["tier"] == 2
    assert listing["tier_name"] == "Attested"
    assert listing["multiplier_bps"] == 20000

    # 404 / error path
    with patch("urllib.request.urlopen", side_effect=Exception("not found")):
        empty = client.get_listing("00" * 32)
    assert empty == {}
