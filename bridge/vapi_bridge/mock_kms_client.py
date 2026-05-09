"""Phase O0 Section 6.3 — MockKMSClient for testing without AWS credentials.

Mirrors the KMSClient interface but uses local secp256k1 keypairs generated
at construction time. Per F2b decision: cryptographically valid mock —
real ECDSA signatures using local keys, verifiable with standard ECDSA
verification math.

The mock enables:
  - CI testing without AWS credentials
  - Local development against the same interface
  - Test patterns matching VAPI's MockGSRGrip / MockBLETransport /
    IoSwarmNodeEmulator precedents

Design rationale (F2b decision):

  Real ECDSA signatures (NOT deterministic stubs) so tests exercise the
  same cryptographic math KMSClient relies on. Mock matches AWS KMS's
  curve choice (secp256k1 per Pass 2C Section 12) and signing algorithm
  (ECDSA over SHA-256 prehashed digests).

  Same exception hierarchy as KMSClient (imported from kms_client) so
  callers handle errors uniformly across mock and real implementations.

  Mock metadata in describe_key() matches real AWS KMS response shape
  with a `_mock` flag for tests to distinguish if needed.

Cross-references:

  bridge/vapi_bridge/kms_client.py — real KMSClient interface this mocks
  bridge/tests/test_kms_client.py — tests that exercise this mock
  agents/skills/cryptographic-signing/SKILL.md — capability spec
"""

from __future__ import annotations

import logging
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from .kms_client import (
    KMSClientValidationError,
    _DIGEST_LENGTH_BYTES,
)

log = logging.getLogger(__name__)


class MockKMSClient:
    """Cryptographically valid mock of KMSClient for testing without AWS.

    Generates one secp256k1 keypair per agent at construction. sign()
    produces real ECDSA signatures; verify() performs real ECDSA
    verification using the local public key.
    """

    # Default agent identifiers (mirrors KMSClient._AGENT_ALIAS_ENV_VARS keys)
    # Phase 238 Step I-FINAL: curator added as third Operator Initiative agent.
    _DEFAULT_AGENTS = ("anchor-sentry", "guardian", "curator")

    def __init__(self, agents: Optional[tuple[str, ...]] = None):
        """Construct mock with secp256k1 keypair per agent.

        Args:
            agents: tuple of agent identifiers. Defaults to ("anchor-sentry", "guardian").
        """
        agent_names = agents if agents is not None else self._DEFAULT_AGENTS

        self._private_keys: dict[str, ec.EllipticCurvePrivateKey] = {}
        self._public_keys: dict[str, ec.EllipticCurvePublicKey] = {}
        for agent in agent_names:
            priv = ec.generate_private_key(ec.SECP256K1(), default_backend())
            self._private_keys[agent] = priv
            self._public_keys[agent] = priv.public_key()

        log.info("MockKMSClient constructed: agents=%s", list(self._private_keys.keys()))

    def _resolve_agent(self, agent: str) -> ec.EllipticCurvePrivateKey:
        """Map agent identifier to local private key. Raises KMSClientValidationError on unknown agent."""
        if agent not in self._private_keys:
            raise KMSClientValidationError(
                f"Unknown agent identifier: {agent!r}. "
                f"Expected one of: {list(self._private_keys.keys())}."
            )
        return self._private_keys[agent]

    @staticmethod
    def _validate_digest(message: bytes) -> None:
        """Mirror KMSClient digest validation."""
        if not isinstance(message, (bytes, bytearray)):
            raise KMSClientValidationError(
                f"message must be bytes, got {type(message).__name__}"
            )
        if len(message) != _DIGEST_LENGTH_BYTES:
            raise KMSClientValidationError(
                f"message must be exactly {_DIGEST_LENGTH_BYTES} bytes "
                f"(SHA-256 digest), got {len(message)} bytes."
            )

    async def sign(self, agent: str, message: bytes) -> bytes:
        """Sign 32-byte digest using local secp256k1 key. Returns DER-encoded ECDSA signature."""
        self._validate_digest(message)
        priv = self._resolve_agent(agent)
        # Prehashed: tells the cryptography library that `message` is already
        # the SHA-256 digest (matches AWS KMS DIGEST MessageType behavior).
        signature = priv.sign(message, ec.ECDSA(Prehashed(hashes.SHA256())))
        log.info("MockKMS sign: agent=%s sig_len=%d", agent, len(signature))
        return signature

    async def verify(self, agent: str, message: bytes, signature: bytes) -> bool:
        """Verify signature against agent's local public key. Returns True if valid, False if not."""
        self._validate_digest(message)
        if agent not in self._public_keys:
            raise KMSClientValidationError(
                f"Unknown agent identifier: {agent!r}. "
                f"Expected one of: {list(self._public_keys.keys())}."
            )
        pub = self._public_keys[agent]
        try:
            pub.verify(signature, message, ec.ECDSA(Prehashed(hashes.SHA256())))
            log.info("MockKMS verify: agent=%s valid=True", agent)
            return True
        except InvalidSignature:
            log.info("MockKMS verify: agent=%s valid=False (InvalidSignature)", agent)
            return False

    async def get_public_key(self, agent: str) -> bytes:
        """Return DER-encoded public key (SubjectPublicKeyInfo) for the agent's local key."""
        if agent not in self._public_keys:
            raise KMSClientValidationError(
                f"Unknown agent identifier: {agent!r}. "
                f"Expected one of: {list(self._public_keys.keys())}."
            )
        pub = self._public_keys[agent]
        der_bytes = pub.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        log.info("MockKMS get_public_key: agent=%s key_len=%d", agent, len(der_bytes))
        return der_bytes

    async def describe_key(self, agent: str) -> dict:
        """Return mock metadata matching real AWS KMS describe_key response shape."""
        if agent not in self._public_keys:
            raise KMSClientValidationError(
                f"Unknown agent identifier: {agent!r}. "
                f"Expected one of: {list(self._public_keys.keys())}."
            )
        # Mock metadata shape matches real AWS KMS describe_key response for
        # ECC_SECG_P256K1 / SIGN_VERIFY keys per Pass 2C Section 12 spec.
        return {
            "KeyId": f"mock-key-{agent}",
            "KeyState": "Enabled",
            "KeySpec": "ECC_SECG_P256K1",
            "KeyUsage": "SIGN_VERIFY",
            "Origin": "MOCK",
            "SigningAlgorithms": ["ECDSA_SHA_256"],
            "_mock": True,  # Flag so tests/diagnostics can distinguish mock from real KMS
        }
