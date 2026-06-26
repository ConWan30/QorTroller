"""Cycle-38 — agent #34 (LivePresenceSignalingAgent) dev-cert presence HUD enhancement.

Pure tests: the verdict->signal mapping (contested wins; human-side -> SELF_CERT_LIVE; inconsistent ->
DEGRADED; indeterminate -> abstain) and signal-vocabulary completeness (no KeyError at dispatch).
"""
from __future__ import annotations

from vapi_bridge.live_presence_signaling_agent import (
    _ANSI,
    _HAPTIC_MS,
    _LED,
    devcert_signal_for_verdict,
)


def test_human_verdicts_signal_self_cert_live():
    assert devcert_signal_for_verdict("CONSISTENT_HUMAN_VERIFIED_HARDWARE") == "DEVELOPER_SELF_CERT_LIVE"
    assert devcert_signal_for_verdict("CONSISTENT_HUMAN") == "DEVELOPER_SELF_CERT_LIVE"


def test_inconsistent_and_hwfail_signal_degraded():
    assert devcert_signal_for_verdict("INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE") == "PRESENCE_DEGRADED"
    assert devcert_signal_for_verdict("INCONSISTENT_PRESENCE_WITHOUT_TRAJECTORY") == "PRESENCE_DEGRADED"
    assert devcert_signal_for_verdict("HARDWARE_CLASS_FAIL") == "PRESENCE_DEGRADED"


def test_indeterminate_unverifiable_abstain():
    assert devcert_signal_for_verdict("INDETERMINATE") is None
    assert devcert_signal_for_verdict("UNVERIFIABLE") is None
    assert devcert_signal_for_verdict("") is None
    assert devcert_signal_for_verdict(None) is None


def test_contested_wins_over_human_verdict():
    # capture integrity precedes presence — a CONTESTED capture can't certify
    assert devcert_signal_for_verdict("CONSISTENT_HUMAN_VERIFIED_HARDWARE", contested=True) == "PRESENCE_CONTESTED"
    assert devcert_signal_for_verdict("INDETERMINATE", contested=True) == "PRESENCE_CONTESTED"


def test_new_signal_vocab_complete():
    # every new signal_type must have LED + haptic + ANSI entries (dispatch would KeyError otherwise)
    for s in ("DEVELOPER_SELF_CERT_LIVE", "PRESENCE_DEGRADED", "PRESENCE_CONTESTED"):
        assert s in _LED, f"{s} missing from _LED"
        assert s in _HAPTIC_MS, f"{s} missing from _HAPTIC_MS"
        assert s in _ANSI, f"{s} missing from _ANSI"
