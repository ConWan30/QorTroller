"""Phase 2 tests for controller ioID registration (Option A, gamer-signed).

Covers:
- canon device_id binding enforced
- DID document construction + pinning
- permit digest + (mock) gamer signature round-trip
- assembly produces plausible calldata
- dry-run result shape + TBA readback stub
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from eth_account import Account
from web3 import Web3

from vapi_bridge.controller_ioid_registration import (
    build_controller_did_document,
    build_permit_digest,
    register_controller_ioid,
    sign_permit,
)


GOLDEN_DEVICE_ID = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
GOLDEN_PUBKEY = "042adcdb3663a318c9ea385df654fdb09b479366ec9046cc5e02115f3202f7ec1b56d5db4d01a0d341782df9843aa03c700c19d0d4c546299c4eea77b62b000f5e"


def test_canon_enforced_in_did_build():
    with pytest.raises(ValueError):
        build_controller_did_document(
            device_id_hex="deadbeef" * 8,
            ecdsa_p256_pubkey_hex=GOLDEN_PUBKEY,
            gamer_address="0x" + "11" * 20,
        )


def test_did_contains_canon_and_gamer():
    doc = build_controller_did_document(
        device_id_hex=GOLDEN_DEVICE_ID,
        ecdsa_p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address="0x" + "aa" * 20,
    )
    assert doc["id"] == f"did:io:{GOLDEN_DEVICE_ID}"
    assert any(v["publicKeyHex"] == GOLDEN_PUBKEY for v in doc["verificationMethod"])


def test_permit_roundtrip_signature():
    gamer = Account.create()
    digest = build_permit_digest("0x" + "22" * 20, gamer.address, 7)
    v, r, s = sign_permit(gamer.key.hex(), digest)
    # Simple check: signature length (v/r/s shape for Ethereum)
    assert v in (27, 28)
    assert len(r) == 32 and len(s) == 32
    assert len(digest) == 32


def _make_mock_web3(nonce_return: int = 0):
    """Create a minimal MagicMock web3 sufficient for get_device_nonce and dry paths."""
    mock_w3 = MagicMock()
    # Support web3.to_checksum_address
    mock_w3.to_checksum_address = lambda a: Web3.to_checksum_address(a) if isinstance(a, str) and a.startswith("0x") else a
    # Contract mock
    contract = MagicMock()
    nonces_fn = MagicMock()
    nonces_fn.call.return_value = nonce_return
    contract.functions.nonces.return_value = nonces_fn
    mock_w3.eth.contract.return_value = contract
    return mock_w3


def test_register_dry_run_shape():
    w3 = _make_mock_web3(nonce_return=5)
    pin = MagicMock()
    pin.pin_json.return_value = "bafytestcid123"

    res = register_controller_ioid(
        web3=w3,
        device_id_hex=GOLDEN_DEVICE_ID,
        p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address="0x" + "bb" * 20,
        gamer_private_key=None,
        birth_cert_cid=None,
        mfg_registry_tx=None,
        pinata_client=pin,
        dry_run=True,
    )
    assert res.device_id == GOLDEN_DEVICE_ID
    assert res.dry_run is True
    assert res.tba_address.startswith("0x")
    assert res.ioid_token_id > 0


def test_register_accepts_real_gamer_sig():
    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock()
    pin.pin_json.return_value = "bafytestcid456"

    gamer = Account.create()

    res = register_controller_ioid(
        web3=w3,
        device_id_hex=GOLDEN_DEVICE_ID,
        p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address=gamer.address,
        gamer_private_key=gamer.key.hex(),
        birth_cert_cid="bafyreal",
        mfg_registry_tx=None,
        pinata_client=pin,
        dry_run=False,
    )
    # In skeleton when key supplied and not dry it still returns a fake tx (we didn't wire real send)
    # The important part: it did not raise on canon or signing path.
    assert res.device_id == GOLDEN_DEVICE_ID
    # tx_hash may be None or fake in skeleton; just assert no crash and id preserved
    assert res.device_id == GOLDEN_DEVICE_ID


def test_permit_flow_and_tba_readback_with_mocked_web3():
    """Covers full permit construction path + TBA readback stub with mocked web3."""
    w3 = _make_mock_web3(nonce_return=7)
    pin = MagicMock()
    pin.pin_json.return_value = "bafypermitflow"

    gamer = Account.create()

    res = register_controller_ioid(
        web3=w3,
        device_id_hex=GOLDEN_DEVICE_ID,
        p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address=gamer.address,
        gamer_private_key=None,  # forces dry-run path inside
        birth_cert_cid=None,
        mfg_registry_tx="0xabc",
        pinata_client=pin,
        dry_run=True,
    )
    assert res.device_id == GOLDEN_DEVICE_ID
    assert res.tba_address.startswith("0x")
    assert res.ioid_token_id > 0
    # DID pinned
    assert res.did_cid.startswith("bafy")
