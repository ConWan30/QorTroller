"""Phase B ② P4b — SDK tests for VAPIPoEPRegistryClient (§5(d) round-trip + no-key-handling)."""

from __future__ import annotations

import hashlib
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import VAPIPoEPRegistryClient  # noqa: E402

REG = "0x00000000000000000000000000000000000000Ab"
DEV_B32 = hashlib.sha256(b"Sony_DualShock_Edge_CFI-ZCP1").digest()
BLOB = b"\x01" + b"composite-pubkey-blob"
COMMIT = hashlib.sha256(b"poep-commit").digest()


def test_build_register_tx_roundtrip():
    from eth_abi import decode as abi_decode
    from eth_utils import keccak

    c = VAPIPoEPRegistryClient(registry_address=REG)
    tx = c.build_register_tx(DEV_B32, BLOB, COMMIT, from_address=REG, nonce=7, chain_id=4690)
    assert tx["to"] == REG and tx["value"] == 0 and tx["chainId"] == 4690 and tx["nonce"] == 7
    data = bytes.fromhex(tx["data"][2:])
    # selector matches registerDevice(bytes32,bytes,bytes32,uint64)
    assert data[:4] == keccak(b"registerDevice(bytes32,bytes,bytes32,uint64)")[:4]
    dev, blob, commit, expires = abi_decode(["bytes32", "bytes", "bytes32", "uint64"], data[4:])
    assert dev == DEV_B32
    assert blob == BLOB
    assert commit == COMMIT
    assert expires == 0  # Option A / Property X: always 0


def test_option_a_no_expires_param_in_signature():
    # v1 build_register_tx signature must NOT expose an expiresAt parameter (contract forces 0)
    params = set(inspect.signature(VAPIPoEPRegistryClient.build_register_tx).parameters)
    assert "expiresAt" not in params and "expires_at" not in params


def test_validation_guards():
    c = VAPIPoEPRegistryClient(registry_address=REG)
    with pytest.raises(TypeError):
        c.build_register_tx(b"short", BLOB, COMMIT)            # device_id not 32 bytes
    with pytest.raises(TypeError):
        c.build_register_tx(DEV_B32, BLOB, b"short")           # commitment not 32 bytes
    with pytest.raises(ValueError):
        c.build_register_tx(DEV_B32, b"", COMMIT)              # empty blob
    with pytest.raises(ValueError):
        VAPIPoEPRegistryClient().build_register_tx(DEV_B32, BLOB, COMMIT)  # no registry address


def test_no_key_handling_surface():
    # auditable W1 property: the client exposes no signing / private-key surface.
    names = [n for n in dir(VAPIPoEPRegistryClient) if not n.startswith("__")]
    for forbidden in ("sign", "sign_tx", "send", "send_tx", "private_key", "set_private_key", "with_key"):
        assert forbidden not in names, f"SDK must have no key-handling method: {forbidden}"
    # build_register_tx takes no private-key parameter
    params = set(inspect.signature(VAPIPoEPRegistryClient.build_register_tx).parameters)
    for forbidden in ("private_key", "priv", "key", "signer"):
        assert forbidden not in params
