"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Hardware Participation Card tests.

Seventh and FINAL ZKBA artifact target. Closes Layer 7 (Methodology Layer)
coverage to 7-of-7 ZKBAClass values. Mirrors the VHP / MARKET / CONSENT /
TOURNAMENT test patterns and adds two HARDWARE-specific invariants:

  - T-ZKBA-HW-9: Sentry-lane authority assertion (Sentry permits
                 tool:zk-artifact-anchor on draft://zk_artifacts/*;
                 Guardian + Curator both FORBID). Mirrors MARKET-9
                 Curator-exclusive assertion + CONSENT-9 Guardian-exclusive
                 assertion — completes the 3-agent CFSS coverage triangle
                 for the new ZKBA artifact at the Cedar policy level.
  - T-ZKBA-HW-10: Layer 7 7-of-7 closure invariant. Confirms HARDWARE
                  occupies ZKBAClass=4, that cross-class commitment
                  collision does not occur with otherwise-identical inputs,
                  and that the manufacturer address bit is independently
                  load-bearing (zero address vs canonical address → different
                  commitment) — surfaces the "first MANUFACTURER-bound
                  audience" novelty as a cryptographic invariant.

T-ZKBA-HW-1:  _compose_hardware_component byte layout matches FROZEN spec
T-ZKBA-HW-2:  build_hardware_card_artifact builds end-to-end (manifest + HTML + DB)
T-ZKBA-HW-3:  rebuild idempotent (same output + UNIQUE constraint on DB)
T-ZKBA-HW-4:  byte-stable across two builds (determinism)
T-ZKBA-HW-5:  VPM wrapper consumes the ZKBA manifest cleanly
T-ZKBA-HW-6:  G4 manifest validator accepts the emitted manifest
T-ZKBA-HW-7:  per-field tamper detection x5 (parametrized)
T-ZKBA-HW-8:  audit harness Section 3 (CFSS) still PASSES after HARDWARE inserted
T-ZKBA-HW-9:  Sentry-lane authority — tool:zk-artifact-anchor permitted on
              draft://zk_artifacts/* for Sentry; FORBIDDEN for Guardian + Curator
T-ZKBA-HW-10: Layer 7 7-of-7 closure — class value, no cross-class collision,
              manufacturer address load-bearing
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
from zkba_compile_hardware_card import (  # noqa: E402
    _compose_hardware_component,
    _parse_hex32,
    _parse_address,
    build_hardware_card_artifact,
)


# Canonical fixture — Sony DualShock Edge CFI-ZCP1 at cert_level=1 certified
# by the bridge wallet (current testnet operator/manufacturer role).
#
# profile_hash: deterministic 32B; in production this is keccak256 of
#   (manufacturer || model || firmwareVersion) — fixture uses a deterministic
#   placeholder value distinguishable from device_id_hash.
# device_id_hash: SHA-256("Sony_DualShock_Edge_CFI-ZCP1") = 10e0169446ba3320...
# manufacturer_address: bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
#   (canonical operator across all post-Phase-O0 ceremonies).
_FIXTURE_PROFILE_HEX = "a1b2c3d4e5f6" + "00" * 26  # 64 hex chars, deterministic placeholder
_FIXTURE_DEVICE_HASH_HEX = "10e0169446ba3320" + "00" * 24  # canonical Sony CFI-ZCP1
_FIXTURE_CERT_LEVEL = 1
_FIXTURE_MFR_ADDR_HEX = "0cf36db57fc4680bcdfc65d1aff96993c57a4692"  # bridge wallet
_FIXTURE_IS_CERTIFIED = True
_FIXTURE_TS_NS = 1778900000000000000


# ---------------------------------------------------------------------------
# T-ZKBA-HW-1: composition byte layout
# ---------------------------------------------------------------------------

