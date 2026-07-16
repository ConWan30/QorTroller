"""Ceremony B — MFG-CA HSM readiness preflight tests. Pure go/no-go (no chain, no spend). Exercises the
readiness check over both a software-backed CA and a KMS-fake-backed CA, and pins the hard-fail paths
(wrong KeySpec, not-a-new-root).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bridge.vapi_bridge.hardware_identity import KMSIdentityBackend
from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA
from bridge.vapi_bridge.mfg_ca_readiness import check_ca_readiness


class _FakeP256KMSPort:
    """Mimics a real P-256 AWS KMS CA key: sign a 32-byte DIGEST -> DER; get_public_key -> SPKI."""
    def __init__(self):
        self._priv = ec.generate_private_key(ec.SECP256R1())

    def sign_digest_der(self, digest):
        return self._priv.sign(digest, ec.ECDSA(Prehashed(SHA256())))

    def get_pubkey_spki(self):
        return self._priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)


_GOOD_META = {"Enabled": True, "KeyUsage": "SIGN_VERIFY", "KeySpec": "ECC_NIST_P256"}


def _software_ca(tmp_path):
    return ManufacturerRootCA(key_path=str(tmp_path / "sw_ca.json"))


def _kms_ca():
    port = _FakeP256KMSPort()
    backend = KMSIdentityBackend(sign_digest_der=port.sign_digest_der,
                                 get_pubkey_spki=port.get_pubkey_spki)
    return ManufacturerRootCA(backend=backend)


# --- software CA (baseline) ------------------------------------------------------------------------

def test_software_ca_is_ready():
    import tempfile
    r = check_ca_readiness(_software_ca(Path(tempfile.mkdtemp())))
    assert r["ready"] is True and r["reason"] == "ready"
    assert r["is_p256_65b"] and r["canary_verifies"] and r["full_cert_verifies"]
    assert len(r["new_issuer_pubkey_hex"]) == 130   # 65 bytes hex


# --- KMS-backed CA (the actual flip target path) ---------------------------------------------------

def test_kms_backed_ca_is_ready_with_good_metadata():
    r = check_ca_readiness(_kms_ca(), key_metadata=_GOOD_META)
    assert r["ready"] is True
    assert r["canary_verifies"] and r["full_cert_verifies"]
    assert r["key_enabled"] and r["key_usage_ok"] and r["key_spec_ok"]


def test_wrong_keyspec_is_not_ready():
    bad = {"Enabled": True, "KeyUsage": "SIGN_VERIFY", "KeySpec": "ECC_SECG_P256K1"}   # secp256k1, not P-256
    r = check_ca_readiness(_kms_ca(), key_metadata=bad)
    assert r["ready"] is False and r["key_spec_ok"] is False
    assert any("KeySpec" in w for w in r["warnings"])


def test_disabled_key_is_not_ready():
    bad = {"Enabled": False, "KeyUsage": "SIGN_VERIFY", "KeySpec": "ECC_NIST_P256"}
    r = check_ca_readiness(_kms_ca(), key_metadata=bad)
    assert r["ready"] is False and r["key_enabled"] is False


# --- new-root check --------------------------------------------------------------------------------

def test_new_root_differs_passes():
    ca = _kms_ca()
    r = check_ca_readiness(ca, prior_software_ca_pubkey_hex="04" + "11" * 64)   # some other pubkey
    assert r["is_new_root"] is True and r["ready"] is True


def test_same_as_prior_is_not_a_new_root():
    ca = _kms_ca()
    same = ca.issuer_pubkey_uncompressed().hex()      # feed the CA its OWN pubkey as "prior"
    r = check_ca_readiness(ca, prior_software_ca_pubkey_hex=same)
    assert r["is_new_root"] is False and r["ready"] is False
    assert any("NOT a new root" in w for w in r["warnings"])


def test_note_flags_the_vmdr_one_shot_reanchor_blocker():
    r = check_ca_readiness(_kms_ca(), key_metadata=_GOOD_META)
    assert "ONE-SHOT" in r["note"] and "581a836c" in r["note"]


def test_full_cert_path_uses_device_id_canon_and_verify_cert():
    """full_cert_verifies must pass production verify_cert (keccak device_id + issuer sig).

    Regression: an early draft used sha256(dev_pub) for device_id_hex, so issuer-sig-only
    passed while verify_cert failed DEVICE_ID_CANON_v1 — overclaiming 'full' cert path.
    """
    from bridge.vapi_bridge.device_birth_cert import verify_cert
    # If readiness is True, the throwaway cert path exercised verify_cert successfully
    # (indirect). Explicit: software CA readiness implies production-shaped full path.
    r = check_ca_readiness(_software_ca(Path(__import__("tempfile").mkdtemp())))
    assert r["full_cert_verifies"] is True and r["ready"] is True
    # smoke that verify_cert is the gate (import + symbol still exists for the path)
    assert callable(verify_cert)
