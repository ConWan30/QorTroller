"""
Phase 225 SDK Tests — InvariantGate Provenance Chain + Governance History API
T225-SDK-1..T225-SDK-4

Tests:
  T225-SDK-1: previous_changes() returns list from GET /agent/allowlist-governance-history
  T225-SDK-2: previous_changes() returns governance entries with expected keys
  T225-SDK-3: chain_intact() returns True from mock history endpoint with intact chain
  T225-SDK-4: chain_intact() returns False when server reports chain_intact=False
"""
import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


def _start_mock_server(handler_class):
    """Start a mock HTTP server and return (server, port, thread)."""
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


# ── T225-SDK-1: previous_changes() calls allowlist-governance-history ─────────
def test_T225_SDK_1_previous_changes_calls_history_endpoint():
    """previous_changes() fetches from GET /agent/allowlist-governance-history."""
    from vapi_sdk import VAPIAllowlistGovernance

    _entries = [
        {
            "id": 2,
            "governance_provenance_hash": "c" * 64,
            "previous_provenance_hash":   "a" * 64,
            "new_allowlist_hash":         "d" * 64,
            "reason_category":            "bugfix",
            "reason_text":                "fixed incorrect validation",
            "created_at":                 1714200100.0,
        },
        {
            "id": 1,
            "governance_provenance_hash": "a" * 64,
            "previous_provenance_hash":   "0" * 64,
            "new_allowlist_hash":         "b" * 64,
            "reason_category":            "refactor",
            "reason_text":                "renamed helper function",
            "created_at":                 1714200000.0,
        },
    ]
    _history_payload = {"entries": _entries, "total_entries": 2, "chain_intact": True, "timestamp": 1714200200.0}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if "/agent/allowlist-governance-history" in self.path:
                body = json.dumps(_history_payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, *a): pass

    server, port, _ = _start_mock_server(_Handler)
    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        changes = client.previous_changes(limit=10)
        assert isinstance(changes, list)
        assert len(changes) == 2
        # Newest first (server returns newest first)
        assert changes[0]["governance_provenance_hash"] == "c" * 64
        assert changes[1]["reason_category"] == "refactor"
    finally:
        server.shutdown()


# ── T225-SDK-2: previous_changes() entries have expected keys ─────────────────
def test_T225_SDK_2_previous_changes_entry_keys():
    """previous_changes() entries include all expected Phase 225 provenance chain keys."""
    from vapi_sdk import VAPIAllowlistGovernance

    _entry = {
        "id": 1,
        "governance_provenance_hash": "e" * 64,
        "previous_provenance_hash":   "0" * 64,
        "new_allowlist_hash":         "f" * 64,
        "reason_category":            "refactor",
        "reason_text":                "reorganised module imports",
        "created_at":                 1714200000.0,
    }
    _payload = {"entries": [_entry], "total_entries": 1, "chain_intact": True, "timestamp": 1714200001.0}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server, port, _ = _start_mock_server(_Handler)
    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        changes = client.previous_changes()
        assert len(changes) == 1
        entry = changes[0]
        expected_keys = {
            "id", "governance_provenance_hash", "previous_provenance_hash",
            "new_allowlist_hash", "reason_category", "reason_text", "created_at",
        }
        assert expected_keys.issubset(set(entry.keys()))
        assert len(entry["governance_provenance_hash"]) == 64
    finally:
        server.shutdown()


# ── T225-SDK-3: chain_intact() returns True when server says intact ───────────
def test_T225_SDK_3_chain_intact_true():
    """chain_intact() returns True when GET /agent/allowlist-governance-history reports chain_intact=True."""
    from vapi_sdk import VAPIAllowlistGovernance

    _payload = {"entries": [], "total_entries": 0, "chain_intact": True, "timestamp": 1714200001.0}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    server, port, _ = _start_mock_server(_Handler)
    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        assert client.chain_intact() is True
    finally:
        server.shutdown()


# ── T225-SDK-4: chain_intact() returns False when server reports broken chain ──
def test_T225_SDK_4_chain_intact_false():
    """chain_intact() returns False when GET /agent/allowlist-governance-history reports chain_intact=False."""
    from vapi_sdk import VAPIAllowlistGovernance

    _payload = {
        "entries": [
            {"id": 2, "governance_provenance_hash": "m" * 64, "previous_provenance_hash": "z" * 64,
             "new_allowlist_hash": "n" * 64, "reason_category": "bugfix",
             "reason_text": "second entry with broken chain", "created_at": 1714200100.0},
            {"id": 1, "governance_provenance_hash": "k" * 64, "previous_provenance_hash": "0" * 64,
             "new_allowlist_hash": "l" * 64, "reason_category": "refactor",
             "reason_text": "first chain entry", "created_at": 1714200000.0},
        ],
        "total_entries": 2,
        "chain_intact": False,
        "timestamp": 1714200200.0,
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

    server, port, _ = _start_mock_server(_Handler)
    try:
        client = VAPIAllowlistGovernance(f"http://127.0.0.1:{port}")
        assert client.chain_intact() is False
    finally:
        server.shutdown()
