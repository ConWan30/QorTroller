"""
Phase 126 — L4 Per-Battery Threshold Router.

Encapsulates per-battery threshold lookup logic for the live L4 gate.
Keeps the calling code (session_adjudicator, operator endpoints) clean
and ensures a single, testable routing path.

Usage:
    from vapi_bridge.l4_threshold_router import get_thresholds

    anomaly, continuity, source = get_thresholds(battery_type, store, cfg)
    # source is "per_battery" or "global_fallback"

W1 invariant: when l4_battery_threshold_enabled=False (the default) this
function ALWAYS returns the global fallback — infrastructure-first, zero
behavior change until the operator explicitly enables the feature.
"""

import logging

_log = logging.getLogger(__name__)


def get_thresholds(
    battery_type: str,
    store,
    cfg,
) -> "tuple[float, float, str]":
    """Return (anomaly_threshold, continuity_threshold, source) for a session.

    Parameters
    ----------
    battery_type : str
        Battery type string from the session (e.g. "touchpad", "trigger").
        Empty string or "unknown" always returns global_fallback.
    store : Store
        Bridge store instance — used to query l4_threshold_tracks.
    cfg :
        Bridge config — reads l4_battery_threshold_enabled,
        l4_anomaly_threshold, l4_continuity_threshold.

    Returns
    -------
    (anomaly_threshold, continuity_threshold, source) where source is
    "per_battery" or "global_fallback".

    This function never raises; any exception falls back to global defaults.
    """
    _global_anomaly: float = float(getattr(cfg, "l4_anomaly_threshold", 7.009))
    _global_continuity: float = float(getattr(cfg, "l4_continuity_threshold", 5.367))

    if not getattr(cfg, "l4_battery_threshold_enabled", False):
        return _global_anomaly, _global_continuity, "global_fallback"

    if not battery_type or battery_type == "unknown":
        _log.warning(
            "l4_threshold_router: battery_type='%s' — using global fallback thresholds",
            battery_type,
        )
        return _global_anomaly, _global_continuity, "global_fallback"

    try:
        tracks = store.get_l4_threshold_tracks(
            battery_type=battery_type, active_only=True
        )
    except Exception as exc:
        _log.warning(
            "l4_threshold_router: store error for battery_type='%s' — %s; "
            "using global fallback thresholds",
            battery_type,
            exc,
        )
        return _global_anomaly, _global_continuity, "global_fallback"

    if not tracks:
        _log.warning(
            "l4_threshold_router: no active track for battery_type='%s' — "
            "using global fallback thresholds (7.009 / 5.367)",
            battery_type,
        )
        return _global_anomaly, _global_continuity, "global_fallback"

    # Use the most-recently-inserted active track (last in list, or sort by id)
    track = max(tracks, key=lambda t: t.get("id", 0))
    anomaly = float(track.get("anomaly_threshold", _global_anomaly))
    continuity = float(track.get("continuity_threshold", _global_continuity))
    return anomaly, continuity, "per_battery"
