#!/usr/bin/env python3
"""
VBDIP-0006 v1.1 conformance vector generator (M1 deliverable).

Generates 100 deterministic test vectors against the v1.1
authoritative wire layout (per Appendix A.3) using
bridge/vapi_bridge/codec.py as oracle. Vectors are signed with an
ephemeral deterministic ECDSA-P256 key whose private half is NEVER
committed (per §9.2 R2 binding contract).

Categories (20 each = 100 total):
    TV-001..020  random       — Mersenne Twister seed=0 sampling
    TV-021..040  edge_case    — 20 explicit boundary samples
    TV-041..060  hard_cheat   — inference_result = 0x28 DRIVER_INJECT
    TV-061..080  chain_rollup — prev_poac_hash = SHA-256(prev body)
    TV-081..100  counter_rollover — monotonic_ctr near 2^32-1 (v1.1 A.3)

Schema: docs/vbdip-0006-conformance-harness.md §3.1 v1.1 literal.
No record_hash_hex field per v1.1 Appendix A.4.

Run:
    python scripts/vbdip_0006_conformance/generator.py
"""
import argparse
import hashlib
import json
import random
import struct
import sys
import time
from pathlib import Path

# Add bridge to sys.path so codec.py import resolves
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge.vapi_bridge import codec  # noqa: E402

from cryptography.hazmat.primitives.asymmetric import ec, utils as ec_utils
from cryptography.hazmat.primitives import hashes, serialization

# ─── FROZEN CONSTANTS (v1.1) ───────────────────────────────────────────

VBDIP_V11_SPEC_HASH = (
    "4aea3a35042a0d59e909b332999fc0b4e673833ed69391cf111b9b3eaf9bfaac"
)
VBDIP_V10_SPEC_HASH = (
    "0667cd34ec2635e58da3fb7860d537018ed3b4f30290df2ccac4a84ecbf1d3db"
)
V11_MANIFEST_PATH = "vsd-vault/manifests/proposals-VBDIP-0006/002.manifest.json"
V11_MANIFEST_COMMIT = "975ea2bb"
SPEC_VERSION = "VBDIP-0006-v1.1"

TOTAL_VECTORS = 100
CATEGORY_COUNT = 20
CATEGORIES = (
    "random",
    "edge_case",
    "hard_cheat",
    "chain_rollup",
    "counter_rollover",
)

# v1.1 A.3: monotonic_ctr is uint32 BE (was uint64 in superseded v1.0 §3.1)
UINT32_MAX = (1 << 32) - 1

# Hard cheat code per v1.0 §3.4 (preserved in v1.1)
HARD_CHEAT_DRIVER_INJECT = 0x28

# Deterministic seeds
RANDOM_SEED = 0
EPHEMERAL_KEY_SEED_HEX = (
    "6d2b56df3a6d5a8c1b8e3f04c0c2e6e1f7b6e8a2c4d8e9f0a1b2c3d4e5f60718"
)

# Output paths (relative to --output-dir)
PUBKEY_FILENAME = "test_signing_key_v1.1.pub.pem"
TRANSCRIPT_FILENAME = "generator-transcript-v1.1.json"
PUBKEY_REF = "scripts/vbdip_0006_conformance/test_signing_key_v1.1.pub.pem"


# ─── DETERMINISTIC INPUT GENERATION ────────────────────────────────────

def _det_bytes(rng: random.Random, n: int) -> bytes:
    """Generate n deterministic bytes from the seeded RNG."""
    return bytes(rng.randint(0, 255) for _ in range(n))


