"""Phase B backlog #8 — iPACT renewal handshake: challenge issuance.

Bridge-issued challenge nonces for the re-attestation handshake (③'s
`_obtain_reattest_proof`). The device composite-signs the nonce (①) under the
dedicated challenge domain tag; the bridge verifies + computes the reattest_proof.

STANDALONE stdlib-only (no PQ libs, no bridge-heavy imports) — safe to import at
bridge startup regardless of enforcement state. The PQ verify path (composite_sig)
is lazy-imported in the agent, only when enforcement is ON (W-3).

Challenge domain tag (W-5): dedicated `b"QORTROLLER-IPACT-CHALLENGE-v1"`, distinct
from the commitment-family tag `b"QORTROLLER-IPACT-RENEWAL-v1"` — the family tag
identifies the commitment family, the challenge tag identifies the protocol step.
Distinct domain separation prevents cross-protocol signature-reuse attacks. RESERVED
capability tag (NOT a PATTERN-017 family); not pinned in PV-CI this step.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

#: Dedicated challenge-step domain tag (W-5). Width-asserted at import per ①'s pattern.
CHALLENGE_TAG = b"QORTROLLER-IPACT-CHALLENGE-v1"
assert len(CHALLENGE_TAG) == 29, "challenge tag must be 29 bytes (v1)"

#: Challenge nonce length (matches ③ §2: 32-byte CSPRNG, prefix byte 0x20).
NONCE_LEN = 32

#: Default challenge time-to-live (seconds).
DEFAULT_TTL_S = 300


@dataclass
class Challenge:
    challenge_id: str
    device_id: str
    nonce: bytes
    expires_at: float


class ChallengeStore:
    """In-memory single-use + TTL challenge store.

    `issue(device_id)` mints a fresh 32-byte CSPRNG nonce bound to the device with a
    TTL. `consume(challenge_id)` validates fresh/unexpired/single-use and removes it
    (anti-replay) — returns True exactly once per issued challenge, False thereafter
    or if expired/unknown.
    """

    def __init__(self, ttl_s: int = DEFAULT_TTL_S) -> None:
        self._ttl_s = int(ttl_s)
        self._open: dict[str, Challenge] = {}

    def issue(self, device_id: str, *, now: float | None = None) -> Challenge:
        t = time.time() if now is None else now
        ch = Challenge(
            challenge_id=secrets.token_hex(16),
            device_id=device_id,
            nonce=secrets.token_bytes(NONCE_LEN),
            expires_at=t + self._ttl_s,
        )
        self._open[ch.challenge_id] = ch
        return ch

    def get(self, challenge_id: str) -> Challenge | None:
        return self._open.get(challenge_id)

    def consume(self, challenge_id: str, *, now: float | None = None) -> bool:
        t = time.time() if now is None else now
        ch = self._open.pop(challenge_id, None)  # single-use: remove on consume
        if ch is None:
            return False
        if t > ch.expires_at:
            return False  # expired
        return True

    def purge_expired(self, *, now: float | None = None) -> int:
        t = time.time() if now is None else now
        stale = [cid for cid, ch in self._open.items() if t > ch.expires_at]
        for cid in stale:
            self._open.pop(cid, None)
        return len(stale)


#: Process-shared store the HTTP challenge endpoint issues into (the agent path in
#: tests uses its own injected store — see W-1/W-2 seam isolation).
SHARED_CHALLENGE_STORE = ChallengeStore()
