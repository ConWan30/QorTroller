"""Phase 184 SDK tests — PostCode Sweep (naming collision check + import gate).

2 tests:
  T184-SDK-1  PersonaBreakResult and MaturityElevationResult importable; no collision with prior SDK classes
  T184-SDK-2  VAPIPersonaBreakDetector and VAPIMaturityElevation importable; client classes distinct
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T184-SDK-1  Result classes importable; no collision with prior SDK classes
# ---------------------------------------------------------------------------

def test_t184_sdk_1_result_classes_no_collision():
    from vapi_sdk import (
        PersonaBreakResult,
        MaturityElevationResult,
        # Prior phases — confirm no name overwrite
        SeparationRatioRecoveryResult,
        ProtocolMaturityScoringResult,
        AgeWeightAnalysisResult,
    )

    # Confirm each is a distinct class
    classes = [
        PersonaBreakResult,
        MaturityElevationResult,
        SeparationRatioRecoveryResult,
        ProtocolMaturityScoringResult,
        AgeWeightAnalysisResult,
    ]
    assert len(set(id(c) for c in classes)) == len(classes), \
        "Name collision detected — two result classes share the same identity"

    # Confirm slot counts
    assert len(PersonaBreakResult.__slots__) == 6
    assert len(MaturityElevationResult.__slots__) == 7


# ---------------------------------------------------------------------------
# T184-SDK-2  Client classes importable and distinct
# ---------------------------------------------------------------------------

def test_t184_sdk_2_client_classes_distinct():
    from vapi_sdk import (
        VAPIPersonaBreakDetector,
        VAPIMaturityElevation,
        VAPISeparationRatioRecovery,
        VAPIProtocolMaturityScoring,
    )

    clients = [
        VAPIPersonaBreakDetector,
        VAPIMaturityElevation,
        VAPISeparationRatioRecovery,
        VAPIProtocolMaturityScoring,
    ]
    assert len(set(id(c) for c in clients)) == len(clients), \
        "Name collision detected — two client classes share the same identity"

    # Confirm VAPIPersonaBreakDetector accepts player_id keyword in get_status
    import inspect
    sig = inspect.signature(VAPIPersonaBreakDetector.get_status)
    assert "player_id" in sig.parameters
