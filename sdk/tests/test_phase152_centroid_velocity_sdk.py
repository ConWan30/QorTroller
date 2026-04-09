"""Phase 152 SDK tests — CentroidVelocityResult + VAPICentroidVelocityMonitor (4 tests)"""

import dataclasses, sys, pathlib
import pytest

_SDK = pathlib.Path(__file__).parents[2] / "sdk"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from vapi_sdk import SDK_VERSION, CentroidVelocityResult, VAPICentroidVelocityMonitor


class TestCentroidVelocitySDK:

    def test_1_result_has_correct_slots(self):
        fields = {f.name for f in dataclasses.fields(CentroidVelocityResult)}
        required = {"probe_type", "velocity", "velocity_per_day", "stagnant", "n_snapshots_used", "error"}
        assert required == fields

    def test_2_client_init(self):
        client = VAPICentroidVelocityMonitor(base_url="http://localhost:8080", api_key="test-key")
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        client = VAPICentroidVelocityMonitor(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_velocity_status(probe_type="touchpad_corners")
        assert isinstance(result, CentroidVelocityResult)
        assert result.stagnant is True
        assert result.error is not None

    def test_4_sdk_version_is_phase156(self):
        assert SDK_VERSION == "3.0.0-phase166"
