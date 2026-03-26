"""Phase 109B — SDK IoSwarmRenewalResult + VAPISwarmRenewal tests (4 tests).

Test plan:
  1. test_1_ioswarm_renewal_result_slots  — IoSwarmRenewalResult.__slots__ has exactly 7 fields
  2. test_2_vapi_swarm_renewal_init       — VAPISwarmRenewal init without raising
  3. test_3_bad_url_returns_error         — get_renewal_status() bad URL -> error != None
  4. test_4_error_defaults                — error result -> ioswarm_renewal_enabled=False,
                                            min_quorum=3, task_spec_registered=True
"""
from __future__ import annotations

import os
import sys

# Sys-path bootstrap
_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sdk.vapi_sdk import IoSwarmRenewalResult, VAPISwarmRenewal  # noqa: E402


class TestIoSwarmRenewalResultSlots:

    def test_1_ioswarm_renewal_result_slots(self):
        """IoSwarmRenewalResult.__slots__ has exactly 7 fields; all named fields present."""
        slots = IoSwarmRenewalResult.__slots__
        assert len(slots) == 7, f"Expected 7 slots, got {len(slots)}: {slots}"
        for field in (
            "ioswarm_renewal_enabled", "min_quorum", "renewal_count",
            "task_spec_registered", "recent_approvals", "recent_skips", "error",
        ):
            assert field in slots, f"Missing slot: {field}"


class TestVAPISwarmRenewalInit:

    def test_2_vapi_swarm_renewal_init(self):
        """VAPISwarmRenewal initializes without raising."""
        client = VAPISwarmRenewal("http://localhost:18081", "test-key-109b")
        assert client is not None
        assert hasattr(client, "get_renewal_status")


class TestVAPISwarmRenewalErrorPath:

    def test_3_bad_url_returns_error(self):
        """get_renewal_status() on unreachable URL (port 1) -> error != None."""
        client = VAPISwarmRenewal("http://127.0.0.1:1", "test-key-109b")
        result = client.get_renewal_status()
        assert isinstance(result, IoSwarmRenewalResult)
        assert result.error is not None

    def test_4_error_defaults(self):
        """Error result -> ioswarm_renewal_enabled=False, min_quorum=3, task_spec_registered=True."""
        client = VAPISwarmRenewal("http://127.0.0.1:1", "test-key-109b")
        result = client.get_renewal_status()
        assert result.ioswarm_renewal_enabled is False
        assert result.min_quorum == 3
        assert result.task_spec_registered is True
        assert result.renewal_count == 0
