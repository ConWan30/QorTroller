"""Phase 235.x-STABILITY-3-PROBE-FIX tests.

Verifies the polling probe handles the doubled-prefix mount correctly,
sources operator API keys from the right places, and aborts before main
load when self-test shows 404. Without these tests, the probe-path bug
that wasted half the 2026-05-08T22:32 first bisection run can recur.

T-235-STAB3-PFIX-1..6.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Probe is in scripts/ which isn't a package; load it as a module.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import stability3_polling_probe as probe  # noqa: E402


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-1: _read_env_file parses KEY=VALUE
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_1_read_env_file_basic():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        p = Path(td) / "fake.env"
        p.write_text(
            "OPERATOR_API_KEY=vapi-test-key\n"
            "# comment line\n"
            "\n"
            "GRIND_MODE=true\n"
            "EQUALS_IN_VALUE=foo=bar=baz\n",
            encoding="utf-8",
        )
        out = probe._read_env_file(p)
        assert out["OPERATOR_API_KEY"] == "vapi-test-key"
        assert out["GRIND_MODE"] == "true"
        assert out["EQUALS_IN_VALUE"] == "foo=bar=baz", \
            "partition should split only on first ="
        # Comment + blank lines NOT in result
        assert "# comment line" not in out


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-2: _read_env_file gracefully handles missing file
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_2_read_env_file_missing():
    out = probe._read_env_file(Path("/nonexistent/path/.env"))
    assert out == {}


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-3: _resolve_api_key precedence — explicit > env > file
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_3_resolve_api_key_explicit_wins():
    with patch.dict("os.environ", {"OPERATOR_API_KEY": "from-env"}, clear=False):
        # Explicit arg wins over env
        assert probe._resolve_api_key("from-arg") == "from-arg"


def test_t_235_stab3_pfix_3b_resolve_api_key_env_used_when_no_explicit():
    with patch.dict("os.environ", {"OPERATOR_API_KEY": "from-env"}, clear=False):
        # No explicit → env used
        result = probe._resolve_api_key(None)
        assert result == "from-env"


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-4: _self_test treats 404 as failure
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_4_self_test_404_fails():
    """Self-test must reject a 404 — that's the bug PROBE-FIX is closing."""
    fake_endpoints = [("/wrong/path", 1.0)]
    fake_headers = {"x-api-key": "irrelevant"}

    def _fake_poll(url, timeout, headers):
        return {
            "ts_ns": 0,
            "url": url,
            "status": 404,
            "latency_ms": 5.0,
            "error": "HTTPError: Not Found",
        }

    with patch.object(probe, "_poll_once", side_effect=_fake_poll):
        ok, results = probe._self_test(
            "http://localhost:8080", fake_endpoints, fake_headers, timeout=2.0
        )
    assert ok is False, "404 must abort self-test"
    assert results[0]["status"] == 404
    assert results[0]["ok"] is False


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-5: _self_test treats 200 as success
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_5_self_test_200_passes():
    fake_endpoints = [
        ("/health", 1.0),
        ("/operator/bridge/capture-health", 3.0),
    ]
    fake_headers = {"x-api-key": "test-key"}

    def _fake_poll(url, timeout, headers):
        return {
            "ts_ns": 0,
            "url": url,
            "status": 200,
            "latency_ms": 50.0,
            "error": None,
        }

    with patch.object(probe, "_poll_once", side_effect=_fake_poll):
        ok, results = probe._self_test(
            "http://localhost:8080", fake_endpoints, fake_headers, timeout=2.0
        )
    assert ok is True
    assert all(r["ok"] for r in results)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-5b: timeout treated as REACHABLE (starvation is the signal)
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_5b_self_test_timeout_passes():
    """A timed-out endpoint means the bridge is alive but starved — that's
    exactly what the probe exists to measure. Don't abort the run."""
    fake_endpoints = [("/operator/bridge/capture-health", 3.0)]
    fake_headers = {"x-api-key": "test-key"}

    def _fake_poll(url, timeout, headers):
        return {
            "ts_ns": 0,
            "url": url,
            "status": None,
            "latency_ms": 10000.0,
            "error": "TimeoutError: timed out",
        }

    with patch.object(probe, "_poll_once", side_effect=_fake_poll):
        ok, results = probe._self_test(
            "http://localhost:8080", fake_endpoints, fake_headers, timeout=2.0
        )
    assert ok is True, "timeout must NOT abort self-test (starvation is the signal)"
    assert results[0]["ok"] is True


# ---------------------------------------------------------------------------
# T-235-STAB3-PFIX-6: corrected paths constant carries doubled prefix
# ---------------------------------------------------------------------------

def test_t_235_stab3_pfix_6_default_paths_use_operator_prefix():
    """Phase 235.x-STABILITY-3-PROBE-FIX freezes the doubled-prefix per
    WIF-061. Future contributor must NOT regress to /bridge/X paths."""
    src = (PROJECT_ROOT / "scripts" / "stability3_polling_probe.py").read_text(
        encoding="utf-8"
    )
    # Operator endpoints MUST go through /operator/ prefix per WIF-061
    assert '"/operator/bridge/capture-health"' in src, \
        "capture-health path must use /operator/ prefix"
    assert '"/operator/bridge/grind-chain-status"' in src, \
        "grind-chain-status path must use /operator/ prefix"
    # /health is on main app (not operator sub-app) — must NOT have prefix
    assert '"/health"' in src
    # Negative — no bare /bridge/X declaration in tuple list
    assert ('("/bridge/capture-health"' not in src and
            '("/bridge/grind-chain-status"' not in src), \
        "regression: bare /bridge/ paths reintroduced"
