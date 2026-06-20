"""CCO Phase A — read-only Controller Capability Oracle.

Wraps existing proto-CCO (``controller/profiles/``) behind a single pure
``CapabilityOracle.resolve()`` boundary. Output contract:
``wiki/methodology/CCO_PHASE_A_ORACLE_CONTRACT_v1.md``.

Extensions beyond the contract resolve signature (documented, not silent):
  - ``profile_id`` optional override — mirrors ``DEVICE_PROFILE_ID`` /
    Battle Beaver VID/PID collision (``054C:0DF2`` resolves to Edge first).
  - ``signing_path`` optional hint for ``identity_class`` (no chain I/O).

Rails: read-only, fail-open, no PoEP/L6B activation, no verdict issuance.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Contract constants (CCO_PHASE_A_ORACLE_CONTRACT_v1)
# ---------------------------------------------------------------------------

SCHEMA = "qortroller-capability-report-v1"
POLICY_REF = "CCO_T0_POLICY_v1_OPTION_C"
AS_OF = "2026-06-19"
T0_ENGINE = "L6B"
T2_T3_ENGINE = "POEP"
VERDICT_TYPES_AVAILABLE = ("REFLEX_OBSERVED",)

# Path B Arc 1 reference device (docs/path-a-manufacturing-spec.md)
PATH_B_DEMO_DEVICE_ID = (
    "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
)

_GENERIC_PROFILE_ID = "generic_unknown_v1"
_GENERIC_DISPLAY_NAME = "Unknown Controller"
_BUTTON_TIMING_PROFILE_IDS = frozenset({
    "hori_fighting_commander_ps5_v1",
    "xbox_elite_s2_v1",
})

_controller_dir = Path(__file__).resolve().parents[2] / "controller"
if str(_controller_dir) not in sys.path:
    sys.path.insert(0, str(_controller_dir))

from device_profile import ControllerFamily, DeviceProfile, PHCITier  # noqa: E402
from profiles import detect_profile, get_profile  # noqa: E402


def _load_chia_profile(profile_id: str) -> Any | None:
    """Optional CHIA canonical lookup — fail-open, read-only."""
    try:
        from .controller_hardware_intelligence_agent import get_canonical_profiles
    except ImportError:
        return None
    try:
        return get_canonical_profiles().get(profile_id)
    except Exception:
        return None


def _normalize_device_id(device_id_hex: str | None) -> str | None:
    if not device_id_hex:
        return None
    normalized = device_id_hex.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    return normalized or None


def _identity_class(
    device_id_hex: str | None,
    signing_path: Literal["A", "B"] | None,
) -> str:
    if signing_path == "A":
        return "I1_SILICON"
    device_id = _normalize_device_id(device_id_hex)
    if device_id is None:
        return "I0_SOFTWARE"
    if device_id == PATH_B_DEMO_DEVICE_ID:
        return "PATH_B_HOST_KEY"
    if signing_path == "B":
        return "PATH_B_HOST_KEY"
    return "I0_SOFTWARE"


def _characterization_status(profile: DeviceProfile, *, is_generic: bool) -> str:
    if is_generic:
        return "UNCHARACTERIZED"
    if profile.has_adaptive_triggers:
        return "PARTIAL_EDGE_ONLY"
    return "UNCHARACTERIZED"


def _presence_ceiling(profile: DeviceProfile, *, is_generic: bool) -> str:
    if is_generic:
        return "P-T0"
    if profile.has_adaptive_triggers:
        return "P-T3"
    if profile.has_gyroscope or profile.has_accelerometer:
        return "P-T1"
    return "P-T0"


def _challenge_type(profile: DeviceProfile, *, is_generic: bool) -> str:
    if is_generic:
        return "generic_input_timing"
    if profile.has_adaptive_triggers:
        return "adaptive_force"
    if profile.has_gyroscope or profile.has_accelerometer:
        return "rumble_imu"
    if profile.profile_id in _BUTTON_TIMING_PROFILE_IDS:
        return "button_timing"
    # No IMU, no adaptive triggers — sticks without IMU would be stick_timing
    # (future UNVALIDATED); V-check pins HORI/Xbox to button_timing.
    if profile.stick_resolution_bits > 8:
        return "stick_timing"
    return "button_timing"


def _capabilities_dict(profile: DeviceProfile, *, is_generic: bool) -> dict[str, Any]:
    if is_generic:
        return {
            "has_adaptive_triggers": False,
            "has_gyroscope": False,
            "has_accelerometer": False,
            "has_touchpad": False,
            "pitl_layers": [],
            "family": ControllerFamily.CUSTOM.name,
        }
    return {
        "has_adaptive_triggers": profile.has_adaptive_triggers,
        "has_gyroscope": profile.has_gyroscope,
        "has_accelerometer": profile.has_accelerometer,
        "has_touchpad": profile.has_touchpad,
        "pitl_layers": list(profile.pitl_layers),
        "family": profile.family.name,
    }


def _resolve_profile(
    vendor_id: int,
    product_id: int,
    profile_id: str | None,
) -> tuple[DeviceProfile | None, str, bool]:
    """Return (profile_or_none, detection_source, is_generic)."""
    if profile_id:
        try:
            return get_profile(profile_id), "vid_pid_registry", False
        except KeyError:
            return None, "generic_fallback", True
    detected = detect_profile(vendor_id, product_id)
    if detected is not None:
        return detected, "vid_pid_registry", False
    return None, "generic_fallback", True


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """Frozen output of ``CapabilityOracle.resolve()`` — contract v1."""

    schema: str
    vendor_id: int
    product_id: int
    profile_id: str
    display_name: str
    detection_source: str
    phci_tier: str
    capabilities: dict[str, Any]
    identity_class: str
    presence_ceiling_candidate: str
    characterization_status: str
    challenge_type_candidate: str
    t0_engine: str
    t2_t3_engine: str
    verdict_types_available: tuple[str, ...]
    policy_ref: str
    as_of: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["verdict_types_available"] = list(self.verdict_types_available)
        return data


class CapabilityOracle:
    """Read-only capability oracle — Phase A.1."""

    @staticmethod
    def resolve(
        vendor_id: int,
        product_id: int,
        *,
        device_id_hex: str | None = None,
        profile_id: str | None = None,
        signing_path: Literal["A", "B"] | None = None,
    ) -> CapabilityReport:
        profile, detection_source, is_generic = _resolve_profile(
            vendor_id, product_id, profile_id,
        )

        # CHIA enrichment: read-only lookup; contract fields from DeviceProfile.
        if profile is not None:
            _load_chia_profile(profile.profile_id)

        if is_generic:
            resolved_profile_id = _GENERIC_PROFILE_ID
            display_name = _GENERIC_DISPLAY_NAME
            phci_tier = PHCITier.NONE.name
            cap_profile = profile  # None — helpers use is_generic=True
        else:
            assert profile is not None
            resolved_profile_id = profile.profile_id
            display_name = profile.display_name
            phci_tier = profile.phci_tier.name
            cap_profile = profile

        return CapabilityReport(
            schema=SCHEMA,
            vendor_id=vendor_id,
            product_id=product_id,
            profile_id=resolved_profile_id,
            display_name=display_name,
            detection_source=detection_source,
            phci_tier=phci_tier,
            capabilities=_capabilities_dict(cap_profile or _placeholder_generic(), is_generic=is_generic),
            identity_class=_identity_class(device_id_hex, signing_path),
            presence_ceiling_candidate=_presence_ceiling(
                cap_profile or _placeholder_generic(), is_generic=is_generic,
            ),
            characterization_status=_characterization_status(
                cap_profile or _placeholder_generic(), is_generic=is_generic,
            ),
            challenge_type_candidate=_challenge_type(
                cap_profile or _placeholder_generic(), is_generic=is_generic,
            ),
            t0_engine=T0_ENGINE,
            t2_t3_engine=T2_T3_ENGINE,
            verdict_types_available=VERDICT_TYPES_AVAILABLE,
            policy_ref=POLICY_REF,
            as_of=AS_OF,
        )


def _placeholder_generic() -> DeviceProfile:
    """Minimal profile for generic-fallback derivation helpers."""
    return DeviceProfile(
        profile_id=_GENERIC_PROFILE_ID,
        display_name=_GENERIC_DISPLAY_NAME,
        manufacturer="",
        family=ControllerFamily.CUSTOM,
        phci_tier=PHCITier.NONE,
        hid_vendor_id=0,
        hid_product_ids=(),
        has_adaptive_triggers=False,
        has_gyroscope=False,
        has_accelerometer=False,
        has_touchpad=False,
        back_paddle_count=0,
        trigger_resolution_bits=8,
        stick_resolution_bits=8,
        schema_version=0,
        sensor_commitment_size_bytes=48,
        pitl_layers=(),
        certification_notes="",
    )
