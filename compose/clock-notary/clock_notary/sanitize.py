"""Refuse biometric / truth-plane keys on the observation wire."""

from __future__ import annotations

FORBIDDEN_KEYS = frozenset(
    {
        "phi", "rumble_imu", "imu", "biometric", "ait", "poep", "poep_enabled",
        "present", "humanity", "eligibility", "wallet_key", "private_key", "nsec",
        "bridge_private_key",
    }
)
FORBIDDEN_PREFIXES = ("imu_", "bio_", "phi_", "poep_", "ait_")


def is_forbidden_key(key: str) -> bool:
    k = key.lower()
    if k in FORBIDDEN_KEYS:
        return True
    return any(k.startswith(p) for p in FORBIDDEN_PREFIXES)


def strip_truth_leaks(obj):
    if isinstance(obj, dict):
        return {k: strip_truth_leaks(v) for k, v in obj.items() if not is_forbidden_key(str(k))}
    if isinstance(obj, list):
        return [strip_truth_leaks(item) for item in obj]
    return obj
