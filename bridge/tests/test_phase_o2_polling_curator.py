"""Phase O2-DRAFT-AUTOLOOP (Curator) -- polling-loop scaffold tests.

Third agent in parallel-fleet trio. Mirrors Sentry/Guardian patterns; adds
Curator-specific verdict-enum + chained-verdict-to-sig + batch-trigger
semantics.

  T-O2-POLL-CURATOR-1: dispatch matrix (listing_event chains verdict+sig;
                       anchor_freshness_alert -> operator-notify;
                       periodic_compliance batch produces N drafts)
  T-O2-POLL-CURATOR-2: rate limiting -- ONE trigger per cycle even when
                       trigger is a batch (periodic_compliance N=3
                       produces 3 rows in one trigger)
  T-O2-POLL-CURATOR-3: start()/stop() lifecycle
  T-O2-POLL-CURATOR-4: opt-in default short-circuit
  T-O2-POLL-CURATOR-5: invalid verdict in listing_event surfaces as draft
                       error; loop logs + continues to next trigger
  T-O2-POLL-CURATOR-6: per-method-success count accurate (listing_event=2,
                       periodic_compliance batch N=3, anchor=1)
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "curator_polling_test.db"))


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_curator_polling_enabled = False
    cfg.operator_agent_curator_polling_interval_s = 1
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# T-O2-POLL-CURATOR-1: dispatch matrix
def test_T_O2_POLL_CURATOR_1_dispatch_matrix(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.operator_agent_curator_polling import CuratorPollingLoop
    from vapi_bridge.curator_review import VERDICT_APPROVED, VERDICT_FLAGGED_TIER_MISMATCH

    # listing_event -> verdict + sig (2 rows; chained)
    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)
    loop = CuratorPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],
    )
    loop._dispatch_one({
        "kind": "listing_event",
        "payload": {
            "listing_id": "listing-0xabc",
            "verdict": VERDICT_APPROVED,
            "review_payload": {"anchors_present": 4, "declared_tier": 3, "derived_tier": 3},
        },
    })
    rows = store.get_operator_agent_drafts(agent_id="curator", limit=10)
    assert len(rows) == 2
    actions = sorted(r["action_name"] for r in rows)
    assert actions == ["kms-sign", "marketplace-listing-review"]
    # /verdict and /sig URI suffixes distinguishable
    uris = [r["draft_uri"] for r in rows]
    assert any(u.endswith("/verdict") for u in uris)
    assert any(u.endswith("/sig") for u in uris)

    # anchor_freshness_alert -> operator-notify (1 row, severity recommend_suspend)
    store2 = _make_store(tmp_path / "anchor")
    gen2 = CuratorDraftGenerator(cfg=_make_cfg(), store=store2)
    loop2 = CuratorPollingLoop(
        cfg=_make_cfg(), store=store2, draft_generator=gen2,
        get_pending_triggers=lambda: [],
    )
    loop2._dispatch_one({
        "kind": "anchor_freshness_alert",
        "payload": {
            "notification_id": "notify-listing-xyz",
            "recommendation": "suspend listing -- anchor stale >30d",
            "notify_payload": {"listing_id": "0xxyz", "anchor_age_hours": 720},
        },
    })
    rows = store2.get_operator_agent_drafts(agent_id="curator", limit=10)
    assert len(rows) == 1
    assert rows[0]["action_name"] == "operator-notify"

    # periodic_compliance batch -> N verdict rows
    store3 = _make_store(tmp_path / "periodic")
    gen3 = CuratorDraftGenerator(cfg=_make_cfg(), store=store3)
    loop3 = CuratorPollingLoop(
        cfg=_make_cfg(), store=store3, draft_generator=gen3,
        get_pending_triggers=lambda: [],
    )
    loop3._dispatch_one({
        "kind": "periodic_compliance",
        "payload": {
            "listings": [
                {"listing_id": f"listing-{i}", "verdict": VERDICT_APPROVED,
                 "review_payload": {"i": i}}
                for i in range(3)
            ],
        },
    })
    rows = store3.get_operator_agent_drafts(agent_id="curator", limit=10)
    assert len(rows) == 3
    assert all(r["action_name"] == "marketplace-listing-review" for r in rows)


# T-O2-POLL-CURATOR-2: rate limiting -- ONE trigger per cycle
def test_T_O2_POLL_CURATOR_2_rate_limit_one_trigger_per_cycle(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.operator_agent_curator_polling import CuratorPollingLoop
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)
    triggers = [
        {"kind": "listing_event", "payload": {
            "listing_id": f"l-{i}", "verdict": VERDICT_APPROVED,
            "review_payload": {"i": i}}}
        for i in range(5)
    ]
    loop = CuratorPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: triggers,
    )
    res = loop._safe_get_triggers()
    assert len(res) == 5
    loop._dispatch_one(res[0])  # head only

    # First listing_event chained -> 2 rows; total 2 only.
    n = store.count_operator_agent_drafts(agent_id="curator", since_seconds=86400)
    assert n == 2
    assert loop._drafts_this_session() == 2  # 2 method successes


# T-O2-POLL-CURATOR-3: start()/stop() lifecycle
@pytest.mark.asyncio
async def test_T_O2_POLL_CURATOR_3_start_stop_lifecycle(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.operator_agent_curator_polling import CuratorPollingLoop

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)
    loop = CuratorPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],
    )
    await loop.start()
    await asyncio.sleep(0.05)
    assert loop._task is not None
    assert not loop._task.done()
    await loop.stop()
    assert loop._task is None


# T-O2-POLL-CURATOR-4: opt-in default
@pytest.mark.asyncio
async def test_T_O2_POLL_CURATOR_4_opt_in_default(tmp_path):
    from vapi_bridge.operator_agent_curator_polling import run_curator_polling_loop

    store = _make_store(tmp_path)
    cfg = _make_cfg(operator_agent_curator_polling_enabled=False)
    await asyncio.wait_for(
        run_curator_polling_loop(cfg=cfg, store=store),
        timeout=1.0,
    )


# T-O2-POLL-CURATOR-5: invalid verdict + handler errors don't crash loop
def test_T_O2_POLL_CURATOR_5_invalid_verdict_does_not_crash(tmp_path):
    """Invalid verdict surfaces as DraftResult.error from
    draft_marketplace_listing_review; the loop logs + continues. The
    invalid trigger produces NO store rows; the next valid trigger
    dispatches normally."""
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.operator_agent_curator_polling import CuratorPollingLoop
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)
    loop = CuratorPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],
    )

    # Invalid verdict -> error result; no row persisted.
    loop._dispatch_one({
        "kind": "listing_event",
        "payload": {"listing_id": "x", "verdict": "GARBAGE", "review_payload": {}},
    })
    n_after_bad = store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    )
    assert n_after_bad == 0
    assert loop._drafts_this_session() == 0

    # Subsequent valid trigger dispatches normally.
    loop._dispatch_one({
        "kind": "listing_event",
        "payload": {"listing_id": "y", "verdict": VERDICT_APPROVED, "review_payload": {}},
    })
    n_after_good = store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    )
    assert n_after_good == 2  # verdict + sig
    assert loop._drafts_this_session() == 2


# T-O2-POLL-CURATOR-6: per-method-success count
def test_T_O2_POLL_CURATOR_6_drafts_this_session_count(tmp_path):
    """Mix of triggers; counter == sum of successful method invocations.
    listing_event=2, periodic_compliance(N=3)=3, anchor_freshness_alert=1."""
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.operator_agent_curator_polling import CuratorPollingLoop
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)
    loop = CuratorPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],
    )

    triggers = [
        {"kind": "listing_event", "payload": {
            "listing_id": "a", "verdict": VERDICT_APPROVED, "review_payload": {}}},  # +2
        {"kind": "periodic_compliance", "payload": {
            "listings": [
                {"listing_id": f"p-{i}", "verdict": VERDICT_APPROVED,
                 "review_payload": {"i": i}}
                for i in range(3)
            ]}},  # +3
        {"kind": "anchor_freshness_alert", "payload": {
            "notification_id": "n1", "recommendation": "check this anchor freshness"}},  # +1
        {"kind": "listing_event", "payload": {
            "listing_id": "b", "verdict": VERDICT_APPROVED, "review_payload": {}}},  # +2
    ]
    for t in triggers:
        loop._dispatch_one(t)

    expected_methods = 2 + 3 + 1 + 2  # = 8
    assert loop._drafts_this_session() == expected_methods
    n_rows = store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    )
    assert n_rows == expected_methods
