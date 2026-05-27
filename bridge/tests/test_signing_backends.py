"""Path A Arc 1 Commit 1 — SigningBackend Protocol + HostKeyBackend + stub.

   T-SB-1  HostKeyBackend satisfies the SigningBackend Protocol structurally
           (runtime_checkable isinstance + every required attribute callable).
   T-SB-2  HostKeyBackend.sign(digest, ctx).blob produces a wire blob that
           verifies under composite_sig.verify with the same pubkey/ctx/digest
           — pre/post-refactor SEMANTIC equivalence guard. (composite_sig.sign
           is non-deterministic in the ECDSA half so byte-identity across two
           calls is NOT a valid test; verification round-trip is.)
   T-SB-3  HostKeyBackend.signing_path() returns the literal "B".
   T-SB-4  HostKeyBackend.backend_type() returns the literal "host_json".
   T-SB-5  SecureElementBackend() raises NotImplementedError with the Arc 2
           hardware message (no phantom Path A proofs).
   T-SB-6  composite_device_identity.make_reattest_signer() shim returns a
           callable whose output verifies under composite_sig.verify — locks
           the dormant-blind closure path against shim regression.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from bridge.vapi_bridge.signing_backends import (
    HostKeyBackend,
    SecureElementBackend,
    SigningBackend,
    CompositeSignature,
    CompositePubkey,
)
from bridge.vapi_bridge import composite_device_identity as cdi


@pytest.fixture
def tmp_key_path():
    """Isolated key file per test — never touches the real ~/.vapi/..."""
    d = tempfile.mkdtemp(prefix="vapi_signing_backend_")
    p = Path(d) / "device_composite_mldsa44.json"
    yield str(p)
    # Best-effort cleanup; Windows file-lock failures are non-fatal in tests.
    try:
        if p.exists():
            p.unlink()
        Path(d).rmdir()
    except OSError:
        pass


# ── T-SB-1 ────────────────────────────────────────────────────────────────────

def test_T_SB_1_hostkeybackend_satisfies_protocol(tmp_key_path):
    backend = HostKeyBackend(tmp_key_path)
    # Structural check via runtime_checkable Protocol.
    assert isinstance(backend, SigningBackend), \
        "HostKeyBackend must satisfy SigningBackend Protocol structurally"
    # Every required attribute is present + callable.
    for attr in ("sign", "get_pubkey", "get_device_id", "signing_path", "backend_type"):
        assert hasattr(backend, attr), f"missing SigningBackend method: {attr}"
        assert callable(getattr(backend, attr)), f"{attr} is not callable"


# ── T-SB-2 ────────────────────────────────────────────────────────────────────

def test_T_SB_2_sign_output_verifies_under_composite_sig(tmp_key_path):
    """Semantic regression: sign() blob MUST verify against the keypair's
    public key under the unchanged l9_presence.composite_sig.verify path.
    composite_sig.sign uses non-deterministic ECDSA, so two consecutive
    sign() calls produce different blobs — byte-identity is NOT the gate."""
    from l9_presence import composite_sig as c
    from bridge.vapi_bridge.ipact_challenge import CHALLENGE_TAG

    backend = HostKeyBackend(tmp_key_path)
    digest = b"test-nonce-32-bytes-for-this-cas"  # 32 B
    assert len(digest) == 32

    sig = backend.sign(digest, CHALLENGE_TAG)
    assert isinstance(sig, CompositeSignature)
    assert isinstance(sig.blob, bytes) and len(sig.blob) > 0
    assert isinstance(sig.ec_p256_sig_der, bytes) and len(sig.ec_p256_sig_der) > 0
    assert isinstance(sig.mldsa44_sig, bytes) and len(sig.mldsa44_sig) == 2420  # FIPS 204

    # AND-verify the wire blob round-trips under the unchanged verify path.
    kp = backend.keypair()
    assert c.verify(kp.public(), CHALLENGE_TAG, digest, sig.blob) is True


# ── T-SB-3 ────────────────────────────────────────────────────────────────────

def test_T_SB_3_signing_path_is_B(tmp_key_path):
    assert HostKeyBackend(tmp_key_path).signing_path() == "B"


# ── T-SB-4 ────────────────────────────────────────────────────────────────────

def test_T_SB_4_backend_type_is_host_json(tmp_key_path):
    assert HostKeyBackend(tmp_key_path).backend_type() == "host_json"


# ── T-SB-5 ────────────────────────────────────────────────────────────────────

def test_T_SB_5_secure_element_raises_not_implemented():
    """No phantom Path A proofs: SecureElementBackend MUST refuse to construct
    until Arc 2 ships real hardware integration."""
    with pytest.raises(NotImplementedError) as excinfo:
        SecureElementBackend()
    msg = str(excinfo.value)
    assert "Arc 2" in msg
    assert "ATECC608A" in msg
    assert "phantom" in msg.lower()


# ── T-SB-6 ────────────────────────────────────────────────────────────────────

def test_T_SB_6_shim_make_reattest_signer_still_verifies(tmp_key_path):
    """Dormant-blind closure regression guard: the shim's make_reattest_signer
    returns a callable that produces a wire blob verifying under composite_sig
    with the CHALLENGE_TAG ctx — byte-identical surface to the pre-refactor
    implementation. If this breaks, the Phase 3 Path B enforcement path breaks."""
    from l9_presence import composite_sig as c
    from bridge.vapi_bridge.ipact_challenge import CHALLENGE_TAG

    signer = cdi.make_reattest_signer(tmp_key_path)
    assert callable(signer)
    nonce = b"x" * 32
    blob = signer(nonce)
    assert isinstance(blob, bytes) and len(blob) > 0

    # The shim path's keypair is the one persisted at tmp_key_path; load it
    # via the shim too so we exercise the full back-compat surface.
    kp = cdi.load_or_generate(tmp_key_path)
    assert c.verify(kp.public(), CHALLENGE_TAG, nonce, blob) is True
