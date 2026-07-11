"""PORT-CERT tests — the portable Match Certificate + off-rig verifier.

Pins: bundle assembly (reference-only + honesty fields); the full VERIFIED path (all hard checks +
injected ZK + injected chain); FAILED on session-join mismatch / non-SYNCHRONIZED / digest mismatch /
ZK-false / ZK-raises; PARTIAL when a hard check is UNCHECKED (no snarkjs or no chain RPC — never a
false VERIFIED); load fail-open.
"""
from __future__ import annotations

import hashlib
import json

from l9_presence.port_cert import (
    MATCH_CERT_SCHEMA,
    build_match_certificate,
    load_and_verify,
    verify_match_certificate,
)

_SID = "b" * 64
_DIG = hashlib.sha256(b'{"posp":"file"}').hexdigest()   # the "published PoSP file" digest


def _posp(sid=_SID, verdict="SYNCHRONIZED", dig=_DIG):
    return {"verdict": verdict, "session_id": sid, "device_id": "dev1",
            "file_sha256": dig, "record_path": "audits/posp_record_x.json"}


def _kas(sid=_SID):
    return {"commitment": "aa" * 32, "verdict": "AUTHORED_SESSION", "session_id": sid}


def _vhr():
    return {"replay_proof_token": "0x" + "c" * 64, "public_inputs": ["1", "2", "3", "4", "5", "6"],
            "poac_chain_root": "978cb10e", "sanitized_trace_root": "deadbeef",
            "proof_ref": "audits/vhr/proof.json", "public_ref": "audits/vhr/public.json",
            "vkey_ref": "zk_artifacts/vkey.json"}


def _anchor(dig=_DIG):
    return {"registry": "0x44CF981f", "tx": "da3a8547", "block": 45447322, "digest": dig,
            "method": "recordAdjudication"}


def _cert(**kw):
    return build_match_certificate(posp=_posp(), kas=_kas(), vhr=_vhr(), anchor=_anchor(), **kw)


# ------------------------------------------------------------------- builder
def test_build_references_and_honesty():
    c = _cert()
    assert c["schema"] == MATCH_CERT_SCHEMA and c["session_id"] == _SID
    assert c["advisory"] is True and c["cert_scope"] == "developer_self"
    assert c["population_certified"] is False and c["verifier_independence"] is False
    assert c["surfaces"]["posp"]["verdict"] == "SYNCHRONIZED"
    assert c["surfaces"]["vhr"]["public_inputs"] == ["1", "2", "3", "4", "5", "6"]
    assert c["surfaces"]["deferred"] is None      # not supplied -> honest null


# ------------------------------------------------------------------- full VERIFIED
def test_full_verified_requires_zk_and_chain():
    """VERIFIED only when every hard check passes AND the ZK proof verifies AND the on-chain anchor
    is confirmed (reading the chain — a forger could fabricate the anchor ref)."""
    rep = verify_match_certificate(_cert(), posp_file_bytes=b'{"posp":"file"}',
                                   groth16_verify=lambda vhr: True, chain_lookup=lambda tx: True)
    assert rep.overall == "VERIFIED" and rep.passed()


# ------------------------------------------------------------------- FAILED paths
def test_schema_error():
    rep = verify_match_certificate({"schema": "nope"})
    assert rep.overall == "SCHEMA_ERROR"


def test_session_join_mismatch_fails():
    c = build_match_certificate(posp=_posp(), kas=_kas(sid="f" * 64), vhr=_vhr(), anchor=_anchor())
    rep = verify_match_certificate(c, posp_file_bytes=b'{"posp":"file"}',
                                   groth16_verify=lambda v: True, chain_lookup=lambda t: True)
    assert rep.overall == "FAILED"
    assert any(ch.name == "session_join" and ch.passed is False for ch in rep.checks)


def test_non_synchronized_fails():
    c = build_match_certificate(posp=_posp(verdict="PARTIAL_SURFACES"), anchor=_anchor(), vhr=_vhr())
    rep = verify_match_certificate(c, posp_file_bytes=b'{"posp":"file"}',
                                   groth16_verify=lambda v: True, chain_lookup=lambda t: True)
    assert rep.overall == "FAILED"


def test_digest_mismatch_fails():
    """The published PoSP file does NOT hash to the anchored digest -> tamper caught."""
    rep = verify_match_certificate(_cert(), posp_file_bytes=b"DIFFERENT BYTES",
                                   groth16_verify=lambda v: True, chain_lookup=lambda t: True)
    assert rep.overall == "FAILED"
    assert any(ch.name == "anchor_digest_match" and ch.passed is False for ch in rep.checks)


def test_zk_false_fails():
    rep = verify_match_certificate(_cert(), posp_file_bytes=b'{"posp":"file"}',
                                   groth16_verify=lambda v: False, chain_lookup=lambda t: True)
    assert rep.overall == "FAILED"


def test_zk_raises_is_fail_not_crash():
    def boom(vhr):
        raise RuntimeError("snarkjs missing")
    rep = verify_match_certificate(_cert(), posp_file_bytes=b'{"posp":"file"}',
                                   groth16_verify=boom, chain_lookup=lambda t: True)
    assert rep.overall == "FAILED"
    assert any(ch.name == "vhr_zk_proof" and ch.passed is False for ch in rep.checks)


# ------------------------------------------------------------------- PARTIAL (honest UNCHECKED)
def test_no_snarkjs_is_partial_not_verified():
    """Offline verify without snarkjs -> ZK UNCHECKED -> PARTIAL, never a false VERIFIED."""
    rep = verify_match_certificate(_cert(), posp_file_bytes=b'{"posp":"file"}',
                                   chain_lookup=lambda t: True)   # no groth16_verify
    assert rep.overall == "PARTIAL"
    assert any(ch.name == "vhr_zk_proof" and ch.passed is None for ch in rep.checks)


def test_no_chain_lookup_is_partial():
    """Even with ZK verified, no chain RPC -> anchor UNCHECKED -> PARTIAL (can't claim it's really anchored)."""
    rep = verify_match_certificate(_cert(), posp_file_bytes=b'{"posp":"file"}',
                                   groth16_verify=lambda v: True)   # no chain_lookup
    assert rep.overall == "PARTIAL"


def test_offline_digest_consistency_partial():
    """No posp file supplied but anchor present -> C4 checks cert-internal consistency; PARTIAL overall."""
    rep = verify_match_certificate(_cert())   # nothing injected
    assert rep.overall == "PARTIAL"
    assert any(ch.name == "anchor_digest_match" and ch.passed is True for ch in rep.checks)


def test_authorship_advisory_note():
    rep = verify_match_certificate(_cert())
    a = next(ch for ch in rep.checks if ch.name == "authorship")
    assert a.passed is True     # kas AUTHORED_SESSION


def test_to_dict_serializable():
    rep = verify_match_certificate(_cert())
    d = rep.to_dict()
    assert d["overall"] == "PARTIAL" and json.dumps(d)   # round-trips


def test_load_fail_open(tmp_path):
    rep = load_and_verify(str(tmp_path / "missing.json"))
    assert rep.overall == "SCHEMA_ERROR"
