"""
Phase 151 SDK tests — CaptureGuidanceResult + VAPIEnrollmentCaptureGuidance (4 tests)
"""

import dataclasses
import sys
import pathlib

import pytest

_SDK = pathlib.Path(__file__).parents[2] / "sdk"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from vapi_sdk import (
    SDK_VERSION,
    CaptureGuidanceResult,
    VAPIEnrollmentCaptureGuidance,
)


class TestEnrollmentCaptureGuidanceSDK:

    def test_1_result_has_correct_slots(self):
        """CaptureGuidanceResult must have exactly 6 slots."""
        fields = {f.name for f in dataclasses.fields(CaptureGuidanceResult)}
        required = {
            "min_n_per_player",
            "probe_types",
            "guidance",
            "sessions_needed_total",
            "overall_ready",
            "error",
        }
        assert required == fields

    def test_2_client_init(self):
        """VAPIEnrollmentCaptureGuidance.__init__ must accept base_url and api_key."""
        client = VAPIEnrollmentCaptureGuidance(
            base_url="http://localhost:8080", api_key="test-key"
        )
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        """get_guidance must never raise — returns error-populated result on any exception."""
        client = VAPIEnrollmentCaptureGuidance(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_guidance(min_n=10)
        assert isinstance(result, CaptureGuidanceResult)
        assert result.overall_ready is False
        assert result.error is not None

    def test_4_sdk_version_is_phase151(self):
        """SDK_VERSION must be 3.0.0-phase166."""
        assert SDK_VERSION == "3.0.0-phase166"
