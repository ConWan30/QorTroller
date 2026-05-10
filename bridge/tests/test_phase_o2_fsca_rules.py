"""Phase O2-FSCA-RULES tests.

Verifies the three new CONTRADICTION rules added to fleet_signal_coherence_agent.py
covering operator-initiative drafting layer health.

  T-O2-FSCA-1: O2_SUGGEST_NO_DRAFTS_24H fires when an agent at O2_SUGGEST has
                0 drafts in the last 24h
  T-O2-FSCA-2: O2_SUGGEST_NO_DRAFTS_24H quiet when >=1 recent draft present
  T-O2-FSCA-3: DRAFT_UNREVIEWED_72H fires when 10+ drafts older than 72h with
                operator_decision IS NULL
  T-O2-FSCA-4: DISAGREEMENT_RATE_TRENDING fires at rate=0.045 (between 0.04
                trending threshold and 0.05 gate breach)
"""
from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "fsca_test.db"))


def _make_cfg():
    cfg = types.SimpleNamespace()
    # FSCA accesses cfg fields per-rule; these defaults satisfy the rules we test.
    cfg.biometric_credential_ttl_days = 90.0
    return cfg


def _make_agent(tmp_path):
    """Construct a FleetSignalCoherenceAgent ready to run sync checks."""
    from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent
    import logging
    store = _make_store(tmp_path)
    cfg = _make_cfg()
    bus = MagicMock()
    logger = logging.getLogger("test_fsca")
    return FleetSignalCoherenceAgent(store=store, config=cfg, bus=bus, logger=logger), store


def _seed_activation(store, agent_id: str, bundle_filename: str, anchored_seconds_ago: float = 7 * 86400):
    """Insert a row into operator_agent_activation_log for the given agent.
    bundle_filename argument is mapped to the canonical `bundle_path` column
    (the watcher's get_latest_operator_agent_activation helper adapts
    bundle_path -> bundle_filename for backward-compat reads)."""
    import sqlite3
    with sqlite3.connect(store._db_path) as conn:
        conn.execute(
            "INSERT INTO operator_agent_activation_log "
            "(agent_id, from_phase, to_phase, from_scope_root, to_scope_root, "
            " bundle_path, governance_tx_hash, operational_tx_hash, "
            " governance_block_number, operational_block_number, "
            " operator_authority_hash, reason_text, activated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent_id,
                "O1_SHADOW",
                "O2_SUGGEST",
                "0x" + "0" * 64,
                "0x" + "a" * 64,
                bundle_filename,
                "0x" + "b" * 64,
                "0x" + "c" * 64,
                12345,
                12346,
                "0x" + "d" * 64,
                "test seed",
                time.time() - anchored_seconds_ago,
            ),
        )


# T-O2-FSCA-1: NO_DRAFTS_24H fires when conditions met
def test_T_O2_FSCA_1_no_drafts_24h_fires(tmp_path):
    agent, store = _make_agent(tmp_path)
    # Sentry at O2_SUGGEST with 0 drafts in last 24h
    _seed_activation(store, "anchor_sentry", "anchor_sentry_o2_suggest_v1.json")
    findings = agent._check_contradictions_sync()
    rule_names = [f["rule_name"] for f in findings]
    assert "O2_SUGGEST_NO_DRAFTS_24H" in rule_names, (
        f"expected O2_SUGGEST_NO_DRAFTS_24H to fire; got {rule_names}"
    )


# T-O2-FSCA-2: NO_DRAFTS_24H quiet when >=1 recent draft
def test_T_O2_FSCA_2_no_drafts_24h_quiet_when_recent_draft(tmp_path):
    agent, store = _make_agent(tmp_path)
    _seed_activation(store, "anchor_sentry", "anchor_sentry_o2_suggest_v1.json")
    # Insert a recent draft for Sentry
    store.insert_operator_agent_draft(
        agent_id="anchor_sentry",
        action_category="tool",
        action_name="kms-sign",
        draft_uri="draft://commit_hashes/abc",
        payload_hash="a" * 64,
        payload_bytes=42,
    )
    findings = agent._check_contradictions_sync()
    rule_names = [f["rule_name"] for f in findings]
    assert "O2_SUGGEST_NO_DRAFTS_24H" not in rule_names, (
        f"NO_DRAFTS_24H should be quiet with 1 recent draft; got {rule_names}"
    )