def test_t_zkba_hw_1_compose_hardware_component_byte_layout():
    """_compose_hardware_component matches the FROZEN byte layout:
       SHA-256( profile_hash(32) || device_id_hash(32) ||
                cert_level_be(1) || manufacturer_addr(20) || is_certified_byte(1) )
       = 86 bytes preimage."""
    profile_hash = bytes.fromhex(_FIXTURE_PROFILE_HEX)
    device_id_hash = bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX)
    mfr_addr = bytes.fromhex(_FIXTURE_MFR_ADDR_HEX)

    out = _compose_hardware_component(
        profile_hash=profile_hash,
        device_id_hash=device_id_hash,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=mfr_addr,
        is_certified=_FIXTURE_IS_CERTIFIED,
    )

    # Manual recompute via spec
    preimage = (
        profile_hash
        + device_id_hash
        + struct.pack(">B", _FIXTURE_CERT_LEVEL)
        + mfr_addr
        + b"\x01"
    )
    assert len(preimage) == 32 + 32 + 1 + 20 + 1 == 86
    expected = hashlib.sha256(preimage).digest()
    assert out == expected
    assert len(out) == 32

    # is_certified=False flips the trailing byte
    out_revoked = _compose_hardware_component(
        profile_hash=profile_hash,
        device_id_hash=device_id_hash,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=mfr_addr,
        is_certified=False,
    )
    assert out_revoked != out


# ---------------------------------------------------------------------------
# T-ZKBA-HW-2: end-to-end build
# ---------------------------------------------------------------------------

