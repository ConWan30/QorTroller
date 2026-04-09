"""Phase 155 SDK tests — ControllerHardwareResult + VAPIControllerHardware (4 tests)"""

import dataclasses, sys, pathlib
import pytest

_SDK = pathlib.Path(__file__).parents[2] / "sdk"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from vapi_sdk import SDK_VERSION, ControllerHardwareResult, VAPIControllerHardware


class TestControllerHardwareSDK:

    def test_1_result_has_correct_slots(self):
        fields = {f.name for f in dataclasses.fields(ControllerHardwareResult)}
        required = {"controller_intelligence_enabled", "multi_controller_enabled",
                    "attested_count", "standard_count", "active_composite_key", "error"}
        assert required == fields

    def test_2_client_init(self):
        client = VAPIControllerHardware(base_url="http://localhost:8080", api_key="test-key")
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        client = VAPIControllerHardware(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_hardware_status()
        assert isinstance(result, ControllerHardwareResult)
        assert result.attested_count == 0
        assert result.error is not None

    def test_4_defaults_on_error(self):
        client = VAPIControllerHardware(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_hardware_status()
        assert result.controller_intelligence_enabled is True
        assert result.multi_controller_enabled is False
        assert result.active_composite_key == ""
        assert result.standard_count == 0
