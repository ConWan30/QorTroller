"""DEPIN-1 LEG 3 (NODE-LEDGER-1) — hash-chained contribution ledger tests.

T1  genesis deterministic per node_id
T2  entry_hash stable / domain tag candidate
T3  chain of 3 entries verifies intact
T4  tamper of scorecard_root → entry_hash mismatch (tamper-evident)
T5  prev_hash break surfaces in verify_chain
T6  append-only JSONL + session dedup
T7  anchored fields NOT in preimage (mark_anchored preserves entry_hash)
T8  mark_anchored refuses empty tx (no fabricate)
T9  w3s_attested framing + meaning string present
T10 scorecard field extraction + scorecard_root from dict/bytes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO / "scripts"))

from vapi_bridge import node_contribution_ledger as ncl  # noqa: E402

# Fixed vectors (public; no secrets)
REF_NODE_ID = "ab" * 32
REF_SESSION_1 = "match_demo_20260713_120000"
REF_SESSION_2 = "match_demo_20260713_130000"
REF_SESSION_3 = "match_demo_20260713_140000"
REF_ROOT = "cd" * 32
REF_TS = 1_752_400_000_000_000_000


def test_t1_genesis_deterministic():
    a = ncl.genesis_hash_hex(REF_NODE_ID)
    b = ncl.genesis_hash_hex("0x" + REF_NODE_ID.upper())
    assert a == b
    assert len(a) == 64
    # different node → different genesis
    other = ncl.genesis_hash_hex("11" * 32)
    assert other != a


def test_t2_entry_hash_stable_domain_candidate():
    h1 = ncl.compute_entry_hash_hex(
        prev_hash=ncl.genesis_hash(REF_NODE_ID),
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS,
    )
    h2 = ncl.compute_entry_hash_hex(
        prev_hash=ncl.genesis_hash_hex(REF_NODE_ID),
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS,
    )
    assert h1 == h2
    assert ncl.LEDGER_DOMAIN == "QORTROLLER-NODE-LEDGER-v0"
    assert ncl.LEDGER_DOMAIN_TAG == b"QORTROLLER-NODE-LEDGER-v0"
    assert not ncl.LEDGER_DOMAIN.startswith("VAPI-")
    assert "FROZEN" not in ncl.LEDGER_DOMAIN
    # w3s flip changes hash
    h3 = ncl.compute_entry_hash_hex(
        prev_hash=ncl.genesis_hash(REF_NODE_ID),
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=True,
        ts_ns=REF_TS,
    )
    assert h3 != h1


def test_t3_chain_of_three_intact(tmp_path: Path):
    path = tmp_path / "node_contribution_ledger.jsonl"
    tip = None
    for sid, verdict in (
        (REF_SESSION_1, "SYNCHRONIZED"),
        (REF_SESSION_2, "PARTIAL_SURFACES"),
        (REF_SESSION_3, "UNVERIFIABLE"),
    ):
        e = ncl.build_entry(
            node_id_hex=REF_NODE_ID,
            session_id=sid,
            scorecard_root_hex=REF_ROOT,
            posp_verdict=verdict,
            w3s_attested=False,
            ts_ns=REF_TS + len(sid),
            prev_hash_hex=tip,
        )
        ncl.append_entry(path, e)
        tip = e["entry_hash"]
    rows = ncl.load_ledger(path)
    assert len(rows) == 3
    v = ncl.verify_chain(rows, node_id_hex=REF_NODE_ID)
    assert v["chain_intact"] is True
    assert v["entry_count"] == 3
    assert v["breaks"] == []
    # first prev is genesis
    assert rows[0]["prev_hash"] == ncl.genesis_hash_hex(REF_NODE_ID)
    assert rows[1]["prev_hash"] == rows[0]["entry_hash"]
    assert rows[2]["prev_hash"] == rows[1]["entry_hash"]


def test_t4_tamper_entry_hash_mismatch():
    e = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS,
    )
    ok, _ = ncl.verify_entry(e)
    assert ok is True
    e["scorecard_root"] = "ee" * 32  # tamper without recomputing hash
    ok2, reason = ncl.verify_entry(e)
    assert ok2 is False
    assert "mismatch" in reason


def test_t5_prev_hash_break_surfaces():
    e1 = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS,
    )
    e2 = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_2,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS + 1,
        prev_hash_hex=e1["entry_hash"],
    )
    # forge a wrong prev while keeping entry_hash for the forged prev (self-consistent but broken link)
    forged_prev = "ff" * 32
    e2_break = dict(e2)
    e2_break["prev_hash"] = forged_prev
    e2_break["entry_hash"] = ncl.compute_entry_hash_hex(
        prev_hash=forged_prev,
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_2,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS + 1,
    )
    v = ncl.verify_chain([e1, e2_break], node_id_hex=REF_NODE_ID)
    assert v["chain_intact"] is False
    assert any("prev_hash break" in b["reason"] for b in v["breaks"])


def test_t6_append_session_dedup(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="ABSENT",
        w3s_attested=False,
        ts_ns=REF_TS,
    )
    ncl.append_entry(path, e)
    with pytest.raises(ValueError, match="already in ledger"):
        ncl.append_entry(path, e)


def test_t7_mark_anchored_preserves_entry_hash(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=True,
        ts_ns=REF_TS,
    )
    ncl.append_entry(path, e)
    before = e["entry_hash"]
    assert e["anchored"] is False
    assert e["anchor_state"] == ncl.ANCHOR_STATE_PENDING
    updated = ncl.mark_anchored(
        path,
        session_id=REF_SESSION_1,
        tx_hash="0x" + "aa" * 32,
        block_number=44028531,
        node_id_hex=REF_NODE_ID,
    )
    assert updated["entry_hash"] == before
    assert updated["anchored"] is True
    assert updated["anchor_state"] == ncl.ANCHOR_STATE_ANCHORED
    assert updated["anchor_tx"].startswith("0x")
    assert updated["anchor_block"] == 44028531
    # chain still intact after rewrite
    v = ncl.verify_chain(ncl.load_ledger(path), node_id_hex=REF_NODE_ID)
    assert v["chain_intact"] is True


def test_t8_mark_anchored_refuses_empty_tx(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=False,
        ts_ns=REF_TS,
    )
    ncl.append_entry(path, e)
    with pytest.raises(ValueError, match="never fabricate"):
        ncl.mark_anchored(path, session_id=REF_SESSION_1, tx_hash="", block_number=1)


def test_t9_w3s_attested_framing():
    e = ncl.build_entry(
        node_id_hex=REF_NODE_ID,
        session_id=REF_SESSION_1,
        scorecard_root_hex=REF_ROOT,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=True,
        ts_ns=REF_TS,
    )
    assert e["w3s_attested"] is True
    meaning = e["w3s_attested_meaning"]
    assert "mechanical" in meaning.lower() or "format" in meaning.lower()
    assert "NOT" in meaning
    assert "truth" in meaning.lower()
    for banned in ncl.LEDGER_MUST_NOT_CLAIM:
        assert "w3s" in banned.lower() or "on-chain" in banned.lower() or "FROZEN" in banned or "mint" in banned or "spend" in banned or "fabricat" in banned
    # report must not claim on-chain while PENDING
    report = ncl.render_ledger_report([e])
    assert "PENDING" in report
    assert "not on-chain" in report.lower() or "local only" in report.lower()
    assert "MUST NOT" in report


def test_t10_scorecard_extract_and_root():
    card = {
        "schema": "qortroller-match-scorecard-v1",
        "label": "demo",
        "session_bind": {"session_id": REF_SESSION_1, "status": "BOUND"},
        "node_id": {
            "value": {"node_id": REF_NODE_ID, "node_id_short": REF_NODE_ID[:12]},
            "source": "DERIVED",
        },
        "fields": {
            "posp_verdict": {"value": "SYNCHRONIZED", "source": "MEASURED"},
            "node_id": {
                "value": {"node_id": REF_NODE_ID},
                "source": "DERIVED",
            },
        },
    }
    fields = ncl.extract_scorecard_fields(card)
    assert fields["node_id"] == REF_NODE_ID
    assert fields["session_id"] == REF_SESSION_1
    assert fields["posp_verdict"] == "SYNCHRONIZED"
    r1 = ncl.compute_scorecard_root(card)
    r2 = ncl.compute_scorecard_root(card)
    assert r1 == r2 and len(r1) == 64
    # raw bytes path
    raw = json.dumps(card, sort_keys=True).encode("utf-8")
    r3 = ncl.compute_scorecard_root(raw)
    assert len(r3) == 64
    # file path
    # (tmp handled inline)
    # posp code table
    assert ncl.posp_verdict_code("SYNCHRONIZED") == 0x03
    assert ncl.posp_verdict_code(None) == 0x00
    assert ncl.posp_verdict_code("nope") == 0x00
