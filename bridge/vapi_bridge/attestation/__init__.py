"""Protocol-Enforced Multi-Modal Attestation Loop.

Reads from all existing QorTroller channels at configurable intervals,
bundles their outputs into a single cryptographic attestation envelope,
and records it in the session database.

This is a read-only integration layer — it never modifies existing
components or protocol paths. See:
    docs/design/attestation-loop-2026-07-29.md
"""

from .types import ChannelSnapshot, AttestationEnvelope
from .ticker import AttestationTicker

__all__ = ["ChannelSnapshot", "AttestationEnvelope", "AttestationTicker"]