def _gen_random_input(rng: random.Random) -> dict:
    """C1 — Mersenne Twister seeded random values within valid domains."""
    return {
        "prev_poac_hash_hex":     _det_bytes(rng, 32).hex(),
        "sensor_commitment_hex":  _det_bytes(rng, 32).hex(),
        "model_manifest_hash_hex": _det_bytes(rng, 32).hex(),
        "world_model_hash_hex":   _det_bytes(rng, 32).hex(),
        # inference_result: avoid 0x28 (reserved for C3 hard-cheat category)
        "inference_result":       rng.randint(0, 0x1F),
        "action_code":            rng.randint(0, 0x0A),
        "confidence":             rng.randint(0, 255),
        "battery_pct":            rng.randint(0, 100),
        "monotonic_ctr":          rng.randint(1, (1 << 31) - 1),
        "timestamp_ms":           rng.randint(0, (1 << 40)),
        "latitude":               rng.uniform(-90.0, 90.0),
        "longitude":              rng.uniform(-180.0, 180.0),
        "bounty_id":              rng.randint(0, (1 << 31) - 1),
    }


def _gen_edge_case_inputs() -> list[dict]:
    """C2 — 20 explicit boundary samples."""
    z32 = "00" * 32
    f32 = "ff" * 32
    h32 = "aa" * 32  # mid-pattern (alternating bits)
    samples = [
        # 1. fully zero
        {"prev_poac_hash_hex": z32, "sensor_commitment_hex": z32,
         "model_manifest_hash_hex": z32, "world_model_hash_hex": z32,
         "inference_result": 0, "action_code": 0, "confidence": 0,
         "battery_pct": 0, "monotonic_ctr": 0, "timestamp_ms": 0,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 2. fully max
        {"prev_poac_hash_hex": f32, "sensor_commitment_hex": f32,
         "model_manifest_hash_hex": f32, "world_model_hash_hex": f32,
         "inference_result": 0xFF, "action_code": 0xFF, "confidence": 255,
         "battery_pct": 100, "monotonic_ctr": UINT32_MAX,
         "timestamp_ms": (1 << 62), "latitude": 90.0, "longitude": 180.0,
         "bounty_id": UINT32_MAX},
        # 3. zero hashes, max scalars
        {"prev_poac_hash_hex": z32, "sensor_commitment_hex": z32,
         "model_manifest_hash_hex": z32, "world_model_hash_hex": z32,
         "inference_result": 0xFF, "action_code": 0xFF, "confidence": 255,
         "battery_pct": 100, "monotonic_ctr": UINT32_MAX,
         "timestamp_ms": (1 << 40), "latitude": 0.0, "longitude": 0.0,
         "bounty_id": UINT32_MAX},
        # 4. max hashes, zero scalars
        {"prev_poac_hash_hex": f32, "sensor_commitment_hex": f32,
         "model_manifest_hash_hex": f32, "world_model_hash_hex": f32,
         "inference_result": 0, "action_code": 0, "confidence": 0,
         "battery_pct": 0, "monotonic_ctr": 0, "timestamp_ms": 0,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 5. alternating hashes
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x10, "action_code": 0x05, "confidence": 128,
         "battery_pct": 50, "monotonic_ctr": 1, "timestamp_ms": 1,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 1},
        # 6. confidence minimum (0)
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x11, "action_code": 0x01, "confidence": 0,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 1.0, "longitude": 1.0, "bounty_id": 0},
        # 7. confidence midpoint (127)
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x12, "action_code": 0x02, "confidence": 127,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 1.0, "longitude": 1.0, "bounty_id": 0},
        # 8. battery_pct boundary 0
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x09, "confidence": 200,
         "battery_pct": 0, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 42},
        # 9. battery_pct boundary 100
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x09, "confidence": 200,
         "battery_pct": 100, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 42},
        # 10. monotonic_ctr = 1 (minimum non-zero)
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 100,
         "battery_pct": 50, "monotonic_ctr": 1, "timestamp_ms": 1,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 11. timestamp_ms = 0 (boot moment)
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x09, "action_code": 0x09, "confidence": 0,
         "battery_pct": 100, "monotonic_ctr": 1, "timestamp_ms": 0,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 12. timestamp_ms at int32 boundary (signed/unsigned interpretation)
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 1000, "timestamp_ms": (1 << 31),
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 13. timestamp_ms at uint32 boundary
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 1000, "timestamp_ms": (1 << 32),
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 14. latitude = equator
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 0.0, "longitude": 0.0, "bounty_id": 0},
        # 15. latitude = south pole
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": -90.0, "longitude": 0.0, "bounty_id": 0},
        # 16. latitude = north pole
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 90.0, "longitude": 0.0, "bounty_id": 0},
        # 17. longitude = anti-meridian negative
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 0.0, "longitude": -180.0, "bounty_id": 0},
        # 18. longitude = anti-meridian positive
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x00, "action_code": 0x00, "confidence": 50,
         "battery_pct": 50, "monotonic_ctr": 100, "timestamp_ms": 1000,
         "latitude": 0.0, "longitude": 180.0, "bounty_id": 0},
        # 19. all action codes — pick the highest named (0x0A SWARM_SYNC)
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x13, "action_code": 0x0A, "confidence": 200,
         "battery_pct": 75, "monotonic_ctr": 12345, "timestamp_ms": 67890,
         "latitude": 45.0, "longitude": -75.0, "bounty_id": 99},
        # 20. advisory inference code 0x33 GSR_CORRELATION_ABSENT
        {"prev_poac_hash_hex": h32, "sensor_commitment_hex": h32,
         "model_manifest_hash_hex": h32, "world_model_hash_hex": h32,
         "inference_result": 0x33, "action_code": 0x02, "confidence": 100,
         "battery_pct": 50, "monotonic_ctr": 999, "timestamp_ms": 99999,
         "latitude": -45.0, "longitude": 75.0, "bounty_id": 1},
    ]
    assert len(samples) == CATEGORY_COUNT
    return samples


