"""CCO Phase B — L6B T0 wiring helpers.

Pure module: applicability gate, L6B→REFLEX_OBSERVED mapping, skip reasons.
Design: ``wiki/methodology/CCO_PHASE_B_DESIGN_v1.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

REFLEX_OBSERVED = "REFLEX_OBSERVED"
T0_ENGINE_L6B = "L6B"
HUMAN_CLASSIFICATION = "HUMAN"


class L6bSkipReason(str, Enum):
    NO_IMU = "NO_IMU"
    NO_ADAPTIVE_TRIGGER_PATH = "NO_ADAPTIVE_TRIGGER_PATH"
    NO_L6_DRIVER = "NO_L6_DRIVER"
    NO_DUALSENSE_HANDLE = "NO_DUALSENSE_HANDLE"
    T0_ENGINE_MISMATCH = "T0_ENGINE_MISMATCH"
    NO_CAPABILITY_REPORT = "NO_CAPABILITY_REPORT"


@dataclass(frozen=True, slots=True)
class L6bApplicability:
    applicable: bool
    skip_reason: L6bSkipReason | None = None


def check_l6b_applicability(
    report: Any | None,
    *,
    l6_driver_present: bool,
    dualsense_handle_present: bool,
) -> L6bApplicability:
    """Return whether the existing L6B stack may run for this session."""
    if report is None:
        return L6bApplicability(False, L6bSkipReason.NO_CAPABILITY_REPORT)
    if getattr(report, "t0_engine", None) != T0_ENGINE_L6B:
        return L6bApplicability(False, L6bSkipReason.T0_ENGINE_MISMATCH)
    caps = getattr(report, "capabilities", None) or {}
    if not caps.get("has_accelerometer", False):
        return L6bApplicability(False, L6bSkipReason.NO_IMU)
    if not caps.get("has_adaptive_triggers", False):
        return L6bApplicability(False, L6bSkipReason.NO_ADAPTIVE_TRIGGER_PATH)
    if not l6_driver_present:
        return L6bApplicability(False, L6bSkipReason.NO_L6_DRIVER)
    if not dualsense_handle_present:
        return L6bApplicability(False, L6bSkipReason.NO_DUALSENSE_HANDLE)
    return L6bApplicability(True)


def map_l6b_classification_to_reflex_verdict(classification: str) -> str | None:
    """Map L6b analyzer output to CCO telemetry verdict (non-gating)."""
    if classification == HUMAN_CLASSIFICATION:
        return REFLEX_OBSERVED
    return None


def format_l6b_skip_log(skip_reason: L6bSkipReason) -> str:
    return f"L6B_SKIPPED/{skip_reason.value}"
