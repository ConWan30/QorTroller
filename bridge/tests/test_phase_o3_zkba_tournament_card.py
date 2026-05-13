"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Tournament Eligibility Card tests.

Fifth ZKBA artifact target — deepest composition test to date. First
artifact referencing 3+ FROZEN primitive surfaces simultaneously:
VHP v1 + GIC v1 + VAPIProtocolLens.isFullyEligible() gate.

T-ZKBA-TOURN-1:  _compose_tournament_component byte layout matches FROZEN spec
T-ZKBA-TOURN-2:  build_tournament_card_artifact builds end-to-end
T-ZKBA-TOURN-3:  rebuild idempotent (UNIQUE on commitment_hex)
T-ZKBA-TOURN-4:  byte-stable across two builds (determinism)
T-ZKBA-TOURN-5:  VPM wrapper consumes the ZKBA manifest cleanly
T-ZKBA-TOURN-6:  G4 manifest validator accepts the emitted manifest
T-ZKBA-TOURN-7:  per-field tamper detection across all 7 input fields
                 (vhp_token_id / vhp_is_valid / gic_chain_head /
                  gic_chain_length / is_fully_eligible / device_id_hash /
                  tournament_id)
T-ZKBA-TOURN-8:  audit harness CFSS still PASSES after TOURNAMENT row
                 inserted alongside GIC/VHP/AIT/MARKET rows
T-ZKBA-TOURN-9:  **eligibility semantic invariant** — flipping
                 is_fully_eligible (ELIGIBLE → INELIGIBLE) MUST change
                 the commitment. The verdict bit is load-bearing — a
                 verifier who treats the artifact as authoritative MUST
                 see a different commitment when eligibility flips.
T-ZKBA-TOURN-10: cross-primitive composition depth test — same VHP
                 state + different GIC state produces different
                 commitments (proves both primitive references are
                 load-bearing); ditto same GIC + different VHP.
