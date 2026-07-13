#!/usr/bin/env python3
"""
scripts/test_w3bstream_ingestion.py — W3bstream Ingestion Invariant Test and Verification

Enforces zero-trust execution boundaries:
1. Environment isolation: pops OPERATOR_PRIVATE_KEY from environment to prevent leakage.
2. Adheres to blockhash-driven temporal rules and cadence-alignment limits.
3. Retina Phase 2: mechanical retina_state_commitment validation (INV-W3S-006).
4. Contains zero screen-scraping, frame-grabbing, or optical capture.
"""

import os
import sys

# INV-W3S-002: Asserts clean environment isolation inside the Python ingestion listener
OPERATOR_PRIVATE_KEY = os.environ.pop('OPERATOR_PRIVATE_KEY', None)

ANCHOR_CADENCE = 64

# Repo root on path for bridge imports when run as script
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from bridge.vapi_bridge.retina_events_root import (  # noqa: E402
    compute_events_root_poseidon,
    set_poseidon_chain_fn,
)
from bridge.vapi_bridge.retina_state_commitment import compute_retina_state_commitment  # noqa: E402
from bridge.vapi_bridge.retina_w3bstream import (  # noqa: E402
    EXIT_OK,
    EXIT_CADENCE,
    EXIT_RETINA,
    EXIT_NODE_SESSION,
    _VALID_PQ_PLACEHOLDER,
    _VALID_NODE_ID_PLACEHOLDER,
    _VALID_SESSION_ROOT_PLACEHOLDER,
    build_evm_log_payload,
    resolve_node_session,
    validate_evm_log_payload,
)


def verify_cadence(block_number: int) -> bool:
    # INV-W3S-001: Enforces the W3bstream native Wasm cadence limit
    return block_number % ANCHOR_CADENCE == 0


