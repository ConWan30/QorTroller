"""ncaa_cfb_27 GameProfile tests (cfb27-r02 prereq item 4) - the 26->27 transfer is pinned honest.

Pins: the profile registers + resolves; R2-first L5 priority + L6-Passive R2 config are BYTE-EQUAL to
26 (the honest v1 - reorders wait for a 27 corpus); the D1 right-stick delta is annotated in the
button_map (the 26 dead-zone assumption must not silently transfer); 26 stays untouched.
"""
from bridge.vapi_bridge.game_profile import (
    NCAA_CFB_26,
    NCAA_CFB_27,
    get_profile,
    get_profile_or_none,
)


def test_cfb27_registers_and_resolves():
    p = get_profile("ncaa_cfb_27")
    assert p is NCAA_CFB_27
    assert p.display_name == "EA Sports College Football 27"
    assert p.platform == "ps5"
    assert get_profile_or_none("ncaa_cfb_27") is p


def test_cfb27_l5_priority_r2_first_and_equal_to_26():
    # honest v1: priority is sample sufficiency; R2 sprint verified still primary in 27
    assert NCAA_CFB_27.l5_button_priority[0] == "r2"
    assert NCAA_CFB_27.l5_button_priority == NCAA_CFB_26.l5_button_priority


def test_cfb27_l6_passive_config_transfers_from_26():
    for attr in ("l6_passive_enabled", "l6_passive_button", "l6_passive_ema_alpha",
                 "l6_passive_baseline_n", "l6_passive_flag_ratio"):
        assert getattr(NCAA_CFB_27, attr) == getattr(NCAA_CFB_26, attr), attr
    assert NCAA_CFB_27.l6_passive_button == "r2"


def test_cfb27_d1_right_stick_delta_annotated():
    # the 26 dead-zone assumption must NOT silently transfer - the map carries the D1 note
    rs = NCAA_CFB_27.button_map["r_stick"]
    assert "Tackle Stick" in rs
    assert "NOT dead-zone" in rs
    # and 26 is untouched (its r_stick note has no 27 language)
    assert "Tackle Stick" not in NCAA_CFB_26.button_map["r_stick"]


def test_cfb26_profile_byte_untouched_semantics():
    assert NCAA_CFB_26.profile_id == "ncaa_cfb_26"
    assert get_profile("ncaa_cfb_26") is NCAA_CFB_26
