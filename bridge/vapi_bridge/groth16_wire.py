"""Shared Groth16 BN254 wire-format codec and snarkjs/Node subprocess helpers.

These helpers were previously duplicated byte-for-byte across
``passport_prover.py``, ``pitl_prover.py`` and ``zk_sepproof_prover.py``.
They are gathered here so the single 256-byte ABI-packed proof layout and the
Node/snarkjs invocation logic live in one place.

The 256-byte layout matches ``abi.decode(proof, (uint256[2], uint256[2][2],
uint256[2]))``:

    [0:64]    pi_a  (a[0], a[1])
    [64:192]  pi_b  (b[0][0], b[0][1], b[1][0], b[1][1])
    [192:256] pi_c  (c[0], c[1])
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PROOF_SIZE = 256  # Groth16 BN254 uncompressed


def encode_proof(proof_json: dict) -> bytes:
    """Encode snarkjs proof.json → 256-byte ABI wire format."""
    def to_bytes32(v) -> bytes:
        n = int(v, 16) if str(v).startswith(("0x", "0X")) else int(v)
        return n.to_bytes(32, "big")

    buf = bytearray(PROOF_SIZE)
    buf[0:32]    = to_bytes32(proof_json["pi_a"][0])
    buf[32:64]   = to_bytes32(proof_json["pi_a"][1])
    buf[64:96]   = to_bytes32(proof_json["pi_b"][0][0])
    buf[96:128]  = to_bytes32(proof_json["pi_b"][0][1])
    buf[128:160] = to_bytes32(proof_json["pi_b"][1][0])
    buf[160:192] = to_bytes32(proof_json["pi_b"][1][1])
    buf[192:224] = to_bytes32(proof_json["pi_c"][0])
    buf[224:256] = to_bytes32(proof_json["pi_c"][1])
    return bytes(buf)


def decode_proof(proof_bytes: bytes) -> dict:
    """Decode 256-byte wire format → snarkjs proof.json structure."""
    def to_hex(b: bytes) -> str:
        return "0x" + b.hex()

    return {
        "pi_a": [to_hex(proof_bytes[0:32]),   to_hex(proof_bytes[32:64]),  "1"],
        "pi_b": [
            [to_hex(proof_bytes[64:96]),   to_hex(proof_bytes[96:128])],
            [to_hex(proof_bytes[128:160]), to_hex(proof_bytes[160:192])],
            ["1", "0"],
        ],
        "pi_c": [to_hex(proof_bytes[192:224]), to_hex(proof_bytes[224:256]), "1"],
        "protocol": "groth16",
        "curve":    "bn128",
    }


def run_node(script: str, args: list, capture_to=None, cwd=None) -> None:
    """Run a Node.js script, optionally capturing stdout to a file."""
    cmd = ["node", script] + list(args)
    if capture_to:
        with Path(capture_to).open("w") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, cwd=cwd, check=False)
    else:
        r = subprocess.run(cmd, capture_output=True, cwd=cwd, check=False)
    if r.returncode != 0:
        stderr = r.stderr.decode(errors="replace") if r.stderr else ""
        raise RuntimeError(f"Node.js helper failed: {stderr[:600]}")


def run_snarkjs(args: list, check: bool = True):
    """Run snarkjs via npx."""
    cmd = ["npx", "--yes", "snarkjs"] + args
    r = subprocess.run(cmd, capture_output=True, check=False)
    if check and r.returncode != 0:
        stderr = r.stderr.decode(errors="replace") if r.stderr else ""
        raise RuntimeError(f"snarkjs failed: {stderr[:600]}")
    return r
