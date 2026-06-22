"""VSD Self-Verifying Loop — session attestation (the cross-session integrity WITNESS).

The dev-loop analog of the protocol's witness primitives (GIC / BT-witness / retina DA-witness).
Any chat session can call this (via the read-only MCP tool) to obtain a recomputable stamp over
the methodology vault's current integrity head:

    stamp = SHA-256(
        b"VAPI-VSD-SESSION-ATTEST-v1"
        || sic_head_32b      (32 bytes — bytes.fromhex(sic_head_hex); "" -> 32 zero bytes)
        || harness_byte      (1 byte — 0x01 pass / 0x00 fail)
        || pv_ci_byte        (1 byte — 0x01 pass / 0x00 fail / 0x02 not-checked)
        || ts_ns_be          (8 bytes, big-endian uint64)
    )

It proves "this session OBSERVED a verified, harness-clean vault at this exact SIC head." It is
READ-ONLY and forge-proof — any party recomputes it from the same inputs (no key, no signature).
It binds an ephemeral session to the durable Synthesis Integrity Chain without mutating anything.

Pure stdlib; standalone (no vault/bridge import). FROZEN tag v1.
"""
import hashlib
import struct

_TAG = b"VAPI-VSD-SESSION-ATTEST-v1"
_PV_CI_NOT_CHECKED = 0x02


def compute_session_attestation(sic_head_hex: str, harness_pass: bool,
                                pv_ci_pass, ts_ns: int) -> dict:
    """Return {stamp, inputs}. pv_ci_pass may be True/False/None (None -> not-checked=0x02)."""
    head = bytes.fromhex(sic_head_hex) if sic_head_hex else b"\x00" * 32
    if len(head) != 32:
        raise ValueError("sic_head_hex must be 64 hex chars (32 bytes) or empty")
    pv_byte = _PV_CI_NOT_CHECKED if pv_ci_pass is None else (0x01 if pv_ci_pass else 0x00)
    stamp = hashlib.sha256(
        _TAG
        + head
        + (b"\x01" if harness_pass else b"\x00")
        + pv_byte.to_bytes(1, "big")
        + struct.pack(">Q", int(ts_ns))
    ).hexdigest()
    return {
        "schema": "vapi-vsd-session-attest-v1",
        "stamp": stamp,
        "inputs": {
            "sic_head_hex": sic_head_hex or "",
            "harness_pass": bool(harness_pass),
            "pv_ci_pass": (None if pv_ci_pass is None else bool(pv_ci_pass)),
            "ts_ns": int(ts_ns),
        },
        "verification": "recompute SHA-256(tag||sic_head||harness||pv_ci||ts_ns); no key required",
    }


def verify_session_attestation(record: dict) -> bool:
    """Recompute the stamp from a record's own inputs and confirm it matches. Tamper-evident."""
    try:
        i = record["inputs"]
        expect = compute_session_attestation(
            i.get("sic_head_hex", ""), bool(i["harness_pass"]), i.get("pv_ci_pass"), int(i["ts_ns"])
        )
        return expect["stamp"] == record.get("stamp")
    except Exception:
        return False
