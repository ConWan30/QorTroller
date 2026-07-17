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
    _VAPI_DID_REGISTRY_ADDR,
    assemble_register_calldata,
    build_controller_did_document,
    build_permit_digest,
    register_controller_ioid,
    resolve_ioid_registry_address,
    sign_permit,
)


GOLDEN_DEVICE_ID = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
GOLDEN_PUBKEY = "042adcdb3663a318c9ea385df654fdb09b479366ec9046cc5e02115f3202f7ec1b56d5db4d01a0d341782df9843aa03c700c19d0d4c546299c4eea77b62b000f5e"

# The ioID PERMIT registry (nonces + 8-param register) vs the Phase 55 DID book (no permit).
PERMIT_REGISTRY = "0x0A7e595C7889dF3652A19aF52C18377bF17e027D"
DID_BOOK = _VAPI_DID_REGISTRY_ADDR  # 0xF7885B58... — must be REFUSED for the permit flow


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


def test_register_dry_run_honest_shape():
    """Dry-run returns an HONEST result — NO fabricated tokenId/TBA (F-T3-1 / round-33):
    ioid_token_id and tba_address are None, the resolved permit registry + live nonce are
    surfaced, and pending_prereqs names what blocks a real registration."""
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
        ioid_registry_address=PERMIT_REGISTRY,
        dry_run=True,
    )
    assert res.device_id == GOLDEN_DEVICE_ID
    assert res.dry_run is True
    # No fabricated success surfaces.
    assert res.ioid_token_id is None
    assert res.tba_address is None
    assert res.tx_hash is None
    # Honest evidence: the resolved PERMIT registry (never the DID book) + the live nonce.
    assert res.ioid_registry_address == PERMIT_REGISTRY
    assert res.ioid_registry_address.lower() != DID_BOOK.lower()
    assert res.device_nonce == 5
    assert res.pending_prereqs and any("VAPIGamerControllerNFT" in p for p in res.pending_prereqs)


def test_register_non_dry_run_refuses_to_fabricate():
    """A non-dry-run call must RAISE (registration is blocked on prereqs + real send not
    wired), never fabricate a tx/tokenId/TBA like the old skeleton did."""
    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock()
    pin.pin_json.return_value = "bafytestcid456"
    gamer = Account.create()

    with pytest.raises(NotImplementedError, match="not wired"):
        register_controller_ioid(
            web3=w3,
            device_id_hex=GOLDEN_DEVICE_ID,
            p256_pubkey_hex=GOLDEN_PUBKEY,
            gamer_address=gamer.address,
            gamer_private_key=gamer.key.hex(),
            birth_cert_cid="bafyreal",
            mfg_registry_tx=None,
            pinata_client=pin,
            ioid_registry_address=PERMIT_REGISTRY,
            dry_run=False,
        )


def test_permit_flow_reads_live_nonce_with_mocked_web3():
    """Full permit construction path + live nonce read via mocked web3; DID pinned."""
    w3 = _make_mock_web3(nonce_return=7)
    pin = MagicMock()
    pin.pin_json.return_value = "bafypermitflow"

    res = register_controller_ioid(
        web3=w3,
        device_id_hex=GOLDEN_DEVICE_ID,
        p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address="0x" + "cc" * 20,
        gamer_private_key=None,  # dry-run path
        birth_cert_cid=None,
        mfg_registry_tx="0xabc",
        pinata_client=pin,
        ioid_registry_address=PERMIT_REGISTRY,
        dry_run=True,
    )
    assert res.device_id == GOLDEN_DEVICE_ID
    assert res.device_nonce == 7
    assert res.ioid_token_id is None
    assert res.did_cid == "bafypermitflow"


# ── F-T3-1 registry resolution + refusal (A2A round-33) ───────────────────────

def test_resolve_ioid_registry_prefers_dedicated_permit_env(monkeypatch, tmp_path):
    monkeypatch.setenv("IOID_PERMIT_REGISTRY_ADDRESS", PERMIT_REGISTRY)
    monkeypatch.delenv("IOID_REGISTRY_ADDRESS", raising=False)
    assert resolve_ioid_registry_address(deployed_addresses_path=tmp_path / "none.json") == PERMIT_REGISTRY


def test_resolve_ioid_registry_from_deployed_addresses(monkeypatch, tmp_path):
    monkeypatch.delenv("IOID_PERMIT_REGISTRY_ADDRESS", raising=False)
    monkeypatch.delenv("IOID_REGISTRY_ADDRESS", raising=False)
    p = tmp_path / "deployed-addresses.json"
    p.write_text(json.dumps({"ioIDRegistry": PERMIT_REGISTRY}), encoding="utf-8")
    assert resolve_ioid_registry_address(deployed_addresses_path=p) == PERMIT_REGISTRY


