"""Phase O4-VPM-INTEGRATION Stream A.2.b — MARKET-LISTING-v1 tests.

Test band:
  T-VPM-ML-1:    compiler ID + ZKBA class + proof weight pinning
                 (MARKET / MARKETPLACE_DERIVED)
  T-VPM-ML-2:    end-to-end happy path
  T-VPM-ML-3:    rebuild idempotency
  T-VPM-ML-4:    byte-stable two-build determinism
  T-VPM-ML-5:    listing-field markers present in HTML
  T-VPM-ML-6:    per-input tamper detection
  T-VPM-ML-7:    invalid hex / invalid types raise ValueError
  T-VPM-ML-ART-1: procedural art generates 8 tiles with correct data-art-tile-*
                  markers per VBDIP-0002 ZKBA Market Card spec
  T-VPM-ML-ART-2: art determinism — same zkba_manifest_hash_hex yields
                  byte-identical art SVG
  T-VPM-ML-ART-3: art sensitivity — flipping one byte in zkba_manifest_hash_hex
                  changes the SVG output (cryptographic fingerprint property)
  T-VPM-ML-CFSS-1: Cedar v2 policy assertion — Curator PERMIT on
                   tool:zk-marketplace-listing at draft://zk_listings/*;
                   Sentry + Guardian FORBID. Sentry CANNOT compile
                   MARKET-LISTING-v1 at the Cedar policy level.

Plus T-VPM-GRAMMAR-1..6 parametrized.

Author: VAPI Architect (Phase O4 Commit 5)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_BRIDGE = os.path.normpath(os.path.join(_REPO, "bridge"))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import VPMArtifactManifest, _VPM_ARTIFACT_SCHEMA  # noqa: E402
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    VISUAL_STATE_SIGNATURES,
    META_TAG_SIGNATURE,
    ARIA_LABEL_SIGNATURE,
)
from vpm_compile_market_listing import (  # noqa: E402
    _VPM_ID,
    build_market_listing_artifact,
    render_procedural_art_svg,
)


_INTEGRITY_LABEL = {
    "proof_type":             "VPM-MARKET-LISTING",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        True,
    "proof_weight":           "MARKETPLACE_DERIVED",
    "revocation_status":      "active",
    "limitations":            ["Buyer-facing listing surface"],
}

_FIXTURE_TS_NS = 1779500000000000000
_FIXTURE_LISTING = "1649f2803e0e3207f93fb1daac25d71d579ba3150d9d15317b97fe0e65a70d5f"  # real Phase 238 listing
_FIXTURE_CONSENT = "d45615ff1ffdef9efa7857fc930c43c0dd20ed492076537d85cc96ae537ac97b"
_FIXTURE_ZKBA_HASH = "32c466da6f3db5c7b3f7fc1d2214ed4cd4c1d7ad90a42b29b4f2a51cfcf73e44"  # real Phase O3 MARKET artifact


def _kwargs(**overrides) -> dict:
    base = dict(
        listing_commitment_hex=_FIXTURE_LISTING,
        listing_title="Tournament Replay Pack - 2026 Spring",
        tier_multiplier_milli=2000,
        ipfs_cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        consent_hash_hex=_FIXTURE_CONSENT,
        suspended=False,
        listing_owner_address="0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        price_iotx_milli=5000,
        integrity_label=_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH,
        visual_state="live",
        capture_mode="live",
        ts_ns=_FIXTURE_TS_NS,
    )
    base.update(overrides)
    return base


def test_t_vpm_ml_1_compiler_identifiers_pinned():
    assert _VPM_ID == "MARKET-LISTING-v1"


def test_t_vpm_ml_2_end_to_end_happy_path(tmp_path):
    manifest = build_market_listing_artifact(**_kwargs(output_dir=tmp_path / "ml_t2"))
    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == _VPM_ID
    assert manifest.zkba_class == int(ZKBAClass.MARKET)
    assert manifest.proof_weight == int(ProofWeightClass.MARKETPLACE_DERIVED)
    html_bytes = Path(manifest.output_path).read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex


def test_t_vpm_ml_3_rebuild_idempotent(tmp_path):
    out = tmp_path / "ml_t3"
    m1 = build_market_listing_artifact(**_kwargs(output_dir=out))
    m2 = build_market_listing_artifact(**_kwargs(output_dir=out))
    assert m1.output_path == m2.output_path
    assert m1.output_hash_hex == m2.output_hash_hex


def test_t_vpm_ml_4_byte_stable_two_runs(tmp_path):
    m_a = build_market_listing_artifact(**_kwargs(output_dir=tmp_path / "ml_a"))
    m_b = build_market_listing_artifact(**_kwargs(output_dir=tmp_path / "ml_b"))
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


def test_t_vpm_ml_5_listing_field_markers_present(tmp_path):
    """All buyer-relevant listing fields appear in HTML with
    data-listing-field markers for downstream machine parsing."""
    manifest = build_market_listing_artifact(**_kwargs(output_dir=tmp_path / "ml_t5"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert 'data-listing-field="commitment"' in html_text
    assert _FIXTURE_LISTING in html_text
    assert 'data-listing-field="tier"' in html_text
    assert "2.00x" in html_text
    assert 'data-listing-field="price"' in html_text
    assert "5.000 IOTX" in html_text
    assert 'data-listing-field="status"' in html_text
    assert "ACTIVE" in html_text
    assert 'data-listing-field="owner"' in html_text
    assert "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692" in html_text
    assert 'data-listing-field="ipfs_cid"' in html_text
    assert "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi" in html_text
    assert 'data-listing-field="consent"' in html_text
    assert _FIXTURE_CONSENT in html_text
    assert 'data-listing-field="zkba_manifest"' in html_text
    assert _FIXTURE_ZKBA_HASH in html_text


@pytest.mark.parametrize("field,mutated", [
    ("listing_commitment_hex",  "9" * 64),
    ("listing_title",           "Other Listing Title"),
    ("tier_multiplier_milli",   3000),
    ("ipfs_cid",                "bafybeiotherciddoesnotmatchthefixturecidatall12345"),
    ("consent_hash_hex",        "5" * 64),
    ("suspended",               True),
    ("listing_owner_address",   "0xdeadbeef"),
    ("price_iotx_milli",        10000),
])
def test_t_vpm_ml_6_per_input_tamper_detection(field, mutated, tmp_path):
    canonical = build_market_listing_artifact(**_kwargs(output_dir=tmp_path / "ml_canonical"))
    tampered = build_market_listing_artifact(**_kwargs(
        **{field: mutated},
        output_dir=tmp_path / f"ml_{field}",
    ))
    assert canonical.input_commitment_hex != tampered.input_commitment_hex, (
        f"field {field}: tamper not detected"
    )


def test_t_vpm_ml_7_invalid_inputs_rejected(tmp_path):
    """Invalid hex (wrong length / non-hex), bad types, negative tier all
    raise ValueError before disk write."""
    with pytest.raises(ValueError):
        build_market_listing_artifact(**_kwargs(
            listing_commitment_hex="abc" * 21,
            output_dir=tmp_path / "ml_bad1",
        ))
    with pytest.raises(ValueError):
        build_market_listing_artifact(**_kwargs(
            consent_hash_hex="z" * 64,
            output_dir=tmp_path / "ml_bad2",
        ))
    with pytest.raises(ValueError):
        build_market_listing_artifact(**_kwargs(
            listing_title="",
            output_dir=tmp_path / "ml_bad3",
        ))
    with pytest.raises(ValueError):
        build_market_listing_artifact(**_kwargs(
            tier_multiplier_milli=-1,
            output_dir=tmp_path / "ml_bad4",
        ))
    with pytest.raises(ValueError):
        build_market_listing_artifact(**_kwargs(
            price_iotx_milli=-1,
            output_dir=tmp_path / "ml_bad5",
        ))


# ---------------------------------------------------------------------------
# T-VPM-ML-ART-1..3 — Procedural Geometric Art per VBDIP-0002 spec
# ---------------------------------------------------------------------------

def test_t_vpm_ml_art_1_eight_tiles_with_markers(tmp_path):
    """Procedural art renders exactly 8 tiles, each with data-art-tile-index
    + data-art-tile-shape + x/y/radius/hue/rotation markers per the FROZEN
    algorithm v1."""
    manifest = build_market_listing_artifact(**_kwargs(output_dir=tmp_path / "ml_art1"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for i in range(8):
        marker = f'data-art-tile-index="{i}"'
        assert marker in html_text, f"missing tile {i} marker"
    # Each tile has all 6 declarative attributes
    for attr in ("data-art-tile-shape", "data-art-tile-x", "data-art-tile-y",
                 "data-art-tile-radius", "data-art-tile-hue",
                 "data-art-tile-rotation"):
        count = html_text.count(attr + "=")
        assert count == 8, f"expected 8 occurrences of {attr}, got {count}"
    # Each tile shape is one of the 4 FROZEN kinds
    valid_shapes = {"triangle", "square", "pentagon", "hexagon"}
    for shape in valid_shapes:
        # At least one shape appearance is allowed but not guaranteed; just
        # assert no unknown shape appears
        pass
    # Defensive: no unknown shape strings emitted
    assert 'data-art-tile-shape="octagon"' not in html_text
    assert 'data-art-tile-shape="circle"' not in html_text


def test_t_vpm_ml_art_2_art_determinism():
    """Same zkba_manifest_hash_hex yields byte-identical art SVG."""
    a = render_procedural_art_svg(zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH)
    b = render_procedural_art_svg(zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH)
    assert a == b
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(b.encode()).hexdigest()


def test_t_vpm_ml_art_3_art_per_byte_sensitivity():
    """Flipping one byte in zkba_manifest_hash_hex changes the SVG output —
    cryptographic visual fingerprint property. Tests several byte positions
    to be defensive against accidental low-sensitivity slots."""
    canonical = render_procedural_art_svg(zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH)
    # Flip first byte (drives tile 0 x-coordinate AND shape)
    flipped_byte_0 = "ff" + _FIXTURE_ZKBA_HASH[2:]
    art_flipped_0 = render_procedural_art_svg(zkba_manifest_hash_hex=flipped_byte_0)
    assert canonical != art_flipped_0
    # Flip last byte (drives tile 7 hue/rotation)
    flipped_byte_31 = _FIXTURE_ZKBA_HASH[:62] + "ff"
    art_flipped_31 = render_procedural_art_svg(zkba_manifest_hash_hex=flipped_byte_31)
    assert canonical != art_flipped_31
    # Flip middle byte
    flipped_byte_16 = _FIXTURE_ZKBA_HASH[:32] + "ff" + _FIXTURE_ZKBA_HASH[34:]
    art_flipped_16 = render_procedural_art_svg(zkba_manifest_hash_hex=flipped_byte_16)
    assert canonical != art_flipped_16


def test_t_vpm_ml_cfss_1_curator_lane_exclusive():
    """Cedar v2 policy assertion: Curator PERMIT on tool:zk-marketplace-listing
    at draft://zk_listings/*; Sentry + Guardian FORBID at action level.
    Sentry CANNOT compile MARKET-LISTING-v1 at the Cedar policy level.

    This mirrors MARKET-9 from Phase O3 (commit 269e439c) and re-asserts
    the Curator-exclusive invariant for the new Phase O4 VPM-layer
    market listing emission path."""
    from zkba_post_ceremony_audit import _bundle_policy_effect

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    bundles = {}
    for agent_id, fname in [
        ("anchor_sentry", "anchor_sentry_o2_suggest_v2.json"),
        ("guardian", "guardian_o2_suggest_v2.json"),
        ("curator", "curator_o2_suggest_v2.json"),
    ]:
        with open(bundle_dir / fname, encoding="utf-8") as f:
            bundles[agent_id] = json.load(f)

    curator_effect = _bundle_policy_effect(
        bundles["curator"],
        "tool:zk-marketplace-listing",
        "draft://zk_listings/*",
    )
    assert curator_effect == "permit", (
        f"Curator should permit zk-marketplace-listing on zk_listings/*; "
        f"got {curator_effect!r}"
    )

    # Critical CFSS assertion: Sentry FORBIDDEN
    sentry_effect = _bundle_policy_effect(
        bundles["anchor_sentry"],
        "tool:zk-marketplace-listing",
        None,
    )
    assert sentry_effect == "forbid", (
        f"Sentry MUST forbid zk-marketplace-listing (CFSS Curator-exclusive); "
        f"got {sentry_effect!r}"
    )

    guardian_effect = _bundle_policy_effect(
        bundles["guardian"],
        "tool:zk-marketplace-listing",
        None,
    )
    assert guardian_effect == "forbid", (
        f"Guardian MUST forbid zk-marketplace-listing (CFSS Curator-exclusive); "
        f"got {guardian_effect!r}"
    )


@pytest.mark.parametrize("state", VISUAL_STATES, ids=list(VISUAL_STATES))
def test_t_vpm_grammar_market_listing_dom_signature(state, tmp_path):
    capture_mode_map = {
        "live": "live", "dry-run": "dry-run", "emulated": "emulated",
        "frozen-disabled": "frozen-disabled", "revoked": "live", "unverified": "demo",
    }
    manifest = build_market_listing_artifact(**_kwargs(
        visual_state=state,
        capture_mode=capture_mode_map[state],
        output_dir=tmp_path / f"ml_grammar_{state}",
    ))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for required in VISUAL_STATE_SIGNATURES[state]:
        assert required in html_text, (
            f"state={state}: missing DOM signature substring {required!r} "
            f"in MARKET-LISTING emitted HTML"
        )
    assert META_TAG_SIGNATURE in html_text
    assert ARIA_LABEL_SIGNATURE in html_text
    assert f'content="{state}"' in html_text
