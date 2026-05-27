"""Path A Arc 1 Commit 1 — SigningBackend abstraction.

The SigningBackend Protocol formalizes the seam between iPACT re-attestation
signing (VHP renewal authenticity) and the underlying key custody. Three
implementations:

  HostKeyBackend       — current host-held JSON key (~/.vapi/...); signing_path "B"
  SecureElementBackend — Arc 2 stub for ATECC608A hardware; raises NotImplementedError
  (future)             — Path A v2 per-PoAC record signing seam (Arc 3+)

SCOPE (per Path A Arc 1 operator decision D-α 2026-05-26): this abstraction
covers iPACT renewal signing ONLY. The 1000 Hz PoAC record-signing hot path
in `dualshock_integration.py` is NOT routed through this Protocol in Arc 1.
"""
from .base import SigningBackend, CompositePubkey, CompositeSignature
from .host_key import HostKeyBackend
from .secure_element import SecureElementBackend

__all__ = [
    "SigningBackend",
    "CompositePubkey",
    "CompositeSignature",
    "HostKeyBackend",
    "SecureElementBackend",
]
