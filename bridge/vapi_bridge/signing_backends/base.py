"""SigningBackend Protocol + composite-signature dataclasses (Path A Arc 1 C1).

⚠ NAMING NOTE (Commit 3 cross-reference, 2026-05-26):
    A SECOND class also named ``SigningBackend`` lives in
    ``bridge/vapi_bridge/hardware_identity.py`` (an ABC, not a Protocol). The
    two abstractions cover DIFFERENT scopes and are intentionally separate
    per Arc 1 D-α operator decision:

      THIS ``SigningBackend`` (Protocol, signing_backends/base.py)
        → iPACT renewal challenge signing (low-volume, vhp_renewal_agent.py)
        → COMPOSITE signing (ECDSA-P256 + ML-DSA-44 via l9_presence.composite_sig)
        → returns CompositeSignature (wire blob + decomposed halves)
        → impls: HostKeyBackend, SecureElementBackend (Arc 2 stub)

      hardware_identity.SigningBackend (ABC)
        → PoAC RECORD signing hot path (~1000 Hz, dualshock_integration.py)
        → ECDSA-P256 over raw 228-byte body
        → returns 64-byte raw r||s
        → impls: SoftwareIdentityBackend, YubiKeyIdentityBackend,
                 ATECC608IdentityBackend (already integrated for the PoAC path)

    Arc 2's ATECC608A wrapper for THIS Protocol is the deferred
    SecureElementBackend; it may delegate to hardware_identity's ATECC608
    integration but lives in this package because the scope (composite-sig
    not raw-r||s) is different.

Wire-format honesty (V-7 finding 2026-05-26): the protocol's underlying
`l9_presence.composite_sig` produces:
  • ECDSA-P256 signatures in DER encoding (variable length, typically 70-72 B
    — NOT the 64-byte raw r||s the original brief assumed). DER stays here
    so the shim is byte-identical with the existing `composite_sig.sign()`
    output; a raw-r||s accessor can be added in a future commit if needed.
  • EC public keys in SEC1 UncompressedPoint encoding (0x04||X||Y = 65 B —
    NOT the 33-byte compressed form the original brief assumed).
  • ML-DSA-44 PQ signatures are fixed 2420 bytes (FIPS 204), PQ public keys
    are fixed 1312 bytes — both match the brief.

CompositeSignature also carries the original `encode_composite()` wire blob
so backward-compatible callers (the dormant-blind closure path) can fetch
the byte-identical signature without re-encoding.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class CompositePubkey:
    """A device's composite public key (EC + PQ halves).

    ec_p256_uncompressed: SEC1 0x04 || X(32) || Y(32) = 65 bytes.
    mldsa44_public:       FIPS 204 raw ML-DSA-44 public key = 1312 bytes.
    """
    ec_p256_uncompressed: bytes
    mldsa44_public: bytes


@dataclass(frozen=True)
class CompositeSignature:
    """An AND-composite signature with both halves + the encoded wire blob.

    blob:            the `encode_composite()` wire output — what callers consume
                     today. Preserved byte-identically for shim compatibility.
    ec_p256_sig_der: ECDSA-P256 signature in DER encoding (variable length,
                     typically 70-72 bytes). Derived from `decode_composite(blob)`.
    mldsa44_sig:     FIPS 204 raw ML-DSA-44 signature = 2420 bytes. Derived.
    label:           algorithm label from the wire framing (alg-id binding).
    """
    blob: bytes
    ec_p256_sig_der: bytes
    mldsa44_sig: bytes
    label: bytes


@runtime_checkable
class SigningBackend(Protocol):
    """The iPACT re-attestation signing seam.

    Scope (Path A Arc 1, D-α): VHP renewal signing only. The 1000 Hz PoAC
    record-signing hot path is NOT routed through this Protocol — see the
    package docstring for the rationale and the Arc 3+ deferral.

    Implementations MUST be deterministic for the same (digest, ctx) within
    a single keypair lifetime (composite_sig binds the message via M' so
    `sign` is functionally a pure function over inputs).
    """

    def sign(self, digest: bytes, ctx: bytes) -> CompositeSignature: ...

    def get_pubkey(self) -> CompositePubkey: ...

    def get_device_id(self) -> str: ...

    def signing_path(self) -> Literal["A", "B"]: ...

    def backend_type(self) -> str: ...
