"""
Phase 222 SDK Tests — BiometricBoundGovernance (BBG)
T222-S1..T222-S4

Tests:
  T222-S1: BBGProposalResult dataclass has correct slots and defaults
  T222-S2: VAPIBiometricGovernance instantiates with base_url and api_key
  T222-S3: get_status() returns BBGProposalResult with error on HTTP failure
  T222-S4: get_status() correctly parses full response body
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T222-S1: BBGProposalResult has correct slots ──────────────────────────────
def test_T222_S1_bbg_proposal_result_slots():
    """BBGProposalResult has expected slots and defaults."""
    from vapi_sdk import BBGProposalResult
    r = BBGProposalResult()
    assert r.bbg_enabled is False
    assert r.total_proposals == 0
    assert r.latest_proposal_hash is None
    assert r.latest_proposer is None
    assert r.on_chain_confirmed is False
    assert r.last_proposal_ts is None
    assert r.error is None


# ── T222-S2: VAPIBiometricGovernance instantiates ────────────────────────────
def test_T222_S2_vapi_bbg_instantiates():
    """VAPIBiometricGovernance instantiates with base_url and api_key."""
    from vapi_sdk import VAPIBiometricGovernance
    client = VAPIBiometricGovernance("http://localhost:8080", "test-key")
    assert client._base == "http://localhost:8080"
    assert client._key  == "test-key"


# ── T222-S3: get_status() returns error on HTTP failure ───────────────────────
def test_T222_S3_get_status_error_on_http_failure():
    """get_status() returns BBGProposalResult with error on HTTP failure."""
    from vapi_sdk import VAPIBiometricGovernance, BBGProposalResult
    client = VAPIBiometricGovernance("http://127.0.0.1:19998")
    result = client.get_status()
    assert isinstance(result, BBGProposalResult)
    assert result.error is not None
    assert result.total_proposals == 0


# ── T222-S4: get_status() parses response body ────────────────────────────────
def test_T222_S4_get_status_parses_response():
    """get_status() correctly parses full response body from mock HTTP server."""
    import json
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from vapi_sdk import VAPIBiometricGovernance, BBGProposalResult

    _payload = {
        "bbg_enabled":          True,
        "total_proposals":      3,
        "latest_proposal_hash": "deadbeef" * 8,
        "latest_proposer":      "0xProposer123",
        "on_chain_confirmed":   True,
        "last_proposal_ts":     1714100000.0,
        "timestamp":            1714100001.0,
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port   = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = VAPIBiometricGovernance(f"http://127.0.0.1:{port}")
        result = client.get_status()
        assert result.bbg_enabled is True
        assert result.total_proposals == 3
        assert result.latest_proposal_hash == "deadbeef" * 8
        assert result.latest_proposer == "0xProposer123"
        assert result.on_chain_confirmed is True
        assert result.last_proposal_ts == 1714100000.0
        assert result.error is None
    finally:
        server.shutdown()