"""
import hashlib
import json
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
from zkba_compile_tournament_card import (  # noqa: E402
    _compose_tournament_component,
    build_tournament_card_artifact,
)


# Canonical fixture — real on-chain values per CLAUDE.md anchored state:
#   - VHP tokenId=2 from Session 3 mint commit 76c92e9b (canonical Sony DualShock Edge)
#   - GIC_100 head from Phase 239 G3 permanent anchor 2026-05-06
#   - device_id_hash for canonical DualShock Edge CFI-ZCP1
#   - is_fully_eligible: True (bridge wallet currently eligible)
#   - tournament_id: synthetic identifier for the first canonical tournament
_FIXTURE_VHP_TOKEN_ID = 2
_FIXTURE_VHP_IS_VALID = True
_FIXTURE_GIC_HEAD_HEX = "0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da"
_FIXTURE_GIC_HEAD_BYTES = bytes.fromhex(_FIXTURE_GIC_HEAD_HEX)
_FIXTURE_GIC_CHAIN_LENGTH = 100   # GIC_100 milestone
_FIXTURE_IS_FULLY_ELIGIBLE = True
_FIXTURE_DEVICE_HASH_HEX = "10e0169446ba3320" + "00" * 24
_FIXTURE_DEVICE_HASH_BYTES = bytes.fromhex(_FIXTURE_DEVICE_HASH_HEX)
_FIXTURE_TOURNAMENT_ID = 20260601001  # synthetic — first official tournament
_FIXTURE_TS_NS = 1778900000000000000


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-1: composition byte layout
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_1_compose_tournament_component_byte_layout():
    """_compose_tournament_component matches the FROZEN byte layout:
       SHA-256( vhp_token_id_be(32) || vhp_is_valid_byte(1) ||
                gic_chain_head(32) || gic_chain_length_be(8) ||
                is_fully_eligible_byte(1) || device_id_hash(32) ||
                tournament_id_be(8) )"""
    out = _compose_tournament_component(
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash=_FIXTURE_DEVICE_HASH_BYTES,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    preimage = (
        _FIXTURE_VHP_TOKEN_ID.to_bytes(32, "big")
        + b"\x01"
        + _FIXTURE_GIC_HEAD_BYTES
        + _FIXTURE_GIC_CHAIN_LENGTH.to_bytes(8, "big")
        + b"\x01"
        + _FIXTURE_DEVICE_HASH_BYTES
        + _FIXTURE_TOURNAMENT_ID.to_bytes(8, "big")
    )
    assert len(preimage) == 32 + 1 + 32 + 8 + 1 + 32 + 8 == 114
    expected = hashlib.sha256(preimage).digest()
    assert out == expected
    assert len(out) == 32


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-2: end-to-end build
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_2_artifact_builds_end_to_end(tmp_path):
    """build_tournament_card_artifact produces manifest + HTML + DB row.
    Verifies all three referenced primitive values appear in the HTML."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_tourn_2.db")
    store = Store(db_path)
    out_dir = tmp_path / "tournament_eligibility_card"

    manifest = build_tournament_card_artifact(
        store=store,
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head_hex=_FIXTURE_GIC_HEAD_HEX,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.TOURNAMENT)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == _FIXTURE_TS_NS
    assert len(manifest.output_hash_hex) == 64

    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex

    # All three primitive references appear in the HTML output
    assert b"Tournament Eligibility Card" in html_bytes
    assert b"VHP (Verified Human Proof)" in html_bytes
    assert b"GIC (Grind Integrity Chain)" in html_bytes
    assert b"ELIGIBLE" in html_bytes
    assert b"VALID" in html_bytes
    assert _FIXTURE_GIC_HEAD_HEX.encode() in html_bytes  # GIC head surfaced
    assert _FIXTURE_DEVICE_HASH_HEX.encode() in html_bytes  # device binding surfaced

    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    # DB row inserted with NULL anchor_tx_hash (Track 1 invariant)
    component = _compose_tournament_component(
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash=_FIXTURE_DEVICE_HASH_BYTES,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.TOURNAMENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.TOURNAMENT)
    assert row["proof_weight"] == int(ProofWeightClass.CHAIN_ONLY)
    assert row["anchor_tx_hash"] is None


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-3: rebuild idempotency
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_3_rebuild_idempotent(tmp_path):
    """Same inputs twice → same manifest + 1 DB row (UNIQUE constraint)."""
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "test_tourn_3.db"))
    out_dir = tmp_path / "tournament_eligibility_card"

    kwargs = dict(
        store=store,
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head_hex=_FIXTURE_GIC_HEAD_HEX,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    m1 = build_tournament_card_artifact(**kwargs)
    m2 = build_tournament_card_artifact(**kwargs)
    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    component = _compose_tournament_component(
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash=_FIXTURE_DEVICE_HASH_BYTES,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.TOURNAMENT,
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
# T-ZKBA-TOURN-4: byte-stable determinism
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_4_byte_stable_two_runs(tmp_path):
    """Same inputs across two independent builds → byte-identical HTML."""
    from vapi_bridge.store import Store

    common = dict(
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head_hex=_FIXTURE_GIC_HEAD_HEX,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
        ts_ns=_FIXTURE_TS_NS,
    )
    m_a = build_tournament_card_artifact(
        store=Store(str(tmp_path / "a.db")),
        output_dir=tmp_path / "t_a", **common,
    )
    m_b = build_tournament_card_artifact(
        store=Store(str(tmp_path / "b.db")),
        output_dir=tmp_path / "t_b", **common,
    )
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-5: VPM wrapper consumes the manifest
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_5_vpm_wrapper_consumes_manifest(tmp_path):
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

    store = Store(str(tmp_path / "test_tourn_5.db"))
    manifest = build_tournament_card_artifact(
        store=store,
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head_hex=_FIXTURE_GIC_HEAD_HEX,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
        output_dir=tmp_path / "tournament_eligibility_card",
        ts_ns=_FIXTURE_TS_NS,
    )
    zkba_dict = asdict(manifest)

    label = VPMIntegrityLabel(
        proof_type="ZKBA-TOURNAMENT",
        capture_mode=VPMCaptureMode.LIVE.value,
        raw_biometrics_exposed=False,
        consent_active=True,
        zk_verified=False,
        on_chain_anchor=False,
        proof_weight=int(ProofWeightClass.CHAIN_ONLY),
        revocation_status=VPMRevocationStatus.ACTIVE.value,
        limitations=(
            "Eligibility snapshot at ts_ns only; subject to VHP TTL "
            "expiration + GIC chain extension + isFullyEligible recompute.",
        ),
    )
    wrapper = wrap_zkba_manifest(
        zkba_manifest_dict=zkba_dict,
        vpm_id="TOURNAMENT-ELIGIBILITY-CARD-v1",
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
    expected_hash = hashlib.sha256(vpm_canonical_json(zkba_dict)).hexdigest()
    assert wrapper.zkba_manifest_hash == expected_hash


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-6: G4 manifest validator
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_6_g4_manifest_validator_accepts(tmp_path):
    """The emitted manifest passes validate_zkba_manifest cleanly."""
    from vapi_bridge.store import Store
    from zkba_manifest_validator import validate_zkba_manifest

    store = Store(str(tmp_path / "test_tourn_6.db"))
    manifest = build_tournament_card_artifact(
        store=store,
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head_hex=_FIXTURE_GIC_HEAD_HEX,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
        output_dir=tmp_path / "tournament_eligibility_card",
        ts_ns=_FIXTURE_TS_NS,
    )
    result = validate_zkba_manifest(asdict(manifest))
    assert result.valid, f"validator returned errors: {list(result.errors)}"


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-7: per-field tamper detection (7 fields)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated_kwargs", [
    ("vhp_token_id",        {"vhp_token_id": _FIXTURE_VHP_TOKEN_ID + 1}),
    ("vhp_is_valid",        {"vhp_is_valid": not _FIXTURE_VHP_IS_VALID}),
    ("gic_chain_head",      {"gic_chain_head": bytes(32)}),
    ("gic_chain_length",    {"gic_chain_length": _FIXTURE_GIC_CHAIN_LENGTH + 1}),
    ("is_fully_eligible",   {"is_fully_eligible": not _FIXTURE_IS_FULLY_ELIGIBLE}),
    ("device_id_hash",      {"device_id_hash": bytes(32)}),
    ("tournament_id",       {"tournament_id": _FIXTURE_TOURNAMENT_ID + 1}),
])
def test_t_zkba_tourn_7_tamper_detection(field, mutated_kwargs):
    """Mutating any single field changes the component hash."""
    base = dict(
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash=_FIXTURE_DEVICE_HASH_BYTES,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    canonical = _compose_tournament_component(**base)
    mutated = {**base, **mutated_kwargs}
    tampered = _compose_tournament_component(**mutated)
    assert tampered != canonical, f"field {field}: tamper not detected"


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-8: audit harness CFSS still PASSES
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_8_audit_harness_cfss_unchanged(tmp_path):
    """Inserting a TOURNAMENT row alongside the GIC/VHP/AIT/MARKET rows
    MUST NOT affect Section 3 CFSS lane authority."""
    from vapi_bridge.store import Store
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        section_3_lane_matrix,
    )

    store = Store(str(tmp_path / "test_tourn_8.db"))
    build_tournament_card_artifact(
        store=store,
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head_hex=_FIXTURE_GIC_HEAD_HEX,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash_hex=_FIXTURE_DEVICE_HASH_HEX,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
        output_dir=tmp_path / "tournament_eligibility_card",
        ts_ns=_FIXTURE_TS_NS,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = section_3_lane_matrix(bundle_dir)
    assert ok, f"CFSS regressed: {findings}"
    assert len(findings) == len(EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-9: eligibility semantic invariant
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_9_eligibility_semantic_invariant():
    """The is_fully_eligible bit MUST be load-bearing.

    A verifier consulting a Tournament Eligibility Card MUST see a
    different commitment when the underlying isFullyEligible() verdict
    flips. Otherwise a malicious operator could swap ELIGIBLE for
    INELIGIBLE cards while reusing the same commitment.

    Identity invariant: all other state held constant, flipping
    is_fully_eligible must change the commitment.
    """
    base = dict(
        vhp_token_id=_FIXTURE_VHP_TOKEN_ID,
        vhp_is_valid=_FIXTURE_VHP_IS_VALID,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES,
        gic_chain_length=_FIXTURE_GIC_CHAIN_LENGTH,
        device_id_hash=_FIXTURE_DEVICE_HASH_BYTES,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    out_eligible = _compose_tournament_component(
        is_fully_eligible=True, **base,
    )
    out_ineligible = _compose_tournament_component(
        is_fully_eligible=False, **base,
    )
    assert out_eligible != out_ineligible, (
        "eligibility bit MUST be load-bearing in the commitment"
    )

    # Same architecture as the VHP token's is_valid bit (which is also a
    # 1-byte field in the preimage but represents a different semantic
    # axis); both must independently change the commitment.
    out_vhp_valid = _compose_tournament_component(
        is_fully_eligible=True,
        **{**base, "vhp_is_valid": True},
    )
    out_vhp_invalid = _compose_tournament_component(
        is_fully_eligible=True,
        **{**base, "vhp_is_valid": False},
    )
    assert out_vhp_valid != out_vhp_invalid, (
        "vhp_is_valid bit MUST also be load-bearing (independent of eligibility)"
    )


# ---------------------------------------------------------------------------
# T-ZKBA-TOURN-10: cross-primitive composition depth
# ---------------------------------------------------------------------------

def test_t_zkba_tourn_10_cross_primitive_composition_depth():
    """Both the VHP primitive reference and the GIC primitive reference
    MUST be independently load-bearing.

    Same VHP state + different GIC state → different commitment.
    Same GIC state + different VHP state → different commitment.

    This proves all referenced primitive surfaces participate in the
    commitment, not just one. Differs from per-field tamper detection
    (T-ZKBA-TOURN-7) in that it explicitly groups the field set by
    primitive source.
    """
    base = dict(
        is_fully_eligible=_FIXTURE_IS_FULLY_ELIGIBLE,
        device_id_hash=_FIXTURE_DEVICE_HASH_BYTES,
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )

    # Same VHP (token=2, valid=True); two different GIC states
    out_gic_a = _compose_tournament_component(
        vhp_token_id=2, vhp_is_valid=True,
        gic_chain_head=bytes.fromhex("aa" * 32), gic_chain_length=100,
        **base,
    )
    out_gic_b = _compose_tournament_component(
        vhp_token_id=2, vhp_is_valid=True,
        gic_chain_head=bytes.fromhex("bb" * 32), gic_chain_length=200,
        **base,
    )
    assert out_gic_a != out_gic_b, (
        "Same VHP, different GIC → MUST produce different commitments"
    )

    # Same GIC; two different VHP tokens
    out_vhp_a = _compose_tournament_component(
        vhp_token_id=2, vhp_is_valid=True,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES, gic_chain_length=100,
        **base,
    )
    out_vhp_b = _compose_tournament_component(
        vhp_token_id=99, vhp_is_valid=True,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES, gic_chain_length=100,
        **base,
    )
    assert out_vhp_a != out_vhp_b, (
        "Same GIC, different VHP → MUST produce different commitments"
    )

    # And the device-binding primitive is also load-bearing independently
    out_dev_a = _compose_tournament_component(
        vhp_token_id=2, vhp_is_valid=True,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES, gic_chain_length=100,
        is_fully_eligible=True,
        device_id_hash=bytes.fromhex("11" * 32),
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    out_dev_b = _compose_tournament_component(
        vhp_token_id=2, vhp_is_valid=True,
        gic_chain_head=_FIXTURE_GIC_HEAD_BYTES, gic_chain_length=100,
        is_fully_eligible=True,
        device_id_hash=bytes.fromhex("22" * 32),
        tournament_id=_FIXTURE_TOURNAMENT_ID,
    )
    assert out_dev_a != out_dev_b, (
        "Same VHP+GIC+eligibility, different device → MUST produce different commitments"
    )