def test_resolve_ioid_registry_SKIPS_did_book_env_falls_through(monkeypatch, tmp_path):
    """grok F3: the SHARED env legitimately holds the DID book for Phase 55 DID work.
    The resolver SKIPS it (not fatal) and falls through to the permit registry."""
    monkeypatch.delenv("IOID_PERMIT_REGISTRY_ADDRESS", raising=False)
    monkeypatch.setenv("IOID_REGISTRY_ADDRESS", DID_BOOK)  # ambient DID config
    p = tmp_path / "deployed-addresses.json"
    p.write_text(json.dumps({"ioIDRegistry": PERMIT_REGISTRY}), encoding="utf-8")
    assert resolve_ioid_registry_address(deployed_addresses_path=p) == PERMIT_REGISTRY


def test_resolve_ioid_registry_raises_when_only_did_book_and_zero(monkeypatch, tmp_path):
    """If EVERY candidate is the DID book / zero and no permit registry is reachable, fail loud."""
    monkeypatch.setenv("IOID_PERMIT_REGISTRY_ADDRESS", "0x" + "00" * 20)
    monkeypatch.setenv("IOID_REGISTRY_ADDRESS", DID_BOOK)
    p = tmp_path / "deployed-addresses.json"
    p.write_text(json.dumps({"VAPIioIDRegistry": DID_BOOK}), encoding="utf-8")  # only the DID book
    # Neutralize the agent-constant fallback so nothing valid remains.
    monkeypatch.setattr(
        "vapi_bridge.agent_registration.IOID_REGISTRY_ADDR", DID_BOOK, raising=False)
    with pytest.raises(ValueError, match="no ioID PERMIT registry"):
        resolve_ioid_registry_address(deployed_addresses_path=p)


def test_register_refuses_explicit_did_book(monkeypatch):
    """Passing the DID book explicitly as ioid_registry_address is refused too."""
    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock()
    pin.pin_json.return_value = "bafy"
    with pytest.raises(ValueError, match="DID book"):
        register_controller_ioid(
            web3=w3, device_id_hex=GOLDEN_DEVICE_ID, p256_pubkey_hex=GOLDEN_PUBKEY,
            gamer_address="0x" + "bb" * 20, gamer_private_key=None,
            birth_cert_cid=None, mfg_registry_tx=None, pinata_client=pin,
            ioid_registry_address=DID_BOOK, dry_run=True,
        )


def test_assemble_register_calldata_canonical_order():
    """F6: calldata follows the LIVE ioIDRegistry order (deviceContract, tokenId, device,
    hash, uri, v, r, s) — decodes back to exactly what was encoded."""
    from eth_abi import decode
    dc = "0x" + "ab" * 20
    dev = "0x" + "cd" * 20
    h = b"\x11" * 32
    data = assemble_register_calldata(
        device_contract=dc, token_id=7, device=dev, did_hash=h,
        uri="ipfs://x", v=27, r=b"\x22" * 32, s=b"\x33" * 32,
    )
    decoded = decode(
        ["address", "uint256", "address", "bytes32", "string", "uint8", "bytes32", "bytes32"],
        data,
    )
    assert decoded[0].lower() == dc.lower()   # deviceContract FIRST (was projectId in skeleton)
    assert decoded[1] == 7                     # tokenId (absent in skeleton)
    assert decoded[2].lower() == dev.lower()   # device
    assert decoded[3] == h                      # hash


# ── ioID Inc-B — Option-A correctness (A2A round-01 F2) ───────────────────────

def test_inc_b_content_hash_is_canonical_did_doc_keccak():
    """compute_did_content_hash hashes the canonical-JSON DID DOCUMENT (agent-consistent),
    NOT the CID string (the old bug)."""
    import json as _json
    from web3 import Web3 as _W3
    from vapi_bridge.controller_ioid_registration import (
        build_controller_did_document, compute_did_content_hash,
    )
    doc = build_controller_did_document(
        device_id_hex=GOLDEN_DEVICE_ID, ecdsa_p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address="0x" + "aa" * 20)
    expected = _W3.keccak(text=_json.dumps(doc, sort_keys=True, separators=(",", ":"))).hex()
    assert compute_did_content_hash(doc) == expected
    # and it is NOT the old CID-string hash
    assert compute_did_content_hash(doc) != _W3.keccak(text="bafysomecid").hex()


