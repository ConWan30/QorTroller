"""
Phase 195 — PMIResult + VAPIProtocolMetabolism SDK tests.
"""
import pytest


# ---------------------------------------------------------------------------
# T195S-1: PMIResult dataclass construction
# ---------------------------------------------------------------------------

def test_t195s_1_pmi_result_construction():
    from vapi_sdk import PMIResult
    r = PMIResult(
        mean_resolution_hours=12.0,
        pmi_score=0.75,
        orphan_count_open=0,
        orphan_count_resolved=3,
        domain="all",
    )
    assert r.mean_resolution_hours == 12.0
    assert r.pmi_score == 0.75
    assert r.orphan_count_open == 0
    assert r.orphan_count_resolved == 3
    assert r.domain == "all"
    assert r.error is None


# ---------------------------------------------------------------------------
# T195S-2: PMIResult with error field
# ---------------------------------------------------------------------------

def test_t195s_2_pmi_result_error_field():
    from vapi_sdk import PMIResult
    r = PMIResult(
        mean_resolution_hours=0.0,
        pmi_score=1.0,
        orphan_count_open=0,
        orphan_count_resolved=0,
        domain="all",
        error="connection refused",
    )
    assert r.error == "connection refused"
    assert r.pmi_score == 1.0  # fail-open default


# ---------------------------------------------------------------------------
# T195S-3: VAPIProtocolMetabolism network error returns fail-open PMIResult
# ---------------------------------------------------------------------------

def test_t195s_3_network_error_fail_open():
    from vapi_sdk import VAPIProtocolMetabolism
    pmi = VAPIProtocolMetabolism("http://127.0.0.1:1", "test_key")
    result = pmi.get_status()
    assert result.pmi_score == 1.0
    assert result.error is not None


# ---------------------------------------------------------------------------
# T195S-4: ProtocolMaturityScoringResult has pmi_component slot
# ---------------------------------------------------------------------------

def test_t195s_4_maturity_scoring_result_has_pmi_slot():
    from vapi_sdk import ProtocolMaturityScoringResult
    r = ProtocolMaturityScoringResult(
        protocol_maturity_enabled=True,
        maturity_score=0.97,
        maturity_tier="PRODUCTION_CANDIDATE",
        separation_component=1.0,
        chain_integrity_component=1.0,
        consent_component=1.0,
        biometric_freshness_component=1.0,
        agent_calibration_component=1.0,
        enrollment_component=1.0,
        pmi_component=0.75,
    )
    assert r.pmi_component == 0.75
    assert r.maturity_score == 0.97
