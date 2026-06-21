"""CCO Phase A — CapabilityOracle V-check tests.

Contract table: wiki/methodology/CCO_PHASE_A_ORACLE_CONTRACT_v1.md §V-check.
Any deviation from expected outputs is surfaced as F-PHASE-A-VCHECK finding.
"""
from __future__ import annotations

import pytest

from bridge.vapi_bridge.capability_oracle import (
    AS_OF,
    PATH_B_DEMO_DEVICE_ID,
    POLICY_REF,
    SCHEMA,
    T0_ENGINE,
    T2_T3_ENGINE,
    VERDICT_TYPES_AVAILABLE,
    CapabilityOracle,
    CapabilityReport,
    resolve_capability_hardware_ids,
)

_CONTRACT_FIELDS = frozenset({
    "schema",
    "vendor_id",
    "product_id",
    "profile_id",
    "display_name",
    "detection_source",
    "phci_tier",
    "capabilities",
    "identity_class",
    "presence_ceiling_candidate",
    "characterization_status",
    "challenge_type_candidate",
    "t0_engine",
    "t2_t3_engine",
    "verdict_types_available",
    "policy_ref",
    "as_of",
})

_CAPABILITY_KEYS = frozenset({
    "has_adaptive_triggers",
    "has_gyroscope",
    "has_accelerometer",
    "has_touchpad",
    "pitl_layers",
    "family",
})

# V-check rows: (label, resolve kwargs, expected subset)
_VCHECK_ROWS = [
    (
        "edge",
        {"vendor_id": 0x054C, "product_id": 0x0DF2},
        {
            "profile_id": "sony_dualshock_edge_v1",
            "presence_ceiling_candidate": "P-T3",
            "challenge_type_candidate": "adaptive_force",
            "characterization_status": "PARTIAL_EDGE_ONLY",
            "detection_source": "vid_pid_registry",
        },
    ),
    (
        "dualsense",
        {"vendor_id": 0x054C, "product_id": 0x0CE6},
        {
            "profile_id": "sony_dualsense_v1",
            "presence_ceiling_candidate": "P-T1",
            "challenge_type_candidate": "rumble_imu",
            "characterization_status": "UNCHARACTERIZED",
        },
    ),
    (
        "scuf",
        {"vendor_id": 0x2F24, "product_id": 0x0011},
        {
            "profile_id": "scuf_reflex_pro_v1",
            "presence_ceiling_candidate": "P-T1",
            "challenge_type_candidate": "rumble_imu",
            "characterization_status": "UNCHARACTERIZED",
        },
    ),
    (
        "hori",
        {"vendor_id": 0x0F0D, "product_id": 0x0133},
        {
            "profile_id": "hori_fighting_commander_ps5_v1",
            "presence_ceiling_candidate": "P-T0",
            "challenge_type_candidate": "button_timing",
            "characterization_status": "UNCHARACTERIZED",
        },
    ),
    (
        "xbox_elite_s2",
        {"vendor_id": 0x045E, "product_id": 0x0B00},
        {
            "profile_id": "xbox_elite_s2_v1",
            "presence_ceiling_candidate": "P-T0",
            "challenge_type_candidate": "button_timing",
            "characterization_status": "UNCHARACTERIZED",
        },
    ),
    (
        "battle_beaver",
        {
            "vendor_id": 0x054C,
            "product_id": 0x0DF2,
            "profile_id": "battle_beaver_dualshock_edge_v1",
        },
        {
            "profile_id": "battle_beaver_dualshock_edge_v1",
            "presence_ceiling_candidate": "P-T3",
            "challenge_type_candidate": "adaptive_force",
            "characterization_status": "PARTIAL_EDGE_ONLY",
        },
    ),
    (
        "unknown",
        {"vendor_id": 0xFFFF, "product_id": 0xFFFF},
        {
            "profile_id": "generic_unknown_v1",
            "display_name": "Unknown Controller",
            "presence_ceiling_candidate": "P-T0",
            "challenge_type_candidate": "generic_input_timing",
            "detection_source": "generic_fallback",
            "phci_tier": "NONE",
        },
    ),
]