def test_inc_b_register_calldata_device_is_gamer_not_device_id():
    """F2: the register `device` slot decodes to the GAMER EOA, never the truncated device_id."""
    from unittest.mock import MagicMock
    from eth_abi import decode
    from web3 import Web3 as _W3
    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock(); pin.pin_json.return_value = "bafy"
    gamer = "0x" + "bb" * 20
    # capture the calldata by patching assemble_register_calldata? simpler: re-derive from result path.
    # The dry-run result doesn't expose calldata, so assert via the assembler directly with device=gamer.
    from vapi_bridge.controller_ioid_registration import assemble_register_calldata
    data = assemble_register_calldata(
        device_contract="0x" + "cd" * 20, token_id=1,
        device=_W3.to_checksum_address(gamer), did_hash=b"\x11" * 32,
        uri="ipfs://x", v=27, r=b"\x22" * 32, s=b"\x33" * 32)
    decoded = decode(["address", "uint256", "address", "bytes32", "string", "uint8", "bytes32", "bytes32"], data)
    assert decoded[2].lower() == gamer.lower()  # device slot == gamer
    # and NOT the truncated device_id
    trunc = "0x" + GOLDEN_DEVICE_ID[-40:]
    assert decoded[2].lower() != trunc.lower()


def test_inc_b_permit_recovers_to_gamer_so_device_must_be_gamer():
    """ecrecover proof: the gamer-signed permit recovers to the gamer, so under Option A the
    on-chain `device` (ecrecover target) MUST be the gamer EOA."""
    from eth_keys import keys as ekeys
    from vapi_bridge.controller_ioid_registration import build_permit_digest, sign_permit
    gamer = Account.create()
    digest = build_permit_digest("0x" + "22" * 20, gamer.address, 0)
    v, r, s = sign_permit(gamer.key.hex(), digest)
    sig = ekeys.Signature(vrs=(v - 27, int.from_bytes(r, "big"), int.from_bytes(s, "big")))
    recovered = sig.recover_public_key_from_msg_hash(digest).to_checksum_address()
    assert recovered.lower() == gamer.address.lower()


def test_inc_b_assert_option_a_register_ready_guards():
    """The real-register guard refuses device!=gamer, zero deviceContract, and zero tokenId."""
    from vapi_bridge.controller_ioid_registration import assert_option_a_register_ready
    gamer = "0x" + "ab" * 20
    nft = "0x" + "cd" * 20
    # happy path
    assert_option_a_register_ready(device_contract=nft, token_id=1, device=gamer, gamer_address=gamer)
    # device != gamer
    with pytest.raises(ValueError, match="must equal the gamer EOA"):
        assert_option_a_register_ready(device_contract=nft, token_id=1,
                                       device="0x" + "ee" * 20, gamer_address=gamer)
    # zero NFT
    with pytest.raises(ValueError, match="VAPIGamerControllerNFT"):
        assert_option_a_register_ready(device_contract="0x" + "00" * 20, token_id=1,
                                       device=gamer, gamer_address=gamer)
    # zero tokenId
    with pytest.raises(ValueError, match="minted controller-NFT tokenId"):
        assert_option_a_register_ready(device_contract=nft, token_id=0,
                                       device=gamer, gamer_address=gamer)


def test_inc_b_f1_assembled_hash_is_full_32_bytes_and_device_is_gamer(monkeypatch):
    """grok r02 F1/F4: capture the ACTUAL assembled args from register_controller_ioid (not just the
    pure fn). The did_hash must be the FULL 32-byte canonical-DID-doc keccak (not 31 bytes from a
    stray [2:]) and the device slot must be the gamer."""
    import json as _json
    from web3 import Web3 as _W3
    import vapi_bridge.controller_ioid_registration as cir

    captured = {}
    real_assemble = cir.assemble_register_calldata

    def _spy(**kwargs):
        captured.update(kwargs)
        return real_assemble(**kwargs)

    monkeypatch.setattr(cir, "assemble_register_calldata", _spy)

    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock(); pin.pin_json.return_value = "bafyxyz"
    gamer = "0x" + "bb" * 20
    cir.register_controller_ioid(
        web3=w3, device_id_hex=GOLDEN_DEVICE_ID, p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address=gamer, gamer_private_key=None, birth_cert_cid=None,
        mfg_registry_tx=None, pinata_client=pin, ioid_registry_address=PERMIT_REGISTRY, dry_run=True)

    # F1: the assembled hash is FULL 32 bytes and equals the canonical DID-doc keccak.
    assert len(captured["did_hash"]) == 32
    doc = cir.build_controller_did_document(
        device_id_hex=GOLDEN_DEVICE_ID, ecdsa_p256_pubkey_hex=GOLDEN_PUBKEY, gamer_address=gamer)
    expected = _W3.keccak(text=_json.dumps(doc, sort_keys=True, separators=(",", ":")))
    assert captured["did_hash"] == bytes(expected)
    # F4: device slot is the gamer (checksummed), not the truncated device_id.
    assert captured["device"].lower() == gamer.lower()
