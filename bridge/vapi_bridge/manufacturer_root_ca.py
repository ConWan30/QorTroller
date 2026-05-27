"""ManufacturerRootCA — Path A Arc 1 Commit 3 manufacturer-signing identity.

Per Arc 1 D-3B operator decision (2026-05-26): the QorTroller Foundation
reference-implementation ManufacturerRootCA is a SEPARATE ECDSA-P256 keypair,
distinct from the bridge wallet (which is secp256k1 for IoTeX/Ethereum). The
two keys serve different roles:

  • Bridge wallet (secp256k1)     — pays gas, calls `registerDevice()` on-chain.
  • ManufacturerRootCA (P-256)    — signs DeviceBirthCertificate canonical bytes.
                                     issuer_pubkey_hex in the cert.

Persisted at ~/.vapi/qortroller_foundation_mfg_ca.json (mirrors the
~/.vapi/device_composite_mldsa44.json pattern; 0o600 perms on POSIX). Auto-
generated on first ceremony fire (via SoftwareIdentityBackend); future partner-
manufacturer deploys swap the backend for a real HSM (YubiKey / ATECC608A) by
construction — see hardware_identity.create_backend().

HONESTY: this is the QorTroller SELF-SIGNED REFERENCE IMPLEMENTATION root CA.
A production partner manufacturer's ceremony MUST replace this with a hardware-
HSM-rooted P-256 key. The cert format already accommodates that by carrying
`manufacturer_id` and `issuer_pubkey_hex` as cert fields — swapping the issuer
identity is a backend swap, not a format change.

  ┌──────────────────────────────────────────────────────────────────┐
  │ This class WRAPS hardware_identity.SoftwareIdentityBackend.      │
  │ It is NOT a SigningBackend itself (neither variant) — it serves  │
  │ a third scope: manufacturer cert issuance, distinct from PoAC    │
  │ record signing AND iPACT renewal signing. See V-6 cross-reference│
  │ in hardware_identity.py / signing_backends/base.py for the full  │
  │ three-scope picture.                                              │
  └──────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_ROOT_CA_KEY_PATH = str(Path.home() / ".vapi" / "qortroller_foundation_mfg_ca.json")

# Stable identifier embedded in the DeviceBirthCertificate.manufacturer_id field
# for the QorTroller Foundation reference-implementation root CA. Partner
# manufacturer deploys would use their own identifier (e.g. "SonyHardwareCA"
# or "BattleBeaverPartnerCA"). Anchored here so a single rename surfaces in CI.
QORTROLLER_FOUNDATION_MFG_ID = "QorTrollerFoundation"


class ManufacturerRootCA:
    """Manufacturer cert-issuing identity. Lazy-loads / generates on first use.

    Two operations:
      sign_cert_body(body: bytes) -> bytes       — ECDSA-P256 over SHA-256(body)
      issuer_pubkey_uncompressed() -> bytes      — SEC1 0x04||X||Y, 65 bytes

    All key custody delegates to hardware_identity.SoftwareIdentityBackend so
    the existing setup/load/generate semantics are preserved verbatim. A
    future partner-HSM deploy swaps in YubiKeyIdentityBackend or
    ATECC608IdentityBackend by changing one line in __init__.
    """

    def __init__(self, key_path: str = DEFAULT_ROOT_CA_KEY_PATH,
                 manufacturer_id: str = QORTROLLER_FOUNDATION_MFG_ID):
        from .hardware_identity import SoftwareIdentityBackend
        self._backend = SoftwareIdentityBackend(key_path)
        self._manufacturer_id = manufacturer_id
        self._ready = False

    def _ensure_setup(self) -> None:
        if not self._ready:
            self._backend.setup()
            self._ready = True

    def manufacturer_id(self) -> str:
        return self._manufacturer_id

    def issuer_pubkey_uncompressed(self) -> bytes:
        """SEC1 uncompressed (0x04 || X(32) || Y(32) = 65 bytes)."""
        self._ensure_setup()
        return self._backend.public_key_bytes

    def issuer_pubkey_hex(self) -> str:
        return self.issuer_pubkey_uncompressed().hex()

    def sign_cert_body(self, body: bytes) -> bytes:
        """ECDSA-P256 over SHA-256(body). Returns 64-byte raw r||s (matches
        the hardware_identity.SoftwareIdentityBackend wire contract)."""
        self._ensure_setup()
        # SoftwareIdentityBackend.sign(body) already does ec.ECDSA(SHA256())
        # internally and converts DER -> raw r||s. We pass body bytes directly.
        return self._backend.sign(body)

    def backend_type(self) -> str:
        """Useful for the cert's `issuer_backend` provenance field (e.g.
        'software' for reference impl, 'atecc608' / 'yubikey' for production)."""
        self._ensure_setup()
        return self._backend.backend_type


def verify_cert_signature(
    issuer_pubkey_uncompressed: bytes,
    cert_body: bytes,
    signature_raw_rs: bytes,
) -> bool:
    """Verify a 64-byte raw r||s ECDSA-P256 signature over SHA-256(cert_body)
    against an uncompressed SEC1 P-256 pubkey. Returns True / False.

    Stateless utility — used by verify_device_cert.py and the test suite. The
    cryptography library expects DER for verify(), so we re-encode raw r||s
    to DER first (the mirror of SoftwareIdentityBackend.sign's r/s split).
    """
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.exceptions import InvalidSignature

    if len(issuer_pubkey_uncompressed) != 65:
        return False
    if issuer_pubkey_uncompressed[0] != 0x04:
        return False
    if len(signature_raw_rs) != 64:
        return False

    try:
        pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), issuer_pubkey_uncompressed
        )
        r = int.from_bytes(signature_raw_rs[:32], "big")
        s = int.from_bytes(signature_raw_rs[32:], "big")
        der = encode_dss_signature(r, s)
        pub.verify(der, cert_body, ec.ECDSA(SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False
    except Exception as exc:  # noqa: BLE001 — verifier MUST NOT raise on bad input
        log.debug("verify_cert_signature: unexpected (returning False): %s", exc)
        return False