def _assert_vcheck(label: str, report: CapabilityReport, expected: dict) -> None:
    for key, want in expected.items():
        got = getattr(report, key)
        if got != want:
            pytest.fail(
                f"F-PHASE-A-VCHECK [{label}] {key}: expected {want!r}, got {got!r}"
            )


@pytest.mark.parametrize("label,kwargs,expected", _VCHECK_ROWS)
def test_vcheck_contract_table(label, kwargs, expected):
    report = CapabilityOracle.resolve(**kwargs)
    _assert_vcheck(label, report, expected)


def test_report_has_all_contract_fields():
    report = CapabilityOracle.resolve(0x054C, 0x0DF2)
    assert set(report.to_dict().keys()) == _CONTRACT_FIELDS


def test_to_dict_round_trip():
    report = CapabilityOracle.resolve(0x054C, 0x0DF2)
    d = report.to_dict()
    assert d["schema"] == SCHEMA
    assert d["policy_ref"] == POLICY_REF
    assert d["as_of"] == AS_OF
    assert d["t0_engine"] == T0_ENGINE
    assert d["t2_t3_engine"] == T2_T3_ENGINE
    assert d["verdict_types_available"] == list(VERDICT_TYPES_AVAILABLE)


def test_capabilities_object_shape():
    report = CapabilityOracle.resolve(0x054C, 0x0DF2)
    assert set(report.capabilities.keys()) == _CAPABILITY_KEYS
    assert report.capabilities["has_adaptive_triggers"] is True


def test_identity_class_default_i0_software():
    report = CapabilityOracle.resolve(0x054C, 0x0DF2)
    assert report.identity_class == "I0_SOFTWARE"


def test_identity_class_path_b_demo_device():
    report = CapabilityOracle.resolve(
        0x054C, 0x0DF2, device_id_hex=PATH_B_DEMO_DEVICE_ID,
    )
    assert report.identity_class == "PATH_B_HOST_KEY"


def test_identity_class_path_b_demo_device_with_0x_prefix():
    report = CapabilityOracle.resolve(
        0x054C, 0x0DF2, device_id_hex=f"0x{PATH_B_DEMO_DEVICE_ID}",
    )
    assert report.identity_class == "PATH_B_HOST_KEY"


def test_identity_class_i1_silicon_signing_path_a():
    report = CapabilityOracle.resolve(0x054C, 0x0DF2, signing_path="A")
    assert report.identity_class == "I1_SILICON"


def test_identity_class_path_b_signing_path_b_with_device():
    report = CapabilityOracle.resolve(
        0x054C, 0x0DF2,
        device_id_hex="a" * 64,
        signing_path="B",
    )
    assert report.identity_class == "PATH_B_HOST_KEY"


def test_identity_class_signing_path_b_without_device_id_is_i0_software():
    report = CapabilityOracle.resolve(0x054C, 0x0DF2, signing_path="B")
    assert report.identity_class == "I0_SOFTWARE"


def test_invalid_profile_id_falls_back_generic():
    report = CapabilityOracle.resolve(
        0x054C, 0x0DF2, profile_id="nonexistent_profile_v99",
    )
    assert report.profile_id == "generic_unknown_v1"
    assert report.detection_source == "generic_fallback"


def test_edge_vid_pid_beats_battle_beaver_without_override():
    """054C:0DF2 without profile_id must resolve to Edge, not Battle Beaver."""
    report = CapabilityOracle.resolve(0x054C, 0x0DF2)
    assert report.profile_id == "sony_dualshock_edge_v1"


def test_resolve_hardware_ids_from_cco_profile_id():
    class _Cfg:
        device_profile_id = ""
        auto_detect_device = False

    vid, pid, hint = resolve_capability_hardware_ids(
        _Cfg(),
        cco_profile_id="sony_dualsense_v1",
        controller_connected=False,
    )
    assert vid == 0x054C
    assert pid == 0x0CE6
    assert hint == "sony_dualsense_v1"
    report = CapabilityOracle.resolve(vid, pid, profile_id=hint)
    assert report.challenge_type_candidate == "rumble_imu"
