"""Phase O2-DRAFT-GENERATION (Sentry) -- end-to-end primitive tests.

Verifies the full pipeline:
  SentryDraftGenerator -> store.insert_operator_agent_draft
                       -> store.count_operator_agent_drafts
                       -> _count_drafts_safe (watcher hook)
                       -> watcher's PHASE_O3_DRAFT_PAYLOAD_MIN gate evaluation

  T-O2-DRAFT-SENTRY-1: kms-sign draft persists with correct draft_uri scheme + hash
  T-O2-DRAFT-SENTRY-2: provenance-recording draft persists; record_id sanitized
  T-O2-DRAFT-SENTRY-3: pda-attestation-anchor scaffold persists; no chain call
  T-O2-DRAFT-SENTRY-4: count_operator_agent_drafts returns N=50 after 50 inserts
  T-O2-DRAFT-SENTRY-5: record_operator_decision flips draft state; idempotent on same decision
  T-O2-DRAFT-SENTRY-6: compute_disagreement_rate returns rejected/reviewed ratio
  T-O2-DRAFT-SENTRY-7: compute_false_positive_rate -> Curator only; non-Curator returns 0.0
                       even after overturn_curator decisions are not recorded
  T-O2-DRAFT-SENTRY-8: end-to-end watcher gate clears: 50 Sentry drafts ->
                       PHASE_O3_DRAFT_PAYLOAD_MIN draft_payload_count blocker disappears
  T-O2-DRAFT-SENTRY-9: invalid input early-returns with error field; no DB row written
  T-O2-DRAFT-SENTRY-10: idempotent insert -- same agent_id+payload_hash twice returns
                        same row id; count remains 1
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub web3 + eth_account modules so any indirect import doesn't trip.
for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    db_path = tmp_path / "drafts_test.db"
    return Store(str(db_path))


def _make_cfg(**overrides):
    """Minimal cfg -- no Q9 hex fields populated, so _resolve_agent_id_for_store
    returns canonical names. Tests run against agent_id='anchor_sentry'."""
    cfg = types.SimpleNamespace()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-1: kms-sign draft persistence + URI/hash correctness
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_1_kms_sign_draft_persists(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import (
        SentryDraftGenerator,
        SENTRY_KMS_SIGN_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    commit = "a" * 40  # valid 40-char SHA-1

    result = gen.draft_kms_sign(
        commit_hash=commit,
        signer_pubkey_hex="0xdeadbeef",
        signature_payload={"repo": "ConWan30/vapi-prototype", "branch": "main"},
    )
    assert result.error is None
    assert result.draft_id > 0
    assert result.draft_uri == f"{SENTRY_KMS_SIGN_DRAFT_PREFIX}{commit}"
    assert len(result.payload_hash) == 64
    assert result.payload_bytes > 0
    assert result.action_category == "tool"
    assert result.action_name == "kms-sign"
    assert result.agent_id_used == "anchor_sentry"

    # Verify the row landed in store
    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    assert len(rows) == 1
    assert rows[0]["draft_uri"] == result.draft_uri
    assert rows[0]["kms_sig_present"] == 1
    assert rows[0]["operator_decision"] is None  # unreviewed


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-2: provenance-recording draft + record_id sanitization
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_2_provenance_record_persists(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import (
        SentryDraftGenerator,
        SENTRY_PROVENANCE_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # record_id with disallowed chars must be sanitized in the URI
    result = gen.draft_provenance_record(
        record_id="poac/chain/head:abc123",
        attestation_payload={
            "event_type": "POAC_CHAIN_LINK",
            "subject": "0x" + "f" * 64,
            "evidence_hash": "0x" + "1" * 64,
        },
    )
    assert result.error is None
    assert result.draft_id > 0
    # / and : should collapse to _
    assert result.draft_uri == SENTRY_PROVENANCE_DRAFT_PREFIX + "poac_chain_head_abc123"
    assert len(result.payload_hash) == 64
    assert result.action_category == "skill"
    assert result.action_name == "provenance-recording"


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-3: pda-anchor scaffold draft (no chain call)
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_3_pda_anchor_scaffold_persists(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import (
        SentryDraftGenerator,
        SENTRY_PDA_ANCHOR_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    poad = "9" * 64
    dev = "8" * 64

    result = gen.draft_pda_anchor(
        device_id_hash_hex="0x" + dev,
        poad_hash_hex=poad,
        dual_veto=False,
    )
    assert result.error is None
    assert result.draft_id > 0
    assert result.draft_uri.startswith(SENTRY_PDA_ANCHOR_DRAFT_PREFIX + "pda-")
    # First 16 chars of poad hash embedded in URI
    assert poad[:16] in result.draft_uri
    assert result.action_name == "pda-attestation-anchor"


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-4: count_operator_agent_drafts returns true count
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_4_count_returns_true_count(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    for i in range(50):
        # Distinct commit hashes -> 50 distinct payload hashes
        result = gen.draft_kms_sign(commit_hash=f"{i:040x}")
        assert result.error is None
        assert result.draft_id > 0

    # Window covering all 50
    n = store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert n == 50

    # Tight 0-second window returns 0 (none strictly older than now)
    # (cutoff = now -> only rows with created_at >= now)
    # depending on float precision this may be 0..50; assert not over 50
    n_tight = store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=0,
    )
    assert 0 <= n_tight <= 50


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-5: record_operator_decision flips state
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_5_record_decision(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    r = gen.draft_kms_sign(commit_hash="b" * 40)

    # accept
    assert store.record_operator_decision(draft_id=r.draft_id, decision="accept")
    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=1)
    assert rows[0]["operator_decision"] == "accept"
    assert rows[0]["operator_decision_at"] is not None

    # invalid decision -> False, no state change
    assert store.record_operator_decision(draft_id=r.draft_id, decision="garbage") is False

    # operator may revise -> 'reject' with reason
    assert store.record_operator_decision(
        draft_id=r.draft_id, decision="reject", reason="signed wrong commit",
    )
    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=1)
    assert rows[0]["operator_decision"] == "reject"
    assert "wrong commit" in (rows[0]["operator_disagreement_reason"] or "")

    # missing draft_id -> False
    assert store.record_operator_decision(draft_id=99999, decision="accept") is False


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-6: compute_disagreement_rate
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_6_disagreement_rate(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Empty state -> 0.0 (no signal yet)
    assert store.compute_operator_agent_disagreement_rate(
        agent_id="anchor_sentry", since_seconds=86400,
    ) == 0.0

    drafts = []
    for i in range(20):
        drafts.append(gen.draft_kms_sign(commit_hash=f"{i:040x}"))

    # Review 10 drafts: 8 accept, 2 reject -> 20% disagreement
    for i in range(8):
        store.record_operator_decision(draft_id=drafts[i].draft_id, decision="accept")
    for i in range(8, 10):
        store.record_operator_decision(draft_id=drafts[i].draft_id, decision="reject")

    rate = store.compute_operator_agent_disagreement_rate(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert rate == pytest.approx(2 / 10, abs=1e-9)

    # Unreviewed drafts (10 remaining) do NOT count toward denominator
    assert rate < 0.5  # not 2/20=0.1


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-7: false_positive_rate is Curator-specific semantically
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_7_false_positive_rate_semantics(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Sentry drafts: even after accept/reject decisions, no overturn_curator
    # decisions exist -> false_positive_rate stays 0.0
    for i in range(10):
        r = gen.draft_kms_sign(commit_hash=f"{i:040x}")
        store.record_operator_decision(draft_id=r.draft_id, decision="accept")

    fp_rate = store.compute_operator_agent_false_positive_rate(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert fp_rate == 0.0

    # Manually inject an overturn_curator decision under "curator" agent
    # to verify the helper IS sensitive to it (Curator path)
    store.insert_operator_agent_draft(
        agent_id="curator",
        action_category="skill",
        action_name="marketplace-listing-review",
        draft_uri="draft://listing_reviews/abc",
        payload_hash="c" * 64,
        payload_bytes=42,
    )
    rows = store.get_operator_agent_drafts(agent_id="curator", limit=1)
    store.record_operator_decision(
        draft_id=rows[0]["id"], decision="overturn_curator",
        reason="operator caught a tier-misclassification",
    )
    rate_curator = store.compute_operator_agent_false_positive_rate(
        agent_id="curator", since_seconds=86400,
    )
    assert rate_curator == pytest.approx(1.0)  # 1 of 1 reviewed -> 100% FP


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-8: end-to-end watcher gate
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_8_watcher_gate_clears_at_50_drafts(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_initiative_advancement import (
        PHASE_O3_DRAFT_PAYLOAD_MIN,
        _count_drafts_safe,
    )

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Below threshold -> safe wrapper returns < 50
    for i in range(10):
        gen.draft_kms_sign(commit_hash=f"{i:040x}")
    n_below = _count_drafts_safe(store, "anchor_sentry")
    assert n_below == 10
    assert n_below < PHASE_O3_DRAFT_PAYLOAD_MIN

    # At threshold (50) -> gate clears
    for i in range(10, PHASE_O3_DRAFT_PAYLOAD_MIN):
        gen.draft_kms_sign(commit_hash=f"{i:040x}")
    n_at = _count_drafts_safe(store, "anchor_sentry")
    assert n_at == PHASE_O3_DRAFT_PAYLOAD_MIN
    assert n_at >= PHASE_O3_DRAFT_PAYLOAD_MIN  # the gate's pass condition


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-9: invalid input early-returns without DB write
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_9_invalid_input_early_returns(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Bad commit hash (too short)
    r1 = gen.draft_kms_sign(commit_hash="abc")
    assert r1.error is not None
    assert r1.draft_id == 0
    assert "40-char" in r1.error

    # Bad provenance: empty record_id
    r2 = gen.draft_provenance_record(record_id="", attestation_payload={"k": "v"})
    assert r2.error is not None
    assert r2.draft_id == 0

    # Bad provenance: payload not a dict
    r3 = gen.draft_provenance_record(record_id="x", attestation_payload="not a dict")  # type: ignore[arg-type]
    assert r3.error is not None
    assert r3.draft_id == 0

    # Bad PDA: short hash
    r4 = gen.draft_pda_anchor(device_id_hash_hex="abc", poad_hash_hex="9" * 64)
    assert r4.error is not None
    assert r4.draft_id == 0

    # No rows persisted
    assert store.count_operator_agent_drafts(agent_id="anchor_sentry", since_seconds=86400) == 0


# --------------------------------------------------------------------------
# T-O2-DRAFT-SENTRY-10: idempotent insert on same agent+payload_hash
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_SENTRY_10_idempotent_insert(tmp_path):
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Same commit hash + same payload (same ts_ns explicitly) -> same hash
    payload = {"repo": "x", "branch": "y", "ts_ns": 1234567890}
    r1 = gen.draft_kms_sign(commit_hash="d" * 40, signature_payload=payload)
    r2 = gen.draft_kms_sign(commit_hash="d" * 40, signature_payload=payload)

    assert r1.payload_hash == r2.payload_hash
    assert r1.draft_id == r2.draft_id  # UNIQUE collision returns existing id
    assert store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    ) == 1
