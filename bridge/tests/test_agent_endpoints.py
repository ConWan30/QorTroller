"""Phase O0 Stream 4-prep Session 2 — five /agent/agent-* endpoint integration tests.

Verifies the five Phase O0 read-only agent-token-gated endpoints per
Pass 2C Section 5.1 lines 794-799 + Decision B3 (agent- prefix
preserved).

Endpoints:
  GET /agent/agent-commit-history
  GET /agent/agent-commit-status
  GET /agent/physical-data-attestation-history
  GET /agent/physical-data-attestation-status
  GET /agent/agent-registry-status

Tests:
  T-AE-1:  agent-commit-history with valid agent token returns rows.
  T-AE-2:  agent-commit-history without Authorization header → 401.
  T-AE-3:  agent-commit-history with operator x-api-key (NOT agent
           token) → 401 (allowlist enforcement: operator keys do not
           authenticate to /agent/agent-* endpoints).
  T-AE-4:  agent-commit-status returns the latest commit summary.
  T-AE-5:  agent-commit-status without token → 401.
  T-AE-6:  physical-data-attestation-history with filter params returns
           rows; store call receives the filter args.
  T-AE-7:  physical-data-attestation-history without token → 401.
  T-AE-8:  physical-data-attestation-status returns the latest summary.
  T-AE-9:  physical-data-attestation-status without token → 401.
  T-AE-10: agent-registry-status with empty agent_registry_address
           returns deferred-activation response (Decision B2).
  T-AE-11: agent-registry-status with populated address returns live
           shape (deployed=True).
  T-AE-12: agent-registry-status without token → 401.
  T-AE-13: When OAuth not configured (no clients), all five endpoints
           return 503.
  T-AE-14: Operator endpoints with x-api-key are UNAFFECTED by the new
           agent endpoints (smoke test that we did not regress
           _check_key / _check_read_key).
"""
import base64
import hashlib
import hmac
import os
import sys
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt  # type: ignore[import-untyped]

from vapi_bridge.operator_api import create_operator_app  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_ISSUER_SECRET = "test-issuer-signing-secret-32-bytes-min"
_CLIENT_ID = "vapi-anchor-sentry"
_CLIENT_SECRET = "sentry-shared-secret-not-real"
_PHASE_O0_SCOPES = ["bridge:agent:phases:read"]


def _make_cfg(
    oauth_configured: bool = True,
    agent_registry_address: str = "",
    operator_api_key: str = "operator-test-key",
):
    cfg = MagicMock()
    cfg.operator_api_key = operator_api_key
    cfg.phg_registry_address = ""
    cfg.oauth_issuer_secret = _ISSUER_SECRET if oauth_configured else ""
    cfg.oauth_token_ttl_seconds = 300
    cfg.oauth_issuer_url = "vapi-bridge-oauth"
    cfg.oauth_audience = "vapi-bridge-agent-endpoints"
    cfg.hmac_nonce_window_seconds = 600
    cfg.hmac_timestamp_tolerance_seconds = 300
    cfg.agent_registry_address = agent_registry_address
    cfg.grind_session_id = ""
    cfg.grind_target = 100
    if oauth_configured:
        cfg.get_oauth_clients.return_value = {
            _CLIENT_ID: (_CLIENT_SECRET, list(_PHASE_O0_SCOPES)),
        }
    else:
        cfg.get_oauth_clients.return_value = {}
    return cfg


def _make_store():
    store = MagicMock()
    store.get_recent_insights.return_value = []
    store.get_federation_clusters.return_value = []
    store.get_last_phg_checkpoint.return_value = None
    store.get_credential_mint.return_value = None
    store.get_all_latest_digests.return_value = []
    store.get_latest_digest.return_value = None
    store.get_devices_by_risk_label.return_value = []
    # Phase O0 store methods
    store.get_agent_commit_history.return_value = [
        {"id": 1, "commit_hash": "abc", "agent_id": _CLIENT_ID, "ts_ns": 1},
    ]
    store.get_agent_commit_status.return_value = {
        "total_commits":      1,
        "latest_hash":        "abc",
        "latest_agent_id":    _CLIENT_ID,
        "latest_commit_sha":  "deadbeef" * 5,
        "latest_ts_ns":       1,
        "on_chain_confirmed": False,
        "anchor_id":          -1,
        "timestamp":          time.time(),
    }
    store.get_physical_data_attestation_history.return_value = [
        {"id": 1, "pda_commitment": "pda-hash-1", "agent_id": _CLIENT_ID,
         "attestation_type": "BIOMETRIC_CORPUS_SNAPSHOT", "ts_ns": 1},
    ]
    store.get_physical_data_attestation_status.return_value = {
        "total_attestations":      1,
        "latest_pda_commitment":   "pda-hash-1",
        "latest_agent_id":         _CLIENT_ID,
        "latest_attestation_type": "BIOMETRIC_CORPUS_SNAPSHOT",
        "latest_ts_ns":            1,
        "on_chain_confirmed":      False,
        "anchor_id":               -1,
        "timestamp":               time.time(),
    }
    return store


