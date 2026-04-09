"""Phase 154 SDK tests — CaptureStagnationResult + VAPICaptureStagnationMonitor (4 tests)"""

import dataclasses, sys, pathlib
import pytest

_SDK = pathlib.Path(__file__).parents[2] / "sdk"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from vapi_sdk import SDK_VERSION, CaptureStagnationResult, VAPICaptureStagnationMonitor


class TestCaptureStagnationSDK:

    def test_1_result_has_correct_slots(self):
        fields = {f.name for f in dataclasses.fields(CaptureStagnationResult)}
        required = {"probe_type", "sessions_per_day", "stagnant", "sessions_in_window", "window_days", "error"}
        assert required == fields

    def test_2_client_init(self):
        client = VAPICaptureStagnationMonitor(base_url="http://localhost:8080", api_key="test-key")
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        client = VAPICaptureStagnationMonitor(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_stagnation_status()
        assert isinstance(result, CaptureStagnationResult)
        assert result.stagnant is True
        assert result.error is not None

    def test_4_defaults_on_error(self):
        client = VAPICaptureStagnationMonitor(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_stagnation_status(probe_type="touchpad_corners")
        assert result.probe_type == "touchpad_corners"
        assert result.sessions_per_day == 0.0
        assert result.sessions_in_window == 0
        assert result.window_days == 7.0
