"""Phase 109C — SDK IoSwarmAdjudicationResult + VAPISwarmAdjudication tests (4 tests).

Test plan:
  1. test_1_ioswarm_adjudication_result_slots — IoSwarmAdjudicationResult.__slots__ has 8 fields
  2. test_2_vapi_swarm_adjudication_init      — VAPISwarmAdjudication init without raising
  3. test_3_bad_url_returns_error             — get_adjudication_status() bad URL -> error != None
  4. test_4_error_defaults                   — error result -> ioswarm_adjudication_enabled=False,
                                               dual_veto_active=False, task_spec_registered=True
"""
from __future__ import annotations

import os
import sys

_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sdk.vapi_sdk import IoSwarmAdjudicationResult, VAPISwarmAdjudication  # noqa: E402


class TestIoSwarmAdjudicationResultSlots:

    def test_1_ioswarm_adjudication_result_slots(self):
        """IoSwarmAdjudicationResult.__slots__ has exactly 8 fields; all named fields present."""
        slots = IoSwarmAdjudicationResult.__slots__
        assert len(slots) == 8, f"Expected 8 slots, got {len(slots)}: {slots}"
        for field in (
            "ioswarm_adjudication_enabled",
            "classj_quorum_verdict",
            "triage_quorum_verdict",
            "dual_veto_active",
            "adjudication_count",
            "recent_blocks",
            "task_spec_registered",
            "error",
        ):
            assert field in slots, f"Missing slot: {field}"


class TestVAPISwarmAdjudicationInit:

    def test_2_vapi_swarm_adjudication_init(self):
        """VAPISwarmAdjudication initializes without raising."""
        client = VAPISwarmAdjudication("http://localhost:18081", "test-key-109c")
        assert client is not None
        assert hasattr(client, "get_adjudication_status")


class TestVAPISwarmAdjudicationErrorPath:

    def test_3_bad_url_returns_error(self):
        """get_adjudication_status() on unreachable URL (port 1) -> error != None."""
        client = VAPISwarmAdjudication("http://127.0.0.1:1", "test-key-109c")
        result = client.get_adjudication_status()
        assert isinstance(result, IoSwarmAdjudicationResult)
        assert result.error is not None

    def test_4_error_defaults(self):
        """Error result -> ioswarm_adjudication_enabled=False, dual_veto_active=False, task_spec_registered=True."""
        client = VAPISwarmAdjudication("http://127.0.0.1:1", "test-key-109c")
        result = client.get_adjudication_status()
        assert result.ioswarm_adjudication_enabled is False
        assert result.dual_veto_active is False
        assert result.task_spec_registered is True
        assert result.adjudication_count == 0
