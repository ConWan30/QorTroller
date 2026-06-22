"""Tests for the Synthesis Integrity Chain (SIC) — pure, no vault/crypto deps."""
from __future__ import annotations

import sys
from pathlib import Path

_VSD = Path(__file__).resolve().parent.parent.parent / "vsd-vault" / ".vsd"
sys.path.insert(0, str(_VSD))

import synthesis_integrity_chain as sic  # noqa: E402

_PBSA = "a" * 64
_COMMIT = "b" * 64


def test_genesis_deterministic_and_32b():
    g1 = sic.genesis_sic("vault-x", 111)
    assert g1 == sic.genesis_sic("vault-x", 111) and len(g1) == 32
    assert g1 != sic.genesis_sic("vault-y", 111)
    assert g1 != sic.genesis_sic("vault-x", 222)


def test_compute_deterministic_and_sensitive():
    g = sic.genesis_sic("v", 1)
    a = sic.compute_sic(g, _PBSA, True, True, 0, 100)
    assert a == sic.compute_sic(g, _PBSA, True, True, 0, 100) and len(a) == 32
    assert a != sic.compute_sic(g, _PBSA, False, True, 0, 100)   # harness flag matters
    assert a != sic.compute_sic(g, _PBSA, True, False, 0, 100)   # pv_ci flag matters
    assert a != sic.compute_sic(g, _PBSA, True, True, 3, 100)    # drift matters
    assert a != sic.compute_sic(g, _PBSA, True, True, 0, 101)    # ts matters


def test_empty_pbsa_allowed():
    g = sic.genesis_sic("v", 1)
    assert len(sic.compute_sic(g, "", True, True, 0, 5)) == 32


def test_bad_pbsa_hash_rejected():
    g = sic.genesis_sic("v", 1)
    try:
        sic.compute_sic(g, "deadbeef", True, True, 0, 5)
        assert False, "should reject non-32-byte pbsa hash"
    except ValueError:
        pass


def test_verify_chain_happy_and_tamper():
    vid, gts = "vault-z", 1000
    prev = sic.genesis_sic(vid, gts)
    links = []
    for i in range(3):
        ts = 2000 + i
        h = sic.compute_sic(prev, _PBSA, True, True, 0, ts).hex()
        links.append({"pbsa_manifest_hash": _PBSA, "harness_pass": True, "pv_ci_pass": True,
                      "mythos_drift": 0, "ts_ns": ts, "sic_hex": h})
        prev = bytes.fromhex(h)
    assert sic.verify_chain(vid, gts, links) is True
    # tamper a middle link
    bad = [dict(x) for x in links]
    bad[1]["sic_hex"] = "00" + bad[1]["sic_hex"][2:]
    assert sic.verify_chain(vid, gts, bad) is False
    # tamper a field that changes the recompute
    bad2 = [dict(x) for x in links]
    bad2[2]["harness_pass"] = False
    assert sic.verify_chain(vid, gts, bad2) is False