# T-O2-FSCA-3: UNREVIEWED_72H fires when 10+ stale drafts
def test_T_O2_FSCA_3_unreviewed_72h_fires(tmp_path):
    agent, store = _make_agent(tmp_path)
    # Insert 10 drafts older than 72h with operator_decision=NULL
    import sqlite3
    cutoff_ts = time.time() - 80 * 3600  # 80h ago, well over 72h
    for i in range(10):
        store.insert_operator_agent_draft(
            agent_id="anchor_sentry",
            action_category="tool",
            action_name="kms-sign",
            draft_uri=f"draft://commit_hashes/{i:040x}",
            payload_hash=f"{i:064x}",
            payload_bytes=42,
        )
    # Backdate created_at directly
    with sqlite3.connect(store._db_path) as conn:
        conn.execute(
            "UPDATE operator_agent_drafts SET created_at = ?",
            (cutoff_ts,),
        )

    findings = agent._check_contradictions_sync()
    rule_names = [f["rule_name"] for f in findings]
    assert "DRAFT_UNREVIEWED_72H" in rule_names, (
        f"expected DRAFT_UNREVIEWED_72H to fire; got {rule_names}"
    )


# T-O2-FSCA-4: DISAGREEMENT_RATE_TRENDING at 0.045 fires
def test_T_O2_FSCA_4_disagreement_rate_trending_fires(tmp_path):
    """Insert 200 drafts: 191 'accept' + 9 'reject' -> rate=9/200=0.045
    (between 0.04 trending threshold and 0.05 max breach)."""
    agent, store = _make_agent(tmp_path)
    import sqlite3

    drafts: list[int] = []
    for i in range(200):
        rid = store.insert_operator_agent_draft(
            agent_id="anchor_sentry",
            action_category="tool",
            action_name="kms-sign",
            draft_uri=f"draft://commit_hashes/{i:040x}",
            payload_hash=f"{i:064x}",
            payload_bytes=42,
        )
        drafts.append(rid)
    # 191 accepts + 9 rejects -> n_reject/n_reviewed = 9/200 = 0.045
    for i in range(191):
        store.record_operator_decision(
            draft_id=drafts[i],
            decision="accept",
            reason="operator approved this commit signature",
        )
    for i in range(191, 200):
        store.record_operator_decision(
            draft_id=drafts[i],
            decision="reject",
            reason="incorrect commit hash signed by Sentry",
        )

    findings = agent._check_contradictions_sync()
    rule_names = [f["rule_name"] for f in findings]
    assert "DISAGREEMENT_RATE_TRENDING" in rule_names, (
        f"expected DISAGREEMENT_RATE_TRENDING at rate=0.045; got {rule_names}"
    )

    # Quiet branch: 195 accepts + 5 rejects -> rate=5/200=0.025 (below threshold)
    agent2, store2 = _make_agent(tmp_path / "quiet_branch")
    drafts2 = []
    for i in range(200):
        rid = store2.insert_operator_agent_draft(
            agent_id="guardian",
            action_category="skill",
            action_name="audit-drafting",
            draft_uri=f"draft://audit_entries/{i:04d}",
            payload_hash=f"{i:064x}",
            payload_bytes=42,
        )
        drafts2.append(rid)
    for i in range(195):
        store2.record_operator_decision(
            draft_id=drafts2[i], decision="accept", reason="operator approved this audit",
        )
    for i in range(195, 200):
        store2.record_operator_decision(
            draft_id=drafts2[i], decision="reject", reason="incorrect audit entry data",
        )
    findings2 = agent2._check_contradictions_sync()
    quiet_names = [f["rule_name"] for f in findings2]
    assert "DISAGREEMENT_RATE_TRENDING" not in quiet_names, (
        f"DISAGREEMENT_RATE_TRENDING should be quiet at rate=0.025; got {quiet_names}"
    )
