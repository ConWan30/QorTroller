"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Marketplace Listing Card tests.

Fourth ZKBA artifact target. First non-Sentry-lane artifact + first
MARKETPLACE_DERIVED proof weight + first cross-primitive composition
(LISTING-v1 + CONSENT v1).

T-ZKBA-MARKET-1: _compose_market_component byte layout matches FROZEN spec
T-ZKBA-MARKET-2: build_marketplace_listing_artifact builds end-to-end
T-ZKBA-MARKET-3: rebuild idempotent (UNIQUE on commitment_hex)
T-ZKBA-MARKET-4: byte-stable across two builds (determinism)
T-ZKBA-MARKET-5: VPM wrapper consumes the ZKBA manifest cleanly
T-ZKBA-MARKET-6: G4 manifest validator accepts the emitted manifest
                 (first MARKETPLACE_DERIVED manifest through validator)
T-ZKBA-MARKET-7: per-field tamper detection (listing / tier / cid /
                 consent / suspended each change the commitment)
T-ZKBA-MARKET-8: audit harness Section 3 CFSS still PASSES after MARKET
                 row inserted alongside VHP + AIT rows
T-ZKBA-MARKET-9: explicit cross-agent lane authority — Curator permits
                 tool:zk-marketplace-listing on draft://zk_listings/*;
                 Sentry + Guardian both forbid the same action
T-ZKBA-MARKET-10: IPFS CID encoding invariant — different CID strings
                  produce different commitments; same CID + different
                  fields produces different commitment
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
from zkba_compile_marketplace_listing import (  # noqa: E402
    _compose_market_component,
    build_marketplace_listing_artifact,
)


# Canonical fixture — synthetic but realistic Phase 238 marketplace listing
# under Curator's lane authority. Listing commitment is a Phase-238-shaped
# 32-byte hash; consent_hash is a Phase-237-shaped MARKETPLACE-category
# commitment. Both values are placeholders for the production listing
# pipeline (no on-chain listing was minted at the time of this commit).
_FIXTURE_LISTING_HEX = "ab12cd34" + "ef" * 28      # 64 hex chars (32 bytes)
_FIXTURE_LISTING_BYTES = bytes.fromhex(_FIXTURE_LISTING_HEX)
_FIXTURE_TIER_MILLI = 2000                          # tier 2.0x (Phase 238 tier table)
_FIXTURE_IPFS_CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
_FIXTURE_CONSENT_HEX = "98" * 32                    # 64 hex chars (placeholder)
_FIXTURE_CONSENT_BYTES = bytes.fromhex(_FIXTURE_CONSENT_HEX)
_FIXTURE_SUSPENDED = False
_FIXTURE_TS_NS = 1778900000000000000


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-1: composition byte layout
# ---------------------------------------------------------------------------

def test_t_zkba_market_1_compose_market_component_byte_layout():
    """_compose_market_component matches the FROZEN byte layout:
       SHA-256( listing_commitment(32) || tier_milli_be(8) ||
                ipfs_cid_root(32) || consent_hash(32) || suspended_byte(1) )"""
    out = _compose_market_component(
        listing_commitment=_FIXTURE_LISTING_BYTES,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash=_FIXTURE_CONSENT_BYTES,
        suspended=_FIXTURE_SUSPENDED,
    )

    ipfs_root = hashlib.sha256(_FIXTURE_IPFS_CID.encode("utf-8")).digest()
    preimage = (
        _FIXTURE_LISTING_BYTES
        + _FIXTURE_TIER_MILLI.to_bytes(8, "big")
        + ipfs_root
        + _FIXTURE_CONSENT_BYTES
        + b"\x00"  # not suspended
    )
    assert len(preimage) == 32 + 8 + 32 + 32 + 1 == 105
    expected = hashlib.sha256(preimage).digest()
    assert out == expected
    assert len(out) == 32

    # suspended=True flips the trailing byte
    out_suspended = _compose_market_component(
        listing_commitment=_FIXTURE_LISTING_BYTES,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash=_FIXTURE_CONSENT_BYTES,
        suspended=True,
    )
    assert out_suspended != out


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-2: end-to-end build
# ---------------------------------------------------------------------------

