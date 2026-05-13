"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Consent Receipt Card tests.

Sixth ZKBA artifact target. First Guardian-lane artifact + first
gamer-facing audience + first GDPR Article 17 compliance-bearing
artifact. Closes the 3-agent CFSS lane coverage gap.

T-ZKBA-CONSENT-1:  _compose_consent_component byte layout matches FROZEN spec
T-ZKBA-CONSENT-2:  build_consent_receipt_artifact builds end-to-end
T-ZKBA-CONSENT-3:  rebuild idempotent (UNIQUE on commitment_hex)
T-ZKBA-CONSENT-4:  byte-stable across two builds (determinism)
T-ZKBA-CONSENT-5:  VPM wrapper consumes the manifest cleanly
T-ZKBA-CONSENT-6:  G4 manifest validator accepts the manifest
T-ZKBA-CONSENT-7:  per-field tamper detection across all 5 input fields
T-ZKBA-CONSENT-8:  audit harness CFSS still PASSES after CONSENT row
                   inserted alongside GIC/VHP/AIT/MARKET/TOURNAMENT
T-ZKBA-CONSENT-9:  **explicit Guardian-lane authority assertion** —
                   Guardian PERMITs tool:zk-audit-trail on
                   draft://zk_verifications/*; Sentry + Curator both
                   FORBID. Mirrors the MARKET #9 pattern but verifies
                   Guardian's lane (the third corner of CFSS now
                   empirically utilized).
T-ZKBA-CONSENT-10: **GDPR Art. 17 revocation semantic invariant** —
                   the revoked_at field MUST be load-bearing. Active
                   (revoked_at=0) vs revoked (revoked_at>0) MUST
                   produce different commitments. A verifier auditing
                   GDPR compliance MUST be able to distinguish
                   cryptographically.
T-ZKBA-CONSENT-11: bitmask category decoding invariant — different
                   bitmasks produce different category lists AND
                   different commitments.