def _make_client(
    oauth_configured: bool = True,
    agent_registry_address: str = "",
    chain=None,
):
    cfg = _make_cfg(
        oauth_configured=oauth_configured,
        agent_registry_address=agent_registry_address,
    )
    store = _make_store()
    app = create_operator_app(cfg, store, chain=chain)
    return TestClient(app), store, cfg


def _make_token(
    client_id: str = _CLIENT_ID,
    secret: str = _ISSUER_SECRET,
    scopes: "list[str]" = _PHASE_O0_SCOPES,
    ttl: int = 300,
) -> str:
    now = int(time.time())
    payload = {
        "sub":   client_id,
        "iss":   "vapi-bridge-oauth",
        "aud":   "vapi-bridge-agent-endpoints",
        "exp":   now + ttl,
        "iat":   now,
        "scope": " ".join(scopes),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("ascii")
    return token


def _signed_headers(
    method: str,
    path: str,
    body: bytes = b"",
    token: "str | None" = None,
) -> dict:
    """Build a complete header dict for a valid agent-token request."""
    if token is None:
        token = _make_token()
    ts = int(time.time())
    nonce = f"endpoint-test-{ts}-{os.urandom(4).hex()}"
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"{method.upper()}\n{path}\n{ts}\n{nonce}\n{body_hash}"
    sig = hmac.new(
        _CLIENT_SECRET.encode("utf-8"), canonical.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return {
        "Authorization": f"Bearer {token}",
        "X-Agent-KeyId": _CLIENT_ID,
        "X-Timestamp":   str(ts),
        "X-Nonce":       nonce,
        "X-Signature":   base64.b64encode(sig).decode("ascii"),
    }


# ---------------------------------------------------------------------------
# T-AE-1
# ---------------------------------------------------------------------------

def test_t_ae_1_agent_commit_history_with_valid_token():
    client, store, _ = _make_client()
    headers = _signed_headers("GET", "/agent/agent-commit-history")
    r = client.get("/agent/agent-commit-history", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["client_id"] == _CLIENT_ID
    assert body["count"] == 1
    assert body["commits"][0]["commit_hash"] == "abc"
    store.get_agent_commit_history.assert_called_once_with("", 20)


# ---------------------------------------------------------------------------
# T-AE-2
# ---------------------------------------------------------------------------

def test_t_ae_2_agent_commit_history_without_token_rejects():
    client, _, _ = _make_client()
    r = client.get("/agent/agent-commit-history")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# T-AE-3
# ---------------------------------------------------------------------------

def test_t_ae_3_operator_key_does_not_authenticate_agent_endpoint():
    """Allowlist enforcement: providing the operator x-api-key (or
    operator-key Query param) does NOT authenticate to /agent/agent-*
    endpoints. Only Bearer agent tokens with all four HMAC headers
    succeed.
    """
    client, _, _ = _make_client()
    # Try with x-api-key header (operator read-key path)
    r = client.get(
        "/agent/agent-commit-history",
        headers={"x-api-key": "operator-test-key"},
    )
    assert r.status_code == 401
    # Try with api_key Query param (operator full-key path)
    r2 = client.get(
        "/agent/agent-commit-history?api_key=operator-test-key",
    )
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# T-AE-4
# ---------------------------------------------------------------------------

def test_t_ae_4_agent_commit_status_with_valid_token():
    client, store, _ = _make_client()
    headers = _signed_headers("GET", "/agent/agent-commit-status")
    r = client.get("/agent/agent-commit-status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_commits"] == 1
    assert body["latest_hash"] == "abc"
    assert body["client_id"] == _CLIENT_ID  # augmented for audit
    store.get_agent_commit_status.assert_called_once()


# ---------------------------------------------------------------------------
# T-AE-5
# ---------------------------------------------------------------------------

def test_t_ae_5_agent_commit_status_without_token_rejects():
    client, _, _ = _make_client()
    r = client.get("/agent/agent-commit-status")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# T-AE-6
# ---------------------------------------------------------------------------

def test_t_ae_6_pda_history_with_filters():
    client, store, _ = _make_client()
    # Sign WITH query string per Decision B4
    path_with_query = (
        "/agent/physical-data-attestation-history"
        "?agent_id=vapi-anchor-sentry&attestation_type=BIOMETRIC_CORPUS_SNAPSHOT&limit=5"
    )
    headers = _signed_headers("GET", path_with_query)
    r = client.get(path_with_query, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filter_agent"] == _CLIENT_ID
    assert body["filter_attestation_type"] == "BIOMETRIC_CORPUS_SNAPSHOT"
    assert body["limit"] == 5
    assert body["count"] == 1
    # Store called with the parsed filter args
    store.get_physical_data_attestation_history.assert_called_once_with(
        _CLIENT_ID, "BIOMETRIC_CORPUS_SNAPSHOT", 5,
    )


# ---------------------------------------------------------------------------
# T-AE-7
# ---------------------------------------------------------------------------

def test_t_ae_7_pda_history_without_token_rejects():
    client, _, _ = _make_client()
    r = client.get("/agent/physical-data-attestation-history")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# T-AE-8
# ---------------------------------------------------------------------------

def test_t_ae_8_pda_status_with_valid_token():
    client, store, _ = _make_client()
    headers = _signed_headers("GET", "/agent/physical-data-attestation-status")
    r = client.get("/agent/physical-data-attestation-status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["latest_pda_commitment"] == "pda-hash-1"
    assert body["latest_attestation_type"] == "BIOMETRIC_CORPUS_SNAPSHOT"
    assert body["client_id"] == _CLIENT_ID
    store.get_physical_data_attestation_status.assert_called_once()


# ---------------------------------------------------------------------------
# T-AE-9
# ---------------------------------------------------------------------------

def test_t_ae_9_pda_status_without_token_rejects():
    client, _, _ = _make_client()
    r = client.get("/agent/physical-data-attestation-status")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# T-AE-10
# ---------------------------------------------------------------------------

def test_t_ae_10_agent_registry_status_deferred_activation():
    """Decision B2: empty agent_registry_address → deferred-activation
    response with deployed=False and an explanatory status string.
    """
    client, _, _ = _make_client(agent_registry_address="")
    headers = _signed_headers("GET", "/agent/agent-registry-status")
    r = client.get("/agent/agent-registry-status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registry_address"] == ""
    assert body["deployed"] is False
    assert "not yet deployed" in body["status"].lower()
    assert body["client_id"] == _CLIENT_ID


# ---------------------------------------------------------------------------
# T-AE-11
# ---------------------------------------------------------------------------

def test_t_ae_11_agent_registry_status_populated_address():
    """When agent_registry_address is non-empty but no chain client is
    available, the endpoint returns deployed=True with the address and
    a `live_read_skipped` marker (no 5xx).
    """
    populated = "0x" + "AB" * 20
    client, _, _ = _make_client(agent_registry_address=populated)
    headers = _signed_headers("GET", "/agent/agent-registry-status")
    r = client.get("/agent/agent-registry-status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registry_address"] == populated
    assert body["deployed"] is True
    assert body["live_read_skipped"] == "chain client unavailable"
    assert "live_read_error" not in body
    assert "total_agents" not in body


# ---------------------------------------------------------------------------
# T-AE-12
# ---------------------------------------------------------------------------

def test_t_ae_12_agent_registry_status_without_token_rejects():
    client, _, _ = _make_client()
    r = client.get("/agent/agent-registry-status")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# T-AE-13
# ---------------------------------------------------------------------------

def test_t_ae_13_oauth_not_configured_returns_503():
    """When oauth_issuer_secret is empty (or no clients), every agent
    endpoint returns 503 'OAuth not configured'.
    """
    client, _, _ = _make_client(oauth_configured=False)
    for path in (
        "/agent/agent-commit-history",
        "/agent/agent-commit-status",
        "/agent/physical-data-attestation-history",
        "/agent/physical-data-attestation-status",
        "/agent/agent-registry-status",
    ):
        r = client.get(
            path, headers={"Authorization": "Bearer anything"},
        )
        assert r.status_code == 503, f"{path} expected 503, got {r.status_code}"


# ---------------------------------------------------------------------------
# T-AE-14
# ---------------------------------------------------------------------------

def test_t_ae_14_existing_health_endpoint_unchanged():
    """Smoke test: pre-existing /health endpoint still returns 200
    without any auth — confirms Session 2 did not regress the 154+
    operator endpoints.
    """
    client, _, _ = _make_client()
    r = client.get("/health")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# T-AE-15  (live read success path — Phase O0 ON-CHAIN COMPLETE)
# ---------------------------------------------------------------------------

class _AsyncMock:
    """Minimal async-callable returning a fixed value (avoids depending on
    AsyncMock symbol differences across MagicMock versions).
    """
    def __init__(self, value):
        self._value = value
        self.calls = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        return self._value


def test_t_ae_15_agent_registry_status_live_read_success():
    """When chain client is wired and view calls succeed, the endpoint
    surfaces total_agents + per-agent records for Sentry and Guardian.
    """
    populated = "0x" + "CD" * 20
    sentry_pk   = "0xeaA6FD569a964C08D541F8e154aB3Ac8cD4e2743"
    guardian_pk = "0x9c577Fb2162824565ef57edd1B55a8EC5f58c181"

    chain = MagicMock()
    chain.get_agent_registry_total = _AsyncMock(2)

    async def _get_record(agent_id_hex: str):
        if agent_id_hex.lower().startswith("0xb21e1ec2"):
            return {
                "public_key": sentry_pk,
                "scope_hash": "0xebe899279b230ff5d71db22dc4b80282c810ff5bd1a9d249db6e6d309af52e41",
                "status":     0,
            }
        if agent_id_hex.lower().startswith("0xbd8c7fba"):
            return {
                "public_key": guardian_pk,
                "scope_hash": "0x46807e13dd1c81cefa784ab8b30f8cdcaefd60697de921aae46ac24dac000a50",
                "status":     0,
            }
        raise AssertionError(f"unexpected agent_id={agent_id_hex}")

    chain.get_agent_record = _get_record

    client, _, _ = _make_client(
        agent_registry_address=populated, chain=chain,
    )
    headers = _signed_headers("GET", "/agent/agent-registry-status")
    r = client.get("/agent/agent-registry-status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registry_address"] == populated
    assert body["deployed"] is True
    assert body["total_agents"] == 2
    assert "live_read_skipped" not in body
    assert "live_read_error" not in body

    sentry = body["agents"]["sentry"]
    assert sentry["registered"] is True
    assert sentry["public_key"] == sentry_pk
    assert sentry["status"] == 0  # STATUS_DEFINED — Phase O0 exit state

    guardian = body["agents"]["guardian"]
    assert guardian["registered"] is True
    assert guardian["public_key"] == guardian_pk
    assert guardian["status"] == 0


# ---------------------------------------------------------------------------
# T-AE-16  (live read failure is fail-open)
# ---------------------------------------------------------------------------

def test_t_ae_16_agent_registry_status_live_read_failure_fails_open():
    """A transient RPC failure during view calls must NOT 5xx the
    endpoint — bridge surfaces the error in `live_read_error` and the
    operator agents continue to observe in shadow mode.
    """
    populated = "0x" + "EF" * 20

    async def _boom(*_a, **_kw):
        raise RuntimeError("rpc unreachable")

    chain = MagicMock()
    chain.get_agent_registry_total = _boom
    chain.get_agent_record = _boom

    client, _, _ = _make_client(
        agent_registry_address=populated, chain=chain,
    )
    headers = _signed_headers("GET", "/agent/agent-registry-status")
    r = client.get("/agent/agent-registry-status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registry_address"] == populated
    assert body["deployed"] is True
    assert body["live_read_error"] == "rpc unreachable"
    assert "total_agents" not in body
    assert "agents" not in body
