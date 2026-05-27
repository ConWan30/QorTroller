"""SecureElementBackend — Path A silicon-rooted SigningBackend stub (Arc 2 gate).

This class is the import-surface anchor for Arc 2. It is intentionally a
runtime NotImplementedError — any caller that attempts to instantiate it
without the ATECC608A hardware path implemented will fail loudly and
immediately. NO PHANTOM PATH A PROOFS — there is no fallback to a host key,
no silent demotion, no "best effort" sign() path.

Arc 2 deliverable (separate session): replace the body of __init__ + sign +
get_pubkey with a real I2C / USB-I2C bridge to an ATECC608A secure element,
preserving the SigningBackend Protocol exactly so all upstream callers
(vhp_renewal_agent et al.) need no changes when a real Path A device comes
online.
"""
from __future__ import annotations
from typing import Literal

from .base import CompositePubkey, CompositeSignature


class SecureElementBackend:
    """Path A silicon-rooted SigningBackend — NOT YET IMPLEMENTED."""

    def __init__(self, *_, **__):
        raise NotImplementedError(
            "Arc 2: requires ATECC608A hardware connected via USB-I2C. "
            "See docs/path-a-manufacturing-spec.md (Arc 1 Commit 3) for the "
            "hardware provisioning ceremony. No phantom Path A proofs — this "
            "backend will only construct when real silicon is wired."
        )

    # The methods below are unreachable in Arc 1 (init always raises) but
    # are declared so static type checkers see SecureElementBackend as a
    # complete SigningBackend implementation.

    def sign(self, digest: bytes, ctx: bytes) -> CompositeSignature:  # pragma: no cover
        raise NotImplementedError

    def get_pubkey(self) -> CompositePubkey:  # pragma: no cover
        raise NotImplementedError

    def get_device_id(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def signing_path(self) -> Literal["A", "B"]:  # pragma: no cover
        return "A"

    def backend_type(self) -> str:  # pragma: no cover
        return "atecc608a"
