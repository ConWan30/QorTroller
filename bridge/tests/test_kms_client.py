"""Phase O0 Section 6.3 — KMSClient + MockKMSClient tests.

Six tests covering:
  Test 1: KMSClient construction succeeds with all required env vars
  Test 2: KMSClient construction raises KMSClientConfigError when env vars missing
  Test 3: MockKMSClient sign-then-verify cryptographic round-trip
  Test 4: MockKMSClient verify catches tampered messages
  Test 5: Separate keys for separate agents (no cross-verification)
  Test 6: Agent identifier mapping + unknown-agent / invalid-digest validation

All six tests use MockKMSClient for the cryptographic operations (no AWS
credentials required for CI). Test 1 / Test 2 construct real KMSClient
to validate the env-var consumption path; both pass without invoking
AWS APIs (boto3 client creation is lazy — no network calls).

Optional integration test (skipped by default; runs manually with
AWS_INTEGRATION_TEST=1):
  test_real_kms_client_sign_then_verify_against_aws

Cross-references:
  bridge/vapi_bridge/kms_client.py — real KMSClient
  bridge/vapi_bridge/mock_kms_client.py — cryptographically valid mock
  agents/skills/cryptographic-signing/SKILL.md — capability spec
  Pass 2C Section 12 (commit fc61d93d) — architectural target
"""

from __future__ import annotations

import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.kms_client import (
    KMSClient,
    KMSClientConfigError,
    KMSClientValidationError,
)
from vapi_bridge.mock_kms_client import MockKMSClient


# ---------------------------------------------------------------------------
# Test 1: Construction succeeds with all env vars
# ---------------------------------------------------------------------------

