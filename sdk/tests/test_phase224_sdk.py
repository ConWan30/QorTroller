"""
Phase 224 SDK Tests — Allowlist Governance
T224-SDK-1..T224-SDK-4

Tests:
  T224-SDK-1: VAPIAllowlistGovernance.status() returns AllowlistGovernanceResult with hash field
  T224-SDK-2: AllowlistGovernanceResult has all 7 slots (slots=True)
  T224-SDK-3: previous_changes() parses governance entries from mock HTTP response
  T224-SDK-4: suspicious_changes() returns empty list when no suspicious entries
"""
import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T224-SDK-1: status() returns AllowlistGovernanceResult ───────────────────
def test_T224_SDK_1_status_returns_result():
    """VAPIAllowlistGovernance.status() returns AllowlistGovernanceResult with current_hash."""
    from vapi_sdk import VAPIAllowlistGovernance, AllowlistGovernanceResult

    # Mock server: coherence status returns allowlist_hash; change status not found
    _coherence_payload = {
        "protocol_coherence_enabled": True,
        "total_anchors": 1,
        "latest_merkle_root": "a" * 64,
        "agent_count": 37,
        "on_chain_confirmed": False,
        "last_anchor_ts": 1714200000.0,
        "timestamp": 1714200001.0,
        "allowlist_hash": "b" * 64,
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if "/agent/protocol-coherence-status" in self.path:
                body = json.dumps(_coherence_payload).encode()
            else:
                body = json.dumps({"error": "not found"}).encode()
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        result = client.status()
        assert isinstance(result, AllowlistGovernanceResult)
        assert result.current_hash == "b" * 64
        assert result.error is None or isinstance(result.error, str)
    finally:
        server.shutdown()


# ── T224-SDK-2: AllowlistGovernanceResult has 7 slots ────────────────────────
def test_T224_SDK_2_allowlist_governance_result_slots():
    """AllowlistGovernanceResult has all 7 slots with correct defaults (slots=True)."""
    from vapi_sdk import AllowlistGovernanceResult
    r = AllowlistGovernanceResult()
    assert r.current_hash == ""
    assert r.last_change_ts is None
    assert r.last_change_reason is None
    assert r.last_change_category is None
    assert r.suspicious_change_count == 0
    assert r.on_chain_anchor_ts is None
    assert r.error is None
    # Verify slots=True (no __dict__ on instance)
    assert not hasattr(r, "__dict__")


# ── T224-SDK-3: previous_changes() parses governance entries ─────────────────
def test_T224_SDK_3_previous_changes_parses_governance():
    """previous_changes() parses governance entries from mock response."""
    from vapi_sdk import VAPIAllowlistGovernance

    _gate_payload = {
        "pv_ci_enabled": True,
        "gate_pass": True,
        "total_checked": 16,
        "failure_count": 0,
        "last_failures": [],
        "last_run_ts": 1714200000.0,
        "run_source": "governance:refactor:renamed helper function",
        "timestamp": 1714200001.0,
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(_gate_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        changes = client.previous_changes()
        assert isinstance(changes, list)
        assert len(changes) >= 1
        first = changes[0]
        assert "run_source" in first or "error" in first
        if "run_source" in first:
            assert first["run_source"].startswith("governance:")
    finally:
        server.shutdown()


# ── T224-SDK-4: suspicious_changes() returns empty list when none ─────────────
def test_T224_SDK_4_suspicious_changes_empty():
    """suspicious_changes() returns empty list when suspicious_count=0."""
    from vapi_sdk import VAPIAllowlistGovernance

    _change_payload = {
        "total_changes": 5,
        "suspicious_count": 0,
        "latest_previous_hash": "a" * 64,
        "latest_new_hash": "b" * 64,
        "latest_detected_at": "1714200000.0",
        "timestamp": 1714200001.0,
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(_change_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        result = client.suspicious_changes()
        assert isinstance(result, list)
        assert len(result) == 0
    finally:
        server.shutdown()
