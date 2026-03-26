"""Phase 109A — ioSwarm SDK tests (4 tests).

Test plan:
  1. test_1_slots_count         — IoSwarmConsensusResult has exactly 9 __slots__
  2. test_2_init                — VAPISwarmStatus("http://...", "key") initializes
  3. test_3_bad_url_error       — get_status() bad URL -> result with error != None
  4. test_4_defaults_on_error   — error result has ioswarm_enabled=False, threshold=0.60
"""
from __future__ import annotations

import os
import sys

import pytest

_SDK = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

from sdk.vapi_sdk import IoSwarmConsensusResult, VAPISwarmStatus  # noqa: E402


class TestIoSwarmSDK:

    def test_1_slots_count(self):
        """IoSwarmConsensusResult must have exactly 9 __slots__ fields."""
        slots = IoSwarmConsensusResult.__slots__
        assert len(slots) == 9, f"Expected 9 slots, got {len(slots)}: {slots}"
        assert "ioswarm_enabled" in slots
        assert "quorum_threshold" in slots
        assert "block_quorum_threshold" in slots
        assert "consensus_count" in slots
        assert "configured_node_count" in slots
        assert "task_spec_registered" in slots
        assert "w3bstream_applets" in slots
        assert "vhp_auth_gate_address" in slots
        assert "error" in slots

    def test_2_init(self):
        """VAPISwarmStatus initializes without raising."""
        vs = VAPISwarmStatus("http://localhost:18080", "test-key")
        assert vs._base_url == "http://localhost:18080"
        assert vs._api_key == "test-key"

    def test_3_bad_url_error(self):
        """get_status() with bad URL returns result with error != None."""
        vs = VAPISwarmStatus("http://localhost:1", "key")
        result = vs.get_status()
        assert isinstance(result, IoSwarmConsensusResult)
        assert result.error is not None

    def test_4_defaults_on_error(self):
        """On error: ioswarm_enabled=False, quorum_threshold=0.60."""
        vs = VAPISwarmStatus("http://localhost:1", "key")
        result = vs.get_status()
        assert result.ioswarm_enabled is False
        assert result.quorum_threshold == pytest.approx(0.60, abs=0.01)
        assert result.block_quorum_threshold == pytest.approx(0.67, abs=0.01)
        assert result.task_spec_registered is True