def test_t_zkba_market_2_artifact_builds_end_to_end(tmp_path):
    """build_marketplace_listing_artifact produces manifest + HTML + DB row."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_market_2.db")
    store = Store(db_path)
    out_dir = tmp_path / "marketplace_listing_card"

    manifest = build_marketplace_listing_artifact(
        store=store,
        listing_commitment_hex=_FIXTURE_LISTING_HEX,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash_hex=_FIXTURE_CONSENT_HEX,
        suspended=_FIXTURE_SUSPENDED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.MARKET)
    # First MARKETPLACE_DERIVED artifact in the pipeline
    assert manifest.proof_weight == int(ProofWeightClass.MARKETPLACE_DERIVED)
    assert manifest.proof_weight != int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.proof_weight != int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT)
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == _FIXTURE_TS_NS
    assert len(manifest.output_hash_hex) == 64

    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex
    assert b"Marketplace Listing Card" in html_bytes
    assert b"ACTIVE" in html_bytes
    assert b"MARKETPLACE_DERIVED" in html_bytes

    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    component = _compose_market_component(
        listing_commitment=_FIXTURE_LISTING_BYTES,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash=_FIXTURE_CONSENT_BYTES,
        suspended=_FIXTURE_SUSPENDED,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.MARKET,
        proof_weight=ProofWeightClass.MARKETPLACE_DERIVED,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.MARKET)
    assert row["proof_weight"] == int(ProofWeightClass.MARKETPLACE_DERIVED)
    assert row["anchor_tx_hash"] is None


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-3: rebuild idempotency
# ---------------------------------------------------------------------------

def test_t_zkba_market_3_rebuild_idempotent(tmp_path):
    """Building the same marketplace listing twice yields the same manifest
    fields and a single DB row (UNIQUE on commitment_hex)."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_market_3.db")
    store = Store(db_path)
    out_dir = tmp_path / "marketplace_listing_card"

    kwargs = dict(
        store=store,
        listing_commitment_hex=_FIXTURE_LISTING_HEX,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash_hex=_FIXTURE_CONSENT_HEX,
        suspended=_FIXTURE_SUSPENDED,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    m1 = build_marketplace_listing_artifact(**kwargs)
    m2 = build_marketplace_listing_artifact(**kwargs)
    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    component = _compose_market_component(
        listing_commitment=_FIXTURE_LISTING_BYTES,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash=_FIXTURE_CONSENT_BYTES,
        suspended=_FIXTURE_SUSPENDED,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.MARKET,
        proof_weight=ProofWeightClass.MARKETPLACE_DERIVED,
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
# T-ZKBA-MARKET-4: byte-stable determinism
# ---------------------------------------------------------------------------

def test_t_zkba_market_4_byte_stable_two_runs(tmp_path):
    """Same inputs across two independent builds produce byte-identical HTML."""
    from vapi_bridge.store import Store

    common = dict(
        listing_commitment_hex=_FIXTURE_LISTING_HEX,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash_hex=_FIXTURE_CONSENT_HEX,
        suspended=_FIXTURE_SUSPENDED,
        ts_ns=_FIXTURE_TS_NS,
    )
    m_a = build_marketplace_listing_artifact(
        store=Store(str(tmp_path / "a.db")),
        output_dir=tmp_path / "mk_a",
        **common,
    )
    m_b = build_marketplace_listing_artifact(
        store=Store(str(tmp_path / "b.db")),
        output_dir=tmp_path / "mk_b",
        **common,
    )
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-5: VPM wrapper consumes the manifest
# ---------------------------------------------------------------------------

def test_t_zkba_market_5_vpm_wrapper_consumes_manifest(tmp_path):
    """The emitted ZKBA manifest wraps cleanly into a VPM wrapper.
    First MARKETPLACE_DERIVED proof_weight through wrap_zkba_manifest."""
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

    store = Store(str(tmp_path / "test_market_5.db"))
    manifest = build_marketplace_listing_artifact(
        store=store,
        listing_commitment_hex=_FIXTURE_LISTING_HEX,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash_hex=_FIXTURE_CONSENT_HEX,
        suspended=_FIXTURE_SUSPENDED,
        output_dir=tmp_path / "marketplace_listing_card",
        ts_ns=_FIXTURE_TS_NS,
    )
    zkba_dict = asdict(manifest)
    assert zkba_dict["proof_weight"] == int(ProofWeightClass.MARKETPLACE_DERIVED)

    label = VPMIntegrityLabel(
        proof_type="ZKBA-MARKET",
        capture_mode=VPMCaptureMode.LIVE.value,
        raw_biometrics_exposed=False,
        consent_active=True,
        zk_verified=False,
        on_chain_anchor=False,
        proof_weight=int(ProofWeightClass.MARKETPLACE_DERIVED),
        revocation_status=VPMRevocationStatus.ACTIVE.value,
        limitations=(
            "Marketplace listing state snapshot; reflects listing.suspended "
            "at ts_ns only; subject to Curator review override.",
        ),
    )
    wrapper = wrap_zkba_manifest(
        zkba_manifest_dict=zkba_dict,
        vpm_id="MARKETPLACE-LISTING-CARD-v1",
        audience="Marketplace Buyers",
        source_commitment=manifest.input_commitment_hex,
        integrity_label=label,
        visual_state=VPMVisualState.LIVE,
        anchor_status=VPMAnchorStatus.NONE,
    )
    assert wrapper.schema == VPM_WRAPPER_SCHEMA
    assert wrapper.wrapper_version == VPM_WRAPPER_VERSION
    assert wrapper.zkba_manifest_schema == ZKBA_WRAPPED_SCHEMA
    assert wrapper.proof_weight == int(ProofWeightClass.MARKETPLACE_DERIVED)
    expected_hash = hashlib.sha256(vpm_canonical_json(zkba_dict)).hexdigest()
    assert wrapper.zkba_manifest_hash == expected_hash


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-6: G4 manifest validator accepts the manifest
# ---------------------------------------------------------------------------

def test_t_zkba_market_6_g4_manifest_validator_accepts(tmp_path):
    """The emitted manifest passes validate_zkba_manifest cleanly.
    First MARKETPLACE_DERIVED manifest through the validator's enum check."""
    from vapi_bridge.store import Store
    from zkba_manifest_validator import validate_zkba_manifest

    store = Store(str(tmp_path / "test_market_6.db"))
    manifest = build_marketplace_listing_artifact(
        store=store,
        listing_commitment_hex=_FIXTURE_LISTING_HEX,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash_hex=_FIXTURE_CONSENT_HEX,
        suspended=_FIXTURE_SUSPENDED,
        output_dir=tmp_path / "marketplace_listing_card",
        ts_ns=_FIXTURE_TS_NS,
    )
    result = validate_zkba_manifest(asdict(manifest))
    assert result.valid, f"validator returned errors: {list(result.errors)}"


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-7: per-field tamper detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated_kwargs", [
    ("listing_commitment", {"listing_commitment": bytes(32)}),
    ("tier_multiplier_milli", {"tier_multiplier_milli": _FIXTURE_TIER_MILLI + 500}),
    ("ipfs_cid", {"ipfs_cid": "bafkreialicebobcarol1234567890abcdefg"}),
    ("consent_hash", {"consent_hash": bytes(32)}),
    ("suspended", {"suspended": True}),
])
def test_t_zkba_market_7_tamper_detection(field, mutated_kwargs):
    """Mutating any single field changes the component hash."""
    base = dict(
        listing_commitment=_FIXTURE_LISTING_BYTES,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash=_FIXTURE_CONSENT_BYTES,
        suspended=_FIXTURE_SUSPENDED,
    )
    canonical = _compose_market_component(**base)
    mutated = {**base, **mutated_kwargs}
    tampered = _compose_market_component(**mutated)
    assert tampered != canonical, f"field {field}: tamper not detected"


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-8: audit harness CFSS still PASSES
# ---------------------------------------------------------------------------