def test_t_zkba_hw_2_artifact_builds_end_to_end(tmp_path):
    """build_hardware_card_artifact produces manifest + HTML file + zkba_artifact_log row."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_hw_2.db")
    store = Store(db_path)

    out_dir = tmp_path / "hardware_participation_card"
    manifest = build_hardware_card_artifact(
        store=store,
        profile_hash_hex=_FIXTURE_PROFILE_HEX,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_address_hex=_FIXTURE_MFR_ADDR_HEX,
        is_certified=_FIXTURE_IS_CERTIFIED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.HARDWARE)
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
    assert b"Hardware Participation Card" in html_bytes
    assert b"CERTIFIED" in html_bytes
    # Manufacturer address surfaced in clear (not hashed) per design
    assert _FIXTURE_MFR_ADDR_HEX.encode() in html_bytes

    # Manifest JSON sidecar exists
    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    # DB row inserted with NULL anchor_tx_hash (Track 1 invariant)
    component = _compose_hardware_component(
        profile_hash=bytes.fromhex(_FIXTURE_PROFILE_HEX),
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=bytes.fromhex(_FIXTURE_MFR_ADDR_HEX),
        is_certified=_FIXTURE_IS_CERTIFIED,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.HARDWARE,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.HARDWARE)
    assert row["proof_weight"] == int(ProofWeightClass.CHAIN_ONLY)
    assert row["anchor_tx_hash"] is None


# ---------------------------------------------------------------------------
# T-ZKBA-HW-3: rebuild idempotency (UNIQUE on commitment_hex)
# ---------------------------------------------------------------------------

def test_t_zkba_hw_3_rebuild_idempotent(tmp_path):
    """Building the same HARDWARE card twice yields the same manifest fields
    and a single DB row (UNIQUE on commitment_hex)."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_hw_3.db")
    store = Store(db_path)
    out_dir = tmp_path / "hardware_participation_card"

    kwargs = dict(
        store=store,
        profile_hash_hex=_FIXTURE_PROFILE_HEX,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_address_hex=_FIXTURE_MFR_ADDR_HEX,
        is_certified=_FIXTURE_IS_CERTIFIED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    m1 = build_hardware_card_artifact(**kwargs)
    m2 = build_hardware_card_artifact(**kwargs)

    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    component = _compose_hardware_component(
        profile_hash=bytes.fromhex(_FIXTURE_PROFILE_HEX),
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=bytes.fromhex(_FIXTURE_MFR_ADDR_HEX),
        is_certified=_FIXTURE_IS_CERTIFIED,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.HARDWARE,
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
# T-ZKBA-HW-4: byte-stable determinism across two builds
# ---------------------------------------------------------------------------

def test_t_zkba_hw_4_byte_stable_two_runs(tmp_path):
    """Same inputs across two independent builds produce byte-identical
    HTML output."""
    from vapi_bridge.store import Store

    db_a = str(tmp_path / "a.db")
    db_b = str(tmp_path / "b.db")
    out_a = tmp_path / "hw_a"
    out_b = tmp_path / "hw_b"

    kwargs_template = dict(
        profile_hash_hex=_FIXTURE_PROFILE_HEX,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_address_hex=_FIXTURE_MFR_ADDR_HEX,
        is_certified=_FIXTURE_IS_CERTIFIED,
        ts_ns=_FIXTURE_TS_NS,
    )

    m_a = build_hardware_card_artifact(store=Store(db_a), output_dir=out_a, **kwargs_template)
    m_b = build_hardware_card_artifact(store=Store(db_b), output_dir=out_b, **kwargs_template)

    bytes_a = Path(m_a.output_path).read_bytes()
    bytes_b = Path(m_b.output_path).read_bytes()
    assert bytes_a == bytes_b
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


# ---------------------------------------------------------------------------
# T-ZKBA-HW-5: VPM wrapper consumes the ZKBA manifest
# ---------------------------------------------------------------------------

def test_t_zkba_hw_5_vpm_wrapper_consumes_manifest(tmp_path):
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

    db_path = str(tmp_path / "test_hw_5.db")
    store = Store(db_path)
    out_dir = tmp_path / "hardware_participation_card"

    manifest = build_hardware_card_artifact(
        store=store,
        profile_hash_hex=_FIXTURE_PROFILE_HEX,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_address_hex=_FIXTURE_MFR_ADDR_HEX,
        is_certified=_FIXTURE_IS_CERTIFIED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    zkba_dict = asdict(manifest)
    assert zkba_dict["schema"] == ZKBA_WRAPPED_SCHEMA

    label = VPMIntegrityLabel(
        proof_type="ZKBA-HARDWARE",
        capture_mode=VPMCaptureMode.LIVE.value,
        raw_biometrics_exposed=False,
        consent_active=True,
        zk_verified=False,
        on_chain_anchor=False,
        proof_weight=int(ProofWeightClass.CHAIN_ONLY),
        revocation_status=VPMRevocationStatus.ACTIVE.value,
        limitations=(
            "Manufacturer-attestation surface; not a biometric humanity proof.",
        ),
    )

    wrapper = wrap_zkba_manifest(
        zkba_manifest_dict=zkba_dict,
        vpm_id="HARDWARE-PARTICIPATION-CARD-v1",
        audience="Tournament Organizers + Hardware Partners",
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
    assert wrapper.vpm_id == "HARDWARE-PARTICIPATION-CARD-v1"
    # zkba_manifest_hash MUST equal SHA-256 of the manifest's canonical bytes
    from vsd_vpm_wrapper import vpm_canonical_json
    expected_hash = hashlib.sha256(vpm_canonical_json(zkba_dict)).hexdigest()
    assert wrapper.zkba_manifest_hash == expected_hash


# ---------------------------------------------------------------------------
# T-ZKBA-HW-6: G4 manifest validator accepts the emitted manifest
# ---------------------------------------------------------------------------

def test_t_zkba_hw_6_g4_manifest_validator_accepts(tmp_path):
    """The emitted ZKBA manifest passes validate_zkba_manifest cleanly."""
    from vapi_bridge.store import Store
    from zkba_manifest_validator import validate_zkba_manifest

    db_path = str(tmp_path / "test_hw_6.db")
    store = Store(db_path)
    out_dir = tmp_path / "hardware_participation_card"

    manifest = build_hardware_card_artifact(
        store=store,
        profile_hash_hex=_FIXTURE_PROFILE_HEX,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_address_hex=_FIXTURE_MFR_ADDR_HEX,
        is_certified=_FIXTURE_IS_CERTIFIED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    result = validate_zkba_manifest(asdict(manifest))
    assert result.valid, f"validator returned errors: {list(result.errors)}"


# ---------------------------------------------------------------------------
# T-ZKBA-HW-7: per-field tamper detection (parametrized x5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated_kwargs", [
    ("profile_hash",      {"profile_hash":      bytes(32)}),
    ("device_id_hash",    {"device_id_hash":    bytes(32)}),
    ("cert_level",        {"cert_level":        _FIXTURE_CERT_LEVEL + 1}),
    ("manufacturer_addr", {"manufacturer_addr": bytes(20)}),
    ("is_certified",      {"is_certified":      not _FIXTURE_IS_CERTIFIED}),
])
def test_t_zkba_hw_7_tamper_detection(field, mutated_kwargs):
    """Mutating any single field changes the component hash."""
    base = dict(
        profile_hash=bytes.fromhex(_FIXTURE_PROFILE_HEX),
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=bytes.fromhex(_FIXTURE_MFR_ADDR_HEX),
        is_certified=_FIXTURE_IS_CERTIFIED,
    )
    canonical = _compose_hardware_component(**base)
    mutated = {**base, **mutated_kwargs}
    tampered = _compose_hardware_component(**mutated)
    assert tampered != canonical, f"field {field}: tamper not detected"


# ---------------------------------------------------------------------------
# T-ZKBA-HW-8: audit harness CFSS still PASSES after HARDWARE inserted
# ---------------------------------------------------------------------------

def test_t_zkba_hw_8_audit_harness_cfss_unchanged(tmp_path):
    """Inserting a HARDWARE card into zkba_artifact_log MUST NOT affect
    Section 3 (Cedar v2 lane authority matrix). The audit harness reads
    bundle files directly and never reads zkba_artifact_log for CFSS, so
    this is a structural invariant — verify it holds."""
    from vapi_bridge.store import Store
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        section_3_lane_matrix,
    )

    db_path = str(tmp_path / "test_hw_8.db")
    store = Store(db_path)
    out_dir = tmp_path / "hardware_participation_card"

    # Insert HARDWARE card
    build_hardware_card_artifact(
        store=store,
        profile_hash_hex=_FIXTURE_PROFILE_HEX,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_address_hex=_FIXTURE_MFR_ADDR_HEX,
        is_certified=_FIXTURE_IS_CERTIFIED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = section_3_lane_matrix(bundle_dir)
    assert ok, f"CFSS regressed: {findings}"
    assert len(findings) == len(EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"


# ---------------------------------------------------------------------------
# T-ZKBA-HW-9: Sentry-lane authority — tool:zk-artifact-anchor permitted on
# draft://zk_artifacts/* for Sentry; FORBIDDEN for Guardian + Curator
# ---------------------------------------------------------------------------

def test_t_zkba_hw_9_sentry_lane_authority_sentry_exclusive():
    """Sentry MUST permit tool:zk-artifact-anchor on draft://zk_artifacts/*.
    Guardian AND Curator MUST forbid the same action — Sentry-exclusive.
    Mirrors MARKET-9 Curator-exclusive + CONSENT-9 Guardian-exclusive
    assertions; with this test, the 3-agent CFSS lane authority matrix is
    empirically verified at the Cedar policy level for ALL three artifact
    lanes (zk_artifacts/, zk_verifications/, zk_listings/).
    """
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        _bundle_policy_effect,
    )
    import json as _json

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    bundles = {}
    for agent_id, fname in [
        ("anchor_sentry", "anchor_sentry_o2_suggest_v2.json"),
        ("guardian", "guardian_o2_suggest_v2.json"),
        ("curator", "curator_o2_suggest_v2.json"),
    ]:
        with open(bundle_dir / fname, encoding="utf-8") as f:
            bundles[agent_id] = _json.load(f)

    # Sentry: PERMIT on draft://zk_artifacts/*
    sentry_effect = _bundle_policy_effect(
        bundles["anchor_sentry"],
        "tool:zk-artifact-anchor",
        "draft://zk_artifacts/*",
    )
    assert sentry_effect == "permit", (
        f"Sentry should permit zk-artifact-anchor on zk_artifacts/*; "
        f"got {sentry_effect!r}"
    )

    # Guardian: FORBID (no resource scope — action-level forbid)
    guardian_effect = _bundle_policy_effect(
        bundles["guardian"],
        "tool:zk-artifact-anchor",
        None,
    )
    assert guardian_effect == "forbid", (
        f"Guardian should forbid zk-artifact-anchor; got {guardian_effect!r}"
    )

    # Curator: FORBID
    curator_effect = _bundle_policy_effect(
        bundles["curator"],
        "tool:zk-artifact-anchor",
        None,
    )
    assert curator_effect == "forbid", (
        f"Curator should forbid zk-artifact-anchor; got {curator_effect!r}"
    )

    # Sanity: the expected lane matrix encodes the same invariant
    sentry_artifact_rows = [
        row for row in EXPECTED_LANE_MATRIX
        if row[1] == "tool:zk-artifact-anchor"
    ]
    assert len(sentry_artifact_rows) == 3, (
        "Expected exactly 3 lane-matrix rows for tool:zk-artifact-anchor "
        "(one permit + two forbids)"
    )
    permit_rows = [r for r in sentry_artifact_rows if r[3] == "permit"]
    forbid_rows = [r for r in sentry_artifact_rows if r[3] == "forbid"]
    assert len(permit_rows) == 1 and permit_rows[0][0] == "anchor_sentry"
    assert len(forbid_rows) == 2
    assert {r[0] for r in forbid_rows} == {"guardian", "curator"}


# ---------------------------------------------------------------------------
# T-ZKBA-HW-10: Layer 7 7-of-7 closure invariant
# ---------------------------------------------------------------------------

def test_t_zkba_hw_10_layer_7_seven_of_seven_closure():
    """Closes Layer 7 coverage to 7-of-7 ZKBAClass values:
       (1) ZKBAClass.HARDWARE == 4 (FROZEN-v1 enum position).
       (2) Cross-class collision does NOT occur: same component bytes +
           same ts_ns through different ZKBAClass values produce
           DIFFERENT commitments. Verifies the domain-tag byte in
           compute_zkba_commitment is load-bearing.
       (3) Manufacturer address is independently load-bearing: zero address
           vs canonical bridge wallet produces different commitments — the
           first ZKBA artifact to bind manufacturer identity into the
           preimage as a publicly-attributable cryptographic surface.
    """
    # (1) Enum position FROZEN
    assert int(ZKBAClass.HARDWARE) == 4

    # (2) Cross-class collision check — compose identical raw component bytes
    # but commit to them under different ZKBAClass values; the resulting
    # commitments MUST differ (domain-tag byte in compute_zkba_commitment
    # is what guarantees this).
    component = _compose_hardware_component(
        profile_hash=bytes.fromhex(_FIXTURE_PROFILE_HEX),
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=bytes.fromhex(_FIXTURE_MFR_ADDR_HEX),
        is_certified=_FIXTURE_IS_CERTIFIED,
    )
    c_hardware = compute_zkba_commitment(
        zkba_class=ZKBAClass.HARDWARE,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    # Iterate all 7 OTHER classes and assert none collide
    other_classes = [
        ZKBAClass.AIT, ZKBAClass.GIC, ZKBAClass.VHP,
        ZKBAClass.CONSENT, ZKBAClass.TOURNAMENT, ZKBAClass.MARKET,
    ]
    for klass in other_classes:
        c_other = compute_zkba_commitment(
            zkba_class=klass,
            proof_weight=ProofWeightClass.CHAIN_ONLY,
            component_hashes=(component,),
            ts_ns=_FIXTURE_TS_NS,
        )
        assert c_other != c_hardware, (
            f"cross-class collision between HARDWARE and {klass.name}"
        )

    # (3) Manufacturer address load-bearing — zero vs canonical
    canonical_mfr = bytes.fromhex(_FIXTURE_MFR_ADDR_HEX)
    zero_mfr = bytes(20)
    assert canonical_mfr != zero_mfr  # sanity

    c_with_canonical = _compose_hardware_component(
        profile_hash=bytes.fromhex(_FIXTURE_PROFILE_HEX),
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=canonical_mfr,
        is_certified=_FIXTURE_IS_CERTIFIED,
    )
    c_with_zero = _compose_hardware_component(
        profile_hash=bytes.fromhex(_FIXTURE_PROFILE_HEX),
        device_id_hash=bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX),
        cert_level=_FIXTURE_CERT_LEVEL,
        manufacturer_addr=zero_mfr,
        is_certified=_FIXTURE_IS_CERTIFIED,
    )
    assert c_with_canonical != c_with_zero, (
        "manufacturer address must be independently load-bearing "
        "(first MANUFACTURER-bound ZKBA audience surface)"
    )
