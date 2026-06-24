"""Tests for full-strength read-only chain-integrity verifiers (WEC links + corpus commitments)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vapi_bridge.watchdog_chain import compute_wec, genesis_wec  # noqa: E402
from vapi_bridge.corpus_snapshot import compute_corpus_commitment  # noqa: E402
from vapi_bridge.chain_integrity_verifiers import (  # noqa: E402
    verify_wec_links, verify_corpus_commitments,
)

SID = "grind_test_v1"


def _wec_chain(n=4, base_ts=1000):
    """Build a genuine linear WEC chain of n events using the FROZEN primitives."""
    rows = []
    prev = None
    for i in range(n):
        ts = base_ts + i
        pid = 100 + i
        code = 2  # BRIDGE_HEALTHY
        if i == 0:
            prev = genesis_wec(SID, ts)
            prev_hex = ""
        else:
            prev_hex = rows[-1]["wec_hash"]
            prev = bytes.fromhex(prev_hex)
        wh = compute_wec(prev, code, pid, SID, ts).hex()
        rows.append({"event_code": code, "pid": pid, "grind_session_id": SID,
                     "ts_ns": ts, "wec_hash": wh, "prev_wec_hash": prev_hex})
    return rows


def test_wec_linear_chain_intact():
    rep = verify_wec_links(_wec_chain(5))
    assert rep.tamper_free and rep.structurally_sound and rep.intact
    assert rep.n_rows == 5 and rep.links_valid == 5 and rep.n_invalid == 0
    assert rep.n_orphans == 0 and rep.n_forks == 0 and rep.n_tips == 1
    assert rep.head_hex == _wec_chain(5)[-1]["wec_hash"]


def test_wec_empty_is_vacuously_intact():
    rep = verify_wec_links([])
    assert rep.intact and rep.n_rows == 0 and rep.head_hex is None


def test_wec_tamper_detected():
    rows = _wec_chain(4)
    rows[2]["wec_hash"] = "00" * 32          # alter a stored hash
    rep = verify_wec_links(rows)
    assert rep.tamper_free is False and rep.n_invalid >= 1 and rep.intact is False


def test_wec_order_independent():
    """Verification must not depend on row order (the whole point vs the naive recompute)."""
    rows = _wec_chain(6)
    shuffled = [rows[0], rows[5], rows[2], rows[4], rows[1], rows[3]]
    rep = verify_wec_links(shuffled)
    assert rep.tamper_free and rep.intact and rep.links_valid == 6


def test_wec_fork_reported_but_links_still_valid():
    """Two events chaining off the SAME prev (concurrency race) is a FORK — reported, not tamper:
    each link is still a valid hash of its recorded predecessor."""
    rows = _wec_chain(3)
    fork_prev = rows[0]["wec_hash"]
    # a second event also chaining off row0's wec_hash (valid hash, but shares a prev)
    ts = 5000; pid = 999; code = 2
    wh = compute_wec(bytes.fromhex(fork_prev), code, pid, SID, ts).hex()
    rows.append({"event_code": code, "pid": pid, "grind_session_id": SID,
                 "ts_ns": ts, "wec_hash": wh, "prev_wec_hash": fork_prev})
    rep = verify_wec_links(rows)
    assert rep.tamper_free is True          # every link is a valid hash
    assert rep.n_forks == 1                 # row0's hash is now the prev of two rows
    assert rep.n_tips == 2                  # two leaves


def test_wec_orphan_detected():
    rows = _wec_chain(3)
    rows.append({"event_code": 2, "pid": 7, "grind_session_id": SID, "ts_ns": 9000,
                 "wec_hash": "ab" * 32, "prev_wec_hash": "ee" * 32})  # prev not in set
    rep = verify_wec_links(rows)
    assert rep.n_orphans == 1 and rep.structurally_sound is False


def test_wec_head_is_latest_by_ts():
    rows = _wec_chain(4)
    rep = verify_wec_links(rows)
    assert rep.head_hex == max(rows, key=lambda r: r["ts_ns"])["wec_hash"]


# ── corpus ───────────────────────────────────────────────────────────────────

def _corpus_rows(n=3, base_ts=2000):
    rows = []
    for i in range(n):
        wiki = bytes([i]) * 32
        agent = bytes([i + 100]) * 32
        ratio = 1.199 + i * 0.01
        cn = 37 + i
        ts = base_ts + i
        commit = compute_corpus_commitment(wiki, agent, ratio, cn, ts).hex()
        rows.append({"wiki_hash": wiki.hex(), "agent_root": agent.hex(),
                     "separation_ratio": ratio, "corpus_n": cn, "ts_ns": ts,
                     "snapshot_commitment": commit})
    return rows


def test_corpus_commitments_intact():
    rep = verify_corpus_commitments(_corpus_rows(3))
    assert rep.tamper_free and rep.intact and rep.commitments_valid == 3 and rep.n_invalid == 0
    assert rep.head_hex == _corpus_rows(3)[-1]["snapshot_commitment"]


def test_corpus_empty_vacuously_intact():
    rep = verify_corpus_commitments([])
    assert rep.intact and rep.n_rows == 0 and rep.head_hex is None


def test_corpus_tamper_detected():
    rows = _corpus_rows(3)
    rows[1]["snapshot_commitment"] = "00" * 32
    rep = verify_corpus_commitments(rows)
    assert rep.tamper_free is False and rep.n_invalid == 1 and rep.intact is False


def test_corpus_field_tamper_detected():
    """Altering a committed FIELD (corpus_n) without re-deriving the commitment is caught."""
    rows = _corpus_rows(2)
    rows[0]["corpus_n"] = 9999            # commitment no longer matches the fields
    rep = verify_corpus_commitments(rows)
    assert rep.n_invalid == 1 and rep.tamper_free is False


def test_corpus_accepts_bytes_or_hex():
    rows = _corpus_rows(1)
    rows[0]["wiki_hash"] = bytes.fromhex(rows[0]["wiki_hash"])   # raw bytes form
    rep = verify_corpus_commitments(rows)
    assert rep.tamper_free


def test_module_reuses_frozen_primitives_not_reimplements():
    """The verifier must IMPORT the FROZEN compute fns, never define its own SHA-256 chain math."""
    import ast, inspect
    from vapi_bridge import chain_integrity_verifiers as M
    src = inspect.getsource(M)
    assert "from .watchdog_chain import compute_wec" in src
    assert "from .corpus_snapshot import compute_corpus_commitment" in src
    # no hashlib chain math of its own
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "hashlib" not in imported  # delegates all hashing to the FROZEN primitives