def _gen_hard_cheat_input(rng: random.Random) -> dict:
    """C3 — random base with inference_result forced to 0x28."""
    base = _gen_random_input(rng)
    base["inference_result"] = HARD_CHEAT_DRIVER_INJECT
    return base


def _gen_counter_rollover_inputs(rng: random.Random) -> list[dict]:
    """C5 — monotonic_ctr clustered near uint32 boundary (v1.1 A.3)."""
    # v1.1 A.3 binding: monotonic_ctr is uint32 BE, NOT uint64. Boundary
    # is 2^32-1 (not 2^64-1 as v1.0 §3.1 erroneously specified). Range
    # covers near-max + power-of-two boundaries + zero.
    rollover_ctrs = [
        UINT32_MAX,
        UINT32_MAX - 1,
        UINT32_MAX - 2,
        UINT32_MAX - 10,
        UINT32_MAX - 100,
        UINT32_MAX - 1000,
        UINT32_MAX - 10000,
        UINT32_MAX - 100000,
        UINT32_MAX - 1000000,
        UINT32_MAX - 10000000,
        UINT32_MAX - 100000000,
        UINT32_MAX // 2,
        UINT32_MAX // 4,
        UINT32_MAX // 8,
        UINT32_MAX // 16,
        (1 << 31),
        (1 << 31) - 1,
        (1 << 24),
        (1 << 16),
        0,
    ]
    assert len(rollover_ctrs) == CATEGORY_COUNT
    inputs = []
    for ctr in rollover_ctrs:
        inp = _gen_random_input(rng)
        inp["monotonic_ctr"] = ctr
        inputs.append(inp)
    return inputs


# ─── BODY SERIALIZATION (uses codec.py as oracle) ──────────────────────

