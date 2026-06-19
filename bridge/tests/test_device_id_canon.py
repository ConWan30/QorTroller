"""Phase 0 commit 2 — DEVICE_ID_CANON_v1 golden-vector cross-layer proof.

Locks the adjudicated formula empirically:
  device_id = keccak256(65-byte SEC1 uncompressed P-256 pubkey, 0x04 prefix included)

Proof structure (F-CANON-1 / F-CANON-2 honesty):
  - Ethereum keccak256 is verified by TWO independent implementations agreeing on
    the fixture digest: codec.py (eth_hash.auto.keccak) and PyCryptodome
    Crypto.Hash.keccak — not a single-library self-check.
  - NIST SHA3-256 (hashlib.sha3_256) is asserted to DIVERGE — proving the fixture
    is not an artifact of the wrong padding variant.
  - EVM execution equivalence is verified in contracts/test/DeviceIdCanon.test.js
    (compiled DeviceRegistry.computeDeviceId against the fixture pubkey).
  - test_device_registry_source_pins_keccak256_pubkey is a supplementary source
    read only; Solidity's keccak256 builtin is Ethereum-keccak by language spec.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from vapi_bridge.codec import compute_device_id  # noqa: E402

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "device_id_canon_demo.json"
DEVICE_REGISTRY_SOL = REPO_ROOT / "contracts" / "contracts" / "DeviceRegistry.sol"


def _ethereum_keccak_pycryptodome(data: bytes) -> bytes:
    """Independent of eth_hash — uses PyCryptodome's raw Keccak-256 (Ethereum padding)."""
    from Crypto.Hash import keccak

    digest = keccak.new(digest_bits=256)
    digest.update(data)
    return digest.digest()


@pytest.fixture
def canon_vector() -> dict:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert data["schema"] == "vapi-device-id-canon-demo-v1"
    return data


def test_fixture_pubkey_is_65_byte_sec1(canon_vector: dict) -> None:
    pubkey = bytes.fromhex(canon_vector["pubkey_hex"])
    assert len(pubkey) == canon_vector["preimage_bytes"] == 65
    assert pubkey[0] == 0x04


def test_two_independent_ethereum_keccak_implementations_agree(canon_vector: dict) -> None:
    """F-CANON-1: eth_hash (codec path) and PyCryptodome must both yield 581a836c."""
    pubkey = bytes.fromhex(canon_vector["pubkey_hex"])
    expected = bytes.fromhex(canon_vector["device_id_hex"])

    via_codec = compute_device_id(pubkey)
    via_pycryptodome = _ethereum_keccak_pycryptodome(pubkey)

    assert via_codec == expected
    assert via_pycryptodome == expected
    assert via_codec == via_pycryptodome


def test_nist_sha3_256_diverges_from_ethereum_keccak(canon_vector: dict) -> None:
    """F-CANON-1 negative control: NIST SHA3-256 != Ethereum keccak256 (different padding)."""
    pubkey = bytes.fromhex(canon_vector["pubkey_hex"])
    expected = bytes.fromhex(canon_vector["device_id_hex"])
    nist_sha3 = hashlib.sha3_256(pubkey).digest()

    assert nist_sha3 != expected
    assert nist_sha3 != compute_device_id(pubkey)
    assert nist_sha3 != _ethereum_keccak_pycryptodome(pubkey)


def test_codec_matches_fixture(canon_vector: dict) -> None:
    pubkey = bytes.fromhex(canon_vector["pubkey_hex"])
    expected = bytes.fromhex(canon_vector["device_id_hex"])
    assert compute_device_id(pubkey) == expected


def test_device_registry_source_pins_keccak256_pubkey() -> None:
    """F-CANON-2 supplementary: source text uses Solidity keccak256 (Ethereum-keccak by spec).

    EVM execution against compiled bytecode is in contracts/test/DeviceIdCanon.test.js.
    This test does NOT substitute for that execution check.
    """
    text = DEVICE_REGISTRY_SOL.read_text(encoding="utf-8")
    assert "function computeDeviceId(bytes calldata _pubkey)" in text
    assert "return keccak256(_pubkey)" in text


def test_64byte_stripped_preimage_diverges(canon_vector: dict) -> None:
    """Canon excludes Ethereum address-style 64-byte encoding (F-KEY-2 negative control)."""
    pubkey = bytes.fromhex(canon_vector["pubkey_hex"])
    stripped_id = compute_device_id(pubkey[1:])
    expected_stripped = bytes.fromhex(canon_vector["negative_control_stripped_device_id_hex"])
    canonical_id = bytes.fromhex(canon_vector["device_id_hex"])
    assert stripped_id == expected_stripped
    assert stripped_id != canonical_id


def test_persistent_identity_keccak_matches_fixture(canon_vector: dict) -> None:
    """Production path uses eth_hash (same as codec); sha3_256 fallback is not canon-conformant."""
    sys.path.insert(0, str(REPO_ROOT / "controller"))
    from persistent_identity import _keccak256  # type: ignore  # noqa: E402

    pubkey = bytes.fromhex(canon_vector["pubkey_hex"])
    expected = bytes.fromhex(canon_vector["device_id_hex"])
    assert _keccak256(pubkey) == expected
    assert _keccak256(pubkey) == _ethereum_keccak_pycryptodome(pubkey)


def test_path_b_581a836c_still_valid_no_migration(canon_vector: dict) -> None:
    """Existing MFG-registered Path B device_id unchanged under canon enforcement."""
    from vapi_bridge.device_birth_cert import (
        compress_sec1_p256_pubkey,
        verify_device_id_matches_pubkey,
    )

    uncompressed = bytes.fromhex(canon_vector["pubkey_hex"])
    compressed_hex = compress_sec1_p256_pubkey(uncompressed).hex()
    ok, reason = verify_device_id_matches_pubkey(
        canon_vector["device_id_hex"], compressed_hex,
    )
    assert ok, reason
    assert canon_vector["device_id_hex"] == "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
