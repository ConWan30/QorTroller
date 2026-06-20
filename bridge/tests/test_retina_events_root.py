"""Retina Phase 3 — Poseidon events_root tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bridge.vapi_bridge.retina_events_root import (
    EVENT_LINE_DOMAIN,
    canonical_event_lines,
    compute_events_root_poseidon,
    event_field_elements,
    event_line_to_field_element,
    events_root_hex,
    set_poseidon_chain_fn,
)
from bridge.vapi_bridge.retina_state_commitment import (
    DOMAIN_TAG,
    DOMAIN_TAG_V2,
    compute_events_root,
    compute_retina_state_commitment,
    compute_retina_state_commitment_v2,
)
from bridge.vapi_bridge.retina_w3bstream import (
    EXIT_EVENTS_ROOT,
    EXIT_OK,
    _VALID_PQ_PLACEHOLDER,
    build_evm_log_payload,
    validate_evm_log_payload,
    verify_events_root_recompute,
)

_ZK_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge" / "retina_zk_artifacts"
_NODE_SCRIPT = _ZK_DIR / "compute_retina_events_root.js"


def _mock_poseidon_chain(field_elements: list[int]) -> bytes:
    """Deterministic test double — not a real Poseidon permutation."""
    payload = json.dumps(field_elements, separators=(",", ":")).encode()
    return hashlib.sha256(b"mock-poseidon-v1" + payload).digest()


@pytest.fixture(autouse=True)
def _reset_poseidon_hook():
    set_poseidon_chain_fn(_mock_poseidon_chain)
    yield
    set_poseidon_chain_fn(None)


def test_canonical_event_lines_order_independent():
    e1 = [{"type": "a", "t": 1}, {"type": "b", "t": 2}]
    e2 = [{"type": "b", "t": 2}, {"type": "a", "t": 1}]
    assert canonical_event_lines(e1) == canonical_event_lines(e2)


def test_event_line_field_element_stable():
    line = '{"t":1,"type":"stick"}'
    a = event_line_to_field_element(line)
    b = event_line_to_field_element(line)
    assert a == b
    assert 0 <= a < 2**256


def test_poseidon_events_root_empty_events():
    root = compute_events_root_poseidon([])
    assert len(root) == 32
    assert events_root_hex(root) == root.hex()


def test_poseidon_events_root_changes_with_event():
    r1 = compute_events_root_poseidon([{"type": "a", "t": 1}])
    r2 = compute_events_root_poseidon([{"type": "b", "t": 2}])
    assert r1 != r2


def test_v1_and_v2_commitments_differ_for_same_inputs():
    events = [{"type": "trajectory_anomalous", "residual": 0.4}]
    dev = "ab" * 32
    ts = 99_000
    v1 = compute_retina_state_commitment(dev, ts, events)
    v2 = compute_retina_state_commitment_v2(dev, ts, events)
    assert v1 != v2


def test_v2_uses_poseidon_domain_tag():
    events = [{"type": "x", "t": 0}]
    dev = "cd" * 32
    ts = 1
    root = compute_events_root_poseidon(events)
    device_b = bytes.fromhex(dev)
    expected = hashlib.sha256(
        DOMAIN_TAG_V2 + device_b + ts.to_bytes(8, "big") + root
    ).hexdigest()
    assert compute_retina_state_commitment_v2(dev, ts, events) == expected


def test_v1_sha256_root_unchanged():
    events = [{"type": "a", "t": 1}, {"type": "b", "t": 2}]
    root = compute_events_root(events)
    assert len(root) == 32


def test_verify_events_root_recompute_ok():
    events = [{"type": "a", "t": 1}]
    root = events_root_hex(compute_events_root_poseidon(events))
    ok, err = verify_events_root_recompute(events, root)
    assert ok, err


def test_verify_events_root_recompute_mismatch():
    events = [{"type": "a", "t": 1}]
    ok, err = verify_events_root_recompute(events, "ff" * 32)
    assert not ok
    assert "mismatch" in err


def test_payload_events_root_verify_exit_7():
    events = [{"type": "a", "t": 1}]
    root = events_root_hex(compute_events_root_poseidon(events))
    bad = build_evm_log_payload(
        device_id="dev",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        events_root="00" * 32,
        retina_events=events,
        retina_events_root_verify=True,
    )
    assert validate_evm_log_payload(bad) == EXIT_EVENTS_ROOT
    good = build_evm_log_payload(
        device_id="dev",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        events_root=root,
        retina_events=events,
        retina_events_root_verify=True,
    )
    assert validate_evm_log_payload(good) == EXIT_OK


def test_event_field_elements_empty_is_zero():
    assert event_field_elements([]) == [0]


def test_line_domain_tag_frozen():
    assert EVENT_LINE_DOMAIN == b"VAPI-RETINA-EVENT-LINE-v1"


def test_v1_domain_tag_frozen():
    assert DOMAIN_TAG == b"VAPI-RETINA-STATE-v1"


@pytest.mark.skipif(not _NODE_SCRIPT.is_file(), reason="node helper missing")
def test_poseidon_helper_matches_mock_shape_via_node():
    """Optional live circomlibjs check when node + npm deps present."""
    node_modules = _ZK_DIR / "node_modules" / "circomlibjs"
    if not node_modules.is_dir():
        pytest.skip("circomlibjs not installed in retina_zk_artifacts")
    elems = event_field_elements([{"type": "golden", "t": 3}])
    payload = json.dumps({"field_elements": [str(x) for x in elems]})
    proc = subprocess.run(
        ["node", str(_NODE_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(_ZK_DIR),
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert len(out["events_root_hex"]) == 64
