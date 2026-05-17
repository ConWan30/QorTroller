"""
VBDIP-0006 v1.1 conformance vector generator — focused regression tests.

Discipline mirror of `bridge/tests/test_phase_o1_c10_e2e_shadow_stack.py`
(static-shape guards) + `frontend/src/__tests__/AndroidResponsiveGuards.test.jsx`
(no-runtime-import static-grep pattern).

Scope: M1 generator only. Mock controller (M2) + validation harness
(M3) deferred.

Test IDs (T-VBDIP-M1-*):
  T-VBDIP-M1-01  100 vectors exist across 5 category files
  T-VBDIP-M1-02  per-category counts are 20 each
  T-VBDIP-M1-03  vector IDs are TV-001..TV-100 contiguous
  T-VBDIP-M1-04  required schema fields present per v1.1 §3.1 literal
  T-VBDIP-M1-05  record_hash_hex ABSENT from every vector (v1.1 A.4)
  T-VBDIP-M1-06  expected_body_hex length == 328 (164B)
  T-VBDIP-M1-07  body_sha256_hex length == 64 (32B full SHA-256)
  T-VBDIP-M1-08  signature_hex length == 128 (64B ECDSA-P256 r||s)
  T-VBDIP-M1-09  body_sha256_hex matches recomputed SHA-256(body_hex)
  T-VBDIP-M1-10  body parses cleanly via codec.parse_record + signature verifies
  T-VBDIP-M1-11  C4 chain integrity: prev_poac_hash chains across links
  T-VBDIP-M1-12  C3 hard-cheat: every vector has inference_result == 0x28
  T-VBDIP-M1-13  C5 counter_rollover: monotonic_ctr values near uint32 max
  T-VBDIP-M1-14  public key file exists; matches generator-derived key
  T-VBDIP-M1-15  NO private key file exists under scripts/vbdip_0006_conformance/
  T-VBDIP-M1-16  static-scan: zero "BEGIN PRIVATE KEY" / "BEGIN ED25519 PRIVATE
                 KEY" / "BEGIN EC PRIVATE KEY" markers under conformance dir
  T-VBDIP-M1-17  transcript fields match v1.1 spec hash + manifest commit + counts
  T-VBDIP-M1-18  generator rerun into tmp dir is deterministic (body bytes equal,
                 signatures verify against same pubkey, sigs may differ
                 byte-wise — see generator transcript signature_determinism_note)
  T-VBDIP-M1-19  mock_controller.py does NOT exist (M2 deferred)
  T-VBDIP-M1-20  vbdip_spec_hash in every vector matches v1.1 manifest
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFORMANCE_DIR = _REPO_ROOT / "scripts" / "vbdip_0006_conformance"
_VECTORS_DIR = _CONFORMANCE_DIR / "vectors"
_BINARY_DIR = _VECTORS_DIR / "binary"
_MANIFESTS_DIR = _CONFORMANCE_DIR / "manifests"

_V11_SPEC_HASH = (
    "4aea3a35042a0d59e909b332999fc0b4e673833ed69391cf111b9b3eaf9bfaac"
)
_V11_MANIFEST_COMMIT = "975ea2bb"

_REQUIRED_INPUT_FIELDS = (
    "prev_poac_hash_hex", "sensor_commitment_hex",
    "model_manifest_hash_hex", "world_model_hash_hex",
    "inference_result", "action_code", "confidence", "battery_pct",
    "monotonic_ctr", "timestamp_ms", "latitude", "longitude", "bounty_id",
)
_REQUIRED_EXPECTED_FIELDS = (
    "body_hex", "body_sha256_hex",
    "signature_status", "signature_hex", "signing_pubkey_ref",
)
_REQUIRED_VECTOR_FIELDS = (
    "vector_id", "spec_version", "vbdip_spec_hash", "vbdip_v10_spec_hash",
    "category", "input", "expected", "validation", "notes",
)

_CATEGORY_FILES = (
    ("001-020-random.json",            0,  20, "random"),
    ("021-040-edge_case.json",         20, 40, "edge_case"),
    ("041-060-hard_cheat.json",        40, 60, "hard_cheat"),
    ("061-080-chain_rollup.json",      60, 80, "chain_rollup"),
    ("081-100-counter_rollover.json",  80, 100, "counter_rollover"),
)


@pytest.fixture(scope="module")
def all_vectors() -> list[dict]:
    vectors = []
    for fname, start, end, _cat in _CATEGORY_FILES:
        path = _VECTORS_DIR / fname
        assert path.exists(), f"Missing vector file: {path}"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert len(loaded) == end - start, (
            f"{fname} count {len(loaded)} != expected {end - start}"
        )
        vectors.extend(loaded)
    return vectors


# ─── T-VBDIP-M1-01..03 — count + IDs + contiguity ─────────────────────

def test_t_vbdip_m1_01_total_vector_count(all_vectors):
    """T-VBDIP-M1-01: 100 vectors across 5 category files."""
    assert len(all_vectors) == 100


def test_t_vbdip_m1_02_per_category_counts(all_vectors):
    """T-VBDIP-M1-02: per-category counts are 20 each."""
    counts: dict[str, int] = {}
    for v in all_vectors:
        counts[v["category"]] = counts.get(v["category"], 0) + 1
    expected = {
        "random": 20, "edge_case": 20, "hard_cheat": 20,
        "chain_rollup": 20, "counter_rollover": 20,
    }
    assert counts == expected, f"Category drift: {counts}"


def test_t_vbdip_m1_03_vector_ids_contiguous(all_vectors):
    """T-VBDIP-M1-03: vector IDs TV-001..TV-100 contiguous."""
    ids = [v["vector_id"] for v in all_vectors]
    expected = [f"TV-{i:03d}" for i in range(1, 101)]
    assert ids == expected, f"ID sequence drift at first mismatch"


# ─── T-VBDIP-M1-04..05 — schema fields + record_hash_hex absent ──────

def test_t_vbdip_m1_04_required_schema_fields_present(all_vectors):
    """T-VBDIP-M1-04: required schema fields present per v1.1 §3.1."""
    for v in all_vectors:
        for f in _REQUIRED_VECTOR_FIELDS:
            assert f in v, f"{v.get('vector_id', '?')} missing top-level field: {f}"
        for f in _REQUIRED_INPUT_FIELDS:
            assert f in v["input"], (
                f"{v['vector_id']} missing input field: {f}"
            )
        for f in _REQUIRED_EXPECTED_FIELDS:
            assert f in v["expected"], (
                f"{v['vector_id']} missing expected field: {f}"
            )


def test_t_vbdip_m1_05_no_record_hash_hex_anywhere(all_vectors):
    """T-VBDIP-M1-05: record_hash_hex ABSENT from every vector (v1.1 A.4
    SUPERSEDED v1.0 §3.1's 16-byte truncation claim — Option A literal)."""
    for v in all_vectors:
        assert "record_hash_hex" not in v["expected"], (
            f"{v['vector_id']} reintroduces record_hash_hex (v1.1 A.4 forbids)"
        )
        # Also scan all nested levels for the offending key
        flat = json.dumps(v)
        assert '"record_hash_hex"' not in flat, (
            f"{v['vector_id']} carries record_hash_hex somewhere in nested struct"
        )


# ─── T-VBDIP-M1-06..09 — hex field lengths + body hash consistency ───

def test_t_vbdip_m1_06_body_hex_length(all_vectors):
    """T-VBDIP-M1-06: expected.body_hex is 328 hex chars (164 bytes)."""
    for v in all_vectors:
        h = v["expected"]["body_hex"]
        assert len(h) == 328, (
            f"{v['vector_id']} body_hex len {len(h)} != 328 (164 bytes)"
        )
        bytes.fromhex(h)  # must be valid hex


def test_t_vbdip_m1_07_body_sha256_length(all_vectors):
    """T-VBDIP-M1-07: body_sha256_hex is 64 hex chars (32 bytes, full SHA-256)."""
    for v in all_vectors:
        h = v["expected"]["body_sha256_hex"]
        assert len(h) == 64, (
            f"{v['vector_id']} body_sha256_hex len {len(h)} != 64 (32 bytes)"
        )
        bytes.fromhex(h)


def test_t_vbdip_m1_08_signature_length(all_vectors):
    """T-VBDIP-M1-08: signature_hex is 128 hex chars (64-byte ECDSA-P256 r||s)."""
    for v in all_vectors:
        h = v["expected"]["signature_hex"]
        assert len(h) == 128, (
            f"{v['vector_id']} signature_hex len {len(h)} != 128 (64 bytes)"
        )
        bytes.fromhex(h)


def test_t_vbdip_m1_09_body_sha256_matches_recomputed(all_vectors):
    """T-VBDIP-M1-09: body_sha256_hex equals SHA-256(body_hex bytes)."""
    for v in all_vectors:
        body = bytes.fromhex(v["expected"]["body_hex"])
        recomputed = hashlib.sha256(body).hexdigest()
        assert recomputed == v["expected"]["body_sha256_hex"], (
            f"{v['vector_id']} body_sha256 drift"
        )


# ─── T-VBDIP-M1-10 — codec.parse_record + signature verify ────────────

def test_t_vbdip_m1_10_records_parse_and_signatures_verify(all_vectors):
    """T-VBDIP-M1-10: full 228-byte records parse cleanly via codec +
    signatures verify against the committed public key."""
    sys.path.insert(0, str(_REPO_ROOT))
    from bridge.vapi_bridge import codec  # noqa: E402
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    pub_pem = (_CONFORMANCE_DIR / "test_signing_key_v1.1.pub.pem").read_bytes()
    pub = serialization.load_pem_public_key(pub_pem)
    # codec.verify_signature expects 65-byte uncompressed SEC1; derive it
    pub_uncompressed = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    for v in all_vectors:
        body = bytes.fromhex(v["expected"]["body_hex"])
        sig = bytes.fromhex(v["expected"]["signature_hex"])
        record_bytes = body + sig
        # 1. parse_record accepts the bytes cleanly (size + offsets correct)
        rec = codec.parse_record(record_bytes)
        assert len(rec.raw_body) == 164, f"{v['vector_id']} body size drift"
        # 2. signature verifies against the committed pubkey
        assert codec.verify_signature(rec, pub_uncompressed), (
            f"{v['vector_id']} signature does not verify against committed pubkey"
        )


# ─── T-VBDIP-M1-11..13 — per-category integrity ──────────────────────

def test_t_vbdip_m1_11_chain_rollup_integrity(all_vectors):
    """T-VBDIP-M1-11: C4 chain — each link's prev_poac_hash equals
    SHA-256(previous link's body). Genesis link prev_poac_hash is zero."""
    chain = [v for v in all_vectors if v["category"] == "chain_rollup"]
    assert len(chain) == 20
    expected_prev = "00" * 32  # genesis
    for v in chain:
        actual = v["input"]["prev_poac_hash_hex"]
        assert actual == expected_prev, (
            f"{v['vector_id']} chain break: prev={actual} expected={expected_prev}"
        )
        body = bytes.fromhex(v["expected"]["body_hex"])
        expected_prev = hashlib.sha256(body).hexdigest()


def test_t_vbdip_m1_12_hardcheat_inference_code(all_vectors):
    """T-VBDIP-M1-12: C3 — every vector has inference_result == 0x28."""
    hc = [v for v in all_vectors if v["category"] == "hard_cheat"]
    assert len(hc) == 20
    for v in hc:
        assert v["input"]["inference_result"] == 0x28, (
            f"{v['vector_id']} not hard-cheat injected"
        )


def test_t_vbdip_m1_13_counter_rollover_uint32_boundary(all_vectors):
    """T-VBDIP-M1-13: C5 — monotonic_ctr clustered near uint32 max OR
    explicit boundary values (per v1.1 A.3 — was uint64 in v1.0)."""
    uint32_max = (1 << 32) - 1
    cr = [v for v in all_vectors if v["category"] == "counter_rollover"]
    assert len(cr) == 20
    # Every value must fit in uint32 (catches v1.0 uint64 regression)
    for v in cr:
        ctr = v["input"]["monotonic_ctr"]
        assert 0 <= ctr <= uint32_max, (
            f"{v['vector_id']} monotonic_ctr {ctr} outside uint32 range"
        )
    # At least one vector should be at exactly UINT32_MAX (rollover target)
    ctrs = [v["input"]["monotonic_ctr"] for v in cr]
    assert uint32_max in ctrs, "C5 missing exact uint32 max boundary sample"


# ─── T-VBDIP-M1-14..16 — credential hygiene (NEVER ship private key) ─

def test_t_vbdip_m1_14_public_key_present(all_vectors):
    """T-VBDIP-M1-14: public key PEM file exists; loads as ECDSA-P256."""
    pub_path = _CONFORMANCE_DIR / "test_signing_key_v1.1.pub.pem"
    assert pub_path.exists(), f"Missing public key: {pub_path}"
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    pub = serialization.load_pem_public_key(pub_path.read_bytes())
    assert isinstance(pub, ec.EllipticCurvePublicKey)
    assert isinstance(pub.curve, ec.SECP256R1)


def test_t_vbdip_m1_15_no_private_key_file_exists():
    """T-VBDIP-M1-15: zero files matching private-key naming patterns
    under scripts/vbdip_0006_conformance/."""
    forbidden_suffixes = (
        ".priv.pem", "_priv.pem", "-priv.pem",
        ".key", "_key.pem", "-key.pem",
        ".private.pem", ".sec",
    )
    forbidden_basenames = (
        "test_signing_key_v1.1.pem",  # no-suffix private would be this
        "test_signing_key.pem",        # M0 plan's original naming if leaked
        "private_key.pem", "signing_key.pem",
    )
    for path in _CONFORMANCE_DIR.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        for suf in forbidden_suffixes:
            assert not name.endswith(suf), (
                f"Forbidden private-key file present: {path}"
            )
        assert name not in forbidden_basenames, (
            f"Forbidden private-key basename present: {path}"
        )


def test_t_vbdip_m1_16_no_private_key_pem_markers_in_files():
    """T-VBDIP-M1-16: static-scan asserts no committed file under
    scripts/vbdip_0006_conformance/ contains a PRIVATE KEY PEM marker
    of any common form. Reads every file byte-by-byte; matches even
    binary fixtures (which should never contain PEM markers)."""
    forbidden_markers = (
        b"BEGIN PRIVATE KEY",
        b"BEGIN ED25519 PRIVATE KEY",
        b"BEGIN EC PRIVATE KEY",
        b"BEGIN RSA PRIVATE KEY",
        b"BEGIN ENCRYPTED PRIVATE KEY",
        b"BEGIN OPENSSH PRIVATE KEY",
    )
    for path in _CONFORMANCE_DIR.rglob("*"):
        if not path.is_file():
            continue
        # Exclude this generator script itself from the scan (it references
        # the marker strings as test-time exclusion documentation; but for
        # M1 simplicity it does NOT — keep the scan strict + universal).
        content = path.read_bytes()
        for marker in forbidden_markers:
            assert marker not in content, (
                f"Forbidden private-key PEM marker {marker!r} found in: {path}"
            )


# ─── T-VBDIP-M1-17 — transcript field consistency ────────────────────

def test_t_vbdip_m1_17_transcript_fields_match():
    """T-VBDIP-M1-17: transcript carries v1.1 spec hash + manifest path
    + manifest commit + vector count + per-category counts."""
    t = json.loads(
        (_MANIFESTS_DIR / "generator-transcript-v1.1.json").read_text(encoding="utf-8")
    )
    assert t["vbdip_spec_version"] == "VBDIP-0006-v1.1"
    assert t["vbdip_spec_hash"] == _V11_SPEC_HASH
    assert t["v11_manifest_path"] == (
        "vsd-vault/manifests/proposals-VBDIP-0006/002.manifest.json"
    )
    assert t["v11_manifest_commit"] == _V11_MANIFEST_COMMIT
    assert t["vector_count"] == 100
    assert t["category_counts"] == {
        "random": 20, "edge_case": 20, "hard_cheat": 20,
        "chain_rollup": 20, "counter_rollover": 20,
    }
    # Generator script SHA-256 matches current script bytes
    actual_sha = hashlib.sha256(
        (_CONFORMANCE_DIR / "generator.py").read_bytes()
    ).hexdigest()
    assert t["generator_script_sha256"] == actual_sha, (
        "Transcript generator_script_sha256 drift — regenerate vectors"
    )
    # No-private-key attestation present
    assert "no_private_key_attestation" in t
    assert "never commit the private key" in t["no_private_key_attestation"].lower()


# ─── T-VBDIP-M1-18 — deterministic rerun ─────────────────────────────

def test_t_vbdip_m1_18_deterministic_rerun_into_tmp(tmp_path):
    """T-VBDIP-M1-18: rerun generator into temp dir. All non-signature
    vector content (input + body_hex + body_sha256_hex) byte-identical
    to committed. Signatures vary (random k per ECDSA default) BUT
    must verify against the committed public key.

    See transcript signature_determinism_note for the documented
    expectation.
    """
    sys.path.insert(0, str(_REPO_ROOT))
    from scripts.vbdip_0006_conformance import generator  # noqa: E402
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    generator.generate(tmp_path)

    # Load original + rerun vectors
    def _load_all(base: Path) -> list[dict]:
        out = []
        for fname, _s, _e, _c in _CATEGORY_FILES:
            out.extend(json.loads(
                (base / "vectors" / fname).read_text(encoding="utf-8")
            ))
        return out

    orig = _load_all(_CONFORMANCE_DIR)
    rerun = _load_all(tmp_path)

    assert len(orig) == len(rerun) == 100

    # Public key byte-identical (deterministic key derivation)
    orig_pub = (_CONFORMANCE_DIR / "test_signing_key_v1.1.pub.pem").read_bytes()
    rerun_pub = (tmp_path / "test_signing_key_v1.1.pub.pem").read_bytes()
    assert orig_pub == rerun_pub, "Public key drift — non-deterministic key derivation"

    # Per-vector: input + body + body_sha256 byte-equal; signature verifies
    pub = serialization.load_pem_public_key(rerun_pub)
    pub_uncompressed = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    from bridge.vapi_bridge import codec  # noqa: E402
    for o, r in zip(orig, rerun):
        assert o["vector_id"] == r["vector_id"]
        assert o["input"] == r["input"], (
            f"{o['vector_id']} input drift on rerun"
        )
        assert o["expected"]["body_hex"] == r["expected"]["body_hex"], (
            f"{o['vector_id']} body drift on rerun"
        )
        assert o["expected"]["body_sha256_hex"] == r["expected"]["body_sha256_hex"], (
            f"{o['vector_id']} body_sha256 drift on rerun"
        )
        # Rerun signature must verify against the same pubkey
        rerun_record = (
            bytes.fromhex(r["expected"]["body_hex"]) +
            bytes.fromhex(r["expected"]["signature_hex"])
        )
        rec = codec.parse_record(rerun_record)
        assert codec.verify_signature(rec, pub_uncompressed), (
            f"{r['vector_id']} rerun signature does not verify"
        )


# ─── T-VBDIP-M1-19 — M2 deferral guard ───────────────────────────────

def test_t_vbdip_m1_19_no_mock_controller_in_m1():
    """T-VBDIP-M1-19: mock_controller.py MUST NOT exist (M2 deferred)."""
    forbidden = _CONFORMANCE_DIR / "mock_controller.py"
    assert not forbidden.exists(), (
        f"M2 work leaked into M1 commit: {forbidden} exists"
    )


# ─── T-VBDIP-M1-20 — spec hash pin in every vector ───────────────────

def test_t_vbdip_m1_20_spec_hash_pin_per_vector(all_vectors):
    """T-VBDIP-M1-20: every vector carries vbdip_spec_hash matching the
    v1.1 architect-signed manifest."""
    for v in all_vectors:
        assert v["vbdip_spec_hash"] == _V11_SPEC_HASH, (
            f"{v['vector_id']} spec hash drift"
        )
        assert v["spec_version"] == "VBDIP-0006-v1.1"
