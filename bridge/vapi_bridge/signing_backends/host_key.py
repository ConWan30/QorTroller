"""HostKeyBackend — Path B host-held composite-key SigningBackend (Arc 1 C1).

Wraps the storage / serialization / sign logic that previously lived in
`composite_device_identity.py`. That module is now a thin shim delegating
into this class — the dormant-blind closure path (vhp_renewal_agent →
make_reattest_signer) continues to work byte-identically.

Storage: same `~/.vapi/device_composite_mldsa44.json` as before, atomic
tmp->replace write, 0o600 best-effort permissions. registered_device_id +
other registration metadata persist in-file via update_registration_metadata.

Security model (unchanged from prior comment in composite_device_identity.py):
this is the SOFTWARE-host backend — the EC private key is on disk. Path A
silicon-rooted custody is the SecureElementBackend (Arc 2, ATECC608A).
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Literal, Optional

from .base import CompositePubkey, CompositeSignature

log = logging.getLogger(__name__)

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
    return {
        "alg": _TIER,
        "ec_private_der_hex": ec_priv_der.hex(),
        "ec_public_hex":      ec_pub.hex(),
        "pq_public_hex":      bytes(keypair.pq_public).hex(),
        "pq_private_hex":     bytes(keypair.pq_private).hex(),
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
        os.chmod(key_path, 0o600)
    except OSError:
        pass


class HostKeyBackend:
    """SigningBackend for the host-held composite keypair (Path B).

    Lazy-loads / generates on first sign() or get_pubkey() call. Multiple
    HostKeyBackend instances for the same key_path are safe — they each
    deserialize the same on-disk material.
    """

    def __init__(self, key_path: str = DEFAULT_COMPOSITE_KEY_PATH):
        self._key_path = key_path
        self._kp = None  # lazy-loaded l9_presence.composite_sig.CompositeKeyPair
        self._meta: Optional[dict] = None

    # ── SigningBackend protocol ────────────────────────────────────────────

    def sign(self, digest: bytes, ctx: bytes) -> CompositeSignature:
        from l9_presence import composite_sig as c
        self._ensure_loaded()
        blob = c.sign(self._kp, ctx, digest)
        label, ec_sig, pq_sig = c.decode_composite(blob)
        return CompositeSignature(
            blob=blob, ec_p256_sig_der=ec_sig, mldsa44_sig=pq_sig, label=label,
        )

    def get_pubkey(self) -> CompositePubkey:
        from cryptography.hazmat.primitives import serialization
        self._ensure_loaded()
        pub = self._kp.public()
        ec_bytes = pub.ec_public.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return CompositePubkey(
            ec_p256_uncompressed=ec_bytes,
            mldsa44_public=bytes(pub.pq_public),
        )

    def get_device_id(self) -> str:
        """Returns the registered_device_id metadata if persisted, else "".

        Empty-string return is the honest answer for a freshly-generated
        keypair that has not yet been registered against a device. Callers
        that need a device_id MUST set it via update_registration_metadata.
        """
        self._ensure_loaded()
        return (self._meta or {}).get("registered_device_id", "") or ""

    def signing_path(self) -> Literal["A", "B"]:
        return "B"

    def backend_type(self) -> str:
        return "host_json"

    # ── HostKeyBackend-specific helpers (shim seams) ──────────────────────

    def keypair(self):
        """Return the raw l9_presence CompositeKeyPair (back-compat for the
        composite_device_identity.load_or_generate shim)."""
        self._ensure_loaded()
        return self._kp

    def encoded_pubkey_blob(self) -> bytes:
        """Return the ① encode_pubkey blob to register on VAPIPoEPRegistry.

        Back-compat for the composite_device_identity.get_composite_pubkey_blob
        shim. The blob format is governed by l9_presence.composite_sig — not
        re-derived here so the registry-write path stays byte-identical."""
        from l9_presence import composite_sig as c
        self._ensure_loaded()
        return c.encode_pubkey(self._kp.public())

    def make_reattest_signer(self):
        """Return Callable[[bytes], bytes] for VHPRenewalAgent._reattest_signer.

        Preserves the legacy nonce->bytes contract (returns the encoded
        composite-sig wire blob) for byte-identical compatibility with the
        dormant-blind closure path. The CHALLENGE_TAG context is bound here
        so the signer's caller (vhp_renewal_agent) sees the same callable
        shape it had before the refactor.
        """
        from .. ipact_challenge import CHALLENGE_TAG
        self._ensure_loaded()

        def _signer(nonce: bytes) -> bytes:
            return self.sign(nonce, CHALLENGE_TAG).blob

        return _signer

    def update_registration_metadata(self, **meta) -> None:
        """Record registration metadata without touching key material.

        Reads-modifies-writes the on-disk JSON. Subsequent get_device_id /
        backend operations see the updated metadata after the next load.
        """
        p = Path(self._key_path)
        data = json.loads(p.read_text())
        data.update(meta)
        _atomic_write(p, data)
        # Invalidate cached metadata so the next get_device_id reflects the update.
        self._meta = None

    # ── internals ─────────────────────────────────────────────────────────

    def _ensure_loaded(self):
        if self._kp is not None and self._meta is not None:
            return
        from l9_presence import composite_sig as c
        p = Path(self._key_path)
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._kp = _deserialize(data)
                self._meta = data
                return
            except Exception as exc:
                log.warning("HostKeyBackend: load failed (%s) — regenerating", exc)
        # First use OR corrupt file → generate fresh keypair, persist with
        # created_at_iso. Subsequent loads will read this file.
        self._kp = c.generate_keypair(_alg())
        data = _serialize(self._kp)
        data["created_at_iso"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _atomic_write(p, data)
        self._meta = data
        log.info("HostKeyBackend: generated new ML-DSA-44 composite keypair at %s", self._key_path)
