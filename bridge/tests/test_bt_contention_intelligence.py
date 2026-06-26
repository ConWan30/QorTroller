"""BT-contention intelligence v1 (PCC-only) — cycle-39 module tests.

Pure tests for assess_contention (precedence: flap > contested > clear > unknown; benign/suspect lean) and
contention_to_presence_signal (contested -> PRESENCE_CONTESTED feeding agent #34).
"""
from __future__ import annotations

from vapi_bridge.bt_contention_intelligence import (
    AdversaryLean,
    ContentionState,
    assess_contention,
    contention_to_presence_signal,
)


def test_clear_uncontested():
    a = assess_contention(host_state="EXCLUSIVE_USB", poll_rate_cv=0.05)
    assert a.state is ContentionState.CLEAR
    assert a.lean is AdversaryLean.NONE
    assert a.contested is False
    assert contention_to_presence_signal(a) is None


def test_contested_suspect_when_unexplained():
    a = assess_contention(host_state="CONTESTED", streaming_source_active=False)
    assert a.state is ContentionState.CONTESTED_SUSPECT
    assert a.lean is AdversaryLean.SUSPECT
    assert a.contested is True
    assert contention_to_presence_signal(a) == "PRESENCE_CONTESTED"


def test_contested_benign_when_streaming_active():
    # Remote Play (a known streaming source) explains the contention -> benign lean (still gates)
    a = assess_contention(host_state="CONTESTED", streaming_source_active=True)
    assert a.state is ContentionState.CONTESTED_BENIGN
    assert a.lean is AdversaryLean.BENIGN
    assert a.contested is True


def test_cv_breach_drives_contention_without_host_label():
    a = assess_contention(host_state="EXCLUSIVE_USB", poll_rate_cv=0.55)
    assert a.contested is True
    assert a.state in (ContentionState.CONTESTED_SUSPECT, ContentionState.CONTESTED_BENIGN)
    # CV just below threshold stays clear
    b = assess_contention(host_state="EXCLUSIVE_USB", poll_rate_cv=0.39)
    assert b.state is ContentionState.CLEAR


def test_flapping_dominates_and_gates():
    a = assess_contention(host_state="EXCLUSIVE_USB", flap_count_in_window=2)
    assert a.state is ContentionState.FLAPPING
    assert a.contested is True
    # flap precedence: even with a streaming source + clean host, repeated detach wins
    b = assess_contention(host_state="CONTESTED", flap_count_in_window=3, streaming_source_active=True)
    assert b.state is ContentionState.FLAPPING
    # single transient detach is tolerated (below threshold)
    c = assess_contention(host_state="EXCLUSIVE_USB", flap_count_in_window=1)
    assert c.state is ContentionState.CLEAR


def test_degraded_or_missing_is_unknown_not_contested():
    # PCC owns the disconnect/degraded path; the contention gate abstains (never spurious-gates)
    for hs in ("DEGRADED", "DISCONNECTED", None, ""):
        a = assess_contention(host_state=hs)
        assert a.state is ContentionState.UNKNOWN
        assert a.contested is False
        assert contention_to_presence_signal(a) is None
