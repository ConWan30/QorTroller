"""Phase 3 (Path B) — persistent host-held composite device keypair.

The device's ① composite keypair (ECDSA-P256 + ML-DSA-44, the user tier) for the
③ re-attestation handshake. Mirrors hardware_identity.SoftwareIdentityBackend's
proven pattern (JSON key file in ~/.vapi, atomic tmp->replace, load-or-generate on
first use, registration-metadata preservation), extended to carry the PQ halves —
composite_sig has encode_pubkey but no PRIVATE-key serializer, so this module adds
serialize/deserialize.

SECURITY MODEL (Path B): the composite PRIVATE key lives host-side (software key
file, 0600). The re-attestation therefore proves "a live host-signer + live Edge
sensor stream," NOT controller-silicon-rooted presence (that is Path A). A future
hardening can move the EC half into a YubiKey/ATECC via the SigningBackend
abstraction without rearchitecting. INSECURE for production custody of a
high-value key; appropriate for testnet dormant-blind closure.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Default key file, parallel to the existing ~/.vapi/dualshock_device_key.json (PoAC).
DEFAULT_COMPOSITE_KEY_PATH = str(Path.home() / ".vapi" / "device_composite_mldsa44.json")
_TIER = "mldsa44"  # ML-DSA-44 + ECDSA-P256 (user tier; operator decision 2026-05-24)


def _alg():
    from l9_presence import composite_sig as c
    return c.ALG_MLDSA44_ECDSA_P256_SHA256


def _serialize(keypair) -> dict:
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, PublicFormat, NoEncryption,
    )
    ec_priv_der = keypair.ec_private.private_bytes(
        Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
    )
    ec_pub = keypair.ec_private.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    # ML-DSA pq halves are raw bytes (PQClean/quantcrypt). bytes() is a no-op guard.
    return {
        "alg": _TIER,
        "ec_private_der_hex": ec_priv_der.hex(),
        "ec_public_hex": ec_pub.hex(),
        "pq_public_hex": bytes(keypair.pq_public).hex(),
        "pq_private_hex": bytes(keypair.pq_private).hex(),
    }


def _deserialize(data: dict):
    from cryptography.hazmat.primitives.serialization import load_der_private_key
    from l9_presence import composite_sig as c
    ec_priv = load_der_private_key(bytes.fromhex(data["ec_private_der_hex"]), password=None)
    return c.CompositeKeyPair(
        alg=_alg(),
        ec_private=ec_priv,
        pq_public=bytes.fromhex(data["pq_public_hex"]),
        pq_private=bytes.fromhex(data["pq_private_hex"]),
    )


def _atomic_write(key_path: Path, data: dict) -> None:
    key_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = key_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(key_path)
    try:
        os.chmod(key_path, 0o600)  # host key file — restrict perms (best-effort on Windows)
    except OSError:
        pass


def load_or_generate(key_path: str = DEFAULT_COMPOSITE_KEY_PATH):
    """Return the persistent composite CompositeKeyPair, generating + persisting on
    first use. Stable across restarts (it is the device's composite identity).
    Preserves any registration metadata already in the file."""
    from l9_presence import composite_sig as c
    p = Path(key_path)
    if p.exists():
        try:
            return _deserialize(json.loads(p.read_text()))
        except Exception as exc:  # corrupt/incompatible → regenerate (logged)
            log.warning("composite_device_identity: load failed (%s) — regenerating", exc)
    kp = c.generate_keypair(_alg())
    data = _serialize(kp)
    data["created_at_iso"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _atomic_write(p, data)
    log.info("composite_device_identity: generated new ML-DSA-44 composite keypair at %s", key_path)
    return kp


def get_composite_pubkey_blob(key_path: str = DEFAULT_COMPOSITE_KEY_PATH) -> bytes:
    """The ① encode_pubkey blob to register on VAPIPoEPRegistry."""
    from l9_presence import composite_sig as c
    return c.encode_pubkey(load_or_generate(key_path).public())


def make_reattest_signer(key_path: str = DEFAULT_COMPOSITE_KEY_PATH):
    """Return a Callable[[bytes], bytes] for VHPRenewalAgent._reattest_signer:
    nonce -> composite_sig over (ctx=CHALLENGE_TAG, commitment=nonce). Lazy-loads
    the keypair once. The seam carries a callable, never a key (matches #8 W-2)."""
    from l9_presence import composite_sig as c
    from .ipact_challenge import CHALLENGE_TAG
    kp = load_or_generate(key_path)

    def _signer(nonce: bytes) -> bytes:
        return c.sign(kp, CHALLENGE_TAG, nonce)

    return _signer


def update_registration_metadata(key_path: str = DEFAULT_COMPOSITE_KEY_PATH, **meta) -> None:
    """Record registration metadata (registered_tx, registry_address, registered_device_id,
    registration_tier, registered_at_iso) into the key file without touching key material."""
    p = Path(key_path)
    data = json.loads(p.read_text())
    data.update(meta)
    _atomic_write(p, data)