def test_t_zkba_market_8_audit_harness_cfss_unchanged(tmp_path):
    """Inserting a MARKET row alongside the GIC/VHP/AIT rows MUST NOT
    affect Section 3 CFSS lane authority."""
    from vapi_bridge.store import Store
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        section_3_lane_matrix,
    )

    store = Store(str(tmp_path / "test_market_8.db"))
    build_marketplace_listing_artifact(
        store=store,
        listing_commitment_hex=_FIXTURE_LISTING_HEX,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        ipfs_cid=_FIXTURE_IPFS_CID,
        consent_hash_hex=_FIXTURE_CONSENT_HEX,
        suspended=_FIXTURE_SUSPENDED,
        output_dir=tmp_path / "marketplace_listing_card",
        ts_ns=_FIXTURE_TS_NS,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = section_3_lane_matrix(bundle_dir)
    assert ok, f"CFSS regressed: {findings}"
    assert len(findings) == len(EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-9: explicit cross-agent lane authority (CFSS)
# ---------------------------------------------------------------------------

def test_t_zkba_market_9_cross_agent_lane_authority_curator_exclusive():
    """Curator MUST permit tool:zk-marketplace-listing on draft://zk_listings/*.
    Sentry AND Guardian MUST forbid the same action — Curator-exclusive."""
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

    # Curator: PERMIT on draft://zk_listings/*
    curator_effect = _bundle_policy_effect(
        bundles["curator"],
        "tool:zk-marketplace-listing",
        "draft://zk_listings/*",
    )
    assert curator_effect == "permit", (
        f"Curator should permit zk-marketplace-listing on zk_listings/*; "
        f"got {curator_effect!r}"
    )

    # Sentry: FORBID (no resource scope — action-level forbid)
    sentry_effect = _bundle_policy_effect(
        bundles["anchor_sentry"],
        "tool:zk-marketplace-listing",
        None,
    )
    assert sentry_effect == "forbid", (
        f"Sentry should forbid zk-marketplace-listing; got {sentry_effect!r}"
    )

    # Guardian: FORBID
    guardian_effect = _bundle_policy_effect(
        bundles["guardian"],
        "tool:zk-marketplace-listing",
        None,
    )
    assert guardian_effect == "forbid", (
        f"Guardian should forbid zk-marketplace-listing; got {guardian_effect!r}"
    )

    # Sanity: the expected lane matrix encodes the same invariant
    curator_market_rows = [
        row for row in EXPECTED_LANE_MATRIX
        if row[1] == "tool:zk-marketplace-listing"
    ]
    assert len(curator_market_rows) == 3, (
        "Expected exactly 3 lane-matrix rows for tool:zk-marketplace-listing "
        "(one permit + two forbids)"
    )
    permit_rows = [r for r in curator_market_rows if r[3] == "permit"]
    forbid_rows = [r for r in curator_market_rows if r[3] == "forbid"]
    assert len(permit_rows) == 1 and permit_rows[0][0] == "curator"
    assert len(forbid_rows) == 2
    assert {r[0] for r in forbid_rows} == {"anchor_sentry", "guardian"}


# ---------------------------------------------------------------------------
# T-ZKBA-MARKET-10: IPFS CID encoding invariant
# ---------------------------------------------------------------------------

def test_t_zkba_market_10_ipfs_cid_encoding_invariant():
    """Different CID strings produce different component hashes; same CID
    with different other fields produces different commitments. CID is
    hashed via SHA-256 of UTF-8 bytes — no CID-internal normalization."""
    base_kwargs = dict(
        listing_commitment=_FIXTURE_LISTING_BYTES,
        tier_multiplier_milli=_FIXTURE_TIER_MILLI,
        consent_hash=_FIXTURE_CONSENT_BYTES,
        suspended=_FIXTURE_SUSPENDED,
    )
    out_cid_a = _compose_market_component(
        ipfs_cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        **base_kwargs,
    )
    out_cid_b = _compose_market_component(
        ipfs_cid="bafkreialicebobcarol1234567890abcdefghijklmnopqrstuvwxyz",
        **base_kwargs,
    )
    assert out_cid_a != out_cid_b, "different CIDs should produce different hashes"

    # Single character change in CID (case-sensitive)
    out_cid_a_upper = _compose_market_component(
        ipfs_cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdI",  # last char upper
        **base_kwargs,
    )
    assert out_cid_a_upper != out_cid_a, "CID case difference should change hash"
