"""
Phase 237-CONSENT SDK Tests — Per-Category Gamer Consent
T237-S1..T237-S4

Tests:
  T237-S1: GamerConsentResult dataclass has correct slots and defaults
  T237-S2: VAPIConsent instantiates with base_url and api_key
  T237-S3: get_status() returns GamerConsentResult with error on HTTP failure
  T237-S4: get_status() correctly parses both aggregated and single-category response
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T237-S1: GamerConsentResult slots ─────────────────────────────────────────
def test_T237_S1_gamer_consent_result_slots():
    """GamerConsentResult has expected slots and defaults."""
    from vapi_sdk import GamerConsentResult
    r = GamerConsentResult()
    assert r.device_id  == ""
    assert r.categories == {}
    assert r.category   is None
    assert r.granted    is False
    assert r.revoked    is False
    assert r.found      is False
    assert r.error      is None


# ── T237-S2: VAPIConsent instantiates ─────────────────────────────────────────
def test_T237_S2_vapi_consent_instantiates():
    """VAPIConsent instantiates with base_url and api_key, trims trailing slash."""
    from vapi_sdk import VAPIConsent
    client = VAPIConsent("http://localhost:8080/", "test-key-237")
    assert client._base == "http://localhost:8080"  # trailing slash stripped
    assert client._key  == "test-key-237"


# ── T237-S3: get_status() returns error on HTTP failure ───────────────────────
def test_T237_S3_get_status_error_on_http_failure():
    """get_status() returns GamerConsentResult with error on HTTP failure."""
    from vapi_sdk import VAPIConsent, GamerConsentResult
    client = VAPIConsent("http://127.0.0.1:19999")  # nothing listening
    result = client.get_status("device_does_not_matter")
    assert isinstance(result, GamerConsentResult)
    assert result.error is not None
    assert result.granted is False
    assert result.categories == {}


# ── T237-S4: get_status() parses both aggregated and single-category responses ─
def test_T237_S4_get_status_parses_responses():
    """get_status() parses aggregated AND single-category response bodies."""
    import json
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
    from vapi_sdk import VAPIConsent

    _aggregated_payload = {
        "device_id": "device_alpha",
        "categories": {
            "TOURNAMENT_GATE": {
                "category": "TOURNAMENT_GATE",
                "granted":  True,
                "revoked":  False,
                "found":    True,
                "consent_given": True,
                "consent_ts":    1714100000.0,
                "revocation_reason": "",
                "erasure_requested": False,
                "erasure_completed": False,
            },
            "ANONYMIZED_RESEARCH": {
                "category": "ANONYMIZED_RESEARCH",
                "granted":  False,
                "revoked":  False,
                "found":    False,
                "consent_given": False,
                "consent_ts":    None,
                "revocation_reason": "",
                "erasure_requested": False,
                "erasure_completed": False,
            },
            "MANUFACTURER_CERT": {
                "category": "MANUFACTURER_CERT",
                "granted":  False,
                "revoked":  False,
                "found":    False,
            },
            "MARKETPLACE": {
                "category": "MARKETPLACE",
                "granted":  False,
                "revoked":  False,
                "found":    False,
            },
        },
    }

    _single_payload = {
        "category":  "TOURNAMENT_GATE",
        "granted":   True,
        "revoked":   False,
        "found":     True,
        "consent_given": True,
        "consent_ts":    1714100000.0,
        "revocation_reason": "",
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            payload = _single_payload if params.get("category") else _aggregated_payload
            body = json.dumps(payload).encode()
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
        client = VAPIConsent(f"http://127.0.0.1:{port}")

        # Aggregated query (no category param)
        agg = client.get_status("device_alpha")
        assert agg.error is None
        assert agg.device_id == "device_alpha"
        assert set(agg.categories.keys()) == {
            "TOURNAMENT_GATE", "ANONYMIZED_RESEARCH",
            "MANUFACTURER_CERT", "MARKETPLACE",
        }
        assert agg.categories["TOURNAMENT_GATE"]["granted"] is True
        assert agg.categories["MARKETPLACE"]["granted"] is False
        assert agg.category is None  # aggregated mode

        # Single-category query
        single = client.get_status("device_alpha", category="TOURNAMENT_GATE")
        assert single.error is None
        assert single.category == "TOURNAMENT_GATE"
        assert single.granted is True
        assert single.revoked is False
        assert single.found is True
    finally:
        server.shutdown()
