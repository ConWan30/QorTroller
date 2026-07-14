"""A2A-DEPIN-1 LEG 2 (W3BSTREAM-VERIFY-1) — node_id + session_root mechanical gate.

Mechanical format/presence only (desk-mirrored in Python):
  - applet ASSERTs well-formed 64-hex when present / when gate armed
  - applet MUST NOT re-derive node_id or recompute session_root
  - node_session_verify default OFF → legacy payloads EXIT_OK
  - PV-CI 183 held (no new INV-W3S; same resolve_sidecar_commitment class)
"""
from __future__ import annotations

import json

from bridge.vapi_bridge.codec import POAC_RECORD_SIZE
from bridge.vapi_bridge.retina_w3bstream import (
    EXIT_OK,
    EXIT_NODE_SESSION,
    _VALID_NODE_ID_PLACEHOLDER,
    _VALID_PQ_PLACEHOLDER,
    _VALID_SESSION_ROOT_PLACEHOLDER,
    build_evm_log_payload,
    resolve_node_session,
    resolve_sidecar_commitment,
    validate_evm_log_payload,
)


def _base(**overrides):
    p = build_evm_log_payload(
        device_id="dev1",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
    )
    p.update(overrides)
    return p


def test_t_depin1_w3s_1_legacy_payload_byte_identical_ok():
    """node_session_verify default OFF + empty fields → EXIT_OK (today's path)."""
    assert validate_evm_log_payload(_base()) == EXIT_OK
    assert _base()["node_session_verify"] is False
    assert _base()["node_id"] == ""
    assert _base()["session_root"] == ""


def test_t_depin1_w3s_2_verify_on_valid_pair_ok():
    p = _base(
        node_id=_VALID_NODE_ID_PLACEHOLDER,
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    assert validate_evm_log_payload(p) == EXIT_OK


def test_t_depin1_w3s_3_verify_on_missing_node_id_fail_closed():
    p = _base(
        node_id="",
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    assert validate_evm_log_payload(p) == EXIT_NODE_SESSION


def test_t_depin1_w3s_4_verify_on_missing_session_root_fail_closed():
    p = _base(
        node_id=_VALID_NODE_ID_PLACEHOLDER,
        session_root="",
        node_session_verify=True,
    )
    assert validate_evm_log_payload(p) == EXIT_NODE_SESSION


def test_t_depin1_w3s_5_verify_on_zero_padded_fail_closed():
    p = _base(
        node_id="0" * 64,
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    assert validate_evm_log_payload(p) == EXIT_NODE_SESSION


def test_t_depin1_w3s_6_malformed_nonempty_gate_off_fail_closed():
    """Garbage not ignored when field is present (even if gate OFF)."""
    p = _base(node_id="zzzz", node_session_verify=False)
    assert validate_evm_log_payload(p) == EXIT_NODE_SESSION


def test_t_depin1_w3s_7_resolve_node_session_shape():
    res, err = resolve_node_session(
        _VALID_NODE_ID_PLACEHOLDER,
        _VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    assert err == ""
    assert res["node_id_valid"] is True
    assert res["session_root_valid"] is True
    assert res["node_session_gate_ok"] is True


def test_t_depin1_w3s_8_not_a_truth_oracle():
    """Well-formed hex that is NOT a real derived node_id still PASSES format gate.

    Honesty rail: mechanical verify ≠ re-derive. A fabricated but well-formed
    64-hex is accepted at this layer (truth lives in leg-1 recompute / leg-3 ledger).
    """
    fake_but_well_formed = "11" * 32
    # Not equal to a known real derivation — still format-valid
    ok, _ = resolve_sidecar_commitment(fake_but_well_formed)
    assert ok is True
    p = _base(
        node_id=fake_but_well_formed,
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    assert validate_evm_log_payload(p) == EXIT_OK


def test_t_depin1_w3s_9_poac_wire_untouched():
    assert POAC_RECORD_SIZE == 228


def test_t_depin1_w3s_10_payload_json_carries_spine_keys():
    p = _base(
        node_id=_VALID_NODE_ID_PLACEHOLDER,
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    raw = json.dumps(p)
    assert "node_id" in raw
    assert "session_root" in raw
    assert "node_session_verify" in raw
    assert EXIT_NODE_SESSION == 8
