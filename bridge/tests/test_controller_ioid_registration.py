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

# CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): many other test files in this
# suite blanket-stub sys.modules["web3"]/["eth_account"] = MagicMock() for their own
# isolation/speed and never clean it up. Whichever gets collected first poisons every
# later import -- this file's tests need the REAL web3 (Web3.to_checksum_address /
# .keccak for genuine cryptographic values, not a MagicMock that silently satisfies any
# attribute access) AND real eth_account (web3 itself imports eth_account.datastructures
# internally, so a poisoned eth_account breaks web3's own import even after web3 itself
# is un-poisoned). Force fresh, real imports of both regardless of collection order.
for _mod_name in ("web3", "eth_account"):
    if isinstance(sys.modules.get(_mod_name), MagicMock):
        del sys.modules[_mod_name]

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


def test_register_non_dry_run_without_prereqs_fails_closed():
    """Inc-D: a non-dry-run call WITHOUT the Inc-A/Inc-C prerequisites (a real deployed
    device_contract + a minted tokenId) must FAIL-CLOSED via assert_option_a_register_ready --
    never fabricate a tx/tokenId/TBA. device_contract defaults to the zero placeholder here."""
    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock()
    pin.pin_json.return_value = "bafytestcid456"
    gamer = Account.create()

    with pytest.raises(ValueError, match="device_contract"):
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
        )  # device_contract/token_id default to placeholders -> the guard refuses


def test_register_non_dry_run_option_a_signer_must_be_sender():
    """Inc-D: with real prereqs but a gamer_private_key whose address != the gamer EOA, the send
    is refused (Option A: the permit signer MUST be the tx sender; ecrecover would fail otherwise).
    Trips before any chain write."""
    w3 = _make_mock_web3(nonce_return=0)
    pin = MagicMock(); pin.pin_json.return_value = "bafytestcid456"
    gamer = Account.create()          # the declared gamer EOA
    other = Account.create()          # a DIFFERENT key
    with pytest.raises(ValueError, match="signer must be the tx sender"):
        register_controller_ioid(
            web3=w3, device_id_hex=GOLDEN_DEVICE_ID, p256_pubkey_hex=GOLDEN_PUBKEY,
            gamer_address=gamer.address, gamer_private_key=other.key.hex(),
            birth_cert_cid="bafyreal", mfg_registry_tx=None, pinata_client=pin,
            ioid_registry_address=PERMIT_REGISTRY, dry_run=False,
            device_contract="0x" + "cc" * 20, token_id=1,
        )


def test_ioid_minted_token_id_parser():
    """Inc-D: the ioID DID tokenId readback parser (load-bearing, per the Inc-C lesson).
    Owner-AGNOSTIC (any `to`), requires the ioID contract + from==0x0 + a 4-topic Transfer;
    skips ERC-20-shaped 3-topic logs and foreign contracts; never IndexErrors."""
    from vapi_bridge.controller_ioid_registration import _ioid_minted_token_id, _TRANSFER_TOPIC0
    IOID = "0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7"
    zero = "0x" + "00" * 32
    to_topic = "0x" + "00" * 12 + "ab" * 20

    class _L:
        def __init__(s, address, topics): s.address, s.topics = address, topics

    def mint(tid, contract=IOID):
        return _L(contract, [_TRANSFER_TOPIC0, zero, to_topic, "0x" + f"{tid:064x}"])

    assert _ioid_minted_token_id([mint(497)], IOID) == 497                       # owner-agnostic hit
    assert _ioid_minted_token_id([mint(5, contract="0x" + "ee" * 20)], IOID) is None  # foreign contract
    # from != 0 (a plain transfer, not a mint) -> skipped
    non_mint = _L(IOID, [_TRANSFER_TOPIC0, to_topic, to_topic, "0x" + f"{9:064x}"])
    assert _ioid_minted_token_id([non_mint], IOID) is None
    # ERC-20-shaped 3-topic Transfer with the same topic0 -> skipped, no IndexError
    erc20 = _L(IOID, [_TRANSFER_TOPIC0, zero, to_topic])
    assert _ioid_minted_token_id([erc20], IOID) is None
    assert _ioid_minted_token_id([], IOID) is None


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


# ── Inc-D real-send end-to-end (mocked web3), incl. grok r07 F1 fail-closed ────
def _make_send_mock_web3(*, status, mint_logs, tba, price_wei=10**17, nonce=0):
    """Mock web3 for the Inc-D real send: nonces/price/register(estimate+build)/send/receipt/wallet."""
    from web3 import Web3 as _W3
    w3 = MagicMock()
    w3.to_checksum_address = staticmethod(lambda a: _W3.to_checksum_address(a))

    def _contract(address=None, abi=None):
        c = MagicMock()
        c.functions.nonces.return_value.call.return_value = nonce
        c.functions.price.return_value.call.return_value = price_wei
        reg = MagicMock()
        reg.estimate_gas.return_value = 120000
        def _build(p):
            w3._cap = {"est_value": None, "build_value": p["value"]}
            return {"to": _W3.to_checksum_address(address), "data": "0x",
                    "nonce": p["nonce"], "gas": p["gas"], "gasPrice": p["gasPrice"],
                    "chainId": p["chainId"], "value": p["value"]}
        reg.build_transaction.side_effect = _build
        c.functions.register.return_value = reg
        c.functions.wallet.return_value.call.return_value = (tba, "did:io:controller")
        return c

    w3.eth.contract.side_effect = _contract
    w3.eth.gas_price = 10 ** 12
    w3.eth.get_transaction_count.return_value = nonce
    w3.eth.send_raw_transaction.return_value = bytes.fromhex("ab" * 32)
    rcpt = MagicMock(); rcpt.status = status; rcpt.logs = mint_logs
    w3.eth.wait_for_transaction_receipt.return_value = rcpt
    return w3


