"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — VHP Verification Card tests.

Second ZKBA artifact target. Mirrors the GIC Continuity Ledger test pattern
(T-ZKBA-10 / T-ZKBA-11) and extends it with end-to-end Layer-7 pipeline
verification: compose -> compile -> VPM wrap -> G4 validate -> audit
re-verify (CFSS lane authority unchanged).

T-ZKBA-VHP-1: _compose_vhp_component byte layout matches FROZEN spec
T-ZKBA-VHP-2: build_vhp_card_artifact builds end-to-end (manifest + HTML + DB)
T-ZKBA-VHP-3: rebuild idempotent (same output + UNIQUE constraint on DB)
T-ZKBA-VHP-4: byte-stable across two builds (determinism)
T-ZKBA-VHP-5: VPM wrapper consumes the ZKBA manifest cleanly
T-ZKBA-VHP-6: G4 manifest validator accepts the emitted manifest
T-ZKBA-VHP-7: tamper detection on each field (token_id / device / expires /
              cert / is_valid all change the commitment)
T-ZKBA-VHP-8: audit harness Section 3 (CFSS) still PASSES after VHP card
              inserted (Cedar v2 lane authority unaffected)
"""
import hashlib
import json
import os
import struct
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_BRIDGE = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import (  # noqa: E402
    ZKBAClass,
    ProofWeightClass,
    compute_zkba_commitment,
)
from vsd_ui_compiler import ZKBAManifest, _MANIFEST_SCHEMA, _COMPILER_VERSION  # noqa: E402
from zkba_compile_vhp_card import (  # noqa: E402
    _compose_vhp_component,
    _parse_device_id_hash,
    build_vhp_card_artifact,
)


# Canonical fixture: real bridge wallet's VHP tokenId=2 from Session 3 mint
# (commit 76c92e9b). Hashes match the canonical Sony DualShock Edge CFI-ZCP1.
_FIXTURE_TOKEN_ID = 2
_FIXTURE_DEVICE_HASH_HEX = "10e0169446ba3320" + "00" * 24  # 64 hex chars
_FIXTURE_EXPIRES_AT = 1786080000  # ~ 2026-08-09 (Session 3 mint + 90d)
_FIXTURE_CERT_LEVEL = 1
_FIXTURE_IS_VALID = True
_FIXTURE_TS_NS = 1778900000000000000


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-1: composition byte layout
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_1_compose_vhp_component_byte_layout():
    """_compose_vhp_component matches the FROZEN byte layout:
       SHA-256( token_id_be(32) || device_id_hash(32) || expires_at_be(32)
                || cert_level_be(1) || is_valid_byte(1) )"""
    device_id_hash = bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX)

    out = _compose_vhp_component(
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash=device_id_hash,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
    )

    # Manual recompute via spec
    preimage = (
        _FIXTURE_TOKEN_ID.to_bytes(32, "big")
        + device_id_hash
        + _FIXTURE_EXPIRES_AT.to_bytes(32, "big")
        + struct.pack(">B", _FIXTURE_CERT_LEVEL)
        + b"\x01"
    )
    assert len(preimage) == 32 + 32 + 32 + 1 + 1 == 98
    expected = hashlib.sha256(preimage).digest()
    assert out == expected
    assert len(out) == 32

    # is_valid=False flips the trailing byte
    out_invalid = _compose_vhp_component(
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash=device_id_hash,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=False,
    )
    assert out_invalid != out


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-2: end-to-end build
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_2_artifact_builds_end_to_end(tmp_path):
    """build_vhp_card_artifact produces manifest + HTML file + zkba_artifact_log row."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_vhp_2.db")
    store = Store(db_path)

    out_dir = tmp_path / "vhp_verification_card"
    manifest = build_vhp_card_artifact(
        store=store,
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.VHP)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == _FIXTURE_TS_NS
    assert len(manifest.output_hash_hex) == 64
    assert len(manifest.input_commitment_hex) == 64

    # HTML written and hash matches
    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex
    assert b"VHP Verification Card" in html_bytes
    assert b"VALID" in html_bytes

    # Manifest JSON sidecar exists
    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    # DB row inserted with NULL anchor_tx_hash (Track 1 invariant)
    component = _compose_vhp_component(
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.VHP,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.VHP)
    assert row["proof_weight"] == int(ProofWeightClass.CHAIN_ONLY)
    assert row["anchor_tx_hash"] is None


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-3: rebuild idempotency (UNIQUE on commitment_hex)
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_3_rebuild_idempotent(tmp_path):
    """Building the same VHP card twice yields the same manifest fields
    and a single DB row (UNIQUE on commitment_hex)."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_vhp_3.db")
    store = Store(db_path)
    out_dir = tmp_path / "vhp_verification_card"

    kwargs = dict(
        store=store,
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    m1 = build_vhp_card_artifact(**kwargs)
    m2 = build_vhp_card_artifact(**kwargs)

    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    component = _compose_vhp_component(
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.VHP,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    with store._conn() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM zkba_artifact_log WHERE commitment_hex=?",
            (expected_zkba.hex(),),
        ).fetchone()[0]
    assert int(cnt) == 1


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-4: byte-stable determinism across two builds
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_4_byte_stable_two_runs(tmp_path):
    """Same inputs across two independent builds produce byte-identical
    HTML output."""
    from vapi_bridge.store import Store

    db_a = str(tmp_path / "a.db")
    db_b = str(tmp_path / "b.db")
    out_a = tmp_path / "vhp_a"
    out_b = tmp_path / "vhp_b"

    kwargs_template = dict(
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
        ts_ns=_FIXTURE_TS_NS,
    )

    m_a = build_vhp_card_artifact(store=Store(db_a), output_dir=out_a, **kwargs_template)
    m_b = build_vhp_card_artifact(store=Store(db_b), output_dir=out_b, **kwargs_template)

    bytes_a = Path(m_a.output_path).read_bytes()
    bytes_b = Path(m_b.output_path).read_bytes()
    assert bytes_a == bytes_b
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-5: VPM wrapper consumes the ZKBA manifest
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_5_vpm_wrapper_consumes_manifest(tmp_path):
    """The emitted ZKBA manifest wraps cleanly into a vapi-vpm-manifest-v1
    wrapper via wrap_zkba_manifest."""
    from vapi_bridge.store import Store
    from vsd_vpm_wrapper import (
        VPMAnchorStatus,
        VPMCaptureMode,
        VPMIntegrityLabel,
        VPMRevocationStatus,
        VPMVisualState,
        VPM_WRAPPER_SCHEMA,
        VPM_WRAPPER_VERSION,
        ZKBA_WRAPPED_SCHEMA,
        wrap_zkba_manifest,
    )

    db_path = str(tmp_path / "test_vhp_5.db")
    store = Store(db_path)
    out_dir = tmp_path / "vhp_verification_card"

    manifest = build_vhp_card_artifact(
        store=store,
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    zkba_dict = asdict(manifest)
    assert zkba_dict["schema"] == ZKBA_WRAPPED_SCHEMA

    label = VPMIntegrityLabel(
        proof_type="ZKBA-VHP",
        capture_mode=VPMCaptureMode.LIVE.value,
        raw_biometrics_exposed=False,
        consent_active=True,
        zk_verified=False,
        on_chain_anchor=False,
        proof_weight=int(ProofWeightClass.CHAIN_ONLY),
        revocation_status=VPMRevocationStatus.ACTIVE.value,
        limitations=("Session-bound presence; not aimbot/wallhack detection.",),
    )

    wrapper = wrap_zkba_manifest(
        zkba_manifest_dict=zkba_dict,
        vpm_id="VHP-VERIFICATION-CARD-v1",
        audience="Tournament Organizers",
        source_commitment=manifest.input_commitment_hex,
        integrity_label=label,
        visual_state=VPMVisualState.LIVE,
        anchor_status=VPMAnchorStatus.NONE,
    )
    assert wrapper.schema == VPM_WRAPPER_SCHEMA
    assert wrapper.wrapper_version == VPM_WRAPPER_VERSION
    assert wrapper.zkba_manifest_schema == ZKBA_WRAPPED_SCHEMA
    assert wrapper.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert wrapper.anchor_status == VPMAnchorStatus.NONE.value
    assert wrapper.vpm_id == "VHP-VERIFICATION-CARD-v1"
    # zkba_manifest_hash MUST equal SHA-256 of the manifest's canonical bytes
    from vsd_vpm_wrapper import vpm_canonical_json
    expected_hash = hashlib.sha256(vpm_canonical_json(zkba_dict)).hexdigest()
    assert wrapper.zkba_manifest_hash == expected_hash


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-6: G4 manifest validator accepts the emitted manifest
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_6_g4_manifest_validator_accepts(tmp_path):
    """The emitted ZKBA manifest passes validate_zkba_manifest cleanly."""
    from vapi_bridge.store import Store
    from zkba_manifest_validator import validate_zkba_manifest

    db_path = str(tmp_path / "test_vhp_6.db")
    store = Store(db_path)
    out_dir = tmp_path / "vhp_verification_card"

    manifest = build_vhp_card_artifact(
        store=store,
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    result = validate_zkba_manifest(asdict(manifest))
    assert result.valid, f"validator returned errors: {list(result.errors)}"


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-7: per-field tamper detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated_kwargs", [
    ("token_id", {"token_id": _FIXTURE_TOKEN_ID + 1}),
    ("device_id_hash", {"device_id_hash": bytes(32)}),
    ("expires_at", {"expires_at": _FIXTURE_EXPIRES_AT + 1}),
    ("cert_level", {"cert_level": _FIXTURE_CERT_LEVEL + 1}),
    ("is_valid", {"is_valid": not _FIXTURE_IS_VALID}),
])
def test_t_zkba_vhp_7_tamper_detection(field, mutated_kwargs):
    """Mutating any single field changes the component hash."""
    base = dict(
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
    )
    canonical = _compose_vhp_component(**base)
    mutated = {**base, **mutated_kwargs}
    tampered = _compose_vhp_component(**mutated)
    assert tampered != canonical, f"field {field}: tamper not detected"


# ---------------------------------------------------------------------------
# T-ZKBA-VHP-8: audit harness CFSS still PASSES after VHP card inserted
# ---------------------------------------------------------------------------

def test_t_zkba_vhp_8_audit_harness_cfss_unchanged(tmp_path):
    """Inserting a VHP card into zkba_artifact_log MUST NOT affect Section 3
    (Cedar v2 lane authority matrix). The audit harness reads bundle files
    directly and never reads zkba_artifact_log for CFSS, so this is a
    structural invariant — verify it holds."""
    from vapi_bridge.store import Store
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        section_3_lane_matrix,
    )

    db_path = str(tmp_path / "test_vhp_8.db")
    store = Store(db_path)
    out_dir = tmp_path / "vhp_verification_card"

    # Insert VHP card
    build_vhp_card_artifact(
        store=store,
        token_id=_FIXTURE_TOKEN_ID,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        expires_at=_FIXTURE_EXPIRES_AT,
        cert_level=_FIXTURE_CERT_LEVEL,
        is_valid=_FIXTURE_IS_VALID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = section_3_lane_matrix(bundle_dir)
    assert ok, f"CFSS regressed: {findings}"
    assert len(findings) == len(EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"
