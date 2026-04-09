"""Phase 153 SDK tests — SeparationRatioRegistryResult + VAPISeparationRatioRegistry (4 tests)"""

import dataclasses, sys, pathlib
import pytest

_SDK = pathlib.Path(__file__).parents[2] / "sdk"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from vapi_sdk import SDK_VERSION, SeparationRatioRegistryResult, VAPISeparationRatioRegistry


class TestSeparationRatioRegistrySDK:

    def test_1_result_has_correct_slots(self):
        fields = {f.name for f in dataclasses.fields(SeparationRatioRegistryResult)}
        required = {"committed", "commit_hash", "ratio_millis", "n_sessions", "n_players", "error"}
        assert required == fields

    def test_2_client_init(self):
        client = VAPISeparationRatioRegistry(base_url="http://localhost:8080", api_key="test-key")
        assert client._base == "http://localhost:8080"
        assert client._key == "test-key"

    def test_3_never_raises_on_bad_url(self):
        client = VAPISeparationRatioRegistry(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_registry_status()
        assert isinstance(result, SeparationRatioRegistryResult)
        assert result.committed is False
        assert result.error is not None

    def test_4_defaults_on_error(self):
        client = VAPISeparationRatioRegistry(base_url="http://127.0.0.1:1", api_key="x")
        result = client.get_registry_status()
        assert result.commit_hash == ""
        assert result.ratio_millis == 0
        assert result.n_sessions == 0
        assert result.n_players == 0
