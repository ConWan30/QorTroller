"""Phase 133 SDK tests — IoSwarm PoAd Auto-Anchor. +4 (SDK 221 → 225)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import IoSwarmPoAdAnchorResult, VAPIIoSwarmPoAdAnchor, SDK_VERSION


def test_1_IoSwarmPoAdAnchorResult_6_slots():
    """IoSwarmPoAdAnchorResult has the 6 expected slot fields."""
    r = IoSwarmPoAdAnchorResult()
    assert r.poad_auto_anchor_enabled is False
    assert r.anchored_count == 0
    assert r.pending_count == 0
    assert r.dual_veto_count == 0
    assert r.anchor_failure_count == 0
    assert r.error is None


def test_2_init_no_raise():
    """VAPIIoSwarmPoAdAnchor instantiation never raises."""
    client = VAPIIoSwarmPoAdAnchor(base_url="http://localhost:8000", api_key="test")
    assert client is not None


def test_3_bad_url_returns_error_not_none():
    """get_anchor_status on unreachable URL returns error field, never raises."""
    client = VAPIIoSwarmPoAdAnchor(base_url="http://127.0.0.1:19999", api_key="")
    result = client.get_anchor_status()
    assert isinstance(result, IoSwarmPoAdAnchorResult)
    assert result.error is not None


def test_4_error_path_anchor_disabled():
    """On connection error the result has poad_auto_anchor_enabled=False and counts zero."""
    client = VAPIIoSwarmPoAdAnchor(base_url="http://127.0.0.1:19999", api_key="")
    result = client.get_anchor_status()
    assert result.poad_auto_anchor_enabled is False
    assert result.anchored_count == 0
    assert result.dual_veto_count == 0
    assert result.anchor_failure_count == 0
