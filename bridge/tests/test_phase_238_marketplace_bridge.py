"""Phase 238-MARKETPLACE Step E+F bridge orchestration tests.

Tests the DataMarketplace orchestration class end-to-end against a temp
SQLite DB.  Mocks Pinata (no real IPFS calls in CI) and chain (no on-chain
operations).  The integration verifies:

  - Schema migration runs cleanly
  - DataMarketplace.create_listing composes commitment + IPFS + anchor + persist
  - tier preview matches anchor presence count
  - get_listing / get_listings_by_seller return enriched results with tier
  - graceful degradation when Pinata or chain are missing/broken
  - MARKETPLACE consent enforcement at orchestration layer (mirrors primitive)

T-238-MKT-BR-1..10.
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.data_marketplace import (  # noqa: E402
    DataMarketplace,
    TIER_BASIC,
    TIER_VERIFIED,
    TIER_ATTESTED,
    TIER_PREMIUM,
)
from vapi_bridge.listing_primitive import _CONSENT_BIT_MARKETPLACE


# ── Test fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_store(tmp_path):
    db_path = str(tmp_path / "phase238_test.db")
    return Store(db_path)


@pytest.fixture
def mock_pinata():
    """Pinata mock that returns a deterministic CID for any pin_json call."""
    pinata = MagicMock()
    pinata.pin_json = AsyncMock(return_value={
        "IpfsHash": "bafybeitestxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "PinSize": 256,
        "Timestamp": "2026-05-09T12:00:00Z",
    })
    return pinata


@pytest.fixture
def mock_chain_anchored():
    """Chain mock where anchor_listing_commitment returns (tx, True)."""
    chain = MagicMock()
    chain.anchor_listing_commitment = AsyncMock(return_value=("0x" + "ab" * 32, True))
    return chain


@pytest.fixture
def mock_chain_unanchored():
    """Chain mock where anchor returns (None, False) — kill-switch / config missing."""
    chain = MagicMock()
    chain.anchor_listing_commitment = AsyncMock(return_value=(None, False))
    return chain


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-1: schema migration applied (table + index existence)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_br_1_schema_migration(tmp_store):
    """marketplace_listing_log table must exist after Store init."""
    with tmp_store._conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='marketplace_listing_log'"
        ).fetchall()
        assert len(rows) == 1
        # Indexes
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='marketplace_listing_log'"
        ).fetchall()
        idx_names = [r["name"] for r in idx]
        assert any("idx_marketplace_listing_log_ts" in n for n in idx_names)
        assert any("idx_marketplace_listing_log_commit" in n for n in idx_names)


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-2: create_listing happy path with IPFS + chain anchored
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_2_create_listing_premium(tmp_store, mock_pinata, mock_chain_anchored):
    """4 anchors -> Premium tier. IPFS pin + chain anchor both succeed."""
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller",
        sepproof_commitment     = bytes.fromhex("aa" * 32),
        biometric_snapshot_hash = bytes.fromhex("bb" * 32),
        corpus_snapshot_hash    = bytes.fromhex("cc" * 32),
        gic_hash                = bytes.fromhex("dd" * 32),
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE | (1 << 1),
        data_class              = 4,
        price_iotx              = 5.0,
        listing_metadata        = {"label": "test_premium"},
        trigger_reason          = "test_premium_listing",
    )
    assert result["error"] == ""
    assert result["tier"] == TIER_PREMIUM
    assert result["tier_name"] == "Premium"
    assert result["multiplier_bps"] == 30000  # 3.0x
    assert result["anchors_present"] == 4
    assert len(result["listing_commitment"]) == 64
    assert result["ipfs_cid"].startswith("bafybei")
    assert result["on_chain_confirmed"] is True
    assert result["tx_hash"].startswith("0x")
    assert result["row_id"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-3: zero-anchor listing -> Tier.Basic
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_3_create_listing_basic(tmp_store, mock_pinata, mock_chain_anchored):
    """No anchors (CONSENT only) -> Basic tier (1.0x)."""
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller_basic",
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = None,
        gic_hash                = None,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
        data_class              = 0,
        price_iotx              = 1.0,
        listing_metadata        = {"label": "test_basic"},
        trigger_reason          = "test_basic_listing",
    )
    assert result["error"] == ""
    assert result["tier"] == TIER_BASIC
    assert result["multiplier_bps"] == 10000  # 1.0x
    assert result["anchors_present"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-4: 1 anchor -> Verified tier
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_4_create_listing_verified(tmp_store, mock_pinata, mock_chain_anchored):
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller_v",
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = bytes.fromhex("cc" * 32),  # only this one
        gic_hash                = None,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
        data_class              = 1,
        price_iotx              = 2.0,
        listing_metadata        = {"label": "test_verified"},
        trigger_reason          = "test_verified_listing",
    )
    assert result["error"] == ""
    assert result["tier"] == TIER_VERIFIED
    assert result["multiplier_bps"] == 15000  # 1.5x
    assert result["anchors_present"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-5: missing MARKETPLACE consent -> error result
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_5_marketplace_consent_required(tmp_store, mock_pinata, mock_chain_anchored):
    """Bridge layer enforces MARKETPLACE consent before primitive even runs."""
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller",
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = None,
        gic_hash                = None,
        consent_bitmask         = (1 << 0) | (1 << 1),  # missing MARKETPLACE bit
        data_class              = 0,
        price_iotx              = 1.0,
        listing_metadata        = {},
        trigger_reason          = "should_reject",
    )
    assert result["error"] != ""
    assert "MARKETPLACE" in result["error"]
    assert result["row_id"] == 0
    assert result["listing_commitment"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-6: chain unavailable -> on_chain_confirmed=False but listing persists
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_6_chain_unanchored_fallthrough(tmp_store, mock_pinata, mock_chain_unanchored):
    """When chain returns (None, False) (kill-switch / config missing),
    listing still persists with on_chain_confirmed=False — graceful degradation."""
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_unanchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller",
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = None,
        gic_hash                = None,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
        data_class              = 0,
        price_iotx              = 1.0,
        listing_metadata        = {"k": "v"},
        trigger_reason          = "kill_switch_test",
    )
    assert result["error"] == ""
    assert result["on_chain_confirmed"] is False
    assert result["tx_hash"] == ""
    assert result["row_id"] > 0  # listing did persist


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-7: pinata=None -> ipfs_cid='' but listing persists (mock mode)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_7_pinata_unavailable(tmp_store, mock_chain_anchored):
    """Pinata not configured -> IPFS pin skipped, ipfs_cid='', commitment includes
    32-byte zero CID hash. Listing still creates."""
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=None,  # explicit None
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller",
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = None,
        gic_hash                = None,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
        data_class              = 0,
        price_iotx              = 1.0,
        listing_metadata        = {"k": "v"},
        trigger_reason          = "pinata_disabled_test",
    )
    assert result["error"] == ""
    assert result["ipfs_cid"] == ""
    assert result["ipfs_cid_hash"] == "0" * 64
    assert result["row_id"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-8: get_listing_status aggregates correctly
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_8_get_listing_status(tmp_store, mock_pinata, mock_chain_anchored):
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    # Create 3 listings, 2 anchored
    for i in range(3):
        chain_mock = mock_chain_anchored if i < 2 else MagicMock(
            anchor_listing_commitment=AsyncMock(return_value=(None, False))
        )
        m2 = DataMarketplace(
            store=tmp_store, chain=chain_mock, cfg=MagicMock(),
            pinata_client=mock_pinata,
        )
        # Vary trigger_reason so listings have different commitments
        result = await m2.create_listing(
            seller_address          = f"0xseller_{i}",
            sepproof_commitment     = None,
            biometric_snapshot_hash = None,
            corpus_snapshot_hash    = None,
            gic_hash                = None,
            consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
            data_class              = 0,
            price_iotx              = float(i + 1),
            listing_metadata        = {"i": i},
            trigger_reason          = f"status_test_{i}",
        )
        assert result["error"] == ""
        # Force ts_ns differentiation since some test environments may collide
        import time
        time.sleep(0.001)

    status = marketplace.get_listing_status()
    assert status["total_listings"] == 3
    assert status["anchored_listings"] == 2  # only first 2 anchored


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-9: get_listing returns enriched dict with tier preview
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_9_get_listing_enriched(tmp_store, mock_pinata, mock_chain_anchored):
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    result = await marketplace.create_listing(
        seller_address          = "0xseller_enrich",
        sepproof_commitment     = bytes.fromhex("ee" * 32),
        biometric_snapshot_hash = bytes.fromhex("ff" * 32),
        corpus_snapshot_hash    = None,
        gic_hash                = None,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
        data_class              = 4,
        price_iotx              = 3.5,
        listing_metadata        = {"x": 1},
        trigger_reason          = "enriched_get_test",
    )
    assert result["error"] == ""
    listing = marketplace.get_listing(result["listing_commitment"])
    assert listing != {}
    assert listing["seller_address"] == "0xseller_enrich"
    assert listing["data_class"] == 4
    assert listing["price_iotx"] == 3.5
    # Tier enrichment fields
    assert "tier" in listing
    assert "tier_name" in listing
    assert "multiplier_bps" in listing
    # 2 anchors -> Attested (2.0x)
    assert listing["tier"] == TIER_ATTESTED
    assert listing["multiplier_bps"] == 20000


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-BR-10: get_listings_by_seller paginated + tier-enriched
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_238_mkt_br_10_get_listings_by_seller(tmp_store, mock_pinata, mock_chain_anchored):
    marketplace = DataMarketplace(
        store=tmp_store, chain=mock_chain_anchored, cfg=MagicMock(),
        pinata_client=mock_pinata,
    )
    seller = "0xseller_paginated"
    # Create 3 listings by same seller
    for i in range(3):
        await marketplace.create_listing(
            seller_address          = seller,
            sepproof_commitment     = None,
            biometric_snapshot_hash = None,
            corpus_snapshot_hash    = None,
            gic_hash                = None,
            consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
            data_class              = 0,
            price_iotx              = float(i + 1),
            listing_metadata        = {"i": i},
            trigger_reason          = f"paged_test_{i}",
        )
        import time
        time.sleep(0.001)

    rows = marketplace.get_listings_by_seller(seller, limit=10)
    assert len(rows) == 3
    # All enriched with tier preview
    for r in rows:
        assert "tier" in r
        assert "tier_name" in r
        assert "multiplier_bps" in r
        assert r["tier"] == TIER_BASIC  # 0 anchors -> Basic
