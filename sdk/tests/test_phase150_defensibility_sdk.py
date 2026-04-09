"""
Phase 150 SDK tests — SeparationDefensibilityResult + VAPISeparationDefensibility (4 tests)
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
    SeparationDefensibilityResult,
    VAPISeparationDefensibility,
)


class TestSeparationDefensibilitySDK:

    def test_1_result_has_correct_slots(self):
        """SeparationDefensibilityResult must have exactly 6 slots."""
        fields = {f.name for f in dataclasses.fields(SeparationDefensibilityResult)}
        required = {"defensible", "ratio", "n_per_player", "min_n_per_player",
                    "all_pairs_above_1", "error"}
        assert required == fields

    def test_2_client_init(self):
        """VAPISeparationDefensibility.__init__ must accept base_url and api_key."""
        client = VAPISeparationDefensibility(
            base_url="http://localhost:8080", api_key="test-key"
        )
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        """get_defensibility_status must never raise — returns error-populated result."""
        client = VAPISeparationDefensibility(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_defensibility_status(session_type="touchpad_corners")
        assert isinstance(result, SeparationDefensibilityResult)
        assert result.defensible is False
        assert result.error is not None

    def test_4_sdk_version_is_phase150(self):
        """SDK_VERSION must be 3.0.0-phase166 after Phase 151 bump."""
        assert SDK_VERSION == "3.0.0-phase166"
