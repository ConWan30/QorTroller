"""Tests for retina_state_commitment (W3bstream prep, off-chain)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.retina_state_commitment import (
    DOMAIN_TAG,
    compute_events_root,
    compute_retina_state_commitment,
)


def test_commitment_deterministic():
    events = [{"type": "controller.trigger.onset", "t": 1.0, "src": "d"}]
    a = compute_retina_state_commitment("ab" * 32, 123456789, events)
    b = compute_retina_state_commitment("ab" * 32, 123456789, events)
    assert a == b
    assert len(a) == 64


def test_events_root_order_independent():
    e1 = [{"type": "a", "t": 1}, {"type": "b", "t": 2}]
    e2 = [{"type": "b", "t": 2}, {"type": "a", "t": 1}]
    assert compute_events_root(e1) == compute_events_root(e2)


def test_commitment_changes_with_ts():
    events = [{"type": "controller.trajectory.anomalous", "t": 0.5}]
    dev = "cd" * 32
    assert compute_retina_state_commitment(dev, 1, events) != compute_retina_state_commitment(
        dev, 2, events
    )


def test_domain_tag_frozen():
    assert DOMAIN_TAG == b"VAPI-RETINA-STATE-v1"