def run_ingestion_test():
    print("=" * 60)
    print("Running W3bstream Ingestion Invariant Tests...")
    print("=" * 60)
    
    # Verify environment isolation (INV-W3S-002)
    if os.environ.get('OPERATOR_PRIVATE_KEY') is not None:
        print("[!] FAILURE: Environment isolation failed! OPERATOR_PRIVATE_KEY is still in env.")
        return False
    print("[+] Environment isolation verified (OPERATOR_PRIVATE_KEY popped).")
    
    # Test valid/invalid cadence (INV-W3S-001)
    test_cases = [
        (0, True),
        (64, True),
        (128, True),
        (1, False),
        (63, False),
        (65, False)
    ]
    
    for block_num, expected in test_cases:
        res = verify_cadence(block_num)
        if res != expected:
            print(f"[!] FAILURE: Cadence limit failed for block_number={block_num}. Expected {expected}, got {res}.")
            return False
            
    print("[+] W3bstream cadence verification passed.")

    # INV-W3S-006 — Retina sidecar mechanical validation
    events = [{"type": "trajectory_anomalous", "residual": 0.5}]

    def _mock_chain(elems):
        import hashlib
        import json as _json

        return hashlib.sha256(
            b"mock-poseidon-v1" + _json.dumps(elems, separators=(",", ":")).encode()
        ).digest()

    set_poseidon_chain_fn(_mock_chain)
    events_root = compute_events_root_poseidon(events).hex()
    retina_hex = compute_retina_state_commitment("device_edge", 42, events)
    ok_payload = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        retina_state_commitment=retina_hex,
        retina_w3bstream_enforce=True,
    )
    if validate_evm_log_payload(ok_payload) != EXIT_OK:
        print("[!] FAILURE: Valid retina+pQ payload rejected.")
        return False
    print("[+] Valid retina_state_commitment accepted.")

    bad_cadence = build_evm_log_payload(
        device_id="device_edge",
        block_number=65,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        retina_state_commitment=retina_hex,
        retina_w3bstream_enforce=True,
    )
    if validate_evm_log_payload(bad_cadence) != EXIT_CADENCE:
        print("[!] FAILURE: Misaligned cadence not rejected.")
        return False
    print("[+] Cadence rejection with retina field passed.")

    zero_retina = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        retina_state_commitment="",
        retina_w3bstream_enforce=True,
    )
    if validate_evm_log_payload(zero_retina) != EXIT_RETINA:
        print("[!] FAILURE: Zero retina under enforce did not return EXIT_RETINA.")
        return False
    print("[+] INV-W3S-006 zero-retina fail-closed passed.")

    verify_payload = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        events_root=events_root,
        retina_events=events,
        retina_events_root_verify=True,
    )
    if validate_evm_log_payload(verify_payload) != EXIT_OK:
        print("[!] FAILURE: events_root verify payload rejected.")
        return False
    print("[+] Phase 3 events_root mechanical verify passed.")

    # ------------------------------------------------------------------
    # DEPIN-1 LEG 2 — node_id + session_root mechanical gate (desk mirror)
    # Mechanical format/presence only; NOT a truth oracle.
    # ------------------------------------------------------------------
    # PASS: gate OFF + empty fields → byte-identical EXIT_OK (legacy path)
    legacy = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
    )
    if validate_evm_log_payload(legacy) != EXIT_OK:
        print("[!] FAILURE: legacy payload without node fields rejected.")
        return False
    print("[+] LEG2: legacy payload (node_session_verify default OFF) accepted.")

    # PASS: gate ON + well-formed node_id + session_root
    ok_node = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        node_id=_VALID_NODE_ID_PLACEHOLDER,
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    if validate_evm_log_payload(ok_node) != EXIT_OK:
        print("[!] FAILURE: valid node_session_verify payload rejected.")
        return False
    print("[+] LEG2: node_session_verify with valid node_id+session_root accepted.")

    # FAIL-CLOSED: gate ON + missing node_id
    missing_node = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        node_id="",
        session_root=_VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    if validate_evm_log_payload(missing_node) != EXIT_NODE_SESSION:
        print("[!] FAILURE: missing node_id under verify did not return EXIT_NODE_SESSION.")
        return False
    print("[+] LEG2: missing node_id fail-closed (exit 8).")

    # FAIL-CLOSED: gate ON + zero-padded session_root
    zero_root = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        node_id=_VALID_NODE_ID_PLACEHOLDER,
        session_root="0" * 64,
        node_session_verify=True,
    )
    if validate_evm_log_payload(zero_root) != EXIT_NODE_SESSION:
        print("[!] FAILURE: zero session_root under verify did not return EXIT_NODE_SESSION.")
        return False
    print("[+] LEG2: zero-padded session_root fail-closed (exit 8).")

    # FAIL-CLOSED: gate OFF but malformed nonempty node_id (garbage not ignored)
    garbage_node = build_evm_log_payload(
        device_id="device_edge",
        block_number=64,
        payload_hash="aa" * 32,
        signature="sig",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        node_id="not-a-hex-commitment",
        session_root="",
        node_session_verify=False,
    )
    if validate_evm_log_payload(garbage_node) != EXIT_NODE_SESSION:
        print("[!] FAILURE: malformed node_id (gate OFF) not rejected.")
        return False
    print("[+] LEG2: malformed nonempty node_id fail-closed even when gate OFF.")

    # resolve_node_session direct resolution shape
    res, err = resolve_node_session(
        _VALID_NODE_ID_PLACEHOLDER,
        _VALID_SESSION_ROOT_PLACEHOLDER,
        node_session_verify=True,
    )
    if err or not res.get("node_session_gate_ok"):
        print(f"[!] FAILURE: resolve_node_session happy path failed: {err!r} {res!r}")
        return False
    print("[+] LEG2: resolve_node_session resolution shape ok.")

    print("[SUCCESS] All W3bstream ingestion test conditions satisfied.")
    return True

if __name__ == "__main__":
    success = run_ingestion_test()
    sys.exit(0 if success else 1)
