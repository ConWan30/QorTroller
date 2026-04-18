"""
Phase 223 SDK Tests — InvariantGate (PV-CI)
T223-S1..T223-S4

Tests:
  T223-S1: InvariantGateResult dataclass has correct slots and defaults
  T223-S2: VAPIInvariantGate instantiates with base_url and api_key
  T223-S3: get_status() returns InvariantGateResult with error on HTTP failure
  T223-S4: get_status() correctly parses full response body
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T223-S1: InvariantGateResult has correct slots ───────────────────────────
def test_T223_S1_invariant_gate_result_slots():
    """InvariantGateResult has expected slots and defaults."""
    from vapi_sdk import InvariantGateResult
    r = InvariantGateResult()
    assert r.pv_ci_enabled is False
    assert r.gate_pass is None
    assert r.total_checked == 0
    assert r.failure_count == 0
    assert r.last_failures == []
    assert r.last_run_ts is None
    assert r.error is None


# ── T223-S2: VAPIInvariantGate instantiates ──────────────────────────────────
def test_T223_S2_vapi_invariant_gate_instantiates():
    """VAPIInvariantGate instantiates with base_url and api_key."""
    from vapi_sdk import VAPIInvariantGate
    client = VAPIInvariantGate("http://localhost:8080", "test-key")
    assert client._base == "http://localhost:8080"
    assert client._key  == "test-key"


# ── T223-S3: get_status() returns error on HTTP failure ──────────────────────
def test_T223_S3_get_status_error_on_http_failure():
    """get_status() returns InvariantGateResult with error on HTTP failure."""
    from vapi_sdk import VAPIInvariantGate, InvariantGateResult
    client = VAPIInvariantGate("http://127.0.0.1:19997")
    result = client.get_status()
    assert isinstance(result, InvariantGateResult)
    assert result.error is not None
    assert result.total_checked == 0


# ── T223-S4: get_status() parses response body ───────────────────────────────
def test_T223_S4_get_status_parses_response():
    """get_status() correctly parses full response body from mock HTTP server."""
    import json
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from vapi_sdk import VAPIInvariantGate, InvariantGateResult

    _payload = {
        "pv_ci_enabled":  True,
        "gate_pass":      True,
        "total_checked":  15,
        "failure_count":  0,
        "last_failures":  [],
        "last_run_ts":    1714200000.0,
        "timestamp":      1714200001.0,
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
        client = VAPIInvariantGate(f"http://127.0.0.1:{port}")
        result = client.get_status()
        assert result.pv_ci_enabled is True
        assert result.gate_pass is True
        assert result.total_checked == 15
        assert result.failure_count == 0
        assert result.last_failures == []
        assert result.last_run_ts == 1714200000.0
        assert result.error is None
    finally:
        server.shutdown()
