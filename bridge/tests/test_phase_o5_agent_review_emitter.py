"""Phase O5-MLGA Stage 7 — AGENT-REVIEW-v1 autonomous emission tests.

T-AR-1   _resolve_canonical_from_agent_id maps canonical string passthrough
T-AR-2   _resolve_canonical_from_agent_id maps Q9-hex via cfg attrs
T-AR-3   emit_agent_review_for_draft: unknown draft_id -> None (fail-open)
T-AR-4   emit_agent_review_for_draft: happy path persists vpm_artifact_log row
T-AR-5   emit_agent_review_for_draft: reject decision flows through
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_agent_sentry_id = "0x" + ("a" * 64)
    cfg.operator_agent_guardian_id = "0x" + ("b" * 64)
    cfg.operator_agent_curator_id = "0x" + ("c" * 64)
    return cfg


# ----- T-1 -----

def test_t_ar_1_canonical_string_passthrough():
    from vapi_bridge.agent_review_emitter import (
        _resolve_canonical_from_agent_id,
    )
    cfg = _make_cfg()
    assert _resolve_canonical_from_agent_id(
        agent_id="anchor_sentry", cfg=cfg,
    ) == "anchor_sentry"
    assert _resolve_canonical_from_agent_id(
        agent_id="guardian", cfg=cfg,
    ) == "guardian"
    assert _resolve_canonical_from_agent_id(
        agent_id="curator", cfg=cfg,
    ) == "curator"


# ----- T-2 -----

def test_t_ar_2_q9_hex_via_cfg():
    from vapi_bridge.agent_review_emitter import (
        _resolve_canonical_from_agent_id,
    )
    cfg = _make_cfg()
    assert _resolve_canonical_from_agent_id(
        agent_id="0x" + ("a" * 64), cfg=cfg,
    ) == "anchor_sentry"
    # Case-insensitive
    assert _resolve_canonical_from_agent_id(
        agent_id="0x" + ("B" * 64), cfg=cfg,
    ) == "guardian"
    # Unknown returns None
    assert _resolve_canonical_from_agent_id(
        agent_id="0xdead", cfg=cfg,
    ) is None


# ----- T-3 -----

def test_t_ar_3_unknown_draft_returns_none():
    from vapi_bridge.store import Store
    from vapi_bridge.agent_review_emitter import emit_agent_review_for_draft
    cfg = _make_cfg()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = Store(db_path=os.path.join(td, "t.db"))
        result = emit_agent_review_for_draft(
            store=store, cfg=cfg, draft_id=999,
        )
        assert result is None


# ----- T-4 -----

def test_t_ar_4_happy_path_persists_row():
    from vapi_bridge.store import Store
    from vapi_bridge.agent_review_emitter import emit_agent_review_for_draft
    cfg = _make_cfg()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        store = Store(db_path=db)
        # Insert a draft + record an accept decision
        draft_id = store.insert_operator_agent_draft(
            agent_id="anchor_sentry",
            action_category="skill",
            action_name="read-wiki",
            draft_uri="draft://commit_hashes/abc",
            payload_hash="aa" * 32,
            payload_bytes=64,
            kms_sig_present=False,
        )
        store.record_operator_decision(
            draft_id=draft_id, decision="accept",
            reason="operator confirmation under tests",
        )
        result = emit_agent_review_for_draft(
            store=store, cfg=cfg, draft_id=draft_id,
        )
        assert result is not None
        assert result["action"] == "emitted"
        assert result["agent_canonical_name"] == "anchor_sentry"
        # Verify vpm_artifact_log row
        con = sqlite3.connect(db, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT vpm_id, zkba_class, proof_weight, preimage_json "
            "FROM vpm_artifact_log WHERE vpm_id='AGENT-REVIEW-v1'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row["zkba_class"] == 5    # CONSENT
        assert row["proof_weight"] == 3  # CHAIN_ONLY
        snap = json.loads(row["preimage_json"])
        assert snap["last_operator_decision"] == "accept"
        assert snap["draft_id"] == draft_id


# ----- T-5 -----

def test_t_ar_5_reject_decision_flows():
    from vapi_bridge.store import Store
    from vapi_bridge.agent_review_emitter import emit_agent_review_for_draft
    cfg = _make_cfg()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        store = Store(db_path=db)
        draft_id = store.insert_operator_agent_draft(
            agent_id="guardian",
            action_category="skill",
            action_name="audit-drafting",
            draft_uri="draft://audit_entries/xyz",
            payload_hash="dd" * 32,
            payload_bytes=128,
            kms_sig_present=False,
        )
        store.record_operator_decision(
            draft_id=draft_id, decision="reject",
            reason="rejected after closer inspection of evidence",
        )
        result = emit_agent_review_for_draft(
            store=store, cfg=cfg, draft_id=draft_id,
        )
        assert result is not None
        # Verify decision = reject in stored row
        con = sqlite3.connect(db, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT preimage_json FROM vpm_artifact_log "
            "WHERE vpm_id='AGENT-REVIEW-v1'"
        ).fetchone()
        con.close()
        snap = json.loads(row["preimage_json"])
        assert snap["last_operator_decision"] == "reject"
        assert snap["agent_canonical_name"] == "guardian"
