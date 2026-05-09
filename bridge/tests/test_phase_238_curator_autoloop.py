"""Phase 238 Step I-AUTOLOOP-1 — Curator autonomous review loop tests.

T-238-CUR-AL-1..8 — verifies the autonomous review loop registers only
when CURATOR_REVIEW_ENABLED=True, picks listings due for review with
idempotency, persists verdicts via the shared compute_verdict_for_listing
helper, fails open on per-listing errors, and matches the FROZEN main.py
task name.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
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
from vapi_bridge.curator_agent import (  # noqa: E402
    compute_verdict_for_listing,
    select_listings_due_for_review,
    json_summary,
)
from vapi_bridge.curator_review import (  # noqa: E402
    MARKETPLACE_CONSENT_BIT,
    VERDICT_APPROVED,
    VERDICT_FLAGGED_TIER_MISMATCH,
)


# ── Test fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_store(tmp_path):
    return Store(str(tmp_path / "phase238_autoloop_test.db"))


def _seed_listing(store, commitment_hex: str, anchors_present: int = 4,
                   data_class: int = 6, consent_bitmask: int = None) -> None:
    """Seed marketplace_listing_log with a test listing."""
    if consent_bitmask is None:
        consent_bitmask = MARKETPLACE_CONSENT_BIT
    store.insert_marketplace_listing(
        listing_commitment      = commitment_hex,
        seller_address          = "0xtestseller",
        sepproof_commitment     = "aa" * 32 if anchors_present >= 1 else "",
        biometric_snapshot_hash = "bb" * 32 if anchors_present >= 2 else "",
        corpus_snapshot_hash    = "cc" * 32 if anchors_present >= 3 else "",
        gic_hash                = "dd" * 32 if anchors_present >= 4 else "",
        consent_bitmask         = consent_bitmask,
        data_class              = data_class,
        price_iotx              = 5.0,
        ipfs_cid                = "bafytest",
        ipfs_cid_hash           = "ee" * 32,
        ts_ns                   = int(time.time_ns()),
        anchors_present_count   = anchors_present,
        on_chain_confirmed      = False,
        tx_hash                 = "",
        trigger_reason          = "seed-for-test",
    )


def _mock_chain_all_recorded() -> MagicMock:
    chain = MagicMock()
    chain.is_adjudication_recorded = AsyncMock(return_value=True)
    return chain


def _mock_chain_none_recorded() -> MagicMock:
    chain = MagicMock()
    chain.is_adjudication_recorded = AsyncMock(return_value=False)
    return chain


def _mock_cfg(**overrides) -> MagicMock:
    cfg = MagicMock()
    cfg.curator_review_enabled = overrides.get("curator_review_enabled", True)
    cfg.curator_review_interval_s = overrides.get("curator_review_interval_s", 0.05)
    cfg.curator_review_batch_limit = overrides.get("curator_review_batch_limit", 25)
    cfg.curator_review_idempotency_window_minutes = overrides.get(
        "curator_review_idempotency_window_minutes", 60)
    cfg.curator_anchor_freshness_blocks = overrides.get(
        "curator_anchor_freshness_blocks", 1_000_000)
    return cfg


# ── T-238-CUR-AL-1 ──────────────────────────────────────────────────────────
def test_t_238_cur_al_1_main_py_wires_loop_when_enabled():
    """main.py registers CuratorReviewLoop task only when curator_review_enabled=True."""
    main_src = (BRIDGE_DIR / "vapi_bridge" / "main.py").read_text()
    # Conditional registration on flag
    assert 'getattr(self.cfg, "curator_review_enabled", False)' in main_src
    # set_name FROZEN
    assert 'set_name("CuratorReviewLoop")' in main_src
    # Imports the loop fn from the module
    assert "from .curator_agent import run_curator_review_loop" in main_src


# ── T-238-CUR-AL-2 ──────────────────────────────────────────────────────────
def test_t_238_cur_al_2_disabled_flag_short_circuits():
    """Static check: when curator_review_enabled=False, no task registers."""
    main_src = (BRIDGE_DIR / "vapi_bridge" / "main.py").read_text()
    # The if-guard short-circuits BEFORE any import or task creation
    sig_pos = main_src.find("Phase 238 Step I-AUTOLOOP-1: Curator autonomous")
    block = main_src[sig_pos:sig_pos + 1500]
    # Guard appears BEFORE the import inside the block
    flag_idx = block.find('curator_review_enabled')
    import_idx = block.find('from .curator_agent import')
    assert flag_idx < import_idx, "flag check must precede import (short-circuit)"


# ── T-238-CUR-AL-3 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_cur_al_3_single_listing_review_persists_row(tmp_store):
    """compute_verdict_for_listing happy path persists to curator_listing_review_log."""
    _seed_listing(tmp_store, "ab" * 32, anchors_present=4)
    chain = _mock_chain_all_recorded()
    cfg = _mock_cfg()

    listings = await asyncio.to_thread(
        select_listings_due_for_review, tmp_store, 60, 25,
    )
    assert len(listings) == 1

    res = await compute_verdict_for_listing(
        tmp_store, chain, cfg,
        "ab" * 32, listings[0], "test_t3",
    )
    assert res["row_id"] > 0
    assert res["verdict"] == VERDICT_APPROVED
    assert res["anchors_recorded_count"] == 4
    assert res["shadow_mode"] is True

    # Row persisted
    rows = tmp_store.get_curator_reviews_for_listing("ab" * 32)
    assert len(rows) == 1
    assert rows[0]["verdict"] == VERDICT_APPROVED


# ── T-238-CUR-AL-4 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_cur_al_4_batch_with_mixed_verdicts(tmp_store):
    """Multiple listings with different anchor states produce varied verdicts."""
    _seed_listing(tmp_store, "11" * 32, anchors_present=4, data_class=6)  # premium
    _seed_listing(tmp_store, "22" * 32, anchors_present=2, data_class=6)  # mismatch
    chain = _mock_chain_all_recorded()  # all isRecorded=True
    cfg = _mock_cfg()

    listings = await asyncio.to_thread(
        select_listings_due_for_review, tmp_store, 60, 25,
    )
    assert len(listings) == 2

    verdicts = {}
    for listing in listings:
        commit = listing["listing_commitment"]
        # Override per-listing chain mock so anchor count matches the seed
        per_chain = MagicMock()
        anchors = listing["anchors_present_count"]
        # First N anchors recorded matching anchors_present_count
        async def _is_rec_dynamic(commit_hex, _n=anchors):
            # Record sequentially
            return commit_hex in {
                "aa" * 32 if _n >= 1 else "",
                "bb" * 32 if _n >= 2 else "",
                "cc" * 32 if _n >= 3 else "",
                "dd" * 32 if _n >= 4 else "",
            }
        per_chain.is_adjudication_recorded = AsyncMock(side_effect=_is_rec_dynamic)
        res = await compute_verdict_for_listing(
            tmp_store, per_chain, cfg, commit, listing, "test_t4",
        )
        verdicts[commit] = res["verdict"]

    assert verdicts["11" * 32] == VERDICT_APPROVED         # 4 anchors + premium intent
    assert verdicts["22" * 32] == VERDICT_FLAGGED_TIER_MISMATCH  # 2 anchors but premium claim


# ── T-238-CUR-AL-5 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_cur_al_5_chain_failure_does_not_raise(tmp_store):
    """compute_verdict tolerates RPC failures from chain.is_adjudication_recorded."""
    _seed_listing(tmp_store, "fa" * 32, anchors_present=4)
    chain = MagicMock()
    chain.is_adjudication_recorded = AsyncMock(side_effect=ConnectionError("RPC down"))
    cfg = _mock_cfg()

    listings = await asyncio.to_thread(
        select_listings_due_for_review, tmp_store, 60, 25,
    )
    res = await compute_verdict_for_listing(
        tmp_store, chain, cfg,
        "fa" * 32, listings[0], "test_t5",
    )
    # All anchors fail-open False → 0 anchors recorded → REJECTED_NO_ANCHORS
    assert res["row_id"] > 0
    assert res["verdict"] == "REJECTED_NO_ANCHORS"
    assert res["anchors_recorded_count"] == 0


# ── T-238-CUR-AL-6 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_cur_al_6_idempotency_window_skips_recently_reviewed(tmp_store):
    """Listings reviewed within idempotency window are excluded from selection."""
    _seed_listing(tmp_store, "cd" * 32, anchors_present=4)
    # Insert a recent review row
    tmp_store.insert_curator_review(
        listing_commitment="cd" * 32, verdict=VERDICT_APPROVED, severity="INFO",
        anchors_recorded_count=4, anchors_breakdown_json="{}",
        consent_marketplace_bit_set=True, ipfs_resolvable=True,
        declared_tier=3, tier_at_review_time=3, tier_changed=False,
        shadow_mode=True, reason_detail="recent", trigger_reason="seed",
        ts_ns=int(time.time_ns()),
    )
    listings = await asyncio.to_thread(
        select_listings_due_for_review, tmp_store, 60, 25,
    )
    # Already reviewed within 60-min window → excluded
    assert len(listings) == 0

    # But with 0 minute window, it should be excluded only if review ts_ns
    # is in the last 0 minutes (i.e., still excluded since just inserted)
    # — verify with a wide window the listing is back in the queue when
    # window=1 min in the past relative to a future ts_ns
    listings_zero = await asyncio.to_thread(
        select_listings_due_for_review, tmp_store, 1, 25,
    )
    # Under a 1-min window, the just-inserted review still falls inside it
    assert len(listings_zero) == 0


# ── T-238-CUR-AL-7 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_cur_al_7_select_respects_batch_limit(tmp_store):
    """select_listings_due_for_review respects limit cap."""
    for i in range(10):
        commit = f"{i:02x}" * 32
        _seed_listing(tmp_store, commit, anchors_present=4)
    listings = await asyncio.to_thread(
        select_listings_due_for_review, tmp_store, 60, 5,
    )
    assert len(listings) == 5  # capped


# ── T-238-CUR-AL-8 ──────────────────────────────────────────────────────────
def test_t_238_cur_al_8_json_summary_helper():
    """json_summary produces deterministic compact verdict breakdown."""
    assert json_summary({}) == "{}"
    assert json_summary({"APPROVED": 3, "FLAGGED_TIER_MISMATCH": 1}) == \
        "APPROVED=3, FLAGGED_TIER_MISMATCH=1"
    # Sorted alphabetically for determinism
    assert json_summary({"FLAGGED_TIER_MISMATCH": 1, "APPROVED": 3}) == \
        "APPROVED=3, FLAGGED_TIER_MISMATCH=1"
