"""
Phase 196 — TournamentPreflightResult biometric_ttl_ok slot SDK tests.
"""
import pytest


# ---------------------------------------------------------------------------
# T196S-1: TournamentPreflightResult has biometric_ttl_ok slot (default True)
# ---------------------------------------------------------------------------

def test_t196s_1_preflight_result_has_biometric_ttl_ok():
    from vapi_sdk import TournamentPreflightResult
    r = TournamentPreflightResult(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True,
    )
    assert r.biometric_ttl_ok is True  # default


# ---------------------------------------------------------------------------
# T196S-2: biometric_ttl_ok=False persists on result
# ---------------------------------------------------------------------------

def test_t196s_2_biometric_ttl_ok_false():
    from vapi_sdk import TournamentPreflightResult
    r = TournamentPreflightResult(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=False,
    )
    assert r.biometric_ttl_ok is False
    assert r.overall_pass is False


# ---------------------------------------------------------------------------
# T196S-3: VAPITournamentPreflight.get_status() network error → biometric_ttl_ok=True (fail-open)
# ---------------------------------------------------------------------------

def test_t196s_3_network_error_biometric_ttl_ok_fail_open():
    from vapi_sdk import VAPITournamentPreflight
    pf = VAPITournamentPreflight("http://127.0.0.1:1", "key")
    result = pf.get_status()
    assert result.biometric_ttl_ok is True  # fail-open
    assert result.error is not None


# ---------------------------------------------------------------------------
# T196S-4: biometric_ttl_ok=False causes overall_pass=False when all others pass
# ---------------------------------------------------------------------------

def test_t196s_4_ttl_not_ok_blocks_overall():
    from vapi_sdk import TournamentPreflightResult
    r = TournamentPreflightResult(
        separation_ok=True,
        l4_ok=True,
        gate_ok=True,
        cert_ok=True,
        audit_ok=True,
        overall_pass=False,  # blocked by biometric_ttl_ok
        biometric_ttl_ok=False,
    )
    # When biometric_ttl_ok is False, overall_pass must be False
    assert r.overall_pass is False
    assert r.biometric_ttl_ok is False
