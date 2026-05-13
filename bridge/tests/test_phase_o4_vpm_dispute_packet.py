"""Phase O4-VPM-INTEGRATION Stream A.2.a — DISPUTE-PACKET-v1 tests.

Test band:
  T-VPM-DP-1:    compiler ID + ZKBA class + proof weight pinning
  T-VPM-DP-2:    end-to-end happy path
  T-VPM-DP-3:    rebuild idempotency
  T-VPM-DP-4:    byte-stable two-build determinism
  T-VPM-DP-5:    case fields surface in HTML with data-dispute-field markers
  T-VPM-DP-6:    per-input tamper detection
  T-VPM-DP-7:    reject unknown adjudicator_agent_id / dispute_status / negative evidence_count
  T-VPM-DP-8:    invalid hex inputs (wrong length / non-hex) raise ValueError
  T-VPM-DP-CFSS-1: Cedar v2 policy assertion — Guardian PERMIT on
                   tool:zk-audit-trail at draft://zk_verifications/*;
                   Sentry + Curator FORBID

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
from vpm_compile_dispute_packet import (  # noqa: E402
    _VPM_ID,
    build_dispute_packet_artifact,
)


_INTEGRITY_LABEL = {
    "proof_type":             "VPM-DISPUTE-PACKET",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        True,
    "proof_weight":           "CHAIN_ONLY",
    "revocation_status":      "active",
    "limitations":            ["Audit-trail packet for a single dispute"],
}

_FIXTURE_TS_NS = 1779400000000000000
_FIXTURE_ZKBA_HASH = "2" * 64
_FIXTURE_RULING_HASH = "a" * 64
_FIXTURE_ATTESTATION_HASH = "b" * 64


def _kwargs(**overrides) -> dict:
    base = dict(
        dispute_id="dispute-000001",
        tournament_id=20260601001,
        disputed_player_address="0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        disputed_ruling_hash_hex=_FIXTURE_RULING_HASH,
        adjudicator_agent_id="guardian",
        evidence_count=3,
        attestation_chain_hash_hex=_FIXTURE_ATTESTATION_HASH,
        dispute_status="open",
        created_ts_ns=_FIXTURE_TS_NS - 60_000_000_000,
        integrity_label=_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH,
        visual_state="live",
        capture_mode="live",
        ts_ns=_FIXTURE_TS_NS,
    )
    base.update(overrides)
    return base


def test_t_vpm_dp_1_compiler_identifiers_pinned():
    assert _VPM_ID == "DISPUTE-PACKET-v1"


def test_t_vpm_dp_2_end_to_end_happy_path(tmp_path):
    manifest = build_dispute_packet_artifact(**_kwargs(output_dir=tmp_path / "dp_t2"))
    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == _VPM_ID
    assert manifest.zkba_class == int(ZKBAClass.CONSENT)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    html_bytes = Path(manifest.output_path).read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex


def test_t_vpm_dp_3_rebuild_idempotent(tmp_path):
    out = tmp_path / "dp_t3"
    m1 = build_dispute_packet_artifact(**_kwargs(output_dir=out))
    m2 = build_dispute_packet_artifact(**_kwargs(output_dir=out))
    assert m1.output_path == m2.output_path
    assert m1.output_hash_hex == m2.output_hash_hex


def test_t_vpm_dp_4_byte_stable_two_runs(tmp_path):
    m_a = build_dispute_packet_artifact(**_kwargs(output_dir=tmp_path / "dp_a"))
    m_b = build_dispute_packet_artifact(**_kwargs(output_dir=tmp_path / "dp_b"))
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


def test_t_vpm_dp_5_case_fields_surface_in_html(tmp_path):
    """All operator-relevant dispute fields appear in emitted HTML with
    data-dispute-field markers for downstream machine parsing."""
    manifest = build_dispute_packet_artifact(**_kwargs(output_dir=tmp_path / "dp_t5"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert 'data-dispute-field="id"' in html_text
    assert "dispute-000001" in html_text
    assert 'data-dispute-field="tournament"' in html_text
    assert "20260601001" in html_text
    assert 'data-dispute-field="status"' in html_text
    assert "OPEN" in html_text
    assert 'data-dispute-field="player"' in html_text
    assert "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692" in html_text
    assert 'data-dispute-field="ruling_hash"' in html_text
    assert _FIXTURE_RULING_HASH in html_text
    assert 'data-dispute-field="adjudicator"' in html_text
    assert "guardian" in html_text
    assert 'data-dispute-field="attestation_chain"' in html_text
    assert _FIXTURE_ATTESTATION_HASH in html_text


@pytest.mark.parametrize("field,mutated", [
    ("dispute_id",                  "dispute-999999"),
    ("tournament_id",               20260801002),
    ("disputed_player_address",     "0xdead"),
    ("disputed_ruling_hash_hex",    "f" * 64),
    ("adjudicator_agent_id",        "curator"),
    ("evidence_count",              0),
    ("attestation_chain_hash_hex",  "e" * 64),
    ("dispute_status",              "escalated"),
])
def test_t_vpm_dp_6_per_input_tamper_detection(field, mutated, tmp_path):
    canonical = build_dispute_packet_artifact(**_kwargs(output_dir=tmp_path / "dp_canonical"))
    tampered = build_dispute_packet_artifact(**_kwargs(
        **{field: mutated},
        output_dir=tmp_path / f"dp_{field}",
    ))
    assert canonical.input_commitment_hex != tampered.input_commitment_hex, (
        f"field {field}: tamper not detected"
    )


def test_t_vpm_dp_7_reject_unknown_enum_values(tmp_path):
    """Unknown adjudicator / status + negative evidence count must raise
    ValueError before disk write."""
    with pytest.raises(ValueError):
        build_dispute_packet_artifact(**_kwargs(
            adjudicator_agent_id="alien",
            output_dir=tmp_path / "dp_bad1",
        ))
    with pytest.raises(ValueError):
        build_dispute_packet_artifact(**_kwargs(
            dispute_status="maybe",
            output_dir=tmp_path / "dp_bad2",
        ))
    with pytest.raises(ValueError):
        build_dispute_packet_artifact(**_kwargs(
            evidence_count=-1,
            output_dir=tmp_path / "dp_bad3",
        ))


def test_t_vpm_dp_8_invalid_hex_rejected(tmp_path):
    with pytest.raises(ValueError) as ex1:
        build_dispute_packet_artifact(**_kwargs(
            disputed_ruling_hash_hex="abc" * 21,
            output_dir=tmp_path / "dp_bad_hex1",
        ))
    assert "disputed_ruling_hash_hex" in str(ex1.value)

    with pytest.raises(ValueError) as ex2:
        build_dispute_packet_artifact(**_kwargs(
            attestation_chain_hash_hex="z" * 64,
            output_dir=tmp_path / "dp_bad_hex2",
        ))
    assert "attestation_chain_hash_hex" in str(ex2.value)


def test_t_vpm_dp_cfss_1_guardian_lane_authority_exclusive():
    """Cedar v2 policy assertion: Guardian PERMIT on tool:zk-audit-trail at
    draft://zk_verifications/*; Sentry + Curator FORBID at action level.
    DISPUTE-PACKET-v1 writes to the Guardian-owned zk_verifications/ lane;
    this test asserts the lane authority triangle structurally holds at the
    Cedar policy level.

    Mirrors CONSENT-9 + MARKET-9 + HW-9 from Phase O3 — closes the CFSS
    coverage triangle for the new Phase O4 dispute artifact lane usage."""
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

    guardian_effect = _bundle_policy_effect(
        bundles["guardian"],
        "tool:zk-audit-trail",
        "draft://zk_verifications/*",
    )
    assert guardian_effect == "permit", (
        f"Guardian should permit zk-audit-trail on zk_verifications/*; "
        f"got {guardian_effect!r}"
    )

    sentry_effect = _bundle_policy_effect(
        bundles["anchor_sentry"],
        "tool:zk-audit-trail",
        None,
    )
    assert sentry_effect == "forbid", (
        f"Sentry should forbid zk-audit-trail; got {sentry_effect!r}"
    )

    curator_effect = _bundle_policy_effect(
        bundles["curator"],
        "tool:zk-audit-trail",
        None,
    )
    assert curator_effect == "forbid", (
        f"Curator should forbid zk-audit-trail; got {curator_effect!r}"
    )


@pytest.mark.parametrize("state", VISUAL_STATES, ids=list(VISUAL_STATES))
def test_t_vpm_grammar_dispute_packet_dom_signature(state, tmp_path):
    capture_mode_map = {
        "live": "live", "dry-run": "dry-run", "emulated": "emulated",
        "frozen-disabled": "frozen-disabled", "revoked": "live", "unverified": "demo",
    }
    manifest = build_dispute_packet_artifact(**_kwargs(
        visual_state=state,
        capture_mode=capture_mode_map[state],
        output_dir=tmp_path / f"dp_grammar_{state}",
    ))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for required in VISUAL_STATE_SIGNATURES[state]:
        assert required in html_text, (
            f"state={state}: missing DOM signature substring {required!r} "
            f"in DISPUTE-PACKET emitted HTML"
        )
    assert META_TAG_SIGNATURE in html_text
    assert ARIA_LABEL_SIGNATURE in html_text
    assert f'content="{state}"' in html_text