def _serialize_body(inp: dict) -> bytes:
    """Serialize per v1.1 A.3 layout using codec.py wire-format constants.

    Mirrors codec.parse_record's inverse: 4×32B hashes then struct-packed
    36B fields = 164B body.
    """
    body = b""
    body += bytes.fromhex(inp["prev_poac_hash_hex"])
    body += bytes.fromhex(inp["sensor_commitment_hex"])
    body += bytes.fromhex(inp["model_manifest_hash_hex"])
    body += bytes.fromhex(inp["world_model_hash_hex"])
    body += struct.pack(
        codec._FIELDS_FMT,
        inp["inference_result"],
        inp["action_code"],
        inp["confidence"],
        inp["battery_pct"],
        inp["monotonic_ctr"],
        inp["timestamp_ms"],
        inp["latitude"],
        inp["longitude"],
        inp["bounty_id"],
    )
    assert len(body) == codec.POAC_BODY_SIZE, (
        f"body size {len(body)} != {codec.POAC_BODY_SIZE}"
    )
    return body


# ─── SIGNING (ephemeral deterministic key; never persisted) ────────────

def _new_ephemeral_signing_key():
    """Derive deterministic ECDSA-P256 private key from fixed seed.

    Per §9.2 R2 binding contract: the private key is generated
    deterministically (re-runs produce the same pubkey) AND never
    committed (only public key + signatures persist). Key derivation
    via ec.derive_private_key from a 32-byte seed integer.

    Note: signing uses random k per Python `cryptography` library
    default. Signatures verify identically across runs (against the
    deterministic pubkey) but signature bytes themselves are NOT
    byte-identical across re-runs. Body content + body_sha256 are
    byte-identical; signatures are not.
    """
    seed_int = int(EPHEMERAL_KEY_SEED_HEX, 16)
    return ec.derive_private_key(seed_int, ec.SECP256R1())


def _sign_body(priv, body: bytes) -> bytes:
    """ECDSA-P256 sign the 164-byte body, return 64-byte (r||s) raw."""
    der_sig = priv.sign(body, ec.ECDSA(hashes.SHA256()))
    r, s = ec_utils.decode_dss_signature(der_sig)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


# ─── VECTOR ASSEMBLY ───────────────────────────────────────────────────

def _build_vector(
    vector_id: str,
    category: str,
    input_fields: dict,
    body: bytes,
    signature: bytes,
    chain_pred_id: str | None,
    notes: str,
) -> dict:
    """Assemble per v1.1 §3.1 schema (literal, no record_hash_hex)."""
    return {
        "vector_id": vector_id,
        "spec_version": SPEC_VERSION,
        "vbdip_spec_hash": VBDIP_V11_SPEC_HASH,
        "vbdip_v10_spec_hash": VBDIP_V10_SPEC_HASH,
        "category": category,
        "input": input_fields,
        "expected": {
            "body_hex": body.hex(),
            "body_sha256_hex": hashlib.sha256(body).hexdigest(),
            "signature_status": "valid_test_fixture",
            "signature_hex": signature.hex(),
            "signing_pubkey_ref": PUBKEY_REF,
        },
        "validation": {
            "expected_verdict": "pass",
            "failure_mode_when_fail": None,
            "verifies_chain_against_prev_vector_id": chain_pred_id,
        },
        "notes": notes,
    }


# ─── GENERATOR ENTRY ───────────────────────────────────────────────────