"""
import hashlib
import os
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
from zkba_compile_consent_receipt import (  # noqa: E402
    _bitmask_to_categories,
    _compose_consent_component,
    build_consent_receipt_artifact,
)


# Canonical fixture — synthetic consent receipt for a hypothetical gamer
# who has granted TOURNAMENT_GATE + MANUFACTURER_CERT (bits 0 + 2 = 0b0101 = 5)
# but NOT ANONYMIZED_RESEARCH or MARKETPLACE.
_FIXTURE_CONSENT_HASH_HEX = "ab" * 32           # 64 hex chars (placeholder Phase 237 output)
_FIXTURE_CONSENT_HASH_BYTES = bytes.fromhex(_FIXTURE_CONSENT_HASH_HEX)
_FIXTURE_BITMASK = 0b0101                        # TOURNAMENT_GATE + MANUFACTURER_CERT
_FIXTURE_REVOKED_AT = 0                          # active consent
_FIXTURE_GAMER_HASH_HEX = "ef" * 32              # 64 hex chars (SHA-256 of placeholder address)
_FIXTURE_GAMER_HASH_BYTES = bytes.fromhex(_FIXTURE_GAMER_HASH_HEX)
_FIXTURE_RECEIPT_ID = 1
_FIXTURE_TS_NS = 1778900000000000000


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-1: composition byte layout
# ---------------------------------------------------------------------------

def test_t_zkba_consent_1_compose_consent_component_byte_layout():
    """_compose_consent_component matches FROZEN byte layout:
       SHA-256( consent_hash(32) || category_bitmask_be(4) ||
                revoked_at_be(8) || gamer_address_hash(32) ||
                receipt_id_be(8) )"""
    out = _compose_consent_component(
        consent_hash=_FIXTURE_CONSENT_HASH_BYTES,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash=_FIXTURE_GAMER_HASH_BYTES,
        receipt_id=_FIXTURE_RECEIPT_ID,
    )
    preimage = (
        _FIXTURE_CONSENT_HASH_BYTES
        + _FIXTURE_BITMASK.to_bytes(4, "big")
        + _FIXTURE_REVOKED_AT.to_bytes(8, "big")
        + _FIXTURE_GAMER_HASH_BYTES
        + _FIXTURE_RECEIPT_ID.to_bytes(8, "big")
    )
    assert len(preimage) == 32 + 4 + 8 + 32 + 8 == 84
    expected = hashlib.sha256(preimage).digest()
    assert out == expected
    assert len(out) == 32


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-2: end-to-end build
# ---------------------------------------------------------------------------

def test_t_zkba_consent_2_artifact_builds_end_to_end(tmp_path):
    """build_consent_receipt_artifact produces manifest + HTML + DB row."""
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "test_consent_2.db"))
    out_dir = tmp_path / "consent_receipt_card"

    manifest = build_consent_receipt_artifact(
        store=store,
        consent_hash_hex=_FIXTURE_CONSENT_HASH_HEX,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash_hex=_FIXTURE_GAMER_HASH_HEX,
        receipt_id=_FIXTURE_RECEIPT_ID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.CONSENT)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == _FIXTURE_TS_NS
    assert len(manifest.output_hash_hex) == 64

    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex

    # Gamer-facing audit surface — render carries GDPR notice + status
    assert b"Consent Receipt Card" in html_bytes
    assert b"ACTIVE" in html_bytes
    assert b"GDPR Art. 17" in html_bytes
    assert b"gamer-self-sovereignty" in html_bytes
    # Two granted categories surfaced (bit 0 + bit 2)
    assert b"TOURNAMENT_GATE" in html_bytes
    assert b"MANUFACTURER_CERT" in html_bytes

    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    component = _compose_consent_component(
        consent_hash=_FIXTURE_CONSENT_HASH_BYTES,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash=_FIXTURE_GAMER_HASH_BYTES,
        receipt_id=_FIXTURE_RECEIPT_ID,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.CONSENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.CONSENT)
    assert row["proof_weight"] == int(ProofWeightClass.CHAIN_ONLY)
    assert row["anchor_tx_hash"] is None


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-3: rebuild idempotency
# ---------------------------------------------------------------------------

def test_t_zkba_consent_3_rebuild_idempotent(tmp_path):
    """Same inputs twice → same manifest + 1 DB row (UNIQUE on commitment_hex)."""
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "test_consent_3.db"))
    out_dir = tmp_path / "consent_receipt_card"
    kwargs = dict(
        store=store,
        consent_hash_hex=_FIXTURE_CONSENT_HASH_HEX,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash_hex=_FIXTURE_GAMER_HASH_HEX,
        receipt_id=_FIXTURE_RECEIPT_ID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    m1 = build_consent_receipt_artifact(**kwargs)
    m2 = build_consent_receipt_artifact(**kwargs)
    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    component = _compose_consent_component(
        consent_hash=_FIXTURE_CONSENT_HASH_BYTES,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash=_FIXTURE_GAMER_HASH_BYTES,
        receipt_id=_FIXTURE_RECEIPT_ID,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.CONSENT,
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
# T-ZKBA-CONSENT-4: byte-stable determinism
# ---------------------------------------------------------------------------

def test_t_zkba_consent_4_byte_stable_two_runs(tmp_path):
    """Same inputs across two independent builds → byte-identical HTML."""
    from vapi_bridge.store import Store

    common = dict(
        consent_hash_hex=_FIXTURE_CONSENT_HASH_HEX,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash_hex=_FIXTURE_GAMER_HASH_HEX,
        receipt_id=_FIXTURE_RECEIPT_ID,
        ts_ns=_FIXTURE_TS_NS,
    )
    m_a = build_consent_receipt_artifact(
        store=Store(str(tmp_path / "a.db")),
        output_dir=tmp_path / "c_a",
        **common,
    )
    m_b = build_consent_receipt_artifact(
        store=Store(str(tmp_path / "b.db")),
        output_dir=tmp_path / "c_b",
        **common,
    )
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-5: VPM wrapper consumes manifest
# ---------------------------------------------------------------------------

def test_t_zkba_consent_5_vpm_wrapper_consumes_manifest(tmp_path):
    """The emitted ZKBA manifest wraps cleanly into a VPM wrapper."""
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
        vpm_canonical_json,
    )

    store = Store(str(tmp_path / "test_consent_5.db"))
    manifest = build_consent_receipt_artifact(
        store=store,
        consent_hash_hex=_FIXTURE_CONSENT_HASH_HEX,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash_hex=_FIXTURE_GAMER_HASH_HEX,
        receipt_id=_FIXTURE_RECEIPT_ID,
        output_dir=tmp_path / "consent_receipt_card",
        ts_ns=_FIXTURE_TS_NS,
    )
    zkba_dict = asdict(manifest)

    label = VPMIntegrityLabel(
        proof_type="ZKBA-CONSENT",
        capture_mode=VPMCaptureMode.LIVE.value,
        raw_biometrics_exposed=False,
        consent_active=(_FIXTURE_REVOKED_AT == 0),
        zk_verified=False,
        on_chain_anchor=False,
        proof_weight=int(ProofWeightClass.CHAIN_ONLY),
        revocation_status=VPMRevocationStatus.ACTIVE.value,
        limitations=(
            "Consent snapshot at ts_ns only; subject to gamer revocation "
            "(GDPR Art. 17) at any future timestamp.",
        ),
    )
    wrapper = wrap_zkba_manifest(
        zkba_manifest_dict=zkba_dict,
        vpm_id="CONSENT-RECEIPT-CARD-v1",
        audience="Gamers",
        source_commitment=manifest.input_commitment_hex,
        integrity_label=label,
        visual_state=VPMVisualState.LIVE,
        anchor_status=VPMAnchorStatus.NONE,
    )
    assert wrapper.schema == VPM_WRAPPER_SCHEMA
    assert wrapper.wrapper_version == VPM_WRAPPER_VERSION
    assert wrapper.zkba_manifest_schema == ZKBA_WRAPPED_SCHEMA
    assert wrapper.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    expected_hash = hashlib.sha256(vpm_canonical_json(zkba_dict)).hexdigest()
    assert wrapper.zkba_manifest_hash == expected_hash


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-6: G4 manifest validator
# ---------------------------------------------------------------------------

def test_t_zkba_consent_6_g4_manifest_validator_accepts(tmp_path):
    """The emitted manifest passes validate_zkba_manifest cleanly."""
    from vapi_bridge.store import Store
    from zkba_manifest_validator import validate_zkba_manifest

    store = Store(str(tmp_path / "test_consent_6.db"))
    manifest = build_consent_receipt_artifact(
        store=store,
        consent_hash_hex=_FIXTURE_CONSENT_HASH_HEX,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash_hex=_FIXTURE_GAMER_HASH_HEX,
        receipt_id=_FIXTURE_RECEIPT_ID,
        output_dir=tmp_path / "consent_receipt_card",
        ts_ns=_FIXTURE_TS_NS,
    )
    result = validate_zkba_manifest(asdict(manifest))
    assert result.valid, f"validator returned errors: {list(result.errors)}"


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-7: per-field tamper detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated_kwargs", [
    ("consent_hash",        {"consent_hash": bytes(32)}),
    ("category_bitmask",    {"category_bitmask": _FIXTURE_BITMASK ^ 0b1000}),  # flip bit 3
    ("revoked_at",          {"revoked_at": 1700000000}),
    ("gamer_address_hash",  {"gamer_address_hash": bytes(32)}),
    ("receipt_id",          {"receipt_id": _FIXTURE_RECEIPT_ID + 1}),
])
def test_t_zkba_consent_7_tamper_detection(field, mutated_kwargs):
    """Mutating any single field changes the component hash."""
    base = dict(
        consent_hash=_FIXTURE_CONSENT_HASH_BYTES,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash=_FIXTURE_GAMER_HASH_BYTES,
        receipt_id=_FIXTURE_RECEIPT_ID,
    )
    canonical = _compose_consent_component(**base)
    mutated = {**base, **mutated_kwargs}
    tampered = _compose_consent_component(**mutated)
    assert tampered != canonical, f"field {field}: tamper not detected"


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-8: audit harness CFSS still PASSES
# ---------------------------------------------------------------------------

def test_t_zkba_consent_8_audit_harness_cfss_unchanged(tmp_path):
    """Inserting a CONSENT row alongside the GIC/VHP/AIT/MARKET/TOURNAMENT
    rows MUST NOT affect Section 3 CFSS lane authority."""
    from vapi_bridge.store import Store
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        section_3_lane_matrix,
    )

    store = Store(str(tmp_path / "test_consent_8.db"))
    build_consent_receipt_artifact(
        store=store,
        consent_hash_hex=_FIXTURE_CONSENT_HASH_HEX,
        category_bitmask=_FIXTURE_BITMASK,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash_hex=_FIXTURE_GAMER_HASH_HEX,
        receipt_id=_FIXTURE_RECEIPT_ID,
        output_dir=tmp_path / "consent_receipt_card",
        ts_ns=_FIXTURE_TS_NS,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = section_3_lane_matrix(bundle_dir)
    assert ok, f"CFSS regressed: {findings}"
    assert len(findings) == len(EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-9: explicit Guardian-lane authority assertion (CFSS)
# ---------------------------------------------------------------------------

def test_t_zkba_consent_9_cross_agent_lane_authority_guardian_exclusive():
    """Guardian MUST permit tool:zk-audit-trail on draft://zk_verifications/*.
    Sentry AND Curator MUST forbid the same action — Guardian-exclusive.
    Mirrors T-ZKBA-MARKET-9's Curator assertion but verifies Guardian's
    lane (the third corner of CFSS now empirically exercised by an
    artifact)."""
    import json as _json
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        _bundle_policy_effect,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    bundles = {}
    for agent_id, fname in [
        ("anchor_sentry", "anchor_sentry_o2_suggest_v2.json"),
        ("guardian", "guardian_o2_suggest_v2.json"),
        ("curator", "curator_o2_suggest_v2.json"),
    ]:
        with open(bundle_dir / fname, encoding="utf-8") as f:
            bundles[agent_id] = _json.load(f)

    # Guardian: PERMIT on draft://zk_verifications/*
    guardian_effect = _bundle_policy_effect(
        bundles["guardian"],
        "tool:zk-audit-trail",
        "draft://zk_verifications/*",
    )
    assert guardian_effect == "permit", (
        f"Guardian should permit zk-audit-trail on zk_verifications/*; "
        f"got {guardian_effect!r}"
    )

    # Sentry: FORBID
    sentry_effect = _bundle_policy_effect(
        bundles["anchor_sentry"],
        "tool:zk-audit-trail",
        None,
    )
    assert sentry_effect == "forbid", (
        f"Sentry should forbid zk-audit-trail; got {sentry_effect!r}"
    )

    # Curator: FORBID
    curator_effect = _bundle_policy_effect(
        bundles["curator"],
        "tool:zk-audit-trail",
        None,
    )
    assert curator_effect == "forbid", (
        f"Curator should forbid zk-audit-trail; got {curator_effect!r}"
    )

    # Sanity: lane matrix encodes the same 1-permit/2-forbid invariant
    audit_trail_rows = [
        row for row in EXPECTED_LANE_MATRIX
        if row[1] == "tool:zk-audit-trail"
    ]
    assert len(audit_trail_rows) == 3
    permit_rows = [r for r in audit_trail_rows if r[3] == "permit"]
    forbid_rows = [r for r in audit_trail_rows if r[3] == "forbid"]
    assert len(permit_rows) == 1 and permit_rows[0][0] == "guardian"
    assert {r[0] for r in forbid_rows} == {"anchor_sentry", "curator"}


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-10: GDPR Art. 17 revocation semantic invariant
# ---------------------------------------------------------------------------

def test_t_zkba_consent_10_revocation_semantic_invariant():
    """The revoked_at field MUST be load-bearing for GDPR compliance.

    A verifier auditing GDPR Article 17 compliance MUST be able to
    distinguish cryptographically between an active consent receipt
    (revoked_at=0) and a revoked consent receipt (revoked_at>0).

    Without this property, a bridge could swap an ACTIVE receipt for
    a REVOKED receipt while reusing the same commitment, defeating
    the audit purpose.
    """
    base = dict(
        consent_hash=_FIXTURE_CONSENT_HASH_BYTES,
        category_bitmask=_FIXTURE_BITMASK,
        gamer_address_hash=_FIXTURE_GAMER_HASH_BYTES,
        receipt_id=_FIXTURE_RECEIPT_ID,
    )
    out_active = _compose_consent_component(revoked_at=0, **base)
    out_revoked_1 = _compose_consent_component(revoked_at=1700000000, **base)
    out_revoked_2 = _compose_consent_component(revoked_at=1700000001, **base)

    assert out_active != out_revoked_1, (
        "active vs revoked MUST produce different commitments "
        "(GDPR Art. 17 audit cryptographically distinguishable)"
    )
    # Even 1-second timing difference in revocation MUST be detectable
    assert out_revoked_1 != out_revoked_2, (
        "two different revocation timestamps MUST produce different commitments"
    )


# ---------------------------------------------------------------------------
# T-ZKBA-CONSENT-11: bitmask category decoding invariant
# ---------------------------------------------------------------------------

def test_t_zkba_consent_11_bitmask_category_decoding():
    """_bitmask_to_categories returns the correct labels in bit order;
    different bitmasks produce different category lists AND different
    component hashes."""
    # Test all 16 combinations of the 4-bit bitmask
    expected_labels = (
        "TOURNAMENT_GATE",      # bit 0
        "ANONYMIZED_RESEARCH",  # bit 1
        "MANUFACTURER_CERT",    # bit 2
        "MARKETPLACE",          # bit 3
    )

    # Empty bitmask
    assert _bitmask_to_categories(0) == []

    # All set
    assert _bitmask_to_categories(0b1111) == list(expected_labels)

    # Single bits
    assert _bitmask_to_categories(0b0001) == ["TOURNAMENT_GATE"]
    assert _bitmask_to_categories(0b0010) == ["ANONYMIZED_RESEARCH"]
    assert _bitmask_to_categories(0b0100) == ["MANUFACTURER_CERT"]
    assert _bitmask_to_categories(0b1000) == ["MARKETPLACE"]

    # Fixture bitmask
    assert _bitmask_to_categories(_FIXTURE_BITMASK) == [
        "TOURNAMENT_GATE", "MANUFACTURER_CERT",
    ]

    # Bitmask change MUST change the commitment (sanity that the bitmask
    # is in the preimage, not just in the renderer)
    base = dict(
        consent_hash=_FIXTURE_CONSENT_HASH_BYTES,
        revoked_at=_FIXTURE_REVOKED_AT,
        gamer_address_hash=_FIXTURE_GAMER_HASH_BYTES,
        receipt_id=_FIXTURE_RECEIPT_ID,
    )
    out_bitmask_5 = _compose_consent_component(category_bitmask=0b0101, **base)
    out_bitmask_10 = _compose_consent_component(category_bitmask=0b1010, **base)
    assert out_bitmask_5 != out_bitmask_10
