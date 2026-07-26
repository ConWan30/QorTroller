"""
Phase 56 — PassportProver tests (mock proof path + wire codec).

The Groth16 artifacts are absent in CI, so the prover runs its mock path; these
tests pin the input validation (N=5 sessions, humanity >= 60%), the mock wire
layout, and the 256-byte proof encode/decode round trip that both paths share.
"""
import hashlib
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.passport_prover import (
    HUMANITY_SCALE,
    MIN_HUMANITY,
    PROOF_SIZE,
    SESSION_COUNT,
    PassportProver,
    _decode_proof,
    _encode_proof,
)

_NULLIFIERS = [str(1000 + i) for i in range(SESSION_COUNT)]
_HUMANITYS = [0.82, 0.75, 0.91, 0.64, 0.70]


def _mock_prover():
    """Prover forced onto the mock path (nonexistent artifact paths)."""
    return PassportProver(
        wasm_path="/nonexistent/TournamentPassport.wasm",
        zkey_path="/nonexistent/TournamentPassport_final.zkey",
        vkey_path="/nonexistent/TournamentPassport_verification_key.json",
    )


class TestGenerateProofValidation(unittest.TestCase):

    def test_wrong_nullifier_count_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            _mock_prover().generate_proof(_NULLIFIERS[:4], _HUMANITYS, "aa" * 32)
        self.assertIn("nullifiers", str(ctx.exception))

    def test_wrong_humanity_count_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            _mock_prover().generate_proof(_NULLIFIERS, _HUMANITYS[:3], "aa" * 32)
        self.assertIn("humanitys", str(ctx.exception))

    def test_humanity_below_threshold_rejected(self):
        low = [0.82, 0.75, 0.91, 0.59, 0.70]
        with self.assertRaises(ValueError):
            _mock_prover().generate_proof(_NULLIFIERS, low, "aa" * 32)

    def test_humanity_exactly_at_threshold_accepted(self):
        at_threshold = [MIN_HUMANITY / HUMANITY_SCALE] * SESSION_COUNT
        _, _, min_hp = _mock_prover().generate_proof(_NULLIFIERS, at_threshold, "aa" * 32)
        self.assertEqual(min_hp, MIN_HUMANITY)

    def test_humanity_above_one_is_clamped(self):
        _, _, min_hp = _mock_prover().generate_proof(
            _NULLIFIERS, [1.5] * SESSION_COUNT, "aa" * 32
        )
        self.assertEqual(min_hp, HUMANITY_SCALE)


class TestMockProof(unittest.TestCase):

    def test_wire_layout(self):
        prover = _mock_prover()
        proof, passport_hash, min_hp = prover.generate_proof(
            _NULLIFIERS, _HUMANITYS, "aa" * 32
        )
        self.assertEqual(len(proof), PROOF_SIZE)
        self.assertEqual(len(passport_hash), 32)
        self.assertEqual(min_hp, 640)
        self.assertEqual(proof[0:32], passport_hash)
        self.assertEqual(struct.unpack(">H", proof[32:34])[0], min_hp)
        self.assertEqual(proof[34:], b"\x00" * (PROOF_SIZE - 34))

    def test_passport_hash_is_sha256_of_nullifiers(self):
        _, passport_hash, _ = _mock_prover().generate_proof(
            _NULLIFIERS, _HUMANITYS, "aa" * 32
        )
        expected = hashlib.sha256(
            b"".join(int(n).to_bytes(32, "big") for n in _NULLIFIERS)
        ).digest()
        self.assertEqual(passport_hash, expected)

    def test_hex_and_prefixed_nullifiers_normalise_identically(self):
        prover = _mock_prover()
        as_hex = [f"{i:064x}" for i in range(1, SESSION_COUNT + 1)]
        as_prefixed = ["0x" + h for h in as_hex]
        a = prover.generate_proof(as_hex, _HUMANITYS, "aa" * 32)[1]
        b = prover.generate_proof(as_prefixed, _HUMANITYS, "aa" * 32)[1]
        self.assertEqual(a, b)

    def test_different_sessions_produce_different_passport_hashes(self):
        prover = _mock_prover()
        other = [str(9000 + i) for i in range(SESSION_COUNT)]
        self.assertNotEqual(
            prover.generate_proof(_NULLIFIERS, _HUMANITYS, "aa" * 32)[1],
            prover.generate_proof(other, _HUMANITYS, "aa" * 32)[1],
        )


class TestVerifyProof(unittest.TestCase):

    def test_roundtrip_verifies(self):
        prover = _mock_prover()
        proof, passport_hash, min_hp = prover.generate_proof(
            _NULLIFIERS, _HUMANITYS, "aa" * 32
        )
        self.assertTrue(prover.verify_proof(proof, 0, 0, passport_hash, min_hp, 0))

    def test_wrong_size_rejected(self):
        prover = _mock_prover()
        _, passport_hash, min_hp = prover.generate_proof(_NULLIFIERS, _HUMANITYS, "aa" * 32)
        self.assertFalse(prover.verify_proof(b"\x00" * 128, 0, 0, passport_hash, min_hp, 0))

    def test_tampered_passport_hash_rejected(self):
        prover = _mock_prover()
        proof, _, min_hp = prover.generate_proof(_NULLIFIERS, _HUMANITYS, "aa" * 32)
        self.assertFalse(prover.verify_proof(proof, 0, 0, b"\xff" * 32, min_hp, 0))

    def test_tampered_min_humanity_rejected(self):
        prover = _mock_prover()
        proof, passport_hash, min_hp = prover.generate_proof(
            _NULLIFIERS, _HUMANITYS, "aa" * 32
        )
        self.assertFalse(prover.verify_proof(proof, 0, 0, passport_hash, min_hp + 1, 0))


_PROOF_JSON = {
    "pi_a": ["1", "2", "1"],
    "pi_b": [["3", "4"], ["5", "6"], ["1", "0"]],
    "pi_c": ["7", "8", "1"],
    "protocol": "groth16",
    "curve": "bn128",
}


class TestProofCodec(unittest.TestCase):

    def test_encode_layout(self):
        raw = _encode_proof(_PROOF_JSON)
        self.assertEqual(len(raw), PROOF_SIZE)
        for idx, expected in enumerate([1, 2, 3, 4, 5, 6, 7, 8]):
            chunk = raw[idx * 32:(idx + 1) * 32]
            self.assertEqual(int.from_bytes(chunk, "big"), expected)

    def test_encode_accepts_hex_strings(self):
        hex_json = {
            "pi_a": ["0x01", "0x02", "1"],
            "pi_b": [["0x03", "0x04"], ["0x05", "0x06"], ["1", "0"]],
            "pi_c": ["0x07", "0x08", "1"],
        }
        self.assertEqual(_encode_proof(hex_json), _encode_proof(_PROOF_JSON))

    def test_decode_roundtrip(self):
        decoded = _decode_proof(_encode_proof(_PROOF_JSON))
        self.assertEqual(decoded["protocol"], "groth16")
        self.assertEqual(decoded["curve"], "bn128")
        self.assertEqual(int(decoded["pi_a"][0], 16), 1)
        self.assertEqual(int(decoded["pi_b"][1][1], 16), 6)
        self.assertEqual(int(decoded["pi_c"][1], 16), 8)
        self.assertEqual(decoded["pi_b"][2], ["1", "0"])


if __name__ == "__main__":
    unittest.main()
