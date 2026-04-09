"""Phase 156 SDK tests — EnrollmentAutoGuidanceResult + VAPIEnrollmentAutoGuidance (4 tests)"""

import dataclasses, sys, pathlib
import pytest

_SDK = pathlib.Path(__file__).parents[2] / "sdk"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from vapi_sdk import SDK_VERSION, EnrollmentAutoGuidanceResult, VAPIEnrollmentAutoGuidance


class TestEnrollmentAutoGuidanceSDK:

    def test_1_result_has_correct_slots(self):
        fields = {f.name for f in dataclasses.fields(EnrollmentAutoGuidanceResult)}
        required = {"sessions_needed_total", "overall_ready", "recommended_action",
                    "urgency_level", "estimated_days", "cov_regime_status", "error"}
        assert required == fields

    def test_2_client_init(self):
        client = VAPIEnrollmentAutoGuidance(base_url="http://localhost:8080", api_key="test-key")
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        client = VAPIEnrollmentAutoGuidance(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_guidance_status()
        assert isinstance(result, EnrollmentAutoGuidanceResult)
        assert result.overall_ready is False
        assert result.error is not None

    def test_4_defaults_on_error(self):
        client = VAPIEnrollmentAutoGuidance(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_guidance_status()
        assert result.sessions_needed_total == 0
        assert result.urgency_level == "UNKNOWN"
        assert result.estimated_days == -1.0
        assert result.recommended_action == "Run EnrollmentAutoGuidanceAgent"
