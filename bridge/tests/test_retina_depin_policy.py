"""Retina DePIN Policy Governor — qualifier and effective-flag tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.retina_depin_policy import (
    RetinaPolicyState,
    TransportSnapshot,
    evaluate_prerequisites,
    is_effective_adjudicator,
    is_effective_fsca,
    is_effective_perception,
    resolve_effective_flags,
    set_runtime_policy_state,
)


def _cfg(**kwargs):
    defaults = {
        "retina_perception_enabled": False,
        "retina_policy_auto_arm": True,
        "retina_fsca_cross_oracle_enabled": True,
        "retina_adjudicator_context_enabled": True,
        "retina_certified_edge_only": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _edge_snap(**kwargs):
    base = dict(
        is_sim_mode=False,
        dualshock_enabled=True,
        transport_running=True,
        profile_id="sony_dualshock_edge_v1",
        phci_tier="ATTESTED",
        hid_vendor_id=0x054C,
        hid_product_id=0x0DF2,
        poll_rate_hz=1002.0,
        capture_state="NOMINAL",
        device_id_hex="ab" * 32,
        trio_retina_importable=True,
        operator_disarmed=False,
    )
    base.update(kwargs)
    return TransportSnapshot(**base)


class TestRetinaDepinPolicy:
    def test_sim_mode_blocks_auto_arm(self):
        snap = _edge_snap(is_sim_mode=True)
        state = evaluate_prerequisites(_cfg(), snap)
        assert state.armed is False
        assert state.arm_source == "unarmed"
        assert state.qualifiers["Q-HW"].startswith("FAIL")

    def test_edge_qualifiers_pass_auto_arm(self):
        snap = _edge_snap()
        state = evaluate_prerequisites(_cfg(), snap)
        assert state.armed is True
        assert state.arm_source == "auto_edge_connect"
        assert state.effective_perception is True

    def test_manual_override_bypasses_qualifiers(self):
        snap = _edge_snap(is_sim_mode=True, poll_rate_hz=0)
        state = evaluate_prerequisites(_cfg(retina_perception_enabled=True), snap)
        assert state.armed is True
        assert state.arm_source == "manual"
        assert state.effective_perception is True

    def test_operator_disarm_blocks_auto(self):
        snap = _edge_snap(operator_disarmed=True)
        state = evaluate_prerequisites(_cfg(), snap)
        assert state.armed is False
        assert state.arm_source == "operator_disarm"

    def test_poll_rate_fail_blocks_arm(self):
        snap = _edge_snap(poll_rate_hz=250.0)
        state = evaluate_prerequisites(_cfg(), snap)
        assert state.armed is False
        assert state.qualifiers["Q-POLL"].startswith("FAIL")

    def test_certified_edge_only_blocks_standard_profile(self):
        snap = _edge_snap(profile_id="sony_dualsense_v1", phci_tier="STANDARD")
        state = evaluate_prerequisites(_cfg(retina_certified_edge_only=True), snap)
        assert state.armed is False
        assert state.qualifiers["Q-EDGE"].startswith("FAIL")

    def test_effective_fsca_respects_layer_flag(self):
        state = RetinaPolicyState(armed=True, arm_source="auto_edge_connect")
        state = resolve_effective_flags(_cfg(retina_fsca_cross_oracle_enabled=False), state)
        state.effective_perception = True
        assert is_effective_fsca(_cfg(retina_fsca_cross_oracle_enabled=False)) is False

    def test_runtime_state_effective_perception(self):
        set_runtime_policy_state(
            RetinaPolicyState(
                armed=True,
                arm_source="auto_edge_connect",
                effective_perception=True,
            )
        )
        assert is_effective_perception(_cfg()) is True
        set_runtime_policy_state(None)

    def test_effective_adjudicator_follows_perception(self):
        set_runtime_policy_state(
            RetinaPolicyState(
                armed=True,
                effective_perception=True,
                effective_adjudicator=True,
            )
        )
        assert is_effective_adjudicator(_cfg()) is True
        set_runtime_policy_state(None)
