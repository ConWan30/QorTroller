"""Phase O0 Section 6.3 — AWS KMS client for VAPI Operator agent signing.

This module provides the bridge-side integration with the operator agents'
AWS KMS-managed signing keys, established via Pass 2C Section 12 amendment
(commit fc61d93d). Both vapi-anchor-sentry and vapi-guardian sign their
draft attestations and (at O2+) commit hashes through this client.

Design rationale (Section 6.3 implementation):

  F1b (boto3 + asyncio.to_thread, NOT aioboto3): low KMS call frequency
  (Phase O1 < 100 sigs/day per agent) makes thread overhead immaterial;
  zero existing AWS SDK code in bridge favors canonical boto3 over wrapper
  aioboto3; smaller transitive dependency surface; modern Python 3.12+
  asyncio.to_thread is the recommended sync-over-async pattern.

  D-Identifier (agent name external interface): callers use symbolic
  agent identifiers ("anchor-sentry" or "guardian") instead of KMS aliases.
  The kms_client module is the only place in the bridge that knows about
  KMS alias strings; capability skills reference agents symbolically.

  D-Input (32-byte digest enforcement): sign() takes message: bytes per
  operator brief but enforces 32-byte length at runtime. Honors the
  agents/skills/cryptographic-signing/SKILL.md boundary "no free-form
  message signing" while matching operator brief parameter naming.

  D-Config (direct os.getenv + load_dotenv at import): keeps kms_client.py
  self-contained and testable in isolation. Idempotent dotenv load
  preserves compatibility with bridge.config which also calls load_dotenv().

Interface contract (composes with cryptographic-signing skill at
agents/skills/cryptographic-signing/SKILL.md, commit 52978771):

  async def sign(agent: str, message: bytes) -> bytes
    Signs a 32-byte digest using the agent's KMS key. The message MUST
    be exactly 32 bytes (typically SHA-256 output of a VAPI FROZEN-v1
    primitive hash like AGENT_COMMIT v1 or PHYSICAL_DATA_ATTESTATION v1).
    Returns DER-encoded ECDSA signature.

  async def verify(agent: str, message: bytes, signature: bytes) -> bool
    Self-verification path. The IAM policy permits kms:Verify on the
    same keys, allowing the bridge to round-trip-verify its own
    signatures without external tooling.

  async def get_public_key(agent: str) -> bytes
    DER-encoded public key for DID document publication and external
    verification.

  async def describe_key(agent: str) -> dict
    Key metadata for diagnostic and verification work (KeySpec, KeyUsage,
    KeyState, etc.).

Configuration (env vars read at construction):

  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_REGION (validated to match Pass 2C Section 12 D1 = us-east-1; warning
              logged on drift but operation continues)
  VAPI_KMS_ANCHOR_SENTRY_ALIAS
  VAPI_KMS_GUARDIAN_ALIAS

  Missing any required var → KMSClientConfigError at construction.

Cross-references:

  Pass 2C Section 12 (commit fc61d93d) — architectural specifications
  agents/skills/cryptographic-signing/SKILL.md (commit 52978771) — capability spec
  agents/tools/kms-sign.md (commit 52978771) — tool spec
  bridge/.env.example (commit 17fe9e3c) — env var template
  bridge/vapi_bridge/mock_kms_client.py — cryptographically valid mock for testing
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from dotenv import load_dotenv

# D-Config: idempotent dotenv load at import time (load_dotenv default
# behavior is non-overriding, so this is safe even if config.py already
# loaded it).
load_dotenv()

log = logging.getLogger(__name__)

# Agent identifier → env var mapping for KMS alias resolution
_AGENT_ALIAS_ENV_VARS = {
    "anchor-sentry": "VAPI_KMS_ANCHOR_SENTRY_ALIAS",
    "guardian": "VAPI_KMS_GUARDIAN_ALIAS",
}

# Pass 2C Section 12 D1 spec
_EXPECTED_REGION = "us-east-1"

# Pass 2C Section 12 + IAM policy condition (kms:SigningAlgorithm pinned)
_SIGNING_ALGORITHM = "ECDSA_SHA_256"
_MESSAGE_TYPE_DIGEST = "DIGEST"
_DIGEST_LENGTH_BYTES = 32  # SHA-256 output length


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class KMSClientError(Exception):
    """Base exception for all KMSClient failures."""


class KMSClientConfigError(KMSClientError):
    """Raised at construction time when required env vars are missing or invalid."""


class KMSClientValidationError(KMSClientError):
    """Raised when input fails validation (e.g., non-32-byte digest, unknown agent)."""


class KMSClientAuthError(KMSClientError):
    """Raised when AWS IAM denies the operation (kms:Sign permission missing)."""


class KMSClientNotFoundError(KMSClientError):
    """Raised when the KMS key is not found, disabled, or in unusable state."""


class KMSClientSigningError(KMSClientError):
    """Raised for general signing failures (network, KMS service errors)."""


# ---------------------------------------------------------------------------
# KMSClient
# ---------------------------------------------------------------------------

class KMSClient:
    """Async wrapper around boto3 KMS client for VAPI Operator agent signing.

    Construction reads AWS credentials and KMS aliases from environment
    variables. Async methods wrap sync boto3 calls via asyncio.to_thread.
    """

    def __init__(self):
        # D-Config: direct os.getenv reads at construction
        self._aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self._aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self._aws_region = os.getenv("AWS_REGION")

        # Validate required env vars present
        missing = []
        if not self._aws_access_key_id:
            missing.append("AWS_ACCESS_KEY_ID")
        if not self._aws_secret_access_key:
            missing.append("AWS_SECRET_ACCESS_KEY")
        if not self._aws_region:
            missing.append("AWS_REGION")

        # Resolve agent → alias mapping
        self._agent_aliases: dict[str, str] = {}
        for agent, env_var in _AGENT_ALIAS_ENV_VARS.items():
            alias = os.getenv(env_var)
            if not alias:
                missing.append(env_var)
            else:
                self._agent_aliases[agent] = alias

        if missing:
            raise KMSClientConfigError(
                f"Missing required env vars: {', '.join(missing)}. "
                f"See bridge/.env.example for the full template."
            )

        # Pass 2C Section 12 D1 sanity check: us-east-1 expected
        if self._aws_region != _EXPECTED_REGION:
            log.warning(
                "AWS_REGION=%r differs from Pass 2C Section 12 spec %r. "
                "Proceeding but this is unverified architectural drift.",
                self._aws_region, _EXPECTED_REGION,
            )

        # Build boto3 KMS client (sync; wrapped by to_thread in async methods)
        self._client = boto3.client(
            "kms",
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
            region_name=self._aws_region,
        )

        log.info(
            "KMSClient constructed: region=%s, agents=%s",
            self._aws_region, list(self._agent_aliases.keys()),
        )

    def _resolve_alias(self, agent: str) -> str:
        """Map agent identifier to KMS alias. Raises KMSClientValidationError on unknown agent."""
        alias = self._agent_aliases.get(agent)
        if alias is None:
            raise KMSClientValidationError(
                f"Unknown agent identifier: {agent!r}. "
                f"Expected one of: {list(self._agent_aliases.keys())}."
            )
        return alias

    @staticmethod
    def _validate_digest(message: bytes) -> None:
        """Enforce 32-byte digest per agents/skills/cryptographic-signing/SKILL.md boundary."""
        if not isinstance(message, (bytes, bytearray)):
            raise KMSClientValidationError(
                f"message must be bytes, got {type(message).__name__}"
            )
        if len(message) != _DIGEST_LENGTH_BYTES:
            raise KMSClientValidationError(
                f"message must be exactly {_DIGEST_LENGTH_BYTES} bytes "
                f"(SHA-256 digest), got {len(message)} bytes. "
                f"Per agents/skills/cryptographic-signing/SKILL.md: "
                f"no free-form message signing."
            )

    @staticmethod
    def _digest_fingerprint(message: bytes) -> str:
        """Return short hash fingerprint for log lines (first 4 hex chars; not the digest itself)."""
        return message[:2].hex() if message else ""

    @staticmethod
    def _wrap_kms_error(operation: str, agent: str, exc: Exception) -> KMSClientError:
        """Map boto3 ClientError / BotoCoreError to KMSClient exception hierarchy."""
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code", "")
            msg = exc.response.get("Error", {}).get("Message", str(exc))
            if code in ("AccessDeniedException", "NotAuthorizedException", "UnrecognizedClientException"):
                return KMSClientAuthError(
                    f"{operation} denied for agent {agent!r}: {code} ({msg}). "
                    f"IAM policy review needed per Pass 2C Section 12.6 D3."
                )
            elif code in ("NotFoundException", "KeyUnavailableException", "DisabledException"):
                return KMSClientNotFoundError(
                    f"{operation} failed for agent {agent!r}: KMS key {code} ({msg}). "
                    f"Agent identity may need DID rotation per Pass 2C Section 10 Note 6."
                )
            else:
                return KMSClientSigningError(
                    f"{operation} failed for agent {agent!r}: {code} ({msg})"
                )
        elif isinstance(exc, BotoCoreError):
            return KMSClientSigningError(
                f"{operation} failed for agent {agent!r}: {type(exc).__name__}({exc})"
            )
        return KMSClientSigningError(f"{operation} failed: {exc}")

    async def sign(self, agent: str, message: bytes) -> bytes:
        """Sign a 32-byte digest using the agent's KMS key. Returns DER-encoded ECDSA signature."""
        self._validate_digest(message)
        alias = self._resolve_alias(agent)
        fingerprint = self._digest_fingerprint(message)
        log.info("sign: agent=%s alias=%s digest_fp=%s...", agent, alias, fingerprint)
        try:
            response = await asyncio.to_thread(
                self._client.sign,
                KeyId=alias,
                Message=message,
                MessageType=_MESSAGE_TYPE_DIGEST,
                SigningAlgorithm=_SIGNING_ALGORITHM,
            )
            signature = response["Signature"]
            log.info(
                "sign: success agent=%s digest_fp=%s sig_len=%d request_id=%s",
                agent, fingerprint, len(signature),
                response.get("ResponseMetadata", {}).get("RequestId", "?"),
            )
            return signature
        except Exception as exc:
            err = self._wrap_kms_error("sign", agent, exc)
            log.error("sign: failed agent=%s digest_fp=%s err=%s", agent, fingerprint, err)
            raise err from exc

    async def verify(self, agent: str, message: bytes, signature: bytes) -> bool:
        """Verify signature against agent's KMS key. Returns True if valid, False if not."""
        self._validate_digest(message)
        alias = self._resolve_alias(agent)
        fingerprint = self._digest_fingerprint(message)
        log.info("verify: agent=%s alias=%s digest_fp=%s...", agent, alias, fingerprint)
        try:
            response = await asyncio.to_thread(
                self._client.verify,
                KeyId=alias,
                Message=message,
                MessageType=_MESSAGE_TYPE_DIGEST,
                Signature=signature,
                SigningAlgorithm=_SIGNING_ALGORITHM,
            )
            valid = response.get("SignatureValid", False)
            log.info("verify: agent=%s digest_fp=%s valid=%s", agent, fingerprint, valid)
            return valid
        except ClientError as exc:
            # KMS verify with invalid signature can raise KMSInvalidSignatureException
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "KMSInvalidSignatureException":
                log.info(
                    "verify: agent=%s digest_fp=%s valid=False (KMSInvalidSignatureException)",
                    agent, fingerprint,
                )
                return False
            err = self._wrap_kms_error("verify", agent, exc)
            log.error("verify: failed agent=%s digest_fp=%s err=%s", agent, fingerprint, err)
            raise err from exc
        except Exception as exc:
            err = self._wrap_kms_error("verify", agent, exc)
            log.error("verify: failed agent=%s digest_fp=%s err=%s", agent, fingerprint, err)
            raise err from exc

    async def get_public_key(self, agent: str) -> bytes:
        """Return DER-encoded public key (SubjectPublicKeyInfo) for the agent's KMS key."""
        alias = self._resolve_alias(agent)
        log.info("get_public_key: agent=%s alias=%s", agent, alias)
        try:
            response = await asyncio.to_thread(self._client.get_public_key, KeyId=alias)
            public_key = response["PublicKey"]
            log.info("get_public_key: success agent=%s key_len=%d", agent, len(public_key))
            return public_key
        except Exception as exc:
            err = self._wrap_kms_error("get_public_key", agent, exc)
            log.error("get_public_key: failed agent=%s err=%s", agent, err)
            raise err from exc

    async def describe_key(self, agent: str) -> dict:
        """Return KMS key metadata (KeyId, KeySpec, KeyUsage, KeyState, etc.) for diagnostic work."""
        alias = self._resolve_alias(agent)
        log.info("describe_key: agent=%s alias=%s", agent, alias)
        try:
            response = await asyncio.to_thread(self._client.describe_key, KeyId=alias)
            metadata = response.get("KeyMetadata", {})
            log.info(
                "describe_key: success agent=%s key_id=%s key_spec=%s key_usage=%s key_state=%s",
                agent,
                metadata.get("KeyId", "?"),
                metadata.get("KeySpec", "?"),
                metadata.get("KeyUsage", "?"),
                metadata.get("KeyState", "?"),
            )
            return metadata
        except Exception as exc:
            err = self._wrap_kms_error("describe_key", agent, exc)
            log.error("describe_key: failed agent=%s err=%s", agent, err)
            raise err from exc
