"""Retina policy auto-arm on mock transport connect/disconnect."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bridge.vapi_bridge.retina_depin_policy import (
    get_runtime_policy_state,
    set_runtime_policy_state,
)


@pytest.fixture
def cfg():
    return SimpleNamespace(
        retina_perception_enabled=False,
        retina_policy_auto_arm=True,
        retina_fsca_cross_oracle_enabled=True,
        retina_adjudicator_context_enabled=True,
        retina_certified_edge_only=True,
        dualshock_enabled=True,
    )


@pytest.fixture
def store(tmp_path):
    from bridge.vapi_bridge.store import Store

    return Store(str(tmp_path / "policy_arm.db"))


def test_refresh_policy_arms_on_qualified_transport(cfg, store):
    from bridge.vapi_bridge.dualshock_integration import DualShockTransport

    ds = DualShockTransport.__new__(DualShockTransport)
    ds._cfg = cfg
    ds._store = store
    ds._is_sim_mode = False
    ds._retina_operator_disarmed = False
    ds._device_id = bytes.fromhex("ab" * 32)
    ds._pcc_monitor = MagicMock()
    ds._pcc_monitor.get_status.return_value = {
        "poll_rate_hz": 1002.0,
        "capture_state": "NOMINAL",
    }
    profile = SimpleNamespace(
        profile_id="sony_dualshock_edge_v1",
        phci_tier=SimpleNamespace(name="ATTESTED"),
        hid_vendor_id=0x054C,
        hid_product_ids=[0x0DF2],
    )
    ds._device_profile = profile

    set_runtime_policy_state(None)
    ds._refresh_retina_policy()

    state = get_runtime_policy_state()
    assert state is not None
    assert state.armed is True
    assert state.arm_source == "auto_edge_connect"
    assert state.effective_perception is True


def test_sim_mode_stays_unarmed(cfg, store):
    from bridge.vapi_bridge.dualshock_integration import DualShockTransport

    ds = DualShockTransport.__new__(DualShockTransport)
    ds._cfg = cfg
    ds._store = store
    ds._is_sim_mode = True
    ds._retina_operator_disarmed = False
    ds._pcc_monitor = None
    ds._device_profile = None

    set_runtime_policy_state(None)
    ds._refresh_retina_policy()

    state = get_runtime_policy_state()
    assert state is not None
    assert state.armed is False
