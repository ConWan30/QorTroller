"""Tests for the controller hot-plug ReconnectPolicy (pure decision core)."""
from __future__ import annotations

from vapi_bridge.controller_reconnect_policy import ReconnectPolicy


def test_does_not_attempt_below_threshold():
    p = ReconnectPolicy(reconnect_after_failures=5)
    assert not p.should_attempt(0)
    assert not p.should_attempt(4)


def test_attempts_at_and_above_threshold():
    p = ReconnectPolicy(reconnect_after_failures=5)
    assert p.should_attempt(5)
    assert p.should_attempt(99)


def test_backoff_walks_schedule_then_caps():
    p = ReconnectPolicy(backoff_schedule=(5.0, 10.0, 30.0, 60.0))
    assert p.backoff_for_attempt(1) == 5.0
    assert p.backoff_for_attempt(2) == 10.0
    assert p.backoff_for_attempt(3) == 30.0
    assert p.backoff_for_attempt(4) == 60.0
    assert p.backoff_for_attempt(5) == 60.0     # caps at the last entry
    assert p.backoff_for_attempt(100) == 60.0   # indefinite retry at the cap


def test_backoff_handles_nonpositive_attempt():
    p = ReconnectPolicy(backoff_schedule=(5.0, 10.0))
    assert p.backoff_for_attempt(0) == 5.0
    assert p.backoff_for_attempt(-3) == 5.0


def test_empty_schedule_safe_default():
    p = ReconnectPolicy(backoff_schedule=())
    assert p.backoff_for_attempt(1) == 5.0


def test_custom_threshold():
    p = ReconnectPolicy(reconnect_after_failures=2)
    assert not p.should_attempt(1)
    assert p.should_attempt(2)
