"""
Phase 197 — TournamentPreflightResult all_pairs_p0_ok slot SDK tests.
"""
import pytest


# ---------------------------------------------------------------------------
# T197S-1: TournamentPreflightResult has all_pairs_p0_ok slot (default False)
# ---------------------------------------------------------------------------

def test_t197s_1_preflight_result_has_all_pairs_p0_ok():
    from vapi_sdk import TournamentPreflightResult
    r = TournamentPreflightResult(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False,
    )
    assert r.all_pairs_p0_ok is False  # fail-closed default


# ---------------------------------------------------------------------------
# T197S-2: all_pairs_p0_ok=True sets correctly
# ---------------------------------------------------------------------------

def test_t197s_2_all_pairs_p0_ok_true():
    from vapi_sdk import TournamentPreflightResult
    r = TournamentPreflightResult(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True, all_pairs_p0_ok=True,
    )
    assert r.all_pairs_p0_ok is True
    assert r.overall_pass is True


# ---------------------------------------------------------------------------
# T197S-3: network error → all_pairs_p0_ok=False (fail-closed)
# ---------------------------------------------------------------------------

def test_t197s_3_network_error_all_pairs_fail_closed():
    from vapi_sdk import VAPITournamentPreflight
    pf = VAPITournamentPreflight("http://127.0.0.1:1", "key")
    result = pf.get_status()
    assert result.all_pairs_p0_ok is False  # fail-closed on error
    assert result.error is not None


# ---------------------------------------------------------------------------
# T197S-4: all_pairs_p0_ok=False blocks overall_pass
# ---------------------------------------------------------------------------

def test_t197s_4_all_pairs_false_blocks_overall():
    from vapi_sdk import TournamentPreflightResult
    r = TournamentPreflightResult(
        separation_ok=True,
        l4_ok=True,
        gate_ok=True,
        cert_ok=True,
        audit_ok=True,
        overall_pass=False,   # blocked by all_pairs_p0_ok
        biometric_ttl_ok=True,
        all_pairs_p0_ok=False,
    )
    assert r.all_pairs_p0_ok is False
    assert r.overall_pass is False
    assert r.biometric_ttl_ok is True  # other P0 still ok
