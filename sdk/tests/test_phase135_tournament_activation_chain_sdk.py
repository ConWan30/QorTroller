"""Phase 135 — TournamentActivationChainAgent SDK Tests (4 tests)"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "sdk"))

from vapi_sdk import (
    TournamentActivationChainResult,
    VAPITournamentActivationChain,
    SDK_VERSION,
)


def test_1_tournament_activation_chain_result_7_slots():
    r = TournamentActivationChainResult()
    assert r.gate_open_notified is False
    assert r.auto_activate_on_breakthrough is False  # PERMANENT INVARIANT
    assert r.operator_action_required is True
    assert r.last_ratio == 0.0
    assert r.last_notification_ts == 0.0
    assert r.notification_count == 0
    assert r.error is None


def test_2_vapi_tournament_activation_chain_init():
    client = VAPITournamentActivationChain(base_url="http://localhost:9999", api_key="k")
    assert client._base == "http://localhost:9999"
    assert client._key == "k"


def test_3_get_status_bad_url_never_raises():
    client = VAPITournamentActivationChain(base_url="http://localhost:19999", api_key="")
    result = client.get_status()
    assert isinstance(result, TournamentActivationChainResult)
    assert result.error is not None
    assert result.auto_activate_on_breakthrough is False  # invariant preserved even on error


def test_4_sdk_version_phase135():
    assert SDK_VERSION == "3.0.0-phase135"
