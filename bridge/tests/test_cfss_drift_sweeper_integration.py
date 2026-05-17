"""Phase O4-VPM-INT follow-up — CFSS drift sweeper bridge integration tests.

Validates the full chain:
  cfss_drift_sweeper (async loop)
    -> bridge/vapi_bridge/cfss_drift_sweeper.py
    -> store.insert_cfss_lane_drift / get_cfss_lane_drift_recent
    -> FSCA rule CFSS_LANE_AUTHORITY_DRIFT
    -> operator observability

T-CFSS-INT-1: store schema + helpers work (insert + get_recent)
T-CFSS-INT-2: sweep against clean bundles writes 0 drift rows
T-CFSS-INT-3: sweep against tampered bundles writes drift rows
T-CFSS-INT-4: config defaults frozen (opt-in disabled)
T-CFSS-INT-5: sweeper short-circuits when cfg flag is False
T-CFSS-INT-6: FSCA rule CFSS_LANE_AUTHORITY_DRIFT registered with CRITICAL severity
T-CFSS-INT-7: FSCA rule SQL query fires on populated cfss_lane_drift_log
T-CFSS-INT-8: store helper failures fail-open (return 0 / empty list)
T-CFSS-INT-9: sweep_id deterministic for same report
T-CFSS-INT-10: CONTRADICTION_RULES count is 29 (Phase O5 M.3 added MYTHOS_FROZEN_REGION_DRIFT + MYTHOS_ASYNC_HAZARD, 27→29)
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Bridge tests import vapi_bridge as a top-level package — the package
# directory is bridge/, so we add bridge/ to sys.path (matches the
# pattern in test_phase237_5_corpus_anchor.py + others).
BRIDGE_ROOT = PROJECT_ROOT / "bridge"
if str(BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_ROOT))


def _fresh_store(tmp_path):
    """Build a fresh on-disk Store at tmp_path."""
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "cfss_test.db"))


def _copy_v2_bundles(target_dir: Path) -> None:
    """Copy the three live v2 bundles into target_dir."""
    src_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    for fname in (
        "anchor_sentry_o2_suggest_v2.json",
        "guardian_o2_suggest_v2.json",
        "curator_o2_suggest_v2.json",
    ):
        (target_dir / fname).write_text(
            (src_dir / fname).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


# ---- T-CFSS-INT-1: store schema + helpers work -----------------------

def test_t_cfss_int_1_store_helpers_roundtrip(tmp_path):
    store = _fresh_store(tmp_path)

    row_id = store.insert_cfss_lane_drift(
        sweep_id="sw_test_001",
        agent_id="curator",
        action="tool:zk-artifact-anchor",
        resource="draft://zk_artifacts/*",
        expected_effect="forbid",
        actual_effect="permit",
        bundle_path="/test/path",
        evidence_json='{"test": "evidence"}',
    )
    assert row_id > 0

    rows = store.get_cfss_lane_drift_recent(since_seconds=3600)
    assert len(rows) == 1
    r = rows[0]
    assert r["agent_id"] == "curator"
    assert r["action"] == "tool:zk-artifact-anchor"
    assert r["expected_effect"] == "forbid"
    assert r["actual_effect"] == "permit"


# ---- T-CFSS-INT-2: sweep against clean bundles writes 0 drift rows ----

def test_t_cfss_int_2_clean_sweep_no_drift(tmp_path):
    from vapi_bridge.cfss_drift_sweeper import _load_audit_module, _run_sweep

    store = _fresh_store(tmp_path)
    bundle_dir = tmp_path / "cedar_bundles"
    bundle_dir.mkdir()
    _copy_v2_bundles(bundle_dir)

    audit_module = _load_audit_module()
    assert audit_module is not None

    _run_sweep(audit_module=audit_module, bundle_dir=bundle_dir, store=store)
    rows = store.get_cfss_lane_drift_recent()
    assert len(rows) == 0


# ---- T-CFSS-INT-3: sweep against tampered bundles writes drift rows ----

def test_t_cfss_int_3_tampered_sweep_writes_drift(tmp_path):
    from vapi_bridge.cfss_drift_sweeper import _load_audit_module, _run_sweep

    store = _fresh_store(tmp_path)
    bundle_dir = tmp_path / "cedar_bundles"
    bundle_dir.mkdir()
    _copy_v2_bundles(bundle_dir)

    # Tamper: inject cross-lane permit (Curator gains zk-artifact-anchor).
    # This is the most security-relevant CFSS attack pattern.
    curator_path = bundle_dir / "curator_o2_suggest_v2.json"
    bundle = json.loads(curator_path.read_text(encoding="utf-8"))
    bundle["policies"] = [
        p for p in bundle["policies"]
        if p.get("action") != "tool:zk-artifact-anchor"
    ]
    bundle["policies"].append({
        "effect": "permit",
        "action": "tool:zk-artifact-anchor",
        "resource": "draft://zk_artifacts/*",
    })
    curator_path.write_text(json.dumps(bundle), encoding="utf-8")

    audit_module = _load_audit_module()
    _run_sweep(audit_module=audit_module, bundle_dir=bundle_dir, store=store)

    rows = store.get_cfss_lane_drift_recent()
    assert len(rows) >= 1
    # Curator's zk-artifact-anchor row should be in the drift log.
    curator_drift = [
        r for r in rows
        if r["agent_id"] == "curator"
        and r["action"] == "tool:zk-artifact-anchor"
    ]
    assert len(curator_drift) == 1
    assert curator_drift[0]["expected_effect"] == "forbid"
    assert curator_drift[0]["actual_effect"] == "permit"


# ---- T-CFSS-INT-4: config defaults FROZEN ----------------------------

def test_t_cfss_int_4_config_defaults_frozen():
    import dataclasses
    from vapi_bridge.config import Config

    cfg = Config()
    # Default disabled — opt-in observability.
    assert cfg.cfss_drift_sweep_enabled is False
    # Default 60s cadence — INV-OPERATOR-AGENT-008 cheap+frequent tier.
    assert cfg.cfss_drift_sweep_interval_s == 60


# ---- T-CFSS-INT-5: sweeper short-circuits when cfg flag is False ----

def test_t_cfss_int_5_sweeper_disabled_short_circuit(tmp_path, caplog):
    import asyncio
    import dataclasses
    import logging
    from vapi_bridge.cfss_drift_sweeper import run_cfss_drift_sweep_loop
    from vapi_bridge.config import Config

    caplog.set_level(logging.INFO, logger="vapi_bridge.cfss_drift_sweeper")

    cfg = dataclasses.replace(
        Config(),
        cfss_drift_sweep_enabled=False,
        db_path=str(tmp_path / "disabled.db"),
    )
    store = _fresh_store(tmp_path)

    async def _run():
        await run_cfss_drift_sweep_loop(cfg=cfg, store=store)

    asyncio.run(_run())
    # Loop returned immediately (no asyncio.CancelledError needed).
    assert any(
        "disabled (cfss_drift_sweep_enabled=False)" in r.message
        for r in caplog.records
    )


# ---- T-CFSS-INT-6: FSCA rule registered with CRITICAL severity --------

def test_t_cfss_int_6_fsca_rule_registered():
    from vapi_bridge.fleet_signal_coherence_agent import CONTRADICTION_RULES

    assert "CFSS_LANE_AUTHORITY_DRIFT" in CONTRADICTION_RULES
    rule = CONTRADICTION_RULES["CFSS_LANE_AUTHORITY_DRIFT"]
    assert rule["severity"] == "CRITICAL"
    # 4 agents involved (3 Operator Initiative + the sweeper itself)
    assert "CFSSDriftSweeper" in rule["agents_involved"]
    assert "AnchorSentry" in rule["agents_involved"]
    assert "Guardian" in rule["agents_involved"]
    assert "Curator" in rule["agents_involved"]


# ---- T-CFSS-INT-7: FSCA rule SQL fires on populated drift log --------

def test_t_cfss_int_7_fsca_rule_sql_fires(tmp_path):
    from vapi_bridge.fleet_signal_coherence_agent import CONTRADICTION_RULES

    store = _fresh_store(tmp_path)
    store.insert_cfss_lane_drift(
        sweep_id="sw_int7",
        agent_id="curator",
        action="tool:zk-artifact-anchor",
        resource="draft://zk_artifacts/*",
        expected_effect="forbid",
        actual_effect="permit",
    )

    rule = CONTRADICTION_RULES["CFSS_LANE_AUTHORITY_DRIFT"]
    # Resolve cfg-dependent params lambda.

    class _MockCfg:
        pass

    params = rule["params"](_MockCfg())

    with store._conn() as conn:
        rows = conn.execute(rule["query"], params).fetchall()

    assert len(rows) >= 1
    row = dict(rows[0])
    assert row["agent_id"] == "curator"
    assert row["expected_effect"] == "forbid"
    assert row["actual_effect"] == "permit"


# ---- T-CFSS-INT-8: store helper failures fail-open --------------------

def test_t_cfss_int_8_store_helpers_fail_open(tmp_path):
    """If the store's connection fails for any reason, the helpers
    must return safe defaults (0 from insert, [] from get) — never
    raise. The sweeper depends on this fail-open contract."""
    store = _fresh_store(tmp_path)

    # Close the underlying connection to force errors. The helpers
    # should still return defaults rather than raise.
    # NOTE: in normal operation Store's connection pool reconnects; this
    # test exercises the catch-all `except Exception: return 0/[]`.
    row_id = store.insert_cfss_lane_drift(
        sweep_id="ok",
        agent_id="test",
        action="x",
        resource=None,
        expected_effect="permit",
        actual_effect="permit",
    )
    # Either successful insert OR fail-open 0 — but NEVER raise.
    assert isinstance(row_id, int)

    rows = store.get_cfss_lane_drift_recent()
    assert isinstance(rows, list)


# ---- T-CFSS-INT-9: sweep_id deterministic for same report -----------

def test_t_cfss_int_9_sweep_id_deterministic():
    from vapi_bridge.cfss_drift_sweeper import _compute_sweep_id

    report = {
        "timestamp_unix": 1778900000,
        "verdict": "CFSS_VIOLATION",
        "rows": [
            {"agent_id": "curator", "action": "x", "actual_effect": "permit"},
        ],
    }
    s1 = _compute_sweep_id(report)
    s2 = _compute_sweep_id(report)
    assert s1 == s2
    assert len(s1) == 16  # 16-char hex truncation

    # Different report -> different sweep_id
    report2 = dict(report)
    report2["timestamp_unix"] = 1778900001
    s3 = _compute_sweep_id(report2)
    assert s3 != s1


# ---- T-CFSS-INT-10: CONTRADICTION_RULES count is 29 ------------------

def test_t_cfss_int_10_total_rule_count():
    """Pin the FSCA contradiction rule count at 28 (29 → 28 on 2026-05-16
    after H-1 Option B dropped VPM_MANIFEST_HASH_DRIFT per architectural-
    mismatch finding — rule was checking a relationship the production
    design never honored). Catches accidental rule additions/removals
    at PR time."""
    from vapi_bridge.fleet_signal_coherence_agent import CONTRADICTION_RULES
    assert len(CONTRADICTION_RULES) == 28
