"""Phase 3 (Path B) — shim wrapping signing_backends.HostKeyBackend.

This module previously held the persistent ML-DSA-44 composite-keypair load /
sign logic. That logic now lives in `signing_backends.host_key.HostKeyBackend`
per Path A Arc 1 Commit 1 (2026-05-26). The four public functions below are
preserved AS-IS so every caller — vhp_renewal_agent, provisioning scripts,
the dormant-blind closure path — continues to work byte-identically.

For new code, prefer the SigningBackend Protocol directly:
    from .signing_backends import HostKeyBackend
    backend = HostKeyBackend()
    sig = backend.sign(digest, ctx)

See `signing_backends/secure_element.py` for the Arc 2 (ATECC608A) path.

SECURITY MODEL (Path B, unchanged from prior implementation): the composite
PRIVATE key lives host-side (software key file, 0600). The re-attestation
proves "a live host-signer + live Edge sensor stream," NOT controller-
silicon-rooted presence (that is Path A v1 — silicon-rooted iPACT renewal
authenticity — via the SecureElementBackend in Arc 2).
"""
from __future__ import annotations

from .signing_backends.host_key import DEFAULT_COMPOSITE_KEY_PATH, HostKeyBackend

# Re-export for callers that import the constant from this module.
__all__ = [
    "DEFAULT_COMPOSITE_KEY_PATH",
    "load_or_generate",
    "get_composite_pubkey_blob",
    "make_reattest_signer",
    "update_registration_metadata",
]


def load_or_generate(key_path: str = DEFAULT_COMPOSITE_KEY_PATH):
    """[SHIM] Return the persistent composite CompositeKeyPair, generating on
    first use. Byte-identical to the pre-refactor behaviour."""
    return HostKeyBackend(key_path).keypair()


def get_composite_pubkey_blob(key_path: str = DEFAULT_COMPOSITE_KEY_PATH) -> bytes:
    """[SHIM] The ① encode_pubkey blob to register on VAPIPoEPRegistry."""
    return HostKeyBackend(key_path).encoded_pubkey_blob()


def make_reattest_signer(key_path: str = DEFAULT_COMPOSITE_KEY_PATH):
    """[SHIM] Return a Callable[[bytes], bytes] for VHPRenewalAgent._reattest_signer.
    Wire-compatible with the pre-refactor signer (returns the encoded composite-
    sig wire blob). The dormant-blind closure path consumes this."""
    return HostKeyBackend(key_path).make_reattest_signer()


def update_registration_metadata(key_path: str = DEFAULT_COMPOSITE_KEY_PATH, **meta) -> None:
    """[SHIM] Record registration metadata (registered_tx, registry_address,
    registered_device_id, registration_tier, registered_at_iso) into the key
    file without touching key material."""
    HostKeyBackend(key_path).update_registration_metadata(**meta)