def _ioid_mint_log(token_id, to_addr):
    from vapi_bridge.controller_ioid_registration import _TRANSFER_TOPIC0
    IOID = "0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7"

    class _L:
        def __init__(s, address, topics): s.address, s.topics = address, topics
    zero = "0x" + "00" * 32
    to_t = "0x" + "00" * 12 + to_addr.replace("0x", "")
    return _L(IOID, [_TRANSFER_TOPIC0, zero, to_t, "0x" + f"{token_id:064x}"])


def _real_send(w3, gamer, pin):
    return register_controller_ioid(
        web3=w3, device_id_hex=GOLDEN_DEVICE_ID, p256_pubkey_hex=GOLDEN_PUBKEY,
        gamer_address=gamer.address, gamer_private_key=gamer.key.hex(),
        birth_cert_cid="bafyreal", mfg_registry_tx=None, pinata_client=pin,
        ioid_registry_address=PERMIT_REGISTRY, dry_run=False,
        device_contract="0x" + "cc" * 20, token_id=1)


def test_inc_d_real_send_happy_path_returns_id_and_tba():
    tba = "0x" + "dd" * 20
    w3 = _make_send_mock_web3(status=1, mint_logs=[_ioid_mint_log(497, "0x" + "ab" * 20)], tba=tba)
    pin = MagicMock(); pin.pin_json.return_value = "bafycid"
    gamer = Account.create()
    res = _real_send(w3, gamer, pin)
    assert res.dry_run is False
    assert res.ioid_token_id == 497
    assert res.tba_address.lower() == tba.lower()
    assert res.tx_hash and res.tx_hash.startswith("0x")
    assert res.pending_prereqs is None
    # F-INC-D-2: register sends value=0 (the fee is the applyIoIDs prepay, not msg.value).
    assert w3.eth.wait_for_transaction_receipt.called
    assert w3._cap["build_value"] == 0


def test_inc_d_real_send_status1_but_no_mint_log_raises():
    """grok r07 F1: mined status=1 with no ioID mint Transfer must NOT return success-shaped None."""
    w3 = _make_send_mock_web3(status=1, mint_logs=[], tba="0x" + "dd" * 20)
    pin = MagicMock(); pin.pin_json.return_value = "bafycid"
    with pytest.raises(RuntimeError, match="NO ioID mint Transfer"):
        _real_send(w3, Account.create(), pin)


def test_inc_d_real_send_zero_tba_raises():
    """grok r07 F1: a zero TBA from ioID.wallet() must fail-closed, not report success."""
    w3 = _make_send_mock_web3(status=1, mint_logs=[_ioid_mint_log(497, "0x" + "ab" * 20)],
                              tba="0x" + "00" * 20)
    pin = MagicMock(); pin.pin_json.return_value = "bafycid"
    with pytest.raises(RuntimeError, match="zero/empty TBA"):
        _real_send(w3, Account.create(), pin)


def test_inc_d_real_send_reverted_status_raises():
    w3 = _make_send_mock_web3(status=0, mint_logs=[], tba="0x" + "dd" * 20)
    pin = MagicMock(); pin.pin_json.return_value = "bafycid"
    with pytest.raises(RuntimeError, match="register reverted"):
        _real_send(w3, Account.create(), pin)


def test_inc_d_insufficient_ioid_maps_to_prepay_instruction():
    """F-INC-D-2 (learned live): the ioID register consumes a project's PRE-PAID activeIoID; without
    a prior applyIoIDs the live registry reverts 'insufficient ioID'. That revert must map to an
    actionable prepay instruction (apply-ioids), not a raw ContractLogicError."""
    w3 = _make_send_mock_web3(status=1, mint_logs=[], tba="0x" + "dd" * 20)

    def _contract(address=None, abi=None):
        c = MagicMock()
        c.functions.nonces.return_value.call.return_value = 0
        c.functions.price.return_value.call.return_value = 10 ** 17
        reg = MagicMock()
        reg.estimate_gas.side_effect = Exception("execution simulation is reverted due to the reason: insufficient ioID")
        c.functions.register.return_value = reg
        return c

    w3.eth.contract.side_effect = _contract
    pin = MagicMock(); pin.pin_json.return_value = "bafycid"
    with pytest.raises(RuntimeError, match="apply-ioids"):
        _real_send(w3, Account.create(), pin)
