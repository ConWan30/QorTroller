"""Arc 7 Decoupled Cryptographic Sidecar Pointer — Data Availability (DA) Layer.

Simulates uploading the full 3,309-byte ML-DSA-65 signature payload to an off-chain
DePIN storage node, keyed by its 32-byte commitment hash.
"""

from __future__ import annotations

import logging
from typing import Dict

log = logging.getLogger(__name__)


class MockDAScheme:
    """Mock off-chain DePIN storage router for Arc 7 composite signatures.

    Adheres strictly to the Decoupled Cryptographic Sidecar Pointer pattern
    by storing the 3,309-byte signature off-chain and exposing the 32-byte
    pointer hash.
    """

    def __init__(self) -> None:
        self._storage: Dict[bytes, bytes] = {}

    def upload_signature(self, commitment: bytes, signature: bytes) -> bool:
        """Upload the 3,309-byte signature payload keyed by its 32-byte commitment."""
        if len(commitment) != 32:
            raise ValueError(f"Invalid commitment hash size: {len(commitment)} (expected 32)")
        if len(signature) != 3309:
            log.warning("DA Upload warning: signature size %d != 3309 bytes", len(signature))
        
        self._storage[commitment] = signature
        log.info(
            "DA Upload SUCCESS: stored %d bytes signature at commitment 0x%s",
            len(signature),
            commitment.hex(),
        )
        return True

    def download_signature(self, commitment: bytes) -> bytes | None:
        """Download the 3,309-byte signature from the off-chain DePIN storage node."""
        return self._storage.get(commitment)

    def clear(self) -> None:
        """Clear all stored signatures."""
        self._storage.clear()


# Global mock DA storage router
da_router = MockDAScheme()
