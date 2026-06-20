"""Retina × W3bstream Phase 2 — mechanical validation test suite."""

from __future__ import annotations

import json

import pytest

from bridge.vapi_bridge.codec import POAC_RECORD_SIZE
from bridge.vapi_bridge.retina_state_commitment import compute_retina_state_commitment
from bridge.vapi_bridge.retina_w3bstream import (
    ANCHOR_CADENCE,
    EXIT_OK,
    EXIT_CADENCE,
    EXIT_PQ,
    EXIT_RETINA,
    _VALID_PQ_PLACEHOLDER,
    build_evm_log_payload,
    build_evm_log_payload_from_retina_row,
    resolve_sidecar_commitment,
    validate_evm_log_payload,
)


def _base_payload(**overrides):
    p = build_evm_log_payload(
        device_id="dev1",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        retina_state_commitment="bb" * 32,
        retina_w3bstream_enforce=False,
    )
    p.update(overrides)
    return p


def test_poac_record_size_unaltered_at_228():
    assert POAC_RECORD_SIZE == 228


def test_valid_payload_exit_ok():
    assert validate_evm_log_payload(_base_payload()) == EXIT_OK


def test_cadence_misaligned_exit_4():
    assert validate_evm_log_payload(_base_payload(block_number=65)) == EXIT_CADENCE


def test_invalid_pq_exit_5():
    assert validate_evm_log_payload(_base_payload(pq_commitment="0" * 64)) == EXIT_PQ


def test_enforce_retina_zero_exit_6():
    p = _base_payload(retina_state_commitment="", retina_w3bstream_enforce=True)
    assert validate_evm_log_payload(p) == EXIT_RETINA


def test_malformed_retina_hex_exit_6():
    p = _base_payload(retina_state_commitment="not-hex")
    assert validate_evm_log_payload(p) == EXIT_RETINA


def test_commitment_round_trip_row_payload():
    events = [{"type": "stick_radial_jump", "magnitude": 0.2}]
    commitment = compute_retina_state_commitment("dev1", 1_000_000, events)
    row = {
        "device_id": "dev1",
        "record_hash_hex": "cc" * 32,
        "state_commitment_hex": commitment,
    }
    payload = build_evm_log_payload_from_retina_row(row)
    assert payload["retina_state_commitment"] == commitment
    assert validate_evm_log_payload(payload) == EXIT_OK


def test_resolve_sidecar_rejects_zero_padded():
    ok, err = resolve_sidecar_commitment("0x" + "0" * 64)
    assert not ok
    assert err


def test_anchor_cadence_constant_matches_wasm():
    assert ANCHOR_CADENCE == 64


def test_payload_json_serializable():
    p = _base_payload()
    raw = json.dumps(p)
    assert "retina_state_commitment" in raw
