"""Phase B backlog #8 — TEST-ONLY composite signer fixture (EDIT 2, Option B).

Simulates the device-side composite signer for the iPACT re-attestation handshake,
exercising the REAL `l9_presence.composite_sig.sign` / `encode_pubkey` code path.

**This module is TEST-ONLY and is NEVER imported by any `bridge/vapi_bridge/` module**
(structural guard, scope §4 / §5f). It holds a composite test keypair — the very
thing that must not exist in production (a runtime-reachable key = credential-spoofing
vector). The production agent's signer/pubkey seams default to None (fail-closed); only
tests inject this fixture. The production device signer is VBDIP-0006 (firmware/SDK,
device-side, deferred) and never hands the bridge a private key.
"""

from __future__ import annotations

from l9_presence import composite_sig as _csig
from vapi_bridge.ipact_challenge import CHALLENGE_TAG


class IpactTestSigner:
    """A simulated device holding a composite keypair (TEST-ONLY).

    `sign(nonce)` returns a real ① composite-signature blob over the challenge nonce
    (`commitment = nonce`, ctx = CHALLENGE_TAG). `pubkey_blob()` returns the encoded
    composite public key the bridge verifier reconstructs via `decode_pubkey`.
    """

    def __init__(self, alg: _csig.CompositeAlg | None = None) -> None:
        self._alg = alg or _csig.ALG_MLDSA44_ECDSA_P256_SHA256
        self._kp = _csig.generate_keypair(self._alg)

    def sign(self, nonce: bytes) -> bytes:
        return _csig.sign(self._kp, CHALLENGE_TAG, nonce)

    def pubkey_blob(self) -> bytes:
        return _csig.encode_pubkey(self._kp.public())

    # convenience seams matching the agent's injection points
    def signer_callable(self):
        """Returns Callable[[bytes], bytes] — challenge nonce -> composite_sig blob."""
        return self.sign

    def pubkey_provider(self):
        """Returns Callable[[str], Optional[bytes]] — device_id -> pubkey_blob."""
        blob = self.pubkey_blob()
        return lambda _device_id: blob