def test_kms_client_construction_succeeds_with_env_vars(monkeypatch):
    """KMSClient construction succeeds when all required env vars are present.

    boto3 client creation is lazy — no AWS API call until a method is invoked.
    So this test passes without AWS credentials being valid.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTTESTTESTTEST")  # 20-char AKIA-prefix
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key-padded-to-40-chars-xxx")  # 40 chars
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("VAPI_KMS_ANCHOR_SENTRY_ALIAS", "alias/vapi-anchor-sentry-signing")
    monkeypatch.setenv("VAPI_KMS_GUARDIAN_ALIAS", "alias/vapi-guardian-signing")

    client = KMSClient()
    assert client is not None
    assert client._agent_aliases["anchor-sentry"] == "alias/vapi-anchor-sentry-signing"
    assert client._agent_aliases["guardian"] == "alias/vapi-guardian-signing"
    assert client._aws_region == "us-east-1"


# ---------------------------------------------------------------------------
# Test 2: Construction fails without env vars
# ---------------------------------------------------------------------------

def test_kms_client_construction_fails_without_env_vars(monkeypatch):
    """KMSClient construction raises KMSClientConfigError when required env vars missing."""
    # Clear all required vars (raising=False so delenv doesn't error if absent)
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "VAPI_KMS_ANCHOR_SENTRY_ALIAS",
        "VAPI_KMS_GUARDIAN_ALIAS",
    ):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(KMSClientConfigError) as exc_info:
        KMSClient()
    assert "Missing required env vars" in str(exc_info.value)
    # Confirm the error message lists at least one specific missing var
    assert "AWS_ACCESS_KEY_ID" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 3: Sign-then-verify cryptographic round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_kms_client_sign_then_verify_roundtrip():
    """MockKMSClient produces signatures that verify against the same key.

    Validates the cryptographic correctness of the sign-then-verify path
    end-to-end through the mock's real ECDSA secp256k1 implementation.
    """
    client = MockKMSClient()
    digest = hashlib.sha256(b"VAPI sign-verify roundtrip test").digest()
    assert len(digest) == 32

    signature = await client.sign("anchor-sentry", digest)
    assert isinstance(signature, bytes)
    assert len(signature) > 0
    # ECDSA secp256k1 DER signatures are typically 70-72 bytes
    assert 60 < len(signature) < 80, f"signature length {len(signature)} outside expected ECDSA-DER range"

    valid = await client.verify("anchor-sentry", digest, signature)
    assert valid is True


# ---------------------------------------------------------------------------
# Test 4: Verify catches tampered messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_kms_client_verify_fails_for_modified_message():
    """MockKMSClient verify returns False when message is tampered after signing.

    Validates that signature integrity catches digest tampering.
    """
    client = MockKMSClient()
    original = hashlib.sha256(b"original message").digest()
    modified = hashlib.sha256(b"modified message").digest()
    assert original != modified

    signature = await client.sign("anchor-sentry", original)
    valid = await client.verify("anchor-sentry", modified, signature)
    assert valid is False


# ---------------------------------------------------------------------------
# Test 5: Separate keys for separate agents (cross-verification fails)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_kms_client_separate_keys_for_separate_agents():
    """anchor-sentry and guardian have distinct keys; cross-verification fails.

    Validates per-agent key isolation. A signature produced by Sentry's key
    must NOT verify with Guardian's key, and vice versa.
    """
    client = MockKMSClient()
    digest = hashlib.sha256(b"shared message both agents would sign").digest()

    sig_sentry = await client.sign("anchor-sentry", digest)
    sig_guardian = await client.sign("guardian", digest)

    # Each signature verifies with its own agent's key
    assert (await client.verify("anchor-sentry", digest, sig_sentry)) is True
    assert (await client.verify("guardian", digest, sig_guardian)) is True

    # Cross-agent verification MUST fail (per-key isolation)
    assert (await client.verify("anchor-sentry", digest, sig_guardian)) is False
    assert (await client.verify("guardian", digest, sig_sentry)) is False

    # Public keys must differ (sanity check on per-agent key generation)
    pk_sentry = await client.get_public_key("anchor-sentry")
    pk_guardian = await client.get_public_key("guardian")
    assert pk_sentry != pk_guardian


# ---------------------------------------------------------------------------
# Test 6: Agent identifier mapping + validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kms_client_agent_identifier_mapping():
    """sign() with valid agent identifiers works; unknown agent / invalid digest raise validation errors."""
    client = MockKMSClient()
    digest = hashlib.sha256(b"test").digest()

    # Valid agents work
    sig_sentry = await client.sign("anchor-sentry", digest)
    sig_guardian = await client.sign("guardian", digest)
    assert isinstance(sig_sentry, bytes)
    assert isinstance(sig_guardian, bytes)

    # Unknown agent raises KMSClientValidationError
    with pytest.raises(KMSClientValidationError) as exc_info:
        await client.sign("unknown-agent", digest)
    assert "Unknown agent identifier" in str(exc_info.value)
    assert "unknown-agent" in str(exc_info.value)

    # Non-32-byte digest raises KMSClientValidationError (D-Input enforcement)
    with pytest.raises(KMSClientValidationError) as exc_info:
        await client.sign("anchor-sentry", b"too short")
    assert "32 bytes" in str(exc_info.value)

    # Non-bytes input raises KMSClientValidationError
    with pytest.raises(KMSClientValidationError) as exc_info:
        await client.sign("anchor-sentry", "string-not-bytes")  # type: ignore[arg-type]
    assert "must be bytes" in str(exc_info.value)

    # describe_key works for valid agents
    metadata_sentry = await client.describe_key("anchor-sentry")
    assert metadata_sentry["KeySpec"] == "ECC_SECG_P256K1"
    assert metadata_sentry["KeyUsage"] == "SIGN_VERIFY"
    assert metadata_sentry["KeyState"] == "Enabled"
    assert metadata_sentry["_mock"] is True

    # describe_key for unknown agent raises validation error
    with pytest.raises(KMSClientValidationError):
        await client.describe_key("unknown-agent")


# ---------------------------------------------------------------------------
# Optional integration test (manual run only with AWS_INTEGRATION_TEST=1)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("AWS_INTEGRATION_TEST") != "1",
    reason="Integration test requires AWS credentials and AWS_INTEGRATION_TEST=1",
)
@pytest.mark.asyncio
async def test_real_kms_client_sign_then_verify_against_aws():
    """Real KMSClient against actual AWS KMS. Manual test only.

    Run with: AWS_INTEGRATION_TEST=1 pytest bridge/tests/test_kms_client.py::test_real_kms_client_sign_then_verify_against_aws

    Requires:
      - bridge/.env populated with valid AWS credentials and KMS aliases
      - AWS account has the two KMS keys per Pass 2C Section 12 spec
      - IAM user has kms:Sign + kms:Verify permissions
    """
    client = KMSClient()
    digest = hashlib.sha256(b"VAPI integration test digest").digest()

    signature = await client.sign("anchor-sentry", digest)
    assert isinstance(signature, bytes)
    assert len(signature) > 0

    valid = await client.verify("anchor-sentry", digest, signature)
    assert valid is True

    # Sanity: describe_key returns Pass 2C Section 12 spec values
    metadata = await client.describe_key("anchor-sentry")
    assert metadata.get("KeySpec") == "ECC_SECG_P256K1"
    assert metadata.get("KeyUsage") == "SIGN_VERIFY"
    assert metadata.get("KeyState") == "Enabled"
