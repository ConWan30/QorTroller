"""A2A-DEPIN-1 LEG 1 (NODE-ID-1) — derived node_id spine.

Rails under test:
  - node_id is DERIVED (SHA-256 domain-tagged preimage), never minted
  - registry-agnostic: VMDR address NOT in preimage
  - additive birth/scorecard: old artifacts read node_id=null honestly
  - over-claim denials: not on-chain, not decentralized-verified pre leg-2
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller as q  # noqa: E402

# Public Path A Arc 1 demo device (on-chain via VMDR; identity is public).
REF_DEVICE_ID = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
REF_FIRST_SESSION = "proof_drill_20260713_123456"


def test_t_depin1_1_derive_deterministic():
    a = q.derive_node_id(REF_DEVICE_ID, REF_FIRST_SESSION)
    b = q.derive_node_id("0x" + REF_DEVICE_ID.upper(), REF_FIRST_SESSION)
    assert a == b
    assert len(a) == 64
    # Hand-recompute preimage (byte-stable contract for NODE-v0 candidate).
    pre = (
        q.NODE_ID_DOMAIN_TAG
        + bytes.fromhex(REF_DEVICE_ID)
        + REF_FIRST_SESSION.encode("utf-8")
    )
    assert a == hashlib.sha256(pre).hexdigest()


def test_t_depin1_2_verify_roundtrip():
    nid = q.derive_node_id(REF_DEVICE_ID, REF_FIRST_SESSION)
    assert q.verify_node_id(nid, REF_DEVICE_ID, REF_FIRST_SESSION) is True
    assert q.verify_node_id(nid, REF_DEVICE_ID, REF_FIRST_SESSION + "x") is False
    assert q.verify_node_id("00" * 32, REF_DEVICE_ID, REF_FIRST_SESSION) is False


def test_t_depin1_3_registry_agnostic_vmdr_not_in_preimage():
    """Changing VMDR evidence constants must not change node_id (not in preimage)."""
    nid = q.derive_node_id(REF_DEVICE_ID, REF_FIRST_SESSION)
    # Evidence strings exist for scorecard transparency only.
    assert q.VMDR_ADDRESS_EVIDENCE.startswith("0x")
    assert "68f6cf49" in q.VMDR_REF_REGISTRATION_TX.lower()
    # Preimage bytes contain domain + device + session only.
    pre = (
        q.NODE_ID_DOMAIN_TAG
        + bytes.fromhex(REF_DEVICE_ID)
        + REF_FIRST_SESSION.encode("utf-8")
    )
    assert q.VMDR_ADDRESS_EVIDENCE.encode() not in pre
    assert bytes.fromhex(q.VMDR_ADDRESS_EVIDENCE[2:]) not in pre
    assert hashlib.sha256(pre).hexdigest() == nid


def test_t_depin1_4_enrich_birth_additive_and_null_honest():
    # Old-shape birth (no device_id) -> node_id null, domain stamped.
    old = {"path": "A", "first_session_id": REF_FIRST_SESSION, "ts": 1}
    e = q.enrich_birth_receipt(old)
    assert e["node_id"] is None
    assert e["node_id_domain"] == q.NODE_ID_DOMAIN
    assert e["first_session_id"] == REF_FIRST_SESSION  # preserved

    # With device_id -> DERIVED node_id.
    e2 = q.enrich_birth_receipt(old, device_id_hex=REF_DEVICE_ID)
    assert e2["node_id"] == q.derive_node_id(REF_DEVICE_ID, REF_FIRST_SESSION)
    assert e2["device_id_hex"] == REF_DEVICE_ID
    assert e2["vmdr_address_evidence"] == q.VMDR_ADDRESS_EVIDENCE
    for banned in q.NODE_ID_MUST_NOT_CLAIM:
        assert banned in e2["node_id_must_not_claim"]


def test_t_depin1_5_scorecard_threads_node_id():
    birth = q.enrich_birth_receipt(
        {"path": "A", "first_session_id": REF_FIRST_SESSION},
        device_id_hex=REF_DEVICE_ID,
    )
    card = q.build_match_scorecard(
        "t",
        kas={
            "verdict": "AUTHORED_SESSION",
            "authored_kills": 1,
            "session_id": "aa" * 32,
        },
        posp={"verdict": "PARTIAL_SURFACES", "session_id": "aa" * 32, "fusion": {}},
        v3=None,
        birth=birth,
    )
    top = card["node_id"]
    assert top["source"] == q.SRC_DERIVED
    assert top["value"]["node_id"] == birth["node_id"]
    assert top["value"]["domain"] == q.NODE_ID_DOMAIN
    assert "on-chain" in " ".join(top["must_not_claim"]).lower() or any(
        "on-chain" in m for m in top["must_not_claim"]
    )
    assert card["rails"]["node_id_derived_not_minted"] is True
    assert "node_id_on_chain" in card["refuted_overclaims"]
    # fields mirror + birth carries node_id
    assert card["fields"]["node_id"]["value"]["node_id"] == birth["node_id"]
    assert card["fields"]["birth"]["value"]["node_id"] == birth["node_id"]


def test_t_depin1_6_scorecard_null_node_without_device():
    birth = {"path": "B", "first_session_id": REF_FIRST_SESSION}  # no device_id
    card = q.build_match_scorecard("t", kas=None, posp=None, v3=None, birth=birth)
    assert card["node_id"]["source"] == q.SRC_ABSENT
    assert card["node_id"]["value"] is None
    text = q.render_match_scorecard(card)
    assert "Node" in text and "(null)" in text
    assert "DERIVED" in text or "device_id" in text.lower()


def test_t_depin1_7_render_shows_short_node_id():
    birth = q.enrich_birth_receipt(
        {"path": "A", "first_session_id": REF_FIRST_SESSION},
        device_id_hex=REF_DEVICE_ID,
    )
    card = q.build_match_scorecard(
        "t",
        kas={"verdict": "FLAG", "authored_kills": 0, "session_id": "bb" * 32},
        posp={"verdict": "UNVERIFIABLE", "session_id": "bb" * 32},
        v3=None,
        birth=birth,
    )
    text = q.render_match_scorecard(card)
    short = q.node_id_short(birth["node_id"])
    assert short in text
    assert "not on-chain" in text or "not minted" in text
    # Must not claim decentralized-verified
    assert "decentralized-verified node" not in text.lower() or "MUST NOT" in text


def test_t_depin1_8_malformed_device_id_raises():
    with pytest.raises(ValueError):
        q.derive_node_id("abc", REF_FIRST_SESSION)
    with pytest.raises(ValueError):
        q.derive_node_id(REF_DEVICE_ID, "")
    with pytest.raises(ValueError):
        q.normalize_device_id_hex("zz" * 32)


def test_t_depin1_9_resolve_device_id_order(tmp_path):
    cert = tmp_path / "device_birth_cert.json"
    cert.write_text(json.dumps({"device_id_hex": REF_DEVICE_ID}), encoding="utf-8")
    # birth wins over cert
    other = "11" * 32
    got = q.resolve_device_id_hex(
        birth={"device_id_hex": other},
        cfg={},
        cert_path=cert,
    )
    assert got == other
    # cfg when birth missing
    got2 = q.resolve_device_id_hex(
        birth={},
        cfg={"device_id_hex": REF_DEVICE_ID},
        cert_path=tmp_path / "missing.json",
    )
    assert got2 == REF_DEVICE_ID
    # cert fallback
    got3 = q.resolve_device_id_hex(birth=None, cfg=None, cert_path=cert)
    assert got3 == REF_DEVICE_ID


def test_t_depin1_10_domain_tag_is_candidate_not_frozen_marker():
    """Domain tag is candidate QORTROLLER-NODE-v0 — not a FROZEN-v1 family claim."""
    assert q.NODE_ID_DOMAIN == "QORTROLLER-NODE-v0"
    assert q.NODE_ID_DOMAIN_TAG == b"QORTROLLER-NODE-v0"
    # Must not look like a VAPI-*-v1 FROZEN tag.
    assert not q.NODE_ID_DOMAIN.startswith("VAPI-")
    assert "FROZEN" not in q.NODE_ID_DOMAIN
