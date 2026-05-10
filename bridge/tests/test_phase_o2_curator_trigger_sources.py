"""Phase O2-CURATOR-TRIGGERS tests.

Verifies the three Curator live trigger sources match the
CuratorPollingLoop trigger contract.

  T-O2-CURATOR-TRIG-1:  factory ListingTriggerSource flag=False -> None;
                        flag=True -> instance
  T-O2-CURATOR-TRIG-2:  factory AnchorFreshnessTriggerSource flag toggle
  T-O2-CURATOR-TRIG-3:  factory PeriodicComplianceTriggerSource flag toggle
  T-O2-CURATOR-TRIG-4:  ListingTriggerSource first call seeds baseline []
                        even with rows already present
  T-O2-CURATOR-TRIG-5:  ListingTriggerSource emits one trigger per new row
                        in id-ASC order; verdict ∈ _FROZEN_VERDICTS
  T-O2-CURATOR-TRIG-6:  ListingTriggerSource cfg flag False short-circuits
  T-O2-CURATOR-TRIG-7:  AnchorFreshnessTriggerSource cron gate suppresses
                        re-emit within interval; emits past interval for
                        stale listings; chain=None safe
  T-O2-CURATOR-TRIG-8:  AnchorFreshnessTriggerSource handles chain RPC
                        failure without raising
  T-O2-CURATOR-TRIG-9:  PeriodicComplianceTriggerSource cron gate +
                        single-batch shape (one trigger, N listings)
  T-O2-CURATOR-TRIG-10: All three sources cfg-disabled -> []
  T-O2-CURATOR-TRIG-11: Malformed listing row (missing optional fields)
                        does not crash either source
  T-O2-CURATOR-TRIG-12: All three sources never raise even when store
                        DB path is bogus
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavyweight deps that bridge imports may pull transitively.
for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


# ── Fixtures ─────────────────────────────────────────────────────────────────
def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_curator_marketplace_trigger_enabled = True
    cfg.operator_agent_curator_anchor_freshness_trigger_enabled = True
    cfg.operator_agent_curator_anchor_freshness_interval_s = 3600
    cfg.operator_agent_curator_periodic_compliance_trigger_enabled = True
    cfg.operator_agent_curator_periodic_compliance_interval_s = 21600
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "curator_trig_test.db"))


def _insert_listing(store, *, commitment, ts_ns,
                    sepproof="", anchors=0, consent=0, data_class=0):
    """Raw-SQL insert into marketplace_listing_log (no high-level helper
    that takes only these fields exists; insert_marketplace_listing
    requires many positional args and is overkill for tests)."""
    db = getattr(store, "_db_path", None) or getattr(store, "db_path", None)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO marketplace_listing_log "
            "(listing_commitment, seller_address, sepproof_commitment, "
            " biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
            " consent_bitmask, data_class, price_iotx, ipfs_cid, "
            " ipfs_cid_hash, ts_ns, on_chain_confirmed, tx_hash, "
            " anchors_present_count, trigger_reason, created_at) "
            "VALUES (?, '', ?, '', '', '', ?, ?, 0.0, '', '', ?, 0, '', "
            "        ?, '', ?)",
            (
                str(commitment),
                str(sepproof),
                int(consent),
                int(data_class),
                int(ts_ns),
                int(anchors),
                time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ── T-O2-CURATOR-TRIG-1..3: factories opt-in/opt-out ─────────────────────────
def test_T_O2_CURATOR_TRIG_1_factory_listing_flag_toggle(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorMarketplaceListingTriggerSource,
        make_curator_marketplace_listing_trigger_source,
    )
    store = _make_store(tmp_path)
    cfg_off = _make_cfg(operator_agent_curator_marketplace_trigger_enabled=False)
    assert make_curator_marketplace_listing_trigger_source(
        cfg=cfg_off, store=store,
    ) is None

    cfg_on = _make_cfg()
    src = make_curator_marketplace_listing_trigger_source(cfg=cfg_on, store=store)
    assert isinstance(src, CuratorMarketplaceListingTriggerSource)
    assert isinstance(src(), list)


def test_T_O2_CURATOR_TRIG_2_factory_freshness_flag_toggle(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorAnchorFreshnessTriggerSource,
        make_curator_anchor_freshness_trigger_source,
    )
    store = _make_store(tmp_path)
    cfg_off = _make_cfg(operator_agent_curator_anchor_freshness_trigger_enabled=False)
    assert make_curator_anchor_freshness_trigger_source(
        cfg=cfg_off, store=store, chain=None,
    ) is None

    cfg_on = _make_cfg()
    src = make_curator_anchor_freshness_trigger_source(
        cfg=cfg_on, store=store, chain=None,
    )
    assert isinstance(src, CuratorAnchorFreshnessTriggerSource)


def test_T_O2_CURATOR_TRIG_3_factory_compliance_flag_toggle(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorPeriodicComplianceTriggerSource,
        make_curator_periodic_compliance_trigger_source,
    )
    store = _make_store(tmp_path)
    cfg_off = _make_cfg(
        operator_agent_curator_periodic_compliance_trigger_enabled=False,
    )
    assert make_curator_periodic_compliance_trigger_source(
        cfg=cfg_off, store=store,
    ) is None

    cfg_on = _make_cfg()
    src = make_curator_periodic_compliance_trigger_source(
        cfg=cfg_on, store=store,
    )
    assert isinstance(src, CuratorPeriodicComplianceTriggerSource)


# ── T-O2-CURATOR-TRIG-4..6: marketplace listing trigger ──────────────────────
def test_T_O2_CURATOR_TRIG_4_listing_baseline_seed(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorMarketplaceListingTriggerSource,
    )
    store = _make_store(tmp_path)
    # Pre-populate a row BEFORE the source initializes — baseline must
    # NOT emit it (matches GitTriggerSource baseline pattern).
    _insert_listing(
        store, commitment="a" * 64, ts_ns=int(time.time() * 1e9),
        anchors=2, data_class=4,
    )
    src = CuratorMarketplaceListingTriggerSource(cfg=_make_cfg(), store=store)
    assert src() == []  # baseline
    assert src() == []  # no new rows


def test_T_O2_CURATOR_TRIG_5_listing_emits_new_rows_in_order(tmp_path):
    from vapi_bridge.curator_review import _FROZEN_VERDICTS
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorMarketplaceListingTriggerSource,
    )
    store = _make_store(tmp_path)
    src = CuratorMarketplaceListingTriggerSource(cfg=_make_cfg(), store=store)
    src()  # seed baseline (empty table)

    now_ns = int(time.time() * 1e9)
    _insert_listing(store, commitment="b" * 64, ts_ns=now_ns,
                    anchors=1, data_class=2)
    _insert_listing(store, commitment="c" * 64, ts_ns=now_ns + 1,
                    anchors=3, data_class=5)
    _insert_listing(store, commitment="d" * 64, ts_ns=now_ns + 2,
                    anchors=0, data_class=0)

    triggers = src()
    assert len(triggers) == 3
    # Forward order: b, c, d
    payloads = [t["payload"] for t in triggers]
    listing_ids = [p["listing_id"] for p in payloads]
    assert listing_ids == ["b" * 64, "c" * 64, "d" * 64]
    for t in triggers:
        assert t["kind"] == "listing_event"
        assert t["payload"]["verdict"] in _FROZEN_VERDICTS
        rp = t["payload"]["review_payload"]
        assert "anchor_count" in rp
        assert "declared_tier" in rp
        assert "ipfs_cid" in rp

    # Subsequent call: no new rows -> empty
    assert src() == []


def test_T_O2_CURATOR_TRIG_6_listing_flag_off_short_circuits(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorMarketplaceListingTriggerSource,
    )
    store = _make_store(tmp_path)
    cfg = _make_cfg(operator_agent_curator_marketplace_trigger_enabled=False)
    src = CuratorMarketplaceListingTriggerSource(cfg=cfg, store=store)
    # Add a row; flag is off so __call__ must return [] without ever
    # initializing.
    _insert_listing(store, commitment="e" * 64, ts_ns=int(time.time() * 1e9))
    assert src() == []
    assert src() == []


# ── T-O2-CURATOR-TRIG-7..8: anchor freshness ─────────────────────────────────
def test_T_O2_CURATOR_TRIG_7_freshness_cron_gate_and_stale_emit(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorAnchorFreshnessTriggerSource,
        FRESHNESS_THRESHOLD_HOURS,
    )
    store = _make_store(tmp_path)
    cfg = _make_cfg(operator_agent_curator_anchor_freshness_interval_s=3600)
    src = CuratorAnchorFreshnessTriggerSource(
        cfg=cfg, store=store, chain=None,
    )

    # Stale listing: ts_ns is 31d in the past (> 720h threshold).
    stale_ts_ns = int(
        (time.time() - (FRESHNESS_THRESHOLD_HOURS + 24) * 3600) * 1e9
    )
    _insert_listing(
        store, commitment="f" * 64, ts_ns=stale_ts_ns,
        sepproof="s" * 64, anchors=1, data_class=2,
    )

    # First call: cron gate has _last_fired_ts=0 so ANY positive interval
    # elapsed -> emits. Listing is stale -> should produce trigger.
    triggers = src()
    assert len(triggers) >= 1
    assert triggers[0]["kind"] == "anchor_freshness_alert"
    payload = triggers[0]["payload"]
    assert payload["recommendation"] == "recommend_suspend"
    assert "notification_id" in payload
    assert payload["notify_payload"]["listing_commitment"] == "f" * 64
    # chain=None -> anchor_present is None
    assert payload["notify_payload"]["anchor_present"] is None

    # Second immediate call: cron gate suppresses
    assert src() == []


def test_T_O2_CURATOR_TRIG_8_freshness_chain_failure_safe(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorAnchorFreshnessTriggerSource,
        FRESHNESS_THRESHOLD_HOURS,
    )
    store = _make_store(tmp_path)
    cfg = _make_cfg()

    class _BrokenChain:
        async def is_adjudication_recorded(self, commitment_hex: str) -> bool:
            raise RuntimeError("simulated RPC failure")

    src = CuratorAnchorFreshnessTriggerSource(
        cfg=cfg, store=store, chain=_BrokenChain(),
    )
    stale_ts_ns = int(
        (time.time() - (FRESHNESS_THRESHOLD_HOURS + 24) * 3600) * 1e9
    )
    _insert_listing(
        store, commitment="g" * 64, ts_ns=stale_ts_ns,
        sepproof="h" * 64, anchors=1,
    )
    # Must not raise even though chain blows up.
    triggers = src()
    assert isinstance(triggers, list)
    if triggers:
        # anchor_present resolved to None on chain failure
        assert triggers[0]["payload"]["notify_payload"]["anchor_present"] in (
            None, False,
        )


# ── T-O2-CURATOR-TRIG-9: periodic compliance batch ───────────────────────────
def test_T_O2_CURATOR_TRIG_9_compliance_cron_gate_and_batch_shape(tmp_path):
    from vapi_bridge.curator_review import _FROZEN_VERDICTS
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorPeriodicComplianceTriggerSource,
    )
    store = _make_store(tmp_path)
    cfg = _make_cfg(operator_agent_curator_periodic_compliance_interval_s=21600)
    src = CuratorPeriodicComplianceTriggerSource(cfg=cfg, store=store)

    now_ns = int(time.time() * 1e9)
    _insert_listing(store, commitment="x" * 64, ts_ns=now_ns)
    _insert_listing(store, commitment="y" * 64, ts_ns=now_ns + 1)
    _insert_listing(store, commitment="z" * 64, ts_ns=now_ns + 2)

    triggers = src()
    assert len(triggers) == 1  # ONE batch trigger
    t = triggers[0]
    assert t["kind"] == "periodic_compliance"
    listings = t["payload"]["listings"]
    assert isinstance(listings, list)
    assert len(listings) == 3
    for entry in listings:
        assert set(entry.keys()) >= {"listing_id", "verdict", "review_payload"}
        assert entry["verdict"] in _FROZEN_VERDICTS

    # Cron gate suppresses re-emit
    assert src() == []


# ── T-O2-CURATOR-TRIG-10: all three flag-disabled ────────────────────────────
def test_T_O2_CURATOR_TRIG_10_all_disabled_return_empty(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorAnchorFreshnessTriggerSource,
        CuratorMarketplaceListingTriggerSource,
        CuratorPeriodicComplianceTriggerSource,
    )
    store = _make_store(tmp_path)
    cfg = _make_cfg(
        operator_agent_curator_marketplace_trigger_enabled=False,
        operator_agent_curator_anchor_freshness_trigger_enabled=False,
        operator_agent_curator_periodic_compliance_trigger_enabled=False,
    )
    # Add data so it's NOT just an empty-DB short-circuit
    _insert_listing(store, commitment="m" * 64, ts_ns=int(time.time() * 1e9))

    s1 = CuratorMarketplaceListingTriggerSource(cfg=cfg, store=store)
    s2 = CuratorAnchorFreshnessTriggerSource(cfg=cfg, store=store, chain=None)
    s3 = CuratorPeriodicComplianceTriggerSource(cfg=cfg, store=store)

    assert s1() == []
    assert s2() == []
    assert s3() == []


# ── T-O2-CURATOR-TRIG-11: malformed row resilience ───────────────────────────
def test_T_O2_CURATOR_TRIG_11_malformed_row_does_not_crash(tmp_path):
    """Even when a row has unusual values, both sources keep working."""
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorMarketplaceListingTriggerSource,
        CuratorPeriodicComplianceTriggerSource,
    )
    store = _make_store(tmp_path)

    # Row with empty commitment + zero ts_ns.  insert_listing helper
    # always sets these fields, so this exercises the per-row try/except
    # paths in the renderer + subsequent normal rows still emit.
    _insert_listing(store, commitment="", ts_ns=0,
                    anchors=0, data_class=0)

    s1 = CuratorMarketplaceListingTriggerSource(cfg=_make_cfg(), store=store)
    s1()  # baseline (with the bad row already present)

    # Add a good row
    _insert_listing(
        store, commitment="n" * 64, ts_ns=int(time.time() * 1e9),
        anchors=1, data_class=2,
    )
    triggers = s1()
    # Must include the good row
    ids = [t["payload"]["listing_id"] for t in triggers]
    assert "n" * 64 in ids

    # Periodic compliance: no crash either
    s3 = CuratorPeriodicComplianceTriggerSource(cfg=_make_cfg(), store=store)
    out = s3()
    assert isinstance(out, list)


# ── T-O2-CURATOR-TRIG-12: bogus DB path -> [] without raising ────────────────
def test_T_O2_CURATOR_TRIG_12_bogus_db_path_safe(tmp_path):
    from vapi_bridge.operator_agent_curator_trigger_sources import (
        CuratorAnchorFreshnessTriggerSource,
        CuratorMarketplaceListingTriggerSource,
        CuratorPeriodicComplianceTriggerSource,
    )

    class _BogusStore:
        _db_path = str(tmp_path / "no_such_dir" / "missing.db")

    store = _BogusStore()
    cfg = _make_cfg()

    s1 = CuratorMarketplaceListingTriggerSource(cfg=cfg, store=store)
    s2 = CuratorAnchorFreshnessTriggerSource(cfg=cfg, store=store, chain=None)
    s3 = CuratorPeriodicComplianceTriggerSource(cfg=cfg, store=store)

    # All three must return [] and NOT raise.
    assert s1() == []
    # Allow second call too: baseline path on first call shouldn't raise.
    assert s1() == []
    assert s2() == []
    assert s3() == []
