"""
Phase 221 SDK Tests — ProtocolCoherence (PoPC)
T221-S1..T221-S4

Tests:
  T221-S1: ProtocolCoherenceResult dataclass has correct slots and defaults
  T221-S2: VAPIProtocolCoherence instantiates with base_url and api_key
  T221-S3: get_status() returns ProtocolCoherenceResult with error on HTTP failure
  T221-S4: get_status() correctly parses full response body
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T221-S1: ProtocolCoherenceResult has correct slots ───────────────────────
def test_T221_S1_protocol_coherence_result_slots():
    """ProtocolCoherenceResult has expected slots and defaults."""
    from vapi_sdk import ProtocolCoherenceResult
    r = ProtocolCoherenceResult()
    assert r.protocol_coherence_enabled is False
    assert r.total_anchors == 0
    assert r.latest_merkle_root is None
    assert r.agent_count == 0
    assert r.on_chain_confirmed is False
    assert r.last_anchor_ts is None
    assert r.error is None


# ── T221-S2: VAPIProtocolCoherence instantiates ───────────────────────────────
def test_T221_S2_vapi_protocol_coherence_instantiates():
    """VAPIProtocolCoherence instantiates with base_url and api_key."""
    from vapi_sdk import VAPIProtocolCoherence
    client = VAPIProtocolCoherence("http://localhost:8080", "test-key")
    assert client._base == "http://localhost:8080"
    assert client._key  == "test-key"


# ── T221-S3: get_status() returns error result on HTTP failure ────────────────
def test_T221_S3_get_status_error_on_http_failure():
    """get_status() returns ProtocolCoherenceResult with error on HTTP failure."""
    from vapi_sdk import VAPIProtocolCoherence, ProtocolCoherenceResult
    client = VAPIProtocolCoherence("http://127.0.0.1:19999")  # nothing listening
    result = client.get_status()
    assert isinstance(result, ProtocolCoherenceResult)
    assert result.error is not None
    assert result.total_anchors == 0


# ── T221-S4: get_status() parses response body ────────────────────────────────
def test_T221_S4_get_status_parses_response():
    """get_status() correctly parses full response body from mock HTTP server."""
    import json
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from vapi_sdk import VAPIProtocolCoherence, ProtocolCoherenceResult

    _payload = {
        "protocol_coherence_enabled": True,
        "total_anchors":              5,
        "latest_merkle_root":         "abcdef" * 10 + "abcd",
        "agent_count":                36,
        "on_chain_confirmed":         True,
        "last_anchor_ts":             1714000000.0,
        "timestamp":                  1714000001.0,
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
        client = VAPIProtocolCoherence(f"http://127.0.0.1:{port}")
        result = client.get_status()
        assert result.protocol_coherence_enabled is True
        assert result.total_anchors == 5
        assert result.agent_count   == 36
        assert result.on_chain_confirmed is True
        assert result.last_anchor_ts == 1714000000.0
        assert result.error is None
    finally:
        server.shutdown()