def generate(output_dir: Path) -> dict:
    """Main entry. Returns the transcript dict for the caller's records."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ephemeral signing key (deterministic; never persisted)
    priv = _new_ephemeral_signing_key()
    pub = priv.public_key()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_uncompressed = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pubkey_fingerprint_sha256_16 = hashlib.sha256(pub_uncompressed).hexdigest()[:16]

    (output_dir / PUBKEY_FILENAME).write_bytes(pub_pem)

    # 2. Generate 100 vectors deterministically
    rng = random.Random(RANDOM_SEED)
    vectors: list[dict] = []

    # C1 random (TV-001..020)
    for i in range(CATEGORY_COUNT):
        vid = f"TV-{i + 1:03d}"
        inp = _gen_random_input(rng)
        body = _serialize_body(inp)
        sig = _sign_body(priv, body)
        vectors.append(_build_vector(
            vid, "random", inp, body, sig, chain_pred_id=None,
            notes=f"C1 random Mersenne Twister seed={RANDOM_SEED} sample {i + 1}",
        ))

    # C2 edge_case (TV-021..040)
    for i, inp in enumerate(_gen_edge_case_inputs()):
        vid = f"TV-{i + 21:03d}"
        body = _serialize_body(inp)
        sig = _sign_body(priv, body)
        vectors.append(_build_vector(
            vid, "edge_case", inp, body, sig, chain_pred_id=None,
            notes=f"C2 edge case boundary sample {i + 1}/20",
        ))

    # C3 hard_cheat (TV-041..060) — inference_result = 0x28
    for i in range(CATEGORY_COUNT):
        vid = f"TV-{i + 41:03d}"
        inp = _gen_hard_cheat_input(rng)
        body = _serialize_body(inp)
        sig = _sign_body(priv, body)
        vectors.append(_build_vector(
            vid, "hard_cheat", inp, body, sig, chain_pred_id=None,
            notes=f"C3 hard-cheat 0x28 DRIVER_INJECT sample {i + 1}/20",
        ))

    # C4 chain_rollup (TV-061..080) — prev_poac_hash chains across links
    prev_body_sha256 = "00" * 32  # genesis: zero predecessor
    for i in range(CATEGORY_COUNT):
        vid = f"TV-{i + 61:03d}"
        inp = _gen_random_input(rng)
        inp["prev_poac_hash_hex"] = prev_body_sha256  # bind to predecessor
        body = _serialize_body(inp)
        sig = _sign_body(priv, body)
        chain_pred = f"TV-{i + 60:03d}" if i > 0 else None
        vectors.append(_build_vector(
            vid, "chain_rollup", inp, body, sig, chain_pred_id=chain_pred,
            notes=f"C4 GIC chain link {i + 1}/20 — prev_poac_hash = SHA-256(prev_body)",
        ))
        prev_body_sha256 = hashlib.sha256(body).hexdigest()

    # C5 counter_rollover (TV-081..100) — monotonic_ctr near uint32 max
    for i, inp in enumerate(_gen_counter_rollover_inputs(rng)):
        vid = f"TV-{i + 81:03d}"
        body = _serialize_body(inp)
        sig = _sign_body(priv, body)
        vectors.append(_build_vector(
            vid, "counter_rollover", inp, body, sig, chain_pred_id=None,
            notes=(
                f"C5 counter_rollover uint32 boundary sample {i + 1}/20 "
                f"(monotonic_ctr={inp['monotonic_ctr']})"
            ),
        ))

    assert len(vectors) == TOTAL_VECTORS, f"vector count: {len(vectors)}"

    # 3. Write per-category vector JSON files
    vectors_dir = output_dir / "vectors"
    vectors_dir.mkdir(exist_ok=True)
    binary_dir = vectors_dir / "binary"
    binary_dir.mkdir(exist_ok=True)

    cat_files = [
        ("001-020-random.json",       0,   20),
        ("021-040-edge_case.json",    20,  40),
        ("041-060-hard_cheat.json",   40,  60),
        ("061-080-chain_rollup.json", 60,  80),
        ("081-100-counter_rollover.json", 80, 100),
    ]
    for fname, start, end in cat_files:
        cat_vecs = vectors[start:end]
        (vectors_dir / fname).write_text(
            json.dumps(cat_vecs, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    # 4. Write binary fixtures (body + signed record per vector)
    for vec in vectors:
        body_bytes = bytes.fromhex(vec["expected"]["body_hex"])
        (binary_dir / f"{vec['vector_id']}.body.bin").write_bytes(body_bytes)
        sig_bytes = bytes.fromhex(vec["expected"]["signature_hex"])
        (binary_dir / f"{vec['vector_id']}.record.bin").write_bytes(
            body_bytes + sig_bytes
        )

    # 5. Write generator transcript / deletion attestation
    manifests_dir = output_dir / "manifests"
    manifests_dir.mkdir(exist_ok=True)

    generator_source = Path(__file__).read_bytes()
    generator_sha256 = hashlib.sha256(generator_source).hexdigest()

    transcript = {
        "schema": "vbdip-0006-conformance-generator-transcript-v1",
        "vbdip_spec_version": SPEC_VERSION,
        "vbdip_spec_hash": VBDIP_V11_SPEC_HASH,
        "vbdip_v10_spec_hash_superseded": VBDIP_V10_SPEC_HASH,
        "supersedes_v10_note": (
            "Vectors generated against v1.1 reconciled wire layout per "
            "Appendix A.3. The SUPERSEDED v1.0 §3.1 table is NOT used as "
            "a vector authority. See vsd-vault/manifests/proposals-VBDIP-"
            "0006/002.manifest.json for the v1.1 architect-signed manifest."
        ),
        "v11_manifest_path": V11_MANIFEST_PATH,
        "v11_manifest_commit": V11_MANIFEST_COMMIT,
        "generator_script_path": "scripts/vbdip_0006_conformance/generator.py",
        "generator_script_sha256": generator_sha256,
        "generator_run_ts_ns": time.time_ns(),
        "vector_count": TOTAL_VECTORS,
        "category_counts": {cat: CATEGORY_COUNT for cat in CATEGORIES},
        "public_key_path": "scripts/vbdip_0006_conformance/" + PUBKEY_FILENAME,
        "public_key_fingerprint_sha256_16": pubkey_fingerprint_sha256_16,
        "deterministic_seed_random": RANDOM_SEED,
        "ephemeral_key_seed_hex": EPHEMERAL_KEY_SEED_HEX,
        "ephemeral_key_derivation_method": (
            "ec.derive_private_key(int(ephemeral_key_seed_hex, 16), SECP256R1)"
        ),
        "no_private_key_attestation": (
            "The ECDSA-P256 private key used for fixture signing was "
            "derived deterministically from a hardcoded seed in this "
            "generator's source (see EPHEMERAL_KEY_SEED_HEX constant). "
            "The private key was NOT persisted to any file under "
            "scripts/vbdip_0006_conformance/ — only the corresponding "
            "public key PEM + per-vector signatures are committed. The "
            "private key exists only within the generator process's "
            "memory and is garbage-collected when the script exits. "
            "Per VBDIP-0006 conformance harness M0.1 §9.2 R2 binding "
            "contract: 'never commit the private key.' Anyone with the "
            "generator source (a known SHA-256) can reproduce the same "
            "key for re-signing purposes; this is acceptable for test-"
            "fixture signing where the key has no production authority. "
            "Production firmware MUST use SE-resident keys never "
            "derivable from a committed seed."
        ),
        "signature_determinism_note": (
            "ECDSA-P256 signatures use random k per Python `cryptography` "
            "library default. Vector body content (input + body_hex + "
            "body_sha256_hex) is byte-deterministic across generator "
            "reruns; signature bytes (expected.signature_hex) vary across "
            "reruns but verify against the deterministic public key. "
            "Determinism regression tests assert body-byte equality + "
            "signature verification, NOT signature byte-equality."
        ),
    }

    (manifests_dir / TRANSCRIPT_FILENAME).write_text(
        json.dumps(transcript, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return transcript


def main():
    parser = argparse.ArgumentParser(
        description="VBDIP-0006 v1.1 conformance vector generator (M1)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_THIS_DIR),
        help="Directory to write vectors/ + manifests/ + pubkey PEM",
    )
    args = parser.parse_args()
    transcript = generate(Path(args.output_dir))
    print(f"Generated {transcript['vector_count']} vectors")
    print(f"  Output:     {args.output_dir}")
    print(f"  Pubkey fp:  {transcript['public_key_fingerprint_sha256_16']}")
    print(f"  Gen SHA-256: {transcript['generator_script_sha256']}")
    print(f"  Spec hash:  {transcript['vbdip_spec_hash']}")


if __name__ == "__main__":
    main()
